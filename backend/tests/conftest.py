import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog import METRICS  # noqa: E402
from app.data import Dataset  # noqa: E402

BASE = {c.column: 1.0 for c in METRICS.values()}


def make_player(pid, role="central_midfielder", minutes=2000, age=22, value=5_000_000, **metrics):
    p = {
        "id": pid, "name": f"Test Player {pid}", "display_name": f"Test Player {pid}", "club": "Test FC",
        "league": "Test League", "season": "2015/16", "role": role, "primary_position": "Center Midfield",
        "role_share": 1.0, "minutes": minutes, "matches": 20, "starts": 20, "age": age,
        "date_of_birth": None, "market_value_eur": value, "valuation_date": "2016-01-01" if value else None,
        "tm_player_id": None, "match_confidence": 1.0, "goals_total": 1, "assists_total": 1, "np_xg_total": 1,
        **BASE,
    }
    for k, v in metrics.items():
        p[METRICS[k].column] = v
    return p


META = {"league": "Test League", "season": "2015/16", "valuations_enabled": "1", "age_reference_date": "2016-01-01"}


@pytest.fixture
def ds():
    """Ten midfielders with progressive_passes 1..10 and tackles 10..1, plus edge cases."""
    players = [make_player(i, progressive_passes=float(i), tackles=float(11 - i)) for i in range(1, 11)]
    players += [
        make_player(101, minutes=500, progressive_passes=50.0),              # below minutes filters
        make_player(102, age=None, progressive_passes=9.5),                   # unknown age
        make_player(103, value=None, progressive_passes=9.5),                 # unknown value
        make_player(104, age=30, progressive_passes=9.9),                     # too old
        make_player(105, value=40_000_000, progressive_passes=9.9),           # over budget
        make_player(106, progressive_passes=8.0, pass_completion=None),       # missing optional metric
        make_player(201, role="winger"),
    ]
    return Dataset(players, dict(META))
