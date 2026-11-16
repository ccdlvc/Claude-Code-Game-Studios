# Localization (vi/en)

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run, decisions in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: none yet (no `design/gdd/game-pillars.md`). Anchored to locked `JX1_Tycoon_GDD.md` lines §1 ("Ngôn ngữ: Tiếng Việt + Tiếng Anh [CHỐT]") and §16.1 (immutable IDs, display names in `i18n/`).
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief exist to check against. Player Fantasy is anchored to locked `JX1_Tycoon_GDD.md` lines instead. Re-run after pillars exist.

## Summary

Localization holds every piece of text the player reads, in Vietnamese and English, keyed by stable ID. It picks the player's language, looks text up, fills in names and numbers in that language's format, and falls back safely when a string is missing. The simulation, saves, events and leaderboards never contain display text, so switching language changes only what is drawn. Read this GDD before designing any screen, notification, Chronicle line or generated text, and before adding content that needs a name.

> **Quick reference** — Layer: `Foundation` · Priority: `Vertical Slice` (key discipline applies from MVP; the English coverage gate starts at Vertical Slice) · Key deps: `None` hard (soft: Data layer for the ID namespace, Dev tooling for the validator that runs these rules) · Feasibility: NOT SOURCEABLE for `Core` (no `docs/engine-reference/godot/modules/core.md`); `modules/ui.md` confirms `tr()` and `AUTOWRAP_WORD_SMART`; Vietnamese glyph coverage in fonts is not covered by any engine reference.

## Overview

Localization is a presentation-side data service. It owns two kinds of catalogue, both kept per locale in `i18n/`:

- **Content names.** These already exist: `names_{vi,en}.csv` and `names_items_{vi,en}.csv`, with columns `id, name, short, desc`. They cover the 10 schools, 15 zones, bosses, 26 buildings, currencies, titles and about 1,080 items and materials (`JX1_Tycoon_GDD.md` §17.1).
- **UI strings.** This catalogue is new: `ui_{vi,en}.csv` with columns `key, text, notes`. It holds every label, message, template and number-format token that is not the name of a content row.

At runtime the service resolves the active locale (`vi` or `en`). Given a key or content ID and typed arguments, it returns finished text. Names and numbers are formatted for that locale, and the service falls back safely when a string is missing. At build time, the shared content validator enforces this system's rules: full coverage in both locales, matching placeholders, NFC Unicode and no key collisions.

The system makes no gameplay decisions. Its contract to the rest of the game is: **no display string lives in code, content tables, the simulation, saves, events or leaderboard payloads.** All of these hold IDs. Text is produced only at draw time. That is why §16.1 can promise that renaming touches neither code nor saves, why the Event bus can say that a rename or a language switch cannot change history, and why a player can switch language mid-session and lose nothing.

Without this system, §1's locked bilingual launch would mean two forks of every screen. Every rename (§16 leaves all names to the designer) would be a code change. Generated prose (Chronicle, LLM text) would freeze in whichever language it was written in.

*No ADR is cited. `docs/architecture/` holds no ADR yet. The implementation approach is left to `/architecture-decision`: Godot's `TranslationServer` with CSV import versus a custom loader, how the per-locale files map to Godot's `keys,<locale>…` CSV layout, and font resources.*

## Player Fantasy

**Indirect.** Players feel this system on every screen without ever touching it, except for one switch in Settings. No game pillars exist yet, so none is quoted. The framing is anchored to locked lines of `JX1_Tycoon_GDD.md`, and should be re-anchored once `design/gdd/game-pillars.md` exists.

**"This game was made in my language."** A Vietnamese player opens the game for the first time. The guild hall is Tổng Đàn, the currency is Quan, and the first boss is Hoả Hạt Vương. Every diacritic is drawn correctly, and no tone mark is clipped by the line above. Nothing reads like a translation, because Vietnamese is the source language (§16: names were authored for a Vietnamese-history setting). The anchor is §1: *"Bối cảnh: lồng ghép lịch sử/văn hoá Việt Nam"* and *"Ngôn ngữ: Tiếng Việt + Tiếng Anh [CHỐT]"*.

**"…and it speaks to me too."** An English player gets the same world in English: Bronze Wall Sect, Lac Sword Order. Text never overflows a button, a number never reads `1.234.567` when they expect `1,234,567`, and no sentence says "1 members".

**"My story doesn't change when the words do."** A player switches from Tiếng Việt to English to show a friend. The Chronicle re-tells the same history in English, and every member, item and boss is still the same one. Nothing in the guild changed. The anchor is §16.1: *"Đổi tên không đụng code, không đổi save"*.

What each promise asks of the design:
- Vietnamese as the source language, with font rules for stacked diacritics (Visual/Audio).
- Per-locale number formats, plural rules and a fit rule for long English text (Formulas).
- Render-time-only text, so a switch is purely presentational (Core Rules R1 and R7).

## Detailed Design

> Specialist lenses applied, per §6 routing: Category `Core` → Foundation/Infrastructure row. Roles: `systems-designer` (primary), `gameplay-programmer` and `engine-programmer` (supporting).
>
> - **systems-designer**: the dangerous coupling is text leaking into deterministic state. Make "IDs only below the presentation line" a rule with a test, not a convention. Every state needs a defined fallback; there must be no blank-text state.
> - **gameplay-programmer**: callers must not concatenate strings. Vietnamese and English word order differ (`Hạ {boss}` vs `{boss} defeated`), so templates need named placeholders. Typed arguments let the formatter pick the number format, and callers never pre-format.
> - **engine-programmer**: the fatal and data-damaged screens (Sim core R10, Data layer UI Requirements) must render when `i18n/` or `data/` failed to load. That needs a small string set compiled into the build. Godot's `tr()` exists (ui.md); the file-format mapping and font fallback chain are ADR questions.
>
> No conflict between roles. No pillar conflict (none exist).

### Core Rules

**R1 — Text exists only at draw time.** No player-facing string may appear in code, `data/` tables, simulation state, saves, events, the history log, command payloads, analytics payloads or leaderboard payloads. These hold IDs and numbers. The presentation layer asks Localization for text when it draws. This restates and owns the rule that Data layer R9 and Event bus R-fields rely on. *Exceptions:* proper nouns (R8) and LLM output caches (R10), each stored with a defined treatment.

**R2 — Supported locales.** The game ships two locales: `vi` (Vietnamese, the **source** language) and `en` (English, a translation of `vi`). A release build must have 100% coverage in both (F5). The locale list is data: adding a third locale means adding files, not code. Adding one is out of scope (Open Questions).

**R3 — Two catalogues, one lookup.**
1. *Content names*: `i18n/names_{loc}.csv` and `i18n/names_items_{loc}.csv`, columns `id, name, short, desc`, keyed by content ID (unchanged from today).
   - `name` is the full display name.
   - `short` is the compact form for tight layouts (F4). It may equal `name`.
   - `desc` is the description, and may be empty.
2. *UI strings*: `i18n/ui_{loc}.csv`, columns `key, text, notes`.
   - `notes` is translator context and is never shown.
   - Every key starts with `ui_`. The content and UI namespaces are one namespace (Data layer: global uniqueness), so the prefix prevents collisions.
   - A key is lowercase ASCII `[a-z0-9_]`, at most 48 characters, the same format as a content ID.
3. One lookup serves both catalogues: `text(key_or_id, field = name, args = {})`.

**R4 — Text format rules** (validated, ERROR on breach):
- UTF-8 without BOM.
- Every cell is in Unicode **NFC**. Vietnamese has precomposed and decomposed forms for the same letter, and mixing them breaks search, comparison and some fonts.
- No leading or trailing whitespace, and no control characters. A line break is written `\n`.
- Placeholders are `{name}`, where `name` is lowercase snake case. A literal brace is written `{{` or `}}`.
- No markup in the catalogue. Emphasis and colour are applied by the UI around a placeholder, never inside a translated string.

**R5 — Templates and typed arguments.** A string with placeholders is a template. Callers pass **typed** arguments and never pre-formatted text. The formatter renders each type as follows:

| Argument type | Caller passes | Rendered as |
|---|---|---|
| `id` | a content ID | that ID's `name` (or `short` under F4) in the active locale |
| `member` | a member ID | the member's proper-noun name (R8), verbatim |
| `int` | integer display units | F1 grouped number |
| `compact` | integer display units | F2 compact number |
| `duration` | whole seconds | F6 duration |
| `count` | integer | F1 number; also selects the plural variant (F3) |
| `text` | player-entered text | verbatim (R8) |

- Every placeholder in a locale's string must appear in the other locale's string for the same key, and no extra ones may appear (placeholder parity, ERROR). Order may differ: that is the point of named placeholders.
- Callers convert internal units before calling. For example, XP is passed as `xp_milli / 1000`, rounded down, as the XP GDD requires. Localization never sees milli-units.

**R6 — Plural variants.** A key whose text depends on a count is written as two rows, `<key>_one` and `<key>_other`, in every locale. The rule F3 picks the variant. Vietnamese has no grammatical plural, so `vi` may give both rows the same text. Both rows must still exist, so the key set stays identical across locales.

**R7 — Locale selection.**
1. **First launch.** The OS language is read once. If it starts with `vi`, the locale is `vi`. Otherwise it is `fallback_locale` (default `en`).
2. **The player's choice** is made in Settings (45). It is stored as a device preference owned by Settings, **not** in the simulation save. It is never part of the content hash, RNG input, an event, or a leaderboard submission.
3. **A switch is live.** No restart is needed. On the next frame, every visible string is re-requested. Cached rendered text (Chronicle pages, tooltips, notification text) is invalidated. No frame shows a mix of the two languages on one screen once the switch has been applied.

**R8 — Proper nouns and player text are not translated.**
- Member personal names are proper nouns. They are shown identically in both locales, from the Member model's name record (PROVISIONAL, see Open Questions).
- Player-entered text, such as a guild name, is shown verbatim in every locale and never passed through lookup. It is normalised to NFC on entry, so R4 holds for everything drawn.
- Content names (schools, zones, items) *are* translated. They come from R3.

**R9 — Missing-string fallback.** A lookup never returns empty text. The chain is:
1. The active locale.
2. The other shipped locale. `vi` is the source, so `en` falls back to `vi`, and `vi` falls back to `en`.
3. In a dev build, the marker `⟦<key>⟧`. In a release build, the text of the core-set key `ui_unknown_name`.

Each missing key is logged once per session. Steps 2 and 3 should be unreachable in a release build, because the validator blocks it (F5). They exist for dev builds and for content hot-loaded in development. An empty `short` falls back to `name`. An empty `desc` renders as no description: the UI hides the line, and no marker is shown.

**R10 — Generated prose.**
- *Chronicle and event feed.* Lines are rendered from `ui_chron_*` and `ui_feed_*` templates, filled from history-log records (IDs and numbers) at draw time. A language switch therefore re-tells all of history in the new language (Event bus: records carry IDs, never text).
- *LLM text (AI text layer, 36).* Generated text is cached in the save with a locale tag (§9.2: results are cached into the save). It is shown only when its tag equals the active locale. Otherwise the template fallback for that feature is shown, and the AI text layer may regenerate the text in the background. Cached LLM text is never translated by this system.
- *Push notifications (46).* Text is rendered in the active locale when the notification is scheduled. A locale switch re-schedules pending notifications with re-rendered text.

**R11 — The core string set.** About 20–30 UI keys are **compiled into the build** for both locales, so they render when `i18n/` or `data/` cannot load. They cover the Data layer's data-damaged screen, the Sim core's fatal-failure screen, the loading screen and the language name of each locale. The same keys also exist in `ui_{loc}.csv`. The validator checks that the compiled set and the file set are byte-identical, so the two can never drift. The core set may not use `id` arguments, because content may be unavailable.

**R12 — No text in art.** Sprites, UI art and AI-generated images contain no readable words in any language. Every visible word is drawn by the text renderer from a catalogue. AI image tools often bake pseudo-text into images (§12.4), so such text is removed at art review.

**R13 — Sorting and comparison.** When a UI list sorts by display name, it sorts in the active locale's collation. Vietnamese order is a ă â b c d đ e ê … with tone marks as a secondary key. Simulation logic never sorts, picks or breaks ties by display name, only by ID (Data layer: IDs are meaning-free, and display names are never used to find or classify content).

**R14 — MVP and Vertical Slice.** From MVP onward, every string goes through lookup. No string is hard-coded, as §3.3 and the systems index require. The MVP may ship `vi` only with `en` incomplete, and dev-build fallback (R9) covers the gaps. The 100% coverage gate for both locales (F5) applies from the Vertical Slice build onward. This follows the systems index scope ("designed now, built in Vertical Slice") and does not change it.

**R15 — Pseudo-locale (dev only).** Dev builds offer a third locale, `qps`. For each string it shows the **longer** of the `vi` and `en` texts, wrapped as `[Ẫ…]`. The width shows the worst-case layout, and `Ẫ` shows the tallest Vietnamese stacked diacritic, so clipping is visible. `qps` never ships, and the validator rejects it in a release build.

### States and Transitions

**Catalogue state**

| State | Meaning | Enters from | Exits to |
|---|---|---|---|
| `Boot` | Only the compiled core string set (R11) is available | app start | `Loading` |
| `Loading` | `i18n/` files are being read | `Boot` | `Ready`, `Degraded`, `Failed` |
| `Ready` | All required keys present for the active locale | `Loading`, `Degraded` (on content reload) | `Loading` (dev hot reload) |
| `Degraded` | Loaded, but some keys missing; R9 fallback in use; dev builds only show the marker | `Loading` | `Ready`, `Loading` |
| `Failed` | `i18n/` unreadable or malformed | `Loading` | none this session; the core set shows the data-damaged screen |

A release build cannot reach `Degraded` with committed files, because the validator blocks the build (F5). If it is reached anyway, for example through a damaged install, the game runs on the R9 fallback chain, which in a release build ends at `ui_unknown_name`, never at the dev marker.

**Locale state**

| State | Meaning | Transition |
|---|---|---|
| `Unresolved` | First launch, no preference stored | → `Active(L)` via R7.1 |
| `Active(L)` | All text rendered in L | → `Switching` on a Settings change |
| `Switching` | Caches invalidated; visible text re-requested | → `Active(L')` on the next frame |

There is no transition that touches simulation state.

### Interactions with Other Systems

| System | Direction | Data | Owner of interface |
|---|---|---|---|
| Data layer (3) | sibling | Shares the global ID namespace. The data layer never mints IDs starting `ui_` (PROVISIONAL). Its R9 points display text here | Data layer owns IDs; Localization owns text |
| Dev tooling and parity harness (43) | tooling runs these rules | The shared validator runs R3–R6, R11, R15 and F5 checks over `i18n/` | Localization defines the rules; Dev tooling owns the validator program |
| Event bus and history log (42) | bus → reader | History records (IDs, numbers) filled into `ui_chron_*` templates | Event bus owns records; Chronicle owner renders |
| Member model (8) | Member → Localization | The member's proper-noun name record by member ID (R8) | Member model (PROVISIONAL) |
| Settings (45) | Settings → Localization | `set_locale(L)`; stores the preference | Settings owns the control and storage |
| Realtime world view (38), Guild screens (39) | caller | `text(key, field, args)`; F4 fit | Localization |
| Sim core (1), Data layer (3) failure screens | caller | Core string set keys (R11) | Localization; layout by Guild screens |
| AI text layer (36) | both | Templates for fallback; locale tag on cached text (R10) | AI text layer owns generation |
| Local push notifications (46) | caller | Render at schedule time; re-schedule on switch (R10) | Notifications (PROVISIONAL) |
| Analytics (37) | reader | Active locale code as a dimension only; no text in events | Analytics |
| In-app purchases (34) | none | Store prices are shown as the platform store formats them, never through F1/F2 | IAP |
| Leaderboards (35) | none | Submissions carry IDs and numbers only; guild names are player text (R8) | Leaderboards |

## Formulas

All formulas run on integers. No float is used, so `vi` and `en` produce identical digits on every device. They take values already in display units (R5).

### F1 — Grouped integer

The format_int formula is defined as:

`format_int(v, L) = sign(v) + group(|v|, sep_thousands[L])`

`group` inserts `sep_thousands[L]` every 3 digits from the right. `sign(v)` is the locale's minus string when `v < 0`, and empty otherwise.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| v | int64 | −2^63 to 2^63−1 | calculated (caller) | value in display units |
| L | enum | `vi`, `en` | calculated (R7) | active locale |
| sep_thousands[L] | string | one character | data file (`ui_num_sep_thousands` in `ui_{L}.csv`) | `.` for vi, `,` for en |
| minus[L] | string | one character | data file (`ui_num_minus`) | `-` in both |

**Output Range:** 1 to 26 characters. 0 renders as `0`. `−2^63` is formatted from its unsigned magnitude, so there is no overflow on negation.
**Example:** `v = 1234567` gives `1.234.567` in vi and `1,234,567` in en. `v = -1200` gives `-1.200` in vi and `-1,200` in en.

### F2 — Compact number

The format_compact formula is defined as:

`format_compact(v, L) = format_int(v, L)` when `|v| < compact_threshold`. Otherwise:
`k = max{ e ∈ {3, 6, 9, 12} : |v| ≥ 10^e }`
`tenths = floor(|v| / 10^(k−1))`, computed as integer division, so it cannot overflow
`out = sign(v) + format_int(floor(tenths / 10), L) + (tenths mod 10 ≠ 0 ? sep_decimal[L] + (tenths mod 10) : "") + suffix_k[L]`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| v | int64 | full int64 | calculated (caller) | value in display units |
| compact_threshold | int | 1,000–1,000,000 | data file (`config.csv` key `l10n_compact_threshold`, default 10,000) | below this, numbers are shown in full |
| sep_decimal[L] | string | one character | data file (`ui_num_sep_decimal`) | `,` for vi, `.` for en |
| suffix_k[L] | string | 1–4 characters | data file (`ui_num_suffix_3/6/9/12`) | vi: `K`, ` Tr`, ` Tỷ`, ` NTỷ`; en: `K`, `M`, `B`, `T` |
| k | int | 3, 6, 9, 12 | calculated | magnitude chosen |
| tenths | int64 | 10–92,233,720 | calculated | value in tenths of the unit, floored |

**Output Range:** at most about 13 characters. The result **rounds down, never up**, so a player is never shown more gold than they hold. Below the threshold, F2 equals F1. At `k = 12` the integer part may exceed 999 (for example `9.223.372 NTỷ`), and it is grouped by F1.
**Example:** `12,345,678` gives `12,3 Tr` in vi and `12.3M` in en. `1,999,999` gives `1,9 Tr` and `1.9M`, never `2M`. `10,000` gives `10K` in both. `9,999` gives `9.999` and `9,999`. `5,000,000` gives `5 Tr` and `5M`, with no trailing `,0`.

### F3 — Plural category

The plural_category formula is defined as:

`plural_category(n, L) = (L = en and n = 1) ? "one" : "other"`

The variant key is then `<key>_<plural_category>`. If that row is missing, it falls back to `<key>_other`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n | int64 | full int64 | calculated (caller, `count` argument) | the count |
| L | enum | `vi`, `en` | calculated | active locale |
| plural rule per locale | rule | `en`: one/other; `vi`: other only | constant | CLDR cardinal rules for these two languages |

**Output Range:** `one` or `other`. In `en`, `0`, `-1` and `2` give `other`, and only `1` gives `one`. In `vi` the result is always `other`.
**Example:** `ui_members_count` with `n = 1` gives `1 member` in en and `1 thành viên` in vi. With `n = 0` it gives `0 members` and `0 thành viên`.

### F4 — Fit to field

The fit_text formula is defined as:

`fit(id, W) = name` if `w(name) ≤ W`. Otherwise `short` if `w(short) ≤ W`. Otherwise `truncate(short, W − w("…")) + "…"`.

UI strings (R3.2) have no `short`. A UI string that does not fit is wrapped (`AUTOWRAP_WORD_SMART`, engine reference `modules/ui.md`). It is never truncated, because a truncated instruction is a wrong instruction.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| W | int | > 0 px | calculated (layout) | width available to the field |
| w(s) | int | ≥ 0 px | calculated (renderer) | rendered width of `s` in the field's font. This is measured in pixels, **not** characters |
| name, short | string | — | data file (`names_*`) | content name variants |

**Output Range:** text whose width is at most W. The full `name` is still available in the tooltip or detail view, so truncation never hides an identity. If `W < w("…")`, only `…` is shown.
**Example:** English names are measured at a median of 1.2× and a 95th percentile of 2.09× the Vietnamese length for schools, zones and buildings, and 1.07× and 1.54× for items (committed `i18n/`, 2026-11-16). A building field sized for `Tổng Đàn` may need `short` in English, while a list row shows `name`.

### F5 — Coverage gate

The coverage formula is defined as:

`coverage(L) = |{ k ∈ Required : text_L(k) non-empty }| / |Required|`, where `Required = ContentIDs ∪ UIKeys`

The gate passes when, for every shipped locale, `coverage(L) = 1` **and** placeholder parity (R5), NFC (R4), key-set equality across locales and the R11 core-set identity all hold.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| ContentIDs | set | ~1,160 today | calculated (validator: schools, zones, boss monsters, materials, items, buildings, as in `content_validator.py`; skills later) | content that needs a `name` |
| UIKeys | set | — | data file (`ui_vi.csv`, the source locale's key set) | every UI key |
| text_L(k) | string | — | data file | `name` column for content, `text` for UI |

**Output Range:** 0 to 1. A Vertical Slice build or later requires 1 for both locales, and anything less is a validator ERROR. An MVP build requires 1 for `vi` only, and `en` below 1 is a WARN (R14). Empty `Required` is impossible, because the core set alone is non-empty.
**Example:** the committed data today has content coverage 1 for both locales (validator prints `0 lỗi`). There is no `ui_*.csv` yet, so UIKeys is empty until the first screen is built. Only the R11 core set is mandatory then.

### F6 — Duration

The format_duration formula is defined as:

`format_duration(s, L)` splits `s ≥ 0` into days, hours, minutes and seconds. It renders the `duration_units_shown` largest units starting from the first non-zero one, flooring the remainder. Each unit is rendered through its plural key `ui_dur_<unit>_<cat>` (F3). The units are joined with `ui_dur_join[L]`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| s | int64 | ≥ 0 | calculated (caller, whole seconds) | duration |
| duration_units_shown | int | 1–4 | data file (`config.csv` key `l10n_duration_units`, default 2) | units displayed |
| ui_dur_* | string | — | data file | vi `{n} ngày / giờ / phút / giây`; en `{n}d / h / m / s` |

**Output Range:** from `0 giây` / `0s` (for `s = 0`) up to the days count with grouping. A negative `s` is a caller bug: it is clamped to 0 and logged.
**Example:** `s = 29,520` gives `8 giờ 12 phút` and `8h 12m`. `s = 90,061` gives `1 ngày 1 giờ` and `1d 1h` (the remaining 1 min 1 s is floored away). `s = 59` gives `59 giây` and `59s`.

## Edge Cases

- **If a key is missing in the active locale**: R9 chain (other locale → `⟦key⟧` marker in dev; `ui_unknown_name` in release), logged once per key per session.
- **If a locale's file is missing entirely in a dev build**: the catalogue goes to `Degraded` and every lookup uses the other locale. In a release build the validator has blocked it. If it is reached through a damaged install, the game behaves the same as in dev, but without the marker.
- **If `i18n/` cannot be read at all**: the catalogue enters `Failed`. Only the core set renders, and the data-damaged screen is shown (R11). The game does not continue into a screen whose text would all be markers.
- **If the OS language is `vi-VN`, `vi`, or any `vi_*`**: the locale is `vi`. If it is anything else (including unreadable): `fallback_locale`.
- **If the stored preference names a locale that is not shipped** (for example a removed `qps` in a release build): it is treated as `Unresolved` and R7.1 runs again.
- **If the player switches locale mid-animation or during offline catch-up**: the switch applies on the next frame. The simulation is unaffected, because locale is not simulation input (R1, R7.2).
- **If a template's argument is missing at call time**: the placeholder renders as `?` and the error is logged. A placeholder is never left as raw `{name}` in front of the player.
- **If an argument is passed that the template does not use**: it is ignored. This is legal, so one call site can serve both locales.
- **If an `id` argument names an ID that has no name** (only possible in a dev build): R9 applies to that name.
- **If an `id` argument names a retired or not-yet-live content row** (Data layer liveness): its name still resolves. Names exist for every ID ever issued, so history and old saves can always be named (§16.1, Event bus milestone naming).
- **If a member record has been deleted** (departed member): the name comes from the Member model's permanent name record (Event bus: Member model keeps a name record for every ID ever issued). If that is absent, `ui_unknown_member` is shown.
- **If player-entered text contains characters the font cannot draw** (emoji, CJK): the font fallback chain is tried (Visual/Audio). If no font has the glyph, it renders as the font's missing-glyph box. The text is never rejected after entry. Input restrictions belong to the entry field's owner (Open Questions).
- **If player-entered text is in decomposed Unicode** (common from some Vietnamese keyboards): it is normalised to NFC on entry (R8), so two visually identical guild names compare equal.
- **If a string contains `{` that is not a placeholder**: the source must write `{{`. A lone `{` is a validator ERROR.
- **If `v` is `−2^63` in F1 or F2**: the magnitude is computed in unsigned form, so there is no overflow (F1 Output Range).
- **If F2 floors to a value with a zero tenth** (`5,000,000`): the decimal is dropped (`5 Tr`), never `5,0 Tr`.
- **If an English UI string is much longer than its Vietnamese source**: the string wraps (F4), and the screen's layout must allow it. This is verified with `qps` (R15) screenshots, not by a character limit in the validator.
- **If a store price arrives from Google Play or the App Store**: it is shown exactly as the store formatted it. Reformatting it would risk showing a price different from the one charged.
- **If a cached LLM line's locale tag differs from the active locale**: the template fallback is shown (R10). Text in one language is never shown in a UI set to the other.
- **If two content rows have the same display name in one locale**: this is allowed (the names are not keys) but produces a WARN. Players cannot tell them apart in a list. The validator lists duplicates per locale.

## Dependencies

**Upstream (this system needs):**

| System | Hard/Soft | Interface | Notes |
|---|---|---|---|
| Data layer and content pipeline (3) | Soft | Global ID namespace; set of content IDs needing names | Runtime lookup works without it (it only needs `i18n/`); the coverage check needs the ID set |
| Dev tooling and parity harness (43) | Soft | The shared validator program executes this system's build-time rules | Without it, rules are unenforced, not broken |
| Member model (8) | Soft | Proper-noun name per member ID (R8) | PROVISIONAL, not designed yet |

**Downstream (depend on this system):**

| System | Hard/Soft | What they need |
|---|---|---|
| Realtime world view (38) | Hard | `text()`, F1–F4, F6, live switch |
| Guild screens (39) | Hard | Same, plus failure-screen core strings (R11) |
| Settings (45) | Hard | Locale list with each language named in itself; `set_locale` |
| AI text layer (36) | Hard | Template fallbacks, locale-tagged cache rule (R10) |
| Sim core (1), Data layer (3) | Soft | Core string set for their failure screens (R11) |
| Schools (20), XP curve (22) | Soft | Names and refusal-reason strings by key; XP display uses F1 |
| Event bus (42) / Chronicle owner | Soft | `ui_chron_*` templates rendered from records |
| Local push notifications (46) | Soft | Render at schedule time, re-schedule on switch |
| Analytics (37) | Soft | Locale code as a dimension |

**Bidirectional check.**
- Data layer and Dev tooling already list Localization (4) as a soft dependency for name coverage (consistent).
- Event bus lists Localization as "none: records carry IDs". This is consistent, because the Chronicle owner, not the bus, calls Localization.
- Schools and XP curve list Localization (consistent).
- Sim core AC-35 is pending on this GDD. R11 supplies its strings.
- Settings (45), 36, 38 and 39 list Localization in the systems index. Their GDDs do not exist yet.

## Tuning Knobs

| Knob | Where | Default | Safe range | Too low | Too high |
|---|---|---|---|---|---|
| `l10n_compact_threshold` | `config.csv` | 10,000 | 1,000–1,000,000 | Small amounts shown as `1,2K`, losing precision players care about early | Long numbers overflow HUD fields late game |
| `l10n_duration_units` | `config.csv` | 2 | 1–4 | `8 giờ` hides that the boss is 59 min away from the next hour | `1 ngày 1 giờ 1 phút 1 giây` is noise on timers |
| `fallback_locale` | `i18n` locale meta (`ui_meta` key in core set) | `en` | `vi` or `en` | — | — (choosing `vi` would show Vietnamese to non-Vietnamese OS users) |
| Number tokens `ui_num_*` | `ui_{L}.csv` | see F1/F2 | any one/short string | — | A long suffix breaks F2's ~13-char budget |
| Duration tokens `ui_dur_*` | `ui_{L}.csv` | see F6 | — | — | — |
| `short` per content row | `names_*.csv` | = `name` | ≤ `name` length | — | A `short` longer than `name` defeats F4 (WARN) |

Interactions: `l10n_compact_threshold` has no effect on fields that always use F1. `l10n_duration_units = 1` makes the minute and second plural keys reachable only for durations under one hour. Both are noted here, not elsewhere.

## Visual/Audio Requirements

Category `Core`: this section is optional, but it is authored because fonts are a hard feasibility risk for Vietnamese. There is no art bible (`design/art/` does not exist), so these requirements are drafted from §1 and §3.5. `art-director` lens applied in this conversation; no agent spawned.

- **Glyph coverage.** Every UI font covers Basic Latin, Latin-1 Supplement, Latin Extended-A/B (`Ă ă Đ đ Ơ ơ Ư ư`) and **Latin Extended Additional U+1EA0–U+1EF9** (`Ạ…ỹ`, the precomposed tone-marked vowels). A font without full Vietnamese coverage is not used for any player text.
- **Stacked diacritics.** Letters such as `Ẫ Ổ Ữ` carry two marks above. Line height and the label's top padding must fit them without clipping or touching the line above. This applies to the pixel font in particular: pixel fonts often ship Vietnamese with marks squeezed into the cap height. `qps` (R15) is the check.
- **Pixel-art style.** The pixel font must keep tone marks legible at the smallest UI size used on a 30-FPS mid-range phone (§3.5). The minimum size is set by the art bible when it exists (Open Questions).
- **Font fallback chain.** primary pixel font → a Vietnamese-complete fallback → the engine default. This covers player-entered glyphs (Edge Cases).
- **No text in art** (R12).
- **Audio.** There is no voice-over. Neither locale has spoken lines in scope, so there is nothing to localise in audio.

NOT SOURCEABLE: no `docs/engine-reference/godot/` file covers font glyph coverage, font fallback or Vietnamese shaping in Godot 4.7. The font choice and fallback setup must be verified in the engine spike before it is committed (→ ADR).

## Game Feel

Optional for `Core`, so this section is kept short. A language switch must feel instant: the next frame is fully in the new language, with no loading screen and no restart (R7.3). Formatting must never make numbers look as if they are jittering. F2 flooring means a rising gold count reads `1,9 Tr` → `2 Tr` and never flickers between `2 Tr` and `1,9 Tr`.

## UI Requirements

- **Settings → Language.** A list with one row per shipped locale. Each row is labelled **in its own language** (`Tiếng Việt`, `English`) and never translated, so a player stuck in the wrong language can find their own. The current locale is marked with text or an icon, not by colour alone. Selecting a row applies immediately (R7.3) with no confirm dialog. The control is owned by Settings (45).
- **Every text field** is designed for the longer of its two locales, or wraps (F4). Screens are signed off with screenshots in `vi`, `en` and `qps` (R15).
- **Truncated content names** (F4) always have the full name reachable in a tooltip or detail view.

> **📌 UX Flag — Localization**: this system has UI requirements (the language list, and the layout rule for every screen). In Pre-Production, run `/ux-design` for the Settings screen, and include `vi`, `en` and `qps` states in every screen's UX spec. Stories that reference UI should cite `design/ux/[screen].md`.

## Cross-References

| This GDD references | Document | Section / rule | Nature |
|---|---|---|---|
| Display text is not content; global ID uniqueness | `data-layer-and-content-pipeline.md` | R9, ID rules, OQ-4 (skill names) | Rule dependency |
| Validator name-coverage check | `data-layer-and-content-pipeline.md`, `dev-tooling-and-parity-harness.md` | AC-29; `make validate` | Tooling dependency |
| Data-damaged screen strings | `data-layer-and-content-pipeline.md` | UI Requirements ("always-available UI string set") | Supplied by R11 |
| Fatal-failure screen strings | `sim-core-and-tick-loop.md` | R10, AC-35, OQ-9 | Supplied by R11 |
| Records carry IDs, never text; member name records | `event-bus-and-history-log.md` | Fields rule, Member model dependency | Rule dependency |
| School names and refusal reasons by key | `schools-and-school-change.md` | UI Requirements | Consumer |
| XP shown as `xp_milli / 1000` floored | `xp-and-level-pacing-curve.md` | UI Requirements | Consumer, uses F1 |
| Locked languages, immutable IDs, names in `i18n/`, LLM language note | `JX1_Tycoon_GDD.md` | §1, §3.3, §9.2, §16, §17 | Source of intent |
| `tr()`, autowrap | `docs/engine-reference/godot/modules/ui.md` | Localization-Ready UI | Engine capability |

## Acceptance Criteria

Each criterion is marked **[Logic]** (automated unit test, BLOCKING), **[Integration]** (automated, multi-system) or **[UI]** (retained screenshot in `production/qa/evidence/`). A "fixture" is a temporary copy of `i18n/` (and `data/` where needed) that the test modifies.

**Catalogue and validation (R3–R6, R11, F5)**
- **AC-1 [Logic]** — **GIVEN** the committed `data/` and `i18n/`, **WHEN** the validator runs, **THEN** it reports 0 errors, and `coverage(vi) = coverage(en) = 1` over the content ID set.
- **AC-2 [Logic]** — **GIVEN** a fixture where one cell of `names_vi.csv` is in decomposed (NFD) form, **WHEN** the validator runs, **THEN** it exits 1, naming the file, the ID and "NFC".
- **AC-3 [Logic]** — **GIVEN** a fixture where `ui_vi.csv` has `ui_x = "Hạ {boss}"` and `ui_en.csv` has `ui_x = "{monster} defeated"`, **WHEN** the validator runs, **THEN** it exits 1 with a placeholder-parity error naming `ui_x`.
- **AC-4 [Logic]** — **GIVEN** a fixture where a key exists in `ui_vi.csv` but not `ui_en.csv`, **WHEN** the validator runs in Vertical Slice mode, **THEN** it exits 1. **WHEN** it runs in MVP mode, **THEN** it reports a WARN and exits 0.
- **AC-5 [Logic]** — **GIVEN** a fixture with a UI key not starting `ui_`, or a content ID starting `ui_`, **WHEN** the validator runs, **THEN** it exits 1, naming the key.
- **AC-6 [Logic]** — **GIVEN** a fixture where one core-set string differs between the compiled set and `ui_en.csv`, **WHEN** the validator runs, **THEN** it exits 1, naming the key.
- **AC-7 [Logic]** — **GIVEN** a fixture with a lone `{` in a string, **WHEN** the validator runs, **THEN** it exits 1. **GIVEN** `{{` instead, **THEN** the string renders a literal `{`.
- **AC-8 [Logic]** — **GIVEN** a plural key with only `_other` in `en`, **WHEN** the validator runs, **THEN** it exits 1 (both variants required in every locale, R6).

**Lookup and fallback (R5, R9)**
- **AC-9 [Logic]** — **GIVEN** a catalogue where `ui_y` exists only in `vi`, **WHEN** `text("ui_y")` is called with locale `en`, **THEN** it returns the `vi` text, and the miss is logged exactly once over 100 calls.
- **AC-10 [Logic]** — **GIVEN** `ui_z` exists in neither locale, **WHEN** it is looked up in a dev build, **THEN** the result is `⟦ui_z⟧`. **WHEN** it is looked up in a release build, **THEN** the result is the text of `ui_unknown_name`. The result is never empty.
- **AC-11 [Logic]** — **GIVEN** the template `"{zone}: {n}"` and args `{zone: id "zone_01"}` with `n` missing, **WHEN** rendered, **THEN** the output is `<zone_01 name>: ?` and an error is logged.
- **AC-12 [Logic]** — **GIVEN** an item with an empty `short`, **WHEN** `text(id, short)` is called, **THEN** it returns `name`. **GIVEN** an empty `desc`, **THEN** `text(id, desc)` returns empty, and no marker is shown.

**Formulas**
- **AC-13 [Logic] (F1)** — `format_int` returns, for `0`, `1234567`, `-1200` and `−2^63` in vi and en, exactly: `0`/`0`, `1.234.567`/`1,234,567`, `-1.200`/`-1,200`, `-9.223.372.036.854.775.808`/`-9,223,372,036,854,775,808`.
- **AC-14 [Logic] (F2)** — with `compact_threshold = 10,000`, `format_compact` returns: `9999` → `9.999`/`9,999`; `10000` → `10K`/`10K`; `1999999` → `1,9 Tr`/`1.9M`; `5000000` → `5 Tr`/`5M`; `12345678` → `12,3 Tr`/`12.3M`; `2^63−1` → `9.223.372 NTỷ`/`9,223,372T`.
- **AC-15 [Logic] (F3)** — in `en`, `plural_category` returns `one` for 1, and `other` for 0, 2 and −1. In `vi` it returns `other` for all four.
- **AC-16 [Logic] (F6)** — with `duration_units_shown = 2`, `format_duration` returns: `0` → `0 giây`/`0s`; `59` → `59 giây`/`59s`; `29520` → `8 giờ 12 phút`/`8h 12m`; `90061` → `1 ngày 1 giờ`/`1d 1h`; `-5` → `0 giây`, and an error is logged.
- **AC-17 [Logic] (F4)** — **GIVEN** a mock measure `w(s) = 10 px × len(s)` and the name `"Bronze Wall Sect"` with short `"Bronze Wall"`, **WHEN** fit is called at `W = 160`, `120` and `60`, **THEN** it returns `Bronze Wall Sect`, `Bronze Wall` and `Bronz…` (60 px − 10 px for `…` = 50 px, which fits 5 characters).

**Locale selection and isolation (R1, R7)**
- **AC-18 [Logic]** — **GIVEN** no stored preference, **WHEN** the OS language is `vi_VN`, `vi`, `en_US` or `fr_FR`, **THEN** the locale is `vi`, `vi`, `en` and `en` respectively.
- **AC-19 [Integration]** — **GIVEN** a seeded run, **WHEN** it is simulated for 10,000 ticks once in `vi` and once in `en`, with a locale switch at tick 5,000 in a third run, **THEN** all three produce byte-identical saves, history logs and content hashes.
- **AC-20 [Integration]** — **GIVEN** the save file, event payloads, command payloads and a leaderboard submission from AC-19, **WHEN** they are scanned for any `name` value from `i18n/` longer than 3 characters, **THEN** zero matches are found. Member proper names (R8) are excluded.
- **AC-21 [UI]** — **GIVEN** the guild screen open in `vi`, **WHEN** the player selects English in Settings, **THEN** the next captured frame shows the screen fully in English, without a restart. Screenshots before and after are retained.
- **AC-22 [Integration] (R10)** — **GIVEN** a Chronicle with at least 5 records, **WHEN** the locale is switched, **THEN** the same number of lines is shown, each naming the same IDs, in the new language.
- **AC-23 [Logic] (R10)** — **GIVEN** a cached LLM line tagged `en`, **WHEN** the active locale is `vi`, **THEN** the template fallback is returned, not the cached line.

**Failure path and visuals (R11, R12, R15, Visual/Audio)**
- **AC-24 [UI]** — **GIVEN** a dev build with `i18n/` removed, **WHEN** the game starts, **THEN** the data-damaged screen is shown with correct text in the stored locale, from the core set. A screenshot is retained for vi and en.
- **AC-25 [UI]** — **GIVEN** the `qps` locale, **WHEN** every Vertical Slice screen is captured, **THEN** no text overflows its container, and no `Ẫ` mark is clipped or touches the line above. One screenshot per screen is retained.
- **AC-26 [UI]** — **GIVEN** a string containing every Vietnamese vowel with every tone mark (`ui_dev_glyph_test`), **WHEN** it is rendered in every UI font at its smallest used size, **THEN** every glyph is drawn, with no missing-glyph box. A screenshot is retained.
- **AC-27 [Logic] (R15)** — **GIVEN** a release build configuration, **WHEN** the locale list is read, **THEN** it contains exactly `vi` and `en`, and setting `qps` is refused.

Performance: lookups are cached per locale, so `text()` adds no per-frame allocation for a key already rendered this locale. The budget is set with the UI performance budget in the architecture phase (Open Questions).

QA lens (`qa-lead`) applied in this conversation:
- Every core rule R1–R15 has a criterion, except R12 (no text in art) and R13 (collation). R12 is a manual art-review check, not automatable. R13's Vietnamese collation is listed as an Open Question, because the engine support for it is NOT SOURCEABLE.
- Every formula F1–F6 has a criterion with boundary values.
- AC-19 and AC-22 are the cross-system checks.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **PROVISIONAL: Member model (8)** — assumes each member has a proper-noun personal name, stored as a name record by member ID and shown verbatim in both locales (R8). Are names generated from Vietnamese name parts, and should English show them with diacritics (assumed yes)? | Member model | When Member model GDD is written |
| OQ-2 | **PROVISIONAL: Data layer (3)** — assumes content IDs never start with `ui_` (R3.2). The Data layer's ID format rule should state this; not edited here. | Data layer / consistency pass | Next `/consistency-check` |
| OQ-3 | **PROVISIONAL: Settings (45)** — assumes Settings stores the locale as a device preference outside the sim save. Should it sync through Account and cloud save (7) so a new device opens in the player's language? | Settings | When Settings GDD is written |
| OQ-4 | **PROVISIONAL: Local push notifications (46), AI text layer (36)** — assumes R10 (render at schedule time, re-schedule on switch; locale-tagged LLM cache). | Those systems | Full Vision |
| OQ-5 | **Skill display names** (Data layer OQ-4, §17.2): skills have none yet, so F5's content set omits skills. Add skill IDs to the required set once named. 91 vi / 42 en item names are still placeholder `Bậc N` / `Tier N` names (§17.1). Should the validator WARN on placeholder names before release? | Localization + content (user) | Before Vertical Slice content lock |
| OQ-6 | **Catalogue file layout vs §3.3.** §3.3 proposed `i18n/vi.csv, en.csv`. This GDD keeps the existing `names_*` files and adds `ui_*` (decision logged). Godot's CSV translation import expects a `keys,<locale>…` layout. Is a build-time converter or a custom loader used? | ADR (`/architecture-decision`) | Architecture phase |
| OQ-7 | **Fonts.** Which pixel font has full Vietnamese coverage and readable stacked diacritics, and what is the minimum UI size? NOT SOURCEABLE from engine reference. | Art bible / engine spike | Spike (§12.1) |
| OQ-8 | **Vietnamese collation** (R13). Does Godot 4.7 sort `đ` and tone marks correctly, or does the game need its own comparator? NOT SOURCEABLE. | ADR | Architecture phase |
| OQ-9 | **Player-entered text limits** (guild name length, allowed characters, profanity filtering for leaderboards). This is out of scope here; R8 only fixes NFC and verbatim display. | Leaderboards (35) / Guild screens (39) | Alpha |
| OQ-10 | **Calendar dates and times** (absolute timestamps in the Chronicle or offline report). This GDD defines durations only (F6). Are absolute dates needed, and in what format (`16/11/2026` vs `Nov 16, 2026`)? | Guild screens / Chronicle owner | Vertical Slice |
| OQ-11 | **A third locale.** R2 keeps the locale list as data. Adding one is a scope change, not decided here. | User | Post-launch |
| OQ-12 | **Lookup performance budget** in frame time and memory for about 1,200 names × 2 locales. | Architecture | Architecture phase |
