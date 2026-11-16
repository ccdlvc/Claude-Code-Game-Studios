# Review Log — Golden Boss and Guild Raid

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning)
Specialists: none (lean — game-designer, systems-designer, economy-designer, qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 6
Summary: Complete (8/8 sections), formulas check out exactly (F1–F5 examples and ranges recomputed; registry values 60 / 3 / 0.5 / 6 / 300 / block 1400 and RNG domains 6/7 all agree). Blocking issues are internal contradictions left behind by the 2026-11-16 consistency pass (offline-trip edge case, AC-7 end state), a missing command-vocabulary row for `set_raid_opt_out`, and an under-specified slot lifecycle when a slot's announcement or due tick lands during another raid. All are small text fixes; the design itself is sound.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Edge Cases (line 218): "Offline progress has already closed all trips before R16 runs (PROVISIONAL on 31)" contradicts R16 and PROVISIONAL-3 (resolved) and Offline R10: live trips are paused, not closed; their members count as home. Delete or rewrite the edge case.
- [BLOCKING] Acceptance Criteria AC-7: says capped-out members end `idle`; R6 and Member state machine R8 send them through `leave_raid(alive=true)` → `resting` (Hunt F7), then `idle`. The AC tests the wrong end state.
- [BLOCKING] Detailed Design R12 / Dependencies: `set_raid_opt_out` is not in Command layer's vocabulary table (only `use_summon_token` is, command-layer.md line 164); the only input path cannot route it. Add the row (owner 14, host/UI, refusal unknown_member) or record it as a Command layer gap.
- [BLOCKING] Detailed Design R2/R14 + States table: announcement/pick is modelled as raid state (`Idle → Announced` only), but R14 assumes a slot whose warning or due tick falls during `Gathering`/`Fighting` still gets announced and picked "as usual". Specify announcement as per-slot (independent of the raid state machine) and define what happens when `queued_slots` is already at `golden_boss_backlog_max` (dropped? emitted as skipped? does `slot_ordinal` still advance?).
- [RECOMMENDED] Dependencies table: Party (13), Member state machine (41), Offline (31), Market (29) still read "Not designed — PROVISIONAL"; all four GDDs exist. Party R16 (`parties_for_raid`, accepts R7 step 2) and MSM R8 (`enter_raid`/`leave_raid`) now answer PROVISIONAL-1/-2 — close them and drop the R7 step-2 [PROVISIONAL] tag (Party OQ-4).
- [RECOMMENDED] R4 condition 2: "`resting`-complete" is not a state; MSM R8 lists `resting` and `returning` as not eligible. Say `idle` or `hunting` (recall hand-off) only.
- [RECOMMENDED] AC-6: "the raid starts at the first group's arrival + no later than 120 s" is ambiguous; state the exact start tick (due tick + `raid_gather_max_s × tick_rate`, since the second group never arrives) and that group 1 is in the raid.
- [RECOMMENDED] AC-23: no numeric pass/fail threshold ("within the budget share … to be measured"). Give a provisional ms budget for `resolve` with n 40 on the reference device, revisable after P1.
- [RECOMMENDED] F4/F5 + Edge Cases: economy — the carry case pays an opted-in L25 member 6 boss-level (L50) kills/hour of XP for zero contribution; with `raid_min_reward_frac` 0.3 this likely outpaces hunting at L25. OQ-5 defers to the simulator; add a target ratio (raid XP per hour ÷ hunt XP per hour at member level) so the sim has a pass criterion.
- [RECOMMENDED] R16 backlog: three backlog raids resolve against the end-of-window roster with every member at full HP and no deaths carried between them (injury from raid 1 should gate raid 2 via R4). State whether R4 is re-evaluated between backlog raids.
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/party.md 6d61064e0aa51fe0b2623d9fa43792cd0a330c11
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/xp-and-level-pacing-curve.md 8b013cb956e1ab238db7f78e811a78b4e397e7fb
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/combat.md cf888cacc1802c9e3bf6b6b888e43e89ba7b9133
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
