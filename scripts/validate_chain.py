"""
Validate the production classifier and chain against the feed's own tags.

This exercises lib.setpieces directly rather than reimplementing it. A checker
that carries its own copy of the logic passes while the shipped code is broken,
which is exactly what happened when first contact was skipping aerial duels.
"""
import os, sys, glob, random, warnings, statistics, collections
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import setpieces, whoscored
from lib.pitch import distance

FEED_TAGS = ("FromCorner", "SetPiece", "DirectFreekick", "ThrowinSetPiece", "Penalty")

CACHE = os.path.expanduser("~/soccerdata/data/WhoScored/events")
paths = [p for p in sorted(glob.glob(os.path.join(CACHE, "*", "*.json")))
         if os.path.getsize(p) > 1000]
random.seed(11); random.shuffle(paths)
paths = paths[:int(sys.argv[1]) if len(sys.argv) > 1 else 120]

gaps, tp, fp, fn, n = [], 0, 0, 0, 0
phases, contacts = collections.Counter(), collections.Counter()
for path in paths:
    try:
        match = whoscored.from_file(path)
    except Exception:
        continue
    n += 1
    pieces = setpieces.extract(match)

    for piece in pieces:
        if piece.contact and piece.end_x is not None and piece.contact.x is not None:
            gap = distance(piece.end_x, piece.end_y, piece.contact.x, piece.contact.y)
            if gap is not None and piece.is_delivery:
                gaps.append(gap)
        if piece.contact:
            contacts[piece.contact.type] += 1
        for shot in piece.shots:
            phases[shot.phase] += 1

    # The feed has no "from a goal kick" tag, so chaining those and then
    # counting them as disagreements compares against something that does not
    # exist. They are excluded from this comparison only, not from the app.
    ours = {s.seq for p in pieces if p.kind != setpieces.GOAL_KICK
            for s in p.shots}
    feed = set()
    for _, row in match.events.iterrows():
        if not row["is_shot"]:
            continue
        quals = row["qualifiers"] if isinstance(row["qualifiers"], dict) else {}
        if any(t in quals for t in FEED_TAGS):
            feed.add(int(row["seq"]))
    tp += len(ours & feed); fp += len(ours - feed); fn += len(feed - ours)

print(f"matches: {n}\n")
print("--- 1. mirroring: delivery end -> first contact ---")
print(f"  n={len(gaps)}  median {statistics.median(gaps):.1f}m  mean {statistics.mean(gaps):.1f}m")
buckets = collections.Counter()
for g in gaps:
    buckets["<5m" if g < 5 else "5-15m" if g < 15 else "15-30m" if g < 30 else ">30m"] += 1
for k in ("<5m", "5-15m", "15-30m", ">30m"):
    print(f"  {k:7s} {buckets[k]:5d}  ({100*buckets[k]/len(gaps):.1f}%)")

print("\n--- 2. our chain vs the feed's shot-situation tags ---")
print(f"  agree {tp} | we found, feed didn't {fp} | feed found, we missed {fn}")
print(f"  recall    {100*tp/max(tp+fn,1):.1f}%")
print(f"  precision {100*tp/max(tp+fp,1):.1f}%")

print("\n--- 3. phase split ---")
print(f"  {dict(phases)}")
print("\n--- 4. first contact types (aerials must not be zero) ---")
for t, c in contacts.most_common(8):
    print(f"  {t:16s} {c}")
