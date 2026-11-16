# Review Log — CA/PA and Traits

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L
Specialists: none (lean mode; game-designer, systems-designer and qa-lead lenses applied in-session)
Blocking items: 5 | Recommended: 7
Summary: Structurally complete (8/8 sections) and the maths holds. F1, F2, F4 and F5 examples recompute exactly, and the F3 nested chain is provably nested and uniform-preserving. What blocks is the contracts. The estimate key is stated two ways. Recruitment and Rebirth call interfaces this GDD does not define. The Member model does not store the fields this GDD writes. The trait term of CA rewards negative traits, and through the Ascension gate it requires three revealed epic traits at PA 160.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R7 / AC-9 / AC-14: R7 keys the domain-9 chain as `[member_id, w]`, but R1, F3, Interactions and Edge Cases key it as `[pa_key, w]`; ACs say "member IDs"/`[id, …]`. member_id is issued only at hiring, so following R7 changes the range at hire and breaks the "same range" promise. Use `pa_key` everywhere.
- [BLOCKING] R2 candidate_view vs Recruitment R7: Recruitment expects `candidate_view` to return the candidate's CA (F1 on the candidate spec: level, school, no skills/gear, revealed traits). This GDD's `candidate_view` returns `{exact, lo, hi, half_stars, surface_trait}` and `ca()` takes only a member_id. Define candidate CA, either as a field of `candidate_view` or as `ca_of_spec`.
- [BLOCKING] R9/R11 vs Rebirth and Ascension R3/Interactions: Rebirth calls `reveal_on_rebirth(member_id, rebirth_no)` and adds `elder_mod_ppm` into `trait_mod_ppm`. This GDD has neither: R11 reacts to a rebirth event, and `trait_mod_ppm` sums only traits. Agree on one contract and write it in both docs.
- [BLOCKING] R1 / Dependencies vs Member model R1 field table: the hard upstream stores only `pa` and `traits[]`. `pa_key`, `pa_lo`, `pa_hw`, `pa_exact` and the per-trait `revealed` flag are absent, so they have no persistence or save/migration path (OQ-1 still open).
- [BLOCKING] R4/F1 trait term + OQ-4/OQ-9: CA points count by tier regardless of sign, so revealing a negative trait raises "current ability". At PA 160 Ascension needs raw CA at 200,000, which means three revealed epic traits on top of max level, skills and gear. "PA ≥ 160 and every term at maximum" understates this. Decide the trait term (a signed `ca_points` column, or drop it from the gate) before trait data ships.
- [RECOMMENDED] Dependencies: Recruitment, Rebirth, Golden Boss, Party, Retention, Jianghu and Offline GDDs now exist but are marked "Not designed — PROVISIONAL"; refresh statuses and the Bidirectional status paragraph.
- [RECOMMENDED] R11 `event:skill_learn`: Skills emits only 2102 `signature_skill_learned` (ultimate/secret by training); there is no general skill-learned event. Name the source event or narrow the condition.
- [RECOMMENDED] R11 `event:party_hunt`: Party says it adds no event; the trigger is Zones 1104 with roster size from 1101. Cite that source. Likewise cite Retention 1604 `member_leaving` for `event:leave_guild`.
- [RECOMMENDED] OQ-17: Guild and buildings still lists only Recruitment as the `bld_scout` `pa_error` reader and does not list `trait_reveal_speed` for this system.
- [RECOMMENDED] OQ-2: trait XP keys (`xp_mult`, `xp_mult_above_L50`…) have no owner. The Player Fantasy's "late bloomer suddenly accelerates at level 50" is therefore not delivered by any designed rule.
- [RECOMMENDED] Tuning Knobs vs F2: `pa_hw_min` range is 1–20 in F2 and 1–10 in Tuning Knobs; pick one.
- [RECOMMENDED] R2 init_potential: "the width the candidate was shown" is false if the Scout House or a Keen Eye reveal changed between view and hire. The result is still correct because of path independence, but reword it to "the current F2 width".
Reviewed-Content-Hash: design/gdd/ca-pa-and-traits.md 6f94b9f89498c0384ce2e725fc215b4349c0a346
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/skills.md 5ccd62bd5b0d5419255d23ca2b3f4b92244c9583
Reviewed-Content-Hash: design/gdd/xp-and-level-pacing-curve.md 8b013cb956e1ab238db7f78e811a78b4e397e7fb
Reviewed-Content-Hash: design/gdd/retention-leaving-and-negotiation.md 91d46c4b4dbdcd99a429121e589d1a9330d2da8c
Reviewed-Content-Hash: design/gdd/party.md 6d61064e0aa51fe0b2623d9fa43792cd0a330c11
