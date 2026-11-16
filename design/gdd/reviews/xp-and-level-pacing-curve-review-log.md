# Review Log: XP and Level Pacing Curve

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: M
Specialists: none (lean mode; game-designer, systems-designer, economy-designer and qa-lead lenses applied in-session)
Blocking items: 2 | Recommended: 8
Summary: Structurally complete (8/8) and numerically sound: every AC value (AC-1 to AC-20, AC-29), the F3 stretches, the F2 bounds and the F4 hash `fcc9532f…` were reproduced independently from `data/config.csv` and `data/rebirth.csv`; no registry conflicts. Two contract holes block implementation: the load path for `level`/`xp_milli` is undefined (R9 zeroes XP yet is cited as the load-time check), and a member who reaches the cap offline never gets the logged 2202 milestone. Much of the dependency text predates the sibling GDDs and is now stale.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Core Rules R9 / Dependencies assumption 1 / AC-34: `init_progress` sets `xp_milli = 0`, yet AC-34 and provisional assumption 1 say it is called "on creation and on load", R9 says "loaded from a migrated save", and Local save line 337 cites R9 as the restore-time refusal. Called on every load it wipes XP; Edge Cases C ("member not changed on load") assumes it is not. Define a separate restore/validate rule (keep `xp_milli`, check level 1…cap and 0 ≤ xp_milli, Capped ⇒ xp_milli = 0) and state which system owns the save section for these fields (Local save R5 lists XP 22 as stateful; Member model says it stores them).
- [BLOCKING] Core Rules R4 step 5 / R6 / Edge Cases B: with `ctx = null` nothing is emitted and Offline R15 forwards only 2201, so a member who caps during an absence never gets 2202 (logged milestone, Chronicle beat, "ready to rebirth" cue). Contradicts Edge B "2202 fires each time, once per tier" and AC-32. Either let Offline also forward 2202 (when old level < cap = new level) or have `award` return a `reached_cap` flag; mirror it in Offline R15 and add an AC.
- [RECOMMENDED] Interactions / Dependencies: stale text: line 109 says Member model, Hunt, Rebirth and Offline have no GDD; Upstream rows marked "(provisional)/undesigned"; "All other systems above are undesigned"; Provisional assumptions 1–5; OQ-8 (F-1 done in Schools line 328, F-2 done in index row 22); OQ-5 answered by Local save R14. Refresh against the existing GDDs.
- [RECOMMENDED] Dependencies: Member model (8) and Rebirth (23) are hard upstream here and hard downstream too, and both list XP curve upstream; systems-index row 22 lists only Data layer, Sim core, Event bus. Record the cycle (storage-owner pattern) or demote one direction, and align row 22.
- [RECOMMENDED] Tuning Knobs `xp_rebirth_mult`: safe range "each tier 1.2–2.0× the last" is violated by today's default (1 → 3 is 3.0×). Widen the range or exempt tier 0→1.
- [RECOMMENDED] Edge Cases D / AC-30: "at most 2 events per awarded member per tick" and "awards come at the end of a hunt trip" conflict with Zones R(91) (one `award` per member per kill) and other sources (quests, boss); several awards to one member in a tick can each emit 2201. Restate the bound per award, or justify per-tick.
- [RECOMMENDED] Formulas F1: state the float evaluation order explicitly and that `L / xp_early_end` is float division (GDScript int/int truncates, which would zero the ramp below level 40); F4 catches it but the rule should be in the text.
- [RECOMMENDED] Edge Cases D: aggregate drift bound "at most 2 milli-XP per skipped call" is < 2.2 at `bonus_ppm` 200,000 (the step1 floor loss is scaled by 1.2); AC-29 only tests rebirth 0. Restate as < 1 + (1 + bonus) or add a rebirth-5 case.
- [RECOMMENDED] Edge Cases (error codes): refusal codes 2201/2202 reuse the same numbers as event types 2201 `member_level_up` / 2202 `member_level_capped`; "returns 2202" vs "emits 2202" is easy to misread in sibling GDDs (Member model AC-17). Consider a distinct error range; also state the check order when several refusals apply.
- [RECOMMENDED] Acceptance Criteria AC-35: `tools/balance_budget.csv` does not exist yet and OQ-1 says the sim does not apply `xp_pct`/`growth_bonus`; keep AC-35 Pending until Dev tooling ships the band.
Reviewed-Content-Hash: design/gdd/xp-and-level-pacing-curve.md 8b013cb956e1ab238db7f78e811a78b4e397e7fb
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/skills.md 5ccd62bd5b0d5419255d23ca2b3f4b92244c9583
Reviewed-Content-Hash: design/gdd/schools-and-school-change.md b468deba3ea43b60bb05cee1b5ae8ce989637c3c
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/gdd/ca-pa-and-traits.md 6f94b9f89498c0384ce2e725fc215b4349c0a346
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/gdd/quests-and-achievements.md e7d8bef5eb5406eb19cbbfb37a06298bf63ae89d
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
