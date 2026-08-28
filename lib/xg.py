"""
Shot quality.

Section 1 used to ban xG outright. That rule was written for an app whose whole
subject was deliveries and first contacts, where danger reads from location and
outcome alone. It no longer holds once the question is "how much of this team's
threat came from dead balls", which is a question about quantity.

What is served here is a specific model, not "xG", and it is labelled that way
everywhere it appears:

  - fitted on 291 La Liga matches, 7,215 non-penalty shots, 681 goals
  - out-of-fold log loss 0.2718 against a 0.3126 base rate, AUC 0.755
  - aggregate calibration 680.6 predicted against 681 scored

**It is trained on one league.** A Bundesliga or Champions League card is out of
distribution until that is checked, and the caller is told so rather than the
number quietly appearing anyway.

The scaler is folded into the coefficients so nothing here imports sklearn and
no training data is needed at run time. The folded form was verified identical
to the fitted pipeline to 8e-16.

**Penalties are never modelled.** They convert near 0.80 regardless of anything
a model could see, and one of them is worth more than most teams' entire
set-piece output -- so folding a penalty into "set-piece xG" would produce a
headline that reads "set pieces were 60% of their threat" when the honest
translation is "they won a penalty". They are reported separately, counted, and
excluded from both sides of every fraction. This is what npxG means here.
"""

from __future__ import annotations

import json
import math
import os

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC_PATH = os.path.join(_HERE, "xg_model.json")

PITCH_X, PITCH_Y = 105.0, 68.0
GOAL_WIDTH = 7.32
POST = GOAL_WIDTH / 2.0
GOAL_Y = PITCH_Y / 2.0

# Raw WhoScored naming. Blocked attempts live inside SavedShot carrying a
# `Blocked` qualifier rather than forming their own type.
SHOT_TYPES = frozenset({"Goal", "MissedShots", "SavedShot", "ShotOnPost"})

# The assist is the pass immediately before the shot; the phase reaches further
# back and must survive intervening events, because a duel is recorded as a
# mirrored pair -- one event per side -- so a headed corner reads as
# corner(A) -> aerial(A) -> aerial(B) -> shot(A).
ASSIST_EVENTS, ASSIST_SECONDS = 3, 5.0
PHASE_EVENTS, PHASE_SECONDS = 10, 15.0

VALIDATED_LEAGUES = frozenset({"laliga"})

_spec: dict | None = None


def spec() -> dict:
    global _spec
    if _spec is None:
        with open(_SPEC_PATH) as handle:
            _spec = json.load(handle)
    return _spec


def penalty_value() -> float:
    return float(spec()["penalty"])


def goal_distance(x: float, y: float) -> float:
    """Metres to the centre of the goal.

    Opta normalises 0-100 on *both* axes, so a unit of x is 1.05m and a unit of
    y is 0.68m. Distance computed in raw Opta units silently squashes the pitch.
    """
    xm, ym = x / 100.0 * PITCH_X, y / 100.0 * PITCH_Y
    return math.hypot(PITCH_X - xm, ym - GOAL_Y)


def goal_angle(x: float, y: float) -> float:
    """The angle the goalmouth subtends, in radians. Even in lateral offset."""
    xm, ym = x / 100.0 * PITCH_X, y / 100.0 * PITCH_Y
    dx, dy = PITCH_X - xm, ym - GOAL_Y
    theta = math.atan2(GOAL_WIDTH * dx, dx * dx + dy * dy - POST * POST)
    return theta + math.pi if theta < 0 else theta


def _has(row, name: str) -> bool:
    return name in (row.get("qualifiers") or {})


def _clock(row) -> float:
    return (row.get("minute") or 0) * 60.0 + (row.get("second") or 0)


def _assist(rows, index):
    shot = rows[index]
    for back in range(1, ASSIST_EVENTS + 1):
        j = index - back
        if j < 0:
            return None
        prior = rows[j]
        if _clock(shot) - _clock(prior) > ASSIST_SECONDS:
            return None
        if prior["team"] != shot["team"]:
            continue
        if prior["type"] == "Pass":
            return prior
    return None


def _phase(rows, index):
    shot = rows[index]
    for back in range(1, PHASE_EVENTS + 1):
        j = index - back
        if j < 0:
            break
        prior = rows[j]
        if _clock(shot) - _clock(prior) > PHASE_SECONDS:
            break
        if prior["team"] != shot["team"] or prior["type"] != "Pass":
            continue
        if _has(prior, "CornerTaken"):
            return "corner"
        if _has(prior, "FreekickTaken"):
            return "freekick"
    return None


def _probability(features: dict) -> float:
    model = spec()
    z = model["intercept"] + sum(model["weights"][k] * v for k, v in features.items())
    return 1.0 / (1.0 + math.exp(-z))


def shots(match) -> pd.DataFrame:
    """
    Every shot in the match with its npxG.

    `penalty` rows carry the constant and are flagged rather than dropped, so a
    caller can count them and report them separately -- but they must never be
    summed into an npxG total.
    """
    rows = match.events.to_dict("records")
    out = []
    for i, row in enumerate(rows):
        if row["type"] not in SHOT_TYPES or _has(row, "OwnGoal"):
            continue
        x, y = row.get("x"), row.get("y")
        if x is None or y is None or pd.isna(x) or pd.isna(y):
            continue
        penalty = _has(row, "Penalty")
        made, phase = _assist(rows, i), _phase(rows, i)
        distance, angle = goal_distance(x, y), goal_angle(x, y)
        value = penalty_value() if penalty else _probability({
            "log_distance": math.log1p(distance),
            "inv_distance": 1.0 / (distance + 1.0),
            "angle": angle,
            "header": float(_has(row, "Head")),
            "volley": float(_has(row, "Volley")),
            "from_corner": float(phase == "corner"),
            "from_freekick": float(phase == "freekick"),
            "assist_cross": float(bool(made and _has(made, "Cross"))),
            "assist_through": float(bool(made and _has(made, "ThroughBall"))),
            "fast_break": float(_has(row, "FastBreak")),
            "assisted": float(made is not None),
        })
        out.append({
            "seq": row.get("seq"), "minute": row.get("minute"),
            "team": row.get("team"), "player": row.get("player"),
            "type": row["type"], "x": x, "y": y,
            "distance": distance, "npxg": 0.0 if penalty else value,
            "penalty_xg": value if penalty else 0.0,
            "penalty": int(penalty), "goal": int(row["type"] == "Goal"),
        })
    return pd.DataFrame(out)


def validated_for(competition_key: str) -> bool:
    """Whether the model has been checked against this competition."""
    return (competition_key or "").lower() in VALIDATED_LEAGUES
