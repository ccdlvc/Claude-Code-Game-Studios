# Zones, Grounds, Monsters and Hunt Trips

> **Status**: In Design
> **Author**: user + Claude (design-system, autonomous batch run; decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no `design/gdd/game-pillars.md`). Serves the locked core loop of `JX1_Tycoon_GDD.md` §1 ("thành viên đi săn → mang tài nguyên về → bang bán/chế tạo/nâng cấp → thành viên mạnh hơn") and §3.2 (one headless core for realtime, offline, simulator and server replay)
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief to check against. Player Fantasy is anchored to `JX1_Tycoon_GDD.md` §1 instead. Re-run once pillars exist.
> **Mode**: retrofit-style authoring against the Python reference `sim/hunt.py` (`fight`, `roll_drops`, `run_trip`, `run_hunt`) and `sim/offline.py` (`estimate_rates`, `fast_forward`). Where this GDD differs from the code, the difference is named and listed in Open Questions.

## Summary

Zones, grounds, monsters and hunt trips is the world the guild's members go out into and the trip they make there: a party leaves the guild for a hunting ground, fights one monster after another, and comes home when its bags are full, its weakest member is hurt or it loses a fight, carrying XP, gold and loot. It owns the 15 zones, 45 grounds and 75 monsters as content, the rules of a trip from departure to settlement, the kill-XP formula, and both ways of resolving trips: the detailed resolver used during live play and the sampled resolver that offline progress uses. It exists because this trip is the game's core loop (GDD §1); almost every other system either feeds it (members, combat, parties) or lives off what it brings home (economy, items, quests, Chronicle).

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Deterministic RNG, Data layer and content pipeline, Sim core and tick loop, Event bus and history log, XP and level pacing curve, Member model, Combat, Items and loot tables, Party, Gold economy, Member state machine`

## Overview

**What it is.** The world map of JX1 Tycoon is 15 zones (`zone_01` … `zone_15`, levels 1–200, GDD §6.3). Each zone has 3 hunting grounds (`grounds.csv`, 45 in all) and 5 monster types: 4 ordinary monsters and 1 zone boss (`monsters.csv`, 75 in all). A *hunt trip* is one round of the guild loop for one hunting group (a party of 1–5 members, formed by Party, 13): travel out, a chain of encounters with monsters picked from the ground's pool, a return home triggered by a defined condition, the sale and split of what was carried, and the rest the members need before they can go again.

**Data layer and player impact.** On the data side, this system owns three content tables (zones, grounds, monsters), builds a frozen boot-time kill-XP table, runs the trip state machine for every active group in the Sim core's P3 `field` phase, and draws its randomness from the RNG domains it owns (3 `spawn`, 4 `hunt_trip`). On the player side, it is the thing the bang chủ (guild master) watches on the map and reads in the "while you were away" report. Members walk to a ground, fight, and come back richer. A badly matched party comes back early and hurt. A ground three levels above the party yields more per kill, while one ten levels below pays half the XP. Zones open as the guild levels up and as members are reborn. The player does not run the trip. They act on its inputs: who hunts together (Party), what each member wears (Items), and which ground is allowed (orders, through the Command layer). Utility AI (12) picks the ground for each group. This system resolves what happens there.

**Why it exists.** Without it there is no core loop: no XP source for the XP curve (22), no gold for the economy (27), no loot for items, crafting and the market (26, 28, 29), and nothing for the world view (38) to show. It is also the system with the largest determinism surface after Combat: every kill is a seeded event, and offline progress (31) is only a driver over its sampled resolver (systems index, TD-SYSTEM-BOUNDARY). Implementation patterns (handler layout, save serializer shape) are left to ADRs; this document describes behaviour.

**Scope.**
- *In:* zone, ground and monster content and its access rules; the trip state machine and return triggers; spawn choice; kill XP and the level-difference penalty; bag capacity; trip timing and rest time; settlement hand-off; the detailed (live) and sampled (offline) resolvers; the simulation LOD rule that picks detailed or card tier per live ground (R17); this system's events, RNG keys and parity table.
- *Out, owned elsewhere:* the fight itself (Combat, 10); which ground a group picks (Utility AI, 12); party formation and the party XP bonus (Party, 13); drop rolls and storage (Items and loot, 26); every credit to a wallet or the guild ledger (Gold economy, 27); member states such as `hunting`, `returning`, `resting`, `dead` (Member state machine, 41); chunking an offline gap (Offline progress, 31); Golden Boss raids (14); the Endless Tower (19), which reuses monster rules but not trips.

## Player Fantasy

**Framing: direct.** The player feels this system on every screen of the realtime map and in every offline report, so it is player-facing (`Gameplay` category).

*No game pillars exist, so no pillar is quoted. The candidates below are anchored to `JX1_Tycoon_GDD.md` §1 (the core loop) and §6.3 (the zone ladder). CD-GDD-ALIGN remains NOT ASSESSED.*

Three framings were considered (creative-director lens):

1. **"They come home richer" (homecoming) — chosen.** *The moment:* a party of five walks back through the guild gate with full bags. A row of gold and item icons rises above them as they sell, and the leader's XP bar ticks past a level. The player did not swing a sword. They chose who went together and what they wore, and the result comes home to them. This framing asks the rest of the design for a visible, frequent, readable *return*: a clear end-of-trip beat, a reason the trip ended, and a summary that names the payoff. GDD §1 describes the game exactly this way ("mang tài nguyên về"), and the trip end is the most frequent payoff the player sees (a full party trip lasts about 15 game minutes today; see Formulas F5).
2. **"Sending them out" (dispatcher's pride).** *The moment:* the player opens the map, sees that Hàn Thuỷ Đầm's water monsters are countered by the guild's earth-element tank, and watches the party head there. It asks for readable ground facts (element, level, danger) and for counters to matter. It is kept as the **secondary line**, because Utility AI makes most picks and the player only overrides them.
3. **"The map opens" (frontier).** *The moment:* the guild reaches level 3 and Hoàng Thổ Cao Nguyên unlocks, a milestone the Chronicle remembers. It asks for meaningful gates and a first-entry beat. It is served by R2 and event 1105, but it happens 15 times in a whole playthrough, too rarely to carry the system.

**Target feeling.** Quiet competence and anticipation: "my guild is out there working, and what comes back shows how well I built it." Failure is legible and never feels like a punishment. A party that comes home early, hurt, has lost a little time and nothing else. Nothing is destroyed and no loot is lost (R8, R9), so the player's reaction is "I should add a healer", not "the game cheated me".

## Detailed Design

### Core Rules

Rules are numbered R1–R16. "The reference" means the Python code in `sim/`.

**Content**

**R1 — Zones, grounds and monsters are content rows.** All three are rows of content tables loaded by the Data layer (3) and looked up only by stable ID or `uid` (Data layer R3, R6):
- **Zone** (`zones.csv`): `order`, `level_min`–`level_max` (descriptive), `primary_element` and `secondary_element` (descriptive; `mixed` for zones 10–15), `wave`, `boss_monster_id`, `guild_lv_req`, `rebirth_req`, `theme` (an art key, not display text).
- **Ground** (`grounds.csv`): `zone_id`, `level_min`–`level_max` (advisory), `capacity` (members, R4), `spawn_rate` (R6), `monster_pool` (a `list(ref(monsters))`, at least 1 non-boss row), `danger` (1–3, display and AI input only). The Data layer adds a `wave` column (Data layer R2). A ground's wave must equal its zone's wave, which the validator checks (F3 forward-reference rule).
- **Monster** (`monsters.csv`): `zone_id`, `level`, `element`, `role` (`swarm`, `melee`, `ranged`, `tank`, `boss`), `hp_mult`, `atk_mult`, `def_mult`, `speed` (attacks per second), `ai_skills` (a list, unused by trips today), `drop_table` (a ref into `drop_tables`), `is_boss`.
- Display names come from `i18n/` by ID (Data layer R9). This system never shows text from a table.

**R2 — Access to a ground.** A hunting group may start a trip at ground `g` in zone `z` only if all of these hold:
1. `content_live(z)` and `content_live(g)` (Data layer F2). This system never compares `wave` itself.
2. Guild level ≥ `z.guild_lv_req`. Guild level is read from Guild and buildings (30).
3. Every member of the group has `rebirth ≥ z.rebirth_req`. That is only zones 11–15 today, which need rebirth 1–5.
4. The ground has room for the whole group (R4).
5. Every member is eligible to start a trip (R3).

The level range of a ground is **advice, not a gate**. A group may hunt above or below it. The level-difference penalty (F2) makes farming far below its level unattractive, and the fight itself makes hunting far above it dangerous. Utility AI (12) reads the level range, `danger`, the monsters' elements and current occupancy (R4) to score grounds. A refused start (any of 1–5 failing) changes nothing and returns a reason code (R14), so the caller can pick again.

**R3 — Who can go.** A member is eligible to start a trip when they are a member of the guild, are not already in a trip, are alive with full HP (every trip ends with members healed, R10), and Member state machine (41) reports them as available to hunt (not `injured`, `boss_raid`, `training`, `away`, and so on). Elders (post-Ascension) earn no XP (XP curve, `Capped`); whether they may hunt at all is owned by Rebirth and Ascension (23) and Member state machine (41).

**R4 — Ground capacity.** `occupancy(g)` is the number of members in trips at `g`, counted from trip start until the trip closes (R10). A group of `n` members may start at `g` only if `occupancy(g) + n ≤ g.capacity` (6, 8 or 10 today). Capacity counts members, not groups. Starts are processed in P3 in ascending `party_id` order (R5), so when two groups compete for the last places, the result is the same on every machine. The reference has no capacity rule. The rule changes where groups hunt, but not what one trip yields, so the calibrated pacing is unaffected (Open Questions OQ-4).

**Trips**

**R5 — A trip and its identity.** A trip belongs to a *hunting group*: the 1–5 members that Party (13) hands over for one trip (a solo member hunts as a party of one; `party_max = 5`). The roster is fixed for the whole trip (Edge Cases). Each trip is identified by the same three numbers Combat (10) and Items and loot (26) already use for the encounter key:
- `party_id`: the key-leader ID Party (13) supplies for every group including a solo hunter — the `member_id` of the trip's key leader (Party R5). It is not a party-record counter: the same leader keys every party they lead and their solo trips;
- `trip_ordinal`: that leader's saved `trips_led` counter, returned by Party `begin_trip(party_id)` at trip start and increased by 1 when, and only when, a trip keyed on that leader starts (Party R5);
- `encounter_ordinal`: 0, 1, 2 … within the trip, increased by 1 for each encounter.

The pair `(party_id, trip_ordinal)` is unique for the life of the save: a member keys at most one trip at a time, member IDs are never reused (Member model R2), and `trips_led` only increases. With `encounter_ordinal` added, every encounter has a unique key (RNG R6, Formulas F9). No component is something the player sets directly, and none is advanced by an unrelated action: re-forming a party does not advance any counter (Party AC-11). Party stores `trips_led` per member (Party R5, R19). *(consistency-check 2026-11-16: aligned to Party R5; OQ-5 resolved.)*

**R6 — The trip, step by step (detailed resolver).** When a start is accepted in P3 of tick N:
1. **Start.** The trip records the ground, the roster, `trip_start_tick = N` and an empty bag (`slots_used = 0`, an empty loot list). It also records the party XP multiplier `xp_mult_ppm`, read once from Party (13) for the roster as it is at the start, and occupancy is increased. It emits **1101** (R13), and the first trip at any ground of zone `z` in this save also emits **1105**.
2. **Outbound.** The group travels for `travel_ms` (F5). No encounter happens while travelling.
3. **Return check.** Before each encounter, the trip checks the return triggers in this order. The first one that holds ends the encounter chain with its reason code (R14):
   1. any queued **recall** or **order home** (R11) — code 4 or 5;
   2. **low HP:** some living member has `hp < flee_hp_pct × hp_max` (0.25 today) — code 1;
   3. **bag full:** Items' `bag_full(bag)` is true (capacity `bag_slots × n`, Items R5; see F4) — code 2.
4. **Spawn.** One monster is chosen uniformly from the ground's non-boss pool (rows with `is_boss = false`, in ascending `uid` order, Data layer R4) with `choice` from a generator derived in domain 3 `spawn` with key F9. Zone bosses never appear in trips (OQ-1).
5. **Fight.** This system builds the encounter (one group: the living members; the monster row; `hp_scale = dmg_scale = 1.0`), derives the fight's generator in domain 1 with key F9, and calls Combat's `resolve(encounter, gen) → FightResult` (Combat R1–R3). Combat owns everything inside the fight: monster stats (Combat F1), targeting, aggro, heals, buffs, Five Elements multipliers, damage variance and the 600 s time limit (`fight_time_limit_s`). The result carries `won`, `reason`, `duration_s`, each member's HP after and `died`. The encounter **ends** at Combat's deadline tick, `start_tick + ceil(duration_s × tick_rate)` (Combat F8). Until then the group is "engaging", and other systems see the pre-fight HP (Combat R2). HP and deaths are applied at the deadline tick.
6. **Loss.** If Combat reports a loss (`reason` `wiped` or `timeout`), the encounter chain ends with code 3 `defeated`. A lost fight pays no XP and rolls no drops.
7. **Kill.** If the fight is won, at the encounter end:
   - the trip's kill count goes up by 1;
   - **XP:** every member who is alive at the end of the fight gets `kill_base_milli` (F1). This system calls `award(member, kill_base_milli, source = hunt_kill)` on the XP curve (22) once per member per kill. Members who died in this fight or earlier in the trip get nothing for this kill, and their share is **not** passed on to the others (the divisor is the full roster, F1);
   - **drops:** Items and loot (26) rolls the monster's `drop_table` once for the kill (domain 2, key `[0, party_id, trip_ordinal, encounter_ordinal]`, Items R3) and adds the result to the party's shared bag (Items R5: gold uses no slot, each item or material unit uses 1 slot, the last kill is always added in full);
   - it emits **1102** and, for each member who died in this fight, **1103**.
8. **Gap.** After a won encounter the group waits `gap_ms` (F6) before the next return check (step 3). After a lost one it goes straight to step 9.
9. **Homebound.** The group travels home for `travel_ms`.
10. **Selling.** The group spends `sell_ms` at the guild. At the end of selling, **settlement** happens (R8).
11. **Rest.** Each member's rest time is F7 (`revive_ms` if dead, else the time to regenerate to full HP). The trip computes `rest_ms = max` over the roster and hands it to Member state machine (41), which runs the rest or revive state. The trip **closes** when the rest ends (R10).

**R7 — The reference's timeline and this one are the same length.** The reference adds `fight + gap` per encounter, and then adds `2 × travel + sell + rest` at the end. This GDD puts one `travel` before the first encounter and one after the last. The trip lasts exactly as long either way (F5), and rates per hour are unchanged. Only the moment at which each event happens differs. A gap is also counted after the last winning encounter, as the reference does. The return check comes after the gap.

**R8 — Settlement.** When selling ends, this system calls Items and loot's `hand_in(party, bag)` (Items R6). Items resolves the bag in its fixed order: equipment by the party loot rule `suited_first` (to a member it suits, otherwise sold), materials to guild storage at their sell value, other items to storage, and the gold accumulator plus all sales as the trip income.
- **What this system guarantees:** the bag holds exactly what this trip's kills rolled, nothing is lost on the way home (not even after a wipe, R9), and `hand_in` is called exactly once per trip.
- **What this system owns:** how the trip income is divided among the roster (Gold economy OQ-11 assigns this to Zones and hunt). The rule, retrofitted from the reference (`share = (gold_pool + value_pool) / n`), is: the income is split equally across the **whole roster**, dead members included, by integer division. The remainder (fewer than `n` gold) goes one gold at a time to members in ascending member-ID order, so no gold is created or lost (S3 money conservation). Each member's share is credited once per trip through Gold economy (27) `credit`, under the mint types `hunt_gold` (the gold-accumulator part) and `loot_handover` (the sale part), each split with the same rule (Gold economy AC-23).
- **Aligned (consistency-check 2026-11-16, OQ-11):** Items R6 step 4 returns `drop_gold` and `sale_gold` to the caller and credits nothing; this system splits and credits them as above. Offline progress (31) applies the same split to the bags it hands in and credits `offline_hunt` (Offline R14).

**R9 — A wipe loses time, never loot.** A group that loses a fight (`defeated`) still travels home, sells and settles its bag. Dead members are revived during rest (`revive_s`, 180 s). There is no XP loss (XP curve R7), no gold loss and no item loss in this system. Injuries and their consequences (GDD §6.4 `injured`) belong to Member state machine (41); this system reports deaths (1103) and nothing more.

**R10 — Closing a trip.** When the rest ends, every member is alive with full HP. In the reference the trip itself does this; here, Member state machine (41) does it at the end of the rest state. The trip record is deleted, occupancy drops by `n`, and **1104** has already been emitted at the moment the encounter chain ended. Members become eligible again (R3). Equipment purchases between trips (the reference's `auto_gear`) are a member action owned by Member model, Items and Gold economy, not by this system.

**R11 — Recall and orders.** Two external requests end a trip early:
- **Recall** (Golden Boss raid, 14, GDD §6.13): the whole group's trip ends at the next return check, with code 4. The fight in progress is already resolved and plays out. The group then skips Homebound, Selling and Rest: settlement happens **immediately** at the encounter end, and the members are handed to the raid, which owns the gathering time and what happens next (PROVISIONAL).
- **Order home** (the player, through the Command layer, 5, GDD §6.4): code 5. The trip ends at the next return check and runs Homebound, Selling and Rest normally.
- A request made while the group is travelling out ends the trip without an encounter: the group turns around and comes back (Homebound starts at once, with the outbound time already spent counted).
- There is no instant teleport. A request never interrupts a fight, because the fight's outcome is already fixed (R6 step 5).

**R12 — The camera never changes an outcome.** During live play, every active trip on every ground is resolved at the tier R17 latched for it — `detailed` or `card` — whether or not the player is looking at that ground. The tier comes from an in-sim rule (R17, F11), never from the camera. The world view (38) only chooses **what to draw**: full sprites near the camera, reduced or no sprites elsewhere (presentation LOD). It never chooses how a trip is computed. Camera position is not in the command log (Sim core R6), so a rule that let it change results would break leaderboard replay (35) and RNG R5. GDD §3.5 ("bãi khác = thống kê theo công thức") is therefore read as a **simulation** LOD decided in-sim (user decision 2026-11-16, OQ-2 resolved). The cost is bounded twice: the resolver is event-driven (P3 does work for a group only on the ticks where one of its steps ends, F8), and card-tier trips call Combat only on card-building chains (F12).
- **`fight_timeline(party_id, trip_ordinal, encounter_ordinal)`** — a side-effect-free, between-tick query for the world view (38). It rebuilds that encounter from saved trip state (roster HP before the fight, monster row, key F9) and calls Combat `resolve(..., want_timeline = true)` on copies with a fresh generator from the same key, returning the timeline. For an encounter replayed from a card (R17) it returns `none`: there is no fight with that key to rebuild, and the view must not invent one. The simulation itself always passes `want_timeline = false`, so timelines never enter events, history, saves or parity comparisons, and the camera cannot change a saved byte (Combat AC-5 guarantees the outcome is identical). *(Added by consistency-check 2026-11-16, World view OQ-1.)*

**Events, keys and offline**

**R13 — Events.** This system registers the Event bus type block **1100–1199** (`hunt_event_type_block`). Payload fields are integers: member IDs, content `uid`s, codes and counts (Event bus R2).

| Type | Name | a | b | c | d | Logged | Notes |
|---|---|---|---|---|---|---|---|
| 1101 | `hunt_trip_started` | party_id | ground uid | roster size n | trip_ordinal | no | Member state machine moves the roster to its hunting state on this |
| 1102 | `hunt_monster_killed` | party_id | monster uid | encounter_ordinal | ground uid | no | Quests (25) count kills from it. Roster from 1101 |
| 1103 | `hunt_member_downed` | member_id | monster uid | ground uid | 0 | no | Member state machine may apply injury rules (§6.4) |
| 1104 | `hunt_trip_ended` | party_id | ground uid | reason code (R14) | kills this trip | no | Emitted when the encounter chain ends, before Homebound |
| 1105 | `zone_first_entered` | zone uid | party_id | 0 | 0 | yes, milestone, `subject_slot = 0` (guild-wide), `ring_per_day = 0` | At most once per zone per save (15 records in a whole game) |

Events 1101–1104 are not logged, so this system adds nothing to the history ring budget (Event bus OQ-3: 0 ring records per day). Settlement results and level-ups are reported by the systems that own them (26, 27 and XP curve 2201/2202).

**R14 — Codes.** Return reasons (field `c` of 1104): 1 `low_hp`, 2 `bag_full`, 3 `defeated`, 4 `recalled`, 5 `ordered_home`. Codes 6–9 are reserved for the §6.4 needs triggers (6 hunger, 7 fatigue, 8 out of potions, 9 reserved). Each will be raised by the system that owns that need (Gold economy S3 consumables, Retention, Member state machine) through a request like R11, and will be checked first in R6 step 3. Codes are never reused. The reference's and Items R5's `wiped` and `lost` both map to 3, because a trip starts with every member alive and a wipe is reported by the fight as a loss (Combat `reason` `wiped` or `timeout`). Start refusals (R2): 11 not live, 12 guild level, 13 rebirth, 14 capacity, 15 member not eligible, 16 empty or oversized roster.

**R15 — The sampled resolver (for Offline progress).** Offline progress (31) does not replay every kill of a long absence (GDD §10). It asks this system for **rates** and applies them over time slices (`sim/offline.py`). This system owns the resolver, and Offline owns the driver: slice length, sample count, when to re-sample, event summaries and the parity tolerance.
- `sample_rates(group, ground, sample_count, sample_keys) → per-member totals` runs `sample_count` complete trips (R6 steps 1–11, rest included) on a **copy** of the group, then throws the copy away. The real members are not touched.
- **Randomness:** each sampled trip uses **one** generator derived in domain 5 `offline_sample` from a key Offline supplies (`sample_keys[i]`, RNG R4, owned by 31). All of that trip's spawn, fight and drop draws come from that one generator in sequence. Draw order is R6's order, and inside a fight it is Combat's order. Sampled trips therefore never share generators with live trips.
- **The copy** receives real `award` calls (so it can level up during the sample, as the reference's clone does). It does not emit events, does not call `hand_in` and does not credit through Gold economy. It totals what settlement would have paid.
- **Output**, as integers per member: `sample_ms` (the total length of the sampled trips, the same for every member), `base_xp_milli` (the sum of the source-side `kill_base_milli` that member received, **before** the XP curve's member-side multipliers), `kills` and `deaths`, plus `bags[i]`: each sampled trip's unscaled bag (item and material counts and its gold accumulator), which the copy never hands in. Offline applies the per-member totals as F10 and hands the bags in, whole and in rotation, through Items `hand_in` (Offline F4), so offline trips bring home materials and gear and the gold comes only from those hand-ins (OQ-7 resolved).
- **Difference from the reference:** `estimate_rates` measures XP after `growth_mult`, because it reads `xp_total`. This GDD reports source-side XP, so that Offline's `award` applies the PA and rebirth multipliers exactly once (XP curve R5). The totals agree once the multiplier is applied, so this changes where the multiplier is applied, not the result.
- The aggregate resolver is outside `phase_table_hash` and carries Offline's `resolver_version` (Sim core R6).

**R16 — Registration and saved state.** This system registers one P3 handler: `register(P3, order = 1100, owner_id = "hunt", handler)`. 1100 is this system's number × 100, following the block convention. Each tick, the handler processes in this order: the LOD snapshot when `N mod lod_eval_ticks = 0` (R17), start requests, then active trips in ascending `party_id`, and within a trip, every step whose due tick is ≤ N, in order. Its saved state, written through Local save's (6) serializer contract, is:
- for each party, `trip_ordinal` (stored on Party's record, 13); for the guild, the set of zones already entered (for 1105);
- for each active trip: `party_id`, `trip_ordinal`, ground `uid`, roster, step, the step's due tick, `encounter_ordinal`, kills, `slots_used`, the pending `FightResult` and its deadline tick (Combat R2: recomputing it on load from the saved key and inputs gives the same result), `xp_mult_ppm`, `trip_start_tick`, the latched `tier` and, for a card replay, the card position `e`. The bag is saved by Items (R5).
- for each `party_id`, its chain card (R17: ground, roster, levels, `uses`, per-encounter entries, end reason); for the guild, the last LOD snapshot `(L, F, D)` and its tick. Member HP and alive flags belong to the Member model.

If the core is `Paused`, no handler runs and trips do not move. If it is `Failed`, the tick's changes are discarded by the core (Sim core R10), and this system does nothing special.

**R17 — Simulation LOD: detailed and card tiers, chosen in-sim (user decision 2026-11-16).** GDD §3.5's "bãi khác = thống kê theo công thức" is a **simulation** LOD, chosen by a deterministic rule on simulation state. The camera never takes part (R12).
1. **Two tiers.** Every live trip runs at one of two tiers:
   - **`detailed`** — R6 as written: every encounter spawns with a domain-3 draw and is fought by Combat `resolve`.
   - **`card`** (the sampled tier) — a group's fights are taken from a saved **chain card** instead of calling Combat on most trips. A card is the per-encounter record of one detailed chain of that group: for each encounter `e`, `{monster uid, duration_ms, won, reason, each member's HP after, died mask}`, plus the chain's end reason. A card-tier trip with **no valid card** runs its chain exactly as `detailed` and records it as the group's new card (*card-building chain*, bit-identical to a detailed chain). A card-tier trip **with** a valid card *replays* it: at R6 step 4 the monster is `card[e].monster` (no domain-3 draw); at step 5 the `FightResult` is `card[e]` (no Combat call, no domain-1 draw) with the deadline `start_tick + ceil(duration_ms × tick_rate / 1000)`; step 3's return checks run normally on the card's HP and the live bag; step 7's XP is F1 on the members' **current** levels and drops are rolled for real by Items with the trip's own key `[0, party_id, trip_ordinal, e]`, so loot is never copied from the card. Events 1102/1103/1104 are emitted as in R6. If the card runs out before a return trigger holds, the chain ends with the card's end reason.
   - A card is **valid** for a group when its ground, its sorted roster and every member's level equal those recorded, and `card.uses < lod_card_trips − 1`. Each replay adds 1 to `uses`. Anything else (a new ground, a roster change, any level-up, uses spent) makes the next card-tier chain a card-building one. One card per `party_id`; it is saved state (R16).
2. **Which grounds are detailed (F11).** At every tick `N` with `N mod lod_eval_ticks = 0`, before start requests (R16), the handler takes a snapshot: the live ground set `L` (grounds with `occupancy(g) > 0`, R4), the forced set `F ⊆ L`, and `D = F ∪ top_N(L \ F)`, where `top_N` ranks by occupancy descending, ties by lowest ground `uid`, and keeps the first `lod_detail_grounds` grounds. The snapshot `(L, F, D)` is saved.
3. **Forced grounds.** `forced(g)` holds when (a) any trip at `g` has a queued recall (R11 code 4) — raid-relevant state — or (b) a registered in-sim predicate says so. Other systems may register a `lod_force(g, view) → bool` predicate at boot (pure, reading committed state only; evaluated in ascending owner block number): Golden Boss (14) for grounds whose members are being gathered for a raid, Onboarding (44) for the tutorial's ground, and a future live event for its event ground. The set may be empty (MVP). PROVISIONAL for each registrant.
4. **The tier is latched at trip start.** At R6 step 1 the trip records `tier = detailed` if `forced(g)` holds now, or `g ∈ D`, or `g ∉ L` and `|D \ F| < lod_detail_grounds` (a ground nobody occupied at the last snapshot takes a free detail slot); otherwise `tier = card`. The tier never changes during that trip: a ground switching tier mid-trip affects only trips that start after the switch, and an in-flight trip finishes at the tier it started with (a card replay in progress finishes its replay; a detailed chain stays detailed). Member entries and departures change occupancy only at trip start and close (R4, R10), so they move a ground's rank at the next snapshot, never mid-trip.
5. **What it depends on, and what it never depends on.** Inputs: occupancy, recall queues, registered predicates, tick, saved cards and the saved snapshot — all simulation state reached through the command log. Never: camera, zoom, focus, frame rate or device. A replay (Sim core R16, Leaderboards 35) therefore reproduces every tier, card and result. No evaluation runs inside an offline skip (no ticks run); the saved snapshot stands until the next evaluation tick after it. Offline's sampled resolver (R15) is unaffected: it always runs its own sampled trips.
6. **The view of a card-tier trip.** A replayed encounter has no fight to rebuild: `fight_timeline` returns `none` for it (R12). The world view (38) still draws the group at the ground and its real kills, deaths, loot pops and return (from 1102–1104), but shows the encounter as abstract activity, never invented hits or damage numbers (World view R17).

### States and Transitions

The trip state machine belongs to one active trip. Member-level states (`hunting`, `returning`, `resting`, `dead`) belong to Member state machine (41), which drives them from events 1101/1104 and the rest hand-off.

| State | Entered when | Lasts | Exits to | Exit condition |
|---|---|---|---|---|
| `Outbound` | Start accepted (R6.1) | `travel_ms` | `Checking` | Due tick reached |
| `Outbound` | — | — | `Homebound` | Recall or order home queued (R11). Homebound lasts the outbound time already spent |
| `Checking` | Outbound ended, or a gap ended | 0 ticks (same tick) | `Engaging` | No trigger holds: spawn and fight resolved at once (R6.4–5) |
| `Checking` | — | — | `Homebound` | Trigger 1, 2, 3 or code 5 holds. Emits 1104 |
| `Checking` | — | — | `Closed` (handed to raid) | Recall (code 4): settles at once (R11). Emits 1104 |
| `Engaging` | Fight resolved | until Combat's deadline tick (F8 there) | `Gap` | Win: XP, drops, 1102/1103 applied at the end tick |
| `Engaging` | — | — | `Homebound` | Loss: 1103 per death, 1104 code 3 |
| `Gap` | Win | `gap_ms` | `Checking` | Due tick reached |
| `Homebound` | Chain ended (not recall) | `travel_ms` | `Selling` | Due tick reached |
| `Selling` | Arrived home | `sell_ms` | `Resting` | Due tick reached: settlement (R8) |
| `Resting` | Settled | `rest_ms` (F7), run by Member state machine | `Closed` | Rest ends: all alive, full HP |
| `Closed` | — | — | (deleted) | Occupancy released |

Invalid transitions: no state returns to `Outbound`; `Engaging` is never interrupted; a closed trip cannot be reopened; settlement cannot happen twice (`Selling` → `Resting` only once, and recall settles only from `Checking`).

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Data layer (3) | in | `zones`, `grounds`, `monsters` rows, `uid`s, `content_live`; `sim_params`/`config` keys (Tuning Knobs) | — | Data layer owns loading and validation; this system owns the meaning of its columns |
| Deterministic RNG (2) | in | Generators from `derive(domain, key)` | — | RNG owns the generator; this system owns keys and draw order for domains 3 and 4 (F9) |
| Sim core (1) | both | Tick N, `ctx` (derive, emit, read content) | One P3 handler at order 1100 | Sim core |
| Event bus (42) | out | — | Types 1101–1105 (R13) | This system owns the block |
| Member model (8) | in | Level, rebirth, alive and HP, `profile(member)` (passed to Combat) | — | Member model owns the data |
| Member state machine (41) | both | "Available to hunt" (R3) | Events 1101, 1103, 1104; the rest hand-off `rest_ms` | MSM owns member states |
| Party (13) | in | The hunting group (roster) for a trip start; `xp_mult_ppm` for a roster; stable `party_id` and stored `trip_ordinal` | Trip-start refusals (R14) | Party owns formation and the bonus |
| Utility AI (12) | out | — | Ground facts, eligibility (R2), occupancy (R4) | Utility AI owns scoring |
| Combat (10) | both | `FightResult`: `won`, `reason`, `duration_s`, HP after, `died` | The encounter (group, monster row, `hp_scale = dmg_scale = 1.0`) and a domain-1 generator — not called for a card replay (R17) | Combat owns `resolve`, monster stats and the fight's draws |
| XP curve (22) | out | Overflow returned | `award(member, kill_base_milli, hunt_kill)` | XP curve owns `award` |
| Items and loot (26) | both | Roll added to the bag; `bag_full(bag)`; trip income from `hand_in` | `drop_table`, monster level, party luck, key `[0, party_id, trip_ordinal, encounter_ordinal]`; `hand_in(party, bag)` at settlement | Items owns rolls, storage and sale value |
| Gold economy (27) | out | `credit` result | One integer credit per member per mint type (`hunt_gold`, `loot_handover`) per trip | Gold economy owns `credit`; this system owns the amounts and the split (R8) |
| Guild and buildings (30) | in | Guild level | — | Guild owns the level |
| Command layer (5) | in | "Order home", "hunt at ground g" orders | Refusal codes | Command layer owns vocabulary and validation |
| Golden Boss raid (14) | in | Recall request; optional `lod_force` predicate (R17.3, PROVISIONAL) | The group, settled, at the encounter end | Golden Boss owns gathering |
| Onboarding (44), future live events | in | Optional `lod_force` predicate (R17.3, PROVISIONAL) | — | Registrants own their predicate |
| Offline progress (31) | both | `sample_keys`, slice plan | `sample_rates` totals (R15) | Offline owns the driver and tolerance |
| Realtime world view (38) | out | — | Trip state incl. latched `tier`, due ticks, events (read-only); `fight_timeline` (`none` for card replays) | World view owns drawing |
| Quests (25), Analytics (37), AI text (36) | out | — | Events 1101–1105 through the bus | Subscribers |
| Dev tooling (43) | out | — | `kill_xp_table_hash` (F3), parity vectors for domains 3, 4 and the trip; balance scenarios | Dev tooling runs them |
| Endless Tower (19) | out | — | Monster rows (Combat owns the stat formula) | Tower owns floors |

## Formulas

All formulas run in integers at play time. As in the XP curve, float `pow()` is used only once per table cell at boot (F1), and the resulting table is hashed (F3), so a last-bit difference between Python and GDScript is caught by the parity gate rather than in play. Float knobs (`flee_hp_pct`, `lvl_diff_penalty` …) are converted once at load to integer parts per million with `round(1,000,000 × value)`. The CSV columns themselves stay as they are (OQ-6).

*Systems-designer lens applied: each formula below was run at 0, its minimum and its maximum. Problems found are noted under each formula and in Edge Cases.*

### F1 — Kill XP per member

The kill_base_milli formula is defined as:

`kill_xp_milli[L] = floor(1000 × xp_kill_coef × L ^ xp_kill_exp)` (boot table, L = 1 … 200)

`kill_base_milli(member, monster) = floor( floor(kill_xp_milli[L] × xp_mult_ppm / 1,000,000) × diff_ppm(member, L) / (n × 1,000,000) )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L | int | 1 – 200 | data file (`monsters.level`) | Level of the monster killed |
| xp_kill_coef | float | 0.1 – 10 (1.5 today) | data file (`sim_params`) | Kill XP scale. The first knob to recalibrate after real skills (GDD §20) |
| xp_kill_exp | float | 1.0 – 2.0 (1.5 today) | data file (`sim_params`) | How fast kill XP grows with monster level |
| kill_xp_milli[L] | int | 1,500 – 4,242,640 today | calculated (boot) | Kill XP of a level-L monster, in milli-XP |
| xp_mult_ppm | int | 1,000,000 – 1,470,000 today | calculated (Party 13, fixed at trip start) | Party bonus: `1 + 0.08 (n−1) + 0.10 buffer + 0.05 tank` today |
| diff_ppm | int | 100,000 – 1,000,000 | calculated (F2) | Level-difference factor |
| n | int | 1 – 5 | calculated | Roster size at trip start, dead members included |
| kill_base_milli | int | 0 – ~4.2 × 10⁶ | calculated | Source-side XP passed to `award` for one member for one kill |

**Output Range:** the smallest non-zero value is 30 milli (a level-1 kill, `xp_mult_ppm = 1,000,000`, the 0.1 floor of F2, shared by 5). The largest today is 4,242,640 milli (a level-200 kill by a solo member, who gets no party bonus). A level-200 kill shared by 5 at the full bonus gives 1,247,336 milli each. Every value is far below `award_base_max_milli` (2⁴⁰). The intermediate product is at most about 4.2 × 10⁶ × 3 × 10⁶ ≈ 1.3 × 10¹³ for any sane `xp_mult_ppm`, safely inside int64. The two-step floor exists so that `kill_xp_milli × xp_mult_ppm × diff_ppm` (up to about 10¹⁹) is never formed, because that would overflow int64.
**Example:** a 5-member party with a buffer and a tank, all level 25, kills `m_z03_b` (level 23) on `g_z03_2`. `kill_xp_milli[23] = floor(1000 × 1.5 × 23^1.5) = 165,456`. `× 1,470,000 / 10⁶ → 243,220`. The level difference is 25 − 23 = 2 ≤ 5, so `diff_ppm = 1,000,000`, and `243,220 × 10⁶ / (5 × 10⁶) = 48,644` milli each. The XP curve then applies `growth_mult` (×1.0 at PA 100).
**Newbie window (Onboarding 44, F1/R13).** In live play Hunt passes `min(2⁴⁰, floor(kill_base_milli × onboarding.xp_mult_ppm() / 1,000,000))` to `award`, a source-side multiplier read at each kill (1,000,000 outside the window; not to be confused with Party's `xp_mult_ppm` above). The sampled resolver (R15) does not apply it, because the window counts played ticks only (Onboarding R13). *(Added by consistency-check 2026-11-16, Onboarding OQ-2.)*
**Boundary notes:** L = 0 is impossible (validator: `level ≥ 1`). n = 0 is impossible (R2: roster 1–5, refusal 16). `xp_kill_coef = 0` gives 0 XP for every kill, which the XP curve accepts (`base_milli ≥ 0`) but which makes the game unwinnable. The safe range in Tuning Knobs excludes it.
**Feedback loops:** a bigger party earns more XP per kill in total (the bonus), but each member gets a share divided by `n`. Kill speed grows with party size, so the loop is positive and intended: parties beat solo (GDD §6.12). It is damped because the share per member falls and capacity is limited (R4).

### F2 — Level-difference factor

The diff_ppm formula is defined as:

`diff = member.level − L`
`diff_ppm = 1,000,000` if `diff ≤ lvl_diff_free`, else `max(lvl_diff_min_ppm, 1,000,000 − lvl_diff_penalty_ppm × (diff − lvl_diff_free))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| member.level | int | 1 – 200 | calculated (Member model) | Level at the moment of the kill |
| L | int | 1 – 200 | data file | Monster level |
| lvl_diff_free | int | 0 – 20 (5 today) | data file (`sim_params`) | Levels above the monster with no penalty |
| lvl_diff_penalty_ppm | int | 0 – 1,000,000 (100,000 today) | data file (`sim_params.lvl_diff_penalty` × 10⁶) | Share of XP lost per level beyond the free band |
| lvl_diff_min_ppm | int | 0 – 1,000,000 (100,000 today) | data file (`sim_params.lvl_diff_min` × 10⁶) | Floor of the factor |

**Output Range:** 100,000 – 1,000,000 today. There is **no bonus** for killing monsters above your level (diff < 0 gives 1,000,000). The reward for hunting up is faster XP per kill from the higher `L` (F1), not a multiplier.
**Example:** a level-33 member kills a level-23 monster: diff = 10, so `1,000,000 − 100,000 × 5 = 500,000` (half XP). At level 39, diff = 16 and `1,000,000 − 1,100,000 < 100,000`, so the factor is the floor, 100,000.
**Boundary notes:** with `lvl_diff_min_ppm = 0`, an over-levelled member earns 0 XP. That is legal but makes over-levelled members dead weight in a party; the floor exists to avoid it. `lvl_diff_penalty_ppm = 0` disables the penalty entirely, so top members could farm zone 1 safely forever, which is a degenerate strategy the floor-and-penalty pair prevents. The factor is computed per member, so a mixed-level party pays each member differently for the same kill.

### F3 — `kill_xp_table_hash`

Monster max HP, hit and defence are **Combat's** formula (Combat F1, R5: `mon_hp = monster_hp_coef × L ^ monster_hp_exp × hp_mult × hp_scale`, and so on). This system owns the monster *rows* (R1) and passes `hp_scale = dmg_scale = 1.0` for a hunt fight. It does not restate or duplicate the stat formula. It owns only the hash of its own boot table.

The kill_xp_table_hash formula is defined as:

`kill_xp_table_hash = SHA-256( concat over L = 1 … 200 of i64_be(kill_xp_milli[L]) )`, hex-encoded lowercase.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| kill_xp_milli[L] | int | 1,500 – 4,242,640 today | calculated (F1, boot) | The kill-XP table |
| i64_be | — | — | constant | Signed 64-bit integer, big-endian bytes |

**Output Range:** 64 lowercase hex characters over a fixed 1,600-byte input. It is recorded in the parity vectors (Dev tooling 43) and logged at boot. A Python and GDScript build that disagree on one cell, because of a last-bit `pow()` difference, fail the parity gate.
**Example:** changing `xp_kill_exp` from 1.5 to 1.51 changes every cell above L = 1 and therefore the hash.
**Boundary notes:** the table covers L = 1 … 200. A monster row with `level` outside that range must be rejected by the validator (OQ-6).

### F4 — Bag capacity (pointer)

Bag capacity is Items and loot's formula (Items R5, `bag_slots × n`, with `n` the roster size at trip start). It is 30 slots solo and 150 for five today. This system only asks `bag_full(bag)` before each encounter (R6 step 3). Measured on the reference: a full level-25 party on `g_z03_2` fills its 150 slots after about 106 kills (about 1.4 slots per kill), and the trip ends `bag_full`.

### F5 — Trip duration

The trip_ms formula is defined as:

`trip_ms = 2 × travel_ms + Σ_encounters fight_ms(i) + gap_ms × wins + sell_ms + rest_ms`, with `fight_ms(i) = tick_ms × ceil(duration_s(i) × tick_rate)` (Combat F8)

where `travel_ms = 1000 × travel_s`, `sell_ms = 1000 × sell_s`, `wins` is the number of encounters won, and each duration is rounded **up** to whole ticks when it is scheduled (`ceil(x / tick_ms) × tick_ms`).

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| travel_s | int | 0 – 600 (30 today) | data file (`sim_params`) | One-way travel time, the same for every ground today |
| fight_ms(i) | int | 0 – ~601,000 | calculated (Combat F8) | Duration of encounter i, rounded up to ticks |
| gap_ms | int | F6 | calculated | Wait after a winning encounter |
| sell_s | int | 0 – 600 (10 today) | data file (`sim_params`) | Time to sell at home |
| rest_ms | int | F7 | calculated | Time to recover after the trip |
| tick_ms | int | 100 today | constant (Sim core R1) | Length of one tick |

**Output Range:** a trip that ends before its first encounter (an order home during outbound) is at least `2 × travel_ms`. A full 5-member trip at its level lasts about 15 minutes (measured 901 s on average over 20 trips, ending `bag_full`). A solo trip lasts about 4–5 minutes and ends `low_hp` after about 4 kills (measured 262 s, `kim_2` level 25 on `g_z03_2`).
**Example:** 106 wins averaging 6 s, gap 2 s: `60 + 636 + 212 + 10 + rest(about 0 – 60) ≈ 918 – 978 s`.
**Boundary notes:** rounding up to ticks adds up to 99 ms per step compared with the reference. Over about 215 steps per trip that is at most +2.1%, and +1% on average. This is a known source of drift from the reference, and the balance gate must absorb it (OQ-3). `travel_s = 0` is legal (instant travel), which removes the main early-game pacing limiter (GDD §4.3: "bị chặn bởi thời gian đi lại").

### F6 — Encounter gap

The gap_ms formula is defined as:

`gap_ms = round(1000 × gap_s × 1,000,000 / spawn_rate_ppm)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| gap_s | float | 0 – 30 (2 today) | data file (`sim_params`) | Base wait between kills |
| spawn_rate_ppm | int | 100,000 – 10,000,000 (1,000,000 today, every ground) | data file (`grounds.spawn_rate` × 10⁶) | Ground respawn speed: 2.0 halves the gap |

**Output Range:** 2,000 ms on every ground today, which is identical to the reference. With `spawn_rate = 0.1` it is 20 s.
**Example:** a ground with `spawn_rate = 1.25` has `round(2000 / 1.25) = 1,600` ms.
**Boundary notes:** `spawn_rate = 0` divides by zero; the validator must require `spawn_rate > 0`. The reference ignores `spawn_rate`. Because every row is 1.0, adopting F6 changes no measured number today (decision logged).

### F7 — Rest time

The rest_ms formula is defined as:

`rest_ms(m) = revive_ms` if m is dead, else `ceil( (hp_max − hp) × 10⁹ / (regen_ppm_per_s × hp_max) )`
`rest_ms(trip) = max over the roster of rest_ms(m)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| revive_s | int | 0 – 3,600 (180 today) | data file (`sim_params`) | Time for a dead member to revive at the shrine (Linh Miếu) |
| regen_ppm_per_s | int | 1,000 – 1,000,000 (10,000 today = 1%/s) | data file (`sim_params.regen_pct_per_s` × 10⁶) | HP regained per second at home, as a share of max HP |
| hp, hp_max | Combat's HP type | 0 – hp_max | calculated (Member model / Combat) | HP at the end of the trip |

**Output Range:** 0 (everyone at full HP) to `max(revive_ms, 100 s)` today: 100 s is a member at 0 HP who is still alive, which Combat cannot produce, so the realistic range is 0 – 75 s for the living (the flee threshold is 25%), or 180 s with a death.
**Example:** the weakest living member is at 40% HP: `0.6 × 10⁹ / 10,000 = 60,000` ms (60 s). If any member died, the trip's rest is 180 s.
**Boundary notes:** `regen_ppm_per_s = 0` divides by zero and must be refused at load. A death always costs the whole group `revive_s`, so in a party one fragile member slows everyone. That is the intended pressure toward healers and tanks (GDD §6.12).

### F8 — Resolver cost per tick (scaling statement for Sim core R17)

The p3_steps formula is defined as:

`p3_steps(N) = starts(N) + Σ_trips [ number of steps of that trip with due tick = N ]`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| starts(N) | int | 0 – guild roster size | calculated | Start requests processed this tick |
| G | int | 0 – max roster (every member solo) | calculated | Active trips |
| steps per trip per tick | int | 0 – 3 | calculated | A gap end, a check and a fight can fall on one tick |

**Output Range:** with G active trips and an average step length of about 4 s (40 ticks), the expected work is about `G × 2 / 40` fights per tick (one check and one fight per encounter). With 8 full parties that is about 0.4 fights per tick, and at most `G` fights in one tick (every group ending a gap together). The cost of one fight is Combat's (event-driven, F-cost owned by 10).
**Example:** 40 solo hunters at worst all resolve a fight on one tick. The P1 spike measures that worst tick against P3's 35% share of the tick budget (Sim core), OQ-2. Card replays (R17) cost a lookup instead of a fight, so only detailed and card-building chains count as fights here (F12).

### F11 — Detailed ground set (simulation LOD, R17)

The lod_detail_set formula is defined as:

`D = F ∪ first_K( sort(L \ F, by (−occupancy(g), uid(g))) )`, `K = lod_detail_grounds`, evaluated at ticks with `N mod lod_eval_ticks = 0`

`tier(trip at g, start tick T) = detailed` if `forced(g, T) ∨ g ∈ D ∨ (g ∉ L ∧ |D \ F| < K)`, else `card`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L | set of ground uid | 0 – 45 grounds | calculated (R4 occupancy at the snapshot) | Live grounds: occupancy > 0 |
| F | set | ⊆ L | calculated (R17.3) | Forced-detailed grounds |
| occupancy(g) | int | 0 – capacity | calculated (R4) | Members in trips at g |
| K = lod_detail_grounds | int | 1 – 45 (4) | data file (`sim_params`, new) | Detail slots besides forced grounds |
| lod_eval_ticks | int | 1 – 36,000 (600 = 60 s) | data file (`sim_params`, new) | Snapshot cadence |

**Output Range:** `|F| ≤ |D| ≤ |F| + K`; `D = L` whenever `|L \ F| ≤ K`. With one live ground (MVP), every trip is detailed.
**Example:** snapshot occupancies A (uid 201) 10, B (202) 8, C (203) 8, D (204) 5, E (205) 5, G (206) 2; E has a recall queued; K = 4. `F = {E}`; `L \ F` sorted: A 10, B 8, C 8, D 5, G 2 (B before C on uid) → `D = {E, A, B, C, D}`; G is card tier. Without the recall, `D = {A, B, C, D}`: D beats E on the tie by lower uid.
**Boundaries:** K ≥ 1 (validator) so a single-ground guild is never card tier. `lod_eval_ticks` = 1 re-ranks every tick (allowed; only trip starts read it). Empty L → empty D, and the next newly occupied ground takes a free slot (`|D \ F| = 0 < K`).

### F12 — Fights per hour under LOD (scaling statement)

The lod_fights_per_h formula is defined as:

`fights_per_h ≈ Σ_{detailed trips} f(t) + Σ_{card trips} f(t) × b(t)`, with `b = 1 / lod_card_trips` when the card stays valid, up to 1 when it is invalidated every chain

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| f(t) | int | 0 – ~60 | calculated (R6) | Encounters in trip t's chain |
| b(t) | ratio | 1/`lod_card_trips` – 1 | calculated (R17.1) | Share of card-tier chains that build a card |
| lod_card_trips | int | 1 – 16 (4) | data file (`sim_params`, new) | Chains per card: 1 build + (n − 1) replays; 1 disables the card tier |

**Output Range:** between `Σ f / lod_card_trips` and `Σ f`; never more fights than all-detailed.
**Example:** 40 groups on 12 grounds, 20 encounters per chain, 4 grounds detailed holding 16 groups: all-detailed = 40 × 20 = 800 fights per round of trips; with LOD = 16 × 20 + 24 × 20 / 4 = 440 (−45%), more while low-level groups level up and rebuild cards.

### F9 — RNG event keys

The hunt_event_key formula is defined as:

`key_encounter = [party_id, trip_ordinal, encounter_ordinal]`, used for domain 3 `spawn` (this system) and domain 1 `combat` (Combat, the same layout Combat states). Domain 2 `loot` uses it with the source tag 0 in front, `[0, party_id, trip_ordinal, encounter_ordinal]` (Items R3).
`key_trip = [party_id, trip_ordinal]`, reserved for domain 4 `hunt_trip`. **No draws are made in domain 4 in this version.** The domain is reserved for later per-trip choices (for example, a §6.4 needs roll).

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| party_id | u64 | ≥ 1 | calculated (Party 13, saved, never reused) | The hunting group (R5) |
| trip_ordinal | u64 | 0 – 2⁶³ | calculated (saved, per party) | Trips this party started before this one |
| encounter_ordinal | u64 | 0 – ~10⁴ | calculated (saved, per trip) | Index of the encounter in this trip |

**Output Range:** unique for every encounter in a save (R5). Domains keep spawn, combat and loot draws independent even though they share a key (RNG R4).
**Draw order (RNG R7):** domain 3, one `choice(pool)` per encounter, in ascending `uid` order of the non-boss pool, and nothing else. Adding a draw to domain 3 is a breaking change to the parity vectors.
**Example:** party 7's 12th trip (ordinal 11), 4th encounter: `[7, 11, 3]` in domains 1 and 3, `[0, 7, 11, 3]` in domain 2.

### F10 — Applying sampled rates (Offline, 31)

The offline_apply formula is defined as:

`amount(member, slice_ms) = floor(total(member) × slice_ms / sample_ms)` for each of `base_xp_milli`, `kills`, `deaths`. Deaths keep a carried remainder, as the reference does (`carry_d`). Gold is not scaled here: it arrives through the rotated bag hand-ins (Offline F4; consistency-check 2026-11-16 — the reference `fast_forward` scaled gold instead).

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| total(member) | int | ≥ 0 | calculated (R15) | Sum over the sampled trips |
| sample_ms | int | > 0 | calculated (R15) | Total length of the sampled trips |
| slice_ms | int | > 0 (7,200,000 today) | data file (Offline 31) | Length of the time slice being filled |

**Output Range:** proportional to the slice. `sample_ms` is never 0, because every trip lasts at least `2 × travel_ms + sell_ms > 0` with the default knobs. With `travel_s = sell_s = 0` and an immediate return it could be 0, so R15 must reject `sample_ms = 0` (Edge Cases).
**Example:** 4 sampled trips total 3,600,000 ms and give a member 12,000,000 base milli-XP. A 2-hour slice applies `12,000,000 × 7,200,000 / 3,600,000 = 24,000,000` milli, passed to `award` once.
**Ownership:** the product `total × slice_ms` can reach about 10⁷ × 10¹⁰ = 10¹⁷ and stays inside int64. Offline owns `slice_ms`, the sample count and the tolerance. This system owns what a total means. The reference's default (2-hour slices, 4 samples) measures about 1% XP drift against the exact run (GDD §18.1).

## Edge Cases

*Systems-designer lens applied to R1–R17 and F1–F12. All cases found are included.*

**Content and access**
- **If a ground's pool has no non-boss monster**: the content is invalid. The validator must reject it (each ground needs ≥ 1 row with `is_boss = false`), and a start at such a ground at run time is a fatal error (RNG R9, `choice` on an empty list), never a silent skip.
- **If a ground is retired or not live in this build, but a loaded save has a trip there**: the trip runs to its end, because retired rows still resolve (Data layer R5). No new trip may start there (refusal 11).
- **If the guild level drops below `guild_lv_req`, or a member is moved to a lower rebirth** (neither exists today): trips already running finish. Only starts are checked.
- **If a group's members are at very different levels** (level 10 and level 40 in one party): the trip is legal. Each member's kill XP uses their own level (F2), so the high member earns little on a low ground. The party's power is decided by Combat. Party (13) owns the level-spread rule (GDD §6.12, ±10).
- **If capacity is exactly full**: a group that would exceed it is refused (14), even by one member. Two groups competing for the last places in one tick are decided by ascending `party_id` (R4).

**During a trip**
- **If the last encounter overfills the bag** (148 slots used, the kill drops 4 items): all 152 units are kept and the trip ends `bag_full` at the next check. Loot is never thrown away.
- **If a member dies but the group wins the fight**: the dead member gets no XP for that kill or any later one, and their share is not redistributed (F1 uses the full `n`). They still receive their equal share of the trip income (R8), and Items' `suited_first` can still hand them equipment (Items R6). Both behaviours are retrofitted from the reference.
- **If the party's buffer or tank dies mid-trip**: `xp_mult_ppm` stays as it was at the trip start. Combat stops applying their in-fight effects because they are dead.
- **If every member is dead after a fight**: Combat reports a loss, and the trip ends `defeated` (3), goes home, settles and rests with `revive_ms`.
- **If HP is exactly at the flee threshold** (`hp = 0.25 × hp_max`): the trigger is `hp < threshold`, strictly less, so the group stays. The comparison is done in Combat's HP type against `flee_hp_ppm`, and the parity vectors cover the boundary.
- **If two triggers hold at the same check** (low HP and bag full): the first in R6 step 3's order wins, and only that code is reported.
- **If a recall and an order home are both queued**: recall (4) wins, because it is checked first. The order is dropped.
- **If a recall arrives during `Homebound`, `Selling` or `Resting`**: the trip is already over. Golden Boss (14) decides whether a member who is still resting can join (R3: not eligible until the trip closes). PROVISIONAL.
- **If a member is asked to leave the guild during a trip** (Retention, 16): the roster is fixed for the trip. The departure takes effect when the trip closes. PROVISIONAL, Retention.
- **If the player tries to make a member join another group mid-trip**: refused. A member is in at most one trip (R3).
- **If a fight reaches Combat's time limit** (two tanks and no damage): it is a loss (3). The group goes home. The time spent counts.

**Timing and determinism**
- **If several steps of one trip fall due on the same tick** (a 0-ms gap): they run in order in that tick (R16). There is never an infinite loop: a fight with any action has `duration_s > 0` and so ends at least 1 tick later (Combat F8). Combat returns `duration_s = 0` only for an empty encounter, which this system never builds (R6 step 5 uses living members only, and R6 step 3 has already ended the trip if none are left).
- **If the camera moves between grounds**: no outcome changes and no tier changes (R12, R17). This is tested by AC-14.

**Simulation LOD (R17)**
- **If a ground switches tier mid-trip** (another ground overtakes it at a snapshot): trips already running keep their latched tier to the end, including a card replay in progress; only trips that start afterwards use the new tier.
- **If a member joins or leaves a group**: the roster is fixed for the trip (R5); the next trip has a new roster, so the card is invalid and that chain rebuilds it. Occupancy changes move ranks at the next snapshot only.
- **If a member levels up during a card replay**: the replay continues (outcomes from the card, XP by F1 at the new level); the next chain rebuilds the card.
- **If gear changes between trips** (purchases, R10): the card is not invalidated; a card can be up to `lod_card_trips − 1` trips stale. Bounded by the knob; the balance gate (AC-36) measures the drift.
- **If the live bag fills earlier or later than the card's** (fresh drops differ): the return check uses the live bag, so the chain ends on `bag_full` at its own time; if the card runs out first, the card's end reason is used.
- **If a recall is queued during a card replay**: R11 applies at the next return check as in detailed play; the ground is also forced detailed for trips starting afterwards (R17.3).
- **If two grounds tie on occupancy at the last detail slot**: the lower `uid` wins (F11).
- **If no snapshot has run yet** (new save, or a load before the first evaluation tick): `L` and `D` are empty, so each newly occupied ground takes a free slot until `K` are taken.
- **If an offline hand-off pauses a card replay** (Offline R5): it resumes at its card position after the skip; the card and snapshot are saved state.
- **If the player reloads a save and changes the party before a trip**: with the same `party_id` and ordinal, the dice are the same, applied to the new inputs (RNG R5). Reloading and waiting gives the same dice, because time is not in the key. If Party (13) gives a re-formed group a new `party_id`, the dice change (OQ-5).
- **If a trip is in progress when an offline hand-off happens**: Offline progress (31) owns the policy (Offline R5 pauses the trip, whatever its tier). The recommended one was to finish the in-progress trip with the detailed resolver, then fill the remaining time with sampled rates (OQ-7). Live keys continue without overlap, because sampled trips use domain 5.

**Offline sampling**
- **If `sample_ms = 0`** (all time knobs 0 and an immediate return): `sample_rates` reports a fatal error, never a division by zero.
- **If a sampled copy levels up mid-sample**: its later sampled kills use the new level (F2), as the reference's clone does. Offline re-samples each slice, so the bias shrinks with shorter slices.
- **If a sampled trip ends `defeated`**: it is included in the totals (deaths, lost time). The rates therefore price in risk honestly.

**Degenerate strategies checked**
- *Farming far below level:* XP falls to 10% (F2), and the drops are low-level. Gold is not penalised by level difference in this system (drops are Items', 26), so farming low grounds for safe gold remains possible. It is bounded by the low `base_gold(L)` of low monsters. Flagged for the Items and Gold economy owners (OQ-8).
- *Solo low-HP cycling:* a fragile solo hunter returns after a few kills (`low_hp`), and the rest is at most about 75 s, so cycling is slow but never stuck.
- *Recall abuse:* recall settles immediately and skips travel (R11). Only the Golden Boss can recall, so the player cannot trigger it at will. Summoning tokens (Triệu Tập Lệnh, §6.5) belong to 14, which must decide whether they recall (OQ-9).

## Dependencies

| System | Direction | Hard / soft | Interface | Status |
|---|---|---|---|---|
| Deterministic RNG (2) | upstream | Hard | `derive(domain, key)`; domains 3, 4 owned here; keys supplied for 1, 2 | GDD exists (Needs Revision) |
| Data layer (3) | upstream | Hard | `zones`, `grounds`, `monsters` schemas, `uid`, `content_live`, validator checks (OQ-6) | GDD exists |
| Sim core (1) | upstream | Hard | P3 registration at order 1100; ctx | GDD exists (Needs Revision) |
| Event bus (42) | downstream of this | Hard | Block 1100–1199 | GDD exists |
| XP curve (22) | upstream | Hard | `award(member, base_milli, source)` | GDD exists. It already lists Hunt (11) as owning kill XP and the level-difference penalty |
| Member model (8) | upstream | Hard | Level, rebirth, HP, `profile(member)` | GDD exists (conformed) |
| Combat (10) | upstream | Hard | `resolve(encounter, gen) → FightResult`; Combat F1 (monster stats), F8 (deadline tick); domain-1 key layout | GDD exists (conformed). Combat lists 11 as a hard dependent |
| Items and loot (26) | upstream | Hard | Kill roll into the bag (R3, R5), `bag_full`, `hand_in` (R6) | GDD exists (conformed, except the income split, OQ-11). Items lists 11 as a hard dependent |
| Party (13) | upstream | Hard | Roster hand-off, `party_id`, `trip_ordinal` storage, `xp_mult_ppm` | **No GDD** (PROVISIONAL) |
| Gold economy (27) | downstream | Hard | `credit` with mint types `hunt_gold`, `loot_handover` | GDD exists (conformed). Gold lists 11 as a hard caller |
| Member state machine (41) | both | Hard | Availability; events 1101/1103/1104; rest hand-off | **No GDD** (PROVISIONAL) |
| Guild and buildings (30) | upstream | Soft | Guild level for `guild_lv_req` | GDD exists. The guild-level read is assumed (it does not yet name Zones (11) as a reader) |
| Command layer (5) | upstream | Soft | Order home, ground orders | GDD in progress (skeleton) |
| Utility AI (12) | downstream | Hard (for 12) | Ground facts, eligibility, occupancy | No GDD |
| Offline progress (31) | downstream | Hard (for 31) | `sample_rates` (R15), F10 | No GDD |
| Golden Boss raid (14) | downstream | Soft | Recall (R11) | No GDD |
| Realtime world view (38) | downstream | Hard (for 38) | Read-only trip state and events | No GDD |
| Quests (25), Analytics (37), AI text (36), Onboarding (44) | downstream | Soft | Events 1101–1105 | No GDD |
| Endless Tower (19) | downstream | Soft | Monster rows | No GDD |
| Dev tooling (43) | downstream | Hard (build time) | `kill_xp_table_hash`, parity vectors for domain 3 and whole trips, the aggregate-vs-exact parity test, balance scenarios | GDD exists |

**Bidirectional check.** The systems index lists 11 as depending on RNG, Member model, Combat, Items and loot and Data layer. This GDD adds the Sim core, Event bus, XP curve, Party, Gold economy, Member state machine and Guild and buildings as interfaces. Combat, Items and loot and Gold economy already list this system. Of the rest, Party and Member state machine are *later* in the design order. They are interface dependencies only (this system defines the call and they implement it), so they do not need to be designed first. The XP curve (22) and Sim core (1) GDDs already list Hunt (11) downstream. The RNG GDD lists 11 as owner of domains 3 and 4. The Data layer lists 11 as a hard dependent.

## Tuning Knobs

*Derived from the Formulas variable tables (systems-designer lens). Every `data file` variable is a knob. Knobs owned by another GDD are pointed to, not duplicated.*

| Knob | File | Today | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `xp_kill_coef` | `sim_params` | 1.5 | 0.5 – 5 | Levels fly by and the 71-hour target to level 100 collapses | Grind; early levels stall | The XP curve's `need_milli` (the pace is their ratio, XP curve Tuning Knobs). Recalibrate this one first after real skills |
| `xp_kill_exp` | `sim_params` | 1.5 | 1.2 – 1.8 | High zones pay disproportionately, and low zones become pointless sooner | Late game crawls | `xp_need_exp` (1.7). Keep `xp_kill_exp` below it so the need outgrows the reward |
| `lvl_diff_free` | `sim_params` | 5 | 2 – 10 | Over-levelled farming is safe and full pay | Parties with a level spread are punished | Ground level bands (4–8 wide) |
| `lvl_diff_penalty` | `sim_params` | 0.1 | 0.05 – 0.25 | XP drops off a cliff a few levels past the band | Farming far below level stays profitable | `lvl_diff_min`: at 0.1 the floor is reached at 9 levels past the band |
| `lvl_diff_min` | `sim_params` | 0.1 | 0.05 – 0.5 | A floor of 0.5 makes over-levelling nearly free | 0 makes over-levelled members dead weight | `lvl_diff_penalty` |
| `flee_hp_pct` | `sim_params` | 0.25 | 0.1 – 0.5 | Trips end constantly; solo play is unworkable | More deaths (each costs the whole group `revive_s`) | Combat's damage (`monster_dmg_factor`, owned by 10) |
| `bag_slots` (Items' F6 uses it; listed here because it sets trip length) | `sim_params` | 30 | 10 – 100 | Fewer trips and fewer homecomings; the loop feels slower even though rates barely change | Trips become a stream of short, travel-dominated runs | `travel_s` (travel overhead per kill = `2 × travel_s / kills_per_trip`) |
| `travel_s` | `sim_params` | 30 | 10 – 120 | Early levels slow down (GDD §4.3 says early pace is limited by travel) | The homecoming beat loses its weight | `bag_slots` |
| `sell_s` | `sim_params` | 10 | 0 – 60 | Dead time | — | — |
| `gap_s` | `sim_params` | 2 | 0.5 – 10 | Kill rate falls for every group | Fights run back to back; the view looks frantic | `spawn_rate` per ground |
| `revive_s` | `sim_params` | 180 | 30 – 900 | Deaths dominate the pace of fragile schools (`thuy_1`) | Death has no cost | `flee_hp_pct` |
| `regen_pct_per_s` | `sim_params` | 0.01 | 0.002 – 0.05 | Rest is negligible | Rest dominates trip time | `flee_hp_pct` (sets the deepest living rest) |
| `monster_hp_coef`, `_exp` (Combat F1 owns the formula) | `config` | 40, 1.3 | Set by `calibrate.py` against the Dev tooling targets (6–25 s per kill) | Fights too long; trips end on low HP | Kills trivial | Combat's member damage; `xp_kill_*` |
| `monster_atk_*`, `monster_def_*` | `config` | 6, 1.25; 3, 1.2 | Calibrated as above | Deaths rise past the 3% target | No danger | `monster_dmg_factor` (Combat) |
| `lod_detail_grounds` (new) | `sim_params` | 4 | 1 – 12 | More fights per tick; the LOD saving vanishes (F12) | Most grounds run card tier; outcomes drift more from detailed | `lod_card_trips`, roster size, F8 |
| `lod_eval_ticks` (new) | `sim_params` | 600 (60 s) | 100 – 6,000 | Ranks lag behind where the guild hunts | Snapshot work every tick (cheap, but pointless churn) | trip length (only trip starts read the tier) |
| `lod_card_trips` (new) | `sim_params` | 4 | 1 – 8 | Cards go stale (gear, HP drift); card-tier income drifts from detailed | 1 = LOD off (every chain detailed) | `lod_detail_grounds`, balance gate |
| Per row: `grounds.capacity` | `grounds` | 6 / 8 / 10 | 1 – 30 | Crowding never binds | Guilds cannot fit their parties in their level band | Roster size (Guild 30), the number of grounds per band |
| Per row: `grounds.spawn_rate` | `grounds` | 1.0 | 0.25 – 4 | That ground pays much more per hour | That ground is dead | `gap_s` |
| Per row: `monsters.*_mult`, `speed`, `level` | `monsters` | Generated (`gen_a.py`) | Validator ranges | — | — | Combat F1 |
| Per row: `zones.guild_lv_req`, `rebirth_req` | `zones` | 1 – 8, 0 – 5 | Must increase with `order` | Zones gated behind guild growth too long | Gates meaningless | Guild and buildings' level curve; Rebirth (23) |

**Owned elsewhere and read here:** `party_xp_per_member`, `party_buffer_bonus`, `party_tank_bonus` (Party 13); `mat_sell_ratio`, `equip_sell_ratio`, `base_gold_*` (Items and loot 26 / Gold economy 27); `monster_dmg_factor`, `def_k_*`, `tank_aggro_share`, `healer_heal_frac`, `buffer_*` (Combat 10); `chunk_s`, sample count (Offline 31); `tick_rate` (Sim core 1, not a shipped knob).

**Rule for every change:** run the balance gate (Dev tooling 43) before committing, regenerate the parity vector for `kill_xp_table_hash` when an F1 input changes, and re-check the XP pace (XP curve AC-35).

## Visual/Audio Requirements

*Art-director lens. There is no art bible yet (`design/art/` does not exist), so this is drafted from GDD §3.5 (30 FPS mid-range target, object pooling, sprite atlas, modular paper-doll sprites with element palette swaps) and §12.4 (AI-assisted pixel art pipeline). Revisit after `/art-bible`.*

**Per-event feedback:**
| Event | Visual | Audio |
|---|---|---|
| Trip start (1101) | Members leave the guild gate in a line toward the ground and a small "→ [ground]" tag appears over the party leader | Soft departure cue (footsteps or a horse); suppressed when several groups leave within 1 s |
| Arrival at the ground | Group appears at the ground edge | None |
| Fight (Engaging) | The world view animates the fight from its start tick to Combat's deadline tick: attacks at Combat's cadence, damage numbers (pooled, capped per §6.13 guidance), element-coloured hit sparks (counter hits distinct) | Hit sounds from the member's weapon family; only for the ground on screen |
| Kill (1102) | Monster death puff; drop icons pop and fly to the nearest member's bag | Short "coin/loot" tick, rate-limited |
| Member downed (1103) | The member falls and turns into a spirit marker that follows the group home | Low, short cue. Must be audible over loot ticks (mix priority above loot) |
| Trip ended (1104) | An icon over the party leader shows the reason (bag, heart, broken sword, horn, flag) | A distinct cue for `defeated` |
| Homecoming / settlement | Bag icons empty into the guild, a gold counter rises, and level-ups (2201) show as they happen | The "homecoming" chime, the system's signature sound (Player Fantasy) |
| First entry to a zone (1105) | A banner with the zone's name across the map | A short fanfare |

**Constraints:**
- Monster sprites follow the zone `theme` key (`field_farmland`, `bronze_mines` …) and reuse the paper-doll and palette-swap method: one base body per role (`swarm`, `melee`, `ranged`, `tank`, `boss`) per theme, with element palettes. That gives 5 roles × 15 themes, not 75 unique monsters.
- Off-screen grounds draw nothing or one marker per group (R12). The view must not need anything from the simulation that a drawn ground does not.
- Reason icons and danger levels are never shown by colour alone (UI Requirements).

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:zones-grounds-monsters-and-hunt-trips` to produce per-asset visual descriptions, dimensions and generation prompts from this section.

## Game Feel

This is an idle game. The player watches rather than acts, so feel is about **readability and rhythm**, not input response.

- **Rhythm targets.** Kills every 6–25 s while engaging (Dev tooling calibration target). A 2 s breath between kills. A homecoming every 10–20 minutes for a full party at its level, and every 3–6 minutes for a solo hunter. The homecoming must stay frequent enough that a player who opens the game for two minutes usually sees one somewhere on the map.
- **Anticipation.** Bag fullness and the weakest member's HP are visible on the group (UI Requirements), so the player can see a return coming.
- **Weight of a return.** The settlement beat lasts the whole `sell_s` (10 s). Gold counts up, items fly into storage, and level-ups appear. It is never instant.
- **Failure reads as information.** A `defeated` return shows which monster won (the 1103 monster uid), so the player can act (bring a healer, gear up, pick an easier ground).
- **No dead air.** A group never stands still on a ground with nothing happening for more than `gap_s` (plus travel).
- **Feel is verified by playtest, not automation** (Acceptance Criteria marks these as playtest items).

## UI Requirements

- **World map / zone panel:** for each zone, its locked or unlocked state and the reason it is locked (guild level N, rebirth N), its level range, its primary and secondary element (icon + text), and the number of guild members hunting there.
- **Ground panel:** level range, danger (1–3, shown as both icons and a number), occupancy against capacity (for example "6 / 8"), the monster list (portrait, level, element icon, role), and which of the guild's elements counter the ground.
- **Member and party card:** current trip step (outbound, hunting at X, heading home, selling, resting) with a countdown to its next due tick; bag fill (slots used / capacity); the weakest member's HP against the flee line.
- **Trip report** (tap on a returning group, and as rows in the offline report owned by 31): kills, time, reason code (icon + text), XP per member, gold, and items.
- **Orders:** "Order home" on a hunting group (code 5), and "Hunt here" on a ground, which sends a request through the Command layer and shows the refusal reason (R14 codes 11–16) as text when refused.
- **Accessibility floor:** no information by colour alone (elements, danger and reasons all have an icon and a text label). Every string comes from `i18n/` keys (vi/en). Leave room for Vietnamese text being longer than English.

> **📌 UX Flag — Zones, grounds, monsters and hunt trips**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the world map, the ground panel, the party trip card and the trip report **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not this GDD directly.

## Cross-References

| This document references | Target GDD | Section / rule | Nature |
|---|---|---|---|
| Domains 3 `spawn`, 4 `hunt_trip` owned; keys for 1, 2, 5 | `deterministic-rng.md` | R4, R5, R6, R7, R9, Edge Cases (save-scumming) | Ownership and rule dependency |
| `uid`, liveness, typed tables, `ppm` conversion, validator | `data-layer-and-content-pipeline.md` | R2, R3, R4, R5, R6, F2, F3 | Rule dependency |
| P3 `field`, `register`, order in steps of 100, `Paused`/`Failed`, `skip_ticks`, `resolver_version`, the per-phase budget | `sim-core-and-tick-loop.md` | R1, R2, R4, R5, R6, R10, R17, Edge Cases | Rule dependency |
| Event block, `register_type` fields, milestone rules, ring budget | `event-bus-and-history-log.md` | R2, R3, R3a, OQ-3 | Rule dependency. Contributes 0 ring records per day |
| `award`, source-side vs member-side multipliers, once-per-kill guarantee, Elders earn no XP | `xp-and-level-pacing-curve.md` | R4, R5, R6, Edge Cases, Dependencies | Interface. Hunt owns kill XP and the level-difference penalty, as that GDD states |
| Balance gate, calibrator targets, parity vectors, aggregate-vs-exact test | `dev-tooling-and-parity-harness.md` | R11, Interactions | Tooling dependency |
| School element and role (feeding Combat and AI ground choice) | `schools-and-school-change.md` | Core Rules | Data dependency through Member model |
| Command vocabulary for orders | `command-layer.md` | (vocabulary) | Interface, provisional |
| `resolve`, `FightResult`, monster stats F1, deadline tick F8, domain-1 key | `combat.md` | R1, R2, R3, R5, R11, F1, F8, Interactions | Interface; monster stat formula owned there |
| Loot key, shared bag, `bag_full`, `hand_in`, `suited_first`, luck | `items-and-loot-tables.md` | R3, R3a, R4, R5, R6 | Interface; conflict on income split (OQ-11) |
| `credit`, mint types `hunt_gold` and `loot_handover`, per-trip credit | `gold-economy.md` | mint table, Interactions, AC-23, OQ-11 | Interface |
| `profile(member)` | `member-model.md` | R7 | Data dependency (passed to Combat) |
| Guild level | `guild-and-buildings.md` | (guild level) | Data dependency, provisional |

## Acceptance Criteria

*QA-lead lens applied: every core rule and formula has at least one criterion; formula criteria include boundary values; cross-system criteria are marked. **Logic** = automated unit test in `tests/unit/hunt/`; **Integration** = automated test in `tests/integration/hunt/`; **Playtest/Visual** = screenshot or playtest evidence in `production/qa/evidence/`. Criteria marked [PENDING] need a GDD or implementation that does not exist yet (Party, Member state machine, Offline progress, the engine); until then they run against the reference's stand-ins.*

**Content and access**
- **AC-1 [Logic] (R1, R6.4)**: **GIVEN** the default data, **WHEN** the spawn pool of every ground is built, **THEN** it contains only rows with `is_boss = false`, in ascending `uid` order, with at least 1 row each. 45 grounds are checked, and no zone boss appears in any pool.
- **AC-2 [Logic] (R2)**: **GIVEN** `live_wave = 1`, **WHEN** a group starts at `g_z12_1` (Wave 2), **THEN** the start is refused with code 11, and occupancy, ordinals and events are unchanged.
- **AC-3 [Logic] (R2)**: **GIVEN** guild level 1, **WHEN** a group starts at `g_z03_1` (`guild_lv_req = 2`), **THEN** it is refused with code 12. **GIVEN** guild level 2, **THEN** it is accepted.
- **AC-4 [Logic] (R2)**: **GIVEN** a group of two at guild level 6 where one member has rebirth 0, **WHEN** it starts at `g_z11_1` (`rebirth_req = 1`), **THEN** it is refused with code 13. With both members at rebirth 1, it is accepted.
- **AC-5 [Logic] (R4)**: **GIVEN** `g_z01_1` (capacity 6) with a 5-member trip active, **WHEN** a 2-member group starts there, **THEN** it is refused with code 14, and a 1-member group is accepted (occupancy 6). **GIVEN** two 1-member requests in one tick with one place left, **THEN** the one with the smaller `party_id` is accepted.
- **AC-6 [Logic] (R3, R5)**: **GIVEN** a member already in a trip, **WHEN** a second group containing them starts, **THEN** it is refused with code 15. **GIVEN** an empty roster or 6 members, **THEN** it is refused with code 16.

**Trip rules**
- **AC-7 [Logic] (R6.3, R14)**: **GIVEN** a trip whose weakest living member has `hp` exactly `0.25 × hp_max`, **WHEN** the check runs, **THEN** the trip continues. At one HP unit below, it ends with code 1. **GIVEN** low HP and a full bag together, **THEN** the code is 1.
- **AC-8 [Integration] (R6.3, Items R5)**: **GIVEN** a 3-member trip whose bag holds 89 slots, **WHEN** the check runs, **THEN** the trip continues. At 90 (`30 × 3`) it ends with code 2. **GIVEN** a kill that takes the bag from 148 to 152 slots in a 5-member trip, **THEN** all 152 units reach `hand_in`.
- **AC-9 [Logic] (R6.6, R9)**: **GIVEN** a stub Combat that reports a loss on the 3rd encounter, **WHEN** the trip runs, **THEN** it ends with code 3 after 2 kills, the third encounter pays no XP and rolls no drops, and the bag from the first 2 kills is settled in full.
- **AC-10 [Logic] (R6.7, F1)**: **GIVEN** a 5-member trip in which member B died in encounter 2, **WHEN** encounter 3 is won, **THEN** `award` is called for the 4 living members only, each with the F1 value using `n = 5`, and never for B.
- **AC-11 [Logic] (R7, F5)**: **GIVEN** the reference trip on a fixed scenario with Combat stubbed to fixed `duration_s` that are whole multiples of 0.1 s, **WHEN** this GDD's trip runs the same encounters, **THEN** `trip_ms` equals the reference's `time_s × 1000` exactly. With arbitrary durations, it exceeds it by at most 100 ms per scheduled step.
- **AC-12 [Logic] (R8)**: **GIVEN** a 3-member trip whose `hand_in` returns an income of 301 gold (100 accumulated gold + 201 of sales), **WHEN** settlement runs, **THEN** the members are credited 101, 100 and 100 gold in ascending member-ID order, the credits sum to 301, `hand_in` was called exactly once, and the `hunt_gold` credits sum to 100 and the `loot_handover` credits to 201.
- **AC-13 [Logic] (R11)**: **GIVEN** a trip in `Gap`, **WHEN** a recall is queued, **THEN** at the next check the trip ends with code 4, settles immediately with no Homebound or Selling ticks, and the members are released to the raid. **GIVEN** an order home during `Outbound` after 12 s of travel, **THEN** the trip reaches home 12 s later with 0 encounters and code 5.
- **AC-14 [Integration] (R12)**: **GIVEN** a fixed seed and a 2-hour scripted run with 4 groups on 4 grounds, **WHEN** it runs once with the camera on ground A and once with the camera moving every 30 s, **THEN** the event streams, every latched tier (R17) and the final saved state are identical byte for byte, and identical to a headless `run_ticks` run with no view at all.
- **AC-33 [Logic] (R17, F11)**: **GIVEN** the F11 example occupancies and K = 4, **WHEN** the snapshot runs, **THEN** `D = {E, A, B, C, D}` with E's recall queued and `{A, B, C, D}` without it; **GIVEN** a snapshot at tick 599 with `lod_eval_ticks = 600`, **THEN** no snapshot is taken until tick 600. **GIVEN** one live ground and K = 1, **THEN** every trip is `detailed`.
- **AC-34 [Logic] (R17.4)**: **GIVEN** a card-tier trip mid-replay on ground G, **WHEN** a snapshot moves G into `D`, **THEN** that trip finishes its replay (no Combat call until it closes) and the group's next trip is `detailed`; **GIVEN** the reverse, a detailed trip stays detailed.
- **AC-35 [Logic] (R17.1)**: **GIVEN** a group with no card on a card-tier ground, **WHEN** its chain runs, **THEN** every event, draw and result is bit-identical to the same chain at `detailed`, and a card is saved. **GIVEN** the next card-tier trip with the same roster and levels, **THEN** Combat `resolve` is called 0 times and no domain-1 or domain-3 generator is derived, drops come from domain 2 with key `[0, party_id, trip_ordinal, e]`, and `uses` becomes 1. **GIVEN** a level-up before the next trip, **THEN** that chain rebuilds the card.
- **AC-36 [Integration] (R17, F12, balance)**: **GIVEN** the max-roster fixture on 12 grounds for 24 game hours, 5 seeds, **WHEN** run with `lod_card_trips = 1` and with the defaults, **THEN** mean XP, gold and stored units per member differ by ≤ 3% and Combat `resolve` calls fall by ≥ 35%.
- **AC-37 [Integration] (R17.5, replay)**: **GIVEN** a recorded command log of the AC-36 run, **WHEN** it is replayed headless with `run_ticks` (no host, no camera) and saved/reloaded at a random tick, **THEN** every latched tier, card and the final state hash equal the live run.
- **AC-15 [Logic] (R10, R4)**: **GIVEN** a trip that has just ended its rest, **THEN** every member is alive at full HP, occupancy of the ground has fallen by `n`, and every member is eligible again.

**Formulas**
- **AC-16 [Logic] (F1)**: **GIVEN** the default data, **THEN** `kill_xp_milli[1] = 1,500`, `[23] = 165,456`, `[100] = 1,500,000` and `[200] = 4,242,640`. **GIVEN** the AC example (5 members, `xp_mult_ppm = 1,470,000`, diff 2), **THEN** `kill_base_milli = 48,644`. **GIVEN** a solo member with `xp_mult_ppm = 1,000,000` killing a level-1 monster at diff 0, **THEN** it is 1,500.
- **AC-17 [Logic] (F2)**: **GIVEN** `lvl_diff_free = 5`, a monster at level 23, **THEN** `diff_ppm` is 1,000,000 for members at levels 1, 23 and 28; 900,000 at 29; 500,000 at 33; and 100,000 at 37 and at 60.
- **AC-18 [Logic] (F3)**: **GIVEN** the default data, **WHEN** `kill_xp_table_hash` is computed in the Python reference and in the port, **THEN** both are equal and match the value recorded in the parity vector. Changing `xp_kill_exp` by 0.01 changes the hash. *(Break it: swap two cells in a scratch build and confirm the parity gate fails.)*
- **AC-19 [Logic] (F6)**: **GIVEN** `gap_s = 2`, **THEN** `gap_ms` is 2,000 at `spawn_rate = 1.0`, 1,600 at 1.25 and 20,000 at 0.1. **GIVEN** `spawn_rate = 0` in a fixture, **THEN** the content validator fails the load.
- **AC-20 [Logic] (F7)**: **GIVEN** a roster with one member at 40% HP and the rest full, **THEN** `rest_ms = 60,000`. **GIVEN** any dead member, **THEN** `rest_ms = 180,000`. **GIVEN** all at full HP, **THEN** 0.
- **AC-21 [Logic] (F9, R5)**: **GIVEN** party 7 on its 12th trip (`trip_ordinal` 11), **WHEN** its 4th encounter spawns, **THEN** the spawn generator is derived from domain 3 with key `[7, 11, 3]` and exactly one `choice` is drawn, the fight uses domain 1 with `[7, 11, 3]`, the drop roll uses domain 2 with `[0, 7, 11, 3]`, and party 7's `trip_ordinal` became 12 at trip start, while no other party's ordinal changed.
- **AC-22 [Logic] (F9, RNG R5)**: **GIVEN** a save just before a trip, **WHEN** it is reloaded twice, the second time after waiting 60 game seconds while other parties start trips, **THEN** this party's first-encounter spawn draw is identical in both runs.
- **AC-23 [Integration] (R15, F10) [PENDING: Offline 31]**: **GIVEN** the standard 5-member PA 100 party on `g_z02_3` for 24 hours, **WHEN** it is run once with the detailed resolver and once through `sample_rates` with 2-hour slices and 4 samples, **THEN** the XP difference is within Offline's tolerance (about 1% today), and `sample_rates` reports XP before the member-side multipliers (`award` applies `growth_mult` once).
- **AC-24 [Logic] (R15)**: **GIVEN** `sample_rates` is called, **THEN** the real members' level, XP, HP, gold and ordinals are unchanged afterwards, no event is emitted, and every draw came from domain 5 with the supplied keys.

**Events and cross-system**
- **AC-25 [Integration] (R13)**: **GIVEN** a seeded 5-member trip that ends `bag_full` after K kills, **THEN** the bus receives one 1101, K 1102 (with `encounter_ordinal` 0 … K−1 in order), one 1103 per death, and one 1104 with `c = 2` and `d = K`, in that order across ticks, and 1101–1104 are not written to history.
- **AC-26 [Integration] (R13)**: **GIVEN** a fresh save, **WHEN** two trips start in zone 1 and one in zone 2, **THEN** exactly two 1105 records exist in history (zone 1, zone 2), both milestones with `subject_slot = 0`, and they survive a save and load.
- **AC-27 [Integration] (R6.7, XP curve, Combat)**: **GIVEN** a solo PA 100 member at level 1 on `g_z01_1`, **WHEN** 2 game hours are simulated, **THEN** their level is above 1 and every XP change is traceable to one `award` call per kill (count of `award` calls with `source = hunt_kill` = count of 1102 events).
- **AC-28 [Integration] (R16)**: **GIVEN** a booted core, **THEN** the phase table contains exactly one entry for `owner_id = "hunt"` at `(P3, 1100)`, and the Event bus type table contains 1101–1105 owned by `hunt`.
- **AC-29 [Integration] (balance, Dev tooling 43)**: **GIVEN** the committed balance budget, **WHEN** the quick scenario runs, **THEN** the hunt rows (kills per trip, seconds per kill 6–25, death rate under 3%) are PASS, and the XP curve's time-to-level-100 row stays inside its band after the integer conversion (OQ-3).
- **AC-30 [Integration] (F8, performance) [PENDING: engine]**: **GIVEN** the max-roster fixture with every member hunting, **WHEN** run on the min-spec Android phone, **THEN** the p99 cost of this system's P3 handler stays inside the P3 share of the tick budget (Sim core R17).

**Playtest / visual**
- **AC-31 [Playtest] (Game Feel)**: in a 10-minute session with a fresh guild, the tester sees at least one homecoming with its settlement beat, and can say why each trip that ended did so (from the reason icon alone).
- **AC-32 [Visual] (Visual/Audio, UI)**: a retained screenshot each of the ground panel, a trip card mid-hunt and a trip report, showing element, danger and reason with icons and text (no colour-only information).

*Simulation LOD (R17, F11, F12) is covered by AC-33 – AC-37 (added 2026-11-16).* *Gaps found by the QA lens and resolved above:* the flee boundary (AC-7), bag overflow (AC-8), the dead-member share (AC-10), camera independence (AC-14) and reload determinism (AC-22) were added. Domain 4 has no draws, so it has no criterion beyond AC-21's "exactly one draw" in domain 3.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Zone bosses.** Each zone has a boss row (`m_zXX_boss`, `zones.boss_monster_id`, its own `drop_zone_XX_boss` table), but the reference never spawns it and GDD §6.3 says only "1 boss vùng". When and how does it appear (a periodic spawn, a summoning item, a zone-clear goal, the Tower)? Adding a spawn rule is a scope change, so this GDD keeps bosses out of trips. | User + game-designer | Before Vertical Slice |
| OQ-2 | **RESOLVED (user decision 2026-11-16):** simulation LOD, chosen by a deterministic in-sim rule, never by the camera. R17 + F11: forced grounds plus the top `lod_detail_grounds` by occupancy (ties lowest uid), snapshotted every `lod_eval_ticks`, tier latched per trip at start; other grounds run the card tier (fights replayed from a saved chain card, drops rolled for real). Camera is visual only (R12). Still open: the P1 spike measures the worst P3 tick (F8, AC-30) and tunes the three LOD knobs; the card-tier drift is gated by AC-36. Original: this GDD read §3.5 as presentation LOD only. | technical-director (tuning) | P1 spike |
| OQ-3 | **Migrating `sim/hunt.py` and `sim/offline.py` to this spec.** It changes outcomes once: per-event RNG keys (RNG OQ-1 hazard b), integer XP (F1), tick rounding (F5, ≤ about +2% trip time), capacity (R4), settlement remainder (R8) and source-side sampled XP (R15). Re-run `calibrate.py` and the balance gate afterwards, and re-measure GDD §4.3 / §18. *Observation:* the calibrator's target "8–16 kills per trip" (Dev tooling R11) does not match the measured 106 kills for a full party (it matches solo only); Dev tooling should say which scenario the target applies to. | Implementation story + Dev tooling (43) | Before Combat (10) implementation |
| OQ-4 | **Capacity values.** Is capacity 6/8/10 right for a full guild? 3 grounds per level band allow only 24 members at one band. Measure with Utility AI once a full roster exists. | game-designer, Utility AI (12) | Vertical Slice |
| OQ-5 | **`party_id` supply (R5, F9).** Combat, Items and this GDD all key encounters on `[party_id, trip_ordinal, …]`. If Party (13) mints a new `party_id` from a guild-wide counter whenever a group is re-formed, the player can change the dice by re-forming a party, and other parties' re-formations advance the counter (RNG R5 forbids that). Party must say how a solo hunter's and a re-formed party's `party_id` are chosen; the RNG owner must confirm the result. **RESOLVED (consistency-check 2026-11-16):** Party R5 keys every trip on the key leader's `member_id` and that leader's `trips_led`, so re-forming changes nothing and other parties cannot advance it (Party AC-10, AC-11); R5 above is aligned. RNG owner confirmation still advisable at RNG's next revision. | Party (13), RNG (2) owner | Closed |
| OQ-6 | **Data layer additions (schema changes, not made here):** `grounds.wave`, already listed by the Data layer; validator checks `speed > 0`, `spawn_rate > 0`, `bag_slots ≥ 1`, `regen_pct_per_s > 0`, at least one non-boss row per pool, and ground wave = zone wave; and whether the float knobs converted to ppm at load (F1, F2, F6, F7) should become integer columns in the CSV, as the XP curve's OQ-2 proposes for its keys. | Data layer (3) | With the Data layer migration |
| OQ-7 | **Offline hand-off of an in-progress trip, and offline loot.** Recommended: finish the in-progress trip with the detailed resolver, then fill the remaining time with sampled rates. The sampled resolver must value a bag without writing guild storage, so Items (26) must provide a side-effect-free valuation of `hand_in` (R15), and offline would return gold but no stored materials or equipment. Is that acceptable to Items, Guild and buildings (material costs) and the offline report? **RESOLVED (consistency-check 2026-11-16):** Offline pauses an in-progress trip instead (Offline R5), and offline loot is the sampled trips' own bags handed in whole and in rotation (Offline F4, R15 `bags[i]`), so materials and gear do come home and no valuation function is needed | Offline progress (31), Items (26) | Closed |
| OQ-8 | **Gold from farming low grounds.** F2 penalises XP but not gold or drops. Should low-level farming be bounded in Items or Gold economy (for example, a level-difference factor on drops)? | Items (26), Gold economy (27) | When 26 is designed |
| OQ-9 | **Summoning tokens and recall.** Does a Triệu Tập Lệnh (GDD §6.5) recall hunting members the way the hourly boss does? If so, the player can trigger R11's immediate settlement at will. | Golden Boss (14) | When 14 is designed |
| OQ-10 | **§6.4 needs triggers** (hunger, fatigue, out of potions; codes 6–8). The owners and thresholds are undecided. GDD §20 S3 makes potions real in combat. | Gold economy (27), Member state machine (41) | Vertical Slice (S3) |
| OQ-11 | **Who splits the trip income (R8).** Items R6 step 4 credits one amount to the party and leaves the split to Gold economy. Gold economy OQ-11 and AC-23 say Zones and hunt owns the amounts and the split. This GDD takes the split. Items' step 4 should then return the income rather than credit it. Also: Gold economy's Tuning Knobs list `base_gold_coef`/`base_gold_exp` as owned by (11), but Items F1 builds `base_gold_milli`, so Items owns them; this GDD does not claim them. **RESOLVED (consistency-check 2026-11-16):** Items R6 step 4 now returns the income; this GDD splits it (R8). Gold economy now names Items as owner of `base_gold_coef`/`base_gold_exp` and the sell ratios | Consistency check: Items (26), Gold economy (27) | Closed |
| OQ-12 | **Monster `ai_skills`.** Combat OQ-4 asks whether Skills (21) or Zones (11) owns monster skills. This GDD owns the monster rows and the `ai_skills` column but defines no skill table. Recommended: Skills (21) owns the skill definitions (one effect schema), and this system owns which monster lists which skill. | User; Skills (21) | Before S4 |
| OQ-13 | **LOD force predicates (R17.3).** Golden Boss (14) and Onboarding (44) are named as `lod_force` registrants; neither GDD defines the predicate yet. Until they do, only queued recalls force a ground. | Golden Boss (14), Onboarding (44) | Consistency pass |
| PROVISIONAL | **Party (13)** — hands over a fixed roster of 1–5 for one trip with a stable `party_id` (solo included) and stores the party's `trip_ordinal`; `xp_mult_ppm(roster)` read once at trip start (today `1 + 0.08 (n−1) + 0.10 buffer + 0.05 tank`, converted to ppm); the loot rule is Items' `suited_first`. | Party (13) | When 13 is designed |
| PROVISIONAL | **Member state machine (41)** — "available to hunt"; drives `hunting`/`returning`/`resting`/`dead` from 1101/1103/1104; runs the rest of length `rest_ms` and restores full HP at its end; injury rules on 1103. | Member state machine (41) | When 41 is designed |
| PROVISIONAL | **Golden Boss (14)** — sends a recall; receives a settled group at its encounter end; owns gathering time and whether resting members can join. | Golden Boss (14) | When 14 is designed |
| PROVISIONAL | **Guild and buildings (30)** — exposes the guild level read by R2 (its GDD exists but does not yet list Zones (11) as a reader). | Guild and buildings (30) | Next consistency check |
| PROVISIONAL | **Offline progress (31)** — supplies domain-5 `sample_keys`, slice length and sample count; applies F10; owns the tolerance and `resolver_version`. | Offline progress (31) | When 31 is designed |
