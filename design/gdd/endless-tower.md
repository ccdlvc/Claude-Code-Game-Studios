# Endless Tower (Vô Tận Tháp)

> **Status**: Designed (pending review)
> **Author**: user + agents (`/design-system`, autonomous batch run)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: No `game-pillars.md` exists; serves GDD §1 core loop (members grow stronger) and §6.3 / §7 (Vô Tận Tháp as end-game item sink, the EHT Dungeon)
> **Creative Director Review (CD-GDD-ALIGN)**: CONCERNS (accepted) 2026-11-16 — see Open Questions OQ-9, OQ-10

## Summary

The Endless Tower is the guild's end-game ladder: the player sends a group of up to five members into the Vô Tận Tháp, and they climb one fight per floor, carrying their wounds from floor to floor, until they fall, run out of time, retreat or reach the tower's height. Each floor the guild clears for the first time pays out rare zone materials and gear into guild storage, and each floor attempted costs common materials, so the tower turns surplus late-game materials into a measure of how strong the guild has become. It exists to give the Wave 2 guild a goal beyond the zone ladder and a sink for the materials hunting keeps producing.

> **Quick reference** — Layer: `Feature` · Priority: `Full Vision` · Key deps: `Combat, Deterministic RNG, Zones and hunt trips, Items and loot tables, Guild and buildings, Member model, Member state machine, Rebirth and Ascension`

## Overview

The Endless Tower is a Wave 2 feature (GDD §12.5) unlocked by building the Vô Tận Tháp (`bld_tower`, needs Tổng Đàn level 5). The building's level sets `floor_cap`, the highest floor the guild may attempt (10 at level 1, 100 at level 10). The guild keeps one number, `best_floor`, the highest floor it has ever cleared. A **run** starts with the player picking one to five idle members; they enter at `best_floor + 1` and fight one monster per floor. Each floor's monster is generated from a formula (no hand-authored floors): its level rises with the floor number, its element cycles through the Five Elements, and every tenth floor is a zone boss. Combat (10) resolves each fight; HP carries over between floors with a small rest heal. A run ends when the group is wiped, a fight times out, the group's HP drops below a retreat threshold, the player calls a retreat, the guild cannot pay the next floor's material cost, or `floor_cap` is reached. Every floor cleared in a run is a first clear (runs never replay cleared floors), so it rolls that floor's zone drop table into guild storage. Floors above 50 are "high floors" and require every member of the group to have reached rebirth tier 2 (`unlock_tower_high`, `rebirth.csv`). The tower grants no XP: it tests the guild, it does not farm it.

## Player Fantasy

**Chosen framing — "Every floor is a verdict on the guild you built."** The player opens the tower panel, sees *Floor 37 — Hoả, level 97*, and sends their best five: a Thuỷ tank, a Mộc healer, a buffer and two counter-element damage dealers. The floor counter ticks up every few seconds, the healer's bar drains, and on floor 40 the zone boss appears. When the group either breaks through or retreats with two members barely standing, the result is not luck the player can reroll: it is what their recruiting, school picks, gear and party balance add up to. The moment that matters is the run summary, *"Cleared 37–41, retreated on 42: party HP below 30%"*, and the next decision it prompts (enhance the tank, rebirth the healer to tier 2, recruit a Kim damage dealer for the Mộc floors).

*Considered and not chosen:*
- *"The treasure vault"* (the tower as a loot fountain): would ask for repeatable rewards, which with seeded dice becomes a farm and fights GDD §4.3's slowing pace.
- *"The lone champion"* (one hero climbing): conflicts with §6.12's party rule (prefer a buffer in every party) and makes the guild layer irrelevant.

What the chosen framing asks of the design: outcomes must be readable (the summary names why the run ended), deterministic for a given guild state, sensitive to element choice and party balance, and never paywalled (RNG R10: nothing bought changes the dice).

## Detailed Design

### Core Rules

**R1 — Availability.** The tower exists when `effect(bld_tower, floor_cap)` (Guild and buildings R7) returns a value; `none` means the tower is unavailable and the tower panel is hidden. `floor_cap` is a capacity key and never decays under arrears (Guild and buildings R8). While `bld_tower` is upgrading, the old level's `floor_cap` applies (Guild and buildings R6).

**R1a — Endless above floor 100 (user decision 2026-11-16, OQ-1).** `bld_tower` gates the tower only up to `tower_endless_from` (100). The tower's effective top is `tower_top = floor_cap` while `floor_cap < tower_endless_from`, and **unbounded** once `floor_cap ≥ tower_endless_from` (`bld_tower` level 10 today). Floors above `tower_endless_from` keep F1–F3's linear scaling (F2 is the endless curve) and their first clear pays **no gold and no items** (F4): they raise `best_floor`, which feeds the leaderboard and the guild's tower title, and nothing else, so the economy is unaffected. Every use of `floor_cap` below as a ceiling means `tower_top`. The **tower title** is derived, never stored: when `best_floor > tower_endless_from` the guild shows "Vô Tận Tháp · tầng N" with N = `best_floor` rounded down to the last boss floor (localisation key `tower.title`); the 1905 `tower_milestone` event on each boss floor above 100 is the title-up moment. Leaderboards (35) ranks on `best_floor` (its OQ-8).

**R2 — Guild tower record.** The system owns one record per guild, saved as its own section `tower` (Local save R6):

| Field | Type | Meaning |
|---|---|---|
| `best_floor` | int ≥ 0 | Highest floor ever cleared. Never decreases; not reset by rebirth, school change or building upgrades. |
| `run_ordinal` | int ≥ 0 | Number of runs ever started. Incremented when a run starts; the current run's ordinal is the new value (so the first run is 1). |
| `run` | object or null | The active run (R4), or null. |

**R3 — One run at a time.** A guild has at most one active run (`tower_max_runs` = 1). A run's group has 1 to `tower_party_max` (5, GDD §6.12) members, in the order the player picked them; that order is Combat's combatant order (Combat R3). The group is a tower group, not a Party (13) party: membership in a hunting party is irrelevant, and party bonuses that Party owns do not apply. Role effects inside the fight (tank aggro, healer, buffer) are Combat's and do apply.

**R4 — The run record.** `members` (ordered member IDs still in the run), `floor` (the floor being fought or next to fight), `start_floor`, `phase` (R7), `fight_tick` (the tick the current floor's fight was resolved, or −1), `next_tick` (the tick the next floor starts), `retreat_requested` (bool), `pending_loot_floor` (the floor whose first-clear loot is waiting for P4, or 0).

**R5 — Starting a run: command `tower_start(member_ids)`** (Command layer, ID 1901, applied in P1 at order 1900). It is refused, with event `tower_start_refused` (1904) carrying the reason and no state change, when:
1. a run is already active;
2. the tower is unavailable (R1);
3. the list is empty, longer than `tower_party_max`, or has a duplicate or unknown member ID;
4. any member is not idle at home (Member state machine 41: state `idle`; PROVISIONAL);
5. `best_floor + 1 > tower_top` (the tower is climbed to its current height; never true once the tower is endless, R1a);
6. `best_floor + 1` is a high floor and any member fails the high-floor gate (F7);
7. guild storage cannot pay the first floor's cost (F5; Items and loot `take` returns false).

If accepted, in this order: `run_ordinal += 1`; the first floor's cost is taken from storage (Items R7 `take`, all-or-nothing; command-time storage writes follow the precedent of Items R8 `award_item`); each member is moved to the `tower` state (Member state machine 41, PROVISIONAL); the run record is created with `floor = start_floor = best_floor + 1`, `phase = Ready`, `next_tick = current tick`; event `tower_run_started` (1901) is emitted.

**R6 — Retreating: command `tower_retreat()`** (ID 1902, P1 order 1900). Refused with 1904 reason 8 if no run is active. Otherwise sets `retreat_requested`. A floor already being fought is not interrupted (a fight is atomic, Combat R2); the run ends with reason `retreat` when that floor's result is applied, or at once if the run is `Between` floors. No material is refunded.

**R7 — Floor resolution (P3 `field`, order 1900).** Each tick, for an active run:
- **Ready and `next_tick` ≤ now:** build the floor encounter (R8), derive the generator `derive(rng_domain_tower = 15, [run_ordinal, floor])` (RNG R3), call Combat `resolve(encounter, gen)`, keep the `FightResult` in memory, set `fight_tick = now`, `phase = Fighting`. The members' HP as other systems see it stays the pre-fight HP until the deadline (Combat R2).
- **Fighting and now ≥ deadline tick** (Combat F8 from `fight_tick` and `duration_s`): apply the result. Each member's HP becomes `hp_after`. Members who died are removed from `members` and handed to Member state machine (41) as `dead` (revive at Linh Miếu, as a hunt death; PROVISIONAL). Then:
  - **Won:** `best_floor = floor`; `pending_loot_floor = floor`; emit `tower_floor_cleared` (1902), and `tower_milestone` (1905) if `floor` is a boss floor (F3). Apply the rest heal (F6) to the survivors. The run **ends** if `retreat_requested` (reason `retreat`), if `floor + 1 > tower_top` (reason `top_reached`), if the run has cleared `tower_run_floor_max` floors (reason `run_limit`; keeps an endless run bounded, F8), if `floor + 1` is a high floor and a survivor fails the gate (reason `high_floor_locked`), or if the retreat check fails (F6; reason `low_hp`). Otherwise `floor += 1`, `phase = Between` (the next floor's cost is paid in P4).
  - **Lost, reason wiped:** the run ends with reason `wiped`.
  - **Lost, reason timeout:** the run ends with reason `timeout`; survivors keep their `hp_after`.
- A run that ends sets every remaining member back to `idle` at home (41) with their current HP, emits `tower_run_ended` (1903) and sets `run = null` once P4 has rolled any pending loot.

**R8 — The floor encounter.** Combat R3 fields:

| Field | Tower value |
|---|---|
| `groups` | One group: the run's `members`, in order |
| `monster` | The floor monster row (F3) with its `level` replaced by `floor_level(floor)` (F1) |
| `hp_scale`, `dmg_scale` | F2 |
| `attack_interval_base_s` | 1.0 (as a hunt fight) |
| `targets_per_attack` | 1 |
| `enrage_every_s`, `enrage_atk` | disabled |
| `time_limit_s` | `tower_time_limit_s` (300) |
| `want_timeline` | true when the tower view is open (Combat R14; never changes the outcome) |

Only the level, the two scales and the time limit differ from a hunt fight, so the floor fight is the same resolver a hunt uses (Combat R3 decision: one resolver).

**R9 — Costs and first-clear rewards (P4 `economy`, order 1900).** In the tick a floor's result is applied:
1. If `pending_loot_floor > tower_endless_from`: no roll and no gold (R1a; title/leaderboard only). Reset `pending_loot_floor = 0`. Otherwise, if `pending_loot_floor > 0`: roll the floor's reward (F4) through Items and loot's guild loot roll with `luck_milli = 1000` and loot event key `[0, 2, run_ordinal, floor]` (Items R3, source tag 2 reserved for this system). Items and materials go to guild storage (no bag, no auto-equip, no sale, as Items R9a). The rolled gold is credited to the **guild fund** through Gold economy (27) as a `tower_reward` mint (Gold economy entry type 13). Reset `pending_loot_floor = 0`.
2. If the run continues (`phase = Between`): `take` the next floor's cost (F5). If storage is short, the run ends with reason `no_material`. Otherwise `next_tick = now + ceil(tower_floor_gap_s × tick_rate)`, `phase = Ready`.

Cleared floors are never fought again, so each floor's reward is paid once per save. There is no repeat reward and no "sweep".

**R10 — No XP, no member gold.** Tower fights award no XP and no personal gold. Level pacing (GDD §4.3) stays owned by hunting and XP and level pacing (22); all tower gold goes to the guild fund.

**R11 — Offline.** A run keeps running while the app is closed. Offline progress (31) must advance an active run exactly, by the same R7–R9 rules, not by sampling (PROVISIONAL): a run is at most `min(tower_top − best_floor, tower_run_floor_max)` floors (≤ 100 fights, F8), cheap enough to resolve exactly. The tower never starts a run on its own; offline only finishes the run the player started.

**R12 — Exclusions while in the tower.** Members in the `tower` state: are not called to a Golden Boss raid (they count as unavailable, like `away`; PROVISIONAL for Golden Boss 14); cannot equip, unequip, be awarded gear, train, change school or rebirth (Member model R6 refuses `equip` outside idle states; PROVISIONAL for the others); and are not subject to Retention (16) leave checks until the run ends (PROVISIONAL).

**R13 — Registration.** Event type block and command block 1900–1999 (Event bus R3, Command layer: owner system number × 100). Handlers: P1 order 1900 (commands), P3 order 1900 (floors), P4 order 1900 (costs and rewards). Save section `tower` (Local save R6) with an invariant check: every member in `run.members` exists and is in the `tower` state; `best_floor ≤ 10⁶`. Feature fail code **19001** `TOWER_ROW_MISSING`: a floor maps to no zone, monster row or grade-1 material (unreachable for content that passes the validator, Edge Cases).

### States and Transitions

**Run phases**

| Phase | Entered when | Leaves to |
|---|---|---|
| (none) | No active run | `Ready` on an accepted `tower_start` |
| `Ready` | Run started, or the next floor's cost was paid | `Fighting` when `next_tick` ≤ now (P3) |
| `Fighting` | The floor fight was resolved; waiting for the deadline tick | `Between` (won, continuing), `Ended` (any end reason) |
| `Between` | Floor won and the run continues; cost not yet paid | `Ready` (cost paid, P4), `Ended` (`no_material`, or `retreat` requested) |
| `Ended` | Any end reason | (none) after P4 rolls pending loot in the same tick |

End reasons (event 1903 `a`): 1 `wiped`, 2 `timeout`, 3 `low_hp`, 4 `retreat`, 5 `top_reached`, 6 `no_material`, 7 `high_floor_locked`, 8 `run_limit` (R7, added 2026-11-16 for the endless tower).

**Member side (PROVISIONAL, owned by Member state machine 41):** `idle → tower` on run start; `tower → dead` on death in a floor fight; `tower → idle` when the run ends. A save mid-`Fighting` stores only `fight_tick`; on load the fight is re-resolved with the same key and the same frozen inputs (members in `tower` cannot change gear, school or level), giving the same result (RNG R5, Combat R4).

### Interactions with Other Systems

| System | Direction | Data | Owner of the interface |
|---|---|---|---|
| Sim core and tick loop (1) | in | P1, P3, P4 handlers; `tick_rate`; `ctx.derive` | Sim core |
| Deterministic RNG (2) | in | Domain 15 `tower`, key `[run_ordinal, floor]`; domain 2 loot key `[0, 2, run_ordinal, floor]` | RNG owns derivation; this GDD owns the domain-15 key |
| Data layer (3) | in | `zones`, `monsters`, `materials`, `drop_tables`, `rebirth`, `sim_params` (tower knobs) | Data layer |
| Event bus (4) | out | Types 1901–1905 | This GDD owns the block |
| Command layer (5) | in | Commands 1901 `tower_start`, 1902 `tower_retreat` | This GDD owns the commands |
| Local save (6) | both | Section `tower` | Save owns the envelope |
| Member model (8) | in | Member stats, current `hp`, rebirth tier field | Member model |
| Combat (10) | out | `resolve(encounter, gen)` per floor; reads `won`, `reason`, `duration_s`, `hp_after`, deaths | Combat owns `resolve` |
| Zones and hunt trips (11) | in | Zone level bands and boss rows (`zones.csv`), monster rows (`monsters.csv`) | Zones owns the content; the tower owns floors |
| Golden Boss raid (14) | out | Tower members are ineligible | Golden Boss (PROVISIONAL) |
| Retention (16) | out | Leave checks deferred for tower members | Retention (PROVISIONAL) |
| Rebirth and Ascension (23) | in | Member's rebirth tier and the cumulative `unlock_tower_high` reward | Rebirth (PROVISIONAL) |
| Items and loot (26) | both | `take` costs; guild loot roll with source tag 2 into storage | Items owns rolls and storage |
| Gold economy (27) | out | `tower_reward` mint to the fund | Gold economy (entry type 13) |
| Guild and buildings (30) | in | `effect(bld_tower, floor_cap)` | Guild and buildings |
| Offline progress (31) | in | Exact advance of an active run | Offline (PROVISIONAL) |
| Member state machine (41) | both | `tower` state, `dead`, `idle` transitions | 41 (PROVISIONAL) |
| Leaderboards (35), Quests (25) | out | Read-only `best_floor`; events 1902, 1905 | Consumers |
| Realtime world view (38), UI | out | Events and the fight timeline | Consumers |

## Formulas

Integers are exact; the two encounter scales (F2) and the HP formulas (F6) are IEEE-754 binary64, evaluated left to right as written (`GODOT_PORT.md` rule 3, as Combat). Tower knobs are new keys in `data/sim_params.csv` (PROVISIONAL, OQ-3).

`systems-designer` lens applied: each variable worked at its minimum, maximum and 0; findings are under each formula and in Edge Cases.

### F1 — Floor level

The floor_level formula is defined as:

`raw_level(N) = tower_base_level + ((N − 1) × tower_level_step_milli) div 1000`
`floor_level(N) = min(raw_level(N), level_cap)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| N | int | 1 – `tower_top` (1–100 below `bld_tower` 10; unbounded above, R1a); formula valid to 10⁶ | calculated (run `floor`) | Floor number |
| tower_base_level | int | 40 (safe 20–80) | data file (`sim_params.csv`) | Level of floor 1 |
| tower_level_step_milli | int | 1600 (safe 800–3000) | data file (`sim_params.csv`) | Levels per floor × 1000 |
| level_cap | int | 200 | constant (Combat F1 range, CA max) | Highest monster level |

**Output Range:** 40 at floor 1, 54 at floor 10, 118 at floor 50, 120 at floor 51, 198 at floor 100, 200 from floor 101. At step 0, every floor is level 40 (the tower stops getting harder: the validator requires step ≥ 1). Integer `div` keeps it identical in Python and GDScript.
**Example:** floor 37: `40 + (36 × 1600) div 1000 = 40 + 57 = 97`.

*Why these numbers:* floor 1 at level 40 sits inside the zone_05 band a Tổng Đàn-5 guild is already hunting; floor 51 (the first high floor) is level 120, the level rebirth tier 2 requires (`rebirth.csv` row 2); floor 100 is level 198, the top of zone_15. The tower therefore stays a little ahead of the zone ladder at every stage.

### F2 — Over-cap scales (the endless part)

The overcap_scale formula is defined as:

`excess(N) = max(0, raw_level(N) − level_cap)`
`hp_scale(N) = 1 + tower_overcap_hp_step × excess(N)`
`dmg_scale(N) = 1 + tower_overcap_dmg_step × excess(N)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| excess(N) | int | ≥ 0 | calculated | Levels past the level cap |
| tower_overcap_hp_step | float | 0.02 (safe 0.005–0.05) | data file (`sim_params.csv`) | HP gain per excess level |
| tower_overcap_dmg_step | float | 0.02 (safe 0.005–0.05) | data file (`sim_params.csv`) | Hit gain per excess level |

**Output Range:** 1.0 for every floor up to 101; above that it grows linearly for ever (the tower is endless above floor 100, R1a). At floor 200: `raw = 40 + 318 = 358`, `excess = 158`, both scales 4.16. Linear and unbounded, never negative (steps ≥ 0, validator). At step 0 floors past 101 never get harder.
**Example:** floor 150: `raw = 40 + (149 × 1600) div 1000 = 278`, `excess = 78`, `hp_scale = 1 + 0.02 × 78 = 2.56`.

This is what makes the tower "vô hạn" (GDD S7: difficulty growing on a set linear curve) above floor 100 (R1a; OQ-1 resolved 2026-11-16).

### F3 — Floor monster

The floor_monster formula is defined as:

`is_boss(N) = (N mod tower_boss_every = 0)`
`zone(N) = the live zone with the greatest level_min ≤ floor_level(N)` (lowest-order live zone if none)
`element(N) = tower_element_cycle[(N − 1) mod 5]`
`monster(N) = zone(N).boss_monster_id` if `is_boss(N)`, else `candidates(element(N))[((N − 1) div 5) mod count]`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| tower_boss_every | int | 10 (safe 5–20) | data file (`sim_params.csv`) | Boss floor spacing |
| tower_element_cycle | list of 5 elements | `moc, hoa, tho, kim, thuy` | constant (the generating cycle, GDD §6.1) | Element order of normal floors |
| candidates(e) | list of monster rows | 10–15 per element today | calculated (`monsters.csv`: live, `is_boss = false`, `element = e`, ascending `uid`) | Normal-floor pool |
| count | int | ≥ 1 | calculated (`len(candidates(e))`) | Pool size; validator requires ≥ 1 per element |

**Output Range:** a live monster row; no random draw (the domain-15 generator is used by Combat only). Five consecutive normal floors cover all five elements, so a group with one element is countered on one floor in five and counters one in five.
**Example:** floor 37: level 97, zone_10 (level_min 90), not a boss floor, `element = cycle[36 mod 5 = 1] = hoa`, index `(36 div 5) mod 12 = 7`, the 8th live non-boss Hoả row by `uid`, fought at level 97. Floor 40: level 102, zone_11 (level_min 100), boss `m_z11_boss` (hp_mult 16) at level 102.

### F4 — First-clear reward

The floor_reward formula is defined as:

`reward(N) = nothing` if `N > tower_endless_from` (R1a: title/leaderboard only); otherwise `tower_reward_rolls_boss` rolls of `zone(N).boss table` if `is_boss(N)`, else `tower_reward_rolls` rolls of `drop_<zone(N)>`, each rolled at monster level `floor_level(N)` with `luck_milli = 1000`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| tower_reward_rolls | int | 2 (safe 1–5) | data file (`sim_params.csv`) | Table rolls on a normal floor |
| tower_reward_rolls_boss | int | 1 (safe 1–3) | data file (`sim_params.csv`) | Boss-table rolls on a boss floor |
| table | drop table | `drop_zone_XX`, `drop_zone_XX_boss` | data file (`drop_tables.csv`) | The zone's own tables (Items R2) |

Several rolls of one floor are one loot event: the table's rows are rolled `rolls` times in sequence inside the one generator (Items R3a order, repeated), so the key stays `[0, 2, run_ordinal, N]`. PROVISIONAL: Items and loot must accept a roll count on the guild loot roll (OQ-5).

**Output Range:** at 0 rolls a floor pays nothing (validator requires ≥ 1). Expected per normal floor in zone_10: 2.2 grade-1, 0.6 grade-2, 0.08 grade-3, 0.03 rare equipment, 2 × base gold. Per boss floor: 6 grade-1, 3 grade-2, 0.75 grade-3, 0.25 rare.
**Example:** floor 37: 2 rolls of `drop_zone_10` at level 97. Floor 140: nothing (no gold, no items); `best_floor` becomes 140.

### F5 — Floor cost

The floor_cost formula is defined as:

`cost_material(N) = the live material with zone_id = zone(N) and grade = 1`
`cost_qty(N) = tower_floor_cost × (tower_boss_cost_mult if is_boss(N) else 1)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| tower_floor_cost | int | 4 (safe 0–20) | data file (`sim_params.csv`) | Grade-1 units per normal floor |
| tower_boss_cost_mult | int | 2 (safe 1–5) | data file (`sim_params.csv`) | Multiplier on boss floors |

**Output Range:** 4 units on a normal floor, 8 on a boss floor. At 0 the tower is free and stops being a sink. Climbing floors 1–100 once costs 90 × 4 + 10 × 8 = 440 grade-1 units across ten zones, plus the cost of every failed floor.
**Example:** floor 37: 4 × `mat_z10_1`.

*Sink check (economy lens):* a normal zone_10 floor takes 4 grade-1 units and returns about 2.2 grade-1 plus 0.6 grade-2 and the rare chances: a net burn of common materials converted into rarer ones. A boss floor takes 8 and returns about 6 grade-1 and 3 grade-2: a net gain, the reward for the hard floor. Every failed floor (wiped or timed out) is a pure burn. There is no repeat reward, so the faucet is bounded (one payout per floor per save, and none above floor 100) while the sink is not: every endless floor is a pure material burn, so the endless tower can only remove resources from the economy.

### F6 — Rest heal and retreat check

The rest_and_retreat formula is defined as:

`hp_i' = min(hp_max_i, hp_i + tower_rest_heal_pct × hp_max_i)` for each surviving member
`retreat = (Σ hp_i' / Σ hp_max_i) < tower_retreat_hp_pct`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| hp_i, hp_max_i | float | 0 < hp ≤ hp_max | calculated (Combat `hp_after`, Member model `hp_max`) | Survivor HP |
| tower_rest_heal_pct | float | 0.10 (safe 0–0.3) | data file (`sim_params.csv`) | Heal between floors |
| tower_retreat_hp_pct | float | 0.30 (safe 0–0.6) | data file (`sim_params.csv`) | Group HP fraction below which the group retreats |

**Output Range:** `hp_i'` in (0, hp_max]; the ratio in (0, 1]. The sums are over survivors only, and a run with no survivors has already ended (`wiped`), so the denominator is never 0. At `tower_retreat_hp_pct = 0` the group never retreats and climbs until it wipes; at ≥ 1 it retreats after every floor.
**Example:** two survivors at 900/3,000 and 1,500/2,500 → after heal 1,200 and 1,750 → ratio 2,950 / 5,500 = 0.536 → continue.

### F7 — High-floor gate

The high_floor_gate formula is defined as:

`is_high(N) = N > tower_high_floor`
`gate_ok(member) = rebirth tier rewards of member include unlock_tower_high = 1`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| tower_high_floor | int | 50 (safe 20–90) | data file (`sim_params.csv`) | Last floor open to every member |
| unlock_tower_high | flag | 0/1 | data file (`rebirth.csv`, tier 2 reward) | Cumulative rebirth reward (Rebirth 23) |

**Output Range:** floors 1–50 open to all; 51+ open only to a group whose every member is at rebirth tier ≥ 2 today. At `tower_high_floor ≥ floor_cap` the gate never applies.
**Example:** a group of four tier-2 members and one tier-1 member at `best_floor = 50` is refused with reason 6.

### F8 — Run length and event budget

The run_bounds formula is defined as:

`floors_per_run ≤ min(tower_top − best_floor, tower_run_floor_max)`
`run_time_s ≤ floors_per_run × (tower_time_limit_s + one action + tower_floor_gap_s)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| tower_time_limit_s | float | 300 (safe 60–600) | data file (`sim_params.csv`) | Per-floor fight limit |
| tower_floor_gap_s | float | 2 (safe 0–30) | data file (`sim_params.csv`) | Pause between floors |
| tower_run_floor_max | int | 100 (safe 20–200) | data file (`sim_params.csv`, new 2026-11-16) | Most floors one run may clear; the endless tower's per-run bound |

**Output Range:** at most 100 floors per run and about 30,300 s (8.4 h) in the worst case; a realistic floor lasts 5–90 s. Events: at most 3 per tick (1902 + 1905 + 1903 on a run-ending boss floor), and 1 + floors + 1 + floors ÷ 10 per run.
**Example:** a 5-floor run with 40 s floors: about 210 s, 1 + 5 + 1 = 7 events (plus one 1905 if it includes a boss floor).

**Feedback loops.** *Positive:* clearing floors pays rare gear and grade-2/3 materials, which make the guild stronger, which clears more floors. Damped by the first-clear-only rule (no farm), by F1's level growth outpacing gear, by `floor_cap` behind building upgrades, and above floor 100 by paying no rewards at all (R1a), so the loop stops there. *Negative:* a failed floor burns materials and kills members (revive time), so pushing too early is punished.

## Edge Cases

- **If the group wins a floor and `floor + 1 > tower_top`** (only below `bld_tower` 10): the run ends with `top_reached`; `tower_start` is refused (reason 5) until `bld_tower` is upgraded. The panel shows "Climbed to the top — upgrade the tower."
- **If the tower is endless and a run clears `tower_run_floor_max` floors**: the run ends `run_limit` (8); the player starts a new run from `best_floor + 1`. This bounds offline resolution (R11) and the event budget (F8); it is not a cap on the tower.
- **If floor 100 is cleared**: its normal first-clear reward is paid (it is not above `tower_endless_from`); floor 101 onward pays nothing. A guild that clears floor 101+ gains leaderboard standing and title only.
- **If `bld_tower` data later lowers `floor_cap` below `tower_endless_from`**: capacity keys never decay, and `best_floor` never decreases; `tower_start` is refused 5 until the cap is above `best_floor` again.
- **If `bld_tower` is upgrading during a run**: the run uses the old level's `floor_cap` until the upgrade completes (Guild and buildings R6); the new cap applies from the next floor check.
- **If the guild is in upkeep arrears**: `floor_cap` is a capacity key and does not decay; the tower is unaffected.
- **If storage is short of the next floor's material**: the run ends with `no_material` after the current floor's loot is rolled; that floor's loot is added first, so a first-clear reward can never be lost to the cost check. (Loot is rolled before the cost is taken, R9.)
- **If the floor's reward contains the very material the next floor costs**: the reward is added before the cost is taken, so it can pay for the next floor. Intended.
- **If a member dies on a floor and others survive**: the dead member leaves the run at once (to `dead`, revive as for hunting); the rest continue with fewer members.
- **If every member dies**: the run ends `wiped`; no loot for that floor; the floor's cost is spent.
- **If a fight times out with survivors**: `timeout`; survivors go home with their current HP; cost spent; no loot.
- **If the player requests a retreat during `Fighting`**: the fight is not interrupted; if it is won, its loot is paid and the run ends `retreat`; if lost, the loss reason is reported instead.
- **If a survivor fails the high-floor gate after floor 50**: impossible today (the gate is checked at start for every member and members cannot rebirth mid-run), but if `tower_high_floor` changes in content mid-run, the run ends `high_floor_locked` before paying the next cost.
- **If `zone(N)` would be a zone not yet live (a later wave)**: `zone(N)` takes the greatest live `level_min ≤ L`, so floors above zone_13's band use zone_13's tables and boss in Wave 2. Rewards then lag the floor level; accepted.
- **If an element has no live non-boss row, or a zone has no grade-1 material or boss row**: the content validator fails the build; at runtime it is fail code 19001 (unreachable for validated content).
- **If a floor's boss row is also a Golden Boss row** (`golden_bosses.monster_id` points at zone bosses): the tower fights it as a plain encounter (no raid scaling, no enrage). No conflict: the row is data.
- **If the app is saved between a floor's resolve and its deadline**: on load the fight is re-resolved with the same key and frozen inputs and gives the same result (RNG R5, R6).
- **If the player reloads a save to retry a failed floor**: `run_ordinal` is saved, so the same run re-rolls the same dice; a *new* run gets a new ordinal and new dice. Retrying is possible but costs the floor's materials each time. Save-scumming yields at most the same outcome (RNG Edge Cases).
- **If a stronger group retries a floor that another group failed**: allowed; the floor's reward is still unclaimed until someone clears it.
- **If the group is one healer**: it deals little damage and times out; the run ends `timeout` on floor 1 of that run. The panel warns before start when the group has no damage dealer (UI Requirements).
- **If `best_floor` reaches the formula's guard (10⁶)**: unreachable in practice (F2 makes floor 1,000 about 29× HP and damage); the invariant check rejects a save above it.
- **If a Golden Boss slot comes due during a run**: tower members are not called (R12); the rest of the guild raids as usual.
- **If a member in the run is removed by a debug tool or migration**: the invariant check fails the load (Local save R6); content-level removal is not a player action.

## Dependencies

**Upstream (this system depends on)**

| System | Type | Interface | Status |
|---|---|---|---|
| Combat (10) | Hard | `resolve(encounter, gen)`, `FightResult`; F8 deadline tick; R3 encounter fields with a level-overridden monster row | GDD exists (PROVISIONAL: Combat accepts a row copy with `level` replaced, OQ-4) |
| Deterministic RNG (2) | Hard | Domain 15 `tower`; `derive` | GDD exists |
| Zones and hunt trips (11) | Hard (data) | `zones.csv` bands and `boss_monster_id`; `monsters.csv` rows | GDD exists |
| Items and loot tables (26) | Hard | Storage `take`/`give`; guild loot roll with source tag 2, `luck_milli = 1000`, roll count | GDD exists (PROVISIONAL roll count and source-tag call, OQ-5) |
| Guild and buildings (30) | Hard | `effect(bld_tower, floor_cap)` | GDD exists |
| Member model (8) | Hard | Stats, `hp`, `hp_max`, rebirth tier field | GDD exists |
| Member state machine (41) | Hard | `tower` state; `idle`, `dead` transitions | **PROVISIONAL: no GDD** — assumes a `tower` state that blocks gear, training, school change and rebirth |
| Rebirth and Ascension (23) | Hard | Member's cumulative tier rewards incl. `unlock_tower_high` | **PROVISIONAL: no GDD** — assumes rewards are cumulative per member |
| Sim core (1), Data layer (3), Event bus (4), Command layer (5), Local save (6) | Hard | Phases, content tables, type block, commands, save section | GDDs exist |
| Gold economy (27) | Soft | `tower_reward` mint to the fund | GDD exists (entry type 13, OQ-6 resolved) |
| Offline progress (31) | Soft | Exact advance of an active run | **PROVISIONAL: no GDD** |

**Downstream (depend on this system)**

| System | Type | Interface |
|---|---|---|
| Golden Boss raid (14) | Soft | Tower members ineligible (PROVISIONAL) |
| Retention (16) | Soft | Leave checks deferred during a run (PROVISIONAL) |
| Leaderboards (35), Quests (25) | Soft | `best_floor`, events 1902, 1905 |
| Realtime world view (38), UI | Soft | Events 1901–1905, fight timeline |

## Tuning Knobs

`systems-designer` lens (Section G) applied; every `data file` variable of D is a knob. All live in `sim_params.csv` (PROVISIONAL, OQ-3) except `floor_cap` (`buildings.csv`, Guild and buildings) and `unlock_tower_high` (`rebirth.csv`, Rebirth).

| Knob | Today | Safe range | Too high | Too low |
|---|---|---|---|---|
| `tower_base_level` | 40 | 20–80 | A new tower is a wall; first floors fail | Early floors are free loot |
| `tower_level_step_milli` | 1600 | 800–3000 | The tower outruns the zone ladder; most guilds stall early | Floors 50+ are easy; high-floor gate is the only wall |
| `tower_boss_every` | 10 | 5–20 | Few walls, few big rewards | Boss walls every few floors; runs end on bosses |
| `tower_time_limit_s` | 300 | 60–600 | Slow parties win by attrition; long CPU per floor | Boss floors time out before they could be won |
| `tower_floor_gap_s` | 2 | 0–30 | Runs drag for no reason | 0 is fine; runs feel instant |
| `tower_rest_heal_pct` | 0.10 | 0–0.3 | Attrition disappears; runs go until a wall | Every run ends `low_hp` after 2–3 floors |
| `tower_retreat_hp_pct` | 0.30 | 0–0.6 | Runs end early, few deaths | Groups climb into deaths (revive time) |
| `tower_floor_cost` | 4 | 0–20 | Tower starves crafting and buildings of materials | No sink |
| `tower_boss_cost_mult` | 2 | 1–5 | Boss floors unaffordable | Boss floors cheap |
| `tower_reward_rolls` | 2 | 1–5 | Tower out-earns hunting per material | Normal floors not worth the cost |
| `tower_reward_rolls_boss` | 1 | 1–3 | Boss floors flood rare gear | — |
| `tower_high_floor` | 50 | 20–90 | Rebirth 2 reward feels empty | Most of the tower is locked behind rebirth 2 |
| `tower_overcap_hp_step`, `_dmg_step` | 0.02 | 0.005–0.05 | The endless climb stalls a few floors past 101 | Endless floors barely harder; leaderboard floods with huge floors |
| `tower_endless_from` | 100 | 100 (fixed by decision) | — | Must equal `bld_tower`'s top `floor_cap`; rewards stop above it |
| `tower_run_floor_max` | 100 | 20–200 | Long offline resolves (R11, AC-27) | Endless climbers restart runs often |
| `tower_party_max` | 5 | 3–5 | Must match Party's max (§6.12) | Healer or buffer crowded out |

**Knobs that interact:** `tower_rest_heal_pct` and `tower_retreat_hp_pct` together set run length; raising heal makes the retreat check rarer. `tower_floor_cost` and `tower_reward_rolls` set the net sink (F5 sink check); change them together. `tower_level_step_milli` and `tower_high_floor` decide whether the rebirth gate or raw difficulty is the wall at floor 50. Combat's `monster_dmg_factor`, `healer_heal_frac` and `buffer_dmg_reduction` (Combat Tuning Knobs) shift every floor's difficulty at once and are pointed to, not duplicated.

## Visual/Audio Requirements

`art-director` lens applied; no art bible exists yet (`/art-bible` not run), so these are intents, not specs.

- **Building:** `bld_tower` is a tall pixel-art pagoda on the guild map; visible height steps with building level (3 silhouettes over 10 levels is enough for a solo dev).
- **Tower view:** a vertical shaft of floors with a floor number plate; the group's sprites stand on the current floor; the floor monster in its element's palette (Five Elements colour coding shared with zones: Kim white-gold, Mộc green, Thuỷ blue, Hoả red, Thổ ochre).
- **Floor clear:** a short "seal breaks" flash and the plate number ticks up (≤ 0.5 s). Boss floor: a red banner "Tầng 40 — Boss" before the fight and a gold flash on clear.
- **Run end:** result card naming the end reason in words (R7 reasons) with floors cleared and loot summary.
- **Audio:** one ascending chime per cleared floor, a heavier gong for boss floors, a low drum for wipe/timeout. Uses Audio (40)'s shared cues where possible; no new music track required.
- **Off-screen:** when the tower view is closed, no sprites render; a small badge on the building shows the current floor.

## Game Feel

- **Cadence:** a floor resolves in seconds to a minute of world time; the player should see the counter move at least every ~60 s on a healthy run, and a run should feel like a short tense sequence, not a background bar.
- **Readability over spectacle:** the timeline (Combat R14) plays at 1× with damage numbers capped like the raid (≤ 15 sprites, limited numbers, Golden Boss §6.13 guidance); members' HP bars must be readable on a phone because HP carry-over is the tension.
- **Decision weight:** starting a run is one confirm with the cost shown; retreat is one tap and takes effect at the end of the current floor (stated on the button: "Retreat after this floor").
- **No reroll feel:** the same group at the same state retrying gets fresh dice per run but the result is dominated by strength; the summary always explains the loss (element countered, no healer, timeout) so the player knows what to change.

## UI Requirements

- **Tower panel** (from the building): best floor, `floor_cap` (or "Endless" once R1a applies), the guild's tower title and a note that floors above 100 award title/leaderboard standing only, next floor preview (number, level, element, boss flag, zone tables rewarded, material cost and stock), last run summary.
- **Group picker:** up to 5 idle members; shows element vs next floors (counter / countered icons for the next 5 floors), role icons, and warnings: "no healer", "no damage dealer", "member X lacks rebirth 2 for floor 51+". Refusal reasons from 1904 map to plain messages.
- **Run view:** floor counter, group HP bars, current monster, retreat button.
- **Notifications:** run end (local push, 46, later) and a history log line (1903 logged).
- Localization keys for every reason string (Localization 39). UX spec to be authored with `/ux-design` when the tower is scheduled.

## Cross-References

| This document references | Target GDD | Specific element | Nature |
|---|---|---|---|
| Floor fight | `combat.md` | R2, R3, R4, R14, F1, F8 | Rule dependency |
| Domain 15 and key rules | `deterministic-rng.md` | R3, R4 (`rng_domain_tower` = 15), R5, R6, R10 | Rule dependency |
| Loot source tag 2, storage, guild roll | `items-and-loot-tables.md` | R3, R3a, R7, R9a | Rule dependency (PROVISIONAL extension) |
| `floor_cap`, capacity keys, upgrades | `guild-and-buildings.md` | R6, R7, R8 | Data dependency |
| Zones and monster rows | `zones-grounds-monsters-and-hunt-trips.md` | Zone bands, boss rows | Data dependency |
| Member stats and equip refusal | `member-model.md` | R6 | Rule dependency |
| `tower_reward` mint | `gold-economy.md` | R3 entry types | Entry type 13 |
| Save section | `local-save-and-migration.md` | R6 | Rule dependency |
| Event and command blocks | `event-bus-and-history-log.md`, `command-layer.md` | Event bus R3; owner × 100 blocks | Rule dependency |
| Phases and handler orders | `sim-core-and-tick-loop.md` | P1, P3, P4; R4, R10 | Rule dependency |
| Source design | `JX1_Tycoon_GDD.md` | §6.3, §6.10 (tier 2), §7, §12.5, §20 S7 | Design intent |

## Acceptance Criteria

*(qa-lead lens applied. "Logic" = automated unit test in `tests/unit/endless_tower/`; "Integration" = real Sim core, Combat, Items and Guild and buildings; "UI" = retained screenshot in `production/qa/evidence/`.)*

- **AC-1 [Logic] (R1)**: **GIVEN** a guild with no `bld_tower`, **WHEN** `tower_start([m1])` is submitted, **THEN** it is refused with 1904 reason 2 and no state changes.
- **AC-2 [Logic] (R5 start)**: **GIVEN** `bld_tower` level 1, `best_floor = 0`, 3 idle members and 10 `mat_z05_1` in storage, **WHEN** `tower_start([a,b,c])` is applied, **THEN** `run_ordinal = 1`, storage holds 6 `mat_z05_1`, the run has `floor = 1`, the three members are in `tower`, and one 1901 event is emitted.
- **AC-3 [Logic] (R5 refusals)**: **GIVEN** each of the seven refusal conditions in turn (active run; no tower; 0 or 6 members or a duplicate; a hunting member; `best_floor = floor_cap`; floor 51 with a tier-1 member; storage short by 1 unit), **WHEN** `tower_start` is applied, **THEN** the refusal reason is 1…7 respectively and storage, `run_ordinal` and member states are unchanged.
- **AC-4 [Logic] (R3)**: **GIVEN** an active run, **WHEN** a second `tower_start` is applied, **THEN** it is refused with reason 1.
- **AC-5 [Logic] (F1)**: **GIVEN** default knobs, **WHEN** `floor_level` is computed for N = 1, 10, 37, 50, 51, 100, 101, 102, **THEN** the results are 40, 54, 97, 118, 120, 198, 200, 200.
- **AC-6 [Logic] (F2)**: **GIVEN** default knobs, **WHEN** scales are computed for N = 100, 102 and 150, **THEN** `hp_scale` is 1.0, 1.02 and 2.56 and `dmg_scale` equals `hp_scale`.
- **AC-7 [Logic] (F3)**: **GIVEN** today's content, **WHEN** the floor monster is computed for floors 37 and 40, **THEN** floor 37 is the 8th live non-boss Hoả row by `uid` at level 97, and floor 40 is `m_z11_boss` at level 102; computing it twice draws nothing from any generator.
- **AC-8 [Logic] (F3 coverage)**: **GIVEN** floors 1–5, **WHEN** their elements are listed, **THEN** they are moc, hoa, tho, kim, thuy.
- **AC-9 [Integration] (R7, R8)**: **GIVEN** a run on floor N, **WHEN** the floor resolves, **THEN** Combat `resolve` is called once with one group in pick order, the level-overridden row, F2 scales, interval 1.0, 1 target, no enrage, limit 300 s, and a generator from `derive(15, [run_ordinal, N])`.
- **AC-10 [Integration] (R7 timing)**: **GIVEN** a floor fight with `duration_s = 15.6` resolved at tick T, **WHEN** ticks advance, **THEN** member HP changes exactly at tick T + 157 and not before.
- **AC-11 [Integration] (R9 rewards)**: **GIVEN** floor 37 cleared in run 4, **WHEN** P4 runs that tick, **THEN** two rolls of `drop_zone_10` are made in one loot event keyed `[0, 2, 4, 37]` with luck 1000, items and materials land in guild storage, and the gold is credited to the fund as `tower_reward`; `best_floor = 37`.
- **AC-12 [Integration] (R9 order)**: **GIVEN** storage holds 0 `mat_z10_1` and floor 37's reward rolls 3 `mat_z10_1`, **WHEN** floor 37 is cleared, **THEN** the reward is added, 3 < 4 so the run ends `no_material`, and storage holds 3.
- **AC-13 [Logic] (F5)**: **GIVEN** default knobs, **WHEN** the costs of floors 37 and 40 are computed, **THEN** they are 4 `mat_z10_1` and 8 `mat_z11_1`.
- **AC-14 [Logic] (F6)**: **GIVEN** survivors at 900/3,000 and 1,500/2,500, **WHEN** the rest heal and retreat check run, **THEN** HP becomes 1,200 and 1,750 and the run continues; **GIVEN** survivors at 300/3,000 and 400/2,500, **THEN** HP becomes 600 and 650, ratio 0.227 < 0.30, and the run ends `low_hp`.
- **AC-15 [Logic] (F7)**: **GIVEN** `best_floor = 50` and a group where one member is rebirth tier 1, **WHEN** `tower_start` is applied, **THEN** it is refused with reason 6; with every member at tier 2 it is accepted.
- **AC-16 [Integration] (R7 deaths)**: **GIVEN** a floor where one of three members dies and the fight is won, **WHEN** the result applies, **THEN** the dead member leaves the run and enters `dead`, the next floor's encounter has two members.
- **AC-17 [Integration] (end reasons)**: **GIVEN** fixtures for wipe, timeout, `top_reached` and `retreat`, **WHEN** each run ends, **THEN** event 1903 carries reason 1, 2, 5, 4, every remaining member is `idle` with its current HP, and `run` is null after P4 of that tick.
- **AC-18 [Logic] (R6)**: **GIVEN** a run in `Fighting` that will be won, **WHEN** `tower_retreat()` is applied, **THEN** the floor completes, its loot is paid, and the run ends with reason 4; no material is refunded.
- **AC-19 [Logic] (no replay)**: **GIVEN** `best_floor = 12` after a run, **WHEN** a new run starts, **THEN** it starts at floor 13 and floors 1–12 are never fought or rewarded again.
- **AC-20 [Logic] (R10)**: **GIVEN** any run, **WHEN** it ends, **THEN** no member's XP or wallet changed.
- **AC-21 [Integration] (save/load determinism)**: **GIVEN** a run saved mid-`Fighting`, **WHEN** the save is loaded and play continues, **THEN** every member's HP, `best_floor`, storage and the 1902/1903 events are bit-identical to an uninterrupted run.
- **AC-22 [Integration] (offline, PROVISIONAL R11)**: **GIVEN** an active run and 2 h offline, **WHEN** the guild is reopened, **THEN** the run's state equals that of the same run advanced in realtime over 2 h.
- **AC-23 [Integration] (R12)**: **GIVEN** members in a run when a Golden Boss slot comes due, **WHEN** the raid gathers, **THEN** none of them participates.
- **AC-24 [Logic] (F8 budget)**: **GIVEN** a 100-floor fixture run, **WHEN** it completes, **THEN** no tick emitted more than 3 tower events and the run emitted 1 + 100 + 10 + 1 events.
- **AC-25 [Logic] (validator)**: **GIVEN** content with an element that has no live non-boss monster, or a zone with no grade-1 material, **WHEN** the content validator runs, **THEN** it reports an error naming the element or zone.
- **AC-26 [UI]**: **GIVEN** the tower panel with a group lacking a healer and a member lacking rebirth 2 at `best_floor = 50`, **WHEN** it is displayed, **THEN** both warnings are visible and the start button shows reason 6; screenshot retained.
- **AC-28 [Logic] (R1a endless)**: **GIVEN** `bld_tower` level 10 (`floor_cap` 100) and `best_floor = 100`, **WHEN** `tower_start` is applied, **THEN** it is accepted with `floor = 101` (no refusal 5); **GIVEN** `bld_tower` level 9 and `best_floor = floor_cap`, **THEN** it is refused 5.
- **AC-29 [Integration] (R1a no rewards)**: **GIVEN** an endless run that clears floors 100 and 101, **WHEN** P4 runs, **THEN** floor 100 pays its normal reward, floor 101 rolls no loot, mints no `tower_reward` gold, puts nothing in storage, and `best_floor = 101`.
- **AC-30 [Logic] (run_limit)**: **GIVEN** an endless tower and a group strong enough to keep winning, **WHEN** the run clears `tower_run_floor_max` (100) floors, **THEN** it ends with 1903 reason 8 and the next run starts at `best_floor + 1`.
- **AC-27 [Logic] (performance)**: **GIVEN** a 100-floor run fixture, **WHEN** resolved headless, **THEN** total resolve time is under 50 ms on the reference desktop and no more than one floor fight resolves per tick.

## Open Questions

| ID | Question | Owner | Resolve by |
|---|---|---|---|
| OQ-1 | **RESOLVED (user decision 2026-11-16):** yes. `bld_tower` gates floors up to 100; once it reaches `floor_cap` 100 the floor cap is removed and the tower is endless with F2's linear scaling (R1a). Rewards above floor 100 are title/leaderboard only — no gold, no items — so the economy is unaffected. New knobs `tower_endless_from` (100) and `tower_run_floor_max` (100, per-run bound for offline and events); new end reason 8 `run_limit`. No `buildings.csv` change is needed. | User / Guild and buildings (30) | Closed |
| OQ-2 | PROVISIONAL: Member state machine (41) — adds a `tower` state entered from `idle`, left to `idle` or `dead`; blocks equip, training, school change and rebirth. | Member state machine (41) | When 41 is designed |
| OQ-3 | PROVISIONAL / schema: the 15 tower knobs (13 plus `tower_endless_from` and `tower_run_floor_max`, 2026-11-16) are new keys in `sim_params.csv` (key/value file, no column change). Data layer to confirm and the content validator to add checks (steps ≥ 1, rolls ≥ 1, element pools non-empty). | Data layer (3) | Implementation |
| OQ-4 | PROVISIONAL: Combat (10) — accepts a monster row copy with `level` replaced by the tower floor level (R8). Combat R5 reads the level from the row, so no rule changes; confirm no row-identity assumption. | Combat (10) | Consistency pass |
| OQ-5 | **RESOLVED (consistency-check 2026-11-16):** Items R9a adds `roll_guild_loot_keyed(key, loot_table, level, rolls)`; this system calls it with `[0, 2, run_ordinal, floor]` (Items R3 reserves source tag 2). | Items and loot (26) | Closed |
| OQ-6 | **RESOLVED (consistency-check 2026-11-16):** Gold economy R3 assigns `tower_reward` entry type 13 (mint → fund, Full Vision). | Gold economy (27) | Closed |
| OQ-7 | PROVISIONAL: Rebirth and Ascension (23) — tier rewards are cumulative per member, so `unlock_tower_high` holds for tiers ≥ 2; and members cannot rebirth while in `tower`. | Rebirth (23) | When 23 is designed |
| OQ-8 | PROVISIONAL: Offline progress (31) advances an active run exactly (R11); Golden Boss (14) treats tower members as unavailable; Retention (16) defers leave checks. | 31, 14, 16 | When each is designed |
| OQ-9 | CD-GDD-ALIGN concern: no repeatable reward means a guild at `floor_cap` has nothing to do in the tower until the next building level. *Partly answered 2026-11-16:* at `bld_tower` 10 the tower is endless (R1a), so a top guild always has a next floor, for title and leaderboard only. Is a weekly "re-climb" (reset to a checkpoint with reduced rewards) wanted? Scope addition, not made here. | User / game-designer | Wave 2 playtest |
| OQ-10 | CD-GDD-ALIGN concern / balance: winnability of floors against real Wave 2 rosters, and whether a 4-unit cost per floor is a meaningful sink next to crafting and buildings, must be measured with the balance simulator (a `sim/tower.py` reference per S7). | systems-designer / economy-designer | Before implementation (S7) |
| OQ-11 | Should the tower panel show a predicted win chance for the next floor (a headless dry-run)? Useful for the "verdict" fantasy but costs CPU and risks feeling like rerolling. | ux-designer | `/ux-design` for the tower |
