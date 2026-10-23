"""Deterministic filtering and ranking. No language model is involved here.

Score = sum(weight_i * percentile_i) / sum(weight_i) over the weighted metrics
the player actually has. Missing metrics are dropped and the remaining weights
renormalised; `coverage` reports the share of the requested weight that was
available, so reduced evidence is always disclosed.
"""
from __future__ import annotations

from collections import OrderedDict

from .catalog import METRICS, PROFILES, ROLE_DISPLAY_METRICS, ROLES
from .data import PERCENTILE_POOL_MIN_MINUTES, Dataset
from .schemas import StructuredQuery

STRENGTH_PCT = 75
TRADEOFF_PCT = 40
LOW_SAMPLE_MINUTES = 1500
VALUE_COVERAGE_MIN = 0.6  # share of role pool with a valuation before value signals are shown
UNDERVALUED_GAP = 30      # score percentile minus value percentile, in points
UNDERVALUED_MIN_SCORE_PCT = 60


def score_player(ds: Dataset, player: dict, weights: dict[str, float]) -> dict:
    role = player["role"]
    rows, used = [], 0.0
    for key, w in weights.items():
        m = METRICS[key]
        value = player.get(m.column)
        pct = ds.percentile(role, key, value)
        rows.append({"key": key, "weight": w, "value": value, "percentile": pct})
        if pct is not None:
            used += w
    contributions = []
    score = 0.0
    for r in rows:
        if r["percentile"] is None or used == 0:
            r["effective_weight"] = 0.0
            r["contribution"] = None
        else:
            r["effective_weight"] = round(r["weight"] / used, 4)
            r["contribution"] = round(r["effective_weight"] * r["percentile"], 2)
            score += r["contribution"]
        contributions.append(r)
    total = sum(weights.values()) or 1.0
    return {
        "score": round(score, 1) if used > 0 else None,
        "coverage": round(used / total, 4),
        "components": contributions,
    }


def _metric_view(ds: Dataset, player: dict, key: str, components: dict) -> dict:
    m = METRICS[key]
    value = player.get(m.column)
    comp = components.get(key)
    return {
        "key": key,
        "label": m.label,
        "short": m.short,
        "group": m.group,
        "unit": m.unit,
        "description": m.description,
        "value": None if value is None else round(value, 2),
        "percentile": ds.percentile(player["role"], key, value),
        "weight": comp["weight"] if comp else 0.0,
        "effective_weight": comp["effective_weight"] if comp else 0.0,
        "contribution": comp["contribution"] if comp else None,
    }


def _strengths_tradeoffs(metrics: list[dict], player: dict) -> tuple[list[str], list[str]]:
    strengths = [f"{m['label']}: {m['percentile']:.0f}th percentile"
                 for m in sorted(metrics, key=lambda m: -(m["percentile"] or 0))
                 if m["percentile"] is not None and m["percentile"] >= STRENGTH_PCT][:4]
    tradeoffs = [f"{m['label']}: {m['percentile']:.0f}th percentile (weighted {m['weight'] * 100:.0f}%)"
                 for m in sorted(metrics, key=lambda m: (m["percentile"] or 0))
                 if m["weight"] > 0 and m["percentile"] is not None and m["percentile"] <= TRADEOFF_PCT][:3]
    if player["minutes"] < LOW_SAMPLE_MINUTES:
        tradeoffs.append(f"Limited sample: {player['minutes']} league minutes — per-90 rates are less stable.")
    return strengths, tradeoffs


def _value_signals(ds: Dataset, query: StructuredQuery) -> tuple[dict[int, dict], dict]:
    """Transparent value heuristic over the role pool (minutes filter only).

    For every role player meeting the minutes filter, rank the performance score
    and the market-value estimate as percentiles. A positive gap means the
    player's output ranks higher than their price within this dataset.
    """
    pool = [p for p in ds.players if p["role"] == query.role and p["minutes"] >= query.minimum_minutes]
    valued = [p for p in pool if p.get("market_value_eur") is not None]
    coverage = len(valued) / len(pool) if pool else 0.0
    info = {"pool_size": len(pool), "valued": len(valued), "coverage": round(coverage, 3),
            "enabled": ds.valuations_enabled and coverage >= VALUE_COVERAGE_MIN and len(valued) >= 10}
    if not info["enabled"]:
        return {}, info
    scored = [(p, score_player(ds, p, query.metric_weights)["score"]) for p in valued]
    scored = [(p, s) for p, s in scored if s is not None]
    scores = sorted(s for _, s in scored)
    values = sorted(p["market_value_eur"] for p, _ in scored)

    def pct(arr, x):
        lo = sum(1 for a in arr if a < x)
        eq = sum(1 for a in arr if a == x)
        return round(100.0 * (lo + 0.5 * eq) / len(arr), 1)

    out = {}
    for p, s in scored:
        sp, vp = pct(scores, s), pct(values, p["market_value_eur"])
        gap = round(sp - vp, 1)
        flag = gap >= UNDERVALUED_GAP and sp >= UNDERVALUED_MIN_SCORE_PCT
        out[p["id"]] = {
            "score_percentile": sp,
            "value_percentile": vp,
            "gap": gap,
            "potentially_undervalued": flag,
            "explanation": (
                f"Within {len(scored)} valued {ROLES[query.role].lower()}s with {query.minimum_minutes}+ minutes, "
                f"this player's score ranks at the {sp:.0f}th percentile and their estimated value at the "
                f"{vp:.0f}th. "
                + ("A gap of 30+ points with a top-40% score is flagged as potentially undervalued. "
                   if flag else "")
                + "This is a dataset-relative heuristic, not evidence of a market inefficiency."
            ),
        }
    return out, info


def _applied_filters(ds: Dataset, q: StructuredQuery) -> list[str]:
    f = [f"Role: {ROLES[q.role]}", f"Minimum minutes: {q.minimum_minutes}"]
    if q.maximum_age is not None:
        f.append(f"Age ≤ {q.maximum_age} (as of {ds.meta.get('age_reference_date', 'mid-season')})")
    if q.maximum_market_value_eur is not None:
        if ds.valuations_enabled:
            f.append(f"Estimated market value ≤ €{q.maximum_market_value_eur / 1e6:g}M")
        else:
            f.append("Budget ignored: no valuation data in this dataset")
    f.append(f"Show top {q.result_limit}")
    return f


def closest_profile(q: StructuredQuery) -> str | None:
    best, best_overlap = None, 0.0
    for p in PROFILES.values():
        if p.role != q.role:
            continue
        overlap = sum(min(q.metric_weights.get(k, 0), w) for k, w in p.weights.items())
        if overlap > best_overlap:
            best, best_overlap = p.label, overlap
    return best if best_overlap >= 0.6 else None


_cache: "OrderedDict[str, dict]" = OrderedDict()
_CACHE_MAX = 256


def rank(ds: Dataset, q: StructuredQuery) -> dict:
    key = f"{ds.token}:{q.cache_key()}"
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    result = _rank(ds, q)
    _cache[key] = result
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return result


def _rank(ds: Dataset, q: StructuredQuery) -> dict:
    role_players = [p for p in ds.players if p["role"] == q.role]
    excluded = {"minutes": 0, "age_over_limit": 0, "age_unknown": 0, "value_over_budget": 0, "value_unknown": 0}
    budget_active = q.maximum_market_value_eur is not None and ds.valuations_enabled
    candidates = []
    for p in role_players:
        if p["minutes"] < q.minimum_minutes:
            excluded["minutes"] += 1
            continue
        if q.maximum_age is not None:
            if p.get("age") is None:
                excluded["age_unknown"] += 1
                continue
            if p["age"] > q.maximum_age:
                excluded["age_over_limit"] += 1
                continue
        if budget_active:
            if p.get("market_value_eur") is None:
                excluded["value_unknown"] += 1
                continue
            if p["market_value_eur"] > q.maximum_market_value_eur:
                excluded["value_over_budget"] += 1
                continue
        candidates.append(p)

    value_signals, value_info = _value_signals(ds, q)
    scored = []
    for p in candidates:
        s = score_player(ds, p, q.metric_weights)
        if s["score"] is None:
            continue
        scored.append((p, s))
    scored.sort(key=lambda ps: (-ps[1]["score"], -ps[0]["minutes"], ps[0]["id"]))

    results = []
    for i, (p, s) in enumerate(scored[: q.result_limit], start=1):
        comps = {c["key"]: c for c in s["components"]}
        keys = list(q.metric_weights) + [k for k in ROLE_DISPLAY_METRICS[q.role] if k not in q.metric_weights]
        metrics = [_metric_view(ds, p, k, comps) for k in keys]
        strengths, tradeoffs = _strengths_tradeoffs(metrics, p)
        missing = [f"{METRICS[c['key']].label} unavailable — its {c['weight'] * 100:.0f}% weight was "
                   f"redistributed across the other metrics." for c in s["components"] if c["percentile"] is None]
        if p.get("age") is None:
            missing.append("Date of birth not matched to Transfermarkt — age unknown.")
        if ds.valuations_enabled and p.get("market_value_eur") is None:
            missing.append("No market-value estimate matched for this player.")
        results.append({
            "rank": i,
            "id": p["id"],
            "name": p["name"],
            "display_name": p["display_name"],
            "club": p["club"],
            "league": p["league"],
            "season": p["season"],
            "role": p["role"],
            "role_label": ROLES[p["role"]],
            "primary_position": p["primary_position"],
            "age": p.get("age"),
            "minutes": p["minutes"],
            "matches": p["matches"],
            "starts": p["starts"],
            "goals": p.get("goals_total"),
            "assists": p.get("assists_total"),
            "market_value_eur": p.get("market_value_eur"),
            "valuation_date": p.get("valuation_date"),
            "valuation_match_confidence": p.get("match_confidence"),
            "score": s["score"],
            "coverage": s["coverage"],
            "metrics": metrics,
            "strengths": strengths,
            "tradeoffs": tradeoffs,
            "missing_data": missing,
            "value_signal": value_signals.get(p["id"]),
        })

    return {
        "query": q.model_dump(),
        "applied_filters": _applied_filters(ds, q),
        "profile_label": closest_profile(q),
        "weights": [{"key": k, "label": METRICS[k].label, "weight": w} for k, w in q.metric_weights.items()],
        "counts": {"role_players": len(role_players), "eligible": len(scored), "excluded": excluded},
        "budget_active": budget_active,
        "value_analysis": value_info,
        "percentile_note": (f"Percentiles compare each player with {ROLES[q.role].lower()}s who played "
                            f"{PERCENTILE_POOL_MIN_MINUTES}+ minutes in {ds.meta.get('league')} "
                            f"{ds.meta.get('season')} (dataset-relative, not league-wide or all-time)."),
        "results": results,
    }
