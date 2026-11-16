# Dev Tooling and Parity Harness

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (design-system)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no pillars written yet)
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game-pillars.md, game-concept.md or game-brief.md to check against

## Summary

Dev tooling and the parity harness are the headless checks that stop a bad change from merging: the content validator, the balance simulator and its budget, the content generators, and the golden vectors that prove the Python reference and the future engine port give the same answers. Three gate classes (static, determinism, balance) run through `make gate` and a CI workflow, with exit codes 0 (pass), 1 (fail) and 2 (could not assess, which also blocks). The Data layer owns what the validator checks and the RNG owns what must match; this system owns running them and keeping the vectors honest.

> **Quick reference** — Layer: `Foundation` · Priority: `MVP` · Key deps: `Deterministic RNG (2), Data layer and content pipeline (3)`

## Overview

Dev tooling and the parity harness are the checks that stand between a change to the game's numbers or code and a build that ships: the content validator, the balance simulator and its calibrator, the CSV generators, the one-command local checks (`make check`), and the cross-implementation parity harness. The Python reference core in `sim/` and the future engine port must produce identical results from the same seed and the same data. The harness proves that with golden vectors that this system generates from the Python reference, and it runs them against the engine implementation as a gate that fails the build. The same system also guards the numbers. It runs the balance simulator with fixed seeds, compares its output to a budget of thresholds, and fails when a change pushes pacing, income or boss difficulty out of range (GDD §4.4 and §20 S9). All of it runs headless from the command line and in CI, with no player interface. The Data layer owns the schema and the validator's rules, and the RNG owns what must match. This system owns the tools, the vector files, the budget and the gates that run them. Without it, a parity break shows up as a leaderboard replay that disagrees with a player's phone, and a balance break shows up as a player who finds a gold loop before the designer does.

**Conventions this GDD uses.** A *golden vector* is a recorded input and its exact expected output, generated once from the Python reference and stored in a file. A *gate* is a check whose failure blocks a merge or an export. *Reference side* means the Python implementation in `sim/`. *Port side* means the engine implementation, which does not exist yet because no engine is chosen.

## Player Fantasy

**Indirect.** Players never see this system. The developer feels two of its promises directly, and the player feels the third without knowing it exists. Each promise rests on a locked line of `JX1_Tycoon_GDD.md` or `GODOT_PORT.md`. There are no game pillars yet, so none is quoted. Re-anchor these once `design/gdd/game-pillars.md` exists.

**1. "I can change a number and know what it did."** The designer edits a value in `sim_params.csv`, runs `make balance`, and within a minute a pass/fail table says whether the standard five-member party still reaches level 100 inside its budgeted window and whether gold income still sits inside its band. The anchor is §4.4: *"Mỗi lần đổi bảng số phải chạy trước khi commit"* (every change to the number tables must be run before committing). The design must therefore make the run fast enough to do before every commit, make the budget an executable table that can fail, and print each result next to its threshold.

**2. "The port is the same game."** The first engine build runs the golden vectors and every one matches. Months later someone adds one random draw inside a combat event, and the gate fails and names the event and the first draw that diverged, before the change merges. The anchors are `GODOT_PORT.md` rule 2, *"Thứ tự rút số ngẫu nhiên phải giữ nguyên"* (the order of random draws must be kept), and §3.2, one deterministic core shared by every consumer. The design must therefore cover every event type that draws, treat a vector change as a deliberate versioned act, and report where outputs diverge, not only that they did.

**3. "The player never meets the bug."** The morning after a patch the player reads the offline report and checks a leaderboard rank, and both are honest. The player never learns that a gate stopped a bad build. The anchors are §3.2 and §8.1, where a server replays signed summaries with the deterministic core. The design must therefore run the gates in CI where a merge cannot skip them, and report a check it could not run as NOT ASSESSED, never as a pass.

What breaks each promise: a budget that never fails, or a run too slow to do before a commit, breaks 1; a vector file that is regenerated to make a failing test pass, or an event type with no vectors, breaks 2; a gate that is local-only, optional or silently skipped breaks 3. Sections C and E are written against those three failures.

## Detailed Design

### Core Rules

**Terms.** A *tool* is a headless command-line program under `tools/`. A *gate* is a check whose failure blocks a merge or an export. A *golden vector* is a recorded input and its exact expected output. The *reference side* is the Python implementation in `sim/`; the *port side* is the engine implementation, which does not exist yet. A *budget row* is one line of the balance budget: a metric, the scenario that produces it, and the band it must stay inside.

**R1 — Tool inventory.** This system owns these tools. Rules about the data they check belong to the Data layer (3) and the RNG (2); this system owns running them.

| Tool | Exists | Job |
|---|---|---|
| `tools/content_validator.py` | yes | Static content checks. Rules and tiers are owned by the Data layer (R8) |
| uid helper | no | Assigns `uid = max + 1` to rows with an empty `uid`. Rule is Data layer F4; this system owns the command |
| `tools/parity.py` | no | Generates, checks and reports on golden vectors (R4–R8) |
| `tools/balance_sim.py` | yes | Runs the headless core on fixed seeds and emits metrics (R10) |
| `tools/validate_balance.py` | no | Compares those metrics with the budget and fails on a breach (R9; GDD §20 S9) |
| `tools/calibrate.py` | yes | Sweeps parameters to find a stable combat rhythm (R11) |
| `tools/gen_a.py`, `gen_b.py`, `gen_c.py` | yes | Content generators, authoring aids only (R12) |
| `tests/` suite | yes | Unit tests of the reference core, run by `make test` |
| `Makefile` and `.github/workflows/gate.yml` | Makefile yes, workflow no | The one-command surface and its CI wrapper (R2, R13) |

**R2 — Three gate classes and one command surface.** Every check belongs to exactly one class, and each class has a command:

| Class | Command | What it covers | Target time |
|---|---|---|---|
| Static | `make validate` | Validator over `data/` and `i18n/` | ≤ 5 s |
| Determinism | `make test` and `make parity` | Unit tests; golden-vector check on the reference side | ≤ 30 s together |
| Balance | `make balance-quick` (gate) and `make balance` (full, advisory) | Budget rows run on fixed seeds | quick ≤ 60 s; full unbounded, run nightly |

`make check` runs static and determinism. `make gate` runs `check` and then `balance-quick`; `gate` is what CI runs and what a developer runs before committing. Measured today on the Python reference: `make check` takes 1.0 s (0 validator errors, 22 tests) and `make balance-quick` takes 29 s, so both targets hold with room to grow.

**R3 — Exit codes.** Every tool exits `0` for pass, `1` for a failed check and `2` for NOT ASSESSED, meaning the check could not run (no git checkout, a missing input file, a vector file for a different `vector_schema`). Exit `2` fails the gate. A tool never reports a pass for a check it did not run, and it names the check it could not run.

**R4 — Tools are headless and deterministic.** A tool reads only `data/`, `i18n/`, `tools/` budget files, `tests/parity/` and git. It writes only to `out/` (not committed) and, for generators and the uid helper, to `data/`. It uses no wall clock, no network, no unseeded randomness, and the project's PCG32 for every random draw. Run twice with the same inputs, it prints the same output. Tools are run as `python3 -I`, so a stray module in the working directory cannot be imported. Tools may import `sim/`; `sim/` never imports `tools/`.

**R5 — Golden-vector files.** Vectors live in `tests/parity/vectors/`, one JSON file per group: `rng`, `event_seed`, `randint`, `choice`, `chance`, `loader`, and one per event type with draws (R8). Each file has a header `{vector_schema, sim_version, generated_by, group}` and a list of vectors `{id, ac, inputs, outputs}`, where `ac` names the acceptance criterion it proves. Encoding rules, so that no value passes through a lossy number type:
- Every `u64` and `i64` is a string of the form `"0x…"` (16 hex digits for `u64`). It is never a JSON number, because a JSON number is a double and cannot hold 2⁶⁴ − 1, and a GDScript `int` is signed.
- Every `float` output is stored as its IEEE-754 binary64 bit pattern in hex, plus a decimal copy for human readers. Only the hex is compared.
- Lists keep their order; a draw sequence is a list, never a set or a map.
- Strings are UTF-8, keys are sorted, and the file ends with one newline, so a regenerated file with no real change produces no diff.

**R6 — Vectors come from the reference and nowhere else.** `tools/parity.py gen` is the only writer of vector files. It runs the reference implementation on inputs declared in the generator and records the outputs. Nobody edits a vector file by hand, and a pull request that changes one without a changed `sim_version` is rejected by R7. The generator's inputs include the vectors fixed in the RNG GDD (AC-01 `pcg32_init(42, 54)`, AC-05 `event_seed`, AC-11 to AC-16), so the files start from known-correct values, not from whatever the code happens to output.

**R7 — The reference-side check and the version rule.** `tools/parity.py check` recomputes every vector from the live reference and compares it with the file. A mismatch is reported as the vector `id`, its `ac`, the first differing field, and the expected and actual values, and for a draw sequence the index of the first draw that differs. The outcome depends on `sim_version`:

| Vectors match | `sim_version` equals the file's | Result |
|---|---|---|
| yes | yes | Pass |
| no | yes | **Fail: breaking change without a version bump.** This is RNG AC-22 (a draw added, removed or reordered) |
| no | no | **Fail: vectors stale.** The version was bumped, so run `parity.py gen` and review the diff |
| yes | no | **Fail: version bumped but behaviour unchanged.** Bumping without a behaviour change invalidates saves and leaderboard replays for nothing |

The only way to a pass after a deliberate behaviour change is to bump `sim_version` and regenerate, in the same change, so the diff shows both. `sim_version` is one integer. Its owner is Sim core (1); that GDD does not exist yet, so Sim core R12 now confirms it (see Dependencies).

**R8 — Event coverage.** Every event type whose draws change a game outcome has at least one vector group. `tools/parity.py coverage` runs each reference event with a recording generator, lists the RNG domains (RNG R4, 18 today) that drew at least once, and compares them with the vector groups present. A domain that draws in the reference but has no vector group is an ERROR. A domain with a vector group but no reference code is a WARN, because the event may be retired. So adding a new random event to the reference cannot pass the gate until it has vectors, which is the guarantee that RNG R7 (draw order is a contract) depends on.

**R9 — The balance budget.** The budget is `tools/balance_budget.csv`. It is not under `data/`, because the Data layer fails any CSV in `data/` that is not in its table inventory (`unknown table`), and the budget is not game content. Columns: `id`, `tier` (`quick` or `full`), `scenario`, `metric`, `min`, `max`, `source`, `notes`. `source` cites the GDD section or formula that justifies the band (Design Document Standards: balance values must link to a rationale). `validate_balance.py` runs the scenarios, reads each metric from the simulator's result rows, and prints one line per budget row: the value, the band, and PASS or FAIL. Any FAIL exits 1. A budget row whose metric the simulator did not produce is a FAIL, never skipped. The gate runs rows with `tier = quick`; `make balance` runs all rows and is advisory.

**R10 — The simulator is a function, not a script.** `balance_sim` today runs its scenarios when imported, parses `sys.argv` at module level, and writes the Markdown report to a hard-coded `out/`. Before the budget gate can exist it must expose a callable that takes a scenario and returns its metric rows as data, with the Markdown report and `out/balance_summary.csv` produced from those rows afterwards. Scenario inputs (party composition, PA, seeds, duration) are declared with the budget rows and not in the script, so changing a scenario is a data edit. A scenario's seeds are fixed in its declaration; two runs of one scenario return identical metrics.

**R11 — The calibrator reports; it never writes.** `calibrate.py` sweeps `monster_hp_exp` and `monster_dmg_factor` against the targets in GDD §4.3 and §18 (8–16 kills per trip, death rate under 3%, 6–25 s to kill one monster) and prints candidate values. It writes nothing into `data/`. The designer copies a chosen value into the CSV by hand, then runs the gate. Its targets are also budget rows, so the same numbers are enforced after calibration.

**R12 — Generators are authoring aids, never gates.** `gen_a.py` overwrites its output on every run, and `gen_b.py` and `gen_c.py` are idempotent. Generators are never run by `make gate` or CI. A generator refuses to overwrite a `data/` file that differs from git `HEAD` unless given `--force`, so an uncommitted hand edit cannot be lost silently. Whatever a generator writes goes through the validator like any hand-written row (Data layer R1).

**R13 — CI wrapper.** `.github/workflows/gate.yml` runs `make gate` on every push to `main` and on every pull request, and a failing or NOT ASSESSED gate blocks the merge. The checkout fetches at least two commits, because the validator compares `uid` pairs against `HEAD` (Data layer R6); a shallow clone that cannot see `HEAD` yields exit `2`, not a pass. Tests are never skipped or disabled to make a gate pass. The engine-side parity job (R14) is a separate workflow that is added when an engine exists.

**R14 — The port-side contract.** The engine implementation provides one runner that reads the same vector files, computes each vector's outputs with the port's own code, and writes a result file in the same schema. `parity.py compare` diffs a result file against the vectors with the same reporting as R7. Everything above that line is defined and testable today. The runner itself is not, because no engine is chosen. RNG AC-21 stays pending until it exists, and until then the reference-side check (R7) is the only parity gate. The loader group of vectors (F1 `content_hash`, the row count of every table, and one canonical sample row per table, as the Data layer's Edge Cases require) is generated by the reference loader and compared the same way.

**R15 — Developer hot-reload.** The Data layer allows a reload only in dev tooling and only between runs (Data layer R10). A tool that reloads content restarts its simulation from tick 0 with the new tables and a fresh seed. It never changes tables under a running world, and the shipped build contains no reload path.

### States and Transitions

A tool run has one state machine. A vector file has a separate status derived from R7.

| Run state | Meaning |
|---|---|
| `Idle` | No run in progress |
| `Running` | Checks executing |
| `Passed` | Every check ran and passed; exit 0 |
| `Failed` | At least one check ran and failed; exit 1 |
| `NotAssessed` | At least one check could not run and no check failed; exit 2. A run with both failures and unrunnable checks is `Failed` (exit 1) and lists the unrunnable ones |

| From | To | Trigger |
|---|---|---|
| `Idle` | `Running` | A command from R2 starts |
| `Running` | `Passed` | All checks ran, none failed |
| `Running` | `Failed` | Any check failed |
| `Running` | `NotAssessed` | A check could not run and no check failed |
| `Passed`, `Failed`, `NotAssessed` | `Idle` | The process exits; there is no state between runs |

| Vector file status | Condition | Fix |
|---|---|---|
| `Current` | Matches the reference, version equal | None |
| `Diverged` | Mismatch, version equal | Revert the code change, or bump `sim_version` and regenerate |
| `Stale` | Version differs from the code's | Run `parity.py gen` and review the diff |
| `Orphaned` | Version bumped, behaviour identical | Revert the bump, or confirm a behaviour change was intended |

### Interactions with Other Systems

| System (#) | Direction | Data / contract | Owner of the interface |
|---|---|---|---|
| Deterministic RNG (2) | RNG → this | Fixed seeds, domain IDs and keys; the correct outputs for AC-01, AC-04, AC-05 and AC-11 to AC-16 | RNG defines what must match; this system owns the files and the gate (RNG AC-21, AC-22) |
| Data layer and content pipeline (3) | both | The validator, the shared schema, the F1 hash, the uid helper's rule (F4) | Data layer owns the rules and checks; this system owns running them and the CI wrapper |
| Sim core and tick loop (1) | Sim core → this | `sim_version`; the single entry the simulator and harness call | Sim core owns the version (Sim core R12, resolved); this system records it in each vector file, together with `phase_table_hash` (Sim core F5) |
| Local save and migration (6) | save → this | A save stamps `sim_version` and F1; the harness uses both to decide whether an old save's replay is comparable | Save owns the stamp |
| Leaderboards and anti-cheat (35) | server → this | The server replays a submission with the core at the submission's `sim_version`; the vector files are the proof the server's core still matches | Leaderboards owns the replay; this system owns the proof |
| Every system whose events draw (10, 11, 12, 14, 15, 9, 24, 16, 28, 17, 19, 18, 25, 26) | owner → this | Each adds a vector group for each event it defines (R8) | The owning system defines the draw order; this system stores and gates it |
| Offline progress (31) and Zones and hunt (11) | both | A parity test of the aggregate resolver against the exact one (index TD note); runs in the determinism class | Offline owns the tolerance; this system runs it |
| Localization (4) | this reads | The validator's name-coverage check reads `i18n/names_*.csv` | Localization owns the text |
| Git and the CI host | this reads | `HEAD` for the `uid` check; the workflow runner | Tooling, not a game system |

## Formulas

Five formulas. They define how a metric passes the budget, how a run's exit code is chosen, how a parity value is encoded and compared, which RNG domains are uncovered, and how long the gate may take. Every comparison is exact integer or bit comparison except F1, which compares a metric with a band the designer chose.

### F1 — Budget band check

The budget_pass formula is defined as:

`budget_pass(row) = (m ≠ null) ∧ (lo ≤ m) ∧ (m ≤ hi)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| m | float or null | any finite float, or null | calculated | The metric the scenario produced. `null` means the scenario did not produce it (for example a level the party never reached) |
| lo | float | finite, `lo ≤ hi`; time, count and rate metrics need `lo ≥ 0` | data file (`balance_budget.csv` `min`) | Lower bound of the band |
| hi | float | finite, `hi ≥ lo` | data file (`balance_budget.csv` `max`) | Upper bound of the band |

**Output range:** true or false. `null` is always false. The budget file itself is validated before any scenario runs: a row with `lo > hi`, a non-finite bound, or a negative `lo` on a time, count or rate metric is an ERROR (exit 1).

**How a designer picks the band.** `lo = T · (1 − t_lo)` and `hi = T · (1 + t_hi)`, where `T` is the target the GDD states and `t_lo`, `t_hi` are tolerances (default 0.15, from the ±15% the GDD uses for skill DPS in §20 S4; ±20% where §20 S6 says so). Only `lo` and `hi` are stored, with `source` naming `T` and its section. The bands are wide on purpose: scenario seeds are fixed (R10), so a run never fails by chance. A fail means the design moved.

**Boundary check:** at `m = lo` and `m = hi` the row passes (inclusive). At `lo = hi` the band is a single value, which is legal for an integer count (such as the 3 backlogged bosses of §20 S7). **Found problem:** `balance_sim.py` today writes `-1` for "level not reached" (`ms.get(t, -1)`). `-1` is a finite number, so a band with `lo ≤ -1` would pass it, and a row with a bad `lo` like `0` would fail it only by accident. **Resolution applied:** the simulator must emit `null` (an empty cell in `out/balance_summary.csv`) for "not produced", and the budget validator rejects `lo < 0` for time metrics, so `-1` can never sit inside a band.

**Example:** budget row `party5_pa100_lv100_hours`, `lo = 60.4`, `hi = 81.6`, source §18.2 (target 71 h, ±15%). A run that returns `m = 71.3` passes. A change that makes the party slower, `m = 94.0`, fails. A run where the party never reaches level 100 returns `m = null` and fails. *(Values are illustrative; the real band is set when the budget file is authored, from a fresh run.)*

### F2 — Exit code of a run

The exit_code formula is defined as:

`exit_code = 1 if n_fail > 0, else 2 if n_unrunnable > 0, else 0`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n_fail | int | 0 – N | calculated | Checks that ran and failed |
| n_unrunnable | int | 0 – N | calculated | Checks that could not run (R3) |
| N | int | ≥ 1 | calculated | Checks the command is defined to perform |

**Output range:** 0, 1 or 2. A run that performs zero checks (`N = 0`) is itself `NotAssessed` (exit 2), so an empty budget file or a vector directory with no files cannot pass. Failure outranks unrunnable, and unrunnable outranks pass, as `.claude/rules/skill-authoring.md` requires.

**Example:** `make gate` with 31 checks where 29 pass, 1 fails and 1 could not run (shallow clone, `uid` check) exits 1, and its output lists the unrunnable check by name below the failure.

### F3 — Parity value encoding and comparison

The parity_equal formula is defined as:

`enc_u(x) = "0x" + hex16(x mod 2⁶⁴)` and `enc_f(x) = "0x" + hex16(bits64(canon(x)))`, and two values are equal when their encoded strings are equal.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| x (integer) | int | −2⁶³ … 2⁶⁴ − 1 | calculated | A `u64` or `i64` output; a negative `i64` is encoded as its two's-complement `u64` |
| x (float) | float | any binary64 | calculated | A float output |
| bits64 | function | 0 … 2⁶⁴ − 1 | constant | The IEEE-754 binary64 bit pattern, big-endian |
| canon | function | — | constant | Maps every NaN to `0x7ff8000000000000`. `+0.0` and `−0.0` stay distinct |
| hex16 | function | 16 lowercase hex digits | constant | Zero-padded |

**Output range:** a 18-character string `0x` + 16 hex digits. Comparison is string equality; there is no tolerance, because a 1-ulp difference can flip a later draw.

**Boundary check:** `x = 0` encodes as `0x0000000000000000`; `x = 2⁶⁴ − 1` as `0xffffffffffffffff`; `x = −1` (`i64`) also as `0xffffffffffffffff`, so a vector's declared type, not its bits, says which it is. `x = 2⁶⁴` is an ERROR in the generator, not wrapped. A NaN never appears in a vector (a NaN output is a defect and fails generation). `−0.0` and `+0.0` are compared as different.

**Example:** `enc_f(0.1) = "0x3fb999999999999a"`, `enc_f(1.0) = "0x3ff0000000000000"`, `enc_f(−0.0) = "0x8000000000000000"`, `enc_u(2⁶⁴ − 1) = "0xffffffffffffffff"`. The pcg32 vector for seed 42, sequence 54 begins `0xa15c02b7` as a `u32`, encoded `0x00000000a15c02b7`.

### F4 — Version-rule verdict

The version_verdict formula is defined as:

`verdict = Pass if (match ∧ same_ver); Diverged if (¬match ∧ same_ver); Stale if (¬match ∧ ¬same_ver); Orphaned if (match ∧ ¬same_ver)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| match | bool | true / false | calculated | Every vector in the file equals its recomputed value (F3) |
| same_ver | bool | true / false | calculated | `sim_version` of the code equals `sim_version` in the file header |

**Output range:** one of four verdicts; three of them fail the gate (R7). The table in R7 is this formula spelled out.

**Boundary check:** an empty vector file has `match = true` vacuously, so F2's `N = 0` rule applies and the run is `NotAssessed`. A file with no `sim_version` header is `NotAssessed` as well.

**Example:** a developer adds one `next_u32` call inside `fight`. The vectors for the combat event no longer match, and the version is unchanged: `Diverged`, fail. They bump `sim_version` from 3 to 4 and rerun: `Stale`, fail. They run `parity.py gen` and the file header now says 4 with new outputs: `Pass`.

### F5 — Uncovered domains

The uncovered formula is defined as:

`uncovered = D_draw \ D_vec`, with `ERROR` if `uncovered ≠ ∅`, and `orphan = D_vec \ D_draw` with `WARN` if `orphan ≠ ∅`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| D_draw | set of int | subset of 1 … 18 | calculated | RNG domains that drew at least once while the harness ran each reference event with a recording generator |
| D_vec | set of int | subset of 1 … 18 | calculated | Domains that have at least one vector group |

**Output range:** both sets are subsets of the 18 domain IDs in RNG R4. An empty `D_draw` while `sim/` has events is itself a defect (the recorder did not attach) and gives exit 2.

**Example:** today the reference draws in the hunt, raid and offline events, so `D_draw` contains those domains. Until their vector groups exist, `uncovered` is not empty, and `make parity` fails with the domain numbers named. Authoring the vectors is part of this system's first implementation story.

### F6 — Gate time budget

The gate_time formula is defined as:

`T_gate = T_validate + T_test + T_parity + T_balance_quick`, required `T_gate ≤ T_max`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| T_validate | float (s) | 0 – 5 | calculated | Wall time of `make validate` |
| T_test | float (s) | 0 – 25 | calculated | Wall time of `make test` |
| T_parity | float (s) | 0 – 5 | calculated | Wall time of `make parity` |
| T_balance_quick | float (s) | 0 – 60 | calculated | Wall time of the quick balance gate |
| T_max | float (s) | 90 | data file (`gate_time_max_s` in this system's tuning knobs) | The limit past which developers stop running the gate before commits |

**Output range:** measured, not computed by the tools; a slow run reports a WARN, not a failure, because machine speed is not a design defect. **Measured now:** `make check` = 1.0 s (validate plus 22 tests), `make balance-quick` = 29.3 s, so `T_gate ≈ 30 s` and `T_parity` is not yet measurable. **Boundary check:** if `T_balance_quick` reaches 60 s alone, the rest of the budget is 30 s, which is why the per-class targets in R2 sum to 90.

**Example:** `T_validate = 0.4`, `T_test = 0.8`, `T_parity = 2.0`, `T_balance_quick = 29.3` gives `T_gate = 32.5 s`, inside 90 s.

**Feedback loops.** One positive loop: a slow gate gets skipped, skipped gates miss breaks, breaks make scenarios slower to fix. It is damped by CI (R13), which runs the gate regardless of habit, and by the 60 s ceiling on the quick class. A second loop is intended and damped: each new event system adds vectors and scenarios, which lengthen the gate. F6 is what stops that growth unnoticed.

## Edge Cases

**Runs and exit codes**
- **If the working directory is not a git checkout, or a CI clone is too shallow to see `HEAD`**: the validator's `uid` check reports NOT ASSESSED by name (Data layer, Dependencies), and the run exits 2 per F2. It is never skipped and never a pass. The CI workflow fetches at least two commits (R13) so this does not happen in CI.
- **If a tool crashes with an uncaught exception**: the process exits 1 and prints the traceback. A crash is a failure, not an unrunnable check, because the cause is a defect in the tool and not a missing input.
- **If a command is given an unknown flag or scenario name**: exit 2 with a usage line. It never falls back to a default scenario, because a gate that quietly runs a different check than the one asked for is a silent skip.
- **If two commands run at once on the same checkout**: each writes only to its own file under `out/`, named by the command, and no tool writes into `data/` or `tests/parity/` except the generators and uid helper. Two writers on the same output file is undefined, so `make` is not run with `-j` across the gate classes. The Makefile does not declare them parallel-safe.
- **If `out/` does not exist**: the tool creates it. If it cannot (read-only disk), the run is `NotAssessed` for the report step and the metric checks still run.

**Golden vectors and parity**
- **If a vector file is edited by hand**: the check recomputes from the reference and finds either a mismatch (`Diverged`) or, if the edit was to the version header, `Stale` or `Orphaned`. It cannot pass unless the edited value equals what the reference produces, in which case nothing is wrong.
- **If `parity.py gen` runs and the output differs from the committed file only by key order or whitespace**: it cannot happen, because R5 fixes sorted keys, one trailing newline and UTF-8. Two runs of `gen` on the same code produce byte-identical files; a diff in that case is a defect in the generator.
- **If a vector's output is a NaN**: generation fails with exit 1 naming the vector. A NaN in a game outcome is a defect in the reference, not something to record (F3).
- **If a vector input is outside the RNG's legal range (for example `randint(5, 1)` or `chance_ppm(1,000,001)`)**: it is stored as an *error vector*, `outputs: {"error": "RngError"}`, because RNG R9 makes these errors and the port must raise the same error class (`RngError`). RNG has no error codes, so none are recorded. Cases RNG marks *Python only* (for example a boolean or float argument, or a key longer than 16 components) carry `"python_only": true`; the port-side comparison skips them, as RNG AC-15 allows.
- **If the vector schema version in a file is newer than the tool understands**: exit 2 naming the file and both schema numbers. The tool never reads a file it only partly understands.
- **If the port side produces a result file with a vector `id` the reference does not have, or lacks one it does**: `parity.py compare` fails for each, with the id. A missing result is never counted as a match.
- **If a new event system adds draws but no vector group**: F5 reports the uncovered domain and the gate fails (R8). The fix is vectors, not an allowlist entry; there is no allowlist.
- **If `sim_version` is bumped in a change that also changes the vectors for an unrelated group**: the harness has no way to tell which group's change was intended. All four R7 rows are evaluated per file, so each file shows its own verdict, and the reviewer reads the diff. This is accepted; the cost of a per-group version would be a second source of truth.
- **If RNG is revised after vectors were generated** (RNG is "Needs Revision" at the time of writing): the vectors are `Diverged` or `Stale`, never silently kept. Regenerating them is part of the RNG migration (RNG OQ-1), not of this system.

**Balance budget**
- **If a scenario crashes**: its budget rows are FAIL (F1, metric `null`), and the rows of other scenarios still run, so one broken scenario does not hide the rest.
- **If the budget file has a duplicate `id`, an unknown `tier`, an unknown scenario, or an empty `source`**: ERROR before any scenario runs. An empty `source` is rejected because a band with no rationale cannot be reviewed.
- **If a metric is produced but no budget row names it**: the tool prints it as `unbudgeted` and does not fail. Whether that should fail is an open question (OQ-3).
- **If a designer widens a band to make a failing run pass**: the gate cannot tell. The change appears in the diff of `tools/balance_budget.csv`, which is why the `source` column is mandatory and the file is reviewed like code. CODEOWNERS can require a review for that path; that is a repository setting, not a rule here.
- **If a data change moves a metric outside its band on purpose** (a deliberate re-balance): the same change edits the budget row, citing the new GDD section in `source`. The gate then passes. There is no `--ignore-budget` flag.
- **If the quick run exceeds 60 s on a slow CI machine**: F6 prints a WARN with the time, and the gate result is unchanged. A timeout on the CI job itself (a runner limit) is a job failure outside this system.
- **If `calibrate.py` finds no parameter set meeting its targets**: it prints the closest candidate and the targets it missed, exits 1, and writes nothing. A calibrator that exits 0 with "no solution" would read as success.
- **If the full run (`make balance`) fails a `full`-tier row**: it prints FAIL and exits 1, but CI does not run it on pull requests (R2), so it blocks nothing. The nightly job reports it. A `full` row that has been failing for a long time is a budget row that should be re-examined, not muted.

**Generators and data**
- **If `gen_a.py` is run on a checkout with uncommitted edits to a file it would write**: it refuses and exits 1 naming the file, unless `--force` is given (R12). With `--force` it overwrites, because the developer asked.
- **If a generator writes a row with an empty `uid`**: the validator fails the next run (Data layer R6), and the output tells the developer to run the uid helper. Generators do not assign `uid`s; one place does (Data layer F4).
- **If the uid helper runs on a file with a duplicate `uid`**: it fails and changes nothing. It assigns only `max + 1` to empty cells, and never repairs a conflict.
- **If `data/` contains a CSV outside the table inventory**: the validator fails (Data layer, Edge Cases), so the budget and any scratch CSV must live elsewhere. A scratch CSV left in `data/` fails the gate on purpose.

**CI**
- **If CI is red for a reason outside the tools** (runner outage, network failure fetching the checkout): the job is red and the merge is blocked; the gate does not retry on its own, because a retry that turns red into green on a flaky failure hides a real intermittent defect. A developer re-runs the job by hand.
- **If a pull request changes only documentation**: the gate still runs. Path filters would make a skipped gate and a passed gate look the same on the pull request page, and the gate is about 30 s.
- **If the engine-side parity job does not exist yet**: the reference-side job passes and the pull request says nothing about the port. RNG AC-21 remains `[PENDING]`, named in this GDD's Acceptance Criteria and Open Questions so the absence is visible.

## Dependencies

**Upstream (this system depends on).** Both upstream GDDs exist and both already name this system in their own Dependencies sections, so the two-way record holds for them.

| System (#) | Hard / soft | Interface | What this system takes |
|---|---|---|---|
| Deterministic RNG (2) | Hard | RNG Acceptance Criteria AC-01, AC-04, AC-05, AC-11 to AC-16 give the known-correct outputs; R4 gives the 18 domain IDs; R9 gives the error cases; R12 is the guarantee the vectors prove; R7 is why AC-22 exists | The inputs and expected values the generator starts from, the domain set for F5, and the error codes for error vectors |
| Data layer and content pipeline (3) | Hard | The validator and its three check tiers (R8), the shared schema (R4), F1 `content_hash`, F4 `uid` assignment, the `unknown table` rule (R2) | The rules this system runs. It adds none of its own to the schema, and its budget file stays outside `data/` |
| Git and the CI host | Hard (validator and gate wrapper) | `HEAD` for the `uid` comparison; a workflow runner for `gate.yml` | Not a game system. Without git the run is NOT ASSESSED (R3) |
| Localization (4) | Soft | The validator's name-coverage check reads `i18n/names_*.csv` | With no i18n files that one check fails and every other check still runs (Data layer, Dependencies) |

**Downstream (systems that depend on this one).** None of these has a GDD yet, except RNG. Each must list this system, name the event groups it adds, and state its `sim_version` behaviour.

| System (#) | Hard / soft | Interface | What it gets |
|---|---|---|---|
| Deterministic RNG (2) | Hard | RNG AC-21 and AC-22 are discharged by R6–R8 and R14 | The vector files and the parity gate. AC-21 stays pending until an engine exists |
| Sim core and tick loop (1) | Hard | Owns `sim_version` (Sim core R12) and `phase_table_hash` (Sim core F5). This system reads both from the code and writes them into each vector file | A single integer (`SIM_VERSION`, in the core's own file) and a hash of the registered handler order, both readable by each implementation |
| Every system whose events draw (9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 24, 25, 26, 28, 31) | Hard | Adds one vector group per event type and a balance scenario where its output enters the budget (R8, R9) | The gate that makes its draw order a contract (RNG R7) |
| Local save and migration (6) | Soft | Stamps `sim_version` and F1 on a save; the harness uses neither at runtime | Nothing to run. It must keep the stamp format stable so replay checks can read it |
| Leaderboards and anti-cheat (35) | Hard (for trust, not for running) | The server replays a submission with the core at its `sim_version`; the vector files are the evidence that core still matches the client's | A parity gate the server can cite |
| Offline progress (31) and Zones and hunt (11) | Hard | A test that compares the aggregate resolver with the exact one (index, TD-SYSTEM-BOUNDARY) runs in the determinism class | A place to run it; the tolerance remains theirs |

"Hard" means the dependent cannot meet its own acceptance criteria without this system. No system needs this one *at runtime*: nothing in `tools/` ships in a build, so a missing tool never stops the game, only stops a merge.

**Consistency notes for the systems index.** The index lists RNG and the Data layer as this system's dependencies, and that is correct. It lists nothing as depending on 43. Systems 1, 6, 11, 31 and 35 and the event systems above each rely on its gate, but a tool is not a runtime dependency, so no index change is proposed. Phase 5 adds the GDD path to row 43 and sets it to Designed.

**Provisional assumptions about undesigned systems.**
1. `sim_version` is a single integer owned by Sim core (1), readable by both implementations. **Resolved** by Sim core R12 (one integer, `SIM_VERSION`). OQ-1 is closed; the header gains `phase_table_hash` (Sim core F5), and a reordered or added handler is a version-bump change.
2. Every event system registers its draws with the recording generator used by F5. How a feature registers is the Sim core's and RNG's to define (RNG `RngFactory`); this GDD requires only that the recording works without changing a draw.
3. The engine implementation can run a headless runner that reads JSON. Not verifiable until an engine is chosen (OQ-2).

## Tuning Knobs

The knobs below live in `tools/gate_config.csv` (columns `key`, `value`, `notes`) or, where noted, in each budget scenario's declaration. They are outside `data/` for the same reason the budget is: the Data layer rejects any CSV there that is not game content. Changing a knob never changes a game outcome; it changes what the gate checks or how long it may take.

| Knob | Where | Default | Safe range | Too high | Too low | Affects |
|---|---|---|---|---|---|---|
| `gate_time_max_s` (F6) | `gate_config.csv` | 90 | 30 – 300 | Developers stop running the gate before a commit; CI minutes grow | A healthy gate warns on every run and the warning is ignored | When F6 prints a time WARN |
| `quick_time_max_s` (R2) | `gate_config.csv` | 60 | 10 – 120, and ≤ `gate_time_max_s` minus 10 | Quick scenarios can grow until the gate is slow | Scenarios are cut until the budget no longer covers pacing and raids | The size of the quick tier |
| `ci_fetch_depth` (R13) | `gate_config.csv` | 2 | 2 and up | Slower checkout, no other harm | 1 makes the `uid` check unrunnable, so every CI run exits 2 | Whether the Data layer's `HEAD` comparison can run |
| `vector_draws_per_event` (R5) | `gate_config.csv` | 16 | 4 – 64 | Vector files grow; diffs get noisy | A reordering that only affects late draws in an event goes unseen | How early a draw-order change is detected (RNG AC-22) |
| `seeds_quick` (R9, R10) | per scenario | 3 | 1 – 10 | Quick run exceeds `quick_time_max_s` | One lucky seed hides a real regression; a band tuned to a single seed breaks on any code change | Time of a scenario and how much its metric is averaged |
| `seeds_full` (R9, R10) | per scenario | 10 | 3 – 100 | Nightly run takes hours | A full run is no better than the quick run | Width of the nightly check |
| Band `lo`, `hi` per budget row (F1) | `balance_budget.csv` | one pair per row | `0 ≤ lo ≤ hi`; width of ±10% to ±25% of the GDD target | Too wide: a real regression passes | Too narrow: any legitimate tuning fails the gate and the budget is edited to make it pass | Whether the gate protects the design intent |

**Interactions.**
- `seeds_quick` and `quick_time_max_s` are coupled: each added seed adds roughly its scenario's run time (the quick run is 29 s today for the current scenario set). The budget file validator checks the sum of declared quick scenarios against the ceiling only by running them; it cannot predict it, so F6 reports the overrun after the fact.
- `quick_time_max_s` is bounded by `gate_time_max_s`: raising only the second does nothing for the quick tier.
- Band width and `seeds_quick` pull against each other. Fewer seeds need wider bands, because a single seed has more variance; more seeds allow tighter bands at a time cost.
- `vector_draws_per_event` and the number of event types set the total size of `tests/parity/vectors/`. Neither is bounded by this system; if the directory grows past a size a reviewer can read, lower the knob before dropping an event.

**Not knobs, and where their values live.**
- *Fixed by design here:* the exit codes 0, 1, 2 (R3), the vector hex encoding (F3), and the four verdicts of F4. Changing any is a breaking change to every vector file and to CI, and bumps `vector_schema`.
- *Owned elsewhere, pointed to:* the PCG32 constants and the event-seed derivation (RNG, Tuning Knobs, fixed by design); `live_wave`, the table inventory and the ID rules (Data layer); the simulator's own parameters in `sim_params.csv` and `config.csv` (Data layer R2, Sim core). This system reads those values and never redefines them.
- *Authoring guidance, not stored:* the default tolerance of ±15% used to pick a band (F1). Only the resulting `lo` and `hi` are stored, because a stored tolerance would be a second source of truth beside them.

## Visual/Audio Requirements

None. This is a Core system with no visual or audio surface.

## Game Feel

None. Players never operate this system. Its indirect contribution to feel is the player's confidence in the numbers (Player Fantasy 3). The developer-facing feel target is the turnaround time of the gate, which F6 and AC-32 specify as a number (≤ 90 s, today ≈ 30 s).

## UI Requirements

No player-facing screen. The tools' output is the only interface, and it is for the developer:

- **Plain text.** Every result line is readable in a CI log and in a terminal with no colour or cursor control. Colour may be added, but never carries a PASS or FAIL by itself: the words `PASS`, `FAIL`, `NOT ASSESSED` are always printed.
- **One line per check**, with the check name first, then the value or reason. The final line is the summary: counts of passed, failed and unrunnable checks, and the exit code (F2).
- **A failure names where to look**: the file and line for the validator, the vector `id` and first differing draw index for parity (AC-14), and the budget row `id` with value and band for balance (AC-29).
- **Unrunnable checks are listed under their own heading**, never mixed into passes.
- Failure messages in these tools are developer text in English; they are not translated and never reach a player.

## Cross-References

| This GDD | References | Section there | Nature |
|---|---|---|---|
| R5–R8, F3–F5, AC-14–AC-23 | Deterministic RNG | AC-21 (port matches the golden-vector file), AC-22 (draw added, removed or reordered fails until the version is bumped) | This system discharges both on the reference side and defines the port-side contract (R14) |
| R5, R6, AC-10 | Deterministic RNG | AC-01, AC-04, AC-05, AC-11 to AC-16 | Known-correct inputs and outputs the generator starts from |
| R8, F5 | Deterministic RNG | R4 (18 domain IDs), R7 (draw order is a contract) | The domain set the coverage check compares against |
| AC-19 | Deterministic RNG | R9 (invalid calls fail loudly), AC-15 | Error vectors record the `RngError` class; Python-only cases are flagged |
| R1, R2, R12, AC-34, AC-35 | Data layer and content pipeline | R1 (pipeline), R2 (inventory, `unknown table`), R6 and F4 (`uid`), R8 (validator tiers), R10 (hot reload) | This system runs the validator and uid helper and owns the CI wrapper; the Data layer owns every rule they apply |
| R14, AC-22 | Data layer and content pipeline | F1 `content_hash`, Edge Cases (loader parity) | The loader vector group carries F1, row counts and a sample row per table |
| R7, F4 | Data layer and content pipeline | F1 (content hash is "the content part of sim version") | `sim_version` covers the code; F1 covers the content. A vector file records the first, and the loader vectors carry the second |
| Overview, R9, R10 | `JX1_Tycoon_GDD.md` | §4.4 (balance simulator is mandatory), §17.1 (tools and `tests/test_core.py`), §20 S9 (`validate_balance.py`) | Source requirements this GDD specifies |
| R5, R14 | `GODOT_PORT.md` | Rule 1 (PCG32 and signed 64-bit shifts), rule 2 (draw order), rule 3 (floats) | The encodings of F3 exist because of these rules |
| Player Fantasy | `JX1_Tycoon_GDD.md` | §3.2, §8.1, §4.4 | Locked lines anchoring the three promises |

## Acceptance Criteria

**Story types.** Every criterion is **Logic** or **Integration** and is checked by an automated test or a scripted fixture run (`tests/unit/tooling/`, `tests/integration/tooling/`; the layout follows the project's current `tests/` folder until an engine sets one). None needs a screenshot or a playtest: this system has no player-facing surface. Criteria marked **[PENDING]** cannot run until an engine exists. Each gate criterion has a *break it* clause: break the thing it guards, confirm the gate fails, then restore it (`.claude/rules/skill-authoring.md`).

**Inventory, commands and exit codes (R1–R4, F2)**
- **AC-1** — **GIVEN** the committed repository, **WHEN** `make check` runs, **THEN** it exits 0 in ≤ 30 s, runs the validator, the unit tests and the vector check, and prints the number of checks of each class.
- **AC-2** — **GIVEN** a fixture where one validator check fails (a dangling reference), **WHEN** `make gate` runs, **THEN** it exits 1 and the output names the failing check.
- **AC-3** — **GIVEN** a copy of the repository with `.git` removed, **WHEN** `make validate` runs, **THEN** it exits 2, prints `NOT ASSESSED: uid check (no git checkout)`, and does not print `0 lỗi` as a pass.
- **AC-4** — **GIVEN** a fixture with 1 failing and 1 unrunnable check, **WHEN** the gate runs, **THEN** it exits 1 and lists the unrunnable check by name. **GIVEN** a fixture with 0 failing and 1 unrunnable check, **THEN** it exits 2.
- **AC-5** — **GIVEN** an empty `tests/parity/vectors/` directory, **WHEN** `make parity` runs, **THEN** it exits 2 (`N = 0`, F2), never 0.
- **AC-6** — **GIVEN** `parity.py --scenario no_such` or `validate_balance.py --tier nonsense`, **WHEN** run, **THEN** it exits 2 with a usage line and runs no other scenario.
- **AC-7** — **GIVEN** a tool run twice on identical inputs, **WHEN** both outputs are compared, **THEN** they are byte-identical. **GIVEN** the tools' source, **THEN** a search finds no wall-clock call, no network call and no use of Python's `random` module in any tool or in `sim/`.
- **AC-8** — **GIVEN** the repository, **WHEN** `sim/` is searched for an import of `tools`, **THEN** there is none.

**Golden vectors and parity (R5–R8, F3–F5)**
- **AC-9** — **GIVEN** `parity.py gen` run twice on unchanged code, **WHEN** the two output trees are compared, **THEN** they are byte-identical, keys are sorted, and each file ends with exactly one newline.
- **AC-10** — **GIVEN** the generated `rng` group, **WHEN** it is read, **THEN** it contains the six outputs `0xa15c02b7 0x7b47f409 0xba1d3330 0x83d2f293 0xbfa4784b 0xcbed606e` for `pcg32_init(42, 54)` as `0x`-prefixed 16-digit strings, and `event_seed(42, 1, [7, 3, 0]) = "0x95221e61ae016288"` in the `event_seed` group. *(Proves RNG AC-01 and AC-05 are the generator's starting values.)*
- **AC-11** — **GIVEN** values `0.1`, `1.0`, `−0.0`, `0.0` and `u64` `2⁶⁴ − 1`, **WHEN** encoded (F3), **THEN** the results are `0x3fb999999999999a`, `0x3ff0000000000000`, `0x8000000000000000`, `0x0000000000000000` and `0xffffffffffffffff`. **GIVEN** `x = 2⁶⁴`, **THEN** generation fails with exit 1.
- **AC-12** — **GIVEN** `+0.0` as expected and `−0.0` as actual, **WHEN** compared, **THEN** they are unequal. **GIVEN** a float output that is NaN, **THEN** generation fails with exit 1 naming the vector.
- **AC-13** — **GIVEN** the committed vectors and unchanged code, **WHEN** `parity.py check` runs, **THEN** every vector passes and the exit code is 0.
- **AC-14** — **GIVEN** a fixture that adds one `next_u32` call inside a reference event that has vectors, with `sim_version` unchanged, **WHEN** `parity.py check` runs, **THEN** the verdict is `Diverged` (F4), the exit code is 1, and the output names the vector `id`, its `ac`, and the index of the first differing draw. *(Proves RNG AC-22 on the reference side. Break it: revert the change and confirm exit 0.)*
- **AC-15** — **GIVEN** the same fixture with `sim_version` bumped and the vectors not regenerated, **WHEN** the check runs, **THEN** the verdict is `Stale` and the exit code is 1. **WHEN** `parity.py gen` then runs, **THEN** the check passes.
- **AC-16** — **GIVEN** a fixture that bumps `sim_version` and changes no behaviour, **WHEN** the check runs, **THEN** the verdict is `Orphaned` and the exit code is 1.
- **AC-17** — **GIVEN** a fixture that reorders two draws inside one event, **WHEN** `check` runs, **THEN** it fails even though the two draws' *set* of values is unchanged, because the sequence is compared in order.
- **AC-18** — **GIVEN** a fixture event that draws in domain 7 with no vector group for domain 7, **WHEN** `parity.py coverage` runs, **THEN** it exits 1 naming domain 7 (F5). **GIVEN** a vector group for a domain with no reference code, **THEN** it prints a WARN and exits 0.
- **AC-19** — **GIVEN** error calls `randint(5, 3)`, `randint(0, 2³²)`, `randint(−2⁶³, 2⁶³ − 1)` and `choice([])`, **WHEN** `gen` runs, **THEN** each is stored as an error vector with `outputs: {"error": "RngError"}` and no output value. *(Mirrors RNG AC-15.)*
- **AC-20** — **GIVEN** a vector file whose `vector_schema` is higher than the tool supports, **WHEN** `check` runs, **THEN** it exits 2 naming the file and both numbers.
- **AC-21** — **GIVEN** a vector file edited by hand to change one expected output, **WHEN** `check` runs, **THEN** it exits 1 (`Diverged`). **GIVEN** a hand edit that changes only the `sim_version` header, **THEN** it exits 1 (`Stale` or `Orphaned`).
- **AC-22** — **GIVEN** the loader group, **WHEN** it is generated and checked, **THEN** it contains the F1 `content_hash`, the row count of all 19 tables, and one canonical sample row per table, and `check` passes. **GIVEN** a fixture that changes one CSV cell, **THEN** the F1 hash vector fails.
- **AC-23** — **[PENDING: needs an engine (`/setup-engine`) and the core port]** — **GIVEN** a port-side result file in the vector schema, **WHEN** `parity.py compare` runs, **THEN** it passes when every vector id is present and equal. **GIVEN** a result file missing one id or holding an unknown one, **THEN** it fails for each, naming the id. *(Discharges RNG AC-21. Everything except producing the result file can be tested today with a fixture result file.)*

**Balance budget (R9–R11, F1, F6)**
- **AC-24** — **GIVEN** a budget row with `lo = 60.4`, `hi = 81.6` and a metric of `71.3`, `60.4`, `81.6`, `94.0` and `null` in turn, **WHEN** `validate_balance.py` evaluates them, **THEN** the results are PASS, PASS, PASS, FAIL and FAIL.
- **AC-25** — **GIVEN** budget files with `lo > hi`, a non-finite bound, a negative `lo` on a time metric, a duplicate `id`, an unknown `tier`, an empty `source`, and an unknown scenario, **WHEN** the validator runs, **THEN** each exits 1 naming the row, before any scenario runs.
- **AC-26** — **GIVEN** a budget row whose metric the simulator did not produce, **WHEN** the gate runs, **THEN** the row is FAIL and the run exits 1. **GIVEN** a scenario that raises an exception, **THEN** its rows are FAIL and the other scenarios' rows still print.
- **AC-27** — **GIVEN** a level the party never reaches, **WHEN** `balance_sim` returns its metric rows, **THEN** the value is `null` (an empty cell in `out/balance_summary.csv`), never `-1`.
- **AC-28** — **GIVEN** `balance_sim` imported as a module, **WHEN** a scenario function is called, **THEN** it returns its metric rows and writes nothing and prints nothing on import. **GIVEN** the same scenario called twice, **THEN** the rows are identical.
- **AC-29** — **GIVEN** the committed budget, **WHEN** `make balance-quick` runs, **THEN** every `quick` row is PASS, the run takes ≤ 60 s, and the table shows value, band and PASS or FAIL per row. *(Break it: double `monster_dmg_factor` in a scratch copy of `sim_params.csv`, confirm at least one row FAILs, restore.)*
- **AC-30** — **GIVEN** the full run, **WHEN** a `full`-tier row fails, **THEN** `make balance` exits 1, and the CI workflow for pull requests does not run `make balance`.
- **AC-31** — **GIVEN** `calibrate.py` run on the committed data, **WHEN** it finishes, **THEN** `git status` shows no change under `data/`. **GIVEN** targets that no parameter set meets, **THEN** it prints the closest candidate and the missed targets and exits 1.
- **AC-32** — **GIVEN** a measured run on the reference machine, **WHEN** `T_gate` is computed (F6), **THEN** `T_gate ≤ 90 s`. **GIVEN** a run that exceeds `gate_time_max_s`, **THEN** a WARN with the time is printed and the exit code is unchanged.

**Generators, uid helper, reload (R12, R15)**
- **AC-33** — **GIVEN** a checkout where `data/schools.csv` has an uncommitted edit, **WHEN** `gen_a.py` would write that file, **THEN** it exits 1 naming the file and writes nothing. **WHEN** run with `--force`, **THEN** it overwrites.
- **AC-34** — **GIVEN** a CSV with one empty `uid` cell, **WHEN** the uid helper runs, **THEN** that row gets `max + 1` and no other cell changes. **GIVEN** a CSV with a duplicate `uid`, **THEN** the helper exits 1 and changes nothing. *(Cross-checks Data layer AC-7.)*
- **AC-35** — **GIVEN** a stray CSV in `data/`, **WHEN** `make gate` runs, **THEN** it exits 1 with `unknown table`. **GIVEN** the budget file in `tools/`, **THEN** the same run does not mention it.
- **AC-36** — **GIVEN** a dev reload of changed content, **WHEN** it runs, **THEN** the simulation restarts at tick 0 with a new seed and the old tables are not read again. A search of the shipped build's entry points finds no call to the reload command.

**CI (R13)**
- **AC-37** — **GIVEN** `.github/workflows/gate.yml`, **WHEN** it is read, **THEN** it triggers on `push` to `main` and on `pull_request`, runs `make gate`, uses `fetch-depth` ≥ `ci_fetch_depth` (2), and has no `paths` filter and no `continue-on-error`.
- **AC-38** — **GIVEN** a pull request that deliberately fails one validator check, **WHEN** CI runs, **THEN** the job is red and the pull request cannot merge. **GIVEN** a shallow clone with depth 1, **THEN** the job is red with exit 2 and the unrunnable `uid` check named. *(Break it: revert both and confirm green.)*

**Cross-system**
- **AC-39** — **GIVEN** the committed `data/` and `i18n/`, **WHEN** the Data layer's AC-1 and this system's `make validate` both run, **THEN** both report 0 errors from the same validator process and the same schema, and neither reads a table list of its own.
- **AC-40** — **GIVEN** a new random event added to `sim/` together with its vector group and a budget scenario, **WHEN** `make gate` runs, **THEN** it passes, and the event's domain appears in both `D_draw` and `D_vec`. **GIVEN** the same event without the vector group, **THEN** `make gate` fails (AC-18).

**Coverage check.** Every rule R1–R15 and formula F1–F6 has a criterion: R1 AC-1; R2 AC-1, AC-29; R3 AC-2–AC-6; R4 AC-7, AC-8; R5 AC-9–AC-12; R6 AC-10, AC-21; R7 AC-14–AC-16; R8 AC-18; R9 AC-24–AC-26, AC-30; R10 AC-27, AC-28; R11 AC-31; R12 AC-33, AC-34; R13 AC-37, AC-38; R14 AC-23 [PENDING]; R15 AC-36; F1 AC-24–AC-27; F2 AC-4, AC-5; F3 AC-11, AC-12; F4 AC-14–AC-16; F5 AC-18; F6 AC-32. *Untested by design:* the 60 s quick-tier ceiling beyond AC-29 and AC-32, and the readability of the failure messages, which AC-14 tests only for the fields it names.

## Open Questions

| # | Question | Owner | Needed by |
|---|---|---|---|
| OQ-1 | **RESOLVED 2026-11-16 by Sim core R12.** `sim_version` is one integer, `SIM_VERSION`, owned by Sim core (1). The vector header also records `phase_table_hash` (Sim core F5). Remaining work: add `phase_table_hash` to the header schema in R5 and F4. | Dev tooling, at implementation | Before the first vector file is committed |
| OQ-2 | **Engine and port-side runner.** AC-23 and RNG AC-21 cannot run until an engine is chosen and the core ported. Feasibility of a headless JSON-reading runner, and of the signed-64-bit encoding in F3, is NOT SOURCEABLE: `docs/engine-reference/` has no core or scripting module and no engine is configured. Run `/setup-engine`, then re-check R14. | Engine setup (`/setup-engine`) | Before the engine port begins |
| OQ-3 | **Should an unbudgeted metric fail?** Today it prints as `unbudgeted` and passes (Edge Cases). Failing it would force every new metric to get a band, which is stricter and noisier. Decide after the first budget is authored and the metric count is known. | User | After the first budget file |
| OQ-4 | **Migration of today's tooling.** The steps: (1) make `balance_sim` a callable that returns rows and emits `null` for not-reached (R10, AC-27, AC-28); (2) author `tools/balance_scenarios` and `balance_budget.csv`; (3) add `tools/validate_balance.py`, `tools/parity.py`, the uid helper and `tools/gate_config.csv`; (4) add the `--force` guard to the generators (R12); (5) add `make parity` and `make gate` to the Makefile; (6) add `.github/workflows/gate.yml`. The 22 existing tests stay as they are. | Implementation stories | MVP |
| OQ-5 | **Order against the RNG migration.** RNG OQ-1 moves `sim/rng.py` to per-event seeding and exact `randint`, which changes every simulated outcome once. Vectors and budget bands recorded before that migration would be recorded twice. Do the RNG migration first, then generate vectors and the first budget from the new numbers. | Producer | Sprint planning |
| OQ-6 | **Test layout.** Existing tests are in `tests/test_core.py`. The project's Web-layout rule names `tests/unit/` and `tests/integration/`, and the engine is not chosen. The criteria assume `tests/unit/tooling/` and `tests/integration/tooling/`. Confirm when the engine is set. | User, at `/test-setup` | Before the first story |
| OQ-7 | **Review of the budget file.** A designer can widen a band to make a failing run pass, and the gate cannot tell (Edge Cases). Requiring review of `tools/balance_budget.csv` through CODEOWNERS is a repository setting. Not needed while the project has one developer. | User | Before a second contributor |
