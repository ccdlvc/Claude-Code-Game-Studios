# Deterministic RNG — Review Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: full · Workflow: full
Scope signal: L
Specialists: game-designer, systems-designer, qa-lead, lead-programmer, creative-director (senior)
Blocking items: 10 | Recommended: 10
Summary: Algorithms and golden vectors are correct and the anti-rigging / anti-save-scum stance is sound. The spec is imprecise where Python and GDScript diverge (integer width, float parsing, stripped asserts), lacks an API and error contract, and has ACs that would fail a correct implementation (AC-14) or pass a broken one (AC-20). Targeted revisions reach APPROVED without redesign.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Acceptance Criteria: AC-14 measures extra draws/call (correct impl = 33.2%) against a 24–26% window; F4 "extra draws below n/2³²" wording wrong
- [BLOCKING] Formulas F4: "a+n−1 representable" is vacuous; real hazard is n=b−a+1 wrapping in int64
- [BLOCKING] Core Rules R5 / F2: key components outside uint64 undefined (Python vs GDScript diverge)
- [BLOCKING] Formulas F6: chance rounds up, not to nearest; CSV float parse is a parity risk; NaN vs R9 ambiguity
- [BLOCKING] Formulas: GDScript rules (constants >2⁶³, masked lsr64 helper, world_seed as hex string) not normative
- [BLOCKING] Detailed Design: no API contract (signatures, injected factory, error type, discarded-generator detection, release-build failure path)
- [BLOCKING] Edge Cases / Tuning Knobs: unique-key assertion scope contradicts reload (R11, AC-19/20) and fires in AC-05..17; unbounded memory
- [BLOCKING] Core Rules R5: content-ID→integer table has no owner/format; F5 should key on stable IDs
- [BLOCKING] Acceptance Criteria: AC-13/17 tolerances <2.5σ and unseeded; AC-20 can pass by chance; AC-18–22 not tagged pending; AC-23 wall-clock ratio
- [BLOCKING] Edge Cases: save-scum key rule covers only explicit gambles; combat/loot/spawn keys vs player-mutable state unspecified
- [RECOMMENDED] Formulas F1/F2: seq<2⁶³ assert; F2 not cryptographic; R12 is consistency, not anti-cheat
- [RECOMMENDED] Edge Cases: fallback seed needs injected entropy_fn; mark fallback seeds leaderboard-ineligible
- [RECOMMENDED] Core Rules R11: mid-event snapshot rule (fights atomic today)
- [RECOMMENDED] Open Questions OQ-1: SIM_VERSION location; migrate all call sites at once; re-baseline seeded tests
- [RECOMMENDED] Acceptance Criteria: measure GDScript derive cost vs 1 s offline cap
- [RECOMMENDED] Detailed Design: threading note
- [RECOMMENDED] Acceptance Criteria: AC-03 allow-list; injected-draw rejection test
- [RECOMMENDED] Acceptance Criteria: coverage gaps (discarded generator, missing seed, ±inf, key range, F2/F4/F5/F6 boundary vectors)
- [RECOMMENDED] Player Fantasy / Dependencies: Offline (31) states expectation-not-variance guarantee
- [RECOMMENDED] Core Rules R10: visible pity allowed only as documented input change
Reviewed-Content-Hash: design/gdd/deterministic-rng.md eeb3c545cc83579778c61fb87ca00deb7e80c244
Reviewed-Content-Hash: design/registry/entities.yaml 870b3a374b6812a771685615b7c9d96fdf12c6b3
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f

## Review — 2026-11-16 (re-review) — Verdict: NEEDS REVISION
Review mode: full · Workflow: full
Scope signal: L
Specialists: game-designer, systems-designer, qa-lead, lead-programmer, creative-director (senior)
Blocking items: 9 | Recommended: 8
Summary: Seed/mixing core is sound and every golden vector was independently recomputed and matches; most prior blockers closed. Remaining: a real signed-64 hole in the F4 range check, no test seams (injected draws, draw counter, event_seed accessor), undefined GDScript fatal path and new_world_seed contract, port-typing contradictions, self-contradictory unique-key tracking, and ACs that can pass vacuously. Local fixes, not a redesign. The uid/ordering conflict was withdrawn: Data layer GDD adopted uid order (R4/R6) mid-review.
Prior verdict resolved: Partly (8 of 10 closed; F4 wrap and release error path half-closed)
Findings:
- [BLOCKING] Formulas F4: d=b−a wraps to −1 for (−2⁶³, 2⁶³−1), passes check, n=0 → mod by zero
- [BLOCKING] API Contract: no test seam for injected raw draws, draws_consumed counter, event_seed accessor
- [BLOCKING] API Contract: GDScript fatal-error path undefined; needs injected fatal sink and post-sink return
- [BLOCKING] API Contract / AC-10: new_world_seed types, clock unit, failure signal, install_id_hash undefined; signature mismatch
- [BLOCKING] Core Rules R5 / F2 example: key [−1] contradiction; per-port typing; Python-only AC cases; parity on error cases
- [BLOCKING] API Contract: unique-key tracking stores seeds but claims full-key compare; no memory cap
- [BLOCKING] Acceptance Criteria: AC-18/20 no negative control; AC-03 lint can pass vacuously; AC-09 default arg nonexistent
- [BLOCKING] Acceptance Criteria AC-23: exact n+3 mix calls fails correct caching; circular pending bullet
- [BLOCKING] Edge Cases (save-scumming): fixed-dice probing mislabelled "a real decision"; state as accepted property
- [RECOMMENDED] Core Rules R2: verifier must not trust client world_seed for ranked play (policy in OQ-2)
- [RECOMMENDED] Summary/F5/F6: overclaims (same outcomes offline, F5 locality, draw counts ignore rejection)
- [RECOMMENDED] Formulas F6: chance_ppm floor vs chance ceil asymmetry
- [RECOMMENDED] Formulas: rotr32 at r=0, GDScript float literal, integer-division operators, non-int/bool args
- [RECOMMENDED] API Contract: close() optional/idempotent; reset_key_tracking on load defeats its motivating case
- [RECOMMENDED] Acceptance Criteria: golden values AC-02/06/12, exact counts, AC-08 boundaries, R4/R8/R2 ACs, error marker in vectors
- [RECOMMENDED] Formulas port rules: JS BigInt rules, seed hex helpers, offline budget gating
- [RECOMMENDED] Open Questions OQ-1: hunt.py:91 randint(b<a), float tank_aggro_share, drop_tables float chance
Reviewed-Content-Hash: design/gdd/deterministic-rng.md 46005409040025c097cdacf9a91872df2b286b04
Reviewed-Content-Hash: design/registry/entities.yaml 8ff1450412d673da0257319b02e5dec8b1a3cb97
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/data-layer-and-content-pipeline.md 1ed2be6c9dfe31e8fd4eb98237636053570cddd1
