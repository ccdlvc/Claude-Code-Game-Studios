# Sim Core and Tick Loop

> **Status**: In Review — revised three times on 2026-11-16 after /design-review (MAJOR REVISION NEEDED each time). The third revision narrowed scope: hand-off policy, quarantine and timer re-anchoring moved to their owners. Awaiting re-review
> **Author**: user + Claude
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet)

## Summary

The Sim core is the fixed 10-ticks-per-second loop that runs the whole guild in six ordered phases, owns the command queue, the event buffer, the injected game clock and the single `sim_version` integer, and contains no game rules. Players never see it; they feel a guild that obeys the next tick's orders and keeps living, by the same rules, while the app is closed. It exists so one deterministic core can serve live play, offline catch-up, the balance simulator and server-side leaderboard replay.

> **Quick reference** — Layer: `Core` · Priority: `MVP` · Key deps: `Deterministic RNG, Data layer and content pipeline`

## Overview

The Sim core is the headless engine room of JX1 Tycoon: a fixed-timestep loop that advances the whole guild simulation at 10 ticks per second (`config.tick_rate`), always in the same six-phase order (GDD §3.4): receive commands, update member states, run combat and hunting, settle drops, trade, tax and production, fire timed events, then publish events to the presentation layer and the history log. It owns three things and nothing more. First, the **tick**: the loop, the phase order, and the rule that feature systems register work into a phase and never call each other or the core. Second, the **injected game clock**: the core never reads the machine clock; its host tells it how much time has passed, which is what lets the same core run live, fast-forward offline, run inside the balance simulator and replay a leaderboard submission on a server. Third, **`sim_version`**, the single integer that names the behaviour of the whole core so saves, golden vectors and the leaderboard verifier can say which rules produced a result. It starts only when the Data layer reports `Ready`, hands every phase the RNG's `derive(domain, key)` without ever drawing itself, and supplies the engine-port fatal sink that discards a failed step. The core contains no game rules: it does not know what a member, a gold coin or a boss is. It is deliberately thin, so that it cannot become a god object and so that a Python reference core and a GDScript port can be proven identical tick for tick.

## Player Fantasy

**Type: indirect.** The player never sees the tick loop. They feel that the guild is a living place that obeys them and keeps living without them. No game pillars exist yet, so this section anchors to the GDD's locked decisions (§3.2, §10) instead of quoting a pillar.

**"The bang chủ decides, the guild acts — and the guild keeps living when I look away."**

*The moment:* the player taps a member and orders them to the infirmary. On the very next tick the member turns around and walks there; no other member's day is disturbed, and the order does not jump the queue ahead of a boss that was already firing. Later the player closes the app, and on return the guild's day has simply continued: the same hunting, the same upkeep, the same hourly Golden Boss, not a different, softer game running in the background.

*The guarantee behind it:* the guild on a phone, the guild fast-forwarded overnight and the guild a leaderboard server replays are one guild, because one core, one clock rule and one logged record of every input drive all three. The same seed, content and logged inputs always replay to the same results. A stretch of time that ran tick by tick is exact. A stretch handed to Offline progress's aggregate resolver is a different algorithm, bounded by that system's stated tolerance, and it replays identically because the hand-off and the resolver's version are logged inputs (R8). "One guild" therefore means one replayable record and one set of rules for live time, plus a tolerance-bounded resolver for long absences, not bit-identical results across both paths. A rank on the board means something because no device ticks differently from another. Exact live time is guaranteed on supported hardware (the min-spec device the P1 spike names, OQ-6). A device below that spec that falls more than `offline_threshold_s` behind in the foreground hands the excess to the same resolver, logged like any other gap.

**What this asks of the rest of the design**
- A command always takes effect at a defined point in a defined tick (Phase 1), never mid-phase. Players must be able to rely on "next tick".
- Time that passes while the app is closed obeys the same rules and timers as live play and reaches the core only through the injected clock and a logged hand-off. Gaps up to `offline_threshold_s` (60 s, provisional until the P1 spike measures tick cost) are re-run as exact ticks. Longer ones go to Offline progress's aggregate resolver (GDD §10), a different algorithm that must stay within its stated tolerance and is replayable because the hand-off is logged (R8). There is no "away mode" with its own rules.
- The core never speeds up, skips or reorders phases to hide slowness. A supported device that hitches catches up with exact ticks and identical results. Only a device below min-spec, falling more than `offline_threshold_s` behind, reaches the resolver (R8, F6).
- World time never stops. An in-app pause defers ticks but still owes the time (R9), so the hourly Golden Boss stays on the wall clock.

*Lens applied:* creative direction (`references/lens-creative-director.md`). Three framings were considered (guild lives on, bang chủ decides, same guild everywhere). Guided mode took the first two as the lead and the third as the guarantee; change by editing this section.

## Detailed Design

### Core Rules

**R1 — One fixed timestep.** The simulation advances in whole ticks. `tick_us = 1,000,000 / tick_rate` microseconds, with `tick_rate` read from `config` (10 today, so 100,000 µs). `tick_rate` must divide 1,000,000 exactly; the Data layer validator rejects any other value. Simulation time is the integer tick counter `tick` (non-negative int64, starts at 0; GDScript has no unsigned integers, so every core counter is a signed 64-bit integer that never goes negative). No rule anywhere in the simulation reads a machine clock or a frame delta. "N seconds of game time" always means `N × tick_rate` ticks.

**Tick numbering.** "Tick N" is the tick that executes while the counter `tick` equals N. Handlers read N through the context. When tick N commits (after P6), `tick` becomes N + 1. The first tick of a fresh core is tick 0, and after one tick `tick` is 1. A failed tick N leaves `tick` at N (R10). Outside a tick, `tick` is the number of committed ticks. Every rule and criterion in this GDD uses this convention.

**R2 — Six phases, fixed order.** Each tick runs these phases in this order (GDD §3.4). The order never changes at runtime, and a change to it is a `sim_version` bump (R12).

| # | Phase | GDD §3.4 step | What runs here |
|---|---|---|---|
| P1 | `commands` | 1 | The core drains the command queue (R6), then registered validators and appliers run |
| P2 | `members` | 2 | Member state machine transitions and AI decisions |
| P3 | `field` | 3 | Combat, hunting, party movement, on-screen and aggregate zone results |
| P4 | `economy` | 4 | Drops, trade, tax, upkeep, building output |
| P5 | `timers` | 5 | Time-driven events: hourly Golden Boss, contracts, quest timers |
| P6 | `publish` | 6 | The buffered event stream is delivered to consumers and written to the history log |

**R3 — The core contains no rules.** It owns the loop, the phase table, the command queue, the event buffer, the clock interface, the lifecycle (below), the fatal sink and `sim_version`. It does not import any feature system, does not know what a member, gold or boss is, and does not draw random numbers. A feature system plugs in by registering (R4).

**R4 — Frozen boot-time registry.** A feature registers one or more handlers with `register(phase, order, owner_id, handler)`, where `order` is an explicit integer. Rules:
- Registration is allowed only in `Booting`. In `Ready`, `Running` or `Paused` the call is refused and the core enters `Failed` (R10). In `Unloaded` or `Failed` it is refused with no state change.
- `handler` must be a method on a live object. In GDScript the core rejects, at register time and as a boot error, any Callable that is not a standard method Callable (a lambda, a `bind()` or `unbind()` result) or whose `is_valid()` is false, or that does not take exactly one argument. The exact Callable checks are an implementation detail for the ADR (APIs unverified for 4.7). The registry holds a reference to the owner object, so a `RefCounted` owner cannot be freed under it. Before each call the core checks `is_valid()` again. An owner freed by `free()` (an `Object` or `Node` owner) fails with code 8, attributed to that owner.
- Within a phase, handlers run in ascending `order`. Two handlers with the same `(phase, order)` is a boot error that names both owners. Ties are never broken by registration order, file order or hash order, so the order is identical on every machine and in every implementation.
- `order` values are allocated in steps of 100 by the owning system's GDD, so a later system can slot between two earlier ones without renumbering them.
- Unregistering does not exist. The table is frozen when the lifecycle leaves `Booting`.
- The frozen table (phase, order, owner_id) is hashed into a `phase_table_hash` that the parity harness (43) records, so a changed order is caught as a behaviour change (R12).

**R5 — Handler contract.** A handler receives a context object, runs synchronously to completion, and returns nothing. Through the context it may: read the executing tick N (R1); call `derive(domain_id, key)` for a fresh RNG generator (RNG R3, R4); read content tables, which the context exposes read-only; `emit(type_id, a, b, c, d)` into the per-tick event buffer (an event is five integers, stride 5, defined by the Event bus GDD R2; type IDs 1–99 are reserved for the core, and `commands_dropped` is type 1); `submit(command)` for the next tick (R6); `fail(code, message)` to report an error (R10), after which it must `return` at once. Once `ctx.failed` is set, every context call does nothing: `emit` and `submit` are dropped, and `derive` returns the RNG R9 poison generator. That way a handler that keeps running after a sink call cannot add to the tick.

**Timers are anchored deadline ticks (a convention for feature owners; the core has no timers, R3).** A timed event stores an absolute due tick and fires in P5 when `N ≥ due`, never on `N % interval == 0`. When it fires, its next due tick is `due + k × interval` for the smallest `k ≥ 1` that makes it strictly greater than N, with `interval ≥ 1`. The cadence stays on its original grid. **Across a skip, Offline progress (31) owns every due tick the gap crosses.** Before it calls `skip_ticks`, it pays whatever backlog it grants and re-anchors each crossed due tick past the skip's end. The first live tick after a skip therefore sees no overdue timer, there is no double count, and there is no burst. The core neither fires nor re-anchors timers (OQ-1).

**Context accessors.** `ctx.tick()` returns N. In P1, `ctx.commands()` returns the commands drained for this tick in ascending `seq` (R6). In P6, `ctx.events()` returns the tick's buffer as it stood when P6 began (R2, Edge Cases). The full list of context calls is the API surface table below; nothing else is exposed.

**A handler must not:**
- call another handler or the core's loop;
- suspend or defer: no `await`, `call_deferred`, `set_deferred`, `Timer` or `create_timer`. A handler that returns a non-null value (the observable sign of a coroutine) is a `ctx.fail` attributed to its owner;
- read a clock or an engine random function;
- mutate content tables;
- touch nodes, scenes or signals;
- keep a float accumulator across ticks unless its owner's GDD defines it (R13).

Handlers must be written so a tick takes the same effect whatever the host's frame rate.

**R6 — Commands.** `submit(command)` may be called at any time by the host and by handlers. It stamps the command with `seq`, the next value of a monotonic non-negative int64 counter `next_command_seq` (first value 1), and appends it to the queue. P1 of the next tick that runs takes queued commands in ascending `seq`, at most `command_drain_max` of them (default 25). Any left over stay queued in `seq` order for the next tick's P1. The cap bounds the cost of one P1 under a "send all" burst, and the count makes it deterministic. A command submitted during tick N therefore takes effect in P1 of tick N+1 at the earliest, never mid-phase. When P1 of tick N takes a command, the core appends `(N, seq, command)` to the command log used for replay: the stamp is the applying tick, not the submit time. The logged command is the whole envelope, including its `origin` (host or sim, Command layer R1, R8). The core exposes the next value of the counter as a read-only query, `next_command_seq() → int` (between ticks), for replay drivers (Command layer R9). A refused `submit` returns 0 and consumes no `seq`. The core also writes three kinds of time entry into the same log, `handoff {at_tick, gap_us}` at a hand-off (R8), `offline_credit {at_tick, c}` when Offline progress (31) calls `log_offline_credit(c)` (the credited window in ticks, `0 ≤ c ≤ k`; called exactly once between the `handoff` and its `skip`, Offline R4), and `skip {at_tick, k, resolver_version}` at `skip_ticks(k, resolver_version)`. A `skip` with no preceding `offline_credit` for its hand-off is a logged error; the run is unranked (Leaderboards' rule). `at_tick` is the committed tick count when the entry was written. **Time entries take no `seq`.** `seq` numbers commands only, so a replay that submits the same commands in the same order reproduces every `seq`. **The log's order is its append order**, not `seq`: a command queued before a hand-off and applied after the skip appears after the `skip` entry. `resolver_version` is an integer owned by Offline progress (31). The aggregate resolver is outside `phase_table_hash`, so this is how a replay knows which resolver produced the gap. The core's replay primitive is `inject_handoff(gap_us)` (API surface). A replay driver walks the log in append order. It runs ticks up to each entry's tick; before each tick it re-submits the logged **host-origin** commands **by `seq`** (every entry whose `seq` equals `next_command_seq()`, in ascending order, Command layer R9), never by apply stamp, and never re-submits sim-origin entries, which the replayed handlers regenerate; at a `handoff` entry it calls `inject_handoff`, `log_offline_credit` with the logged `c`, and `skip_ticks` with the same resolver version. *(Replay wording, `origin`, `next_command_seq` and `offline_credit`: consistency-check 2026-11-16, answering Command layer OQ-2, Offline OQ-2, Leaderboards OQ-5.)* The driver itself, the log format, its size bound, the signed summary and the treatment of a `handoff` with no `skip` belong to Leaderboards (35). The command vocabulary and validation are owned by the Command layer (5). Command objects carry only integers, IDs and `uid`s, so a log replays without the original session. Any 64-bit value written to JSON (a save, a log, a vector) is encoded as a string, because JSON numbers lose precision above 2^53.

**R7 — The game clock is injected.** The core takes a `GameClock` interface supplied by its host: `monotonic_us() -> int` and `utc_s() -> int`. The core itself uses neither to decide how many ticks to run (R8 takes elapsed time as an argument). The clock exists so that Offline progress (31) can compute `Δt = utc_s() − last_saved_utc` and so Leaderboards (35) can use one trusted source, and so tests drive both with a fake clock. The core does not decide which source is trusted. That policy (server time versus device time, clock-rollback checks) belongs to Offline progress and Leaderboards. **One source per interval, never both.** The host owns `elapsed_us`, by this rule:
- **Foreground frames.** `elapsed_us` is the difference of two `monotonic_us()` readings, never `_process(delta)`, which is a float. In Godot, `monotonic_us()` is `Time.get_ticks_usec()`.
- **Absences.** The monotonic clock is not trusted across device suspend, because it may not count sleep. An absence is an **OS-level** suspension: the app is backgrounded (mobile `NOTIFICATION_APPLICATION_PAUSED`/`RESUMED`), or it is a cold start. Focus loss without suspension is not an absence, because frames keep running. An in-app pause (R9) is not an absence either. The host re-baselines its monotonic reading and discards that delta at three points: suspension, resumption and `start()`. The first `advance` after a resume, or after `start()` on a loaded save, carries the absence as `elapsed_us = clamp(utc_s() − utc_at_absence_start, 0, 2^62 // 1,000,000) × 1,000,000`, clamped before the multiply so it cannot overflow. For a cold start, `utc_at_absence_start` is the save's `last_saved_utc`. For a new guild it is "now", giving 0. `utc_s()` is whole seconds, so an absence is measured to ±1 s. That is accepted.
- **Trust policy.** Caps and tamper checks on that UTC delta (server time, rollback) belong to Offline progress and Leaderboards. The core takes the value it is given.
- **Host node.** The node that calls `advance` uses `PROCESS_MODE_ALWAYS`, so a `SceneTree.paused` menu never stops it. A scene freeze is an in-app pause (R9) and calls `core.pause()`.

Every absence therefore enters through `advance` exactly once, and F2 decides whether it is exact ticks or a hand-off. The Godot notifications the host listens to are an ADR detail, and the suspend behaviour of `Time.get_ticks_usec()` on Android and iOS is still to be verified (OQ-12); the rule above holds either way.

The host calls `advance` from `_process`, not `_physics_process`, so the physics tick rate and `max_physics_steps_per_frame` play no part. `Engine.time_scale` has no effect on the sim; a debug speed-up scales `elapsed_us` in the host.

**R8 — `advance(elapsed_us, max_ticks)`: hand-off first, then bounded catch-up.** The host calls `advance(elapsed_us)` once per frame. `max_ticks` defaults to `M` and is clamped to `0 … M`. The core adds `elapsed_us` to an integer accumulator `acc_us` (F2):
- **Range guard.** If `elapsed_us` is above `2^62 − acc_us` (checked by subtraction, so nothing overflows), the call goes to the fatal sink and nothing is added. This keeps `acc_us ≤ 2^62` at all times.
- **Hand-off.** If no hand-off is pending and the debt exceeds `T_us` (`offline_threshold_s × 1,000,000`), the core runs **no** tick in this call. It hands off every whole tick of the debt as `gap_us`, keeps only the sub-tick remainder in `acc_us`, sets `pending_gap_us = gap_us`, and appends a `handoff {at_tick, gap_us}` entry to the command log (R6). The gap is therefore applied before any later live tick, in timeline order. `gap_us` is always a whole multiple of `tick_us`. The host must pass it to Offline progress (31), which applies its aggregate results, re-anchors crossed timers (R5) and then calls `skip_ticks(gap_us / tick_us, resolver_version)`.
- **Pending.** While `pending_gap_us > 0`, at most one hand-off is in flight. `advance` adds `elapsed_us` to `acc_us`, runs no tick and makes no second hand-off. There is **no timeout**. Time that arrives while a hand-off is pending, including a further absence, is later than the gap, so it stays in `acc_us` in timeline order. If that debt exceeds `T_us` when the skip lands, the next `advance` hands it off as a second, ordinary, logged gap. The guild is never frozen by a slow resolver and never failed by one. How fast the resolver must be (well under `T`, or the guild runs only on resolved gaps) is Offline progress's requirement (OQ-1). A valid `skip_ticks` clears `pending_gap_us`. The read-only `handoff_pending` flag shows it to presentation.
- **Catch-up.** Otherwise the core runs `n = min(acc_us // tick_us, max_ticks)` ticks and keeps the rest. If debt of at least one tick remains, the sim is behind real time until it recovers, and the read-only `catching_up` flag is true.

**The threshold tests total debt.** A small hitch during a long drain can push the total over `T_us` and hand off the whole remaining debt, including time that was on the exact path. This is accepted. Handing off only the new time would apply it before older debt and break timeline order. The result is deterministic and logged. On a supported device a drain of `T` takes at most the catch-up budget (F6), so the window is bounded.

While `catching_up` is true, the host **must** time-slice (R17). Results are identical however the ticks are spread across frames. Presentation reads `catching_up`, `handoff_pending` and `debt_us` (= `acc_us`) to suppress detail and show that the guild is catching up.

`advance` returns `{ticks_run, gap_us}`. A host that discards `gap_us` never calls the matching `skip_ticks`, so the guild stays pending, runs no tick and keeps `handoff_pending` true. That is visible in the facade and is a host bug, but it is not a crash. The accumulator and the pending gap are never saved (R14). After a load, the absence enters through `advance` by the R7 rule.

**R9 — Pause defers ticks; world time keeps running.** `pause()` and `resume()` take effect between ticks, never inside one. A tick in progress always completes first. If `pause()` is called from a handler during an `advance` that planned `n` ticks, the remaining ticks of that call do not run, and their time is returned to `acc_us`, so nothing is lost. While `Paused`, `advance` behaves exactly as in `Running` except that it runs no tick: it accrues `elapsed_us`, and it hands off when debt exceeds `T_us`. Paused time is therefore owed, never discarded. On `resume()` it drains as catch-up, or it has already been handed off. A cold-start absence that arrives while `Paused` is kept the same way. `pause()` and `resume()` are called from the main thread only (OQ-8). Pausing gains the player nothing: timers are tick-denominated, and the owed ticks run on resume.

**R10 — Failure halts the core and distrusts state.** The core supplies the engine-port fatal sink required by RNG R9. A failure comes from that sink, from a boot error (R4), or from a handler calling `ctx.fail(code, message)`. After every handler returns, the core checks `ctx.failed`, and if it is set the core stops. In every case the core: stops running further handlers for this tick; discards the failing tick's event buffer and command-log entries; does **not** increment `tick`; enters `Failed`; records `fail_code`, `fail_owner_id` and `failed_at_tick` (= `tick`); and marks `state_trusted = false`. The first failure wins: a later `ctx.fail` or sink call never overwrites the record.

**Fail codes.** `fail_code` is an integer. Codes 1–99 are reserved for the core, and a feature's `ctx.fail` uses 1000 or above (values allocated in its own GDD). For a core-originated failure, `fail_owner_id` is the `owner_id` of the handler that was running, or `"core"` if none was.

| Code | Name | Raised by |
|---|---|---|
| 1 | `BOOT_DUPLICATE_ORDER` | two handlers at one `(phase, order)` (R4) |
| 2 | `BOOT_BAD_REGISTRATION` | bad phase, order, `owner_id` or Callable (R4) |
| 3 | `LATE_REGISTER` | `register` outside `Booting` (R4) |
| 4 | `REENTRANT_CALL` | `advance`, `run_ticks`, `skip_ticks` or `inject_handoff` from inside a handler |
| 5 | `ELAPSED_OUT_OF_RANGE` | `elapsed_us` non-integer or above `2^62 − acc_us` (R8) |
| 6 | `BAD_SKIP` | a `skip_ticks` that is mismatched or unrequested (Edge Cases) |
| 7 | `EVENT_CAP` | more than `event_buffer_hard_cap` events in one tick |
| 8 | `HANDLER_FREED` | a handler whose owner was freed (R4) |
| 9 | `HANDLER_RETURNED_VALUE` | a handler returned non-null (R5) |
| 10 | `RNG_FAILURE` | the RNG R9 sink (invalid `derive` and the like) |

**The sink does not unwind in GDScript.** The Python sink raises `RngError`. Every public core entry point catches it at its own boundary (the tick boundary inside a tick, the call boundary outside one) and converts it to `Failed`. The GDScript sink returns normally, so two rules hold:
- The sink records the failure and sets `state = Failed` before returning.
- Every core function that calls the sink, or checks `ctx.failed`, returns at once without touching core state.

Every later call is then refused by the `Failed` state, so the two ports end in the same state. The port's sink first reports through an injected `error_reporter` (default `push_error(message)`), so tests can observe it, then marks the failure. `assert` is never used, because GDScript strips it in release builds.

**Only reported failures reach this path.** A GDScript runtime error (null dereference, bad index, a call on a freed object, a Callable called with the wrong number of arguments) does not raise. It logs and returns a default value, so the core cannot detect it and its effects may be committed. That is an accepted limit of the port, and it is mitigated in three ways:
- At register time the core checks that the handler takes exactly one argument (the context), so the arity case cannot arise. The API to use is an ADR detail.
- The parity harness (43) compares the port against the Python reference, which does raise.
- The host may count script errors through an engine logger hook and report them to Local save as untrusted. Whether it does is Local save's decision (OQ-2), and the API is unverified for 4.7.

The core does **not** roll feature state back: anything a handler mutated during the failing tick is untrusted.

**Recovery is Local save's (6).** `Failed` is terminal for the instance. No transition leaves it, and the instance refuses every call except queries. The host recovers by discarding it and constructing a new instance: a reload, a restart, or a dev-tooling reload (43). Everything else belongs to Local save and the UI (OQ-2):
- refusing to overwrite the last good save while `state_trusted` is false;
- the autosave cadence and the number of save generations;
- any crash marker, and whether the failing stretch is avoided on reload;
- the fatal screen's options.

The core offers no special start mode for recovery. If Local save needs one (for example to carry the guild past `failed_at_tick` through the resolver), its GDD requests it and this rule changes. The Data layer's `Failed` and this state share the same player message class ("fatal error, last save kept").

**R11 — Startup order.** The core never runs a tick before all of these hold, in this order: (1) the Data layer is `Ready` (Data layer R10: content loads once), checked by polling the injected Data layer's state, not through a signal; (2) `config`, `sim_params` and the F1 `content_hash` have been read; (3) the host has finished registering features (the core cannot know which features should exist, so a missing feature shows up as a different `phase_table_hash`, F5), and the table is frozen (R4); (4) `world_seed` is set, either read from a save or created for a new guild by `new_world_seed(entropy_fn, clock_fn, install_id)` with all three injected (RNG R2); (5) the event buffer and command queue are empty. The host then calls `seal()`, which checks all five, freezes the table and moves `Booting → Ready`. A `seal()` with any condition unmet is refused with an error naming it, and the state does not change. `start()` then moves `Ready → Running`. Nothing else starts the core. `submit` before `seal()` is refused (returns 0). If the Data layer reports `Failed`, the core stays in `Booting` and runs no tick.

**R12 — `sim_version` is one integer, owned here.** A constant `SIM_VERSION` (uint32, starts at 1) lives in the core's own file in each implementation. It is read-only at runtime. The same integer is stamped into saves (6) and written into every golden-vector file (43). Its bump rule is Dev tooling R7: any change that alters a result for the same seed, content and command log is a breaking change and must bump it in the same change as the regenerated vectors. A change to the phase table (R2), the registration order (R4) or the arithmetic of R1 or R8 counts as such a change. This settles Dev tooling's provisional assumption that `sim_version` is a single integer, and rejects a per-subsystem version.

**R13 — Core state is integers only.** The core's own state is `tick`, `acc_us`, `pending_gap_us`, `next_command_seq`, `world_seed`, `state` and the buffers. None of these is a float. Each counter is a non-negative int64 in both implementations (R1). **`world_seed` is 63-bit, `0 … 2^63 − 1`**, so it is a non-negative GDScript `int` with no codec. This requires `new_world_seed` to clear the top bit, a change to RNG R2, which currently says 64-bit (Dependencies, OQ-13). Money and drop quantities stay integers by the GDD §3.2 rule, and each owner's GDD defines any float it keeps. Floats inside a handler are 64-bit and evaluated in the order the owner specifies (`GODOT_PORT.md`).

**R14 — What the core saves.** The core contributes exactly `world_seed`, `tick`, `next_command_seq` and `sim_version` to a save (RNG R11 saves only the seed, and the owning systems save their own counters). It does not save `acc_us`, the event buffer or the command queue. Unspent debt is therefore lost on a save-then-quit: up to one tick normally, and up to the drain still owed while `catching_up`. The next absence is measured from `last_saved_utc`, which already includes that wall time, so a cold start re-owes it. The loss on a live save is at most the sub-tick remainder, which is accepted. A save is only taken between ticks (a save never captures a half-run tick). Saves are produced by Local save (6) calling the core's `snapshot_core()` while the core is in `Running` or `Paused`, not mid-tick and not while a hand-off is pending (the gap would otherwise be lost). Either refusal is an error return, and the host retries later. A load uses `restore_core(snapshot)`, allowed only in `Booting` before `seal()`. It sets `world_seed`, `tick` and `next_command_seq`, and it refuses a snapshot whose `sim_version` differs from `SIM_VERSION` (migration is Local save's). In JSON, `world_seed`, `tick` and `next_command_seq` are strings (R6).

**R15 — Presentation reads events, not state.** Realtime world view (38) and Audio (40) consume the P6 event stream and may read committed state only between ticks, never during one. Neither can call into the loop: they receive a read-only facade exposing exactly the event stream, `tick`, `alpha`, `catching_up`, `handoff_pending` and `debt_us`, never the core itself. A GDScript reference cannot enforce read-only access, and GDScript has no private members, so the facade is an accident barrier, not a security boundary. Events reach consumers as read-only copies, so a consumer cannot mutate what the history log holds. The core is a `RefCounted` constructed by the host, not a Node or an autoload. A render frame may fall between two ticks; it interpolates from the last events and `alpha` (F3). Nothing presentation knows — camera position, zoom, which ground is on screen, window focus — ever reaches the simulation: in particular, which grounds run the detailed resolver and which the sampled one (simulation LOD) is decided in-sim by Zones' deterministic tier rule (Zones R17, user decision 2026-11-16), so replay and the leaderboard verifier (35, which has no camera) reproduce it exactly.

**R16 — The same loop runs headless.** Tools and tests drive the core with `run_ticks(n)` and a fake clock, with no host frame loop. `run_ticks` is the exact path used by the balance simulator and the parity harness (43) and by Leaderboards' server replay (35). It runs the same phases in the same order as `advance`. The aggregate offline resolver of Offline progress (31) is a different algorithm, owned by that system, and not an approximation of `run_ticks`. It enters the core only through a logged `handoff` and `skip` (R6, R8), so a replay of the log calls the same resolver version with the same `gap_us`.

**R17 — Time-slicing and instrumentation are required.**
- **Time-slicing (host).** While `catching_up` is true, the host calls `advance(0, 1)` repeatedly within one frame, one tick per call. It stops when its per-frame sim budget `sim_slice_budget_us` is spent or when `catching_up` clears. It always makes at least one call per frame. `sim_slice_budget_us = sim_share × frame_budget_us` (F6): 8,333 µs at 60 fps and 16,667 µs at 30 fps. It is the same half-frame figure F6 uses for single-tick frames, so there is one constant. The host checks its monotonic clock between calls, never inside the core. A frame's sim cost is therefore at most `sim_slice_budget_us + c_tick`. The UI keeps rendering and taking input every frame **as long as `c_tick` stays below `sim_slice_budget_us`**, which is the min-spec requirement (F6). A long drain is slow but never freezes the app.
- **Catch-up presentation.** While `catching_up` or `handoff_pending` is true, presentation suppresses per-event animation and audio and shows a catching-up state with progress from `debt_us`. Orders the player gives during catch-up are queued and apply at the next tick that runs, which is behind wall time until the drain ends. The UI acknowledges a queued order at once (Guild screens 39).
- **Instrumentation (core).** The core calls an injected, observer-only `profiler` with `begin(phase, owner_id)` and `end(phase, owner_id)` around each phase (`owner_id = ""`) and each handler. The core never reads a clock itself (R1), so the profiler implementation reads the host's clock, and no value it produces is ever read by a handler or written to state. With no profiler injected (`null`, the release default), the core skips the calls with one `if profiler != null` check per site, so it pays no call cost. The profiler keeps fixed-capacity sample buffers (no unbounded growth). It records per-tick cost (p50, p95, p99, max), per-phase and per-owner cost, events and commands per tick, queue depth, `debt_us`, slices per frame and slice overruns. Overhead target: at most 0.1 ms per tick when enabled, measured as the profiler-on minus profiler-off delta (AC-34).
- **Budgets.** Each phase has a provisional, non-binding share of the per-tick budget (F6). Each feature GDD that registers a handler states its cost scaling (per member, per event) at the max-roster fixture against its phase's share. No handler may scan every member every tick when the work is timer- or event-driven; deadline ticks (R5) exist for that.

### Core API surface

Every call the Acceptance Criteria use is listed here. A call not in this table does not exist. Return values are what tests assert. An "error return" is a non-OK `Error` value (GDScript) or a raised `CoreError` (Python), with no state change.

| Call | Allowed in | Returns | Notes |
|---|---|---|---|
| `new(clock, data, log_sink, error_reporter, profiler = null)` | — | instance in `Unloaded` | All dependencies injected. `data` exposes its state and tables |
| `boot()` | `Unloaded` | `bool` | A second call logs an error and returns false |
| `register(phase, order, owner_id, handler)` | `Booting` | `bool` | Holds a reference to the owner object. Errors per R4 |
| `restore_core(snapshot)` | `Booting`, before `seal` | OK or error return | R14 |
| `seal()` | `Booting` | OK or error naming the unmet condition | R11 |
| `start()` | `Ready` | `bool` | |
| `pause()` / `resume()` | `Running` / `Paused` | `bool` | R9 |
| `advance(elapsed_us, max_ticks = M)` | `Running`, `Paused` | `{ticks_run, gap_us}` | R8. Other states return `{0, 0}` (Edge Cases) |
| `run_ticks(n)` | `Running`, no hand-off pending | ticks run, or error return | R16 |
| `skip_ticks(k, resolver_version)` | `Running`, `Paused`, with a hand-off pending | OK. A mismatch is fatal (code 6) | Edge Cases |
| `inject_handoff(gap_us)` | `Running`, no hand-off pending | OK or error return | Replay only (R6). Sets the pending gap and logs `handoff` exactly as R8 would |
| `submit(command)` | after `seal`, not `Failed` | `seq` (≥ 1), or 0 if refused | R6 |
| `snapshot_core()` | `Running`, `Paused`, between ticks, no hand-off pending | snapshot, or error return | R14 |
| `dispose()` | any | — | Clears the registry, context and facade (Edge Cases) |
| `facade()` | any | the R15 facade | |
| Queries | any | value | `state`, `tick`, `state_trusted`, `fail_code`, `fail_owner_id`, `failed_at_tick`, `catching_up`, `handoff_pending`, `debt_us`, `clock_anomaly_count`, `event_soft_cap_count`, `phase_table_hash`, `command_log()` (a read-only copy, in append order) |
| `ctx.tick()`, `ctx.commands()` (P1), `ctx.events()` (P6), `ctx.derive(domain_id, key)`, `ctx.content(table)`, `ctx.emit(type_id, a, b, c, d)`, `ctx.submit(command)`, `ctx.fail(code, message)`, `ctx.failed` | inside a handler | per R5 | The full context. A context object is only valid during its tick, and calls on a stale one do nothing |
| `ticks(s)`, `seconds(t)` | static | `int` | F4, in the core's time module |

### States and Transitions

| State | Meaning | Ticks run? | Accepts `register`? |
|---|---|---|---|
| `Unloaded` | Process started, nothing initialised | No | No |
| `Booting` | Waiting for the Data layer `Ready`; features register (R4) | No | Yes |
| `Ready` | Table frozen, seed set, buffers empty | No | No |
| `Running` | Ticking via `advance` or `run_ticks` | Yes | No |
| `Paused` | Between ticks, host asked to pause; time still accrues (R9) | No | No |
| `Failed` | A failure occurred (R10); `state_trusted = false` | No | No |

| From | To | Trigger |
|---|---|---|
| `Unloaded` | `Booting` | Host calls `boot()` |
| `Booting` | `Ready` | Host calls `seal()` with all R11 conditions met |
| `Booting` | `Failed` | Duplicate `(phase, order)`, unknown phase, out-of-range `order`, bad `owner_id`, or an invalid handler (R4). A Data layer `Failed` is **not** a trigger: the core stays in `Booting` (R11) |
| `Ready` | `Running` | Host calls `start()`. `run_ticks` does not start the core |
| `Ready` | `Failed` | A `register` call after the table is frozen (R4) |
| `Running` | `Paused` | `pause()`, effective at the next tick boundary (R9) |
| `Paused` | `Running` | `resume()` |
| `Running` | `Failed` | Any fatal-sink call or `ctx.fail`, inside or outside a tick (fail codes 3–10, R10): a handler failure, a re-entrant call, `elapsed_us` out of range, a mismatched or unrequested `skip_ticks`, the event cap, a freed owner, a handler returning a value, an RNG failure. Also a late `register` (R4) |
| `Paused` | `Failed` | Any fatal-sink call outside a tick (a mismatched or unrequested `skip_ticks`, `elapsed_us` out of range), or a late `register` (R4) |

**Hand-off pending** is a flag (`pending_gap_us > 0`) inside `Running` or `Paused`, not a separate state. While it is set: `advance` accrues time but runs no tick and makes no second hand-off (R8), `run_ticks`, `inject_handoff` and `snapshot_core()` are refused with an error return, and only a matching `skip_ticks` clears it. It has no timeout.

This table is the single source of truth for the lifecycle; Edge Cases and Acceptance Criteria follow it. `Ready`, `Running` and `Paused` never go back to `Booting`: registration is closed for the life of the instance. `Failed` is terminal. No transition leaves it, and the instance refuses every call except state queries. Recovery means discarding it: the host constructs a new core instance (switching saves, restart, or a dev-tooling reload), which starts in `Unloaded`. Recovery policy is Local save's (R10).

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Deterministic RNG (2) | RNG → core | `derive(domain_id, key)`, `new_world_seed(...)`, `fatal_sink` contract | The `fatal_sink` implementation; a context method that forwards `derive` | RNG owns the API; the core owns when events run |
| Data layer (3) | Data → core | Its state (polled, R11); `config`, `sim_params`, F1 hash | Boot refusal while the Data layer is not `Ready` | Data layer |
| Command layer (5) | both | Validated command objects submitted via `submit` | Queue order (`seq`) and the P1 drain point | Command layer owns the vocabulary, the core owns the queue |
| Local save (6) | both | Core snapshot (R14), `state_trusted` | `snapshot_core()`, `restore_core()`; a `state_trusted` flag that save must honour; the `Failed` record (`fail_code`, `fail_owner_id`, `failed_at_tick`) | Save owns the format, the cadence, the generations and all crash-recovery policy (R10, OQ-2); the core owns what it contributes |
| Event bus and history log (42) | core → bus | Per-tick event buffer in emission order | The P6 `publish` handler delivers the buffer | Bus owns delivery and log format, the core owns the buffer and the discard-on-fail rule |
| Offline progress (31) | both | `gap_us` from `advance`; `GameClock.utc_s()` | `skip_ticks(k, resolver_version)`; the clock interface | Offline owns the aggregate resolver, its tolerance and speed, `resolver_version`, the UTC trust policy, the timer backlog and the re-anchoring of crossed due ticks (R5) |
| Leaderboards and anti-cheat (35) | both | Command log with `handoff` and `skip` entries; `sim_version`; `world_seed` | `run_ticks` and `inject_handoff` for server replay; the clock interface | Leaderboards owns the replay driver, the summary format, the log size bound and the unranked rule |
| Dev tooling and parity harness (43) | core → tools | `SIM_VERSION`; `phase_table_hash`; `run_ticks` entry | A callable entry the balance simulator uses | Dev tooling |
| Feature systems (8–30, 41) | feature → core | `register(phase, order, owner_id, handler)` | Context object (R5) | Each feature owns its own phase order and draw order |
| Realtime world view (38), Audio (40) | core → view | The read-only facade: P6 events, `tick`, `alpha`, `catching_up`, `handoff_pending`, `debt_us` (R15) | None; they never call the loop | World view |
| Push notifications (46) | core → push | `tick`, `GameClock` | None | Push notifications |

## Formulas

All formulas are integer arithmetic. `//` is floor division on non-negative integers (identical in Python and GDScript for non-negative operands). F3 is the only value that is not an integer, and it is presentation-only.

### F1 — `tick_us`

The tick_us formula is defined as:

`tick_us = 1,000,000 // tick_rate`, valid only when `1,000,000 mod tick_rate = 0`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| tick_rate | int | one of {1, 2, 4, 5, 8, 10, 16, 20} | data file (`config.tick_rate`) | Ticks per second |
| tick_us | int | one of {1,000,000, 500,000, 250,000, 200,000, 125,000, 100,000, 62,500, 50,000} | calculated | Microseconds of simulation time per tick |

**Output Range:** 50,000 to 1,000,000, a non-contiguous set. The validator applies two rules. The divisor rule rejects any value that does not divide 1,000,000 = 2^6 × 5^6 (for example 3, 7, 12), because `tick_us` would be inexact and the two implementations could round differently. The range rule rejects 0 and anything above 20 (for example 25, which does divide 1,000,000). The bound of 20 is a performance guard, not a math limit (F6). The accepted values are exactly the eight listed above.
**Example:** `tick_rate = 10` → `tick_us = 100,000`. `tick_rate = 8` → `125,000`. `tick_rate = 3` → rejected by the divisor rule (1,000,000 mod 3 = 1). `tick_rate = 25` → rejected by the range rule.

### F2 — `advance` (catch-up and hand-off)

The advance formula is defined as:

```
if elapsed_us < 0: elapsed_us = 0 (Edge Cases)
if elapsed_us > 2^62 − acc_us: fatal sink, code 5 ; nothing is added
acc' = acc_us + elapsed_us
if pending_gap_us > 0:                            # hand-off in flight: accrue only (R8)
    acc_us = acc' ; n = 0 ; gap_us = 0
elif acc' > T_us:                                 # hand-off first, no tick this call
    n = 0 ; acc_us = acc' mod tick_us ; gap_us = acc' − acc_us ; pending_gap_us = gap_us
else:                                             # bounded catch-up
    m = 0 if state = Paused else clamp(max_ticks, 0, M)
    n = min(acc' // tick_us, m) ; acc_us = acc' − n × tick_us ; gap_us = 0
catching_up = (acc_us ≥ tick_us) and pending_gap_us = 0 and state = Running
```

If a handler pauses the core after `j < n` of the planned ticks, the call stops and `n` is reported as `j`. The unrun ticks' time stays in `acc_us` (`acc_us = acc' − j × tick_us`), so the identity below still holds.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| elapsed_us | int | 0 – `2^62 − acc_us` | calculated (host) | Wall time since the previous `advance`. Negative is clamped to 0; non-integer or above range is fatal (Edge Cases) |
| max_ticks | int | 0 – M (clamped) | argument, default M | The host's per-call tick cap; time-slicing passes 1 (R17) |
| acc_us | int | 0 – 2^62 | calculated | Unspent time carried between calls. `≤ T_us` after a catch-up call, `< tick_us` right after a hand-off, any value up to 2^62 while a hand-off is pending |
| pending_gap_us | int | 0, or a valid `gap_us` | calculated | The in-flight hand-off; 0 when none |
| tick_us | int | 50,000 – 1,000,000 | calculated (F1) | Tick length |
| M | int | 1 – 20 | data file (`config.live_catchup_max_ticks`) | Maximum ticks one `advance` call may run |
| T_us | int | `(M + 1) × tick_us` – 600,000,000 | data file (`config.offline_threshold_s` × 1,000,000; `offline_threshold_s` is a whole number 1 – 600) | Debt above which time is handed to Offline progress |
| n | int | 0 – M | calculated | Ticks run this call |
| gap_us | int | 0, or a multiple of `tick_us` in `T_us` … 2^62 | calculated | Time handed to Offline progress (R8) |
| catching_up | bool | — | calculated | True while `Running` with at least one whole tick of debt and no hand-off pending |

**Output Range:**
- `n` is in 0 … `max_ticks` ≤ M.
- `acc_us` never exceeds 2^62, because the range guard checks before adding. No intermediate exceeds 2^62, which is far inside int64.
- `gap_us` is 0, or a whole multiple of `tick_us` that is at least `T_us`. It is a multiple because `T_us` is whole seconds and `tick_us` divides 1,000,000, so `T_us` is itself a multiple of `tick_us`.
- Time is conserved, with no rounding and no exceptions: `elapsed_us + acc_before = n × tick_us + acc_after + gap_us`. Here `elapsed_us` is the value after the negative clamp. This holds in `Paused` (where `n = 0`), while a hand-off is pending, and when a pause cuts a call short.

**Validator rule `T_us ≥ (M + 1) × tick_us`.** In steady state `acc_us < tick_us`, so a frame triggers a hand-off only if it carries more than `T_us − tick_us`. The rule keeps that above `M × tick_us`, so only a hitch longer than one call's full catch-up can hand off, never an ordinary frame. Without the rule, `tick_rate = 1` with `T = 1 s` would hand off almost every tick: from `acc = 990,000`, a frame of `16,667` gives `acc' = 1,006,667 > T_us`. The rule replaces the earlier claim that "`T_us ≥ tick_us`, so no check is needed", which was wrong. At the defaults the rule needs `T ≥ 0.6 s`, so 60 s passes easily. At `tick_rate = 1` and `M = 5` it needs `T ≥ 6 s`.

In GDScript, `//` is integer `/` on non-negative ints, `2^62` is written `1 << 62` (`^` is XOR), and `min` is `mini`.

**Boundaries:** `elapsed_us = 0` → `n = 0` unless debt is already ≥ one tick. The test is strict, so `acc' = T_us` exactly is kept and caught up, and `T_us + 1` hands off. `M = 1` is allowed: the sim runs at most one tick per call, and host time-slicing (R17) supplies the throughput.

**Example (a 1 s hitch):** `tick_us = 100,000`, `M = 5`, `T_us = 60,000,000`, `acc_us = 0`, `elapsed_us = 1,000,000`. `acc' = 1,000,000 ≤ T_us`, so `n = 5`, `acc_us = 500,000`, `catching_up = true`. Next frame `elapsed_us = 33,000`: `acc' = 533,000`, `n = 5`, `acc_us = 33,000`, `catching_up = false`. Recovered in two frames.

**Example (resumed after 45 s):** the R7 absence rule gives `elapsed_us = 45,000,000` from `acc_us = 0`. `acc' ≤ T_us`, so this is caught up as exact ticks: `n = 5` this call, `acc_us = 44,500,000`. With host time-slicing (R17), the drain time follows F6.

**Example (resumed after 10 minutes, then locked during the hand-off):** `elapsed_us = 600,050,000` from `acc_us = 0`. `acc' > T_us`, so `n = 0`, `acc_us = 50,000`, `gap_us = 600,000,000`, and a `handoff {at_tick, 600,000,000}` entry is logged. Before the resolver finishes, the player locks the phone for 40 s. The resume carries `advance(40,000,000)`: no tick runs, no fatal, and `acc_us = 40,050,000`. Offline progress then calls `skip_ticks(6,000, resolver_version)`. The next `advance(0)` finds `acc' = 40,050,000 ≤ T_us` and runs 5 ticks, starting the drain of the 40 s as exact ticks. Had the lock lasted 90 s, `acc' = 90,050,000 > T_us` and that `advance(0)` would hand off a second, logged gap of 90 s.

**Example (paused through an absence):** `Paused` with `acc_us = 0`, then `advance(30,000,000)`. `n = 0` and `acc_us = 30,000,000`. After `resume()`, `advance(0)` runs 5 ticks. The 30 s is owed, not discarded (R9).

### F3 — `alpha` (render interpolation)

The alpha formula is defined as:

`alpha = min(float(acc_us) / float(tick_us), 1.0)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| acc_us | int | F2 range | calculated | Unspent time (F2) |
| tick_us | int | 50,000 – 1,000,000 | calculated (F1) | Tick length |
| alpha | float | 0.0 – 1.0 | calculated | How far between two ticks the renderer is |

**Output Range:** 0.0 to 1.0. The conversion to float is explicit, because GDScript `int / int` is integer division and would give only 0 or 1. The value is clamped: while `catching_up` or `handoff_pending`, unclamped `acc_us / tick_us` can reach 600 or more, and presentation must not extrapolate from it. It is read by presentation only and is never written to saves or read by any handler (R15), so its float representation cannot affect determinism. Right after a hand-off `acc_us < tick_us`, so `alpha < 1.0`. Time accrued while the hand-off is pending can clamp it back to 1.0, and presentation then shows the catching-up state (R17).
**Example:** `acc_us = 33,000`, `tick_us = 100,000` → `alpha = 0.33`. `acc_us = 500,000` → `alpha = 1.0` (clamped).

### F4 — Time conversions

The tick_count formula is defined as:

`ticks(s) = s × tick_rate` and `seconds(t) = t // tick_rate`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| s | int | 0 – 86,400 × 30 | calculated | Whole seconds of simulation time |
| t | int | 0 – 2^62 | calculated | Ticks |
| tick_rate | int | the F1 set | data file (`config.tick_rate`) | Ticks per second |

**Output Range:** exact for whole seconds. Anything a feature measures in seconds, minutes or hours converts through this one rule; no feature defines its own tick length.
**Example:** the hourly Golden Boss, `golden_boss_interval_min = 60` → `ticks(3,600) = 36,000`. The offline cap `offline_cap_free_h = 12` (one cap for every player, user decision 2026-11-16) → 432,000 ticks, which is why Offline progress resolves a gap in aggregate (GDD §10) instead of through `run_ticks` (R16).

### F5 — `phase_table_hash`

The phase_table_hash formula is defined as:

`phase_table_hash = SHA-256( concat over entries sorted by (phase, order) of [ u8(phase) ‖ u32_be(order) ‖ u8(len) ‖ utf8(owner_id) ] )`, hex-encoded lowercase

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| phase | int | 1 – 6 | constant | P1…P6 of R2 |
| order | int | 0 – 2^31 − 1 | calculated | The registered `order` (R4) |
| owner_id | string | 1 – 48 chars, `[a-z0-9_]` | calculated | The registering system's stable ID (same format as Data layer R3) |
| phase_table_hash | string | 64 hex chars | calculated | Identifies the exact set and order of handlers |

**Output Range:** 64 lowercase hex characters. `u32_be` is big-endian. In GDScript it is packed by hand with shifts, because `PackedByteArray.encode_u32` writes little-endian. The digest uses `HashingContext` (`HASH_SHA256`) and `.hex_encode()`, and CI cross-checks it against Python `hashlib`. It covers phase, order and owner only, not handler code: its job is to make a reordered or added handler visible to the parity harness (43), which records it beside `sim_version`.
**Example:** a table of one entry `(phase 2, order 100, "member_state_machine")` hashes the bytes `02 00000064 14 6d656d6265725f...`. (The 64-character result is computed by the implementation; this GDD gives the framing, not a hash value.)

### F6 — Sustainable tick cost

The tick-cost formulas are defined as:

`sim_slice_budget_ms = sim_share × frame_budget_ms` (the frame bound: one tick must fit, `c_tick ≤ sim_slice_budget_ms`)

`r_net = sim_share × 1000 / c_tick − tick_rate` (net drain rate, ticks per second, while time-slicing)

`t_drain(D) = D / r_net` and `T_max = B × r_net / tick_rate` (seconds)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| frame_budget_ms | float | 8.33 – 33.3 | constant | Per-frame budget from `technical-preferences.md` (120 fps → 8.33, 60 fps → 16.67, 30 fps → 33.3 ms) |
| sim_share | float | 0.25 – 0.75 | constant | Share of a frame the simulation may use (0.5 chosen: the other half is rendering and input). The single half-frame constant behind `sim_slice_budget_us` (R17) and the single-tick p99 bound |
| c_tick | float | > 0 | measured (P1 spike) | Per-tick cost in ms, at the max-roster fixture (OQ-6) |
| tick_rate | int | the F1 set | data file | Ticks per second arriving in real time |
| D | int | ≥ 0 | calculated | Debt to drain, in ticks |
| B | float | 10 s (provisional) | constant | Catch-up budget: the longest a supported device may show "catching up" after a gap of `T` |
| r_net | float | may be ≤ 0 | calculated | Ticks of debt cleared per second of wall time |
| T_max | float | seconds | calculated | Largest `offline_threshold_s` whose drain fits in `B` |

**Output Range:**
- **Frame bound.** `sim_slice_budget_ms` is 8.33 ms at 60 fps and 16.67 ms at 30 fps. Time-slicing runs one tick per call (R17), so a frame's sim cost is at most the slice budget plus one tick. **A device is min-spec only if its p99 `c_tick` is at most `sim_slice_budget_ms`.** Above that, a single tick is a visible stutter on every catch-up frame and on spike frames (the hourly P5, a P1 burst). The fix is then handler cost or `tick_rate` (a `sim_version` bump), not this formula.
- **Drain rate.** `r_net` does not depend on frame rate, because the slice scales with the frame: `sim_share × frame_budget_ms / c_tick` ticks per frame, times `1000 / frame_budget_ms` frames per second. The sim falls behind real time only when `r_net ≤ 0`, that is when `c_tick ≥ sim_share × 1000 / tick_rate` (50 ms at the defaults), which is far outside min-spec.
- **Threshold.** `T_max = B × r_net / tick_rate`. The P1 spike sets `offline_threshold_s` to at most `T_max`, and at least the Tuning Knobs floor.

| `c_tick` (p95) | `r_net` (ticks/s) | Drain of 60 s (600 ticks) | `T_max` at B = 10 s |
|---|---|---|---|
| 1.5 ms | 323 | 1.9 s | 323 s |
| 5 ms | 90 | 6.7 s | 90 s |
| 8.33 ms (min-spec limit) | 50 | 12 s | 50 s |
| 10 ms | 40 | 15 s | 40 s |
| 20 ms | 15 | 40 s | 15 s |

This is the arithmetic the earlier "0.5 ms gives 0.3 s, 10 ms gives 6 s" figures got wrong: they ignored the slice share and the time that keeps arriving. **The default `T = 60 s` is consistent with B = 10 s only if p95 `c_tick ≤ 6.9 ms`.** If the spike measures more, `T` comes down. If `T_max` falls below the 30 s floor, a phone lock of up to 30 s would reach the resolver, which is a Player Fantasy trade-off. The creative-director decides that, not this formula.

- **Unsliced calls.** A host that does not slice runs up to M ticks per call, which costs `M × c_tick`. That is why R17 makes slicing mandatory and why M only bounds a single unsliced call.
- **Throttling.** Thermal throttling slows the whole frame, so measure after at least 20 minutes of sustained load as well as cold.
- **Release builds only.** Debug builds and the editor make GDScript much slower, so only release-export timings count.

**Provisional, non-binding per-phase shares of the per-tick budget** (owners state their scaling against these, R17): P1 10%, P2 25%, P3 35%, P4 15%, P5 5%, P6 10%. The P1 spike replaces them with measured values (OQ-6).

**This is a budget to measure, not a measured value.** `GODOT_PORT.md` records only Python timings for whole trips (about 1.9 µs per simulated tick in aggregate). Those are not comparable to a per-tick loop. Verify on the named min-spec Android phone in the P1 spike, using p95, p99 and max tick cost rather than the mean, at both 60 and 30 fps (AC-34, OQ-6).

**Example:** a measured 4 ms p95 tick gives `r_net = 0.5 × 1000 / 4 − 10 = 115` ticks/s. A 60 s gap then drains in `600 / 115 ≈ 5.2 s`, and `T_max = 10 × 115 / 10 = 115 s`, so `T = 60 s` stands. A measured 12 ms p95 gives `r_net ≈ 31.7` and `T_max ≈ 32 s`, and that device also fails min-spec, because its p99 is above 8.33 ms.

## Edge Cases

**Time input**
- **If `elapsed_us` is negative**: treat it as 0, add 1 to a `clock_anomaly_count` the host can read, and log one warning per core instance, on the first anomaly only, through the injected log sink. A monotonic clock cannot legitimately go backwards, but ending the guild's run for a clock glitch is worse than ignoring one frame. Detecting wall-clock tampering is Offline progress's and Leaderboards' job (R7), not this rule.
- **If `elapsed_us` is not an integer, or exceeds `2^62 − acc_us`**: fatal sink, code 5 (R8, R10). It is a host programming error, and silent truncation would differ between Python and GDScript. The guard subtracts before adding, so it cannot overflow. In GDScript the parameter is typed `int`, so a non-integer cannot reach the core; that case is checked in Python only.
- **If `elapsed_us` is 0**: no tick unless carried debt already covers one (F2). Never an error.
- **The sub-tick remainder of a gap**: never leaves the core. A hand-off keeps `acc' mod tick_us` in `acc_us`, so `gap_us` is always a whole number of ticks `k = gap_us / tick_us` (F2). No credit-back call exists.
- **If Offline progress finishes a gap**: it calls `skip_ticks(k, resolver_version)`. This adds `k` to `tick` without running phases, clears the pending flag and logs a `skip {at_tick, k, resolver_version}` entry (R6). Before the call, Offline progress applies the aggregate results, pays any timer backlog it grants (Golden Boss backlog is at most 3, `golden_boss_backlog_max`) and re-anchors every due tick the gap crosses (R5). The first live tick after a skip therefore sees no overdue timer and no burst.
  - `skip_ticks` is the only way the core's time moves other than a tick.
  - It is accepted only between ticks, in `Running` or `Paused`, and only with `k` equal to the pending hand-off's `gap_us / tick_us`.
  - A mismatched or unrequested skip goes to the fatal sink (code 6). So does a skip called from inside a handler (code 4). In other states it is refused with an error return and no state change.
  - While a hand-off is pending, `advance` accrues `elapsed_us` but runs no tick and makes no second hand-off (F2). That includes a further absence of any length. There is no timeout. After the skip, the first `advance` treats the accrued debt normally: it catches up if the debt is at most `T_us`, or it hands off again as a second, ordinary, logged gap.
  - **If the resolver is slower than `T`**: every skip is followed by a new gap of at least `T`, so the guild advances only through resolved gaps and no live tick runs. That is not a deadlock, because time still moves. It does break the live experience, so Offline progress must resolve well within `T` (OQ-1).
  - **If no skip ever arrives** (a host bug): the guild stays pending, `handoff_pending` stays true and no tick runs. It is visible, not a crash, and no state is lost.
  - The call shape stays provisional until Offline progress is designed (OQ-1).
- **If the host never calls `advance` while the app is backgrounded**: by R7 the host discards the monotonic delta on resume and passes the UTC absence as one `elapsed_us`. Up to `T_us`, that debt is caught up as exact ticks with mandatory time-slicing (R17). Above `T_us`, the whole debt is handed off before any tick runs (F2 example). Splitting a gap into many small `advance` calls does not dodge the hand-off: each call adds to `acc_us`, so the threshold is crossed in the same place.
- **If a debugger breakpoint stalls a dev build**: the next `elapsed_us` is large and may hand off. That is correct but noisy, so a dev build's host may clamp it. A release host never clamps.
- **If a save from a build with a different `tick_rate` is loaded**: refused or migrated by Local save (6). `tick_rate` is not a tuning knob in a shipped build (Tuning Knobs): every tick-denominated number in a save (timers, cooldowns, `tick` itself) changes meaning if it changes, so changing it is a `sim_version` bump with a migration.

**Lifecycle**
- **If `advance` or `run_ticks(n > 0)` is called in `Unloaded`, `Booting`, `Ready` (before `start`) or `Failed`**: no tick runs and no debt accrues. `advance` returns `{ticks_run: 0, gap_us: 0}`. In `Failed` it is silent, since the failure was already reported. In the other three it logs one error per call, because it is a host sequencing bug. Tools call `seal()` and `start()` before `run_ticks`, like any host.
- **If `run_ticks` is called while `Paused`, or while a hand-off is pending**: refused (0 ticks, error return). Tools never pause. A pending gap must be skipped first.
- **If `seal()` is called with a condition unmet, or outside `Booting`**: refused with an error naming the condition; no state change.
- **If `advance`, `run_ticks`, `skip_ticks` or `inject_handoff` is called from inside a handler (re-entrancy)**: fatal sink, code 4. A tick must never start while another is running.
- **If `pause()` is called mid-tick** (from a handler): the current tick completes and no further tick of that `advance` call runs. Their time stays in `acc_us` (R9, F2). A call from another thread is unsupported (R9, OQ-8). If the core is not `Running`, `pause()` is a no-op that returns false.
- **If the player pauses and real time passes**: the time is owed (R9). `Paused` accrues it in `acc_us` and runs no tick. On `resume()` it drains as catch-up, or it is handed off while still paused if it exceeds `T_us`. Backgrounding is the absence rule instead (R7). In both cases, no wall time is ever discarded.
- **If `boot()` is called twice**: the second call logs an error and does nothing; registrations are not duplicated.
- **If the host switches to another save slot**: it constructs a new core instance on the same loaded Data layer. State is never shared between instances: the core keeps no static or global state. The old instance is released with `dispose()`, which clears the registry, context and facade so that no reference cycle keeps it alive.
- **If the Data layer is `Failed`**: the core stays in `Booting`, runs no tick, and reports "data layer failed" so the host can show its fatal screen (Data layer UI Requirements).

**Registration**
- **If two handlers register the same `(phase, order)`**: boot error naming both owners; `Booting → Failed`. It is never resolved by registration order.
- **If `phase` is not in 1…6, `order` is outside 0…2^31−1, or `owner_id` breaks the F5 format**: boot error; `Booting → Failed`.
- **If `register` is called outside `Booting`**: the call is refused. From `Ready`, `Running` or `Paused` the core enters `Failed` (R10) and the message names the owner. From `Unloaded` or `Failed` nothing else changes (States table). A late registrant is a programming error that would otherwise give an order no other machine reproduces.
- **If a feature registers no handler in a phase**: fine. If it registers none at all, it has no per-tick behaviour; the core does not care.
- **If a feature is present in one build and absent in another** (for example a Wave 2 system not yet shipped): the `phase_table_hash` differs, so a save, a golden vector and a leaderboard summary tied to the other table are not comparable. That difference is expected; Dev tooling (43) records the hash, and a content or build mismatch is Local save's and Leaderboards' policy.

**Commands**
- **If a command is submitted while `Paused`**: queued with a normal `seq` (not 0); applied in P1 of the first tick after `resume()`. The queue is not time-stamped by wall time.
- **If a command is submitted while `Failed`**: refused; `submit` returns `seq = 0`. `seq` starts at 1, and 0 means "not accepted".
- **If the queue reaches `command_queue_max`**: the new command is refused, `submit` returns 0 and consumes no `seq`. Refusals are coalesced into one `commands_dropped` core event per tick (type 1, `a = count`), emitted into the buffer of the next tick that runs (or the current tick, if a handler submitted). A tap-flood of any size therefore adds one event, never enough to reach the event cap. The queue is never silently truncated from the front. Showing the drop to the player is Guild screens' job (39).
- **If more than `command_drain_max` commands are queued at a tick**: P1 takes the first `command_drain_max` in `seq` order, and the rest wait for the next tick. Nothing is dropped.
- **If a command is submitted before `seal()`**: refused, returns 0. This guards against a UI tap-flood; a normal player never reaches the cap.
- **If a handler submits a command during tick N**: it applies in P1 of tick N+1 (R6). A handler cannot make a command apply in the same tick.
- **If two commands conflict** (for example, order the same member to two jobs): they apply in ascending `seq`. The second sees the state the first left, and a validator rejects it if it no longer applies. The result is deterministic because the order is.
- **If a command references a member or object that was removed earlier in the same P1 pass**: its validator rejects it, with no effect and no error. Validation always reads the state at that command's turn.

**Events and publish**
- **If a handler emits an event during P6**: it goes into the next tick's buffer. It is never delivered in the tick that is already publishing, so a publish cannot loop.
- **If one tick emits more than `event_buffer_hard_cap` events (default 2,000, a config knob)**: fatal sink, code 7. It almost certainly indicates a runaway loop in a handler. Exactly the cap passes, and core events count toward it. The cap stays fatal, not discard-and-continue, because hiding a runaway handler would quietly corrupt the P6 history. A system that can legitimately emit many events in one tick (a raid, a mass drop) must bound its own per-tick emission or aggregate, and state that bound in its GDD. Local save's autosave cadence (OQ-2) limits what the player loses.
- **If one tick emits more than half the cap** (`event_buffer_hard_cap // 2`, so 1,000 by default): a soft warning. The core increments `event_soft_cap_count` and logs once per instance, and the tick continues. This gives a warning long before the fatal cap.
- **If a failure occurs during P6 after some consumers have already received events**: those events cannot be recalled. The tick is still discarded and the core is `Failed`; consumers saw a prefix of a failed tick. Accepted: state is untrusted either way, and the host shows the fatal screen.
- **If two events are emitted in the same tick by different phases**: delivery order is emission order, which is phase order and then handler order. It is deterministic by R2 and R4.

**Failure and save**
- **If a failure happens in tick N**: `tick` is still N, the buffer is discarded, `state_trusted = false`, and `failed_at_tick = N`. Feature state mutated by handlers up to the failure is untrusted. Local save must keep the last good save. What the player loses, and whether a reload avoids tick N, is Local save's policy (R10, OQ-2). That is the accepted cost of not rolling back.
- **If `snapshot_core()` is called mid-tick, while a hand-off is pending, or while `Failed`**: refused with an error return, never a fatal sink; a bad save call must not end the run. The host retries later.
- **If a save is taken, then the run later fails, then the player reloads that save**: it reloads cleanly, because the save was taken between ticks of a trusted state.

**Numbers**
- **If `tick` would exceed 2^63 − 1**: unreachable. At 20 ticks per second it takes about 1.5 × 10^10 years. No guard is written, and none is required.
- **If `T_us` or `M` is out of range in `config`, or `T_us < (M + 1) × tick_us`**: the Data layer validator rejects the file (F2 ranges and validator rule). The core never runs with an out-of-range value, because Data `Ready` is a precondition (R11).
- **If a 64-bit value round-trips through JSON** (a save, a log, a vector): it is written as a decimal string and parsed back to `int`. Godot's JSON parser returns every number as a float, so a numeric `world_seed` above 2^53 would be silently corrupted (R6). `world_seed` is at most 2^63 − 1 (R13), so the string always parses into a non-negative GDScript `int`.
- **If a tick costs more than `sim_slice_budget_ms`** (F6): the device is below min-spec. Catch-up and spike frames stutter, but no time is lost. Debt still drains while `r_net > 0`. If a foreground hitch pushes debt above `T_us`, it hands off. That is logged and therefore replayable, but approximate, which the Player Fantasy states for below-min-spec devices. `catching_up` and `debt_us` make it visible. The balance simulator and `run_ticks` never see it, because tools have no frame budget.

**Degenerate use**
- **If a player pauses repeatedly to dodge a time-limited event**: nothing is gained. Paused time is owed (R9), so the timer's due tick arrives on resume as it would have live.
- **If a player sets the device clock forward**: the core is unaffected, since it never reads the device clock to decide ticks. The effect arrives only through `GameClock.utc_s()` as a larger gap, and the offline cap and server-time policy are Offline progress's and Leaderboards' (R7).

## Dependencies

**Upstream (this system depends on).** All three upstream GDDs exist and each already names this system in its own Dependencies section, so the two-way record holds.

| System (#) | Hard / soft | Interface | What this system takes |
|---|---|---|---|
| Deterministic RNG (2) | Hard | `derive(domain_id, key)` (R3, R4); `new_world_seed` with injected `entropy_fn`, `clock_fn`, `install_id` (R2), **which must return a 63-bit seed, a pending change to RNG R2 (OQ-13)**; the `fatal_sink` contract and poison values (R9); the guarantee that outcomes are identical across implementations (R12) | The core makes `derive` available in every phase through the handler context, supplies the port's `fatal_sink`, and never draws itself |
| Data layer and content pipeline (3) | Hard | `Ready` state before tick 1 (R10 of that GDD); `config` and `sim_params`; the F1 content hash | The core runs no tick until `Ready`, reads `config.tick_rate`, `live_catchup_max_ticks`, `offline_threshold_s`, `command_queue_max`, `command_drain_max`, `event_buffer_hard_cap`, and holds the F1 hash for saves and the verifier |

**Downstream (systems that depend on this one).** None has a GDD yet except Dev tooling (43). Each must list this system, state which phase or phases it registers into, give its `order` values, and say what it does when the core is `Failed` or `Paused`.

| System (#) | Hard / soft | Interface | What it gets |
|---|---|---|---|
| Command layer (5) | Hard | `submit(command)`; P1 drain and `seq` order (R6) | A single ordered queue and a defined application point |
| Local save and migration (6) | Hard | `snapshot_core()` and `restore_core()`; `world_seed`, `tick`, `next_command_seq`, `sim_version`; the `state_trusted` flag; the `Failed` record including `failed_at_tick` (R10, R14) | The core's contribution to a save and a signal to refuse unsafe overwrites. Recovery policy is Save's |
| Member model (8), Combat (10), Zones and hunt (11), Utility AI (12), Party (13), Golden Boss (14), Recruitment (15), Retention (16), Gold economy (27), Guild and buildings (30), Member state machine (41), and every other feature with per-tick behaviour | Hard | `register(phase, order, owner_id, handler)` (R4); the handler context (R5) | A place in the tick, a stable order, access to `derive`, events and commands |
| Event bus and history log (42) | Hard | The per-tick event buffer; the P6 `publish` handler (R2, R5) | Events in emission order, discarded if the tick fails (R10) |
| Offline progress (31) | Hard | A whole-tick `gap_us` from `advance` and its logged `handoff` (R8); `GameClock.utc_s()` (R7); `skip_ticks(k, resolver_version)`, with no timeout (Edge Cases); anchored deadline-tick timers (R5); the UTC absence rule (R7) | A single time path and a defined, replayable hand-off, so it never needs to read a clock or invent a tick count. It owns the timer backlog a long gap owes, the re-anchoring of crossed due ticks, and resolving well within `T` |
| Leaderboards and anti-cheat (35) | Hard | `run_ticks` for server replay; the command log with `handoff` and `skip` entries (R6, R8); `sim_version` (R12); `world_seed` | The same loop and the same hand-off path on a server, and a version to select the core by. Leaderboards owns the log size bound and the rule that a run with an unlogged gap is unranked |
| Realtime world view (38), Audio (40) | Hard | The read-only facade: P6 events, `tick`, `alpha`, `catching_up`, `debt_us` (R15, F3, R8) | Presentation inputs that can never mutate state, plus a signal to show "catching up" |
| Dev tooling and parity harness (43) | Hard (build-time) | `SIM_VERSION`, `phase_table_hash` (F5), `run_ticks` entry (R16) | A single version integer and a headless entry point; resolves Dev tooling OQ-1 |
| Local push notifications (46) | Soft | `tick`, `GameClock` | The data to schedule the next hourly boss notification |

"Hard" means the dependent cannot meet its own acceptance criteria without this system. Nothing here is soft except push notifications, which can work from the clock alone.

**Consistency notes for the systems index.** The index lists Sim core as a dependency of 5, 6, 8, 10, 30, 31, 35, 38, 40, 42 and 46. Systems 9, 11, 12, 13, 14, 15, 16, 24, 27, 28, 41 and others also register per-tick handlers, but their index rows do not say so. Phase 5 does not propose adding them all: it is enough that each feature's own GDD names the phase it registers into. The two upstream rows (RNG 2, Data layer 3) are correct as listed.

**Provisional assumptions about undesigned systems.**
1. Offline progress (31) can work within a whole-tick `gap_us`, a logged `handoff`, and `skip_ticks(k, resolver_version)` with no time limit. It re-anchors every crossed due tick before the skip (R5), resolves well within `T`, and keeps its resolver's results within a stated tolerance of exact ticks at the `T` boundary, so the threshold is not a lever a player can farm. It owns the trust policy for the UTC absence delta (R7). If it needs a different hand-off (for example a dry-run query for the next timed event), R8 and the Edge Cases change. Open Questions OQ-1.
2. Local save (6) accepts that a `Failed` core means "keep the last good save" with no rollback (R10). It owns all recovery policy: autosave cadence, generations, any pre-save invariant check, any crash marker, and whether a reload avoids `failed_at_tick`. If it needs a core primitive for that, R10 changes. OQ-2.
3. The Event bus (42) accepts a buffer owned by the core and delivers it in one P6 handler. OQ-3.
4. A GDScript host can hold `acc_us` and `tick` as 64-bit signed integers without loss (F2, R13). It does, as GDScript `int` is 64-bit signed, which is why every counter is specified as non-negative int64 and never uint64.

## Tuning Knobs

The knobs below are `config.csv` rows (`key,value`, as the existing file). They are game-core parameters, not balance numbers: none changes how fast the guild earns, only how the loop keeps time. The five new keys do not exist in `data/config.csv` yet; the Data layer must add them to its schema (Open Questions OQ-4).

| Knob | Where | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `live_catchup_max_ticks` (M, F2) | `config.csv` | 5 | 1 – 20 | One unsliced `advance` costs `M × c_tick`, so a host that does not slice stutters (F6). It also raises the `T` floor `(M + 1) × tick_us` | 1: an unsliced call clears one tick per frame. That is harmless, because slicing (R17) supplies the throughput | `offline_threshold_s` (validator rule), `tick_rate`, host time-slicing (R17) |
| `offline_threshold_s` (T, F2) | `config.csv` | 60 (provisional; the P1 spike sets it to at most `T_max`, F6, OQ-6) | Validator accepts whole seconds 1 – 600 with `T_us ≥ (M + 1) × tick_us`; safe 30 – 600 | The drain of a gap of `T` exceeds the catch-up budget `B` (F6 table: at 10 ms per tick, 60 s takes 15 s) | More gaps go to the aggregate resolver. Below 30 s, a short phone lock switches the guild to approximate rules, against the Player Fantasy; that is a creative-director decision (F6) | `live_catchup_max_ticks`; host time-slicing; Offline progress's tolerance (about 1% XP drift, GDD §18.1) |
| `command_queue_max` (R6) | `config.csv` | 1,000 | 100 – 10,000 | A tap-flood or a bug grows memory | A quick sequence of legitimate orders (a "send all" action) is dropped | `command_drain_max`; the Command layer's batch size |
| `command_drain_max` (R6) | `config.csv` | 25 (provisional; at an estimated 20–100 µs per command in GDScript, 100 would cost 2–10 ms in one P1) | 10 – 1,000 | One P1 can take many commands and break the single-tick budget (F6) | A large legitimate burst takes several ticks to apply, visibly | `command_queue_max` (must be ≤ it); the P1 budget share (F6) |
| `event_buffer_hard_cap` (Edge Cases) | `config.csv` | 2,000 (provisional; set from the P1 spike's events-per-tick peak, about 10–20× it) | 500 – 10,000 | A runaway handler costs many milliseconds and megabytes before it is caught | A legitimate busy tick (a raid, a mass drop) ends the run, unless its owner bounds per-tick emission (Edge Cases) | The soft warning at half the cap; P6 cost; coalesced `commands_dropped` (one per tick) |

**Interactions.**
- `live_catchup_max_ticks` and `offline_threshold_s` are coupled only through the validator floor `T_us ≥ (M + 1) × tick_us` (F2). With mandatory one-tick slicing (R17), drain time depends on `c_tick`, not on `M`: `t_drain = D / r_net` (F6 table). The earlier frame-count figures (125 frames at `M = 5`) assumed a zero-cost tick and no slicing, and are withdrawn.
- `offline_threshold_s` is set from measurement: `T ≤ T_max = B × r_net / tick_rate`, with `B = 10 s` (F6). At the defaults, `T = 60 s` holds while the p95 `c_tick` is at most about 6.9 ms.
- `command_queue_max` and `command_drain_max` do not interact with F2. Together they bound the memory of the queue and the cost of one P1.

**Not knobs, and where their values live.**
- **`tick_rate`** is read from `config.csv` but is fixed in a shipped build. Changing it changes the meaning of every saved tick count, so it is a `sim_version` bump with a save migration (Edge Cases). It is not a balance lever; it is a performance and feel constant (F1, F6).
- **`SIM_VERSION`**, the phase order (R2), the fail codes (R10) and the `phase_table_hash` framing (F5) are fixed by design. (`handoff_timeout_s` was removed in the third revision: a pending hand-off has no timeout.) Changing any is a breaking change under Dev tooling R7.
- **`sim_share`, `frame_budget_ms` and the catch-up budget `B`** in F6, and the host's `sim_slice_budget_us = sim_share × frame_budget_us` (R17), are design or host constants, not game data.
- **Handler `order` values** are not knobs. They are assigned in each owner's GDD (R4).

*Lens applied:* systems-designer (Section G). Knobs were derived from the Section D variable table: every variable marked `data file` is a row above; every `constant` is listed under "not knobs".

## Visual/Audio Requirements

None. This is a Core system with no visual or audio surface. The one screen its `Failed` state causes is specified under UI Requirements.

## Game Feel

None directly. The core's contribution to feel is that it never changes speed to hide slowness (Player Fantasy): a slow phone sees the guild move at less than real time, not at a different set of rules. The render interpolation value `alpha` (F3) is exposed so presentation can smooth between ticks at 10 Hz, but how it is used is World view's to design. The per-tick cost budget (F6) is measured on a real phone in the P1 spike (OQ-6).

## UI Requirements

One screen, shown only when the core enters `Failed` in a shipped build (R10, AC-35):

- **Content:** a localised title and body ("something went wrong — your last save is safe"), the `sim_version`, and the error code (`fail_code`, R10). No stack trace and no file paths are shown to players.
- **Actions:** "Reload last save", which constructs a new core instance (Edge Cases) and loads the last good save, plus "Quit". Never "continue", because state is untrusted (R10). Any further recovery option (an older backup, skipping the failing stretch, a read-only view of the guild) is Local save's and Guild screens' decision (OQ-2).
- **Loss statement:** the body says that orders given since the last save are lost (R10).
- **Strings** come from the always-available UI string set, not from `data/` (same rule as the Data layer's fatal screen), because a core failure may be a data failure.
- **Dev builds** print the failing message and the `owner_id` of the handler that was running to the console.

The screen's layout and wording belong to Guild screens (39) and Localization (4). This GDD requires only that it exists and what it offers.

## Cross-References

| This GDD | References | Section there | Nature |
|---|---|---|---|
| R3, R4, R5, Dependencies | Deterministic RNG | R3 (per-event seeding), R4 (domain IDs) | The core exposes `derive(domain_id, key)` and never draws itself |
| R10, Edge Cases | Deterministic RNG | R9 (invalid calls fail loudly; engine-port sink and poison values) | The core supplies the port's `fatal_sink` and defines what "commits none of that step's results" means: discard buffers, no rollback |
| R11, R13 | Deterministic RNG | R2 (the world seed; `new_world_seed` with injected functions) | The core calls it for a new guild and reads the seed from a save otherwise. **Conflict pending:** R13 requires a 63-bit seed, and RNG R2 still says 64-bit (OQ-13) |
| R14 | Deterministic RNG | R11 (what is saved: only `world_seed`) | The core adds `tick`, `next_command_seq` and `sim_version` and nothing else |
| R12, F5 | Deterministic RNG | R12 (same results everywhere; replay from `world_seed` + command log + sim version) | `sim_version` and `phase_table_hash` are the parts of "sim version" this system owns |
| Edge Cases (same-tick events) | Deterministic RNG | Edge Cases (order of state changes is the Sim core's) | Phase order (R2) and handler order (R4) are that order |
| R11, States | Data layer and content pipeline | R10 (load once), States (`Ready`, `Failed`) | The core starts only on `Ready` |
| Tuning Knobs, F1, F2 | Data layer and content pipeline | R2 (table inventory: `config`, `sim_params`) | The five new keys must be added to the `config` schema and validator (OQ-4) |
| R12, F5, R16 | Dev tooling and parity harness | R7 (version rule), R8 (event groups), Dependencies (OQ-1) | Settles OQ-1: `sim_version` is one integer owned here; `run_ticks` is the headless entry |
| Overview, R2, F4 | `JX1_Tycoon_GDD.md` | §3.2 (layers, fixed timestep), §3.4 (tick order), §6.13 / `golden_boss_interval_min` | Source requirements this GDD specifies |
| R8, Edge Cases | `JX1_Tycoon_GDD.md` | §10 (offline progress, caps, aggregate not tick-by-tick), §3.5 (LOD shared with offline) | Why a long gap is handed off instead of run |
| R5, R13 | `GODOT_PORT.md` | Rules for identical results (RNG, 64-bit integers, `float` order) | Integer-only core state; handler float rules deferred to owners |
| F6 | `.claude/docs/technical-preferences.md` | Performance Budgets (60 fps, 16.6 ms) | The frame budget F6 divides |

## Acceptance Criteria

Story types: **[Logic]** automated unit test (blocking), **[Integration]** integration test or documented device run, **[UI]** retained screenshot. `[PENDING: engine]` means it needs the Godot port or a device and cannot run in Python yet. Unless stated, every case starts from a fresh core (constructed, booted, restored or seeded, sealed and started) with `tick_us = 100,000`, `M = 5`, `T_us = 60,000,000`. A case that ends in `Failed` or with a hand-off pending is never followed by another case on the same core. "Fatal (code X)" means the state is `Failed`, `fail_code = X`, `fail_owner_id` is as stated (or `"core"`), `tick` is unchanged, and the injected `error_reporter` received exactly one message. **Runners:** GDScript cases run under gdUnit4 in `tests/unit/sim_core/` (`[system]_[feature]_test.gd`). Python cases, marked *(Python)*, run under `pytest tests/unit/sim_core/`, and CI runs both. No core implementation exists yet in either language, so every Logic AC waits on it. `[PENDING]` marks a dependency beyond that.

**Time and phases**
- **AC-1 [Logic] (R1, F1)**: **GIVEN** `config.tick_rate` of 20, 10, 8 and 1, **WHEN** `tick_us` is computed, **THEN** it is 50,000, 100,000, 125,000 and 1,000,000.
- **AC-1b [Logic] [PENDING: validator, OQ-4] (F1)**: **GIVEN** `tick_rate` of 3 and 12, **WHEN** the validator runs, **THEN** each is rejected by the divisor rule. **GIVEN** 0 and 25, **THEN** each is rejected by the range rule. Every error names `tick_rate`, and the core does not boot. **GIVEN** each of {1, 2, 4, 5, 8, 10, 16, 20}, **THEN** it is accepted.
- **AC-2 [Logic] (R2, R3)**: **GIVEN** one recording handler registered in each of P1 to P6, **WHEN** one tick runs, **THEN** they run in order P1…P6, then `tick` is 1.
- **AC-3 [Logic] (R3, R5, R10) — a tripwire, not a proof.** A token lint cannot be complete (dynamic `call("…")` evades any lint), so this guards against accidents, and code review covers the rest.
  - **Tool.** `python tools/ci/lint_core.py <dir>` prints one `file:line:token` line per hit and a final `scanned N files` line. It exits 0 with no hits and non-zero with hits **or with N = 0**.
  - **Two passes.** Pass 1 records the string argument of every `preload(…)`, `load(…)` and `extends "…"`. It fails if the path is outside the core directory, except for the allow-listed upstream interfaces: the RNG module and the Data layer's read interface (R3 forbids features, not upstream contracts). Pass 2 strips comments and every GDScript string form (`"…"`, `'…'`, `"""…"""`, `r"…"`, `&"…"`, `^"…"`), then matches whole tokens.
  - **GDScript tokens.** `randi`, `randf`, `randi_range`, `randf_range`, `randfn`, `randomize`, `rand_from_seed`, `seed`, `RandomNumberGenerator`, `Crypto`, `shuffle`, `pick_random`, `hash`, `Time`, `OS`, `Engine`, `Thread`, `Mutex`, `WorkerThreadPool`, `FileAccess`, `DirAccess`, `ResourceLoader`, `ResourceSaver`, `ConfigFile`, `JSON`, `ProjectSettings`, `ClassDB`, `instance_from_id`, `signal`, `emit_signal`, `connect`, `Node`, `SceneTree`, `get_tree`, `get_node`, `Timer`, `Tween`, `await`, `call_deferred`, `set_deferred`, `create_timer`, `assert`, and the `$` and `%` node shorthands. Every core class `extends RefCounted` or another core class, and no inner class extends anything else.
  - **Python tokens.** Imports of feature modules, `random`, `secrets`, `time`, `datetime`, `os`, `uuid`, `threading`, `asyncio`, `importlib`, and the `__import__` and `hash` builtins. Python uses an `ast` walk, not regex, so variable names such as `time_left` never match.
  - **THEN.** It exits 0 on the core. On a fixture with one line per banned token, it prints each token by name. On a fixture whose comments and strings mention every token, that uses `NodePath`, `phase_table_hash` and `HashingContext`, and that loads an in-core sibling and the allow-listed RNG module, it exits 0. On an empty directory it exits non-zero.
  - A second, shorter profile (clock, random, `await`, `call_deferred`, `Timer`, node access) runs over feature handler directories (R5).
- **AC-4 [Logic] (R4, F5)**: **GIVEN** three handlers in one phase with orders 300, 100 and 200 registered in each of the 6 possible sequences, **WHEN** a tick runs, **THEN** they always run 100, 200, 300, and `phase_table_hash` is identical for all 6 sequences.
- **AC-5 [Logic] (R4)**: **GIVEN** two handlers registered at the same `(phase, order)`, **WHEN** boot finishes, **THEN** `register` returns false for the second call, the state is `Failed` with `fail_code = 1`, the message names both `owner_id`s, and no tick runs.
- **AC-6 [Logic] (R4, Edge Cases)**: **GIVEN** registrations with phase 0, phase 7, order −1, order 2^31, and `owner_id` "Bad ID", **WHEN** each is attempted, **THEN** each causes a boot error. **GIVEN** a `register` call in each of `Ready`, `Running` and `Paused`, **THEN** the call is refused and the core is `Failed`. **GIVEN** a `register` call in `Unloaded` or `Failed`, **THEN** it is refused and the state is unchanged. **GIVEN** `order` 0 and 2^31 − 1, phase 1 and 6, and `owner_id` of 1 and 48 characters, **THEN** each is accepted, and an `owner_id` of 49 characters is a boot error. **GIVEN** `[PENDING: engine]` a lambda, a `bind()` result, an invalid Callable or a method taking two arguments, **THEN** each is a boot error with `fail_code = 2`.
- **AC-7 [Logic] (F5)**: **GIVEN** a registration table, **WHEN** one `order` changes by 1, or one `owner_id` changes, **THEN** `phase_table_hash` changes. **GIVEN** a one-entry table `(2, 100, "member_state_machine")`, **THEN** the digest equals Python `hashlib.sha256` over the F5 bytes computed in the test (`02 00000064 14` followed by the UTF-8 name). The cross-implementation equality waits for both ports.

**Handlers, commands, events**
- **AC-8 [Integration] [PENDING: RNG implementation, or a stub with the RNG GDD's golden vectors] (R5)**: **GIVEN** a handler that calls `derive(1, [7])` and draws once, **WHEN** the same call is made outside the core with the same `world_seed`, **THEN** the two draws are equal.
- **AC-9 [Logic] (R5, Edge Cases)**: **GIVEN** a P2 handler that calls `advance(0)`, and in separate cases `run_ticks(1)`, `skip_ticks(1, 1)` and `inject_handoff(100,000)`, **WHEN** it runs, **THEN** each is fatal (code 4) with `fail_owner_id` equal to that handler's owner.
- **AC-10 [Logic] (R1, R6)**: **GIVEN** a fresh core with `tick = 0` and commands A, B, C submitted in that order, **WHEN** one tick runs, **THEN** their `seq` values are 1, 2, 3, P1 of tick 0 applies A, B, C in that order, the command log holds `(0, 1, A)`, `(0, 2, B)`, `(0, 3, C)`, and `tick` is 1.
- **AC-10b [Logic] (R6)**: **GIVEN** a handler that submits a command during tick N, **THEN** it applies in P1 of tick N+1, not N.
- **AC-11 [Logic] (R6, Edge Cases)**: **GIVEN** `command_queue_max = 100` and `command_drain_max = 100`, **WHEN** 103 commands are submitted before tick N, **THEN** the first 100 get `seq` 1–100, the last 3 return `seq = 0`, and a stub P6 publisher receives, in tick N, exactly one `commands_dropped` event, the record `(1, 3, 0, 0, 0)`. After tick N's P1 drains the queue, the next `submit` is accepted with `seq = 101`. **GIVEN** state `Failed`, **THEN** `submit` returns 0. **GIVEN** state `Paused`, **WHEN** a command is submitted, then `resume()` and one tick run, **THEN** `submit` returned a non-zero `seq` and the command was in that tick's `ctx.commands()`.
- **AC-13 [Logic] (Edge Cases)**: **GIVEN** a stub P6 publisher at order 100 that records `ctx.events()`, and P6 emitters at order 50 and 200, each emitting one event in tick N, **WHEN** ticks N and N+1 run, **THEN** both events are delivered in tick N+1, not N.
- **AC-13b [Logic] (Edge Cases)**: **GIVEN** `event_buffer_hard_cap = 2,000` and a handler emitting 1,000 events in one tick, **THEN** the tick completes and `event_soft_cap_count = 0`. **GIVEN** 1,001, **THEN** the tick completes, `event_soft_cap_count = 1` and one warning is logged. **GIVEN** 1,001 in each of two consecutive ticks, **THEN** `event_soft_cap_count = 2` and still exactly one warning is logged. **GIVEN** 2,000, **THEN** the tick completes. **GIVEN** 2,001, **THEN** it is fatal (code 7), attributed to the emitting handler.

**Clock and `advance`**
- **AC-14 [Logic] (R7)**: **GIVEN** a fake `GameClock` injected at construction that counts calls, **WHEN** the call counts are recorded before `seal()`, then `seal`, `start`, 1,000 ticks through `advance`, 100 through `run_ticks`, one hand-off and its `skip_ticks` run, **THEN** both counts are unchanged.
- **AC-15 [Logic] (R8, F2)**: **GIVEN** the default values and `acc_us = 0`, with each bullet on a fresh core:
  - **WHEN** `advance(1,000,000)` runs, **THEN** `n = 5`, `acc_us = 500,000`, `gap_us = 0`, `catching_up = true`. **WHEN** `advance(33,000)` runs next, **THEN** `n = 5`, `acc_us = 33,000`, `catching_up = false`.
  - **WHEN** `advance(600,050,000)` runs from `acc_us = 0`, **THEN** `n = 0`, `acc_us = 50,000`, `gap_us = 600,000,000`, `catching_up = false`, `alpha < 1.0`, and the command log's last entry is `handoff {at_tick: 0, gap_us: 600,000,000}` with no `seq`.
- **AC-15b [Logic] (F2 boundaries)**: **WHEN** `advance(60,000,000)` runs, **THEN** `gap_us = 0`, `n = 5`, `acc_us = 59,500,000` and `catching_up = true`. **WHEN** `advance(60,000,001)` runs on a fresh core, **THEN** `gap_us = 60,000,000` and `acc_us = 1`. **WHEN** `advance(0)` runs on a fresh core, **THEN** `n = 0`. **WHEN** `advance(1,000,000, 1)` runs on a fresh core, **THEN** `n = 1` and `acc_us = 900,000`. With `max_ticks = 0`, `n = 0`.
- **AC-16 [Logic] (F2)**: **GIVEN** the default values and the list `[0, 1, 99,999, 100,000, 16,667, 10,000,000, 60,000,000, 300,000,000, 600,000,000]` with `−5` and `2,000,000` added, cycled in order to 10,000 `advance` calls, with every hand-off followed by the matching `skip_ticks` and `pause()`/`resume()` toggled on every 7th call, **WHEN** each call completes, with negative input counted as 0, **THEN** `elapsed_us + acc_before = n × tick_us + acc_after + gap_us` exactly, `n ≤ 5`, `acc_after ≤ T_us`, `gap_us mod tick_us = 0`, and `gap_us = 0 or gap_us ≥ T_us`.
- **AC-16b [Logic] (F2, R8 pending)**: **GIVEN** a pending hand-off created by `advance(600,050,000)` (`acc_us = 50,000`), **WHEN** `advance(10,000,000)` runs, **THEN** 0 ticks run, `gap_us = 0`, `acc_us = 10,050,000`, and the state is `Running`. **WHEN** `advance(3,600,000,000)` (a 1 h absence) then runs, **THEN** it is not fatal and `acc_us = 3,610,050,000`. **WHEN** `skip_ticks(6,000, 1)` and `advance(0)` follow, **THEN** a second hand-off of `gap_us = 3,610,000,000` is logged after the `skip` entry, and `acc_us = 50,000`. **GIVEN** a pending core with `acc_us = 50,000`, **WHEN** `advance((1 << 62) − 50,000)` runs, **THEN** it is accepted with `acc_us = 2^62`. **WHEN** `advance(1)` then runs, **THEN** it is fatal (code 5) and `acc_us` is unchanged.
- **AC-17 [Logic] (F2)**: **GIVEN** `M = 1` and `acc_us = 0`, **WHEN** `advance(1,000,000)` and then 9 calls of `advance(0)` run, **THEN** each call runs exactly 1 tick, and afterwards `acc_us = 0` and `catching_up = false`.
- **AC-17b [Logic] (Edge Cases)**: **GIVEN** 3 calls with `elapsed_us = −5` on one core instance, **THEN** `clock_anomaly_count = 3`, `acc_us` is unchanged, and exactly 1 warning reaches the injected log sink. **GIVEN** `elapsed_us = 2^62` on a fresh core, **THEN** it is accepted: a hand-off with `gap_us = 4,611,686,018,427,300,000` and `acc_us = 87,904`. **GIVEN** `2^62 + 1` on a fresh core, **THEN** it is fatal (code 5). **GIVEN** *(Python)* `elapsed_us = 1.5`, **THEN** it is fatal (code 5).
- **AC-17c [Logic] [PENDING: validator, OQ-4] (Tuning Knobs)**: **GIVEN** `offline_threshold_s` of 0, 601 and 1.5, **THEN** each is rejected. **GIVEN** 1 and 600, **THEN** each is accepted. **GIVEN** `tick_rate = 1` and `M = 5`, **THEN** `offline_threshold_s = 5` is rejected by the `T_us ≥ (M + 1) × tick_us` rule and 6 is accepted. **GIVEN** `M` of 0 and 21, `command_queue_max` of 99, `command_drain_max` of 9 or above `command_queue_max`, and `event_buffer_hard_cap` of 499, **THEN** each is rejected, and every error names its key.
- **AC-18 [Logic] (F3)**: **GIVEN** a fresh core and `advance(33,000)`, **THEN** the facade's `abs(alpha − 0.33) < 1e-9`. **GIVEN** `advance(1,000,000)` on a fresh core (`acc_us = 500,000`), **THEN** `alpha = 1.0`. **GIVEN** a handler context, **THEN** its public names are exactly the context row of the API surface table.
- **AC-19 [Logic] (F4)**: **GIVEN** `tick_rate = 10`, **THEN** `ticks(3,600) = 36,000`, `ticks(8 × 3,600) = 288,000`, `ticks(24 × 3,600) = 864,000`, `seconds(36,000) = 3,600` and `seconds(35,999) = 3,599`. **GIVEN** `tick_rate = 20`, **THEN** `ticks(3,600) = 72,000`.
- **AC-20 [Logic] (R9)**: **GIVEN** `pause()` called from a P2 handler during tick N, **THEN** P3 to P6 of tick N still run, tick N commits, and the state is `Paused`.
- **AC-20a [Logic] (R9, F2)**: **GIVEN** `Paused` with `acc_us = 0`, **WHEN** `advance(10,000,000)` runs, **THEN** 0 ticks run and `acc_us = 10,000,000`. **WHEN** `resume()` and then `advance(16,000)` run, **THEN** 5 ticks run and `acc_us = 9,516,000`. The paused time is owed.
- **AC-20c [Logic] (R9, R7)**: **GIVEN** a core restored from a save and started, then paused before its first `advance`, **WHEN** the cold-start absence `advance(45,000,000)` arrives while `Paused`, **THEN** `acc_us = 45,000,000`. **GIVEN** instead `advance(90,000,000)` while `Paused`, **THEN** it hands off `gap_us = 90,000,000` with 0 ticks run.
- **AC-20d [Logic] (R9, F2)**: **GIVEN** a handler in tick 2 of `advance(1,000,000)` (5 ticks planned) that calls `pause()`, **THEN** the call returns `ticks_run = 3` and `acc_us = 700,000`, and the conservation identity holds.
- **AC-20e [Logic] (R9)**: **GIVEN** a state other than `Paused`, **THEN** `resume()` returns false.
- **AC-20b [Logic] (Edge Cases)**: **GIVEN** `Ready`, **THEN** `pause()` returns false and the state is unchanged.

**Failure, startup, state**
- **AC-21 [Logic] (R10)**: **GIVEN** command X submitted before tick 7, a stub P6 publisher, a P2 handler that emits an event, a P3 handler at order 100 that calls `ctx.fail(1001, "x")` in tick 7, and a second P3 handler at order 200, **WHEN** tick 7 fails, **THEN**:
  - the state is `Failed`, `tick` is still 7 and `failed_at_tick = 7`;
  - neither the order-200 P3 handler nor any P4–P6 handler ran, and the publisher received no tick-7 event;
  - X was in tick 7's `ctx.commands()`, yet the command log's last entry is from tick 6 or earlier.
- **AC-21b [Logic] (R10)**: **GIVEN** the same setup on a fresh core, after the failure, **THEN** `state_trusted` is false, `fail_code = 1001`, and `fail_owner_id` is the order-100 P3 owner. `snapshot_core()` returns an error, and `advance` returns `{ticks_run: 0, gap_us: 0}`. A second `ctx.fail(1002)` attempted by a test hook does not change `fail_code`.
- **AC-21c [Logic] (Edge Cases)**: **GIVEN** five P6 consumer handlers in order, the third of which calls `ctx.fail(1001, "x")`, **WHEN** tick N runs, **THEN** consumers 1–2 received tick N's events, consumers 4–5 were never called, and the core is `Failed`.
- **AC-22 [Logic] [PENDING: RNG implementation or a stub that calls the sink] (R10)** *(Python)*: **WHEN** a P3 handler's `derive` triggers the default sink, which raises `RngError` inside tick 7, **THEN** the loop catches it at the tick boundary, and the outcome matches AC-21 except `fail_code = 10`. **WHEN** the sink fires outside a tick (a bad `skip_ticks`), **THEN** the call boundary catches it, and the result is `Failed` with code 6 and no exception reaching the caller.
- **AC-23 [Logic] [PENDING: engine] (R10, GDScript only)**: **GIVEN** the GDScript port with a recording `error_reporter` injected, **WHEN** a handler calls `ctx.fail` or the port's sink fires, **THEN** the reporter receives exactly one message containing the `owner_id`, and the state matches AC-21 and AC-21b. **GIVEN** each core sink site (a bad `skip_ticks`, `elapsed_us` out of range, the event cap, a freed owner, a returned value), **THEN** after the sink returns, the call changed no core field other than the `Failed` record. That proves there is no fall-through. The absence of `assert` is checked by the AC-3 lint, not at runtime.
- **AC-23b [Logic] [PENDING: RNG poison generator, RNG R9] (R5)**: **GIVEN** a handler that calls `ctx.fail(1001, "x")` and then 3,000 `emit` calls, one `submit` and one `derive`, **THEN** `event_soft_cap_count = 0`, no event cap fired, `next_command_seq` is unchanged, and `derive` returned the RNG R9 poison generator. **GIVEN** a handler that returns a non-null value, **THEN** it is fatal (code 9) with that handler's `owner_id`.
- **AC-24 [Logic] (R11)**: **GIVEN** a Data layer in `Failed`, **WHEN** the core boots and `seal()` is called, **THEN** `seal()` is refused naming the Data layer, the state stays `Booting`, `advance` runs 0 ticks, and "data layer failed" is reported. **GIVEN** a `Booting` core with no seed set, **THEN** `seal()` is refused naming the seed. **GIVEN** a non-empty command queue or event buffer at `seal()` (injected by a test hook), **THEN** it is refused naming it. **GIVEN** `submit` before `seal()`, **THEN** it returns 0. **GIVEN** a new guild, **THEN** `new_world_seed` is called once with the injected functions; **GIVEN** a save, **THEN** the seed comes from the save and `new_world_seed` is not called.
- **AC-25 [Logic] (States)**: **GIVEN** a matrix of the 6 states × the operations `boot`, `restore_core`, `seal`, `start`, `pause`, `resume`, `register` (valid arguments), `advance(0)`, `run_ticks(1)`, `snapshot_core`, `skip_ticks(1, 1)`, `inject_handoff(100,000)`, `submit` and `dispose`, each case on a fresh core driven into its state, **THEN** the resulting state of every case is asserted against the States table: exactly the 9 listed transitions change state, and every other case leaves the state unchanged (or, for `skip_ticks` in `Running` or `Paused` with no pending hand-off, enters `Failed` per the table). **GIVEN** a `Failed` instance, **WHEN** the host constructs a new instance, **THEN** the new one reports `Unloaded`, and the old one still reports `Failed` and refuses every non-query call.
- **AC-26 [Logic] (Edge Cases)**: **GIVEN** `advance(1,000,000)` or `run_ticks(5)` in each of `Unloaded`, `Booting`, `Ready` and `Failed`, **THEN** 0 ticks run and `debt_us = 0` afterwards; the first three log one error per call, `Failed` logs none. **GIVEN** `run_ticks` while `Paused` or while a hand-off is pending, **THEN** 0 ticks run and an error is returned. **GIVEN** `boot()` twice, **THEN** the second call logs an error and changes nothing.

**Version, save, headless**
- **AC-27 [Logic] (R12)**: **GIVEN** the core, **THEN** `SIM_VERSION` is an integer in 1 … 2^32 − 1, declared with `const` (GDScript) or as a module-level constant that a test cannot reassign (Python), and equal to the value in `snapshot_core()`. `[PENDING: Dev tooling 43]` It also equals the golden-vector header.
- **AC-27b [Integration] [PENDING: Dev tooling `parity check`, 43] (R12)**: **GIVEN** a change to a handler `order` with no bump, **WHEN** Dev tooling `parity check` runs, **THEN** it fails as "breaking change without a version bump" (Dev tooling R7).
- **AC-28 [Logic] (R13)**: **GIVEN** the core's state fields (`tick`, `acc_us`, `pending_gap_us`, `next_command_seq`, `world_seed`), **THEN** each is an `int` and non-negative after boot, after 100 ticks and after a hand-off. There are two cases, one pytest and one gdUnit4.
- **AC-29 [Integration] (R14)**: **GIVEN** a test feature that saves its own counter, **WHEN** the core runs 100 ticks, `snapshot_core()` is taken, a new core instance calls `restore_core()` in `Booting`, seals, starts and runs 100 more, **THEN** the restored run's event stream equals ticks 100–199 of a single 200-tick run, the snapshot has exactly `world_seed`, `tick`, `next_command_seq`, `sim_version`, and `acc_us` is 0 after restore. **GIVEN** a snapshot whose `sim_version` differs, **THEN** `restore_core()` is refused.
- **AC-29b [Logic] (R6, R13, R14, Edge Cases)**: **GIVEN** `world_seed = 2^63 − 1`, `tick = 2^53 + 1` and `next_command_seq = 2^53 + 3`, **WHEN** the snapshot is written to JSON by `snapshot_core()`'s serialiser and read back, **THEN** all three values are decimal strings in the JSON and equal after restore. **GIVEN** a snapshot whose `world_seed` string is `"9223372036854775808"` (2^63), **THEN** `restore_core()` refuses it. **GIVEN** `snapshot_core()` mid-tick (from a handler) or while a hand-off is pending, **THEN** it returns an error, not a fatal.
- **AC-30 [Logic] (R16)**: **GIVEN** two cores from equal starts, **WHEN** one runs `run_ticks(50)` and the other 10 calls of `advance(5 × tick_us)`, **THEN** both have `tick = 50`, `acc_us = 0` and identical event streams. **GIVEN** `M = 20` and 3 calls of `advance(20 × tick_us)` against `run_ticks(60)`, **THEN** the same holds with `tick = 60`.
- **AC-31 [Logic] (Edge Cases)**: **GIVEN** a hand-off of `gap_us = 600,000,000` (`tick_us = 100,000`) and a test stand-in for Offline progress:
  - **WHEN** it calls `skip_ticks(6,000, 1)`, **THEN** `tick` rose by 6,000, 0 handlers ran, the pending flag is clear, and a `skip {6000, 1}` entry is logged.
  - **GIVEN** instead `skip_ticks(5,999, 1)`, **THEN** it is fatal (code 6). **GIVEN** a fresh core with no pending hand-off and `skip_ticks(1, 1)`, **THEN** it is fatal (code 6).
  - **GIVEN** `advance(1,000,000)` called while the hand-off is pending, **THEN** 0 ticks run and `gap_us = 0`. After the skip, the next `advance(0)` runs 5 ticks (`M = 5`).
  - **GIVEN** `skip_ticks` in `Unloaded`, `Booting`, `Ready` or `Failed`, **THEN** it returns an error and the state and `tick` are unchanged.
- **AC-31b [Logic] (R5, Edge Cases)**: **GIVEN** `offline_threshold_s = 20`, `tick = 90` and a recording P5 handler, **WHEN** `advance(20,000,001)` hands off `gap_us = 20,000,000` and `skip_ticks(200, 1)` follows, **THEN** `tick = 290` and no handler ran for ticks 90–289. **WHEN** the next tick runs, **THEN** the P5 handler reads `ctx.tick() = 290`. The re-anchoring of feature timers across the skip is Offline progress's contract (R5) and is tested there.

**Cross-system and device**
- **AC-32 [Integration] (R11, Tuning Knobs)**: **GIVEN** the real `data/config.csv` with the five new keys added and validated, **WHEN** the core boots, **THEN** it reaches `Ready` with `tick_rate = 10`, `M = 5`, `T = 60 s`, `command_queue_max = 1,000`, `command_drain_max = 25` and `event_buffer_hard_cap = 2,000` `[PENDING: keys added by Data layer, OQ-4]`.
- **AC-33 [Integration] (R10, Interactions)**: **GIVEN** the Event bus (42) registered as the P6 handler, **WHEN** a tick fails after P2 emits an event, **THEN** the event is never delivered. `[PENDING: Event bus GDD]`
- **AC-34 [Integration] [PENDING: engine, P1 spike] (F6, R17) — BLOCKING (coding-standards Integration default).**
  - **Setup.** A release export on the named min-spec Android phone, in the Compatibility renderer with real rendering, using the max-roster save fixture `tests/fixtures/sim_core_max_roster` (the member count is stated by Member model 8; until then, the largest roster in the GDD).
  - **Run.** At least 36,000 ticks (one hour of game time, so the hourly P5 fires at least once), at 60 fps and again at 30 fps. Run once cold and once after 20 minutes of sustained load, logging the thermal state. Run with the profiler on and again with it off. Include the scripted spikes: a 25-command P1 burst, the hourly P5, and an events-per-tick peak at half the cap.
  - **Record.** p50, p95, p99, p99.9 and max per tick and per phase, plus the profiler-on minus profiler-off delta, written to `production/qa/evidence/`.
  - **PASS** only if all three hold:
    1. p99 `c_tick` ≤ `sim_slice_budget_ms` (8.33 ms at 60 fps, 16.67 ms at 30 fps), throttled run included.
    2. The profiler overhead is ≤ 0.1 ms per tick.
    3. The measured time-sliced drain of a gap of the shipped `T` is ≤ `B` (10 s).
  - **On pass**, `offline_threshold_s` is set to at most `T_max` (F6), and OQ-6 is updated.
  - **FAIL** otherwise. A failure escalates to the technical-director, and the remedy is handler cost or `tick_rate`, never this AC. If `T_max` < 30 s, the creative-director decides the Player Fantasy trade-off (F6).
- **AC-35 [UI] [PENDING: Guild screens 39, Localization 4] (UI Requirements)**: **GIVEN** a forced `Failed` in a dev build, **WHEN** the fatal screen shows, **THEN** a retained screenshot in `production/qa/evidence/` for each locale touched shows the localised message with the lost-orders statement, `sim_version`, the error code, "Reload last save" and "Quit", and no "continue" option, no stack trace and no file path. The forced `Failed` comes from a dev-only debug command that calls `ctx.fail` from a test handler.

**Added in revision (2026-11-16)**
- **AC-36 [Logic] (R15)**: **GIVEN** the presentation facade, **THEN** its public names are exactly {event stream, `tick`, `alpha`, `catching_up`, `handoff_pending`, `debt_us`}. This is an allow-list test, because GDScript cannot enforce read-only access. **GIVEN** a facade read before and after one tick from tick 4, **THEN** it reads 4 and then 5. **GIVEN** a pending hand-off, **THEN** `handoff_pending` is true, and it is false after the skip.
- **AC-37 [Integration] (R6, R8, R16)**: **GIVEN** a live run of 1,000 ticks with a fixed command script and one hand-off of 600 s resolved by a deterministic stand-in resolver, **WHEN** a test replay driver (R6) replays the command log on a fresh core with the same seed, registrations and resolver version, walking it in append order and calling `run_ticks`, `submit`, `inject_handoff` and `skip_ticks`, **THEN** the event stream, every command `seq` and the log itself are identical to the live run, and the final `tick` is 7,000 in both. **GIVEN** `[PENDING: Leaderboards 35]` the same log with the `skip` entry removed, **THEN** the replay's final `tick` is 6,000 lower and the driver's comparison returns a mismatch.
- **AC-38 [Logic] (R8, R17)**: **GIVEN** core A with `M = 5` and core B with `M = 20`, from equal starts, **WHEN** each runs `advance(45,000,000)` and then `advance(0)` until `catching_up` is false (capped at 90 calls), **THEN** A's first call returns `n = 5`, `acc_us = 44,500,000`, `gap_us = 0`, `catching_up = true`, and at the end both have `tick = 450`, `acc_us = 0`, and identical event streams and command logs.

**Added in second revision (2026-11-16)**
- **AC-39 [Logic] (R8, F2 example)**: **GIVEN** a pending 600 s hand-off, **WHEN** a 40 s lock arrives as `advance(40,000,000)`, **THEN** it is not fatal, 0 ticks run and `acc_us = 40,050,000`. After `skip_ticks(6,000, 1)`, `advance(0)` runs 5 ticks. **GIVEN** a 90 s lock instead, **THEN** after the skip, `advance(0)` logs a second hand-off of `gap_us = 90,000,000`.
- **AC-40 [Logic] (R6)**: **GIVEN** `command_drain_max = 100` and 250 queued commands, **WHEN** three ticks run, **THEN** P1's `ctx.commands()` holds `seq` 1–100, 101–200 and 201–250 respectively, and the log stamps them with ticks 0, 1 and 2.
- **AC-41 [Logic] [PENDING: engine] (R4)**: **GIVEN** a handler whose owner is an `Object` subclass, freed with `free()` before tick 3, **WHEN** tick 3 runs, **THEN** it is fatal (code 8) with that `owner_id`. **GIVEN** a `RefCounted` owner whose last outside reference is dropped, **THEN** the handler still runs, because the registry holds the owner.
- **AC-42 [Logic] (R17)**: **GIVEN** a recording profiler injected, **WHEN** one tick runs with 3 handlers, **THEN** it receives `begin`/`end` pairs for 6 phases and 3 owners in execution order, each handler's pair nested inside its phase's pair. **GIVEN** the same run with a profiler that returns the fixed sequence −1, 2^62 and NaN, **THEN** the event stream is identical to a run with no profiler. **GIVEN** `profiler = null`, **THEN** the tick runs and no profiler method is called.
- **AC-43 [Integration] [PENDING: engine] (R7, R9, R17)**: **GIVEN** a test host with a fake monotonic clock and a fake UTC clock:
  - **WHEN** the app is suspended (`NOTIFICATION_APPLICATION_PAUSED`/`RESUMED`) for a UTC time of 45 s while the monotonic clock advances 2 s, **THEN** the first `advance` after resume carries exactly 45,000,000 µs, and the 2 s monotonic delta is not also counted.
  - **WHEN** focus is lost without suspension for 5 s, **THEN** the frames keep advancing and no UTC absence is added.
  - **GIVEN** an in-app pause (`SceneTree.paused` plus `core.pause()`) of 10 s, with the host in `PROCESS_MODE_ALWAYS`, **THEN** `acc_us` grows by 10,000,000 while paused, and the debt drains after `resume()`.
  - **GIVEN** a 600-tick debt and a fake tick cost of 5 ms, injected through the fake clock rather than by sleeping, **THEN** every frame makes at least one `advance(0, 1)` call, its sim cost is ≤ `sim_slice_budget_us + 5,000` µs, and the debt clears.
- **AC-44 [Logic] (Edge Cases)**: **GIVEN** two core instances from different seeds whose ticks are interleaved, **THEN** each instance's event stream equals that of the same instance run alone. **GIVEN** a core with zero registered handlers, **THEN** 10 ticks run and `tick = 10`.

**Added in third revision (2026-11-16)**
- **AC-45 [Logic] (Edge Cases, R6)**: **GIVEN** `command_queue_max = 100` and a full queue, **WHEN** 2,500 more commands are submitted before one tick, **THEN** all 2,500 return 0, the publisher receives exactly one `commands_dropped` record `(1, 2500, 0, 0, 0)` in that tick, the core is not `Failed`, and `event_soft_cap_count = 0`.
- **AC-46 [Logic] (R6)**: **GIVEN** command A (`seq` 5) queued when a hand-off occurs and applied after the skip, **THEN** `command_log()` in append order reads `handoff`, `skip`, then `(N, 5, A)`, and neither time entry carries a `seq`.
- **AC-47 [Logic] (F2 validator, Edge Cases)**: **GIVEN** `tick_rate = 1`, `M = 5`, `T = 6 s`, and frames of `advance(16,667)`, **WHEN** 600 frames run, **THEN** no hand-off occurs, exactly 10 ticks have run, and `acc_us = 600 × 16,667 − 10 × 1,000,000 = 200`.
- **AC-48 [Logic] (R4)** *(Python)*: **GIVEN** a handler function taking two parameters, **THEN** `register` returns false and the core is `Failed` with code 2.

**Coverage check (lens: qa-lead).** Every rule R1–R17 maps to at least one criterion:

| Rule | Criteria |
|---|---|
| R1 | AC-1, AC-2 |
| R2 | AC-2, AC-13 |
| R3 | AC-3 |
| R4 | AC-4 to AC-7, AC-41, AC-48 |
| R5 | AC-3, AC-8, AC-9, AC-18, AC-23b, AC-31b |
| R6 | AC-10, AC-10b, AC-11, AC-29b, AC-37, AC-40, AC-45, AC-46 |
| R7 | AC-14, AC-20c, AC-43 |
| R8 | AC-15, AC-15b, AC-16, AC-16b, AC-17, AC-17b, AC-31, AC-37, AC-38, AC-39, AC-47 |
| R9 | AC-20 to AC-20e, AC-43 |
| R10 | AC-21 to AC-23b, AC-33 |
| R11 | AC-24, AC-25, AC-32 |
| R12 | AC-27, AC-27b |
| R13 | AC-28, AC-29b |
| R14 | AC-29, AC-29b |
| R15 | AC-18, AC-36 |
| R16 | AC-30, AC-37 |
| R17 | AC-34, AC-38, AC-42, AC-43 |
| API surface | AC-25 (state matrix), AC-18 and AC-36 (name lists) |

Every formula F1–F6 maps to one:
- F1: AC-1, AC-1b.
- F2: AC-15 to AC-17c, AC-20a, AC-20d, AC-39, AC-47.
- F3: AC-18.
- F4: AC-19.
- F5: AC-4, AC-7.
- F6: AC-34 only, a device run (PENDING: engine).

Boundaries covered:
- `tick_rate` 1, 20, 0 and 25.
- `M = 1` and `max_ticks` 0 and 1.
- `acc' = T_us` and `T_us + 1`.
- The `acc_us` range guard at exactly 2^62 and one above.
- `elapsed_us` 0, negative, 2^62 and 2^62 + 1.
- The event soft warning at 1,000 and 1,001, and the cap at 2,000 and 2,001.
- The `T` floor at `tick_rate = 1` (5 s rejected, 6 s accepted).
- `world_seed` 2^63 − 1 accepted and 2^63 refused.
- Not yet probed: `M = 20` beyond AC-30, and `T` at 600 s.

Gaps:
- AC-7's cross-implementation digest, AC-23, AC-34, AC-41 and AC-43 wait for the engine or a device.
- The other `[PENDING]` ACs wait for their owning systems.
- Timer re-anchoring across a skip, resolver tolerance and crash-recovery policy are tested in Offline progress (31) and Local save (6), not here.

## Open Questions

- **OQ-1 — Offline progress hand-off.** This GDD fixes the core's side of the contract: a whole-tick `gap_us` with a logged `handoff`, then `skip_ticks(k, resolver_version)` with a logged `skip`, and no timeout. Offline progress (31) must specify its side:
  - It re-anchors every due tick the gap crosses before the skip (R5), and decides what backlog a long gap owes (24 Golden Bosses for 24 h, or `golden_boss_backlog_max` = 3).
  - Its resolver is deterministic for a given `(state, gap_us)` and carries a `resolver_version` bumped on any behaviour change, because Leaderboards replays it (AC-37).
  - It resolves well within `T`, or the guild advances only through resolved gaps (Edge Cases).
  - It states a tolerance between its results and exact ticks at the `T` boundary, so a player cannot farm the threshold by backgrounding for just over `T`.
  - It may need more from the core, for example a dry-run query for the next timed event, or a "while you were away" summary event entering the P6 stream. Owner: Offline progress (31).
- **OQ-2 — Local save owns recovery.** R10 accepts that a failed tick is not rolled back and exposes the `Failed` record (`fail_code`, `fail_owner_id`, `failed_at_tick`) and `state_trusted`. Local save (6) owns everything else:
  - the autosave cadence, which bounds lost orders (about 60 s is proposed);
  - the number of save generations;
  - a pre-save invariant check that catches silent GDScript corruption (R10);
  - any host error-logger hook;
  - any crash marker, and whether a reload avoids `failed_at_tick`, for example by asking the core for a forced hand-off primitive;
  - the fatal screen's recovery options, including any read-only view.

  If Save needs a core primitive, R10 changes. Owner: Local save (6).
- **OQ-3 — Event buffer ownership.** The core owns the per-tick buffer and the Event bus (42) delivers it in P6. If the bus needs to own the buffer, R5, R10 and AC-33 move. P6 should deliver one batched, packed buffer per tick, not one signal per event. Owner: Event bus (42). **Resolved 2026-11-16 by the Event bus GDD:** the core owns the buffer and its caps, and the bus delivers one batch per tick in a single P6 handler. Events are five integers (R5 above). The bus still wants the core to record which handler emitted each event, so a bad record can be attributed (Event bus OQ-1, the only part left open).
- **OQ-4 — Config keys and validator rules.** `config.csv` needs `live_catchup_max_ticks`, `offline_threshold_s`, `command_queue_max`, `command_drain_max` and `event_buffer_hard_cap`. The validator needs:
  - `tick_rate` a divisor of 1,000,000 and within 1–20;
  - `M` within 1–20;
  - `offline_threshold_s` a whole number within 1–600 (default 60) with `T_us ≥ (M + 1) × tick_us`;
  - `command_queue_max` within 100–10,000;
  - `command_drain_max` within 10–1,000 and ≤ `command_queue_max` (default 25);
  - `event_buffer_hard_cap` within 500–10,000 (default 2,000).

  None exists. Owner: Data layer (3).
- **OQ-5 — Handler `order` allocation.** Orders are allocated in steps of 100 in each owner's GDD. Nothing yet stops two GDDs picking the same value except a boot error late in implementation. Consider a single allocation table (in this GDD or the control manifest) once the first three feature GDDs register. Owner: this GDD, after Member model and Combat.
- **OQ-6 — Tick cost on a phone.** `M = 5` and `T = 60 s` are reasoned, provisional defaults. `T = 60 s` holds with `B = 10 s` only if the p95 tick cost is at most about 6.9 ms (F6). The P1 spike (GDD §12.1) runs AC-34, names the min-spec device and the max-roster fixture, and sets `offline_threshold_s ≤ T_max`. It also sets `event_buffer_hard_cap` to about 10–20× the measured events-per-tick peak, re-checks `command_drain_max` against measured per-command cost, and replaces F6's provisional per-phase shares. If `T_max` < 30 s, the creative-director decides the Player Fantasy trade-off. Feature GDDs must also state their per-tick `derive` count, because a fresh generator per member per tick may alone exceed the budget.
- **OQ-7 — Who calls `pause()`.** No system yet requests a pause (an in-app menu, a modal ad, a settings screen). Since the third revision a pause only defers ticks, so its value is smaller. If no system needs it, `Paused` can be dropped. Owner: Guild screens (39) and Settings (45).
- **OQ-8 — Threading.** R15 assumes the host and the core share one thread. If the core runs on a worker thread for performance, snapshot and event hand-off need a thread contract. Out of scope for MVP; revisit if OQ-6 shows ticks above budget.
- **OQ-9 — Failure message class.** R10 says the fatal screen shares the Data layer's message class. Wording and where the screen lives belong to Guild screens (39) and Localization (4).
- **OQ-10 — Command log and history size.** The command log grows with every command, `handoff` and `skip`. The P6 history grows with every tick: at 864,000 ticks a day, even 40 bytes per event is about 35 MB a day, and dictionary events are far more. The earlier "10–20 MB per day" estimate had no stated basis and is withdrawn.
  - Leaderboards (35) owns a checkpoint-and-truncate scheme for the log, with a periodic signed state hash.
  - The Event bus (42) owns a hard memory bound for history, a ring buffer or batched flush, and no synchronous main-thread I/O.
  - Both should add a steady-state memory AC over 8 h of `run_ticks`.
  - Packed integer arrays are preferred over dictionaries for the log, the history and the event buffer.

  Owners: Leaderboards (35), Event bus (42).
- **OQ-11 — Pause, then quit.** Resolved in the third revision: paused time is owed (R9), so a pause followed by quitting is ordinary offline time, measured from `last_saved_utc`. There is nothing to exploit, because the pause never stopped world time.
- **OQ-12 — Monotonic clock across suspend.** Specialists believe `Time.get_ticks_usec()` does not count device sleep on Android or iOS. This is unverified. R7 is written to hold either way. The P1 spike should confirm it on a device and name the host notifications in the ADR (`NOTIFICATION_APPLICATION_PAUSED`/`RESUMED` on mobile; focus-loss behaviour on desktop). Owner: this GDD, P1 spike.
- **OQ-13 — 63-bit `world_seed`.** R13 fixes `world_seed` to `0 … 2^63 − 1`. The RNG GDD (R2, the `RngFactory` API row and the variable table) still says unsigned 64-bit and must be revised so that `new_world_seed` clears the top bit. Its golden vectors must use seeds below 2^63. `event_seed` and draw outputs inside the RNG are unaffected. Owner: Deterministic RNG (2).
- **OQ-14 — Unverified Godot 4.7 APIs.** R4, R5, R7 and R10 rely on APIs that need checking against the 4.7 class reference or a spike:
  - `Callable.is_standard()`, `is_custom()` and `get_argument_count()`;
  - a suspended coroutine returning a non-null `GDScriptFunctionState`;
  - `OS.add_logger` and `Logger._log_error`;
  - `String.to_int` overflow behaviour;
  - `NOTIFICATION_APPLICATION_PAUSED` versus focus semantics on Android.

  The ADR records the verified forms. Floats in handler state are an owner concern, but note that `round()` differs from Python and that transcendentals depend on the platform. Owner: this GDD's ADR.
