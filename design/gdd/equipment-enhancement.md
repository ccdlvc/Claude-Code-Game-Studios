# Equipment Enhancement

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run; decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet); serves JX1_Tycoon_GDD.md §19.3 (the forge as the bottomless late-game gold sink) and §1 ("thành viên mạnh hơn")

## Summary

Equipment enhancement is the Luyện Khí Đài forge: the bang chủ pays guild gold to try to raise an equipped item from +0 up to +20, each step adding a fixed share to the item's flat stats. Early steps are cheap and nearly certain; from +6 a failure drops the item one level unless a ward (Bùa Hộ Cường, crafted or bought with Linh Bảo) is burned, and from +11 the odds and the costs make the forge a sink no guild ever fills. It exists so that a rich late-game guild always has a reason to want more gold (§19.3), and so that a favourite member's weapon can grow with them instead of being replaced by every new drop.

> **Quick reference** — Layer: `Feature` · Priority: `Vertical Slice` · Key deps: `Deterministic RNG, Member model, Items and loot tables, Gold economy, Guild and buildings, Data layer and content pipeline, Command layer, Event bus and history log`

## Overview

Equipment enhancement owns one number per equipped item, its enhancement level `enhance_lv` (0–20), and the one rule that changes it: an **attempt**. The player picks a member and a gear slot and orders an attempt through the `enhance_item` command. The attempt costs guild-fund gold (F1), optionally burns one ward from guild storage, and rolls once against the target level's success chance in `data/enhance.csv` (F2). Success raises the level by one; failure leaves it unchanged below +6 and, from +6, drops it by one unless a ward was used. An item is **never destroyed**. How high an item may go is capped by the Luyện Khí Đài's level (`max_enhance_lv`, 2 → 20, owned by Guild and buildings). The bonus itself, `stat_pct_total` (+4 % at +1 up to +65 % at +20), multiplies the item's flat stats in the Member model's gear sum.

For the player it is an active, short decision: which member's gear deserves the gold, how far to push, and whether a ward is worth it at this step. Without it the gold economy has no unbounded sink (Gold economy R9: "the forge is the designed bottomless sink"), the late game has no use for a large fund, and gear progression is purely "replace with a higher tier".

**What this system does not own:**
- Gold balances and debits: Gold economy (27) owns the ledger; this system calls `debit(enhance_cost, fund, …)` with entry type 23.
- Guild storage and the ward item: Items and loot (26) owns storage (`count`/`take`) and the `item_enhance_ward` row; Crafting (28) owns how wards are made; Gold economy (27) R16 sells them for Linh Bảo at `lb_price_enhance_ward` (user decision 2026-11-16).
- The cap value per building level and its arrears fade: Guild and buildings (30) owns `effect(bld_enhance, max_enhance_lv)`.
- How the bonus enters combat stats: Member model (8) F2 applies `stat_pct_total` to flat stats; this system owns the table values.
- Randomness: Deterministic RNG (2) owns the generator; this system owns its event key and draw order.

## Player Fantasy

**Both.** The player acts on the forge directly (choose, pay, watch the roll) and feels it indirectly in every fight the sharper blade wins.

*Lens applied:* creative direction (`references/lens-creative-director.md`). No pillars exist, so each framing is anchored to a JX1_Tycoon_GDD.md line instead of a quoted pillar.

1. **"The blade that grew with her" (chosen).** Anchor: §1, "thành viên mạnh hơn". *The moment:* the guild's oldest tank comes home from a boss fight, and the bang chủ spends the night's tax on taking her sword from +9 to +10. It holds. The sword's name on her panel now reads "+10" in gold. *Asks of the design:* enhanced gear is never lost, never auto-replaced or auto-sold (Items R6), and keeps its level through storage, school changes and rebirth.
2. **"The forge is never full."** Anchor: §19.3, "+11…+20 … là hố tiêu vàng cuối game". *The moment:* every building is maxed, the fund is fat, and +15 on the carry's weapon still eats a week of income. *Asks:* costs that scale without bound and a ward economy that makes +11…+20 possible but slow (F3).
3. **"Push or hold."** Anchor: §19.3, "Thất bại từ +6 trở lên tụt 1 cấp". *The moment:* the item sits at +7 at 70 %; the bang chủ has one ward left and wonders whether to save it for +9. *Asks:* visible odds, visible cost and a ward choice per attempt (UI Requirements).

Framing 1 is chosen (an emotional anchor for a Progression system whose payoff is attachment to a member); 2 and 3 are kept as supporting moments, and the rules below deliver all three. The game deliberately avoids JX1's "the item shatters" fear: §19.3 says "không bao giờ mất món".

## Detailed Design

*Lenses applied (Section 6 routing, Progression → Progression/XP/skills row): game-designer (primary), systems-designer (curves), economy-designer (sinks).*

- **game-designer:** the decision is *where* to put gold, not *whether* to tap. Keep the odds and the expected cost visible before each attempt; the ward choice is the one in-attempt decision and must be optional per attempt. The player must not be able to lose an item, or the attachment fantasy turns into dread.
- **systems-designer:** one integer level, one draw per attempt, fixed draw order, integer gold. The cap check must be against the *target* level, and the cap may fall (arrears) below the current level without touching it. The RNG key must be unique and not shiftable by unrelated actions (RNG Edge Cases, save-scumming).
- **economy-designer:** every attempt is a burn (Gold R9), the ward is never sold for gold or real money and is unsellable from storage (it is crafted, or bought with earned-only Linh Bảo at `lb_price_enhance_ward`, default 60 ≈ 0.16 of a week's quest faucet; Gold economy R16/F9), and enhanced items sell for the same as unenhanced ones so the forge never refunds. +1…+5 are cheap (≈0.3 member-income-hours per item, F3) so the early game feels the bonus; +10 costs ≈ 6 hours and +15 is only reachable with wards.
- No conflict between the roles needed a decision beyond the logged ones (decision log, 2026-11-16).

### Core Rules

**R1: What can be enhanced.** Only an item **equipped** in one of a member's four slots (`weapon`, `armor`, `ring`, `amulet`; Member model R5) can be enhanced. Items in guild storage cannot: storage is keyed by value `(content_id, enhance_lv)` with no per-instance identity (Items and loot R7). The level travels with the item: unequip, displacement, school-change moves and awards keep it (Member R6, Items R7–R8). Materials, consumables and specials have no enhancement level.

**R2: The command.** The player orders one attempt with the host command `enhance_item` (ID 2401):

| Arg | `arg_kinds` | Meaning |
|---|---|---|
| member | `entity` | The member wearing the item |
| slot | `int(1, 4)` | Slot code (Member model event codes: 1 weapon, 2 armor, 3 ring, 4 amulet) |
| use_ward | `int(0, 1)` | 1 = burn one `item_enhance_ward` on this attempt |
| stop_at | `int(1, 20)` | Refuse if the item is already at or above this level |

`stop_at` lets the UI submit "attempt ×N toward +T" as a Command layer R12 batch of N identical commands: once the item reaches +T the remaining commands are refused with `enhance_target_reached` and cost nothing. There is no auto-forge loop state.

**R3: Validation order.** The applier runs in P1 (Command layer R3) and checks, in this order; the first failure refuses with that reason and changes nothing:
1. The member exists and is on the roster → else `target_missing` (6).
2. The slot holds an item → else `target_missing` (6).
3. The member is not in `hunting`, `boss_raid`, `away`, `dead` or `training` (the same set as Member model R6 rule 6) → else `not_allowed_now` (7). The gear has to be at the forge.
4. Let `cur` be the item's level and `n = cur + 1` the target. If `cur ≥ stop_at` → `enhance_target_reached` (103).
5. If the Luyện Khí Đài is not built (`effect(bld_enhance, max_enhance_lv)` returns none) → `enhance_forge_not_built` (101).
6. If `n > cap` (F4) → `enhance_cap_reached` (100).
7. If `use_ward = 1`: the `enhance.csv` row `n` has `ward_usable = false` → `enhance_ward_not_usable` (102); `item_enhance_ward` is not live → `not_live` (9); guild storage `count(item_enhance_ward) < 1` → `cannot_afford` (8).
8. `can_debit(fund, cost)` with `cost = F1(item, n)` is false → `cannot_afford` (8).

**R4: Resolution.** If R3 passes, in the same handler with nothing between (Gold R4.2):
1. `debit(enhance_cost /*23*/, fund, cost, item_uid)`.
2. If `use_ward = 1`: `take({item_enhance_ward: 1})` from guild storage.
3. `o = enhance_attempt_ordinal`; then `enhance_attempt_ordinal = o + 1`.
4. `rng = derive(10 /*enhance*/, [o])`; `success = rng.chance_ppm(success_ppm[n])` — the attempt's **only** draw (RNG R7).
5. New level: success → `n`; failure and row `n` has `fail_effect = drop_1` and `use_ward = 0` → `cur − 1`; otherwise → `cur`.
6. Write the new level through Member model `set_enhance_lv(member_id, slot, lv)` (PROVISIONAL, OQ-3); the Member model re-derives the profile and rescales HP (Member R7, F5).
7. Emit the outcome event (R7).

The ward is consumed on every warded attempt, success or failure (matches `sim/economy.py` `enhance_expected_cost`, which adds the ward cost per attempt). Gold and ward are spent whether the roll succeeds or not.

**R5: Never lost.** No rule of this system removes, destroys or replaces an item. The worst outcome of an attempt is one level down. Level never goes below 0 (row 1–5 failures cannot drop; see Edge Cases).

**R6: The RNG key.** Domain 10 (`enhance`, RNG R4). Key `[enhance_attempt_ordinal]`: one guild-wide uint64 counter, starting at 0, saved with the guild, advanced **only** by step R4.3 of an accepted attempt. *Uniqueness (RNG R6):* each accepted attempt reads a value no earlier attempt read, and the counter never decreases or resets. *Not player-shiftable (RNG R5):* no other action, refusal, time passage or unrelated command advances it, so after a reload the next attempt gets the same dice whatever else the player did first (RNG AC-20). *Commit point (RNG OQ-6):* an attempt resolves atomically in the P1 apply that dispatches it, so dispatch is the commit; no separate pre-commit is needed. Probing the fixed next roll by reloading is accepted (RNG Edge Cases); see Edge Cases for the "burn a bad roll" variant.

**R7: Events.** This system registers the type block 2400–2499 (`enhance_event_type_block`) with the Event bus. Payload IDs for content are their `uid`.

| type_id | Name | Fields | Logged | Milestone | Subject slot | `ring_per_day` |
|---|---|---|---|---|---|---|
| 2401 | `enhance_succeeded` | `a` member_id, `b` item uid, `c` new level, `d` 1 if a ward was used | no | no | — | 0 |
| 2402 | `enhance_failed` | `a` member_id, `b` item uid, `c` level after, `d` flags (1 ward used, 2 dropped) | no | no | — | 0 |
| 2403 | `enhance_milestone` | `a` member_id, `b` item uid, `c` level (10, 15 or 20) | yes | yes | 1 | 10 |

2403 is emitted in addition to 2401 when a success reaches +10, +15 or +20. Command refusals are reported by Command layer 502 (host orders), not by an event of this block. Peak emission: 2 events per accepted attempt; attempts are host-only, bounded by the Command layer host cap (Command layer F1).

**R8: What it does not do.** Members never enhance their own gear (no Utility AI action, no wallet payment; OQ-1). Offline progress never makes attempts. Enhancement does not change an item's sell value (Items F5), its auto-equip dominance check (Items R6 already never displaces enhanced gear) or its equip requirements.

### States and Transitions

The item level is the state; transitions are one step per accepted attempt.

| From | Event | To | Condition |
|---|---|---|---|
| `cur` (0–19) | attempt succeeds | `cur + 1` | `cur + 1 ≤ cap` (R3.6) |
| `cur` (0–4) | attempt fails | `cur` | rows 1–5 `fail_effect = none` |
| `cur` (5–19) | attempt fails, no ward | `cur − 1` | rows 6–20 `fail_effect = drop_1` |
| `cur` (5–19) | attempt fails, ward | `cur` | ward consumed |
| any | cap falls below `cur` (arrears, R3.6) | `cur` | unchanged; only new attempts are refused |
| any | unequip / displacement / storage / award | same `cur` | the level travels with the item (R1) |
| 20 | — | — | terminal: `enhance_max_lv` |

The guild-wide `enhance_attempt_ordinal` has one transition: `o → o + 1` per accepted attempt.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|---|---|---|---|---|
| Command layer (5) | in | `enhance_item` envelopes in `seq` order | Applier return code (0 or a reason) | Command layer owns dispatch; this system owns ID 2401, args, reason codes 100–103 |
| Member model (8) | both | Member on roster, slot item, member state (via 41) | `set_enhance_lv(member, slot, lv)` (PROVISIONAL) | Member model owns the field storage; this system is its only writer (Member R5) |
| Member state machine (41) | in | Member state for R3.3 | — | 41 (PROVISIONAL, not designed) |
| Gold economy (27) | out | `can_debit(fund, cost)` | `debit(23 enhance_cost, fund, cost, item_uid)` | Ledger owns the debit; this system owns the amount (Gold R9) |
| Items and loot (26) | both | `count(item_enhance_ward)`, item `level_req` and `uid` | `take({item_enhance_ward: 1})` | Items owns storage and the item row |
| Guild and buildings (30) | in | `effect(bld_enhance, max_enhance_lv)` (effective level after arrears, its R6/R8) | — | Buildings owns which value is in force; this system owns its meaning |
| Deterministic RNG (2) | out | One `EventRng` | `derive(10, [o])`, one `chance_ppm` | RNG owns the generator; this system owns the key and draw order |
| Data layer (3) | in | `enhance` table rows (level 1–20), `config.enhance_base_per_level`, `config.enhance_max_lv` | — | Data layer owns loading and liveness; this system owns the rows' meaning |
| Event bus (42) | out | — | 2401–2403 | Bus owns delivery; this system owns block 2400–2499 |
| Local save (6) | out | — | `enhance_attempt_ordinal` (one uint64) | Save owns the format |
| Crafting (28) | in (indirect) | Wards appear in storage via its recipe `rec_item_enhance_ward` at `bld_enhance` level 3 | — | Crafting (PROVISIONAL, not designed) |
| Gold economy (27) | in (indirect) | Wards appear in storage via the Linh Bảo shop (`lb_buy`, R16) | — | Gold economy |
| Guild screens (39) | out | — | Forge screen data: odds, cost, F3 estimate | Guild screens owns layout |
| Dev tooling and balance sim (43) | out | — | F3 for balance tables; the S5 player policy | Dev tooling owns the harness |

## Formulas

*Lens applied: systems-designer (Section D) with economy-designer cost checks. Every formula was worked at its minimum, maximum and zero inputs.*

### F1: Attempt cost

The attempt_cost formula is defined as:

`cost = ceil_div(enhance_base_per_level × max(1, level_req) × cost_mult_milli[n], 1000)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| enhance_base_per_level | int | 30 (safe 10–100) | data file (`config.csv`) | Gold per item level per cost unit |
| level_req | int | 1 – 200 (0 for non-equipment, never enhanced) | data file (`items.csv`) | The item's tier requirement |
| n | int | 1 – 20 | calculated | Target level (current + 1) |
| cost_mult_milli[n] | int | 1,000 – 600,000 | data file (`enhance.csv` `cost_mult` × 1000, converted once at boot) | Cost multiplier for target n |

**Output Range:** 30 gold (L1 item, +1) to 3,600,000 gold (L200 item, +20) per attempt. Always ≥ 1 because both factors are ≥ 1; `max(1, …)` guards a `level_req = 0` row. Integer arithmetic only (Gold economy: integers only); `ceil_div` is exact on today's data (every `30 × cost_mult` is an integer).
**Example:** a level-70 sword, +9 → +10 (`cost_mult` 18): 30 × 70 × 18,000 / 1000 = **37,800** gold. The same sword +0 → +1: 2,100.

*Progression check:* cost scales linearly with `level_req`, and member income scales linearly with level (`income_ref_per_level` 1000 × L per hour, Gold economy), so the hours of income an enhancement costs are the same at every tier (F3). This is intended: the forge stays a constant-depth sink however far the guild progresses.

### F2: Success check

The success_check formula is defined as:

`success = chance_ppm(success_ppm[n])` — one draw from `derive(10, [enhance_attempt_ordinal])`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| success_ppm[n] | int (ppm) | 50,000 – 1,000,000 | data file (`enhance.csv`; today `success_pct` × 10,000, OQ-4) | Chance that the attempt to target n succeeds |
| enhance_attempt_ordinal | uint64 | 0 – 2⁶⁴−1 | calculated (saved counter, R6) | Event key |

**Output Range:** boolean. Rows 1–2 are 1,000,000 (always succeed; `chance_ppm` still consumes its one draw, RNG F6). Row 20 is 50,000 (5 %). A row of 0 would make the level unreachable; the validator rejects 0 (Tuning Knobs).
**Example:** +7 → +8, `success_ppm` 600,000: the attempt succeeds when the event's draw falls below 600,000 ppm (RNG F6).

### F3: Expected cost to a target (planning and balance)

The expected_enhance_cost formula is defined as:

`E_n = (c_n + w_n · W + (1 − p_n) · back_n) / p_n`, with `back_n = E_{n−1}` if row n is `drop_1` and `w_n = 0`, else 0; `Total(0 → T) = Σ_{n=1..T} E_n`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| c_n | int | 30 – 3,600,000 | calculated (F1) | Gold per attempt at target n |
| p_n | float | 0.05 – 1.0 | data file (`success_ppm[n] / 10⁶`) | Success chance |
| w_n | int | 0 or 1 | player policy | Ward used on attempts to target n (only where `ward_usable`) |
| W | int | ≥ 0 | calculated (balance assumption: 20,000 gold, the ward recipe's gold, materials excluded) | Gold-equivalent value of one ward |
| E_n | float | — | calculated | Expected gold to go from n−1 to n, first time |

**Output Range:** finite for every p_n > 0. Without wards the late rows compound: 0 → +20 on a level-70 item is ≈ 3.0 × 10¹³ gold (unreachable, by design). Floats are allowed here because F3 is never simulation state: it feeds the forge screen estimate and the balance simulator only.
**Example** (level-70 item; hours = gold ÷ 70,000, one member's reference income per hour):

| Target | No ward | Ward on every usable row (from +6) | `stat_pct_total` |
|---|---|---|---|
| +5 | 19,594 (0.28 h) | 19,594 (0.28 h) | +20 % |
| +8 | 98,771 (1.41 h) | 162,999 (2.33 h) | +32 % |
| +10 | 428,094 (6.1 h) | 397,899 (5.7 h) | +40 % |
| +12 | 2,637,296 (37.7 h) | 923,709 (13.2 h) | +45 % |
| +15 | 1.55 × 10⁸ (≈2,200 h) | 3,792,042 (54 h) | +52.5 % |
| +20 | 3.0 × 10¹³ | 58,342,042 (833 h) | +65 % |

These match `sim/economy.py` `enhance_expected_cost` and the "no ward" column of GDD §19.3. §19.3's "with ward" column (1.3 h at +5, 3.0 h at +8) adds the ward to every row including +1…+5, where R3.7 refuses it; the column above is the rule-correct one. The ward break-even sits near +9 to +10: below it, risking the drop is cheaper than the ward, which is the "push or hold" decision of Player Fantasy 3. *Guild scale:* the fund receives 10 % tax, so 20 members at the same level fund ≈ 2 member-hours of forge per hour; +8 on all 80 equipped items ≈ 113 member-hours ≈ 56 hours of fund income.

### F4: Effective cap

The enhance_cap formula is defined as:

`cap = min(effect(bld_enhance, max_enhance_lv), enhance_max_lv)`; none (not built) → attempts refused (R3.5)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| max_enhance_lv | int | 2 – 20 (2 per building level) | data file (`buildings.csv`, owned by Guild and buildings) | Cap at the forge's effective level after arrears |
| enhance_max_lv | int | 20 | data file (`config.csv`) | Absolute cap; also the last `enhance.csv` row |

**Output Range:** 2 – 20 once built. **Example:** Luyện Khí Đài level 6 with 2 arrears days (effective level 4, Buildings F4): cap = min(8, 20) = 8; an item at +12 stays +12, and an attempt to +13 is refused with 100.

### F5: Stat bonus (owned table, applied by the Member model)

The enhance_stat_bonus formula is defined as:

`bonus(lv) = 0` if lv = 0, else `stat_pct_total[lv]`; applied as Member model F2 `round(1000 · v_k · (1 + bonus))` for k in {atk, hp, def} only

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| lv | int | 0 – 20 | calculated (R4) | Item enhancement level |
| stat_pct_total[lv] | float | 0.04 – 0.65 | data file (`enhance.csv`) | Total bonus at lv (not per step) |

**Output Range:** 0 – 0.65; +4 % per level to +10 (+40 %), then +2.5 % per level to +20 (+65 %). Pct stats (`atk_pct`, `hp_pct`, `def_pct` on accessories) are **not** multiplied (confirms Member model OQ-2). **Example:** sword atk 444 at +10 → 444 × 1.40 = 621.6 atk (Member AC-14).

*Feedback loop:* enhanced gear → faster kills → more income → more enhancement. Intended and damped by the steep cost curve (F1/F3: each further 2.5 % above +10 costs several times the previous step) and by the building cap.

## Edge Cases

*Lens applied: systems-designer (Section E), on Sections C and D as written.*

- **If the item is at +20**: `n = 21 > enhance_max_lv`, refused with `enhance_cap_reached` (100) at R3.6; no gold, ward or ordinal is spent. The UI hides the attempt button.
- **If the item is at +0–+4 and fails**: rows 1–5 have `fail_effect = none`, so it stays; the level can never go below 0. The validator rejects `drop_1` on row 1 (a drop from +0 is impossible).
- **If the forge's cap falls below an item's level** (arrears, Buildings R8): the item keeps its level and bonus; attempts are refused until the cap is above the current level again (Buildings F4 example).
- **If the Luyện Khí Đài is being upgraded**: the previous level's cap applies until it completes (Buildings R6); the forge never closes.
- **If the member leaves, dies permanently or is removed while wearing enhanced gear**: Member model R9/Items own what happens to the gear; it keeps its level wherever it goes. This system has no hook.
- **If the slot's item is replaced between the player's tap and the P1 apply** (a hand-in auto-equip, an award): the attempt applies to whatever is in the slot at apply time, using that item's cost. Auto-equip never displaces enhanced gear (Items R6), so this only happens to a +0 item. The UI shows the item that was enhanced in the outcome toast.
- **If the fund holds exactly the cost**: the debit succeeds and leaves 0 (Gold economy edge case).
- **If `use_ward = 1` on a row that cannot drop** (+1…+5): refused with 102, nothing spent. A ward cannot be wasted by mistake.
- **If a batch "×N toward +T" runs out of gold midway**: the remaining commands are refused with `cannot_afford` (8), each costing nothing; Command layer R12 reports each outcome.
- **If two batches target the same item**: they apply in `seq` order; `stop_at` of each is checked against the level at apply time.
- **If the player reloads to retry an attempt** (save-scumming): the next attempt uses the same ordinal and gets the same draw (R6, RNG AC-20). **"Burning a bad roll"**: a player who learned by reloading that the next roll fails can spend it on a cheap 100 % attempt (+0 → +1 on a low-tier item) and so skip the known failure. This is the accepted probing property of fixed dice (RNG Edge Cases, user 2026-11-16); it costs a reload per roll and at most one cheap attempt. Not mitigated; revisit if Leaderboards (35) needs it (OQ-5).
- **If `enhance.csv` row n has `success_ppm = 0`**: the level n would be unreachable while still charging gold. The validator rejects it.
- **If an item row's `level_req` is 0**: F1 uses `max(1, …)`. Only equipment can be equipped (Member R6), and all 945 equipment rows have `level_req ≥ 1`.
- **If `item_enhance_ward` is retired or not live**: warded attempts are refused with 9; unwarded attempts still work.
- **If a game update changes `enhance.csv` odds or costs**: existing levels are kept; only future attempts use the new values. Lowering `stat_pct_total` changes every enhanced item's bonus at once (a balance patch, called out in patch notes).

## Dependencies

| System | Hard / Soft | Interface | Why |
|---|---|---|---|
| Deterministic RNG (2) | Hard | `derive(10, [ordinal])`, `chance_ppm` | The attempt roll |
| Data layer and content pipeline (3) | Hard | `enhance` table, `config.enhance_base_per_level`, `config.enhance_max_lv` | Odds, costs, bonus |
| Command layer (5) | Hard | `register_command(2401 enhance_item)`, reason codes 100–103 + shared 6–9 | The only way to attempt |
| Local save and migration (6) | Hard | Saves `enhance_attempt_ordinal` | Key uniqueness across loads |
| Member model (8) | Hard | Slot contents, roster, `set_enhance_lv` (PROVISIONAL) | The thing enhanced |
| Items and loot tables (26) | Hard | `count`/`take` on `item_enhance_ward`; item `level_req`, `uid` | Ward, cost input |
| Gold economy (27) | Hard | `can_debit`, `debit` with entry type 23 `enhance_cost` from the fund | Payment |
| Guild and buildings (30) | Hard | `effect(bld_enhance, max_enhance_lv)` | The cap |
| Event bus and history log (42) | Hard | Type block 2400–2499 | Outcomes and milestones |
| Member state machine (41) | Soft (PROVISIONAL) | Member state for R3.3 | Without it, only roster presence is checked |
| Crafting and recipes (28) | Soft (PROVISIONAL) | Produces wards | Without it, +11…+20 is practically unreachable |
| **Depended on by:** Guild screens (39), Quests and achievements (25, e.g. "reach +10"), Dev tooling and balance sim (43), Leaderboards (35) | — | Events 2401–2403, F3 | — |

Bidirectional check: Member model, Items and loot, Gold economy, Guild and buildings, Deterministic RNG, Data layer and Command layer already list Equipment enhancement — consistent. Guild screens (39) lists Enhancement — consistent. Command layer's provisional row gives `enhance_item` the single arg `item entity`; this GDD replaces it with member, slot, use_ward, stop_at (OQ-6).

## Tuning Knobs

*Lens applied: systems-designer (Section G), derived from the Formulas variable tables.*

| Knob | Where | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `enhance_base_per_level` | `config.csv` | 30 | 10 – 100 | Forge stops being affordable early; +5 no longer an early-game goal | Gold inflates late (§19.5 out/in ratio falls) | Every row's `cost_mult` scales with it |
| `enhance_max_lv` | `config.csv` | 20 | 10 – 20 (must equal the last `enhance.csv` row) | Rows above 20 do not exist | Cuts the late-game sink | `max_enhance_lv` above it is inert |
| `success_pct` → `success_ppm` per row | `enhance.csv` | 1,000,000 … 50,000 | > 0 and non-increasing by row | Sink collapses (high levels cheap) | Rows become unreachable; validator rejects 0 | `fail_effect`: drop rows compound with low odds (F3) |
| `cost_mult` per row | `enhance.csv` | 1 … 600 | ≥ 1, non-decreasing | +10 no longer a "normal" goal | Forge no longer a sink | `enhance_base_per_level` |
| `fail_effect` per row | `enhance.csv` | none 1–5, drop_1 6–20 | `none` on row 1 | Drop from +1 frustrates early | No risk; wards become pointless | `ward_usable` (true only matters on drop rows) |
| `ward_usable` per row | `enhance.csv` | true 6–20 | true only where `drop_1` | Wards wasted on rows that cannot drop (R3.7 refuses anyway) | +11…+20 effectively unreachable | Ward recipe cost (Crafting 28) sets W in F3 |
| `stat_pct_total` per row | `enhance.csv` | 0.04 … 0.65 | non-decreasing; +10 ≤ 0.40 until S5 proves otherwise | Boss 1.5× level becomes winnable (S5 gate) | Forge not worth the gold | Combat `def_k_*` (Combat Tuning Knobs) scales the value of def bonus |
| `max_enhance_lv` per building level | `buildings.csv` | 2 → 20 | Owned by Guild and buildings (30) — pointed to, not duplicated | — | — | F4 |
| Ward recipe gold / materials | `recipes.csv` | 20,000 + `mat_z06_1:8; mat_z06_2:2` | Owned by Crafting (28) | — | — | F3 `W` |

## Visual/Audio Requirements

Progression category: optional; a brief note suffices at the GDD stage. No art bible exists (`design/art/art-bible.md` absent); this is drafted from §19.3 and the Player Fantasy.

- **Attempt:** a short forge strike on the Luyện Khí Đài sprite (≤ 0.6 s), then the outcome. Success: the item icon flashes and its `+N` label ticks up; failure without a drop: a dull spark; failure with a drop: the `+N` label ticks down with a cracked-ember particle, never a shattering effect (the item is never lost, R5); a ward used: a brief talisman glyph burns away.
- **Milestones (+10, +15, +20):** a larger effect and the 2403 entry in the guild chronicle; the item's `+N` label changes colour tier (for example white below +5, green +5–+9, gold +10–+14, red +15+) **and** gains a pip count, so colour is never the only cue.
- **Audio:** hammer hit per attempt; distinct rising chime for success, lower thud for failure, a distinct "ward burn" sound. Failure sounds must not be punishing (no glass break).

## Game Feel

- One tap → outcome visible within one tick plus the ≤ 0.6 s strike animation. "×N" batches play a compressed animation per attempt (≤ 0.2 s each) with a skip-to-result option.
- No confirmation dialog for unwarded attempts below the item's drop threshold; a single confirm for the first attempt that can drop the item (+5 → +6) in a session, with "don't ask again".

## UI Requirements

- **Forge screen** (Guild screens 39), reached from the Luyện Khí Đài and from the member panel's gear slot: member and slot picker; the item with its current `+N` and its flat stats now and at `+N+1` (F5); success chance (F2 row, shown as a percentage), attempt cost (F1), fund balance; failure consequence in words ("stays at +N" / "drops to +N−1"); ward toggle with storage count, disabled with a reason on rows 1–5; the current cap (F4) and why (building level, arrears); an expected-cost estimate to a chosen target (F3, labelled as an average, not a promise).
- **Batch:** "Attempt ×N toward +T" with N and T pickers; shows the worst-case gold (N × the costs).
- Every refusal reason (100–103 and 6–9) is shown in words through `i18n/` keys `cmd_reason.enhance.<name>`.
- Text fields need room for Vietnamese diacritics and the longest localisation (Localization 4).

> **📌 UX Flag — Equipment enhancement**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the forge screen **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD's section | Other GDD | Their section | Relationship |
|---|---|---|---|
| R1, R4.6, F5 | `member-model.md` | R5, R6, F2, OQ-2 | `enhance_lv` field and gear sum; OQ-2 answered (flat only) |
| R3.3 | `member-model.md` | R6 rule 6 | Same blocked-state set |
| R4.1, R8 | `gold-economy.md` | R1, R3 (type 23), R4, R9, OQ-5 | Fund pays player-ordered attempts; OQ-5 answered for the player command |
| R3.7, R4.2, R8 | `items-and-loot-tables.md` | R6, R7, R8, F5, OQ-10 | Ward from storage; level travels with the item; OQ-10 answered (sell value ignores enhancement) |
| F4, Edge Cases | `guild-and-buildings.md` | R6, R8, F4, AC-10, AC-11 | Cap from `max_enhance_lv` |
| R6, Edge Cases | `deterministic-rng.md` | R4 (domain 10), R5, R6, R7, Edge Cases (save-scumming), AC-20, OQ-6 | Key `[ordinal]`; OQ-6 answered (dispatch is the commit) |
| R2, R3 | `command-layer.md` | R2, R6, R12, vocabulary row `enhance_item`, OQ-8 | Command ID, args and reason codes |
| R7 | `event-bus-and-history-log.md` | R3 | Block 2400–2499 |
| F2 | `data-layer-and-content-pipeline.md` | R2, R4 (ppm rule), OQ-1 | `success_pct` → `success_ppm` |
| Tuning Knobs | `combat.md` | Tuning Knobs (`def_k_*`) | Value of the def bonus |
| AC-16 | `xp-and-level-pacing-curve.md` | OQ-6 | Re-measure pacing with enhancement |

## Acceptance Criteria

*Lens applied: qa-lead. "Logic" criteria are automated unit tests in `tests/unit/equipment_enhancement/` (and `sim/` tests for the Python reference); "Integration" runs with real Gold economy, Items, Buildings and RNG; "Balance" runs the balance simulator; "UI" needs a retained screenshot.*

- **AC-1 [Logic] (R4, F1, F2 success)**: **GIVEN** a member at home wearing a level-70 sword at +9, Luyện Khí Đài level 5 (cap 10), fund 100,000, and a fixture seed whose draw for ordinal `o` succeeds at 400,000 ppm, **WHEN** `enhance_item(member, 1, 0, 20)` applies, **THEN** the sword is +10, the fund is 62,200 (cost 37,800), the ordinal is `o + 1`, and events 2401 `(member, sword uid, 10, 0)` and 2403 `(member, sword uid, 10)` were emitted.
- **AC-2 [Logic] (R4.5 drop)**: **GIVEN** the same at +7 and a draw that fails row 8 (600,000 ppm), no ward, **WHEN** applied, **THEN** the sword is +6, the fund fell by 30 × 70 × 8 = 16,800, and 2402 has `d = 2`.
- **AC-3 [Logic] (R4.5 ward)**: **GIVEN** +7, 1 ward in storage, a failing draw, **WHEN** applied with `use_ward = 1`, **THEN** the sword stays +7, storage holds 0 wards, the fund fell by 16,800, and 2402 has `d = 1`.
- **AC-4 [Logic] (R4.5 no-drop rows)**: **GIVEN** +3 and a failing draw for row 4 (900,000 ppm), **WHEN** applied, **THEN** the sword stays +3.
- **AC-5 [Logic] (R3 order and refusals)**: each of the following refuses with the given code and leaves fund, storage, item level and ordinal unchanged: empty slot → 6; member `hunting` → 7; `cur = 5`, `stop_at = 5` → 103; forge not built → 101; cap 8, `cur = 8` → 100; `cur = 20`, cap 20 → 100; `use_ward = 1` at `cur = 3` → 102; `use_ward = 1` with 0 wards → 8; fund 37,799 for a 37,800 attempt → 8. **GIVEN** an empty slot and a hunting member together, **THEN** the code is 6 (order).
- **AC-6 [Logic] (F1 boundaries)**: cost for (L1, +1) = 30; (L70, +3, `cost_mult` 1.5) = 3,150; (L200, +20) = 3,600,000; an item row with `level_req = 0` gives the L1 cost.
- **AC-7 [Logic] (F2 always-succeed rows)**: **GIVEN** `cur = 0` and any seed, **WHEN** 1,000 attempts are made on fresh +0 items, **THEN** all succeed and the ordinal advanced by 1,000 (one draw consumed each).
- **AC-8 [Logic] (F3)**: `Total(0 → 10)` for a level-70 item with no wards is 428,094 ± 1 gold and `Total(0 → 15)` with wards from +6 at `W = 20,000` is 3,792,042 ± 1, matching `sim/economy.py` `enhance_expected_cost` for the no-ward case.
- **AC-9 [Logic] (F4 arrears)**: **GIVEN** Luyện Khí Đài 6 and 2 arrears days (`max_enhance_lv` 8) and an item at +12, **THEN** the item stays +12 with bonus 0.45, an attempt is refused with 100, and after arrears reset an attempt to +13 is accepted.
- **AC-10 [Logic] (R6 key)**: **GIVEN** a save just before an attempt, **WHEN** the attempt is made, the save reloaded, one item sold, 60 s of game time passed and the attempt repeated, **THEN** both attempts derive `(10, [o])` with the same `event_seed` and outcome; the next attempt derives `[o + 1]`; a refused attempt between them does not advance `o`. (Satisfies RNG AC-20 a/b.)
- **AC-11 [Logic] (R5 conservation)**: **GIVEN** 10,000 random-seeded attempts across items at +0…+19, **THEN** no item left its slot, every level is in 0…20, and each level changed by −1, 0 or +1 per attempt.
- **AC-12 [Integration] (Gold ledger)**: **GIVEN** a run of 500 attempts, **THEN** ledger `total(enhance_cost)` equals the sum of F1 costs of accepted attempts, the fund never went negative, and the conservation identity (Gold F6) holds.
- **AC-13 [Integration] (level travels)**: **GIVEN** a +7 sword, **WHEN** it is unequipped, then awarded to another eligible member, **THEN** storage briefly held `(sword, 7)` and the new wearer's sword is +7 with Member F2 atk = round(1000 · atk · 1.28).
- **AC-14 [Integration] (batch)**: **GIVEN** an item at +4 and fund enough for 20 attempts, **WHEN** a 20-command batch with `stop_at = 6` is submitted, and a fixture seed under which +6 is reached within the batch, **THEN** the item ends at +6, every command after the one that reached +6 is refused with 103, and refused commands cost nothing.
- **AC-15 [Balance] (S5 gate)**: **GIVEN** the balance simulator with the S5 player policy (enhance every equipped item toward +5…+8 when the fund exceeds the next attempt's cost), **WHEN** run to level 100, **THEN** the time to level 100 differs by at most 15 % from the run without enhancement, and no party wins against a boss at ≥ 1.5× its level (GDD §20 S5).
- **AC-16 [Balance] (sink)**: **GIVEN** the same run at levels 30, 60 and 100, **THEN** the guild-wide `gold_out / gold_in` stays within 60–90 % (§19.5) with the forge included.
- **AC-17 [UI]**: a retained screenshot in `production/qa/evidence/` of the forge screen showing an item at +7 with success chance, cost, drop warning, ward toggle and cap, and one of the refused state (cap reached) with its reason in words.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Scope (not decided here):** should members spend their own wallets on enhancement through Utility AI (12), as an idle-game convenience? Today only the player enhances, paid by the fund (Gold R1, OQ-5). Adding it is a scope change | Producer + user, Utility AI (12) | Before Vertical Slice stories |
| OQ-2 | **PROVISIONAL: Member state machine (41)** — states `hunting`, `boss_raid`, `away`, `dead`, `training` exist with Member model R6's meaning and are readable in P1 | Member state machine (41) | When 41 is designed |
| OQ-3 | **PROVISIONAL: Member model (8)** — exposes `set_enhance_lv(member_id, slot, lv)` (validates 0…20, re-derives profile, rescales HP) as the only writer path for `enhance_lv` | Member model (8) | Consistency pass |
| OQ-4 | **Data migration:** `enhance.csv` `success_pct` must become `success_ppm` (×10,000) per Data layer R4, and `cost_mult` is converted to milli at boot; add the validator rules (row count = `enhance_max_lv`, `success_ppm > 0` and non-increasing, `fail_effect = none` on row 1, `ward_usable` only on `drop_1` rows). Schema change, not made here | Data layer (3) | Data layer OQ-1 migration |
| OQ-5 | Does "burning a bad roll" (Edge Cases) need mitigation for ranked play, e.g. a per-item key component? | Leaderboards and anti-cheat (35) | When 35 is designed |
| OQ-6 | **Command layer vocabulary:** replace the provisional `enhance_item(item entity)` row with ID 2401 `(member entity, slot int(1,4), use_ward int(0,1), stop_at int(1,20))`, reason codes 100 `enhance_cap_reached`, 101 `enhance_forge_not_built`, 102 `enhance_ward_not_usable`, 103 `enhance_target_reached`; applier cost O(1) (two ledger/storage calls, one derive, one draw); no sim-origin requests | Command layer (5) | Consistency pass |
| OQ-7 | **PROVISIONAL: Crafting (28)** — `rec_item_enhance_ward` at `bld_enhance` level 3 is the gold source of wards; since the user decision of 2026-11-16 the Linh Bảo shop (Gold economy R16, 60 Linh Bảo) is a second source, so `items.csv`'s `craft_only=1` on the ward and §19.3's "chỉ chế tạo, không bán" need updating (data/master-GDD change, not made here). Are 20,000 gold + materials and 60 Linh Bảo the right ward prices once S5 measures ward use? | Crafting (28) | When 28 is designed |
| OQ-8 | §19.3 balance warning: +10 = +40 % must pass the S5 combat re-run (AC-15) before `stat_pct_total` is locked; also re-measure XP pacing (XP curve OQ-6) | Dev tooling and balance sim (43) | S5 |
| OQ-9 | Rebirth (23): confirm rebirth and Ascension keep equipped items and their levels (assumed: rebirth does not touch equipment) | Rebirth and Ascension (23) | When 23 is designed |
