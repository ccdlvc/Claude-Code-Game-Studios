# Data Layer and Content Pipeline

> **Status**: Designed (pending re-review) — revised 2026-11-16 after `/design-review` (NEEDS REVISION, 3 blockers applied; see `design/gdd/reviews/data-layer-and-content-pipeline-review-log.md`)
> **Author**: user + Claude
> **Last Updated**: 2026-11-16 (revision round: uid ledger, drop-row identity, per-key parameter schema)
> **Last Verified**: 2026-11-16
> **Implements Pillar**: none yet (no `design/gdd/game-pillars.md`)
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief to check against; Player Fantasy is anchored to locked `JX1_Tycoon_GDD.md` lines instead. Re-run after pillars exist.

## Summary

The data layer carries all game content from the designer's spreadsheets to the simulation. The pipeline is CSV in `data/`, then a validator that refuses bad data, then typed, read-only tables (the R2 inventory, 19 today) keyed by permanent IDs. Players never see it. What they feel is that their guild survives every update, that offline and leaderboard results come from exactly the content that was tested (a content hash proves which content was used), and that each wave of content arrives whole and never leaks early. Read this GDD before designing any system that reads content tables, uses content IDs in RNG event keys, or stores content in saves.

> **Quick reference** — Layer: `Foundation` · Priority: `MVP` · Key deps: `None` (soft: Localization, for the validator's name-coverage check) · Feasibility: NOT SOURCEABLE (engine pinned to Godot 4.7 GDScript, but `docs/engine-reference/godot/modules/` has no core or scripting module — OQ-6)

## Overview

The data layer and content pipeline is the path that carries every piece of game content from the spreadsheets the designer edits into the simulation. Content covers schools, skills, zones, monsters, items, drop tables, recipes, buildings, quests and rebirth tiers, plus every tunable number in `config.csv` and `sim_params.csv`. The pipeline has three stages, following JX1_Tycoon_GDD.md §12.3. The designer authors rows in a spreadsheet and exports them as CSV into `data/`. `tools/content_validator.py` then checks ids, cross-references, wave rules and balance invariants, and refuses the build on any error. Finally, the loader (`sim/data.py` in the Python reference, and its port in the engine) reads the validated tables once at startup into read-only content tables. Each table is keyed by a stable, immutable string ID, so every other system looks content up by ID and never by row position or display name. Display names are not part of content tables; they live in `i18n/names_*.csv`, keyed by the same IDs (§3.3, §16), so renaming something never touches code or saves.

The system has no player-facing surface and makes no runtime decisions. Its job is to guarantee four things to the roughly two-thirds of systems that read from it:

- What the simulation runs on is exactly what the validator approved.
- An ID means the same thing in every build and every save.
- Only content whose wave has shipped is live.
- The Python reference and the engine port load identical tables, which the cross-implementation parity guarantee of Deterministic RNG (R12) depends on.

Without it, content would be hard-coded, which §20 rule 1 forbids. Every number change would need a code change. The balance simulator (§4.4) could no longer prove that the numbers it tested are the numbers players get.

*No ADR is cited. `docs/architecture/` holds no ADR for this system yet, so the implementation approach (file format at runtime, load timing on mobile, engine resource type) is left to `/architecture-decision` and is not set here.*

## Player Fantasy

**Indirect.** Players never see this system. They feel three promises it keeps, and each promise rests on a locked `[CHỐT]` line of `JX1_Tycoon_GDD.md`. There are no game pillars yet, so none is quoted. Re-anchor these once `design/gdd/game-pillars.md` exists.

**1. "My guild survives every update."** A content patch arrives. The player opens the game, and every member is still there with the same gear, the same school, the same rebirth count and the same history. Nothing is renamed out from under them, and no item turns into something else. The anchor is §16: *"Code và data chỉ dùng ID bất biến … Đổi tên không đụng code, không đổi save"* (code and data use only immutable IDs; renaming touches neither code nor saves). The design must therefore treat IDs as permanent. An ID is never reused, never repointed, and never deleted while any save could hold it.

**2. "The numbers are honest."** The player returns after up to twelve hours (the offline cap) to an offline report, or checks a leaderboard rank, and believes it. The tables that produced those results are the tables the balance simulator measured and the server verifier replays. The anchor is §3.2: one deterministic, headless core shared by realtime play, offline fast-forward, the balance simulator and leaderboard checks. The design must therefore make the running build's content provably identical to the validated content, so the build can name exactly which tables it runs (F1) and the RNG replay rule (R12 of Deterministic RNG) has something to check against.

**3. "A new wave opens the map."** When Wave 2 goes live, five new schools, new zones and their monsters, drops and recipes appear together, as one event the player can feel. Before that day, none of it appears: no Wave 2 item in a Wave 1 drop and no Wave 2 recipe in a Wave 1 forge. The anchor is §12.2: *"Ra mắt theo wave nhưng plan đầy đủ cho tất cả ngay từ đầu"* (launch in waves, but plan everything up front). The design must therefore make wave gating total, so no live row can reach a row that is not live.

What breaks each promise: a reused or repointed ID breaks 1; content that differs from what was validated breaks 2; a live row that references unreleased content breaks 3. Sections C and E are written against those three failures.

## Detailed Design

### Core Rules

**Terms.** A *table* is one CSV file in `data/`. A *content table* holds things the game contains: schools, zones, items and so on. A *parameter table* holds named numbers: `config.csv`, `sim_params.csv` and `sim_roles.csv`. A *row key* is the column, or column pair, that identifies a row. The *loader* is the runtime code that reads tables (`sim/data.py` in the Python reference, plus its engine port). The *validator* is `tools/content_validator.py`, the build-time gate.

**R1 — The pipeline.** Content moves one way only: spreadsheet → CSV in `data/` → validator → loader → read-only tables. Each step works as follows:
- The spreadsheet is the authoring surface. The CSV in `data/` is the source of truth, and it is what is committed, reviewed, diffed and hashed.
- Generator scripts (`tools/gen_a.py`, `gen_b.py`, `gen_c.py`) are authoring aids that write CSV. Their output goes through the same validator as hand-written rows.
- Nothing at runtime writes to `data/`.

**R2 — Table inventory.** The loader loads **every table in this inventory** (19 today; tables approved below join it when built). Wherever this GDD or another says "all tables", it means this inventory, never a fixed count. A table that the validator checks and the loader does not load is a defect. Today `recipes`, `buildings`, `building_meta`, `enhance`, `quests`, `rebirth` and `traits` are validated but not loaded. Each table's row key is fixed:

| Table | Kind | Row key | `wave` column |
|---|---|---|---|
| `schools` | content | `id` | yes (exists) |
| `skills` | content | `id` | yes (rename `unlock_wave` → `wave`) |
| `traits` | content | `id` | add |
| `zones` | content | `id` | yes (exists) |
| `grounds` | content | `id` | add |
| `monsters` | content | `id` | add |
| `golden_bosses` | content | `id` | yes (exists) |
| `materials` | content | `id` | add |
| `items` | content | `id` | add |
| `drop_tables` | content | (`table_id`, `ref`): one row per entry of a group; a group lists each `ref` at most once (validator ERROR otherwise; true of all 315 rows today) | add, per row |
| `recipes` | content | `id` | add |
| `building_meta` | content | `id` | yes (exists) |
| `buildings` | content | (`building_id`, `level`) | add, per level row |
| `enhance` | content | `level` | add, per level row |
| `quests` | content | `id` | add |
| `rebirth` | content | `no` | yes (exists) |
| `config` | parameter | `key` | none |
| `sim_params` | parameter | `key` | none |
| `sim_roles` | parameter | `role` | none |

Adding a table means adding a row here, a schema (R4) and a loader entry. Nothing else in the pipeline needs to change.

**R3 — Stable IDs.** Every `id` and `table_id` value is a stable ID. The rules for stable IDs are:
- **Format:** lowercase ASCII `[a-z0-9_]`, 1–48 characters. Today's longest ID is 36 characters.
- **Global uniqueness:** an ID is unique across all tables, not only within its own, because `i18n/names_*.csv` and the `uid` space (R6) are single namespaces. All 1,899 current IDs already satisfy this.
- **Immutability:** once an ID has shipped in any build, it is never renamed, never reused for different content, and never deleted. Content that is withdrawn stays in its table, gets `retired=true` (R5), and stops being live. Its row remains so that old saves still resolve.
- **Meaning-free:** systems look content up only by ID. Row order, display names and any parsing of an ID string (for example reading `kim` out of `kim_1`) are never used to find or classify content. An ID's components are a human convenience; the row's columns are the facts.

**R4 — Typed, frozen tables.** Each table has one declared schema that both the loader and the validator read. A schema lists every column with its type:
- **Column types:** `int`, `float`, `ppm`, `bool` (`true`/`false` only), `str`, `enum(<values>)`, `ref(<table>)`, `list(<type>)` written `a;b;c`, and `map(<type>)` written `k=v;k=v`.
- **Probabilities are integers.** Every column whose value is used directly as a draw probability has type `ppm`: an integer from 0 to 1,000,000, with the column suffix `_ppm`. It goes through `chance_ppm` (Deterministic RNG F6), never through a float. A float parsed from CSV can differ by one ulp between implementations and flip a draw at the boundary; an integer cannot. Today two columns qualify: `drop_tables.chance` becomes `drop_chance_ppm`, and `enhance.success_pct` becomes `success_ppm`. The `_pct` multipliers that are not draw probabilities, such as `guild_tax_pct` and `flee_hp_pct`, stay `float`. A probability computed at run time from those multipliers belongs to the owning system (RNG F6 `chance(p)`).
- **Conversion at load:** each value is converted once, when it is loaded. A packed column (`stats`, `effects`, `monster_pool`, `inputs`, `cost_mats`, `rewards`, `mechanics`, `conflicts`, `ai_skills`, `reward_items`) becomes a real list or map at load time. No system re-parses a string afterwards.
- **Failure:** a value that does not convert fails the load (see States).
- **Parameter tables are typed per key.** `config` and `sim_params` have one `value` column, so their schema is a per-key table in the shared schema module: `key → (type, range, owning GDD)`, using the column types above (`int`, `float`, `ppm`, `bool`, `str`, `enum`, `list(<type>)`). Each `value` is converted once at load by its key's declared type, like any column. The validator rules:
  - a key in the CSV that the schema does not declare: ERROR (`unknown key`)
  - a key the schema declares that the CSV lacks: ERROR (`missing key`). There are no schema defaults, for the same reason as Edge Cases (empty cell): a missing value must never quietly become a permissive one
  - a value outside its declared type or range: ERROR naming the key
  - a key ends in `_ppm` exactly when its type is `ppm`; a `_pct` key is never `ppm`

  A key approved in a GDD (Approved schema additions) enters the per-key schema in the same change as its CSV row and its validator rule. `sim_roles` is an ordinary typed table (one column per multiplier) and needs no per-key schema.
- **Frozen:** after load, every table, row, list and map is read-only for the life of the process. A system that needs mutable state copies values into its own state. It never edits the content table.
- **Deterministic order:** every table, every `drop_tables` group and every `list(ref)` or `map(ref)` cell is exposed in ascending `uid` order (R6), never in file row order. That is the order RNG F5 requires for `choice` and for weighted picks. File order is only a convenience for the people editing the spreadsheet, so reordering rows changes nothing the simulation does.
- **Constants:** the constants `sim/data.py` and the validator duplicate today move into data. Level caps and the rebirth-to-wave mapping come from `rebirth.csv` (`new_level_cap`, `wave`). The element set and the Five Elements counter cycle are declared once in the schema module. Neither the loader nor the validator holds a private copy.

**R5 — Waves and liveness.** Every content table has a `wave` column (an integer of 1 or more). A content row may also have `retired` (bool, default `false`). How waves work:
- **Live wave:** the live wave `W_live` is read from `config.csv` key `live_wave`.
- **Liveness:** a row is *live* when F2 holds.
- **Gating is total:** the loader loads **every** row of every wave, because the balance simulator, saves and the validator need all of them, and it answers liveness through a single query. Systems that offer content to the player (recruitment, drops, recipes, shops, quests, zone access) ask that query. They never compare `wave` themselves.
- **No forward references:** a live row may reference only live rows. The validator enforces this statically as F3: every reference points to a row of equal or earlier wave. So unreleased content cannot leak through a drop table, recipe input, monster pool or skill prerequisite.
- **Wave-derivation checks:** the validator keeps its existing checks and generalises them. A skill's wave equals the larger of its school's wave and the wave of its rebirth tier. A zone's wave equals the wave of its rebirth requirement.

**R6 — Content `uid`s.** Every content table carries an integer `uid` column, which is the column Deterministic RNG R5 requires and assigns to this system. In `drop_tables` each row has its own `uid`. The rules:
- **Range and reserved value:** `uid` is an integer from 1 to 2³²−1. The value 0 (`content_id_none`) means "none" and is never assigned.
- **Global uniqueness:** one namespace across all tables, the same as IDs (R3), so a `uid` alone identifies a row anywhere: in an event key, in a save, or in a log.
- **Append-only:** a new row gets the next unused `uid` (F4). A row's `uid` is never changed, never reused for another row, and never freed. That includes retired rows, because retired rows stay in their tables (R3), and deleted rows, because their ledger entry stays (below).
- **The `uid` ledger.** `data/meta/uid_ledger.csv` (columns `uid`, `table`, `row_key`) is the permanent record of every `uid` ever assigned, one line per assignment, in ascending `uid` order. It is committed with the tables. It is not a content table: it is outside the `data/*.csv` glob (Edge Cases, unknown table), the loader does not read it, and it is not part of F1, because it changes no outcome. Only the uid helper writes it, and only by appending.
- **Purpose:** content IDs enter RNG event keys as their `uid` (RNG R5). Lists are ordered by `uid` (R4, RNG F5). Saves may store a `uid` wherever a compact ID helps.
- **Validator checks, against the ledger (no git needed):** ERROR if any row lacks a `uid`; if any `uid` is used twice; if a row's (`table`, row key, `uid`) does not match its ledger line (a changed `uid`, or a `uid` moved to another row); or if a row has a `uid` the ledger does not hold. A ledger line whose row no longer exists is a deleted row: WARN (`removed row`) before launch and ERROR after (OQ-2). Its `uid` stays reserved.
- **Validator check, against history:** the ledger is append-only. The committed ledger at the comparison base (Dev tooling R13: the merge-base with `main`, or the pre-push tip on `main`) must be a byte prefix of the working ledger. A changed or removed ledger line is an ERROR. A base with no ledger yet (the first commit that adds it) passes. Without a git checkout or a resolvable base, this one check reports **NOT ASSESSED** by name (Dependencies) and every other check still runs.
- **Authoring:** the uid helper fills empty `uid` cells using F4 and appends one ledger line per assignment, so authors never pick numbers by hand.

**R7 — Content version.** At load, the loader computes the content hash F1 over the exact bytes of every inventory table (R2). How the hash is used:
- **Recorded:** the hash is kept with every save and every leaderboard submission, so Deterministic RNG's replay rule (R12) knows which content a run used.
- **Matching in the reference core:** the Python reference and the engine port must produce the same hash from the same files.
- **Mismatch handling:** what a mismatch means for an old save belongs to Local save and migration (6).

**R8 — Validator as the build gate.** The validator has three tiers of check, and a build or export cannot proceed on any ERROR:
- **Structural:** schema, types, row keys, ID format and uniqueness, references, `ppm` ranges, and `uid`s.
- **Content rules:** wave derivation and forward references.
- **Balance invariants:** the existing per-table rules, such as "10 schools, 5 in Wave 1, one buff school in Wave 1", and the gold-sink and XP-pacing checks.

Its output and exit codes:
- An ERROR exits 1. A WARN is printed and does not fail.
- Every message names the file, the line (or ID) and the column involved.
- The loader repeats the structural checks only. It does not repeat the balance checks, because a shipped build trusts the gate that produced it.

**R9 — Display text is not content.** Tables hold no player-facing text. Names, short names and descriptions live in `i18n/names_*.csv` and `names_items_*.csv`, keyed by stable ID, and are owned by Localization (4). The `notes` and `theme` columns are designer notes and are never shown to the player. The data layer's only i18n duty is the validator's coverage check: every school, zone, boss monster, material, item and building has a non-empty name in each shipped language. Skill names are not yet covered (§17.2), which is a known gap and is tracked in Open Questions.

**R10 — Load once.** Content is loaded once, before the first simulation tick, and is never reloaded while a world is running. A developer hot-reload is allowed only in dev tooling (43), and only between runs: it restarts the simulation and never mutates live tables.

### Approved schema additions (2026-11-16)

**User decision 2026-11-16:** every schema proposal in the GDDs below is approved in principle. Nothing is added now. Each addition lands when the owning system's story is built, in the same change as its validator rule (R8) and, for a save section, its Local save section contract (serializer, restorer, migration step, fixture). The owning GDD stays the authority on names, types, defaults and ranges.

**New content tables**

| Table | Owning GDD |
|---|---|
| `feature_flags.csv` | `entitlement-and-feature-flags.md` |
| `achievements.csv` | `quests-and-achievements.md` |
| `npc_guilds.csv` | `jianghu-free-agents-and-npc-guilds.md` (R3) |
| `elder_buffs.csv` | `rebirth-and-ascension.md` (R8, OQ-13) |
| `iap_products.csv` | `in-app-purchases.md` |
| `onboarding_steps.csv` | `onboarding-and-tutorial.md` |
| `analytics_events.csv` | `analytics.md` |

**New `config.csv` / `sim_params.csv` keys** (each GDD's Tuning Knobs and its schema Open Question list them): `sim_params.csv` — `arena.md`, `combat.md`, `endless-tower.md` (incl. `tower_endless_from`, `tower_run_floor_max`). `config.csv` — `ca-pa-and-traits.md`, `command-layer.md`, `crafting-and-recipes.md`, `gold-economy.md`, `items-and-loot-tables.md`, `golden-boss-and-guild-raid.md`, `jianghu-free-agents-and-npc-guilds.md` (`fa_*`, `npc_*`, `inv_*`, `sign_*`, `poach_*`, `return_*`), `guild-screens.md`, `guild-and-buildings.md`, `guild-market-and-trade-orders.md`, `quests-and-achievements.md`, `recruitment.md`, `retention-leaving-and-negotiation.md`, `local-push-notifications.md`, `onboarding-and-tutorial.md`, `leaderboards-and-anti-cheat.md`, `member-state-machine.md` (OQ-2), `party.md`, `skills.md` (incl. `academy_gate_enabled`), `utility-ai.md`, `sim-core-and-tick-loop.md`, `in-app-purchases.md`, `ads.md`, `rebirth-and-ascension.md` (`elder_trait_share_ppm`, `elder_trait_categories`, `elder_buff_cap_ppm`), `settings.md` (`settings_*`, `a11y_text_scale_*`; whether host-service keys live in `config.csv` stays Settings OQ-2).

**New save sections:** `arena` (`arena.md`), `tower` (`endless-tower.md`), `crafting` (`crafting-and-recipes.md`), `recruitment` (`recruitment.md`), `onboarding` (`onboarding-and-tutorial.md`), `entitlement` (`entitlement-and-feature-flags.md`), `ranked_log` (`leaderboards-and-anti-cheat.md`), `ai_text` (`ai-text-layer.md`), plus the sections that `party.md`, `quests-and-achievements.md` and `retention-leaving-and-negotiation.md` register.

**Withdrawn:** the `bld_hq` effect key `elder_slots` proposed by Rebirth (23) is not needed (Elders are unlimited, user decision 2026-11-16).

### States and Transitions

The loader has four states. There is no partial state: either every table is loaded and checked, or none is usable.

| State | Meaning | Can systems read tables? |
|---|---|---|
| `Unloaded` | Process started, nothing read | No |
| `Loading` | Reading files, converting types, building indexes, computing F1 | No |
| `Ready` | Every inventory table (R2) loaded, structural checks passed, hash known | Yes, read-only |
| `Failed` | A file is missing or unreadable, a value fails conversion, a key is duplicated, a reference is dangling, or a row is missing its `uid` | No |

| From | To | Trigger |
|---|---|---|
| `Unloaded` | `Loading` | Startup calls load |
| `Loading` | `Ready` | Every table and check succeeded |
| `Loading` | `Failed` | First fatal error. The loader reports *every* error it can find in that pass, not only the first, and then stops |
| `Failed` | `Loading` | Only a process restart (shipped build) or a dev-tooling reload (43) |
| `Ready` | — | Terminal for the process. Tables never change (R10) |

`Failed` in a shipped build is a fatal startup error, shown as a "game data is damaged — reinstall" message (UI Requirements). The game never runs on partial content.

### Interactions with Other Systems

| System | Direction | What flows | Owner of the interface |
|---|---|---|---|
| Deterministic RNG (2) | out | Content `uid`s used as event-key components (RNG R5); lists in `uid` order (RNG F5); `_ppm` probabilities (RNG F6) | This system owns the `uid` column, the `ppm` type and their validation; RNG owns the key and draw rules |
| Sim core and tick loop (1) | out | `Ready` tables before tick 1; `config` and `sim_params` values; the F1 hash | This system |
| Schools (20), Skills (21), XP curve (22), Items and loot (26), Crafting (28), Guild and buildings (30), Enhancement (24), Quests (25), Rebirth (23), CA/PA and traits (9), Zones and hunt (11), Golden Boss raid (14), Combat (10) | out | Typed rows by ID, liveness query (F2) | This system owns lookup and liveness; each feature owns what its rows *mean* |
| Localization (4) | sibling | Shares the stable-ID namespace; the validator checks name coverage | Localization owns the text; this system owns the IDs |
| Local save and migration (6) | out | Stable IDs or `uid`s in saves; F1 hash stamped on saves | Save owns the format and the mismatch policy |
| Leaderboards and anti-cheat (35) | out | F1 hash in each submission, so the server replays with the same content | Leaderboards owns verification |
| Dev tooling and parity harness (43) | both | Balance simulator and calibrator read the same loader. Generators write CSV. The validator runs in CI. The parity harness compares the Python and engine loaders' F1 hash | Dev tooling owns the tools; this system owns the schema they share |

*Engine-side implementation (CSV parsed at runtime vs a pre-built bundle, resource type, mobile load time) → becomes an ADR. This GDD fixes only the behaviour above.*

## Formulas

This system defines no balance numbers. Its formulas are the integrity rules that Core Rules R5–R7 rely on. Every gameplay number lives in a table and is owned by the GDD of the system that reads it.

### F1 — Content hash

The content_hash formula is defined as:

`content_hash = SHA-256( ‖ over f in sorted(P) of [ utf8(f) ‖ 0x00 ‖ u64_le(len(norm(f))) ‖ norm(f) ] )`

`norm(f) = bytes of f with one leading UTF-8 BOM (EF BB BF) removed, then every CR LF and every lone CR replaced by LF`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| P | set of paths | one per R2 inventory table (19 today) | constant (R2 inventory) | Repo-relative paths with `/` separators, e.g. `data/items.csv`. Sorted by byte value. The `uid` ledger (R6) is not in P |
| utf8(f) | bytes | 1–64 bytes | calculated | The path string encoded as UTF-8 |
| len(norm(f)) | u64 | 0 – 2⁶⁴−1 | calculated | Length of the normalised file, little-endian, so a byte cannot slide from one file into the next |
| norm(f) | bytes | any | data file | File contents after BOM strip and newline normalisation |
| content_hash | 32 bytes | — | calculated | Written as 64 lowercase hex characters in saves and submissions |

**Output range:** any 256-bit value. The hash changes if any table changes, including whitespace and row order, even though row order does not change any outcome (R4). It does not change for a BOM or a CRLF checkout. To stop most CRLF checkouts at the source, `.gitattributes` declares `data/*.csv text eol=lf`. Normalisation is the backstop.

**Example:** `data/zones.csv` saved by a spreadsheet as `EF BB BF` + `id,order…\r\n…` and the same file checked out with LF endings both normalise to `id,order…\n…`, contribute the same framed bytes, and give the same `content_hash`. Swapping the order of two rows in `items.csv` gives a different hash but no different outcome, because iteration is in `uid` order (R4). The hash errs on the side of reporting a change.

### F2 — Liveness

The content_live formula is defined as:

`content_live(r) = (r.wave ≤ W_live) ∧ ¬r.retired`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| r.wave | int | 1 – W_max | data file | The row's `wave` column (R5) |
| W_live | int | 1 – W_max | data file (`config.csv` key `live_wave`) | Highest wave released in this build |
| W_max | int | 3 today | calculated | Largest `wave` in any content table |
| r.retired | bool | true/false | data file (`retired`, default false) | Withdrawn content: still resolvable, never offered |
| live(r) | bool | true/false | calculated | Whether systems may offer this row to the player |

**Output range:** true or false. The validator requires `1 ≤ W_live ≤ W_max`, because `W_live = 0` makes nothing live and the game cannot start. A `W_live` above `W_max` would make everything live, which is harmless, but it is still rejected because it means the config and the content disagree. Liveness affects only what is *offered*. A non-live row is still loaded and still resolves by ID (R5, Edge Cases).

**Example:** with `live_wave = 1`, school `kim_1` (`wave = 1`) is live, a Wave 2 school (`wave = 2`) is not, and a Wave 1 item with `retired = true` is not live but still shows correctly in an old save's inventory.

### F3 — Reference legality

The ref_ok formula is defined as, for every reference from row `a` to row `b` (a `ref(...)` column, or an element of a `list(ref)` or `map(ref)` column):

`ref_ok(a, b) = (b.wave ≤ a.wave) ∧ (a.retired ∨ ¬b.retired)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| a.wave, b.wave | int | 1 – W_max | data file | Waves of the referencing and referenced rows. A parameter-table row counts as wave 1 |
| a.retired, b.retired | bool | true/false | data file | Retirement flags |
| ref_ok | bool | true/false | calculated | Validator ERROR when false |

**Output range:** true or false. The first clause gives F2 a guarantee: if `a` is live then `a.wave ≤ W_live`, so `b.wave ≤ W_live` too. A live row therefore never reaches a row from an unreleased wave, whatever `W_live` is. The second clause handles the case the first misses: a live drop table, recipe or monster pool still pointing at retired content would keep handing it out.

**Example:** a Wave 1 drop table (`wave = 1`) listing a Wave 2 item (`wave = 2`) fails: `2 ≤ 1` is false. A Wave 2 recipe using a Wave 1 material passes. A live recipe whose input material has been retired fails until the recipe is retired as well or the input is changed.

### F4 — `uid` assignment

The next_uid formula is defined as:

`next_uid = 1 + max({0} ∪ { L.uid : L a line of the uid ledger (R6) })`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L.uid | u32 | 1 – 2³²−1 | data file (`data/meta/uid_ledger.csv`, R6) | Every `uid` ever assigned, including those of rows since deleted. 0 (`content_id_none`) means "none" and is never assigned |
| next_uid | u32 | 1 – 2³²−1 | calculated | The `uid` given to the next new row |

**Output range:** 1 when the ledger is empty, and otherwise one above the highest `uid` ever assigned. The maximum is taken over the ledger, not over the tables, so deleting the highest-`uid` row and committing does not lower it: a freed `uid` is never handed out again, whatever the git history. The ledger is append-only and checked against the comparison base (R6), so the maximum can never go down in a merged change. The u32 ceiling (4,294,967,295) is unreachable in practice: there are 2,431 content-table rows today. Reaching it is still a validator ERROR, not a wrap-around.

**Example:** the first run of the helper on today's content finds an empty ledger and assigns 1 … 2,431 in R2 table-inventory order, then file order within each table, appending 2,431 ledger lines. A later patch deletes the row holding `uid` 2,431 and adds three items: `next_uid` is still 2,432, the items get 2,432, 2,433 and 2,434, and 2,431 stays reserved in the ledger (a `removed row` WARN before launch).

## Edge Cases

**Files and structure**

- **If a table from the R2 inventory is missing or unreadable**: the validator raises ERROR and the loader goes to `Failed`, naming the file. Nothing loads, not even the other 18 tables, so the game never runs on part of its content.
- **If `data/` contains a CSV that is not in the R2 inventory**: validator ERROR (`unknown table`). The validator builds its file list by globbing `data/*.csv` and compares it against the inventory, so a new file cannot skip validation just by not being listed. The loader ignores the file, but the build cannot get that far.
- **If a table has a column its schema does not declare, or lacks one it does**: ERROR naming the column. Column *order* does not matter to the loader, which reads by header name. It does change F1, which is correct, because the bytes changed.
- **If a row has more or fewer cells than the header**: ERROR with the line number (existing behaviour, kept).
- **If the file has a UTF-8 BOM or CRLF line endings**: accepted. Both are normalised before parsing and before hashing (F1).

**Values**

- **If a required cell is empty**: ERROR. This includes `wave`, every `int`/`float`/`ref` column without a declared default, and `config.live_wave`. An empty `list` or `map` cell is the empty list or map. An empty `retired` cell is `false`. No other column has an implied default, because a missing value must never quietly become the permissive one.
- **If an `int` value is outside the signed 64-bit range, or a `float` is `nan`, `inf` or not a plain decimal**: ERROR. A plain decimal is an optional sign, digits, an optional fraction and an optional exponent. Both implementations must parse decimals to the correctly rounded IEEE-754 double, so they load bit-identical values. The parity harness (43) checks this (AC).
- **If a `map` cell repeats a key** (`atk=1;atk=2`): ERROR, because the first-wins and last-wins readings would disagree between implementations.
- **If a `map` value itself contains `=`**: the key is the text before the first `=`, and the rest is the value. `;` is reserved inside `list` and `map` cells and cannot be escaped. A value that needs it belongs in its own column.
- **If an `enum` cell holds a value outside its set** (for example an element other than `kim|moc|thuy|hoa|tho`): ERROR, as the validator does today, but now driven by the shared schema.

**IDs, `uid`s and probabilities**

- **If an ID breaks the format rule** (uppercase, a space, a hyphen, a diacritic, more than 48 characters): ERROR. Diacritics belong in `i18n`, never in IDs.
- **If the same ID appears in two tables**: ERROR (R3 global uniqueness), even though each table on its own is clean.
- **If a row has an empty `uid` cell**: ERROR with the hint "run the uid helper". The loader goes to `Failed`.
- **If a ledger line's row no longer exists because the row was deleted**: WARN (`removed row`) before launch, because IDs are renamed often before the first public build. The `uid` stays reserved in the ledger (F4). After launch, deleting a shipped row breaks R3, and OQ-2 asks for the ship marker that turns this into an ERROR.
- **If two branches each add rows and their merge gives two rows the same `uid`** (or two ledger lines with one `uid`): ERROR (duplicate `uid`). The fix is to re-run the helper on the merged files. It keeps every ledger line already present at the comparison base (R6), drops the conflicting new lines, and renumbers only the rows that were new on either branch, so nothing that has merged moves.
- **If someone changes the `uid` of an existing row**: ERROR, because the row no longer matches its ledger line (R6). This holds after the change is committed, because the ledger, not `HEAD`, is the reference. **If someone also edits or deletes the ledger line to match**: ERROR, because the working ledger is no longer an extension of the base ledger (R6, history check). There is no override flag. A wrong `uid` on content that has not shipped is fixed by retiring the row and adding a new one.
- **If a `drop_tables` row's `uid` changes, or two rows of one group swap `uid`s**: ERROR, like any other row. Each drop row is identified by (`table_id`, `ref`) (R2), so a changed `uid` inside a group is a mismatch, not a delete plus an add. Changing a drop row's `ref` is a delete plus an add: the old line is a `removed row` and the new row gets a fresh `uid`.
- **If the ledger file is missing while tables hold `uid`s**: ERROR (every row has a `uid` the ledger does not hold). The helper never rebuilds a ledger from the tables, because that would launder a changed `uid`.

**Parameter keys**

- **If `config.csv` or `sim_params.csv` holds a key the per-key schema does not declare, or lacks a declared key**: ERROR (`unknown key` / `missing key`) naming the file and key (R4). A key approved in a GDD but not yet built is absent from both the schema and the CSV, which is consistent.
- **If a parameter value does not convert to its key's type** (`party_max = 5.5` for an `int` key, `true` for a `float` key, a list key with an element of the wrong type): ERROR naming the key, the same as for a column.
- **If a `ppm` cell is outside 0 … 1,000,000, or is not an integer** (`0.55`, `55%`): ERROR. It is never clamped or converted, matching RNG F6, which treats an out-of-range `chance_ppm` as an error.

**Waves and liveness**

- **If a row references a row from a later wave, or a live row references a retired row**: ERROR (F3), naming both rows and the column.
- **If a save or a running world holds content that is not live** (retired content, or a later wave after a build with a lower `live_wave`): the content still resolves by ID and behaves as its row says. Liveness gates only what is *offered*, never what *exists*. What a feature does with an owned but non-live thing, such as a member standing in a zone that is not live, belongs to that feature's GDD. Lowering `live_wave` in a shipped build is not a supported release operation (OQ-3).
- **If a system looks up an ID that no table has** (a save from a newer build, or a corrupted save): the lookup raises a defined `UnknownContent(id)` error. It never returns an empty row or null. Local save and migration (6) decides whether the save is refused or repaired.

**Ordering and cycles**

- **If two rows of a `drop_tables` group, or two IDs in a `list(ref)` cell, are reordered**: F1 changes, because the bytes changed, but the loaded order does not, because everything is exposed in `uid` order (R4, RNG F5). No outcome changes.
- **If a self-referencing column forms a cycle** (skill A's `prereq` is B, and B's `prereq` is A): ERROR. The schema marks such a column acyclic (today only `skills.prereq`), and the validator checks it.

**Implementations**

- **If the Python loader and the engine loader both reach `Ready` but disagree**: the parity harness (43) catches it by comparing F1, the row count of every table, and a canonical dump of one sample row per table. A loader that reaches `Ready` on its own proves nothing about parity.

## Dependencies

**Upstream (this system depends on): none at runtime.** The data layer is Foundation-layer. It reads only files. It has two build-time inputs, and neither is a runtime dependency:

| System (#) | Hard / soft | Interface |
|---|---|---|
| Localization (4) | Soft, validator only | The validator reads `i18n/names_*.csv` to check name coverage (R9). The loader never reads i18n. With no i18n files, the name check fails and every other check still runs |
| Git (tooling, not a game system) | Hard, validator only | R6's history check compares the `uid` ledger with the ledger at the comparison base that Dev tooling (43) R13 resolves. Outside a git checkout, or with no resolvable base, that one check reports **NOT ASSESSED** by name and the run cannot pass. It is never silently skipped. Every other check, including rows against the ledger, needs no git |

**Downstream (systems that depend on this one).** Every system below has a GDD (re-verified 2026-11-16). Each lists this system in its own Dependencies section, names the tables or keys it reads, and states what its rows mean. Systems that read only `config`/`sim_params` keys are listed with their keys' owner role.

| System (#) | Hard / soft | Interface | Tables / outputs |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | Starts tick 1 only on `Ready`; reads parameters | `config`, `sim_params`, F1 |
| Deterministic RNG (2) | Hard, contract only | RNG R5 assigns this system the append-only `uid` column; RNG F5 needs `uid` order; RNG F6 needs `_ppm` integers. RNG's code does not call the loader; its callers do | `uid` columns, `ppm` columns |
| Local save and migration (6) | Hard | Saves store stable IDs or `uid`s, stamp F1, and own the policy for unknown IDs and for a hash mismatch | `uid`s, F1 |
| Member model (8) | Hard | School, items and skills by ID | `schools`, `items`, `skills` |
| CA/PA and traits (9) | Hard | Trait definitions | `traits` |
| Combat (10) | Hard | Skill effects, monster stats, role multipliers | `skills`, `monsters`, `sim_roles`, `sim_params` |
| Zones, grounds, monsters and hunt trips (11) | Hard | World content; liveness for zone access | `zones`, `grounds`, `monsters`, `materials` |
| Golden Boss and guild raid (14) | Hard | Boss definitions | `golden_bosses` |
| Schools and school change (20) | Hard | School definitions | `schools` |
| Skills (21) | Hard | Skill definitions and the effect schema columns | `skills` |
| XP and level pacing curve (22) | Hard | Curve parameters, level caps | `config`, `sim_params`, `rebirth` |
| Rebirth and Ascension (23) | Hard | Rebirth tiers | `rebirth` |
| Equipment enhancement (24) | Hard | Enhancement levels | `enhance` |
| Quests and achievements (25) | Hard | Quest definitions; liveness for daily and weekly selection | `quests` |
| Items and loot tables (26) | Hard | Items, drop groups in `uid` order with `drop_chance_ppm` (RNG F5, F6); owns the weighted-pick rule | `items`, `drop_tables`, `materials` |
| Crafting and recipes (28) | Hard | Recipes | `recipes` |
| Guild and buildings (30) | Hard | Building meta and per-level rows | `building_meta`, `buildings` |
| Leaderboards and anti-cheat (35) | Hard | Server replay uses the content matching the submission's F1 | F1 |
| Dev tooling and parity harness (43) | Hard | Balance simulator, calibrator and parity harness use the same loader and schema; the validator is part of this system's pipeline and runs in CI; R13 resolves the comparison base for the ledger history check (R6) | all, `uid` ledger |
| Command layer (5) | Hard | Command arguments of type `content(<table>)` resolve by ID or `uid`; its config keys | any content table, `config` |
| Utility AI (12) | Hard | Weights and thresholds | `config` |
| Recruitment (15) | Hard | Candidate generation reads schools, traits and its config keys; liveness for offered schools | `schools`, `traits`, `config` |
| Retention, leaving and negotiation (16) | Hard | Its config keys | `config` |
| Jianghu free agents and NPC guilds (17) | Hard | NPC guild definitions (approved addition) and its config keys | `npc_guilds` (when built), `config` |
| Arena (18), Endless Tower (19) | Hard | Their `sim_params` keys | `sim_params`, `monsters` |
| Gold economy (27) | Hard | Prices, tax and upkeep parameters | `items`, `buildings`, `config` |
| Offline progress (31) | Hard | Offline cap and resolver parameters | `config`, `sim_params` |
| Entitlement and feature flags (32) | Hard | Feature flags (approved addition) | `feature_flags` (when built) |
| Ads (33), In-app purchases (34) | Hard | Product catalogue (approved addition) and their config keys | `iap_products` (when built), `config` |
| Guild screens (39) | Soft | Display-side config keys | `config` |
| Event bus and history log (42) | Hard | History-log limits | `config` |
| Onboarding (44), Analytics (37), Settings (45), Local push (46) | Soft | Approved host-side tables and keys | `onboarding_steps`, `analytics_events` (when built), `config` |
| Every system that offers content to the player | Hard | Uses the F2 liveness query, never `wave` directly (R5) | — |

"Hard" means the dependent system cannot run without this one. The systems not listed (UI, audio, ads, analytics and so on) reach content only through the systems above.

**Consistency note for the systems index.** Re-verified 2026-11-16: the index rows of systems 1, 5, 6, 8–12, 14–16, 20–28, 30, 32–35, 39, 42 and 43 list the Data layer. Systems 17, 18, 19, 31, 37, 44, 45 and 46 read only approved keys or tables that are not built yet; their index rows can add the Data layer when those land. Deterministic RNG's Cross-References point here (R5 `uid`, F5, F6).

## Tuning Knobs

This system owns one knob. The hundreds of gameplay numbers stored in its tables are knobs too, but each belongs to the system that reads it, and it is documented there. This GDD does not duplicate them. A designer changes any of them by editing CSV, never code, and §4.4 requires a balance-simulator run before any number change.

| Knob | Where | Safe range | Too low | Too high | Interacts with |
|---|---|---|---|---|---|
| `live_wave` (W_live, F2) | `config.csv` | 1 – W_max (3 today) | 0 or below: nothing is live and the validator rejects it | Above W_max: the validator rejects it as a config/content mismatch | Every row's `wave` column. Raising it releases a whole wave at once (Player Fantasy 3). Lowering it in a shipped build is unsupported (OQ-3). It is part of F1, so changing it changes the content hash. Leaderboards are not split by content hash: each ranked segment replays with its own content (Leaderboards R7.3) |

**Not knobs (constants by design):**
- The ID format and the 48-character limit (R3). Widening the limit is backwards-compatible. Narrowing it would invalidate shipped IDs.
- `uid` 0 (`content_id_none`) meaning "none" (R6).
- `stable_id_max_length` = 48 (R3).
- The F1 framing and normalisation. Changing any of these changes every hash and breaks replay of earlier submissions, so a change needs a version bump owned by Leaderboards (35).

**Per-row content fields that look like knobs but are content:** `wave` and `retired` on each row. They are edited the same way as other content, and the validator constrains them (F3).

## Visual/Audio Requirements

None. This is a Core system with no visual or audio surface. The one screen it causes is specified under UI Requirements.

## Game Feel

None. Players never operate this system directly. Its contribution to feel is indirect: content is loaded once before tick 1 (R10), so there is never a content-loading hitch during play. The cold-start load-time budget is OQ-5.

## UI Requirements

One screen, shown only when the loader ends in `Failed` in a shipped build (States, AC-28):

- **Content:** a localised title and body ("game data is damaged — reinstall the game"), the first 8 hex characters of the expected F1 when it is known, and an error code. No stack trace and no file paths are shown to players.
- **Actions:** a single "Quit" button. On platforms whose store allows it, a "Verify / reinstall" deep link is also offered.
- **Never** a "continue anyway" option. The game does not run on partial content (Player Fantasy 2).
- **Strings** come from Localization (4) like any other text. Because the loader failed, this screen must not depend on content tables. Its strings live in the always-available UI string set, not in `data/`.

In dev builds, the full error list (every error from the failed pass) is printed to the console instead.

## Cross-References

| This GDD | References | Section there | Nature |
|---|---|---|---|
| R6, Dependencies | Deterministic RNG | R5 ("Content `uid`s": an append-only integer `uid` column, owned by Data layer) | This system specifies that column, its assignment (F4) and its validation |
| R4 (`ppm` type) | Deterministic RNG | F6 ("Probabilities in data are integers", `chance_ppm`) | This system types and validates every `_ppm` column |
| R7, F1 | Deterministic RNG | R12 (same results everywhere; replay from `world_seed` + command log + sim version) | F1 is the content part of "sim version" |
| R4 (deterministic order), Edge Cases, AC-31 | Deterministic RNG | F5 (lists sorted by content `uid`, never by file row position) | The loader exposes every table, group and list in `uid` order |
| Overview, R1, R8 | `JX1_Tycoon_GDD.md` | §12.3 (content pipeline), §17 (existing data and tools), §20 rule 1 (data-driven, immutable IDs) | Source requirements this GDD specifies |
| Player Fantasy | `JX1_Tycoon_GDD.md` | §16 (immutable IDs, i18n names), §3.2 (one deterministic core), §12.2 (wave launch) | Locked lines anchoring the three promises |

## Acceptance Criteria

Every criterion below is a **Logic** story test (automated, `tests/`, BLOCKING) unless marked **UI** (a retained screenshot in `production/qa/evidence/`) or **Integration** (multi-system, automated). "Fixture" means a temporary copy of `data/` and `i18n/` that the test modifies. No test edits the real `data/`.

**Pipeline and inventory (R1, R2)**

- **AC-1** — **GIVEN** the committed `data/` and `i18n/`, **WHEN** the validator runs, **THEN** it prints `0 lỗi` and exits 0, and the loader reaches `Ready` with all 19 tables, each with the same row count as its CSV body.
- **AC-2** — **GIVEN** a fixture with an extra file `data/foo.csv`, **WHEN** the validator runs, **THEN** it exits 1 with an `unknown table` error naming `data/foo.csv`.
- **AC-3** — **GIVEN** a fixture with `data/recipes.csv` deleted, **WHEN** the loader runs, **THEN** it ends in `Failed`, reports `data/recipes.csv`, and no table is readable (every lookup raises an error, none returns data).
- **AC-4** — **GIVEN** a generator script (`tools/gen_a.py`) writing into a fixture, **WHEN** the validator runs on the output, **THEN** the same checks apply as for hand-written rows (a generated row with a dangling reference exits 1).

**IDs (R3, R6, F4)**

- **AC-5** — **GIVEN** a fixture where one item ID is changed to `Kim_Sword-1`, **WHEN** the validator runs, **THEN** it exits 1 with an ID-format error naming the file, line and ID.
- **AC-6** — **GIVEN** a fixture where a material is given the same ID as an existing school, **WHEN** the validator runs, **THEN** it exits 1 with a global-uniqueness error naming both tables.
- **AC-7** — **GIVEN** a fixture with a new item row whose `uid` cell is empty, **WHEN** the validator runs, **THEN** it exits 1 and the message contains the hint to run the uid helper. **WHEN** the helper then runs, **THEN** the item gets `uid = max + 1` (F4), and every other `uid` cell in every table is unchanged.
- **AC-8** — **GIVEN** a fixture where every `uid` cell is empty and there is no `HEAD` history, **WHEN** the helper runs, **THEN** `uid`s 1 … N are assigned with no gaps and no duplicates, where N is the total row count of the content tables, and no row has `uid = 0`.
- **AC-9** — **GIVEN** a git checkout whose `HEAD` has `uid`s, **WHEN** a fixture changes one existing row's `uid`, **THEN** the validator exits 1, naming the row. **WHEN** a fixture instead deletes one row, **THEN** it prints a `removed row` WARN and exits 0 (before launch, OQ-2). **GIVEN** the same files outside any git checkout, **THEN** the run reports the history check as `NOT ASSESSED` and exits 1, not 0.
- **AC-10** — **GIVEN** a fixture where two rows in different tables share one `uid` (a simulated bad merge), **WHEN** the validator runs, **THEN** it exits 1 with a duplicate-`uid` error naming both rows.
- **AC-10b** — **GIVEN** fixtures where a `drop_chance_ppm` cell holds `0.55`, then `1000001`, then `-1`, **WHEN** the validator runs, **THEN** each exits 1, naming the cell. **GIVEN** `550000`, **THEN** it passes and loads as the integer 550000.

**Typed, frozen tables (R4)**

- **AC-11** — **GIVEN** the loaded tables, **WHEN** a test reads `items[<any equip id>].stats`, `skills[<any id>].effects` and `grounds[<any id>].monster_pool`, **THEN** they are a map, a map and a list of monster rows respectively, never strings, and `level_req` is an integer.
- **AC-12** — **GIVEN** a `Ready` loader, **WHEN** a test tries to assign to a table, a row field, or an element of a list or map column, **THEN** the write raises an error and a re-read returns the original value.
- **AC-13** — **GIVEN** a fixture where `rebirth.csv` row 1 has `new_level_cap = 125`, **WHEN** the loader and validator run, **THEN** both use 125 as the level cap for rebirth 1. A search of `sim/` and `tools/` finds no literal level-cap table.
- **AC-14** — **GIVEN** fixtures with, one per case, an empty `wave` cell, an `int` cell `12.5`, a `float` cell `nan`, and a `map` cell `atk=1;atk=2`, **WHEN** the validator runs, **THEN** each exits 1 with an error naming the file, line and column.

**Waves and liveness (R5, F2, F3)**

- **AC-15** — **GIVEN** `live_wave = 1`, **WHEN** the liveness query is asked about every school, **THEN** exactly the 5 schools with `wave = 1` are live, and all 10 still resolve by ID.
- **AC-16** — **GIVEN** fixtures with `live_wave` set to 0, then to W_max + 1, then empty, **WHEN** the validator runs, **THEN** each exits 1. **GIVEN** `live_wave = W_max`, **THEN** every non-retired row is live.
- **AC-17** — **GIVEN** a fixture where a `wave = 1` drop table lists a `wave = 2` item, **WHEN** the validator runs, **THEN** it exits 1 with an F3 error naming the drop table, the item and the column.
- **AC-18** — **GIVEN** a fixture where an item has `retired = true` and a live recipe uses it as an input, **WHEN** the validator runs, **THEN** it exits 1. **WHEN** the recipe is also retired, **THEN** it exits 0, and the item is not live but still resolves by ID.
- **AC-19** — **GIVEN** a search of every system's source outside the data layer, **WHEN** it looks for reads of a row's `wave` field, **THEN** it finds none. Liveness is reached only through the query.

**Content hash (R7, F1)**

- **AC-20** — **GIVEN** the committed files, **WHEN** F1 is computed on an LF checkout, on a copy with CRLF line endings and on a copy where `zones.csv` begins with a UTF-8 BOM, **THEN** all three hashes are equal.
- **AC-21** — **GIVEN** a fixture where two adjacent rows of `items.csv` are swapped, or `live_wave` is changed, **WHEN** F1 is computed, **THEN** it differs from the committed hash.
- **AC-22** (**Integration**) — **GIVEN** the same `data/` directory, **WHEN** the Python loader and the engine loader both load it, **THEN** both reach `Ready` with equal F1, equal row counts per table, and an equal canonical dump of one sample row per table, including at least one float column compared bit for bit. *Blocked until an engine is chosen (Deterministic RNG OQ-5).*

**Gate, messages and load lifetime (R8, R10, States)**

- **AC-23** — **GIVEN** a fixture with only a WARN-level issue (one row deleted relative to `HEAD`, before launch), **WHEN** the validator runs, **THEN** it exits 0 and prints the warning naming the ID.
- **AC-24** — **GIVEN** a fixture with three independent structural errors in three different tables, **WHEN** the loader runs, **THEN** it ends in `Failed` and reports all three, not only the first.
- **AC-25** — **GIVEN** a running simulation, **WHEN** any file in `data/` is changed on disk, **THEN** the loaded tables and F1 are unchanged until the process restarts.
- **AC-26** — **GIVEN** a `Ready` loader, **WHEN** a lookup uses an ID no table has, **THEN** it raises `UnknownContent` carrying that ID and never returns an empty row or null.
- **AC-27** — **GIVEN** a fixture where `skills.prereq` forms a two-skill cycle, **WHEN** the validator runs, **THEN** it exits 1, naming both skills.
- **AC-28** (**UI**) — **GIVEN** a shipped build with a corrupted table, **WHEN** the game starts, **THEN** it shows the "game data is damaged — reinstall" screen with no simulation running behind it. A screenshot is retained in `production/qa/evidence/`.

**Display text (R9)**

- **AC-29** — **GIVEN** a fixture where `names_en.csv` lacks one zone ID, **WHEN** the validator runs, **THEN** it exits 1, naming the language and the missing ID.

**Cross-system**

- **AC-30** (**Integration**) — **GIVEN** a world run by the balance simulator with a fixed seed, **WHEN** it runs twice on the same content and then once on content whose F1 differs, **THEN** the first two runs give identical summaries, and the summary records F1 so the third run is shown to be on different content.
- **AC-31** (**Integration**) — **GIVEN** a `drop_tables` group and a `grounds.monster_pool` cell whose entries are reordered in a fixture, **WHEN** the same seeded kill and the same seeded spawn are rolled on both fixtures, **THEN** the results are identical, and the loaded order of the group and the pool is ascending `uid` in both (RNG F5).

**Coverage map.** R1: AC-4. R2: AC-1–3. R3: AC-5, 6. R4: AC-11–14. R5: AC-15–19. R4 (`ppm`): AC-10b. R6: AC-7, 9, 10. R7: AC-20–22. R8: AC-1, 23, 24. R9: AC-29. R10: AC-25. F1: AC-20–22. F2: AC-15, 16 (boundaries 0, W_max, W_max+1). F3: AC-17, 18. F4: AC-7, 8. States: AC-3, 24, 28. Edge cases with their own criterion: AC-26, 27, 31.

**Gap (qa-lead lens):** there is no load-time budget. A mobile cold start is where this system could breach a budget, but a number depends on the engine and on the runtime format, which is an ADR. Tracked as OQ-5. Until it exists, there is no performance criterion here.

## Open Questions

| # | Question | Owner | Resolve by |
|---|---|---|---|
| OQ-1 | **Migrating today's data and code to this spec.** The steps are: add `wave` (and optional `retired`) to the 14 tables that lack it, filling each value as the largest wave among the rows it references, with a minimum of 1, then checking it by hand; rename `skills.unlock_wave` → `wave`; add `config.live_wave = 1`; add a `uid` column to every content table and fill it with the helper; convert `drop_tables.chance` → `drop_chance_ppm` and `enhance.success_pct` → `success_ppm` (exact: `0.55` → `550000`); add `.gitattributes`; move the duplicated constants (R4) into the shared schema; rewrite `sim/data.py` to load all 19 tables typed and frozen; update `balance_sim`, `calibrate` and the tests for typed rows. Content values do not change, so balance results should not move. Re-run `balance_sim` to confirm. | Implementation (story under Dev tooling 43 / this system) | Before any other MVP system's implementation story |
| OQ-2 | **Ship marker for removed rows.** Before launch, a row deleted relative to `HEAD` is a WARN. After the first public build, deleting a shipped row should be an ERROR. What marks "shipped": a `shipped_through_uid` value in `config.csv`, a git tag, or a column? | This system + Release (release-manager) | Before the first public build |
| OQ-3 | **Lowering `live_wave` in a shipped build** (rollback or regional staggering). It is unsupported for now. If ever needed, each feature with non-live content in saves must define its behaviour. | Producer | Only if a staggered release is planned |
| OQ-4 | **Skill display names.** §17.2 says skills have no display names yet, so R9's coverage check omits skills. Add skill IDs to the required set once names exist. | Localization (4) | Vertical Slice (when Localization is built) |
| OQ-5 | **Runtime format and cold-start load budget on mobile.** CSV parsed at startup vs a pre-built bundle, and the time budget, depend on the engine. This becomes an ADR. | `/architecture-decision` after `/setup-engine` | Before Architecture gate |
| OQ-6 | **Feasibility not checked against the pinned engine.** NOT SOURCEABLE: there is no core or scripting module under `docs/engine-reference/godot/modules/`, and the engine is not chosen (Deterministic RNG OQ-5). Float-parsing parity (Edge Cases, AC-22) is the highest-risk port item. | technical-director | Before Architecture gate |
