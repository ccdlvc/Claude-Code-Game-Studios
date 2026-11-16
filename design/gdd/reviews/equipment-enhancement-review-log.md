# Review Log — Equipment Enhancement

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: M (producer should verify before sprint planning)
Specialists: none (lean mode; game-designer, systems-designer, economy-designer and qa-lead lenses applied in-session)
Blocking items: 3 | Recommended: 7
Summary: A tight, implementable design: integer F1 costs, one draw per attempt with a well-argued key, and F3's expected-cost table reproduces exactly from `data/enhance.csv` (recomputed: 19,594 / 98,771 / 428,094 / 3,792,042 / 58,342,042). Three things block: AC-9 asserts an outcome the Buildings cap forbids, and two sibling GDDs this one marks "PROVISIONAL, not designed" (Member state machine 41, Crafting 28) now exist and contradict it on the blocked-state set and on where wards come from.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Acceptance Criteria AC-9: "after arrears reset an attempt to +13 is accepted" is false. Luyện Khí Đài 6 has `max_enhance_lv` 12 (Buildings F4 example, AC-11), so +12 → +13 is refused with 100 with or without arrears. Use a level-7 forge (cap 14), or reset arrears and attempt a target ≤ 12 from a lower item.
- [BLOCKING] Detailed Design R3.3 / Dependencies / OQ-2: the blocked set `hunting, boss_raid, away, dead, training` was copied from Member model R6.6 (provisional). The designed Member state machine (41) also has active states `returning` and `bounty`, which R3.3 lets through, contradicting "the gear has to be at the forge". State the set against 41 (e.g. block all of 41's active states plus `dead`/`away`; decide `injured`/`resting`/`elder`), drop "PROVISIONAL, not designed" for 41, and close OQ-2.
- [BLOCKING] Overview / Interactions / OQ-7 vs crafting-and-recipes.md: Crafting (28) is designed, and its R9 and Player Fantasy 3 say the ward has "no drop, no shop, no Linh Bảo" source; this GDD and Gold economy R16 (user decision 2026-11-16, registry `lb_price_enhance_ward` 60) sell it for Linh Bảo. Two designed GDDs give contradictory ward sources; record the user decision in Crafting R9 (or reverse it here and in Gold R16), and drop "PROVISIONAL, not designed" for Crafting.
- [RECOMMENDED] Summary: "from +6 a failure drops the item one level" reads as "at +6 or above"; the rule is "attempts to +6 and above" (row 6 `drop_1`, so a failed +5 → +6 drops to +4, as the States table says). Reword to match §19.3's intent explicitly.
- [RECOMMENDED] R2 / Edge Cases (slot replaced before apply): the command carries no item identity, so a swap between tap and apply spends gold on an item the player did not choose. Add an `expected_item` content arg (args fit the 6-int envelope) and refuse on mismatch instead of accepting the surprise.
- [RECOMMENDED] AC-11: "10,000 random-seeded attempts" conflicts with the determinism standard; name a fixed seed list. AC-7 omits fund, item tier and cap fixtures needed to run it.
- [RECOMMENDED] Open Questions OQ-5: Leaderboards (35) is designed and accepted the "burn a bad roll" property with no ranked mitigation; close OQ-5.
- [RECOMMENDED] Open Questions OQ-9: Rebirth (23) is designed and keeps all equipment on rebirth (R3, "Kept"); Ascension moves the Elder's gear to storage via `unequip` (levels travel). Close OQ-9 and cite it.
- [RECOMMENDED] Dependencies / OQ-6: Command layer's vocabulary row still reads `enhance_item(item entity)`; the consistency pass must land the four-arg signature and reason codes 100–103 before stories.
- [RECOMMENDED] Dependencies: Local save OQ-4 asks this system whether a dispatched attempt forces a save; R6 answers "dispatch is the commit, no pre-commit" for RNG but not the save question. Answer it in R6 (and add Quests (25) achievement use of 2403 to the depended-on rationale, Quests OQ-14).
Reviewed-Content-Hash: design/gdd/equipment-enhancement.md f34423bdf934dfc4fe6e0b7df0e00fe853e4b331
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/crafting-and-recipes.md ae31dfda676080b5aaba9627f9ca6d08c0bc3474
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/gdd/leaderboards-and-anti-cheat.md 36124b2475f1e23092510a18f6f1bb4d92a0ae06
Reviewed-Content-Hash: data/enhance.csv 1caa1ea8b4895ec769d084e82d5efac6f517dbe4
