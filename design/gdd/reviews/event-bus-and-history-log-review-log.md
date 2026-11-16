# Review Log — Event Bus and History Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: full · Workflow: full
Scope signal: XL
Specialists: game-designer, systems-designer, qa-lead, godot-specialist, performance-analyst, creative-director
Blocking items: 8 | Recommended: 9
Summary: Structure is sound (8/8 sections, examples recompute, fail codes comply), but retention guarantees break under idle-play pressure (ring flush, 2.8 h span, milestone fallback evicting day-one recruits, uncapped subject 0), engine semantics are wrong (packed arrays are by reference), and the F1/AC-20 budget gate is circular. Fixable cluster; system identity unchanged.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Player Fantasy / R7 / F4: 8 h Chronicle-agrees-with-roster promise unenforced; roster-changing events evictable; OQ-6 ring flush is a design flaw
- [BLOCKING] R7 / F5: milestone fallback evicts protected first-3 above 1,333 subjects; subject 0 uncapped; per-subject fallback dead code; combined eviction order undefined
- [BLOCKING] F1 / F3 / registry: history_bytes_max range should be 11,200–8,000,000; r_logged_max 0.00116–1.157; "7.8 MB" is 8.0 MB; E_budget can go negative
- [BLOCKING] F1 / AC-20: 833 µs budget unit incoherent vs Sim core F6 and catch-up; AC-20 circular
- [BLOCKING] R5 / R8 / R11: packed arrays are by reference (needs duplicate); JSON snapshot unsafe; subscriber strong refs; R4 arity check cases
- [BLOCKING] R7: ring and milestone-tier data structures and commit complexity unspecified
- [BLOCKING] Acceptance Criteria: AC-14 seam, AC-17 refusal/return shape, AC-16 fixture, PENDING splits, AC-22 length, coverage gaps (R3, R4, R6, R8, states, R12, group D)
- [BLOCKING] Player Fantasy 3: "same name after rename" needs Member model tombstones and an AC
- [RECOMMENDED] R11: core_tick wording; restore trim vs protection; counters validated or rebuilt
- [RECOMMENDED] R3 / F2: name charset and length check at seal; last ID block overflow; central ID allocation table
- [RECOMMENDED] R4: restate the 16-subscriber cap in the rule
- [RECOMMENDED] F4 / F1 / F3: r_logged = 0 gives infinity; c_commit not constant; 8.16 MB transient at hard-cap max
- [RECOMMENDED] R8: same-tick cross-tier ordering; bound read_history
- [RECOMMENDED] R5: check the failed flag after every handler call
- [RECOMMENDED] Detailed Design: absence or wall-clock marker record
- [RECOMMENDED] Acceptance Criteria: AC-24/29/15/28 wording; unbundle; story-type tags
- [RECOMMENDED] Dependencies: Data layer and Dev tooling reciprocation
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md d65914f44e6e788c937deae892ea55bd066851f9
Reviewed-Content-Hash: design/registry/entities.yaml ca120c844017e4ef6aa22fbda590f77b8e75ff44
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md dc48b7f66f1f15c99bf9606dd770972eebc3a4fa
Reviewed-Content-Hash: design/gdd/data-layer-and-content-pipeline.md 1ed2be6c9dfe31e8fd4eb98237636053570cddd1
Reviewed-Content-Hash: design/gdd/dev-tooling-and-parity-harness.md c200df0720461b76ce29a2080e24572b30c3bd76
