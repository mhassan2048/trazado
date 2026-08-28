"""
Text that goes on a graphic.

Every line here is bound by the same three rules as the rest of the app: no
claim of tendency, no percentage on a denominator under ten, and nothing said
that this one match does not show. "Five of seven went near post" is allowed.
"Prefers the near post" is not, and neither is "71%".
"""

from __future__ import annotations

from collections import Counter

from . import setpieces
from .setpieces import CORNER, FREEKICK, GOAL_KICK, PENALTY, THROW_IN

# How each zone reads inside a sentence. "to the central" is not English.
ZONE_PHRASE = {
    "six-yard box": "to the six-yard box",
    "central": "centrally",
    "left half space": "to the left half space",
    "right half space": "to the right half space",
    "edge of box": "to the edge of the box",
    "wide of box": "wide of the box",
}

KIND_WORD = {
    CORNER: ("corner", "corners"),
    FREEKICK: ("free kick", "free kicks"),
    THROW_IN: ("long throw", "long throws"),
    GOAL_KICK: ("goal kick", "goal kicks"),
    PENALTY: ("penalty", "penalties"),
}


def _plural(kind: str, n: int) -> str:
    single, many = KIND_WORD.get(kind, (kind, kind))
    return single if n == 1 else many


def summary(pieces, team: str) -> dict:
    """The numbers a card needs, already counted."""
    mine = [p for p in pieces if p.team == team]
    deliveries = [p for p in mine if p.is_delivery]
    contacted = [p for p in deliveries if p.contact]
    aerial = [p for p in contacted if p.contact.aerial]
    shots = [s for p in mine for s in p.shots]
    second = [s for s in shots if s.phase == setpieces.SECOND_PHASE]

    return {
        "pieces": mine,
        "total": len(mine),
        "by_kind": Counter(p.kind for p in mine),
        "deliveries": len(deliveries),
        "contact_won": sum(1 for p in contacted if p.contact.attacking),
        "contact_total": len(contacted),
        "aerial_won": sum(1 for p in aerial if p.contact.attacking),
        "aerial_total": len(aerial),
        "shots": len(shots),
        "second": len(second),
        "goals": sum(1 for p in mine if p.goal),
        "zones": Counter(p.zone for p in deliveries if p.zone
                         and p.zone not in ("unknown", "short")),
    }


def headline(pieces, team: str) -> str:
    """
    The single most interesting thing this team's set pieces did.

    Ordered by what a reader would actually lead with: a goal, then second
    phase, then where the deliveries went, then the duel record. Falls back to
    a plain count rather than reaching for a claim the match does not support.
    """
    s = summary(pieces, team)

    if s["goals"]:
        scored = [p for p in s["pieces"] if p.goal]
        # A card about deliveries should not lead with a penalty: penalties are
        # excluded from every delivery visual, so the headline would describe
        # something the reader cannot see on the pitch below it.
        preferred = [p for p in scored if p.kind != PENALTY] or scored
        piece = preferred[0]
        shot = next((x for x in piece.shots if x.goal), None)
        kind = _plural(piece.kind, 1)
        phrase = ZONE_PHRASE.get(piece.zone, "")
        where = f" {phrase}" if phrase and piece.kind != PENALTY else ""
        # Taker and scorer are the same player on a penalty, and naming them
        # twice reads as a bug.
        if shot and piece.taker and shot.player != piece.taker:
            who = f", {piece.taker} to {shot.player}"
        elif shot and shot.player:
            who = f", scored by {shot.player}"
        else:
            who = ""
        extra = "" if len(scored) == 1 else f" One of {len(scored)} set-piece goals."
        return f"Scored from a {kind}{where}{who}.{extra}".strip()

    if s["shots"] and s["second"]:
        return (f"{s['second']} of {s['shots']} set-piece "
                f"{'shot' if s['shots'] == 1 else 'shots'} came after the "
                f"first contact, not off the delivery.")

    if s["zones"]:
        zone, count = s["zones"].most_common(1)[0]
        placed = sum(s["zones"].values())
        if count > 1 and placed > 1:
            phrase = ZONE_PHRASE.get(zone, f"to the {zone}")
            return f"{count} of {placed} deliveries into the box went {phrase}."

    if s["contact_total"]:
        return (f"Won first contact on {s['contact_won']} of "
                f"{s['contact_total']} deliveries.")

    if s["total"]:
        kind, count = s["by_kind"].most_common(1)[0]
        return f"{s['total']} dead balls, most of them {_plural(kind, 2)}."

    return "No qualifying set-pieces."


def strip(pieces, team: str) -> list[tuple[str, str]]:
    """
    The stat row: value then label. Counts and fractions only.

    Ordered by what the card is actually about. A graphic that runs out of room
    must lose a type count, never the second-phase fraction -- that is the
    number the whole app exists to show. Callers that truncate take from the
    end, so the payload sits at the front.
    """
    s = summary(pieces, team)
    cells: list[tuple[str, str]] = [(str(s["total"]), "Set-Pieces")]

    # Each label names its own denominator. Two fractions sitting side by side
    # with different bases -- one out of deliveries, one out of shots -- and
    # nothing saying which is which is how "5/5" ends up meaning nothing.
    if s["contact_total"]:
        cells.append((f"{s['contact_won']}/{s['contact_total']}",
                      "Deliveries Won"))
    cells.append((str(s["shots"]), "Shots"))
    if s["shots"]:
        cells.append((f"{s['second']}/{s['shots']}", "Shots, 2nd Phase"))
    if s["goals"]:
        cells.append((str(s["goals"]), "Goals"))
    if s["aerial_total"]:
        cells.append((f"{s['aerial_won']}/{s['aerial_total']}", "Aerials Won"))

    for kind in (CORNER, FREEKICK, THROW_IN, GOAL_KICK, PENALTY):
        if s["by_kind"].get(kind):
            cells.append((str(s["by_kind"][kind]), _plural(kind, 2).title()))
    return cells


# ---------------------------------------------------------------------------
# the copyable text report
# ---------------------------------------------------------------------------

def _split(pieces, predicate):
    """(matching, total) for a subset -- fractions, never a percentage."""
    subset = [p for p in pieces if predicate(p)]
    return len(subset), len(pieces)


def _phase_line(pieces) -> str:
    shots = [s for p in pieces for s in p.shots]
    if not shots:
        return "no shots"
    second = sum(1 for s in shots if s.phase == setpieces.SECOND_PHASE)
    word = "shot" if len(shots) == 1 else "shots"
    return f"{len(shots)} {word}, {second} of them second phase"


def _threat_lines(match, pieces, team: str) -> list[str]:
    """
    How much of this side's threat came from dead balls.

    Both measures are fractions with their totals shown, never a bare
    percentage: the npxG share here rests on a handful of shots, and a lone
    "36%" invites a precision the sample does not support.

    npxG is the measure that means something. Penalties are excluded from both
    sides of it -- one spot kick is worth more than most teams' entire
    set-piece output, so including it would report "they won a penalty" as if
    it said something about corners.

    xT is reported for the open-play continuation only. An open-play threat
    grid cannot price a dead ball, so the delivery itself contributes nothing;
    see lib/xt.
    """
    try:
        from . import xg as xg_lib, xt as xt_lib
    except Exception:
        return []
    out: list[str] = []
    try:
        frame = xg_lib.shots(match)
        seqs = {shot.seq for piece in pieces for shot in piece.shots}
        frame["setpiece"] = frame["seq"].isin(seqs)
        live = frame[(frame["penalty"] == 0) & (frame["team"] == team)]
        total = float(live["npxg"].sum())
        share = float(live[live["setpiece"]]["npxg"].sum())
        count = int(live["setpiece"].sum())
        if total:
            shots_word = "shot" if count == 1 else "shots"
            out.append(f"Set-piece npxG {share:.2f} of {total:.2f} "
                       f"(from {count} {shots_word}; penalties excluded)")
        pens = int(frame[(frame["team"] == team)]["penalty"].sum())
        if pens:
            out.append(f"Penalties {pens}, held out of every npxG figure above")
    except Exception:
        pass
    try:
        totals = xt_lib.totals(match)
        chain = xt_lib.setpiece_chain(pieces).get(team, 0.0)
        whole = totals.get(team, 0.0)
        if whole:
            out.append(f"Set-piece xT {chain:.2f} of {whole:.2f} open-play "
                       f"(chain only; the delivery itself is not priced)")
    except Exception:
        pass
    return out


def report(match, pieces) -> str:
    """
    The whole match as text, ready to paste.

    Structured the way someone writing about the game would want it: what
    happened overall, then split by half, then by game state, then by restart
    type, then every dead ball in order. Counts and fractions throughout -- a
    single match never supports a percentage, and this text is the most likely
    thing to be quoted out of context.
    """
    meta = match.meta
    home, away = meta["home_team"], meta["away_team"]
    lines: list[str] = []
    add = lines.append

    add(f"{home} {meta.get('score', '')} {away}")
    bits = [x for x in (meta.get("competition"), meta.get("venue"),
                        str(meta.get("start_date") or "")[:10]) if x]
    if bits:
        add(" · ".join(bits))
    add("Set-pieces — single match. Data from Opta.")
    add("")
    add("WHAT THE NUMBERS MEAN")
    for term, meaning in GLOSSARY:
        add(f"  {term} — {meaning}")
    add("")

    # --- per team -----------------------------------------------------------
    for team in (home, away):
        s = summary(pieces, team)
        if not s["total"]:
            continue
        mine = s["pieces"]
        add(f"{team.upper()}")
        add(f"  {s['total']} dead balls: " + ", ".join(
            f"{n} {_plural(k, n)}" for k, n in s["by_kind"].most_common()))
        if s["contact_total"]:
            add(f"  First contact won {s['contact_won']}/{s['contact_total']} deliveries")
        if s["aerial_total"]:
            add(f"  Aerial duels won {s['aerial_won']}/{s['aerial_total']}")
        add(f"  {_phase_line(mine)}")
        for line in _threat_lines(match, pieces, team):
            add(f"  {line}")
        if s["goals"]:
            for piece in [p for p in mine if p.goal]:
                scorer = next((x.player for x in piece.shots if x.goal), "")
                add(f"  GOAL {piece.clock} from a {_plural(piece.kind, 1)}"
                    + (f", {scorer}" if scorer else ""))
        if s["zones"]:
            add("  Delivered into: " + ", ".join(
                f"{n} {z}" for z, n in s["zones"].most_common()))
        add("")

    # --- halves -------------------------------------------------------------
    add("BY HALF")
    for label, keep in (("First half", lambda p: p.period == "FirstHalf"),
                        ("Second half", lambda p: p.period != "FirstHalf")):
        half = [p for p in pieces if keep(p)]
        if not half:
            continue
        h = sum(1 for p in half if p.team == home)
        shots = sum(len(p.shots) for p in half)
        add(f"  {label}: {len(half)} dead balls ({h} {home}, {len(half)-h} {away}), "
            f"{shots} shots")
    add("")

    # --- game state ---------------------------------------------------------
    # The scoreline a set piece was taken at changes what it was for. This is
    # the state at the moment of the restart, not the final score.
    add("BY GAME STATE")
    for team in (home, away):
        mine = [p for p in pieces if p.team == team]
        if not mine:
            continue
        buckets = {"leading": [], "level": [], "trailing": []}
        for piece in mine:
            diff = piece.home_score - piece.away_score
            if team == away:
                diff = -diff
            buckets["leading" if diff > 0 else "trailing" if diff < 0 else "level"].append(piece)
        parts = []
        for state in ("leading", "level", "trailing"):
            got = buckets[state]
            if got:
                shots = sum(len(p.shots) for p in got)
                tail = (f" ({shots} shot{'s' if shots != 1 else ''})"
                        if shots else "")
                parts.append(f"{len(got)} while {state}{tail}")
        if parts:
            add(f"  {team}: " + ", ".join(parts))
    add("")

    # --- ledger -------------------------------------------------------------
    add("EVERY DEAD BALL")
    for piece in pieces:
        contact = piece.contact
        who = f" → {contact.player} ({contact.type})" if contact else ""
        shot = piece.shots[0] if piece.shots else None
        out = ""
        if piece.goal:
            out = f" → GOAL {shot.player}" if shot else " → GOAL"
        elif shot:
            phase = "2nd" if shot.phase == setpieces.SECOND_PHASE else "1st"
            out = f" → {phase} phase shot, {shot.player}"
        # A goal kick's zone is computed for attacking-half deliveries and
        # means nothing here, so it is left off rather than printed as noise.
        zone = ("" if piece.kind == GOAL_KICK or piece.zone in ("", "unknown")
                else f", {piece.zone}")
        add(f"  {piece.clock} [{piece.state}] {piece.team} "
            f"{piece.kind.replace('_', ' ')} ({piece.subtype}){zone} — "
            f"{piece.taker}{who}{out}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# what the numbers mean
# ---------------------------------------------------------------------------

GLOSSARY = [
    ("First contact",
     "the first player to touch the ball after a delivery, either side."),
    ("Deliveries won",
     "deliveries where that first touch went to the delivering team."),
    ("First phase",
     "the shot IS the first contact — the ball is met directly, one touch "
     "from delivery to attempt."),
    ("Second phase",
     "someone touches it first and the shot comes after: a knockdown, a "
     "clearance worked back in, a scramble. Out of that team's set-piece "
     "shots, not out of its set-pieces."),
]


def glossary_text() -> str:
    return "\n".join(f"{term} — {meaning}" for term, meaning in GLOSSARY)
