"""
Trazado — set piece analysis for a single match.

Match event data is never held between visits; every match is fetched fresh.
The schedule layer -- which season is live, which fixtures exist -- is
navigation metadata and is held briefly so that clicking a theme does not cost
six network requests.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Trazado", page_icon="assets/logo.svg",
                   layout="centered", initial_sidebar_state="collapsed")

from lib import schedule                       # noqa: E402
from lib.competitions import COMPETITIONS      # noqa: E402
from lib.competitions import get as competition_by_key      # noqa: E402
from lib import whoscored                                  # noqa: E402
from ui import analysis, competitions, matches, theme as theming  # noqa: E402
from ui.chrome import header, link             # noqa: E402


# Fifteen minutes, not three. This is navigation metadata -- which season is
# live, which fixtures exist -- and it changes on the timescale of a matchday,
# not a page load. A short TTL meant a hosted deploy re-fetched every few
# minutes and spent its whole rate-limit budget on data that had not moved.
# Section 1 governs match event data, which is still never cached.
@st.cache_data(ttl=900, show_spinner="Checking what has been played…")
def summaries():
    """Which season is live, and how many matches are openable right now."""
    return schedule.summarise_all(COMPETITIONS)


def current_theme() -> str:
    """
    Theme lives in the query string so a shared link keeps its look, and falls
    back to session state so a rerun that drops the param does not flicker.
    """
    asked = st.query_params.get("theme")
    if asked in theming.THEMES:
        st.session_state["theme"] = asked
        return asked
    return st.session_state.get("theme", theming.DEFAULT)


def stub(title: str, detail: str) -> None:
    st.markdown(f'<div class="tz-h1">{title}</div>'
                f'<p class="tz-sub">{detail}</p>', unsafe_allow_html=True)


def main() -> None:
    active = current_theme()
    params = st.query_params

    st.markdown(theming.font_links(), unsafe_allow_html=True)
    st.markdown(theming.css(active), unsafe_allow_html=True)
    match_id = params.get("match")
    competition = params.get("competition")

    # The header is identical on every screen, so it is rendered before the
    # branch rather than inside each one.
    if match_id or competition:
        # Carry the screen's own params through a theme switch, so changing
        # theme never navigates away from the day you were looking at.
        keep = {}
        if competition and not match_id:
            keep["competition"] = competition
            if params.get("day"):
                keep["day"] = params.get("day")
        st.markdown(header(active, **keep), unsafe_allow_html=True)
        st.markdown(
            f'<a class="tz-back" href="{link(theme=active)}" target="_self">'
            f'&larr; competitions</a>', unsafe_allow_html=True)

    if match_id:
        # Fetched fresh every time, per section 1. Nothing is cached here.
        named = competition_by_key(competition) if competition else None
        try:
            with st.spinner("Pulling the match from WhoScored…"):
                match = whoscored.fetch(
                    match_id, competition=named.name if named else "")
        except Exception as exc:
            stub("Could not load this match", str(exc))
            return
        analysis.render(match, active)
        return
    if competition:
        chosen = competition_by_key(competition)
        if chosen is None:
            stub("Unknown competition", "That competition is not one of the six.")
            return
        try:
            live = summaries()
        except Exception:
            live = {}
        matches.render(chosen, live.get(competition), active,
                       day=params.get("day"))
        return

    try:
        live = summaries()
    except Exception:
        live = {}  # The chooser still renders; cards show a dash.
    competitions.render(active, summaries=live)


if __name__ == "__main__":
    main()
