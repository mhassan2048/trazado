"""
Fixtures for the current season, resolved live.

WhoScored addresses a season by a season id and a stage id, both of which roll
over every year. Nothing here is hard coded: a competition's landing page
redirects to whatever season is live, and that page carries three useful
things at once -- the season list with the current one marked selected, the
stage id, and the fixtures for the round being played. So the common case
costs one request.

Browsing to another matchweek uses the month endpoint, which needs the stage id
the landing page just gave us.
"""

from __future__ import annotations

import html as html_module
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import http
from .competitions import Competition
from .http import FetchError, get

# WhoScored's fixture status codes. 6 is a finished match; anything else is
# unplayed, in progress, or abandoned, and carries no set piece data to show.
STATUS_FINISHED = 6

_SEASON_SELECT = re.compile(r'<select id="seasons".*?</select>', re.S)
_OPTION = re.compile(r'<option([^>]*)value="([^"]+)"[^>]*>([^<]+)</option>')
_SEASON_ID = re.compile(r"/Seasons/(\d+)")
_JSON_COMMENT = re.compile(r"<!--(\{.*?\})-->", re.S)


@dataclass(frozen=True)
class Fixture:
    match_id: int
    home: str
    away: str
    home_id: int
    away_id: int
    home_score: int | None
    away_score: int | None
    kickoff: datetime | None
    status: int
    elapsed: str

    @property
    def played(self) -> bool:
        """Only a finished match has set-piece data worth opening."""
        return self.status == STATUS_FINISHED and self.home_score is not None

    @property
    def score(self) -> str:
        if not self.played:
            return ""
        return f"{self.home_score} - {self.away_score}"

    @property
    def day(self) -> str:
        return self.kickoff.strftime("%Y-%m-%d") if self.kickoff else ""


@dataclass(frozen=True)
class Season:
    """The live season for one competition, plus whatever fixtures came free."""
    competition: Competition
    season_id: int
    stage_id: int                # 0 until the competition publishes a stage
    name: str                    # e.g. "2026/2027"
    fixtures: tuple[Fixture, ...]

    @property
    def started(self) -> bool:
        """
        False before a competition publishes any fixtures.

        A season that exists but has no stage is the normal pre-season state --
        the Champions League sits here through the summer. It is a state to
        show, not an error to raise.
        """
        return bool(self.stage_id)

    def month_url(self, year: int, month: int) -> str:
        return (f"https://www.whoscored.com/tournaments/{self.stage_id}"
                f"/data/?d={year}{month:02d}")


def _parse_kickoff(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for form in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw, form)
        except ValueError:
            continue
    return None


def _fixture(raw: dict) -> Fixture | None:
    try:
        return Fixture(
            match_id=int(raw["id"]),
            home=raw.get("homeTeamName", ""),
            away=raw.get("awayTeamName", ""),
            home_id=int(raw.get("homeTeamId") or 0),
            away_id=int(raw.get("awayTeamId") or 0),
            home_score=raw.get("homeScore"),
            away_score=raw.get("awayScore"),
            kickoff=_parse_kickoff(raw.get("startTime")),
            status=int(raw.get("status") or 0),
            elapsed=str(raw.get("elapsed") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _fixtures_from_payload(payload: dict, stage_id: int | None = None) -> list[Fixture]:
    """Pull matches out of a {"tournaments": [...]} payload."""
    out = []
    for tournament in payload.get("tournaments", []) or []:
        if stage_id is not None and tournament.get("stageId") != stage_id:
            continue
        for raw in tournament.get("matches", []) or []:
            built = _fixture(raw)
            if built is not None:
                out.append(built)
    return out


def _embedded_payloads(page: str) -> list[dict]:
    """The landing page carries its fixture payloads inside HTML comments."""
    found = []
    for blob in _JSON_COMMENT.findall(page):
        try:
            parsed = json.loads(blob)
        except ValueError:
            continue
        if isinstance(parsed, dict) and "tournaments" in parsed:
            found.append(parsed)
    return found


def resolve(competition: Competition) -> Season:
    """
    Find the live season for a competition and return it with its current
    fixtures. One request.
    """
    page = get(competition.url)

    # The season <select> is HTML-entity encoded, so unescape before matching.
    unescaped = html_module.unescape(page)
    select = _SEASON_SELECT.search(unescaped)
    season_id, season_name = 0, ""
    if select:
        options = _OPTION.findall(select.group(0))
        chosen = next((o for o in options if "selected" in o[0]), options[0] if options else None)
        if chosen:
            found = _SEASON_ID.search(chosen[1])
            season_id = int(found.group(1)) if found else 0
            season_name = chosen[2].strip()

    payloads = _embedded_payloads(page)
    stage_id, fixtures = 0, []
    for payload in payloads:
        for tournament in payload.get("tournaments", []) or []:
            if tournament.get("tournamentId") != competition.tournament_id:
                continue
            stage_id = int(tournament.get("stageId") or 0)
            season_name = season_name or str(tournament.get("seasonName") or "")
            season_id = season_id or int(tournament.get("seasonId") or 0)
            fixtures = _fixtures_from_payload(payload, stage_id)
            break
        if stage_id:
            break

    if not season_id and not stage_id:
        raise FetchError(
            f"Could not resolve the live season for {competition.name}. "
            "WhoScored may have changed its page structure.")

    return Season(competition=competition, season_id=season_id, stage_id=stage_id,
                  name=season_name, fixtures=tuple(fixtures))


def month(season: Season, when: datetime) -> list[Fixture]:
    """Every fixture in one calendar month. Empty before the season starts."""
    if not season.started:
        return []
    page = get(season.month_url(when.year, when.month), referer=season.competition.url)
    try:
        payload = json.loads(page)
    except ValueError as exc:
        raise FetchError("Fixture endpoint did not return JSON.") from exc
    return _fixtures_from_payload(payload, season.stage_id)


def recent(season: Season, days: int = 10, today: datetime | None = None) -> list[Fixture]:
    """
    Finished fixtures from the last `days`, newest first.

    This is the matchday window: what a person opening Trazado today would
    actually want to look at. It spans the month boundary when it has to.
    """
    if not season.started:
        return []
    now = today or datetime.now()
    start = now - timedelta(days=days)

    seen = {f.match_id: f for f in season.fixtures}
    wanted = sorted({(start.year, start.month), (now.year, now.month)})
    failures = 0
    for year, mon in wanted:
        try:
            for fixture in month(season, datetime(year, mon, 1)):
                seen.setdefault(fixture.match_id, fixture)
        except FetchError:
            failures += 1  # One bad month should not empty the list.

    # But every month failing must not look like a quiet weekend. Without this
    # a rate-limited fetch renders as "no recent matches", which is a claim
    # about the football rather than about the request -- exactly the kind of
    # silent wrongness the project rules out.
    if failures == len(wanted):
        raise FetchError("Could not load fixtures for "
                         f"{season.competition.name}.")

    out = [f for f in seen.values()
           if f.played and f.kickoff and start <= f.kickoff <= now]
    return sorted(out, key=lambda f: f.kickoff, reverse=True)


@dataclass(frozen=True)
class Summary:
    """
    What the competition chooser needs to draw one card.

    `error` carries why a lookup failed, when it did. Swallowing the reason
    into a bare None meant a hosted deploy could show "Coming soon" for a
    competition it simply could not reach -- a claim about the football rather
    than about the request.
    """
    season: Season | None = None
    recent: tuple[Fixture, ...] = ()
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.season is not None and not self.error

    @property
    def started(self) -> bool:
        return bool(self.season and self.season.started)

    @property
    def count(self) -> int:
        return len(self.recent)


def failed(competition: Competition, reason: str) -> "Summary":
    return Summary(season=None, recent=(), error=reason)


def summarise(competition: Competition, days: int = 10,
              today: datetime | None = None) -> Summary:
    """
    Resolve a competition and count what is actually openable right now.

    The count deliberately does not come from the fixtures embedded in the
    landing page. Those are whichever round WhoScored is currently featuring,
    and the moment a round finishes they flip to the next one -- so a league
    that played ten matches this week would report none. Ask the date window
    instead.
    """
    season = resolve(competition)
    return Summary(season=season, recent=tuple(recent(season, days=days, today=today)))


def summarise_all(competitions, days: int = 10,
                  today: datetime | None = None) -> dict[str, "Summary"]:
    """
    Summarise every competition at once.

    Run through `http.politely`: a small pool with a stagger between starts,
    rather than six simultaneous requests. A competition that fails carries its
    reason rather than taking the page down or going silently missing.
    """
    def one(competition):
        try:
            return competition.key, summarise(competition, days=days, today=today)
        except Exception as exc:
            return competition.key, failed(competition, str(exc))

    return dict(http.politely(one, competitions))


def board(season: Season, days: int = 10,
          today: datetime | None = None) -> list[Fixture]:
    """
    What the match chooser shows: recent finished matches, plus the fixtures
    still to come in the round being played.

    The unplayed ones are included deliberately. Section 6 wants them greyed
    and labelled rather than hidden, so that a league mid-round looks like a
    league mid-round instead of looking broken.
    """
    if not season.started:
        return []
    seen = {f.match_id: f for f in recent(season, days=days, today=today)}
    for fixture in season.fixtures:
        seen.setdefault(fixture.match_id, fixture)
    return sorted(seen.values(),
                  key=lambda f: (f.kickoff or datetime.min), reverse=True)


def days_on(fixtures) -> list[str]:
    """Distinct kickoff dates present, newest first."""
    return sorted({f.day for f in fixtures if f.day}, reverse=True)
