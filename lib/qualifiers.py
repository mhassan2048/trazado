"""
WhoScored qualifier vocabulary, grouped by what Trazado uses it for.

The feed attaches an untyped list of qualifiers to every event. Most carry no
value and act as flags; a few (Length, Angle, PassEndX/Y, GoalMouthY/Z, Zone)
carry a string value. We keep the raw dict on every row and flatten only the
groups the visuals actually read.
"""

# --- restart type -----------------------------------------------------------
# Present on the Pass event that restarts play. GoalKick and KeeperThrow are
# restarts we exclude; they are listed so the classifier can reject rather than
# silently fold them into "free kick".
CORNER = "CornerTaken"
FREEKICK = "FreekickTaken"
FREEKICK_INDIRECT = "IndirectFreekickTaken"
THROW_IN = "ThrowIn"
GOAL_KICK = "GoalKick"
KEEPER_THROW = "KeeperThrow"
PENALTY = "Penalty"

# --- shot situation ---------------------------------------------------------
# WhoScored's own labelling of where a shot came from. This is the feed telling
# us what our second-phase chaining should independently conclude, so it doubles
# as a validation channel rather than a substitute for the chain.
SHOT_SITUATIONS = (
    "FromCorner",
    "SetPiece",
    "DirectFreekick",
    "Penalty",
    "ThrowinSetPiece",
    "FastBreak",
    "RegularPlay",
)

# --- where the shot was struck from, per the feed's own grid ----------------
SHOT_ZONES = (
    "SmallBoxLeft", "SmallBoxCentre", "SmallBoxRight",
    "BoxLeft", "BoxCentre", "BoxRight",
    "DeepBoxLeft", "DeepBoxRight",
    "OutOfBoxLeft", "OutOfBoxCentre", "OutOfBoxRight",
    "OutOfBoxDeepLeft", "OutOfBoxDeepRight",
    "ThirtyFivePlusLeft", "ThirtyFivePlusCentre", "ThirtyFivePlusRight",
)

# --- where it finished, in the goal frame ----------------------------------
GOAL_PLACEMENTS = (
    "LowLeft", "LowCentre", "LowRight",
    "HighLeft", "HighCentre", "HighRight",
    "MissLeft", "MissRight", "MissHigh", "MissHighLeft", "MissHighRight",
    "PostLeft", "PostRight", "PostHigh",
    "Blocked", "CloseLeft", "CloseRight", "CloseHigh",
    "CloseLeftAndHigh", "CloseRightAndHigh",
)

# --- body part --------------------------------------------------------------
# Reliable on shots. On passes the feed tags HeadPass but rarely tags a foot,
# so do not read foot from a delivery event -- see docs in classify.py.
BODY_PARTS = ("Head", "LeftFoot", "RightFoot", "OtherBodyPart")

# --- chain links ------------------------------------------------------------
# LayOff and ShotAssist are what make second-phase separable: a LayOff is the
# knockdown, a ShotAssist is the ball that became the shot.
CHAIN = (
    "Assisted", "IntentionalAssist", "IntentionalGoalAssist",
    "KeyPass", "ShotAssist", "LayOff", "Throughball",
    "Cross", "BlockedCross", "Chipped", "HeadPass",
    "FirstTouch", "LeadingToAttempt", "LeadingToGoal",
)

# --- goalkeeper -------------------------------------------------------------
KEEPER = (
    "HighClaim", "Collected", "Punch", "Hands", "Parried", "ParriedSafe",
    "ParriedDanger", "DivingSave", "StandingSave", "KeeperSaveInTheBox",
    "KeeperSaveObox", "KeeperThrow", "GoalKick", "FromShotOffTarget",
)

# --- blocks and defensive context ------------------------------------------
DEFENSIVE = (
    "OutfielderBlock", "SixYardBlock", "Offensive", "Defensive",
    "BlockedX", "BlockedY", "Blocked",
)

# Qualifiers carrying a parseable numeric value.
NUMERIC = ("Length", "Angle", "PassEndX", "PassEndY", "GoalMouthY", "GoalMouthZ",
           "BlockedX", "BlockedY", "RelatedEventId")

# Event `type.displayName` values that are shots.
SHOT_TYPES = frozenset({
    "Goal", "SavedShot", "MissedShots", "MissedShot",
    "ShotOnPost", "BlockedShot", "AttemptSaved", "Attempt",
})

# Event types that are goalkeeper actions in their own right.
KEEPER_TYPES = frozenset({
    "Save", "Claim", "Punch", "KeeperPickup", "KeeperSweeper", "SmotherWon",
})

# Types that contest the ball but carry isTouch = False in the feed. Aerial is
# the one that matters: every aerial duel in a match is flagged False, so a
# first-contact rule built on isTouch alone skips the duels that decide most
# set pieces and attributes contact to whatever happened next.
CONTEST_TYPES = frozenset({
    "Aerial", "BallRecovery", "Challenge", "Interception", "Block",
    "Save", "Claim", "Punch", "KeeperPickup", "KeeperSweeper", "Smother",
})

# Event types that never represent a touch on the ball and so can never be a
# first contact. Used when walking forward from a delivery.
NON_CONTACT_TYPES = frozenset({
    "CornerAwarded", "Card", "SubstitutionOn", "SubstitutionOff",
    "FormationChange", "FormationSet", "End", "Start", "TeamSetUp",
    "OffsideGiven", "PenaltyFaced", "ChanceMissed", "Delay", "DelayEnd",
})
