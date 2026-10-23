import pytest

from app.data import Dataset
from app.schemas import StructuredQuery
from app.scoring import rank, score_player
from conftest import META, make_player


def q(**kw):
    base = dict(role="central_midfielder", maximum_age=None, minimum_minutes=900,
                maximum_market_value_eur=None, metric_weights={"progressive_passes": 1.0}, result_limit=10)
    base.update(kw)
    return StructuredQuery(**base)


def tiny():
    players = [make_player(i, progressive_passes=float(i), tackles=float(5 - i)) for i in range(1, 5)]
    return Dataset(players, dict(META))


# ------------------------------------------------------------- percentiles
def test_midrank_percentiles():
    ds = tiny()
    assert [ds.percentile("central_midfielder", "progressive_passes", v) for v in (1, 2, 3, 4)] == [12.5, 37.5, 62.5, 87.5]
    assert ds.percentile("central_midfielder", "progressive_passes", 0.5) == 0.0
    assert ds.percentile("central_midfielder", "progressive_passes", 99) == 100.0
    assert ds.percentile("central_midfielder", "progressive_passes", None) is None


def test_percentile_pool_excludes_low_minutes_players():
    ds = Dataset([make_player(1, progressive_passes=1.0), make_player(2, progressive_passes=2.0),
                  make_player(3, minutes=100, progressive_passes=100.0)], dict(META))
    # Player 3 is not in the reference pool, so player 2 is the top of it.
    assert ds.percentile("central_midfielder", "progressive_passes", 2.0) == 75.0
    assert ds.percentile("central_midfielder", "progressive_passes", 100.0) == 100.0


# ------------------------------------------------------------------ scores
def test_weighted_score_matches_hand_calculation():
    ds = tiny()
    p = ds.by_id[4]  # progressive_passes pct 87.5, tackles pct 12.5
    s = score_player(ds, p, {"progressive_passes": 0.75, "tackles": 0.25})
    assert s["score"] == pytest.approx(0.75 * 87.5 + 0.25 * 12.5, abs=0.05)
    assert s["coverage"] == 1.0
    assert sum(c["contribution"] for c in s["components"]) == pytest.approx(s["score"], abs=0.1)


def test_weights_are_normalised_by_schema():
    sq = q(metric_weights={"progressive_passes": 3, "tackles": 1})
    assert sq.metric_weights == {"progressive_passes": 0.75, "tackles": 0.25}
    assert sum(q(metric_weights={"tackles": 0.2, "interceptions": 0.2, "xa": 0.1}).metric_weights.values()) == pytest.approx(1.0)


def test_zero_weights_dropped():
    sq = q(metric_weights={"progressive_passes": 1, "tackles": 0})
    assert sq.metric_weights == {"progressive_passes": 1.0}


def test_missing_metric_renormalises_and_discloses(ds):
    p = ds.by_id[106]  # pass_completion is None
    weights = {"progressive_passes": 0.5, "pass_completion": 0.5}
    s = score_player(ds, p, weights)
    pp = ds.percentile("central_midfielder", "progressive_passes", 8.0)
    assert s["coverage"] == 0.5
    assert s["score"] == pytest.approx(pp, abs=0.05)  # all weight shifts to the available metric
    missing = next(c for c in s["components"] if c["key"] == "pass_completion")
    assert missing["contribution"] is None and missing["effective_weight"] == 0.0

    res = rank(ds, q(metric_weights=weights))
    r = next(r for r in res["results"] if r["id"] == 106)
    assert r["coverage"] == 0.5
    assert any("Pass completion" in m and "redistributed" in m for m in r["missing_data"])


def test_all_metrics_missing_player_is_not_ranked():
    ds = Dataset([make_player(1), make_player(2, pass_completion=None)], dict(META))
    res = rank(ds, q(metric_weights={"pass_completion": 1}))
    assert [r["id"] for r in res["results"]] == [1]


def test_ranking_order_and_contributions(ds):
    res = rank(ds, q(minimum_minutes=900, maximum_age=25, maximum_market_value_eur=10_000_000))
    scores = [r["score"] for r in res["results"]]
    assert scores == sorted(scores, reverse=True)
    top = res["results"][0]
    assert top["id"] == 10
    weighted = [m for m in top["metrics"] if m["weight"] > 0]
    assert sum(m["contribution"] for m in weighted) == pytest.approx(top["score"], abs=0.1)


# ----------------------------------------------------------------- filters
def test_filters_exclude_and_count(ds):
    res = rank(ds, q(maximum_age=25, maximum_market_value_eur=10_000_000))
    ids = {r["id"] for r in res["results"]}
    assert not ids & {101, 102, 103, 104, 105, 201}
    ex = res["counts"]["excluded"]
    assert ex == {"minutes": 1, "age_over_limit": 1, "age_unknown": 1, "value_over_budget": 1, "value_unknown": 1}


def test_filters_inclusive_boundaries(ds):
    res = rank(ds, q(maximum_age=22, maximum_market_value_eur=5_000_000, minimum_minutes=2000))
    assert 10 in {r["id"] for r in res["results"]}
    res = rank(ds, q(maximum_age=21))
    assert 10 not in {r["id"] for r in res["results"]}


def test_no_age_filter_keeps_unknown_age(ds):
    res = rank(ds, q())
    assert 102 in {r["id"] for r in res["results"]}
    r = next(r for r in res["results"] if r["id"] == 102)
    assert any("age unknown" in m for m in r["missing_data"])


def test_result_limit(ds):
    assert len(rank(ds, q(result_limit=3))["results"]) == 3


def test_budget_disabled_without_valuations():
    players = [make_player(i, value=None, progressive_passes=float(i)) for i in range(1, 6)]
    ds = Dataset(players, {**META, "valuations_enabled": "0"})
    res = rank(ds, q(maximum_market_value_eur=1_000_000))
    assert res["budget_active"] is False
    assert len(res["results"]) == 5
    assert any("Budget ignored" in f for f in res["applied_filters"])
    assert res["value_analysis"]["enabled"] is False
    assert all(r["value_signal"] is None for r in res["results"])


def test_value_signal_requires_coverage():
    # Only 2 of 12 players valued -> coverage too low for any value claims.
    players = [make_player(i, value=None if i > 2 else 1_000_000, progressive_passes=float(i)) for i in range(1, 13)]
    res = rank(Dataset(players, dict(META)), q())
    assert res["value_analysis"]["enabled"] is False


def test_value_signal_flags_cheap_high_scorer():
    players = [make_player(i, value=i * 1_000_000, progressive_passes=float(i)) for i in range(1, 13)]
    players.append(make_player(99, value=500_000, progressive_passes=20.0))
    res = rank(Dataset(players, dict(META)), q())
    sig = next(r for r in res["results"] if r["id"] == 99)["value_signal"]
    assert sig["potentially_undervalued"] is True and sig["gap"] >= 30
    assert "not evidence of a market inefficiency" in sig["explanation"]
    # A player whose score and value ranks agree is not flagged.
    assert next(r for r in res["results"] if r["id"] == 12)["value_signal"]["potentially_undervalued"] is False
