# Review Log — Arena (Lôi Đài)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L
Specialists: none (lean mode; game-designer, systems-designer, economy-designer and qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 8
Summary: Complete, well-calculated GDD (8/8 sections; F1, F2, F3, F4 and F5 worked examples re-checked and correct against Combat F1, buildings.csv and the registry). It was written against a Jianghu (17) that did not exist yet; the Jianghu GDD now exists and exposes a different interface and units, which invalidates F1's input and the calibration table. Two cross-system holes break the "reward is not farmable" and offline-cap promises: arrears decay of `opponents` lets new-best loot be re-earned, and the tick-based arena day pays for frozen offline time.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Dependencies / R3, R4, R8, F1: Jianghu (17) GDD now exists and contradicts every assumed API. Arena calls `npc_guilds()` (`power_milli` 500–2000), `arena_lineup(guild_id)` (1–5 champions `{school_id, level, power_milli, former_member_id}`) and `add_prestige(...)`; Jianghu R7 provides `npc_guilds_view()` (`power` = CA 0–200, `uid`), `npc_lineup(uid)` (exactly 5 slots `{source, ca, school_id, level, fa_id, member_id}`) and `npc_record_result(uid, fame_delta)`, which the Arena never calls; there is no `add_prestige` and no player-guild prestige owner (OQ-4). F1's `P = power_milli/1000` has no source, so the F1 calibration table, AC-11 and AC-12 rest on an undefined input. Dependencies table still says "no GDD".
- [BLOCKING] R3.3 / R3.2 / F5: `opponents` is a decaying key (Guild and buildings R8; only listed capacity keys are exempt) and restores the tick arrears clear. Shrink removes top NPC seats, regrowth re-inserts the same guilds above rank 1 and shifts `best_rank`, so already-beaten seats become "new bests" again: deliberate arrears (tax near 0, Vertical Slice) re-pays F5 loot each cycle. Contradicts F5 "at most 30 table rolls over the save" and Player Fantasy "the reward is not farmable". Decay to effective level 0 also returns `none`, an Unavailable path the States table says only building removal causes.
- [BLOCKING] F3 / R10: `arena_day` divides the raw tick counter, but Offline R4/R6 skip the full gap `k` including uncredited frozen time ("no timer fires"), and Offline R8 requires every timer owner to register a class. The arena registers nothing and pays up to 3 backlog days for time the 12 h offline cap does not credit; "no arena-specific path" is false.
- [BLOCKING] R6.2 / R7 (OQ-2): the core bout rule needs Combat to accept a caller-built monster row not in `monsters.csv` and a caller-supplied starting HP; Combat R4 reads the member's current `hp` and Combat lists the Arena only as a caller of `resolve`. Needs Combat's acceptance (or the stated alternative) before implementation.
- [RECOMMENDED] R3.3: `best_rank` shift counts removed seats "above the player"; it should count removed seats above `best_rank` (a removal between `best_rank` and the player wrongly improves `best_rank`).
- [RECOMMENDED] R3.2: guilds that go live in a later wave are seeded relative to the player and may be weak, yet are always inserted above rank 1; state whether ladder order is meant to stay power-ordered.
- [RECOMMENDED] R11: invariant `tickets ≤ arena_daily_challenges` fails a valid save if a content update lowers the knob; clamp on load instead of rejecting.
- [RECOMMENDED] Edge Cases / F4: "Jianghu has no NPC guild" (S = 1) contradicts Jianghu's 8–12 live guilds and F4's stated range S 4–11; R4's 1–5 lineup and truncation case vs Jianghu's exactly-5 lineup.
- [RECOMMENDED] Dependencies (bidirectional note): stale — Gold economy R3 already names Arena (type 12); Items, Member state machine and Offline still do not name the Arena.
- [RECOMMENDED] Dependencies / R6: define the Arena's `npc_record_result(uid, fame_delta)` call (when, how much) that Jianghu expects as its only write.
- [RECOMMENDED] Acceptance Criteria: AC-15 "GIVEN any ladder state" is not a test — rewrite as boundary cases (S 1 and 11, r 1 and S, reward_mult 1.1 and 1.8, L_top 1). AC-12's 10–90% band at P 1.1 accepts almost any curve; tighten (e.g. 20–60% at L100 per the F1 table).
- [RECOMMENDED] Formulas / registry: once F1's input is redefined, update registry `arena_champion_row` (its note names `power_milli`).
Reviewed-Content-Hash: design/gdd/arena.md 2ce210ca96466ea7a031e6ad6b6e97b20c5b8d0a
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/jianghu-free-agents-and-npc-guilds.md 9092a7b46bed56bec3486a6bdc7e3fc5c5323fa3
Reviewed-Content-Hash: design/gdd/combat.md cf888cacc1802c9e3bf6b6b888e43e89ba7b9133
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
