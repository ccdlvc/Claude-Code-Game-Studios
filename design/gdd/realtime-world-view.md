# Realtime World View

> **Status**: In Design
> **Author**: user + Claude (design-system, autonomous batch run; decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no `design/gdd/game-pillars.md`). Serves `JX1_Tycoon_GDD.md` §1 ("mô phỏng realtime trên map"), §2 ("Chiến đấu: Realtime trên map" [CHỐT]), §3.2 (Presentation reads events, sends commands), §3.5 (30 FPS mid-range, pooling, presentation LOD, paper-doll sprites) and §6.13 (≤ 15 full sprites in a raid)
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief to check against. Player Fantasy is anchored to `JX1_Tycoon_GDD.md` §1 instead. Re-run once pillars exist.

## Summary

The Realtime world view is the living pixel map the player watches: the guild town, the hunting grounds and the Golden Boss arena, with every member walking, fighting, coming home and resting exactly as the simulation says. It draws only; it never decides an outcome, and the camera never changes what happens. It exists because the game's promise is "my guild is out there working, and I can watch it", and that promise is kept only if what the player sees is the fight and the trip that were actually computed.

> **Quick reference** — Layer: `Presentation` · Priority: `MVP` · Key deps: `Sim core, Event bus, Command layer, Localization, Member model, Member state machine, Zones and hunt, Combat, Golden Boss`

## Overview

**Framing: both** (UI category: player-facing, with a strict read-only data contract beneath it).

The world view is the Godot scene layer that turns the headless Simulation Core into something to watch. It has three kinds of **location**: the **Town** (the guild compound: buildings, gate, inn, Linh Miếu shrine, infirmary, Elders' hall, guild banner), one location per live **Ground**, and the **Raid arena** while a Golden Boss raid is gathering or fighting. The camera shows one location at a time; a location strip shows the others as markers with counts. Each frame the view reads the Sim core's read-only facade (Sim core R15): the tick's event batch, `tick`, `alpha`, `catching_up`, `handoff_pending` and `debt_us`, plus committed state between ticks. From those it **choreographs**: it places members on paths computed from their state and step timers, plays each fight back from Combat's action timeline, and shows the beats other systems asked for (homecoming, level-up, raid call, arrivals at the gate). The player interacts in two ways only: moving the camera and tapping a member or building to open its card, from which orders go through the Command layer. Positions, poses, particles and camera are presentation state; none of it is saved or logged, and none of it reaches a handler.

**Why it exists.** Every gameplay GDD already lists what it needs drawn (Combat V/A 1–4, Zones V/A table, Member state machine V/A, Golden Boss V/A, Guild and buildings V/A). Without this system those requirements have no owner and the "realtime on the map" decision of GDD §2 is not delivered. Implementation patterns (scene tree, pooling, shader use, integer scaling setup) are left to ADRs; this document describes behaviour.

## Player Fantasy

**Framing: direct.** The player looks at this system for most of every session.

*No game pillars exist, so no pillar is quoted. The candidates are anchored to `JX1_Tycoon_GDD.md` §1 (the guild loop) and the Player Fantasies of Zones ("They come home richer") and Combat. CD-GDD-ALIGN remains NOT ASSESSED.*

Three framings were considered (creative-director lens):

1. **"A window onto a living guild" — chosen.** *The moment:* the player opens the game on the bus, and the town is mid-afternoon busy: two members sit at the inn with a "zzz" icon, a party of five is walking through the gate with loot sacks, and a stranger in plain travel clothes waits at the gate to be recruited. The player did nothing, and the guild still feels alive and theirs. This asks for every state to be readable at a glance, for the town to be the default view, and for nothing to stand still without a reason.
2. **"What you see is what happened" (trust).** *The moment:* a healer's green number lands on the tank one hit before the tank would have dropped, and the party wins. The player later reads the trip report and the numbers match. This is the **non-negotiable constraint** under framing 1 rather than a separate fantasy: the view replays the computed fight and never invents misses, hits or near-deaths (Combat Game Feel "Trust").
3. **"The general's map" (command).** *The moment:* the player pans to the ground, sees the party fighting a countered element, taps the leader and orders them home. Kept as the **secondary line**: orders are possible from the map, but Utility AI makes most choices, so the view is mostly watched, not operated.

**Target feeling.** Calm, ambient attention with frequent small payoffs. A two-minute glance should usually show at least one homecoming somewhere (Zones Game Feel), and nothing on the map should ever demand a reaction.

## Detailed Design

### Core Rules

Rules are numbered R1–R16.

**Contract**

**R1 — Draw only; never decide.** The view reads the Sim core facade and committed state, and its only outputs are pixels, sound-cue context for Audio (R13) and commands the **player** taps (R11). It never submits a command on its own, never calls a handler, never derives a simulation random generator and never writes state. The camera, the selected location, zoom, selection and every cosmetic value are absent from the command log, saves and events (Sim core R6, Zones R12). Consequence, tested by AC-1: a session with the camera moved anywhere produces the same command log, saves and event stream as the same session with the view never opened.

**R2 — Read between ticks.** The view reads committed state only between ticks, never during one (Sim core R15). Each render frame it: (1) takes every event batch the host's `advance` calls produced since the last frame, in tick order; (2) applies them to its own presentation model; (3) reads `tick`, `alpha` and the catch-up flags; (4) draws. Events are read-only copies (Sim core R15); the view keeps only the fields it needs.

**R3 — The view owns all positions.** The simulation has no positions (Combat has no spatial model; Zones steps are timers). Every on-screen position is computed by the view from (location, member state, trip step, the step's start and due ticks) by F2, so a frame can always be drawn from committed state alone, after a load, a resume or a catch-up, with no history needed. Cosmetic variation (idle wander targets, particle spread, sprite jitter) uses the **engine's** random functions, which is allowed for presentation and forbidden in the simulation (Deterministic RNG R1).

**Locations and camera**

**R4 — Locations.** A location is one of: `town` (always), `ground:<uid>` for every ground that is `content_live` (Data layer F2) and unlocked or holding a trip, and `raid` while a raid is in `Gathering` or `Fighting` (Golden Boss states). In MVP that is the Town, the one slice ground and the raid arena. Each location is a fixed authored backdrop with **anchors**: named points the choreography uses (`gate`, `inn_seats[]`, `shrine`, `infirmary_beds[]`, `banner`, `building:<kind>`, `ground_edge`, `fight_spots[]`, `arena_ring[]`). Locations are not connected in space: travel between Town and a ground is drawn as leaving one location's edge and arriving at the other's (R6).

**R5 — Camera.** The camera shows one location at a time. The player pans by drag (clamped to the location's bounds) and zooms between the integer pixel scales in `view_zoom_levels` (pixel art stays crisp; no fractional scale). A **location strip** (tabs at the screen edge) lists every location with a marker count (members present, a fight icon if any fight is in progress, a raid icon while the arena exists); tapping a tab switches location with a short cut, not a scroll. The game opens on `town`. The camera never moves by itself, except that **Follow** on a selected member (R10) keeps that member centred and switches location when the member travels; any drag cancels Follow. A raid announcement shows a "Go to raid" action on the Golden Boss banner (Golden Boss UI) and does not jump the camera unasked.

**Choreography**

**R6 — Members are drawn from state.** Each member is drawn in exactly one place per frame, chosen from Member state machine's state (MSM "Where" column) and, while `hunting` or `returning`, from the Zones trip step:

| MSM state / trip step | Location | Drawn as |
|---|---|---|
| `idle` | town | wanders between plaza anchors (cosmetic) |
| `hunting` · Outbound | town → ground | walks from the plaza to `gate` and leaves (Town half of the travel), then enters at `ground_edge` and walks to a free `fight_spot` (ground half); F2 splits the travel time 50/50 |
| `hunting` · Engaging / Gap | ground | at the party's `fight_spot`, fighting (R7) or standing ready |
| `returning` · Homebound | ground → town | reverse of Outbound, carrying a loot sack sized by bag fill |
| `returning` · Selling | town | at the market building; the settlement beat (R8) |
| `resting` | town | seated at `inn_seats` (or the trip's rest spot) with "zzz" |
| `dead` | ground → town | spirit marker follows the party home, then waits at `shrine` |
| `injured` | town | in an `infirmary_bed`, bandaged |
| `boss_raid` | town banner, then raid | gathers under `banner`; on `gb_started` (1402) the raid location holds them on `arena_ring` |
| `training` | town | at the training building, seated with a scroll |
| `bounty` | off map | not drawn; a pin on the notice board |
| `away` | town, once | walks out of `gate` and fades (Retention V/A), then not drawn |
| `elder` | town | at the Elders' hall |

A state with no anchor free (more members than seats) stacks members at the anchor with a small offset; nothing is ever drawn outside its location.

**R7 — Fights are played back from the computed timeline.** When a fight is in progress at the viewed location, the view requests that fight's action timeline once, between ticks, through a **side-effect-free sim query** `fight_timeline(fight_key) → timeline` [PROVISIONAL: Zones (11) and Golden Boss (14) to provide; see Interactions and OQ-1]. The query recomputes the fight with Combat's `resolve(..., want_timeline = true)` on a copy of the saved inputs and the same keyed generator, which Combat AC-5 guarantees gives an identical result; it touches no state, so the camera still changes nothing. The view then plays each record at F3's time: attack pose and damage number per attack, a heal number and beam on heals, a hit flash on monster attacks, a death pose and fade on deaths. HP bars move with each record's `target HP after`. The fight's result is applied by the simulation at Combat's deadline tick (Combat F8); the last record plays at `duration_s`, which is never later than the deadline, so the view is always at or ahead of applied state and never shows an HP the simulation does not reach. Fights at locations not being viewed are never queried and cost the view nothing. A trip whose latched tier is `card` (Zones R17) has no fight to rebuild; the view never queries it and draws it by R17 below.

**R8 — Beats requested by other systems.** The view draws the beats the owning GDDs specify, driven by their events, and owns only the timing and pooling rules of this GDD. The event-to-beat map (owners decide content; this system decides how it is drawn and limited):

| Event (owner) | Beat | Limit |
|---|---|---|
| 1101 trip started (Zones) | "→ ground" tag over the leader as the party leaves | 1 per party |
| 1102 kill (Zones) | monster death puff; drop icons fly to the nearest member's sack | drop icons count towards the effect cap (F5) |
| 1103 member downed (Zones) | fall, then spirit marker | — |
| 1104 trip ended (Zones) | reason icon over the leader (bag, heart, broken sword, horn, flag) for `view_icon_s` | 1 per party |
| Selling → settlement (Zones R8, Items, Gold economy) | sacks empty into the market, gold counter rises over `sell_s`, level-ups pop as they arrive | the beat lasts the whole selling step, never instant |
| 1105 first zone entry (Zones) | zone-name banner over the location strip | — |
| 1401 announced, 1402 started, 1403/1404/1405 (Golden Boss) | drum banner and countdown (Golden Boss UI owns the banner), arena opens, win/loss stamp, result card (39) | — |
| 1501 candidate offered (Recruitment) | one pixel figure per candidate at `gate` | until accepted, rejected or expired |
| 1601 leave request (Retention) | speech-bubble icon over the member | until answered |
| 2101 skill level-up (Skills), 2201 level-up (XP curve) | text pop over the member | F6: at most one pop per member per `pop_min_interval_s`, extras merged |
| 2102 skill milestone, `school_joined` / `school_changed` (Schools) | short glow on the member | F6 |
| 3002/3003/3004 build started/completed, guild level up (Guild and buildings) | scaffolding while building; completion puff; larger banner for guild level | — |
| 4101 state changed (MSM) | the transition animation of MSM V/A ("set off", sack drop, revive light) | F6 |
| `command_applied` / `command_refused` (Command layer R11) | pending marker resolves on the member or building it targets | every order resolves visibly (Command layer Game Feel) |
| Utility AI ground choice (Utility AI V/A) | target ground's element glyph over the leader for `intent_cue_s` | 1 per party |

Any event the table does not name is ignored by the view (it may still be heard by Audio or shown by Guild screens).

**Budgets and level of detail**

**R9 — Presentation LOD.** At most `view_full_sprites_max` members are drawn as full paper-doll sprites at once; the rest of the members at the viewed location are drawn as **group tokens** (one token per party with the party's role icons, member count and a shared HP bar). Which members get full sprites is F4: nearest to the camera centre first, with hysteresis so sprites do not flicker between full and token while the camera pans. Monsters in a fight with a full-sprite party are always full. Damage and heal numbers on screen are capped at `view_damage_numbers_max` (F5). These rules choose only **what to draw**, never what is computed (Zones R12). Which grounds are *simulated* in detail is a separate, in-sim rule (Zones R17) that the camera cannot influence; this rule is presentation LOD on top of it. In an ordinary MVP town or ground the cap is rarely reached; it exists for the raid (§6.13) and for large guilds later.

**R10 — Selection and Follow.** Tapping a full sprite or a group token selects it (a token selects its party; a second tap on the token cycles through its members). The selected member shows a name label (Localization `short` field, F4 fit) and opens the **member quick card** (state, HP, bag fill, needs icons, current order, order buttons; layout owned by Guild screens 39). A **Follow** toggle on the card centres the camera on the member (R5). Selection survives location switches; it clears when the member leaves the guild (Edge Cases). Tapping a building opens its card (Guild screens 39). Tapping empty ground clears selection.

**Orders and catch-up**

**R11 — Orders only through the Command layer.** Every order the player gives from the map (quick card buttons, "Hunt here" on a ground's card) is a Command layer `submit` (Command layer R11). The view shows the **pending** marker on the target in the frame of the tap and resolves it on the outcome event, with the refusal reason in words (Command layer UI 1–5). The view never pre-animates the effect of an order before `command_applied` (for example a member does not turn for home until the trip's step actually changes), so a refused order never shows a move that did not happen.

**R12 — Catch-up and hand-off.** While `catching_up` or `handoff_pending` is true (Sim core R17), the view: (1) stops per-event beats, animation and cue context (R13); (2) keeps drawing the last committed state with sprites frozen in place (idle breathing only); (3) shows a **catching-up overlay** with progress from F7 and, during an offline `Resolving`, Offline progress's own progress; (4) keeps taking input: camera, selection and orders (orders show as pending "waiting on the guild", Command layer UI 5). When both flags clear, the view **snaps** to committed state (every member re-placed by F2 from its current step) and shows no beats for events that occurred during catch-up, except a single merged toast per category (for example "3 level-ups") so nothing important is silently lost; the full account is the "while you were away" report (Offline progress 31, Guild screens 39).

**R13 — Cue context for Audio.** The view exposes a read-only `view_context` each frame: the viewed location, the camera rectangle, the set of members drawn as full sprites, `suppressed` (true during catch-up, R12), the reduced-motion flag (R15) and `played_records` — the Combat timeline records (Combat R14 format) whose playback time fell inside this frame, for the fights the view is drawing (R7). *(`played_records` added by consistency-check 2026-11-16 for Audio OQ-2.)* Audio (40) uses it to play location-bound cues only for what is on screen (Zones V/A "only for the ground on screen"). The view plays no sound itself.

**Text and accessibility**

**R14 — Text through Localization.** Every on-map string (names, damage numbers, tags, banners, reason labels, the overlay) is drawn with Localization's `text()` and number formatting (Localization F1, F2, F4). A locale switch applies on the next frame (Localization R7.3): persistent labels re-render; transient pops already on screen finish in the old locale (≤ `view_icon_s`). Names truncated by F4 have the full name on the quick card.

**R15 — Accessibility floor.** No information by colour alone: elements carry their glyph, counter hits are larger with a glyph and countered hits smaller (Combat V/A 2), states carry an icon (MSM V/A), reasons carry an icon and text. Screen shake, hit-stop and the location cut honour the **reduced motion** setting (Settings 45 R12a), which replaces them with none, none and a fade. The view also reads Settings' **text size** (scales name plates, damage numbers and toasts; world sprites keep their integer scale) and the **colorblind-safe five-element palette** (swaps element tints on sprites, hit pops and ground markers; glyphs stay). All three apply on the next frame. *(Updated 2026-11-16: Settings is designed.)* Every tap target is at least `view_min_tap_px` physical pixels. Damage numbers have an outline readable on every backdrop.

**R16 — Background and resume.** When the app loses focus, the view stops drawing; the host decides whether the core keeps ticking (Sim core). On return, the next frame is drawn from committed state (R3), and any catch-up runs under R12.

**R17 — Card-tier trips (simulation LOD).** Zones R17 runs most trips on less-populated grounds at the `card` tier: their fights are replayed from a saved record rather than fought by Combat, so no hit-by-hit timeline exists. The view reads each trip's latched `tier` from committed trip state and, for a `card` trip at the viewed location:
1. **Still draws every member** exactly as R6 (walking out, at the ground, engaging, returning) and the monster of the current encounter from trip state.
2. **Draws the encounter as abstract activity:** a looping skirmish animation (dust cloud, weapon glints, the party token's role icons pulsing) for the encounter's length. **No fabricated hits:** no damage or heal numbers, no hit flashes, no attack poses tied to records, no `fight_timeline` query. HP bars hold the pre-encounter HP and change once, at Combat's deadline tick, to committed HP (as the `Unavailable` path, Edge Cases).
3. **Plays every real outcome:** the kill puff and loot pop on 1102, the downed pose on 1103, the reason icon on 1104, and the homecoming beat — these are simulation events, not inventions.
4. **Says so:** the ground's tab and the party token carry a small "summarised" glyph (≈) with tooltip text "Hunting summarised — busiest grounds are shown blow by blow" (keyed, R14; not colour-only, R15).
5. **Never changes it:** looking at a card-tier ground does not promote it; the player promotes a ground only by sending more members there (Zones F11). A ground can hold detailed and card trips at once after a tier switch; each trip is drawn by its own tier.

### States and Transitions

The view has one global state machine and, per fight, a playback state.

**View states**

| State | Entered when | Behaviour | Leaves to |
|---|---|---|---|
| `Loading` | app start, before the core is `Running` | splash and loading bar; no map | `Live` (core `Running`, no catch-up) · `CatchingUp` (core `Running` with `catching_up` or `handoff_pending`) · `Failed` |
| `Live` | core running, both flags false | full choreography and beats (R6–R9) | `CatchingUp` · `Background` · `Failed` |
| `CatchingUp` | `catching_up` or `handoff_pending` true | R12 overlay; input on, beats off | `Live` (both flags false; snap) · `Background` · `Failed` |
| `Background` | app focus lost | no drawing | `Live` / `CatchingUp` on focus (by the flags) |
| `Failed` | core `Failed` | the map is hidden; the failure screen (Sim core UI Requirements, owned by Guild screens 39) | `Loading` (on "Reload last save") |

Every transition not listed is invalid. A core `Paused` (debug or host pause) is drawn as `Live` with every timer frozen (members hold their F2 positions, because `tick` does not move).

**Fight playback states** (per fight shown at the viewed location)

| State | Meaning | Next |
|---|---|---|
| `Requested` | the fight started (or the view arrived mid-fight) and the timeline query is pending for the next between-tick read | `Playing` · `Unavailable` |
| `Playing` | records play at F3 times | `Holding` at `duration_s` |
| `Holding` | last record shown; waiting for the deadline tick (< 1 tick) | `Done` when the trip's step leaves Engaging |
| `Unavailable` | the query returned nothing (Edge Cases) | `Done` at the deadline tick; HP bars move once to the applied HP, no numbers |
| `Done` | released to the pool | — |

Leaving the location drops all playbacks there to `Done`; coming back mid-fight starts `Requested` again and seeks (F3).

### Interactions with Other Systems

| System | Direction | Data | Owner of interface |
|---|---|---|---|
| Sim core (1) | core → view | read-only facade: event batches, `tick`, `alpha`, `catching_up`, `handoff_pending`, `debt_us`; committed state between ticks (R15, F3) | Sim core |
| Event bus (42) | bus → view | the full tick batch through the facade | Event bus |
| Command layer (5) | view → layer | `submit`, `submit_batch`; `[seq, reason]`; outcome events | Command layer |
| Localization (4) | view → loc | `text(key, field, args)`, F1, F2, F4, live switch | Localization |
| Member model (8) | model → view | read-only record and profile: school (sprite), element (palette), name record, HP max | Member model |
| Member state machine (41) | MSM → view | state, timers, needs vs thresholds, orders; events 4101–4103 | MSM |
| Zones and hunt (11) | 11 → view | trip state per party: ground, roster, step, step start and due tick, bag fill, latched `tier` (Zones R17); events 1101–1105; `fight_timeline` query (Zones R12; `none` for card replays) | Zones |
| Combat (10) | indirect | timeline records (time, actor, kind, target, amount, HP after, died) via the caller's query; element multiplier class for counter/countered display | Combat (record format) |
| Golden Boss (14) | 14 → view | raid state, participants, groups, boss row; events 1401–1408; raid `raid_fight_timeline` query (Golden Boss R8) | Golden Boss |
| CA/PA and traits (9) | 9 → view | `pa_view`, `traits_view`, `ca` only (R12 of 9), for the quick card | CA/PA |
| Guild and buildings (30) | 30 → view | built kinds and level bands, build queue, events 3001–3007 | Guild and buildings |
| Recruitment (15), Retention (16), Skills (21), XP curve (22), Schools (20), Utility AI (12), Items (26), Gold economy (27), Party (13) | → view | the events and read models named in R8 and R10 | each owner |
| Offline progress (31) | 31 → view | `Resolving` progress and the summary record (for R12's toasts) | Offline |
| Guild screens (39) | view ↔ 39 | the view opens cards and the failure screen that 39 lays out; 39 can ask the view to focus a member or location | Guild screens |
| Audio (40) | view → audio | `view_context` (R13) | this system |
| Settings (45) | 45 → view | reduced motion, (later) damage-number toggle [PROVISIONAL] | Settings |
| Deterministic RNG (2) | none | the view must not depend on it (RNG Dependencies) | — |

*Specialist lenses applied in this session (game-designer primary; ux-designer, ui-programmer, art-director, technical-artist supporting, per the UI row of the routing table):*
- **game-designer** — the view serves watching, not operating; the one decision it hosts is "do I step in" (order home, hunt here), so the quick card must surface the facts that decide it (HP vs flee line, bag fill, element matchup).
- **ux-designer** — Town is the default because it is where most states are visible at once; location switching is a cut with a strip, not a scroll, so the player always knows where they are; every order has pending → resolved feedback.
- **ui-programmer** — all text through `text()` with F4 fit; labels sized for Vietnamese (longer than English); quick card is a 39-owned scene, not duplicated here.
- **art-director** — one base body per role and palette swaps (§3.5, Zones constraints); beats are short and small; the homecoming is the signature moment and gets the longest beat.
- **technical-artist** — pooled sprites, numbers and particles; integer scaling only; a fixed LOD cap rather than distance culling alone, because a raid puts everyone in one place.
- *Tension surfaced:* art-director wanted the camera to auto-cut to the raid on `gb_started`; ux-designer and the idle fit (Combat Game Feel "nothing demands attention") argued against moving the camera unasked. Resolved for **no auto-jump** (R5), logged as a decision; the banner's "Go to raid" button keeps it one tap away.

## Formulas

All formulas run in presentation only. They use floats freely, because nothing they produce is saved, logged or read by a handler (Sim core F3 note).

### F1 — View time

The view_time formula is defined as:

`view_time_s = (float(tick) + alpha) / float(tick_rate)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| tick | int | 0 – 2^62 | calculated (Sim core facade) | Last committed tick |
| alpha | float | 0.0 – 1.0 | calculated (Sim core F3) | Fraction towards the next tick, clamped |
| tick_rate | int | 1 – 20 (10 today) | data file (`config.csv`, registry `tick_rate`) | Ticks per second |
| view_time_s | float | ≥ 0 | calculated | The world-time the frame draws |

**Output Range:** monotonic non-decreasing in normal play. During catch-up `alpha` is clamped to 1.0 and the view does not use F1 for animation (R12).
**Example:** `tick = 36,000`, `alpha = 0.4`, `tick_rate = 10` → `view_time_s = 3,600.04`.

### F2 — Step progress and position

The step_position formula is defined as:

`p = 1.0 if due_tick <= start_tick else clamp((float(tick) + alpha − start_tick) / (due_tick − start_tick), 0.0, 1.0)`
`pos = lerp(anchor_from, anchor_to, ease(p))`, with Outbound/Homebound split: Town half for `p < 0.5` (rescaled `2p`), location half for `p ≥ 0.5` (rescaled `2p − 1`)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| start_tick, due_tick | int | ≥ 0 | calculated (Zones trip step / MSM timer) | Start and end of the current step |
| anchor_from, anchor_to | Vector2 | location bounds | data file (location scene anchors) | Where the step starts and ends on screen |
| ease | function | [0,1] → [0,1] | constant (smoothstep) | Walk easing; identity for timers that are not walks |
| p | float | 0.0 – 1.0 | calculated | Progress through the step |

**Output Range:** `pos` always lies on the segment between the anchors; `p` is clamped, so a late frame or an early due tick never draws a member past its target. `due_tick ≤ start_tick` (a zero-length step) snaps to the target.
**Example:** Outbound with `start_tick = 1,000`, `due_tick = 1,300` (travel 30 s), `tick = 1,060`, `alpha = 0` → `p = 0.2` → Town half, rescaled 0.4 of the way from plaza to `gate`.

### F3 — Timeline record time

The record_play_time formula is defined as:

`play_at_s = fight_start_tick / tick_rate + rec.time_s`; a record plays on the first frame with `view_time_s ≥ play_at_s`. On arriving mid-fight, every record with `play_at_s < view_time_s` is applied silently (HP bars set, deaths set, no numbers), and playback continues from the next one.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| fight_start_tick | int | ≥ 0 | calculated (Zones step start / Golden Boss gathering end) | Tick the encounter started |
| rec.time_s | float | 0 – `fight_time_limit_s` (600) / `raid_time_limit_s` (300) | calculated (Combat timeline) | Record time from fight start |
| play_at_s | float | ≥ 0 | calculated | World-time the record is shown |

**Output Range:** the last record's `play_at_s` is `fight_start_tick / tick_rate + duration_s` (Combat AC-5), which is ≤ the deadline tick's time `(fight_start_tick + ceil(duration_s × tick_rate)) / tick_rate` (Combat F8). The gap is under one tick (`Holding`).
**Example:** fight starts at tick 5,000 (500.0 s); a heal record at `time_s = 7.3` plays at 507.3 s. Deadline for `duration_s = 15.6` is tick 5,156 (515.6 s), equal to the last record's time.

### F4 — Full-sprite selection (LOD)

The full_sprite_set formula is defined as:

`score(m) = |screen_pos(m) − camera_centre|² − (h² if m was full last frame else 0)`; `full_set = the view_full_sprites_max members with the lowest score`, ties broken by ascending `member_id`. The selected member is always in the set (it replaces the highest-scoring member).

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| screen_pos(m) | Vector2 | location bounds | calculated (F2) | Where member m is drawn |
| camera_centre | Vector2 | location bounds | calculated (camera) | Centre of the view |
| h | float | 0 – 128 px | data file (`view_lod_hysteresis_px`) | Distance advantage kept by an already-full sprite, against flicker |
| view_full_sprites_max | int | 5 – 40 (15) | data file | Full-sprite cap (§6.13) |

**Output Range:** `|full_set| = min(members_at_location, view_full_sprites_max)`. At `h = 0` sprites may swap every frame at the boundary; at large `h` a far sprite keeps full detail after the camera pans away (bounded by the cap, so cost never rises).
**Example:** 20 raiders, cap 15, `h = 32`: the 15 closest are full; a member 30 px outside the boundary but full last frame stays full until another is more than 32 px closer.

### F5 — Damage-number and effect admission

The number_admission formula is defined as:

`merge` if a number for the same target and kind spawned less than `dmg_merge_window_ms` ago (its amount becomes the sum and its lifetime restarts); else `spawn` if `active < view_damage_numbers_max`; else `recycle` the oldest active number. Effects (sparks, drop icons, puffs) follow the same rule with `view_effects_max`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| active | int | 0 – cap | calculated | Numbers on screen |
| view_damage_numbers_max | int | 5 – 60 (20) | data file | Cap (Combat V/A 4 proposed 20) |
| dmg_merge_window_ms | int | 0 – 500 (200) | data file | Merge window for multi-hit skills |
| view_effects_max | int | 10 – 100 (40) | data file | Cap on pooled effects |

**Output Range:** never more than the cap on screen; the pool never grows past the cap. Merging changes only how numbers are grouped, never their sum: every point of computed damage is shown in some number (trust).
**Example:** a 3-hit skill deals 40, 42, 39 within 150 ms on one monster → one number "121". At 20 numbers active, a new hit replaces the oldest.

### F6 — Pop rate limit

The pop_admission formula is defined as:

`show` if `now_s − last_pop_s(member) ≥ pop_min_interval_s`; else merge into the pending pop for that member ("Lv 12 → 14", "+2 skills"), shown when the interval elapses.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| now_s | float | ≥ 0 | calculated (host monotonic clock, not view time) | Real time, so a slow phone does not stack pops |
| last_pop_s(member) | float | ≥ 0 | calculated | Last pop shown over this member |
| pop_min_interval_s | float | 0.25 – 3.0 (1.0) | data file | Minimum spacing per member (Skills V/A: one per member per second) |

**Output Range:** at most one pop per member per interval; no pop is dropped, only merged.
**Example:** settlement gives a member two level-ups 0.3 s apart → one pop "Lv 12 → 14".

### F7 — Catch-up progress

The catchup_progress formula is defined as:

`progress = clamp(1.0 − float(debt_us) / float(debt_peak_us), 0.0, 1.0)`, where `debt_peak_us` is the largest `debt_us` seen since the view entered `CatchingUp` (reset on entry).

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| debt_us | int | 0 – T_us and above | calculated (Sim core facade) | Unspent time still owed |
| debt_peak_us | int | ≥ 1 | calculated | Peak debt this catch-up |
| progress | float | 0.0 – 1.0 | calculated | Bar fill |

**Output Range:** 0 to 1. If debt grows during the drain, the peak grows and the bar can step back; the bar never shows more than 100 % or less than 0 %. During `handoff_pending` the overlay shows Offline progress's `Resolving` progress instead.
**Example:** entry debt 40 s, now 10 s owed → 75 %.

### F8 — View frame budget (scaling statement)

The view_budget formula is defined as:

`c_view_ms ≤ view_share × frame_budget_ms`, with `view_share = 1 − sim_share − engine_share`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| frame_budget_ms | float | 16.67 – 33.3 | constant (`technical-preferences.md`; 30 FPS target §3.5) | Frame time |
| sim_share | float | 0.5 | constant (Sim core F6) | Simulation's half of the frame |
| engine_share | float | 0.2 – 0.35 (0.3 provisional) | constant (P1 spike measures) | Godot's own render and input cost |
| c_view_ms | float | ≥ 0 | calculated (profiler) | View script cost per frame: event application, choreography, LOD, pooling |

**Output Range:** at 30 FPS, `0.2 × 33.3 = 6.7 ms` for view scripts. The view's per-frame cost must scale with **drawn** objects (≤ cap) plus events this frame, never with roster size: members not at the viewed location cost one state read each, and only when their state changes (from 4101), not per frame.
**Example:** a 40-member raid with cap 15: 15 full sprites, 5 tokens, ≤ 20 numbers; target `c_view_ms ≤ 6.7` on the min-spec phone (AC-17, P1 spike).

## Edge Cases

- **If the view opens mid-fight**: F3 seeks; already-past records apply silently; playback continues. No fight is replayed from its start.
- **If `fight_timeline` returns nothing** (the query is not yet built, the inputs cannot be rebuilt after a migration, or the fight's key is unknown): playback is `Unavailable`; the view draws the party in a generic fighting loop with **no numbers**, and at the deadline tick HP bars move once to the applied HP and deaths are shown. It never draws invented hits (trust). A dev build logs the cause.
- **If a viewed trip is card tier** (Zones R17): no timeline is queried; the encounter is drawn as abstract activity with zero numbers, and only real events (kill, downed, return) produce beats (R17). Switching the camera to or from that ground changes neither its tier nor any result.
- **If two or more parties fight at the same location**: each has its own playback; numbers share the global cap (F5).
- **If a member is selected and leaves the guild** (`away` completes, dismissal): the quick card closes and selection clears on the event; Follow stops.
- **If the selected member is off map** (`bounty`, `away`): the card stays open; the camera does not move; Follow is disabled with a reason.
- **If a ground stops being live** (content wave change after an update) while being viewed: its tab disappears at the next frame and the camera cuts to Town; members still in a trip there are drawn on the road token in the strip until the trip ends (the simulation decides what happens to them, not the view).
- **If more members need an anchor than it has slots** (inn seats, infirmary beds): extras stack with a small offset at the anchor; no member is hidden.
- **If 40 members change state in one tick** (raid recall, MSM peak 40): every transition animation starts that frame; pops follow F6; the frame cost is bounded by F8 because animations are pooled and capped.
- **If a pending order's target disappears before its outcome** (member leaves, building removed): the marker resolves when the outcome event arrives, shown in the card or a toast if the target is gone; it never stays up forever (Command layer "never silent").
- **If the core enters `Failed`**: the map is hidden at once; no partial frame of the failed tick is drawn (the core discards it, Sim core R10).
- **If a raid announcement arrives during catch-up**: no banner animation; on exit the snap shows the current raid state (arena if already fighting, banner if still gathering), plus one merged toast.
- **If `tick_rate` changes in config**: F1–F3 use the current value; nothing in the view assumes 10 Hz.
- **If the locale switches while pops are on screen**: those pops finish in the old locale (≤ `view_icon_s`); every persistent label is in the new locale next frame (R14).
- **If the device rotates or the window resizes**: the camera re-clamps to the location bounds and keeps its centre; zoom stays at the nearest valid integer scale.
- **If the camera is at a location with nobody there**: the backdrop plays its ambient animation; the strip shows where everyone is. There is no "nothing to see" error.
- **If a member's HP in committed state disagrees with the playback's last HP at the deadline** (a bug, since Combat AC-5 forbids it): the view snaps to committed state and a dev build logs a parity warning (AC-6 catches it).

## Dependencies

### Upstream (this system depends on)

| System | Hard / Soft | Interface | Status |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | read-only facade, `alpha` (F3), catch-up flags, `debt_us` | GDD exists |
| Event bus and history log (42) | Hard | per-tick event batch via the facade | GDD exists |
| Command layer (5) | Hard | `submit`, `submit_batch`, outcome events | GDD exists |
| Localization (4) | Hard | `text()`, F1, F2, F4, live switch | GDD exists |
| Member model (8) | Hard | record, profile, name record, school for sprite | GDD exists |
| Member state machine (41) | Hard | states, timers, needs, 4101–4103 | GDD exists |
| Zones and hunt trips (11) | Hard | trip state, step timers, 1101–1105, `fight_timeline` query | GDD exists; query conformed (OQ-1) |
| Combat (10) | Hard (through 11, 14) | timeline record format; counter/countered class | GDD exists |
| Golden Boss and guild raid (14) | Hard for the raid arena | raid state, groups, 1401–1408, raid timeline | GDD exists; timeline source conformed (OQ-2) |
| Guild and buildings (30) | Soft | built kinds, level bands, 3001–3007 | GDD exists |
| CA/PA and traits (9), Recruitment (15), Retention (16), Skills (21), XP curve (22), Schools (20), Utility AI (12), Items (26), Gold economy (27), Party (13), Offline (31) | Soft | events and read models in R8, R10, R12 | GDDs exist |
| Settings (45) | Soft | reduced motion | No GDD — PROVISIONAL (OQ-5) |

### Downstream (systems that depend on this one)

| System | Hard / Soft | Interface | Status |
|---|---|---|---|
| Audio (40) | Hard | `view_context` (R13) incl. `played_records` | GDD exists — conforms (OQ-6 resolved) |
| Guild screens (39) | Soft | open card / focus member / focus location calls; the view hosts the cards 39 lays out | No GDD — PROVISIONAL (OQ-4) |
| Onboarding (44) | Soft | highlight a member, building or location (focus calls) | No GDD |

**Bidirectional check.** Every upstream GDD above already lists the world view (38) as a downstream consumer (verified by search this session), except Settings, Audio, Guild screens and Onboarding, which have no GDD yet. The systems index row lists Localization, Sim core, Command layer, Member model, Combat, Zones and hunt, Golden Boss and Event bus; this GDD adds Member state machine (41) as a hard dependency (its states are what most of the map draws) and the soft ones above.

## Tuning Knobs

All knobs are **presentation config**, read by the view only. They must not enter the simulation's content hash (changing them must not change leaderboards or replays). Where they live is open (OQ-3).

| Knob | Today | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `view_full_sprites_max` | 15 | 5 – 40 | frame drops in a raid (§6.13) | the guild looks like tokens | P1 spike sets it; F8 |
| `view_lod_hysteresis_px` | 32 | 0 – 128 | far sprites stay detailed after a pan | flicker at the LOD edge | full-sprite cap |
| `view_damage_numbers_max` | 20 | 5 – 60 | unreadable clutter, cost | multi-party fights lose numbers to recycling | merge window |
| `dmg_merge_window_ms` | 200 | 0 – 500 | separate hits blur together | multi-hit skills spam numbers | numbers cap |
| `view_effects_max` | 40 | 10 – 100 | cost | kills without a puff | — |
| `pop_min_interval_s` | 1.0 | 0.25 – 3.0 | level-ups feel delayed | pops stack over a head | Skills V/A "one per second" |
| `view_icon_s` | 2.0 | 1.0 – 5.0 | icons linger and overlap | reason icons missed | — |
| `intent_cue_s` | 1.5 | 0.5 – 3.0 | — | — | owned by Utility AI V/A; listed here, not duplicated |
| `view_zoom_levels` | {2, 3} (integer pixel scales) | 1 – 6, integers | too few members on screen | sprites unreadable on a phone | sprite size from the art bible (32×32 or 48×48, §12.4) |
| `view_min_tap_px` | 44 | 40 – 64 | crowded taps hit the wrong member | taps miss small sprites | zoom |
| `engine_share` (F8) | 0.3 | 0.2 – 0.35 | view budget too small | — | measured, not tuned (P1 spike) |

Settlement duration (`sell_s`), fight pacing and trip timers belong to Zones and Combat; the view only follows them.

## Visual/Audio Requirements

*Art-director lens applied. No art bible exists (`design/art/art-bible.md` absent), so this is drafted from GDD §3.5 (paper-doll, palette swap per element, atlas, pooling) and §12.4 (AI-assisted pixel art, small sprites, few frames, code-drawn placeholders). Revisit after `/art-bible`.*

1. **Pixel discipline.** Integer scaling only (R5); one shared palette; sprites at the art bible's size (32×32 or 48×48 proposed in §12.4). Placeholders are code-drawn shapes coloured by element with the element glyph (§12.4, P3 "placeholder bằng code theo hệ/phái"), so the view is buildable before art exists.
2. **Member sprites.** Paper-doll: one base body, school outfit and weapon layer, element palette swap (Member model V/A). Animation set kept small: idle, walk, attack, cast, hurt, down (spirit), sit, sleep. Eight states × few frames.
3. **Monsters.** One base body per role (`swarm`, `melee`, `ranged`, `tank`, `boss`) per zone `theme`, palette by element (Zones V/A constraints).
4. **Town.** Each building kind drawn per level band (1–3, 4–7, 8+; Guild and buildings V/A), with scaffolding while building and the market's goods prop when stalls are stocked (Market V/A). The gate, inn, shrine, infirmary, Elders' hall and guild banner are fixed anchors.
5. **Event feedback.** As R8 and the owners' V/A sections: the world view draws them and does not redesign them. The homecoming settlement is the signature beat (Zones Player Fantasy).
6. **Group tokens.** A banner-shaped token with role icons, count and a shared HP bar; readable at the smallest zoom.
7. **Audio.** The view plays nothing; it publishes `view_context` (R13). Audio (40) owns every cue and their mix priority; cues for off-screen locations are suppressed or reduced by Audio using that context.

📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:realtime-world-view` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

This is an idle game: feel is **readability, rhythm and trust**, not input response in a fight.

- **Smooth at 10 Hz.** Movement is interpolated with `alpha` (F1, F2), so members glide at the display rate even though the world ticks ten times a second. No visible stepping at 30 or 60 FPS.
- **Camera responds in the frame of the touch.** Pan follows the finger 1:1 with light inertia on release; zoom snaps to the next integer scale within 150 ms; a location switch is a cut of at most 200 ms (a fade under reduced motion).
- **Orders acknowledge in 0 frames** (pending marker in the tap frame) and visibly react within 200 ms in normal play (Command layer, MSM Game Feel).
- **Weight on the important hits only.** Hit-stop of 1–2 frames on counter hits and kills; a short shake on a party member's death (Combat Game Feel); both off under reduced motion.
- **No dead air.** A party on a ground is never idle on screen for longer than `gap_s` plus travel (Zones); the town always has ambient motion.
- **Nothing demands attention.** No beat interrupts the camera; no alarm plays for an ordinary fight; the raid call is a banner, not a forced cut (R5).
- **Trust.** What is drawn is what was computed: no fake misses, no invented near-deaths, numbers that add up (F5).
- Feel is verified by playtest and retained screenshots, not automation.

## UI Requirements

The view owns the map surface and these on-map elements; screens and cards are laid out by Guild screens (39).

- **Location strip:** one tab per location (Town, each live ground, raid while it exists) with member count, fight icon and raid icon; the current location marked with text or an icon, not colour alone.
- **Over sprites:** HP bar (members and monsters), name label when selected, state icon (MSM V/A), needs icons, reason icons, pending-order marker, speech bubble for leave requests.
- **Member quick card** (opened by the view, laid out by 39): state label, HP vs flee line, bag fill, needs, current order, Follow toggle, order buttons (Hunt, Return, Stay home, Clear order), refusal reason in words.
- **Catching-up overlay:** a non-blocking bar with F7 progress and a localised label; input stays available.
- **Accessibility:** colour is never the only cue (R15); tap targets ≥ `view_min_tap_px`; reduced motion; all text through Localization with room for Vietnamese.
- **Screenshot evidence:** each element above is signed off with a retained screenshot in `production/qa/evidence/` in `vi`, `en` and `qps` (Localization R15).

> **📌 UX Flag — Realtime world view**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the world view HUD (location strip, over-sprite indicators, member quick card, catching-up overlay) **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not this GDD directly.

## Cross-References

| This GDD | References | Section | What is relied on |
|---|---|---|---|
| R1, R2, F1, R12 | Sim core and tick loop | R6, R10, R15, R17, F3, F6 | Facade, between-tick reads, `alpha`, catch-up flags, `sim_share` |
| R2, R8 | Event bus and history log | R12, Interactions | Tick batch delivery; presentation suppresses during catch-up |
| R11 | Command layer | R11, UI Requirements, Game Feel | Pending/applied/refused pattern |
| R14 | Localization | R1, R7.3, F1, F2, F4, R15 | Draw-time text, live switch, fit, `qps` sign-off |
| R6, R10 | Member model | V/A, UI | Sprite by school, name above selected sprite |
| R6, R8 | Member state machine | States table "Where", V/A, Game Feel | Location and pose per state, transition animations |
| R4, R6, R7, R9 | Zones, grounds, monsters and hunt trips | R6, R12, R13, V/A, Game Feel | Trip steps, presentation LOD, events, homecoming beat |
| R7, F3, F5 | Combat | R14, F8, AC-5, V/A 1–4, Game Feel | Timeline playback, deadline, numbers cap 20, ≤ 15 sprites |
| R4, R8, R9 | Golden Boss and guild raid | R2, R8, R17, V/A, UI | Raid arena, `want_timeline`, events 1401–1408 |
| R3 | Deterministic RNG | R1, Dependencies | Engine random allowed for cosmetics only |
| R8 | Guild and buildings; Guild market | V/A | Level bands, scaffolding, market prop |
| R8, F6 | Skills; XP curve; Schools; Recruitment; Retention; Utility AI | V/A | Pops, glows, gate arrivals, speech bubble, intent glyph |
| R10 | CA/PA and traits | R12 | UI reads `pa_view`, `traits_view`, `ca` only |
| R12 | Offline progress | Interactions | `Resolving` progress, summary record |

## Acceptance Criteria

Story type in brackets: **[Logic]** automated test (presentation-model tests run headless against a scripted facade), **[Integration]** automated with the real core, **[UI]/[Visual]** retained screenshot, **[Playtest]** feel.

**Contract**
- **AC-1 [Integration] (R1)** — **GIVEN** a fixed save and a scripted 10-minute session of player orders, **WHEN** it runs once with the view panning, zooming, switching locations and following members every few seconds and once headless with no view, **THEN** the command logs, the final saves and the event streams are byte-identical.
- **AC-2 [Logic] (R1)** — **GIVEN** the view running for 10 minutes with no player input, **WHEN** the Command layer's submission log is inspected, **THEN** it contains zero commands from the view.
- **AC-3 [Logic] (R2)** — **GIVEN** a scripted facade that delivers three tick batches before one frame, **WHEN** the frame runs, **THEN** the presentation model applies them in tick order and the drawn state equals that of applying them one per frame.
- **AC-4 [Logic] (R3, F2)** — **GIVEN** a save loaded with members in every MSM state and every trip step, **WHEN** the first frame is drawn, **THEN** every member is at the position F2 gives for its committed step with no history, and no member is outside its location's bounds.

**Choreography and playback**
- **AC-5 [Logic] (F2)** — **GIVEN** an Outbound step from tick 1,000 to 1,300, **WHEN** frames are drawn at ticks 1,000, 1,060, 1,150, 1,300 and 1,400 (alpha 0), **THEN** `p` is 0, 0.2, 0.5, 1.0 and 1.0, the member is in Town for `p < 0.5` and on the ground for `p ≥ 0.5`, and a zero-length step (`due = start`) gives `p = 1`.
- **AC-6 [Integration] (R7, F3)** — **GIVEN** a viewed ground with a party fighting, **WHEN** the playback finishes, **THEN** the sum of displayed damage per target equals the timeline's sum, each member's HP bar after the last record equals the committed HP at the deadline tick, and the last record's `play_at_s` is ≤ the deadline tick's time.
- **AC-7 [Logic] (F3)** — **GIVEN** a fight started at tick 5,000 with records at 0.0, 7.3 and 15.6 s, **WHEN** the view arrives at `view_time_s = 510.0`, **THEN** the first two records are applied silently with no numbers spawned, and the third plays at 515.6 s.
- **AC-8 [Logic] (Edge: query empty)** — **GIVEN** `fight_timeline` returns nothing, **WHEN** the fight runs to its deadline, **THEN** zero damage numbers are spawned and HP bars change exactly once, at the deadline tick, to the committed HP.
- **AC-9b [Integration] (R17, Zones R17)** — **GIVEN** a viewed ground with one card-tier trip replaying 5 encounters, **WHEN** the trip runs to its end, **THEN** `fight_timeline` is called 0 times, 0 damage or heal numbers are spawned, each member's HP bar changes exactly once per encounter at its deadline tick to committed HP, one kill puff and loot pop play per 1102, and the summarised glyph is shown on the tab and token; **AND** the run's state hash equals a headless run with the camera elsewhere.
- **AC-9c [UI] (R17)** — a retained screenshot of a card-tier ground mid-encounter showing members, the monster, the skirmish loop, the ≈ glyph and no numbers.
- **AC-9 [Integration] (R7)** — **GIVEN** two grounds with fights and the camera on Town, **WHEN** the profiler counts `fight_timeline` calls over 5 minutes, **THEN** the count is zero; after switching to one ground it equals the number of fights in progress there.
- **AC-10 [Logic] (R6)** — **GIVEN** 12 members `resting` and an inn with 8 seats, **WHEN** the Town is drawn, **THEN** all 12 are drawn at inn anchors (4 stacked with an offset) and none is hidden.
- **AC-11 [UI] (R8)** — **GIVEN** a party returning with a full bag, **WHEN** Selling runs, **THEN** a retained screenshot shows sacks emptying, a rising gold counter and a level-up pop, and the beat lasts the whole `sell_s` (timed in the test: ≥ `sell_s − 0.1 s`).

**LOD and budgets**
- **AC-12 [Logic] (F4)** — **GIVEN** 20 members at the raid location and `view_full_sprites_max = 15`, **WHEN** F4 runs, **THEN** exactly 15 are full and 5 are tokens; the selected member is full even when farthest; with `h = 32`, a full member 30 px beyond the boundary stays full and one 40 px beyond is replaced.
- **AC-13 [Logic] (F5)** — **GIVEN** 20 active numbers, **WHEN** a new hit arrives, **THEN** the oldest is recycled and the active count stays 20; **GIVEN** three hits of 40, 42, 39 on one target within 150 ms, **THEN** one number reading 121 is shown; **GIVEN** `dmg_merge_window_ms = 0`, **THEN** three numbers are shown.
- **AC-14 [Logic] (F6)** — **GIVEN** `pop_min_interval_s = 1.0` and two level-ups for one member 0.3 s apart, **WHEN** they arrive, **THEN** one pop "Lv N → N+2" is shown, and no level-up is lost.
- **AC-15 [Logic] (F7)** — **GIVEN** catch-up entered with `debt_us` 40 s, **WHEN** it falls to 10 s, **THEN** progress is 0.75; **WHEN** it rises to 50 s, **THEN** the peak becomes 50 s and progress stays in [0, 1].
- **AC-16 [Integration] (R12)** — **GIVEN** a 50 s catch-up containing 200 events including 6 level-ups, **WHEN** it runs, **THEN** zero per-event beats play and zero cue contexts are marked unsuppressed; on exit every member is at its F2 position and one merged "6 level-ups" toast is shown; orders tapped during catch-up show "waiting on the guild" and resolve after the drain.
- **AC-17 [Integration, device] (F8, R9)** — **GIVEN** the min-spec Android phone of the P1 spike and a raid with 40 participants, **WHEN** the raid plays for 60 s on screen, **THEN** the frame rate stays ≥ 30 FPS at p95 and the profiled view cost is ≤ `0.2 × frame_budget_ms` at p95. *Blocked until the P1 spike device exists.*
- **AC-18 [Logic] (F8 scaling)** — **GIVEN** rosters of 10 and 40 members with the camera on an empty ground, **WHEN** 600 frames are profiled with no state changes, **THEN** the view's per-frame cost for the 40 roster is within 10 % of the 10 roster (cost does not scale with off-screen members).

**Interaction, text and accessibility**
- **AC-19 [Integration] (R11)** — **GIVEN** a hunting member selected, **WHEN** the player taps Return, **THEN** a pending marker shows in the same frame, the member does not turn for home before `command_applied`, and on `command_refused` the reason text is shown and the member's path is unchanged.
- **AC-20 [Logic] (R5)** — **GIVEN** a Golden Boss `gb_started` (1402) while the camera is on a ground, **WHEN** the event is applied, **THEN** the camera location is unchanged and the raid tab appears in the strip.
- **AC-21 [Logic] (R10, Edge)** — **GIVEN** a selected member with Follow on, **WHEN** that member reaches `away`, **THEN** selection clears, the card closes and Follow stops in the same frame as the event.
- **AC-22 [UI] (R14)** — **GIVEN** the Town and a ground with a fight on screen, **WHEN** screenshots are taken in `vi`, `en` and `qps`, **THEN** no label overflows its field, truncated names show the full name on the card, and the locale switch is complete in the next frame.
- **AC-23 [UI] (R15)** — **GIVEN** a fight with a counter hit and a countered hit, and members in every state, **WHEN** a greyscale screenshot is taken, **THEN** each counter/countered number, each state and each reason is still distinguishable by shape or text.
- **AC-24 [Playtest] (Game Feel)** — **GIVEN** five playtesters opening the game for two minutes at random times during a normal session, **WHEN** asked afterwards, **THEN** at least four report seeing a party come home or a fight, and none reports the camera moving by itself or a fight looking different from the trip report.

*QA lens applied:* every rule R1–R15 and R17 (AC-9b, AC-9c) and formula F1–F8 has at least one criterion; boundary values (zero-length step, empty query, cap reached, merge window 0, debt rising) are covered; AC-1, AC-6, AC-9 and AC-19 test cross-system interactions. R16 (background) is covered by AC-4's load-and-draw path. AC-17 is device-gated and must not be closed from an emulator.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **RESOLVED (consistency-check 2026-11-16): Zones R12 now provides `fight_timeline(party_id, trip_ordinal, encounter_ordinal)`** as specified here. Original question: provide it as a side-effect-free between-tick query that rebuilds the pending encounter from saved trip state (roster HP before the fight, monster row, key F9) and calls Combat `resolve(..., want_timeline = true)` on copies with a fresh generator from the same key. Zones today saves the pending `FightResult` but defines no timeline transport; Combat says the timeline is "passed on by the caller as events", and Combat V/A says "off-screen fights record no timeline". This GDD assumes the query instead of events, so timelines never enter the event stream, the history log or saves, and the camera cannot change any saved byte. | Zones (11) + Combat (10) | Before the world view epic |
| OQ-2 | **RESOLVED (consistency-check 2026-11-16): Golden Boss R8 now passes `want_timeline = false` in the simulation and offers `raid_fight_timeline(raid_ordinal)`.** Original question: Golden Boss (14) — `want_timeline` "true when the world view is showing the raid" (R8 of 14) makes a saved/pending field depend on the camera. Proposed: the raid passes `want_timeline = false` in the simulation, and the view uses the same `fight_timeline` query (OQ-1) for the raid. If 14 keeps the flag, it must state that the timeline is excluded from saves, events and parity comparisons. | Golden Boss (14) | Consistency pass |
| OQ-3 | **Where presentation knobs live** (Tuning Knobs). They must not be in the simulation's content hash. Options: rows in `config.csv` excluded from the hash, or a separate presentation file. A new data file is a schema change, so it is not decided here. | Data layer (3) | Before implementation |
| OQ-4 | **PROVISIONAL: Guild screens (39)** — owns the layout of the member quick card, building card, failure screen and "while you were away" report; offers `focus_member(id)` and `focus_location(loc)` calls to the view. | Guild screens (39) | When 39 is designed |
| OQ-5 | **PROVISIONAL: Settings (45)** — provides a reduced-motion flag (shake, hit-stop, cut→fade) and possibly a damage-number toggle. Settings is Vertical Slice, so in MVP reduced motion is a debug option only. | Settings (45) | Vertical Slice |
| OQ-6 | **RESOLVED (consistency-check 2026-11-16):** Audio R2/R6 consume `view_context` (R13, now with `played_records`) and the event stream, and own off-screen suppression. | Audio (40) | Closed |
| OQ-7 | `view_full_sprites_max` (15) and `engine_share` (0.3) are guesses until the P1 spike measures raid sprite performance on the real Android phone (§12.1, §6.13, systems index risk table). | P1 spike / technical-director | P1 spike |
| OQ-8 | Integer-scale pixel rendering in Godot 4.7: the stretch defaults for new projects changed in 4.7 (`canvas_items`, `expand`; `docs/engine-reference/godot/modules/ui.md`). The integer scale-mode setting for pixel-perfect 2D is **NOT SOURCEABLE** from `docs/engine-reference/godot/` and must be verified against the installed editor (installed version NOT DETERMINED). → becomes an ADR. | technical-director | Before implementation |
| OQ-9 | Should the view show a member walking to the shop during the town visit (MSM OQ-9: errands take no sim time)? This GDD draws errands as cosmetic wander during the rest only, which never contradicts timers. | Member state machine (41) | Consistency pass |
| OQ-10 | Zone travel is drawn as leaving one location and entering another (R4, R6). A continuous world map with roads was considered and rejected for the art and performance budget of a solo developer; revisit if playtests show players lose track of travelling parties. | game-designer | After first playtest |
