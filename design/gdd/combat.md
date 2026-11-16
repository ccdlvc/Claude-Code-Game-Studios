# Combat

> **Status**: Designed (revised 2026-11-16, pending re-review)
> **Author**: user + Claude (autonomous batch run, decisions in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet). Serves the core guild loop, `JX1_Tycoon_GDD.md` §1, and the locked decision "Chiến đấu: Realtime trên map" (§2)
> **Mode**: Retrofit. The built behaviour is `fight()` in `sim/hunt.py` and the raid loop in `sim/raid.py`; this GDD makes that behaviour the specification and marks every gap.

## Summary

Combat resolves one fight between a group of guild members and one monster or boss: who acts when, how much each hit does after defence and the Five Elements, who the monster hits, who the healer saves, and who dies. The player never presses an attack button. They win fights by who they recruit, which school and element they field, how they gear and party their members, and which ground they send them to. Combat exists so that those management choices have a fair, readable and deterministic result that hunting, the Golden Boss raid, offline progress and leaderboard replay all share.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Sim core and tick loop, Deterministic RNG, Member model, Schools and school change, Skills, Data layer and content pipeline`

## Overview

Combat is a pure resolver inside the headless simulation core. A caller (Zones and hunt trips for ordinary fights, Golden Boss and guild raid for the hourly boss, later Endless Tower and Arena) hands it an **encounter**: the fighting members with their current HP, the monster row, the encounter parameters, and a fresh random generator. Combat runs the whole fight at once on an event timeline (members and the monster each act on their own interval, the earliest action goes next) and returns a **fight result**: win or loss, duration, each member's HP afterwards, who died, and how much each member dealt, healed and took. It writes nothing itself; the caller applies the result. Damage follows one formula in each direction: attacker power × Five Elements multiplier × a small random spread × a defence factor that depends on the encounter level. Role behaviour is data: tanks draw the monster's attacks, healers heal the most hurt ally below a threshold, and a buffer in the party raises everyone's damage and lowers damage taken. For the player this is the system that turns a roster into results. A matched element hits 25% harder, a party without a buffer is visibly slower, and a fragile solo caster dies where a tank would not. Without it the game has no outcome to manage towards.

## Player Fantasy

The fantasy is the guild master watching a plan work. You read the ground's element, pick the party, and send them out. On screen a Kim swordsman tears through Mộc beasts with the counter bonus showing in every hit, the tank soaks the swarm, and the Thanh Mộc Cốc healer pulls a dying archer back above the line. You did not throw a punch, but every number in that fight is there because of a decision you made, and you can see which one.

Three moments carry it:

1. **The matchup pays off.** Moving a party to a ground its elements counter makes kills visibly faster. Five Elements is a lever, not decoration (`JX1_Tycoon_GDD.md` §4.2, §6.12 "Bãi sẽ chọn theo hệ chủ đạo khắc").
2. **The role earns its slot.** A party with a buffer and a tank survives and kills faster than five damage dealers. The warning "thiếu buffer" (§6.12) is true in the numbers, so following it feels like insight, not obedience.
3. **The hourly boss is everyone's fight.** In the Golden Boss the whole guild acts in the same resolver, and the contribution board shows the healer's and the tank's work next to the damage dealers' (§6.13).

What it must not feel like: a slot machine. The spread on a hit is ±10% and the dice for a fight are fixed by its key, so a reload gives the same fight (RNG R5). Losing comes from the plan, not from bad luck.

`creative-director` lens applied in this session, not as a spawned agent (skill rule). Reference feeling: Evil Hunter Tycoon's hunters on the map (§1), with Five Elements counters as the added layer of reading.

## Detailed Design

Specialist views applied before drafting (routing row "Combat, damage, health": primary `game-designer`; supporting `systems-designer`, `ai-programmer`, `art-director`):

- **game-designer** — The player's decisions sit outside the fight: roster, school, element, gear, party, ground. Combat must make each of them legible in the result: element counters, role coverage, level gap. The player cannot target, cast, retreat mid-fight or use items mid-fight. Retreat belongs to the hunt trip (flee below `flee_hp_pct`, Zones and hunt 11), between fights.
- **systems-designer** — The built loop has five hard-coded numbers (600 s limit, 0.8 heal threshold, 1.0 s member interval, 1.0 s monster base interval, ±10% spread). They become named knobs here. The raid loop duplicates the fight loop with three differences that are all parameters, so one resolver can serve both. The draw order is a contract (RNG R7) and must be written down exactly.
- **ai-programmer** — In-fight "AI" is three fixed rules (tank aggro share, healer threshold, earliest-action-next). There is no perception and no scoring in a fight. Utility AI (12) decides where to fight, not how. When real skills arrive (S4), skill choice inside a fight must stay a rule with no draws, so it does not change the dice.
- **art-director** — Fights resolve instantly in the simulation, but the player watches them in real time. The result must carry an optional timeline of actions so the world view can play the fight back faithfully, hit by hit, and never show a different fight from the one that happened.

No conflict between the views needed a user decision. Decisions taken autonomously are logged in `production/session-logs/decision-log.md`.

### Core Rules

**R1 — Combat is a resolver, not a tick handler.** Combat registers no Sim core handler and emits no events. It is a pure function `resolve(encounter, gen) -> FightResult` called from inside the caller's handler (normally Zones and hunt 11, in phase P3 `field`). It reads only its arguments and read-only content tables, and it changes nothing outside the `FightResult` it returns. The caller applies the result to members, awards XP and loot, and emits events.

**R2 — One fight is one atomic random event.** A fight resolves completely in one call, inside one tick (decision: atomic timing model). It uses exactly one generator, created by the caller with `derive(domain_id, key)` for that fight (RNG R3) and discarded after. There is no partial fight state, so a save never holds a fight in progress. The fight still *takes time* in the world: the result carries `duration_s`, and a realtime caller applies the result at the deadline tick (F8). Between the start tick and the deadline tick the members are in combat, and their HP as seen by other systems is the HP before the fight.

**R3 — The encounter.** The caller supplies:

| Field | Meaning |
|---|---|
| `groups` | One or more ordered lists of members. A hunt fight has one group (the party, or a solo member as a group of one). A raid has one group per party, temporary parties included (Party 13, Golden Boss 14). Buffs and heals act within a group (R8, R9); a group's own slot order breaks heal-target ties (R7). |
| `order` | The **combatant order**: every member of `groups` exactly once, in the order the caller gives. A hunt fight passes the group's slot order. A raid passes its participant list (Golden Boss R8), which need not follow the groups. |
| `start_hp[member]` | Each member's HP at fight start (binary64, R4a). A hunt passes the member's current HP; the raid passes `hp_max`; the Arena passes `hp_max` or the HP carried from its previous duel (Arena R6). Combat never reads stored HP itself. |
| `monster` | A row with the `monsters.csv` fields (level, element, hp/atk/def multipliers, speed). Normally a `monsters.csv` row; a caller may build one (the Arena champion, Arena F1), and that caller validates it with the same content rules (level ≥ 1, speed > 0, multipliers > 0) before calling. |
| `hp_part_scale`, `hp_raid_scale`, `dmg_scale` | Multipliers on the monster's HP (two separate factors, applied in this order, F1) and on its hit. All 1.0 for a hunt fight. Raid: `hp_part_scale = 1 + hp_per_participant × n`, `hp_raid_scale = raid_hp_mult`, `dmg_scale = raid_dmg_mult` (Golden Boss 14 owns these values). The two HP factors are never pre-multiplied: `(M × X) × R` and `M × (X × R)` differ in binary64 (measured: 14,036 of 40,000 cases). |
| `attack_interval_base_s` | The monster's base attack interval before speed. 1.0 for a hunt fight; `raid_boss_interval_s` for a raid. |
| `targets_per_attack` | How many different members one monster attack hits. 1 for a hunt fight; `raid_boss_targets` for a raid. |
| `enrage_every_s`, `enrage_atk` | Enrage step. Disabled (no step) for a hunt fight; `raid_enrage_every_s`, `raid_enrage_atk` for a raid. |
| `time_limit_s` | The fight is lost past this time. `fight_time_limit_s` for a hunt fight; `raid_time_limit_s` for a raid. |
| `want_timeline` | Whether to record the action timeline (R14). Does not change the outcome. |

Only members of `order` with `start_hp > 0` take part, in `order`. The combatant order decides every action tie (R6), the order of the start-up draws (R13) and the order of the monster's target pool (R10). The group slot order decides only heal-target ties (R7).

**Reference parity (decision D5, 2026-11-16: Combat matches the reference code exactly; no `sim_version` bump).** With the hunt values above, `order` = the party's slot order and `start_hp` = current HP, the resolver reproduces `fight()` in `sim/hunt.py` bit for bit. With the raid values, `order` = the `members` list passed to `simulate_raid()`, `groups` = `form_parties(members)` and `start_hp = hp_max` for everyone, it reproduces `simulate_raid()` in `sim/raid.py` bit for bit. The reference draws start-ups, breaks action ties and builds the target pool in raw `members` order, while a heal picks within `parties[pi]` in party order; `order` and `groups` encode exactly those two orders. Every hunt-only value is either the identity (×1.0) or a disabled step, and multiplying a binary64 by 1.0 is exact. How a caller builds `groups` and `order` is the caller's (Golden Boss R7–R8); parity is a property of the resolver on given inputs. (Decision: one resolver for hunt and raid.)

**R4 — Combatant stats are a snapshot.** At the start of the fight Combat reads, for each member, the Member model (8) `profile(member)` integers, the element from Schools (20) (none for an unaffiliated member), the school's `role` and `buff_role`, and `start_hp` from the encounter. A change to equipment, school or level during the fight's world time does not affect it (consistent with RNG R5: changed inputs, same dice, applied to the next fight). Member model's "level rises mid-fight" edge case therefore means the *next* fight reads the new profile; the fight in progress keeps its snapshot.

**R4a — Integer boundary.** Member model stores integers (`dps_milli`, `hp_max_milli`, `def_milli`, `hp_milli`); Combat runs in binary64 (Formulas, OQ-3). The conversion is fixed:
- **In:** `dps = dps_milli / 1000`, `hp_max = hp_max_milli / 1000`, `def = def_milli / 1000`, and for a hunt `start_hp = hp_milli / 1000`: each a correctly rounded binary64 division of an integer below 2⁵³.
- **Out:** the caller writes `hp_milli = 0` for a member in `died`, otherwise `hp_milli = min(hp_max_milli, max(1, round_half_away(hp_after × 1000)))`. A survivor never rounds to 0, and an untouched member's HP round-trips exactly. `dealt`, `healed` and `taken` stay binary64 for the caller (Golden Boss F3). Combat itself writes nothing (R1): Member model lists Combat (10) as the writer of `hp_milli`, and that write is this rule, applied by the caller at the deadline tick on Combat's behalf.
- **Parity:** the reference reads float stats from `sim/model.py`, which differ from Member model's integer profile by up to 0.001 (Member model F3). Parity vectors (AC-1, AC-2) feed both implementations the same binary64 stats; profile parity is Member model AC-11/AC-12's.
- Gear stats outside the profile (`gear_stat(member, crit_rate)`, Member model OQ-4) are ignored in stage 1; they become inputs only through a stage-2 kind handler (R15).

**R5 — Monster stats.** The monster's max HP, hit and defence come from F1 at the monster's level and the row's multipliers, then `hp_scale` and `dmg_scale`. The monster's level is also the **encounter level** used by the defence factor in both directions (F2).

**R6 — The event timeline.** Each combatant has a next-action time; the monster has a next-attack time. Members act every `member_action_interval_s` seconds. The monster attacks every `attack_interval_base_s / speed` seconds. The loop:

1. Let `alive` be the combatants with HP > 0. If `alive` is empty, the fight is **lost**. If the current time `t` is greater than `time_limit_s`, the fight is **lost** (timeout).
2. Take the alive member with the earliest next-action time. On a tie, the one earliest in combatant order.
3. If that time is less than or equal to the monster's next-attack time, the member acts (R7); set `t` to that time and add `member_action_interval_s` to the member's next-action time. Members win ties with the monster.
4. Otherwise the monster attacks (R10); set `t` to the monster's next-attack time and add the monster's interval to it.
5. If the monster's HP is at or below 0, the fight is **won** at time `t`. Otherwise go to 1.

The timeout check runs only at the top of the loop, so an action at a time just past `time_limit_s` (scheduled while `t ≤ time_limit_s`) can still kill the monster: `won = true` with `duration_s > time_limit_s` is possible, by at most one action interval (as built; AC-7).

Time is a binary64 number of seconds from the fight's start. The loop is event-driven; it never steps by tick (`GODOT_PORT.md` rule 5).

**R7 — A member's action.** In MVP stage 1 (built today) a member's action is one of:

- **Heal**, if the member's role is `healer_support` and the alive member of its own group with the lowest HP fraction (ties: earliest in the group's slot order, as the reference's `min` over `parties[pi]`; in a hunt fight this is the combatant order; the healer may pick itself) is below `healer_heal_threshold`. The target gains F6 HP, capped at its `hp_max`. The heal replaces the attack for that action.
- **Attack** otherwise. The monster loses F4 damage.

From MVP stage 2 (real skills, §20 S4) the attack is replaced by the skill rule in R15. The heal rule stays as the healer's fallback when no healing skill is ready.

**R8 — The buffer bonus.** A group "has a buffer" if any of its combatants at fight start belongs to a school with `buff_role = true` (today `moc_1`; Wave 2 adds `thuy_2`). Every member of that group gets `+buffer_atk` to its attacks and takes `buffer_dmg_reduction` less damage. The bonus does not stack with a second buffer and lasts the whole fight, even if the buffer dies. A buffer does not have to be a healer, and a healer is a buffer only through its school's `buff_role`.

**R9 — Group scope.** Heals target only the healer's own group, and the buffer bonus covers only the buffer's own group. In a hunt fight there is one group, so this is the whole party.

**R10 — The monster's attack.** Each attack hits `targets_per_attack` different alive members, picked one after another from a pool that starts as all alive members in combatant order and loses each pick:

- The pool starts as the alive members in combatant order (`order`), not in group order.
- If the pool holds at least one tank (school role `tank` or `tank_guardian`), draw `u`; if `u < tank_aggro_share`, pick a tank from the pool with `choice`, otherwise pick any member of the pool with `choice`.
- If the pool holds no tank, pick any member of the pool with `choice`.
- If the pool is empty, the attack ends early.

Each picked target loses F5 damage. A target reaching HP ≤ 0 is set to exactly 0 and **dies** (R11). Monsters in stage 1 have only this basic attack; the `ai_skills` column is not executed yet (Open Questions).

**R11 — Death.** A dead member takes no further action, cannot be targeted or healed in this fight, and stays dead in the result. Combat does not revive anyone. Revival, the Linh Miếu wait and the trip's end are the caller's (Zones and hunt 11: `revive_s`; Golden Boss 14: Linh Miếu). Deaths reach other systems only as `FightResult.died`, reported by the caller (Zones 1103, Golden Boss R9); lifetime death counts are Dev tooling (43) instrumentation derived from events, not state (Member model R1).

**R12 — Element multiplier.** Every hit, in both directions, is multiplied by F3 for the attacker's element against the defender's element. A member with no school has no element and is neutral, ×1.0 both ways (this answers Schools and school change OQ-4).

**R13 — Draw order (contract, RNG R7).** Inside one fight, draws happen in exactly this order:

1. For each combatant in combatant order: one `random()`, `u`; the member's first action is at `u × member_action_interval_s`.
2. One `random()`, `u`; the monster's first attack is at `u × (attack_interval_base_s / speed)`.
3. Then, as the loop runs: each **member attack** draws one `random()` for the spread (F4). A **heal** draws nothing. Each **target pick** of a monster attack draws one `random()` for the tank check if the pool holds a tank, then one `choice` (F5, whose bounded integer may use more than one `next_u32` under RNG F4's rejection). Monster damage has no spread and draws nothing.

Any change to this list (a new draw, a reorder, a removed draw) is a breaking change to the combat parity vectors and needs a `sim_version` bump (Sim core R12, Dev tooling 43). `GODOT_PORT.md` rule 2 says a monster attack draws its target "and then the spread"; the code has no monster spread, and this GDD follows the code (Open Questions OQ-9).

**R14 — The fight result.** `resolve` returns:

| Field | Meaning |
|---|---|
| `won` | true if the monster's HP reached ≤ 0 |
| `reason` | `won`, `wiped` (no alive combatant) or `timeout` |
| `duration_s` | `t` when the fight ended (binary64 seconds) |
| `monster_hp_left` | ≥ 0; 0 on a win (the raid reports it) |
| `hp_after[member]` | each combatant's HP at the end, 0 for the dead |
| `died` | combatants who died, in the order they died |
| `dealt[member]` | total F4 damage, before the monster's HP is clamped (as built: the killing blow counts in full) |
| `healed[member]` | HP actually restored by this member's heals, after the `hp_max` cap |
| `taken[member]` | total F5 damage received, capped at the HP the member had (no overkill) |
| `timeline` | only if `want_timeline`: one record per action — time, actor, kind (attack / heal / monster attack), target, amount, target HP after, and whether the target died |

`dealt` is what `fight()` returns as `contrib` today. `healed` and `taken` are new, consume no draws and do not change outcomes; Golden Boss raid (14) uses them in its contribution score (§6.13).

**R15 — Skill execution (MVP stage 2, §20 S4).** When real skills replace the flat `skill_dps_bonus`:

- Skills (21) owns the skill rows, the closed effect vocabulary and **each key's kind** (Skills R2: damage, damage over time, heal and restore, modifier, control, shape, spawn, trigger; a key never changes kind). Combat implements **one handler per kind** and reads the key's parameters; it never branches on a skill ID, school ID or slot (Skills R2, systems index per-system notes). A kind without a Combat handler is a content error caught by the validator, not a silent no-op. Combat reads each member's loadout and passive sheet from Skills R9 (the resolved kit).
- **Mana, cooldowns and casting** are Combat's in-fight state (Skills R1, OQ-4): the MP pool and cooldown timers live only inside one `resolve` call. The base MP maximum and regeneration per member are not defined by any GDD yet (OQ-11).
- **Passive** skills apply at fight start as part of the R4 snapshot.
- **Choosing an action** is a fixed rule with no draws: on each action, use the ready active skill with the highest `slot` (an ultimate before a basic active) whose cooldown has elapsed and whose MP cost the member can pay; otherwise use the basic attack (R7). A ready healing skill counts as the healer's heal.
- **Kinds** Combat must handle are Skills R2's; which key belongs to which kind is Skills R2's table, not this GDD's (for example `crit_rate`, `crit_dmg`, `def_ignore`, `element_dmg` and `hp_pct` are `modifier` keys there). Timed effects are scheduled on the same event timeline as R6.
- **Spatial keys** (`aoe_radius`, `knockback`, `dash`, `pull`, `range`) have no effect in a one-monster fight with no positions. They are kept in data for the world view and for multi-monster encounters (Open Questions OQ-5).
- **New draws** (a crit roll, a cleanse chance) come after the stage-1 draws of the same action, in the order the effects are listed in the row. Every data-driven chance (Skills `chance` values are ppm) is drawn with RNG `chance_ppm(k)` (RNG R8, F6). Their exact list is fixed when S4 is built and is a `sim_version` bump.

The S4 acceptance target stays §20's: each school completes a full fight, and role damage and effectiveness match `sim_roles.csv` within ±15%.

**R16 — Not combat's.** Choosing where to fight (Utility AI 12), forming parties (Party 13), picking the next monster and the gap between fights (Zones and hunt 11), fleeing at low HP, carrying loot, XP for the kill and the level-gap penalty (Zones and hunt 11, XP curve 22), drops (Items and loot 26), revive timers, potions used in fights (Gold economy 27 / S3), and the aggregate "sampled" resolution of off-screen and offline hunts (Zones and hunt 11, Offline progress 31). The aggregate path calls this resolver on sampled trips; it never uses a second combat formula.

### States and Transitions

A fight has a short lifetime inside one `resolve` call. A combatant has three states during it.

**Fight states**

| State | Entered when | Leaves to |
|---|---|---|
| `Running` | `resolve` starts and at least one combatant is alive | `Won`, `Wiped`, `Timeout` |
| `Won` | monster HP ≤ 0 after a member action | — (result returned) |
| `Wiped` | the top-of-loop check finds no alive combatant | — |
| `Timeout` | the top-of-loop check finds `t > time_limit_s` | — |
| `Empty` | `resolve` is called with no alive combatant | — (returns `won = false`, `reason = wiped`, `duration_s = 0`, no draws) |

**Combatant states**

| State | Condition | Can act | Can be targeted or healed |
|---|---|---|---|
| `Fighting` | HP > 0 | yes | yes |
| `Dead` | HP reached ≤ 0 this fight | no | no |
| `Absent` | dead or at 0 HP at fight start, or not in the encounter | no | no |

`Fighting → Dead` is the only transition; nothing in a fight leads out of `Dead`.

**From the caller's side (realtime)**: a member is "in combat" from the fight's start tick to its deadline tick (F8). This is reported to Member state machine (41) by the caller as part of `hunting`; Combat adds no member state of its own.

### Interactions with Other Systems

| System | Direction | Data | Owner of the interface |
|---|---|---|---|
| Sim core and tick loop (1) | in | Runs inside the caller's handler; `tick_rate` for F8; `ctx.derive` | Sim core R5 |
| Deterministic RNG (2) | in | One generator per fight: domain 1 `combat` for hunt fights (key layout below); the raid's own domain 6 for raid fights | RNG R3–R7; this GDD owns the domain-1 key and the draw order |
| Data layer (3) | in | `monsters`, `sim_params`, `sim_roles`, `schools`, `config` (element multipliers), later `skills` | Data layer R4 |
| Member model (8) | in / out | In: `profile` integers and `hp_milli` (converted by R4a). Out (via caller, R4a): `hp_milli` from `hp_after`, deaths | Member model owns stats and storage; Combat owns the conversion |
| Schools and school change (20) | in | `element` (or none), `role`, `buff_role` | Schools R2 |
| Skills (21) | in | Loadout and passive sheet (stage 2, Skills R9) | Skills owns the vocabulary and kinds; Combat owns one handler per kind |
| Zones and hunt trips (11) | out | Calls `resolve` per encounter; reads `FightResult`; uses `duration_s` | Combat owns `resolve` |
| Party (13) | in | Group membership and slot order | Party owns composition |
| Golden Boss and guild raid (14) | out | Calls `resolve` with raid encounter values; reads `dealt`, `healed`, `taken`, `monster_hp_left` | Raid owns the raid values and the contribution score |
| Offline progress (31) | out (indirect) | Through Zones and hunt's sampled trips | Zones and hunt |
| Realtime world view (38), Audio (40) | out (indirect) | `timeline` from the callers' side-effect-free queries (Zones `fight_timeline`, Golden Boss `raid_fight_timeline`), never as events | Caller owns the query; the world view plays back |
| Dev tooling and parity harness (43) | out | Golden vectors for `resolve` | Dev tooling owns the harness |
| Endless Tower (19), Arena (18) | out (Full Vision) | Call `resolve` under their own RNG domains; the Arena passes a caller-built champion row and `start_hp` (R3) | Combat owns `resolve`; the caller owns and validates its row |

**Domain-1 event key** (RNG R5, R6): `[party_id, trip_ordinal, encounter_ordinal]`, as Zones R5 and F9 define it. `party_id` is the `member_id` of the trip's key leader (Party R5; a solo hunter keys their own trips); `trip_ordinal` is that leader's saved `trips_led` counter, advanced only when a trip keyed on them starts; `encounter_ordinal` counts fights within the trip from 0. Unique because member IDs are never reused (Member model R2), a member keys at most one trip at a time and `trips_led` only increases. None of the three is player-mutable before the fight.

## Formulas

All formulas run in IEEE-754 binary64, evaluated left to right in the order written; a port must not reorder or fuse operations (`GODOT_PORT.md` rule 3). Results are not rounded inside a fight. (Decision: binary64 as built; integer fixed-point is Open Question OQ-3.) Values are today's, from `data/config.csv` and `data/sim_params.csv`.

`systems-designer` lens applied in this session: every variable was worked at its minimum, maximum and 0; findings are under each formula and in Edge Cases.

### F1 — Monster combat stats

The monster stat formulas are defined as:

`mon_hp = monster_hp_coef × L ^ monster_hp_exp × hp_mult × hp_part_scale × hp_raid_scale`
`mon_hit = monster_atk_coef × L ^ monster_atk_exp × atk_mult × monster_dmg_factor × dmg_scale`
`mon_def = monster_def_coef × L ^ monster_def_exp × def_mult`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L | int | 1–200 | data file (`monsters.level`) | Monster level, also the encounter level |
| monster_hp_coef, monster_hp_exp | float | 40, 1.3 | data file (`config.csv`) | HP curve (§4.2, calibrated) |
| monster_atk_coef, monster_atk_exp | float | 6, 1.25 | data file (`config.csv`) | Attack curve |
| monster_def_coef, monster_def_exp | float | 3, 1.2 | data file (`config.csv`) | Defence curve |
| hp_mult, atk_mult, def_mult | float | 0.7–22, 0.9–2.2, 0.7–2.0 in today's data | data file (`monsters.csv`) | Per-monster multipliers (bosses are high) |
| monster_dmg_factor | float | 0.05 | data file (`sim_params.csv`) | Global scale on monster hits; the main survival knob |
| hp_part_scale, hp_raid_scale, dmg_scale | float | 1.0 (hunt); raid values (R3) | calculated by caller | Encounter scaling; the two HP factors are applied one after the other, left to right, as `sim/raid.py` does |

**Output Range:** at multipliers 1.0: L1 hp 40, hit 0.30, def 3.0; L100 hp 15,924, hit 94.9, def 754; L200 hp 39,210, hit 225.6, def 1,731. All positive for L ≥ 1. L = 0 gives 0 HP (an instant win) and is rejected by the content validator (monster level ≥ 1).
**Example:** `m_z01_d` (L8, hp_mult 1.4, atk_mult 1.0, def_mult 1.3): `mon_hp = 40 × 8^1.3 × 1.4 = 835.9`, `mon_hit = 6 × 8^1.25 × 1.0 × 0.05 = 4.04`, `mon_def = 3 × 8^1.2 × 1.3 = 47.3`.

### F2 — Defence factor

The defence factor formula is defined as:

`K(L) = def_k_per_level × L + def_k_flat`
`mitigation(L, def) = K(L) / (K(L) + def)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L | int | 1–200 | monster level | Encounter level, for both directions |
| def | float | ≥ 0 | calculated (`mon_def`, or member `def` from Member model 8) | The defender's defence |
| def_k_per_level | float | 8 | data file (`sim_params.csv`) | How fast the defence "denominator" grows with level |
| def_k_flat | float | 50 | data file (`sim_params.csv`) | Floor so level-1 defence is not worthless or absolute |

**Output Range:** in (0, 1]. `def = 0` gives exactly 1.0 (no reduction). As `def → ∞` it tends to 0 but never reaches it, so damage is never negative. `K` is ≥ 58 for L ≥ 1, so the denominator is never 0. Against a monster at multiplier 1.0 the factor is 0.95 at L1, 0.53 at L100, 0.49 at L200; a defender with defence equal to `K` takes half damage.
**Example:** `m_z01_d`: `K(8) = 114`; `mitigation = 114 / (114 + 47.3) = 0.707`.

### F3 — Five Elements multiplier

The element multiplier formula is defined as:

`element_mult(a, d) = element_counter_mult` if `a` counters `d`; `element_countered_mult` if `d` counters `a`; `element_same_mult` if `a = d`; otherwise 1.0. A missing element on either side gives 1.0.

Counter cycle (khắc): Kim → Mộc → Thổ → Thuỷ → Hoả → Kim (§4.2; declared once by Data layer R4). The generation cycle (tương sinh) is not used by Combat (it is Party 13's group bonus, Open Questions OQ-6).

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| a, d | enum or none | kim, moc, thuy, hoa, tho, none | data file (`schools.element`, `monsters.element`) | Attacker and defender elements |
| element_counter_mult | float | 1.25 | data file (`config.csv`) | Attacker counters defender |
| element_countered_mult | float | 0.80 | data file (`config.csv`) | Defender counters attacker |
| element_same_mult | float | 0.95 | data file (`config.csv`) | Same element |

**Output Range:** 0.80–1.25. The validator should require `countered < same ≤ 1 < counter` (today true) so that a counter is always better than neutral (Tuning Knobs).
**Example:** a Kim member hitting a Mộc monster: ×1.25. The Mộc monster hitting that member: ×0.80.

### F4 — Member hit damage

The member hit formula is defined as:

`spread = (1 − dmg_variance) + (2 × dmg_variance) × u`
`member_hit = dps × (1 + atk_bonus) × element_mult(member, monster) × spread × mitigation(L, mon_def)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| dps | float | ~1.4 (L1 healer) – ~3,300 (L200 burst) without gear | calculated (Member model 8) | Damage per action; one action per `member_action_interval_s` |
| atk_bonus | float | 0 or `buffer_atk` (0.08) | data file (`sim_params.csv`) via R8 | Buffer bonus of the member's group |
| u | float | [0, 1) | RNG (one `random()` draw) | Spread draw |
| dmg_variance | float | 0.10 | constant in code today; proposed `sim_params.csv` key (OQ-1) | Half-width of the spread; 0.10 gives 0.9–1.1 |
| element_mult, mitigation | float | F3, F2 | calculated | |

**Output Range:** `dps × 0.8 × 0.9 × (≈0.3–0.95)` to `dps × 1.08 × 1.25 × 1.1 × 1.0`, so about 0.2× to 1.49× `dps`. Always > 0 when `dps > 0`. `dps = 0` (impossible from Member model's formula, which is positive for L ≥ 1) would make the fight a timeout. With `dmg_variance = 0.1` the spread is exactly `0.9 + 0.2u`, bit-identical to `sim/hunt.py`.
**Example:** a `kim_2` member at L10, no gear (`dps 57.79`), no buffer, against `m_z01_d`: mean hit `57.79 × 1 × 1.25 × 1.0 × 0.707 = 51.1`; the monster's 835.9 HP falls in about 16 actions, about 16 s. The reference run with `PCG32(5)` wins in 15.6 s.

### F5 — Monster hit damage

The monster hit formula is defined as:

`enrage = 1 + enrage_atk × floor(t / enrage_every_s)` (1 when enrage is disabled)
`monster_hit = mon_hit × enrage × element_mult(monster, member) × (1 − dmg_red) × K(L) / (K(L) + def_member)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| mon_hit | float | F1 | calculated | Monster hit after `monster_dmg_factor` and `dmg_scale` |
| t | float | 0 – `time_limit_s` | calculated | Time of this attack |
| enrage_atk, enrage_every_s | float | raid only: 0.5, 60 | data file (`sim_params.csv`) via caller | Raid enrage step |
| dmg_red | float | 0 or `buffer_dmg_reduction` (0.10) | data file (`sim_params.csv`) via R8 | Buffer reduction of the target's group |
| def_member | float | ≥ 0 | calculated (Member model 8) | Target's defence |

The multiplication by `K(L)` happens before the division, as in the code: `((mon_hit × enrage × element × (1 − dmg_red)) × K) / (K + def_member)`.

**Output Range:** > 0 for every valid input. Hunt fights at L200 with the strongest multiplier (2.2) and a counter: about `225.6 × 2.2 × 1.25 = 620` before defence. A raid at 300 s reaches `enrage = 3.5`. `buffer_dmg_reduction ≥ 1` would make damage 0 or negative; the validator must keep it below 1 (Edge Cases).
**Example:** `m_z01_d` attacking the L10 `kim_2` (def 19.0): `4.04 × 1 × 0.80 × 1 × 114 / 133.0 = 2.77` per attack, one attack every `1.0 / 0.9 = 1.11` s, about 39 HP over the 15.6 s fight; the member ends at 485 of 524 HP, as the reference run does.

### F6 — Heal amount

The heal formula is defined as:

`heal = min(hp_max_target − hp_target, healer_heal_frac × hp_max_target)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| healer_heal_frac | float | 0.03 | data file (`sim_params.csv`) | Share of the target's max HP restored per heal action |
| healer_heal_threshold | float | 0.8 | constant in code today; proposed `sim_params.csv` key (OQ-1) | A heal happens only if the target's HP fraction is below this |
| hp_max_target, hp_target | float | > 0 | calculated | Target's max and current HP |

**Output Range:** 0 < heal ≤ 3% of the target's max HP per action. The heal scales with the target, not the healer, so a low-level healer heals a high-level tank fully (Edge Cases). `healed[member]` counts `heal` as computed here, after the cap.
**Example:** a tank at 50% of 9,737 HP: heal = 292 HP; the healer does not attack on that action.

### F7 — Action schedule

The action schedule formula is defined as:

`member_first = u_i × member_action_interval_s`, then `+ member_action_interval_s` per action
`monster_interval = attack_interval_base_s / speed`; `monster_first = u_m × monster_interval`, then `+ monster_interval` per attack

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| member_action_interval_s | float | 1.0 | constant in code today; proposed `sim_params.csv` key (OQ-1) | Seconds between a member's actions; `dps` is damage per action |
| attack_interval_base_s | float | 1.0 hunt; 1.5 raid (`raid_boss_interval_s`) | caller | Monster base interval |
| speed | float | 0.8–1.2 in today's data | data file (`monsters.speed`) | Higher is faster; must be > 0 |
| u_i, u_m | float | [0, 1) | RNG | Start-up offsets (R13 steps 1–2) |

**Output Range:** monster intervals 0.83–1.25 s in hunts, 1.25–1.875 s in raids. Members act once per second each. `speed = 0` divides by zero and is a content error (validator: `speed > 0`).
**Example:** `m_z01_d` (speed 0.9) attacks every 1.11 s.

### F8 — Deadline tick

The deadline tick formula is defined as:

`deadline_tick = start_tick + ceil(duration_s × tick_rate)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| start_tick | int | ≥ 0 | Sim core (`ctx` tick) | Tick the caller resolved the fight in |
| duration_s | float | 0 – `time_limit_s` + one action | calculated (R14) | Fight duration |
| tick_rate | int | 10 | data file (`config.csv`, Sim core owns) | Ticks per second |

**Output Range:** 0 to about 6,010 ticks for a 600 s hunt limit. A fight with `duration_s = 0` (empty encounter) applies in the same tick.
**Example:** the reference fight's 15.6158 s at 10 Hz: `ceil(156.158) = 157` ticks after the start. (A duration of exactly 15.6 s gives `ceil(156.0) = 156`.)

The rule is offered to realtime callers; aggregate and offline callers simply add `duration_s` to their own clocks, as `run_trip` does today.

## Edge Cases

`systems-designer` lens applied to the written Sections C and D in this session.

- **If `resolve` is called with no alive combatant**: returns `won = false`, `reason = wiped`, `duration_s = 0`, consumes no draws. The caller should not call it, but the result is defined.
- **If the last alive member dies on the same attack that would have been the killing blow**: impossible: members and the monster never act at the same instant (R6 serialises them; members win ties), so either the member's hit lands first and the fight is won, or the monster's attack lands first.
- **If a member's next action and the monster's next attack are at exactly the same time**: the member acts first (R6 step 3).
- **If two members' next actions are at exactly the same time**: the one earliest in combatant order acts first.
- **If the killing hit overkills**: the monster's HP goes negative; the fight is won; `dealt` records the full hit (as built); `monster_hp_left = 0`.
- **If a hit takes a member below 0**: HP is set to 0 and the member dies; `taken` counts only the HP the member had.
- **If the fight passes `time_limit_s`**: it is lost (`timeout`) at the next top-of-loop check, so `duration_s` can exceed the limit by up to one action interval. The monster is not killed and the caller treats it as a loss (Zones and hunt 11 ends the trip: `lost`). The members keep their HP.
- **If the buffer dies mid-fight**: the bonus stays for the rest of the fight (R8); it was snapshot at the start. In the next fight, a dead buffer is absent and the bonus is gone.
- **If two buffers are in one group**: one bonus; no stacking.
- **If the healer is the most hurt member**: it heals itself.
- **If every member of the healer's group is at or above `healer_heal_threshold`**: the healer attacks. A healer never "wastes" an action on a full-HP target.
- **If a low-level healer heals a high-level tank**: the heal is 3% of the *tank's* max HP. This is as built. It makes healers equally useful at every level gap, and is a candidate exploit only in the sense that a cheap healer helps a strong party; it does not create unbounded gain. Recorded as OQ-7 for Party (13) and Retention balance.
- **If a group has tanks but all of them are dead**: the tank check is skipped (no tank in the pool), and targets are picked from everyone alive.
- **If `targets_per_attack` is greater than the number of alive members**: the attack hits each alive member once and ends.
- **If the encounter has an unaffiliated member (no element)**: ×1.0 both ways (R12).
- **If the monster is far above the party's level**: nothing in Combat caps it. The fight resolves and is usually a timeout or a wipe; the 600 s limit bounds its cost. The "never beat a boss at 1.5× level" check of §20 S5 is a balance test on this resolver, not a rule in it.
- **If equipment, school or level change during a fight's world time**: no effect on that fight (R4). The next fight uses the new values.
- **If the member is recalled to a Golden Boss raid during a hunt fight**: the fight completes; the recall takes effect at its deadline tick (decision: no interrupt). The wait is bounded by `fight_time_limit_s`; typical fights last seconds (OQ-8 asks Golden Boss 14 to confirm its gathering time covers it).
- **If the game is saved between a fight's start tick and its deadline tick**: the save holds whatever the caller keeps for the pending result (Zones and hunt 11 / Local save 6). Because the fight is atomic and its key and inputs are saved, recomputing it on load gives the identical result. Deterministic RNG AC-19 can be retired (OQ-10).
- **If the player reloads and changes the party before a fight**: same dice (same key), different outcome. Accepted (RNG Edge Cases, save-scumming).
- **If content gives `speed ≤ 0`, `buffer_dmg_reduction ≥ 1`, `dmg_variance ≥ 1`, `healer_heal_frac ≤ 0`, monster level < 1, or element multipliers out of order**: content error at validation (Data layer R8); never reached at runtime. [Some of these checks do not exist yet: OQ-2.]
- **If a combatant's stats produce NaN or infinity** (a corrupt row): Combat calls `ctx.fail` with its error code and the core halts (Sim core R10). A fight result with NaN is never returned.
- **Degenerate strategy check**: there is no in-fight loop the player can repeat for gain; all gain is per kill and owned by the caller. The positive loop "stronger members kill faster, earn more, get stronger" is intended (§1 core loop) and is damped by monster curves rising with level and by the XP curve (22).

## Dependencies

| System | Kind | What Combat needs | Status |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | Runs inside a caller's handler; `ctx.derive`, `ctx.fail`, `tick_rate` | Designed (Needs Revision) |
| Deterministic RNG (2) | Hard | One generator per fight; domain 1; `random`, `choice` | Designed (Needs Revision) |
| Data layer and content pipeline (3) | Hard | `monsters`, `sim_params`, `sim_roles`, `schools`, `config`; later `skills` | Designed |
| Member model (8) | Hard | `profile` integers, `hp_milli` (R4a) | Designed (Needs Revision) |
| Schools and school change (20) | Hard | `element` or none, `role`, `buff_role` | Designed |
| Skills (21) | Hard from stage 2 (S4) | Loadout, passive sheet, effect vocabulary and kinds | Designed (Needs Revision) |
| Party (13) | Soft | Group membership and slot order; the key leader's `party_id` (Party R5) | Designed |
| Zones and hunt (11), Golden Boss (14), Arena (18) | Callers | Build the encounter (R3) | Designed |

**Depended on by**: Zones and hunt trips (11, hard), Golden Boss and guild raid (14, hard), Offline progress (31, through 11), Realtime world view (38, through the caller's events), Endless Tower (19), Arena (18), Dev tooling and parity harness (43, vectors), CA/PA and traits (9) only if traits later modify combat stats (through Member model). The systems index lists Combat in the Depends On column of 11, 13, 14, 18, 19, 31 and 38, which matches. Party (13) lists Combat as a dependency; here Party is only a soft input, since Party reads Combat's behaviour (buffer bonus) to score compositions.

## Tuning Knobs

`systems-designer` lens (Section G) applied: knobs derived from the Formulas variable tables.

| Knob | Today | Safe range | Too high | Too low | Lives in |
|---|---|---|---|---|---|
| `monster_dmg_factor` | 0.05 | 0.02–0.15 | Members die each fight; trips end at the first `flee_hp_pct` | No fight is ever dangerous; healers and tanks lose their point | `sim_params.csv` |
| `monster_hp_coef` / `_exp` | 40 / 1.3 | exp 1.2–1.5 | Fights drag, kill rate and XP rate collapse (1.6 was tried and rejected, §4.2) | Fights are instant, the timeline is unreadable | `config.csv` |
| `monster_atk_*`, `monster_def_*` | 6/1.25, 3/1.2 | exp ±0.1 | — | — | `config.csv` |
| `def_k_per_level`, `def_k_flat` | 8, 50 | 4–16, 20–100 | Defence barely matters, gear and tanks lose value | Defence dominates; armour-stacking makes members unkillable | `sim_params.csv` |
| `element_counter_mult` | 1.25 | 1.1–1.5 | Element choice becomes mandatory; off-element grounds are dead | Matchups stop mattering (Player Fantasy moment 1 lost) | `config.csv` |
| `element_countered_mult` | 0.80 | 0.6–0.95 | (must stay < same) | Wrong element is crippling | `config.csv` |
| `element_same_mult` | 0.95 | 0.85–1.0 | (must stay ≤ 1) | — | `config.csv` |
| `tank_aggro_share` | 0.7 | 0.4–0.95 | Non-tanks are never hit; tank is mandatory | Tanks are ignored and pointless | `sim_params.csv` |
| `healer_heal_frac` | 0.03 | 0.01–0.08 | Parties with a healer never die | Healers are pure damage loss | `sim_params.csv` |
| `healer_heal_threshold` | 0.8 | 0.5–0.95 | Healer heals almost every action, its damage is near 0 | Heals arrive too late, members die | code constant → OQ-1 |
| `buffer_atk` | 0.08 | 0.03–0.15 | A buffer is mandatory | "Thiếu buffer" warning is false | `sim_params.csv` |
| `buffer_dmg_reduction` | 0.10 | 0.0–0.3 (hard < 1) | ≥ 1 makes damage ≤ 0 | — | `sim_params.csv` |
| `dmg_variance` | 0.10 | 0.0–0.25 | Fights feel random (anti-fantasy) | 0 makes every fight of a matchup identical in length | code constant → OQ-1 |
| `member_action_interval_s` | 1.0 | 0.5–2.0 | Slower fights at the same `dps` | More actions, more draws, more cost per fight | code constant → OQ-1 |
| `fight_time_limit_s` | 600 | 60–900 | Hopeless fights cost a lot of CPU | Hard fights are cut off before they could be won | code constant → OQ-1 |
| `skill_dps_bonus` | 0.4 | — | — | — | `sim_params.csv`; Member model's stand-in for skills, retired at S4 |

**Knobs that interact**: `monster_dmg_factor`, `healer_heal_frac` and `buffer_dmg_reduction` together set survival; raising one makes the others less visible. `tank_aggro_share` matters only with a tank in the group. `def_k_*` sets how much `mon_def` and member `def` matter, so it scales the value of every defence stat in Enhancement (24) and Items (26). Raid values (`raid_hp_mult`, `raid_dmg_mult`, `raid_boss_interval_s`, `raid_boss_targets`, `raid_enrage_*`, `raid_time_limit_s`) are owned by Golden Boss and guild raid (14) and are pointed to, not duplicated. Member stat curves (`member_*_coef/_exp`, `sim_roles.csv`) are owned by Member model (8). Every change runs `python3 tools/balance_sim.py --quick` (§21 Prompt 0 rule 6).

## Visual/Audio Requirements

No art bible exists (`design/art/` is absent), so this is drafted from the GDD's art direction (§3.5 paper-doll sprites, palette swap per element; §12.4 AI-assisted pixel art). `art-director` lens applied in this session.

1. **Every timeline record is visible.** The world view plays the `timeline` back at world speed: a member's attack animation and a damage number per attack; a green heal number on the target; the monster's attack with a hit flash on each target; a death pose and fade. The playback must show the fight that happened, never an invented one (the outcome is already known).
2. **Element matchup is readable without colour alone.** A counter hit (×1.25) shows a larger number and an element glyph; a countered hit (×0.80) a smaller, muted number. Colour per element follows the palette swap, plus the glyph (accessibility).
3. **Role reads at a glance.** Tank: taunt flash when it is picked by the aggro check. Buffer: a persistent aura on the group while the bonus is active. Healer: a beam or glyph from healer to target.
4. **Budget (§3.5, §6.13).** Object-pool damage numbers; cap damage numbers on screen (proposed 20) and full sprites in a raid (≤ 15, others as group tokens). The simulation records no timeline for any fight (`want_timeline = false`); the view requests one only for fights it draws, through the callers' timeline queries.
5. **Audio.** Hit, counter hit, heal, death, and monster attack cues; counter hits and deaths get the higher mix priority. Owned in detail by Audio (40).

📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:combat` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

- **Pace:** an ordinary fight lasts seconds to tens of seconds (the reference L10 fight: 15.6 s). Members act once a second; monsters every 0.83–1.25 s. Fast enough to watch many fights, slow enough to read who did what.
- **No input latency to design for:** the player does not act in a fight. Feel targets are readability and weight: hit-stop of 1–2 frames on counter hits and kills only, a short shake on a death in the party.
- **Trust:** what the player sees equals what was computed. No fake misses, no hidden rubber-banding.
- **Idle fit:** nothing in a fight demands attention. A wipe or flee is reported by the trip, not by an alarm in the fight.
- These are targets for the world view (38); verified by screenshot and playtest, not by automated tests.

## UI Requirements

Combat owns no screen. It supplies data that other screens show:

- Above members and monsters in the world view (38): HP bars, damage and heal numbers, the death state.
- In party and ground screens (39): the element matchup of the party against the ground's dominant element (counter / neutral / countered), and the "thiếu buffer" warning, computed from F3 and R8.
- In the Golden Boss result (14, 39): per-member `dealt`, `healed`, `taken`.
- All numbers are localised through i18n (4); the element names are display strings, not IDs.

**📌 UX Flag — Combat**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for each screen or HUD element this system contributes to **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD uses | From | Section / rule | Kind |
|---|---|---|---|
| Per-event seeding, domain 1, key rules, draw order as contract | `deterministic-rng.md` | R3–R7, F3–F5 | Rule dependency |
| Handler context, `ctx.fail`, `tick_rate`, `sim_version` bump | `sim-core-and-tick-loop.md` | R1, R5, R10, R12 | Rule dependency |
| Table schemas, element cycle declared once, validator gate | `data-layer-and-content-pipeline.md` | R4, R8 | Data dependency |
| `element`, `role`, `buff_role`; unaffiliated = no element | `schools-and-school-change.md` | R2, OQ-4 | Data dependency (answers OQ-4) |
| Golden vectors and bit-exact float comparison | `dev-tooling-and-parity-harness.md` | R5, R14 | Verification |
| Kill XP and level-gap penalty are not Combat's | `xp-and-level-pacing-curve.md` | Interactions (Hunt row) | Ownership boundary |
| Formulas and cycle | `JX1_Tycoon_GDD.md` | §4.2 | Source of values |
| Roles, aggro, buffer, party effects | `JX1_Tycoon_GDD.md` | §6.12 | Source of rules |
| Raid structure, contribution, mobile limits | `JX1_Tycoon_GDD.md` | §6.13 | Source of rules |
| Skill tree shape; S4 acceptance | `JX1_Tycoon_GDD.md` | §6.2, §20 S4 | Stage 2 scope |
| Draw order, floats, ties, event-driven | `GODOT_PORT.md` | Rules 2–5 | Port contract |

## Acceptance Criteria

`qa-lead` lens applied against Sections C, D and E in this session. All criteria are **Logic** (automated unit test in `tests/`, Python reference first, then the port via parity vectors) unless marked.

**Resolver and parity**
- **AC-1 (R3, R13)** — **GIVEN** the hunt encounter values and the fixture of `tools/calibrate.py` (`kim_2`-style member at L10, monster `m_z01_d`, generator seeded as the reference test), **WHEN** `resolve` runs, **THEN** `won`, `duration_s` (bit pattern), `hp_after` and `dealt` equal `sim/hunt.py fight()` on the same inputs and generator.
- **AC-2 (R3, D5)** — **GIVEN** a 20-member guild with buffers and tanks not first in roster order, and a Golden Boss row, **WHEN** `resolve` runs with the raid encounter values, `order` = the roster as passed to `simulate_raid()`, `groups` = `form_parties(roster)` and `start_hp = hp_max`, **THEN** `won`, `duration_s` (bit pattern), deaths, `monster_hp_left` and `dealt` equal `sim/raid.py simulate_raid()` on the same inputs and generator.
- **AC-2b (F1)** — **GIVEN** L 1–200, `hp_mult` in {0.7, 1, 4, 12, 22} and n 1–40, **WHEN** `mon_hp` is computed with `hp_part_scale = 1 + 0.1 × n` and `hp_raid_scale = 6`, **THEN** it equals `monster_hp(L, hp_mult) × (1 + 0.1 × n) × 6` of `sim/raid.py` bit for bit in all 40,000 cases.
- **AC-2c (R4a)** — **GIVEN** a member with `hp_milli = 523,999` and no hit taken, **THEN** the written-back `hp_milli` is 523,999; **GIVEN** a survivor with `hp_after = 0.0003`, **THEN** `hp_milli = 1`; **GIVEN** a member in `died`, **THEN** `hp_milli = 0`.
- **AC-2d (R3)** — **GIVEN** a caller-built monster row not in `monsters.csv` and `start_hp` below `hp_max` for one member, **WHEN** `resolve` runs, **THEN** it uses the row's multipliers by F1 and that member starts at the given HP.
- **AC-3 (R13)** — **GIVEN** a counting generator, **WHEN** a fight with 2 members, 1 healer heal, 5 member attacks and 3 single-target monster attacks against a party with a tank runs, **THEN** the draws are exactly: 2 start-up + 1 monster start-up + 5 spread + 3 × (1 tank check + one `choice`), in that order, and a heal draws nothing.
- **AC-4 (R2)** — **GIVEN** the same encounter and the same `(domain, key)`, **WHEN** `resolve` runs twice, **THEN** the two results are identical. **WHEN** `encounter_ordinal` is +1, **THEN** the first spread draw differs.
- **AC-5 (R14)** — **GIVEN** any fixture, **WHEN** it runs with `want_timeline` true and false, **THEN** every field except `timeline` is identical, and the timeline's last record's time equals `duration_s`.

**Rules**
- **AC-6 (R6)** — **GIVEN** a member and the monster whose next times are equal, **WHEN** the loop reaches them, **THEN** the member acts first. **GIVEN** two members with equal next times, **THEN** the earlier in combatant order acts first.
- **AC-7 (R6)** — **GIVEN** a member with `dps` too low to kill before 600 s, **WHEN** the fight runs, **THEN** `won = false`, `reason = timeout`, and `600 < duration_s ≤ 600 + 1.0`. **GIVEN** a fixture whose killing action falls in (600, 601], **THEN** `won = true` with `duration_s > 600`.
- **AC-8 (R7, F6)** — **GIVEN** a `healer_support` member and an ally at 79% HP, **WHEN** the healer acts, **THEN** the ally gains `0.03 × hp_max` (capped at max), the monster's HP is unchanged, and no draw is used. **GIVEN** the ally at 80%, **THEN** the healer attacks.
- **AC-9 (R8)** — **GIVEN** a party with one `moc_1` member, **WHEN** another member attacks with `u = 0.5`, **THEN** its hit equals the no-buffer hit × 1.08 (to 1 ulp), and a monster hit on any member equals the no-buffer hit × 0.90. **GIVEN** two buffers, **THEN** the factors are the same.
- **AC-10 (R8)** — **GIVEN** the buffer dies mid-fight, **WHEN** a later member attack resolves, **THEN** it still includes `+buffer_atk`.
- **AC-11 (R9)** — **GIVEN** a raid with two groups, group A with a healer and a buffer, **WHEN** a group-B member is at 10% HP and a group-A member at 90%, **THEN** the healer attacks rather than healing the group-B member, and group-B members get no buffer factor.
- **AC-12 (R10)** — **GIVEN** a party of one tank and four non-tanks and 100,000 single-target monster attacks across seeded fights, **WHEN** targets are counted, **THEN** the tank's share is `0.7 + 0.3 / 5 = 0.76` within ±0.01.
- **AC-13 (R10)** — **GIVEN** `targets_per_attack = 3` and 2 alive members, **WHEN** the monster attacks, **THEN** each member is hit once and the attack ends.
- **AC-14 (R11)** — **GIVEN** a member taking a hit larger than its HP, **THEN** `hp_after = 0`, it appears in `died`, `taken` equals its HP before the hit, and it takes no further action or heal.
- **AC-15 (R12, F3)** — **GIVEN** each of the 25 element pairs and an attacker with no element, **WHEN** `element_mult` is evaluated, **THEN** the five counter pairs give 1.25, the five reverse pairs 0.80, the five same pairs 0.95, the other ten 1.0, and every pair with `none` gives 1.0. (The existing `tests/test_core.py` element test covers the 25 pairs.)
- **AC-16 (R4)** — **GIVEN** a fight resolved at tick N with deadline N+157, **WHEN** the member's weapon is changed at tick N+10, **THEN** the applied result equals the result computed at tick N.
- **AC-17 (R1)** — **GIVEN** `resolve` is called, **THEN** no member, monster, table or core field outside the returned result has changed (check by hashing the inputs before and after).

**Formulas (boundaries)**
- **AC-18 (F1)** — **GIVEN** L = 1, 100, 200 and multipliers 1.0, **THEN** `mon_hp` = 40.0, 15,924.3, 39,210.2 and `mon_hit` = 0.300, 94.87, 225.64 (±0.05).
- **AC-19 (F2)** — **GIVEN** L = 8 and `def = 0`, **THEN** mitigation = 1.0; **GIVEN** `def = K(8) = 114`, **THEN** 0.5.
- **AC-20 (F4)** — **GIVEN** `u = 0` and `u → 1` (largest float below 1), **THEN** the spread is 0.9 and < 1.1, and with `dmg_variance = 0.1` the spread equals `0.9 + 0.2u` bit for bit.
- **AC-21 (F5)** — **GIVEN** raid values and `t = 0, 59.9, 60, 300`, **THEN** `enrage` = 1, 1, 1.5, 3.5.
- **AC-22 (F6)** — **GIVEN** a target at 99% HP, **WHEN** healed (threshold set to 1.0 for the test), **THEN** `healed` = 1% of max, not 3%.
- **AC-23 (F8)** — **GIVEN** `duration_s = 15.6158` and `tick_rate = 10`, **THEN** `deadline_tick = start + 157`; **GIVEN** `duration_s = 0`, **THEN** `start + 0`.

**Content and cross-system**
- **AC-24 (Edge Cases)** — **GIVEN** a `monsters.csv` row with `speed = 0`, or `buffer_dmg_reduction = 1.0`, **WHEN** the content validator runs, **THEN** it reports an ERROR. [PENDING OQ-2: the checks do not exist yet.]
- **AC-25 (Integration, R16)** — **GIVEN** the 24-hour 5-member hunt fixture, **WHEN** it is simulated exactly and with Offline progress's sampled fast-forward, **THEN** both call only this resolver for fights (instrumented count > 0 on both paths), and total XP differs by ≤ 2% (§18.1 measured ~1%).
- **AC-26 (Integration, Balance)** — **GIVEN** `tools/balance_sim.py --quick`, **WHEN** run after any change to this system, **THEN** solo and party times to L100 stay within the bands of Dev tooling's balance budget. [PENDING: S9 budget table.]
- **AC-27 (Stage 2, R15)** — [PENDING: Skills 21, S4] **GIVEN** each school's 12 skills, **WHEN** a full fight runs, **THEN** it completes without error, no code path compares a skill or school ID, and role damage matches `sim_roles.csv` within ±15% (§20 S4).
- **AC-28 (UI / Visual)** — **GIVEN** a viewed ground with a party fighting, **WHEN** the world view plays back a fight, **THEN** a retained screenshot in `production/qa/evidence/` shows HP bars, damage numbers, a counter-hit marker that does not rely on colour alone, and a heal number. [PENDING: Realtime world view 38.]

**Performance** — **AC-29** — **GIVEN** the max-roster fixture of Sim core (F6) with all hunting parties on aggregate grounds, **WHEN** an hour is simulated, **THEN** the P3 share used by fights is within Sim core's provisional 35% phase share, measured on the reference device. Cost scales with actions per fight (about `duration_s × (members + 1/interval)`), not with ticks. [PENDING: P1 spike, Sim core OQ-6.]

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | Promote the five code constants (`fight_time_limit_s` 600, `healer_heal_threshold` 0.8, `member_action_interval_s` 1.0, `dmg_variance` 0.10, hunt `attack_interval_base_s` 1.0) to `sim_params.csv` keys. This is a schema change to data and the validator; not made in this autonomous run. Values are bit-identical, so no parity change. | user + Data layer (3) | Before the Godot port of combat |
| OQ-2 | Add validator checks: `monsters.speed > 0`, `level ≥ 1`, `buffer_dmg_reduction < 1`, `0 ≤ dmg_variance < 1`, `healer_heal_frac > 0`, `element_countered_mult < element_same_mult ≤ 1 < element_counter_mult`. Schema/validator change. | Data layer (3) | With OQ-1 |
| OQ-3 | Keep binary64 floats (chosen) or move combat to integer fixed-point as the XP curve did? Floats rely on both ports evaluating in the same order and `pow()` agreeing bit for bit; the parity harness will show it. | technical-director | After the first parity run on the engine |
| OQ-4 | Monster `ai_skills` (`bite`, `enrage_30pct`, `summon_adds`, …) have no definition table. Until one exists monsters use the basic attack only. Who owns monster skills: Skills (21) or Zones (11)? | user | Before S4 |
| OQ-5 | Fights are one monster, no positions. Do AoE, knockback and summons need multi-monster encounters (several monsters at once), or are they cosmetic in the simulation? Affects R15 and hunt pacing. | user + Zones and hunt (11) | Before S4 |
| OQ-6 | The generation-cycle (tương sinh) group bonus and "element coverage" bonus of §6.12 are not built. Proposed: Party (13) computes them and passes a group `atk_bonus`/`dmg_red` addition into the encounter. | Party (13) | When Party is designed |
| OQ-7 | Heals scale with the target's max HP, not the healer's power, so a low-level healer is as good as a high one. Intended? | user | Before S4 |
| OQ-8 | Closed: Golden Boss R5 drops a group not arrived within `raid_gather_max_s`; no abort rule. | — | — |
| OQ-9 | `GODOT_PORT.md` rule 2 says monster attacks draw a spread after the target; the code does not. Correct the port note to match R13. | user (file outside design/) | Next port-doc edit |
| OQ-10 | Deterministic RNG AC-19 (mid-fight save) can be retired: fights are atomic (R2). The RNG owner should update its AC. | Deterministic RNG (2) | Next RNG revision |
| OQ-11 | Base MP maximum and MP regeneration per member for stage-2 casting (R15): Skills R2 has only `mp_max_pct`/`mp_regen` modifiers, and no GDD defines the base. Recommended: Member model adds `mp_max_milli` to the profile from a `sim_roles.csv` column; Combat owns regen at a flat `mp_regen_per_s` knob. | user + Member model (8) + Skills (21) | Before S4 |
| PROVISIONAL-1 | Closed 2026-11-16: Member model R7 `profile` integers; conversion R4a. | — | — |
| PROVISIONAL-2 | Closed 2026-11-16: Skills R2 kinds, one handler per kind (R15); MP base is OQ-11. | — | — |
| PROVISIONAL-3 | Closed 2026-11-16: Zones R5 / Party R5 key leader `party_id` and `trips_led`. | — | — |
| PROVISIONAL-4 | Closed 2026-11-16: Golden Boss R7–R8 build `groups`, `order`, `start_hp` and the raid values. | — | — |
| PROVISIONAL-5 | Closed 2026-11-16: Zones R6, R15. | — | — |
