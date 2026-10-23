"""Template scouting summaries (demo mode / fallback) and the evidence payload
given to the model. The model sees only retrieved records, computed scores and
source metadata."""
from __future__ import annotations


def _ordinal(n: float) -> str:
    n = int(round(n))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def template_summary(r: dict) -> str:
    weighted = [m for m in r["metrics"] if m["weight"] > 0 and m["percentile"] is not None]
    best = sorted(weighted, key=lambda m: -m["percentile"])[:2]
    worst = sorted(weighted, key=lambda m: m["percentile"])[:1]
    age = f", {r['age']}" if r.get("age") is not None else ""
    parts = [f"{r['display_name']} ({r['club']}{age}) scores {r['score']:.0f}/100 for this brief."]
    if best:
        parts.append("Strongest weighted areas: " + " and ".join(
            f"{m['short'].lower()} ({_ordinal(m['percentile'])} pct, {m['value']}{'%' if m['unit'] == '%' else ' per 90'})"
            for m in best) + ".")
    if worst and worst[0]["percentile"] < 50:
        parts.append(f"Trade-off: {worst[0]['short'].lower()} sits at the {_ordinal(worst[0]['percentile'])} percentile.")
    vs = r.get("value_signal")
    if vs and vs.get("potentially_undervalued"):
        parts.append("Output ranks well above estimated value within this dataset (heuristic).")
    parts.append(f"Based on {r['minutes']:,} league minutes in {r['season']}"
                 + (" — limited sample." if r["minutes"] < 1500 else "."))
    if r["coverage"] < 1:
        parts.append(f"Only {r['coverage'] * 100:.0f}% of the scoring weight had data.")
    return " ".join(parts)


def evidence_payload(rank_result: dict, ids: list[int], meta: dict) -> dict:
    players = []
    for r in rank_result["results"]:
        if r["id"] not in ids:
            continue
        players.append({
            "player_id": r["id"],
            "name": r["display_name"],
            "club": r["club"],
            "age": r["age"],
            "minutes": r["minutes"],
            "score_0_100": r["score"],
            "weight_coverage": r["coverage"],
            "metrics": [{"metric": m["label"], "per90_or_pct": m["value"],
                         "percentile": None if m["percentile"] is None else round(m["percentile"]),
                         "weight": m["effective_weight"]} for m in r["metrics"]],
            "estimated_market_value_eur": r["market_value_eur"],
            "valuation_date": r["valuation_date"],
            "value_signal": r["value_signal"] and {
                "potentially_undervalued": r["value_signal"]["potentially_undervalued"],
                "score_percentile": r["value_signal"]["score_percentile"],
                "value_percentile": r["value_signal"]["value_percentile"]},
            "missing_data": r["missing_data"],
        })
    return {
        "brief": {"filters": rank_result["applied_filters"], "weights": rank_result["weights"]},
        "source": {"league": meta.get("league"), "season": meta.get("season"),
                   "stats": meta.get("stats_source"), "valuations": meta.get("valuation_source")},
        "percentile_note": rank_result["percentile_note"],
        "players": players,
    }
