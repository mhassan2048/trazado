"""
The analysis screen.

Scroll layout, hero first. Every section is conditional: a match with no
throw-ins into the box renders no throw-in row, and a match with no set piece
goals renders no goal card. An empty panel is never drawn.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from lib import badges, readout, setpieces
from lib.setpieces import CORNER, FREEKICK, GOAL_KICK, THROW_IN, PENALTY

from .charts import (aerial_zones, chain_caption, chainable, chains,
                     comparison, comparison_rows,
                     delivery_map, goal_kick_caption as charts_caption,
                     goal_kicks, timeline, to_png)
from .export import VISUALS, card
from .theme import THEMES as ALL_THEMES
from .theme import THEMES

KIND_LABEL = {CORNER: "corners", FREEKICK: "free kicks",
              THROW_IN: "throw-ins", PENALTY: "penalties",
              GOAL_KICK: "goal kicks"}


def _crest(team_id: int, name: str) -> str:
    src = badges.url(team_id)
    if src:
        return f'<img class="tz-crest" src="{src}" alt="">'
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    return f'<div class="tz-mono-crest" aria-hidden="true">{initials}</div>'


def _identity(match, home_id: int, away_id: int) -> str:
    meta = match.meta
    bits = [b for b in (meta.get("competition"), meta.get("venue"),
                        str(meta.get("start_date") or "")[:10]) if b]
    return f"""
<div class="tz-match">
  <div class="tz-side">{_crest(home_id, meta['home_team'])}
    <div class="tz-team">{meta['home_team']}</div></div>
  <div class="tz-score">{meta.get('score', '')}</div>
  <div class="tz-side tz-side--away">
    <div class="tz-team">{meta['away_team']}</div>{_crest(away_id, meta['away_team'])}</div>
</div>
<div class="tz-matchmeta">{' · '.join(bits)}</div>"""


def _glossary() -> str:
    items = "".join(
        f'<div class="tz-gl"><b>{term}</b> {meaning}</div>'
        for term, meaning in readout.GLOSSARY)
    return f'<details class="tz-glossary"><summary>What these numbers mean</summary>{items}</details>'


def _summary(pieces, team: str) -> str:
    """
    The stat strip, from the same source as the export card.

    It used to build its own cells with its own labels, which meant the screen
    and the card could disagree about what a number was called -- and did.
    """
    cells = readout.strip(pieces, team)
    inner = "".join(f'<div class="tz-stat"><div class="tz-stat-n">{value}</div>'
                    f'<div class="tz-stat-l">{label}</div></div>'
                    for value, label in cells)
    return f'<div class="tz-strip">{inner}</div>'


BADGE = {CORNER: "CO", FREEKICK: "FK", THROW_IN: "TI", PENALTY: "PK",
         GOAL_KICK: "GK"}


def _zone(piece) -> str:
    """
    A goal kick's zone is computed for attacking-half deliveries and means
    nothing at the other end of the pitch, so it is left blank rather than
    printed as noise.
    """
    if piece.kind == GOAL_KICK or piece.zone in ("", "unknown"):
        return "&mdash;"
    return piece.zone


KIND_NAME = {CORNER: "Corner", FREEKICK: "Free Kick", THROW_IN: "Throw-In",
             PENALTY: "Penalty", GOAL_KICK: "Goal Kick"}


def _ledger_key(pieces) -> str:
    """
    What the marks in the ledger mean.

    Built from the match, not from a fixed list: a key offering a Long Throw
    badge to a match with no long throws is describing a different game. Every
    item reuses the row classes rather than restating the styling, so the key
    and the table cannot drift apart.

    It sits above the table. A key below forty-five rows is a key you reach
    after you needed it.
    """
    groups = []

    kinds = [k for k in (CORNER, FREEKICK, THROW_IN, GOAL_KICK, PENALTY)
             if any(p.kind == k for p in pieces)]
    if kinds:
        items = "".join(
            f'<span class="tz-key-item">'
            f'<span class="tz-badge tz-badge--{k}">{BADGE.get(k, "??")}</span>'
            f'{KIND_NAME[k]}</span>' for k in kinds)
        groups.append(("Type", items))

    deliveries = [p for p in pieces if p.is_delivery]
    if deliveries:
        rules = []
        if any(p.complete for p in deliveries):
            rules.append(("tz-l-solid", "Found a Teammate"))
        if any(not p.complete for p in deliveries):
            rules.append(("tz-l-dash", "Cleared"))
        rule_html = lambda pairs: "".join(
            f'<span class="tz-key-item">'
            f'<span class="tz-l-line tz-key-rule"><i class="{cls}"></i></span>'
            f'{label}</span>' for cls, label in pairs)
        groups.append(("Delivery", rule_html(rules)))
        # Style and colour are independent channels here: the rule says whether
        # the ball was found, the accent says whether a shot followed, and a
        # cleared delivery that still produced a shot is drawn dashed AND in
        # accent. Listing the accent inside the Delivery group implied it was a
        # third line style, so it gets named for the channel it actually is.
        if any(p.led_to_shot for p in pieces):
            groups.append(("Accent", rule_html(
                [("tz-l-solid tz-l-hot", "Led to a Shot, Either Rule")])))

        contacts = [p.contact for p in deliveries]
        dots = []
        if any(c and c.attacking for c in contacts):
            dots.append(("tz-dot--won", "Won"))
        if any(c and not c.attacking for c in contacts):
            dots.append(("tz-dot--lost", "Lost"))
        if any(c is None for c in contacts):
            dots.append(("tz-dot--none", "No Contact"))
        if dots:
            groups.append(("First Contact", "".join(
                f'<span class="tz-key-item">'
                f'<span class="tz-dot {cls}"></span>{label}</span>'
                for cls, label in dots)))

    shots = [s for p in pieces for s in p.shots]
    if shots:
        items = ['<span class="tz-key-item"><span class="tz-out tz-out--shot">'
                 '1st</span>Off the Delivery</span>']
        if any(s.phase == setpieces.SECOND_PHASE for s in shots):
            items.append('<span class="tz-key-item">'
                         '<span class="tz-out tz-out--shot">2nd</span>'
                         'After the First Contact</span>')
        if any(p.goal for p in pieces):
            items.append('<span class="tz-key-item">'
                         '<span class="tz-out tz-out--goal">GOAL</span>'
                         'Scored</span>')
        groups.append(("Outcome", "".join(items)))

    if not groups:
        return ""
    blocks = "".join(f'<div class="tz-key-group">'
                     f'<span class="tz-key-label">{name}</span>{items}</div>'
                     for name, items in groups)
    return f'<div class="tz-key">{blocks}</div>'


def _ledger(pieces, home: str) -> str:
    """
    The ledger as notation, not as a spreadsheet.

    Each row carries the same vocabulary the charts use: a solid rule where the
    delivery found a teammate, dashed where it was cleared, the accent only
    where it led to a shot, and a filled or hollow marker for the duel.
    """
    rows = []
    for piece in pieces:
        contact = piece.contact
        shot = piece.shots[0] if piece.shots else None

        line_class = "tz-l-solid" if piece.complete else "tz-l-dash"
        if piece.led_to_shot:
            line_class += " tz-l-hot"

        if contact is None:
            marker = '<span class="tz-dot tz-dot--none"></span>'
            who = "&mdash;"
        else:
            filled = "tz-dot--won" if contact.attacking else "tz-dot--lost"
            marker = f'<span class="tz-dot {filled}"></span>'
            who = f"{contact.player}<span class='tz-ct'>{contact.type}</span>"

        if shot is None:
            result = '<span class="tz-out">&mdash;</span>'
        elif piece.goal:
            result = f'<span class="tz-out tz-out--goal">GOAL {shot.player}</span>'
        else:
            phase = "2nd" if shot.phase == setpieces.SECOND_PHASE else "1st"
            result = (f'<span class="tz-out tz-out--shot">{phase} &middot; '
                      f'{shot.player}</span>')

        rows.append(f"""
<div class="tz-row-l{' tz-row-l--goal' if piece.goal else ''}">
  <div class="tz-l-min">{piece.clock}</div>
  <div class="tz-l-state">{piece.state}</div>
  <div class="tz-l-glyph"><span class="tz-badge tz-badge--{piece.kind}">{BADGE.get(piece.kind, '??')}</span></div>
  <div class="tz-l-what">
    <div class="tz-l-taker">{piece.taker or '&mdash;'}</div>
    <div class="tz-l-sub">{piece.team} &middot; {piece.subtype}</div>
  </div>
  <div class="tz-l-line"><i class="{line_class}"></i></div>
  <div class="tz-l-zone">{_zone(piece)}</div>
  <div class="tz-l-contact">{marker}{who}</div>
  <div class="tz-l-result">{result}</div>
</div>""")

    head = """
<div class="tz-row-l tz-row-l--head">
  <div class="tz-l-min">Min</div><div class="tz-l-state">State</div>
  <div class="tz-l-glyph">Type</div><div class="tz-l-what">Taker</div>
  <div class="tz-l-line">Delivery</div><div class="tz-l-zone">Zone</div>
  <div class="tz-l-contact">First Contact</div><div class="tz-l-result">Outcome</div>
</div>"""
    return f'<div class="tz-ledger">{head}{"".join(rows)}</div>'


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in str(text)).strip("-").lower()


def _export_name(match, visual: str, team: str | None, suffix: str = "png") -> str:
    """
    A filename that says what it is without being opened.

    Names the visual, who it is about, which match, and when it was exported.
    Downloads accumulate in one folder and a name like `trazado-threat.png`
    collides with the next match and tells you nothing a week later.

    The export stamp is UTC and marked as such. The app already labels fixture
    times in UTC, and an unmarked local timestamp on a file that gets shared is
    ambiguous in exactly the way a timestamp exists to prevent.
    """
    meta = match.meta
    played = str(meta.get("start_date") or "")[:10].replace("-", "")
    subject = _slug(team) if team else (
        f"{_slug(meta.get('home_team'))}-vs-{_slug(meta.get('away_team'))}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    parts = ["trazado", _slug(visual), subject, played or "match", stamp]
    return "-".join(p for p in parts if p) + f".{suffix}"


def _export_panel(match, pieces, theme: str) -> None:
    """
    Section 7's card, one visual at a time.

    Every visual is exportable, not just the delivery map -- a chart that can
    only be seen inside the app is a chart nobody sends to anyone. Team-scoped
    visuals render one card per side; match-scoped ones render a single card.

    The card takes the app's theme. Section 7 allowed choosing it separately;
    in practice that was a second control to set before you could download
    something you were already looking at.
    """
    st.markdown('<div class="tz-sec">Export</div>', unsafe_allow_html=True)

    keys = list(VISUALS)
    chosen = st.selectbox(
        "Visual", keys, key="export_visual",
        format_func=lambda k: VISUALS[k]["label"], label_visibility="collapsed")

    spec = VISUALS[chosen]
    if spec["team"]:
        teams = [t for t in (match.meta["home_team"], match.meta["away_team"])
                 if any(p.team == t for p in pieces)]
    else:
        teams = [None]

    columns = st.columns(len(teams)) if len(teams) > 1 else [st.container()]
    for column, team in zip(columns, teams):
        with column:
            png = card(match, pieces, visual=chosen, team=team, theme=theme)
            st.image(png, use_container_width=True)
            who = team or match.meta["match_name"]
            st.download_button(
                f"Download {who}", data=png,
                file_name=_export_name(match, chosen, team), mime="image/png",
                use_container_width=True, key=f"dl_{chosen}_{who}")


def render(match, theme: str) -> None:
    palette = THEMES.get(theme, THEMES["vivid"])
    pieces = setpieces.extract(match)

    players = match.players
    home_id = away_id = 0
    if not players.empty:
        home_rows = players[players["side"] == "home"]
        away_rows = players[players["side"] == "away"]
        home_id = int(home_rows.iloc[0]["team_id"] or 0) if not home_rows.empty else 0
        away_id = int(away_rows.iloc[0]["team_id"] or 0) if not away_rows.empty else 0
    badges.warm([home_id, away_id])

    st.markdown(_identity(match, home_id, away_id), unsafe_allow_html=True)

    if not pieces:
        st.markdown('<p class="tz-empty">No qualifying set-pieces in this match.</p>',
                    unsafe_allow_html=True)
        return

    # The per-team summary strips stay: they are text, and they are what the
    # export panel below is a picture of. Everything that used to be rendered
    # here as its own on-screen figure is now reached through the export
    # selector -- one rendering path instead of two, and every visual has to
    # earn a card rather than existing only inside the app.
    for team in (match.meta["home_team"], match.meta["away_team"]):
        if not any(p.team == team for p in pieces):
            continue
        st.markdown(f'<div class="tz-sec">{team}</div>', unsafe_allow_html=True)
        st.markdown(_summary(pieces, team), unsafe_allow_html=True)
        if team == match.meta["home_team"]:
            st.markdown(_glossary(), unsafe_allow_html=True)

    _export_panel(match, pieces, theme)

    st.markdown('<div class="tz-sec">Ledger</div>', unsafe_allow_html=True)
    st.markdown(_ledger_key(pieces), unsafe_allow_html=True)
    st.markdown(_ledger(pieces, match.meta["home_team"]), unsafe_allow_html=True)

    st.markdown('<div class="tz-sec">Report</div>', unsafe_allow_html=True)
    text = readout.report(match, pieces)
    st.code(text, language=None)
    st.download_button("Download report", data=text,
                       file_name=_export_name(match, "report", None, "txt"),
                       mime="text/plain", key="dl_report")
