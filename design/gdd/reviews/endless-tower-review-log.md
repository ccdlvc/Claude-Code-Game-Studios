# Endless Tower — Review Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L
Specialists: none (lean; game-designer, systems-designer, economy-designer and qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 5
Summary: Complete 8/8, formulas check out arithmetically against data/ (F1–F5 examples, zone_05/zone_10/zone_11 bands, 12 Hoả rows, drop_zone_10 expectations, rebirth tier 2 = L120), and registry values agree. The blockers are cross-document: the GDD still claims Member state machine (41), Rebirth (23) and Offline progress (31) have no GDD, but 41 and 31 now exist without any `tower` state or tower advance; OQ-5 is marked resolved while Items has no keyed/roll-count guild roll. One AC contradicts Combat F8, and retreat during the `Ready` gap is unspecified.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Dependencies / R5 / R7 / R12: Member state machine (41) is designed and has no `tower` state (codes 1–11), no enter/leave API, and its raid-eligibility and `enter_away` rules do not mention tower members; the GDD still lists 41 as "no GDD". Either 41 gains a `tower` state (code 12, enter/leave calls, eligibility rows) or the tower reuses an existing state; Offline progress (31) likewise exists but has no exact tower advance (R11, AC-22).
- [BLOCKING] R9 / F4 / OQ-5: OQ-5 says Items R9a adds `roll_guild_loot_keyed(key, loot_table, level, rolls)`, but items-and-loot-tables.md R9a only defines `roll_guild_loot(raid_ordinal, loot_table, boss_level)` (Golden Boss keyed); no key or roll-count variant exists. Re-open OQ-5 or get Items to add the API.
- [BLOCKING] Acceptance Criteria AC-10: `duration_s = 15.6` gives Combat F8 `ceil(15.6 × 10) = 156` (binary64 gives exactly 156.0), so HP changes at T + 156, not T + 157 as written.
- [BLOCKING] R6 / R7 / States: a `tower_retreat` arriving in P1 normally finds the run in `Ready` (the `tower_floor_gap_s` wait, cost already paid), since `Between` only exists inside P3→P4 of one tick. R7's Ready branch never checks `retreat_requested`, so the next floor is fought anyway. Specify: retreat in `Ready` ends at once (cost forfeited or refunded — choose) or after the next floor.
- [RECOMMENDED] Edge Cases: "survivor fails the high-floor gate … impossible today" is wrong — R5 #6 checks the gate only when the start floor is high, so a run starting at floor 45 with a tier-1 member ends `high_floor_locked` at 50 in normal play. Fix the edge case and add an AC for reason 7 (AC-17 covers 1, 2, 4, 5 only).
- [RECOMMENDED] F3: `candidates(e)` counts live rows, so a new content wave changes which monster an uncleared floor uses, and a save mid-`Fighting` across a content update re-resolves differently (R7/Member side claims identical replay). State that content updates are applied only between runs, or pin the pool per run.
- [RECOMMENDED] Dependencies: bidirectionality — Golden Boss (14) and Retention (16) GDDs do not mention tower members; Zones (11) still says "No GDD" for Endless Tower. Raise with those owners.
- [RECOMMENDED] AC-27: "reference desktop" is not defined here and "no more than one floor fight resolves per tick" needs reconciling with offline exact catch-up (R11); name the reference machine/source and the offline tick model.
- [RECOMMENDED] OQ-3: says 15 tower knobs; Tuning Knobs lists 17 `sim_params` keys (plus `tower_max_runs`). Reconcile the count.
- [NICE] AC numbering: AC-27 follows AC-30; F2 "floor 1,000 about 29×" is 29.76 (≈30×).
Reviewed-Content-Hash: design/gdd/endless-tower.md e962f7799a12b16baeae8120add5c5c0a27d961b
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/combat.md cf888cacc1802c9e3bf6b6b888e43e89ba7b9133
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/retention-leaving-and-negotiation.md 91d46c4b4dbdcd99a429121e589d1a9330d2da8c
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/leaderboards-and-anti-cheat.md 36124b2475f1e23092510a18f6f1bb4d92a0ae06
