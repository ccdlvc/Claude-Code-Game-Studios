# Review Log — Recruitment (design/gdd/recruitment.md)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: M (single feature system, 8 formulas but simple, 11 hard/soft deps, no new ADR beyond board storage; producer should verify)
Specialists: none (lean mode; game-designer, systems-designer and qa-lead lenses applied in-session)
Blocking items: 3 | Recommended: 8
Summary: Complete (8/8 sections) and unusually precise; F1–F8 arithmetic checks out (walk-in mean 79.76, best-of-3 odds 65.7/22.1/4.4%, invitation 73.3/21.7/5.0%, F2 examples 1,795 and 281,474,976,710,913, fee 200–970) and all registry values match. Three defects block: the founding rule turns reject-all into an unbounded free reroll (and Retention's dismiss_member re-enters it at will), the offline hook contradicts the now-designed Offline progress GDD, and two upstream contracts the MVP card and hire depend on (pa_key in create_member, CA of a candidate spec) do not exist in their owners' GDDs.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R11 / Edge Cases ("rejecting all gives the next offer at once ... deliberate"): during the founding phase every close, including all_rejected, opens the next offer at N+1, so "pass on all" is a one-tap reroll at up to one offer per tick; ~23 taps per PA≥170 candidate (4.4%/offer), ~5 per PA≥140 (22.1%), so a player can found with five 4–5-star members in minutes, against Player Fantasy "the dice cannot be re-rolled", F4 "rare at the top" and the §4.3 PA-100 pacing. In VS, Retention `dismiss_member` (1603) drops the roster below 5 and re-enters the phase at will. Also ambiguous whether "fewer than 5" is read before or after the accept that closes the offer (roster 4 → 5). Fix: fast-path only on `accepted`, or a saved one-shot `founding_done` flag, or a cap on founding offers; state the boundary and add ACs.
- [BLOCKING] Edge Cases (offline) / Interactions / AC-23 / OQ-8: Recruitment invents `settle_gap(from_tick, to_tick)` "called once before skip_ticks", but Offline progress R8 (now designed) requires each timer owner to register at boot as Paused or Elapsing and fires crossed due ticks through `settle_to(to_tick)` at the end of the containing slice; Offline progress never mentions Recruitment. Declare the walk-in grid as Elapsing, use `settle_to`, define which slice's roster feeds the buffer lean and what `opened_tick` is, and get Offline to list Recruitment.
- [BLOCKING] R7 / R8 / AC-16 / AC-21 / OQ-1 / OQ-2: Member model R8's `create_member(spec)` has no `pa_key` (CA/PA `init_potential(member_id, pa_key, …)` needs it), and CA/PA's `candidate_view` returns `{exact, lo, hi, half_stars, surface_trait}` with no CA and no other CA-of-candidate-spec function exists, yet the MVP card shows CA. Both contracts must be added to their owners (or R7 changed) before implementation.
- [RECOMMENDED] Dependencies: table is stale; Offline progress (31), Retention (16), Jianghu (17), Onboarding (44) and Entitlement (32) GDDs now exist. Onboarding answers OQ-5 (keep R11, no scripted party); Jianghu answers OQ-6 (own command, not a kind-2 offer; lists only the highest-PA unhired candidate); Retention OQ-8 awaits the hire salary; Entitlement PROVISIONAL-5 asks R7/R17 to read `feature_on(exact_pa_view)` instead of `exact_pa_all`.
- [RECOMMENDED] F1 rationale: "q_d_recruit ... this cadence always allows" is false in MVP once the roster reaches `member_cap` (12), since `dismiss_member` is VS-only; the daily quest becomes uncompletable. Coordinate with Quests (gate the quest on roster < cap) or soften the claim.
- [RECOMMENDED] F7 / R8 / R15: define when `half_stars_shown` is evaluated for the fee and for events 1501/1502 (accept-time `candidate_view` with the current Scout level and entitlement snapshot), and the rounding of `cost_scale` (floor ppm). A Scout House upgrade or Thiên Nhãn purchase between viewing and tapping changes the fee.
- [RECOMMENDED] Edge Cases (reload): "re-derived from the same key if ever regenerated" contradicts R12 "it never regenerates candidates"; drop the clause.
- [RECOMMENDED] F2 Output Range: "about 5.6 × 10¹⁴" ignores reserved kind 2 (max ≈ 8.4 × 10¹⁴); still within `pa_key` range, but state the true bound.
- [RECOMMENDED] AC-3 / R11: AC-3 assumes the grid anchored at 0, but the founding phase re-anchors the grid from N+1; give AC-3 its anchor explicitly and add an AC for the grid after the founding phase ends.
- [RECOMMENDED] Tuning Knobs: `recruit_offer_size` safe range 2–4 vs F5 variable range 1–5; reconcile or explain.
- [RECOMMENDED] AC-30: "min-spec Android device" should cite where min-spec is defined (project.yaml / performance budget).
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/ca-pa-and-traits.md 6f94b9f89498c0384ce2e725fc215b4349c0a346
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/onboarding-and-tutorial.md 2c478f90a0439cfd555335eb95dce08afe2f20ae
Reviewed-Content-Hash: design/gdd/jianghu-free-agents-and-npc-guilds.md 9092a7b46bed56bec3486a6bdc7e3fc5c5323fa3
Reviewed-Content-Hash: design/gdd/retention-leaving-and-negotiation.md 91d46c4b4dbdcd99a429121e589d1a9330d2da8c
Reviewed-Content-Hash: design/gdd/quests-and-achievements.md e7d8bef5eb5406eb19cbbfb37a06298bf63ae89d
Reviewed-Content-Hash: design/gdd/entitlement-and-feature-flags.md e988772d3723b158efa58a36578ef586a578bf44
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
