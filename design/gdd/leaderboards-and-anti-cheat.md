# Leaderboards and Anti-cheat

> **Status**: Designed (pending independent /design-review)
> **Author**: user + Claude (autonomous batch run, decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet). Serves the locked GDD §1 promise "bảng xếp hạng bang hội + thành viên" (guild and member leaderboards), §8.1 (signed summary + seed, growth-vs-playtime check, Free and Premium share boards) and §13 ("chống gian lận bảng xếp hạng → chấp nhận mức vừa đủ": moderate anti-cheat is accepted).

## Summary

Leaderboards and anti-cheat ranks guilds and members on shared seasonal boards and decides which entries are trustworthy enough to show. The client sends its guild's history in small signed segments (the player's commands and the time gaps, not the results); the server checks every segment against the real time that has passed, and replays the ones that matter (the top of each board, a random sample and anything suspicious) with the same deterministic core, deriving the ranked numbers itself. It exists because GDD §1 locks guild and member leaderboards, and a board in an offline-first game is worthless unless edited saves and sped-up clients cannot top it.

> **Quick reference** — Layer: `Feature` · Priority: `Alpha` · Key deps: `Sim core and tick loop (1)`, `Command layer (5)`, `Deterministic RNG (2)`, `Data layer (3)`, `Local save and migration (6)`, `Account and cloud save (7)`, `CA/PA and traits (9)`, `Offline progress (31)`

## Overview

Leaderboards and anti-cheat is a host-level service (GDD §3.2 `[Services]`: "Leaderboard") with a server half. It owns five things. **(1) The ranked log:** a save section holding the host commands and time entries the Sim core logs (Sim core R6) since the last segment the server acknowledged; it is the "checkpoint-and-truncate" scheme Sim core OQ-10 assigns here. **(2) Segments:** the signed summary of GDD §8.1, a contiguous slice of that log plus the state hash at its end, the versions that produced it and the values the client claims. **(3) Intake checks (Tier 1):** cheap checks on every segment at the moment it arrives, chiefly that the guild has not done more simulated work than real time allows (F1), the growth-versus-playtime check §8.1 asks for. **(4) Replay verification (Tier 2):** an asynchronous verifier that replays pending segments from the last server-verified checkpoint with the core at the segment's `sim_version` (Sim core R16, Command layer R9), compares the end state hash, and computes every ranked value from its own replayed state. **(5) Boards:** one guild board and three member boards (CA, level, Golden Boss kills), all seasonal, shared by Free and Premium players. The player meets the system as a "Rankings" screen and a small badge on their own guild ("verified" or "checking"). The simulation never knows it exists: it registers no tick phase and emits no events, exactly as Account and cloud save R1 is outside the simulation. Without it the §1 leaderboards could not ship honestly, because the local save's checksum detects damage, not tampering (Local save R3), and every value on a phone can be edited.

## Player Fantasy

**"The rank is real."** This is an indirect fantasy (Meta category): the player does not enjoy the verifier; they enjoy what it makes true. *The moment:* after three weeks the player's guild climbs into the top 50 of the guild board, and beside it sits a small seal — *verified*. They scroll up to the guild at number 1 and see the same seal. Neither of them got there by editing a file or running the clock forward; both got there by recruiting, gearing and sending members to the right grounds. The seal is the whole fantasy: a stranger's rank means the same thing as mine.

Candidate framings considered (lens: creative direction, applied without a pillars file): (A) "The rank is real" — chosen; anchored to §8.1 ("chống gian lận mức vừa đủ") and §1 (shared boards). It asks the rest of the design for a replay that derives the numbers itself and a top of board that is verified-only. (B) "Our name on the wall" — guild pride and recognition; rejected as the anchor because the pride belongs to the guild loop (§1), which this system only displays, and because seasonal rewards that would feed it are out of scope (Open Questions). (C) "A fair race for everyone" — Free and Premium on one board; folded into A, since §8.1 already locks shared boards and the offline-cap difference is a design question recorded in Open Questions, not a fantasy.

What this asks of the design: the top of every board must never show an unverified entry (R9); a player who did nothing wrong must never be punished by a verifier bug without a recovery path (R11); and the system must cost the honest player nothing they can feel (no blocking network calls, no extra waits).

## Detailed Design

### Core Rules

Specialist lenses applied (Section 6 routing, `Meta` → row "Foundation/Infrastructure"; `systems-designer` primary, `gameplay-programmer` and `engine-programmer` supporting):
- **systems-designer:** trust must come from replay, never from the signature; the signature only binds a payload to an account. Every check must have an explicit outcome state (accepted, rejected with a reason, or not yet assessed), and "not yet replayed" must never display as "verified". The tick budget must be cumulative, or a player could mint one offline cap per segment.
- **gameplay-programmer:** the client side must cost nothing in a frame: the log is packed integers appended between ticks, submission is a background HTTP call, and nothing waits on the network. The log must be bounded.
- **engine-programmer:** the server cannot run GDScript inside a Supabase Edge Function; replay needs a separate worker running a core of the exact `sim_version` (the Python reference `sim/` or a headless engine export — an ADR). Old `sim_version` cores must be kept for as long as unverified segments exist for them.
- **Conflict surfaced:** GDD §8.1 names an Edge Function as the anti-cheat; the engine-programmer view is that a full replay does not fit one. Resolved (autonomous, logged): the Edge Function does Tier 1 intake only; Tier 2 runs in a separate worker (R7, Open Questions OQ-1).

**R1 — Outside the simulation.** This system is a host-level service. It registers no tick phase, emits no Event-bus events, writes no simulation state and is never called from inside a tick. Its only presence in the save is one section, `ranked_log` (R3), which it registers with Local save (6) like any feature section. It reads committed state between ticks only, to compute the claimed values of a segment (R5).

**R2 — Ranked entities.** Two kinds of entity can rank:
- **The guild:** one per account. The ranked guild is the guild in the account's single cloud slot (Account and cloud save, one slot per account). A player who starts a new guild on the same account ends the old guild's chain (R10) and enrols the new one.
- **Members:** every active roster member of a ranked guild, identified by `(account_id, member_uid)`. Members who have left the guild and Elders (Rebirth and Ascension 23) do not rank on member boards and do not count toward the guild board. At most `member_board_per_guild_max` (5) members of one guild appear on any one member board; the guild's best five by that board's key.

Guest accounts may rank (Account R3 gives a guest a real `account_id`). Every entry is chain-verified, so creating many guest accounts gains nothing.

**R3 — The ranked log (save section `ranked_log`).** The Sim core appends every applied command and every `handoff`/`skip` time entry to its command log (Sim core R6). This system keeps, in its save section:
- `entries`: the **host-origin** command envelopes with their `seq` and applying tick, and every time entry, in append order, since `ack_boundary`. Sim-origin entries are not kept, because replay regenerates them (Command layer R9).
- `ack_boundary`: `{tick, state_hash, seg_index}` of the last segment the server acknowledged (received and passed Tier 1), or the genesis boundary (R4) before the first ack.
- `unranked_reason`: absent, or one reason code from R12 that ends ranking for this guild on this device.
- Entries before `ack_boundary` are deleted when the server acknowledges a segment. All 64-bit values are strings in JSON (Sim core R6).
- The log is capped at `ranked_log_max_entries` (100,000). If an append would exceed it, the log is cleared, `unranked_reason = log_overflow` is set, and no further entries are kept for this guild (R12). At a few hundred host commands per day of play this is weeks of play without network.

**R4 — Genesis.** A guild's chain starts at its creation. The genesis boundary is `{tick: 0, state_hash: H(new_guild(world_seed, content_hash, sim_version)), seg_index: 0}`. The server can reproduce the genesis state from those three values alone, because new-guild creation is deterministic from `world_seed` (RNG R2). A save that existed before this system was in its build has no log from tick 0 and can never rank (`unranked_reason = no_genesis`); this only affects pre-release saves.

**R5 — Segments (the signed summary of §8.1).** A segment is a contiguous slice of `entries` plus:
- `account_id`, `save_id` (Local save R13), `seg_index` (previous + 1), `start` boundary (must equal the client's `ack_boundary`), `end_tick`, `end_state_hash` (F2's hash of committed state at `end_tick`).
- `sim_version`, `content_hash`, `phase_table_hash`, `resolver_version`, `command_table_hash` — one value each for the whole segment.
- `world_seed` (segment 0 only; later segments inherit it from the chain).
- `worked_ticks`: ticks the guild actually simulated in the segment, i.e. foreground ticks plus the credited window `c` of each offline hand-off (Offline progress R4), excluding frozen ticks `u`.
- `claims`: the ranked values the client computes from its committed state at `end_tick`, for display before replay: guild level, top-10 CA sum, and per active member `{member_uid, school, level, rebirth, ca, season_boss_kills}`.
- `client_flags`: `clock_skew_flag` from Offline progress (R3.5), and whether any `dev_only` command was applied.
- `signature`: an authentication tag over the canonical payload with a key the server issued to this account at enrolment (algorithm and key handling: ADR). It proves the payload came from the account's session and was not altered in transit. **It is not evidence of a fair run;** a device-held key can be extracted.

A segment **closes** at the first of: a submission (R6); a change of `sim_version`, `content_hash`, `phase_table_hash` or `resolver_version` on load (one entry in Local save's `lineage`, R13), so one segment always replays with one core; or `segment_max_entries` (20,000) entries. Closed, unsent segments queue in the save in order.

**R6 — Submission.** While online and the account has a session, the client submits all closed segments in order, then closes and submits the open one, every `submit_interval_min` (30) minutes and when the app is backgrounded. Submission is a background HTTP request through `CloudService` (§8.1); it never blocks a frame, a save or a tick. A failed request is retried at the next interval. The server's acknowledgement moves `ack_boundary` and truncates the log (R3).

**R7 — Tier 1: intake checks (every segment, synchronous, server side).** In this order, first failure wins; a failure rejects the segment with a reason code (R12) and is final for that segment:
1. **Authentication:** valid session for `account_id`; valid `signature`.
2. **Structure:** schema valid; every 64-bit field a decimal string; no float anywhere; a `handoff` is always followed by its `skip` before the next command or the segment end; `entries` in non-decreasing tick order with host `seq` strictly increasing.
3. **Known build:** `sim_version` and the other hashes are a released combination the server holds a replay core for (R8). An unknown combination is `unknown_build`, not a cheat.
4. **Chain:** `start` equals a boundary the server holds for this guild (R10); `seg_index` follows it.
5. **No dev commands:** `client_flags` reports none, and no entry has a `dev_only` type (Command layer R13). A dev command means the guild never ranks (Command layer OQ-5).
6. **Store grants:** every `grant_store_item`/`revoke_store_item` entry carries a `grant_ref` the In-app purchases ledger issued to this account (In-app purchases OQ-8). Lenses cannot change a ranked value (CA/PA AC-24), so this is hygiene.
7. **Time budget (F1):** the chain's cumulative `worked_ticks` up to `end_tick` must not exceed what real server time allows. This is §8.1's "ngưỡng tăng trưởng hợp lý theo thời gian chơi".
8. **Claim bounds (F3):** each claim is within its absolute bound: level ≤ the level cap of its rebirth tier (Rebirth and Ascension 23), CA ≤ the CA ceiling (CA/PA 9), Golden Boss kills ≤ F3.

A segment that passes is **acknowledged** (state `Plausible`). Its claims become **provisional** entries on the boards (R9).

**R8 — Tier 2: replay verification (asynchronous worker).** The verifier keeps, per guild, the last **verified checkpoint**: the full committed state it produced itself at a segment boundary, starting from genesis (R4). To verify, it:
1. Loads the checkpoint state into a core of the next pending segment's `sim_version`. If that version differs from the checkpoint's, it first migrates the state with that build's Local save migration, exactly as the client did on load.
2. Walks the segment's entries in append order: runs ticks with `run_ticks` up to each entry, re-submits host commands by `seq` through `submit_replay` (Command layer R9), and at each `handoff` calls `inject_handoff`, then `skip_ticks(k, resolver_version)` with the logged credited window `c` (Sim core R6, R8; Offline progress OQ-2).
3. A `submit_replay` that returns a different `seq` than the logged one, any core failure (Sim core R10), or an end state hash that differs from `end_state_hash` is a **divergence** (R11).
4. On a match the segment is `Verified`, the checkpoint advances, and the verifier computes every ranked value from **its own** replayed state and the events it saw during replay (for boss kills, F4). Those values replace the provisional claims. The claims are never used again.
5. Pending segments of one guild are verified in `seg_index` order; a guild's later segment is never verified before an earlier one.

The server keeps a replay core for every released `sim_version` while any unverified segment needs it.

**R9 — Who gets replayed, and what is shown.** Replay capacity is finite, so the verifier takes guilds in this priority order (ties: oldest pending segment first):
1. Any guild whose provisional entry would place in the top `verify_top_n` (100) of any board.
2. Any guild with a Tier 1 soft flag: `clock_skew_flag` set, or F1 slack below `budget_tight_ratio` (10 %).
3. A random `verify_sample_rate` (5 %) of all other acknowledged segments, drawn by the server.
4. Everything else, when capacity is idle.

**Display rule:** the top `verify_top_n` positions of every board show **verified entries only**. A provisional entry that would rank there is shown at its provisional rank to its own player only, marked "checking", and to everyone else it appears below position `verify_top_n` until it is verified. Below that line, provisional entries are shown to everyone with a "checking" mark. A verified entry shows a seal.

**R10 — The chain and forks.** The server holds, per guild, the ordered list of acknowledged boundaries for the last `fork_window_days` (30) days, plus the verified checkpoint. A segment may start at **any** held boundary, not only the newest. This happens when the player restores an older cloud backup or keeps an older device's save in a conflict (Account and cloud save, Edge Cases). Then every acknowledged segment after that boundary becomes `Superseded`, its provisional and verified values are withdrawn, and the guild's entry falls back to the values at that boundary until the new segment is processed. A rollback therefore never gains rank; with fixed dice (RNG R12, the attempt-ordinal rule) it cannot re-roll an outcome either. A segment starting at a boundary the server no longer holds is rejected `chain_broken`. Starting a new guild on the account (new `save_id` at genesis) ends the old chain: its entries leave the boards.

**R11 — Divergence.** A diverged segment is never shown. The guild's entries are withdrawn and the guild becomes `Unranked(diverged)` for the rest of the current season and every later season, because the server can no longer reach the client's state. Divergence has two causes the server cannot tell apart: a modified client, and a parity bug between the client's core and the server's. So the player is never told they cheated; the screen says "Your ranking could not be verified" (UI Requirements). Every divergence is recorded with the first diverging tick and `seq` for the developer. When the developer confirms a parity bug, an admin action re-verifies that guild's pending segments with the fixed core for the same `sim_version` (a server-side rebuild, not a version bump) and, on a match, restores the guild to `Ranked`.

**R12 — Reason codes.** Rejections and unranked states carry one integer code, shown to the player as words through Localization (4). 3501 `auth_failed`, 3502 `malformed`, 3503 `unknown_build`, 3504 `chain_broken`, 3505 `dev_command`, 3506 `grant_unissued`, 3507 `time_budget`, 3508 `claim_out_of_bounds`, 3509 `diverged`, 3510 `log_overflow`, 3511 `no_genesis`, 3512 `opted_out`. `unknown_build` and network errors are retried (the player may simply need to update); every other rejection is final for that segment. 3504, 3505, 3509, 3510 and 3511 make the guild unranked (R13).

**R13 — Seasons.** All four boards are seasonal. Season `s` covers server UTC `[epoch + s·L, epoch + (s+1)·L)` with `L = season_length_days` (28) (F5). A guild appears on a season's boards once it has an acknowledged segment received in that season. Stock values (guild level, CA, level) are the values at the guild's newest acknowledged or verified boundary. The flow value (Golden Boss kills) counts kills inside segments **received** in the season, whole segment to one season (F4). At a season's end its standings are frozen and archived as final, using verified values only; provisional entries that were never verified are left out of the archive. There are no season rewards (Open Questions OQ-6).

**R14 — Board keys.** Ordering per board, highest first, each with a final tie-break of "verified earlier":
- **Guild board:** `guild_level` (Guild and buildings R9), then `guild_power` (F6). GDD §8.1 names fame ("danh vọng"); fame has no owner yet (Guild and buildings OQ-6), so it is not a key. When an owner defines it, fame becomes the first key from the next season.
- **Member CA board:** `ca` (CA/PA 9), then `level`.
- **Member level board:** `rebirth` (Rebirth and Ascension 23), then `level`, then `ca`.
- **Member Golden Boss board:** season Golden Boss kills (F4), then `level`.

Free and Premium accounts share every board (§8.1), and both get the same offline cap (Offline R4, user decision 2026-11-16): Premium is convenience only, so no entitlement buys worked ticks on a ranked board.

**R15 — Names on boards.** Boards carry IDs and numbers only (Localization R1); display text is drawn on the device. The guild name is player text and is the one exception: the server stores it, and runs it through a server-side word filter before showing it to others. A name that fails, or that other players report `name_report_threshold` (3) times, is shown to others as "Guild #[short id]" until the player renames it. Member names are generated proper nouns (Localization R8) and are shown as they are. Length and character rules for the name entry belong to Guild screens (39) (Localization OQ-9).

**R16 — Opting out.** Settings (45) has a "Show my guild on leaderboards" toggle, on by default. Off: the client stops submitting, the server withdraws the guild's entries (`opted_out`), and the ranked log keeps growing locally so the player can opt back in without losing the chain, until `ranked_log_max_entries`. Account deletion (Account R15) deletes the guild's chain, checkpoints and entries.

### States and Transitions

**Segment states (server):**

| State | Entered when | Leaves to |
|---|---|---|
| `Received` | Request arrives | `Rejected` (Tier 1 fails) · `Plausible` (Tier 1 passes; acknowledged) |
| `Rejected` | Any R7 check fails | — (final; the reason is returned to the client) |
| `Plausible` | Tier 1 passed | `Verified` (replay matches) · `Diverged` (replay mismatch) · `Superseded` (a fork starts at an earlier boundary, R10) |
| `Verified` | Replay matched | `Superseded` (fork, R10) |
| `Diverged` | Replay mismatch | `Verified` (admin re-verify after a confirmed parity bug, R11) |
| `Superseded` | Fork | — (final) |

**Guild ranking states (server, mirrored on the client from responses):**

| State | Meaning | Transitions |
|---|---|---|
| `NotEnrolled` | No acknowledged segment yet | → `Pending` on the first acknowledged segment |
| `Pending` | Has `Plausible` segments not yet replayed; entries provisional | → `Verified` when every acknowledged segment is verified · → `Unranked` on 3504/3505/3509/3510/3511 · → `OptedOut` |
| `Verified` | Every acknowledged segment verified; entries sealed | → `Pending` on a new acknowledged segment · → `Unranked` · → `OptedOut` |
| `Unranked(reason)` | Never ranks again with this guild (R11, R12) | → `Verified` only by admin re-verify after a parity bug (R11) |
| `OptedOut` | Player turned the toggle off (R16) | → `Pending` when the toggle is turned on and a segment is acknowledged |

A segment rejected with `unknown_build`, `auth_failed`, `grant_unissued`, `time_budget`, `claim_out_of_bounds` or `malformed` changes the guild state by nothing except that its entry stays at the last acknowledged values. `time_budget` and `claim_out_of_bounds` rejections also queue the guild for priority replay (R9 class 2) of what it already has.

The client never shows a rank it computed itself; it shows the server's state and rank from its last response.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Sim core and tick loop (1) | in (client), both (server) | Command log entries and `handoff`/`skip` time entries (R6, R8); `sim_version` (R12); `world_seed`, `tick` | Server uses `run_ticks`, `submit_replay` via Command layer, `inject_handoff`, `skip_ticks` (R16) | Sim core owns the log and replay primitives; this system owns the driver, the log size bound, the segment format and the unranked rule (Sim core R6, OQ-10) |
| Command layer (5) | both | `origin` on each envelope; `dev_only` flag; `command_table_hash` | Re-submits host entries by `seq` (R9); `seq` mismatch = divergence | Command layer owns the envelope and the replay rule; this system owns the divergence policy |
| Deterministic RNG (2) | in | `world_seed`; R12 replay guarantee | — | RNG |
| Data layer (3) | in | `content_hash` (F1) per segment | Server holds the matching content per released build | Data layer |
| Local save and migration (6) | both | Section registration; `save_id`, `lineage` (R13); migration for version changes in replay | `ranked_log` section | Local save owns the contract; this system owns the section |
| Account and cloud save (7) | in | `account_id`, session token, account state; account deletion | Guest ranking allowed (R2) | Account for identity |
| CA/PA and traits (9) | in | Deterministic `ca`; CA ceiling | — | CA/PA |
| Guild and buildings (30) | in | `guild_level` | — | Guild and buildings |
| Rebirth and Ascension (23) | in | `rebirth`, level cap per tier, Elder status | — | Rebirth |
| Golden Boss and guild raid (14) | in (server replay) | Events 1403 `gb_won`, 1408 `gb_member_rewarded` seen during replay | Season boss kills (F4) | Golden Boss |
| Offline progress (31) | in | `clock_skew_flag`; replayable resolver; credited window `c` in the `skip` entry | Priority replay for flagged guilds | Offline progress owns the flag; this system owns its consequence (R9 class 2) |
| In-app purchases (34) | in | Server-side ledger of issued `grant_ref`s | Rejects unissued refs (R7.6) | IAP |
| Dev tooling and parity harness (43) | in | Golden vectors proving the server's core matches the client's per `sim_version` | Divergence reports (first tick, `seq`) | Dev tooling owns the proof; this system owns the replay |
| Localization (4) | in | Reason code and board text | IDs and numbers only (R15) | Localization |
| Settings (45) | in | Opt-out toggle (R16) | — | Settings (no GDD yet) |
| Guild screens (39) | out | — | Rankings screen data, guild badge state | Guild screens own layout |
| Endless Tower (19) | in (Wave 2) | `best_floor` | A future tower board | Out of scope until Wave 2 (Open Questions OQ-8) |
| Arena (18) | none | — | Arena ranks stay local (GDD §6 "Lôi Đài … chỉ cục bộ") | — |

## Formulas

Specialist lens applied: systems-designer, Section D checks (boundaries at 0, minimum and maximum worked for each formula below).

### F1 — Time budget (`time_budget_ok`)

The time_budget_ok formula is defined as:

`time_budget_ok = W_total ≤ (T_recv − T_0) · r + cap_s · r + slack_s · r`

where `W_total = Σ worked_ticks` over the chain from genesis to this segment's `end_tick`, and `T_0 = T_account − enroll_grace_s`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| W_total | int | 0 – 2^62 | calculated | Cumulative worked ticks (foreground + credited offline `c`) on the chain up to this segment |
| T_recv | int | Unix seconds | calculated (server clock) | Server receipt time of this segment |
| T_account | int | Unix seconds | calculated (server) | Server creation time of the account (Account R3) |
| enroll_grace_s | int | 0 – 60 days | data file (`config.csv`, `lb_enroll_grace_days` × 86,400) | Allowance for offline play before the first network contact (default 14 days) |
| r | int | 10 | constant (`tick_rate`, Sim core) | Ticks per second |
| cap_s | int | 43,200 (12 h) at default | data file (`offline_cap_free_h` × 3,600, Offline progress) | The one offline cap, the same for every account (Offline R4; user decision 2026-11-16 removed the 8 h / 24 h Free/Premium split); Offline R3 lets a clock change borrow at most one cap |
| slack_s | int | 0 – 3,600 | data file (`config.csv`, `lb_budget_slack_s`) | Upload latency and clock jitter (default 600) |

**Output Range:** boolean. With default values a guild 30 days after account creation may claim up to (30 + 14) days + 12 h + 10 min of worked ticks ≈ 38.5 M ticks. At `W_total = 0` it always passes. At `T_recv = T_0` it allows exactly one cap plus slack. A worked-tick count cannot exceed real time by more than one cap plus grace over the whole chain, so a speed-hacked or clock-shifted client is bounded; the bound is cumulative so it cannot be renewed per segment.
**Example:** account created 1 Nov 00:00; segment received 3 Nov 00:00 (any entitlement). Allowed = (2 d + 14 d) · 864,000 + 12 · 36,000 + 6,000 = 13,824,000 + 432,000 + 6,000 = 14,262,000 ticks. A chain claiming 14,300,000 is rejected `time_budget`.
**Soft flag:** `slack_ratio = 1 − W_total / allowed`. Below `budget_tight_ratio` (0.10) the guild is queued for priority replay (R9 class 2). An honest guild that plays constantly reaches about `enroll_grace` worth of headroom, so the flag fires mostly for guilds near the bound.

### F2 — End state hash (`end_state_hash`)

The end_state_hash formula is defined as:

`end_state_hash = SHA-256(canonical_sim_state(end_tick))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| canonical_sim_state | bytes | — | calculated | The save payload's simulation sections (Sim core R14 fields and every feature section) serialised canonically (sorted keys, R5 value encoding), **excluding** host-only metadata: `last_saved_utc`, `sync_meta`, `ranked_log` itself and any device preference |
| end_tick | int | 0 – 2^62 | calculated | Committed tick at the segment end |

**Output Range:** 32 bytes, stored as 64 lowercase hex characters. Equal states give equal hashes in both implementations; any differing simulation value changes it.
**Example:** a guild at tick 1,204,500 hashes its state; the server replays to tick 1,204,500 and hashes its own; equal → `Verified`.
Local save's checksum (Local save F1) covers the whole payload including host metadata, so it cannot serve here (Open Questions OQ-3).

### F3 — Claim bounds (`claim_ok`)

The claim_ok formula is defined as:

`claim_ok = level ≤ level_cap(rebirth) ∧ ca ≤ ca_max ∧ boss_kills ≤ floor(W_seg / (gb_interval_min · 60 · r)) + gb_backlog_max`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| level_cap(rebirth) | int | per tier | data file (Rebirth and Ascension 23) | Level cap of the member's rebirth tier |
| ca_max | int | — | data file (CA/PA 9) | Highest CA the formula can produce |
| boss_kills | int | 0 – … | claim | Golden Boss kills the member claims in segments of this season |
| W_seg | int | 0 – 2^62 | calculated | Worked ticks in this season's acknowledged segments |
| gb_interval_min | int | 60 | data file (`golden_boss_interval_min`, Golden Boss) | Minutes between boss slots |
| gb_backlog_max | int | 3 | data file (Offline progress, backlogged bosses) | Bosses that may resolve at once after an absence |

**Output Range:** boolean. At `W_seg = 0` up to 3 kills pass (the backlog). One worked day (864,000 ticks) allows 24 + 3 = 27 kills. A claim breaking any bound is rejected `claim_out_of_bounds`; it cannot be honest, so the guild also goes to priority replay.
**Example:** a member claims 30 kills after 864,000 worked ticks in the season → bound is 27 → rejected.

### F4 — Season Golden Boss kills (`season_boss_kills`)

The season_boss_kills formula is defined as:

`season_boss_kills(m, s) = |{ slot : member m has a 1408 gb_member_rewarded event in slot, slot ended with 1403 gb_won, the slot's segment was received in season s }|`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| m | id | member uid | calculated | The member |
| s | int | 0 – … | calculated (F5) | Season |
| 1403, 1408 | event types | — | Golden Boss R17 | Win and per-participant reward events, observed by the verifier during replay |

**Output Range:** 0 to F3's bound. A participant in a lost raid scores 0 for that slot. Counted only from replay, so a provisional entry shows the claim and a verified entry shows this value.
**Example:** in season 3 a member fought 40 raids, won 31; the verifier counts 31.

### F5 — Season index (`season_id`)

The season_id formula is defined as:

`season_id = floor((T_recv − season_epoch) / (season_length_days · 86,400))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| T_recv | int | Unix seconds | calculated (server clock) | Segment receipt time |
| season_epoch | int | Unix seconds | data file (server config, `lb_season_epoch`) | Start of season 0, a Monday 00:00 UTC chosen at launch |
| season_length_days | int | 7 – 90 | data file (server config, `lb_season_length_days`) | Season length (default 28) |

**Output Range:** 0 and up; negative before the epoch, which the server never accepts (entries before launch are test data). Server time only; the device clock plays no part.
**Example:** epoch Mon 5 Jan 2027 00:00 UTC, length 28 days, receipt 2 Mar 2027 → day 56 → season 2.

### F6 — Guild power (`guild_power`)

The guild_power formula is defined as:

`guild_power = Σ_{i=1..min(K, n)} ca_(i)`, members sorted by `ca` descending.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| ca_(i) | int | CA range | calculated (CA/PA 9) | CA of the i-th strongest active member (Elders excluded) |
| K | int | 1 – 40 | data file (server config, `lb_guild_power_top_k`) | Members counted (default 10) |
| n | int | 0 – `member_cap` | calculated | Active roster size |

**Output Range:** 0 (no members) to `K · ca_max`. Counting only the top K rewards a strong core over a large roster, so a guild cannot climb by hiring weak members. At `n < K` it sums all members.
**Example:** a guild of 14 with top-10 CAs summing to 1,240 has `guild_power` 1,240.

### F7 — Replay cost estimate (`replay_cost_s`)

The replay_cost_s formula is defined as:

`replay_cost_s = fg_ticks · c_tick + n_skip · c_skip`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| fg_ticks | int | 0 – 864,000 per day | calculated | Foreground (tick-exact) ticks in the segments |
| c_tick | float (s) | ~0.0005 – 0.005 | constant (to measure) | Server cost of one tick at max roster |
| n_skip | int | 0 – … | calculated | Offline hand-offs |
| c_skip | float (s) | to measure | constant (to measure) | Server cost of one aggregate resolution (Offline progress F3/F4) |

**Output Range:** planning value only; not used by any rule. **Example:** a player with 2 h of foreground play a day and 2 absences: 72,000 · 0.001 + 2 · 0.5 ≈ 73 s of worker CPU per day. Replaying every guild would cost about that per daily player; R9's priority order replays the top boards, flagged guilds and a 5 % sample, which bounds cost by board size rather than player count. `c_tick` and `c_skip` are NOT SOURCEABLE until the P1 spike measures them (Open Questions OQ-1).

## Edge Cases

Specialist lens applied: systems-designer, Section E checks on C and D (zero, maximum, simultaneous events, degenerate strategies).

- **If the player is offline for weeks and the log reaches `ranked_log_max_entries`**: the log is cleared and the guild is `Unranked(log_overflow)` permanently; the player is told on next network contact. Honest players reach this only after weeks of heavy play with no network at all.
- **If a `handoff` is logged with no `skip` in a submitted segment**: rejected `malformed`. A save is never taken while a hand-off is pending (Sim core R14), so a correct client cannot produce this.
- **If the app crashes mid-resolution of an absence**: the log in the save ends before the hand-off (the save predates it), and the next start re-measures the absence with the same keys (Offline progress R16). The resubmitted log is the same as if the crash never happened.
- **If the player restores an older cloud backup**: the next segment starts at an older held boundary; later segments are `Superseded` (R10). The board falls back to the older values. No rank is gained.
- **If two devices play the same guild at once and both submit**: whichever segment arrives second starts at the same boundary as the first; it is accepted as a fork and supersedes the first. Each device's chain is still bounded by F1, so alternating devices gains nothing.
- **If a guild's start boundary is older than `fork_window_days`**: rejected `chain_broken`; the guild is unranked.
- **If the player updates the app mid-season** (new `sim_version`): the segment closes at the lineage change (R5); the server replays the earlier segment with the old core and the later one with the new core after migrating the checkpoint (R8.1).
- **If the server no longer holds a core for a segment's version** (should not happen while segments are pending): the segment stays `Plausible` and is never shown in the top `verify_top_n`; an alert fires for the developer. Never treated as verified.
- **If the player has not updated and their build is retired** (`unknown_build`): segments are retried; entries stay at their last values. The Rankings screen says an update is needed to keep ranking.
- **If a speed hack runs the client faster than real time**: F1 rejects once cumulative worked ticks exceed real time plus one cap plus grace. Below the bound the guild only did work it could have done honestly in that time.
- **If a modified client alters results** (more gold per kill, a guaranteed drop): the commands replay on the server's unmodified core, the end hash differs, `Diverged` (R11).
- **If a modified client sends honest logs but inflated claims**: F3 rejects impossible claims; the rest show as provisional and are replaced by the verifier's values; claims never reach the top `verify_top_n` (R9).
- **If an auto-clicker or macro plays the game**: accepted. Its commands are real commands replayed on the server. The game is idle by design.
- **Seed shopping** (RNG OQ-2): a player creates guilds until one starts lucky. Accepted: one ranked guild per account, a new guild ends the old chain (R10), and the edge is early-game only. Not mitigated further (GDD §13 "mức vừa đủ").
- **"Burning a bad roll" in enhancement** (Enhancement OQ-5): accepted. Reloading costs real time, which F1 already counts, and the verifier replays the outcome faithfully. No ranked-play mitigation.
- **If a parity bug makes honest guilds diverge**: they are unranked and recorded (R11). Many divergences at the same `sim_version` and first-diverging handler point to a bug; the developer fixes the server core, re-verifies, and the guilds return. The player was never accused.
- **If a guild sits exactly on a season boundary**: the segment counts for the season it was received in (F5). A player who holds a segment back to the next season moves those boss kills, at the cost of not ranking with them now. Accepted.
- **If two entries tie on every key**: the one verified earlier ranks higher; a provisional entry ranks below verified entries with the same keys.
- **If the guild has 0 active members**: it still ranks on the guild board by `guild_level` with `guild_power = 0`.
- **If the account is deleted**: chain, checkpoints and entries are deleted (R16); archived season standings replace the guild with "Deleted guild".
- **If the player toggles opt-out off and on**: the chain continues from the client's `ack_boundary` (R16); nothing is lost unless the log overflowed meanwhile.
- **If a guild name is offensive**: the server filter or reports hide it to others (R15).

## Dependencies

| System | Direction | Hard/Soft | Interface | Status |
|---|---|---|---|---|
| Sim core and tick loop (1) | Upstream | Hard | Command log with `handoff`/`skip`, `run_ticks`, `inject_handoff`, `skip_ticks`, `sim_version`, `world_seed` | Needs Revision |
| Command layer (5) | Upstream | Hard | `origin`, `submit_replay`, R9 replay rule, `dev_only` flag, `command_table_hash` | Designed |
| Deterministic RNG (2) | Upstream | Hard | `world_seed`; same draws on every machine (R12) | Needs Revision |
| Data layer and content pipeline (3) | Upstream | Hard | `content_hash` per segment; content per released build | Designed |
| Local save and migration (6) | Upstream | Hard | Section registration for `ranked_log`; `save_id`; `lineage`; migration for replay; a canonical sim-state digest (F2, PROVISIONAL) | Designed |
| Account and cloud save (7) | Upstream | Hard | `account_id`, session, account creation time, deletion | Designed |
| CA/PA and traits (9) | Upstream | Hard | Deterministic `ca`, `ca_max` | Designed |
| Offline progress (31) | Upstream | Soft | `clock_skew_flag`, credited window `c` in `skip`, offline caps | Designed |
| Guild and buildings (30) | Upstream | Soft | `guild_level`, `member_cap` | Designed |
| Rebirth and Ascension (23) | Upstream | Soft | `rebirth`, level cap per tier, Elder flag | Designed |
| Golden Boss and guild raid (14) | Upstream | Soft | Events 1403, 1408; `golden_boss_interval_min` | Designed |
| In-app purchases (34) | Upstream | Soft | Issued `grant_ref` ledger | Designed |
| Dev tooling and parity harness (43) | Upstream | Soft (for trust) | Golden vectors per `sim_version` | Designed |
| Localization (4) | Upstream | Soft | Reason-code text, board text | Designed |
| Settings (45) | Upstream | Soft | Opt-out toggle | No GDD (PROVISIONAL) |
| Guild screens (39) | Downstream | Soft | Rankings screen, guild badge | No GDD |
| Endless Tower (19) | Upstream | Soft (Wave 2) | `best_floor` | Designed; board deferred |

The systems index lists Sim core, RNG, Local save, Account and cloud save, CA/PA and traits and Data layer; Command layer (5) and Offline progress (31) are added because replay and the time budget cannot be specified without them.

Bidirectional check: Sim core, Command layer, RNG, Data layer, Local save, Account, CA/PA, Offline progress, IAP, Rebirth, Endless Tower, Enhancement and Dev tooling already list this system. Golden Boss (14) and Guild and buildings (30) do not list Leaderboards as a dependent; recorded for the consistency pass (Open Questions OQ-9).

## Tuning Knobs

Specialist lens applied: systems-designer, Section G (knobs derived from the `data file` variables of Section D, plus rule constants).

| Knob | Default | Safe range | Too low | Too high | Interacts with |
|---|---|---|---|---|---|
| `lb_enroll_grace_days` | 14 | 0 – 60 | Offline-first players whose first network contact is late are rejected `time_budget` | Pre-account speed hacks get more room | F1 |
| `lb_budget_slack_s` | 600 | 60 – 3,600 | Honest guilds fail on upload latency | Small extra room for speed hacks | F1 |
| `lb_budget_tight_ratio` | 0.10 | 0.0 – 0.5 | Fewer near-bound guilds are prioritised | Priority queue fills with honest heavy players | R9 class 2 |
| `lb_verify_top_n` | 100 | 10 – 1,000 | Little of each board is verified-only | Replay cost grows; more honest entries wait as "checking" | R9, F7 |
| `lb_verify_sample_rate` | 0.05 | 0 – 1 | Cheaters below the top are rarely caught | Cost approaches replaying everyone (F7) | F7 |
| `lb_submit_interval_min` | 30 | 5 – 240 | More requests and segments | Longer "checking" delay; larger logs | `ranked_log_max_entries` |
| `ranked_log_max_entries` | 100,000 | 10,000 – 500,000 | Offline players overflow sooner | Save grows (packed ints) | Local save size |
| `lb_segment_max_entries` | 20,000 | 1,000 – 100,000 | Many small segments | Longer single replay jobs | F7 |
| `lb_fork_window_days` | 30 | 1 – 90 | Restoring a slightly old backup breaks the chain | Server stores more boundaries | R10 |
| `lb_season_length_days` | 28 | 7 – 90 | Boards reset before guilds can climb | Stale boards; late joiners discouraged | F5 |
| `lb_guild_power_top_k` | 10 | 1 – 40 | One star member decides the guild board | Roster size dominates | F6 |
| `member_board_per_guild_max` | 5 | 1 – 40 | Strong guilds show only their best | One guild floods a member board | R2 |
| `name_report_threshold` | 3 | 1 – 20 | Griefers hide innocent names | Offensive names stay up longer | R15 |

`offline_cap_free_h` (Offline progress; the single cap, `offline_cap_premium_h` is deprecated), `tick_rate` (Sim core), `golden_boss_interval_min` (Golden Boss) and the backlog of 3 feed F1 and F3 and are owned by those GDDs; they are not duplicated here. Server-side knobs live in the server's config; client-side ones (`submit_interval`, the two entry caps) in `config.csv` (new keys, Open Questions OQ-4).

## Visual/Audio Requirements

Optional for `Meta`. Brief requirements only; no art bible exists yet.
- **Verified seal:** a small stamp-like seal glyph beside a verified entry; **checking:** a neutral hourglass glyph. Both have a text label for screen readers and are never distinguished by colour alone.
- **Own entry** is highlighted with a frame, not only a colour.
- **Rank change** since the last visit: an up/down arrow with the number of places; no sound.
- **Unranked notice:** plain text, no alarm sound, no red "cheater" styling (R11).
- Season end: a short banner when the player opens Rankings after a season closes, showing their final standing; one soft chime (Audio 40).

## Game Feel

Optional for `Meta`. One target: **no cost to the honest player.** Opening Rankings shows the last cached board at once and refreshes in the background; submission never adds a frame of latency or delays a save (R6); the "checking" mark resolves without player action.

## UI Requirements

- **Rankings screen** (owned by Guild screens 39): tabs for Guild, Member CA, Member level, Golden Boss; season selector (current and archived); 50 entries per page; a "my position" jump; each row shows rank, guild name (or "Guild #id", R15), the board's values, and the seal or checking mark.
- **Guild badge** on the guild header: "Verified", "Checking", "Not ranked: [reason]" (R12), or nothing when opted out.
- **Unranked explanation** sheet: plain words per reason code, never accusing ("could not be verified", "update the game to keep ranking", "the guild's history is incomplete").
- **Settings toggle** "Show my guild on leaderboards" (Settings 45, R16).
- **Report name** action on another guild's row (R15).
- All text through Localization; numbers formatted per locale.

📌 **UX Flag — Leaderboards and anti-cheat**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the Rankings screen and guild badge **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD | Other GDD | Their section | Nature |
|---|---|---|---|
| R3, R8, OQ-10 answer | `sim-core-and-tick-loop.md` | R6, R8, R16, OQ-10 | Owns the driver, log bound, unranked rule (assigned to this system) |
| R3, R8 | `command-layer.md` | R9, R13, OQ-5 | Replay rule; dev commands never rank |
| Edge Cases (seed shopping) | `deterministic-rng.md` | R2, R12, OQ-2 | Seed shopping accepted with one ranked guild per account |
| R5, R7.3 | `data-layer-and-content-pipeline.md` | F1, `live_wave` row | Boards are **not** split by `content_hash`; each segment replays with its own content. Data layer's tuning-knob text speaks of "every leaderboard bucket keyed by that hash" — soft wording conflict (OQ-9) |
| R1, R3, R5, F2 | `local-save-and-migration.md` | R3, R13, OQ-3 | `lineage` used only to close segments; the 256 cap is sufficient because replay never reads old lineage |
| R2, R10 | `account-and-cloud-save.md` | R3, R15, Edge Cases, OQ-7 | Guests may rank; rollback resistance via R10 |
| R14, F6 | `ca-pa-and-traits.md` | `ca`, AC-24 | Deterministic CA |
| R9, F1 | `offline-progress.md` | R3, R4, R17, OQ-2 | `clock_skew_flag` → priority replay only; `c` logged in `skip` |
| R7.6 | `in-app-purchases.md` | OQ-8 | Unissued `grant_ref` rejected |
| R2, R14 | `rebirth-and-ascension.md` | OQ-12 | Elders excluded from member boards |
| F3, F4 | `golden-boss-and-guild-raid.md` | R17 | Events 1403, 1408 |
| R14 | `guild-and-buildings.md` | R9, OQ-6 | `guild_level`; fame unowned |
| Edge Cases | `equipment-enhancement.md` | OQ-5 | No ranked mitigation |
| R15 | `localization.md` | R1, R8, OQ-9 | IDs only; guild name filter here, length rules in 39 |
| R8 | `dev-tooling-and-parity-harness.md` | R7, R14 | Golden vectors as server-core proof |
| OQ-8 | `endless-tower.md` | `best_floor` | Future board |

## Acceptance Criteria

Specialist lens applied: qa-lead (coverage of every rule and formula, measurable THEN, boundary values, cross-system). Story types: [Logic] automated unit test; [Integration] automated multi-system test; [UI] screenshot.

- **AC-1 [Logic] (R3)**: **GIVEN** a 1-hour `run_ticks` with a script of 50 host commands and AI activity, **WHEN** the `ranked_log` section is read, **THEN** it holds exactly the 50 host entries and the time entries, and no sim-origin entry.
- **AC-2 [Logic] (R3)**: **GIVEN** a log at `ranked_log_max_entries − 1`, **WHEN** two more host commands apply, **THEN** the log is empty and `unranked_reason = 3510`, and no further entries are appended.
- **AC-3 [Logic] (R4, F2)**: **GIVEN** `world_seed` S, content C and `sim_version` V, **WHEN** the genesis hash is computed on the client and in the server core, **THEN** both equal.
- **AC-4 [Logic] (R5)**: **GIVEN** an open segment, **WHEN** the save is loaded by a build with a different `sim_version`, **THEN** a segment closes at the restored tick and the next segment carries the new version; no segment mixes two versions.
- **AC-5 [Integration] (R6)**: **GIVEN** the network is down, **WHEN** the app runs 2 h and is backgrounded, **THEN** no frame exceeds the Sim core frame budget because of submission, segments queue in the save, and they are submitted in order on reconnect.
- **AC-6 [Integration] (R7.1–R7.4)**: **GIVEN** one valid segment, **WHEN** copies are sent with a bad signature, a float in an arg, an unreleased `sim_version`, and a `start` that matches no held boundary, **THEN** they are rejected 3501, 3502, 3503 and 3504 respectively, and the valid one is acknowledged.
- **AC-7 [Integration] (R7.5)**: **GIVEN** a dev build log with one applied `dev_only` grant-gold command, **WHEN** submitted, **THEN** rejected 3505 and the guild is `Unranked(dev_command)`.
- **AC-8 [Integration] (R7.6)**: **GIVEN** a `grant_store_item` entry with a `grant_ref` the IAP ledger never issued to this account, **WHEN** submitted, **THEN** rejected 3506.
- **AC-9 [Logic] (F1)**: **GIVEN** the F1 example (account 1 Nov, receipt 3 Nov, Free), **WHEN** `W_total` is 14,118,000, **THEN** accepted; **WHEN** 14,118,001, **THEN** rejected 3507. **GIVEN** `W_total = 0`, **THEN** accepted.
- **AC-10 [Integration] (F1, speed hack)**: **GIVEN** a test client that runs ticks at 3× real time for 48 real hours from account creation with `enroll_grace` 0, **WHEN** it submits every 30 min, **THEN** the first segment whose cumulative worked ticks exceed the bound is rejected 3507, and none before it is.
- **AC-11 [Logic] (F3)**: **GIVEN** 864,000 worked season ticks, **WHEN** a member claims 27 kills, **THEN** accepted; **WHEN** 28, **THEN** rejected 3508. **GIVEN** 0 worked ticks, **THEN** 3 kills accepted and 4 rejected.
- **AC-12 [Integration] (R8)**: **GIVEN** a 1,000,000-tick honest run with 300 host commands and two offline hand-offs, **WHEN** the verifier replays its segments from genesis, **THEN** every segment is `Verified`, the end hash matches, and verified values equal the client's claims.
- **AC-13 [Integration] (R8, R11)**: **GIVEN** the same run on a client whose gold-per-kill is altered by 1 %, **WHEN** replayed, **THEN** the first segment containing a kill is `Diverged`, the guild is `Unranked(diverged)`, its entries are withdrawn, and the record names the first diverging tick.
- **AC-14 [Integration] (R8.1)**: **GIVEN** a chain whose segment 3 is at `sim_version` 1 and segment 4 at 2, **WHEN** replayed, **THEN** segment 4 is replayed after migrating the checkpoint with version 2's migration and verifies.
- **AC-15 [Integration] (R8.5)**: **GIVEN** segments 5 and 6 pending, **WHEN** the verifier is asked to verify 6 first, **THEN** it verifies 5 first.
- **AC-16 [Integration] (R9)**: **GIVEN** a board of 200 verified entries and a new provisional entry whose claims would rank 10th, **WHEN** another player views the board, **THEN** positions 1–100 hold only verified entries and the new entry appears after position 100 with a checking mark; **WHEN** its owner views it, **THEN** they see it at 10 marked checking.
- **AC-17 [Integration] (R9)**: **GIVEN** a guild with `clock_skew_flag` set and 1,000 unflagged guilds pending, **WHEN** the verifier picks its next job, **THEN** it picks the flagged guild before any unflagged guild outside the top 100.
- **AC-18 [Integration] (R10)**: **GIVEN** a chain with acknowledged segments 1–4, **WHEN** a segment starting at the end of segment 2 arrives, **THEN** segments 3–4 are `Superseded`, the guild's entries show segment 2's values, and the new segment is processed. **GIVEN** a start boundary older than `fork_window_days`, **THEN** rejected 3504.
- **AC-19 [Integration] (R10)**: **GIVEN** a ranked guild, **WHEN** the player starts a new guild on the same account and it submits its genesis segment, **THEN** the old guild's entries leave every board.
- **AC-20 [Logic] (R12)**: **GIVEN** each of the 12 reason codes, **WHEN** rendered in vi and en, **THEN** each has text in both and none contains the word for "cheat".
- **AC-21 [Logic] (R13, F5)**: **GIVEN** epoch Mon 5 Jan 2027 00:00 UTC and 28 days, **WHEN** receipts are at 1 Feb 2027 23:59:59 and 2 Feb 2027 00:00:00, **THEN** seasons are 0 and 1.
- **AC-22 [Integration] (R13)**: **GIVEN** a season whose board holds verified entries and one guild that is still provisional when the season ends, **WHEN** the season closes, **THEN** the archive contains only verified entries and is unchanged by later submissions.
- **AC-23 [Logic] (R14, F6)**: **GIVEN** two guilds with `guild_level` 5, top-10 CA sums 1,240 and 1,239, **WHEN** ranked, **THEN** the 1,240 guild is above; **GIVEN** equal keys, **THEN** the earlier-verified guild is above. **GIVEN** a guild with 0 members, **THEN** `guild_power = 0` and it is ranked by level.
- **AC-24 [Integration] (R2)**: **GIVEN** a guild with 12 members above every other guild's members in CA, **WHEN** the CA board is built, **THEN** exactly 5 of them appear, the guild's top 5, and no Elder appears.
- **AC-25 [Integration] (F4)**: **GIVEN** a replayed segment with 10 Golden Boss slots, 7 won and 3 lost, and a member in all 10, **WHEN** the verifier counts, **THEN** that member's season kills increase by 7.
- **AC-26 [Logic] (R14, Free/Premium)**: **GIVEN** a Free and a Premium guild, **WHEN** the board is queried, **THEN** both appear on the same board with no entitlement field in the response.
- **AC-26b [Logic] (F1, equal cap)**: **GIVEN** two chains identical except that one account is Premium, **WHEN** F1 is evaluated, **THEN** `cap_s` and the allowed budget are identical (14,262,000 ticks in the F1 example) and no entitlement lookup is made.
- **AC-27 [Integration] (R15)**: **GIVEN** a guild name on the server filter list, **WHEN** another player views the board, **THEN** it shows "Guild #[id]"; the owner sees their own name. **GIVEN** 3 reports from distinct accounts, **THEN** the same.
- **AC-28 [Integration] (R16)**: **GIVEN** a ranked guild, **WHEN** the toggle is turned off, **THEN** within one request its entries are withdrawn and no submission is sent; **WHEN** turned on after 2 days, **THEN** the queued segments are submitted from the old `ack_boundary` and accepted.
- **AC-29 [Integration] (R1)**: **GIVEN** a 100,000-tick run with this system active and one with it removed, same seed and commands, **THEN** every simulation section of the save other than `ranked_log` is identical.
- **AC-30 [Integration] (Edge Cases, crash)**: **GIVEN** a crash injected during an offline resolution, **WHEN** the app restarts and resolves the absence again and submits, **THEN** the segment verifies.
- **AC-31 [UI] (UI Requirements)**: screenshots in `production/qa/evidence/` of the Rankings screen (each tab, a verified and a checking row, own row highlighted) and of the guild badge in each state, in vi and en.
- **AC-32 [Performance] (F7)**: **GIVEN** the max-roster fixture, **WHEN** the server core replays 36,000 ticks, **THEN** the measured `c_tick` is recorded and the per-player daily cost is computed; the result sets `lb_verify_top_n` and `lb_verify_sample_rate` (OQ-1). NOT ASSESSED until the server core exists.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Server replay runtime and cost.** Which core runs on the server: the Python reference `sim/` at the tag of each `sim_version` (requires every feature to exist in the reference, which today covers only part of the game, systems index §"Python reference") or a headless engine export? Where does it run (GDD §8.1 names Edge Functions; a full replay likely exceeds their limits — NOT SOURCEABLE, no Supabase reference under `docs/engine-reference/`)? Measure `c_tick` and `c_skip` (F7, AC-32). → becomes an ADR. | technical-director | Before Alpha implementation |
| OQ-2 | Signature algorithm and key issue/rotation for R5 (HMAC with a per-account key over TLS assumed). → ADR. | security-engineer | Alpha |
| OQ-3 | **PROVISIONAL: Local save and migration (6)** — assumes it can expose a canonical sim-state digest (F2) that excludes host metadata (`last_saved_utc`, `sync_meta`, `ranked_log`), identical in both implementations. Its F1 checksum covers the whole payload and cannot serve. | Local save (6) | Next Local save revision |
| OQ-4 | **PROVISIONAL: Data layer (3)** — new `config.csv` keys `lb_submit_interval_min`, `ranked_log_max_entries`, `lb_segment_max_entries` (client side). Server-side knobs live in server config. | Data layer (3) | When implemented |
| OQ-5 | **Partly RESOLVED (consistency-check 2026-11-16):** Sim core R6 now logs `offline_credit {at_tick, c}` before each `skip`, so `worked_ticks` = foreground ticks + Σc is readable from the log; the `new_guild(...)` determinism point stays open. Original: **Sim core (1) / Offline progress (31)** — the `skip` log entry (or a companion entry) records the credited window `c` (Offline progress OQ-2); `new_guild(world_seed, content, sim_version)` is deterministic (R4); the client can read `worked_ticks` (foreground ticks + Σc) for each segment. | Sim core (1) | Next Sim core revision |
| OQ-6 | **Scope (not decided here):** season rewards (titles, cosmetics). GDD §8.1 says "theo mùa" but names no rewards; adding them is a scope change. | Producer / creative-director | Before Alpha |
| OQ-7 | **RESOLVED (user decision 2026-11-16):** equal offline cap for ranked play — 12 h for every player; Premium gets convenience only, no extra offline time (Offline R4). F1's `cap_s` is one value for all accounts. Original: Premium's 24 h cap vs Free's 8 h gave Premium more worked ticks on shared boards (§8.1, §11.2). | — | Closed |
| OQ-8 | Endless Tower (19, Wave 2) `best_floor` board, gated by `content_wave`. Deferred with Wave 2. | Leaderboards (35) | Wave 2 |
| OQ-9 | Consistency pass: Golden Boss (14) and Guild and buildings (30) should list this system as a soft dependent; Data layer's `live_wave` row speaks of leaderboard buckets keyed by content hash, but boards are not split by content (R7.3, Cross-References). | consistency-check | Next `/consistency-check` |
| OQ-10 | **Fame** (`Guild.fame`, §4.1) has no owner (Guild and buildings OQ-6). When an owner exists, the guild board's first key becomes fame from the next season (R14). | Producer / systems index | Before Recruitment revision |
| OQ-11 | **RESOLVED (user decision 2026-11-16):** moot — F1's `cap_s` no longer depends on entitlement, so the server needs no "ever Premium" answer. | — | Closed |
| OQ-12 | **PROVISIONAL: Settings (45)** — hosts the "Show my guild on leaderboards" toggle (R16). | Settings (45) | When 45 is designed |
| OQ-13 | A growth envelope from the balance simulator (per-hour p99.9 level and CA gain for the fastest policy) would let Tier 1 reject more impossible claims before replay. It needs a new data table, which is a schema change not made here. | Dev tooling (43) / Data layer (3) | Post-launch, if provisional cheating is seen below the top 100 |
| OQ-14 | Privacy policy (§14) must cover public guild names and member names on boards and the retention of command logs on the server. | Producer / legal | Before Alpha |
| OQ-15 | `log_overflow` and `diverged` are permanent for a guild. Is a "re-enrol with a fresh unverified chain" path (rank allowed only after a long verified probation) worth its complexity? Not needed for launch. | Leaderboards (35) | After launch, if support tickets show it |

*Post-design note:* CD-GDD-ALIGN was applied as a checklist against GDD §1, §8.1, §11.2 and §13 and this GDD's Player Fantasy, but without a pillars file, concept or brief the verdict is recorded as NOT ASSESSED (consistent with sibling GDDs). One finding for the creative director regardless: OQ-7 (offline-cap advantage on shared boards) touches §11.2 and is left open, not resolved.
