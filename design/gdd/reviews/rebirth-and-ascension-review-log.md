# Review Log — Rebirth and Ascension (design/gdd/rebirth-and-ascension.md)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (multi-system integration, 6 formulas, 13 upstream deps, elder-buff cache/applier ADR pending; producer should verify)
Specialists: none (lean mode; game-designer, systems-designer, economy-designer and qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 9
Summary: All 8 sections are present and the arithmetic checks out (F1 ladder totals, F4 afford hours, F5 reachability, R10 upkeep, AC-2 F7 levels, registry values). The blockers are about how this GDD connects to the systems it depends on. It still treats the Member state machine as undesigned, and that system's real `can(rebirth)` and `enter_elder` rules break the "cannot fail after gates" promise. Four of the ten school Elder buffs use keys that no consumer reads through `trait_mod_ppm`. AC-10 still tests the retired code 111. The synchronous one-time-reward contract that AC-5 depends on is contradicted by how Schools and CA/PA describe their side.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Acceptance Criteria AC-10: expects refusal 111 "(5 of 5 Elders)", which contradicts R9 (111 retired, never emitted), F2 (no Elder cap) and AC-14. Remove the 111 fixture.
- [BLOCKING] R4 rule 7 / R6 step 4 / Dependencies: Member state machine (41) is designed, but this GDD calls it "PROVISIONAL, no GDD". MSM defines `can(rebirth)` as true in `idle`, `returning` and `resting`. That differs from R4's list: it allows `returning` (not at home) and does not exclude `bounty`. MSM's `enter_elder` accepts only `idle`, so an Ascension of a `resting` or `returning` member passes the gates and then fails after the gold debit. R6 also lacks R4's "steps cannot fail / ctx.fail" atomicity statement. Fix: use `can(rebirth)` as the gate, pick the Ascension state precondition (idle-only, or MSM widens T22), and state atomicity for R6.
- [BLOCKING] R8 / F3 / Tuning Knobs (elder_buffs.csv): the "no new read path, every consumer gets it via trait_mod_ppm" claim fails for several keys. `xp_mult` and `skill_xp_mult` have no reader (CA/PA "keys no system owns"; XP R5 applies only PA and rebirth bonuses member-side). `injury_recovery` is a building `effect()` key read by MSM, not a trait key. Items F3 reads `rare_drop`, not `drop_rate`. So the thuy_1, thuy_2, moc_1 and tho_2 Elder buffs (and parts of the F3 example, AC-11 and AC-13) do nothing in the game, and the F3 XP feedback-loop analysis is moot. CA/PA (9) does not mention `elder_mod_ppm` at all, although the registry lists it as a referencer. Fix: restrict school buff keys to keys with a consumer, or get owners for them, and add a validator rule.
- [BLOCKING] R4 accepted-step 5 / Edge Cases "same batch" / AC-5 / AC-6: the same-tick free-credit and reveal guarantees need synchronous `grant_free_change` and `reveal_on_rebirth` calls. Schools R6 and its interactions consume a "completed rebirth tier" signal, and CA/PA's interactions table lists a "Rebirth event with rebirth_no" (event-driven, P6). If either owner applies the reward from the 2301 event, AC-5 fails. OQ-5 and OQ-6 record this but leave it open. Agree on one interface with 9 and 20 before implementation.
- [RECOMMENDED] F2 / F6 / OQ-13: stale slot-era remnants. F2 example "HQ 8, Shrine 6, 7 Elders" and the HQ reference; F6 "Elder count ≤ 20" and "Elders × traits ≤ 20 × 3", which are wrong now that Elders are unlimited.
- [RECOMMENDED] F6 / R8: `elder_mod_ppm` is O(Elders × traits) with no upper bound and is added to every `trait_mod_ppm` read (Combat hot path). Make the cache (invalidated on 2302 and 903 for an Elder) a rule, not an optional ADR choice.
- [RECOMMENDED] R3: says one-time rewards fire at "R4 step 6", but they fire at step 5. Step 6 is the event emit.
- [RECOMMENDED] AC-12: the "share giving −12,345.6" fixture cannot be built at share 250,000 with integer trait_ppm. Give concrete trait_ppm and share values, for example trait_ppm −49,383 at 250,000 → −12,345.
- [RECOMMENDED] F5 / OQ-4 / Player Fantasy: CA ≥ 180 needs PA ≥ 160 and near-max CA terms. The fantasy is a guild that keeps "graduating" walk-ins. Quantify the recruit PA ≥ 160 share (Recruitment distribution) before Wave 3, or Elders may be too rare to deliver the ending.
- [RECOMMENDED] F3 variables: the `school_buff_ppm` range is 0–1,000,000, but Tuning Knobs gives a safe range of 0–`elder_buff_cap_ppm`. Align them, and make the validator enforce one.
- [RECOMMENDED] F4: Σ level_i should exclude Elders, who do not hunt or earn. Otherwise late-guild fund income is overstated.
- [RECOMMENDED] Dependencies bidirectionality: Items (26) still lists Rebirth as "Not designed (Alpha)". CA/PA (9) has no `elder_mod_ppm` or `reveal_on_rebirth` entry. The registry `elder_mod_ppm` referenced_by CA/PA is unbacked.
- [RECOMMENDED] AC-15 has a `[PENDING]` dependency on Schools, Retention and Party. AC-20's "±20% of GDD §4.3" relies on Dev tooling (43). Mark both as integration-gated so the story does not close on them.
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/ca-pa-and-traits.md 6f94b9f89498c0384ce2e725fc215b4349c0a346
Reviewed-Content-Hash: design/gdd/schools-and-school-change.md b468deba3ea43b60bb05cee1b5ae8ce989637c3c
Reviewed-Content-Hash: design/gdd/skills.md 5ccd62bd5b0d5419255d23ca2b3f4b92244c9583
Reviewed-Content-Hash: design/gdd/xp-and-level-pacing-curve.md 8b013cb956e1ab238db7f78e811a78b4e397e7fb
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
