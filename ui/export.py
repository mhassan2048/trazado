"""
The export card.

A frame, not a chart. Any visual in `charts` can be dropped into it, because
every visual worth looking at is worth sharing -- a timeline that can only be
seen inside the app is a timeline nobody sends to anyone.

Section 7 sets the anatomy: brand block, match identity, title, one-fact
caption, the visual, a legend in the notation vocabulary, and a footer whose
"single match" qualifier is load bearing given there is no aggregation
anywhere in this app.
"""

from __future__ import annotations

import io

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

import io as _io

from lib import badges, readout

from . import charts
from .theme import THEMES

WIDTH, HEIGHT = 10.80, 13.50     # 1080 x 1350 at dpi 100
FOOTER_LEFT = "Data from Opta"
FOOTER_RIGHT = "@mhassanfootball"
TITLE_ALPHA = 0.70

# Each visual declares whether it is about one team or the whole match, where
# its plot sits on the card, and how to caption it.
VISUALS: dict[str, dict] = {
    "deliveries": {
        "label": "Delivery Map",
        "team": True,
        "rect": [0.075, 0.160, 0.850, 0.570],
        "heading": "Set-Pieces",
    },
    "chains": {
        "label": "Second Phase",
        "team": True,
        "rect": [0.075, 0.150, 0.850, 0.545],
        "legend_y": 0.062,
        "heading": "Second Phase",
    },
    "aerials": {
        "label": "Aerial Duels",
        "team": True,
        "rect": [0.075, 0.318, 0.850, 0.412],
        "extra": [0.100, 0.150, 0.800, 0.150],
        "legend_y": 0.300,
        "heading": "Aerial Duels",
    },
    "goalkicks": {
        "label": "Goal Kicks",
        "team": True,
        "rect": [0.060, 0.278, 0.880, 0.432],
        "legend_y": 0.200,
        "heading": "Goal Kicks",
    },
    "timeline": {
        "label": "Timeline",
        "team": False,
        "rect": [0.085, 0.220, 0.845, 0.505],
        "heading": "Dead Balls Against the Scoreline",
    },
}


def _mark(figure, x, y, size, palette):
    """
    The Trazado mark, drawn from assets/logo.svg coordinates.

    Its y axis runs downward as SVG does; flipping it turns the run curve
    upside down.
    """
    axis = figure.add_axes([x, y, size, size * (WIDTH / HEIGHT)])
    axis.set_xlim(-4, 124); axis.set_ylim(124, -4)
    axis.set_aspect("equal"); axis.axis("off"); axis.set_facecolor("none")
    axis.add_patch(Rectangle((17, 89), 9, 9, facecolor=palette["ink"], lw=0))
    p0, p1, p2 = (27, 88), (40, 32), (88, 12)
    curve = [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
              (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
             for t in [i / 60 for i in range(61)]]
    axis.plot([c[0] for c in curve], [c[1] for c in curve],
              color=palette["ink"], lw=3.4, ls=(0, (3.0, 2.6)),
              solid_capstyle="round", dash_capstyle="round")
    axis.plot([77, 98, 82], [2, 12, 30], color=palette["accent"], lw=3.4,
              solid_capstyle="round", solid_joinstyle="round")
    axis.plot([40, 68], [78, 65], color=palette["hot"], lw=4.4,
              solid_capstyle="round")
    return axis


CREST_ALPHA = 0.75


def _crest(figure, team_id, x, y, size):
    """
    A club crest, placed by its centre.

    Team names are long, inconsistently abbreviated by the feed, and push the
    header out of alignment; the crest says the same thing in a fixed box.
    Held at 75% so it sits behind the type rather than competing with it.
    Returns False when the id has no badge, so the caller can fall back.
    """
    data = badges.fetch(team_id)
    if not data:
        return False
    try:
        from PIL import Image
        image = Image.open(_io.BytesIO(data)).convert("RGBA")
    except Exception:
        return False
    axis = figure.add_axes([x - size / 2, y - size * (WIDTH / HEIGHT) / 2,
                            size, size * (WIDTH / HEIGHT)])
    axis.imshow(image, alpha=CREST_ALPHA, interpolation="lanczos")
    axis.axis("off")
    axis.set_facecolor("none")
    return True


def _team_ids(match):
    players = match.players
    out = {}
    if players is None or players.empty:
        return out
    for side, key in (("home", "home_team"), ("away", "away_team")):
        rows = players[players["side"] == side]
        if not rows.empty:
            out[match.meta[key]] = int(rows.iloc[0]["team_id"] or 0)
    return out


def _rule(figure, y, palette, alpha=1.0):
    figure.add_artist(Line2D([0.075, 0.925], [y, y], transform=figure.transFigure,
                             color=palette["line"], lw=1.1, alpha=alpha))


def _legend(figure, handles, palette, y):
    """Notation first, origin markers on a second row beneath it."""
    first, second = handles[:5], handles[5:]
    legend = figure.legend(handles=first, loc="lower center",
                           bbox_to_anchor=(0.5, y), ncol=3, frameon=False,
                           fontsize=12.5, handlelength=2.4, columnspacing=2.4,
                           handletextpad=0.9)
    for text in legend.get_texts():
        text.set_color(palette["muted"])
    if second:
        marks = figure.legend(handles=second, loc="lower center",
                              bbox_to_anchor=(0.5, y - 0.028), ncol=3,
                              frameon=False, fontsize=12, handlelength=1.2,
                              columnspacing=3.0, handletextpad=0.8)
        for text in marks.get_texts():
            text.set_color(palette["faint"])
        figure.add_artist(legend)


def card(match, pieces, *, visual: str = "deliveries", team: str | None = None,
         theme: str = "newspaper") -> bytes:
    """Render one card and return PNG bytes."""
    spec = VISUALS[visual]
    palette = THEMES.get(theme, THEMES["newspaper"])
    meta = match.meta
    home, away = meta["home_team"], meta["away_team"]
    scoped = [p for p in pieces if p.team == team] if spec["team"] else pieces

    figure = plt.figure(figsize=(WIDTH, HEIGHT), facecolor=palette["bg"])

    # header
    _mark(figure, 0.073, 0.932, 0.054, palette)
    figure.text(0.142, 0.951, "trazado", color=palette["ink"], fontsize=25,
                fontweight="bold", va="center", ha="left")
    ids = _team_ids(match)
    badges.warm(ids.values())
    score = str(meta.get("score", "") or "")
    # Wider gaps than the type strictly needs: a monospaced face sets the same
    # score noticeably wider than a proportional one, and the header must not
    # have to be re-tuned every time the typeface changes.
    figure.text(0.874, 0.963, score, color=palette["ink"], fontsize=16,
                va="center", ha="center")
    drew = (_crest(figure, ids.get(home, 0), 0.802, 0.963, 0.038)
            and _crest(figure, ids.get(away, 0), 0.946, 0.963, 0.038))
    if not drew:
        # No badge for one of the ids: names rather than a gap.
        figure.text(0.925, 0.963, f"{home}  {score}  {away}",
                    color=palette["ink"], fontsize=14, va="center", ha="right")
    identity = [x for x in (meta.get("competition"), meta.get("venue"),
                            str(meta.get("start_date") or "")[:10]) if x]
    figure.text(0.925, 0.936, " · ".join(identity), color=palette["muted"],
                fontsize=11.5, va="center", ha="right")
    _rule(figure, 0.926, palette)

    # title and the one fact worth leading with
    # The title block sits above the caption with real clearance. The crest is
    # centred on the heading, and the caption starts below the crest's lower
    # edge -- not level with the heading, which put the badge through the text.
    heading = spec["heading"]
    if spec["team"] and _crest(figure, ids.get(team, 0), 0.106, 0.888, 0.060):
        figure.text(0.150, 0.888, heading, color=palette["ink"], fontsize=32,
                    fontweight="bold", va="center", ha="left", alpha=TITLE_ALPHA)
    else:
        figure.text(0.075, 0.888, (f"{team} — " if spec["team"] else "") + heading,
                    color=palette["ink"], fontsize=32, fontweight="bold",
                    va="center", ha="left", alpha=TITLE_ALPHA)
    if visual == "aerials":
        caption = charts.aerial_caption(scoped)
    elif visual == "goalkicks":
        caption = charts.goal_kick_caption(scoped, team)
    elif visual == "chains":
        caption = charts.chain_caption(scoped)
    elif visual == "timeline":
        caption = charts.timeline_caption(scoped, home, away)
    else:
        caption = readout.headline(pieces, team)
    figure.text(0.075, 0.851, caption, color=palette["muted"], fontsize=14,
                va="top", ha="left", wrap=True)

    # the numbers
    cells = readout.strip(pieces, team)[:6] if spec["team"] else _match_strip(pieces, home, away)
    if cells:
        left, right = 0.075, 0.925
        step = (right - left) / len(cells)
        for index, (value, label) in enumerate(cells):
            x = left + step * index
            figure.text(x, 0.786, value, color=palette["ink"], fontsize=25,
                        fontweight="bold", va="center", ha="left")
            figure.text(x, 0.763, label, color=palette["faint"], fontsize=9.5,
                        va="center", ha="left")
        _rule(figure, 0.744, palette, alpha=0.6)

    # the visual, drawn by the same code the screen uses, at card scale
    rect = spec["rect"]
    if visual == "deliveries":
        _, handles = charts.draw_deliveries(figure, rect, scoped, palette, scale=1.55)
    elif visual == "aerials":
        _, handles = charts.draw_aerials(figure, rect, scoped, palette, scale=1.5)
        charts.draw_aerial_breakdown(figure, spec["extra"], scoped, palette,
                                     scale=1.35)
    elif visual == "goalkicks":
        _, handles = charts.draw_goal_kicks(figure, rect, scoped, palette,
                                            home, scale=1.5)
    elif visual == "chains":
        _, handles = charts.draw_chains(figure, rect, scoped, palette,
                                        scale=1.25, columns=2)
    else:
        from lib.setpieces import match_goals
        _, handles = charts.draw_timeline(
            figure, rect, scoped, palette, home, away,
            goals=match_goals(match),
            max_minute=int(meta.get("max_minute") or 95), scale=1.5)

    _legend(figure, handles, palette,
            y=spec.get("legend_y", 0.098 if len(handles) > 5 else 0.086))

    # footer
    _rule(figure, 0.050, palette)
    figure.text(0.075, 0.031, FOOTER_LEFT, color=palette["muted"], fontsize=12,
                va="center", ha="left")
    figure.text(0.925, 0.031, FOOTER_RIGHT, color=palette["muted"], fontsize=12,
                va="center", ha="right")

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=100, facecolor=palette["bg"])
    plt.close(figure)
    return buffer.getvalue()


def _match_strip(pieces, home, away):
    """Both sides at once, for a card that is about the match not a team."""
    h = readout.summary(pieces, home)
    a = readout.summary(pieces, away)
    return [
        (str(len(pieces)), "Dead Balls"),
        (f"{h['total']}-{a['total']}", "By Team"),
        (f"{h['shots']}-{a['shots']}", "Shots"),
        (f"{h['second'] + a['second']}/{h['shots'] + a['shots']}", "Second Phase"),
        (f"{h['goals']}-{a['goals']}", "Set-Piece Goals"),
    ]
