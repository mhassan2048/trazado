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

# How hard we are willing to hit WhoScored at once. Two is deliberate: a
# hosted deploy shares a datacentre egress IP and six simultaneous requests
# from that pool reads as abuse regardless of what this app is doing.
MAX_PARALLEL = int(os.environ.get("TRAZADO_PARALLEL", "2"))
STAGGER = float(os.environ.get("TRAZADO_STAGGER", "0.35"))


def _from_secrets() -> str | None:
    """
    Streamlit Cloud sets secrets, not environment variables.

    Read lazily and defensively: importing streamlit outside a script run, or
    touching st.secrets with no secrets file, both raise.
    """
    try:
        import streamlit as st
        value = st.secrets.get("TRAZADO_PROXY", "")
    except Exception:
        return None
    value = str(value).strip()
    return value or None


def proxy() -> str | None:
    return os.environ.get(PROXY_ENV, "").strip() or _from_secrets()


def proxy_status() -> str:
    """One line describing how requests will leave this machine."""
    where = proxy()
    if not where:
        return "direct (no proxy)"
    # Never echo credentials embedded in a proxy URL.
    safe = where.split("@")[-1] if "@" in where else where
    return f"via {safe}"


def politely(work, items):
    """
    Run `work` over `items` with a small pool and a stagger between starts.

    Six requests fired simultaneously is what a scraper looks like. The same
    six spread over a couple of seconds is what a browser looks like, and the
    wall-clock difference on a page nobody is watching load is negligible.
    """
    from concurrent.futures import ThreadPoolExecutor

    items = list(items)
    if not items:
        return []

    def staggered(indexed):
        index, item = indexed
        # No point pacing politely into a wall: once the circuit is open the
        # remaining work is going to fail instantly anyway.
        if not _circuit_open():
            time.sleep(STAGGER * index + random.uniform(0, STAGGER))
        return work(item)

    workers = max(1, min(MAX_PARALLEL, len(items)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(staggered, enumerate(items)))

# curl_cffi sessions are not safe to share across threads, and the competition
# chooser resolves six competitions at once. Each thread gets its own, built
# on first use and reused thereafter.
_local = threading.local()

# Circuit breaker, for a total outage only.
#
# It exists so a completely unreachable host does not cost 39 seconds of
# spinner. It must NOT fire on rate limiting: being refused half the time is
# the normal signal from a shared address, and those requests succeed on
# retry. Tripping at two turned "some competitions failed" into "half the
# competitions failed", because everything after the trip got a single attempt
# and no retry. It now takes a run of failures long enough that no plausible
# rate limit explains it.
#
# Five, not eight: a failure is recorded once per get() after its retries are
# exhausted, not once per attempt, so with six competitions a trip above six is
# unreachable and a total outage never fails fast. Five needs a run that rate
# limiting will not produce, because rate limiting lets some requests through
# and any success resets the count.
_BREAKER_TRIP = int(os.environ.get("TRAZADO_BREAKER", "5"))
_BREAKER_COOLDOWN = float(os.environ.get("TRAZADO_COOLDOWN", "30"))
_breaker = {"failures": 0, "opened_at": 0.0}
_breaker_lock = threading.Lock()


def _circuit_open() -> bool:
    with _breaker_lock:
        if _breaker["failures"] < _BREAKER_TRIP:
            return False
        if time.time() - _breaker["opened_at"] > _BREAKER_COOLDOWN:
            _breaker["failures"] = 0          # cooled off; let one through
            return False
        return True


def _record(success: bool) -> None:
    with _breaker_lock:
        if success:
            _breaker["failures"] = 0
        else:
            _breaker["failures"] += 1
            if _breaker["failures"] == _BREAKER_TRIP:
                _breaker["opened_at"] = time.time()


def breaker_state() -> str:
    with _breaker_lock:
        n = _breaker["failures"]
    return "open" if _circuit_open() else f"closed ({n} recent failures)"


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


def get(url: str, *, referer: str | None = None, timeout: int = 20,
        retries: int = 2) -> str:
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
    # Only a total outage skips retries. A 403 from a rate limit is exactly
    # the case retries are for.
    if _circuit_open():
        retries = 0
    for attempt in range(retries + 1):
        try:
            response = session().get(url, timeout=timeout, headers=headers)
            status = response.status_code
        except Exception as exc:                      # transport-level failure
            status, last = None, f"{type(exc).__name__}: {exc}"
            response = None

        if status == 200:
            _record(True)
            return response.text
        if status is not None:
            last = f"status {status}"

        retryable = status in (403, 429, 500, 502, 503, 504) or status is None
        if retryable and attempt < retries:
            reset()
            time.sleep(min(4.0, 1.2 * (2 ** attempt)) + random.uniform(0, 0.5))
            continue
        break

    _record(False)
    hint = ""
    if "403" in last or "429" in last:
        hint = (" WhoScored rate limits bursts and throttles datacentre "
                "addresses hard.")
        if not proxy():
            hint += f" Try routing through a proxy: {PROXY_ENV}=socks5://host:port"
    raise FetchError(f"WhoScored request failed ({last}).{hint}")
