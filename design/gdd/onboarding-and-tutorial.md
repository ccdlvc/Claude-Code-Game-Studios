# Onboarding and Tutorial

> **Status**: Designed (pending independent /design-review)
> **Author**: user + Claude (autonomous batch run, decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against (see the post-design note at the end of Open Questions)
> **Implements Pillar**: None (no game-pillars.md yet). Serves GDD §4.3 "Đầu game **nhanh** để tạo hứng" and its "thưởng tân thủ" lever, §2 "Single-player offline", and the §11.2 rule "không dùng quảng cáo xen kẽ (interstitial) làm gián đoạn gameplay".

## Summary

Onboarding and tutorial teaches a new guild master the core loop of JX1 Tycoon in the first session: hire people, watch them team up, send them hunting, see them come back stronger. It does this with short, non-blocking coach cards that complete when the player actually does each thing, plus one-time tips that appear the first time something new happens later (the first Golden Boss, the first injury, the first offline report). It also owns the "newbie bonus" — triple hunt XP for the first 30 minutes of play — that GDD §4.3 names as the way to make the opening fast without bending the level curve. Its progress lives in the guild save, so a restored or cloud-synced guild never repeats a lesson.

> **Quick reference** — Layer: `Polish` · Priority: `Alpha` · Key deps: `Event bus and history log (42)`, `Command layer (5)`, `Recruitment (15)`, `Zones and hunt (11)`, `Guild screens (39, PROVISIONAL)`, `Realtime world view (38, PROVISIONAL)`, `Local save (6)`, `Localization (4)`

## Overview

Onboarding has two halves. The **tracker** is a small simulation-side system: it subscribes to the Event bus (42) for the handful of event types that prove the player has done something for the first time, keeps a bitmask of which lessons are done, owns two host commands (acknowledge a card, skip the tutorial), owns a countdown of simulated ticks during which hunt XP is tripled, and saves all of that under its own `onboarding` save section. The **coach layer** is presentation: it reads the tracker's state through the Sim core facade and draws a coach card, a highlight ring around the relevant button or world object, and a short "done" toast when a step completes. The player meets a **first-session chain** of seven steps (welcome → first hire → first party → first hunt → first level-up → first return → keep your guild safe), which takes about one hunt trip (~15–20 minutes), and then a set of **just-in-time tips** that each show once, at the moment their subject first appears. Onboarding never pauses the simulation, never locks the screen, never shows an ad or a shop offer, and never grants gold or items; the only gameplay value it changes is the newbie XP window. Long-term goals (first building, next zone, rebirth) belong to Quests and achievements (25), not here. Implementation choices — the overlay scene, how highlight anchors are registered, and whether the coach layer is one autoload or per-screen nodes — become ADRs.

*Framing: both — the tracker is described as infrastructure, its player effect is stated (Meta category; the coach layer is player-facing). No ADR exists yet, so none is cited.*

## Player Fantasy

**"I opened the gates, and the guild came alive — and I understood why."**

This system is experienced indirectly. The fantasy it serves is the game's own: the player is a *Bang chủ* who runs a living guild (GDD §1). Onboarding succeeds when the player never feels "taught". They tap a walk-in candidate because the card says three people are waiting at the gate; within minutes the first five have teamed up on their own and set off for Thanh Thảo Cốc (zone_01, tagged "tutorial" in GDD §6.3); a quarter of an hour later they walk back in, bags full, one of them a level higher. The tutorial's last card asks only whether the player wants the guild backed up. Everything after that is discovery: the first time the drum of the Golden Boss sounds, a single line explains what it is and that the guild will answer it without help.

The anchor moment is the **first return**: the party coming home on screen, the gold ticking into the fund, a "Lan reached level 3" toast. That moment is where an idle tycoon's promise — *they get stronger while you watch* — is proved, and §4.3's fast opening (with the newbie XP window) exists to put it inside the first session.

Candidate framings considered (creative-director lens, no agent spawned; no pillars exist, so framings were anchored to GDD §1, §4.3 and §6.3):
1. *"The guild came alive"* (chosen) — anchors on the first return; asks the rest of the design for a first trip short enough to finish in one session (Hunt: ~15 min, R7 of that GDD) and a visible level-up.
2. *"A wise elder at your side"* — a named NPC mentor who narrates each step. Asks for a character, portrait and voice, and for narrative ownership; rejected for the Alpha because the AI text layer (36) and narrative content are Full Vision, and a mentor speaking over an idle game becomes noise. Kept as an option in Open Questions (OQ-8).
3. *"Learn by doing, alone"* — no cards at all, tips only. Fastest to build; rejected because the recruit board and party formation are not self-explaining to a player who has never seen EHT.

## Detailed Design

*Specialist lenses applied in this run (no agent spawned). Meta row of the routing table: **Foundation/Infrastructure** (tutorial plumbing) → `systems-designer` primary, `gameplay-programmer` and `engine-programmer` supporting; plus **UI systems** because the coach layer is a screen surface → `game-designer`, `ux-designer`, `ui-programmer`. Union taken because the system has both a sim-side tracker and an overlay.*

- **systems-designer** — Progress must be a single source of truth that survives save, cloud restore and replay, so it lives in the sim, not in device settings. Steps must complete even when the triggering event happened *before* the step became current (a party may form before the player has read the hire card), so completion is a sticky "seen" bit, not "event while current". Offline hand-offs produce summaries, not per-trip events, so hunt steps need an offline path.
- **gameplay-programmer** — The XP window must be deterministic: count simulated ticks, never wall time; a skipped gap must not consume it. Keep the subscriber cheap: a bit test per record.
- **engine-programmer** — No new save format: one section through the Local save section contract. Cards are Control nodes over the world view; Godot 4.5+ AccessKit and 4.6 focus changes are post-cutoff (see Knowledge gaps in UI Requirements).
- **game-designer** — The opening must reach the anchor moment (first return) inside one session; that is ~15 minutes of trip time plus a few minutes of hiring. First build is impossible in the first session (every level-1 building costs `mat_z02_1 ×6`, `buildings.csv`), so it is a Quests goal, not a step.
- **ux-designer** — Soft guidance only: no forced-tap lock, no dimmed world that the sim keeps running behind. One card at a time. Every card has "Skip tutorial". A highlight is never colour-only (ring + arrow + text). The player who skips must still get the one-time tips.
- **ui-programmer** — Highlights need stable anchor IDs from screens that are not designed yet (Guild screens 39, Realtime world view 38): PROVISIONAL interface. Card text must fit vi and en, which run ~30% longer in Vietnamese with diacritics stacking; cards grow vertically, never truncate.

*Disagreement surfaced and resolved by the recommended option:* the ux-designer prefers no tracker at all (pure UI flags), the systems-designer requires a sim tracker. The sim tracker was chosen (decision log, "where progress state lives") because device-side flags reset on reinstall while the guild is restored from the cloud, and because the XP window must replay identically for Leaderboards (35).

### Core Rules

**R1 — Rows.** Every lesson is one row of the onboarding table (proposed `data/onboarding_steps.csv`, OQ-1). Columns:

| Column | Type | Meaning |
|---|---|---|
| `row_id` | int 1–63 | Stable bit index. Never reused (like Event bus type IDs) |
| `key` | `[a-z0-9_]` | Name; text keys are `ui_onb_<key>_title` and `ui_onb_<key>_body` (Localization R3) |
| `kind` | `chain` / `tip` | First-session chain step, or one-time tip |
| `chain_order` | int | Position in the chain (chain rows only; 1…n, no gaps) |
| `complete_by` | `ack` / `event` / `ui` | How the row completes (R3) |
| `type_ids` | list of event type IDs | The events that complete (chain) or trigger (tip) it; empty for `ack` and `ui` |
| `offline_ok` | 0/1 | 1 = an `offline_resolved` event (3101) also satisfies this row (R7) |
| `priority` | int | Display order when several cards are pending; higher first |
| `anchor` | string | Presentation anchor the highlight points at (R9); empty = centred card |
| `content_wave` | int | Rows for content not yet released are inert (GDD §12.5 `content_wave`) |
| `suppress_banner` | 0/1 | 1 = Ads (33) hides the banner while this row's card is showing (Ads R7). **0 on every Wave 1 row**: the band is fixed layout and the card sits above it, so nothing needs hiding |

**R2 — The Wave 1 rows.**

*First-session chain:*

| row_id | key | chain_order | complete_by | type_ids | offline_ok | anchor |
|---|---|---|---|---|---|---|
| 1 | `welcome` | 1 | ack | — | 0 | — |
| 2 | `hire_first` | 2 | event | 1502 `candidate_accepted` | 0 | `recruit_board` |
| 3 | `first_party` | 3 | event | 1301 `party_formed` | 0 | `party_panel` |
| 4 | `first_hunt` | 4 | event | 1101 `hunt_trip_started` | 1 | `world_party` |
| 5 | `first_level` | 5 | event | 2201 `member_level_up` | 1 | `member_card` |
| 6 | `first_return` | 6 | event | 1104 `hunt_trip_ended` | 1 | `world_gate` |
| 7 | `safeguard` | 7 | ack | — | 0 | `settings_account` |

*One-time tips:*

| row_id | key | complete_by | type_ids | priority | Wave |
|---|---|---|---|---|---|
| 16 | `tip_boss` | event | 1401 `gb_announced` | 90 | 1 |
| 17 | `tip_offline` | event | 3101 `offline_resolved` | 80 | 1 |
| 18 | `tip_downed` | event | 1103 `hunt_member_downed` | 60 | 1 |
| 19 | `tip_injured` | event | 4102 `member_injured` | 60 | 1 |
| 20 | `tip_epic_loot` | event | 2602 `epic_loot` | 40 | 1 |
| 21 | `tip_pa_estimate` | event | 901 `pa_estimate_narrowed` | 30 | 1 |
| 22 | `tip_guild_level` | event | 3004 `guild_level_up` | 50 | 1 |
| 23 | `tip_build_ready` | ui | — (R8 predicate) | 50 | 1 |
| 24 | `tip_leave_request` | event | 1601 `leave_requested` | 70 | 1 (VS system) |
| 25 | `tip_enhance_fail` | event | 2402 `enhance_failed` | 40 | 1 (VS system) |

Chain rows are 1–15 and tips are 16–63, so a later wave can add rows without renumbering. All chain steps have priority 100, above every tip, except that `tip_boss` (90) is shown over a chain card when it is pending (R10).

**R3 — How a row completes.** `done_mask` (int64) holds one bit per row.
- `event` chain row: its bit is set by the tracker when any of its `type_ids` is delivered (R5), **whether or not it is the current step**. Completion is sticky; a later loss (the party disbands, the member leaves) never clears it.
- `event` tip row: delivery of a listed type sets its bit in `pending_mask` if it is not already done. It becomes done only when the player dismisses the tip (`onboarding_ack`, R6).
- `ack` row (chain or tip): done only by `onboarding_ack`.
- `ui` row: never triggered by the sim; the coach layer decides when to show it (R8) and submits `onboarding_ack` when it is dismissed.

**R4 — The current step and the end of the chain.** The current step is the lowest `chain_order` whose bit is not done. The tutorial is **Finished** when every chain bit is done; at that moment the tracker sets `ended = 1` and emits `onboarding_ended` (4402, a = 1). The chain is linear in display only: step 5 can be done before step 4 (R3); the coach layer always shows the current step, and steps already done are passed over without a card but with their toast (R10).

**R5 — The tracker subscriber.** `subscribe("onboarding", order = 4400, [1502, 1301, 1101, 2201, 1104, 1401, 3101, 1103, 4102, 2602, 901, 3004, 1601, 2402], handler)` at boot — the union of every active row's `type_ids` plus 3101, built from the table at boot (a typo'd type ID is an Event bus boot error, Event bus R4). For each record in the batch, in order: for each row listing that type (precomputed type → row-bits map) apply R3; apply R7 for 3101. For each chain bit newly set, in `chain_order`, emit `onboarding_step_completed` (4401) with `a = row_id`, `b = 0` (by event) or `2` (by offline). If the chain becomes complete, apply R4. When `ended ≠ 0` and every tip row is done, the handler returns at once. The handler touches only Onboarding's own state (Event bus R6). Events it emits land in the next tick.

**R6 — Commands (host, P1).** Block 4400–4499 (Command layer type-ID rule).
- `onboarding_ack(row_id)` — command **4401**. Refused with `target_missing` (6) if `row_id` is not an active row; `onb_already_done` (101) if its bit is done; `onb_not_ackable` (102) if it is an `event` chain row; `onb_not_current` (103) if it is an `ack` chain row that is not the current step. Otherwise sets the done bit, clears its pending bit, and emits 4401 with `b = 1`. If that completes the chain, R4 applies.
- `onboarding_skip()` — command **4402**. Refused with `onb_already_ended` (104) if `ended ≠ 0`. Otherwise sets every chain bit done, sets `ended = 2`, and emits 4402 with `a = 2`, `b = ` the `chain_order` of the step that was current. No 4401 events are emitted for skipped steps. Tips are unaffected: they keep appearing (R11).
- Both commands change only Onboarding's state, cost nothing, and are logged like every command, so a replay reproduces the tutorial exactly.

**R7 — Offline gaps.** A gap longer than `offline_threshold_s` is resolved by Offline progress (31) in aggregate and produces `offline_resolved` (3101), not per-trip 1101/1104/2201 events. On 3101 the tracker sets the bit of every chain row with `offline_ok = 1` **only if at least one member exists** (the trips could have happened) — a player who hired and closed the app is not asked, on return, to "send your first party out". 3101 also triggers `tip_offline`.

**R8 — The `tip_build_ready` predicate (presentation).** The coach layer shows `tip_build_ready` the first time, outside a chain card, that the Guild screens' build list reports at least one building whose level-1 cost the guild can pay now (gold and materials, read through the facade). Onboarding does not compute affordability itself; it asks the screen (PROVISIONAL, Guild screens 39 — OQ-3). Dismissing it submits `onboarding_ack(23)`.

**R9 — The coach layer (presentation).** One card at a time, docked to the bottom third of the screen above the banner-ad strip (the layout reserve is Ads' (33) — PROVISIONAL), never covering the anchor. The card holds a title, a one- or two-sentence body, and buttons: chain `ack` cards have a primary button ("Begin" / "Sign in" / "Not now"); chain `event` cards have none (they close when the event comes); every chain card has a small "Skip tutorial" link; tip cards have "Got it". A highlight ring, an arrow and the anchor's own label point at `anchor`; if the anchor is not on screen (another screen is open), the card says where to go and the ring appears on the navigation button that leads there. The simulation keeps running; the world is not dimmed; every other button stays usable.

**R10 — What is shown, in what order.** Each frame the coach layer picks at most one card:
1. If `tip_boss` is pending, it (a Golden Boss warning lasts only `golden_boss_warning_s`, 120 s).
2. Else, if the chain is not ended, the current step's card.
3. Else, the pending tip of highest `priority` (ties: lowest `row_id`), subject to the tip pacing gap (F3), and then `tip_build_ready` if its predicate holds.

A completed chain step shows a 2-second toast ("✓ First party formed"), even when it was completed out of order; several toasts in one tick queue in `chain_order`. While the core is `catching_up` or a hand-off is pending (Sim core R15), no card or toast is shown; they appear once catch-up ends.

**R11 — Tips after skip, and turning tips off.** Skipping ends the chain, not the tips. Settings (45) holds a device-level "Show tips" toggle (default on). When off, the coach layer shows no tip cards; the tracker still records pending tips, so turning it back on shows the ones still pending. The toggle is a display preference, not guild state, and is not synced (PROVISIONAL, Settings 45 — OQ-5).

**R12 — `safeguard` (the one sign-in prompt).** Account and cloud save (7) allows "one prompt in onboarding at most". When `safeguard` becomes current, the coach layer reads the account state: `Linked` → it submits `onboarding_ack(7)` at once and shows no card; `Guest` or `NoAccount` → it shows "Sign in to keep your guild safe" with "Sign in" (opens the account link flow, then acks) and "Not now" (acks). Either button completes the step; onboarding never asks again. Without network the card says the guild can be backed up later from Settings.

**R13 — The newbie XP window.** A new guild starts with `newbie_ticks_left = newbie_window_s × tick_rate` (F2). A P5 handler (`owner_id = "onboarding"`, order 4400) decrements it by 1 each tick the core runs while it is > 0. Ticks skipped by a hand-off (`skip_ticks`) do not decrement it: the window measures **play**, not elapsed time, so a player who closes the app at minute 5 still has 25 minutes on return. Onboarding exposes the read-only query `xp_mult_ppm() → int` (F1). Hunt (11) multiplies each kill's XP by it as a source-side multiplier before calling XP's `award` (XP R5; Zones F1 "Newbie window" — OQ-2 resolved). Nothing else reads it. Skipping the tutorial does not end the window. The window is the same for every guild and is replayed exactly, so it does not distort Leaderboards (35).

**R14 — State and persistence.** Saved under the `onboarding` section (Local save section contract: own serializer and migration): `done_mask` (int64), `pending_mask` (int64), `ended` (0 active, 1 finished, 2 skipped), `newbie_ticks_left` (int). All integers. A new guild starts at `0, 0, 0, F2`, saved with the guild's first save (Local save: "immediately after a new guild is created"). **Migration:** a save with no `onboarding` section (made before this system shipped) loads as `done_mask = all active rows`, `pending_mask = 0`, `ended = 1`, `newbie_ticks_left = 0`: an existing guild is never tutored and never gets the bonus. New rows added by a later version start not-done on an existing save; a later wave's tips therefore appear for veterans when their subject first happens, and chain rows added after `ended ≠ 0` are marked done by the migration.

**R15 — What Onboarding never does.** It never pauses, slows or speeds the simulation; never submits gameplay commands on the player's behalf (no scripted hire, no forced trip); never mints gold, Linh Bảo or items; never shows a store, Premium or ad prompt; and never changes any rule of another system. Its only effect on game state is R13.

### States and Transitions

The chain:

| State | Entered when | Shown | Exits to | On |
|---|---|---|---|---|
| `NotStarted` | No guild exists (first launch, before the new-guild flow) | Nothing; locale and consent flows run first (Localization R7, Ads 33) | `Active(1)` | New guild created |
| `Active(k)` | Step k is the lowest not-done chain step | Step k's card | `Active(j>k)` | Step k (and any steps already done after it) completed |
| | | | `Finished` | Last chain bit set (R4) |
| | | | `Skipped` | `onboarding_skip` applied |
| `Finished` | All chain bits done by play | Tips only | — | Terminal for this guild |
| `Skipped` | Player skipped | Tips only | — | Terminal for this guild |

`NotStarted` is not saved (no guild, no save). `ended` stores `Finished`/`Skipped`; `Active(k)` is derived from `done_mask`.

Each tip row: `Unseen` → (`type_ids` delivered, or R8 predicate true) → `Pending` → (`onboarding_ack`) → `Done`. A tip acked while `Unseen` (only `ui` tips can be) goes straight to `Done`. `Done` is terminal.

The newbie window: `Open` (`newbie_ticks_left > 0`) → `Closed` when it reaches 0. Never reopens.

### Interactions with Other Systems

| System | Direction | Data | Owner of the interface |
|---|---|---|---|
| Event bus (42) | bus → Onboarding | `subscribe` order 4400 for the R5 list; `register_type` 4401, 4402 | Bus owns delivery; this GDD owns the block 4400–4499 and order 4400 |
| Command layer (5) | UI → Onboarding | Commands 4401 `onboarding_ack`, 4402 `onboarding_skip`; reason codes 101–104; outcome via 501/502 | Command layer owns the envelope; this GDD owns the rules |
| Sim core (1) | both | P5 handler order 4400 (R13); `catching_up` / hand-off flags read by the coach layer | Sim core |
| Recruitment (15) | Recruitment → Onboarding | 1502 completes `hire_first`. **Answers Recruitment OQ-5:** keep R11's founding roster (quick walk-in offers until 5 members); no scripted party | Recruitment |
| Party (13) | Party → Onboarding | 1301 completes `first_party` | Party |
| Zones and hunt (11) | both | 1101, 1103, 1104 complete or trigger rows; **Hunt reads `xp_mult_ppm()`** (R13; Zones F1 now states the call) | Hunt applies; Onboarding owns the value |
| XP curve (22) | Onboarding → (via Hunt) | The window is a source-side multiplier (XP R5); answers XP OQ-3 for the newbie bonus only | XP owns `award` |
| Golden Boss (14), Offline (31), Member state machine (41), Items (26), CA/PA (9), Guild and buildings (30), Retention (16), Enhancement (24) | → Onboarding | Trigger events for tips (R2) | Each emitter |
| Guild screens (39) | Onboarding ↔ screens | Screens register anchors `recruit_board`, `party_panel`, `member_card`, `settings_account`; the build list reports "affordable now" (R8) — **PROVISIONAL**, not designed | Guild screens |
| Realtime world view (38) | Onboarding ↔ view | Anchors `world_party` (the first party's sprites), `world_gate` — **PROVISIONAL** | World view |
| Account and cloud save (7) | Onboarding → Account | The `safeguard` step reads account state and opens the link flow (R12) | Account |
| Ads and consent (33) | Ads → Onboarding | Consent flow completes before `welcome`; banner strip reserved under the card — **PROVISIONAL** | Ads |
| Settings (45) | Settings → coach layer | "Show tips" toggle (R11) — **PROVISIONAL** | Settings |
| Localization (4) | Onboarding → i18n | `ui_onb_<key>_title`, `ui_onb_<key>_body`, `ui_onb_skip`, `ui_onb_got_it` and the three reason-code texts | Localization owns the catalogue |
| Local save (6) | both | `onboarding` section (R14) | Local save owns the contract |
| Quests and achievements (25) | Onboarding → Quests | At `Finished`/`Skipped` the last card points to the Quest panel; long goals are Quests' — **PROVISIONAL**, not designed | Quests |
| Analytics (37) | Onboarding → Analytics | 4401/4402 form the first-session funnel — **PROVISIONAL**, not designed | Analytics |
| Leaderboards (35) | — | The XP window replays deterministically from the command log | Leaderboards |

## Formulas

*`systems-designer` lens applied in this run (no agent spawned).*

### F1 — `xp_mult_ppm` and the newbie-boosted kill XP

The xp_mult_ppm formula is defined as:

`xp_mult_ppm = (newbie_ticks_left > 0) ? newbie_xp_ppm : 1,000,000`

`boosted_milli = floor(base_milli × xp_mult_ppm / 1,000,000)` (computed by Hunt, int64)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| newbie_ticks_left | int | 0 – 72,000 | calculated (saved) | Simulated ticks left in the window (F2, R13) |
| newbie_xp_ppm | int | 1,000,000 – 5,000,000 (default 3,000,000) | data file (`config.csv`, proposed — OQ-1) | Multiplier while the window is open; 1,000,000 = ×1 (off) |
| base_milli | int | 0 – 2⁴⁰ | calculated (Hunt) | The kill's XP in milli-XP after Hunt's other source-side bonuses |
| boosted_milli | int | 0 – 2⁴⁰ | calculated | What Hunt passes to XP `award` |

**Output Range:** `xp_mult_ppm` is 1,000,000 or `newbie_xp_ppm`. `base_milli × 5,000,000` ≤ 2⁴⁰ × 5 × 10⁶ ≈ 5.5 × 10¹⁸ < 2⁶³, so the product never overflows int64. `boosted_milli` can exceed 2⁴⁰ only if `base_milli` > 2⁴⁰ / 5 ≈ 2.2 × 10¹¹, which no early-game kill approaches (an Edge Case states the clamp). At `newbie_xp_ppm = 1,000,000` the bonus is off and Hunt's XP is unchanged. Values below 1,000,000 are refused by the validator (a "bonus" must never slow the start).
**Example:** a zone_01 kill worth `base_milli = 12,000` during the window: `12,000 × 3,000,000 / 1,000,000 = 36,000` milli-XP (36 XP). After the window: 12,000.

*Why ×3 for 30 minutes:* GDD §4.3 gives exactly this example and states that lv10 at ~2–4 h AFK is gated by trip time, not XP, so the window cannot pull lv10 much earlier; what it does is put a level-up or two inside the **first trip** (the anchor moment, Player Fantasy). It sits on top of `xp_early_floor = 0.08`, which §4.3 says must not be lowered further. The real effect on time-to-lv10 must be measured by the balance sim (OQ-4).

### F2 — `newbie_ticks_total`

The newbie_ticks_total formula is defined as:

`newbie_ticks_total = newbie_window_s × tick_rate`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| newbie_window_s | int | 0 – 7,200 (default 1,800) | data file (`config.csv`, proposed — OQ-1) | Length of the window in simulated seconds; 0 = no window |
| tick_rate | int | 10 | data file (`config.csv`, Sim core) | Ticks per second |
| newbie_ticks_total | int | 0 – 72,000 | calculated | Initial `newbie_ticks_left` of a new guild |

**Output Range:** 0 to 72,000 ticks. Default 18,000 ticks = 30 minutes of play. At 0 the window is closed from tick 0 and F1 always returns 1,000,000.
**Example:** `1,800 × 10 = 18,000`. A player who plays 5 minutes (3,000 ticks), closes the app for 8 hours (a hand-off: no decrement) and returns has 15,000 ticks left.

### F3 — Tip pacing (presentation, wall-clock)

The tip_show_at formula is defined as:

`tip_show_at_s = max(now_s, last_card_closed_s + tip_min_gap_s)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| now_s | float | ≥ 0 | calculated | Presentation wall-clock seconds since launch |
| last_card_closed_s | float | ≥ 0 | calculated | When the last card (chain or tip) closed in this run; 0 at launch |
| tip_min_gap_s | int | 0 – 600 (default 45) | data file (UI config, proposed — OQ-1) | Minimum gap between two cards so tips never stack |

**Output Range:** `tip_show_at_s ≥ now_s`. At `tip_min_gap_s = 0` tips show back to back. `tip_boss` ignores F3 (R10.1), because its subject lasts only 120 s. F3 is presentation only and never enters the simulation.
**Example:** a card closes at 300 s; an injury tip becomes pending at 310 s; it shows at `max(310, 345) = 345` s.

### F4 — Nudge timing (presentation)

The nudge formula is defined as:

`nudge_at_s = step_shown_s + hint_idle_s × (1 + n_nudges)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| step_shown_s | float | ≥ 0 | calculated | When the current chain card appeared |
| hint_idle_s | int | 5 – 120 (default 20) | data file (UI config, proposed — OQ-1) | Idle time before the highlight pulses |
| n_nudges | int | 0 – 3 | calculated | Pulses already played for this card; capped at `nudge_max` (3) |

**Output Range:** pulses at 20 s, 40 s, 60 s after the card appears, then no more (the card stays). Any input the player gives on the anchor resets `step_shown_s` and `n_nudges`.
**Example:** the hire card appears at 12 s; the player watches the world; the ring pulses at 32, 52 and 72 s.

### F5 — Event volume (Event bus F1, F4)

The onboarding_ring_lifetime formula is defined as:

`ring_records_lifetime = n_rows_active + 1`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n_rows_active | int | 1 – 63 | data file (row count) | Rows active in the current wave (Wave 1: 17) |
| ring_records_lifetime | int | 2 – 64 | calculated | Most 4401 + 4402 records one guild ever logs |

**Output Range:** at most 64 records in the guild's lifetime; the declared peak `ring_per_day` is 63 for 4401 and 1 for 4402 (all of them could happen on day one), a negligible share of the ring budget that Event bus `seal()` checks (F4). Subscriber cost per tick is one bit test per delivered record of a watched type: O(batch), bounded by the emitters' own budgets.
**Example:** Wave 1: 7 chain + 10 tips + 1 end = 18 records, all in the first days.

## Edge Cases

*`systems-designer` lens applied to Sections C and D (no agent spawned).*

- **If a party forms (1301) before the player accepts the hire card's lesson** (e.g. the player hired two people before reading): `first_party` is already done; when `hire_first` completes, the coach layer shows both toasts in order and moves to `first_hunt`. Completion is sticky (R3).
- **If several chain steps complete in the same tick**: 4401 is emitted for each in `chain_order`, and the toasts queue in that order (R5, R10).
- **If the player rejects every candidate forever**: `hire_first` stays current; the card nudges (F4) and Recruitment R11 keeps opening offers each tick until 5 members exist. Nothing forces a hire.
- **If the only member is dismissed or leaves during the chain**: done bits stay set; the current step's card stays. If the roster drops to 0 at `first_party`, the card's body switches to "hire people first" (a presentation check on roster size), no state change.
- **If the player closes the app after hiring and returns hours later**: Offline progress emits 3101; because at least one member exists, `first_hunt`, `first_level` and `first_return` are set (R7) and `tip_offline` becomes pending. The chain resumes at `safeguard`.
- **If 3101 arrives with zero members**: no chain bit is set (R7); `tip_offline` still becomes pending.
- **If the gap is shorter than `offline_threshold_s`** (60 s): it is re-run as exact ticks, real 1101/1104 events fire, and the newbie window *does* decrement for those ticks (they are run, not skipped — R13).
- **If a step event is delivered while the core is catching up**: the bit is set immediately; the card and toast wait until `catching_up` is false (R10).
- **If the first Golden Boss is announced (minute 58) while the chain is still active**: `tip_boss` (priority 90) is shown over the chain card, and the chain card returns when the tip is dismissed (R10.1). If it is not dismissed within 120 s the tip stays pending but is no longer forced to the top; it shows under normal tip rules.
- **If `onboarding_ack` arrives for a done row, an unknown row, an event chain row or a non-current ack step**: refused 101 / 6 / 102 / 103, no state change (R6). The coach layer never sends these in normal play; a double tap produces 101, which is shown as nothing (the card is already gone).
- **If `onboarding_skip` arrives twice**: the second is refused 104.
- **If the player skips during the newbie window**: the window continues (R13). Skipping is never a penalty.
- **If `boosted_milli` would exceed 2⁴⁰**: Hunt clamps it to 2⁴⁰ before `award` (XP refuses above 2⁴⁰, error 2201). Unreachable with Wave 1 data (F1).
- **If `newbie_window_s` or `newbie_xp_ppm` is changed by a content update while a guild's window is open**: `newbie_ticks_left` is saved state and is not recomputed; a new `newbie_xp_ppm` applies from the next kill. The validator keeps `newbie_xp_ppm ≥ 1,000,000`.
- **If a save from before this system loads**: the migration marks everything done, ended = 1, window 0 (R14).
- **If a cloud restore brings back an older save mid-tutorial**: its `onboarding` section is restored with it, and the tutorial resumes at that save's current step. A lesson may repeat only if the restored save is older than the lesson — correct, since that guild never had it.
- **If the player starts a second guild** (new guild flow after "save damaged", or a new slot): the new guild gets a fresh section and the full chain; the welcome card's "Skip tutorial" is the fast exit for experienced players. The new guild gets a fresh newbie window — accepted, because Deterministic RNG already accepts "seed shopping" as a small early-game-only edge, and the window is identical for every guild.
- **If the anchor of the current step does not exist** (screen not built yet in a build, or the anchor ID is unknown): the card is shown centred with no ring and the coach layer logs a dev warning; the step is still completable by its event.
- **If the locale changes mid-card**: the card re-renders from its `ui_onb_*` keys; no state changes.
- **If "Show tips" is off when `tip_boss` fires**: no tip card; the Golden Boss has its own banner and drum (Golden Boss Game Feel), so the player still sees the event.
- **If the device has no network at `safeguard`**: the card offers only "Not now" with the "back up later from Settings" text (R12); the step completes.
- **Degenerate strategy check**: there is none to exploit — rows grant nothing, and the only value (the XP window) counts simulated ticks once per guild and cannot be refreshed except by a new guild.

## Dependencies

### Upstream (this system depends on)

| System | Hard/Soft | Interface | Status |
|---|---|---|---|
| Event bus and history log (42) | Hard | `subscribe` (order 4400), `register_type` 4401–4402 | Designed (Needs Revision) |
| Command layer (5) | Hard | `register_command` 4401, 4402; reason codes 101–104 | Designed |
| Sim core and tick loop (1) | Hard | P5 handler order 4400; facade flags `catching_up`, `handoff_pending` | Designed (Needs Revision) |
| Local save and migration (6) | Hard | `onboarding` section serializer and migration (R14) | Designed |
| Data layer and content pipeline (3) | Hard | Proposed `onboarding_steps.csv` and four config keys (OQ-1) | Designed — table not yet registered |
| Localization (4) | Hard | `ui_onb_*` keys | Designed |
| Recruitment (15) | Hard | Event 1502; R11 founding roster | Designed |
| Party (13) | Hard | Event 1301 | Designed |
| Zones and hunt (11) | Hard | Events 1101, 1103, 1104; calls `xp_mult_ppm()` (PROVISIONAL) | Designed — call not yet in its GDD |
| XP and level pacing curve (22) | Hard | Event 2201; source-side multiplier rule (R5) | Designed |
| Guild screens (39) | Hard | Anchors; "affordable building" query (R8) | **Not designed — PROVISIONAL** |
| Realtime world view (38) | Hard | Anchors `world_party`, `world_gate` | **Not designed — PROVISIONAL** |
| Account and cloud save (7) | Soft | Account state + link flow (R12) | Designed |
| Offline progress (31) | Soft | Event 3101 | Designed |
| Golden Boss (14), Member state machine (41), Items (26), CA/PA (9), Guild and buildings (30), Retention (16), Enhancement (24) | Soft | Tip trigger events | Designed |
| Ads and consent (33) | Soft | Consent before welcome; banner reserve | **Not designed — PROVISIONAL** |
| Settings (45) | Soft | "Show tips" toggle | **Not designed — PROVISIONAL** |

### Downstream (systems that depend on this one)

| System | Hard/Soft | Interface |
|---|---|---|
| Zones and hunt (11) | Soft | `xp_mult_ppm()` (works without it at ×1) |
| Analytics (37) | Soft | Events 4401, 4402 |
| Quests and achievements (25) | Soft | Hand-off card at chain end; may listen for 4402 |
| Leaderboards (35) | Soft | Replays the window through the command log; no direct call |

**Bidirectional check:** Event bus lists Onboarding (44) as a hard `subscribe` consumer ✅. Command layer lists Onboarding as a screen that sends commands ✅. Recruitment lists Onboarding (soft, founding roster) and its OQ-5 is answered here ✅. Account and cloud save lists the optional sign-in step ✅. Zones and hunt lists Onboarding as downstream of events 1101–1105 ✅ but not the `xp_mult_ppm` call ⚠ (OQ-2). XP curve OQ-3 names Onboarding as a candidate owner ✅ (answered for the newbie bonus). The systems index row 44 lists Zones and hunt, Guild screens, Event bus; this GDD adds Command layer, Recruitment, Party, Local save, Localization, Realtime world view (index Depends On updated).

## Tuning Knobs

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `newbie_xp_ppm` (`config.csv`, proposed) | 3,000,000 | 1,000,000 – 5,000,000 | First members overshoot zone_01 (lv 1–10) in the window and the "first return" level-up becomes several, flattening §4.3's curve | 1,000,000 turns the bonus off | `newbie_window_s`, `xp_kill_coef`, `xp_early_floor` (XP curve, which §4.3 says must not be lowered) |
| `newbie_window_s` (`config.csv`, proposed) | 1,800 | 0 – 7,200 | The boost covers several trips and pulls lv10 well under 2 h, beyond the §4.3 target | 0 = no window; under ~900 (one trip) the first return may see no boosted level-up | `newbie_xp_ppm`; Hunt trip length (~15 min) |
| `tip_min_gap_s` (UI config, proposed) | 45 | 0 – 600 | Tips arrive long after their subject; players miss the context | Tips stack and feel like nagging | Number of tip rows |
| `hint_idle_s` (UI config, proposed) | 20 | 5 – 120 | A stuck player waits too long for a nudge | The ring pulses while the player is still reading | `nudge_max` |
| `nudge_max` (UI config, proposed) | 3 | 0 – 10 | Pulsing becomes noise | 0 = no nudges | `hint_idle_s` |
| Row table (`onboarding_steps.csv`, proposed) | R2 | ≤ 15 chain rows, ≤ 48 tips | A long chain delays the anchor moment past one session | Too few chain rows leave the recruit board and party formation unexplained | Recruitment R11, Party R3 |

Not knobs here (pointed to): `recruit_founding_roster` (Recruitment), `golden_boss_warning_s` (Golden Boss), `offline_threshold_s` (Sim core), `tick_rate` (Sim core).

## Visual/Audio Requirements

Optional for the Meta category; written briefly because the coach layer is on screen. No art bible exists (`design/art/art-bible.md` absent), so this is drafted from GDD §1 (pixel 2D) and the requirement that cards never hide the world.

- **Card:** a pixel-art scroll or wooden plaque frame in the shared UI palette (GDD §12.4 palette quantisation), the guild's crest top-left; text in the UI font at the standard body size, never smaller.
- **Highlight:** a 2-px animated ring plus a bobbing arrow in a high-contrast colour, *and* the anchor's own label; never colour alone. Ring pulse = scale 1.0 → 1.15 → 1.0 over 0.6 s (F4 pulses).
- **Toast:** a small "✓" seal stamp animation (0.3 s) with the step title, at the top of the screen, auto-hiding after 2 s.
- **Audio:** a soft brush/paper sound when a card opens, a light chime on step completion, nothing on tips except the Golden Boss tip, which uses no sound of its own (the boss drum already plays). All via Audio (40); mix priority below gameplay warnings.
- **No full-screen dim, no character portrait** (Player Fantasy framing 2 was not chosen).

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:onboarding-and-tutorial` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

Optional for Meta; three targets.
- A step completes **within one tick plus one frame** of its event (≤ 100 ms at 10 Hz): the toast appears as the party is seen leaving or arriving, not seconds later.
- A card opens or closes in ≤ 0.2 s; tapping anywhere outside a card never closes it accidentally, and never blocks the tap's own target.
- The first-session chain should complete in **15–25 minutes** of play for a player who follows it (one trip, ~15 min, Hunt F-trip; plus hiring). Measured by Analytics' funnel and the first playtest (OQ-6).

## UI Requirements

- One overlay layer above the world view and every guild screen, below system dialogs (consent, purchase). Cards anchored in the bottom third, above the banner-ad strip.
- Anchors: screens register named anchors (`recruit_board`, `party_panel`, `member_card`, `settings_account`, `world_party`, `world_gate`); the overlay asks for an anchor's screen rect each frame. Unknown anchor → centred card (Edge Cases).
- Text: vi and en; cards grow vertically and never truncate; body ≤ 2 sentences, title ≤ 32 characters in en.
- Accessibility: every highlight has a text equivalent; cards are reachable by keyboard/controller focus on PC; with a screen reader the card is announced when it appears and focus does not jump away from what the player is doing. **Knowledge gap (HIGH):** AccessKit screen-reader support is new in Godot 4.5 and mouse hover is separate from keyboard focus in 4.6 (`docs/engine-reference/godot/modules/ui.md`); verify both before building. Engine domain for this Meta system is Core: no engine reference for `core` under `docs/engine-reference/godot/modules/`; feasibility not checked against the pinned engine for the tracker, only for the overlay (UI module).
- A "Guide" list inside Guild screens (Help) shows every row's title and body that is done, so a player can re-read a lesson without replaying it (read-only, no state).
- Command acknowledgement follows the Command layer's UI Requirements (pending → applied/refused; codes 101–104 have i18n texts but are normally invisible).

> **📌 UX Flag — Onboarding and tutorial**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the coach overlay, the card states and the anchor contract (`design/ux/onboarding-overlay.md`) **before** writing epics. Stories that reference UI should cite that spec, not this GDD.

## Cross-References

| This GDD | Other GDD | Its rule or value | Nature |
|---|---|---|---|
| R5, F5 | `event-bus-and-history-log.md` | R3 type blocks, R4 `subscribe` (order steps of 100, ≤ 16 subscribers), R6 subscriber contract, F4 ring budget | Rule dependency |
| R6 | `command-layer.md` | Type-ID block rule (owner number × 100), reason codes 100–999, generic code 6 `target_missing`, UI Requirements 1–6 | Rule dependency |
| R13, F2 | `sim-core-and-tick-loop.md` | R8 hand-off (`skip_ticks` runs no tick), R15 `catching_up`; `tick_rate` 10 | Rule + value dependency |
| R2, R11-answer | `recruitment.md` | R11 founding roster, `recruit_founding_roster` 5, OQ-5, event 1502 | Rule dependency; answers OQ-5 |
| R2 | `party.md` | Event 1301 `party_formed`, automatic formation | Event dependency |
| R2, R13, F1 | `zones-grounds-monsters-and-hunt-trips.md` | Events 1101/1103/1104; trip ~15 min; caller applies source-side XP | Event + rule dependency (PROVISIONAL call) |
| R13, F1 | `xp-and-level-pacing-curve.md` | R5 source-side multipliers, `base_milli` ≤ 2⁴⁰ (error 2201), OQ-3, event 2201 | Rule dependency; answers OQ-3 for the newbie bonus |
| R7 | `offline-progress.md` | Event 3101 `offline_resolved` | Event dependency |
| R2, R10 | `golden-boss-and-guild-raid.md` | Event 1401, `golden_boss_warning_s` 120 s, first slot at tick 36,000 | Event + value dependency |
| R12 | `account-and-cloud-save.md` | "one prompt in onboarding at most"; account states `Guest`, `Linked`, `NoAccount` | Rule dependency |
| R14 | `local-save-and-migration.md` | Section contract; first save right after new guild | Rule dependency |
| Detailed Design (game-designer) | `guild-and-buildings.md` / `data/buildings.csv` | Level-1 buildings cost `mat_z02_1 ×6` | Value dependency (why first build is not a chain step) |
| R2 tips | `member-state-machine.md`, `items-and-loot-tables.md`, `ca-pa-and-traits.md`, `retention-leaving-and-negotiation.md`, `equipment-enhancement.md` | Events 4102, 2602, 901, 1601, 2402 | Event dependency |
| Edge Cases | `deterministic-rng.md` | "Seed shopping" accepted | Rule dependency |
| R1 | `localization.md` | `ui_` key prefix | Value dependency (registry `ui_string_key_prefix`) |

## Acceptance Criteria

*`qa-lead` lens applied in this run (no agent spawned). [Logic] = automated unit test in `tests/unit/onboarding/`; [Integration] = automated integration test; [UI] = retained screenshot in `production/qa/evidence/`; [Playtest] = documented playtest.*

- **AC-1 [Logic] (R14)**: **GIVEN** a new guild, **WHEN** it is created, **THEN** the `onboarding` section is `done_mask = 0, pending_mask = 0, ended = 0, newbie_ticks_left = 18,000` (defaults) and the current step is `welcome`.
- **AC-2 [Logic] (R3, R5)**: **GIVEN** an active chain at `welcome`, **WHEN** event 1301 is delivered, **THEN** bit 3 is set, 4401 is emitted with `a = 3, b = 0` in the next tick, and the current step is still `welcome`.
- **AC-3 [Logic] (R4, R5)**: **GIVEN** bits 1, 3, 4, 5, 6, 7 done, **WHEN** 1502 is delivered, **THEN** bit 2 is set, `ended = 1`, and 4401 (a = 2) then 4402 (a = 1) are emitted in that order.
- **AC-4 [Logic] (R6)**: **GIVEN** an active chain at `welcome`, **WHEN** `onboarding_ack(1)` is applied, **THEN** bit 1 is set and 4401 with `b = 1` is emitted; **WHEN** `onboarding_ack(1)` is applied again, **THEN** it is refused 101 and state is unchanged.
- **AC-5 [Logic] (R6)**: **GIVEN** an active chain, **THEN** `onboarding_ack(2)` is refused 102, `onboarding_ack(7)` is refused 103 while `welcome` is current, and `onboarding_ack(64)` is refused 6.
- **AC-6 [Logic] (R6)**: **GIVEN** an active chain at step 3, **WHEN** `onboarding_skip()` is applied, **THEN** every chain bit is set, `ended = 2`, exactly one 4402 with `a = 2, b = 3` is emitted and no 4401; **WHEN** applied again, **THEN** refused 104.
- **AC-7 [Logic] (R3 tips)**: **GIVEN** `tip_injured` unseen, **WHEN** 4102 is delivered twice, **THEN** its pending bit is set once and it is not done; **WHEN** `onboarding_ack(19)` is applied, **THEN** it is done and pending is clear; **WHEN** 4102 is delivered again, **THEN** pending stays clear.
- **AC-8 [Logic] (R7)**: **GIVEN** a guild with 1 member at step 4, **WHEN** 3101 is delivered, **THEN** bits 4, 5, 6 are set and `tip_offline` is pending. **GIVEN** a guild with 0 members, **WHEN** 3101 is delivered, **THEN** no chain bit changes and `tip_offline` is pending.
- **AC-9 [Logic] (R13, F2)**: **GIVEN** a new guild, **WHEN** 3,000 ticks run, then a hand-off of 8 h is skipped, then 1 tick runs, **THEN** `newbie_ticks_left = 14,999`.
- **AC-10 [Logic] (F1)**: **GIVEN** `newbie_ticks_left = 1`, **THEN** `xp_mult_ppm() = 3,000,000`; **WHEN** one tick runs, **THEN** it returns 1,000,000. **GIVEN** `newbie_xp_ppm = 1,000,000`, **THEN** it returns 1,000,000 while the window is open.
- **AC-11 [Integration] (R13, F1, cross-system)**: **GIVEN** two identical new guilds with the same seed, one with `newbie_window_s = 0`, **WHEN** a zone_01 kill with `base_milli = 12,000` is awarded at tick 100, **THEN** the member gains 36,000 milli-XP in the default guild and 12,000 in the other (before member-side multipliers, XP R5).
- **AC-12 [Logic] (F1 boundary)**: **GIVEN** `base_milli = 2⁴⁰` and the window open at 5,000,000 ppm, **THEN** the product is computed in int64 without overflow and Hunt passes 2⁴⁰ to `award` (clamp).
- **AC-13 [Logic] (R14 migration)**: **GIVEN** a save with no `onboarding` section, **WHEN** it loads, **THEN** every active row is done, `ended = 1`, `newbie_ticks_left = 0`, and no card is shown.
- **AC-14 [Integration] (determinism)**: **GIVEN** a recorded command log of a first session including `onboarding_ack` and `onboarding_skip`, **WHEN** it is replayed headless, **THEN** the `onboarding` section and every 4401/4402 record match the original byte for byte.
- **AC-15 [Logic] (R5 boot)**: **GIVEN** a row whose `type_ids` contains an unregistered type, **WHEN** the bus seals, **THEN** boot fails naming `onboarding` (Event bus R4).
- **AC-16 [Logic] (validator, Tuning Knobs)**: **GIVEN** `newbie_xp_ppm = 999,999`, or `newbie_window_s = 7,201`, or two chain rows with the same `chain_order`, or a `row_id` reused, **THEN** the content validator reports an error.
- **AC-17 [UI] (R9, R10)**: **GIVEN** a fresh install on the target Android phone, **WHEN** the new guild opens, **THEN** the welcome card is shown in the bottom third, the world is not dimmed and still animates, and "Skip tutorial" is visible (screenshot, vi and en).
- **AC-18 [UI] (R9)**: **GIVEN** step `hire_first` current, **THEN** a ring and arrow surround the recruit board with its label visible; in a greyscale screenshot the highlight is still distinguishable.
- **AC-19 [UI] (R10)**: **GIVEN** the chain at step 4 and `gb_announced` delivered, **THEN** the Golden Boss tip replaces the chain card within one frame of catch-up ending; after "Got it", the step-4 card returns.
- **AC-20 [UI] (R10, catch-up)**: **GIVEN** a step completes while `catching_up` is true, **THEN** no card or toast is drawn until `catching_up` is false, and then its toast appears once.
- **AC-21 [UI] (R12)**: **GIVEN** account state `Linked`, **WHEN** `safeguard` becomes current, **THEN** no card is drawn and `onboarding_ack(7)` is submitted; **GIVEN** `Guest`, **THEN** the sign-in card is shown once and never again after either button.
- **AC-22 [UI] (R11)**: **GIVEN** "Show tips" off and `tip_injured` pending, **THEN** no tip card shows; **WHEN** the toggle is turned on, **THEN** the tip shows.
- **AC-23 [Logic] (R15)**: **GIVEN** a full first session played through the chain, **THEN** the gold ledger, items and every non-onboarding save section equal those of the same command log replayed with every `onboarding_*` command removed and `newbie_window_s = 1,800` kept — onboarding commands change nothing outside their section.
- **AC-24 [Playtest] (Game Feel, Player Fantasy)**: **GIVEN** 5 first-time players on the target phone, **WHEN** each plays until the chain ends or 30 minutes pass, **THEN** the median completes the chain in 15–25 minutes, and at least 4 of 5 see a level-up toast before or at `first_return`.
- **AC-25 [Logic] (F3, F4)**: **GIVEN** `tip_min_gap_s = 45` and a card closed at 300 s, **WHEN** a tip becomes pending at 310 s, **THEN** it is shown at 345 s; **GIVEN** `hint_idle_s = 20`, `nudge_max = 3`, **THEN** a card shown at 12 s pulses at 32, 52 and 72 s and not at 92 s.

**Coverage:** R1 (AC-16), R2 (AC-2–3, AC-7–8), R3 (AC-2, AC-7), R4 (AC-3), R5 (AC-2–3, AC-15), R6 (AC-4–6), R7 (AC-8), R8 (UI review via the UX spec — needs Guild screens; noted gap), R9 (AC-17–18), R10 (AC-19–20), R11 (AC-22), R12 (AC-21), R13 (AC-9–11), R14 (AC-1, AC-13), R15 (AC-23); F1 (AC-10–12), F2 (AC-9), F3/F4 (AC-25), F5 (event volume follows from AC-2–6; no separate test). Gap: R8 has no criterion until Guild screens (39) defines its affordability query.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | Schema change, not made here: register `data/onboarding_steps.csv` (R1 columns, validator rules from AC-16) and the config keys `newbie_xp_ppm`, `newbie_window_s` (`config.csv`), plus the UI config keys `tip_min_gap_s`, `hint_idle_s`, `nudge_max`. Until then the R2 rows are the specification | Data layer (3) | Before Onboarding implementation (Alpha) |
| OQ-2 | **RESOLVED (consistency-check 2026-11-16):** Zones F1 now multiplies each live kill's XP by `onboarding.xp_mult_ppm()` and clamps at 2⁴⁰; the offline sampled resolver does not apply it (window counts played ticks). | Zones and hunt (11) | Closed |
| OQ-3 | PROVISIONAL: Guild screens (39) — registers anchors `recruit_board`, `party_panel`, `member_card`, `settings_account` and exposes "a building is affordable now" for `tip_build_ready` (R8) | Guild screens (39) | When Guild screens is designed |
| OQ-4 | Measure the newbie window's effect with the balance sim: time to first level-up, levels gained by the end of the first trip, time to lv10, versus §4.3's "lv10 after ~2–4 h AFK" | Dev tooling and balance sim (43) | Before the Alpha balance gate |
| OQ-5 | PROVISIONAL: Settings (45) — a device-level "Show tips" toggle, not synced (R11). Should it sync with the guild instead? | Settings (45) | When Settings is designed |
| OQ-6 | Ads and consent (33, now designed) — conforms to Ads R6 (fixed banner band) and R7 (`suppress_banner` per onboarding row; all 0 in Wave 1). Still assumed: the consent/privacy flow finishes before `welcome` is shown. Confirm in the consistency pass | Ads (33) | Consistency pass |
| OQ-7 | Realtime world view (38, now designed) offers "highlight a member, building or location (focus calls)". Assumed: `world_party` = focus on the first party's leader while outbound, `world_gate` = focus on the guild gate location, and the view reports the focused object's screen rect for the ring | Realtime world view (38) | Consistency pass |
| OQ-8 | Narrative: should a named mentor NPC (Player Fantasy framing 2) voice the cards in a later wave, possibly through the AI text layer (36)? | Narrative / creative direction | Full Vision |
| OQ-9 | PROVISIONAL: Quests and achievements (25) — at chain end, the last toast points to the Quest panel, whose main line carries "first building", "first zone_02 hunt" and the road to rebirth. Quests owns those goals | Quests (25) | When Quests is designed |
| OQ-10 | Analytics (37, now designed) assumes a host signal `step_completed(step_id)` (its OQ-7). This GDD provides it as the sim event 4401 (`a = row_id`, a stable int 1–63) plus 4402 for finish/skip; Analytics can take them from its existing bus tap (order 3700) instead of a separate host signal. **RESOLVED (consistency-check 2026-11-16):** Analytics OQ-7 now takes 4401/4402 from its tap | Analytics (37) | Consistency pass |

*Post-design note — CD-GDD-ALIGN run in this session (lens applied, no agent): no game pillars, concept or brief exist (`design/gdd/game-pillars.md`, `game-concept.md`, `design/game-brief.md` absent). Checked against GDD §1, §4.3, §11.2 instead: the chain reaches the Player Fantasy's anchor moment inside one trip (R2, Game Feel); the fast opening uses §4.3's own newbie-bonus lever without lowering `early_floor` (F1); no rule interrupts play with ads or purchases (R15). Verdict recorded as NOT ASSESSED because the required pillar input is missing.*
