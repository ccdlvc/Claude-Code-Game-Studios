# Account and Cloud Save

> **Status**: Designed (pending independent /design-review)
> **Author**: user + Claude (autonomous batch run, decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet). Serves the locked GDD §1 promise "cloud save đa nền tảng" (cross-device cloud save).

## Summary

Account and cloud save gives every guild an identity on the backend and keeps one copy of its local save in the cloud, so a guild survives a lost phone and follows the player to another device. Players see it only as a quiet "backed up" mark, an optional Google/Apple sign-in, and, rarely, a screen asking which of two saves to keep. It exists because GDD §1 locks cross-platform cloud save, and because purchases, entitlement and leaderboards all need a stable account to attach to.

> **Quick reference** — Layer: `Feature` · Priority: `Alpha` · Key deps: `Local save and migration (6, provisional)`, `Sim core and tick loop (1)`; depended on by `Entitlement (32)`, `In-app purchases (34)`, `Leaderboards (35)`, `Settings (45)`

## Overview

Account and cloud save is a service-layer system (GDD §3.2 `[Services]`, `CloudService`) that sits outside the simulation. It does two jobs. **Account**: it gives the installation a backend identity, an anonymous guest identity first and a linked Google, Apple or (provisionally) Steam identity once the player signs in (§8.1), so the same guild can be opened on another device. **Cloud save**: it keeps exactly one cloud slot per account holding an opaque copy of the save file that Local save (6) already wrote, uploads it on a throttle, checks for a newer copy on launch, and, when the device copy and the cloud copy have both moved on since they last agreed, stops and lets the player choose (§8.1 "xung đột → người chơi chọn bản"). It never reads or writes simulation state, never takes a snapshot itself, and never blocks play: the game is single-player and offline-first (§1), so every cloud operation is asynchronous and failure only means "not backed up yet". It also hands three things to other services: the account id and session token (Entitlement, IAP, Leaderboards) and a server-time reading that Offline progress may choose to trust (§10). Backend choice is Supabase (Postgres + Auth + Edge Functions, §8.1 [ĐỀ XUẤT]); this GDD specifies behaviour against a backend-neutral `CloudService` contract so the choice can still change. Implementation details (HTTP client, token storage, table layout, RLS policy text) → become ADRs.

## Player Fantasy

*Framing chosen: Indirect (Persistence category). The player feels what this system enables, not the system.*

**"My guild is safe, and it goes where I go."** The moment it lands: a player who has spent three weeks raising a guild loses their phone, installs the game on a new one, taps "Sign in with Google", and the hall loads with every member, every enhanced blade and the Golden Boss timer exactly where they left it — followed by the usual "while you were away" report. The relief is the fantasy. The cost of a tycoon game is time invested; the system's promise is that the time is never lost to hardware.

The second, quieter moment is the player who never signs in: they still see a small "backed up 2 min ago" mark in Settings and never think about it again. Infrastructure done right is invisible.

What this asks of the rest of the design:
- A conflict must never silently destroy progress. If two devices disagree, the player decides, sees enough to decide well (guild name, level, members, how much play each side has), and the side they do not pick is kept as a backup, not deleted.
- Sign-in is never a gate. Nothing in the core loop requires an account (§1 single-player offline).
- The system never nags. No pop-ups asking to sign in during play; one prompt in onboarding at most, and the Settings entry.

Candidate framings considered (lens: creative direction): (A) "Safe and portable" — chosen; (B) "One guild across every screen" — PC/Web continuity, rejected as the anchor because PC and Web ship after Android (§12.2 phase 6) and the Wave 1 player has one device; (C) "Nothing is ever lost" — too absolute, since a guest who never connects and loses the phone does lose the guild. No pillar exists to quote; the anchor is GDD §1.

## Detailed Design

> Specialist lenses applied (Foundation/Infrastructure row, SKILL §6): **systems-designer** (primary), **gameplay-programmer** and **engine-programmer** (supporting). Their points are folded into the rules below; the one disagreement is recorded under R6.
> - systems-designer: every sync state and transition must be explicit; conflict detection must not depend on device clocks; a lost-update between two devices is the failure to design against.
> - gameplay-programmer: nothing here may touch the tick; the only safe way to adopt a different save is the same "discard the core instance and reload" path the Sim core already defines (Sim core R10).
> - engine-programmer: Godot has no SDK dependency for this (REST over `HTTPRequest`, §3.1); platform sign-in goes through Android/iOS plugins that the P1 spike must verify (§12.1); token storage on device has no built-in keychain API → ADR.

### Core Rules

**R1 — Outside the simulation.** Account and cloud save is a host-level service. It holds no simulation state, registers no tick phase, emits no Event-bus events (the bus carries P6 sim events only, Event bus GDD), and is never called from inside a tick. Its outputs to the UI are host signals (`account_state_changed`, `sync_state_changed`, `conflict_detected`). It may use engine randomness and engine time, because the determinism rules (`GODOT_PORT.md`, RNG GDD) bind only the simulation.

**R2 — Offline-first, never blocking.** No game screen waits on the network, except the two screens the player opened on purpose: the sign-in flow and the conflict choice. A failed request is retried by F2 and surfaced only as the sync status ("not backed up yet"). Launch never waits for a cloud check: the local save loads first; the cloud check runs in the background and, if it finds something, raises the conflict or adopt flow (R7) as an interruption the player can postpone.

**R3 — Identity: guest first, link later.** On the first launch that has network, the service creates an **anonymous guest account** on the backend (Supabase anonymous sign-in, to be verified in the P1 spike) and stores its refresh credential on the device. A guest account has a real `account_id` and its own cloud slot, so a guest is backed up too, and purchases (34) and entitlement (32) have something to attach to. **Linking** adds a provider identity (Google on Android, Apple on iOS — mandatory on iOS whenever any other social login is offered, §8.1 — Google on Web, Steam on PC, provisional) to the **same** `account_id`, so linking never moves or copies a save. Signing in on a second device with an already-linked provider yields that account's `account_id` and its cloud slot. A device that has never had network has no account at all (state `NoAccount`) and plays normally.

**R4 — One cloud slot per account.** Each account has exactly `cloud_slot_count` = 1 active slot (§8.1, systems index). The slot holds one **cloud record**: the save blob plus metadata (R5). The backend keeps the previous `cloud_server_history_depth` records (default 1) as a server-side safety copy, readable only through "Restore previous cloud backup" in Settings. More slots for Premium (§11.2 suggestion) are not in this design (Open Questions OQ-5).

**R5 — The blob is opaque; the metadata is small.** The cloud record is:

| Field | Written by | Meaning |
|---|---|---|
| `blob` | client | The exact bytes of the save file Local save (6) last wrote (compressed JSON with its own checksum, §8.2). The cloud never parses it. |
| `blob_sha256` | client, checked by server | Hash of `blob`, for transport integrity. |
| `rev` | **server** | Integer, starts at 1, +1 on every accepted upload. The only conflict key (R6). |
| `server_saved_utc` | **server** | Server time of acceptance. Display only. |
| `schema_version` | client | Save schema version (Local save, S8). |
| `sim_version` | client | `SIM_VERSION` of the writing client (Sim core R12). |
| `summary` | client | Display data for the conflict screen: `guild_uid`, guild display name, guild level, member count, highest member level, rebirth count, `tick` (world ticks since guild creation). Read from the save's header, which Local save must expose (PROVISIONAL). |
| `device_tag` | client | Platform name plus a 4-hex tag derived from a hash of the RNG `install_id`, so the conflict screen can say "this device" or "Android ·3f2a". Never a hardware identifier. |

Row-level security (or the backend's equivalent) lets an account read and write only its own slot. The service never uploads anything else about the player.

**R6 — Conflict detection by revision, never by clock.** The device keeps `sync_meta` beside (not inside) its local save: `account_id`, `base_rev` (the cloud `rev` the local save last agreed with), `base_tick` (the save's `tick` at that moment) and `local_dirty` (true once Local save writes a save after that agreement). Every upload is a **compare-and-set**: the server accepts it only if the slot's current `rev` equals the `base_rev` sent; it then returns the new `rev`, which becomes `base_rev`, and `local_dirty` clears. Classification of local vs cloud is F3. Device clocks are never used to decide which copy is newer, because they can be wrong or set back (§10). *(Lens disagreement, resolved by recommended option: GDD §20 S8 says the Python reference should "take the latest by `updated_at`, warn on large divergence". systems-designer objected that `updated_at` from two device clocks cannot order saves; the design keeps S8's intent — recommend the more advanced copy and warn on large divergence — but orders by revision and progress, not timestamps. S8 should simulate this rule; see OQ-2.)*

**R7 — What happens for each classification (F3).**
1. `in_sync` — nothing.
2. `local_ahead` — upload when F1 says it is due.
3. `cloud_ahead` (the cloud moved on, this device did not) — **adopt flow**: the player sees one notice, "A newer backup of *[guild]* from *[device_tag]* is in the cloud. Load it?" with *Load* (default) and *Not now*. *Load* downloads, verifies (R9) and adopts it (R8). *Not now* keeps playing the local copy, which makes the next save `local_dirty`, so the case becomes `diverged` and the full choice (4) appears on the next check. The device never adopts a cloud copy without one tap, because adoption replaces what is on screen.
4. `diverged` (both moved on since `base_rev`) — **conflict flow** (§8.1): a blocking-by-choice screen showing both summaries side by side, labelled "This device" and "Cloud (*device_tag*)", each with the progress it has made since they last agreed (F4). The recommended option is the side with more progress since base (F4), ties go to the cloud copy. Choosing either side triggers a second confirmation when the discarded side's progress is at or above `cloud_divergence_warn_ticks` (F4) or when the two `guild_uid` differ ("These are two different guilds"). *Keep this device* uploads with `base_rev` set to the cloud's current `rev` (a forced CAS on the rev the player was shown, so a third device that uploads in between causes a fresh conflict, not a silent overwrite). *Keep cloud* adopts the cloud copy (R8). *Decide later* postpones; uploads stay paused (`Conflict` state) until the player decides, and the reminder reappears on each launch and in Settings.
5. `different_account` (a sign-in switched this device to an account whose slot holds a different guild) — handled as `diverged` with the "two different guilds" confirmation always shown.
6. `cloud_empty` (a new account, or the slot was deleted) — upload if a local save exists.

**R8 — Adopting a save is a reload, never a hot swap.** To adopt a cloud copy the service (a) asks Local save to store the current local save as a **kept backup** (labelled "replaced by cloud copy, [date]") — this never overwrites Local save's normal rotating generations; (b) hands the verified blob to Local save, which writes it as the current save, migrating if needed; (c) asks the host to discard the running core instance and boot a new one from that save, the same path as Sim core R10's recovery reload. Offline progress then runs from the adopted save's `last_saved_utc` exactly as on any cold start. The service never calls `restore_core` itself and never changes state mid-tick.

**R9 — Downloads are verified before anything is touched.** A downloaded blob is accepted only if its `blob_sha256` matches, Local save's own checksum passes, and its `schema_version` is one this build can read (equal, or older with a migration path). A blob with a **newer** `schema_version` or `sim_version` than this build supports is never loaded and never overwritten from this device: the slot shows "Update the game to use this backup" and uploads from this device are refused (`Blocked` state) until the app is updated. A blob that fails a check is discarded; the local save is untouched and the failure is logged.

**R10 — Upload source and size.** The service uploads only a save file Local save has completed (atomic write done, §8.2). It never snapshots the core. If the compressed blob exceeds `cloud_blob_max_bytes` the upload is refused locally, the status shows "backup too large", and a diagnostic is logged; the local save is unaffected. Local save must keep its file well under this bound (PROVISIONAL).

**R11 — When uploads happen (F1).** An upload is attempted when `local_dirty` is true and any of: (a) the throttle `cloud_upload_min_interval_s` has passed since the last successful upload; (b) the app is about to be backgrounded or closed (mobile pause notification, desktop quit) — this one bypasses the throttle; (c) the player taps "Back up now" in Settings — bypasses the throttle; (d) the player is about to sign out or switch account — bypasses the throttle and must finish or be explicitly abandoned first (R13). No upload is attempted in states `Conflict`, `Blocked`, `Disabled` or `NoAccount`.

**R12 — When the cloud is checked.** A metadata check (fetch `rev`, `summary`, `schema_version`, `device_tag`; not the blob) runs on cold start once the local save has loaded, on resume after an absence of at least `cloud_check_on_resume_s`, after every sign-in, and on "Back up now". The blob is downloaded only when the player chooses to adopt it (R7). Every successful response also refreshes the server-time reading (R14).

**R13 — Sign-out and account switching.** Signing out first attempts a final upload (R11d). The local save stays on the device; `sync_meta` is cleared, and the device becomes a fresh guest on next network contact (a new anonymous account, `base_rev` empty), so the next check sees `cloud_empty` and backs the local guild up to the new guest slot. Signing in to a different account that already has a cloud record goes through R7 case 5. A guest account that signs out before linking is warned: "This guest backup can't be recovered after you sign out" (anonymous accounts have no way back in).

**R14 — Server time for other systems.** Each successful response carries the backend's time (an HTTP `Date` header or an RPC result — ADR). The service keeps `server_utc_at_sync` and the device's `monotonic_us()` reading at the same moment, and exposes `server_utc_estimate()` = F5 while no device suspend has happened since that reading; after a suspend it returns *unknown* until the next response. It decides nothing with it. Offline progress (31) owns whether to trust it for `Δt` (§10, Sim core R7 "trust policy"), and Leaderboards (35) owns its own server-side checks.

**R15 — Account deletion.** Settings offers "Delete account and cloud backup". After a confirmation that names what will be lost (cloud backup, account link, purchases restorable only through the store), the service calls a backend function that deletes the slot, its history and the auth user. The local save on this device is not deleted (the player can still play locally, as a new guest). Store policies (Apple and Google Play both require in-app account deletion for apps with account creation — verify current wording before submission) make this mandatory for launch.

**R16 — Cloud backup toggle.** Settings has "Cloud backup: On/Off" (default On). Off stops uploads and checks (`Disabled`) and does not delete the cloud record. Turning it back on runs a check (R12) first. The account itself stays; entitlement and purchases keep working.

**R17 — What is not in the blob.** Purchased consumable balances that the store cannot restore (Thiên Cơ Kính stock, §11.5) must not live only inside the save blob, because choosing a save in a conflict would then duplicate or erase paid items. They belong to a server-side record owned by In-app purchases / Entitlement (32, 34) and keyed by `account_id` (PROVISIONAL). What a spent Kính *produced* (an exact PA revealed on a member) is game state and stays in the save.

### States and Transitions

Two independent state machines. The account state is about identity; the sync state is about the slot.

**Account state**

| State | Meaning | → To | Trigger |
|---|---|---|---|
| `NoAccount` | Never had network; no backend identity | `Guest` | First successful anonymous sign-in (R3) |
| `Guest` | Anonymous account, credential on device | `Linked` | Player links Google/Apple/Steam (R3) |
| | | `NoAccount` | Sign-out (R13) — next network contact makes a new `Guest` |
| | | `SessionLost` | Refresh credential rejected (expired, revoked, device data cleared) |
| `Linked` | Has at least one provider identity | `NoAccount` | Sign-out (R13) |
| | | `SessionLost` | Refresh credential rejected |
| | | `NoAccount` | Account deleted (R15) |
| `SessionLost` | Account exists but this device cannot act for it | `Linked` | Player signs in again with the provider |
| | | `NoAccount` | Guest session lost: no way back; next network contact makes a new `Guest` and the old guest slot is orphaned (Edge Cases) |

**Sync state**

| State | Meaning | → To | Trigger |
|---|---|---|---|
| `Disabled` | Toggle off, or account state is `NoAccount`/`SessionLost` | `Checking` | Toggle on with an account; account becomes `Guest`/`Linked` |
| `Idle` | Nothing in flight; `local_dirty` may be true | `Uploading` | F1 says due (R11) |
| | | `Checking` | R12 trigger |
| `Checking` | Metadata request in flight | `Idle` | `in_sync`, `local_ahead` or `cloud_empty` (upload then becomes due) |
| | | `AdoptOffered` | `cloud_ahead` |
| | | `Conflict` | `diverged` / `different_account` |
| | | `Blocked` | Cloud copy needs a newer build (R9) |
| | | `Backoff` | Request failed |
| `Uploading` | CAS upload in flight | `Idle` | Accepted (`base_rev` updated, `local_dirty` cleared) |
| | | `Checking` | Rejected: `rev` mismatch (someone else uploaded) — reclassify |
| | | `Backoff` | Network/server error |
| `AdoptOffered` | Waiting for the player's Load / Not now | `Downloading` | Load |
| | | `Idle` | Not now (local becomes dirty on next save → `Conflict` on next check) |
| `Downloading` | Blob request in flight | `Idle` | Verified and adopted (R8, R9); `base_rev` = cloud `rev` |
| | | `Idle` | Verification failed (local kept, logged) |
| | | `Backoff` | Network error |
| `Conflict` | Waiting for the player's choice; uploads paused | `Uploading` | Keep this device |
| | | `Downloading` | Keep cloud |
| `Blocked` | Cloud copy is from a newer build | `Checking` | App updated (on next launch) |
| `Backoff` | Waiting F2 delay | previous request | Delay elapsed, or "Back up now" (resets the failure count) |

`Disabled` is entered from any state when the toggle goes off or the account state leaves `Guest`/`Linked`; any in-flight request is abandoned (an abandoned upload leaves `local_dirty` true, so nothing is lost).

### Interactions with Other Systems

| System | Direction | Data / call | Owner of the interface |
|---|---|---|---|
| Local save and migration (6) | Upstream, hard | Reads: path and bytes of the last completed save, its header (`schema_version`, `sim_version`, `summary` fields, `last_saved_utc`), a "save completed" signal. Calls: `store_kept_backup(label)`, `write_current_from_blob(blob)` (migrates), checksum verify. | Local save (6). **PROVISIONAL** — GDD not written. |
| Sim core and tick loop (1) | Upstream, hard (indirect) | Uses the host's reload path (discard instance, construct new, R10) to adopt a save; reads `GameClock.monotonic_us()` for F5 and the throttle; never calls the core. | Sim core (written). |
| Deterministic RNG (2) | Upstream, soft | Reads `install_id` (kept in platform settings, RNG R2) only to derive `device_tag`. | RNG (written). |
| Offline progress (31) | Downstream, soft | Gets `server_utc_estimate()` (R14) and decides whether to trust it. After an adopt, runs as on a cold start. | This system provides the reading; Offline progress owns the policy. |
| Entitlement and feature flags (32) | Downstream, hard | Gets `account_id`, session token, `account_state_changed`. Syncs `is_premium` across devices through the account (§11.3). | This system. |
| In-app purchases (34) | Downstream, hard | Gets `account_id` and session token to call receipt-verification functions; owns the server-side consumable balance (R17). | This system for identity; IAP for balances. **PROVISIONAL**. |
| Leaderboards and anti-cheat (35) | Downstream, hard | Gets `account_id`, session token, `account_state` (whether guests may rank is 35's call). | This system for identity. **PROVISIONAL**. |
| Settings (45) | Downstream, hard | Shows account state, link/sign-out/delete, toggle, "Back up now", "Restore previous cloud backup", sync status, pending conflict. | Settings owns the screen; this system owns the actions. |
| Onboarding (44) | Downstream, soft | May show one optional "Sign in to keep your guild safe" step. | Onboarding. |
| Analytics (37) | Downstream, soft | May subscribe to host signals (sync success/failure, conflicts, choice made) — not through the sim Event bus. | Analytics. |
| Ads and consent (33) | Sideways, soft | The privacy notice shown at first launch must cover the cloud backup and the guest account (§14). | Ads/consent flow owns the notice. |

## Formulas

All times here are wall-clock service timings outside the simulation; none affects a simulation result. Knob defaults are proposals (§4 "every number is a starting point").

### F1 — `upload_due`

The upload_due formula is defined as:

`upload_due = local_dirty AND sync_state = Idle AND ( forced OR (now_mono_s − last_upload_ok_mono_s) ≥ cloud_upload_min_interval_s )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `local_dirty` | bool | — | calculated | A save was written since the last agreement with the cloud (R6) |
| `forced` | bool | — | calculated | True for triggers R11 (b) pause/quit, (c) "Back up now", (d) sign-out |
| `now_mono_s` | int | ≥ 0 | calculated | `GameClock.monotonic_us() // 1,000,000`, re-baselined after a suspend (then treated as "interval elapsed") |
| `last_upload_ok_mono_s` | int | ≥ 0 | calculated | Monotonic seconds of the last accepted upload; none yet → interval elapsed |
| `cloud_upload_min_interval_s` | int | 60–3,600 | data file | Throttle between ordinary uploads; default **300** |

**Output Range:** boolean. At the default, a foreground session uploads at most 12 times an hour plus one per backgrounding.
**Example:** a save at 10:00:00 uploads at once (first upload of the session); saves at 10:01 and 10:03 wait; the save at 10:05:10 uploads (≥ 300 s). The player backgrounds the app at 10:06 → forced upload.

*Why 300 s:* the worst case lost to a destroyed phone is about 5 minutes of foreground play plus anything since the last backgrounding, which is small next to an 8-hour offline cap (§10), and it keeps a long idle session to a handful of uploads an hour (F6).

### F2 — `retry_delay_s`

The retry_delay_s formula is defined as:

`retry_delay_s = min(cloud_retry_base_s × 2^(n − 1), cloud_retry_cap_s) × (1 + j)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `n` | int | 1 – ∞ (clamped to 1–20 in the exponent) | calculated | Consecutive failures of this request kind; resets to 0 on success or "Back up now" |
| `cloud_retry_base_s` | int | 5–300 | data file | First retry delay; default **30** |
| `cloud_retry_cap_s` | int | 300–7,200 | data file | Longest delay; default **1,800** |
| `j` | float | 0.0–0.2 | calculated (engine random, outside sim, R1) | Jitter so many clients that failed together do not retry together |

**Output Range:** 30 s to 2,160 s at defaults (1,800 × 1.2). The exponent is clamped at 20, so `2^(n−1)` never overflows; at n ≥ 7 the cap already binds (30 × 64 = 1,920 > 1,800).
**Example:** failures 1, 2, 3, 4 → 30, 60, 120, 240 s (before jitter); failure 7 onward → 1,800 s.
**Boundaries:** `n = 0` never evaluates (no failure, no retry). An auth failure (session rejected) is not retried by F2; it moves the account to `SessionLost`.

### F3 — `sync_class`

The sync_class formula is defined as:

```
sync_class =
  cloud_empty        if cloud_rev = none
  in_sync            if cloud_blob_sha256 = sha256(local save file)   (own upload whose reply was lost; set base_rev = cloud_rev, clear local_dirty)
  different_account  if base_rev = none AND cloud_guild_uid ≠ local_guild_uid
  in_sync            if cloud_rev = base_rev AND NOT local_dirty
  local_ahead        if cloud_rev = base_rev AND local_dirty
  cloud_ahead        if cloud_rev > base_rev AND NOT local_dirty
  diverged           otherwise   (cloud_rev > base_rev AND local_dirty, or base_rev = none with the same guild)
```

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `cloud_rev` | int or none | ≥ 1 | calculated (server) | Current revision of the slot |
| `base_rev` | int or none | ≥ 1 | calculated (`sync_meta`) | Revision this device last agreed with; none after sign-in on a new device or after sign-out |
| `local_dirty` | bool | — | calculated | As F1 |
| `cloud_guild_uid`, `local_guild_uid` | string | — | calculated (save header) | Stable guild id created with the guild (Local save, PROVISIONAL) |

**Output Range:** one of six classes (rules evaluated top to bottom; the hash rule matches only when the cloud holds exactly the bytes on this device, so it is always safe). `cloud_rev < base_rev` cannot happen while the server only increments; if seen (server restore, data loss) it is treated as `diverged` and logged.
**Example:** device A uploads rev 7 and stops. Device B, last synced at rev 5, played offline → `cloud_rev 7 > base_rev 5`, dirty → `diverged`. Device A reopens next day with no new save → `cloud_rev` 8 (B's choice was uploaded) `> 7`, not dirty → `cloud_ahead` → adopt offer.
*A first install restoring onto a fresh device* (`base_rev = none`, no local save) skips F3: with no local save it simply offers the cloud copy (`cloud_ahead` behaviour).

### F4 — `progress_since_base` and the divergence warning

The progress_since_base formula is defined as:

`progress_since_base(side) = max(0, side.tick − base_tick)`
`recommended = argmax(progress_since_base(local), progress_since_base(cloud))`, ties → cloud
`warn_on_discard(side) = progress_since_base(side) ≥ cloud_divergence_warn_ticks OR local_guild_uid ≠ cloud_guild_uid`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `side.tick` | int | ≥ 0 | calculated (save header `summary.tick`) | World ticks since guild creation, including offline gaps skipped (Sim core R14) |
| `base_tick` | int | ≥ 0 | calculated (`sync_meta`) | `tick` of the save at the last agreement; 0 when `base_rev` is none |
| `cloud_divergence_warn_ticks` | int | 0–864,000 | data file | Progress the player is about to throw away that triggers a second confirmation; default **36,000** (1 hour of world time, Sim core F4 `ticks(3,600)`) |

**Output Range:** `progress_since_base` 0 to 2^63−1 (int64 ticks). `warn_on_discard` boolean. At knob 0 every discard warns; at the maximum (24 h = the Premium offline cap, 864,000) a full day can be discarded with one tap — the safe range keeps it ≤ 8 h (288,000).
**Example:** base_tick 1,000,000. Local tick 1,054,000 (+54,000 = 1.5 h), cloud tick 1,012,000 (+12,000 = 20 min). Recommended: *Keep this device*. Choosing *Keep cloud* discards 54,000 ≥ 36,000 → second confirmation: "You'll lose about 1 h 30 min of progress on this device. It will be kept as a backup."
*Why world ticks, not play time or timestamps:* ticks come from the save itself, need no clock, and count offline progress — which is real progress to the player. The weakness (a long offline gap counts the same as active play) is accepted; the side-by-side summary (level, members, rebirths) carries the rest.

### F5 — `server_utc_estimate`

The server_utc_estimate formula is defined as:

`server_utc_estimate = server_utc_at_sync + (now_mono_us − mono_us_at_sync) // 1,000,000`, or *unknown* if a device suspend occurred since `mono_us_at_sync` or no successful response exists this process

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `server_utc_at_sync` | int | ≥ 0 | calculated (server response) | Server time in whole UTC seconds at the last successful response |
| `mono_us_at_sync` | int | ≥ 0 | calculated | `GameClock.monotonic_us()` when that response arrived |
| `now_mono_us` | int | ≥ `mono_us_at_sync` | calculated | Current monotonic reading |

**Output Range:** UTC seconds, accurate to about ±(1 s + request round-trip/2); *unknown* across suspends because the monotonic clock may not count sleep (Sim core R7, OQ-12).
**Example:** response at mono 5,000,000 µs says 1,795,000,000; at mono 65,500,000 µs the estimate is 1,795,000,060.

### F6 — `daily_upload_bytes` (capacity estimate)

The daily_upload_bytes formula is defined as:

`daily_upload_bytes = blob_bytes × (foreground_s / cloud_upload_min_interval_s + backgroundings)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `blob_bytes` | int | 1 – `cloud_blob_max_bytes` | calculated | Compressed save size; assumed ~100–300 KB (PROVISIONAL, Local save) |
| `foreground_s` | int | 0–86,400 | calculated | Foreground seconds per day for one player |
| `backgroundings` | int | ≥ 0 | calculated | Times the app is backgrounded per day |
| `cloud_upload_min_interval_s` | int | 60–3,600 | data file | As F1 |

**Output Range:** an upper bound (uploads happen only when dirty). Used to size the backend plan, not at runtime.
**Example:** 200 KB blob, 1 h foreground, 6 backgroundings → 200 KB × (12 + 6) = 3.6 MB/day per active player; 10,000 daily players ≈ 36 GB/day ingress. Backend plan limits and prices are **not sourceable** from this repo (§8.1 "kiểm tra giá/giới hạn hiện hành") — check before launch (OQ-6). If too high, raise the interval before shrinking anything else.

### F7 — Blob size guard

`upload_allowed_by_size = blob_bytes ≤ cloud_blob_max_bytes`

| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `blob_bytes` | int | ≥ 1 | calculated | As F6 |
| `cloud_blob_max_bytes` | int | 262,144–8,388,608 | data file | Hard limit; default **2,097,152** (2 MiB) — several times the expected save, below typical request-body limits |

**Output Range:** boolean. **Example:** a 2.5 MiB blob is refused locally with "backup too large" (R10).

## Edge Cases

**Identity**
- **If the device has no network on first launch and never gets it**: state stays `NoAccount`; play is unaffected; Settings shows "Not backed up — no connection". The guild is lost if the device is lost, which the Player Fantasy accepts (framing C rejected).
- **If a guest's session is lost (app data cleared, credential revoked)**: the old guest slot cannot be reached again. The device becomes a new guest; if a local save still exists it is uploaded to the new slot (`cloud_empty`). The orphaned slot is deleted by a backend cleanup after `guest_orphan_retention_days` (proposal 90) of inactivity (OQ-4).
- **If a player links a provider that is already linked to another account**: linking is refused ("This Google account already has a guild backup"). The player is offered *Switch to that account*, which is a sign-in to the other account and goes through R7 case 5. Accounts are never merged (merging two guilds is meaningless).
- **If sign-in is cancelled or the provider fails**: account state is unchanged; a guest stays a guest with its backup intact.
- **If the provider (e.g., Apple) hides the email**: nothing depends on email; `account_id` is the only key.

**Conflicts and timing**
- **If two devices upload at the same instant with the same `base_rev`**: the server's compare-and-set accepts exactly one; the other gets a `rev` mismatch, re-checks, and sees `diverged`. No upload ever silently overwrites another.
- **If the player picks *Keep this device* while a third device has uploaded since the conflict screen opened**: the forced CAS uses the `rev` that was shown, so it fails and a fresh conflict is shown with the new cloud summary. The player never overwrites a copy they did not see.
- **If the app is killed during an upload**: the server either committed it (rev advanced) or not. On next launch, `base_rev` still holds the old value; the check returns `cloud_rev = base_rev + 1` with `blob_sha256` equal to the local save file's hash → F3 classifies `in_sync` (the device recognises its own upload) and `base_rev` is advanced. Without the hash match it would wrongly be `diverged`.
- **If the app is killed while adopting (R8)**: the kept backup was written first and the current save is replaced by an atomic write (Local save §8.2), so on relaunch either the old or the new save loads; if the old one loads, the next check offers the adopt again.
- **If the player keeps choosing *Not now* / *Decide later***: no upload happens until the choice is made, so the cloud copy is protected; the reminder stays in Settings. There is no forced timeout (it would be a silent decision).
- **If a conflict is between two different guilds (`guild_uid` differs)**: the second confirmation is always shown, and the losing guild is kept as a local backup. One slot means only one of them can be backed up (OQ-5 more slots).
- **If the device clock is wildly wrong or set back**: no effect on this system (R6 uses revisions; F5 uses server time). Offline progress handles its own Δt.

**Versions and data**
- **If the cloud copy has a newer `schema_version`/`sim_version`**: `Blocked`; the game says "Update to use your cloud backup"; this device plays its local save and does not upload, so an old build can never overwrite a newer save.
- **If the cloud copy is older-schema**: downloadable; Local save migrates it on adopt.
- **If a downloaded blob fails its hash or checksum**: it is discarded, the local save stays, the event is logged, and the server-side previous record (R4) remains available through "Restore previous cloud backup".
- **If the blob exceeds `cloud_blob_max_bytes`**: upload refused locally (R10, F7); the status shows it; Local save's size is the thing to fix (OQ-3).
- **If the local save is in an untrusted state (Sim core `state_trusted` false or core `Failed`)**: Local save does not write a new save (Sim core R10), so the service has nothing new to upload and the last good cloud copy is preserved. The service never uploads anything other than a completed Local save file.

**Abuse**
- **If a player rolls back by adopting an older cloud copy (e.g., to undo an enhancement failure)**: possible only through the server-side previous record ("Restore previous cloud backup") or by keeping an older device's save in a conflict. Single-player rollback is tolerated — the game is offline-first and local saves can be copied anyway. What must not be exploitable: paid consumables (kept outside the blob, R17) and leaderboard standing (Leaderboards 35 must not trust a save's history blindly; OQ-7).
- **If a player edits the save file and uploads it**: the cloud stores whatever the client uploads; it is the player's own single-player save. Leaderboards does its own verification (§8.1 signed summary + seed).

**Account deletion**
- **If deletion is requested while offline**: the button is disabled with "Needs a connection"; nothing is queued (a deletion must be confirmed by the server, not deferred).
- **If deletion succeeds**: local save kept, account state `NoAccount`, `sync_meta` cleared; next network contact creates a new guest and backs the local guild up again unless the player turns the toggle off. The confirmation text says so.

## Dependencies

**Upstream (this system depends on)**

| System (#) | Hard / soft | Interface | Status |
|---|---|---|---|
| Local save and migration (6) | Hard | Completed save file bytes and header (`schema_version`, `sim_version`, `guild_uid`, `tick`, summary fields, `last_saved_utc`); "save completed" signal; `store_kept_backup(label)`; `write_current_from_blob(blob)` with migration; checksum verify; atomic writes (§8.2) | **No GDD yet — PROVISIONAL** (OQ-1) |
| Sim core and tick loop (1) | Hard (indirect) | Host reload path (Sim core R10: discard instance, construct new); `GameClock.monotonic_us()` (R7); never called during a tick | GDD exists (Needs Revision). This system adds no requirement to it beyond what R10 and R7 already allow. |
| Deterministic RNG (2) | Soft | `install_id` (RNG R2) for `device_tag` | GDD exists |
| Data layer (3) | Soft | Reads the proposed `cloud_*` config keys (Tuning Knobs) from `config.csv` | GDD exists; keys not added yet (OQ-8) |

The systems index lists only Local save as a dependency, which is correct for hard design dependencies; Sim core, RNG and Data layer are reached through it or are soft.

**Downstream (systems that depend on this one)** — none has a GDD yet.

| System (#) | Hard / soft | What it needs from here |
|---|---|---|
| Entitlement and feature flags (32) | Hard | `account_id`, session token, account-state signal; cross-device sync of `is_premium` (§11.3) |
| In-app purchases (34) | Hard | `account_id` and token for receipt verification; owns the server-side consumable balance (R17) |
| Leaderboards and anti-cheat (35) | Hard | `account_id`, token, account state; owns guest ranking policy and rollback resistance |
| Settings (45) | Hard | All account and backup actions (R13, R15, R16, "Back up now", "Restore previous cloud backup") |
| Offline progress (31) | Soft | `server_utc_estimate()` (R14); not listed in the index as a dependency — it can work from device time alone |
| Onboarding (44), Analytics (37) | Soft | Optional sign-in step; host signals |

**Bidirectional check:** the index rows for 32, 34, 35 and 45 list "Account and cloud save" — consistent. Offline progress (31) would gain a soft link to this system; that is 31's GDD's call, not an index change made here.

## Tuning Knobs

Proposed as rows in `data/config.csv` (key,value), not added by this GDD (OQ-8). They tune service behaviour, not game balance; none changes a simulation result, so none needs a balance-simulator run or a `SIM_VERSION` bump.

| Knob | Default | Safe range | Too low | Too high | Interacts with |
|---|---|---|---|---|---|
| `cloud_upload_min_interval_s` | 300 | 120–900 | Backend traffic and cost scale up (F6); battery/data use | More play lost if a device dies in the foreground | F6 capacity; `cloud_check_on_resume_s` |
| `cloud_retry_base_s` | 30 | 10–120 | Hammering a down backend from every client | Slow recovery after a short outage | `cloud_retry_cap_s` (if base ≥ cap, backoff is flat) |
| `cloud_retry_cap_s` | 1,800 | 600–3,600 | Same as base too low during long outages | Backup stays stale for hours after the backend returns ("Back up now" resets it) | `cloud_retry_base_s` |
| `cloud_check_on_resume_s` | 600 | 60–3,600 | A check on every quick app switch | A device that sat idle may miss another device's newer save until next cold start | `cloud_upload_min_interval_s` |
| `cloud_divergence_warn_ticks` | 36,000 | 6,000–288,000 | Every conflict needs two taps (warning fatigue) | Large progress discarded with one tap | Sim core tick rate (F4 uses ticks) |
| `cloud_blob_max_bytes` | 2,097,152 | 262,144–8,388,608 | Real saves refused | Slow uploads on mobile data; backend body limits | Local save size (OQ-3) |
| `cloud_server_history_depth` | 1 | 0–3 | 0 removes the server-side safety copy | Storage cost × depth; more rollback surface | — |
| `cloud_request_timeout_s` | 15 | 5–60 | Fails on slow mobile networks | A stuck request delays the conflict check | F2 |
| `guest_orphan_retention_days` | 90 | 30–365 | Guest data deleted before a reinstall could reach it (it cannot anyway) | Storage held for dead guests | Privacy policy retention text |

`cloud_slot_count` = 1 is a design constant (§8.1), not a knob.

## Visual/Audio Requirements

Optional for Persistence; brief note. No art bible exists yet.
- A small sync-status glyph in Settings and, optionally, a corner mark on the guild screen during an upload: four states (backed up / backing up / not backed up / needs attention). Shape plus text, never colour alone.
- The conflict screen reuses the standard modal frame; each side shows the guild crest and the summary fields. No VFX.
- Audio: none required. The conflict and adopt modals use the standard UI open sound (Audio 40) — no alert sound, since this is not urgent.

## Game Feel

Optional for this category. One target: a cloud operation must never cause a frame hitch or an input stall. Uploads and downloads run off the main thread or as non-blocking HTTP requests; hashing a 2 MiB blob is done off the frame (ADR). The adopt reload shows the same loading screen as a cold start.

## UI Requirements

- **Settings → Account & backup** (owned by Settings 45): account state ("Guest" / "Signed in with Google"), Link account (Google/Apple/Steam per platform), Sign out, Delete account and cloud backup, Cloud backup On/Off, Back up now, Restore previous cloud backup, last backup time (server time, shown in local format) and device tag, pending-conflict banner.
- **Adopt notice** (R7.3): one modal, two buttons, guild name and device tag.
- **Conflict screen** (R7.4): two columns with summary fields and "progress since last sync" (F4 rendered as hours/minutes), the recommended side marked, three actions; second confirmation for large or cross-guild discards. Must fit Vietnamese strings (longer than English) and the Free build's bottom banner (§11.3).
- **Blocked notice**: "Update the game to use your cloud backup" with a store link.
- All text through `i18n/` keys (§3.3).

> **📌 UX Flag — Account and cloud save**: This system has UI requirements. In Pre-Production, run `/ux-design` for the conflict screen and the Settings account section before writing epics; stories should cite `design/ux/[screen].md`.

## Cross-References

| This GDD | Refers to | What |
|---|---|---|
| R8, Dependencies | `sim-core-and-tick-loop.md` R10, R14 | Adopt = discard instance and reload; saves only between ticks; `restore_core` refuses other `sim_version` |
| R14, F5 | `sim-core-and-tick-loop.md` R7, OQ-12 | `GameClock`, monotonic clock not trusted across suspend; trust policy belongs to Offline progress |
| F4 | `sim-core-and-tick-loop.md` F4 | `ticks(3,600) = 36,000` |
| R5 | `deterministic-rng.md` R2 | `install_id` kept in platform settings, not in the save |
| R1 | `event-bus-and-history-log.md` | The bus carries sim P6 events only; this system uses host signals |
| Tuning Knobs | `data-layer-and-content-pipeline.md` | `config.csv` key,value format |
| R6, OQ-2 | `JX1_Tycoon_GDD.md` §20 S8 | Reference conflict simulation |
| Throughout | `JX1_Tycoon_GDD.md` §1, §8.1, §8.2, §10, §11.1, §11.3, §11.5, §12.1, §14 | Source intent |

## Acceptance Criteria

Story types: AC-1 to AC-14 are **Logic** (automated, against a fake `CloudService` backend and a fake clock, in `tests/unit/account_cloud/`); AC-15 to AC-17 are **Integration** (real backend in a test project); AC-18 to AC-19 are **UI** (screenshot evidence). Performance: AC-20.

- **AC-1 (R2, launch)**: **GIVEN** a local save and a backend that never responds, **WHEN** the game cold-starts, **THEN** the guild is playable with no wait attributable to the cloud (time to first interactive frame within 100 ms of the same launch with networking disabled), and sync state is `Checking` then `Backoff`.
- **AC-2 (R3)**: **GIVEN** a fresh install with network, **WHEN** first launch completes, **THEN** account state is `Guest` with a non-empty `account_id`, and after the first save the slot has `rev = 1`.
- **AC-3 (R3, linking)**: **GIVEN** a `Guest` with `rev = 4` in its slot, **WHEN** the player links Google, **THEN** `account_id` is unchanged, the slot still has `rev = 4`, and account state is `Linked`.
- **AC-4 (R6, CAS)**: **GIVEN** a slot at `rev = 7` and two fake clients both with `base_rev = 7` and dirty saves, **WHEN** both upload, **THEN** exactly one is accepted (`rev = 8`), the other is rejected and its next check classifies `diverged`.
- **AC-5 (F3, all classes)**: **GIVEN** the six (`cloud_rev`, `base_rev`, `local_dirty`, guild uid) combinations of the F3 table, **WHEN** classified, **THEN** each returns its listed class; and `cloud_rev < base_rev` returns `diverged` with a log entry.
- **AC-6 (R7.3, adopt)**: **GIVEN** `cloud_ahead`, **WHEN** the player taps *Load*, **THEN** a kept backup labelled "replaced by cloud copy" exists, the current save's bytes equal the downloaded blob (after any migration), the core was rebuilt (new instance id), and `base_rev` = cloud `rev`. **WHEN** instead the player taps *Not now* and the game then saves, **THEN** the next check classifies `diverged`.
- **AC-7 (R7.4, F4, recommendation)**: **GIVEN** `base_tick = 1,000,000`, local tick 1,054,000, cloud tick 1,012,000, **WHEN** the conflict screen opens, **THEN** *Keep this device* is marked recommended; **GIVEN** both at 1,020,000, **THEN** *Keep cloud* is recommended.
- **AC-8 (F4, warning boundary)**: **GIVEN** `cloud_divergence_warn_ticks = 36,000`, **WHEN** the player discards a side with progress 35,999, **THEN** no second confirmation; with 36,000, **THEN** the second confirmation appears; with differing `guild_uid` and progress 0, **THEN** it appears.
- **AC-9 (R7.4, third device)**: **GIVEN** a conflict screen opened at cloud `rev = 9`, **WHEN** another client uploads `rev = 10` and then the player picks *Keep this device*, **THEN** the upload is rejected and a new conflict screen shows the `rev = 10` summary.
- **AC-10 (R9, newer build)**: **GIVEN** a cloud record with `schema_version` one higher than the build supports, **WHEN** checked, **THEN** state is `Blocked`, no download is offered, and a dirty local save produces no upload request.
- **AC-11 (R9, corrupt)**: **GIVEN** a downloaded blob whose bytes do not match `blob_sha256`, **WHEN** adopt runs, **THEN** the current local save's bytes are unchanged and the core is not rebuilt.
- **AC-12 (F1, R11)**: **GIVEN** `cloud_upload_min_interval_s = 300` and a fake clock, **WHEN** saves complete at t = 0, 60, 180, 310 s, **THEN** uploads start at t = 0 and t = 310 only; **WHEN** a pause notification arrives at t = 320 with a dirty save, **THEN** an upload starts immediately.
- **AC-13 (F2)**: **GIVEN** base 30, cap 1,800 and jitter forced to 0, **WHEN** a request fails 1, 2, 3, 7 and 25 times in a row, **THEN** the delays are 30, 60, 120, 1,800 and 1,800 s; **WHEN** "Back up now" is tapped during a backoff, **THEN** the request runs at once and the failure count is 0.
- **AC-14 (F5)**: **GIVEN** a response with server time 1,795,000,000 at mono 5 s, **WHEN** queried at mono 65.5 s, **THEN** `server_utc_estimate()` = 1,795,000,060; **WHEN** a suspend notification occurred in between, **THEN** it returns *unknown*.
- **AC-15 (Edge: killed mid-upload)**: **GIVEN** an upload the server committed but whose response never arrived, **WHEN** the app relaunches, **THEN** the check classifies `in_sync` (matching hash, F3) and advances `base_rev`; no conflict screen appears.
- **AC-16 (R15, deletion)**: **GIVEN** a `Linked` account with a slot and one history record, **WHEN** deletion is confirmed online, **THEN** a fresh sign-in with the same provider finds no cloud record and a new `account_id`, and the local save on the device is byte-identical to before.
- **AC-17 (cross-device, end to end)**: **GIVEN** device A with a linked account and a guild at tick T, **WHEN** device B (fresh install) signs in with the same provider, **THEN** B offers the cloud copy, and after *Load* B's guild summary (name, level, member count, tick ≥ T) matches A's last upload and Offline progress runs from that save's `last_saved_utc`.
- **AC-18 (UI)**: Screenshot of the conflict screen in vi and en, both sides filled, recommended side marked, on a 1080×2400 Android screen with the Free banner visible — no clipped text.
- **AC-19 (UI)**: Screenshot of Settings → Account & backup in each of: Guest, Linked, not backed up, Blocked, pending conflict.
- **AC-20 (Game Feel)**: **GIVEN** a 2 MiB blob, **WHEN** an upload and its hashing run during play on the min-spec Android device, **THEN** no frame exceeds the frame budget by more than 5 ms attributable to the service (profiler capture retained).

Coverage gaps the QA lens found and accepted: R13's guest sign-out warning and R16's toggle are covered only by AC-19 screenshots; the provider-already-linked edge case needs a real backend (add to AC-15–17 suite when the backend exists).

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **PROVISIONAL: Local save (6)** — assumes it exposes: completed-save bytes plus a header with `schema_version`, `sim_version`, `guild_uid` (stable id created with the guild), `tick`, `last_saved_utc` and the summary fields (guild name, level, member count, highest member level, rebirth count); a "save completed" signal; `store_kept_backup(label)` that does not consume normal rotating generations; `write_current_from_blob(blob)` with migration; atomic writes. `sync_meta` lives beside the save, not inside it. | Local save GDD author | When 6 is designed (MVP) |
| OQ-2 | GDD §20 S8 says the reference conflict simulation takes "the latest by `updated_at`". This GDD orders by server revision and recommends by progress since base (R6, F4) because device clocks cannot order saves. Update S8's description to simulate R6/F3/F4? | User / Dev tooling (43) | Before S8 is built |
| OQ-3 | Expected compressed save size at late game (10 schools, many members, history log) — confirms `cloud_blob_max_bytes` and F6. | Local save + Event bus (history log bound) | Vertical Slice |
| OQ-4 | Guest orphan cleanup and retention period; privacy policy text for guest accounts and backup retention (§14). | User (legal) | Before Alpha store submission |
| OQ-5 | Scope: GDD §11.2 suggests "more cloud save slots" as a Premium feature. Not designed here (systems index: one slot). Add later as an entitlement-gated extension? | User | Post Wave 1 |
| OQ-6 | Backend plan limits and pricing (Supabase or other) for the F6 traffic estimate; not sourceable from the repo. Also verify Supabase anonymous sign-in and identity linking in the P1 spike (§12.1). | User / P1 spike | P1 spike |
| OQ-7 | **PROVISIONAL: Leaderboards (35)** — assumes 35 decides whether guests may rank, and that it resists save rollback (restore previous backup, keeping an older device in a conflict) without help from this system. | Leaderboards GDD author | When 35 is designed |
| OQ-8 | Add the `cloud_*` and `guest_orphan_retention_days` keys to `data/config.csv`, or keep service settings in a separate services config? (Data layer owns the file.) | Data layer owner | Before implementation |
| OQ-9 | **PROVISIONAL: In-app purchases (34) / Entitlement (32)** — assumes consumable balances (Thiên Cơ Kính stock) are a server-side record keyed by `account_id`, not only in the save blob (R17), and that offline spending of a consumable is 34's design. | IAP / Entitlement GDD authors | When 32/34 are designed |
| OQ-10 | **PROVISIONAL: PC/Steam identity** — §11.1 says Steam shares the cloud account. Steam is not a standard Supabase auth provider; assumes an Edge Function that exchanges a Steam session ticket. Verify before the PC port. | User / P1-equivalent spike for PC | Before PC port (phase 6) |
| OQ-11 | Token storage on device (no Godot keychain API): plain `user://` file vs a platform plugin (Android Keystore, iOS Keychain). | ADR (security) | Before implementation |
| OQ-12 | Store policy wording on in-app account deletion (Apple, Google Play) — verify current text; this GDD assumes it is mandatory (R15). | User | Before store submission |
| OQ-13 | **PROVISIONAL: Offline progress (31)** — assumes it reads `server_utc_estimate()` and owns the trust decision; and that after an adopt it treats the adopted save like a cold start from that save's `last_saved_utc` (possibly another device's clock). | Offline progress GDD author | When 31 is designed |

**Engine feasibility note.** Domain: Core (Persistence). There is no `docs/engine-reference/godot/modules/core.md`, so feasibility was **not checked against the pinned engine** for file, threading or crypto APIs. `modules/networking.md` lists no 4.7 networking changes; `breaking-changes.md` notes `FileAccess.store_*` now return `bool` (relevant to Local save, not here). Platform sign-in plugins (Google, Apple, Steam) are unverified on Godot 4.7 — the P1 spike's job (§12.1, §3.1 risks). No ADRs exist yet.
