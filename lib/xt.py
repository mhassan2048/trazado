"""
Expected threat, and the one thing it must not be used for.

The grid is the standard 12x8. It values a position on the pitch by what
possession there tends to be worth, fitted on **open play**.

**Dead balls are excluded from both sides of every fraction, and this is not a
tuning choice.** Measured on one real match: eight corners produced 0.91 of raw
xT gain against 2.00 for a team's entire match across 439 positive passes -- a
corner valued at roughly 27 times an average pass. The cause is structural. The
grid says the corner flag is a low-value cell *because in open play, having the
ball there is not threatening*; a free delivery from a stopped clock breaks that
premise entirely. It would also hand +0.22 to a corner headed straight out.

So `totals` counts open-play passes only, and set-piece value is measured from
the chain **after** the ball is live. That number is small by nature -- second
phase possessions are short -- and it is honest, which the alternative is not.

The consequence worth stating plainly: **xT is the weaker of the two measures
here.** Set-piece threat should be read from npxG, where the model prices a
set-piece shot on its own terms (`from_corner` carries a -0.41 coefficient).
xT is reported for the open-play continuation and nothing more.
"""

from __future__ import annotations

import os

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_GRID_PATH = os.path.join(_HERE, "xT_Grid.csv")

# Qualifiers that mark a pass as a dead-ball restart rather than open play.
RESTARTS = ("CornerTaken", "FreekickTaken", "ThrowIn", "GoalKick")

_grid = None


def grid():
    global _grid
    if _grid is None:
        _grid = pd.read_csv(_GRID_PATH, header=None).to_numpy()
    return _grid


def _cell(x, y):
    if x is None or y is None or pd.isna(x) or pd.isna(y):
        return None
    values = grid()
    rows, cols = values.shape
    ix = min(max(int(x / 100.0 * cols), 0), cols - 1)
    iy = min(max(int(y / 100.0 * rows), 0), rows - 1)
    return float(values[iy, ix])


def gain(x, y, end_x, end_y):
    """Threat added by moving the ball. None when either end is unknown."""
    start, finish = _cell(x, y), _cell(end_x, end_y)
    if start is None or finish is None:
        return None
    return finish - start


def _is_restart(row) -> bool:
    qualifiers = row.get("qualifiers") or {}
    return any(name in qualifiers for name in RESTARTS)


def totals(match) -> dict[str, float]:
    """
    Open-play threat per team: completed passes, restarts excluded.

    Only positive gain counts. A pass backwards is not negative threat, it is a
    different intention, and netting the two off understates sides that build
    patiently.
    """
    out: dict[str, float] = {}
    for row in match.events.to_dict("records"):
        if row.get("type") != "Pass" or row.get("outcome") != "Successful":
            continue
        if _is_restart(row):
            continue
        value = gain(row.get("x"), row.get("y"), row.get("end_x"), row.get("end_y"))
        if value and value > 0:
            out[row["team"]] = out.get(row["team"], 0.0) + value
    return out


def setpiece_chain(pieces) -> dict[str, float]:
    """
    Threat created after a set piece became live, per team.

    The delivery itself contributes nothing here -- see the module note. Only
    links won by the delivering team count; an opponent clearing the ball
    upfield is not threat the attacking side created.
    """
    out: dict[str, float] = {}
    for piece in pieces:
        total = 0.0
        for link in piece.chain:
            if not link.attacking:
                continue
            value = gain(link.x, link.y, link.end_x, link.end_y)
            if value and value > 0:
                total += value
        if total:
            out[piece.team] = out.get(piece.team, 0.0) + total
    return out
