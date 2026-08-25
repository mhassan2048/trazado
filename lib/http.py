"""
One shared WhoScored session.

WhoScored returns 403 to plain requests, so every call goes through curl_cffi
with a Chrome TLS fingerprint. The session is built once and reused: the
warm-up request costs a round trip and a pause, and paying that per fetch would
make the competition chooser unusably slow.
"""

from __future__ import annotations

import os
import random
import threading
import time

BASE = "https://www.whoscored.com"

# Optional proxy, off unless asked for.
#
#   export TRAZADO_PROXY=socks5://127.0.0.1:9050    # Tor, as the Zauberpass
#                                                    # bulk pipeline uses
#
# The matchday scraper this app follows goes direct, and direct is right for
# the common case: section 1 promises every match is fetched fresh, and a proxy
# adds a round trip to every request. But WhoScored rate limits bursts, and a
# shared or datacentre IP gets throttled far harder than a home connection --
# so it is one env var away rather than a code change.
PROXY_ENV = "TRAZADO_PROXY"


def proxy() -> str | None:
    value = os.environ.get(PROXY_ENV, "").strip()
    return value or None


def proxy_status() -> str:
    """One line describing how requests will leave this machine."""
    where = proxy()
    return f"via {where}" if where else "direct (no proxy)"

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
    where = proxy()
    if where:
        made.proxies = {"http": where, "https": where}
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
        retries: int = 3) -> str:
    """
    Fetch a page, backing off and rebuilding the session when refused.

    A 403 poisons the session: every later call on the same connection is
    refused too, so the session is dropped and rebuilt, forcing a new TLS
    handshake and new cookies.

    Backoff is exponential with jitter. On a home connection one retry is
    plenty; from a datacentre address -- which is what a hosted deploy has --
    WhoScored throttles far harder, and a fixed short retry just produces a
    second refusal a moment later.
    """
    headers = {"Referer": referer} if referer else {}
    last = ""
    for attempt in range(retries + 1):
        try:
            response = session().get(url, timeout=timeout, headers=headers)
            status = response.status_code
        except Exception as exc:                      # transport-level failure
            status, last = None, f"{type(exc).__name__}: {exc}"
            response = None

        if status == 200:
            return response.text
        if status is not None:
            last = f"status {status}"

        retryable = status in (403, 429, 500, 502, 503, 504) or status is None
        if retryable and attempt < retries:
            reset()
            time.sleep(min(8.0, 1.5 * (2 ** attempt)) + random.uniform(0, 0.75))
            continue
        break

    hint = ""
    if "403" in last or "429" in last:
        hint = (" WhoScored rate limits bursts and throttles datacentre "
                "addresses hard.")
        if not proxy():
            hint += f" Try routing through a proxy: {PROXY_ENV}=socks5://host:port"
    raise FetchError(f"WhoScored request failed ({last}).{hint}")
