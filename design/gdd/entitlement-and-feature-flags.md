# Entitlement and Feature Flags

> **Status**: Designed (pending independent /design-review)
> **Author**: user + Claude (autonomous batch run, decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief exist to check against (`design/gdd/game-pillars.md`, `design/gdd/game-concept.md` and `design/game-brief.md` are all absent)
> **Implements Pillar**: None (no game-pillars.md yet). Serves the locked GDD §2/§11.1 rule "1 app + IAP Premium mua một lần", the §11.2 rule "không bán sức mạnh trực tiếp làm lệch bảng xếp hạng", §11.3 "mọi tính năng khoá đi qua `FeatureFlags`" and §11.5 "entitlement tách khỏi `is_premium`".

## Summary

Entitlement and feature flags is the one place the game decides what this player has unlocked: Premium (from the one-time purchase, or the paid PC build) and Thiên Nhãn's "exact PA for everyone" (from its own purchase). It reads the purchase ledger kept by In-app purchases, keeps a local cache so the answer works offline, and hands the simulation a small **entitlement snapshot** through one logged host command, so every Premium-gated rule reads the same value and a replay reproduces it. On top of that it holds the **feature flag table**, which maps each gated feature (no ads, party lock, 24 h offline cap, detailed stats…) to the entitlement it needs and to an optional time-limited free trial.

> **Quick reference** — Layer: `Feature` · Priority: `Alpha` · Key deps: `In-app purchases (34)`, `Account and cloud save (7)`, `Command layer (5)`, `Local save and migration (6)`; depended on by `Ads (33)`, `Offline progress (31)`, `Party (13)`, `CA/PA and traits (9)`, `Recruitment (15)`, `Quests and achievements (25)`, `Leaderboards (35)`, `Guild screens (39)`, `Settings (45)`

## Overview

Entitlement and feature flags (EFF) has two halves. The **Entitlement service** is host-level (GDD §3.2 `[Services]`: "Entitlement(Free/Premium)"). It derives two booleans, `premium` and `exact_pa_all`, from three sources in strict priority — the build type (the Steam build is Premium by definition, §11.1), the account's ownership records in the server ledger written by In-app purchases (IAP R5), and, while verification of a just-made purchase is pending, the store client's own purchase state (a short provisional grant, R5). It keeps a per-account local cache so a player who bought Premium keeps it on a plane (R6). It never verifies receipts itself (that is IAP's `verify_purchase`) and never writes simulation state directly. The **sim-side entitlement view** is a tiny simulation section (`entitlement`) that holds the last applied snapshot and any running feature trials. The service changes it only by submitting the host command `set_entitlement` (R3), which the Command layer logs, so the leaderboard verifier and the parity harness replay Premium exactly as it was (Command layer R9). The **feature flag table** (proposed `data/feature_flags.csv`, R8) lists every gated feature with the entitlement it needs, whether it is read inside the simulation or only by the host, and whether a quest may grant a trial of it. Every gated check in the game is `feature_on(feature_id)` (F3), never a raw `is_premium` test, so a feature can move between Free and Premium by editing a data row.

*Framing: technical (Meta category, recommended option); no ADR exists yet, so none is cited. Implementation choices — the cache file format, how the host reads the store client's purchase list, and the boot wiring — become ADRs.*

## Player Fantasy

**"I paid once, and it just stays paid."** This is an indirect fantasy (Meta category): nobody enjoys an entitlement system; they enjoy never thinking about it. The moment: a player who bought Premium on the bus with no signal sees the banner vanish at once; a month later, on a flight, the game still has no ads and still credits 24 hours of offline work; when she gets a new phone and signs in, Premium is there before the first guild screen loads. And the free player next to her, whose guild has the same seed and the same orders, gets exactly the same drops and the same fights — the only differences are comfort, convenience and how long the guild may work while the app is closed.

Supporting promises the rules must keep:

- **Paid never flickers off.** A network failure, a slow backend or an expired cache never downgrades a paying player. Only an authoritative "not owned" from the backend (a refund) does (R6).
- **Free is a full game, and trials show the rest.** Free players get every core loop (§11.2); a quest may lend a Premium convenience for a day so the player sees what it does (§11.5), never Premium itself and never Thiên Nhãn.
- **The leaderboard can see who was Premium.** Every change of entitlement is a logged command with its source, so a ranked run can be checked (R3, R11).

*`creative-director` lens applied in this run (no agent spawned). No game pillars exist, so the framing is anchored to GDD §11.2 and §11.5 text.*

## Detailed Design

> Specialist lenses applied (SKILL §6 routing; `Meta` → Foundation/Infrastructure row): **systems-designer** (primary), **gameplay-programmer** and **engine-programmer** (supporting). Points are folded into the rules; the one disagreement is recorded under R3.
> - systems-designer: Premium changes simulation outcomes (party commands, ad-quest claims; no longer the offline cap — user decision 2026-11-16 made it equal for every player), so it is a simulation **input**; an input that is not in the command log breaks replay and the leaderboard verifier. The snapshot therefore enters as a logged host command, not as a live service call.
> - gameplay-programmer: nothing in a tick may call a service or read a file; sim-side gating must be a pure read of sim state. Applier code should never test a raw boolean, or moving a feature between tiers becomes a code hunt.
> - engine-programmer: the store client's local purchase query (Google Play Billing through a Godot Android plugin) is **NOT SOURCEABLE** — `docs/engine-reference/godot/` has no module for billing or platform plugins, and there is no `core.md` (the domain the `Meta` category maps to). Whether it works offline and how fast it answers must be measured in the P1 spike (§12.1). Feasibility of R5 was therefore not checked against the pinned engine.

### Core Rules

**R1 — Two halves, one truth.** The Entitlement service is host-level: no tick phase, no Event-bus events, never called from inside a tick, free to use engine time and network (the determinism rules bind only the simulation). The sim-side view is simulation state owned by this system: a saved section and a read-only query used by other systems' appliers and handlers. The service never writes the view except by submitting `set_entitlement` (R3). Host-scope consumers (Ads, UI) read the **view**, not the service, once the guild is loaded, so the UI and the simulation can never disagree about Premium for more than the one tick a command takes to apply (Command layer R11).

**R2 — The two entitlements.** Exactly two, deliberately separate (§11.5 "entitlement tách khỏi `is_premium`"):

| Entitlement | Bit | Granted by | Never granted by |
|---|---|---|---|
| `premium` | 1 | Steam/PC paid build; an `active` ownership record for `premium_unlock`; a provisional `premium_unlock` (R5) | quests, trials, rewarded ads, Thiên Nhãn |
| `exact_pa_all` | 2 | an `active` ownership record for `pa_eye` (on Steam: the equivalent DLC, PROVISIONAL, IAP OQ-6); a provisional `pa_eye` (R5) | Premium, quests, trials, ads (§11.5 "Không bao giờ" free) |

The snapshot is the integer `flags` = sum of the held bits (0 – 3), derived by F1. Thiên Cơ Kính (the consumable lens) is **not** an entitlement: it is an item in guild storage delivered by IAP R8.

**R3 — The snapshot enters the simulation as a logged host command.** The service submits `set_entitlement(flags, source)` through the Command layer host path (Command layer R8). It is registered by this system in block 3200:

| `type_id` | Name | Args (`arg_kinds`) | Origins | Reason codes |
|---|---|---|---|---|
| 3201 | `set_entitlement` | flags `int(0, 3)`, source `int(0, 4)` | host | 101 `entitlement_unchanged` |

`source` records why: `0 = default` (no information, Free), `1 = server` (an authoritative ledger answer this session), `2 = cache` (R6), `3 = provisional` (R5), `4 = build` (paid PC build). The applier: if `flags` and `source` both equal the view's current values, refuse `101` (the client treats it as success, and nothing is logged as a change); otherwise set `view.flags`, `view.source`, `view.applied_tick = ctx.tick`, and emit `entitlement_changed` (R10). The applier cost is constant (two int writes, one emit). The service submits only when its derived `(flags, source)` differs from the view (no submit storms on every refresh). *(Lens disagreement, resolved by recommended option: engine-programmer proposed passing the snapshot as an argument to every `advance` call, which avoids a command. systems-designer objected that a per-call input is not in the command log, so Leaderboards and the parity harness could not replay it without a second log; and the Command layer R14 already names the snapshot as injected input read by appliers. The logged-command design was kept.)*

**R4 — Derivation order.** Each time it refreshes (R7), the service computes `flags` and `source` by F1, taking the first source that answers for each bit: (1) **build** — the PC/Steam build sets `premium`; (2) **server** — the newest successful ledger read of this session for the current `account_id`; (3) **provisional** — a store-client purchase not yet verified (R5); (4) **cache** — the per-account cache (R6); (5) **default** — Free. `source` in the command is the highest-priority source that contributed a held bit, or the source of the newest answer when no bit is held (so a server "not owned" is recorded as `server`, not `default`).

**R5 — Provisional grant after a purchase.** This answers IAP OQ-5. When the store client reports a non-consumable (`premium_unlock` or `pa_eye`) as purchased and IAP's verification has not yet returned (IAP states `Purchased`, `Verifying`, `Backoff`), the service grants that bit provisionally for at most `provisional_grace_h` (F2), measured from the moment the service first saw the store's purchased state. A `Verified` answer converts it to `server`. A `Rejected` answer removes it at once. If the window runs out with no answer, the bit is dropped and comes back as soon as verification succeeds (IAP R6/R7 keep retrying). Rationale: the player has just paid, and a "Premium is being verified…" wait with ads still showing is the worst first impression of the purchase; the abuse risk (a forged client-side purchase on a rooted device) gains only ad removal and comfort, and its `source = 3` is visible to the leaderboard verifier (R11). Consumables are never provisional (IAP R6).

**R6 — The local cache never downgrades on its own.** After every successful ledger read, the service writes a per-account cache file beside the save (not inside it, so choosing a save in a cloud conflict cannot change entitlement): `{account_id, premium_owned, pa_eye_owned, fetched_utc}`. Rules:
- The cache is used only for the same `account_id` it was written for. Signing in as a different account ignores it (R9).
- A cached `true` is kept **however old it is** until an authoritative server answer says otherwise. Being offline, the backend being down, or the session being lost (`SessionLost`, Account R3) never removes an entitlement. Only a successful ledger read that shows no `active` record does (a refund or chargeback, IAP R11).
- With no account and no cache (`NoAccount`, a device that never had network), the result is Free, except on the paid PC build.
- The cache is not tamper-proof and does not try to be: editing it gains comfort features offline, and the logged `source = 2` lets ranked play be checked (R11).

**R7 — Refresh triggers.** The service re-derives (and, when the result changed, submits `set_entitlement`) on: boot, after the save is loaded and before the core starts ticking (so the first tick already sees the right value); IAP `ledger_changed`, `purchase_state_changed` and `restore_finished` (IAP R13); Account `account_state_changed`; app resume; and every `entitlement_refresh_min` minutes while the app is in the foreground with network. A ledger read uses the Account session token and follows the Account and cloud save F2 back-off on failure (`retry_delay_s`), not a schedule of its own.

**R8 — The feature flag table.** One row per gated feature, in a data file (proposed `data/feature_flags.csv` — a new content table, so its creation is a schema change left to the user, OQ-1). Columns: `id`, `requires` (`premium` | `exact_pa_all` | `none`), `scope` (`sim` — read by appliers or handlers; `host` — read only by services and UI), `trial_eligible` (bool), `owner` (the system that implements the feature). The proposed Wave 1 rows, from GDD §11.2 and the GDDs that already gate on Premium:

| `id` | requires | scope | trial | owner | Source |
|---|---|---|---|---|---|
| `no_ads` | premium | host | no | Ads (33) | §11.2 "Không quảng cáo" |
| `ad_quest_direct_claim` | premium | sim | no | Quests (25) | §11.4; `quests.csv` `premium_auto_claim` |
| `party_lock` | premium | sim | yes | Party (13) | Party R11 |
| `party_rearrange_all` | premium | sim | yes | Party (13) | Party R11; §11.5 example "tự động xếp đội 24 giờ" |
| `party_presets` | premium | sim | no | Party (13) | Party R11 |
| `batch_orders` | premium | host | yes | Guild screens (39) | §11.2 "thao tác hàng loạt" |
| `detailed_stats` | premium | host | yes | Guild screens (39) | §11.2 "thống kê chi tiết/phân tích bang" |
| `themes` | premium | host | no | Guild screens (39) | §11.2 "theme/trang trí" |
| `exact_pa_view` | exact_pa_all | sim | no | CA/PA (9), Recruitment (15) | CA/PA R10, Recruitment R7 |

Removed from the table (user decision 2026-11-16): `offline_cap_extended`. The offline cap is the same 12 h for every player on ranked play (Offline R4); Premium is convenience only and buys no offline time, so Offline progress reads no flag.

Not in the Wave 1 table, each recorded as an open question rather than designed here: "thêm lượt tuyển mộ/ngày" (Recruitment OQ-9), "thêm slot cloud save" (Account OQ-5), "gói AI" (AI text layer 36, Full Vision). Content-validator rules: every `id` is unique `[a-z0-9_]`; a row with `requires = exact_pa_all` must have `trial_eligible = false` (§11.5 Thiên Nhãn is never free); `no_ads` must have `trial_eligible = false` (a trial of it is a free Premium slice that changes ad revenue; GDD §11.5 allows trials of conveniences only — OQ-4).

**R9 — Account changes.** When the `account_id` changes (sign-in as a different linked account on this device), the service drops the old account's server answers and provisional grants, loads the new account's cache if one exists, and re-derives. Purchases follow the account (IAP R10). A guest → linked upgrade keeps the same `account_id` (Account R3) and changes nothing here.

**R10 — Feature trials (sim side).** A trial lends one `trial_eligible` feature for a fixed time. Trials are simulation state in the `entitlement` section: `trial_until[feature_uid]` in ticks. They are granted only from inside the simulation, by the owning reward system (Quests and achievements 25, PROVISIONAL), through `grant_trial(ctx, feature_uid, duration_h)` (F4). A trial never stacks beyond one `trial_max_h` window from now, and granting one while the player already has the entitlement is a no-op (nothing to lend). A trial ends on its own at `trial_until`; nothing is taken back that the player made while it ran (owners define what happens on lapse: Party keeps locks in force, Party "If Premium lapses"). The `entitlement` section saves `flags`, `source`, `applied_tick` and the `trial_until` entries that are still in the future. Events registered in block 3200 (Event bus R3), all `logged = false`, `milestone = false`, `ring_per_day = 0`:

| `type_id` | Name | Fields |
|---|---|---|
| 3201 | `entitlement_changed` | `a = old_flags`, `b = new_flags`, `c = source` |
| 3202 | `trial_started` | `a = feature_uid`, `b = until_tick` |
| 3203 | `trial_ended` | `a = feature_uid` |

`trial_ended` is emitted by this system's own P5 handler at the first tick `≥ until_tick` (cost: one comparison per running trial per tick; at most the number of trial-eligible rows, 4 in Wave 1). Guild screens show trial banners from these; Analytics (37) may subscribe.

**R11 — What the leaderboard can see.** Every entitlement change is in the command log with its `source` and tick. Whether a ranked submission may contain `source = 2` (cache) or `3` (provisional) periods, and whether the server cross-checks `server` periods against the ledger, is Leaderboards' (35) policy, not this system's. This system guarantees only that the log is complete: the view never changes except through `set_entitlement`, and a load restores it from the save without a command (the saved value is the state at the save's tick).

**R12 — Dev overrides.** Dev builds can force any `flags` through the normal `set_entitlement` with `source = 0`, from the debug menu. There is no separate cheat command: the host path is already the trust boundary, and a release build's service never submits a value it did not derive (F1).

### States and Transitions

The service tracks, per entitlement bit, which source currently answers:

| State | Meaning | → To | Trigger |
|---|---|---|---|
| `Default` | No information: Free | `Cached` | A cache for this `account_id` is loaded with the bit true |
| | | `Server` | Ledger read succeeds |
| | | `Provisional` | Store client reports the product purchased, verification pending (R5) |
| `Cached` | Bit taken from the cache (R6) | `Server` | Ledger read succeeds (bit may become false only here) |
| | | `Provisional` | A new purchase is seen (rare: re-purchase after a refund) |
| `Provisional` | Bit held for up to `provisional_grace_h` (F2) | `Server` | IAP `Verified` (bit true) |
| | | `Default` / `Cached` | IAP `Rejected`, or the window runs out (falls back to the next source) |
| `Server` | Authoritative answer this session | `Server` | Every later ledger read; a refund turns the bit false here |
| | | `Cached` | App restart (server answers do not persist except through the cache) |
| `Build` | Paid PC build: `premium` fixed true | — | terminal for the life of the build |
| any | | `Default` (then re-derive) | `account_id` changes (R9) |

The sim-side view has no states of its own beyond its stored values; each trial is `running` from `grant_trial` until `trial_until`, then gone.

### Interactions with Other Systems

| System | Direction | Data / call | Owner of the interface |
|---|---|---|---|
| In-app purchases (34) | Upstream, hard | Reads the account's ownership records (`premium_unlock`, `pa_eye`, state `active`/`revoked`); listens to `ledger_changed`, `purchase_state_changed`, `restore_finished` (IAP R13); reads the purchase-transaction state for R5. | IAP owns the ledger and signals; this system owns the derivation. |
| Account and cloud save (7) | Upstream, hard | `account_id`, session token, `account_state_changed`; F2 `retry_delay_s` for back-off. | Account. |
| Command layer (5) | Upstream, hard | Registers `set_entitlement` (3201) in block 3200, reason code 101. | Command layer owns the envelope; this system owns the type. |
| Event bus (42) | Upstream, hard | Registers event types 3201–3203 (R10). | Event bus. |
| Local save and migration (6) | Upstream, hard | Registers the `entitlement` section (`register_section`, Local save R6). The per-account cache is a separate small file beside the save. | Local save owns the format. |
| Data layer (3) | Upstream, hard | Loads the `feature_flags` table (R8); each row has a stable `uid` used by `grant_trial` and events. | Data layer. **PROVISIONAL** — table not yet created (OQ-1). |
| Ads (33) | Downstream, hard | `feature_on(no_ads)`: banner and rewarded placements are hidden when true. | Ads. **PROVISIONAL** — GDD not written. |
| Quests and achievements (25) | Downstream, hard | Reads `feature_on(ad_quest_direct_claim)` (Premium claims the ad quest directly, §11.4); calls `grant_trial` as a reward (R10). | Quests. **PROVISIONAL** — GDD not written. |
| Party (13) | Downstream, hard | Appliers read `feature_on(party_lock / party_rearrange_all / party_presets)` and refuse with `PARTY_PREMIUM_REQUIRED` (Party R11). | Party. |
| CA/PA and traits (9), Recruitment (15) | Downstream, soft (display) | Read `feature_on(exact_pa_view)` (the `exact_pa_all` bit) in their view functions. | CA/PA, Recruitment. |
| Guild screens (39), Settings (45) | Downstream, soft | Host-scope flags; trial banners from R10 events; Settings shows "Premium: active (verified / offline)". | Those systems own layout. |
| Leaderboards and anti-cheat (35) | Downstream, soft | Reads `set_entitlement` entries in the command log (R11). | Leaderboards. **PROVISIONAL** — GDD not written. |
| Analytics (37) | Downstream, soft | May subscribe to 3201–3203. | Analytics. |

## Formulas

### F1 — `entitlement_flags`

The entitlement_flags formula is defined as:

`flags = 1·premium + 2·exact_pa_all`, where
`premium = build_paid ∨ held(premium_unlock)` and `exact_pa_all = held(pa_eye)`,
`held(p) = server(p)` if a ledger read for this `account_id` succeeded this session; else `prov(p) ∨ cache(p)`; and `prov(p) = store_purchased(p) ∧ ¬rejected(p) ∧ (now_utc − first_seen_utc(p)) < provisional_grace_h × 3600` (F2).

When a server answer exists, `held(p) = server(p) ∨ prov(p)` — a purchase made after the last read is still provisional until the next read.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `build_paid` | bool | — | constant (build configuration) | True on the paid PC/Steam build (§11.1) |
| `server(p)` | bool | — | calculated (IAP ledger) | An `active` ownership record for product `p` exists for this `account_id` |
| `cache(p)` | bool | — | calculated (local cache, R6) | Last saved `server(p)` for this `account_id`; false if no cache |
| `store_purchased(p)` | bool | — | calculated (store client) | The store client reports `p` purchased on this device |
| `rejected(p)` | bool | — | calculated (IAP) | IAP returned `Rejected` for that purchase token |
| `first_seen_utc(p)` | int (s) | ≥ 0 | calculated | Engine UTC time the service first saw `store_purchased(p)` |
| `provisional_grace_h` | int (h) | 1 – 168 | data file (`config.csv`, key to be added) | Provisional window (F2) |

**Output Range:** 0 to 3. 0 = Free; 1 = Premium; 2 = Thiên Nhãn only; 3 = both.
**Example:** Android player, Premium bought last month (server `active`), Thiên Nhãn just bought on a train with no network: no server answer yet, `cache(premium_unlock)` true → `premium` true; `prov(pa_eye)` true (seen 10 min ago, window 72 h) → `exact_pa_all` true; `flags = 3`, `source = 3` (provisional is the highest-priority source that contributed a held bit after server/cache, R4). Back online, IAP verifies → `source = 1`, `flags = 3`, one new command.

### F2 — `provisional_active`

The provisional_active formula is defined as:

`provisional_active(p) = store_purchased(p) ∧ ¬rejected(p) ∧ (now_utc − first_seen_utc(p)) < provisional_grace_h × 3600`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `now_utc` | int (s) | ≥ 0 | calculated (engine clock, host) | Host wall clock; the service is not in the sim |
| `first_seen_utc(p)` | int (s) | ≤ `now_utc` normally | calculated | Saved in the cache file so a restart does not reset the window |
| `provisional_grace_h` | int (h) | 1 – 168, default 72 | data file | Matches IAP's `store_finalize_deadline_h` (72): if a purchase is not verified by then the store refunds it anyway |

**Output Range:** bool. **Boundaries:** if `now_utc < first_seen_utc` (clock set back), the difference is negative and the grant holds; setting the clock back can extend a provisional grant, and that gains only comfort features and is visible as `source = 3` (R11). At the knob's minimum (1 h) a slow backend makes Premium blink off after an hour; at the maximum (168 h) a refunded-by-store unverified purchase keeps Premium for a week.
**Example:** seen at 10:00, `provisional_grace_h = 72`, no network for 3 days: true until 10:00 three days later, then false; verification at 10:05 that day turns it into a `server` answer.

### F3 — `feature_on`

The feature_on formula is defined as:

`feature_on(f) = (requires(f) = none) ∨ (requires(f) = premium ∧ view.flags & 1 ≠ 0) ∨ (requires(f) = exact_pa_all ∧ view.flags & 2 ≠ 0) ∨ (trial_eligible(f) ∧ tick < trial_until(f))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `requires(f)` | enum | none / premium / exact_pa_all | data file (`feature_flags.csv`) | Entitlement the feature needs |
| `trial_eligible(f)` | bool | — | data file | Whether a trial may lend it |
| `view.flags` | int | 0 – 3 | calculated (sim state, R3) | Last applied snapshot |
| `trial_until(f)` | int (ticks) | 0 – 2^62 | calculated (sim state, R10) | 0 when no trial ran |
| `tick` | int (ticks) | ≥ 0 | calculated (Sim core) | Current tick; host readers use the view's last completed tick |

**Output Range:** bool. A pure function of sim state and content, no RNG, no clock: identical in Python and GDScript and in replay. **Boundaries:** `trial_until = tick` → false (the trial ended at that tick). An unknown `f` is a boot error at seal (callers name features by content `uid` resolved at boot), never a silent false.
**Example:** Free guild, `party_rearrange_all` trial until tick 1,000,000, now 999,999 → true; at 1,000,000 → false and `trial_ended` fires that tick.

### F4 — `trial_until_after_grant`

The trial_until_after_grant formula is defined as:

`trial_until'(f) = max(trial_until(f), tick + min(duration_h, trial_max_h) × 3600 × tick_rate)`, applied only when `trial_eligible(f)` and `feature_on(f)` is false through entitlement; otherwise no change.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `duration_h` | int (h) | 1 – `trial_max_h` | data file (the reward row, owned by Quests 25) | Length of the trial being granted |
| `trial_max_h` | int (h) | 1 – 168, default 48 | data file (`config.csv`, key to be added) | Longest a single grant may lend |
| `tick_rate` | int | 10 | data file (`config.csv`, exists) | Ticks per second (Sim core) |
| `trial_until(f)`, `tick` | int | as F3 | calculated | As F3 |

**Output Range:** `trial_until'` ≤ `tick + trial_max_h × 36,000` (at 10 Hz: ≤ 1,728,000 ticks ahead at the default). `max`, not addition: two grants in a row do not stack into a longer trial, so a trial cannot be farmed into permanent Premium (§11.5 "không phát vĩnh viễn miễn phí").
**Example:** a weekly-quest reward grants `party_rearrange_all` for 24 h at tick 5,000,000: `trial_until = 5,864,000`. The same reward again 10 h later (tick 5,360,000) gives `max(5,864,000, 6,224,000) = 6,224,000` — the trial runs 24 h from the second grant, not 38 h from the first.

## Edge Cases

- **If the backend is unreachable at boot and a cache says Premium**: Premium (`source = 2`) from the first tick; no downgrade however long the outage lasts (R6).
- **If a ledger read returns "not owned" for a player the cache says owns Premium** (refund, chargeback): the bit turns false at once, the cache is rewritten, and `set_entitlement` is submitted. Owners apply their lapse rules (Party keeps locks; Offline is unaffected — its cap is the same for every player). No popup beyond Settings' status line; IAP owns any refund messaging.
- **If the player buys Premium while the guild is mid-offline-resolution** (hand-off pending): the command queues and applies at the first tick after the hand-off (Sim core R17). The absence is unaffected either way: the offline cap is the same for every player (Offline R4).
- **If the app was closed with Premium and opened after a refund, offline first**: the hand-off happens before the boot refresh can reach the server (the load restores `flags = 1` from the save), which changes no offline result (the cap is equal for all, Offline R4); only Premium conveniences stay on until the refresh. Accepted: a refunded player who goes offline indefinitely keeps the cached Premium anyway (R6). Leaderboards sees it (R11).
- **If two saves disagree about `flags`** (cloud conflict, Account R8): the adopted save's view is loaded; the boot refresh then submits the account's real value. Entitlement never comes from a save in the end, only the momentary view does.
- **If the store client says purchased but IAP returns `Rejected`** (a forged or foreign token): the provisional bit drops immediately; one `set_entitlement` with the lower flags.
- **If the paid PC build also owns `premium_unlock` on the same account** (bought on Android first): `premium` from `build`; nothing double-counts. Mobile on the same account gets Premium from the ledger.
- **If the account switches to one without Premium** (R9): Free from the next refresh, even though the store account on the device may own `premium_unlock` — until *Restore purchases* re-binds the record to the new account (IAP R10, last restore wins).
- **If a trial is granted while the feature is already on through Premium**: no-op, no event (F4). If Premium later lapses, there is no hidden trial waiting.
- **If a trial is running when Premium is bought**: the trial keeps its `trial_until` and simply stops mattering; `trial_ended` still fires (the UI hides it while Premium).
- **If a trial ends during an offline absence**: the P5 check does not run during an aggregate offline resolution (Offline R4 resolves without ticks); `trial_ended` fires at the first live tick ≥ `trial_until`. Trial-eligible features in Wave 1 are commands and UI conveniences, not offline rates, so nothing is mis-credited.
- **If `feature_flags.csv` lacks a row an owner names**: boot error at seal naming the owner and the missing `id` (F3 boundary). A missing row must never read as "Free" or "Premium".
- **If the clock is set back during a provisional window**: the window lengthens (F2 boundary); accepted, visible as `source = 3`.
- **If the cache file is missing or corrupt**: treated as absent (Free until the server answers, or `build`). A corrupt cache is deleted and logged to the host log sink; never a crash.
- **If `set_entitlement` arrives with the same flags but a different source** (cache → server): applied and logged (the source change matters to R11), `entitlement_changed` carries `old_flags = new_flags`.

## Dependencies

### Upstream (this system depends on)

| System | Hard/Soft | Interface | Status |
|---|---|---|---|
| In-app purchases (34) | Hard | Ownership records per `account_id`; signals `ledger_changed`, `purchase_state_changed`, `restore_finished`; purchase-transaction state (`Purchased`/`Verifying`/`Backoff`/`Verified`/`Rejected`) | Designed (pending review) |
| Account and cloud save (7) | Hard | `account_id`, session token, `account_state_changed`, F2 `retry_delay_s`, adopt signal | Designed |
| Command layer (5) | Hard | `register_command` (R2), host submit path (R8), replay (R9), owner gating rule (R14) | Designed |
| Event bus and history log (42) | Hard | `register_type` (R3) for 3201–3203 | Needs Revision |
| Local save and migration (6) | Hard | `register_section` for `entitlement` | Designed |
| Data layer and content pipeline (3) | Hard | `feature_flags` content table with stable `uid`s | Designed; table **not yet created** (OQ-1) |
| Sim core and tick loop (1) | Hard | P5 handler registration; `ctx.tick` | Designed |

### Downstream (systems that depend on this one)

| System | Hard/Soft | Interface | Status |
|---|---|---|---|
| Ads (33) | Hard | `feature_on(no_ads)` | Not designed — PROVISIONAL |
| Party (13) | Hard | `feature_on(party_lock / party_rearrange_all / party_presets)` (its PROVISIONAL-1) | Designed |
| Quests and achievements (25) | Hard | `feature_on(ad_quest_direct_claim)`; `grant_trial` | Not designed — PROVISIONAL |
| CA/PA and traits (9) | Soft | `feature_on(exact_pa_view)` (its OQ-13) | Designed |
| Recruitment (15) | Soft | `feature_on(exact_pa_view)` | Designed |
| Leaderboards and anti-cheat (35) | Soft | `set_entitlement` entries in the command log (R11) | Not designed — PROVISIONAL |
| Guild screens (39), Settings (45) | Soft | Host-scope flags, trial events, status line | Not designed |
| Analytics (37) | Soft | Events 3201–3203 | Not designed |

**Bidirectional check:** the systems index row lists Account and cloud save and In-app purchases; this GDD adds Command layer, Event bus, Local save, Data layer and Sim core as hard upstream links (infrastructure every sim-state owner uses). IAP, Account, Party, Offline, CA/PA and Recruitment already name this system from their side.

## Tuning Knobs

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `provisional_grace_h` (`config.csv`, to add) | 72 | 24 – 96 | A store-refunded, never-verified purchase keeps Premium for days | A slow backend makes a just-paid Premium blink off | IAP `store_finalize_deadline_h` (keep equal) |
| `entitlement_refresh_min` (`config.csv`, to add) | 60 | 15 – 240 | Refunds take hours to show | Backend read load (one row per active player per period) | Account F2 back-off |
| `trial_max_h` (`config.csv`, to add) | 48 | 12 – 72 | A trial feels like free Premium; weakens §11.5 | Trial too short to see the value | Quests (25) reward `duration_h` (must be ≤) |
| `feature_flags.csv` rows (`requires`, `trial_eligible`) | R8 table | per row | Moving too much to Premium makes Free feel cut (§11.2 "Đầy đủ") | Too little in Premium makes it thin | Validator rules R8; owners' lapse rules |

`offline_cap_free_h` is Offline progress's knob, not this system's, and is the same for every player; `offline_cap_premium_h` is deprecated (user decision 2026-11-16). This system selects no offline cap.

## Visual/Audio Requirements

None owned. `Meta` is not a category for which Visual/Audio is required. Shop art, Premium badges and trial banners belong to Guild screens (39) and the art bible.

## Game Feel

Not required for `Meta`. One feel rule: a purchase shows its effect within one second of the store sheet closing (R5 provisional grant, R3 one-tick apply), never after a verification wait.

## UI Requirements

Owned by Guild screens (39) and Settings (45); this system supplies the data:
- Settings status line: "Premium: active", "Premium: active (offline — will verify)" for `source = 2/3`, "Free"; same for Thiên Nhãn.
- Premium-gated controls show a Premium badge and are disabled when `feature_on` is false; the applier refusal is still handled (Command layer R14).
- Trial banner: "Trial: <feature> — <time left>", from `trial_started`/`trial_ended`.
- No nag: the game never shows an upsell because a flag check failed; only the badge and the shop.

> **📌 UX Flag — Entitlement and feature flags**: the Premium badge, trial banner and status line should be covered in the Guild screens / Settings UX spec (`/ux-design`) before epics.

## Cross-References

| This GDD references | Document | Section | Nature |
|---|---|---|---|
| Free/Premium split, trials, entitlement separate from `is_premium` | `JX1_Tycoon_GDD.md` | §11.1–11.5 | Source rule |
| Ownership records, `verify_purchase`, signals, OQ-5 (answered by R5) | `in-app-purchases.md` | R5, R6, R10, R11, R13 | Data dependency |
| Account identity, states, back-off | `account-and-cloud-save.md` | R3, F2 | Data dependency |
| Host commands, block allocation, gating rule, replay | `command-layer.md` | R2, R8, R9, R14 | Rule dependency |
| Event registration | `event-bus-and-history-log.md` | R3 | Rule dependency |
| Equal offline cap, no entitlement read (user decision 2026-11-16) | `offline-progress.md` | R4, OQ-8 | Rule removed |
| Premium party commands | `party.md` | R11, PROVISIONAL-1 | State trigger |
| `exact_pa_all` display | `ca-pa-and-traits.md`, `recruitment.md` | R10, OQ-13; R7, R17 | Display dependency |
| Ad-quest auto claim column | `data/quests.csv` | `premium_auto_claim` | Data dependency |

## Acceptance Criteria

Story types: **[Logic]** automated unit test (blocking); **[Integration]** integration test or documented device run; **[UI]** retained screenshot. `[PENDING: engine]` needs the Godot port or a device.

- **AC-1 [Logic] (R2, F1)**: **GIVEN** each combination of `build_paid`, `server(premium_unlock)`, `server(pa_eye)` (8 cases), **WHEN** F1 runs, **THEN** `flags` equals `1·(build ∨ premium) + 2·pa_eye`; in particular `pa_eye` alone gives 2 and `premium_unlock` alone gives 1.
- **AC-2 [Logic] (R3)**: **GIVEN** a view with `flags = 0, source = 0`, **WHEN** `set_entitlement(1, 1)` applies, **THEN** the view is `1, 1`, `applied_tick` is the apply tick, and one `entitlement_changed(0, 1, 1)` is emitted. **WHEN** `set_entitlement(1, 1)` is submitted again, **THEN** it is refused with 101 and no event is emitted.
- **AC-3 [Logic] (R3, Command layer R4)**: **GIVEN** `set_entitlement(4, 1)` or `set_entitlement(1, 5)`, **THEN** refused `bad_arg` (3); **GIVEN** a sim-origin request, **THEN** `origin_not_allowed` (4).
- **AC-4 [Integration] (R3, R11, Command layer R9)**: **GIVEN** a recorded session with `set_entitlement` changes at ticks 100 (→1) and 50,000 (→0), **WHEN** replayed from `world_seed` and the host log, **THEN** `view.flags` matches the original at every tick and the final state hash is identical.
- **AC-5 [Logic] (R4, R6)**: **GIVEN** a cache `{account A, premium_owned = true, fetched_utc 60 days ago}` and the backend unreachable, **WHEN** the service boots for account A, **THEN** it submits `set_entitlement(1, 2)` before the first tick, and after 10 failed refreshes the view is still `flags = 1`.
- **AC-6 [Logic] (R6)**: **GIVEN** a cache saying Premium for account A, **WHEN** a ledger read for A returns no active `premium_unlock`, **THEN** `set_entitlement(0, 1)` is submitted and the cache now says `premium_owned = false`.
- **AC-7 [Logic] (R6, R9)**: **GIVEN** a cache for account A saying Premium, **WHEN** the device signs in as account B with no cache and the backend unreachable, **THEN** the derived flags are 0 with `source = 0`.
- **AC-8 [Logic] (R5, F2)**: **GIVEN** the store client reports `premium_unlock` purchased at `t0` and IAP is in `Backoff`, **WHEN** the service derives at `t0 + 1 s`, **THEN** `flags = 1, source = 3`; **at `t0 + 72 h − 1 s`** still 1; **at `t0 + 72 h`** 0 (with no cache). **GIVEN** IAP returns `Rejected` at `t0 + 5 min`, **THEN** flags drop to 0 at that refresh.
- **AC-9 [Logic] (R5)**: **GIVEN** a provisional `pa_eye`, **WHEN** IAP returns `Verified`, **THEN** one `set_entitlement(2, 1)` is submitted (source change) and no further command follows on later identical refreshes.
- **AC-10 [Logic] (R4)**: **GIVEN** the paid PC build with no account, **THEN** `flags = 1, source = 4`; **GIVEN** the same build and an active `pa_eye` record, **THEN** `flags = 3`.
- **AC-11 [Logic] (R7)**: **GIVEN** a fake clock and network, **WHEN** 3 hours pass in the foreground with no signals, **THEN** exactly 3 ledger reads occur at `entitlement_refresh_min = 60`, and 0 `set_entitlement` submits if nothing changed.
- **AC-12 [Logic] (R8, F3)**: **GIVEN** `view.flags = 0`, **THEN** `feature_on` is false for every `premium` and `exact_pa_all` row and true for a `none` row; **GIVEN** `flags = 1`, true for every `premium` row and false for `exact_pa_view`; **GIVEN** `flags = 2`, the reverse.
- **AC-13 [Logic] (R8)**: **GIVEN** a `feature_flags.csv` row with `requires = exact_pa_all, trial_eligible = true`, or `no_ads` with `trial_eligible = true`, **WHEN** the content validator runs, **THEN** it reports one error per such row; **GIVEN** an owner naming an `id` not in the table, **THEN** boot fails at seal naming the owner and the `id`.
- **AC-14 [Logic] (R10, F4)**: **GIVEN** a Free guild at tick 5,000,000 and `trial_max_h = 48`, **WHEN** `grant_trial(party_rearrange_all, 24)` runs, **THEN** `trial_until = 5,864,000` and `trial_started` is emitted; **WHEN** it runs again at tick 5,360,000, **THEN** `trial_until = 6,224,000`; **WHEN** `grant_trial(…, 100)` runs, **THEN** the duration is clamped to 48 h.
- **AC-15 [Logic] (R10, F3)**: **GIVEN** `trial_until = 1,000,000`, **THEN** `feature_on` is true at tick 999,999 and false at 1,000,000, and exactly one `trial_ended` is emitted in tick 1,000,000's P5.
- **AC-16 [Logic] (R10)**: **GIVEN** `flags = 1` (Premium), **WHEN** `grant_trial(party_lock, 24)` runs, **THEN** `trial_until` is unchanged and no event is emitted; **GIVEN** a feature with `trial_eligible = false`, **THEN** the grant is a no-op and logged to the host log sink as a content error.
- **AC-17 [Integration] (R1, Local save)**: **GIVEN** a guild saved with `flags = 1, source = 1` and a running trial, **WHEN** it is loaded in a fresh instance, **THEN** the view and the trial are restored without any `set_entitlement` command in the log, and an expired trial is not restored.
- **AC-18 [Integration] (Offline R4, equal cap)**: **GIVEN** a view with `flags = 1` at the hand-off and a 30 h gap, **WHEN** offline resolves, **THEN** the credited window is 12 h; **GIVEN** `flags = 0`, also 12 h, with bit-identical results. **GIVEN** `set_entitlement(1, 1)` submitted while the hand-off is pending, **THEN** the absence result is unchanged and the view becomes 1 on the next tick. **AND** `feature_flags.csv` has no `offline_cap_extended` row.
- **AC-19 [Integration] (Party R11)**: **GIVEN** `flags = 0`, **WHEN** `rearrange_all` is submitted, **THEN** refused `PARTY_PREMIUM_REQUIRED`; **GIVEN** a running `party_rearrange_all` trial, **THEN** it applies.
- **AC-20 [Logic] (no power sold)**: **GIVEN** two guilds with the same seed and the same host command log except for `set_entitlement`, played for 10,000 ticks plus a 30 h offline gap and no Premium-only commands, **THEN** their state hashes are identical (entitlement alone changes no simulation outcome).
- **AC-21 [Integration] [PENDING: engine] (R5)**: **GIVEN** a device with network off, **WHEN** Premium is bought through a store test account, **THEN** the banner is gone within 1 s of the store sheet closing.
- **AC-22 [UI] [PENDING: engine]**: Settings status line for `source = 1`, `2` and `3`, and a trial banner — one retained screenshot each in `production/qa/evidence/`.

Coverage: R1–R12 and F1–F4 each have at least one criterion (R11 via AC-4, R12 via AC-2's path). qa-lead lens: AC-21 is a device test; everything else runs headless in Python against the reference core once the section and command are added.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | Create `data/feature_flags.csv` (new content table, columns per R8) and add `provisional_grace_h`, `entitlement_refresh_min`, `trial_max_h` to `config.csv`? Not done here: a new content table is a schema change. | User / Data layer (3) | Before Alpha build |
| OQ-2 | **RESOLVED (user decision 2026-11-16):** equal offline cap for ranked play (12 h for everyone); Premium gets convenience only, no extra offline time. `offline_cap_extended` removed from R8; §11.2 "cap offline cao hơn" is overridden. Original: Premium's 24 h cap vs Free's 8 h let Premium progress further per real day on shared boards. | — | Closed |
| OQ-3 | Scope: "thêm lượt tuyển mộ/ngày" (Recruitment OQ-9), "thêm slot cloud save" (Account OQ-5) and "gói AI" (36) are §11.2 Premium suggestions not in the Wave 1 flag table. Add as rows when their owners design them? | User | Post Wave 1 |
| OQ-4 | R8 forbids trials of `no_ads` (`offline_cap_extended` no longer exists, OQ-2). §11.5 only gives "tự động xếp đội 24 giờ" as the example trial. Confirm the trial-eligible set. | User | Before Quests GDD |
| OQ-5 | Steam: which Steam DLC/ownership API maps to `exact_pa_all` and whether the PC build reads the same ledger (IAP OQ-6). | User, IAP | Post Wave 1 |
| OQ-6 | **NOT SOURCEABLE**: whether the Godot Android billing plugin can list owned purchases offline, and how fast (R5, F1 `store_purchased`). No `docs/engine-reference/godot/` module covers it. Verify in the P1 spike. | engine-programmer | P1 spike |
| PROVISIONAL-1 | **Ads (33)** — hides banner and rewarded placements when `feature_on(no_ads)`; reads the view, never IAP. | Ads | When 33 is designed |
| PROVISIONAL-2 | **Quests and achievements (25)** — reads `feature_on(ad_quest_direct_claim)` for rows with `premium_auto_claim = true`; grants trials only via `grant_trial(ctx, feature_uid, duration_h)` with `duration_h ≤ trial_max_h`; the reward-row format is Quests'. | Quests | When 25 is designed |
| PROVISIONAL-3 | **Leaderboards (35)** — decides the ranked policy for `source = 2/3` periods and any server cross-check (R11). | Leaderboards | When 35 is designed |
| PROVISIONAL-4 | **Event bus (42)** block 3200 and **Command layer (5)** type 3201 are allocated here per the "system number × 100" rule; IDs are proposals until a consistency pass. | Command layer / Event bus | Consistency pass |
| PROVISIONAL-5 | **Party (13)**, **CA/PA (9)**, **Recruitment (15)** currently read "Premium"/"`exact_pa_all`" directly; this GDD asks them to read `feature_on(<id>)` instead (R8). Their text is not edited here. | Those owners | Consistency pass |

**Post-design note (CD-GDD-ALIGN):** NOT ASSESSED — no pillars, concept or brief exist. Checked instead against GDD §11 text: the system keeps Premium to comfort and convenience only; the one exception, the offline cap, was removed by user decision 2026-11-16 (OQ-2).
