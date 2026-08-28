"""
Themes.

Per the spec, only the token block is dynamic. Every rule below it references
var(--token) and never a literal colour, so switching theme rewrites one small
block and nothing else.

Known gap, carried from the spec: Vivid defines three accents, Moon and
Newspaper one. Rather than leave `hot` and `warn` undefined in Moon -- which
would render as inherited or transparent, not as a visible fallback -- they are
mapped onto Moon's single accent and a muted gold. That keeps every theme
renderable while the wider decision (extend the palettes, or design every chart
to need one accent) stays open.
"""

from __future__ import annotations

# Rebuilt for restraint, not for contrast -- the old set already passed every
# contrast check and still looked cheap. The measurement that explains why:
# Vivid's series ran at OKLCH chroma 0.225 / 0.114 / 0.210. Two at near-maximum
# saturation and one moderate, so the red and the violet shouted while the teal
# receded. That imbalance is what reads as garish, and it was not a choice --
# teal at that lightness cannot exceed C 0.11 in sRGB, so the other two were
# simply left wherever they landed.
#
# The fix is even chroma, which costs colour-blind separation, because ΔE comes
# largely from chroma. Section 4 makes colour the *only* channel carrying set
# piece type -- there are no shape markers to fall back on -- so separation
# cannot be traded away. The resolution was to search for hues that reach even
# chroma while staying separable, rather than to desaturate the existing ones.
#
# Result: one hue family across all three themes -- ochre 70, jade 170,
# lavender 305 -- differing only in lightness, with chroma even within a theme.
# Vivid/Moon sit at C 0.125, Newspaper at C 0.110 for its lighter surface.
# Verified with the dataviz validator: lightness band, chroma floor, CVD
# separation (deutan 10.8 / tritan 14.4 on dark, 9.4 / 12.6 on light),
# normal-vision floor and 3:1 contrast all pass.
#
# Every token below also clears section 5: 4.5:1 for body text and 3:1 for
# secondary text and chart lines, against BOTH bg and surface. `faint` is the
# one that keeps failing when nudged -- it sat at 2.76:1 on surface during this
# rebuild before being lifted -- so re-measure it after any change.
# Series colours are chosen, not derived. Each theme names its own set rather
# than sharing one across all three -- an earlier version used identical hexes
# for Vivid and Moon, which made the two themes indistinguishable in the one
# channel that carries meaning.
#
#   Vivid      Copper / Teal / Periwinkle
#   Moon       the same family, lighter and slightly cooler for its ground
#   Newspaper  Rose / Olive / Azure, pitched deeper to hold a light surface
#
# Chroma is even within each set. The set this replaced ran 0.225 / 0.114 /
# 0.210, so two colours shouted and one receded; that imbalance is what reads as
# garish, and it is measurable rather than a matter of taste.
#
# All three pass the dataviz validator on their own surface -- lightness band,
# chroma floor, CVD separation, normal-vision floor, 3:1 contrast. Section 4
# makes colour the only channel carrying set piece type, with no shape markers
# to fall back on, so separation cannot be traded for prettiness.
#
# **The accent is checked against the series, not just against the ground.** It
# means "led to a shot" and nothing else, so it must not read as a fourth type.
# The blue accents that preceded these sat ΔE 6.5 from Newspaper's azure and 8.5
# from Moon's periwinkle -- close enough to pass for a type colour. Gold on the
# dark themes and violet on Newspaper clear every series by ΔE 15.8 or better.
# `hot` and `warn` are not part of that check because neither ever appears on a
# chart beside the series; they live on the chooser and the logo mark.
#
# Every token also clears section 5 on BOTH bg and surface: 4.5:1 for body text,
# 3:1 for secondary text and chart lines. `faint` is the one that fails when
# nudged, so re-measure it after any change.
# Rose / olive / azure, at three weights. Two findings forced this and both are
# worth keeping.
#
# **The validator was being run adjacent-pairs-only, which hid a real fault.**
# With `--pairs all` it compares every pair, and the palettes that preceded these
# do not survive it: copper/teal/periwinkle scores 7.9, below the floor. Search
# with all-pairs checking and almost everything collapses -- of nine hand-picked
# families only rose/olive/azure passed, at 11.7 against 7.9 for the next best.
# Run the validator with `--pairs all` or it will tell you what you want to hear.
#
# **Thin tapered strokes need chroma.** A near-monochrome Newspaper -- black,
# coffee, grey -- separated beautifully on paper and was unreadable in practice,
# because a comet fades from solid to nothing and a low-chroma stroke has no
# fade left to give. Chroma is floored at 0.12 here for that reason alone.
#
# Olive rather than green is not a preference. Rose against green is the classic
# deuteranopia confusion; h122 is as far toward green as the middle slot can go
# and still be seen by a red-green colour-blind reader.
#
# Themes differ by weight rather than by hue, because only one hue structure
# survives: Vivid boldest at C 0.145, Moon lighter and softer at 0.125,
# Newspaper deeper at 0.122 for its cream ground. Accents are teal, the widest
# gap left in the wheel, and each is checked against the series it sits beside
# rather than only against the ground.
#
# Every token clears section 5 on BOTH bg and surface: 4.5:1 body text, 3:1
# secondary text and chart lines. `faint` is the one that fails when nudged.
THEMES: dict[str, dict[str, str]] = {
    "vivid": {
        "bg": "#101017", "surface": "#1A1A23", "surface-dim": "#14141B",
        "line": "#2E2E3C", "line-dim": "#222230",
        "ink": "#ECEAF2", "muted": "#9A96A8", "faint": "#696577",
        "accent": "#62D4C8", "accent-on": "#06302C",
        "hot": "#E0785E", "warn": "#D2A244",
        "s1": "#D3658F", "s2": "#819C23", "s3": "#1299DE",
        "chip": "#FFFFFF",
    },
    "moon": {
        "bg": "#0D1016", "surface": "#161B22", "surface-dim": "#11151B",
        "line": "#28303B", "line-dim": "#1D242D",
        "ink": "#E2E7EE", "muted": "#8B95A4", "faint": "#606977",
        "accent": "#66DAD7", "accent-on": "#06302F",
        "hot": "#DC8266", "warn": "#C9A15A",
        "s1": "#D27295", "s2": "#88A142", "s3": "#3F9EDA",
        "chip": "#FFFFFF",
    },
    "newspaper": {
        "bg": "#FBF7EE", "surface": "#F3EDE0", "surface-dim": "#EEE7D7",
        "line": "#DAD1BF", "line-dim": "#E6DFCF",
        "ink": "#332F28", "muted": "#736A5A", "faint": "#908673",
        "accent": "#003636", "accent-on": "#E8F2F1",
        "hot": "#A64B33", "warn": "#8C6B1F",
        "s1": "#A54D6E", "s2": "#637916", "s3": "#0776AE",
        "chip": "#FFFFFF",
    },
}

# One hue per set piece type. Assigned in fixed order and never cycled; a
# fourth type folds into the neutral rather than inventing a hue.
#
# Every set passes the five checks on its own theme's chart surface: OKLCH
# lightness band, chroma floor, colour-blind separation, normal-vision
# separation, and 3:1 contrast. Searched in OKLCH rather than picked by eye --
# the earlier hand-picked sets failed CVD separation every time.
SERIES = ("s1", "s2", "s3")

DEFAULT = "vivid"          # app default, per the spec
EXPORT_DEFAULT = "newspaper"  # export default, for graphics beside written work


def tokens(theme: str) -> str:
    """The one dynamic block."""
    palette = THEMES.get(theme, THEMES[DEFAULT])
    body = "\n".join(f"  --{name}: {value};" for name, value in palette.items())
    return f":root {{\n{body}\n}}"


# Everything below is static.
# Interface face. Declared once here and once as --font-ui below; no rule names
# a family directly, so swapping it is a two-line change.
# The typeface is whatever sits in assets/fonts -- family name, weights and
# @font-face rules are all read from the files. Replacing the font is a matter
# of replacing files; nothing here names a family.
from lib import typeface  # noqa: E402

_STATIC = """
/* Typography lives in two tokens so swapping a family is a one-line change
   rather than a hunt through every rule. Mono is deliberate on numbers: it
   makes figures read as readouts and keeps ledger columns aligned.

   The families load through a <link>, not @import. CSS ignores an @import
   that is not the first rule in the sheet, and the theme token block is
   emitted ahead of this one -- so an @import here never loaded at all and the
   page silently fell back to Streamlit's own face. */
:root {
  --font-ui: __FONT_STACK__;
  /* Kept as a token so readouts can still be tabular, but it is the same
     family -- one font, everywhere. */
  --font-mono: __FONT_STACK__;
}

/* Strip Streamlit's own chrome so the page is ours. */
#MainMenu, header[data-testid="stHeader"], footer, [data-testid="stToolbar"] {
  display: none !important;
}
[data-testid="stAppViewContainer"] > .main { background: var(--bg); }
.block-container {
  max-width: 860px !important;
  padding: 2rem 1.25rem 4rem !important;
}
html, body, [data-testid="stAppViewContainer"], .stApp {
  background: var(--bg) !important;
  -webkit-font-smoothing: antialiased;
}
/* Streamlit applies its own font-family to inner containers, so inheriting
   from body is not enough -- every Trazado element names the face itself. */
html, body, .stApp, .block-container,
[data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"],
[class^="tz-"], [class*=" tz-"], .tz-h1, .tz-sub, .tz-team, .tz-name,
.tz-brand-name, .tz-league h2 {
  font-family: var(--font-ui) !important;
}
/* ...except the readouts, which are re-asserted after the blanket rule. */
.mono, .tz-count, .tz-themes a, .tz-chips a, .tz-or span, .tz-dayhead,
.tz-result, .tz-kick, .tz-season, .tz-back, .tz-note, .tz-mono-crest {
  font-family: var(--font-mono) !important;
}

/* Numbers stay legible as readouts without a second family: tabular figures
   keep ledger columns aligned, and the letterspacing does the rest. */
.mono, .tz-count, .tz-l-min, .tz-l-state, .tz-badge, .tz-result, .tz-kick,
.tz-season, .tz-back, .tz-note, .tz-dayhead, .tz-chips a, .tz-themes a,
.tz-or span, .tz-stat-n, .tz-score, .tz-matchmeta, .tz-l-sub, .tz-ct, .tz-out {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
}

/* Streamlit assigns its own colour and underline to any markdown anchor. Every
   Trazado anchor opts out; each rule below then sets its own colour. */
a[class^="tz-"], a[class^="tz-"]:visited, a[class^="tz-"]:active,
.tz-chips a, .tz-themes a, .tz-fixtures a {
  text-decoration: none !important;
}

/* --- header, identical on every screen --- */
.tz-top {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 16px; margin-bottom: 26px;
  border-bottom: 1px solid var(--line-dim);
}
.tz-brand { display: flex; align-items: center; gap: 10px; }
.tz-brand-name {
  color: var(--ink); font-size: 20px; font-weight: 700; letter-spacing: -0.5px;
}
.tz-themes { display: flex; gap: 6px; }
.tz-themes a {
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.5px;
  color: var(--muted); border: 1px solid var(--line); border-radius: 20px;
  padding: 5px 12px; text-decoration: none; transition: all .18s ease;
}
.tz-themes a:hover { color: var(--ink); border-color: var(--ink); }
.tz-themes a[aria-current="true"] {
  background: var(--accent); color: var(--accent-on); border-color: var(--accent);
}

/* --- headings --- */
/* The masthead runs heavy: the season is the loudest thing on the page. It is
   a title here, not a table readout, so it stays in the UI face rather than
   mono. */
.tz-h1 {
  color: var(--ink); font-size: 32px; font-weight: 700;
  letter-spacing: -1px; margin: 0 0 4px; line-height: 1.05;
}
.tz-sub {
  color: var(--muted); font-size: 13px; margin: 0 0 22px;
  letter-spacing: 0.1px;
}

/* --- competition grid --- */
.tz-grid {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 11px; margin-bottom: 26px;
}
/* Streamlit underlines and recolours any <a> inside markdown, so the card and
   everything nested in it has to opt out explicitly. */
.tz-card, .tz-card:hover, .tz-card *, .tz-themes a, .tz-themes a:hover {
  text-decoration: none !important;
}
.tz-card { -webkit-text-decoration: none !important; }
.tz-card {
  display: block; text-decoration: none;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 11px; padding: 15px;
  transition: border-color .18s ease, transform .18s ease;
}
a.tz-card:hover { border-color: var(--accent); transform: translateY(-2px); }
/* A competition with nothing to open. Same treatment as an unplayed fixture --
   dashed and dimmed, no hover -- so "nothing here" reads the same way twice. */
.tz-card--off {
  background: transparent; border-style: dashed; border-color: var(--line-dim);
}
.tz-card--off .tz-name { color: var(--faint); }
.tz-card--off .tz-chip { opacity: 0.5; }
.tz-row { display: flex; align-items: center; gap: 12px; }
.tz-chip {
  width: 40px; height: 40px; flex-shrink: 0;
  background: var(--chip); border: 1px solid var(--line);
  border-radius: 9px; display: flex; align-items: center; justify-content: center;
}
.tz-chip img { width: 28px; height: 28px; object-fit: contain; display: block; }
.tz-name {
  color: var(--ink); font-size: 14px; font-weight: 500; line-height: 1.25;
}
.tz-count { color: var(--muted); font-size: 11px; margin-top: 15px; }
.tz-count--unknown { color: var(--faint); }
.tz-count--warn { color: var(--warn); }

/* --- divider before the direct lookup --- */
.tz-or { display: flex; align-items: center; gap: 14px; margin-bottom: 6px; }
.tz-or i { flex: 1; height: 1px; background: var(--line-dim); }
.tz-or span {
  color: var(--muted); font-size: 10px; letter-spacing: 1px;
  font-family: var(--font-mono);
}

/* --- the direct lookup, which is a real Streamlit input --- */
[data-testid="stTextInput"] input {
  background: var(--surface) !important; border: 1px solid var(--line) !important;
  border-radius: 9px !important; color: var(--ink) !important;
  font-family: var(--font-mono) !important; font-size: 12px !important;
  padding: 11px 13px !important;
}
[data-testid="stTextInput"] input::placeholder { color: var(--faint) !important; }
[data-testid="stTextInput"] input:focus {
  border-color: var(--accent) !important; box-shadow: none !important;
}
[data-testid="stTextInput"] label { display: none !important; }
[data-testid="stButton"] button {
  background: var(--accent) !important; color: var(--accent-on) !important;
  border: none !important; border-radius: 9px !important;
  font-family: var(--font-ui) !important;
  font-size: 13px !important; font-weight: 500 !important;
  padding: 11px 24px !important; width: 100%;
}
[data-testid="stButton"] button:hover { filter: brightness(1.08); }

/* --- match chooser --- */
.tz-league { display: flex; align-items: center; gap: 11px; margin-bottom: 4px; }
.tz-league .tz-chip { width: 34px; height: 34px; border-radius: 8px; }
.tz-league .tz-chip img { width: 24px; height: 24px; }
.tz-league h2 {
  color: var(--ink); font-size: 22px; font-weight: 500;
  letter-spacing: -0.5px; margin: 0;
}
.tz-season {
  color: var(--faint); font-size: 11px; letter-spacing: 0.5px;
  font-family: var(--font-mono);
}

.tz-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 18px 0 20px; }
.tz-chips a {
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.4px;
  color: var(--muted); border: 1px solid var(--line); border-radius: 20px;
  padding: 5px 11px; transition: all .18s ease;
}
.tz-chips a:hover { color: var(--ink); border-color: var(--ink); }
.tz-chips a[aria-current="true"] {
  background: var(--accent); color: var(--accent-on); border-color: var(--accent);
}

.tz-dayhead {
  color: var(--faint); font-size: 10px; letter-spacing: 1.2px;
  font-family: var(--font-mono);
  margin: 22px 0 9px; padding-bottom: 6px; border-bottom: 1px solid var(--line-dim);
}
.tz-dayhead:first-of-type { margin-top: 0; }

.tz-fixtures { display: flex; flex-direction: column; gap: 8px; }
.tz-fix {
  display: grid; grid-template-columns: 1fr auto 1fr; align-items: center;
  gap: 10px; padding: 12px 14px;
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  transition: border-color .18s ease, transform .18s ease;
}
a.tz-fix:hover { border-color: var(--accent); transform: translateY(-1px); }
/* An unplayed fixture has nothing to open. It stays visible so a league
   mid-round looks mid-round, but it must not invite a click: dimmed crests,
   a fainter rule, and no hover response. */
.tz-fix--off {
  background: transparent; border-color: var(--line-dim); border-style: dashed;
}
.tz-fix--off .tz-crest, .tz-fix--off .tz-mono-crest { opacity: 0.45; }
.tz-fix--off .tz-team { color: var(--faint); }
.tz-side { display: flex; align-items: center; gap: 9px; min-width: 0; }
.tz-side--away { justify-content: flex-end; }
.tz-crest {
  width: 26px; height: 26px; flex-shrink: 0; object-fit: contain; display: block;
}
.tz-mono-crest {
  width: 26px; height: 26px; flex-shrink: 0; border-radius: 50%;
  background: var(--surface-dim); border: 1px solid var(--line);
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); font-size: 9px; font-weight: 700;
  font-family: var(--font-mono);
}
.tz-team {
  color: var(--ink); font-size: 13px; line-height: 1.2;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tz-fix--off .tz-team { color: var(--muted); }
.tz-result {
  font-family: var(--font-mono); font-size: 15px; font-weight: 700;
  color: var(--ink); letter-spacing: 0.5px; white-space: nowrap;
  padding: 0 6px; text-align: center;
}
.tz-kick {
  font-family: var(--font-mono); font-size: 10px;
  color: var(--faint); white-space: nowrap; padding: 0 6px; text-align: center;
}
.tz-empty {
  color: var(--muted); font-size: 13px; padding: 26px 0;
  border-top: 1px solid var(--line-dim);
}

/* Narrow screens shrink the name rather than dropping it. Section 6 already
   flags that badges alone are hard to read in less familiar leagues, so the
   name is the part that has to survive. */
@media (max-width: 520px) {
  .tz-team { font-size: 11px; }
  .tz-fix { padding: 10px; gap: 6px; }
  .tz-crest, .tz-mono-crest { width: 22px; height: 22px; }
}

/* --- analysis --- */
.tz-match {
  display: grid; grid-template-columns: 1fr auto 1fr; align-items: center;
  gap: 14px; margin-bottom: 6px;
}
.tz-match .tz-team { font-size: 17px; font-weight: 600; }
.tz-match .tz-crest, .tz-match .tz-mono-crest { width: 34px; height: 34px; }
.tz-score {
  font-family: var(--font-mono); font-size: 26px; font-weight: 700;
  color: var(--ink); letter-spacing: 1px; white-space: nowrap; padding: 0 10px;
}
.tz-matchmeta {
  color: var(--faint); font-size: 11px; font-family: var(--font-mono);
  text-align: center; margin-bottom: 26px;
  padding-bottom: 16px; border-bottom: 1px solid var(--line-dim);
}
.tz-sec {
  color: var(--ink); font-size: 17px; font-weight: 600; letter-spacing: -0.3px;
  margin: 30px 0 12px;
}
.tz-strip {
  display: flex; flex-wrap: wrap; gap: 1px; margin-bottom: 18px;
  background: var(--line-dim); border: 1px solid var(--line-dim);
  border-radius: 10px; overflow: hidden;
}
.tz-stat { flex: 1 1 auto; min-width: 92px; background: var(--surface); padding: 11px 13px; }
.tz-stat-n {
  font-family: var(--font-mono); font-size: 19px; font-weight: 700; color: var(--ink);
}
.tz-stat-l {
  color: var(--muted); font-size: 10px; letter-spacing: 0.3px; margin-top: 3px;
}

/* Shown only when a fetch failed, so the reader is never left guessing
   whether a competition is empty or simply unreachable. */
.tz-alert {
  border: 1px solid var(--warn); border-left-width: 3px;
  border-radius: 9px; padding: 10px 13px; margin: -14px 0 22px;
  color: var(--muted); font-size: 11.5px; line-height: 1.6;
}
.tz-alert b { color: var(--ink); font-weight: 600; }
.tz-why {
  display: block; color: var(--faint); font-size: 11px; margin-top: 6px;
}

/* --- glossary, collapsed by default --- */
.tz-glossary {
  border: 1px solid var(--line-dim); border-radius: 9px;
  padding: 9px 13px; margin: -8px 0 18px;
  background: var(--surface-dim);
}
.tz-glossary summary {
  color: var(--muted); font-size: 11px; cursor: pointer;
  letter-spacing: 0.3px; list-style: none;
}
.tz-glossary summary::-webkit-details-marker { display: none; }
.tz-glossary summary::before { content: "? "; color: var(--faint); }
.tz-glossary[open] summary { margin-bottom: 8px; color: var(--ink); }
.tz-gl {
  color: var(--muted); font-size: 11.5px; line-height: 1.65;
  padding: 3px 0 3px 12px; border-left: 2px solid var(--line);
  margin-bottom: 4px;
}
.tz-gl b { color: var(--ink); font-weight: 600; }

/* --- ledger: the chart vocabulary, as a table --- */
.tz-ledger {
  border: 1px solid var(--line-dim); border-radius: 10px; overflow: hidden;
  margin-bottom: 8px;
}
.tz-row-l {
  display: grid;
  grid-template-columns: 50px 42px 34px minmax(118px,1.4fr) 70px 78px minmax(138px,1.5fr) minmax(118px,1.2fr);
  align-items: center; gap: 10px;
  padding: 9px 13px; border-top: 1px solid var(--line-dim);
  font-size: 12px; color: var(--ink);
}
.tz-row-l:first-child { border-top: none; }
.tz-row-l:nth-child(even) { background: var(--surface-dim); }
.tz-row-l--head {
  background: var(--surface); color: var(--faint);
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 1px;
}
.tz-row-l--goal { background: var(--accent-on) !important; }

.tz-l-min, .tz-l-state { font-family: var(--font-mono); font-size: 11px; color: var(--muted); }
.tz-l-glyph { text-align: left; }
.tz-row-l--head { text-transform: none; }
.tz-badge {
  display: inline-block; font-family: var(--font-mono); font-size: 9px;
  letter-spacing: 0.6px; color: var(--muted);
  border: 1px solid var(--line); border-radius: 4px; padding: 2px 5px;
}
.tz-badge--penalty { color: var(--ink); border-color: var(--muted); }
.tz-l-taker { color: var(--ink); line-height: 1.2; }
.tz-l-sub {
  color: var(--faint); font-size: 10px; margin-top: 2px;
  font-family: var(--font-mono);
}
.tz-l-zone { color: var(--muted); font-size: 11px; }

/* The ledger key. Every swatch reuses the row classes above rather than
   restating them, so the key cannot drift from the table it explains. */
.tz-key {
  display: flex; flex-wrap: wrap; gap: 9px 26px;
  margin: -2px 0 14px; align-items: center;
}
.tz-key-group { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.tz-key-label {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 1px;
  color: var(--faint);
}
.tz-key-item {
  display: flex; align-items: center; gap: 7px;
  font-family: var(--font-ui); font-size: 11px; color: var(--muted);
}
.tz-key-item .tz-dot { margin-right: 0; }
.tz-key-rule { display: inline-block; width: 24px; }

/* The delivery rule: same notation as the pitch. */
.tz-l-line i { display: block; height: 0; width: 100%; }
.tz-l-line i.tz-l-solid { border-top: 2px solid var(--muted); }
.tz-l-line i.tz-l-dash { border-top: 2px dashed var(--muted); }
.tz-l-line i.tz-l-hot { border-color: var(--accent); }

.tz-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 7px; vertical-align: middle;
}
.tz-dot--won { background: var(--muted); border: 1px solid var(--muted); }
.tz-dot--lost { background: transparent; border: 1px solid var(--muted); }
.tz-dot--none { background: transparent; border: 1px dotted var(--faint); }
.tz-ct {
  display: block; color: var(--faint); font-size: 10px;
  font-family: var(--font-mono); margin-top: 2px;
}
.tz-out { font-size: 11px; color: var(--faint); font-family: var(--font-mono); }
.tz-out--shot { color: var(--accent); }
.tz-out--goal { color: var(--accent); font-weight: 700; letter-spacing: 0.4px; }

@media (max-width: 720px) {
  .tz-row-l { grid-template-columns: 46px 34px 1fr 56px 1fr; }
  .tz-l-state, .tz-l-zone, .tz-l-result { display: none; }
}

/* breadcrumb, on every screen below the chooser */
.tz-back {
  display: inline-block; margin-bottom: 18px;
  color: var(--muted) !important; font-size: 11px; letter-spacing: 0.3px;
  font-family: var(--font-mono); text-decoration: none !important;
}
.tz-back:hover { color: var(--accent) !important; }

/* --- Streamlit widgets we did not previously touch ---------------------
   These render from .streamlit/config.toml, which is a fixed dark theme, so
   on Newspaper they came out white-on-cream and dark-on-cream. Anything the
   app shows has to take its colour from the active token block, not from a
   config file that knows nothing about which theme is on. */
[data-testid="stRadio"] label,
[data-testid="stRadio"] label p,
[data-testid="stRadio"] div[role="radiogroup"] label {
  color: var(--ink) !important;
  font-family: var(--font-ui) !important;
}
[data-testid="stRadio"] label { font-size: 13px !important; }

[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"],
[data-testid="stDownloadButton"] button {
  background: var(--accent) !important;
  color: var(--accent-on) !important;
  border: none !important;
  border-radius: 9px !important;
  font-family: var(--font-ui) !important;
  font-weight: 600 !important;
}
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stDownloadButton"] button:hover { filter: brightness(1.06); }

/* The text report */
[data-testid="stCode"], [data-testid="stCode"] pre, pre, pre code {
  background: var(--surface-dim) !important;
  color: var(--ink) !important;
  border: 1px solid var(--line-dim) !important;
  border-radius: 10px !important;
  font-family: var(--font-ui) !important;
  font-size: 12px !important;
  line-height: 1.55 !important;
}
[data-testid="stCode"] pre { border: none !important; }
pre code span { color: var(--ink) !important; }

.tz-note {
  margin-top: 26px; padding-top: 16px; border-top: 1px solid var(--line-dim);
  color: var(--faint); font-size: 11px; line-height: 1.7;
  font-family: var(--font-mono); letter-spacing: 0.3px;
}
.tz-by { color: var(--muted) !important; }
.tz-stamp {
  color: var(--faint); font-size: 10.5px; letter-spacing: 0.3px;
  margin: 14px 0 -6px; font-family: var(--font-mono);
}
.tz-by:hover { color: var(--accent) !important; }
.tz-error {
  color: var(--hot); font-size: 12px; margin-top: 10px;
  font-family: var(--font-mono);
}

@media (max-width: 640px) {
  .tz-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tz-top { flex-direction: column; align-items: flex-start; gap: 14px; }
}
@media (max-width: 420px) { .tz-grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""


def font_links() -> str:
    """
    The @font-face block, emitted on its own.

    It must not share a markdown payload with the main <style> block:
    Streamlit drops the second style tag when two are sent together.
    """
    typeface.sync_served()
    return f"<style>\n{typeface.face_css()}\n</style>"


def css(theme: str) -> str:
    body = _STATIC.replace("__FONT_STACK__", typeface.css_stack())
    return f"<style>\n{tokens(theme)}\n{body}\n</style>"

