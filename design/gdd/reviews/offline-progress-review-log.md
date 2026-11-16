# Review Log — Offline Progress

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning)
Specialists: none (lean mode; game-designer, systems-designer, economy-designer and qa-lead lenses applied in-session)
Blocking items: 3 | Recommended: 8
Summary: Structurally complete (8/8 sections) and the registry values agree (cap 12 h, slice 7,200 s, 4 samples, skew 300 s, backlog 3, domain 5, block 3100, threshold 60 s). The design is a sound driver over Zones' sampled resolver, but three rules do not hold together: an AC contradicts R6 on never-hunted members, per-gap truncation of fractional trips silently drops loot and gold on short and medium absences (contradicting the Edge Cases "neither helps nor hurts" claim, which AC-7 tests only for XP), and the clock trust policy compares a device-clock high-water mark against a server-clock "now".
Prior verdict resolved: First review
Findings:
- [BLOCKING] Acceptance Criteria AC-9 vs R6.3: AC-9 says "a member who never hunted earns nothing"; R6.3 says a brand-new member who never hunted is grouped and sampled like any other. Pick one and align the other.
- [BLOCKING] F4 / Edge Cases (threshold gap): `carry_g` is "per group, per gap", so fractional trips are discarded at every gap's end. A gap shorter than one mean trip hands in 0 bags (no loot, no gold) while XP is still credited; a 30-min gap with 20-min trips loses a third of the loot. The live trip is paused, so nothing compensates. Persist the carry across gaps in the save section, or resolve the fraction with a domain-5 draw, and extend AC-7 to gold and stored units.
- [BLOCKING] R3 / F1 clock bases: `hw_utc` is recorded from `GameClock.utc_s()` (device) at saves, but `now_utc` is `server_utc_estimate()` when known; `now_utc − hw_utc` mixes two clocks, so an honest device running fast loses credit (and R3.3 then writes a server time into a device-time mark). State one time base for both terms (e.g. store hw in server time when known, or always compare device-to-device and use the server only for the skew flag).
- [RECOMMENDED] Dependencies: Party (13), Member state machine (41), Leaderboards (35), Guild screens (39), Realtime world view (38) and Local push notifications (46) are listed "No GDD" but all exist; Party R20 answers OQ-4 and Member state machine R18 answers OQ-9 — update statuses and close those OQs.
- [RECOMMENDED] R6.1 vs Edge Cases (boss_raid): R6.1 makes `boss_raid` members unavailable, the edge case makes them available from slice 0 after Golden Boss finishes the raid at `at_tick`; state one rule and cite the Golden Boss rule that finishes the raid.
- [RECOMMENDED] Tuning Knobs: the deprecation paragraph after the first row splits the markdown table; rows below it no longer render as a table. Move the note below the table.
- [RECOMMENDED] OQ-11 (targeted at design review): keep freezing uncredited time (exploit-safe, no upkeep for unworked time); close the OQ (decision logged).
- [RECOMMENDED] OQ-10 / Degenerate strategies: "Offline is never better than live per hour" is unproven once consumables are bought live (GDD §19.2 ~23% of income). Gate it with an AC-6 variant at Vertical Slice (S3).
- [RECOMMENDED] R2 / R5: the starting state of a sampled copy (HP, potions) is not stated, notably for a member whose live trip is paused at low HP. Say "copy starts at full HP from home" or equivalent.
- [RECOMMENDED] Overview/Why: cites GDD §4.3 pacing with the old 8/24 h cap; flag a master-GDD update for the 12 h equal cap.
- [RECOMMENDED] Header Status still reads "pending independent `/design-review`"; update after revision.
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/party.md 6d61064e0aa51fe0b2623d9fa43792cd0a330c11
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
