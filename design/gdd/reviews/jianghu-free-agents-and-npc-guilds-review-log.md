# Review Log — Jianghu Free Agents and NPC Guilds

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning)
Specialists: none (lean; game-designer, systems-designer, qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 9
Summary: Complete (8/8 sections), formulas verified (F2, F3, F5, F7, F8 examples and AC values all recompute correctly) and registry values agree. Blocking problems are at the seams: the Arena GDD now exists and expects a different API and power scale; the Member model's `create_member` spec cannot carry what R10 keeps; R7's lineup filter makes the headline fantasy (the ex-member at the Lôi Đài) rare; and the invite transaction contradicts the all-or-nothing applier rule.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Interactions / R7 / OQ-1: Arena (arena.md, Designed) consumes `npc_guilds()` and `arena_lineup(guild_id)` returning `{school_id, level, power_milli (~500–2000), former_member_id}`, calls `add_prestige(...)` (Arena OQ-4) and expects ≥3 guilds live; this GDD exposes `npc_lineup(uid)` with `ca` 0–200, `npc_guilds_view()`, `npc_record_result(uid, fame_delta)`, no prestige, and still calls Arena "not designed". Reconcile names, scale, write API and prestige ownership in one place.
- [BLOCKING] R10 / AC-16 / AC-18: Member model R8 `create_member(spec)` carries name, origin, pa, traits, school, level, rebirth, original ID only — not `skills[]` (lv, xp), `pa_exact`, trait reveals or contract salary, and step 3 has owners *initialise* fields. R10's "kept" fields have no path; add them to Member model R8 (bidirectional) or define a restore hook per owner.
- [BLOCKING] R7 vs Player Fantasy: signed agents appear only if `ca > power`; power tracks the player's top-5 CA mean × strength (≥ it for strength ≥ 1.0), signing is fame-weighted toward the strongest guilds, and agent CA is frozen while power only rises — so a departed (usually below-top-5) member is mostly absent from lineups (AC-12 drops the CA-50 agent). Reserve a lineup slot for signed ex-members, or otherwise guarantee the "familiar face" moment.
- [BLOCKING] R8 / R10: attempt cost is "paid win or lose" and survives a failed `create_member`, yet R10 is "one P1 applier, all-or-nothing" (Command layer); poach-fee shortfall after a successful die (104) burns the attempt cost and the die. Pre-check `fund ≥ attempt + poach_fee` as a `cannot_afford` refusal and state exactly what commits and what rolls back.
- [RECOMMENDED] F2 Output Range: noise applies while `power < target + overshoot`, so power can reach `target + overshoot + noise_max − 1`; the stated cap is off by up to 2 at safe max.
- [RECOMMENDED] Edge Cases (dismiss-and-rehire): "attempt cost ≥ ask ≥ 10% D" is wrong — offer floor is 50% of ask (≥5% D) and `inv_fee_days` safe range includes 0 (cost 0).
- [RECOMMENDED] R5 vs R11: R5 gives return key `[4, fa_id]`, R11 `[4, fa_id, release_count]`; align.
- [RECOMMENDED] F9 / Edge Cases: `return_tick` uses "day slot tick", undefined for an eviction outside a day slot; offline rule uses undefined `return_tick_live`.
- [RECOMMENDED] R2 step 5: unlist test names `fa_stay_days`; should be the record's own stay (candidates `fa_candidate_days`).
- [RECOMMENDED] F7 notation: `inv_base`, `inv_loyalty_coef`, `reason_pen`, `poach_mult` are fractions, contradicting "all values integers, ppm"; give ppm defaults.
- [RECOMMENDED] F2 ratchet vs Rebirth: non-decreasing power after a rebirth CA drop may leave Arena rivals unreachable for a long time; state the expected recovery time or confirm intent.
- [RECOMMENDED] Acceptance Criteria: no AC for `return_pool_max` discard, `cannot_afford_fee` (104), decline / `not_pending` (105), orphan migration (17002), seeding (R3), or eviction's return draw.
- [RECOMMENDED] OQ-5: `npc_guilds.csv` schema still unapproved; must close before implementation stories.
Reviewed-Content-Hash: design/gdd/jianghu-free-agents-and-npc-guilds.md 9092a7b46bed56bec3486a6bdc7e3fc5c5323fa3
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/arena.md 2ce210ca96466ea7a031e6ad6b6e97b20c5b8d0a
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/retention-leaving-and-negotiation.md 91d46c4b4dbdcd99a429121e589d1a9330d2da8c
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
