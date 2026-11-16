# XP and Level Pacing Curve

> **Status**: In Design
> **Author**: user + Claude (design-system)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no game pillars written yet)
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against; re-run once pillars are written

## Summary

The XP and level pacing curve decides how much XP a guild member needs for each level, how high each rebirth tier lets them climb, and the single `award` call through which every source of XP turns into levels. It makes the first levels fast and each rebirth slower, so a new disciple grows within the first sitting and a veteran's progress feels earned. It exists because this curve is the game's main pacing control and must stay data-driven and identical in Python and GDScript.

> **Quick reference** — Layer: `Core` · Priority: `MVP` · Key deps: `Data layer and content pipeline, Sim core and tick loop, Event bus and history log, Member model, Rebirth and Ascension`

## Overview

The XP and level pacing curve decides how long it takes a guild member to grow. It owns the XP a member needs to reach each next level, the level cap that each rebirth tier allows, and the single rule that turns earned XP into levels and announces each level-up. The curve is fast in the first levels, so a new recruit feels progress within the first hours, and it slows with every rebirth, so a member at rebirth 5 needs 18 times the XP of a first-life member for the same level. The player never calls this system. They feel it as the pace of the whole game: how soon a recruit reaches the joining level, how many days a team takes to reach level 100, and how heavy each rebirth feels. Other systems pay XP in (hunting, quests, buffs) through one award call, and read levels out (Member model, Schools, Skills, Rebirth); none of them keeps its own copy of the curve. Every number is data-driven, because this curve is the main balance knob of the game and has to be re-tuned after real skills and enhancement shift the pace (GDD §4.3, §20).

*Scope note:* this system applies only the bonuses that belong to the member (the PA growth multiplier and the rebirth bonuses). How much XP a kill, a party or a buff pays is decided by the system that owns that source (Detailed Design R5).

## Player Fantasy

**The fantasy has two halves: a fast start that makes the player attached, and a long road that makes the commitment feel earned.**

*Watching them grow up.* The player hires a recruit in the morning and, by lunch, that recruit has reached level 10 and joined a school. The first levels come quickly and reliably (`early(L)` starts at 8% of the base cost), so a new face becomes "my disciple" within the first sitting. The player is not asked to do anything for this to happen. They return, and the guild has moved on without them.

*A long road, honestly priced.* Later the same disciple is at level 180, and the next level takes days. The player sees that cost plainly and decides to keep going, because every rebirth pays them back with a higher cap and new content (GDD §6.10). The slowdown is the price of a bigger step, not a punishment. A first-life member needs 1 times the base XP, and a fifth-rebirth member needs 18 times, so the player feels the weight of "this one has come a long way".

**What the design owes the player.** Early growth must be fast and visible, so the level-up has to be an event the interface can show (Realtime world view, Guild screens). Every slowdown must come with a stated reward at the rebirth that causes it. The pace has to stay predictable, so a player who leaves for a day can guess how far the guild has come.

*Pillar anchor:* none. The project has no game pillars yet, so this section is anchored to GDD §1 ("thành viên mạnh hơn") and §4.3 ("nhanh đầu game, chậm dần theo chuyển sinh"). Re-check it against the pillars when they exist.

## Detailed Design

### Core Rules

**R1: One owner of level and XP.** A member carries three progress fields: `level` (int), `xp_milli` (int, XP in thousandths) and `rebirth` (int, 0–5). Member model (8) stores them. This system is the only writer of `level` and `xp_milli`, and it writes them only through `award` (R4) and `init_progress` (R9). Rebirth and Ascension (23) is the only writer of `rebirth`. No other system keeps a copy of the curve or computes a level from XP.

**R2: The curve is an integer table built at boot.** When the Data layer is sealed, this system builds three read-only tables and never changes them during play:
- `need_milli[r][L]`: the XP, in thousandths, to go from level L to L+1 for a member at rebirth r (F1). Built for r in 0–5 and L in 1–199.
- `cap[r]`: the level cap at rebirth r (R3).
- `bonus_ppm[r]` and `growth_bonus_ppm[r]`: the cumulative rebirth XP bonuses at tier r (R5).

The formula uses float `pow()` once per cell at boot, then rounds to an integer (F1). The runtime never calls `pow()`. The hash of the three tables is recorded in the parity vectors (F4), so a Python and GDScript build that disagree on one cell are caught before play.

**R3: Level caps come from the rebirth table.** `cap[0]` is the `req_level` of rebirth row 1 (100 today). For r in 1–5, `cap[r]` is the `new_level_cap` of row r (120, 140, 160, 180, 200). The validator enforces `cap[r]` = `req_level` of the next row, so a member who reaches the cap is exactly the one who may rebirth (or ascend). The caps move out of `sim/data.py` (`LEVEL_CAP`, hardcoded today) into data.

**R4: `award(ctx, member_id, base_milli, source_id)`.** The single way XP enters the game. `ctx` is the calling handler's Sim core context, which `award` uses to emit events (step 5).
1. `base_milli` is an integer ≥ 0. A negative or non-integer value is a caller bug: the call is refused with error 2201 and the member is unchanged. There is no XP loss in this game.
2. Member-side multipliers are applied here (F2): the PA growth multiplier and the rebirth bonuses. The caller has already applied everything source-side (R5).
3. The effective XP is added to `xp_milli`. While `level < cap[rebirth]` and `xp_milli ≥ need_milli[rebirth][level]`, the need is subtracted and `level` rises by 1. Any number of levels can be gained in one call.
4. If the member reaches `cap[rebirth]`, `xp_milli` is set to 0 and the rest is discarded. The call returns the amount discarded, so the caller can report it.
5. Events are emitted once, after the loop (R6), with `ctx.emit` from the caller's context. A caller without a live handler context (the offline resolver) passes `ctx = null`: the award is applied identically and **no event is emitted**. Offline progress (31) then emits one 2201 per member whose level changed over the whole absence, on this system's behalf, with `b` = level before and `c` = level after (Offline R15); this is the only other emitter this system permits for 2201 (OQ-4 resolved).
6. **Skills hook.** Before returning, `award` calls the one listener registered at boot by Skills (21), `on_xp_awarded(member_id, effective_milli, new_level)`, synchronously, with `effective_milli` the amount from step 2 **before** any cap discard (step 4) and `new_level` the level after step 3. It is called on every award, live or offline (`ctx` may be null), in the same order as the awards (R10). The listener must not call `award`.
7. `award` returns `{discarded_milli, old_level, new_level}`. *(Steps 5–7: consistency-check 2026-11-16, answering Skills OQ-2 and Offline OQ-5.)*

**R5: Who applies which multiplier.**
- *Member-side, applied by `award`:* the PA growth multiplier (`growth_mult`, F2) and the member's cumulative rebirth bonuses (`xp_pct`, `growth_bonus` from `rebirth.csv`). These are permanent properties of the member.
- *Source-side, applied by the caller before it calls `award`:* kill XP from the monster and the level-difference penalty (Hunt, 11), the party bonus (Party, 13), and timed buffs such as the feast and the Library of Wisdom (the system that owns the buff; OQ-3). These depend on the roster, the monster or the clock, which this system cannot see.

**R6: Events.** This system registers the block 2200–2299 with the Event bus (`xp_event_type_block`). It emits:
- **2201 `member_level_up`** (`a` = member_id, `b` = old level, `c` = new level, `d` = rebirth): once per `award` that changes the level, never once per level gained. An offline award can gain dozens of levels for each member, and one event per level would break the Event bus's per-tick budget. The event is not logged.
- **2202 `member_level_capped`** (`a` = member_id, `b` = cap level, `c` = rebirth): once, in the award that first reaches the cap. It is logged and a milestone, with `subject_slot` 1. This is the history entry for "this disciple has gone as far as they can".

Subscribers must use `c` (new level) and treat `b` to `c` as a range. Schools (20) already compares with `level ≥ school_join_level`, so a jump from level 8 to 12 still joins the member (flag: Schools assumed one event per level; see Cross-References).

**R7: Level never falls and XP never goes below 0.** Nothing in this system lowers `level` or `xp_milli`. A rebirth keeps both: the member's level stays where it was, `xp_milli` is 0 because they were capped, and only `rebirth`, `cap` and the cost multiplier change. GDD §4.3 measures "lv100→120" as its own stretch, which confirms that the level is kept.

**R8: The curve takes no randomness and no clock.** `award` is a pure function of the member's three fields, the three tables and its arguments. It does not use the RNG, and it is safe to call from the live tick or the offline resolver with the same result.

**R9: `init_progress(member_id, level, rebirth)`.** Called by Member model when a member is created or loaded from a migrated save. It sets `xp_milli` to 0 and accepts a level from 1 to `cap[rebirth]`. A level outside that range is refused with error 2202. Recruitment (15) decides what level a recruit arrives at, and this system only validates it.

**R10: Calls arrive in a fixed order.** `award` calls in the same tick are applied in the order they were made. The order matters only for which call is credited the 2202 event, and for nothing else, because XP is additive and the loop is order-independent within one member.

### States and Transitions

A member is in exactly one of two progress states, decided by `level` and `cap[rebirth]`.

| State | Condition | `xp_milli` | `award` does |
|-------|-----------|------------|--------------|
| `Growing` | `level < cap[rebirth]` | 0 ≤ xp < `need_milli` | Adds XP, may level up |
| `Capped` | `level = cap[rebirth]` | always 0 | Discards the XP and returns it as overflow |

| From | To | Trigger |
|------|----|---------|
| `Growing` | `Growing` | `award` that gains 0 or more levels but does not reach the cap |
| `Growing` | `Capped` | `award` that reaches `cap[rebirth]`; emits 2201 and 2202 |
| `Capped` | `Growing` | Rebirth (23) raises `rebirth`; the cap rises by 20 levels |
| `Capped` | `Capped` | `award`; no change, overflow returned |

There is no transition out of `Capped` at rebirth 5. The member stays capped until Ascension (23) changes them into an Elder, and Elders do not earn XP, so Hunt does not call `award` for them (their state is owned by Member state machine, 41).

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|--------|-----------|---------|----------|------------------------|
| Data layer (3) | in | `config` curve keys, `sim_params` kill-XP keys (read by Hunt), `rebirth` rows (caps, XP bonuses) | — | Data layer owns loading and validation; this system owns the meaning of the curve keys |
| Member model (8) | both | Reads and writes `level`, `xp_milli`, reads `rebirth`, `pa` | `award`, `init_progress`, `cap[r]` | Member model owns storage; this system owns the values (same pattern as Schools R2) |
| Hunt (11) | in | `award(member, base_milli, source_id)` with kill XP already computed | Overflow returned | Hunt owns kill XP and the level-difference penalty |
| Party (13) | in | The party bonus is applied by Hunt before the call | — | Party owns the bonus |
| Rebirth and Ascension (23) | in | Writes `rebirth`; reads `cap[r]`, and whether a member is `Capped` | `rebirth.csv` bonus values read at boot | Rebirth owns the rebirth rules; this system owns the cap and the cost multiplier |
| Schools (20) | out | — | Event 2201 (new level) | Schools evaluates `join_due` on the new level |
| Skills (21) | out | — | `level`, read from Member model; `on_xp_awarded(member_id, effective_milli, new_level)` per award (R4 step 6) | Skills owns `lv_req` checks and the listener; this system owns when it is called |
| Offline progress (31) | in | `award` with the accumulated base amount per member | Overflow returned | Offline owns the aggregate; this system gives the same result as a tick-by-tick run for a given total (see Edge Cases) |
| Event bus (42) | out | — | `register_type` for block 2200, `ctx.emit` of 2201, 2202 | Event bus owns delivery; this system owns the two types |
| Realtime world view (38), Guild screens (39) | out | — | Level-up and capped events, `level`, `cap`, XP fraction | Presentation reads, never writes |

*Provisional assumptions:* Member model (8), Hunt (11), Rebirth (23) and Offline (31) have no GDD yet. The call names `award`, `init_progress` and `cap[r]` are this GDD's proposal for their contracts.

## Formulas

All four formulas run in integers at play time. Only F1 uses float `pow()`, once per table cell at boot (R2). The values are the project's current numbers (GDD §4.3, `data/config.csv`), reproduced by the reference script `sim/formulas.py` (`xp_need`).

### F1: `need_milli`

The need_milli formula is defined as:

`need_milli(r, L) = floor( 1000 × xp_need_coef × L ^ xp_need_exp × early(L) × xp_rebirth_mult[r] + 0.5 )`

with `early(L) = xp_early_floor + (1 − xp_early_floor) × min(1, L / xp_early_end)`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| r | int | 0 – 5 | calculated | The member's rebirth tier |
| L | int | 1 – 199 | calculated | The member's current level; the result is the XP to reach L + 1 |
| xp_need_coef | int | 1 – 10,000 (100 today) | data file (`config.csv`) | Base XP scale |
| xp_need_exp | float | 1.0 – 3.0 (1.7 today) | data file (`config.csv`) | How steeply the need grows with level |
| xp_early_floor | float | 0.01 – 1.0 (0.08 today) | data file (`config.csv`) | Share of the base cost charged at level 0; 1.0 turns the ramp off |
| xp_early_end | int | 1 – 200 (40 today) | data file (`config.csv`) | The level at which the early ramp ends and the cost becomes full |
| xp_rebirth_mult[r] | int | 1 – 1,000 (1, 3, 5, 8, 12, 18 today) | data file (`config.csv`) | Cost multiplier per rebirth tier; strictly increasing |
| 1000 | constant | — | constant | Converts XP to the integer thousandths the game stores |

**Output Range:** 10,300 (level 1, rebirth 0) to 14,565,410,703 (level 199, rebirth 5) with today's data, both as milli-XP. Always ≥ 1 and strictly increasing in L for a given r (checked for all 6 × 199 cells), so the level-up loop in R4 always ends. The largest cell is far below the int64 maximum of 9.2×10¹⁸.

**Example:** r = 0, L = 10: `early(10) = 0.08 + 0.92 × 0.25 = 0.31`; `100 × 10^1.7 = 5,011.87`; `5,011.87 × 0.31 × 1 = 1,553.68` XP, so `need_milli = 1,553,680`. r = 1, L = 100: `early = 1.0`, `100 × 100^1.7 × 3 = 753,565.93` XP, so `753,565,929`.

**Why this shape.** The `L^1.7` term makes late levels cost much more than early ones. The `early(L)` ramp makes the first levels cheap (level 1 costs 10.3 XP, a tenth of the unramped 100), so the first sitting is full of level-ups, which delivers the "watching them grow up" half of the fantasy. The rebirth multiplier is the "long road": it is a table, not a formula, so a designer can bend one tier without moving the others.

### F2: `effective_milli`

The effective_milli formula is defined as:

`pa_eff = min( pa_max, floor( pa × (1,000,000 + growth_bonus_ppm[r]) / 1,000,000 ) )`
`growth_ppm = growth_base_ppm + floor( growth_pa_ppm × pa_eff / pa_max )`
`step1 = floor( base_milli × growth_ppm / 1,000,000 )`
`effective_milli = floor( step1 × (1,000,000 + bonus_ppm[r]) / 1,000,000 )`

The two steps are separate on purpose. Each is floored on its own, so no intermediate exceeds 1.5×10¹⁸.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| base_milli | int | 0 – 2⁴⁰ (1,099,511,627,776) | calculated | The caller's XP, already multiplied by its source-side bonuses (R5); above 2⁴⁰ the call is refused (error 2201) |
| pa | int | 0 – 200 | calculated (Member model) | The member's hidden potential (PA), fixed at birth |
| pa_max | int | 200 | data file (`config.csv`) | The top of the PA scale |
| growth_base_ppm | int | 0 – 2,000,000 (600,000 today) | data file (`config.csv`, today `growth_mult_base` = 0.6) | The growth multiplier at PA 0, in millionths |
| growth_pa_ppm | int | 0 – 2,000,000 (800,000 today) | data file (`config.csv`, today `growth_mult_pa` = 0.8) | How much PA adds across its full range, in millionths |
| growth_bonus_ppm[r] | int | 0 – 500,000 (0, 0, 50,000, 50,000, 50,000, 50,000) | data file (`rebirth.csv`, `growth_bonus`, cumulative by tier) | Rebirth bonus to effective PA, in millionths (+5% from rebirth 2) |
| bonus_ppm[r] | int | 0 – 1,000,000 (0, 100,000, 100,000, 100,000, 200,000, 200,000) | data file (`rebirth.csv`, `xp_pct`, cumulative by tier) | Rebirth XP bonus, in millionths (+10% at rebirths 1 and 4) |

**Output Range:** `growth_ppm` runs from 600,000 (PA 0) to 1,400,000 (PA 200). `effective_milli` is at most about 1.69× `base_milli` (PA 200 at rebirth 4–5: 1.4 × 1.2), at least 0.6×, and 0 when `base_milli` is 0. The largest possible intermediate is 2⁴⁰ × 1,400,000 ≈ 1.54×10¹⁸, below the int64 maximum.

**Example:** `base_milli` = 10,000 (10 XP), PA 100, rebirth 2: `pa_eff = min(200, floor(100 × 1.05)) = 105`; `growth_ppm = 600,000 + floor(800,000 × 105 / 200) = 1,020,000`; `step1 = 10,200`; `effective_milli = floor(10,200 × 1,100,000 / 1,000,000) = 11,220` (11.22 XP). The same call at rebirth 0 gives 10,000.

**Boundaries checked.** PA 0 gives 0.6×, so a weak member still progresses. PA 190 or more at rebirth ≥ 2 reaches the `pa_eff` cap of 200, so the +5% is inert for the best members (accepted; the rebirth reward is felt by the rest). Both growth keys move out of float into integer `_ppm` keys (today `growth_mult_base` and `growth_mult_pa`); the Data layer's `ppm` type is meant for probabilities up to 1,000,000, so these two use plain `int` (OQ-2).

### F3: `cumulative_need_milli`

The cumulative_need_milli formula is defined as:

`cumulative_need_milli(r, a, b) = Σ need_milli(r, L) for L = a … b − 1`

It is used by the balance gate (Dev tooling 43) to compare measured hours against the pacing bands, and by Rebirth (23) to show "XP left to the cap". It is not used by `award`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| r | int | 0 – 5 | calculated | Rebirth tier |
| a | int | 1 – 199 | calculated | The starting level |
| b | int | a – `cap[r]` | calculated | The ending level (exclusive of the XP to leave it) |

**Output Range:** 0 when `a = b`. With today's data: level 1 → 10 at rebirth 0 costs 3,855,180 milli-XP (3,855 XP); level 1 → 100 costs 8,983,258,280 (about 8.98 million XP); each later tier costs 17.6 M (rebirth 1, levels 100 → 120), 39.0 M, 79.7 M, 147.9 M and 268.2 M XP. The sum is below 1.5×10¹¹ for any range, far inside int64.

**Example:** `cumulative_need_milli(1, 100, 120)` = 17,614,542,112 milli-XP (17,614,542 XP), the cost of the first rebirth stretch.

### F4: `progress_table_hash`

The progress_table_hash formula is defined as:

`progress_table_hash = SHA-256( concat( i64_be(need_milli[r][L]) for r = 0…5, L = 1…199 ‖ concat( u16_be(cap[r]) ‖ u32_be(bonus_ppm[r]) ‖ u32_be(growth_bonus_ppm[r]) ) for r = 0…5 ) )`, hex-encoded lowercase.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| need_milli[r][L] | int | F1 | calculated | The built need table, in order (r outer, L inner) |
| cap[r] | int | 1 – 200 | calculated | The level cap per tier (R3) |
| bonus_ppm[r] | int | F2 | calculated | Cumulative XP bonus per tier |
| growth_bonus_ppm[r] | int | F2 | calculated | Cumulative PA bonus per tier |

**Output Range:** a 64-character hex string over a fixed 9,612-byte input (1,194 × 8 + 6 × 10 bytes). It is recorded in the parity vectors (Dev tooling 43) and logged at boot. A port whose hash differs from the vector fails the parity gate, which is how a last-bit `pow()` difference between Python and GDScript is caught.

**Example:** with today's data the reference script gives `fcc9532fd641d0898a20de6837044c4190dd94327b492602ce0f78e56be301b8`. This is the first parity vector for this system; any change to a curve key or to `rebirth.csv` changes it on purpose.

**Registry candidates (Phase 5):** formulas `need_milli`, `effective_milli`, `progress_table_hash` (and `cumulative_need_milli`); constants `xp_event_type_block` = 2200, `award_base_max_milli` = 2⁴⁰ (1,099,511,627,776).

## Edge Cases

Error codes 2201–2204 are returned to the caller. They are not events and not sim failures, so the tick continues. The caller decides what to do with them. Every refused call leaves the member unchanged and emits nothing.

### A. Award inputs

- **If `base_milli` is 0**: the call runs the level loop and applies the cap rule, so it settles anything already owed (see C). It emits events only if a level is actually gained, and otherwise changes nothing.
- **If `base_milli` is negative, not an integer, or above 2⁴⁰ (1,099,511,627,776)**: refused with 2201. There is no XP loss mechanic, and a value above 2⁴⁰ would risk int64 overflow in F2.
- **If `member_id` does not exist**: refused with 2203, with nothing emitted. Member model owns existence; this system reports it.
- **If the member's `pa` is outside 0–200**: refused with 2204. PA is fixed at birth, so a value outside the range is a corrupt save, and clamping would hide it.
- **If the effective XP rounds down to 0** (for example 1 milli at PA 0): the XP is dropped with no carried remainder. Each of the two floors in F2 loses less than 1 milli-XP per call, a negligible amount against 10,300 milli at the cheapest level.

### B. Levels and cap

- **If one award is large enough to gain several levels**: the loop gains them all in one call and emits one 2201 with `b` = old level and `c` = new level. Subscribers treat it as a range.
- **If an award crosses the cap**: the member stops at `cap[rebirth]`, `xp_milli` becomes 0, the surplus is discarded and returned to the caller, and the call emits 2201 then 2202, in that order, in the same tick. If the member started at one level below the cap, 2201 still fires with `b` = cap − 1 and `c` = cap.
- **If a `Capped` member is awarded XP**: nothing changes, nothing is emitted and the whole effective amount is returned as overflow.
- **If a member reaches a cap more than once** (after each rebirth the cap rises): 2202 fires each time, once per tier, so the history shows each stretch of the road.

### C. Rebirth, saves and data

- **If Rebirth (23) raises `rebirth`**: `cap` rises (by 20 levels today), the member becomes `Growing` at the same level with `xp_milli` 0, and the need now comes from the next tier's row. No XP is awarded or lost, and no event is emitted by this system.
- **If a loaded member has `level` above `cap[rebirth]`** (a hand-edited save, or a patch that lowered a cap): `init_progress` is refused with 2202. This system does not clamp the level. Recovery (reset, clamp or reject the save) belongs to Local save and migration (6) (OQ-5).
- **If a data patch lowers a level's need below a member's stored `xp_milli`**: the member is not changed on load. They gain the level at their next `award`, and a zero-XP award is enough (see A), so an owner can settle every member once after a patch.
- **If the validator finds any of these, the build fails (ERROR) and the game never boots on bad data**:
  - `xp_early_end` below 1 (it would divide by zero), or `xp_early_floor` outside (0, 1];
  - `xp_rebirth_mult` not strictly increasing, or any `xp_rebirth_mult_r` key missing (the Python reference silently defaults a missing key to 1.0; the port must not, because a typo would make a whole tier free);
  - a broken cap chain (`cap[r]` ≠ the next row's `req_level`);
  - an unparseable or negative `xp_pct` or `growth_bonus` in `rebirth.csv`;
  - any need cell above 2⁶², or a table that is not strictly increasing in L.

### D. Offline and event volume

- **If Offline (31) awards one aggregate amount instead of many single awards**: the result equals the sum of the single awards plus at most 2 milli-XP per skipped call, because the floors in F2 happen once instead of many times. At a level boundary this can differ from a live run by one level at most. Offline's parity tolerance owns the exact bound.
- **If many members level up in the same tick**: this system emits at most 2 events per awarded member per tick (2201, plus 2202 at the cap). Awards come at the end of a hunt trip, so the load is a fraction of the Event bus's per-tick budget. Only 2202 is logged, and it declares its peak ring rate when it registers (R6), so history size is bounded by the Event bus's own caps.
- **If a caller awards the same kill twice**: both awards are applied. This system cannot tell, because it has no kill identity. Hunt (11) owns the once-per-kill guarantee.
- **Degenerate strategy check**: nothing inside this system can be repeated for unbounded XP. XP never reduces the need, the need table is fixed at boot, and all sources are paid by other systems. The most the member-side multipliers give is 1.69× (F2), for PA 200 at rebirth 4–5.

## Dependencies

### Upstream (this system depends on)

| System (#) | Hard / soft | Interface | What this system takes |
|---|---|---|---|
| Data layer and content pipeline (3) | Hard | `config` curve keys, `rebirth` rows (`req_level`, `new_level_cap`, `rewards`), the typed-table load and validator (R8) | Every curve number and cap. The Data layer GDD already lists this system downstream ("Curve parameters, level caps"), so the two-way record holds |
| Sim core and tick loop (1) | Hard | `ctx.emit` in the caller's handler context; the boot-time `seal()` after which the tables are frozen | Where events are emitted and when the tables are built. This system registers no tick handler of its own |
| Event bus and history log (42) | Hard | `register_type` for block 2200–2299; `ctx.emit` | Delivery of 2201 and 2202 and the history entry for 2202. The Event bus lists "feature systems that emit (8–30, 41)", which includes this one |
| Member model (8) | Hard (provisional) | Storage of `level`, `xp_milli`, `rebirth`; the member's `pa` | The member record this system reads and writes. Member model is undesigned (its index row lists this system upstream) |
| Rebirth and Ascension (23) | Hard (provisional) | The writer of `rebirth`; the rebirth rows' `xp_pct` and `growth_bonus` | When a member's tier changes, and the bonus values |

Deterministic RNG (2) is **not** a dependency. No rule in this system draws (R8).

### Downstream (systems that depend on this one)

| System (#) | Hard / soft | Interface | What it gets |
|---|---|---|---|
| Member model (8) | Hard | `init_progress`, the field rules (R1, R7) | The only legal way to set level and XP |
| Zones, grounds, monsters and hunt trips (11) | Hard | `award` with kill XP computed | The single XP entry point, and the overflow it returns |
| Rebirth and Ascension (23) | Hard | `cap[r]`, `Capped` state, `cumulative_need_milli` (F3) | When a member may rebirth, and the cost of the next stretch |
| CA/PA and traits (9) | Hard | `cap[r]` | The level scale `l_norm = level / cap` in the CA formula |
| Schools (20) | Soft | Event 2201 (new level `c`) | The trigger for `join_due`. Schools assumed one event per level gained; this system emits one per award, which Schools' `≥` test handles (see Cross-References) |
| Skills (21) | Hard | `level`, read through Member model; the R4 step 6 listener | The `lv_req` check for each skill; skill XP from member XP (Skills OQ-2) |
| Offline progress (31) | Hard | `award` with an accumulated amount | The same result as a live run, up to the F2 rounding (Edge Cases D) |
| Quests and achievements (25) | Soft | `award` with a quest's XP reward | The XP sink for quest rewards |
| Recruitment (15) | Soft | `init_progress` range check | A valid arrival level |
| Dev tooling and parity harness (43) | Hard | `progress_table_hash` (F4); `cumulative_need_milli` (F3) | The parity vector and the balance gate's XP-to-hours conversion |
| Realtime world view (38), Guild screens (39) | Soft | Events 2201 and 2202; `level`, `cap`, `xp_milli`, `need_milli` | The level-up pop, and the XP bar |
| Jianghu Chronicle and AI text (36) | Soft | Event 2202 (milestone) | A story beat when a disciple reaches the end of a road |

"Hard" means the dependent cannot meet its own acceptance criteria without this system.

**Bidirectional status.**
- Data layer (3): lists this system. ✓
- Event bus (42): covers it under "feature systems that emit". ✓
- Schools (20): lists this system as a soft upstream, assuming one event per level. **Needs an edit**: its provisional assumption 1 and the dependency row should read "one level-up event per award, carrying the old and new level" (follow-up F-1).
- Systems index row 22 lists only the Data layer. It should also list **Sim core (1)** and **Event bus (42)**, which are hard upstream here (follow-up F-2).
- Sim core (1) does not list individual features, and does not need to.
- All other systems above are undesigned and must list this system when they are designed.

**Provisional assumptions about undesigned systems.**
1. Member model (8) stores `level`, `xp_milli` and `rebirth`, exposes `pa`, and calls `init_progress` on creation and load.
2. Hunt (11) computes kill XP and the level-difference penalty, and the party bonus, before calling `award`, and tolerates the 2201–2204 returns.
3. Rebirth (23) writes `rebirth` and does not touch `level` or `xp_milli`.
4. Offline (31) can call `award` for a gap without a handler context (OQ-4).
5. Timed XP buffs (feast, Library of Wisdom) are applied by their owner before `award` (OQ-3).

## Tuning Knobs

Every knob lives in a data file and is read at boot (R2), so a change needs a rebuild of the tables and moves `progress_table_hash` (F4) on purpose. After any change, regenerate the parity vector and re-run the balance gate (Dev tooling 43). The pacing the knobs produce today (GDD §4.3, measured with a standard 5-member party at PA 100 playing 24 hours a day) is: level 100 in about 71 hours, then about 69 hours, 4.6 days, 8.5 days, 13.3 days and 21.3 days for the later stretches, 54 days in all. A real player takes 2 to 4 times longer because of the offline cap.

| Knob | File | Today | Safe range | Too high | Too low |
|------|------|-------|------------|----------|---------|
| `xp_need_coef` | `config.csv` | 100 | 20 – 500 | Every level slows in proportion; 200 doubles all times, so level 100 takes about 6 days | Every level speeds up; 20 makes level 100 in about 14 hours and the fantasy of a "long road" disappears |
| `xp_need_exp` | `config.csv` | 1.7 | 1.4 – 2.0 | Late levels dominate: 2.0 multiplies the need by L^0.3, which is 2.0× at level 10, 4.0× at level 100 and 4.9× at level 199, so the long road gets far longer than the start | The curve flattens: 1.4 divides the need by the same factor, so late levels feel the same as early ones and rebirths lose their weight |
| `xp_early_floor` | `config.csv` | 0.08 | 0.03 – 0.25 | The early ramp fades: 1.0 turns it off and the first levels cost the full amount (level 1 costs 100 XP, not 10.3) | Levels 1 – 5 become near-instant (floor 0.01 costs about 3.5 XP at level 1), so the first sitting is only level-up noise |
| `xp_early_end` | `config.csv` | 40 | 10 – 80 | The cheap ramp lasts too long and the cost then jumps; at 80, level 40 still costs only 54% of full price | The ramp ends before the player has made a choice; at 10, school joining (level 10) is the last cheap level |
| `xp_rebirth_mult[0..5]` | `config.csv` | 1, 3, 5, 8, 12, 18 | strictly increasing, each tier 1.2 – 2.0× the last | A steep tier makes its stretch a wall; 18 → 30 stretches the last 20 levels to about 35 days | A shallow tier makes a rebirth feel like nothing; equal values are refused (strictly increasing) |
| `growth_base_ppm` | `config.csv` (today `growth_mult_base`) | 600,000 | 400,000 – 1,000,000 | A weak-PA member grows as fast as a strong one, and PA stops mattering | A weak member crawls; 0 would stop a PA 0 member from ever levelling |
| `growth_pa_ppm` | `config.csv` (today `growth_mult_pa`) | 800,000 | 0 – 1,200,000 | PA dominates XP speed; a PA 200 member levels many times faster than PA 0 | At 0 every member levels at the base rate and PA is only a cap on CA |
| `pa_max` | `config.csv` | 200 | fixed at 200 (matches the CA scale) | — | — |
| `xp_pct` per rebirth tier | `rebirth.csv` `rewards` (cumulative) | +10% at rebirths 1 and 4 | 0 – 25% per tier | A big bonus undoes the rebirth multiplier; +100% halves a tier's cost | 0 removes the "+XP" promised in GDD §6.10 |
| `growth_bonus` per rebirth tier | `rebirth.csv` `rewards` (cumulative) | +5% effective PA at rebirth 2 | 0 – 10% | Effective PA reaches the 200 cap early and the bonus goes inert | 0 removes the reward the GDD promises for rebirth 2 |
| Cap chain (`req_level`, `new_level_cap`) | `rebirth.csv` | 100, 120, 140, 160, 180, 200 | each step 10 – 40 levels; the last is 200 | Longer stretches stretch the pacing (see the `xp_rebirth_mult` row) | Short stretches make a rebirth cheap; the CA scale (`ca_max` 200) still sets the top |

**Knobs that interact.**
- `xp_need_coef` and `xp_rebirth_mult[r]` multiply each other. Doubling the coefficient and halving every multiplier gives the same table, so change one at a time and record which.
- `xp_early_floor` and `xp_early_end` are both inert if `xp_early_floor` = 1.0.
- `growth_pa_ppm` and `growth_bonus` both matter only below PA 190; at the top of the scale the `pa_eff` cap makes the bonus inert (F2).
- The kill-XP knobs (`xp_kill_coef`, `xp_kill_exp`) and the level-difference keys are owned by Hunt (11), and `party_xp_per_member`, `party_buffer_bonus` and `party_tank_bonus` by Party (13). They set how fast XP arrives, while this table sets how much is needed. The **pace** is the ratio of the two, so recalibrate `xp_kill_coef` first (GDD §20 says to do this after real skills), and touch this table only if the shape is wrong.
- `school_join_level` (default 10) is owned by Schools (20). It must stay below `cap[0]`.

**Not knobs.** `1000` (milli per XP), `1,000,000` (ppm scale) and the award ceiling 2⁴⁰ are constants of the representation. Changing them changes the save format and needs a `sim_version` bump (Sim core R12).

## Visual/Audio Requirements

This system owns no rendering or sound. It sets three requirements for the presentation systems:
- **A level-up is a beat, not a number.** Event 2201 deserves a short visual pop on the member and a soft audio cue in the Realtime world view (38) and Audio (40). The cue is suppressed during catch-up (Sim core R15), and several level-ups in one frame collapse into one pop per member.
- **Reaching the cap reads differently from levelling.** Event 2202 gets a distinct, calmer cue ("this disciple has gone as far as they can"), because it is the signal that a rebirth is available.
- **No state by colour alone.** A capped member shows an icon or text ("Capped"), not only a recoloured bar (accessibility floor).

No art bible exists, so no art-bible principle is cited. The presentation systems own the cue design.

## Game Feel

Not a feel system. Its timing promises:
- A level-up emitted in tick N is visible to the player in the same frame's P6 delivery. The event is stamped and delivered in the tick it was emitted, with no delay beyond that.
- A level-up never appears twice, and an offline gap shows one summary per member (see OQ-4), not a replay of every level.
- The XP bar never moves backwards. A rebirth resets the bar to empty at the same level, and the empty bar is explained by the "next stretch" text in UI Requirements.

## UI Requirements

This system needs player-facing UI. Guild screens (39) and the Realtime world view (38) own the screens, and this section lists what they must offer:
1. **Member card** shows level, the XP bar (`xp_milli` over `need_milli`) and the rebirth tier. A `Capped` member shows "Capped" in words and an icon, and "ready to rebirth" when Rebirth (23) says it is available.
2. **Level-up feedback** from event 2201 (new level, and the jump when more than one level was gained), and a calm "reached the cap" line from 2202 in the guild chronicle.
3. **Next-stretch preview** for a capped member: the XP cost of the next tier's stretch (F3) and the rebirth reward, so the "long road" is stated before the player commits.
4. **Rate hint** (optional, for the Fantasy): XP per hour and the estimated time to the next level, computed from the member's recent awards. It is shown as an estimate, never as a promise.

Every string goes through Localization (4). Numbers are shown in XP (`xp_milli / 1000`, rounded down), never as milli-XP.

## Cross-References

| This document references | Target | Element | Nature |
|---|---|---|---|
| `config` curve keys and `rebirth` rows (caps, bonuses) | `data-layer-and-content-pipeline.md` | R2, R8, Dependencies | Data dependency |
| Typed tables, `int` and `float` columns, validator as the build gate | `data-layer-and-content-pipeline.md` | R2, R8 | Rule dependency |
| Handler context and `ctx.emit`; core state is integers only | `sim-core-and-tick-loop.md` | R5, R13 | Rule dependency |
| `sim_version` bump for a changed representation | `sim-core-and-tick-loop.md` | R12 | Rule dependency |
| Catch-up quiet period for presentation | `sim-core-and-tick-loop.md` | R15 | Rule dependency |
| Type registration, blocks of 100, milestones, `ring_per_day` | `event-bus-and-history-log.md` | R3, R3a, F4 | Rule dependency |
| Event budget per tick | `event-bus-and-history-log.md` | F1 | Rule dependency (AC-30) |
| `school_join_level`, `join_due` on a level-up event | `schools-and-school-change.md` | R3, F1 | Rule dependency. **Conflict flagged:** Schools assumed one event per level gained; this system emits one per award (follow-up F-1) |
| Parity vectors, the balance gate and `balance_budget.csv` | `dev-tooling-and-parity-harness.md` | R5, R14, Tuning Knobs | Ownership handoff: this system supplies F3 and F4; Dev tooling owns the bands |
| Float rules: `float` is 64-bit, `pow()` order | `GODOT_PORT.md` | Rule 3 | Rule dependency (F1 uses it once per cell at boot) |
| `xp_need`, early ramp, rebirth multipliers, measured pacing | `JX1_Tycoon_GDD.md` | §4.2, §4.3 | Source of intent |
| Rebirth caps and rewards (`xp_pct`, `growth_bonus`) | `JX1_Tycoon_GDD.md` | §6.10 | Source of intent |
| Reference formula, `Member.gain_xp` | `sim/formulas.py`, `sim/model.py` | `xp_need`, `gain_xp` | Reference implementation (to be migrated, OQ-1) |

## Acceptance Criteria

Every number below is reproduced by `sim/formulas.py` with the data in `data/config.csv` and `data/rebirth.csv` as of 2026-11-16. A test sets up the data and the member itself, so it depends on no other system. Criteria marked **[Pending: X]** need a system that has no GDD yet and are written against its provisional contract. Logic criteria need an automated unit test (`tests/unit/xp-and-level-curve/`), integration ones an integration test, and each is BLOCKING under the project's default gate levels.

### Tables and formulas (F1–F4, R2, R3)

- **AC-1 (F1, boundaries)**: **GIVEN** the default data, **WHEN** the need table is built, **THEN** `need_milli(0, 1) = 10,300`, `need_milli(0, 10) = 1,553,680`, `need_milli(1, 100) = 753,565,929` and `need_milli(5, 199) = 14,565,410,703`.
- **AC-2 (F1, monotonic and positive)**: **GIVEN** the default data, **WHEN** the table is built, **THEN** every cell is ≥ 1, `need_milli[r][L+1] > need_milli[r][L]` for all r in 0–5 and L in 1–198, and no cell exceeds 2⁶².
- **AC-3 (F2, typical and boundary)**: **GIVEN** `base_milli = 10,000`, **WHEN** F2 is evaluated for (PA 100, rebirth 2), (PA 100, rebirth 0), (PA 200, rebirth 5), (PA 0, rebirth 0) and (PA 195, rebirth 3), **THEN** the results are 11,220, 10,000, 16,800, 6,000 and 15,400.
- **AC-4 (F2, rounding)**: **GIVEN** PA 0 and rebirth 0, **WHEN** `base_milli` is 1, 2 and 3, **THEN** `effective_milli` is 0, 1 and 1. A `base_milli` of 0 gives 0 for every PA.
- **AC-5 (F2, overflow bound)**: **GIVEN** `base_milli = 2⁴⁰`, PA 200 and rebirth 5, **WHEN** F2 is evaluated, **THEN** the result is 1,847,179,534,663 and no intermediate value exceeds 2⁶³ − 1.
- **AC-6 (F3)**: **GIVEN** the default data, **WHEN** `cumulative_need_milli` is evaluated, **THEN** (0, 1, 100) = 8,983,258,280, (1, 100, 120) = 17,614,542,112, and any (r, a, a) = 0.
- **AC-7 (F4, parity)**: **GIVEN** the default data, **WHEN** `progress_table_hash` is computed, **THEN** it equals `fcc9532fd641d0898a20de6837044c4190dd94327b492602ce0f78e56be301b8`, and the same value is computed by the Python reference and the GDScript port. Changing `xp_rebirth_mult_3` by 1 changes the hash.
- **AC-8 (R3, cap chain)**: **GIVEN** the default `rebirth.csv`, **WHEN** the caps are built, **THEN** `cap = [100, 120, 140, 160, 180, 200]` and each equals the next row's `req_level`. A copy of the data with row 3's `req_level` changed to 141 fails the validator with an ERROR that names the row.
- **AC-9 (R2, runtime)**: **GIVEN** a booted game, **WHEN** 1,000 `award` calls run, **THEN** no float `pow()` is called and the three tables are byte-identical to the values before the calls (checked by hash). A static check confirms `award` contains no `pow`, `**` or float literal.

### `award` and levels (R1, R4–R10)

- **AC-10 (R4, one award, many levels)**: **GIVEN** a member at level 1, `xp_milli` 0, rebirth 0 and PA 100, **WHEN** `award(base_milli = 3,855,180)` is called, **THEN** `level = 10`, `xp_milli = 0` and exactly one event 2201 is emitted with `a` = the member ID, `b = 1`, `c = 10`, `d = 0`.
- **AC-11 (R4, partial progress)**: **GIVEN** the same member, **WHEN** `award(base_milli = 5,000)` is called, **THEN** `level = 1`, `xp_milli = 5,000` and no event is emitted; a second call of 5,300 gives level 2 and `xp_milli = 0` (`need_milli(0, 1)` = 10,300).
- **AC-12 (R4, cap crossing)**: **GIVEN** a member at level 99, `xp_milli` 0, rebirth 0, PA 100, **WHEN** `award(base_milli = 300,000,000)` is called, **THEN** `level = 100`, `xp_milli = 0`, the call returns overflow 53,066,603, and the events are 2201 (`b = 99`, `c = 100`) then 2202 (`b = 100`, `c = 0`), in that order.
- **AC-13 (R4, capped member)**: **GIVEN** a member at level 200, rebirth 5, PA 100, **WHEN** `award(base_milli = 10,000)` is called, **THEN** nothing is changed, no event is emitted and the overflow returned is 12,240.
- **AC-14 (R4, zero award settles)**: **GIVEN** a member at level 5, rebirth 0, with `xp_milli = 400,000` (above the 300,804 needed for level 5 after a patch), **WHEN** `award(base_milli = 0)` is called, **THEN** the member reaches level 6, one 2201 is emitted (`b = 5`, `c = 6`) and the call returns no error. The same call on a member with nothing owed changes nothing and emits nothing.
- **AC-15 (R4, refused inputs)**: **GIVEN** a valid member, **WHEN** `award` is called with `base_milli` = −1, `2⁴⁰ + 1`, the float 5.0, and again with an unknown `member_id`, **THEN** the calls return 2201, 2201, 2201 and 2203, and the member and the event buffer are unchanged. `base_milli = 2⁴⁰` is accepted.
- **AC-16 (R4, bad PA)**: **GIVEN** a member whose `pa` is 201 or −1, **WHEN** `award` is called, **THEN** it returns 2204 and nothing changes.
- **AC-17 (R5, member-side only)**: **GIVEN** two members, one at PA 0 and one at PA 200 (rebirth 0), **WHEN** each is awarded `base_milli = 100,000`, **THEN** they gain 60,000 and 140,000 milli-XP, and `award` applies no party, monster or buff bonus.
- **AC-18 (R6, events)**: **GIVEN** the Event bus at boot, **WHEN** this system registers its types, **THEN** 2201 (`field_count` 4, not logged) and 2202 (`field_count` 3, logged, milestone, `subject_slot` 1) register inside block 2200–2299 without a boot error, and `seal()` succeeds.
- **AC-19 (R6, one event per award)**: **GIVEN** a member at level 1 and an award of 150,000,000 milli at PA 100, rebirth 0, **WHEN** the call finishes, **THEN** the member gains more than one level and exactly one 2201 is in the event buffer, with `b = 1` and `c` = the new level.
- **AC-20 (R7, rebirth keeps level)**: **GIVEN** a capped member at level 100, rebirth 0, **WHEN** `rebirth` is set to 1 (by the test acting as Rebirth 23) and `award(base_milli = 1,000,000,000)` is called at PA 100, **THEN** `level = 101`, `xp_milli = 346,434,071`, and one 2201 is emitted with `b = 100`, `c = 101`, `d = 1`. Before the award, `level = 100` and `xp_milli = 0`.
- **AC-21 (R7, no loss)**: **GIVEN** any member, **WHEN** any sequence of `award` calls runs, **THEN** `level` never decreases and `xp_milli` is never negative.
- **AC-22 (R8, no RNG)**: **GIVEN** a seeded RNG with a known `draws_consumed`, **WHEN** 100 `award` calls run, **THEN** `draws_consumed` is unchanged and the same inputs give the same output on a second run.
- **AC-23 (R9, init_progress)**: **GIVEN** a member at rebirth 1, **WHEN** `init_progress` is called with level 120, 121 and 0, **THEN** level 120 is accepted with `xp_milli = 0`, and 121 and 0 are refused with 2202.
- **AC-24 (R10, order)**: **GIVEN** two awards to one member in one tick that together cross the cap, **WHEN** they run in order A then B, **THEN** the 2202 event is emitted by the call that reaches the cap, and swapping the order moves the 2202 but leaves the final `level` and `xp_milli` unchanged.

### States (States and Transitions)

- **AC-25 (state table)**: **GIVEN** a member at `level < cap`, **WHEN** an award reaches the cap, **THEN** the member is `Capped` (`level = cap`, `xp_milli = 0`). **GIVEN** a `Capped` member, **WHEN** `rebirth` rises by 1, **THEN** the member is `Growing` and `cap` is 20 higher with today's data. There is no path from `Capped` to `Growing` other than a rebirth.

### Edge cases and validator (Edge Cases A–D)

- **AC-26 (patch lowers need)**: **GIVEN** a stored member with `xp_milli` above the new `need_milli` after a data patch, **WHEN** the member is loaded, **THEN** `level` and `xp_milli` are unchanged on load; the first `award` (including 0) settles the level (AC-14).
- **AC-27 (over-cap save)**: **GIVEN** a stored member at rebirth 0 with `level = 130`, **WHEN** `init_progress(level = 130, rebirth = 0)` is called, **THEN** it returns 2202 and the member is not clamped.
- **AC-28 (validator refusals)**: **GIVEN** seven copies of the data, one with each fault: `xp_early_end = 0`, `xp_early_floor = 0`, `xp_rebirth_mult_3 = 4` (not above 5), `xp_rebirth_mult_4` missing, an unparseable `xp_pct` in `rebirth.csv`, `xp_need_exp = 40` (a cell above 2⁶²) and a broken cap chain, **WHEN** the validator runs on each, **THEN** each fails with an ERROR naming the key, and the game does not boot. A control copy of the default data passes.
- **AC-29 (aggregate vs single)**: **GIVEN** a member at PA 0, rebirth 0, **WHEN** 1,000 awards of 1,501 milli are applied one by one in one run, and one award of 1,501,000 in a second run, **THEN** the effective XP differs by at most 2,000 milli (it differs by 600 today), and the final levels differ by at most 1.
- **AC-30 (event volume)**: **GIVEN** 20 members each awarded a level-up and a cap crossing in one tick, **WHEN** the tick's events are counted, **THEN** this system accounts for at most 40 events (2 per awarded member).

### Cross-system

- **AC-31 (Schools, [Pending: Schools tests it too])**: **GIVEN** an unaffiliated member at level 8 with an aspiring school and `school_join_level = 10`, **WHEN** an award lifts them to level 12 in tick N (one 2201 with `c = 12`), **THEN** Schools' `join_due` is true and the member joins in P1 of tick N + 1.
- **AC-32 (Event bus, integration)**: **GIVEN** the bus sealed with this system's types and a history log, **WHEN** a member reaches the cap, **THEN** 2202 is delivered to a subscriber in the same tick's P6 batch and one history record (stride 6) with the member as subject is written; 2201 writes no history record.
- **AC-33 (Data layer, integration)**: **GIVEN** the real `config.csv` and `rebirth.csv`, **WHEN** the Data layer loads and the validator runs, **THEN** it passes with 0 errors and `cap`, `bonus_ppm` and `growth_bonus_ppm` equal their tables in F2 and R3.
- **AC-34 (Member model, [Pending: Member model])**: **GIVEN** a member created through Member model with a given PA, **WHEN** an award is made, **THEN** `level` and `xp_milli` are written only by this system (no other write path exists; a grep of the code base finds none), and `init_progress` is called on creation and on load.
- **AC-35 (balance gate, [Pending: Dev tooling])**: **GIVEN** the standard 5-member party at PA 100 with the current hunt model, **WHEN** the quick balance scenario runs, **THEN** the time to level 100 falls inside the band in `tools/balance_budget.csv` (about 71 hours today), computed with F3. The scenario reports `null` instead of a number if the party never reaches the level.

### Coverage and gaps

- **Covered:** R1 (AC-21, AC-34), R2 (AC-1, AC-9), R3 (AC-8), R4 (AC-10 to AC-16), R5 (AC-17), R6 (AC-18, AC-19, AC-30), R7 (AC-20, AC-21), R8 (AC-22), R9 (AC-23), R10 (AC-24), F1 (AC-1, AC-2), F2 (AC-3 to AC-5), F3 (AC-6), F4 (AC-7), the states (AC-25) and every edge-case group.
- **Not testable here (moved to playtest):** whether the pace *feels* like fast-early and a long road (Player Fantasy). It is a playtest question for the first vertical-slice session: "Did the first hour feel full of level-ups, and did the late levels feel worth waiting for?" The hours in AC-35 are the automated proxy.
- **Needs another system's tests:** the once-per-kill guarantee (Hunt), the offline parity bound (Offline) and the Schools edit (follow-up F-1).

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | The Python reference stores XP as a float and keeps `LEVEL_CAP` in code, defaults a missing `xp_rebirth_mult_r` key to 1.0 and never applies `xp_pct` or `growth_bonus`. It must migrate to `xp_milli`, the data-driven caps and a refusing validator (F1, F2, R3, AC-28) before the balance sim is trusted. Re-measure the pacing after the migration | Dev tooling and balance sim (43) | Before the balance gate is enabled |
| OQ-2 | The growth multiplier needs `_ppm` keys above 1,000,000, which the Data layer's `ppm` type (probabilities, 0–1,000,000) does not allow; `rebirth.csv` `rewards` is an untyped `key=value;` string, so `xp_pct` and `growth_bonus` need typed parsing. Add the two `int` keys, rename `growth_mult_base` and `growth_mult_pa`, and add the validator rules | Data layer (3) | When the Data layer next changes |
| OQ-3 | Who applies timed XP buffs (feast +10% for 1 hour, Library of Wisdom, and the "newbie bonus" idea in §4.3: XP ×3 for the first 30 minutes)? R5 puts them on the caller, but no system owns them yet | Items and loot (26), Guild and buildings (30), Onboarding (44) | When those GDDs are designed |
| OQ-4 | How does the offline resolver call `award` without a handler context, and how do level-ups in a gap surface (one summary event per member)? **RESOLVED (consistency-check 2026-11-16):** R4 step 5 — `ctx = null` emits nothing, returns old/new level (step 7); Offline emits one 2201 per member per absence on this system's behalf (Offline R15) | Offline progress (31), with Event bus OQ-2 | Closed |
| OQ-5 | Recovery for a save with `level > cap[rebirth]` (reject, clamp, or move the member to the cap)? `init_progress` only refuses it | Local save and migration (6) | When Local save is designed |
| OQ-6 | The measured pacing (71 hours to level 100, 54 days to 200) comes from the Python sim with stand-in skills. Real skills and enhancement will shift it. After S4, recalibrate `xp_kill_coef` first, then the curve (GDD §20) | Dev tooling and balance sim (43), Hunt (11) | After real skills ship in the sim |
| OQ-7 | Should reaching certain levels (every 10th, the school-join level) be a logged milestone for the Chronicle? 2201 is not logged today, to protect the history budget | Event bus (42), Jianghu Chronicle (36) | When the Chronicle is designed |
| OQ-8 | Schools (20) must change its provisional assumption 1 and its dependency row to "one level-up event per award, with the old and new level" (follow-up F-1). Systems index row 22 must add Sim core and Event bus as dependencies (follow-up F-2) | Schools (20); `/map-systems` | Before `/design-review` of both |
