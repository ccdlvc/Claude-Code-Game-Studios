# Golden Boss and Guild Raid

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run, decisions in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet). Serves the guild loop of `JX1_Tycoon_GDD.md` §1 and the locked decision "Raid Boss Hoàng Kim — cả bang cùng đánh" (§2, §6.5, §6.13)
> **Mode**: Retrofit. The built behaviour is `simulate_raid()` and `form_parties()` in `sim/raid.py`; the fight loop itself is now specified by Combat (10). This GDD makes the raid's own rules (schedule, boss pick, who takes part, rewards, backlog, summons) the specification and marks every gap against the code.

## Summary

Every hour a Golden Boss appears and the whole guild drops what it is doing to fight it together. This system decides which boss comes (by guild level), who answers the call, how they are grouped, how big the boss gets for the number of fighters, and what everyone takes home: the boss's spoils go to guild storage for the bang chủ to hand out, and each fighter earns personal XP and gold by how much they contributed. Missed bosses while the player is away pile up (at most 3) and are fought on return; a Triệu Tập Lệnh (summon horn) calls one on demand.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` (scaled down: participant cap, gated on the P1 Android spike) · Key deps: `Combat, Deterministic RNG, Items and loot, Gold economy, XP curve, Zones and hunt, Party, Member state machine, Guild and buildings, Data layer`

## Overview

The Golden Boss and guild raid is a timed event inside the simulation core. It owns a wall-clock schedule (one slot every `golden_boss_interval_min` = 60 minutes, anchored as a deadline tick), a deterministic **boss pick** for each slot from `golden_bosses.csv` filtered by guild level and live wave, and the **raid lifecycle**: announce, recall hunters and gather, fight, apply the result, pay out. The fight itself is one call to Combat's resolver (`resolve`) with raid encounter values that this system owns: boss HP scaled by participant count (`hp_per_participant`, `raid_hp_mult`), three targets per boss attack, enrage every 60 seconds, a 300-second limit. Fighters keep their hunting parties; everyone else is grouped into temporary parties so each group has a buffer and a tank where the roster allows. A win sends the boss's loot table to guild storage through Items and loot, its gold to the guild fund, and personal XP and gold to every fighter by a **contribution share** built from damage dealt, healing done and damage taken, with a guaranteed minimum for the weakest. The player's levers are all indirect: who they recruited, how they balanced parties, who they excused from the raid, and when they spend a summon horn. Without this system the guild loop has no shared climax, guild storage has no epic source beyond zone bosses, and the bang chủ's "who deserves this sword" decision never comes up.

## Player Fantasy

**Chosen framing: "The war drum sounds and the whole sect rides out."** (anchors: §1 core loop, §6.5 "cả bang cùng đánh", §6.13 "bang chủ thấy rõ giá trị của đội hình cân bằng").

1. **The call (every hour).** A drum and a banner: *Boss Hoàng Kim — Thuỷ, cấp 50 — 2 phút nữa*. Parties across the map turn around mid-trip and stream home. The player sees the whole roster converge, the one moment the guild is visibly *one* thing rather than many small trips.
2. **The fight (half a minute to five minutes).** Tanks draw the boss, buffers glow, the boss's HP bar is huge because everyone came. The enrage clock is visible; a balanced guild finishes before the second or third enrage, a guild with no healer watches its DPS fall.
3. **The spoils (after).** A result card: win or loss, time, who died, and a contribution ranking with each member's dealt/healed/taken. Storage gains a stack of materials and, sometimes, an epic. The bang chủ now chooses who gets it (Items and loot R9a, designated award). This is the decision the raid exists to create.

*Rejected framing:* "boss rush / combat skill check" — the player has no input in fights (Combat Player Fantasy), so the fantasy must be preparation and reward, not execution.

**Reference games.** Evil Hunter Tycoon's Field Boss horn (the summon), and guild raids in idle MMOs (participation-scaled HP, contribution rankings). Differs: loot belongs to the guild, not to the top damage dealer.

## Detailed Design

### Core Rules

**R1 — The schedule.** The guild keeps one saved `next_slot_tick`. It is first set at guild creation to `creation_tick + ticks(golden_boss_interval_min × 60)` (Sim core F-ticks). A P5 `timers` handler (owner `golden_boss`, order 1400 — block convention; consistency-check 2026-11-16) fires a **slot** when `tick ≥ next_slot_tick`, then advances it by the interval using Sim core's anchored deadline rule (smallest `k ≥ 1` so the new due tick is in the future). Each slot increments the saved `slot_ordinal` (starts at 0, only this rule advances it). Pause does not stop the schedule (Sim core R9).

**R2 — Announcement.** `golden_boss_warning_s` (default 120 s) before a slot's due tick, the handler picks the slot's boss (R3) and emits `gb_announced` (1401) with boss, element, level and due tick. The pick is fixed from then on. The world view and push notifications (46) read it.

**R3 — Boss pick.** For slot `s`, the candidate list is every `golden_bosses.csv` row whose `wave` is live (Data layer `content_wave`) and whose `min_guild_lv` lies in `[g − golden_boss_tier_span + 1, g]`, where `g` = `guild_level` (Guild and buildings R9). If that list is empty (a guild level above every row's tier), use the rows with the highest live `min_guild_lv`. Order the list by row `uid`; pick one with `choice` from a generator derived in **domain 7** (`golden_boss_pick`) with key `[0, s]`. The boss's level, element and combat stats are those of its `monster_id` row in `monsters.csv`. Example with today's data: guild level 5, span 2 → candidates `gb_07`–`gb_10` (levels 70–100).

**R4 — Eligibility.** At the slot's due tick, a member is **eligible** when all hold:
1. They are in the guild and alive.
2. Member state machine (41) reports them in a state that may join a raid: `idle`, `resting`-complete, or `hunting` (recall, R5). Not `injured`, `dead`, `away`, `training`, or already `boss_raid`.
3. `level ≥ ceil(raid_min_level_ratio × boss_level)` (F2).
4. Their per-member `raid_opt_out` flag is false (set by the player with `set_raid_opt_out`, R12; GDD §6.13 "có thể tắt cho từng người").

A member in a trip's `Homebound`, `Selling` or `Resting` stage (Zones R11 edge) becomes eligible only if their trip closes before the gathering window ends (R5).

**R5 — Recall and gathering.** At the due tick the raid enters `Gathering`:
- Eligible idle members move to `boss_raid` at once (through Member state machine 41).
- For every hunting group with at least one eligible member, the raid sends a **recall** to Zones and hunt (11, R11). The trip ends at its next return check; the fight in progress completes (Combat: no interrupt); settlement is immediate; the members are handed back here and enter `boss_raid` if still eligible. Ineligible members of a recalled group (opted out, under-level) go home (Member state machine R8 routes them through a short `resting` of Hunt F7 length, then `idle`) — the trip is over for the whole group (Zones R11 is per group).
- Gathering ends at the first tick where every recalled group has arrived, or `raid_gather_max_s` (default 120 s) after the due tick, whichever is first. Members not arrived by then are dropped from this raid; their recall still lands and they go home (Member state machine R8 routes them through a short `resting` of Hunt F7 length, then `idle`). This bounds Combat OQ-8: a hunt fight longer than the window costs that group the raid, never stalls it.

**R6 — Participant cap (MVP).** If `raid_max_participants > 0` and more members gathered than the cap, keep the top `raid_max_participants` by level descending, ties by `member_id` ascending; the rest leave through `leave_raid(alive = true)` (`resting`, then `idle`, Member state machine R8). `0` means no cap (the full-game rule of §2). MVP ships with the cap set from the P1 spike's measurement (provisional 20, the size §18.2 was balanced at).

**R7 — Grouping.** The raid groups (Combat R3 `groups`) are, in this order:
1. Each existing party (Party 13) with at least one participant, ordered by `party_id` ascending, its participants in party slot order.
2. Temporary groups for the remaining participants, built by the reference rule of `form_parties()`: `t = ceil(m / 5)` groups for `m` leftover members; deal buffers round-robin, then tanks round-robin, then everyone else to the smallest group (ties: lowest index); move overflow beyond 5 to the smallest group. Members are taken in `member_id` order. [PROVISIONAL: Party 13 may replace this with its own temporary-party algorithm, §6.13 "cùng thuật toán 6.12".]

**R8 — The fight.** At the end of gathering, with `n` participants (`n ≥ 1`), the raid calls Combat `resolve(encounter, gen)` once with:

| Encounter field | Raid value |
|---|---|
| `groups` | R7 |
| `monster` | the picked boss's `monsters.csv` row |
| `hp_scale` | F1 `(1 + hp_per_participant × n) × raid_hp_mult` |
| `dmg_scale` | `raid_dmg_mult` |
| `attack_interval_base_s` | `raid_boss_interval_s` (1.5) |
| `targets_per_attack` | `raid_boss_targets` (3) |
| `enrage_every_s`, `enrage_atk` | `raid_enrage_every_s` (60), `raid_enrage_atk` (0.5) |
| `time_limit_s` | `raid_time_limit_s` (300) |
| `want_timeline` | always `false` in the simulation. The world view gets the raid's timeline from `raid_fight_timeline(raid_ordinal)`, a side-effect-free between-tick query that re-runs the saved fight inputs (R18) on copies with a fresh domain-6 generator from key `[raid_ordinal]` and `want_timeline = true`; timelines never enter saves, events or parity comparisons (consistency-check 2026-11-16, World view OQ-2) |

Every participant starts at full HP (as built: `m.hp = hp_max`). The generator comes from **domain 6** (`raid`) with key `[raid_ordinal]` (R11). The result is applied at Combat's deadline tick (F8 of Combat, `start + ceil(duration_s × tick_rate)`); until then the raid is `Fighting` and participants stay in `boss_raid`.

**R9 — Outcome and death.** At the deadline tick:
- `died` members are reported to Member state machine (41), which applies §6.4: sent to Linh Miếu to revive, and serious injury by its rules. A member who died keeps the contribution they made (§6.13).
- Survivors leave `boss_raid` through `leave_raid(alive = true)` with their `hp_after`: Member state machine R8 puts them in `resting` for Hunt F7 (from `hp_after`), then `idle` at full HP. *(consistency-check 2026-11-16: aligned to the state owner; was "to `idle`".)*
- Emit `gb_won` (1403) or `gb_lost` (1404) with boss, `n`, `duration_s`, deaths, and the top three contributors.

**R10 — Rewards.** Computed from the `FightResult` after R9:
- **Guild loot (win only).** Call Items and loot `roll_guild_loot(raid_ordinal, loot_table, boss_level)` (Items R9a). Items and materials land in storage. The returned table gold is credited by this system to the guild fund as `boss_reward` (Gold economy R3, type 4). A loss drops nothing.
- **Personal rewards (win and loss).** Each participant `i` gets XP `xp_i` (F4) through XP curve `award(ctx, member_id, xp_i, source=raid)` and gold `gold_i` (F5) through `credit(boss_reward, wallet_i, gold_i, raid_uid)`. On a loss both are scaled by `raid_loss_reward_frac`. Contribution share is F3.
- In MVP, distribution of storage loot is the Items and loot designated award only. From Vertical Slice, Market (29) may list storage items for members to buy (Chợ Bang, §6.5); this system is unchanged by it.

**R11 — Keys and ordinals.** Saved counters: `slot_ordinal` (R1) and `summon_ordinal` (R13). A raid's `raid_ordinal` is `2 × slot_ordinal` for an hourly slot and `2 × summon_ordinal + 1` for a summon. It is unique per raid, never reused, and advanced only by the event itself, so a summon cannot shift the dice of an hourly raid (RNG R5, R6). Keys: boss pick domain 7 `[0, slot_ordinal]` or `[1, summon_ordinal]`; fight domain 6 `[raid_ordinal]`; loot domain 2 `[0, 1, raid_ordinal]` (Items R3).

**R12 — Commands.** Registered with the Command layer (5):
- `set_raid_opt_out(member_id, bool)` — host or UI. Refused for an unknown member. Takes effect at the next eligibility check; a member already in a raid stays in it.
- `use_summon_token()` — §6.5 Triệu Tập Lệnh (R13).

**R13 — Summon horn.** `use_summon_token` is refused `not_allowed_now` while any raid is in `Gathering` or `Fighting`, and refused if storage holds no `item_summon_horn`. Otherwise it takes one horn from storage (Items `take`), increments `summon_ordinal`, picks a boss with domain-7 key `[1, summon_ordinal]` by R3, and starts the raid immediately at `Gathering` (no announcement; it recalls hunters exactly as R5 — answers Zones OQ-9). It does not move `next_slot_tick`. Emit `gb_summoned` (1407).

**R14 — Collisions.** If a slot comes due while a raid is in progress, the slot is **queued** (saved `queued_slots`, capped at `golden_boss_backlog_max`) and starts at `Gathering` on the tick after the current raid's deadline. Its boss was picked at announcement as usual.

**R15 — No one comes.** If gathering ends with `n = 0`, the raid is `Skipped`: no fight, no rewards, emit `gb_skipped` (1405). The slot's `raid_ordinal` is consumed.

**R16 — Offline backlog.** When Offline progress (31) resolves a gap, it asks this system for the slots the gap crossed (Sim core R5: Offline re-anchors them). Let `K` be their count. Only the **last** `min(K, golden_boss_backlog_max)` slots are kept as a backlog; earlier ones are lost (§6.5, S7 acceptance: at most 3). On return, each backlog slot is resolved in slot order, after Offline has applied the hunt aggregate, by the same R3–R10 with these differences: no announcement, no recall, no gathering wait — participants are the members eligible (R4) at the moment of resolution, capped by R6 (a member on a live trip that Offline paused, Offline R5, counts as home for R4 condition 2 whatever the trip's stage; the trip is not closed, recalled or changed by the backlog raid — consistency-check 2026-11-16); each fight is applied immediately (no deadline wait); the result screen (39) lists them in the "while you were away" report. Each emits `gb_backlog_resolved` (1406) in addition to `gb_won`/`gb_lost`. (Decision: exact resolve on the roster snapshot instead of a separate statistical model; at most three raids is cheap and keeps one code path.)

**R17 — Events.** Type block **1400–1499**. 1401 `gb_announced`, 1402 `gb_started` (fight begins, `n`, groups), 1403 `gb_won`, 1404 `gb_lost`, 1405 `gb_skipped`, 1406 `gb_backlog_resolved`, 1407 `gb_summoned`, 1408 `gb_member_rewarded` (per participant: share, XP, gold). Typical peak: one tick emits 1402 plus one 1104 recall-settlement per recalled group (Zones); the result tick emits 1403/1404 plus `n` × 1408 plus Items' 2602 per epic. Ring budget: 1401–1407 at ≈ 24/day each; 1408 at `24 × n`/day (≤ 960 at 40 members) — 1408 is **not** kept in the history ring (delivery only); 1403 and the first-kill of each `gb_*` id are milestones for the Chronicle (42).

**R18 — Save.** Saved state: `next_slot_tick`, `slot_ordinal`, `summon_ordinal`, `queued_slots`, `backlog` (list of slot ordinals awaiting resolution), per-member `raid_opt_out`, and the current raid record (phase, `raid_ordinal`, boss id, gathering deadline, participant list, fight start tick, deadline tick). Because the fight is atomic and its key and inputs are saved, a raid saved in `Fighting` recomputes the same result on load (Combat edge case). Registered with Local save (6) under its `schema_version`.

### States and Transitions

| State | Enters when | Exits to | Exit condition |
|---|---|---|---|
| `Idle` | no raid in progress | `Announced`; `Gathering` (summon, queued slot) | `tick ≥ next_slot_tick − warning`; R13; R14 |
| `Announced` | R2 | `Gathering` | `tick ≥ due tick` |
| `Gathering` | R5 | `Fighting`; `Skipped` | all recalled arrived or window over; `n = 0` |
| `Fighting` | R8 | `Resolved` | deadline tick reached |
| `Resolved` | R9, R10 applied | `Idle` (or `Gathering` if a slot is queued) | same tick |
| `Skipped` | R15 | `Idle` | same tick |

Member side (owned by Member state machine 41): `idle`/`hunting` → `boss_raid` → `idle` | `dead` (→ Linh Miếu) | `injured`.

### Interactions with Other Systems

| System | Direction | Data | Owner of the interface |
|---|---|---|---|
| Sim core (1) | in | P5 handler; anchored due ticks; `ticks()`; `ctx.derive`, `ctx.emit` | Sim core R4, R5 |
| Deterministic RNG (2) | in | Domains 6 (fight) and 7 (pick); keys R11 | RNG R4–R6; this GDD owns the keys |
| Data layer (3) | in | `golden_bosses`, `monsters`, `sim_params` (raid_*), `config` (golden_boss_*, raid_min_level_ratio), `content_wave` | Data layer R4 |
| Command layer (5) | in | `set_raid_opt_out`, `use_summon_token` | This system registers them |
| Local save (6) | out | R18 state | Local save registers serializers |
| Member model (8) | in | Roster, level, `profile` (via Combat) | Member model |
| Combat (10) | out | `resolve` with R8 values; reads `dealt`, `healed`, `taken`, `died`, `hp_after`, `duration_s` | Combat owns `resolve`; this GDD owns the raid values |
| Zones and hunt (11) | out / in | Recall request; settled group returned | Zones R11 |
| Party (13) | in | Existing parties and slot order; temporary-party algorithm | Party |
| Items and loot (26) | out | `roll_guild_loot`; `take(item_summon_horn)` | Items R9, R9a |
| Gold economy (27) | out | `credit(boss_reward, fund | wallet, …)` | Gold economy R3 |
| XP curve (22) | out | `award(ctx, member, base_milli, raid)` | XP curve R4 |
| Kill XP / base gold tables | in | `kill_xp_milli[L]` (Zones F1), `base_gold_milli[L]` (Items F1) | Their owners |
| Guild and buildings (30) | in | `guild_level`; `member_cap` (bounds `n`) | Guild and buildings R9, F2 |
| Member state machine (41) | out / in | Enter/leave `boss_raid`; death and injury; "may join a raid?" | 41 |
| Offline progress (31) | in | Crossed slots; backlog resolution call | Offline owns the gap; this system owns R16 |
| Event bus (42) | out | Block 1400–1499 | Event bus R2 |
| World view (38), Guild screens (39), Push (46), Quests (25), Analytics (37) | out | Events and the raid record (read-only) | Consumers |
| Market (29, Vertical Slice) | none directly | Lists storage items; no call from here | Market |

## Formulas

### F1 — Raid boss HP scale

`hp_scale = (1 + hp_per_participant × n) × raid_hp_mult`; boss max HP = Combat F1 `monster_hp(L, hp_mult) × hp_scale`

| Variable | Type | Range | Source | Description |
|---|---|---|---|---|
| n | int | 1 – `member_cap` (12–40) | calculated (R5, R6) | Participants at fight start |
| hp_per_participant | float | 0.0 – 0.5 (0.10 all rows) | `golden_bosses.csv` | HP added per participant |
| raid_hp_mult | float | 1 – 20 (6) | `sim_params.csv` | Global raid HP multiplier |

**Output Range:** 6.6 (n 1) to 30 (n 40) with today's data. **Example:** `gb_05` (L 50, `hp_mult` 12), n 20 → `hp_scale = 3 × 6 = 18`; boss HP ≈ `40 × 50^1.3 × 12 × 18 ≈ 1.40 M`. §18.2: with 20 fighters the win/loss wall sits at members ≈ 80–90 % of boss level.

### F2 — Minimum level

`min_level = ceil(raid_min_level_ratio × boss_level)`

| Variable | Type | Range | Source | Description |
|---|---|---|---|---|
| raid_min_level_ratio | float | 0 – 1 (0.5) | `config.csv` | Fraction of boss level required |
| boss_level | int | 10 – 200 | `monsters.csv` | Picked boss's level |

**Output Range:** 5 (L 10) to 100 (L 200). **Example:** L 50 → 25. Note: Schools edge cases read this ratio as "half the guild's level"; the guild level is 1–8, so this GDD applies it to the boss level (OQ-3).

### F3 — Contribution share

For each component `k ∈ {dealt, healed, taken}` with total `X_k = Σ_i x_{i,k}` over participants:

`share_i = Σ_{k : X_k > 0} w_k × x_{i,k} / X_k  ÷  Σ_{k : X_k > 0} w_k`

| Variable | Type | Range | Source | Description |
|---|---|---|---|---|
| x_{i,dealt}, x_{i,healed}, x_{i,taken} | float | ≥ 0 | Combat `FightResult` | Member's damage dealt, HP healed, damage taken (capped at HP) |
| w_dealt, w_healed, w_taken | float | 0 – 1 (0.6, 0.2, 0.2) | `config.csv` (new keys, OQ-1) | Weight of each pot |

**Output Range:** each `share_i ∈ [0, 1]`; `Σ share_i = 1` (whenever any pot is non-zero; a fight with no damage, healing or hits cannot occur with `n ≥ 1`, since members act first). Computed in binary64 in participant order, then used only through the floors in F4/F5. Pots with no entries (no healer present) drop out and the others are renormalised, so a guild without healers does not lose 20 % of its rewards. Crowd-control contribution (§6.13 "hỗ trợ khống chế") joins as a fourth pot when Skills (21) adds control effects (OQ-4). **Example:** a tank with 5 % of damage, 0 heals and 30 % of damage taken, healers present: `0.6×0.05 + 0.2×0 + 0.2×0.30 = 0.09`.

### F4 — Personal raid XP

`xp_i = floor( kill_xp_milli[L] × raid_xp_mult × (raid_min_reward_frac + (1 − raid_min_reward_frac) × n × share_i) × outcome )`, `outcome = 1` on a win, `raid_loss_reward_frac` on a loss.

| Variable | Type | Range | Source | Description |
|---|---|---|---|---|
| kill_xp_milli[L] | int | 1,500 – 4,242,640 | Zones F1 boot table | Kill XP of a level-L monster, milli-XP |
| raid_xp_mult | float | 1 – 100 (20) | `config.csv` (new, OQ-1) | A raid is worth this many boss-level kills per participant on average |
| raid_min_reward_frac | float | 0 – 1 (0.3) | `config.csv` (new) | Guaranteed fraction for any participant (§6.13 "phần tối thiểu") |
| raid_loss_reward_frac | float | 0 – 1 (0.25) | `config.csv` (new) | Rewards kept on a loss |
| n, share_i | — | F1, F3 | calculated | |

**Output Range:** the average participant gets exactly `kill_xp_milli[L] × raid_xp_mult` (shares sum to 1); minimum `0.3×` that; the theoretical maximum (one member with share 1) is `(0.3 + 0.7 n)×`. Passed to XP curve `award`, which applies rebirth growth (XP curve F2) and its 2⁴⁰ limit (never approached: 4.24 M × 20 × 28 ≈ 2.4 × 10⁹). **Example:** L 50 (`kill_xp_milli` 530,330), n 20, share 0.10, win → `530,330 × 20 × 1.7 = 18,031,220` milli-XP; share 0 → 3,181,980.

### F5 — Personal raid gold

`gold_i = floor( base_gold_milli[L] × raid_gold_mult × (raid_min_reward_frac + (1 − raid_min_reward_frac) × n × share_i) × outcome / 1000 )` whole gold to the member's wallet.

| Variable | Type | Range | Source | Description |
|---|---|---|---|---|
| base_gold_milli[L] | int | 2,000 – 679,459 | Items F1 | Base gold at level L |
| raid_gold_mult | float | 0 – 50 (5) | `config.csv` (new, OQ-1) | Average personal gold in base-gold units |

**Output Range:** 0 – about `679 × 5 × 28 ≈ 95,000` gold for one extreme member at L 200, n 40; average participant 10 (L 1) to 3,397 (L 200). **Example:** L 50 (`147,876`), share 0.10, n 20, win → `floor(147,876 × 5 × 1.7 / 1000) = 1,256` gold. These mint into wallets (Gold economy `boss_reward`, taxable under R6 when tax is live) and are part of the faucet §19.5 must balance (OQ-5).

## Edge Cases

- **If no boss row is live for the guild level band**: R3 falls back to the highest live tier; if no row is live at all (corrupt content), a content error at validation (Data layer R8), never at runtime.
- **If the guild has one eligible member**: the raid runs with `n = 1` (`hp_scale` 6.6). It is usually lost and the member gets `raid_loss_reward_frac × (0.3 + 0.7) = 0.25` of the average reward. Accepted; a tiny guild is not barred from the event.
- **If every member is opted out or under-level**: `Skipped` (R15). The player sees "Không ai tham chiến" in the result card.
- **If a recalled group's hunt fight is long** (up to Combat's 600 s limit): it misses the raid after 120 s (R5); its members go home through a short rest, then `idle` (Member state machine R8), not back to hunting (the trip already ended).
- **If a member is injured or dies on a hunt during gathering**: they arrive injured/dead and are no longer eligible (R4 is re-checked on arrival).
- **If the player opts a member out during `Gathering`**: applies on arrival if they have not yet entered `boss_raid`; otherwise next raid.
- **If the player uses a summon horn right before an hourly slot**: the hourly slot queues (R14) and runs after. Both raids pay out. Two raids in quick succession are bounded by horn supply (3 % per Golden Boss win today).
- **If guild level changes between announcement and due tick**: the announced boss stands (pick is fixed at R2).
- **If content changes the wave between announcement and resolution** (update installed mid-raid): the save holds the boss id; if the row no longer exists, Local save migration (6) cancels the raid as `Skipped`.
- **If offline crosses 24 slots**: only the last 3 become backlog (R16); the other 21 are lost with no reward. The "while you were away" report says how many were missed.
- **If backlog resolution finds members still on offline-sampled trips**: Offline progress (31) has already closed all trips at the end of the gap before R16 runs (PROVISIONAL on 31), so the whole roster is home.
- **If a raid is saved in `Fighting` and loaded**: recomputed identically from the saved key and inputs (R18). Participants' stats are re-read at load; Combat R4 snapshots at fight start, so the save must hold the participant list and the fight's start tick, and equipment cannot change while in `boss_raid` (Member model R6).
- **Save-scumming a raid**: reload gives identical dice (keys R11 contain no player-mutable state). Changing parties or opt-outs before gathering changes inputs, not dice. Accepted (RNG edge cases).
- **Degenerate strategy — carry low-level members for XP**: a member at exactly 50 % of boss level who contributes nothing still earns `0.3 × kill_xp_milli[L] × 20`, i.e. six boss-level kills an hour. This is the §6.13 "minimum share" intent; the simulator must confirm it does not outpace hunting at that level (OQ-5). The level floor F2 is the main guard.
- **Degenerate strategy — opt everyone weak out to shrink boss HP**: HP scales with `n`, so fewer, stronger fighters face a smaller boss; with `hp_per_participant` 0.10 and `raid_hp_mult` 6, each extra member adds ≈ 3 % HP at n 20 but more damage than that if their dps exceeds 3 % of the raid's. Reward pools scale with `n` too, so excluding members lowers total guild reward. No dominant choice expected; verify with the simulator.
- **If `n` exceeds 40** (future member cap): F1 stays linear; Sim core's event cap must still cover the result tick (R17, ≤ 2 + n + epics events).

## Dependencies

| System | Kind | What this system needs | Status |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | P5 handler, anchored due ticks, `ctx` | Designed (In Review) |
| Deterministic RNG (2) | Hard | Domains 6, 7 | Designed (Needs Revision) |
| Data layer (3) | Hard | `golden_bosses`, `monsters`, `sim_params`, `config` | Designed |
| Command layer (5) | Hard | Two commands | Designed |
| Local save (6) | Hard | Serializer registration | Designed |
| Member model (8) | Hard | Roster, level | Designed |
| Combat (10) | Hard | `resolve` with raid values, `healed`/`taken` | Designed |
| Zones and hunt (11) | Hard | Recall (R11) | Designed |
| Party (13) | Soft | Existing parties; temp-party algorithm | Not designed — PROVISIONAL |
| XP curve (22) | Hard | `award` | Designed |
| Items and loot (26) | Hard | `roll_guild_loot`, `take`, `base_gold_milli` | Designed |
| Gold economy (27) | Hard | `credit(boss_reward)` | Designed |
| Guild and buildings (30) | Hard | `guild_level`, `member_cap` | Designed |
| Member state machine (41) | Hard | `boss_raid` state; death/injury; eligibility | Not designed — PROVISIONAL |
| Offline progress (31) | Hard (both ways) | Crossed slots; calls R16 | Not designed — PROVISIONAL |
| Event bus (42) | Hard | Block 1400–1499 | Designed (Needs Revision) |
| Market and trade orders (29) | Soft (Vertical Slice) | Lists storage items | Not designed; MVP uses designated award only |

**Depended on by**: Offline progress (31), Quests and achievements (25), Realtime world view (38), Guild screens (39), Local push notifications (46), Analytics (37), Dev tooling (43, raid vectors and balance scenarios). The systems index row listed Market and Party as dependencies; this GDD adds Sim core, Command layer, Member model, Zones and hunt, XP curve, Gold economy, Member state machine, Offline progress and Event bus, which the rules above require.

## Tuning Knobs

`systems-designer` and `economy-designer` lenses applied.

| Knob | Today | Safe range | Too high | Too low | Lives in |
|---|---|---|---|---|---|
| `golden_boss_interval_min` | 60 | 30 – 240 | Raids rare, players forget them | Raids dominate time; recall constantly breaks trips | `config.csv` |
| `golden_boss_backlog_max` | 3 | 0 – 6 | Offline raids out-earn play | Long absence loses all raids | `config.csv` |
| `golden_boss_warning_s` | 120 | 0 – 600 | — | No time to see the call | new `config.csv` key (OQ-1) |
| `golden_boss_tier_span` | 2 | 1 – 4 | Easy low-tier bosses keep appearing | Every raid is the hardest boss | new key |
| `raid_gather_max_s` | 120 | 30 – 600 | Raids start late | Far parties always miss | new key |
| `raid_max_participants` | 20 (MVP), 0 (full) | 0, 10 – 40 | Phone frame drops (§6.13) | Large guilds bench members | new key; P1 spike |
| `raid_min_level_ratio` | 0.5 | 0.3 – 0.8 | Small raids, boss lost | Power-levelling carry | `config.csv` |
| `hp_per_participant` | 0.10 | 0.0 – 0.3 | Extra members hurt | Big guilds trivialise | `golden_bosses.csv` |
| `raid_hp_mult` | 6 | 3 – 12 | Unwinnable (§18.2 early bosses already "hơi khó") | Trivial | `sim_params.csv` |
| `raid_dmg_mult`, `raid_boss_targets`, `raid_boss_interval_s`, `raid_enrage_*`, `raid_time_limit_s` | 1, 3, 1.5, 60/0.5, 300 | see Combat Tuning Knobs | | | `sim_params.csv` (values owned here, operators in Combat) |
| `w_dealt` / `w_healed` / `w_taken` | 0.6 / 0.2 / 0.2 | each 0 – 1 | DPS-only ranking (dealt) | Tanks out-earn DPS (taken) | new keys |
| `raid_xp_mult` | 20 | 5 – 50 | Raid XP outpaces hunting | Raid not worth the recall | new key |
| `raid_gold_mult` | 5 | 0 – 20 | Inflation (§19.5) | — | new key |
| `raid_min_reward_frac` | 0.3 | 0 – 0.6 | Contribution stops mattering | Weak members earn nothing | new key |
| `raid_loss_reward_frac` | 0.25 | 0 – 0.5 | Losing is fine | Losses feel like wasted hours | new key |

**Interactions:** `raid_hp_mult` × `hp_per_participant` set the win wall; `raid_xp_mult` and `raid_min_reward_frac` set how much raids pace levelling versus hunting (XP curve OQ-6 recalibration must include raids); `raid_gold_mult` joins `golden_boss_interval_min` in the gold faucet.

## Visual/Audio Requirements

No art bible exists; drafted from §3.5, §6.13, §12.4. `art-director` lens applied.

1. **The call** is unmistakable: a drum cue, a banner with the boss's element glyph and level, and a countdown (from 1401). Parties visibly turn home.
2. **The arena** shows full sprites for at most `raid_full_sprites` (≤ 15, §6.13) around the camera; other groups render as group tokens with a shared HP bar. Damage numbers pooled and capped (Combat V/A 4).
3. **Boss presence:** a large sprite, its element palette, the giant HP bar, and an enrage meter that ticks each 60 s.
4. **Result card:** win/loss stamp, time, deaths, ranking with role icons, storage gains with epics highlighted (Items' 2602).
5. **Audio:** drum call, boss roar on start, enrage sting, victory and defeat themes. Highest mix priority after critical UI. Detailed by Audio (40).

📌 **Asset Spec** — after the art bible is approved, run `/asset-spec system:golden-boss-and-guild-raid`.

## Game Feel

- **Rhythm:** a beat every hour, short and dramatic; the raid itself 30 s – 5 min.
- **Anticipation over input:** the warning window (120 s) is for the player to look, opt members out, or ready a summon, not to act in the fight.
- **Trust:** the playback is the computed fight (Combat timeline); rankings add up to 100 %.
- **Generosity:** no one leaves with nothing; losses still pay a quarter.
- Verified by playtest and screenshots in `production/qa/evidence/`, not automation.

## UI Requirements

- **HUD banner/countdown** for an announced boss (element, level, time) and a "Đang tập hợp N/M" gathering counter.
- **Roster column**: a raid opt-out toggle per member (sends `set_raid_opt_out`), with level-eligibility shown against the next boss.
- **Summon button** in storage when a horn is held, disabled with a reason while a raid runs.
- **Result card** (R9, R10) and a "while you were away" section for backlog raids (R16).
- All strings through Localization (4).

**📌 UX Flag — Golden Boss and guild raid**: run `/ux-design` for the raid banner, result card and opt-out control before writing epics.

## Cross-References

| This GDD uses | From | Section / rule | Kind |
|---|---|---|---|
| Raid encounter fields, `resolve`, `healed`/`taken`, deadline tick | `combat.md` | R3, R14, F8 | Rule dependency |
| Domains 6, 7; key rules | `deterministic-rng.md` | R4–R6 | Rule dependency |
| P5 timers, anchored due ticks, pause | `sim-core-and-tick-loop.md` | Phases, R5, R9 | Rule dependency |
| Recall, immediate settlement; `kill_xp_milli` | `zones-grounds-monsters-and-hunt-trips.md` | R11, F1 | Rule / data dependency |
| `roll_guild_loot`, storage, summon horn, `base_gold_milli` | `items-and-loot-tables.md` | R9, R9a, F1 | Rule / data dependency |
| `boss_reward` mint | `gold-economy.md` | R3, R6 | Rule dependency |
| `award` | `xp-and-level-pacing-curve.md` | R4 | Rule dependency |
| `guild_level`, `member_cap` | `guild-and-buildings.md` | R9, F2 | Data dependency |
| `use_summon_token` vocabulary row | `command-layer.md` | Vocabulary table | Interface |
| Design intent | `JX1_Tycoon_GDD.md` | §6.5, §6.12, §6.13, §10, §18.2, §20 S7 | Source |
| Reference code | `sim/raid.py` | `simulate_raid`, `form_parties` | Retrofit baseline |

## Acceptance Criteria

`qa-lead` lens applied. All **Logic** (automated, Python reference first, then the port through parity vectors) unless marked.

**Schedule and pick**
- **AC-1 (R1)**: **GIVEN** a new guild at tick 0, **WHEN** 3 hours of ticks run, **THEN** exactly 3 slots fire at ticks 36,000, 72,000, 108,000 and `slot_ordinal` = 3. **GIVEN** a pause of 10 minutes, **THEN** the due ticks are unchanged.
- **AC-2 (R2)**: **GIVEN** a slot, **THEN** `gb_announced` is emitted `golden_boss_warning_s × tick_rate` ticks before its due tick, and the boss it names is the one fought.
- **AC-3 (R3)**: **GIVEN** guild level 5, span 2 and today's data, **WHEN** 10,000 slots are picked, **THEN** only `gb_07`–`gb_10` appear, each 25 % ± 1.5 %. **GIVEN** the same seed and slot ordinal, **THEN** the pick repeats.
- **AC-4 (R3)**: **GIVEN** a Wave-1-only build and guild level 8, **THEN** the pick falls back to `gb_11` (the highest live tier).

**Eligibility, gathering, grouping**
- **AC-5 (R4, F2)**: **GIVEN** a level-50 boss and members at levels 24, 25, 60 (one opted out), one `injured`, **THEN** only the level-25 and the non-opted level-60 member are eligible.
- **AC-6 (R5)**: **GIVEN** two hunting groups, one whose fight ends 30 s after the due tick and one at 150 s, **THEN** the raid starts at the first group's arrival + no later than 120 s, the second group's members end `resting` (then `idle` when Hunt F7 elapses), not in the raid, and their trip is closed.
- **AC-7 (R6)**: **GIVEN** 30 gathered members and cap 20, **THEN** the 20 highest-level (ties by id) fight; the rest are `idle`.
- **AC-8 (R7)**: **GIVEN** two existing parties (ids 4, 2) and 7 unpartied members including 2 buffers and 1 tank, **THEN** groups are party 2, party 4, then two temporary groups each with one buffer, the tank in the first, sizes 4 and 3.

**Fight and rewards**
- **AC-9 (R8, retrofit parity)**: **GIVEN** a 20-member guild with no existing parties, **WHEN** the raid runs, **THEN** `won`, `duration_s` and deaths equal `sim/raid.py simulate_raid` on the same members, boss and generator (no-party case is where R7 equals `form_parties`).
- **AC-10 (F1)**: **GIVEN** `gb_05`, n 20, **THEN** `hp_scale = 18.0` exactly.
- **AC-11 (F3)**: **GIVEN** any raid result, **THEN** `Σ share_i = 1 ± 1e-12`; **GIVEN** no healer, **THEN** the healed pot is dropped and weights renormalise to 0.75 / 0.25.
- **AC-12 (F4, F5)**: **GIVEN** the F4 and F5 examples, **THEN** the XP passed to `award` is 18,031,220 milli and the gold credited is 1,256; a share-0 participant gets 3,181,980 milli-XP; on a loss each is ×0.25 before the floor.
- **AC-13 (R10)**: **GIVEN** a won raid, **THEN** `roll_guild_loot` is called once with `raid_ordinal`, its gold is credited to the fund as `boss_reward`, and every participant gets exactly one `award` and one `credit(boss_reward, wallet)`. **GIVEN** a lost raid, **THEN** no loot call is made.
- **AC-14 (R9)**: **GIVEN** a member who dies at 40 s having dealt 5 % of damage, **THEN** their share is > 0, they are reported to 41 as dead, and they get the reward of their share.
- **AC-15 (R15)**: **GIVEN** all members opted out, **THEN** `gb_skipped` is emitted, no `resolve`, no rewards, and `slot_ordinal` still advances.

**Keys, summons, collisions, offline, save**
- **AC-16 (R11)**: **GIVEN** a horn used between slots 4 and 5, **WHEN** compared with a run without the horn, **THEN** slot 5's boss, fight and loot are bit-identical.
- **AC-17 (R13)**: **GIVEN** storage with no horn, **THEN** `use_summon_token` is refused; **GIVEN** one horn and a raid in `Fighting`, **THEN** refused `not_allowed_now` and the horn stays.
- **AC-18 (R14)**: **GIVEN** a summon raid that is `Fighting` when a slot comes due, **THEN** the slot starts at `Gathering` on the tick after the summon's deadline.
- **AC-19 (R16, §20 S7)**: **GIVEN** a 24 h offline gap, **THEN** 24 slots are crossed and exactly 3 backlog raids resolve, for the last three crossed slot ordinals in order, each emitting 1406; `slot_ordinal` advances by 24.
- **AC-20 (R18)**: **GIVEN** a save taken in `Fighting`, **WHEN** loaded and run to the deadline, **THEN** the result equals the uninterrupted run.
- **AC-21 (R17)**: the raid emits only types in 1400–1499 (plus owners' events it triggers), and the result tick with n 40 stays under Sim core's `event_buffer_hard_cap`.
- **AC-22 (RNG R5)**: no key component in R11 is player-mutable (code review + AC-16).

**Performance and visual**
- **AC-23 [Performance]**: **GIVEN** 40 participants at L 200 vs `gb_15`, **WHEN** `resolve` runs, **THEN** it completes within the P3/P5 budget share Sim core F6 assigns (to be measured in the P1 spike on the reference Android device).
- **AC-24 [UI] [PENDING: Guild screens 39, World view 38]**: a retained screenshot in `production/qa/evidence/` of the announcement banner, the gathering counter and the result card.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | Add new config keys (`golden_boss_warning_s`, `golden_boss_tier_span`, `raid_gather_max_s`, `raid_max_participants`, `w_dealt`/`w_healed`/`w_taken`, `raid_xp_mult`, `raid_gold_mult`, `raid_min_reward_frac`, `raid_loss_reward_frac`) to `data/config.csv` with validator ranges. Not done in this pass (data change). | user / Data layer (3) | Before implementation |
| OQ-2 | Retrofit gaps in `sim/raid.py`: existing parties are re-split (R7), no eligibility/min level/cap (R4, R6), no rewards (R10), shared generator instead of domain 6 key (R11), no `healed`/`taken` (Combat R14), no schedule, backlog or summon (§20 S7 `sim/world.py`). | Implementation story | S7 |
| OQ-3 | **RESOLVED (consistency-check 2026-11-16):** Schools' edge case now reads boss level, matching F2. | Schools (20) owner | Closed |
| OQ-4 | Crowd-control contribution pot (§6.13) once Skills (21) adds control effects and Combat reports them. | Skills (21), Combat (10) | S4 |
| OQ-5 | Balance: raid XP/gold versus hunting at each level band and the §19.5 faucet target; "early Golden Bosses a bit hard" (§18.2, §20 note 3) — tune `raid_hp_mult` or `golden_boss_tier_span`. | Dev tooling (43), balance sim | After S3–S5 |
| OQ-6 | Should the boss's monster `ai_skills` / `golden_bosses.mechanics` (enrage_30pct, summon_adds, …) be executed? Today they are data only (Combat OQ-4). | Combat (10), Skills (21) | S4 |
| OQ-7 | MVP participant cap value from the P1 Android spike (§12.1). | technical-director | P1 spike |
| PROVISIONAL-1 | **Party (13)** — exposes existing parties with stable `party_id` and slot order; may supply its own temp-party algorithm in place of R7 step 2. | Party (13) | When 13 is designed |
| PROVISIONAL-2 | **Member state machine (41)** — has `boss_raid`; answers "may join a raid?" (R4); applies death → Linh Miếu and injury after a raid; forbids equip changes in `boss_raid`. | 41 | When 41 is designed |
| PROVISIONAL-3 | **RESOLVED (consistency-check 2026-11-16):** Offline progress R10 reports the slots in the credited window and calls R16 once after its last slice, using this system's exact resolver. It does **not** close trips first: live trips are paused (Offline R5), and R16 now counts their members as home for eligibility without touching the trip. | 31 | Closed |
| PROVISIONAL-4 | **Market (29)** — Vertical Slice listing of storage loot; no interface from this system. | 29 | Vertical Slice |
| PROVISIONAL-5 | **Zones and hunt (11)** — recall of a group in `Homebound`/`Selling`/`Resting` is not sent; those members join only if their trip closes inside the gathering window (answers Zones' PROVISIONAL edge). | Zones (11) | Consistency pass |
