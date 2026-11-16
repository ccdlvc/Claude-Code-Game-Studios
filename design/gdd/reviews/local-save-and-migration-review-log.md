# Review Log — Local Save and Migration

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning)
Specialists: none (lean mode; systems-designer, qa-lead and cross-GDD lenses applied in-session)
Blocking items: 5 | Recommended: 10
Summary: Structurally complete (8/8 sections, registry values agree: SAVE_SCHEMA_VERSION 1, autosave 60 s, 3 backups, 32 MiB cap, history_bytes_max 736,000), and the atomic-write and migration contract is strong. But the generation rule breaks both recovery paths that load something other than the newest file (crash-loop "Load an older save" and cloud import), R6 forbids a cross-feature call that XP R9 and R14 depend on, and the save contract no longer matches the now-designed Account and cloud save (7) and Leaderboards (35) GDDs it still marks PROVISIONAL.
Prior verdict resolved: First review
Findings:
- [BLOCKING] R18 / R19 / R10 step 3: after "Load an older save" (ckpt gen 20 while sav/bak hold 40+), the next write gets generation last_written + 1 (21), so R10 step 3 sees sav gen 41 ≠ 20 and fails 6108; if it did commit, the next boot's F2 picks bak1 gen 41 (the crashing state) again. import_blob sets gen max+1 but hits the same step-3 check. Define generation = max on disk + 1 and the step-3 baseline for these paths; AC-33 must cover the next boot
- [BLOCKING] R6 vs XP R9 / R14: R6 says restore may not call another feature, but XP R9 has Member model call init_progress on load, and R14's "lowering a limit" rule relies on that 2202 refusal surfacing as 6009. Either allow restore to call stateless validators (content/curve) or move the check into check()
- [BLOCKING] R19 / OQ-7 vs account-and-cloud-save.md R5, R8, R9, OQ-1: summary fields differ (7 wants guild_uid, guild name, highest member level, rebirth count; 6 offers sum of levels and total gold); 7 calls store_kept_backup(label), write_current_from_blob and a "save completed" signal that 6 does not define; 6 keeps one slot0.replaced.sav while 7 keeps the losing guild as a backup; and R11 step 4 / Edge Cases lock the local slot on a newer cloud blob, whereas 7 R9 leaves local play and saving untouched (a lock would stop local saving)
- [BLOCKING] R13 vs leaderboards-and-anti-cheat.md R5, OQ-3: Leaderboards closes segments on a lineage change of phase_table_hash or resolver_version, but lineage records only sim_version, content_hash, schema_version; the canonical sim-state digest Leaderboards OQ-3 asks of this GDD is not addressed
- [BLOCKING] F4 / R10 (cloud): F4 omits the ranked_log section (ranked_log_max_entries 100,000) and assumes 3–5× gzip on base64-packed int64 data; its 0.3–4 MB file range exceeds Account's cloud_blob_max_bytes (2 MiB) with no rule or AC that keeps the file under it
- [RECOMMENDED] R10 step 3: reads "the generation in the header", but generation is a payload field, not in the R2 header; either add it to the header or say the payload is decoded
- [RECOMMENDED] R11 step 7 vs R13: step 7 appends lineage on sim_version/content_hash change only; R13 also names schema_version
- [RECOMMENDED] R12 / F2: "valid … for the same save_id" is circular (whose save_id?); tie order "sav < tmp < …" does not say which wins; state whether the R15 lock is judged on the highest candidate passing steps 1–3
- [RECOMMENDED] F3: the ~61 s bound does not hold while autosave is deferred (catching_up) or after repeated 6103/6106; state the bound's conditions in Player Fantasy
- [RECOMMENDED] F4: 245,334 × 4 = 981,336, not 981,334
- [RECOMMENDED] R6: register_section signature lacks the optional summary() R19 relies on
- [RECOMMENDED] R15: "never deletes" vs save_damaged_keep deleting oldest damaged files; reconcile wording
- [RECOMMENDED] Acceptance Criteria: no AC for 6105, 6006, 6012, 6013, save_damaged_keep, crash marker reset/no-older-checkpoint case, schema-only lineage append; AC-2 accepts "6003 or 6004" (pin each case); AC-25 "peak memory below 2× file size" needs a measurement method
- [RECOMMENDED] Dependencies / OQ-3, OQ-7, OQ-8, OQ-9: Account (7), Leaderboards (35), Member model (8) and Guild screens (39) GDDs now exist; the PROVISIONAL labels and bidirectional check are stale
- [RECOMMENDED] Edge Cases: line 343 (candidates with differing save_id, highest wins) contradicts R12's same-save_id validity rule
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/account-and-cloud-save.md 1d2ee76c49defdfb7cc8aae45a3b1ecb6e18403c
Reviewed-Content-Hash: design/gdd/leaderboards-and-anti-cheat.md 36124b2475f1e23092510a18f6f1bb4d92a0ae06
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/xp-and-level-pacing-curve.md 8b013cb956e1ab238db7f78e811a78b4e397e7fb
