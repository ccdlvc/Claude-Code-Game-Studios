# Items and Loot Tables

> **Status**: Designed (revised 2026-11-16, pending re-review)
> **Author**: Claude (design-system, autonomous batch run; decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no game pillars written yet; anchored to JX1_Tycoon_GDD.md §1, §6.5, §6.12, §19)
> **Mode**: Retrofit against `sim/hunt.py` (`roll_drops`, `_equip_pool`, the bag in `run_trip`) and `data/items.csv`, `materials.csv`, `drop_tables.csv`
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, `game-concept.md` or `game-brief.md` exist to check against; re-run once pillars are written

## Summary

Items and loot tables is the system that decides what a kill drops, how much the party can carry home, what happens to that loot when it arrives (equipped by the member it suits, sold, or put into guild storage), and how the guild master hands stored items to members. It is the "carry loot home" half of the guild loop and the "distribute supplies" verb of GDD §1. It exists because every gold coin earned by hunting, every material that builds the guild and every piece of rare gear passes through it, so it must be data-driven, integer-exact and identical in Python and the engine port.

> **Quick reference** — Layer: `Core` · Priority: `MVP` · Key deps: `Deterministic RNG, Data layer and content pipeline, Sim core and tick loop, Event bus and history log, Schools and school change, Member model, Gold economy, Zones and hunt trips` · Feasibility: NOT SOURCEABLE (no engine Scripting module; OQ-9)

## Overview

This system owns four things. **Item definitions**: the 1,043 rows of `data/items.csv` (945 equipment pieces in 21 tiers and three rarities, 91 consumables, 7 special items) and the 45 materials of `data/materials.csv`; it owns what an item row *means* (slot, requirement, rarity, value) while the Data layer owns loading and liveness. **Loot tables**: the 315 data rows of `data/drop_tables.csv`, grouped into 30 zone tables (normal and zone-boss) and 15 Golden Boss tables, and the rule that turns one kill into a set of drops using the project RNG (domain 2, `loot`). **The bag contents and the hand-in**: what fills the party's bag on a hunting trip (its capacity is Zones and hunt's), and what happens when the party returns home: equipment goes to the member it suits if it is a clear upgrade (their old piece goes to storage), unclaimed equipment is sold, and materials enter guild storage while the party is paid their sell value. **Guild storage and the designated award**: an uncapped store of items and materials that belongs to the guild, fed by hand-ins, Golden Boss loot, school changes and crafting, and drained by buildings, crafting, enhancement and the bang chủ's "designated award" (*chỉ định trao*, GDD §6.5), the one command by which the player gives a stored item to a chosen member.

The player rarely touches this system directly. They see it as a party walking home with a full bag, a gold figure ticking up, a member who suddenly wears a blue-rimmed sword, and a storage screen filling with Golden Boss spoils that they decide who deserves. Without it the loop has no reward: a kill would produce XP and nothing else, the guild would have no materials to build with, and the guild master would have no gifts to give. The behaviour described here matches the Python reference (`sim/hunt.py`) except where this GDD deliberately changes it to meet the source GDD (the PA drop multiplier of §4.2, the party loot rule of §6.12, guild storage of §6.5) or the integer-parity rules of Deterministic RNG; each change is listed in OQ-1.

*Scope note:* this system does not own gold. It computes how much gold a drop or a sale is worth and hands that amount to Gold economy (27), which owns both currencies, the guild fund and every credit and debit (systems index, per-system notes). It does not own the member's equipment slots or inventory either; Member model (8) stores them, and this system writes to them only through Member model's interface.

## Player Fantasy

**The fantasy has two halves: the bag that comes home full, and the gift the guild master chooses to give.**

*The bag comes home.* A party of five has been in Hàn Thuỷ Đầm for twenty minutes. The player glances over and sees them walking back along the road, packs bulging. At the gate the gold counter jumps, a stack of river-reed materials lands in storage, and the young swordsman at the back is suddenly holding a rare blade he picked up on the way. Nobody was told to do this. The guild worked while the player watched, and the reward is visible and concrete: gold, goods, gear. The anchor is GDD §1: *"thành viên đi săn → mang tài nguyên về → bang bán/chế tạo/nâng cấp → thành viên mạnh hơn"* (members hunt → bring resources home → the guild sells, crafts, upgrades → members grow stronger). The design owes the player a hand-in that is a clear, readable moment, and drops whose value climbs with the zone.

*The guild master's gift.* The hourly Golden Boss falls and its spoils belong to the guild, not to whoever struck last. An epic armour sits in storage. The player opens storage, looks at the roster and chooses: the tank who held the line, or the high-potential recruit who needs it to catch up. They tap *Award*, the member equips it, and the history log records the gift. The anchor is GDD §6.5: *"đồ rơi thuộc **bang** … bang chủ **chỉ định trao**"* (the loot belongs to the guild; the guild master awards it). This is one of the four guild-master verbs (§1: *"phân phối vật tư"*, distribute supplies), so the design owes the player a real choice: storage must hold things worth giving, the award must be immediate and visible, and the system must never hand those items out on its own.

**What this asks of the rest of the design.** Drops must be honest: no hidden pity timers or streak rigging (RNG R10), and potential (PA) is the only member trait that nudges rare-drop odds, as §4.2 promises. Loot must never be lost: a wiped party still brings its bag home, displaced gear goes to storage, and enhanced gear is never sold automatically.

*Pillar anchor:* none. The project has no pillars yet (systems index, CD-SYSTEMS note). Candidate framings considered: (1) "the bag comes home" (chosen, the idle-reward half), (2) "the guild master's gift" (chosen, the agency half), (3) "the treasure hunt" (rejected: rare drops are 1.5% per kill and mostly sold, so a jackpot fantasy would over-promise what the tables deliver). `creative-director` lens applied in-session, not by an agent.

## Detailed Design

### Core Rules

**Terms.** A *loot table* is the group of `drop_tables` rows that share one `table_id`. A *row* is one possible drop. A *unit* is one item or one material. *Equipment* is an item with `kind = equip`; a *consumable* has `kind = consumable`; a *special* has `kind = special`. An *instance* is a stored or equipped equipment unit together with its enhancement level (0–20; Enhancement 24 owns the value). The *party* is the group that made a kill (a solo hunter is a party of one; Party 13 and Hunt 11 own that).

**R1: Item and material definitions.** This system owns the meaning of these columns (Data layer owns loading, types, IDs and liveness):

| Table | Column | Meaning (owned here) |
|---|---|---|
| `items` | `kind` | `equip`, `consumable` or `special` |
| `items` | `slot` | equipment: `weapon`, `armor` or `accessory`; consumable: `potion`, `food`, `drink`; special: `special` |
| `items` | `family` | equipment: weapon family (one per school), armour class, or accessory type `ring` / `amulet`. The member slot an accessory fills is its `family` |
| `items` | `school_req`, `armor_class` | Inputs to Schools R7, the only rule that decides school eligibility |
| `items` | `tier`, `level_req` | Tier 1–21; the member's level must be ≥ `level_req` to equip or use it |
| `items` | `rarity` | `common` < `rare` < `epic` (rarity rank 0, 1, 2) |
| `items` | `stats` | The item's effect map. Equipment stats are read by Member model and Combat; consumable and special effects are read by the system that applies them (19.2 buffs: Gold economy and the buildings; specials: see R9) |
| `items` | `price` | The item's base value in whole gold. It is the buy price where a shop sells it (Gold economy, Market) and the base of the sell value (F5). It is **not** a power order: today an epic tier-2 weapon (atk 77, price 2,367) costs more than a common tier-3 one (atk 106, price 924), so upgrades compare stats (R6). Specials have price 0 and cannot be sold |
| `items` | `craftable` | Only `common` items may be craftable (validator rule today); Crafting (28) owns recipes |
| `materials` | `zone_id`, `grade` | Each zone has grades 1–3 |
| `materials` | `base_price` | Whole gold; the base of the material sell value (F5) |

**R2: Loot table rows.** Each `drop_tables` row has a `kind` and is resolved as follows (columns per Data layer R4, with `chance` renamed `drop_chance_ppm` by Data layer OQ-1):

| `kind` | `ref` | Quantity | What one hit produces |
|---|---|---|---|
| `gold` | `base_gold` | `qty_min`–`qty_max` are **multipliers** of the level's base gold (0.8–1.2 for normal kills, up to 10–15 for Golden Bosses) | Whole gold (F2) |
| `material` | a material ID | `qty_min`–`qty_max` integer units | That many units of the material |
| `item` | an item ID | `qty_min`–`qty_max` integer units | That many units of the item |
| `equip_pool` | a rarity | exactly 1 (validator: `qty_min = qty_max = 1`) | One equipment piece drawn uniformly from the **pool**: every live equipment row of that rarity with `lv_min ≤ level_req ≤ lv_max`, in ascending `uid` order |

Every row is rolled independently (a kill can drop gold, two materials and a rare all at once). This is the model of the reference code and of today's data, and it is kept. There is no weighted single pick in any table today. If one is added later, it must follow the RNG F5 rule (randint against cumulative integer weights in `uid` order) and be specified here first.

**R3: One kill, one loot event.** A loot roll is one RNG event in domain 2 (`rng_domain_loot`). Its event key is:
- hunt kill: `key_encounter = [party_id, trip_ordinal, encounter_ordinal]` exactly as Zones and hunt (11, F9) supplies it, **with no source tag in front**, shared with domains 1 and 3 for the same encounter (domains keep the draws independent, RNG R4). `party_id` is the leader's `member_id` and `trip_ordinal` the leader's `trips_led` (Party R5);
- Golden Boss: `[0, 1, raid_ordinal]`, where `raid_ordinal` is the guild's raid counter owned by Golden Boss (14);
- `[0, 2, …]` is reserved for Endless Tower (19); `[0, t, …]` for t ≥ 3 for later sources.

A hunt key's first component is a member ID, which is always ≥ 1, so a key starting with 0 can never equal a hunt key: hunt keys never collide with a Golden Boss or Endless Tower key, whatever the party ID (revision 2026-11-16: Zones F9's `[0, party_id, …]` form is withdrawn, because party 2 would collide with Endless Tower's `[0, 2, run_ordinal, floor]`). Uniqueness within a source is inherited from the owner's counter (RNG R6). No key contains party composition, equipment, PA or any other player-mutable value (RNG R5). Luck (R4) is an *input* to the roll, so a reload with a different party re-uses the same dice with different odds; this is the accepted seeded-RNG property (RNG Edge Cases, save-scumming).

**R3a: Draw order is a contract (RNG R7).** Within one loot event, rows are processed in ascending `uid` order of the group. For each row:
1. Exactly one `chance_ppm(effective_ppm)` draw (F4), even when `effective_ppm` is 0 or 1,000,000.
2. If it hits: `gold` → one `randint(qmin_milli, qmax_milli)` (F2); `material` and `item` → one `randint(qty_min, qty_max)`, even when the bounds are equal; `equip_pool` → one `choice(pool)`.
3. If it misses: no further draw for that row.

Changing this order, or adding or removing a draw, is a breaking change to the parity vectors (Dev tooling 43).

**R4: Luck.** Only rows of kind `equip_pool` whose rarity is `rare` or `epic` are affected by luck (GDD §4.2: *"tỷ lệ rơi đồ hiếm cũng nhân theo PA"*, the rare-drop rate also scales with PA). Their probability is multiplied by the party's `luck_milli` (F3, F4). Luck comes from each member's true PA, from the cumulative `drop_rate` rewards of their rebirth tier (`rebirth.csv`, tier 3 today), and from the member's `drop_rate` and `rare_drop` trait modifiers (`trait_mod_ppm`, which for a disciple already includes the Elder buff `elder_mod_ppm`, Rebirth R8). **`drop_rate` and `rare_drop` mean the same thing in this game: rare-drop luck.** Neither scales gold, material, item or common-equipment rows; this is the meaning `rebirth.csv`'s `drop_rate` already has here (revision 2026-11-16). It is centred so that an average guild (PA 100, no rebirth bonus) gets exactly the tabled odds. Golden Boss loot uses `luck_milli = 1000` (guild-owned loot; no single member's potential should steer it). No purchase, entitlement, ad or setting changes luck (RNG R10).

**R5: The bag.** During a hunting trip the party carries one shared bag:
- Capacity is owned by Zones and hunt (11, F4: `bag_capacity = bag_slots × n`, `bag_slots` 30). This system defines only what fills it: each item or material unit uses one slot; gold uses none.
- Hunt checks the bag before each new encounter and ends the trip with reason `bag_full` (Zones R6 step 3). The last kill's loot is always added in full, so a bag can end up to one kill's drops above capacity. Nothing is ever discarded for lack of room.
- The bag is kept whatever ends the trip (`bag_full`, `low_hp`, `lost`, `wiped`). A wiped party still brings its loot home. The game has no loot-loss mechanic.
- The bag is not saved mid-trip as a list of rolls; it is saved as its contents (item and material counts plus a gold accumulator), so a save in the middle of a trip resumes with the same bag.

**R6: Hand-in.** When selling ends (Zones R8 settlement, the "sell" step of the GDD §6.4 `returning` state), Hunt calls `hand_in(roster, bag)`, which resolves the bag in this fixed order:
1. **Equipment, by the party loot rule `suited_first`** (GDD §6.12, the only rule in MVP). Equipment units are processed in ascending item `uid`, then in the order they were rolled. For each unit, the *candidates* are the party members who are present (not `away`) and for whom:
   - Schools R7 allows the item for the member's school;
   - `level_req ≤` the member's level;
   - the member's slot for that item (`weapon`, `armor`, or the accessory `family`) is empty, or holds an item at **enhancement level 0** that the new item **dominates**: every stat key of the current item is present in the new item with a value ≥, and at least one is strictly greater (stat maps from `items.stats`). Dominance needs no stat weights, so it never trades one stat for another on the member's behalf; a mixed case is left for the player or Member model's re-gear.

   The unit goes to an empty-slot candidate first, then to the candidate whose current item has the lowest `level_req`; ties go to the lowest `member_id`. It is handed to Member model `equip` (Member model R6). The displaced item, if any, goes to guild storage (Member model R6: an item is never destroyed). If there is no candidate, or `equip` refuses, the unit is sold (F5). A member with an enhanced item in a slot is never auto-upgraded in that slot, because dominance ignores enhancement and an unenhanced rare can be weaker than a +10 common; the player can still award a better item to them (R8).
2. **Materials** go to guild storage, and each unit's sell value (F5) is added to the trip's sale total. (Retrofit parity: in the reference code the member is paid for every material, and the guild receiving the material too is the EHT pattern of §1. To stop the same material being paid twice, materials can never be sold out of storage (R13), which answers Gold economy OQ-15.)
3. **Items** (`kind = item` rows, specials and consumables) go to guild storage. They are not sold.
4. **Gold**: the result is two whole-gold totals, `drop_gold` (the bag's gold accumulator) and `sale_gold` (every sale in steps 1–2). `hand_in` **returns** both totals to its caller and credits nothing. The caller divides and credits them: live settlement is Zones and hunt R8 (which owns the split: equal integer shares over the whole roster, remainder by ascending member ID, credited as `hunt_gold` and `loot_handover`, Gold economy R3 types 1 and 2); Offline progress (31) applies the same Zones R8 split and credits `offline_hunt` (Offline R14). This system never writes a wallet (consistency-check 2026-11-16: resolves Zones OQ-11 / Gold economy OQ-11).
5. One `loot_handed_in` event is emitted, plus one `rare_haul` per roster member when the bag held at least one rare-or-better unit (R10).

**R7: Guild storage.** Guild storage is one store per guild, owned by this system:
- It maps a key `(content_id, enhance_level)` to a count (int64 ≥ 0). Materials, consumables and specials always use `enhance_level = 0`; equipment keeps its level, so an enhanced weapon returned to storage comes back out with the same level.
- It is **uncapped**. No storage building exists in GDD §7, and Schools (20) requires that gear returned on a school change is never destroyed. If a cap is ever added it belongs to Guild and buildings (30) and must never destroy items (OQ-4).
- Entries with count 0 are removed. Retired content (Data layer R5) stays in storage and remains usable; liveness gates only what is *newly* offered (drops, shops, recipes), never what the player already owns.
- Writers: hand-in (R6), Golden Boss loot (R9a), Schools (gear moved on joining or changing), Member model and the award (displaced gear), Crafting (outputs), Market (purchases, VS). Readers and consumers: Guild and buildings (material costs), Crafting (inputs), Enhancement (wards, VS), Schools (`item_school_token`), Golden Boss (`item_summon_horn`), Party (`item_banner`), Recruitment (`item_recruit_token`), CA/PA (`item_pa_lens`), and the award. (`item_pa_eye` never enters storage; see R9.) Every other system reads and changes storage only through `count(key)`, `give(map)` and `take(map)` (the names Guild and buildings R2/R3 already uses; a key without an enhancement level means level 0). `take` is all-or-nothing: if any entry of the map is short it returns false and changes nothing, so a consumer can never drive a count negative and a multi-material cost is never half-paid. `give` always succeeds (storage is uncapped).

**R8: The designated award.** The player command `award_item(member_id, content_id, enhance_level)` (through the Command layer, 5) hands one unit from storage to a member. It is applied in P1 and is refused, with a `item_award_refused` event and no change, when:
- the member does not exist (reason 1);
- storage holds no unit with that key (reason 2);
- the item is not awardable: materials, and specials whose effect is used by the guild rather than a member (R9) (reason 3);
- for equipment: Schools R7 forbids it (reason 4), `level_req` exceeds the member's level (reason 5), or Member model `equip` refuses for the member's state (`hunting`, `boss_raid`, `away`, `dead`, `training`; Member model R6 rule 6) (reason 7). A refused unit stays in storage;
- reason 6 is reserved and never raised in this version: the member inventory (`inventory[]`, stored on Member model's record) is **owned by this system and uncapped**, a map `content_id → count` holding only awarded consumables and member-held specials, never the hunt bag (that is the trip's, R5). If a cap is ever added it is defined here and refuses with reason 6 (revision 2026-11-16; resolves the bag/inventory ownership split with Member model R1).

If accepted: equipment is equipped at once in its slot, and the displaced item (any enhancement level) goes to storage, never sold; consumables and member-held specials go to the member's inventory. One unit per command; the player repeats the command for more. A member out hunting cannot be awarded gear until they are home (reason 7); the award screen says so. Awarding gold instead of an item is Gold economy's `gold_award` (entry type 43). The award is free in MVP. When the Guild market (29) ships, buying from storage with member gold is a second path to the same item, owned by the Market (GDD §6.5).

**R9: Special items.** The seven specials are handled by who uses them. *Member-held* (awardable): `item_rebirth_pill` (Rebirth 23 consumes it from the member). *Guild-held* (stay in storage, consumed there by their owner): `item_summon_horn` (Golden Boss 14), `item_banner` (Party 13), `item_recruit_token` (Recruitment 15), `item_pa_lens` (CA/PA 9; sold by IAP 34 and granted by Quests, not dropped), `item_enhance_ward` (Enhancement 24; craft-only). `item_school_token` (Schools OQ-2) is guild-held. **`item_pa_eye` (Thiên Nhãn) is not a storage item:** it is a permanent purchase that Entitlement (32) exposes as `exact_pa_all` in its injected snapshot (CA/PA R10, IAP R2); the simulation never stores, gives, takes or awards it, and its `items.csv` row is only a catalog/display reference (`give` of `item_pa_eye` is a caller error; IAP AC-6 refuses it at the command). *(consistency-check 2026-11-16: resolves CA/PA OQ-13, IAP OQ-9.)* Until `items.csv` has a column for this (OQ-5), the split is the list above, keyed by the effect key in `stats` (`rebirth` → member-held; everything else → guild-held).

**R9a: Golden Boss loot.** When Golden Boss (14) reports a raid won, it calls `roll_guild_loot(raid_ordinal, loot_table, boss_level)`. The roll follows R3a with `luck_milli = 1000`. All items and materials go straight to guild storage (no bag, no auto-equip, no sale), and the table's gold (F2) is returned to Golden Boss, which credits it to the **guild fund** as a `boss_reward` mint (Gold economy R3, entry type 4). This system never writes the fund. Personal raid rewards (XP and gold by contribution, §6.13) belong to Golden Boss, not to this table. Offline backlogged bosses (§6.5) use the same call, one per resolved boss. **Keyed form (Endless Tower R9/F4, OQ-5).** The general entry point is

`roll_guild_loot_keyed(key: int[], loot_table: table_id, level: int, rolls: int) -> int` (whole gold rolled)

- `key` must start with 0 followed by a source tag ≥ 1 reserved in R3 (`[0, 1, raid_ordinal]` Golden Boss, `[0, 2, run_ordinal, floor]` Endless Tower); any other key is a caller error (fails loudly).
- `rolls` is 1 – `loot_rolls_max` (8). One generator is derived once from `(domain 2, key)`; the table's rows are processed `rolls` times in sequence from that one generator, each pass by R3a, with `luck_milli = 1000`. `rolls = 1` is bit-identical to a single roll.
- All items and materials go to guild storage, `epic_loot` (2602) is emitted per epic unit with `a = 0` and `c` = the key's source tag, and the summed table gold of all passes is **returned** to the caller, which credits the fund (Golden Boss `boss_reward`, Endless Tower `tower_reward`). This system never writes the fund.

`roll_guild_loot(raid_ordinal, loot_table, boss_level)` is exactly `roll_guild_loot_keyed([0, 1, raid_ordinal], loot_table, boss_level, 1)`.

**R10: Events.** This system registers type block 2600–2699 with the Event bus (`items_event_type_block`). Payload IDs for content are their `uid` (Data layer R6):

| type_id | Name | Fields | Logged | Milestone | Subject slot | `ring_per_day` |
|---|---|---|---|---|---|---|
| 2601 | `loot_handed_in` | `a` party_id, `b` trip income (gold), `c` units sold, `d` material units stored | no | no | — | 0 |
| 2602 | `epic_loot` | `a` party_id (0 for a guild source), `b` item uid, `c` source tag (R3: 0 hunt, 1 Golden Boss, 2 Endless Tower) | yes | no | — | 24 |
| 2603 | `item_awarded` | `a` member_id, `b` item uid, `c` enhance_level | yes | no | 1 | 50 |
| 2604 | `item_award_refused` | `a` member_id, `b` item uid, `c` reason (R8) | no | no | — | 0 |
| 2605 | `item_auto_equipped` | `a` member_id, `b` new item uid, `c` displaced item uid (0 if none) | no | no | — | 0 |
| 2606 | `rare_haul` | `a` member_id, `b` rare-or-better units in the bag, `c` best rarity rank (1 rare, 2 epic) | no | no | — | 0 |

`epic_loot` is emitted once per epic unit at roll time (zone bosses and Golden Bosses are the only epic sources today). Rare drops are not announced individually (about 1.5% of all kills; too many for the history ring); the hand-in summary, `item_auto_equipped` and `rare_haul` carry them. `rare_haul` is the per-member "their hunt produced a rare-or-better drop" signal that CA/PA (9) uses as a trait-reveal trigger. Peak emission per returning party per tick: one 2601, at most 5 × 4 = 20 `item_auto_equipped` (5 members, 4 slots), at most 5 `rare_haul`, plus one `epic_loot` per epic unit rolled.

**R11: Where it runs.** All loot rolls, hand-ins and storage writes happen in the Sim core `economy` phase (P4), in one handler registered as owner `items` at order 2600 (the block-number convention Gold economy uses for its own P4 handler, 2700, so loot resolves before the ledger handler in the same tick). Hunt (P3) queues each kill `(event key, table_id, monster level, party)` and each return; this handler drains the queue in queue order in the same tick. The award runs in P1 with the other commands. The roll, `bag_full` and `hand_in` are also exposed as pure functions over explicit inputs, so the aggregate hunt resolver and Offline progress (31) call exactly the same rules without a live tick (R12).

**R12: Offline and aggregate resolution.** The aggregate hunt path and offline fast-forward must deliver loot through `hand_in`, never by crediting gold directly. A sampled trip is rolled exactly and Zones R15 returns each sampled trip's unscaled bag. Offline fills the elapsed time by handing in **whole sampled bags in rotation** (Offline F4), calling `hand_in` once per filled trip, so auto-equip, storage and sale all apply and no unit is ever fractional (answers OQ-6). The acceptance target is AC-24.

**R13: What the player cannot do.** The player cannot edit drop odds, re-roll a drop, pick which member a hunt drop goes to (only `suited_first` exists in MVP; other `loot_rule` values are Vertical Slice, OQ-7), sell **materials** from storage (they were already paid for at hand-in; Gold economy's `sell_item` R15 sells equipment and consumables from storage at F5's value, and this system refuses a material taken for that purpose), destroy items, or award materials. Members never take items from storage on their own; only the award, and the owning systems in R7, take from it.

### States and Transitions

The lifecycle of one loot unit:

| State | Enters from | Leaves to | Trigger |
|---|---|---|---|
| Rolled | — | In bag; In storage | Loot event (R3). Hunt rolls go to the bag; Golden Boss rolls go to storage (R9a) |
| In bag | Rolled | Equipped; Sold; In storage | Hand-in (R6) |
| Equipped (on a member) | In bag (auto-equip); In storage (award) | In storage (displaced by auto-equip or award, school change, any Member model unequip or removal) | R6 step 1, R8, Member model R6, Schools R5/R3 |
| In storage | Rolled (boss); In bag (materials, items); Equipped; Crafted; Bought (`buy_item`) | Equipped; Member inventory; Consumed; Sold (Gold economy `sell_item`, never materials) | R8 award, `take` by an owning system |
| Member inventory | In storage (award) | Consumed | The using system (Rebirth, consumable use) |
| Sold / Consumed | — | (terminal; the unit no longer exists) | — |

Invalid transitions: a material never goes from storage to "sold"; nothing goes from a member back into a bag; nothing disappears without one of the terminal events. An equipped item never reaches "sold" directly; it passes through storage, where only the player's `sell_item` can sell it.

The bag itself has three states owned by Hunt's trip: *empty* (trip start), *filling* (encounters), *handed in* (return; the bag is cleared and the trip's `TripResult` is final).

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Deterministic RNG (2) | in | `derive(2, key)`, `chance_ppm`, `randint`, `choice` | — | RNG |
| Data layer (3) | in | Typed `items`, `materials`, `drop_tables` groups in `uid` order, liveness query, `config`/`sim_params` values | — | Data layer owns lookup and liveness; this system owns meaning (R1) |
| Sim core (1) | in | P4 handler slot, P1 command slot, `ctx.emit` | — | Sim core |
| Event bus (42) | out | — | Types 2601–2606 (R10) | Each feature owns its block |
| Schools (20) | in/out | R7 "may this school use this item" | Storage `give` for gear moved on joining/changing; `take` for `item_school_token` | Schools owns R7; this system owns storage |
| Member model (8) | in/out | Member's level, school, PA, rebirth, present/away/dead, equipped item and its enhancement per slot | `equip(member, slot, item, enh)` returning the displaced instance; `give(member, item)` to inventory | Member model owns the fields; provisional |
| CA/PA and traits (9) | in/out | True PA of each member (via Member model); `trait_mod_ppm(m, drop_rate)` and `trait_mod_ppm(m, rare_drop)` (Elder buff included, Rebirth R8) | `rare_haul` (2606) for `event:rare_drop` | CA/PA |
| Rebirth (23) | in | `drop_rate` in `rebirth.csv` rewards | Rebirth pill handed to a member (R8) | Rebirth owns tier rewards |
| Gold economy (27) | out | `sell_item` / `buy_item` calls that `take` / `give` storage | `drop_gold` and `sale_gold` per settlement (credited as `hunt_gold`, `loot_handover`); sell values (F5) | Gold economy owns every credit |
| Zones and hunt (11) | in/out | Kill queue entries with `key_encounter` (Zones F9), monster level, roster; settlement trigger (Zones R8) | Roll results into the bag; `hand_in` results | Hunt owns trips, bag capacity (Zones F4) and settlement timing; this system owns rolls, storage and sale value |
| Golden Boss (14) | in | Raid won, `raid_ordinal`, `loot_table`, boss level | `roll_guild_loot` (R9a) gold returned; storage contents; `take` for summon horn | Golden Boss |
| Endless Tower (19) | in | Floor cleared, `run_ordinal`, floor, `loot_table`, level, `rolls` | `roll_guild_loot_keyed` (R9a) gold returned; storage contents | This system owns the call; Tower owns the key's counters |
| Offline progress (31) | in | Scaled bags (R12) | Same as hand-in | Offline |
| Command layer (5) | in | `award_item` command | Accept/refuse | This system owns the command's name and args (R8); Command layer carries it |
| Crafting (28), Guild and buildings (30), Enhancement (24), Party (13), Recruitment (15), Market (29) | in/out | `give`/`take` on storage | Storage counts | This system |
| Local save (6) | out | — | Storage map, in-trip bags, registered serializer | Local save owns the contract |
| Guild screens (39), Realtime view (38) | out | — | Storage read model, events | UI reads only |

## Formulas

All runtime arithmetic is integer. Floats appear only at boot, when F1 builds a table and when `qty_min`/`qty_max` and the sell ratios are converted once to thousandths (`round(x × 1000)`, round half up). The boot tables and conversions are part of the parity vectors (AC-22), so a Python and engine build that disagree are caught before play. Values reproduce `sim/formulas.py` (`base_gold`) and `sim/hunt.py`.

### F1: `base_gold_milli`

The base_gold_milli formula is defined as:

`base_gold_milli[L] = floor( 1000 × base_gold_coef × L ^ base_gold_exp + 0.5 )`, built at boot for L = 1 … 200

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L | int | 1 – 200 | calculated | The monster's (or Golden Boss's) level |
| base_gold_coef | float | 0.1 – 100 (2.0 today) | data file (`config.csv`) | Gold scale |
| base_gold_exp | float | 0.5 – 2.0 (1.1 today) | data file (`config.csv`) | How fast gold grows with level |
| 1000 | constant | — | constant | Thousandths of a gold |

**Output Range:** 2,000 (L 1) to 679,459 (L 200) milli-gold with today's data; strictly increasing in L. Validator: every cell ≥ 1.
**Example:** L 50: `2.0 × 50^1.1 = 147.876` → `147,876`.

### F2: `gold_drop`

The gold_drop formula is defined as:

`gold_drop = ( base_gold_milli[L] × q_milli + 500,000 ) div 1,000,000`, with `q_milli = randint(qmin_milli, qmax_milli)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| base_gold_milli[L] | int | 2,000 – 679,459 | calculated (F1) | Base gold for the level |
| qmin_milli, qmax_milli | int | 0 – 100,000, `qmin ≤ qmax` | data file (`drop_tables.qty_min/qty_max` × 1000 at boot) | Multiplier bounds (800–1,200 normal kills; 10,000–15,000 Golden Boss) |
| q_milli | int | qmin – qmax | calculated (RNG F4) | The rolled multiplier |

**Output Range:** whole gold, 2 (L 1) to 10,192 (L 200 Golden Boss, q 15,000). Max intermediate `679,459 × 100,000 ≈ 6.8×10¹⁰`, far below int64. Rounds half up, so the mean matches the reference float formula to within 0.5 gold per drop.
**Example:** L 50, `q_milli` 800 / 1,000 / 1,200 → 118 / 148 / 177 gold. L 1 always gives 2 (1.6–2.4 rounds to 2).

### F3: `luck_milli`

The luck_milli formula is defined as:

`member_luck_milli(m) = clamp( drop_luck_floor_milli + (drop_luck_span_milli × pa_m) div pa_max + rebirth_drop_milli[r_m] + (trait_mod_ppm(m, drop_rate) + trait_mod_ppm(m, rare_drop)) div 1000, 0, drop_luck_max_milli )` (`div` of the trait sum truncates toward zero)

`luck_milli(party) = ( Σ over the n party members alive at the kill of member_luck_milli ) div n`

`rebirth_drop_milli[r] = Σ over rebirth tiers t ≤ r of round(1000 × drop_rate_t)` (boot table, r = 0 … 5; tier 3 gives 50 today, so r ≥ 3 → 50)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| drop_luck_floor_milli | int | 0 – 1,000 (800 proposed) | data file (`config.csv`, new key) | Luck of a PA 0 member |
| drop_luck_span_milli | int | 0 – 1,000 (400 proposed) | data file (`config.csv`, new key) | Extra luck from PA 0 to PA `pa_max` |
| pa_m | int | 0 – 200 | calculated (CA/PA 9, true PA) | The member's potential |
| pa_max | int | 200 | data file (`config.csv`) | PA scale |
| r_m | int | 0 – 5 | calculated (Member model) | Rebirth tier |
| drop_rate_t | float | 0 – 1 | data file (`rebirth.csv` rewards) | Per-tier drop bonus; converted once at boot |
| trait_mod_ppm(m, k), k ∈ {drop_rate, rare_drop} | int | −130,000 – +750,000 summed (0 in MVP) | calculated (CA/PA 9) | Sum of the member's trait effects on `k`, in millionths (+0.10 → 100,000 → +100 milli); for a disciple it already includes `elder_mod_ppm(k)` (Rebirth R8, capped at `elder_buff_cap_ppm` 150,000 per key). Both keys are rare-drop luck (R4). Traits arrive in Vertical Slice; the clamp is this system's, as CA/PA requires of each consumer |
| drop_luck_max_milli | int | 1,000 – 2,000 (2,000) | data file (`config.csv`, new key) | Upper clamp of one member's luck; keeps F4's luck input ≤ 2,000 |
| n | int | 1 – 5 | calculated | Party members alive when the kill lands |

**Output Range:** 0 – `drop_luck_max_milli` (2,000). Without traits or Elders (MVP): 800 (all PA 0) to 1,250 (all PA 200 at rebirth ≥ 3); 1,000 for an average guild. With traits and Elders (Vertical Slice) the largest unclamped member value is 1,250 + 600 (`t_lucky` 180 + `t_fortune_child` 300 + `t_treasure_hunter` 120) + 300 (two Elder keys at the 150,000 cap) = 2,150, clamped to 2,000. Golden Boss rolls use 1,000 (R4). `n` is never 0, because a kill needs a living member.
**Example:** party of PA 40, 100, 160 at rebirth 0: 880 + 1,000 + 1,120 = 3,000, `div 3` = 1,000 (neutral). A solo PA 200 member at rebirth 3: 800 + 400 + 50 = 1,250. A PA 100 member at rebirth 0 with `t_lucky` (`drop_rate` +0.10, `rare_drop` +0.08; traits act hidden or revealed): 800 + 200 + 0 + (100,000 + 80,000) div 1000 = 1,180.
**Why centred.** The reference simulation was calibrated with no PA effect (`sim/hunt.py`). Centring at PA 100 keeps that calibration for an average guild while honouring §4.2. Luck only touches rare and epic rows, which carry about 13% of a normal kill's value, so the full 800–1,250 span moves total kill value by about −2.7% to +4%: a felt reason to value high-PA recruits, not a dominant one.

### F4: `effective_ppm`

The effective_ppm formula is defined as:

`effective_ppm(row) = min( 1,000,000, (drop_chance_ppm × luck_milli) div 1000 )` if the row is `equip_pool` with rarity `rare` or `epic`; otherwise `effective_ppm(row) = drop_chance_ppm`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| drop_chance_ppm | int | 1 – 1,000,000 | data file (`drop_tables`) | Tabled chance (validator: > 0) |
| luck_milli | int | 0 – 2,000 | calculated (F3) | Party luck |

**Output Range:** 0 – 1,000,000; passed to `chance_ppm` (RNG F6). The clamp is reached only by a row tabled above 800,000 ppm with maximum luck; no luck-affected row today exceeds 600,000 (Golden Boss rare), and those use luck 1,000. Max intermediate `10⁶ × 2,000 = 2×10⁹`.
**Example:** zone rare row 15,000 ppm, luck 1,250 → 18,750 ppm (1.875% per kill). Luck 800 → 12,000.

### F5: `sell_value`

The sell_value formula is defined as:

`sell_value(unit) = ( price × sell_ratio_milli + 500 ) div 1000`, where `price` = item `price` (equipment and consumables) or material `base_price`, and `sell_ratio_milli` = `equip_sell_milli` (equipment and consumables) or `mat_sell_milli` (materials)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| price | int | 0 – 10⁹ | data file (`items.price`, `materials.base_price`) | Whole-gold base value |
| equip_sell_milli | int | 0 – 1,000 (400 today) | data file (`sim_params.equip_sell_ratio` × 1000 at boot) | Share of price paid for equipment |
| mat_sell_milli | int | 0 – 1,000 (500 today) | data file (`sim_params.mat_sell_ratio` × 1000 at boot) | Share of price paid for materials |

**Output Range:** 0 to `price`. A ratio above 1,000 is rejected by the validator, so selling can never pay more than an item's buy price (no buy-and-sell loop at shops). This system sells only at hand-in (equipment nobody takes, and materials); storage sales are Gold economy's `sell_item`, which uses this formula. Specials have price 0 and so sell for 0.
**Example:** a tier-5 rare weapon (price 6,311) sells for `(6,311 × 400 + 500) div 1000 = 2,524`; one `mat_z05_1` (145) sells for 73.

### F6: bag capacity (pointer)

Owned by Zones and hunt (11, F4): `bag_capacity = bag_slots × n`, `bag_slots` 30 in `sim_params.csv`. This system supplies only the fill rate: about 1.455 units per normal kill with today's zone tables (F7), so a party fills its bag in about `20.6 × n` kills.

### F7: `expected_kill_value` (validation and balance only)

The expected_kill_value formula is defined as:

`E_gold(T, L) = Σ gold rows ppm/10⁶ × base_gold_milli[L]/1000 × (qmin+qmax)/2000`; `E_sale(T, L, luck) = Σ material rows ppm/10⁶ × (qmin+qmax)/2 × sell_value + Σ equip_pool rows effective_ppm/10⁶ × mean sell_value(pool)`; `E_units = Σ material/item rows ppm/10⁶ × (qmin+qmax)/2 + Σ equip_pool rows effective_ppm/10⁶`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| T | table id | 45 tables | data file | The loot table |
| L | int | 1 – 200 | calculated | Monster level |
| luck | int | 800 – 1,250 | calculated (F3) | Party luck |

**Output Range:** used by `balance_sim`, the validator and AC-20; never at runtime (it is float). It ignores auto-equip, which removes some equipment from sale.
**Example:** `drop_zone_05`, L 45, luck 1,000: `E_gold` 131.7, `E_sale` 202.1 (materials 157.0, rare gear 45.1), `E_units` 1.455. Luck 1,200 raises `E_sale` to 211.1. `loot_gb_05` at L 50: `E_gold` 1,848, materials and gear about 6,895 gold of value going to storage, about 25.8 units.

*Lens applied:* systems-designer and economy-designer, Section D checks (in-session). Boundaries worked: L 1 (gold 2), L 200 (10,192 max), luck 0/2,000 clamps, ratio 0 (nothing sold for gold; legal) and > 1,000 (rejected), `bag_slots` 1. Feedback loop: PA → luck → rare gear → stronger member is a positive loop, damped by the small span (F3) and by auto-equip, which only accepts items that dominate what is worn. Faucets here (drop gold, sales) are balanced by Gold economy's sinks (§19), not by this system.

## Edge Cases

### A. Rolls and tables
- **If a loot table has a row with `drop_chance_ppm` 1,000,000**: it always hits and still consumes its draw (R3a), so tuning a row to certain never shifts later draws.
- **If a live `equip_pool` row's pool is empty** (no live equipment of that rarity in range, for example after retiring a tier): the validator fails the build (extends today's check to liveness). At runtime this cannot occur; if it does, `choice` on an empty list fails loudly (RNG R9) and the tick is discarded.
- **If a monster's `drop_table` or a boss's `loot_table` names no group**: validator error (exists today).
- **If a Wave 2 item appears in a Wave 1 table**: validator F3 error (Data layer AC-17).
- **If `qty_min > qty_max`, a material/item quantity is not an integer, or an `equip_pool` row has quantity other than 1**: validator error.
- **If the same item drops twice in one kill** (two rows reference it): both are added; rows are independent (R2).
- **If the luck of a party changes during a trip** (a member dies): luck is computed per kill from members alive at that kill (F3), so a death lowers or raises the next kills' odds. This is intended: it is cheap and correct.

### B. Bag and hand-in
- **If the bag is exactly at capacity after a kill**: the trip ends before the next encounter. If it is one below, one more kill is made and may overshoot (R5).
- **If the party wipes or flees**: the bag comes home in full (R5).
- **If two equipment units in one hand-in suit the same member and slot**: they are processed in item `uid` order; the first may be equipped, then the second is compared with the newly equipped item and equipped only if it dominates it; whichever is not worn is sold (or goes to another candidate). Two items that do not dominate each other: the first one processed stays.
- **If an item suits two members equally** (both empty slots, or current items of the same `level_req`): the lower `member_id` gets it. Deterministic, and the player can re-award later.
- **If the candidate is the member whose slot holds an enhanced item**: not a candidate (R6); the unit goes to the next candidate or is sold. The player sees it in the hand-in summary and can award a better item directly.
- **If a member leaves the party or the guild between the kill and the hand-in**: only members present at hand-in are candidates. Income is credited to the party as it is at hand-in; Gold economy owns the split (OQ-3).
- **If a hand-in sells nothing and finds no gold** (empty bag after a `lost` on the first fight): a 2601 with zeros is still emitted, so the UI can show the return.

### C. Storage and award
- **If two award commands in one tick target the last unit of an item**: the first in command order succeeds; the second is refused with reason 2.
- **If an award targets a member who is out hunting, in a raid or training**: refused with reason 7 (Member model R6 rule 6); the unit stays in storage and the player can award it when the member is home.
- **If the award displaces an enhanced item**: the displaced instance goes to storage with its level kept (R7), never sold.
- **If storage would exceed int64** (9.2×10¹⁸ of one key): impossible in play (a guild gains well under 10⁷ materials per day). `give` fails loudly rather than wrap.
- **If a stored item has been retired**: it can still be awarded and used (R7). It is never dropped again.
- **If a save from before storage existed is loaded**: storage starts empty. Local save (6) owns the migration (S8).
- **If a consumer calls `take` for more than storage holds**: refused, nothing changes (R7).

### D. Determinism and degenerate strategies
- **Save-scumming a drop**: reloading before a kill gives the same dice. Changing the party changes luck (an input), so a player could reload and swap in a high-PA member before a known epic. Accepted, consistent with RNG R5. The gain is bounded by the luck span (F3).
- **Farming low zones for sale gold**: drop gold and sale value both scale with level (F1, material prices), and the XP penalty for over-levelled hunting is Hunt's, so low-zone farming pays less per hour. No unbounded loop exists in this system.
- **Buy-and-sell loop**: impossible because sell value ≤ price (F5). Gold economy's `buy_item` burns the full price and `sell_item` pays at most F5, so buying into storage and selling back always loses gold.
- **Double payment for materials**: a material is paid once, at hand-in (`loot_handover`), and can never be sold out of storage (R13), so it cannot be paid twice (Gold economy OQ-15).
- **Award ping-pong** (awarding an item back and forth): each award only moves units between storage and members; no value is created.

*Lens applied:* systems-designer, Section E checks over C and D (in-session).

## Dependencies

### Upstream (this system depends on)

| System | Hard/Soft | Interface | Status |
|---|---|---|---|
| Deterministic RNG (2) | Hard | Domain 2 `loot`; `derive`, `chance_ppm` (F6), `randint` (F4), `choice` (F5); key rules R5–R7 | Designed |
| Data layer and content pipeline (3) | Hard | Typed `items`, `materials`, `drop_tables` (groups in `uid` order, `drop_chance_ppm`), liveness (F2), `config`/`sim_params`/`rebirth` values | Designed |
| Sim core and tick loop (1) | Hard | P4 handler, P1 command handling, `ctx.emit` | Designed |
| Event bus and history log (42) | Hard | `register_type` for 2601–2606, ring budget | Designed |
| Schools and school change (20) | Hard | R7 equip eligibility | Designed |
| Member model (8) | Hard (interface) | Fields, slots (R5) and `equip`/`unequip` with displaced items to storage (R6), `inventory[]` | Designed. Member model also depends on this system; the cycle is broken by an injected interface |
| Gold economy (27) | Hard | Settlement credits `hunt_gold` / `loot_handover`; `boss_reward` via Golden Boss; `sell_item` / `buy_item` on storage (Gold economy R3, R15) | Designed |
| Command layer (5) | Hard (interface) | Carries `award_item` (owned here, R8) | Designed |
| CA/PA and traits (9) | Soft | True `pa`; `trait_mod_ppm(drop_rate)` and `trait_mod_ppm(rare_drop)` per member | Designed |
| Rebirth and Ascension (23) | Soft | `drop_rate` reward values; Elder `drop_rate`/`rare_drop` buffs via `trait_mod_ppm` (R8) | Designed |

### Downstream (systems that depend on this one)

| System | Hard/Soft | What it uses |
|---|---|---|
| Zones and hunt trips (11) | Hard | Roll per kill (key F9), `hand_in` at settlement (R8) |
| Golden Boss and guild raid (14) | Hard | `roll_guild_loot`, storage (`item_summon_horn`) |
| Offline progress (31) | Hard | Pure roll and `hand_in` (R12) |
| Member model (8) | Hard | Item definitions, slot meaning (R1) |
| Gold economy (27) | Hard | Loot income and guild loot credits; item prices for shops |
| Guild and buildings (30) | Hard | Storage `take` for material costs |
| Crafting (28), Enhancement (24), Market (29) | Hard | Item definitions, storage |
| Party (13), Recruitment (15), Schools (20), CA/PA (9) | Soft | Their special items in storage |
| Endless Tower (19) | Hard | Source tag 2 (R3); `roll_guild_loot_keyed` with `rolls` (R9a) |
| CA/PA and traits (9) | Soft | Event 2606 `rare_haul` (`event:rare_drop` reveal trigger) |
| Quests (25), Analytics (37), AI text (36) | Soft | Events 2601–2606 |
| Guild screens (39), Realtime view (38) | Soft | Storage read model, events |
| Local save (6) | Hard | Storage and bag serializers |
| Dev tooling and parity harness (43) | Hard | Parity vectors for F1–F5 and R3a |

## Tuning Knobs

| Knob | Source | Today | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `drop_chance_ppm` per row | `drop_tables.csv` | 15,000–1,000,000 | 1 – 1,000,000 | Gold inflation; rare gear stops feeling rare | Hunting feels empty; buildings starve for materials | Luck (F4) for rare/epic rows |
| `qty_min`/`qty_max` per row | `drop_tables.csv` | 0.8–1.2 gold; 1–20 units | gold 0–100; units 0–1,000 | Bags fill in a few kills (trips too short) | Little income per kill | `bag_slots` |
| `base_gold_coef` | `config.csv` | 2.0 | 0.5 – 10 | Gold inflation (§18.3) | Sinks unaffordable | Gold economy income target (§19.1) |
| `base_gold_exp` | `config.csv` | 1.1 | 0.9 – 1.5 | Late game gold explodes | Late zones not worth it | Material prices, §19 sinks |
| `bag_slots` | `sim_params.csv` | 30 | — | Owned by Zones and hunt (11, F4); pointed to, not duplicated | | Drop quantities here set how fast it fills |
| `mat_sell_ratio` | `sim_params.csv` | 0.5 | 0 – 1.0 | Materials dominate income | Hunting pays only drop gold | Gold economy faucet budget |
| `equip_sell_ratio` | `sim_params.csv` | 0.4 | 0 – 1.0 | Selling gear beats using it | Rare drops feel worthless when not equipped | Market prices (VS) |
| `drop_luck_floor_milli` | `config.csv` (new) | 800 | 500 – 1,000 | Low-PA members drop as well as high (PA meaningless here) | Low-PA guilds feel punished | `drop_luck_span_milli`: floor + span/2 should stay 1,000 to keep the calibration neutral |
| `drop_luck_span_milli` | `config.csv` (new) | 400 | 0 – 1,000 | High-PA parties dominate rare drops | PA effect invisible (0 turns luck off) | Floor (above) |
| `drop_rate` per rebirth tier | `rebirth.csv` | 0.05 at tier 3 | 0 – 0.5 | Rebirthed parties flood rare gear | Rebirth reward not felt | Owned by Rebirth (23); pointed to, not duplicated |
| `drop_luck_max_milli` | `config.csv` (new) | 2,000 | 1,000 – 2,000 | (above 2,000 breaks F4's stated bound) | Lucky traits and Elders stop mattering | F3, F4 |
| `loot_rolls_max` | `config.csv` (new) | 8 | 1 – 16 | One guild event pours many tables into storage | Endless Tower multi-roll floors fail | R9a, Endless Tower F4 |

Item `price`, material `base_price`, rarity and stats are content values, tuned per row. Auto-equip compares stats by dominance (R6), so a stat change can change which drops are worn; price changes only affect gold.

## Visual/Audio Requirements

No art bible exists (`design/art/art-bible.md` absent); this section is drafted from the GDD and the art plan (§12.4: AI-generated pixel art, a 20-icon art spike).
- **Icons:** every item and material needs an icon. Rarity must be readable without colour alone: common plain frame, rare frame plus one corner mark, epic frame plus a glow animation (two frames). 945 equipment rows share icons by (slot, family, tier band) rather than one per row; this is an asset-budget call for `/asset-spec`.
- **Hand-in:** a short "bag empties" animation at the guild gate, a gold "+N" float, and a small stack-icon pop into the storage building. One sound for the sale (coins) and one for storage (crate).
- **Epic drop:** a bright beam over the party in the realtime view, plus a distinct chime; it is the only per-drop effect, because rare drops are too frequent to announce.
- **Award:** the member briefly shows the new item icon above their head; a soft "gift" sound.
- **Audio priority:** the epic chime is above ambient hunt sounds and below boss warnings.

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:items-and-loot-tables` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

- **Hand-in is a beat, not a menu.** The return should take under 2 seconds of animation and require no input; the summary is optional to open.
- **Award is instant.** From the award tap to the item visibly worn: one tick (≤ 100 ms simulated) plus the animation, no confirmation dialog for awards that cannot fail; a single confirm only when the award displaces an enhanced item.
- **Upgrades are noticeable.** An `item_auto_equipped` should flash the member's portrait in the roster, so the player connects "the party came home" with "that member got stronger".

## UI Requirements

- **Guild storage screen** (Guild screens 39): grid of stored keys with icon, count and enhancement level; filters by kind (equipment, materials, consumables, specials) and rarity; sorted by item `uid` by default. Selecting an equipment item shows which members can use it (Schools R7 and level) and the stat difference against what each wears.
- **Award flow**: storage item → member picker (eligible members first, ineligible greyed with the refusal reason) → tap to award. Refusals (R8 reasons) show a localised message.
- **Hand-in summary**: per return, gold earned, units sold, materials stored, auto-equips; reachable from the guild log.
- **Member detail**: equipped item per slot with enhancement level.
- **Accessibility**: rarity always shown by frame shape/mark and by text, never colour alone; counts in localised number format; all strings from `i18n/names_items_*.csv` (1,083 names today).

> **📌 UX Flag — Items and loot tables**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the guild storage screen, the award flow and the hand-in summary **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This document references | Target GDD | Specific element referenced | Nature |
|---|---|---|---|
| Loot domain, event keys, draw order, chance/randint/choice | `deterministic-rng.md` | R3–R7, R10, F4, F5, F6; domain 2 `loot` | Rule dependency |
| Typed tables, `drop_chance_ppm`, `uid` order, liveness | `data-layer-and-content-pipeline.md` | R3–R6, F2, F3, OQ-1 | Data dependency |
| P4 economy phase, P1 commands, `ctx.emit` | `sim-core-and-tick-loop.md` | R2, R4 | Rule dependency |
| Type block 2600–2699, logged types, ring budget | `event-bus-and-history-log.md` | R3, R3a, F4 | Rule dependency |
| Equip eligibility; gear moved to storage; `item_school_token` | `schools-and-school-change.md` | R7, R3/R5 gear return, OQ-2 | Rule dependency. **Discrepancy:** Schools lists guild storage under Guild and buildings (30) and assumes a storage cap ("If guild storage is full…"). Per the systems index, storage is owned here and is uncapped (R7), so Schools' over-cap case never arises. To reconcile in the next consistency check |
| `award` call pattern, PA and rebirth tables | `xp-and-level-pacing-curve.md` | R2 (boot-time integer tables) | Pattern precedent only |
| Award command | `command-layer.md` | MVP command vocabulary | Command layer carries `award_item` as defined in R8 (owner) |
| Guild loot keyed roll | `endless-tower.md` | R9, F4, OQ-5 | Interface provided (R9a `roll_guild_loot_keyed`) |
| `drop_rate` / `rare_drop` Elder buffs | `rebirth-and-ascension.md` | R8, F3 | Formula input (F3), via CA/PA's `trait_mod_ppm` |
| Slots, `equip`/`unequip`, displaced gear to storage, `inventory[]` | `member-model.md` | R5, R6 | Interface dependency (OQ-2) |
| Encounter key, bag capacity, settlement, offline rates | `zones-grounds-monsters-and-hunt-trips.md` | F9, F4, R8, F10 | Interface dependency. Conformed (consistency-check 2026-11-16): Zones R8 calls R6 and owns the income split; Zones R15 returns per-trip bags for Offline's rotation (OQ-6, OQ-11 resolved) |
| Entry types `hunt_gold`, `loot_handover`, `boss_reward`; `sell_item`/`buy_item`; OQ-15 | `gold-economy.md` | R3, R15, OQ-9, OQ-15 | Interface dependency. **Discrepancy:** `sell_item` includes materials (OQ-3) |
| Storage `count`/`take`/`give`, over-cap returns | `guild-and-buildings.md` | R2, R3, Dependencies | Interface dependency. Storage is uncapped here, so its over-cap assumption always holds |
| `pa`, `trait_mod_ppm(drop_rate / rare_drop)`, rare-drop reveal trigger, lens in storage | `ca-pa-and-traits.md` | R-trait mods, OQ-12 | Formula input (F3) and event 2606 (answers CA/PA OQ-12) |

## Acceptance Criteria

Story types: AC-1 to AC-23 and AC-26 to AC-28 are **Logic/Integration** (automated tests, `tests/unit/items_and_loot/` and the Python reference tests). AC-24 is **Integration**. AC-25 and AC-29 are **UI** (retained screenshot in `production/qa/evidence/`).

**Rolls (R2, R3, R3a, F2, F4)**
- **AC-1 (R3a draw order)**: **GIVEN** `drop_zone_01` and the loot generator built from `EventRng.from_raw` with known raw values, **WHEN** one kill at L 5 with luck 1,000 is rolled, **THEN** exactly one `chance_ppm` draw is consumed per row in `uid` order, plus one `randint` for each hit gold/material row and one `choice` for a hit `equip_pool` row, and `draws_consumed` equals that count.
- **AC-2 (R3a extremes)**: **GIVEN** a fixture table whose first row is set to 0 ppm, then to 1,000,000 ppm, **WHEN** the same raw sequence is rolled, **THEN** both rolls consume one draw for that row, and every later row's outcome is identical in both.
- **AC-3 (R3 keys)**: **GIVEN** a hunt kill of party 2 with key `[2, 3, 12]`, a raid with key `[0, 1, 3]` and an Endless Tower floor with key `[0, 2, 3, 12]`, **WHEN** all three are derived in domain 2, **THEN** the three event seeds differ pairwise, and repeating each derive gives bit-identical rolls. **GIVEN** a call to `roll_guild_loot_keyed` with key `[2, 3, 12]` (no leading 0), **THEN** it fails loudly.
- **AC-4 (R2 independence)**: **GIVEN** a fixture table with two rows at 1,000,000 ppm referencing the same material with qty 1–1, **WHEN** a kill is rolled, **THEN** the bag holds 2 units of it.
- **AC-5 (F2)**: **GIVEN** L 50 and `q_milli` forced to 800, 1,000 and 1,200, **THEN** `gold_drop` is 118, 148 and 177. **GIVEN** L 1 with any `q_milli` in 800–1,200, **THEN** it is 2. **GIVEN** L 200 and `q_milli` 15,000, **THEN** it is 10,192.
- **AC-6 (F4)**: **GIVEN** a rare `equip_pool` row of 15,000 ppm, **WHEN** luck is 1,250 / 1,000 / 800, **THEN** `effective_ppm` is 18,750 / 15,000 / 12,000. **GIVEN** a material row of 550,000 ppm and luck 1,250, **THEN** it stays 550,000. **GIVEN** 900,000 ppm rare and luck 2,000, **THEN** it is 1,000,000.
- **AC-7 (R2 pool)**: **GIVEN** `drop_zone_05`'s rare row (L 40–50), **WHEN** the pool is built, **THEN** it contains every live rare equipment row with `level_req` 40–50 and nothing else, in ascending `uid` order, and a fixture that retires one of them removes it from the pool.

**Luck (R4, F3)**
- **AC-8**: **GIVEN** a party with true PA 40, 100, 160 at rebirth 0, **THEN** `luck_milli` is 1,000. **GIVEN** a solo PA 200 member at rebirth 3, **THEN** 1,250. **GIVEN** a solo PA 0 member at rebirth 0, **THEN** 800. **GIVEN** a solo PA 100 member at rebirth 0 with `t_lucky`, **THEN** 1,180. **GIVEN** a solo PA 200 member at rebirth 3 with `t_lucky`, `t_fortune_child`, `t_treasure_hunter` and both Elder keys at +150,000, **THEN** 2,000 (clamped from 2,150). **GIVEN** a solo PA 0 member at rebirth 0 with `t_unlucky` (−80,000, −50,000), **THEN** 670.
- **AC-9**: **GIVEN** a party of three where one member dies mid-fight before the kill, **WHEN** the kill is rolled, **THEN** luck averages only the two living members.
- **AC-10**: **GIVEN** a Golden Boss roll for a guild whose members are all PA 200, **THEN** `luck_milli` is 1,000.
- **AC-11 (R10, RNG R10)**: **GIVEN** Premium and Free entitlement snapshots with identical guilds and seed, **WHEN** 10,000 kills are rolled, **THEN** the drops are identical.

**Bag (R5)**
- **AC-12**: **GIVEN** a roll result of 1 gold row, 2 material units and 1 equipment unit, **WHEN** it is added to a bag, **THEN** the bag's slot count rises by exactly 3 and its gold accumulator by the gold amount (capacity itself is tested by Zones and hunt).
- **AC-13**: **GIVEN** a trip that ends `wiped` with 40 units and 500 gold in the bag, **WHEN** the party is handed in, **THEN** all 40 units are resolved and the trip income includes the 500 gold.
- **AC-14 (save)**: **GIVEN** a trip saved mid-way with a non-empty bag, **WHEN** it is reloaded and continued, **THEN** the hand-in result equals that of the uninterrupted run (same seed).

**Hand-in (R6, F5)**
- **AC-15 (auto-equip)**: **GIVEN** a party where member 4 (school `kim_2`, level 45) wears the common tier-5 sword (`atk=337`) at enhancement 0, and the bag holds `eq_wpn_sword_05_r` (`atk=439`, dominates), **WHEN** hand-in runs, **THEN** member 4 wears the rare sword, the common sword is in guild storage at enhancement 0, `sale_gold` does not include it, and a 2605 event names both items.
- **AC-16 (enhanced protected)**: **GIVEN** the same but member 4's sword is at enhancement 3, **THEN** the rare sword is not equipped on member 4; it goes to the next candidate or is sold, and member 4's sword is unchanged.
- **AC-17 (tie and dominance)**: **GIVEN** two members with the same school, level and empty weapon slot, **THEN** the lower `member_id` receives the weapon. **GIVEN** a member wearing armour `def=8;hp=27` and a drop `def=9;hp=26`, **THEN** it is not auto-equipped (no dominance) and is sold.
- **AC-18 (F5)**: **GIVEN** a bag with one tier-5 rare weapon (price 6,311) that no one can use and three `mat_z05_1`, **WHEN** hand-in runs, **THEN** income from sales is 2,524 + 3 × 73 = 2,743, storage gains 3 `mat_z05_1`, and one 2601 event carries `b` = total income, `c` = 1, `d` = 3.
- **AC-19 (Gold economy integration)**: **GIVEN** a bag with 500 drop gold and the AC-18 contents, **WHEN** settlement runs, **THEN** Gold economy receives `drop_gold` 500 as `hunt_gold` and `sale_gold` 2,743 as `loot_handover` for the roster, the ledger's minted total rises by exactly 3,243, and this system writes no balance itself.
- **AC-19b (storage sale)**: **GIVEN** storage with 3 `mat_z05_1` and 1 `eq_wpn_sword_05_c`, **WHEN** the player's `sell_item` asks to take the material, **THEN** it is refused and storage is unchanged; **WHEN** it asks for the sword, **THEN** the sword is taken and its F5 value (1,010) is the amount Gold economy credits.

**Balance (F7)**
- **AC-20 (statistical)**: **GIVEN** 100,000 seeded kills on `drop_zone_05` at L 45 with luck 1,000, **THEN** mean gold is 131.7 ± 1%, mean units 1.455 ± 1%, and mean sale value 202.1 ± 2%.
- **AC-21 (validator)**: **GIVEN** fixtures with an `equip_pool` row of quantity 2, a material quantity of 1.5, a sell ratio of 1.01, and a live `equip_pool` whose pool is empty, **WHEN** the validator runs, **THEN** each exits 1 naming the row.
- **AC-22 (parity)**: **GIVEN** the default data, **WHEN** the Python reference and the engine port build F1, the milli conversions of F2/F5 and `rebirth_drop_milli`, and roll the committed vector set of kills, **THEN** every table cell and every roll is identical.

**Storage and award (R7, R8, R9, R9a)**
- **AC-23 (award)**: **GIVEN** storage holding one epic armour of class `heavy` and a `kim_1` member (heavy armour school) of sufficient level wearing an armour at enhancement 2, **WHEN** `award_item` is applied, **THEN** the member wears the epic armour, storage holds the old armour at enhancement 2 and no epic, and a logged 2603 event has `subject_slot` 1. **GIVEN** a second identical command in the same tick, **THEN** it is refused with reason 2 and a 2604 event.
- **AC-26 (refusals)**: **GIVEN** each R8 refusal condition in turn (unknown member, missing key, a material, an `item_summon_horn`, a wrong-class armour, a level-too-low item, a valid weapon for a member in `hunting`), **THEN** each is refused with reasons 1, 2, 3, 3, 4, 5, 7, a 2604 event, and nothing changes.
- **AC-27 (Golden Boss)**: **GIVEN** `loot_gb_05` won at L 50, **WHEN** `roll_guild_loot` runs, **THEN** every rolled item and material is in storage, nothing is sold or equipped, the rolled gold is returned to Golden Boss (no balance written here), and an epic unit emits one 2602 with `a` = 0 and `c` = 1. **GIVEN** the same table, level and raid ordinal `r`, **WHEN** `roll_guild_loot_keyed([0, 1, r], loot_gb_05, 50, 1)` runs instead, **THEN** storage, returned gold and draws are bit-identical to `roll_guild_loot(r, loot_gb_05, 50)`.
- **AC-30 (R9a keyed, Endless Tower)**: **GIVEN** `drop_zone_10`, level 37 and key `[0, 2, 4, 37]`, **WHEN** `roll_guild_loot_keyed` runs with `rolls = 2`, **THEN** one generator is derived, the draws consumed equal pass 1 plus pass 2 each by R3a (pass 2 continues the same stream), all units are in storage, the returned gold is the sum of both passes' gold rows, any epic emits 2602 with `a` = 0 and `c` = 2, and `rolls = 0` or `rolls = 9` fails loudly. **GIVEN** a hunt hand-in containing an epic, **THEN** its 2602 has `c` = 0.
- **AC-28 (`take`)**: **GIVEN** storage with 3 `mat_z04_1`, **WHEN** Guild and buildings calls `take({mat_z04_1: 20})`, **THEN** it returns false and storage still holds 3. **GIVEN** `take({mat_z04_1: 2, mat_z04_2: 1})` with no `mat_z04_2`, **THEN** it returns false and `mat_z04_1` is still 3.

**Offline, events and UI**
- **AC-24 (R12, Integration)**: **GIVEN** a 5-member party hunting 24 hours, **WHEN** the same seed is run exactly and with the offline sampled driver, **THEN** gold income, materials stored and equipment sold are each within ±3% of the exact run, and every unit went through `hand_in`.
- **AC-29 (R10, events)**: **GIVEN** the Event bus at boot, **WHEN** this system registers its types, **THEN** 2601–2606 register inside block 2600–2699 with the flags in R10 (2606 `rare_haul`: not logged, not milestone, no subject slot, `ring_per_day` 0) and `seal()` succeeds; a build that omits 2606 fails this test. **GIVEN** a hand-in for a 3-member roster whose bag holds 1 rare and 1 epic unit, **THEN** three 2606 events are emitted, one per member, each with `b` = 2 and `c` = 2; **GIVEN** a bag with only commons, **THEN** none.
- **AC-25 (UI)**: **GIVEN** the storage screen with at least one item of each rarity, **THEN** a retained screenshot shows rarity distinguishable by frame mark and text in greyscale.

*Lens applied:* qa-lead (in-session). Coverage: every core rule (R2–R12) and formula (F1–F5) has a criterion; F1 is covered by AC-5 and AC-22; F7 by AC-20. Not automatable: Game Feel targets (playtest).

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Retrofit changes to `sim/hunt.py`** (implementation story): integer gold (F1, F2) and sale (F5); RNG per-event loot keys (R3, R3a) replacing the shared generator; luck (F3, F4) — today `roll_drops` has none; `suited_first` auto-equip (R6) — today every equipment drop is sold; materials into storage (R6); Golden Boss loot into storage (R9a) — `raid.py` rolls no loot today; validator rules of AC-21; new `config.csv` keys `drop_luck_floor_milli`, `drop_luck_span_milli`. Re-run `balance_sim` and `calibrate` after: auto-equip of rare gear raises member power and lowers sale income slightly | Implementation (Hunt 11 + this system), Dev tooling (43) | Before Hunt's implementation story |
| OQ-2 | **Member model (8) reconciliation.** Conformed to its R5 slots and R6 `equip`/`unequip` (displaced items to storage; equip refused while `hunting`, `boss_raid`, `away`, `dead`, `training`). Still PROVISIONAL: whether settlement (Zones R6 step 10, `selling`) is a state in which `equip` is allowed, so hand-in auto-equip works; Resolved 2026-11-16: `inventory[]` is owned here and uncapped (R8 reason 6 reserved). Member model lists `inventory[]` as "the carry bag"; here the hunt bag is the trip's (Zones R6), and `inventory[]` holds only awarded consumables and member-held specials | Member model + this system | Consistency check |
| OQ-3 | **Gold economy (27) reconciliation.** (a) Answer to Gold OQ-15: materials are paid once at hand-in and are never sellable from storage; Gold R15 `sell_item` should drop its material case. (b) Gold economy's Pointed-to list names Zones and hunt as owner of `base_gold_coef`/`base_gold_exp`; Zones says drops are Items'. This GDD owns them (F1). (c) Open: should the guild fund, not a mint, pay members for handed-in materials once tax and market land (VS)? | Gold economy + this system | Consistency check |
| OQ-4 | Should guild storage ever have a cap (a storage building)? If yes, Guild and buildings owns it and over-cap must never destroy items (Schools edge case) | Guild and buildings (30) | Vertical Slice |
| OQ-5 | Add an `items.holder` column (`member` / `guild`) to replace the R9 effect-key list. This is a schema change, so it is not made here | Data layer (3) | With Data layer OQ-1 migration |
| OQ-6 | **RESOLVED (consistency-check 2026-11-16):** Offline progress F4 does not scale bags; it hands in whole sampled bags in rotation (`bag[j mod S]`), so no rare unit is fractional. AC-24's ±3% is checked by Offline AC-6 | Offline | Closed |
| OQ-7 | Other `loot_rule` values (GDD §6.12 "chỉnh được theo bang"), e.g. "rare and above to storage" so the guild master can award hunt gear. Vertical Slice | Party (13), this system | Vertical Slice |
| OQ-8 | Source and rarity of `item_school_token` (Schools OQ-2): add it to Golden Boss tables, to an Academy recipe, or both? | Schools (20), Crafting (28), this system | When Crafting is designed |
| OQ-9 | **Feasibility not checked against the pinned engine.** NOT SOURCEABLE: no `scripting.md` or `core.md` under `docs/engine-reference/godot/modules/`. Integer and boot-table design avoids float parity risk; the CSV float conversion of `qty_*` and sell ratios (round to thousandths) is the only port risk, covered by AC-22 | technical-director | Before Architecture gate |
| OQ-10 | Does an enhanced item's sell value or award desirability depend on its enhancement level (Enhancement 24)? Today F5 ignores enhancement and auto-equip never displaces enhanced gear | Enhancement (24) | Vertical Slice |
| OQ-11 | **RESOLVED (consistency-check 2026-11-16):** Zones R8 calls `hand_in` (R6) and owns the split of the returned income; `hand_in` returns totals and credits nothing (R6 step 4). Zones R15 now returns per-trip bags, and gold offline comes only through the handed-in bags (Zones F10 no longer scales gold) | Zones and hunt + this system | Closed |
| OQ-12 | **Conformed (Golden Boss 14 designed):** owns `raid_ordinal` and calls `roll_guild_loot` once per won raid (and per resolved backlog boss); a lost raid drops nothing | Golden Boss | When Golden Boss is designed |
| OQ-13 | **Conformed (Command layer 5 designed; it mirrors owners):** carries `award_item(member_id, content_id, enhance_level)` to P1 | Command layer | When Command layer is finished |
