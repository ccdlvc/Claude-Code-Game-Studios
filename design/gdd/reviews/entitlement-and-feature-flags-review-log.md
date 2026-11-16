# Review Log — Entitlement and Feature Flags (design/gdd/entitlement-and-feature-flags.md)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (multi-system integration, 4 formulas, 9+ dependencies, cache/billing/boot ADRs pending; producer should verify)
Specialists: none (lean mode; game-designer, systems-designer, qa-lead lenses applied in-session)
Blocking items: 5 | Recommended: 7
Summary: Complete (8/8 sections) and well structured: the logged `set_entitlement` command, no-downgrade cache rule and data-driven flag table are sound, and registry values (block 3200, provisional_grace_h 72, entitlement_refresh_min 60, trial_max_h 48, offline_cap_free_h 12) match. Five defects block: stale 24 h offline-cap claims survive the equal-cap decision, the host interface does not match the now-designed Ads GDD, AC-20 cannot pass as written, the F2 persistence of first_seen_utc has no home in the R6 cache schema, and F1 defines held(p) twice with different results.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Summary (L12) / Player Fantasy (L24) / Quick reference (L14): still promise a "24 h offline cap" and "credits 24 hours of offline work" and list Offline progress (31) as a dependent; contradicts R8's removal of `offline_cap_extended`, Offline R4 (12 h for everyone, reads no entitlement) and registry `offline_cap_premium_h` (deprecated). Remove the claims and the Offline (31) dependent.
- [BLOCKING] R1 / Interactions / Dependencies vs ads.md R2, Interactions, OQ-10: Ads (now designed) consumes host-side `is_premium` + `ready` + a change signal and fails closed until ready; EFF exposes no `ready` state, no host change signal, forbids raw `is_premium` reads, and says host consumers read the sim view only "once the guild is loaded", leaving pre-load (title/consent screens) undefined. Define the host API (ready semantics, signal, pre-load source) and reconcile names with Ads. Downstream table also still marks Ads, Quests and Leaderboards "Not designed".
- [BLOCKING] Acceptance Criteria AC-20: `view.flags`/`source`/`applied_tick` are saved sim state, so two runs that differ in `set_entitlement` cannot have identical state hashes. Restate as: hashes identical excluding the `entitlement` section (or compare every other section's hash).
- [BLOCKING] F2 vs R6: F2 says `first_seen_utc` is "saved in the cache file so a restart does not reset the window", but the R6 cache schema `{account_id, premium_owned, pa_eye_owned, fetched_utc}` has no such field and the cache is written only after a successful ledger read, i.e. never during the offline purchase case R5 exists for. Add a per-product `first_seen_utc` to the cache (written on first sight of a store purchase) or state that a restart restarts the window; AC-8 needs a restart case.
- [BLOCKING] Formulas F1: `held(p)` is defined as `server(p)` when a read succeeded, then redefined as `server(p) ∨ prov(p)`; the two give different answers for a purchase made after the last read. Keep one definition and align R4's per-bit priority text with it.
- [RECOMMENDED] R3 / R4 / F1 example: one `source` for both bits loses provenance (F1 example: premium from cache is logged as source 3); if R11 matters, log per-bit source or say why one is enough.
- [RECOMMENDED] R11 / Player Fantasy "The leaderboard can see who was Premium": leaderboards-and-anti-cheat.md never reads `set_entitlement` and states boards carry no entitlement field (AC-26); with the equal cap the rationale is weak. Either drop the promise or get Leaderboards to own a policy (PROVISIONAL-3).
- [RECOMMENDED] F2 boundary: a clock set back keeps the provisional grant indefinitely (negative difference always < window). Treat `now_utc < first_seen_utc` as expired or re-anchor first_seen, rather than "holds".
- [RECOMMENDED] Dependencies: Quests lists Entitlement as Soft and has its own OQ-13/OQ-15 on `grant_trial`; this GDD calls Quests Hard. Align; systems-index Depends On row lacks Event bus and Sim core that the GDD adds.
- [RECOMMENDED] AC-16: a sim-side `grant_trial` "logged to the host log sink" crosses the determinism boundary; prefer a content-validator rule rejecting quest rewards that name a non-trial-eligible feature.
- [RECOMMENDED] AC-11: "exactly 3 ledger reads" in 3 h is ambiguous about the boot read and the starting phase of the timer; state the start condition.
- [RECOMMENDED] Dependencies: Event bus (42) is Needs Revision upstream; re-verify R10's registration once it is revised.
Reviewed-Content-Hash: design/gdd/entitlement-and-feature-flags.md e988772d3723b158efa58a36578ef586a578bf44
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/in-app-purchases.md 8c7664cce9b979a920419c261cd24312c068259b
Reviewed-Content-Hash: design/gdd/ads.md 6aca4cbbabb22607ee97b4ca7ad39ace5a220630
Reviewed-Content-Hash: design/gdd/quests-and-achievements.md e7d8bef5eb5406eb19cbbfb37a06298bf63ae89d
Reviewed-Content-Hash: design/gdd/leaderboards-and-anti-cheat.md 36124b2475f1e23092510a18f6f1bb4d92a0ae06
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/party.md 6d61064e0aa51fe0b2623d9fa43792cd0a330c11
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
