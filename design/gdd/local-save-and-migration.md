# Local Save and Migration

> **Status**: Designed (pending `/design-review` in a fresh session)
> **Author**: user + Claude (autonomous batch run; decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet)

## Summary

Local save and migration writes the whole guild to one save slot on the device and reads it back, so the guild the player left is exactly the guild they return to, after a quit, a crash or a game update. It defines a contract, not features: each feature registers its own section, invariant check and migration steps under one `schema_version`, and save never imports a feature. Writes are atomic, checksummed and backed up in rotation, so a torn write, a full disk or a bad tick never costs more than the last minute of orders.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Sim core and tick loop, Data layer and content pipeline, Event bus and history log`

## Overview

Local save and migration is the persistence service of JX1 Tycoon (GDD §8.2, §20 S8). It turns the running simulation into one file per guild slot and turns that file back into a running simulation. The file is compressed JSON in a small binary header that carries a checksum. It is written atomically (temporary file, read-back check, rename) with rotating backups and hourly checkpoints. Every save carries one integer, `schema_version`, that names its format. When the game updates and the format changes, the features whose data changed supply migration steps, and the save service chains them to bring an old save up to the current format before anything is restored. GDD §12.5 requires a migration for every content wave.

The system is deliberately thin (systems index, Relationship analysis). It knows four things: the envelope (header, stamps, lineage), the Sim core's snapshot (Sim core R14), the Event bus's history snapshot (Event bus R11), and a list of registered **sections**. It does not know what a member, an item or gold is. A feature that has state registers a section with a serializer, a restorer, an optional invariant check and its migration steps. The host does this registration, so the save service never imports a feature. Save also owns the crash-recovery policy that the Sim core hands it (Sim core R10, OQ-2): when to save, how many generations to keep, never overwriting the last good save with untrusted state, and how a player escapes a save that crashes on every load.

**Player impact.** Players never open a save menu. There is one guild, it autosaves, and it is there when they come back. They see this system only when something goes wrong, and then it must tell them the truth in one sentence: "restored from 2 minutes earlier", "this save is from a newer version — please update", or "storage is full, the game cannot save". Without it, an idle game that runs for months has nothing to come back to.

**What the system does not own.** The cloud slot, account linking and conflict resolution between devices belong to Account and cloud save (7). This system only exports and imports a verified blob. Offline progress (31) owns what `last_saved_utc` means for a long absence and the clock trust policy. Leaderboards (35) owns anti-cheat. The local checksum detects damage, not tampering. Settings, language, ad consent and `install_id` live in platform settings, not in the save (Settings 45, RNG R2). Each feature's data, and the meaning of that data, belong to the feature.

## Player Fantasy

**Indirect.** The player never operates this system. They feel what it guarantees.

**The guild was waiting for me.** The player closes the app on the bus, opens it that evening, and every member, every item in storage and every coin is where they left it, plus what the guild earned while they were away. Nothing asks them to save, and nothing asks which file to load. The guild on the phone is the one they built.

**A crash costs a minute, not a month.** The phone runs out of battery mid-raid. On the next launch the guild is back, at most about a minute of orders behind (F3), with no "corrupted save" screen. If the newest file is damaged, the game says so in plain words and loads the one before.

**Updates never break my guild.** A new wave adds five schools and two zones. The player's eight-month-old guild loads into it untouched, with the new content waiting and none of the old progress reset (GDD §12.5).

*No game pillars exist, so no pillar is quoted. These three are anchored to GDD §1 (single-player offline with continuity), §8.2 (save requirements), §10 (offline progress) and §12.5 (save schema reserved for later waves, a migration per wave). CD-GDD-ALIGN remains NOT ASSESSED. Lens applied: creative-director, three framings drafted; in autonomous mode all three were kept as one indirect fantasy because they describe one guarantee from three moments.*

## Detailed Design

*Specialist lenses applied (§6 routing: Persistence → Foundation/Infrastructure).*

- **systems-designer (primary).** The save must be one state machine with no hidden half-states. The contract with features must be total: every section present after migration, no unknown keys, no float, no shared references. Candidate selection on load must be a rule, not a sequence of "try this, then that" special cases. That led to R12 (highest valid generation wins).
- **gameplay-programmer (feasibility).** Collection must happen between ticks and fit the frame budget. Owners must return fresh copies so the worker thread never reads live state. A migration must work on the decoded JSON tree, never on live objects, so an old save can migrate without the old feature code existing.
- **engine-programmer (integration).** Godot's `JSON` parser returns every number as a float, which silently loses int64 precision above 2^53. So the save holds no JSON numbers at all (R5). Rename onto an existing file is not atomic on every platform, so rotation happens before the rename, and a crash in between is recovered by generation (R10, R12). Mobile backgrounding gives little time, so the background save is synchronous and the format is small.
- **Disagreement resolved (logged):** the gameplay-programmer lens wanted all work on the main thread for simplicity. The engine-programmer lens wanted encoding, compression and I/O off-thread. Chosen: collect on the main thread, encode/compress/write on one worker, because the collected tree is an immutable copy (R7).

### Core Rules

**R1 — One slot, one guild.** The MVP has exactly one save slot, `slot0`, holding one guild. All files of a slot live in one save directory in the app's private storage (the Godot path is an ADR detail). A slot is identified across devices by its `save_id`: 128 random bits from platform entropy, written as 32 lowercase hex characters, created once with the guild and never changed. `save_id` is not drawn from the simulation RNG, so it does not affect any outcome. Multiple slots are not in scope (OQ-6).

**R2 — The file.** A save file is:

| Part | Size | Content |
|---|---|---|
| Magic | 4 bytes | ASCII `JX1S` |
| Container version | 1 byte | `1`. Changes only if this table changes |
| Checksum | 32 bytes | F1: SHA-256 of the uncompressed payload |
| Payload length | 4 bytes | Uncompressed payload size in bytes, unsigned little-endian |
| Payload | rest | The payload JSON (R4), UTF-8, compressed as a standard gzip stream (RFC 1952) |

The container uses standard gzip, not an engine-private block format, so the Python reference (`sim/save.py`, S8) and the engine port read each other's files (R16). A file whose payload length exceeds `save_max_uncompressed_bytes` is rejected before it is decompressed, which bounds memory for a damaged or hostile file.

**R3 — The checksum is for damage, not for cheating.** F1 detects a torn write, a bad sector or a truncated copy. It is not a secret and does not stop a player from editing and re-sealing a save. Integrity against cheating belongs to Leaderboards (35), which replays from `world_seed` and the command log and never trusts a save's numbers.

**R4 — The payload.** The payload is one JSON object with sorted keys and no insignificant whitespace (sorted for diffable fixtures; byte identity between implementations is not required, R16):

| Key | Type | Meaning |
|---|---|---|
| `schema_version` | int-string | The format this payload follows (R8). `SAVE_SCHEMA_VERSION` = 1 at launch |
| `save_id` | 32 hex chars | R1 |
| `generation` | int-string | 1 for the first save of the guild; every later write takes the highest generation on disk + 1 (R10 generation rule), so a newer write always outranks every file already present |
| `created_utc` | int-string | `GameClock.utc_s()` when the guild was created |
| `last_saved_utc` | int-string | `GameClock.utc_s()` at collection (R7). Offline progress measures absence from it (Sim core R7) |
| `app_build` | string | Build identifier of the writer, for support only |
| `sim_version` | int-string | `SIM_VERSION` of the writer (Sim core R12) |
| `content_hash` | 64 hex chars | Data layer F1 of the writer's content |
| `phase_table_hash` | 64 hex chars | Sim core F5 of the writer |
| `live_wave` | int-string | The writer's live wave, informational |
| `seed_used_fallback` | bool | The `used_fallback` flag `new_world_seed` returned at guild creation (RNG API; answers RNG OQ-4) |
| `lineage` | array | R13 |
| `summary` | object | R19 summary values (int-strings, `guild_name` a string), from `core.tick` and the sections' `summary()` at collection |
| `core` | object | `snapshot_core()` verbatim: `world_seed`, `tick`, `next_command_seq`, `sim_version` (Sim core R14) |
| `history` | object | `snapshot_history()`: both packed arrays as R5 blobs, plus `type_table_hash` (Event bus R11) |
| `sections` | object | One entry per registered section, keyed by `section_id` (R6) |

`state_trusted` is never written: an untrusted state is never saved (R9), so every save on disk was trusted when written.

**R5 — No JSON numbers.** The save holds strings, booleans, arrays, objects and `null`, and nothing else:
- **Integers** are decimal strings (`"-12"`, `"9223372036854775807"`), with no leading `+`, no leading zeros and no exponent. This extends Sim core R14 and AC-29b to every section, because a JSON number loses int64 precision in Godot's parser and in any JavaScript reader.
- **Bulk int64 arrays** (a `PackedInt64Array`, such as the history tiers) are an object `{"i64le": "<base64>"}`: the array's values as signed little-endian 8-byte integers, base64 encoded (RFC 4648, with padding). An empty array is `{"i64le": ""}`.
- **Sets of int64** (for example In-app purchases' `store_grants_applied`) are stored as an `{"i64le": …}` array sorted ascending with no duplicates, so equal sets encode identically (R21 digest).
- **Floats are forbidden.** A section that needs a fraction stores a fixed-point integer and states its scale in its own GDD. The encoder rejects a float anywhere in the tree (write error 6104). This keeps saves exact and identical across implementations (GDD §3.2: integers for money and drops).
- **Strings** are UTF-8. Content references are the Data layer's stable IDs or `uid`s (Data layer R3, R6).

**R6 — Sections.** Before the core is sealed, the host registers each stateful feature with:

`register_section(section_id, owner_id, serialize, restore, check = null, summary = null, in_digest = true)`

- `section_id` matches `^[a-z][a-z0-9_]{0,31}$` and is unique. `core`, `history`, `meta` and `save` are reserved.
- `serialize() -> Dictionary` returns a **fresh** tree of R5 values that shares no reference with live state. It is called between ticks only (R7) and may not mutate anything.
- `restore(tree) -> int` takes the tree from the payload and loads the feature's state. It returns 0 or the feature's own error code. It may validate its own data, read content tables, and call another feature's **stateless** functions — pure functions of their arguments and content, such as a curve or a range validator (XP's restore-time validation of `level`/`xp_milli`, XP R9). It may not read or write another feature's **state**: restore order is `section_id` order, and no section can rely on another being loaded yet. A stateless validator's refusal is returned as the section's error code and surfaces as 6009, which is what R14's "lowering a limit" rule relies on.
- `summary() -> Dictionary` is optional: the owner's R19 summary numbers (int-strings), called at collection.
- `in_digest` is false only for sections that hold host or presentation data rather than simulation state (Leaderboards' `ranked_log`, an AI-text cache); such sections are excluded from the R21 digest.
- `check() -> Array[int]` is the optional **invariant check** (Sim core OQ-2). It returns the error codes of violated invariants, empty if none. It runs after all sections are restored on a load, and before encoding on a save. Cross-section consistency (a party that names a member who exists) belongs here.
- Registration closes when the core is sealed (Sim core R4). A late `register_section` is refused.

Sections are serialized, restored and checked in ascending `section_id` order, so the result never depends on the host's registration order. The save service has no list of expected features. The registered set is the expected set (R11).

**R7 — Collecting a save.** A save is taken in two stages:
1. **Collect (main thread, between ticks).** Allowed only when the core is `Running` or `Paused`, not inside a tick, with no hand-off pending, and with `state_trusted = true` (Sim core R14, R10). The service calls `snapshot_core()`, `snapshot_history()`, then every section's `serialize()`, stamps the envelope (R4) with `last_saved_utc = GameClock.utc_s()` and `generation = next_generation` (R10), and runs every `check()`. Any refusal or a non-empty check result aborts the save with no file touched (6101, 6102, 6103). Collection must fit `save_collect_budget_us` (Game Feel).
2. **Write (one worker thread).** The collected tree is immutable. The worker encodes it (R5), computes F1, compresses and writes it (R10). The worker touches no simulation state.

At most one write is in flight. A save requested while one is in flight is **coalesced**: when the write finishes, one more collection runs if any request arrived. Requests never queue up.

**R8 — Autosave triggers.** The service saves:
- every `autosave_interval_s` of foreground wall time, measured on the host's monotonic clock. A due autosave is deferred, not skipped, while the core refuses collection or while `catching_up` is true, and runs on the first frame it is allowed;
- synchronously when the app is backgrounded or asked to close (on mobile the OS-pause notification, on desktop the close request; exact Godot notifications are an ADR detail, shared with Sim core R7). If collection is refused at that moment (a hand-off pending), the previous save stands, which Sim core R14 already accounts for;
- immediately after a new guild is created (generation 1), so a guild never exists only in memory;
- in the first frame after an Offline progress hand-off resolves (`skip_ticks` returns), so a crash after a long absence does not re-run the resolver over a larger gap;
- immediately after a load that migrated or restored from a backup (R12, R14), so the current format and a good generation are on disk.

The service does not save on individual player commands. Whether player gambles should force a commit point is RNG OQ-6's question (OQ-4 here).

**R9 — Never overwrite good with bad.** While the core reports `state_trusted = false` or is `Failed`, every save request is refused (6101) and the autosave timer stops. The last good save stays as it is. A pre-save `check()` failure is treated the same way for that save (6103): the file is not written, the error is reported through the injected log sink, and the next autosave tries again. After `save_check_fail_alert` consecutive check failures the player sees a non-blocking notice (UI Requirements), because the guild is no longer being saved.

**R10 — Atomic write and rotation.** **Generation rule.** The instance keeps two numbers. `max_gen_seen` is the highest generation among every slot file it read at boot (`sav`, `tmp`, `bak*`, `ckpt*`, for the slot's `save_id`, including files that failed R11 steps 5–8 but not files in `damaged/`), raised by every commit and by `import_blob` (R19); `next_generation = max_gen_seen + 1`. `expected_sav_gen` is the generation of `slot0.sav` as this instance last saw it: read at boot (0 if there was no `sav`), and set to the committed generation at step 6. Loading a candidate other than the newest — a backup after damage (R12), an older checkpoint after a crash loop (R18), an imported blob (R19) — changes neither rule: the next write still outranks every file on disk, so the next boot's F2 picks it and not the newer file that was skipped.

The worker writes in this order:
1. Write the file to `slot0.tmp`, flush and close it.
2. **Read-back:** reopen `slot0.tmp`, decompress and recompute F1. On mismatch, delete the temporary file and fail (6107).
3. **Foreign-writer check:** decode the payload envelope of the current `slot0.sav` (generation is a payload field, R4) and compare its generation with `expected_sav_gen` (absent `sav` reads as 0). If they differ, another process (a second desktop window, a restored backup tool) has written the slot. Stop autosaving, keep the temporary file aside as `slot0.orphan`, and fail (6108). The player sees the "open elsewhere" notice.
4. **Rotate:** delete `slot0.bak{N}` (N = `save_backup_generations`), rename `bak{k}` to `bak{k+1}` from the top down, then rename `slot0.sav` to `slot0.bak1`.
5. **Checkpoint:** if at least `save_checkpoint_interval_s` of UTC time has passed since the newest checkpoint's `last_saved_utc` (or none exists), copy the new file as the newest checkpoint `slot0.ckpt1`, shifting older checkpoints up to `save_checkpoint_count`.
6. **Commit:** rename `slot0.tmp` to `slot0.sav`. The write has succeeded: `expected_sav_gen = max_gen_seen = generation`, and the host signal `save_written(generation)` is emitted (R19).

Rotation happens before the commit rename because renaming onto an existing file is not atomic on every platform. A crash between steps 4 and 6 leaves no `slot0.sav`, but a verified `slot0.tmp` with the newest generation, which R12 loads. Any I/O error fails the write (6106) and leaves every earlier file in place. Nothing in this procedure ever deletes the newest good generation.

**R11 — Loading: one candidate.** To load a candidate file the service:
1. Checks magic and container version, then the payload length against `save_max_uncompressed_bytes` (6004, 6011).
2. Decompresses, recomputes F1 and compares it with the header (6003).
3. Parses the JSON and validates the envelope: every R4 key present with its R5 type (6005).
4. **Version gate.** If `schema_version > SAVE_SCHEMA_VERSION` or `sim_version > SIM_VERSION`, the file is from a newer build: refuse with 6001 or 6002. On a boot candidate this also **locks the slot** (R15); on an `import_blob` (R19) it only refuses, because the local files are not newer-version files and must keep being saved.
5. **Migrate** if `schema_version < SAVE_SCHEMA_VERSION` (R14), in memory only.
6. **Section match.** After migration, the set of section IDs must equal the registered set exactly. A missing or an extra section is refused (6008). An extra section means a feature was removed without a migration step that deletes its data, which is a bug, not a player problem.
7. **Restamp versions.** If any lineage field (R13: `sim_version`, `content_hash`, `schema_version`, `phase_table_hash`, `resolver_version`) of the running build differs from the last lineage entry, append a lineage entry (R13) and set the payload's `sim_version` and the core tree's `sim_version` to `SIM_VERSION`. A save written by an older behaviour continues under the new rules from the moment it loads (RNG Edge Cases, "game update changes the draws"); `restore_core` refuses a mismatched `sim_version` precisely so that this decision is made here (Sim core R14).
8. **Restore**, on a freshly constructed core whose features are registered but not sealed (Sim core R11): `restore_core(core)` (6012 on refusal); each section's `restore` in `section_id` order (6009 on a non-zero return or an `UnknownContent` error from the Data layer); `bus.seal()`; `restore_history(history, core.tick)` (6010 on `ok = false`); every `check()` (6013 if any fails). Then the host calls `core.seal()` and `start()`.

A failure at step 8 leaves a half-restored instance, so the host discards the whole instance and constructs a new one before trying the next candidate. The candidate file is never modified by a failed load. `trimmed_count`, `unknown_type_count` and `hash_mismatch` from `restore_history` are not failures: they are logged to the injected log sink and shown nowhere to the player (Event bus R11 leaves the warning decision here; the answer is "no player warning").

**R12 — Loading: choosing among candidates.** The candidate files are `slot0.sav`, `slot0.tmp`, `slot0.bak1…N` and `slot0.ckpt1…K`. At boot the service reads each header and payload envelope, and loads by F2: the **valid candidate with the highest generation** wins, where valid means it passes R11 steps 1–4. The highest-generation valid candidate defines the slot's `save_id`; a candidate with a different `save_id` is not valid (6006, logged). If the winner then fails at steps 5–8, the next-highest with that `save_id` is tried, and so on. The R15 lock is judged on the highest-generation candidate that passes steps 1–3.
- If the winner is `slot0.tmp`, it is promoted (renamed to `slot0.sav`) after a successful load. This recovers the R10 crash window.
- If the loaded generation is lower than the highest generation found on disk because the newer files failed to load (damaged), the player sees the "restored from an earlier save" notice with the loaded save's `last_saved_utc` as a local time, and R8 writes a new generation at once. The damaged files are moved to the `damaged/` subdirectory, never deleted (R15). The new generation is `max_gen_seen + 1` (R10), so it outranks the damaged files' generations too. An older save loaded on purpose (R18, R19) is not this case: no file is moved, and the newer files stay in rotation until the next writes push them out.
- Candidates with a different `save_id` from the winner are ignored and logged (6006). With one slot this happens only after manual file copying, or after an `import_blob` that replaced the guild (R19), whose older-`save_id` backups then rotate out.
- If no candidate exists, the slot is empty and the new-guild flow runs. If candidates exist and none loads, see R15.

**R13 — Lineage.** `lineage` is an ordered list of `{from_tick, sim_version, content_hash, schema_version, phase_table_hash, resolver_version}` entries, int fields as R5 strings. `phase_table_hash` is Sim core F5 of the running build and `resolver_version` is Offline progress's `resolver_version` constant (Offline R17), both read from the host at load. The first entry is written at guild creation with `from_tick = "0"`. On each load whose build differs from the last entry in any of these five fields, R11 step 7 appends an entry with `from_tick` = the restored core tick. These are exactly the fields whose change closes a Leaderboards segment (Leaderboards R5), so one segment always replays with one core. It tells Leaderboards (35) and the parity harness (43) which rules and content governed each stretch of a guild's life, so a replay can be judged comparable (Dev tooling Dependencies). The list keeps at most `save_lineage_cap` entries; beyond that the oldest entry is dropped and the next one's `from_tick` is kept, so the list always covers the newest stretches. Leaderboards reads only the newest entry (Leaderboards Cross-References), so the cap is sufficient.

**R14 — Migration.** One integer, `SAVE_SCHEMA_VERSION`, names the format of the whole payload. It starts at 1 and increases by exactly 1 for each format change. Every content wave that adds or changes state bumps it (GDD §12.5).
- **Steps.** An owner registers `register_migration(section_id, from_version, step)` where `step(section_tree_or_null, payload_readonly) -> section_tree_or_null` turns that section from format `from_version` into `from_version + 1`. The step receives the section's decoded R5 tree, not live objects, so it runs without the old feature code. It receives `null` for a section that does not yet exist (a new feature creates its initial data this way), and returns `null` to delete the section (a removed feature). It may read the whole payload as it stood at `from_version`, so data can move between sections. It may read content tables. It may not use RNG, a clock, I/O or any other feature.
- **Chaining.** For a save at version v < current, the service applies, for each version from v up to current − 1, every step registered for that version in `section_id` order, then sets `schema_version` to the next value. The envelope's own fields migrate through steps registered under the reserved section ID `meta`.
- **Completeness.** A version with no registered step for any section is allowed: it records a bump whose change was outside sections (for example the envelope). A missing step that a section needed shows up as a restore failure (6009) or a section-set mismatch (6008). Fixture tests (R17) make both a CI failure, never a player failure.
- **A step that throws** or returns a non-R5 tree fails the load with 6007. The file is not changed.
- **Pre-migration copy.** Before the first save after a migration, the loaded file is copied as `slot0.pre_v{v}.sav` (v = its old `schema_version`). The service keeps the single most recent pre-migration copy and deletes the older one only after a later migration has completed and saved. This is the rollback point if a migration step is later found to be wrong.
- **Lowering a limit is a migration.** A patch that tightens a rule a saved value could violate (for example a lower level cap, XP R9) ships a migration step that brings saved data inside the new rule, and a `schema_version` bump. Without one, the restore fails with 6009, which the fixture tests catch. This answers XP OQ-5: the save system does not clamp, reset or repair data on its own; migrations do, explicitly.

**R15 — Never delete, sometimes lock.** The save service never deletes a file that might be the only copy of a guild:
- Damaged candidates move to `damaged/` with their original name and a timestamp suffix. The service keeps at most `save_damaged_keep` files there, deleting the oldest beyond that.
- **Newer-version lock.** If the highest-generation candidate is refused with 6001 or 6002, the slot is locked for this run: no save is written (6109) and the new-guild flow is unavailable, because starting a new guild would rotate the newer save out. The player sees only the "update the game" screen.
- **All damaged.** If candidates exist and every one fails, the player sees the "save damaged" screen with two actions: start a new guild, which first moves every slot file to `damaged/`, or quit. The service never silently starts a new guild over an existing one.

**R16 — Python reference and parity.** `sim/save.py` (S8) is the reference implementation, written before the port, as for every other `sim/` module (GDD §18, `GODOT_PORT.md`). Both implementations must load each other's files and arrive at the same core and section state; they need not produce byte-identical files (gzip output and JSON string escaping legitimately differ). The checksum is over the bytes the writer produced, so it needs no canonical form.

**R17 — Fixtures live forever.** Every released `schema_version` has at least one fixture save committed under `tests/fixtures/saves/` (a guild with members, items, history and at least one milestone). Fixtures are never deleted or regenerated. CI loads every fixture through migration in both implementations (GDD §20 S8: "load save v1 from a sample file after migration"). A schema bump that ships without a fixture of the previous version fails CI.

**R18 — Crash loops.** When the core enters `Failed`, the host writes a small crash marker `slot0.crash` holding `{base_generation, failed_at_tick, fail_code, fail_owner_id, count}`, int fields as R5 strings. `base_generation` is the generation the running session loaded or last wrote. If the marker already names the same `base_generation`, `failed_at_tick` and `fail_code`, `count` is incremented instead. When `count ≥ crash_repeat_threshold`, the fatal screen (Sim core UI Requirements) adds a third action, **"Load an older save"**, which loads the newest **checkpoint** whose generation is below `base_generation` (usually `ckpt1`, or `ckpt2` if `ckpt1` is the crashing generation). Rotating backups are skipped on purpose: they are minutes old and likely hold the same bad state (F5). After the older save loads, R8 writes it at once as generation `max_gen_seen + 1` (R10), so the next boot's F2 picks the recovered state, not the crashing `sav`/`bak` generations, and the foreign-writer check compares against the `sav` generation read at boot (`expected_sav_gen`), so it passes. The marker is deleted after the next successful write. The core gets no new primitive for this (Sim core R10 is unchanged), and there is no "skip the failing stretch" option in MVP (OQ-2).

**R19 — Cloud hand-off.** For Account and cloud save (7), the service offers:
- `export_current() -> {bytes, save_id, generation, last_saved_utc, schema_version, sim_version, summary}`: the exact bytes of the current `slot0.sav` plus its envelope facts. `summary` is the envelope's `summary` object (R4), taken at collection: `tick` (core), `guild_name`, `guild_level`, `member_count`, `member_level_sum`, `gold_total`. Each value except `tick` is supplied by the section that owns it through its `summary()` (R6); a key no registered section supplies is absent, never invented. The guild key across devices is `save_id` (R1); there is no separate guild uid.
- `save_written(generation)`: host signal emitted after every commit (R10 step 6), including the write that follows an import. It is the "save completed" signal 7 listens to.
- `import_blob(bytes) -> {code, generation}`: runs R11 steps 1–8 on the blob in a fresh instance. On success the blob becomes the current guild: the current local `slot0.sav` is first copied to `slot0.replaced.sav` (one copy, replaced by the next import, never rotated by ordinary writes), then R8 writes the imported state locally as generation `max(max_gen_seen, imported generation) + 1` (R10), and that generation is returned so 7 can record it as its agreement point (Account R6). The written bytes differ from the blob (new generation, new `last_saved_utc`); 7 compares by `save_id` and generation, not by bytes. A different `save_id` is allowed here (a cloud guild replacing a local one) only because 7 asked the player. A refusal returns the R20 load code and changes nothing on disk; a newer-version blob (6001/6002) is refused **without** locking the slot (R11 step 4), and 7 checks the cloud record's versions before downloading (Account R9), so this is a backstop.
- **Cloud size budget.** At shipped defaults the compressed file must stay at or below Account's `cloud_blob_max_bytes` (2 MiB) for the max-roster fixture with a ranked log of one submit interval (F4). Above that (a ranked log of about 30,000 or more entries, F4) Account refuses the upload as "backup too large" (Account R10) until Leaderboards' acknowledgement truncates the log; the local save is unaffected.

The conflict rule (newest `last_saved_utc` versus asking the player, GDD §8.1 "conflict → player chooses", S8 "warn on large divergence") is 7's.

**R20 — Result codes.** Save and load return codes. They are not `ctx.fail` codes and never fail the core (Sim core R10 reserves ≥ 1000 for feature `ctx.fail`; this range is outside the tick).

| Code | Load-side meaning | | Code | Write-side meaning |
|---|---|---|---|---|
| 6001 | `schema_version` newer than build | | 6101 | State untrusted or core `Failed` (R9) |
| 6002 | `sim_version` newer than build | | 6102 | Core or bus refused the snapshot: mid-tick, hand-off pending, not sealed |
| 6003 | Checksum mismatch | | 6103 | A section `check()` failed |
| 6004 | Bad magic, container version, gzip or JSON | | 6104 | Encoding: a float, a non-R5 value or a shared reference |
| 6005 | Envelope key missing or wrong type | | 6105 | Payload over `save_max_uncompressed_bytes` |
| 6006 | `save_id` mismatch on a candidate | | 6106 | I/O error (write, flush, rename, storage full) |
| 6007 | A migration step failed | | 6107 | Read-back checksum mismatch |
| 6008 | Section set differs from the registered set | | 6108 | Foreign writer detected (R10 step 3) |
| 6009 | A section's `restore` failed, or `UnknownContent` | | 6109 | Slot locked by a newer-version save (R15) |
| 6010 | `restore_history` returned `ok = false` | | | |
| 6011 | Payload length over the limit | | | |
| 6012 | `restore_core` refused | | | |
| 6013 | A section `check()` failed after load | | | |

**R21 — Sim-state digest (for Leaderboards).** `sim_state_digest() -> 64 hex chars` is SHA-256 over the **canonical form** of `{core, history, sections}` taken by one R7 collection, where `sections` keeps only sections registered with `in_digest = true` (R6). The envelope (`last_saved_utc`, `generation`, `app_build`, `lineage`, `summary`, …) is excluded, so two runs that reach the same simulation state at the same tick give the same digest even if they saved at different times. Canonical form, which unlike the file (R16) must be byte-identical in both implementations: the R5 tree as UTF-8 JSON with object keys sorted by Unicode code point, no whitespace, strings escaped only for `"`, `\` and code points below U+0020 (as `\u00xx`, lowercase hex), base64 with padding. It answers Leaderboards OQ-3 (its F2 `end_state_hash` is this digest at `end_tick`). It is computed on demand between ticks (same preconditions as R7 collection) and costs one serialization plus one hash; it is not stored in the file.

**R22 — Side files.** Small per-device files that must not live inside the save (so a save chosen in a cloud conflict cannot change them) are written through one helper, `write_side_file(name, tree)`: R5 tree, gzip, the R2 container, written as `name.tmp`, read back, then committed as R10 steps 4 and 6 do with one backup (`name` → `name.bak`, `name.tmp` → `name`; on read, a valid `name` wins, else a valid `name.tmp`, else `name.bak`), with the same 6104/6106/6107 codes. A side file that fails its checksum on read is treated as absent and logged. Users: Account's `sync_meta` (Account R6), Entitlement's per-account cache (Entitlement R6) and In-app purchases' pending receipts (IAP R4.3). Side files are never rotated, never uploaded and never part of the digest.

### States and Transitions

One `SaveService` instance per app run, per slot.

| State | Meaning | Event | Next state |
|---|---|---|---|
| `Idle` | Constructed; no file read | `boot_load()` finds no candidate | `NewGuild` |
| `Idle` | | `boot_load()` finds candidates | `Loading` |
| `Loading` | Trying candidates by F2 (R11, R12) | A candidate loads | `Active` |
| `Loading` | | Highest candidate is newer-version (6001/6002); boot only, never from `import_blob` | `Locked` |
| `Loading` | | Every candidate fails | `Damaged` |
| `NewGuild` | Host creates a guild | Generation 1 written | `Active` |
| `Damaged` | "Save damaged" screen | Player chooses "start new guild" (files moved to `damaged/`) | `NewGuild` |
| `Active` | Autosaving (R8) | Core `state_trusted = false` or `Failed` | `Halted` |
| `Active` | | Foreign writer detected (6108) | `Halted` |
| `Active` | | App closes after the final save | — |
| `Halted` | No writes; last good save kept (R9). Crash marker written if the core failed (R18) | Player chooses "Reload" or "Load an older save" | new instance, `Idle` |
| `Locked` | No writes, no new guild (R15) | — (terminal for the run) | — |

`Writing` is not a state of the service: it is a flag (`write_in_flight`) inside `Active`, because collection and coalescing (R7) happen within `Active`. A transition to `Halted` while a write is in flight lets that write finish: its tree was collected while the state was trusted.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|---|---|---|---|---|
| Sim core (1) | both | `snapshot_core()`, `state_trusted`, `state`, the `Failed` record, `GameClock.utc_s()` | `restore_core(core)` on a fresh instance; recovery policy (R9, R18) | Core owns what it contributes (R14); Save owns format, cadence, generations, crash policy |
| Data layer (3) | in | `content_hash` (F1), `live_wave`, `Ready` state, content lookups and `UnknownContent` during restore and migration | — | Data layer owns IDs and hash; Save owns the mismatch policy (R11 step 7: a mismatch is normal, recorded in lineage) |
| Event bus (42) | both | `snapshot_history()` | `restore_history(snapshot, core_tick)` | Bus owns snapshot content; Save owns encoding (R5 blobs) and the warning decision (no player warning) |
| Deterministic RNG (2) | in (via host) | `world_seed` inside the core snapshot; `used_fallback` from `new_world_seed` | `seed_used_fallback` stored in the envelope | RNG owns "only the seed is saved" (R11); owners save their ordinal counters in their sections |
| Every stateful feature (8, 9, 11, 13, 14, 15, 16, 22, 23, 24, 26, 27, 28, 29, 30, 31, …) | both | `serialize`, `restore`, `check`, `summary`, migration steps | The section tree on load | Each feature owns its section's content and migrations; Save owns the contract (R5, R6, R14) |
| Offline progress (31) | out | Hand-off resolution (R8 trigger); `resolver_version` for lineage (R13) | `last_saved_utc` of the loaded save | Offline owns absence trust and the cap (12 h for every player, Offline R4) |
| Account and cloud save (7) | both | `import_blob` requests; `sync_meta` side file (R22) | `export_current`, `save_written`, `import_blob` result `{code, generation}` (R19) | 7 owns the cloud slot and conflict policy |
| Leaderboards (35) | both | `ranked_log` section (`in_digest = false`) | `lineage` (R13), `save_id`, `sim_version`, `sim_state_digest()` (R21) | 35 owns replay comparability and its section |
| In-app purchases (34) | both | Its section holding `store_grants_applied` and `store_grants_revoked` (int64 sets, R5); pending-receipt side file (R22) | Section tree on load | IAP owns the fields; for a save whose schema predates the section, IAP's migration step receives `null` and returns two empty sets (R14) — at `SAVE_SCHEMA_VERSION` 1 every save has it |
| Entitlement (32) | both | `entitlement` section; per-account cache side file (R22) | Section tree on load | Entitlement owns both |
| Offline progress (31) | both | Its section, including the per-group trip carry `carry_g` kept across gaps (user decision D6, 2026-11-16; Offline R16 adds it) | Section tree on load | Offline owns the field and its migration |
| Dev tooling (43) | out | — | `sim_version` and `content_hash` stamps, fixtures (R17) | Save keeps the stamp format stable |
| Guild screens (39), Localization (4) | out | Player choices on the notices | Notice kinds and their facts (UI Requirements) | 39 and 4 own layout and wording |

## Formulas

### F1 — `save_checksum`

The save_checksum formula is defined as:

`save_checksum = SHA-256(payload_bytes)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| payload_bytes | bytes | 2 – `save_max_uncompressed_bytes` | calculated | The uncompressed UTF-8 payload JSON exactly as the writer produced it (R4) |
| save_checksum | 32 bytes | 0 – 2^256 − 1 | calculated | Stored raw in the header (R2) |

**Output Range:** any 256-bit value. The minimum payload is `{}` (2 bytes), which is never a valid save but still hashes.
**Example:** a 1.9 MB payload hashes to a 32-byte value in a few milliseconds on a phone; flipping any one byte of the payload changes the checksum and the load is refused with 6003. SHA-256 is the same hash the Data layer uses for F1, so both implementations already have it.

### F2 — `load_choice`

The load_choice formula is defined as:

`load_choice = the candidate c ∈ valid with the greatest generation(c); ties broken by file order sav < tmp < bak1 … bakN < ckpt1 … ckptK`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| valid | set | 0 – (2 + N + K) files | calculated | Candidates that pass R11 steps 1–4 for the slot's `save_id` |
| generation(c) | int | 1 – 2^63 − 1 | save file | R4 |
| N | int | 1 – 10 | data file | `save_backup_generations` |
| K | int | 0 – 10 | data file | `save_checkpoint_count` |

**Output Range:** one candidate, or none when `valid` is empty (R15). A tie is possible only when a checkpoint is a copy of the current file (R10 step 5), and then both are the same bytes.
**Example:** after a crash between rotation and commit, the disk holds `tmp` (gen 412), `bak1` (gen 411), `bak2` (410), `bak3` (409), `ckpt1` (380). `sav` is absent. `load_choice = tmp`, which is promoted to `sav`.

### F3 — `lost_wall_time_max`

The lost_wall_time_max formula is defined as:

`lost_wall_time_max_s = autosave_interval_s + write_time_s` (an unclean exit: crash, kill, power loss)
`lost_wall_time_clean_s ≤ 0.1 s` (a background or quit save that completes; Sim core R14 sub-tick remainder)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| autosave_interval_s | int | 15 – 300 | data file | R8 interval (default 60) |
| write_time_s | float | 0 – ~1 | calculated (measured) | Collect + encode + write time of the last save; under 1 s at the size budget on min-spec (to be measured in the P1 spike) |

**Output Range:** about 61 s at defaults; 16 s at the minimum interval; 301 s at the maximum. What is lost is the player's orders and the live progress in that window. Offline progress does not replay it: the next start measures absence from the older `last_saved_utc`, so the wall time itself is not lost, only the orders given in it. That is the "at most about a minute of orders" promise in Player Fantasy.
**Example:** a crash 59 s after an autosave loses 59 s of orders; the next launch credits all wall time since that save as an absence.

### F4 — `save_size_estimate`

The save_size_estimate formula is defined as:

`payload_bytes ≈ ⌈history_bytes / 3⌉ × 4 + members × member_bytes + other_bytes`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| history_bytes | int | 11,200 – 8,000,000 | calculated | Event bus F3 `history_bytes_max` (736,000 at defaults); base64 adds a third |
| members | int | 1 – 1,000 | calculated | Members holding a section entry, including departed members whose name record is kept (Event bus OQ-4: `milestone_subjects_planned` = 1,000) |
| member_bytes | int | ~0.5 – 4 KB | constant (estimate) | Per-member JSON footprint; PROVISIONAL until Member model (8) defines its section |
| other_bytes | int | ~50 – 500 KB | constant (estimate) | Storage, buildings, market, quests, envelope; PROVISIONAL |

**Output Range:** about 1.3 MB at defaults with 100 members at 2 KB (981,334 + 200,000 + ~150,000). Worst case about 15 MB (10.7 MB history + 4 MB members + 0.5 MB). gzip typically compresses this kind of text 3–5×, so the file is roughly 0.3–4 MB. The worst case stays below `save_max_uncompressed_bytes` (32 MiB) with more than 2× headroom. `save_size_warn_bytes` (8 MiB) logs a dev warning well before the hard limit.
**Example:** defaults with 100 members: 1.33 MB payload, about 350 KB on disk.

### F5 — `recovery_lookback`

The recovery_lookback formula is defined as:

`rotating_lookback_s ≈ save_backup_generations × autosave_interval_s`
`checkpoint_lookback_s ≈ save_checkpoint_count × save_checkpoint_interval_s`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| save_backup_generations | int | 1 – 10 | data file | Rotating backups (default 3) |
| save_checkpoint_count | int | 0 – 10 | data file | Hourly checkpoints kept (default 2) |
| save_checkpoint_interval_s | int | 600 – 86,400 | data file | UTC seconds between checkpoints (default 3,600) |

**Output Range:** at defaults, rotating backups reach about 3 minutes back (they protect against a damaged file); checkpoints reach about 1–2 hours back (they protect against bad state that was saved repeatedly, which rotation alone cannot escape). With `save_checkpoint_count = 0` a crash loop whose bad state is older than 3 minutes has no escape, so the knob's floor is effectively 1 for a shipped build.
**Example:** a silent GDScript corruption is saved for 10 minutes before it trips a check. All three backups hold it; `ckpt1` (up to an hour old) does not, and "Load an older save" (R18) reaches it.

## Edge Cases

*Lens applied: systems-designer, Section E checks on Sections C and D.*

**Writing**
- **If the device is out of storage**: the write fails at step 1 with 6106, the temporary file is deleted if it exists, every earlier file stays, and the next autosave retries. After `save_write_fail_alert` consecutive failures the player sees the "cannot save" notice. Play continues; nothing is deleted to make room.
- **If the app is killed during step 1 or 2**: a partial or unverified `slot0.tmp` is left. On the next boot it fails F1 or the gzip read and is ignored; `slot0.sav` (previous generation) loads. The stale temporary file is overwritten by the next write.
- **If the app is killed between rotation (step 4) and commit (step 6)**: there is no `slot0.sav`. F2 picks the verified `slot0.tmp` (newest generation) and promotes it. If the kill happened mid-rotation, every file still exists under some name, and F2 orders them by generation, not by name.
- **If a save is requested inside a tick, during a pending hand-off or before `seal()`**: collection is refused (6102), nothing is written, and the request stays due; the service retries next frame (Sim core R14 makes these error returns, not fatals).
- **If a section's `serialize()` returns a float, a non-R5 value or a reference to live state**: the encoder refuses the whole save (6104). In a dev build the error names the section and the key path. This must never reach a player: AC-14 runs every registered section's serializer through the encoder in CI.
- **If the background save cannot run because a hand-off is pending at the moment of backgrounding**: the previous save stands. The next start measures from the older `last_saved_utc` and re-owes the gap (Sim core R14). Accepted.
- **If a second process writes the slot (two desktop windows)**: the second writer to reach step 3 sees an unexpected generation, stops autosaving, and keeps its file as `slot0.orphan` (6108). No write ever overwrites another process's newer generation. The orphan is not loaded automatically; it is kept for support.
- **If the device clock jumps backward between two saves**: `last_saved_utc` may go down. It is stored as read; the checkpoint rule (R10 step 5) treats a negative elapsed time as "not yet due". Clock trust is Offline progress's and Leaderboards' (Sim core R7).
- **If `generation` reaches 2^63 − 1**: unreachable (one save per 60 s for 10^13 years). No rule.
- **If the payload exceeds `save_size_warn_bytes`**: a dev warning is logged; the save proceeds. **If it exceeds `save_max_uncompressed_bytes`**: refused (6105) and handled like a write failure (notice after repeated failures). The F4 worst case cannot reach it at shipped caps; a reach means a section grew without bound, which is that section's bug.

**Loading**
- **If the newest file has a bad checksum but a backup is good**: the backup loads, the player sees "restored from an earlier save" with its time, the damaged file moves to `damaged/`, and a new generation is written at once (R12).
- **If a save is from a newer build (a player sideloads an older APK, or a cloud blob from a newer device)**: refused (6001/6002); the slot is locked: no writes, no new guild (R15). The screen says to update the game. Nothing on disk changes.
- **If the content hash differs** (any content patch): normal. A lineage entry is appended (R13); nothing is shown to the player.
- **If a save references an ID that no table has**: the Data layer raises `UnknownContent` (Data layer Edge Cases); the section's restore fails (6009) and the next candidate is tried. Since shipped content rows are never deleted (Data layer R6), this means corruption or a newer build that the version gate missed, so falling back is right.
- **If a save holds content that is no longer live** (retired, or a later wave than `live_wave`): it loads and behaves as its row says (Data layer content_live). No migration is needed.
- **If a section's data violates a tightened rule (a level above a lowered cap)**: the owner's restore refuses it (XP R9, 2202), the load fails with 6009, and all backups fail the same way. This is prevented, not handled: the patch that lowered the cap must ship a migration step (R14), and the fixture tests fail the build without one.
- **If a new feature ships**: its migration step for the new version receives `null` and returns the section's initial data, so an old save gains the section at load.
- **If a feature is removed**: its migration step returns `null` for the section. Without that step the load fails with 6008, caught by fixtures.
- **If restore_history reports trimmed records, retired types or a type-table mismatch**: logged only (R11). The Chronicle may be shorter after a tightened cap; that is the Event bus's accepted behaviour.
- **If restore_history refuses because its last record tick is ≥ the core tick** (history and core from different generations): impossible for a file written by R7 (one collection), so it means a hand-built or corrupted file: 6010, next candidate.
- **If `last_saved_utc` is later than the current UTC on load**: the core clamps the absence to 0 (Sim core R7). The save system does not correct the stamp.
- **If the only candidates have a different `save_id` from each other** (files copied in by hand): F2 picks the highest generation; the rest are logged and ignored.
- **If every candidate fails**: the "save damaged" screen (R15). Starting a new guild moves all files to `damaged/` first.
- **If a migration chain is long** (a guild returning after several waves): each step runs in order in memory; the pre-migration copy keeps only the original file (`pre_v{v}`). A chain over 20 versions has no special rule; its cost is dominated by decoding, not by steps.

**Crash recovery**
- **If the core fails on every load at the same tick**: the crash marker's count rises; at `crash_repeat_threshold` (2) the fatal screen offers "Load an older save" (R18), which reaches a checkpoint older than the crashing generation.
- **If the older save also crashes**: its own marker starts (a new `base_generation`), and the offer repeats with the next older checkpoint. When no older candidate remains, the offer is not shown, leaving "Reload" and "Quit" (Sim core UI Requirements). Accepted: a fault that reaches every checkpoint is a build bug that a patch must fix.
- **If the core fails but `state_trusted` is false only transiently** (there is no such case: `Failed` is terminal, Sim core R10): no rule.
- **Save-scumming** (reload to re-roll an outcome): reloading repeats the outcome, because only the seed and ordinals are saved (RNG Edge Cases). The save system adds no rule; forcing a save at gamble commit points is OQ-4.

## Dependencies

| System | Hard/Soft | Interface used | What this system needs |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | `snapshot_core()`, `restore_core()`, `state_trusted`, `state`, the `Failed` record, `GameClock.utc_s()`, `SIM_VERSION`, startup order R11 | A consistent between-ticks snapshot and a trusted-state signal |
| Data layer and content pipeline (3) | Hard | `content_hash` (F1), `live_wave`, read-only tables, `UnknownContent`, the config keys in Tuning Knobs | Stable IDs that mean the same thing in every build; config values for the knobs |
| Event bus and history log (42) | Hard | `snapshot_history()`, `restore_history(snapshot, core_tick)` (R11) | A bounded, versioned history to persist |
| Deterministic RNG (2) | Soft (through the core and host) | `world_seed` in the core snapshot; `used_fallback` | Nothing beyond storing them |

| Depended on by | Hard/Soft | What they get |
|---|---|---|
| Every stateful feature (Member model 8, CA/PA 9, Zones 11, Party 13, Golden Boss 14, Recruitment 15, Retention 16, XP 22, Rebirth 23, Enhancement 24, Items 26, Gold economy 27, Crafting 28, Market 29, Guild and buildings 30, Offline 31, Quests 25, …) | Hard | The section contract (R5, R6) and migration (R14). Each must register a section, keep its counters in it (RNG R11), and ship a step plus a fixture for each format change |
| Offline progress (31) | Hard | `last_saved_utc`; a save after each resolved hand-off (R8) |
| Account and cloud save (7) | Hard | `export_current`, `import_blob`, `summary` (R19) |
| Leaderboards and anti-cheat (35) | Soft | `lineage`, `save_id` (R13) |
| Dev tooling and parity harness (43) | Soft | Stable `sim_version`/`content_hash` stamps; fixtures and cross-implementation load test (R16, R17) |
| Guild screens (39), Localization (4) | Soft | The notice kinds in UI Requirements |
| XP and level pacing curve (22) | Soft | Answer to XP OQ-5: out-of-range levels are fixed by migrations, never clamped by save (R14) |

**Bidirectional check.** Sim core, Data layer, Event bus and RNG each list Local save (6) as a dependent with the same interfaces used here. Dev tooling lists it as Soft with the stamp format, matching. XP lists it for OQ-5, answered here. The systems index row lists Sim core, Data layer and Event bus, matching the Hard rows above.

## Tuning Knobs

All knobs are `config` keys (PROVISIONAL: they do not exist in `data/config.csv` yet; OQ-1 asks the Data layer to add them with validator ranges). None affects simulation results, so changing one is not a `sim_version` bump. It does change `content_hash`, which is harmless (R11 step 7).

| Knob | Default | Safe range | Too high | Too low |
|---|---|---|---|---|
| `autosave_interval_s` | 60 | 15 – 300 | More orders lost on a crash (F3) | More write wear and battery; more frames carrying collection cost |
| `save_backup_generations` | 3 | 1 – 10 | More storage (≈ file size × N) | Less protection against a damaged newest file |
| `save_checkpoint_count` | 2 | 1 – 10 (0 only in tests) | More storage | 0 removes crash-loop escape (F5) |
| `save_checkpoint_interval_s` | 3,600 | 600 – 86,400 | Older escape point, more progress lost on "Load an older save" | Checkpoints converge on rotating backups and may hold the same bad state |
| `save_max_uncompressed_bytes` | 33,554,432 (32 MiB) | 16 – 128 MiB | Larger peak memory on load of a hostile file | Legitimate large guilds refused (F4 worst case ≈ 15 MB) |
| `save_size_warn_bytes` | 8,388,608 (8 MiB) | 1 MiB – max | Late warning | Noisy dev logs |
| `save_lineage_cap` | 256 | 16 – 4,096 | Envelope grows slightly | Leaderboards loses older lineage (OQ-3) |
| `crash_repeat_threshold` | 2 | 1 – 5 | Player sees more crashes before the escape is offered | 1 offers an older save after a single crash, which may lose progress for a one-off fault |
| `save_write_fail_alert` | 3 | 1 – 20 | Player learns late that nothing is being saved | Notice on a transient I/O hiccup |
| `save_check_fail_alert` | 3 | 1 – 20 | As above, for invariant failures | As above |
| `save_damaged_keep` | 10 | 1 – 50 | Storage | Support loses evidence |
| `save_collect_budget_us` | 4,000 | 1,000 – 8,333 | Frame hitches at autosave (Game Feel) | Over-constrains feature serializers |

**Interactions.** `save_checkpoint_interval_s` and `autosave_interval_s` together set F5; a checkpoint interval at or below `save_backup_generations × autosave_interval_s` makes checkpoints redundant with backups. `autosave_interval_s` and `save_collect_budget_us` together set the average save cost per minute. **Not knobs:** the container layout (R2), the R5 encodings, error codes (R20) and `SAVE_SCHEMA_VERSION` are fixed by design; changing the container needs a new container version byte.

## Visual/Audio Requirements

No visual or audio feedback for a normal save: there is no save icon and no sound, because an autosave every minute that shows itself is noise in an idle game. The notices in UI Requirements use the standard notice and screen styles of Guild screens (39). No art bible exists; nothing here needs one.

## Game Feel

The only feel target is **no hitch**. Collection (R7 stage 1) runs on the main thread between ticks and must cost at most `save_collect_budget_us` (4 ms, provisional) at p95 on the min-spec device with the max-roster fixture, so that a frame carrying a save stays within Sim core F6's half-frame sim share. Encoding, compression and I/O never run on the main thread except for the synchronous background/quit save, when no frame is being shown. The P1 spike measures collection and write time (OQ-5).

## UI Requirements

This system defines the facts each notice carries; Guild screens (39) and Localization (4) own layout and wording. All strings come from the always-available UI string set, because a save failure may coincide with a data failure (same rule as the Sim core fatal screen).

| Notice | Kind | Facts shown | Actions |
|---|---|---|---|
| Restored from an earlier save | Non-blocking banner, once | `last_saved_utc` of the loaded save as local time | Dismiss |
| Save from a newer version | Blocking screen | — | Update (store link), Quit |
| Save damaged | Blocking screen | That the damaged files were kept | Start a new guild, Quit |
| Cannot save | Non-blocking banner, persists until a save succeeds | "Storage full?" hint for 6106; generic for others | Dismiss (re-shown on the next failure) |
| Open elsewhere | Blocking banner | — | Reload, Quit |
| Load an older save | Extra action on the Sim core fatal screen (R18) | Time of the older save | — |

No stack traces, file paths or error codes beyond the code number are shown to players.

> **📌 UX Flag — Local save and migration**: This system has UI requirements. In Pre-Production, run `/ux-design` for these notices (or fold them into the Guild screens shell spec) **before** writing epics. Stories that reference this UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This document references | Target | Element | Nature |
|---|---|---|---|
| `snapshot_core`, `restore_core`, what the core saves, int64 as strings | `sim-core-and-tick-loop.md` | R14, AC-29, AC-29b | Rule dependency |
| `Failed`, `state_trusted`, recovery handed to Save | `sim-core-and-tick-loop.md` | R10, OQ-2 | Ownership handoff: answered in R9, R18 |
| `sim_version` single integer, bump rule | `sim-core-and-tick-loop.md` | R12 | Rule dependency (R11 step 7, R13) |
| Startup order and `seal()` | `sim-core-and-tick-loop.md` | R11 | Rule dependency (R11 step 8) |
| `GameClock.utc_s()`, absence from `last_saved_utc` | `sim-core-and-tick-loop.md` | R7 | Data dependency |
| Fatal screen and its actions | `sim-core-and-tick-loop.md` | UI Requirements | Extension: adds "Load an older save" (R18) |
| `snapshot_history`, `restore_history`, warning decision | `event-bus-and-history-log.md` | R11 | Rule dependency; warning decision answered (none) |
| `history_bytes_max` | `event-bus-and-history-log.md` | F3 | Formula input (F4) |
| `milestone_subjects_planned` | `event-bus-and-history-log.md` | Tuning Knobs, OQ-4 | Formula input (F4) |
| `content_hash`, stable IDs, `uid`, `UnknownContent`, liveness | `data-layer-and-content-pipeline.md` | R3, R6, R7, Edge Cases | Rule dependency; mismatch policy answered (R11 step 7) |
| `world_seed`, "only the seed is saved", `used_fallback` | `deterministic-rng.md` | R2, R11, API, OQ-4 | Data dependency; OQ-4 answered (R4) |
| Save-scumming, commit points | `deterministic-rng.md` | Edge Cases, OQ-6 | Open question (OQ-4) |
| `init_progress` refuses out-of-range levels | `xp-and-level-pacing-curve.md` | R9, OQ-5 | OQ-5 answered (R14) |
| Stamp format used by replay checks | `dev-tooling-and-parity-harness.md` | Dependencies | Rule dependency (R13, R16) |
| Save requirements and S8 module | `JX1_Tycoon_GDD.md` | §8.2, §12.5, §20 S8, §21 | Source of intent |
| Cloud conflict ("player chooses") | `JX1_Tycoon_GDD.md` | §8.1 | Ownership handoff to Account and cloud save (7) |

## Acceptance Criteria

Story types: **[Logic]** automated unit test (blocking), **[Integration]** integration test or documented device run, **[UI]** retained screenshot in `production/qa/evidence/`. `[PENDING: X]` means it needs system X or the engine port before it can run. Unless stated, tests use a fake `GameClock`, an in-memory or temp-directory file store, and a test feature with one section holding an int counter, a string and a `PackedInt64Array`.

**Format and encoding (R2, R4, R5, F1)**
- **AC-1 [Logic] (R2, F1)**: **GIVEN** a saved guild, **WHEN** the file is read, **THEN** bytes 0–3 are `JX1S`, byte 4 is `1`, bytes 5–36 equal SHA-256 of the decompressed payload, bytes 37–40 equal its length little-endian, and the rest decompresses with a standard gzip reader (Python `gzip`).
- **AC-2 [Logic] (F1)**: **GIVEN** a valid file, **WHEN** one byte of the compressed payload is flipped (and separately, one byte of the stored checksum), **THEN** the load of that file returns 6003 or 6004 and the file is unchanged.
- **AC-3 [Logic] (R5)**: **GIVEN** a section holding `2^63 − 1`, `−2^63`, `2^53 + 1` and a `PackedInt64Array` of `[0, −1, 2^62]`, **WHEN** saved and loaded, **THEN** the payload contains no JSON number token, the ints are decimal strings, the array is `{"i64le": ...}`, and all values are equal after restore. An empty array round-trips as `{"i64le": ""}`.
- **AC-4 [Logic] (R5, 6104)**: **GIVEN** a section whose `serialize()` returns a float at path `a.b[2]`, **WHEN** a save is requested, **THEN** it returns 6104, the error names the section and the path, and no file changes.
- **AC-5 [Logic] (R4)**: **GIVEN** a payload missing any one R4 key, or with `generation` as a JSON number, **WHEN** loaded, **THEN** 6005 for each case.

**Collecting and writing (R7–R10)**
- **AC-6 [Integration] (R7, Sim core R14)**: **GIVEN** a running core, **WHEN** a save is requested from inside a handler, while a hand-off is pending, and between ticks, **THEN** the first two return 6102 with no file change and the third writes generation `last + 1`.
- **AC-7 [Logic] (R7 coalescing)**: **GIVEN** a write in flight, **WHEN** five save requests arrive before it finishes, **THEN** exactly one further collection and write happen after it, and generations increase by exactly 2 in total.
- **AC-8 [Logic] (R8)**: **GIVEN** `autosave_interval_s = 60` and a fake monotonic clock, **WHEN** 60 s elapse while `catching_up` is true and catch-up clears 10 s later, **THEN** no save happens during catch-up and exactly one happens on the first frame after it clears.
- **AC-9 [Logic] (R8)**: **GIVEN** a new guild, **WHEN** creation completes, **THEN** generation 1 is on disk before the first tick. **GIVEN** a resolved Offline hand-off `[PENDING: Offline progress 31]`, **THEN** a save is written in the first frame after `skip_ticks` returns.
- **AC-10 [Integration] (R9)**: **GIVEN** a core forced into `Failed`, **WHEN** autosave and an explicit save are requested, **THEN** both return 6101, the files on disk are byte-identical to before the failure, and `slot0.crash` exists with `failed_at_tick` and `fail_code` (R18).
- **AC-11 [Logic] (R9, 6103)**: **GIVEN** a section whose `check()` returns `[1234]`, **WHEN** three consecutive saves are requested with `save_check_fail_alert = 3`, **THEN** each returns 6103, no file changes, and the "cannot save" notice is raised exactly once, on the third.
- **AC-12 [Logic] (R10 kill points)**: **GIVEN** a fault-injecting file store, **WHEN** the write is aborted after each of steps 1, 2, 4 (after each individual rename) and 5, **THEN** for every abort point a fresh boot loads a save whose generation is either the old or the new one, never fails, and never loads a torn file.
- **AC-13 [Logic] (R10 rotation)**: **GIVEN** `save_backup_generations = 3`, **WHEN** 6 saves are written, **THEN** `sav` has gen 6, `bak1`–`bak3` have gens 5, 4, 3, and no `bak4` exists.
- **AC-14 [Integration] (R6, R5) [PENDING: each stateful feature]**: **GIVEN** the full feature set registered with a max-roster fixture guild, **WHEN** a save is written, **THEN** it succeeds with no 6104, and every section is present in the payload.
- **AC-15 [Logic] (R10 checkpoints, F5)**: **GIVEN** a fake UTC clock and `save_checkpoint_interval_s = 3600`, `count = 2`, **WHEN** saves are written every 60 s for 3 h, **THEN** `ckpt1` and `ckpt2` exist with `last_saved_utc` about 3,600 s apart, and no third checkpoint exists. **GIVEN** a UTC step backwards, **THEN** no checkpoint is taken at that save.
- **AC-16 [Logic] (R10 step 3)**: **GIVEN** a loaded guild at gen 10, **WHEN** another writer replaces `slot0.sav` with gen 11 and this instance saves, **THEN** it returns 6108, `slot0.sav` is still gen 11, `slot0.orphan` holds this instance's file, and autosave stops.
- **AC-17 [Logic] (6106)**: **GIVEN** a store that fails every write with "no space", **WHEN** 3 autosaves run with `save_write_fail_alert = 3`, **THEN** all return 6106, the previous files are intact, no `slot0.tmp` remains, and the notice is raised once.

**Loading (R11, R12, R15, F2)**
- **AC-18 [Integration] (S8 determinism; RNG AC-18) [PENDING: Sim core 1 port, per-event seeding]**: **GIVEN** a guild with a fixed `world_seed` and command log, **WHEN** run A runs 2 h of game time continuously, and run B runs 1 h, saves, is loaded into a new instance and runs 1 h more with the same remaining commands, **THEN** the final state hash and the event stream of the second hour are identical. **Negative control:** zeroing one saved ordinal counter before the load gives a different hash.
- **AC-19 [Logic] (F2)**: **GIVEN** candidates `tmp` gen 412, `bak1` 411, `bak2` 410, `ckpt1` 380 and no `sav`, **WHEN** the slot boots, **THEN** `tmp` loads and is renamed to `sav`. **GIVEN** `sav` gen 412 with a bad checksum and `bak1` gen 411 valid, **THEN** `bak1` loads, the "restored" notice shows `bak1`'s time, the bad file is in `damaged/`, and gen 413 is written.
- **AC-20 [Logic] (R11 step 4, R15)**: **GIVEN** a `sav` with `schema_version = SAVE_SCHEMA_VERSION + 1` (and separately `sim_version = SIM_VERSION + 1`), **WHEN** the slot boots, **THEN** the load returns 6001 (6002), the state is `Locked`, a save request returns 6109, the new-guild action is unavailable, and every file is byte-identical afterwards.
- **AC-21 [Logic] (R15)**: **GIVEN** three candidates all with bad checksums, **WHEN** the slot boots, **THEN** the state is `Damaged`; **WHEN** the player chooses "start a new guild", **THEN** all three files are in `damaged/` before generation 1 of the new guild is written.
- **AC-22 [Logic] (R11 step 6)**: **GIVEN** a save with a section `foo` that no feature registered (and separately, a registered section missing from the save), **WHEN** loaded, **THEN** 6008, and the next candidate is tried on a fresh instance.
- **AC-23 [Integration] (R11 step 8) [PENDING: Data layer 3 port]**: **GIVEN** a section that references the ID `itm_does_not_exist`, **WHEN** loaded, **THEN** 6009, the half-restored instance is discarded, and the next candidate loads on a new instance.
- **AC-24 [Integration] (R11 step 8, Event bus R11)**: **GIVEN** a save whose history snapshot's last record tick equals the core tick, **WHEN** loaded, **THEN** 6010. **GIVEN** a valid save after `history_ring_cap` was lowered, **THEN** it loads, `trimmed_count > 0` is logged, and no player notice is raised.
- **AC-25 [Logic] (R11 step 1, 6011)**: **GIVEN** a file whose header claims a payload of `save_max_uncompressed_bytes + 1`, **WHEN** loaded, **THEN** 6011 is returned without decompressing (peak memory below 2× the file size).

**Versions and migration (R11 step 7, R13, R14, R17)**
- **AC-26 [Logic] (R11 step 7, R13)**: **GIVEN** a save written with `sim_version = 1` and content hash H1, **WHEN** loaded by a build with `SIM_VERSION = 2` and hash H2, **THEN** `restore_core` succeeds, the payload and core `sim_version` are 2, and `lineage` ends with `{from_tick: <core tick>, sim_version: "2", content_hash: H2, schema_version: …}`. **GIVEN** the same build loads it again, **THEN** no further entry is appended.
- **AC-27 [Logic] (R13 cap)**: **GIVEN** `save_lineage_cap = 16` and a save with 16 entries, **WHEN** a 17th is appended, **THEN** the list has 16 entries and the oldest was dropped.
- **AC-28 [Logic] (R14 chaining)**: **GIVEN** a v1 fixture and steps registered for `members` 1→2 and 2→3 and for a new section `tower` at 2→3 (receiving `null`), **WHEN** loaded by a v3 build, **THEN** the steps run in order 1→2 then 2→3 (`members` before `tower`), `tower` exists with its initial data, and `schema_version` is `"3"`. **GIVEN** a step that returns `null` for a removed section, **THEN** the section is absent and the load succeeds.
- **AC-29 [Logic] (R14 failure)**: **GIVEN** a migration step that throws, **WHEN** a v1 save loads, **THEN** 6007, the file on disk is unchanged, and the next candidate is tried.
- **AC-30 [Logic] (R14 pre-migration copy)**: **GIVEN** a v1 save loaded by a v2 build, **WHEN** the first save after load completes, **THEN** `slot0.pre_v1.sav` is byte-identical to the original v1 file. **GIVEN** a later v2→v3 migration and save, **THEN** `pre_v2` exists and `pre_v1` is deleted.
- **AC-31 [Logic] (R17)**: **GIVEN** the CI suite, **WHEN** it runs, **THEN** every file in `tests/fixtures/saves/` loads in the Python reference to the current schema with code 0. **GIVEN** a build whose `SAVE_SCHEMA_VERSION` is N with no fixture at version N − 1, **THEN** CI fails.
- **AC-32 [Integration] (R16) [PENDING: engine port]**: **GIVEN** the same fixture guild, **WHEN** the Python reference writes a save and the port loads it, and vice versa, **THEN** both loads return 0 and produce the same core state and the same section trees.

**Crash recovery and cloud hand-off (R18, R19)**
- **AC-33 [Integration] (R18)**: **GIVEN** a test feature that fails at tick 500 after loading gen 40, with `crash_repeat_threshold = 2` and `ckpt1` at gen 20, **WHEN** the player reloads and it fails again at tick 500, **THEN** the marker's `count` is 2 and the fatal screen state offers "Load an older save"; choosing it loads gen 20; the next successful save deletes the marker.
- **AC-34 [Logic] (R19) [PENDING: Account and cloud save 7]**: **GIVEN** a local guild at gen 50 and an imported blob at gen 70, **WHEN** `import_blob` succeeds, **THEN** the local file is kept as `slot0.replaced.sav`, the new current file is gen 71, and `export_current` returns its bytes and header facts. **GIVEN** a blob with a bad checksum, **THEN** `import_blob` returns 6003 and nothing on disk changes.

**Performance and UI**
- **AC-35 [Integration] (Game Feel) [PENDING: engine port, P1 spike device]**: **GIVEN** the max-roster fixture on the min-spec device, **WHEN** 100 autosaves are measured, **THEN** p95 collection time ≤ `save_collect_budget_us` and no frame containing a save exceeds the Sim core F6 frame budget.
- **AC-36 [UI] [PENDING: Guild screens 39, Localization 4]**: **GIVEN** each notice in UI Requirements forced in a dev build, **WHEN** it shows, **THEN** a retained screenshot exists in `production/qa/evidence/` for each, in vi and en.

*QA lens applied (`references/lens-qa-lead.md`).* Coverage: R2, R4, R5 (AC-1–5); R6 (AC-14, AC-22); R7 (AC-6, AC-7); R8 (AC-8, AC-9); R9 (AC-10, AC-11); R10 (AC-12, AC-13, AC-15–17); R11 (AC-5, AC-20, AC-22–26); R12/F2 (AC-19); R13 (AC-26, AC-27); R14 (AC-28–30); R15 (AC-20, AC-21); R16 (AC-32); R17 (AC-31); R18 (AC-33); R19 (AC-34); R20 codes throughout; F1 (AC-1, AC-2); F3 is a derived bound, verified by AC-8 and AC-13 together (no separate test); F4 is an estimate, checked by AC-14's measured size against `save_size_warn_bytes` (gap: no AC asserts F4's numbers until Member model defines its section); F5 (AC-15, AC-33). Cross-system: AC-6, AC-18, AC-23, AC-24, AC-26, AC-34.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **PROVISIONAL: Data layer (3)** — add the Tuning Knobs keys to `data/config.csv` with validator ranges. Assumed: they are ordinary `config` rows read once at boot. | Data layer (3) | Before S8 implementation |
| OQ-2 | Should a crash loop offer "skip the failing stretch" (a forced hand-off past `failed_at_tick`) in addition to "Load an older save"? That needs a core primitive, which would change Sim core R10. Not in MVP. Also: should the host count GDScript script errors through an engine logger hook and mark state untrusted (Sim core R10, API unverified for 4.7)? | Local save (6) with Sim core (1) | After the P1 spike |
| OQ-3 | **PROVISIONAL: Leaderboards (35)** — `lineage` entries `{from_tick, sim_version, content_hash, schema_version}` capped at 256 are enough to judge replay comparability. | Leaderboards (35) | When Leaderboards is designed |
| OQ-4 | Player-gamble commit points: should Enhancement (24), Recruitment (15) and Crafting (28) force a save when an attempt is dispatched (RNG OQ-6)? This system supports it through an ordinary save request; the decision is theirs. | RNG (2) with 15, 24, 28 | When those GDDs are written |
| OQ-5 | P1 spike measurements: collection p95 and write time on min-spec (AC-35); confirm `save_collect_budget_us`. Confirm Godot 4.7 for: standard gzip from `PackedByteArray.compress` (or a different API), atomic rename behaviour on Android and Windows, synchronous work allowed in the OS-pause notification, thread use for the worker. **NOT SOURCEABLE** — no `core.md` exists under `docs/engine-reference/godot/modules/`; save/file APIs are not covered by the pinned engine reference, so feasibility was not checked against 4.7. The only covered item is `FileAccess.store_*` returning `bool` since 4.4 (breaking-changes.md), which the ADR must check. | technical-director (ADR) | Before implementation |
| OQ-6 | Multiple guild slots: out of scope; one slot matches one cloud slot (GDD §8.1). Revisit only if a "second guild" feature is proposed. | Producer | Post-launch |
| OQ-7 | **PROVISIONAL: Account and cloud save (7)** — R19's `export_current`/`import_blob` and the `summary` fields (tick, guild level, member count, sum of member levels, total gold) are what 7 needs to show a conflict and measure divergence. | Account and cloud save (7) | When 7 is designed (Alpha) |
| OQ-8 | **PROVISIONAL: every stateful feature** — each registers one section via R6 and supplies `summary()` numbers it owns. Member model (8) sets the real `member_bytes` for F4. | Member model (8) and feature owners | As each GDD is written |
| OQ-9 | **PROVISIONAL: Guild screens (39)** — the notices in UI Requirements fit its notice/banner styles; the store link on "update" is per platform. | Guild screens (39) | When 39 is designed |
| OQ-10 | Should the save be encrypted or obfuscated to discourage casual editing? Recommended no (R3: integrity, not secrecy; Leaderboards replays). Logged for `/security-audit`. | security-engineer | Before Alpha |

**Engine feasibility note.** Domain: Core (Persistence). No `docs/engine-reference/godot/modules/core.md` exists, so the file, compression, threading and notification APIs this design relies on were not verified against Godot 4.7. Every engine-specific choice is deferred to an ADR (OQ-5). No ADR exists in `docs/architecture/` for this system.
