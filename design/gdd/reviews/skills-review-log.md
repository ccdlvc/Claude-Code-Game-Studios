# Skills — Review Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (10 formulas, 9 upstream / 9 downstream systems, new `skill_expr` type and vocabulary file likely need an ADR; producer should verify)
Specialists: none (lean mode; game-designer, systems-designer, qa-lead lenses applied in-session)
Blocking items: 3 | Recommended: 9
Summary: Structurally complete (8/8) and the numbers hold: F1–F9 examples and ACs recompute correctly against data/skills.csv and the XP curve table, the R2 vocabulary matches the 115 effect keys in the data exactly, and no registry value conflicts. It is blocked by one underspecified core algorithm (the R6 pool remainder, which parity depends on) and by two contracts with GDDs that have since been designed (Member model storage, Combat operators/kinds) that still disagree with this one.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R6 steps 4-5: pool is "poured into" skill_xp_milli, yet step 5 moves "pool left" on; undefined whether the carried remainder is the excess over the last level's need, the skill's whole progress, or whether progress resets — AC-12 cannot be given exact values and the Python/GDScript ports may diverge. State the remainder and the gated skill's residual progress exactly.
- [BLOCKING] Detailed Design R4 / OQ-8: member-model.md (Designed) stores `skills[] {skill_id, lv, xp}` and has no `skill_bank_milli` or `skill_focus_slot`; this GDD assumes per-slot arrays plus bank and focus. Reconcile (and update Member model) — OQ-8 can no longer be "provisional, when designed".
- [BLOCKING] Detailed Design R2 / OQ-4: combat.md (Designed) says Combat owns "one operator per effect key", groups `crit_rate`, `crit_dmg`, `def_ignore`, `element_dmg` as direct damage and `hp_pct` as healing, and still lists Skills as "Not designed — PROVISIONAL"; this GDD says one handler per kind and classes those keys as `modifier`, with "a key may not change kind". Agree one dispatch model and one kind per key in both docs.
- [RECOMMENDED] Detailed Design R2 (line 98) and Core Rules lens (line 57): "130 keys" — data and vocabulary both hold 115 distinct keys.
- [RECOMMENDED] Edge Cases (line 384): `taunt_s`+`aggro` called `shape` keys; R2 classes them `control`.
- [RECOMMENDED] Formulas F1 output range: min example is `dmg_taken_party=-0.4` (sk_kim1_09), not `dmg_taken`.
- [RECOMMENDED] Formulas F10: cites Offline (31) OQ-4, which is about Party; offline-progress.md never mentions Skills although listed as a Hard downstream — add the link and the event-flood handling there.
- [RECOMMENDED] Formulas F4: `skill_xp_mult` (trait t_dull, Rebirth elder buff thuy_1) has no consumer; CA/PA OQ-2 names Skills as co-owner. Decide whether F4 applies it.
- [RECOMMENDED] Detailed Design R10: CA/PA expects an `event:skill_learn` trait-reveal hook with member_id; say which event (2101 0→1 or 2102) serves it. Also 2101 `skill_level_up` fires on set_levels decreases (AC-25) — name/direction field.
- [RECOMMENDED] Acceptance Criteria AC-4/6/8/15/18/21: anchored on kim_1/kim_2 (Wave 2) while MVP ships only tho_1/moc_1/hoa_2; under shipped MVP data kim_1 is not live, so AC-15 training would never run. State the wave/liveness fixture or re-anchor on slice schools.
- [RECOMMENDED] States and Transitions: no Learned→Mastered row; Locked vs level-0-but-gated overlap unclear.
- [RECOMMENDED] Dependencies bidirectional note (line 419): says Combat, CA/PA, Rebirth are undesigned — they are designed; Rebirth (R4 step 4, AC-2) and CA/PA (F9) already conform; refresh the note and header status.
Reviewed-Content-Hash: design/gdd/skills.md 5ccd62bd5b0d5419255d23ca2b3f4b92244c9583
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/combat.md cf888cacc1802c9e3bf6b6b888e43e89ba7b9133
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/ca-pa-and-traits.md 6f94b9f89498c0384ce2e725fc215b4349c0a346
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/gdd/xp-and-level-pacing-curve.md 8b013cb956e1ab238db7f78e811a78b4e397e7fb
Reviewed-Content-Hash: design/gdd/schools-and-school-change.md b468deba3ea43b60bb05cee1b5ae8ce989637c3c
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
