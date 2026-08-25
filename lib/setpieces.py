"""
Set piece classification and second-phase chaining.

The classifier answers "what restart was this", the chain answers "what
happened next". They are separate on purpose: the chain is the part that makes
Trazado worth building, and it has to be verifiable against the feed's own
shot-situation tags without ever reading them.

Scope, per the spec:

- Corners: all of them, short ones included.
- Free kicks: attacking half only. Goal kicks and keeper throws are rejected
  explicitly rather than folded in -- roughly half of all FreekickTaken events
  are restarts we do not want.
- Throw-ins: only where the ball finishes inside the penalty area.
- Penalties: recorded in the ledger, excluded from every delivery visual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from . import qualifiers as Q
from .pitch import delivery_zone, distance, in_box, to_attacking_frame

# How long after a restart we keep looking for a shot. Long enough for a
# knockdown and a follow-up, short enough that unrelated open play does not
# drift in.
CHAIN_SECONDS = 15
CHAIN_EVENTS = 14

CORNER, FREEKICK, THROW_IN, PENALTY = "corner", "freekick", "throw_in", "penalty"
GOAL_KICK = "goal_kick"

# Subtypes. A restart's subtype is what actually distinguishes it -- "delivery"
# on its own says nothing, which is why throw-ins and corners carry their own.
DELIVERY, SHORT, DIRECT = "delivery", "short", "direct"

# Throw-ins. Only throws finishing in the box are kept at all, and those split
# cleanly in the data: across 40 matches their lengths ran 18 to 42 with a
# median of 27, taken from a median x of 85. A throw of 25+ units, or one
# launched from outside the final eighth, is the long-throw weapon; the rest
# are short throws worked into the box from close range.
THROW_LONG, THROW_NEAR = "long throw", "into box"
LONG_THROW_LENGTH = 25.0
LONG_THROW_ORIGIN = 75.0

# Goal kicks. 14 a match, 43% launched past halfway, and a quarter of all of
# them are contested in the air within three events -- which is the same
# first-contact-then-second-ball question the rest of the app asks, just
# starting from the other box. They are kept in the ledger and counted, and
# excluded from the attacking-half delivery map, where they do not belong.
GK_LAUNCHED, GK_SHORT = "launched", "played short"

FIRST_PHASE, SECOND_PHASE = "first", "second"


@dataclass
class Contact:
    """The first touch after a delivery."""
    player: str
    team: str
    type: str
    minute: int
    second: int
    x: float | None
    y: float | None
    seq: int
    attacking: bool          # did the delivering team win it
    aerial: bool
    headed: bool
    keeper: bool

    @property
    def outcome(self) -> str:
        if self.keeper:
            return "keeper"
        return "won" if self.attacking else "lost"


@dataclass
class Link:
    """One touch between the first contact and the shot."""
    player: str
    team: str
    type: str
    x: float | None
    y: float | None
    end_x: float | None
    end_y: float | None
    seq: int
    attacking: bool


@dataclass
class Shot:
    player: str
    team: str
    type: str
    x: float | None
    y: float | None
    seq: int
    phase: str               # first or second
    goal: bool
    on_target: bool
    blocked: bool
    situation: str           # the feed's own tag, for validation only


@dataclass
class SetPiece:
    kind: str
    subtype: str
    minute: int
    second: int
    period: str
    team: str
    taker: str
    x: float | None
    y: float | None
    end_x: float | None
    end_y: float | None
    complete: bool
    seq: int
    length: float | None = None
    angle: float | None = None
    zone: str = ""
    home_score: int = 0
    away_score: int = 0
    contact: Contact | None = None
    shots: list[Shot] = field(default_factory=list)
    chain: list[Link] = field(default_factory=list)

    @property
    def clock(self) -> str:
        return f"{self.minute}:{self.second:02d}"

    @property
    def state(self) -> str:
        return f"{self.home_score}-{self.away_score}"

    @property
    def led_to_shot(self) -> bool:
        return bool(self.shots)

    @property
    def goal(self) -> bool:
        return any(s.goal for s in self.shots)

    @property
    def phase(self) -> str:
        """Which phase produced the first shot, if any."""
        return self.shots[0].phase if self.shots else ""

    @property
    def is_delivery(self) -> bool:
        """
        Whether this belongs on the attacking-half delivery map.

        A penalty is not a delivery, a direct attempt is a shot, and a goal
        kick starts from the other end of the pitch.
        """
        return (self.kind not in (PENALTY, GOAL_KICK)
                and self.subtype != DIRECT)

    @property
    def contested(self) -> bool:
        """First contact was an aerial duel."""
        return bool(self.contact and self.contact.aerial)


def _clock(row) -> int:
    return int(row["minute"]) * 60 + int(row["second"])


def _quals(row) -> dict:
    value = row["qualifiers"]
    return value if isinstance(value, dict) else {}


def _shot_situation(quals: dict) -> str:
    for name in Q.SHOT_SITUATIONS:
        if name in quals:
            return name
    return ""


def _gk_subtype(end_x) -> str:
    """Launched or played short, decided by whether the ball crosses halfway."""
    if end_x is None or pd.isna(end_x):
        return GK_SHORT
    return GK_LAUNCHED if float(end_x) >= 50 else GK_SHORT


def _classify(row, quals: dict) -> tuple[str, str] | None:
    """
    Name the restart, or return None when this event is not one.

    Order matters. A penalty carries FreekickTaken on some feeds, and a goal
    kick always does, so both are settled before the free kick branch.
    """
    is_shot = bool(row["is_shot"])

    if Q.PENALTY in quals:
        # One penalty leaves four events carrying this qualifier: the foul won,
        # the foul conceded, the keeper's PenaltyFaced, and the kick itself.
        # Only the kick is the penalty; counting the rest inflated the rate to
        # about five times what football actually produces.
        return (PENALTY, DIRECT) if is_shot else None

    # A direct free kick attempt is logged as a shot carrying DirectFreekick,
    # never as a pass carrying FreekickTaken. Without this branch every direct
    # attempt in the match disappears from the ledger.
    if "DirectFreekick" in quals and is_shot:
        return (FREEKICK, DIRECT)

    if Q.CORNER in quals:
        # A corner played short is not a delivery and must not be counted as
        # one. Swing direction would be the other axis here, but it needs the
        # taker's foot, which the feed does not give on a pass.
        return (CORNER, DELIVERY if in_box(row["end_x"], row["end_y"]) else SHORT)

    if Q.THROW_IN in quals:
        # Throws only count when the ball actually reaches the box.
        if not in_box(row["end_x"], row["end_y"]):
            return None
        length = quals.get("Length")
        origin = row["x"]
        far = (isinstance(length, (int, float)) and length >= LONG_THROW_LENGTH)
        deep = (origin is not None and not pd.isna(origin)
                and origin <= LONG_THROW_ORIGIN)
        return (THROW_IN, THROW_LONG if (far or deep) else THROW_NEAR)

    if Q.KEEPER_THROW in quals:
        return None  # a throw is a keeper's choice, not a dead ball restart

    if Q.GOAL_KICK in quals:
        return (GOAL_KICK, _gk_subtype(row["end_x"]))

    if Q.FREEKICK in quals or Q.FREEKICK_INDIRECT in quals:
        x = row["x"]
        if x is None or pd.isna(x):
            return None

        # A free kick taken by the goalkeeper in his own half is a keeper
        # restart, not an attacking set piece: same decision, same launch, same
        # first-contact question as a goal kick. Roughly five a match, and the
        # own-half rule was throwing every one of them away.
        if row["is_keeper"] and x < 50:
            return (GOAL_KICK, _gk_subtype(row["end_x"]))

        if x < 50:
            return None  # own half; not an attacking set-piece
        return (FREEKICK, DELIVERY if in_box(row["end_x"], row["end_y"]) else SHORT)

    return None


def _running_score(events: pd.DataFrame, home: str) -> list[tuple[int, int]]:
    """Scoreline as it stood before each event."""
    out, h, a = [], 0, 0
    for _, row in events.iterrows():
        out.append((h, a))
        if row["is_goal"]:
            own = "OwnGoal" in _quals(row)
            scoring_home = (row["team"] == home) != own
            if scoring_home:
                h += 1
            else:
                a += 1
    return out


def _touches_ball(event) -> bool:
    """
    Whether an event represents a player getting to the ball.

    Not simply `is_touch`: the feed sets that False on Aerial, BallRecovery and
    Challenge, so a rule built on it alone walks straight past the duel that
    decided the set piece.
    """
    if event["type"] in Q.NON_CONTACT_TYPES:
        return False
    return bool(event["is_touch"]) or event["type"] in Q.CONTEST_TYPES


def _first_contact(window: pd.DataFrame, team: str) -> Contact | None:
    for _, event in window.iterrows():
        if not _touches_ball(event):
            continue
        quals = _quals(event)
        return Contact(
            player=str(event["player"] or ""),
            team=str(event["team"] or ""),
            type=str(event["type"]),
            minute=int(event["minute"]), second=int(event["second"]),
            x=event["x"], y=event["y"], seq=int(event["seq"]),
            attacking=(event["team"] == team),
            aerial=event["type"] == "Aerial",
            headed=("Head" in quals or "HeadPass" in quals),
            keeper=bool(event["is_keeper"]) or event["type"] in Q.KEEPER_TYPES,
        )
    return None


def _links(window: pd.DataFrame, contact, shot, team: str) -> list[Link]:
    """
    The touches between the first contact and the shot.

    A duel is logged twice, once per side, at the same instant and mirrored
    across the pitch. Both halves describe one contest, so the second is
    dropped -- keeping it draws a phantom extra touch on top of the first.
    """
    if contact is None or shot is None:
        return []
    out: list[Link] = []
    # Seeded with the first contact itself: the other half of that same duel
    # sits in the window and would otherwise be drawn as a phantom extra touch
    # on the identical spot.
    seen: set[tuple] = {(contact.minute, contact.second, contact.type)}
    for _, event in window.iterrows():
        seq = int(event["seq"])
        if seq <= contact.seq or seq >= shot.seq:
            continue
        if not _touches_ball(event):
            continue
        key = (int(event["minute"]), int(event["second"]), str(event["type"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(Link(
            player=str(event["player"] or ""), team=str(event["team"] or ""),
            type=str(event["type"]), x=event["x"], y=event["y"],
            end_x=event["end_x"], end_y=event["end_y"], seq=seq,
            attacking=(event["team"] == team)))
    return out


def _shots(window: pd.DataFrame, piece_clock: int, team: str,
           contact: Contact | None) -> list[Shot]:
    found = []
    for _, event in window.iterrows():
        if _clock(event) - piece_clock > CHAIN_SECONDS:
            break
        if not event["is_shot"] or event["team"] != team:
            continue
        quals = _quals(event)
        phase = (FIRST_PHASE
                 if contact is not None and int(event["seq"]) == contact.seq
                 else SECOND_PHASE)
        found.append(Shot(
            player=str(event["player"] or ""),
            team=str(event["team"] or ""),
            type=str(event["type"]),
            x=event["x"], y=event["y"], seq=int(event["seq"]),
            phase=phase,
            goal=bool(event["is_goal"]),
            on_target=event["type"] in ("Goal", "SavedShot"),
            blocked=event["type"] == "BlockedShot",
            situation=_shot_situation(quals),
        ))
    return found


def extract(match) -> list[SetPiece]:
    """Every qualifying dead ball in a match, in order."""
    events = match.events
    home = match.meta.get("home_team", "")
    scores = _running_score(events, home)

    pieces = []
    for position, (_, row) in enumerate(events.iterrows()):
        quals = _quals(row)
        named = _classify(row, quals)
        if named is None:
            continue
        kind, subtype = named

        team = str(row["team"] or "")
        # Defensive actions are logged in the defending team's own frame, so
        # the window has to be restated before first contact means anything.
        framed = to_attacking_frame(events, team)
        window = framed[framed["seq"] > row["seq"]].head(CHAIN_EVENTS)

        contact = None if subtype == DIRECT else _first_contact(window, team)
        shots = _shots(window, _clock(row), team, contact)

        # A direct attempt is its own shot; there is no chain to walk.
        if subtype == DIRECT:
            shots = [Shot(
                player=str(row["player"] or ""), team=team, type=str(row["type"]),
                x=row["x"], y=row["y"], seq=int(row["seq"]), phase=FIRST_PHASE,
                goal=bool(row["is_goal"]),
                on_target=row["type"] in ("Goal", "SavedShot"),
                blocked=row["type"] == "BlockedShot",
                situation=_shot_situation(quals),
            )]

        links = _links(window, contact, shots[0] if shots else None, team)
        home_score, away_score = scores[position]
        pieces.append(SetPiece(
            kind=kind, subtype=subtype,
            minute=int(row["minute"]), second=int(row["second"]),
            period=str(row["period"]), team=team,
            taker=str(row["player"] or ""),
            x=row["x"], y=row["y"], end_x=row["end_x"], end_y=row["end_y"],
            complete=bool(row["success"]),
            seq=int(row["seq"]),
            length=quals.get("Length"), angle=quals.get("Angle"),
            zone=(delivery_zone(row["end_x"], row["end_y"], row["y"])
                  if subtype != DIRECT else ""),
            home_score=home_score, away_score=away_score,
            contact=contact, shots=shots, chain=links,
        ))
    return pieces


def ledger(pieces: list[SetPiece]) -> pd.DataFrame:
    """
    Every dead ball as a table. The backbone of the text report, and the
    thing that proves nothing is being quietly dropped.
    """
    rows = []
    for piece in pieces:
        contact = piece.contact
        shot = piece.shots[0] if piece.shots else None
        rows.append({
            "min": piece.clock,
            "state": piece.state,
            "team": piece.team,
            "type": piece.kind,
            "sub": piece.subtype,
            "taker": piece.taker,
            "zone": piece.zone,
            "len": piece.length,
            "complete": piece.complete,
            "first_contact": contact.player if contact else "",
            "contact_by": ("attack" if contact and contact.attacking
                           else "defence" if contact else ""),
            "contact_type": contact.type if contact else "",
            "headed": contact.headed if contact else False,
            "shots": len(piece.shots),
            "phase": piece.phase,
            "shooter": shot.player if shot else "",
            "outcome": shot.type if shot else "",
            "goal": piece.goal,
        })
    return pd.DataFrame(rows)


def match_goals(match) -> list[dict]:
    """
    Every goal in the match, not only the set piece ones.

    The timeline plots dead balls *against the scoreline*, and the scoreline is
    the real one. Stepping it on set piece goals alone draws a flat line
    through a 4-2 and quietly misrepresents the game state every restart was
    taken in -- which is the whole point of that chart.
    """
    home = match.meta.get("home_team", "")
    out = []
    for _, row in match.events.iterrows():
        if not row["is_goal"]:
            continue
        quals = row["qualifiers"] if isinstance(row["qualifiers"], dict) else {}
        own = "OwnGoal" in quals
        out.append({
            "minute": int(row["minute"]),
            "for_home": (row["team"] == home) != own,
            "player": str(row["player"] or ""),
            "own": own,
            "seq": int(row["seq"]),
        })
    return out
