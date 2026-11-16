# Schools and School Change — Review Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L
Specialists: none (lean — game-designer, systems-designer, economy-designer and qa-lead lenses applied in-session)
Blocking items: 5 | Recommended: 6
Summary: All 8 sections are present, the formulas are arithmetically correct, and the registry values (join level 10, keep 30%, block 2000, income_ref 1,000, token 200 LB, raid ratio 0.5) all match. The GDD was written while most neighbours were undesigned; they are now designed, and several of its contracts no longer hold against them: offline completion has no counterpart in Offline progress, the free-credit interface differs from Rebirth's, the training gate ignores the designed Member state machine, and the event-rate declaration is wrong at the max-roster fixture. Targeted revisions, not a redesign.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Edge Cases / Dependencies (Offline 31): Offline progress never mentions schools, and Sim core R5 says Offline re-anchors crossed due ticks past the skip's end, which contradicts "complete at the due tick, never late". No owner applies R5 (or F1 joins from level-ups) inside a gap; AC-25 has nothing to pend on. Agree the contract with Offline 31 and record it in both GDDs.
- [BLOCKING] R6 (Rebirth 23): R6 grants the credit from a "completed-rebirth signal"; Rebirth R3/R4 calls a synchronous `grant_free_change(member_id)` and relies on it for the same-batch case (Rebirth AC-5, OQ-6). Adopt the synchronous call in R6 and AC-12.
- [BLOCKING] R4 condition 3 / AC-8 (Member state machine 41): MSM allows `enter_training` only from `idle` and `resting`, so `hunting`, `returning` and `bounty` also refuse — the usual state of an idle-game member. Restate condition 3 as `can(enter training)`, decide refuse vs queue (and the UI for "recall first"), and fix AC-8: it names `busy` (not a code; shared 7 `not_allowed_now`) and omits `elder` and `hunting`.
- [BLOCKING] F5: `ring_per_day = 20` is declared as the peak, but Event bus R3 defines it at the max-roster fixture; `member_cap` reaches 80 (Guild and buildings AC-13), and aligned cooldowns plus free credits let every member start a change on one day. Declare a max-roster peak (≥ 80) and fix AC-15/AC-21.
- [BLOCKING] Acceptance Criteria AC-23: the criterion voids its own precondition ("at its cap … is void"). Rewrite as: GIVEN any storage contents, WHEN a change returns two items, THEN `give` succeeds and storage count = previous + 2.
- [RECOMMENDED] Open Questions: OQ-3 (Rebirth: credit persists), OQ-4 (Combat R12: neutral ×1.0) and OQ-6 (Rebirth R8: Elder's school) are answered elsewhere; close them and drop the matching provisional assumptions 5 and the OQ-4 note.
- [RECOMMENDED] Dependencies: "every other system above is undesigned" and most "Soft (provisional)" tags are stale — all listed systems now have GDDs; systems-index row 20 already lists Sim core and Event bus; the Guild and buildings row still says it supplies "the item cost and gear return" (storage is Items 26).
- [RECOMMENDED] R3: joining fires in P1 while the member is usually mid-hunt, so wrong-class armour is stripped and HP rescaled mid-trip. State it deliberately or defer the armour move to trip close.
- [RECOMMENDED] R4 accept step 1: cite Gold economy R7 (`can_debit` + Items `take`, check both then commit) so "all at once or not at all" has a mechanism.
- [RECOMMENDED] Tuning Knobs `school_join_level` row: "arrival levels (0 or 10)" is stale; Recruitment R4 uses 1 (unaffiliated) or `school_join_level` (affiliated).
- [RECOMMENDED] Cross-system: Skills Edge Cases says "Schools refuses to start a change while a rebirth is pending"; no such rule exists here and Rebirth is synchronous. Align one side.
Reviewed-Content-Hash: design/gdd/schools-and-school-change.md b468deba3ea43b60bb05cee1b5ae8ce989637c3c
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/skills.md 5ccd62bd5b0d5419255d23ca2b3f4b92244c9583
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/combat.md cf888cacc1802c9e3bf6b6b888e43e89ba7b9133
Reviewed-Content-Hash: design/gdd/xp-and-level-pacing-curve.md 8b013cb956e1ab238db7f78e811a78b4e397e7fb
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
