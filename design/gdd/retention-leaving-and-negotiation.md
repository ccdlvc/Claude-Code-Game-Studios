# Retention, Leaving and Negotiation

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run, decisions logged)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet); serves GDD §1 "keeping them" and §6.8

## Summary

Retention gives every guild member two moods the player can read: a fast **mood** that reacts to tax, food, taverns, parties, friends, injuries and pay, and a slow **loyalty** that follows mood over days. When loyalty sinks, a member asks to leave and names one condition for staying (a raise, a specific item, a building, a hunting ground); the player accepts, counter-offers with a smaller raise, or lets them go, and the game decides the outcome deterministically. It exists so that the roster is a cast of people who must be kept, not units that stay forever, and so that tax, salary and buildings have a human cost the player can see.

> **Quick reference** — Layer: `Feature` · Priority: `Vertical Slice` · Key deps: `Deterministic RNG, Member model, CA/PA and traits, Gold economy, Party (PROVISIONAL), Member state machine (PROVISIONAL), Guild and buildings, Items and loot, Event bus, Command layer, Sim core`

## Overview

Retention is a rules module inside the headless simulation. It owns three fields that the Member model stores for every disciple, `mood`, `loyalty` and `contract{salary, demands[]}`, plus the guild's **bonds** (how close two members have grown by hunting together) and the **leave requests** that are open at any moment. Once per game hour it moves each member's mood toward a target built from the guild's situation (tax rate, Tửu Lâu level, party membership, closest friend, salary, unmet needs, rank in the roster) and moves loyalty a little way toward mood. Once per game day it checks each member's loyalty against a threshold shifted by their traits; below it, or by a seeded chance just above it, the member files a request to leave with one stay condition. The request runs a small negotiation (GDD §6.8): the player meets the condition, makes one counter-offer whose success chance depends on traits, loyalty and how much they offer, or lets the member go. A request the player ignores resolves on its own: the member either takes a short recuperation break (the locked decision "bình thường chỉ bị thương → dưỡng sức", GDD §2) or leaves. A leaving member's wallet is burned, their record is handed to Jianghu free agents (17), and their close friends lose mood (§6.8 "phản ứng dây chuyền nhẹ"). The player meets this system directly on the member panel (mood and loyalty with their causes) and on the leave-request card; indirectly it is the reason tax, salaries and the Tửu Lâu matter. Without it, nobody ever leaves, the tax slider has no downside, and the people pipeline (Recruitment 15 → Retention 16 → Jianghu 17) has no middle.

## Player Fantasy

**"They stay because of how I run the guild."** The bang chủ opens a member who has been quiet for a week and sees why: loyalty 34, mood falling, *Tax −10, no friends in the guild, Proud: ranked low*. The next morning the request arrives: Lý Thanh wants a raise of 60,000 a day or he walks. The player knows him. He is Proud, so a lowball will probably fail; the fund can afford it, but the tax that pays for it came out of everyone else's pockets. They counter at 80%, the dice say no, and they pay the full raise rather than lose their only tank. A month later, when his closest hunting partner is dismissed, Lý Thanh's mood drops and the player understands that too.

The feeling the system serves is the tycoon's: **people, not numbers** (CA/PA Player Fantasy), managed through readable trade-offs. Every change in mood has a named cause on screen, every request names one concrete thing that would fix it, and every outcome is decided by visible rules and a fixed die, never by a hidden streak (RNG R10). Losing a member hurts, but it is never a surprise and never a punishment for being away: requests cannot expire while the game is closed.

*Lens applied (creative-director, no agent spawned):* the three candidate framings were "the fair employer" (above), "the drama of the roster" (members as soap opera) and "the ruthless optimiser" (members as assets to be replaced). The fair-employer framing was chosen (autonomous, recommended) because it matches GDD §2's locked decision that leaving is conditional and negotiable, and CA/PA's "people, not numbers". The ruthless framing is still playable (dismiss, let go) but is not what the rules reward: chain reactions and the wallet burn make churn costly.

## Detailed Design

*Specialist lenses applied (no agents spawned; routing: Gameplay → Character systems row, union with Economy for the salary loop).* **game-designer:** the player's decisions are tax rate, salary, which buildings to raise, who hunts with whom, and the three answers to a request; the player cannot set mood or loyalty directly, cannot stop a member asking, and cannot make a counter-offer twice. The request must name exactly one fixable thing, or it reads as noise. **systems-designer:** two state variables at two time scales (mood hours, loyalty days) make causes legible and smooth out tax-slider spam; every random outcome is a single seeded draw with a stated key; the hard threshold alone would give "nobody leaves" or "everyone leaves", so a seeded soft band above it carries the 3–10%/month target (GDD §20 S2). **economy-designer:** salary is a fund → wallet transfer (Gold economy R8), so a raise feeds the shop burn rather than minting; the departing wallet is burned, never paid to the fund, so driving members out is never profitable (Gold economy R11). **narrative-director:** the leave card and the chronicle need the cause and the condition as IDs so the AI text layer (36) can phrase them without deciding anything (GDD §9 "kết quả do game quyết"). **art-director:** mood and loyalty need an icon and a number, never colour alone. No disagreement between lenses needed a decision beyond those logged.

### Core Rules

All values are integers. Mood, loyalty and bond are stored in thousandths of a point (`_milli`, 0 – 100,000 for 0 – 100 points); probabilities and fractions are parts per million (`_ppm`). This document writes them in points and percent for readability. Rounding is round-half-away-from-zero unless a formula says floor.

**R1 — Fields and ownership.** For every disciple on the roster this system is the only writer of `mood`, `loyalty` and `contract{salary, demands[]}` (Member model field table). It initialises them when the Member model asks during creation (Member model R8 step 3): `mood = mood_join`, `loyalty = loyalty_join`, `contract.salary` = the amount the recruit was hired at (Recruitment 15 passes it, 0 by default), `demands = []`. A returning member (origin `returned`) starts at `loyalty_join + 100 × loyalty_gain_return` (trait key, `t_nostalgic` +20), clamped to 100. Elders (`rank = elder`, Rebirth 23) are exempt from every rule below: their mood and loyalty are frozen and they never file a request (OQ-9).

**R2 — Hourly update (P5).** The system registers one P5 handler (`retention`, order 1600) with two anchored deadline ticks (Sim core R5): `hour_due_tick` every 3,600 s of game time and `day_due_tick` every 86,400 s, both anchored at guild creation. At each hour slot, for every on-roster disciple in ascending `member_id`:
1. Compute the mood target T (F1) from the current inputs.
2. Move mood toward T (F2).
3. Move loyalty toward mood (F3).
4. Update bonds for every pair of members who shared a party during the hour (F8, R9).
5. If mood crossed below `mood_alert_low` or back above it, emit `mood_alert` (1607).
6. Check open requests' deadlines (R6).

**R3 — Event bumps (P6 subscriber).** Some causes are moments, not conditions. The system subscribes to the Event bus (one subscriber, `retention`) and applies these mood bumps to the subject member, clamped 0 – 100, in the tick they are delivered:

| Source event | Bump | Rule |
|---|---|---|
| `hunt_member_downed` (1103, Zones and hunt) | `bump_downed` (−6) | Once per downing |
| Entering `injured` (Member state machine 41, PROVISIONAL) | `bump_injured` (−6) | Not for Retention's own recuperation (R7) |
| `item_awarded` (2603, Items and loot) | `bump_award × max(0, 1 − loot_share_demand)` (+4) | At most once per `award_cooldown_h` (6 h) per member |
| `salary_unpaid` (2707, Gold economy) | `bump_unpaid` (−10) | Also sets `unpaid_streak`, see F1 |
| `member_leaving` (1604, this system) for a bonded member | `−chain_coef × bond / 100`, × `dismiss_chain_mult` if dismissed | R8 chain reaction |
| A salary cut (R10) | F7 | Applied by the command, not the bus |
| Food eaten (Items and loot / Member state machine) | the food's `mood` value in `items.csv` | PROVISIONAL: the eater's system calls `add_mood(member_id, points_milli)` |

Bumps are the only writes outside the hourly update. `add_mood` is the single API other systems use; it refuses negative bumps from callers other than this system's table above.

**R4 — Daily leave check (P5).** At each day slot, after the hour slot of the same tick, for every on-roster disciple in ascending `member_id`, a member is **eligible** if all hold: they joined at least `leave_grace_days` (2) ago; they have no open request; they are not recuperating; their request cooldown has passed; and the guild has fewer than `leave_open_max` (3) open requests. An eligible member files a request (R5) if loyalty < θ (F4, no draw), or with chance F4 if θ ≤ loyalty < θ + `leave_soft_band` (one RNG draw, R12). A member not checked because `leave_open_max` was reached is simply checked again the next day.

**R5 — Filing a request.** The request gets a **demand**, one stay condition chosen by a weighted draw (F6) among the kinds currently possible:

| Kind | Condition | How it is met |
|---|---|---|
| 1 `salary` | A raise of R gold per day (F5) | `answer_leave_request(accept)`: `contract.salary += R` at once |
| 2 `item` | One named equipment row: awardable to this member, `level_req` ≤ member level, in the slot whose equipped item has the lowest `level_req` (empty first), highest `level_req` such row, ties lowest `uid` | The player awards any unit of that row, or a row of the same slot with higher `level_req`, through `award_item` (Items R8). The `item_awarded` event meets the demand; no accept command is needed |
| 3 `building` | The next level of one building from `retention_demand_buildings` (`bld_tavern; bld_inn; bld_restaurant; bld_housing`) that can be built now (Guild and buildings rules); the lowest-level one, ties in list order | `build_queued` or `build_started` (3001/3002) for that building at ≥ the target level **pledges** the guild (state `Pledged`); `build_completed` (3003) meets it |
| 4 `ground` | A hunting ground: the live ground whose level range contains the member's level and whose dominant element is countered by the member's element, highest level, ties lowest `uid` (Zones and hunt) | `answer_leave_request(accept)`: a `{ground, uid, until}` entry is added to `contract.demands[]` for `ground_pledge_days` (7); Utility AI sends the member there when they hunt (PROVISIONAL, Utility AI 12) |

`salary` is possible unless the member's salary is already at the ceiling (`salary_max_pct × D`). A kind with no valid target has weight 0; if all four are 0, no request is filed (Edge Cases). The request opens with `deadline = now + leave_request_window_h` (24 h), the reference raise R is recorded on it (it is the yardstick of every counter-offer, F5, F6), and `leave_requested` (1601) is emitted. The player is told by the event; no answer is forced.

**R6 — Answering.** One command, `answer_leave_request(member, choice, amount)` (1601), applied in P1:
- **Accept** (`choice = 1`). For `salary` and `ground`: the condition is applied, the request closes as **Stayed**: loyalty += `stay_loyalty_bonus` (10), mood += `stay_mood_bonus` (5), cooldown `request_cooldown_days` (7). For `item` and `building`: refused with `demand_unmet` (4) unless the condition is already met, since meeting it closes the request by itself.
- **Counter** (`choice = 2`, `amount` = offered raise in gold per day, 0 ≤ amount < R). Allowed once per request (`counter_max` = 1). One draw (R12) with chance F6. Success: `contract.salary += amount`, request closes as **Stayed** with `counter_loyalty_bonus` (6) and `counter_mood_bonus` (2). Failure: mood −`counter_fail_mood` (5); the request stays open with the same demand and deadline; Accept and Let go remain.
- **Let go** (`choice = 3`). The member leaves (R8), reason `let_go`. No draw.
- The outcome is emitted as `leave_request_answered` (1602).
- **Deadline.** At the first hour slot at or after `deadline` with the request still open (or `Pledged` past `pledge_max_h` without completion), the request **times out**: one draw (R12) with chance F7 decides **Recuperate** (R7) or **Leave** (R8, reason `timeout`). A member who recuperated within the last `recup_cooldown_days` (30) leaves without a draw.
- **Offline.** A deadline cannot pass during an offline gap. When Offline progress (31) hands control back, every open request's deadline becomes `max(deadline, return_tick + leave_request_window_h × 3600 × tick_rate)`. Requests filed during the gap are listed in the away report.

**R7 — Recuperate (dưỡng sức).** The member stays on the roster. The system asks the Member state machine (41) to place them in `injured` with reason `recuperate` for `recup_days` (2) of game time (PROVISIONAL). When the break ends: loyalty = max(loyalty, θ + `recup_loyalty_margin` (10)), mood = max(mood, `mood_base`), the request closes, cooldown `request_cooldown_days` starts. `member_recuperating` (1603) is emitted when it starts. No chain reaction, no wallet change.

**R8 — Leaving.** For `let_go`, `timeout`, and `dismissed` (R10), in this order:
1. Tick N: emit `member_leaving` (1604) with the reason and final loyalty. CA/PA (9) reveals an `event:leave_guild` trait on it while the member is still on the roster (CA/PA Edge Cases). Apply the chain reaction: every on-roster member with bond ≥ `bond_chain_min` (20) to the leaver takes R3's chain bump. Close any request.
2. Request the Member state machine (41) to move the member to `away` (sim command, next tick). If the member is in a hunt trip, the move waits for the trip to close (Zones and hunt Edge Cases); if in a raid, for the raid to end.
3. When the member is in `away` (state event from 41, PROVISIONAL): burn the wallet through Gold economy as `member_departed` (Gold economy R11); compute `return_chance` (F9); hand the record snapshot plus `{departed_tick, reason, final_loyalty, wallet_burned, return_chance}` to Jianghu free agents (17) (discarded while 17 is not built); delete the member's bonds; call Member model `remove_member(member_id, reason)` (Member model R9).
Step 3 is always at least one tick after step 1, so the trait reveal lands while the member is still a guild member.

**R9 — Bonds.** A bond is a value 0 – 100 for an unordered pair of on-roster disciples, stored only while above 0. Each hour, for every pair who were in the same party at the hour slot (Party 13 membership, PROVISIONAL), the bond grows by F8; a pair whose traits conflict (one member holds a trait listed in the other's trait `conflicts` column in `traits.csv`) loses `bond_clash_rate` instead (§6.12 "đội xung đột trait thì giảm"). Every other stored pair decays by `bond_decay`. At most `bond_slots × roster / 2` pairs are kept (`bond_slots` = 5): when a new pair would exceed it, the lowest stored pair is dropped, ties by lowest `(lo_id, hi_id)`. When a bond first reaches `bond_friend_threshold` (60), `bond_formed` (1606) is emitted. A member's **top bond** (their highest pair) feeds F1.

**R10 — Contract commands.**
- `offer_contract(member, salary)` (1602) sets `contract.salary` outside a request: 0 ≤ salary ≤ `salary_max_pct` × D (F5). Refused while the member has an open request (`open_request`, 102, use `answer_leave_request`) or within `salary_change_cooldown_h` (24) of the last change (`cooldown`, 103). A raise needs no consent and takes effect from the next salary slot (Gold economy R8). A cut applies at once and costs mood F7-cut.
- `dismiss_member(member)` (1603) makes a disciple leave at once (R8, reason `dismissed`), with chain bumps × `dismiss_chain_mult` (1.5). Refused for elders (`elder`, 104). *(Codes renumbered by consistency-check 2026-11-16: 1, 7, 8 and 9 are Command layer envelope/shared codes with other meanings, Command layer R6.)*
- Every accepted salary change emits `contract_changed` (1605).

**R11 — Salary payment.** Gold economy pays `contract.salary` daily (its R8.2). This system reads `salary_unpaid` (2707): R3's bump, and `unpaid_streak` counts consecutive unpaid day slots (reset by a paid day, known from the absence of 2707 at the slot; PROVISIONAL, Gold economy emits nothing on success: this system compares the day slot with the last 2707 tick). While `unpaid_streak > 0`, F1's salary term is 0.

**R12 — Randomness.** All draws use RNG domain 12 (`retention`). Event key: `[member_id, joined_tick, retention_ordinal]`, where `retention_ordinal` is a per-member counter, saved, starting at 0 at each join and incremented once per random event. `member_id` is never reused (Member model R2) and `joined_tick` differs per stint, so keys are unique across leaving and returning (RNG R6). No key component is player-mutable: the player cannot re-roll a counter-offer by reloading or by doing something else first; reloading and offering more applies the same die to a better chance (RNG Edge Cases, save-scumming). Draw order, one draw per event:
- soft-band leave check: `chance_ppm(F4)`;
- demand pick: `randint(0, W − 1)` over the cumulative weights of F6 in kind order 1 – 4;
- counter-offer: `chance_ppm(F6)`;
- timeout: `chance_ppm(F7)` for Recuperate.

**R13 — Save.** The Member model record stores `mood`, `loyalty` and `contract`. This system registers its own save section (Local save R5): open requests, bonds, per-member `retention_ordinal`, cooldown and recuperation ticks, `unpaid_streak`, last award-bump tick, `hour_due_tick`, `day_due_tick`.

### States and Transitions

Per-member retention state (a member is in exactly one):

| State | Meaning | Leaves to |
|---|---|---|
| `Grace` | Joined less than `leave_grace_days` ago | `Settled` when the grace ends |
| `Settled` | Normal; daily check runs (R4) | `Requesting` on filing |
| `Requesting` | One request open (`Open` or `Pledged`, below) | `Cooldown` (Stayed), `Recuperating`, `Departing` |
| `Recuperating` | In `injured/recuperate` for `recup_days` (R7) | `Cooldown` when the break ends |
| `Cooldown` | No check until `request_cooldown_days` after the last request closed | `Settled` |
| `Departing` | `member_leaving` emitted; waiting for `away` (R8) | `Gone` after `remove_member` |
| `Gone` | Off the roster; only Jianghu (17) holds them | `Grace` if they rejoin (origin `returned`) |
| `Exempt` | Elder; frozen | — |

Request states:

| State | Entered by | Exits |
|---|---|---|
| `Open` | Filing (R5); a cancelled pledge (`build_cancelled` 3005) reopens it with `deadline = now + window` | Accept (salary/ground) or demand met → `Stayed`; Counter success → `Stayed`; Counter fail → `Open` (counter used); `building` queued → `Pledged`; Let go → `Left`; deadline → `Recuperated` or `Left` |
| `Pledged` | Building demand queued or started | `build_completed` → `Stayed`; cancelled → `Open`; `pledge_max_h` (72) passed → timeout draw |
| `Stayed`, `Recuperated`, `Left` | Terminal; the request record is deleted after its event | — |

Dismissal can happen from any member state except `Departing`, `Gone` and `Exempt`; it closes an open request as `Left`.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|---|---|---|---|---|
| Sim core (1) | core → this | P5 handler (order 1600), P1 appliers, `ctx.derive`, `ctx.emit`, `ctx.submit` | — | Sim core |
| Deterministic RNG (2) | this → RNG | Domain 12, key R12 | Draws | RNG |
| Data layer (3) | data → this | `config.csv` keys (Tuning Knobs), `traits.csv` conflicts, `items.csv` mood/slot/level, building effects | — | Data layer |
| Command layer (5) | both | Commands 1601–1603 | Reason codes | Command layer frames; this system validates and applies |
| Member model (8) | both | Roster, level, `rank`, `joined_tick`, `origin`, equipment | Writes `mood`, `loyalty`, `contract`; calls `remove_member` | Member model stores; this system writes |
| CA/PA and traits (9) | 9 → this | `trait_mod_ppm` for `loyalty_decay`, `leave_threshold`, `salary_demand`, `loot_share_demand`, `negotiation_success`, `mood_gain_party`, `mood_loss_low_rank`, `bond_gain`, `return_chance`, `loyalty_gain_return`; CA for rank | `member_leaving` (1604) for the leave reveal | This system owns the meaning of those keys (CA/PA Interactions table) |
| Party (13) | 13 → this | Party membership at each hour slot (PROVISIONAL) | Bonds, for Party's own "quan hệ" score if it wants them | Party owns membership |
| Member state machine (41) | both | `injured` entry, `away` reached, `satiety`, `stamina` (PROVISIONAL) | Requests: `injured/recuperate` for a duration, `away` | 41 owns states |
| Zones and hunt (11) | 11 → this | 1103 downed | — | Zones |
| Items and loot (26) | 26 → this | 2603 awards; item rows for item demands | — | Items owns awards |
| Gold economy (27) | both | `tax_ppm`, 2707 `salary_unpaid` | `contract.salary`; `member_departed` burn; `member_returned` mint on return | Gold owns the ledger; this system owns the amounts |
| Guild and buildings (30) | 30 → this | `effect(bld_tavern, mood_gain)` (with its arrears fade), 3001/3002/3003/3005 | — | Buildings |
| Utility AI (12) | this → 12 | `contract.demands[]` ground entries (PROVISIONAL) | — | Utility AI honours |
| Recruitment (15) | 15 → this | Initial salary at hire | — | Recruitment |
| Jianghu (17) | this → 17 | — | Departure snapshot, `return_chance` (F9); rejoin initialisation (R1) | Jianghu owns free agents and returns |
| Offline progress (31) | 31 → this | `settle_retention(to_tick, slice_inputs)` per slice; return tick (R6) | — | Offline owns the gap |
| Event bus (42) | both | Subscribed types above | Types 1601–1608 (F10) | Event bus |
| Local save (6) | this → 6 | — | Section R13 | Local save |
| Guild screens (39), AI text (36), Quests (25), Analytics (37) | this → them | — | Events and read API `retention_view(member_id)` (mood, loyalty, T's terms, open request) | Readers only |

## Formulas

Shared variables: `D = income_ref_per_level × max(1, level) × 24`, the reference daily income of a member (gold/day; Gold economy's `income_ref_per_level` = 1000). `trait(k)` = `trait_mod_ppm(member, k) / 1e6` (CA/PA). θ is F4's threshold.

*Lens applied (systems-designer, no agent spawned):* every formula below was evaluated at its minimum, maximum and zero inputs; the boundary results are stated under each. Feedback loops: (1) low mood → leave → chain bump → lower mood among friends is a positive loop, damped because the chain bump is one-off and capped by bond (≤ 15 points, ≤ 22.5 dismissed) and requests are capped at 3 open; (2) salary raises feed wallets that are spent in guild shops, 30% back to the fund (Gold R7), a weak intended negative loop on fund cost.

### F1 — `mood_target`

The mood_target formula is defined as:

`T = clamp(mood_base + tavern + party + bond + salary_term − tax_term − needs_term − rank_term, 0, 100)`

where
`tavern = 100 × effect(bld_tavern, mood_gain)`,
`party = 100 × max(0, mood_party_base + trait(mood_gain_party))` if in a party at the slot, else 0,
`bond = bond_mood_max × top_bond / 100`,
`salary_term = min(sal_mood_cap, sal_mood_coef × salary / (D × max(0.5, 1 + trait(salary_demand))))`, 0 while `unpaid_streak > 0`,
`tax_term = tax_mood_coef × max(0, tax_ppm − tax_mood_free_ppm) / 10,000` (Vertical Slice, with the tax slider: user decision 2026-11-16 makes MVP's tax a flat fixed rate with **no** mood effect; this system and the slider, `economy_tax_slider_live`, arrive together, so `tax_term` is never computed in MVP),
`needs_term = needs_pen × [satiety < needs_low] + needs_pen × [stamina < needs_low]`,
`rank_term = low_rank_pen × max(0, 1 + trait(mood_loss_low_rank))` if roster ≥ `low_rank_min_roster` and the member's CA rank is in the bottom `low_rank_frac` of the roster, else 0.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| mood_base | int (points) | 30 – 70 | data file (`config.csv`) | Neutral mood, default 50 |
| effect(bld_tavern, mood_gain) | fraction | 0 – 0.16 | data file (`buildings.csv`, via Guild and buildings) | Tửu Lâu level effect after its arrears fade; 0 when unbuilt |
| mood_party_base | fraction | 0 – 0.10 | data file | Mood points (÷100) for being in a party, default 0.03 |
| trait(mood_gain_party) | fraction | 0 – 0.10 | calculated (traits) | `t_generous`, `t_social`, `t_team_player` +0.05 each |
| bond_mood_max | int (points) | 0 – 10 | data file | Mood from a top bond of 100, default 6 |
| top_bond | int | 0 – 100 | calculated (R9) | Member's highest bond |
| salary | int (gold/day) | 0 – 0.5·D | calculated (`contract.salary`) | Contracted salary |
| sal_mood_coef | int | 0 – 300 | data file | Points per unit of salary/D, default 100 |
| sal_mood_cap | int (points) | 0 – 20 | data file | Cap on the salary term, default 12 |
| trait(salary_demand) | fraction | −0.1 – +0.25 | calculated (traits) | `t_greedy` +0.15, `t_ambitious` +0.10, `t_generous` −0.10 |
| tax_ppm | int | 0 – 200,000 | calculated (Gold economy R6) | Current tax rate: the player's slider from Vertical Slice; on an MVP save it starts at the flat `guild_tax_pct` (100,000) |
| tax_mood_free_ppm | int | 0 – 200,000 | data file | Tax members accept without complaint, default 50,000 (5%) |
| tax_mood_coef | float (points per pp) | 0 – 3 | data file | Default 1.0 |
| satiety, stamina | int | 0 – 100 | calculated (Member state machine 41, PROVISIONAL) | Needs |
| needs_low | int | 0 – 100 | data file | Default 30 |
| needs_pen | int (points) | 0 – 20 | data file | Default 8 each |
| low_rank_pen | int (points) | 0 – 15 | data file | Default 5 |
| trait(mood_loss_low_rank) | fraction | 0 – 0.2 | calculated (traits) | `t_proud` +0.2 |
| low_rank_frac | ppm | 0 – 500,000 | data file | Default 333,333 (bottom third by CA, ties by higher `member_id` lower) |
| low_rank_min_roster | int | 3 – 20 | data file | Default 6 |

**Output Range:** 0 to 100 by the clamp. Unclamped extremes: best case 50 + 16 + 13 + 6 + 12 = 97; worst case 50 − 15 − 16 − 6 = 13. The clamp is therefore never reached at default knobs; it guards knob edits. At zero salary the salary term is 0; at D's floor (level 0 treated as 1) D = 24,000 and the term stays capped. `max(0.5, …)` keeps the denominator positive whatever traits sum to.
**Example:** level 50, tax 10%, Tửu Lâu level 2 (0.04), in a party, top bond 40, salary 0, fed and rested, mid-ranked: T = 50 + 4 + 3 + 2.4 + 0 − 5 = 54.4. With a raise of 60,000/day (5% of D = 1,200,000): +5 → 59.4.

### F2 — `mood_step`

The mood_step formula is defined as:

`M' = clamp(M + trunc((T − M) × mood_relax_ppm / 1e6), 0, 100)` (in milli-points, hourly)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| M | int (milli) | 0 – 100,000 | calculated | Current mood |
| T | int (milli) | 0 – 100,000 | calculated (F1) | Target |
| mood_relax_ppm | int | 10,000 – 1,000,000 | data file | Share of the gap closed per hour, default 200,000 (half-life ≈ 3.1 h) |

**Output Range:** M' lies between M and T, so it never overshoots. At `mood_relax_ppm = 1e6`, M jumps to T (bumps then last under an hour). `trunc` toward zero leaves a residual gap below 5 milli-points (0.005) at the default, invisible on screen. At 0 the gap stays; the validator forbids values below 10,000.
**Example:** M = 40, T = 54.4: M' = 40 + 2.88 = 42.88.

### F3 — `loyalty_step`

The loyalty_step formula is defined as:

`L' = clamp(L + trunc((M − L) × loyalty_relax_ppm × k / 1e6), 0, 100)`, `k = max(0.1, 1 + trait(loyalty_decay))` when M < L, else `k = 1`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L | int (milli) | 0 – 100,000 | calculated | Current loyalty |
| M | int (milli) | 0 – 100,000 | calculated (after F2) | Mood this hour |
| loyalty_relax_ppm | int | 1,000 – 100,000 | data file | Default 15,000 (half-life ≈ 46 h) |
| trait(loyalty_decay) | fraction | −0.4 – 0 | calculated (traits) | `t_loyal` −0.3, `t_stubborn` −0.1 |

**Output Range:** L' lies between L and M. Loyalty is a slow average of mood; one-off bonuses (stay, return) fade back toward mood over days: kindness bought with a raise lasts only if the raise also lifts mood. `k` floor 0.1 keeps a member with stacked loyalty traits from becoming immovable. At M = L nothing moves.
**Example:** L = 60, M = 30, `t_loyal`: k = 0.7, ΔL = −30 × 0.015 × 0.7 = −0.315 per hour (≈ −7.6 on the first day, shrinking as the gap closes).

### F4 — `leave_threshold` and `soft_leave_chance`

The leave_threshold formula is defined as:

`θ = clamp(leave_threshold_base + trait(leave_threshold) × 1, θ_min, θ_max)` (trait values are in points)

`p_soft = leave_soft_max_ppm × (θ + leave_soft_band − L) / leave_soft_band` for θ ≤ L < θ + band; 1,000,000 (certain, no draw) for L < θ; 0 otherwise.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| leave_threshold_base | int (points) | 10 – 50 | data file | Default 30 |
| trait(leave_threshold) | int (points) | −15 – +25 | calculated (traits) | `t_loyal` −15, `t_ambitious` +10, `t_wanderer` +15 |
| θ_min, θ_max | int | 5, 80 | data file | Clamp |
| leave_soft_band | int (points) | 1 – 30 | data file | Default 15 |
| leave_soft_max_ppm | int | 0 – 100,000 | data file | Daily chance at the bottom of the band, default 20,000 (2%) |
| L | int (milli) | 0 – 100,000 | calculated | Loyalty at the day slot |

**Output Range:** p_soft 0 to `leave_soft_max_ppm` inside the band, linear. `leave_soft_band` ≥ 1 avoids the division by 0. At `leave_soft_max_ppm = 0` only the hard threshold acts.
**Example:** θ = 30, L = 40: p = 20,000 × 5/15 = 6,667 ppm (0.67%/day). A `t_wanderer` (θ = 45) at L = 54.4 is inside their band: p = 20,000 × 5.6/15 = 7,467 ppm.

### F5 — `reference_raise`

The reference_raise formula is defined as:

`R = ceil_to(D × raise_pct_ppm / 1e6 × max(0.5, 1 + trait(salary_demand)), raise_round)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| D | int (gold/day) | 24,000 – 4,800,000 | calculated | `income_ref_per_level × max(1, level) × 24`, levels 1 – 200 |
| raise_pct_ppm | int | 10,000 – 200,000 | data file | Default 50,000 (5% of daily income) |
| raise_round | int (gold) | 1 – 1,000 | data file | Default 10 |
| salary_max_pct | ppm | 100,000 – 1,000,000 | data file | Salary ceiling as a share of D, default 500,000 (R10); an accepted raise is capped so the salary stays ≤ the ceiling |

**Output Range:** 1,200 gold/day (level 1) to 300,000 (level 200 with `t_greedy` and `t_ambitious`, ×1.25); 276,000 for a greedy level-200 member. Never 0 because D ≥ 24,000 and the factor ≥ 0.5. Against the fund: at the default tax of 10% a member pays the fund about 0.1·D a day, so one accepted raise costs half of that member's tax; this is the intended trade-off (Gold economy F1, R6).
**Example:** level 50: D = 1,200,000; R = 60,000/day; greedy: 69,000.

### F6 — `demand_weights` and `counter_success`

The demand_weights formula is defined as:

`w_salary = w_base_salary × (1 + trait(salary_demand))`, `w_item = w_base_item × (1 + trait(loot_share_demand))`, `w_building = w_base_building`, `w_ground = w_base_ground × (1 + [has t_ambitious])`; a kind with no valid target (R5) has weight 0; W = Σw (integers, ×1000).

The counter_success formula is defined as:

`p_counter = clamp(neg_base + neg_loyalty_coef × (L − θ) / 100 − neg_shortfall_coef × (1 − amount / R) + trait(negotiation_success), neg_min, neg_max)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| w_base_* | int | 0 – 100 | data file | Defaults salary 40, item 25, building 15, ground 20 |
| trait(loot_share_demand) | fraction | 0 – 0.1 | calculated | `t_greedy` +0.1 |
| neg_base | ppm | 0 – 1,000,000 | data file | Default 550,000 |
| neg_loyalty_coef | float | 0 – 3 | data file | Default 1.0 |
| neg_shortfall_coef | float | 0 – 3 | data file | Default 1.5 |
| amount | int (gold/day) | 0 – R − 1 | command arg | Offered raise |
| R | int | F5 | calculated (recorded at filing) | Reference raise |
| trait(negotiation_success) | fraction | −0.25 – +0.2 | calculated | `t_humble` +0.1, `t_haggler` +0.1, `t_proud` −0.1, `t_stubborn` −0.15 (positive = easier for the guild, OQ-6) |
| neg_min, neg_max | ppm | 0 – 1,000,000 | data file | Defaults 20,000 and 900,000 |

**Output Range:** W ≥ `w_base_salary` > 0 whenever the member is below the salary ceiling (the validator requires `w_base_salary ≥ 1`); W = 0 only in the ceiling case, where no request is filed and nothing is drawn. p_counter from 2% (an offer of 0, a "please stay") to 90%; never certain, never impossible. More money always helps: p is non-decreasing in `amount`.
**Example:** L = 38, θ = 30, offer 80% of R, `t_humble`: 0.55 + 0.08 − 0.30 + 0.10 = 0.43. Same member `t_proud` instead: 0.23.

### F7 — `recuperate_chance` and `salary_cut_bump`

The recuperate_chance formula is defined as:

`p_recup = clamp(recup_base + recup_loyalty_coef × (L − θ) / 100, recup_min, recup_max)`

The salary_cut_bump formula is defined as:

`bump_cut = −min(cut_bump_cap, cut_bump_coef × (old − new) / D)` (points)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| recup_base | ppm | 0 – 1,000,000 | data file | Default 500,000 |
| recup_loyalty_coef | float | 0 – 5 | data file | Default 2.0 |
| recup_min, recup_max | ppm | | data file | Defaults 100,000 and 900,000 |
| cut_bump_coef | int | 0 – 500 | data file | Default 200 |
| cut_bump_cap | int (points) | 0 – 40 | data file | Default 20 |
| old, new | int (gold/day) | 0 – 0.5·D | calculated | Salary before and after |

**Output Range:** p_recup 10% – 90%. bump_cut 0 (no cut) to −20; a cut of the whole 5% raise costs −10.
**Example:** L = 28, θ = 30: p_recup = 0.5 − 0.04 = 0.46.

### F8 — `bond_step`

The bond_step formula is defined as:

`b' = clamp(b + bond_rate × max(0, 1 + trait_a(bond_gain) + trait_b(bond_gain)), 0, 100)` for a party pair without conflict; `b − bond_clash_rate` for a conflicting party pair; `b − bond_decay` otherwise (hourly)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| bond_rate | float (points/h) | 0 – 2 | data file | Default 0.5 (≈ 8 days of shared hunting to 100) |
| trait(bond_gain) | fraction | −0.2 – +0.2 | calculated | `t_social` +0.2, `t_humble` +0.1, `t_loner` −0.2 |
| bond_clash_rate | float (points/h) | 0 – 2 | data file | Default 0.5 |
| bond_decay | float (points/h) | 0 – 0.5 | data file | Default 0.02 (≈ 0.5/day) |

**Output Range:** 0 – 100 by clamp. Two `t_loner`s gain at 0.3/h; the `max(0, …)` floor means stacked negatives never turn growth into loss. A pair that reaches 0 is deleted.
**Example:** `t_social` with a plain member: +0.6/h; 100 hours together → 60, `bond_formed`.

### F9 — `return_chance`

The return_chance formula is defined as:

`return_chance = clamp(return_base + trait(return_chance) + return_loyalty_coef × final_loyalty / 100, 0, 1)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| return_base | ppm | 0 – 500,000 | data file | Default 100,000 |
| trait(return_chance) | fraction | 0 – 0.45 | calculated | `t_nostalgic` +0.3, `t_wanderer` +0.15 |
| return_loyalty_coef | float | 0 – 1 | data file | Default 0.2 |
| final_loyalty | int (points) | 0 – 100 | calculated | Loyalty when leaving |

**Output Range:** 0.1 – 0.75 at defaults. It is an input for Jianghu (17), which owns the return event; this system does not draw it.
**Example:** final loyalty 30, `t_nostalgic`: 0.1 + 0.3 + 0.06 = 0.46.

### F10 — event volume and the leave-rate target

Event volume (Event bus F1, F4): `ring_per_day` peaks at the 80-member fixture: 1602 `leave_request_answered` 12 (at most 3 open requests and 2 answers each, refilled daily, ×2 margin); 1603 `member_recuperating` 3; 1605 `contract_changed` 80 (one change per member per 24 h, R10); 1606 `bond_formed` 8. 1601 and 1604 are milestones (subject slot 1, `ring_per_day` 0); their count is bounded by `leave_open_max` per day. 1607 and 1608 are not logged.

The leave-rate identity used by the balance simulator:

`leave_rate_month ≈ (30 / N) × Σ_i p_request_i × P(leave | request)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| N | int | 12 – 80 | calculated | Disciples on the roster |
| p_request_i | float | 0 – 1 | calculated (F4) | Member i's daily request chance |
| P(leave \| request) | float | 0 – 1 | calculated (policy, F6, F7) | Share of requests that end in leaving under the simulated player policy |

**Output Range:** the target is 0.03 – 0.10 per month with the standard configuration and the standard policy (GDD §20 S2; Member model's `leave_rate`). It is a calibration target measured by Dev tooling (43), not a value the game computes at run time.
**Example:** 20 members, 3 inside their soft band at an average 0.5%/day (Σ p = 0.015), policy losing 40% of requests: 30 × 0.015 × 0.4 / 20 = 0.9% a month. That is below target, so the knobs (`leave_soft_max_ppm`, `tax_mood_free_ppm`) are tuned until the measured rate enters 3–10%. Hard-threshold requests (events, unpaid salary, wanderers) add to this and are only measurable in the simulator.

## Edge Cases

*Lens applied (systems-designer, Section E checks on C and D as written).*

**Requests**
- **If a member qualifies for a request on the same day slot as `leave_open_max` is reached**: members are taken in ascending `member_id`; the rest are checked again next day. Older members therefore ask first. Accepted for determinism.
- **If the item demand's row is awarded to another member first**: the demand stays; any unit of that row or a same-slot row with higher `level_req` still meets it. If no such row exists in the game any more (content removed by a migration), the demand is re-picked at the next hour slot without a draw: it becomes `salary` with the recorded R.
- **If a building demand's target becomes unbuildable** (built to that level by another path): the request is met (`Stayed`) at the next hour slot, because the condition is true.
- **If the pledged build is cancelled and re-queued repeatedly**: each cancel reopens the request with a fresh window, but `pledge_max_h` is measured from the first pledge, so the guild cannot stall forever.
- **If the player accepts a salary demand that would exceed `salary_max_pct × D`**: the raise is capped at the ceiling and the request still closes as Stayed. A member at the ceiling gets `salary` weight 0 (R5); if every kind has weight 0 the member files no request and is set to `Cooldown` (a member who can be given nothing more is not asked to want it).
- **If a counter amount ≥ R or < 0 is sent**: refused `bad_amount` (5). An equal offer is an Accept and must be sent as one.
- **If the player answers a request whose member is in a hunt trip**: allowed. Accept and counter apply at once; a departure waits for the trip to close (R8).
- **If a member levels up while a request is open**: R is fixed at filing; the demand does not grow.

**Leaving**
- **If two departures happen in one tick**: processed in ascending `member_id`; each chain reaction uses bonds as they stand after the previous leaver's bonds were deleted. The second leaver's friends are not hit by the first's chain twice.
- **If a member is dismissed while `Departing`**: refused (`not_member`, 101), they are already leaving.
- **If `remove_member` is refused** (`MM_STATE_BLOCKED` because 41 has not reached `away`): the system retries at each hour slot. The member stays `Departing`; mood and loyalty are frozen; no new request.
- **If the wallet is 0 at departure**: no burn entry is written (Gold R4 refuses amounts ≤ 0); `wallet_burned = 0` in the snapshot.
- **If a leaver's friend is recuperating**: they still take the chain bump.

**Mood and loyalty**
- **If the tax is set to 0**: tax_term is 0, never positive. Low tax removes a complaint; it does not buy love. The fund then relies on shop revenue (Gold R7).
- **If the player flips tax every `tax_change_cooldown_s`**: mood follows with F2's 3-hour half-life and loyalty with a 46-hour one, so a brief high tax costs little and a sustained one costs a lot. No exploit: lowering tax just before a day slot changes loyalty by at most one hour's step.
- **If a member is awarded items in a loop for mood**: one award bump per 6 hours, and each award gives away a real item.
- **If all members are in one huge party**: party size is capped at 5 (`party_max`), so at most 10 pairs per party grow.
- **If the roster is below `low_rank_min_roster`**: no one is "low ranked".
- **If a member's needs are unknown** (41 not built, Vertical Slice before 41 exposes needs): needs_term is 0 (PROVISIONAL).

**Offline and time**
- **If a request is filed during an offline gap**: it waits; its deadline is extended from the return tick (R6). No member leaves by timeout while the player is away.
- **If the offline gap spans many days**: `settle_retention` runs hour slots per slice from the slice's aggregate inputs (party membership per trip, downings) and day slots in order; at most `leave_open_max` requests can be open, so a week away yields at most 3 waiting cards, not seven days of departures.
- **If a member joins at 23:59 of a day slot**: `leave_grace_days` counts game seconds from `joined_tick`, not day slots, so nobody leaves on their first day (S2 acceptance).

**Degenerate strategies checked**
- *Dismiss and rehire to reset loyalty*: a dismissed member's wallet is burned, friends lose mood ×1.5, and rehiring goes through Jianghu (17), where returning is chance-based (F9). Not profitable.
- *Accept every raise, then cut salaries*: each cut costs up to −20 mood at once and lowers the salary term permanently; loyalty follows. Net effect worse than not raising.
- *Ignore every request to get "free" recuperation*: recuperation takes the member off duty for 2 days, and a second timeout within 30 days always means leaving.
- *Save-scum a counter-offer*: same key, same die (R12).

## Dependencies

### Upstream (this system depends on)

| System | Hard/Soft | Interface | Status |
|---|---|---|---|
| Sim core (1) | Hard | P5 handler, P1 appliers, ctx | Designed (Needs Revision) |
| Deterministic RNG (2) | Hard | Domain 12, key R12, `chance_ppm`, `randint` | Designed (Needs Revision) |
| Data layer (3) | Hard | `config.csv`, `traits.csv`, `items.csv`, `buildings.csv` | Designed |
| Member model (8) | Hard | Field storage, roster, `remove_member` | Designed |
| CA/PA and traits (9) | Hard | `trait_mod_ppm`, CA | Designed |
| Gold economy (27) | Hard | `tax_ppm`, salary payment, 2707, `member_departed`/`member_returned` | Designed |
| Party (13) | Soft (bonds and party term are 0 without it) | Membership at the hour slot | Not designed — PROVISIONAL |
| Member state machine (41) | Hard for departure and recuperation | `injured/recuperate` with duration, `away`, needs | Not designed — PROVISIONAL |
| Guild and buildings (30) | Soft | Tửu Lâu effect, build events, buildable check | Designed |
| Items and loot (26) | Soft | 2603, item rows | Designed |
| Zones and hunt (11) | Soft | 1103 | Designed |
| Event bus (42) | Hard | Subscribe, emit, block 1600 | Designed (Needs Revision) |
| Command layer (5) | Hard | Commands 1601–1603 | Designed |

### Downstream (systems that depend on this one)

| System | Hard/Soft | What it needs |
|---|---|---|
| Jianghu free agents and NPC guilds (17) | Hard | Departure snapshot, `return_chance`, rejoin initialisation |
| Guild screens (39) | Hard | `retention_view`, events, commands |
| AI text layer (36) | Soft | Request cause and demand IDs for negotiation dialogue |
| Utility AI (12) | Soft | Ground demands in `contract.demands[]` |
| Quests (25), Analytics (37) | Soft | Events 1601–1606 |
| Offline progress (31) | Hard (it calls in) | `settle_retention` |
| Local save (6) | Hard | Section R13 |

The systems index lists Depends On as RNG, Member model, CA/PA and traits, Party, Gold economy. This GDD adds Member state machine (41), Event bus (42), Command layer (5), Sim core (1), Data layer (3), Guild and buildings (30), Items and loot (26) and Zones and hunt (11); the index row is updated to match.

## Tuning Knobs

All in `data/config.csv` (new keys; adding them and the validator ranges is the implementation story's job).

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `mood_base` | 50 | 40 – 60 | Nobody ever asks | Everyone asks | θ base, soft band |
| `mood_relax_ppm` | 200,000 | 50,000 – 500,000 | Bumps vanish within an hour | Tax changes take days to show | `loyalty_relax_ppm` |
| `loyalty_relax_ppm` | 15,000 | 5,000 – 50,000 | Loyalty jumps with every mood swing | One bad week never shows | — |
| `tax_mood_free_ppm` | 50,000 | 0 – 100,000 | Tax has no human cost | Default 10% tax crashes mood (S2 fails) | `tax_mood_coef`, Gold `guild_tax_pct` |
| `tax_mood_coef` | 1.0 | 0.5 – 2 | Tax unusable | Tax free | as above |
| `mood_party_base` | 0.03 | 0 – 0.08 | Solo hunting pointless | Parties feel no different | Party (13) |
| `bond_mood_max` | 6 | 0 – 10 | Friendships dominate mood | Bonds invisible | `chain_coef` |
| `sal_mood_coef`, `sal_mood_cap` | 100, 12 | 50–200, 6–20 | Salary trivially fixes everything | Raises useless | `raise_pct_ppm` |
| `needs_low`, `needs_pen` | 30, 8 | 10–50, 0–15 | Hunger is a crisis | Food irrelevant to mood | Member state machine (41) |
| `low_rank_pen`, `low_rank_frac`, `low_rank_min_roster` | 5, 1/3, 6 | 0–10, 0.2–0.5, 3–12 | Weak members always leave | Rank invisible | — |
| `leave_threshold_base` | 30 | 20 – 40 | Constant requests | Nobody leaves | traits `leave_threshold` |
| `leave_soft_band`, `leave_soft_max_ppm` | 15, 20,000 | 5–25, 5,000–50,000 | Rate above 10%/month | Rate 0 in a decent guild | F10 target |
| `leave_grace_days` | 2 | 1 – 7 | New members never tested | Leaves on day one (S2 fails) | — |
| `leave_open_max` | 3 | 1 – 5 | Card overload on return | Requests queue for weeks | — |
| `leave_request_window_h` | 24 | 6 – 72 | Requests linger | No time to gather an item | `pledge_max_h` |
| `request_cooldown_days` | 7 | 3 – 30 | — | Same member asks every week | — |
| `raise_pct_ppm`, `raise_round`, `salary_max_pct` | 50,000, 10, 500,000 | 20k–100k, 1–100, 200k–1M | Raises drain the fund | Raises trivial | Gold upkeep and tax |
| `w_base_salary/item/building/ground` | 40/25/15/20 | 0 – 100 (salary ≥ 1) | One kind dominates | A kind never appears | — |
| `neg_base`, `neg_loyalty_coef`, `neg_shortfall_coef`, `neg_min`, `neg_max` | 0.55, 1.0, 1.5, 0.02, 0.9 | 0.3–0.8, 0–2, 0.5–3 | Counter always wins (accept never used) | Counter never worth trying | traits `negotiation_success` |
| `counter_max` | 1 | 1 – 2 | Repeated rolls until success | — | — |
| `recup_base`, `recup_loyalty_coef`, `recup_min`, `recup_max` | 0.5, 2.0, 0.1, 0.9 | — | Ignoring requests is safe | Ignoring is always a loss | `recup_cooldown_days` |
| `recup_days`, `recup_loyalty_margin`, `recup_cooldown_days` | 2, 10, 30 | 1–5, 5–20, 14–60 | — | — | — |
| `pledge_max_h`, `ground_pledge_days` | 72, 7 | 24–168, 3–14 | — | — | Building build times |
| `stay_loyalty_bonus`, `stay_mood_bonus`, `counter_loyalty_bonus`, `counter_mood_bonus`, `counter_fail_mood` | 10, 5, 6, 2, 5 | 0 – 20 | — | — | F3 fades them |
| `bump_downed`, `bump_injured`, `bump_award`, `award_cooldown_h`, `bump_unpaid` | 6, 6, 4, 6, 10 | 0 – 20 | Single events dominate | Events invisible | — |
| `chain_coef`, `dismiss_chain_mult`, `bond_chain_min` | 15, 1.5, 20 | 0–30, 1–3, 0–60 | Cascading exits | No chain reaction (§6.8 lost) | `bond_mood_max` |
| `bond_rate`, `bond_clash_rate`, `bond_decay`, `bond_friend_threshold`, `bond_slots` | 0.5, 0.5, 0.02, 60, 5 | — | — | — | Party (13) |
| `cut_bump_coef`, `cut_bump_cap`, `salary_change_cooldown_h` | 200, 20, 24 | — | — | Salary cuts are free | — |
| `return_base`, `return_loyalty_coef` | 0.1, 0.2 | 0–0.5, 0–1 | — | — | Jianghu (17) |
| `loyalty_join`, `mood_join` | 60, 55 | 40 – 80 | — | Grace period ends in a request | θ |
| `retention_demand_buildings` | `bld_tavern;bld_inn;bld_restaurant;bld_housing` | IDs in `buildings.csv` | — | — | Guild and buildings |
| `mood_alert_low` | 30 | 10 – 50 | — | — | UI |

Owned elsewhere and only read here: `guild_tax_pct`, `tax_rate_cap` (Gold economy, Guild and buildings), `income_ref_per_level` (Gold economy), the Tửu Lâu `mood_gain` levels (`buildings.csv`, Guild and buildings), trait effect values (`traits.csv`, CA/PA), food `mood` values (`items.csv`, Items and loot), `party_max` (Party).

## Visual/Audio Requirements

*art-director lens: no art bible exists (`design/art/art-bible.md` absent); drafted from GDD §1 and the pixel 2D style.*
- **Mood and loyalty** on the member panel and roster list: an icon plus the number, with an arrow for the hourly trend. Never colour alone.
- **Leave request arrival** (1601): a small speech-bubble icon over the member's sprite in the world view until answered, and a badge on the guild screen. A short, non-alarming chime; a departure is a quieter, falling two-note cue.
- **Stayed**: a brief heart or bow animation on the sprite. **Recuperating**: the injured/rest pose of the Member state machine with a "resting" tag. **Leaving**: the sprite walks out of the guild gate once (world view 38); the roster slot greys out until removal.
- **Chain bump** and **bond formed**: a tiny emote over the affected member (sad cloud, linked hands), each at most once per event.
- 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:retention-leaving-and-negotiation`.

## Game Feel

- The answer to a request is felt at once: the card resolves in the same frame the command is acknowledged (P1 apply, next frame UI), with the outcome text and the die result ("Thương lượng thất bại").
- Mood visibly reacts within one game hour of a cause (F2 closes 20% of the gap per hour), so a tax change shows on the next hourly tick; loyalty visibly lags over days, so the player reads it as character rather than a bar.
- No outcome is ever a surprise: a member who is about to ask shows a falling loyalty arrow for at least a day before (soft band) unless an event knocked them below θ, and every outcome happens on screen or in the away report.

## UI Requirements

- **Member panel** (Guild screens 39): mood, loyalty, trend arrows; a breakdown of F1's non-zero terms as named lines ("Tax −5", "Tửu Lâu +4", "Party +3", "Friend Lý Thanh +2.4", "Ranked low −6"), salary, closest bonds.
- **Leave request card**: member, top two negative terms as the cause, the demand (item icon, building and level, ground, or raise amount), time left, and three buttons: Accept / meet it (for item and building, a shortcut to the award or build screen), Counter (a slider from 0 to 99% of R with a qualitative chance band: "very unlikely … likely"), Let go. Counter is hidden after one use.
- **Salary**: an edit field on the member panel; a cut shows the mood cost before confirming.
- **Dismiss**: a confirmation listing the friends who will be upset.
- **Away report**: requests filed while away, with their new deadlines.
- All text through Localization (4) keys; numbers formatted per locale.
- 📌 **UX Flag — Retention, leaving and negotiation**: this system has UI requirements. Run `/ux-design` for the member panel and the leave-request card before writing epics.

## Cross-References

| This GDD | Other GDD | Their section | Relationship |
|---|---|---|---|
| R1, R8 | `member-model.md` | Field table, R8, R9, R3 | Field ownership; removal; name record kept |
| R3, F1, F4–F9 | `ca-pa-and-traits.md` | `trait_mod_ppm`, reveal `event:leave_guild`, Interactions (Retention row) | This system owns the meaning of behaviour keys |
| F1, R10, R11, R8 | `gold-economy.md` | R6 (tax_ppm), R8 (salary, 2707), R11 (departed/returned), F1 | Salary and wallet flows |
| R12 | `deterministic-rng.md` | R4 domain 12, R5–R7, save-scumming edge case | Key layout and draw order |
| R2, R3 | `sim-core-and-tick-loop.md` | R2, R4, R5 | P5 order 1600, anchored timers |
| R3, F10 | `event-bus-and-history-log.md` | R3 (block 1600–1699), subscriber rules | Types 1601–1608 |
| R6, R10 | `command-layer.md` | Vocabulary table (`offer_contract`, `dismiss_member`) | Adds `answer_leave_request`; IDs 1601–1603 |
| R5, F1 | `guild-and-buildings.md` | `effect()`, 3001–3005 | Tửu Lâu term; building demands |
| R3, R5 | `items-and-loot-tables.md` | R8, 2603 | Award bump; item demands |
| R3, R8 | `zones-grounds-monsters-and-hunt-trips.md` | 1103; Edge Cases "asked to leave during a trip" | Downed bump; deferred departure |
| R13 | `local-save-and-migration.md` | R5, R6, R14 | Save section |

## Acceptance Criteria

*qa-lead lens applied: every rule R1–R12 and formula F1–F9 has at least one criterion; F10 is a balance-simulator criterion. All are [Logic] automated tests unless marked.*

- **AC-1 (R1)**: **GIVEN** a new recruit hired at salary 0, **WHEN** the Member model creates them, **THEN** mood = 55, loyalty = 60, salary 0, demands empty. **GIVEN** origin `returned` with `t_nostalgic`, **THEN** loyalty = 80.
- **AC-2 (R1)**: **GIVEN** an elder, **WHEN** 30 game days pass with tax at the cap, **THEN** their mood and loyalty are unchanged and no request is filed.
- **AC-3 (F1)**: **GIVEN** the F1 example inputs, **THEN** T = 54,400 milli. **GIVEN** tax 200,000 ppm, no tavern, no party, no bond, hungry and tired, low-ranked, **THEN** T = 50 − 15 − 16 − 5 = 14 points. **GIVEN** `unpaid_streak` 1 and salary 60,000 at level 50, **THEN** the salary term is 0.
- **AC-4 (F2)**: **GIVEN** M = 40, T = 54.4, **WHEN** one hour slot runs, **THEN** M = 42,880 milli. **GIVEN** M = T, **THEN** M is unchanged.
- **AC-5 (F3)**: **GIVEN** L = 60, M = 30, `t_loyal`, **WHEN** one hour slot runs, **THEN** L = 59,685 milli. **GIVEN** M > L, **THEN** k = 1 regardless of traits.
- **AC-6 (R3)**: **GIVEN** a member receives two awards 2 hours apart, **THEN** only the first raises mood (+4, greedy +3.6). **GIVEN** 2707 for a member, **THEN** mood −10 that tick.
- **AC-7 (F4, R4)**: **GIVEN** θ 30 and L 29.9, **WHEN** the day slot runs, **THEN** a request is filed with no RNG draw (ordinal unchanged). **GIVEN** L 40 with a fixed world seed, **THEN** the draw uses `chance_ppm(6,667)` with key `[id, joined_tick, ordinal]`; over 100,000 seeds the filing rate is 6,667 ± 300 ppm.
- **AC-8 (R4)**: **GIVEN** a member who joined 47 game hours ago with loyalty 0, **WHEN** a day slot runs, **THEN** no request. **GIVEN** 3 requests already open, **THEN** no fourth is filed and the member is checked the next day.
- **AC-9 (R5, F6)**: **GIVEN** a member at the salary ceiling and no valid item, building or ground, **THEN** no request is filed and the member enters `Cooldown`. **GIVEN** all kinds valid and a greedy member, **THEN** W = 46 + 27.5 + 15 + 20 (×1000), and over 100,000 seeds kind frequencies match weights within 1%.
- **AC-10 (F5)**: **GIVEN** level 50, plain traits, **THEN** R = 60,000; level 1 → 1,200; level 200 greedy → 276,000.
- **AC-11 (R6 accept)**: **GIVEN** a `salary` request with R 60,000, **WHEN** Accept is applied, **THEN** salary +60,000, loyalty +10, mood +5, request `Stayed`, 1602 outcome 1, cooldown 7 days. **GIVEN** an `item` request, **WHEN** Accept is sent before the award, **THEN** refused `demand_unmet` (4); **WHEN** the item is awarded, **THEN** the request closes `Stayed` that tick.
- **AC-12 (R6 counter, F6)**: **GIVEN** the F6 example (L 38, θ 30, 80%, humble), **THEN** `chance_ppm(430,000)` is drawn once; success raises salary by the offered amount; failure lowers mood by 5 and a second counter is refused `counter_used` (3). **GIVEN** amount = R, **THEN** refused `bad_amount`.
- **AC-13 (R6 let go, R8)**: **GIVEN** a member with wallet 5,000 and bond 80 with B, **WHEN** Let go is applied in tick N, **THEN** 1604 is emitted in N, B's mood falls by 12 in N, the member is moved to `away` no earlier than N+1, a `member_departed` burn of 5,000 is recorded, and `remove_member` is called after the burn. **[Integration]** with CA/PA: a `t_nostalgic` member's reveal (903) is emitted while they are still on the roster.
- **AC-14 (R6 timeout, R7, F7)**: **GIVEN** an open request and no answer, **WHEN** the deadline hour slot runs, **THEN** one `chance_ppm(F7)` draw decides; on Recuperate the member is `injured/recuperate` for 2 days, then loyalty ≥ θ + 10 and mood ≥ 50. **GIVEN** a recuperation 10 days earlier, **THEN** the timeout leaves without a draw.
- **AC-15 (R6 offline)**: **GIVEN** an open request with 2 hours left, **WHEN** the player is offline for 30 hours, **THEN** the request is still open on return with 24 hours left.
- **AC-16 (R5 building, pledge)**: **GIVEN** a Tửu Lâu level 3 demand, **WHEN** the build is queued, **THEN** the request is `Pledged`; **WHEN** completed, `Stayed`; **WHEN** cancelled instead, `Open` with a fresh 24 h; **WHEN** 72 h pass from the first pledge without completion, **THEN** the timeout draw runs.
- **AC-17 (R5 ground)**: **GIVEN** a ground demand accepted, **THEN** `contract.demands[]` holds `{ground, uid, until = now + 7 days}`; **WHEN** 7 days pass, **THEN** the entry is removed.
- **AC-18 (R9, F8)**: **GIVEN** a `t_social` and a plain member in one party for 100 hours, **THEN** their bond is 60 and 1606 is emitted once. **GIVEN** a `t_greedy` and a `t_generous` (conflicting) in one party for 10 hours from bond 10, **THEN** the bond is 5. **GIVEN** the pair limit is reached, **THEN** the lowest pair is dropped by the stated tiebreak.
- **AC-19 (R10)**: **GIVEN** a salary cut of 60,000 at level 50, **THEN** mood −10 at once and 1605 is emitted; a second change within 24 h is refused `cooldown`. **GIVEN** `dismiss_member` on an elder, **THEN** refused `elder`.
- **AC-20 (R12)**: **GIVEN** the same save, **WHEN** a counter-offer is reloaded and re-sent with the same amount 5 times, **THEN** the outcome is identical each time; with a higher amount the die value is the same and only the chance changes.
- **AC-21 (F9)**: **GIVEN** final loyalty 30 and `t_nostalgic`, **THEN** the snapshot's `return_chance` = 460,000 ppm.
- **AC-22 (R13) [Integration]**: **GIVEN** a guild with 2 open requests (one pledged), 10 bonds and a recuperating member, **WHEN** saved, loaded and run 48 game hours, **THEN** state and events equal an uninterrupted 48-hour run.
- **AC-23 (F10, GDD §20 S2) [Balance sim]**: **GIVEN** the standard configuration (20 members, tax 10%, Tửu Lâu 2, standard parties) and the standard policy (accept when R ≤ 10% of the fund's daily tax income, else counter at 80%, else let go), **WHEN** 30 game days are simulated over 20 seeds, **THEN** the mean leave rate is within 3–10%/month, no member leaves on day 1, and mean mood stays ≥ 45 at tax 10%.
- **AC-24 (Edge: two leavers)**: **GIVEN** members 5 and 9 both leave in tick N and both are bonded to member 7, **THEN** 7 takes two chain bumps in order 5 then 9, and the 5–9 bond is not applied to either.
- **AC-25 [UI, screenshot]**: the leave-request card and member mood breakdown render with icon + number for mood and loyalty in vi and en; retained screenshot in `production/qa/evidence/`.

*Gaps found by the lens and resolved above:* the offline deadline extension (AC-15) and the elder exemption (AC-2) had no criterion in the first draft. Playtest questions (not automatable): does a request feel fair and readable; is the counter slider's chance band understood.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | PROVISIONAL: Member state machine (41) — offers a `injured` sub-reason `recuperate` with a caller-set duration, an `away` transition on request that waits for trip/raid end, an event when `away` is reached, an `injured`-entry event, and `satiety`/`stamina` on a 0–100 scale | Member state machine (41) | When 41 is designed |
| OQ-2 | PROVISIONAL: Party (13) — exposes each member's party at the hour slot; Retention owns bonds (§6.8 "quan hệ"); Party may read bonds for its "quan hệ/trait hợp nhau" score (§6.12) | Party (13) | When 13 is designed |
| OQ-3 | PROVISIONAL: Utility AI (12) — honours a `ground` entry in `contract.demands[]` when choosing where a member hunts; ordering the member elsewhere during the pledge is allowed but costs `bump_broken_promise` (not yet a knob) | Utility AI (12) | When 12 is designed |
| OQ-4 | PROVISIONAL: Jianghu (17) — receives the departure snapshot and `return_chance`, owns the free-agent list and the story return, and calls Retention's rejoin initialisation; returned wallet minted as `member_returned` at 100% of the burned amount unless Jianghu decides otherwise | Jianghu (17) | When 17 is designed |
| OQ-5 | PROVISIONAL: Offline progress (31) — calls `settle_retention(to_tick, slice_inputs)` per slice with per-trip party rosters and downings; passes the return tick for the deadline extension | Offline progress (31) | When 31 is designed |
| OQ-6 | `t_haggler` `negotiation_success +0.1`: read here as "easier for the guild" like `t_humble`. A haggler could instead be meant to drive a harder bargain (−). Data owner to confirm the sign | CA/PA and traits (9) / user | Before the S2 implementation |
| OQ-7 | Interpretation of GDD §2 "bình thường chỉ bị thương → dưỡng sức": read as the ordinary non-leaving outcome of an unanswered request (and as "defeat never makes a member leave"). Confirm with the user | User | Before /design-review |
| OQ-8 | PROVISIONAL: Recruitment (15) — passes the hire salary (from the candidate's §6.7 "yêu cầu lương/đồ") into R1; item demands at hire are not modelled here | Recruitment (15) | When 15 is designed |
| OQ-9 | **RESOLVED (consistency-check 2026-11-16):** Rebirth R10 confirms Elders are exempt from leaving, mood, contracts and dismissal. | Rebirth (23) | Closed |
| OQ-10 | GDD §21 Prompt S2 also lists school change at Tàng Kinh Các; that is owned by Schools and school change (20) and is not part of this system | — | Resolved by scope |
| OQ-11 | Gold economy emits nothing when a salary is paid; R11 infers "paid" from the absence of 2707 at the day slot. A `salary_paid` event or query would be cleaner | Gold economy (27) | Next Gold revision |
| OQ-12 | Command layer listed only `offer_contract` and `dismiss_member`; this GDD adds `answer_leave_request` and allocates IDs 1601 `answer_leave_request`, 1602 `offer_contract`, 1603 `dismiss_member`. Applier cost: O(1) each plus one draw; sim requests per tick ≤ number of departures that tick (≤ 3 + dismissals) | Command layer (5) | Consistency pass |
| OQ-13 | `add_mood` for food: who calls it (Items and loot on consumption, or Member state machine on eating) | Items (26) / 41 | When 41 is designed |
