# Review Log — Dev Tooling and Parity Harness

## Review — 2026-11-16 — Verdict: MAJOR REVISION NEEDED
Review mode: full · Workflow: full
Scope signal: L
Specialists: game-designer, systems-designer, qa-lead, economy-designer, devops-engineer, creative-director (senior)
Blocking items: 10 | Recommended: 6
Summary: Structural, not wording. Promise 2 is defeatable (behaviour change + `parity.py gen` without a sim_version bump passes R7), the exit-code contract cannot survive `make`, ~a dozen ACs are unbuildable without fixture injection, and the balance budget covers pacing but not the §4.4/§19.5 economy. Needs new mechanisms: merge-base check, `tools/gate.py` driver, `--root`, invariant + budget-stale rows. Note: the doc was edited on disk mid-review (RNG R3→R4); hashes below are of the post-edit copy.
Prior verdict resolved: First review
Findings:
- [BLOCKING] R7/F4: no base-branch comparison; regenerating vectors without a bump passes; R6 claim false
- [BLOCKING] F4/States: per-file verdict makes unchanged groups Orphaned on a legit bump; Stale overlaps Orphaned
- [BLOCKING] R3/F2: make collapses exit codes to 2 and stops at first failure; argparse 2 collides with NOT ASSESSED; F2 returns 0 for N=0
- [BLOCKING] R4/AC: no fixture injection (`--root`); AC-2, AC-4, AC-14–18, AC-29, AC-33/35 unbuildable
- [BLOCKING] R13/Edge Cases: uid baseline HEAD/depth-2 wrong (merge queue, multi-commit push); first commit / no HEAD exits 2 forever
- [BLOCKING] F3: ambiguous signed/unsigned range, mod vs ERROR contradiction, no type tag, no u32/bool/string/null encoding
- [BLOCKING] F1/R9: NaN/inf unhandled; no metric-kind column; no economy families (§4.4, §19.5, §20 S3/S5); no invariant rows
- [BLOCKING] F1/R9/R10: circular bands from first-run output, seed variance ignored, scenarios have no declared home, no budget sim_version / stale verdict
- [BLOCKING] R8/F5: no event registry, domains not (event,domain) pairs, hard-coded 1–18
- [BLOCKING] Acceptance Criteria: AC-6 vs AC-25 conflict; AC-36 needs nonexistent reload tool/build; AC-38 manual; uncovered R3 crash, R6, R11, R12, F2 N=0, F5 empty, negative i64
- [RECOMMENDED] Tuning Knobs: vector_draws_per_event=16 misses late reorders; hash full sequence
- [RECOMMENDED] F6/R2/R4: limits sum 95 not 90; knob ranges inconsistent; wall-clock ban vs timing WARN (rule: advisory telemetry)
- [RECOMMENDED] R13/R12/OQ-4: ci_fetch_depth dual source; -I vs unittest; Makefile order and .NOTPARALLEL; --force undefined for untracked/no git
- [RECOMMENDED] R9/AC-29: quick tier unrepresentative; single mutation; `*_hours` cumulative vs stage; no rebirth/wave rule
- [RECOMMENDED] Acceptance Criteria: hard-coded 19 tables, pinned "0 lỗi", nonexistent tests/unit/tooling paths
- [RECOMMENDED] Dependencies: Localization (Vertical Slice) missing i18n would fail the MVP gate
Reviewed-Content-Hash: design/gdd/dev-tooling-and-parity-harness.md 1a19029b1b60363b6909d90cf39e127140864875
Reviewed-Content-Hash: design/registry/entities.yaml a3170643639257847998375d8e2c54dbb4e4ad7b
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/deterministic-rng.md 3b4df44f912ebdde679fddd680123b698722af24
Reviewed-Content-Hash: design/gdd/data-layer-and-content-pipeline.md 1ed2be6c9dfe31e8fd4eb98237636053570cddd1
Reviewed-Content-Hash: JX1_Tycoon_GDD.md 8a751aeb1425527ef8cfc819b1034f0621587a7d
Reviewed-Content-Hash: GODOT_PORT.md 7b123e019cbb3d5b636301e6d11ff468a5d23983
