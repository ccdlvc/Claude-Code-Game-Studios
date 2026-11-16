# Guild Market and Trade Orders

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run, decisions logged)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against (`design/gdd/game-concept.md`, `game-pillars.md` and `design/game-brief.md` are all absent)
> **Implements Pillar**: None (no game-pillars.md yet). Serves GDD §1 (the guild "bán/chế tạo" step of the loop), §6.5 (boss loot sold at Chợ Bang), §6.6 (members spend surplus gold on guild-exclusive goods), §7 (Chợ Bang, Thương Hội) and §20 S3

## Summary

Guild market and trade orders is where the guild sells and commissions: the Chợ Bang's stalls sell catalogue gear and the guild's own stock (Golden Boss loot, crafted and displaced gear) to members for their wallet gold, and the Thương Hội posts material orders whose bounty, paid from the guild fund, steers hunters toward what the build plan needs. It gives member gold a place to go back to the fund (§6.5, §6.6) and gives the guild master a lever on what gets hunted (§7), while minting no gold: every sale and bounty is a ledger transfer or an existing shop sale.

> **Quick reference** — Layer: `Feature` · Priority: `Vertical Slice` · Key deps: `Items and loot tables, Gold economy, Guild and buildings, Member model, Utility AI (provisional), Command layer, Sim core, Event bus`

## Overview

**Data layer.** This system runs two guild buildings' trade rules inside the headless simulation. The **Chợ Bang** (`bld_market`, GDD §7: the four EHT shops merged into one building) has `market_slots` stalls (9 at level 1, 36 at level 10). Each stall holds one **line**: either a *catalogue line* (one equipment family, sold without limit at the `items.csv` price, the "Chợ Bang gear" shop sale of Gold economy R7) or a *stock listing* (units the guild already holds in storage — Golden Boss loot, crafted goods, displaced gear — sold at a price the player sets, which drifts slowly down if nobody buys). Members buy from stalls with their own wallet gold. The **Thương Hội** (`bld_trade`) holds `order_slots` **trade orders** (1–5): the player asks for N units of one material and promises a bounty per unit from the guild fund; members steer their hunting toward it, and every matching unit handed in pays the bounty to the party that brought it. All amounts are int64 gold moved through the Gold economy ledger; all goods move through Items and loot storage. This system owns the stalls, the orders, their prices and bounties, and the rules for when a purchase or a delivery is legal — never a balance and never a storage count.

**Player impact.** This is where the guild master *sells* and *commissions*. Golden Boss loot becomes something members can buy (GDD §6.5: "thành viên mua bằng tiền hoặc bang chủ chỉ định trao"), so a member's surplus gold flows back to the fund instead of piling up (§6.6), and the master's stocking choices decide which schools find their weapons at home. Trade orders give the master a way to say "we need Zone 6 ore for the Tổng Đàn" without micromanaging parties: they cost fund gold and buy speed. Without this system, member wallets have nowhere to go but consumables, boss loot can only be handed out for free, and the build plan waits on whatever the hunters happen to bring home.

**Scope.** Market is Vertical Slice (systems index row 29). It does **not** own item prices or sell values (Items and loot 26), the ledger or tax (Gold economy 27 — including the tax cap `tax_rate_cap`, which the Chợ Bang's level supplies but Gold economy applies), building levels and their effect values (Guild and buildings 30), or *whether* a member wants to buy or which ground a party picks (Utility AI 12). Crafting (28) puts goods into storage; this system only sells what is there. Implementation choices (a market resource, an order list) become an ADR.

## Player Fantasy

**Both.** The player acts directly — stocks stalls, sets prices, posts orders — and feels the result indirectly, through members who buy and hunters who come home with the ore the guild asked for.

*Lens applied: creative-director (Section B). No pillars, concept or brief exist (`design/gdd/game-pillars.md`, `game-concept.md`, `design/game-brief.md` are absent), so each framing is anchored to the closest locked GDD text instead of a quoted pillar.*

1. **"The guild's merchant." (chosen)** Anchor: GDD §1, the loop's "bang bán/chế tạo/nâng cấp" step, and §6.6, "Tiền thành viên dư → mua tài nguyên độc quyền bang". *The moment:* after a Golden Boss, the master lists the epic blade at 150%, and an hour later the history log says Lan bought it — her wallet is lighter, the fund heavier, and she hits harder on the next hunt. *Asks of the design:* listings the player prices, purchases that visibly land in the fund and on a member, and no way for a listing to lose the guild money compared with selling to the void.
2. **"Commissions on the notice board."** Anchor: GDD §7, Thương Hội: "Đặt đơn vật liệu → thành viên đi săn theo đơn". *The moment:* the Tổng Đàn needs 30 Zone 6 ore; the master posts an order, and parties drift to the Zone 6 grounds; the order bar fills over a night away. *Asks:* orders that steer hunting legibly, and a bounty that is a real cost so orders are a choice, not a permanent toggle.
3. **"A fair price."** Anchor: GDD §6.8, mood and loyalty "chịu ảnh hưởng của thuế, chia đồ". *The moment:* the master marks gear up to fill the fund, and watches members grumble. *Asks:* price feeds mood (Retention 16). This framing is kept as a consequence, not the headline: the mood effect belongs to Retention, so this GDD only exposes prices.

Framing 1 is the headline (it carries §6.5 and §6.6, the system's reason to exist); framing 2 is the Thương Hội half of the same fantasy; framing 3 is delegated to Retention.

## Detailed Design

*Lenses applied before drafting (Section C, routing row "Economy, loot, crafting"):*

- **economy-designer (primary).** The market is a *transfer* system, not a faucet: every gold amount moves wallet → fund (sales) or fund → wallet (bounties), so the money supply changes only by the shop burn that Gold economy R7 already applies to catalogue sales. Three warnings. (1) A storage listing that sells below an item's sell value (Items F5) makes "list it" worse than `sell_item`; floor every listing at that value. (2) Materials must never become sellable through the market — Items R13 closed that double payment (members are paid for materials at hand-in). Trade orders therefore pay a *bounty*, a transfer from the fund, never a sale of the material. (3) A free order is a permanent toggle, not a decision; a bounty floor makes every order cost the fund real gold.
- **systems-designer (supporting).** Integers and ppm only (Sim core R13). Every purchase is one all-or-nothing step: price check, storage `take`, ledger call, equip/inventory, in a fixed order with every check before the first write (Command layer R5 "validate before mutating"). Stalls and orders are capacity keys (Buildings R8), so arrears can never orphan them. Listing price drift is computed from the listing tick on read, so there is no daily handler and offline gaps need no settlement. Order fulfilment must run inside the same hand-in that stores the materials, live and offline, or offline nights would fill no orders.
- **game-designer (supporting).** The player's decisions: which families to stock (which schools are served at home), which storage goods to list and at what markup, and which materials to commission at what bounty. What the player cannot do: sell materials, force a member to buy, set a price below the floor, pay a bounty from member gold, or list a guild-held special (horns, banners, wards, lenses).

No conflict between the lenses needed a choice. The two structural choices (player-placed bounties rather than NPC buyer orders; stalls that hold either a catalogue line or a storage listing) were made on the recommended options and logged.

### Core Rules

**Terms.** A *stall* is one of the Chợ Bang's `market_slots` positions, numbered 1…`market_slots`. A *line* is what a stall sells. A *buyer* is a roster member. *Storage* is Items and loot's guild storage (Items R7), keyed `(content_id, enhance_level)`. *Listable* goods are the goods Items R8 calls awardable — equipment, consumables and member-held specials — with a `price > 0`; materials and guild-held specials are never listable. *Home* means a member state in which Member model R6 rule 6 allows `equip` (not `hunting`, `boss_raid`, `away`, `dead`, `training`).

**R1: The Chợ Bang and its stalls.** The stall count is `effect(bld_market, market_slots)` (Buildings R7). It is a capacity key, so it never decays in arrears (Buildings R8). At Chợ Bang level 0 (not built) the query returns `none`: there are no stalls, every Market command for stalls is refused `not_built`, and no member can buy from the market. Each stall is either *empty* or holds exactly one line (R2 or R3). Stalls are independent; the same family or storage key may not appear in two stalls (refused `duplicate_line`), so the player cannot double the visibility of one good.

**R2: Catalogue lines (the Chợ Bang's own gear).** `set_catalogue(stall, slot_kind, family)` puts a catalogue line in a stall. `slot_kind` is `weapon`, `armor` or `accessory`; `family` is an `items.family` value of that slot (a weapon family, an armour class, or `ring`/`amulet`). The line offers **every live equipment row** with that `slot` and `family` and `rarity = common`, at its `items.csv` `price`. Stock is unlimited (the goods are made by the shop, as Gold economy R7 assumes: its burn part "stands for the ingredients and labour").
- Rare and epic equipment is never on a catalogue line; it reaches the market only as stock (R3). This keeps drops and boss loot the only source of rarity.
- A sale on a catalogue line is a **shop sale**: the ledger's `shop_sale(member_id, price_total, bld_market uid, item_uid)` (Gold economy R7), which sends the fund share (Gold F2, 30% default) to the fund as `shop_revenue` and burns the rest as `shop_cost`. `price_total` is F2 of this GDD (the item price adjusted by the buyer's trade trait).
- The new item is created by the purchase — it is never taken from storage — and goes straight to the buyer through Member model `equip` (R5).

**R3: Stock listings (goods the guild already owns).** `list_stock(stall, content_id, enhance_level, qty, markup_ppm)` puts a stock listing in a stall:
- It is refused unless the key is listable (`not_listable`), storage holds at least one unit of it at the moment of listing (`target_missing`, shared 6), `1 ≤ qty ≤ listing_qty_max` (`out_of_range`) and `markup_min_ppm ≤ markup_ppm ≤ markup_max_ppm` (`out_of_range`).
- A listing does **not** reserve units. Units stay in storage, where the award (Items R8) and every owning system can still take them. A listing's *available* count is `min(qty_remaining, storage.count(key))`, read at sale time. This keeps one source of truth for goods and lets the master still award a listed item for free.
- The asking price is F1: `price × markup_ppm` at listing, discounted linearly per game day after a grace period, never below the item's sell value (Items F5). The discount clock starts at the listing tick; `set_markup(stall, markup_ppm)` re-prices a listing and restarts its clock.
- A sale takes one unit from storage (`take`, all-or-nothing) and moves the buyer's gold to the fund as one `market_trade` transfer (Gold economy R3, type 44, wallet → fund) for the whole price. There is no burn: the goods' cost was already sunk (boss loot: nothing; crafted: `craft_cost`; bought into storage: `fund_purchase`). `qty_remaining` falls by 1; at 0 the listing ends and the stall becomes empty (`listing_sold_out`).
- Equipment goes to the buyer through Member model `equip` (R5); consumables go to the buyer's inventory (Member model; Items R8's inventory path). Enhancement level travels with the unit (Items R7).

**R4: Clearing a stall.** `clear_stall(stall)` empties it. Nothing moves: catalogue goods do not exist until bought, and stock never left storage. Clearing is free and always accepted for a non-empty stall (refused `stall_empty` otherwise).

**R5: Buying.** Members buy on their own; the player never orders a purchase.
1. **Who decides.** Utility AI (12) decides whether and what a member buys, from the market's offer query `offers_for(member_id)` (Interactions). It queues a purchase intent `buy(member_id, stall, content_id)` in its own phase (PROVISIONAL, OQ-3). This system does not score, rank or recommend goods.
2. **Where it runs.** Market registers one P4 handler (`economy`, order 2900, after Items 2600 and the ledger 2700) that drains the intent queue in queue order in the same tick.
3. **Checks, all before any write.** The intent is refused (event `market_purchase_refused`, reason in the payload; nothing changes) unless: the member exists and is *home*; the stall holds a line offering `content_id` (for a stock listing, also *available* ≥ 1); for equipment, Member model R6 rules 2–5 pass for this member (slot, level, school, armour class); for a consumable, the member's inventory accepts it (Member model; Items R8 reason 6); and `ledger.can_debit(wallet, price)` with the price from F2.
4. **Commit, in this order.** (a) Stock only: `storage.take({key: 1})`. (b) The ledger call: `shop_sale` (catalogue) or `transfer(market_trade, wallet, fund, price, item_uid)` (stock). (c) `equip` (equipment; the displaced item goes to storage per Member model R6) or inventory give (consumable). (d) Emit `catalogue_sale` (2901) or `stock_sale` (2902). Because a handler runs to completion (Sim core R5) and every condition was checked in step 3, none of (a)–(c) can fail; if one does, that is a bug and calls `ctx.fail(29001, MARKET_COMMIT_FAILED)`.
5. **Limits.** One unit per intent. A member may make at most `market_buys_per_member_day` purchases per game day (counted on the member's last-purchase window; protects wallets from a mis-tuned AI loop and bounds event volume).

**R6: Trade orders (Thương Hội).** `place_trade_order(material_id, qty, bounty_per_unit)` posts an order. The order count limit is `effect(bld_trade, order_slots)` (1–5; a capacity key, never decays). It is refused unless the Thương Hội is built (`not_built`), an order slot is free (`slots_full`), the material is live (`not_live`, shared 9), no open order already names this material (`duplicate_line`), `1 ≤ qty ≤ order_qty_max` (`out_of_range`) and `bounty_min ≤ bounty_per_unit ≤ bounty_max` from F3 (`out_of_range`).
- An accepted order gets the next `order_id` (a guild counter starting at 1, never reused), `remaining = qty`, `placed_tick = N`, and emits `trade_order_placed`. **Nothing is paid at placement**; the bounty is paid on delivery (R7). An order therefore never holds fund gold hostage, and an unaffordable order simply waits.
- `cancel_trade_order(order_id)` removes an open order at once, frees its slot and emits `trade_order_cancelled`. Nothing is refunded because nothing was prepaid. Materials already delivered stay in storage.
- Orders do not expire. An idle player's order stays until it is filled or cancelled.

**R7: Delivery (filling an order).** Orders are filled inside Items and loot's hand-in (Items R6 step 2, where materials enter storage), live and offline alike:
1. After step 2 stores a party's materials, Items calls `market.deliver(roster, materials)` with the per-material unit counts just stored (PROVISIONAL interface, OQ-2). The materials are already in storage and stay there; delivery only counts them against orders and pays the bounty.
2. For each material in ascending material `uid`, if an open order names it: `credited` = F4 (bounded by the order's remaining units, the units just handed in, and what the fund can pay).
3. If `credited > 0`: the bounty `credited × bounty_per_unit` is paid **from the fund to the roster**, split by F4 (equal integer shares, remainder to ascending `member_id` — the same split rule as Zones R8), each share one ledger transfer of the requested type `order_bounty` (fund → wallet; OQ-1). `remaining` falls by `credited`. Emit `trade_order_progress`.
4. If the fund could not pay for every eligible unit, emit `trade_order_unfunded` once for that order in that hand-in; the unpaid units are ordinary materials in storage and do not count toward the order.
5. At `remaining = 0` the order completes: its slot frees, `trade_order_completed` is emitted (logged).
- The bounty is not taxed (Gold economy R6 taxes only its listed income types) — the fund cannot tax back what it pays out.
- Delivery is the only path that counts toward an order. Materials already in storage before the order was placed, or taken from storage, never count: an order is a request for **new** hunting, which is what steering buys.

**R8: Steering the hunt.** The order book is published to Utility AI (12) as `open_orders() → [(material_id, remaining, bounty_per_unit)]` and per member as `order_demand(material_id) → remaining`. Utility AI owns how much an order raises the score of grounds whose monsters drop that material (GDD §7: "thành viên đi săn theo đơn"); this system defines no score. A party is never forced to a ground, so an order for a material no live ground drops simply never fills (Edge Cases).

**R9: Prices the player sets, and what they cannot do.** The player sets: which lines fill which stalls, each stock listing's quantity and markup, and each order's material, quantity and bounty. The player cannot: list or sell materials (Items R13); list guild-held specials or price-0 items; set a markup outside `[markup_min_ppm, markup_max_ppm]` or a bounty outside F3; make a member buy; take gold from a wallet (Gold economy R1); prepay or escrow a bounty; post two orders for one material; or put the same line in two stalls. Catalogue prices are fixed at `items.csv` `price` (no markup), so catalogue gear stays the cheap, always-available baseline that §18.3 measures (a full set in 0.1–0.6 h of income).

**R10: Live switch.** `market_live` (`config.csv`, false in the MVP build, true from Vertical Slice) is read once at boot. While false, every Market command is refused `not_live` (shared 9), `offers_for` returns nothing and `deliver` does nothing. Golden Boss loot then reaches members only through the designated award (systems index: tier inversion, MVP stand-in). Whether the MVP Chợ Bang runs any stand-in shop is not decided here (OQ-4).

**R11: Registration.** Commands (Command layer 5; type IDs in this system's block 2900–2999, applied in P1 at order 2900): 2901 `set_catalogue`, 2902 `list_stock`, 2903 `set_markup`, 2904 `clear_stall`, 2905 `place_trade_order`, 2906 `cancel_trade_order`. Owner reason codes (100–999): 101 `not_built`, 102 `not_listable`, 103 `duplicate_line`, 104 `out_of_range`, 105 `slots_full`, 106 `stall_empty`, 107 `bad_stall`, 108 `bad_family`. Shared codes used: 6 `target_missing`, 7 `not_allowed_now` (member not home, daily buy cap), 8 `cannot_afford` (wallet short on a purchase), 9 `not_live`. P4 handler order 2900 (R5). Feature fail code **29001** `MARKET_COMMIT_FAILED`. Events 2901–2909 (F5).

**R12: Saved state.** Local save (6) registers this system's serializer: `stalls[]` (per stall: empty, or `{kind: catalogue, slot_kind, family}`, or `{kind: stock, content_id, enhance_level, qty_remaining, markup_ppm, listed_tick}`), `orders[]` (`{order_id, material_id, qty, remaining, bounty_per_unit, placed_tick}` in `order_id` order), `next_order_id`, and per member `buy_window_start_tick` and `buys_in_window` (on the member record, R5 rule 5). Every int64 is a JSON string (Sim core R6). Listing prices are not saved; they are recomputed from F1.

### States and Transitions

**Stall**

| State | Enters from | Leaves to | Trigger |
|---|---|---|---|
| `Empty` | (start), any line state | `Catalogue`, `Stock` | `set_catalogue` / `list_stock` accepted |
| `Catalogue` | `Empty`, `Catalogue`, `Stock` | `Empty`, `Catalogue`, `Stock` | `clear_stall`; a new `set_catalogue` / `list_stock` on the stall replaces the line (same as clear then set) |
| `Stock` | `Empty`, `Catalogue`, `Stock` | `Empty` (sold out, cleared), `Catalogue`, `Stock` | `qty_remaining` reaches 0 (`listing_sold_out`); `clear_stall`; replacement |
| `Stock (unavailable)` | `Stock` | `Stock` | Not a stored state: *available* = 0 because storage has none of the key right now (awarded, consumed). The listing stays and sells again when the key returns to storage |

**Trade order**

| State | Enters from | Leaves to | Trigger |
|---|---|---|---|
| `Open` | — | `Open` (progress), `Completed`, `Cancelled` | `place_trade_order` accepted |
| `Completed` | `Open` | — (removed; slot frees) | `remaining` reaches 0 in a delivery |
| `Cancelled` | `Open` | — (removed; slot frees) | `cancel_trade_order` |

Invalid transitions: a completed or cancelled order never reopens (a new order gets a new `order_id`); an order's `qty`, material and bounty never change after placement (cancel and re-post instead — the new order counts only new deliveries); no stall state moves goods except a sale.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Sim core (1) | core → this | P1 command slot (order 2900), P4 handler slot (order 2900), tick N, `ctx.emit`, `ctx.fail` | — | Sim core |
| Data layer (3) | data → this | `items` (`kind`, `slot`, `family`, `rarity`, `price`, liveness), `materials` (`base_price`, liveness), `config.csv` knobs | — | Data layer |
| Command layer (5) | in | Commands 2901–2906 | Accept / refuse codes (R11) | Command layer owns the envelope; this system owns the appliers |
| Event bus (42) | out | — | Types 2901–2909 (F5) | Event bus delivers; this system owns its types |
| Items and loot (26) | both | Storage `count` / `take`; the awardable test (R8); sell value (F5); hand-in calls `deliver` (R7) | `take` on a stock sale; the bought consumable to inventory | Items owns storage, sell value and hand-in |
| Gold economy (27) | both | `can_debit`, `shop_sale`, `transfer` results; `fund()` | `shop_sale` (catalogue), `market_trade` (stock), `order_bounty` (requested, OQ-1) | Gold economy owns the ledger and every entry type |
| Guild and buildings (30) | in | `effect(bld_market, market_slots)`, `effect(bld_trade, order_slots)` | — | Buildings owns levels and effects. `tax_rate_cap` (also `bld_market`) is read by Gold economy, not here |
| Member model (8) | both | Member level, school, state, inventory acceptance | `equip(member_id, slot, item)` (R5); inventory give | Member model owns fields and equip rules |
| CA/PA and traits (9) | in | `trait_mod_ppm(member, buy_price_mult)` | — | CA/PA owns trait values; this system owns their meaning for market prices (F2) |
| Utility AI (12) | both | Purchase intents `buy(member, stall, content_id)` | `offers_for(member)`, `open_orders()`, `order_demand(material)` | Utility AI owns every decision (PROVISIONAL, OQ-3) |
| Golden Boss (14) | indirect | Boss loot lands in storage (Items R9a) | Sold through stock listings (§6.5) | Golden Boss |
| Crafting (28) | indirect | Crafted goods land in storage | Sold through stock listings | Crafting |
| Retention (16) | out | — | Current markups and catalogue/stock availability, sale events 2901–2902 (price fairness as a mood input, §6.8) | Retention owns mood effects (PROVISIONAL, OQ-6) |
| Quests (25) | out | — | Sale events 2901–2902 (quest `q_d_sell`, objective `sell_items_market`) | Quests owns objectives |
| Offline progress (31) | in | Offline hand-ins via Items R12 | Same `deliver` path; listings need no settlement (F1 is computed on read) | Offline owns the slicing |
| Local save (6) | both | — | Save block (R12) | Local save owns the format |
| Guild screens (39) | out | — | Stalls, prices (F1), availability, orders, refusal reasons | UI reads between ticks only (Sim core R15) |

**Query API** (read-only, callable between ticks and from handlers): `stalls()`, `offers_for(member_id) → [(stall, content_id, enhance_level, price)]` (only goods this member may legally buy now, priced by F2), `listing_ask(stall)` (F1), `open_orders()`, `order_demand(material_id)`. **Mutating API** (handlers only): the P1 appliers (R11), the P4 purchase handler (R5), `deliver(roster, materials)` (R7, called by Items).

## Formulas

All formulas run in integers at play time; ratios are ppm (millionths), converted once at boot from `config.csv` floats with `round(x × 1,000,000)` (the Gold economy convention). Division is floor division on non-negative integers. `ticks_per_day = 86,400 × tick_rate` = 864,000 at the default 10 Hz.

*Lens applied: systems-designer (Section D), with the economy-designer cost checks. Each formula was worked at 0, at its default and at its maximum; the boundary findings are noted under each.*

### F1: `listing_ask`

The listing_ask formula is defined as:

`list_price = max(1, price × markup_ppm // 1,000,000)`; `days_over = max(0, (N − listed_tick) // ticks_per_day − listing_grace_days)`; `discount = list_price × min(1,000,000, listing_decay_ppm_per_day × days_over) // 1,000,000`; `listing_ask = max(floor_value, list_price − discount)`, where `floor_value = max(1, sell_value(price))` (Items and loot F5, equipment ratio)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| price | int | 1 – ~200,000 | data file (`items.csv` `price`, owned by 26) | The listed good's base price; price-0 goods are not listable (R3) |
| markup_ppm | int | `markup_min_ppm` – `markup_max_ppm` (500,000 – 5,000,000) | calculated (player's `list_stock` / `set_markup`) | The player's markup over base price |
| N, listed_tick | int | ≥ 0 | calculated | Current tick; tick of the listing or its last re-price |
| ticks_per_day | int | 864,000 | constant (`86,400 × tick_rate`) | Ticks in one game day |
| listing_grace_days | int | 0 – 7 | data file (`config.csv`, default 1) | Days at full price before discounting |
| listing_decay_ppm_per_day | int | 0 – 200,000 | data file (`config.csv` `listing_decay_pct_per_day`, default 0.05) | Linear discount per day beyond grace |
| sell_value | int | ≥ 0 | calculated (Items F5: `(price × equip_sell_milli + 500) div 1000`, `equip_sell_ratio` 0.4) | What `sell_item` would pay the fund for the same unit |

**Output Range:** `floor_value` to `price × 5`. At decay 0 the ask never moves. The `min(1,000,000, …)` clamp keeps `discount ≤ list_price`, so a listing forgotten for years reaches the floor and stops; it never goes negative, and the product stays below 5×10⁵ × 2×10⁵ × … ≤ 10¹² (no int64 risk). The floor guarantees **listing is never worse for the fund than `sell_item`**: at the floor the member pays what the void would have, as a transfer instead of a mint.
**Boundary findings.** (1) `markup_min_ppm` (0.5) is above `equip_sell_ratio` (0.4), so a fresh listing always starts above its floor; if `equip_sell_ratio` is ever tuned above `markup_min`, the floor simply wins (no breakage). (2) A re-price resets the clock (R3), so the player can hold a price indefinitely by re-pricing — accepted: holding a price is a legitimate choice and costs the player sales, not the economy.
**Example:** a Golden Boss epic sword `eq_wpn_sword_05_e` (price 17,671) listed at 1.5×: `list_price` = 26,506; `floor_value` = (17,671 × 400 + 500) div 1000 = 7,068. Day 0–1: 26,506. After 3 full days (`days_over` 2): discount 26,506 × 100,000 // 10⁶ = 2,650, ask 23,856. From day 16 on (`days_over` ≥ 15): ask = 7,068.

### F2: `member_price`

The member_price formula is defined as:

`t = clamp(trait_mod_ppm(member, buy_price_mult), −trade_trait_clamp_ppm, +trade_trait_clamp_ppm)`; `member_price = max(price_floor, base × (1,000,000 + t) // 1,000,000)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| base | int | 1 – 10⁶ | calculated | Catalogue: the item's `price`. Stock: `listing_ask` (F1) |
| trait_mod_ppm(buy_price_mult) | int | any | calculated (CA/PA and traits 9) | Sum of the member's `buy_price_mult` trait values in ppm; `t_haggler` gives −80,000 |
| trade_trait_clamp_ppm | int | 0 – 500,000 | data file (`config.csv`, default 300,000) | Bound on the trait effect, so stacked traits can never make a price 0 or negative |
| price_floor | int | ≥ 1 | calculated | Catalogue: 1. Stock: F1's `floor_value` |

**Output Range:** catalogue `price × 0.7` – `price × 1.3` at the default clamp; stock `floor_value` – `listing_ask × 1.3`. Never 0. The floor on stock means a haggler cannot buy a listing below what `sell_item` would pay the fund.
**Example:** a haggler buys catalogue `eq_wpn_sword_05_c` (price 2,524): 2,524 × 920,000 // 10⁶ = 2,322. The same haggler buys the epic sword of F1 at its floor (7,068): 7,068 × 0.92 = 6,502 < floor, so the price is 7,068.

### F3: `bounty_bounds`

The bounty_bounds formula is defined as:

`bounty_min = max(1, base_price × bounty_min_ppm // 1,000,000)`; `bounty_max = max(bounty_min, base_price × bounty_max_ppm // 1,000,000)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| base_price | int | 12 – ~2,035 | data file (`materials.csv` `base_price`, owned by 26) | The ordered material's base price |
| bounty_min_ppm | int | 100,000 – 1,000,000 | data file (`config.csv` `order_bounty_min_pct`, default 0.5) | Lowest bounty per unit, as a share of base price |
| bounty_max_ppm | int | 1,000,000 – 10,000,000 | data file (`config.csv` `order_bounty_max_pct`, default 3.0) | Highest bounty per unit |

**Output Range:** `mat_z01_1` (12): 6 – 36 per unit. `mat_z15_2` (2,035): 1,017 – 6,105. A full order costs at most `order_qty_max × bounty_max` = 999 × 6,105 = 6.1 M, far inside `gold_op_max`; each delivery pays only what was delivered.
**Why 0.5 – 3.0.** At the floor the bounty equals the member's own hand-in pay for the unit (`mat_sell_ratio` 0.5, Items F5), so a bounty at least doubles what a hunter earns for that material — enough to be a felt incentive if Utility AI reads wallet gain, and enough to cost the fund real gold (the economy-designer warning: no free orders). The 3.0 cap stops the fund being drained into wallets faster than shops burn it back (a fund-to-wallet pump is inflationary only through the wallet side, which the shop burn and forge absorb).
**Example:** the Tổng Đàn level 3 needs `mat_z06_1` × 30 (Buildings OQ-9). Base price 184: bounty 92 – 552. At the default the player posts 184/unit; filling the order costs the fund 5,520 gold.

### F4: `order_delivery`

The order_delivery formula is defined as:

`credited = min(remaining, units_in, fund // bounty_per_unit)`; `total = credited × bounty_per_unit`; `share_i = total // n + (1 if i < total mod n else 0)` for the roster's members sorted by ascending `member_id`, `i` = 0 … n − 1

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| remaining | int | 1 – `order_qty_max` | calculated | Units the order still needs |
| units_in | int | ≥ 0 | calculated (Items hand-in) | Units of this material just stored by this hand-in |
| fund | int | ≥ 0 | calculated (Gold economy `fund()`, read at this order's turn) | Guild fund after any earlier order in the same hand-in |
| bounty_per_unit | int | F3 | calculated (order) | The order's bounty |
| n | int | 1 – `party_max` (5) | calculated (Zones / Items roster) | Members in the returning roster |

**Output Range:** `credited` 0 – `remaining`; `total` 0 – `fund`, so every share transfer is covered and no transfer is refused. A share of 0 (total < n) is skipped, not sent as a 0-gold transfer (the ledger refuses amounts ≤ 0, Gold R4). Division by zero: `bounty_per_unit ≥ 1` (F3) and `n ≥ 1` (a hand-in always has a roster).
**Example:** a party of 4 hands in 12 `mat_z06_1`; the order has 30 remaining at 184. Fund 50,000: `credited` 12, total 2,208, 552 each; 18 remain. Fund 1,000: `credited` 5 (1,000 // 184), total 920, 230 each; `trade_order_unfunded` is emitted; 25 remain and the other 7 units are plain storage.

### F5: event volume (Event bus F1, F4)

Type block 2900–2999. None of the types is a milestone.

| type_id | Name | Fields | Logged | Subject slot | `ring_per_day` |
|---|---|---|---|---|---|
| 2901 | `catalogue_sale` | `a` member_id, `b` item uid, `c` price | no | — | 0 |
| 2902 | `stock_sale` | `a` member_id, `b` item uid, `c` price, `d` enhance_level | yes | 1 | 50 |
| 2903 | `listing_sold_out` | `a` stall, `b` item uid | no | — | 0 |
| 2904 | `market_purchase_refused` | `a` member_id, `b` stall, `c` reason | no | — | 0 |
| 2905 | `trade_order_placed` | `a` order_id, `b` material uid, `c` qty, `d` bounty | no | — | 0 |
| 2906 | `trade_order_progress` | `a` order_id, `b` credited, `c` total bounty | no | — | 0 |
| 2907 | `trade_order_completed` | `a` order_id, `b` material uid, `c` qty | yes | — | 20 |
| 2908 | `trade_order_cancelled` | `a` order_id, `b` remaining | no | — | 0 |
| 2909 | `trade_order_unfunded` | `a` order_id, `b` units not paid | no | — | 0 |

The volume formula is defined as:

`purchase_events_per_day ≤ roster × market_buys_per_member_day`; `delivery_events_per_hand_in ≤ 3 × order_slots` (progress, unfunded, completed per order)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| roster | int | 1 – `member_cap` (≤ ~60) | calculated (Buildings F2) | Members who can buy |
| market_buys_per_member_day | int | 1 – 24 | data file (`config.csv`, default 6) | R5 rule 5 cap |
| order_slots | int | 1 – 5 | data file (`buildings.csv`, owned by 30) | Open orders |

**Output Range:** at most 60 × 6 = 360 sale events per game day and 15 events per hand-in. Peak per tick: one sale or refusal per queued intent plus 15 per hand-in in that tick — inside the Event bus F1 budget that Items (≤ 10 + epics per returning party) already sets the scale for. Logged ring use: ≤ 50 `stock_sale` + 20 `trade_order_completed` per day.
**Example:** 20 members, 6 buys each: ≤ 120 sale events/day, of which typically a handful are logged stock sales.

## Edge Cases

*Lens applied: systems-designer (Section E) over Core Rules and F1–F5 as written.*

### A. Stalls and listings

- **If a listed key's storage count drops to 0** (awarded, consumed by its owner, taken by a school change): the listing stays with its `qty_remaining`, shows as unavailable, refuses purchases (`market_purchase_refused`, reason `target_missing`), and sells again if the key returns to storage. It is not auto-cleared, so a master who awards a listed blade and gets another from the next boss does not have to re-list.
- **If a listed key's storage count is below `qty_remaining`**: *available* is the storage count; the listing sells at most that many until more arrive.
- **If two buyers' intents target the last available unit in one tick**: intents run in queue order; the first buys, the second is refused `target_missing` with no change.
- **If the player awards (Items R8) the same unit a member intends to buy in the same tick**: P1 (award) runs before P4 (purchase), so the award wins and the purchase is refused.
- **If an item becomes non-live (retired content, Data layer R5)**: a stock listing of it keeps selling (liveness gates only what is newly offered; owned goods stay usable, Items R7). A catalogue line stops offering the retired rows at once; a catalogue line whose family has no live common rows left offers nothing and stays in its stall until cleared.
- **If `set_catalogue` names a family that has no live common row for that slot kind**: refused `bad_family`.
- **If the Chợ Bang's `market_slots` in data is lowered between versions below the number of non-empty stalls** (the only way the count can shrink; the key never decays): at load, stalls above the new count are cleared in descending stall number (nothing moves; goods were never taken), and one `listing_sold_out` per cleared stock listing is emitted. A save never fails for this.
- **If a stall number is 0 or above `market_slots`**: refused `bad_stall`.
- **If the guild's fund is at the gold cap** (`gold_balance_max`): a stock sale's transfer clamps per Gold R5 (the excess is burned as `balance_clamp`); the sale still succeeds. Practically unreachable at 10¹⁵.

### B. Buying

- **If a member is not home** (hunting, in a raid, away, dead, training): no purchase is possible; Utility AI should not queue one, and if it does the intent is refused `not_allowed_now`.
- **If a member's wallet exactly equals the price**: the purchase succeeds and the wallet goes to 0.
- **If the item would not be an upgrade for the member**: the market does not care — legality only (R5 step 3). Whether it is worth buying is Utility AI's decision. A bought item that is worse than the equipped one still displaces it to storage (Member model R6), from where it can be re-listed: nothing is lost.
- **If the displaced item is itself enhanced**: it goes to storage with its level (Items R7) and can be listed; F1 prices enhanced items from base `price` only — the player raises the markup to price in the enhancement (up to 5×). Whether an enhancement-aware base is wanted is OQ-7.
- **If a member hits `market_buys_per_member_day`**: further intents that day are refused `not_allowed_now`; the window resets one game day after its first purchase.
- **If the ledger's `can_debit` passes but a later commit step fails**: unreachable by construction (R5 step 4); if it happens it is `ctx.fail(29001)`, a bug, not a refusal.

### C. Trade orders

- **If an order names a material that no live ground drops** (a zone not yet unlocked, `content_wave` gating): the order is accepted (the master may plan ahead) but cannot fill until such a ground is reachable; the order screen marks it "no source reachable" (UI Requirements). It never auto-cancels.
- **If the fund is 0 when an order's material arrives**: `credited` = 0, `trade_order_unfunded` is emitted, and every unit is ordinary storage. The order waits; it does not pause other orders, and it never creates a debt.
- **If two orders could match one hand-in**: impossible for one material (R6 refuses a second order on the same material); different materials are processed in ascending material `uid`, so an earlier material's bounty can consume fund that a later one needed. The order is deterministic and shown in the order screen as "paid first".
- **If the units handed in exceed `remaining`**: only `remaining` are credited; the rest are plain storage. The order completes in that hand-in.
- **If the player cancels an order in the same tick a party hands in its material**: P1 (cancel) runs before P4 (hand-in), so nothing is credited.
- **If the material is retired while an order is open**: the order stays open and can still fill from grounds that drop it; no new order for it can be placed (`not_live`).
- **If an offline night fills an order**: offline hand-ins call the same `deliver` (Items R12), so bounties are paid and orders complete at the hand-in that fills them; the player sees `trade_order_completed` in the history on return. **Conflict carried from Items R12 / OQ-6**: if Zones F10's offline path still scales only gold and XP and brings home no materials, offline nights fill no orders — this system inherits that gap (OQ-5).
- **If the Thương Hội is never built**: `order_slots` is `none`; `place_trade_order` is refused `not_built`; `open_orders()` is empty.

### D. Degenerate strategies checked

- **Buy-and-relist arbitrage** (`buy_item` into storage, list at a markup, a member buys): `fund_purchase` burns the full price, the sale transfers wallet gold back. The fund converts member gold into fund gold at the player's markup, which is the designed purpose of the market; no gold is minted.
- **List at the floor instead of selling to the void**: equal value to the fund, but as a transfer from a wallet (no mint), so it *lowers* the money supply relative to `sell_item`. Encouraged.
- **Order bounties as a fund-to-wallet pump** (post orders for cheap materials at the 3.0× cap to enrich members): bounded by `bounty_max`, `order_slots` (≤ 5) and the drop rate; the wallets' gold returns through shop sales (70% burned) and stock purchases. Net effect is a mild deflation of the fund, never a mint.
- **Re-posting orders to count old storage**: impossible — only new deliveries count (R7).
- **Markup at 5× to drain wallets**: members decide whether to buy (Utility AI), and Retention reads prices (OQ-6); the market itself only bounds the markup.

## Dependencies

### Upstream (this system depends on)

| System | Nature | Interface | Status |
|---|---|---|---|
| Items and loot (26) | Hard | Storage `count`/`take`, the awardable test (R8), `price`, `kind`/`slot`/`family`/`rarity`, sell value F5; hand-in calls `deliver` (R7) | Designed — conforms. `deliver` hook and inventory-give path are PROVISIONAL (OQ-2) |
| Gold economy (27) | Hard | `can_debit`, `shop_sale` (R7), `transfer(market_trade)`, `fund()`; the requested `order_bounty` type | Designed — conforms for sales; `order_bounty` and a Market-computed `price_total` are requests (OQ-1, OQ-8) |
| Guild and buildings (30) | Hard | `effect(bld_market, market_slots)`, `effect(bld_trade, order_slots)`; both capacity keys (its R8) | Designed — conforms |
| Member model (8) | Hard | Level, school, state; `equip`; inventory acceptance | Designed — conforms (equip called from the P4 handler, as Items hand-in already does) |
| Sim core (1), Data layer (3), Command layer (5), Event bus (42) | Hard | Phases and slots; tables and config; commands 2901–2906; events 2901–2909 | Designed |
| CA/PA and traits (9) | Soft | `trait_mod_ppm(buy_price_mult)` | Designed — conforms (it already lists Market as a consumer) |
| Utility AI (12) | Hard for purchases and steering; the market runs without it but nobody buys | Purchase intents; reads `offers_for`, `open_orders`, `order_demand` | **Not designed — PROVISIONAL (OQ-3)** |

### Downstream (systems that depend on this one)

| System | Nature | What they need |
|---|---|---|
| Golden Boss and guild raid (14) | Soft (tier inversion: MVP uses the award) | Stock listings as the §6.5 "members buy with gold" path for boss loot |
| Guild screens (39) | Hard | Stall, listing, price and order read models; the six commands |
| Quests and achievements (25) | Soft | Sale events for `q_d_sell` (`sell_items_market`) |
| Retention (16) | Soft | Markups and availability as mood inputs (PROVISIONAL, OQ-6) |
| Crafting (28) | Soft | A place to sell crafted output (via storage) |
| Utility AI (12) | Hard | The offer and order queries |
| Local save (6), Offline progress (31), Dev tooling (43) | Hard / Soft | Save block; the offline `deliver` path; S3 scenarios (`sim/economy_full.py`, "Chợ Bang (mua/bán, giá động nhẹ), đơn Thương Hội") |

Bidirectionality: Items (26), Gold (27), Buildings (30), CA/PA (9), Command layer (5) and Local save (6) already name Market (29) as a dependent. Golden Boss (14), Guild screens (39) and Quests (25) are undesigned; their GDDs must list this system.

## Tuning Knobs

*Lens applied: systems-designer (Section G).* All are `config.csv` rows read once at boot (Data layer R10), all new. `*_pct` values are converted to the `*_ppm` variables of F1–F3 at boot.

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `market_live` | false (MVP), true (VS) | bool | — | — | Scope switch (R10), not a balance knob |
| `markup_min_pct` | 0.5 | 0.4 – 1.0 | Cannot clear stale goods cheaply | Below `equip_sell_ratio` the floor takes over (harmless) | `equip_sell_ratio` (26) |
| `markup_max_pct` | 5.0 | 1.5 – 10.0 | Wallet drain if Utility AI is price-blind | Enhanced gear cannot be priced fairly | Utility AI purchase scoring; Retention price fairness |
| `listing_grace_days` | 1 | 0 – 7 | Stale loot sits unsold for idle players | Prices start falling at once | `listing_decay_pct_per_day` |
| `listing_decay_pct_per_day` | 0.05 | 0 – 0.20 | Boss loot dumps at the floor in days | 0 disables "giá động nhẹ" | `listing_grace_days`; F1 floor |
| `listing_qty_max` | 99 | 1 – 999 | — | Player re-lists often | — |
| `trade_trait_clamp_pct` | 0.30 | 0 – 0.50 | Stacked traits near-free gear | Traits feel inert | `t_haggler` (9) |
| `market_buys_per_member_day` | 6 | 1 – 24 | Mis-tuned AI empties wallets | Members cannot gear up after a level burst | F5 event volume; Utility AI |
| `order_bounty_min_pct` | 0.5 | 0.1 – 1.0 | Orders too expensive to post | Orders become free toggles | `mat_sell_ratio` (11/26) |
| `order_bounty_max_pct` | 3.0 | 1.0 – 10.0 | Fund-to-wallet pump | Rare materials cannot be prioritised | Shop burn (Gold F2) |
| `order_qty_max` | 999 | 50 – 9,999 | — | Large building costs need several orders | `buildings.csv` `cost_mats` |

**Not knobs (constants):** command and event type IDs (2901–2909), P1/P4 order 2900, fail code 29001, `ticks_per_day`.
**Pointed to, not owned:** `market_slots`, `order_slots`, `tax_rate_cap` (30, `buildings.csv`); item `price`, material `base_price`, `equip_sell_ratio`, `mat_sell_ratio` (26/11); `shop_fund_share_pct` (27); trait values (9).

## Visual/Audio Requirements

Optional for `Economy`; kept brief. No art bible exists (`design/art/art-bible.md` absent), so this is drafted from the GDD alone.

- **Chợ Bang on the realtime map (38):** stall count is not drawn individually (§7: "4 sạp thành 1 công trình" to save art); the building shows a small goods-on-display prop when at least one stall is non-empty, none when all are empty.
- **A stock sale** (2902): the buyer's sprite plays the existing "receive item" beat used by the award, with a coin glint toward the building; rarity colour on the item icon follows the item system's rarity treatment, always paired with the rarity label (never colour alone).
- **Order completed** (2907): a short notice-board flourish on the Thương Hội and a toast. Audio: one light coin cue for sales (low mix priority, rate-limited to one per 2 s so a buying spree does not chatter), one brighter cue for order completion.

📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:guild-market-and-trade-orders` to produce per-asset descriptions from this section.

## Game Feel

Optional for `Economy`. Targets: a command (stock a stall, post an order) acknowledges at once and resolves next tick (Command layer R11); a sale is visible within one tick of happening (history entry for stock sales, a counter tick for catalogue sales). The order progress bar moves on each delivery, never in a jump at completion only, so a night away reads as steady work.

## UI Requirements

Part of Guild screens (39). Two screens:

1. **Chợ Bang screen.** A grid of `market_slots` stalls. Each stall shows its line: catalogue (family icon, the price range of offered tiers) or stock (item, enhancement level, available/remaining, current ask from F1, the "full price until …" or "discounting −5%/day, floor X" note). Actions: set catalogue line (pick slot kind, then family; families with no live commons are hidden), list stock (pick from listable storage, choose quantity and markup with a slider in 5% steps showing the resulting ask and its floor), re-price, clear. Refusals show the reason words (Command layer R6). A note under stock listings states that listed goods stay in storage and can still be awarded.
2. **Thương Hội screen.** `order_slots` order cards: material icon and name, where it drops (zones/grounds, or "no source reachable"), progress `qty − remaining / qty`, bounty per unit and the total still payable, and a warning badge when the last delivery was unfunded. Posting an order: material picker (live materials), quantity, bounty slider bounded by F3 with the member's own hand-in pay shown beside it for comparison, and the "paid in material order" note when two orders are open.

Both screens read state only between ticks (Sim core R15) and send the six commands. All strings are i18n keys (Localization 4); prices use the locale's digit grouping.

> **📌 UX Flag — Guild market and trade orders**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for each screen (Chợ Bang, Thương Hội) **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD | Other GDD | Their section | Relationship |
|---|---|---|---|
| R2 catalogue sale | Gold economy | R7, F2 (`shop_sale`, `shop_fund_share`) | Uses; requests that `price_total` may be Market-computed (F2), OQ-8 |
| R3 stock sale | Gold economy | R3 type 44 `market_trade` | Uses (wallet → fund) |
| R7 bounty | Gold economy | R3 (closed entry-type table) | Requests new type `order_bounty` (OQ-1) |
| R3, F1 floor | Items and loot | R7 storage, R8 awardable, R13, F5 `sell_value` | Uses; listable = awardable with price > 0; materials never sold |
| R7 delivery | Items and loot | R6 hand-in step 2, R12 offline | Requests a `deliver` call after step 2 (OQ-2) |
| R1, R6 | Guild and buildings | R7 `effect`, R8 capacity keys | Uses `market_slots`, `order_slots`; never decays |
| R5 | Member model | R6 `equip` rules 2–6 | Uses; displaced gear to storage |
| F2 | CA/PA and traits | `trait_mod_ppm` | Consumes `buy_price_mult` (`t_haggler`) |
| R5, R8 | Utility AI (undesigned) | — | Provides queries; PROVISIONAL (OQ-3) |
| R7 offline | Zones and hunt | F10 offline scaling | Inherits the materials-offline gap (Items OQ-6) |
| R10 | Systems index | Tier inversions | MVP boss loot via award only |

## Acceptance Criteria

*Lens applied: qa-lead (Section H) over C, D and E as written.* Story types: AC-1 – AC-22 are **Logic** (automated unit tests in `tests/unit/market/`, deterministic, injected storage/ledger/member fakes); AC-23 – AC-24 are **Integration**; AC-25 is **UI** (screenshot evidence).

- **AC-1 (R1)**: **GIVEN** Chợ Bang level 0, **WHEN** `set_catalogue(1, weapon, sword)` is ordered, **THEN** it is refused `not_built` and no stall exists. **GIVEN** level 1, **THEN** `stalls()` has exactly 9 entries.
- **AC-2 (R1)**: **GIVEN** stall 1 holds catalogue `weapon/sword`, **WHEN** `set_catalogue(2, weapon, sword)` is ordered, **THEN** it is refused `duplicate_line`.
- **AC-3 (R2)**: **GIVEN** a catalogue line `weapon/sword`, **WHEN** `offers_for` is queried for a level-40 `kim_2` member, **THEN** it lists only live **common** sword rows with `level_req ≤ 40`, each at its `items.csv` price (no rare or epic).
- **AC-4 (R2, Gold R7)**: **GIVEN** a non-trait member with 3,000 gold, home, **WHEN** a purchase intent for `eq_wpn_sword_05_c` (2,524) is processed, **THEN** the wallet is 476, the fund rose by 2,524 × 300,000 // 10⁶ = 757, a `shop_cost` burn of 1,767 is recorded, storage is unchanged, and the sword is equipped.
- **AC-5 (R3)**: **GIVEN** storage holds 0 of `eq_wpn_sword_05_e`, **WHEN** `list_stock` names it, **THEN** it is refused `target_missing`. **GIVEN** a material or `item_summon_horn`, **THEN** refused `not_listable`. **GIVEN** markup 0.4 or 5.1, **THEN** refused `out_of_range`.
- **AC-6 (R3)**: **GIVEN** a stock listing of the epic sword (qty 1, markup 1.5) and storage count 1, **WHEN** a member with 30,000 gold buys it on day 0, **THEN** the wallet falls by 26,506, the fund rises by 26,506 as one `market_trade` entry, storage count is 0, the listing ends with `listing_sold_out`, and the stall is `Empty`.
- **AC-7 (R3, no reservation)**: **GIVEN** a stock listing (qty 2) and storage count 1, **WHEN** the player awards that unit, **THEN** the award succeeds, the listing shows available 0 and remains, and a later purchase intent is refused `target_missing`.
- **AC-8 (R4)**: **GIVEN** a stock listing, **WHEN** `clear_stall` is ordered, **THEN** the stall is `Empty` and storage counts are unchanged. **GIVEN** an empty stall, **THEN** refused `stall_empty`.
- **AC-9 (R5 checks)**: **GIVEN** a member in `hunting`, **WHEN** their purchase intent is processed, **THEN** it is refused, `market_purchase_refused` is emitted, and wallet, fund and storage are unchanged. Repeat for: wrong school, level too low, wallet one gold short — each refused with no change.
- **AC-10 (R5 order)**: **GIVEN** two intents for the last available unit in one tick, **WHEN** P4 runs, **THEN** the first in queue order buys and the second is refused `target_missing`.
- **AC-11 (R5 rule 5)**: **GIVEN** `market_buys_per_member_day` 6, **WHEN** a member's 7th intent arrives within one game day, **THEN** it is refused `not_allowed_now`; **WHEN** one game day after the first purchase passes, **THEN** the next intent is accepted.
- **AC-12 (R5 displaced)**: **GIVEN** a member holding an enhanced (+4) sword, **WHEN** they buy a catalogue sword, **THEN** the +4 sword is in storage at key `(id, 4)`.
- **AC-13 (F1)**: **GIVEN** the epic sword (price 17,671) listed at 1.5× at tick 0 with defaults, **WHEN** `listing_ask` is read at ticks 0, 2 × 864,000 + 1 (days_over 1), 3 × 864,000 (days_over 2) and 40 × 864,000, **THEN** it returns 26,506; 25,181; 23,856; 7,068.
- **AC-14 (F1 boundary)**: **GIVEN** `listing_decay_pct_per_day` 0, **WHEN** the ask is read after 1,000 days, **THEN** it equals `list_price`. **GIVEN** decay 0.20 and 10,000 days, **THEN** it equals the floor and is > 0.
- **AC-15 (F1 re-price)**: **GIVEN** a listing on day 10 at its floor, **WHEN** `set_markup(stall, 1,000,000)` is ordered, **THEN** the ask becomes `price` and stays there for `listing_grace_days`.
- **AC-16 (F2)**: **GIVEN** a `t_haggler` member, **WHEN** `offers_for` prices catalogue `eq_wpn_sword_05_c`, **THEN** the price is 2,322; **WHEN** it prices the epic sword at its 7,068 floor, **THEN** the price is 7,068 (floor holds). **GIVEN** a test trait stack of −0.9, **THEN** the effect is clamped to −0.30.
- **AC-17 (R6)**: **GIVEN** Thương Hội level 1 (`order_slots` 1) with one open order, **WHEN** a second order is placed, **THEN** refused `slots_full`. **GIVEN** level 0, **THEN** refused `not_built`. **GIVEN** an open order for `mat_z06_1`, **WHEN** another for `mat_z06_1` is placed at level 2, **THEN** refused `duplicate_line`.
- **AC-18 (F3)**: **GIVEN** `mat_z06_1` (184) and defaults, **WHEN** orders are placed with bounty 91, 92, 552 and 553, **THEN** 91 and 553 are refused `out_of_range` and 92 and 552 are accepted. Placing an order does not change the fund.
- **AC-19 (R7, F4)**: **GIVEN** an order for 30 `mat_z06_1` at 184 and fund 50,000, **WHEN** a party of 4 (IDs 3, 5, 8, 9) hands in 12 units, **THEN** each member receives 552 as `order_bounty`, the fund is 47,792, remaining is 18, storage holds the 12 units, and `trade_order_progress` reports 12 / 2,208.
- **AC-20 (F4 unfunded, remainder)**: **GIVEN** the same order and fund 1,000, **WHEN** 12 units are handed in by a party of 3 (IDs 2, 4, 7), **THEN** 5 are credited, total 920 is split 307 / 307 / 306 (IDs 2, 4 get the extra gold), the fund is 80, `trade_order_unfunded` is emitted, and remaining is 25.
- **AC-21 (R7 completion and new-only)**: **GIVEN** storage already holds 40 `mat_z06_1`, **WHEN** an order for 10 is placed, **THEN** remaining stays 10 until a hand-in; **WHEN** a hand-in brings 15, **THEN** 10 are credited, `trade_order_completed` is emitted and logged, and the slot is free.
- **AC-22 (R10)**: **GIVEN** `market_live` false, **WHEN** any of the six commands is submitted, **THEN** it is refused `not_live`; `offers_for` is empty and a hand-in pays no bounty.
- **AC-23 (Integration: conservation)**: **GIVEN** a seeded 7-day S3 scenario with tax live, 20 members, catalogue lines, two boss-loot listings and two orders, **WHEN** it runs, **THEN** Gold economy's conservation identity (Gold F6) holds after every tick and every market amount appears under types 41/20 (catalogue), 44 (stock) or `order_bounty` only.
- **AC-24 (Integration: offline)**: **GIVEN** an open order and an 8-hour offline gap whose sampled trips bring that material home (once Items OQ-6 is resolved), **WHEN** offline progress runs, **THEN** bounties paid and units credited equal those of the same 8 hours run live with the same seed.
- **AC-25 (UI)**: **GIVEN** the Chợ Bang screen with one catalogue line, one discounting stock listing and one unavailable listing, and the Thương Hội screen with one unfunded order, **WHEN** each is shown, **THEN** a retained screenshot in `production/qa/evidence/` shows the current ask and floor, the "available 0" state, and the unfunded badge with its reason text.

**Gaps found and kept as questions, not criteria:** whether members buy sensibly (Utility AI, OQ-3) and whether markups hurt mood (Retention, OQ-6) are playtest/balance questions for S3, not market logic.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Schema request (not made here).** Bounties need a fund → wallet transfer type. Gold economy R3 is a closed vocabulary owned there; request `order_bounty` (transfer, fund → wallet, caller Market 29, Vertical Slice; suggested ID 46), untaxed under Gold R6. Until added, R7 step 3 cannot be implemented | Gold economy (27) | Before the Market story |
| OQ-2 | PROVISIONAL: Items and loot (26) — hand-in (R6 step 2) and the offline path (R12) call `market.deliver(roster, materials_stored)` after materials enter storage; the bought-consumable path uses the award's inventory give (Items R8 reason 6) | Items and loot (26) | Consistency pass |
| OQ-3 | PROVISIONAL: Utility AI (12) — queues `buy(member_id, stall, content_id)` intents that Market's P4 handler (order 2900) drains in queue order, and reads `offers_for`, `open_orders`, `order_demand`; owns whether to buy and how much an order raises a ground's score | Utility AI (12) | When Utility AI is designed |
| OQ-4 | **Scope question (not decided here).** What does the Chợ Bang do in MVP, when Market is Vertical Slice (Guild and buildings OQ-10)? Options: nothing until VS; a catalogue-only stand-in (R2 without stock); the full market early. Gold R7 already prices "Chợ Bang gear" as an MVP shop sale | Producer | Before MVP sprint planning |
| OQ-5 | PROVISIONAL: Offline progress (31) / Zones (11) — offline trips bring materials home through `hand_in`; today Zones F10 scales only gold and XP (Items OQ-6), so offline nights would fill no orders | Zones (11), Offline (31) | When Offline progress is designed |
| OQ-6 | PROVISIONAL: Retention (16) — reads markups and catalogue availability as a "fair price / gear at home" mood input (§6.8); this system exposes them only | Retention (16) | When Retention is designed |
| OQ-7 | Should F1's base for an enhanced item include its enhancement (e.g. the expected forge cost from `enhance.csv`), so the default 1.0× markup is fair for +10 gear? Today the player prices it in with the markup (≤ 5×) | Equipment enhancement (24) + this GDD | When Enhancement is designed |
| OQ-8 | Gold economy R7 defines `price_total` as `price × quantity`; F2 adjusts it by the buyer's `buy_price_mult` trait. Confirm R7 accepts a Market-computed `price_total` (its interaction table already says "Market owns prices") | Gold economy (27) | Consistency pass |
| OQ-9 | `market_fee` (Gold R3 type 44's sibling, 45, wallet → fund) has no use in this design: the guild's "phí giao dịch" (§6.6) is the stock markup plus the shop fund share. Retire 45 or keep it reserved? `market_trade`'s wallet → wallet path is likewise unused (members hold no tradeable stock) | Gold economy (27) | Consistency pass |
| OQ-10 | Crafting (28) — is catalogue gear (R2, made "by the shop") in tension with crafted commons in storage? If Crafting wants the EHT model (shops sell only what the smith made), catalogue lines would need crafted stock. Scope for Crafting's GDD | Crafting (28) | When Crafting is designed |
| OQ-11 | New `config.csv` keys to add with validator ranges: `market_live`, `markup_min_pct`, `markup_max_pct`, `listing_grace_days`, `listing_decay_pct_per_day`, `listing_qty_max`, `trade_trait_clamp_pct`, `market_buys_per_member_day`, `order_bounty_min_pct`, `order_bounty_max_pct`, `order_qty_max` | Data layer (3) | Before the Market story |
| OQ-12 | §20 S3 (`sim/economy_full.py`) has no market or order code; it must implement R2–R7 before the knobs above are tuned (AC-23). The defaults are reasoned, not simulated | Dev tooling (43) | S3 |
| OQ-13 | PROVISIONAL: Golden Boss (14), Guild screens (39) and Quests (25) — must list this system in their Dependencies (bidirectionality) | Those GDDs | When designed |
