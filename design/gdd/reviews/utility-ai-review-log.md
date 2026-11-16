# Review Log — Utility AI (design/gdd/utility-ai.md)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (3 formulas, 9 upstream + 6 downstream dependencies, parity harness against balance_sim; producer should verify before sprint planning)
Specialists: none (lean — game-designer, ai-programmer, systems-designer and qa-lead lenses applied in-session)
Blocking items: 3 | Recommended: 7
Summary: Structurally complete (8/8 sections) and the F1 parity argument holds: recomputed against data (no duplicate level_min, widest band 8, no level 1–100 gap at rebirth 0, standard-party edge 0, AC-2/AC-3/AC-11 numbers all reproduce). It fails on contracts that the downstream GDDs, written after it, no longer honour: Golden Boss temp teams do not use F3, the R9 early re-ask on a freed place has no implementer, and the F3 "buffer always wins" invariant is false at default weights.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R2/R11, Interactions, Dependencies, UI Requirements: F3 `composition_score(roster, target_element)` is said to form Golden Boss temporary teams with the boss element, but Golden Boss R7 step 2 and Party R16/OQ-4 keep the reference `form_parties()` rule for parity and Party R3 always calls F3 with `none`. `counters(t)`/`ai_counter_cover_ppm` and the "raid team suggestion" UI have no MVP caller; AC-11's `t = moc` case tests a path nothing uses. Align the contract (drop or mark PROVISIONAL) with Golden Boss and Party.
- [BLOCKING] Detailed Design R9 / Game Feel / AC-10: R9 promises the group is re-asked "at once when an event … frees a place (a trip closing)", but Member state machine R10 step 4 and its edge case only re-ask after `ai_reask_ticks`. One of the two GDDs must change; as written a programmer cannot tell whether MSM wakes idle groups on 1104.
- [BLOCKING] Formulas F3 Output Range / Edge Cases (synergy cap) / Tuning Knobs (`ai_buffer_bonus_ppm`): "a roster with a buffer beats any roster without one unless it costs more than 8 levels of excess spread" is false — a no-buffer roster with tank + 5 links + counter scores 550,000 vs 400,000 for a bare buffer roster. For Party's marginal Fill (R3) at defaults, a `t_loner` buffer adding no link (+350,000) loses to a `t_team_player` tank adding two links (+360,000); with the 200,000 synergy cap the swing is up to 400,000, so "traits cannot outweigh the buffer rule" also fails. State the real guarantee (marginal gain, with bounds on links/synergy) or re-weight, and add an AC for it.
- [RECOMMENDED] Dependencies / Interactions / OQ-1, OQ-6–OQ-8: Member state machine, Party, Offline progress and Golden Boss GDDs now exist; rows still say "Not designed — PROVISIONAL", and OQ-1 is already resolved by Member model R6 note (consistency-check 2026-11-16).
- [RECOMMENDED] Detailed Design R4: Offline progress OQ-3 asks this GDD to define `view` outside a tick (paused live trips count as occupying); R4 is written only for P2/P3.
- [RECOMMENDED] Acceptance Criteria (Performance): "under 0.05 ms on the reference desktop" — reference machine undefined, "confirm on the device spike" is not a pass/fail; and the cited "Sim core R16 budgets" is the headless-loop rule, not a budget. Name the machine and budget rule, or defer to MSM F6 `c_ai`.
- [RECOMMENDED] Acceptance Criteria AC-9: "1,000 seeded member states" — the generator, seed and state ranges are unspecified; give the fixture source (Dev tooling parity vectors).
- [RECOMMENDED] Tuning Knobs `ai_fit_below_ppm`: safe range 0–499,999 but the fallback parity with `pick_ground` (prefer nearest too-hard) needs `ai_fit_above − step×gap > ai_fit_below` for the largest gap; today there is no gap, so state that the guarantee assumes contiguous bands (content validator rule).
- [RECOMMENDED] Formulas F1: `element_same_mult = 0.95` (data/config.csv) makes same-element pairs −50,000 on both `off` and `def`; it cancels, but the text only mentions `none` = 1.0. Note the same-element case in Boundary notes.
- [RECOMMENDED] Cross-References / Dependencies: Guild market (29) lists Utility AI as a dependency in the systems index; this GDD names Market only as a PROVISIONAL catalog source — confirm the direction.
Reviewed-Content-Hash: design/gdd/utility-ai.md 9623faf37b9dba716b70349067a807abd4166ff5
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/party.md 6d61064e0aa51fe0b2623d9fa43792cd0a330c11
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
