"""Deterministic (demo-mode) natural-language parsing.

Used when no Meta API key is configured, and as the fallback whenever the
model call fails or returns invalid output. Rules are intentionally simple and
predictable; anything they cannot interpret is left at a default and reported.
"""
from __future__ import annotations

import re

from .catalog import DEFAULT_PROFILE_FOR_ROLE, METRIC_GROUPS, PROFILES
from .schemas import StructuredQuery

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10}

ROLE_PATTERNS = [
    ("striker", r"\b(strikers?|centre[- ]forwards?|center[- ]forwards?|forwards?|number 9|no\.? ?9|goal ?scorers?|target m[ae]n)\b"),
    ("winger", r"\b(wingers?|wide (?:players?|forwards?|midfielders?)|wing(?:s)?|inside forwards?)\b"),
    ("central_midfielder", r"\b(midfielders?|midfield|playmakers?|cms?|cdms?|dms?|number [68]|no\.? ?[68]|holding|anchor|box[- ]to[- ]box)\b"),
]
UNSUPPORTED_ROLES = r"\b(goal ?keepers?|keepers?|gks?|centre[- ]backs?|center[- ]backs?|defenders?|full[- ]backs?|wing[- ]backs?|left[- ]backs?|right[- ]backs?)\b"
DEFENSIVE_MID = r"\b(defensive midfielders?|holding midfielders?|ball[- ]winn(?:er|ing)|destroyer|anchor|number 6|no\.? ?6|cdm|dm)\b"

GROUP_PATTERNS = {
    "progression": r"progress|progressive|move the ball|carr(?:y|ies)|drive|break(?:s|ing)? lines|forward pass",
    "defending": r"defen[cs]e|defensiv|defend(?!ers?\b)|tackl|intercept|win(?:s|ning)? (?:the )?ball|ball[- ]winn|recover|duel|work rate",
    "pressing": r"\bpress(?:ing|es|ure)?\b|counter[- ]press",
    "creation": r"creat|chance|playmak|key pass|assist|final ball|supply",
    "scoring": r"goal|scor|finish|clinical|xg\b",
    "shooting": r"shoot|shots?\b|volume",
    "dribbling": r"dribbl|take[- ]?ons?|1v1|one[- ]on[- ]one|beat(?:s|ing)? (?:defenders|players|his man|their man)",
    "retention": r"pass(?:ing)? (?:accuracy|completion)|retain|keep(?:s|ing)? (?:the )?ball|tidy|secure in possession|press[- ]resistant",
}
NEGATION = r"(?:less|lower|reduce|de-?prioriti[sz]e|ignore|drop|remove|without|don'?t care about|no need for|not)\s+(?:\w+\s+){0,3}?"
EMPHASIS = r"(?:prioriti[sz]e|priority|focus(?:ing)? on|emphasi[sz]e|more weight|weight more|heavier weight|stronger|more|value|care about)\s+(?:\w+\s+){0,3}?"


class ParseResult:
    def __init__(self, query: StructuredQuery, notes: list[str], warnings: list[str]):
        self.query, self.notes, self.warnings = query, notes, warnings


class UnsupportedRequest(ValueError):
    pass


def _check_supported(text: str) -> None:
    t = text.lower()
    if re.search(UNSUPPORTED_ROLES, t) and not any(re.search(p, t) for _, p in ROLE_PATTERNS):
        raise UnsupportedRequest(
            "ScoutIQ's MVP supports central midfielders, wingers and strikers only. "
            "Goalkeepers and defenders are not covered yet.")


def detect_role(text: str) -> str | None:
    t = text.lower()
    hits = [(m.start(), role) for role, pat in ROLE_PATTERNS for m in [re.search(pat, t)] if m]
    return min(hits)[1] if hits else None


_MONEY = re.compile(
    r"(?P<cur>€|£|\$|eur\b|euros?\b)?\s*(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>m\b|mn\b|mil\b|million\b|k\b|thousand\b|bn\b)?\s*(?P<cur2>€|eur\b|euros?\b)?",
    re.I)


def parse_money(text: str) -> tuple[int | None, bool, str | None]:
    """Return (amount_eur, remove_budget, currency_warning)."""
    t = text.lower()
    if re.search(r"\b(no|remove|ignore|drop|any|unlimited|without)\s+(?:a |the |any )?(budget|price|value cap|cost limit)\b|\bany price\b", t):
        return None, True, None
    found = []
    for m in _MONEY.finditer(t):
        if not (m.group("cur") or m.group("cur2") or m.group("unit")):
            continue
        num = float(m.group("num").replace(",", "."))
        unit = (m.group("unit") or "").lower()
        if unit in ("m", "mn", "mil", "million"):
            num *= 1_000_000
        elif unit in ("k", "thousand"):
            num *= 1_000
        elif unit == "bn":
            num *= 1_000_000_000
        elif num < 1000:
            num *= 1_000_000  # "€15" in a budget context means millions
        context = t[max(0, m.start() - 40): m.start()]
        if unit in ("m",) and not (m.group("cur") or m.group("cur2")) and not re.search(r"budget|value|worth|cost|price|€|under|below|less", context):
            continue  # "3m" without money context
        found.append((m.start(), int(num), m.group("cur"), context))
    if not found:
        return None, False, None
    pos, amount, cur, context = found[-1]
    if re.search(r"\bby\b\s*$", context.strip() + " ") or re.search(r"(increase|raise|add)\w*\s+(?:the\s+)?budget\s+by\s*$", context):
        amount = -amount  # relative change, resolved by caller
    warn = None
    if cur in ("£", "$"):
        warn = f"Amount given in {cur}; ScoutIQ treats it as euros (no currency conversion applied)."
    return amount, False, warn


def parse_age(text: str) -> tuple[int | None, bool]:
    t = text.lower()
    if re.search(r"\b(any age|no age (?:limit|cap)|remove (?:the )?age|ignore (?:the )?age)\b", t):
        return None, True
    pats = [
        (r"\bu-?(\d{2})s?\b", -1),
        (r"\b(?:under|younger than|below|less than)\s+(?:the\s+)?(?:age\s+(?:of\s+)?)?(\d{2})(?!\s*(?:m\b|mn|million|k\b|%|minutes|mins|€))(?:\s*(?:years|yrs|y/o|year[- ]olds?))?", -1),
        (r"\bage[ds]?\s+(?:under|below|less than)\s+(\d{2})\b", -1),
        (r"\b(?:aged\s+)?(\d{2})\s*(?:or|and)\s*(?:younger|under|below)\b", 0),
        (r"\b(?:at most|max(?:imum)?|no older than|up to)\s+(?:age\s+)?(\d{2})\s*(?:years|yrs)?(?:\s*old)?\b(?!\s*(?:m\b|million|k\b|minutes|mins))", 0),
        (r"\bage (?:limit|cap)\s+(?:to|of|at)?\s*(\d{2})\b", 0),
        (r"\bmax(?:imum)? age\s+(?:to|of|at)?\s*(\d{2})\b", 0),
    ]
    for pat, adj in pats:
        m = re.search(pat, t)
        if m:
            age = int(m.group(1)) + adj
            if 16 <= age <= 45:
                return age, False
    return None, False


def parse_minutes(text: str) -> int | None:
    m = re.search(r"(\d{1,2}[,.]?\d{3}|\d{3,4})\s*\+?\s*(?:league\s+)?(?:minutes|mins)\b", text.lower())
    if not m:
        return None
    return min(3420, int(re.sub(r"[,.]", "", m.group(1))))


def parse_limit(text: str) -> int | None:
    t = text.lower()
    m = re.search(r"\btop\s+(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\b", t)
    if not m:
        m = re.search(r"\b(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\s+(?:\w+\s+)?(?:players?|midfielders?|wingers?|strikers?|forwards?|options?|names?|targets?|candidates?)\b", t)
    if not m:
        m = re.search(r"\b(?:show|give|list)(?: me)?\s+(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\b", t)
    if not m:
        return None
    raw = m.group(1)
    n = NUMBER_WORDS.get(raw) or int(raw)
    return max(1, min(10, n))


def detect_groups(text: str) -> tuple[list[str], list[str]]:
    """Return (emphasised groups, de-emphasised groups)."""
    t = text.lower()
    pos, neg = [], []
    for group, pat in GROUP_PATTERNS.items():
        for m in re.finditer(pat, t):
            before = t[max(0, m.start() - 40): m.start()]
            if re.search(NEGATION + r"$", before):
                neg.append(group)
            else:
                pos.append(group)
            break
    # "goal" inside "goal-scoring striker" with no other signal is just the role.
    return list(dict.fromkeys(g for g in pos if g not in neg)), list(dict.fromkeys(neg))


def _profile_for(role: str, text: str) -> str:
    if role == "central_midfielder" and re.search(DEFENSIVE_MID, text.lower()):
        return "defensive_midfielder"
    return DEFAULT_PROFILE_FOR_ROLE[role]


def _boost(weights: dict[str, float], groups: list[str], amount: float) -> dict[str, float]:
    w = dict(weights)
    metrics = [m for g in groups for m in METRIC_GROUPS[g]]
    if not metrics:
        return w
    per = amount / len(metrics)
    for m in metrics:
        w[m] = w.get(m, 0.0) + per
    return w


def parse_request(text: str) -> ParseResult:
    _check_supported(text)
    notes, warnings = [], []
    role = detect_role(text)
    if role is None:
        role = "central_midfielder"
        warnings.append("No supported position recognised — defaulted to central midfielder.")
    profile = PROFILES[_profile_for(role, text)]
    notes.append(f"Started from the '{profile.label}' profile weights.")
    weights = dict(profile.weights)
    emph, deemph = detect_groups(text)
    if emph:
        weights = _boost(weights, emph, 0.6)
        notes.append("Emphasised: " + ", ".join(emph) + ".")
    for g in deemph:
        for m in METRIC_GROUPS[g]:
            weights.pop(m, None)
    if not weights:
        weights = dict(profile.weights)

    age, _ = parse_age(text)
    amount, _, warn = parse_money(text)
    if warn:
        warnings.append(warn)
    minutes = parse_minutes(text)
    limit = parse_limit(text)
    q = StructuredQuery(
        role=role,
        maximum_age=age,
        minimum_minutes=minutes if minutes is not None else 900,
        maximum_market_value_eur=abs(amount) if amount else None,
        metric_weights=weights,
        result_limit=limit or 5,
    )
    return ParseResult(q, notes, warnings)


def refine_request(current: StructuredQuery, text: str) -> ParseResult:
    """Apply a follow-up instruction to an existing structured query."""
    _check_supported(text)
    notes, warnings = [], []
    data = current.model_dump()
    t = text.lower()

    role = detect_role(text)
    if role and role != current.role:
        data["role"] = role
        data["metric_weights"] = dict(PROFILES[_profile_for(role, text)].weights)
        notes.append(f"Switched role to {role.replace('_', ' ')} and reset weights to its default profile.")
    elif role == "central_midfielder" and re.search(DEFENSIVE_MID, t) and "prioriti" not in t:
        data["metric_weights"] = dict(PROFILES["defensive_midfielder"].weights)
        notes.append("Switched to the defensive-midfielder profile.")

    emph, deemph = detect_groups(text)
    if emph:
        w = dict(data["metric_weights"])
        for m in [m for g in emph for m in METRIC_GROUPS[g]]:
            w[m] = w.get(m, 0.0) * 2 + 0.1
        data["metric_weights"] = w
        notes.append("Increased weight on: " + ", ".join(emph) + ".")
    if deemph:
        w = dict(data["metric_weights"])
        for m in [m for g in deemph for m in METRIC_GROUPS[g]]:
            w.pop(m, None)
        if w:
            data["metric_weights"] = w
            notes.append("Removed weight from: " + ", ".join(deemph) + ".")
        else:
            warnings.append("Cannot remove every weighted metric; kept the previous weights.")

    amount, remove_budget, warn = parse_money(text)
    if warn:
        warnings.append(warn)
    if remove_budget:
        data["maximum_market_value_eur"] = None
        notes.append("Removed the budget cap.")
    elif amount:
        if amount < 0:
            base = current.maximum_market_value_eur or 0
            data["maximum_market_value_eur"] = base + abs(amount)
        else:
            data["maximum_market_value_eur"] = amount
        notes.append(f"Budget set to €{data['maximum_market_value_eur'] / 1e6:g}M.")

    age, remove_age = parse_age(text)
    if remove_age:
        data["maximum_age"] = None
        notes.append("Removed the age cap.")
    elif age is not None:
        data["maximum_age"] = age
        notes.append(f"Maximum age set to {age}.")
    elif re.search(r"\b(younger)\b", t) and current.maximum_age:
        data["maximum_age"] = max(16, current.maximum_age - 2)
        notes.append(f"Lowered the maximum age to {data['maximum_age']}.")
    elif re.search(r"\b(older|experienced)\b", t) and current.maximum_age:
        data["maximum_age"] = min(45, current.maximum_age + 2)
        notes.append(f"Raised the maximum age to {data['maximum_age']}.")

    minutes = parse_minutes(text)
    if minutes is not None:
        data["minimum_minutes"] = minutes
        notes.append(f"Minimum minutes set to {minutes}.")
    limit = parse_limit(text)
    if limit:
        data["result_limit"] = limit
        notes.append(f"Showing {limit} players.")

    if not notes:
        warnings.append("Couldn't interpret that refinement in demo mode — filters unchanged. Try e.g. "
                        "'prioritize defensive contribution' or 'increase the budget to €25 million'.")
    return ParseResult(StructuredQuery(**data), notes, warnings)
