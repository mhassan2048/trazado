"""
The analysis screen.

Scroll layout, hero first. Every section is conditional: a match with no
throw-ins into the box renders no throw-in row, and a match with no set piece
goals renders no goal card. An empty panel is never drawn.
"""

from __future__ import annotations

import streamlit as st

from lib import badges, readout, setpieces
from lib.setpieces import CORNER, FREEKICK, GOAL_KICK, THROW_IN, PENALTY

from .charts import (aerial_zones, chain_caption, chainable, chains,
                     delivery_map, goal_kick_caption as charts_caption,
                     goal_kicks, timeline, to_png)
from .export import VISUALS, card
from .theme import THEMES as ALL_THEMES
from .theme import THEMES

KIND_LABEL = {CORNER: "corners", FREEKICK: "free kicks",
              THROW_IN: "throw-ins", PENALTY: "penalties",
              GOAL_KICK: "goal kicks"}


def _crest(team_id: int, name: str) -> str:
    src = badges.url(team_id)
    if src:
        return f'<img class="tz-crest" src="{src}" alt="">'
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    return f'<div class="tz-mono-crest" aria-hidden="true">{initials}</div>'


def _identity(match, home_id: int, away_id: int) -> str:
    meta = match.meta
    bits = [b for b in (meta.get("competition"), meta.get("venue"),
                        str(meta.get("start_date") or "")[:10]) if b]
    return f"""
<div class="tz-match">
  <div class="tz-side">{_crest(home_id, meta['home_team'])}
    <div class="tz-team">{meta['home_team']}</div></div>
  <div class="tz-score">{meta.get('score', '')}</div>
  <div class="tz-side tz-side--away">
    <div class="tz-team">{meta['away_team']}</div>{_crest(away_id, meta['away_team'])}</div>
</div>
<div class="tz-matchmeta">{' · '.join(bits)}</div>"""


def _glossary() -> str:
    items = "".join(
        f'<div class="tz-gl"><b>{term}</b> {meaning}</div>'
        for term, meaning in readout.GLOSSARY)
    return f'<details class="tz-glossary"><summary>What these numbers mean</summary>{items}</details>'


def _summary(pieces, team: str) -> str:
    """
    The stat strip, from the same source as the export card.

    It used to build its own cells with its own labels, which meant the screen
    and the card could disagree about what a number was called -- and did.
    """
    cells = readout.strip(pieces, team)
    inner = "".join(f'<div class="tz-stat"><div class="tz-stat-n">{value}</div>'
                    f'<div class="tz-stat-l">{label}</div></div>'
                    for value, label in cells)
    return f'<div class="tz-strip">{inner}</div>'


def render(match, theme: str) -> None:
    palette = THEMES.get(theme, THEMES["vivid"])
    pieces = setpieces.extract(match)

    players = match.players
    home_id = away_id = 0
    if not players.empty:
        home_rows = players[players["side"] == "home"]
        away_rows = players[players["side"] == "away"]
        home_id = int(home_rows.iloc[0]["team_id"] or 0) if not home_rows.empty else 0
        away_id = int(away_rows.iloc[0]["team_id"] or 0) if not away_rows.empty else 0
    badges.warm([home_id, away_id])

    st.markdown(_identity(match, home_id, away_id), unsafe_allow_html=True)

    if not pieces:
        st.markdown('<p class="tz-empty">No qualifying set-pieces in this match.</p>',
                    unsafe_allow_html=True)
        return

    for team in (match.meta["home_team"], match.meta["away_team"]):
        mine = [p for p in pieces if p.team == team]
        if not mine:
            continue
        st.markdown(f'<div class="tz-sec">{team}</div>', unsafe_allow_html=True)
        st.markdown(_summary(pieces, team), unsafe_allow_html=True)
        if team == match.meta["home_team"]:
            # Printed once, under the first strip. The two fractions there have
            # different denominators and the reader has no way to know that.
            st.markdown(_glossary(), unsafe_allow_html=True)

        drawable = [p for p in mine if p.is_delivery and p.end_x is not None]
        if drawable:
            shots = sum(1 for p in drawable if p.led_to_shot)
            figure = delivery_map(
                drawable, palette,
                subtitle=f"{len(drawable)} deliveries · {shots} led to a shot")
            st.image(to_png(figure), use_container_width=True)

        # Conditional, per section 1. The test must match what the chart
        # actually plots -- testing `contested` alone let a goal-kick duel open
        # a panel that then rendered 0/0, because the chart counts deliveries
        # only and a goal kick is not one.
        #
        # The title carries the team. Rendered inside a per-team loop it is
        # obvious which side it belongs to while you are writing it, and not at
        # all obvious when you are looking at one map on a long page.
        if any(p.is_delivery and p.contested for p in mine):
            st.image(to_png(aerial_zones(mine, palette,
                                         title=f"{team} — Aerial Duels")),
                     use_container_width=True)
        else:
            st.markdown(
                f'<p class="tz-note">{team} contested no set-piece delivery in '
                f'the air, so there is no aerial map for them.</p>',
                unsafe_allow_html=True)

        # Conditional: a side whose every set piece shot came straight off the
        # delivery has no second phase to show.
        if chainable(mine):
            st.image(to_png(chains(mine, palette,
                                   title=f"{team} — Second Phase")),
                     use_container_width=True)

        if any(p.kind == GOAL_KICK for p in mine):
            st.image(to_png(goal_kicks(
                mine, palette, match.meta["home_team"],
                title=f"{team} — Goal Kicks",
                subtitle=charts_caption(mine, team))),
                use_container_width=True)

    _export_panel(match, pieces, theme)

    st.markdown('<div class="tz-sec">Timeline</div>', unsafe_allow_html=True)
    st.image(to_png(timeline(pieces, palette, match.meta["home_team"],
                             match.meta["away_team"],
                             goals=setpieces.match_goals(match),
                             max_minute=int(match.meta.get("max_minute") or 95))),
             use_container_width=True)

    st.markdown('<div class="tz-sec">Ledger</div>', unsafe_allow_html=True)
    st.markdown(_ledger(pieces, match.meta["home_team"]), unsafe_allow_html=True)

    st.markdown('<div class="tz-sec">Report</div>', unsafe_allow_html=True)
    text = readout.report(match, pieces)
    st.code(text, language=None)
    st.download_button("Download report", data=text,
                       file_name=f"trazado-report-"
                                 f"{match.meta.get('match_id') or 'match'}.txt",
                       mime="text/plain", key="dl_report")
