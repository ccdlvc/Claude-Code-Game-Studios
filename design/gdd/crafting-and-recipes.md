# Crafting and Recipes

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: design-system skill (autonomous batch run) for the user
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet). Serves JX1_Tycoon_GDD.md §1 (the guild loop's "bang bán/chế tạo/nâng cấp" step), §7 (Thiết Tượng Phô, Châu Bảo Các, Dược Quán), §17.1 (`recipes.csv`) and §19.4 ("Chế tạo: công thức tốn vàng + nguyên liệu")

## Summary

Crafting turns the materials that members bring home into gear, potions, food, feasts, brews and the two craft-only specials, at the guild's own workshops. The bang chủ orders a recipe and a quantity, pays gold from the guild fund and materials from guild storage up front, and the finished units land in storage one by one, ready for the designated award. Without it, stored materials can only pay for buildings, and the guild has no cheaper source of supplies than buying them at full shop price.

> **Quick reference** — Layer: `Feature` · Priority: `Vertical Slice` · Key deps: `Items and loot tables, Gold economy, Guild and buildings, Data layer and content pipeline, Command layer, Sim core and tick loop, Event bus and history log, Local save and migration` (Deterministic RNG: reserved domain, not drawn from in Vertical Slice)

## Overview

**Data layer.** Crafting is a small production system inside the headless simulation. It owns the 408 rows of `data/recipes.csv`: each row names one output item, the building that makes it, the building level it needs, a per-unit list of materials, a per-unit gold cost and a per-unit time. It also owns one craft queue per crafting building: one order in progress plus up to `craft_queue_max` waiting orders. The seven crafting buildings and their recipe counts are Thiết Tượng Phô (`bld_smith`, 273 weapon and armour recipes), Châu Bảo Các (`bld_jeweler`, 42 accessories), Dược Quán (`bld_alchemy`, 42 potions), Thiện Đường (`bld_restaurant`, 7 foods and 21 feasts), Tửu Lâu (`bld_tavern`, 21 brews), Linh Miếu (`bld_shrine`, the rebirth pill) and Luyện Khí Đài (`bld_enhance`, the Enhancement Ward). Crafting reads the building's effective level and craft speed from Guild and buildings (30), takes gold from the fund through Gold economy (27) as a `craft_cost` burn, and takes and gives units through Items and loot (26) guild storage. It is fully deterministic and draws no random numbers.

**Player impact.** Crafting is the guild's supply line. A haul of river-reed materials is otherwise only good for building costs, because materials can never be sold from storage (Items and loot R13). Crafting converts them, plus a gold fee of about half the item's shop price, into the exact things the bang chủ wants to hand out: a weapon for a new recruit, twenty potions before a boss, a feast for the hunting party. It is also the only source of the Enhancement Ward (Bùa Hộ Cường, GDD §19.3: "chỉ chế tạo, không bán") and of the rebirth pill. Upgrading a workshop unlocks higher-tier recipes and crafts faster, which gives the building track (30) a visible payoff.

This system does **not** set item prices or stats (Items and loot 26), shop sales to members (Gold economy 27 R7), building levels or effects (Guild and buildings 30), or what the Ward does at the forge (Equipment enhancement 24). It does not decide which member gets a crafted unit; the designated award does (Items and loot R8).

## Player Fantasy

**Framing:** Both. The player acts directly (choosing what to craft and in what quantity), and the infrastructure (queues, timers, storage) runs without attention, including offline.

*Specialist step (creative-director lens) applied in this session; no pillars exist, so each framing is anchored to a JX1_Tycoon_GDD.md section instead of a quoted pillar.*

1. **"Nothing the guild brings home is wasted."** (Chosen.) Anchor: §1, "thành viên đi săn → mang tài nguyên về → bang bán/chế tạo/nâng cấp → thành viên mạnh hơn". *The moment:* the bang chủ opens storage after a night away, sees 140 river-reed fibres, taps Dược Quán and queues 20 tier-5 potions; by lunch they are in storage and the healer who keeps dying gets ten of them. *Asks of the design:* a clear view of which recipes the stored materials can pay for right now (UI Requirements 2), and output that goes straight to storage and the award.
2. **"The workshop grows with the guild."** Anchor: §7, the workshops as named buildings. *The moment:* Thiết Tượng Phô reaches level 6 and tier-12 blades appear in the recipe list, each crafted 48% faster than at level 1. *Asks:* tier unlocks and speed shown on the building upgrade preview (UI Requirements 4).
3. **"The ward is earned, not bought."** Anchor: §19.3 and §19 intro ("không ép mua bằng tiền thật"). *The moment:* after weeks of hoarding zone-6 ore, the guild crafts its first Bùa Hộ Cường and risks a +11 attempt. *Asks:* the Ward stays craft-only, with no Linh Bảo or shop path (Core Rules R9).

Framing 1 is the primary fantasy because it is the step of the core loop this system owns; 2 and 3 are secondary moments it must also deliver.

## Detailed Design

*Lenses applied before drafting (Section C, routing row "Economy, loot, crafting"):*

- **economy-designer (primary).** Crafting is a sink of both gold and materials and a faucet of items. The materials it consumes are already paid for at hand-in, so the danger is a loop that turns them into gold a second time: craft, then sell the product from storage. Today 405 of the 408 recipes cost less gold than their product's sell value (`recipes.gold` ≈ 35% of price for gear, potions as low as 14.5%; `sell_value` = 40% of price), so craft-and-sell is a materials-to-gold faucet that undoes Items and loot R13. Warning: crafting must cost more gold than the product sells for. Second warning: crafting at a fraction of the shop price is the intended dominant purchase for *guild* supplies; it must not become cheaper for members than buying in their own shops, and it is not, because members never craft.
- **systems-designer (supporting).** Integers only (Sim core R13): times become ticks, `craft_speed_mult` becomes milli at boot. Pay at order, like a build (Guild and buildings R2), so a queued order never stalls. Every order needs a defined end state across an offline gap; units complete at anchored deadline ticks that Offline progress (31) can cross. Gate and speed must be read through Guild and buildings' queries, never from `buildings.csv`.
- **game-designer (supporting).** The decisions are which recipe, how many, and which workshop's queue to fill first. What the player cannot do: craft with member gold, craft above the workshop's level, speed up a craft, or get a random better result. Cancellation is the open usability gap (see R6).

Two tensions were settled in this autonomous run (decision log, 2026-11-16): the craft gold ratio (economy-designer vs GDD §19.4's "~30%", OQ-1 — **confirmed by the user 2026-11-16**: 45% with the fee ≥ sell value validator rule) and cancellation (game-designer vs Gold economy's closed entry-type vocabulary, OQ-2, still open).

### Core Rules

**R1: Recipe rows.** A recipe row (`data/recipes.csv`, loaded by the Data layer, meaning owned here) has:

| Column | Type | Meaning |
|---|---|---|
| `id` | stable ID | `rec_<output>` by convention; never parsed (Data layer R3) |
| `output` | `ref(items)` | The item produced. One unit per craft. Must be `craftable = true` in `items.csv`, or a special listed in R9 |
| `building` | `ref(building_meta)` | The workshop that crafts it |
| `building_lv_req` | int ≥ 1 | Minimum effective level of `building` (R3). ≤ that building's `max_lv` (validator, exists) |
| `inputs` | `map(ref(materials) → int ≥ 1)` | Materials per unit, converted at load (Data layer R4) |
| `gold` | int ≥ 0 | Gold per unit (F1) |
| `time_s` | int ≥ 1 | Game seconds per unit at speed 1.0 (F4) |
| `wave` | int ≥ 1 | Content wave (Data layer R5; column to add) |
| `retired` | bool | Data layer R5 |

There is exactly one recipe per craftable output (validator rule, exists: every `craftable = true` item has a recipe).

New validator rules owned here (to add to `tools/content_validator.py`, OQ-1): **V-CR1** every recipe with `price(output) > 0` has `gold` = F1; **V-CR2** F2 margin ≥ 0; **V-CR3** `craft_gold_ratio > equip_sell_ratio`; **V-CR4** every `bld_smith`, `bld_jeweler`, `bld_alchemy` recipe has `building_lv_req = ceil(output.tier / 2)`; **V-CR5** every `craft_speed_mult` value in `buildings.csv` is ≥ 1.0. A recipe has no random column; crafting always yields exactly one unit of `output` per unit ordered.

**R2: Ordering — the `craft` command.** The player submits `craft(recipe_uid, qty)` through the Command layer (5), applied in P1. The applier checks, in this order, and refuses with the first failing reason (nothing changes on a refusal):
1. The recipe row exists (the Command layer's R4 already checks the uid); it and its `output` are live (Data layer F2). Else `not_live` (9).
2. `1 ≤ qty ≤ craft_batch_max`. Else `qty_out_of_range` (102).
3. The recipe is unlocked (R3). Else `workshop_level_low` (100).
4. The workshop's queue has room: `active + queued < 1 + craft_queue_max`. Else `craft_queue_full` (101).
5. The guild can pay the whole order (F3): Gold economy `can_debit(fund, order_gold)` and Items and loot `count` for every material ≥ `order_mats`. Else `cannot_afford` (8). An `order_gold` above `gold_op_max` is refused here with `cannot_afford` as well (Gold economy R4 would refuse it as `invalid_amount`; the player sees one reason).
6. Commit, with nothing between (Gold economy R4.2): `take(order_mats)` from storage, then debit `order_gold` from the fund as a `craft_cost` burn (entry type 26). If `order_gold` is 0 (no such row today) the debit is skipped.
7. Append the order `{recipe_uid, qty, done = 0, unit_due_tick = none, order_seq}` to the workshop's queue. If the workshop has no active order, it starts at once (R4). Emit `craft_ordered` (2801).

The cost is paid at the order, not unit by unit, so a waiting order can never stall for lack of funds, and the conservation test (Gold economy F6) sees one `craft_cost` per order.

**R3: Unlock gate.** A recipe is unlocked when `effective_level(building) ≥ building_lv_req` (F5), where `effective_level` is the building's level after arrears decay (Guild and buildings F4). For Thiết Tượng Phô, Châu Bảo Các and Dược Quán this is the same test as `effect(building, max_craft_tier) ≥ output.tier`, because their rows give `max_craft_tier = min(21, 2 × level)` and their recipes have `building_lv_req = ceil(tier / 2)` (GDD §17.1); the validator keeps the two in step (V-CR4). Thiện Đường, Tửu Lâu, Linh Miếu and Luyện Khí Đài have no `max_craft_tier` key, so the level test is the only one that covers all seven workshops. The gate is checked **at order time only** (R5).

**R4: The craft queue.** Each crafting building has one queue: one **active** order and up to `craft_queue_max` **waiting** orders, in `order_seq` (command `seq`) order. Workshops craft in parallel; one workshop crafts one unit at a time.
- **Starting a unit:** when an order becomes active, or its previous unit finishes, the next unit starts at tick N with `unit_due_tick = N + unit_ticks` (F4). The speed in F4 is read once, at that unit's start, and fixed for that unit.
- **Finishing a unit:** a P5 handler (order 2800, anchored deadline, Sim core R5) finishes every active unit with `unit_due_tick ≤ N`, in ascending `unit_due_tick`, ties by building `uid`. Each finished unit is given to storage (`give({output: 1})`, always succeeds — Items and loot R7), `done` rises by 1 and `craft_unit_done` (2802) is emitted. If `done < qty` the next unit starts at the same tick N. If `done = qty` the order is removed, `craft_order_done` (2803) is emitted and the next waiting order starts at tick N.
- An idle workshop holds no due tick.

**R5: An order, once paid, always finishes.** A building decaying below `building_lv_req` (arrears), a recipe or output being retired, or the live wave changing does **not** stop, pause or refund an order already accepted: it is paid, so it completes at its normal pace (with whatever speed the building has when each unit starts). Only new orders are gated. This follows Guild and buildings' rule that capacity never orphans existing state, and it means offline resolution never has to model a stalled queue.

**R6: No cancellation in Vertical Slice.** An accepted order cannot be cancelled. A refund would need a gold mint that Gold economy's closed entry-type table (R3) does not have (there is `building_refund` for builds, nothing for crafts), and adding one is that GDD's decision (OQ-2). To make this safe, `craft_batch_max` is small (default 10), the order screen confirms the total cost before submitting, and the longest order at the defaults is 10 rebirth pills at Linh Miếu (10 game hours).

**R7: Speed.** A workshop's craft speed is `effect(building, craft_speed_mult)` read through Guild and buildings R7 and converted to integer milli on each read (F4). If the key is absent (Thiện Đường, Tửu Lâu, Linh Miếu, Luyện Khí Đài) or the query returns `none`, the speed is 1.0. Because `craft_speed_mult` is a decaying key (Guild and buildings R8), arrears slow units started while the fund is in arrears.

**R8: Gold and materials go only through their owners.** Crafting never writes the fund or storage itself. All gold leaves as `craft_cost` (Gold economy R3, burn, fund →, entry type 26); members' wallets are never charged (GDD §6.6: only the guild fund pays for guild production). All materials leave through `take` and all products arrive through `give` (Items and loot R7).

**R9: Specials.** Two recipe outputs are specials, not `craftable` items: `item_enhance_ward` (Luyện Khí Đài level 3, guild-held, consumed by Enhancement 24) and `item_rebirth_pill` (Linh Miếu level 1, member-held, awarded and consumed by Rebirth 23). Both are crafted exactly like any other recipe and land in storage. Their `price` is 0 and they cannot be sold, so F1 and F2 do not apply to them; their `gold` is a hand-set content value. The Ward has no other source (no drop, no shop, no Linh Bảo), which is the GDD §19 rule that sinks cannot be bought with real money. A recipe for `item_school_token` is not added in Vertical Slice (Items and loot OQ-8; see OQ-6).

**R10: Determinism.** Crafting draws no random numbers. Deterministic RNG reserves domain 13 (`rng_domain_crafting`) for "one craft that has a random outcome"; no Vertical Slice recipe has one. If a later recipe gets a random outcome, its event key must use a per-guild craft attempt ordinal (RNG's save-scumming rule), and that change needs this GDD revised. RNG OQ-6 (commit points for player gambles) therefore does not apply to crafting today.

**R11: What the player cannot do.** Craft with member gold; craft a recipe above the workshop's effective level; craft a non-live recipe; order more than `craft_batch_max` units at once or more than `1 + craft_queue_max` orders per workshop; cancel, reorder or speed up an order; choose the quality or rarity of a product (every crafted gear item is the `common` row its recipe names, Items and loot validator rule); craft materials; dismantle items back into materials.

**R12: Registration.** Command type 2801 `craft` (Command layer R2; owner `crafting`; args `recipe_uid, qty`; origin player; reason codes 100 `workshop_level_low`, 101 `craft_queue_full`, 102 `qty_out_of_range`, plus shared 8 and 9). Event type block 2800–2899 (R13). P5 handler order 2800. Feature fail code **28001** `CRAFT_RECIPE_MISSING`, raised if an active order's recipe uid does not resolve at a unit's start or finish (a content defect: IDs are never deleted, Data layer R3). Save section `crafting` (Local save R5).

**R13: Events.**

| type_id | Name | Fields (a, b, c, d) | Logged | Milestone |
|---|---|---|---|---|
| 2801 | `craft_ordered` | building uid, recipe uid, qty, order gold | no | no |
| 2802 | `craft_unit_done` | building uid, recipe uid, output uid, units done in order | no | no |
| 2803 | `craft_order_done` | building uid, recipe uid, qty, — | yes | first craft of each special (`item_enhance_ward`, `item_rebirth_pill`) only |

Quests and achievements (25) subscribe to 2802 for "craft N items" goals (GDD §11.4 weekly quests).

**R14: Saved state.** Per crafting building: the ordered list of orders `{recipe_uid, qty, done, unit_due_tick, order_seq}`. Nothing else: gold and materials were already paid, and the speed is folded into `unit_due_tick`.

### States and Transitions

An **order** has three states; a **workshop queue** is `Idle` when it holds no order and `Busy` otherwise.

| Order state | Meaning | Gold and materials | Holds a due tick |
|---|---|---|---|
| `Waiting` | Paid, behind the active order | Paid | No |
| `Active` | A unit of it is being crafted | Paid | Yes, the current unit's |
| (removed) | All `qty` units delivered | — | — |

| From | To | Trigger | Phase |
|---|---|---|---|
| (none) | `Active` | `craft` accepted, workshop `Idle` (R2.7) | P1 |
| (none) | `Waiting` | `craft` accepted, workshop `Busy` | P1 |
| `Active` | `Active` | A unit finishes and `done < qty`; next unit starts the same tick (R4) | P5 |
| `Active` | (removed) | The last unit finishes (R4) | P5 |
| `Waiting` | `Active` | The order ahead is removed (R4) | P5 |

There is no transition back to unpaid, no pause and no cancel (R5, R6). An order never moves between workshops.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Data layer (3) | in | Typed `recipes` rows in `uid` order, `items`/`materials` rows, liveness query (F2), `config.csv` knobs | — | Data layer owns lookup and liveness; this system owns what a recipe means |
| Items and loot (26) | both | Storage `count` for materials; output item rows (`price`, `tier`, `craftable`); `sell_value` (F5) for the V-CR2 rule | `take(order_mats)` at order; `give({output: 1})` per unit | Items and loot owns storage |
| Gold economy (27) | both | `can_debit(fund, amount)`; `gold_op_max` | Debit `craft_cost` (entry type 26) | Gold economy owns the ledger |
| Guild and buildings (30) | in | `effective_level(building_id)` (PROVISIONAL, OQ-3); `effect(building, craft_speed_mult)`; `effect(building, max_craft_tier)` for the UI | — | Guild and buildings owns levels and effects |
| Command layer (5) | in | `craft` envelopes in `seq` order | Applier return codes | Command layer owns the contract |
| Sim core (1) | both | Tick N, `tick_rate`, P5 deadline slot | P5 handler 2800; fail code 28001 | Sim core owns phases |
| Event bus (42) | out | — | 2801–2803 | Each feature owns its block |
| Local save (6) | out | — | Section `crafting` (R14) | Local save owns the contract |
| Offline progress (31) | in | Due ticks crossed by a gap | — | Offline owns crossed due ticks (PROVISIONAL, OQ-4) |
| Equipment enhancement (24) | out | — | `item_enhance_ward` units in storage | Enhancement consumes them |
| Rebirth and Ascension (23) | out | — | `item_rebirth_pill` units in storage | Rebirth consumes them after the award |
| Quests and achievements (25) | out | — | `craft_unit_done`, `craft_order_done` | Quests subscribe |
| Deterministic RNG (2) | — | Domain 13 reserved, unused (R10) | — | RNG |
| Guild screens (39) | out | — | Recipe list with lock state and affordability, queues, timers, refusal reasons | UI reads only |

## Formulas

### F1: `craft_gold` (content rule for the `gold` column)

The craft_gold formula is defined as:

`craft_gold(recipe) = ( price(output) × craft_gold_ratio_milli + 500 ) div 1000`, for every recipe whose output has `price > 0`. Specials (price 0) carry a hand-set `gold`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| price(output) | int | 1 – 10⁹ | data file (`items.price`, Items and loot 26) | Shop price of the product; 12 – 26,042 today |
| craft_gold_ratio_milli | int | 401 – 1,000 | data file (`config.csv` `craft_gold_ratio`, new key, default 0.45, × 1000 at boot) | Gold fee as a share of shop price |

**Output Range:** 1 to `price`. It is a generator and validator rule, not a runtime calculation: the generators (`tools/gen_a.py`, `tools/gen_c.py`) write `gold` with it and the validator checks it (V-CR1). At 0.45 the fee runs from 5 gold (tier-1 weapon, price 12) to 11,719 (tier-21 ring, price 26,042).
**Example:** `eq_wpn_staff_17_c` (price 18,843): `(18,843 × 450 + 500) div 1000 = 8,479` gold per unit, against 6,595 in the data today.

**Why 0.45, not GDD §19.4's "~30%".** The product of a craft can be sold from storage at `sell_value` = 40% of price (Items and loot F5, `equip_sell_ratio` 0.4). At 30–35% the guild could craft from materials that are otherwise unsellable and sell the result for more gold than the craft cost, turning materials into gold a second time, which Items and loot R13 exists to prevent. Today 405 of 408 recipes allow it (worst case: `pot_hp_21`, fee 406, sells for 1,120). 0.45 keeps a 5-point margin above the sell ratio, so craft-then-sell always loses gold even with free materials, and crafting still costs the guild under half of `buy_item` (Gold economy R15, which burns 100% of price). The materials are the rest of the price. Approved by the user 2026-11-16 (OQ-1): `data/recipes.csv` must be regenerated at 0.45 (today's file still holds the old fees, so V-CR1/V-CR2 fail until it is), and JX1_Tycoon_GDD.md §19.4's craft line now reads 45% (updated 2026-11-16).

### F2: no-profit invariant (validator rule V-CR2)

The craft_sell_margin formula is defined as:

`craft_sell_margin(recipe) = craft_gold(recipe) − sell_value(output)` and the rule is `craft_sell_margin ≥ 0` for every recipe whose output can be sold

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| craft_gold(recipe) | int | 0 – 10⁹ | data file (`recipes.gold`) | Gold per unit (F1) |
| sell_value(output) | int | 0 – price | calculated (Items and loot F5) | What one unit sells for from storage |

**Output Range:** must be ≥ 0; at the defaults (0.45 vs 0.40) it is about 5% of price (0 for the cheapest items after rounding: tier-1 weapon 5 − 5 = 0). A negative margin fails validation (exit 1). This keeps the rule true whatever `equip_sell_ratio` or `craft_gold_ratio` is later tuned to: raising the sell ratio above the craft ratio fails the build instead of opening a loop.
**Example:** `eq_arm_heavy_05_c` (price 2,524): fee `(2,524 × 450 + 500) div 1000 = 1,136`, sell value `(2,524 × 400 + 500) div 1000 = 1,010`, margin 126 ≥ 0. With today's data (fee 883) the margin is −127 and the validator would fail.

### F3: order cost

The order_cost formula is defined as:

`order_gold = qty × gold`; `order_mats[m] = qty × inputs[m]` for each material `m` in the recipe

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| qty | int | 1 – `craft_batch_max` | command argument | Units ordered |
| gold | int | 0 – 10⁹ | data file (`recipes.gold`) | Gold per unit |
| inputs[m] | int | 1 – 1,000 | data file (`recipes.inputs`) | Units of material `m` per craft; 1 – 22 today |
| craft_batch_max | int | 1 – 100 | data file (`config.csv`, new key) | Default 10 |

**Output Range:** `order_gold` 0 to `100 × 10⁹` at the validator caps, below `gold_op_max`; today's maximum is 10 × 50,000 = 500,000 (rebirth pills). Integer only, no overflow.
**Example:** 10 × `rec_pot_hp_05` at F1 (price 560 → fee `(560 × 450 + 500) div 1000 = 252`): 2,520 gold and 40 `mat_z04_1`.

### F4: `unit_ticks`

The unit_ticks formula is defined as:

`unit_ticks = ceil( time_s × tick_rate × 1000 / speed_milli )`, with `speed_milli = round(craft_speed_mult × 1000)` if the workshop has the key, else 1000

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| time_s | int | 1 – 86,400 | data file (`recipes.time_s`) | Game seconds per unit at speed 1.0; 22 – 3,600 today (generator: `round(20 × 1.15^tier)` for gear and potions, `20 + 2 × tier` for feasts and brews) |
| tick_rate | int | divides 1,000,000 | data file (`config.csv`, Sim core R1) | Ticks per second, 10 today |
| craft_speed_mult | float → milli | 1.0 – 3.0 | data file (`buildings.csv` effects via Guild and buildings R7) | 1.08 – 1.88 today for the three workshops that have it |
| speed_milli | int | 1,000 – 3,000 | calculated | Read once at unit start (R4) |

**Output Range:** 1 tick to `86,400 × 10` ticks (24 game hours) per unit. `ceil` makes every unit take at least one tick, so the P5 handler can never finish more than one unit of an order in a tick, except across an offline gap. `speed_milli` is never below 1,000, so there is no division by zero (validator: `craft_speed_mult ≥ 1.0`, V-CR5).
**Example:** `rec_eq_wpn_staff_17_c` (215 s) at Thiết Tượng Phô level 9 (`craft_speed_mult` 1.72): `ceil(215 × 10 × 1000 / 1720) = 1,250` ticks = 125 game seconds. The same recipe at level 11 (1.88): `ceil(2,150,000 / 1880) = 1,144` ticks.

### F5: unlock gate

The craft_unlocked formula is defined as:

`craft_unlocked(recipe) = live(recipe) ∧ live(output) ∧ effective_level(building) ≥ building_lv_req`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| live(·) | bool | — | calculated (Data layer F2) | Liveness of the recipe and output rows |
| effective_level(building) | int | 0 – `max_lv` | calculated (Guild and buildings F4, PROVISIONAL query, OQ-3) | Level after arrears decay; 0 if not built |
| building_lv_req | int | 1 – `max_lv` | data file (`recipes.building_lv_req`) | 1 – 11 today |

**Output Range:** true or false. An unbuilt workshop (level 0) unlocks nothing, because `building_lv_req ≥ 1`.
**Example:** Thiết Tượng Phô level 6, 2 arrears days at `arrears_days_per_level = 1`: effective level 4, so tier-9 to tier-12 smith recipes (`building_lv_req` 5–6) are locked for new orders until the fund pays a full upkeep charge; an order for a tier-12 blade placed the day before still finishes (R5).

### F6: workshop throughput (balance reference)

The craft_throughput formula is defined as:

`units_per_hour = 3600 × tick_rate / unit_ticks`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| unit_ticks | int | ≥ 1 | calculated (F4) | Ticks per unit |
| tick_rate | int | 10 | data file (`config.csv`) | Ticks per second |

**Output Range:** 1 unit per 24 h at the extreme to 36,000 per hour (1-tick units). Today: 1 rebirth pill per hour; 18 tier-21 rings per hour at Châu Bảo Các 11; about 290 tier-1 swords per hour at Thiết Tượng Phô 1. The binding limit on crafting is materials and gold, not time, for everything below tier 15.
**Example:** tier-17 staff at smith level 9: `36,000 / 1,250 = 28.8` units per hour.

**Feedback loops.** *Workshop level → better and faster crafts → stronger members → deeper zones → better materials → higher workshop levels* (positive, intended): bounded by finite building levels (max 11) and by the tier cap of 21. *Craft-and-sell* (would be positive and unbounded within material supply): closed by F2. No loop involves member wallets.

## Edge Cases

*Specialist step (systems-designer lens, Section E) applied to R1–R14 and F1–F6.*

**Ordering**
- **If the fund holds exactly `order_gold` and storage exactly `order_mats`**: the order is accepted and both reach 0. Upkeep at the next day slot then pays what it can (Gold economy R8); crafting does not reserve upkeep.
- **If two `craft` commands for the same workshop arrive in one tick**: they apply in command `seq` order (Sim core R6); each sees the storage and fund the previous one left. The second may be refused `cannot_afford` or `craft_queue_full`.
- **If a `craft` command and a `build` command (Guild and buildings) compete for the same material in one tick**: `seq` order decides; whichever applies second sees the reduced count. Neither is half-paid (`take` is all-or-nothing).
- **If `qty` is 0, negative or above `craft_batch_max`**: refused `qty_out_of_range`, nothing changes.
- **If the workshop is level 0 (not built) or decayed below the requirement**: refused `workshop_level_low`. The UI shows the lock and the level needed.
- **If the workshop is under construction from level L to L+1**: the gate and speed use level L (Guild and buildings R6); recipes that need L+1 unlock on completion.
- **If the recipe or its output is not live (unreleased wave or retired)**: refused `not_live`. A live recipe cannot reference a non-live input (Data layer F3, validator), so a live recipe never asks for an unobtainable material.
- **If `order_gold` exceeds `gold_op_max`**: refused `cannot_afford` (R2.5). Unreachable at the defaults (max 500,000).

**Running orders**
- **If arrears push a workshop below an active or waiting order's requirement**: the order keeps running (R5); its later units start with the decayed `craft_speed_mult` (R7), so they may be slower.
- **If a recipe or output is retired while an order for it is queued**: the order finishes and delivers; retired items stay usable in storage (Items and loot R7).
- **If an active order's recipe uid no longer resolves**: the tick fails with 28001. This cannot happen with valid content (IDs are never deleted) and signals a content or save defect.
- **If several workshops finish units on the same tick**: processed in ascending `unit_due_tick`, ties by building `uid`. The order is invisible to the player (each `give` always succeeds) but fixed for parity.
- **If a unit's output is equipment**: it goes to storage at `enhance_level = 0` and is never auto-equipped; only the designated award equips it (Items and loot R8).
- **If storage already holds a huge count of the output**: `give` still succeeds (storage is uncapped, Items and loot R7). There is no overflow below int64.
- **If the player orders the same recipe in two orders**: allowed; they are separate orders and run one after the other.

**Offline and save**
- **If an offline gap crosses many unit due ticks**: Offline progress (31) runs the P5 handler at each crossed due tick in order (PROVISIONAL, OQ-4), so every unit finishes at the same tick it would have finished live, the next unit starts at that tick, and the result equals a live run. A 10-hour gap with a 10-unit rebirth-pill order delivers all 10.
- **If the game is saved mid-unit and loaded**: the active unit's `unit_due_tick` is restored and it finishes at that tick; no time is lost or gained.
- **If `tick_rate` changes between saves**: due ticks already stored are absolute ticks and are converted by Local save's migration, as for buildings (Local save R14). Crafting does not recompute them.

**Degenerate strategies**
- **Craft, then sell the product from storage**: never profitable, by F2 (fee ≥ sell value). Without F2, today's data makes it a materials-to-gold faucet (F1 note).
- **Craft gear for the guild instead of buying it**: intended. It costs about 45% of price in gold plus materials against 100% for `buy_item`; the materials are the difference.
- **Use crafting to dodge upkeep (spend the fund to 0 before the day slot)**: upkeep simply goes into arrears, which decays the workshops themselves (Guild and buildings R8). No gain.
- **Fill every queue with long orders to hold gold out of reach**: the gold is burned at order, not held, so there is nothing to reclaim later.

## Dependencies

### Upstream (this system depends on)

| System (#) | Hard / soft | Interface | Status |
|---|---|---|---|
| Data layer and content pipeline (3) | Hard | `recipes` table and schema (add `wave`, `retired`); liveness F2; validator rules V-CR1–V-CR5 | Designed |
| Items and loot tables (26) | Hard | Storage `count` / `take` / `give`; item `price`, `tier`, `craftable`; `sell_value` (F5) | Designed |
| Gold economy (27) | Hard | `can_debit`; `craft_cost` debit (entry type 26); `gold_op_max` | Designed |
| Guild and buildings (30) | Hard | `effective_level(building_id)` (PROVISIONAL, OQ-3); `effect(building, craft_speed_mult)`, `effect(building, max_craft_tier)` | Designed |
| Command layer (5) | Hard | `register_command` for type 2801; shared codes 8, 9 | Designed |
| Sim core and tick loop (1) | Hard | P5 anchored deadline slot; `tick_rate`; fail code | Needs Revision |
| Event bus and history log (42) | Hard | `register_type` for 2801–2803 | Designed |
| Local save and migration (6) | Hard | Section `crafting` | Designed |
| Deterministic RNG (2) | Soft (reserved) | Domain 13, not drawn from in Vertical Slice (R10) | Needs Revision |

### Downstream (systems that depend on this one)

| System (#) | Hard / soft | Interface | What it gets |
|---|---|---|---|
| Equipment enhancement (24) | Hard | `item_enhance_ward` in storage (`take`, its R2.7) | The gold source of Wards (§19.3); the Linh Bảo shop (Gold economy R16, user decision 2026-11-16) is the other source. Its F3 prices a ward at this recipe's 20,000 gold |
| Rebirth and Ascension (23) | Hard | `item_rebirth_pill` in storage | The only source of rebirth pills besides rebirth rewards |
| Quests and achievements (25) | Soft | 2802, 2803 | "Craft N items" weekly goals (§11.4) |
| Offline progress (31) | Hard | Due ticks inside a gap | Completing units offline in order |
| Guild screens (39) | Hard | Recipe list, lock and affordability, queues, timers, refusal reasons | The workshop screen |
| Local save (6) | Hard | Section `crafting` | What to persist |
| Guild market and trade orders (29) | Soft | Crafted units in storage | Goods the market may sell (VS, its GDD) |

**Bidirectional status.** Items and loot (26), Gold economy (27), Guild and buildings (30), Data layer (3), Command layer (5), Local save (6) and Deterministic RNG (2) already list Crafting (28). The systems index row 28 lists RNG, Items and loot, Gold economy, Guild and buildings and Data layer; Command layer, Sim core, Event bus and Local save are also hard dependencies and are added to the row. Equipment enhancement (24) lists this system as the Ward source (its OQ-7). Rebirth (23) is undesigned and should list it as the pill source.

**Provisional assumptions about other systems:**
1. Guild and buildings (30) exposes `effective_level(building_id)` (its F4 value for a decaying key) as a query alongside `effect()`.
2. Offline progress (31) runs crafting's P5 handler at each crossed due tick, in order, as it does for builds.
3. Gold economy (27) `sell_item` sells consumables from storage at `equip_sell_milli`, the same as equipment (F5 names equipment only).

## Tuning Knobs

*Derived from the `data file` variables of F1–F6 (systems-designer lens, Section G).*

| Knob | Where | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `craft_gold_ratio` (new) | `config.csv` | 0.45 | > `equip_sell_ratio` (0.40) – 0.80 | Crafting loses its edge over `buy_item`; materials pile up unused | ≤ 0.40 breaks F2: craft-and-sell mints gold (validator fails) | `equip_sell_ratio` (Items 26) bounds it from below; `shop_fund_share_pct` (27) does not apply to crafts |
| `craft_batch_max` (new) | `config.csv` | 10 | 1 – 50 | Big uncancellable mistakes (R6) | Tedious repeat ordering | `craft_queue_max` (together they set how much a workshop can hold: 10 × 6 = 60 units) |
| `craft_queue_max` (new) | `config.csv` | 5 | 0 – 20 | Long offline runs become fully automatic; less reason to return | 0 = one order at a time; frequent check-ins | `craft_batch_max` |
| `recipes.gold` per row | `recipes.csv` | F1 | F1, V-CR2 | See `craft_gold_ratio` | See `craft_gold_ratio` | Generated; edit the ratio, not rows, except specials |
| `recipes.gold` for specials | `recipes.csv` | Ward 20,000; pill 50,000 | Ward: 0.5 – 5 h of a lv60 guild's fund income; pill: per Rebirth 23 | Wards out of reach: +11…+20 impossible (§19.3) | The §19.3 sink table collapses | Enhancement 24's `enhance.csv` and its +15/+20 cost table |
| `recipes.inputs` per row | `recipes.csv` | Generator (gear: 3 + tier grade 1, …) | ≥ 1 per material | Materials gate everything; buildings starve | Materials pile up unused | Guild and buildings `cost_mats` competes for the same materials |
| `recipes.time_s` per row | `recipes.csv` | `20 × 1.15^tier` (gear, potions); `20 + 2 tier` (feasts, brews) | 1 – 86,400 | Late tiers feel slow | Time stops mattering | `craft_speed_mult` |
| `craft_speed_mult` | `buildings.csv` (owned by 30) | 1 + 0.08 × level | ≥ 1.0 | — | — | Pointer: Guild and buildings Tuning Knobs |
| `max_craft_tier` / level gate | `buildings.csv` (30) / `recipes.building_lv_req` | `2 × level` / `ceil(tier/2)` | V-CR4 keeps them equal | — | — | Pointer: Guild and buildings |

`equip_sell_ratio` (Items and loot 26) and `gold_op_max` (Gold economy 27) are pointed to, not duplicated.

## Visual/Audio Requirements

Optional for the `Economy` category; brief notes only. No art bible exists (`design/art/art-bible.md` absent), so these follow GDD §12.4's pixel 2D direction and are not checked against art principles.

- **Workshop working state:** each crafting building shows a small looping "working" animation (smoke from Thiết Tượng Phô, steam from Dược Quán, fire under Thiện Đường) while its queue is `Busy`, and stops when `Idle`. One sprite overlay per building, no per-unit effect.
- **Unit done:** a small item icon pops from the building and arcs toward the storage chest, at most one per building per second on screen (batched when many finish together, e.g. after offline).
- **Order done:** a short chime; a distinct, brighter cue for the first Ward and first rebirth pill (milestone events).
- **Audio priority:** low; never masks Golden Boss or member-death cues.

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:crafting-and-recipes` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

Optional for `Economy`. Targets: the `craft` order confirms within one frame of the tap (the command is applied next tick, at most 100 ms); the queue shows the new order instantly as pending and then accepted; timers count down smoothly in seconds. Crafting is meant to feel like a quick, satisfying errand, not a minigame: three taps from the storage screen to a queued order.

## UI Requirements

1. **Workshop screen (one per crafting building):** the active order with its unit progress bar and time left; the waiting orders; empty slots up to `1 + craft_queue_max`; the building's level, craft speed and highest unlocked tier.
2. **Recipe list:** filterable by slot and tier; each row shows output icon and name, per-unit gold and materials (with owned counts), time per unit at current speed, and a state: *craftable now*, *short of materials/gold* (shows what is missing), *locked* (shows the level needed). Locked recipes for the next level are visible, greyed; recipes of unreleased waves are hidden.
3. **Order dialog:** quantity stepper (1 – `craft_batch_max`), live total gold and materials, total time, and an explicit warning that the order cannot be cancelled (R6). Confirm button disabled when unaffordable, but the applier's refusal is still handled (Command layer R14).
4. **Building upgrade preview (Guild and buildings' screen):** the recipes and speed the next level adds.
5. **Storage screen shortcut:** from a material, "craft with this" lists recipes that use it.
6. **Refusal feedback:** each reason code shown as localised words (`workshop_level_low`, `craft_queue_full`, `qty_out_of_range`, `cannot_afford`, `not_live`). Nothing conveyed by colour alone.

> **📌 UX Flag — Crafting and recipes**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the workshop screen and order dialog **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD uses | From | Section | Notes |
|---|---|---|---|
| Storage `count` / `take` / `give`, all-or-nothing `take` | `items-and-loot-tables.md` | R7 | Interface |
| Materials never sold from storage | `items-and-loot-tables.md` | R13 | Reason for F2 |
| `sell_value` | `items-and-loot-tables.md` | F5 | Input to F2 |
| Only `common` items craftable; Crafting owns recipes | `items-and-loot-tables.md` | Core Rules data table | Constraint |
| `item_school_token` recipe question | `items-and-loot-tables.md` | OQ-8 | Answered: not in VS (OQ-6) |
| `craft_cost` entry type 26 (burn, fund →) | `gold-economy.md` | R3, R9 | Interface |
| Check-then-commit for multi-part debits | `gold-economy.md` | R4.2 | Rule R2.6 |
| `buy_item` burns full price | `gold-economy.md` | R15 | Comparison for F1 |
| `effect()` query; no consumer reads levels itself | `guild-and-buildings.md` | R7 | Tension: needs `effective_level` query (OQ-3) |
| Arrears decay; `craft_speed_mult`, `max_craft_tier` decay | `guild-and-buildings.md` | R8, F4 | Gate and speed |
| Upgrade keeps old level working | `guild-and-buildings.md` | R6 | Edge case |
| Build queue pay-at-order pattern | `guild-and-buildings.md` | R2 | Same pattern |
| `recipes` table; liveness; no forward references | `data-layer-and-content-pipeline.md` | R2, R5, F2, F3 | Interface |
| Command registration and shared codes | `command-layer.md` | R2, R6, R14 | Interface |
| Command type IDs = system number × 100 | registry `command_type_id_block_rule` | — | Type 2801 |
| Domain 13 crafting; save-scumming rule | `deterministic-rng.md` | domain table, Edge Cases, OQ-6 | Reserved, unused |
| Save section contract | `local-save-and-migration.md` | R5, R14 | Interface |

## Acceptance Criteria

*Specialist step (qa-lead lens) applied. Tags: [Logic] = automated unit test; [Integration] = automated multi-system test; [UI] = screenshot evidence.*

**Ordering (R2, F3)**
- **AC-1 [Logic] (R2, F3)**: **GIVEN** Dược Quán level 3, fund 10,000, storage 40 `mat_z04_1`, recipe `rec_pot_hp_05` with gold 252 (F1) and inputs `mat_z04_1:4`, **WHEN** `craft(rec_pot_hp_05, 10)` is applied, **THEN** the fund is 7,480, storage holds 0 `mat_z04_1`, `total[craft_cost]` rose 2,520, the workshop has one active order with `qty = 10, done = 0`, and one 2801 event carries `(bld_alchemy uid, recipe uid, 10, 2520)`.
- **AC-2 [Logic] (R2.5)**: **GIVEN** the setup of AC-1 but storage holds 39 `mat_z04_1`, **WHEN** the same command is applied, **THEN** it is refused with code 8, and the fund, storage and queue are unchanged.
- **AC-3 [Logic] (R2.5)**: **GIVEN** the setup of AC-1 but the fund is 2,519, **THEN** refused with code 8 and nothing changes; **GIVEN** fund exactly 2,520, **THEN** accepted and the fund is 0.
- **AC-4 [Logic] (R2.2)**: **GIVEN** `craft_batch_max = 10`, **WHEN** `qty` is 0 or 11, **THEN** refused with 102; **WHEN** `qty` is 1 or 10, **THEN** accepted.
- **AC-5 [Logic] (R2.4)**: **GIVEN** `craft_queue_max = 5` and a workshop with 1 active and 5 waiting orders, **WHEN** a sixth `craft` arrives, **THEN** refused with 101; a different workshop still accepts.
- **AC-6 [Logic] (R2.1)**: **GIVEN** `live_wave = 1` and a recipe whose `wave = 2`, **WHEN** `craft` is applied, **THEN** refused with 9.

**Gate (R3, F5)**
- **AC-7 [Logic] (F5)**: **GIVEN** Thiết Tượng Phô level 6 and 0 arrears, **WHEN** a tier-12 smith recipe (`building_lv_req` 6) is ordered, **THEN** accepted; **GIVEN** 2 arrears days at `arrears_days_per_level = 1`, **THEN** refused with 100; **GIVEN** the workshop is not built, **THEN** a level-1 recipe is refused with 100.
- **AC-8 [Logic] (R3, V-CR4)**: **GIVEN** the shipped data, **WHEN** the validator runs, **THEN** every `bld_smith`, `bld_jeweler` and `bld_alchemy` recipe has `building_lv_req = ceil(output.tier / 2)`, so `effect(max_craft_tier) ≥ tier` ⇔ F5's level test at every level 1–11.
- **AC-9 [Logic] (Edge: under construction)**: **GIVEN** Thiết Tượng Phô building from 5 to 6, **WHEN** a level-6 recipe is ordered, **THEN** refused with 100; **WHEN** the build completes, **THEN** the same order is accepted the next tick.

**Queue and timing (R4, F4)**
- **AC-10 [Logic] (F4)**: **GIVEN** `tick_rate = 10`, `craft_speed_mult = 1.72`, recipe `time_s = 215`, **WHEN** a unit starts at tick 1,000, **THEN** its `unit_due_tick` is 2,250; **GIVEN** a workshop without the key and `time_s = 3,600`, **THEN** 37,000.
- **AC-11 [Logic] (R4)**: **GIVEN** an order of 3 units with `unit_ticks = 100` started at tick 0, **WHEN** the sim runs to tick 300, **THEN** storage gains exactly 1 unit at ticks 100, 200 and 300, three 2802 events and one 2803 are emitted, and the order is removed at tick 300.
- **AC-12 [Logic] (R4)**: **GIVEN** an active order and one waiting order in the same workshop, **WHEN** the active order's last unit finishes at tick N, **THEN** the waiting order's first unit starts at tick N (its due tick is N + its `unit_ticks`).
- **AC-13 [Logic] (R4, R7)**: **GIVEN** an active 2-unit order, **WHEN** the workshop's `craft_speed_mult` drops (arrears) during unit 1, **THEN** unit 1 keeps its due tick and unit 2's `unit_ticks` uses the lower speed.
- **AC-14 [Logic] (Edge: same-tick completions)**: **GIVEN** two workshops whose units are due on the same tick, **WHEN** P5 runs, **THEN** they finish in ascending building `uid` and the event order matches the Python reference.

**Paid orders always finish (R5, R6)**
- **AC-15 [Logic] (R5)**: **GIVEN** a waiting order for a level-6 recipe, **WHEN** arrears decay the workshop to effective level 4, **THEN** the order still starts and delivers all its units; a new order for the same recipe is refused with 100.
- **AC-16 [Logic] (R5)**: **GIVEN** an active order whose output is set `retired = true` by a content update, **WHEN** the sim runs, **THEN** all units are delivered to storage.
- **AC-17 [Logic] (R6)**: **GIVEN** the Command layer registry, **THEN** no crafting cancel command exists, and the order dialog's warning text key is present in `i18n/` vi and en.

**Formulas and data (F1, F2)**
- **AC-18 [Logic] (F1, V-CR1)**: **GIVEN** `craft_gold_ratio = 0.45` and regenerated data, **WHEN** the validator runs, **THEN** every recipe with `price(output) > 0` has `gold = (price × 450 + 500) div 1000` (e.g. `eq_wpn_staff_17_c` → 8,479; `eq_wpn_sword_01_c` → 5).
- **AC-19 [Logic] (F2, V-CR2)**: **GIVEN** a fixture recipe with `gold` 883 and output price 2,524 (sell value 1,010), **WHEN** the validator runs, **THEN** it exits 1 naming the recipe; **GIVEN** gold 1,010, **THEN** it exits 0 (margin 0 is allowed).
- **AC-20 [Logic] (V-CR3)**: **GIVEN** the validator, **WHEN** `craft_gold_ratio ≤ equip_sell_ratio`, **THEN** it exits 1.
- **AC-21 [Integration] (F2, Gold economy F6)**: **GIVEN** a guild with 100 `mat_z05_1` and fund 100,000, **WHEN** it crafts every recipe the materials allow and then sells every product with `sell_item`, **THEN** the fund ends ≤ 100,000, and the conservation identity F6 holds after every tick.

**Specials, determinism, integration**
- **AC-22 [Integration] (R9)**: **GIVEN** Luyện Khí Đài level 3, fund 20,000, 8 `mat_z06_1` and 2 `mat_z06_2`, **WHEN** `craft(rec_item_enhance_ward, 1)` completes, **THEN** storage holds 1 `item_enhance_ward`, a logged 2803 milestone is emitted for the first Ward, and `sell_item` on it is refused.
- **AC-23 [Logic] (R10)**: **GIVEN** a seeded run with crafting orders, **WHEN** the crafting handler runs, **THEN** it makes zero RNG draws (domain 13 draw counter stays 0), and two runs with different world seeds produce identical crafting events.
- **AC-24 [Integration] (Offline, PROVISIONAL)**: **GIVEN** a 10-unit order with `unit_ticks = 36,000` started at tick 0, **WHEN** a 10-hour offline gap is fast-forwarded, **THEN** storage gains 10 units and the event stream equals a live 10-hour run.
- **AC-25 [Integration] (R14, save)**: **GIVEN** an active order at `done = 4` of 10 with `unit_due_tick = 5,000`, **WHEN** the game saves at tick 4,000 and loads, **THEN** the fifth unit is delivered at tick 5,000 and the remaining units follow on schedule.
- **AC-26 [Integration] (Quests)**: **GIVEN** a "craft 20 items" quest subscribed to 2802, **WHEN** two orders of 10 complete, **THEN** the quest counter reads 20.
- **AC-27 [UI]**: screenshot evidence in `production/qa/evidence/` of the workshop screen with an active and a waiting order, a locked recipe showing its level requirement, and the order dialog showing the no-cancel warning.

**Performance.** The P5 handler does O(workshops) work per tick when no unit is due (seven anchored deadlines, checked by the Sim core's deadline set), and O(units finishing) otherwise; across a 24-hour offline gap the cost is O(units crafted). No budget beyond the Sim core's tick budget is needed.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **RESOLVED (user decision 2026-11-16):** the craft fee is 45% of the output's shop price (`craft_gold_ratio` 0.45, F1) and the validator enforces fee ≥ the product's sell value (V-CR2, F2), replacing GDD §19.4's "~30%". Follow-up work, not done in this GDD: (1) regenerate `recipes.gold` in `data/recipes.csv` via `tools/gen_a.py`/`gen_c.py` at 0.45 (potion and food fees were also computed from pre-repricing prices); (2) add V-CR1–V-CR5 to `tools/content_validator.py`; (3) JX1_Tycoon_GDD.md §19.4's craft line — done 2026-11-16 (now 45%, with a pointer here); calibrate in S3 | Dev tooling (43), Items and loot (26) | Before the crafting story / S3 |
| OQ-2 | **Cancellation (deferred).** Cancelling a paid order needs a `craft_refund` mint type in Gold economy's closed entry-type table (R3), like `building_refund`. Add it (and a `cancel_craft` command refunding the active and waiting units in full), or keep R6's no-cancel rule? | Gold economy (27), user | Before the crafting UI story |
| OQ-3 | PROVISIONAL: Guild and buildings (30) — exposes `effective_level(building_id)` (F4 for a decaying key) as a query. Its R7 says consumers never compare levels; the alternative is a per-building `max_craft_level`-style key on all seven workshops (data change to `buildings.csv`) | Guild and buildings (30) | Consistency check |
| OQ-4 | PROVISIONAL: Offline progress (31) — runs crafting's P5 handler at every crossed due tick in order, as for builds | Offline progress (31) | When its GDD is written |
| OQ-5 | **Shops and crafted stock (scope).** In EHT, shops sell what the workshops craft. Here Gold economy R7 sells shop goods to members without stock, and crafting feeds only guild storage. Should Vertical Slice tie shop availability to crafted stock? It would change Gold economy R7, Utility AI (12) buying and Market (29); not decided here | Producer, Gold economy (27), Market (29) | Before Vertical Slice sprint planning |
| OQ-6 | Items and loot OQ-8: no `item_school_token` recipe in Vertical Slice (keeps it a Golden Boss drop). Adding one is a content and scope decision for Schools (20) | Schools (20), Items and loot (26) | When Schools' Academy is scheduled |
| OQ-7 | **RESOLVED (consistency-check 2026-11-16):** Items F5 now names consumables with equipment (`equip_sell_milli`), and Gold economy `sell_item` sells equipment and consumables (never materials) at F5's value. F2 uses `sell_value(output)` unchanged | Gold economy (27), Items and loot (26) | Closed |
| OQ-8 | `recipes.csv` needs `wave` and `retired` columns (Data layer R5 "add"); each recipe's wave must be ≥ its output's, inputs' and building's waves (F3) | Data layer (3) | Next data pass |
| OQ-9 | Ward fee (20,000) and pill fee (50,000) are hand-set and not simulated. Equipment enhancement (24, now designed) uses `W = 20,000` in its F3 and asks the same question (its OQ-7); confirm both once S5 measures ward use. Pill fee pending Rebirth (23) | Enhancement (24), Rebirth (23) | S5 |
| OQ-10 | Brew recipes for tiers 15–21 all need Tửu Lâu level 8 (its `max_lv`), so seven brew tiers unlock at once. Intended, or should Tửu Lâu gain levels or the brews be re-spaced? | Guild and buildings (30), content | Next data pass |
