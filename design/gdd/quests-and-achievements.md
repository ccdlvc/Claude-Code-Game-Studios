# Quests and Achievements

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: design-system skill (autonomous batch run) for the user
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief exist to check against (see Open Questions, post-design note)
> **Implements Pillar**: None (no `game-pillars.md` yet). Serves JX1_Tycoon_GDD.md §2 (daily/weekly quests are the Free build's only rewarded-ad surface, Premium claims directly), §6.6 (Linh Bảo comes from quests and achievements), §7 (Quest/Achievement → "Nhiệm vụ chính + Thành tựu"), §11.4 (daily and weekly quests), §11.5 (free Thiên Cơ Kính rules) and §17.1 (`data/quests.csv`)

## Summary

Quests and achievements give the guild master a short list of goals that renews every day and every week, plus a permanent book of one-time milestones. They watch what the guild already does (hunts, Golden Boss raids, sales, recruits, crafts, builds), never order members around, and pay guild gold, the premium currency Linh Bảo and a few capped special items, including the one free Thiên Cơ Kính a week. They exist to give each session a reason to open the app, to host the optional rewarded-ad slot of the Free build without making ads pay for power, and to be the main faucet of Linh Bảo.

> **Quick reference** — Layer: `Feature` · Priority: `Vertical Slice` · Key deps: `Event bus, Command layer, Gold economy, Items and loot, Data layer, RNG, Guild and buildings, Zones and hunt, Golden Boss, Recruitment, Crafting, Market, Offline progress, Entitlement and feature flags, Ads`

## Overview

**Data layer.** Quests and achievements is an event-bus subscriber with its own small save section. It reads quest definitions from `data/quests.csv` (12 rows today: 6 daily, 6 weekly) and, once the table exists, achievement definitions from a proposed `data/achievements.csv` (Open Questions OQ-2). It keeps one **quest board** per guild: the daily and weekly *instances* currently offered, each with a target and reward fixed when the period began, and a progress counter. It also keeps a **milestone book**: lifetime counters and the state of every achievement. Progress moves only when an event that another system already emits is delivered to it (Event bus R4). The player's input is limited to claiming rewards; the host's input is the wall-clock period (which day and week it is), delivered as a command so the simulation stays deterministic and replayable. All rewards are paid through their owners: gold and Linh Bảo through the Gold economy ledger (entry types 5 `quest_reward`, 60 `lb_quest`, 61 `lb_achievement`), items through Items and loot storage.

**Player impact.** Every morning the board shows five or six small goals in guild terms ("hunt 40 monsters", "join a Golden Boss raid", "take in a recruit"). Most complete on their own while the guild plays or the phone sleeps; the player comes back, taps *Claim*, and sees gold and Linh Bảo land. One slot each day and week is the optional ad (Free) or a direct claim (Premium). Finishing every non-ad weekly goal pays one Thiên Cơ Kính, the game's only steady free source of exact PA reveals. Achievements mark the long arc: the first rebirth, the Tổng Đàn's eighth level, a +15 blade. Without this system the idle loop has no daily cadence, the Free build has no non-intrusive ad slot, Linh Bảo has no source, and the free lens promised in §11.5 does not exist.

This GDD stays at the behaviour level. Implementation choices (one Godot node or a plain object, how the board is serialised) are ADR material and are not decided here.

## Player Fantasy

*Framing (Progression → both direct and indirect):* the player engages with the board directly (reading it, claiming), but most of the work is done by the guild running itself.

Three framings were considered (creative-director lens; no pillars exist, so each is anchored to JX1 GDD text):

1. **"The notice board at dawn" (chosen).** Anchor: §11.4 and §7 (Cáo Thị Đường, "cũng là nguồn nhiệm vụ ngày/tuần"). *The moment:* the player opens the app on the bus, the board has reset overnight, and four of six slips already carry a red seal because the guild hunted and fought the hourly boss while they slept. They tap *Claim all*, the fund ticks up, and the last two slips (sell five items, take in a recruit) are things they can do in the next minute. *Asks of the design:* goals that the guild's normal life completes, rewards that land with a visible beat, and a board that is never empty or stale.
2. **"The sect's annals."** Anchor: §7 ("Nhiệm vụ chính + Thành tựu… có cốt truyện"). *The moment:* months in, the player scrolls the achievement book and sees "First Elder ascended — Day 63". *Asks:* a long list of milestones worth reading, and a narrative chain. Kept as the achievements half of this system, but not the primary fantasy, because the content for a story chain does not exist yet (OQ-3).
3. **"The steward's ledger."** The quests as an efficiency puzzle to optimise each day. Rejected: it pushes towards micromanagement and fights the idle loop (§1: the guild runs itself).

What the chosen fantasy asks of the rules: quest objectives are things the guild already does (no quest may require an action that only exists for the quest, except the optional ad), completion while away counts (R4, R9), nothing is lost by not opening the app on a given day except the chance to claim that day's slips (R7: unclaimed completed slips are paid at reset), and a free player who never watches an ad still earns the weekly lens (R6).

## Detailed Design

*Specialist lenses applied (Section 6 routing, row "Progression/XP/skills": game-designer primary; systems-designer, economy-designer supporting; no agents spawned):*

- **game-designer (primary).** The loop this serves is the session loop of an idle game: open, read, claim, nudge, close. Decisions are few on purpose: which slip to finish first, whether to watch the optional ad, when to spend a lens so the weekly one is not wasted. The player cannot reroll a quest, buy a completion, or skip the wait for reset. Warning: a quest that only completes when the player is away (defeat a *backlog* boss) rewards absence; it is kept because the data has it, and whether it should gate the weekly lens (R6) is OQ-5.
- **systems-designer (supporting).** Every objective needs one named event source, or it is not offered (R3) — otherwise `complete_all_weekly` becomes impossible and the free lens silently disappears. The period must be monotonic or clock changes multiply resets (R2). Progress is clamped at the target so a burst of events cannot overflow anything.
- **economy-designer (supporting).** Quest gold is small next to hunting (F2, F7: at most about 10,000 gold a day at guild level 8, against `income_ref` of 1,000 gold per member-level per hour) and is a fund mint that needs no new sink. Linh Bảo is the real faucet (F6: up to 402 a week); its sink is the Linh Bảo shop (Gold economy R16, user decision 2026-11-16: Chiêu Hiền Lệnh, enhancement wards, the Scripture token for school change, special items), priced by Gold economy F9 against this faucet. Linh Bảo is never sold for real money. The free lens must not undercut paid lenses: it is capped by `pa_lens_weekly_free` and `pa_lens_stock_cap` (IAP R9).
- **Tension surfaced and resolved by the logged decision:** game-designer (wall-clock days, so "daily" means a real day) against systems-designer (game-time days, as Gold economy R8 does, for determinism). Resolved with a host-delivered wall-clock day index applied as a command: deterministic in replay and true to the real calendar (R2).

### Core Rules

**R1 — Definitions are data.** A quest row in `data/quests.csv` has: `id`, `period` (`daily` | `weekly`), `objective` (one of the closed set in R3), `count_base`, `count_per_guild_lv`, `reward_gold_base`, `reward_gold_per_guild_lv`, `reward_gem` (Linh Bảo), `reward_items` (`item_id:qty;…`), `ad_variant`, `premium_auto_claim`, `min_guild_lv`. The content validator already enforces (§17, `tools/content_validator.py`): period is daily or weekly; reward items exist; an `ad_variant` row never rewards `item_pa_lens` or `item_pa_eye`; `item_pa_eye` is never a quest reward; every `ad_variant` row has `premium_auto_claim = true`; the weekly lens total equals `pa_lens_weekly_free`; at least 5 daily rows. Liveness follows the Data layer's single wave query (Data layer R2 gating): a row that is not live in the current wave is never offered.

**R2 — The period clock is wall-clock and monotonic.** Quests reset on the real calendar, not on game time, because offline game time is capped (Offline progress: 12 h for every player — user decision 2026-11-16) and a game-time "day" would stretch to several real days for a casual player, breaking §11.5's one free lens per week.
1. The host computes the trusted UTC now exactly as Offline progress R3 does (server estimate when known, else `GameClock.utc_s()`), and from it the **day index** `D` and **week index** `W` (F4). Reset is at `quest_reset_utc_s` past each UTC midnight (default 61,200 = 00:00 in UTC+7). Weeks begin on Monday.
2. The host submits the host-only command `quest_clock(day_index, session_start)` (R10) at every app start and resume (`session_start = 1`) and, while running, whenever its computed `D` changes (`session_start = 0`). The host checks `D` at most once a minute; a minute of lag at reset is accepted.
3. The simulation stores `cur_day` and `cur_week`. A `quest_clock` with `day_index > cur_day` **rolls** the daily board (R7); if `W(day_index) > cur_week` it also rolls the weekly board. A `day_index < cur_day` is refused with `101 clock_behind` and changes nothing. Equal is accepted and only counts the login (R3).
4. **Effect on clock tampering:** setting the clock forward gives one early reset, after which `cur_day` sits ahead of real time and every `quest_clock` is refused until real time catches up. Resets over any span are therefore at most the real days elapsed plus one (Edge Cases). The same "borrow, never multiply" property as Offline progress R3.4.
5. Because the day index enters as a logged command, a replay (Leaderboards 35, Dev tooling 43) reproduces every reset exactly. Nothing in the simulation reads a clock.

**R3 — Objectives are a closed table, each with one event source.** An objective with no live source is **not offered** (it is never shown as an impossible slip, and it is excluded from `complete_all_weekly`, R6). Progress `+n` is applied when the listed event is delivered:

| Objective | Source (event or command) | Progress per delivery | Live when |
|---|---|---|---|
| `kill_monsters` | Zones and hunt 1102 `hunt_monster_killed`; Offline progress 3102 `offline_member_summary` | +1 per 1102; +`c` (kills) per 3102 | MVP |
| `join_golden_boss` | Golden Boss 1403 `gb_won`, 1404 `gb_lost` | +1 per raid that was fought (a skipped raid, 1405, does not count) | MVP |
| `sell_items_market` | Market 2901 `catalogue_sale`, 2902 `stock_sale` | +1 per sale event | Market (29) live |
| `accept_candidate` | Recruitment 1502 `candidate_accepted` | +1 | Recruitment (15) live |
| `login` | this system's `quest_clock` command (R2) | set to 1 when any `quest_clock` is accepted for the current day | always |
| `watch_rewarded_ad` | in-sim API `add_ad_progress(quest_uid)` (R5), called by Ads' (33) applier of its host command 3301 `credit_ad_watch` after a completed rewarded view | +1 | Ads (33) live and Premium not active (R5) |
| `craft_items` | Crafting 2802 `craft_unit_done` | +1 per unit | Crafting (28) live |
| `upgrade_building` | Guild and buildings 3003 `build_completed` | +1 | MVP |
| `complete_bounties` | **none** — no system owns the Cáo Thị Đường bounty board (OQ-1) | — | never, until OQ-1 is resolved |
| `defeat_backlog_boss` | Golden Boss 1406 `gb_backlog_resolved` with a won result (PROVISIONAL payload, OQ-8) | +1 per won backlog raid | MVP |
| `complete_all_weekly` | this system (R6) | completes when the R6 condition holds | always |

Achievements (R8) may also use these lifetime objectives: `reach_guild_level` (3004 `guild_level_up`, value = new level), `reach_member_level` (2201 `member_level_up`, value = `c`), `member_reborn` (2301), `member_ascended` (2302), `reach_enhance_level` (2403 `enhance_milestone`, value = `c`), `pa_revealed` (902 `pa_exact_revealed`), and every counting objective above as a lifetime total. A new objective is added here, with its source, never invented in data.

**R4 — Progress.** One subscriber (owner `quests`, order 2500) listens to the source types above. For each delivered record, in emission order, it adds the progress to every **Active** instance with that objective on the current boards and to the matching lifetime counter (R8). Progress is clamped at the target; an instance reaching its target becomes **Completed** and emits `quest_completed` (2503) in the next tick (Event bus R6: subscriber emits land next tick). Events about entities not in the player's guild never arrive (every listed source is guild-scoped). Progress is never negative and never decreases within a period. Offline progress counts: its summary events (3102, 1406) arrive in the first live tick after the skip and are applied to the board current at that moment (R9).

**R5 — The ad slot.** An instance whose row has `ad_variant = true`:
- **Free entitlement:** progresses only through `add_ad_progress(quest_uid) → ok | not_ad_quest | satisfied`, an in-sim call made by the applier of Ads' host command 3301 `credit_ad_watch` (Ads R9), which owns the watch record, duplicate protection (`ad_watches_applied`) and the per-day cap `ad_rewarded_daily_max`. This system checks only that the current open instance of `quest_uid` is an ad slot with `progress < target`, then adds 1. A watch that straddles a reset counts toward the new day's instance (Ads R9). Watching is always optional; nothing else on the board depends on it (R6).
- **Premium entitlement:** if `premium_auto_claim = true`, the instance is **claimable without progress** — the Premium player taps *Claim* and receives the reward directly (§2, §11.2: "nhận thẳng thưởng, không xem quảng cáo"). It is also paid at reset like any completed slip (R7). For Premium, `add_ad_progress` returns `satisfied` (Ads shows no *Watch* button for Premium anyway, Ads R8).
- Premium is read as `feature_on(ad_quest_direct_claim)` from Entitlement's sim view (Entitlement 32 R3: the snapshot enters as the logged host command `set_entitlement`), at the moment the claim or the roll is applied. A Premium refund mid-period simply turns the slot back into an ad slot from the next claim on (Edge Cases).
- Ad-slot rewards never include `item_pa_lens` or `item_pa_eye` (validator, R1).

**R6 — The weekly lens gate (`complete_all_weekly`).** The `q_w_all_done` instance completes when **every other weekly instance offered this week with `ad_variant = false`** is Completed or Claimed. Ad slots are excluded so the free lens is the same for Free and Premium and never requires watching an ad (§11.5: "Free và Premium nhận như nhau"; "Thưởng của nhiệm vụ xem quảng cáo không bao giờ là Kính/Nhãn"). Objectives with no live source (R3) are not offered and therefore not required. If no other non-ad weekly instance is offered, `complete_all_weekly` itself is not offered (it would complete for nothing). Today, at guild level 1 with no bounty board, the gate is: craft 15 units and complete 2 building upgrades in the week; from guild level 2 it adds one won backlog boss (OQ-5).

**R7 — Rolling a board.** When R2 rolls a period, in this order, inside the `quest_clock` applier:
1. **Pay what was earned.** Every Completed-but-unclaimed instance of the closing board, and every Premium-claimable ad slot (R5), is claimed automatically by R11's grant steps (the lens stock rule F5 applies; what does not fit is skipped and reported, `free_lens_skipped` 2505). The closing period's claims are counted in `quest_period_rolled` (2501).
2. **Drop the rest.** Active instances of the closing board are discarded. Progress never carries over.
3. **Build the new board.** Take every live row of that period whose `min_guild_lv ≤ guild_level` (Guild and buildings: completed `bld_hq` level, 1–8) and whose objective has a live source (R3), in ascending row `uid`. If their count exceeds `quest_daily_max` (or `quest_weekly_max`), choose that many with F3 (RNG domain 17 `quest_roll`); otherwise offer all. `complete_all_weekly` is decided last (R6).
4. **Snapshot each instance:** `target = F1`, `gold = F2`, `gem = reward_gem`, `items = reward_items`, all at the current `guild_level`. Instances never change after this, even if the guild levels up or a content patch edits the row.
5. Emit `quest_period_rolled` (2501).
A roll that skips several days (the app was closed) rolls once: intermediate days had no board and pay nothing. A first-ever `quest_clock` on a new guild builds both boards with no step 1.

**R8 — Achievements (milestone book).** An achievement is a one-time, guild-wide goal that never resets. Each has an objective from R3 (a lifetime count, or a threshold on an event's value), a `target`, rewards (Linh Bảo through `lb_achievement`, gold through `quest_reward`, items), and an optional `requires` (another achievement that must be Claimed first). `requires` chains are how the "main quest" line of §7 is expressed — one mechanism for both; the chain's content and story are Narrative's (OQ-3).
- **Counting:** the system keeps one int64 lifetime counter per counting objective (`kills_total`, `raids_fought_total`, …) and one high-water value per threshold objective (`max_guild_level`, `max_member_level`, `max_enhance_level`, …). They only rise.
- An achievement is **Locked** until its `requires` is Claimed, **Active** after, **Completed** when its counter or high-water reaches the target, then **Claimed**. Unlike quests it is never auto-claimed or lost: a completed achievement waits for the player forever.
- Locked achievements still advance their counters (counters are shared per objective), so unlocking a chain step whose target is already met completes it at once.
- Achievement definitions live in a proposed table (Open Questions OQ-2, columns listed there). Until it exists, the book is empty and this rule is dormant; daily and weekly quests do not depend on it.
- Free lens rewards from achievements are limited by content rule: the sum over all achievements of `item_pa_lens` rewards is at most `achievement_lens_total_max` (4, the IAP F3 assumption `M`), and `item_pa_eye` is never a reward (§11.5).

**R9 — Away time.** Quests are an elapsing system in Offline progress's sense, but they own no game-time due tick: the board changes only on `quest_clock`. On resume, the host submits `quest_clock` before the `advance` call that resolves the gap; it applies in P1 of the first live tick, and the offline summary events are delivered in P6 of the same tick. So a reset that happened while away is applied first, and everything the guild did while away counts toward the **new** day's board. This is generous on purpose (the guild worked; the player should see slips sealed when they return) and is listed in Edge Cases.

**R10 — Commands** (Command layer block 2500–2599; applied in P1):

| ID | Command | Args | Origins | Reason codes |
|---|---|---|---|---|
| 2501 | `quest_clock` | `day_index` int(0, 2^31−1), `session_start` int(0, 1) | host | 101 `clock_behind` |
| 2502 | `claim_quest` | `quest` content(quests) | host | 6 `target_missing`, 102 `not_complete`, 103 `already_claimed`, 104 `lens_stock_full` |
| 2503 | `claim_achievement` | `achievement` content(achievements) | host | 6, 102, 103, 104 |

"Claim all" in the UI is a `submit_batch` of 2502 per claimable slip (Command layer R12). Ad watches do not enter through this block: Ads owns `credit_ad_watch` (3301) and calls `add_ad_progress` (R5); the simulation cannot verify an ad was watched and does not try (the reward is small, never a lens, and Free-only). Applier cost: O(board size ≤ 12) for 2502–2503 and `add_ad_progress`; 2501 with a roll is O(rows ≤ 12 + RNG draws ≤ 12). No sim-origin requests (peak 0 per tick).

**R11 — Claiming.** `claim_quest` / `claim_achievement` on a Completed (or Premium-claimable, R5) entry:
1. If the rewards include `item_pa_lens`, compute the grant with F5. On an explicit claim, if F5 grants fewer than requested, the claim is refused with `104 lens_stock_full` and nothing changes — the player can spend a lens and claim again. (At roll, R7 step 1, the claim proceeds with the partial grant instead.)
2. Credit gold: `credit(quest_reward, fund, gold, quest_uid)` if `gold > 0`.
3. Credit Linh Bảo: `credit(lb_quest, linh_bao, gem, quest_uid)` (achievements: `lb_achievement`) if `gem > 0`.
4. Give items: Items and loot `give({item: qty, …})` into guild storage.
5. Mark Claimed and emit `quest_claimed` (2504) or `achievement_claimed` (2507).
Ledger credits never fail for a valid amount (Gold economy R5: they clamp at the cap). If `give` refuses (PROVISIONAL, OQ-10), the whole claim is refused with `8 cannot_afford`-style handling deferred to Items' code, and no credit is made: steps 2–4 are checked before any is applied (Gold economy R4.2 pattern).

**R12 — Events** (Event bus block 2500–2599, registered at boot):

| ID | Name | Fields | Logged | Milestone | `ring_per_day` |
|---|---|---|---|---|---|
| 2501 | `quest_period_rolled` | `a` period (1 daily, 2 weekly), `b` period index, `c` instances offered, `d` auto-claimed | yes | no | 2 |
| 2502 | `quest_progressed` | `a` quest uid, `b` progress, `c` target | no | no | 0 |
| 2503 | `quest_completed` | `a` quest uid, `b` period, `c` period index | yes | no | 12 |
| 2504 | `quest_claimed` | `a` quest uid, `b` gold, `c` Linh Bảo, `d` 1 if auto (R7) | no | no | 0 |
| 2505 | `free_lens_skipped` | `a` source uid, `b` requested, `c` granted | yes | no | 1 |
| 2506 | `achievement_completed` | `a` achievement uid | yes | yes (subject 0) | 0 |
| 2507 | `achievement_claimed` | `a` achievement uid, `b` Linh Bảo, `c` lens granted | no | no | 0 |

`quest_progressed` is emitted at most once per instance per tick (coalesced), so a tick with 50 kills emits one per affected slip. Ring total 15 per day, 0.15% of the default ring budget of 10,000 (Event bus F4).

**R13 — Saved state** (Local save 6 registers this system's serializer under the one `schema_version`): `cur_day`, `cur_week`, both boards (per instance: quest uid, target, progress, gold, gem, items, state), `login_day`, the lifetime counters and high-waters (R8), and per achievement its state. Every int64 is a JSON string (Sim core R6). A migration from a save with no quest section starts with an empty board and `cur_day = −1` (the next `quest_clock` builds both boards); lifetime counters are seeded from the migrated save where the data exists (OQ-7).

### States and Transitions

**Quest instance** (one per offered row per period):

| State | Meaning | → To | Trigger |
|---|---|---|---|
| (none) | Not on the board | `Active` | Period roll offers the row (R7 step 3) |
| `Active` | Counting | `Completed` | progress reaches target (R4), or an `add_ad_progress` call brings it there (R5) |
| `Active` | | discarded | period roll (R7 step 2) |
| `Active` (Premium ad slot) | Claimable without progress | `Claimed` | `claim_quest` or roll (R5, R7 step 1) |
| `Completed` | Waiting for claim | `Claimed` | `claim_quest` accepted (R11) or roll auto-claim (R7 step 1) |
| `Completed` | | `Completed` | `claim_quest` refused `104 lens_stock_full` (stays) |
| `Claimed` | Paid | discarded | period roll |

**Achievement** (permanent):

| State | → To | Trigger |
|---|---|---|
| `Locked` | `Active` | its `requires` becomes Claimed (or it has none: starts Active) |
| `Active` | `Completed` | counter or high-water ≥ target (checked on each delivery and on unlock) |
| `Completed` | `Claimed` | `claim_achievement` accepted |

**Period clock:** `cur_day = −1` (no board) → `cur_day = D` on the first `quest_clock`; afterwards only increases. There is no invalid transition: a lower day index is refused (R2.3).

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Event bus (42) | bus → this | Source events of R3, one batch per tick | Types 2501–2507 | Event bus (subscriber order 2500, block 2500–2599) |
| Command layer (5) | both | 2501–2503 envelopes | reason codes | Command layer framing; this GDD owns rules |
| Data layer (3) | data → this | `quests.csv`, proposed `achievements.csv`, `config.csv` keys, wave liveness | — | Data layer |
| Gold economy (27) | this → 27 | — | `credit(quest_reward \| lb_quest \| lb_achievement, …)` | Gold economy (entry types 5, 60, 61); this system owns amounts |
| Items and loot (26) | both | `count(item_pa_lens)` | `give(items)` | Items (R7 storage API) |
| RNG (2) | this → RNG | — | domain 17 `quest_roll`, key `(period, period_index, draw_ordinal)` | RNG; this GDD owns key layout (F3) |
| Guild and buildings (30) | 30 → this | `guild_level` read at roll (inside the applier, a read the Command layer allows appliers); events 3003, 3004 | — | Guild and buildings |
| Zones and hunt (11), Golden Boss (14), Recruitment (15), Crafting (28), Market (29), XP curve (22), Rebirth (23), Enhancement (24), CA/PA (9) | → this | Their events (R3) | — | Each emitter |
| Offline progress (31) | → this | 3102 kills, ordering of R9 | — | Offline progress |
| Entitlement (32) | → this | `feature_on(ad_quest_direct_claim)` from the sim view (Entitlement R3); `grant_trial` as a possible reward (Entitlement R10, OQ-15) | — | Entitlement |
| Ads (33) | Ads' applier → this | `add_ad_progress(quest_uid)` from command 3301 (Ads R9) | which slips are ad slots and their rewards (read-only, for the *Watch* row) | Ads owns the command; this system owns progress and payout |
| In-app purchases (34) | sideways | — | free lens supply obeys IAP R9 | Quests owns `pa_lens_weekly_free` semantics |
| Local save (6) | both | — | save section (R13) | Local save |
| Guild screens (39), Realtime view (38), Audio (40), Analytics (37), Push (46) | this → them | — | boards, book, events | Read between ticks only (Sim core R15) |

## Formulas

All formulas are integer arithmetic at play time. *Lens applied: systems-designer (Section D) with the economy-designer cost checks; every formula was worked at 0, its default and its maximum.*

### F1: `quest_target`

The quest_target formula is defined as:

`quest_target = count_base + count_per_guild_lv × (L − 1)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| count_base | int | 1 – 10,000 | data file (`quests.csv`) | Target at guild level 1 |
| count_per_guild_lv | int | 0 – 1,000 | data file (`quests.csv`) | Added per guild level above 1 |
| L | int | 1 – 8 | calculated (completed `bld_hq` level at roll) | Guild level snapshot |

**Output Range:** today 1 (login, recruit, boss, ads) to 110 (`q_d_hunt` at L 8). `count_base = 0` is rejected by the validator (a target of 0 would complete on creation; proposed new validator rule, OQ-11).
**Example:** `q_d_hunt` at guild level 4: 40 + 10 × 3 = **70** kills. `q_w_craft` at level 8: 15 + 5 × 7 = **50** units.
*Why (L − 1):* `count_base` reads as the level-1 value in the data; with `× L` a level-1 guild would need 50 kills, not 40.

### F2: `quest_gold`

The quest_gold formula is defined as:

`quest_gold = reward_gold_base + reward_gold_per_guild_lv × (L − 1)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| reward_gold_base | int | 0 – 1,000,000 | data file (`quests.csv`) | Gold at guild level 1 |
| reward_gold_per_guild_lv | int | 0 – 100,000 | data file (`quests.csv`) | Added per guild level above 1 |
| L | int | 1 – 8 | calculated | As F1 |

**Output Range:** 0 (`q_w_all_done`) to 13,500 (`q_w_backlog_boss` at L 8: 3,000 + 1,500 × 7). 0 means no gold credit is made (the ledger refuses amounts ≤ 0, Gold economy R4.4).
**Example:** `q_d_golden_boss` at L 3: 500 + 250 × 2 = **1,000** gold to the fund.

### F3: `quest_selection`

The quest_selection rule is defined as:

`offered = E` if `|E| ≤ M`, else the first `M` of a partial Fisher–Yates shuffle of `E` with `j_i = i + bounded(|E| − i)` for `i = 0 … M − 1`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| E | list | 0 – rows of that period | calculated | Eligible rows (R7 step 3), ascending `uid` |
| M | int | 1 – 12 | data file (`quest_daily_max` 6, `quest_weekly_max` 6; new `config.csv` keys) | Board size per period |
| bounded(n) | int | 0 – n−1 | RNG domain 17 `quest_roll`, key `(period, period_index, i)` | Exactly uniform draw (RNG rejection sampling) |

**Output Range:** `min(|E|, M)` instances. `|E| = 0` → empty board (only possible if every row is gated; the validator's "≥ 5 daily rows" keeps it non-empty at level 1).
**Example:** today 6 daily rows and `M = 6` → all offered, **no draw**. The weekly board has 6 rows minus `q_w_bounty` (no source) minus `q_w_backlog_boss` below level 2 → 4 at level 1 (craft, upgrade, weekly ad, all-done), no draw.
`complete_all_weekly` is never a candidate in the shuffle; it is added after if R6 allows, and does not count toward `M`.

### F4: `period_index`

The period_index formula is defined as:

`D = floor((utc_s − quest_reset_utc_s) / 86,400)`; `W = floor((D − quest_week_start_day) / 7)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| utc_s | int | ≥ 0 | calculated (host, Offline progress R3 trusted UTC) | Seconds since 1970-01-01 UTC |
| quest_reset_utc_s | int | 0 – 86,399 | data file (`config.csv`, new, default 61,200) | Reset time of day in UTC seconds (61,200 = 17:00 UTC = 00:00 UTC+7) |
| quest_week_start_day | int | 0 – 6 | data file (`config.csv`, new, default 3) | The value of `D mod 7` whose game day is a Monday; it depends on `quest_reset_utc_s` and must be re-derived if that knob changes |
| D, W | int | ≥ 0 | calculated | Day and week index |

Game day `D` begins at UTC instant `D × 86,400 + quest_reset_utc_s`. With the default offset that instant is local midnight UTC+7 of the calendar date after UTC date `D`, so `D mod 7 = 3` is a Monday (1970-01-01, date index 0, was a Thursday).

**Output Range:** `D` grows by 1 per real day; `W` by 1 per real week, at the Monday reset.
**Example:** `utc_s = 1,800,000,000` (2027-01-15 08:00 UTC = 15:00 UTC+7, Friday): `D = floor(1,799,938,800 / 86,400) = 20,832` (`20,832 mod 7 = 0`, Friday), `W = floor(20,829 / 7) = 2,975`. Day 20,835 begins 2027-01-18 00:00 UTC+7 (Monday, `mod 7 = 3`) and `W` becomes 2,976; day 20,842 (Monday 2027-01-25) gives 2,977. Values checked with a calendar library.

### F5: `free_lens_grant`

The free_lens_grant formula is defined as:

`granted = min(n, max(0, pa_lens_stock_cap − stock))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n | int | 0 – 4 | data file (reward `item_pa_lens:n`) | Lenses this reward offers |
| stock | int | ≥ 0 | calculated (Items `count(item_pa_lens)`, paid and free alike) | Lenses in guild storage now |
| pa_lens_stock_cap | int | 1 – 20 | data file (`config.csv`, 5) | Free-grant stock cap (§11.5 "tồn kho tối đa 5"; IAP R9) |

**Output Range:** 0 to `n`. A stock above the cap (paid deliveries ignore the cap, IAP R9) gives 0, never negative.
**Example:** stock 4, weekly lens `n = 1` → granted 1. Stock 5 → granted 0: an explicit claim is refused (`104`), a roll grants 0 and emits `free_lens_skipped` (2505).

### F6: `linh_bao_weekly`

The linh_bao_weekly formula is defined as:

`LB_week = 7 × Σ_daily(gem_i × done_i) + Σ_weekly(gem_j × done_j)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| gem | int | 0 – 1,000 | data file (`quests.csv` `reward_gem`) | Linh Bảo per claim |
| done | int | 0 – 1 | calculated | 1 if the slip is completed in that period (daily `done` assumed constant across the week) |

**Output Range:** 0 to **402** if every row of today's data were offered (daily 41 × 7 = 287; weekly 20 + 25 + 20 + 30 + 20 = 115); **382** while the bounty board does not exist (OQ-1). A Free player who never watches ads: 31 × 7 + 75 = **292** at guild level ≥ 2 without the bounty board; 262 at level 1. Achievements add one-off amounts (OQ-2).
**Example:** a Premium player who completes everything except the backlog boss: 287 + 85 = 372 Linh Bảo a week.
*Economy check:* Linh Bảo is never converted to gold (Gold economy R1). It is spent in the Linh Bảo shop (Gold economy R16; from Vertical Slice), whose prices are sized as 0.1–1.0 week of this faucet (Gold economy F9, `LB_week_ref` = 382). Unspent, 402/week accumulates to about 21,000 a year, far below `linh_bao_balance_max` (10,000,000).

### F7: `quest_gold_share` (simulator metric, not a rule)

The quest_gold_share formula is defined as:

`share = quest_gold_day / (quest_gold_day + hunt_income_day)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| quest_gold_day | int | 0 – 17,161 | calculated (Σ daily F2 + Σ weekly F2 / 7) | Quest gold per day, all slips done |
| hunt_income_day | int | ≥ 0 | calculated (balance simulator; Gold economy F4 reference `1,000 × L × 24` per member) | Guild hunting income per day |

**Output Range:** 0 to 1. Target: ≥ 0.15 in the first 2 days of a new guild (quests are a visible early boost) and ≤ 0.05 after day 14 (quests never become the income source). At guild level 1 all-done gold is 2,250/day + 11,000/7 ≈ 3,821; at level 8, 10,090 + 49,500 / 7 ≈ 17,161 (weekly totals include every row, so these are upper bounds).
**Example:** a day-1 guild of 5 level-5 members hunting 30% of the day: `1,000 × 5 × 24 × 0.3 × 5` = 180,000 → share ≈ 0.02. **This misses the 0.15 early target by an order of magnitude**; quest gold is decorative at the data's current values. Recorded as OQ-4 for the balance simulator (S5) rather than retuned here.

## Edge Cases

*Lens applied: systems-designer, Section E checks over Sections C and D.*

- **If the device clock is set forward N days**: the next `quest_clock` rolls once (one early reset, rewards of the closing board paid). Every later `quest_clock` with a smaller day index is refused (`101`) until real time reaches the stored `cur_day`. Net resets over any span ≤ real days + 1. The weekly lens can be pulled forward by at most one week, never doubled.
- **If the device clock is set back**: refused (`101`); the board stays as it is and keeps counting progress.
- **If the player travels across time zones**: nothing changes; the reset is fixed in UTC (F4), never local time.
- **If the app is closed for several days**: one roll on return (R7); intermediate days pay nothing; the closing board's completed slips are paid.
- **If a reset passes while the app is closed and the guild hunted offline**: the roll applies first and the offline kills count toward the new day (R9). Documented generosity, not a bug.
- **If two `quest_clock` commands arrive in one P1** (resume and a minute check): applied in `seq` order; the second has an equal day index and only counts the login.
- **If the guild levels up mid-period**: targets and rewards stay as snapshot (R7 step 4); new rows unlocked by `min_guild_lv` appear at the next roll.
- **If a content patch changes or removes a row mid-period**: the instance keeps its snapshot and stays claimable; a removed reward item is skipped at claim and logged as a content error by the validator on the next build (OQ-10).
- **If the lens stock is at or above the cap when the weekly lens is claimed**: explicit claim refused with `104` (the slip stays Completed); at roll, granted 0, other rewards of that slip are paid, `free_lens_skipped` emitted.
- **If an achievement lens cannot be granted (stock full)**: the claim is refused with `104` and the achievement stays Completed forever, so a one-off lens is never lost.
- **If Premium is bought mid-period**: the ad slot becomes claimable without progress from the next claim or roll (R5). Any ad progress already made is irrelevant.
- **If Premium is refunded mid-period** (IAP R11): the ad slot is an ordinary ad slot again from the next claim; a reward already claimed is not clawed back (small, never a lens).
- **If an ad watch is credited for a completed or Premium slot**: `add_ad_progress` returns `satisfied` and Ads refuses 3301 with `3301-2 quest_satisfied`; no double reward.
- **If the Ads SDK reports a reward but the command is lost** (app killed before submit): the view is not counted; the player can watch another. The simulation cannot know, and the reward is too small to warrant a recovery protocol.
- **If a burst of events would push progress past the target**: clamped (R4); one `quest_completed`.
- **If an objective's source system is not live** (bounty board, Market before Vertical Slice): the row is not offered and does not block `complete_all_weekly` (R3, R6).
- **If no non-ad weekly row is offered**: `complete_all_weekly` is not offered, and no free lens is earned that week. With today's data this cannot happen (craft and upgrade are always offered once Crafting is live); before Crafting is live it can (OQ-5).
- **If Linh Bảo would exceed `linh_bao_balance_max`**: Gold economy clamps and records the excess (Gold economy R5).
- **If a claim's item `give` is refused**: no part of the claim applies (R11), the slip stays Completed.
- **If a save happens mid-period**: the board and counters are saved (R13); after load, progress continues; the next `quest_clock` decides whether to roll.
- **If a save from before this system is loaded**: empty board, `cur_day = −1`; the next `quest_clock` builds both boards; lifetime counters start from seeded values (OQ-7).
- **Degenerate strategy — new-guild farming:** creating a fresh guild resets nothing about the old one; rewards are per guild and per day, so there is no loop. **Degenerate strategy — waiting for absence:** `defeat_backlog_boss` is only satisfiable by being away for more than an hour; a player who plays constantly cannot finish it (OQ-5). **Degenerate strategy — ad spam:** the ad slot's target is 1 (daily) / 3 (weekly); further `quest_ad_watched` are refused.

## Dependencies

### Upstream (this system depends on)

| System | Hard/Soft | Interface | Status |
|---|---|---|---|
| Event bus and history log (42) | Hard | `subscribe` (order 2500), `register_type` block 2500–2599 | GDD exists (Needs Revision) |
| Command layer (5) | Hard | `register_command` 2501–2503, reason codes 101–104 | GDD exists |
| Data layer (3) | Hard | `quests.csv`, wave liveness, `config.csv` keys; proposed `achievements.csv` | GDD exists |
| Gold economy (27) | Hard | ledger `credit` with types 5, 60, 61 | GDD exists |
| Items and loot (26) | Hard | `count`, `give` | GDD exists |
| RNG (2) | Soft (only above `M`) | domain 17 `quest_roll` | GDD exists |
| Guild and buildings (30) | Hard | `guild_level`; events 3003, 3004 | GDD exists |
| Zones and hunt (11) | Soft | 1102 | GDD exists |
| Golden Boss (14) | Soft | 1403, 1404, 1406 | GDD exists (1406 payload PROVISIONAL) |
| Recruitment (15) | Soft | 1502 | GDD exists |
| Crafting (28) | Soft | 2802 | GDD exists |
| Market (29) | Soft | 2901, 2902 | GDD exists (systems index row does not list it; added here) |
| Offline progress (31) | Soft | 3102; R9 ordering | GDD exists |
| XP curve (22), Rebirth (23), Enhancement (24), CA/PA (9) | Soft (achievements only) | 2201, 2301, 2302, 2403, 902 | GDDs exist |
| Entitlement and feature flags (32) | Soft | `feature_on(ad_quest_direct_claim)`; `grant_trial` | GDD exists |
| Ads (33) | Soft | calls `add_ad_progress` from its 3301 applier | GDD exists |
| Local save (6) | Hard | serializer registration | GDD exists |

### Downstream (systems that depend on this one)

| System | Hard/Soft | Interface |
|---|---|---|
| In-app purchases (34) | Soft, sideways | free lens supply and cap semantics (IAP R9) |
| Guild screens (39) | Hard | board, book, claim commands |
| Ads (33) | Hard (for its only rewarded surface) | ad slots |
| Analytics (37), Audio (40), Realtime view (38), Push (46), Onboarding (44) | Soft | events 2501–2507 |
| AI text / Chronicle (36) | Soft | 2506 milestone |

**Bidirectional check:** the systems index row lists RNG, Event bus, Zones and hunt, Golden Boss, Recruitment, Gold economy, Crafting, Guild and buildings, Data layer. This GDD adds Command layer, Items and loot, Market, Offline progress, Local save (hard or soft as above), Entitlement and Ads (provisional) and the achievement event sources; the index row's Depends On is updated accordingly. Each existing upstream GDD already names Quests (25) as a consumer (Crafting, Recruitment, Golden Boss, Zones, Items, Guild and buildings, Gold economy, IAP, RNG, Event bus, Local save); Market (29), Offline progress (31), XP curve (22), Rebirth (23), Enhancement (24) and CA/PA (9) do not yet list Quests for the events used here — flagged for the consistency pass, not edited here.

## Tuning Knobs

| Knob | Default | Safe range | Too high | Too low | Owner / location |
|---|---|---|---|---|---|
| `quests.csv` `count_base`, `count_per_guild_lv` | per row | target reachable in ≤ 30% of a period by normal play | slips never complete; board feels like chores | slips complete before the player sees them | this system, `data/quests.csv` |
| `quests.csv` `reward_gold_*` | per row | F7 share 0.05–0.15 | quests become the income source | rewards invisible (today's state, OQ-4) | this system |
| `quests.csv` `reward_gem` | per row | F6 ≤ ~500/week; a change here rescales Gold economy F9 (`LB_week_ref`) and the Linh Bảo shop prices | Linh Bảo shop items become routine | no Linh Bảo source | this system |
| `quests.csv` `min_guild_lv` | 1 (backlog boss 2) | 1–8 | rows never seen | early board crowded | this system |
| `quest_daily_max` (new) | 6 | 5–8 | board noise, chore feel | rows never offered | `config.csv` |
| `quest_weekly_max` (new) | 6 | 4–8 | as above | as above | `config.csv` |
| `quest_reset_utc_s` (new) | 61,200 | 0–86,399 | — (time of day) | — | `config.csv`; market choice per launch region |
| `quest_week_start_day` (new) | 3 | 0–6 | weeks start on the wrong weekday | as too high | `config.csv`; must be re-derived whenever `quest_reset_utc_s` changes (F4) |
| `achievement_lens_total_max` (new) | 4 | 0–8 | paid lenses undercut (IAP F3) | no milestone lenses | `config.csv`; IAP F3 `M` must match |
| `pa_lens_weekly_free` | 1 | 0–3 | paid lenses pointless | free players never see a reveal | `config.csv`; **semantics owned here**, registered by IAP (34) |
| `pa_lens_stock_cap` | 5 | 1–20 | hoarding | free lenses wasted | `config.csv`; as above |

Interacting knobs: `pa_lens_weekly_free` must equal the weekly rows' lens total (validator) and, with `achievement_lens_total_max`, sets IAP F3's free supply; changing one without the other breaks the IAP pricing model. `quest_daily_max` below the number of always-live daily rows turns on the RNG draw (F3), which changes which slips players see.

Knobs owned elsewhere and only read: `linh_bao_balance_max`, `gold_op_max` (Gold economy), `guild_level` range (Guild and buildings), `offline_cap_*_h` (Offline progress), `history_ring_cap` (Event bus).

## Visual/Audio Requirements

Optional for Progression; brief notes. No art bible exists (`design/art/art-bible.md` absent), so this is drafted from §1 and §7.

- **The board** is a wooden notice board (Cáo Thị Đường styling, even when the building is not built) with paper slips; a completed slip gets a red seal stamp; a claimed slip is torn off. Ad slips carry a small distinct icon (not colour alone).
- **Claim** plays a short coin/seal beat and a gold or Linh Bảo count-up toward the HUD; "Claim all" chains the beats quickly (≤ 1.5 s total regardless of count).
- **Reset** while the app is open: a soft gong and the board re-papers itself. Suppressed during catch-up (Sim core R15); the "while you were away" report says "New day's notices posted" instead.
- **Achievement completed**: a banner with the achievement name, larger than a quest beat, logged into the Chronicle.
- **Free lens skipped**: a quiet warning toast ("Lens storage full — this week's lens was not added"), never a loud sound.

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:quests-and-achievements` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

Optional for Progression. Targets: a claim responds within one frame of the tap (optimistic UI; the command applies next tick, Command layer R11), and the board is readable in under 3 seconds ("which slips can I finish now?"). Completed-but-unclaimed slips sort to the top. No feel target depends on simulation timing.

## UI Requirements

- **Quest board screen** (Guild screens 39): two tabs, Daily and Weekly; each slip shows objective text (localised from the objective key and target), a progress bar `progress / target`, rewards (gold, Linh Bảo, item icons), and its state (Active, Completed, Claimed). A countdown to the next reset (from the host's F4 computation). "Claim all" button when any slip is claimable.
- **Ad slip**: Free shows "Watch ad" (disabled with a reason when Ads reports no fill or no consent); Premium shows "Claim" directly. Never shown as a pop-up or interstitial (§11.2 principle).
- **Weekly lens slip** explains what it needs ("Finish every other weekly notice — ads not required") and, when the lens stock is full, shows "Use a lens first" instead of Claim.
- **Achievement book**: list grouped by objective kind, Locked entries greyed with their prerequisite named, Completed entries claimable. Chain (main quest) entries appear in order.
- **Badges**: a count badge on the board's entry point when anything is claimable.
- **Refusal text** for 101–104 via `cmd_reason.quests.<name>` (Command layer R6; Localization 4).
- Accessibility: states are not conveyed by colour alone (seal stamp, check mark); text scales.

> **📌 UX Flag — Quests and achievements**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the quest board and achievement book **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD | Other document | Section / item | Nature |
|---|---|---|---|
| R1, R6, F5 | `JX1_Tycoon_GDD.md` | §2, §11.2, §11.4, §11.5, §17.1 | Source of intent |
| R11, F6 | `gold-economy.md` | R3 types 5, 60, 61; R4; R5 clamp; F6 conservation | Ledger contract |
| R11, F5 | `items-and-loot-tables.md` | R7 storage API (`count`, `give`) | Reward delivery |
| R5, R6, F5, Tuning | `in-app-purchases.md` | R9, F3 `M`, Tuning `pa_lens_*` | Free lens supply and cap (answers its PROVISIONAL rows) |
| R4, R12 | `event-bus-and-history-log.md` | R3, R4, R6, F4 | Subscriber and emitter rules |
| R10 | `command-layer.md` | R2 blocks, R6 reason codes, R12 batches | Command contract |
| F3 | `deterministic-rng.md` | domain 17 `quest_roll` | Selection draws |
| R2, R9 | `offline-progress.md` | R3 trusted UTC, R15 summary events | Clock trust and away-time ordering |
| R3 | `zones-grounds-monsters-and-hunt-trips.md` | 1102 | Kill source |
| R3 | `golden-boss-and-guild-raid.md` | R15–R17 (1403–1406) | Raid sources |
| R3 | `recruitment.md` | 1502 | Recruit source |
| R3 | `crafting-and-recipes.md` | 2802, AC-26 | Craft source |
| R3 | `guild-market-and-trade-orders.md` | 2901, 2902 | Sale source |
| R3, R7 | `guild-and-buildings.md` | R9 `guild_level`, 3003, 3004; `bounty_slots`, `bounty_reward_mult` (OQ-1) | Level and build source |
| R8 | `xp-and-level-pacing-curve.md`, `rebirth-and-ascension.md`, `equipment-enhancement.md`, `ca-pa-and-traits.md` | 2201; 2301, 2302; 2403; 902 | Achievement sources |
| R13 | `local-save-and-migration.md` | R5, R6, R14 | Save section |

## Acceptance Criteria

*(qa-lead lens applied: one or more criteria per core rule and formula, boundaries at 0 and caps, cross-system checks. [Logic] = automated unit test in `tests/unit/quests/`; [Integration] = real Sim core, Command layer, Event bus and Gold economy; [UI] = screenshot in `production/qa/evidence/`.)*

**Period clock (R2, F4)**
- **AC-1 [Logic] (R2.3)**: **GIVEN** `cur_day = 100`, **WHEN** `quest_clock(99, 1)` is applied, **THEN** it is refused with 101 and the board, `cur_day` and login are unchanged; **WHEN** `quest_clock(100, 0)` **THEN** accepted with no roll and `q_d_login` progress = 1; **WHEN** `quest_clock(101, 0)` **THEN** exactly one daily roll (one 2501 with `a = 1`).
- **AC-2 [Logic] (R2.4)**: **GIVEN** `cur_day = 100`, **WHEN** `quest_clock(107, 1)` then `quest_clock(101, 1)` … `quest_clock(106, 1)` then `quest_clock(108, 1)`, **THEN** exactly two daily rolls happen in total and every command from 101 to 106 is refused with 101.
- **AC-3 [Logic] (F4)**: **GIVEN** `quest_reset_utc_s = 61,200`, **WHEN** F4 is evaluated at `utc_s` 1,799,945,999 and 1,799,946,000 (2027-01-15 00:00 UTC+7), **THEN** `D` is 20,831 and 20,832 respectively (the reset instant is the boundary).
- **AC-8 [Logic] (F4)**: **GIVEN** the default knobs, **WHEN** `W` is computed for every UTC+7 local midnight from 2027-01-11 to 2027-01-25, **THEN** `W` increments exactly at 2027-01-18 00:00 and 2027-01-25 00:00 UTC+7 (Mondays) and at no other instant.

**Board and roll (R7, F1, F2, F3)**
- **AC-4 [Logic] (R7, F1, F2)**: **GIVEN** guild level 4 and today's `quests.csv`, **WHEN** the daily board rolls, **THEN** it holds all 6 daily rows, `q_d_hunt` has target 70 and gold 750, `q_d_golden_boss` target 1 and gold 1,250, and no RNG domain-17 draw was made.
- **AC-5 [Logic] (R7 step 4)**: **GIVEN** a daily board rolled at guild level 1, **WHEN** the guild reaches level 3 mid-day, **THEN** `q_d_hunt` keeps target 40 and gold 300 until the next roll.
- **AC-6 [Logic] (F1 boundary)**: **GIVEN** guild level 8, **THEN** `q_d_hunt` target = 110 and `q_w_backlog_boss` gold = 13,500; **GIVEN** level 1, `q_w_all_done` gold = 0 and no `quest_reward` ledger entry is made when it is claimed.
- **AC-7 [Logic] (F3)**: **GIVEN** a test table of 9 eligible daily rows and `quest_daily_max = 6`, **WHEN** two guilds with the same seed roll day index 500, **THEN** both offer the same 6 rows; **WHEN** one rolls day 501, **THEN** its draws use keys `(1, 501, 0..5)` and the set is reproducible by replaying the command log.
- **AC-9 [Logic] (R3, R7)**: **GIVEN** no bounty board system and guild level 1, **WHEN** the weekly board rolls, **THEN** `q_w_bounty` and `q_w_backlog_boss` are absent and `q_w_all_done` is present; at level 2 `q_w_backlog_boss` is present.
- **AC-10 [Logic] (R7 steps 1–2)**: **GIVEN** a daily board with `q_d_hunt` Completed unclaimed and `q_d_sell` Active at 3/5, **WHEN** the next day rolls, **THEN** `q_d_hunt`'s gold and Linh Bảo are credited once (2504 with `d = 1`), `q_d_sell` is discarded unpaid, and the new board's `q_d_sell` starts at 0.

**Progress (R3, R4, R9)**
- **AC-11 [Integration] (R3, R4) [with Zones, Offline]**: **GIVEN** an Active `q_d_hunt` with target 40, **WHEN** 25 1102 events are delivered and then one 3102 with `c = 30`, **THEN** progress reads 40 (clamped), exactly one 2503 is emitted, and the lifetime `kills_total` rises by 55.
- **AC-12 [Integration] (R3) [with Golden Boss]**: **GIVEN** an Active `q_d_golden_boss`, **WHEN** a raid is skipped (1405), **THEN** progress stays 0; **WHEN** a raid is lost (1404), **THEN** it completes.
- **AC-13 [Integration] (R3) [with Crafting]**: **GIVEN** `q_w_craft` with target 20, **WHEN** two craft orders of 10 units complete, **THEN** progress reads 20 (Crafting AC-26).
- **AC-14 [Integration] (R9) [with Offline progress]**: **GIVEN** a save on day 100 and an 8 h absence crossing the reset, **WHEN** the host submits `quest_clock(101, 1)` then `advance`, **THEN** in the first live tick the daily roll precedes the delivery of 3102, and the offline kills count toward day 101's `q_d_hunt`.
- **AC-15 [Logic] (R4)**: **GIVEN** 50 kill events in one tick and two Active kill slips, **THEN** at most one 2502 per slip is emitted for that tick.

**Ads, Premium and the weekly lens (R5, R6, F5)**
- **AC-16 [Integration] (R5) [with Ads]**: **GIVEN** a Free view and `q_d_watch_ad` Active, **WHEN** `credit_ad_watch(q_d_watch_ad, w1)` and then `credit_ad_watch(q_d_watch_ad, w2)` are applied, **THEN** the first completes it (`add_ad_progress` → ok) and the second is refused with `3301-2` because `add_ad_progress` returns `satisfied`.
- **AC-17 [Logic] (R5)**: **GIVEN** a Premium snapshot and `q_d_watch_ad` Active at 0, **WHEN** `claim_quest(q_d_watch_ad)` is applied, **THEN** 600 gold (level 1) and 10 Linh Bảo are credited; **WHEN** `add_ad_progress(q_d_watch_ad)` is called, **THEN** it returns `satisfied`.
- **AC-18 [Logic] (R6)**: **GIVEN** a Free guild at level 1 that completes `q_w_craft` and `q_w_upgrade` but never watches an ad, **THEN** `q_w_all_done` becomes Completed.
- **AC-19 [Logic] (F5, R11)**: **GIVEN** 5 lenses in storage and `q_w_all_done` Completed, **WHEN** `claim_quest(q_w_all_done)` is applied, **THEN** refused with 104 and nothing changes; **WHEN** the week rolls instead, **THEN** 0 lenses are given, 2505 is emitted with `b = 1, c = 0`; **GIVEN** 4 lenses, the claim gives exactly 1.
- **AC-20 [Logic] (validator, §11.5)**: **GIVEN** `data/quests.csv` with an `ad_variant = true` row rewarding `item_pa_lens`, **WHEN** the content validator runs, **THEN** it fails (shared with IAP AC-14).

**Claims and ledger (R11) [Integration, with Gold economy and Items]**
- **AC-21**: **GIVEN** `q_d_recruit` Completed at level 2, **WHEN** claimed, **THEN** the ledger shows one `quest_reward` of 600 to the fund and one `lb_quest` of 8 to Linh Bảo, the F6 conservation identity holds, and a second claim is refused with 103.
- **AC-22**: **GIVEN** `q_d_hunt` Active, **WHEN** claimed, **THEN** refused with 102 and no ledger entry exists.

**Achievements (R8)** — *[PENDING: OQ-2, the achievements table]*
- **AC-23 [Logic]**: **GIVEN** test achievements A (kill 100) and B (kill 500, requires A), and 600 kills already counted, **WHEN** A is claimed, **THEN** B moves Locked → Active → Completed in the same applier and emits 2506 once.
- **AC-24 [Logic]**: **GIVEN** an achievement rewarding one lens and 5 lenses in storage, **WHEN** claimed, **THEN** refused with 104 and it stays Completed; after one lens is used, the claim succeeds.
- **AC-25 [Logic] (content rule)**: **GIVEN** achievement rows whose lens rewards sum to 5 with `achievement_lens_total_max = 4`, **WHEN** the validator runs, **THEN** it fails.

**Save and events (R12, R13)**
- **AC-26 [Integration] (R13)**: **GIVEN** a board mid-day with progress 17/40, **WHEN** saved and loaded, **THEN** the board, progress, snapshot rewards and `cur_day` are identical and the digest after 100 further ticks matches an unsaved run.
- **AC-27 [Logic] (R12)**: **GIVEN** a booted bus, **WHEN** types are sealed, **THEN** 2501–2507 are registered under owner `quests` with the flags of R12 and a ring total of 15 per day; the subscriber has order 2500.
- **AC-28 [UI]**: a screenshot of the quest board showing Active, Completed and Claimed slips, an ad slip in Free and Premium variants, and the full-lens-stock message on the weekly lens slip.

*Gaps found by the QA lens:* "the board is readable in under 3 seconds" and "rewards feel worth the tap" are playtest questions (PT-1, PT-2 in Open Questions), not ACs. AC-23–AC-25 cannot run until the achievements table exists (OQ-2).

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Scope — bounty board (Cáo Thị Đường, `bld_bounty`, `complete_bounties`).** Guild and buildings lists `bounty_slots` and `bounty_reward_mult` as read by Quests, and §7 says the building is "also the source of daily/weekly quests", but no system owns bounties (what a bounty is, how one is generated, how it pays). Should this system own them (a lean design: procedurally pick a monster from a zone the guild can reach, target N kills, gold/XP × `bounty_reward_mult`, `bounty_slots` concurrent), or should a separate system? Until decided, `q_w_bounty` is never offered (R3). Not decided autonomously: scope change. | Producer, user | Before Vertical Slice stories |
| OQ-2 | **Schema — achievements table.** Proposed `data/achievements.csv` columns: `id, objective, target, requires, reward_gem, reward_gold, reward_items, content_wave, hidden`, with validator rules: objective in R3's set, `requires` exists and is acyclic, no `item_pa_eye`, lens total ≤ `achievement_lens_total_max`. Not created autonomously: schema change. Content (how many, which) also open. | User, Data layer (3) | Before Vertical Slice stories |
| OQ-3 | Main quest chain (§7 "Nhiệm vụ chính… có cốt truyện quay lại cố nhân"): content and story are Narrative's; R8 `requires` chains carry it. Is a chain wanted for Vertical Slice, or later? | Narrative, user | Alpha |
| OQ-4 | Quest gold is ~2% of a day-1 guild's income (F7), far below the 15% early target. Retune `reward_gold_*` with the balance simulator (S5), or accept that quests pay mainly in Linh Bảo and items? | Economy, Dev tooling (43) | Balance pass |
| OQ-5 | `defeat_backlog_boss` (`q_w_backlog_boss`) is completable only by being away > 1 h, and it gates the weekly lens from guild level 2 (R6). Keep it in the lens gate, exclude it like ad slots, or change it to "defeat any Golden Boss N times"? | Game design, user | Before Vertical Slice stories |
| OQ-6 | **RESOLVED (user decision 2026-11-16):** Linh Bảo is not sold for real money; its sinks are the Linh Bảo shop in Gold economy R16 (Chiêu Hiền Lệnh, enhancement wards, Scripture token, special items), priced against F6 by Gold economy F9 | Economy | Closed |
| OQ-7 | Seeding lifetime counters and high-waters from a migrated save (R13): which values can be reconstructed (guild level, member levels, rebirths yes; total kills no)? Local save R14 owns migration mechanics. | Local save (6) | When achievements ship |
| OQ-8 | **PROVISIONAL: Golden Boss (14)** — assumes 1406 `gb_backlog_resolved` carries a won/lost field (or is emitted in the same tick immediately before its 1403/1404 so the pairing is unambiguous), and that backlog events are emitted in the first live tick after a skip. | Golden Boss | Consistency check |
| OQ-9 | Ads (33) R9 calls "Quests' objective API"; this GDD names it `add_ad_progress(quest_uid)` with results ok / not_ad_quest / satisfied (R5). Ads' F3 note says ad slips carry about a quarter of quest gold; with today's data the two ad slips are 600 + 2,000/7 ≈ 886 of 3,821 gold/day at level 1 (23%). Accept, or lower? Also Ads OQ-3 (no-fill fallback grant) would change this system's rules and needs a decision here. | Ads, Economy | Consistency check |
| OQ-10 | **PROVISIONAL: Items and loot (26)** — assumes `give` of specials (`item_pa_lens`, `item_banner`) into guild storage cannot be refused for capacity; if it can, R11's all-or-nothing rule applies. Also: what happens to a reward item removed by a content patch mid-period. | Items and loot | Consistency check |
| OQ-11 | Proposed validator additions: `count_base ≥ 1`; objective in R3's closed set; `min_guild_lv` within 1–8; `q_w_all_done`-style rows must have `ad_variant = false`. | Dev tooling (43) | With S-module for quests |
| OQ-12 | Reset time: `quest_reset_utc_s` = 00:00 UTC+7 suits the Vietnamese launch audience; is one global reset acceptable for later regions (iOS, Steam, §12), or is a per-region reset wanted (which would need region in the save)? | Producer, user | Before Alpha |
| OQ-13 | Entitlement R3 makes the snapshot a logged `set_entitlement` command; this GDD assumes `feature_on(ad_quest_direct_claim)` is readable by this system's appliers in P1 (Entitlement's Quests row says so). | Entitlement | Consistency check |
| OQ-15 | **Schema — trial rewards.** Entitlement R10 lets Quests grant Premium-feature trials (§11.5 "dùng thử có giới hạn"), but `quests.csv` has no column for them. Add a `reward_trial` column (feature uid, hours), or carry trials only in the achievements table (OQ-2)? Not decided autonomously: schema change. | User, Entitlement (32) | Before Vertical Slice stories |
| OQ-14 | Systems index row 25 lists no Market (29), Offline progress (31), Command layer (5), Items (26) or Local save (6); this GDD adds them. Market, Offline, XP, Rebirth, Enhancement and CA/PA GDDs do not yet name Quests as a consumer of the events used. | Consistency check | Next `/consistency-check` |
| PT-1 | Playtest: can players tell in under 3 s which slips they can finish now? | UX | First playtest |
| PT-2 | Playtest: do rewards feel worth the tap at current values (see OQ-4)? | Game design | First playtest |

**Post-design note (CD-GDD-ALIGN):** NOT ASSESSED — no `game-pillars.md`, `game-concept.md` or game brief exist. Checked informally against JX1 GDD §1 and this GDD's Player Fantasy: the rules deliver the "notice board at dawn" moment (R4, R7, R9), and §11.5's equality between Free and Premium for the free lens is enforced by rule (R6). Open risks to the fantasy: OQ-4 (gold rewards invisible) and OQ-5 (a slip that rewards absence).
