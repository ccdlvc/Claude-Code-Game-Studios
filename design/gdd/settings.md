# Settings

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run, decisions in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: none yet (no `design/gdd/game-pillars.md`). Anchored to locked `JX1_Tycoon_GDD.md` lines §1 ("Ngôn ngữ: Tiếng Việt + Tiếng Anh [CHỐT]"; "cloud save đa nền tảng [CHỐT]"), §8.1 (guest mode, account linking), §11.3 (ad consent UMP/GDPR, ATT on iOS) and §21 Prompt B ("cài đặt (vi/en)").
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief exist to check against. Re-run after pillars exist.

## Summary

Settings is the one screen where the player changes how the game behaves on this device: language, sound volumes, cloud backup and account actions, restoring purchases, and privacy and ad-consent options. It also owns the small device preferences file that holds those choices and the device's `install_id`, kept apart from the guild save so a setting can never change, corrupt or leak into the simulation. Read this GDD before adding any player-adjustable option or any value that must survive restarts but must not be part of the save.

> **Quick reference** — Layer: `Presentation` · Priority: `Vertical Slice` (Language only at VS; Audio, Account & backup, Purchases and Privacy & ads sections appear when systems 40, 7, 34 and 33 land at Alpha; Notifications at Full Vision) · Key deps: `Localization (4)` hard; `Account and cloud save (7)`, `In-app purchases (34)`, `Ads (33, provisional)`, `Audio (40, provisional)` soft (section hosts); `Deterministic RNG (2)` for `install_id` · Feasibility: NOT SOURCEABLE for `Core` (no `docs/engine-reference/godot/modules/core.md`); `modules/audio.md` confirms `AudioServer.set_bus_volume_db` and named buses; `modules/ui.md` confirms AccessKit screen-reader support on `Control` nodes.

## Overview

Settings has two halves. **The preferences store** is a host-level service outside the simulation: one small versioned file in the app's private storage, separate from the save directory, holding the device preferences (locale, volumes, mute, cloud-backup toggle) and the device's `install_id`. It is read once at boot before anything that needs a preference, validated key by key, and written atomically shortly after each change. Nothing in it reaches the simulation, the save, the event bus, RNG keys, the content hash or a leaderboard submission. **The Settings screen** is a list of sections, each contributed by the system that owns the behaviour: Language (Localization), Audio (Audio), Account & backup (Account and cloud save), Purchases (In-app purchases), Privacy & ads (Ads) and later Notifications (Local push notifications). Settings owns the screen, the store and the rule that every change applies immediately; the owning systems own the actions behind the buttons. A section whose owner is not in the build is simply absent, which is how the screen grows from "language only" at Vertical Slice to the full list at Alpha without redesign. Without this system the player could not pick a language (a locked requirement, §1), could not reach account linking or deletion (store-mandated, Cloud save R15), could not restore purchases (IAP R10) and could not revisit ad consent (§11.3).

## Player Fantasy

**Indirect.** Settings is not where the game is played; it is where the player makes the game theirs and then forgets it. The target feeling is *"it did exactly what I touched, instantly, and it remembered."* Three moments carry it:

1. **The wrong-language rescue.** A Vietnamese player's phone is set to English, so the first launch opens in English (Localization R7.1). They find Settings → Language, see `Tiếng Việt` written in Vietnamese, tap it, and the screen they are looking at turns Vietnamese on the next frame. No restart, no confirm, no lost place.
2. **The commute mute.** The player opens the game on a bus, taps Mute all, closes the game. Tomorrow it is still muted, and when they un-mute, every slider is where they left it.
3. **The quiet reassurance.** A player who never signs in sees "Backed up 2 min ago" in Account & backup (Cloud save Player Fantasy) and never thinks about it again.

What the player must never feel: that a setting cost them progress, that the game nagged them from this screen, or that privacy choices were hidden. Settings never rewards, never charges, never interrupts the guild (the simulation keeps running while it is open, as an idle game should).

*Creative-director lens applied in this session (framings considered: "control panel mastery", "invisible comfort", "trust and transparency"); "invisible comfort" chosen with the privacy-transparency line folded in, because it matches the idle genre's low-friction expectation and Cloud save's existing framing.*

## Detailed Design

*Lenses applied (routing: `Persistence` → Foundation/Infrastructure, unioned with `Meta`'s UI-systems row because the system is mostly a screen):*

- **systems-designer** — The store must have explicit states (loaded, recovered from backup, defaulted) and a write path that cannot leave a half-written file. Every key needs a type, a range and an owner. Warned: if `install_id` is wiped by a "reset" it silently changes Cloud save's `device_tag` and RNG's fallback input; it must be protected.
- **gameplay-programmer** — Live apply is cheap only if each owner exposes a setter and Settings never caches derived state. Debounce writes so dragging a slider does not write the file 60 times a second. Settings must not need the Data layer to boot, because Localization needs the locale before `i18n/` loads.
- **engine-programmer** — Keep the store out of the save directory so Local save's candidate scan (R12) and its "never delete" rule (R15) never see it. Use the same tmp-then-rename pattern as Local save R10; Godot's `ConfigFile` is adequate, but the format choice is an implementation decision → becomes an ADR.
- **ux-designer** — No Apply button; immediate effect with visible state. Language rows labelled in their own language. Destructive actions (delete account) are visually separated and confirm. Every toggle shows its state as text or icon, never colour alone. Sliders must be operable by screen reader and by keyboard on PC.
- **ui-programmer** — Sections should be data-bound to their owner's state (Cloud save's four sync states, Ads' "privacy options required" flag) and re-render on change; Vietnamese strings run ~30% longer than English, so section labels need wrap room (Localization F4).

No disagreement between roles needed a decision. One tension was resolved by the recommended option and logged: whether preferences should sync through the cloud (Localization OQ-3). Chosen: **device-only** (R2), because syncing would add fields to the cloud record, a schema change this GDD may not make; recorded as OQ-1.

### Core Rules

**R1 — Outside the simulation.** Settings is a host-level service. It holds no simulation state, registers no save section (Local save R6), submits no commands (Command layer), emits nothing on the sim event bus, and is never an input to RNG keys (RNG "keys never contain player-mutable state"), the content hash, or a leaderboard submission. Opening, using or closing Settings does **not** pause the simulation core; this answers Sim core OQ-7 for Settings: Settings needs no `pause()`.

**R2 — One preferences store, device-local.** All preferences live in one file, `settings.cfg`, in the app's private storage **outside** the save directory (Local save R1). It is never uploaded, never part of the cloud blob (Cloud save R17), and never copied by Local save's backup rotation. A new device starts from defaults (R4), except that Localization R7.1 picks the first locale from the OS language. Cross-device sync is not designed (OQ-1).

**R3 — Keys.** The store holds exactly these keys at `settings_version = 1`. Each key has one owner who defines its meaning; Settings owns storage, validation and the screen control.

| Key | Type | Valid values | Default | Meaning owned by |
|---|---|---|---|---|
| `settings_version` | int | ≥ 1 | 1 | Settings |
| `install_id` | uint64, stored as 16 lowercase hex chars | any non-zero | created at first launch (R5) | Deterministic RNG (R2); read by Cloud save for `device_tag` |
| `locale` | string | a shipped locale code (`vi`, `en`); `qps` in dev builds only | absent → Localization R7.1 | Localization (R7) |
| `vol_master` | int | 0–100, multiple of `volume_slider_step` | `settings_default_vol_master` | Audio (provisional) |
| `vol_music` | int | 0–100, as above | `settings_default_vol_music` | Audio (provisional) |
| `vol_sfx` | int | 0–100, as above | `settings_default_vol_sfx` | Audio (provisional) |
| `vol_ui` | int | 0–100, as above | `settings_default_vol_ui` | Audio (provisional) |
| `mute_all` | bool | true/false | false | Audio (provisional) |
| `cloud_backup_enabled` | bool | true/false | true | Account and cloud save (R16) |
| `a11y_reduced_motion` | bool | true/false | false | Settings (R12a); consumed by Guild screens (39) and Realtime world view |
| `a11y_text_scale` | int (percent) | one of `a11y_text_scale_options` | `a11y_text_scale_default` | Settings (R12a); consumed by Guild screens (39) and Realtime world view |
| `a11y_element_palette` | string | `standard`, `colorblind` | `standard` | Settings (R12a); palette values owned by the art bible; consumed by Guild screens (39) and Realtime world view |

Adding a key is a change to this table (a new `settings_version` only when an existing key changes meaning or type, R6). Ad consent is **not** stored here: the consent platform SDK (UMP on Android/iOS) keeps its own record in platform storage, owned by Ads (33). Notification preferences (master toggle, one toggle per kind, quiet hours on/off with start and end, the permission-ask state) are defined by Local push notifications R12 as device-local Settings preferences; their keys, types and defaults are owned by that GDD and are added to this table when 46 is built (OQ-5).

**R4 — Defaults are data.** The four default volumes, the slider step and the audio taper (F1) are read from `data/config.csv` keys `settings_*` (proposed, OQ-2). A preference that is absent from the store resolves to its default **at first read**, not at boot, so the store can be loaded before the Data layer is `Ready`. The only preferences read before the Data layer is ready are `locale` (whose default is the OS rule, not data) and `install_id` (no default; created). A resolved default is not written back to the store until the player changes that preference, so a later change to a default in `config.csv` reaches every player who never touched it.

**R5 — Boot order.** At app start the host loads the store **first**, before Localization leaves `Boot` (Localization needs `locale`) and before any new guild is created (RNG needs `install_id`):
1. Load `settings.cfg` (R7). If unreadable, try `settings.bak`; if both fail, start from an empty store (`Defaulted`).
2. If `install_id` is absent or zero, create one from platform entropy, store it, and write the store immediately (no debounce). This is the only write Settings performs without a player action.
3. Hand `locale` (or "absent") to Localization; Localization resolves R7.1 itself.
4. Later, when Audio (40) starts, it reads the volume keys through Settings and applies F1.

**R6 — Versioning.** `settings_version` names the store's format. A newer build that changes a key's meaning increments it and migrates on load (old value → new value, one step per version, same discipline as Local save R14). An older build that reads a store with a **higher** version than it knows reads the keys it recognises, keeps every unknown key and the higher version number unchanged on write, and never migrates down. Unknown keys are always preserved on write.

**R7 — Validation on read.** Each key is validated against R3 when loaded:
- Wrong type, unparseable, or a value outside its valid set → treated as absent (default applies); a warning is logged; the bad value is dropped on the next write.
- A volume that is in 0–100 but not a multiple of `volume_slider_step` → rounded to the nearest step (half rounds up). A volume outside 0–100 → clamped.
- `locale` not shipped in this build (including `qps` in a release build) → treated as absent, so Localization R7.1 runs again.
Validation never blocks boot and never shows an error to the player.

**R8 — Live apply, no Apply button.** Every control takes effect immediately: it calls the owner's setter (`set_locale`, Audio's bus gain, Cloud save's toggle) on the same frame as the input, and the owner's change is visible by the next frame. There is no Apply, OK or Cancel on the screen. The store is marked dirty and written per F2.

**R9 — Atomic write.** A store write (a) serialises all keys, sorted, to `settings.tmp`, flushes and closes it; (b) reads it back and parses it; on mismatch, deletes it and fails; (c) renames the current `settings.cfg` to `settings.bak` (replacing the old backup); (d) renames `settings.tmp` to `settings.cfg`. A failed write keeps the store dirty and is retried at the next F2 trigger; the player is never shown a write error (preferences are not progress). This mirrors Local save R10 at a smaller scale.

**R10 — Sections.** The screen is an ordered list of sections. At host startup each owning service that is present in the build registers its section with Settings; Settings never imports a feature. Fixed order, by importance to a player in trouble:

| # | Section | Registered by | From tier | Contents |
|---|---|---|---|---|
| 1 | Language | Localization (4) | Vertical Slice | One row per shipped locale, labelled in its own language (Localization UI Requirements) |
| 1a | Accessibility | Settings (45) itself | Vertical Slice | Reduced motion toggle; Text size choice; Colour-blind-safe element palette toggle (R12a; user decision 2026-11-16) |
| 2 | Audio | Audio (40) | Alpha | Mute all toggle; Master, Music, Sound effects, Interface sliders |
| 3 | Account & backup | Account and cloud save (7) | Alpha | Everything listed in Cloud save UI Requirements (account state, link, sign out, delete, backup toggle, Back up now, Restore previous cloud backup, last backup time, conflict banner) |
| 4 | Purchases | In-app purchases (34) | Alpha | Restore purchases; Purchase history; link to shop |
| 5 | Privacy & ads | Ads (33) | Alpha | Privacy policy link; Privacy options (consent form) when required; ATT status on iOS |
| 6 | Notifications | Local push notifications (46) | Full Vision | Master toggle; per-kind toggles; quiet hours toggle and start/end pickers; OS permission status line and "Open system settings" when denied or revoked (Local push notifications R12, UI Requirements) |

A section is shown only if its owner registered it **and** the owner reports it applicable on this platform (for example, Privacy & ads registers nothing on Steam builds if Ads is absent there, R13). A section with no visible rows is hidden, never shown empty. At Vertical Slice the screen therefore shows Language and Accessibility only.

**R11 — Language section.** Selecting a locale row calls `set_locale(L)` and stores `locale = L` (Localization R7.2, R7.3). Re-selecting the current locale does nothing. The current locale is marked by a check icon plus `accessibility` text, not colour alone.

**R12 — Audio section.** (PROVISIONAL until Audio (40) exists.)
1. Four sliders: Master, Music, Sound effects, Interface. Range 0–100 in steps of `volume_slider_step`, shown as a number next to the slider.
2. **Mute all** toggle sets `mute_all`. While on, all output is silent (F1) and each slider keeps its stored value; the sliders stay operable and their values are kept, and a "Muted" label shows beside the section title. Turning Mute all off restores every channel to its slider value.
3. Moving a slider changes the gain live during the drag. Releasing the Sound effects or Interface slider plays one preview cue on that channel (the cue is Audio's choice), unless `mute_all` is on.
4. Settings stores only the slider integers and `mute_all`; converting them to bus gain is F1, applied by Audio.

**R12a — Accessibility section (user decision 2026-11-16, OQ-8).** Settings owns the meaning of these three keys; the screens that render the game read them through Settings and apply them live (R8).
1. **Reduced motion** (`a11y_reduced_motion`). When on: screen transitions are instant (Guild screens Game Feel: 0 ms), and Realtime world view turns off camera shake and hit-stop and replaces location cuts with a fade. It never changes what is shown, only how it moves.
2. **Text size** (`a11y_text_scale`). A choice among `a11y_text_scale_options` (default 100, 125, 150 %), shown as labelled buttons with a live sample line. Applied as a theme font-size multiplier to every UI text; every screen must lay out without clipping at the largest option (Guild screens R16, AC-18). World-view floating text (names, damage numbers) scales with it up to the view's own legibility limit.
3. **Colour-blind-safe element palette** (`a11y_element_palette`). `colorblind` swaps the five element colours (Kim, Mộc, Thủy, Hỏa, Thổ) for a palette distinguishable under protanopia, deuteranopia and tritanopia (values owned by the art bible). **Non-colour element icons are always on**, whichever palette is chosen: every element shown anywhere carries its glyph and name (Guild screens R16, Realtime world view R15), so the palette is an aid, never the only cue.
4. All three are host-level presentation only (R1, R15): they never reach the sim, a save, an RNG key or a leaderboard.

**R13 — Privacy & ads section.** (PROVISIONAL until Ads (33) exists.)
1. **Privacy policy** — a link that opens the published privacy policy in the system browser. Shown on every build that has Ads or Account and cloud save (both send data off the device).
2. **Privacy options** — reopens the consent platform's form. Shown **only when Ads reports that a privacy-options entry point is required** for this user (the UMP SDK exposes this). Settings does not decide when consent is required, does not store the choice, and does not change ad behaviour itself; Ads re-reads consent after the form closes.
3. **iOS tracking (ATT)** — a read-only line showing the current App Tracking Transparency status ("Allowed" / "Not allowed" / "Not asked"), with a button that opens the OS settings page for this app. Settings never triggers the ATT prompt (the OS allows it once; Ads owns when).
4. On Premium and on Steam, Ads may report consent not required; then row 2 is hidden. Row 1 stays if Cloud save is present.

**R14 — Account & backup and Purchases sections.** Settings renders the state each owner publishes and calls the owner's action when a row is tapped. Settings stores only `cloud_backup_enabled`. Every confirmation dialog, result toast and error text for these actions belongs to the owning system (Cloud save R13, R15, R16; IAP R10). Destructive rows (Sign out, Delete account and cloud backup) sit at the bottom of their section, separated by a divider, and always confirm through the owner's dialog.

**R15 — Settings never affects progress.** No setting grants or costs gold, items, XP or quest progress; no setting changes simulation behaviour or balance. A future option that would (for example a gameplay speed or an "auto-sell" preference) belongs in the save as a guild command, not in this store.

**R16 — Where Settings is reached.** From a gear button on the guild screen (Guild screens 39) and from the data-damaged / boot-failure screens' "Language" link (so a player stuck in the wrong language on a failure screen can switch: Localization R11 core string set). Closing Settings returns to the screen that opened it and triggers a store flush (F2).

### States and Transitions

**Store state**

| State | Meaning | Enters from | Exits to |
|---|---|---|---|
| `Unloaded` | App start, nothing read | app start | `Loaded`, `Recovered`, `Defaulted` |
| `Loaded` | `settings.cfg` parsed (individual keys may still have been rejected by R7) | `Unloaded` | `Clean` |
| `Recovered` | `settings.cfg` unreadable; `settings.bak` used | `Unloaded` | `Dirty` (writes the recovered values back so `.cfg` is healthy again) |
| `Defaulted` | Both files unreadable or absent (first launch included) | `Unloaded` | `Dirty` (R5.2 writes at once because `install_id` was created) |
| `Clean` | Store on disk matches memory | `Loaded`, `Writing` (success) | `Dirty` on any change |
| `Dirty` | A change is waiting to be written | `Clean`, `Recovered`, `Defaulted`, `Writing` (failure) | `Writing` when F2 fires |
| `Writing` | R9 in progress | `Dirty` | `Clean` (success), `Dirty` (failure; retry at next trigger) |

A change made while `Writing` marks the store dirty again; the in-flight write completes and a second write follows at the next F2 trigger.

**Screen state:** `Closed` → `Open` (from R16 entry points) → `Closed`. While open, each section re-renders when its owner's state changes (for example Cloud save moving from *backing up* to *backed up*). There is no modal state of Settings itself; owner dialogs are the owner's.

### Interactions with Other Systems

| System | Direction | Data / call | Owner of interface |
|---|---|---|---|
| Localization (4) | Settings ↔ Localization | Settings hands the stored `locale` (or absent) at boot; Language section calls `set_locale(L)`; Settings stores `L` | Localization owns locale behaviour (R7); Settings owns storage and the control |
| Deterministic RNG (2) | Settings → RNG (via host) | `install_id` for `new_world_seed(entropy_fn, clock_fn, install_id)` | RNG owns meaning (R2); Settings owns creation and storage |
| Account and cloud save (7) | both | Settings reads `install_id` for `device_tag`; stores `cloud_backup_enabled` and passes changes to Cloud save; hosts the Account & backup section; Cloud save publishes account and sync state | Cloud save owns all actions and state; Settings owns the screen |
| In-app purchases (34) | IAP → Settings | Registers Purchases section; Restore purchases action, purchase history list | IAP owns actions; Settings owns the screen |
| Ads (33) | Ads → Settings | Registers Privacy & ads section; `privacy_options_required: bool`; `open_privacy_options()`; ATT status | Ads (PROVISIONAL, no GDD) |
| Audio (40) | Audio ← Settings | Reads `vol_*`, `mute_all`; applies F1 to buses; supplies preview cue | Audio (PROVISIONAL, no GDD) |
| Local push notifications (46) | both | Notifications section; device-local preference keys and permission state stored here (46 R12); Settings never schedules anything | Local push notifications owns meaning and rows; Settings owns storage and the screen |
| Guild screens (39) | both | Gear button opens Settings; Guild screens reads `a11y_text_scale`, `a11y_element_palette`, `a11y_reduced_motion` (R12a) | Guild screens owns rendering; Settings owns the keys |
| Realtime world view | view ← Settings | Reads `a11y_reduced_motion`, `a11y_text_scale`, `a11y_element_palette` (R12a) | View owns rendering; Settings owns the keys |
| Sim core (1) | none | Settings never calls `pause()` or `submit()` (R1) | — |
| Local save (6) | none | The store is outside the save directory and save payload (R2) | — |
| Analytics (37) | Analytics ← Settings (read) | May read the active locale and whether sound is muted as session dimensions; no setting-change events on the sim bus | Analytics (PROVISIONAL) |

## Formulas

*Systems-designer lens applied: each formula below was worked at its minimum, maximum and zero inputs.*

### F1 — Channel gain

The `channel_gain_db` formula is defined as:

`channel_gain_db(v, mute) = −∞ (silent)  if mute or v = 0 or 20·k·log10(v / 100) < volume_floor_db`
`channel_gain_db(v, mute) = 20 · k · log10(v / 100)  otherwise`

and is applied separately to the Master bus (`v = vol_master`) and to each channel bus (`v = vol_music`, `vol_sfx`, `vol_ui`), so the heard level of a channel is the sum of its bus gain and the Master gain. `mute = mute_all` for the Master bus and `false` for channel buses (muting Master silences everything).

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `v` | int | 0–100 | settings store (`vol_*`) | Slider value |
| `mute` | bool | — | settings store (`mute_all`) | Silences Master |
| `k` | float | 1.0–3.0 | data file (`volume_taper_exp`, default 2.0) | Taper exponent: amplitude = (v/100)^k. k = 1 is a linear-amplitude slider (top 80% of the travel sounds almost the same); k = 2 approximates perceived loudness |
| `volume_floor_db` | float | −80 to −40 | data file (default −60) | Below this the channel is muted rather than barely audible |

**Output Range:** 0 dB at `v = 100` (never above unity, so a slider cannot clip the mix); falls to `volume_floor_db` and then silence. With k = 2 and floor −60 dB, any `v` below 3.2 is silent — with the default step of 5 the lowest audible step is 5 (−52.0 dB). At `v = 0` the log is undefined; the first branch handles it, so the formula never evaluates `log10(0)`.

**Example:** `vol_master = 80`, `vol_sfx = 50`, k = 2: Master = 40·log10(0.8) = −3.88 dB; SFX bus = 40·log10(0.5) = −12.04 dB; heard SFX ≈ −15.9 dB relative to full scale of the authored mix. With `mute_all = true`, everything is silent and the stored 80 and 50 are unchanged.

### F2 — Store write timing

The `settings_write_at` formula is defined as:

`settings_write_at = min(t_last_change + settings_write_debounce_ms, t_flush_event)`

where `t_flush_event` is the first of: app moved to background or quit, Settings screen closed, `install_id` created (R5.2, immediate). A write only happens when the store is `Dirty`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `t_last_change` | ms (monotonic) | ≥ 0 | calculated | Time of the most recent preference change; each change restarts the debounce |
| `settings_write_debounce_ms` | int | 250–5000 | data file (default 1000) | Quiet time before writing |
| `t_flush_event` | ms (monotonic) or none | ≥ 0 | calculated | First flush trigger, if any |

**Output Range:** a write at most once per debounce window while a slider is dragged continuously (dragging restarts the timer, so a 10-second drag produces one write 1 s after release, or at once if the screen is closed first). With debounce 0 (outside the safe range) every drag frame would write; the 250 ms floor prevents this.

**Example:** the player drags Music from 70 to 40 over 2 s, releasing at t = 5000 ms, then closes Settings at t = 5400 ms. `settings_write_at = min(5000 + 1000, 5400) = 5400`: one write, on close.

No other numeric rule is defined here: the cloud, purchase and consent numbers belong to their owners.

## Edge Cases

*Systems-designer lens applied to C and D; findings added below.*

- **If `settings.cfg` is unreadable but `settings.bak` parses**: use the backup (`Recovered`), then write it back as `settings.cfg`. At most one debounce window of changes is lost.
- **If both files are unreadable or missing on an install that already has a save**: start `Defaulted`, create a new `install_id`. The guild save is untouched (R2). Consequences, all accepted: Localization re-runs R7.1, volumes return to defaults, Cloud save's `device_tag` for this device changes (a conflict screen would show the new tag; Cloud save R6 detects conflicts by revision, not tag, so no data is at risk), and `cloud_backup_enabled` returns to true (a player who had turned backup off finds it on again; flagged in OQ-4).
- **If `install_id` is present but zero or not 16 hex characters**: treat as absent and create a new one (R5.2).
- **If platform entropy is unavailable when `install_id` must be created**: Settings stores no `install_id` and retries at next launch. RNG R9 already refuses to seed a new guild from the clock alone when `install_id` is missing, so new-guild creation shows its error; existing guilds play normally.
- **If the store write fails (disk full, permission)**: store stays `Dirty`; retried at the next trigger; no message to the player; preferences remain in effect for this session.
- **If the stored `locale` is a code this build does not ship** (a newer build added a language, then the player downgraded; or `qps` reached a release build): treat as absent, run Localization R7.1, and keep the unknown value on disk only until the player picks a language.
- **If `settings_version` on disk is higher than this build knows**: read known keys, preserve unknown keys and the version number on write (R6). No migration runs.
- **If two app instances run at once on desktop and both write**: last write wins. Accepted, because no preference is progress; Local save R10 already guards the save itself against a second writer.
- **If the player moves a volume slider while Mute all is on**: the value is stored and shown, nothing is heard, no preview cue plays (R12.3); the "Muted" label stays visible so the silence is explained.
- **If all four volumes are 0 and Mute all is off**: silent, as chosen. No warning (the player set it).
- **If Audio (40) is not in the build (Vertical Slice)**: the Audio section is hidden; stored volume keys, if any, are kept untouched on write.
- **If the player switches language while an owner dialog from Settings is open** (for example the delete-account confirmation): the switch cannot happen, because the dialog is modal over the Language section. If a locale change arrives by another path, Localization R7.3 re-renders the dialog text.
- **If Ads' "privacy options required" flag changes while Settings is open** (consent SDK finishes its update): the Privacy & ads section re-renders and the row appears or disappears.
- **If the player turns Cloud backup off and back on within one debounce window**: Cloud save receives both changes in order (R8 applies each immediately); the store writes once with the final value.
- **If the device has no network**: every section still opens. Network actions are disabled or report their own offline state (owners' rules); Language and Audio work fully offline.
- **If the player opens Settings from a boot-failure screen** (R16) before the Data layer is `Ready`: only the Language section is shown, using the compiled core string set (Localization R11). Volume defaults (which need data) are not resolved.
- **If `a11y_text_scale` is stored but no longer in `a11y_text_scale_options`** (data changed the list): R7 treats it as absent and the default applies.
- **If the art bible's colour-blind palette is not delivered yet**: the toggle is hidden (a row with nothing to apply is not shown); element icons stay on regardless.
- **Degenerate strategy check:** no setting changes simulation outcome, RNG keys or rewards (R1, R15), so no setting can be used to re-roll or gain progress. Changing language does not change any event's dice (RNG keys never contain settings).

## Dependencies

| System | Direction | Hard/Soft | Interface | Status |
|---|---|---|---|---|
| Localization (4) | upstream | Hard | `set_locale(L)`; R7.1 first-launch rule; core string set for the boot-failure entry; text lookup for every label | Designed (`localization.md`) |
| Deterministic RNG (2) | downstream consumer of `install_id` | Hard (for new-guild creation) | `install_id: uint64 \| None`, kept in platform settings (RNG R2) — this GDD defines that "platform settings" is this store | Needs Revision (`deterministic-rng.md`) |
| Account and cloud save (7) | section host + key storage | Soft (section absent until Alpha) | Account & backup section contents; `cloud_backup_enabled`; reads `install_id` for `device_tag` | Designed (`account-and-cloud-save.md`) |
| In-app purchases (34) | section host | Soft | Purchases section: Restore purchases, purchase history | Designed (`in-app-purchases.md`) |
| Ads (33) | section host | Soft | `privacy_options_required`, `open_privacy_options()`, ATT status, privacy-policy URL | Not Started — PROVISIONAL |
| Audio (40) | consumer of volume keys | Soft | Reads `vol_*`, `mute_all`; applies F1; preview cue | Not Started — PROVISIONAL |
| Local push notifications (46) | section host + key storage | Soft | Notifications section and preference keys (46 R12) | Designed in parallel (`local-push-notifications.md`) |
| Data layer (3) | upstream | Soft | `settings_*` keys in `config.csv` for defaults and F1/F2 knobs (proposed, OQ-2) | Designed |
| Guild screens (39) | caller + consumer | Soft | Gear button entry point; consumes text size, element palette and reduced motion (R12a) | Designed (`guild-screens.md`) |
| Realtime world view | consumer | Soft | Consumes reduced motion, text size and element palette (R12a) | Designed (`realtime-world-view.md`) |
| Sim core (1), Local save (6) | none (isolation) | — | Explicitly no interface (R1, R2) | Designed |

**Bidirectional check.** Localization, Cloud save and IAP already list Settings (45) as a downstream dependent. RNG R2 says `install_id` lives in "platform settings" without naming an owner; this GDD claims it, and RNG should cite Settings in its next revision (OQ-3). Local save's "does not own" paragraph already names Settings for language, consent and `install_id`. The systems index row lists Localization, Account and cloud save, Ads, Audio; this GDD adds Deterministic RNG and In-app purchases (row updated).

## Tuning Knobs

All proposed as `data/config.csv` keys (OQ-2). Safe ranges are where the screen still behaves as designed.

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `settings_default_vol_master` | 80 | 50–100 | First launch loud in public; no headroom to turn up | First launch sounds broken (player thinks there is no audio) | Must be a multiple of `volume_slider_step` |
| `settings_default_vol_music` | 70 | 30–100 | Music masks UI feedback | Music unnoticed | Audio's mix (40) |
| `settings_default_vol_sfx` | 80 | 30–100 | Combat noise fatigue in an idle game | Hits unreadable by ear | Audio's mix |
| `settings_default_vol_ui` | 80 | 30–100 | Taps feel loud | Taps feel dead | Audio's mix |
| `volume_slider_step` | 5 | 1–10 | Coarse control near the quiet end | Fiddly on touch, more writes while dragging (F2 absorbs it) | Defaults must be multiples; with k = 2 and floor −60 dB, steps below 4 add silent positions |
| `volume_taper_exp` (k) | 2.0 | 1.0–3.0 | Most of the slider is quiet | Top of slider all sounds the same | `volume_floor_db` (raising k moves the silent zone up the slider) |
| `volume_floor_db` | −60 | −80 to −40 | Low steps become silent | Barely audible hiss-level steps | `volume_taper_exp` |
| `settings_write_debounce_ms` | 1000 | 250–5000 | More changes lost on a crash (never progress) | More disk writes while dragging | — |
| `a11y_text_scale_options` | 100;125;150 | 100–200, ascending, first = 100 | Layouts at the top option clip (Guild screens AC-18) | Low-vision players get too little gain | Guild screens `ui_touch_min_px`; art bible pixel font sizes |
| `a11y_text_scale_default` | 100 | one of the options | — | — | `a11y_text_scale_options` |

## Visual/Audio Requirements

Not required for the `Persistence` category; brief notes. No art bible exists yet (`design/art/art-bible.md` absent), so these follow the project's pixel-2D style and should be checked when it lands.
- Standard UI kit controls (rows, toggles, sliders, section headers); no bespoke VFX.
- Each toggle shows state with an icon or text label plus colour, never colour alone.
- Audio: tapping a row uses the standard UI tap cue on the Interface channel; slider release plays a preview (R12.3). Settings defines no unique sounds.

## Game Feel

Optional for this category; one target: **every input visibly or audibly answers on the next frame** (R8). Slider drag changes volume continuously during the drag, not on release. No transition animation longer than the project's standard screen transition.

## UI Requirements

- **Settings screen** (owned here): full-screen on mobile, a panel on PC. Title; sections per R10 in fixed order, each with a header; scrolls vertically; safe-area aware; leaves room for the Free build's bottom banner (§11.3) — the banner's height is Ads' to publish.
- **Language section**: rows labelled in their own language, never translated; check icon on the current one (Localization UI Requirements).
- **Audio section**: Mute all toggle at top; four labelled sliders with numeric value; "Muted" label when on.
- **Accessibility section** (R12a): Reduced motion toggle; Text size as labelled option buttons with a sample line that re-renders live; Element palette toggle with a preview strip of the five element icons in the chosen palette (icon + name + colour).
- **Account & backup, Purchases, Privacy & ads**: layouts per their owners' UI requirements; Settings provides the section container, the divider before destructive rows, and re-render on owner state change.
- **Accessibility floor**: every control reachable and operable with a screen reader (Godot 4.5+ AccessKit on `Control` nodes, `modules/ui.md`) and, on PC, keyboard/controller focus; sliders adjust by one step per arrow key; labels wrap (Vietnamese can run ~30% longer, Localization F4); touch targets at least the project's minimum size (to be set by `/ux-design`).
- **Entry points**: gear button on the guild screen; "Language" link on boot-failure screens (R16).

> **📌 UX Flag — Settings**: This system has UI requirements. In Pre-Production, run `/ux-design` for the Settings screen (all sections, `vi`/`en`/`qps` states, Free-build banner) before writing epics; stories should cite `design/ux/settings.md`.

## Cross-References

| This GDD | References | Fact relied on |
|---|---|---|
| R2, R11, R16 | `localization.md` R7, R11, UI Requirements | Locale chosen in Settings, stored as a device preference outside the sim save; live switch; core string set on failure screens |
| R3, R5 | `deterministic-rng.md` R2, R9 | `install_id` is a 64-bit random value created at first launch and kept in platform settings; no clock-only seed |
| R1 | `sim-core-and-tick-loop.md` OQ-7 | Settings does not request `pause()` |
| R2, R9 | `local-save-and-migration.md` R1, R10, R12, R15, "does not own" | Separate directory; tmp-then-rename write pattern; settings live in platform settings |
| R3, R10, R14 | `account-and-cloud-save.md` R6, R13, R15, R16, R17, UI Requirements | Toggle default On; account actions and dialogs owned by Cloud save; `device_tag` from `install_id` |
| R10, R14 | `in-app-purchases.md` R10, UI Requirements | Restore purchases and purchase history hosted in Settings |
| R13 | `JX1_Tycoon_GDD.md` §11.3 | UMP/GDPR consent and ATT on iOS |
| F1 | `docs/engine-reference/godot/modules/audio.md` | `AudioServer.set_bus_volume_db`, named buses |

## Acceptance Criteria

*QA lens applied: one or more criteria per core rule and formula; boundary values included; story type marked [Logic] (automated unit test), [Integration], or [UI] (retained screenshot).*

- **AC-1 [Logic] (R2, R1)** — **GIVEN** a fresh install with a guild saved, **WHEN** the player changes locale and every volume, **THEN** the save files in the save directory are byte-identical to before, `settings.cfg` exists outside that directory, and the next autosave's payload contains none of the R3 keys.
- **AC-2 [Logic] (R5)** — **GIVEN** no `settings.cfg` or `.bak`, **WHEN** the app boots, **THEN** a non-zero 16-hex-char `install_id` is written to `settings.cfg` before any new guild is created, and a second boot reads the same value.
- **AC-3 [Logic] (R7)** — **GIVEN** a store with `vol_music = "abc"`, `vol_sfx = 150`, `vol_ui = 52`, `locale = "fr"`, **WHEN** loaded with step 5, **THEN** `vol_music` resolves to its default, `vol_sfx = 100`, `vol_ui = 50`, and Localization receives "absent" for locale; boot completes with no player-visible error.
- **AC-4 [Logic] (R6)** — **GIVEN** a store with `settings_version = 2` and an unknown key `foo = 1`, **WHEN** a version-1 build changes `vol_master` and writes, **THEN** the written file still has `settings_version = 2` and `foo = 1`.
- **AC-5 [Logic] (R4)** — **GIVEN** a store with no `vol_music` and `settings_default_vol_music = 70`, **WHEN** Audio reads it, **THEN** it gets 70 and the store is not written; **WHEN** `config.csv` changes the default to 60 and the app restarts, **THEN** Audio gets 60.
- **AC-6 [Logic] (R9)** — **GIVEN** a write that fails after step (a) (simulated I/O error at rename), **WHEN** the app restarts, **THEN** the previous `settings.cfg` or `settings.bak` loads and no key holds a partial value.
- **AC-7 [Logic] (store states)** — **GIVEN** an unparseable `settings.cfg` and a valid `settings.bak`, **WHEN** booted, **THEN** state passes `Recovered` → `Dirty` → `Clean` and `settings.cfg` afterwards parses with the backup's values.
- **AC-8 [Logic] (F1)** — with k = 2, floor −60: `v = 100` → 0.00 dB; `v = 50` → −12.04 dB (±0.01); `v = 5` → −52.04 dB; `v = 3` → silent; `v = 0` → silent with no `log10(0)` evaluated; `mute_all = true` with `vol_master = 80` → Master silent and stored value still 80.
- **AC-9 [Logic] (F2)** — **GIVEN** debounce 1000 ms, **WHEN** changes arrive at t = 0, 400 and 900 ms and nothing else happens, **THEN** exactly one write occurs at t = 1900 ms; **WHEN** instead the screen is closed at t = 950 ms, **THEN** exactly one write occurs at 950 ms.
- **AC-10 [Integration] (R8, R11)** — **GIVEN** the guild screen behind Settings in `en`, **WHEN** the player taps `Tiếng Việt`, **THEN** the next frame shows Settings in Vietnamese with no restart, and after a cold restart the game opens in Vietnamese.
- **AC-11 [Integration] (R12)** — **GIVEN** Audio present, **WHEN** the player turns Mute all on, closes and relaunches the app, **THEN** the game is silent, each slider shows its previous value, and turning Mute all off restores audible output at those values.
- **AC-12 [Integration] (R10)** — **GIVEN** a Vertical Slice build (only Localization and Settings' own Accessibility section register), **WHEN** Settings opens, **THEN** only the Language and Accessibility sections are shown and no empty section headers appear; **GIVEN** an Alpha build with all owners, **THEN** sections appear in the R10 order.
- **AC-13 [Integration] (R13)** — **GIVEN** a consent-SDK test configuration that marks privacy options required, **WHEN** Settings opens, **THEN** the Privacy options row is shown and tapping it opens the consent form; **GIVEN** not required, **THEN** the row is absent and the Privacy policy link remains.
- **AC-14 [Integration] (R14)** — **GIVEN** a signed-in account, **WHEN** the player toggles Cloud backup off, **THEN** Cloud save enters `Disabled` on that frame and `cloud_backup_enabled = false` is on disk after F2; Settings itself shows no dialog of its own.
- **AC-15 [Integration] (R1)** — **GIVEN** a running guild, **WHEN** Settings is open for 60 s, **THEN** the sim tick counter advances by 600 (±1) at 10 Hz, i.e. the core was not paused.
- **AC-16 [Logic] (R15, Edge: degenerate)** — **GIVEN** two runs from the same save and seed, one with locale `vi` and volumes at defaults, one with `en` and all volumes 0, **WHEN** both simulate 10,000 ticks, **THEN** the resulting sim state hashes are identical.
- **AC-17 [Integration] (R16, Edge)** — **GIVEN** the Data layer forced into `Failed`, **WHEN** the player taps Language on the failure screen, **THEN** Settings opens with only the Language section and a locale switch re-renders the failure screen.
- **AC-18 [UI]** — Retained screenshots in `production/qa/evidence/` of the Settings screen in `vi`, `en` and `qps`: Vertical Slice (Language and Accessibility), Alpha Free build (all sections with banner space), Alpha Steam build (no Privacy options row), Audio section with Mute all on.
- **AC-20 [Integration] (R12a reduced motion)** — **GIVEN** reduced motion on, **WHEN** the player opens a detail screen and a party member dies in the world view, **THEN** the screen transition takes 0 ms and no camera shake or hit-stop occurs; turning it off restores both on the next frame.
- **AC-21 [UI] (R12a text size)** — **GIVEN** each `a11y_text_scale_options` value, **WHEN** the Settings screen and the guild screens G2–G13 are shown in `vi`, **THEN** retained screenshots show all text at that scale with no clipping (shared with Guild screens AC-18).
- **AC-22 [UI] (R12a palette)** — **GIVEN** `a11y_element_palette = colorblind`, **WHEN** a member list and the world view are shown, **THEN** a retained screenshot shows the swapped element colours with every element still carrying its icon and name; a greyscale capture of the `standard` palette still identifies every element.
- **AC-23 [Logic] (R12a, R7)** — **GIVEN** `a11y_text_scale = 175` with options 100;125;150, **WHEN** loaded, **THEN** it resolves to 100 and boot shows no error; **GIVEN** two runs differing only in the three a11y keys, **THEN** the sim state hashes after 10,000 ticks are identical.
- **AC-19 [UI] (accessibility)** — **GIVEN** a screen reader enabled on Android, **WHEN** the tester navigates Settings, **THEN** every row and slider is announced with its label and state, and each slider changes by one step per adjust gesture.

Gaps the QA lens found and accepted: ATT status (R13.3) can only be verified on iOS hardware, deferred to iOS bring-up; Audio and Ads criteria (AC-11, AC-13) are provisional until those GDDs fix their interfaces.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | Should any preference (locale at least) sync through Account and cloud save so a new device opens in the player's language? Would add fields to the cloud record (a schema change, not made here). Answers Localization OQ-3 as "device-only for now". | Settings + Account and cloud save | Before Alpha |
| OQ-2 | Add the `settings_*` keys (R4, Tuning Knobs) to `data/config.csv`, or keep host-service knobs in a separate services config? Same question as Cloud save OQ-8. | Data layer owner | Before implementation |
| OQ-3 | RNG R2 says `install_id` is "kept in platform settings" without naming an owner; this GDD claims it (R3, R5). RNG's next revision should cite Settings. | Deterministic RNG | Next RNG revision |
| OQ-4 | When the store is lost (both files damaged), `cloud_backup_enabled` returns to its default On. Should Cloud save keep its own copy of the toggle in `sync_meta` so an Off choice survives? | Account and cloud save | Before Alpha |
| OQ-5 | Local push notifications (46) R12 defines its preferences as device-local Settings keys (conformed here). Exact key names, types and defaults still need adding to the R3 table; 46 lists Settings as PROVISIONAL and should cite this GDD. | Local push notifications + Settings | When 46 is built |
| OQ-6 | PROVISIONAL: Ads (33) — assumes it exposes `privacy_options_required`, `open_privacy_options()`, ATT status, the privacy-policy URL and the banner height, owns the consent record, and decides when the ATT prompt appears. | Ads | When 33 is designed |
| OQ-7 | PROVISIONAL: Audio (40) — assumes buses Master, Music, SFX, UI, applies F1 from the stored integers, and supplies preview cues. A Voice bus is not planned. | Audio | When 40 is designed |
| OQ-8 | **RESOLVED (user decision 2026-11-16) for accessibility:** full accessibility ships in Settings — reduced motion, text size and a colour-blind-safe five-element palette, with non-colour element icons always on (R3 keys, R10 section 1a, R12a, AC-20–AC-23). Guild screens (39) and Realtime world view consume them. **Still open (scope):** an About row (build version, licences, AI-asset disclosures per §12.4), a "reset settings" action, and graphics/battery options (frame-rate cap, §3.5). | Producer / user | Before Alpha UX spec |
| OQ-9 | Store format and file API (`ConfigFile` vs JSON) → becomes an ADR; must keep R9's read-back and tmp-then-rename. | Technical director | Before implementation |
