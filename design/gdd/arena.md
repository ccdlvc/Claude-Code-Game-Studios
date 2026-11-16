# Arena (Lôi Đài)

> **Status**: Designed (pending review)
> **Author**: user + agents (`/design-system`, autonomous batch run)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: No `game-pillars.md` exists; serves GDD §6.11 (Lôi Đài) and §7 (PvP Colosseum → Lôi Đài)
> **Creative Director Review (CD-GDD-ALIGN)**: CONCERNS (accepted) 2026-11-16 — see Open Questions OQ-4, OQ-10

## Summary

The Arena (Lôi Đài) is the guild's local ranked ladder against NPC guilds: the player spends a few daily tickets to send up to five members against the guild seated just above, and the lineup fights that guild's champions one after another in quick, harmless spars resolved by the ordinary combat engine. Winning takes the seat; holding a seat pays daily prestige and a little guild gold, and each new best rank pays one zone loot roll. It exists to give the Wave 2 guild a visible measure of strength against the jianghu, and a stage where members who left come back as rivals.

> **Quick reference** — Layer: `Feature` · Priority: `Full Vision` · Key deps: `Combat, Jianghu free agents and NPC guilds, Deterministic RNG, Guild and buildings, Member model, Items and loot tables`

## Overview

The Arena is a Wave 2 feature (GDD §12.5) unlocked by building the Lôi Đài (`bld_arena`, needs Tổng Đàn level 5, `building_meta.csv`). It is a **local ladder**: the player's guild and a set of NPC guilds from the Jianghu (17) hold ranked seats, and the building's level sets how many NPC guilds hold seats (`opponents`, 3 at level 1, 10 at level 8) and how much the arena pays (`reward_mult`, 1.1 to 1.8). The player spends one of a few daily **challenge tickets** to send a lineup of one to five members against an NPC guild seated just above them. The bout is a **gauntlet**: the lineup fights the opponent's champions one at a time, carrying its wounds from duel to duel, and wins if it beats every champion. Each duel is an ordinary Combat (10) fight against a champion turned into a monster-shaped row (its school's element, its level, an archetype by role, scaled by the NPC guild's power). A bout is a **spar**: no one is hurt, dies, earns XP or leaves home, and it resolves in one tick. Winning swaps the two seats. Holding a seat pays a daily reward of prestige and guild-fund gold that grows with rank, and every first arrival at a new best rank rolls one zone drop table into guild storage. NPC guilds never challenge back, so the arena runs only when the player acts, and the ladder is never uploaded (GDD §6.11: local only, to avoid cloud cheating).

## Player Fantasy

**Chosen framing — "Prove the guild on the platform."** The player opens the Lôi Đài and sees the seat above: *Thiết Kiếm Bang, rank 4, a Kim striker, a Thổ tank and a former disciple of yours, now their Hoả archer.* They pick five members, put the tank first and a Hoả damage dealer against the Kim champion, and press challenge. The duels play back in seconds: the striker falls, the tank holds, the archer — the one who left them for a better offer — goes down last. The seat flips to them, the rank-4 banner goes up over the guild hall, and tomorrow's reward is bigger. When the bout fails, the summary says which duel it broke on and why (*"Lost duel 3 of 4: Thổ champion, your lineup had no Mộc to counter it"*), and that points at the next decision: recruit, enhance, rebirth.

*Considered and not chosen:*
- *"The tournament"* (seasons, brackets, opponents who challenge you back): needs NPC guilds to act on their own and to punish a player who is away, which fights offline play (GDD §10) and makes a loss a chore instead of a lesson.
- *"The rival story"* (the arena as a stage for former members): kept as flavour (the former disciple in the lineup above), but a ladder built only around ex-members would be empty for most of the game.

What the chosen framing asks of the design: the result is decided by the guild's strength and the player's lineup choice, not by luck (one seeded generator per duel, RNG R5); the reason for a loss is readable; the reward is not farmable; and nothing bought changes the dice (RNG R10). `creative-director` lens applied in this session, not as a spawned agent (skill rule).

## Detailed Design

Specialist views applied before drafting (routing row "Combat, damage, health" for a fight-based Gameplay system: primary `game-designer`; supporting `systems-designer`, `ai-programmer`, `art-director`):

- **game-designer** — The player's decisions are the lineup, its order and which seat to challenge. Everything else (the duel itself) is Combat's and is not steered. The arena must not add a second progression track that competes with hunting: no XP, and rewards that sit beside, not above, the zone ladder. A loss should cost a ticket and nothing else.
- **systems-designer** — Combat resolves members against one monster (Combat R3); it has no member-against-member mode. The smallest design that keeps "one resolver" is to turn each NPC champion into a monster-shaped row and fight the champions in sequence. A ladder that only moves when the player wins cannot oscillate; a ladder that shrinks or grows with the building needs an exact insertion rule. Rewards paid per win would be farmable with fixed dice, so pay per day held and per first arrival.
- **ai-programmer** — NPC guilds make no decisions in the arena: no challenge-backs, no lineup AI. The opponent's lineup is the snapshot Jianghu (17) gives, in its order. Inside a duel, behaviour is Combat's three fixed rules.
- **art-director** — The bout resolves instantly but should be watched: Combat's timeline (R14) plays back each duel on the platform, and the summary names the deciding duel. Former members in an NPC lineup are marked so the player recognises them.

No conflict between the views needed a user decision. Decisions taken autonomously are logged in `production/session-logs/decision-log.md`.

### Core Rules

**R1 — Availability.** The arena exists when `effect(bld_arena, opponents)` (Guild and buildings R7) returns a value; `none` means the arena is unavailable and its panel is hidden. `opponents` and `reward_mult` are read at the moment they are used. While `bld_arena` is upgrading, the old level's values apply (Guild and buildings R6). Whether `opponents` decays under upkeep arrears is Guild and buildings' rule; the arena only reads it (a shrinking value is handled by R3).

**R2 — Guild arena record.** One record per guild, saved as its own section `arena` (Local save R6):

| Field | Type | Meaning |
|---|---|---|
| `ladder` | list of guild IDs | Seats in rank order; index 0 is rank 1 (the top). The player's guild is the sentinel ID `0`; every other entry is an NPC guild ID owned by Jianghu (17). |
| `best_rank` | int ≥ 1 | Best (lowest) rank the player has ever held. Starts at the player's first rank. Never gets worse. |
| `challenge_ordinal` | int ≥ 0 | Number of bouts ever fought. Incremented when a bout resolves; the current bout's ordinal is the new value. |
| `tickets` | int ≥ 0 | Challenges left in the current arena day. |
| `day` | int ≥ 0 | The arena day (F3) the tickets and rewards were last settled for. |

**R3 — Building the ladder (seeding and resizing).** Let `N = effect(bld_arena, opponents)` and `G` = Jianghu's live NPC guild list (17, PROVISIONAL `npc_guilds()`), sorted by `power_milli` ascending, ties by guild ID ascending. Let `M` = the number of NPC seats currently on the ladder.
1. **First creation** (the arena becomes available, `ladder` empty): take the first `min(N, |G|)` guilds of `G` (the weakest), place them in **descending** power order (strongest at rank 1), and put the player at the bottom. `best_rank` = the player's rank; `tickets = arena_daily_challenges`; `day` = the current arena day.
2. **Growth** (`N > M`, after an upgrade completes or new NPC guilds appear in `G`): take the next `min(N − M, available)` guilds of `G` not already seated, weakest first, and insert them **above rank 1**, strongest of them at the new rank 1. Existing seats keep their relative order; the player's rank number rises by the number inserted, and `best_rank` is shifted by the same amount (a newly inserted seat was never held).
3. **Shrink** (`N < M`, or a seated guild is no longer in `G`): remove the missing guild first; if still `M > N`, remove NPC seats from the **top**, one at a time, never the player. The player's rank number and `best_rank` fall by the number of removed seats that were above them (`best_rank` floors at 1).
Resizing runs in P4 (R8) before tickets are settled. It never pays a reward and never rolls loot.

**R4 — The opponent's lineup.** When a bout resolves, the arena asks Jianghu for the seated guild's champion lineup: `arena_lineup(guild_id)` (17, PROVISIONAL), an ordered list of 1 to `arena_lineup_max` (5) champions, each `{school_id, level, power_milli, former_member_id or 0}`. The lineup is read fresh at that moment, so an NPC guild that has grown since the last bout fights stronger (GDD §6.11: NPC guilds grow over real and offline time). Each champion becomes one **champion row** (F1). A former member (Retention 16 → Jianghu 17) fights as a champion like any other; the ID is carried only for display.

**R5 — Challenging: command `arena_challenge(target_rank, member_ids)`** (Command layer, ID 1801, applied in P1 at order 1800). Refused, with event `arena_challenge_refused` (1804) carrying the reason and no state change, when:
1. the arena is unavailable (R1);
2. a bout is already pending this tick (one bout per tick per guild);
3. `tickets = 0`;
4. `target_rank` is not an NPC seat with `player_rank − arena_reach ≤ target_rank ≤ player_rank − 1` (only seats above, within reach; at rank 1 every challenge is refused with this reason);
5. the member list is empty, longer than `arena_lineup_max`, or has a duplicate or unknown member ID;
6. any member is not at home and free: Member state machine (41) `state_of` must be `idle` or `resting` (PROVISIONAL query; no state change is requested).

If accepted, the command stores a pending challenge `{target_guild_id, member_ids}` (by guild ID, not rank, so a resize in the same tick cannot redirect it) and spends one ticket. Nothing else changes in P1.

**R6 — Resolving a bout (P3 `field`, order 1800).** For a pending challenge, in the same tick:
1. `challenge_ordinal += 1`; let `c` be the new value.
2. Snapshot the lineup: the members in the order given, each at **full HP** (`hp_max`), with their stats read as Combat R4 (PROVISIONAL: Combat accepts a caller-supplied starting HP, see OQ-2). Members' real HP is never read or written.
3. Build the champion rows (R4, F1) in the opponent's order.
4. For duel `j = 0, 1, …` over the champions: build the encounter (R7), derive `gen = derive(rng_domain_arena = 16, [c, j])` (RNG R3), call Combat `resolve(encounter, gen)`. Survivors carry `hp_after` into duel `j + 1`; the dead leave the lineup. If the duel is lost (wiped or timeout), the bout is **lost** at duel `j`; stop. If every champion is beaten, the bout is **won**.
5. **Won:** swap the player's seat with the target's seat in `ladder` (the guild's ID is looked up again; if it is gone, see Edge Cases). If the player's new rank is better than `best_rank`, set `best_rank`, store `pending_best = {c, L_op}` for P4 (F5), and emit `arena_new_best` (1805). Emit `arena_rank_changed` (1802).
6. Emit `arena_bout_resolved` (1801) with the result in every case.
A bout is atomic and applied in the tick it is resolved; there is no deadline and no saved bout in progress (Combat R2's deadline exists for callers whose result other systems can see; an arena result touches only the arena's own record). The world view plays the duels back from the timeline after the fact (UI Requirements).

**R7 — The duel encounter.** Combat R3 fields:

| Field | Arena value |
|---|---|
| `groups` | One group: the lineup's surviving members, in the player's order |
| `monster` | The champion row (F1) |
| `hp_scale` | 1.0 (strength lives in the row's multipliers) |
| `dmg_scale` | `arena_dmg_scale` (30, F1) |
| `attack_interval_base_s` | 1.0 |
| `targets_per_attack` | 1 |
| `enrage_every_s`, `enrage_atk` | disabled |
| `time_limit_s` | `arena_duel_time_s` (120) |
| `want_timeline` | true when the arena view is open (never changes the outcome) |

Group-scoped rules apply within the lineup as in a hunt: the buffer bonus if any lineup member is a buffer at the start of that duel, the healer's heal, tank aggro (Combat R8–R10). The champion's own role does not give it heals or buffs: it is one monster-shaped combatant.

**R8 — Arena day, tickets and the daily reward (P4 `economy`, order 1800).** Each tick, if the arena is available:
1. Resize the ladder if needed (R3).
2. If `pending_best` is set: roll the new-best reward (F5) and clear it.
3. If `arena_day(now) > day` (F3): pay the daily rank reward (F4) for `min(arena_day(now) − day, arena_backlog_days)` days at the player's **current** rank and the current `reward_mult`; set `tickets = arena_daily_challenges` (tickets do not accumulate); set `day = arena_day(now)`; emit `arena_daily_reward` (1803).
The gold goes to the guild fund through Gold economy (27) as an `arena_reward` mint (Gold economy entry type 12). Prestige goes to the guild's prestige total through Jianghu (17) `add_prestige(guild_id = 0, amount, source = arena)` (PROVISIONAL owner of guild prestige, OQ-4).

**R9 — No XP, no member effect.** Bouts award no XP, no personal gold and no wallet changes; they cost no HP, cause no death or injury and request no member state change. Members used in a bout keep doing whatever they were doing (an `idle` member may start a trip in the same tick). The arena changes Retention (16) nothing directly; any mood effect of winning is out of scope (OQ-7).

**R10 — Offline.** Bouts happen only from a player command, so the arena does nothing while the app is closed except what R8 settles from the day count: on the first tick after an absence, at most `arena_backlog_days` days of rank reward are paid and the tickets are refilled once. NPC guilds never move seats on their own. Offline progress (31) needs no arena-specific path, provided the P4 handler runs at least once after the hand-off (PROVISIONAL).

**R11 — Registration.** Event type and command block 1800–1899 (Event bus R3, Command layer: owner system number × 100). Handlers: P1 order 1800 (commands), P3 order 1800 (bouts), P4 order 1800 (resize, rewards, day). Save section `arena` (Local save R6) with an invariant check: `ladder` contains `0` exactly once and no duplicate ID; `1 ≤ best_rank ≤ |ladder|`; `tickets ≤ arena_daily_challenges`. A pending challenge or `pending_best` never survives a tick and is not saved. Feature fail code **18001** `ARENA_LINEUP_INVALID`: Jianghu returned an empty lineup or a champion with an unknown school (a defect in 17; the tick fails rather than guessing, Sim core R10).

### States and Transitions

**Arena availability**

| State | Entered when | Leaves to |
|---|---|---|
| `Unavailable` | `bld_arena` not built | `Open` when `opponents` first returns a value (R3.1 seeds the ladder) |
| `Open` | Ladder exists | `Open` (resize, R3); `Unavailable` only if the building is removed (not a player action today) |

**Per bout (inside one tick)**

| Step | Phase | Next |
|---|---|---|
| `Pending` | P1, accepted `arena_challenge` (ticket spent) | `Resolved` in P3 of the same tick |
| `Resolved` (won or lost) | P3 | rewards for a new best in P4 of the same tick; then gone |

Refusal reasons (event 1804 `a`): 1 `unavailable`, 2 `busy`, 3 `no_ticket`, 4 `bad_target`, 5 `bad_lineup`, 6 `member_busy`. Bout outcomes (event 1801): `won`, or `lost` with the duel index and Combat's reason (`wiped` or `timeout`).

There is no member-side state: the arena never calls Member state machine's request calls (R9).

### Interactions with Other Systems

| System | Direction | Data | Owner of the interface |
|---|---|---|---|
| Sim core and tick loop (1) | in | P1, P3, P4 handlers; `tick`, `tick_rate`; `ctx.derive` | Sim core |
| Deterministic RNG (2) | in | Domain 16 `arena`, key `[challenge_ordinal, duel_index]`; loot domain 2 key `[0, 3, challenge_ordinal]` | RNG owns derivation; this GDD owns the domain-16 key |
| Data layer (3) | in | `schools` (element, role), `zones`, `drop_tables`, `buildings`, `sim_params` (arena knobs) | Data layer |
| Event bus (42) | out | Types 1801–1805 | This GDD owns the block |
| Command layer (5) | in | Command 1801 `arena_challenge` | This GDD owns the command |
| Local save (6) | both | Section `arena` | Save owns the envelope |
| Member model (8) | in | Member stats (`dps`, `hp_max`, `def`), school, top level of the roster (F4) | Member model |
| Combat (10) | out | `resolve(encounter, gen)` per duel, with full starting HP (PROVISIONAL) | Combat owns `resolve` |
| Zones and hunt trips (11) | in | Zone level bands and drop table IDs (`zones.csv`) for the new-best roll | Zones owns the content |
| Retention (16) | none directly | Former members reach NPC lineups through 17 | — |
| Jianghu free agents and NPC guilds (17) | in / out | `npc_guilds()`, `arena_lineup(guild_id)`, `add_prestige(...)` | Jianghu (PROVISIONAL, undesigned) |
| Items and loot (26) | out | Guild loot roll with source tag 3 into storage | Items owns rolls and storage |
| Gold economy (27) | out | `arena_reward` mint to the fund | Gold economy (entry type 12) |
| Guild and buildings (30) | in | `effect(bld_arena, opponents)`, `effect(bld_arena, reward_mult)` | Guild and buildings |
| Offline progress (31) | in | One P4 pass after a hand-off settles days (R10) | Offline (PROVISIONAL) |
| Member state machine (41) | in | `state_of(member_id)` query only | 41 |
| Leaderboards (35), Quests (25), AI text layer (36) | out | Read-only `best_rank`, current rank; events 1801–1805 | Consumers (the arena ladder is never uploaded, GDD §6.11) |
| Realtime world view (38), Guild screens (39) | out | Events and the duel timelines | Consumers |

## Formulas

Integers are exact; the champion multipliers (F1) are IEEE-754 binary64, evaluated left to right as written (`GODOT_PORT.md` rule 3, as Combat). Arena knobs are new keys in `data/sim_params.csv` (PROVISIONAL, OQ-5). `opponents` and `reward_mult` come from `buildings.csv` (`bld_arena` effects).

`systems-designer` lens applied (Sections D, E, G). Values below were calibrated in this session with a scratch harness over the reference `sim/hunt.fight` (a standard Wave 1 party `tho_1, moc_1, kim_2, hoa_2, thuy_1`, PA 100, auto-geared at level L, 150 seeds per cell, against a five-champion lineup `kim_2, tho_1, hoa_2, moc_1, thuy_1` at the same level). They are a starting point: S7 (`sim/world.py`) and the balance simulator must re-run them once Skills (S4) and Enhancement (S5) change member power.

### F1 — Champion row

The champion_row formula is defined as:

`arch = arena_archetype[role(school)]`
`P = power_milli / 1000`
`champion = { level: clamp(level, 1, 200), element: element(school), hp_mult: arch.hp × P, atk_mult: arch.atk × P, def_mult: arch.def, speed: 1.0 }`
and the duel encounter uses `dmg_scale = arena_dmg_scale` (R7), so the champion's hit is Combat F1 `mon_hit` × `arena_dmg_scale`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| school, level, power_milli | string, int, int | any live school; 1–200; 500–2000 assumed | calculated (Jianghu 17 `arena_lineup`, PROVISIONAL) | One champion of the NPC lineup |
| role(school), element(school) | enum | `schools.csv` | data file | The school's role and element |
| arena_archetype | table role → (hp, atk, def) | see below | data file (`sim_params.csv`, 12 keys `arena_<arch>_hp/atk/def`) | Champion shape by role |
| arena_dmg_scale | float | 30 (safe 20–40) | data file (`sim_params.csv`) | How hard champions hit relative to a same-level monster; the main difficulty knob |

Archetypes (role → archetype: `tank`, `tank_guardian` → **tank**; `healer_support`, `buff_mp_support` → **support**; `melee_burst`, `melee_dps`, `ranged_dps` → **striker**; `control_caster`, `control_summoner`, `dot_debuff` → **caster**):

| Archetype | hp | atk | def |
|---|---|---|---|
| tank | 4.0 | 0.70 | 1.6 |
| support | 3.0 | 0.85 | 1.0 |
| striker | 2.3 | 1.40 | 0.9 |
| caster | 2.5 | 1.15 | 1.0 |

The role-to-archetype map is a constant of this GDD (a new school role must be added to it; the content validator rejects a role with no archetype). A champion's element applies through Combat F3 in both directions, so countering the lineup element by element is the player's lever.

**Output Range:** with `P` in 0.5–2.0, hp_mult 1.15–8.0, atk_mult 0.35–2.8, def_mult 0.9–1.6 (inside or near today's monster ranges, Combat F1: hp 0.7–22, atk 0.9–2.2, def 0.7–2.0). Calibration of the whole bout (win %, mean bout length in s):

| Level | P 0.9 | P 1.0 | P 1.1 | P 1.2 |
|---|---|---|---|---|
| 60 | 100%, 38 | 76%, 45 | 1%, 47 | 0%, 43 |
| 100 | 100%, 36 | 96%, 41 | 26%, 47 | 0%, 45 |
| 140 | 100%, 37 | 99%, 42 | 35%, 48 | 0%, 47 |

A same-level lineup at `P = 1.0` is a hard win for a well-built guild, `P = 1.1` is a coin flip at mid levels, `P = 1.2` is out of reach. Ten levels of difference shift the break-even by about 0.2 in `P` (level L−10: break-even about P 0.8 at L60, 0.95 at L140). The curve is steep on purpose: outcomes follow the guild's strength, not the dice.
**Example:** a `kim_2` champion (striker) at level 100, `power_milli` 1100: `hp_mult = 2.3 × 1.1 = 2.53`, `atk_mult = 1.4 × 1.1 = 1.54`, `def_mult = 0.9`, element Kim. Combat F1: `mon_hp = 40 × 100^1.3 × 2.53 ≈ 40,290`; `mon_hit = 6 × 100^1.25 × 1.54 × 0.05 × 30 ≈ 4,380` before defence; against the reference L100 tank (`def ≈ 1,180`, `K(100) = 850`) it lands `≈ 4,380 × 850 / 2,030 ≈ 1,834` on a 16,400-HP tank.

### F2 — Challenge reach

The challenge_reach formula is defined as:

`can_target(t) = (ladder[t − 1] ≠ 0) and (r − arena_reach ≤ t ≤ r − 1)` where `r` is the player's rank

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| r | int | 1 – (N + 1) | calculated (index of `0` in `ladder` + 1) | The player's rank |
| t | int | 1 – (N + 1) | command argument | The target rank |
| arena_reach | int | 2 (safe 1–3) | data file (`sim_params.csv`) | How many seats up the player may challenge |

**Output Range:** 0 to `arena_reach` legal targets; 0 at rank 1. The climb from the bottom of an 11-seat ladder to rank 1 needs at least `ceil(10 / arena_reach)` = 5 wins at reach 2.
**Example:** player rank 6, reach 2: ranks 4 and 5 are legal; rank 3 is refused (reason 4).

### F3 — Arena day

The arena_day formula is defined as:

`arena_day(tick) = tick div (arena_day_s × tick_rate)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| tick | int64 | ≥ 0 | calculated (Sim core tick counter) | Current tick |
| arena_day_s | int | 86,400 (safe 3,600–86,400) | data file (`sim_params.csv`) | Length of an arena day in seconds of sim time |
| tick_rate | int | 10 | data file (`config.csv`, Sim core R1) | Ticks per second |

**Output Range:** non-decreasing integer; increments once per 864,000 ticks at defaults. Uses the tick count, not `utc_s()`, so it is deterministic under replay (Sim core R6: features read no clock). The day boundary is therefore anchored to the save's tick 0, not to local midnight (OQ-6).
**Example:** tick 2,000,000 → day 2.

### F4 — Daily rank reward

The daily_reward formula is defined as:

`steps = S − r + 1` where `S = |ladder|` (NPC seats + 1)
`gold_day = arena_gold_per_level × L_top × steps × reward_mult_milli div 1000`
`prestige_day = arena_prestige_per_step × steps × reward_mult_milli div 1000`
`paid_days = min(arena_day(now) − day, arena_backlog_days)`; totals are `paid_days × gold_day` and `paid_days × prestige_day`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| r, S | int | 1–11, 4–11 | calculated (`ladder`) | Player rank, ladder size |
| L_top | int | 1–200 | calculated (Member model: highest level on the roster at payment) | Scales gold with the guild's stage |
| reward_mult_milli | int | 1100–1800 | data file (`buildings.csv` `reward_mult` × 1000, rounded) | Building level bonus |
| arena_gold_per_level | int | 100 (safe 25–300) | data file (`sim_params.csv`) | Gold per level per rank step per day |
| arena_prestige_per_step | int | 10 (safe 1–50) | data file (`sim_params.csv`) | Prestige per rank step per day |
| arena_backlog_days | int | 3 (safe 1–7) | data file (`sim_params.csv`) | Days of reward an absence can pay at most |

**Output Range:** bottom seat of a level-1 Lôi Đài (S 4, r 4) at L_top 60: `100 × 60 × 1 × 1.1 = 6,600` gold and 11 prestige a day. Top of a level-8 Lôi Đài (S 11, r 1) at L_top 150: `100 × 150 × 11 × 1.8 = 297,000` gold and 198 prestige a day, about 2 hours of one member's income (GDD §19.1: ≈ 1000 × level per hour) and under 1% of a 20-member guild's daily income: the arena's gold is a garnish, its value is prestige and the new-best loot. Zero is impossible (`steps ≥ 1`, `reward_mult ≥ 1.1`).
**Example:** rank 3 of 8 (S 8, steps 6) at Lôi Đài level 5 (`reward_mult` 1.5), L_top 120, after 5 days away: `gold_day = 100 × 120 × 6 × 1500 div 1000 = 108,000`; `paid_days = min(5, 3) = 3`; total 324,000 gold and `3 × 90 = 270` prestige.

### F5 — New-best reward

The new_best_reward formula is defined as:

`L_op = max level among the beaten lineup's champions`
`zone(L_op) = the live zone with the greatest level_min ≤ L_op` (lowest-order live zone if none; the same rule as Endless Tower F3)
`reward = arena_best_rolls` rolls of `drop_<zone(L_op)>` at monster level `L_op`, `luck_milli = 1000`, loot key `[0, 3, c]`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L_op | int | 1–200 | calculated (F1 levels) | Strength of the guild just beaten |
| c | int | ≥ 1 | calculated (`challenge_ordinal` of the winning bout) | Loot event key component |
| arena_best_rolls | int | 3 (safe 1–5) | data file (`sim_params.csv`) | Table rolls per new best rank |
| table | drop table | `drop_zone_XX` | data file (`drop_tables.csv`) | The zone's own table (Items R2) |

Several rolls are one loot event, as Endless Tower F4 (PROVISIONAL: Items and loot accepts a roll count, the same open item as Endless Tower OQ-5). Source tag 3 is the next free tag after Endless Tower's 2 (Items R3: "`[0, t, …]` for t ≥ 3 for later sources").

**Output Range:** at most one roll event per rank the player newly reaches, so at most `N` events per ladder size, plus one per seat added by a growth (R3.2 shifts `best_rank`, so new top seats are new bests). With 10 seats at `arena_best_rolls = 3`: at most 30 table rolls over the save. Expected per event in zone_10 at L97 about 3.3 grade-1, 0.9 grade-2, 0.12 grade-3, 0.05 rare equipment and 3 × base gold (from Endless Tower F4's per-roll figures).
**Example:** the player climbs from rank 4 to rank 3 for the first time, beating a lineup whose best champion is level 112: `zone(112) = zone_11`, 3 rolls of `drop_zone_11` at level 112, key `[0, 3, 41]`.

### F6 — Bout budget

The bout_budget formula is defined as:

`duels ≤ arena_lineup_max`; `sim_seconds ≤ arena_lineup_max × arena_duel_time_s`; `bouts_per_day ≤ arena_daily_challenges`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| arena_lineup_max | int | 5 (constant, GDD §6.12 party size) | constant | Members per side |
| arena_duel_time_s | int | 120 (safe 60–300) | data file (`sim_params.csv`) | Combat time limit per duel |
| arena_daily_challenges | int | 5 (safe 1–10) | data file (`sim_params.csv`) | Tickets per arena day |

**Output Range:** one bout is at most 5 `resolve` calls and 600 s of event-timeline time (observed 36–48 s); one tick holds at most one bout (R5.2), so the P3 cost is bounded and small next to a Golden Boss raid. Events per bout: 1–3 (1801, plus 1802 and 1805 on a win).
**Example:** 5 tickets a day × 5 duels = at most 25 fights per arena day.

**Feedback loops.** *Positive:* a higher rank pays more prestige, which (through Jianghu and Recruitment, PROVISIONAL) attracts better recruits, who climb further. Damped by the fixed ladder size, the steep F1 curve (the top seats are simply stronger guilds), and the fact that the only farmable part (daily reward) is small. *Negative:* none inside the arena; NPC guild growth (17) is the pressure that keeps seats contested.

## Edge Cases

- **If the player is at rank 1**: every `arena_challenge` is refused with reason 4; tickets still refill daily and are simply unused; the top daily reward is paid. The panel shows "Champion of the Lôi Đài" and the next upgrade's added seats. Intended: the way up after rank 1 is a building upgrade (R3.2).
- **If Jianghu has fewer NPC guilds than `opponents`**: the ladder holds all of them (R3.1/R3.2 take `min`); it grows when 17 adds guilds. If Jianghu has **no** NPC guild, the ladder is just the player at rank 1; no challenge is possible and the rank-1 reward is `steps = 1` (S 1), the bottom amount.
- **If the target guild leaves the ladder between P1 and P3 of the same tick** (a resize in P4 runs after P3, so this can only happen if 17 removes the guild during P3): the bout still resolves against the lineup read in P3; if won and the guild is no longer seated, the player's seat does not move, no new best is recorded, and 1801 reports `won` with `swapped = 0`. The ticket is spent.
- **If `arena_lineup` returns an empty list or an unknown school**: fail code 18001 (R11). A lineup longer than 5 is truncated to the first 5 and is a content warning, not a failure.
- **If a lineup member is removed from the roster between P1 and P3** (departure resolved in P2): the member is dropped from the lineup; if none remain, the bout is lost at duel 0 with reason `wiped` and the ticket is spent. Departure in the same tick as a challenge is rare and the cost is one ticket.
- **If the lineup has one member, or only healers**: legal. A lone healer deals little damage and usually loses duel 0 by `timeout`; the panel warns before the challenge when the lineup has no damage dealer.
- **If a duel times out with survivors**: the bout is lost (no draw); survivors' HP is discarded (spar).
- **If the player wins the last duel with one member at 1 HP**: a win; HP is discarded.
- **If two days or more pass while the app is open but no tick runs** (paused): the clock owes the time (Sim core R9); on the next P4 the backlog cap applies as for an absence.
- **If the player is away for longer than `arena_backlog_days`**: only `arena_backlog_days` days are paid; the tickets of missed days are lost (they never accumulate). Intended: the arena is a daily habit, not a stockpile.
- **If the player's rank changes during a backlog payment**: it cannot; rewards are paid in P4 before any later challenge, and NPCs never move seats.
- **If `bld_arena` upgrades and inserts seats above the player**: the player's rank number rises (worse); `best_rank` shifts with it, so the new seats are unclaimed new bests and their first reach pays F5. Daily reward `steps` does not change from the insertion itself (`S − r` is unchanged), but `reward_mult` rises.
- **If `opponents` shrinks** (arrears decay, if Guild and buildings applies it to this key, or a content change): seats are removed from the top (R3.3); the player can never be removed; `best_rank` floors at 1. No reward is clawed back.
- **If a former member sits in an opponent's lineup and the player rehires them** (Jianghu 17): the next `arena_lineup` read no longer includes them; a lineup can change between the panel preview and the bout, and the bout always uses the read in P3. The preview is marked as "as of now".
- **If the same member could appear on both sides** (a member on the roster and a stale former-member champion): impossible if Jianghu removes rehired members from NPC rosters (PROVISIONAL); if it happens, the champion fights as an ordinary champion row (it is a copy, not the member).
- **If a save is reloaded to retry a lost bout**: `challenge_ordinal` and `tickets` are saved, so the same challenge re-rolls the same dice with the same inputs (RNG R5) and gives the same result; a changed lineup gives a different, still-deterministic fight. Reload-scumming changes nothing that a lineup change would not.
- **Degenerate strategy — a pure counter lineup**: stacking five members of the element that counters the opponent's dominant element is intended play (the lever of Combat F3). NPC lineups (17) should mix elements so no single stack beats every seat (PROVISIONAL requirement on 17).
- **Degenerate strategy — staying low for easy wins**: impossible; no reward is paid per win, and a win always moves the player up.

## Dependencies

**Upstream (this system depends on)**

| System | Type | Interface | Status |
|---|---|---|---|
| Combat (10) | Hard | `resolve(encounter, gen)`, `FightResult` (`won`, `reason`, `hp_after`, `died`, `timeline`); R3 encounter fields with a synthetic monster row and a caller-supplied starting HP | GDD exists (PROVISIONAL: synthetic rows and starting HP, OQ-2) |
| Jianghu free agents and NPC guilds (17) | Hard | `npc_guilds()` (id, name, `power_milli`), `arena_lineup(guild_id)`, `add_prestige(guild_id, amount, source)`, former-member mapping | **PROVISIONAL: no GDD** (OQ-1, OQ-4) |
| Deterministic RNG (2) | Hard | Domain 16 `arena`; `derive` | GDD exists |
| Guild and buildings (30) | Hard | `effect(bld_arena, opponents)`, `effect(bld_arena, reward_mult)` | GDD exists |
| Member model (8) | Hard | Stats (`dps`, `hp_max`, `def`), school, level | GDD exists |
| Member state machine (41) | Hard | `state_of(member_id)` query | GDD exists (no new state needed) |
| Items and loot tables (26) | Hard | Guild loot roll with source tag 3, `luck_milli = 1000`, roll count | GDD exists (PROVISIONAL roll count, shared with Endless Tower OQ-5) |
| Zones and hunt trips (11) | Hard (data) | `zones.csv` level bands; zone drop tables | GDD exists |
| Sim core (1), Data layer (3), Event bus (42), Command layer (5), Local save (6) | Hard | Phases and tick counter, content tables, type block 1800, command 1801, save section `arena` | GDDs exist |
| Schools and school change (20) | Hard (data) | `element`, `role` per school | GDD exists |
| Gold economy (27) | Soft | `arena_reward` mint to the fund | GDD exists (entry type 12, OQ-3 resolved) |
| Offline progress (31) | Soft | One P4 pass after a hand-off (R10) | GDD exists (PROVISIONAL, no arena path expected) |

**Downstream (depend on this system)**

| System | Type | Interface |
|---|---|---|
| Jianghu (17) | Soft | Arena is the consumer that gives NPC guild strength a player-visible meaning |
| Quests and achievements (25) | Soft | Events 1801, 1802, 1805 |
| Leaderboards (35) | Soft | None by design: the arena ladder stays local (GDD §6.11); 35 must not upload it |
| AI text layer (36), Event history / Chronicle (42) | Soft | Events 1801–1805 for narration ("defeated by former disciple …") |
| Realtime world view (38), Guild screens (39) | Soft | Events, duel timelines, `ladder`, `best_rank`, `tickets` |

Bidirectional note: Combat, RNG and Guild and buildings already list the Arena (Combat Interactions and Dependencies, RNG domain table, Guild and buildings soft consumers). Items and loot (R3 reserves tags ≥ 3 for later sources), Gold economy (entry types) and Member state machine do not name the Arena yet; a later consistency pass adds them. This GDD does not edit them.

## Tuning Knobs

| Knob | Default | Safe range | Too low | Too high | Interacts with |
|---|---|---|---|---|---|
| `arena_dmg_scale` | 30 | 20–40 | Every same-level seat is a free win; the ladder is decided by tickets alone | Same-level seats are unwinnable; only over-levelled guilds climb | `power_milli` range (17); member power (S4, S5); recalibrate together |
| `arena_<arch>_hp/atk/def` (12 keys) | table in F1 | ±30% of default | One archetype becomes a free duel | One archetype walls every lineup | `arena_dmg_scale`; Combat F3 element mult |
| `arena_duel_time_s` | 120 | 60–300 | Healer-heavy lineups lose to timeout | Little effect (observed duels ≤ 15 s); raises worst-case cost | Combat `time_limit_s` |
| `arena_reach` | 2 | 1–3 | Climb is slow, one seat at a time | Skipping seats makes the middle of the ladder irrelevant | Ladder size (`opponents`) |
| `arena_daily_challenges` | 5 | 1–10 | A loss blocks the day | Daily cap stops mattering; climbs finish in a day | `arena_reach` (climb speed = tickets × reach) |
| `arena_day_s` | 86,400 | 3,600–86,400 | Daily reward becomes an hourly faucet (scales payout ×24) | — (one day is the design) | `arena_backlog_days` |
| `arena_backlog_days` | 3 | 1–7 | Players who miss a day lose most of the reward | Long absences pay a week at once | Golden Boss backlog (3, Offline 31) for consistency |
| `arena_gold_per_level` | 100 | 25–300 | Gold reward invisible | Arena becomes a gold faucet competing with hunting (§19.5 out/in target) | `reward_mult`; §19.1 income |
| `arena_prestige_per_step` | 10 | 1–50 | Rank is meaningless to prestige | Arena dominates prestige over other sources (17 owns the total) | Prestige consumers (Recruitment, PROVISIONAL) |
| `arena_best_rolls` | 3 | 1–5 | New best feels unrewarded | Arena loot rivals the Tower's first-clears | Endless Tower F4 rolls |
| `opponents`, `reward_mult` | `buildings.csv` | owned by Guild and buildings | — | — | Ladder size, F4 |

Climb pacing at defaults: from the bottom of a 3-seat ladder to rank 1 takes 2 wins; a full 10-seat ladder takes at least 5 wins (one day of tickets if every bout is won), but realistically weeks, because each seat up is a stronger guild (F1).

## Visual/Audio Requirements

`art-director` lens applied in this session (no art bible exists yet; constraints from GDD §12.4: code-drawn minimal style is the fallback art plan).

1. **The platform.** One arena scene (the Lôi Đài stage) reused for every duel: the player's lineup on one side, the current champion on the other, the remaining champions waiting in a row. A champion is drawn with its school's member sprite (it is a person, not a monster), even though the sim treats it as a monster row.
2. **Playback.** Each duel replays Combat's timeline (Combat R14) at 1× with a 2× / skip option; hit numbers and the element-counter tint follow Combat V/A. Between duels a 0.5 s "next challenger" beat.
3. **Former members** carry a marker (a broken-tie ribbon icon) and their old name in the champion card.
4. **Result.** Win: the seat banner swaps on the ladder board with a short climb animation; new best adds a loot chest drop. Loss: the deciding duel's champion is highlighted with the reason (`wiped` or `timeout`).
5. **Audio.** A drum roll at bout start, one gong per duel won, a crowd cheer on a bout win, a muted gong on loss. No looping arena music beyond the guild theme (audio budget, Audio 40).

> **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:arena` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

- **Instant verdict, watchable proof.** The result exists the moment the player taps challenge (it resolved in the tick); the playback is optional and skippable. The ladder board updates when the playback ends or is skipped, never before, so the reveal is not spoiled.
- **Target lengths.** A bout plays back in 36–48 s at 1× (observed in calibration); 2× halves it; skip shows the summary within 0.3 s.
- **No chore.** One tap to challenge from the ladder board with the last lineup pre-filled; lineup editing is a drag-reorder of up to 5 portraits. No confirmation dialog unless the lineup has no damage dealer.
- **Readable loss.** The loss summary always names one duel and one cause, plus a suggested counter element for that champion (from Combat F3).

## UI Requirements

1. **Ladder board** (main arena panel): every seat with rank, guild name, power band (a 1–5 star bucket of `power_milli`, never the raw number), and the player's seat highlighted; challengeable seats (F2) marked; tickets left and time to the next arena day; today's reward at the current rank.
2. **Opponent preview**: the target's lineup as of now, champion by champion (school, element, level, archetype, former-member marker); the player's element matchups against each champion shown as counter/neutral/countered icons with text labels (not colour alone).
3. **Lineup editor**: pick 1–5 members who are `idle` or `resting` (others greyed with their state), reorder by drag; warnings: no damage dealer, no tank, all one element.
4. **Bout playback and summary**: per-duel result list; deciding duel and reason; rank change; new-best loot list.
5. **Daily reward toast** on the first tick of a new arena day, including backlog days paid.
6. All strings through Localization (4); guild names from Jianghu's (17) name pool.

> **📌 UX Flag — Arena**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for each screen or HUD element this system contributes to **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD references | GDD | Section / rule | Nature |
|---|---|---|---|
| One resolver, encounter fields, starting snapshot, result fields | `combat.md` | R2, R3, R4, R8–R10, R14, F1, F3 | Rule dependency (PROVISIONAL extensions OQ-2) |
| Domain 16 `arena`, `derive`, inputs not in keys | `deterministic-rng.md` | R3, R5, R10, domain table | Rule dependency |
| `effect()`, upgrade keeps old level | `guild-and-buildings.md` | R6, R7, R8 | Rule dependency |
| `state_of` query | `member-state-machine.md` | R6 queries, state codes | Rule dependency |
| Guild loot roll, source tag reservation | `items-and-loot-tables.md` | R2, R3, R3a, R9a | Rule dependency (source tag 3) |
| Mint entry types | `gold-economy.md` | R2, R3 | Rule dependency (`arena_reward`, type 12) |
| Departed members → Jianghu | `retention-leaving-and-negotiation.md` | R8, OQ-4 | Context (former members as champions) |
| Zone lookup by level, roll counts | `endless-tower.md` | F3, F4, OQ-5 | Shared pattern (same zone rule, same roll-count open item) |
| Phases, tick counter, no clock reads, owed time | `sim-core-and-tick-loop.md` | R1, R6, R7, R9, R10 | Rule dependency |
| Type and command blocks | `event-bus-and-history-log.md`, `command-layer.md` | R3; ID blocks | Rule dependency |
| Save sections and invariants | `local-save-and-migration.md` | R6 | Rule dependency |
| Day-boundary settlement after absence | `offline-progress.md` | hand-off | Rule dependency (PROVISIONAL) |

## Acceptance Criteria

`qa-lead` lens applied: every core rule and formula has at least one criterion; all are runnable headless with a fake Jianghu (17) supplying fixed guilds and lineups.

- **AC-1 (R1)**: **GIVEN** no `bld_arena`, **WHEN** `arena_challenge` is sent, **THEN** it is refused with 1804 reason 1 and no state changes; the panel is hidden.
- **AC-2 (R3.1)**: **GIVEN** `bld_arena` level 1 completes and Jianghu has 10 guilds with powers 600…1500, **WHEN** the next P4 runs, **THEN** `ladder` = the 3 weakest in descending power then `0`, the player is rank 4, `best_rank = 4`, `tickets = 5`.
- **AC-3 (R3.2)**: **GIVEN** the AC-2 ladder with the player at rank 2, **WHEN** `bld_arena` reaches level 2 (`opponents` 4), **THEN** the 4th-weakest guild is inserted at rank 1, the player is rank 3, `best_rank` shifted by 1, and no reward or loot is paid.
- **AC-4 (R3.3)**: **GIVEN** a ladder of 4 NPC seats with the player at rank 3, **WHEN** `opponents` becomes 3, **THEN** the top NPC seat is removed, the player is rank 2, and the player is never removed in any shrink.
- **AC-5 (R5, F2)**: **GIVEN** the player at rank 6, reach 2, 1 ticket, **WHEN** challenges target ranks 3, 4, 7, **THEN** rank 3 and 7 are refused (reason 4), rank 4 is accepted and `tickets = 0`; a further challenge is refused (reason 3).
- **AC-6 (R5.5–6)**: **GIVEN** a lineup with a duplicate ID, 6 IDs, or a member in `hunting`, **WHEN** challenging, **THEN** refused with reasons 5, 5, 6 respectively, and no ticket is spent.
- **AC-7 (R6, R7)**: **GIVEN** a fixed lineup and a fake 3-champion opponent, **WHEN** the bout resolves, **THEN** Combat `resolve` is called once per duel until a loss, with generators `derive(16, [c, 0])`, `[c, 1]`, … and the R7 encounter values; duel 0 starts every member at `hp_max`; duel `j+1` starts at duel `j`'s `hp_after`.
- **AC-8 (R6 determinism)**: **GIVEN** the same save, **WHEN** the same challenge is replayed twice (reload), **THEN** both bouts give identical results and timelines.
- **AC-9 (R6.5)**: **GIVEN** a won bout from rank 4 against rank 3 with `best_rank = 4`, **THEN** the seats swap, `best_rank = 3`, events 1801, 1802, 1805 are emitted in that order, and P4 of the same tick rolls F5 once with key `[0, 3, c]`.
- **AC-10 (R9 spar)**: **GIVEN** a lineup member at 40% HP in `resting`, **WHEN** a bout is fought and lost with that member dying in duel 1, **THEN** after the tick the member's HP, death counter, XP, wallet and state are exactly as before.
- **AC-11 (F1)**: **GIVEN** a `kim_2` champion, level 100, `power_milli` 1100, **THEN** the champion row is `hp_mult 2.53, atk_mult 1.54, def_mult 0.9, speed 1.0, element kim` (binary64, exact to the formula), and every school role maps to one archetype (validator test over `schools.csv`).
- **AC-12 (F1 calibration)**: **GIVEN** the reference party of F1 at level 100 and a same-level 5-champion lineup, **WHEN** 150 seeded bouts run in the balance simulator, **THEN** win rate is ≥ 90% at `P = 0.9`, between 10% and 90% at `P = 1.1`, and ≤ 10% at `P = 1.2` (re-baselined after S4/S5).
- **AC-13 (F3, R8)**: **GIVEN** `day = 2` and 1 ticket left, **WHEN** the tick crosses into arena day 3, **THEN** one daily reward is paid, `tickets = 5`, `day = 3`, event 1803 emitted once.
- **AC-14 (F4)**: **GIVEN** rank 3 of 8, `reward_mult` 1.5, `L_top` 120, last settled day 5 days ago, **WHEN** P4 runs, **THEN** exactly 324,000 gold is minted to the fund as `arena_reward` and 270 prestige is passed to `add_prestige`.
- **AC-15 (F4 floor)**: **GIVEN** any ladder state, **THEN** `steps ≥ 1` and the daily reward is > 0 gold and > 0 prestige.
- **AC-16 (F5)**: **GIVEN** a new best won against a lineup whose best champion is level 112, **THEN** `drop_zone_11` is rolled `arena_best_rolls` times at level 112 into guild storage, its gold minted to the fund; reaching the same rank again later rolls nothing.
- **AC-17 (R10)**: **GIVEN** an absence of 10 arena days, **WHEN** the first P4 after the hand-off runs, **THEN** exactly 3 days are paid, tickets = 5 (not 50), and the ladder is unchanged.
- **AC-18 (R11)**: **GIVEN** a save whose `ladder` contains `0` twice, **WHEN** loaded, **THEN** the invariant check rejects it; **GIVEN** a fake Jianghu returning an empty lineup, **THEN** the tick fails with 18001.
- **AC-19 (F6)**: **GIVEN** two `arena_challenge` commands in one tick, **THEN** the second is refused with reason 2 and at most 5 `resolve` calls happen in that tick.
- **AC-20 (local only)**: **GIVEN** a cloud sync and a leaderboard submission, **THEN** neither payload contains the `arena` section's ladder or rank (the save section is still part of cloud save as a whole).
- **AC-21 (UI)**: **GIVEN** the arena view, **WHEN** a bout is fought, **THEN** the ladder board updates only after playback ends or is skipped, the loss summary names one duel and one reason, and element matchups have text labels. Evidence: retained screenshots in `production/qa/evidence/`.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | PROVISIONAL: Jianghu free agents and NPC guilds (17) — provides `npc_guilds()` (stable IDs, names, `power_milli` in about 500–2000, growing over real and offline time), `arena_lineup(guild_id)` (1–5 champions `{school_id, level, power_milli, former_member_id}`, mixed elements), removes rehired members from NPC rosters, and keeps ≥ 3 NPC guilds live from Wave 2. | game-designer (17's author) | When 17 is designed |
| OQ-2 | PROVISIONAL: Combat (10) — accepts a caller-built monster row that is not in `monsters.csv` (the champion row, F1) and a caller-supplied starting HP per member (spar at `hp_max`). Alternative if Combat refuses: Combat gains a member-against-member mode (schema change; not taken here). | Combat owner, technical-director | Before S7 |
| OQ-3 | **RESOLVED (consistency-check 2026-11-16):** Gold economy R3 now lists `arena_reward` as entry type 12 (mint → fund, Full Vision). Faucet size still to be balance-checked. | economy-designer | Closed |
| OQ-4 | Who owns **guild prestige (danh vọng)**? GDD §6.7, §6.11 and §8.1 use it (recruit quality, NPC guild strength, leaderboards) but no designed system owns it. This GDD assumes Jianghu (17) `add_prestige`. Scope change for the systems index if it belongs elsewhere (Guild and buildings 30, or a new system). | producer, systems index | Before Wave 2 |
| OQ-5 | New `sim_params.csv` keys for every arena knob (schema/content change, PROVISIONAL as Endless Tower OQ-3); and whether the 12 archetype keys should be their own small table instead. | data owner | With S7 |
| OQ-6 | Arena day anchored to save tick 0 (F3) rather than local midnight. Daily quests (Quests 25, GDD §11.4) will need a shared "game day" definition; whichever system owns it, the arena should use the same one. | Sim core / Quests owner | Vertical Slice |
| OQ-7 | Should arena wins or losses affect member mood or loyalty (Retention 16), or Chronicle entries for rivalries with former members? Out of scope here. | game-designer | Wave 2 |
| OQ-8 | Calibration depends on today's flat-DPS member model; S4 (skills) and S5 (enhancement) will shift it. Re-run the F1 table and AC-12 in `sim/world.py` (S7). | systems-designer | With S7 |
| OQ-9 | Wave 4 asynchronous cloud PvP (GDD §6.11, "shadow" lineups of real players) would reuse the champion-row conversion but needs anti-cheat and moderation; not committed. | producer | Wave 4 |
| OQ-10 | No game pillars exist (systems index, CD-SYSTEMS); the Player Fantasy rests on GDD §6.11 alone. | creative-director | Before production |
