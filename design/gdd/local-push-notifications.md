# Local Push Notifications

> **Status**: Designed (pending independent `/design-review`)
> **Author**: design-system (autonomous batch run) + user direction in `JX1_Tycoon_GDD.md`
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no `design/gdd/game-pillars.md`). Serves `JX1_Tycoon_GDD.md` §1 ("Tycoon / Idle / AFK", "có offline progress"), §6.5 (hourly Golden Boss, missed bosses become a backlog of at most N) and §10 (offline cap; the 8 h Free / 24 h Premium split there is overridden by user decision 2026-11-16: 12 h for every player, Offline R4). The monolithic GDD never names notifications; this system is **inferred** by the systems index (row 46, Full Vision).
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no `game-pillars.md`, `game-concept.md` or game brief exist to check against; checked against GDD §1/§10 and this GDD's Player Fantasy instead (OQ-10)

## Summary

Local push notifications tell the player, when the game is not on screen, about the few moments where coming back actually changes something: the guild has used up its offline time and stopped working, missed Golden Bosses are starting to be lost, or (if the player asks for it) the next Golden Boss is about to arrive. They are computed on the device from saved timers at the moment the app is suspended, never sent from a server, never used for ads or offers, and they never touch the simulation.

> **Quick reference** — Layer: `Presentation` · Priority: `Full Vision` · Key deps: `Sim core and tick loop, Golden Boss and guild raid, Offline progress, Localization, Settings (provisional)`

## Overview

Local push notifications is a host-level presentation service outside the deterministic simulation (GDD §3.2 places services beside the core, not in it). It has two delivery paths. The **scheduled path** runs once, when the OS suspends or closes the app: it reads a handful of saved timers — when the Golden Boss is next due (Golden Boss R1), the offline high-water mark and cap (Offline progress R3/R4) — converts them from ticks to wall-clock time, and hands at most two notifications to the operating system's scheduler. Every pending notification is cancelled the moment the app returns. The **live path** exists only on desktop, where the game keeps running while minimised: it reads the tick's event batch through the Sim core's read-only facade (Sim core R15) and raises an OS notification for three event kinds already flagged by their owners (Golden Boss 1401, Recruitment 1501 rare variant, Endless Tower 1903). The system writes no simulation state, submits no commands, and is not part of the save, so it cannot affect determinism, leaderboards or parity tests. It exists because an idle game is played mostly while closed: without it, the 8-hour Free cap and the 3-boss backlog silently waste the player's guild time, and the player only learns this afterwards from the absence report.

## Player Fantasy

**Indirect.** The player does not "use" notifications; they feel the guild reaching out at the right moment.

Chosen framing — **"Word from the guild hall."** *The moment:* the bang chủ (guild master) closed the game before dinner; at 08:00 the next morning, one line arrives: "Your guild has worked the full 12 hours and is resting. Come and see what they brought back." The player opens the app to a full absence report, not to a guilt trip. The fantasy is that the guild is a living household that sends a runner when there is real news, and is otherwise quiet. It asks of the design: very few messages (R8), messages only when returning changes the outcome (R4), quiet hours (R7), and plain, factual text (R9).

Candidate framings considered (lens: creative direction, autonomous run):
- (A) "Word from the guild hall" — chosen, above.
- (B) "The hourly drum" — every Golden Boss announced, the guild calling the master to battle. Rejected as the default: hourly messages contradict "Idle / AFK" (§1) and would be the most-muted notification in the game. Kept as an opt-in kind (`boss_soon`, default off).
- (C) "Nothing slips away" — notify on every lost opportunity. Rejected: it turns the cap into fear of missing out, which works against an idle game whose promise is that the guild works without the player.

No pillar exists to quote; the anchor is GDD §1 ("Idle / AFK") and §10. Re-check when pillars are written (OQ-10).

## Detailed Design

### Core Rules

**R1 — Outside the simulation.** The service is constructed by the host, like Account and cloud save. It reads (a) committed state between ticks — Golden Boss `next_slot_tick`, Offline progress `hw_utc` and `cap_s`, Sim core `tick` and `tick_rate` — and (b) the P6 event batch through the Sim core facade (R15). It never writes simulation state, never submits a command, never calls the RNG, and owns no save section. Removing the service entirely changes no simulated result.

**R2 — Two delivery paths, chosen by platform state.**

| App state | Mobile (Android, later iOS) | Desktop (PC/Steam) |
|---|---|---|
| Foreground, focused | Nothing. In-app UI (badges, world view) handles it. | Nothing. |
| Running, not focused / minimised | (Mobile has no such state: losing focus without suspension keeps frames running and the app visible) | **Live path** (R6) |
| Suspended or closed | **Scheduled path** (R5) | Nothing: no process runs, and PC scheduling is out of scope (OQ-5) |

Web: no notifications in this version (OQ-5).

**R3 — Permission and opt-in.**
1. Before the OS permission is granted, the service schedules and raises nothing.
2. The game asks for permission **once**, through an in-game pre-prompt that explains the two default kinds, at the first **trigger moment**: the first time the player dismisses an absence report whose `capped` flag is true (Offline progress R11), or the first time the absence report shows a missed boss — whichever comes first, and never during onboarding (44) or within the first session. A capped absence is the moment the notification would have helped, so the ask lands when its value is obvious.
3. The pre-prompt has two buttons: "Notify me" (shows the OS permission dialog; on Android 13+ the POST_NOTIFICATIONS runtime permission) and "Not now". "Not now" or an OS denial ends automatic asking for good. After that, the only route is the Settings toggle (R12), which opens the OS app-notification settings when the OS permission is denied.
4. Where the OS needs no runtime permission (Android 12 and lower, desktop), the pre-prompt still runs once and sets the master toggle; the game never notifies a player who has not said yes in-game.

**R4 — The notification kinds.** Kinds are fixed by this GDD; their default state and timing values are data (Tuning Knobs).

| Kind | Path | Default | Fires when | Tap opens |
|---|---|---|---|---|
| `offline_cap_reached` | scheduled | on | The credited offline window ends: the guild stops working (Offline R4 frozen time). F2. | App → absence report |
| `boss_backlog_full` | scheduled | on | The first Golden Boss slot that will be **lost** is crossed: slot number `golden_boss_backlog_max + 1` after suspension inside the credited window (Golden Boss R16 keeps only the last 3). F3. | App → absence report |
| `boss_soon` | scheduled | **off** | `notif_boss_soon_lead_s` before the first Golden Boss slot that is at least `notif_boss_soon_min_wait_s` after suspension, if it lies inside the credited window. F4. Only one per absence. | App → world view at headquarters |
| `boss_announced` | live | on | Event 1401 `gb_announced` (Golden Boss R2) | Focus the window, world view |
| `rare_candidate` | live | on | Event 1501 with the rare variant (candidate of four stars or more, Recruitment Visual/Audio) | Focus the window, recruitment board |
| `tower_run_ended` | live | on | Event 1903 `tower_run_ended` (Endless Tower) | Focus the window, tower result |

No other kind exists. Specifically, there is **no** generic "come back" reminder, no streak or daily-login reminder, no daily-quest reminder, no shop, ad, sale or IAP message (R11).

**R5 — The scheduled path.**
1. **When.** On the OS suspend/close notification, after Local save has collected and written its save at that same hook (Local save R8), so the values read are the ones saved. If the save was refused (a hand-off pending, Local save R8), the service reads the same committed state the previous save holds and proceeds; the timers it reads only change inside ticks.
2. **Cancel first.** Cancel every notification this app has pending with the OS.
3. **Compute.** Take `suspend_utc = GameClock.utc_s()` once. Compute each enabled kind's fire time (F1–F4). Drop a kind whose time is invalid (outside the credited window, or not in the future).
4. **Quiet hours** (R7), then **caps** (R8), then **render** (R9).
5. **Schedule** the survivors with the OS as inexact (non-exact-alarm) local notifications.
6. **On resume or cold start** (the first `advance` after resume, or `start()` on a loaded save): cancel every pending notification. The player is here; anything still pending is stale.

Because each suspend cancels and recomputes, the scheduled set is always a pure function of the saved timers, `suspend_utc`, settings and locale. Nothing about it needs saving.

**R6 — The live path (desktop only).** While the window is unfocused or minimised and not suspended, after each tick the service reads that tick's batch from the facade. For each event matching an enabled live kind it raises one OS notification at once, subject to R7 and R8. While the core is `catching_up` (Sim core R15/R17) the service raises nothing for those ticks: replayed catch-up events are old news. A hand-off produces no per-tick events (Event bus R12), so an absence resolution never triggers the live path.

**R7 — Quiet hours.** Default 22:00 to 08:00 in the device's local time zone. This is the only place the game uses local time, and it never reaches the simulation. A notification whose fire time falls in quiet hours is:
- **moved** to the end of quiet hours, if its kind stays true afterwards: `offline_cap_reached` and `boss_backlog_full` (the guild is still stopped, bosses are still being lost);
- **dropped**, if it would be stale: `boss_soon` and every live kind.
The player can change both bounds or turn quiet hours off (R12). Equal start and end means no quiet hours.

**R8 — Frequency caps.**
1. At most `notif_max_per_absence` (2) scheduled notifications per suspension.
2. At most `notif_max_live_per_hour` (3) live notifications in any rolling 60 minutes; extras are dropped, not queued.
3. When the scheduled set is over the cap, keep by priority `offline_cap_reached` > `boss_backlog_full` > `boss_soon`.
4. **Collapse.** If two scheduled notifications land within `notif_collapse_window_s` (15 minutes) of each other after quiet-hour moves, keep only the higher-priority one. The cap message already tells the player to come back.

**R9 — Text.** Each kind has `ui_notif_<kind>_title` and `ui_notif_<kind>_body` keys in `i18n/ui_{loc}.csv`, rendered in the active locale at schedule time (Localization R10) with ICU arguments: guild display name, hours worked (`cap_s / 3600`), boss local due time as `HH:MM`, candidate star count. Text is factual and short; it states what happened and what returning gives. It never uses guilt, urgency words ("hurry", "last chance") or countdowns. Because every pending notification is cancelled on resume (R5.6), a locale switch — always made in the foreground — finds nothing pending; Localization R10's re-schedule obligation is met trivially.

**R10 — Tap behaviour.** A notification carries only its kind ID as payload: no state, no tick, no IDs. Tapping it opens (or focuses) the app; once the absence resolves, the app routes to the screen in R4's "Tap opens" column. If that screen is unavailable (feature not unlocked, content wave locked), the app shows its normal start screen. The payload is untrusted input: an unknown kind is ignored.

**R11 — What notifications may never do.** Never advertise, sell, announce sales or premium, request reviews, or remind about streaks, logins or quests. Free and Premium players get the same kinds, text and times: the offline cap is the same for every player (Offline R4, user decision 2026-11-16). This rule is part of the design, not a tuning choice; changing it is a scope decision for the user.

**R12 — Settings.** Stored as device-local preferences owned by Settings (45), **not** in the game save and not in the cloud (a phone and a PC can want different behaviour): master toggle, one toggle per kind (R4 defaults), quiet hours on/off, start and end hour. The Settings screen shows the OS permission state and, when denied, a button that opens the OS settings page.

### States and Transitions

**Permission state** (device-local, Settings preference):

| State | Meaning | Transitions |
|---|---|---|
| `NotAsked` | Pre-prompt never shown | → `Granted` ("Notify me" + OS allow); → `Declined` ("Not now" or OS deny) |
| `Granted` | Master toggle may be on | → `Revoked` (OS permission found withdrawn at resume); master toggle off/on stays in `Granted` |
| `Declined` | Player said no in game or OS | → `Granted` only via Settings toggle + OS allow |
| `Revoked` | OS permission withdrawn outside the game | → `Granted` via Settings + OS allow |

The service is **active** only in `Granted` with the master toggle on.

**Scheduled notification lifecycle:**

| State | Enter | Exit |
|---|---|---|
| `Computed` | R5.3 produced a valid time | → `Dropped` (R7 stale, R8 cap or collapse); → `Scheduled` |
| `Scheduled` | Handed to OS | → `Delivered` (OS shows it); → `Cancelled` (resume, next suspend) |
| `Delivered` | Shown | → (tapped) app opens, R10 |

### Interactions with Other Systems

| System | Direction | Data | Owner of interface |
|---|---|---|---|
| Sim core and tick loop (1) | in | `tick`, `tick_rate`, `GameClock.utc_s()`, facade event batch and `catching_up` (R7, R15); the suspend/resume host hook | Sim core |
| Golden Boss and guild raid (14) | in | Saved `next_slot_tick`, `golden_boss_interval_min`, `golden_boss_backlog_max`; event 1401 | Golden Boss |
| Offline progress (31) | in | `hw_utc`, `cap_s` (Offline R3, R4; its Dependencies row: "cap reached time `hw_utc + cap_s`"); summary `capped` flag and missed bosses for the R3 trigger | Offline progress |
| Localization (4) | in | `ui_notif_*` keys, ICU formatting, active locale (R10) | Localization |
| Settings (45) | in | Device-local preferences (R12) and permission state; screen rows | Settings (PROVISIONAL) |
| Local save and migration (6) | order | Scheduled path runs after the suspend save (R5.1) | Local save |
| Recruitment (15) | in | Event 1501, rare variant | Recruitment |
| Endless Tower (19) | in | Event 1903 | Endless Tower |
| Onboarding (44) | in | "Onboarding complete" flag to gate the R3 ask | Onboarding (PROVISIONAL) |
| Guild screens (39), Realtime world view (38) | out | Deep-link route by kind (R10) | Those screens (PROVISIONAL) |
| Analytics (37) | out | Opt-in result, kind scheduled, kind tapped (counts only) | Analytics (PROVISIONAL) |

## Formulas

### F1 — Tick to wall-clock time

The tick_to_utc formula is defined as:

`tick_to_utc(due_tick) = suspend_utc + ceil((due_tick − tick) / tick_rate)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `suspend_utc` | int (s) | ≥ 0 | calculated (`GameClock.utc_s()` at suspend) | Wall time at suspension |
| `due_tick` | int | ≥ `tick` | saved state of the owning system | Tick a timer fires |
| `tick` | int | ≥ 0 | Sim core | Current committed tick |
| `tick_rate` | int (ticks/s) | 1–20 (registry: 10) | data file (`config.csv`, Sim core) | Simulation rate |

**Output Range:** `suspend_utc` to `suspend_utc + (due_tick − tick)/tick_rate`, rounded up to the whole second. If `due_tick < tick` (should not happen: R5 runs between ticks, after the timer handler ran) the kind is dropped, never scheduled in the past.
**Example:** `tick = 1,000,000`, `due_tick = 1,012,005`, `tick_rate = 10`, `suspend_utc = 1,795,000,000` → `1,795,000,000 + ceil(1,200.5) = 1,795,001,201`.

Why this is correct across the absence: while the app is closed no ticks run, and on return the gap is replayed or handed off (Sim core R7/R8), so tick `t` corresponds to `suspend_utc + (t − tick)/tick_rate` of real time **only inside the credited window**. F2 bounds every other formula to that window.

### F2 — Offline cap reached

The cap_reached_utc formula is defined as:

`cap_reached_utc = max(suspend_utc, hw_utc) + cap_s`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `suspend_utc` | int (s) | ≥ 0 | calculated | As F1 |
| `hw_utc` | int (s) | ≥ 0 | saved state (Offline progress R3) | High-water mark of trusted time; normally equals `suspend_utc` after the suspend save |
| `cap_s` | int (s) | 3,600 – 86,400 (43,200 default) | calculated by Offline R4 as `offline_cap_free_h` (12) × 3,600, data file | Credited window length, the same for every player |

**Output Range:** 1 h to 24 h after suspension under the knob range (12 h at default). When the device clock was set back earlier (`hw_utc > suspend_utc`), Offline credits nothing until real time passes `hw_utc`, so the guild works later; `max` moves the notification by the same amount and it stays true.
**Example:** any player, `suspend_utc = hw_utc` = 19:30 local → `cap_reached_utc` = 07:30 → in quiet hours (R7) → moved to 08:00. Suspended at 21:30 instead, the cap is reached at 09:30, outside quiet hours, and fires then.

### F3 — First lost Golden Boss

The backlog_full_utc formula is defined as:

`slot_due(j) = next_slot_tick + (j − 1) × interval_ticks`, with `interval_ticks = golden_boss_interval_min × 60 × tick_rate`

`backlog_full_utc = tick_to_utc(slot_due(golden_boss_backlog_max + 1))`, **valid only if** `backlog_full_utc ≤ cap_reached_utc`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `next_slot_tick` | int | > `tick` | saved state (Golden Boss R1) | Due tick of the next hourly slot |
| `j` | int | ≥ 1 | calculated | Slot number counted from suspension |
| `golden_boss_interval_min` | int (min) | registry: 60 | data file (`config.csv`, Golden Boss) | Slot spacing |
| `golden_boss_backlog_max` | int | registry: 3 | data file (`config.csv`, Golden Boss) | Slots kept as backlog |
| `tick_rate` | int | registry: 10 | data file | As F1 |

**Output Range:** with the registry values, 3 h 0 s to 4 h after suspension (the 4th slot). If `golden_boss_backlog_max = 0`, the first slot is already lost and F3 gives the first slot (0–1 h). Invalid (dropped) whenever the 4th slot lies past the cap — e.g. if a future cap knob were set below 4 h.
**Example:** suspend 19:30, `next_slot_tick` maps to 19:50 → slots 19:50, 20:50, 21:50, 22:50 → `backlog_full_utc` = 22:50 ≤ 07:30 → valid → quiet hours → moved to 08:00 → collapses with the 08:00 cap notification (R8.4) → only `offline_cap_reached` is scheduled.

The summon horn's queued slot (Golden Boss R13) is not predicted; it needs the app open, and no horn can be used while closed.

### F4 — Next boss soon (opt-in)

The boss_soon_utc formula is defined as:

`j* = smallest j ≥ 1 with tick_to_utc(slot_due(j)) − suspend_utc ≥ notif_boss_soon_min_wait_s`

`boss_soon_utc = tick_to_utc(slot_due(j*)) − notif_boss_soon_lead_s`, **valid only if** `tick_to_utc(slot_due(j*)) ≤ cap_reached_utc`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `notif_boss_soon_min_wait_s` | int (s) | 300 – 3,600 (default 900) | data file (`config.csv`, new) | Skip a slot that is so close the player just left it |
| `notif_boss_soon_lead_s` | int (s) | 120 – 1,800 (default 600) | data file (`config.csv`, new) | How long before the slot the message fires |
| others | | | | As F1, F3 |

**Output Range:** `min_wait − lead` to `min_wait − lead + interval` seconds after suspension; with defaults, 5 min to 65 min. Constraint `notif_boss_soon_lead_s < notif_boss_soon_min_wait_s` (validator), else the time could be before suspension.
**Example:** suspend 21:30, next slot 21:50 (20 min ≥ 15 min) → `j* = 1` → fires 21:40 with text "The Golden Boss arrives at 21:50."

The lead is long (10 min) because OS delivery is inexact (R5.5): the text states the absolute time, so a late delivery is self-evidently late rather than misleading. If the player opens the app before the slot is due, the slot fires live; after, it is resolved as backlog (Golden Boss R16).

### F5 — Quiet-hour shift

The shifted_utc formula is defined as:

`shifted(t) = t` if `local_hour_min(t) ∉ [q_start, q_end)`, else `next_local(q_end)` after `t` (movable kinds) / dropped (stale kinds, R7)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| `t` | int (s) | ≥ `suspend_utc` | calculated (F2–F4) | Fire time |
| `q_start`, `q_end` | int (minute of day) | 0–1,439 (defaults 1,320 = 22:00, 480 = 08:00) | player preference, defaults in data file (`config.csv`, new) | Quiet window; wraps midnight when `q_start > q_end`; empty when equal |

**Output Range:** `t` to `t + 24 h`. Time-zone and daylight-saving changes are taken from the OS at suspend time; a change during the absence is not tracked (Edge Cases).
**Example:** `t` = 05:30, window 22:00–08:00 → 08:00 the same morning.

## Edge Cases

- **If the app is killed by the OS without a suspend notification** (crash, force-stop): no new schedule is made; whatever the last suspend scheduled stays pending and may fire. Each pending notification was correct for that suspension, and the resume cancels it. Accepted.
- **If the player opens the app before a scheduled notification fires**: R5.6 cancels it; it never appears.
- **If the device clock is moved forward or back during the absence**: OS schedulers usually fire on wall-clock, so notifications may fire early or late. No reward depends on them (R1); Offline progress's own clock policy decides credit. Accepted.
- **If `hw_utc` is far ahead of `suspend_utc`** (clock was set back earlier): F2 moves the cap message by the same amount, and F3/F4 are computed from `suspend_utc` but checked against that later cap. Bosses inside frozen time are shifted, not crossed (Offline R8), so F3/F4 can be early; they stay true in direction ("bosses are being lost" happens no earlier than claimed). Accepted; OQ-7.
- **If the player is Premium**: identical to Free — same cap (12 h), same kinds, same times (Offline R4, user decision 2026-11-16).
- **If entitlement changes while closed** (refund or purchase): nothing here changes; `cap_s` does not depend on entitlement.
- **If two scheduled notifications collapse and the dropped one was the more informative** (backlog full before cap): accepted by R8.4; the absence report shows missed bosses.
- **If a time-zone or daylight-saving change happens during the absence**: quiet hours were computed in the zone at suspend; a message may arrive an hour off. Accepted.
- **If the OS permission is revoked while notifications are pending**: the OS discards them. At next resume the state becomes `Revoked`.
- **If the saved timers are unavailable** (save failed and no committed state: new guild before first tick): schedule nothing.
- **If the game is in an in-app pause (Sim core R9) when suspended**: the schedule continues (Golden Boss R1: pause does not stop the schedule), and the absence is credited the same way, so F1–F4 are unchanged.
- **If the desktop app is minimised while catching up after sleep**: R6 raises nothing until `catching_up` is false; a 1401 emitted during catch-up is not notified.
- **If a 1401 and a 1501 arrive in the same tick on desktop**: both are raised in emission order, counting two toward R8.2.
- **If the core is `Failed`** (Sim core R10): live path stops; scheduled path does not run at suspend (state is untrusted).
- **If a content wave locks the deep-link screen**: R10 falls back to the start screen.
- **Degenerate strategy check:** no notification gives or withholds a reward, so there is nothing to farm. The only exploit surface is spam toward the player, bounded by R8.

## Dependencies

| System | Direction | Hard/Soft | Interface | Status |
|---|---|---|---|---|
| Sim core and tick loop (1) | upstream | Hard | `tick`, `tick_rate`, `GameClock`, facade (R15), suspend/resume hook (R7) | GDD exists — conforms; its row lists 46 as Soft dependent on `tick`, `GameClock` |
| Golden Boss and guild raid (14) | upstream | Hard | `next_slot_tick` (R1), interval, `golden_boss_backlog_max` (R16), 1401 (R2) | GDD exists — conforms; lists 46 as a consumer of 1401 |
| Offline progress (31) | upstream | Hard | `hw_utc`, `cap_s`, summary `capped` and missed bosses | GDD exists — conforms to its row "cap reached time (`hw_utc + cap_s`)"; this GDD uses `max(suspend_utc, hw_utc)` (same value in the normal case) |
| Localization (4) | upstream | Hard | `ui_notif_*` keys, R10 | GDD exists — conforms; answers its OQ-4 for this system |
| Settings (45) | upstream | Hard | Device-local preferences, permission row | No GDD — PROVISIONAL (OQ-1) |
| Local save and migration (6) | upstream | Soft | Ordering at the suspend hook | GDD exists — conforms (R8) |
| Recruitment (15) | upstream | Soft | 1501 rare variant | GDD exists — conforms |
| Endless Tower (19) | upstream | Soft | 1903 | GDD exists — conforms |
| Onboarding (44) | upstream | Soft | Onboarding-complete flag | No GDD — PROVISIONAL (OQ-2) |
| Realtime world view (38), Guild screens (39) | downstream | Soft | Deep-link routes | No GDD — PROVISIONAL (OQ-3) |
| Analytics (37) | downstream | Soft | Opt-in and tap counts | No GDD — PROVISIONAL (OQ-4) |
| Rebirth and Ascension (23) | — | none | Lists 46 as a reader of `rebirth_status`; this GDD defines no rebirth kind | OQ-6 |

**Bidirectional check:** the index row lists Sim core, Golden Boss, Offline progress; all three list 46 as a dependent. This GDD adds Localization and Settings as hard links (index updated). Recruitment, Endless Tower and Rebirth list 46 from their side; Recruitment and Tower are honoured as live kinds, Rebirth is not (OQ-6).

## Tuning Knobs

All in `data/config.csv` (new keys; Data layer validator to range-check them).

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `notif_default_cap_reached` | 1 (on) | 0/1 | — | Main value of the system lost | — |
| `notif_default_backlog_full` | 1 (on) | 0/1 | — | — | collapse window |
| `notif_default_boss_soon` | 0 (off) | 0/1 | On by default → hourly-feeling nudges, opt-outs | — | `notif_max_per_absence` |
| `notif_default_live_kinds` | 1 (on) | 0/1 | — | Desktop players miss raids | `notif_max_live_per_hour` |
| `notif_max_per_absence` | 2 | 1–3 | Spam; more opt-outs | Backlog message never survives | priority order R8.3 |
| `notif_max_live_per_hour` | 3 | 1–6 | Desktop spam (1401 is hourly + horn) | Rare candidates dropped | Golden Boss cadence |
| `notif_collapse_window_s` | 900 | 0–3,600 | Distinct messages merged | Two messages a minute apart | quiet hours |
| `notif_boss_soon_lead_s` | 600 | 120–1,800; < `min_wait` | Message long before the fight | Inexact delivery arrives after the slot | `notif_boss_soon_min_wait_s` |
| `notif_boss_soon_min_wait_s` | 900 | 300–3,600 | Skips a reachable slot | Message right after leaving | `lead_s` (must stay greater) |
| `notif_quiet_start_min` | 1,320 (22:00) | 0–1,439 | — | — | `quiet_end` (equal = off) |
| `notif_quiet_end_min` | 480 (08:00) | 0–1,439 | — | — | `quiet_start` |

Owned elsewhere and read here: `tick_rate` (Sim core), `golden_boss_interval_min`, `golden_boss_backlog_max` (Golden Boss), `offline_cap_free_h` (Offline progress; the one cap for every player, `offline_cap_premium_h` deprecated). A cap below 4 h makes `boss_backlog_full` inert (F3 invalid); a backlog max of 0 makes it fire within the first hour.

## Visual/Audio Requirements

Meta category: optional, brief. No art bible exists (`design/art/art-bible.md` absent); drafted from GDD §1 (pixel 2D).
- **Android status-bar icon:** monochrome silhouette of the guild banner, white on transparent, per Android small-icon rules; large icon = app icon.
- **Sound:** OS default notification sound on one Android notification channel per group ("Guild news" for scheduled kinds, "Golden Boss" for `boss_soon`), so the player can silence one in OS settings. No custom sound in this version.
- **No images, no rich media.**

## Game Feel

Not a feel system. One target: the pre-prompt (R3) must appear only after the absence report is dismissed, never over it, so asking never interrupts the reward moment.

## UI Requirements

- **Pre-prompt dialog** (R3): title, two sentences naming the two default kinds, "Notify me" / "Not now". Localized; fits at phone width with Vietnamese text (longer than English).
- **Settings rows** (owned by Settings 45): master toggle; per-kind toggles (six, live kinds shown only on desktop); quiet hours toggle + start/end pickers; permission status line and "Open system settings" button when denied/revoked.
- No in-game notification centre or history; the Chronicle and absence report already cover history.

> **📌 UX Flag — Local push notifications**: run `/ux-design` for the pre-prompt and the Settings rows before epics.

## Cross-References

| This GDD | References | Element | Nature |
|---|---|---|---|
| R1, R6, F1 | `sim-core-and-tick-loop.md` | R7 GameClock and absences, R15 facade, `tick_rate` | Reads |
| R4, F3, F4 | `golden-boss-and-guild-raid.md` | R1 schedule, R2 1401, R13 horn, R16 backlog, `golden_boss_backlog_max` | Reads |
| R3, F2 | `offline-progress.md` | R3 `hw_utc`, R4 cap and frozen time, R8 shifted due ticks, R11 summary | Reads |
| R9 | `localization.md` | R10 push text at schedule time | Conforms |
| R5.1 | `local-save-and-migration.md` | R8 suspend save | Ordering |
| R4 | `recruitment.md` | 1501, rare variant (four stars+) | Reads |
| R4 | `endless-tower.md` | 1903 `tower_run_ended` | Reads |
| — | `rebirth-and-ascension.md` | Lists 46 as reader of `rebirth_status` | Not honoured (OQ-6) |

## Acceptance Criteria

Story types: AC-1…AC-9, AC-13, AC-14 are Logic (unit test with a fake clock, fake OS scheduler and fixed saved state). AC-10…AC-12 are Integration (on device). AC-15 is UI (screenshot).

- **AC-1 (R1)**: **GIVEN** a parity run of 10,000 ticks plus one suspend/resume, **WHEN** run with the service present and with it removed, **THEN** the state hash and event log are identical.
- **AC-2 (F1)**: **GIVEN** `tick = 1,000,000`, `tick_rate = 10`, `suspend_utc = 1,795,000,000`, **WHEN** `tick_to_utc(1,012,005)`, **THEN** 1,795,001,201; **WHEN** `tick_to_utc(1,000,000)`, **THEN** 1,795,000,000.
- **AC-3 (F2)**: **GIVEN** the default cap (`cap_s = 43,200`) on a Free and on a Premium account, `hw_utc = suspend_utc = S`, quiet hours off, **WHEN** suspended, **THEN** exactly one `offline_cap_reached` is scheduled at `S + 43,200` for both; **GIVEN** `hw_utc = S + 3,600`, **THEN** at `S + 46,800`.
- **AC-4 (F3)**: **GIVEN** next slot 1,200 s after suspend, interval 60 min, backlog max 3, default cap, quiet hours off, **WHEN** suspended, **THEN** `boss_backlog_full` is scheduled at `S + 1,200 + 3 × 3,600 = S + 12,000`; **GIVEN** `offline_cap_free_h = 3`, **THEN** it is not scheduled.
- **AC-5 (F4)**: **GIVEN** `boss_soon` enabled, lead 600, min wait 900, next slot at `S + 1,200`, **WHEN** suspended, **THEN** `boss_soon` at `S + 600`; **GIVEN** next slot at `S + 600`, **THEN** at `S + 600 + 3,600 − 600 = S + 3,600`.
- **AC-6 (R7, F5)**: **GIVEN** quiet 22:00–08:00 and a cap time of 05:30 local, **THEN** it is scheduled at 08:00; **GIVEN** a `boss_soon` time of 23:10, **THEN** it is dropped.
- **AC-7 (R8.4)**: **GIVEN** the F3 example (suspend 19:30, slots from 19:50, default cap, default quiet hours), **WHEN** suspended, **THEN** only `offline_cap_reached` at 08:00 is scheduled.
- **AC-8 (R8.1, R8.3)**: **GIVEN** all three scheduled kinds valid and distinct, quiet hours off, **WHEN** suspended, **THEN** exactly `offline_cap_reached` and `boss_backlog_full` are scheduled.
- **AC-9 (R5.2, R5.6)**: **GIVEN** two pending notifications, **WHEN** the app resumes, **THEN** the fake OS has zero pending; **WHEN** suspended twice in a row, **THEN** the second schedule fully replaces the first.
- **AC-10 (R3)** [Integration]: **GIVEN** a fresh install past onboarding, **WHEN** the first capped absence report is dismissed, **THEN** the pre-prompt appears once; **WHEN** "Not now" is chosen and five more capped reports are dismissed, **THEN** it never appears again and nothing is scheduled at suspend.
- **AC-11 (R3.3)** [Integration, Android 13+]: **GIVEN** the OS permission denied, **WHEN** the Settings toggle is tapped, **THEN** the OS app-notification page opens.
- **AC-12 (R6)** [Integration, desktop]: **GIVEN** the window minimised, **WHEN** a 1401 is emitted, **THEN** one OS notification appears; **GIVEN** `catching_up` is true, **WHEN** a 1401 is emitted, **THEN** none appears.
- **AC-13 (R8.2)**: **GIVEN** desktop live path and four matching events within 30 min, **THEN** three notifications are raised and the fourth is dropped.
- **AC-14 (R9, R11)**: **GIVEN** locale `vi` then `en`, **WHEN** a schedule is made, **THEN** title/body come from `ui_notif_*` keys in that locale; **AND** a grep of `i18n/ui_*.csv` `ui_notif_*` values contains no store, ad, sale or premium wording, and the set of scheduled kinds is identical for Free and Premium fixtures except the F2 time.
- **AC-15 (UI)**: screenshots of the pre-prompt and the Settings rows in both locales at 360 px width, in `production/qa/evidence/`.

Coverage: R1 AC-1; R2 AC-9/AC-12; R3 AC-10/11; R4 AC-3–5/12; R5 AC-9; R6 AC-12; R7 AC-6; R8 AC-7/8/13; R9/R11 AC-14; R10 has no automated criterion (playtest: tap each kind, check the screen); R12 AC-15. F1–F5 each have a criterion with a boundary value.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **PROVISIONAL: Settings (45)** — assumes it owns device-local preferences (not save, not cloud) and hosts the notification rows and permission state (R12). | Settings GDD | Before 46 is built |
| OQ-2 | **PROVISIONAL: Onboarding (44)** — assumes an "onboarding complete" flag readable by the host to gate R3. | Onboarding GDD | Alpha |
| OQ-3 | **PROVISIONAL: World view (38), Guild screens (39)** — assumes routes for absence report, headquarters, recruitment board and tower result reachable from a kind ID. | Those GDDs | Full Vision |
| OQ-4 | **PROVISIONAL: Analytics (37)** — assumes counts-only events (opt-in, scheduled kind, tapped kind), honouring ad/analytics consent. | Analytics GDD | Full Vision |
| OQ-5 | **Scope (not decided, scope change):** scheduled notifications on PC/Steam (needs OS-scheduled toasts with no running process) and on Web (Push API needs a server and service worker, which contradicts "local"). Kept out per the index. | User | Before PC port |
| OQ-6 | Rebirth (23) and other GDDs list 46 as a reader of their events (`rebirth_status`). Adding kinds is a scope decision; none added. | User | Full Vision |
| OQ-7 | Offline progress: confirm `hw_utc` equals `suspend_utc` after the suspend save, and that shifted (frozen-time) slots make F3/F4 at most early, never late. | Offline progress | Consistency pass |
| OQ-8 | **Engine — NOT SOURCEABLE:** Godot 4.7 local-notification scheduling on Android (plugin or AAR, notification channels, POST_NOTIFICATIONS, inexact alarms) and desktop toast APIs are not covered by `docs/engine-reference/godot/` (no `core.md`, no notification entry). Decide in an ADR after a device spike. | Technical director | Before 46 epic |
| OQ-9 | **Schema (not decided, schema change):** the knobs above are new `config.csv` keys; the Data layer owns the validator ranges, including `lead_s < min_wait_s`. | Data layer | When built |
| OQ-10 | CD-GDD-ALIGN NOT ASSESSED: no pillars. Re-run when `game-pillars.md` exists; especially R11 and the default-off `boss_soon`. | Creative director | When pillars exist |
| OQ-11 | Store policy: confirm Google Play policy on notification content and permission prompts matches R3/R11 before launch. | User | Before release |

**Engine feasibility note.** Domain: Core (Meta). `docs/engine-reference/godot/modules/` has no `core.md`; feasibility not checked against the pinned engine (OQ-8). No ADR in `docs/architecture/` covers this system. Specialists not spawned: lenses for `systems-designer` (primary, Foundation/Infrastructure row for Meta), `gameplay-programmer`, `engine-programmer`, plus `ux-designer` for the permission flow, applied in this autonomous session.
