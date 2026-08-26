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

from lib import schedule, snapshot             # noqa: E402
from lib.competitions import COMPETITIONS      # noqa: E402
from lib.competitions import get as competition_by_key      # noqa: E402
from lib import whoscored                                  # noqa: E402
from ui import analysis, competitions, matches, theme as theming  # noqa: E402
from ui.chrome import header, link             # noqa: E402


# The schedule comes from a committed snapshot, refreshed by a scheduled job
# rather than by whoever happens to load the page. The chooser and the fixture
# list then cost no network at all, which is the whole eighteen-request burst
# that a shared hosting address gets refused for.
#
# Live fetching stays as the fallback: if the snapshot is missing or older than
# a few hours, try the network, and fall back to the stale file if that fails
# too. A broken scheduled job degrades to the old behaviour rather than to an
# empty app. Section 1 governs match event data, which is never cached.
@st.cache_data(ttl=900, show_spinner="Checking what has been played…")
def summaries():
    """
    Which season is live, how many matches are openable, and where that came
    from -- returned together so the two cannot disagree.

    Deriving the note separately got this exactly backwards. A stale snapshot
    served through the fallback below came out with no stamp at all, because
    the note only spoke up when the snapshot was fresh. That is the one case
    where saying when matters most: old fixtures presented silently read as
    current ones.
    """
    data = snapshot.read()
    if snapshot.is_fresh(data):
        return snapshot.to_summaries(data), _stamp(data)

    # summarise_all does not raise when a competition is refused -- it returns
    # a summary carrying the reason. So "did the live fetch work" is a
    # question about how many competitions came back usable, not about
    # whether an exception escaped. Relying on the exception meant a refused
    # deploy would render six Unavailable cards while a perfectly good, if
    # older, snapshot sat unread on disk.
    try:
        live = schedule.summarise_all(COMPETITIONS)
    except Exception:
        live = {}
    stored = snapshot.to_summaries(data) if data else {}

    usable = sum(1 for s in live.values() if s.ok)
    kept = sum(1 for s in stored.values() if s.ok)
    # Serve whichever shows the reader more competitions, and say when it is
    # the older one. A complete set of yesterday's fixtures beats two live
    # leagues and four dashes.
    if usable and usable >= kept:
        return live, ""
    if kept:
        return stored, _stamp(data)
    return live, ""


def _stamp(data) -> str:
    """The "as of" line for a snapshot we are actually serving."""
    stamp = snapshot.fetched_at(data)
    return stamp.strftime("Fixtures as of %d %b, %H:%M UTC") if stamp else ""


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
        # Carry every param that identifies the current screen through a theme
        # switch. Built from the query string rather than listed by hand: the
        # hand-written version dropped `match`, so changing theme on a match
        # threw you back to the competition list, and any param added later
        # would have been dropped the same way.
        keep = {k: v for k, v in params.items() if k != "theme" and v}
        st.markdown(header(active, **keep), unsafe_allow_html=True)
        st.markdown(
            f'<a class="tz-back" href="{link(theme=active)}" target="_self">'
            f'&larr; competitions</a>', unsafe_allow_html=True)

    if match_id:
        # Fetched fresh every time, per section 1. Nothing is cached here.
        named = competition_by_key(competition) if competition else None
        try:
            with st.spinner("Loading match…"):
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
            live, _ = summaries()
        except Exception:
            live = {}
        matches.render(chosen, live.get(competition), active,
                       day=params.get("day"))
        return

    try:
        live, note = summaries()
    except Exception:
        live, note = {}, ""  # The chooser still renders; cards show a dash.
    competitions.render(active, summaries=live, note=note)


if __name__ == "__main__":
    main()
