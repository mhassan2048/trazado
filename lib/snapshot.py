"""
The schedule, read from a file instead of the network.

The competition chooser and the fixture list are the expensive part of this
app: eighteen requests in a burst, every one of them navigation metadata that
changes on the timescale of a matchday. A hosted deploy shares an egress
address and gets refused for exactly that pattern.

So a scheduled job fetches it from somewhere else and commits the result, and
the app reads the file. What remains live is opening a match -- one request,
user-triggered, which is a completely different risk profile.

Nothing here fabricates freshness. Every entry carries when it was fetched,
the app shows it, and a stale snapshot falls back to the network rather than
quietly serving old fixtures as current.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .competitions import BY_KEY
from .schedule import Fixture, Season, Summary

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "schedule.json")

# Beyond this the snapshot is treated as a fallback rather than the truth.
# Long enough to cover the overnight gap between scheduled runs, short enough
# that a matchday afternoon never serves yesterday's scores as current.
STALE_HOURS = float(os.environ.get("TRAZADO_SNAPSHOT_STALE_HOURS", "6"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fixture_to_json(f: Fixture) -> dict:
    return {
        "match_id": f.match_id, "home": f.home, "away": f.away,
        "home_id": f.home_id, "away_id": f.away_id,
        "home_score": f.home_score, "away_score": f.away_score,
        "kickoff": f.kickoff.isoformat() if f.kickoff else None,
        "status": f.status, "elapsed": f.elapsed,
    }


def _fixture_from_json(d: dict) -> Fixture:
    kickoff = d.get("kickoff")
    return Fixture(
        match_id=int(d["match_id"]), home=d.get("home", ""), away=d.get("away", ""),
        home_id=int(d.get("home_id") or 0), away_id=int(d.get("away_id") or 0),
        home_score=d.get("home_score"), away_score=d.get("away_score"),
        kickoff=datetime.fromisoformat(kickoff) if kickoff else None,
        status=int(d.get("status") or 0), elapsed=str(d.get("elapsed") or ""))


def write(entries: dict[str, dict], path: str = PATH) -> str:
    """
    Write the snapshot. `entries` maps competition key to its payload.

    Sorted and stably formatted so an unchanged fetch produces an identical
    file and the scheduled job has nothing to commit.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"fetched_at": _now().isoformat(timespec="seconds"),
               "competitions": dict(sorted(entries.items()))}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    return path


def read(path: str = PATH) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) and data.get("competitions") else None


def age_hours(data: dict | None) -> float | None:
    stamp = _parse((data or {}).get("fetched_at"))
    if stamp is None:
        return None
    return (_now() - stamp).total_seconds() / 3600.0


def fetched_at(data: dict | None) -> datetime | None:
    return _parse((data or {}).get("fetched_at"))


def is_fresh(data: dict | None) -> bool:
    age = age_hours(data)
    return age is not None and age <= STALE_HOURS


def to_summaries(data: dict) -> dict[str, Summary]:
    """Rebuild what the chooser expects from the stored payload."""
    out: dict[str, Summary] = {}
    for key, entry in (data.get("competitions") or {}).items():
        competition = BY_KEY.get(key)
        if competition is None:
            continue
        season = Season(
            competition=competition,
            season_id=int(entry.get("season_id") or 0),
            stage_id=int(entry.get("stage_id") or 0),
            name=str(entry.get("season_name") or ""),
            fixtures=tuple(_fixture_from_json(f) for f in entry.get("fixtures", [])),
        )
        recent = tuple(_fixture_from_json(f) for f in entry.get("recent", []))
        out[key] = Summary(season=season, recent=recent,
                           error=str(entry.get("error") or ""))
    return out
