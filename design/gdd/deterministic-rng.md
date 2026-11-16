# Deterministic RNG

> **Status**: Designed (pending re-review) — revised on 2026-11-16 after `/design-review`: first review NEEDS REVISION with 10 blockers, re-review NEEDS REVISION with 9 blockers, both applied; revision round of 2026-11-16 closed the stale dependency rows (see `design/gdd/reviews/deterministic-rng-review-log.md`)
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars (`design/gdd/game-pillars.md` and `game-concept.md` absent). Player Fantasy alignment was checked and the rules deliver it (R3, R10). Re-run once pillars exist.
> **Author**: user + Claude
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None defined yet (no game-pillars.md). Serves the locked GDD principle "deterministic simulation: same seed, same result" (JX1_Tycoon_GDD.md §3.2, §21 Prompt 0 rule 2).

## Summary

Deterministic RNG is the game's only source of randomness. Every random event — a fight, a drop roll, a recruit, an enhancement attempt — gets its own PCG32 generator, seeded from the save's world seed, the consumer's domain ID and the event's key, so the same guild and commands produce the same outcomes on every machine, in the balance simulator and on the leaderboard verifier, offline progress applies the same rules and odds, and no draw in one system can shift another. For the player this means fair dice: the same rules and odds while away as while watching, no hidden rigging, and luck that comes only from visible modifiers such as traits.

> **Quick reference** — Layer: `Foundation` · Priority: `MVP` · Key deps: `None` (depended on by 19 systems; see Dependencies)

## Overview

Deterministic RNG is the single source of randomness for the whole simulation. It is a seeded PCG32 generator (XSH-RR variant, 64-bit state, 32-bit output) that, given the same seed, produces the same sequence of numbers on every machine and in every implementation of the game — the Python reference core in `sim/` today, the Godot port tomorrow, and the leaderboard verifier on the server. Every outcome that is not fixed by data — damage variance, which monster spawns, what drops, which candidate walks through the guild gate, whether an enhancement attempt succeeds — is drawn from it. The player never touches this system directly; they experience what it guarantees: a guild that behaves the same way when the simulation runs live, when it catches up after up to 12 hours offline (the offline cap, Offline progress R4), and when the same day is replayed to check a leaderboard score. Without it, the game's core technical promise (GDD §3.2: one headless simulation shared by realtime play, offline fast-forward, the balance simulator and server-side checks) cannot hold, because any engine-provided random function differs between platforms, versions and runs. The system's scope is the generator, the derived draws built on it (uniform float, bounded integer, choice, chance), how independent streams are created for different consumers, and how its state is saved and restored; it deliberately owns no game rules — callers decide what a draw means.

## Player Fantasy

**Type: indirect.** The player never sees this system; they feel what it guarantees. No game pillars exist yet, so this section anchors to the GDD's locked decisions instead of quoting a pillar.

**"The world is fair, even when you're away — and luck lives in your members, not in the machine."**

*The moment:* the bang chủ opens the game after a night away and reads the "while you were away" report (GDD §10). The party that hunted in Hàn Thuỷ Đầm came home with two rare drops, one member was injured, and the Golden Boss backlog was cleared once. None of it feels like a consolation summary invented to fill the gap: the same rules and the same odds applied while the player slept as when they watched, drawn from dice that never lean toward or against them. When one member keeps bringing home better loot than the others, the player can point at the reason — that member's "lucky" trait (GDD §5.2) — rather than suspecting the game of picking favourites.

This framing is honest about one limit: offline progress samples trips rather than replaying every hit (GDD §10, §18.1, about 1% XP drift), so the offline report is a fair outcome of the same rules, not a frame-identical replay of what live play would have shown. What is identical is the rulebook and the odds.

**What this asks of the rest of the design**
- Offline progress, off-screen zones and live play must draw from the same RNG rules and the same event keys (Section C), never from a separate shortcut generator.
- Every luck effect anywhere in the game — traits, PA-scaled drop rates, buffs — must be a visible, data-driven modifier applied to a fair draw. No hidden pity timers, streak breakers, rubber-banding or outcome rigging, in either direction, in any system. If a design later wants a pity mechanic, it must be an explicit, player-visible rule in that system's GDD, not a silent bias in the dice.
- Monetisation never touches the dice: no purchase, Premium entitlement or ad reward changes the probability of any random outcome (consistent with GDD §11.2, "do not sell power directly").

*Lens applied:* creative direction (`references/lens-creative-director.md`) — three framings were offered; the user chose a combination of "fair even when away" and "luck lives in members".

## Detailed Design

### Core Rules

**Decisions taken in this section (user, 2026-11-16):** randomness uses **per-event seeding**; bounded integers are **exactly uniform** (rejection sampling). Both change the current `sim/rng.py` behaviour; see Open Questions for the migration.

**R1 — One generator algorithm.** All simulation randomness comes from PCG32 XSH-RR (64-bit state, 64-bit increment, 32-bit output), exactly as specified in Formulas F1. Engine-provided random functions (Godot `randf()`, `randi()`, `RandomNumberGenerator`, Python `random`) are forbidden inside the simulation core and in any code whose result reaches the simulation. They may be used only for presentation that never feeds back (for example, idle sprite jitter).

**R2 — The world seed.** Each save has exactly one `world_seed`, an unsigned 64-bit integer chosen once when a new guild is created and stored in the save forever. It is the only entropy the simulation ever receives. A signed-64-bit port (GDScript) holds it in an `int` with the same 64-bit pattern, so values of 2⁶³ or more read as negative there; every consumer (Sim core, Local save) treats it as that bit pattern, never as a signed quantity. It is chosen from OS or platform entropy at new-game time; it is never derived from the wall clock alone. Tests, the balance simulator and leaderboard replay pass it explicitly.

- **A client-chosen seed is never trusted for ranking.** The verifier (35) replays a client's `world_seed` to check that the reported results follow from it. It must not treat a seed the client chose as evidence that the run was fair, because a player can scan seeds offline for a lucky start (seed shopping). How ranked guilds get an acceptable seed is owned by Leaderboards and anti-cheat (35), OQ-2.

**R3 — Per-event seeding.** There is no long-lived shared generator. Each *random event* creates a fresh, short-lived generator whose seed is derived from the world seed, a **domain ID** and an **event key** (Formulas F2). A random event is one logically complete outcome — one fight, one drop roll for one kill, one recruit candidate, one enhancement attempt, one raid, one sampled offline trip. Draws inside an event come from that event's generator in sequence; the generator is discarded when the event resolves.

**R4 — Domain IDs.** Every consumer of randomness has a fixed, unique domain ID from a single registry kept in this GDD (table below). The registry is append-only: an ID is never reused, renumbered or deleted, even if its system is removed. A new consumer gets the next unused ID. The domain ID is also the generator's stream selector (`seq`), so two domains given the same key still produce unrelated sequences.

| Domain ID | Domain | Owner (system #) | Example event |
|---|---|---|---|
| 1 | combat | Combat (10) | one fight between a party and one monster |
| 2 | loot | Items and loot (26) | the drop roll for one kill |
| 3 | spawn | Zones and hunt (11) | which monster appears for one encounter |
| 4 | hunt_trip | Zones and hunt (11) | per-trip choices not covered by 1–3 |
| 5 | offline_sample | Offline progress (31) | one sampled trip during fast-forward |
| 6 | raid | Golden Boss and guild raid (14) | one guild raid |
| 7 | golden_boss_pick | Golden Boss and guild raid (14) | which boss and element appears in one hourly slot |
| 8 | recruit | Recruitment (15) | one candidate: school, element, level, PA, traits |
| 9 | pa_estimate | CA/PA and traits (9) | the fixed noise on one member's displayed PA range (GDD §5.1) |
| 10 | enhance | Equipment enhancement (24) | one enhancement attempt |
| 11 | ai_tiebreak | Utility AI (12) | breaking an exact score tie for one decision |
| 12 | retention | Retention (16) | one negotiation or leave check |
| 13 | crafting | Crafting (28) | one craft that has a random outcome |
| 14 | npc_guild | Jianghu and NPC guilds (17) | one NPC guild growth step or offer |
| 15 | tower | Endless Tower (19) | one tower floor |
| 16 | arena | Arena (18) | one arena bout |
| 17 | quest_roll | Quests (25) | one daily or weekly quest selection |
| 18 | trait_reveal | CA/PA and traits (9) | one trait-reveal check |

A new consumer requests the next unused ID (19) through a revision of this GDD; IDs 1–18 are reserved for the owners listed even if their GDDs later rename the event.

**R5 — Event keys.** An event key is an ordered list of unsigned 64-bit integers that uniquely identifies the event inside its domain for the lifetime of the save. The owning system defines the key layout in its own GDD (for example combat: `[party_id, trip_ordinal, encounter_ordinal]`). Every key component must itself be deterministic and saved: stable entity IDs, per-entity ordinal counters, integer simulation time in milliseconds, and content IDs given as the integer `uid` of the content row. Never allowed in a key: wall-clock time, floating-point values, object or memory identities, hash-map iteration order, frame counts, or anything that differs between Python and the engine port.

- **Range and type.** Every key component is an unsigned 64-bit value, 0 … 2⁶⁴−1. It never masks or wraps. What each port can check differs, and the rule is:
  - **Python reference:** a component must be exactly an `int` (`type(x) is int`; `bool` and `float`, including `5.0`, are rejected) in 0 … 2⁶⁴−1. Anything else is an error (R9).
  - **Signed-64-bit ports (GDScript):** keys are `Array[int]`. Every 64-bit pattern is a valid component, and a negative `int` *is* the component 2⁶⁴ + x (so `−1` is 2⁶⁴−1). The port cannot detect an out-of-range value, so it checks only what it can express: key length, an empty key, the domain, and the element type.
  - **Consequence:** a negative number produced by a subtraction bug is rejected by the Python reference but accepted by the port. The Python reference, which runs the full test suite and the balance simulator, is the side that catches it. The parity vectors (AC-21) include error cases only for inputs both ports can express.
- **Content `uid`s.** Every data table whose rows can appear in a key or in a `choice` list carries an explicit, append-only integer `uid` column: never reused, never renumbered, validated unique by the content validator in CI. Row position and engine string hashes (GDScript `hash()`) are never used. The column and its validation are owned by Data layer and content pipeline (3).
- **Keys never contain player-mutable state.** No key may include anything the player can change before the event: party composition, equipment, chosen zone, settings, or a counter that unrelated actions advance. Keys are built only from saved IDs and from ordinals that only the event itself advances. Simulation time may appear in a key only where only the simulation advances it, never where the player controls it by waiting or choosing when to act. So after a reload the *dice* for an event are always the same; the *outcome* differs only if the player changed the event's inputs. Because the dice are fixed, a player can reload and try different inputs against them. This is an accepted property of seeded single-player RNG, not a re-roll (Edge Cases, save-scumming).

**R6 — Uniqueness is the owner's job.** Two different events in the same domain must never share a key; if they do, they get identical outcomes. Each owning system's GDD states why its key layout is unique (usually: an entity ID plus a counter that only increases and is saved).

**R7 — Draw order inside an event is a contract.** Within one event, the number and order of draws is part of the owning system's specification. Reordering, adding or removing a draw inside an event changes that event's outcomes and is a **breaking change** to the parity vectors (Dev tooling, system 43); it must be versioned and called out in that system's changelog. Changes in one event never affect any other event (that is the point of R3).

**R8 — Derived draws.** All draws are built on `next_u32` and specified exactly in Formulas: `random()` (float in [0, 1) with 2⁻³² resolution, F3), `randint(a, b)` (exactly uniform integer via Lemire's method with rejection, F4), `choice(list)` (F5), `chance_ppm(k)` (F6, the form every data-driven probability uses) and `chance(p)` (F6, for probabilities computed at run time). No other derived draw may be added without updating this GDD and the golden vectors.

**R9 — Invalid calls fail loudly.** These are programmer or data errors:
- `randint(a, b)` with `b < a`, or a range wider than 2³² values
- `choice` on an empty list
- a key that is empty, longer than 16 components, or has a component outside 0 … 2⁶⁴−1 (Python only; R5)
- a non-integer argument where an integer is required (`a`, `b`, `k`, `domain_id`, `world_seed`, key components). In Python, `bool` and `float` values count as non-integers, even `5.0`
- a missing world seed, or a domain ID not in the R4 registry
- `chance_ppm(k)` with `k` outside 0 … 1,000,000
- `chance(p)` with `p` NaN
- any draw on a discarded generator

The call fails through the API contract's error path (the fatal sink). That path is still active in release builds, so a bad call can never succeed in one build and fail in another. No simulation result is ever computed from a failed call.

`chance(p)` accepts every other `p`, including ±infinity: `p ≤ 0` is always false and `p ≥ 1` is always true, by definition of F6, so these are not errors.

**R10 — No rigging, anywhere.** No system may alter the outcome of a draw after it is made, redraw because it disliked a result, or keep hidden streak or pity state that changes odds. Luck effects change the *inputs* to a draw (a probability, a weight table) in a way the owning GDD documents, never the draw itself. Purchases and entitlements never change any probability (Player Fantasy).

**R11 — What is saved.** Because generators are per-event and short-lived, the save stores only `world_seed` and the event-ordinal counters that the owning systems use in their keys. No generator state is saved. An event in progress at save time is either completed before saving or restarted from its key on load, which reproduces the same draws.

**R12 — Same results everywhere.** For the same `world_seed`, domain ID, event key and call sequence, every implementation (Python reference, engine port, server verifier) returns bit-identical `next_u32` values and therefore identical integer and boolean results. Float results from `random()` are identical because they are an exact division of a 32-bit integer by 2³² (F3).

### API Contract

Names are normative; the Python reference and the engine port expose the same surface. There is no global or static RNG state: the factory is constructed once per simulation run and passed to the systems that draw (dependency injection, per the coding standards).

| Member | Signature | Behaviour |
|---|---|---|
| `RngFactory` | `RngFactory(world_seed: uint64, assert_unique_keys: bool, fatal_sink: Callable = default)` | One per simulation run (a live session, an offline fast-forward, a balance-sim run, a verifier replay, one test). Loading a save starts a new run and builds a new factory. Both the seed and the tracking flag are required arguments; there is no default for either. Tests may also pass `key_cap` (default 1,000,000) to lower the tracking cap. Fails (R9) if `world_seed` is missing, not an integer, or outside 0 … 2⁶⁴−1 |
| `derive` | `factory.derive(domain_id: int, key: list[int]) -> EventRng` | F2 + `pcg32_init`. Validates the domain (registry R4), the key length (1–16) and the key components (R5) |
| `event_seed` | `event_seed(world_seed, domain_id, key) -> uint64` | Pure F2, with the same validation as `derive`. Used by tests and by the verifier's logs |
| `rng.event_seed` | read-only `uint64` | The seed this generator was derived from |
| `rng.draws_consumed` | read-only `int` | Number of `next_u32` steps taken since `derive`, *excluding* the two in `pcg32_init`. Every derived draw counts the raw draws it used, including rejected ones (F4) |
| `factory.derive_count`, `factory.mix_calls` | read-only `int` | Counters since the factory was built. They are plain integer increments, kept in release builds |
| `next_u32` | `rng.next_u32() -> int` | F1 |
| `random` | `rng.random() -> float` | F3 |
| `randint` | `rng.randint(a: int, b: int) -> int` | F4 |
| `choice` | `rng.choice(items: list) -> item` | F5 |
| `chance_ppm` | `rng.chance_ppm(k: int) -> bool` | F6 |
| `chance` | `rng.chance(p: float) -> bool` | F6 |
| `close` | `rng.close()` | Marks the generator discarded. Every later draw on it fails (R9). Idempotent: a second `close()` does nothing. Calling it is recommended but not required: forgetting it changes no result and only loses misuse detection. Python also supports `with factory.derive(...) as rng:`, which closes on exit |
| `new_world_seed` | `new_world_seed(entropy_fn, clock_fn, install_id) -> (seed: uint64, used_fallback: bool)` | R2. All three arguments are injected so tests can drive each path (see below) |

- **Error path (fatal sink).** Every R9 failure calls `fatal_sink(message)`. The message contains `domain=<id>` and the key where relevant.
  - **Python:** the default sink raises `RngError`, a subclass of `ValueError`. So a failed call never returns.
  - **Engine port:** the default sink is supplied by Sim core and tick loop (1). It calls `push_error(message)` and marks the current simulation step as failed, so the tick loop stops, discards that tick's events and command-log entries without advancing `tick`, and marks simulation state untrusted (Sim core R10). The core does not roll back feature state already changed in that tick. `assert` is never used, because GDScript strips it in release builds.
  - **After the sink returns (port only):** GDScript has no exceptions, so the failing call must still return a value. It returns a defined poison value: `0` from `next_u32` and `randint`, `0.0` from `random`, `false` from `chance` and `chance_ppm`, and `null` from `choice`. `derive` returns a generator that is already closed. The generator is also marked closed, so every later call goes to the sink again. A poison value can never reach a committed result, because the step it belongs to is discarded.
  - **Web port:** the sink throws.
  - **Tests:** tests inject a recording sink and assert that it was called and with which message.
- **Test seam.** `EventRng.from_raw(draws: list[int], fatal_sink)` builds a generator whose `next_u32` returns the given raw values in order. When the list is exhausted, it fails (R9). The derived draws (F3–F6) run on it unchanged. It exists for tests only: the AC-03 lint flags any use of it outside the test root.
- **`new_world_seed` arguments:**
  - **`entropy_fn() -> int`** returns 64 random bits as an integer in 0 … 2⁶⁴−1 (signed ports: any 64-bit pattern). It has **failed** if it raises, or (Python) returns a non-integer or an out-of-range value. If it succeeds, the result is `(that value, false)`.
  - **`clock_fn() -> int`** returns wall-clock nanoseconds since the Unix epoch as an integer. Ports whose clock is in milliseconds or float seconds convert to integer nanoseconds.
  - **`install_id: uint64 | None`** is a 64-bit random value created once at first launch and kept in platform settings (the store Settings (45) defines), not in the save. It is not a hash of a device identifier.
  - **Fallback:** if `entropy_fn` fails, the result is `(mix(clock_fn() ^ install_id), true)`, using F2's `mix`. If `install_id` is also `None`, the call fails (R9), because R2 forbids a seed from the clock alone. New-guild creation then shows an error rather than creating a guild.
- **Unique-key tracking.** The tracking scope is one `RngFactory`, so one simulation run. Each test builds its own factory.
  - **What is stored:** the set holds `(domain_id, full key)` pairs, so a repeat means exactly the same event, and a 64-bit seed collision never causes a false failure. In Python each entry costs roughly 100–200 bytes.
  - **Hard cap:** a factory tracks at most 1,000,000 keys. At the cap, tracking turns off for the rest of the run and logs one warning that names the cap. It never fails a run because of the cap.
  - **Where it is on:** debug builds and tests pass `assert_unique_keys=True`. Release, balance-sim, offline fast-forward and verifier-replay runs pass `False`.
  - **What it does not catch:** tracking does not cross a save/load boundary, because a load builds a new factory. A counter that was not saved and restarts at 0 is caught by the save/load equivalence test (AC-18), whose state after the reload then differs from the uninterrupted run.
- **Threading.** An `EventRng` belongs to the thread that derived it. `derive` is pure apart from the counters and the tracking set, which belong to the factory. A factory is used by one thread only. A worker thread, for example an offline fast-forward, builds its own factory with `assert_unique_keys=False`.

### States and Transitions

The system itself is almost stateless. Two lifecycles matter:

**World seed (per save)**

| State | Meaning | Transition | To |
|---|---|---|---|
| Absent | No guild exists yet | New guild created: draw 64 bits of OS entropy | Set |
| Set | `world_seed` stored in the save | Save written | Set (unchanged) |
| Set | — | Save loaded | Set (same value) |
| Set | — | Any attempt to change it | **Forbidden** — the seed never changes for the life of a save |

**Event generator (per random event)**

| State | Meaning | Transition | To |
|---|---|---|---|
| — | No generator | Owner calls `derive(domain, key)` | Live |
| Live | Seeded from F2; draws allowed | Owner makes draws | Live |
| Live | — | Event resolves | Discarded |
| Live | — | Save requested mid-event | Owner completes the event first, or discards and replays from the same key on load (R11) |
| Discarded | Owner called `close()`; must not be used | Any draw on a discarded generator | Error (R9), detected by the generator's `closed` flag |

There is no transition in which a generator survives past its event, is shared between two events, or is re-seeded.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Who owns the interface |
|---|---|---|---|---|
| Sim core and tick loop (1) | RNG → core | — | `derive()` available to every tick phase | RNG owns the API; Sim core owns *when* events run |
| Local save (6) | both | `world_seed` on load | `world_seed` to save | Save owns the format; RNG owns the rule that only the seed is saved (R11). Owning systems save their own ordinal counters |
| Combat (10), Zones and hunt (11), Items and loot (26), Golden Boss (14), Recruitment (15), CA/PA (9), Enhancement (24), Utility AI (12), Retention (16), Crafting (28), Jianghu (17), Tower (19), Arena (18), Quests (25) | owner → RNG | domain ID + event key | draws | Each owner defines its key layout and draw order in its own GDD (R5–R7) |
| Offline progress (31) | owner → RNG | domain 5 + key | draws | Offline uses the same rules; its sampled trips have their own domain because they are different events from live trips |
| Leaderboards and anti-cheat (35) | RNG → verifier | `world_seed` + command log from the client summary | replayed outcomes | Leaderboards owns the summary format; RNG guarantees R12 |
| Dev tooling and parity harness (43) | RNG → tooling | fixed seeds, domains, keys | golden vectors | Tooling owns the parity test files; RNG defines what must match (Acceptance Criteria) |
| Presentation (38, 40) | none | — | — | Presentation must not use this system for cosmetic noise; it uses engine random freely because the result never feeds the sim (R1) |

*Specialist lenses applied:* systems-designer (primary), gameplay-programmer and engine-programmer (supporting), per the Foundation/Infrastructure routing row. The tension between keeping the current single stream and isolating streams was put to the user; the user chose per-event seeding, which goes further than named per-system streams.

## Formulas

All arithmetic below is on unsigned integers modulo 2⁶⁴ unless marked otherwise. `>>` is a **logical** right shift, `^` is XOR, `|` is OR, and `rotr32(x, r)` rotates a 32-bit value right by `r` bits. It is defined for every r in 0 … 31 as `((x >> r) | (x << ((32 − r) & 31))) & 0xFFFFFFFF`, which gives `x` at r = 0. Integer division and modulo (`t`, `T(k)`, `n`, all non-negative) are `//` and `%` in Python, and `/` and `%` on `int` operands in GDScript.

**Port rules for signed 64-bit integers.** These apply to GDScript and to any other port whose `int` is a signed 64-bit integer. Multiplication and addition wrap correctly there; the following are mandatory (`GODOT_PORT.md`, rule 1):
1. **No bare `>>` on a 64-bit value.** Every right shift in F1, F2 and F4 goes through one helper, `lsr64(x, n) = (x >> n) & ((1 << (64 − n)) − 1)` for 1 ≤ n ≤ 63. A bare `>>` inside the RNG module is a review failure. The affected shift sites are:
   - F1: `>> 18`, `>> 27`, `>> 59`
   - F2: `>> 30`, `>> 27`, `>> 31`
   - F4: `>> 32`
2. **Constants above 2⁶³−1 are written as signed decimals,** never as hex literals:
   - `0x9E3779B97F4A7C15` = −7046029254386353131
   - `0xBF58476D1CE4E5B9` = −4658895280553007687
   - `0x94D049BB133111EB` = −7723592293110705685

   `MULT` (6364136223846793005) is below 2⁶³ and needs no conversion. AC-04 proves the conversion.
3. **`world_seed` is serialised as a 16-digit lowercase hex string,** never as a JSON number. JSON parsers, including Godot's, read numbers as doubles and lose precision above 2⁵³.
4. **F3 divides by a float literal.** In GDScript, `int / int` is integer division, so `next_u32() / 4294967296` would always give 0. Write the divisor as `4294967296.0`.
5. **Range checks run before any arithmetic that could wrap** (F4). The worked examples were computed against `sim/rng.py`; the F2 and F4 examples use a scratch implementation of this specification, because the code does not implement F2 or the rejection step yet (Open Questions).

This system defines no tunable game values: every variable is either a fixed algorithm constant or an input supplied by the caller. There are no feedback loops.

### F1 — PCG32 step and seeding

The pcg32_step formula is defined as:

`pcg32_step: old = state; state = old · MULT + inc; out = rotr32( ((old >> 18) ^ old) >> 27 (low 32 bits), old >> 59 )`

`pcg32_init(seed, seq): state = 0; inc = (seq << 1) | 1; pcg32_step; state = state + seed; pcg32_step`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| state | uint64 | 0 – 2⁶⁴−1 | calculated | Generator state; advances once per draw |
| old | uint64 | 0 – 2⁶⁴−1 | calculated | The state before this step; the output is computed from it |
| inc | uint64 | odd values 1 – 2⁶⁴−1 | calculated | Stream increment; always odd, so every `seq` gives a full-period stream |
| MULT | uint64 | 6364136223846793005 | constant | PCG reference multiplier |
| seed | uint64 | 0 – 2⁶⁴−1 | calculated (F2) | Initial seed; 0 is valid |
| seq | uint64 | 0 – 2⁶³−1 | calculated (domain ID) | Stream selector; in this game always the domain ID (R4) |
| out | uint32 | 0 – 2³²−1 | calculated | The value returned by `next_u32` |

**Output Range:** `out` covers 0 to 2³²−1 uniformly with period 2⁶⁴ per stream. At extremes: seed 0 and seq 0 are valid; `seq ≥ 2⁶³` loses its top bit in the shift and aliases a lower `seq`, which cannot happen because domain IDs are small.
**Example:** `pcg32_init(42, 54)`, then six draws → `0xa15c02b7, 0x7b47f409, 0xba1d3330, 0x83d2f293, 0xbfa4784b, 0xcbed606e` (the official PCG32 reference vectors, asserted today by `tests/test_core.py::TestRng::test_pcg32_official_vectors`).

### F2 — Event seed derivation

The event_seed formula is defined as:

`mix(z) = z' ^ (z' >> 31)`, where `z1 = z + 0x9E3779B97F4A7C15; z2 = (z1 ^ (z1 >> 30)) · 0xBF58476D1CE4E5B9; z' = (z2 ^ (z2 >> 27)) · 0x94D049BB133111EB` (the SplitMix64 finaliser)

`event_seed(world_seed, domain_id, key[0..n−1]) = mix( h_n ^ n )`, where `h_0 = mix( world_seed ^ mix(domain_id) )` and `h_(i+1) = mix( h_i ^ key[i] )`

`event_generator = pcg32_init( seed = event_seed(...), seq = domain_id )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| world_seed | uint64 | 0 – 2⁶⁴−1 | save file | The save's only entropy (R2) |
| domain_id | uint64 | 1 – 18 today; append-only | constant (registry in Core Rules R4) | Which consumer is drawing |
| key[i] | uint64 | 0 – 2⁶⁴−1 | calculated (owning system) | Event key components (R5); anything outside this range is an error, never masked |
| n | int | 1 – 16 | calculated | Key length; **must be ≥ 1** (empty key is an error, R9). 16 is a sanity cap, not a design need |
| h_i | uint64 | 0 – 2⁶⁴−1 | calculated | Running hash |

**Output Range:** a 64-bit seed. Folding `n` in at the end means `[5]` and `[5, 0]` give different seeds. The chance that two different events in one domain receive the same seed is roughly `E² / 2⁶⁵` for `E` events in that domain; at an estimated 17 million combat events per save-year (20 members × about 100 fights an hour, all year), that is about 10⁻⁵. A collision is harmless (two outcomes coincide) and is not detected. Different domains never share a stream even with equal seeds, because `seq` differs.
**Example:** `mix(0) = 0xe220a8397b1dcdaf` (matches the published SplitMix64 reference). `event_seed(42, 1, [7, 3, 0]) = 0x95221e61ae016288`; that generator's first three `next_u32` values are `0x3369385d, 0x5d832f29, 0x93a287a4`. High-bit vector (exercises every masked shift): `event_seed(2⁶⁴−1, 18, [2⁶³, 2⁶⁴−1]) = 0xa559044d93ff9e7d`, first three draws `0x89b429db, 0x0eaffbae, 0x31ff0819`. `event_seed(42, 1, [2⁶⁴−1]) = 0xdd116837814cfa36`. In GDScript the same component is written `[−1]` and gives the same seed. In the Python reference, `[−1]` is an error (R5).

### F3 — Uniform float

The random formula is defined as:

`random() = next_u32() / 2³²` (exact IEEE-754 double division)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| next_u32() | uint32 | 0 – 2³²−1 | calculated (F1) | One draw |

**Output Range:** 0 to 1 − 2⁻³² (0.99999999977), resolution 2⁻³². Never returns 1.0, so `floor(random() · k)` is always in 0 … k−1. Returns exactly 0.0 with probability 2⁻³². Identical in Python and GDScript because both use 64-bit doubles and the division is exact.
**Example:** the first draw of the F2 example generator is `0x3369385d` = 862,533,725 → `random() = 0.20082428236491978`.

### F4 — Exactly uniform bounded integer

The randint formula is defined as:

`randint(a, b)`: first the range check. Compute `d = b − a`, which wraps in signed 64-bit. The call is an error (R9) if `b < a`, or `d < 0`, or `d > 4,294,967,295`. Here `d < 0` with `b ≥ a` is exactly the case where the true difference is 2⁶³ or more. For example, `a = −2⁶³, b = 2⁶³−1` gives `d = −1`. Without that test it would pass `d ≤ 2³²−1` and lead to `n = 0` and a modulo by zero. In Python, where integers do not wrap, `d < 0` never fires and `d > 4,294,967,295` catches the same case. Then `n = d + 1`; `x = next_u32(); m = x · n; l = m mod 2³²`; if `l < n`: `t = (2³² − n) mod n`; while `l < t`: `x = next_u32(); m = x · n; l = m mod 2³²`; return `a + (m >> 32)` (Lemire's nearly-divisionless method with rejection)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| a, b | int64 | any int64, with `b ≥ a` and `b − a ≤ 2³² − 1` | calculated (caller) | Inclusive bounds. The check is done on `d = b − a` (with `d < 0` rejected) before computing `n`, because `b − a` can wrap in signed 64-bit (e.g. `a = −2⁶³, b = 2⁶³−1`) |
| n | uint64 | 1 – 2³² | calculated | Number of possible results; computed only after the range check passes |
| x | uint32 | 0 – 2³²−1 | calculated (F1) | One raw draw |
| m | uint64 | 0 – (2³²−1)·2³² | calculated | 64-bit product; can exceed 2⁶³, so GDScript must use the masked shift |
| l | uint32 | 0 – 2³²−1 | calculated | Low 32 bits of `m`; compared against `t` to decide rejection |
| t | uint32 | 0 – n−1 | calculated | Rejection threshold |

**Output Range:** every value in `[a, b]` with probability exactly `1/n`. Always consumes at least one draw, including when `n = 1`. The number of draws is otherwise data-dependent only through rejection: changing `n` changes which raw draws are rejected, so with probability under 0.0001% at gameplay sizes it can shift the later draws in the same event. Each draw is rejected with probability `r = t / 2³² < n / 2³²`. A call therefore rejects at least once with probability `r`, and costs `r / (1 − r)` extra draws on average. For any `n` up to 4,000 (gameplay sizes) both figures are under 0.0001%. At `n = 3·2³⁰`, `t = 2³⁰`, so `r = 25%` and extra draws are 33.3%. Measured from the F2 example generator over 100,000 calls: 25.01% of calls rejected, 0.3335 extra draws per call. `n = 2³²` gives `t = 0`, so it never rejects.
**Example:** from the F2 example generator, five calls of `randint(1, 6)` → `2, 3, 4, 1, 6` (no rejection occurred).

### F5 — Choice

The choice formula is defined as:

`choice(list) = list[ randint(0, len(list) − 1) ]`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| list | ordered sequence | length 1 – 2³² | calculated (caller) | Candidates in a deterministic order; an empty list is an error (R9) |

**Output Range:** each element with probability `1/len`. The caller must build the list in a deterministic order: sorted by the content `uid` (R5), never by file row position or hash-map iteration order. This is the order the Data layer exposes every table in (Data layer and content pipeline R4, R6). Sorting by `uid` makes the order independent of spreadsheet edits. It does **not** make content changes local: adding a row to a list changes `len`, which can change the outcome of every event that draws from that list. That is why outcomes are tied to the content hash and sim version (Edge Cases, version). A weighted pick from a data table (drop tables) belongs to the owning system. It must use `randint` against cumulative integer weights ordered by `uid`, so it consumes at least one draw (more only on F4 rejection), and that system's GDD specifies it.
**Example:** `choice(["kim", "moc", "thuy", "hoa", "tho"])` with a first draw giving `randint(0, 4) = 2` → `"thuy"`.

### F6 — Chance

The chance formula is defined as:

`chance_ppm(k) = next_u32() < T(k)`, where `T(k) = floor( k · 2³² / 1,000,000 )` (pure integer arithmetic)

`chance(p) = random() < p`

**Probabilities in data are integers.** Every probability stored in a data file is an integer in parts per million (0–1,000,000, column suffix `_ppm`), and goes through `chance_ppm`. A float parsed from a CSV can differ by one ulp between Python and Godot's `String.to_float` and flip a draw near the boundary; an integer cannot. `chance(p)` is kept only for probabilities computed at run time from integers or exact floats (for example a buff multiplier applied to a ppm value), and the owning GDD must show that the computation is bit-identical in both ports. Where possible, compute in ppm and call `chance_ppm`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| k | int | 0 – 1,000,000 | data file (owning system), e.g. `drop_chance_ppm` in `drop_tables.csv` | Success probability in parts per million; outside the range is an error (R9) |
| T(k) | uint64 | 0 – 2³² | calculated | Integer threshold. `T(1,000,000) = 2³²`, so a `uint32` draw is always below it |
| p | float64 | any non-NaN real | calculated (caller) | Run-time probability for `chance`; NaN is an error (R9) |

**Output Range:**
- `chance_ppm(k)` is true with probability exactly `T(k) / 2³²`. This is within 2⁻³² of `k / 10⁶`, rounded down.
  - `k = 0` is always false and `k = 1,000,000` is always true.
  - Any `0 < k` gives at least 4294/2³² ≈ 10⁻⁶.
- `chance(p)` for `0 < p < 1` is true with probability `ceil(p · 2³²) / 2³²`, because `x / 2³² < p` holds for every `x < p · 2³²`. This rounds **up** to the 2⁻³² grid.
  - Any `p > 0` succeeds with probability at least 2⁻³².
  - Any `p > 1 − 2⁻³²` is always true.
  - The maximum bias is 2⁻³², which is harmless for gameplay.
- **The two forms round in opposite directions, by decision (user, 2026-11-16).** `chance_ppm` rounds down and `chance` rounds up. So `chance(k / 10⁶)` and `chance_ppm(k)` can disagree on at most one raw draw value out of 2³². The two are not interchangeable in parity vectors; each has its own.
- `chance(p)` is always false for `p ≤ 0` (including −∞) and always true for `p ≥ 1` (including +∞).
- **Both forms always consume exactly one draw, even at the extremes,** so tuning a probability to 0 or 1,000,000 in a CSV never shifts later draws in the same event.

**Example:** the F3 example raw draw is `0x3369385d` = 862,533,725.
- `chance_ppm(250000)`: T = 1,073,741,824, so the result is `true`.
- `chance_ppm(200000)`: T = 858,993,459, so the result is `false`.
- `chance_ppm(0)` is `false`.
- `chance(0.25) = true`, `chance(0.2) = false`.

*Lens applied:* systems-designer, Section D checks. Every formula was run at its minimum, maximum and zero inputs. Two boundary rules were decided by the user: event keys need at least one component, and `chance` always consumes one draw.

## Edge Cases

- **If two different events in the same domain are given the same event key** (an owning system's bug, for example an ordinal counter that was not saved and restarted at 0 after load): both events receive identical draws and therefore identical outcomes. Release builds do not detect this. With `assert_unique_keys` on (debug builds and tests), the factory tracks the full keys derived in its own simulation run and fails on a repeat, naming the domain and key. A load builds a new factory, so a reload that legitimately re-derives the same keys is not a repeat. The example bug (a counter not saved) crosses a load, so tracking cannot see it; the save/load equivalence test (AC-18) catches it instead. Scope, cap and memory are given in the API Contract. The owning system fixes its key layout; this system never "fixes" a duplicate by mutating the key.
- **If a save is requested while an event is in progress**: no event's results are ever half-applied. The simulation applies an event's results only when it resolves (an owning-system obligation stated here because RNG relies on it). The save either waits for resolution or stores the pre-event state; on load the event re-derives its generator from the same key and replays identical draws.
- **If the player reloads a save to try for a different outcome (save-scumming)**: the outcome repeats exactly, because the key and world seed are unchanged. To keep this true, **event keys for player-initiated gambles** — enhancement attempts (24), recruitment candidates (15), crafting with random outcomes (28), and any later system where the player chooses when to roll — **must use per-object attempt ordinals only** (for example `[item_instance_id, enhance_attempt_ordinal]`), never simulation time, frame counts, or a global counter that other actions advance. Otherwise reloading and doing something unrelated first (or waiting a second) would give a fresh roll — a degenerate strategy. Each such GDD states its key and why the player cannot shift it. **The same holds for every other domain** (combat, loot, spawn, hunt trips, raids, and so on): under R5, keys contain no player-mutable state. A player who reloads and changes the party, equipment or zone before a hunt gets the same dice applied to different inputs. No change, however trivial, re-rolls the dice. Each owning GDD's key-uniqueness argument (R6) also states that no key component is player-mutable.
  - **Accepted: probing fixed dice (user, 2026-11-16).** Because the dice are fixed before the player commits the inputs, a player can reload, change the lineup or an item, and keep the configuration whose inputs push a known draw across a threshold, for example a rare drop. This is a search over inputs, not a re-roll. It is an accepted property of seeded single-player RNG, shared with games that fix their dice per action. It does not affect leaderboard fairness, because the verifier replays the whole command log. Whether a player gamble needs a commit point (for example, an attempt ordinal consumed and saved when the attempt is dispatched) is decided in each gamble GDD (OQ-6).
- **If offline progress and live play cover adjacent stretches of time**: their events can never share a generator, because offline sampled trips use their own domain (5, `offline_sample`) and live trips use domains 1–4. Which ordinal counters offline advances so that live keys continue without overlap is owned by Offline progress (31).
- **If two saves have the same `world_seed`** (vanishingly unlikely with 64 bits of entropy): given identical command sequences they play out identically. Accepted; no detection.
- **If OS or platform entropy is unavailable when a new guild is created**: the world seed falls back to `mix(clock_ns ^ install_id)` (F2's `mix`; arguments as defined in the API Contract). If no install ID exists either, new-guild creation fails with an error rather than seed from the clock alone. This fallback is allowed only for choosing a new world seed, never during play, and the save records that the fallback was used so a later audit can tell.
- **If a game update changes the draws inside an event** (adds, removes or reorders a draw — a breaking change under R7): existing saves continue under the new rules from the moment they load in the new version; events already resolved are not recomputed. Every leaderboard summary carries the simulation version that produced it, and the verifier (35) replays with that same version or rejects the summary as unverifiable — it never replays an old summary with new rules.
- **If an update adds a new domain**: its events derive from the existing `world_seed`; no save migration is needed. **If a system is removed**: its domain ID is retired and never reused (R4), so no future system can inherit its outcomes.
- **If `chance(p)` receives NaN** (a formula bug), it is an error (R9), not a silent `false`, so the bad formula is found immediately.
  - Both ports check it explicitly (`math.isnan(p)` / `is_nan(p)`), because `random() < NaN` is silently false in both languages.
  - ±infinity follows the normal extremes: `−inf` is always false, `+inf` always true.
  - **If `chance_ppm(k)` receives a value outside 0 … 1,000,000** (a data bug), it is an error (R9). It is never clamped. The content validator also rejects such values at load time.
- **If `randint(a, b)` is called with bounds more than 2³² − 1 apart**, for example `randint(−2⁶³, 2⁶³−1)`, where `b − a + 1` would wrap to 0 in signed 64-bit: error (R9). The range is checked on `b − a` before `n` is computed (F4). Gameplay ranges are far below these limits; the rule exists so the Python and engine versions fail the same way instead of diverging.
- **If two events resolve in the same tick and the two implementations process them in different orders**: the draws are unaffected, because each event has its own generator derived only from its key. The order of their *state changes* is owned by the Sim core's tick phases (1), not by this system.

*Accepted, not resolved here:* **seed shopping.** A player can create new guilds until one has a lucky early run (for example strong first recruits) to gain a leaderboard edge. The edge is small and early-game only, and the game is single-player and offline-first. Owner: Leaderboards and anti-cheat (35), which may add an account-age rule or a server-issued seed. Recorded in Open Questions.

*Lens applied:* systems-designer, Section E checks on Sections C and D. One degenerate strategy (save-scumming through time-shifted keys) was found and closed with the attempt-ordinal key rule; the user accepted seed shopping as an open question for Leaderboards.

## Dependencies

**Upstream (this system depends on): none.** RNG is Foundation-layer. It needs no other system to function; the only things it is given are inputs (`world_seed`, domain ID, event key) supplied by its callers.

**Downstream (systems that depend on this one).** Every system below has a GDD. Each lists Deterministic RNG in its own Dependencies section and states its domain ID, event-key layout, key-uniqueness argument (R6) and in-event draw order (R7).

| System (#) | Hard / soft | Interface | Domain ID(s) |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | Makes `derive(domain, key)` available in every tick phase; never draws itself | — |
| Local save and migration (6) | Hard | Persists `world_seed` (R11); owning systems persist their own ordinal counters | — |
| CA/PA and traits (9) | Hard | Fixed PA-display noise; trait-reveal checks | 9, 18 |
| Combat (10) | Hard | One generator per fight | 1 |
| Zones, grounds, monsters and hunt trips (11) | Hard | Spawn choice, per-trip choices | 3, 4 |
| Utility AI (12) | Soft | Only for exact score ties; without RNG ties fall back to lowest ID first | 11 |
| Golden Boss and guild raid (14) | Hard | One generator per raid; hourly boss pick | 6, 7 |
| Recruitment (15) | Hard | One generator per candidate (player gamble: attempt-ordinal keys) | 8 |
| Retention (16) | Hard | Negotiation and leave checks | 12 |
| Jianghu free agents and NPC guilds (17) | Hard | NPC guild growth and offers | 14 |
| Arena (18) | Hard | One generator per bout | 16 |
| Endless Tower (19) | Hard | One generator per floor | 15 |
| Equipment enhancement (24) | Hard | One generator per attempt (player gamble: attempt-ordinal keys) | 10 |
| Quests and achievements (25) | Hard | Daily and weekly quest selection | 17 |
| Items and loot tables (26) | Hard | One generator per kill's drop roll | 2 |
| Crafting and recipes (28) | Hard | Random-outcome crafts only (player gamble: attempt-ordinal keys) | 13 |
| Offline progress (31) | Hard | One generator per sampled trip | 5 |
| Leaderboards and anti-cheat (35) | Hard | Replays summaries from `world_seed` + command log + sim version (R12, Edge Cases) | — |
| Dev tooling and parity harness (43) | Hard | Owns the golden-vector files that prove R12 across implementations | — |
| Settings (45) | Soft | Owns the platform-settings store that keeps `install_id` (API Contract, `new_world_seed`) | — |

"Hard" means the dependent system cannot produce its outcomes without this one. The only soft dependent is Utility AI, which uses randomness only to break exact ties.

**Not dependents:** Realtime world view (38) and Audio (40) may use engine random functions for cosmetic effects that never feed the simulation (R1); they must not depend on this system.

**Consistency note for the systems index.** Re-verified 2026-11-16: every system in the table above lists RNG in its systems-index row, so the dependency is recorded in both directions.

## Tuning Knobs

**This system has no gameplay tuning knobs, by design.** Every variable in the Formulas table is either an algorithm constant or a caller-supplied input; none is marked `data file`. Making any of them adjustable would break the system's one promise: the same seed and key must give the same result everywhere and in every version (R12). The randomness a designer *does* tune — drop chances, PA distribution, enhancement success rates, damage variance — is owned by the system that consumes the draw and lives in that system's data (for example `data/drop_tables.csv`, `data/enhance.csv`, `data/sim_params.csv`), and is listed in that system's GDD.

**Fixed by design (not knobs — changing any is a breaking change requiring new golden vectors and a sim-version bump):**

| Value | Where defined | Why fixed |
|---|---|---|
| PCG32 constants (`MULT`, shift amounts 18 / 27 / 59) | F1 | Define the algorithm; the official reference vectors depend on them |
| SplitMix64 constants | F2 | Define event-seed derivation; every saved game's outcomes depend on them |
| Domain IDs 1–18 | Core Rules R4 | Append-only; renumbering changes every outcome in the affected domains |
| Draw resolution 2⁻³² | F3 | Changing it alters every float draw and the `chance` grid |
| Key-length cap 16 | F2 | Sanity limit only; raising it is harmless but must match in all implementations |

**Developer switches (not gameplay, not exposed to players):**

| Switch | Default | Effect | Safe range |
|---|---|---|---|
| `rng_assert_unique_keys` (the `RngFactory` `assert_unique_keys` argument) | on in debug builds and tests; off in release, balance-sim, offline and verifier-replay runs | Tracks `(domain_id, full key)` pairs per factory, so per simulation run, and fails on an exact repeat (API Contract) | on / off. Hard cap 1,000,000 keys per factory (roughly 100–200 MB in Python at the cap). At the cap tracking turns off with one warning. The cap is a fixed constant, not a knob |

*Lens applied:* systems-designer, Section G check. Knobs were derived from the Section D variable table; no `data file` variables exist, so no gameplay knobs are defined here. The knobs that shape randomness belong to the consuming systems' GDDs.

## Visual/Audio Requirements

Not applicable — this system has no visual or audio output. Cosmetic randomness in presentation (sprite jitter, particle variation) uses engine random functions and is specified by Realtime world view (38) and Audio (40), never by this system (R1).

## Game Feel

Not applicable — the player never operates this system directly. The fairness it guarantees is described under Player Fantasy.

## UI Requirements

Not applicable — no screen or HUD element. Systems that show odds (for example enhancement success rates) own that UI.

## Cross-References

Every referenced system now has a GDD (re-verified 2026-11-16).

| This GDD references | Referenced system / document | What is referenced | Status |
|---|---|---|---|
| Core Rules R2, R11 | Local save and migration (6) | Save persists `world_seed`; owners persist ordinal counters | `local-save-and-migration.md` |
| Core Rules R4 table | Systems 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 24, 25, 26, 28, 31 | Each owns its domain ID, key layout and draw order | Each system's GDD (Dependencies table above) |
| Edge Cases (save-scumming) | Recruitment (15), Enhancement (24), Crafting (28) | Player-gamble keys must use attempt ordinals | `recruitment.md`, `equipment-enhancement.md`, `crafting-and-recipes.md` |
| Core Rules R5, F5, F6 | Data layer and content pipeline (3) | Append-only integer `uid` column on every keyed or chosen table; probabilities stored as `_ppm` integers; validator checks both | design/gdd/data-layer-and-content-pipeline.md (R4 `ppm` type and `uid` order, R6 `uid` column, F4 assignment) |
| Edge Cases (offline/live) | Offline progress (31) | Which counters offline advances | `offline-progress.md` |
| Edge Cases (version), seed shopping | Leaderboards and anti-cheat (35) | Summaries carry sim version; seed-shopping policy | `leaderboards-and-anti-cheat.md` |
| Acceptance Criteria AC-21, AC-22 | Dev tooling and parity harness (43) | Golden-vector files and the parity gate | `dev-tooling-and-parity-harness.md` (R5–R8, R14) |
| Player Fantasy | `JX1_Tycoon_GDD.md` §5.2, §10, §11.2 | Luck trait, offline report, "do not sell power" | Source GDD v1.0 |
| Formulas, Core Rules | `GODOT_PORT.md` rules 1–2 | Logical right shift; draw order as contract | Existing doc |
| Formulas F1, AC-01 | `sim/rng.py`, `tests/test_core.py::TestRng` | Current implementation and reference vectors | Existing code |

## Acceptance Criteria

All criteria are **Logic** story type unless tagged **Integration**. Each Logic criterion needs an automated unit test under the test root (today `tests/`, Python `unittest`; the engine port adds its own under the engine's test root). Integration criteria need an integration test or a documented playtest. None needs a screenshot. Expected values come from Formulas; the Python reference is the oracle until the engine port exists.

- **Pending criteria.** A criterion tagged **[PENDING: needs X]** cannot run until X exists. It does not block closing this GDD's own implementation story; it blocks the story of the system named in the tag.
- **The F2 example generator** is `derive(1, [7, 3, 0])` on a new `RngFactory(world_seed=42, assert_unique_keys=False)`, read from its first draw. Every statistical criterion uses it, so its counts are fixed and reproducible. "A fresh F2 example generator" means one derived on a new factory. There is no clone API.
- **"Consumed N draws"** means `rng.draws_consumed` rose by exactly N across the call (API Contract).
- **"Injected raw draws"** means a generator built with the test seam `EventRng.from_raw(...)` (API Contract).
- **Python-only cases.** Cases marked *(Python only)* test a range or type check that a signed-64-bit port cannot express (R5). The port's suite omits them.

**Generator (F1, R1, R12)**
- **AC-01** — **GIVEN** a generator initialised with `pcg32_init(seed=42, seq=54)`, **WHEN** `next_u32` is called six times, **THEN** the results are exactly `0xa15c02b7, 0x7b47f409, 0xba1d3330, 0x83d2f293, 0xbfa4784b, 0xcbed606e`. *(Covers F1. Passes today.)*
- **AC-02** — **GIVEN** `pcg32_init(seed=0, seq=0)`, **WHEN** three draws are made, **THEN** they are exactly `0xe4c14788, 0x379c6516, 0x5c4ab3bb`. *(F1 boundary: zero seed and zero stream.)*
- **AC-03** — a lint step searches the simulation source tree (`sim/` today, the engine core later).
  - It looks for these patterns, matched on word boundaries with comments stripped. Each pattern is anchored so that a name preceded by `.` (a method call on an object, such as `rng.random()`) never matches, except where the pattern itself names the module:
    - Python: `import random`, `from random`, `random\.\w+` where `random` is not preceded by `.`, `secrets`, `os.urandom`, `time.time`, `hash(`
    - GDScript: `randf`, `randi`, `randf_range`, `randi_range`, `randfn`, `randomize`, `rand_from_seed`, `pick_random`, `shuffle`, `RandomNumberGenerator`, `Crypto`, `generate_random_bytes`, `hash(`
    - Both: `from_raw` (the test seam) anywhere outside the test root
  - **THEN** there are zero matches. The only exception is an explicit allow-list containing exactly one function: the world-seed `entropy_fn` of this system's module (R2).
  - **AND** the lint reports at least one scanned file per source tree, so a wrong path fails instead of passing.
  - **AND** a fixture file with one planted violation per pattern is flagged on every pattern.
  - *(R1, R5, API Contract test seam.)*

**Event seeding (F2, R2–R6)**
- **AC-04** — **GIVEN** the SplitMix64 `mix` function, written with the port's constant spelling (signed decimals in a signed-64-bit port, per the Formulas port rules), **WHEN** `mix(0)` is computed, **THEN** it equals `0xe220a8397b1dcdaf`. *(F2 constant check.)*
- **AC-05** — **GIVEN** `world_seed = 42`, domain 1, key `[7, 3, 0]`, **WHEN** the event generator is derived, **THEN** its seed is `0x95221e61ae016288` and its first three draws are `0x3369385d, 0x5d832f29, 0x93a287a4`. **GIVEN** `world_seed = 2⁶⁴−1`, domain 18, key `[2⁶³, 2⁶⁴−1]`, **THEN** its seed is `0xa559044d93ff9e7d` and its first three draws are `0x89b429db, 0x0eaffbae, 0x31ff0819`. **GIVEN** `world_seed = 42`, domain 1, key `[2⁶⁴−1]`, **THEN** its seed is `0xdd116837814cfa36`. *(F2 golden vectors, typical and high-bit, the second exercising every masked shift.)*
- **AC-06** — **GIVEN** `world_seed = 42`, **WHEN** generators are derived for keys `[5]` and `[5, 0]` in domain 1, and for key `[5]` in domains 1 and 2, **THEN** all four seed/stream pairs differ and their first draws are not all equal. *(F2: length folding and domain separation.)*
- **AC-07** — **GIVEN** an event generator for domain 2, key `[100, 1]`, **WHEN** an unrelated event in domain 1 makes 0, 1 or 50 draws before it is derived (each case on its own factory), **THEN** the domain-2 generator's first ten draws are identical in all three cases. *(R3: events are isolated from each other's draw counts.)*
- **AC-08** — **GIVEN** a factory, **WHEN** `derive` is called with any of the following, **THEN** each raises `RngError` and returns no generator:
  - an empty key
  - a key of 17 components
  - domain ID 0, or the lowest ID above the registry's highest (19 today)
  - *(Python only)* a key containing `−1`, `2⁶⁴`, `1.5`, `5.0` or `True`

  **GIVEN** `RngFactory(world_seed=None)`, or *(Python only)* `−1`, `2⁶⁴` or `True`, **THEN** it raises `RngError`. **GIVEN** a generator after `close()`, **WHEN** any draw is made, **THEN** it raises `RngError`, and a second `close()` raises nothing. **Accepted, no error:** a key of exactly 16 components; domains 1 and 18; `RngFactory(0)` and `RngFactory(2⁶⁴ − 1)`. *(R3, R4, R5, R9, API Contract.)*
- **AC-09** — unique-key tracking:
  - **GIVEN** `RngFactory(42, assert_unique_keys=True)`, **WHEN** `derive(1, [7, 3, 0])` is called twice, **THEN** the second call raises `RngError` whose message contains `domain=1` and `[7, 3, 0]`.
  - **WHEN** the same key is derived once each on two separate factories (a save and a reload), **THEN** neither raises and both generators produce identical draws. *(R11 replay from key.)*
  - **WHEN** key `[7, 3, 0]` is derived in domains 1 and 2 on one tracking factory, **THEN** neither raises.
  - **GIVEN** `assert_unique_keys=False`, **WHEN** the same key is derived twice, **THEN** nothing raises and both generators produce identical draws.
  - **GIVEN** a tracking factory whose cap is lowered to 3 by `key_cap=3`, **WHEN** four distinct keys and then a repeat of the first are derived, **THEN** one warning naming the cap is logged and nothing raises.
  - Which build profile passes which flag is a smoke check (`/smoke-check`), not a unit test.

  *(R6, API Contract.)*
- **AC-10** — world seed creation:
  - **GIVEN** `entropy_fn` returning `0x0123456789abcdef`, **WHEN** `new_world_seed(entropy_fn, clock_fn, install_id=7)` is called, **THEN** it returns `(0x0123456789abcdef, false)` and `clock_fn` is not called.
  - **GIVEN** an `entropy_fn` that raises, `clock_fn` returning `1000` and `install_id = 7`, **THEN** it returns `(mix(1000 ^ 7), true)` = `(0xe637bb4c9e7d0985, true)`. The same result follows *(Python only)* from an `entropy_fn` returning `None`, `−1` or `2⁶⁴`.
  - **GIVEN** an `entropy_fn` that raises and `install_id = None`, **THEN** the call fails (R9) and returns no seed.
  - **Integration, [PENDING: needs the Local save (6) implementation]** The save records the `used_fallback` flag in its `seed_used_fallback` envelope field (Local save, envelope).

  *(R2, Edge Cases.)*

**Derived draws (F3–F6, R8, R9)**
- **AC-11** — **GIVEN** a generator whose next raw draw is `0x3369385d`, **WHEN** `random()` is called, **THEN** it returns `0.20082428236491978`; **GIVEN** raw draws `0x00000000` and `0xffffffff` (injected), **THEN** `random()` returns `0.0` and `1 − 2⁻³²` respectively and never `1.0`. *(F3 typical and both boundaries.)*
- **AC-12** — **GIVEN** a fresh F2 example generator, **WHEN** `randint(1, 6)` is called five times, **THEN** the results are `2, 3, 4, 1, 6`. **GIVEN** a fresh F2 example generator, **WHEN** `randint(−3, 3)` is called, **THEN** the result is `−2` and one draw was consumed. *(F4 golden vector and a negative lower bound.)*
- **AC-13** — **GIVEN** the F2 example generator, **WHEN** `randint(3, 7)` is called 100,000 times, **THEN** every value 3–7 appears and each count is within 700 of 20,000 (3.5%, about 5.5σ; measured maximum deviation 162). **WHEN** `randint(9, 9)` is called, **THEN** it returns 9 and the generator has advanced by exactly one draw. **WHEN** `randint(0, 2³² − 1)` is called with injected raw draws `0` and `0xffffffff`, **THEN** it returns `0` and `2³² − 1` with no rejection. *(F4 uniformity and the n = 1 and n = 2³² boundaries.)*
- **AC-14** — rejection path of `randint(0, 3·2³⁰ − 1)`:
  - **GIVEN** the F2 example generator, **WHEN** it is called 100,000 times:
    - the fraction of calls whose `draws_consumed` rose by more than one is between 24% and 26% (measured 25.013%)
    - total `draws_consumed` minus 100,000, divided by 100,000, is between 0.318 and 0.348 (measured 0.33351)
    - no returned value is outside the range
  - **GIVEN** injected raw draws `[4, 1]`, **THEN** the first is rejected (`l = 0 < t = 2³⁰`), exactly two draws are consumed, and the result is `(1 · 3·2³⁰) >> 32` = 0. **GIVEN** injected raw draws `[0xffffffff]`, **THEN** one draw is consumed and the result is `3·2³⁰ − 1`.

  *(F4 rejection rate, a deterministic rejection, and the value returned after it.)*
- **AC-15** — **GIVEN** calls `randint(5, 3)`, `randint(0, 2³²)` (n = 2³² + 1), `randint(−2⁶³, 2⁶³ − 1)` and `choice([])`, **WHEN** each is made, **THEN** each raises `RngError` and returns no value. *(Python only)* `randint(1.5, 3)` and `randint(True, 3)` raise `RngError` too. `randint(−2⁶³, 2⁶³ − 1)` is the signed-wrap case (`d = −1`, F4). Python's ints do not wrap, so there it only proves the `d > 4,294,967,295` test. The engine port's suite must include the same call, where it proves the `d < 0` test. The port's tests inject a recording fatal sink and check that it fired, that the call returned the poison value, and that the generator is closed (API Contract). They never rely on `assert`. *(F4, F5, R9.)*
- **AC-16** — `chance_ppm` and `chance`, each called as the first draw of a fresh F2 example generator, whose first raw draw is `0x3369385d` (`random()` would return 0.2008…):
  - **WHEN** `chance_ppm(250000)`, `chance_ppm(200000)`, `chance_ppm(0)` and `chance_ppm(1000000)` are called, **THEN** they return `true, false, false, true`.
  - **WHEN** `chance(0.25)`, `chance(0.2)`, `chance(0)`, `chance(−1)`, `chance(−inf)`, `chance(1)`, `chance(5)` and `chance(+inf)` are called, **THEN** they return `true, false, false, false, false, true, true, true`.
  - Every one of these calls advanced the generator by exactly one draw.
  - **GIVEN** an injected raw draw `0x40000000` (exactly 0.25), **THEN** `chance(0.25)` and `chance_ppm(250000)` both return `false` (strict less-than).
  - **GIVEN** injected raw draws, **THEN** `chance_ppm(1)` is `true` on `4293` and `false` on `4294` (T(1) = 4294, rounds down), and `chance(2⁻³²)` is `true` on `0` and `false` on `1` (rounds up). `chance(−0.0)` is `false`.
  - **WHEN** `chance(NaN)`, `chance_ppm(−1)` or `chance_ppm(1000001)` is called, or *(Python only)* `chance_ppm(2.5)`, **THEN** it raises `RngError`.

  *(F6 typical, boundaries, draw-count rule, strictness, invalid input.)*
- **AC-17** — **GIVEN** the F2 example generator and a list of five element `uid`s sorted by `uid`, **WHEN** `choice` is called 50,000 times, **THEN** each element's count is within 500 of 10,000 (5%, about 5.6σ; measured maximum deviation 128). **GIVEN** a one-element list, **THEN** `choice` returns that element and consumes one draw. *(F5 uniformity and the single-element boundary.)*

**Saving, replay and cross-system (R7, R11, R12)**
- **AC-18** — **Integration, [PENDING: needs Sim core (1), Local save (6), per-event seeding]** — **GIVEN** a guild simulated for 2 hours of game time with a fixed `world_seed` and command log, saved, then loaded and simulated for a further 2 hours, **WHEN** the final state is compared with an uninterrupted 4-hour run from the same seed and commands, **THEN** the serialised states are byte-identical (or their state hashes are equal).
  - Each 2-hour half makes at least 100 `derive` calls (`factory.derive_count`), so the test cannot pass on a fixture with no randomness.
  - **Negative control:** a variant that zeroes one saved ordinal counter before the load must give a different final state hash.

  *(R11; also catches the "counter not saved" duplicate-key bug that tracking cannot see across a load.)*
- **AC-19** — **Integration, [PENDING: needs Combat (10) to decide whether fights span ticks; if fights stay atomic within one tick this criterion is retired]** — **GIVEN** a save taken while a fight is in progress, **WHEN** it is loaded and the fight completes, **THEN** the fight's outcome equals the outcome of the same fight in an uninterrupted run. *(Edge Cases: mid-event save.)*
- **AC-20** — **Integration, [PENDING: needs Equipment enhancement (24), Local save (6)]**
  - **(a) Same attempt after a reload.** **GIVEN** a save taken just before an enhancement attempt, **WHEN** the attempt is made and its `(domain, key)`, `event_seed` and first draw are recorded, **AND** the save is reloaded, one named unrelated action (selling one item) is performed, 60 seconds of game time pass and the same enhancement is attempted, **THEN** the second attempt has the same `(domain, key)`, `event_seed`, first draw and outcome.
  - **(b) Negative control.** **WHEN** the next attempt on the same item is made (attempt ordinal + 1), **THEN** its `event_seed` differs from attempt (a)'s. A key that ignores the ordinal fails here.
  - **(c) Changed inputs, same dice.** **GIVEN** a save taken just before a hunt, **WHEN** the first fight's `event_seed` and first draw are recorded in a run with the party's equipment unchanged and in a run where one member's weapon was swapped after the reload, **THEN** both runs have the same `event_seed` and first draw for that fight.

  *(Edge Cases: save-scumming; R5 no player-mutable state in keys.)*
- **AC-21** — **[PENDING: needs the Godot 4.7 GDScript core port and its parity runner (Dev tooling R14)]** — **GIVEN** the golden-vector file produced by Dev tooling (43) from the Python reference (AC-01, AC-04, AC-05, AC-11–AC-16 inputs and outputs), **WHEN** the engine implementation runs the same inputs, **THEN** every integer and boolean output matches exactly and every float matches bit for bit. Error cases are in the file with an `error` marker in place of an output, and only for inputs both ports can express (R5). The file includes the GDScript spelling `[−1]` of the key `[2⁶⁴−1]` with the same expected seed. *(R12.)*
- **AC-22** — **[PENDING: needs Dev tooling and parity harness (43)]** — **GIVEN** the golden-vector file, **WHEN** a draw is added, removed or reordered inside any event type that has vectors in that file and the parity harness runs, **THEN** it fails until the sim version is bumped and the vectors are regenerated. Each event type that draws must have at least one vector in the file. *(R7.)*

**Performance**
- **AC-23** — Gating, structural and deterministic:
  - **GIVEN** a factory, **WHEN** one event generator with a key of length n (n = 1, 3, 16) is derived, **THEN** `factory.mix_calls` rose by at most n + 3 (an implementation may cache `mix(domain_id)`), the seed equals the F2 value, and `rng.draws_consumed` is 0. So the two `pcg32_init` steps are not counted and no extra draw was taken before the caller's first.
  - **[PENDING: needs Sim core (1), Zones and hunt (11), Combat (10)]** **GIVEN** the fixture `tests/fixtures/hunt_24h_5m.json`, which records its expected `random_events` count (fights + drop rolls + encounters), **WHEN** it is simulated, **THEN** `factory.derive_count` equals `random_events`, and the total `draws_consumed` across events exceeds it.

  Non-gating: a benchmark records derive cost against one `next_u32` (Python 2026-11-16: 2.78 µs vs 0.36 µs, ratio 7.7) and is reported, not asserted. Advisory, on target hardware once the engine exists: absolute µs per derive, compared with the offline fast-forward budget (≤ 1 second for 24 hours, `GODOT_PORT.md`), which Offline progress (31) owns. *(Per-event seeding must not turn into per-draw seeding.)*

**Registry and API surface (R4, R8)**
- **AC-24** — **GIVEN** the code's domain registry, **THEN** it contains exactly IDs 1–18 with the R4 names, all unique, `derive` accepts each, and each generator's stream `seq` equals its domain ID. **GIVEN** the public members of `EventRng`, **THEN** they are exactly `next_u32, random, randint, choice, chance_ppm, chance, close, event_seed, draws_consumed`. *(R4, R8.)*
- **AC-25** — **GIVEN** two factories with `world_seed = 42`, **WHEN** draws on `derive(1, [7, 3, 0])` from the first are interleaved with draws on `derive(2, [5])` from the second, **THEN** each sequence equals the same draws taken alone. *(API Contract: no global state.)*

*QA lens applied (`references/lens-qa-lead.md`; revised after the second `/design-review` 2026-11-16).* Coverage check: F1–F6, R1, R3–R9, R11, R12 and the API Contract each have at least one criterion. R2 seed immutability across save and load belongs to Local save (6) (OQ-4). R10 is delegated to the owning GDDs (gap 3). Boundary values are tested for F1–F6, including the 16-component key. Cross-system criteria are tagged Integration and PENDING with the system they wait for. **Known gaps:**
1. AC-21 cannot run until the Godot core port exists; AC-22 until the parity harness exists.
2. Today's `sim/rng.py` passes only AC-01, AC-02 and the uniformity parts of AC-13 and AC-17. Everything else needs the OQ-1 migration.
3. R10 (no rigging) and the R5 "no player-mutable state" rule cannot be verified by a test of this system alone. Each consuming system's GDD must carry a criterion that its luck modifiers change only draw inputs, and that its key has no player-mutable component.
4. R8 ("no other derived draw") is enforced by code review of the RNG module, not by a test.

## Open Questions

| # | Question | Owner | Resolve by |
|---|---|---|---|
| OQ-1 | **Migrating `sim/rng.py` to this spec.** The code today uses one shared generator passed through every call, an unused `fork()`, and `randint` without rejection. Moving to per-event seeding (R3, F2) and exact `randint` (F4) changes every simulated outcome once, so `balance_sim` and `calibrate` must be re-run and the §4.3 and §18 numbers in `JX1_Tycoon_GDD.md` re-measured. The order: implement F2 and F4 with tests, switch all call sites in one change, then recalibrate. Old `randint` gives the same value as F4 on every draw that is not rejected, so only the streams change, not how a draw maps to a value. Known hazards: (a) old `randint(b < a)` silently returns `a`, but R9 makes it fatal, so audit `sim/hunt.py:91` (CSV `qty_min`/`qty_max`); (b) `hunt.py` and `raid.py` thread one generator through a whole run, so splitting them into R3 events is a redesign of those loops, not a rename; (c) `rng.random() < tank_aggro_share` uses a float config probability, so convert it to ppm or justify `chance()`; (d) `drop_tables.csv` still has a float `chance` column, which must become `_ppm` (Data layer); (e) tests that build `PCG32(n)` directly move to factory + domain + key and are re-baselined; (f) delete `fork()`. | Implementation (story for this GDD) + Dev tooling (43) | Before Combat (10) implementation starts |
| OQ-2 | **RESOLVED by Leaderboards and anti-cheat (35), Edge Cases:** seed shopping is accepted, with one ranked guild per account and a new guild ending the old chain (Leaderboards R10). | Leaderboards and anti-cheat (35) | Closed |
| OQ-3 | **Event-key layouts** for each of the 18 domains, with their uniqueness arguments (R5, R6). This GDD sets the rules; each owner writes its own. | Each owning system's GDD | As each GDD is written |
| OQ-4 | **RESOLVED by Local save and migration (6):** `world_seed` travels in the core snapshot, and the envelope field `seed_used_fallback` stores the `used_fallback` flag. | Local save and migration (6) | Closed |
| OQ-5 | **RESOLVED 2026-11-16: the engine is Godot 4.7, GDScript** (`project.yaml`), so the signed-64-bit port rules above apply and AC-21 runs through Dev tooling R14. The rest of this row is kept for a possible later web port only. Engine choice decides how AC-21 runs and which integer-width pitfalls the port faces. A web/TypeScript port needs its own port rules: `BigInt` with `BigInt.asUintN(64, …)` (JS `Number` is exact only to 2⁵³, and `>>`/`>>>` are 32-bit), `BigInt` key components, and the world-seed hex helpers. Its derive cost must then be measured against the offline budget, which AC-23 does not gate. | `/setup-engine` (user) | Before Architecture |
| OQ-6 | **Commit points for player gambles.** Fixed dice can be probed by reloading with different inputs (Edge Cases, accepted). Should Enhancement (24), Recruitment (15) and Crafting (28) consume and save their attempt ordinal when an attempt is dispatched? | Each gamble GDD | As each GDD is written |
