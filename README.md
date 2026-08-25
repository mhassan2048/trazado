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

## Deploying

Trazado scrapes WhoScored on demand, and WhoScored throttles **datacentre
addresses far harder than home connections**. A hosted deploy shares a small
pool of egress IPs with every other app on the platform, so the same request
pattern that works from a laptop can be refused almost entirely from
Streamlit Community Cloud.

Three things matter, in order of how much they help.

### 1. Give it a cleaner exit address

The single reliable fix. Any HTTP or SOCKS5 proxy whose exit is not a
datacentre range:

```bash
export TRAZADO_PROXY=socks5://user:pass@host:port
```

On Streamlit Cloud there are no environment variables — put it in
**Settings → Secrets** instead:

```toml
TRAZADO_PROXY = "socks5://user:pass@host:port"
```

Both are read automatically; the environment variable wins if you set both.
Credentials are never echoed back in status output or error messages.

### 2. Self-host

Anywhere with its own IP — a VPS, a home machine, a Tailscale funnel — avoids
the shared-pool problem entirely. `streamlit run app.py` is the whole
deployment; there is no database and nothing to persist.

### 3. Tune the request pressure

Defaults are already conservative. Loosen them if your address is trusted,
tighten them if you are still being refused:

| variable | default | what it does |
|---|---|---|
| `TRAZADO_PARALLEL` | `2` | simultaneous requests to WhoScored |
| `TRAZADO_STAGGER` | `0.35` | seconds between request starts |

Six-way parallel looks like a scraper; two requests spread over a couple of
seconds looks like a browser. The cold competition chooser takes about eight
seconds either way once, then is cached for fifteen minutes.

### Reading the failure

The chooser tells you which case you are in. **"Coming soon"** means nothing
has been played yet. **"Unavailable"** means the fetch failed, and the banner
underneath carries the reason. An unavailable competition stays clickable,
because clicking is how you retry.
