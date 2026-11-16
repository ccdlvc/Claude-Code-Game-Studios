# Review Log — Guild Market and Trade Orders

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L
Specialists: none (lean mode; lenses applied in-session by an independent reviewer)
Blocking items: 4 | Recommended: 7
Summary: The structure is complete (8/8 sections), and every worked number checks out against data and the registry: F1–F4 examples, AC-4, AC-13 and AC-18 to AC-20. The problems are its contracts with the GDDs it depends on. Utility AI is now designed, and its purchase model (`choose_gear` called by MSM at trip close, commons only, caller submits `shop_sale` directly, closed consideration list) leaves no producer for R5's intent queue, no buyer for stock listings and no consumer for R8's order steering. Catalogue gating (9 stalls at L1 against 15 equipment families, a Chợ Bang that starts at level 0, `market_live` false in MVP, and a cap of 6 buys a day) contradicts the "every common always buyable" assumption that the calibrated pacing rests on. R7 delivery depends on a ledger type and a hand-in hook that do not exist upstream.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Rules R5/R8, Dependencies: contradicts designed Utility AI. UA R2/R10 has MSM call `choose_gear` at trip close; the caller submits `shop_sale` + `equip` directly, commons only; UA R12 has a closed list of considerations with no trade-order term. As a result, nothing queues `buy(member, stall, content_id)` intents, no one ever buys stock listings (the headline "Lan bought the epic blade" fantasy), and orders steer nothing. The GDD still says UA is "Not designed — PROVISIONAL (OQ-3)".
- [BLOCKING] R1/R2/R5.5/R10: catalogue gating vs calibrated gear pacing. Data has 15 equipment families (10 weapon, 3 armour, ring, amulet) but `market_slots` = 9 at L1. `bld_market` starts at level 0 (Buildings R1). With `market_live` false in MVP, `offers_for` is empty, yet Gold R7 prices MVP "Chợ Bang gear" sales and UA R10 / Member model AC-21 assume every common is always buyable. The `market_buys_per_member_day` cap of 6 sits against UA's up to 4 purchases per trip close. The GDD never says where members buy gear when the market is absent or under-stocked. OQ-4 cannot stay a producer question because it decides MVP pacing.
- [BLOCKING] R7, OQ-1/OQ-2: delivery cannot be implemented. `order_bounty` is absent from Gold R3's closed entry-type table (GDD admits "R7 step 3 cannot be implemented"), and Items R6/R12 never call `market.deliver`. Upstream acceptance is needed before this can be approved.
- [BLOCKING] F2/R2, OQ-8: registry `member_price` says it is "passed as shop_sale price_total", but Gold R7 defines the price as `items.csv` price × quantity. The trait-adjusted catalogue price contradicts the owning GDD, and UA F2 also decides affordability on the catalog price.
- [RECOMMENDED] F1, Tuning Knobs, AC-15, UI: grace off-by-one. `days_over = elapsed_days − grace` keeps full price for grace+1 whole days (the F1 example shows day 0–1 at grace 1), while the knob says "days at full price" and AC-15 says "stays there for listing_grace_days". Define the semantics and fix AC-15 to exact ticks.
- [RECOMMENDED] Edge Cases C, OQ-5, AC-24: stale. Items R12 now hands in whole sampled bags offline (Items OQ-6 answered), so the "offline nights fill no orders" conflict and AC-24's "once Items OQ-6 is resolved" are obsolete.
- [RECOMMENDED] Dependencies: stale status. Utility AI, Golden Boss, Guild screens and Quests are all designed now. Golden Boss still lists Market as "Not designed", Quests says Market does not name it as a consumer, and Items does not mention `deliver`. A consistency pass is needed.
- [RECOMMENDED] R12/R5.5: `buy_window_start_tick` / `buys_in_window` are written "on the member record" (Member model owns member fields). Keep them in Market's own save block keyed by `member_id`. R5.5 "last-purchase window" also conflicts with the edge text "one game day after its first purchase".
- [RECOMMENDED] Acceptance Criteria: missing ACs for the R12 save round-trip, the `market_slots`-lowered-at-load edge, consumable-to-inventory purchase, `set_markup` clock restart, and `bad_stall` / `bad_family` refusals.
- [RECOMMENDED] F3 example: "at the default the player posts 184/unit", but no default bounty is defined (knob or UI slider start).
- [RECOMMENDED] Player Fantasy framing 1: depends on a buyer for rare/epic stock, which UA's commons-only `choose_gear` never provides. Resolve together with blocking item 1.
- [NICE] F1 Output Range: the overflow sentence is garbled ("5×10⁵ × 2×10⁵ × … ≤ 10¹²"). State it as `price × markup_ppm ≤ 2×10⁵ × 5×10⁶ = 10¹²`.
- [NICE] Edge A: "taken by a school change" is wrong, since school change puts gear into storage. Also, R3's "member-held specials with price > 0" is an empty set today.
Registry values: searched item/material prices, market_slots, order_slots, shop_fund_share_pct, equip/mat_sell_ratio, t_haggler, tick_rate, party_max, gold_op_max and market_buys_per_member_day. All match except the member_price/Gold R7 conflict above.
Reviewed-Content-Hash: design/gdd/guild-market-and-trade-orders.md b970a0ecd83f5a4af112aee544058e8d987a89f5
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/utility-ai.md 9623faf37b9dba716b70349067a807abd4166ff5
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/quests-and-achievements.md e7d8bef5eb5406eb19cbbfb37a06298bf63ae89d
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: data/items.csv 8dc7e745e5add4dbc9d8ccc2e0145fe60078d16c
Reviewed-Content-Hash: data/buildings.csv fff45a345d60567f9b13e04635c761e954350389
Reviewed-Content-Hash: data/materials.csv 8aa9e8e46e141fc0cdcb8478cbc27e3793727b90
Reviewed-Content-Hash: data/traits.csv c23100b15a2f93ba4448dfb4a3961c23820d4f87
