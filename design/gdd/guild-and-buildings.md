# Guild and Buildings

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run; decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet); serves JX1_Tycoon_GDD.md §1 (the bang chủ "builds buildings") and §19.4 (buildings as a gold sink)

## Summary

Guild and buildings is the guild's physical base: the Tổng Đàn (guild hall) and the 25 other buildings the bang chủ builds and upgrades with guild funds and hunted materials. For the player it is the long-term investment track. Each level takes real time to build, unlocks or strengthens something the members use (food, potions, the market, enhancement, rest, training), and the Tổng Đàn's level caps the roster and the number of buildings. It exists because "the guild sells, crafts and upgrades" is half of the core loop (§1), and because buildings are the largest planned gold sink in the game (§19.4, 44.2 million gold to max everything).

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Sim core and tick loop, Data layer and content pipeline, Gold economy, Items and loot tables, Event bus and history log`

## Overview

Guild and buildings owns the guild record's structural part and every building's level. Its data layer is simple: one current level per building kind (0 = not built), a build queue of at most `build_concurrent_max + build_queue_max` entries, and the effects map that `buildings.csv` gives each level. Its player-facing side is the build decision. The bang chủ chooses which building to build or upgrade next, pays the gold from the guild fund and the materials from guild storage at once, and waits out `build_time_min` of real (simulated) time. Every other system reads a building's effects through one query, never through the CSV. The Tổng Đàn (`bld_hq`) is special: its level is the guild level, it sets the base member cap and the number of building slots, and every other building's level requires a minimum Tổng Đàn level.

The system is played actively, in short decisions, and felt passively for hours: a Dược Phòng upgrade makes better potions craftable, and the Luyện Khí Đài's level caps how far gear can be enhanced. Without it the guild has no visible growth of its own, the gold economy has no large sink (§18.3: gold inflates without one), and half of the downstream systems (crafting, enhancement, market, recruitment cap, school change) have no gate.

**MVP scope** (systems index, PR-SCOPE): the full system is designed here; MVP builds five buildings: Tổng Đàn (`bld_hq`), Thiện Đường (`bld_restaurant`), Dược Phòng (`bld_alchemy`), Chợ Bang (`bld_market`) and Luyện Khí Đài (`bld_enhance`). How the other 21 are held back in the slice is an open question (OQ-1).

**What this system does not own:**
- The guild fund, its balance, credits and debits, tax and upkeep. Gold economy (27) owns every gold movement; this system asks it to debit and credit (systems index, "every credit and debit").
- Guild storage and materials. Items and loot (26) owns storage; this system asks it to take and return materials.
- What an effect *does*. `satiety_mult` belongs to whoever owns satiety, `max_enhance_lv` to Equipment enhancement (24), and so on. This system owns which value is in force; the consumer owns its meaning and its value when the building is not built.
- Building display names and descriptions (`i18n/`, Data layer R9).
- Guild fame (§4.1 `Guild.fame`). No system owns it yet (OQ-6).

## Player Fantasy

**Both.** The player acts on buildings directly (choose, pay, wait, see it rise) and feels them indirectly through every member who eats better, heals faster or carries sharper gear.

*Lens applied:* creative direction (`references/lens-creative-director.md`). No pillars exist, so each framing is anchored to a JX1_Tycoon_GDD.md line instead of a quoted pillar. Three candidates were written:

1. **"From a hut to a sect headquarters" (chosen).** Anchor: §1, "Bang chủ quản lý bang hội võ lâm: tuyển thành viên, xây công trình…". *The moment:* the player comes back after a night away, the Tổng Đàn has reached level 3, and the roster limit, the building slots and the Luyện Khí Đài all open at once. The guild visibly became bigger while they slept. *Asks of the design:* long builds that complete offline (R6, Edge Cases), a visible guild level (R9), and an unlock that changes what the player can do, not only a bigger number.
2. **"Every tael goes into the walls."** Anchor: §19.4, buildings as the 44.2 M sink. *The moment:* the player weighs 15,000 gold for the next Tổng Đàn level against three enhancement attempts. *Asks:* real trade-offs between buildings and other sinks, which F6 checks.
3. **"The guild provides."** Anchor: §1's loop "bang bán/chế tạo/nâng cấp → thành viên mạnh hơn". *The moment:* a member returns injured and the upgraded Y Quán sends them back in half the time. *Asks:* building effects that the player can see on members (UI Requirements 4).

Framing 1 is chosen (recommended for an Economy system whose payoff is visible growth); framings 2 and 3 are kept as supporting moments, and the rules below deliver all three.

## Detailed Design

### Core Rules

**R1: Building kinds and the level track.** A building kind is a `building_meta` row (`id`, `max_lv`, `unlock_hq_lv`, `wave`). Its levels are the `buildings` rows with that `building_id`, levels 1 to `max_lv`. The guild holds **one instance of each kind**, with an integer `level` from 0 (not built) to `max_lv`. There is no demolition and no downgrade: a level, once completed, is kept for the life of the save.
- A new guild starts with `bld_hq` at level 1 and every other kind at level 0. `bld_hq` level 1 (cost 0, time 0) is the starting state and is never built.
- A kind is **available** when its `building_meta` row is live (Data layer F2). A non-live kind cannot be queued, and it stays invisible in the build list. A kind that becomes non-live after being built (retired) keeps its level and its effects (Edge Cases).

**R2: The build order.** The player orders a build with `build(building_id)`, applied in P1 (Sim core R2). It targets the next level: `to_level = level + 1`. It is **refused**, with a reason code (F7 event 3006) and nothing taken, unless every one of these holds:
1. The kind is available (R1) and `level < max_lv`.
2. The kind has no entry in the queue or under construction already (one entry per kind).
3. The queue has room: `active_count + queued_count < build_concurrent_max + build_queue_max`.
4. **Tổng Đàn requirement:** the completed `bld_hq` level ≥ the target row's `hq_lv_req`. This is checked against completed levels only, never against a Tổng Đàn upgrade still in the queue. For `bld_hq` itself the requirement is waived (its rows set `hq_lv_req = level`, which only describes the guild level the row produces).
5. **Slot:** if `to_level = 1` (a new building), `slots_used + 1 ≤ building_slots` (F3). An upgrade never needs a slot.
6. **Cost:** the guild fund holds `cost_gold` (Gold economy 27) and guild storage holds every `cost_mats` entry (Items and loot 26).

**When the order is accepted**, in this order and in the same handler call:
1. Take the cost: debit `cost_gold` from the guild fund with reason `building_cost`, and take the `cost_mats` from storage. Both are checked before either is taken (condition 6), so both succeed.
2. Append a queue entry `{building_id, to_level, gold_paid, mats_paid, state}`. If `active_count < build_concurrent_max`, the entry starts at once (R4). Otherwise it waits as `Queued`.
3. Emit `build_queued` (3001).

The cost is paid at the order, not at the start, so a queued entry never stalls for lack of funds and the money-conservation test (S3) sees one debit per order.

**R3: Cancelling.** `cancel_build(building_id)` applied in P1 removes that kind's entry, whether `Queued` or `Building`, and refunds exactly `gold_paid` (credit, reason `building_refund`) and `mats_paid` (returned to storage). Refund is always 100%: building gives nothing until it completes, so a full refund creates no exploit. If the cancelled entry was `Building`, the next `Queued` entry starts in the same P1 (R4). A cancel for a kind with no entry is refused (reason 7). Emits `build_cancelled` (3005).

**R4: Starting a build.** An entry starts when a construction slot is free (`active_count < build_concurrent_max`). Entries start in queue order (the order in which they were accepted, which is command `seq` order, Sim core R6). On start: `state = Building`, `start_tick = N`, `due_tick` from F1. Emits `build_started` (3002).

**R5: Completing a build.** A P5 handler (Sim core R5, anchored deadline) completes every `Building` entry with `due_tick ≤ N`, in ascending `due_tick`, ties by queue order:
1. `level` of that kind becomes `to_level`.
2. The entry is removed; the next `Queued` entry starts (R4) at tick N.
3. Emit `build_completed` (3003). If the kind is `bld_hq`, also emit `guild_level_up` (3004, a guild-wide milestone).

A completed level's effects are in force from tick N + 1: P1–P4 of tick N already ran with the old level. A row with `build_time_min = 0` therefore completes in the P5 of the tick it starts.

**R6: An upgrade keeps the old level working.** While a kind is `Building` from level L to L + 1, every query returns level L's effects. A new building (L = 0) gives nothing until it completes. Nothing is ever closed for construction, because an idle player cannot reopen it and offline resolution would have to model the gap.

**R7: Effects and the one query.** A level row's `effects` is a `map` (Data layer R4), loaded once. Every consumer reads it through:

`effect(building_id, key) → value | none`

It returns the value of `key` in the row for the kind's **effective level** (F4), or `none` if the effective level is 0 or the key is absent from that row. A consumer defines its own behaviour for `none` (normally "the feature is unavailable"), in its own GDD. No consumer reads `buildings.csv`, compares levels itself, or caches a value across ticks (the value can change in any P5).

Two effect values are guild-wide aggregates that this system computes instead of a consumer:
- `member_cap` (F2): the Tổng Đàn's absolute value plus the Trú Xá's (`bld_housing`) additive value.
- `building_slots` (F3): the Tổng Đàn's value.

`guild_level` is the completed `bld_hq` level (R9).

**R8: Arrears decay ("quỹ cạn → buff công trình tắt dần", §19.4).** When the guild fund cannot pay its daily upkeep, building effects fade one effective level at a time; no data is deleted and no level is lost.
- Gold economy (27) reports `upkeep_arrears_days`: the number of consecutive daily upkeep charges not paid in full, reset to 0 by a charge paid in full (PROVISIONAL, OQ-2).
- The effective level of every **decaying key** drops by one per `arrears_days_per_level` arrears days (F4), down to 0.
- **Capacity keys never decay**, because lowering them would orphan existing state (members over the cap, orders in slots, buildings over the slot count): `member_cap`, `building_slots`, `order_slots`, `bounty_slots`, `market_slots`, `train_slots`, `log_slots`, `floor_cap`, `tax_rate_cap`, `rebirth_max`, `phi_thang`. Every other key decays. The set is a constant list in this GDD; a new key is decaying unless this list is amended.
- When arrears clear, the effective level returns to the real level at once (next tick).
- Emits `building_decay_changed` (3007) whenever the decay step (F4 `loss`) changes.

**R9: The guild record.** This system owns the guild's structural fields from §4.1 `Guild`:
- `guild_level`: equals the completed `bld_hq` level (1–8). It is derived and never stored separately.
- `member_cap`: derived (F2).
- `buildings[]`: the level per kind and the build queue.

It does not own `funds` (Gold economy 27), `storage` (Items and loot 26), `market` (Market 29), `quests` (Quests 25), `rivals` (NPC guilds 17) or `fame` (unowned, OQ-6).

**R10: What the player cannot do.** Build two levels of one kind at once; queue a building whose Tổng Đàn requirement is met only by a queued Tổng Đàn upgrade; demolish or downgrade; build a second instance of a kind; speed up a build (no speed-up exists; any paid acceleration is a scope decision, OQ-4); build with member gold (only the guild fund pays, §6.6).

**R11: Registration.** Handlers (Sim core R4, orders allocated in steps of 100 within this system's band): P1 order 3000 (`build`, `cancel_build` validators and appliers), P5 order 3000 (completion, R5; arrears decay step update, R8). Feature fail code (Sim core R10): **30001** `BUILD_ROW_MISSING`, raised if a queue entry's `(building_id, to_level)` has no level row at start or completion (a broken save or content; the validator makes it unreachable for shipped content).

### States and Transitions

Each building kind is in exactly one construction state. The level is a separate integer that only R5 changes.

| State | Meaning | `level` | Effects in force |
|---|---|---|---|
| `Idle` | No entry in the queue | 0 – `max_lv` | Level `level` (F4) |
| `Queued` | Paid, waiting for a construction slot | unchanged | Level `level` |
| `Building` | Under construction, `due_tick` set | unchanged | Level `level` (R6) |

| From | To | Trigger | Phase |
|---|---|---|---|
| `Idle` | `Queued` | `build` accepted, no free construction slot (R2) | P1 |
| `Idle` | `Building` | `build` accepted, a construction slot free (R2, R4) | P1 |
| `Idle` | `Idle` | `build` refused: reason code, nothing taken | P1 |
| `Queued` | `Building` | A construction slot frees (R3, R4, R5) | P1 or P5 |
| `Queued` | `Idle` | `cancel_build`: full refund (R3) | P1 |
| `Building` | `Idle` | `cancel_build`: full refund (R3) | P1 |
| `Building` | `Idle`, `level + 1` | `due_tick ≤ N` (R5) | P5 |

`Idle` at `level = max_lv` is terminal for that kind. No other transition exists: there is no pause, and nothing leaves `Building` except completion or cancel.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Data layer (3) | in | `building_meta`, `buildings` rows (effects as a loaded map, `cost_mats` as a loaded map), liveness query, `config.csv` knobs | — | Data layer |
| Sim core (1) | both | Commands in P1, tick N, `tick_rate` | P1 and P5 handlers (R11) | Sim core owns phases |
| Gold economy (27) | both | Fund balance; `upkeep_arrears_days` (PROVISIONAL) | Debit `building_cost`, credit `building_refund` | Gold economy owns the ledger |
| Items and loot (26) | both | Storage counts per material | Take `cost_mats`; return them on cancel | Items and loot owns storage |
| Event bus (42) | out | — | Events 3001–3007 (F7) | Event bus owns delivery; this system owns its types |
| Recruitment (15) | out | — | `member_cap` (F2); `effect(bld_scout, …)` | Recruitment owns the "roster full" refusal |
| Equipment enhancement (24) | out | — | `effect(bld_enhance, max_enhance_lv)` | Enhancement |
| Crafting (28) | out | — | `max_craft_tier`, `craft_speed_mult` of `bld_smith`, `bld_jeweler`, `bld_alchemy` | Crafting |
| Market (29) | out | — | `market_slots`, `tax_rate_cap` (`bld_market`); `order_slots` (`bld_trade`) | Market |
| Gold economy (27) | out | — | `daily_interest_pct` (`bld_bank`), `tax_rate_cap` | Gold economy owns the interest and tax credits |
| Member state / needs (8, 16, 41) | out | — | Restaurant, tavern, inn, infirmary, training multipliers | Each consumer |
| Schools (20) | out | — | `bld_academy_skill` level | Schools |
| Combat (10), XP curve (22) | out | — | `atk_pct`, `hp_pct`, `xp_pct` (buff buildings) | Each consumer |
| Rebirth (23) | out | — | `bld_shrine` effects | Rebirth |
| Retention (16) | out | — | Building levels and `build_completed` (a "build X" stay condition, §6.8) | Retention |
| Offline progress (31) | out | — | Due ticks crossed by a gap (Edge Cases) | Offline owns crossed due ticks (Sim core R5) |
| Guild screens (39) | out | — | Levels, queue, costs, refusal reasons, previews | Guild screens |

## Formulas

### F1 — `build_due_tick`

The build_due_tick formula is defined as:

`build_due_tick = start_tick + build_time_min × 60 × tick_rate`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| start_tick | int | ≥ 0 | calculated | Tick N in which the entry started (R4) |
| build_time_min | int | 0 – 10,080 | data file (`buildings.csv`) | Build time of the target level row, in game minutes. Today 0 – 3,840 |
| tick_rate | int | divides 1,000,000 | data file (`config.csv`, Sim core R1) | Ticks per second, 10 today |

**Output Range:** `start_tick` to `start_tick + 6,048,000` at the validator cap of 10,080 min (7 days); today's longest row (`bld_hq` 8, 3,840 min) is 2,304,000 ticks. Integer arithmetic only; no overflow below 2^62.
**Example:** Thiện Đường level 3 (14 min) started at tick 1,000 is due at 1,000 + 14 × 60 × 10 = 9,400.

### F2 — `member_cap`

The member_cap formula is defined as:

`member_cap = cap_hq(eff_hq) + cap_housing(eff_housing)`, where `cap_housing(0) = 0`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| cap_hq | int | 12 – 40 | data file (`bld_hq` `member_cap`) | Absolute base cap at the Tổng Đàn's level |
| cap_housing | int | 0 – 40 | data file (`bld_housing` `member_cap`) | Additive cap of Trú Xá (written `+4`…`+40`; the sign is cosmetic, OQ-7) |
| eff_hq, eff_housing | int | 1 – 8, 0 – 10 | calculated | Levels; `member_cap` is a capacity key, so it never decays (R8) |

**Output Range:** 12 (new guild) to 80 (Tổng Đàn 8 + Trú Xá 10). MVP has no Trú Xá: 12 / 16 / 20 at Tổng Đàn 1 / 2 / 3.
**Example:** Tổng Đàn 3 (20) + Trú Xá 4 (+16) = 36.

### F3 — `slots_used` and `building_slots`

The slot formula is defined as:

`slots_used = |{ k ≠ bld_hq : level_k ≥ 1 }| + |{ queue entries with to_level = 1 }|`; a new building needs `slots_used + 1 ≤ building_slots(eff_hq)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| level_k | int | 0 – max_lv | calculated | Completed level of kind k |
| building_slots | int | 9 – 30 | data file (`bld_hq` `building_slots`) | Slots at the Tổng Đàn's level |

**Output Range:** `slots_used` 0 – 25 (25 non-HQ kinds; 23 in Wave 1). Slots bind from Tổng Đàn 1 (9) to 6 (24); from Tổng Đàn 7 (27) every kind fits. A queued new building holds its slot, so cancelling it frees the slot.
**Example:** Tổng Đàn 1 (9 slots), 8 buildings built and 1 new build queued: `slots_used = 9`, so a tenth new building is refused (reason 5) until Tổng Đàn 2 (12).

### F4 — effective level under arrears

The effective_level formula is defined as:

`loss = floor(upkeep_arrears_days / arrears_days_per_level)`; `effective_level(k, key) = level_k` if `key` is a capacity key (R8), else `max(0, level_k − loss)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| upkeep_arrears_days | int | ≥ 0 | calculated (Gold economy 27, PROVISIONAL) | Consecutive unpaid daily upkeep charges |
| arrears_days_per_level | int | 1 – 30 | data file (`config.csv`) | Arrears days per level of decay; default 1 |
| level_k | int | 0 – 11 | calculated | Completed level |

**Output Range:** 0 to `level_k`. At 0 arrears, `effective_level = level_k` exactly, so a solvent guild never sees decay. Every kind decays to 0 after at most `11 × arrears_days_per_level` days (11 days at default) and nothing is deleted. Division by zero is impossible (validator: `arrears_days_per_level ≥ 1`).
**Example:** Luyện Khí Đài level 6 (`max_enhance_lv` 12) after 2 arrears days: effective level 4, so `max_enhance_lv` is 8 until the fund pays a full charge. Items already at +12 keep their level; only new attempts above +8 are refused (Equipment enhancement owns that rule).

**Feedback loop.** Decay is a negative-for-the-player loop (broke → weaker buildings → slightly weaker members). It is damped because guild income does not come from buildings: from MVP it is a flat member tax on hunting income at `guild_tax_pct` 10% (Gold economy R6; user decision 2026-11-16) plus the fund's share of members' shop purchases (Gold economy R7, `shop_fund_share_pct` 0.3); upkeep is ≈ 3% of AFK income (§19.4); arrears need a fund spent to zero (or, from Vertical Slice when the player has the tax slider, tax set near 0). Capacity keys are exempt so the loop can never evict a member or delete an order.

### F5 — build cost and time totals (balance reference)

The total cost formula is defined as:

`total_gold(k) = Σ_{L=2 if k=bld_hq else 1}^{max_lv} cost_gold(k, L)`; `total_time_min(k)` likewise over `build_time_min`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| cost_gold | int | ≥ 0 | data file (`buildings.csv`) | Gold per level row |
| cost_mats | map(ref(materials), int) | counts ≥ 1 | data file | Materials per level row |
| build_time_min | int | 0 – 10,080 | data file | Minutes per level row |

**Output Range:** all 26 kinds: 44,213,601 gold and 36,326 min (25.2 days with one construction slot), matching §19.4's "44.2 M". Tổng Đàn alone is 32,947,000 gold (74.5%) and 7,620 min. The five MVP kinds: Tổng Đàn 32,947,000; Dược Phòng 905,257; Luyện Khí Đài 680,119; Chợ Bang 408,071; Thiện Đường 306,052.
**Example:** reaching Tổng Đàn 3 costs 2,000 + 15,000 = 17,000 gold, 20 `mat_z04_1` + 30 `mat_z06_1`, and 180 min.

*Lens applied:* systems and economy design (`references/lens-systems-designer.md`). Cost check against §19.1 (income ≈ 1,000 × level gold/h/member) and §19.4 (10% tax): a 5-member guild at level 20 yields ≈ 10,000 gold/h of tax, so Tổng Đàn 3 (15,000) is ≈ 1.5 h of tax and Tổng Đàn 8 (25 M) is ≈ 11.5 days of tax for 20 members at level 70, as §19.4 states. (These "hours of tax" hold in MVP: a flat 10% tax is live from MVP (Gold economy R6, user decision 2026-11-16), and the 30% shop-sale share (Gold economy R7/F2) comes on top, so the fund gets ≈ 17% of member income and buildings may complete faster than §19.4's figures; S3 measures it. The player's tax slider, bounded by `tax_rate_cap`, arrives in Vertical Slice.) Non-HQ kinds grow ×1.9 per level (a geometric curve); a kind's last level costs ≈ 47% of that kind's total (Thiện Đường: 145,209 of 306,052), so "max one building" is a sink, not a trap. No building is strictly better at the same price, because each kind feeds a different consumer. The dominant purchase is the Tổng Đàn, by design: it gates everything. Faucet check: buildings produce no gold, except Tiền Trang interest, which Gold economy owns and must cap (OQ-3). Boundary run: `build_time_min = 0` completes in the start tick's P5 (R5); `cost_gold = 0` is a free order (valid); `max_lv = 0` is rejected by the validator.

### F6 — refund

`refund_gold = gold_paid`, `refund_mats = mats_paid` (exact amounts recorded at the order, R2). Range: the paid amount; never more. Because the entry stores what was paid, a content patch that changes `cost_gold` between order and cancel cannot mint or destroy gold (Edge Cases).

### F7 — event volume (Event bus F1, F4)

The event volume formula is defined as:

`ring_per_day(build_completed) = building_events_ring_per_day`, `ring_per_day(building_decay_changed) = 4`, every other type here has `ring_per_day = 0`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| building_events_ring_per_day | int | 60 | constant | Declared peak ring records per 86,400 game seconds |
| type block | int | 3000 – 3099 | constant | This system's Event bus type IDs (block = system number × 100) |

**Output Range:** the seven types are 3001 `build_queued(building_uid, to_level, queue_pos)` (not logged), 3002 `build_started(building_uid, to_level, due_tick)` (not logged), 3003 `build_completed(building_uid, new_level)` (ring), 3004 `guild_level_up(new_level)` (milestone, subject 0), 3005 `build_cancelled(building_uid, to_level)` (not logged), 3006 `build_refused(building_uid, reason_code)` (not logged), 3007 `building_decay_changed(loss)` (ring). Building IDs travel as content `uid`s (Data layer R6). Order and cancel events are not logged, so an order-cancel loop cannot flood the ring. Completions are bounded by content: 235 buildable rows in the whole game, and with one construction slot and the shortest row at 5 min, fewer than 60 a day are reachable even on day one (early rows take 5–14 min plus the time to afford them). `guild_level_up` adds at most 7 milestones per save, 3.5% of `milestone_cap_guildwide` (200). Decay changes at most once per arrears day, and the declared 4 allows for clearing and re-entering arrears.
**Reason codes** (payload of 3006): 1 not available, 2 at max level, 3 already queued, 4 queue full, 5 no slot, 6 Tổng Đàn level too low, 7 nothing to cancel, 8 not enough gold, 9 not enough materials. When several fail, the lowest code is reported.

## Edge Cases

- **If a `build` and a `cancel_build` for the same kind arrive in one tick**: they apply in command `seq` order (Sim core R6). Cancel-then-build refunds and re-pays; build-then-cancel refunds the order just made. Either way the net ledger is zero or one order.
- **If two orders in one tick compete for the last gold or the last slot**: the earlier `seq` is accepted, the later is refused with reason 8 or 5. Each order's checks see the state left by the previous one.
- **If two builds are due in the same tick**: they complete in ascending `due_tick`, ties by queue order (R5). With `build_concurrent_max = 1` this cannot happen; it matters only when the knob is raised.
- **If an offline gap crosses one or more due ticks**: Offline progress (31) owns every due tick a gap crosses (Sim core R5). It must complete those builds at their due ticks, start the next queued entry at each completion tick, and use the new level's effects in the aggregate resolver from the tick after each completion. A full queue therefore finishes offline in sequence, and the player returns to all of it built (Player Fantasy 1). PROVISIONAL until Offline progress is designed (OQ-5).
- **If the Tổng Đàn completes while a building that needs it is still refused**: nothing is retried automatically. Orders are never held for prerequisites; the player orders again (R2.4, R10).
- **If a queued Tổng Đàn upgrade is cancelled**: nothing else is affected, because no queue entry was accepted on the strength of a queued Tổng Đàn level (R2.4).
- **If the fund is at exactly `cost_gold`**: the order is accepted and the fund goes to 0. The next daily upkeep charge may then fail and start arrears (R8); that is the player's trade-off, and the build screen warns when an order would leave less than one day's upkeep (UI Requirements 3).
- **If the guild is in arrears**: building orders are still allowed if the fund can pay. Paying a build does not clear arrears; only a full upkeep charge does (Gold economy).
- **If arrears decay takes the effective level to 0**: the effect query returns `none` exactly as if the building were not built; the real level, slot and queue are untouched, and members, orders and items already above a decayed limit keep what they have.
- **If a cancel's material refund would exceed storage capacity**: the materials are returned in full, over the cap (Items and loot R7: storage is uncapped and `give` always succeeds). Nothing paid is ever lost.
- **If content changes between order and completion** (a patch changes `cost_gold`, `build_time_min` or `effects`): the paid amount stays as recorded (F6); the `due_tick` stays as computed at start; the effects at completion are the new row's. If the target row no longer exists, the core fails with 30001 (R11); the validator's append-only rule (Data layer R3, R6) makes this unreachable for shipped content.
- **If a built kind is retired** (`retired = true`): it keeps its level and its effects, cannot be upgraded further, still uses its slot, and is shown as "legacy". Retiring must never take a feature away from an existing save.
- **If `max_lv` grows in a later wave**: new level rows become orderable when live; existing levels are unaffected.
- **If the member count is above `member_cap`** (only possible through a content change lowering `cap_hq`, since `member_cap` never decays): no member is removed; Recruitment refuses new members until the count is below the cap.
- **If the player orders the 30-day-long build at the validator cap**: allowed; one construction slot means everything else waits behind it, which the queue view shows (UI Requirements 2).
- **Degenerate strategy check:** no loop yields gold (refund = payment, F6; buildings produce no gold except Bank interest, which Gold economy caps, OQ-3). Building only the Tổng Đàn is possible but leaves every consumer at `none`, so it is not dominant. Queue-and-cancel spam is bounded by the command queue and produces no logged history (F7).

## Dependencies

### Upstream (this system depends on)

| System (#) | Hard / soft | Interface | What this system takes |
|---|---|---|---|
| Data layer and content pipeline (3) | Hard | `building_meta`, `buildings` (effects and `cost_mats` as loaded maps), liveness query (F2), `config.csv` knobs | Every building definition and tuning value. Data layer already lists this system downstream ("Building meta and per-level rows") |
| Sim core and tick loop (1) | Hard | P1 commands, P5 anchored deadline ticks, `tick_rate`, `ctx.fail` code 30001 | When orders apply and builds complete |
| Gold economy (27) | Hard (PROVISIONAL, not yet designed) | `balance()`, `debit(amount, reason)`, `credit(amount, reason)` with reasons `building_cost` and `building_refund`; `upkeep_arrears_days` | Paying for builds; refunds; the R8 decay input |
| Items and loot tables (26) | Hard (PROVISIONAL, not yet designed) | `count(material_id)`, `take(map)`, `give(map)` accepting returns over cap | Material costs and refunds |
| Event bus and history log (42) | Hard | `register_type` for block 3000–3099, `ctx.emit` | Delivery of F7 events. Event bus covers "feature systems that emit (8–30, 41)" |
| Command layer (5) | Hard (PROVISIONAL) | `build(building_id)`, `cancel_build(building_id)` commands | The only path from the player to R2/R3 |

The systems index row lists Sim core, Data layer and Gold economy. Items and loot (storage), Event bus and Command layer are also hard upstream dependencies; Phase 5 proposes adding them to the index row.

### Downstream (systems that depend on this one)

| System (#) | Hard / soft | Interface | What it gets |
|---|---|---|---|
| Recruitment (15) | Hard | `member_cap` (F2); `effect(bld_scout, pa_error / candidate_extra)` | The roster limit; scout quality (Vertical Slice) |
| Equipment enhancement (24) | Hard | `effect(bld_enhance, max_enhance_lv)` | The enhancement cap (§19.3) |
| Crafting and recipes (28) | Hard | `max_craft_tier`, `craft_speed_mult` of smith, jeweler, alchemy | Recipe tier gate (`ceil(tier/2)`, §17.1) and craft speed |
| Guild market and trade orders (29) | Hard | `market_slots`, `tax_rate_cap`, `order_slots` | Market and order capacity |
| Golden Boss and guild raid (14) | Soft | Building effects on members (buff buildings) | Raid strength (index lists this dependency) |
| Quests and achievements (25) | Soft | `build_completed`, `guild_level_up`; `bounty_slots`, `bounty_reward_mult` | "Upgrade a building" quests (§11.4); bounty capacity |
| Schools and school change (20) | Soft | `bld_academy_skill` level | School change gate (Schools R4.4); Academy not in MVP (Schools OQ-1) |
| Jianghu free agents and NPC guilds (17) | Soft | `guild_level`, building levels | NPC guild comparison (index lists this dependency) |
| Retention (16), Member state machine (41), XP curve (22), Combat (10), Rebirth (23), Endless Tower (19), Arena (18) | Soft | Their building effects through `effect()` | Each consumer's multiplier or cap |
| Offline progress (31) | Hard | Due ticks and effect changes inside a gap | Completing builds offline in order |
| Guild screens (39) | Hard | Levels, queue, costs, previews, refusal reasons | The building screen |
| Local save and migration (6) | Hard | Levels per kind; queue entries with paid amounts and ticks | What to persist |
| AI text layer / Chronicle (36) | Soft | `guild_level_up` milestone | The guild's growth in the Chronicle |

**Bidirectional status.** Data layer (3) lists this system. Event bus (42) covers it generically. Schools (20) lists this system, but expects guild storage here (its Dependencies row and assumption 3); storage belongs to Items and loot (26) per the systems index, so the consistency pass should repoint Schools' storage interface to 26 (OQ-8). Every other system above is undesigned and must list this system when designed.

**Provisional assumptions about undesigned systems:**
1. Gold economy (27) exposes `balance`, `debit`, `credit` with reason tags, never lets the fund go below 0, and reports `upkeep_arrears_days` as defined in R8.
2. Items and loot (26) exposes storage `count`, `take`, `give`, and accepts system returns over its cap.
3. Command layer (5) delivers `build` and `cancel_build` as P1 commands with `seq` order.
4. Offline progress (31) completes builds at their due ticks inside a gap and starts queued entries in order.
5. Each effect consumer defines its own behaviour for `none` (building not built or decayed to 0).

## Tuning Knobs

*Lens applied:* systems design, Section G. Every `data file` variable in Section D is a knob; per-row content values are tuned in the CSVs, the rest are `config.csv` rows read once at load. All defaults are provisional until the balance sim (S3) measures gold flow.

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `build_concurrent_max` (`config.csv`, new) | 1 | 1 – 3 | Builds stop being a decision; 25-day build track collapses to ~8 days; gold becomes the only limit | 1 is the minimum | `build_time_min` (total serial time, F5); `build_queue_max` |
| `build_queue_max` (`config.csv`, new) | 2 | 0 – 5 | Player fills a long queue and stops returning (less engagement); more paid-up gold sits idle | 0: no queue, the player must return at every completion (hostile for an idle game) | `build_concurrent_max`; offline cap (8 h Free) |
| `arrears_days_per_level` (`config.csv`, new) | 1 | 1 – 30 | Arrears have no visible consequence (§19.4's pressure lost) | 1 is the minimum (fastest decay) | Gold economy upkeep and tax knobs (`guild_upkeep_per_level_day`, `guild_tax_pct`) |
| `cost_gold` per row (`buildings.csv`) | per row | ≥ 0 | Building track outlasts the content (Tổng Đàn 8 already ≈ 11.5 days of tax) | Gold inflates (§18.3) | §19.5 out/in 60–90% target; income per level (§19.1) |
| `cost_mats` per row | per row | counts ≥ 1, live materials | Hunting for one material gates the guild | Materials lose a sink | Zone access: Luyện Khí Đài 1 needs `mat_z06_1` (OQ-9) |
| `build_time_min` per row | per row | 0 – 10,080 | Long silent waits; offline cap ends before builds do | Builds feel weightless (Player Fantasy 1 lost) | `build_concurrent_max`, offline cap |
| `hq_lv_req` per row, `unlock_hq_lv`, `max_lv` (`building_meta`) | per row | 1 – 8; non-decreasing per kind | Buildings unlock late | Tổng Đàn stops gating | `building_slots` (F3) |
| `effects` per row | per row | per consumer | — | — | Owned by each consumer's GDD for meaning and safe range |

**Not knobs here:** `tick_rate` (Sim core), `guild_upkeep_per_level_day` and `guild_tax_pct` (Gold economy, `config.csv` today), `income_ref_per_level` (Gold economy), `milestone_cap_guildwide` (Event bus). The capacity-key list (R8) and `building_events_ring_per_day` (F7) are design constants.

**Validator rules for the Data layer** (owned here, enforced by the content validator, Dev tooling 43):
1. Each kind's level rows are exactly 1 … `max_lv`, contiguous; `max_lv ≥ 1`.
2. `building_meta.unlock_hq_lv` equals the kind's level-1 `hq_lv_req`.
3. `hq_lv_req` is non-decreasing with level and ≤ `bld_hq.max_lv`; for `bld_hq`, `hq_lv_req = level`.
4. `bld_hq` level 1 has `cost_gold = 0`, no `cost_mats` and `build_time_min = 0`, and its effects include `member_cap` and `building_slots`.
5. `build_time_min` is 0 – 10,080; `cost_gold ≥ 0`; every `cost_mats` key is a material of equal or earlier wave (Data layer F3).
6. Every effect key is in the known key list (the keys in `buildings.csv` today); a new key needs a consumer GDD.
7. `building_slots(bld_hq.max_lv) ≥` the number of non-HQ kinds of the final wave (30 ≥ 25 today), so every kind is buildable at the top.
8. `arrears_days_per_level ≥ 1`, `build_concurrent_max ≥ 1`, `build_queue_max ≥ 0`.

## Visual/Audio Requirements

Economy category: optional; written briefly because the system has a visible base on the map.
- **Each built kind is visible on the guild map** (Realtime world view 38), with a distinct look per level band (for example 1–3, 4–7, 8+) rather than per level, to keep the art budget solo-sized (§7 "gộp để giảm art/scene").
- **Construction is visible:** scaffolding or a marker on the building while `Building`, with the time remaining on tap.
- **Completion gets a short beat** (visual and sound); `guild_level_up` gets a larger one. Both are suppressed during catch-up (Sim core R15) and summarised in the "while you were away" report instead.
- **Decay is shown without colour alone:** a decayed building gets an icon and a "−N levels (unpaid upkeep)" label.

No art bible exists, so no art-bible principle is cited (`art-director` lens applied from §7 and §12.4 only).

## Game Feel

Not a feel system. Its timing promises:
- An order or cancel is acknowledged in the UI at once and applied in P1 of the next tick (≤ 100 ms at 10 Hz).
- A build completes exactly at its due tick, including across an offline gap (F1, Edge Cases).
- A refused order always shows its reason in words (F7 reason codes), never a silent no-op.

## UI Requirements

Guild screens (39) own the screens; this system needs:
1. **Building list**: every available kind with its level / `max_lv`, state, and the next level's cost (gold and materials, with the guild's holdings shown beside each), time, Tổng Đàn requirement and slot need. Unbuildable entries show why (reason codes 1–9) before the player taps.
2. **Queue view**: the active build with its time remaining and the queued entries in order, each with a cancel button that states the full refund.
3. **Order confirm**: shows the cost, the time, and a warning when the order would leave the fund below one day's upkeep (Edge Cases).
4. **Effect preview**: the current and next level's effects in words, through `i18n/` keys per effect key, showing what the player gains (Player Fantasy 3).
5. **Guild header**: guild level (Tổng Đàn level), member count / `member_cap`, slots used / `building_slots`.
6. **Decay notice**: when `loss > 0`, which buildings are weakened, by how much, and that paying upkeep restores them at once.

Every string goes through Localization (4).

> **📌 UX Flag — Guild and buildings**: This system has UI requirements. Run `/ux-design` for the building screen before writing epics.

## Cross-References

| This document references | Target | Element | Nature |
|---|---|---|---|
| `building_meta`, `buildings` tables; packed `effects`/`cost_mats` loaded as maps | `data-layer-and-content-pipeline.md` | R2, R4 | Data dependency |
| Liveness query; no forward references; append-only IDs and `uid`s | `data-layer-and-content-pipeline.md` | R3, R5, R6, F2, F3 | Rule dependency |
| Display names in `i18n/` | `data-layer-and-content-pipeline.md` | R9 | Rule dependency |
| Phases P1/P5, command `seq` order, handler registration orders in steps of 100 | `sim-core-and-tick-loop.md` | R2, R4, R6 | Rule dependency |
| Anchored deadline ticks; Offline owns crossed due ticks | `sim-core-and-tick-loop.md` | R5 | Rule dependency (F1, Edge Cases) |
| `tick_rate` | `sim-core-and-tick-loop.md` | R1 | Data dependency (F1) |
| Feature fail codes ≥ 1000 | `sim-core-and-tick-loop.md` | R10 | Rule dependency (30001) |
| Type blocks of 100, `ring_per_day`, milestones, subject 0 | `event-bus-and-history-log.md` | R3, R3a, F4 | Rule dependency (F7) |
| Academy level gate for school change; storage assumption | `schools-and-school-change.md` | R4.4, Dependencies assumption 3, OQ-1 | State trigger; ownership mismatch (OQ-8) |
| EHT building map and new building names | `JX1_Tycoon_GDD.md` | §7 | Source of intent |
| Upkeep, buildings as sink, "buffs fade when the fund is empty", 44.2 M total | `JX1_Tycoon_GDD.md` | §19.4 | Source of intent (R8, F5) |
| MVP five buildings | `JX1_Tycoon_GDD.md` | §21 Prompt P3; systems index MVP cuts | Scope |
| Build queue in the S3 economy module | `JX1_Tycoon_GDD.md` | §20 S3 | Reference implementation still to write |

## Acceptance Criteria

*Lens applied:* QA (`references/lens-qa-lead.md`). [Logic] = automated unit test in `tests/unit/guild_and_buildings/` (and the Python reference); [Integration] = automated multi-system test; [UI] = screenshot.

- **AC-1 [Logic] (R1)**: **GIVEN** a new guild, **WHEN** it is created, **THEN** `bld_hq` is level 1, every other kind is level 0, the queue is empty, `member_cap = 12` and `building_slots = 9`.
- **AC-2 [Logic] (R2, F1)**: **GIVEN** Tổng Đàn 1, fund 1,000, storage with 6 `mat_z02_1`, an empty queue, **WHEN** `build(bld_restaurant)` applies in tick 100, **THEN** the fund is 550, storage holds 0 `mat_z02_1`, the entry is `Building` with `due_tick = 100 + 5 × 60 × 10 = 3,100`, and events 3001 and 3002 are emitted.
- **AC-3 [Logic] (R5)**: **GIVEN** the AC-2 entry, **WHEN** ticks run to 3,100, **THEN** in tick 3,099 `effect(bld_restaurant, satiety_mult)` is `none`, in tick 3,100's P5 the level becomes 1 and 3003 is emitted, and from tick 3,101 the query returns 1.1.
- **AC-4 [Logic] (R2.4)**: **GIVEN** Tổng Đàn 2 completed and Tổng Đàn 3 queued, enough gold and materials, **WHEN** `build(bld_enhance)` (needs Tổng Đàn 3) applies, **THEN** it is refused with reason 6 and the fund and storage are unchanged.
- **AC-5 [Logic] (R2.5, F3)**: **GIVEN** Tổng Đàn 1 with 8 non-HQ kinds built and 1 new build queued, **WHEN** a new building is ordered, **THEN** it is refused with reason 5; **AND WHEN** an upgrade of a built kind is ordered with enough funds, **THEN** it is accepted.
- **AC-6 [Logic] (R2.2, R2.3)**: **GIVEN** `build_concurrent_max = 1`, `build_queue_max = 2` and one entry each for three kinds, **WHEN** a fourth kind is ordered, **THEN** reason 4; **AND WHEN** a second order for a queued kind is made, **THEN** reason 3.
- **AC-7 [Logic] (R2.6)**: **GIVEN** a fund of `cost_gold − 1`, **WHEN** the build is ordered, **THEN** reason 8 and nothing changes; **GIVEN** a fund of exactly `cost_gold` and the materials, **THEN** it is accepted and the fund is 0.
- **AC-8 [Logic] (R3, F6)**: **GIVEN** an entry paid 1,140 gold and 10 `mat_z04_1`, after which `cost_gold` in content is changed to 2,000, **WHEN** it is cancelled, **THEN** exactly 1,140 gold and 10 `mat_z04_1` return, the ledger nets to zero, and the next queued entry starts in the same tick.
- **AC-9 [Logic] (R4, R5)**: **GIVEN** three entries accepted in `seq` order A, B, C with one construction slot, **WHEN** all complete, **THEN** they complete in order A, B, C, each starting in the tick the previous completed, and the total elapsed ticks equal the sum of their F1 durations.
- **AC-10 [Logic] (R6)**: **GIVEN** Luyện Khí Đài level 2 upgrading to 3, **WHEN** queried during construction, **THEN** `max_enhance_lv = 4` (level 2), and 6 from the tick after completion.
- **AC-11 [Logic] (R8, F4)**: **GIVEN** Luyện Khí Đài 6, Tổng Đàn 3 and `arrears_days_per_level = 1`, **WHEN** `upkeep_arrears_days` is 2, **THEN** `effect(bld_enhance, max_enhance_lv) = 8`, `member_cap` is still 20, `building_slots` still 15, and 3007 was emitted with `loss = 2`; **WHEN** arrears reset to 0, **THEN** from the next tick `max_enhance_lv = 12`.
- **AC-12 [Logic] (F4 boundary)**: **GIVEN** a level-3 building and arrears of 50 days, **WHEN** queried, **THEN** a decaying key returns `none` and the stored level is still 3.
- **AC-13 [Logic] (F2)**: **GIVEN** Tổng Đàn 3 and Trú Xá 4, **THEN** `member_cap = 36`; **GIVEN** Tổng Đàn 8 and Trú Xá 10, **THEN** 80.
- **AC-14 [Logic] (Edge Cases, ordering)**: **GIVEN** a fund for exactly one build and two orders in one tick, **WHEN** P1 applies them, **THEN** the lower `seq` is accepted and the other is refused with reason 8.
- **AC-15 [Integration] (Edge Cases, offline; with Offline progress 31)**: **GIVEN** a queue of three entries totalling 3 h and an 8 h offline gap, **WHEN** the gap is resolved, **THEN** the result is identical to running the same 8 h live tick by tick: same levels, same completion ticks, same ledger (determinism test, Sim core).
- **AC-16 [Integration] (S3 conservation; with Gold economy 27)**: **GIVEN** a seeded 30-day balance-sim run with orders and cancels, **WHEN** the ledger is summed, **THEN** total `building_cost` debits − total `building_refund` credits equals the sum of `cost_gold` over completed and in-progress entries.
- **AC-17 [Logic] (F7)**: **GIVEN** a booted bus, **WHEN** types are sealed, **THEN** 3001–3007 are registered under owner `guild_and_buildings` with the logged/milestone flags of F7, and 3004 has `subject_slot = 0`; 100 order-cancel pairs add 0 ring records.
- **AC-18 [Logic] (validator)**: **GIVEN** a `buildings.csv` copy with a gap in a kind's levels, or `unlock_hq_lv` ≠ level-1 `hq_lv_req`, or an unknown effect key, **WHEN** the validator runs, **THEN** it exits 1 naming the file, row and column; on today's data it reports 0 errors for these rules.
- **AC-19 [UI]**: **GIVEN** the building screen in the slice, **WHEN** it shows a kind the guild cannot build, **THEN** the reason is shown in words; a retained screenshot of the list, the queue and the order confirm is in `production/qa/evidence/`.

Performance: the effect query is O(1) (indexed by kind and level at load); the P5 handler is O(active entries) ≤ `build_concurrent_max` per tick.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | MVP has five buildings. How are the other 21 held back in the slice: a slice-only content set, a config allow-list, or wave flags (all 24 are wave 1 today)? Scope decision, not made here | Producer, Data layer (3) | Before MVP sprint planning |
| OQ-2 | **RESOLVED (consistency-check 2026-11-16):** Gold economy R4/R8 — non-negative balances, typed `debit`/`credit` (`building_cost`, `building_refund`), and `upkeep_arrears_days` (consecutive short daily charges, reset by a full one) as defined here. | Gold economy (27) | Closed |
| OQ-3 | Tiền Trang `daily_interest_pct` up to 1.6%/day on the fund is a faucet that compounds; Gold economy must cap it (or base it on a bounded amount) | Gold economy (27) | When its GDD is written |
| OQ-4 | Is any build speed-up wanted (Linh Bảo, ads, items)? §19 forbids real-money buying of sinks; none is designed. Scope decision | Producer, IAP (34), Ads (33) | Before Alpha |
| OQ-5 | PROVISIONAL: Offline progress (31) — completes builds at their due ticks and starts queued entries in order inside a gap, using new effects from the tick after | Offline progress (31) | When its GDD is written |
| OQ-6 | Guild `fame` (§4.1, used by recruitment §6.7) has no owner in the systems index. Assign it (here, Recruitment or Quests)? Scope decision | Producer, systems index | Before Recruitment is designed |
| OQ-7 | `bld_housing` writes `member_cap=+4`; the `+` is cosmetic under F2. Drop it from the data so the map parses as a plain int in both ports | Data layer (3) | Next data pass |
| OQ-8 | Schools (20) expects guild storage from this system (Dependencies, assumption 3). Storage belongs to Items and loot (26); repoint Schools' storage interface in the consistency pass | Consistency check | Next `/consistency-check` |
| OQ-9 | Luyện Khí Đài 1 needs Tổng Đàn 3 (`mat_z06_1` × 30 plus `mat_z04_1` × 20 for Tổng Đàn 2) and its own `mat_z06_1` × 6. A one-ground slice cannot reach it unless that ground is in zone 6 or the slice data changes. Scope decision for the slice | Producer, Zones (11) | Before the P3 slice |
| OQ-10 | What do Chợ Bang and Dược Phòng do in MVP, when Market (29) and Crafting (28) are Vertical Slice? A stand-in shop is implied by P3 but not designed | Producer, Items and loot (26) | Before MVP sprint planning |
| OQ-11 | **RESOLVED (consistency-check 2026-11-16):** Items R7 — storage exposes `count`/`take` (all-or-nothing)/`give`, and is uncapped, so every return fits. | Items and loot (26) | Closed |
| OQ-12 | PROVISIONAL: Command layer (5) — `build` and `cancel_build` arrive as P1 commands in `seq` order | Command layer (5) | When its GDD is written |
| OQ-13 | Resolved 2026-11-16: systems index row 30 now lists Items and loot, Event bus and Command layer. The design-order list (§ "Design order", item 9) still names only Sim core, Data layer and Gold economy | Systems index owner | Next `/map-systems` pass |
| OQ-14 | §20 S3 (`sim/economy_full.py`) must implement the build queue to this GDD before the balance sim tunes F5 and the knobs | Dev tooling (43) | Before balance tuning |
