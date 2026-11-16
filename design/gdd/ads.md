# Ads (banner, rewarded, consent)

> **Status**: Designed (pending independent /design-review)
> **Author**: user + Claude (autonomous batch run, decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against (see Post-design note at the end of Open Questions)
> **Implements Pillar**: None (no game-pillars.md yet). Serves the locked GDD §2 rows "Bản Free (quảng cáo banner dưới …)", "Nhiệm vụ ngày/tuần: có mục xem quảng cáo thưởng (tuỳ chọn) ở Free; Premium nhận thẳng thưởng", "PC (Steam): chỉ bản trả phí, không quảng cáo", and the §11.2 rule "không dùng quảng cáo xen kẽ (interstitial) làm gián đoạn gameplay".

## Summary

Ads is the host-level service that shows the Free mobile build's fixed bottom banner, plays an opt-in rewarded video when a player taps *Watch* on one of the two ad-variant quests, and runs the first-launch privacy notice and the ad-consent flow (Google UMP / GDPR, iOS ATT later) before any ad is requested. It never interrupts play (no interstitials, no app-open ads), never shows anything to a Premium or PC player, and changes the simulation only through one host command that credits a watched ad to a quest. It exists because ads are the Free build's revenue alongside IAP (GDD §2, §11), and because consent rules make an ad SDK that runs before the player has agreed a store-removal risk.

> **Quick reference** — Layer: `Feature` · Priority: `Alpha` · Key deps: `Entitlement and feature flags (32)`, `Quests and achievements (25)`, `Command layer (5)`, `Localization (4)`; depended on by `Settings (45)`, `Guild screens (39)`, `Realtime world view (38)`, `Analytics (37)`

## Overview

Ads is a host-level service (GDD §3.2 `[Services]`: "Ads, IAP, Entitlement(Free/Premium)") that sits outside the deterministic simulation, like In-app purchases (34). It owns four things: the **privacy and consent flow** that every install passes once before any ad SDK request (R3–R5); the **banner** — one anchored adaptive banner at the bottom of the screen in the Free mobile build, inside a layout band every screen reserves from day one (GDD §11.3 "tính vào layout UI từ đầu", R6–R7); the **rewarded flow** — load, show and reward-callback handling for the `watch_rewarded_ad` quest objective (R8–R11); and the **gating rule** that no ad is requested, loaded or shown unless Entitlement reports a definite Free state on a mobile build (R2). It does not own the quests themselves: which quests exist, their counts, rewards and resets, and the Premium auto-claim of the same quests, belong to Quests and achievements (25) and `data/quests.csv`. It does not decide who is Premium: that is Entitlement's (32) derivation from the IAP ledger. Players see it as the bottom banner, a *Watch ad* button on two quest rows, a one-time privacy screen, and a *Privacy & ads* entry in Settings. The ad network plugin, mediation choice, ad unit configuration and the consent SDK binding become ADRs.

*Framing: technical (Meta category, recommended option); no ADR exists yet, so none is cited. Player effect is stated where it matters.*

## Player Fantasy

**"Ads I choose, never ads that ambush me."** This is an indirect fantasy (Meta category): the player does not enjoy ads, they enjoy what the rules around ads protect — an idle management game they can leave running, glance at, and come back to without a full-screen video stealing the moment. The anchor moment: a Free player opens the app on the bus, the "while you were away" report fills the screen, the Golden Boss is about to spawn — and nothing covers it. The banner sits in its own strip below the guild, where it always is. Later, on the daily quest list, they see *Watch ad → 600 gold, 10 Linh Bảo* and decide, on their own terms, that thirty seconds is worth it today.

Three supporting promises the rules must keep:

- **An ad never covers the game.** No interstitial, no app-open ad, no auto-played video; a rewarded video starts only from the player's tap (R1, R8).
- **Paying once means never again.** A Premium or PC player sees no banner, no *Watch* button and no ad SDK request (R2), and the ad quests are simply claimed for them (Quests 25, `premium_auto_claim`).
- **Saying no costs nothing but the ad's own reward.** Declining consent still lets the player use every feature; skipping a rewarded video loses only that quest's reward, never progress (R4, R10).

*`creative-director` lens applied in this run (no agent spawned). No game pillars exist, so framings were anchored to GDD §2 and §11.2 text. The "ads I choose" framing was chosen over "fair trade for a free game" because the latter centres revenue rather than the player moment.*

## Detailed Design

> Specialist lenses applied (SKILL §6 routing; `Meta` → Foundation/Infrastructure row, plus the UI systems row because the banner band and consent screens are UI surfaces): **systems-designer** (primary), **game-designer** (primary, UI row), **gameplay-programmer** and **engine-programmer** (supporting), **ux-designer** and **ui-programmer** (supporting, UI row). Points are folded into the rules; the one disagreement is recorded under R10.
> - systems-designer: three independent state machines (consent, banner, rewarded) plus one gating predicate; the reward must enter the sim as a replay-safe command, idempotent per watch, or a crash or a double callback duplicates it.
> - game-designer: the rewarded watch is a choice only if declining is cheap and the offer is honest — the button must show the exact reward and disappear when the quest no longer needs a watch. F3 shows ads carry about a quarter of quest gold; flagged for Quests and economy, not settled here.
> - gameplay-programmer: nothing here runs inside a tick; the sim must not pause for a video (the guild keeps hunting, R8.5); every value here is host-side config, not sim state.
> - engine-programmer: Godot has no built-in ad or UMP support; AdMob and UMP go through an Android plugin whose current API is not covered by `docs/engine-reference/godot/` → **NOT SOURCEABLE**, verify in the P1 spike (§12.1, AC-18).
> - ux-designer: the banner band must be part of every layout (Account and cloud save AC-18 already tests its conflict screen "with the Free banner visible"); the consent and privacy screens need plain vi/en wording and an always-reachable way to change the choice.
> - ui-programmer: the band height must be known before the first ad loads, or every screen jumps when it arrives; reserve it at startup from the SDK's adaptive size for the current width.
> - **Disagreement (game-designer vs systems-designer) on no-fill:** game-designer wanted a fallback grant after repeated "no ad available" so Free players in low-fill regions are not penalised; systems-designer objected that a fallback changes quest rules owned by Quests (25) and makes the watch pointless. Autonomous run took the narrower option (no fallback in this GDD) and recorded the choice as OQ-3.

### Core Rules

**R1 — Outside the simulation; no interrupting formats.** Ads is a host-level service. It holds no simulation state, registers no tick phase, emits no Event-bus events, and is never called from inside a tick. It may use engine time and engine randomness. It uses exactly two ad formats: an **anchored adaptive banner** and a **rewarded video**. Interstitial, app-open, rewarded-interstitial, native-in-feed and auto-playing formats are forbidden (GDD §11.2); mediation adapters must be configured so none of them is ever requested.

**R2 — The ads-allowed gate.** An ad may be requested, loaded or shown only when all of these hold; otherwise every banner and rewarded object is destroyed and nothing is requested:
- (a) the build is a mobile store build (Android in Wave 1; iOS later). The PC/Steam build and the Web build contain no ad SDK at all (GDD §2 "PC chỉ bản trả phí, không quảng cáo"; Web is OQ-7);
- (b) Entitlement (32) reports a **definite** `is_premium = false`. While Entitlement is not yet ready (first seconds of launch, cache missing and not yet refreshed) the gate is **closed** — Ads fails closed, so a paying player never sees an ad because a check was slow (P5 prompt "Premium không bao giờ thấy quảng cáo");
- (c) the consent flow has reached `ConsentResolved` and the consent SDK reports that ads may be requested (R4);
- (d) the ad SDK has initialised.
The gate is re-evaluated on every Entitlement change, consent change and app resume. A change to Premium mid-session closes it immediately (R7, Edge Cases).

**R3 — First-launch privacy notice.** On the first launch of an install, before any ad, analytics or cloud call, the game shows its own **privacy notice** screen (vi/en): what is collected (cloud backup and guest account — Account and cloud save 7; ads — this system; analytics — Analytics 37), a link to the privacy policy URL (data, `ad_privacy_policy_url`), and one *Continue* button. It is informational, not a consent form; it is shown once per install and is reachable again from Settings → *Privacy & ads*. Account and cloud save (7) names this notice as owned here.

**R4 — Ad consent (UMP / GDPR).** After the privacy notice, Ads asks the consent SDK (Google User Messaging Platform on Android) to refresh consent information for the device.
1. If consent is **required** for the device's region (EEA, UK, Switzerland and any region the SDK flags) and not yet given, the SDK's consent form is shown.
2. If the player accepts, ads are personalised as the consent allows; if the player declines or manages choices down, ads are requested in the SDK's non-personalised / limited mode. **Declining never blocks any game feature**, including the ad quests (the player may still watch a limited ad).
3. If consent is **not required**, no form is shown.
4. If the consent information cannot be fetched (no network), the state stays `ConsentUnknown`, the gate stays closed, and the refresh is retried on the next app resume with network. The game is fully playable meanwhile.
5. When the SDK reports that a privacy-options entry point is required, Settings (45) shows *Privacy & ads → Change ad choices*, which reopens the consent form. It is shown to every Free player either way, labelled "Ad privacy settings".
6. Consent is device/install state kept in platform settings by the consent SDK, **never in the save** (Local save GDD: "ad consent … live in platform settings, not in the save"), so a restored cloud save never carries another device's consent.

**R5 — iOS tracking prompt and age.** On iOS (post Wave 1, OQ-6) the App Tracking Transparency prompt is shown once, after the UMP step, and only if the build requests IDFA; a refusal means non-personalised ads. The game is **not child-directed**: store age rating and ad requests declare it as a general-audience title (no child-directed or under-age-of-consent tag). If the store rating or target audience ever includes children, R1 formats and networks must be re-reviewed (OQ-5).

**R6 — The banner band.** In the Free mobile build every screen lays out above a bottom **banner band** whose height is fixed at startup: the ad SDK's anchored adaptive banner height for the current screen width in dp, or `ad_banner_fallback_dp` when the SDK cannot report one. The band is reserved whether or not an ad has filled, so nothing jumps when one loads. When the gate (R2) is closed because the player is Premium, or on PC/Web, the band height is 0 and the layout uses the full screen. The band sits above the system navigation area and inside safe-area insets (edge-to-edge Android, Godot 4.7 — `current-best-practices.md`).

**R7 — Banner behaviour.**
- One banner instance, loaded when the gate opens, refreshed by the ad network at the rate set in the network console (not by game code).
- Hidden (band left empty, no request) while: the consent form or privacy notice is open; a rewarded video is playing; a store purchase sheet or the Premium shop confirmation is open (In-app purchases R4); the first-launch onboarding steps that Onboarding (44) marks `suppress_banner` are showing.
- Destroyed immediately, and the band collapsed to 0 on the next layout pass, when Entitlement changes to Premium. Re-created on the next app start after Entitlement changes back to Free (a refund, IAP R11).
- If the banner fails to load it retries with F1 back-off while the app is in the foreground; the empty band shows the game's own background, never a "Go Premium" upsell (no pressure prompts, matching IAP R12).

**R8 — The rewarded offer.** A rewarded video is offered **only** on a quest row whose quest has `objective = watch_rewarded_ad` and `ad_variant = true` in `data/quests.csv`, while that quest instance is open and needs more watches (`progress < count`). Today that is `q_d_watch_ad` (1 per day) and `q_w_watch_ad` (3 per week).
1. When such a row exists and the gate is open, Ads preloads one rewarded ad.
2. The row shows *Watch ad* with the exact reward the quest pays (gold, Linh Bảo) from Quests, and the watch count (for example "1/3"). While no ad is ready it shows "Loading…" and is disabled; on no-fill it shows "No ad available right now" (R10).
3. Tap → one rewarded video plays full screen; game audio is muted for its duration (Audio 40). Only one rewarded show may be in flight.
4. The SDK's **earned-reward** callback (not the close callback) is the only event that counts a watch (R9).
5. The simulation keeps running while the video plays; the host `advance` call continues on resume, and a long video follows the normal resume path of the Sim core (and, beyond `offline_threshold_s`, Offline progress 31). The video never pauses the guild.
6. After the watch, the next ad is preloaded if the quest still needs watches.

A Premium player never sees *Watch ad*: Quests (25) claims these quests for them through `premium_auto_claim = true` using Entitlement's sim snapshot. Ads plays no part in that path.

**R9 — Crediting a watch: `credit_ad_watch` (host command 3301).** On the earned-reward callback, Ads:
1. Creates a watch record `{watch_id, quest_id, period_index}` (`watch_id` a random 62-bit host id) and writes it atomically to a small **pending-watch side file** beside the save, not inside it.
2. Submits host-origin command `credit_ad_watch(quest_id, watch_id)` through the Command layer host facade.
3. Its applier (owned by this system, executing Quests' objective API) checks: the quest is an `ad_variant` quest with objective `watch_rewarded_ad`; the current open instance of that quest has `progress < count`; `watch_id` is not in the save's `ad_watches_applied` set; the per-day credit count is below `ad_rewarded_daily_max` (F2). If all hold, it adds 1 to the quest's objective progress, adds `watch_id` to `ad_watches_applied`, and returns accepted. Reward payout on completion is Quests' (25) normal completion path.
4. Refusals: `101 not_ad_quest`, `102 quest_satisfied` (instance complete or no open instance), `103 duplicate_watch`, `104 daily_cap`. A refusal changes nothing.
5. The side-file record is removed once a save that contains the accepted `watch_id` has been written; on launch, any record still in the file is re-submitted (idempotent through 103).

The command uses the **current** open instance of `quest_id`, not the instance that was open when the video started, so a watch that straddles a daily reset counts toward the new day's quest (Edge Cases). `ad_watches_applied` is pruned to the watch ids of the current and previous period of each ad quest.

**R10 — Declining, skipping and no-fill.** Closing the video before the earned callback grants nothing and costs nothing; the quest stays open and the button returns. No-fill, SDK errors and offline state show "No ad available right now — try again later" and retry the load with F1 back-off while the quest is open and the app is in the foreground. There is **no fallback grant** in this GDD (OQ-3). Nothing in the game nags: no pop-up suggests watching, and the quest list is the only entry point.

**R11 — Ad content and placement rules (data, network console).** Ad unit ids live in data, not code (`ad_unit_banner_android`, `ad_unit_rewarded_android`). Debug and internal-test builds use the network's test unit ids and test-device registration and never request live ads. Sensitive ad categories that conflict with a general-audience fantasy game (gambling, dating, political) are blocked in the network console; the list is maintained by the user, not by code (OQ-8).

**R12 — Host signals.** Ads emits host signals (not Event-bus events) for Analytics (37) and the UI: `consent_state_changed(state, personalised)`, `banner_state_changed(state)`, `rewarded_state_changed(state)`, `ad_watch_credited(quest_id, watch_id)`, `ad_watch_refused(quest_id, reason)`. Analytics must only forward them under its own consent rules (OQ-4).

### States and Transitions

**Consent (per install)**

| State | Meaning | → Next | Trigger |
|---|---|---|---|
| `NoticePending` | Fresh install, privacy notice not yet acknowledged | `ConsentChecking` | *Continue* on the privacy notice (R3) |
| `ConsentChecking` | Asking the consent SDK for status | `FormShowing` / `ConsentResolved` / `ConsentUnknown` | SDK says form required / not required or already obtained / fetch failed |
| `FormShowing` | UMP form on screen | `ConsentResolved` | Player accepts, declines or manages choices |
| `ConsentUnknown` | Status could not be fetched; gate closed | `ConsentChecking` | App resume with network |
| `ConsentResolved` | SDK reports ads may (or may not) be requested, personalised or not | `FormShowing` | *Change ad choices* in Settings |

On PC/Web builds the machine stops at `NoticePending → ConsentResolved` with ads disabled (the notice is still shown for cloud and analytics).

**Banner (per session)**

| State | → Next | Trigger |
|---|---|---|
| `Off` (gate closed; band 0 if Premium/PC, else reserved and empty) | `Loading` | Gate opens (R2) |
| `Loading` | `Showing` / `Retrying` | Load success / failure |
| `Retrying` | `Loading` | F1 delay elapsed, app in foreground |
| `Showing` | `Hidden` | R7 suppression condition starts |
| `Hidden` | `Showing` | Suppression ends |
| any | `Off` | Gate closes (Premium, consent withdrawn to "no ads", app to background) |

**Rewarded (per session)**

| State | → Next | Trigger |
|---|---|---|
| `Idle` (no ad quest needs a watch, or gate closed) | `Loading` | An ad quest needs a watch and the gate is open |
| `Loading` | `Ready` / `Retrying` | Load success / no-fill or error |
| `Retrying` | `Loading` | F1 delay elapsed |
| `Ready` | `Showing` | Player taps *Watch ad* |
| `Showing` | `Earned` / `Idle`-or-`Loading` | Earned-reward callback / closed early or show error |
| `Earned` | `Loading` or `Idle` | `credit_ad_watch` submitted (R9); preload again if more watches needed |
| any | `Idle` | Gate closes (objects destroyed) |

### Interactions with Other Systems

| System | Direction | Data / call | Owner of the interface |
|---|---|---|---|
| Entitlement and feature flags (32) | Upstream, hard | Reads `is_premium` and a `ready` flag; listens for changes. Never reads IAP directly (IAP Interactions row "Ads (33)"). | Entitlement. **PROVISIONAL** — GDD not written. |
| Quests and achievements (25) | Upstream/sideways, hard | Reads open ad-variant quest instances (`quest_id`, `period_index`, `progress`, `count`, reward preview); the 3301 applier calls Quests' objective-progress API; Quests owns rewards, resets and `premium_auto_claim`. | Quests. **PROVISIONAL** — GDD not written. |
| Command layer (5) | Upstream, hard | Registers host-only command `credit_ad_watch` (3301) in block 3300, args `content(quests)`, `int(1, 2^62−1)`; reason codes 101–104. | Command layer owns the envelope; this system owns the type (id confirmed, consistency-check 2026-11-16). |
| Local save and migration (6) | Upstream, hard | New sim-state field `ad_watches_applied` (set of watch ids, pruned); pending-watch side file beside the save, written atomically. | Local save owns the format. **PROVISIONAL**. |
| Account and cloud save (7) | Sideways, soft | Its first-launch privacy-notice requirement is met by R3. Consent is not synced. | This system owns the notice. |
| In-app purchases (34) | Sideways, soft | Banner hidden while the store sheet / shop confirmation is open; Premium purchase reaches Ads only through Entitlement. | IAP for the sheet signal. |
| Settings (45) | Downstream, hard | Hosts *Privacy & ads*: reopen privacy notice, *Change ad choices* (R4.5), privacy policy link. | Settings owns the screen; this system owns the actions. |
| Guild screens (39), Realtime world view (38) | Downstream, hard | Every screen lays out above the banner band (R6); quest list shows the *Watch ad* row states (R8). | Screens own layout; this system owns band height and button state. |
| Onboarding and tutorial (44) | Upstream, soft | May mark steps `suppress_banner` (R7). | Onboarding. **PROVISIONAL**. |
| Audio (40) | Downstream, soft | Mutes game audio during a rewarded video. | Audio. **PROVISIONAL**. |
| Localization (4) | Upstream, hard | Notice, button and error strings in vi/en. The UMP form is localised by the SDK. | Localization. |
| Analytics (37) | Downstream, soft | Subscribes to R12 host signals. | Analytics. **PROVISIONAL**. |
| Leaderboards and anti-cheat (35) | Downstream, soft | Sees `credit_ad_watch` in the command log; credits are bounded by quest counts and F2, so a forged command gains nothing a real watch does not. | Leaderboards. |
| Data layer (3) | Upstream, hard | Reads `data/quests.csv` (`ad_variant`, `objective`, counts) and the new config keys (OQ-2). | Data layer. |

## Formulas

### F1 — `ad_retry_delay_s` (load back-off)

The ad_retry_delay_s formula is defined as:

`ad_retry_delay_s(n) = min(ad_retry_base_s × 2^(n−1), ad_retry_max_s)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n | int | 1–∞ | calculated | Consecutive failed loads of this format since the last success or app resume |
| ad_retry_base_s | int | 5–60 (10) | data file (`config.csv`, key to add, OQ-2) | First retry delay, seconds |
| ad_retry_max_s | int | 60–1800 (300) | data file (`config.csv`, key to add) | Cap on the delay, seconds |

**Output Range:** 10 s to 300 s at defaults (10, 20, 40, 80, 160, then 300 from n = 6). The counter resets to 0 on a successful load or app resume; retries pause while the app is in the background. At n large, the cap keeps requests to at most 12 per hour per format, inside network fair-use guidance (which is NOT SOURCEABLE here — check the network policy, OQ-8). Validator: `ad_retry_base_s ≥ 1` and `ad_retry_max_s ≥ ad_retry_base_s`.
**Example:** a rewarded ad fails three times in a row → waits 10 s, 20 s, 40 s; the fourth try fills.

### F2 — `rewarded_watches_max` (watches the game can credit)

The rewarded_watches_max formula is defined as:

`W_period(L) = Σ over quests q with ad_variant(q) = true, period(q) = period, min_guild_lv(q) ≤ L of (count_base(q) + count_per_guild_lv(q) × L)`

`W_day_max(L) = min(W_daily(L) + W_weekly(L), ad_rewarded_daily_max)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L | int | 1–guild level cap | calculated (Guild and buildings 30) | Current guild level |
| count_base, count_per_guild_lv, min_guild_lv, period, ad_variant | int / bool | per `quests.csv` | data file (`data/quests.csv`, exists) | Quest objective count and gating |
| ad_rewarded_daily_max | int | 1–10 (5) | data file (`config.csv`, key to add) | Safety cap on credits per local calendar day, enforced by the 3301 applier |

**Output Range:** with today's data `W_daily = 1`, `W_weekly = 3` for every L, so at most 4 credits in one day and 10 in a week (1 × 7 + 3). The cap 5 never binds at current data; it exists so a content edit (for example a non-zero `count_per_guild_lv`) cannot turn the quest list into an ad wall. Content validator: **error** if `W_daily(L) + W_weekly(L) > ad_rewarded_daily_max` for any L up to the level cap.
**Example:** guild level 4, fresh week: the player can watch 1 (daily) + 3 (weekly) = 4 ads today; a 5th tap is impossible because no quest needs a watch.

### F3 — `ad_reward_share` (balance observation for Quests and economy)

The ad_reward_share formula is defined as:

`share_gold(period, L) = Σ_ad gold(q, L) / Σ_all gold(q, L)`, where `gold(q, L) = reward_gold_base(q) + reward_gold_per_guild_lv(q) × L` over quests of that period with `min_guild_lv(q) ≤ L` (the same ratio with `reward_gem` gives `share_gem`).

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| reward_gold_base, reward_gold_per_guild_lv, reward_gem | int | per `quests.csv` | data file (`data/quests.csv`, exists) | Quest rewards |
| L | int | 1–level cap | calculated | Guild level |
| ad_reward_share_warn | float | 0.1–0.5 (0.30) | data file (`config.csv`, key to add) | Validator **warning** threshold (observation, not a block) |

**Output Range:** 0 to 1. At current data: daily gold 900 / 3,370 = **0.267** at L = 1, tending to 300/1,120 = 0.268 as L grows; daily Linh Bảo 10 / 41 = 0.244; weekly gold 3,000 / 12,000 = 0.25 at L = 1, 4,000 / 22,000 = 0.18 at L = 2 (the backlog-boss quest unlocks). So a Free player who never watches forgoes about a quarter of quest gold and Linh Bảo — the same amount a Premium player gets by auto-claim and a Free player gets by watching. Below the 0.30 warning, but large enough that "optional" deserves an economy check (OQ-1).
**Example:** L = 10 daily: ad quest pays 600 + 300 × 10 = 3,600 gold; all six daily quests pay 2,250 + 1,120 × 10 = 13,450; share = 0.268.

## Edge Cases

- **If Premium is bought while a rewarded video is playing**: the video finishes; an earned callback is still credited (the player watched it); then the gate closes, all ad objects are destroyed and the *Watch ad* rows disappear as Quests auto-claims. No watch is lost or double-paid (102 refuses a credit to an already auto-claimed quest).
- **If Premium is bought while the banner shows**: banner destroyed at once, band collapses to 0 on the next layout pass; no app restart needed.
- **If Premium is refunded (Entitlement → Free)**: no ad appears mid-session; the gate opens on the next app start. Rationale: an ad appearing the instant a refund lands looks like punishment and races Entitlement refreshes.
- **If Entitlement is not ready within the first seconds of launch**: gate stays closed; the band is reserved (Free layout assumed for a fresh install with no cache) and empty. If Entitlement then reports Premium, the band collapses once.
- **If the earned callback fires twice for one video** (SDK retry): the second creates a new `watch_id`, so it would be credited — guarded because Ads ignores any earned callback while `rewarded_state` is already `Earned` for the current show.
- **If the app is killed after the earned callback but before the save**: the pending-watch side file holds the record; on relaunch it is re-submitted and credited once (R9.5, 103 for repeats).
- **If a video straddles the daily or weekly reset**: the credit goes to the current open instance of the same quest (R9). If that instance is already satisfied, refused with 102 and the player sees "Today's ad quest is already done".
- **If the player watches while the guild is in a long offline hand-off** (video longer than `offline_threshold_s`, 60 s): the resume goes through the Sim core's normal path; the credit command is queued and applied in the first live tick, after the offline window. Nothing hunts twice.
- **If consent cannot be fetched (offline first launch)**: `ConsentUnknown`; no ads at all; every game feature works; the ad quest rows show "Ads unavailable offline". Retried on resume with network.
- **If the player withdraws consent in Settings**: subsequent requests are non-personalised/limited per the SDK; the banner is reloaded under the new choice; already-credited watches stand.
- **If the device blocks ads (ad blocker, private DNS)**: indistinguishable from no-fill; R10 applies; no detection, no warning.
- **If a cloud save from another device is adopted**: `ad_watches_applied` comes with the save (it is sim state); consent does not (platform settings). A pending side-file record from this device whose quest the adopted save already satisfied is refused 102 and dropped.
- **If `quests.csv` is edited so an `ad_variant` quest grants `item_pa_lens` or `item_pa_eye`**: content validator error (IAP AC-14; §11.5 "Thưởng của nhiệm vụ xem quảng cáo không bao giờ là Kính/Nhãn").
- **If `quests.csv` has `ad_variant = true` with an objective other than `watch_rewarded_ad`, or `premium_auto_claim = false` on an ad quest**: content validator error — a Premium player could never complete it (no ads for Premium).
- **If a forged `credit_ad_watch` is submitted** (modified client): bounded by the quest count and F2, so the most it can do is what real watching does; no leaderboard advantage beyond a legitimate Free player. Server-side verification is OQ-9.
- **If the PC/Steam build loads a Free save from mobile**: no ads; the ad quests are auto-claimed because the PC build is Premium by Entitlement (§11.1).

*`systems-designer` lens applied to C and D: F1 at n = 0 is unused (n starts at 1); F2 with all counts 0 gives no *Watch* row, valid; F3 with zero total gold is undefined → validator skips the ratio when the denominator is 0.*

## Dependencies

| System | Kind | Interface |
|---|---|---|
| Entitlement and feature flags (32) | **Hard, upstream** | `is_premium`, `ready`, change signal. Gate R2(b). |
| Quests and achievements (25) | **Hard, upstream** | Open ad-quest instances and reward preview; objective-progress API for the 3301 applier; `premium_auto_claim`. |
| Command layer (5) | **Hard, upstream** | Host submit path and registration of `credit_ad_watch` (3301). |
| Local save and migration (6) | **Hard, upstream** | Persists `ad_watches_applied`; pending-watch side file. |
| Data layer (3) | **Hard, upstream** | `quests.csv`, config keys, ad unit ids. |
| Localization (4) | **Hard, upstream** | All strings. |
| Settings (45) | Hard, downstream (UI) | *Privacy & ads* entry. |
| Guild screens (39), Realtime world view (38) | Hard, downstream (UI) | Banner band, *Watch ad* row. |
| Account and cloud save (7) | Soft, sideways | Privacy notice covers cloud backup. |
| In-app purchases (34) | Soft, sideways | Store-sheet suppression signal. |
| Onboarding (44), Audio (40) | Soft, upstream/downstream | `suppress_banner`; mute during video. |
| Analytics (37), Leaderboards (35) | Soft, downstream | Host signals; command log. |

Bidirectional check: the systems index lists 33 → Entitlement only. Quests, Command layer, Local save, Data layer and Localization are added because the reward path (R9) and the strings need them; the index row's Depends On is updated accordingly. Settings (45) already lists Ads as a dependency. Account and cloud save lists "Ads and consent (33)" as owner of the privacy notice — consistent. IAP lists Ads as reading Premium via Entitlement only — consistent. Entitlement, Quests, Guild screens, Onboarding, Audio and Analytics must add Ads when their GDDs are written (Open Questions).

## Tuning Knobs

| Knob | Default | Safe range | Too low | Too high | Source |
|---|---|---|---|---|---|
| `ad_retry_base_s` | 10 | 5–60 | Hammers the network on no-fill | Player waits long after a transient error | `config.csv` (to add) |
| `ad_retry_max_s` | 300 | 60–1800 | Excess requests in low-fill regions | Ad stays unavailable long after fill returns | `config.csv` (to add) |
| `ad_rewarded_daily_max` | 5 | 1–10 | Blocks legitimate quest watches (validator error if below F2's W) | Allows an ad wall if quest counts grow | `config.csv` (to add) |
| `ad_reward_share_warn` | 0.30 | 0.1–0.5 | Warnings on every content change | Never warns about ad-heavy rewards | `config.csv` (to add) |
| `ad_banner_fallback_dp` | 50 | 50–90 | Banner overlaps content if SDK size is larger | Wastes screen on small phones | `config.csv` (to add) |
| `ad_unit_banner_android`, `ad_unit_rewarded_android` | test ids in debug | — | — | — | data (to add), never in code |
| `ad_privacy_policy_url` | — | — | — | — | data (to add) |
| Banner refresh rate, blocked ad categories, mediation | network console | network rules | — | — | Network console, not game data |

Quest counts and rewards (`quests.csv`) are Quests' (25) knobs; they feed F2 and F3 here and must not be duplicated.

## Visual/Audio Requirements

- Banner band: a plain strip in the UI palette, separated from game content by a 1 px divider so the ad never reads as part of the guild UI. No frame, label or icon that imitates game UI around the ad (network policy and honesty).
- *Watch ad* button: the quest row's normal button style plus a small "video" glyph; reward icons (gold, Linh Bảo) identical to the quest reward display.
- Audio: game music and SFX muted (not paused) while a rewarded video plays and restored on close (Audio 40). No sound plays when a banner refreshes.
- No VFX. No celebratory effect beyond Quests' normal quest-complete feedback.

## Game Feel

- Banner never animates in over content; it appears inside its already-reserved band.
- *Watch ad* responds to the tap within one frame (button pressed state) and the video opens within the SDK's show latency; if no ad is ready, the button is disabled rather than accepting a tap and failing.
- After the video closes, the quest row updates within one tick of the credit command (≤ 100 ms at 10 Hz) so the reward feels earned at once.

## UI Requirements

- **Banner band** on every screen in the Free mobile build (R6), including modal dialogs that do not cover the full screen; full-screen modals (consent form, rewarded video, store sheet) hide it (R7). All layouts must fit Vietnamese strings above the band on a 1080×2400 screen.
- **Privacy notice** (first launch, R3): title, 3–4 short bullet lines (cloud backup, guest account, ads, analytics), privacy-policy link, *Continue*. vi/en.
- **Quest row** for ad quests: *Watch ad* with reward and count, states Loading / Ready / No ad available / Ads unavailable offline / Done; hidden for Premium (Quests shows the auto-claimed row).
- **Settings → Privacy & ads** (Settings 45): *Ad privacy settings* (reopens the consent form), *Privacy notice*, *Privacy policy* link. Hidden on PC/Web except the notice and policy.
- Accessibility: button states by text as well as colour; the banner band is not focusable; screen readers skip it.

> **📌 UX Flag — Ads**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` for the privacy notice, the quest-row ad states and the Settings privacy entry **before** writing epics.

## Cross-References

| This GDD | References | Their section | Relationship |
|---|---|---|---|
| R2, Edge Cases | In-app purchases | Interactions row "Ads (33)", R4 (store sheet), R11 (refund), R12 (no pressure prompts), AC-14 | Premium via Entitlement only; suppression during purchase; same no-upsell rule; ad rewards never lens/eye |
| R3 | Account and cloud save | Interactions row "Ads and consent (33)", AC-18 (Free banner visible) | Owns the first-launch privacy notice; banner band in its conflict screen |
| R4.6 | Local save and migration | "What the system does not own" (ad consent in platform settings) | Consent kept out of the save |
| R9 | Command layer | R2 registration, ID blocks (owner × 100), R8 host submit, R9 replay | Registers `credit_ad_watch` 3301 in block 3300 |
| R8.5, Edge Cases | Sim core and tick loop; Offline progress | Sim core R8 (`offline_threshold_s` hand-off); Offline progress R4 | Video does not pause the sim; long video resumes through normal hand-off |
| F2, F3 | `data/quests.csv` | `q_d_watch_ad`, `q_w_watch_ad`, `ad_variant`, `premium_auto_claim` | Source of ad quest counts and rewards |
| R1–R11 | JX1_Tycoon_GDD.md | §2, §3.1, §11.2, §11.3, §11.4, §11.5, §12.1, §14, Prompt P5, P7 | Source of formats, consent, Premium/PC rules, spike |

## Acceptance Criteria

Story types: **[Logic]** automated unit test; **[Integration]** automated test against a fake ad SDK, fake consent SDK and fake Entitlement; **[UI]** retained screenshot in `production/qa/evidence/`; **[Device]** manual check on a real Android device in the P1 spike / pre-launch.

- **AC-1 [Logic] (R2 gate, Premium)**: **GIVEN** fake Entitlement `ready = true, is_premium = true` and consent resolved, **WHEN** the app starts and runs 10 minutes with an open ad quest, **THEN** the fake ad SDK records zero load and zero show calls, band height = 0, and no *Watch ad* row exists.
- **AC-2 [Logic] (R2 fail-closed)**: **GIVEN** Entitlement `ready = false`, **WHEN** 30 s pass, **THEN** zero ad requests are made; **WHEN** Entitlement becomes `ready, is_premium = false`, **THEN** the banner loads within one gate evaluation.
- **AC-3 [Logic] (R2 PC build)**: **GIVEN** the PC export preset, **WHEN** the build is inspected, **THEN** it contains no ad SDK library and the Ads service reports `disabled_platform`.
- **AC-4 [Integration] (R3, R4 order)**: **GIVEN** a fresh install in a consent-required region (fake SDK), **WHEN** the app launches, **THEN** the privacy notice shows first, then the consent form, and the fake ad SDK receives no request before the form returns.
- **AC-5 [Integration] (R4 decline)**: **GIVEN** the player declines in the consent form, **WHEN** an ad quest is open, **THEN** ads are requested in non-personalised mode and the *Watch ad* row still works; every non-ad feature is reachable.
- **AC-6 [Integration] (R4.4 offline)**: **GIVEN** no network at first launch, **WHEN** the notice is acknowledged, **THEN** state = `ConsentUnknown`, zero ad requests, ad rows read "Ads unavailable offline"; **WHEN** the app resumes with network, **THEN** consent is checked again.
- **AC-7 [Logic] (R6 band)**: **GIVEN** the Free build and a fake SDK that reports adaptive height 56 dp, **WHEN** the first screen lays out, **THEN** the band = 56 dp before any ad loads, and does not change when the ad fills; **GIVEN** the SDK reports no size, **THEN** band = `ad_banner_fallback_dp`.
- **AC-8 [Integration] (R7 Premium mid-session)**: **GIVEN** a banner showing, **WHEN** Entitlement changes to Premium, **THEN** the banner object is destroyed and the band is 0 on the next layout pass, without restart.
- **AC-9 [Logic] (R8 offer)**: **GIVEN** `q_w_watch_ad` open with progress 3/3, **WHEN** the quest list renders, **THEN** no *Watch ad* button is shown and no rewarded ad is preloaded.
- **AC-10 [Logic] (R9 credit)**: **GIVEN** `q_d_watch_ad` open at 0/1, **WHEN** the fake SDK fires earned-reward, **THEN** `credit_ad_watch` is accepted, progress = 1/1, `watch_id` ∈ `ad_watches_applied`.
- **AC-11 [Logic] (R9 refusals)**: **GIVEN** the end state of AC-10, **WHEN** the same `watch_id` is re-submitted, **THEN** refused 103; **WHEN** a new `watch_id` is submitted for `q_d_watch_ad`, **THEN** refused 102; **WHEN** submitted for `q_d_hunt`, **THEN** refused 101; no state changes in each case.
- **AC-12 [Logic] (R10 skip)**: **GIVEN** a rewarded ad showing, **WHEN** the fake SDK closes it without earned-reward, **THEN** no command is submitted and the quest progress is unchanged.
- **AC-13 [Integration] (R9.5 crash)**: **GIVEN** an earned callback written to the side file and the process killed before save, **WHEN** the app relaunches, **THEN** the watch is credited exactly once and the side file is empty after the next save.
- **AC-14 [Logic] (F1)**: **GIVEN** defaults 10/300, **WHEN** loads fail n = 1…7 times, **THEN** delays are 10, 20, 40, 80, 160, 300, 300 s; a success resets n.
- **AC-15 [Logic] (F2 validator)**: **GIVEN** `quests.csv` edited so `q_w_watch_ad.count_base = 5`, **WHEN** the content validator runs, **THEN** it reports an error (1 + 5 > 5); with current data it passes; **GIVEN** 5 credits already today, **WHEN** a 6th valid credit is submitted, **THEN** refused 104.
- **AC-16 [Logic] (F3 report)**: **GIVEN** current `quests.csv`, **WHEN** the validator runs, **THEN** it prints `share_gold(daily, 1) = 0.267`, `share_gold(weekly, 1) = 0.25`, `share_gem(daily) = 0.244` and no warning at threshold 0.30; at threshold 0.25 it prints a warning for the daily share, and exits successfully (warning, not error).
- **AC-17 [Logic] (content rules)**: **GIVEN** a `quests.csv` row with `ad_variant = true` and `premium_auto_claim = false`, or `reward_items` containing `item_pa_lens`, **WHEN** the validator runs, **THEN** it fails.
- **AC-18 [Device] (P1 spike, §12.1)**: **GIVEN** a real Android device with the Godot 4.7 build and AdMob test units, **WHEN** the banner and a rewarded test ad run and a UMP test geography (EEA) is forced, **THEN** the consent form appears before any request, the banner fits the band inside safe-area insets, and the earned callback credits the quest. Records plugin and SDK versions (closes the NOT SOURCEABLE item).
- **AC-19 [Integration] (R1 boundary)**: **GIVEN** the parity harness, **WHEN** a full rewarded flow runs, **THEN** the only command from Ads in the log is `credit_ad_watch`, no Event-bus event is emitted by Ads, and two saves with the same commands, one Free and one Premium, differ only in quest-claim path, not in totals.
- **AC-20 [UI]**: Screenshots of the privacy notice, the consent form (test geography), the quest list with *Watch ad* in each state, the Settings *Privacy & ads* entry, and a guild screen with the banner band, in vi and en on a 1080×2400 screen, retained in `production/qa/evidence/`.

*`qa-lead` lens applied: every rule R2–R10 and F1–F3 has a criterion. R11 (console category blocking) and R12 (signal list) are checked by review, not test — flagged here rather than dropped. Game Feel timings are playtest checks.*

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | Balance: F3 shows ad quests carry about 27% of daily quest gold and 24% of Linh Bảo. Is a Free player who never watches acceptably behind? Needs quest income as a share of total income from the balance simulator. | economy-designer / Quests author | Before Alpha balance pass |
| OQ-2 | Schema change, not made here: add `config.csv` keys `ad_retry_base_s`, `ad_retry_max_s`, `ad_rewarded_daily_max`, `ad_reward_share_warn`, `ad_banner_fallback_dp`, and a data home for ad unit ids and `ad_privacy_policy_url`; add validator checks AC-15–AC-17. | Data layer (3) / User | Alpha |
| OQ-3 | No-fill fallback: should repeated "no ad available" (low-fill regions, ad blockers) eventually let the player claim the ad quest without a video? Rejected here because it changes Quests' rules; Quests (25) may decide otherwise. | Quests author / User | When 25 is designed |
| OQ-4 | Analytics consent: does the R3 notice suffice for analytics, or does Analytics (37) need its own opt-in in GDPR regions? Ads signals must not be forwarded before that is settled. | Analytics author / User | When 37 is designed |
| OQ-5 | Store age rating and target audience: confirm not child-directed (Play Families policy not opted in). If children are included, ad formats, networks and consent tags must be redesigned. | User | Before Play listing |
| OQ-6 | iOS: ATT prompt wording and timing, SKAdNetwork ids, UMP on iOS. Not verifiable without Apple Developer membership (§12.1). | User | Before iOS |
| OQ-7 | Web build monetization is not defined in GDD §11; this GDD assumes no ads on Web. | User | Before Web |
| OQ-8 | **NOT SOURCEABLE** — Godot 4.7 Android AdMob/UMP plugin API, adaptive banner sizing, mediation adapters, network fair-use and policy rules are not covered by `docs/engine-reference/godot/`. Verify in the P1 spike (AC-18) before an ADR; user maintains the blocked-category list. | User / technical-director | P1 spike |
| OQ-9 | Server-side verification (SSV) of rewarded callbacks: worth it for leaderboard hygiene? Current design: client callback only, credits bounded by quest counts. | Leaderboards author / User | When 35 is designed |
| OQ-10 | **PROVISIONAL: Entitlement and feature flags (32)** — assumes it exposes `ready` and `is_premium` with a change signal on the host side, reports definite Free for a fresh install once its first local check completes, and reports Premium for the PC build. | Entitlement GDD author | When 32 is designed |
| OQ-11 | **PROVISIONAL: Quests and achievements (25)** — assumes quest instances with `quest_id`, `period_index`, `progress`, `count`; an objective-progress API callable from a command applier; `premium_auto_claim` handled by Quests from the entitlement snapshot; reset times in local calendar days. | Quests GDD author | When 25 is designed |
| OQ-12 | **RESOLVED (consistency-check 2026-11-16):** command id 3301 in block 3300 (unique in the registry; Command layer R2 lets owners allocate in their block). Reason codes were `3301-1…4`, which are not integers (Command layer R4); renumbered to 101–104. | Command layer GDD author | Closed |
| OQ-13 | **PROVISIONAL: Local save (6)** — new sim-state field `ad_watches_applied` (pruned to current and previous period) and the pending-watch side file. | Local save GDD author | When 6 is revised |
| OQ-14 | **PROVISIONAL: Onboarding (44), Audio (40), Guild screens (39), Settings (45)** — `suppress_banner` flag on onboarding steps; mute during video; banner band in every layout; *Privacy & ads* entry. | Each owner | When each is designed |

*Post-design note — CD-GDD-ALIGN run in this session against GDD §2/§11 text (no pillars, concept or brief exist): no interrupting formats (R1), Premium and PC never see ads (R2), rewarded watches are opt-in and only through quests (R8), ad rewards never include Kính/Nhãn (Edge Cases, AC-17). Concern noted for a later review: F3's ~25% reward share tests how "optional" the watch is (OQ-1). Verdict recorded as NOT ASSESSED because the required pillar input is missing.*
