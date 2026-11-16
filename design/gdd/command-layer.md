# Command Layer

> **Status**: Designed (pending independent /design-review)
> **Author**: user + agents (autonomous batch run, `/design-system`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: CONCERNS (accepted) 2026-11-16 — no `game-pillars.md`; checked against the Player Fantasy and GDD §3.2/§6.4 instead. Rules R6, R7, R11 and F2 deliver the promised moment. Concern: orders queued at the moment of quitting are lost (Edge Cases, OQ-10), a small breach of "never eaten"; accepted pending playtest.
> **Implements Pillar**: none defined (no `game-pillars.md`); serves GDD §3.2 (one headless core shared by realtime, offline, simulator and server replay) and §6.4 (the player can order a member directly)

## Summary

The Command layer is the single doorway through which the player (and dev tools and server replay) change the guild simulation: every order becomes a small integer command that the Sim core queues and this layer validates and hands to the owning system in strict order in the next tick, accepted or refused with a reason and no side effects. It gives the player instant acknowledgement and next-tick obedience for every tap, and it keeps the log of player orders exact enough for leaderboard replay, while AI decisions stay inside the simulation.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Sim core, Event bus, Data layer`

## Overview

The Command layer is the only way anything outside the simulation changes it (GDD §3.2: presentation sends *commands*, the core sends back *events*). A player tap ("send Lan to the Bamboo Grove", "upgrade the Pharmacy", "change school"), a dev cheat and a replayed log entry all become the same thing: a small integer **command envelope** that the Sim core queues, stamps with a `seq` and drains in Phase 1 of the next tick (Sim core R6). This system owns what the core deliberately does not: the **command vocabulary** (which command types exist, who owns each, and their argument shapes), the **one P1 dispatcher** that validates every envelope and hands it to its owner's applier in `seq` order, the **outcome contract** (accepted, or refused with a reason code and no state change), the **origin tag** that keeps replay exact, and the host-side facade the UI calls. It holds no game rules: whether a school change is affordable is Schools' (20) decision, not this layer's. Without it, each feature would read the queue for itself, commands would apply in handler order instead of `seq` order, refusals would be ad hoc, and a replay would double-apply requests the simulation made to itself.

*Framing: technical (Core category). No ADR exists yet; the implementation pattern (a `RefCounted` service injected into the host, mirroring the Sim core and Event bus) becomes an ADR.*

## Player Fantasy

**Indirect.** Players never see the Command layer; they feel its promise: **"my order is taken at once and obeyed next tick, every time, or I am told why not."** That is the EHT-style direct control of GDD §6.4 ("the player can tap a member to give a direct order: buy items, learn a skill, go for treatment") made trustworthy.

Candidate framings considered (creative-direction lens; no pillars file, so each anchors to a GDD section instead of a quoted pillar):

1. **The obedient guild (chosen).** Moment: the player taps three injured members, presses "go heal", and three acknowledgement ticks appear instantly; a tenth of a second later all three turn toward the Thiện Đường. Anchor: §6.4 direct orders. Asks of the design: an immediate acknowledgement (R11), a ≤ 1-tick apply in normal play (F2), and a visible reason for every refusal (R7).
2. **The honest ledger.** Moment: a leaderboard entry is verified because the server replays exactly what the player ordered. Anchor: §8.1 anti-cheat replay. Asks: exact replay (R9). True but invisible to most players, so it is a consequence, not the fantasy.
3. **The master who delegates.** Moment: the player stops micromanaging and the AI keeps the guild running. Anchor: §9.1 Utility AI. Rejected as this system's fantasy: it belongs to Utility AI (12); this layer only guarantees a player order overrides the AI cleanly.

The player must never feel a tap was "eaten": a lost or silently ignored order is the failure this system exists to prevent.

## Detailed Design

### Core Rules

**Terms.** A *command* is one envelope (R1). Its *owner* is the system that registered its type and applies it. *Host* means code outside a tick: the UI, dev tools, a replay driver. *Sim* means a handler running inside a tick. A command is *accepted* when its applier returns 0 and *refused* when it returns a reason code. Tick numbering follows Sim core R1.

**R1 — The envelope is integers only.** A command is `{type_id, origin, args}`:
- `type_id`: an int registered under R2.
- `origin`: `0 = host`, `1 = sim`. Set by the submit path (R8), never by the caller.
- `args`: a `PackedInt64Array` of exactly the type's `arg_count` values (0 – 6, `cmd_args_max`). Each value is a member ID, an item-instance ID, a content row `uid` (Data layer), a quantity or a small enum.
- No strings, floats, Dictionaries, Objects or Callables. A content row is named by its `uid`, never its string key, so a log replays without the original session and survives a rename (Sim core R6).
- The Sim core stamps `seq` on `submit`. The envelope plus `seq` is what the command log stores. Any 64-bit value written to JSON is a string (Sim core R6).

**R2 — Command types are registered at boot.** `register_command(type_id, owner_id, name, arg_kinds, origins, dev_only, reason_codes, applier)`:
- `type_id` is unique and permanent. A retired ID is never reused, and a type whose argument meaning changes gets a new ID, or old logs replay wrongly.
- **ID blocks follow the owner's Event bus block** (Event bus R3): owner system number × 100, for example Schools (20) owns 2000 – 2099 and XP (22) owns 2200 – 2299. Command IDs and event IDs are separate namespaces, so one allocation serves both and two GDDs cannot collide. IDs 1 – 99 are reserved for this layer (none used in MVP). This layer's own block is 500 – 599, used for its events (R7).
- `owner_id` and `name` are 1 – 48 characters of `[a-z0-9_]`, as for event types.
- `arg_kinds` is a list of 0 – 6 kinds, one per argument:

  | Kind | Checked by this layer (R4) | Example |
  |---|---|---|
  | `int(min, max)` | inclusive int64 range | a quantity 1 – 999; an enum 0 – 4 |
  | `content(table)` | the `uid` exists in that content table | a school, a ground, a building row |
  | `entity` | `≥ 0` only; the owner resolves it | a member, an item instance, a candidate |

- `origins` is a non-empty subset of `{host, sim}`.
- `dev_only` marks cheats and debug commands (R13).
- `reason_codes` lists the owner's own refusal codes (100 – 999, unique within the type), each with a stable `[a-z0-9_]` name used for its localisation key (R6).
- `applier` is an unbound method Callable on a live object taking exactly two arguments `(cmd, ctx)` and returning an int, under the same Callable rules as Sim core R4 and Event bus R4. The layer holds a strong reference to its object.
- Registration is open only while the layer is `Registering`. Every check runs at `seal()`, and a failure is a boot error naming the owner and `type_id`.

**R3 — One P1 dispatcher, in `seq` order.** The layer registers exactly one Sim core handler, `register(P1, 100, "command_layer", dispatch)`. **It is the only handler that reads `ctx.commands()`.** Features do not register P1 handlers to read the queue; they register appliers here. (Per-owner P1 readers would apply commands in handler order, not `seq` order, and break Sim core R6 and its "the second sees the state the first left" edge case.) Other P1 handlers may run at order ≥ 200 for work that must follow the tick's commands. For each command in ascending `seq`:
1. Check the envelope (R4). On a failure, refuse it with that code and go to step 5.
2. Call `applier(cmd, ctx)` and take its return `r`.
3. If `ctx.failed` is set, return at once (Sim core R10).
4. Check `r`: it must be 0, a shared code 6 – 9 (R6) or one of the type's registered codes. Anything else (a non-int, a negative value, an unregistered code, an envelope-only code 1 – 5) is a bug: `ctx.fail(5001, msg)` naming the owner, `type_id` and value, and return.
5. Report the outcome (R7).

A command sees the state every earlier command of the same P1 left. That is the whole conflict rule: two orders for one member resolve by `seq`, and the second is judged on the state the first produced.

**R4 — Envelope checks, first failure wins.** In this order:
1. `type_id` not registered → `unknown_type` (1).
2. `args` length differs from `arg_count` → `bad_arity` (2).
3. `origin` not in the type's `origins` → `origin_not_allowed` (4).
4. `dev_only` type in a release build → `dev_disabled` (5).
5. An `int` arg outside its range, a `content` uid absent from its table, or a negative `entity` → `bad_arg` (3).

The layer does not check whether an entity exists, whether content is live in this wave, or anything about game state. Those are the owner's (R5, R14).

**R5 — The applier contract: all or nothing.**
- **Refuse** by returning a reason code > 0. A refusal changes no state in any system, takes no cost, submits nothing and emits no outcome of its own (R7 reports it). Drawing from a derived RNG generator does not count as a state change, because derived generators are fresh per event (RNG R3).
- **Accept** by applying the command fully and returning 0. It may emit its owner's events, request follow-up commands (R8), call other systems' in-sim APIs as their GDDs allow (for example a Gold economy debit), and derive RNG under its own domain.
- **Validate before mutating.** An applier checks every condition before its first write. If it finds, after a write, that it cannot finish, that is a bug: it calls `ctx.fail` with its own code, never returns a refusal, because a refusal after a write would be a partial order.
- Every Sim core R5 prohibition applies (no clock, no `await`, no nodes, no engine random).
- Each owner's GDD states its applier's cost (F3).

**R6 — Reason codes.** One integer per refusal, shown to the player as words (UI Requirements).

| Code | Name | Raised by | Meaning |
|---|---|---|---|
| 1 | `unknown_type` | layer | No such command type |
| 2 | `bad_arity` | layer | Wrong number of arguments |
| 3 | `bad_arg` | layer | Argument out of range or content row missing |
| 4 | `origin_not_allowed` | layer | Host sent a sim-only command, or the reverse |
| 5 | `dev_disabled` | layer | Dev-only command in a release build |
| 6 | `target_missing` | owner (shared) | The member, item or candidate no longer exists |
| 7 | `not_allowed_now` | owner (shared) | The target's state forbids it (for example a member in `boss_raid`) |
| 8 | `cannot_afford` | owner (shared) | The guild lacks the gold or items |
| 9 | `not_live` | owner (shared) | The content is not live in the current wave |
| 10 | `host_queue_full` | facade only | Host cap reached (F1); never in an event |
| 11 | `core_refused` | facade only | The Sim core's `submit` returned 0 (queue full, `Failed`, not sealed); never in an event |
| 100 – 999 | owner-defined | owner | Registered per type in R2 |

Localisation keys: `cmd_reason.<name>` for codes 1 – 11, and `cmd_reason.<owner_id>.<name>` for owner codes. Localization (4) owns the text. Owners should reuse 6 – 9 rather than define their own copy.

**R7 — Outcome events, host commands only.** This layer registers two event types in its block (Event bus R3):

| `type_id` | Name | Fields | `logged` | `milestone` |
|---|---|---|---|---|
| 501 | `command_applied` | `a = seq`, `b = type_id` | no | no |
| 502 | `command_refused` | `a = seq`, `b = type_id`, `c = reason_code` | no | no |

- Emitted in P1, so they are delivered in P6 of the **same** tick. `ring_per_day = 0` (not logged).
- Emitted only for `origin = host`. A sim-origin outcome adds 1 to the query counters `sim_applied_count` or `sim_refused_count` (not saved). A system that needs a player-visible consequence of its own refused request emits its own event.
- Not logged, because an accepted command's effect is already recorded by its owner's events (for example Schools' `school_change_started`). These two are acknowledgement plumbing for the UI. At most `command_drain_max` of them per tick.

**R8 — Two submit paths set the origin.**
- **Host path:** `commands.submit(type_id, args) → [seq, reason]`. The facade builds an `origin = host` envelope, pre-checks `unknown_type` and `bad_arity` (cheap, saves a tick), checks the host cap (F1), then calls the core's `submit`. `seq > 0` means queued, with `reason = 0`. `seq = 0` means refused now, with `reason` one of 1, 2, 10 or 11. `commands.submit_batch(list) → [[seq, reason], …]` queues a list **all or nothing** against the host cap (R12).
- **Sim path:** `commands.request(ctx, type_id, args)` builds an `origin = sim` envelope and calls `ctx.submit`. It applies in P1 of the next tick (Sim core R6). This is how a feature asks for a change it will apply through its own applier, for example Schools' `join_school` (Schools R3).
- The caller never sets `origin`. A handler that hand-builds a host envelope and calls `ctx.submit` directly would corrupt replay (R9). Nothing at runtime can stop it in GDScript, so the parity harness (43) and code review catch it (OQ-4).

**R9 — Replay re-submits host commands only, in `seq` order.** The command log (Sim core R6) stores every applied envelope with its `origin`.
- A replay driver (Leaderboards 35, the parity harness 43) re-submits **only `origin = host` entries**. Sim-origin entries are regenerated by the replayed handlers; re-submitting them would apply them twice.
- It submits through `commands.submit_replay(envelope) → seq`, which skips the host cap (the original was accepted) but not the core's checks.
- **It submits by `seq`, not by apply stamp.** Host submits happen only between ticks and sim submits only inside ticks, so between two ticks the host's commands hold a contiguous `seq` range. Before running each tick, the driver submits every logged host entry whose `seq` equals the core's next `seq`, in ascending order, and stops at the first that does not. This reproduces every `seq` even when `command_drain_max` delays application by several ticks (F2). Re-submitting by apply stamp would not: a host command queued before tick N and applied in tick N+1 would get a later `seq` than a request a handler made during tick N.
- A returned `seq` that differs from the logged one is a replay divergence. The driver's response is Leaderboards' policy.
- The core exposes it as `next_command_seq()` (Sim core R6; OQ-2 resolved).

**R10 — AI decisions are not commands.** Utility AI (12) scores options and the Member state machine (41) applies the choice inside P2 of the same tick. Neither goes through the queue: that would add a tick of latency to every AI choice, fill the log with entries replay regenerates anyway, and let AI volume crowd the drain cap ahead of the player. **A player's direct order is a host command** owned by the Member state machine (41). It sets an override that the AI respects until the order completes or is cleared (GDD §6.4, §9.1: "player orders override").

**R11 — Acknowledge at once, resolve next tick.** The UI marks an order pending the moment `submit` returns `seq > 0`, and resolves it when a `command_applied` or `command_refused` with that `seq` is delivered. A host refusal (`seq = 0`) is shown at once with its reason. Pending orders survive pause, catch-up and a pending hand-off; they simply resolve later (Sim core R17). The queue is never saved (Sim core R14), so a pending set is never saved either, and a load starts with none pending.

**R12 — Multi-target orders expand to one command per target.** "Send all selected to the Bamboo Grove" becomes one command per member, submitted together through `submit_batch` in the displayed order. Each gets its own `seq` and outcome, so one refused member (injured) does not block the rest. The batch is refused whole with `host_queue_full` if it does not fit the host cap (F1), so the player never sees half an order queued. The drain cap spreads a large batch over a few ticks (F2).

**R13 — Dev commands.** A `dev_only` type (grant gold, set level, force a Golden Boss) is registered in every build, so `command_table_hash` (F4) is the same in dev and release, and is refused with `dev_disabled` in a release build. Host origin only. Whether a log containing an applied dev command can rank is Leaderboards' rule (OQ-5).

**R14 — Gating is the owner's.** The layer never checks wave liveness, Premium entitlement, building levels or member states. The owner's applier reads them (the entitlement snapshot is injected input, systems index) and refuses with `not_live`, `not_allowed_now` or an owner code. A locked feature's UI should hide or disable its button, but the applier's refusal is the rule.

**R15 — State and persistence.** The layer's state is the frozen registry, `host_pending` (int ≥ 0, host commands queued and not yet drained), `sim_applied_count` and `sim_refused_count`. It saves nothing. The queue is not saved (Sim core R14), so `host_pending` restarts at 0 on load. The registry's shape is hashed (F4) and recorded by the parity harness; a change that alters results for the same log is a `sim_version` bump (Sim core R12, Dev tooling R7).

**R16 — Boot order.** The host calls `commands.seal()` before `core.seal()`, alongside `bus.seal()` (Event bus R10). `seal()` runs every R2 check, freezes the registry, computes `command_table_hash` and moves `Registering → Sealed`. The layer registers its two event types with the bus and its P1 handler with the core while both are still open. A `dispatch` call while the layer is `Registering` calls `ctx.fail(5002, "command layer not sealed")`.

**Fail codes** (system 5 → 5001 – 5099): 5001 an applier returned an invalid value (R3); 5002 dispatch before `seal()` (R16); 5003 an applier's object was freed (checked before each call, as Event bus R4).

#### MVP command vocabulary

The vocabulary is owned here; each command's rules are owned by its owner's GDD. IDs are allocated inside the owner's block by that owner's GDD; only Schools' are proposed here, because the Schools GDD names its commands but not their IDs. Every row except Schools is **PROVISIONAL** until its owner's GDD exists.

| Command | Owner | Args (`arg_kinds`) | Origins | Source |
|---|---|---|---|---|
| `set_aspiring_school` (2001) | Schools (20) | member `entity`, school `content(schools)` | host | Schools R3 |
| `change_school` (2002) | Schools (20) | member `entity`, school `content(schools)` | host | Schools R4 |
| `join_school` (2003) | Schools (20) | member `entity` | sim | Schools R3 ("queues a `join_school` request") |
| `order_member` (4101) | Member state machine (41) | member `entity`, job `int(enum)`, target `entity` or uid | host | §6.4 direct orders: hunt at a ground, return, rest, heal, shop |
| `clear_order` (4102) | Member state machine (41) | member `entity` | host | §6.4: hand control back to the AI |
| `learn_skill` | Skills (21) | member `entity`, skill `content(skills)` | host | §6.4 "học skill" |
| `equip_item` / `unequip_item` | Member model (8) | member `entity`, item `entity`, slot `int(enum)` | host | §6.4 "mua đồ" follow-through |
| `buy_item` / `sell_item` | Gold economy (27) | item `content(items)` or item `entity`, qty `int(1, 999)` | host | §6.6 |
| `build_building` / `upgrade_building` | Guild and buildings (30) | building `content(buildings)` | host | §7, §19.4 |
| `accept_candidate` (1501) / `reject_candidate` (1502) | Recruitment (15) | candidate `entity` | host | §6.7 |
| `use_summon_token` | Golden Boss (14) | none | host | §6.5 Triệu Tập Lệnh |
| `enhance_item` (2401) | Equipment enhancement (24, Vertical Slice) | item `entity` | host | §19.3 |
| `offer_contract` (1602), `dismiss_member` (1603) | Retention (16, Vertical Slice) | member `entity`, terms `int` | host | §6.8 |

Each owner assigns its reason codes and states its applier cost. *(consistency-check 2026-11-16: IDs shown are the ones the owners' GDDs now allocate; later-wave owners — Party 1301–1311, Arena 1801, Tower 1901–1902, Rebirth 2301–2302, Quests 2501–2504, Crafting 2801, Market 2901–2906, Entitlement 3201, Ads 3301, IAP 3401–3402, Onboarding 4401–4402, Jianghu 1701+ — register in their own blocks, recorded in the registry; owner codes must be plain integers ≥ 100, never a code 6–9 reused with another meaning.)*

### States and Transitions

| State | Meaning | Accepts `register_command`? | `dispatch` in P1 | Host `submit` |
|---|---|---|---|---|
| `Registering` | Boot; registry open | Yes | `ctx.fail(5002)` | Refused (`core_refused`, the core is not sealed) |
| `Sealed` | Registry frozen, hash computed | No (error return, no change) | Runs (R3) | Allowed |
| `Disposed` | Host called `dispose()` | No | Not registered with a live core | Refused (`core_refused`) |

| From | To | Trigger |
|---|---|---|
| `Registering` | `Sealed` | `seal()` with every R2 check passing |
| `Registering` | `Registering` | `seal()` with a boot error: stays, error names the owner and `type_id` |
| `Sealed` | `Disposed` | `dispose()` |
| `Registering` | `Disposed` | `dispose()` |

There is no `Failed` state, as for the Event bus: a dispatch fault fails the core (Sim core R10), and the layer is discarded with it. While the core is `Failed`, host `submit` returns `[0, core_refused]`.

Per command, the lifecycle is: **submitted** (host: `seq > 0`, `host_pending + 1`) → **queued** (in the core's queue) → **drained** (P1 takes it; host: `host_pending − 1`) → **applied** or **refused** (R3) → **reported** (R7). A host command refused at submit never gets a `seq` and never enters the log.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Sim core (1) | both | `ctx.commands()` in P1; `submit` / `ctx.submit` return values; core state for the facade | One P1 handler (order 100); envelopes via `submit` and `ctx.submit`; fail codes 5001 – 5003 | Core owns the queue, `seq`, the drain cap and the log; this layer owns the vocabulary, the envelope and dispatch (Sim core R6) |
| Event bus (42) | layer → bus | None | Types 501, 502 registered at boot; outcome events in P1 | Bus owns delivery; this layer owns its block 500 – 599 |
| Data layer (3) | data → layer | Content tables, to check `content(table)` uids | None | Data layer owns `uid`s |
| Feature owners (8, 14, 15, 16, 20, 21, 24, 27, 30, 41, …) | both | `register_command` at boot; applier return codes | Applier calls in `seq` order with the envelope and the tick context | Each owner owns its commands' rules, reason codes and cost; this layer owns the contract (R5) |
| Utility AI (12) | none | None | None. AI decisions do not use commands (R10) | Utility AI |
| Guild screens (39), Realtime world view (38), Onboarding (44) | UI → layer | `submit`, `submit_batch` | `[seq, reason]`; outcome events through the facade's event stream | This layer owns the facade; the UI owns presentation |
| Localization (4) | layer → i18n | None | Reason-code key names (R6) | Localization owns the text |
| Leaderboards and anti-cheat (35) | both | Command log with `origin` | `submit_replay`; the R9 replay rule | Leaderboards owns the driver and divergence policy |
| Dev tooling and parity harness (43) | layer → tools | None | `command_table_hash` (F4); the dev-command set (R13) | Dev tooling |
| Local save (6) | none | None | Nothing is saved (R15) | — |

*Lens notes (applied in this run, no agents spawned).* **systems-designer:** the conflict rule must be one rule (R3: `seq` order on shared state), and every refusal must be stateless, or replay and the UI disagree; the origin gap in replay (R9) is the main hazard. **gameplay-programmer:** commands must not carry Objects or strings; a per-command GDScript cost of 20 – 100 µs (Sim core's estimate) makes the drain cap the P1 budget knob (F3). **engine-programmer:** no engine surface; the layer is a `RefCounted` service like the core and the bus, with no autoload, signal or node. No disagreement between the lenses needed a decision beyond those logged.

## Formulas

*(systems-designer lens applied: boundaries worked at 0 and the caps below. Every value here is integer arithmetic; nothing is a float.)*

### F1 — Host cap (`host_accepts`)

The host_accepts formula is defined as:

`host_accepts(k) = (host_pending + k ≤ host_pending_max)` and `sim_reserve = command_queue_max − host_pending_max`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| host_pending | int | 0 – host_pending_max | calculated | Host commands queued and not yet drained (R15) |
| k | int | 1 – host_pending_max | calculated | Commands in this `submit` (1) or `submit_batch` (the list length) |
| host_pending_max | int | 25 – command_queue_max ÷ 2 | data file (`config.csv`, new key) | Most host commands that may wait at once. Default 200 |
| command_queue_max | int | 100 – 10,000 | data file (Sim core knob) | The core's whole queue (default 1,000) |
| sim_reserve | int | ≥ command_queue_max ÷ 2 | calculated | Queue room host traffic can never take from sim-origin requests |

**Output Range:** a boolean. With the defaults, at most 200 host commands wait and at least 800 slots are reserved for sim requests, so a tap-flood can never make the core refuse a `join_school`. At `k = 0` the formula is not evaluated (an empty batch is a no-op returning `[]`). A `k` above `host_pending_max` can never fit and is refused at once. The validator bound `host_pending_max ≤ command_queue_max ÷ 2` keeps `sim_reserve` at least half the queue; `host_pending_max ≥ 25` (the default drain cap) means a host batch of at least one full drain always fits an empty cap. A roster-wide batch larger than `host_pending_max` cannot be sent in one batch (Edge Cases).
**Example:** `host_pending = 190`, a batch of 12 → `202 > 200`, refused whole with `host_queue_full`. A batch of 10 → `200 ≤ 200`, accepted.

### F2 — Apply latency (`wait_ticks`)

The wait_ticks formula is defined as:

`wait_ticks(p) = ceil(p / command_drain_max)` and `wait_ms(p) = wait_ticks(p) × tick_us / 1000`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| p | int | 1 – command_queue_max | calculated | The command's 1-based position in the queue, in `seq` order, when the next tick starts |
| command_drain_max | int | 10 – 1,000 | data file (Sim core knob) | Commands P1 takes per tick (default 25) |
| tick_us | int | 50,000 – 1,000,000 | calculated (Sim core F1) | 100,000 at 10 Hz |
| wait_ticks | int | ≥ 1 | calculated | Ticks that run until this command is applied, counting the applying tick |
| wait_ms | int | ≥ 100 at 10 Hz | calculated | Game-time latency, equal to wall time when the sim is not catching up |

**Output Range:** 1 tick (100 ms) for any order when fewer than 26 commands are queued, which is normal play. A host command waits at most `ceil((host_pending_max + s) / command_drain_max)` ticks, where `s` is the sim requests ahead of it: 8 ticks (800 ms) for a full host cap with `s = 0`. While catching up or with a hand-off pending, the wait is the same number of ticks, but those ticks arrive later in wall time (Sim core R17). `p = 0` cannot occur.
**Example:** a "send all" batch of 60 members into an empty queue: members 1 – 25 apply in the first tick, 26 – 50 in the second and 51 – 60 in the third, so the last one moves 300 ms after the tap.

### F3 — P1 dispatch cost (`c_P1`)

The c_P1 formula is defined as:

`c_P1 = c_disp + Σ(i = 1..n) (c_env + c_apply[type_i]) + n_host × c_emit` with `n ≤ command_drain_max`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n | int | 0 – command_drain_max | calculated | Commands drained this tick |
| n_host | int | 0 – n | calculated | Of those, host-origin (one outcome event each, R7) |
| c_disp | float (µs) | > 0 | measured (P1 spike) | Fixed cost of the dispatcher with an empty drain |
| c_env | float (µs) | > 0 | measured (P1 spike) | One R4 envelope check |
| c_apply[t] | float (µs) | > 0 | measured, stated by each owner GDD | One applier call of type `t` |
| c_emit | float (µs) | > 0 | measured (Event bus F1 `c_emit`) | One `ctx.emit` |
| P1 share | float | 0.10 (provisional) | constant (Sim core F6) | P1's share of the per-tick budget |

**Output Range:** in normal play `n = 0` and `c_P1 = c_disp`. A burst tick has `n = command_drain_max`. The provisional target is `c_P1 ≤ 0.10 × c_tick` at the p95 tick of 6.9 ms (Sim core F6), about 690 µs, which at `n = 25` leaves about 27 µs per command for `c_env + c_apply + c_emit`. **The Sim core's own estimate is 20 – 100 µs per command in GDScript, which can exceed that by up to 4×** (2.5 ms at 25 × 100 µs). A burst tick then takes P1 over its share but stays inside the single-tick frame bound (8.33 ms) unless the rest of the tick is already near it. The P1 spike measures it and either lowers `command_drain_max` or accepts P1 bursts above share (OQ-3). GDScript per-call costs are **NOT SOURCEABLE** from `docs/engine-reference/godot/`, so no `c_*` here is a fact.
**Example (illustrative, unmeasured):** `c_disp = 5 µs`, `c_env = 3 µs`, average `c_apply = 30 µs`, `c_emit = 2 µs`, a 25-command host batch: `5 + 25 × 33 + 25 × 2 = 880 µs`, 28% over the 690 µs share and 11% of the 8.33 ms frame bound.

### F4 — `command_table_hash`

The command_table_hash formula is defined as:

`command_table_hash = SHA-256( frame(r_1) ‖ frame(r_2) ‖ … ‖ frame(r_m) )`, records sorted by ascending `type_id`

`frame(r) = u16 type_id ‖ str(owner_id) ‖ str(name) ‖ u8 arg_count ‖ arg(1) … arg(arg_count) ‖ u8 origins ‖ u8 dev_only ‖ u16 reason_count ‖ u16 code(1) … code(reason_count)`

with `str(s) = u8 len ‖ ASCII bytes`; `arg = u8 kind` (0 `int`, 1 `content`, 2 `entity`), followed by `i64 min ‖ i64 max` for `int` and `str(table)` for `content`; `origins` a bitmask (1 host, 2 sim); reason codes ascending. All integers big-endian.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| m | int | 0 – 65,535 | calculated | Registered command types |
| r_i | record | — | calculated | One R2 registration |
| command_table_hash | 32 bytes | — | calculated | Hex string recorded by the parity harness beside `phase_table_hash` and `type_table_hash` |

**Output Range:** 32 bytes. `m = 0` hashes the empty string (`e3b0c442…b855`), which the MVP never ships. The applier is not hashed, as Callables differ per implementation; a behaviour change in an applier is caught by golden vectors, not by this hash.
**Example:** one type `(type_id 100, owner "test", name "noop", no args, origins host, dev_only 0, no reason codes)` frames as the 17 bytes `00640474657374046e6f6f700001000000`, whose SHA-256 is `eaad224889afdf83777b17495ce9fa73aa13a55a6fa8eef83b6ce65d9c7aa279`.

## Edge Cases

*(systems-designer lens applied to R1 – R16 and F1 – F4.)*

**Ordering and conflicts**
- **If two host orders for one member arrive in the same tick** (tap "heal", then "hunt"): both apply in ascending `seq`. The second sees the first's result and its owner judges it on that state, so "hunt" overrides "heal" if the owner allows a new order to replace one in progress, or is refused with `not_allowed_now` if not. The rule is the owner's; the order is this layer's.
- **If a command targets a member removed earlier in the same P1** (dismissed by command `seq` 5, then ordered by `seq` 6): the owner refuses `seq` 6 with `target_missing`. No error.
- **If a sim request and a host order for one member are applied in the same P1** (Schools' `join_school` and the player's `change_school`): ascending `seq` decides, as for any two commands. The request was submitted during the previous tick, so it usually has the lower `seq`.
- **If an applier submits a follow-up request** (R8): it applies in P1 of the next tick at the earliest (Sim core R6). An applier can never make a second command apply in the same P1.

**Queue and caps**
- **If the host cap is full** (F1): `submit` returns `[0, host_queue_full]` at once, consumes no `seq`, writes nothing to the log and emits no event. The UI says so (UI Requirements).
- **If a batch is larger than the remaining host cap**: the whole batch is refused (R12); nothing in it is queued.
- **If a batch is larger than `host_pending_max` itself** (a very large roster): it can never fit. The UI splits it into batches of at most `host_pending_max` and submits the next one after the previous one's outcomes arrive. Each part is all or nothing.
- **If the core's queue is full because of sim requests** (a runaway feature): host `submit` returns `[0, core_refused]` and the core emits `commands_dropped` (Sim core Edge Cases). That is a feature bug: every owner states its peak requests per tick (Dependencies), and the sum must stay below `sim_reserve`.
- **If the drain cap leaves commands queued** (F2): they apply in later ticks in `seq` order, and their outcome events come in those ticks. Nothing is dropped.

**Lifecycle**
- **If the player orders while paused, catching up or with a hand-off pending**: the order is queued with a normal `seq`, acknowledged at once (R11), and applies in the next tick that runs. During a pending hand-off that is after the skip (Sim core R8), so the order is judged against the post-absence state and may now be refused (the member died while away). That is correct: the order applies when the guild can act on it.
- **If the game is saved and quit with host orders queued**: the queue is not saved (Sim core R14), so those orders are lost. The UI showed them as pending, never as done. At most `host_pending` orders from the last moments before the save are lost, which is accepted; the next autosave cadence is Local save's (6).
- **If a command is submitted while the core is `Failed`**: `[0, core_refused]`. Pending orders never resolve; the fatal screen replaces the UI (Sim core R10).
- **If the failing tick contained commands**: the core discards that tick's command-log entries and events (Sim core R10), so their outcome events never arrive. The instance is discarded anyway.

**Envelope and applier faults**
- **If an applier returns an invalid value** (a non-int, negative, or an unregistered code): `ctx.fail(5001)`, naming the owner, `type_id` and value. It is never treated as a refusal, because a silent mis-coded refusal would hide a bug and might have left state half-written.
- **If an applier writes state and then returns a refusal code**: the layer cannot detect this at runtime. It breaks R5, and owner ACs plus parity vectors catch it (each owner's refusal ACs assert unchanged state, as Schools AC-8 does).
- **If an applier's object has been freed**: `ctx.fail(5003)` before the call.
- **If a content `uid` is valid but its row is not live in this wave**: the layer accepts the envelope (R4 checks existence only) and the owner refuses with `not_live`.
- **If an `entity` ID is negative**: `bad_arg` (3) at the envelope check. A non-negative ID that does not exist is the owner's `target_missing`.

**Replay and versions**
- **If a log contains a `type_id` that is no longer registered** (a retired command): the replayed command is refused with `unknown_type`. The replay diverges from the original only if the original accepted it, so a retired type is a `sim_version` bump, and Leaderboards replays a log with the core build of its `sim_version`.
- **If a log is replayed on a build with a different `command_table_hash`**: the parity harness flags it. Leaderboards selects the core by `sim_version`, so a changed table without a version bump is a release bug Dev tooling's gate catches.
- **If a handler hand-builds an `origin = host` envelope through `ctx.submit`** (bypassing R8): replay would apply it twice. Not detectable at runtime (OQ-4).
- **If a dev command was applied in a dev build and that save is opened in a release build**: the effect stays in state. Whether such a save can rank is Leaderboards' rule (OQ-5).

**Degenerate strategies**
- **Order spam to "re-roll" an outcome**: not possible. A refusal takes no cost and changes nothing, and RNG generators are derived per event (RNG R3), so re-submitting an order never draws different dice for the same event.
- **Tap-flooding to slow the sim**: bounded by `host_pending_max` and `command_drain_max`; the extra cost is at most one burst P1 per tick (F3).

## Dependencies

### Upstream (this system depends on)

| System | Hard/Soft | Interface | Why |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | `submit`, `ctx.submit`, `ctx.commands()` in P1, `seq`, `command_drain_max`, `command_queue_max`, the command log, `register(P1, …)`, `ctx.fail`; a next-`seq` query (OQ-2) | The queue, the drain point and `seq` order are the core's (R6); this layer is the one P1 reader |
| Event bus and history log (42) | Hard | `register_type` for 501 and 502; delivery in P6 | Outcome events reach the UI |
| Data layer and content pipeline (3) | Hard | Content tables and row `uid`s | `content(table)` argument checks (R4) |

### Downstream (systems that depend on this one)

| System | Hard/Soft | Interface | What it needs |
|---|---|---|---|
| Schools and school change (20) | Hard | `register_command` for `set_aspiring_school`, `change_school`, `join_school`; the R5 contract; `commands.request` | Its P1 appliers run through the dispatcher (Schools R3, R4) |
| Member state machine (41) | Hard | `order_member`, `clear_order` | Player overrides of the AI (R10) — PROVISIONAL |
| Member model (8), Skills (21), Golden Boss (14), Recruitment (15), Gold economy (27), Guild and buildings (30) | Hard | One or more registered commands each | Their player actions — PROVISIONAL |
| Retention (16), Equipment enhancement (24), Market (29), Crafting (28) | Hard | Registered commands | Vertical Slice player actions — PROVISIONAL |
| Guild screens (39), Realtime world view (38), Onboarding (44) | Hard | `submit`, `submit_batch`, `[seq, reason]`, outcome events | Every player action and its acknowledgement |
| Leaderboards and anti-cheat (35) | Hard | `origin` in the log, `submit_replay`, the R9 rule | Exact server replay — PROVISIONAL |
| Dev tooling and parity harness (43) | Soft | `command_table_hash`, dev commands, `submit_replay` | Parity and golden vectors replay command scripts |
| Localization (4) | Soft | Reason-code key names | Refusal text |
| Utility AI (12) | None | — | Explicitly does not use commands (R10) |

**Every owner that registers a command must state, in its own GDD:** the command's ID in its block, its `arg_kinds`, its reason codes, its applier cost (F3), and, for sim-origin requests, its peak requests per tick at the max-roster fixture (Edge Cases: the sum stays below `sim_reserve`).

**Bidirectionality.** Sim core already lists this layer (Interactions, Dependencies). Schools names the commands and "P1 appliers" but lists only the Sim core as their interface; it should add this layer (OQ-1). The Event bus does not list this layer as an emitter; that is generic (feature → bus) and needs no change.

## Tuning Knobs

| Knob | Source | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `host_pending_max` (F1) | `config.csv` (new key) | 200 | 25 – `command_queue_max ÷ 2` | Host traffic can crowd sim requests; a flood costs more burst ticks | Large "send all" batches must be split; impatient tapping hits `host_queue_full` | `command_queue_max` (upper bound), `command_drain_max` (F2 worst wait) |
| `cmd_args_max` (R1) | constant | 6 | — | — | — | Fixed by the envelope format; a change is a `sim_version` bump |

Owned elsewhere and **not duplicated** here: `command_queue_max` and `command_drain_max` (Sim core Tuning Knobs). `command_drain_max` is the real P1 cost knob (F3); `host_pending_max` only bounds the host's share of the queue. Raising `command_queue_max` without `host_pending_max` grows `sim_reserve` only. The validator (Data layer 3) must add: `host_pending_max` an integer within 25 – `command_queue_max ÷ 2` (OQ-6).

## Visual/Audio Requirements

Optional for a `Core` system, and this one has no visuals or sounds of its own (the art-director step is not required for this category; no art bible exists yet). What it requires of presentation:
- Every host order has a visible **pending** state the frame it is submitted, and a visible resolution when its outcome event arrives (Guild screens 39, Realtime world view 38).
- A refusal has a distinct cue from an acceptance, and the two are not told apart by colour alone (an icon or text as well). A refusal sound, if any, is Audio's (40) and must be quieter than any combat or Golden Boss warning cue.
- While catching up or with a hand-off pending, pending markers stay up without per-order animation (Sim core R17).

## Game Feel

- **Acknowledge in the same frame.** `submit` is synchronous, so the pending marker appears in the frame of the tap: 0 frames of delay.
- **Resolve within one tick** in normal play: ≤ 100 ms after the tap at 10 Hz, plus up to one render frame (F2). A large batch resolves in `ceil(n / command_drain_max)` ticks and the UI shows the batch as in progress until its last outcome.
- **Never silent.** Every tap ends in exactly one of: acknowledged then applied, acknowledged then refused with a reason, or refused at once with a reason. A tap that ends in none of these is a bug (AC-18).
- Feel targets for the order screens themselves (button response, haptics) are Guild screens' (39).

## UI Requirements

This layer has no screen. It requires these of the screens that send commands (Guild screens 39, Realtime world view 38, Onboarding 44):
1. Track pending orders by `seq` and clear each on its `command_applied` / `command_refused` (R11).
2. Show every reason code in words through `i18n/` (R6). Codes 1 – 5 are bugs or tampering in a release build; show a generic "order could not be given" text, not the code name.
3. `host_queue_full`: tell the player to wait a moment; do not retry automatically.
4. Disable or hide actions the player plainly cannot take (locked content, Premium), but still handle the applier's refusal (R14).
5. While catching up, show pending orders as waiting on the guild, not as failed.
6. Split a roster-wide batch larger than `host_pending_max` (Edge Cases).

> **📌 UX Flag — Command layer**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` for the order-acknowledgement pattern (pending, applied, refused) in `design/ux/interaction-patterns.md` before writing epics for Guild screens (39) and Realtime world view (38).

## Cross-References

| This GDD | Other GDD | Its rule or value | Nature |
|---|---|---|---|
| R1, R3, R8, R9, F2 | `sim-core-and-tick-loop.md` | R6 (queue, `seq`, drain cap, command log, "vocabulary and validation owned by the Command layer") | Rule dependency; this GDD fills the vocabulary half |
| R3, R5 | `sim-core-and-tick-loop.md` | R5 handler prohibitions, R10 failure, Edge Cases "two commands conflict" | Rule dependency |
| F1, F2, F3, Tuning Knobs | `sim-core-and-tick-loop.md` | `command_queue_max` 1,000, `command_drain_max` 25, P1 share 10% (F6) | Value dependency (registry) |
| R15 | `sim-core-and-tick-loop.md` | R14 (queue not saved), R12 (`sim_version`) | Rule dependency |
| R2, R7 | `event-bus-and-history-log.md` | R3 (type blocks, owner × 100), R2 (five-integer events), R10 (seal order) | Rule dependency; block 500 – 599 claimed |
| R4, R1 | `data-layer-and-content-pipeline.md` | Row `uid`s, content tables | Data dependency |
| R5 | `deterministic-rng.md` | R3 (per-event derived generators) | Why a refusal that draws is stateless |
| Vocabulary, R8 | `schools-and-school-change.md` | R3 `set_aspiring_school`, `join_school` request; R4 `change_school`, reason names; AC-8 unchanged state on refusal | Rule dependency; Schools' appliers run through R3 |
| F4 | `dev-tooling-and-parity-harness.md` | R7 (`sim_version` bump rule), golden vectors | Hash recorded beside `phase_table_hash` |

## Acceptance Criteria

*(qa-lead lens applied: one or more criteria per rule and formula, boundaries at 0 and caps, and cross-system checks. "Logic" criteria are automated unit tests in `tests/unit/command_layer/`; "Integration" criteria run with a real Sim core and Event bus; "UI" needs a retained screenshot.)* Test fixtures register stub command types in a test block (for example `type_id 100 – 199`, owner `test`) with stub appliers that record calls.

**Envelope and registration (R1, R2, R16)**
- **AC-1 [Logic] (R1)**: **GIVEN** a host `submit` with a String, a float or a Dictionary in `args`, **THEN** it returns `[0, bad_arg]` (or is impossible to build, because `args` is a `PackedInt64Array`) and nothing is queued. **GIVEN** an envelope with 6 int args for a 6-arg type, **THEN** it is queued; with 7, `[0, bad_arity]`.
- **AC-2 [Logic] (R2)**: **GIVEN** two `register_command` calls with the same `type_id`, **WHEN** `seal()` runs, **THEN** it is refused with an error naming both owners and the layer stays `Registering`. The same holds for an `owner_id` with an uppercase letter, an empty `origins`, 7 `arg_kinds`, a reason code of 99 or 1,000, and an applier whose argument count is not 2.
- **AC-3 [Logic] (R16, States)**: **GIVEN** a layer in `Registering`, **WHEN** its P1 handler runs, **THEN** the tick fails with code 5002 and `fail_owner_id = "command_layer"`. **GIVEN** a `Sealed` layer, **THEN** `register_command` returns an error and the registry is unchanged.
- **AC-4 [Logic] (F4)**: **GIVEN** only the type `(100, "test", "noop", no args, origins host, dev_only 0, no reasons)`, **THEN** `command_table_hash` is `eaad224889afdf83777b17495ce9fa73aa13a55a6fa8eef83b6ce65d9c7aa279`, identical in Python and GDScript. **GIVEN** the same types registered in a different call order, **THEN** the hash is the same. **GIVEN** one changed `int` range, **THEN** the hash differs.

**Dispatch and outcomes (R3 – R7)**
- **AC-5 [Logic] (R3)**: **GIVEN** stub commands A (owner X), B (owner Y), C (owner X) submitted in that order, **WHEN** one tick runs, **THEN** the appliers are called A, B, C in `seq` order, each exactly once, and only `command_layer` reads `ctx.commands()` (a second P1 handler at order 200 that asserts it is never handed commands passes).
- **AC-6 [Logic] (R3, Edge Cases)**: **GIVEN** a stub `dismiss(member 7)` at `seq` 5 and `order(member 7)` at `seq` 6 in one tick, **THEN** `seq` 6 is refused with `target_missing` (6) and no fail occurs.
- **AC-7 [Logic] (R4)**: **GIVEN** one envelope per check (unknown type; wrong arity; sim-only type from the host; a `dev_only` type with the build flag set to release; an `int(1, 999)` arg of 0 and of 1,000; a `content(schools)` uid that is not in the table; an `entity` of −1), **THEN** each is refused with codes 1, 2, 4, 5, 3, 3, 3, 3 respectively, the applier is never called, and an envelope failing two checks reports the first in R4 order. **GIVEN** `int(1, 999)` args of 1 and 999, **THEN** the applier is called.
- **AC-8 [Logic] (R5, R3)**: **GIVEN** a stub applier that returns −1, then (separately) 1,234 unregistered, then 3 (envelope-only), then the String `"ok"`, **THEN** each fails the tick with 5001 naming the owner and `type_id`. **GIVEN** it returns 0, 7 or a registered 100, **THEN** no fail occurs.
- **AC-9 [Integration] (R5)**: **GIVEN** each MVP owner's refusal fixtures, **WHEN** the refused commands apply, **THEN** a full-state digest of every system is identical before and after the P1. (Each owner GDD supplies the fixtures; Schools AC-8 is the first.)
- **AC-10 [Integration] (R7)**: **GIVEN** a host command accepted in tick N and another refused with reason 8, **THEN** P6 of tick N delivers `[N, 501, seq₁, type₁, 0, 0]` and `[N, 502, seq₂, type₂, 8, 0]` to a subscriber of 501 and 502, and `read_history` over tick N contains neither. **GIVEN** a sim-origin command accepted, **THEN** no 501 is emitted and `sim_applied_count` rises by 1.

**Origin, replay and AI (R8 – R10)**
- **AC-11 [Logic] (R8)**: **GIVEN** a host `submit` and a handler `commands.request(ctx, …)`, **THEN** their logged envelopes carry `origin` 0 and 1 respectively. A host `submit` of a sim-only type returns `[0, …]` or is refused in P1 with `origin_not_allowed`, never applied.
- **AC-12 [Integration] (R9, F2)**: **GIVEN** `command_drain_max = 10`, a host batch of 30 submitted before tick 0, and a stub feature that `request`s one sim command during each of ticks 0 – 4, **WHEN** 10 ticks run and the log is replayed on a fresh core by the R9 rule (host entries only, submitted by `seq`), **THEN** every replayed `seq`, every apply tick and a final full-state digest equal the original, and the replay's log equals the original's. **GIVEN** the same log replayed by apply stamp instead, **THEN** at least one `seq` differs (this demonstrates the rule matters; the test asserts the divergence).
- **AC-13 [Integration] (R9)**: **GIVEN** a log replayed with sim-origin entries also re-submitted, **THEN** the replay applies each sim request twice and its digest differs (a negative test proving R9's filter is required).
- **AC-14 [Integration] [PENDING: Utility AI 12, Member state machine 41] (R10)**: **GIVEN** a 1-hour `run_ticks` with no player input, **THEN** the command log contains no host entries and the count of sim entries is only the owners' declared requests (no entry per AI decision).

**Host facade and acknowledgement (R11, R12, F1)**
- **AC-15 [Logic] (F1)**: **GIVEN** `host_pending_max = 200` and 190 pending, **WHEN** a batch of 12 is submitted, **THEN** all 12 return `[0, host_queue_full]`, `host_pending` stays 190 and no `seq` is consumed. **WHEN** a batch of 10 is submitted, **THEN** all 10 get consecutive `seq`s and `host_pending = 200`. **WHEN** one tick drains 25, **THEN** `host_pending = 175`. **GIVEN** `host_pending = 0` and an empty batch, **THEN** `submit_batch` returns `[]` and changes nothing.
- **AC-16 [Logic] (F1, Edge Cases)**: **GIVEN** `host_pending_max = 200`, `command_queue_max = 1,000` and a stub feature that requests 800 sim commands in one tick, **THEN** none of them is refused by the core while the host cap is full. **GIVEN** a validator run with `host_pending_max = 501` and `command_queue_max = 1,000`, or 24, **THEN** each is rejected; 25 and 500 are accepted.
- **AC-17 [Logic] (F2)**: **GIVEN** `command_drain_max = 25` and an empty queue, **WHEN** a 60-command batch is submitted before tick N, **THEN** commands 1 – 25 apply in tick N, 26 – 50 in N + 1 and 51 – 60 in N + 2. **GIVEN** a single command, **THEN** it applies in tick N.
- **AC-18 [Integration] (R11, Game Feel)**: **GIVEN** a running guild, **WHEN** a script submits 1,000 random host commands across 10,000 ticks, including while paused and across one hand-off, **THEN** every command whose `submit` returned `seq > 0` gets exactly one 501 or 502 with that `seq`, and every one that returned 0 got a non-zero reason at once. No `seq` is resolved twice or never.
- **AC-19 [Logic] (Edge Cases)**: **GIVEN** host commands queued and a `snapshot_core()` then a load, **THEN** `host_pending = 0` after the load and none of the queued commands applies.

**Dev, gating and cost (R13, R14, F3)**
- **AC-20 [Logic] (R13)**: **GIVEN** a `dev_only` type, **THEN** it is in `command_table_hash` in both build flags, applies with the dev flag, and is refused with `dev_disabled` with the release flag.
- **AC-21 [Integration] [PENDING: Schools 20 port] (R14, cross-system)**: **GIVEN** `live_wave = 1`, **WHEN** the player submits `change_school(member, thuy_2's uid)`, **THEN** the envelope passes R4 (the uid exists), the Schools applier refuses with `not_live`, the player sees the localised `not_live` text, and nothing changes.
- **AC-22 [Integration] [PENDING: P1 spike] (F3)**: **GIVEN** the min-spec device, a release export and the max-roster fixture, **WHEN** a 25-command host batch of the most expensive MVP command applies in one P1, **THEN** the measured P1 cost is recorded, and either it is ≤ 10% of the p95 tick budget or `command_drain_max` is lowered until the tick stays within the single-tick frame bound (8.33 ms at 60 fps).

**UI (UI Requirements)**
- **AC-23 [UI] [PENDING: Guild screens 39, Localization 4]**: **GIVEN** a tap on "go heal" for three members, one in `boss_raid`, **THEN** a retained screenshot in `production/qa/evidence/` shows three pending markers in the tap frame, and a second shows two applied and one refused with the localised `not_allowed_now` text, in each locale, with the refusal marked by icon or text and not by colour alone.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **PROVISIONAL: Schools (20)** — its "P1 applier" for `set_aspiring_school`, `change_school` and `join_school` registers with this layer (R2, R3), not as its own P1 handler reading `ctx.commands()`; the proposed IDs 2001 – 2003 and numeric reason codes 100+ for its named reasons (`already_affiliated`, `change_in_progress`, `same_school`; `not_live` and `cannot_afford` map to shared 9 and 8) need confirming. Its event 2004 `school_change_refused` duplicates this layer's 502 for host orders; consistency pass to decide whether Schools keeps it (it may still be useful for the sim-origin `join_school` refusal). **RESOLVED (consistency-check 2026-11-16):** Schools R8 now registers its three appliers here with IDs 2001–2003 and reason codes 101–107 (shared 7, 8, 9 where they fit), and emits 2004 only for sim-origin refusals; host refusals are reported by 502 alone | Schools (20), consistency-check | Closed |
| OQ-2 | **RESOLVED (consistency-check 2026-11-16):** Sim core R6 now logs the full envelope with `origin`, exposes `next_command_seq()`, and states replay by `seq` for host entries only (origin is still set by the submit path, R8; OQ-4's forgery lint stands). Original: **Sim core (1)** — R9 needs a read-only query of the next `seq` (`next_command_seq`), and the replay rule changes Sim core R6's "submits the commands stamped for the next tick" to "submits host entries by `seq`". Sim core should also state that the command log stores `origin` (part of the envelope). If the core prefers, it could stamp `origin` itself from the submit path (host `submit` vs `ctx.submit`), which would close OQ-4 | Sim core (1) | Next Sim core revision |
| OQ-3 | **Per-command cost.** F3 shows the Sim core's 20 – 100 µs estimate can put a 25-command burst P1 over its 10% share. The P1 spike measures it (AC-22) and sets `command_drain_max` or accepts burst P1s. NOT SOURCEABLE until measured | Sim core (1), P1 spike | P1 spike |
| OQ-4 | **Origin forgery.** A handler can hand-build an `origin = host` envelope and call `ctx.submit` directly. Nothing in GDScript prevents it. Either the core stamps origin by path (OQ-2) or a lint rule in Dev tooling (43) forbids building envelopes outside this layer | Dev tooling (43) / Sim core (1) | Before the first feature port |
| OQ-5 | **PROVISIONAL: Leaderboards (35)** — the replay driver follows R9 (host entries only, by `seq`, through `submit_replay`), treats a `seq` mismatch as divergence, and decides whether a log with an applied `dev_only` command can rank (assumed: never) | Leaderboards (35) | Leaderboards GDD |
| OQ-6 | **PROVISIONAL: Data layer (3)** — `config.csv` needs `host_pending_max` (default 200) and the validator rule `25 ≤ host_pending_max ≤ command_queue_max ÷ 2`. Adding a config key is a data change not made here | Data layer (3) | With Sim core OQ-4's keys |
| OQ-7 | **PROVISIONAL: Utility AI (12) and Member state machine (41)** — AI decisions are applied in P2 without commands; a player order is a host `order_member` command that sets an override the AI respects until it completes or `clear_order` (R10). The job enum and override lifetime are 41's | Member state machine (41), Utility AI (12) | Their GDDs |
| OQ-8 | **PROVISIONAL: every other vocabulary row** (Member model 8, Skills 21, Gold economy 27, Guild and buildings 30, Recruitment 15, Golden Boss 14, Retention 16, Enhancement 24) — command names and args are assumed from the GDD sections cited; each owner allocates IDs in its block, reason codes and states its applier cost and peak sim requests per tick | Each owner | Each owner's GDD |
| OQ-9 | **PROVISIONAL: Guild screens (39)** — implements the UI Requirements list, including batch splitting above `host_pending_max` | Guild screens (39) | Its GDD and `/ux-design` |
| OQ-10 | **Should a pending order survive a save?** Today the queue is not saved (Sim core R14), so orders queued at the moment of quitting are lost. If playtests show players notice, the core or Local save (6) would need to save the queue, which is a schema change and is not decided here | Local save (6), Sim core (1) | After the vertical slice playtest |
