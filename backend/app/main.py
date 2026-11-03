"""ScoutIQ FastAPI application."""
from __future__ import annotations

import logging
import time
from collections import OrderedDict, defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .catalog import EXAMPLE_QUERIES, METRICS, PROFILES, ROLES
from .config import settings
from .data import Dataset, get_dataset
from .explain import evidence_payload, template_summary
from .llm import LLMError, MetaClient
from .parser import ParseResult, UnsupportedRequest, parse_request, refine_request
from .schemas import RankRequest, RefineRequest, SearchRequest, StructuredQuery, SummariesRequest
from .scoring import rank

log = logging.getLogger("scoutiq")
app = FastAPI(title="ScoutIQ API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

# Overridable in tests.
state = {"dataset": None, "llm": None}


def dataset() -> Dataset:
    return state["dataset"] or get_dataset()


def llm() -> MetaClient:
    if state["llm"] is None:
        state["llm"] = MetaClient()
    return state["llm"]


# --------------------------------------------------------------- middleware
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "POST":
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            return JSONResponse({"detail": "Too many requests — please wait a moment."}, status_code=429)
        q.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    msgs = []
    for e in exc.errors()[:5]:
        loc = ".".join(str(p) for p in e["loc"] if p not in ("body",))
        msgs.append(f"{loc}: {e['msg']}" if loc else e["msg"])
    return JSONResponse({"detail": "Invalid request — " + "; ".join(msgs)}, status_code=422)


@app.exception_handler(UnsupportedRequest)
async def unsupported_handler(_: Request, exc: UnsupportedRequest):
    return JSONResponse({"detail": str(exc)}, status_code=422)


# ------------------------------------------------------------------ helpers
_parse_cache: "OrderedDict[str, StructuredQuery]" = OrderedDict()


def _mode() -> str:
    return "meta" if llm().enabled else "demo"


def _interpret(text: str) -> tuple[StructuredQuery, str, list[str], list[str]]:
    """Return (query, source, notes, warnings). Falls back to the demo parser."""
    demo: ParseResult = parse_request(text)  # also enforces supported roles
    if not llm().enabled:
        return demo.query, "demo", demo.notes, demo.warnings
    key = " ".join(text.lower().split())
    if key in _parse_cache:
        return _parse_cache[key], "meta", ["Interpreted by the Meta model (cached)."], []
    try:
        q = llm().parse_query(text)
    except LLMError as exc:
        log.warning("parse fallback: %s", exc)
        return demo.query, "demo_fallback", demo.notes, demo.warnings + [
            f"Meta model unavailable ({exc}); used the deterministic demo parser instead."]
    _parse_cache[key] = q
    if len(_parse_cache) > 256:
        _parse_cache.popitem(last=False)
    return q, "meta", [f"Interpreted by {settings.meta_model}."], demo.warnings


def _changes(old: StructuredQuery, new: StructuredQuery) -> list[str]:
    def fmt(field: str, v) -> str:
        if v is None:
            return "no limit"
        if field == "role":
            return ROLES[v]
        if field == "maximum_market_value_eur":
            return f"€{v / 1e6:g}M"
        return str(v)

    labels = {"role": "Role", "maximum_age": "Max age", "minimum_minutes": "Min minutes",
              "maximum_market_value_eur": "Budget", "result_limit": "Players shown"}
    out = []
    for f, label in labels.items():
        a, b = getattr(old, f), getattr(new, f)
        if a != b:
            out.append(f"{label}: {fmt(f, a)} → {fmt(f, b)}")
    if old.metric_weights != new.metric_weights:
        out.append("metric weights updated")
    return out


def _response(q: StructuredQuery, source: str, notes: list[str], warnings: list[str], **extra) -> dict:
    ds = dataset()
    result = rank(ds, q)
    if q.maximum_market_value_eur is not None and not ds.valuations_enabled:
        warnings = warnings + ["Budget filtering is disabled: this dataset has no market-value estimates."]
    if not result["results"]:
        warnings = warnings + ["No players match every filter. Try raising the age or budget cap, or lowering minimum minutes."]
    return {"mode": _mode(), "parse_source": source, "notes": notes, "warnings": warnings, **extra, **result}


# ------------------------------------------------------------------- routes
@app.get("/api/config")
def config():
    ds = dataset()
    return {
        "mode": _mode(),
        "model": settings.meta_model if llm().enabled else None,
        "dataset": ds.public_meta(),
        "roles": ROLES,
        "metrics": [{"key": k, "label": m.label, "short": m.short, "group": m.group,
                     "description": m.description, "unit": m.unit} for k, m in METRICS.items()],
        "profiles": [{"key": p.key, "label": p.label, "role": p.role, "weights": p.weights, "blurb": p.blurb}
                     for p in PROFILES.values()],
        "examples": EXAMPLE_QUERIES,
        "limits": {"max_text": 500, "max_results": 10, "max_compare": 3},
    }


@app.post("/api/search")
def search(req: SearchRequest):
    q, source, notes, warnings = _interpret(req.text)
    return _response(q, source, notes, warnings)


@app.post("/api/rank")
def rank_route(req: RankRequest):
    return _response(req.query, "manual", ["Filters edited manually."], [])


@app.post("/api/refine")
def refine(req: RefineRequest):
    demo = refine_request(req.query, req.text)
    if not llm().enabled:
        q, source, notes, warnings = demo.query, "demo", demo.notes, demo.warnings
    else:
        key = req.query.cache_key() + "|" + " ".join(req.text.lower().split())
        try:
            if key not in _parse_cache:
                _parse_cache[key] = llm().refine_query(req.query, req.text)
                if len(_parse_cache) > 256:
                    _parse_cache.popitem(last=False)
            q, source, notes, warnings = _parse_cache[key], "meta", [
                f"Refinement interpreted by {settings.meta_model}."], []
        except LLMError as exc:
            log.warning("refine fallback: %s", exc)
            q, source, notes = demo.query, "demo_fallback", demo.notes
            warnings = demo.warnings + [f"Meta model unavailable ({exc}); used the deterministic demo parser instead."]
    return _response(q, source, notes, warnings, changes=_changes(req.query, q))


@app.post("/api/summaries")
def summaries(req: SummariesRequest):
    ds = dataset()
    result = rank(ds, req.query)
    by_id = {r["id"]: r for r in result["results"]}
    ids = [i for i in req.player_ids if i in by_id]
    templates = {i: template_summary(by_id[i]) for i in ids}
    if not llm().enabled or not ids:
        return {"source": "template", "summaries": templates, "warnings": []}
    try:
        written = llm().summarize(evidence_payload(result, ids, ds.meta), ids)
    except LLMError as exc:
        log.warning("summary fallback: %s", exc)
        return {"source": "template_fallback", "summaries": templates,
                "warnings": [f"Meta model unavailable ({exc}); showing template summaries."]}
    merged = {i: written.get(i, templates[i]) for i in ids}
    rejected = [i for i in ids if i not in written]
    return {"source": "meta", "summaries": merged, "model": settings.meta_model,
            "warnings": ["Some model summaries failed validation and were replaced by templates."] if rejected else []}


@app.get("/api/health")
def health():
    return {"ok": True, "mode": _mode(), "players": len(dataset().players)}
