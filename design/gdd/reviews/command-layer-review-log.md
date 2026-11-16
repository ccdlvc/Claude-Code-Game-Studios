# Command Layer — Review Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (4 formulas, 3 upstream + ~15 downstream owners, needs the RefCounted-service ADR)
Specialists: none (lean; systems-designer, qa-lead, game-designer lenses applied in-session)
Blocking items: 3 | Recommended: 8
Summary: The core contract (one P1 dispatcher in seq order, stateless refusals, origin-tagged replay, host cap with sim reserve) is sound, all 8 sections are present, F1–F3 arithmetic checks out and the F4 test vector was verified (SHA-256 matches). It cannot go to implementation because the command vocabulary it claims to own is stale against owner GDDs written since, and because in-flight commands lost at save (sim-origin requests and consumed seqs) break both owner invariants and the R9 replay rule.
Prior verdict resolved: First review
Findings:
- [BLOCKING] MVP command vocabulary: table contradicts owner GDDs and calls rows PROVISIONAL "until the owner GDD exists" though all exist. Skills registers `set_skill_focus` (not `learn_skill`); Guild and buildings uses `build`/`cancel_build` (not `build_building`/`upgrade_building`); Items and loot (26) owns `award_item` (absent; table gives `equip_item` to Member model 8); Golden Boss also registers `set_raid_opt_out`; Retention adds `answer_leave_request` 1601 (table has 1602/1603 only); Enhancement OQ-6 asks to replace `enhance_item(item entity)` with `(member, slot int(1,4), use_ward int(0,1), stop_at int(1,20))`. Downstream Dependencies table misses Items and loot (26).
- [BLOCKING] R8/R15/Edge Cases: only lost *host* orders at save are addressed. Sim-origin requests queued between ticks are also dropped (Sim core R14 does not save the queue). Schools evaluates `join_due` only on level-up/arrival, so a save between the `join_school` request and P1 leaves the member unaffiliated permanently; it also breaks Local save AC-18 save/load equivalence. Needs a rule: owners keep their pending intent in saved state and re-request on load, or the core saves sim-origin queue entries.
- [BLOCKING] R9: replay by contiguous `seq` ("stops at the first that does not") stalls or diverges after a save/load, because `next_command_seq` is restored (Sim core R14) while the dropped queued commands consumed seqs that never reach the log. State how the log marks a session boundary / seq gap and how the driver resumes.
- [RECOMMENDED] R12: `submit_batch` is all-or-nothing only against the host cap; a core refusal (queue full) part-way would queue half a batch. Pre-check core room or define the rollback.
- [RECOMMENDED] AC-1: expects `submit` to return `[0, bad_arg]`, but R8 says the facade only returns 1, 2, 10, 11.
- [RECOMMENDED] AC-11: accepts either `[0, …]` or a P1 `origin_not_allowed`; pick one (or pre-check origin/dev_only in the facade, which is as cheap as arity).
- [RECOMMENDED] Acceptance Criteria: AC-18 uses "1,000 random host commands" without a fixed seed (determinism rule); AC-14 "only the owners' declared requests" is not measurable — give the expected count from the stub fixture.
- [RECOMMENDED] Vocabulary/R2: `order_member` target "entity or uid" and `buy_item`/`sell_item` "content or entity" are impossible under fixed per-slot `arg_kinds`; split into types or fix one kind.
- [RECOMMENDED] R7: Event bus `register_type` also needs `field_count` and `subject_slot`; state them for 501/502.
- [RECOMMENDED] States: `Disposed` says dispatch is "not registered with a live core", but Sim core R4 has no unregistration; define dispatch-after-dispose (e.g. ctx.fail) or require dispose only with the core.
- [RECOMMENDED] Dependencies: Data layer GDD does not mention this layer (uid-exists lookup, `host_pending_max` key, OQ-6); Retention lists raw `ctx.submit` as its interface instead of `commands.request` (OQ-4 forgery risk).
- [NICE] Test block `type_id 100–199` is Sim core's (system 1) block; R9 says the log stores "every applied envelope" though the core logs every drained one, refused included.
Registry: searched host_pending_max, cmd_args_max, command_layer_event_type_block, command_type_id_block_rule, command_queue_max, command_drain_max, schools_event_type_block — no conflicts.
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/schools-and-school-change.md b468deba3ea43b60bb05cee1b5ae8ce989637c3c
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/gdd/equipment-enhancement.md f34423bdf934dfc4fe6e0b7df0e00fe853e4b331
Reviewed-Content-Hash: design/gdd/retention-leaving-and-negotiation.md 91d46c4b4dbdcd99a429121e589d1a9330d2da8c
Reviewed-Content-Hash: design/gdd/skills.md 5ccd62bd5b0d5419255d23ca2b3f4b92244c9583
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/data-layer-and-content-pipeline.md c3f4acefb5084f8b639f485e3d9714219f496da8
