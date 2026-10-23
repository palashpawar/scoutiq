import pytest
from pydantic import ValidationError

from app.catalog import EXAMPLE_QUERIES
from app.parser import UnsupportedRequest, parse_request, refine_request
from app.schemas import StructuredQuery


# ------------------------------------------------------- schema validation
VALID = dict(role="winger", maximum_age=23, minimum_minutes=900, maximum_market_value_eur=10_000_000,
             metric_weights={"xa": 0.5, "dribbles": 0.5}, result_limit=5)


def test_valid_query_accepted():
    assert StructuredQuery(**VALID).role == "winger"


@pytest.mark.parametrize("patch", [
    {"role": "goalkeeper"},
    {"maximum_age": 12},
    {"minimum_minutes": -5},
    {"minimum_minutes": 99999},
    {"maximum_market_value_eur": 50},
    {"metric_weights": {}},
    {"metric_weights": {"xa": 0}},
    {"metric_weights": {"vibes": 1.0}},
    {"metric_weights": {"xa": -1}},
    {"metric_weights": {"xa": float("nan")}},
    {"result_limit": 0},
    {"result_limit": 50},
    {"sql": "DROP TABLE players"},
])
def test_invalid_query_rejected(patch):
    with pytest.raises(ValidationError):
        StructuredQuery(**{**VALID, **patch})


# ---------------------------------------------------------- demo parsing
def test_primary_example_parses():
    q = parse_request(EXAMPLE_QUERIES[0]).query
    assert q.role == "central_midfielder"
    assert q.maximum_age == 24
    assert q.maximum_market_value_eur == 15_000_000
    assert q.result_limit == 3
    w = q.metric_weights
    assert {"progressive_passes", "progressive_carries", "tackles", "interceptions"} <= set(w)
    assert w["progressive_passes"] > w["key_passes"]


def test_winger_example():
    q = parse_request(EXAMPLE_QUERIES[1]).query
    assert (q.role, q.maximum_age, q.maximum_market_value_eur) == ("winger", 23, 10_000_000)
    assert "tackles" not in q.metric_weights  # "beat defenders" is not a defensive request


def test_striker_example():
    q = parse_request(EXAMPLE_QUERIES[2]).query
    assert (q.role, q.maximum_age, q.minimum_minutes, q.maximum_market_value_eur) == ("striker", 26, 1500, 20_000_000)


@pytest.mark.parametrize("text,expected", [
    ("defensive midfielder under 21", "defensive_midfielder"),
    ("holding midfielder who wins the ball", "defensive_midfielder"),
])
def test_defensive_mid_profile(text, expected):
    q = parse_request(text).query
    assert q.metric_weights["tackles"] >= 0.2


def test_unsupported_role_rejected():
    with pytest.raises(UnsupportedRequest):
        parse_request("Find me a centre-back under 23")


def test_no_role_defaults_with_warning():
    res = parse_request("someone cheap and young please")
    assert res.query.role == "central_midfielder" and res.warnings


def test_pound_amount_warns():
    res = parse_request("striker under £20m")
    assert res.query.maximum_market_value_eur == 20_000_000
    assert any("euros" in w for w in res.warnings)


# --------------------------------------------------------- follow-ups
@pytest.fixture
def base():
    return parse_request(EXAMPLE_QUERIES[0]).query


def test_followup_prioritise_defence(base):
    new = refine_request(base, "Prioritize defensive contribution").query
    defensive = lambda q: sum(q.metric_weights.get(k, 0) for k in ("tackles", "interceptions", "ball_recoveries"))
    assert defensive(new) > defensive(base) + 0.1
    assert (new.role, new.maximum_age, new.maximum_market_value_eur, new.result_limit) == \
        (base.role, base.maximum_age, base.maximum_market_value_eur, base.result_limit)


def test_followup_budget_absolute(base):
    new = refine_request(base, "Increase the budget to €25 million").query
    assert new.maximum_market_value_eur == 25_000_000
    assert new.metric_weights == base.metric_weights


def test_followup_budget_relative(base):
    assert refine_request(base, "increase the budget by €5m").query.maximum_market_value_eur == 20_000_000


def test_followup_remove_budget(base):
    assert refine_request(base, "remove the budget").query.maximum_market_value_eur is None


def test_followup_age_and_limit(base):
    new = refine_request(base, "show five players under 23").query
    assert (new.maximum_age, new.result_limit) == (22, 5)


def test_followup_role_switch_resets_weights(base):
    new = refine_request(base, "show wingers instead").query
    assert new.role == "winger" and "xa" in new.metric_weights


def test_followup_deemphasise(base):
    new = refine_request(base, "ignore passing accuracy").query
    assert "pass_completion" not in new.metric_weights


def test_followup_unrecognised_is_noop_with_warning(base):
    res = refine_request(base, "hmm interesting")
    assert res.query == base and res.warnings
