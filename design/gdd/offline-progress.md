# Offline Progress

> **Status**: Designed (pending independent `/design-review`)
> **Author**: design-system (autonomous batch run) + user direction in `JX1_Tycoon_GDD.md`
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no `design/gdd/game-pillars.md`). Serves `JX1_Tycoon_GDD.md` §1 ("có offline progress" [CHỐT]), §3.2 (one headless core for realtime, offline, simulator and server replay), §6.5/§6.13 (backlogged Golden Bosses), §10 (offline progress) and §20 S7
> **Mode**: retrofit-style authoring against the Python reference `sim/offline.py` (`estimate_rates`, `fast_forward`). Where this GDD differs from the code, the difference is named in the rule and listed in Open Questions.
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no `game-pillars.md`, no `game-concept.md`; checked against GDD §1 and this GDD's Player Fantasy instead (see Open Questions OQ-12)

## Summary

Offline progress is what lets the guild keep working while the app is closed: when the player comes back, it fast-forwards the absence (up to 12 hours, the same for every player — Premium buys no extra offline time) by sampling a few real hunting trips per group, scaling them to the time away, completing the timers the absence crossed, and resolving up to three missed Golden Bosses, then shows a "while you were away" report. It is a driver over the hunt system's sampled resolver, not a second simulation, so the dice and rules are the same as live play.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Sim core, RNG, Zones and hunt, Utility AI, Items and loot, XP curve, Gold economy, Golden Boss, Party, Event bus, Local save`

## Overview

**Data layer.** Offline progress is the other half of the Sim core's hand-off contract. When the host's `advance` call finds more than `offline_threshold_s` (60 s) of unspent time, the core runs no tick and hands the gap to this system as a whole number of ticks (Sim core R8). This system decides how much of that gap the guild actually worked (the **credited window**: the absence, capped at 12 h for every player (user decision 2026-11-16), and never more than the trusted clock allows), cuts the credited window into slices of about two hours, and for each slice asks Zones and hunt (11) to run a handful of complete sampled trips for every hunting group on a throwaway copy (Zones R15, RNG domain 5). It scales those samples to the slice: XP through the XP curve's `award`, loot through Items and loot's `hand_in` (so auto-equip, storage and sale happen as they would live), gold credited as `offline_hunt` (Gold economy R3, R14). It lets every timer the window crossed fire through its owner, resolves up to `golden_boss_backlog_max` (3) missed Golden Bosses, freezes whatever part of the gap was not credited, and finally calls `skip_ticks(k, resolver_version)` so the core's tick counter jumps over the gap. In the first live tick after the skip it emits a summary on the Event bus, and the report screen reads it.

**Player effect.** The player closes the game at night and opens it at breakfast to a single report: how long they were away and how long the guild worked, levels and XP per member, gold earned, gear auto-equipped and materials stored, builds finished, bosses fought. It is the most frequent reward moment in an idle game and the reason to come back.

**Why it exists.** GDD §1 locks offline progress as part of the game; an idle tycoon that stops when the phone sleeps is not one. Without this system every absence longer than a minute would leave the guild frozen in time (the core has no other path for a long gap), and the GDD §4.3 pacing, which already assumes the offline cap ("dài gấp ~2–4 lần với người chơi thật vì offline cap 8/24 giờ"), could not be reached.

**Boundary.** This GDD describes behaviour. How the resolver is scheduled across frames in Godot (a coroutine, a worker thread with its own `RngFactory` per RNG §threading) is an implementation choice → becomes an ADR.

## Player Fantasy

**Framing: direct**, with infrastructure beneath it. The player never operates offline progress, but they read its output every session.

*Creative-director lens applied. Three framings were drafted; in autonomous mode the recommended combination was taken (decision log).*

1. **"The night shift report" (primary).** Anchor: GDD §1, "thành viên đi săn → mang tài nguyên về → bang bán/chế tạo/nâng cấp → thành viên mạnh hơn". *The moment:* the player opens the app in the morning, a scroll unrolls, and it reads "Away 13 h 12 m — the guild worked 12 h". Below it, Lê Hoàn went from level 41 to 47, the Luyện Khí Đài finished, two Golden Bosses fell and one escaped, and a rare sword was auto-equipped on the healer. The player feels like a guild master receiving a steward's report, not a gamer collecting a timer. *Asks of the design:* the report must be specific (names, items, levels), honest about the cap, and arrive fast (Game Feel).
2. **"The guild never sleeps."** *The moment:* a build queued at 23:00 is done at 07:00 and the next one has started. *Asks:* timers crossed by a gap fire in order (R9). Kept as a rule, not as the headline.
3. **"Same dice, same rules" (constraint, not a headline).** Anchor: RNG GDD Overview, "the same rules and odds while away as while watching". *The moment:* the player notices that a weak member on a hard ground died a lot offline, exactly as they would have live. *Asks:* the sampled resolver prices in risk (deaths, failed trips) and stays within a stated tolerance of exact play (F5). Being away is never better or worse than watching.

**What this system must never make the player feel:** that closing the app is the optimal strategy (it would make realtime play pointless), that the cap is a punishment (the report states it neutrally), or that the numbers are invented (every item and level in the report traces to a sampled trip).

## Detailed Design

*Specialist lenses applied (routing: `Gameplay` → the row that fits is Foundation/Infrastructure-like time handling plus Economy for the credits; Primary `systems-designer` and `game-designer`, Supporting `gameplay-programmer`, `engine-programmer`, `economy-designer`).*

- **game-designer.** The player decides nothing here; their decisions happen before the absence (parties, grounds, builds queued, gear). So offline must reward good setup: a balanced party on a fitting ground earns more offline exactly as it does live. Warn: if members out-level their ground during an 8-hour window and stay there, offline earns less than the balance simulator measured (`tools/balance_sim.py` re-picks the ground every step). Ground re-selection per slice is therefore a rule (R6) with a fallback.
- **systems-designer.** The hand-off must be one deterministic function of `(save state, k, credited ticks, resolver_version)`. Every timer crossed by the gap needs one owner and one rule; the core already says Offline owns them (Sim core R5). Two timer classes are needed, or a paused trip and an elapsing injury get the same treatment (R8).
- **economy-designer.** Gold minted offline must be distinguishable in the ledger (`offline_hunt`, Gold economy R3) and taxed like live income (Gold economy R6). Upkeep must not be charged for time the guild was not credited with (R4), or a long absence on Free costs more than it earns.
- **gameplay-programmer.** Do not run the detailed per-tick resolver outside a tick to finish an in-progress trip: there is no handler context there, and it is the most expensive path. Pausing the live trip and inserting sampled trips is cheaper and deterministic (R5). The resolver must be resumable in small work units so the UI never freezes (R12).
- **engine-programmer.** `Time.get_ticks_usec()` may not count device sleep (Sim core OQ-12), so absences are measured in UTC (Sim core R7). UTC can be changed by the player, so the trust policy (R3) is this system's, and it must work with no network (Account R2). Saving after resolution is Local save's (R8 trigger).
- **Tension surfaced:** game-designer wants the ground re-picked each slice (fidelity to live play and to the balance simulator); gameplay-programmer worried the scorer might not be pure. Resolved by Utility AI's GDD (R1: pure, no RNG, no state), which already names Offline as a caller between slices. Ground is re-picked per slice (R6).

### Core Rules

**R1 — Entry point: one hand-off, one resolution.** When the core's `advance` returns `gap_us > 0` (Sim core R8), the host passes it to `offline.begin(gap_us)`. This system:
1. computes `k = gap_us / tick_us` (always whole, Sim core R8), the trusted elapsed time and the **credited window** `c` (F1, F2, R3, R4);
2. builds the slice plan over the first `c` ticks of the gap (F3, R7);
3. runs the slices in order (R6–R10);
4. freezes the uncredited remainder `u = k − c` (R4, R8);
5. writes the absence summary to its save section (R11), increments `offline_gap_ordinal`;
6. calls `log_offline_credit(c)` (Sim core R6, so replay knows the credited window), then `skip_ticks(k, resolver_version)` exactly once, with the full `k`, never `c`. The core requires the skip to match the pending gap (a mismatch is fatal code 6, Sim core Edge Cases).

Only one resolution runs at a time, because the core allows only one pending hand-off (Sim core R8). A further absence during resolution accrues in the core's accumulator and becomes the next, ordinary hand-off after the skip.

**R2 — Same rules, sampled.** Offline never invents rates. Every XP point, kill, death, item and coin it applies comes from a complete trip run by Zones and hunt's sampled resolver (`sample_rates`, Zones R15) on a copy of the group, with every draw from RNG domain 5 `offline_sample` (RNG R4) and the event keys of R13. The copy fights with Combat's resolver and rolls drops with Items' pure roll, so risk (deaths, defeats, lost time) is priced into the rates.

**R3 — Clock trust policy (GDD §10: "dùng giờ server khi có mạng, chặt hơn khi hoàn toàn offline").** The core measures an absence from device UTC (Sim core R7). This system decides how much of it to believe, without ever waiting for the network:
1. It keeps a **high-water mark** `hw_utc` in its save section: the largest `GameClock.utc_s()` value seen at any save or any resolution. It never decreases.
2. The **trusted elapsed time** is `trusted_s = min(gap_s, max(0, now_utc − hw_utc))` (F1), where `now_utc` is the server estimate if Account and cloud save's `server_utc_estimate()` is known at `begin` (Account R14, F5), else `GameClock.utc_s()`.
3. After resolution, `hw_utc = max(hw_utc, now_utc)`.
4. **Effect:** setting the clock back gives nothing (core clamps to 0; `hw_utc` stays ahead). Setting it forward gives at most one cap of credited time (R4), and afterwards every real absence is credited 0 until real time passes `hw_utc` again. Offline time can be **borrowed, never minted**: over any span, total credited time ≤ real elapsed time + one cap.
5. When a later server response shows the device clock ahead of server time by more than `clock_skew_tolerance_s` (F1), this system sets `clock_skew_flag` in its save section and records the skew. It changes no result; Leaderboards (35) decides what the flag means for ranking (Sim core R7, "trust policy ... Leaderboards").

**R4 — The cap and the credited window.** `cap_s = offline_cap_free_h × 3600` for **every** player — Free, Premium and the PC/Steam build alike (user decision 2026-11-16: equal offline cap for ranked play; Premium is convenience only and buys no offline time). This system reads no entitlement. The config key keeps its historical name `offline_cap_free_h`; `offline_cap_premium_h` is deprecated and not read. The credited window is `c = min(trusted_s, cap_s)` in ticks (F2). The credited window is the **first** `c` ticks of the gap, starting at the hand-off tick `at_tick`. The remaining `u = k − c` ticks are **frozen time**: nothing hunts, no timer fires, no upkeep is charged, and every due tick after the credited window is shifted by `u` (R8). The guild therefore experiences exactly `c` ticks of work across the gap, whatever the clock did.

**R5 — Trips in progress are paused, and sampled trips are inserted.** A group that is mid-trip at `at_tick` keeps its live trip exactly as it is: position in the trip, HP, bag and trip timers. That trip's remaining due ticks are shifted by the full `k` (R8 class *paused*), so it resumes after the skip with the same remaining time. The credited window is filled by **additional, whole sampled trips** (R6). Resting and returning groups are handled the same way (their rest/return timers are paused). This differs from Zones Edge Cases' recommendation (finish the trip with the detailed resolver); Zones left the policy to this system (Zones OQ-7). Reasons: no detailed resolver runs outside a tick, a short backgrounding cannot force early returns, and it is the cheapest correct option.

**R6 — Group plan per slice.** At the start of each slice:
1. **Available members**: members in `hunting`, `returning`, `resting` or `idle` state at `at_tick`, plus members whose recovery timer (dead, injured, training; Member state machine 41) completed in an earlier slice. Members in `away`, `boss_raid` (see Edge Cases) or with a recovery timer still running are not available this slice.
2. **Groups**: a member in a party (Party 13) samples with the available members of that party. A member not in a party samples solo. A party with no available member is skipped.
3. **Ground**: at each slice start, each group's ground is `choose_ground(group, view)` from Utility AI (12, Utility AI R2/R3: a pure, RNG-free scorer that Utility AI already lists Offline as a caller of "between slices"), with the group's members as they stand after the previous slice; groups are asked in ascending anchor order and each chosen group is added to `view` (Utility AI R4), as Member state machine does live. If it returns `none`, the group idles this slice (Utility AI R9). A brand-new member who never hunted is grouped and asked like any other available member.
4. A ground that is no longer live for the group (Zones R2: content wave, guild level, rebirth) is never sampled; the group falls back to the highest live ground it may enter that it most recently hunted, else idles.

Groups are processed in ascending **group anchor** order (R13).

**R7 — Slices.** The credited window is cut into slices of at most `offline_slice_s` (7,200 s; reference `chunk_s`). A slice also ends early at any due tick inside the window that its owner declared **rate-changing** (a build completion that changes hunt effects, Guild and buildings Edge Cases; an upkeep slot that turns buffs off, Gold economy R8), so new effects apply from the next slice, as Buildings requires ("new level's effects ... from the tick after each completion"). Golden Boss due ticks never cut a slice (bosses are handled by R10). Slices are numbered from 0 within one gap.

**R8 — Timers crossed by the gap (Sim core R5: Offline owns every crossed due tick).** Every timer owner registers with this system at boot as one of two classes:
- **Paused** (activity in progress: the live trip, rest, return travel). Every due tick `D ≥ at_tick` is shifted to `D + k`. The activity resumes after the skip with its remaining time.
- **Elapsing** (time passes for it: upkeep, salary and interest slots, build completions, recovery timers, CA/PA day boundaries, quests, Golden Boss cadence). Due ticks inside the credited window `[at_tick, at_tick + c)` fire through the owner's `settle_to(to_tick)` hook at the end of the slice that contains them (R9). Due ticks at or after `at_tick + c` are shifted by `u` (frozen time). The owner re-anchors its own grid (Sim core R5 convention); this system tells it the shift.

After the skip, the first live tick sees no overdue timer and no burst (Sim core Edge Cases).

**R9 — Order of work inside one slice.** Deterministic and identical on every implementation:
1. Build the group plan (R6).
2. For each group in ascending anchor order: call `sample_rates(group, ground, offline_sample_trips, keys)` (Zones R15) and apply it (F4): XP through `award` per member in ascending `member_id`; scaled bag hand-ins through Items `hand_in` in rotation order, credited as `offline_hunt` (R14 below); kill and death counts into the absence summary.
3. (Golden Boss slots inside this slice are only counted here; the backlog is resolved once after the last slice, R10.)
4. Every elapsing timer owner, in ascending owner block number, is called with `settle_to(slice_end_tick)` (Gold economy's `settle_schedule`, Gold economy R14; build completions, Guild and buildings Edge Cases; CA/PA's day-boundary handler, CA/PA OQ-11; recovery timers).

Step 4 runs after the slice's income, so upkeep is charged against the fund as income arrives (Gold economy Edge Cases "Offline").

**R10 — Golden Boss backlog (GDD §6.5 "tối đa N", S7 "tối đa 3"; Golden Boss R16 owns the rule).** This system reports to Golden Boss (14) the slots whose due ticks fall inside the **credited** window (slots in frozen time are shifted by R8, not crossed). Golden Boss keeps the last `min(K, golden_boss_backlog_max)` (3, owned by Golden Boss) as backlog and drops the rest as missed. After the last slice's step 4, this system calls Golden Boss R16 once; it resolves each backlog slot in slot order with its normal raid rules (R3–R10 there, no announcement, recall or gathering), against the guild as it stands at the end of the window. Rewards follow Golden Boss's rules (guild loot via Items R9a, `boss_reward`). Members on a paused live trip (R5) count as home for backlog eligibility; their trip state is unchanged (Golden Boss R16 agrees, OQ-6 resolved).

**R11 — The absence summary.** The resolution writes one summary record to this system's save section: `gap_ordinal`, `gap_s`, `trusted_s`, `credited_s`, `cap_s`, `capped` (bool), and per member: level before and after, base XP awarded, gold credited, kills, deaths, items auto-equipped, units stored, units sold; guild-wide: bosses won, lost and missed, builds completed, upkeep paid. The record is kept until the player dismisses the report or the next hand-off replaces it (one record, not a history: the Event bus history log is the history).

**R12 — Resumable, bounded work.** The resolver's unit of work is one sampled trip. It runs across frames with at most `offline_frame_budget_ms` of work per frame and returns control between units; results do not depend on how units are spread across frames (same as Sim core R17 for ticks). The core is pending during resolution, so presentation shows a catching-up state (Sim core R15). Resolution has no time-out (Sim core R8), but it has a performance target (F6, AC-20).

**R13 — RNG keys (domain 5, RNG R5, R6).** One sampled trip uses one generator, key `[offline_gap_ordinal, slice_index, group_anchor, sample_index]`:
- `offline_gap_ordinal`: saved counter in this system's section, starts at 1, advanced only by a completed resolution;
- `slice_index`: 0-based within the gap;
- `group_anchor`: the `party_id` for a party, or `2^63 + member_id` for a solo member (the high bit separates the two ID spaces);
- `sample_index`: 0 … `offline_sample_trips − 1`.
Unique because no two sampled trips share all four. No component is player-mutable: the party ID is a stable entity ID and none of the four reads composition, equipment or ground. A reload before resolution reproduces the same dice (RNG R5, accepted property).

**R14 — Credits are live-shaped.** XP enters only through `award` (XP curve R4), which applies PA and rebirth multipliers exactly once to the source-side base XP (Zones R15). Loot enters only through `hand_in` (Items R6, R12), which returns the trip income and credits nothing; this system divides it by the Zones R8 split and credits each share as `offline_hunt` instead of `loot_handover`/`hunt_gold` (Gold economy R3 type 3, R14); tax applies as for a live credit (Gold economy R6). Nothing writes a wallet, storage or a member field directly.

**R15 — Events.** In P5 of the first live tick after the skip, this system's handler (owner `offline`, order 3100) emits the summary (Event bus R12) from its saved record and then clears a `summary_pending` flag:
- **3101 `offline_resolved`** (`a` = credited_s, `b` = gap_s clamped to int32, `c` = bosses won, `d` = gap_ordinal). Logged, milestone no, `ring_per_day` 24.
- **3102 `offline_member_summary`** (`a` = member_id, `b` = levels gained, `c` = kills, `d` = deaths), one per member who gained anything. Not logged.
- One **2201 `member_level_up`** per member whose level changed, with `b` = level at `at_tick`, `c` = level after resolution (XP curve R6 "once per award that changes the level"; the gap is treated as one award for events). Emitted on XP curve's behalf (XP curve R4 step 5, OQ-5 resolved) so CA/PA reveals and Chronicle entries fire once per absence.
Peak: 2 + 2 × roster events in one tick, once per absence.

**R16 — What is saved.** `offline_gap_ordinal`, `hw_utc`, `clock_skew_flag` and its skew, the summary record and `summary_pending`. Nothing about an in-flight resolution is saved: the core's pending gap is not saved either (Sim core R14), so a crash mid-resolution re-measures the absence from `last_saved_utc` on the next start and resolves it from scratch with the same keys (same `offline_gap_ordinal`), giving the same result for the same gap.

**R17 — Determinism and versioning.** The resolution is a pure function of the loaded state, `k`, `c` and `resolver_version`. `resolver_version` is a uint32 constant in this system's code (starts at 1), passed to `skip_ticks` and logged by the core (Sim core R8), and bumped on any change that alters a resolution result. It is outside `phase_table_hash` (Zones R15). Leaderboards' replay needs `c` as well as `k` (OQ-2).

### States and Transitions

| State | Entered when | Leaves to | On |
|---|---|---|---|
| `Idle` | boot; after a skip | `Planning` | host calls `begin(gap_us)` |
| `Planning` | `begin` | `Resolving` | F1–F3 computed, slice plan built (one frame) |
| `Resolving` | plan ready | `Settling` | last slice's step 4 done |
| `Resolving` | — | `Resolving` | end of frame budget (R12): resumes next frame |
| `Settling` | slices done | `Skipped` | R4/R8 shifts applied, summary written, `skip_ticks` returned OK |
| `Skipped` | skip OK | `Idle` | first live tick's P5 handler emits R15 events and clears `summary_pending` |
| any | — | (process dies) | crash or kill: nothing in flight is saved; next start re-measures (R16) |

Invalid transitions: `begin` while not `Idle` is a host bug and is refused with an error return (the core would also refuse a second hand-off). `skip_ticks` is called only from `Settling`. A zero-credit gap (`c = 0`) goes `Planning → Settling` directly (no slices).

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|---|---|---|---|---|
| Sim core (1) | both | `gap_us` from `advance`; `GameClock.utc_s()`; `tick_rate` | `skip_ticks(k, resolver_version)`; a P5 handler (order 3100) | Sim core owns the hand-off; this system owns the trust policy, backlog and re-anchoring (Sim core R5, R7, R8) |
| Deterministic RNG (2) | owner → RNG | — | `derive(5, key)` per sampled trip (R13) | RNG owns domain 5; this system owns the key layout |
| Member model (8) | read | Member records, states, party membership | — (writes only through `award`, `hand_in`) | Member model |
| Combat (10) | indirect | through `sample_rates` | — | Combat |
| Zones and hunt (11) | 31 → 11 | `sample_rates` totals and per-trip bags (Zones R15, F10) | group, ground, sample count, keys | Zones owns the resolver; this system owns the driver and tolerance |
| Utility AI (12) | 31 → 12 | `GroundChoice` | `choose_ground(group, view)` per group per slice | Utility AI R2–R4, R9 |
| Party (13) | read | party membership and `party_id` | — | Party (PROVISIONAL, OQ-4) |
| Golden Boss (14) | 31 → 14 | backlog results (1406 events, rewards) | crossed slots in the credited window; one R16 call after the slices; cadence shift | Golden Boss R16 owns the backlog rule, cap and resolver; this system owns the gap |
| XP curve (22) | 31 → 22 | old/new level | `award(null ctx, member, base_milli, source)` | XP curve (PROVISIONAL, OQ-5) |
| Items and loot (26) | 31 → 26 | hand-in results (returned income) | `hand_in(roster, bag)` per rotated sampled bag; this system credits `offline_hunt` | Items (conformed, OQ-7) |
| Gold economy (27) | 31 → 27 | — | `offline_hunt` credits of the returned hand-in income (R14); `settle_schedule(to_tick)` per slice | Gold economy R14 |
| Guild and buildings (30) | 31 → 30 | completions, rate-changing due ticks | `settle_to(to_tick)` | Buildings Edge Cases |
| CA/PA and traits (9) | 31 → 9 | — | day-boundary `settle_to`; forwarded 2201 | CA/PA OQ-11 |
| Event bus (42) | 31 → bus | — | 3101, 3102, forwarded 2201 (R15) | Event bus R12, OQ-2 |
| Local save (6) | both | `last_saved_utc` (via the core's absence rule) | this system's save section (R16); a save after skip (Local save R8 trigger) | Local save |
| Account and cloud save (7) | soft, read | `server_utc_estimate()` | — | Account R14 |
| Leaderboards (35) | 31 → 35 | — | `clock_skew_flag`; resolver is replayable | Leaderboards owns the ranking consequence |
| Guild screens (39) / Realtime world view (38) | 31 → UI | — | summary record, progress during `Resolving` | UI owns layout |

## Formulas

*Systems-designer lens applied: each formula has its variable table, boundaries worked at 0, minimum and maximum, and feedback loops named.*

### F1 — Trusted elapsed time

The trusted_elapsed formula is defined as:

`trusted_s = min(gap_s, max(0, now_utc − hw_utc))`, with `gap_s = k // tick_rate`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| k | int | `offline_threshold_s × tick_rate` + 1 … 2^62 / tick_us | calculated (Sim core R8) | Ticks in the handed-off gap |
| tick_rate | int | 1–60 (10) | data file (`config.tick_rate`, Sim core) | Ticks per second |
| now_utc | int | ≥ 0 | calculated | `server_utc_estimate()` if known, else `GameClock.utc_s()` (R3) |
| hw_utc | int | ≥ 0 | calculated (saved) | High-water UTC seen at saves and resolutions; 0 on a new guild means "now" at creation |
| clock_skew_tolerance_s | int | 60–3,600 (300) | data file (`config.offline_clock_skew_tolerance_s`, new) | Device-ahead-of-server margin before `clock_skew_flag` is set (R3.5) |

**Output Range:** 0 to `gap_s`. 0 when the clock was set back below `hw_utc`. Never above the gap the core measured.
**Example:** last save at UTC 1,800,000,000 (= `hw_utc`), app reopened at 1,800,033,120 (9 h 12 m). `gap_s` = 33,120, `trusted_s = min(33,120, 33,120)` = 33,120. If the player had set the clock forward a day earlier and back again, `hw_utc` = 1,800,086,400 and `trusted_s = 0`.
**Boundaries:** `now_utc = hw_utc` → 0. `hw_utc = 0` cannot happen on a live save (set at creation). `gap_s` at its minimum (61 s at defaults) → up to 61.

### F2 — Credited window

The credited_window formula is defined as:

`c = min(trusted_s, cap_s) × tick_rate` ticks; `u = k − c`; `cap_s = offline_cap_free_h × 3600` (one cap for every player, R4)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| trusted_s | int | 0 … gap_s | calculated (F1) | Trusted elapsed seconds |
| offline_cap_free_h | int | 1–24 (12) | data file (`config.csv`, exists; value still 8 there until the data change lands) | The one offline cap, hours, for every player (user decision 2026-11-16; was 8 Free / 24 Premium) |

**Output Range:** 0 to `cap_s × tick_rate` (432,000 ticks at the default, for every player). `u` is 0 when the gap is shorter than the cap.
**Example:** 13 h 12 m away (any entitlement): `c = min(47,520, 43,200) × 10 = 432,000` ticks (12 h), `u = 475,200 − 432,000 = 43,200` ticks (1 h 12 m frozen). The report says "Away 13 h 12 m — the guild worked 12 h".
**Boundaries:** trusted 0 → `c = 0`, a pure skip with every due tick shifted by `k`. Validator rule: `offline_cap_free_h ≥ 1` (a cap of 0 would make the hand-off threshold the cap, and every absence a pure skip).

### F3 — Slice plan

The slice_plan formula is defined as:

`slice_end_i = min(slice_start_i + offline_slice_s × tick_rate, next_rate_change_tick(slice_start_i), at_tick + c)`, `slice_start_0 = at_tick`, `slice_start_{i+1} = slice_end_i`; `n_slices ≈ ceil(c / (offline_slice_s × tick_rate)) + rate_change_cuts`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| offline_slice_s | int | 600–14,400 (7,200) | data file (`config.offline_slice_s`, new; reference `chunk_s`) | Longest slice, seconds |
| next_rate_change_tick | int | > slice_start | calculated (timer owners, R7) | Earliest rate-changing due tick after the slice start, or +∞ |
| at_tick | int | ≥ 0 | calculated (Sim core) | Tick at which the gap begins |

**Output Range:** at defaults, 6 slices for the 12 h cap (4 for 8 h), plus one per rate-changing event in the window (a build queue of `build_queue_max` = 2 adds at most a few). `c = 0` → 0 slices.
**Example:** 8 h credited, one build completes at 3 h: slices [0, 2 h), [2 h, 3 h), [3 h, 5 h), [5 h, 7 h), [7 h, 8 h) — 5 slices.
**Why 2 h:** the reference measured about 1% XP drift at 2-hour slices with 4 samples and found 30-minute slices with 8 samples slower than the exact run (`sim/offline.py` docstring, GDD §18.1). Shorter slices track level-ups better; longer ones are cheaper.

### F4 — Applying a sample to a slice

The offline_apply formula is defined as (extends Zones F10, which owns what a total means):

`xp_i(m) = floor(base_xp_milli(m) × slice_ms / sample_ms)` → `award(m, xp_i(m))`
`trip_milli_i = floor(slice_ms × S × 1000 / sample_ms) + carry_g`, `trips_i = trip_milli_i // 1000`, `carry_g = trip_milli_i mod 1000`
`hand_in(bag[(j) mod S])` for `j = 0 … trips_i − 1`
`kills_i(m) = floor(kills(m) × slice_ms / sample_ms)`, `deaths_i(m)` likewise with a carried remainder

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| base_xp_milli(m) | int | ≥ 0 | calculated (Zones R15) | Source-side XP the member earned over the S sampled trips |
| kills(m), deaths(m) | int | ≥ 0 | calculated (Zones R15) | Totals over the sampled trips |
| bag[s] | map | — | calculated (Zones R15 `bags[i]`) | The bag of sampled trip s, unscaled |
| sample_ms | int | > 0 | calculated (Zones R15) | Total length of the S sampled trips |
| slice_ms | int | > 0 | calculated (F3) | Slice length in ms |
| S | int | 1–16 (4) | data file (`config.offline_sample_trips`, new; reference `trips`) | Sampled trips per group per slice |
| carry_g | int | 0–999 | calculated (per group, per gap) | Fractional trips carried to the next slice, in milli-trips |

**Output Range:** proportional to `slice_ms`. `sample_ms` is never 0 (Zones R15 rejects it). `base_xp_milli × slice_ms` ≤ about 10^7 × 1.4 × 10^7 ≈ 1.4 × 10^14, inside int64. `trips_i` is about `slice_ms / mean_trip_ms` (for 20-minute trips, 6 per 2-hour slice).
**Example:** 4 sampled trips total 3,600,000 ms and a member's `base_xp_milli` is 12,000,000. A 2-hour slice awards `12,000,000 × 7,200,000 / 3,600,000 = 24,000,000` milli-XP once. `trip_milli = 7,200,000 × 4 × 1000 / 3,600,000 = 8,000` → 8 hand-ins: bags 0,1,2,3,0,1,2,3.
**Why rotation, not scaling:** handing in whole sampled bags keeps every unit an integer (no fractional rare items, Items OQ-6) and sends every unit through `hand_in` (Items R12). It is unbiased (each sampled bag is an honest trip) but has the samples' variance: a rare drop in one sample repeats `trips_i / S` times in that slice. Fresh samples every slice average it out over a long absence; AC-6 bounds it.
**Difference from the reference:** `fast_forward` credits gold directly (`m.gold += rg × dt`) and calls `auto_gear`; this spec delivers loot and gold through `hand_in`, which does both (R14).
**Feedback loop:** positive (stronger members → more XP and gear offline → stronger). Intended; it is the core loop. Damped by the cap, the level-difference factor (Zones F2) and the XP curve.

### F5 — Parity tolerance

The parity_tolerance formula is defined as:

`drift_xp = |mean_seeds(xp_offline) / mean_seeds(xp_exact) − 1| ≤ offline_parity_tol_xp`; `drift_gold` likewise `≤ offline_parity_tol_gold`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| xp_exact, xp_offline | int | ≥ 0 | calculated (test fixture) | Total XP of the same party, same start, same window, run tick-exact and through this system |
| offline_parity_tol_xp | float (test constant) | 0.005–0.05 (0.02) | constant (test fixture `tests/integration/offline/`) | XP tolerance; matches Combat AC-25 (≤ 2%), reference measured ~1% |
| offline_parity_tol_gold | float (test constant) | 0.01–0.10 (0.03) | constant (test fixture) | Gold and stored-units tolerance; matches Items AC-24 (±3%) |

**Output Range:** a pass/fail. Measured over at least 5 seeds for the 24-hour 5-member fixture, and over 200 seeds for the threshold fixture (gaps of `offline_threshold_s + 1` s), where the mean XP per credited second must also be within ±5% of the exact long-run rate, so backgrounding for just over the threshold cannot be farmed (Sim core OQ-1).
**Why these are constants, not knobs:** they are quality gates for the build, owned by tests; loosening them is a design decision, not a tuning step.

### F6 — Resolution cost

The resolution_cost formula is defined as:

`cost ≈ n_slices × G × S × trip_cost`, wall time `≈ cost / offline_frame_budget_ms` frames

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n_slices | int | 0–~15 | calculated (F3) | Slices in the window |
| G | int | 1 – roster cap | calculated (R6) | Groups sampled per slice |
| S | int | 1–16 (4) | data file | Samples per group |
| trip_cost | ms | measured | measured (P1 spike) | Cost of one sampled trip on the target device |
| offline_frame_budget_ms | int | 2–16 (8) | data file (`config.offline_frame_budget_ms`, new) | Work per frame while resolving (R12) |

**Output Range:** 12 h (the cap), one 5-member party: 6 × 1 × 4 = 24 sampled trips (the 24 h reference: ≈ 0.5 s in Python versus 1.6 s exact, GDD §18.2, so about half that). Max roster in ~6 groups: about 145 trips.
**Target:** ≤ 1 s wall time for a full 12 h cap with one 5-member party on a mid-range Android device (GDD §21 Prompt B), ≤ 3 s at the max-roster fixture on min-spec; if not met, reduce `S` or lengthen `offline_slice_s` within F5, or move the resolver to GDExtension (GDD §21).

## Edge Cases

*Systems-designer lens applied to C and D: zero, max, simultaneity, dependency floors, degenerate strategies.*

**Time and clock**
- **If `c = 0`** (clock set back, or `now_utc ≤ hw_utc`): no slice runs, every due tick ≥ `at_tick` is shifted by `k`, the summary shows "Away X — the guild worked 0 m", `skip_ticks(k)` is still called (the core must leave pending).
- **If the player sets the clock forward to farm**: credited at most one cap (F2); `hw_utc` moves to the fake time, so real absences are credited 0 until real time passes it (R3.4). Net credited time over any span ≤ real time + one cap.
- **If the device clock is ahead of a later server reading by more than `clock_skew_tolerance_s`**: `clock_skew_flag` is set; no result changes; Leaderboards decides (R3.5).
- **If the gap is exactly the cap**: `u = 0`, nothing is frozen.
- **If a second absence happens during `Resolving`**: it accrues in the core (Sim core R8 Pending) and becomes the next hand-off after the skip, with its own `gap_ordinal`, slices and keys; it is never merged into the first.
- **If the app is killed during `Resolving`**: nothing is saved mid-resolution; the next start re-measures from `last_saved_utc` (a gap now longer by the time dead) and resolves from scratch with the same `gap_ordinal`, so the first part of the result is identical and only the extra time is new (R16).
- **If `gap_s` is just above `offline_threshold_s`** (61 s): about 0.5 sampled trips' worth is applied (`trips_i` may be 0 with a carry; XP is applied proportionally). Live trips are paused, not ended, so frequent short backgrounding neither helps nor hurts on average (F5 threshold fixture).

**Members and groups**
- **If a member is in `boss_raid` at `at_tick`** (a live raid was running): the raid's fight is atomic and saved (Golden Boss R18), so it is finished first at `at_tick` by Golden Boss, outside the backlog count; its members are available from slice 0 (PROVISIONAL, OQ-6).
- **If a member is dead, injured or training at `at_tick`**: their recovery timer is elapsing (R8); they join their group from the first slice after it completes. A death inside a sampled trip is priced into the rates and never puts the real member into `dead` (the copy is revived after each trip, Zones/Combat).
- **If a member levels up past their ground mid-window**: the next slice uses the new level (F4 re-samples per slice) and Utility AI picks a fitting ground (R6.3).
- **If a member leaves the roster mid-window** (Retention 16 is Vertical Slice): not modelled at MVP; Retention's departure timers are elapsing timers and fire through `settle_to` at the slice end, after which the member is not available (PROVISIONAL, OQ-9).
- **If a group's ground stops being live** (content wave flag changes between sessions): R6.4 fallback, else the group idles.
- **If the bag of a sampled trip holds an item no member may equip**: `hand_in` sells or stores it by Items R6; nothing is lost.
- **If storage is full or a wallet would exceed int64**: owned by Items and Gold economy; this system passes no amount that the live path could not also pass (each hand-in is one trip's bag).

**Timers**
- **If two timers fall on the same tick in one slice**: they settle in ascending owner block number (R9.4), then each owner's own order.
- **If a build completion falls exactly on a slice boundary**: it settles at the end of the slice that ends there, and its new effects apply from the next slice (R7).
- **If 12 Golden Boss slots are crossed** (a full 12 h window, the most any player can be credited): the last 3 are resolved, 9 are missed (R10, Golden Boss Edge Cases). If 2 are crossed, both are resolved.
- **If an elapsing timer's due tick is in the frozen part**: it is shifted by `u` and fires live later with its remaining time intact.
- **If upkeep would exceed the fund**: Gold economy pays what it can and turns buffs off (Gold economy R8); because it is a rate-changing tick (R7), the next slice samples without the buffs.

**Degenerate strategies**
- **Background at the threshold repeatedly to skip risk**: risk is in the sampled rates (deaths, defeats), so no.
- **Reload before resolution to re-roll**: keys are fixed (R13), so the same dice return; the player can change inputs (party, ground) before closing the app, which is legitimate play.
- **Buy Premium for more offline time**: impossible; the cap is the same for every player (R4), so a ranked board never rewards a purchase with worked time.
- **Stay offline forever rather than play**: offline earns at the live rate up to the cap and nothing beyond it, and has no player decisions; live play earns the same rate with decisions (orders, bosses fought live instead of 3 of 12). Offline is never better than live per hour.

## Dependencies

| System | Direction | Hard/Soft | Interface | Status |
|---|---|---|---|---|
| Sim core and tick loop (1) | upstream | Hard | `advance` → `gap_us`, `skip_ticks(k, resolver_version)`, `GameClock`, P5 registration, anchored timers (R5) | GDD exists (In Review) — conforms to R5, R7, R8, OQ-1 |
| Deterministic RNG (2) | upstream | Hard | domain 5 `offline_sample`, key layout R13 | GDD exists |
| Member model (8) | upstream | Hard | records, states (read only) | GDD exists |
| Combat (10) | upstream | Hard (indirect) | through Zones' sampled trips | GDD exists |
| Zones and hunt (11) | upstream | Hard | `sample_rates` (R15) with per-trip `bags[i]`, F10 | GDD exists — conformed (OQ-7) |
| Party (13) | upstream | Hard | `party_id`, membership | No GDD — PROVISIONAL (OQ-4) |
| Golden Boss (14) | upstream | Hard | crossed slots, R16 backlog call | GDD exists — conforms to R16; one conflict (OQ-6) |
| XP curve (22) | upstream | Hard | `award` without a handler context | GDD exists — PROVISIONAL (OQ-5) |
| Items and loot (26) | upstream | Hard | `hand_in` returning the income (Items R6 step 4) | GDD exists — conformed (OQ-7) |
| Gold economy (27) | upstream | Hard | `offline_hunt` (type 3), `settle_schedule(to_tick)` (R14) | GDD exists — conforms |
| Event bus (42) | upstream | Soft | type block 3100–3199, R12 | GDD exists — answers its OQ-2 |
| Local save (6) | upstream | Hard | save section (R16); save after skip | GDD exists — conforms (R8 trigger) |
| Guild and buildings (30) | peer | Hard (for 30) | `settle_to`, rate-changing due ticks | GDD exists — answers its OQ-5 |
| CA/PA and traits (9) | peer | Soft | day-boundary `settle_to`; forwarded 2201 | GDD exists — answers its OQ-11 |
| Utility AI (12) | upstream | Hard | `choose_ground(group, view)` | GDD exists — conforms |
| Account and cloud save (7) | upstream | Soft | `server_utc_estimate()` | GDD exists — answers its OQ-13 |
| Member state machine (41) | upstream | Soft | state names, recovery timers | No GDD — PROVISIONAL (OQ-9) |
| Leaderboards (35) | downstream | Soft | replayable resolution, `clock_skew_flag` | No GDD |
| Guild screens (39), Realtime world view (38) | downstream | Hard (for them) | summary record, `Resolving` progress | No GDD |
| Local push notifications (46) | downstream | Soft | cap reached time (`hw_utc + cap_s`) | No GDD (Full Vision) |
| Dev tooling and parity harness (43) | downstream | Hard (build) | F5 tests in the determinism class; `tools/balance_sim.py` uses `fast_forward` | GDD exists |

**Bidirectional check:** the index row for 31 lists Sim core, RNG, Member model, Combat, Zones and hunt, Party, Golden Boss, Gold economy, Event bus. This GDD adds hard links to Items and loot (26), XP curve (22) and Local save (6), already asserted from their side (Items R12, XP R4/OQ-4, Local save R8), and soft links to Account (7), Utility AI (12), Member state machine (41) and Guild and buildings (30). The index row's Depends On column is updated with the hard ones. The former soft link to Entitlement (32) was dropped by the 2026-11-16 equal-cap decision (R4).

## Tuning Knobs

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `offline_cap_free_h` (`config.csv`, exists) | 12 (was 8; user decision 2026-11-16) | 8–16 | Live play less needed; ranked boards reward absence | A night's sleep exceeds it; returning feels punished | GDD §4.3 pacing ("×2–4 real time"); `golden_boss_backlog_max`; Leaderboards F1 |

`offline_cap_premium_h` (24) is **deprecated** (user decision 2026-11-16): one cap for every player, Premium is convenience only. It is not read; remove it from `config.csv` with the data change that sets `offline_cap_free_h = 12`.
| `offline_slice_s` (new) | 7,200 | 1,800–14,400 | Level-ups tracked poorly, more drift (F5 fails) | Slower than exact (reference) | `offline_sample_trips`, F6 |
| `offline_sample_trips` (new) | 4 | 2–8 | Slower; variance lower | High variance of rare loot (AC-6 fails) | `offline_slice_s` |
| `offline_clock_skew_tolerance_s` (new) | 300 | 60–3,600 | Clock tampering not flagged | Honest drifted clocks flagged | Leaderboards (35) |
| `offline_frame_budget_ms` (new) | 8 | 2–16 | Frame drops during the report intro | Resolution takes many seconds | F6 target |
| `offline_report_min_s` (new) | 300 | 61–3,600 | Short absences give no feedback | A report after every phone call | — |

Owned elsewhere and read here: `golden_boss_backlog_max` (3, Golden Boss 14); `offline_threshold_s` and `tick_rate` (Sim core); `chunk`-independent trip timing knobs (Zones); tax rate (Gold economy); Golden Boss cadence (Golden Boss). The parity tolerances (F5) are test constants, not knobs.

## Visual/Audio Requirements

*Art-director lens applied. No art bible exists (`design/art/art-bible.md` absent); drafted from GDD §1 tone (Vietnamese martial-arts guild, pixel 2D, paper-doll sprites §3.5).*

- **While resolving:** a full-screen "the steward is counting" state over the dimmed guild map: a pixel scroll or abacus animation with a progress bar driven by sampled trips done / planned (R12). No per-event animation or sound (Sim core R15 suppression).
- **Report reveal:** the scroll unrolls top to bottom; headline (away / worked), then per-member rows with a small portrait (paper-doll head), level-up chevrons, then guild rows (bosses, builds, gold). A soft gong or wooden-block cue on open; a short chime per level-up row, capped at 3 chimes so a big roster does not spam.
- **Cap reached:** a neutral hourglass icon, never red or alarming (Player Fantasy "never a punishment").
- **Rare item row:** item rarity colour plus an icon and text label (not colour alone, accessibility).
- 📌 **Asset Spec** — after the art bible is approved, run `/asset-spec system:offline-progress`.

## Game Feel

- **Time to report:** the first frame of the resolving state within 100 ms of resume; the report on screen within 1 s for the 5-member 12 h (cap) case on mid-range Android (F6). Anything longer shows real progress, never a spinner without a bar.
- **One tap to dismiss**, one tap to "see details" per member; dismissing never loses data (the record stays until the next absence, R11).
- **Skippable reveal:** tapping during the unroll shows the full report at once.
- **No dead input during resolution:** the player can open menus; orders queue and acknowledge immediately (Sim core R15, Command layer), and apply after the skip.

## UI Requirements

- **"While you were away" report** (Guild screens 39 owns layout): headline `Away {gap} — the guild worked {credited}` (+ `cap {cap_h} h` when capped; no Premium upsell line — Premium does not change the cap); per member: name, level before → after, XP, gold, kills, deaths, items equipped; guild: bosses won/lost/missed, builds finished, upkeep paid, materials stored. Shown when `credited_s ≥ offline_report_min_s`; shorter absences show a one-line toast.
- **Resolving overlay** with progress (R12).
- All strings keyed in `i18n/` (Localization 4), numbers formatted per locale; Vietnamese names may be long (room for 24 characters per name).

> **📌 UX Flag — Offline progress**: this system has UI requirements. In Pre-Production, run `/ux-design` for the "while you were away" report and the resolving overlay before writing epics; stories should cite `design/ux/[screen].md`.

## Cross-References

| This GDD | Other document | Section | Nature |
|---|---|---|---|
| R1, R8, R17 | `sim-core-and-tick-loop.md` | R5, R7, R8, R14, R16, Edge Cases, OQ-1 | Interface: hand-off, skip, timer ownership |
| R13 | `deterministic-rng.md` | R3–R6, domain 5 | Key layout for `offline_sample` |
| R2, R5, F4 | `zones-grounds-monsters-and-hunt-trips.md` | R15, F10, Edge Cases, OQ-7 | Sampled resolver; in-progress trip policy (differs from its recommendation) |
| R14, F4 | `items-and-loot-tables.md` | R6, R12, AC-24, OQ-6 | Loot through `hand_in`; rotation answers fractional units |
| R9, R14 | `gold-economy.md` | R3 (type 3), R6, R8, R14 | Offline credits and per-slice settlement |
| R14, R15 | `xp-and-level-pacing-curve.md` | R4, R6, Edge Cases D, OQ-4 | One `award` per slice; one 2201 per absence |
| R10 | `golden-boss-and-guild-raid.md` | R14, R16, R18, PROVISIONAL-3 | Backlog rule and cap owned there |
| R6 | `utility-ai.md` | R1–R4, R9 | Ground choice per slice |
| R9 | `guild-and-buildings.md` | Edge Cases (offline), AC-15, OQ-5 | Builds complete at due ticks inside the window |
| R9, R15 | `ca-pa-and-traits.md` | OQ-11 | Day boundaries and level-reveal events |
| R15 | `event-bus-and-history-log.md` | R12, OQ-2 | Summary events after a skip |
| R16 | `local-save-and-migration.md` | R8 trigger, AC-9 | Save after a resolved hand-off |
| R3 | `account-and-cloud-save.md` | R14, F5, OQ-13 | Server time estimate; trust policy owned here |
| F5 | `combat.md` | AC-25 | ≤ 2% XP parity |
| F5, F6 | `dev-tooling-and-parity-harness.md` | Interactions (aggregate vs exact) | Parity test runs in the determinism class |
| Reference | `sim/offline.py`, `tests/test_core.py::TestOfflineFastForward`, `tools/balance_sim.py` | — | Retrofit source |

## Acceptance Criteria

*QA-lead lens applied: one criterion per core rule and formula, boundary values included, cross-system criteria marked. **Logic** = automated unit test in `tests/unit/offline/`; **Integration** = automated test in `tests/integration/offline/`; **UI/Visual** = retained screenshot in `production/qa/evidence/`. `[PENDING: X]` needs a GDD or implementation that does not exist yet.*

- **AC-1 [Logic] (R1, F2)** — **GIVEN** a pending hand-off of `k` = 475,200 ticks (13 h 12 m), **WHEN** resolution completes, **THEN** `skip_ticks` is called once with `k` = 475,200 (not the credited 432,000) and the current `resolver_version`, and the core is no longer pending.
- **AC-2 [Logic] (R3, F1)** — **GIVEN** `hw_utc` = 1,800,086,400 and `now_utc` = 1,800,033,120, **WHEN** a gap of 33,120 s is resolved, **THEN** `trusted_s` = 0, `c` = 0, no sampled trip is run, and every due tick ≥ `at_tick` moves by exactly `k`.
- **AC-3 [Logic] (R3.4)** — **GIVEN** a save, **WHEN** the clock is set 24 h forward, the game opened and resolved, the clock set back to real time and the game reopened after 2 real hours, **THEN** the first resolution credits 12 h and the second credits 0, and `hw_utc` equals the forward time.
- **AC-4 [Logic] (R3.5)** — **GIVEN** a device clock 400 s ahead of a server reading and tolerance 300, **WHEN** the reading arrives, **THEN** `clock_skew_flag` is set and no member, wallet or storage value changes.
- **AC-5 [Logic] (R4, F2)** — **GIVEN** a 30 h gap, **WHEN** resolved, **THEN** `c` = 432,000 ticks, `u` = 648,000, and an upkeep slot due at hour 14 of the gap is shifted by `u` to hour 32 and fires live 2 h after the skip, not during the resolution. **GIVEN** an 11 h gap, **THEN** `u` = 0.
- **AC-5b [Logic] (R4, equal cap)** — **GIVEN** the same save and a 30 h gap resolved once with `flags = 0` (Free), once with `flags = 1` (Premium) and once on the PC build, **WHEN** resolved, **THEN** `cap_s`, `c`, `u` and every result are bit-identical, and no entitlement call is made.
- **AC-6 [Integration] (F4, F5, R14)** — **GIVEN** the standard 5-member PA 100 party on `g_z02_3` for 12 h (the cap), 5 seeds, **WHEN** run tick-exact and through this system, **THEN** mean XP differs by ≤ 2%, gold and stored units by ≤ 3%, and every unit went through `hand_in` (instrumented count equals the sum of `trips_i`).
- **AC-7 [Integration] (F5, threshold)** — **GIVEN** 200 seeds of gaps of `offline_threshold_s + 1` s, **WHEN** resolved, **THEN** mean XP per credited second is within ±5% of the exact long-run rate.
- **AC-8 [Logic] (R5)** — **GIVEN** a party 40% through a live trip with a bag of 12 units, **WHEN** a 2 h gap resolves, **THEN** after the skip the trip's remaining time, HP and bag are unchanged and its due ticks are shifted by `k`.
- **AC-9 [Logic] (R6)** — **GIVEN** a member dead with revive due at hour 3 of an 8 h window, **WHEN** resolved, **THEN** that member earns nothing in slices ending ≤ 3 h and earns in later slices; a member who never hunted earns nothing.
- **AC-10 [Logic] (F3, R7)** — **GIVEN** 8 h credited and a build due at 3 h declared rate-changing, **WHEN** the plan is built, **THEN** it has exactly 5 slices with boundaries at 2, 3, 5, 7 h; **GIVEN** `c` = 0, **THEN** 0 slices.
- **AC-11 [Integration] (R8, R9) [with Guild and buildings, Gold economy]** — **GIVEN** a queue of three builds totalling 3 h and an 8 h gap, **WHEN** resolved, **THEN** completion ticks, levels and ledger equal those of an 8 h tick-exact run with the same hunting income (Buildings AC-15), and the first live tick after the skip has no overdue timer.
- **AC-12 [Integration] (R10) [with Golden Boss]** — **GIVEN** a 12 h window crossing 12 slots, **WHEN** resolved, **THEN** Golden Boss R16 is called once, after the last slice, exactly the last 3 slots resolve in slot order (three 1406 events) and the report shows 9 missed; **GIVEN** a 30 h gap, **THEN** only slots inside the first 12 h are reported as crossed; **GIVEN** 2 crossed, **THEN** 2 resolved, 0 missed.
- **AC-13 [Logic] (R13, R17)** — **GIVEN** the same save and gap, **WHEN** resolved twice, and once with the work split across 1 frame and across 500 frames, **THEN** all results are bit-identical, every draw came from domain 5, and no two sampled trips shared a key (debug factory with `assert_unique_keys = True`).
- **AC-14 [Logic] (R16)** — **GIVEN** the process is killed at 50% of `Resolving`, **WHEN** restarted with the clock advanced 10 more minutes, **THEN** the resolution uses the same `gap_ordinal` and the result equals a clean resolution of the longer gap.
- **AC-15 [Logic] (R14)** — **GIVEN** a resolution with tax live, **THEN** every gold mint carries entry type 3 `offline_hunt`, is taxed per Gold economy R6, and no wallet, storage or member field was written except through `award` and `hand_in`.
- **AC-16 [Integration] (R15) [with Event bus, XP curve, CA/PA]** — **GIVEN** a member going from level 41 to 47 in a gap, **WHEN** the first live tick after the skip runs, **THEN** exactly one 3101, one 3102 for that member and one 2201 with `b` = 41, `c` = 47 are emitted in that tick and none afterwards, and CA/PA reveals every `level:N` with N ≤ 47.
- **AC-17 [Logic] (R11)** — **GIVEN** a resolved gap, **THEN** the summary record holds every R11 field and survives a save/load until dismissed or replaced.
- **AC-18 [Logic] (R6.4)** — **GIVEN** a group whose ground's content wave is no longer live, **WHEN** resolved, **THEN** no sampled trip runs on that ground.
- **AC-19 [Logic] (Edge Cases, second absence)** — **GIVEN** 40 s more absence accrues during `Resolving` of a 2 h gap, **THEN** after the skip it drains as exact ticks (≤ threshold) and no second resolution starts; at 10 min it becomes a second hand-off with `gap_ordinal` + 1.
- **AC-20 [Performance] (F6)** — **GIVEN** a 30 h gap (12 h credited) with one 5-member party, **WHEN** resolved on the mid-range Android reference device, **THEN** wall time ≤ 1 s and no frame exceeds `offline_frame_budget_ms` + 4 ms of resolver work; max-roster fixture ≤ 3 s on min-spec. `[PENDING: engine port, P1 device]`.
- **AC-21 [UI] (UI Requirements)** — **GIVEN** a 13 h 12 m absence, **WHEN** the report opens, **THEN** the headline reads "Away 13 h 12 m — the guild worked 12 h" with the cap icon and no Premium line, and a screenshot is retained; **GIVEN** a 4-minute absence, **THEN** a toast appears and no report. `[PENDING: Guild screens 39]`.
- **AC-22 [Integration] (Dev tooling)** — **GIVEN** `make test`, **THEN** AC-6 and AC-13 run in the determinism class and fail the build on violation.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Retrofit of `sim/offline.py`.** The reference credits gold directly, calls `auto_gear`, takes no cap, no clock policy, no timers, no backlog and draws from one shared `PCG32`. Migrating to R2–R17 changes outcomes once; re-run `tools/balance_sim.py` and GDD §4.3/§18 measurements afterwards. | Implementation story + Dev tooling (43) | Before Vertical Slice |
| OQ-2 | **RESOLVED (consistency-check 2026-11-16):** Sim core R6 adds the companion time entry `offline_credit {at_tick, c}`, written when this system calls `log_offline_credit(c)` once between the hand-off and `skip_ticks(k, resolver_version)` (signature unchanged). Original: replay needs the credited window `c` as well as `k`. | Sim core + Leaderboards (35) | Before Leaderboards design |
| OQ-3 | **Utility AI `view` outside a tick.** `choose_ground(group, view)` needs a view of ground occupancy; offline builds it from the groups chosen so far in the slice (paused live trips count as occupying their ground). Confirm with Utility AI R4. | Utility AI | Consistency check |
| OQ-4 | **PROVISIONAL: Party (13)** — assumes a stable saved `party_id` and that membership is readable at `at_tick`; temporary raid teams are not parties. | Party | When 13 is designed |
| OQ-5 | **RESOLVED (consistency-check 2026-11-16):** XP curve R4 steps 5–7 — `award(null, …)` applies the XP, emits nothing and returns `{discarded_milli, old_level, new_level}`; this system is the one permitted other emitter of 2201, once per member per absence. | XP curve | Closed |
| OQ-6 | **Conflict with Golden Boss PROVISIONAL-3** — Golden Boss assumes Offline "closes all sampled trips first" so the whole roster is home for R16. This GDD pauses live trips (R5) and treats their members as home for backlog eligibility without closing the trip. Also: a raid in progress at hand-off is assumed finished by Golden Boss at `at_tick`, outside the backlog. GDD §6.13 says backlog raids are "mô phỏng thống kê"; Golden Boss R16 uses its exact resolver — this GDD conforms to Golden Boss. **RESOLVED (consistency-check 2026-11-16):** Golden Boss PROVISIONAL-3 and R16 now adopt the pause rule (paused-trip members are home for eligibility, trip untouched). | Golden Boss + Offline | Closed |
| OQ-7 | **RESOLVED (consistency-check 2026-11-16):** Zones R15 now returns `bags[i]` (and F10 no longer scales gold); Items `hand_in` returns the income without crediting, and this system credits it as `offline_hunt` by the Zones R8 split (R14) — no entry-type override is needed. Zones OQ-7 and Items OQ-6 closed with the rotation rule (F4). | Zones + Items | Closed |
| OQ-8 | **RESOLVED (user decision 2026-11-16):** equal offline cap (12 h) for every player on ranked play; Premium is convenience only. R4 reads no entitlement, `offline_cap_extended` is retired from Entitlement R8, and `offline_cap_premium_h` is deprecated. Original: assumed a local `is_premium()` choosing between an 8 h Free and 24 h Premium cap. | — | Closed |
| OQ-9 | **PROVISIONAL: Member state machine (41), Retention (16)** — assumes recovery and departure timers are anchored due ticks registered as elapsing timers (R8). Mood, loyalty and hunger offline are not modelled at MVP. | Member state machine, Retention | When 41/16 are designed |
| OQ-10 | **Consumables offline.** Potions and food (Gold economy S3, GDD §19.2 ≈ 23% of income) are not bought by sampled copies today. Offline income would then exceed live income by that sink. Must the sampled copy price consumables, or should Offline debit a per-trip consumable cost? | Gold economy + Zones | Before Vertical Slice balance pass |
| OQ-11 | **Freezing uncredited time vs. "real time passes".** R4 freezes builds and upkeep beyond the cap (exploit-safe, and upkeep is not charged for unworked time). The alternative lets builds finish in real time. Economy-designer and game-designer to confirm against Guild and buildings Player Fantasy 1. | game-designer + economy-designer | Design review |
| OQ-12 | **CD-GDD-ALIGN NOT ASSESSED**: no game pillars or concept doc. Re-run once `game-pillars.md` exists. | creative-director | When pillars exist |
| OQ-13 | **Index scope.** GDD §6.11 says NPC guilds grow "theo thời gian thực/offline" and GDD §6.12 mentions "hệ số thành phần đội (10)". Both are Full Vision / Party concerns; NPC guild growth offline is left to Jianghu (17) as an elapsing timer owner. Confirm no further scope here. | Producer | Before Full Vision |
