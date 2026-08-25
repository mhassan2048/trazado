"""
Coordinate handling.

WhoScored records every event in the *acting team's* attacking frame: x=100 is
always the goal that player is attacking. So a clearance that ends a corner is
logged near x=8, not x=92, because the clearing team attacks the other way.

Any visual that shows a delivery and the defensive action that killed it has to
put both in one frame first. Getting this wrong does not raise — it silently
mirrors half the markers onto the wrong side of the pitch, so it is done here
once rather than in each chart.
"""

from __future__ import annotations

import pandas as pd

# Penalty area in WhoScored's 0-100 units.
BOX_X = 83.0
BOX_Y_MIN, BOX_Y_MAX = 21.0, 79.0
SIX_YARD_X = 94.2
SIX_YARD_Y_MIN, SIX_YARD_Y_MAX = 36.8, 63.2
GOAL_Y_MIN, GOAL_Y_MAX = 44.2, 55.8
EDGE_X = 76.0        # front edge of the "edge of box" band

_MIRROR = (("x", "end_x", "blocked_x"), ("y", "end_y", "blocked_y"))


def to_attacking_frame(events: pd.DataFrame, team: str) -> pd.DataFrame:
    """
    Restate every event in `team`'s attacking frame.

    Rows belonging to `team` are untouched; every other row is mirrored through
    the centre of the pitch. After this, x=100 is the goal `team` attacks for
    all rows, and a defensive clearance sits where it physically happened.

    Adds `mirrored` so a chart can still tell whose action it was.
    """
    out = events.copy()
    flip = out["team"].ne(team) & out["team"].ne("")
    for column in _MIRROR[0] + _MIRROR[1]:
        if column in out.columns:
            out.loc[flip, column] = 100.0 - out.loc[flip, column]
    out["mirrored"] = flip
    return out


def in_box(x, y) -> bool:
    """True when a point lies inside the penalty area being attacked."""
    if pd.isna(x) or pd.isna(y):
        return False
    return x >= BOX_X and BOX_Y_MIN <= y <= BOX_Y_MAX


def in_six_yard(x, y) -> bool:
    if pd.isna(x) or pd.isna(y):
        return False
    return x >= SIX_YARD_X and SIX_YARD_Y_MIN <= y <= SIX_YARD_Y_MAX


# Lateral channels, in the standard tactical corridors: a central corridor
# roughly y 37-63 with a half space either side of it.
#
# Opta y runs 0 to 100 across the pitch. For a team attacking towards x=100,
# y=100 is that team's LEFT -- verified by rendering the landmarks rather than
# reasoned about, because getting it backwards silently mirrors every zone
# label in the app.
HALF_SPACE_RIGHT = 36.8      # y below this is the right half space
HALF_SPACE_LEFT = 63.2       # y above this is the left half space


def delivery_zone(end_x, end_y, taken_from_y=None) -> str:
    """
    Name the area a delivery finished in, in absolute pitch terms.

    Zones are the real sides of the pitch, not mirrored onto the delivery
    side: the left half space is the left half space whichever corner the ball
    came from. `taken_from_y` is accepted and ignored so existing callers keep
    working.

    Returns one of: short, six-yard box, central, left half space,
    right half space, edge of box, wide of box.
    """
    if pd.isna(end_x) or pd.isna(end_y):
        return "unknown"

    x, y = float(end_x), float(end_y)
    if x < EDGE_X:
        return "short"
    if not (BOX_Y_MIN <= y <= BOX_Y_MAX):
        return "wide of box"
    if x < BOX_X:
        return "edge of box"
    if y > HALF_SPACE_LEFT:
        return "left half space"
    if y < HALF_SPACE_RIGHT:
        return "right half space"
    if x >= SIX_YARD_X:
        return "six-yard box"
    return "central"


def distance(x1, y1, x2, y2) -> float | None:
    """
    Straight-line distance in metres between two 0-100 points.

    WhoScored's grid is not square: 100 units of x span a 105m pitch and 100
    units of y span 68m, so scale each axis before measuring.
    """
    if any(pd.isna(v) for v in (x1, y1, x2, y2)):
        return None
    dx = (float(x2) - float(x1)) * 1.05
    dy = (float(y2) - float(y1)) * 0.68
    return (dx * dx + dy * dy) ** 0.5
