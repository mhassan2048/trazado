# Trazado

A matchday web app that analyses set pieces only, for the big five leagues and the Champions League.

This file is the project spec. It was agreed in planning before any code was written. Read it before making design or data decisions, and update it when a decision changes.

---

## 1. What this is, and what it is not

Trazado describes what happened in a single match. It does not store data, does not aggregate across matches, and never claims what a team or player tends to do.

Positioning: there are many generic match analysis apps. Trazado is narrow on scope and high on craft. The differentiator is set piece second phase work plus visual quality, not breadth of coverage.

Stack: Streamlit. Lightweight, stateless, scrape on demand, nothing persisted per game.

### Hard rules

- Every match is fetched fresh. Nothing is cached between visits.
- No claims of tendency. Say "five of seven deliveries went near post", never "prefers the near post".
- No percentages where the denominator is under ten. Use fractions.
- No xG anywhere, in data or visuals. Danger is communicated through location and outcome only.
- Sections render only when the match contains that content. Never render an empty panel.

---

## 2. Data

### Source

WhoScored only. Trazado has its own scraper at `lib/whoscored.py`, adapted from the Zauberpass matchday one but not shared with it.

**Transfermarkt is out.** WhoScored's own match blob carries height, weight, age, position, shirt number, starting XI, formations with their minute windows, manager, venue, referee and attendance. Height is present for 99.1% of players across a 250-match sample, so the external identity source bought us nothing and cost a name-matching step, a manual approval flow, and a dependency on an external drive.

Player height still matters more here than in the midfielder model. It drives aerial target profiling and defensive mismatch. It just comes from the same fetch as everything else now.

The one thing Transfermarkt had that WhoScored does not is footedness. See the swing direction note below.

### Current season only, resolved live

Trazado has no interest in past seasons and stores no ids that go stale. Only `region_id` and `tournament_id` are held in code; they are stable for the life of a competition. Season and stage ids are resolved at run time.

This is not a theoretical concern. The ids read from cache while building this were 2025/26; by the time they were tested live the season had rolled to 2026/27 and every one of them was wrong. Hard coding them means the app breaks silently each August.

The discovery is cheaper than expected. A competition's landing page — `/Regions/{region}/Tournaments/{tournament}` — redirects to whatever season is live and carries three things at once:

- the season list, with the live one marked `selected` (note the markup is HTML-entity encoded, so unescape before parsing)
- the stage id
- the fixtures for the round currently being played, embedded as JSON inside an HTML comment

So the common case costs one request per competition. Six run in parallel in under two seconds. Browsing to another matchweek uses `/tournaments/{stage_id}/data/?d=YYYYMM`, which needs the stage id the landing page already gave us.

A competition that has published no stage yet is the normal pre-season state, not an error. The Champions League sits there through the summer, which is exactly the state section 6 wants its card to show.

Fixture status `6` means finished. Anything else is unplayed, in progress or abandoned, and has no set piece data worth opening.

**Trap: the embedded fixtures are not the played ones.** They are whichever round WhoScored is currently featuring, and the moment a round completes they flip to the next one. Counting them caught this live — the Premier League showed ten played matches in the morning and zero a few hours later, while ten matches had in fact been played that week. Never count the embedded list. Ask the date window, which spans the month boundary and hits the month endpoint.

### On caching, and the schedule snapshot

Section 1 governs match event data: that is never held between visits. The schedule layer — which season is live, which fixtures exist — is navigation metadata, and it is not fetched on page load at all.

**The schedule is precomputed out of band.** A GitHub Action runs `scripts/fetch_schedule.py` and commits `data/schedule.json`; the app reads that file. The chooser and the fixture list then cost zero network requests and render in about a millisecond.

This was forced by a real failure, not chosen for speed. The hosted deploy loaded only half the leagues while the same code loaded all six locally. The cause is the request pattern rather than the code: opening the chooser fans out to six competitions at once, and a shared datacentre address gets that burst refused where a home connection does not. Nothing done inside a page load fixes this — the page load is the problem. Caching only froze the failure for fifteen minutes; the circuit breaker made it worse, converting "two refused" into "everything after runs with no retries", which is exactly the half-empty chooser that was reported.

Moving the fetch off the page load fixes it properly. The Action is not racing a user's page load, so it can retry patiently over minutes, and a run that fails entirely keeps the previous snapshot rather than showing an empty app.

Three layers, in order: a fresh snapshot; a live fetch if the snapshot is missing or older than `TRAZADO_SNAPSHOT_STALE_HOURS` (default 6); the stale snapshot if that fetch fails too. So a broken Action degrades to the old behaviour, and a broken Action *plus* a refused fetch still renders yesterday's fixtures. All three paths are exercised, not assumed.

**Say when, not now.** The chooser carries a "Fixtures as of 25 Aug, 20:07 UTC" line whenever it is serving the snapshot, and drops it when the data came live. An app this careful about not overstating what a match shows cannot present a six-hour-old fixture list as current.

**The cron runs Thursday to Monday.** That is when the big five and the Champions League actually play. Midweek gets a couple of evening runs to catch cup rounds and rearranged fixtures, rather than nothing. Half-hourly during those windows, so a score is never more than thirty minutes behind.

The fetch path imports no pandas, no matplotlib, no Streamlit — only `curl_cffi` beyond the standard library — so the Action installs one package instead of the app's full requirements.

**Open risk, and it can only be answered by running it.** GitHub runners use Azure datacentre addresses, which is the same category of address the Streamlit deploy is being refused from. If WhoScored refuses those too, the Action fails every run and the snapshot goes stale — at which point the app falls back to live fetching and behaves exactly as it does today, which is why this is worth shipping before the answer is known. If it does turn out to be blocked, the next move is a proxy on the Action or running the fetch somewhere with a residential address.

### Proxy

Off by default, one env var away:

```
export TRAZADO_PROXY=socks5://127.0.0.1:9050
```

Direct is right for the common case. The Zauberpass **matchday** scraper this app follows goes direct via curl_cffi; the Tor proxy lives in `data_pipeline_app.py`, which is the bulk `soccerdata` path for pulling whole seasons — a different job with a different request volume. And section 1 promises every match is fetched fresh, so a round trip added to every request is a real cost.

But WhoScored rate limits bursts, and a shared or datacentre IP gets throttled far harder than a home connection. `lib/http.py` is the only place a session is built, so the proxy is set in one function and every caller inherits it. The 403 message names the env var when no proxy is set.

### Hosted deploys get throttled

WhoScored rate limits bursts, and it throttles **datacentre addresses far harder than home connections**. The same six-competition burst that returns 6/6 from a laptop can be refused almost entirely from a hosted Streamlit deploy, because the whole platform shares a small pool of egress IPs.

Four things follow, and all four are implemented:

- **The proxy reads Streamlit secrets as well as the environment.** Streamlit Cloud has no environment variables, so an env-var-only setting is unreachable exactly where it is most needed. Credentials in a proxy URL are never echoed back in status output or error messages.
- **Requests are throttled, not fired at once.** Two at a time with a stagger between starts, via `http.politely`. Six simultaneous requests look like a scraper; the same six spread over a couple of seconds look like a browser, and the wall-clock difference on a page nobody is watching load is negligible. Tunable with `TRAZADO_PARALLEL` and `TRAZADO_STAGGER`.
- **The schedule cache runs fifteen minutes, not three.** This is navigation metadata and it changes on the timescale of a matchday. A short TTL meant a hosted deploy spent its whole rate-limit budget re-fetching data that had not moved. Section 1 still governs match event data, which is never cached.

- **Retries back off.** Exponential with jitter, on 403/429/5xx and transport failures, dropping the session each time so a poisoned connection cannot persist. A fixed short retry just produces a second refusal a moment later.
- **A failed lookup must not read as an empty competition.** "Coming soon" is a claim about the football; "Unavailable" is a claim about us. Showing the first when the second is true is quietly wrong about every competition at once, which is exactly what a throttled deploy produces.
- **An unreachable competition stays clickable.** We cannot assert it is empty, and clicking is how you retry.

- **A circuit breaker, for a total outage only.** It must not fire on rate limiting. Tripping it at two consecutive failures turned "some competitions failed" into "half the competitions failed", because everything after the trip got one attempt and no retry — which is the exact symptom a hosted deploy showed while working perfectly on a laptop. Rate limiting is what retries are *for*. It now trips at five, which needs a run of failures that intermittent refusal will not produce, since any success resets the count. Note a failure is recorded once per request after its retries are exhausted, not once per attempt, so a trip above the number of competitions is unreachable.

- **Whatever fails gets a second, slower pass.** A shared address is refused intermittently rather than blocked, and the same request succeeds moments later. Retrying the stragglers one at a time costs nothing when the first pass worked, and is the difference between half the leagues loading and all of them. Measured with refusals injected at the transport layer: at 50% refusal, 6/6 load in about 12 seconds.

When something does fail the chooser says so once, with the reason, rather than leaving a wall of dashes to be interpreted.

**The failure path has to be rendered, not reasoned about.** `Summary.season` became optional when failures started carrying a reason, and one caller still reached through it — which crashed the whole chooser on exactly the deploy where failures are normal. It was caught in production, not in testing, because every local check ran against a healthy connection. Point `TRAZADO_PROXY` at a dead port to force the failing state and look at the page.

### Why our own scraper

The Zauberpass scraper builds the full qualifier map and then keeps a whitelist of about forty booleans. That discards `ThrowIn`, `GoalKick`, `IndirectFreekickTaken`, `Length`, `Angle`, every shot situation tag and the whole goalkeeper vocabulary. Throw-ins become undetectable, which removes a feature outright.

Ours keeps the raw qualifier dict on every row and flattens only what the visuals read. It also drops xT, progressive pass metrics and synthetic carry events. Synthetic carries would sit between a delivery and its first contact and corrupt the chain.

### What counts as a set piece

- Corners. All, including short.
- Free kicks in the attacking half, classified into direct shot, delivery into the box, or played short.
- Throw-ins only where the ball ends inside the penalty area.
- Goal kicks, **including free kicks taken by the goalkeeper in his own half**. The feed tags those as `FreekickTaken`, not `GoalKick`, so the attacking-half rule threw away about five a match — every one of them a keeper restart with the same launch decision and the same first-contact question as a goal kick. The goalkeeper is identified from the squad list, which every match carries, so this needs no inference. Together they run roughly 20 a match across both sides. Originally 14 a match from `GoalKick` alone, 43% launched past halfway, and a quarter of them contested in the air within three events — the same first-contact-then-second-ball question the rest of the app asks, started from the other box. Counted and laddered; excluded from the attacking-half delivery map, where they do not belong. Split into launched and played short by whether the ball crosses halfway, which needs no arbitrary threshold.
- Penalties are logged in the ledger but excluded from every delivery visual.

Free kick classification needs custom logic. The feed does not cleanly separate a whipped delivery from a short pass or a direct shot. Classify from end coordinates plus the next event.

### Available from the feed, high confidence

Set piece type, taker, start coordinates, delivery end coordinates, completion, first contact player and coordinates, aerial duel outcome, body part, shot location and outcome, goal, clock, scoreline at the moment of the set piece.

Also, and not assumed before we looked:

- **Delivery `Length` and `Angle`** on roughly 950 passes a match. Angle is in radians and runs about 1.7 from the y=0 corner, about 4.6 from y=100.
- **Shot situation, labelled by the feed**: `FromCorner`, `SetPiece`, `DirectFreekick`, `Penalty`, `ThrowinSetPiece`, `FastBreak`, `RegularPlay`. This is how a direct free kick attempt is identified — the tag sits on the shot, not on the restart.
- **Goal mouth placement**: `GoalMouthY` and `GoalMouthZ` plus a named cell such as `LowLeft` or `HighCentre`, on essentially every shot.
- **Shot location zone**: `SmallBoxCentre`, `BoxLeft`, `DeepBoxRight`, `OutOfBoxCentre` and so on.
- **Chain tags**: `LayOff`, `ShotAssist`, `Assisted`, `IntentionalAssist`, plus `relatedEventId` linking a shot to the event that created it.
- **Goalkeeper vocabulary** as event types (`Claim`, `Punch`, `KeeperPickup`, `KeeperSweeper`, `Save`) and as qualifiers (`HighClaim`, `Collected`, `ParriedSafe`, `DivingSave`).
- **Squad data**: height, weight, age, position, shirt number, starting XI.

Typical volumes per match across a 250-match sample: 9.8 corners, 25.6 free kicks taken including goal kicks and own-half restarts, 38.4 throw-ins of which only a handful finish in the box.

### Derivable with our own logic, moderate confidence

- Throw-in kind. Only throws finishing in the box are kept, and those split cleanly: across 40 matches their lengths ran 18 to 42 with a median of 27, taken from a median x of 85. A throw of 25 units or more, or one launched from outside the final eighth, is the long-throw weapon; the rest are short throws worked in from close range. A subtype of "delivery" on every restart says nothing, which is the point of typing them.

- Swing direction, from the `Angle` qualifier plus which corner it was taken from. **Not** from the taker's stronger foot: WhoScored tags foot reliably on shots but rarely on passes, and with Transfermarkt gone there is no footedness lookup. Angle is the channel.
- Second phase, by chaining events for a few seconds after first contact while possession is retained. Separates a shot off the delivery from a shot off the knockdown or recycled ball. This is the core differentiator.

  Measured, not hoped for. Over 120 matches, walking forward fifteen seconds from each corner and comparing against the feed's own `FromCorner` tag — which the chain never reads — gives **96.7% recall and 98.9% precision**. Of 468 chained corner shots, **229 were first phase and 239 were second phase**. Slightly over half the shooting off corners comes after the first contact, which is the layer nobody renders.

  One trap found while measuring this. `eventId` is sequential *per team*, not per match, so sorting on it puts a keeper's `Save` ahead of the shot it saved and mis-reads the save as the first contact. That alone inflated the second-phase count by 8%. The feed's own array order is chronological; sort on that. The scraper keeps it as `feed_order`.
- Delivery zone from end coordinates: near post, central, far post, short.
- First contact win rate by zone.
- Goalkeeper involvement through claims, punches, and first contact.

### Not available, do not attempt

Event data records the ball, not the bodies. There is no zonal versus man marking, no blockers or screens, no attacker starting positions, no count of bodies in the box, no delivery height or hang time, no marking assignments. That layer needs freeze frames, tracking data, or manual tagging.

This defines the ceiling. Trazado is delivery and outcome analysis with real second phase work. It is not routine analysis.

### Known traps

- **One penalty leaves four events carrying the `Penalty` qualifier**: the foul won, the foul conceded, the keeper's `PenaltyFaced`, and the kick itself. Counting them all put the rate at 1.3 a match against a real-world 0.25–0.30. Only the event that is also a shot is the penalty.

- **`isTouch` is False on `Aerial`, `BallRecovery` and `Challenge`.** Every aerial duel in the feed carries `isTouch = False`. A first-contact rule built on `isTouch` alone therefore walks straight past the duel that decided the set piece and attributes contact to whatever happened next. This shipped and went unnoticed because the verification script carried its own copy of the walk-forward logic and had the same blind spot — a checker that reimplements the code under test passes while the code is broken. Test the shipped function.

  Correcting it moved the phase split from 229 first / 239 second to **140 first / 313 second**: roughly two thirds of set piece shots come after the first contact, not half. The differentiator is bigger than the first measurement suggested.

- ~~Fouled player attribution is inconsistent in some feeds.~~ **Checked.** A `Foul` event with `outcome == Successful` is the player who *won* the foul. Verified by testing whether that player's team took the resulting free kick: 16 of 16, no mismatches. Keep the check as a runtime assertion rather than trusting it blindly.

- **Coordinate frames are per team, and this is the easiest thing to get silently wrong.** WhoScored records every event in the acting team's attacking frame, so a clearance that ends a corner is logged near x=8, not x=92. Aerials and `CornerAwarded` appear as mirrored pairs at (x, y) and (100−x, 100−y). Any chart showing a delivery next to the defensive action that killed it must put both in one frame first — `lib/pitch.to_attacking_frame` does this. Getting it wrong does not raise; it mirrors half the markers onto the wrong side. The regression test is that first contact should sit within a few metres of where the delivery landed: median is 1.9m, 87% under 5m.

- Height is missing for about 0.9% of players, and WhoScored writes `0` rather than omitting it. The scraper reads 0 as missing so nobody profiles a 0cm target.
- Long throws are excluded from most standard set piece definitions. We include them, conditionally, per the rule above.
- Single match samples are small. Roughly eight to twelve corners across both sides. Every label must respect that.

---

## 3. Visuals

Thirteen items. Types are first class throughout, with a filter for all, corners, free kicks, throw-ins.

Origin markers make type readable at a glance: corner arc for corners, small square at the spot for free kicks, touchline tick for throw-ins.

1. Match summary strip. Counts by type per team, shots created, goals, first contact fraction. No rates.
2. Delivery map. All types on one pitch, filterable. The hero visual and the default share image.
3. Free kick panel. Award locations in the attacking half, and for direct attempts the shot location, distance, outcome. Conditional.
4. First contact map. Filled marker for won, hollow for lost.
5. Aerial duels by box zone. Counts by zone, with the box tiled in **absolute** pitch terms:

    | zone | where |
    |---|---|
    | six-yard box | x 94.2+, central |
    | central | the central corridor, y 37–63 |
    | left half space | y 63–79 |
    | right half space | y 21–37 |
    | edge of box | in front of the area |

    **Zones are the real sides of the pitch, not mirrored onto the delivery side.** The left half space is the left half space whichever corner the ball came from. Opta y=100 is the attacking team's left — verified by rendering the landmarks, not reasoned about, because getting it backwards silently mirrors every zone label in the app.

    Two earlier versions of this were wrong. The first labelled the wide bands "near post" and "far post", putting a post label on a strip of grass eleven metres wide starting at the edge of the six-yard box; those bands are half spaces. The second named them near/far and mirrored them onto the delivery side, which made left and right meaningless.

    `lib.pitch.delivery_zone` and `ui.charts.ZONE_BOXES` share the same names by construction, so the ledger and the map cannot disagree.

6. Second phase chain. Delivery, first contact, next action, shot. In the dashed notation, not a generic Sankey.
7. Set piece shot map. Split first and second phase. Marked on target, off target, blocked, goal.
8. Set piece goal card. One panel per goal showing delivery, contact and finish, with taker and scorer named. Conditional.
9. Game state timeline. Every dead ball against the scoreline, with type markers. The scoreline is the **real** one, stepped on every goal in the match — stepping it on set piece goals alone draws a flat line through a 4-2 and misrepresents the game state every restart was taken in, which is the whole point of the chart. Goals carry the new score and the scorer; the ones that came from a set piece are ringed in the accent. Carries a half-time divider, a shot ring on the restarts that produced one, and each side's running count.
10. Fouls won in the final third. Locations and names, wide versus central distinguished.
11. Defensive panel. Clearances, keeper claims and punches, first contact fractions by zone.
12. Team comparison. Raw counts across the metrics above.
13a. Goal kick map. Full pitch, always left to right. Goal kicks cannot share the delivery map — that map is the attacking half and these start on the other goal line. Landing point filled when the kicking side got there, hollow when they did not, ringed when contested in the air. Counted and drawn because a quarter of them are contested within three events, which is the same first-contact question the rest of the app asks.
13. Set piece ledger. Table of every dead ball: minute, team, type, taker, target zone, first contact, outcome. Backbone for the copyable text report.

---

## 4. Notation system

The logo's vocabulary is the chart vocabulary. Keep them identical.

- **Comet stroke**: every delivery. Thin and faint where the ball was struck, thick and solid where it finished — direction reads without an arrowhead, origin reads without a glyph.
- **Colour**: which kind of set piece it was. One hue per type, assigned in fixed order and never cycled.
- **Weight and opacity**: a delivery that led to a shot is heavier and fully opaque; one that led to a goal heavier still. The quiet ones are drawn first so the ones that mattered are never buried.

**No shape markers.** An earlier version encoded type as circles, squares, ticks and triangles and outcome as filled versus hollow. That asked the reader to hold four glyph meanings in their head before they could read anything, and the legend needed two rows to explain it. Colour carries type in one channel and the legend is three swatches.

### Series colours

One hue per set piece type, per theme. Every set passes all five checks on its own chart surface — OKLCH lightness band, chroma floor, colour-blind separation, normal-vision separation, and 3:1 contrast:

```
vivid / moon   s1 #FE4431   s2 #06A89D   s3 #A86BFD
newspaper      s1 #A8481C   s2 #0E9AA0   s3 #67459F
```

Found by searching OKLCH space, not picked by eye: every hand-picked set failed colour-blind separation, usually teal against pink under deuteranopia. Re-run the check before changing any of them.

This closes the section 9 question about extending Moon and Newspaper beyond one accent — they now carry three. A delivery that produced a **goal** is ringed at its landing point — without it the single most important delivery on the pitch is drawn identically to one that produced a blocked shot.

**Every marker on a chart must appear in that chart's legend.** Legends are built from the data, not from a fixed list: a hardcoded one left goal-kick triangles scattered across the timeline with nothing anywhere saying what they were. An unlabelled symbol is worse than no symbol.

**Every per-team visual names its team in its own title.** Which side a map belongs to is obvious while writing it inside a per-team loop and not at all obvious when looking at one map on a long page.

A completed delivery is drawn as a **comet**: the stroke tapers and brightens from the striking point to where the ball finished, so direction of travel reads without an arrowhead. A cleared or incomplete one stays dashed. A dashed comet reads as neither, so the two encodings do not combine.

The ledger uses the same vocabulary as the pitch — a solid rule where the delivery found a teammate, dashed where it was cleared, the accent only where it led to a shot, filled or hollow dot for the duel. It is notation in a table, not a spreadsheet dump.

**Orientation, verified.** WhoScored records every event in the acting team's attacking frame; the mirror to a common frame is a 180° rotation, `x -> 100-x, y -> 100-y`. Checked four ways: mirrored aerial pairs land exactly on each other; first contact sits a median 1.9m from where the delivery finished across 120 matches; a landmark render puts the attacked goal at the top with the penalty spot centred below it; and near/far post labels contradict actual post distances in 0 of 13 corners. Note the rendered x-axis is inverted, so opta `y=0` appears on the **right**.

---

## 5. Brand

### Name

Trazado. Spanish for the plotted line or layout. Chosen over Trazo and Arco for ownability.

### Logo

Playbook notation mark. A solid square at the starting position, a dashed run curve with an arrowhead, and an accent stroke for the blocking action. Below roughly 24px the dashes and arrowhead drop out and the mark simplifies to square plus solid curve plus accent tick.

SVG source is in `assets/logo.svg`.

Open items: the square reads as a ball but a ball is round, so test an open circle variant. Dashed strokes suffer under JPEG compression, so test the mark at 400px inside a compressed image before committing.

### Themes

Three. Vivid is the app default. The export card follows whatever the app is set to.

**Every colour is contrast-checked against both `bg` and `surface`**: 4.5:1 for body text, 3:1 for secondary text and chart lines. Newspaper failed this badly before it was measured — `faint` sat at 2.3:1 and the accent at 2.4:1 as text. Its cream is now cooled and its ink taken near black, which is also what the brand note below asked for.

Streamlit's own widgets — radio, buttons, code blocks — render from `.streamlit/config.toml`, which is a fixed dark theme. They must be styled from the token block too, or they come out white-on-cream the moment anyone switches to Newspaper.

**Vivid** (default)
```
bg #12121A   surface #1D1D2A   surface-dim #16161F
line #33334A line-dim #26263A
ink #FFFFFF  muted #9C9CB8     faint #5A5A72
accent #00E0C6   accent-on #0A3D36   hot #FF3B6B   warn #FFD23F
```

**Moon**
```
bg #0E1116   surface #171C24   surface-dim #12161C
line #2A323D line-dim #1E242D
ink #E4E8EE  muted #8A94A3     faint #5A6270
accent #7FA8D9   accent-on #0B1A2B
```

**Newspaper**
```
bg #FBF6EA   surface #F3EAD6   surface-dim #EFE5CE
line #DCCEB0 line-dim #E5DAC0
ink #3A3125  muted #8A7B62     faint #A7997D
accent #C98A3C   accent-on #2A1D08   hot #B0522A   warn #A8842F
```

Known gap: Vivid carries three accents, Moon and Newspaper carry one. Any chart needing three encodings will run out of channels outside Vivid. Either extend the other two, or design every chart to need one accent only.

Newspaper note: the cream reads as aged paper rather than newsprint. If it should match its name, cool the cream and darken the ink toward true black.

### Typography

- **IBM Plex Sans** for interface, body and headings, weights 400, 500, 600, 700. Subtly squared, engineered, credible — it carries a dense fixture list without the technical edge of a display face.
- JetBrains Mono for scores, counts, labels and all numeric readouts

Both from Google Fonts. Mono on numbers is deliberate. It makes figures read as readouts and keeps columns aligned in the ledger.

Both families are declared once as `--font-ui` and `--font-mono`. Swapping either is a one-line change; no rule names a family directly.

Chosen from a specimen screen that rendered the real furniture — masthead, league card, fixture row — in eight candidates at once. Also tried: Chakra Petch, Saira, Oxanium, Rajdhani, Anybody, Sora, Barlow, and earlier Space Grotesk and Archivo. Picking a face from a rendered specimen rather than a description is worth the twenty minutes; the first two picks were both made blind and both wrong.

---

## 6. Screens

### Header, on every page

Trazado mark plus wordmark on the left, theme switcher on the right, hairline rule beneath. Identical across all screens.

### Competition chooser

Heading is the live season in short form — "2026-27", not "2026/2027" — taken from what actually resolved rather than a constant, so it is right the day the season rolls over. Subtitle is "Set piece analysis". Footer is the byline, "by @mhassanfootball", linking out.

Six cards in a three column grid. League logo on a light chip, league name, match count. No country names, no matchweek.

**A competition with nothing to open is not a link.** Dashed border, dimmed chip, faint name — the same treatment as an unplayed fixture, so "nothing here" reads the same way in both places. That covers a season that has not started ("Coming soon") and one whose window is empty ("No recent matches"). A competition we simply failed to reach stays clickable and shows a dash: we cannot claim it is empty, and clicking is how you retry.

No accent colour on any card. The Champions League is not singled out — before its season starts it is just another disabled card, which is what it is.

Below, a divider and a direct lookup field taking a match URL or ID.

Logos sit on a white chip because the asset set has mixed ink and several logos are dark artwork that would sink into the dark themes. **Measured, and the chip stays.** Mean ink luminance across the six: Ligue 1 is 0 and the Champions League star ball is 9, both effectively pure black and invisible on Vivid and Moon. Bundesliga 92, Serie A 92, Premier League 101, La Liga 128. White variants exist only for Ligue 1 and the Champions League, so per-theme swapping would still leave four logos unsolved.

All six are sourced and live in `assets/leagues` at 96px, trimmed to their ink and padded square so they read at a consistent size on a 28px chip. Total 52KB, which keeps the base64 payload cheap.

Logos are trademarks regardless of the file licence. Fine for a personal tool. Check before putting them on public share graphics.

### Match chooser

Breadcrumb back to competitions, league name, then date chips.

Fixture cards showing home badge, score in mono, away badge. Unplayed fixtures greyed and non interactive, labelled not played. No dates on the cards themselves — the date lives once in the group header above them.

**Matchweek chips are not buildable; use date chips.** The fixture feed carries no round, matchweek or gameweek field. Checked against every field on a live fixture: the only thing resembling one is `stageId`, which is constant across a season. Group by kickoff date instead. For a matchday app that is the better grouping anyway, and it is honest about what the feed knows.

**The set piece count cannot go on a fixture card.** Counting dead balls requires the full event feed for that match, so showing it on ten cards means ten full scrapes to render one chooser screen — twenty seconds or more before anything appears, to produce a number nobody asked for yet. Drop it from the card. The count belongs on the analysis screen, where the match has actually been fetched.

Open item: badges alone are hard on less familiar leagues. Consider a short text label or hover title.

**Club crests come from WhoScored, keyed on team id.** `https://d2zywfiolv4f83.cloudfront.net/img/teams/{teamId}.png`. Every fixture already carries `homeTeamId` and `awayTeamId`, so there is no name matching anywhere in the path. Coverage is 96 of 96 across all six competitions — no gaps, and it stays correct through promotion and relegation because nothing is hand mapped.

football-logos.cc was tested as the alternative and rejected for this screen. It is a genuinely good library — 4,232 logos at 1500px, `robots.txt` allows crawling, and it publishes an image sitemap with canonical hashed URLs. The problem is joining it to WhoScored's team names, which has to be done by slug. Measured against the 96 current teams: 81% match exactly, and the fuzzy remainder is actively wrong — Leeds resolves to `lewes`, Deportivo Alaves to a Peruvian club, Como to `cosmos`, Monaco to `moncao`. Eight well known clubs including AC Milan, Celta Vigo and Strasbourg fail outright. A silently wrong crest is worse than no crest, so this route does not guess.

The trade is resolution: WhoScored's crests are 70px or 80px. Ample for a fixture card, not for a large export crest. If the export cards need big crests, that wants a hand verified mapping to football-logos.cc, not an automated one — and note their terms say free access does not transfer trademark rights and that bulk collection may carry separate terms.

A monogram fallback is implemented for any id without a badge. It is currently unused, which is the point: it exists so a missing crest holds its space rather than making a card look broken.

### Loading

Named stages rather than a spinner: match events retrieved, dead ball sequences isolated, tracing deliveries and first contacts, building second phase chains, rendering. Progress bar in accent. Completed stages get a check, active stage pulses, pending stages are dimmed.

Carries a line stating that Trazado holds nothing between visits so every match is pulled fresh, typically ten to twenty seconds. This turns the constraint into a stated principle.

### Analysis

Scroll layout. Delivery map as hero at the top, then first contact, then second phase, then the rest below the fold. Type filter available throughout.

### Export panel

Row of type buttons, one per visual. Live preview of the branded card. Actions: download PNG, copy report, open a prefilled post.

---

## 7. Export spec

- 4:5 portrait, around 1080 by 1350. Takes more feed space than 16:9 and suits a tall pitch graphic.
- Rendered separately from the on screen figure. Different padding, different type sizes, and the branding block exists only on the export.
- Header: mark and wordmark left, match identity and competition right.
- Title, then a caption line stating the single most interesting fact from that match.
- **Header text is Title Case.** Not shouting caps, not lowercase.
- **Every element gets reserved space.** Charts are laid out in bands measured from the data, never as a fraction of the axis with labels dropped wherever they land — that put team names straight through the tick bars and clipped a 90th-minute goal off the right edge. Text near an axis edge anchors away from it.
- The visual.
- Legend using the notation vocabulary.
- Footer: "Data from Opta" left, "@mhassanfootball" right. The handle is **@mhassanfootball** — it goes on every graphic that leaves this app, so it is written down here rather than retyped from memory.
- The card takes the app's theme. Choosing it separately was a second control to set before you could download something you were already looking at.
- **Crests, not team names.** Names are long, inconsistently abbreviated by the feed, and push the header out of alignment; the crest says the same thing in a fixed box. Held at 75% opacity so it sits behind the type rather than competing with it. Falls back to names when an id has no badge.

The post button can only open a prefilled compose window. It cannot attach the image. Flow is download, compose, attach. Label it honestly.

**The card is a frame, not a chart.** Any visual can be dropped into it, because a chart that can only be seen inside the app is a chart nobody sends to anyone. Every visual in `ui/charts` is a `draw_*` function that renders into a rectangle it is handed and returns its legend handles — it never makes its own figure or writes its own title. That is what lets one visual appear on screen and inside the card at different sizes from the same code, which is what section 7 means by "rendered separately", not a second implementation.

**Built.** `ui/export.py` renders the card at 1080x1350 and returns PNG bytes; the analysis screen shows one per team with a download button and its own theme picker. The caption comes from `lib/readout.headline`, which is bound by the same rules as everything else — a fact this match shows, in fractions, never a tendency and never a percentage on a denominator under ten.

Two things the card taught us:

- **The stat row must be ordered by payload, not by category.** A first pass listed the type counts first and truncated to fit, which silently dropped `SHOTS` and `SECOND PHASE` — the two numbers the app exists to produce. `readout.strip` now front-loads them so a card that runs out of room loses a corner count instead.
- **The legend has to explain the origin markers.** Without a second legend row the reader cannot tell a corner from a free kick on the pitch, which makes the type filter meaningless on an exported image.

The mark is drawn from `assets/logo.svg` coordinates directly. Its y axis runs downward as SVG does; flipping it turns the run curve upside down.

---

## 8. Streamlit implementation notes

- Custom HTML in `st.markdown` cannot reference arbitrary local files, but Streamlit does serve `./static` at `/app/static` when `server.enableStaticServing` is on. Use that for anything that repeats.

  This matters more than it sounds. Club crests appear on every fixture row, and inlining them as data URIs produced a single 488KB markdown payload that Streamlit silently rendered as nothing — no error, just an empty page. Served as files the same screen is 7.8KB, a 63x reduction, and the browser caches each crest. Base64 is still right for one-off images like the six league logos (96px source, 28px render, 52KB total) and for the export renderer, which has no server to fetch from.
- `st.image` will not work inside custom HTML blocks. It is for standalone images only.
- Card click targets are best handled as anchor links carrying query params, read back with `st.query_params`. Streamlit buttons resist the card styling this design needs.
- **Webfonts need a `<link>`, in a markdown call of their own.** Two traps stack here and both fail silently.

  First: `@import` is only honoured as the *first* rule in a stylesheet. The theme token block is emitted ahead of the static CSS, so an `@import` inside the static block never loaded at all — the app rendered in Streamlit's own Source Sans for its entire life while appearing to specify a face. Nothing errors; the page just looks slightly wrong in a way that reads as a bad font choice rather than a bug.

  Second: a `<link>` and a `<style>` sent in one `st.markdown` call lose the `<style>` — Streamlit keeps the links and drops the block. They must be two calls.

  Verify with `getComputedStyle(el).fontFamily` in the browser rather than by eye. A missing webfont looks like a design opinion, not a defect.

- Streamlit sets `font-family` on its own inner containers, so inheriting from `body` is not enough. Trazado elements name the face explicitly.

- Theme is a query param or session state value that swaps a `:root` custom property block. Keep the rest of the CSS static and referencing `var(--token)` so only the token block is dynamic.
- Greyed non interactive fixture cards should be plain markup with no anchor, not disabled buttons.
- The staged loading view will not come out of `st.status`. Render the whole panel as one HTML block and update it in place.
- Export images should be generated server side as figures, not screenshotted from the DOM.

---

## 9. Open decisions

- Brand fonts are not installed locally. Space Grotesk and JetBrains Mono load from Google Fonts in the browser, but `matplotlib` cannot reach a CDN, so every server-rendered export card silently falls back to DejaVu Sans. Both families are open licence. The `.ttf` files have to be on disk before the export panel is built, or the one surface that carries the brand is the one that will not be on brand.
- Shot outcome in visual 7 needs four encodings and Moon and Newspaper have one accent. Recommended resolution is to encode outcome in marker shape and fill, which the notation system already uses for duels, and leave the accent meaning only "led to a shot" as section 4 requires. Until that is settled, Moon maps `hot` onto its single accent, which makes the featured Champions League card read the same as an accent hover.

- Penalties in or out of the ledger.
- Club crests: 20 of roughly 106 are available and only for big clubs, so the match chooser needs a monogram fallback or a full sourcing pass.
- Whether swing direction is worth showing at all now that it rests on `Angle` alone rather than angle plus footedness.
- Whether the app says something when a match has almost no set piece content.
- Circle versus square in the logo mark.
- Whether to extend Moon and Newspaper to three accents.
- ~~Whether to source white logo variants for all six competitions and drop the chip.~~ **Closed.** Only two of six have white variants; the chip stays.
- Club crest source and licensing.
- Text labels or hover titles alongside club badges.

---

## 10. First tasks in Claude Code

1. ~~Point at one real match export and confirm the actual field names and qualifier structure.~~ **Done.** Schema confirmed against cached blobs across six competitions; scraper written and swept over 250 matches with no parse failures. Verified live end to end since: a fixture played the same day fetches fresh in under two seconds with corners, throw-ins, goal kicks, shot situations and squad heights all present.
2. Write the set piece classifier: corner, free kick by subtype, qualifying throw-in, penalty. Reject goal kicks and keeper throws explicitly rather than folding them into free kicks — the feed distinguishes them and roughly half of all `FreekickTaken` events are restarts we do not want.
3. Build the ledger for that match and print it. The ledger proves nothing is being silently dropped.
4. Chain first contact and second phase, and verify against a match with a known set piece goal.
5. Only then start on visuals, beginning with the delivery map.
