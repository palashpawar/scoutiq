"""End-to-end smoke test against running servers (default: through the Next.js proxy).

    python scripts/smoke_test.py [--base http://localhost:3000]

Walks the two-minute demo: search -> shortlist -> evidence -> compare data -> refine.
"""
from __future__ import annotations

import argparse
import sys

import httpx

EXAMPLE = ("Find three midfielders under age 25 who progress the ball well, contribute defensively, "
           "and have an estimated market value below €15 million.")


def check(cond: bool, msg: str) -> None:
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    base = ap.parse_args().base.rstrip("/")
    c = httpx.Client(base_url=base, timeout=60)

    html = c.get("/")
    check(html.status_code == 200 and "ScoutIQ" in html.text, "frontend serves the search page")

    cfg = c.get("/api/config").json()
    check(len(cfg["examples"]) == 3, f"config loaded (mode={cfg['mode']}, {cfg['dataset']['league']} {cfg['dataset']['season']})")
    check("META_API_KEY" not in str(cfg) and "Bearer" not in str(cfg), "config exposes no credentials")

    for ex in cfg["examples"]:
        r = c.post("/api/search", json={"text": ex}).json()
        check(len(r["results"]) > 0, f"example returns players: {ex[:50]}…")

    r = c.post("/api/search", json={"text": EXAMPLE}).json()
    q = r["query"]
    check(q["role"] == "central_midfielder" and q["maximum_age"] == 24 and q["maximum_market_value_eur"] == 15_000_000,
          f"request parsed into filters ({r['parse_source']})")
    res = r["results"]
    check(len(res) == 3, "shortlist has three players")
    check(all(p["age"] <= 24 and p["market_value_eur"] <= 15_000_000 and p["minutes"] >= 900 for p in res),
          "every player satisfies the filters")
    check(all(abs(sum(m["contribution"] or 0 for m in p["metrics"] if m["weight"] > 0) - p["score"]) < 0.2 for p in res),
          "metric contributions sum to each fit score")

    s = c.post("/api/summaries", json={"query": q, "player_ids": [p["id"] for p in res]}).json()
    check(set(map(int, s["summaries"])) == {p["id"] for p in res}, f"evidence summaries for all players ({s['source']})")

    top = res[0]
    check(bool(top["strengths"]) or bool(top["tradeoffs"]), "player detail has strengths/trade-offs")
    check(all(m["percentile"] is None or 0 <= m["percentile"] <= 100 for m in top["metrics"]), "percentiles in range")

    compare_ids = [p["id"] for p in res[:3]]
    check(len(set(compare_ids)) == 3, "three distinct players available to compare")

    ref = c.post("/api/refine", json={"query": q, "text": "Increase the budget to €25 million"}).json()
    check(ref["query"]["maximum_market_value_eur"] == 25_000_000, f"refinement raised budget: {ref['changes']}")
    ref2 = c.post("/api/refine", json={"query": q, "text": "Prioritize defensive contribution"}).json()
    dw = lambda qq: sum(qq["metric_weights"].get(k, 0) for k in ("tackles", "interceptions", "ball_recoveries"))
    check(dw(ref2["query"]) > dw(q), "refinement increased defensive weights")

    bad = c.post("/api/search", json={"text": "best goalkeeper"})
    check(bad.status_code == 422, "unsupported role returns a friendly 422")
    print("Smoke test complete.")


if __name__ == "__main__":
    main()
