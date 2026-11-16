# Review Log — Items and Loot Tables

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning) — 7 formulas, ~10 hard dependencies, storage/bag serializers, parity vectors
Specialists: none (lean mode; game-designer, systems-designer, economy-designer, qa-lead lenses applied in-session by an independent reviewer)
Blocking items: 3 | Recommended: 7
Summary: Complete (8/8 sections), integer-exact and data-checked: F1/F2/F5 examples, AC-5/AC-18/AC-19b values and registry entries (base_gold_milli, gold_drop, loot_luck_milli, sell_value, items_event_type_block) all agree with data/*.csv and design/registry/entities.yaml. Three contract defects block implementation: the domain-2 hunt loot key differs between this GDD, its own AC-3 and Zones F9 (and Zones' form collides with Endless Tower keys); event 2606 is defined but not registered by the ACs/dependency tables; and the `drop_rate` effect key that traits, Elders and CA/PA route to this system has no consumer. Several cross-references are stale against sibling GDDs that were already reconciled.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R3 / Acceptance Criteria AC-3: hunt loot key is `[anchor_member_id, trip_ordinal, encounter_ordinal]` (no tag, first component ≥ 1) in R3, but Zones F9 (line 395) says domain 2 uses `[0, party_id, trip_ordinal, encounter_ordinal]` "(Items R3)", and AC-3 tests `[0, 7, 3, 12]` for a hunt and `[1, 3]` for a raid (R3 says raid is `[0, 1, raid_ordinal]`). Under Zones' form, party_id 2 gives `[0, 2, trip, enc]`, the same shape as Endless Tower's `[0, 2, run_ordinal, floor]` — a real key collision (RNG R6). Pick one layout, fix Zones F9 and AC-3 to it.
- [BLOCKING] R10 / Interactions / Dependencies / AC-29: R10 defines 2606 `rare_haul` (consumed by CA/PA `event:rare_drop`), but the Interactions table, upstream Event bus row, downstream Quests row and AC-29 all say 2601–2605, so the registration AC would pass without 2606; CA/PA OQ-12 still lists the rare-drop event as open. Make every list 2601–2606 and test 2606's flags.
- [BLOCKING] Formulas F3 / R4: `trait_mod_ppm(m, rare_drop)` is the only trait input, but traits.csv carries `drop_rate` on t_lucky/t_unlucky/t_fortune_child, Rebirth's Elder buffs include `drop_rate` (tho_2 40,000) and `rare_drop`, and CA/PA line 151 says Items reads `trait_mod_ppm(drop_rate / rare_drop)`. Define what `drop_rate` scales (all rows? item/material rows? gold?) or declare it unused and tell the owners; also state how Elder buffs enter F3.
- [RECOMMENDED] F3/F4: `member_luck_milli` has no upper clamp, while F4's 0–2,000 range and int64 bound assume one; add `min(luck_max_milli, …)` as a knob.
- [RECOMMENDED] Cross-References / OQ-2 / OQ-3: stale — Schools R282 already treats storage as uncapped and Items-owned; Gold economy R15 already refuses materials (OQ-15 closed); Member state machine line 239 allows equip in `returning` (settlement), so OQ-2's settlement question is answered. Update or close.
- [RECOMMENDED] R7 vs Interactions / Edge Cases C: storage API is `count/give/take` in R7 but `put` in the Interactions table and "`put` fails loudly" in Edge Cases; one name.
- [RECOMMENDED] R10 `epic_loot.c` "source tag (R3)": hunt keys carry no tag under R3; define the hunt value (e.g. 0) and test it alongside AC-27's `c = 1`.
- [RECOMMENDED] R10 peak emission "up to 10 + epic units": unexplained; with 5 members × 4 slots auto-equips plus 5 `rare_haul` it can exceed 10. State the bound from its terms.
- [RECOMMENDED] Overview: "316 rows of drop_tables.csv" — the file has 315 data rows plus header.
- [RECOMMENDED] Header Status still "In Design" while systems-index said Designed; align after revision.

Registry check: searched base_gold, gold_drop, luck, sell_value/sell_ratio, bag_slots, pa_max, 2600–2606, rng_domain_loot; no value conflicts with the registry. Conflicts found were with sibling GDDs (above). No game concept, brief or narrative docs exist: lore/pillar alignment not assessed.

Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/schools-and-school-change.md b468deba3ea43b60bb05cee1b5ae8ce989637c3c
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/gdd/ca-pa-and-traits.md 6f94b9f89498c0384ce2e725fc215b4349c0a346
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/endless-tower.md e962f7799a12b16baeae8120add5c5c0a27d961b
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
