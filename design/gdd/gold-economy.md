# Gold Economy (currencies, ledger, tax, upkeep, sinks)

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run, decisions logged)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against (`design/gdd/game-concept.md`, `game-pillars.md` and `design/game-brief.md` are all absent)
> **Implements Pillar**: None (no game-pillars.md yet). Serves GDD §1 (the guild loop's "sell, craft, upgrade" step), §6.6 and §19

## Summary

Gold economy owns the game's two kinds of gold — each member's own wallet and the guild fund the player controls — plus the premium currency Linh Bảo, and it is the only place any of them changes. Every credit and debit (hunt income, tax, shop sales, upkeep, building and forge costs, salaries) is one integer ledger entry with a named type, so the guild master sees where the money went and the S3 money-conservation test can be enforced in one place. It exists so the tycoon layer has a purse worth managing: gold flows in from hunting, the player decides how much of it reaches the guild, and the sinks of §19 keep it from inflating.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` (income, shop sales, upkeep, building spend and a flat tax at `guild_tax_pct`; the player's tax slider, salary, bank, market entries and the Linh Bảo shop arrive in Vertical Slice) · Key deps: `Sim core and tick loop, Data layer and content pipeline, Event bus and history log, Member model, Items and loot, Guild and buildings`

## Overview

**Data layer.** Gold economy is a ledger inside the headless simulation. It holds three kinds of balance, all non-negative int64: one **wallet** per roster member (Member model's `gold` field, which only this system writes), one **guild fund** (`Guild.funds`, GDD §4.1), and one **Linh Bảo** balance for the guild. Every change to a balance is an entry with a stable entry type, an amount and a reference ID. An entry is a **mint** (gold created: monster drops, loot handover, quest rewards), a **burn** (gold destroyed: upkeep, building costs, the forge) or a **transfer** between two balances (tax, the guild's share of a shop sale, salary). Other systems never write a balance; they call the ledger, which refuses anything it cannot pay. Running totals per entry type give the §19.5 inflation metrics and the conservation identity *minted − burned = sum of balances*.

**Player impact.** The player owns the fund and never touches a member's wallet directly. Members earn into their wallets when they hunt and spend from them on their own (potions, feasts, gear, chosen by Utility AI). The player's levers are the tax rate (a fixed rate in MVP, the player's slider from Vertical Slice), what the fund is spent on (buildings, the forge, school changes, salaries, gold awards), and which buildings sell to members. The two tiers are the tension: a richer fund builds the guild faster, but tax and empty shops make members poorer and unhappier (Retention, §6.8). Without this system the game is an idler with a number that only goes up; with it, the guild master runs a treasury.

This GDD does **not** set prices (Items and loot 26, `items.csv`), building costs (Guild and buildings 30, `buildings.csv`), forge costs (Equipment enhancement 24, `enhance.csv`), rebirth costs (Rebirth 23, `rebirth.csv`) or how much gold a monster drops (Items and loot 26, F1 `base_gold_milli` from `base_gold_coef`/`base_gold_exp`). It owns the rules for moving that gold, the guild-level money rules (tax, upkeep, shop split, bank interest, starting fund) and the reference income `income_ref_per_level`. Implementation choices (a ledger class, a Guild resource) become an ADR.

## Player Fantasy

**Both.** The player acts on the fund directly — sets the tax, chooses what to build, pays the forge — and feels the member wallets indirectly, through members who can or cannot afford their own feasts and potions.

*Lens applied: creative-director (Section B). No pillars exist, so each framing is anchored to the closest locked GDD decision instead of a quoted pillar.*

1. **"I hold the guild's purse."** (GDD §1: the bang chủ "xây công trình, phân phối vật tư".) The player opens the treasury after a night away: the fund rose from shop sales and tax, upkeep took its hourly cut, and there is just enough for the Tổng Đàn upgrade — or for one more +11 attempt at the forge. The choice is real because the fund is finite and every entry is visible. *Asks of the design:* a readable ledger, sinks that compete for the same fund, and no hidden flows.
2. **"My people prosper, or they don't."** (GDD §6.6: two tiers of money; §6.8: tax lowers mood and loyalty.) A veteran with a fat wallet buys a feast before every trip on their own; a new recruit cannot. Raising the tax fills the fund but the Chronicle starts to show grumbling. *Asks of the design:* member wallets that drive visible behaviour, and a tax lever whose cost is felt in Retention, not only in a number.
3. **"The forge is never full."** (GDD §19.3: enhancement is the bottomless late-game sink.) Late in the game the fund is large, every building is maxed, and +15 on the tank's blade still eats a week of income. *Asks of the design:* a sink that scales without bound, so a rich guild always has a reason to want more.

**Chosen: all three, in that order of prominence.** Framing 1 is the system's own fantasy; framing 2 is what the two-tier rule (R1) and tax (R6) must deliver; framing 3 is what the sink rules (R9) promise late game. Reference games: Evil Hunter Tycoon (the town earns from hunters' purchases and spends on buildings — GDD §1's base loop) and Football Manager's club finances (a budget the manager controls, wages the players care about).

## Detailed Design

*Lenses applied before drafting (Section C, routing row "Economy, loot, crafting"):*

- **economy-designer (primary).** Every faucet needs a sink at the same level. The faucets are hunting (gold drops plus loot handover), boss and quest rewards and bank interest. The sinks are consumables, gear, upkeep, buildings, the forge, rebirth, school change and crafting. Warning: if the guild shop's price is a pure transfer to the fund, consumption is not a sink at all, and the fund grows without bound once buildings are maxed (GDD §19.4 puts all buildings at 44.2 M). So split each shop sale: part to the fund, the rest burned. Bank interest is a compounding positive loop and must be capped. The forge must stay unbounded so a late fund always has a use.
- **systems-designer (supporting).** Integers only (GDD §3.2, Sim core R13): every amount is an int64 and every rate is ppm, converted from the existing float config once at boot. No balance may go negative, and every debit is all-or-nothing, except upkeep, which pays what it can (GDD §19.4: an empty fund turns buffs off and deletes nothing). Scheduled work (upkeep, salary, interest) uses anchored deadline ticks (Sim core R5) and must be settleable by Offline progress across a gap. The entry-type table is a closed vocabulary, so the conservation test can classify every entry.
- **game-designer (supporting).** The player's decisions: tax rate (from Vertical Slice), spend order, and whether to keep a reserve against upkeep. What the player cannot do: take gold from a wallet, spend a wallet, set a negative tax, or convert Linh Bảo into gold. In MVP the tax is a flat fixed rate the player cannot change (user decision 2026-11-16), so the MVP treasury is fed by tax plus the shop split; the decision to raise or lower the rate arrives with the slider in Vertical Slice.

No conflict between the lenses needed a choice. The MVP fund is fed by the flat tax and the split shop sale; the mood cost of a higher rate is a Vertical Slice concern (Retention 16).

### Core Rules

**R1: Two tiers of gold, one premium currency.**
- **Wallet** — one per roster member, the member's own gold. Credited by that member's income; spent only by the member's own actions (Utility AI purchases, R7) or by system rules that name the member (a market trade, a departure). The player cannot debit a wallet.
- **Guild fund** — one per guild, the player's treasury. Credited by tax, the guild's share of shop sales, quest rewards and bank interest; debited by upkeep and by every player-ordered cost.
- **Linh Bảo** — one guild-level balance of the premium currency (GDD §6.6; `reward_gem` in `quests.csv`). It is **earned only** (quests and achievements) and is **never sold for real money** (user decision 2026-11-16, closing GDD §6.6 [MỞ]). It is never converted to or from gold. It buys only the items on the Linh Bảo shop list (R16): Chiêu Hiền Lệnh, the enhancement ward, the Scripture token for a school change, and special items flagged in data. It never buys potions, feasts, brews, food, gold or an enhancement attempt itself. Because it cannot be bought with money, selling wards for it does not break GDD §19's rule that nothing is forced onto real money (§19's "Linh Bảo không mua được bùa cường hoá" and §19.3's "chỉ chế tạo, không bán" were written while a real-money sale was still open; they need a master-GDD update, OQ-6).
- All three are int64 integers, ≥ 0 and ≤ their cap (`gold_balance_max`, `linh_bao_balance_max`). There are no fractional gold, no floats and no negative balances anywhere in the economy.

**R2: The ledger is the only writer.** No other system writes a wallet, the fund or Linh Bảo. Each change is one call to the ledger API (Interactions, below) naming an **entry type** from the closed table in R3, a positive integer amount, the account(s) and a reference `uid` (the item, building, quest or member it is about; `content_id_none` if none). The ledger validates and either applies the whole entry or refuses it and changes nothing (R4).

**R3: Entry types.** Entry types are integer constants owned here. Each has one kind (mint, burn, transfer), fixed accounts, and the tier in which it is first used. A caller may only use a type with the accounts listed for it. New types are added here, never invented by callers. IDs are permanent (they appear in saves and events).

| ID | Entry type | Kind | From → To | Called by | Tier |
|---|---|---|---|---|---|
| 1 | `hunt_gold` | mint | → wallet | Zones and hunt (11) | MVP |
| 2 | `loot_handover` | mint | → wallet | Zones and hunt (11) / Items and loot (26) | MVP |
| 3 | `offline_hunt` | mint | → wallet | Offline progress (31) | MVP |
| 4 | `boss_reward` | mint | → wallet or fund | Golden Boss raid (14) | MVP |
| 5 | `quest_reward` | mint | → fund | Quests and achievements (25) | Vertical Slice |
| 6 | `bank_interest` | mint | → fund | this system (R8.3) | Vertical Slice |
| 7 | `member_returned` | mint | → wallet | Retention (16) / Jianghu (17) (100% of the burned `member_departed` amount, Jianghu OQ-4) | Vertical Slice |
| 8 | `starting_fund` | mint | → fund | this system, new guild only (R10) | MVP |
| 10 | `building_refund` | mint | → fund | Guild and buildings (30), a cancelled build (reverses its `building_cost`) | MVP |
| 11 | `storage_sale` | mint | → fund | this system, the player's `sell_item` command (R15) | MVP |
| 12 | `arena_reward` | mint | → fund | Arena (18), daily and bout rewards | Full Vision |
| 13 | `tower_reward` | mint | → fund | Endless Tower (19), floor/run rewards | Full Vision |
| 9 | `dev_grant` | mint | → any | Dev tooling (43), debug and test builds only | MVP |
| 20 | `shop_cost` | burn | wallet → | this system, the burned part of a shop sale (R7) | MVP |
| 21 | `upkeep` | burn | fund → | this system (R8) | MVP |
| 22 | `building_cost` | burn | fund → | Guild and buildings (30) | MVP |
| 23 | `enhance_cost` | burn | fund or wallet → | Equipment enhancement (24) | Vertical Slice |
| 24 | `rebirth_cost` | burn | fund → | Rebirth and Ascension (23) | Alpha |
| 25 | `school_change_cost` | burn | fund → | Schools (20) | MVP |
| 26 | `craft_cost` | burn | fund → | Crafting (28) | Vertical Slice |
| 27 | `recruit_cost` | burn | fund → | Recruitment (15) | Vertical Slice |
| 28 | `member_departed` | burn | wallet → | Retention (16) | Vertical Slice |
| 29 | `balance_clamp` | burn | (excess of a credit) → | this system (R5) | MVP |
| 30 | `fund_purchase` | burn | fund → | this system, the player's `buy_item` command (R15) | MVP |
| 31 | `jianghu_invite` | burn | fund → | Jianghu (17), the invite attempt cost | Full Vision |
| 32 | `jianghu_poach` | burn | fund → | Jianghu (17), the poach fee for a signed free agent | Full Vision |
| 40 | `tax` | transfer | wallet → fund | this system (R6) | MVP |
| 41 | `shop_revenue` | transfer | wallet → fund | this system, the fund's part of a shop sale (R7) | MVP |
| 42 | `salary` | transfer | fund → wallet | this system (R8) | Vertical Slice |
| 43 | `gold_award` | transfer | fund → wallet | Items and loot (26), the "designated award" with gold | MVP |
| 44 | `market_trade` | transfer | wallet → wallet or fund | Market and trade orders (29) | Vertical Slice |
| 45 | `market_fee` | transfer | wallet → fund | Market and trade orders (29) | Vertical Slice |
| 60 | `lb_quest` | mint | → Linh Bảo | Quests and achievements (25) | Vertical Slice |
| 61 | `lb_achievement` | mint | → Linh Bảo | Quests and achievements (25) | Vertical Slice |
| 70 | `lb_spend` | burn | Linh Bảo → | this system, the player's `lb_buy` command (R16) | Vertical Slice |

`dev_grant` is refused in a release build. Every other type is always accepted when its accounts and amount are valid; the tier column says when its caller first exists, not a runtime switch. The runtime switches are the tax and its slider (R6).

**R4: Debits are all-or-nothing; balances never go negative.**
1. A debit or transfer whose source balance is below the amount is refused with reason `insufficient` and changes nothing.
2. A call that needs several debits at once (a school change: gold plus an item; a building: gold plus materials) is checked first with `can_debit` and then committed in the same handler, with nothing between. Because a handler runs to completion (Sim core R5), nothing can spend the gold between the check and the commit. The item part belongs to Items and loot (26); the caller orders the two checks and commits only if both pass.
3. The one exception is upkeep (R8), which pays what the fund holds and records the shortfall instead of refusing.
4. An amount ≤ 0, a non-integer, or above `gold_op_max` is refused with `invalid_amount`. An unknown account, or one that does not match the entry type, is refused with `bad_account`.
5. A refusal returns its reason code to the caller and emits `ledger_refused` (2709, not logged). It is never a tick failure: running out of money is gameplay, not a bug.

**R5: Credits clamp at the cap.** A credit that would take a balance above `gold_balance_max` (or `linh_bao_balance_max`) fills the balance to the cap. The excess is recorded as a `balance_clamp` burn, so the conservation identity (F6) still holds, and `balance_clamped` (2710) is emitted. A credit is never refused for being too large while it is within `gold_op_max`.

**R6: Tax (flat in MVP, slider in Vertical Slice).** When `economy_tax_live` is true (the default from MVP, user decision 2026-11-16), every credit of a taxable type to a wallet — `hunt_gold`, `loot_handover`, `offline_hunt` and `boss_reward` to a wallet — is split before it lands: the tax (F1) is transferred to the fund as a `tax` entry in the same call, and the member keeps the rest. Tax is never applied to salary, gold awards, market proceeds or returned wallets, so the player cannot tax back what the fund paid out.
- **MVP (flat).** When `economy_tax_slider_live` is false (the MVP build), `tax_ppm` is fixed at `round(guild_tax_pct × 10⁶)` (100,000) for the whole session, `set_tax_rate` is refused with `not_live`, and the rate is **not** bounded by `tax_cap_ppm` (the cap bounds only the player's slider; the validator already keeps `guild_tax_pct` ≤ every Chợ Bang `tax_rate_cap`). A saved `tax_ppm` that differs is reset to the flat rate at load.
- **Vertical Slice (slider).** When `economy_tax_slider_live` is true, the rate is `tax_ppm`, set by the player with the `set_tax_rate(ppm)` command (applied in P1). It is refused unless `0 ≤ ppm ≤ tax_cap_ppm` (the current Chợ Bang level's `tax_rate_cap`, read from Guild and buildings 30) and at least `tax_change_cooldown_s` of game time has passed since the last change. The default rate is `guild_tax_pct`.
- When `economy_tax_live` is false (a test or tuning build only), taxable credits land whole and `set_tax_rate` is refused with `not_live`.
- The tax rate's effect on mood and loyalty is owned by Retention (16), which reads `tax_ppm`. This system only exposes it. In MVP the flat tax has **no** mood or loyalty effect; Retention applies one only from Vertical Slice, with the slider.

**R7: Shop sales split between the fund and a burn.** When a member buys from a guild building (Thiện Đường food and feasts, Dược Phòng potions, Tửu Lâu brews, Chợ Bang gear), the ledger takes the whole price from the wallet in one call `shop_sale(member_id, price_total, building_uid, item_uid)`. The fund's part (F2) is a `shop_revenue` transfer; the rest is a `shop_cost` burn, which stands for the ingredients and labour behind the goods. The price is the item's `price` in `items.csv` times the quantity (Items and loot 26 owns both and adds the goods to the member). Who decides to buy, and when, is Utility AI (12) (GDD §19.2: members buy by gold threshold and mood). A purchase the wallet cannot cover is refused (R4) and the member does without.

**R8: Scheduled charges — once per game day.** The ledger registers one P4 handler (`economy`, order 2700). It keeps one anchored deadline tick (Sim core R5), `day_due_tick`, every 86,400 s of game time. At each day slot, in this order:
1. **Upkeep (MVP).** The charge F3 is computed from the current roster's levels. The fund pays `min(charge, fund)` as an `upkeep` burn. If it paid less than the charge, the shortfall is forgiven (it is not a debt), `upkeep_arrears_days` increases by 1 and `upkeep_charged` (2704) reports it. If it paid in full, `upkeep_arrears_days` returns to 0. Guild and buildings (30) reads `upkeep_arrears_days` and owns how building effects fade with it (its R8/F4; GDD §19.4: "buff công trình tắt dần, không xoá dữ liệu"). Upkeep never deletes buildings, members or items.
2. **Salary (Vertical Slice).** Every member with a contracted salary (`contract.salary`, owned by Retention 16) is paid from the fund as a `salary` transfer, in ascending `member_id`. Each salary is paid in full or not at all (R4). An unpaid salary emits `salary_unpaid` (2707) for Retention to react to; it is not carried over.
3. **Bank interest (Vertical Slice).** If the guild has a Tiền Trang (`bld_bank`), interest F5 is minted into the fund.

Upkeep is charged daily, not hourly, because GDD §19.4 states it per day and Guild and buildings (30) decays one effective level per arrears **day**. The fund therefore needs a reserve of one day's upkeep, which the Treasury screen shows.

**R9: Sinks are owned by their systems; the forge is unbounded.** Every gold cost except upkeep and the shop burn is set by the system that sells the thing, and charged through this ledger with that system's entry type: building levels (30), forge attempts (24), rebirth (23), school change (20, `change_gold_cost`), crafting (28), recruitment items (15). This system's rule is only that each of them is a burn (destroyed, not paid to anyone), so a fund that spends is a fund that shrinks the money supply. The forge (24) is the designed bottomless sink (GDD §19.3); no other sink needs to be unbounded.

**R10: Starting fund.** A new guild starts with a `starting_fund` mint of `starting_fund_gold` into the fund and 0 in every wallet. A recruit joins with an empty wallet unless a system mints into it with its own type (a returning member's `member_returned`).

**R11: Leaving and returning members.** When a member leaves the guild (Retention 16), their wallet is burned as `member_departed` before the member is removed from the roster, so the conservation identity holds for the guild. Retention or Jianghu (17) may record the amount on the free-agent record; if the member returns, it is minted back as `member_returned`. This system does not decide whether a returner keeps their gold.

**R12: Totals and metrics.** The ledger keeps an int64 running total per entry type (`total[type]`), and per-hour totals of all mints and all burns for the last `metrics_window_h` hours. These give the §19.5 metrics (F7) without logging every entry. They are saved with the ledger.

**R13: Conservation check.** The identity F6 is checked:
- after every tick in test and debug builds — a mismatch fails the tick (`ctx.fail`, code `ledger_mismatch`), because it means a balance was written outside the ledger;
- at every save in release builds — a mismatch emits `ledger_mismatch` (2711, logged), and the save still proceeds, because refusing to save would lose the player's progress.

**R14: Offline settlement.** Across an offline gap, Offline progress (31) owns every due tick the gap crosses (Sim core R5). It credits each member's aggregate income with `offline_hunt` (taxed by R6 exactly as a live credit is), and for each slice calls `settle_schedule(to_tick)`, which runs every upkeep, salary and interest slot up to `to_tick` in R8's order, against the fund and roster as they stand after that slice's credits. It then re-anchors the due ticks past the gap's end. The ledger never fires a backlog of slots on the first live tick after a skip.

**R15: Player commands owned here** (Command layer 5 vocabulary). Applied in P1:
- `set_tax_rate(ppm)` — R6.
- `sell_item(item, qty)` — sells equipment or consumables from guild storage: Items and loot (26) removes the goods, and the fund is credited `storage_sale` at the item's sell value (Items F5, `equip_sell_ratio`). Refused if storage lacks the goods, and refused for **materials**, which were already paid for at hand-in (Items R13; answers OQ-15).
- `buy_item(item, qty)` — buys a shop item into guild storage (for a designated award): the full price is burned from the fund as `fund_purchase` (the guild buying from its own shop earns itself no margin). Refused with the Command layer's shared `cannot_afford` if the fund is short.
- `lb_buy(item, qty)` (Vertical Slice) — R16.
A ledger refusal surfaced through a command maps `insufficient` to the Command layer's `cannot_afford`.

**R16: The Linh Bảo shop (Vertical Slice).** Linh Bảo's only sink (user decision 2026-11-16). The player orders `lb_buy(item, qty)` (host, P1, `qty` 1–99). The offer list is every live `items.csv` row with `lb_price > 0` (a proposed column, OQ-7); today's offers and their prices are tuning knobs sized by F9:

| Offer | Item | Price knob | Default (Linh Bảo) | What it is for | Using system |
|---|---|---|---|---|---|
| Chiêu Hiền Lệnh | `item_recruit_token` | `lb_price_recruit_token` | 150 | An invitation offer (Recruitment R13) | Recruitment (15) |
| Bùa Hộ Cường | `item_enhance_ward` | `lb_price_enhance_ward` | 60 | Keeps the level on a failed +6…+20 attempt (Enhancement R3/R4) | Equipment enhancement (24) |
| Scripture token | `item_school_token` | `lb_price_school_token` | 200 | The item cost of a paid school change (Schools F2); the gold cost is still paid | Schools (20) |
| Special items | per row | `items.csv` `lb_price` | 50 – 1,000 per row | Designer-chosen specials (decor, banners, trial items); never a consumable on R1's never-buy list | Items and loot (26) |

The order is refused with `not_live` (9) if the item is retired or `lb_price = 0`, with `cannot_afford` (8) if `linh_bao < lb_price × qty`, and with Items' storage refusal if storage cannot take the goods; nothing is spent on a refusal. On success, in one P1 step, the ledger burns `lb_price × qty` as `lb_spend` (ref = the item's content ID) and Items and loot `give`s the items into guild storage. The bought item is identical to a crafted or dropped one, and its sell value (Items F5) is unchanged; selling it back mints gold, so the validator keeps every `lb_price` offer's sell value at 0 or the item unsellable (OQ-7), or Linh Bảo would convert into gold through storage. The shop is closed while `economy_lb_shop_live` is false (MVP), and `lb_buy` is then refused `not_live`.

### States and Transitions

The ledger itself is always in one state (open) while the sim runs. The guild fund has a money state that other systems read:

| State | Condition | Effect |
|---|---|---|
| `Solvent` | `upkeep_arrears_days = 0` | Normal |
| `In arrears` | `upkeep_arrears_days ≥ 1` | Guild and buildings (30) fades building effects by it (its F4); UI shows the warning |

| From | To | Trigger |
|---|---|---|
| `Solvent` | `In arrears` | A day's upkeep pays less than its charge. Emits `fund_arrears_started` (2705) |
| `In arrears` | `In arrears` | Another short day: `upkeep_arrears_days` + 1 |
| `In arrears` | `Solvent` | A day's upkeep is paid in full. `upkeep_arrears_days` = 0. Emits `fund_arrears_cleared` (2706) |

There is no "bankrupt" state: the fund cannot go below 0, nothing is repossessed, and the guild recovers as soon as income covers one day's upkeep. A charge of 0 (an empty roster) is paid in full.

Tax has two switches (`economy_tax_live`, `economy_tax_slider_live`) read once at boot; they do not change during a session.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Sim core (1) | core → this | P4 handler slot (order 2700), `ctx.tick()`, `ctx.fail` | — | Sim core |
| Data layer (3) | data → this | `config.csv` keys (Tuning Knobs); `items.csv` `price` via Items | — | Data layer |
| Event bus (42) | this → bus | — | Types 2701–2711 (F8) | Event bus |
| Member model (8) | both | Roster, levels, `contract.salary` | Writes the member's `gold` field (only writer) | Member model holds the field; this system owns writes |
| Zones and hunt (11) | 11 → this | Integer gold and handover amounts per member per trip | `credit` result | This system (API); Zones owns the amounts and how a party's pool is divided |
| Items and loot (26) | both | Item prices; storage for handed-over loot; designated awards | `shop_sale`, `gold_award` results | Items owns prices and goods |
| Utility AI (12) | 12 → this | Purchase decisions | `can_debit` answers, wallet balances | Utility AI owns the decision |
| Guild and buildings (30) | both | Building costs; `tax_rate_cap`; `daily_interest_pct`; Tiền Trang level | `building_cost` debits, `building_refund` credits; `upkeep_arrears_days` | Buildings owns costs and the fade (its R8, F4) |
| Golden Boss (14) | 14 → this | Boss gold rewards | — | Golden Boss owns the amounts |
| Schools (20), Enhancement (24), Rebirth (23), Crafting (28), Recruitment (15) | → this | Their gold costs | Debit results | Each owns its cost |
| Retention (16), Jianghu (17) | both | Departure and return amounts; salary contracts | `tax_ppm`, `salary_unpaid` events | Retention owns mood/loyalty effects |
| Market (29) | 29 → this | Trades and fees | Results | Market owns prices and fees |
| Quests (25) | 25 → this | Gold and Linh Bảo rewards | — | Quests owns the reward amounts |
| Offline progress (31) | 31 → this | Aggregate incomes; `settle_schedule(to_tick)` calls | — | Offline owns the slicing |
| Local save (6) | both | — | The ledger's save block (below) | Local save owns the format |
| Guild screens (39), Realtime view (38) | this → UI | — | Balances, totals, metrics, events | UI reads between ticks only (Sim core R15) |
| Dev tooling (43) | both | `dev_grant`; balance-sim scenarios | F6/F7 metrics, golden vectors | Dev tooling owns the harness |

**Ledger API** (called only from inside a handler; all amounts int64):
- `credit(type, account, amount, ref_uid) → code` — mints. Applies R5 and, for taxable types, R6.
- `debit(type, account, amount, ref_uid) → code` — burns. R4.
- `transfer(type, from, to, amount, ref_uid) → code` — R4.
- `shop_sale(member_id, price_total, building_uid, item_uid) → code` — R7.
- `can_debit(account, amount) → bool` — no side effects.
- `settle_schedule(to_tick)` — R14, for Offline progress only.
- Read-only between ticks: `fund()`, `wallet(member_id)`, `linh_bao()`, `tax_ppm()`, `upkeep_arrears_days()`, `total(type)`, `metrics()`.

Codes: `ok`, `insufficient`, `invalid_amount`, `bad_account`, `not_live`, `cooldown`, `out_of_range`.

**Save block** (Local save 6 registers this system's serializer): `fund`, `linh_bao`, `tax_ppm`, `last_tax_change_tick`, `day_due_tick`, `upkeep_arrears_days`, `total[type]` for every type, and the metrics window. Wallets are saved on the member records. Every int64 is a JSON string (Sim core R6).

## Formulas

All formulas run in integers at play time. The float values that already exist in data (`guild_tax_pct` in `config.csv`; `daily_interest_pct` and `tax_rate_cap` in `buildings.csv`) are converted once at boot to ppm with `round(x × 1,000,000)`, the same boot-time conversion pattern as XP curve R2. Division is floor division on non-negative integers.

*Lens applied: systems-designer (Section D), with the economy-designer cost checks. Every formula below was worked at 0, at its default and at its maximum.*

### F1: `tax_amount`

The tax_amount formula is defined as:

`tax_amount = gross × tax_ppm // 1,000,000` (and `net = gross − tax_amount`)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| gross | int | 1 – `gold_op_max` | calculated | The taxable credit before tax (R6) |
| tax_ppm | int | 0 – `tax_cap_ppm` | calculated | The player's current rate; default `round(guild_tax_pct × 10⁶)` = 100,000 |
| tax_cap_ppm | int | 110,000 – 200,000 | data file (`buildings.csv` `tax_rate_cap`, owned by 30) | The highest rate the current Chợ Bang level allows |
| guild_tax_pct | float | 0 – 0.2 | data file (`config.csv`, 0.1) | Default rate |
| 1,000,000 | int | — | constant | ppm denominator |

**Output Range:** 0 (rate 0, or a gross below 1,000,000 / tax_ppm, e.g. a 9-gold credit at 10%) to `gross × 0.2` at the highest Chợ Bang level. Rounding always favours the member: the remainder stays in the wallet. The product `gross × tax_ppm` is at most 10¹⁵ × 2×10⁵ = 2×10²⁰, which overflows int64, so `gold_op_max` is set to 10¹² (F6 note) and the product is at most 2×10¹⁷.
**Example:** a member's trip pays 7,000 gold at 10%: tax 700 goes to the fund, 6,300 to the wallet. A 9-gold credit pays 0 tax.

**Boundary note.** With many tiny credits, floor rounding lets a member avoid tax entirely (9 gold at a time). Zones and hunt credits once per trip, not per kill (`run_trip` pays at return), so a credit is typically thousands of gold and the rounding loss is under 0.02%. A caller that credits per kill must say so; the leak is then bounded by 1 gold per credit and is accepted.

### F2: `shop_fund_share`

The shop_fund_share formula is defined as:

`fund_part = price_total × shop_fund_share_ppm // 1,000,000`, `burn_part = price_total − fund_part`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| price_total | int | 1 – `gold_op_max` | calculated | Item `price` × quantity (Items 26) |
| shop_fund_share_ppm | int | 0 – 1,000,000 | data file (`config.csv` `shop_fund_share_pct`, new key, default 0.3) | The guild's margin on a shop sale |

**Output Range:** `fund_part` 0 – `price_total`; `burn_part` the rest. At 0 every sale is a pure sink and the fund's only steady income is tax. At 1.0 no consumption is a sink, and the fund inflates (the warning in Section C).
**Example:** a level-40 member buys 5 `pot_hp_05` at 560 each: `price_total` 2,800, the fund gets 840, 1,960 is burned.

**Why 0.3.** GDD §19.2 puts full consumption at about 23% of member income. At a 30% share the fund receives about 7% of member income from shops, and 70% of consumption (about 16% of income) is still burned. With the flat 10% tax live from MVP (user decision 2026-11-16) the fund gets about 17% of member income, the share GDD §19.4 sized the 44.2 M building bill against (10% tax) plus shops, so MVP buildings may complete faster than §19.4 assumed. Both are PROVISIONAL until S3's simulator run (OQ-1).

### F3: `upkeep_charge`

The upkeep_charge formula is defined as:

`upkeep_charge = guild_upkeep_per_level_day × Σ level_i` over the roster, charged once per game day

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| guild_upkeep_per_level_day | int | 0 – 2,400 | data file (`config.csv`, 700) | Gold per member level per day (GDD §19.4) |
| level_i | int | 1 – 200 | calculated (Member model) | Each roster member's level, including injured, away and raiding members |

**Output Range:** 0 for an empty roster. 80 members (the largest roster Guild and buildings F2 allows) at level 200: 700 × 16,000 = 11,200,000 a day. Against reference income (F4) upkeep is always `700 / (24 × 1,000)` ≈ 2.9% of the roster's AFK income, matching GDD §19.4's "≈3%". At 2,400 it is 10% of income, the top of the safe range.
**Example:** 20 members with levels summing to 1,400 (average 70): 980,000 gold a day, against roughly 1,400,000 gold an hour of member income.

### F4: `income_ref` (reference, not a rule)

The income_ref formula is defined as:

`income_ref(L) = income_ref_per_level × L` gold per member per hour

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| income_ref_per_level | int | 1 – 100,000 | data file (`config.csv`, 1,000) | Measured AFK income per level per hour (GDD §19.1) |
| L | int | 1 – 200 | calculated | Member level |

**Output Range:** 1,000 gold/h at level 1 to 200,000 at level 200.
**Example:** a level-70 member's reference income is 70,000 gold/h.

**This formula generates no gold.** Real income comes from hunting (Zones and hunt 11). `income_ref` is the calibration target the simulator checks hunting against, and the yardstick other systems price in "hours of income" (Schools F2 `change_gold_cost`, GDD §19.3's forge table). If simulated income drifts more than 15% from it at levels 30/60/100, either the drops or this value is re-tuned (OQ-2).

### F5: `bank_interest`

The bank_interest formula is defined as:

`interest = min(fund × interest_ppm // 1,000,000, upkeep_charge × bank_interest_cap_pct // 100)` per day slot, 0 without a Tiền Trang

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| fund | int | 0 – `gold_balance_max` | calculated | The fund after the day's upkeep and salaries |
| interest_ppm | int | 2,000 – 16,000 | data file (`buildings.csv` `daily_interest_pct` 0.2–1.6, owned by 30) | Daily rate by Tiền Trang level |
| upkeep_charge | int | F3 | calculated | Today's upkeep bill |
| bank_interest_cap_pct | int | 0 – 200 | data file (`config.csv`, new key, 100) | Interest is capped at this share of the daily upkeep |

**Output Range:** 0 with no bank or an empty fund. The cap makes the loop bounded: at the default, the bank can at most pay the guild's upkeep, never grow the fund on its own. Uncapped, 1.6%/day compounds to ×1.78 in 36 days, an unbounded positive loop that violates GDD §19.5 ("quỹ bang không tăng vô hạn").
**Example:** fund 10,000,000, Tiền Trang level 8 (16,000 ppm), `upkeep_charge` 980,000: uncapped 160,000, cap 980,000 → 160,000 is minted. At a fund of 100,000,000 the uncapped value is 1,600,000 and the cap pays 980,000.

### F6: `conservation`

The conservation formula is defined as:

`Σ total[mint types] − Σ total[burn types] = fund + Σ wallet_i` (gold), and separately `total[lb_quest] + total[lb_achievement] − total[lb_spend] = linh_bao`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| total[type] | int | 0 – 2⁶³ − 1 | calculated (saved) | Running total of each entry type since the guild was created |
| fund, wallet_i | int | 0 – `gold_balance_max` | calculated | Current balances, roster members only |
| gold_balance_max | int | 10¹⁵ | constant | Balance cap (R5) |
| gold_op_max | int | 10¹² | constant | Largest single amount, so F1/F2/F5 products stay under 2⁶³ (10¹² × 10⁶ = 10¹⁸ < 9.2×10¹⁸) |

**Output Range:** the two sides are always equal; the difference is 0. Transfers appear on neither side. `balance_clamp` and `member_departed` are burns and `member_returned` is a mint, so departures, returns and caps keep it exact. A lifetime of income (60 members × 200,000 gold/h for 10 years ≈ 10¹²) is six orders of magnitude below the int64 limit.
**Example:** a new guild: `starting_fund` 2,000 minted. A trip mints 7,000 `hunt_gold`, 700 of it taxed to the fund. The day's upkeep burns 100. Left side 9,000 − 100 = 8,900; right side fund 2,600 + wallet 6,300 = 8,900.

### F7: `out_in_ratio` and `cash_surplus_hours` (simulator metrics)

The out_in_ratio formula is defined as:

`out_in_ratio = Σ burns over the window / Σ mints over the window`; `cash_surplus_hours(member) = wallet / income_ref(L)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| window | int | `metrics_window_h` hours (24) | data file (`config.csv`, new key) | Rolling window of per-hour totals (R12) |
| wallet, L | int | — | calculated | A member's balance and level |

**Output Range:** `out_in_ratio` ≥ 0; 0 when nothing is burned, above 1 while the guild spends savings. Undefined when nothing was minted in the window (an empty roster); reported as "no income" rather than divided by 0. These are float metrics computed by tools and the UI, never fed back into a rule.
**Targets (GDD §19.5, the S3 acceptance bar):** `out_in_ratio` 0.60–0.90 at steady state at levels 30, 60 and 100; the fund does not grow without bound; a level-100 member who owns their needed gear holds no more than 50 `cash_surplus_hours`.
**Example:** in one hour a guild mints 1,400,000 and burns 1,050,000: ratio 0.75, inside the target.

### F8: event volume (Event bus F1, F4)

The event volume formula is defined as:

`Σ ring_per_day(this system) = 1 (upkeep_charged) + 1 (arrears start or clear) + 24 (tax_rate_changed) + 10 (balance_clamped) + 2 (ledger_mismatch) = 38`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| type block | int | 2700 – 2799 | constant | This system's Event bus type IDs (block = system number × 100) |
| day slot | int | 1 per 86,400 s | constant | Bounds upkeep and arrears events to 1 a day each |
| tax_change_cooldown_s | int | 3,600 | data file | Bounds `tax_rate_changed` to 24 a day |

**Output Range:** the types are 2701 `member_paid` (a = member, b = gross, c = tax, d = entry type; not logged), 2702 `shop_sale` (member, item uid, price, fund part; not logged), 2703 `fund_spent` (type, amount, ref uid, fund after; not logged — the spending system logs its own milestone), 2704 `upkeep_charged` (charge, paid, upkeep_arrears_days, fund after; ring), 2705 `fund_arrears_started` (ring), 2706 `fund_arrears_cleared` (ring), 2707 `salary_unpaid` (member, amount; not logged, Retention logs consequences), 2708 `tax_rate_changed` (old ppm, new ppm; ring), 2709 `ledger_refused` (reason, type, amount, account; not logged), 2710 `balance_clamped` (account, excess; ring), 2711 `ledger_mismatch` (left − right, high bits, low bits; ring). 38 is 0.38% of the default ring budget of 10,000 (Event bus F4).
**Peak events per tick.** `member_paid` and `shop_sale` scale with trips: a 40-member guild returns roughly one trip per member every 10–15 minutes and buys a few items per trip, so well under 1 event per tick on average and at most about 2 × roster on a tick when every party returns at once. Not logged, so they cost the ring nothing.
**Example:** a day with no arrears and no tax changes logs 1 `upkeep_charged` record. In MVP `tax_rate_changed` never fires (no slider), so the bound is 14.

### F9: `lb_offer_weeks` (Linh Bảo sink sizing)

The lb_offer_weeks formula is defined as:

`lb_offer_weeks(item) = lb_price(item) / LB_week_ref`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| lb_price | int | 1 – 1,000 | data file (R16 knobs, `items.csv` `lb_price`) | Linh Bảo per unit |
| LB_week_ref | int | 382 | Quests and achievements (25) F6 | A full week of quest claims without the bounty board; 292 for a Free player who never watches ads |

**Output Range:** target 0.1 – 1.0 week per staple offer. Below 0.1 a week of quests buys ten or more of it and the offer stops being a choice (wards would make +11…+20 routine); above 1.0 the player waits more than a week for one purchase and the currency feels dead. With the defaults: ward 60 → 0.16 (≈6 a week, ≈4.9 for a no-ad Free player); Chiêu Hiền Lệnh 150 → 0.39 (≈2.5 a week); Scripture token 200 → 0.52 (≈1.9 a week). The offers compete for one balance, so the real choice is "one invitation, or two wards and change".
**Example:** a Free player who never watches ads earns 292 a week: one Chiêu Hiền Lệnh (150) and two wards (120) leave 22 for next week.
*Economy check:* a ward bought for 60 Linh Bảo stands in for one crafted at ≈20,000 gold plus materials (Enhancement F3 `W`), so the forge stays a gold sink: at ≈6 wards a week Linh Bảo covers a small share of the wards +15 needs, and the rest are crafted. PROVISIONAL until S5 measures ward use (OQ-1).

**Feedback loops.**
- *Income → gear → income* (positive, intended): richer members buy better gear and hunt faster. Damped by gear's level gates and by consumption scaling with level (§19.2 prices are `k × level_req`).
- *Fund → buildings → shop revenue* (positive, intended, bounded): building levels are finite (§19.4 total 44.2 M).
- *Fund → bank interest* (positive, capped by F5).
- *Tax → fund, tax → mood* (balancing): a higher rate fills the fund but Retention (16) lowers mood and loyalty.
- *Arrears → weaker buildings → less income* (negative, a slump risk): a guild in arrears hunts worse and earns less. Damped because upkeep is forgiven, not accrued, and is only ~3% of income, so the slump ends as soon as members hunt.

## Edge Cases

*Lens applied: systems-designer (Section E).*

**Amounts and balances**
- **If an amount is 0, negative or a float**: refused with `invalid_amount`; nothing changes. A 0-gold drop is the caller's to skip, not to send.
- **If an amount is above `gold_op_max` (10¹²)**: refused with `invalid_amount`. No legitimate cost reaches it (the largest data cost is Phi Thăng's 50,000,000).
- **If a credit would exceed `gold_balance_max`**: the balance is set to the cap, the excess is burned as `balance_clamp`, and `balance_clamped` is emitted (R5).
- **If a wallet or the fund holds exactly the price**: the debit succeeds and leaves 0.
- **If two costs in one tick both fit the fund separately but not together**: the first call in handler order succeeds, the second is refused. Order is the deterministic handler order (Sim core R4), then call order inside a handler.

**Tax**
- **If `set_tax_rate` is above `tax_cap_ppm`**: refused with `out_of_range`; the rate is unchanged.
- **If the data's `tax_rate_cap` for the current Chợ Bang level falls below the saved `tax_ppm`** (a data change between versions): at load the rate is clamped to the cap and `tax_rate_changed` is emitted once.
- **If the guild has no Chợ Bang at all**: with the slider (Vertical Slice) `tax_cap_ppm` is 0, so only a 0% rate is allowed. PROVISIONAL on Guild and buildings (30) — OQ-10. In MVP the flat rate applies with or without a Chợ Bang (R6).
- **If an MVP save is loaded into a Vertical Slice build**: the saved flat `tax_ppm` becomes the slider's starting rate (clamped to the cap as above).
- **If a taxable credit is so small that the tax rounds to 0**: the member keeps it all (F1 boundary note).
- **If a player sets tax to the cap and back every hour**: allowed, bounded by `tax_change_cooldown_s`. The mood effect is Retention's to model.

**Upkeep, salary, interest**
- **If the fund is 0 when upkeep is due**: 0 is paid, `upkeep_arrears_days` increases, nothing else happens. No building, member or item is removed.
- **If the roster is empty**: the charge is 0, paid in full, `upkeep_arrears_days` returns to 0.
- **If the roster changes during the day**: the charge uses the roster as it stands on the day-slot tick. A member recruited an hour before pays a full day; one who left an hour before pays nothing. Accepted: the error is at most one member-day (~3% of one member's daily income).
- **If the fund cannot pay every salary**: salaries are paid in ascending `member_id`, each in full or not at all; the unpaid members get `salary_unpaid`. Low IDs (older members) are therefore paid first. Accepted for determinism; Retention may weigh it (OQ-4).
- **If the guild is in arrears and interest is due**: interest is still minted. It is capped by the day's upkeep charge, so it can at most help pay upkeep.

**Offline**
- **If an offline gap crosses several day slots**: Offline progress calls `settle_schedule` per slice, so slots are charged in order against the fund as income arrives, not all against the fund at the start of the gap (R14). A gap's upkeep can never exceed what the fund held plus what the gap earned.
- **If the first live tick after a skip sees a day slot already overdue**: it cannot, because Offline re-anchors the due ticks past the gap (R14, Sim core R5). If it does, it is a bug caught by AC-21.

**Members**
- **If a member leaves holding gold**: the wallet is burned as `member_departed` before removal (R11). It never transfers to the fund — the player cannot profit from driving members out.
- **If a member returns**: their stored amount, if any, is minted as `member_returned`. The amount is Retention's and Jianghu's to decide.
- **If a member dies or is injured mid-trip**: no ledger effect; whatever Zones and hunt pays at return is credited.

**Degenerate strategies checked**
- *Buy from your own shop to launder wallet gold into the fund*: members buy, not the player, and only 30% reaches the fund; 70% is burned. Not profitable.
- *Hire, tax, fire*: a departing member's wallet is burned, not seized; tax applies only to income. No gain.
- *Award gold, then tax it back*: `gold_award` and `salary` are not taxable (R6).
- *Bank compounding*: capped by F5.
- *Linh Bảo to gold*: no such conversion exists (R1). Buying an item with Linh Bảo and selling it from storage is closed by R16's sell-value rule.
- *Linh Bảo shop*: `lb_buy` refusals spend nothing; a purchase is one atomic step (burn + give), so no partial state.

## Dependencies

### Upstream (this system depends on)

| System | Hardness | Interface | What it provides |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | `register(P4, 2700, …)`, `ctx`, anchored deadline ticks, integer-state rule (R13) | The handler slot and timing |
| Data layer and content pipeline (3) | Hard | `config.csv` keys; validator rules (`shop_fund_share_pct` in 0–1; `bank_interest_cap_pct` 0–200) | Tuning values |
| Event bus and history log (42) | Hard | `register_type` for 2701–2711, `ctx.emit` | Delivery and the Chronicle |
| Member model (8) | Hard | Roster, `level`, the `gold` field, `contract.salary` | Who has a wallet and what upkeep costs. PROVISIONAL — no GDD yet |
| Items and loot (26) | Hard | Item prices; handover of loot to storage; designated awards | Shop sales and the loot handover mint. PROVISIONAL — no GDD yet |
| Guild and buildings (30) | Soft for MVP ledger and flat tax, hard for the tax slider and bank | `tax_rate_cap`, `daily_interest_pct`, Chợ Bang and Tiền Trang levels; consumes `upkeep_arrears_days` | Tax cap, interest rate, fade behaviour. PROVISIONAL — no GDD yet |

### Downstream (systems that depend on this one)

| System | Hardness | What it uses |
|---|---|---|
| Zones and hunt (11), Golden Boss (14), Offline progress (31) | Hard | `credit` with the mint types; `settle_schedule` (31) |
| Utility AI (12) | Hard | Wallet balances, `can_debit`, `shop_sale` |
| Schools (20) | Hard | `school_change_cost` debit; `income_ref_per_level` |
| Enhancement (24), Rebirth (23), Crafting (28), Recruitment (15), Guild and buildings (30) | Hard | Debits with their burn types |
| Retention (16), Jianghu (17) | Hard | `tax_ppm`, `salary_unpaid`, `member_departed`/`member_returned` |
| Market (29), Quests (25) | Hard | Transfers, fees, rewards |
| Guild screens (39), Realtime view (38) | Soft | Balances, totals, metrics and events |
| Local save (6) | Hard | The save block |
| Dev tooling (43) | Hard | F6 and F7 for S3 and the balance budget (S9) |

Bidirectional check: Schools (20) already lists Gold economy as a soft, provisional dependency (debit the fund, `income_ref_per_level`) — consistent. Sim core lists Gold economy (27) among its P4 registrants — consistent. Systems not yet designed must list this system when they are written.

## Tuning Knobs

*Lens applied: systems-designer (Section G).* All are `config.csv` rows read once at boot (Data layer R10).

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `income_ref_per_level` (exists) | 1,000 | 500 – 5,000 | Every "hours of income" price (school change, forge planning) becomes cheap relative to real income only if hunting is not re-tuned too | Prices feel cheap | Zones and hunt drop tuning; Schools `school_change_income_hours` |
| `guild_tax_pct` (exists) | 0.10 | 0 – 0.20, ≤ every Chợ Bang `tax_rate_cap` | Members poor, mood falls (Retention) | Fund relies on shops only | `tax_rate_cap` (30); Retention's tax→mood curve |
| `economy_tax_live` (new) | true (MVP and later; user decision 2026-11-16, was false in MVP) | bool | — | — | Switch, not a balance knob; false only in test/tuning builds |
| `economy_tax_slider_live` (new) | false (MVP), true (Vertical Slice) | bool | — | — | Scope switch: the player's `set_tax_rate` and Retention's tax→mood effect |
| `economy_lb_shop_live` (new) | false (MVP), true (Vertical Slice) | bool | — | — | Scope switch for R16 |
| `lb_price_recruit_token` (new) | 150 | 40 – 382 (F9: 0.1 – 1.0 week) | Invitations rare; Linh Bảo piles up | Invitations replace walk-ins | Recruitment R13; Quests F6 |
| `lb_price_enhance_ward` (new) | 60 | 40 – 382 | Linh Bảo wards irrelevant; crafting the only source | +11…+20 becomes routine; forge stops being a gold sink | Enhancement F3 `W`; Crafting ward recipe |
| `lb_price_school_token` (new) | 200 | 40 – 382 | School change gated by the token's other sources | Changes become routine (the gold cost still applies) | Schools F2 |
| `items.csv` `lb_price` (proposed column) | 0 (not offered) | 0, or 50 – 1,000 | — | — | Special items on the R16 list |
| `tax_change_cooldown_s` (new) | 3,600 | 600 – 86,400 | Player cannot react to a crisis | Event spam, mood whiplash | F8 ring budget |
| `shop_fund_share_pct` (new) | 0.30 | 0.10 – 0.50 | Consumption stops being a sink; fund inflates after buildings max | MVP fund starves; buildings stall | `guild_tax_pct` (together they set the fund's income share) |
| `guild_upkeep_per_level_day` (exists) | 700 | 0 – 2,400 | Arrears become normal at low tax (2,400 ≈ 10% of income) | Fund grows unchecked late | `shop_fund_share_pct`, `guild_tax_pct`; `arrears_days_per_level` (30) sets how hard arrears bite |
| `bank_interest_cap_pct` (new) | 100 | 0 – 200 | Above 100 the bank grows the fund on its own | Tiền Trang pointless | `guild_upkeep_per_level_day` |
| `starting_fund_gold` (new) | 2,000 | 1,750 – 10,000 | Skips the opening decision | Cannot afford the three level-1 shops (450 + 700 + 600 = 1,750) | `buildings.csv` level-1 costs |
| `metrics_window_h` (new) | 24 | 1 – 168 | Memory (one int pair per hour) | Noisy ratio | — |
| `linh_bao_balance_max` (new) | 10,000,000 | ≥ 100,000 | — | Clamps legitimate rewards | Quests (25) reward sizes |

**Not knobs (constants):** `gold_balance_max` 10¹⁵, `gold_op_max` 10¹², the entry-type IDs, the event type block 2700–2799, the P4 order 2700. Changing any is a `sim_version` bump (Sim core R12).

**Pointed to, not owned:** item prices (26), building costs and `tax_rate_cap`/`daily_interest_pct` (30), forge costs (24), rebirth `gold_cost` (23), `change_gold_cost` (20), monster gold `base_gold_coef`/`base_gold_exp` (26, Items F1), sell ratios `mat_sell_ratio`/`equip_sell_ratio` (26, Items F5), and the simulator's consumption policy `potion_use_per_hour`, `feast_use_per_hour`, `brew_use_per_hour` (Utility AI 12 / Dev tooling 43 — `sim/economy.py` uses them analytically).

## Visual/Audio Requirements

Not required for the Economy category; a brief note. No art bible exists yet (`design/art/art-bible.md` absent), so this is drafted from GDD §1's pixel-2D tone.
- **Fund change:** a small coin tick on the fund counter when it rises; a muted drop when upkeep is charged. No sound per member purchase (too frequent).
- **Arrears:** the fund counter turns to a warning style with an icon (not colour alone) and one warning cue when the guild enters arrears; a relief cue when it clears.
- **Forge and buildings:** their own GDDs own the spend feedback; this system only supplies the event.

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:gold-economy` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

Optional for Economy. Target: the fund counter updates within one frame of the P6 event that changed it, and rolls up rather than jumping for changes above 1% of the balance, so income reads as a flow. No hitch: no ledger work runs on the render thread.

## UI Requirements

1. **HUD:** fund balance and Linh Bảo always visible; arrears warning when `In arrears`.
2. **Treasury screen:** last hour / last 24 h totals by entry type, grouped as income, transfers and spending; the current tax rate — in MVP a read-only "Thuế bang 10%" line; from Vertical Slice a slider limited to `tax_cap_ppm` with the cooldown shown; the next daily upkeep charge, the time until it and whether the fund covers it; `out_in_ratio` as a plain-language "spending X% of what the guild earns".
3. **Member card:** the member's wallet; what they bought recently (from `shop_sale` events).
4. **Spend confirmations:** any player-ordered cost shows the fund before and after; an unaffordable button is disabled with the missing amount, not hidden.
5. Numbers use locale grouping (vi and en); amounts at or above `l10n_compact_threshold` (10,000) are abbreviated by Localization F2 (`format_compact`, the formatting owner), with the exact value on long-press. *(consistency-check 2026-11-16: was "above a million"; Guild screens OQ-13.)*

> **📌 UX Flag — Gold economy**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for each screen or HUD element this system contributes to **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD uses | Source | Section / rule | Kind |
|---|---|---|---|
| Six phases; P4 is economy; handler order steps of 100 | `sim-core-and-tick-loop.md` | R2, R4 | Rule dependency |
| Anchored deadline ticks; Offline owns crossed due ticks | `sim-core-and-tick-loop.md` | R5 | Rule dependency (R8, R14) |
| Integer state; money is integer; int64 as JSON strings | `sim-core-and-tick-loop.md` | R6, R13 | Rule dependency |
| `ctx.fail` and failure semantics | `sim-core-and-tick-loop.md` | R10 | Rule dependency (R13) |
| Type blocks of 100; ring budget 10,000/day; `register_type` | `event-bus-and-history-log.md` | R2, R3, F4 | Rule dependency (F8) |
| Typed `config.csv`, validator as build gate, `content_id_none` | `data-layer-and-content-pipeline.md` | R2, R6, R10 | Data dependency |
| `change_gold_cost` debits the fund; `income_ref_per_level` owned here | `schools-and-school-change.md` | R4, F2 | Data dependency (consistent) |
| Boot-time float → integer conversion pattern | `xp-and-level-pacing-curve.md` | R2 | Pattern reused |
| Two tiers, Linh Bảo, sinks | `JX1_Tycoon_GDD.md` | §6.6, §19 | Design source |
| Reference income, tax, upkeep, building totals, out/in targets | `JX1_Tycoon_GDD.md` | §19.1, §19.4, §19.5, §18.3 | Design source |
| S3 money-conservation acceptance | `JX1_Tycoon_GDD.md` | §20 S3 | Acceptance source |
| Analytic economy model | `sim/economy.py` | `income_per_hour`, `upkeep_per_hour` | Retrofit reference (OQ-3) |
| Trip payout of gold + loot value to members | `sim/hunt.py` | `run_trip`, `roll_drops` | Retrofit reference |

## Acceptance Criteria

*Lens applied: qa-lead (Section H).* Story types: AC-1 to AC-22 are **Logic** (automated unit tests in `tests/unit/gold_economy/`); AC-23 to AC-25 are **Integration**; AC-26 is **UI** (screenshot).

**Accounts and the ledger (R1–R5)**
- **AC-1 (R1)**: **GIVEN** a new guild with defaults, **THEN** fund = 2,000, every wallet = 0, Linh Bảo = 0, and all are integers.
- **AC-2 (R2)**: **GIVEN** a static scan of the sim code, **THEN** no file except the ledger writes a member's `gold`, `Guild.funds` or the Linh Bảo balance.
- **AC-3 (R3)**: **GIVEN** a call `credit(upkeep, fund, 100)` (a burn type used as a mint) or `transfer(tax, fund, wallet, 100)` (wrong direction), **THEN** both return `bad_account` and no balance changes.
- **AC-4 (R4)**: **GIVEN** a fund of 999, **WHEN** a 1,000-gold `building_cost` is debited, **THEN** it returns `insufficient`, the fund is still 999, and one `ledger_refused` event is emitted. **GIVEN** a fund of 1,000, **THEN** the same debit succeeds and leaves 0.
- **AC-5 (R4)**: **GIVEN** amounts 0, −1, 5.0 and 10¹² + 1, **THEN** each is refused with `invalid_amount`; 10¹² is accepted for a credit.
- **AC-6 (R5)**: **GIVEN** a wallet at `gold_balance_max` − 10, **WHEN** 100 is credited, **THEN** the wallet is at the cap, `total[balance_clamp]` rose by 90 and `balance_clamped` was emitted with excess 90.
- **AC-7 (R3)**: **GIVEN** a release build, **WHEN** `dev_grant` is called, **THEN** it is refused and nothing changes; **GIVEN** a test build, **THEN** it succeeds.

**Tax (R6, F1)**
- **AC-8 (F1)**: **GIVEN** tax live at 100,000 ppm, **WHEN** 7,000 `hunt_gold` is credited, **THEN** the wallet gains 6,300 and the fund 700. **GIVEN** a 9-gold credit, **THEN** tax is 0. **GIVEN** rate 0, **THEN** tax is 0. **GIVEN** rate 200,000 and 7,000, **THEN** tax is 1,400.
- **AC-9 (R6)**: **GIVEN** tax live, **WHEN** a `salary` or `gold_award` is paid, **THEN** no tax is taken.
- **AC-10 (R6)**: **GIVEN** Chợ Bang level 1 (cap 110,000), **WHEN** `set_tax_rate(120,000)` is ordered, **THEN** it is refused `out_of_range`; **WHEN** `set_tax_rate(110,000)` is ordered and then `set_tax_rate(50,000)` 1,000 s later, **THEN** the first applies and the second is refused `cooldown`.
- **AC-11 (R6, MVP flat tax)**: **GIVEN** the MVP defaults (`economy_tax_live = true`, `economy_tax_slider_live = false`) and a guild with no Chợ Bang, **WHEN** 7,000 `hunt_gold` is credited, **THEN** the wallet gains 6,300 and the fund 700, and `set_tax_rate(50,000)` is refused `not_live` with the rate unchanged at 100,000. **GIVEN** `economy_tax_live = false` (test build), **THEN** the wallet gains 7,000.
- **AC-11b (R16)**: **GIVEN** `economy_lb_shop_live = true`, Linh Bảo 200 and `lb_price_enhance_ward = 60`, **WHEN** `lb_buy(item_enhance_ward, 3)` is applied, **THEN** Linh Bảo is 20, storage gained 3 wards, `total[lb_spend]` rose by 180 and F6's Linh Bảo identity holds. **WHEN** `lb_buy(item_enhance_ward, 1)` follows, **THEN** it is refused `cannot_afford` and nothing changes. **GIVEN** an item with `lb_price = 0`, or `economy_lb_shop_live = false`, **THEN** `lb_buy` is refused `not_live`.
- **AC-11c (R16 validator)**: **GIVEN** `items.csv`, **THEN** every row with `lb_price > 0` has sell value 0 or is unsellable, and is not a potion, feast, brew or food.

**Shop sales (R7, F2)**
- **AC-12 (F2)**: **GIVEN** a wallet of 3,000 and the default share, **WHEN** `shop_sale` of 2,800 is made, **THEN** the wallet is 200, the fund rose 840, `total[shop_cost]` rose 1,960. **GIVEN** share 0, **THEN** the fund rises 0; **GIVEN** share 1.0, **THEN** burn is 0.
- **AC-13 (R7)**: **GIVEN** a wallet of 2,799, **WHEN** a 2,800 sale is attempted, **THEN** it is refused and nothing changes.

**Upkeep, salary, interest (R8, F3, F5)**
- **AC-14 (F3)**: **GIVEN** 20 members with levels summing to 1,400 and a large fund, **WHEN** one day slot runs, **THEN** exactly 980,000 is burned as `upkeep`. **GIVEN** `guild_upkeep_per_level_day` = 0, **THEN** 0 is burned and the guild stays `Solvent`.
- **AC-15 (R8)**: **GIVEN** a fund of 10,000 and a charge of 980,000, **THEN** 10,000 is burned, the fund is 0, `upkeep_arrears_days` = 1 and `fund_arrears_started` is emitted; **WHEN** the next day's charge is paid in full, **THEN** `upkeep_arrears_days` = 0 and `fund_arrears_cleared` is emitted. No building level, member or item changed.
- **AC-16 (R8)**: **GIVEN** an empty roster, **THEN** the charge is 0 and `upkeep_arrears_days` stays 0.
- **AC-17 (R8)**: **GIVEN** a fund of 1,000 and salaries of 600 (member 3) and 600 (member 5) due on the day slot, **THEN** member 3 is paid, member 5 is not and receives `salary_unpaid`, and the fund is 400.
- **AC-18 (F5)**: **GIVEN** Tiền Trang level 8 and an upkeep charge of 980,000, **WHEN** the day slot runs with fund 10,000,000, **THEN** 160,000 is minted; with fund 100,000,000, **THEN** 980,000 is minted; with no Tiền Trang, **THEN** 0.
- **AC-19 (R8)**: **GIVEN** a day slot with upkeep, an unpaid salary and a Tiền Trang, **THEN** the event order is `upkeep_charged`, then any `salary_unpaid`, then the interest credit.

**Conservation and offline (R11–R14, F6)**
- **AC-20 (F6, S3)**: **GIVEN** a seeded 30-day headless run of a 20-member guild with tax live, shops, upkeep, salaries, a departure and a return, **THEN** F6 holds after every tick, and the gold identity's difference is 0.
- **AC-21 (R14)**: **GIVEN** a 50-hour offline gap that crosses 2 day slots, **WHEN** Offline progress resolves it, **THEN** exactly 2 upkeep charges are made, each against the fund as it stood after the income credited before it, the first live tick after the skip charges none, and F6 holds.
- **AC-22 (R11)**: **GIVEN** a member with 5,000 gold, **WHEN** they leave, **THEN** `total[member_departed]` rises 5,000, the fund is unchanged, and F6 holds.

**Integration**
- **AC-23 (Zones and hunt)**: **GIVEN** a party of 5 returns from a trip, **THEN** each member receives exactly one taxable credit per mint type used, every amount is an integer, and the sum of credits equals the trip's gold plus handover value as computed by Zones and hunt.
- **AC-24 (§19.5)**: **GIVEN** the S3 balance scenario at levels 30, 60 and 100, **THEN** `out_in_ratio` over 24 h is in 0.60–0.90, the fund at day 30 is within 2× its day-15 value, and a level-100 member with full gear holds ≤ 50 `cash_surplus_hours`. (Simulator check; fails S9 if out of band.)
- **AC-25 (Schools)**: **GIVEN** a paid school change at level 60 and a fund of 240,000, **THEN** the fund is 0 after the change and `total[school_change_cost]` rose 240,000; **GIVEN** a fund of 239,999, **THEN** the change is refused with no gold or item taken.
- **AC-26 (UI)**: **GIVEN** a guild in arrears, **THEN** a screenshot of the HUD and the Treasury screen shows the warning icon, the next upkeep charge and last-24-h totals, retained in `production/qa/evidence/`.

**Performance**: the ledger's P4 handler does no work on ticks without a due slot (one integer compare); a ledger call is O(1). P4's provisional share is 15% of a tick (Sim core F6).

*QA lens gaps found:* none uncovered among R1–R16 and F1–F7 (F9 is a sizing target checked in S5); F8 is covered by the event-volume declaration being checked at `seal()` (Event bus F4), so no separate criterion. AC-24 depends on simulator calibration (OQ-1) and may fail until S3 tunes the knobs — that is its purpose.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | `shop_fund_share_pct` 0.30, `starting_fund_gold` 2,000 and `bank_interest_cap_pct` 100 are reasoned, not simulated. Calibrate in S3 (`sim/economy_full.py`) against AC-24 | This GDD + Dev tooling (43) | S3 |
| OQ-2 | Does real hunting income match `income_ref_per_level` (±15%) once money is integer and loot handover is minted? | Zones and hunt (11), Dev tooling (43) | S3 |
| OQ-3 | Retrofit gaps in `sim/`: money is float (`Member.gold`, `run_trip` share); no fund, tax, upkeep or ledger; `economy.upkeep_per_hour` means *consumable spend*, not guild upkeep — rename it when porting to avoid two meanings of "upkeep"; `enhance_*` belongs to Enhancement (24) | Dev tooling (43) / S3 | S3 |
| OQ-4 | Salary shortfall pays in `member_id` order. Should Retention prefer pro-rata or player-chosen priority? | Retention (16) | When Retention is designed |
| OQ-5 | **Scope question (not decided here):** who pays forge attempts — the fund (player-ordered) or the member's wallet (member-driven, as S5's simulated policy suggests)? The ledger supports both (`enhance_cost` from either) | Enhancement (24) + user | When Enhancement is designed |
| OQ-6 | **RESOLVED (user decision 2026-11-16):** Linh Bảo is never sold for real money; it buys Chiêu Hiền Lệnh, the enhancement ward, the Scripture token (school change) and special items through R16, priced by F9 against the ~382/week quest faucet. Follow-up: JX1_Tycoon_GDD.md §6.6 [MỞ], §19's preamble ("Linh Bảo không mua được bùa cường hoá") and §19.3 (ward "chỉ chế tạo, không bán") still read the old way and need a master-GDD edit | User + In-app purchases | Closed (master-GDD follow-up open) |
| OQ-7 | New `config.csv` keys to add with validator ranges: `economy_tax_live`, `tax_change_cooldown_s`, `shop_fund_share_pct`, `bank_interest_cap_pct`, `starting_fund_gold`, `metrics_window_h`, `linh_bao_balance_max`, `economy_tax_slider_live`, `economy_lb_shop_live`, `lb_price_recruit_token`, `lb_price_enhance_ward`, `lb_price_school_token`; proposed `items.csv` column `lb_price` (int ≥ 0) with validator rules: 0 or 50–1,000; a row with `lb_price > 0` has sell value 0 or is unsellable and is not a potion/feast/brew/food. Schema approved in principle (user decision 2026-11-16), added with the economy story | Data layer (3) | Before the economy story |
| OQ-8 | **RESOLVED (consistency-check 2026-11-16):** Member model field table holds `gold` (writer: this system only) and `contract{salary, demands[]}` (writer: Retention 16). | Member model (8) | Closed |
| OQ-9 | **RESOLVED (consistency-check 2026-11-16):** Items R6 — equipment is auto-equipped or sold, materials go to storage and are paid at sell value as `loot_handover`, other items go to storage unpaid; `price` is the shop price (Items R1); the gold award is `gold_award` (Items R8) | Items and loot (26) | Closed |
| OQ-10 | PROVISIONAL: Guild and buildings (30) — exposes the current Chợ Bang `tax_rate_cap` and Tiền Trang `daily_interest_pct`; owns the buff fade from `upkeep_arrears_days`; with no Chợ Bang the tax cap is 0 | Guild and buildings (30) | When Guild and buildings is designed |
| OQ-11 | **RESOLVED (consistency-check 2026-11-16):** Zones R8 credits integer `hunt_gold` and `loot_handover` once per member per trip and owns the split (equal shares over the whole roster, remainder by ascending member ID); Items `hand_in` returns the totals and credits nothing | Zones and hunt (11) | Closed |
| OQ-12 | **RESOLVED (consistency-check 2026-11-16):** Offline R9 step 4 calls `settle_schedule` per slice and R14 credits `offline_hunt` (taxed); Golden Boss R10 credits personal gold to wallets and table gold to the fund as `boss_reward`. | Offline (31), Golden Boss (14) | Closed |
| OQ-14 | **RESOLVED (user decision 2026-11-16):** a flat tax at `guild_tax_pct` is live from MVP (R6), so `guild-and-buildings.md` F4's assumption that guild income comes from member tax holds in MVP; the slider and its mood effect are Vertical Slice | Guild and buildings (30) + this GDD | Closed |
| OQ-15 | **RESOLVED (consistency-check 2026-11-16):** Items R13 forbids selling materials from storage (they were paid at hand-in), and `sell_item` (R15/API) refuses them; equipment and items stored at hand-in were not paid for, so selling them is not double payment | Items and loot (26) + this GDD | Closed |
| OQ-13 | Do Elders (Ascension, 23) count toward upkeep? This GDD counts every roster member. **RESOLVED (consistency-check 2026-11-16):** yes — Rebirth R10 agrees (an L200 Elder ≈ 0.1% of late daily income); F3 unchanged | Rebirth and Ascension (23) | Closed |
