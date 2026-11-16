# Review Log — Retention, Leaving and Negotiation

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning)
Specialists: none (lean mode; lenses applied in-session)
Blocking items: 5 | Recommended: 9
Summary: Complete (8/8 sections), unusually precise, and its formulas and worked examples check out against the registry and `data/traits.csv`. It is held back by one hard cross-GDD collision (its reason codes 3–5 are Command layer layer codes), contracts gone stale now that Offline progress and the Member state machine are designed, a same-tick departure rule that contradicts its own AC, and an unanalysed repeat-request loop that undercuts the stated Player Fantasy.
Prior verdict resolved: First review
Findings:
- [BLOCKING] R6 / Edge Cases / AC-12: reason codes `counter_used` 3, `demand_unmet` 4, `bad_amount` 5 collide with Command layer R6 layer codes 3 `bad_arg`, 4 `origin_not_allowed`, 5 `dev_disabled` (which the UI shows as generic tampering text). Renumber into the 100+ owner range like 101–104.
- [BLOCKING] R6 Offline / Edge Cases (Offline and time) / Dependencies: contract mismatch with the now-designed Offline progress (31). This GDD expects `settle_retention(to_tick, slice_inputs)` per slice with per-trip rosters and frozen/extended deadlines; Offline R8/OQ-9 treats Retention as an elapsing `settle_to` owner whose departure timers fire at slice end, with mood/loyalty not modelled. Also unstated: what happens over the uncredited (beyond 12 h) part of the gap. One model must be chosen and written into both GDDs.
- [BLOCKING] R7: recuperation is requested with MSM `enter_injured`, which MSM accepts only from `idle`/`resting`. A timeout that rolls Recuperate while the member is `hunting`, `returning`, `boss_raid` or `training` (the common case) is unspecified: queue it, defer the draw, or apply on next idle?
- [BLOCKING] R8 / Edge Cases (two departures) / AC-24: bonds are deleted only at R8 step 3 (after `away`, at least a tick later), and step 1 hits "every on-roster member" with bond ≥ 20, which includes a co-leaver still in `Departing`. The Edge Case ("bonds as they stand after the previous leaver's bonds were deleted") and AC-24 ("the 5–9 bond is not applied to either") therefore cannot pass as written. State that `Departing` members are excluded from chain bumps (or delete bonds at step 1).
- [BLOCKING] R4–R6 / F3 / Player Fantasy: a Stayed request buys exactly the cooldown. Loyalty's +10 relaxes back to mood with a 46 h half-life (~8% left after 7 days), so a member whose mood target sits below θ re-files every `request_cooldown_days`. The demand kind is a weighted draw unrelated to the cause, so a raise does not fix "Tax −10" (salary_term caps at 0.12·D while the ceiling is 0.5·D, so raises past 12% buy no mood at all). Salaries can ratchet to the ceiling with no mood effect. Analyse the loop and either tie the demand to the top negative term or make the stay effect last, and reconcile with "every request names one concrete thing that would fix it".
- [RECOMMENDED] Dependencies / Quick reference / OQ-1–5, OQ-8: Party, Member state machine, Utility AI, Offline progress, Recruitment and Jianghu are now designed but still marked "Not designed — PROVISIONAL". MSM conforms (enter_injured cause 2, queued enter_away, 4101 to-state 10, add_mood on eating) and Party R17 conforms; update the statuses and close the OQs they answer.
- [RECOMMENDED] R5 kind 4 `ground` / OQ-3: Accept is free and unenforced. Utility AI R12 says considerations are a closed list and a Retention term needs a design change to Utility AI, and `bump_broken_promise` is not a knob. About 20% of requests can be dismissed at no cost. Give it a cost or an enforcement path.
- [RECOMMENDED] R7 vs R6: ignoring a request is a free ~46% coin flip, and Recuperate sets loyalty to max(L, θ+10), which beats Accept's L+10 whenever L < θ. The "Ignore" degenerate-strategy note only cites the 2-day downtime. Check that Accept is never dominated by doing nothing.
- [RECOMMENDED] F10 / Tuning Knobs: at defaults a plain member's mood target (~54 in the F1 example) sits above θ + band (45), so the soft band barely fires, and the doc's own example gives 0.9%/month against a 3–10% target. Give a steady-state estimate showing which inputs are expected to produce the target, rather than leaving it all to the simulator.
- [RECOMMENDED] F1 Variables / Output Range: `trait(mood_gain_party)` can reach 0.15 (`t_generous` + `t_social` + `t_team_player` are mutually compatible in traits.csv), so the best case is 102 and the clamp is reachable at default knobs. `trait(bond_gain)` can likewise reach +0.3 (`t_social` + `t_humble`). Fix the ranges and the "never reached" claim.
- [RECOMMENDED] F3 Example: "≈ −7.6 on the first day" is the linear figure. With the gap closing, 24 h at 1.05%/h gives ≈ −6.7.
- [RECOMMENDED] AC-5: M = 30 with no T given; F2 runs first and moves M. Fix T = 30 (or M = T) so L = 59,685 is deterministic.
- [RECOMMENDED] AC-7: ±300 ppm over 100,000 seeds is about 1.2σ (σ ≈ 257 ppm). Use a fixed seed list or widen to ±4σ (~±1,050 ppm).
- [RECOMMENDED] OQ-7: marked "Confirm with the user before /design-review" and still open. It is the interpretation of locked decision §2 that R7 rests on. Get the confirmation before approval. Logged in autonomous mode, not decided here.
- [NICE] F10 / registry: event 1608 `chain_mood_hit` is named in the registry but never defined in the GDD body. R3 also lists `member_leaving` as a subscribed source, although the chain bump is applied directly in R8 step 1.
Reviewed-Content-Hash: design/gdd/retention-leaving-and-negotiation.md 91d46c4b4dbdcd99a429121e589d1a9330d2da8c
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/ca-pa-and-traits.md 6f94b9f89498c0384ce2e725fc215b4349c0a346
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/party.md 6d61064e0aa51fe0b2623d9fa43792cd0a330c11
Reviewed-Content-Hash: design/gdd/utility-ai.md 9623faf37b9dba716b70349067a807abd4166ff5
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/gdd/jianghu-free-agents-and-npc-guilds.md 9092a7b46bed56bec3486a6bdc7e3fc5c5323fa3
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: data/traits.csv c23100b15a2f93ba4448dfb4a3961c23820d4f87
