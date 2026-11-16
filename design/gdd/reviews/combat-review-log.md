# Combat — Review Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (8 formulas, 7 dependencies, likely an ADR on binary64 vs fixed-point; producer should verify)
Specialists: none spawned (lean); game-designer, systems-designer, qa-lead lenses applied in the main session
Blocking items: 3 | Recommended: 8
Summary: Complete (8/8 sections), precise, and every registry value matches (element mults 1.25/0.80/0.95, monster_dmg_factor 0.05, tank_aggro_share 0.7, buffer_atk 0.08, buffer_dmg_reduction 0.10, healer_heal_frac 0.03, fight_time_limit_s 600, tick_rate 10, domain 1/6). Hunt parity with `sim/hunt.py fight()` checks out line by line. But the load-bearing claim that one resolver reproduces `simulate_raid()` bit for bit is false on two counts, and the numeric contract with Member model and Skills, both now Designed with integer milli/micro values, is undefined.
Prior verdict resolved: First review
Findings:
- [BLOCKING] R3 / AC-2: combatant order is "groups concatenated", but `simulate_raid()` draws start-ups, breaks ties and builds the target pool in the raw `members` order, while `form_parties()` reorders (buffers, tanks, rest). Raid parity cannot hold. Either add an explicit combatant order to the encounter, or drop raid bit-parity and regenerate vectors with a `sim_version` bump.
- [BLOCKING] F1 / R3: `hp_scale = (1 + hp_per_participant × n) × raid_hp_mult` precomputed gives `M × (X × R)`; code computes `(M × X) × R`. Measured: 14,036 of 40,000 (L 1–200, 5 hp_mults, n 1–40) differ in binary64. Contradicts "evaluated left to right" and the bit-for-bit claim. Keep the two factors separate in F1 or accept the change.
- [BLOCKING] R4 / Dependencies / OQ-3: Member model (Designed) exposes `profile()` as integers (`dps_milli`, `hp_max_milli`, `def_milli`) and stores `hp_milli`; Skills (Designed) resolves effects as integer micro-units with "no float at run time". Combat reads float `dps`/`hp_max`/`def`/`hp` and returns float `hp_after`. Define the milli→binary64 conversion and the rounding of `hp_after`/`taken` back to `hp_milli`, or move to fixed-point now. Also reconcile Member model's "level rises mid-fight: Combat reads the new profile" and "Combat writes hp_milli" with R1/R4 (snapshot, caller applies). Dependencies table still lists Member model, Skills, Party as Not designed.
- [RECOMMENDED] R3 / R6 / AC-7: a member action at `t` just past `time_limit_s` (top-of-loop check passed at t ≤ limit) can still kill the monster, so `won = true` with `duration_s > time_limit_s` is possible. State it in R3/Edge Cases and AC-7.
- [RECOMMENDED] Interactions (domain-1 key) / PROVISIONAL-3: Zones R5 and Party R5 define `party_id` as the key leader's `member_id` and `trip_ordinal` as that leader's `trips_led`; Combat still says "stable ID of the hunting group, a party ID is never reused". Align wording and close PROVISIONAL-3.
- [RECOMMENDED] R15 / PROVISIONAL-2: Skills R1 says Combat owns mana pools, cooldowns and casting; PROVISIONAL-2 says members "get an MP pool" from Skills. Name the owner of MP max/regen.
- [RECOMMENDED] R15: Skills `chance` values are ppm for RNG `chance_ppm`; R15 does not say crit/chance draws use `chance_ppm`. Note it in the stage-2 draw list.
- [RECOMMENDED] Member model OQ-4: `gear_stat(crit_rate)` is exposed for Combat to define; Combat is silent. Say stage 1 ignores it, or define it.
- [RECOMMENDED] R11: "a member's death counter is incremented by the caller" but Member model says lifetime `deaths` is Dev tooling instrumentation, not state. Drop or re-own.
- [RECOMMENDED] AC-26: "within the bands of Dev tooling's balance budget" has no numbers yet; AC-24/27/28/29 also PENDING. Not testable until those land; track them.
- [RECOMMENDED] Header: CD-GDD-ALIGN NOT ASSESSED (no pillars/concept); Player Fantasy unchecked against pillars.
- [NICE] F8 example: `ceil(156.16)` should read `ceil(156.158)`.
Decisions (autonomous, logged to production/session-logs/decision-log.md): no revision in this session (review-only instruction); systems index set to Needs Revision; review log appended.
Reviewed-Content-Hash: design/gdd/combat.md cf888cacc1802c9e3bf6b6b888e43e89ba7b9133
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/skills.md 5ccd62bd5b0d5419255d23ca2b3f4b92244c9583
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
