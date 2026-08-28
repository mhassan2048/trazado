"""
Figures.

Every visual is a `draw_*` function that renders into a rectangle of a figure
you give it and returns the legend handles it needs. Nothing here creates its
own figure or writes its own title. That is what lets one visual appear both
as an on-screen plot and inside the branded export card at a different size,
from the same code -- section 7 asks for different padding and type sizes, not
a second implementation.

Notation, enforced here rather than per chart:

    comet (tapered)  found a teammate
    dashed line      cleared or incomplete
    accent           led to a shot, and nothing else, ever
    filled marker    duel won
    hollow marker    duel lost
"""

from __future__ import annotations

import io
import io as _io

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as _np
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Rectangle
from mplsoccer import Pitch, VerticalPitch

from lib import setpieces, typeface
from lib.setpieces import CORNER, FREEKICK, GOAL_KICK, PENALTY, THROW_IN

typeface.install()

# Colour carries the set piece type. Shape does not: a legend of circles,
# squares, ticks and triangles asked the reader to hold four glyph meanings in
# their head before they could read anything, and it still left the outcome to
# a second encoding. One hue per type, comets for everything.
# Three series hues for the attacking set pieces. Goal kicks take the neutral
# deliberately: no fourth hue survives a colour-blind check against these three
# (gold collides with the red at deltaE 1.1 under deuteranopia, blue with the
# violet), and they are the least interesting mark on a shared chart while
# being the most numerous. They have a chart of their own.
TYPE_COLOUR = {CORNER: "s1", FREEKICK: "s2", THROW_IN: "s3",
               GOAL_KICK: "muted", PENALTY: "ink"}
TYPE_LABEL = {CORNER: "corner", FREEKICK: "free kick", THROW_IN: "long throw",
              GOAL_KICK: "goal kick", PENALTY: "penalty"}


def colour_for(piece, palette):
    return palette[TYPE_COLOUR.get(piece.kind, "s1")]

# The penalty area, tiled. Names match lib.pitch.delivery_zone exactly, so the
# ledger and this map cannot disagree about where a ball landed.
#
# Absolute sides, not mirrored: the left half space is the left half space
# whichever corner the ball came from. Opta y=100 is the attacking team's left.
ZONE_BOXES = {
    "six-yard box":     (94.2, 100.0, 36.8, 63.2),
    "central":          (83.0, 94.2, 36.8, 63.2),
    "left half space":  (83.0, 94.2, 63.2, 79.0),
    "right half space": (83.0, 94.2, 21.0, 36.8),
    "edge of box":      (76.0, 83.0, 21.0, 79.0),
}


def _pitch(palette, linewidth=1.3):
    return VerticalPitch(
        pitch_type="opta", half=True,
        pad_top=4, pad_bottom=1, pad_left=1, pad_right=1,
        pitch_color=palette["surface"], line_color=palette["line"],
        linewidth=linewidth, goal_type="box", goal_alpha=0.7,
    )


def to_png(figure, dpi: int = 110) -> bytes:
    """Render to PNG bytes. st.pyplot re-saves with bbox_inches='tight',
    which crops the margins titles and legends live in."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=dpi, facecolor=figure.get_facecolor())
    plt.close(figure)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# visual 2 — delivery map
# ---------------------------------------------------------------------------

def draw_deliveries(figure, rect, pieces, palette, scale=1.0):
    """
    Every delivery as a comet, coloured by what kind of set piece it was.

    The comet does the work markers used to: it starts thin and faint where the
    ball was struck and ends thick and solid where it finished, so direction
    reads without an arrowhead and origin reads without a glyph. Deliveries
    that produced a shot are drawn heavier and fully opaque; the rest sit back.
    """
    axis = figure.add_axes(rect)
    pitch = _pitch(palette, linewidth=1.3 * scale)
    pitch.draw(ax=axis)

    shown = [p for p in pieces if p.is_delivery
             and p.x is not None and p.end_x is not None]
    # Draw the quiet ones first so a delivery that mattered is never buried.
    for piece in sorted(shown, key=lambda p: (p.led_to_shot, p.goal)):
        colour = colour_for(piece, palette)
        led = piece.led_to_shot
        width = (5.6 if piece.goal else 4.4 if led else 2.8) * scale
        pitch.lines(piece.x, piece.y, piece.end_x, piece.end_y, ax=axis,
                    color=colour, lw=width, comet=True, transparent=True,
                    alpha_start=0.04,
                    alpha_end=1.0 if piece.goal else 0.9 if led else 0.42,
                    zorder=4 if piece.goal else 3 if led else 2)

        # Outcome sits on the landing point, in the delivery's own colour, so
        # colour still means type and the marker means only what happened.
        # Nothing is drawn where nothing came of it.
        if piece.goal:
            # Solid all the way through. A ring around a disc left a gap in the
            # theme's background colour, which reads as hollow at any size.
            pitch.scatter(piece.end_x, piece.end_y, ax=axis, marker="o",
                          s=210 * scale ** 2, facecolor=colour,
                          edgecolor=colour, linewidths=0, zorder=7)
        elif led:
            pitch.scatter(piece.end_x, piece.end_y, ax=axis, marker="o",
                          s=110 * scale ** 2, facecolor="none",
                          edgecolor=colour, linewidths=2.0 * scale, zorder=6)
    return axis, type_legend(palette, shown) + outcome_legend(palette, shown)


def outcome_legend(palette, pieces):
    """
    Two entries, and only when the match has them.

    Neutral ink, because these apply across every type -- putting them in one
    type's hue would imply only that type can score.
    """
    ink = palette["ink"]
    out = []
    if any(p.led_to_shot and not p.goal for p in pieces):
        out.append(Line2D([], [], color=ink, marker="o", ls="none",
                          markerfacecolor="none", markeredgewidth=2,
                          markersize=11, label="led to a shot"))
    if any(p.goal for p in pieces):
        out.append(Line2D([], [], color=ink, marker="o", ls="none",
                          markerfacecolor=ink, markeredgewidth=0,
                          markersize=14, label="led to a goal"))
    return out


def type_legend(palette, pieces):
    """One swatch per type actually drawn. Nothing else."""
    kinds = [k for k in TYPE_LABEL if any(p.kind == k for p in pieces)]
    return [Line2D([], [], color=palette[TYPE_COLOUR[k]], lw=4.5, ls="-",
                   solid_capstyle="round", label=TYPE_LABEL[k])
            for k in kinds]


# ---------------------------------------------------------------------------
# visual 5 — aerial duels by zone
# ---------------------------------------------------------------------------

def aerial_tally(pieces):
    """Duels contested on a set-piece delivery, bucketed by where it landed."""
    tally = {name: [0, 0] for name in ZONE_BOXES}
    for piece in pieces:
        contact = piece.contact
        if not piece.is_delivery or contact is None or not contact.aerial:
            continue
        zone = piece.zone if piece.zone in tally else "edge of box"
        tally[zone][1] += 1
        tally[zone][0] += int(contact.attacking)
    return tally


def draw_aerials(figure, rect, pieces, palette, scale=1.0):
    tally = aerial_tally(pieces)
    busiest = max((t for _, t in tally.values()), default=0)

    pitch = _pitch(palette, linewidth=1.3 * scale)
    axis = figure.add_axes(rect)
    pitch.draw(ax=axis)
    axis.set_ylim(74.5, 101.5)
    axis.set_xlim(86, 14)

    for name, (x0, x1, y0, y1) in ZONE_BOXES.items():
        won, total = tally[name]
        weight = 0.0 if not busiest else total / busiest
        axis.add_patch(Rectangle((y0, x0), y1 - y0, x1 - x0,
                                 facecolor=palette["ink"],
                                 alpha=0.04 + 0.20 * weight,
                                 edgecolor=palette["line"], lw=0.9 * scale,
                                 zorder=2))
        cx, cy = (y0 + y1) / 2, (x0 + x1) / 2
        if not total:
            axis.text(cx, cy, name, color=palette["faint"],
                      fontsize=7.5 * scale, ha="center", va="center", zorder=5)
            continue
        axis.text(cx, cy + 1.9, f"{won}/{total}", color=palette["ink"],
                  fontsize=14 * scale, fontweight="bold", ha="center",
                  va="center", zorder=5)
        axis.text(cx, cy - 2.9, name, color=palette["muted"],
                  fontsize=7.5 * scale, ha="center", va="center", zorder=5)
        span = min(9.0, (y1 - y0) * 0.55)
        left = cx - span / 2
        axis.add_patch(Rectangle((left, cy - 0.9), span, 0.75, facecolor="none",
                                 edgecolor=palette["muted"], lw=0.9 * scale,
                                 zorder=6))
        if won:
            axis.add_patch(Rectangle((left, cy - 0.9), span * won / total, 0.75,
                                     facecolor=palette["muted"], lw=0, zorder=6))

    legend = [
        Line2D([], [], color=palette["muted"], marker="s", ls="none",
               markerfacecolor=palette["muted"], markersize=8,
               label="won by the delivering side"),
        Line2D([], [], color=palette["muted"], marker="s", ls="none",
               markerfacecolor="none", markeredgewidth=1.6, markersize=8,
               label="won by the defence"),
    ]
    return axis, legend


def aerial_caption(pieces) -> str:
    tally = aerial_tally(pieces)
    won = sum(w for w, _ in tally.values())
    total = sum(t for _, t in tally.values())
    return (f"{won}/{total} aerial first contacts won. Set-piece deliveries "
            f"only — open play duels are not counted.")


# ---------------------------------------------------------------------------
# visual 9 — dead balls against the scoreline
# ---------------------------------------------------------------------------

def draw_timeline(figure, rect, pieces, palette, home, away,
                  goals=None, max_minute=95, scale=1.0, half_time=45):
    """
    Every dead ball against the scoreline.

    Laid out in reserved bands so nothing can collide: the scoreline owns the
    middle, each team's ticks sit in their own strip clear of it, and the team
    labels sit clear of the ticks. Earlier versions computed tick height as a
    fraction of the axis and let the labels land wherever -- which put team
    names straight through the bars and clipped a 90th-minute goal off the
    right edge.
    """
    axis = figure.add_axes(rect)
    axis.set_facecolor(palette["surface"])
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(palette["line"])

    goals = sorted(goals or [], key=lambda g: g["minute"])
    minutes, diffs, running = [0], [0], 0
    for goal in goals:
        step = 1 if goal["for_home"] else -1
        minutes += [goal["minute"], goal["minute"]]
        diffs += [running, running + step]
        running += step
    minutes.append(max_minute); diffs.append(running)

    # Reserved bands, measured from the widest lead the match reached.
    peak = max((abs(d) for d in diffs), default=0)
    label_room = 1.15          # for the score/scorer text beside each step
    tick_base = peak + label_room + 0.85
    tick_len = 0.52
    name_y = tick_base + tick_len + 0.62
    limit = name_y + 0.45

    axis.fill_between(minutes, diffs, color=palette["accent"], alpha=0.09, zorder=1)
    axis.plot(minutes, diffs, color=palette["muted"], lw=1.5 * scale, zorder=3)
    axis.axhline(0, color=palette["line"], lw=1.0 * scale, zorder=2)

    # Half time, drawn only through the scoreline band so it cannot cross a tick.
    axis.plot([half_time, half_time], [-tick_base + 0.1, tick_base - 0.1],
              color=palette["line"], lw=1.0 * scale, ls=(0, (2, 3)), zorder=2)
    axis.text(half_time + 0.8, 0.12, "HT", color=palette["faint"],
              fontsize=8 * scale, va="bottom", ha="left")

    home_n = away_n = 0
    for piece in sorted(pieces, key=lambda p: p.minute):
        led = piece.led_to_shot
        is_home = piece.team == home
        home_n, away_n = (home_n + 1, away_n) if is_home else (home_n, away_n + 1)
        colour = colour_for(piece, palette)
        # Every restart is the same length. Varying it by outcome made the
        # rows read as two different things at once; the dot carries outcome
        # and the bar carries only "a dead ball happened here".
        direction = 1 if is_home else -1
        base = tick_base * direction
        tip = base + tick_len * direction
        axis.plot([piece.minute, piece.minute], [base, tip],
                  color=colour, lw=3.0 * scale, solid_capstyle="round",
                  alpha=0.95 if led else 0.55, zorder=5)
        if led:
            axis.scatter(piece.minute, tip, marker="o", s=34 * scale ** 2,
                         facecolor=colour, edgecolor=colour, linewidths=0,
                         zorder=6)

    # Goals: a dot on the step, with the new score and scorer placed so the
    # text stays inside the axes at either end of the match.
    from_set_piece = {p.shots[0].seq for p in pieces if p.goal and p.shots}
    tally_h = tally_a = 0
    previous = None
    for goal in goals:
        tally_h, tally_a = ((tally_h + 1, tally_a) if goal["for_home"]
                            else (tally_h, tally_a + 1))
        y = tally_h - tally_a
        minute = goal["minute"]
        special = goal["seq"] in from_set_piece
        colour = palette["s1"] if special else palette["muted"]
        axis.scatter(minute, y, marker="o", s=70 * scale ** 2,
                     facecolor=palette["bg"], edgecolor=colour,
                     lw=2.0 * scale, zorder=8)

        name = goal["player"].split()[-1] if goal["player"] else ""
        text = f"{tally_h}-{tally_a}" + (f" {name}" if name else "") + (" ·SP" if special else "")
        # Anchor away from whichever edge is close, and stagger a goal that
        # lands within six minutes of the previous one.
        if minute < max_minute * 0.12:
            ha, dx = "left", 9
        elif minute > max_minute * 0.86:
            ha, dx = "right", -9
        else:
            ha, dx = "center", 0
        crowded = previous is not None and minute - previous < 6
        dy = (-17 if goal["for_home"] else 13) if crowded else (13 if goal["for_home"] else -17)
        axis.annotate(text, (minute, y), textcoords="offset points",
                      xytext=(dx, dy), ha=ha,
                      color=palette["ink"] if special else palette["muted"],
                      fontsize=8.5 * scale,
                      fontweight="bold" if special else "normal", zorder=9)
        previous = minute

    axis.text(1.5, name_y, f"{home}  ·  {home_n} dead balls",
              color=palette["muted"], fontsize=8.5 * scale, va="center")
    axis.text(1.5, -name_y, f"{away}  ·  {away_n} dead balls",
              color=palette["muted"], fontsize=8.5 * scale, va="center")

    axis.set_xlim(-1, max_minute + 1)
    axis.set_ylim(-limit, limit)
    axis.set_yticks([])
    axis.set_xticks([0, 15, 30, 45, 60, 75, 90])
    axis.tick_params(colors=palette["faint"], labelsize=8 * scale, length=0)

    legend = type_legend(palette, pieces) + [
        Line2D([], [], color=palette["ink"], marker="o", ls="none",
               markerfacecolor=palette["ink"], markeredgewidth=0,
               markersize=8, label="led to a shot"),
        Line2D([], [], color=palette["muted"], lw=1.6, label="scoreline"),
    ]
    return axis, legend


def timeline_caption(pieces, home, away) -> str:
    home_n = sum(1 for p in pieces if p.team == home)
    away_n = len(pieces) - home_n
    shots = sum(1 for p in pieces if p.led_to_shot)
    return (f"{len(pieces)} dead balls — {home_n} {home}, {away_n} {away}. "
            f"{shots} produced a shot. Ticks above the line are {home}, below "
            f"are {away}; the line is the running scoreline.")


def draw_aerial_breakdown(figure, rect, pieces, palette, scale=1.0):
    """
    The same duels again, cut by which restart produced them.

    A five-zone map over two or three duels -- which is what one match gives
    you -- leaves most of the frame empty. This fills it with the other cut of
    the same numbers rather than with padding, and it answers a question the
    zone map cannot: which kind of set piece is actually winning the ball.
    """
    from collections import Counter
    won = Counter()
    total = Counter()
    for piece in pieces:
        contact = piece.contact
        if not piece.is_delivery or contact is None or not contact.aerial:
            continue
        total[piece.kind] += 1
        won[piece.kind] += int(contact.attacking)

    order = [k for k in (CORNER, FREEKICK, THROW_IN) if total[k]]
    axis = figure.add_axes(rect)
    axis.set_facecolor("none")
    axis.axis("off")
    if not order:
        return axis, []

    axis.set_xlim(0, 1); axis.set_ylim(-0.5, len(order) - 0.5)
    label = {CORNER: "corners", FREEKICK: "free kicks", THROW_IN: "long throws"}
    biggest = max(total[k] for k in order)

    for index, kind in enumerate(order):
        y = len(order) - 1 - index
        share = total[kind] / biggest
        axis.text(0.0, y + 0.30, label[kind], color=palette["muted"],
                  fontsize=10.5 * scale, va="center", ha="left")
        axis.text(1.0, y + 0.30, f"{won[kind]}/{total[kind]}",
                  color=palette["ink"], fontsize=12 * scale, va="center",
                  ha="right", fontweight="bold")
        # Outline is every duel; the fill is the ones won. Same reading as a
        # filled versus hollow marker anywhere else in the app.
        axis.add_patch(Rectangle((0, y - 0.18), share, 0.30, facecolor="none",
                                 edgecolor=palette["muted"], lw=1.1 * scale))
        if won[kind]:
            axis.add_patch(Rectangle((0, y - 0.18),
                                     share * won[kind] / total[kind], 0.30,
                                     facecolor=palette["muted"], lw=0))
    return axis, []


# ---------------------------------------------------------------------------
# set-piece share of threat
# ---------------------------------------------------------------------------

# npxG spans roughly 0.02 to 0.45 on one match, a 22x ratio. Encoded as area
# with no bounds the small shots vanish and the biggest swallows the box, so the
# scale is clamped at both ends and the legend carries reference sizes. An area
# encoding without a key is unreadable by design.
MIN_AREA, MAX_AREA = 22.0, 620.0
KEY_VALUES = (0.05, 0.30)


def _area(value, scale=1.0):
    """Marker area for an npxG value. Area, not radius -- radius exaggerates
    by the square, which is the classic way a bubble chart lies."""
    capped = min(max(float(value), 0.0), 0.45) / 0.45
    return (MIN_AREA + (MAX_AREA - MIN_AREA) * capped) * scale ** 2


def draw_threat(figure, rect, match, pieces, palette, home, away, scale=1.0):
    """
    Where each side's shot threat came from, and how much of it was dead balls.

    Two half pitches, every shot sized by npxG. Set-piece shots carry the
    accent and are drawn last; open play sits back as faint outlines. Section 4
    already says the quiet ones go first so what mattered is never buried --
    that line was written for deliveries and describes this exactly.

    The claim rests on a handful of shots, so the chart shows every one of them
    rather than rendering a share as a smooth quantity. A reader can count them.
    That is section 1's fraction rule applied to form rather than to a label.
    """
    from lib import xg as xg_lib

    frame = xg_lib.shots(match)
    setpiece_seqs = {shot.seq for piece in pieces for shot in piece.shots}
    frame["setpiece"] = frame["seq"].isin(setpiece_seqs)
    live = frame[frame["penalty"] == 0]

    x, y, width, height = rect
    band = height * 0.26
    pitch_h = height - band
    handles = []

    for index, team in enumerate((home, away)):
        cell = [x + index * width / 2.0, y + band,
                width / 2.0 - 0.012, pitch_h]
        axis = figure.add_axes(cell)
        pitch = _pitch(palette, linewidth=1.05 * scale)
        pitch.draw(ax=axis)
        mine = live[live["team"] == team]

        # Quiet first, accent last, goals last of all.
        order = mine.sort_values(["setpiece", "goal"])
        for row in order.itertuples():
            area = _area(row.npxg, scale)
            if row.setpiece:
                axis.scatter(row.y, row.x, s=area, marker="o",
                             facecolor=palette["s1"], edgecolor=palette["s1"],
                             linewidth=0, alpha=0.92, zorder=4)
            else:
                axis.scatter(row.y, row.x, s=area, marker="o",
                             facecolor="none", edgecolor=palette["faint"],
                             linewidth=1.0 * scale, zorder=2)
            if row.goal:
                axis.scatter(row.y, row.x, s=area * 2.3, marker="o",
                             facecolor="none", edgecolor=palette["ink"],
                             linewidth=1.3 * scale, zorder=5)

        total = mine["npxg"].sum()
        share = mine[mine["setpiece"]]["npxg"].sum()
        # The fraction, never a bare percentage: this is eight shots.
        axis.set_title(f"{share:.2f} of {total:.2f}", color=palette["ink"],
                       fontsize=12.5 * scale, fontweight="bold", pad=6 * scale)

    _threat_band(figure, [x, y + band * 0.10, width, band * 0.80], live, palette,
                 home, away, scale)

    handles = [
        Line2D([], [], marker="o", linestyle="none", markersize=7 * scale,
               markerfacecolor=palette["s1"], markeredgecolor=palette["s1"],
               label="from a set-piece"),
        Line2D([], [], marker="o", linestyle="none", markersize=7 * scale,
               markerfacecolor="none", markeredgecolor=palette["faint"],
               label="open play"),
    ]
    if int(live["goal"].sum()):
        handles.append(Line2D([], [], marker="o", linestyle="none",
                              markersize=9 * scale, markerfacecolor="none",
                              markeredgecolor=palette["ink"], label="goal"))
    for value in KEY_VALUES:
        handles.append(Line2D([], [], marker="o", linestyle="none",
                              markersize=(_area(value, scale) ** 0.5) * 0.62,
                              markerfacecolor="none",
                              markeredgecolor=palette["muted"],
                              label=f"{value:.2f} npxG"))
    return None, handles


def threat_caption(match, pieces, home, away):
    """The side that got most from dead balls, stated as a fraction."""
    from lib import xg as xg_lib
    frame = xg_lib.shots(match)
    seqs = {shot.seq for piece in pieces for shot in piece.shots}
    frame["setpiece"] = frame["seq"].isin(seqs)
    live = frame[frame["penalty"] == 0]
    best, share, total, count = None, 0.0, 0.0, 0
    for team in (home, away):
        mine = live[live["team"] == team]
        sp = mine[mine["setpiece"]]
        if sp["npxg"].sum() > share:
            best, share = team, sp["npxg"].sum()
            total, count = mine["npxg"].sum(), len(sp)
    if not best or not count:
        return "Neither side created a shot from a set-piece."
    shots_word = "shot" if count == 1 else "shots"
    return (f"{best} created {share:.2f} of their {total:.2f} npxG from "
            f"set-pieces, off {count} {shots_word}.")


def _threat_band(figure, rect, live, palette, home, away, scale):
    """
    Cumulative npxG, stepped, with the set-piece contribution in accent.

    Stepped rather than smoothed: a shot changes the value at one moment, and
    interpolating implies chance quality accrued continuously between them. The
    band is what a share number cannot show -- three shots off one sequence read
    as a cliff rather than as a decimal.
    """
    axis = figure.add_axes(rect)
    axis.set_facecolor("none")
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(palette["line"])
    axis.tick_params(colors=palette["faint"], labelsize=7.5 * scale, length=2)

    ceiling = 0.0
    for team, colour in ((home, palette["s2"]), (away, palette["s3"])):
        mine = live[live["team"] == team].sort_values("minute")
        if mine.empty:
            continue
        minutes, running, total = [0], [0.0], 0.0
        for row in mine.itertuples():
            total += row.npxg
            minutes.append(row.minute); running.append(total)
        minutes.append(95); running.append(total)
        ceiling = max(ceiling, total)
        axis.step(minutes, running, where="post", color=colour,
                  lw=1.6 * scale, label=team)
        # Labelled at the line's end rather than in the legend. A legend entry
        # would make the reader carry a colour across the card; a label sits
        # where the eye already is, and keeps the legend to the encodings that
        # actually need explaining.
        axis.text(96, total, f" {team}", color=colour, va="center", ha="left",
                  fontsize=7.6 * scale, fontweight="bold")
        for row in mine[mine.setpiece].itertuples():
            axis.plot([row.minute], [running[minutes.index(row.minute)]],
                      marker="o", markersize=3.4 * scale, color=palette["s1"],
                      zorder=4)
    axis.set_xlim(0, 128)
    axis.set_ylim(0, max(ceiling * 1.18, 0.5))
    axis.set_xticks([0, 45, 90])
    axis.set_xlabel("minute", color=palette["faint"], fontsize=7.5 * scale)
    axis.set_ylabel("cumulative npxG", color=palette["faint"],
                    fontsize=7.5 * scale)


# ---------------------------------------------------------------------------
# visual 12 — team comparison


# Section 7: crests sit at 75% so they read as identity rather than compete
# with the numbers beside them.
CREST_ALPHA = 0.75

# How much vertical room the crest band takes, in rows.
CREST_ROWS = 0.9


def _crest_pair(ids, home, away):
    """
    Both crests as image arrays, or None if either is missing.

    Both or neither: one crest and one bare column reads as a rendering fault
    rather than as a missing badge.
    """
    if not ids:
        return None
    from lib import badges
    out = []
    for team in (home, away):
        data = badges.fetch(int(ids.get(team) or 0))
        if not data:
            return None
        try:
            from PIL import Image
            out.append(_np.asarray(
                Image.open(_io.BytesIO(data)).convert("RGBA")))
        except Exception:
            return None
    return out


# ---------------------------------------------------------------------------

# Rows in reading order: the volume first, then what the volume actually
# produced. Ending on goals means the eye finishes on the outcome rather than
# on a throw-in count.
#
# Two kinds of row. A count row is one number a side. A fraction row is a
# numerator over a denominator, drawn the way every duel in this app is drawn:
# outline for what was attempted, fill for what was won. That keeps one
# vocabulary across the map, the breakdown and this table.
_ROWS = [
    ("Set-Pieces",      "total",      None),
    ("Corners",         CORNER,       "kind"),
    ("Free Kicks",      FREEKICK,     "kind"),
    ("Long Throws",     THROW_IN,     "kind"),
    ("Goal Kicks",      GOAL_KICK,    "kind"),
    ("First Contact",   "contact",    "fraction"),
    ("Aerials Won",     "aerial",     "fraction"),
    ("Shots",           "shots",      None),
    ("Shots, 2nd Phase", "second",    "fraction"),
    ("Goals",           "goals",      None),
]


def _row_values(stat, key, mode):
    """(numerator, denominator) for one side of one row; denominator None
    for a plain count."""
    if mode == "kind":
        return stat["by_kind"].get(key, 0), None
    if mode == "fraction":
        if key == "contact":
            return stat["contact_won"], stat["contact_total"]
        if key == "aerial":
            return stat["aerial_won"], stat["aerial_total"]
        return stat["second"], stat["shots"]
    return stat[key], None


def comparison_rows(pieces, home, away):
    """The rows this match actually supports, in order."""
    from lib import readout
    left, right = readout.summary(pieces, home), readout.summary(pieces, away)
    out = []
    for label, key, mode in _ROWS:
        h = _row_values(left, key, mode)
        a = _row_values(right, key, mode)
        # Section 1: never render an empty panel, and never an empty row
        # either. A match with no long throws should not carry a Long Throws
        # line reading 0 against 0.
        if mode == "fraction":
            if not (h[1] or a[1]):
                continue
        elif not (h[0] or a[0]):
            continue
        out.append((label, mode, h, a))
    return out


def draw_comparison(figure, rect, pieces, palette, home, away, scale=1.0,
                    ids=None):
    """
    Both sides' set-piece work, row by row, counted.

    Bars run outward from a central label column. Each row is scaled to its
    own larger side, because a row measuring corners and a row measuring goals
    share no unit and comparing their lengths would mean nothing. The raw
    number sits at the end of every bar, so length is never the only thing
    carrying the value -- which is what keeps a 3-against-2 row from reading
    like a rout.
    """
    rows = comparison_rows(pieces, home, away)
    axis = figure.add_axes(rect)
    axis.set_facecolor("none")
    axis.axis("off")
    if not rows:
        return axis, []

    axis.set_xlim(0, 1)
    # Headroom above the top row for the crests, and only when there are
    # crests to put there.
    crests = _crest_pair(ids, home, away)
    axis.set_ylim(-0.6, len(rows) - 0.4 + (CREST_ROWS if crests else 0.0))

    colours = (palette["s1"], palette["s2"])
    height = 0.34

    # Draw the labels and the numbers first, then measure what they actually
    # occupy and give the bars whatever is left. Section 7: bands are measured
    # from the data, never taken as a fraction of the axis with text dropped
    # wherever it lands -- which is how "Shots, 2nd Phase" ended up printed
    # straight through both bars.
    def cell(value, mode):
        numerator, denominator = value
        return f"{numerator}/{denominator}" if mode == "fraction" else str(numerator)

    probes = [axis.text(0.5, 0, label, fontsize=10.2 * scale, alpha=0)
              for label, _, _, _ in rows]
    probes += [axis.text(0.5, 0, cell(v, mode), fontsize=11.5 * scale,
                         fontweight="bold", alpha=0)
               for _, mode, h, a in rows for v in (h, a)]
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    axis_px = axis.get_window_extent(renderer).width
    widths = [t.get_window_extent(renderer).width / axis_px for t in probes]
    label_w = max(widths[:len(rows)])
    digit_w = max(widths[len(rows):])
    for t in probes:
        t.remove()

    # Half the widest label each side of centre, plus breathing room; the
    # numbers get their own reserved column at the outer end. Capped so a
    # freak label cannot squeeze the bars out of existence.
    gutter = min(label_w / 2 + 0.028, 0.34)
    digits = min(digit_w + 0.014, 0.14)
    inner_l, inner_r = 0.5 - gutter, 0.5 + gutter
    span = max(inner_l - digits, 0.02)

    for index, (label, mode, h, a) in enumerate(rows):
        y = len(rows) - 1 - index
        base = max(h[1] or h[0], a[1] or a[0]) or 1

        axis.text(0.5, y, label, color=palette["muted"],
                  fontsize=10.2 * scale, va="center", ha="center")

        for value, side, colour in ((h, "home", colours[0]),
                                    (a, "away", colours[1])):
            numerator, denominator = value
            outer = denominator if denominator is not None else numerator
            length = span * outer / base
            sign = -1 if side == "home" else 1
            edge = inner_l if side == "home" else inner_r
            x = edge - length if side == "home" else edge
            text_x = edge - length - 0.012 if side == "home" else edge + length + 0.012
            align = "right" if side == "home" else "left"

            if denominator is None:
                if numerator:
                    axis.add_patch(Rectangle((x, y - height / 2), length, height,
                                             facecolor=colour, lw=0))
                shown = str(numerator)
            else:
                # Outline is every attempt, fill is the ones won -- the same
                # reading as a filled versus hollow marker anywhere else.
                if outer:
                    axis.add_patch(Rectangle((x, y - height / 2), length, height,
                                             facecolor="none", edgecolor=colour,
                                             lw=1.15 * scale))
                if numerator:
                    won = span * numerator / base
                    wx = edge - won if side == "home" else edge
                    axis.add_patch(Rectangle((wx, y - height / 2), won, height,
                                             facecolor=colour, lw=0))
                shown = f"{numerator}/{denominator}"

            axis.text(text_x, y, shown,
                      color=palette["ink"] if numerator else palette["faint"],
                      fontsize=11.5 * scale, va="center", ha=align,
                      fontweight="bold")

    # A crest over each column says which side is which without a legend row,
    # and without the feed's inconsistent abbreviations of a club name. The
    # names come back only when a badge is missing, so a side is never
    # unlabelled.
    if crests:
        top = len(rows) - 0.4 + 0.42
        for image, x in zip(crests, (inner_l - span / 2, inner_r + span / 2)):
            axis.add_artist(AnnotationBbox(
                # Section 7's 75%, the same as every other crest on a card.
                OffsetImage(image, zoom=0.34 * scale, alpha=CREST_ALPHA),
                (x, top), frameon=False, box_alignment=(0.5, 0.5)))

    handles = [] if crests else [
        Line2D([], [], marker="s", linestyle="none", markersize=8 * scale,
               markerfacecolor=colours[0], markeredgecolor=colours[0],
               label=home),
        Line2D([], [], marker="s", linestyle="none", markersize=8 * scale,
               markerfacecolor=colours[1], markeredgecolor=colours[1],
               label=away),
    ]
    # The hollow bar is a marker like any other, and an unlabelled symbol is
    # worse than no symbol.
    if any(mode == "fraction" for _, mode, _, _ in rows):
        handles.append(
            Line2D([], [], marker="s", linestyle="none", markersize=8 * scale,
                   markerfacecolor="none", markeredgecolor=palette["muted"],
                   label="attempted"))
    return axis, handles


# What a reader would actually lead with, in order. Not simply the biggest
# gap: "Set-Pieces" is a sum dominated by goal kicks, so a row reading 25 to 20
# beats a 4-to-1 shot count on raw difference while saying far less about the
# match.
_CAPTION_ORDER = [("Goals", 1), ("Shots", 2), ("Corners", 2),
                  ("Free Kicks", 2), ("Goal Kicks", 3), ("Set-Pieces", 4)]


def comparison_caption(pieces, home, away):
    """The row worth leading with, named in counts."""
    counts = {label: (h[0], a[0])
              for label, mode, h, a in comparison_rows(pieces, home, away)
              if mode != "fraction"}
    for label, least in _CAPTION_ORDER:
        pair = counts.get(label)
        if not pair or abs(pair[0] - pair[1]) < least:
            continue
        left, right = pair
        leader = home if left > right else away
        return (f"{leader} had {max(left, right)} {label.lower()} "
                f"to {min(left, right)}.")
    # No row is decisive. Say what the match had rather than reaching for a
    # comparison it does not support -- and never claim "evenly split", which
    # a 1-0 split would have been described as.
    total = len(pieces)
    ball = "dead ball" if total == 1 else "dead balls"
    pair = counts.get("Set-Pieces")
    if pair and (pair[0] or pair[1]):
        return f"{total} {ball}, {pair[0]} to {pair[1]}."
    return f"{total} {ball}."


# ---------------------------------------------------------------------------
# on-screen wrappers: same drawing code, plainer frame, no branding block
# ---------------------------------------------------------------------------

def _screen(figure, title, subtitle, palette, handles, legend_y=0.045):
    if title:
        figure.text(0.03, 0.975, title, color=palette["ink"], fontsize=14,
                    fontweight="bold", va="top")
    if subtitle:
        figure.text(0.03, 0.928, subtitle, color=palette["muted"], fontsize=9.5,
                    va="top")
    if handles:
        legend = figure.legend(handles=handles, loc="lower center",
                               bbox_to_anchor=(0.5, legend_y), ncol=3,
                               frameon=False, fontsize=8.2, handlelength=2.2,
                               columnspacing=1.6, handletextpad=0.6)
        for text in legend.get_texts():
            text.set_color(palette["muted"])
    return figure


def delivery_map(pieces, palette, title="", subtitle=""):
    figure = plt.figure(figsize=(6.2, 7.3), facecolor=palette["bg"])
    _, handles = draw_deliveries(figure, [0.03, 0.155, 0.94, 0.735], pieces, palette)
    return _screen(figure, title, subtitle, palette, handles, legend_y=0.02)


def aerial_zones(pieces, palette, title="Aerial Duels", subtitle=""):
    figure = plt.figure(figsize=(6.2, 5.6), facecolor=palette["bg"])
    _, handles = draw_aerials(figure, [0.03, 0.34, 0.94, 0.52], pieces, palette)
    draw_aerial_breakdown(figure, [0.06, 0.10, 0.88, 0.17], pieces, palette, 0.95)
    return _screen(figure, title, subtitle or aerial_caption(pieces),
                   palette, handles, legend_y=0.285)


def comparison(pieces, palette, home, away, title="Team Comparison",
               subtitle="", ids=None):
    rows = len(comparison_rows(pieces, home, away))
    # Height follows the row count, plus a band for the crests. A fixed frame
    # either crushes ten rows or leaves half the card empty on a match with
    # three.
    tall = 1.55 + 0.42 * (rows + (CREST_ROWS if _crest_pair(ids, home, away) else 0))
    figure = plt.figure(figsize=(6.6, tall), facecolor=palette["bg"])
    top = 0.86 - 0.30 / tall
    _, handles = draw_comparison(figure, [0.045, 0.155, 0.91, top - 0.155],
                                 pieces, palette, home, away, ids=ids)
    return _screen(figure, title,
                   subtitle or comparison_caption(pieces, home, away),
                   palette, handles, legend_y=0.015)


def timeline(pieces, palette, home, away, goals=None, max_minute=95):
    figure = plt.figure(figsize=(7.4, 3.9), facecolor=palette["bg"])
    _, handles = draw_timeline(figure, [0.055, 0.30, 0.925, 0.50], pieces,
                               palette, home, away, goals=goals,
                               max_minute=max_minute)
    return _screen(figure, "Dead Balls Against the Scoreline",
                   timeline_caption(pieces, home, away), palette, handles,
                   legend_y=0.01)


# ---------------------------------------------------------------------------
# goal kicks — their own visual, because they happen on their own pitch
# ---------------------------------------------------------------------------

def draw_goal_kicks(figure, rect, pieces, palette, home, scale=1.0):
    """
    Where the keeper put it, and whether it stuck.

    Goal kicks cannot share the delivery map: that map is the attacking half
    and these start on the other goal line. Full pitch, always left to right,
    so a launched kick reads as the long diagonal it is. Colour separates the
    ones the kicking side kept from the ones they gave away, which is the only
    question worth asking of a goal kick.
    """
    kicks = [p for p in pieces if p.kind == GOAL_KICK
             and p.x is not None and p.end_x is not None]
    pitch = Pitch(pitch_type="opta", pitch_color=palette["surface"],
                  line_color=palette["line"], linewidth=1.2 * scale,
                  goal_type="box", goal_alpha=0.7, pad_top=1, pad_bottom=1)
    axis = figure.add_axes(rect)
    pitch.draw(ax=axis)
    axis.axvline(50, color=palette["line"], lw=1.0 * scale, ls=(0, (2, 3)),
                 zorder=2)

    for kick in sorted(kicks, key=lambda k: bool(k.contact and k.contact.attacking)):
        kept = bool(kick.contact and kick.contact.attacking)
        colour = palette["s2"] if kept else palette["s1"]
        pitch.lines(kick.x, kick.y, kick.end_x, kick.end_y, ax=axis,
                    color=colour, lw=(4.0 if kept else 3.0) * scale, comet=True,
                    transparent=True, alpha_start=0.04,
                    alpha_end=0.9 if kept else 0.6, zorder=3)

    legend = [
        Line2D([], [], color=palette["s2"], lw=4.5, ls="-",
               solid_capstyle="round", label="kicking side won it"),
        Line2D([], [], color=palette["s1"], lw=4.5, ls="-",
               solid_capstyle="round", label="lost it"),
    ]
    return axis, legend


def goal_kick_caption(pieces, team) -> str:
    kicks = [p for p in pieces if p.kind == GOAL_KICK]
    if not kicks:
        return "No goal kicks."
    launched = sum(1 for k in kicks if k.subtype == setpieces.GK_LAUNCHED)
    contested = [k for k in kicks if k.contested]
    won = sum(1 for k in kicks if k.contact and k.contact.attacking)
    bits = [f"{len(kicks)} goal kicks, {launched} launched past halfway",
            f"{won}/{len(kicks)} first contacts won"]
    if contested:
        aw = sum(1 for k in contested if k.contact.attacking)
        bits.append(f"{aw}/{len(contested)} of the aerial duels won")
    return ". ".join(bits) + "."


def goal_kicks(pieces, palette, home, title="Goal Kicks", subtitle=""):
    figure = plt.figure(figsize=(7.2, 5.4), facecolor=palette["bg"])
    _, handles = draw_goal_kicks(figure, [0.03, 0.20, 0.94, 0.62], pieces,
                                 palette, home)
    return _screen(figure, title, subtitle, palette, handles, legend_y=0.02)


# ---------------------------------------------------------------------------
# visual 6 — second phase chain
# ---------------------------------------------------------------------------

def chainable(pieces):
    """
    The set pieces this chart is about: the ones where the shot came *after*
    the first contact.

    A first-phase set piece has no second phase -- the header went straight in
    -- so its panel would be a delivery and a dot on the same spot, filed under
    a heading that says otherwise. Those live on the delivery map.
    """
    return [p for p in pieces
            if p.is_delivery and p.contact and p.shots
            and p.shots[0].phase == setpieces.SECOND_PHASE]


def draw_chains(figure, rect, pieces, palette, scale=1.0, columns=2, cap=6):
    """
    Visual 6, on the pitch.

    One small pitch per set piece that produced a shot, because that is a
    median of three a team and drawing each one keeps the geometry -- where the
    ball landed, where it was won, where the shot came from. A flow diagram
    would throw all of that away, which is why the spec rules one out.

    Reading each panel: the comet is the delivery, the ring is where first
    contact happened, the thin line is the ball being worked, and the marker at
    the end is the shot -- solid when it went in.
    """
    shown = chainable(pieces)[:cap]
    if not shown:
        return [], []

    # One crop for every panel, computed across all of them. A per-panel crop
    # gave each pitch its own aspect and the grid came out ragged -- the panels
    # have to be directly comparable, which means identical.
    depths = []
    for piece in shown:
        depths += [v for v in (piece.x, piece.end_x,
                               piece.contact.x, piece.shots[0].x) if v is not None]
        depths += [l.x for l in piece.chain if l.x is not None]
    floor = max(46.0, min(depths) - 5) if depths else 60.0

    rows = -(-len(shown) // columns)
    left, bottom, width, height = rect
    gap_x, gap_y = 0.018, 0.052
    cell_w = (width - gap_x * (columns - 1)) / columns
    cell_h = (height - gap_y * (rows - 1)) / rows

    for index, piece in enumerate(shown):
        row, col = divmod(index, columns)
        x = left + col * (cell_w + gap_x)
        y = bottom + (rows - 1 - row) * (cell_h + gap_y)

        pitch = VerticalPitch(
            pitch_type="opta", half=True, pad_top=2, pad_bottom=1,
            pad_left=1, pad_right=1,
            pitch_color=palette["surface"], line_color=palette["line"],
            linewidth=0.9 * scale, goal_type="box", goal_alpha=0.7)
        axis = figure.add_axes([x, y, cell_w, cell_h])
        pitch.draw(ax=axis)

        colour = colour_for(piece, palette)
        shot = piece.shots[0]
        contact = piece.contact

        axis.set_ylim(floor, 101.5)

        # 1. the delivery
        pitch.lines(piece.x, piece.y, piece.end_x, piece.end_y, ax=axis,
                    color=colour, lw=4.0 * scale, comet=True, transparent=True,
                    alpha_start=0.05, alpha_end=0.9, zorder=3)

        # 2. first contact
        if contact.x is not None:
            pitch.scatter(contact.x, contact.y, ax=axis, marker="o",
                          s=110 * scale ** 2,
                          facecolor=colour if contact.attacking else "none",
                          edgecolor=colour, linewidths=1.8 * scale, zorder=5)

        # 3. the ball being worked, contact through every link to the shot
        route = [(contact.x, contact.y)]
        route += [(l.x, l.y) for l in piece.chain if l.x is not None]
        route.append((shot.x, shot.y))
        route = [pt for pt in route if pt[0] is not None]
        for (ax0, ay0), (ax1, ay1) in zip(route, route[1:]):
            pitch.lines(ax0, ay0, ax1, ay1, ax=axis, color=palette["muted"],
                        lw=1.3 * scale, linestyle=(0, (2.6, 2.2)), alpha=0.75,
                        zorder=4, comet=False)

        # 4. the shot
        pitch.scatter(shot.x, shot.y, ax=axis, marker="o",
                      s=(150 if shot.goal else 110) * scale ** 2,
                      facecolor=colour if shot.goal else palette["bg"],
                      edgecolor=colour, linewidths=2.2 * scale, zorder=6)

        outcome = "GOAL" if shot.goal else shot.type.replace("MissedShots", "off target").replace("SavedShot", "saved").replace("BlockedShot", "blocked").replace("ShotOnPost", "post")
        axis.set_title(f"{piece.clock}  {TYPE_LABEL.get(piece.kind, '')} · {outcome}",
                       color=palette["ink"] if shot.goal else palette["muted"],
                       fontsize=8.6 * scale,
                       fontweight="bold" if shot.goal else "normal", pad=5)
        axis.text(0.5, -0.045, f"{piece.taker.split()[-1]} → {shot.player.split()[-1]}",
                  transform=axis.transAxes, ha="center", va="top",
                  color=palette["faint"], fontsize=7.6 * scale)

    legend = [
        Line2D([], [], color=palette["muted"], lw=3.4, ls="-",
               solid_capstyle="round", label="the delivery"),
        Line2D([], [], color=palette["muted"], marker="o", ls="none",
               markerfacecolor=palette["muted"], markersize=8,
               label="first contact won"),
        Line2D([], [], color=palette["muted"], marker="o", ls="none",
               markerfacecolor="none", markeredgewidth=1.8, markersize=8,
               label="first contact lost"),
        Line2D([], [], color=palette["muted"], lw=1.4, ls=(0, (2.6, 2.2)),
               label="ball worked to the shot"),
    ]
    return shown, legend


def chain_caption(pieces) -> str:
    shown = chainable(pieces)
    if not shown:
        return "No set-piece produced a shot."
    goals = sum(1 for p in shown if p.shots[0].goal)
    total = sum(len(p.shots) for p in pieces if p.is_delivery)
    word = "set-piece" if len(shown) == 1 else "set-pieces"
    bits = [f"{len(shown)} of {total} {word} produced a shot after the first "
            f"contact, not off the delivery"]
    if goals:
        bits.append(f"{goals} scored")
    return ". ".join(bits) + "."


def chains(pieces, palette, title="Second Phase", subtitle=""):
    figure = plt.figure(figsize=(6.6, 6.4), facecolor=palette["bg"])
    _, handles = draw_chains(figure, [0.03, 0.14, 0.94, 0.72], pieces, palette,
                             scale=0.9)
    return _screen(figure, title, subtitle or chain_caption(pieces), palette,
                   handles, legend_y=0.01)
