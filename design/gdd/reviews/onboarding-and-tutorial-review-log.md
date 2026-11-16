# Review Log — Onboarding and Tutorial

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning)
Specialists: none (lean mode; lenses applied in-session)
Blocking items: 4 | Recommended: 7
Summary: Complete on structure (8/8 sections), registry values all agree (tick_rate 10, recruit_founding_roster 5, block 1500, ui_ prefix, command block rule 100, offline_threshold_s 60, award_base_max_milli 2^40, golden_boss_warning_s 120), and every trigger event ID matches its emitter. It fails on stale dependencies: Guild screens (39), Settings (45), Ads (33) and Realtime world view (38) now have GDDs, and two of them do not provide what this GDD relies on. There are also two places where the rules contradict each other: acking a tip that has not been seen yet, and where the offline path resumes the chain.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Dependencies / R11 / AC-22: Settings (45) is designed but defines no "Show tips" toggle; Dependencies still lists Settings, Guild screens, Ads and World view as "Not designed — PROVISIONAL". Re-verify each against its GDD, and get Settings to add the toggle (or drop R11).
- [BLOCKING] R8 / R9 / UI Requirements: anchor contract mismatch. Guild screens R18 names anchors `ui_anchor.<screen>.<control>` and says Onboarding "needs no other hook" (its OQ-6), while this GDD uses bare IDs (`recruit_board`…) and needs an "affordable building now" query for `tip_build_ready` that Guild screens does not expose (it has only an R14 badge rule). Align the IDs and the query.
- [BLOCKING] R6 vs States and Transitions: R6 does not refuse `onboarding_ack` on an `event` tip row that is still Unseen, yet the state machine says only `ui` tips can be acked while Unseen. Add a reason code (e.g. 105 `onb_not_pending`) and an AC.
- [BLOCKING] R7 vs Edge Cases: the edge case says "hire, close app, return → chain resumes at `safeguard`", but `first_party` has `offline_ok = 0`, so it resumes at `first_party` unless a party already formed. `first_level` with `offline_ok = 1` also toasts a level-up that may not have happened, and Offline R15 already forwards real 2201 events. Gate R7 on a party existing, or on trips the summary actually records, and fix the edge case.
- [RECOMMENDED] R10.1 vs Edge Cases: "after 120 s `tip_boss` is no longer forced to the top" is not in R10 and needs a stated timer source (sim tick of 1401 + warning ticks, or wall clock).
- [RECOMMENDED] Dependencies (bidirectional): Zones R17.3 lists Onboarding as registering a `lod_force` predicate for the tutorial ground; this GDD never mentions it. Adopt it or ask Zones to drop it.
- [RECOMMENDED] R12: account states `Conflict`, `Blocked`, `Disabled` and a cancelled or failed link flow are unhandled.
- [RECOMMENDED] Dependencies status column is stale: Command layer, Local save, Zones, World view and Guild screens are Needs Revision in the index; Zones "call not yet in its GDD" contradicts OQ-2 RESOLVED.
- [RECOMMENDED] AC-3 / AC-11: preconditions are unreachable in play (bit 7 done before bit 2; a kill at tick 100). State them as injected fixtures.
- [RECOMMENDED] Acceptance Criteria: R8 has no criterion (acknowledged gap). Add one once the Guild screens query exists.
- [RECOMMENDED] Header: CD-GDD-ALIGN is NOT ASSESSED because no pillars, concept or brief exist. Re-run once one exists.
Reviewed-Content-Hash: design/gdd/onboarding-and-tutorial.md 2c478f90a0439cfd555335eb95dce08afe2f20ae
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/gdd/ads.md 6aca4cbbabb22607ee97b4ca7ad39ace5a220630
Reviewed-Content-Hash: design/gdd/realtime-world-view.md 7cd31abd632c70b6504f7a25d90fce0a7647d306
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/account-and-cloud-save.md 1d2ee76c49defdfb7cc8aae45a3b1ecb6e18403c
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
