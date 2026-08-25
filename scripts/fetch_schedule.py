"""
Fetch the schedule and write data/schedule.json.

Run on a cron from somewhere that is not the app, so the competition chooser
costs no network at all. See .github/workflows/schedule.yml.

Two behaviours matter more than speed:

- **A competition that fails keeps its previous entry.** Overwriting it with
  an error would take a league that was loading fine and blank it because one
  fetch was refused. A stale fixture list is worth more than none.
- **The file only changes when the football does.** Same content produces a
  byte-identical file, so the job has nothing to commit and the history stays
  readable.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import schedule, snapshot                                # noqa: E402
from lib.competitions import COMPETITIONS                         # noqa: E402
from lib.snapshot import _fixture_to_json                         # noqa: E402

ATTEMPTS = int(os.environ.get("TRAZADO_FETCH_ATTEMPTS", "3"))
PAUSE = float(os.environ.get("TRAZADO_FETCH_PAUSE", "20"))


def one(competition) -> dict | None:
    """
    Fetch a competition, retrying patiently.

    A scheduled job can afford to wait in a way a page load cannot: if the
    address is being rate limited, sitting out twenty seconds and asking again
    is free here and impossible in a browser.
    """
    for attempt in range(1, ATTEMPTS + 1):
        try:
            summary = schedule.summarise(competition)
            season = summary.season
            return {
                "season_id": season.season_id,
                "stage_id": season.stage_id,
                "season_name": season.name,
                "fetched_at": snapshot._now().isoformat(timespec="seconds"),
                "fixtures": [_fixture_to_json(f) for f in
                             schedule.board(season)],
                "recent": [_fixture_to_json(f) for f in summary.recent],
            }
        except Exception as exc:
            print(f"  attempt {attempt}/{ATTEMPTS} failed: {str(exc)[:110]}")
            if attempt < ATTEMPTS:
                time.sleep(PAUSE)
    return None


def main() -> int:
    existing = snapshot.read() or {}
    previous = existing.get("competitions", {})

    entries, fresh, kept, lost = {}, 0, 0, 0
    for competition in COMPETITIONS:
        print(f"{competition.name}:")
        got = one(competition)
        if got is not None:
            entries[competition.key] = got
            played = sum(1 for f in got["fixtures"] if f.get("home_score") is not None)
            print(f"  ok — {len(got['fixtures'])} fixtures, {played} played")
            fresh += 1
        elif competition.key in previous:
            entries[competition.key] = previous[competition.key]
            print("  failed — keeping the previous entry")
            kept += 1
        else:
            print("  failed — and nothing previous to keep")
            lost += 1
        time.sleep(1.5)

    if not entries:
        print("\nnothing fetched and nothing to keep; leaving the file alone")
        return 1

    path = snapshot.write(entries)
    print(f"\nwrote {path}: {fresh} fresh, {kept} kept, {lost} missing")
    # Only a total failure is worth failing the job over. A partial fetch has
    # still produced a usable file.
    return 0 if fresh else 1


if __name__ == "__main__":
    raise SystemExit(main())
