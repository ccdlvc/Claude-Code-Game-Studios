# Audio

> **Status**: Designed (pending review)
> **Author**: user + agents (`/design-system`, autonomous batch run)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: No `game-pillars.md` exists; serves GDD §1 (the guild loop, the hourly Golden Boss as shared climax), §3.2 (Presentation layer: "map, sprite, UI, VFX, audio") and §12.4 item 6 (audio licensing)
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief exist to check against (`design/gdd/game-concept.md`, `game-pillars.md` and `design/game-brief.md` are all absent). Re-run once pillars exist.

## Summary

Audio turns what the guild does into sound: a drum when the Golden Boss is called, a chime when a party comes home with full bags, a low note when a member falls, and three music loops for town, field and raid. It listens to the simulation's event stream and to the world view's animation, picks one sound per moment by a fixed priority, and stays quiet while the game catches up after an absence. It exists so a player who is not looking at the screen still knows when something important happened to their guild.

> **Quick reference** — Layer: `Presentation` · Priority: `Alpha` · Key deps: `Sim core and tick loop, Event bus and history log, Realtime world view, Settings`

## Overview

Audio is the Presentation-layer system that plays every sound effect and music track in JX1 Tycoon. It has three inputs and no outputs into the game. The first input is the Sim core's read-only presentation facade (Sim core R15): each tick's P6 event batch, plus `catching_up` and `handoff_pending`. A **cue table** maps event type IDs, which the emitting systems already own in their registry blocks, to named cues. The second input is the Realtime world view's read-only `view_context` (World view R13), read each frame: which location is on screen, whether presentation is suppressed, and the fight-timeline records the view drew this frame. Combat hits come from those records, because the view plays a fight back over time while Combat resolves it in one call (World view R7). The third input is the **UI channel**: Guild screens (39) and Settings (45) ask for a UI cue by name (`play_cue`). Every request then goes through one mixer. The mixer sorts cues into four priority tiers, applies per-cue rate limits, steals voices from lower tiers when the pool is full, and ducks the music under alerts and stings. Volumes come from Settings (45) as device preferences.

**Player impact.** This is an idle game that the player often leaves running while looking at another app or another screen. Audio is how the guild reaches them: the Golden Boss drum means "the raid is starting", the homecoming chime means "loot came in", a falling two-note cue means "someone wants to leave". If audio were missing, the game would still work, because every cue has a visual counterpart owned by its emitting system. But the guild would feel silent, and the player would miss the hourly climax unless they were watching.

**What the system does not own.** Which moments deserve a sound, and their relative weight, were requested by the emitting GDDs (see Cross-References). Audio owns how each sound is played, mixed and limited. The volume controls and their storage are Settings' (45). The visual feedback for each event belongs to the Realtime world view (38) and the emitting GDDs. Audio never reads or writes simulation state, never emits events or commands, and never uses the simulation's RNG (Deterministic RNG, Dependencies).

## Player Fantasy

**Direct: "I can hear my guild."** The player is in the Chợ Bang screen sorting a shipment. Behind it, a drum rolls twice. They know without looking that the Golden Boss has been called and their members are turning home. A few minutes later (1401 → 1402 is 120–240 s, Golden Boss R2/R5) they hear a roar and the music swells into the raid theme, then a bright victory sting. They switch back to the town view in time to see the boss's loot landing in guild storage.

No pillars exist yet, so the fantasy is anchored to GDD §1 ("the guild loop … punctuated by an hourly Golden Boss that the whole guild fights together") and §6.5 (the boss "every 1 hour, the whole guild fights together" [CHỐT]).

What this asks of the design:
- **Each important moment gets its own, recognisable cue**, and the most important ones (boss call, member down, arrears) are never masked by routine ones (R4, R5).
- **Routine moments stay quiet.** An idle guild of 40 members produces hundreds of small events an hour; if each one chimed, the player would mute the game and lose the important cues too (R6).
- **Sound never carries information alone** (R11), so a player with sound off loses atmosphere but not information.

Two framings were considered and not chosen: "a living martial-arts town" (ambience first, which suits the town view but not the off-screen player) and "wuxia drama" (big music for every fight, which fails the quiet-routine rule).

## Detailed Design

*Specialist lenses applied (Section 6 routing, row "Audio systems"): **game-designer** — the decisions are the player's, not this system's; Audio's job is to make the guild's moments legible without looking, and the main risk is fatigue in an idle game, so suppression rules matter more than cue variety. **audio-director** — four priority tiers, with Golden Boss and member-down at the top, match what eleven sibling GDDs already requested; one field theme for Wave 1 (not per-zone) suits a solo developer and the small-install goal (GDD §3.1); every AI-generated sound follows §12.4's license rules. **sound-designer** — every cue needs a cooldown and a collapse rule, or a 40-member homecoming wave becomes noise; hit sounds must follow the world view's playback, not the event tick. No conflict between the lenses needed a decision.*

### Core Rules

**R1: Three input channels, one mixer.**
- **Event channel.** Once per render frame, Audio reads the event records delivered since the last frame from the Sim core facade (R15) and looks up each `type_id` in the cue table (R3). An event type with no row plays nothing.
- **View channel.** Once per frame, Audio reads the world view's `view_context` (World view R13). From it Audio takes: the viewed location (Town, a Ground, or the Raid arena), which drives music (R8); `suppressed`, treated like catch-up (R6 step 1); and `played_records`, the Combat timeline records (World view R7, Combat record format: time, actor, kind, target, amount, died) whose playback time fell in this frame. Each record kind maps to a cue: attack → the hit cue of the actor's weapon family (or the monster attack cue), counter hit → `hit_counter`, heal → `heal`, died → `combat_death`, enrage → `gb_enrage`. Only what the view draws is heard, so hits are heard only for the location on screen (Zones V/A). `played_records` is part of World view R13 (OQ-2 resolved).
- **UI channel.** `play_cue(cue_id, context)` is called by Guild screens (39), Settings (45) and the offline report. `context` carries an optional `member_id`, which is the UI channel's collapse key (R6). The world view never calls it (World view R1: "the view plays no sound itself"). The UI cue names are Guild screens' (Visual/Audio item 4): `ui_tap`, `ui_confirm`, `ui_refused`, `ui_toast`, `ui_modal_open`, `ui_badge_new`; plus Settings' `ui_preview` and `sfx_preview` (R10) and the offline report's `report_open` and `report_row`. There is no close sound.
- **One refusal, one cue.** A refused order is heard only as `ui_refused`, requested by Guild screens when it shows the refusal (it sees both the Command layer outcome 502 and host-side refusals such as `host_queue_full`). Event 502 `command_refused` has **no** event-channel row, so one refusal can never sound twice.
- All three channels feed the same mixer (R4–R7). Audio exposes nothing else to the game.

**R2: Audio is read-only and cosmetic.**
- It never calls the loop, emits events, submits commands or writes state. It reads only the facade (Sim core R15), never the core.
- Cosmetic variation (pitch jitter, picking one of several variants) uses the engine's random functions, never the simulation's PCG32 (Deterministic RNG R1).
- Nothing Audio does is saved. Its only persistent inputs are the volume preferences that Settings stores (R10).
- A headless run (balance simulator, tests, server replay; Sim core R16) has no Audio at all, and nothing in the simulation may depend on it.

**R3: The cue table.** A cue is a named sound. Its row holds:
- `cue_id`; `tier` (R4); `priority` (an integer, R4; fixed per row); `bus` (`sfx` or `ui`); `gain_db`; `cooldown_ms` and `frame_cap` (R6); `collapse_group` and, for event rows, `collapse_slot` (R6, optional; required when `collapse_group` is set); `variants` (1–4 sound files, one picked at random); `pitch_jitter` (0 – 0.1); and for event cues, the `type_id` and an optional payload filter (one slot, one value, for example "reason = defeated").
- The table is presentation data. It is a resource file under `assets/audio/`, not a Data layer content table. It is not part of the content hash, `content_validator`, or any leaderboard input (OQ-1).
- A cue may name a `type_id` that is not registered in this build (for example a Wave 2 type). That row is inactive and logged once at boot, never an error, because presentation must not block a content wave.
- The Wave 1 cue list is under Visual/Audio Requirements.

**R4: Four priority tiers.** Each cue has one tier. The tier decides voice stealing (F2), music ducking (F4) and which cue wins a collapse group (R6).

| Tier | Priority | Meaning | Examples |
|---|---|---|---|
| T1 Alert | 100 | The player should act or look now | Golden Boss call (1401) and start (1402), boss enrage, member downed (1103), arrears started (2705) |
| T2 Milestone | 80 – 89 (each row's own value, cue list) | A rare, memorable moment | Ascension (2302, 89, the highest non-warning cue), rebirth (2301, 87), horn (1407, 86), raid victory/defeat stings (85), guild level-up (84), hire (83), epic drop (82), signature skill and first zone entry (81), enhance milestone, school beat and level cap (80) |
| T3 Feedback | 60 | A routine but meaningful result | Homecoming chime (2601), level-up (2201), craft done, enhance success/fail, injury, revival |
| T4 Ambient | 40 | Texture; safe to drop | Combat hits, coin ticks, party formed, trip departure |

The `ui` bus has its own small pool (R5) and never steals from or is stolen by `sfx`. The refusal cue `ui_refused` is on the `ui` bus at `gain_db = -6`, so it stays quieter than any combat or Golden Boss cue (Command layer, Visual/Audio). It is still always heard over gameplay, because no `sfx` cue can take its voice and it has a timbre no other cue uses; that is how Guild screens' "audible over gameplay" is met without making it louder. The four-tier order is the order sibling GDDs asked for: boss cues above member death, death above loot, epic chime above ambient but below boss warnings (Golden Boss, Zones, Items, Crafting, CA/PA, Rebirth).

**R5: Fixed voice pools.** Audio pre-creates its players once at boot (Godot audio reference, "Object Pooling for SFX"): `sfx_voices` (12) on the `sfx` bus, `ui_voices` (3) on the `ui` bus, and 2 music players for crossfading. It never creates a player at runtime. When a pool is full, a new cue may take a voice only by F2. Otherwise it is dropped. A dropped cue is never queued, except T2 cues (R7).

**R6: Rate limits and collapse.** In order, for each requested cue:
1. **Catch-up gate.** If the facade reports `catching_up` or `handoff_pending`, or `view_context.suppressed` is true, every event-channel and view-channel cue is dropped (Sim core R17, Event bus R12, World view R12). UI-channel cues still play. The UI channel only carries sounds of the player's own taps and of screens that exist for catch-up (the summary toast, the offline report). Callers do not request event-derived UI cues while catching up: Guild screens holds per-event toasts and badges (its R12) and requests one `ui_toast` for the summary. So taps, confirms and refusals still sound while catching up, and nothing else does.
2. **Collapse.** All cues requested in one frame **on the same channel** that share a `collapse_group` and the same **context key** are reduced to the one with the highest `priority`. Ties go to the first requested. The context key is:
   - event channel: the payload value in the row's `collapse_slot` (1–4 = `a`–`d`). Every row of one group names the slot that holds the same entity. Wave 1 groups: `join` = 1502 slot 2 (`member_id`) and 801 slot 1 (`member_id`); `enhance` = 2401, 2402 and 2403 slot 1 (`member_id`);
   - UI channel: `context.member_id` (absent = one shared key);
   - view channel: no groups in Wave 1.
   There is no collapse across channels. This is how a hire plays the hire sting and not also the welcome chime (1502 and 801 for the same member), and an enhance milestone plays instead of the plain success cue (2403 over 2401). A row with `collapse_group` but no `collapse_slot` fails the build check (AC-16).
   - **Member deaths are heard once.** A member's death is announced by the 1103 event cue (T1). A view-channel `died` record whose target is a **member** plays nothing; `combat_death` plays only for monster deaths. So the two channels never double one death.
3. **Frame cap.** At most `frame_cap` instances of one cue start per frame (default 1). So a tick in which ten members level up plays one level-up cue, not ten.
4. **Cooldown.** F3. A cue inside its cooldown is dropped.
5. **Voice.** F2.

**R7: T2 milestones are spaced, not dropped.** T2 cues that pass R6 steps 1–4 are handled in **descending `priority`** within a frame (ties in request order).
1. A T2 cue starts at once (step 5, F2) if no cue is waiting and no T1 or T2 cue started in the last `milestone_gap_ms` (600 ms). Otherwise it joins the wait queue.
2. The queue holds at most `milestone_queue_cap` (3) cues and drains in **descending priority** (ties: the earlier arrival first). The head starts `milestone_gap_ms` after the previous T1/T2 start; the next one `milestone_gap_ms` after that, and so on. So a guild level-up and a rebirth in the same tick are both heard.
3. A T2 cue arriving while the queue is full replaces the lowest-priority waiting cue (the latest arrival among equals) if its priority is strictly higher; otherwise it is dropped.
4. When a waiting cue's turn comes, only step 1 (catch-up gate) and step 5 (F2) are re-run. If either refuses it (catch-up began, or every voice is held by an equal or higher priority), it is **dropped, not re-queued**, and the next waiting cue keeps its own start time.
T1 cues never wait: they play at once, by F2.

**R8: Music.** One loop plays at a time, chosen by music state:

| State | Track | Entered when | Left when |
|---|---|---|---|
| `town` | Town theme | Boot; any other state ends | — |
| `field` | Field theme | `view_context` location is a Ground | Location is the Town |
| `raid` | Raid theme | 1402 `gb_started` | 1403 `gb_won`, 1404 `gb_lost`, or `raid_music_timeout_s` (360 s) with neither |
| `report` | Current track at `report_music_db` | The offline report opens (UI channel `report_open`) | The report closes |

- `raid` outranks `field` and `town`: while it is active, focus changes are remembered but do not switch the track.
- Changing tracks crossfades over `music_crossfade_ms` (1,500 ms) on the two music players.
- 1403 and 1404 play the victory or defeat sting (T2), and the music returns to the remembered `field`/`town` state after the sting ends.
- **Catch-up.** Music keeps playing while catching up and does not change track. Audio still reads 1402, 1403 and 1404 during catch-up, but only to keep its own `raid_active` flag, so the right track is chosen when catch-up ends. No sting plays for a raid that resolved during catch-up.
- There is no `field` theme per zone or per element in Wave 1 (OQ-3).

**R9: App lifecycle and ads.**
- When the app loses focus or goes to the background, Audio pauses every player. When it returns, it resumes them, fading the Master bus in over `resume_fade_ms` (300 ms). Event cues requested while paused are not played on return. The simulation may still have run (Offline progress), and its report has its own cues.
- While a rewarded video plays, game music and SFX are **muted, not paused**: Audio mutes on Ads R12 `rewarded_state_changed` entering `Showing` and restores on leaving `Showing` (Ads R12, Visual/Audio). The video's own audio is the ad SDK's.

**R10: Buses and volumes.**
- Bus layout: `Master` → `Music`, `SFX`, `UI`.
- Settings (45) owns the four sliders (`vol_master`, `vol_music`, `vol_sfx`, `vol_ui`, 0 – 100 in steps of `volume_slider_step`), the `mute_all` toggle, their defaults (80, 70, 80, 80) and the volume curve (Settings R3, R4, R12, F1). It stores them as device preferences, never in the simulation save. Audio owns only the bus layout and applying the gains.
- At boot Audio reads the five values through Settings and applies F1 to each bus (Settings R5 step 4). On every slider or toggle change Settings calls `apply_volumes(vol_master, vol_music, vol_sfx, vol_ui, mute_all)` on the same frame (Settings R8), and Audio re-applies F1.
- Audio supplies the preview cue Settings plays on releasing the Sound effects or Interface slider (Settings R12.3): `ui_preview` on the `ui` bus and `sfx_preview` (the homecoming chime) on the `sfx` bus. No preview plays while `mute_all` is on.

**R11: Sound never carries information alone.** Every cue in the table has a visual counterpart owned by its emitting system or the world view. A player with sound muted loses no information. Audio adds no cue whose event has no visual (accessibility floor, lens ux-designer). There is no voice-over (Localization, Visual/Audio), so nothing in audio is localised.

**R12: Licensing.** Every sound file ships with a recorded source and license, under the same rules as art (GDD §12.4 item 6, §12.4.1): a tool that allows commercial use, a dated copy of its terms, and a log entry. AI-generated audio is declared wherever the store requires it (Steam). A sound with no log entry does not ship (AC-19).

### States and Transitions

Audio has a lifecycle state and the music state (R8).

| Lifecycle state | Plays cues? | Plays music? |
|---|---|---|
| `Booting` | No | No |
| `Active` | Yes (subject to R6) | Yes |
| `CatchingUp` (facade `catching_up` or `handoff_pending`, or view `suppressed`) | UI channel only | Yes, no track change |
| `Paused` (app in background) | No | No (paused) |
| `AdMuted` (rewarded video showing) | No | Muted, still running |

| From | To | Trigger |
|---|---|---|
| `Booting` | `Active` | Pools created, cue table loaded, bus volumes applied from Settings |
| `Active` | `CatchingUp` | Facade reports `catching_up` or `handoff_pending`, or `view_context.suppressed` is true |
| `CatchingUp` | `Active` | All three false; music state re-derived from `raid_active` and focus |
| `Active` / `CatchingUp` | `Paused` | App focus lost |
| `Paused` | previous state | Focus regained; Master fades in (R9) |
| `Active` / `CatchingUp` | `AdMuted` | Ads R12 `rewarded_state_changed` enters `Showing` |
| `AdMuted` | previous state | `rewarded_state_changed` leaves `Showing`; volumes restored from Settings F1 |

The music state table is in R8. `raid_active` is set by 1402 and cleared by 1403, 1404 or the timeout, in every lifecycle state except `Booting`.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Sim core (1) | core → audio | The read-only facade: P6 events, `catching_up`, `handoff_pending` (R15) | None | Sim core |
| Event bus (42) | bus → audio (via the facade) | Event records `tick, type_id, a, b, c, d` (Event bus R2); type IDs from the registry blocks | None. Audio is not one of the 16 bus subscribers (Event bus R4), so it does not count against `max_event_subscribers` | Each emitter owns its type block; Audio owns the cue table |
| Realtime world view (38) | view → audio | `view_context` (R13): location, camera, full sprites, `suppressed`, reduced motion; plus `played_records` | None | World view owns the context; Audio owns every cue and its mix (World view V/A item 7) |
| Guild screens (39) | screens → audio | `play_cue` with the six UI cue names (R1), incl. the single refusal cue `ui_refused`; the offline report | None | Guild screens owns when; Audio owns the cue and mix |
| Settings (45) | both | `vol_*` and `mute_all` at boot and on change (`apply_volumes`) | The preview cues | Settings owns the controls, storage, defaults and F1; Audio owns the bus layout and F1 |
| Ads (33) | ads → audio | R12 `rewarded_state_changed(state)`; mute while `Showing` | None | Ads |
| Offline progress (31) | none directly | Its report sounds arrive through the UI channel | None | Offline progress owns when |
| Deterministic RNG (2) | none | None. Audio must not use it | None | — |
| Localization (4) | none | No voice-over | None | — |

## Formulas

### F1 — `channel_gain_db` (slider to bus gain) — owned by Settings

Audio does not define its own volume curve. It applies Settings' F1 `channel_gain_db(v, mute)` (`design/gdd/settings.md`, Formulas; registry `channel_gain_db`) to the Master bus with `v = vol_master`, `mute = mute_all`, and to the Music, SFX and UI buses with their own `vol_*` and `mute = false`. The taper `volume_taper_exp` (k = 2.0) and `volume_floor_db` (−60) are Settings' knobs. Audio's only addition is how a result is applied:

`bus_volume_db[bus] = channel_gain_db(v_bus, mute_bus)`; a silent result (−∞) sets the engine's bus mute instead of a dB value

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| v_bus | int | 0 – 100 | Settings store (`vol_master`, `vol_music`, `vol_sfx`, `vol_ui`) | Slider value for one bus |
| mute_bus | bool | — | Settings store (`mute_all`, Master only) | Silences Master |
| bus_volume_db | float | −60.0 – 0.0, or muted | calculated (Settings F1) | Gain set on that bus |

**Output Range:** 0 dB at 100; muted at 0, below the floor, or with `mute_all` on (Master). Never above 0 dB.
**Example (from Settings F1):** `vol_master = 80`, `vol_sfx = 50` → Master −3.88 dB, SFX bus −12.04 dB, heard SFX ≈ −15.9 dB.

### F2 — `voice_steal` (who gets a voice when the pool is full)

The `voice_steal` formula is defined as:

`victim = argmin over playing voices of (priority, start_ms)`; the new cue takes `victim` iff `priority_new > priority_victim`, else the new cue is dropped (T2: queued per R7)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| priority_new | int | 40 – 100 | cue table (tier) | Priority of the cue asking for a voice |
| priority_victim | int | 40 – 100 | calculated | Lowest priority among playing voices on that bus |
| start_ms | int | ≥ 0 | calculated | When the voice started; older loses a tie |
| sfx_voices | int | 12 | data file (knob) | Pool size for `sfx` |
| ui_voices | int | 3 | data file (knob) | Pool size for `ui` |

**Output Range:** a T1 cue always gets a voice unless all 12 voices are T1, which cannot happen in normal play: the T1 events are at most a few per minute. T4 cues never steal (nothing is lower).
**Priority** is the row's own `priority` (R3): T1 = 100, T3 = 60, T4 = 40, and each T2 row its listed 80–89 value.
**Example:** 12 voices are busy: 9 T4 hits and 3 T3 chimes. A 1103 member-downed cue (T1) steals the oldest T4 hit. A new T4 coin cue finds no lower voice and is dropped.
**Why strict "greater than":** equal-tier stealing would make a busy fight cut its own hits off every frame (audible chatter). Dropping the newcomer costs nothing at T4.

### F3 — `cooldown_pass` (per-cue rate limit)

The `cooldown_pass` formula is defined as:

`cooldown_pass = (now_ms − last_play_ms[cue]) ≥ cooldown_ms[cue]`; a cue never played passes

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| now_ms | int | ≥ 0 | engine monotonic clock | Real time, not game time |
| last_play_ms | int | ≥ 0 | calculated | When this cue last started (not when it was last requested) |
| cooldown_ms | int | 0 – 5,000 | cue table | Minimum gap between two starts of this cue |

**Output Range:** boolean. `cooldown_ms = 0` means only `frame_cap` limits the cue.
**Example:** the light coin cue for market sales has `cooldown_ms = 2,000` (Guild market, Visual/Audio: "rate-limited to one per 2 s"). A buying spree of 30 sales in 5 s plays 3 coin cues.
**Real time, not ticks:** cues are heard in real time, and the clock is never read by the simulation, so this does not break Sim core R1.

### F4 — `music_duck_db` (music under alerts and stings)

The `music_duck_db` formula is defined as:

`music_duck_db = duck_db` while any T1 cue or music sting is playing; it moves toward the target linearly in dB over `duck_attack_ms` going down and `duck_release_ms` going up

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| duck_db | float | −20.0 – 0.0 | data file (knob, default −8.0) | How far music drops under an alert |
| duck_attack_ms | int | 20 – 500 | data file (default 80) | Time to reach `duck_db` |
| duck_release_ms | int | 100 – 2,000 | data file (default 600) | Time to return to 0 dB after the last alert ends |

**Output Range:** −20 dB to 0 dB, added to the Music bus only. Overlapping alerts do not stack: the target is `duck_db` while one or more are playing.
**Example:** the 1401 drum call starts. In 80 ms the town theme is 8 dB lower. The drum lasts 1.6 s; 600 ms after it ends the theme is back at full level.

## Edge Cases

- **If an event batch holds more cue-mapped events than voices** (a homecoming wave: twenty 2601 events in one tick): R6 frame cap reduces each cue to one start per frame, so at most one homecoming chime plays. The visual for each settlement still shows (Items, Visual/Audio).
- **If a T1 and a T2 cue arrive in the same frame**: the T1 plays at once (F2); the T2 waits in the milestone queue (R7) and starts `milestone_gap_ms` later, so the alert is heard first and clearly.
- **If two T1 cues arrive in the same frame** (a member downed on the tick the boss is announced): both play; each gets a voice by F2 because nothing else is T1. Music ducks once (F4).
- **If a raid result (1403/1404) arrives with no 1402 seen** (the game was loaded mid-raid, or 1402 fell inside catch-up before Audio booted): the sting plays if not catching up, `raid_active` stays false, and the music stays in its current state. The track was never `raid`, so nothing switches back.
- **If no raid result arrives within `raid_music_timeout_s`** (a raid outlasting its 300 s limit cannot happen by Golden Boss rules, but a lost event or a failed core can stop the stream): the music leaves `raid` after 360 s. Audio never stays in raid music forever.
- **If the Sim core enters `Failed`**: no more events arrive. Music keeps its state; the failure screen (Sim core, UI Requirements) uses the `ui` bus only. Audio does not try to read state from a failed core.
- **If catch-up ends in the middle of a raid**: `raid_active` is true from the 1402 seen during catch-up, so the music switches to `raid` with a normal crossfade on the first `Active` frame. The 1402 roar is not replayed.
- **If an event cue is requested while `Paused`**: it is dropped, not saved for later. On return, the offline report or the visible state tells the player what happened.
- **If the same event type has two rows** (a plain and a payload-filtered variant, for example 1104 with reason = defeated): the filtered row is tried first; if its filter does not match, the unfiltered row is used; if none matches, nothing plays.
- **If a cue file is missing or fails to load**: the row is disabled at boot and logged once with its `cue_id`; the game continues silently for that cue. In a debug build, the missing file is an error the developer sees on boot.
- **If the cue table names an unregistered `type_id`**: R3, inactive row, one log line. A typo is caught by AC-16 at build time, not at runtime.
- **If a slider changes while a cue is playing**: the bus gain changes at once (F1); voices are not restarted.
- **If the app goes to the background while a rewarded video plays** (the ad SDK opens its own activity): `Paused` applies as well; on return Audio stays `AdMuted` until the video-closed signal, then restores volumes.
- **If music crossfade is requested while a crossfade is running** (the player taps between town and field quickly): the new target replaces the old; the outgoing player fades from its current level, so there is never a third player or a jump in volume.
- **If the device is in silent mode or its media volume is 0**: Audio does nothing special; the OS mixer handles it. How Android/iOS audio focus interacts with Godot's audio output is not covered by `docs/engine-reference/godot/modules/audio.md` (OQ-6).
- **Degenerate play:** none; Audio grants nothing. A player who mutes everything loses no information (R11).

## Dependencies

### Upstream (this system depends on)

| System | Type | Interface | Why |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | The R15 facade: P6 events, `catching_up`, `handoff_pending` | The only source of game events Audio may read |
| Event bus and history log (42) | Hard | Event record layout (R2) and the registered type IDs of each emitter's block | The cue table is keyed on these IDs |
| Realtime world view (38) | Hard | `view_context` (World view R13) incl. `played_records` | Combat sounds must follow animation playback, not event ticks |
| Settings (45) | Soft | `vol_*`, `mute_all`, F1 (`channel_gain_db`) | Without it Audio plays at full scale with no mute |
| Guild screens (39) | Soft | `play_cue` with its six UI cue names (Visual/Audio item 4) | Without it there are no UI sounds. Designed (`guild-screens.md`) |
| Ads (33) | Soft | R12 `rewarded_state_changed` (`Showing`) | Without it game audio plays over the video. Designed (`ads.md`) |

### Downstream (systems that depend on this one)

| System | Type | Interface |
|---|---|---|
| Settings (45) | Hard (for its audio controls) | `apply_volumes`, the preview cues `ui_preview` and `sfx_preview` |
| Guild screens (39), Settings (45), Offline progress report (31) | Soft | `play_cue(cue_id, context)` on the UI channel |

**Emitting systems** whose events Audio maps (no dependency in either direction; they only own type IDs): Member model (800), CA/PA and traits (900), Hunt (1100), Party (1300), Golden Boss (1400), Recruitment (1500), Retention (1600), Endless Tower (1900, Full Vision), Schools (2000), Skills (2100), XP (2200), Rebirth (2300), Enhancement (2400), Items (2600), Gold economy (2700), Crafting (2800), Market (2900), Buildings (3000), Member state machine (4100), Command layer (500).

**Bidirectional check.** The systems index row listed "Sim core, Realtime world view, Event bus"; Settings and Ads (both soft) were added to it. Ads (33) R12 and the Realtime world view (38) list Audio and conform. Settings (45) and Guild screens (39) still mark Audio "PROVISIONAL / no GDD" (stale on their side; cross-cluster request 2026-11-16, with Guild screens V/A item 4 to match R6 step 1 and R1's single refusal path). Sim core and Event bus list Audio as a facade consumer.

## Tuning Knobs

All knobs live in the Audio resource files under `assets/audio/` (R3), not in the simulation data.

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `sfx_voices` | 12 | 8 – 24 | CPU and mix mud on low-end phones | T3 cues dropped in busy fights | `frame_cap`, cooldowns |
| `ui_voices` | 3 | 2 – 4 | Overlapping taps sound messy | Fast taps cut each other off | — |
| `milestone_queue_cap` | 3 | 1 – 5 | A late burst of stings long after the moment | Simultaneous milestones lost | `milestone_gap_ms` |
| `milestone_gap_ms` | 600 | 300 – 1,500 | Queue drains too slowly, sting arrives after the visual | Stings overlap and blur | `milestone_queue_cap` (cap × gap = max delay, 1.8 s) |
| `cooldown_ms` (per cue) | per table | 0 – 5,000 | The cue goes missing on real repeats | Chatter | `frame_cap` |
| `frame_cap` (per cue) | 1 | 1 – 3 | Stacked identical cues sound loud and phasey | — | — |
| `duck_db` | −8.0 | −14 – −4 | Music vanishes on every alert | Alert masked by music | `duck_release_ms` |
| `duck_attack_ms` / `duck_release_ms` | 80 / 600 | per F4 | Pumping | Abrupt jumps | — |
| `music_crossfade_ms` | 1,500 | 500 – 3,000 | Tracks muddle on quick view changes | Hard cuts | — |
| `raid_music_timeout_s` | 360 | 310 – 600 | Raid music lingers after a lost event | Cuts off a real raid; must exceed Golden Boss's 300 s limit | Golden Boss `raid_time_limit_s` (300) |
| `report_music_db` | −12 | −20 – −6 | Music competes with report chimes | — | — |
| `resume_fade_ms` | 300 | 0 – 1,000 | Sluggish return | Loud pop on return | — |
| Volume defaults, taper, floor | — | — | — | — | Owned by Settings (`settings_default_vol_*`, `volume_taper_exp`, `volume_floor_db`); not duplicated here |
| `audio_size_budget_mb` | 10 | 6 – 15 | Install size grows (GDD §3.1 small install) | Too few variants, repetitive | Music bitrate |

## Visual/Audio Requirements

*Audio-director and sound-designer lenses applied. No art bible and no audio style guide exist, so these are intents, not specs. The sound palette follows the setting: Vietnamese and wider East Asian martial-arts instruments (drums such as trống, gongs, bells, plucked strings, bamboo flute), dry and short for routine cues, with more reverb for milestones.*

**Wave 1 music (3 loops + 2 stings).** Town theme (calm, plucked strings, 2–3 min loop), Field theme (forward motion, light percussion), Raid theme (war drums, high energy), Victory sting (3–5 s), Defeat sting (3–5 s, sombre but not punishing). OGG Vorbis, streamed, looped.

**Wave 1 event cues.** Tier in brackets; cooldown where it is not 0. Source request in the last column.

| Event (type_id) | Cue | Tier | Cooldown / collapse | Requested by |
|---|---|---|---|---|
| 1401 `gb_announced` | Drum call | T1 | — | Golden Boss, Member state machine |
| 1402 `gb_started` | Boss roar; music → `raid` | T1 | — | Golden Boss |
| 1403 / 1404 `gb_won` / `gb_lost` | Victory / defeat sting | T2 (85) | — | Golden Boss |
| 1407 `gb_summoned` | Horn | T2 (86) | — | Golden Boss |
| 1103 `hunt_member_downed` | Low short cue | T1 | 500 ms | Zones (above loot), Combat |
| 2705 / 2706 arrears started / cleared | Warning / relief | T1 / T3 | — | Gold economy |
| 2302 `member_ascended` | Unique sting | T2 (89) | — | Rebirth |
| 2301 `member_reborn` | Bell strike + rising pad | T2 (87) | — | Rebirth |
| 2102 `signature_skill_learned` | Glow chime | T2 (81) | — | Skills |
| 1502 `candidate_accepted` | Warm sting | T2 (83) | group `join`, slot 2 (wins over 801) | Recruitment |
| 801 `member_joined` | Welcome chime | T3 | group `join`, slot 1 | Member model |
| 3004 `guild_level_up` | Larger beat | T2 (84) | — | Buildings |
| 2202 `member_level_capped` | Calm distinct cue | T2 (80) | 1,000 ms | XP |
| 2403 `enhance_milestone` | Large chime | T2 (80) | group `enhance`, slot 1 | Enhancement |
| 2001 / 2003 `school_joined` / `school_changed` | School beat | T2 (80) | — | Schools |
| 2602 `epic_loot` | Epic chime | T2 (82) | 1,000 ms | Items |
| 1105 `zone_first_entered` | Discovery sting | T2 (81) | — | Zones |
| 903 / 904 trait revealed / added | Discovery sting (low) | T3 | 1,000 ms | CA/PA |
| 902 `pa_exact_revealed` | Soft chime | T3 | — | CA/PA |
| 2601 `loot_handed_in` | **Homecoming chime** (signature) | T3 | 1,500 ms | Zones, Items |
| 2201 `member_level_up` | Soft rise | T3 | 500 ms | XP |
| 2401 / 2402 enhance success / failure | Rising chime / low thud (no glass break) | T3 | group `enhance`, slot 1 | Enhancement |
| 2803 `craft_order_done` | Short chime | T3 | 1,000 ms | Crafting |
| 3003 `build_completed` | Short beat | T3 | — | Buildings |
| 2907 trade order completed | Bright cue | T3 | — | Market |
| 2603 `item_awarded` | Soft gift | T3 | 500 ms | Items |
| 804 `member_equipped` | Metallic click / soft chime (by slot) | T3 | 200 ms | Member model |
| 1501 `recruit_offer_opened` | Gate knock or soft gong | T3 | — | Recruitment |
| 1601 `leave_requested` | Short non-alarming chime | T3 | — | Retention |
| 1604 `member_leaving` | Falling two-note cue | T3 | — | Retention |
| 4102 `member_injured` | Short low cue | T3 | 500 ms | Member state machine |
| 4101 revival transition (dead/injured → idle) | Gentle chime | T3 | 500 ms | Member state machine |
| 1104 `hunt_trip_ended`, reason defeated | Defeat cue | T3 | 1,000 ms | Zones |
| 1101 `hunt_trip_started` | Footsteps / horse | T4 | 1,000 ms | Zones |
| 1301 `party_formed` | Short drum roll | T4 | 1,000 ms | Party |
| 2901 / 2902 sales | Light coin | T4 | 2,000 ms | Market |
| 2704 `upkeep_charged` | Muted drop | T4 | — | Gold economy |
| 1902 / 1903 tower floor / run end (Full Vision) | Ascending chime, gong (boss floor), low drum (wipe) | T3 | — | Endless Tower |

**View-channel and UI-channel cues.** Hit per weapon family (one per school's family; 5 in Wave 1, 10 by Wave 2), counter hit, heal, combat death (monsters only; a member's death is the 1103 cue, R6 step 2), monster attack, boss enrage sting (T1), the Guild screens UI cues `ui_tap`, `ui_confirm`, `ui_refused` (soft refusal, `ui` bus, −6 dB, 300 ms cooldown; the only refusal sound, R1), `ui_toast`, `ui_modal_open`, `ui_badge_new`, IAP success (quiet chime; refund has no sound), enhancement hammer per attempt, fund coin tick, offline report open (soft gong or wood block), report level-up row (capped at 3 per report by Offline progress).

**No sound** for: 1408 `gb_member_rewarded`, 1405, 1406, 501 `command_applied`, 502 `command_refused` (heard as `ui_refused` from Guild screens, R1), 802 `member_removed`, routine 4101 trip transitions, Utility AI decisions, saves (Local save), and catch-up.

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:audio` to produce per-asset descriptions and generation prompts from this section.

## Game Feel

- **Latency.** A UI-channel or view-channel cue starts within one render frame of its request or record (≤ 33 ms at 30 fps). An event cue starts within one frame of its tick being delivered; at 10 Hz that is at most 100 ms after the simulated moment, which is below what a player notices for an idle game.
- **Hits follow the picture.** Combat hit sounds come from the timeline records the world view drew this frame, so a hit is heard when the sword lands on screen, not when Combat resolved the fight.
- **Quiet by default.** The target for a 40-member guild in the town view is no more than about one T3/T4 cue every 2 s on average outside raids. The playtest question: "after 15 minutes, did any sound annoy you enough to lower the SFX slider?"
- **Alerts cut through.** A T1 cue must be identifiable with the phone at low volume over a busy hunt scene (playtest check on a real device).

## UI Requirements

Audio has no screen of its own. The volume sliders and the Mute all toggle are the Audio section of the Settings screen (Settings R12), which owns their layout, labels and storage. Audio's only contribution is the two preview cues (R10). No UX flag is raised for this system.

## Cross-References

| This GDD references | Element | Where used |
|---|---|---|
| `sim-core-and-tick-loop.md` | R15 facade, R16 headless, R17 catch-up presentation | R1, R2, R6 step 1, States |
| `event-bus-and-history-log.md` | R2 record layout, R4 subscriber cap, R12 catch-up | R1, Interactions |
| `deterministic-rng.md` | R1 (engine RNG allowed for cosmetics) | R2 |
| `combat.md` | Visual/Audio item 5; timeline playback | R1, cue list |
| `golden-boss-and-guild-raid.md` | R17 events 1401–1408; Visual/Audio item 5; 300 s fight limit | R4, R8, knobs |
| `zones-grounds-monsters-and-hunt-trips.md` | Visual/Audio event table; homecoming chime | Cue list, R4 |
| `items-and-loot-tables.md`, `crafting-and-recipes.md`, `ca-pa-and-traits.md` | Audio priority lines | R4, cue list |
| `command-layer.md` | Refusal cue quieter than combat/boss | R4 |
| `guild-market-and-trade-orders.md` | Coin cue 1 per 2 s | F3 example, cue list |
| `rebirth-and-ascension.md` | Ascension = highest non-warning cue | R4, cue list |
| `member-model.md`, `member-state-machine.md`, `recruitment.md`, `retention-leaving-and-negotiation.md`, `schools-and-school-change.md`, `skills.md`, `xp-and-level-pacing-curve.md`, `equipment-enhancement.md`, `guild-and-buildings.md`, `gold-economy.md`, `party.md`, `endless-tower.md`, `in-app-purchases.md`, `offline-progress.md`, `account-and-cloud-save.md` | Their Visual/Audio cue requests | Cue list |
| `localization.md` | No voice-over; device-preference storage rule | R10, R11 |
| `settings.md` | R3, R4, R5, R8, R12; F1 `channel_gain_db` and its knobs | R10, F1 |
| `ads.md` | R8.3 mute during rewarded video; Visual/Audio | R9, States |
| `JX1_Tycoon_GDD.md` | §1, §3.1, §3.2, §3.5, §6.5, §12.4 item 6, §12.4.1 | Player Fantasy, R12, knobs |

## Acceptance Criteria

Story types: Logic criteria get automated tests with a fake facade, fake clock and stub players (no audio device needed); Integration criteria run in the engine; Visual/Feel criteria are playtest or device checks with evidence in `production/qa/evidence/`.

- **AC-1 [Logic] (R1, R3)**: **GIVEN** a cue table with a row for 2601 and none for 2701, **WHEN** a frame's batch holds one 2601 and one 2701, **THEN** exactly one `homecoming` cue is requested and nothing for 2701.
- **AC-2 [Logic] (R1)**: **GIVEN** `play_cue("ui_tap", {})` on the UI channel, **THEN** one voice on the `ui` bus starts in that frame. **GIVEN** a fake `view_context` whose `played_records` hold one attack by a `kim_2` member and one `died` record, **THEN** that school's weapon-family hit cue and `combat_death` are requested; **GIVEN** the same records with `suppressed = true`, **THEN** nothing plays.
- **AC-3 [Logic] (R2)**: **GIVEN** a static scan of the Audio source, **THEN** it contains no call to `ctx.emit`, `submit`, any core method outside the R15 facade, or the simulation RNG module. **GIVEN** a headless `run_ticks(1000)` with and without Audio instantiated, **THEN** the event stream and final state hash are identical.
- **AC-4 [Logic] (R4, F2)**: **GIVEN** 12 `sfx` voices playing (9 T4, 3 T3, distinct start times), **WHEN** a T1 cue is requested, **THEN** the oldest T4 voice is stopped and the T1 cue plays; **WHEN** a T4 cue is then requested, **THEN** it is dropped and no voice changes.
- **AC-5 [Logic] (F2 boundary)**: **GIVEN** 12 T3 voices playing, **WHEN** a T3 cue is requested, **THEN** it is dropped (equal priority does not steal).
- **AC-6 [Logic] (R4)**: **GIVEN** a full `sfx` pool of T4 voices, **WHEN** a `ui` cue is requested, **THEN** it plays on a `ui` voice and no `sfx` voice stops.
- **AC-7 [Logic] (R5)**: **GIVEN** boot completed, **WHEN** 1,000 cues are requested over 100 frames, **THEN** the number of player objects is still `sfx_voices + ui_voices + 2`.
- **AC-8 [Logic] (R6 step 1)**: **GIVEN** the facade reports `catching_up = true`, **WHEN** a batch with 1401, 2201 and 2601 arrives, **THEN** no event cue plays; **WHEN** `play_cue("report_open")` is called, **THEN** it plays. **GIVEN** `handoff_pending = true` and `catching_up = false`, **THEN** event cues are still dropped.
- **AC-9 [Logic] (R6 step 2)**: **GIVEN** one frame with 1502 (`b` = 7) and 801 (`a` = 7), **THEN** only the hire sting plays. **GIVEN** 1502 with `b` = 7 and 801 with `a` = 9, **THEN** both play. **GIVEN** 2401 and 2403 with `a` = 4 in one frame, **THEN** only the milestone chime plays. **GIVEN** `play_cue("ui_tap", {member_id: 3})` twice and `play_cue("ui_confirm", {member_id: 3})` in one frame with `ui_tap`/`ui_confirm` in one group, **THEN** one cue plays. **GIVEN** a frame with 1103 (`a` = 5) and a view `died` record for member 5, **THEN** only the 1103 cue plays; **GIVEN** a `died` record for a monster, **THEN** `combat_death` plays. **GIVEN** a cue table row with `collapse_group` and no `collapse_slot`, **THEN** the AC-16 build check fails.
- **AC-10 [Logic] (R6 step 3)**: **GIVEN** a batch with ten 2201 events, **THEN** one level-up cue starts that frame.
- **AC-11 [Logic] (F3)**: **GIVEN** the coin cue with `cooldown_ms = 2,000`, **WHEN** it is requested at 0, 1,999, 2,000 and 3,500 ms, **THEN** it starts at 0 and 2,000 only. **GIVEN** a cue never played, **THEN** its first request passes.
- **AC-12 [Logic] (R7)**: **GIVEN** free voices, an empty queue, no T1/T2 start in the last 600 ms and `milestone_gap_ms = 600`, **WHEN** four T2 cues of priorities 80, 82, 85, 87 arrive in that order in the frame at t = 0, **THEN** 87 starts at t = 0 and 85, 82, 80 wait and start at t = 600, 1,200 and 1,800 ms. **GIVEN** the same, plus a T2 of priority 79 at t = 100 ms, **THEN** it is dropped and the start times are unchanged. **GIVEN** instead a T2 of priority 84 at t = 100 ms, **THEN** 80 is dropped and 85, 84, 82 start at t = 600, 1,200 and 1,800 ms. **GIVEN** the 1,200 ms turn arrives while all 12 `sfx` voices are T1, **THEN** that cue is dropped (not re-queued) and the next waiting cue still starts at t = 1,800 ms. **GIVEN** catch-up begins at t = 1,000 ms, **THEN** the cues due at 1,200 and 1,800 ms are dropped.
- **AC-13 [Logic] (R7, edge case)**: **GIVEN** a T1 and a T2 cue in one frame, **THEN** the T1 starts in that frame and the T2 starts `milestone_gap_ms` later.
- **AC-14 [Logic] (R8)**: **GIVEN** music state `field`, **WHEN** 1402 arrives, **THEN** the state becomes `raid` with a 1,500 ms crossfade; **WHEN** a focus change to `town` is reported, **THEN** the track stays `raid`; **WHEN** 1403 arrives, **THEN** the victory sting plays and after it ends the state is `town`.
- **AC-15 [Logic] (R8 catch-up, edge cases)**: **GIVEN** catch-up during which 1402 arrives and no result, **WHEN** catch-up ends, **THEN** the music switches to `raid` and no roar plays. **GIVEN** 1402 and 1403 both inside catch-up, **THEN** no sting plays and the music never changes. **GIVEN** `raid` with no result for 360 s of fake clock, **THEN** the state leaves `raid`. **GIVEN** 1404 with no prior 1402, **THEN** the defeat sting plays and the music state is unchanged.
- **AC-16 [Logic] (R3)**: **GIVEN** the shipped cue table and the registry's event type blocks, **WHEN** the build check runs, **THEN** every `type_id` in the table is in some owner's registered block, and every row whose `type_id` is not registered in the current wave is reported inactive, not an error.
- **AC-17 [Logic] (F1)**: **GIVEN** `vol_master = 80`, `vol_sfx = 50`, `mute_all = false` and Settings' default k = 2, **WHEN** Audio applies volumes, **THEN** the Master bus is −3.88 dB (±0.01) and the SFX bus −12.04 dB (±0.01); **GIVEN** `vol_music = 0`, **THEN** the Music bus is muted, not set to a dB value; **GIVEN** `mute_all = true`, **THEN** Master is muted and the stored slider values passed in are unchanged.
- **AC-18 [Logic] (F4)**: **GIVEN** music at 0 dB, **WHEN** a T1 cue starts at t = 0 and ends at t = 1,600 ms, **THEN** music gain is −8 dB at t = 80 ms, still −8 dB at 1,600 ms, and 0 dB at 2,200 ms; two overlapping T1 cues never take it below −8 dB.
- **AC-19 [Config] (R12)**: **GIVEN** the shipped `assets/audio/` folder, **WHEN** the license check runs, **THEN** every audio file has a license log entry with source, terms date and tool; a file with none fails the check.
- **AC-20 [Integration] (R9)**: **GIVEN** a device build playing the town theme, **WHEN** the app is sent to background and returned, **THEN** nothing plays while backgrounded and Master fades back in over about 300 ms; **WHEN** a test rewarded video shows, **THEN** game music and SFX are silent while `rewarded_state_changed` is `Showing` and return at their slider levels when it leaves `Showing`.
- **AC-21 [Integration] (R10)**: **GIVEN** the Settings screen, **WHEN** the Music slider is set to 0 and the app restarted, **THEN** music is muted on boot and the slider still reads 0.
- **AC-22 [Integration] (R1, cross-system)**: **GIVEN** a live run where a party returns home in the town view, **THEN** the homecoming chime is heard within one frame of the settlement visual. **GIVEN** a Golden Boss slot, **THEN** the drum call, roar, raid music and a result sting are heard in that order; **GIVEN** the camera moves from the Town to a Ground, **THEN** the music crossfades to the field theme.
- **AC-23 [Visual/Feel] (Game Feel, R11)**: **GIVEN** a 15-minute playtest of a 40-member guild on a min-spec phone, **THEN** the tester can name what each heard cue meant, rates no cue as annoying, and with sound muted reports no information missed. Evidence: playtest notes in `production/qa/evidence/`.
- **AC-24 [Performance]**: **GIVEN** the max-roster fixture at the busiest settlement tick, **THEN** Audio's per-frame CPU cost is under 0.5 ms on the min-spec device (profiler), and total shipped audio is at most `audio_size_budget_mb`.

## Open Questions

- **OQ-1 (owner: technical-director, before architecture).** Where does the cue table live: a presentation resource under `assets/audio/` (this GDD's assumption, R3) or a `data/` CSV checked by `content_validator`? A new Data layer table is a schema change and was not decided by this batch run.
- **OQ-2 RESOLVED (consistency-check 2026-11-16): World view R13 now carries `played_records`.** Original: Realtime world view (38) — `realtime-world-view.md` R13 exposes `view_context` (location, camera, full sprites, `suppressed`, reduced motion) but not the timeline records it played. This GDD assumes a `played_records` field is added to `view_context`, so combat hits sync to the picture without the view playing sound (its R1). Raise with the world view at its next revision; until then hits fall back to none (combat is still visible).
- **OQ-3 (owner: audio-director, Wave 2 planning).** Per-element or per-zone field themes? Wave 1 ships one field theme to keep install size small; five element themes would cost about 7–9 MB more.
- **OQ-4 (closed by `settings.md`).** Settings owns the sliders, `mute_all`, defaults and F1; this GDD conforms. Settings lists Audio as PROVISIONAL and should drop that tag at its next revision; it calls the setter `apply_volumes` here (name to confirm in the Settings ADR/story).
- **OQ-5 RESOLVED (2026-11-16):** Ads R12 `rewarded_state_changed`, mute while `Showing` (R9).
- **OQ-6 (owner: godot-specialist, P1 spike).** Android/iOS audio focus (a call, another app's music) and its interaction with Godot 4.7's audio output: `NOT SOURCEABLE — not covered by docs/engine-reference/godot/modules/audio.md`. Also whether short SFX use WAV with QOA compression or OGG: not covered by the engine reference; decide in an ADR.
- **OQ-7 RESOLVED (2026-11-16):** Guild screens calls `play_cue` with its six UI cue names (R1). Its V/A item 4 must be updated to R6 step 1 (taps/confirms/refusals sound during catch-up; held toasts do not) — cross-cluster request.
- **OQ-8 (owner: producer).** Does the audio license log join `ART_LICENSE_LOG.md` (§12.4.1) as a section, or have its own file?
- **OQ-9 (owner: game-designer).** Haptics (vibration on T1 cues) are out of scope; decide for the mobile polish pass whether they belong to Audio or Settings.
- **OQ-10 PROVISIONAL: payload filters** — the cue list relies on payload fields owned by emitters (1104 reason, 4101 from/to state, 804 slot, 1501 shown stars for the rare-candidate variant, 2803 first-Ward milestone variant). Slot positions are taken from each emitter's GDD at implementation; any that the emitter does not carry fall back to the unfiltered cue.
