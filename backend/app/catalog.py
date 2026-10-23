"""Static catalog: supported roles, metrics and scouting profiles.

Everything the language model is allowed to reference lives here. Model output
naming anything outside these tables is rejected by schema validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["central_midfielder", "winger", "striker"]
ROLES: dict[str, str] = {
    "central_midfielder": "Central midfielder",
    "winger": "Winger",
    "striker": "Striker",
}


@dataclass(frozen=True)
class Metric:
    key: str
    column: str
    label: str
    short: str
    group: str
    description: str
    unit: str = "/90"


METRICS: dict[str, Metric] = {m.key: m for m in [
    Metric("np_goals", "np_goals_p90", "Non-penalty goals per 90", "NP goals", "scoring",
           "Goals excluding penalties, per 90 minutes."),
    Metric("np_xg", "np_xg_p90", "Non-penalty xG per 90", "NP xG", "scoring",
           "StatsBomb expected goals from non-penalty shots, per 90."),
    Metric("shots", "shots_p90", "Shots per 90", "Shots", "scoring",
           "Non-penalty shots attempted, per 90."),
    Metric("assists", "assists_p90", "Assists per 90", "Assists", "creation",
           "Passes directly leading to a goal, per 90."),
    Metric("xa", "xa_p90", "Expected assists (xA) per 90", "xA", "creation",
           "Sum of xG from non-penalty shots the player's pass set up, per 90."),
    Metric("key_passes", "key_passes_p90", "Key passes per 90", "Key passes", "creation",
           "Passes that directly led to a shot, per 90."),
    Metric("progressive_passes", "prog_passes_p90", "Progressive passes per 90", "Prog. passes", "progression",
           "Completed open-play passes from outside the defending 40% that move the ball at least 25% "
           "closer to goal (and 5+ yards forward) or into the penalty area, per 90."),
    Metric("progressive_carries", "prog_carries_p90", "Progressive carries per 90", "Prog. carries", "progression",
           "Carries meeting the same progressive rule as passes, per 90."),
    Metric("dribbles", "dribbles_p90", "Successful dribbles per 90", "Dribbles", "progression",
           "Completed take-ons past an opponent, per 90."),
    Metric("pass_completion", "pass_completion_pct", "Pass completion %", "Pass %", "possession",
           "Completed / attempted passes (excluding throw-ins). Missing below 50 attempts.", "%"),
    Metric("tackles", "tackles_p90", "Tackles won per 90", "Tackles won", "defending",
           "Tackle duels won, per 90."),
    Metric("interceptions", "interceptions_p90", "Interceptions per 90", "Interceptions", "defending",
           "Successful interceptions, per 90."),
    Metric("ball_recoveries", "recoveries_p90", "Ball recoveries per 90", "Recoveries", "defending",
           "Loose-ball recoveries, per 90."),
    Metric("pressures", "pressures_p90", "Pressures per 90", "Pressures", "defending",
           "StatsBomb pressure events on an opponent in possession, per 90."),
]}
MetricKey = Literal[
    "np_goals", "np_xg", "shots", "assists", "xa", "key_passes", "progressive_passes",
    "progressive_carries", "dribbles", "pass_completion", "tackles", "interceptions",
    "ball_recoveries", "pressures",
]

# Metrics shown on every card for a role (the scoring weights decide what counts).
ROLE_DISPLAY_METRICS: dict[str, list[str]] = {
    "central_midfielder": ["progressive_passes", "progressive_carries", "key_passes", "pass_completion",
                           "tackles", "interceptions", "ball_recoveries", "np_goals", "assists"],
    "winger": ["xa", "key_passes", "dribbles", "progressive_carries", "assists", "np_goals", "np_xg", "pressures"],
    "striker": ["np_goals", "np_xg", "shots", "xa", "key_passes", "dribbles", "pressures", "assists"],
}


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    role: str
    weights: dict[str, float]
    blurb: str


PROFILES: dict[str, Profile] = {p.key: p for p in [
    Profile("ball_progressing_midfielder", "Ball-progressing midfielder", "central_midfielder",
            {"progressive_passes": 0.30, "progressive_carries": 0.25, "key_passes": 0.10,
             "pass_completion": 0.10, "tackles": 0.10, "interceptions": 0.10, "xa": 0.05},
            "Moves the ball up the pitch by pass and carry while holding possession."),
    Profile("defensive_midfielder", "Defensive midfielder", "central_midfielder",
            {"tackles": 0.25, "interceptions": 0.25, "ball_recoveries": 0.20, "pressures": 0.15,
             "pass_completion": 0.10, "progressive_passes": 0.05},
            "Wins the ball back and keeps it simple."),
    Profile("creative_winger", "Creative winger", "winger",
            {"xa": 0.25, "key_passes": 0.20, "dribbles": 0.20, "progressive_carries": 0.20,
             "assists": 0.10, "np_xg": 0.05},
            "Creates chances and beats defenders from wide areas."),
    Profile("goal_scoring_striker", "Goal-scoring striker", "striker",
            {"np_goals": 0.30, "np_xg": 0.30, "shots": 0.15, "xa": 0.10, "key_passes": 0.10, "dribbles": 0.05},
            "Gets into scoring positions and finishes."),
]}
DEFAULT_PROFILE_FOR_ROLE = {
    "central_midfielder": "ball_progressing_midfielder",
    "winger": "creative_winger",
    "striker": "goal_scoring_striker",
}

# Keyword groups used by the deterministic parser to emphasise metrics.
METRIC_GROUPS: dict[str, list[str]] = {
    "progression": ["progressive_passes", "progressive_carries"],
    "defending": ["tackles", "interceptions", "ball_recoveries"],
    "pressing": ["pressures"],
    "creation": ["key_passes", "xa", "assists"],
    "scoring": ["np_goals", "np_xg"],
    "shooting": ["shots"],
    "dribbling": ["dribbles"],
    "retention": ["pass_completion"],
}

EXAMPLE_QUERIES = [
    "Find three midfielders under age 25 who progress the ball well, contribute defensively, "
    "and have an estimated market value below €15 million.",
    "Show me creative wingers aged 23 or younger who create chances and beat defenders, valued under €10 million.",
    "I need a goal-scoring striker under 27 with at least 1500 minutes and a value below €20 million.",
]
