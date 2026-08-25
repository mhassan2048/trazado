"""
Print the set piece ledger for one match, plus an audit of what was rejected.

The audit half matters as much as the ledger: it names every dead ball the
classifier chose not to keep, so "nothing is silently dropped" is something you
can read rather than something you have to trust.
"""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from lib import qualifiers as Q, setpieces, whoscored
from lib.pitch import in_box

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 200)

target = sys.argv[1] if len(sys.argv) > 1 else None
if target and os.path.exists(target):
    match = whoscored.from_file(target)
else:
    match = whoscored.fetch(target or 1903117)

print(f"{match.meta['match_name']}  {match.meta['score']}  "
      f"{match.meta['venue']}  {str(match.meta['start_date'])[:10]}")
print(f"{len(match.events)} events\n")

pieces = setpieces.extract(match)
frame = setpieces.ledger(pieces)
print("=" * 118)
print(f"LEDGER — {len(pieces)} dead balls")
print("=" * 118)
print(frame.to_string(index=False))

# --- audit: every restart in the feed, kept or rejected, with the reason ----
print("\n" + "=" * 118)
print("AUDIT — every restart the feed contains")
print("=" * 118)
kept = {p.seq for p in pieces}
reasons = collections.Counter()
rejected = []
for _, row in match.events.iterrows():
    quals = row["qualifiers"] if isinstance(row["qualifiers"], dict) else {}
    tags = [t for t in (Q.CORNER, Q.FREEKICK, Q.FREEKICK_INDIRECT, Q.THROW_IN,
                        Q.GOAL_KICK, Q.KEEPER_THROW, Q.PENALTY, "DirectFreekick")
            if t in quals]
    if not tags:
        continue
    if int(row["seq"]) in kept:
        reasons["kept"] += 1
        continue
    if Q.GOAL_KICK in quals:
        why = "goal kick"
    elif Q.KEEPER_THROW in quals:
        why = "keeper throw"
    elif Q.THROW_IN in quals:
        why = "throw-in, ball not in box"
    elif (Q.FREEKICK in quals or Q.FREEKICK_INDIRECT in quals):
        why = "free kick, own half"
    else:
        why = "unclassified — INVESTIGATE"
    reasons[why] += 1
    rejected.append((f"{row['minute']}:{int(row['second']):02d}", row["team"],
                     "+".join(tags), why))

for why, count in reasons.most_common():
    print(f"  {count:4d}  {why}")

unexplained = [r for r in rejected if "INVESTIGATE" in r[3]]
print(f"\n  unexplained rejections: {len(unexplained)}")
for r in unexplained[:12]:
    print(f"     {r[0]:>7} {str(r[1])[:16]:16s} {r[2]:40s} {r[3]}")

# --- chain check against the feed's own tags -------------------------------
print("\n" + "=" * 118)
print("CHAIN CHECK — our chain vs the feed's shot-situation tags")
print("=" * 118)
ours = {s.seq for p in pieces for s in p.shots}
feed = set()
for _, row in match.events.iterrows():
    if not row["is_shot"]:
        continue
    quals = row["qualifiers"] if isinstance(row["qualifiers"], dict) else {}
    if any(t in quals for t in ("FromCorner", "SetPiece", "DirectFreekick",
                                "ThrowinSetPiece", "Penalty")):
        feed.add(int(row["seq"]))
print(f"  agree {len(ours & feed)} | we found, feed didn't {len(ours - feed)} "
      f"| feed found, we missed {len(feed - ours)}")

phases = collections.Counter(s.phase for p in pieces for s in p.shots)
print(f"  phase split: {dict(phases)}")
kinds = collections.Counter(p.kind for p in pieces)
print(f"  by type: {dict(kinds)}")
print(f"  set piece goals: {sum(1 for p in pieces if p.goal)}")
