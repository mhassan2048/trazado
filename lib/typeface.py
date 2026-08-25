"""
One typeface, for the browser and for matplotlib, read from the files on disk.

Drop font files into assets/fonts and they become the app's face. Nothing is
hard coded to a family name: the name is read out of the file itself, so
swapping the typeface is a matter of replacing files, not editing code.

A font cannot be "hard coded" in any other sense -- matplotlib rasterises
glyphs from real bytes, and there is no string that conjures them. Without
files here every figure silently falls back to DejaVu Sans, which is not an
error anyone sees; it just looks like a bad font choice. `active()` and
`is_branded()` make that checkable.

Formats: .ttf and .otf work in both matplotlib and the browser. .woff2 is
browser-only and is deliberately not accepted -- it would give an app that
looked right and export cards that did not.
"""

from __future__ import annotations

import glob
import os

import matplotlib
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")
SERVE_DIR = os.path.join(ROOT, "static", "fonts")
USABLE = (".ttf", ".otf")

FALLBACK = "DejaVu Sans"
SANS_TAIL = "'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO_TAIL = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

_state: dict | None = None


def _files() -> list[str]:
    """Every usable font under assets/fonts, at any depth.

    Recursive because a font downloaded from Google Fonts arrives as a folder,
    and requiring it to be unpacked by hand is exactly the friction this module
    exists to remove."""
    found = []
    for ext in USABLE:
        found += glob.glob(os.path.join(FONT_DIR, "**", f"*{ext}"), recursive=True)
        found += glob.glob(os.path.join(FONT_DIR, "**", f"*{ext.upper()}"), recursive=True)
    return sorted(set(found))


_WEIGHT_WORDS = {"thin": 100, "extralight": 200, "ultralight": 200,
                 "light": 300, "book": 400, "normal": 400, "regular": 400,
                 "medium": 500, "demibold": 600, "semibold": 600,
                 "bold": 700, "extrabold": 800, "heavy": 800, "black": 900}


def _is_monospaced(path: str) -> bool:
    """
    True when every glyph advances the same width.

    Measured, not guessed from the family name: the fallback stack has to
    match, or a browser without the font swaps a monospace design for a
    proportional one and every aligned column collapses.
    """
    try:
        font = font_manager.get_font(path)
        font.set_size(64, 72)
        widths = set()
        for ch in "iMW1l .":
            font.clear()
            font.set_text(ch)
            widths.add(round(font.get_width_height()[0]))
        return len(widths) == 1
    except Exception:
        return False


def _describe(path: str):
    """(family, weight, style) as the file itself declares them."""
    try:
        props = font_manager.ttfFontProperty(font_manager.get_font(path))
    except Exception:
        return None
    weight = props.weight
    if not isinstance(weight, int):
        weight = _WEIGHT_WORDS.get(str(weight).lower(), 400)
    style = "italic" if str(props.style).lower() in ("italic", "oblique") else "normal"
    return props.name, int(weight), style


def install() -> dict:
    """
    Register every font found and point matplotlib at it. Idempotent.

    Returns {family, weights, files, branded}.
    """
    global _state
    if _state is not None:
        return _state

    faces = []
    for path in _files():
        described = _describe(path)
        if described is None:
            continue
        try:
            font_manager.fontManager.addfont(path)
        except Exception:
            continue
        family, weight, style = described
        faces.append({"family": family, "weight": weight, "style": style,
                      "file": os.path.basename(path), "path": path,
                      # A downloaded font keeps its original timestamp, so the
                      # file's own mtime says when it was built, not when it
                      # was put here. The folder it arrived in says the latter.
                      "mtime": max(os.path.getmtime(path),
                                   os.path.getmtime(os.path.dirname(path)))})

    # When several families are present the most recently added one wins.
    # Dropping a font in is how you choose it, so the newest arrival is the
    # intent; counting files would let an old family outvote a deliberate
    # replacement simply by shipping more weights.
    family = FALLBACK
    if faces:
        newest: dict[str, float] = {}
        for face in faces:
            newest[face["family"]] = max(newest.get(face["family"], 0.0),
                                         face["mtime"])
        family = max(newest, key=newest.get)
        faces = [f for f in faces if f["family"] == family]

    available = {f.name for f in font_manager.fontManager.ttflist}
    if family not in available:
        family = FALLBACK
        faces = []

    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = [family, FALLBACK]
    matplotlib.rcParams["font.monospace"] = [family, "DejaVu Sans Mono"]
    matplotlib.rcParams["axes.unicode_minus"] = False

    mono = bool(faces) and _is_monospaced(faces[0]["path"])
    _state = {"family": family,
              "faces": sorted(faces, key=lambda f: (f["style"], f["weight"])),
              "branded": family != FALLBACK,
              "monospaced": mono}
    return _state


def is_monospaced() -> bool:
    return install()["monospaced"]


def active() -> str:
    return install()["family"]


def is_branded() -> bool:
    return install()["branded"]


def css_stack() -> str:
    """The CSS font stack, with a fallback that matches the font's own nature."""
    tail = MONO_TAIL if install()["monospaced"] else SANS_TAIL
    return f"'{active()}', {tail}"


def face_css(url_base: str = "app/static/fonts") -> str:
    """
    @font-face rules for the files on disk.

    Served locally rather than from a CDN so the browser and matplotlib load
    the same bytes -- they cannot drift apart, and the app needs no network.
    """
    rules = []
    for face in install()["faces"]:
        kind = "opentype" if face["file"].lower().endswith(".otf") else "truetype"
        # Italics are declared with their real style so the browser uses the
        # designed face instead of shearing the upright one.
        rules.append(
            "@font-face{font-family:'%s';font-style:%s;font-weight:%d;"
            "font-display:swap;src:url('%s/%s') format('%s');}"
            % (face["family"], face["style"], face["weight"],
               url_base, face["file"], kind))
    return "\n".join(rules)


def sync_served() -> int:
    """
    Copy the fonts into static/ so Streamlit can serve them. Returns the count.

    Kept as a copy rather than a symlink because Streamlit's static server
    will not follow links out of its directory.
    """
    import shutil
    os.makedirs(SERVE_DIR, exist_ok=True)
    for stale in glob.glob(os.path.join(SERVE_DIR, "*")):
        os.remove(stale)
    copied = 0
    for face in install()["faces"]:
        source = face.get("path") or os.path.join(FONT_DIR, face["file"])
        if os.path.exists(source):
            shutil.copy2(source, os.path.join(SERVE_DIR, face["file"]))
            copied += 1
    return copied
