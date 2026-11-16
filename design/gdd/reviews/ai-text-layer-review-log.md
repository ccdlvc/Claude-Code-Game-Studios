# Review Log — AI Text Layer (optional local LLM)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (multi-system integration, 7 formulas, new ADR for llama.cpp GDExtension; producer should verify before sprint planning)
Specialists: none spawned (lean); game-designer, systems-designer, narrative-director, qa-lead lenses applied in-session
Blocking items: 5 | Recommended: 10
Summary: Structurally complete (8/8 sections, all dependency GDDs exist) and the core principle (template floor, fact sheet of player-known facts only, output never read by the simulation) is sound and consistent with Localization R10, Sim core R15, Event bus R8, CA/PA R12 and Retention. It fails on interfaces that no longer match the GDDs it depends on (Entitlement, Settings, which it still says do not exist) and on two R5 validation checks that cannot be implemented as written; the job cancel/re-queue lifecycle is stated three ways. Registry values (ai_text_cache_cap_kb 1024, ai_text_max_chars_bio 600) match.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Dependencies / R12 / F2: `feature_ai_text` is read as a field of the entitlement snapshot, but Entitlement R2–R8 make the snapshot a 2-bit `flags` int (premium, exact_pa_all) plus a feature-flag table whose rows have no AI entry ("gói AI" is parked as an open question). Define the AI row (`requires`, `scope: host`) with Entitlement, or read `premium` directly; remove "Entitlement has no GDD" (line 314).
- [BLOCKING] Dependencies / UI Requirements: Settings GDD exists; its R3 key list is closed ("exactly these keys") and has no AI toggle, pack state or download row. The AI row (line 367) and the "both" interface (line 135) have no counterpart; agree the key(s) with Settings and fix the stale "no GDD" claims (lines 306, 314; Free agents also exists and lists this system).
- [BLOCKING] R5 check 3: "every proper name in the output" has no detection rule. Free prose has no name markup, and capitalisation fails for vi (Hán-Việt titles, sentence starts). Specify the mechanism (for example, frame asks the model to emit `{m:id}` tokens and any capitalised token outside the glossary rejects), or the check cannot be built or tested beyond AC-6's toy case.
- [BLOCKING] R5 check 4 / Player Fantasy: rejecting spelled numbers outright rejects the vi indefinite article "một", English "one"/"a third", and ordinals; the fantasy's own example ("the third Golden Boss", "eight hours") would be rejected. Define the number lexicon per locale (cardinals vs ordinals vs articles) and whether ordinals derived from fact-sheet counts are allowed.
- [BLOCKING] R6 / Job states / F4: cancellation is stated three ways (R6 "cancelled and re-queued"; Job states "return to Queued once, then dropped", trigger list garbled — "gate closed, subject left the screen and the queue is over queue_max"; F4 "re-queued next time viewed"). With `idle_s` reset on every touch and 14–27 s jobs (F3), most jobs are cancelled during play; state one lifecycle and a target completion rate, or partial-output reuse.
- [RECOMMENDED] States: "The UI shows `Off`, `Idle`, `Loading` and `Ready` as On" contradicts the Settings state label "Off / On"; `Off` should show as Off.
- [RECOMMENDED] States / F1: Ineligible is entered from "any check of F1", but after install free storage naturally drops below `pack_mb × margin`; say F1 is evaluated only before download (or only the RAM term after).
- [RECOMMENDED] R5 check 7 / Tuning Knobs: `echo_max_ratio` has no default, range or knob row.
- [RECOMMENDED] R4 / AC-20: "same model, frame and facts give the same text" holds only per device/build/thread count (llama.cpp sampling and matmul are not bit-identical across CPUs); scope the reproducibility claim; AC-20 tests the seed only, which is fine.
- [RECOMMENDED] F5: `seed = (… ) mod 2³² + retry_n` can exceed 32 bits; apply mod after adding retry_n.
- [RECOMMENDED] F7 / Account R10: up to 1 MB of cached prose travels in the cloud blob (`cloud_blob_max_bytes` 2 MiB, expected save 100–300 KB); give the compressed estimate or exclude the `ai_text` section from cloud upload.
- [RECOMMENDED] Dependencies: bidirectional gaps — Guild screens (39), Realtime world view (38), Dev tooling (43, AC-17 harness), Settings (45), Account (7, `submit_report`) and Local save (6) do not mention this system; Data layer already lists the `ai_text` save section, so OQ-2 is half-resolved elsewhere.
- [RECOMMENDED] R9 / UI: state whether the report record stores placeholder text or filled names; player-entered member names are user content in the payload (Data safety, OQ-10).
- [RECOMMENDED] R2 table vs AC-3: the `bio` fact sheet lists no PA, but AC-3 allows "the displayed estimate bounds"; align (include or exclude PA).
- [RECOMMENDED] AC-19: "no frame over 16.6 ms attributable to the layer" needs a method (A/B trace with pack on/off, or worker-thread markers); also note F2 normally keeps the worker idle during active play.
Reviewed-Content-Hash: design/gdd/ai-text-layer.md 7fb82e64228d84f29c309f6081e141a1d1de5cf0
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/entitlement-and-feature-flags.md e988772d3723b158efa58a36578ef586a578bf44
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/gdd/jianghu-free-agents-and-npc-guilds.md 9092a7b46bed56bec3486a6bdc7e3fc5c5323fa3
Reviewed-Content-Hash: design/gdd/account-and-cloud-save.md 1d2ee76c49defdfb7cc8aae45a3b1ecb6e18403c
Reviewed-Content-Hash: design/gdd/dev-tooling-and-parity-harness.md c200df0720461b76ce29a2080e24572b30c3bd76
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/gdd/realtime-world-view.md 7cd31abd632c70b6504f7a25d90fce0a7647d306
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/gdd/data-layer-and-content-pipeline.md c3f4acefb5084f8b639f485e3d9714219f496da8
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/localization.md 4f526afa5088f0dc117a1a76231ef2a6d3829a56
Reviewed-Content-Hash: design/gdd/retention-leaving-and-negotiation.md 91d46c4b4dbdcd99a429121e589d1a9330d2da8c
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/ca-pa-and-traits.md 6f94b9f89498c0384ce2e725fc215b4349c0a346
