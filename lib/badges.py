"""
Club crests, by team id.

Fetched from WhoScored's own asset host and keyed on the same `teamId` that
arrives with every fixture, so there is no name matching anywhere in the path.
That matters: matching WhoScored's team names against a third-party logo
catalogue by slug resolves 81% exactly, and the fuzzy remainder is actively
wrong -- Leeds resolves to Lewes, Alaves to a Peruvian club. A silently wrong
crest is worse than no crest, so this route does not guess.

The trade is resolution: these are 70px or 80px, fine for a fixture card but
not for a large export crest. If exports need bigger, that wants a hand
verified mapping to a high-resolution catalogue, not an automated one.

Crests do not change, so each is written to `assets/clubs` on first use. That
is an asset cache, not match data -- section 1 governs the analysis, which is
always fetched fresh.
"""

from __future__ import annotations

import base64
import os
import threading

from .http import session

CDN = "https://d2zywfiolv4f83.cloudfront.net/img/teams"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Streamlit serves ./static at /app/static, so crests live there and are
# referenced by URL rather than embedded. See `url()` below.
STORE = os.path.join(ROOT, "static", "clubs")
URL_BASE = "app/static/clubs"

_lock = threading.Lock()
_memory: dict[int, bytes | None] = {}


def _path(team_id: int) -> str:
    return os.path.join(STORE, f"{team_id}.png")


def fetch(team_id: int) -> bytes | None:
    """One crest. Returns None when the id has no badge, without raising."""
    team_id = int(team_id)
    if team_id <= 0:
        return None

    with _lock:
        if team_id in _memory:
            return _memory[team_id]

    path = _path(team_id)
    if os.path.exists(path):
        with open(path, "rb") as handle:
            data = handle.read()
        with _lock:
            _memory[team_id] = data
        return data

    try:
        response = session().get(f"{CDN}/{team_id}.png", timeout=15)
        data = response.content if response.status_code == 200 else None
        if data and not data.startswith(b"\x89PNG"):
            data = None  # An error page dressed as a 200.
    except Exception:
        data = None

    if data:
        os.makedirs(STORE, exist_ok=True)
        tmp = f"{path}.{os.getpid()}.part"
        with open(tmp, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)  # Atomic, so a torn write is never read back.

    with _lock:
        _memory[team_id] = data
    return data


def warm(team_ids) -> None:
    """
    Pre-fetch a page's worth of crests in parallel.

    A fixture list needs about twenty. Sequentially that is a visible stall;
    in parallel it is not.
    """
    missing = [int(t) for t in set(team_ids)
               if int(t) > 0 and int(t) not in _memory and not os.path.exists(_path(int(t)))]
    if not missing:
        return
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(8, len(missing))) as pool:
        list(pool.map(fetch, missing))


def url(team_id: int) -> str:
    """
    Served URL for a crest, or "" when there is none.

    Preferred over `uri`: a fixture list repeats the same crests across rows,
    and inlining them made a single markdown payload large enough that
    Streamlit silently rendered nothing.
    """
    return f"{URL_BASE}/{int(team_id)}.png" if fetch(team_id) else ""


def uri(team_id: int) -> str:
    """Data URI. For the export renderer, which has no server to fetch from."""
    data = fetch(team_id)
    if not data:
        return ""
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
