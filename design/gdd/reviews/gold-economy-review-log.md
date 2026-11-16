# Review Log — Gold Economy (design/gdd/gold-economy.md)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (ledger + 9 formulas, 20+ calling systems, needs a ledger ADR; producer should verify before sprint planning)
Specialists: none (lean mode; economy-designer, systems-designer, game-designer and qa-lead lenses applied in-session)
Blocking items: 3 | Recommended: 7
Summary: Structurally complete (8/8 sections), registry values all agree (tax 0.1, upkeep 700, income_ref 1,000, share 0.3, start fund 2,000, Linh Bảo prices, caps), and the ledger/conservation design is sound. Blocking defects are in the integer math: the boot conversion rule gives the bank 100× its intended rate, F5's product can overflow int64, and the MVP storage-trade commands that mint and burn fund gold have no acceptance criteria. Several cross-references are stale (dependency GDDs now exist).
Prior verdict resolved: First review
Findings:
- [BLOCKING] Formulas (line 210) / F5: the single conversion rule `round(x × 1,000,000)` is applied to `daily_interest_pct`, but `buildings.csv` stores it in percent (0.2–1.6), so it yields 200,000–1,600,000 ppm, not F5's stated 2,000–16,000. Specify `round(x × 10,000)` for `daily_interest_pct` (and keep ×10⁶ for the fraction-valued `guild_tax_pct`/`tax_rate_cap`), plus a validator range.
- [BLOCKING] F5 / F6 note (line 312): `fund × interest_ppm` uses the fund (up to `gold_balance_max` 10¹⁵), not an op amount bounded by `gold_op_max`; 10¹⁵ × 16,000 = 1.6×10¹⁹ > 2⁶³. The claim "F1/F2/F5 products stay under 2⁶³" is false for F5. Define an overflow-safe evaluation (e.g. compare against the cap first, or `(fund // 10⁶) × ppm + (fund % 10⁶) × ppm // 10⁶`) and add a boundary AC at fund = `gold_balance_max`.
- [BLOCKING] Acceptance Criteria / R15: no AC covers `sell_item` (the `storage_sale` mint, sell value from Items F5, refusal for materials and missing goods) or `buy_item` (`fund_purchase` burn, `cannot_afford`). These are MVP gold faucet/sink paths; the QA-lens note "none uncovered among R1–R16" is incorrect.
- [RECOMMENDED] Dependencies (lines 425–427): Member model, Items and loot and Guild and buildings are marked "PROVISIONAL — no GDD yet", but all three GDDs exist and OQ-8/OQ-9 were resolved against them; update hardness/status and the bidirectional-check paragraph.
- [RECOMMENDED] OQ-10 / Edge Cases (line 387): Guild and buildings is designed (tax_rate_cap is a non-decaying capacity key); confirm the no-Chợ-Bang cap = 0 from its effect query and close OQ-10.
- [RECOMMENDED] Cross-doc interface: guild-and-buildings.md (line 284) calls Gold economy `balance()`, `debit(amount, reason)`, `credit(amount, reason)` and marks it "not yet designed"; this GDD's API is `fund()`, `debit(type, account, amount, ref_uid)`. Propagate to Guild and buildings.
- [RECOMMENDED] R3 / OQ-5: Equipment enhancement R8 settles that attempts are fund-paid only (no wallet path); R3's `enhance_cost` "fund or wallet" and OQ-5 are stale — narrow to fund (wallet only if Enhancement OQ-1 is later accepted).
- [RECOMMENDED] AC-19: asserts an "interest credit" event in the order, but no event type is emitted for a fund mint (2701 is wallet-only, 2703 is spending). Either add an event or rewrite the AC against `total[bank_interest]` after the slot.
- [RECOMMENDED] F8: the 24/day `tax_rate_changed` bound uses the default cooldown; the knob's safe range goes down to 600 s (144/day). Derive the declared volume from `86,400 // tax_change_cooldown_s` or raise the safe-range floor. The 10/day `balance_clamped` bound is unjustified; state why (caps practically unreachable) or rate-limit it.
- [RECOMMENDED] Acceptance Criteria: no AC for R12 (per-hour rolling metrics window) or R13's release-build path (mismatch emits 2711 and the save still proceeds).
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/equipment-enhancement.md f34423bdf934dfc4fe6e0b7df0e00fe853e4b331
Reviewed-Content-Hash: design/gdd/schools-and-school-change.md b468deba3ea43b60bb05cee1b5ae8ce989637c3c
Reviewed-Content-Hash: design/gdd/utility-ai.md 9623faf37b9dba716b70349067a807abd4166ff5
Reviewed-Content-Hash: design/gdd/quests-and-achievements.md e7d8bef5eb5406eb19cbbfb37a06298bf63ae89d
Reviewed-Content-Hash: design/gdd/guild-market-and-trade-orders.md b970a0ecd83f5a4af112aee544058e8d987a89f5
Reviewed-Content-Hash: data/buildings.csv fff45a345d60567f9b13e04635c761e954350389
Reviewed-Content-Hash: data/items.csv 8dc7e745e5add4dbc9d8ccc2e0145fe60078d16c
Reviewed-Content-Hash: data/config.csv 89e06e312872e021af129b1c0a12268fee841170
