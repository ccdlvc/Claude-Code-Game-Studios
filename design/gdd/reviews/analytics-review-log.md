# Analytics — Review Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (7 formulas, 10 upstream dependencies, backend ingest/retention ADR required; producer should verify)
Specialists: none spawned (lean); systems-designer, qa-lead, game-designer lenses applied in the main session
Blocking items: 5 | Recommended: 7
Summary: Complete (8/8 sections), privacy-first and cleanly isolated from the simulation. Registry values match (subscriber order 3700, queue cap 5,000), every allowlisted event ID exists in the registry or its emitter GDD, and the Gold economy payload slots (2701 c, 2702 d, 2703 b) are right. F2, F4 and F5 check out numerically. But the consent/boot rule loses every first-session sim event, the day attribution that retention depends on is undefined, and the system's own counters would make the server reject whole batches.
Prior verdict resolved: First review
Findings:
- [BLOCKING] R1 / R2 / States: the tap is registered at boot only if consent is already `granted`, and every first launch is `unasked` (the opt-in comes after the R3 notice). So no player's first session ever yields sim events: the R10 first-hour funnel (`boss_won`, `recruit_hire`, onboarding steps) and Onboarding's "15–25 min chain measured by Analytics' funnel" are uncollectable. R2 also says `granted` "takes effect at the next session start" while the States table says host signals are collected "now". Fix: the interactive host always registers the tap with `active = false` and flips `active` on grant; define one activation moment.
- [BLOCKING] R4 / F6 / Edge Cases (clock): `utc_day` is per batch, but batches can sit in the queue for days (R7) and the server rejects any batch whose `utc_day` is more than 1 day from receipt. Either stale offline batches are dropped (contradicting R7) or sessions are dated by upload day, which breaks `first_day` and `has_session` in F6. Fix: put the session's own UTC day in `session_start` and validate against the queue's maximum age.
- [BLOCKING] R8 / R7 / Edge Cases: `queue_dropped`, `upload_rejected` and `raw_overflow` are summary `ev` keys not in the R5 allowlist, and the server drops a whole batch whose `ev` is not in the published allowlist (4xx, not retried). That causes a rejection loop: the batch is rejected, `upload_rejected` is counted, and the next summary is rejected too. Add the system's own counters to the published key list.
- [BLOCKING] R5 / R10 / Dependencies / OQ-7: OQ-7 is marked RESOLVED (take 4401/4402 from the tap), but the R5 allowlist still has "Host: onboarding step completed (PROVISIONAL)" with no 4401/4402 rows. The Dependencies table says Onboarding has "no GDD" (onboarding-and-tutorial.md exists), and the bidirectional note says Onboarding "must list Analytics when designed". The allowlist row, the dependency status and the R10 `onb_step` source need updating.
- [BLOCKING] F7 / R10: §19.5's `out/in` is the whole economy's gold_in/gold_out (mints vs burns per hour). F7 measures only fund flows (tax + shop fund part vs `fund_spent`) and leaves out the `upkeep` fund burn (reported by 2704, not 2703), wallet-side burns (`shop_cost`, enhancement) and mints. Comparing it to "the §19.5 target of 60–90%" would steer balancing wrong. Either redefine F7 over mint/burn entry types or rename it and drop the §19.5 target claim.
- [RECOMMENDED] R5 / Edge Cases (subscriber cap): filtering the allowlist to types registered at boot and checking the 16-subscriber cap both need bus introspection before `seal()` (and the tap registered last), which Event bus R4 does not offer. Also, if the filtered list ends up empty, `subscribe` with an empty list is a boot error. Specify the API, or ask the Event bus for it (OQ-6).
- [RECOMMENDED] F6: the "sid = 1 with a non-zero bucket" reset flag can never fire, because the last `session_end` time lives in the analytics file that decline, reset and reinstall delete. Name where the last-session time is kept, or drop the heuristic.
- [RECOMMENDED] F1: `bucket_max` 16 is reached at 2¹⁵ min ≈ 22.8 days, not "≈ 45 days".
- [RECOMMENDED] F3: `online`, `backing_off`, `lifecycle` and `now` are missing from the variable table, and R8's metered/Data Saver rule is not in the formula.
- [RECOMMENDED] Acceptance Criteria: no AC covers the R8 metered rule, the skip for negative `sum` slots, or the two-instance file lock. AC-23's "equal size and weight" should be measurable (same control type, font size and bounding box ±2 px).
- [RECOMMENDED] Dependencies / OQ-1: Settings (45) is a hard dependency but has no `analytics_consent` key or Privacy rows yet. Its row also lists "sound muted" as an analytics dimension that this GDD does not collect. Reconcile both.
- [RECOMMENDED] Detailed Design note: HTTPRequest/HTTPClient upload feasibility on Godot 4.7 has not been checked against the engine reference. Keep it as a P1 spike item.
Reviewed-Content-Hash: design/gdd/analytics.md a425a3ababa71b12fc0babedb4012cb62b91fd42
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/onboarding-and-tutorial.md 2c478f90a0439cfd555335eb95dce08afe2f20ae
Reviewed-Content-Hash: design/gdd/ads.md 6aca4cbbabb22607ee97b4ca7ad39ace5a220630
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/gdd/entitlement-and-feature-flags.md e988772d3723b158efa58a36578ef586a578bf44
Reviewed-Content-Hash: design/gdd/in-app-purchases.md 8c7664cce9b979a920419c261cd24312c068259b
Reviewed-Content-Hash: design/gdd/account-and-cloud-save.md 1d2ee76c49defdfb7cc8aae45a3b1ecb6e18403c
Reviewed-Content-Hash: JX1_Tycoon_GDD.md ac0a914e274b82095a96f8f66fd43757a52a9566
