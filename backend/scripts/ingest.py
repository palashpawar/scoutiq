"""Reproducible data ingestion for ScoutIQ.

Builds backend/data/scoutiq.db from two public, openly licensed sources:

1. StatsBomb Open Data (event data) — Premier League 2015/16, all 380 matches.
   https://github.com/statsbomb/open-data  (attribution to StatsBomb required)
2. transfermarkt-datasets by dcaribou (CC0-1.0) — player dates of birth and
   historical Transfermarkt market-value estimates.
   https://github.com/dcaribou/transfermarkt-datasets

Raw downloads are cached gzip-compressed in backend/data/raw/ so re-runs are
fast and offline-friendly. Usage:

    python scripts/ingest.py               # full build
    python scripts/ingest.py --no-valuations   # build without market values
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import re
import sqlite3
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
DB_PATH = DATA / "scoutiq.db"

SB_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
TM_BASE = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data"
COMPETITION_ID, SEASON_ID = 2, 27  # Premier League 2015/16
LEAGUE, SEASON = "Premier League", "2015/16"
AGE_REFERENCE = date(2016, 1, 1)  # mid-season reference date for ages
VALUATION_WINDOW = ("2015-07-01", "2016-06-30")

ROLE_POSITIONS = {
    "central_midfielder": {
        "Center Defensive Midfield", "Left Defensive Midfield", "Right Defensive Midfield",
        "Center Midfield", "Left Center Midfield", "Right Center Midfield",
        "Center Attacking Midfield",
    },
    "winger": {
        "Left Wing", "Right Wing", "Left Midfield", "Right Midfield",
        "Left Attacking Midfield", "Right Attacking Midfield",
    },
    "striker": {
        "Center Forward", "Left Center Forward", "Right Center Forward", "Secondary Striker",
    },
}
POSITION_TO_ROLE = {p: r for r, ps in ROLE_POSITIONS.items() for p in ps}

SET_PIECE_PASSES = {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}
SUCCESS = {"Won", "Success", "Success In Play", "Success Out"}
GOAL = (120.0, 40.0)


# --------------------------------------------------------------------------- io
def fetch(client: httpx.Client, url: str, dest: Path) -> bytes:
    """Download url once, cached gzip-compressed at dest."""
    if dest.exists():
        return gzip.decompress(dest.read_bytes())
    for attempt in range(4):
        try:
            r = client.get(url, timeout=60)
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            if url.endswith(".gz"):
                dest.write_bytes(r.content)
                return gzip.decompress(r.content)
            dest.write_bytes(gzip.compress(r.content))
            return r.content
        except httpx.HTTPError as exc:  # pragma: no cover - network
            if attempt == 3:
                raise
            print(f"  retry {url}: {exc}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------- event math
def goal_dist(x: float, y: float) -> float:
    return math.hypot(GOAL[0] - x, GOAL[1] - y)


def in_box(x: float, y: float) -> bool:
    return x >= 102 and 18 <= y <= 62


def is_progressive(start, end) -> bool:
    """Documented progressive-action rule (StatsBomb pitch units, 120x80 yards).

    The action must start outside the defending 40% of the pitch (x >= 48) and
    either move the ball at least 25% closer to the centre of the opponent's goal
    (and at least 5 yards forward), or enter the penalty area from outside it.
    """
    if not start or not end:
        return False
    sx, sy, ex, ey = start[0], start[1], end[0], end[1]
    if sx < 48:
        return False
    if in_box(ex, ey) and not in_box(sx, sy):
        return True
    return ex - sx >= 5 and goal_dist(ex, ey) <= 0.75 * goal_dist(sx, sy)


def t(ev) -> float:
    return ev["minute"] + ev["second"] / 60.0


def aggregate_match(events: list[dict], stats: dict, positions: dict, teams: dict):
    """Accumulate one match's events into per-player counters."""
    end = {1: 45.0, 2: 90.0}
    for ev in events:
        if ev["period"] in end:
            end[ev["period"]] = max(end[ev["period"]], t(ev))

    on: dict[int, tuple[int, float]] = {}
    off: dict[int, tuple[int, float]] = {}
    started: set[int] = set()
    pass_owner: dict[str, int] = {}

    for ev in events:
        typ = ev["type"]["name"]
        if typ == "Starting XI":
            for slot in ev["tactics"]["lineup"]:
                pid = slot["player"]["id"]
                on[pid] = (1, 0.0)
                started.add(pid)
                teams[pid][ev["team"]["name"]] += 0  # register team
        elif typ == "Substitution":
            off.setdefault(ev["player"]["id"], (ev["period"], t(ev)))
            on[ev["substitution"]["replacement"]["id"]] = (ev["period"], t(ev))
        else:
            card = (ev.get("foul_committed") or ev.get("bad_behaviour") or {}).get("card", {})
            if card.get("name") in ("Red Card", "Second Yellow") and "player" in ev:
                off.setdefault(ev["player"]["id"], (ev["period"], t(ev)))
        if typ == "Pass" and "player" in ev:
            pass_owner[ev["id"]] = ev["player"]["id"]

    def played(pid: int) -> float:
        p_on, t_on = on[pid]
        p_off, t_off = off.get(pid, (2, end[2]))
        if p_off not in end:
            p_off, t_off = 2, end[2]
        if p_on == p_off:
            return max(0.0, t_off - t_on)
        return max(0.0, end[1] - t_on) + max(0.0, t_off - 45.0)

    team_of = {}
    for ev in events:
        if "player" in ev:
            team_of[ev["player"]["id"]] = ev["team"]["name"]
        if ev["type"]["name"] == "Starting XI":
            for slot in ev["tactics"]["lineup"]:
                team_of[slot["player"]["id"]] = ev["team"]["name"]
        if ev["type"]["name"] == "Substitution":
            team_of[ev["substitution"]["replacement"]["id"]] = ev["team"]["name"]

    for pid in on:
        mins = played(pid)
        s = stats[pid]
        s["minutes"] += mins
        s["matches"] += 1
        s["starts"] += pid in started
        teams[pid][team_of.get(pid, "?")] += mins

    for ev in events:
        if "player" not in ev:
            continue
        pid = ev["player"]["id"]
        s = stats[pid]
        typ = ev["type"]["name"]
        if "position" in ev:
            positions[pid][ev["position"]["name"]] += 1
        if typ == "Shot":
            shot = ev["shot"]
            pen = shot.get("type", {}).get("name") == "Penalty"
            goal = shot["outcome"]["name"] == "Goal"
            s["goals"] += goal
            if not pen:
                s["np_goals"] += goal
                s["np_xg"] += shot.get("statsbomb_xg", 0.0)
                s["shots"] += 1
            kp = shot.get("key_pass_id")
            if kp and kp in pass_owner and not pen:
                stats[pass_owner[kp]]["xa"] += shot.get("statsbomb_xg", 0.0)
        elif typ == "Pass":
            p = ev["pass"]
            ptype = p.get("type", {}).get("name")
            if ptype != "Throw-in":
                s["pass_att"] += 1
            completed = "outcome" not in p
            if completed and ptype != "Throw-in":
                s["pass_cmp"] += 1
            if p.get("goal_assist"):
                s["assists"] += 1
            if p.get("goal_assist") or p.get("shot_assist"):
                s["key_passes"] += 1
            if completed and ptype not in SET_PIECE_PASSES and is_progressive(ev.get("location"), p.get("end_location")):
                s["prog_passes"] += 1
        elif typ == "Carry":
            if is_progressive(ev.get("location"), ev["carry"].get("end_location")):
                s["prog_carries"] += 1
        elif typ == "Duel":
            d = ev.get("duel", {})
            if d.get("type", {}).get("name") == "Tackle" and d.get("outcome", {}).get("name") in SUCCESS:
                s["tackles"] += 1
        elif typ == "Interception":
            if ev.get("interception", {}).get("outcome", {}).get("name") in SUCCESS:
                s["interceptions"] += 1
        elif typ == "Ball Recovery":
            if not ev.get("ball_recovery", {}).get("recovery_failure"):
                s["recoveries"] += 1
        elif typ == "Pressure":
            s["pressures"] += 1
        elif typ == "Dribble":
            if ev.get("dribble", {}).get("outcome", {}).get("name") == "Complete":
                s["dribbles"] += 1


# ------------------------------------------------------------ name matching
def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]+", " ", text.lower()).strip()


def norm_club(text: str) -> str:
    words = [w for w in norm(text).split() if w not in {"fc", "afc"}]
    return " ".join(words)


def name_score(sb_names: list[str], tm_name: str) -> float:
    tm = norm(tm_name)
    best = 0.0
    for n in sb_names:
        n = norm(n)
        if not n:
            continue
        sc = max(fuzz.token_set_ratio(n, tm), fuzz.token_sort_ratio(n, tm))
        # Full StatsBomb names often contain extra middle names; reward a
        # matching surname plus matching first initial.
        nt, tt = n.split(), tm.split()
        if nt and tt and nt[-1] == tt[-1] and nt[0][0] == tt[0][0]:
            sc = max(sc, 92)
        best = max(best, sc)
    return best


def load_transfermarkt(client: httpx.Client):
    players_csv = fetch(client, f"{TM_BASE}/players.csv.gz", RAW / "tm" / "players.csv.gz").decode()
    vals_csv = fetch(client, f"{TM_BASE}/player_valuations.csv.gz", RAW / "tm" / "player_valuations.csv.gz").decode()
    players = {r["player_id"]: r for r in csv.DictReader(io.StringIO(players_csv))}
    by_club: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(io.StringIO(vals_csv)):
        if VALUATION_WINDOW[0] <= r["date"] <= VALUATION_WINDOW[1]:
            by_club[norm_club(r["current_club_name"])][r["player_id"]].append(r)
    return players, by_club


# --------------------------------------------------------------------- main
METRICS = [
    "goals", "np_goals", "assists", "np_xg", "xa", "shots", "key_passes",
    "prog_passes", "prog_carries", "tackles", "interceptions", "recoveries",
    "pressures", "dribbles",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-valuations", action="store_true", help="skip Transfermarkt join (ages + values unavailable)")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    with httpx.Client(follow_redirects=True, headers={"User-Agent": "ScoutIQ-ingest/1.0"}) as client:
        matches = json.loads(fetch(client, f"{SB_BASE}/matches/{COMPETITION_ID}/{SEASON_ID}.json",
                                   RAW / "sb" / f"matches_{COMPETITION_ID}_{SEASON_ID}.json.gz"))
        print(f"StatsBomb: {len(matches)} matches for {LEAGUE} {SEASON}")
        ids = [m["match_id"] for m in matches]

        def get(mid):
            ev = fetch(client, f"{SB_BASE}/events/{mid}.json", RAW / "sb" / "events" / f"{mid}.json.gz")
            lu = fetch(client, f"{SB_BASE}/lineups/{mid}.json", RAW / "sb" / "lineups" / f"{mid}.json.gz")
            return json.loads(ev), json.loads(lu)

        stats = defaultdict(lambda: defaultdict(float))
        positions = defaultdict(Counter)
        teams = defaultdict(Counter)
        names: dict[int, dict] = {}
        done = 0
        with ThreadPoolExecutor(args.workers) as pool:
            for events, lineups in pool.map(get, ids):
                aggregate_match(events, stats, positions, teams)
                for team in lineups:
                    for p in team["lineup"]:
                        names[p["player_id"]] = {"name": p["player_name"], "nickname": p.get("player_nickname")}
                done += 1
                if done % 50 == 0:
                    print(f"  aggregated {done}/{len(ids)} matches")

        tm_players, tm_by_club = ({}, {}) if args.no_valuations else load_transfermarkt(client)

    rows = []
    match_counts = Counter()
    for pid, s in stats.items():
        if s["minutes"] <= 0 or pid not in names:
            continue
        role_events = Counter()
        for pos, n in positions[pid].items():
            if pos in POSITION_TO_ROLE:
                role_events[POSITION_TO_ROLE[pos]] += n
        total = sum(positions[pid].values())
        if not role_events:
            continue  # goalkeepers / defenders are out of MVP scope
        role, n_role = role_events.most_common(1)[0]
        if n_role < 0.5 * total:
            continue  # mostly plays outside the three supported roles
        team_list = [tm for tm, _ in teams[pid].most_common() if tm != "?"]
        nm = names[pid]
        nineties = s["minutes"] / 90.0
        row = {
            "id": pid,
            "name": nm["name"],
            "display_name": nm["nickname"] or nm["name"],
            "club": " / ".join(team_list[:2]),
            "league": LEAGUE,
            "season": SEASON,
            "role": role,
            "primary_position": positions[pid].most_common(1)[0][0],
            "role_share": round(n_role / total, 3),
            "minutes": round(s["minutes"]),
            "matches": int(s["matches"]),
            "starts": int(s["starts"]),
            "pass_completion_pct": round(100 * s["pass_cmp"] / s["pass_att"], 1) if s["pass_att"] >= 50 else None,
            "age": None, "date_of_birth": None, "market_value_eur": None,
            "valuation_date": None, "tm_player_id": None, "match_confidence": None,
        }
        for m in METRICS:
            row[f"{m}_p90"] = round(s[m] / nineties, 3)
        for m in ("goals", "assists", "np_xg"):
            row[f"{m}_total"] = round(s[m], 2)

        if tm_by_club:
            cands = []
            for club in team_list:
                for tm_id, vals in tm_by_club.get(norm_club(club), {}).items():
                    tm = tm_players.get(tm_id)
                    if not tm:
                        continue
                    sc = name_score([nm["name"], nm["nickname"] or ""], tm["name"])
                    cands.append((sc, tm_id, vals))
            cands.sort(key=lambda c: -c[0])
            if cands and cands[0][0] >= 85 and (len(cands) == 1 or cands[0][0] - cands[1][0] >= 3 or cands[0][1] == cands[1][1]):
                sc, tm_id, vals = cands[0]
                tm = tm_players[tm_id]
                latest = max(vals, key=lambda v: v["date"])
                dob = (tm["date_of_birth"] or "")[:10]
                if dob:
                    d = datetime.strptime(dob, "%Y-%m-%d").date()
                    row["date_of_birth"] = dob
                    row["age"] = AGE_REFERENCE.year - d.year - ((AGE_REFERENCE.month, AGE_REFERENCE.day) < (d.month, d.day))
                row["market_value_eur"] = int(float(latest["market_value_in_eur"])) if latest["market_value_in_eur"] else None
                row["valuation_date"] = latest["date"]
                row["tm_player_id"] = int(tm_id)
                row["match_confidence"] = round(sc / 100, 2)
                match_counts["matched"] += 1
            else:
                match_counts["unmatched"] += 1
        rows.append(row)

    DATA.mkdir(exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    cols = list(rows[0].keys())
    col_defs = ", ".join(f"{c} {'INTEGER PRIMARY KEY' if c == 'id' else ''}" for c in cols)
    con.execute(f"CREATE TABLE players ({col_defs})")
    con.executemany(f"INSERT INTO players ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                    [tuple(r[c] for c in cols) for r in rows])
    con.execute("CREATE INDEX idx_players_role ON players(role)")
    con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    meta = {
        "league": LEAGUE,
        "season": SEASON,
        "matches": str(len(ids)),
        "stats_source": "StatsBomb Open Data (event data), github.com/statsbomb/open-data",
        "valuation_source": "" if args.no_valuations else
            "Transfermarkt community estimates via transfermarkt-datasets (CC0-1.0), github.com/dcaribou/transfermarkt-datasets",
        "valuations_enabled": "0" if args.no_valuations else "1",
        "valuation_window": f"{VALUATION_WINDOW[0]} to {VALUATION_WINDOW[1]} (latest estimate in window)",
        "age_reference_date": AGE_REFERENCE.isoformat(),
        "players_matched_to_transfermarkt": str(match_counts["matched"]),
        "players_unmatched": str(match_counts["unmatched"]),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    con.executemany("INSERT INTO metadata VALUES (?, ?)", meta.items())
    con.commit()
    con.close()
    by_role = Counter(r["role"] for r in rows)
    print(f"Wrote {len(rows)} players to {DB_PATH} ({dict(by_role)}); Transfermarkt matches: {dict(match_counts)}")


if __name__ == "__main__":
    main()
