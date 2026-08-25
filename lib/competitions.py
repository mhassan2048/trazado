"""
The six competitions Trazado covers.

Only `region_id` and `tournament_id` are stored. They are stable for the life
of a competition. Season and stage ids change every year, so they are resolved
at run time by `lib.schedule` -- hard coding them means the app quietly breaks
each August. It is only ever the current season; Trazado has no interest in
past ones.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Competition:
    key: str            # our slug, and the query param value
    name: str           # as shown; no country name, per the spec
    logo: str           # file under assets/leagues
    region_id: int
    tournament_id: int

    @property
    def url(self) -> str:
        """The competition's landing page, which redirects to the live season."""
        return (f"https://www.whoscored.com/Regions/{self.region_id}"
                f"/Tournaments/{self.tournament_id}")


COMPETITIONS: tuple[Competition, ...] = (
    Competition("epl", "Premier League", "epl.png", 252, 2),
    Competition("laliga", "La Liga", "laliga.png", 206, 4),
    Competition("seriea", "Serie A", "seriea.png", 108, 5),
    Competition("bundesliga", "Bundesliga", "bundesliga.png", 81, 3),
    Competition("ligue1", "Ligue 1", "ligue1.png", 74, 22),
    Competition("ucl", "Champions League", "ucl.png", 250, 12),
)

BY_KEY = {c.key: c for c in COMPETITIONS}


def get(key: str) -> Competition | None:
    return BY_KEY.get(key)
