# Sim Core and Tick Loop — Review Log

## Review — 2026-11-16 — Verdict: MAJOR REVISION NEEDED
Review mode: full · Workflow: full
Scope signal: XL
Specialists: game-designer, systems-designer, qa-lead, godot-specialist, performance-analyst, creative-director (senior)
Blocking items: 9 | Recommended: 8
Summary: The loop, phase order and registry are sound. However, the central guarantee ("one guild" across live play, offline time and server replay) was false for any session with a hitch, because the frame-timing-dependent hand-off and `skip_ticks`/`credit_us` were not logged, and the Player Fantasy contradicted R16. R10's failure model assumed exceptions GDScript does not have, and the state machine contradicted itself in three places. Revised in the same session. Decisions: T = 300 s (provisional), hand-offs logged with an unranked fallback, timers as deadline ticks, autosave bound required of Local save.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Core Rules R8/R6: hand-off device-dependent and unlogged; skip_ticks/credit_us break server replay
- [BLOCKING] Player Fantasy: "same core, same phase order" offline contradicts R16 aggregate resolver
- [BLOCKING] Edge Cases: credit_us can push acc_us above T_us; skip_ticks timer model (modulo vs deadline) unspecified
- [BLOCKING] Core Rules R10: assumes exceptions; GDScript runtime errors log and continue
- [BLOCKING] Core Rules R1/R6/R7, F5: uint64 unrepresentable; JSON >2^53 precision; elapsed_us source undefined; encode_u32 little-endian
- [BLOCKING] States and Transitions: Booting→Failed on Data Failed vs R11; Failed→Unloaded vs terminal; late register outside Ready unspecified
- [BLOCKING] Edge Cases R10: no autosave bound, so lost progress is unbounded
- [BLOCKING] Formulas F2/F3/F6, Tuning Knobs: "> c_tick_max ⇒ below real time" wrong; alpha int division and unclamped; recovery ignores inflow; dead T<tick_us check
- [BLOCKING] Acceptance Criteria: AC-1 expects 25 rejected (it divides 1e6); missing [PENDING] tags; R15 and warn-once untested; AC-3 import scan
- [RECOMMENDED] Edge Cases: event_buffer_hard_cap 100,000 → 10,000, stays fatal; P6 history ring buffer
- [RECOMMENDED] Open Questions: command log unbounded (~10-20 MB/day), checkpoint-and-truncate (Leaderboards 35)
- [RECOMMENDED] Core Rules R8/R6: expose catching_up/debt_us; command_rejected event
- [RECOMMENDED] Core Rules R9: carried debt survives pause; reword
- [RECOMMENDED] Formulas F2: range wording vs strict > test
- [RECOMMENDED] Core Rules R4/R15: RefCounted core + read-only facade; reject lambdas; pause main-thread only
- [RECOMMENDED] Acceptance Criteria: split overloaded ACs; float tolerance; T_us equality boundary; Python-only tags
- [RECOMMENDED] Formulas F6: measure p95/p99 at 30 fps too
Revision applied (same session): all 9 blocking items. Recommended items applied: event cap, catching_up/debt_us, R9, F2 ranges, RefCounted/facade/lambda/main-thread rules, AC splits, p95/p99. Deferred to an OQ: command log size and history ring buffer (OQ-10). Not applied: the command_rejected event (the Command layer (5) owns it).
Note: the target GDD is deliberately not hash-stamped. The verdict applies to the pre-revision text, which had no snapshot, and the revised text has not been reviewed, so the next run must be a full re-review.
Reviewed-Content-Hash: design/registry/entities.yaml 41c2729967fb5930b31ceaf8d5427da61ce8e0c8
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f

## Review — 2026-11-16 (second) — Verdict: MAJOR REVISION NEEDED
Review mode: full · Workflow: full
Scope signal: XL
Specialists: game-designer, systems-designer, qa-lead, godot-specialist, performance-analyst, creative-director (senior)
Blocking items: 10 | Recommended: 8
Summary: The first revision closed all 9 prior blockers. It also introduced new contract-level contradictions in the hand-off and timing core. The pending hand-off was unmodelled and could overflow, the monotonic clock likely drops suspended time, tick numbering was inconsistent, Ready/run_ticks contradicted itself, and recovery re-ran the failing tick. On top of that, the performance assumption behind T=300 s was unvalidated and many ACs were wrong or untestable. Revised in the same session. Decisions: T = 60 s provisional; one hand-off in flight with a 30 s pending timeout (late time accrues in acc_us, because the CD's merge-into-gap variant is infeasible since the resolver already ran); the resume gap comes from UTC only; quarantine plus an older backup.
Prior verdict resolved: Yes (all 9 prior blockers closed; new defects found)
Findings:
- [BLOCKING] Formulas F2 / Edge Cases: the pending hand-off was absent from F2, the States table and R13; it contradicted Edge Cases; acc_us was unbounded (int64 wrap)
- [BLOCKING] Core Rules R7/R8: Time.get_ticks_usec likely excludes device suspend; no single absence rule; risk of double or zero counting with the UTC gap
- [BLOCKING] Core Rules R1/R10, AC-10/21/36: tick numbering inconsistent
- [BLOCKING] States and Transitions: Ready/run_ticks contradiction; no seal trigger; fatal triggers outside ticks missing
- [BLOCKING] Core Rules R10, UI: recovery re-ran the failing tick deterministically (soft-lock); lost orders unstated
- [BLOCKING] Core Rules R5: await/call_deferred escape the tick; ctx calls after a fail unspecified
- [BLOCKING] Core Rules R5, AC-31b: reschedule rule ambiguous (tick+interval vs grid)
- [BLOCKING] Formulas F6, Tuning Knobs: 0.5 ms/tick unvalidated; time-slicing optional; no instrumentation or per-phase budgets; event cap 10,000 too high
- [BLOCKING] Acceptance Criteria: AC-30 M≥50; AC-25 not executable; AC-34 no pass/fail; AC-23 vs AC-3; AC-37/38 unobservable or vacuous; AC-11 vs Edge Cases; AC-29 restore API and 2^53 seed
- [BLOCKING] Acceptance Criteria AC-3: lint list incomplete (assert, await, RNG family, I/O, class_name) and substring false positives
- [RECOMMENDED] Core Rules R8: hand-off tests total debt (hitch cliff) — documented as accepted to keep timeline order
- [RECOMMENDED] Tuning Knobs: lowering M vs drain time unreconciled
- [RECOMMENDED] Core Rules R6: P1 drain cap; buffered history I/O (Event bus 42)
- [RECOMMENDED] Core Rules R9: SceneTree.paused debt; pause-then-quit exploit (OQ-11, Offline 31)
- [RECOMMENDED] Player Fantasy: "same results" reworded; resolver_version logged
- [RECOMMENDED] Core Rules: silent-corruption backstop; central handler-order registry
- [RECOMMENDED] Acceptance Criteria: split bundled ACs; missing ACs (chained hand-off, interleaved instances, zero handlers)
- [RECOMMENDED] Implementation (ADR): is_standard callables, dispose(), facade leaks, GDScript notation, 4.7 typed-return overrides
Revision applied (same session): all 10 blocking items. Recommended items applied: drain cap, SceneTree pause, Player Fantasy rewording and resolver_version, dispose(), notation note, missing ACs (AC-16b, 23b, 29b, 39–44). Documented, not changed: the hitch cliff. Deferred to an OQ: pause-then-quit (OQ-11), clock verification (OQ-12). Not applied: P6 invariant hook and central order registry (OQ-5 remains), history I/O (Event bus 42).
Note: the target GDD is deliberately not hash-stamped, because the revised text has not been reviewed. The next run must be a full re-review.
Reviewed-Content-Hash: design/registry/entities.yaml 4844b9835acd9aaf2b7c2206868675254227ddb4
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f

## Review — 2026-11-16 (third) — Verdict: MAJOR REVISION NEEDED
Review mode: full · Workflow: full
Scope signal: XL (L after the recommended scope cut)
Specialists: game-designer, systems-designer, qa-lead, godot-specialist, performance-analyst, creative-director (senior)
Blocking items: 11 | Recommended: 11
Summary: The core loop (integer state, phases, registration, determinism, command queue) is sound. The contracts layered on it (pending hand-off lifecycle, quarantine, timers across a skip, autosave trust) turn legitimate play into fatal screens, and the seed width contradicts the RNG GDD. The CD recommends narrowing scope: keep a minimal gap_us/skip_ticks primitive in the core and move resolver, timer re-anchoring, quarantine and recovery policy to Offline progress (31), Local save (6) and Leaderboards (35).
Prior verdict resolved: Yes (prior 10 blockers addressed; new contract-level defects found)
Findings:
- [BLOCKING] Core Rules R8/F2: pending-hand-off timeout is fatal for a legitimate absence or a resolver slower than 30 s; no handoff_pending on facade
- [BLOCKING] Core Rules R5 / Edge Cases: no timer rule after skip; overdue burst can exceed fatal event cap; double-count with Offline backlog
- [BLOCKING] Core Rules R9 / F2: Paused advance discards elapsed_us, so a cold-start absence while Paused is deleted; conservation exceptions unstated
- [BLOCKING] Core Rules R13/R14: world_seed int64 contradicts RNG R2 uint64
- [BLOCKING] Core Rules R10: GDScript sink does not unwind (fall-through); Callable wrong arity silently skips handler
- [BLOCKING] Core Rules R17 / Tuning Knobs: time-slice granularity is M ticks; drain arithmetic ignores slice share and inflow; AC-34 2 s target forces T below H
- [BLOCKING] Core Rules R10 / F2: quarantine gap from untrusted marker can overflow or be 0
- [BLOCKING] Formulas F2: "T_us ≥ tick_us, no check needed" wrong (tick_rate 1, T 1 s hands off every tick)
- [BLOCKING] Edge Cases (Commands): per-refusal command_dropped events can hit the fatal event cap
- [BLOCKING] Player Fantasy: "results identical" on a slow device contradicts the Numbers edge case
- [BLOCKING] Acceptance Criteria: no API surface; AC-3 contradicts R3 and is vacuous; core fail codes undefined; AC-37 replay API missing; AC-34 cannot fail and its gate contradicts standards; AC-21/31b/16b defects; missing PENDING tags
- [RECOMMENDED] Core Rules R17: profiler overhead target, bounded store
- [RECOMMENDED] Open Questions OQ-10: P6 history memory bound and owner
- [RECOMMENDED] Core Rules R5/R6: derive allocation, command_drain_max 20-30, batched P6, suppress presentation while catching up
- [RECOMMENDED] Core Rules R6: command-log replay order key; handoff without skip
- [RECOMMENDED] Core Rules R14/R9: snapshot while catching_up drops debt; pause mid-advance; run_ticks after quarantine start
- [RECOMMENDED] Edge Cases: chained hand-off at T=30 s; livelock when T ≤ resolver latency
- [RECOMMENDED] Core Rules R7/R13: float rules, utc_s flooring, FOCUS_OUT vs PAUSED, PROCESS_MODE_ALWAYS (APIs UNVERIFIED)
- [RECOMMENDED] Player Fantasy / UI: stale-view commands in catch-up; hourly tick vs wall time; away summary event; command_dropped UI
- [RECOMMENDED] Formulas F6: unify the three half-frame constants
- [RECOMMENDED] Acceptance Criteria: Python-only ACs have no runner
- [RECOMMENDED] Acceptance Criteria: ~29 qa-lead rewrites (split bundled, vacuous assertions, facade allow-list, coverage gaps)
Revision applied (same session): all 11 blocking items. Decisions: narrow scope (no pending timeout; quarantine/recovery → Local save 6; timer re-anchoring and resolver tolerance → Offline progress 31; replay driver → Leaderboards 35); 63-bit world_seed (RNG R2 change pending, OQ-13); paused time is owed; honest Player Fantasy with min-spec; catch-up budget B = 10 s sets T. Recommended items applied: profiler null-check and overhead target, history memory (OQ-10), command_drain_max 100→25, log order key and time entries without seq, snapshot debt note, pause mid-advance, chaining/livelock, GDScript notes (OQ-14), catch-up UX, single half-frame constant, test runners, most qa-lead AC rewrites. Registry: handoff_timeout_s deprecated, command_drain_max 25, advance_catchup gains max_ticks. Not applied: P6 batching and derive budget (deferred to Event bus 42 and feature GDDs via OQ-3/OQ-6).
Note: the receipt above stamps the pre-revision text, so the next run sees the target CHANGED and must do a full re-review.
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md d8d69976bc3bf0577a81f4ab9dfd8fbd0b4f8346
Reviewed-Content-Hash: design/registry/entities.yaml 4844b9835acd9aaf2b7c2206868675254227ddb4
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: design/gdd/data-layer-and-content-pipeline.md 1ed2be6c9dfe31e8fd4eb98237636053570cddd1
Reviewed-Content-Hash: design/gdd/dev-tooling-and-parity-harness.md c200df0720461b76ce29a2080e24572b30c3bd76
