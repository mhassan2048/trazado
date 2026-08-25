"""Parse cached WhoScored blobs and report what Trazado can see in them."""
import os, sys, glob, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.whoscored import from_file
from lib import qualifiers as Q

CACHE = os.path.expanduser("~/soccerdata/data/WhoScored/events")

def report(path):
    m = from_file(path)
    ev = m.events
    q = ev["qualifiers"]
    has = lambda name: q.apply(lambda d: name in d)

    print(f"\n{'='*78}\n{m.meta['match_name']}  {m.meta['score']}  ({m.meta['venue']}, {str(m.meta['start_date'])[:10]})")
    print(f"  {len(ev)} events | {len(m.players)} players | ref {m.meta['referee']} | att {m.meta['attendance']}")
    print(f"  formations: {m.meta['home_formations'][0]['name'] if m.meta['home_formations'] else '?'}"
          f" v {m.meta['away_formations'][0]['name'] if m.meta['away_formations'] else '?'}")

    heights = m.players["height"].dropna()
    print(f"  heights: {len(heights)}/{len(m.players)} present, "
          f"{heights.min():.0f}-{heights.max():.0f}cm, tallest "
          f"{m.players.loc[m.players['height'].idxmax(), 'player']}")

    print("  restarts: " + "  ".join(
        f"{n}={int(has(t).sum())}" for n, t in
        [("corner", Q.CORNER), ("fk", Q.FREEKICK), ("fk-ind", Q.FREEKICK_INDIRECT),
         ("throw", Q.THROW_IN), ("goalkick", Q.GOAL_KICK), ("pen", Q.PENALTY)]))

    shots = ev[ev.is_shot]
    sit = collections.Counter()
    for d in shots["qualifiers"]:
        for s in Q.SHOT_SITUATIONS:
            if s in d:
                sit[s] += 1
                break
    print(f"  shots: {len(shots)} -> {dict(sit)}")
    print(f"  goalmouth placement on {shots['goal_mouth_y'].notna().sum()}/{len(shots)} shots")
    print(f"  chain tags: layoff={int(has('LayOff').sum())} "
          f"shotassist={int(has('ShotAssist').sum())} assisted={int(has('Assisted').sum())} "
          f"relatedEvent={int(ev['related_event_id'].notna().sum())}")
    print(f"  keeper events: {dict(collections.Counter(ev[ev.type.isin(Q.KEEPER_TYPES)]['type']))}")
    print(f"  length/angle on {int(has('Length').sum())} passes")
    return m

paths = sys.argv[1:] or sorted(glob.glob(os.path.join(CACHE, "*", "*.json")))[:0]
if not paths:
    for league in sorted(os.listdir(CACHE)):
        found = sorted(glob.glob(os.path.join(CACHE, league, "*.json")))
        if found:
            paths.append(found[0])
    paths = paths[:6]

for p in paths:
    try:
        report(p)
    except Exception as exc:
        print(f"\n!! {os.path.basename(p)}: {type(exc).__name__}: {exc}")
