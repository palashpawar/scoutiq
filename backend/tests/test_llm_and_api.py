import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.catalog import EXAMPLE_QUERIES
from app.config import Settings
from app.llm import LLMError, MetaClient

GOOD_QUERY = {"role": "central_midfielder", "maximum_age": 24, "minimum_minutes": 900,
              "maximum_market_value_eur": 15000000,
              "metric_weights": {"progressive_passes": 0.6, "tackles": 0.4}, "result_limit": 3}


def cfg(**kw):
    return Settings(meta_api_key="test-key", meta_api_base_url="https://api.example.test/v1",
                    meta_model="muse-spark-1.3", meta_timeout_seconds=2, **kw)


def client_returning(content=None, status=200, raw=None, exc=None, seen=None):
    def handler(request: httpx.Request):
        if seen is not None:
            seen.append(request)
        if exc:
            raise exc
        if raw is not None:
            return httpx.Response(status, text=raw)
        body = {"choices": [{"message": {"role": "assistant", "content": content if isinstance(content, str) else json.dumps(content)}}]}
        return httpx.Response(status, json=body)
    return MetaClient(cfg(), transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------- adapter
def test_request_shape_follows_meta_docs():
    seen = []
    q = client_returning(GOOD_QUERY, seen=seen).parse_query("find midfielders")
    req = seen[0]
    assert str(req.url) == "https://api.example.test/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer test-key"
    body = json.loads(req.content)
    assert body["model"] == "muse-spark-1.3"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert body["messages"][0]["role"] == "developer"
    assert q.metric_weights == {"progressive_passes": 0.6, "tackles": 0.4}


@pytest.mark.parametrize("kwargs", [
    {"content": "not json at all"},
    {"content": {**GOOD_QUERY, "role": "goalkeeper"}},
    {"content": {**GOOD_QUERY, "sql": "SELECT *"}},
    {"content": {**GOOD_QUERY, "metric_weights": {"charisma": 1}}},
    {"content": [1, 2, 3]},
    {"raw": "{}"},
    {"status": 500, "content": GOOD_QUERY},
    {"status": 401, "content": GOOD_QUERY},
    {"exc": httpx.ReadTimeout("slow")},
    {"exc": httpx.ConnectError("down")},
])
def test_adapter_failures_raise_llmerror(kwargs):
    with pytest.raises(LLMError):
        client_returning(**kwargs).parse_query("find midfielders")


def test_compat_retry_for_openai_compatible_servers():
    """A server that rejects the `developer` role gets one retry with `system`."""
    seen = []

    def handler(request: httpx.Request):
        seen.append(json.loads(request.content))
        if seen[-1]["messages"][0]["role"] == "developer":
            return httpx.Response(400, json={"error": "unsupported role"})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(GOOD_QUERY)}}]})

    q = MetaClient(cfg(), transport=httpx.MockTransport(handler)).parse_query("midfielders")
    assert q.result_limit == 3 and len(seen) == 2
    retry = seen[1]
    assert retry["messages"][0]["role"] == "system"
    assert "reasoning_effort" not in retry and "max_completion_tokens" not in retry
    assert retry["response_format"]["type"] == "json_schema"


def test_no_retry_on_auth_failure():
    seen = []
    with pytest.raises(LLMError):
        client_returning(status=401, content=GOOD_QUERY, seen=seen).parse_query("x")
    assert len(seen) == 1


def test_error_message_never_leaks_key():
    try:
        client_returning(status=401, content=GOOD_QUERY).parse_query("x")
    except LLMError as exc:
        assert "test-key" not in str(exc)


def test_disabled_without_key():
    c = MetaClient(Settings(meta_api_key=""))
    assert not c.enabled
    with pytest.raises(LLMError):
        c.parse_query("x")


def test_summaries_filter_unsupported_claims():
    c = client_returning({"summaries": [
        {"player_id": 1, "summary": "Ranks highly for progressive passes in this dataset."},
        {"player_id": 2, "summary": "A natural leader with no injury concerns."},
        {"player_id": 999, "summary": "Not in the shortlist at all."},
    ]})
    out = c.summarize({"players": []}, [1, 2])
    assert out == {1: "Ranks highly for progressive passes in this dataset."}


# -------------------------------------------------------------------- API
@pytest.fixture
def api(ds):
    main.state["dataset"] = ds
    main.state["llm"] = MetaClient(Settings(meta_api_key=""))
    main._parse_cache.clear()
    main._hits.clear()
    yield TestClient(main.app)
    main.state.update(dataset=None, llm=None)


def test_config_reports_demo_mode(api):
    r = api.get("/api/config").json()
    assert r["mode"] == "demo" and r["model"] is None
    assert len(r["examples"]) == 3
    assert "test-key" not in json.dumps(r)


def test_search_demo_mode(api):
    r = api.post("/api/search", json={"text": EXAMPLE_QUERIES[0]}).json()
    assert r["parse_source"] == "demo"
    assert r["query"]["maximum_age"] == 24
    assert all(p["age"] <= 24 and p["market_value_eur"] <= 15_000_000 for p in r["results"])


def test_search_falls_back_when_model_fails(api):
    main.state["llm"] = client_returning(status=503, content=GOOD_QUERY)
    r = api.post("/api/search", json={"text": EXAMPLE_QUERIES[0]})
    assert r.status_code == 200
    body = r.json()
    assert body["parse_source"] == "demo_fallback"
    assert any("Meta model unavailable" in w for w in body["warnings"])
    assert body["results"]


def test_search_uses_model_when_valid(api):
    main.state["llm"] = client_returning(GOOD_QUERY)
    body = api.post("/api/search", json={"text": "anything"}).json()
    assert body["parse_source"] == "meta" and body["query"]["result_limit"] == 3


def test_refine_falls_back_and_reports_changes(api):
    main.state["llm"] = client_returning(raw="garbage")
    base = api.post("/api/search", json={"text": EXAMPLE_QUERIES[0]}).json()["query"]
    r = api.post("/api/refine", json={"query": base, "text": "Increase the budget to €25 million"}).json()
    assert r["parse_source"] == "demo_fallback"
    assert r["query"]["maximum_market_value_eur"] == 25_000_000
    assert "Budget: €15M → €25M" in r["changes"]


def test_summaries_fallback_to_templates(api):
    main.state["llm"] = client_returning(exc=httpx.ReadTimeout("slow"))
    q = {**GOOD_QUERY, "maximum_market_value_eur": None, "maximum_age": None}
    ids = [p["id"] for p in api.post("/api/rank", json={"query": q}).json()["results"]]
    r = api.post("/api/summaries", json={"query": q, "player_ids": ids}).json()
    assert r["source"] == "template_fallback"
    assert set(map(int, r["summaries"])) == set(ids)


def test_input_limits(api):
    assert api.post("/api/search", json={"text": "x" * 501}).status_code == 422
    assert api.post("/api/search", json={"text": ""}).status_code == 422
    assert api.post("/api/search", json={"text": "midfielders", "extra": 1}).status_code == 422
    bad = {**GOOD_QUERY, "metric_weights": {"__import__": 1}}
    assert api.post("/api/rank", json={"query": bad}).status_code == 422


def test_unsupported_role_is_friendly(api):
    r = api.post("/api/search", json={"text": "best goalkeeper under 25"})
    assert r.status_code == 422 and "Goalkeepers" in r.json()["detail"]


def test_rate_limit(api):
    object.__setattr__(main.settings, "rate_limit_per_minute", 3)  # Settings is frozen
    try:
        codes = [api.post("/api/rank", json={"query": GOOD_QUERY}).status_code for _ in range(5)]
    finally:
        object.__setattr__(main.settings, "rate_limit_per_minute", 30)
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
