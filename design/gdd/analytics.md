# Analytics

> **Status**: Designed (pending independent /design-review)
> **Author**: user + Claude (autonomous batch run, decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against; checked informally against GDD §1, §11.2 and §14 instead (see the note at the end of Open Questions)
> **Implements Pillar**: None (no game-pillars.md yet). Serves GDD §3.2 `[Services] … Analytics`, §14 "Chính sách quyền riêng tư + điều khoản (có cloud save, quảng cáo, analytics)" and the §12.2/§15 need to tune pacing and economy (§4.3, §19.5) against real play, not only the simulator.

## Summary

Analytics is a privacy-first, consent-gated telemetry service that tells the solo developer how real players move through the game: how long they stay, where they stop, whether the pacing of §4.3 and the gold sinks of §19 hold up outside the balance simulator, and whether Premium and rewarded ads behave as §11 intends. It watches a short allowlist of simulation events through one passive Event-bus subscription plus a few host signals, rolls high-frequency events into per-session counters, and uploads small batches to the project's Supabase backend. It never changes the game: it holds no simulation state, is not in the save, and a player who declines consent plays exactly the same game.

> **Quick reference** — Layer: `Polish` · Priority: `Alpha` · Key deps: `Event bus and history log (42)`, `Settings (45, consent key)`; soft: `Ads (33)`, `Account and cloud save (7)`, `In-app purchases (34)`, `Entitlement (32)`, `Onboarding (44)`, `Localization (4)`, `Data layer (3)`

## Overview

Analytics (37) is a host-level service in the GDD §3.2 `[Services]` layer, in the same position as Account and cloud save (7) and In-app purchases (34): outside the deterministic simulation, free to use engine time and engine randomness, never called from inside a tick except through one narrow door. That door is a single Event-bus subscriber, the **tap** (`owner_id = "analytics"`, order 3700), which copies records of allowlisted event types into a host-side queue and does nothing else — it never emits, never submits a command, never calls `ctx.fail`, and keeps nothing the simulation reads (Event bus R4–R6; the bus GDD lists Analytics as "the stream, as a pure observer"). Everything else — consent, the pseudonymous install ID, session tracking, rollup counters, the on-disk outbound queue and the upload to a Supabase Edge Function (§8.1) — runs on the host, between ticks.

The system owns: the **analytics event vocabulary** (which bus types and host signals are collected, and how — raw, count or sum), the **analytics record schema**, the **consent gate** as applied to telemetry, the **install ID**, **session** boundaries, the **local queue**, the **upload policy**, and the **KPI definitions** the backend computes. It does not own the privacy notice (Ads 33 R3) or the preferences store and Settings screen (45) that hold and show its consent choice, the backend dashboards (an ADR and tooling concern), or any game rule.

Players feel it only as one line in the first-launch privacy prompt and one toggle in Settings. The developer feels it as the difference between guessing and knowing why day-2 players leave. Implementation choices — the Edge Function layout, table schema and retention jobs on Supabase, queue file format, compression — become ADRs.

*Framing: technical (Meta category, recommended option); no ADR exists yet, so none is cited.*

## Player Fantasy

**"The game respects me: it asks first, takes nothing personal, and never slows me down."** This is an indirect fantasy (Meta category). Players do not enjoy telemetry; they enjoy a game that keeps getting better tuned and never treats them as a product. The moment: on first launch the privacy prompt says, in the player's language, that anonymous play statistics help a one-person studio balance the game, with *Allow* and *No thanks* given equal weight. A player who taps *No thanks* never sees the question again unless they open Settings, and nothing about their guild, rewards or ads changes.

Three promises the rules must keep:

- **Asked, not assumed.** Nothing is recorded, queued or sent before the player says yes (R2).
- **Anonymous by construction.** No name, account, guild name, member name, free text, contact detail or advertising ID is ever in a record (R3, R4). Localization R1 already keeps text out of events; this system keeps identity out too.
- **Invisible in play.** No spinner, no frame hitch, no battery drain worth noticing; analytics failing or offline is never visible (R9, F5).

*`creative-director` lens applied in this run (no agent spawned). No pillars exist; the framing was anchored to GDD §11.2 ("không bán sức mạnh", no interstitials — a player-respecting monetization stance) and §14. The alternative "the developer's eyes on the world" was rejected as a developer fantasy, not a player one.*

## Detailed Design

> Specialist lenses applied (SKILL §6 routing; `Meta` → Foundation/Infrastructure row): **systems-designer** (primary), **gameplay-programmer** and **engine-programmer** (supporting). Points are folded into the rules.
> - systems-designer: the tap sits on the P6 hot path; listing many types raises `k̄` in Event bus F1 for every listed type, so the allowlist must stay narrow and high-volume types must be aggregated, not forwarded raw. Analytics must be removable without changing a single simulation output.
> - gameplay-programmer: analytics must never become a hidden dependency of gameplay (no "if analytics enabled" branches in features); the tap only ever reads its batch. Headless runs (balance simulator, leaderboard verifier, parity harness) simply do not register it.
> - engine-programmer: HTTP upload uses Godot's `HTTPRequest`/`HTTPClient` from the host on the main thread or a worker, never inside a tick; there is no `core.md` engine reference for this domain under `docs/engine-reference/godot/modules/`, so feasibility is **not checked against the pinned engine** — verify in the P1 spike alongside the Supabase REST call (§12.1 item 5).

### Core Rules

**R1 — Outside the simulation, one passive tap.** Analytics registers no tick phase, owns no Event-bus type block, and emits no events. Its only simulation contact is `subscribe("analytics", order = 3700, allowlisted_type_ids, tap)` at boot (Event bus R4). The tap, for each record in its batch, looks up the type's collection mode (R5) and either appends the record to the host-side **pending buffer** or adds to a session counter. It returns. It never calls `ctx.emit`, `ctx.submit` or `ctx.fail`, never queries history, and never reads another system's state. Its pending buffer and counters are host memory, are not part of any simulation snapshot or save, and are never read by a handler. Removing the subscription changes no simulation output, hash or save byte (AC-1).
- The tap is registered **only** by the interactive game host. The balance simulator, leaderboard verifier, parity harness and any headless run never register it, so it takes no subscriber slot there.
- If consent is not `granted` (R2) at boot, the tap is not registered at all.
- *Subscriber order 3700 follows the "block = system number × 100" convention. It is not the highest order in use (Member state machine 4100 and Onboarding 4400 subscribe later); that is harmless, because the tap reads only the delivered batch, which no subscriber can change (consistency-check 2026-11-16: corrected "highest order in use").*

**R2 — Consent gate.** Analytics has three consent states: `unasked`, `granted`, `declined` (States below). Analytics owns this value; it is independent of ad consent, which the UMP SDK holds for Ads (33 R4). It is stored as one key, `analytics_consent`, in the Settings (45) preferences store (PROVISIONAL, OQ-1). Ads R3's privacy notice is informational, not consent, so it does not grant analytics consent; this answers Ads OQ-4. The opt-in choice (UI Requirements) is shown immediately after the R3 notice, before any analytics call.
- Only `granted` collects. In `unasked` and `declined` nothing is recorded, nothing is queued, the install ID is not created, and no network call is made.
- The default is `unasked`, and `unasked` behaves exactly like `declined`. There is no implied consent, no region-based default and no "legitimate interest" path in Alpha.
- Changing to `declined` at any time (Settings toggle) immediately unsubscribes nothing mid-run (bus tables are frozen) but sets the tap's `active` flag false so it drops every record, deletes the on-disk queue, clears counters and deletes the install ID (R3). The next boot does not register the tap.
- Changing to `granted` takes effect at the next session start (R6); the tap is registered at the next boot. Until then host signals are collected but sim events are not.

**R3 — Pseudonymous install ID.** On the first `granted` session the host creates `analytics_id`: a random 128-bit value (engine randomness is allowed here, R1) stored in a small analytics file beside, not inside, the save. It is never derived from, joined to or sent with `account_id`, device IDs, the advertising ID or `guild_uid`. It is regenerated after any `declined`, after *Reset analytics ID* in Settings, and after uninstall. Different devices of one player are different analytics users; this is accepted.

**R4 — Record schema.** Every uploaded record is a flat object of IDs and integers:

| Field | Type | Notes |
|---|---|---|
| `aid` | string (32 hex) | `analytics_id` (R3) |
| `sid` | int | Session ordinal on this install, starting at 1 |
| `seq` | int | Record ordinal within the session, for de-duplication (R8) |
| `ev` | string `[a-z0-9_]`, ≤ 32 | Analytics event key (R5); never free text |
| `t_ms` | int | Milliseconds since session start (engine monotonic time) |
| `p` | up to 4 ints | Payload: the bus record's `a–d`, or the signal's fields, unchanged |
| `cu` | 0/1 | 1 if the source tick ran while `catching_up` (Sim core R15) |

Each batch carries one header, not repeated per record: `app_version`, `sim_version`, `content_wave`, `platform` (`android`/`ios`/`steam`/`web`), `locale` (Localization 4: the code only), `tier` (`free`/`premium`, from Entitlement 32's `premium` entitlement at session start), `utc_day` of the batch (the calendar date, no time). Wall-clock timestamps are not sent per record; the backend stamps receipt time.
- **Forbidden in any field:** display strings, player or guild names, member names, account or store IDs, email, IP-derived location beyond the backend's country lookup (OQ-4), advertising ID, purchase receipts or order IDs, prices in local currency. Product IDs and the Entitlement tier are allowed.
- Payload ints are copied, not interpreted. Their meaning is the emitter GDD's, keyed by `sim_version`.

**R5 — Collection modes and the allowlist.** Each collected source has one mode:
- **`raw`** — one record per occurrence. For rare, high-signal events (milestone-class).
- **`count`** — a per-session counter per `ev`, incremented per occurrence, uploaded once in the session summary (R6).
- **`sum`** — like `count`, plus a per-session sum of one named payload slot (`sum_slot` 1–4).

The allowlist maps a source (bus `type_id`, or host signal name) to `{ev, mode, sum_slot}`. Initial allowlist (event IDs from the emitter GDDs and the registry; names in brackets are those GDDs'):

| Source | `ev` | Mode | Why |
|---|---|---|---|
| 1101 [`hunt_trip_started`] (Zones 11) | `hunt_trip` | count | Activity level |
| 1403 / 1404 / 1405 [`gb_won`/`gb_lost`/`gb_skipped`] (Golden Boss 14) | `boss_won` / `boss_lost` / `boss_skipped` | raw | Core hourly beat; time-to-first-win |
| 1406 [`gb_backlog_resolved`] (14) | `boss_backlog` | count | Offline backlog use |
| 1502 / 1504 [`candidate_accepted`/`candidate_rejected`] (Recruitment 15) | `recruit_hire` / `recruit_reject` | raw / count | Roster growth |
| 1604 [`member_leaving`] (Retention 16, VS) | `member_left` | raw | Churn of members — a retention KPI for the *game's* tuning |
| 2101 [`skill_level_up`] (Skills 21) | `skill_up` | count | Progress rate |
| 2301 / 2302 [`member_reborn`/`member_ascended`] (Rebirth 23) | `rebirth` / `ascend` | raw | Long-tail reach (§6.10) |
| 2401 / 2402 [`enhance_succeeded`/`enhance_failed`] (Enhancement 24) | `enhance_ok` / `enhance_fail` | count | Sink engagement (§19.3) |
| 2601 [`loot_handed_in`] (Items 26) | `loot_in` | count | Loop throughput |
| 2701 [`member_paid`] (Gold economy 27) | `gold_tax_in` | sum, slot 3 (tax) | Live §19.5 out/in ratio, inflow |
| 2702 [`shop_sale`] (27) | `gold_shop_in` | sum, slot 4 (fund part) | Inflow |
| 2703 [`fund_spent`] (27) | `gold_spent` | sum, slot 2 (amount) | Outflow |
| 2802 [`craft_unit_done`] (Crafting 28, VS) | `craft_unit` | count | Feature use |
| 3101 [`offline_resolved`] (Offline 31) | `offline_return` | raw | Absence length and return rate |
| Host: `session_start` / `session_end` (this system, R6) | same | raw | Sessions and retention |
| Host: IAP R13 `purchase_state_changed(product_id, state)` (34) | `iap_state` | raw | Funnel; product ID and state only |
| Host: Account `sync_state_changed` / `conflict_detected` (7) | `cloud_sync` / `cloud_conflict` | count / raw | Cloud reliability |
| Host: Ads R12 `banner_state_changed(state)` / `rewarded_state_changed(state)` / `ad_watch_credited(quest_id, watch_id)` (33) | `ad_banner` / `ad_rewarded_state` / `ad_watch` | count / count / raw (`quest_id` only) | Opt-in rate (§11.4) |
| Host: Ads R12 `consent_state_changed(state, personalised)` (33) | `ad_consent` | raw | Ad-consent mix (ints only) |
| 3201 / 3202 / 3203 [`entitlement_changed`/`trial_started`/`trial_ended`] (Entitlement 32) | `entitlement` / `trial_start` / `trial_end` | raw / raw / count | Premium conversion and trial value (§11.5 "dùng thử có giới hạn") |
| Host: onboarding step completed (Onboarding 44, PROVISIONAL) | `onb_step` | raw | Tutorial funnel |

- Adding, removing or changing a row is a data change, not a code change, and does not change `sim_version` (the bus does not hash subscribers). Where the allowlist is stored is open (OQ-2).
- A bus type that is not registered at `seal()` cannot be subscribed (Event bus R4 boot error). The analytics host therefore **filters its subscription list to types registered in this build** before calling `subscribe`, and logs (not fails) any allowlist row it dropped, so Wave-gated or not-yet-built emitters never break boot.
- Per-member detail is not collected: payload slots holding a member ID are copied as-is (member IDs are per-save integers with no meaning outside the save), but no per-member profile is built.

**R6 — Sessions.** A session starts when the app reaches the foreground with consent `granted` and ends when it goes to the background for longer than `session_gap_s` or quits. A return within `session_gap_s` continues the same session.
- `session_start` (raw) carries `p = [offline_s_bucket, 0, 0, 0]` where the bucket is F1 of the real time since the last session end.
- `session_end` (raw) carries `p = [duration_s, ticks_run, catchup_ticks, 0]`, followed by the session **summary**: one record per non-zero `count`/`sum` counter, `ev = <key>`, `p = [count, sum_low, sum_high, 0]` (sum split into two 31-bit halves, F2).
- If the app is killed without a background callback, the summary is written at the next launch from the persisted counters (counters are flushed to the analytics file at each background, R7).

**R7 — Local queue.** Records go to an in-memory pending buffer, then to an append-only on-disk queue at each upload attempt and at each background. The queue holds at most `queue_cap_records`; on overflow the **oldest raw records are dropped first**, session summaries last, and a `queue_dropped` counter records how many (uploaded with the next summary). The queue file is separate from the save, never synced by cloud save, and deleted on `declined` (R2).

**R8 — Upload.** The host uploads the queue to the `analytics_ingest` Supabase Edge Function (§8.1) as one compressed batch of at most `batch_max_records`, when F3 says flush. It is never called inside a tick and never blocks a frame.
- A `2xx` response deletes the sent records. Any other response or a timeout keeps them and retries per F4.
- The backend de-duplicates on `(aid, sid, seq)`, so a resend after a lost response is harmless.
- No upload on a metered connection when the OS reports data saver (Android `isActiveNetworkMetered` + Data Saver), except session summaries (small).
- The ingest endpoint takes an anonymous project key only; it is rate-limited per `aid` server-side (ADR). Records are untrusted input: the server validates schema, `ev` against the published allowlist, and field ranges, and drops the batch on failure.

**R9 — Failure is silent.** No analytics error is ever shown to the player, logged as a game error, or allowed to affect play. A full queue, a dead network, a server error or a malformed allowlist row only reduces what is collected. The one exception is development builds, where the host prints analytics warnings to the debug console.

**R10 — KPIs (backend definitions).** The backend computes, per `app_version` and `platform`:
- **Retention** D1 / D7 / D30: share of `aid`s whose first `session_start` is on day 0 and who have a `session_start` on day N (F6).
- **Session length** median and p90 of `session_end.p[0]`.
- **First-hour funnel**: time from first `session_start` to first `boss_won`, first `recruit_hire`, and each `onb_step`.
- **Economy health**: per `aid`-day, `gold_spent / (gold_tax_in + gold_shop_in)` against the §19.5 target of 60–90% (F7).
- **Pacing**: distribution of days to first `rebirth` against §4.3.
- **Monetization**: share of `aid`s with `tier = premium`; `ad_rewarded` per Free DAU; IAP funnel by `iap_state`.
- **Reliability**: `cloud_conflict` per 1,000 sessions; `queue_dropped` totals.
KPI dashboards, retention windows and alert thresholds are tooling, not game rules, and live outside this GDD (ADR).

### States and Transitions

Consent state (per install):

| State | Collects? | Install ID | Tap registered at boot? |
|---|---|---|---|
| `unasked` | No | None | No |
| `granted` | Yes | Exists | Yes |
| `declined` | No | Deleted | No |

| From | To | Trigger | Effect |
|---|---|---|---|
| `unasked` | `granted` | Player taps *Allow* on the analytics opt-in screen (after Ads R3 notice) | ID created; host signals collected now; sim events from next boot |
| `unasked` | `declined` | *No thanks* | Nothing stored |
| `granted` | `declined` | Settings toggle off | Tap goes inactive at once; queue, counters, ID deleted |
| `declined` | `granted` | Settings toggle on | New ID; as `unasked → granted` |
| `granted` | `granted` | *Reset analytics ID* | Queue and counters deleted, new ID, new session ordinal 1 |

Upload state (host, per attempt): `Idle → Sending → Idle` (2xx) or `Sending → Backoff → Idle` (error/timeout, F4). Only one batch is in flight.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Event bus and history log (42) | bus → this | Per-tick batches of allowlisted types via `subscribe("analytics", 3700, …)` | Nothing | Bus owns delivery; this system owns the tap |
| Sim core (1) | core → this | `catching_up`, ticks run (R15 facade, read between ticks) | Nothing | Sim core |
| Ads (33) | 33 → this | R3 notice shown (gate for the opt-in screen); R12 host signals | Nothing | Ads |
| Settings (45) | 45 → this | Preferences-store key `analytics_consent`; toggle and *Reset ID* rows | Nothing | Settings owns the store and screen; this system owns the key's meaning (PROVISIONAL) |
| Entitlement (32) | 32 → this | `premium` at session start; events 3201–3203 via the bus | Nothing | Entitlement |
| In-app purchases (34) | 34 → this | R13 host signals | Nothing | IAP |
| Account and cloud save (7) | 7 → this | `sync_state_changed`, `conflict_detected` host signals (never `account_id`) | Nothing | Account |
| Onboarding (44) | 44 → this | Step-completed signal (PROVISIONAL) | Nothing | Onboarding |
| Localization (4) | 4 → this | Active locale code | Nothing | Localization |
| Data layer (3) | 3 → this | Allowlist and knobs (OQ-2) | Nothing | Data layer |
| Emitter GDDs (11, 14, 15, 16, 21, 23, 24, 26, 27, 28, 31) | via bus | Event payload meanings | Nothing | Each emitter |
| Supabase backend (§8.1) | this → backend | Batches (R4, R8) | KPIs (R10) | Backend ADR |

## Formulas

### F1 — `offline_s_bucket`

The offline_s_bucket formula is defined as:

`offline_s_bucket = 0 if gap_s < 60; else min(bucket_max, 1 + floor(log2(gap_s / 60)))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| gap_s | int | 0 – 2³¹ | calculated | Real seconds since the previous `session_end` on this install (engine wall clock; 0 for the first session) |
| bucket_max | int | 16 | constant | Top bucket (≈ 45 days and beyond) |

**Output Range:** 0 – 16. Bucket 1 = 1–2 min, 5 = 16–32 min, 9 ≈ 4.3–8.5 h, 10 ≈ 8.5–17 h, 11 ≈ 17–34 h. Coarse buckets are deliberate: they answer "how long were they away" (offline cap 8 h Free / 24 h Premium, §21 P4) without sending a timestamp. A negative gap (clock moved back) is treated as 0.
**Example:** away 9 h = 32,400 s → 32,400 / 60 = 540 → log2 540 ≈ 9.08 → bucket 10.

### F2 — Sum split

The sum split formula is defined as:

`sum_low = S mod 2³¹;  sum_high = floor(S / 2³¹)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| S | int64 | 0 – `gold_balance_max`-scale (≤ 10¹⁸ per session) | calculated | Session sum of the `sum_slot` payload for one `ev` |

**Output Range:** each half 0 – 2³¹ − 1, so JSON consumers that read numbers as doubles stay exact (the same reason Local save writes int64 as strings). `sum_high` exceeds 2³¹ only above 4.6 × 10¹⁸, beyond any per-session gold flow (`gold_op_max` = 10¹², Gold economy). Negative payloads are not summed: a `sum` source whose slot can be negative is a configuration error, logged and skipped (R9).
**Example:** S = 5,000,000,000 → `sum_high` = 2, `sum_low` = 705,032,704.

### F3 — `flush_now`

The flush_now formula is defined as:

`flush_now = online AND consent_granted AND NOT in_flight AND NOT backing_off AND ( queued ≥ flush_threshold OR (now − last_flush_s) ≥ flush_interval_s OR lifecycle ∈ {background, session_end} )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| queued | int | 0 – `queue_cap_records` | calculated | Records in pending buffer + disk queue |
| flush_threshold | int | 50 – 1,000 (default 200) | data file | Size trigger |
| flush_interval_s | int | 60 – 3,600 (default 600) | data file | Time trigger while in the foreground |
| last_flush_s | int | — | calculated | Engine time of the last successful upload |

**Output Range:** boolean. With defaults and a typical session (F5), a session uploads once or twice: at background, plus a 10-minute flush in long sessions.
**Example:** 120 records queued, 11 minutes since the last flush → time trigger fires.

### F4 — `retry_delay_s`

The retry_delay_s formula is defined as:

`retry_delay_s = min(retry_max_s, retry_base_s × 2^attempt) × (1 + j)`,  `j` uniform in [−0.2, 0.2]

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| attempt | int | 0 – ∞ (reset to 0 on 2xx) | calculated | Consecutive failed attempts |
| retry_base_s | int | 5 – 120 (default 30) | data file | First delay |
| retry_max_s | int | 300 – 86,400 (default 3,600) | data file | Delay ceiling |
| j | float | −0.2 – 0.2 | calculated (engine RNG, host-side) | Jitter so many clients do not retry in step after an outage |

**Output Range:** 24 s – 4,320 s with defaults. Reaches the cap at attempt 7. `attempt` only grows while the app is running; a new session resets it.
**Example:** attempt 3 → min(3,600, 240) = 240 s × (1 ± 0.2) = 192–288 s.

### F5 — Volume and tap cost

The volume formulas are defined as:

`bytes_per_day = sessions_per_day × (raw_per_session × raw_bytes + counters_per_session × counter_bytes + header_bytes) × compress_ratio`

`c_tap_tick = n_tap × c_tap_rec`  (the tap's own work inside its bus call, Event bus R6)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| sessions_per_day | float | 1 – 20 | calculated (KPI) | Assumed 5 for an idle game |
| raw_per_session | int | 0 – `raw_per_session_max` (default 300) | calculated | Raw records in a session; capped (Tuning Knobs) |
| raw_bytes | int | ≈ 120 | constant (schema) | One R4 record as JSON |
| counters_per_session | int | 0 – allowlist size (≈ 25) | calculated | Non-zero counters in the summary |
| counter_bytes | int | ≈ 80 | constant (schema) | One summary record |
| header_bytes | int | ≈ 250 | constant (schema) | Batch header |
| compress_ratio | float | 0.15 – 0.4 | measured | gzip on repetitive JSON |
| n_tap | int | 0 – 2,000 | calculated | Allowlisted records in this tick's batch |
| c_tap_rec | µs | > 0 | measured (P1 spike) | Per record: mode lookup + append or counter add |

**Output Range:** typical ≈ 5 × (60 × 120 + 20 × 80 + 250) × 0.25 ≈ **11 KB/day per player**; at the raw cap ≈ 5 × (300 × 120 + 25 × 80 + 250) × 0.4 ≈ **77 KB/day**. At 10,000 DAU that is 110 MB – 770 MB/day of ingest, which sets the Supabase tier (OQ-5). The tap's cost must not move the bus's `E_budget`: the allowlist adds 1 to `k̄` only for the ≈ 25 listed types, and `c_tap_rec` should be ≤ `c_route` (Event bus F1). The spike measures both.
**Example:** a 24 h offline return emits one `offline_resolved` plus backlog summaries; with `count` mode, a 2,000-event catch-up tick costs one counter add per allowlisted record and adds 0–3 raw records.

### F6 — Retention (backend)

`retention_dN = |{aid : first_day(aid) = d0 AND has_session(aid, d0 + N)}| / |{aid : first_day(aid) = d0}|`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| N | int | 1, 7, 30 | constant | Retention day |
| first_day(aid) | date | — | calculated | `utc_day` of the `aid`'s first `session_start` |
| has_session | bool | — | calculated | Any `session_start` from that `aid` on that `utc_day` |

**Output Range:** 0 – 1. Because `aid` resets on decline/reset/reinstall (R3), a returning player can count as a new one; retention is a **lower bound** and cohorts with high reset rates are flagged by `session_start` with `sid = 1` and a non-zero bucket (impossible for a true first session).
**Example:** 1,000 installs on day 0, 380 seen on day 1 → D1 = 0.38.

### F7 — `gold_out_in_ratio` (backend)

`gold_out_in_ratio = Σ gold_spent.sum / (Σ gold_tax_in.sum + Σ gold_shop_in.sum)` over one `aid`-day; undefined (excluded) when the denominator is 0

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| gold_spent.sum | int | ≥ 0 | calculated | F2-reassembled sum of 2703 slot 2 |
| gold_tax_in.sum | int | ≥ 0 | calculated | Sum of 2701 slot 3 |
| gold_shop_in.sum | int | ≥ 0 | calculated | Sum of 2702 slot 4 |

**Output Range:** 0 – unbounded; §19.5 targets 0.6 – 0.9. It is a **field check of the simulator's** §19.5 number, not a replacement for the Gold economy's S3 conservation test. It omits fund inflows that are not 2701/2702 (building output, rewards) until Gold economy confirms which types carry them (OQ-3).
**Example:** spent 540,000, tax 400,000, shop 200,000 → 0.90.

## Edge Cases

- **If consent is `unasked` or `declined`**: no tap, no file, no network. Session counters are not kept either, so granting later does not back-fill earlier play.
- **If the player declines mid-session**: the tap's `active` flag drops every later record at once; the queue, counters and ID are deleted before the toggle's UI confirms. Records already received by the server stay under the old `aid` until deletion by request (OQ-4).
- **If an allowlisted bus type is not registered in this build** (Wave-gated, VS-only or not built): it is dropped from the subscription list before `subscribe`, a dev-build warning names it, and boot proceeds (R5). A typo therefore cannot cause the bus boot error in Event bus R4.
- **If the subscriber cap (16) would be exceeded by the tap**: the tap is not registered, a dev-build error names it, and the game boots normally with analytics limited to host signals. Analytics never takes the last slot from a gameplay subscriber (OQ-6).
- **If the tap's batch holds 2,000 records** (hard-cap tick, or a large catch-up tick): every record is counted; raw-mode records beyond `raw_per_session_max` for the session are counted under `raw_overflow` and not queued.
- **If an event arrives while `catching_up`**: it is collected and flagged `cu = 1` (R4), so offline-resolved bursts can be separated from live play.
- **If the app is killed without a background callback**: counters were last persisted at the previous background (R6); the next launch writes that session's `session_end` with `p[0] = 0` (unknown duration) and its persisted summary. Play since the last background is lost from analytics only.
- **If the device clock jumps** (manual change, time zone): `t_ms` uses the monotonic clock and is unaffected; F1 treats a negative wall-clock gap as 0; `utc_day` may be wrong and the server rejects batches whose `utc_day` is more than 1 day from receipt (R8 validation).
- **If the queue is full and offline for days**: oldest raw records drop first, summaries last, `queue_dropped` counts the loss (R7). The queue never grows past `queue_cap_records`.
- **If the server returns 4xx (schema or allowlist reject)**: the batch is dropped, not retried (a bad batch never becomes good), and `upload_rejected` is counted. 5xx and timeouts retry (F4).
- **If two app instances run** (PC/Steam): the analytics file is locked by the first; the second runs without analytics.
- **If a `sum` slot is negative** in a record: that record is counted but not summed, and a dev-build warning names the source (F2).
- **If the player is a minor or the store rating requires it**: no special path in Alpha; the opt-in gate already collects nothing without consent. Age-gating rules are a legal OQ (OQ-4).
- **If a cloud-save conflict restores an older save**: analytics is unaffected; it is not in the save. Counters keep counting from the restored state's events.
- **If Premium is bought mid-session**: `tier` stays `free` for that session's header and becomes `premium` from the next session; the purchase itself is visible as `iap_state`.
- **Degenerate use**: a player cannot gain anything through analytics (it sends, never receives), so there is no exploit. A malicious client can send fake records; the server only validates shape and rate (R8), and KPIs are treated as indicative, never as leaderboard or reward input.

## Dependencies

### Upstream (this system depends on)

| System (#) | Hard / soft | Interface | Status |
|---|---|---|---|
| Event bus and history log (42) | Hard (for sim events) | `subscribe("analytics", 3700, type_ids, tap)` at boot; batch delivery R5; subscriber contract R6 | GDD exists (Needs Revision); conforms to it |
| Ads (33) | Soft | R3 notice precedes the analytics opt-in; R12 host signals | GDD exists; its OQ-4 answered by R2 |
| Settings (45) | Hard (for any collection) | Preferences key `analytics_consent`; Privacy section rows (toggle, *Reset analytics ID*) | GDD exists; key and rows not yet in it (**PROVISIONAL**, OQ-1) |
| Sim core (1) | Soft | `catching_up` and tick counts via the R15 facade, read between ticks | GDD exists |
| Entitlement and feature flags (32) | Soft | `premium` entitlement at session start; events 3201–3203 | GDD exists |
| In-app purchases (34) | Soft | R13 host signals | GDD exists |
| Account and cloud save (7) | Soft | `sync_state_changed`, `conflict_detected` host signals | GDD exists |
| Onboarding and tutorial (44) | Soft | Step-completed host signal with a stable step ID | **PROVISIONAL** — no GDD |
| Localization (4) | Soft | Active locale code | GDD exists (lists Analytics as reader) |
| Data layer (3) | Soft | Allowlist and knob storage | Storage form open (OQ-2) |

Analytics works with any subset: without the bus tap it sends host signals only; without consent it does nothing.

### Downstream (systems that depend on this one)

None in the game. Every gameplay system works identically with Analytics absent (R1). The backend dashboards (tooling, ADR) consume its records.

**Bidirectional check.** Event bus, IAP, Account and cloud save, Localization, Recruitment, Golden Boss, Retention, Items, Skills, Member model, Member state machine, Rebirth and Zones GDDs already list Analytics as a soft downstream consumer. Member model (801–805) and Member state machine (4101–4103) list Analytics, but none of their types is in the initial allowlist; that is consistent (listing a consumer permits, not obliges, collection). Ads (33) and Entitlement (32) list Analytics. Settings (45) lists Analytics only as a reader of locale; it must add the `analytics_consent` key and the two Privacy rows (OQ-1). Onboarding (44) must list Analytics when designed.

## Tuning Knobs

All live in the analytics config (storage OQ-2), never in simulation config; changing them never changes `sim_version`.

| Knob | Default | Safe range | Too low | Too high |
|---|---|---|---|---|
| `session_gap_s` | 300 | 30 – 1,800 | App switches split sessions; inflated session counts | Separate visits merge; session length inflated |
| `flush_threshold` | 200 | 50 – 1,000 | Many small uploads, radio wake-ups, battery | Larger batches lost on kill |
| `flush_interval_s` | 600 | 60 – 3,600 | Battery and data | Data arrives late for live dashboards |
| `batch_max_records` | 500 | 100 – 2,000 | Many requests | Request body too large for the Edge Function limit |
| `queue_cap_records` | 5,000 | 1,000 – 20,000 | Loss on long offline spells | Disk use (≈ 0.6 MB at 5,000 × 120 B; ≈ 2.4 MB at the top) |
| `raw_per_session_max` | 300 | 50 – 2,000 | Milestone loss in long sessions | Volume (F5) |
| `retry_base_s` / `retry_max_s` | 30 / 3,600 | see F4 | Hammering the server in an outage | Slow recovery |
| Allowlist rows (R5) | see table | — | Blind spots | `k̄` cost on the bus (F5) and volume |

Interactions: `flush_threshold` above `queue_cap_records` makes the size trigger dead; the validator should reject it. `batch_max_records` below `flush_threshold` splits each flush into several requests — allowed but wasteful.

Pointed to, not owned: `max_event_subscribers` (16, Event bus), `event_buffer_hard_cap` (2,000, Sim core), `gold_op_max` (Gold economy), the §19.5 60–90% target.

## Visual/Audio Requirements

None owned. The privacy prompt and Settings toggle reuse the UI style of the Ads (33) privacy notice and Settings (45). No sound.

## Game Feel

Not applicable beyond R9 and F5: analytics must cause no frame hitch (no upload or file write inside a tick; file writes only on background or flush) and no visible state.

## UI Requirements

Analytics contributes content to screens owned elsewhere:
- **Analytics opt-in (shown right after Ads R3's privacy notice, first launch only):** one line explaining anonymous play statistics, the privacy policy link (§14), and an *Allow* / *No thanks* choice of equal visual weight, no pre-selected option. On builds without Ads (Steam, Web) it follows the same notice (Ads R3 PC/Web path).
- **Settings (45) → Privacy & ads:** an *Anonymous play statistics* toggle (state from R2), a *Reset analytics ID* action with a one-line confirmation, and the policy link.
- All strings via Localization (4) keys; no analytics string is hardcoded.

> **📌 UX Flag — Analytics**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` for the consent prompt and the Settings privacy panel (owned by 33/45) **before** writing epics. Stories that reference this UI should cite `design/ux/[screen].md`, not this GDD.

## Cross-References

| Reference | Document | What this GDD relies on |
|---|---|---|
| Event bus R4–R6, F1 | `event-bus-and-history-log.md` | `subscribe` contract, pure-observer role, `k̄` cost, 16-subscriber cap |
| Sim core R15 | `sim-core-and-tick-loop.md` | `catching_up` flag via the facade |
| IAP R13 | `in-app-purchases.md` | Host signal names and fields |
| Account R1, host signals | `account-and-cloud-save.md` | Host-level service pattern; `sync_state_changed`, `conflict_detected` |
| Localization R1 | `localization.md` | No text in analytics payloads; locale code as a dimension |
| Gold economy F8 event list | `gold-economy.md` | 2701–2703 payload slot meanings for `sum` mode |
| Golden Boss R17 | `golden-boss-and-guild-raid.md` | 1403–1406 |
| Recruitment events | `recruitment.md` | 1502, 1504 |
| Retention R8 | `retention-leaving-and-negotiation.md` | 1604 `member_leaving` |
| Skills, Rebirth, Enhancement, Items, Crafting, Offline, Zones event blocks | respective GDDs; `design/registry/entities.yaml` | Event IDs in R5 |
| GDD §3.2, §8.1, §11, §14, §19.5 | `JX1_Tycoon_GDD.md` | Services layer, Supabase backend, Free/Premium, privacy policy, economy target |

## Acceptance Criteria

- **AC-1 [Integration] (R1)**: **GIVEN** a fixed seed and command script, **WHEN** the run is executed once with the analytics tap registered and consent `granted` and once without it, **THEN** the final state hash, `type_table_hash`, history snapshot and save bytes are identical.
- **AC-2 [Logic] (R1)**: **GIVEN** the tap receives any batch, **WHEN** it returns, **THEN** it has made zero calls to `ctx.emit`, `ctx.submit`, `ctx.fail` or any history query (verified with a recording `ctx` double).
- **AC-3 [Logic] (R1)**: **GIVEN** a headless host (balance simulator, verifier, parity harness), **WHEN** it boots, **THEN** no subscriber with `owner_id = "analytics"` is registered.
- **AC-4 [Integration] (R2)**: **GIVEN** a fresh install with consent `unasked`, **WHEN** the player plays 10 minutes and backgrounds the app, **THEN** no analytics file exists and zero network requests to `analytics_ingest` were made.
- **AC-5 [Integration] (R2)**: **GIVEN** consent `granted` with 150 queued records, **WHEN** the player turns the Settings toggle off, **THEN** before the toggle confirms, the queue file, counters and `analytics_id` are deleted, and later allowlisted events produce no record.
- **AC-6 [Logic] (R3)**: **GIVEN** consent `granted`, **WHEN** *Reset analytics ID* is used, **THEN** the new ID differs from the old one, `sid` restarts at 1, and the queue is empty.
- **AC-7 [Logic] (R4)**: **GIVEN** every record type the system can produce, **WHEN** serialized, **THEN** each matches the R4 schema and no field contains `account_id`, `guild_uid`, any display string, or any value outside `[a-z0-9_]` in `ev` (schema test over a fixture of all allowlist rows).
- **AC-8 [Logic] (R5)**: **GIVEN** an allowlist with one `count`, one `sum` (slot 3) and one `raw` row, **WHEN** a batch of 10, 10 and 2 matching records arrives, **THEN** the counter reads 10, the sum equals the sum of the 10 slot-3 values, and exactly 2 raw records are queued.
- **AC-9 [Logic] (R5)**: **GIVEN** an allowlist row for a type not registered in this build, **WHEN** the host subscribes, **THEN** the row is omitted from the `subscribe` list, `bus.seal()` succeeds, and a dev-build warning names the row.
- **AC-10 [Logic] (R6, F1)**: **GIVEN** a previous `session_end` 9 h ago, **WHEN** a session starts, **THEN** `session_start.p[0]` = 10; and with gaps of 0 s, 59 s, 60 s and −100 s it is 0, 0, 1 and 0.
- **AC-11 [Logic] (R6)**: **GIVEN** the app backgrounds for `session_gap_s` − 1 s and returns, **THEN** `sid` is unchanged; **GIVEN** `session_gap_s` + 1 s, **THEN** `sid` increments and a `session_end` plus summary were queued.
- **AC-12 [Integration] (R6)**: **GIVEN** a session with persisted counters, **WHEN** the process is killed without a background callback and relaunched, **THEN** the queue holds that session's `session_end` with `p[0] = 0` and its summary records.
- **AC-13 [Logic] (R7)**: **GIVEN** `queue_cap_records` = 1,000 filled with 990 raw and 10 summary records, **WHEN** 20 more raw records arrive, **THEN** the queue holds 1,000 records, all 10 summaries remain, the 20 oldest raw records are gone, and `queue_dropped` = 20.
- **AC-14 [Integration] (R8)**: **GIVEN** a mock ingest that drops the response of the first request, **WHEN** the client retries, **THEN** the server-side store holds each `(aid, sid, seq)` exactly once.
- **AC-15 [Logic] (R8)**: **GIVEN** a 400 response, **THEN** the batch is deleted and `upload_rejected` increments; **GIVEN** a 503 or timeout, **THEN** the batch is kept and the next attempt waits per F4.
- **AC-16 [Logic] (F2)**: **GIVEN** S = 5,000,000,000, **THEN** `sum_high` = 2 and `sum_low` = 705,032,704, and `sum_high × 2³¹ + sum_low` = S; **GIVEN** S = 0, **THEN** both are 0.
- **AC-17 [Logic] (F3)**: **GIVEN** defaults, **WHEN** `queued` = 199 and 9 min since the last flush in the foreground, **THEN** `flush_now` is false; at `queued` = 200, or at 10 min, or on background, it is true; while a request is in flight it is false.
- **AC-18 [Logic] (F4)**: **GIVEN** defaults and jitter fixed at 0 (injected), **WHEN** attempts 0, 3 and 10 fail, **THEN** delays are 30 s, 240 s and 3,600 s; with jitter fixed at ±0.2 the attempt-3 delay is 192 s / 288 s.
- **AC-19 [Performance] (F5)**: **GIVEN** the P1 spike device and the max-roster fixture, **WHEN** the tap processes a 2,000-record batch of allowlisted types, **THEN** its p99 cost per record is ≤ the measured `c_route`, and the measured `E_budget` with the tap registered is ≥ `E_floor` (Event bus F1).
- **AC-20 [Integration] (F5)**: **GIVEN** a 24 h offline return on the max-roster fixture, **WHEN** the session ends, **THEN** raw records ≤ `raw_per_session_max`, every record from catch-up ticks has `cu = 1`, and the uploaded batch is ≤ 100 KB compressed.
- **AC-21 [Logic] (F6, F7)**: **GIVEN** a fixture of 10 `aid`s with known session days and gold sums, **WHEN** the backend KPI queries run, **THEN** D1/D7 and `gold_out_in_ratio` match hand-computed values, and an `aid`-day with zero inflow is excluded from F7.
- **AC-22 [Logic] (R9)**: **GIVEN** the network is down, the queue is full and the allowlist has a malformed row, **WHEN** the player plays, **THEN** no error dialog, toast or game error log entry appears in a release build.
- **AC-23 [UI] (UI Requirements)**: **GIVEN** the first-launch prompt and the Settings privacy panel, **WHEN** shown in `vi` and `en`, **THEN** *Allow* and *No thanks* have equal size and weight, neither is pre-selected, and a retained screenshot of each is stored in `production/qa/evidence/`.

*`qa-lead` lens applied: every core rule (R1–R9) and formula (F1–F7) has at least one criterion; R10 KPI definitions are covered through F6/F7 (AC-21); AC-19 depends on the P1 spike's measured constants and is blocked until then.*

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **PROVISIONAL: Settings (45)** — assumes a preferences key `analytics_consent` (`unasked`/`granted`/`declined`, default `unasked`) and two rows in its Privacy & ads section (toggle, *Reset analytics ID*), shown on every build including Steam/Web. **Ads (33)** — assumes the opt-in screen is sequenced right after its R3 notice, and that its OQ-4 is closed by R2 here (own opt-in, everywhere). Whether the store review accepts the notice + separate opt-in flow is unverified. | 45/33 authors | Next consistency pass |
| OQ-2 | **Schema change, not decided in this run:** where the R5 allowlist and the Tuning Knobs live. Proposed: a new `data/analytics_events.csv` (`source`, `ev`, `mode`, `sum_slot`, `min_wave`) validated by `content_validator`, plus analytics keys in a non-sim config so changes never bump `sim_version`. Needs Data layer (3) approval. | Data layer owner + user | Before Alpha implementation |
| OQ-3 | **PROVISIONAL: Gold economy (27)** — which event types carry *all* fund inflows (building output, quest/raid rewards) so F7 covers every inflow, and confirmation of the 2701 slot 3 / 2702 slot 4 / 2703 slot 2 meanings. | Gold economy author | Next consistency pass |
| OQ-4 | Legal: is the opt-in pseudonymous design enough for GDPR/PDPD (Vietnam Decree 13/2023) and Play Data safety; does the backend's country lookup from IP count as location collection; how is a deletion request by `aid` served; what age-gating applies. Not legal advice (§14). | User (legal review) | Before Wave 1 store submission (P7) |
| OQ-5 | Backend cost: F5's 110–770 MB/day at 10,000 DAU against the Supabase tier, and a server-side retention period for raw records (proposed 13 months, aggregates kept). | User + devops | Before Alpha launch |
| OQ-6 | Subscriber budget: Event bus caps subscribers at 16. Confirm the planned set (41, 25, 37, 44, and any others) leaves room so the tap never displaces a gameplay subscriber. | Event bus author | Next consistency pass |
| OQ-7 | **RESOLVED (consistency-check 2026-11-16):** Onboarding (event block 4400) provides sim events 4401 `onboarding_step_completed` (`a` = stable `row_id` 1–63) and 4402 `onboarding_ended`; the tap takes them from the bus by allowlisting 4401/4402 instead of a host signal (Onboarding OQ-10). | 44 author | Closed |
| OQ-8 | Whether Premium's "thống kê chi tiết/phân tích bang" (§11.2) should reuse this pipeline. Proposed **no**: that is an in-game guild statistics screen computed locally from the history log; analytics is developer telemetry. Recorded so the two are not merged by accident. | Game designer | When Guild screens (39) is designed |

*Post-design note (CD-GDD-ALIGN): NOT ASSESSED — no `game-concept.md`, `game-pillars.md` or `game-brief.md` exists. An informal check against GDD §1 and §11.2 found no conflict: the system sells nothing, changes no rule, and its opt-in stance matches §11.2's player-respecting monetization.*
