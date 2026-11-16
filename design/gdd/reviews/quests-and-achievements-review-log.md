# Review Log — Quests and Achievements

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning)
Specialists: none (lean — game-designer, systems-designer, economy-designer, qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 10
Summary: Structurally complete (8/8 sections), formulas verified against `data/quests.csv` (F1, F2, F4, F6, F7 and AC-4/5/6/17/21 values all check out), and the event-driven, command-clocked design is sound and deterministic. But the free weekly lens, the system's most load-bearing promise (§11.5, IAP pricing), has two gate defects: one slip needs the player to be away, and one becomes impossible once buildings are maxed. The clock-tamper invariant in Edge Cases is false as written, and an honest clock correction freezes the board with no recovery. Two cross-document values conflict.
Prior verdict resolved: First review
Findings:
- [BLOCKING] R6 / OQ-5: from guild level 2 the weekly lens gate requires `q_w_backlog_boss`, which only completes after being away > 1 h (Golden Boss R16 backlog); an always-online player never gets the free lens, against Player Fantasy and §11.5. Decide OQ-5 (exclude from gate, or retarget to "defeat any Golden Boss N times") before stories.
- [BLOCKING] R3 / R6 / Edge Cases: `upgrade_building` (target 2/week) draws on finite content (235 buildable rows; 5 buildings at MVP; hq-level and fund gates); once nothing is upgradable it can never complete, so `q_w_all_done` and the free lens are lost permanently for mature guilds. R3 liveness has no "no upgrade available" rule; Edge Cases line 318 treats "offered" as "completable".
- [BLOCKING] R2.4 / Edge Cases (line 302): "one early reset" / "weekly lens pulled forward by at most one week, never doubled" contradicts R2.3, which accepts any `day_index > cur_day`; stepping the clock forward repeatedly rolls repeatedly (plus 12 h offline catch-up per step), borrowing many weeks at once. Also an honest correction after a wrong-forward clock (or online server time after offline tampering) freezes the board (every `quest_clock` refused 101) for the whole gap with no recovery path. Restate the invariant and add a bound/recovery (e.g. cap forward jump against server time, or re-anchor on server-confirmed time).
- [BLOCKING] Cross-document values: Ads R9 refuses 3301 with `102 quest_satisfied`, but Edge Cases (line 314) and AC-16 cite `3301-2`; registry `quests_event_type_block` note says "Command block 2501-2504" while R10 defines only 2501–2503. Align both.
- [RECOMMENDED] F6 example (line 280): Premium "everything except the backlog boss" is 287 + 65 = 352, not 372 (85 includes `q_w_bounty`, which is never offered).
- [RECOMMENDED] R11 / OQ-10: Items R (storage API) states `give` always succeeds (storage uncapped); close OQ-10 and drop the deferred "if `give` refuses" clause.
- [RECOMMENDED] F5 / IAP OQ-4: stock counts paid lenses, so a lens buyer holding ≥ 5 loses the free weekly lens; state this as the deliberate answer to IAP OQ-4 (or count free-sourced lenses only).
- [RECOMMENDED] R8 / OQ-2: achievements table absent, so R8 is dormant and AC-23–25 cannot run; the "Achievements" half is not implementable until the schema decision is made.
- [RECOMMENDED] F7 / Tuning Knobs / OQ-4: quest gold share ≈ 0.02 against a stated 0.15 early target; the target is unmet by design data — retune or rewrite the target.
- [RECOMMENDED] R2.3 / R3 `login`: unclear whether a rolling `quest_clock` sets the new board's `q_d_login` (roll builds the board in the same applier); `login_day` in R13 is undefined elsewhere. State the order.
- [RECOMMENDED] OQ-8: Golden Boss R16 emits 1406 "in addition to" 1403/1404 with no stated ordering or result field; `defeat_backlog_boss` cannot be implemented until pairing is fixed in Golden Boss.
- [RECOMMENDED] Acceptance Criteria gaps: no AC for R6 "all_done not offered when no non-ad weekly", Premium refund mid-period (R5), R11 all-or-nothing, `add_ad_progress → not_ad_quest`, or the F4 `quest_week_start_day` re-derivation.
- [RECOMMENDED] Dependencies / OQ-14: the systems-index row already lists Market, Offline, Command layer, Items, Local save, Entitlement, Ads; OQ-14 and the bidirectional note are stale on that point. Market, Offline, XP, Rebirth, Enhancement, CA/PA still do not name Quests as a consumer.
- [RECOMMENDED] OQ-15: no `reward_trial` column, so Entitlement R10 trial rewards have no carrier.
Reviewed-Content-Hash: design/gdd/quests-and-achievements.md e7d8bef5eb5406eb19cbbfb37a06298bf63ae89d
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: data/quests.csv 305983eaa348bbb291b23fa8d80505003beca03a
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/ads.md 6aca4cbbabb22607ee97b4ca7ad39ace5a220630
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/in-app-purchases.md 8c7664cce9b979a920419c261cd24312c068259b
