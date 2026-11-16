# Jianghu Free Agents and NPC Guilds

> **Status**: Designed (pending `/design-review` in a fresh session)
> **Author**: user + agents (`/design-system`, autonomous batch run; decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: none written (no `game-pillars.md`); anchored on JX1_Tycoon_GDD.md §6.11, §2 ("Bang NPC mô phỏng cục bộ trước"), §20 S2/S7
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, `game-concept.md` or `game-brief.md` exist to check against (systems index CD-SYSTEMS note: "no game pillars exist")

## Summary

Jianghu is the world outside the player's guild: 8–12 coarse-simulated NPC guilds that grow every day, and the free-agent list where members who left (and the best rejected recruits) wait for a few days before an NPC guild signs them, the player invites them back, or they drift away. Some who drift away come back weeks later as "cố nhân" (old friends) on a seeded story timer. It exists so that losing a member has a consequence you can see (they may face you at the Lôi Đài), so a departure is not always final, and so the Arena (18) has rivals whose strength follows the player's own guild.

> **Quick reference** — Layer: `Feature` · Priority: `Full Vision` · Key deps: `Deterministic RNG, Retention (16), Member model (8), CA/PA and traits (9), Gold economy (27), Guild and buildings (30), Recruitment (15), Sim core (1), Event bus (42), Command layer (5), Offline progress (31), Local save (6), Data layer (3)`

## Overview

Jianghu is a rules module in the headless simulation, live from content wave 2 (with the Arena). It owns two collections and nothing else. **NPC guilds**: each has a level 1–8, a fame number, a `power` (the CA of its representative fighters) and up to five signed free agents; once per game day each guild's power moves part of the way toward a target set by the player's own top members (multiplied by that guild's fixed strength), plus a small seeded noise, and never goes down. A guild's **lineup** (five fighters) is a formula over its power and its signed agents, which is what the Arena fights (GDD §6.11 "đội hình đại diện, snapshot tính bằng công thức"). **The free-agent list** (Danh sách Giang Hồ): every member Retention (16) lets go arrives here with their full record and their `return_chance` (Retention F9), and so does the best unhired candidate of each closed recruitment offer. A listed agent stays `fa_stay_days` (7) days. Each day after the first, an NPC guild may sign them (a seeded chance that rises with their CA and with time listed); the player may instead **invite** them back once a day with a salary offer, paying a day's wage up front, at a chance that depends on how they left and what is offered. An agent no one signs leaves the list; an ex-member then gets one seeded roll against their `return_chance`, and on success a return day 14–60 days ahead. On that day they appear at the gate as a **cố nhân** and the player accepts or declines (GDD §6.11 "Cố nhân trở lại"); a returner keeps their ID, level, PA and traits and remembers 70% of their skill levels. The player meets this system on the Jianghu screen (list, NPC guild ranking) and through events. Without it, every departure is a deletion and the Arena has nobody to fight.

## Player Fantasy

*Lens: creative-director (no agents spawned; autonomous run picked the recommended framing, decision logged).*

**"The jianghu remembers my guild."** Two moments carry it, both from GDD §6.11.

- **The rival with a familiar face.** The player let Lý Tam go over a salary demand last month. Tonight, at the Lôi Đài, the third fighter of Thanh Long Bang is Lý Tam, and his attack is the number the player remembers. A departure is not a deletion: the people you did not keep shape the world you compete in. *Asks of the design:* signed agents appear in lineups by name and ID (R7), and NPC strength tracks the player so the rivalry stays close (F2).
- **The door that stays open.** A disciple who left in anger knocks on the gate six weeks later, older and slightly rusty. The player decides whether to take them back. *Asks of the design:* the return is rare enough to matter (gated by Retention's `return_chance`), keeps identity (same ID and name, Member model R2), and costs something visible (skills partly forgotten, F8).

Rejected framing: "a living economy of rival guilds" (full NPC simulation). It works against GDD §6.11 "mức thô (không mô phỏng realtime)" and the mobile tick budget (Sim core F-budget, P5 5%).

## Detailed Design

*Specialist lenses applied (no agents spawned; routing: `Gameplay` → "Character systems" row, union with "AI, pathfinding, behavior" for NPC guild behaviour).* **game-designer:** the player's decisions are three — invite a free agent now (and at what salary) or let the jianghu take them; poach a strong agent back from an NPC guild at a fee; accept or decline a cố nhân. The player cannot see whether a departed member will return, cannot stop an NPC guild signing someone except by getting there first, and cannot weaken NPC guilds. **systems-designer:** two daily processes and two commands, every random outcome one seeded draw with a stated key; NPC growth is a rubber band (non-decreasing, bounded per day) so it can neither run away nor be sandbagged; every collection has a hard cap (F10). **ai-programmer:** NPC guilds make no decisions beyond "sign this agent" (a weighted draw) — no scoring, no planning, constant cost per guild per day. **narrative-director:** every transition is an event with IDs only (the Chronicle and AI text layer 36 phrase it; GDD §9 "kết quả do game quyết"); a returner's rejoin is a milestone. **art-director:** an NPC guild needs a banner colour plus a glyph, never colour alone. **systems-designer vs game-designer tension** (resolved by recommended option): a pure schedule for NPC growth is simpler but leaves Arena rivals far too weak or strong after rebirths; the rubber band was chosen.

### Core Rules

All values are integers. Probabilities are parts per million (`_ppm`); written here as percent for readability. Gold is integer gold. Rounding is floor unless stated. "Day slot" means this system's anchored daily deadline (R2).

**R1 — Ownership and gating.** Jianghu owns: the NPC guild table state (`npc[]`), the free-agent records (`fa[]`), the return schedule, commands 1701–1702, events 1701–1709, fail codes 17001–17003, the `fa_*`, `npc_*`, `inv_*`, `sign_*`, `poach_*` and `return_*` keys in `config.csv` (except `return_base` and `return_loyalty_coef`, which Retention owns), and the new content table `npc_guilds.csv` (R3). It does not own the member record (Member model 8), loyalty or contracts (Retention 16), CA (CA/PA 9), the ledger (Gold economy 27), the roster cap (Guild and buildings 30) or arena fights (Arena 18). Jianghu is **live** when at least one `npc_guilds.csv` row is live (`content_wave` ≤ current wave; Data layer gating, default wave 2). While not live, nothing in this document runs and the hand-offs from Retention and Recruitment are discarded, as those GDDs already state.

**R2 — Daily job (P5).** One P5 handler (`jianghu`, order 1700), with one anchored deadline `day_due_tick` every 86,400 s of game time, anchored at guild creation (Sim core R5 convention; the same grid as Retention's day slot, which runs first at order 1600). At each day slot, in this order:
1. Close return offers past their window (R9).
2. Open return offers whose `return_tick` ≤ now (R9), ascending `fa_id`.
3. For each NPC guild in ascending `uid`: grow (F2), update level (F3) and fame (F4); emit `npc_guild_level_up` (1708) on a level change.
4. For each NPC guild in ascending `uid`: release signed agents whose tenure reached `npc_tenure_days` (R6).
5. For each `Listed` agent in ascending `fa_id`: if listed ≥ `fa_stay_days` days ago, unlist it (R5); else if listed at least one full day ago, run the sign check (R6).

On the first day slot after Jianghu goes live, NPC guilds are seeded (R3) before step 3.

**R3 — NPC guilds.** `npc_guilds.csv` (new; one row per guild, 8–12 rows, `npc_guild_count_min/max` enforced by the content validator): `id`, `uid`, `name_key` (i18n), `strength_ppm` (500,000 – 1,500,000), `schools` (semicolon list of 1–5 `school_id`s, cycled for synthetic slots), `banner` (art key), `content_wave`. Runtime state per guild: `power` (0–200), `level` (1–8), `fame` (≥ 0), `signed[]` (≤ `npc_signed_max` fa_ids). **Seeding:** `power = floor(player_ref_ca × strength_ppm / 1e6 × npc_start_ppm / 1e6)` (F1, F2 inputs), `fame = 0`, `level` by F3, `signed = []`. A guild row that becomes live in a later wave is seeded the same way at its first day slot.

**R4 — Listing.** A free-agent record is created in two ways. Each gets `fa_id = fa_next_id++` (saved counter, never reused) and is `Listed` with `listed_tick = now`.
- **Departure** (Retention R8 step 3): Retention hands `{snapshot, departed_tick, reason, final_loyalty, wallet_burned, return_chance}`. The record keeps all of it; `source = departed`, `member_id` = the snapshot's ID. `ca` is read once from CA/PA on the snapshot and frozen.
- **Unhired candidate** (Recruitment R10): when an offer closes, Recruitment hands its unhired candidate specs. Jianghu lists only the one with the highest PA (ties lowest slot), with `source = candidate`, `member_id = 0`, `final_loyalty = fa_candidate_loyalty` (50), `reason = candidate`, `return_chance = 0`, and a stay of `fa_candidate_days` (2) instead of `fa_stay_days`. `ca` comes from CA/PA's candidate view (PROVISIONAL, OQ-3).
If the list is at `fa_list_max` (40), the `Listed` record with the soonest expiry is unlisted first (cause `evicted`, R5), candidates before departed members, ties lowest `fa_id`; a departed member is never evicted to make room for a candidate (the candidate is then dropped instead). Emit `fa_listed` (1701).

**R5 — Unlisting.** A record leaves `Listed` by expiry or eviction. A `candidate` record is deleted (`Gone`). A `departed` record goes to **Dormant**: one return draw (F9, R11 key `[4, fa_id]`). On failure the record is deleted. On success `return_tick` is set and the record is kept with its snapshot. Emit `fa_unlisted` (1703) with cause; the payload never says whether a return is scheduled (hidden, as GDD §6.11 intends).

**R6 — NPC signing.** Sign check for one `Listed` agent: if no live NPC guild has a free signed slot, skip. Else one draw `chance_ppm(F5)`; on success one `randint(0, W − 1)` picks a guild among those with a free slot, weight `fame + 1`, in ascending `uid`. The agent becomes `Signed` with that guild, `signed_tick = now`. Emit `fa_signed` (1702). **Release:** a `Signed` agent whose tenure reached `npc_tenure_days` (30) is released: a `departed` record goes to Dormant with a fresh return draw (R5; a rival can become an old friend), a `candidate` record is deleted. Emit `npc_released` (1709). A signed agent's `ca` stays frozen at listing.

**R7 — Lineup (read API, for Arena 18).** `npc_lineup(uid)` returns exactly `npc_lineup_size` (5) slots, recomputed on each call, never stored: signed agents with `ca > power` first, by `ca` descending then `fa_id`; remaining slots synthetic, each `{source: synthetic, ca: power, school_id: schools[i mod len], level: F6}`. A signed slot is `{source: agent, fa_id, member_id, name via Member model name record, school_id and level from the snapshot, ca}`. Arena owns how a slot becomes combat stats (PROVISIONAL, OQ-1). `npc_guilds_view()` returns, per live guild, `{uid, name_key, banner, level, fame, power, signed count}` for the ranking screen, plus the player guild's `guild_level` (Guild and buildings) and `player_ref_ca` (F1) for comparison. `npc_record_result(uid, fame_delta)` is Arena's only write: `fame = max(0, fame + fame_delta)`.

**R8 — Inviting (command 1701).** `invite_free_agent(fa_id, offer)` (P1). `offer` is a daily salary in gold. Refusals, in order: Jianghu not live (`not_live`, 9); no `Listed` or `Signed` record with that ID (`unknown_agent`, 101); the agent was invited within `inv_cooldown_h` (24) (`cooldown`, 106); `offer < ask × inv_offer_floor_ppm / 1e6` (F7) (`offer_too_low`, 103); roster at `member_cap` (Guild and buildings F2) (`roster_full`, 102); the fund cannot pay the attempt cost (`cannot_afford`, 8). Otherwise:
1. Debit the **attempt cost** = `offer × inv_fee_days` (1 day's wage, "tiền lễ") through Gold economy as sink `jianghu_invite` (Gold economy type 31). It is paid win or lose.
2. Increment the record's `invite_ordinal`; one draw `chance_ppm(F7)` with key `[3, fa_id, invite_ordinal]`.
3. Success on a `Signed` agent also debits the **poach fee** (F8) as sink `jianghu_poach`; if the fund cannot pay it now the invite still fails with no second draw (the reason is reported as `cannot_afford_fee`, 104) — so the client must show the fee before sending (UI Requirements).
4. Success: rejoin (R10) with path `list` or `npc`; the record is deleted. Failure: nothing else changes; the agent stays where they are.
Emit `fa_invite_result` (1704) either way.

**R9 — Cố nhân (story return, command 1702).** At step 2 of the day job, a Dormant record with `return_tick ≤ now` becomes `ReturnOffered` with `offer_until = now + return_offer_window_h` (48 h). Emit `return_offer_opened` (1706). `answer_return(fa_id, accept)` (P1): refused if no such offer (`not_pending`, 105); accept with roster at cap (`roster_full`, 102). Accept → rejoin (R10) with path `story`, at the salary the member had when they left, with no attempt cost. Decline, or the window passes (step 1), → the record is deleted (`Gone`; the name record stays, Member model R3). Emit `return_offer_closed` (1707) with the outcome. There is no fee: the cost of a cố nhân is the forgotten skill (F8) and a roster slot.

**R10 — Rejoin.** In one P1 applier, all-or-nothing (Command layer):
1. Build the `create_member` spec from the snapshot (Member model R8): a `departed` record passes its original `member_id` with origin `returned`; a `candidate` record gets a new ID with origin `recruited` (path `list`) or `poached` (path `npc`). Level, rebirth, PA, `pa_exact`, traits and reveals, school and skills are kept (CA/PA OQ-7 conformed); on path `story` skill levels are reduced by F8. Equipment is empty (it went to guild storage at departure, Member model R9).
2. Retention initialises mood, loyalty and contract (Retention R1; origin `returned` gets its return bonus); the contract salary is the accepted `offer` (paths `list`/`npc`) or the old salary (path `story`).
3. If `wallet_burned > 0`, Gold economy mints it back as `member_returned` (Gold economy R11) — 100% (Retention OQ-4 default).
4. Emit `member_rejoined` (1705), a **milestone** with the member as subject.
If `create_member` refuses (for example the ID check of Member model R2 fails), the command fails, nothing is debited except the already-paid attempt cost, and fail code 17001 is logged in debug builds.

**R11 — Randomness.** RNG domain 14 (`npc_guild`). Keys, one generator per event:
- NPC growth: `[1, npc_uid, day_index]` → `randint(0, npc_noise_max)` (one draw, even when unused, so draw order never depends on state).
- Sign check: `[2, fa_id, day_index]` → `chance_ppm(F5)`, then, on success, `randint(0, W − 1)`.
- Invite: `[3, fa_id, invite_ordinal]` → `chance_ppm(F7)`.
- Return: `[4, fa_id, release_count]` → `chance_ppm(return_chance)`, then, on success, `randint(return_min_days, return_max_days)`. `release_count` (0 at first unlisting, +1 on each NPC release) makes a second Dormant entry a different event.
`day_index = (day slot tick − anchor tick) / day_ticks`. **Uniqueness (RNG R6):** `fa_id` and `npc_uid` are unique for the save, `day_index` increases, `invite_ordinal` and `release_count` are saved per record and only increase; the leading tag separates event kinds. **No key part is player-mutable**: reloading and offering more reuses the same die with a better chance (RNG Edge Cases, save-scumming).

**R12 — Save.** One save section (Local save R5): `fa_next_id`, `day_due_tick`, NPC guild states, every `fa` record with its snapshot, `invite_ordinal`, `release_count`, `last_invite_tick`, `return_tick`/`offer_until`.

### States and Transitions

Free-agent record (one state at a time):

| State | Meaning | Leaves to |
|---|---|---|
| `Listed` | On the Jianghu list, up to `fa_stay_days` (candidates `fa_candidate_days`) | `Signed` (R6), `Rejoined` (invite success), `Dormant` (departed, expiry/eviction, return draw succeeds), `Gone` (candidate expiry/eviction, or return draw fails) |
| `Signed` | Fights for an NPC guild; visible in its lineup | `Rejoined` (poached, R8), `Dormant` (released after tenure, return draw succeeds), `Gone` (otherwise) |
| `Dormant` | Hidden; `return_tick` scheduled | `ReturnOffered` at `return_tick` |
| `ReturnOffered` | Cố nhân at the gate for `return_offer_window_h` | `Rejoined` (accept), `Gone` (decline or expiry) |
| `Rejoined` | Terminal: back on the roster; record deleted after `member_rejoined` | — |
| `Gone` | Terminal: record deleted; the name record survives in Member model | — |

NPC guild: `Unseeded` → `Active` (first live day slot). Active guilds never leave; level only rises (F3 on non-decreasing power).

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|---|---|---|---|---|
| Sim core (1) | core → this | P5 handler (order 1700), P1 appliers, `ctx.derive`, `ctx.emit` | — | Sim core |
| Deterministic RNG (2) | this → RNG | Domain 14, keys R11 | Draws | RNG primitives; this GDD owns keys |
| Data layer (3) | data → this | `npc_guilds.csv` (new), `config.csv` keys | — | Data layer; validator ranges are the implementation story's |
| Command layer (5) | both | Commands 1701 `invite_free_agent`, 1702 `answer_return` | Reason codes | Command layer frames |
| Local save (6) | this → 6 | — | Section R12 | Local save contract |
| Member model (8) | both | Snapshot at removal; name record; `member_cap` check uses roster size | `create_member(spec)` with original ID / origin (R10) | Member model owns creation and IDs |
| CA/PA and traits (9) | 9 → this | CA of a snapshot and of a candidate spec; `trait_mod_ppm(negotiation_success, salary_demand)` | — | CA/PA |
| Retention (16) | both | Departure hand-off (R8 step 3), `return_chance` (F9), `return_base`, `return_loyalty_coef`, D (F5 daily reference) | Rejoin initialisation call (Retention R1) | Retention owns loyalty; Jianghu owns the list and returns |
| Recruitment (15) | 15 → this | Unhired candidate specs on offer close (R10) | — | Jianghu owns the list (Recruitment OQ-6 answered: own command, not a board offer) |
| Gold economy (27) | this → 27 | `fund` balance | Sinks `jianghu_invite`, `jianghu_poach`; mint `member_returned` | Gold owns the ledger and all lines (types 31, 32, 7; OQ-4 resolved) |
| Guild and buildings (30) | 30 → this | `member_cap`, `guild_level` | — | Buildings |
| Offline progress (31) | 31 → this | `settle_to(to_tick)` as an **elapsing** owner (Offline R8, answers Offline OQ-13) | Away-report lines: signed, unlisted, return offers | Offline owns the gap |
| Event bus (42) | this → 42 | — | Events 1701–1709 | Event bus |
| Arena (18) | 18 ↔ this | `npc_record_result(uid, fame_delta)` | `npc_guilds_view`, `npc_lineup` (R7) | Jianghu owns NPC state; Arena owns fights (PROVISIONAL, OQ-1) |
| Guild screens (39), AI text (36), Chronicle, Quests (25), Analytics (37), Push (46) | this → them | — | Events and read APIs `fa_list_view()`, `npc_guilds_view()` | Readers only |

**Events** (Event bus R3; block 1700–1799; payload ≤ 4 ints):

| ID | Name | Payload | Tier |
|---|---|---|---|
| 1701 | `fa_listed` | fa_id, member_id or 0, source (0 departed, 1 candidate), ca | ring |
| 1702 | `fa_signed` | fa_id, member_id or 0, npc_uid | ring |
| 1703 | `fa_unlisted` | fa_id, member_id or 0, cause (0 expired, 1 evicted) | ring |
| 1704 | `fa_invite_result` | fa_id, success, offer, chance_ppm | ring |
| 1705 | `member_rejoined` | member_id, path (0 list, 1 npc, 2 story), npc_uid or 0 | **milestone** |
| 1706 | `return_offer_opened` | fa_id, member_id | ring |
| 1707 | `return_offer_closed` | fa_id, member_id, outcome (0 accepted, 1 declined, 2 expired) | ring |
| 1708 | `npc_guild_level_up` | npc_uid, level | ring |
| 1709 | `npc_released` | fa_id, member_id or 0, npc_uid | ring |

Free agents and NPCs are ring events with no milestone subject (Event bus R3a); only 1705, where the subject is back on the roster, is a milestone.

**Fail codes:** 17001 `create_member` refused a rejoin; 17002 a `Signed` record names a guild that is not live; 17003 a duplicate `fa_id` on load.

## Formulas

### F1 — `player_ref_ca`

The player_ref_ca formula is defined as:

`player_ref_ca = floor( Σ ca(top k) / k )`, where the top k are the `min(npc_ref_top, n)` on-roster non-elder members with the highest CA; 0 if n = 0.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| npc_ref_top | int | 1 – 10 | data file | Default 5 (= `party_max`, the player's best party) |
| n | int | 0 – member_cap | calculated | On-roster non-elder members |
| ca | int | 0 – 200 | calculated | CA/PA's CA |

**Output Range:** 0 – 200. 0 only with no eligible member; F2 then has target 0, so power does not change (it never falls).
**Example:** top five CA 90, 85, 80, 70, 65 → 390 / 5 = 78.

### F2 — `npc_power` (daily growth)

The npc_power formula is defined as:

`target = min(200, floor(player_ref_ca × strength_ppm / 1e6))`
`gap_step = max(0, ceil((target − power) × npc_catchup_ppm / 1e6))`
`noise = randint(0, npc_noise_max)` if `power < target + npc_overshoot`, else 0 (the draw is still made)
`power' = min(200, power + gap_step + noise)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| strength_ppm | int | 500,000 – 1,500,000 | data file (`npc_guilds.csv`) | Guild's strength relative to the player |
| npc_catchup_ppm | int | 20,000 – 300,000 | data file | Share of the gap closed per day. Default 100,000 |
| npc_noise_max | int | 0 – 3 | data file | Default 1 |
| npc_overshoot | int | 0 – 20 | data file | Max drift above target. Default 5 |
| npc_start_ppm | int | 0 – 1,000,000 | data file | Seed fraction of target (R3). Default 800,000 |
| power | int | 0 – 200 | calculated (saved) | Current power |

**Output Range:** 0 – 200, non-decreasing. Above `target + overshoot` power is frozen; a guild can never exceed `max(its value when the player weakened, target + overshoot)`. Daily change ≤ `ceil(200 × 0.3) + 3 = 63` at the safe-range extremes; ≤ 21 at defaults.
**Example:** power 60, player_ref_ca 80, strength 1,200,000 → target 96; gap 36 × 0.1 = 3.6 → 4; noise 0–1 → power 64–65. Halfway point closes in about 7 days (0.9⁷ ≈ 0.48).
**Feedback loop:** a negative (balancing) loop by design — rivals chase the player. Damped by catchup < 1, the overshoot cap and non-decrease (so a player cannot sandbag CA to weaken rivals; Edge Cases).

### F3 — `npc_level`

The npc_level formula is defined as:

`level = clamp(1 + floor(power / npc_level_ca_step), 1, 8)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| power | int | 0 – 200 | calculated | F2 |
| npc_level_ca_step | int | 15 – 40 | data file | Default 25 |

**Output Range:** 1 – 8 (matches the player's `guild_level` scale, Guild and buildings). Power 175+ is level 8 at defaults.
**Example:** power 64 → 1 + 2 = 3.

### F4 — `npc_fame` (daily)

The npc_fame formula is defined as:

`fame' = fame + level × npc_fame_per_level` (daily), plus Arena's `fame_delta` (R7), floored at 0.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| level | int | 1 – 8 | calculated | F3 |
| npc_fame_per_level | int | 0 – 50 | data file | Default 10 |
| fame_delta | int | any | Arena (18) | PROVISIONAL |

**Output Range:** ≥ 0; grows at most 400/day at the safe max. Used only as the signing weight (F5 guild pick) and for display. Unbounded growth is harmless in 64-bit (8 × 50 × 365 × 100 years ≈ 1.5 × 10⁷).
**Example:** level 3 → +30/day.

### F5 — `sign_chance` (daily, per listed agent)

The sign_chance formula is defined as:

`sign_chance = clamp(sign_base + sign_ca_coef × ca / 200 + sign_day_coef × days_listed, sign_min, sign_max)`; guild pick weight `fame + 1`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| sign_base | ppm | 0 – 200,000 | data file | Default 50,000 |
| sign_ca_coef | ppm | 0 – 500,000 | data file | Default 250,000 |
| sign_day_coef | ppm | 0 – 100,000 | data file | Default 20,000 per full day listed |
| ca | int | 0 – 200 | calculated (frozen at listing) | Agent's CA |
| days_listed | int | 1 – 6 | calculated | Full days since listing (checks start at 1, R2) |
| sign_min, sign_max | ppm | 0 – 1,000,000 | data file | Defaults 0, 600,000 |

**Output Range:** 7% (CA 0, day 1) to 42% (CA 200, day 6) at defaults, inside [0, 60%].
**Example:** CA 100, day 3: 5% + 12.5% + 6% = 23.5%. Per-day chances for CA 100 on days 1–6 are 19.5%, 21.5%, 23.5%, 25.5%, 27.5%, 29.5%: 80.5% survive day 1, 63% survive day 2, and 18% are never signed in a 7-day stay — the player has a day or two, and a strong agent goes quickly.

### F6 — `synthetic_level`

The synthetic_level formula is defined as:

`level = clamp(round(power × npc_level_per_ca_ppm / 1e6), 1, 200)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| power | int | 0 – 200 | calculated | F2 |
| npc_level_per_ca_ppm | int | 500,000 – 1,500,000 | data file | Default 1,000,000 (CA and level share the 0–200 scale) |

**Output Range:** 1 – 200. **Example:** power 64 → level 64. PROVISIONAL on Arena's stat conversion (OQ-1).

### F7 — `fa_ask` and `invite_chance`

The invite_chance formula is defined as:

`ask = max(last_salary, ceil_to(D × fa_ask_pct_ppm / 1e6 × max(0.5, 1 + trait(salary_demand)), raise_round))`
`base = inv_base + inv_loyalty_coef × final_loyalty / 100 + trait(negotiation_success) − reason_pen(reason)`
`invite_chance = clamp(base × min(offer, ask) / ask × (poach_mult if Signed else 1), inv_min, inv_max)`
Offers below `ask × inv_offer_floor_ppm / 1e6` are refused (R8).

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| D | gold/day | ≥ 24,000 | calculated (Retention F5: `income_ref_per_level × level × 24`) | Daily reference income at the agent's level |
| fa_ask_pct_ppm | ppm | 50,000 – 200,000 | data file | Default 100,000 (twice Retention's `raise_pct_ppm`) |
| last_salary | gold/day | ≥ 0 | snapshot | 0 for candidates |
| raise_round | int | 1 – 100 | data file (Retention) | Rounding step |
| inv_base | fraction | 0.1 – 0.6 | data file | Default 0.3 |
| inv_loyalty_coef | fraction | 0 – 1 | data file | Default 0.4 |
| final_loyalty | int | 0 – 100 | snapshot (candidates `fa_candidate_loyalty` 50) | Loyalty at departure |
| trait(…) | fraction | −0.3 – +0.3 | calculated (CA/PA `trait_mod_ppm`) | e.g. `t_stubborn` −0.15 negotiation |
| reason_pen | fraction | 0 – 0.5 | data file | `let_go` 0, `timeout` 0.05, `dismissed` 0.25, `candidate` 0 |
| poach_mult | fraction | 0.2 – 1 | data file | Default 0.5 |
| inv_offer_floor_ppm | ppm | 0 – 1,000,000 | data file | Default 500,000 |
| inv_min, inv_max | ppm | — | data file | Defaults 20,000, 900,000 |

**Output Range:** 2% – 90%. At the offer floor the chance is half of `base`; `ask ≥ 1` always (D ≥ 24,000), so no division by zero.
**Example:** D = 120,000, `t_stubborn` (no salary trait), last salary 5,000 → ask = max(5,000, 12,000) = 12,000. Final loyalty 30, reason `let_go`: base = 0.3 + 0.12 − 0.15 = 0.27. Offer 12,000 → 27%; offer 6,000 → 13.5%. Same agent signed by an NPC guild, full offer → 13.5%.

### F8 — `poach_fee` and `return_skill_keep`

The poach_fee formula is defined as:

`poach_fee = ca × poach_fee_per_ca × npc_level`
`lv' = lv ≥ 1 ? max(1, floor(lv × return_skill_keep_ppm / 1e6)) : 0`, `xp' = 0` — for every entry of `skills[]`, path `story` only.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| ca | int | 0 – 200 | calculated | Agent's frozen CA |
| poach_fee_per_ca | gold | 0 – 5,000 | data file | Default 500 |
| npc_level | int | 1 – 8 | calculated | F3 of the signing guild |
| return_skill_keep_ppm | ppm | 300,000 – 1,000,000 | data file | Default 700,000 (GDD §6.11 "nhớ lại một phần") |
| lv | int | 0 – skill max | snapshot | Skill level |

**Output Range:** fee 0 – 8,000,000 gold (CA 200, level 8, max knob); 480,000 for CA 120 at level 8 at defaults — a large but finite sink, comparable to mid-game enhancement. Skill level never drops below 1 for a learned skill.
**Example:** CA 120, guild level 4 → 240,000 gold. Skill lv 10 → 7; lv 1 → 1.

### F9 — `return_schedule`

The return_schedule formula is defined as:

`will_return = chance_ppm(return_chance)`; if true, `return_tick = day slot tick + randint(return_min_days, return_max_days) × 86,400 × tick_rate`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| return_chance | ppm | 0 – 1,000,000 | Retention F9 (at departure) | 0.1 – 0.75 at defaults |
| return_min_days | int | 3 – 60 | data file | Default 14 |
| return_max_days | int | ≥ return_min_days, ≤ 180 | data file | Default 60 |

**Output Range:** each departed agent who reaches Dormant returns with exactly `return_chance`, between 14 and 60 days later, uniformly.
**Example:** `return_chance` 0.46 (Retention's worked example) → 46% chance of a cố nhân offer 14–60 days after unlisting.

### F10 — Memory bound

The jianghu_records formula is defined as:

`records ≤ fa_list_max + npc_count × npc_signed_max + return_pool_max`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| fa_list_max | int | 10 – 100 | data file | Default 40 |
| npc_count | int | 8 – 12 | content | Live `npc_guilds.csv` rows |
| npc_signed_max | int | 0 – 5 | data file | Default 5 (≤ `npc_lineup_size`) |
| return_pool_max | int | 10 – 200 | data file | Default 50; when full, a successful return draw is discarded (oldest-scheduled kept) |

**Output Range:** ≤ 40 + 60 + 50 = 150 records at defaults; at about 1 KB per snapshot, ≤ 150 KB of save. Per day slot the work is O(npc_count + records), constant-bounded.
**Example:** expected flow at Retention's 3–10%/month target with a 30-member roster: 1–3 departures a month plus one candidate per closed recruitment offer (each staying 2 days); when full, the cap evicts candidates first and never evicts a departed member for a candidate (R4).

## Edge Cases

- **If Jianghu is not live** (wave 1): Retention and Recruitment discard their hand-offs; no record exists; `npc_lineup` returns an empty list; commands refuse `not_live`. Members who left in wave 1 never return (accepted; Retention already states it).
- **If a member leaves while the list is full of departed members**: the soonest-expiring departed record is evicted to Dormant (with its return draw), not deleted — departures are never lost silently.
- **If the player invites an agent the same tick an NPC signs them**: P1 (command) runs before P5 (day job), so the invite resolves first; a successful invite deletes the record before the sign check.
- **If two invites for the same agent arrive in one tick**: the second is refused `cooldown` (Command layer processes in order).
- **If the roster is at cap when a cố nhân arrives**: the offer still opens; `answer_return(accept)` is refused `roster_full` until the player makes room within the 48 h window.
- **If a returning member's ID is somehow on the roster** (corruption): `create_member` refuses, fail 17001, the record is kept (not deleted), and the debug build reports it.
- **If the player has no eligible member** (all elders or empty roster): `player_ref_ca` = 0, target 0, NPC power does not change (non-decreasing). Seeding with ref 0 gives power 0 (level 1); they catch up when the roster recovers.
- **If the player's CA drops** (school change skill loss, rebirth effects, top members leaving): NPC power never falls; rivals stay at their peak until the player catches up. Sandbagging CA gains nothing.
- **If player CA jumps** (a strong hire): rivals close 10% of the gap per day; Arena is temporarily easier — intended reward.
- **If a dismissed member is re-invited at once to reset loyalty** (degenerate loop check): they pay the attempt cost (≥ ask ≥ 10% D, twice a Retention raise), face `reason_pen` 0.25 and a daily cooldown, friends already took Retention's ×1.5 chain penalty, and the wallet nets to zero (burned, minted back). Not profitable versus accepting a raise. Re-invite starts loyalty at `loyalty_join` (Retention R1), which is intended forgiveness.
- **If the player farms recruitment rejections to fill the list**: only one candidate per offer is listed, for 2 days, and inviting costs a day's wage plus salary ≥ ask; it is a second recruitment door, bounded by `member_cap`.
- **If an NPC guild row is removed or its `content_wave` raised in a later build**: its signed agents become orphans (fail 17002 on load); the migration releases them to Dormant with their return draw. Signed slots of other guilds are unaffected.
- **Offline gap**: Jianghu is an elapsing owner (Offline R8): every crossed day slot runs through `settle_to` in order, using the CA in the simulation at that moment. Agents can be signed or unlisted while the player is away; each such change is an away-report line. A return offer whose window would close during the gap gets `offer_until = max(offer_until, return_tick_live + return_offer_window_h)` at hand-back, the same pattern as Retention R6.
- **If `return_pool_max` is reached**: a new successful return draw is discarded and the record deleted (`Gone`); the draw was still consumed so keys stay aligned.
- **If a signed agent's CA ≤ guild power**: they are not in the lineup (synthetic fighters are stronger) but still occupy a signed slot until tenure; the Jianghu screen still lists them under the guild.
- **If `npc_signed_max` = 0**: no signing; listed agents only expire or are invited. Arena lineups are fully synthetic.
- **If `strength_ppm` > 1,000,000 and the player is at CA 200**: target capped at 200; strongest rivals match, never exceed, the scale.

## Dependencies

### Upstream (this system depends on)

| System | Hard/Soft | Interface | Status |
|---|---|---|---|
| Deterministic RNG (2) | Hard | Domain 14, keys R11 | Designed (Needs Revision) |
| Retention (16) | Hard | Departure hand-off, `return_chance`, D, rejoin initialisation | Designed |
| Member model (8) | Hard | Snapshot, `create_member` with original ID, name record | Designed |
| CA/PA and traits (9) | Hard | CA of snapshot/candidate spec, `trait_mod_ppm` | Designed (candidate CA PROVISIONAL, OQ-3) |
| Gold economy (27) | Hard | Two new sinks, `member_returned` mint | Designed (new sinks PROVISIONAL, OQ-4) |
| Guild and buildings (30) | Hard | `member_cap`, `guild_level` | Designed |
| Sim core (1), Command layer (5), Event bus (42), Local save (6), Data layer (3) | Hard | P5 handler, commands, events, save section, tables | Designed |
| Offline progress (31) | Hard | Elapsing timer owner | Designed |
| Recruitment (15) | Soft | Unhired candidates | Designed |

### Downstream (systems that depend on this one)

| System | Hard/Soft | Interface |
|---|---|---|
| Arena (18) | Hard | `npc_guilds_view`, `npc_lineup`, `npc_record_result` (not designed — PROVISIONAL) |
| Guild screens (39) | Soft | Jianghu screen: `fa_list_view`, `npc_guilds_view`, commands 1701–1702 |
| AI text layer (36), Chronicle | Soft | Events 1701–1709 |
| Quests (25), Analytics (37), Local push (46) | Soft | Events (1706 is a push candidate) |

## Tuning Knobs

All in `data/config.csv` (new keys; adding them and validator ranges is the implementation story's job), except `strength_ppm`/`schools` (per row of the new `npc_guilds.csv`).

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `fa_stay_days` | 7 | 3 – 14 | List bloats, no urgency | No time to react | `sign_*`, `fa_list_max` |
| `fa_candidate_days` | 2 | 1 – 5 | Candidates crowd departures | Candidate door useless | `fa_list_max` |
| `fa_candidate_loyalty` | 50 | 30 – 70 | Candidates easier to win than recruits | Never worth inviting | `inv_loyalty_coef` |
| `fa_list_max` | 40 | 10 – 100 | Save/UI weight | Departures evicted early | F10 |
| `npc_ref_top` | 5 | 1 – 10 | Rivals track roster depth | Rivals track one star | F1 |
| `npc_catchup_ppm` | 100,000 | 20,000 – 300,000 | Rivals snap to player instantly | Rivals lag for weeks | `npc_overshoot` |
| `npc_noise_max`, `npc_overshoot` | 1, 5 | 0–3, 0–20 | Rivals drift above player | Rivals perfectly predictable | F2 |
| `npc_start_ppm` | 800,000 | 0 – 1,000,000 | Wave 2 opens on equal rivals | Rivals trivial at launch | F2 |
| `npc_level_ca_step` | 25 | 15 – 40 | Levels compress | Level 8 reached too early | F3 |
| `npc_fame_per_level` | 10 | 0 – 50 | — | All guilds equally likely to sign | F5 pick weight |
| `npc_signed_max`, `npc_lineup_size` | 5, 5 | 0–5, 3–5 | — | Ex-members never appear as rivals | Arena |
| `npc_tenure_days` | 30 | 7 – 90 | Rivals never release | Rival faces churn | F9 return path |
| `npc_level_per_ca_ppm` | 1,000,000 | 500k – 1.5M | — | — | Arena (OQ-1) |
| `sign_base`, `sign_ca_coef`, `sign_day_coef`, `sign_min`, `sign_max` | 5%, 25%, 2%, 0, 60% | see F5 | Player never wins the race | NPC rivals never get ex-members | `fa_stay_days` |
| `inv_base`, `inv_loyalty_coef`, `inv_min`, `inv_max` | 0.3, 0.4, 2%, 90% | see F7 | Departures meaningless | Invite never worth trying | Retention negotiation |
| `reason_pen_*` | 0 / 0.05 / 0.25 / 0 | 0 – 0.5 | — | Dismiss-and-rehire too easy | Edge Cases |
| `inv_offer_floor_ppm`, `inv_fee_days`, `inv_cooldown_h` | 500,000, 1, 24 | 0–1M, 0–3, 6–72 | Invites prohibitive | Spam invites | — |
| `fa_ask_pct_ppm` | 100,000 | 50,000 – 200,000 | Return too dear | Return cheaper than a raise | Retention `raise_pct_ppm` |
| `poach_mult`, `poach_fee_per_ca` | 0.5, 500 | 0.2–1, 0–5,000 | Poaching never used | Poaching dominates listing | Gold sinks |
| `return_min_days`, `return_max_days` | 14, 60 | 3–60, ≤ 180 | Returns forgotten | Return feels like a revolving door | Retention `return_base` |
| `return_offer_window_h` | 48 | 12 – 168 | — | Offer missed on a normal schedule | Offline |
| `return_skill_keep_ppm` | 700,000 | 300k – 1M | Return is free power | Returner useless | Skills (21) |
| `return_pool_max` | 50 | 10 – 200 | Save weight | Returns discarded | F10 |

Owned elsewhere and only read here: `return_base`, `return_loyalty_coef`, `raise_round`, `income_ref_per_level` (Retention, Gold economy), `party_max` (Party), trait values (`traits.csv`, CA/PA), `member_cap` (Guild and buildings).

## Visual/Audio Requirements

*Lens: art-director. No art bible exists (`design/art/art-bible.md` absent); drafted from GDD §12.4 pixel style.*

- **NPC guild identity**: each guild has a banner (colour + distinct glyph, so it reads without colour) in the ranking and Arena screens. 8–12 banners at the icon size used for buildings.
- **Listing (1701)**: on the Jianghu screen, the departed member's existing portrait/paper-doll in a desaturated frame with a "days left" pip row; candidates use their recruitment card art.
- **Signed (1702)**: the portrait gains the NPC banner as a badge. A short, low "door closes" cue if the agent was an ex-member.
- **Cố nhân (1706)**: the member walks in through the gate in the world view (Realtime world view 38) and waits; a warm, distinct sting — the rarest people event, it should be recognisable.
- **Rejoin (1705)**: same arrival treatment as a hire (Recruitment), with the "returned" mark.
- **NPC level up (1708)**: no world-view effect; ranking-screen arrow only (avoid noise).

## Game Feel

- **Urgency without panic**: the list shows days left and a qualitative "in demand" tag (sign chance ≥ 20%) — never the exact percent, but the player feels the race.
- **The invite answer is immediate**: the command resolves in the next tick; the result card shows win/loss within 200 ms of input on device, with the chance the player was shown before sending (pre-computed by the read API).
- **The return is a surprise**: no countdown, no hint that it is scheduled. The first cố nhân should feel like the game remembered.

## UI Requirements

- Jianghu screen (Guild screens 39): tab 1 free-agent list (portrait, name, school, level, CA/PA estimate as CA/PA shows it, days left, "in demand" tag, NPC banner if signed, ask, invite chance preview for the entered offer, attempt cost and poach fee); tab 2 NPC guild ranking including the player guild (level, power band, fame, banner, signed ex-members).
- Invite dialog: salary field defaulting to `ask`, with the floor; shows attempt cost and, for signed agents, the poach fee; disabled with the reason code text when a refusal would apply.
- Cố nhân card: who, how long ago they left and why (reason ID → i18n), salary they return at, the skill-loss note; Accept / Decline; time left.
- Away report: lines for agents signed, unlisted and cố nhân offers during the gap.
- All text through `i18n/` keys; NPC guild names are `name_key`s.

## Cross-References

| This GDD | Referenced document | Element | Nature |
|---|---|---|---|
| R4, R10, F7 | `retention-leaving-and-negotiation.md` | R1 rejoin init, R8 departure hand-off, F5 D, F9 `return_chance`, OQ-4 | Data and rule dependency |
| R10 | `member-model.md` | R2 ID rule, R3 name record, R8 `create_member`, R9 removal snapshot, `origin` field | Rule dependency |
| R4, F7 | `ca-pa-and-traits.md` | CA, `trait_mod_ppm`, OQ-7 (returner keeps traits — conformed) | Data dependency |
| R8, R10 | `gold-economy.md` | R11 `member_departed`/`member_returned`; new sinks | Ledger dependency |
| R8, R9 | `guild-and-buildings.md` | F2 `member_cap`, `guild_level`; `rivals` field noted as owned here | Data dependency |
| R4 | `recruitment.md` | R10 unhired candidates; OQ-6 (answered) | Data dependency |
| R11 | `deterministic-rng.md` | Domain 14 `npc_guild`, R5–R7 | Rule dependency |
| R2, Edge Cases | `offline-progress.md`, `sim-core-and-tick-loop.md` | Offline R8/R9 elapsing owners, OQ-13; Sim core R5 anchored timers | Rule dependency |
| Events | `event-bus-and-history-log.md` | R3 type IDs and block, R3a milestone subjects | Rule dependency |
| Commands | `command-layer.md` | ID block 1700–1799, reason codes | Rule dependency |
| — | `member-state-machine.md` | No longer lists Jianghu as an `enter_away` caller (OQ-2) | Reconciled 2026-11-16 |

## Acceptance Criteria

Story types: AC-1 – AC-20 are Logic (automated unit tests in `tests/unit/jianghu/`); AC-21 is Integration; AC-22 – AC-23 are UI (screenshot in `production/qa/evidence/`).

- **AC-1 (R1)**: **GIVEN** content wave 1, **WHEN** Retention completes a departure, **THEN** no `fa` record exists and `invite_free_agent` returns `not_live` (9).
- **AC-2 (R4)**: **GIVEN** Jianghu live, **WHEN** a member with final loyalty 30 departs, **THEN** a `Listed` record holds the snapshot, `fa_listed` (1701) is emitted with source 0 and the member's ID, and `fa_next_id` increased by 1.
- **AC-3 (R4)**: **GIVEN** an offer closes with unhired candidates of PA 80, 95 and 95 in slots 0, 1, 2, **WHEN** Recruitment hands them over, **THEN** exactly one record is listed, the slot-1 candidate, with a 2-day stay.
- **AC-4 (R4 eviction)**: **GIVEN** a full list (40) of departed records, **WHEN** a candidate arrives, **THEN** the candidate is dropped and the list is unchanged; **WHEN** a departure arrives instead, **THEN** the soonest-expiring departed record moves to Dormant handling (cause 1) and the new one is listed.
- **AC-5 (R2, F5)**: **GIVEN** an agent listed at tick T, **WHEN** the first day slot falls less than 24 h after T, **THEN** no sign draw is made for it.
- **AC-6 (F5)**: **GIVEN** CA 100 on day 3 at defaults, **THEN** `sign_chance` = 235,000 ppm; **GIVEN** CA 200 on day 6, **THEN** 420,000; **GIVEN** knobs set so the sum exceeds `sign_max`, **THEN** 600,000.
- **AC-7 (R6)**: **GIVEN** two guilds with free slots and fame 0 and 9, **WHEN** 10,000 seeded sign successes are simulated, **THEN** the second guild is picked 10/11 ± 1% of the time; **GIVEN** no free slot anywhere, **THEN** no draw is consumed.
- **AC-8 (F1, F2)**: **GIVEN** power 60, top-5 CA mean 80, strength 1,200,000, defaults, **WHEN** a day slot runs, **THEN** power is 64 or 65; **GIVEN** power 110 and target 96, **THEN** power stays 110 (frozen above target + 5).
- **AC-9 (F2 boundary)**: **GIVEN** an empty roster, **WHEN** 30 day slots run, **THEN** every NPC guild's power is unchanged.
- **AC-10 (F3, F4)**: **GIVEN** power rises from 74 to 75, **THEN** level goes 3 → 4, `npc_guild_level_up` (1708) is emitted once, and fame grows by 40 that day.
- **AC-11 (R6 release)**: **GIVEN** a signed ex-member at tenure 30 days, **WHEN** the day slot runs, **THEN** `npc_released` (1709) is emitted, a return draw with key `[4, fa_id, 1]` is consumed, and the guild's signed count drops by 1.
- **AC-12 (R7)**: **GIVEN** power 64 and signed agents of CA 90 and 50, **WHEN** `npc_lineup` is called, **THEN** it returns 5 slots: the CA-90 agent first, then 4 synthetic slots of CA 64, level 64, schools cycling through the row's list; the CA-50 agent is absent.
- **AC-13 (F7)**: **GIVEN** D 120,000, last salary 5,000, final loyalty 30, `t_stubborn`, reason `let_go`, **WHEN** offer 12,000, **THEN** ask = 12,000 and chance = 270,000 ppm; offer 6,000 → 135,000; offer 5,999 → refused `offer_too_low` (103); the same agent `Signed` at offer 12,000 → 135,000.
- **AC-14 (R8)**: **GIVEN** a valid invite of 12,000 that fails its draw, **THEN** the fund decreased by exactly 12,000 (sink `jianghu_invite`), the agent stays `Listed`, and a second invite before 24 h is refused `cooldown` (106).
- **AC-15 (R8, F8)**: **GIVEN** a successful invite on a CA-120 agent signed by a level-4 guild, **THEN** 240,000 gold is debited as `jianghu_poach` in addition to the attempt cost, and the member rejoins with path 1.
- **AC-16 (R10)**: **GIVEN** a departed member with `wallet_burned` 3,000 invited back, **WHEN** the invite succeeds, **THEN** `create_member` receives the original `member_id` with origin `returned`, Gold economy records a `member_returned` mint of 3,000, the member has no equipment, all traits and `pa_exact` match the snapshot, and `member_rejoined` (1705) is a milestone with that member as subject.
- **AC-17 (F9)**: **GIVEN** `return_chance` 460,000 and a fixed seed, **WHEN** 10,000 records reach Dormant, **THEN** 46% ± 1% get a `return_tick`, all between 14 and 60 days after their unlisting slot, roughly uniform (χ² p > 0.01).
- **AC-18 (R9, F8)**: **GIVEN** a cố nhân with skills at lv 10 and lv 1, **WHEN** accepted, **THEN** the member rejoins with skill levels 7 and 1, xp 0, at their old salary, with no gold debited; **WHEN** instead the 48 h pass, **THEN** `return_offer_closed` outcome 2 is emitted and the record is gone.
- **AC-19 (R11 determinism)**: **GIVEN** a saved game, **WHEN** the player reloads and repeats the same invite with a higher offer, **THEN** the same die is used (same `invite_ordinal` key) and the outcome differs only if the higher chance crosses that die.
- **AC-20 (Edge: roster full)**: **GIVEN** the roster at `member_cap`, **WHEN** the player invites or accepts a cố nhân, **THEN** both are refused `roster_full` (102) and no gold moves.
- **AC-21 (Integration, offline)**: **GIVEN** a listed agent and 3 days offline, **WHEN** Offline progress settles, **THEN** the day job ran exactly 3 times in order, the result equals 3 live day slots with the same inputs (parity), and every sign/unlist appears in the away report.
- **AC-22 (UI)**: Screenshot of the Jianghu list with a listed ex-member (days left, "in demand"), a signed agent with banner, and the invite dialog showing ask, chance preview, attempt cost and poach fee.
- **AC-23 (UI)**: Screenshot of a cố nhân card and of the NPC guild ranking including the player guild.

**Performance**: the day job for 12 guilds and 150 records completes within the P5 share of one tick (Sim core: 5% of the tick budget) on the min-spec device; measured with the P1 spike harness.

## Open Questions

| # | Question | Owner | Resolve by |
|---|---|---|---|
| OQ-1 | PROVISIONAL: Arena (18) — consumes `npc_lineup` slots `{ca, level, school_id, snapshot}` and converts them to combat stats; writes NPC fame only through `npc_record_result(uid, fame_delta)`; owns arena rewards and the local Lôi Đài leaderboard. | Arena GDD | When Arena is designed |
| OQ-2 | **RESOLVED (user decision 2026-11-16):** NPC guilds never poach on-roster members; they only sign free agents (§6.11). No on-roster poaching cause is added to Retention. Member model R9 and Member state machine R6 conform. "Poach" in this document means only the *player* signing a `Signed` agent back from an NPC guild (R8, F8). | Producer | Closed |
| OQ-3 | PROVISIONAL: CA/PA (9) — exposes CA for a departure snapshot and for a recruitment candidate spec (`candidate_view` or a pure `ca_of(spec)`). | CA/PA | Implementation |
| OQ-4 | **RESOLVED (consistency-check 2026-11-16):** Gold economy R3 adds `jianghu_invite` (31) and `jianghu_poach` (32) as fund burns; `member_returned` (7) mints 100% of the burned amount. | Gold economy | Closed |
| OQ-5 | **Schema change (not decided autonomously):** the new content table `data/npc_guilds.csv` (R3) and its validator rules (8–12 rows, `strength_ppm` range, school IDs exist). GDD §20 line "dữ liệu bang NPC: soạn khi vào giai đoạn 3" expects it; needs approval and a Data layer entry. | Data layer / producer | Before implementation |
| OQ-6 | **RESOLVED (consistency-check 2026-11-16):** Command layer R6's shared codes are 6 `target_missing`, 7 `not_allowed_now`, 8 `cannot_afford`, 9 `not_live`; 7 is not `cooldown`. `cannot_afford` (8) and `not_live` (9) stand; `cooldown` is now this system's own code 106 (101–106 are its own). | Command layer | Closed |
| OQ-7 | Should the cố nhân be a multi-step story chain (GDD §6.11 "chuỗi sự kiện cốt truyện") rather than one gate event? This design ships one event; a chain is narrative content for AI text (36) / Chronicle, with the outcome still decided here. | Narrative / producer | Full Vision content pass |
| OQ-8 | Should signed agents' CA grow while in an NPC guild (currently frozen at listing)? Frozen is simpler and keeps "the number the player remembers"; growth would make poaching more attractive. | Game design | Arena balance pass |
| OQ-9 | Cloud asynchronous "bóng" opponents (GDD §6.11, Wave 4, uncommitted) are out of scope; if ever built they would replace or supplement `npc_lineup`. | Producer | Wave 4 |
