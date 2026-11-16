# Event Bus and History Log

> **Status**: In Review (revised 2026-11-16 after /design-review NEEDS REVISION; re-review pending)
> **Author**: user + Claude
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet)

## Summary

The Event bus and history log delivers each tick's events from the Sim core's last phase to every subscriber in one deterministic batch, and records the story-worthy ones in a bounded two-tier history. Players never see it. They see a world that reacts in the right order, exactly once, and a Chronicle that still remembers a member's first milestones months later. It exists so quests, analytics, the AI text layer, the world view and audio depend on one stream and not on every feature system.

> **Quick reference** — Layer: `Core` · Priority: `MVP` · Key deps: `Sim core and tick loop, Data layer and content pipeline`

## Overview

The Event bus and history log is how the guild's simulation tells everyone else what just happened. Once per tick, in the last phase (P6) of the Sim core's loop, it takes the events the feature systems emitted that tick, in emission order, and delivers them to every subscriber: the world view and audio that show them, and quests, analytics, the AI text layer and the member state machine that react to them. In the same pass it records the events worth remembering into a bounded history log, the guild's chronicle. Subscribers depend on this one stream, not on the five or more feature systems that produce events, and producers never know who is listening.

The bus carries events one way: it reads state nowhere, writes none, and cannot call back into a feature. The history log is its only memory. It is what the Jianghu Chronicle (`bld_chronicle`) retells as prose and what the AI text layer reads for context. It has a hard memory bound, because a guild that runs for months must not grow without limit (Sim core OQ-10). The bus does no scoring, no narration and no text: it keeps structured records, and display strings stay in `i18n/` (GDD §3.3).

**Player impact.** Players never see the bus. They see what it makes possible: a feed of "what just happened" in the guild, a Chronicle that remembers a member's rise and a boss kill after the app has been closed, and quests and achievements that fire the moment the thing they track occurs. If the bus dropped, reordered or double-delivered an event, the player would see a quest that never completes, an achievement that triggers twice, or a Chronicle that disagrees with what they watched.

**What the system does not own.** The per-tick event buffer, its soft and hard caps, and the discard-on-failed-tick rule belong to the Sim core (R2, R10). The event types and their payloads belong to the systems that emit them. The command log belongs to Leaderboards (35). Narrating history as prose belongs to the Chronicle UI and the AI text layer (36).

## Player Fantasy

**Indirect.** The player never touches the bus. They feel three things it makes possible.

**The guild has a past.** After eight hours away, the player opens the Chronicle and reads who rose, who left and which Golden Boss fell. It agrees with the roster in front of them. The guild did not pause while they were gone, and it remembers what happened. The memory works with no LLM installed, because the plain template sentences (GDD §9.2) come from the same log.

**The world answers right now.** On the map, a drop, a level-up and a quest tick land in the same beat, in the order they happened, each exactly once. During catch-up the world stays quiet instead of flooding the screen.

**The story is mine.** The member the player recruited on day one reaches a milestone, and the Chronicle names them. It names the same person after a rename or a language switch, because the log records who they are, not what they were called that day. This holds after they leave the guild only because Member model keeps a name record for every member ID ever issued (Dependencies, OQ-4).

*No game pillars exist, so no pillar is quoted. These three are anchored to GDD §3.4 step 6, §9.2 (Giang Hồ Ký) and the infinite-play and offline-progress rows. CD-GDD-ALIGN remains NOT ASSESSED.*

## Detailed Design

### Core Rules

**R1: One bus, one P6 publisher.** The bus registers a single P6 handler as `owner_id = "event_bus"` at `order = 100`. It is the only handler that reads `ctx.events()`. Other P6 handlers may emit events, and those go to the next tick (Sim core Edge Cases). The bus holds no game state and calls no feature. Its only memory is the history log (R7).

**R2: Records are integers only.**
- An emitted event is five integers: `type_id, a, b, c, d`. The core's buffer stores them with stride 5.
- A history record has stride 6: `tick, type_id, a, b, c, d`. The bus stamps `tick` itself.
- `tick` is the tick whose P6 delivers the event. An event emitted in P6 of tick N − 1 carries N.
- Fields hold stable IDs and quantities, never display strings. A rename or a language switch cannot change history.
- Unused payload slots are 0.

**R3: Event types are registered at boot.** `register_type(type_id, owner_id, name, field_count, logged, milestone, subject_slot, ring_per_day)`:
- `type_id` is 1 – 65,535 and unique.
- IDs 1 – 99 are reserved for the core (`commands_dropped` = 1); an owner other than `sim_core` registering one is a boot error. Other owners get blocks of 100 within 100 – 65,499, allocated in their own GDDs and recorded in the registry so two GDDs cannot claim one block. IDs 65,500 – 65,535 are unallocated.
- `owner_id` and `name` are each 1 – 48 characters of `[a-z0-9_]` (so one byte per character, which F2's `u8` length prefix relies on).
- `field_count` is 0 – 4.
- `milestone` implies `logged`.
- `subject_slot` is 0 (no subject) or 1 – 4, and at most `field_count`. It names which payload slot holds the member ID that the milestone belongs to.
- `ring_per_day` is the type's declared **peak** number of ring records per 86,400 game seconds at the max-roster fixture, a whole number ≥ 0. It must be 0 unless the type is `logged` and not `milestone`. It is the emitter GDD's stated rate (F1 emission-budget rule), and `seal()` checks the sum (F4).
- **Type IDs are permanent.** A retired ID is never reused, and a type whose payload meaning changes gets a new ID. Otherwise old history records silently change meaning.
- Registration is open only while the bus is `Registering` (R10). A duplicate `type_id`, an out-of-range value, a malformed `owner_id` or `name`, a `subject_slot` above `field_count`, a `milestone` flag without `logged` or a nonzero `ring_per_day` on a type that never reaches the ring is a boot error naming the owner. `register_type` records the call; every check runs at `seal()`.

**R3a: Emitter rules the bus cannot check.** Each emitting GDD must follow these, and its own ACs test them:
- **Roster-changing events are milestones.** A type that records a member joining, leaving, being promoted or demoted, or being renamed must be `milestone = true`, so the Chronicle never contradicts the roster because a ring record was evicted.
- **Milestone subjects are guild members.** `subject_slot` names a member of the player's guild, or 0 for a guild-wide milestone. Events about NPCs, free agents and applicants are ring events (or carry subject 0). This keeps the number of milestone subjects within F5's planning bound.

**R4: Subscribers are registered at boot.** `subscribe(owner_id, order, type_ids, handler)`:
- Handlers run in ascending `order`. Two with the same `order` is a boot error that names both owners. Orders are allocated in steps of 100 by the subscriber's GDD.
- At most 16 subscribers (`max_event_subscribers`). A 17th is a boot error at `seal()`. The cap bounds F1's `S × c_call` term.
- `type_ids` is a non-empty list of registered types, or `ALL`. An empty list, or a type that is not registered at `seal()`, is a boot error, so a typo fails at boot and not silently.
- `handler(batch, ctx)` takes exactly two arguments and returns nothing, under the same Callable rules as Sim core R4. The accepted form is an unbound method Callable on a live object whose `get_argument_count()` is 2. A bound Callable, a lambda, or a method with a third, defaulted parameter is a boot error (the default counts toward arity). `ctx` is the tick context passed to the bus's own P6 handler. A subscriber calls `ctx.emit`, `ctx.submit` and `ctx.fail` through it.
- **Lifetime.** A Callable does not keep its object alive. The bus therefore holds a strong reference to each handler's object for the life of the bus. `seal()` checks `is_valid()` on every handler. P6 checks it again before each call, and an invalid handler fails the tick with `ctx.fail(42003, msg)` naming the subscriber's `owner_id`.

**R5: Delivery, one batch per tick.** In P6, in this order:
0. If the buffer is empty, return. No allocation, no calls, no commit.
1. Validate the buffer (R9). If invalid, fail.
2. Stamp each event with `tick` (R2) into the bus's own working array.
3. For each subscriber in ascending `order`, build its batch: the stamped records whose type it listed, in emission order. If the batch is non-empty, call `handler(batch, ctx)` once. A subscriber with an empty batch is not called. After every call, check `ctx.failed`, and stop at once if it is set. GDScript has no exceptions, so this check is the only way a later subscriber is not called.
4. If every subscriber returned and the core is not failed, commit the stamped records to history (R7) from the working array.

**Each batch is a fresh array.** Godot 4 passes packed arrays by reference, so the bus builds every subscriber's batch as a new `PackedInt64Array` and never hands out the working array, a ring array or another subscriber's batch. A subscriber that writes to its batch changes only that array. Delivery is deterministic: the order is fixed by `order` and the batch by emission order.

**R6: Subscriber contract.** A subscriber runs to completion and returns nothing.
- It may update **its own** system's state, `emit` (the event lands in the next tick), `submit` (applies next tick) and `ctx.fail`, all through the `ctx` argument. A failure from a subscriber is reported with `fail_owner_id = "event_bus"`, and its message names the subscriber's `owner_id`.
- It must not read or write another system's state, and it must not do work whose cost scales beyond reading its batch. Heavy work is queued and done in the subscriber's own handler in P2–P5 of a later tick.
- It may query history (R8). Queries exclude the batch being delivered, since that batch is not yet committed.

**R7: History is two tiers, both bounded.**
- **Recent ring.** Records of types with `logged = true` and `milestone = false`. It holds at most `history_ring_cap` records and evicts the oldest first. It is a preallocated `PackedInt64Array` of `history_ring_cap × 6` ints with a head index and a count: an append overwrites the slot at the head, so the ring never resizes or erases.
- **Milestone tier.** Records of types with `milestone = true`. They are never in the ring. Each has a subject: the member ID in `subject_slot`, or 0 for a guild-wide milestone (R3a).
  - Subject limit: `milestone_cap_per_subject` for a member, `milestone_cap_guildwide` for subject 0.
  - Global limit: `milestone_cap_total`, which counts subject 0's records too.
  - **Protection.** A subject's oldest `milestone_keep_first` retained records are protected. Subject 0 is protected the same way.
  - **Eviction order.** Records are committed one at a time, in emission order. After each append the bus evicts: (1) if the record's subject is over its subject limit, that subject's oldest unprotected record; then (2) while the tier is over `milestone_cap_total`, the oldest unprotected record of the tier; and (3) only if step 2 finds no unprotected record, the oldest record of the tier. Step 1 always finds an unprotected record, because `milestone_keep_first` is below every subject limit. Step 3 is reachable only beyond F5's planning bound, and it is the documented loss: the oldest subjects' protected records go first.
  - **Structure.** The tier is an append-only slot array in commit order, with tombstones for evicted slots and a per-subject index of live slots (at most the subject limit). A commit costs O(subject limit) plus the slots skipped by step 2's scan. The array is compacted when tombstones exceed half its length (amortised O(1) per record).
- Both tiers are in tick order (the ring by construction, the tier because it is append-only). Events not flagged `logged` are delivered and never stored.

**R8: Queries.** All return new arrays (never a live tier array) and are allowed whenever the core is not `Failed`. While it is `Failed`, each returns an empty result and logs an error, because the in-memory history is untrusted (Sim core R10).
- `read_history(from_tick, to_tick, max_records = 2000) → PackedInt64Array` (stride 6): the merge of both tiers in tick order, at most `max_records` records, the oldest first. Both ends are inclusive. The range start is found by binary search in each tier. A page never splits a tick: it stops before the first tick that would take it past `max_records`, unless that tick is the first in the page, which is then returned whole. A caller pages by calling again from the last returned tick + 1. Records with the same tick come milestone tier first, then ring, each in append order, because the original interleaving across tiers is not stored. The Chronicle must not infer cause and effect from order within one tick. `from_tick > to_tick`, or no records in range, returns an empty array.
- `milestones_for(subject_id) → PackedInt64Array` (stride 6), in tick order. It carries no gap marker: a consumer cannot tell whether middle records were evicted.
- `size()` returns `{ring, milestones}`.

**R9: Validation.** Before delivery the bus checks every buffered record. A failure calls `ctx.fail(42001, msg)`, and the core fails per Sim core R10. A record is invalid if:
- its `type_id` is not registered;
- an unused payload slot is nonzero;
- its `subject_slot` value is negative;
- the buffer length is not a multiple of 5.

The message names the buffer index, `type_id` and registered `owner_id` (if any). For a length that is not a multiple of 5 it names the length instead, since no record can be indexed. Attribution to the emitter is not possible, because the core does not record it (OQ-1).

**R10: Boot sequence.** The host calls `bus.seal()` before `core.seal()`. `seal()` validates R3, R4 and the ring budget (F4), freezes both tables, computes `type_table_hash` (F2) and moves the bus from `Registering` to `Sealed`. If the P6 handler runs before `seal()`, it calls `ctx.fail(42002, "bus not sealed")`.

**R11: Persistence.** The bus does no I/O.
- **Snapshot.** `snapshot_history()` is allowed between ticks while the bus is `Sealed`, no hand-off is pending and the core is not `Failed`. Otherwise it returns an error and no snapshot. A snapshot holds two compacted `PackedInt64Array`s and `type_table_hash`. The ring array holds stride-6 records, oldest first. The milestone array holds stride-7 entries in commit order: the record plus its subject, so a record whose type is later retired keeps its subject. It holds no Dictionary: the per-subject index is rebuilt from the records on restore. Local save owns the encoding and must keep every int64 exact, as it does for the core (Sim core R14, AC-29b: decimal strings in JSON, never JSON numbers).
- **Restore.** `restore_history(snapshot, core_tick) → {ok, error, trimmed_count, unknown_type_count, hash_mismatch}` is allowed once, after `bus.seal()` while the core is `Booting`. `core_tick` is the core's restored `tick`, the next tick it will run. A call at any other time, or a second call, is refused (`ok = false`) with no change.
- **Checks.** A snapshot is refused with no change if: its stride is wrong; its ticks are not non-decreasing within each tier (equal ticks are allowed); or its last record's tick is ≥ `core_tick`, which means the history and the core snapshot come from different save generations. An empty snapshot is always accepted.
- **Trimming.** If the snapshot holds more records than the current caps, the bus replays the records in order through R7's eviction rules, so protection survives a tightened cap. It reports the number dropped in `trimmed_count`. Tightening a cap in a patch therefore never rejects an old save.
- **Retired types.** Records with a `type_id` that is no longer registered are kept in their tier and counted in `unknown_type_count`, so a content patch cannot erase history.
- **Hash.** A mismatched `type_table_hash` sets `hash_mismatch = true` and is not fatal. Local save decides whether to warn.

**R12: Catch-up and hand-off.** The bus behaves identically during catch-up (it delivers and logs). Suppressing animation and sound while `catching_up` is the presentation's job (Sim core R15). A hand-off gap produces no per-tick events, so history ticks are not contiguous across a gap. That is valid, and no query or restore check assumes contiguity. Offline progress (31) must emit its summary as ordinary events from a handler in the first tick after the skip, so the Chronicle has a record of each absence (OQ-2).

### States and Transitions

| State | Meaning | Accepts `register_type` / `subscribe`? | Delivers in P6? |
|---|---|---|---|
| `Registering` | Boot; tables open | Yes | No (the handler fails with 42002) |
| `Sealed` | Tables frozen, hash computed | No (error return, no change) | Yes |
| `Disposed` | Host called `dispose()` | No | No |

| From | To | Trigger |
|---|---|---|
| `Registering` | `Sealed` | `seal()` with R3/R4 valid |
| `Registering` | `Registering` | `seal()` with a boot error: stays, error names the owner |
| `Sealed` | `Disposed` | `dispose()` |
| `Registering` | `Disposed` | `dispose()` |

There is no `Failed` state. A bus-detected fault fails the core (Sim core R10), and the bus is discarded with it. After a core failure the in-memory history is untrusted, like all state (Sim core R10): queries return empty (R8) and `snapshot_history()` is refused (R11), so a failed run's history is never saved.

**Fail codes.** 42001 invalid buffer (R9); 42002 bus not sealed (R10); 42003 a subscriber's handler object was freed (R4).

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Sim core (1) | both | The per-tick buffer via `ctx.events()` | The P6 handler; the `ctx.fail` codes 42001–42003 | Core owns the buffer and caps; bus owns delivery and log |
| Feature systems (8–30, 41) | feature → bus | Events via `ctx.emit` (R2); `register_type` at boot | Nothing directly | Each feature owns its type block |
| Subscribers (25, 36, 37, 41, 44) | bus → subscriber | `subscribe` at boot | Per-subscriber batches (R5); history queries (R8) | Subscriber owns its handler and order |
| Realtime world view (38), Audio (40) | bus → view | None | The full tick batch through the Sim core facade (R15) | World view / Audio |
| Local save (6) | both | `restore_history` | `snapshot_history()` | Save owns format and cadence; bus owns what is in the snapshot |
| Offline progress (31) | feature → bus | Summary events after a skip (R12) | None | Offline owns the summary schema |
| Jianghu Chronicle UI / AI text (36) | bus → reader | None | `read_history`, `milestones_for` | Chronicle owns narration |
| Dev tooling (43) | bus → tools | None | `type_table_hash` (F2) | Dev tooling |
| Localization (4) | none | None | None. Records carry IDs, never text | Localization |

**Provisional assumptions about the Sim core (conflicts to resolve, not silently assumed):**
1. The Sim core GDD now states these (revised 2026-11-16): `ctx.emit` takes five integers `(type_id, a, b, c, d)`, the core buffer has stride 5, and `commands_dropped` is type 1 with `a = count`.
2. (closed by 1.)
3. The core does not record which handler emitted an event, so R9 cannot attribute a bad record to its emitter.

## Formulas

### F1 — `c_p6` and `E_budget` (P6 cost)

The P6 cost formula is defined as:

`c_p6 = c_empty` when `E = 0`, else `c_p6 = c_fixed + E × (c_rec + k̄ × c_route + ℓ̄ × c_commit) + n_called × c_call`

`E_budget = max( 0, floor( (p6_share × sim_slice_budget_us − c_fixed − S × c_call) / (c_rec + k̄ × c_route + ℓ̄ × c_commit) ) )`

`E_floor = Σ over emitting GDDs of their stated typical events per tick` (the emission-budget rule below)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| E | int | 0 – `event_buffer_hard_cap` (2,000) | calculated | Events in this tick's buffer |
| S | int | 0 – 16 | constant | Registered subscribers (validator limit, so the `S × c_call` term is bounded) |
| n_called | int | 0 – S | calculated | Subscribers with a non-empty batch this tick |
| k̄ | float | 0 – S | calculated | Mean number of subscribers listing an event's type (found through a type → subscribers index built at `seal()`, not by scanning all S per event) |
| ℓ̄ | float | 0 – 1 | calculated | Fraction of the tick's events whose type is `logged` |
| c_empty | µs | > 0 | measured (P1 spike) | Cost of the empty-buffer early-out: one length check, no allocation |
| c_fixed | µs | > 0 | measured (P1 spike) | Per-tick cost with events present: setup and building the S batch arrays |
| c_rec | µs | > 0 | measured (P1 spike) | Per record: validate (R9) and stamp (R2) |
| c_route | µs | > 0 | measured (P1 spike) | Per record per interested subscriber: append 6 ints to its batch |
| c_commit | µs | > 0 | measured (P1 spike) | Per logged record: ring write or milestone insert, including any eviction |
| c_call | µs | > 0 | measured (P1 spike) | Per subscriber call, excluding what the subscriber does inside |
| p6_share | float | 0.10 (provisional) | constant | Sim core F6's provisional P6 share of one tick |
| sim_slice_budget_us | int | 8,333 at 60 fps; 16,667 at 30 fps | constant | Sim core R17 and F6, used unchanged |

**What the budget is a share of.** Sim core F6 bounds one tick: a device is min-spec only if its p99 `c_tick` ≤ `sim_slice_budget_us`, because time-slicing runs one tick per call and a frame's sim cost is at most the slice plus one tick (Sim core R17). `p6_share × sim_slice_budget_us` (833 µs at 60 fps) is P6's provisional share of that **single-tick** bound, not of a 100 ms tick period. The sum-of-phases gate is the core's (Sim core AC-34: p99 `c_tick` ≤ the slice). During catch-up, ticks run back to back inside each slice, so P6's **mean** cost also lowers the drain rate `r_net` (Sim core F6), and the spike reports both.

**Output Range.** `c_p6` should stay ≤ `p6_share × sim_slice_budget_us` (833 µs at 60 fps). `E_budget` is the sustained events per tick that fits, and it is never negative. A result of 0 means the fixed costs alone exceed P6's share, and the spike fails. A tick above `E_budget` is slow, not wrong: it costs a stutter and nothing else. Only the core's `event_buffer_hard_cap` fails a run. **The spike passes only if the measured `E_budget` ≥ `E_floor`.** The floor is set before measuring, from the emitter GDDs, so the gate is not derived from the run it judges.

**Boundaries.**
- **E = 0:** costs `c_empty` only. The empty early-out is a rule, not an optimisation (R5 step 1 does nothing for an empty buffer).
- **E = 2,000 (the hard cap):** costs about `2,000 × (per-record cost)`, which is many times the P6 share (see the example).
- **S = 0:** `k̄ = 0` and nothing is routed. The bus still validates and commits.
- **Denominator ≤ 0:** cannot happen while every `c_*` is positive.
- **Numerator ≤ 0:** for example S = 16, `c_call` = 50 and `c_fixed` = 100 give 833 − 100 − 800 < 0. The `max(0, …)` clamp gives 0, a spike failure.
- **Worst case, not typical.** `E_budget` charges `S × c_call` (every subscriber called), while `c_p6` charges `n_called × c_call`. The budget is deliberately conservative.
- **`c_commit` is not constant.** It includes R7's eviction scan, so the spike measures it with a full ring and a full milestone tier, not an empty log.
- The subscriber's own work inside its call is not in `c_call`. It belongs to the subscriber's GDD (R6).

**Emission budget rule.** Every GDD that emits events states, per event type, its typical and peak events per tick at the max-roster fixture and its `logged` rate. It must coalesce high-volume things (per-hit damage, per-item drops) into at most one summary event per tick per source. The sum of typical rates is `E_floor`, and it must stay at or under the measured `E_budget`. The P1 spike measures the `c_*` constants at p99, replaces the illustrative numbers below, and sets `E_budget`. Until three emitter GDDs exist, `E_floor` is provisionally 50 events per tick. That is a placeholder at about a quarter of the illustrative `E_budget`, chosen so 4× headroom is required. The first three emitter GDDs replace it (OQ-3). The engine reference does not cover GDScript loop cost (NOT SOURCEABLE), so no `c_*` value in this GDD is a fact.

**Example (ILLUSTRATIVE unit costs, not measured):** `c_fixed = 20 µs`, `c_rec = 1.5`, `k̄ = 2`, `c_route = 1.0`, `ℓ̄ = 0.3`, `c_commit = 1.5`, `S = 6`, `c_call = 5`. Per-record cost = 1.5 + 2.0 + 0.45 = **3.95 µs**. `E_budget = max(0, floor((833 − 20 − 30) / 3.95)) = 198`. A tick at the soft cap (1,000) would cost about 3.95 ms, roughly 47% of the single-tick bound. A tick at the hard cap (2,000) would cost about 7.9 ms, about 95% of it: the whole sim slice for that frame.

### F2 — `type_table_hash`

The type_table_hash formula is defined as:

`type_table_hash = SHA-256( concat over types sorted by type_id of [ u16_be(type_id) ‖ u8(field_count) ‖ u8(flags) ‖ u8(subject_slot) ‖ u8(len(owner_id)) ‖ utf8(owner_id) ‖ u8(len(name)) ‖ utf8(name) ] )`, hex-encoded lowercase, with `flags = logged + 2 × milestone`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| type_id | int | 1 – 65,535 | calculated | The registered ID (R3) |
| field_count | int | 0 – 4 | calculated | Payload slots in use |
| flags | int | 0 – 3 | calculated | Bit 0 `logged`, bit 1 `milestone` (`milestone` implies bit 0 set, so 2 is invalid) |
| subject_slot | int | 0 – 4 | calculated | Which payload slot holds the member ID |
| owner_id | string | 1 – 48 chars, `[a-z0-9_]` (checked at `seal()`, R3) | calculated | The registering system's stable ID (same format as the Data layer) |
| name | string | 1 – 48 chars, `[a-z0-9_]` | calculated | The type's stable name |
| type_table_hash | string | 64 hex chars | calculated | Identifies the exact event vocabulary |

**Output Range:** 64 lowercase hex characters. `u16_be` is packed by hand in GDScript, as for Sim core F5, and CI cross-checks the digest against Python `hashlib`. With zero types the input is empty and the hash is the SHA-256 of the empty string. That is valid, and `seal()` still succeeds (a bus with no types delivers nothing).
**Not covered.** The hash covers types only, not subscriber orders or handlers. A changed subscriber order is caught by the parity harness through different outputs, not by this hash.
**Implementation.** Use `HashingContext` with `HASH_SHA256`, then `hex_encode()`. With zero types, skip `update()` (an empty `update` may error) and call `finish()` directly.
**Example:** one type `(type_id 1, owner "sim_core", name "commands_dropped", field_count 1, flags 0, subject_slot 0)` frames as the 31 bytes `00010100000873696d5f636f726510636f6d6d616e64735f64726f70706564`. Their SHA-256 is `77e1e65233cb5cf05b48e87bf58eca6d74e056d465589dde2612ed7641c8b25a` (computed with Python `hashlib`, 2026-11-16). That is the known-answer value AC-21 commits.

### F3 — `history_bytes_max`

The history memory bound is defined as:

`history_bytes_max = 48 × (history_ring_cap + milestone_cap_total) + 16 × milestone_cap_total`

`transient_bytes_max = 48 × event_buffer_hard_cap × (1 + S)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| 48 | bytes | constant | constant | 6 ints × 8 bytes per history record |
| 16 | bytes | constant | constant | Per-subject index cost per retained milestone (one int64 slot reference plus amortised key). A planning estimate: a GDScript Dictionary entry costs more, and the spike measures it (OQ-9) |
| history_ring_cap | int | 100 – 100,000 | data file | Recent-ring capacity (default 10,000) |
| milestone_cap_total | int | 100 – 50,000 | data file | Milestone-tier capacity (default 4,000) |
| event_buffer_hard_cap | int | 500 – 10,000 | data file | Sim core's knob |
| S | int | 0 – 16 | constant | Subscribers |

**Output Range:**
- Defaults give `48 × 14,000 + 16 × 4,000 = 736,000` bytes, about 719 KiB.
- `snapshot_history()` copies both tiers, so peak at a save is about twice that (about 1.4 MiB), plus whatever transient copy Local save's encoder makes (Local save owns that figure).
- The transient per-tick copies are at most `48 × 2,000 × (1 + 6) = 672,000` bytes at the cap and S = 6, freed after P6. At S = 16 it is 1,632,000 B. At the hard-cap knob's maximum (10,000) and S = 16 it is 8,160,000 B, larger than the history itself. The core's own buffer (40 B per event) is extra.
- At the minima (100 and 100) the log is `48 × 200 + 16 × 100 = 11,200` bytes.
- At the maxima (100,000 and 50,000) the log is `48 × 150,000 + 16 × 50,000 = 8,000,000` bytes (8.0 MB, 7.63 MiB), and the validator rejects larger.
- It does not grow with play time. The 8-hour memory AC checks that.

**Example:** at 10,000 / 4,000 the log holds 14,000 records, 672,000 bytes, plus 64,000 for the per-subject index.

### F4 — `ring_span_s` and `r_logged_max`

The ring-span formula is defined as:

`ring_span_s = history_ring_cap / r_logged`  and  `r_logged_max = history_ring_cap / away_span_target_s`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| history_ring_cap | int | 100 – 100,000 | data file | As F3 |
| r_logged | float | ≥ 0 | calculated | Guild-wide logged non-milestone records per game-time second, summed over all owners |
| away_span_target_s | int | 86,400 | constant | How far back the recent ring should reach (default 86,400, 24 h) |
| ring_span_s | float | seconds | calculated | How far back the ring reaches at that rate |
| r_logged_max | float | > 0 | calculated | The sustained logged rate the target allows |

**Output Range:** `r_logged_max` runs from 100 / 86,400 = 0.00116 to 100,000 / 86,400 = 1.157 records per second over the knob's range. At the defaults it is `10,000 / 86,400 = 0.116` records per second, one per 8.6 s (one per 86 ticks at 10 Hz). If `r_logged = 0`, the ring never fills and `ring_span_s` is infinite (the formula is not evaluated). If it is 1 per second, the span is 10,000 s, about 2.8 h. The Chronicle can then not show a full 8-hour absence from the ring. That is why the rule below is checked at boot. Roster changes are milestones (R3a), so the roster agrees with the Chronicle even when the ring is short.
**Rule, checked at `seal()`:** `Σ ring_per_day over all types ≤ history_ring_cap × 86,400 / away_span_target_s` (10,000 at the defaults, the integer form of `r_logged ≤ r_logged_max`). If the sum is above it, `seal()` fails with a boot error that lists each type's `ring_per_day`. A single repeated action therefore cannot flush the ring unless its owner declared that rate and the sum still fits. A type that emits above its declared rate is an emitter bug, caught by its GDD's emission-rate AC, not by the bus. Offline summaries count as ring records, one per absence, not one per skipped tick. The split between owners is an open question (OQ-3).
**Example:** 12 members each with 1 logged event per 5 minutes gives `r_logged = 0.04`, and `ring_span_s = 250,000 s ≈ 2.9 days`.

### F5 — `milestone_protection_fits`

The milestone-tier fit check is defined as:

`protected_total = Σ over subjects s of min(count_s, milestone_keep_first)`  and  `fits = (protected_total ≤ milestone_cap_total)`

**Validator sizing rule (planning bound):** `milestone_cap_total ≥ milestone_keep_first × milestone_subjects_planned + milestone_cap_guildwide`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| count_s | int | 0 – the subject's limit (`milestone_cap_per_subject`, or `milestone_cap_guildwide` for subject 0) | calculated | Retained milestone records of subject s |
| milestone_cap_guildwide | int | 10 – 1,000 | data file | Subject 0's limit (default 200) |
| milestone_subjects_planned | int | 1,000 (provisional) | constant | Planning bound on distinct guild members that ever hold a milestone in one save. Member model (8) confirms it (OQ-4) |
| milestone_keep_first | int | 0 – (min(`milestone_cap_per_subject`, `milestone_cap_guildwide`) − 1) | data file | Oldest retained records per subject that are protected (default 3) |
| milestone_cap_per_subject | int | 2 – 100 | data file | Per-subject limit (default 24) |
| milestone_cap_total | int | 100 – 50,000 | data file | As F3 |

**Output Range:** `fits` is true while `protected_total ≤ milestone_cap_total`. At the defaults the sizing rule gives `3 × 1,000 + 200 = 3,200 ≤ 4,000`, so every member up to the planning bound keeps their first three milestones. Strictly, fit holds up to `(4,000 − 200) / 3 = 1,266` member subjects once subject 0 is full. Beyond that, R7 step 3 evicts the oldest record of the whole tier, so the oldest subjects' protected records go first. That is the documented loss past the planning bound. NPCs and free agents never count, because they are not milestone subjects (R3a). With `milestone_keep_first = 0` nothing is protected and the tier is a plain FIFO within each subject. `milestone_keep_first ≥` either subject limit is invalid, and the validator rejects it, since no record of that subject would ever be evictable.
**Example:** 200 subjects × 3 = 600 ≤ 4,000, so protection holds. 2,000 lifetime member subjects × 3 = 6,000 > 4,000 breaks the planning bound. The validator cannot see lifetime subjects, so the loss happens at run time, oldest first, and Member model's bound (OQ-4) exists to keep it from happening.

**Feedback loops.** None. Eviction only removes records and never emits events, so a full log cannot feed back into the stream.

## Edge Cases

**Boot and registration**
- **If two types share a `type_id`**, or the ID is 0 or above 65,535, or `field_count` > 4, or `subject_slot` > `field_count`, or `milestone` is set without `logged`: boot error naming the owner(s). `seal()` returns an error, the bus stays `Registering`, and nothing is frozen.
- **If a subscriber lists an unregistered type**, an empty list, or two subscribers share an `order`, or there are more than 16 subscribers, or a handler is bound, a lambda, has the wrong arity or is invalid: boot error at `seal()` naming the owner(s) (R4).
- **If a name or `owner_id` is empty, longer than 48 characters, or outside `[a-z0-9_]`**: boot error at `seal()` naming the owner (R3).
- **If the declared `ring_per_day` values sum above the ring budget (F4)**: boot error at `seal()` listing every type's rate, so the owners can rebalance.
- **If a subscriber's handler object is freed after `seal()`**: the next P6 that would call it fails with 42003 naming the subscriber (R4).
- **If `register_type` or `subscribe` is called after `seal()`**: error return and an error log, with no state change. The bus cannot fail the core outside a tick.
- **If `seal()` is called twice**: the second call returns OK and the same hash, with no change.
- **If the core is sealed and ticking before `bus.seal()`**: the first P6 fails the core with 42002. The host owns the order (R10).
- **If there are zero types and zero subscribers**: `seal()` succeeds with the empty-input hash (F2). Every tick takes the empty-buffer path, or discards its events after validation.

**Delivery and failure**
- **If the buffer is empty**: P6 returns after one length check. No stamping, no calls, history unchanged.
- **If a subscriber emits during P6**: the event lands in the next tick's buffer, and no other subscriber sees it this tick, whatever its `order`.
- **If a subscriber calls `ctx.fail`**: later subscribers are not called and history is not committed. Earlier subscribers keep what they saw (the Sim core's accepted prefix).
- **If a subscriber writes to its batch**: only its own copy changes.
- **If a subscriber queries history in P6**: the result excludes the batch being delivered.
- **If an event has an unregistered type, a nonzero unused slot or a negative subject value**: 42001, with the buffer index, `type_id` and registered owner (if any). The emitter cannot be named (OQ-1).
- **If the same type appears twice in a batch**: both records are delivered, in emission order.
- **If an event's type is not `logged` and has no subscriber**: it is validated, stamped and dropped. It costs time (F1) and nothing else.
- **If a tick sits at exactly 2,000 events**: the core passes it and the bus delivers it. Transient memory is F3's `transient_bytes_max`. The cost is above `E_budget` (F1): a stutter, not a failure.

**History log and queries**
- **If the ring is full**: appending evicts the oldest record. Tick order is preserved across the wrap.
- **If one append puts a subject over its limit and the tier over `milestone_cap_total`**: R7 step 1 evicts the subject's oldest unprotected record first. That also brings the tier back to its cap, so step 2 does nothing. One eviction, not two.
- **If the tier is over `milestone_cap_total` and every record is protected** (more subjects than F5's planning bound): R7 step 3 evicts the oldest record of the tier, including a protected one. This is the documented loss.
- **If a milestone's subject value is 0** in a slot that declares a subject: the event is a guild-wide milestone (subject 0), limited by `milestone_cap_guildwide`.
- **If a member leaves the guild**: their milestones stay until evicted. Member IDs are never reused within a save (an assumption on Member model 8, OQ-4).
- **If two milestones for one subject arrive in the same tick**: both are stored, in emission order.
- **If `read_history` is called over the whole span**: it returns at most `max_records` (default 2,000, about 96 KB), and the caller pages. The Chronicle must cache and must not call it every frame (Chronicle UI owner).
- **If `from_tick` > `to_tick`**, or the range holds no records: an empty array, not an error.
- **If any query runs while the core is `Failed`**: an empty result and an error log (R8).

**Persistence, versions and degenerate strategies** (authored 2026-11-16 after design review)
- **If `snapshot_history()` is called inside a handler, while a hand-off is pending, before `seal()` or while the core is `Failed`**: error return, no snapshot (R11). The host retries between ticks.
- **If `restore_history` is called before `bus.seal()`, after the core leaves `Booting`, or a second time**: refused with `ok = false` and no change (R11).
- **If a patch retires a type**: its records are kept and counted in `unknown_type_count` (R11). Its ID is never reused (R3).
- **If a patch renames a type, or changes any F2 field**: `type_table_hash` changes, and restore reports `hash_mismatch = true` without refusing. A change of payload meaning must take a new ID instead (R3).
- **If the core fails**: the in-memory history is untrusted. Queries return empty and no snapshot can be taken, so the last good save's history stands (States).
- **If a player repeats an action that emits a ring event**: the type's emission is bounded by its declared `ring_per_day`, and the sum is checked at `seal()` (F4). An owner whose type can repeat faster must coalesce it (F1 emission-budget rule) or declare the higher rate and fit the budget.
- **If history ticks are non-contiguous after a hand-off**: valid. No query or restore check assumes contiguity (R12).

## Dependencies

### Upstream (this system depends on)

| System (#) | Hard / soft | Interface | What this system takes |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | `ctx.events()` in P6, `ctx.fail`, the buffer and its caps, `sim_slice_budget_us` (F1), `core_tick` for restore (R11) | The per-tick buffer, delivered once per tick in emission order. The Sim core's GDD already lists this system downstream, so the two-way record holds |
| Data layer and content pipeline (3) | Hard | Five `config.csv` keys: `history_ring_cap`, `milestone_cap_total`, `milestone_cap_per_subject`, `milestone_cap_guildwide`, `milestone_keep_first`. The validator enforces the F3–F5 ranges and the F5 sizing rule (see Tuning Knobs) | Read once at `bus.seal()`. None of the five exists yet (OQ-7) |

Deterministic RNG (2) is **not** a dependency: the bus never draws, and its output depends only on the event stream.

### Downstream (systems that depend on this one)

| System (#) | Hard / soft | Interface | What it gets |
|---|---|---|---|
| Feature systems that emit (8–30, 41) | Hard | `register_type` at boot, `ctx.emit` (R2, R3), the emitter rules (R3a), the emission-budget rule (F1) and the ring budget (F4) | A stable vocabulary and a delivery guarantee. Each must state its type block, typical and peak events per tick, each type's `ring_per_day`, and which types are milestones. Each must test its own R3a compliance |
| Member model (8) | Hard | R3a, F5 | Must never reuse a member ID within a save, must keep a name record for every ID ever issued (including departed members) so the Chronicle can name them, and must confirm or replace `milestone_subjects_planned` (OQ-4) |
| Member state machine (41) | Hard | `subscribe` (R4) | Batches in a deterministic order, no direct feature coupling |
| Quests and achievements (25) | Hard | `subscribe` | The stream its triggers watch |
| Analytics (37) | Hard | `subscribe` | The stream, as a pure observer |
| Onboarding and tutorial (44) | Hard | `subscribe` | The stream its steps watch |
| AI text layer (36) | Soft | `read_history`, `milestones_for` (R8) | History as prompt context. Works without an LLM through the template fallback (GDD §9.2) |
| Chronicle screen and `bld_chronicle` (owner not yet assigned, OQ-8) | Hard | `read_history`, `milestones_for` | The records it narrates. It owns paging and caching (Edge Cases) |
| Realtime world view (38), Audio (40) | Hard | The full tick batch through the Sim core's facade (R15) | Presentation inputs |
| Local save and migration (6) | Hard | `snapshot_history()`, `restore_history(snapshot, core_tick)` (R11) | A bounded, versioned history to persist |
| Offline progress (31) | Soft | Summary events emitted after a skip (R12) | A Chronicle entry for each absence. It can run without the bus, but the gap then leaves no record |
| Dev tooling and parity harness (43) | Soft (build-time) | `type_table_hash` (F2) | A recorded vocabulary hash beside `phase_table_hash` |

"Hard" means the dependent cannot meet its own acceptance criteria without this system.

**Consistency with the systems index.** Row 42 lists Sim core and Data layer. Rows 6, 25, 31, 36, 37, 38, 40, 41 and 44 list Event bus (checked 2026-11-16).

**Bidirectional status.** Only the Sim core GDD names this system today. The Data layer GDD must add the five config keys and validator rules. The Dev tooling GDD must record `type_table_hash`. Every undesigned dependent must list this system when it is designed.

**Provisional assumptions about undesigned systems.**
1. Local save (6) accepts that the bus gives it a bounded snapshot and that it must pass `core_tick` on restore.
2. Offline progress (31) emits its summary as ordinary events in the first tick after a skip.
3. The Chronicle owner pages its reads.
4. Member IDs are never reused within a save, departed members keep a name record, and `milestone_subjects_planned` = 1,000 holds (OQ-4).
5. Every emitter follows R3a (roster changes are milestones; milestone subjects are guild members).

## Tuning Knobs

The knobs below are `config.csv` rows. They bound memory and history reach. None changes how fast the guild earns or fights. They were derived from Section D's variable tables: every `data file` variable is a knob, and every `constant` is listed under "Not knobs".

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `history_ring_cap` | 10,000 | 100 – 100,000 | Memory and snapshot size grow (F3: 480 KB at the default, 4.8 MB at the max). The span exceeds what the Chronicle shows | The ring covers less time (F4). A 24 h absence may no longer fit, and the Chronicle's recent past is short | `r_logged` (F4), `away_span_target_s` (design constant), `snapshot_history()` size |
| `milestone_cap_total` | 4,000 | 100 – 50,000 | Memory grows (192 KB at the default); `read_history` merges more | Protection fails sooner (F5): the oldest subjects' first records are evicted | `milestone_cap_per_subject`, `milestone_cap_guildwide`, `milestone_keep_first`, `milestone_subjects_planned` |
| `milestone_cap_guildwide` | 200 | 10 – 1,000 | Guild-wide milestones take more of the total cap, so fewer member subjects fit (F5) | The guild's own story (boss kills, buildings) keeps only its first records and a short tail | `milestone_cap_total`, `milestone_keep_first` (must be smaller) |
| `milestone_cap_per_subject` | 24 | 2 – 100 | One long career fills the tier, and the total cap is hit sooner | A long-serving member's story is cut to the first records and a short rolling tail | `milestone_keep_first` (must be smaller), `milestone_cap_total` (must not be larger) |
| `milestone_keep_first` | 3 | 0 – (min(`milestone_cap_per_subject`, `milestone_cap_guildwide`) − 1) | Protected records use the total cap faster (F5: 1,266 member subjects at 3, 760 at 5, with subject 0 full) and leave a shorter rolling tail | 0: the day-one milestone can be evicted, which breaks Fantasy 3 | `milestone_cap_per_subject`, `milestone_cap_total` |

**Validator rules for the Data layer (OQ-7):**
- `history_ring_cap` is a whole number in 100 – 100,000.
- `milestone_cap_total` is a whole number in 100 – 50,000.
- `milestone_cap_per_subject` is a whole number in 2 – 100.
- `milestone_cap_guildwide` is a whole number in 10 – 1,000.
- `milestone_keep_first` is a whole number in 0 – (min(`milestone_cap_per_subject`, `milestone_cap_guildwide`) − 1).
- Sizing (F5): `milestone_cap_total ≥ milestone_keep_first × 1,000 + milestone_cap_guildwide`, where 1,000 is `milestone_subjects_planned`.

**Interactions.**
- `milestone_keep_first` and `milestone_cap_per_subject` set the rolling tail: `milestone_cap_per_subject − milestone_keep_first` (21 at the defaults). If `milestone_keep_first` is one below the cap, the tail is a single record.
- `milestone_keep_first × subjects + milestone_cap_guildwide ≤ milestone_cap_total` is the F5 fit, and the validator enforces it at the planning bound. Raising either side without the other shortens the number of subjects that stay protected.
- `history_ring_cap` and the declared `ring_per_day` sum set the ring's span (F4), and `seal()` enforces the budget.
- Changing a cap in a patch is safe for old saves, because `restore_history` trims through R7's eviction rules (R11).

**Not knobs, and where their values live.**
- **Record stride (5 in the buffer, 6 in history)**, the payload limit of 4, and the type ID range. Changing any is a `sim_version` bump and a save migration.
- **`S` ≤ 16 subscribers.** A validator limit that bounds F1.
- **`away_span_target_s` (86,400)** is a planning constant for F4.
- **`milestone_subjects_planned` (1,000, provisional)** is a planning constant for F5, owned with Member model (OQ-4).
- **`E_floor` (50, provisional)** is the spike's pass floor (F1), replaced by the emitter GDDs' sums.
- **`event_buffer_hard_cap`** is the Sim core's knob. It interacts here through F3's transient memory and F1's cost. It is pointed to, not duplicated.
- **`p6_share` and `sim_slice_budget_us`** belong to the Sim core (F6).
- **Fail codes 42001 – 42003** and each owner's event type IDs.

*Lens applied: systems-designer (Section G). No game-balance values are involved. The defaults are provisional until the P1 spike measures the emission rates.*

## Visual/Audio Requirements

None for this system. The bus has no presentation. The visual and audio response to each event belongs to the Realtime world view (38) and Audio (40), which read the tick's batch through the Sim core facade (R15). Suppressing animation and sound while the game catches up is theirs too (R12).

## Game Feel

The bus has no feel of its own, but it sets one timing promise the presentation can rely on:
- An event emitted in P1–P5 of tick N is delivered in P6 of tick N. At 10 ticks per second that is under 100 ms from cause to delivery.
- An event emitted from P6 (by a subscriber) is delivered in tick N + 1, so at most one more tick (100 ms).
- Order within a tick is exact, so a drop never appears before the kill that caused it.
- AC-2a, AC-2b and AC-7b test the two latencies. Smoothing between ticks is the presentation's job (Sim core F3).

## UI Requirements

None. The bus has no screen. The Chronicle screen that narrates history (`bld_chronicle`) reads it through `read_history` and `milestones_for` (R8). Its owner is unassigned (OQ-8), and its requirements (paging, caching, empty state, unknown event types) are not authored here. No UX flag is raised, because this system has no UI of its own.

## Cross-References

| This document references | Target | Element | Nature |
|---|---|---|---|
| P6 as the `publish` phase; the bus as its handler | `sim-core-and-tick-loop.md` | R2 (phase table), Interactions row 42 | Ownership handoff: the core owns the buffer, the bus owns delivery |
| Handler Callable rules, `order` allocation in steps of 100 | `sim-core-and-tick-loop.md` | R4 | Rule dependency |
| `ctx.emit`, `ctx.submit`, `ctx.fail`; events emitted in P6 go to the next tick | `sim-core-and-tick-loop.md` | R5, Edge Cases (events and publish) | Rule dependency |
| Failed tick discards its events; `fail_owner_id`; fail code ranges | `sim-core-and-tick-loop.md` | R10 | Rule dependency |
| Event buffer caps (soft 1,000, hard 2,000) | `sim-core-and-tick-loop.md` | Edge Cases; registry `event_buffer_hard_cap` | Data dependency |
| Presentation reads the batch through the facade | `sim-core-and-tick-loop.md` | R15 | Rule dependency |
| The core saves no event buffer; int64 values are saved as decimal strings | `sim-core-and-tick-loop.md` | R14, AC-29b | Rule dependency (R11 encoding, AC-16 fixture) |
| The single-tick bound and the sum-of-phases gate | `sim-core-and-tick-loop.md` | F6, AC-34 | Formula dependency (F1 budget) |
| `sim_slice_budget_us`, the P6 share | `sim-core-and-tick-loop.md` | R17, F6 | Formula dependency (F1) |
| Buffer ownership and history bound | `sim-core-and-tick-loop.md` | OQ-3, OQ-10 | This GDD resolves both |
| Core AC-33 and AC-11 | `sim-core-and-tick-loop.md` | AC-33, AC-11 | This GDD's AC-27 and AC-28 close them |
| `config.csv` keys and validator ranges | `data-layer-and-content-pipeline.md` | R4 (typed tables); OQ-7 here | Data dependency |
| IDs, not display text, in records | `data-layer-and-content-pipeline.md` | R3 (stable IDs), R9 (display text is not content) | Rule dependency |
| `type_table_hash` recorded beside `phase_table_hash`; stride change is a `sim_version` bump | `dev-tooling-and-parity-harness.md` | R7 (version rule) | Ownership handoff |
| The log is written by the main design | `JX1_Tycoon_GDD.md` | §3.4 step 6, §9.2 | Source of intent |

## Acceptance Criteria

Story types follow the Testing Standards:
- **[Logic]** is the default: an automated unit test under `tests/unit/event-bus/`. Logic tests drive the bus through a **fake context**, a `RefCounted` with `tick()`, `events()`, `emit()`, `submit()`, `fail()` and `failed`. The bus treats `ctx` as duck-typed, so no real core is needed.
- **[Integration]** uses the real Sim core, under `tests/integration/event-bus/`.
- **[Integration, device]** is a measurement on the named min-spec device, under `tests/performance/`. It is ADVISORY, with evidence in `production/qa/evidence/`.

Caps come from a fixture factory, not inline numbers, except where the exact value is the boundary being tested. A criterion with several GIVEN/THEN pairs is one parametrized test with one case per pair. `[PENDING: …]` marks a criterion that needs a system or measurement that does not exist yet; it is a separate criterion, so the ones beside it can close.

**Core rules**

- **AC-1 [Integration] (R1)**: **GIVEN** a bus and core sealed with a stub P3 emitter, **WHEN** the core's registration list (the input to `phase_table_hash`, Sim core R4) is read, **THEN** it holds exactly one P6 entry, `owner_id = "event_bus"` at `order = 100`.
- **AC-2a (R2)**: **GIVEN** type 100 registered with `field_count 2`, **WHEN** the fake context returns `(100, 7, 9, 0, 0)` for tick 5, **THEN** a subscriber to 100 receives exactly `[5, 100, 7, 9, 0, 0]`.
- **AC-2b [Integration] (R2)**: **GIVEN** a P6 subscriber that emits in tick 5, **THEN** the event arrives in tick 6 with `tick = 6`.
- **AC-3a (R3)**: **GIVEN** each of these registrations, **WHEN** `seal()` runs, **THEN** it returns an error naming the owner, the bus stays `Registering` and nothing is frozen:
  - a duplicate `type_id`; `type_id` 0 or 65,536;
  - `type_id` 50 from an owner other than `sim_core`;
  - `field_count` 5; `subject_slot` above `field_count`; `milestone` without `logged`;
  - an `owner_id` or `name` that is empty, 49 characters long, or `"Sim-Core"`;
  - a nonzero `ring_per_day` on a type that is not logged, or that is a milestone.

  Each `register_type` call itself returns OK (checks run at `seal()`).
- **AC-3b (R3)**: **GIVEN** `type_id` 1 (owner `sim_core`) and 65,535, `field_count` 0 and 4, `subject_slot` equal to `field_count`, and a 48-character name, **THEN** each seals.
- **AC-4a (R4)**: **GIVEN** each of these subscriptions, **THEN** `seal()` errors naming the owner(s):
  - two subscribers at one `order` (both owners named);
  - an unregistered type; an empty `type_ids`;
  - 17 subscribers;
  - a one-argument method, a bound Callable, a lambda, or a method with a defaulted third parameter.
- **AC-4b (R4)**: **GIVEN** 16 subscribers, **THEN** it seals. **GIVEN** a subscriber with `ALL` and three types emitted, **THEN** it receives all three in emission order.
- **AC-4c (R4)**: **GIVEN** a subscriber object referenced only by the bus, **WHEN** the test drops its own reference, **THEN** the handler is still valid and is called. **GIVEN** a handler object freed explicitly after `seal()`, **THEN** the next P6 that would call it fails with 42003 naming the subscriber's `owner_id`.
- **AC-5 (R5)**: **GIVEN** three subscribers at orders 300, 100 and 200, and events emitted in the order `e1` (type A), `e2` (type B), `e3` (type A), **WHEN** one tick runs, **THEN** the subscribers are called in 100, 200, 300 order, each exactly once with only its listed types in emission order. A subscriber whose types are absent is not called.
- **AC-6 [Integration] (R5, R10)**: **GIVEN** three subscribers where the second calls `ctx.fail(1001, "x")` and then keeps running, **WHEN** the tick runs, **THEN** the third is not called, history is unchanged, the first received its batch, and the core is `Failed` with `fail_owner_id = "event_bus"` and a message naming the second subscriber.
- **AC-7a (R5)**: **GIVEN** subscriber A writes `batch[0] = -1` and subscriber B lists the same type, **THEN** B's batch and the committed history are unchanged. This is also the P1 spike's check of packed-array reference semantics (OQ-9).
- **AC-7b [Integration] (R6)**: **GIVEN** a subscriber emits during P6 of tick N, **THEN** the event is delivered in tick N + 1, not N, to every subscriber including ones with a higher `order`. **GIVEN** a subscriber calls `ctx.submit` during P6 of tick N, **THEN** the command is in tick N + 1's `ctx.commands()`.
- **AC-8 (R6)**: **GIVEN** a subscriber that calls `read_history(0, 1000)` during P6, **THEN** the result excludes the batch being delivered and includes the previous tick's.
- **AC-9 (R7, ring)**: **GIVEN** `history_ring_cap = 100` (the minimum) and 100 ring-type events, **THEN** the ring holds 100 and none is evicted. **GIVEN** a 101st, **THEN** the ring holds 100, the oldest record is gone, and `read_history` still returns ascending ticks. The ring's backing array is 600 ints long at every step (no resize).
- **AC-10 (R7, per subject)**: **GIVEN** `milestone_cap_per_subject = 5`, `milestone_keep_first = 2` and 8 milestones for subject 7, **THEN** the tier holds the 1st, 2nd, 6th, 7th and 8th.
- **AC-11 (R7, beyond the planning bound)**: The fixture bypasses the F5 sizing rule. **GIVEN** `milestone_cap_total = 100`, `milestone_keep_first = 3`, and 33 subjects each with 3 milestones (99 records), **THEN** all 99 are retained. **GIVEN** a 34th subject's first, second and third milestones, **THEN** after the 100th the tier holds 100. After the 101st, the oldest record of the tier (subject 1's first) is evicted by R7 step 3. After the 102nd, subject 1's second is evicted. This is the F5 boundary: 100 protected records fit, 101 do not.
- **AC-12a (R7, subject 0)**: **GIVEN** `milestone_cap_guildwide = 5`, `milestone_keep_first = 2` and 8 guild-wide milestones (subject 0), **THEN** the tier holds the 1st, 2nd, 6th, 7th and 8th.
- **AC-12b (R7, both limits)**: **GIVEN** `milestone_cap_total = 10`, `milestone_cap_per_subject = 3`, `milestone_keep_first = 1`, and subjects 1–4 holding 3, 3, 3 and 1 records, **WHEN** subject 1's 4th arrives, **THEN** exactly one record is evicted (subject 1's 2nd). Subject 1 holds its 1st, 3rd and 4th, and the other subjects are unchanged.
- **AC-12c (R7)**: **GIVEN** a milestone type and a ring type, **THEN** `size().ring` counts only the ring type. **GIVEN** two milestones for one subject in one tick, **THEN** both are stored, in emission order. **GIVEN** a milestone whose subject slot holds 0, **THEN** it counts against `milestone_cap_guildwide`.
- **AC-13a (R8)**: **GIVEN** a ring record and a milestone at tick 5 and one record at tick 6, **THEN** `read_history(5, 6)` returns the milestone first, then the ring record, then tick 6. **THEN** `read_history(5, 5)` returns the two tick-5 records, `read_history(6, 5)` returns empty, and a range with no records returns empty.
- **AC-13b (R8, paging)**: **GIVEN** records at ticks 1, 2, 2, 3 and `max_records = 2`, **THEN** the first page returns tick 1 only (tick 2 would split), the call from tick 2 returns both tick-2 records, and the call from tick 3 returns tick 3. **GIVEN** three records at tick 1 and `max_records = 2`, **THEN** all three are returned.
- **AC-13c (R8)**: **GIVEN** milestones for subjects 7 and 8, **THEN** `milestones_for(7)` returns only subject 7's, in tick order, and `size()` matches both tiers. **GIVEN** a test that writes to any returned array, **THEN** a later identical query is unchanged. **GIVEN** a fake context with `failed = true`, **THEN** each query returns empty.
- **AC-14 (R9)**: **GIVEN** a fake context whose `events()` returns, in turn:
  1. an unregistered `type_id`;
  2. a nonzero unused slot;
  3. a negative value in the `subject_slot` of a milestone type with `subject_slot = 1`;
  4. 7 ints.

  **WHEN** P6 runs, **THEN** `fail(42001, msg)` is called once, no subscriber is called and history is unchanged. In cases 1–3 the message contains the buffer index and `type_id`; in case 4 it contains the length 7.
- **AC-15a (R10)**: **GIVEN** an unsealed bus, **THEN** its P6 handler calls `fail(42002, …)`.
- **AC-15b (R10)**: **GIVEN** a sealed bus, **THEN** a second `seal()` returns OK with the same hash.
- **AC-15c (R10)**: **GIVEN** a sealed bus, **THEN** `register_type` and `subscribe` each return an error code, and the hash is unchanged.
- **AC-15d (States)**: **GIVEN** a bus in `Registering`, and one in `Sealed`, **WHEN** `dispose()` is called, **THEN** each is `Disposed` and later `register_type`, `subscribe` and `seal()` return errors. **GIVEN** a `seal()` that failed because a subscriber listed an unregistered type, **WHEN** that type is registered and `seal()` is called again, **THEN** it succeeds.
- **AC-16 [Integration] (R11, round trip)**: The fixture has a synthetic P3 emitter and no P6 emitters, because the core does not save its event buffer (Sim core R14). **GIVEN** run A of 200 ticks, and run B of 100 ticks on the same seed, **WHEN** run B takes `snapshot_core()` and `snapshot_history()`, a fresh core and bus restore them (`restore_history(snapshot, 100)`), seal, start and run 100 more ticks, **THEN** `read_history(0, 199)` paged to the end is equal in both runs, element for element.
- **AC-17a (R11)**: **GIVEN** a snapshot whose last record is tick 99, **THEN** `restore_history(snapshot, 100)` returns `ok = true`. **GIVEN** a last record of tick 100, **THEN** `ok = false` and nothing changes.
- **AC-17b (R11, trimming)**: **GIVEN** 150 ring records restored into `history_ring_cap = 100`, **THEN** the ring holds the newest 100 and `trimmed_count = 50`. **GIVEN** 8 milestones for subject 7 restored into `milestone_cap_per_subject = 5`, `milestone_keep_first = 2`, **THEN** the tier holds the 1st, 2nd, 6th, 7th and 8th, and `trimmed_count = 3`.
- **AC-17c (R11, retired types)**: **GIVEN** a milestone record whose type is no longer registered, **THEN** it is kept under its saved subject and `unknown_type_count = 1`. **GIVEN** a different type table, **THEN** `ok = true` and `hash_mismatch = true`.
- **AC-17d (R11, order)**: **GIVEN** descending ticks in a tier, **THEN** `ok = false`. **GIVEN** two records with equal ticks, **THEN** `ok = true`. **GIVEN** an empty snapshot at `core_tick = 0`, **THEN** `ok = true`.
- **AC-17e (R11, timing)**: **GIVEN** a second `restore_history`, or one called before `seal()`, **THEN** `ok = false`. **GIVEN** `snapshot_history()` called inside a handler, with a hand-off pending, or with the core `Failed` `[Integration]`, **THEN** each returns an error and no snapshot.
- **AC-18 [Integration] (R12)**: The fixture is a synthetic emitter with one ring event per tick and one milestone every 10 ticks. **GIVEN** two equal cores, one run with `run_ticks(50)` and one through `advance(0, 1)` calls in catch-up, one tick per call, to the same tick, **THEN** their histories are identical.
- **AC-18b [Integration] (R12)**: **GIVEN** a hand-off gap of 600 ticks resolved by `skip_ticks`, **THEN** `read_history` over the gap returns the records on both sides with no record inside it, and a snapshot taken after it restores with `ok = true`.

**Formulas**

- **AC-19 (F1, empty buffer)**: **GIVEN** a tick with no events, **THEN** no subscriber is called and history is unchanged. **GIVEN** a tick whose only event is a non-logged type with no subscriber, **THEN** history is unchanged and nothing is called. This tests behaviour, not allocations (Gaps).
- **AC-20a (F1)**: **GIVEN** the F1 example inputs, **THEN** the F1 function gives `E_budget = 198`. **GIVEN** S = 16, `c_call` = 50 and `c_fixed` = 100, **THEN** it gives 0.
- **AC-20b [Integration, device] [PENDING: P1 spike] (F1)**: release build, max-roster fixture, named min-spec device.
  - **Run A (measure):** 300 warm-up ticks discarded, then 3,000 ticks at each of E = 0, 50, 200, 1,000 and 2,000, with S = 6 and 16 and `k̄` = 1 and S, the ring full, and the tier full with 1,000 member subjects. The event mix is 30% logged and 2% milestone. It derives each `c_*` at p99 and `E_budget`.
  - **Pass 1:** `E_budget ≥ E_floor`, where `E_floor` is fixed before Run A.
  - **Run B (verify):** 36,000 ticks at E = `E_budget`, once cold and once after 20 minutes of sustained load. **Pass 2:** p99 `c_p6` ≤ `p6_share × sim_slice_budget_us`.
  - **Linearity:** measured `c_p6` at E = 1,000 is within 25% of F1's prediction.
  - **Reported, no gate:** max `c_p6` at E = 2,000, and slices per frame and overruns during a catch-up drain at E = `E_budget`.
- **AC-21a (F2)**: **GIVEN** two types registered in either order, **THEN** `type_table_hash` is equal. **GIVEN** any one field changed (including a flag), **THEN** it differs. **GIVEN** zero types, **THEN** it equals `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. **GIVEN** the F2 example type, **THEN** it equals the committed known answer `77e1e65233cb5cf05b48e87bf58eca6d74e056d465589dde2612ed7641c8b25a`.
- **AC-21b [PENDING: engine, CI] (F2)**: **GIVEN** a committed fixture table of 50 types, **THEN** the GDScript digest equals Python `hashlib` over the same framed bytes.
- **AC-22a (F3)**: **GIVEN** `history_ring_cap = 100`, `milestone_cap_total = 100`, `milestone_cap_guildwide = 10`, `milestone_keep_first = 1` and a synthetic emitter that overfills both tiers, **WHEN** 2,000 ticks run, **THEN** the sizes equal the caps at tick 1,000 and at tick 2,000, and `48 × (ring + milestones) + 16 × milestones ≤ 11,200`. **GIVEN** 2,000 events and 6 subscribers to `ALL`, **THEN** Σ `batch.size() × 8` over the batches is at most 672,000.
- **AC-22b [Integration, device] [PENDING: P1 spike, engine] (F3)**: **GIVEN** default caps and the same emitter, **WHEN** 288,000 ticks (8 h at 10 Hz) run, **THEN** process memory at tick 288,000 is within 1 MB of tick 144,000.
- **AC-23 (F4)**: **GIVEN** `history_ring_cap = 100` and one ring record at each of ticks 0, 10, …, 4,990, **THEN** the oldest ring record is exactly tick 4,000. **GIVEN** no ring-type events, **THEN** the ring stays empty.
- **AC-23b (F4, seal budget)**: **GIVEN** default caps and types whose `ring_per_day` sums to 10,000, **THEN** `seal()` succeeds. **GIVEN** a sum of 10,001, **THEN** it fails with an error listing every type's rate.
- **AC-24a (F5)**: AC-11 covers the boundary (100 protected fit, 101 do not). **GIVEN** `milestone_keep_first = 0`, **THEN** a subject's first record is evictable.
- **AC-24b [PENDING: Data layer validator, OQ-7] (F5)**: **GIVEN** `milestone_keep_first` equal to `milestone_cap_per_subject` or to `milestone_cap_guildwide`, **THEN** it is rejected. **GIVEN** `milestone_keep_first = 3` and `milestone_cap_guildwide = 200`, **THEN** `milestone_cap_total = 3,199` is rejected and 3,200 is accepted.

**Edge cases and cross-system**

- **AC-25 (Edge Cases, delivery)**: **GIVEN** exactly 2,000 events in one tick (the core's cap), **THEN** the tick completes and every record is delivered in order.
- **AC-26 (Edge Cases, boot)**: **GIVEN** zero types and zero subscribers, **THEN** `seal()` succeeds with the empty hash, and ticks run with no calls and no failure.
- **AC-27 [Integration] (Sim core AC-33)**: **GIVEN** the bus as the registered P6 handler and a P2 emitter, **WHEN** the same tick then fails in P3, **THEN** the P2 event is never delivered and history is unchanged. This closes the Sim core's pending AC-33.
- **AC-28 [Integration] (Sim core AC-11)**: **GIVEN** `command_queue_max = 100` and 103 commands submitted before tick N, the next tick to run, **THEN** in tick N a subscriber to type 1 receives exactly one record `[N, 1, 3, 0, 0, 0]`.
- **AC-29 [PENDING: Data layer validator, OQ-7] (config)**: **GIVEN** each of these, **THEN** it is rejected:
  - `history_ring_cap` 99 or 100,001;
  - `milestone_cap_total` 99 or 50,001;
  - `milestone_cap_per_subject` 1 or 101;
  - `milestone_cap_guildwide` 9 or 1,001.

  **GIVEN** each key at each end of its range (100 and 100,000; 100 and 50,000; 2 and 100; 10 and 1,000), with the other keys at defaults that satisfy the sizing rule, **THEN** each is accepted.
- **AC-30 (Fantasy 3)**: **GIVEN** a milestone for member 7, **WHEN** member 7 is renamed and the locale is switched, **THEN** `milestones_for(7)` is unchanged, element for element.
- **AC-30b [Integration] [PENDING: Member model (8)] (Fantasy 3)**: **GIVEN** member 7 with a milestone who is renamed and then leaves the guild, **THEN** Member model still resolves ID 7 to a name, and no later member is issued ID 7.

**Gaps, recorded not hidden**
1. **R3 "type IDs are permanent"** has no automated test here. Nothing in the bus can see a previous build's table, so it needs a tooling check against `HEAD`, owned by Dev tooling (43) (OQ-5).
2. **R3a** (roster changes are milestones; milestone subjects are guild members) cannot be checked by the bus. Each emitter GDD's own ACs must test it.
3. **F1 "no allocation on an empty buffer"** is not observable without engine counters. AC-19 tests behaviour, and the spike measures cost (AC-20b).

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Partly resolved 2026-11-16:** the Sim core now says `ctx.emit(type_id, a, b, c, d)`, stride 5, and `commands_dropped` is type 1 with `a = count`. **Still open:** the core should record the emitting handler's `owner_id` per event, so R9 can name the emitter of a bad record. Without it a 42001 names only the buffer index and `type_id` | Sim core (1) | Before the Sim core's next `/design-review` |
| OQ-2 | Offline summary events: type, schema (gap length, XP and gold gained, bosses missed) and one record per absence | Offline progress (31) | When Offline's GDD is designed |
| OQ-3 | How the ring budget (Σ `ring_per_day` ≤ 10,000 at the defaults, F4) is split between emitters, and the real `E_floor` that replaces the provisional 50 (F1) | This GDD, with the first three emitter GDDs (Member model, Zones and hunt, Golden Boss) | When those three are designed |
| OQ-4 | Member IDs are never reused within a save; every issued ID keeps a name record after the member leaves (Fantasy 3, AC-30b); confirm `milestone_subjects_planned` = 1,000 (F5) | Member model (8) | When Member model is designed |
| OQ-5 | **Edge cases resolved 2026-11-16** (authored after design review). **Still open:** a tooling check that type IDs are permanent, against `HEAD` | Dev tooling (43) | Before `/gate-check` |
| OQ-6 | **Resolved 2026-11-16:** no per-type quota. Each type declares `ring_per_day`, `seal()` checks the sum (F4), and roster changes are milestones (R3a). Revisit only if the spike's measured rates exceed what owners declared | This GDD | Closed |
| OQ-7 | Five `config.csv` keys (including `milestone_cap_guildwide`), their range rules and the F5 sizing rule | Data layer (3) | When the Data layer next changes |
| OQ-8 | Who owns the Chronicle screen (Guild screens 39 or Guild and buildings 30), and who pages and caches its reads | Systems index owner | When screens are designed |
| OQ-9 | Unverified engine facts, NOT SOURCEABLE from the engine reference. R5 now assumes packed arrays are passed by reference and builds a fresh batch per subscriber; AC-7a confirms it. Still to measure: `get_argument_count()` for bound, lambda and default-argument Callables (R4), Dictionary entry size (F3), `PackedInt64Array` growth cost, `Callable` dispatch cost, flush time. The 4.7 packed-array element-write change must be checked against the log's write path | This GDD's ADR and the P1 spike | P1 spike |
| OQ-10 | Should the parity harness record a history hash as a golden output? | Dev tooling (43) | When Dev tooling is next revised |
