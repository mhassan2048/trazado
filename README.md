# Trazado

Set-piece analysis for a single match, across the big five leagues and the
Champions League.

Trazado describes what happened at set-pieces in one match. It does not store
data, does not aggregate across matches, and never claims what a team or player
tends to do. Every match is fetched fresh from WhoScored; nothing is persisted
between visits.

The differentiator is **second phase** — separating a shot taken off the
delivery from one taken after the first contact. Roughly two thirds of
set-piece shots fall into the latter, and that is the part most analysis skips.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Pick a competition, pick a fixture, and the match is fetched and analysed.

## What it produces

- Delivery map, second-phase chains, aerial duels by zone, goal kicks, and a
  timeline of every dead ball against the scoreline
- A branded 4:5 export card for each of those, per team
- A full text report: per team, by half, by game state, then every dead ball
- A ledger of every restart, with an audit trail of what was rejected and why

## Layout

| path | |
|---|---|
| `app.py` | routing |
| `lib/whoscored.py` | fetch and parse; keeps the raw qualifier list |
| `lib/setpieces.py` | classifier and second-phase chaining |
| `lib/readout.py` | the text report and card captions |
| `lib/pitch.py` | coordinate frames and zones |
| `ui/charts.py` | every visual, as `draw_*` into a given rectangle |
| `ui/export.py` | the export card frame |
| `scripts/` | ledger audit and chain validation |

`CLAUDE.md` is the project spec and carries the reasoning behind the data
decisions, including the traps in the feed. Read it before changing anything
about classification or coordinates.

## Checks

```bash
python scripts/ledger.py <match-id>      # ledger + audit of every rejection
python scripts/validate_chain.py 60      # chain vs the feed's own tags
```

Data from Opta via WhoScored. Club crests and competition logos are trademarks
of their respective owners.
