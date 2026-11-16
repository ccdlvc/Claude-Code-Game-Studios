# Review Log — Data Layer and Content Pipeline

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (4 integrity formulas, ~20 hard dependents, runtime-format ADR pending — producer should verify)
Specialists: none (lean mode; lenses applied in the main session)
Blocking items: 3 | Recommended: 6
Summary: Complete (8/8 sections), tightly specified and consistent with the registry (content_hash, content_live, content_id_none = 0, stable_id_max_length = 48 all match). The blocking problems are all in the uid-immutability contract that Deterministic RNG, saves and leaderboard replay rest on: the HEAD-only history check and max-based allocator can reuse or silently change uids, and parameter tables cannot be typed under R4. Several statements (no downstream GDDs exist, engine not chosen, leaderboard buckets by hash) are stale against the now-complete GDD set.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Formulas F4 / R6: next_uid = 1 + max over HEAD and working copy is not append-only. Delete the highest-uid row and commit; the next helper run hands that uid out again, breaking "never freed" and RNG R5. Same root: the R6 "pair changed vs HEAD" check is vacuous once a change is committed (in CI the working copy is HEAD), so a committed uid change passes. Needs a persisted high-water mark / uid ledger and a comparison base that is not HEAD (merge-base with main, or the ledger).
- [BLOCKING] Core Rules R4 / R2: config and sim_params are key,value tables with one untyped `value` column, yet R4 requires every column typed at load with no later re-parsing, and approved additions put `_ppm`, bool and list values there (elder_trait_share_ppm, party_xp_mult_ppm, elder_trait_categories, academy_gate_enabled). Specify a per-key schema (key -> type, range, default, ppm-or-not) and the validator rules for missing/unknown keys.
- [BLOCKING] Core Rules R2/R6 (drop_tables): the row key `table_id` is shared by every row of a group, so (row key, uid) does not identify a drop row; a changed uid inside a group reads as delete + add (WARN only) instead of the R6 ERROR. Drop rows (the table whose uid order drives loot RNG, RNG F5) need a per-row identity (e.g. table_id + item ref, or uid-ledger by row).
- [RECOMMENDED] Dependencies: "None of these has a GDD yet, apart from Deterministic RNG" and the systems-index consistency note are stale — all listed GDDs exist and the index rows now name Data layer. Downstream table also omits newer consumers (Entitlement feature_flags, Quests achievements, NPC guilds, IAP, Onboarding, Analytics, Gold economy, Command layer, Utility AI, Arena, Endless tower, Settings, Offline progress).
- [RECOMMENDED] Tuning Knobs (live_wave row): "every leaderboard bucket keyed by that hash" contradicts Leaderboards R7.3 (boards are not split by content_hash; Leaderboards OQ-9 already flags it).
- [RECOMMENDED] Quick reference / OQ-6 / AC-22: says the engine is not chosen, but project.yaml pins Godot 4.7 GDScript. Re-source feasibility against Godot (correctly-rounded decimal parsing in String.to_float is the named risk) and restate AC-22's unblock condition.
- [RECOMMENDED] R7 / F1: content_hash covers host-only data (UI, push, ads, settings keys in config.csv; proposed analytics_events, iap_products, onboarding_steps). Every non-sim tweak then appends a save lineage entry and closes a leaderboard segment. Either split a sim-content hash from host data or state this is intended.
- [RECOMMENDED] Approved schema additions: the 7 new tables are not classified (content vs parameter, wave, uid, included in F1). "19" is hard-coded in R2, F1, States, AC-1 and Dev tooling AC-22 — define the count as "the R2 inventory".
- [RECOMMENDED] Header: Status "In Design" disagrees with systems-index "Designed".
Reviewed-Content-Hash: design/gdd/data-layer-and-content-pipeline.md c3f4acefb5084f8b639f485e3d9714219f496da8
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/gdd/leaderboards-and-anti-cheat.md 36124b2475f1e23092510a18f6f1bb4d92a0ae06
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/dev-tooling-and-parity-harness.md c200df0720461b76ce29a2080e24572b30c3bd76
Reviewed-Content-Hash: design/gdd/entitlement-and-feature-flags.md e988772d3723b158efa58a36578ef586a578bf44
