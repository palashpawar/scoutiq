"""Loads the SQLite player table into memory once (it is small) and serves
cached, dataset-relative percentile lookups."""
from __future__ import annotations

import itertools
import sqlite3
from bisect import bisect_left, bisect_right
from functools import lru_cache
from pathlib import Path

from .catalog import METRICS

# Percentiles are computed against role-mates with at least this many minutes,
# so tiny samples do not distort the reference distribution.
PERCENTILE_POOL_MIN_MINUTES = 900
_tokens = itertools.count()


class Dataset:
    def __init__(self, players: list[dict], meta: dict[str, str]):
        self.players = players
        self.by_id = {p["id"]: p for p in players}
        self.meta = meta
        self.token = next(_tokens)  # cache namespace, unique per instance
        self._sorted: dict[tuple[str, str], list[float]] = {}

    @classmethod
    def from_sqlite(cls, path: Path) -> "Dataset":
        if not path.exists():
            raise FileNotFoundError(f"{path} not found — run `python scripts/ingest.py` first")
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        players = [dict(r) for r in con.execute("SELECT * FROM players")]
        meta = {k: v for k, v in con.execute("SELECT key, value FROM metadata")}
        con.close()
        return cls(players, meta)

    @property
    def valuations_enabled(self) -> bool:
        return self.meta.get("valuations_enabled") == "1" and any(
            p.get("market_value_eur") is not None for p in self.players)

    def role_pool(self, role: str) -> list[dict]:
        return [p for p in self.players if p["role"] == role and p["minutes"] >= PERCENTILE_POOL_MIN_MINUTES]

    def _sorted_values(self, role: str, metric: str) -> list[float]:
        key = (role, metric)
        if key not in self._sorted:
            col = METRICS[metric].column
            self._sorted[key] = sorted(p[col] for p in self.role_pool(role) if p.get(col) is not None)
        return self._sorted[key]

    def percentile(self, role: str, metric: str, value: float | None) -> float | None:
        """Mid-rank percentile (0-100) of value among role-mates with 900+ minutes."""
        if value is None:
            return None
        vals = self._sorted_values(role, metric)
        if not vals:
            return None
        lo, hi = bisect_left(vals, value), bisect_right(vals, value)
        return round(100.0 * (lo + 0.5 * (hi - lo)) / len(vals), 1)

    def public_meta(self) -> dict:
        m = self.meta
        return {
            "league": m.get("league"),
            "season": m.get("season"),
            "matches": int(m.get("matches", 0)),
            "players": len(self.players),
            "stats_source": m.get("stats_source"),
            "valuation_source": m.get("valuation_source") or None,
            "valuations_enabled": self.valuations_enabled,
            "valuation_window": m.get("valuation_window"),
            "age_reference_date": m.get("age_reference_date"),
            "percentile_pool_min_minutes": PERCENTILE_POOL_MIN_MINUTES,
            "players_matched_to_transfermarkt": int(m.get("players_matched_to_transfermarkt", 0) or 0),
            "players_unmatched": int(m.get("players_unmatched", 0) or 0),
            "built_at": m.get("built_at"),
            "synthetic": m.get("synthetic") == "1",
        }


@lru_cache(maxsize=1)
def get_dataset() -> Dataset:
    from .config import settings
    return Dataset.from_sqlite(settings.db_path)
