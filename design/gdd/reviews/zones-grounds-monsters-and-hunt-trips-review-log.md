# Review Log — Zones, Grounds, Monsters and Hunt Trips

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: XL (12 formulas, 15+ interfaces, simulation LOD likely needs an ADR; producer should verify before sprint planning)
Specialists: none (lean — game-designer, systems-designer, qa-lead lenses applied in-session)
Blocking items: 3 | Recommended: 7
Summary: All 8 sections present and the arithmetic checks out (F1, F2, F7, F11, F12 examples and AC-16/17 values re-computed; registry values for kill_base_milli, party_xp_mult_ppm, party_max, event block 1100, P3 order 1100 all match). The blockers are all in the new simulation LOD (R17) and its interaction with recall: a card can carry a recall/order-home end reason into a replay, the free-detail-slot rule does not say whether it mutates D between snapshots, and the "player cannot trigger recall" claim is now false because Golden Boss R13's summon horn recalls exactly as R5.
Prior verdict resolved: First review
Findings:
- [BLOCKING] R17.1 Simulation LOD: a card built from a chain that ended on code 4 `recalled` or 5 `ordered_home` (or was cut short by them) replays that ending — "if the card runs out ... the chain ends with the card's end reason" — so a replay can fabricate a recall (immediate settlement, hand-off to a raid that does not exist) or an order home. State that chains ending 4/5 never become a valid card (or the replay ends on the card's last natural trigger), and add an AC.
- [BLOCKING] R17.4 / F11 tier latch: `g ∉ L ∧ |D \ F| < K` reads the saved snapshot, which only changes every `lod_eval_ticks`; nothing says a ground taking a free slot is added to D. As written, any number of newly occupied grounds go detailed until the next snapshot, contradicting Edge Cases ("each newly occupied ground takes a free slot until K are taken"). Specify whether D (saved state) is updated on a free-slot take, and its ordering within one tick (ascending party_id), so the Python and GDScript ports agree.
- [BLOCKING] Edge Cases (Recall abuse) / R11 / OQ-9: says "Only the Golden Boss can recall, so the player cannot trigger it at will", but Golden Boss R13 makes `use_summon_token` recall hunters exactly as R5 (answers OQ-9). The player can now buy immediate settlement that skips Homebound, Selling and Rest with a horn. Decide whether horn recalls keep the skip, update the degenerate-strategy entry, close OQ-9 and drop R11's PROVISIONAL.
- [RECOMMENDED] Dependencies: table still says "No GDD" / PROVISIONAL for Party, Member state machine, Utility AI, Offline, Golden Boss, World view, Quests, Onboarding, Endless Tower — all exist now; Items row still cites OQ-11 as open. Open Questions PROVISIONAL rows for 13/14/31/41 are likewise stale.
- [RECOMMENDED] F1 variable table / PROVISIONAL Party row: states `xp_mult_ppm = 1 + 0.08 (n−1) + 0.10 buffer + 0.05 tank`, omitting Party F1's `− no_buffer_ppm × (1 − B)` term (0 today). Point to Party F1 instead of restating it.
- [RECOMMENDED] F7 / Edge Cases: "realistic range 0–75 s for the living" assumes HP ≥ 25% at trip end, but the flee check runs before an encounter; a won fight can leave a member near 0 HP, so rest reaches ~100 s. Correct the range and the "at most about 75 s" degenerate-strategy note.
- [RECOMMENDED] R17.1 card HP: card stores "each member's HP after" — say whether absolute or a share of hp_max, and what a replay does when a member's hp_max changed by a mid-replay level-up.
- [RECOMMENDED] R17.1 card validity ignores gear, skills and school changes (only level/roster/ground); Edge Cases accepts gear drift but not skill/school changes. List every Combat input the card ignores and confirm AC-36 covers them.
- [RECOMMENDED] Edge Cases (offline hand-off): still describes the superseded "finish with the detailed resolver" recommendation; replace with Offline R5 (pause) as the rule.
- [RECOMMENDED] Header Status reads "In Design" while systems-index read "Designed"; Guild and buildings still does not list Zones (11) as a guild-level reader (bidirectional gap).
- [NICE-TO-HAVE] Registry `kill_base_milli` output_range [30, 4242640] is pre-newbie-window; note that the value passed to award can be ×`newbie_xp_ppm` (3.0) higher during Onboarding.
- [NICE-TO-HAVE] AC-31 "can say why each trip ended (from the reason icon alone)" — measurable as "names the correct reason for ≥ 4 of 5 trips without help".
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/party.md 6d61064e0aa51fe0b2623d9fa43792cd0a330c11
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/realtime-world-view.md 7cd31abd632c70b6504f7a25d90fce0a7647d306
Reviewed-Content-Hash: design/gdd/onboarding-and-tutorial.md 2c478f90a0439cfd555335eb95dce08afe2f20ae
Reviewed-Content-Hash: design/gdd/utility-ai.md 9623faf37b9dba716b70349067a807abd4166ff5
