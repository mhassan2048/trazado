"""The match chooser: fixtures for one competition, grouped by day."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from lib import badges, schedule

from .chrome import data_uri, link


def _crest(team_id: int, name: str) -> str:
    """
    A club crest, or a monogram when the feed has no badge for that id.

    The monogram exists because a missing crest must still occupy the same
    space -- a card that silently loses its badge looks broken, and a wrong
    badge would be worse than either.
    """
    src = badges.url(team_id)
    if src:
        return f'<img class="tz-crest" src="{src}" alt="">'
    initials = "".join(word[0] for word in name.split()[:2]).upper() or "?"
    return f'<div class="tz-mono-crest" aria-hidden="true">{initials}</div>'


def _fixture(fix, competition_key: str, theme: str) -> str:
    home = _crest(fix.home_id, fix.home)
    away = _crest(fix.away_id, fix.away)

    if fix.played:
        middle = f'<div class="tz-result">{fix.score}</div>'
        # Only a finished match has anything to analyse, so only it is a link.
        return f"""
<a class="tz-fix" href="{link(match=fix.match_id, competition=competition_key, theme=theme)}"
   target="_self" aria-label="{fix.home} {fix.score} {fix.away}">
  <div class="tz-side">{home}<div class="tz-team">{fix.home}</div></div>
  {middle}
  <div class="tz-side tz-side--away"><div class="tz-team">{fix.away}</div>{away}</div>
</a>"""

    when = fix.kickoff.strftime("%H:%M") if fix.kickoff else "not played"
    return f"""
<div class="tz-fix tz-fix--off">
  <div class="tz-side">{home}<div class="tz-team">{fix.home}</div></div>
  <div class="tz-kick">{when}</div>
  <div class="tz-side tz-side--away"><div class="tz-team">{fix.away}</div>{away}</div>
</div>"""


ALL = "all"


def default_day(days: list[str], today: datetime | None = None) -> str | None:
    """
    The date a matchday app should open on: the most recent one that has
    already happened.

    Landing on "All" meant scrolling past next weekend's unplayed fixtures to
    reach the football that was actually played. Falls forward to the nearest
    upcoming date when nothing has been played yet -- a competition mid
    pre-season still has to show something.
    """
    if not days:
        return None
    now = (today or datetime.now()).strftime("%Y-%m-%d")
    past = [d for d in days if d <= now]
    return max(past) if past else min(days)


def _chips(days: list[str], active: str | None, competition_key: str, theme: str) -> str:
    def chip(value: str | None, label: str) -> str:
        selected = (value or ALL) == (active or ALL)
        return (f'<a href="{link(competition=competition_key, day=value or ALL, theme=theme)}" '
                f'target="_self" aria-current="{str(selected).lower()}">{label}</a>')

    out = [chip(ALL, "All")]
    for day in days:
        shown = datetime.strptime(day, "%Y-%m-%d").strftime("%a %d %b")
        out.append(chip(day, shown))
    return f'<div class="tz-chips">{"".join(out)}</div>'


def render(competition, summary, theme: str, day: str | None = None) -> None:
    logo = data_uri("leagues/" + competition.logo)
    season_name = summary.season_name if summary else ""
    st.markdown(
        f'<div class="tz-league">'
        f'  <div class="tz-chip"><img src="{logo}" alt=""></div>'
        f'  <h2>{competition.name}</h2>'
        f'</div>'
        f'<div class="tz-season">{season_name}</div>',
        unsafe_allow_html=True)

    if summary is None or not summary.ok:
        why = (summary.error if summary is not None and summary.error else "")
        st.markdown(
            '<p class="tz-empty">Could not reach WhoScored for this '
            'competition. Reload to try again.'
            + (f'<span class="tz-why">{why}</span>' if why else "")
            + '</p>', unsafe_allow_html=True)
        return
    if not summary.started:
        st.markdown('<p class="tz-empty">This competition has not started. '
                    'There are no fixtures to show yet.</p>', unsafe_allow_html=True)
        return

    try:
        fixtures = schedule.board(summary.season)
    except Exception:
        st.markdown('<p class="tz-empty">Could not load fixtures just now. '
                    'Reload in a moment.</p>', unsafe_allow_html=True)
        return
    if not fixtures:
        st.markdown('<p class="tz-empty">No matches in the last ten days.</p>',
                    unsafe_allow_html=True)
        return

    days = schedule.days_on(fixtures)
    # No day in the URL means a fresh visit, which opens on the most recent
    # date played. An explicit "all" is how you ask for everything; a stale
    # date falls back to the same default rather than showing nothing.
    if day == ALL:
        day = None
    elif day is None or day not in days:
        day = default_day(days)
    st.markdown(_chips(days, day, competition.key, theme), unsafe_allow_html=True)

    shown = [f for f in fixtures if not day or f.day == day]
    badges.warm([f.home_id for f in shown] + [f.away_id for f in shown])

    blocks = []
    for value in [d for d in days if not day or d == day]:
        of_day = [f for f in shown if f.day == value]
        if not of_day:
            continue
        heading = datetime.strptime(value, "%Y-%m-%d").strftime("%A %d %B")
        cards = "".join(_fixture(f, competition.key, theme) for f in of_day)
        blocks.append(f'<div class="tz-dayhead">{heading}</div>'
                      f'<div class="tz-fixtures">{cards}</div>')
    st.markdown("".join(blocks), unsafe_allow_html=True)
