"""The competition chooser: six cards, then a direct match lookup."""

from __future__ import annotations

from collections import Counter

import streamlit as st

from lib.competitions import COMPETITIONS
from lib.whoscored import parse_match_input

from .chrome import data_uri, header, link


def _meta(summary) -> str:
    """
    The line under the league name.

    Three states. Either there are matches to open, or there are not, or we
    could not find out. A competition with no published stage and one whose
    window happens to be empty are the same thing to a reader -- nothing to
    click yet -- so they say the same thing. A failed lookup shows a dash
    rather than a zero, because zero would be a claim we cannot make.
    """
    if summary is None:
        return '<div class="tz-count tz-count--unknown">&mdash;</div>'
    if not summary.started or not summary.count:
        return '<div class="tz-count tz-count--unknown">Coming soon</div>'
    return f'<div class="tz-count">{summary.count} matches</div>'


def _card(comp, summary, theme: str) -> str:
    """
    One competition card.

    A competition with nothing to open is not a link. That covers a season
    that has not started and one whose window is empty. A competition we
    simply failed to reach stays clickable -- we cannot claim it is empty, and
    clicking is how you retry.
    """
    inner = (f'<div class="tz-row">'
             f'<div class="tz-chip"><img src="{data_uri("leagues/" + comp.logo)}" alt=""></div>'
             f'<div class="tz-name">{comp.name}</div>'
             f'</div>{_meta(summary)}')

    empty = summary is not None and (not summary.started or not summary.count)
    if empty:
        return f'<div class="tz-card tz-card--off">{inner}</div>'

    # The anchor's only text sits in nested divs, which leaves it unnamed in the
    # accessibility tree. Label it explicitly. Theme rides along so a shared
    # link keeps the look it was shared in.
    return (f'<a class="tz-card" href="{link(competition=comp.key, theme=theme)}" '
            f'target="_self" aria-label="{comp.name}">{inner}</a>')


def _short_season(name: str) -> str:
    """
    WhoScored writes "2026/2027". We show "2026-27".

    A competition played inside one calendar year comes through as a bare
    "2026" and is left alone.
    """
    if "/" not in name:
        return name.strip()
    first, _, second = name.partition("/")
    first, second = first.strip(), second.strip()
    if len(first) == 4 and len(second) == 4 and first.isdigit() and second.isdigit():
        return f"{first}-{second[2:]}"
    return f"{first}-{second}"


def _season_label(summaries: dict) -> str:
    """
    The season every competition is currently in.

    Taken from what actually resolved rather than from a constant, so it is
    right the day the season rolls over. If the six ever disagree -- a
    competition spanning a calendar year differently -- the most common one
    wins and the heading stays a single clean line.
    """
    names = [s.season.name for s in summaries.values() if s and s.season.name]
    if not names:
        return ""
    return _short_season(Counter(names).most_common(1)[0][0])


def render(theme: str, summaries: dict | None = None) -> None:
    summaries = summaries or {}
    st.markdown(header(theme), unsafe_allow_html=True)
    season = _season_label(summaries)
    st.markdown(
        f'<div class="tz-h1">{season or "This Season"}</div>'
        '<p class="tz-sub">Set-Piece Analysis</p>',
        unsafe_allow_html=True,
    )

    cards = "".join(_card(c, summaries.get(c.key), theme) for c in COMPETITIONS)
    st.markdown(f'<div class="tz-grid">{cards}</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="tz-or"><i></i><span>Or Go Straight To A Match</span><i></i></div>',
        unsafe_allow_html=True,
    )

    field, action = st.columns([3, 1], gap="small")
    with field:
        raw = st.text_input("Match", key="lookup",
                            placeholder="Paste a match URL or ID",
                            label_visibility="collapsed")
    with action:
        go = st.button("Open", key="lookup_go", use_container_width=True)

    if go or raw:
        match_id = parse_match_input(raw) if raw else None
        if raw and match_id is None:
            st.markdown(
                '<div class="tz-error">Not a WhoScored match URL or ID.</div>',
                unsafe_allow_html=True)
        elif match_id is not None and go:
            st.query_params.update({"match": str(match_id), "theme": theme})
            st.rerun()

    st.markdown('<p class="tz-note">by '
                '<a class="tz-by" href="https://x.com/mhassanfootball" '
                'target="_blank" rel="noopener">@mhassanfootball</a></p>',
                unsafe_allow_html=True)
