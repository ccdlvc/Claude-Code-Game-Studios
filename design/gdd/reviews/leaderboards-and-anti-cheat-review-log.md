# Review Log — Leaderboards and Anti-cheat

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: XL (producer should verify before sprint planning) — server replay worker, 7 formulas, 17 dependencies, at least two new ADRs (OQ-1 replay runtime, OQ-2 signature)
Specialists: none (lean mode; lenses applied by the main reviewer)
Blocking items: 3 | Recommended: 7
Summary: The design is complete (8/8 sections) and its trust model holds up: trust comes from replay, the time budget is cumulative, the top of each board shows verified entries only, and honest players are never accused. Registry values match. Three defects block implementation. The chain and fork rules can permanently unrank honest players who use two devices or come back after a long absence. The top-N display rule does not say which values a verified guild shows while a newer segment is pending. AC-9 still uses the time-budget numbers from the old 8 h cap.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Acceptance Criteria AC-9: the accept/reject threshold is 14,118,000 / 14,118,001 (the old 8 h cap: 13,824,000 + 288,000 + 6,000), but the F1 example and AC-26b give 14,262,000 for the 12 h cap. Rewrite it to 14,262,000 / 14,262,001.
- [BLOCKING] Detailed Design R10 / Edge Cases: the GDD does not say whether the server keeps Superseded boundaries, or the newest boundary once it is older than `fork_window_days`. As written, device A's next segment after device B forks starts from a superseded boundary, and a player who comes back after more than 30 days offline starts from a boundary the server dropped. Both get rejected 3504 `chain_broken`, which permanently unranks honest play (3504 is in the unranked set, R12). That contradicts Player Fantasy ("never punished ... without a recovery path"). Specify that the newest acknowledged boundary is always kept, and say what happens to segments sent from a superseded branch (reject and retry from the server's boundary rather than unrank).
- [BLOCKING] Detailed Design R9 / R13: top guilds submit every 30 min, so they almost always have a Plausible segment pending. R13 says stock values come from the "newest acknowledged or verified boundary", and R9 says the top `verify_top_n` positions show verified entries only. The rule never says whether a verified guild with a newer pending segment keeps its last-verified values in the top N or drops below position N. Without that, the board flickers or the top N empties. State that the top N shows values at the guild's last verified boundary.
- [RECOMMENDED] Formulas F1: `enroll_grace_s` shifts `T_0` back permanently, so every chain carries 14 days of headroom for its whole life, which a speed hack can spend at any time. Consider applying the grace only to ticks logged before the first network contact.
- [RECOMMENDED] Formulas F3 / R5 claims: the client computes `season_boss_kills` claims but cannot know which season its open segment will be received in, because seasons follow server receipt time (F5). Define the claim as kills in this segment, and let the server do the per-season sum.
- [RECOMMENDED] Detailed Design R3: "a few hundred host commands per day ... weeks of play" does not match the arithmetic (100,000 / ~300 per day ≈ 11 months). R16 opt-out keeps growing the log indefinitely, so a player who opts out for a long time reaches a permanent 3510 on opting back in. Fix the wording, and consider clearing the log on opt-out instead.
- [RECOMMENDED] Dependencies: Settings (45) and Guild screens (39) are listed as "No GDD", but both GDDs exist. Neither mentions the leaderboard toggle (R16) or the Rankings screen and badge (UI Requirements), so the dependency is one-way. Golden Boss (14) and Guild and buildings (30) are also one-way (already OQ-9).
- [RECOMMENDED] Acceptance Criteria AC-5: "no frame exceeds the Sim core frame budget because of submission" cannot be attributed. Rewrite it as a measured bound, e.g. "submission work on the main thread is ≤ 1 ms in every frame over the 2 h run; all HTTP runs off the main thread".
- [RECOMMENDED] Acceptance Criteria AC-32: this is a measurement task with no pass/fail condition. Add a threshold (e.g. measured per-player daily cost × projected top-N plus sample volume ≤ the worker budget), or move it to OQ-1's spike.
- [RECOMMENDED] Detailed Design R7.8 / Edge Cases: a server that has retired its core for a pending segment leaves the segment Plausible indefinitely. Define a timeout or an archive rule so it is not stuck for good.
Reviewed-Content-Hash: design/gdd/leaderboards-and-anti-cheat.md 36124b2475f1e23092510a18f6f1bb4d92a0ae06
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/account-and-cloud-save.md 1d2ee76c49defdfb7cc8aae45a3b1ecb6e18403c
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
