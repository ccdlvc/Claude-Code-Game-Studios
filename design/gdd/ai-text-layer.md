# AI Text Layer (optional local LLM)

> **Status**: Designed (pending independent /design-review)
> **Author**: design-system (autonomous batch run) + user review pending
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, `game-concept.md` or `game-brief.md` exist; checked instead against GDD §2/§9.2 intent (no contradiction found: text-only, template floor, deterministic logic untouched)
> **Implements Pillar**: None (no game pillars written yet). Anchored to JX1_Tycoon_GDD.md §9.2 and the candidate pillar "every member is a person with a hidden ceiling" (systems index CD note).

## Summary

An optional, downloadable on-device language model that rewrites five kinds of game text (member biographies, the Jianghu Chronicle, advisor explanations, random-event lines and negotiation lines) in a livelier voice. It only ever sees facts the player already knows, every name and number it writes is checked against those facts, and its text is labelled, reportable and cached in the save. Without the pack, or whenever it fails, the complete template text is shown and nothing in the game changes.

> **Quick reference** — Layer: `Polish` · Priority: `Full Vision` · Category: `Narrative` · Key deps: `Localization, Event bus and history log, Member model, CA/PA and traits, Local save, Data layer, Sim core` (soft: Retention, Entitlement, Settings, Jianghu free agents, Account and cloud save)

## Overview

The AI text layer is an optional, presentation-side writer. With a small language model downloaded as an extra pack (GDD §9.2: llama.cpp, GGUF Q4, 0.5–1.5B parameters, 300 MB–1 GB), it rewrites five kinds of game text in a livelier voice: member biographies, the Jianghu Chronicle (Giang Hồ Ký), the advisor's explanations (Quân sư), lines for game-generated random events, and the flavour lines of a negotiation. Each of the five already exists without it as a template, built by Localization from IDs and numbers, and the template is always the first thing the player sees.

**Data layer.** The layer takes a *fact sheet*: the IDs and numbers the player is already allowed to know, never hidden traits, exact PA or a probability. It wraps the fact sheet in a fixed per-feature frame, asks the model for a short JSON answer, checks every name and number in the answer against the fact sheet, and caches accepted text in the save with a locale tag. It runs in the background only while the device is idle, cool and has memory to spare, and it switches itself off when it does not.

**Player impact.** A player who never installs the pack loses nothing: every screen, every decision and every number is identical, and the game is fully playable and fully readable. A player who does install it gets a guild whose members sound like people, and a Chronicle that reads like a story rather than a log. Nothing the model writes can change the simulation: no command, no score, no outcome ever reads its output (§9.2: *"game logic deterministic; LLM chỉ sinh văn bản trong khung"*).

**Why it exists.** §9.2 locks it as a side feature (§2: *"AI: Tuỳ chọn; LLM nhỏ + template khung chặt, là tính năng phụ [CHỐT]"*). It is the cheapest way for a solo developer to give hundreds of members and a never-ending Chronicle varied prose, without writing that prose by hand and without letting a model anywhere near game logic.

*Not owned here:* the templates themselves and the locale rules (Localization R10), the history records (Event bus), what a member is and what the player may know about them (Member model, CA/PA and traits), the negotiation outcome (Retention), and whether the feature is Free or Premium (Entitlement, OQ-1). The llama.cpp GDExtension binding is an implementation choice → becomes an ADR.

## Player Fantasy

**Framing: Direct.** The player reads this text; they never operate the system.

*Specialist lens applied: creative-director (no agent spawned).* Three candidate framings were drafted, each anchored to one moment. No game pillars exist, so none is quoted; the anchor is §9.2 and the systems index's candidate pillar *"every member is a person with a hidden ceiling"*.

1. **"They have a story, not a stat line."** (chosen) The player opens a recruit who has just revealed *Phúc Tinh*. Under the numbers is a short paragraph: a fisherman's child from the river delta, joined Thủy môn at level 10, carried the guild's banner back from the third Golden Boss. Every fact in it is one the player could have checked on the card. The words are new; nothing in them is a secret.
2. **"The guild remembers, in its own words."** After eight hours away the player opens the Chronicle and reads a paragraph about the night the guild finally killed the Golden Boss, naming the healer who held the line. It agrees with the roster in front of them.
3. **"My people answer back."** A disciple asks to leave. Their line sounds proud, or wounded, or greedy, the way their revealed temperament says it should. The offer, the amount and the buttons are the game's, unchanged.

**Chosen: 1, with 2 and 3 as supporting moments.** The layer's job is to make the people of the guild feel specific. It must never feel like an oracle: the player should never learn something from the prose that the game had not already shown them, and never miss something because the prose left it out.

**What the player must never feel:**
- *Cheated.* The prose never contradicts the numbers, never hints at a hidden trait, and never reads as if it decided an outcome.
- *Punished for opting out.* The template version is complete and pleasant. AI text is seasoning.
- *Waiting.* No screen ever shows a spinner for prose. The template is there at once.

Reference feel: the generated biographies of Dwarf Fortress legends and the Chronicle tone of Crusader Kings event text, short and grounded in what happened.

## Detailed Design

*Specialist lenses applied (no agents spawned; routing: Narrative → "Dialogue, quests, lore" row).*
- **game-designer:** the layer offers no decision; its design risk is that it creates one by accident. If prose ever carries a fact the UI does not (a hint, a probability, a hidden trait), players will learn to read the prose to play. Rule: every number and every decision input stays in a fixed UI widget; prose is never the only carrier of anything (R1, R3).
- **narrative-director:** tone must be one voice across 5 features and 2 languages. §16.3 asks for a single chosen register (serious history vs folk legend) and says the choice also feeds the LLM prompt. That choice is not made yet (OQ-5); the frame carries a `tone_id` so it can be set once in data. Historical and religious figures must never be described as monsters, and never as the subject of a joke (§16.3).
- **writer:** small models write English better than Vietnamese (§9.2), and Vietnamese diacritics fail first. The templates are the voice of record; the model writes *variations* of a template's content, at most a few sentences. Short fields are easier to keep in voice than long ones, so every feature has a hard length cap (F3).
- **art-director:** the only visual work is labelling: generated text carries a small "AI" mark and a report control (R9, R10) that must read at pixel-UI sizes without crowding the card.
- *Disagreement surfaced:* the writer lens would keep Vietnamese generation off entirely; §9.2 asks for vi/en quality tests "riêng" (separately), which implies vi may ship. Resolved by making generation per-locale and data-driven (R7): vi ships off and is switched on per feature only when its quality test passes. Logged as an autonomous decision.

### Core Rules

**R1 — Text out, nothing back.** The layer's output is display text only. It is never read by the simulation, a command, Utility AI, Analytics, Leaderboards, a save checksum check other than its own section, or any formula. No command may be built from model output. The layer reads the simulation only through published read APIs, between ticks, on the main thread, and copies what it needs into a fact sheet; it never holds a reference into live state.

**R2 — The template is the floor.** Each feature has a complete template path rendered by Localization (R10 there) from the same fact sheet. The template path is always available, needs no download, and is what the player sees whenever the AI path is off, not ready, rejected, reported, stale or in another locale. A feature may not ship in this layer unless its template path is complete (AC-1).

| Feature | `feature_id` | Subject key | Fact sheet (player-known only) | Template fallback (§9.2) | AI output frame |
|---|---|---|---|---|---|
| Member biography | `bio` | `member_id` | name record, school and join level, element, level, rebirth count, **revealed** traits only, days in guild, up to `bio_milestones_max` milestones from `milestones_for(member_id)`, origin zone if known | Fragment assembly: `ai_tpl_bio_*` keys chosen by school, element, first revealed personality trait and milestones | `{"bio": string}` |
| Jianghu Chronicle | `chron` | game-day index | up to `chron_records_max` history records of that day (`read_history`), resolved to names | Line-per-record `ui_chron_*` (Event bus / Localization) | `{"title": string, "body": string}` |
| Advisor (Quân sư) | `advice` | suggestion ID from its producer | the producer's suggestion and the numbers it computed (PROVISIONAL, OQ-3) | Suggestion table rows | `{"why": string}` |
| Random event | `event` | event instance ID from its producer | event type, participants, outcome already decided (PROVISIONAL, OQ-4) | Scripted lines `ai_tpl_event_*` | `{"line": string}` |
| Negotiation | `nego` | `[member_id, request ordinal]` | demand kind and target, `R` (the asked raise), displayed mood and loyalty bands, revealed personality traits, the player's choice after it is made | Fixed dialogue `ai_tpl_nego_*` per demand kind and choice | `{"line": string}` |

**R3 — The fact sheet holds only what the player may already know.** It is built by this layer from read APIs and is the model's entire input apart from the frame. Never included: hidden traits or their count beyond what the card shows; exact PA unless the CA/PA R12 view would show it at that moment; PA estimate bounds other than the ones on screen; any probability, chance or weight (for example Retention's `p_counter`, F6); RNG keys or seeds; future or undecided outcomes; another member's private negotiation. Numbers enter as the same integers the UI shows (rounded the same way). Each fact sheet has a canonical form (sorted keys, IDs not names, ints) whose hash `facts_hash` (F5) keys the cache.

**R4 — The frame.** A generation request is `system_frame[feature_id, locale, tone_id] + fact sheet`. The frame is authored data (not code), versioned by `frame_version`, and instructs the model to answer only with the feature's JSON object. Generation uses a fixed sampling seed derived from `facts_hash` and `frame_version`, so the same model, frame and facts give the same text (reproducible QA). Output is capped at `max_tokens[feature]`.

**R5 — Validation, then cache or discard.** A model answer is accepted only if all of these hold; otherwise it is discarded, the template stays, and the job counts as a failure (F6):
1. It parses as the feature's JSON object, with no extra fields and every string non-empty.
2. Each string is at most `max_chars[feature]` characters after trimming.
3. **Names:** every proper name in the output is a name in the fact sheet's name list (members, schools, zones, bosses, items it lists) or in the locale's allowed glossary. Matching is case-insensitive and diacritic-exact for `vi`.
4. **Numbers:** every number written in digits equals a number in the fact sheet. Numbers spelled as words are rejected outright (`reject_spelled_numbers`, default on), because they cannot be checked.
5. **Script and locale:** for `vi`, the text uses Latin script with Vietnamese diacritics and no CJK characters; for `en`, ASCII letters plus the diacritics of names in the fact sheet.
6. **Blocklist:** no term from the locale's `ai_blocklist` (slurs, sexual content, real-world politics, the names of real historical or religious figures in a demeaning context per §16.3).
7. It does not repeat the frame or the fact sheet verbatim (`echo_max_ratio`).

**R6 — Background, idle, never in the way.** Generation runs on one worker thread, one job at a time, only while the runtime gate F2 is open: enabled, model loaded, the Sim core not catching up, free memory, battery and temperature within limits, and the player idle for `idle_min_s`. When the gate closes mid-job, the job is cancelled (not paused) and re-queued. The worker never touches simulation state; it receives a copied fact sheet and returns a string. The model is unloaded after `unload_after_idle_s` with an empty queue, and immediately on an OS low-memory warning.

**R7 — Per-feature, per-locale switch.** `ai_text_enabled[feature_id][locale]` is data. At launch every `vi` entry is off and every `en` entry is on (§9.2: small models write English better; vi/en quality is tested separately). Turning a locale on for a feature requires its quality test (Acceptance Criteria AC-17) to pass on the shipped model. A feature/locale pair that is off behaves exactly as if the pack were not installed.

**R8 — Cache.** Before storing, every name matched by R5 check 3 is replaced by a placeholder for its ID (`{m:<member_id>}`, `{s:<school_id>}`, `{z:<zone_id>}` …), filled in at display time from the current name record and locale names, so a rename never leaves an old name in cached prose. Accepted text is stored as `{feature_id, subject_key, facts_hash, frame_version, model_id, locale, text, created_utc, last_shown_utc, reported}`. Display (R11) uses an entry only if `feature_id`, `subject_key` and `locale` match **and** `facts_hash` equals the current fact sheet's hash and `frame_version` and `model_id` are current. An entry that fails the hash check is *stale*: the template is shown and a regeneration is queued. Cached text is never translated (Localization R10). The cache is bounded by F7 and persisted with the save (OQ-2: save section registration).

**R9 — Report.** Every piece of displayed AI text has a report control (Google Play policy on in-app AI-generated content; GDD §12.4.1 and the P6 prompt). Reporting:
1. immediately replaces the text with the template on every screen,
2. marks the entry `reported = true` and blocks regeneration for that `[feature_id, subject_key]` until the facts change,
3. stores a report record `{feature_id, frame_version, model_id, locale, text, facts_hash, utc}` locally, and
4. queues it for submission to the developer when online and the account service allows it (PROVISIONAL, OQ-6). The report works with no network: steps 1–3 never wait for step 4.

**R10 — Labelled, always.** AI text is always marked as AI text (a small mark next to it, with an accessible label "AI-generated text" / "Văn bản do AI viết"). Template text never carries the mark. The player can always tell which they are reading.

**R11 — Display rule: template first, swap on next open.** A screen asks `ai_text.get(feature_id, subject_key, fact_sheet)`. It returns `{text, source: template | ai, entry_id}` at once, never blocking. If there is no valid entry it returns the template and enqueues a job. A finished job never replaces text the player is reading: new AI text appears the next time that panel or page is opened. Numbers, buttons and outcomes are always in the screen's own widgets, not inside the returned prose (R1).

**R12 — Opt-in pack.** The pack is not in the base install (§9.2 "gói tải thêm"; P7 "tách gói LLM"). The player turns the feature on in Settings, sees the download size and storage and memory requirements, and confirms. The pack is verified by checksum before use. The player can switch the feature off (model unloaded, cache kept) or delete the pack (files removed; cache kept, still shown while valid, regenerations stop). Device eligibility is F1. The feature is also gated by Entitlement's flag `feature_ai_text` (OQ-1); while no entitlement snapshot is available the flag is treated as **off**.

**R13 — Model and frames are content.** `model_id`, its pack size and memory need, every frame, glossary, blocklist and the R7 switch table are data files (Data layer), so a model swap or a tone change is a content update, not a code change. Changing `model_id` or `frame_version` makes every cached entry stale (R8); old text is shown until replaced only if `keep_stale_on_model_change` is on (default off: the template is shown).

### States and Transitions

**Pack and runtime state** (one per install):

| State | Meaning | Enters from | Leaves to |
|---|---|---|---|
| `NotInstalled` | No pack on disk | Start; `Delete pack` | `Downloading` (player confirms, F1 eligible) |
| `Ineligible` | Device fails F1 | Any check of F1 | `NotInstalled` when F1 passes (storage freed) |
| `Downloading` | Pack transfer in progress, resumable | `NotInstalled` | `Verifying` on completion; `NotInstalled` on cancel; stays on network loss (paused, resumes) |
| `Verifying` | Checksum and size check | `Downloading` | `Off` on pass; `NotInstalled` on fail (file removed, error shown) |
| `Off` | Pack installed, feature switched off or entitlement flag off | `Verifying`; player switches off; flag off | `Idle` when switched on and flag on |
| `Idle` | Enabled, model not in memory | `Off`; `Ready` after `unload_after_idle_s` or low-memory warning | `Loading` when a job is queued and F2 open |
| `Loading` | Model being loaded | `Idle` | `Ready` on success; `Suspended` on load failure |
| `Ready` | Model loaded, worker runs jobs while F2 open | `Loading` | `Idle`; `Suspended`; `Off` |
| `Suspended` | `fail_max` consecutive failures (F6) or load failure | `Ready`; `Loading` | `Idle` after `fail_cooldown_s`; `Off` |

The UI shows `Off`, `Idle`, `Loading` and `Ready` as **On**; `Suspended` as **On (paused)**; there is no state in which a screen waits on the layer.

**Job states** (per request): `Queued → Running → Accepted | Rejected | Cancelled`. `Cancelled` jobs (gate closed, subject left the screen and the queue is over `queue_max`) return to `Queued` once, then are dropped. `Rejected` jobs are retried at most `retry_max` times with the same seed incremented by 1, then the key is left on the template until its facts change.

### Interactions with Other Systems

| System | Direction | Data | Owner of interface |
|---|---|---|---|
| Localization (4) | both | Template fallback rendering per feature; `ai_tpl_*` keys; active locale; locale-tag rule (R10 there) | Localization owns templates and the locale rule; this layer owns `ai_tpl_*` content requirements |
| Member model (8) | 8 → this | Name record (including departed members), school, element, level, rebirth, days in guild | Member model |
| CA/PA and traits (9) | 9 → this | Revealed traits only; the PA view as the player sees it (R12 there) | CA/PA. This layer must never call an API that returns hidden traits |
| Event bus and history log (42) | 42 → this | `read_history(from, to, max)`, `milestones_for(subject)`; paged reads, cached here | Event bus |
| Retention (16) | 16 → this | `retention_view(member_id)` (displayed mood/loyalty, demand kind and target, `R`); request cause and demand IDs | Retention. Outcome and probabilities stay there |
| Jianghu free agents (17) | 17 → this | Free-agent and returning-member biographies use the `bio` feature with the same fact rules (PROVISIONAL, OQ-7) | Free agents |
| Local save (6) | this → 6 | The cache and report queue as one save section (PROVISIONAL, OQ-2) | Local save owns the contract |
| Entitlement (32) | 32 → this | `feature_ai_text` flag in the entitlement snapshot | Entitlement |
| Settings (45) | both | On/off toggle, download/delete, storage shown | Settings owns the screen; this layer owns the states |
| Sim core (1) | 1 → this | `catching_up` flag and the between-ticks read window | Sim core |
| Guild screens (39), Realtime world view (38) | this → them | `ai_text.get` results; AI mark and report control | Screens own layout |
| Account and cloud save (7) | this → 7 | Report submission when online (PROVISIONAL, OQ-6) | Account |
| Dev tooling (43) | 43 → this | Offline quality harness for AC-17 | Dev tooling |

## Formulas

*Specialist lens applied: systems-designer (no agent spawned).* None of these formulas touches the simulation or game balance; they bound device cost, text length and cache size. Every variable was checked at 0 and at both ends of its range (findings in Edge Cases). Device-side numbers (RAM, tokens per second, thermal levels) are **unverified estimates**: no engine reference covers llama.cpp or GDExtension inference (`NOT SOURCEABLE — on-device LLM performance is not covered by docs/engine-reference/godot/`), so each is a data value to be calibrated on real hardware (OQ-8).

### F1 — Device eligibility

The eligible formula is defined as:

`eligible = (ram_total_mb ≥ model_ram_total_min_mb) ∧ (storage_free_mb ≥ ceil(pack_mb × storage_margin))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| ram_total_mb | int | 1,024–24,576 | calculated (OS query) | Device physical RAM |
| model_ram_total_min_mb | int | 3,072–8,192 | data file (model row) | Minimum device RAM for this model; 4,096 for a 0.5B Q4 model, 6,144 for 1.5B Q4 (estimate) |
| storage_free_mb | int | 0–∞ | calculated (OS query) | Free app storage |
| pack_mb | int | 300–1,024 | data file (model row) | Download size (§9.2: 300 MB–1 GB) |
| storage_margin | float | 1.0–3.0 | data file | Space for the download plus unpacked copy; default 1.5 |

**Output Range:** boolean. **Example:** a 4 GB phone with 900 MB free and a 400 MB pack: `4096 ≥ 4096` and `900 ≥ 600` → eligible. With 500 MB free → `Ineligible`, and Settings shows "needs 600 MB free".

### F2 — Runtime gate

The gate_open formula is defined as:

`gate_open = enabled ∧ flag_ai_text ∧ ¬catching_up ∧ (ram_free_mb ≥ model_ram_need_mb + ram_headroom_mb) ∧ (charging ∨ battery_pct ≥ battery_min_pct) ∧ (thermal_level ≤ thermal_max) ∧ (idle_s ≥ idle_min_s)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| enabled | bool | — | calculated (Settings) | Player switch, and state not `Suspended` |
| flag_ai_text | bool | — | calculated (Entitlement snapshot) | `feature_ai_text`; false when no snapshot (R12) |
| catching_up | bool | — | calculated (Sim core) | Offline fast-forward in progress |
| ram_free_mb | int | 0–24,576 | calculated (OS query) | Available memory now |
| model_ram_need_mb | int | 300–2,048 | data file (model row) | Resident memory with context; ~700 for 0.5B Q4 at 1,024-token context (estimate) |
| ram_headroom_mb | int | 0–2,048 | data file | Memory left for the game and OS; default 512 |
| battery_pct | int | 0–100 | calculated (OS query) | Battery level |
| battery_min_pct | int | 0–100 | data file | Default 30 |
| thermal_level | int | 0–3 | calculated (OS: 0 nominal, 1 fair, 2 serious, 3 critical) | Device thermal status |
| thermal_max | int | 0–3 | data file | Default 1 |
| idle_s | float | 0–∞ | calculated | Seconds since the last touch or key input |
| idle_min_s | float | 0–60 | data file | Default 5 |

**Output Range:** boolean, re-evaluated every `gate_poll_s` (1 s) and before each job. **Example:** a phone at 45 % battery, thermal 1, 1,400 MB free, idle 8 s: `1400 ≥ 700 + 512` → open. At thermal 2 the running job is cancelled and re-queued (R6).

### F3 — Length caps

The max_tokens formula is defined as:

`max_tokens[f, loc] = ceil(max_chars[f] / chars_per_token[loc]) + json_token_slack`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| max_chars[f] | int | 40–1,200 | data file | Per feature, all strings in the answer combined: `bio` 600, `chron` 800, `advice` 300, `event` 200, `nego` 160 |
| chars_per_token[loc] | float | 1.5–5.0 | data file (model row) | Tokenizer density; `en` 4.0, `vi` 2.5 (estimate; diacritics tokenize poorly) |
| json_token_slack | int | 0–64 | data file | Tokens for the JSON wrapper; default 32 |

**Output Range:** 42 (`nego`, en) to 352 (`chron`, vi) tokens at defaults. **Example:** `bio` in `vi`: `ceil(600 / 2.5) + 32 = 272` tokens. At an estimated 10–20 tokens/s on a mid-range phone, 14–27 s per job, under `job_timeout_s` (30).

### F4 — Queue order

The queue_key formula is defined as:

`queue_key = (visible desc, prio[f] desc, enqueue_seq asc)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| visible | bool | — | calculated | The subject is on an open screen now |
| prio[f] | int | 0–9 | data file | `nego` 5, `event` 4, `advice` 3, `bio` 2, `chron` 1 |
| enqueue_seq | int | 0–2⁶³ | calculated | Monotonic per session |
| queue_max | int | 1–256 | data file | Default 32; when full, the lowest non-visible job is dropped |

**Output Range:** a total order. **Example:** an open negotiation (visible, 5) runs before an off-screen bio (not visible, 2) queued earlier. A dropped job is re-queued the next time its subject is viewed.

### F5 — Cache key and seed

The facts_hash formula is defined as:

`facts_hash = FNV1a64(canonical_bytes(fact_sheet))`; `seed = (facts_hash ⊕ frame_version) mod 2³² + retry_n`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| canonical_bytes | bytes | — | calculated | Sorted keys, IDs not names, ints as decimal strings, UTF-8 |
| frame_version | int | 1–2³¹ | data file | Raised on any frame edit |
| retry_n | int | 0–`retry_max` | calculated | Retry count for this key (R5) |

**Output Range:** 64-bit hash; 32-bit seed. This is not the simulation RNG and never uses or advances it (Deterministic RNG R1 forbids nothing here because it governs simulation draws only). **Example:** a member renamed → the name record changes, but the fact sheet stores the ID, so `facts_hash` is unchanged and the cached bio still shows; the name is substituted at display time (Edge Cases). A newly revealed trait changes the hash and the bio goes stale.

### F6 — Failure and suspension

The suspend formula is defined as:

`suspend = consecutive_fail ≥ fail_max`, where a failure is a Rejected job (R5), a timeout (`wall_s > job_timeout_s`) or a model error; any Accepted job resets `consecutive_fail` to 0.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| consecutive_fail | int | 0–∞ | calculated | Session counter |
| fail_max | int | 1–20 | data file | Default 3 |
| job_timeout_s | float | 5–120 | data file | Default 30 |
| fail_cooldown_s | int | 60–86,400 | data file | `Suspended` length; default 1,800 |
| retry_max | int | 0–5 | data file | Retries per key; default 1 |

**Output Range:** boolean. **Example:** three timeouts in a row on an old phone → `Suspended` for 30 min; templates everywhere; no error shown beyond "On (paused)".

### F7 — Cache bound

The cache_ok formula is defined as:

`cache_ok = Σ bytes(entry) ≤ cache_cap_kb × 1024 ∧ ∀f: count_f ≤ cache_count_max[f]`; on violation, evict the entry with the oldest `last_shown_utc` among unreported entries of the feature over its count (else of any feature) until both hold. A reported entry is kept as a 48-byte stub (`feature_id`, `subject_key`, `facts_hash`, `reported`) with no text.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| bytes(entry) | int | 40–2,400 | calculated | UTF-8 text plus fields |
| cache_cap_kb | int | 64–8,192 | data file | Default 1,024 |
| cache_count_max[f] | int | 0–10,000 | data file | `bio` 300, `chron` 400, `advice` 50, `event` 100, `nego` 50 |

**Output Range:** at most 1 MB of the save. **Example:** 200 members × ~900 B (`vi` bio) = 180 KB; a year of Chronicle days × ~1.2 KB = 440 KB; total ≈ 0.7 MB, under the cap. At `cache_cap_kb` = 64 only recent bios survive and most screens show templates; the game is unaffected.

## Edge Cases

*Specialist lens applied: systems-designer and narrative-director rows (no agents spawned), re-read against Core Rules and Formulas.*

- **If the pack is never installed**: every feature shows its template; no queue is created, no worker thread starts, the save section stores an empty cache. Gameplay, numbers and screens are identical (R2).
- **If the model answers with a number not in the fact sheet** (for example "won 3 fights" when the sheet says 2): rejected by R5 check 4; template stays. Prose never states a number the UI cannot back.
- **If the model names someone not in the fact sheet** (an invented hero, a real historical figure): rejected by R5 check 3. Real historical or religious figures may appear only if they are in the locale glossary as allowed names, and never in a monster or boss role (§16.3).
- **If the model hints at a hidden trait in words** ("she seems unusually lucky" while *Phúc Tinh* is hidden): the fact sheet never held it, so the model can only guess; the guess is not checkable by R5. Mitigation: frames forbid describing traits not listed, and the quality harness (AC-17) measures trait-word rate on members with hidden traits. A guess carries no information, because the model never saw the trait. Accepted risk.
- **If a member is renamed after their bio was cached**: the cache holds `{m:id}` placeholders (R8), so the bio shows the new name; `facts_hash` is unchanged because the sheet stores IDs. No regeneration.
- **If a member leaves or dies (departs) after their bio was cached**: the bio stays valid (it is history); the screen marks the member as departed per Member model R3. The departed member's entry is the first evicted under F7 pressure among `bio` entries with equal `last_shown_utc`.
- **If a trait is revealed, the member changes school or is reborn**: the fact sheet changes, `facts_hash` changes, the entry is stale, the template is shown, and a job is queued (R8).
- **If the locale switches**: entries tagged with the other locale are not shown; templates appear on the next frame (Localization R10); jobs for the new locale are queued only for subjects as they are viewed (no bulk regeneration). If the new locale's switch (R7) is off, nothing is queued.
- **If the player is reading a panel when its job finishes**: text is not swapped (R11); it appears on the next open.
- **If offline catch-up runs for 24 h**: the gate is closed throughout (F2, `catching_up`); afterwards the Chronicle shows templates for those days and only the days the player opens are generated. No backlog of hundreds of jobs forms.
- **If the queue is full (F4)**: the lowest-priority non-visible job is dropped; it comes back when its subject is viewed. A visible job is never dropped for a non-visible one.
- **If the OS issues a low-memory warning during a job**: the job is cancelled, the model is unloaded, state goes to `Idle` (R6). This does not count as a failure in F6.
- **If generation is slow on every attempt (old device)**: three timeouts → `Suspended` for `fail_cooldown_s` (F6). Repeated suspension does not change F1; the player can switch the feature off in Settings. OQ-8 tracks whether F1's thresholds need a speed benchmark.
- **If the pack file is corrupted or deleted outside the game**: the next `Loading` fails → `Suspended`; on the next launch the checksum fails → `NotInstalled`, with a one-line notice in Settings. The cache is kept.
- **If the player reports text while offline**: the text is hidden at once and the report is stored; it is submitted when online (R9). If the report queue exceeds `report_queue_max`, the oldest unsent reports are dropped first, and the hide-and-block effect remains.
- **If the same text is reported, then the facts change**: the block lifts and a new generation may run (with a new `facts_hash`, so a new seed). The old stub is evicted.
- **If entitlement turns the flag off (refund, OQ-1)**: state goes to `Off`; cached AI text stops being shown (templates everywhere) but is kept, so turning the flag back on restores it without regeneration.
- **If the model returns valid JSON with an empty string or only whitespace**: rejected by R5 check 1.
- **If the model outputs mixed scripts** (Chinese characters in `vi`): rejected by R5 check 5. This is a known failure of small multilingual models.
- **If a cloud save from another device is loaded**: the cache travels with the save; entries with a `model_id` this device does not have are stale (R8, R13) and templates are shown.
- **If the history page for a Chronicle day exceeds `chron_records_max`**: the fact sheet keeps the milestone records first, then the rest in tick order, up to the cap; the template path still renders every record (the prose is a summary, the template list is complete).
- **If `cache_cap_kb` is 0 or `cache_count_max[f]` is 0**: nothing is cached for that feature; it effectively runs template-only, and no jobs are queued for it (a job whose result cannot be stored is not started).
- **If `idle_min_s` is 0**: generation may run during play. Allowed only in dev builds; the release validator enforces `idle_min_s ≥ 1` (Tuning Knobs).

## Dependencies

| System | Hard/Soft | Interface | Why |
|---|---|---|---|
| Localization (4) | Hard | Template rendering for every feature; `ai_tpl_*` keys; active locale; R10 locale-tag rule | The template floor (R2). Without it there is nothing to fall back to |
| Event bus and history log (42) | Hard | `read_history`, `milestones_for` | Chronicle and bio facts |
| Member model (8) | Hard | Name record, school, element, level, rebirth, days in guild | Bio facts and name placeholders |
| CA/PA and traits (9) | Hard | Revealed traits, the player-visible PA view (R12 there) | What may be said about a person (R3) |
| Local save and migration (6) | Hard | One registered save section (PROVISIONAL, OQ-2) | The cache persists (§9.2 "cache vào save") |
| Data layer (3) | Hard | Model rows, frames, glossaries, blocklists, switch table (R13) | All tuning is data |
| Sim core (1) | Hard | `catching_up`, between-ticks read window | Gate F2 and R1 |
| Retention (16) | Soft | `retention_view`, request cause and demand IDs | The `nego` feature only |
| Jianghu free agents (17) | Soft | Free agents use `bio` (PROVISIONAL, OQ-7) | Not designed yet |
| Entitlement (32) | Soft | `feature_ai_text` snapshot flag (OQ-1) | Free vs Premium undecided; off when absent |
| Settings (45) | Soft | Toggle, download, delete | Not designed yet; PROVISIONAL |
| Account and cloud save (7) | Soft | Report submission (OQ-6) | Reports are stored locally without it |
| Advisor suggestion producer (unassigned) | Soft | Suggestion ID and computed numbers (OQ-3) | No index system owns §9.1's suggestions yet |
| Random event producer (unassigned) | Soft | Event instance, participants, decided outcome (OQ-4) | No index system owns §9.2's "sự kiện ngẫu nhiên" |
| Dev tooling (43) | Soft | Offline quality harness (AC-17) | Release gating of R7 switches |

**Depended on by:** Guild screens (39) and Realtime world view (38) display its results; nothing in the simulation depends on it, by design (R1).

**Bidirectionality check.** Localization, Event bus, Member model, CA/PA (903/904 milestones, revealed traits), Retention, Items and loot, Skills, Schools and Gold economy already list this system. Local save does not list it yet (it has no list of features by design, Local save R6, but OQ-2 needs its owner's agreement); Settings, Entitlement and Free agents have no GDD. Recorded for the consistency pass (OQ-9).

## Tuning Knobs

All knobs live in data files (R13). None affects game balance; they trade text quality against device cost.

| Knob | Default | Safe range | Too high | Too low |
|---|---|---|---|---|
| `model_ram_total_min_mb` | 4,096 (0.5B) | 3,072–8,192 | Few devices eligible | Crashes or OS kills on small phones |
| `ram_headroom_mb` | 512 | 256–2,048 | Rarely runs | Game stutters, OS kills the app |
| `storage_margin` | 1.5 | 1.1–3.0 | Refuses installs with room to spare | Download fails mid-unpack |
| `battery_min_pct` | 30 | 0–80 | Rarely runs unplugged | Drains a low battery |
| `thermal_max` | 1 | 0–2 | Heat and throttling during play (§3.5) | Almost never runs on warm phones |
| `idle_min_s` | 5 | 1–60 (release ≥ 1) | Long sessions get few generations | Competes with play for CPU |
| `unload_after_idle_s` | 120 | 10–900 | Holds ~700 MB idle | Reload cost on every burst |
| `job_timeout_s` | 30 | 5–120 | A hung job blocks the queue longer | Long `vi` bios always time out (F3) |
| `fail_max` / `fail_cooldown_s` | 3 / 1,800 | 1–20 / 60–86,400 | Wasted battery on a failing device | Gives up on transient failures |
| `retry_max` | 1 | 0–5 | Battery spent on bad keys | One bad sample leaves a template |
| `max_chars[f]` | 600/800/300/200/160 | 40–1,200 | Rambling, more R5 failures | Prose too thin to beat the template |
| `chars_per_token[loc]` | en 4.0, vi 2.5 | 1.5–5.0 | Truncated JSON (R5 fails) | Wasted token budget |
| `prio[f]`, `queue_max` | F4 values, 32 | 0–9, 1–256 | — | Visible subjects wait |
| `cache_cap_kb`, `cache_count_max[f]` | 1,024; F7 values | 0–8,192 | Save grows | Templates come back often; more regeneration |
| `bio_milestones_max`, `chron_records_max` | 8, 20 | 1–32, 1–64 | Longer prompts, slower, more hallucination | Thin prose |
| `ai_text_enabled[f][loc]` | en on, vi off | bool | — | — |
| `tone_id` | unset (OQ-5) | one of the authored tones | — | — |
| `keep_stale_on_model_change` | false | bool | Old-model text shown after a model swap | — |
| `report_queue_max` | 200 | 10–2,000 | Small save growth | Reports lost while offline long |
| `reject_spelled_numbers` | true | bool | — | Uncheckable numbers reach the player |
| `gate_poll_s` | 1 | 0.25–10 | Slow to stop a job when play resumes | Polling cost |
| `get_budget_us` | 200 | 50–1,000 | — (a target, not a behaviour) | — |
| `quality_sample_n` / `quality_accept_min` | 200 / 90 % | 50–2,000 / 70–99 % | Longer release gate | Ships a locale whose text mostly falls back |

**Interactions:** `max_chars` and `chars_per_token` together set `max_tokens` (F3), and `max_tokens` against device speed sets whether `job_timeout_s` is reachable; tune the three together. `idle_min_s` and `thermal_max` together decide how often generation runs at all on a given phone.

## Visual/Audio Requirements

*Specialist lens applied: art-director (no agent spawned). No art bible exists (`design/art/` absent), so no art-bible principle is cited; re-check when it is written.*

- **No VFX and no sound.** This layer adds no events the player must react to. Generated text arriving is deliberately silent (R11: it appears on the next open).
- **AI mark.** A small pixel glyph (for example a brush-and-spark icon, 8×8 at 1× scale) placed after the last line of AI text, in the secondary text colour. Paired with a text label in accessibility mode, so the mark never relies on shape or colour alone.
- **Report control.** A flag glyph next to the AI mark, same size, with a touch target of at least 44×44 dp (padding, not a larger icon). Never shown on template text.
- **Typography.** AI text uses the same font, size and line height as the template it replaces, so a swap does not reflow the panel more than the length difference. Long prose panels (Chronicle) scroll; they never shrink text to fit.
- **Tone.** The visual frame of the Chronicle (parchment or scroll) belongs to the Chronicle screen owner (Event bus OQ-8), not to this layer.

## Game Feel

- **Zero latency to readable text.** `ai_text.get` returns within `get_budget_us` (200 µs) on the main thread, cache lookup only; no screen ever waits on the worker.
- **No frame cost during play.** The worker runs only when the player is idle (F2). Target: no frame over 16.6 ms caused by the layer on the reference device while the gate is open; generation threads run at below-normal priority.
- **No heat during play.** `thermal_max` = 1 keeps the phone out of throttling that would hurt FPS (§3.5).
- **Silent failure.** Rejections, timeouts and suspensions never produce a popup. The only visible state is Settings' "On (paused)".

## UI Requirements

- **Settings (45):** an "AI text (optional)" row with: a toggle; download size, required free storage (F1) and required RAM; download progress with pause/cancel; a "Delete pack" action showing the space freed; state label (Off / On / On (paused) / Not supported on this device); per-language note ("English only for now" while R7 has `vi` off). A one-time explainer on first enable: what it does, that it runs on the device, that text may be imperfect and can be reported.
- **Every AI text surface** (member card bio, Chronicle page, advisor panel, event dialog, negotiation dialog): the AI mark and report control (R9, R10).
- **Report dialog:** one tap opens a confirm sheet with optional reason chips (offensive, wrong facts, nonsense, other); confirm hides the text at once and shows "Reported — thank you" for 2 s. No free-text field (keeps the report payload free of personal data).
- **Negotiation and advisor dialogs:** prose sits in its own text area above the screen's fixed widgets (amount, choices, numbers). Removing the prose must leave a complete, usable dialog.

> **📌 UX Flag — AI text layer**: This system has UI requirements. In Pre-Production, run `/ux-design` for the Settings AI row and the report dialog, and fold the AI mark and report control into the interaction pattern library, **before** writing epics.

## Cross-References

| This GDD references | Document | Section | Nature |
|---|---|---|---|
| Five features, fallbacks, frame-and-cache principle, llama.cpp GGUF Q4, model size, idle and low-RAM rules, vi/en note, Premium [XÁC NHẬN] | `JX1_Tycoon_GDD.md` | §9.2 | Source of intent |
| AI locked as optional side feature | `JX1_Tycoon_GDD.md` | §2 | Constraint |
| One tone for names and text, feeds the LLM prompt; historical figures never monsters | `JX1_Tycoon_GDD.md` | §16.3 | Constraint (tone_id, R5 check 6) |
| In-app report button for AI content (Google Play) | `JX1_Tycoon_GDD.md` | §12.4.1, P6, P7 | Constraint (R9) |
| Locale tag on cached LLM text; templates for fallback; never translated | `design/gdd/localization.md` | R10, AC-23 | Conformed to |
| `read_history`, `milestones_for`, records carry IDs | `design/gdd/event-bus-and-history-log.md` | R8 | Consumed |
| Name record kept for departed members | `design/gdd/member-model.md` | R3 | Consumed (placeholders, R8) |
| Hidden vs revealed traits; exact-PA visibility | `design/gdd/ca-pa-and-traits.md` | R9–R12 | Constraint (R3) |
| `retention_view`; demand kinds; `p_counter` never shown | `design/gdd/retention-leaving-and-negotiation.md` | R5, F6, Interactions | Consumed; probability excluded (R3) |
| `register_section` contract | `design/gdd/local-save-and-migration.md` | R6 | PROVISIONAL use (OQ-2) |
| `catching_up` | `design/gdd/sim-core-and-tick-loop.md` | R15 | Gate input (F2) |

## Acceptance Criteria

*Specialist lens applied: qa-lead (no agent spawned); checked against Core Rules, Formulas and Edge Cases. Logic criteria run with a stub model (scripted outputs), so they are deterministic and need no download.*

- **AC-1 [Logic] (R2)** — **GIVEN** no pack installed, **WHEN** each of the five features is requested for a valid subject, **THEN** `get` returns `source = template` with non-empty text in both `vi` and `en`, and no worker thread exists.
- **AC-2 [Integration] (R1)** — **GIVEN** two runs of the same save and command log for 10,000 ticks, one with the stub model producing text for every request and one with the layer off, **WHEN** the end states are compared, **THEN** the simulation state hash is identical.
- **AC-3 [Logic] (R3)** — **GIVEN** a member with 1 revealed and 2 hidden traits and an exact PA not visible, **WHEN** a `bio` fact sheet is built, **THEN** it contains the revealed trait ID only, no PA value other than the displayed estimate bounds, and no probability field.
- **AC-4 [Logic] (R3)** — **GIVEN** an open leave request, **WHEN** a `nego` fact sheet is built, **THEN** it contains the demand kind, target and `R`, and does not contain `p_counter` or any trait effect value.
- **AC-5 [Logic] (R5.1–2)** — **GIVEN** stub outputs of invalid JSON, an extra field, an empty string and a string of `max_chars + 1`, **WHEN** each is validated, **THEN** each is rejected and the template is returned.
- **AC-6 [Logic] (R5.3)** — **GIVEN** a fact sheet naming members A and B, **WHEN** the stub output names C, **THEN** it is rejected; **WHEN** it names only A and B, **THEN** it is accepted.
- **AC-7 [Logic] (R5.4)** — **GIVEN** a fact sheet with the numbers {2, 40}, **WHEN** the output says "3" or "three", **THEN** it is rejected; **WHEN** it says "2" and "40", **THEN** it is accepted.
- **AC-8 [Logic] (R5.5–6)** — **GIVEN** a `vi` request, **WHEN** the output contains a CJK character or a blocklist term, **THEN** it is rejected.
- **AC-9 [Logic] (R8, F5)** — **GIVEN** a cached bio, **WHEN** the member is renamed, **THEN** `facts_hash` is unchanged and the displayed bio shows the new name; **WHEN** a trait is then revealed, **THEN** the entry is stale and the template is returned.
- **AC-10 [Logic] (R8)** — **GIVEN** a cached `en` entry, **WHEN** the active locale is `vi`, **THEN** the template is returned (Localization AC-23).
- **AC-11 [Logic] (R9)** — **GIVEN** a displayed AI bio, **WHEN** it is reported with no network, **THEN** the next `get` returns the template, no job is queued for that key, and one report record is stored; **WHEN** the facts change, **THEN** a job may be queued again.
- **AC-12 [UI] (R10, R11)** — **GIVEN** the pack on and an AI bio cached, **WHEN** the member card is opened, **THEN** the bio shows the AI mark and report control; a template bio shows neither. Screenshot retained in `production/qa/evidence/`.
- **AC-13 [Integration] (R11)** — **GIVEN** a member card open with a template bio, **WHEN** the job for that bio completes, **THEN** the visible text does not change until the card is closed and reopened.
- **AC-14 [Logic] (F2, R6)** — **GIVEN** each gate input set to its failing value in turn (flag off, catching up, free RAM below need + headroom, battery 29 % unplugged, thermal 2, idle 4 s), **WHEN** the gate is evaluated, **THEN** it is closed; with all at passing values it is open; a running job is cancelled within `gate_poll_s` + 1 s of the gate closing.
- **AC-15 [Logic] (F1)** — **GIVEN** RAM 4,096 / free 600 / pack 400 / margin 1.5, **THEN** eligible; **GIVEN** free 599, **THEN** `Ineligible`.
- **AC-16 [Logic] (F3, F4, F6, F7)** — **GIVEN** defaults, **THEN** `max_tokens[bio, vi]` = 272; a visible `bio` job runs before an earlier non-visible `nego` job; three stub timeouts put the state in `Suspended`, and one accepted job before the third resets the count; filling the cache past `cache_cap_kb` evicts the oldest-shown unreported entry and keeps reported stubs.
- **AC-17 [Integration, release gate] (R7)** — **GIVEN** the shipped model and frames, **WHEN** the dev-tooling harness runs `quality_sample_n` (200) fixed fact sheets per feature and locale, **THEN** the R5 acceptance rate is ≥ `quality_accept_min` (90 %) and a human review of 30 accepted samples finds 0 blocklist-class or hidden-trait-revealing texts; only then may that `ai_text_enabled[f][loc]` ship as on.
- **AC-18 [Integration] (R12, states)** — **GIVEN** a device that passes F1, **WHEN** the player downloads, then corrupts the pack file, then relaunches, **THEN** states run `NotInstalled → Downloading → Verifying → Off`, and after corruption `NotInstalled` with a notice; templates show throughout and the cache is kept.
- **AC-19 [Performance] (Game Feel)** — **GIVEN** the reference device with the gate open and a job running, **WHEN** a 60 s idle-screen trace is taken, **THEN** `get` p99 ≤ 200 µs, and during 60 s of active play with the pack on, no frame over 16.6 ms is attributable to the layer.
- **AC-20 [Logic] (R4)** — **GIVEN** the stub model in seed-echo mode, **WHEN** the same fact sheet and frame are generated twice, **THEN** both requests carry the same seed; after `frame_version` is raised, the seed differs and existing entries are stale.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Free or Premium?** §9.2 says "AI nằm trong bộ tính năng nâng cao của Premium [XÁC NHẬN]" — unconfirmed. This GDD reads one flag, `feature_ai_text`, from Entitlement and treats absent as off. Who gets the flag is a monetisation (scope) decision. **PROVISIONAL: Entitlement (32) — supplies `feature_ai_text` in its snapshot.** | User / Entitlement (32) | Before Entitlement GDD |
| OQ-2 | **Save section (schema change, not made here).** §9.2 and Localization R10 say the cache lives in the save. Registering an `ai_text` section (cache + report queue, ≤ `cache_cap_kb`) adds to the payload and needs a `SAVE_SCHEMA_VERSION` step and a fixture (Local save R14, R17). The section is presentation data: it must be excluded from leaderboard replays and parity tests. Alternative: a sidecar file next to the save. **PROVISIONAL: Local save (6) — accepts a non-simulation section via `register_section`.** | User / Local save owner | Before implementation |
| OQ-3 | **Who produces advisor suggestions?** §9.1 lists "gợi ý xếp đội boss theo khắc hệ"; no index system owns them (Utility AI scores members but does not publish suggestions). **PROVISIONAL: a suggestion producer — publishes `{suggestion_id, kind, member_ids, numbers}`.** Adding an owner is a scope change. | Systems index owner | Full Vision |
| OQ-4 | **Who produces random events?** §9.2 "Sự kiện ngẫu nhiên do game sinh" has no owner in the index. **PROVISIONAL: an event producer — publishes `{event_id, type, participant_ids, outcome}` with the outcome already decided.** Scope change if added. | Systems index owner | Full Vision |
| OQ-5 | **Tone.** §16.3 asks for one register (serious history vs folk legend). Frames carry `tone_id`; none is chosen. | Narrative director / user | Before frames are authored |
| OQ-6 | **Report delivery.** Where reports go (Supabase table via Account services? email?), consent wording, retention period, and whether Play policy accepts local-only reporting while offline. **PROVISIONAL: Account and cloud save (7) — offers an authenticated `submit_report` endpoint.** | Account (7) / release manager | Before Play submission |
| OQ-7 | **Free agents' bios.** **PROVISIONAL: Jianghu free agents (17) — free agents and NPC guild members are Member-model people with name records, so `bio` works unchanged; their hidden traits stay hidden.** | Free agents GDD | Full Vision |
| OQ-8 | **Device numbers.** RAM needs, tokens/s, thermal levels and the 0.5B vs 1.5B choice are estimates (`NOT SOURCEABLE` from the engine reference). Needs a benchmark on 3 target phones; consider adding a speed probe to F1. llama.cpp via GDExtension → becomes an ADR. | Technical director | Before Alpha port of this layer |
| OQ-9 | **Bidirectional dependencies.** Settings (45), Entitlement (32) and Free agents (17) must list this system when written; Local save must accept OQ-2. | Consistency pass | Next wave |
| OQ-10 | **Store disclosure.** Steam's AI-content disclosure and Play's Data safety form must describe on-device generation; confirm wording against official pages (GDD §12.4.1 says secondary sources only). | Release manager | Before store submission |
