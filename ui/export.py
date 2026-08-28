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
    "comparison": {
        "label": "Comparison",
        "team": False,
        # Taller than the others: this card carries no strip and no caption,
        # so the band starts just under the title instead of below a rule.
        "rect": [0.075, 0.150, 0.850, 0.700],
        "heading": "Team Comparison",
    },
    "threat": {
        "label": "Set-Piece Threat",
        "team": False,
        "rect": [0.075, 0.150, 0.850, 0.616],
        "legend_y": 0.055,
        "heading": "Set-Piece Share of Threat",
    },
    "timeline": {
        "label": "Timeline",
        "team": False,
        "rect": [0.085, 0.220, 0.845, 0.561],
        "heading": "Dead Balls Against the Scoreline",
    },
    "deliveries": {
        "label": "Delivery Map",
        "team": True,
        "rect": [0.075, 0.160, 0.850, 0.626],
        "heading": "Set-Pieces",
    },
    "chains": {
        "label": "Second Phase",
        "team": True,
        "rect": [0.075, 0.150, 0.850, 0.601],
        "legend_y": 0.062,
        "heading": "Second Phase",
    },
    "aerials": {
        "label": "Aerial Duels",
        "team": True,
        "rect": [0.075, 0.318, 0.850, 0.468],
        "extra": [0.100, 0.150, 0.800, 0.150],
        "legend_y": 0.300,
        "heading": "Aerial Duels",
    },
    "goalkicks": {
        "label": "Goal Kicks",
        "team": True,
        "rect": [0.060, 0.278, 0.880, 0.488],
        "legend_y": 0.200,
        "heading": "Goal Kicks",
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


# One left margin for the whole card, and one vertical rhythm. These were
# scattered as literals, which is how the title drifted off the strip's edge
# when the caption was removed and nothing recomputed around it.
MARGIN_L, MARGIN_R = 0.075, 0.925
TITLE_Y = 0.882
STRIP_VALUE_Y, STRIP_LABEL_Y, STRIP_RULE_Y = 0.836, 0.812, 0.793

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
    figure.add_artist(Line2D([MARGIN_L, MARGIN_R], [y, y], transform=figure.transFigure,
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

    # Header, on the same two margins as everything below it. The away crest is
    # placed by its centre, so it sits half its width inside MARGIN_R -- it used
    # to run to 0.946 while the line of text beneath it stopped at 0.925, which
    # left the header's right edge ragged against the rest of the card.
    CREST = 0.038
    _mark(figure, MARGIN_L, 0.932, 0.054, palette)
    figure.text(MARGIN_L + 0.067, 0.951, "trazado", color=palette["ink"],
                fontsize=25, fontweight="bold", va="center", ha="left")
    ids = _team_ids(match)
    badges.warm(ids.values())
    score = str(meta.get("score", "") or "")
    away_x = MARGIN_R - CREST / 2.0
    # Wider gaps than the type strictly needs: a monospaced face sets the same
    # score noticeably wider than a proportional one, and the header must not
    # have to be re-tuned every time the typeface changes.
    home_x = away_x - 0.144
    figure.text((home_x + away_x) / 2.0, 0.963, score, color=palette["ink"],
                fontsize=16, va="center", ha="center")
    drew = (_crest(figure, ids.get(home, 0), home_x, 0.963, CREST)
            and _crest(figure, ids.get(away, 0), away_x, 0.963, CREST))
    if not drew:
        # No badge for one of the ids: names rather than a gap.
        figure.text(MARGIN_R, 0.963, f"{home}  {score}  {away}",
                    color=palette["ink"], fontsize=14, va="center", ha="right")
    identity = [x for x in (meta.get("competition"), meta.get("venue"),
                            str(meta.get("start_date") or "")[:10]) if x]
    figure.text(MARGIN_R, 0.936, " · ".join(identity), color=palette["muted"],
                fontsize=11.5, va="center", ha="right")
    _rule(figure, 0.926, palette)

    # Title, always on the same left margin as everything under it.
    #
    # The crest used to sit to the LEFT of the heading, which pushed the text in
    # to x=0.150 on team cards while the strip below stayed at 0.075 -- so the
    # title and the numbers it introduced did not share an edge, and only on
    # some cards. The crest now sits at the right end of the title line, which
    # mirrors the header above it (mark left, crests right) and leaves one
    # margin running the height of the card.
    heading = spec["heading"]
    figure.text(MARGIN_L, TITLE_Y, heading, color=palette["ink"], fontsize=32,
                fontweight="bold", va="center", ha="left", alpha=TITLE_ALPHA)
    if spec["team"]:
        if not _crest(figure, ids.get(team, 0), MARGIN_R - 0.030, TITLE_Y, 0.060):
            # No badge for this side, so the name carries the identification.
            figure.text(MARGIN_R, TITLE_Y, team, color=palette["muted"],
                        fontsize=15, va="center", ha="right")
    # No captions. A sentence under the title restated what the chart already
    # showed, and on a card whose whole argument is the visual it read as
    # hedging. The title names the thing; the graphic makes the case.

    # the numbers
    if visual == "comparison":
        cells = []
    elif spec["team"]:
        cells = readout.strip(pieces, team)[:6]
    elif visual == "threat":
        cells = _threat_strip(match, pieces, home, away)
    else:
        cells = _match_strip(pieces, home, away)
    if cells:
        step = (MARGIN_R - MARGIN_L) / len(cells)
        for index, (value, label) in enumerate(cells):
            x = MARGIN_L + step * index
            figure.text(x, STRIP_VALUE_Y, value, color=palette["ink"], fontsize=25,
                        fontweight="bold", va="center", ha="left")
            figure.text(x, STRIP_LABEL_Y, label, color=palette["faint"], fontsize=9.5,
                        va="center", ha="left")
        _rule(figure, STRIP_RULE_Y, palette, alpha=0.6)

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
    elif visual == "threat":
        _, handles = charts.draw_threat(figure, rect, match, scoped, palette,
                                        home, away, scale=1.35)
    elif visual == "comparison":
        # Rows are as tall as the frame divided by however many there are, so
        # a three-row match in a ten-row frame comes out as three fat slabs.
        # Hold the row height instead and let the block shrink upward.
        count = len(charts.comparison_rows(scoped, home, away, match=match))
        # The crest band is part of the axis, so it has to be part of the
        # height too -- otherwise the rows compress to make room for it and
        # leave the slack sitting under the table instead.
        if charts._crest_pair(ids, home, away):
            count += charts.CREST_ROWS
        x, y, w, h = rect
        used = min(h, 0.056 * count)
        # Centred in the band, not anchored to its top: anchoring left a dead
        # strip above the legend on a match with few rows.
        _, handles = charts.draw_comparison(
            figure, [x, y + (h - used) / 2, w, used], scoped, palette,
            home, away, scale=1.45, ids=ids, match=match)
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
    figure.text(MARGIN_L, 0.031, FOOTER_LEFT, color=palette["muted"], fontsize=12,
                va="center", ha="left")
    figure.text(MARGIN_R, 0.031, FOOTER_RIGHT, color=palette["muted"], fontsize=12,
                va="center", ha="right")

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=100, facecolor=palette["bg"])
    plt.close(figure)
    return buffer.getvalue()


def _threat_strip(match, pieces, home, away):
    """
    The threat card's own numbers, led by the thing it is about.

    Section 7: ordered by payload, so a card that runs out of room loses a
    goal count rather than the npxG it exists to show. Penalties appear only
    when the match had one, and never inside an npxG total -- one spot kick is
    worth more than most teams' entire set-piece output.
    """
    from lib import xg as xg_lib
    frame = xg_lib.shots(match)
    seqs = {shot.seq for piece in pieces for shot in piece.shots}
    frame["setpiece"] = frame["seq"].isin(seqs)
    live = frame[frame["penalty"] == 0]

    def side(team):
        mine = live[live["team"] == team]
        return mine[mine["setpiece"]]["npxg"].sum(), mine["npxg"].sum(), \
            int(mine["setpiece"].sum())

    hs, ht, hn = side(home)
    aside, at, an = side(away)
    h = readout.summary(pieces, home)
    a = readout.summary(pieces, away)
    cells = [
        (f"{hs:.2f}-{aside:.2f}", "Set-Piece npxG"),
        (f"{ht:.2f}-{at:.2f}", "Total npxG"),
        (f"{hn}-{an}", "Set-Piece Shots"),
        (f"{h['goals']}-{a['goals']}", "Set-Piece Goals"),
    ]
    penalties = int(frame["penalty"].sum())
    if penalties:
        cells.append((str(penalties), "Penalties (Excl.)"))
    return cells


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
