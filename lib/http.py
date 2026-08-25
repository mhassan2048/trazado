"""
One shared WhoScored session.

WhoScored returns 403 to plain requests, so every call goes through curl_cffi
with a Chrome TLS fingerprint. The session is built once and reused: the
warm-up request costs a round trip and a pause, and paying that per fetch would
make the competition chooser unusably slow.
"""

from __future__ import annotations

import threading
import time

BASE = "https://www.whoscored.com"

# curl_cffi sessions are not safe to share across threads, and the competition
# chooser resolves six competitions at once. Each thread gets its own, built
# on first use and reused thereafter.
_local = threading.local()


class FetchError(RuntimeError):
    """A WhoScored request failed."""


def session():
    existing = getattr(_local, "session", None)
    if existing is not None:
        return existing
    try:
        from curl_cffi import requests
    except ImportError as exc:
        raise FetchError(
            "curl_cffi is required; WhoScored blocks plain requests. "
            "Install it with: pip install curl_cffi"
        ) from exc
    made = requests.Session(impersonate="chrome120")
    try:
        made.get(BASE, timeout=15)
        time.sleep(0.6)
    except Exception:
        pass  # A failed warm-up is not fatal; the real request may still pass.
    _local.session = made
    return made


def reset() -> None:
    """Drop this thread's session so the next call builds a fresh one."""
    _local.session = None


def get(url: str, *, referer: str | None = None, timeout: int = 30,
        retries: int = 1) -> str:
    """
    Fetch a page, rebuilding the session once if WhoScored refuses.

    A 403 poisons the session: every later call on the same connection is
    refused too, so without this the app stays broken until the process
    restarts. Dropping it forces a new TLS handshake and new cookies.
    """
    headers = {"Referer": referer} if referer else {}
    for attempt in range(retries + 1):
        response = session().get(url, timeout=timeout, headers=headers)
        if response.status_code == 200:
            return response.text
        if response.status_code == 403 and attempt < retries:
            reset()
            time.sleep(2.0)
            continue
        if response.status_code == 403:
            raise FetchError(
                "WhoScored refused the request (403). It rate limits bursts; "
                "wait a moment and try again.")
        raise FetchError(f"WhoScored returned status {response.status_code}.")
    raise FetchError("WhoScored refused the request (403).")
