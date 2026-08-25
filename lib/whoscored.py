"""
WhoScored match fetch and parse for Trazado.

Differs from the Zauberpass matchday scraper in three ways that matter here:

1. The raw qualifier list is preserved on every event. The Zauberpass scraper
   builds the full qualifier map and then keeps only a whitelist of ~40
   booleans, which discards ThrowIn, GoalKick, IndirectFreekickTaken, Length,
   Angle, the shot-situation tags and the whole goalkeeper vocabulary. All of
   those are load bearing for set-piece work.
2. Squad data is returned alongside events. WhoScored carries height, weight,
   position, shirt number and starting XI in the match blob, so aerial
   profiling needs no external identity source.
3. No xT, no progressive-pass metrics, no synthetic carry events. Trazado shows
   no xG or xT, and synthetic carries would sit between a delivery and its
   first contact and corrupt the chain.

Nothing here caches. `from_file` exists for development against a saved blob;
the app must always call `fetch`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .http import BASE, FetchError, get as http_get
from .qualifiers import NUMERIC, SHOT_TYPES

_MATCH_VARS = (
    "matchCentreData",
    "initialMatchDataForScorers",
    "matchCentreEventTypeJson",
    "matchCentreEventData",
    "matchCentreEventsData",
    "matchData",
    "matchCentreJsonData",
)

_PERIODS = {
    1: "FirstHalf", 2: "SecondHalf",
    3: "ExtraTimeFirstHalf", 4: "ExtraTimeSecondHalf",
    5: "PenaltyShootout",
}

# Rank, not name, decides order. Sorting periods alphabetically puts
# ExtraTimeFirstHalf before FirstHalf.
_PERIOD_RANK = {
    "FirstHalf": 1, "SecondHalf": 2,
    "ExtraTimeFirstHalf": 3, "FirstPeriodOfExtraTime": 3,
    "ExtraTimeSecondHalf": 4, "SecondPeriodOfExtraTime": 4,
    "PenaltyShootout": 5,
}
_VALID_PERIODS = frozenset(_PERIOD_RANK)


class WhoScoredError(FetchError):
    """Raised when a match cannot be fetched or parsed."""


@dataclass
class Match:
    """One match: events, squads, and the identity needed to label a graphic."""

    events: pd.DataFrame
    players: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def home(self) -> str:
        return self.meta.get("home_team", "")

    @property
    def away(self) -> str:
        return self.meta.get("away_team", "")

    def height(self, player: str) -> int | None:
        """Height in cm, or None where the feed omits it."""
        row = self.players[self.players["player"] == player]
        if row.empty:
            return None
        value = row.iloc[0]["height"]
        return None if pd.isna(value) else int(value)

    def __repr__(self) -> str:
        return (f"<Match {self.meta.get('match_name', '?')} "
                f"{self.meta.get('score', '?')} — {len(self.events)} events>")


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def parse_match_input(raw: str) -> int | None:
    """Accept a WhoScored URL or a bare match id. Return the id, or None."""
    text = str(raw).strip()
    if text.isdigit():
        return int(text)
    found = re.search(r"/Matches/(\d+)", text)
    return int(found.group(1)) if found else None


def _flatten_qualifiers(raw: list) -> dict[str, Any]:
    """
    Collapse the qualifier list into {displayName: value}.

    Value-less qualifiers map to True so membership and truth tests behave the
    same way. Numeric qualifiers are cast; a malformed one is dropped rather
    than poisoning the column dtype.
    """
    out: dict[str, Any] = {}
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        qtype = item.get("type") or {}
        name = qtype.get("displayName") if isinstance(qtype, dict) else str(qtype)
        if not name:
            continue
        value = item.get("value", item.get("qualifierValue"))
        if value is None or value == "":
            out[name] = True
        elif name in NUMERIC:
            try:
                out[name] = float(value)
            except (TypeError, ValueError):
                out[name] = value
        else:
            out[name] = value
    return out


def _first(quals: dict, names) -> str:
    """Return the first qualifier from `names` present on this event."""
    for name in names:
        if name in quals:
            return name
    return ""


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def _period_name(raw: Any) -> str:
    if isinstance(raw, dict):
        return raw.get("displayName") or _PERIODS.get(int(raw.get("value", 1)), "FirstHalf")
    try:
        return _PERIODS.get(int(raw), "FirstHalf")
    except (TypeError, ValueError):
        return str(raw)


def _positive(value: Any) -> float | None:
    """WhoScored writes 0 for an unknown height or weight. Read that as missing."""
    number = _num(value)
    return number if number and number > 0 else None


def _squad(side: dict, field_name: str, names: dict) -> list[dict]:
    rows = []
    for player in side.get("players", []) or []:
        pid = str(player.get("playerId") or player.get("id") or "")
        rows.append({
            "player_id": pid,
            "player": names.get(pid) or player.get("name") or "",
            "team": side.get("name") or side.get("teamName") or "",
            "team_id": side.get("teamId"),
            "side": field_name,
            "position": player.get("position") or "",
            "shirt_no": player.get("shirtNo"),
            "height": _positive(player.get("height")),
            "weight": _positive(player.get("weight")),
            "age": player.get("age"),
            "started": bool(player.get("isFirstEleven")),
            "is_keeper": (player.get("position") or "").upper() in ("GK", "GOALKEEPER"),
        })
    return rows


def parse(blob: dict, match_id: int | None = None, competition: str = "") -> Match:
    """Turn a raw matchCentreData dict into a Match."""
    if not isinstance(blob, dict):
        raise WhoScoredError("Match data is absent — the fixture is probably unplayed.")
    events = blob.get("events") or blob.get("matchEvents") or []
    if not events:
        raise WhoScoredError("Event list is empty.")

    names = {str(k): v for k, v in (blob.get("playerIdNameDictionary") or {}).items()}
    home = blob.get("home") or blob.get("homeTeam") or {}
    away = blob.get("away") or blob.get("awayTeam") or {}

    players = pd.DataFrame(_squad(home, "home", names) + _squad(away, "away", names))
    player_team = dict(zip(players["player_id"], players["team"])) if not players.empty else {}
    keepers = set(players.loc[players["is_keeper"], "player"]) if not players.empty else set()

    home_name = home.get("name") or home.get("teamName") or "Home"
    away_name = away.get("name") or away.get("teamName") or "Away"

    rows = []
    for order, event in enumerate(events):
        period = _period_name(event.get("period", 1))
        if period not in _VALID_PERIODS:
            continue

        etype = event.get("type") or {}
        outcome = event.get("outcomeType") or {}
        type_name = etype.get("displayName", "Unknown") if isinstance(etype, dict) else str(etype)
        outcome_name = outcome.get("displayName", "") if isinstance(outcome, dict) else str(outcome)

        quals = _flatten_qualifiers(event.get("qualifiers", []))
        pid = str(event.get("playerId", "") or "")
        team = player_team.get(pid, "")

        rows.append({
            # identity and clock
            "feed_order": order,
            "event_id": event.get("eventId"),
            "uid": event.get("id"),
            "related_event_id": event.get("relatedEventId"),
            "related_player_id": event.get("relatedPlayerId"),
            "minute": int(event.get("minute") or 0),
            "second": int(event.get("second") or 0),
            "expanded_minute": event.get("expandedMinute"),
            "period": period,
            # actor
            "team": team,
            "team_id": event.get("teamId"),
            "is_home": team == home_name,
            "player": names.get(pid, "") or event.get("playerName", "") or "",
            "player_id": pid,
            "is_keeper": (names.get(pid, "") in keepers),
            # core
            "type": type_name,
            "outcome": outcome_name,
            "success": outcome_name == "Successful",
            "x": _num(event.get("x")),
            "y": _num(event.get("y")),
            "end_x": _num(event.get("endX")),
            "end_y": _num(event.get("endY")),
            "is_touch": bool(event.get("isTouch")),
            "is_shot": bool(event.get("isShot")) or type_name in SHOT_TYPES,
            "is_goal": bool(event.get("isGoal")),
            "card_type": (event.get("cardType") or {}).get("displayName")
                         if isinstance(event.get("cardType"), dict) else event.get("cardType"),
            # shot detail
            "goal_mouth_y": _num(event.get("goalMouthY") or quals.get("GoalMouthY")),
            "goal_mouth_z": _num(event.get("goalMouthZ") or quals.get("GoalMouthZ")),
            "blocked_x": _num(event.get("blockedX") or quals.get("BlockedX")),
            "blocked_y": _num(event.get("blockedY") or quals.get("BlockedY")),
            # delivery detail
            "pass_length": quals.get("Length"),
            "pass_angle": quals.get("Angle"),
            "zone": quals.get("Zone"),
            # the escape hatch: everything, untouched
            "qualifiers": quals,
        })

    if not rows:
        raise WhoScoredError("No events survived parsing.")

    frame = pd.DataFrame(rows)
    frame["period_rank"] = frame["period"].map(_PERIOD_RANK)
    frame = frame.sort_values(
        ["period_rank", "minute", "second", "feed_order"], kind="stable")
    frame = frame.reset_index(drop=True)
    frame["seq"] = frame.index

    scores = _score(blob.get("score"))
    meta = {
        "match_id": match_id,
        "competition": competition,
        "home_team": home_name,
        "away_team": away_name,
        "home_team_id": home.get("teamId"),
        "away_team_id": away.get("teamId"),
        "match_name": f"{home_name} vs {away_name}",
        "score": scores,
        "ft_score": _score(blob.get("ftScore")) or scores,
        "ht_score": _score(blob.get("htScore")),
        "et_score": _score(blob.get("etScore")),
        "pk_score": _score(blob.get("pkScore")),
        "home_goals": (home.get("scores") or {}).get("fulltime"),
        "away_goals": (away.get("scores") or {}).get("fulltime"),
        "start_date": blob.get("startDate"),
        "start_time": blob.get("startTime"),
        "venue": blob.get("venueName"),
        "attendance": blob.get("attendance"),
        "referee": _referee(blob.get("referee")),
        "home_manager": home.get("managerName"),
        "away_manager": away.get("managerName"),
        "home_formations": _formations(home),
        "away_formations": _formations(away),
        "max_minute": blob.get("maxMinute"),
        "elapsed": blob.get("elapsed"),
    }
    return Match(events=frame, players=players, meta=meta)


def _score(raw: Any) -> str:
    """
    Normalise a scoreline to "4 - 2".

    WhoScored writes "4 : 2". A colon reads as a ratio or a time; football
    scores are written with a dash, and every surface in this app shows the
    same string.
    """
    text = str(raw or "").strip()
    return text.replace(" : ", " - ").replace(":", " - ") if text else ""


def _referee(raw: Any) -> str:
    if isinstance(raw, dict):
        return " ".join(p for p in (raw.get("firstName"), raw.get("lastName")) if p)
    return str(raw or "")


def _formations(side: dict) -> list[dict]:
    """Formation shape and the minute window it held for."""
    out = []
    for item in side.get("formations", []) or []:
        out.append({
            "name": item.get("formationName"),
            "start": item.get("startMinuteExpanded"),
            "end": item.get("endMinuteExpanded"),
            "player_ids": item.get("playerIds"),
            "captain_id": item.get("captainPlayerId"),
        })
    return out


# ---------------------------------------------------------------------------
# fetching
# ---------------------------------------------------------------------------

def _extract_json_object(text: str, start: int) -> str | None:
    """Walk braces from `start` and return the balanced object, string-aware."""
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        char = text[idx]
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]
    return None


def _find_blob(html: str) -> dict | None:
    for var in _MATCH_VARS:
        for sep in (f"{var} = {{", f"{var}={{", f"{var}: {{", f"{var}:{{"):
            at = html.find(sep)
            if at == -1:
                continue
            raw = _extract_json_object(html, html.index("{", at))
            if not raw:
                continue
            try:
                candidate = json.loads(raw)
            except ValueError:
                continue
            if len(candidate.get("events") or candidate.get("matchEvents") or []) > 5:
                return candidate
    # Fall back to locating the events array and walking back to its container.
    for hit in re.finditer(r'"events"\s*:\s*\[', html):
        window_start = max(0, hit.start() - 2000)
        brace = html[window_start:hit.start()].rfind("{")
        if brace == -1:
            continue
        raw = _extract_json_object(html, window_start + brace)
        if not raw:
            continue
        try:
            candidate = json.loads(raw)
        except ValueError:
            continue
        if len(candidate.get("events") or candidate.get("matchEvents") or []) > 5:
            return candidate
    return None


def fetch(match: str | int, competition: str = "", timeout: int = 30) -> Match:
    """
    Fetch a match live from WhoScored. Nothing is written to disk.

    `match` is a match id or a WhoScored URL.
    """
    match_id = parse_match_input(match)
    if match_id is None:
        raise WhoScoredError(f"Could not read a match id from {match!r}")

    page = http_get(f"{BASE}/Matches/{match_id}/Live", timeout=timeout)
    blob = _find_blob(page)
    if blob is None:
        raise WhoScoredError("Could not locate event data in the page source.")
    return parse(blob, match_id=match_id, competition=competition)


def from_file(path: str, competition: str = "") -> Match:
    """
    Parse a saved matchCentreData blob. Development only.

    The app fetches every match fresh; this exists so the classifier and the
    visuals can be built and tested without repeatedly hitting WhoScored.
    """
    with open(path, encoding="utf-8") as handle:
        blob = json.load(handle)
    found = re.search(r"(\d+)", os.path.basename(path))
    return parse(blob, match_id=int(found.group(1)) if found else None,
                 competition=competition)
