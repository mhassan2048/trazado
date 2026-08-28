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
- **xG and xT are allowed, as named models, under the rules below.** This reverses the original ban. That rule was written for an app whose entire subject was deliveries and first contacts, where danger reads from location and outcome alone. It stopped holding the moment the question became "how much of this team's threat came from dead balls", which is a question about quantity and cannot be answered with position.

  What is served is **a specific model, never "xG" in the abstract**: fitted on 291 La Liga matches, 7,215 non-penalty shots, 681 goals. Out-of-fold log loss 0.2718 against a 0.3126 base rate, AUC 0.755, aggregate calibration 680.6 predicted against 681 scored. Agreed with FotMob to within 0.10 on both sides of the one match checked against it.

  **It is trained on one league.** A Bundesliga or Champions League card is out of distribution until that is checked. `lib.xg.validated_for` names which competitions have been, and the honest options are to validate or to withhold — not to let the number appear anyway.

  **Always npxG.** Penalties are excluded from both sides of every fraction. A penalty scores 0.804 from this model and a team's whole set-piece output in a match runs 0.3 to 0.9, so one spot kick would become the majority of "set-piece xG" and the headline would read "set pieces were 60% of their threat" when the honest translation is "they won a penalty" — a sentence about nothing the app is about. Penalties are counted and reported separately.
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

- **An open-play xT grid cannot price a dead ball, and using it anyway looks fine.** Measured: eight corners in one match produced 0.91 of raw xT gain against 2.00 for that team's entire match across 439 positive passes — a corner valued at roughly 27 times an average pass. This is structural, not a tuning problem. The grid says the corner flag is a low-value cell *because in open play the ball being there is not threatening*; a free delivery from a stopped clock breaks that premise. It would also hand +0.22 to a corner headed straight out.

  So `lib/xt.py` excludes dead-ball restarts from **both** sides: `totals` counts open-play passes only, and set-piece value is measured from the chain after the ball is live. That number is small by nature — second-phase possessions are short — and it is honest, which the inflated version is not.

  The consequence to state plainly: **xT is the weaker of the two measures.** Set-piece threat should be read from npxG, where the model prices a set-piece shot on its own terms (`from_corner` carries a −0.41 coefficient). xT describes the open-play continuation and nothing more.

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
12. Team comparison. Raw counts across the metrics above, as opposed bars running outward from a central label column. **Built.**

    Each row is scaled to its own larger side, and the raw number is printed at the end of every bar. Rows measuring corners and rows measuring goals share no unit, so a single scale across the table would make a 1-goal row an invisible nub next to a 14-goal-kick row; per-row scaling with the number always printed keeps length honest within a row and never asks length to carry the value alone. That is also what stops a 3-against-2 row reading as a rout.

    Fraction rows — first contact, aerials, shots in the second phase — use the outline-is-attempted, fill-is-won encoding from the aerial breakdown, so the reader learns one vocabulary rather than one per chart.

    **Crests head the two columns, not names.** Same reasoning as the export header: the feed abbreviates club names inconsistently and a long one pushes the layout around, while a crest says the same thing in a fixed box. They sit at section 7's 75%. The names come back in the legend only when a badge is missing, and it is both crests or neither — one crest against one bare column reads as a rendering fault rather than a missing badge. The crest band is counted as part of the chart's height, or the rows compress to make room and leave the slack under the table.

    **The label column is measured, not assumed.** A fixed gutter printed "Shots, 2nd Phase" straight through both bars. The chart now draws every label and every value invisibly, measures them against the rendered axis, and gives the bars whatever is left — which is what section 7 means by bands measured from the data.

    The caption leads with the row a reader would actually lead with, not the biggest gap: "Set-Pieces" is a sum dominated by goal kicks, so on one real match a 25-to-20 row beat a 4-to-1 shot count on raw difference while saying far less. Goals, then shots, then corners. When no row is decisive it states the split rather than claiming one, and it never says "evenly split" — a 1-0 match had been described that way.
13a. Goal kick map. Full pitch, always left to right. Goal kicks cannot share the delivery map — that map is the attacking half and these start on the other goal line. Landing point filled when the kicking side got there, hollow when they did not, ringed when contested in the air. Counted and drawn because a quarter of them are contested within three events, which is the same first-contact question the rest of the app asks.
14. Set-piece share of threat. **Built.** Two half pitches, every shot in the match sized by npxG — area, not radius, since radius exaggerates by the square. Set-piece shots carry the accent and are drawn last; open play sits back as faint outlines, which is section 4's "quiet ones first" rule applied to shots rather than deliveries. Goals are ringed.

    **The form is chosen by the sample size.** The claim rests on a handful of shots — eight on the match this was built against — so the chart shows every one of them rather than rendering a share as a smooth quantity. A donut or a stacked bar would look cleaner and would hide how few events built the number. A reader can count these. That is section 1's fraction rule applied to form, not just to labels.

    For the same reason the headline reads `0.87 of 2.38`, never `36%`.

    Beneath sits a stepped cumulative npxG band with set-piece contributions marked, because a share cannot show *when*. On the match this was built against, three shots came off one 52nd-minute sequence — a cliff in the band, and a decimal in the share.

    Both teams on one card, never one card per team: a side with no set-piece shots would otherwise render an empty pitch, which section 1 forbids. Their empty half is the story instead.

    The two lines are labelled at their ends rather than in the legend. A legend entry makes the reader carry a colour across the card; a label sits where the eye already is, and keeps the legend to the encodings that genuinely need explaining.

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
vivid       s1 #FF1493   s2 #32CD32   s3 #1299DE   accent #00E5FF   deeppink / limegreen / azure, cyan
moon        s1 #87CEEB   s2 #C9CDD3   s3 #D9A05B   accent #FFFFFF   skyblue / light grey / sand, white
newspaper   s1 #4169E1   s2 #878787   s3 #9F8164   accent #4169E1   royalblue / grey / coffee
```

Found by searching OKLCH space, not picked by eye: every hand-picked set failed colour-blind separation, usually teal against pink under deuteranopia. Re-run the check before changing any of them.

**Rebuilt once for restraint, and the reason is worth keeping.** The first set passed every contrast and colour-blind check and still looked cheap. The measurement that explains why: its series ran at chroma **0.225 / 0.114 / 0.210** — two at near-maximum saturation and one moderate, so the red and violet shouted while the teal receded. That imbalance was not a choice. Teal at that lightness **cannot exceed C 0.11 in sRGB**, so the other two were simply left wherever they landed.

Evening the chroma costs colour-blind separation, because ΔE comes largely from chroma — and section 4 makes colour the *only* channel carrying set piece type, with no shape markers to fall back on, so separation cannot be traded away. The fix was to search for hues that reach **even** chroma while staying separable, rather than to desaturate the ones already chosen.

The result is one hue family across all three themes — **ochre 70, jade 170, lavender 305** — differing only in lightness, with chroma even within a theme. Validated: deutan 10.8 / tritan 14.4 on dark, 9.4 / 12.6 on light, normal-vision floor and 3:1 contrast passing throughout.

**Each theme names its own set.** An earlier version used identical hexes for Vivid and Moon, which made the two themes indistinguishable in the one channel that carries meaning. They now differ by design intent: Vivid runs boldest, Moon lighter and cooler for its ground, Newspaper pitched deeper to hold a light surface.

**Some triples are impossible, and it is worth knowing which.** Anything pairing a red with a green scores deutan 0.0–2.1 and is unusable — Coral/Sage/Slate, Gold/Emerald/Plum and Clay/Forest/Mauve were all searched and discarded. With no shape markers to fall back on there is no secondary encoding to rescue them.

**These are hand-picked, not searched.** The sets above were chosen directly and do not clear the validator's colour-blind separation — deeppink against limegreen is a red-green pair, and Moon's skyblue against light grey separates mainly by chroma. That is a deliberate override of the rule below, recorded rather than hidden. If a colour-blind reader ever has to use this, the palettes need re-deriving.

Newspaper's grey is darkened on the way in. CSS `lightgrey` measures **1.28:1** against the cream surface, nowhere near the 3:1 a chart mark needs, and would repeat the invisible-tone-ramp failure. It sits at the lightest value that clears 3:1, so it reads as mid grey rather than light. Any "light" colour named for this theme gets the same treatment — cream is a light ground and there is no room above it.

**Run the validator with `--pairs all`.** Its default compares only *adjacent* pairs, which will happily pass a palette whose first and third colours are nearly identical — and did. Under all-pairs checking most of what looked fine collapses: copper/teal/periwinkle scores 7.9, below the floor, and of nine hand-picked hue families only rose/olive/azure survived, at 11.7 against 7.9 for the next best. Every earlier number in this section was measured the weaker way.

**Thin tapered strokes need chroma; this is the constraint that outranks taste.** A near-monochrome Newspaper — black, coffee, grey — separated beautifully by tone, passed everything that mattered, and was unreadable in practice. A comet fades from solid to nothing, and a low-chroma stroke has no fade left to give. Chroma is floored at 0.12 for that reason alone.

**How green the middle slot can get, measured.** Sweeping it from olive toward lime collapses tritan separation against the azure: 10.6 at h122, 8.7 at h128, 4.5 at h145, and CSS limegreen fails outright. Nor does rearranging help — holding a true lime in the middle and searching every position for the other two returned nothing above the floor. Vivid reaches **h128**, the greenest that clears; Moon and Newspaper are already at their own limit of h122 and cannot follow, so the middle hue differs slightly by theme.

**Olive rather than green is not a preference.** Rose against green is the classic deuteranopia confusion. h122 is as far toward green as the middle slot can travel and still be seen by a red-green colour-blind reader; anything greener fails.

**Themes differ by weight, not by hue, because only one structure survives.** Vivid boldest, Moon lighter and softer, Newspaper deeper for its cream ground. Sharing the structure is forced by the search, not laziness — and it is worth re-testing whenever a fourth series colour is proposed, because three is already near the limit of what stays separable.

**Superseded: Newspaper as a tone ramp.** Black sits at L 0.17 and every series colour reads as grey, so the lightness band and the chroma floor both FAIL. Those two exist to guarantee separation by *hue*; this palette separates by *tone*, which is how newsprint has always worked and which colour blindness cannot touch.

The checks that measure the actual goal pass, and by a wider margin than any hue set found for this theme: CVD separation **15.5 protan / 18.9 tritan against 9.3 / 8.0**, normal-vision floor **18.4 against 9.3**, contrast passing throughout. It is more readable to colour-blind readers, not less. Do not "fix" the two failures — they are the design.

**The accent is checked against the series, not only against the ground.** It means "led to a shot" and nothing else, so it must not read as a fourth type. The blue accents that preceded the current ones sat ΔE 6.5 from Newspaper's azure and 8.5 from Moon's periwinkle — close enough to pass for a type colour, and only visible when measured. Gold on the dark themes and violet on Newspaper clear every series by ΔE 15.8 or better. `hot` and `warn` are exempt because neither ever appears on a chart beside the series; they live on the chooser and the logo mark.

The lesson for next time: **a palette can pass every check and still be wrong.** The checks catch inaccessibility, not garishness. Uneven chroma is what garishness usually is, and it is measurable.

This closes the section 9 question about extending Moon and Newspaper beyond one accent — they now carry three. A delivery that produced a **goal** is ringed at its landing point — without it the single most important delivery on the pitch is drawn identically to one that produced a blocked shot.

**Every marker on a chart must appear in that chart's legend.** Legends are built from the data, not from a fixed list: a hardcoded one left goal-kick triangles scattered across the timeline with nothing anywhere saying what they were. An unlabelled symbol is worse than no symbol.

**Every per-team visual names its team in its own title.** Which side a map belongs to is obvious while writing it inside a per-team loop and not at all obvious when looking at one map on a long page.

A completed delivery is drawn as a **comet**: the stroke tapers and brightens from the striking point to where the ball finished, so direction of travel reads without an arrowhead. A cleared or incomplete one stays dashed. A dashed comet reads as neither, so the two encodings do not combine.

The ledger uses the same vocabulary as the pitch — a solid rule where the delivery found a teammate, dashed where it was cleared, the accent only where it led to a shot, filled or hollow dot for the duel. It is notation in a table, not a spreadsheet dump.

**And therefore it carries a key.** Notation the reader has to infer is not notation. The key is built from the match like every other legend here — a match with no penalty offers no PK badge, one where every delivery was met offers no "no contact" dot — and each swatch reuses the row classes rather than restating the styling, so the key and the table cannot drift apart.

It sits **above** the table, unlike chart legends, which sit below. A key underneath forty-five rows is a key you reach long after you needed it.

**Style and colour are independent channels in the ledger, and the first version of the key hid that.** The rule says whether the ball was found; the accent says whether a shot followed. A cleared delivery that still produced a shot is drawn dashed *and* in accent — which happens in real matches — so listing the accent as a third entry under "Delivery" implied it was a third line style. The accent is named for the channel it actually is.

Note the badge for a throw-in reads "Throw-In", not "Long Throw". Only throws finishing in the box are kept and they split into the long-throw weapon and short throws worked in; the subtype column carries that distinction, so the badge must not pre-empt it.

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

Note `ink` is an off-white in every dark theme rather than `#FFFFFF`. Pure white on a near-black ground is harsh at body size and is one of the things that made the first set read as cheap; it costs nothing in contrast (15.9:1 against bg) to soften it.

**Vivid** (default)
```
bg #101017   surface #1A1A23   surface-dim #14141B
line #2E2E3C line-dim #222230
ink #ECEAF2  muted #9A96A8     faint #696577
accent #6FB8D9   accent-on #0B2733   hot #DD6F80   warn #D2A244
```

**Moon**
```
bg #0D1016   surface #161B22   surface-dim #11151B
line #28303B line-dim #1D242D
ink #E2E7EE  muted #8B95A4     faint #606977
accent #7FA8D9   accent-on #0B1A2B   hot #D97F86   warn #C9A15A
```

**Newspaper**
```
bg #FBF7EE   surface #F3EDE0   surface-dim #EEE7D7
line #DAD1BF line-dim #E6DFCF
ink #332F28  muted #736A5A     faint #908673
accent #2F6B8F   accent-on #EAF1F5   hot #A64B33   warn #8C6B1F
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

**There are no on-screen figures.** Every visual is reached through the export selector, which renders the card and shows it. That is one rendering path instead of two, and it means a visual has to earn a 4:5 card rather than existing only inside the app. Section 7 already said the card is a frame rather than a chart; this is that taken to its conclusion.

What the screen carries in its own right is text: the glossary, the ledger with its key, and the copyable report. The per-team summary strips are gone — every card already carries its own, so printing them on the page first said the same numbers twice before the reader reached anything they could take away.

**Every card renders, one after another.** There is no selector. A dropdown asked the reader to know what they were looking for before they could see anything, on a page whose whole job is to show them. Order is deliberate: the match-level overviews first — comparison, threat, timeline — then the per-team detail they summarise.

The **comparison leads**, because it is the summary every other card is a detail of. It carries no stat strip and no caption: the strip's numbers are rows in the table already, including set-piece and total npxG, and printing them twice on one card is just noise.

The **glossary sits above the first card**, under its own heading, open rather than collapsed. It explains the vocabulary every visual below uses, so it belongs before them and not tucked under a strip halfway down.

One card failing must not take the page with it. Nothing exercises these on screen any more, so an exception in a single visual would otherwise surface as a blank report rather than as one missing panel.

### Export panel

Row of type buttons, one per visual. Live preview of the branded card. Actions: download PNG, copy report, open a prefilled post.

---

## 7. Export spec

- 4:5 portrait, around 1080 by 1350. Takes more feed space than 16:9 and suits a tall pitch graphic.
- Rendered separately from the on screen figure. Different padding, different type sizes, and the branding block exists only on the export.
- Header: mark and wordmark left, match identity and competition right.
- **The vertical rhythm is constants too** (`TITLE_Y`, `STRIP_VALUE_Y`, `STRIP_LABEL_Y`, `STRIP_RULE_Y`, `VISUAL_CEILING`). Baseline gaps understate how close two blocks land when their type sizes differ: the title is 32pt against the strip's 25pt, so a 0.046 gap between baselines left almost no air and the two read as one stacked lump. The title now sits nearer the header rule and the strip drops away from it. `VISUAL_CEILING` is what stops a rect climbing back into the strip when heights are next adjusted — it was hand-checked per visual before, which is how three of them ended up overlapping.

- **One left margin and one right margin run the whole height of the card**, and they are constants (`MARGIN_L`, `MARGIN_R`) rather than literals repeated per element. They were literals, and when the caption was removed nothing recomputed around them: the heading sat at 0.150 on team cards because the crest was to its left, while the strip beneath it stayed at 0.075, so title and numbers did not share an edge — and only on some cards. The team crest now sits at the *right* end of the title line, mirroring the header above it. The away crest is placed by its centre, so it is inset half its width to finish on the margin rather than overshooting it.
- Title. **No caption.** A sentence under the title restated what the chart already showed, and on a card whose whole argument is the visual it read as hedging. The title names the thing; the graphic makes the case. The band it occupied went to the visual.
- **Header text is Title Case.** Not shouting caps, not lowercase.
- **Every element gets reserved space.** Charts are laid out in bands measured from the data, never as a fraction of the axis with labels dropped wherever they land — that put team names straight through the tick bars and clipped a 90th-minute goal off the right edge. Text near an axis edge anchors away from it.
- The visual.
- Legend using the notation vocabulary.
- Footer: "Data from Opta" left, "@mhassanfootball" right. The handle is **@mhassanfootball** — it goes on every graphic that leaves this app, so it is written down here rather than retyped from memory.
- The card takes the app's theme. Choosing it separately was a second control to set before you could download something you were already looking at.
- **Crests, not team names.** Names are long, inconsistently abbreviated by the feed, and push the header out of alignment; the crest says the same thing in a fixed box. Held at 75% opacity so it sits behind the type rather than competing with it. Falls back to names when an id has no badge.

**Every export is named for what it is.** `trazado-{visual}-{subject}-{match date}-{export stamp}.png`, where subject is a team slug for a per-team card and `home-vs-away` for a match card. Downloads accumulate in one folder, and `trazado-threat.png` collides with the next match and tells you nothing a week later. The export stamp is UTC and marked `Z` — the app already labels fixture times in UTC, and an unmarked local timestamp on a file that gets shared is ambiguous in exactly the way a timestamp exists to prevent.

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
