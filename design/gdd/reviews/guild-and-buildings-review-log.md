# Guild and Buildings — Review Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (7 formulas, 6 upstream / 13+ downstream systems, cross-system timer and save contracts; producer should verify)
Specialists: none (lean mode; game-designer, systems-designer, economy-designer, qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 8
Summary: Structurally complete (8/8) and numerically sound: F1–F5 totals (44,213,601 gold, 36,326 min, 235 buildable rows, per-kind MVP totals) and AC-2/3/8/10 values recompute exactly against data/buildings.csv, and no registry value conflicts. It is blocked because four GDDs it calls PROVISIONAL or undesigned have since been designed and define contracts this one does not meet (Command layer vocabulary, Offline settle_to/frozen time, Local save section), and because MVP scope questions leave the five-building slice unimplementable without guessing.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R2/R3, Dependencies, OQ-12: command-layer.md line 162 registers `build_building` / `upgrade_building` with arg `content(buildings)` (a level-row uid); this GDD uses `build(building_id)` (a kind) plus `cancel_build`, which Command layer does not list. Agree one command set, arg type, command IDs in block 30, owner reason codes (vs R14 `not_live`/`not_allowed_now` and the 3006 codes 1–9) and applier cost, as Command layer OQ-8 asks each owner.
- [BLOCKING] Edge Cases (offline), OQ-5, AC-15: offline-progress.md R4/R7/R9 now answers OQ-5 with a contract this GDD does not state: a `settle_to(to_tick)` hook, a declaration of which build completions are "rate-changing" (slice breaks), and re-anchoring of due ticks beyond the credited window by the frozen shift `u`. Adopt it; also resolve Offline OQ-11 (frozen time vs Player Fantasy 1 "returns to all of it built").
- [BLOCKING] Dependencies (Local save 6 listed only downstream): local-save-and-migration.md R5/R6/R14 require every stateful feature to register a section (no JSON numbers, schema/migration step). This GDD names no section id, field schema for levels and queue entries (`building_id`, `to_level`, `gold_paid`, `mats_paid`, `state`, `start_tick`, `due_tick`) or migration step; add Local save as a Hard upstream contract.
- [BLOCKING] Overview MVP scope, OQ-1/OQ-9/OQ-10: the mechanism holding back the 21 non-MVP kinds is undecided, Chợ Bang and Dược Phòng have no MVP consumer (Market 29 and Crafting 28 are VS), and Luyện Khí Đài 1 needs Tổng Đàn 3 + zone-6 materials. An MVP implementer must guess what 2 of the 5 MVP buildings do and how the list is filtered; decide before the system enters a sprint.
- [RECOMMENDED] Acceptance Criteria AC-11: "Luyện Khí Đài 6, Tổng Đàn 3" is unreachable (bld_enhance 6 has hq_lv_req 5); re-anchor on Tổng Đàn 5 (`member_cap` 28, `building_slots` 21).
- [RECOMMENDED] Formulas F5 lens and Tuning Knobs `cost_gold`: "Tổng Đàn 8 (25 M) ≈ 11.5 days of tax ... as §19.4 states" — by the GDD's own inputs (20 × 70 × 1,000 × 10% = 140,000/h) it is ≈ 7.4 days; JX1 GDD §19.4's 11.5 days refers to the full 44.2 M.
- [RECOMMENDED] Acceptance Criteria AC-16: conservation should sum recorded `gold_paid` over completed, Building and Queued entries, not `cost_gold` (content changes between order and completion, F6).
- [RECOMMENDED] Detailed Design R7: effect values include floats (`satiety_mult=1.1`, AC-3 returns 1.1) while Sim core R13 / Data layer favour integer state; state the value type `effect()` returns and who converts to ppm (Gold economy already converts its own keys).
- [RECOMMENDED] Detailed Design R5: a 0-minute entry started in P5 by a completion — does it complete in the same P5 (loop) or the next tick? State the loop rule (AC-9 relies on start-at-completion-tick).
- [RECOMMENDED] Dependencies, Bidirectional status, OQ-3/OQ-5/OQ-12, header Status: Gold economy, Items and loot, Command layer and Offline progress are designed (Gold economy F5 already caps interest, answering OQ-3); refresh the PROVISIONAL labels and the "every other system is undesigned" note.
- [RECOMMENDED] Detailed Design R8 capacity-key list: confirm whether `opponents` (Arena) and `teach_max_skill_lv` should decay; the list is closed by default so omissions silently decay.
- [RECOMMENDED] Open Questions OQ-1: "all 24 are wave 1" — 24 kinds incl. Tổng Đàn are wave 1, 2 (`bld_tower`, `bld_arena`) are wave 2; the 21 held back already include the 2 wave-2 kinds.
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/data-layer-and-content-pipeline.md c3f4acefb5084f8b639f485e3d9714219f496da8
Reviewed-Content-Hash: data/buildings.csv fff45a345d60567f9b13e04635c761e954350389
Reviewed-Content-Hash: data/building_meta.csv 7497cc3812a1349e281a751e6c349e1079bd120a
Reviewed-Content-Hash: data/config.csv 89e06e312872e021af129b1c0a12268fee841170
Reviewed-Content-Hash: JX1_Tycoon_GDD.md ac0a914e274b82095a96f8f66fd43757a52a9566
