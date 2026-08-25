"""
Shared page furniture.

Streamlit cannot reference local image files from inside custom markup, so
every image here is inlined as a data URI. The league logos render at 28px and
the sources are 96px, which keeps each one a few kilobytes.
"""

from __future__ import annotations

import base64
import functools
import os
from urllib.parse import urlencode

from .theme import THEMES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")


@functools.lru_cache(maxsize=64)
def data_uri(relative: str) -> str:
    """Inline an asset. Cached because the bytes never change within a run."""
    path = os.path.join(ASSETS, relative)
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    kind = "image/svg+xml" if relative.endswith(".svg") else "image/png"
    return f"data:{kind};base64,{encoded}"


def link(**params) -> str:
    """
    Build a same-page URL carrying query params.

    Navigation is by anchor rather than st.button because the cards need to be
    styled as cards, which buttons resist.
    """
    clean = {k: v for k, v in params.items() if v is not None}
    return f"?{urlencode(clean)}" if clean else "?"


def mark(size: int = 28) -> str:
    """
    The Trazado mark, drawn inline so it inherits the theme.

    Square at the starting position, dashed run curve, accent stroke for the
    blocking action -- the same vocabulary the charts use.
    """
    return f"""
<svg width="{size}" height="{size}" viewBox="0 0 120 120" aria-hidden="true">
  <rect x="16" y="88" width="11" height="11" fill="var(--ink)"/>
  <path d="M27 88 Q40 32 88 12" fill="none" stroke="var(--ink)" stroke-width="6"
        stroke-dasharray="13 11" stroke-linecap="round"/>
  <path d="M77 2 L98 12 L82 30" fill="none" stroke="var(--accent)" stroke-width="6"
        stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M40 78 L68 65" fill="none" stroke="var(--hot)" stroke-width="8"
        stroke-linecap="round"/>
</svg>"""


def header(theme: str, **keep) -> str:
    """
    The header, identical on every screen.

    `keep` carries the current screen's params through a theme switch so
    changing theme never navigates away from where you are.
    """
    switches = "".join(
        f'<a href="{link(**{**keep, "theme": name})}" target="_self" '
        f'aria-current="{str(name == theme).lower()}">{name.title()}</a>'
        for name in THEMES
    )
    return f"""
<div class="tz-top">
  <div class="tz-brand">{mark()}<span class="tz-brand-name">trazado</span></div>
  <div class="tz-themes" role="group" aria-label="Theme">{switches}</div>
</div>"""
