# Recruitment

> **Status**: In Design
> **Author**: Claude (design-system, autonomous batch run) — pending user review
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no game pillars written yet). Anchored to GDD §1 ("tuyển thành viên" is the first of the four guild-master verbs), §2 ("Tuyển mộ: Chủ động (mời, thám tử) + thụ động [CHỐT]"), §6.7, and the candidate pillar in the systems index CD note: "every member is a person with a hidden ceiling".
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, `game-concept.md` or game brief exist to check against; re-run once pillars are written
> **Reference implementation**: none. GDD §20 prompt S1 plans `sim/recruit.py`; it does not exist yet. This GDD is the spec that module and the Godot port follow.

## Summary

Recruitment is how new people enter the guild. Every couple of hours a group of three strangers arrives at the gate, each showing a school (or "undecided"), a level, a CA value and a PA estimate as stars and a range, and the guild master takes at most one of them. It is the game's first and most frequent decision about people: who to take, on a hunch about a hidden ceiling, and which gap in the roster to fill.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` (the recurring pick-1-of-3 walk-in offer with CA, PA estimate and school; Chiêu Hiền Lệnh, the Scout House's extra candidates, traits, fees, demands and a fame-driven arrival rate in Vertical Slice) · Key deps: `Deterministic RNG, CA/PA and traits, Member model, Guild and buildings, Schools, Command layer, Sim core and tick loop, Data layer, Event bus, XP curve, Local save`

## Overview

Recruitment generates candidates and turns the one the player picks into a guild member. It runs inside the headless simulation as a small state machine around a single **recruitment board**: on a fixed schedule of game time a **walk-in offer** of `recruit_offer_size` (3) candidates appears; the player accepts one (`accept_candidate`), rejects candidates one by one (`reject_candidate`), or leaves the offer open. Accepting hires that candidate through Member model's `create_member` and closes the offer, so the other candidates leave. Each candidate is rolled from RNG domain 8 with a key built only from the offer's ordinal and the candidate's slot, so reloading or doing something else first never changes who arrives.

The data layer is small (the board, a few ordinals and due ticks), but the player-facing effect is large. This is where the player first meets the CA/PA estimate and has to act on it, where school choice starts (GDD §6.12: every party wants a buffer, and the board leans toward the buffer school while the guild lacks one), and where the roster grows from empty to a full first party. Without it the guild has no way to get people, and the management core of the game (GDD §5: "who do I take? what could they become?") has no moment where the first question is asked.

The MVP is deliberately thin (systems index, MVP scope cuts): walk-in offers only, no traits, no fee, no demands. The Vertical Slice adds the active routes of GDD §6.7 (Chiêu Hiền Lệnh invitations, the Scout House's extra candidates), traits, a hiring fee, salary demands, and a faster arrival rate as the guild grows. The full rules are specified once here; the tier tags say what is built first.

*Implementation boundary.* How the board is stored, how candidate generation is split into functions, and whether the screen polls or subscribes are implementation choices for an ADR. This GDD fixes behaviour: draw order, keys, commands, events and refusals.

## Player Fantasy

**Framing: both.** The player acts on Recruitment directly (scan three cards, take one) and feels it indirectly for weeks afterwards, as the recruit grows into or falls short of their stars.

Candidate framings considered (creative-direction lens; no pillars file, so each anchors to a GDD section instead of a quoted pillar):

- **(A) "A hunch at the gate" — chosen.** Three strangers stand at the gate. Two show three stars; the third shows two and a half with a wide range, 74–150, but is the healer the guild has been missing. The guild master takes the healer. Every later level-up is a small verdict on that call. *Anchor:* GDD §5.1 (the player only sees an estimate) and §6.7 (candidates show school, level and a PA estimate).
- **(B) "Building the sect I need."** The roster lacks a buffer and a Hoả school for the next Golden Boss; the board is a puzzle of filling gaps. *Anchor:* GDD §6.12, §6.13. Kept as a secondary moment: the buffer lean (R6) makes it real, but school choice is also Schools' fantasy, so it does not anchor this GDD.
- **(C) "The jianghu comes to me."** Fame grows, better people knock on the door, and a Chiêu Hiền Lệnh brings a master. *Anchor:* GDD §6.7 ("tốc độ/độ hiếm theo … danh vọng"). Kept for the Vertical Slice, when fame and invitations exist (R13, R14).

**The feeling to protect:** a small, frequent, *informed gamble*. The player should feel that they read the cards well or badly, not that a slot machine paid out. That asks three things of the rules: the estimate shown is honest (the true PA is always inside the range — CA/PA R7), the dice cannot be re-rolled (R4), and saying no costs only time, never a penalty (R9).

*Reference:* Evil Hunter Tycoon's hunter arrivals (frequent, low-stakes, with rare standouts) and Football Manager's scouting (a range that narrows with investment). This system takes the cadence of the first and the honesty of the second.

## Detailed Design

*Specialist lenses applied (Section 6 routing, `Gameplay` → row "Character systems"):*
- **game-designer (primary).** The decision is "which of three", so the three must differ in readable ways: school, arrival level and estimate. A board that can be cleared for free and rerolled on demand would turn the decision into a grind, so rejecting costs time (R9). A full roster must not silently stop the board; the player should see who they are missing (R8).
- **systems-designer.** Keys must not include anything the player can shift (RNG R5, save-scum rule): key the dice on the offer ordinal and slot only, never the candidate count, the tick at which the offer opened or a global candidate counter that a Scout House level would shift (R4). The buffer lean reads roster state, which the player controls; that changes inputs, not dice, and is the accepted "probing fixed dice" case (RNG Edge Cases).
- **art-director.** The arrival of an offer and a rare candidate (four stars or more on the card) each need a distinct visual beat; the cards must read at phone width (Visual/Audio, UI Requirements).
- **narrative-director.** A hire is a story beginning; the Chronicle should record who joined and from where (`origin`), and rejected candidates should feel like they went back to the jianghu, not that they were deleted (Vertical Slice hand-off to Jianghu, R10).

No conflict between the lenses needed a decision.

### Core Rules

**R1 — Ownership.** Recruitment owns: the recruitment board and every candidate on it; the candidate generator (school, arrival level, PA, name and, from the Vertical Slice, traits); the offer schedule; the `accept_candidate`, `reject_candidate` and (Vertical Slice) `use_recruit_token` commands; and the `recruit_*` keys in `config.csv`. It does not own the member record (Member model 8), PA display or traits' rules (CA/PA 9), schools (Schools 20), the roster cap (Guild and buildings 30), gold (Gold economy 27), contracts and salaries (Retention 16) or free agents (Jianghu 17).

**R2 — The board.** The guild has one board. At any time it is either `Empty` or holds one **offer**: `{kind, ordinal, opened_tick, candidates[]}`. `kind` is `walk_in` (0) or, from the Vertical Slice, `invitation` (1). Each candidate is `{candidate_id, school_id_or_none, aspiring_school_id, level, pa, trait_ids[], name}` plus `state ∈ {open, rejected}`. Candidates hold no PA-estimate state; the screen asks CA/PA's `candidate_view(candidate_id, pa, trait_ids, snapshot)` each time it draws (CA/PA R2), with `candidate_id` as the `pa_key`.

**R3 — The walk-in schedule (MVP).** Walk-in offers arrive on an anchored deadline grid (Sim core R5 convention): `walk_in_due_tick` starts at 0 for a new guild and advances by `interval_ticks` (F1). A P5 handler (order 1500) runs each tick:
1. If `N < walk_in_due_tick`, do nothing.
2. Re-anchor `walk_in_due_tick` to the next grid point strictly after N (F1).
3. If the board is `Empty`, open a walk-in offer with ordinal `walk_in_ordinal + 1` (R5) and store the new ordinal. If the board holds an offer, the slot is **skipped**: nothing is generated and the ordinal does not advance. There is no backlog.

So a player who ignores the board keeps the same offer until they act on it, and a player who acts at once gets a new offer at the next grid point, not sooner.

**R4 — Keys and IDs (RNG domain 8).** Candidate `s` (0-based slot) of offer `(kind, ordinal)` is generated from `derive(8, [kind, ordinal, s])`. Its `candidate_id` is F2: unique in the save, fixed when it is generated, used as the command target and as CA/PA's `pa_key`. Why the player cannot shift the dice:
- `ordinal` advances only when an offer of that kind opens (R3, R13). It never advances on accept, reject, reload, roster change or building upgrade.
- The slot index is the candidate's position. Extra slots from the Scout House (R14) are appended after slot 2, so a Scout House level changes how many candidates an offer has, never who sits in slots 0–2.
- No tick, wall-clock time or roster value is in the key.
- Candidates are generated and saved when the offer opens (R12), which is the commit point RNG OQ-6 asks each gamble GDD to state: what is on the board is fixed, and reloading shows the same people.

**R5 — Opening an offer.** In order:
1. Compute the offer size `n` (F5): `recruit_offer_size` (3), plus the Scout House's `candidate_extra` from the Vertical Slice.
2. For `s = 0 … n − 1`, generate candidate `s` with the draw order of R6. Generation reads the roster as it is now (for the buffer lean) and reads no other mutable state.
3. Run CA/PA `check_potential(pa, trait_ids)` on each. A refusal (951) is a Recruitment bug: `ctx.fail(15001)` naming the key. It is never retried with other draws.
4. Store the offer with `opened_tick = N` and emit `recruit_offer_opened` (1501).

**R6 — Candidate generation: draw order is a contract (RNG R7).** One generator per candidate, these draws in this order:
1. **Affiliation:** `chance_ppm(recruit_affiliated_ppm)`. True → the candidate arrives already in a school; false → unaffiliated.
2. **School:** a weighted pick (F3) over the **live** schools (Data layer `content_live`; wave 1 = `kim_2, moc_1, thuy_1, hoa_2, tho_1`) in `uid` order. Every school weighs `recruit_school_weight_ppm`; a school with `buff_role = true` weighs `recruit_school_weight_ppm + recruit_buffer_boost_ppm` while the guild has a **buffer deficit** (F3). An affiliated candidate gets this as `school_id`; an unaffiliated one gets it as `aspiring_school_id` and is shown as "undecided" (Schools R3).
3. **PA band:** a weighted pick over the PA bands (F4) in band order.
4. **PA:** `randint(band_lo, band_hi)`.
5. **Name:** `choice(surnames)` then `choice(given_names)` from the person-name lists in `uid` order (OQ-4).
6. **Traits (Vertical Slice; F6).** In MVP no draw is made and the trait list is empty. Because traits come last, adding them in the Vertical Slice changes no MVP candidate's school, PA or name.

The **arrival level** is not a draw: an affiliated candidate arrives at `school_join_level` (10, Schools) and an unaffiliated one at level 1 (F8). GDD §6.7 says "level 10 hoặc 0"; level 0 does not exist (XP curve R9 accepts 1 to `cap[r]`), so 0 is read as 1. Rebirth is 0. Element follows the school (Schools); an unaffiliated candidate has no element.

**R7 — What a candidate card shows.** School (or "undecided" with no element), arrival level, CA, the PA estimate from `candidate_view` (stars and range, or the exact PA while the Thiên Nhãn entitlement is held — CA/PA R10), the surface trait if any (Vertical Slice), the count of hidden trait slots as `?` (Vertical Slice), and from the Vertical Slice the hiring fee and salary demand. CA is CA/PA F1 evaluated on the candidate's spec (level, school, no skills, no equipment, revealed traits only); Recruitment asks CA/PA for it through `candidate_view` and does not compute it (PROVISIONAL — OQ-2). The true PA, hidden traits and the aspiring school of an undecided candidate are never shown.

**R8 — `accept_candidate(candidate_id)` (host, P1, command 1501).** Validated in this order, first failure wins:
1. The candidate is on the open offer and in state `open` → otherwise `target_missing` (6).
2. The roster is below `member_cap` (Guild and buildings F2) → otherwise `roster_full` (101).
3. (Vertical Slice) The fund can pay the hiring fee (F7) → otherwise `cannot_afford` (8).

Then, all or nothing (Command layer R5): debit the fee as `recruit_cost` (Vertical Slice); call `create_member(spec)` with `{name, origin, pa, pa_key = candidate_id, traits, school_id or aspiring_school_id, level, rebirth = 0}`; on success, close the offer (R10) with reason `accepted` and emit `candidate_accepted` (1502). `origin` is `walk_in` for a walk-in offer and `recruited` for an invitation (GDD §4.1). If `create_member` refuses after validation passed (it checks the same cap, so this means two systems disagree), that is `ctx.fail(15002)`, never a refusal, because the fee may already be debited.

A full roster does not stop offers from opening (R3); the card shows the refusal reason before the player taps, so the player sees who they would be missing and can make room (Retention's `dismiss_member`, Vertical Slice).

**R9 — `reject_candidate(candidate_id)` (host, P1, command 1502).** Refuses with `target_missing` (6) if the candidate is not `open` on the current offer. Otherwise sets it to `rejected` and emits `candidate_rejected` (1504). When no `open` candidate remains, the offer closes (R10) with reason `all_rejected`. Rejecting is free and has no effect on mood, fame or any later offer; its only cost is that the next walk-in offer still waits for the next grid point (R3). The screen offers "pass on all", which submits one `reject_candidate` per open candidate in slot order.

**R10 — Closing an offer.** The board becomes `Empty` and `recruit_offer_closed` (1503) is emitted with the reason. Candidates not hired are discarded in the MVP. From the Vertical Slice they are handed, as specs, to Jianghu free agents (17), which decides whether they enter the free-agent list (PROVISIONAL — OQ-6). They are never re-offered by Recruitment.

**R11 — The founding roster.** A new guild has no members (PROVISIONAL with Onboarding 44 — OQ-5). While the roster holds fewer than `recruit_founding_roster` (5, one full party) members, closing a walk-in offer sets `walk_in_due_tick = N + 1`, so the next offer opens on the next tick instead of waiting for the grid. The grid resumes from that tick. The first offer opens on tick 0 of a new guild. This gets the player to a full first party in a few minutes of choices, each still a real pick of one from three.

**R12 — State and persistence.** Saved under the `recruitment` section (Local save R-contract: own serializer and migration): `walk_in_ordinal`, `walk_in_due_tick`, the board (offer and candidates with their states), and from the Vertical Slice `invitation_ordinal`. All values are integers or the candidate name text. No generator state is saved (RNG R11). A load restores the board exactly; it never regenerates candidates from their keys, so a content change between versions cannot change people already on the board.

**R13 — Invitations: Chiêu Hiền Lệnh (Vertical Slice).** `use_recruit_token()` (host, P1, command 1503) refuses with `board_occupied` (102) if the board holds an offer, and with `cannot_afford` (8) if Items and loot reports no `item_recruit_token` in guild storage. Otherwise Items `take`s one token and an invitation offer opens at once (R5) with ordinal `invitation_ordinal + 1`, kind 1. Invitation candidates roll their PA band only from bands `≥ recruit_token_min_band` (F4, renormalised): "invite top-tier people with an item" (GDD §6.7). The walk-in grid is unaffected; a walk-in slot that falls while the invitation is open is skipped as usual. Tokens reach storage as quest/achievement rewards or are bought with Linh Bảo in the Linh Bảo shop at `lb_price_recruit_token` (default 150, about 0.4 of a week's quest faucet; Gold economy R16/F9, user decision 2026-11-16). Recruitment only consumes the token; it never sells it.

**R14 — Scout House and arrival rate (Vertical Slice).**
- *Extra candidates:* each offer gets `candidate_extra` more candidates at the current `bld_scout` level (`buildings.csv`: 0, 1, 1, 2, 2, 3, 3, 4 at levels 1–8), appended as slots 3+ (R4). The Scout House also narrows every candidate's PA range; that is CA/PA F2, not this system.
- *Arrival rate:* the walk-in interval shortens with guild fame (F1 `fame_cut`). Fame has no owner yet (Guild and buildings OQ-6); until it has one, `fame_cut = 0` and the interval is fixed. GDD §6.7 names a Tụ Nghĩa Đường building as the other driver; no such building exists in `buildings.csv` (OQ-3).
- *Fee and demands:* accepting debits the hiring fee (F7). Each candidate shows a salary demand, set by Retention (16) as the hired member's starting `contract.salary` (PROVISIONAL — OQ-7).

**R15 — Events.** Recruitment registers the type block 1500–1599 (`recruitment_event_type_block`):

| ID | Name | a, b, c, d | Logged |
|---|---|---|---|
| 1501 | `recruit_offer_opened` | kind, ordinal, candidate count, best half-stars shown | no |
| 1502 | `candidate_accepted` | candidate_id, member_id, kind, half-stars shown | **milestone** (Chronicle: who joined, from where) |
| 1503 | `recruit_offer_closed` | kind, ordinal, reason (0 accepted, 1 all_rejected) | no |
| 1504 | `candidate_rejected` | candidate_id, kind, ordinal | no |

Quests (25) counts `accept_candidate` objectives (`q_d_recruit`) from 1502. Notifications (46) and the world view (38) read 1501. Per-tick volume is at most one offer and a few commands, far below the Event bus emission budget.

**R16 — Registration.** Commands 1501–1503 in this system's block (Command layer R2); reason codes 101 `roster_full`, 102 `board_occupied`; P5 handler order 1500; fail codes 15001 (a generated candidate failed `check_potential`), 15002 (`create_member` refused after validation), 15003 (a weighted pick with total weight 0, i.e. no live school or no live band — a data error the validator should have caught).

**R17 — Gating.** Recruitment is live from the first tick in every wave. Invitations and extra candidates are gated on their content being live (`item_recruit_token`, `bld_scout`), checked by this system's applier (`not_live`, 9; Command layer R14). The Thiên Nhãn entitlement changes only what the card shows, never what is generated.

### States and Transitions

**Board**

| From | To | Trigger | Notes |
|---|---|---|---|
| `Empty` | `Offer open` | P5 walk-in due tick (R3), or `use_recruit_token` (R13, VS) | Generates and saves all candidates (R5) |
| `Offer open` | `Offer open` | `reject_candidate` with open candidates remaining | One candidate becomes `rejected` |
| `Offer open` | `Empty` | `accept_candidate` accepted | Reason `accepted`; the rest leave (R10) |
| `Offer open` | `Empty` | the last open candidate rejected | Reason `all_rejected` |
| `Offer open` | `Offer open` | walk-in due tick | Skipped: no new offer, no ordinal change (R3) |

**Candidate:** `open → rejected` (R9), `open → hired` (R8, becomes a member and leaves the board), `open/rejected → gone` when the offer closes (R10). There is no transition back to `open`.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|---|---|---|---|---|
| Deterministic RNG (2) | → this | Generators from `derive(8, key)`; `chance_ppm`, `randint`, `choice` | Key layout `[kind, ordinal, slot]` | RNG owns the primitives; this GDD owns the key and draw order |
| Data layer (3) | → this | `schools.csv` (`buff_role`, live rows), `config.csv` `recruit_*`, `items.csv`, person-name lists | — | Data layer |
| Sim core (1) | both | Tick N, P1 commands, P5 phase | P5 handler 1500 | Sim core |
| Command layer (5) | both | Dispatch of 1501–1503 | Appliers, reason codes 101–102 | Command layer owns the envelope; this GDD owns the rules |
| CA/PA and traits (9) | both | `check_potential`, `candidate_view` (stars, range, exact flag, surface trait, CA), `max_traits`, conflict rules | `pa_key = candidate_id`, `pa`, trait IDs | CA/PA owns display and trait rules; this system owns the rolls |
| Member model (8) | → Member model | — | `create_member(spec)` | Member model owns creation and IDs |
| Schools (20) | → this | Live schools, `school_join_level`, `buff_role` | `school_id` or `aspiring_school_id` | Schools owns liveness and joining |
| XP curve (22) | → this | `init_progress` range (1 … `cap[0]`) | Arrival level | XP curve validates |
| Guild and buildings (30) | → this | `member_cap` (F2), `effect(bld_scout, candidate_extra)` (VS) | — | Guild and buildings |
| Gold economy (27) | → Gold (VS) | `can_debit` | `debit(recruit_cost, fund, fee, candidate uid)` | Gold owns the ledger |
| Items and loot (26) | → Items (VS) | Storage count of `item_recruit_token` | `take(item_recruit_token, 1)` | Items owns storage |
| Retention (16) | both (VS) | Salary demand for a candidate; `dismiss_member` frees roster space | Candidate spec | Retention owns contracts |
| Jianghu free agents (17) | → Jianghu (VS) | — | Unhired candidate specs on close | Jianghu owns the free-agent list |
| Event bus (42) | → bus | — | Events 1501–1504 | Event bus owns delivery and the milestone log |
| Quests (25), Analytics (37), Notifications (46), World view (38) | bus → them | 1501–1504 | — | Each consumer |
| Guild screens (39) | reads | Board state, candidate cards, refusal reasons | Commands | Guild screens owns layout |
| Offline progress (31) | both | Gap bounds | `settle_gap(from_tick, to_tick)` (R-Edge) | Offline owns crossed due ticks (Sim core R5) |
| Local save (6) | both | Load | `recruitment` section | Save owns the format |
| Entitlement (32) | → this (display only) | `exact_pa_all` snapshot | — | Entitlement |

## Formulas

### F1 — Walk-in interval and grid

The walk_in_interval formula is defined as:

`interval_ticks = recruit_offer_interval_min × 60 × tick_rate × (1,000,000 − fame_cut_ppm) // 1,000,000`
`next_due = due + k × interval_ticks`, smallest `k ≥ 1` with `next_due > N`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| recruit_offer_interval_min | int | 15 – 720 (120) | data file (`config.csv`, new) | Minutes of game time between walk-in slots |
| tick_rate | int | Sim core F1 set (10) | data file (`config.tick_rate`) | Ticks per second |
| fame_cut_ppm | int ppm | 0 – `recruit_fame_cut_max_ppm` (0 in MVP) | calculated (VS, from fame; OQ-3) | Share of the interval removed by guild fame |
| recruit_fame_cut_max_ppm | int ppm | 0 – 750,000 (500,000) | data file (`config.csv`, new, VS) | Fastest arrival is half the base interval |
| due | int | ≥ 0 | calculated (saved) | Current `walk_in_due_tick` |
| N | int | ≥ 0 | Sim core | Executing tick |

**Output Range:** 72,000 ticks (2 h) in MVP; 36,000 ticks (1 h) at the VS fame cap. At most 12 walk-in offers per game day in MVP, fewer for a real player because an open offer skips slots. The validator refuses `interval_ticks < 1`.
**Example:** `120 × 60 × 10 = 72,000`. A guild created at tick 0 has slots at 0, 72,000, 144,000 … If the offer from tick 0 is still open at 72,000, that slot is skipped and the next chance is 144,000.

*Why 2 hours:* the MVP roster cap is 12 (`bld_hq` level 1) and the founding rule (R11) fills the first 5 at once. Seven more places at up to 12 offers a day fill in a day of attentive play or two to three days of a real schedule, roughly when `bld_housing` and the HQ upgrades start to matter (Guild and buildings). The daily quest `q_d_recruit` asks for one hire a day, which this cadence always allows. An hourly cadence (the Golden Boss's) would fill the cap in an afternoon and make rejecting free.

### F2 — Candidate ID

The candidate_id formula is defined as:

`candidate_id = 1 + kind × 2⁴⁸ + ordinal × 2⁸ + slot`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| kind | int | 0 – 2 | constant | 0 walk-in, 1 invitation; 2 reserved |
| ordinal | int | 1 – 2⁴⁰ − 1 | calculated (saved) | Offer ordinal within its kind |
| slot | int | 0 – 255 | calculated | Candidate position; at most `recruit_offer_size_max` − 1 in practice |

**Output Range:** 1 to about 5.6 × 10¹⁴, inside CA/PA's `pa_key` range (1 – 2⁶³−1) and a non-negative command `entity` arg. Unique because (kind, ordinal, slot) is unique and each field fits its bit width. Reaching ordinal 2⁴⁰ needs over 250 million years of 2-hour offers.
**Example:** walk-in offer 7, slot 2 → `1 + 0 + 7 × 256 + 2 = 1,795`. Invitation offer 1, slot 0 → `1 + 2⁴⁸ + 256 = 281,474,976,710,913`.

### F3 — School weights and buffer deficit

The school_weight formula is defined as:

`deficit = buffers < max(1, ceil(roster / party_max))`
`w(school) = recruit_school_weight_ppm + (buff_role(school) and deficit ? recruit_buffer_boost_ppm : 0)`
`pick = first school in uid order whose running weight sum > randint(0, Σw − 1)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| buffers | int | 0 – roster | calculated | Roster members whose `school_id`, or `aspiring_school_id` if unaffiliated, has `buff_role = true` |
| roster | int | 0 – `member_cap` | calculated (Member model) | Disciples on the roster now |
| party_max | int | 5 | data file (`config.csv`) | Party size; one buffer per party is the goal (GDD §6.12) |
| recruit_school_weight_ppm | int | 1 – 1,000,000 (1,000,000) | data file (`config.csv`, new) | Base weight of each live school |
| recruit_buffer_boost_ppm | int | 0 – 4,000,000 (1,000,000) | data file (`config.csv`, new; GDD §20 S1 `recruit_buffer_boost`) | Extra weight for each buffer school while in deficit |
| Σw | int | ≥ 1, ≤ 2³² | calculated | Total weight; 0 is fail 15003, above 2³² is a validator ERROR |

**Output Range:** with the 5 wave-1 schools (one buffer, `moc_1`): `moc_1` probability is 20% without a deficit and `2/6 ≈ 33.3%` with one. At boost 4,000,000 it reaches `5/9 ≈ 55.6%`.
**Example:** roster 6 with one `moc_1` → needed `ceil(6/5) = 2`, buffers 1, deficit true. Σw = 6,000,000; `randint` 1,500,000 lands in `moc_1`'s range [1,000,000, 3,000,000) if `moc_1` is second by `uid`.
**Boundaries:** roster 0 → needed 1, buffers 0 → deficit (the founding offers lean to a healer). Boost 0 → plain uniform. No live buffer school (a later wave could remove one) → the boost applies to nothing; weights stay uniform.

### F4 — PA bands

The pa_roll formula is defined as:

`band = weighted pick over bands b ∈ {1…5} with weights recruit_pa_band_w[b]` (only `b ≥ min_band`, F4 renormalises by picking over the remaining weights)
`pa = randint(band_lo[b], band_hi[b])`

| Band b | `band_lo`–`band_hi` | `recruit_pa_band_w` (ppm) | Shown roughly as |
|---|---|---|---|
| 1 | 0 – 59 | 300,000 | ½–1½ stars |
| 2 | 60 – 99 | 400,000 | 1½–2½ stars |
| 3 | 100 – 139 | 220,000 | 2½–3½ stars |
| 4 | 140 – 169 | 65,000 | 3½–4 stars |
| 5 | 170 – 200 | 15,000 | 4–5 stars |

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| band_lo[b], band_hi[b] | int | 0 – `pa_max`, contiguous, covering 0–200 | data file (`config.csv`, new: `recruit_pa_band{b}_lo/_hi`) | Band bounds |
| recruit_pa_band_w[b] | int ppm | 0 – 1,000,000, sum 1,000,000 | data file (`config.csv`, new: `recruit_pa_band{b}_w`) | Band weight |
| min_band | int | 1 for walk-ins; `recruit_token_min_band` (3) for invitations | data file (`config.csv`, new, VS) | Lowest band allowed |
| pa_max | int | 200 | data file (`config.csv`) | PA ceiling (CA/PA) |

**Output Range:** PA 0–200. Walk-in mean ≈ 79.8, median 79; P(PA ≥ 100) = 30%, P(≥ 140) = 8%, P(≥ 170) = 1.5%. Best of a 3-candidate offer: expected max ≈ 116; at least one PA ≥ 100 in 65.7% of offers, ≥ 140 in 22.1%, ≥ 170 in 4.4%. Invitations (bands 3–5 only): mean ≈ 130, P(≥ 170) = 5%.
**Example:** a band draw lands in band 3, then `randint(100, 139)` → 117.
**Why bands, not a curve:** a piecewise table is integer-exact in Python and GDScript, makes "rare at the top" (GDD §20 S1) a visible, tunable number per band, and gives the statistical AC exact expected frequencies. The balance simulator's standard party is PA 100 (GDD §4.3); a typical first party picked best-of-3 lands near 100–116, so the measured pacing holds for an attentive player and runs slower for one who takes whoever comes.
**Boundaries:** a band with weight 0 is never picked and still consumes no extra draw (the pick is one `randint`). Weights not summing to 1,000,000, gaps or overlaps between bands, or a band outside 0–`pa_max` are validator ERRORs. No live band at `min_band` or above → fail 15003.

### F5 — Offer size

The offer_size formula is defined as:

`n = min(recruit_offer_size_max, recruit_offer_size + candidate_extra(scout_lv))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| recruit_offer_size | int | 1 – 5 (3) | data file (`config.csv`, new) | Base candidates per offer |
| candidate_extra | int | 0 – 4 | data file (`buildings.csv` `bld_scout` effects; 0 without the building and in MVP) | Scout House extra candidates (VS) |
| recruit_offer_size_max | int | 1 – 8 (8) | data file (`config.csv`, new) | Hard cap, keeps slots well under 256 (F2) and the screen readable |

**Output Range:** 3 in MVP; 3–7 in the Vertical Slice.
**Example:** Scout House level 4 → `min(8, 3 + 2) = 5`.

### F6 — Traits (Vertical Slice)

The trait_roll formula is defined as:

`count = weighted pick over {1, 2, 3} with recruit_trait_count_w[1..3]`, capped at `max_traits`
for each of `count` picks: `tier = weighted pick over {common, rare, epic} with recruit_trait_tier_w`; `eligible` = live traits of that tier, not yet chosen, not conflicting (both directions) with any chosen, in `uid` order; if `eligible` is non-empty, `choice(eligible)`, else the pick adds nothing

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| recruit_trait_count_w[k] | int ppm | sum 1,000,000 (500,000 / 350,000 / 150,000) | data file (`config.csv`, new) | Odds of 1, 2, 3 traits (GDD §5.2: "1–3 trait/member") |
| recruit_trait_tier_w | int ppm | sum 1,000,000 (700,000 / 250,000 / 50,000) | data file (`config.csv`, new) | Odds of common, rare, epic per pick |
| max_traits | int | 3 | data file (`config.csv`) | CA/PA cap |

**Output Range:** 0–3 traits (0 only if every pick finds no eligible trait, which the 40-trait table makes impossible today); mean 1.65. No conflicting pair by construction, so `check_potential` never fails on traits.
**Example:** count draw → 2; first pick tier common → `t_greedy`; second pick common → eligible excludes `t_greedy` and `t_generous` (conflict) → `t_brave`.
**Draw count:** 1 + per pick (1 tier draw + 1 choice draw if eligible). Variable but fully determined by the key, which is all RNG R7 requires.

### F7 — Hiring fee (Vertical Slice)

The recruit_fee formula is defined as:

`fee = recruit_fee_base + recruit_fee_per_half_star × half_stars_shown + recruit_fee_per_level × (level − 1)`, scaled by `cost_scale`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| recruit_fee_base | int gold | 0 – 10,000 (200) | data file (`config.csv`, new) | Flat fee |
| recruit_fee_per_half_star | int gold | 0 – 2,000 (50) | data file (`config.csv`, new) | Per half-star **shown** on the card |
| recruit_fee_per_level | int gold | 0 – 500 (30) | data file (`config.csv`, new) | Per arrival level above 1 |
| half_stars_shown | int | 0 – 10 | calculated (CA/PA F4 via `candidate_view`) | Stars as the player sees them |
| cost_scale | float→ppm | 1.0 | data file (`config.csv`) | Global cost knob, converted once at boot (Gold economy) |

**Output Range:** 200 (level 1, 0 stars) to 970 (level 10, 5 stars) gold. Small against income (about 1,000 gold per member-level per hour, GDD §19.1): a fee is a speed bump that makes "take the 4-star" a small, felt cost, not a barrier.
**Why shown stars, not true PA:** a fee from true PA would leak it (two candidates with the same card and different fees). With Thiên Nhãn the shown stars are the exact ones, so the fee follows what that player sees.
**Example:** level 10, 3 stars shown (6 half-stars): `200 + 300 + 270 = 770`.

### F8 — Arrival level

`level = affiliated ? school_join_level : 1`

| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| affiliated | bool | — | calculated (R6 draw 1, `recruit_affiliated_ppm`, 0 – 1,000,000, default 500,000, `config.csv` new) | Arrives in a school |
| school_join_level | int | 1 – 20 (10) | data file (Schools) | Joining level |

**Output Range:** 1 or 10. Must be within XP curve R9 (`1 … cap[0]`); the validator checks `school_join_level ≤ cap[0]`.
**Trade-off it creates:** an affiliated level-10 candidate is useful today; an undecided level-1 candidate is a blank page whose school the player picks (Schools R3), ten levels (about 2–4 hours AFK, GDD §4.3) from mattering.

## Edge Cases

**Schedule and offline**
- **If a walk-in due tick falls while an offer is open**: the slot is skipped and the ordinal does not advance (R3). The open offer is never replaced, so a candidate the player is saving roster room for is never lost.
- **If the player is offline across one or more due ticks**: Offline progress (31) owns crossed due ticks (Sim core R5). It calls `settle_gap(from_tick, to_tick)` once before `skip_ticks`: if the board is `Empty` and at least one due tick lies in the gap, one walk-in offer opens (next ordinal), dated `opened_tick = to_tick`; then `walk_in_due_tick` is re-anchored past `to_tick`. Backlog is at most one offer, because the board holds one (PROVISIONAL — OQ-8). The roster read for the buffer lean is the roster at the end of the gap.
- **If the founding rule and the grid both apply on one tick** (an offer closes at tick N with roster < 5): the next offer opens at N + 1 (R11); the grid re-anchors from there. Only one offer can open per tick, because opening needs an empty board.
- **If `recruit_offer_interval_min` changes in a content update**: the saved `walk_in_due_tick` is kept; the new interval applies from the next re-anchor. No offer is lost or doubled.

**Accepting and rejecting**
- **If the roster is full**: offers still open; `accept_candidate` refuses with `roster_full` (101) and changes nothing; the card shows the reason before the tap.
- **If two `accept_candidate` commands for the same offer arrive in one tick**: P1 applies them in `seq` order (Command layer R3); the first hires and closes the offer, the second refuses with `target_missing`.
- **If the player accepts a candidate that was already rejected**: `target_missing` (6). Rejection cannot be undone.
- **If `member_cap` drops below the roster** (a content change, Guild and buildings Edge Cases): nobody is removed; accepts refuse until the roster is below the cap.
- **If the player reloads to see different candidates**: the same candidates appear, because they were saved when the offer opened (R12) and are re-derived from the same key if ever regenerated (R4). Rejecting all and reloading restores the same offer.
- **If the player tries to reroll by rejecting all at once**: the next offer waits for the next grid point (R3), so rejecting buys nothing but a wait. During the founding phase (R11) rejecting all gives the next offer at once; that is deliberate, because the founding offers are about picking a party, and the founding phase ends at 5 members.
- **If the player hires a weak candidate during the founding phase to get past it quickly**: allowed. The founding phase ends at 5 members regardless of quality; a weak founder is a cost the player chose.
- **If the player changes the roster before an offer opens to steer the school pick** (for example dismissing the healer to create a deficit): the dice are fixed, only the weights change. This is the accepted "probing fixed dice" property (RNG Edge Cases); the gain is a higher chance of a buffer school, which is the lean's purpose anyway.

**Generation**
- **If no school is live** (impossible in shipped waves): Σw = 0 → `ctx.fail(15003)`. The content validator rejects any wave with no live school.
- **If a school is retired between offers**: it is never offered again (`content_live`); candidates already on the board keep it, and Schools R1 lets a member of a retired school keep it.
- **If every buffer school is non-live**: F3's boost applies to no school; picks stay uniform.
- **If the generator produces a candidate `check_potential` refuses**: `ctx.fail(15001)`, the run halts (Sim core R10). Never reroll, because a reroll would make the draw count depend on content in a way the parity harness cannot predict.
- **If the person-name lists are empty or missing**: the validator ERRORs at boot; the sim never runs with them (OQ-4).
- **If two candidates get the same name**: allowed; the ID is the identity (Member model R4).
- **If the Thiên Nhãn entitlement is bought while an offer is open**: the cards switch to exact PA at once; nothing in the offer changes (R17). Refunded: back to the estimate.

**Vertical Slice**
- **If `use_recruit_token` is used with an offer open**: refused `board_occupied` (102); no token is spent. The player passes on the walk-in offer first.
- **If the fee becomes unaffordable between seeing the card and tapping**: `cannot_afford` (8), nothing changes.
- **If the Scout House is upgraded while an offer is open**: the open offer keeps its size; the next offer uses the new `candidate_extra`. Slots 0–2 of every offer are unchanged by the upgrade (R4).

*Lens applied:* systems-designer, Section E checks against Sections C and D. Two degenerate strategies were found and closed: reject-all rerolling (closed by the grid in R3, kept open only in the founding phase by design) and Scout-House-shifted keys (closed by keying on slot, not on a global candidate counter).

## Dependencies

| System | Hard / Soft | Interface | Status |
|---|---|---|---|
| Deterministic RNG (2) | Hard | Domain 8, `derive`, `chance_ppm`, `randint`, `choice`; key rules R5–R7; save-scum rule | Designed |
| Data layer and content pipeline (3) | Hard | `content_live`, `uid` order, `config.csv`, `schools.csv`, `items.csv`, validator | Designed |
| Sim core and tick loop (1) | Hard | P1, P5, anchored deadline ticks, `ctx.fail` | Designed |
| Command layer (5) | Hard | Command registration, reason codes, all-or-nothing appliers | Designed (lists `accept_candidate`/`reject_candidate` as PROVISIONAL; this GDD fixes IDs 1501–1503) |
| CA/PA and traits (9) | Hard | `check_potential`, `candidate_view`, `pa_key`, `max_traits`, conflict rules, CA on a candidate spec | Designed |
| Member model (8) | Hard | `create_member(spec)`, `MM_ROSTER_FULL`, roster count, names | Designed |
| Guild and buildings (30) | Hard | `member_cap` (F2); `effect(bld_scout, candidate_extra)` (VS) | Designed |
| Schools and school change (20) | Hard | Live schools, `buff_role`, `school_join_level`, aspiring school | Designed |
| XP and level pacing curve (22) | Soft | `init_progress` level range | Designed |
| Event bus and history log (42) | Hard | Type block 1500, milestone 1502 | Designed |
| Local save and migration (6) | Hard | `recruitment` save section | Designed |
| Gold economy (27) | Soft (VS) | `debit(recruit_cost …)` | Designed (lists `recruit_cost` as VS) |
| Items and loot (26) | Soft (VS) | `take(item_recruit_token)` | Designed |
| Offline progress (31) | Soft | `settle_gap` call across a skip | Not designed — PROVISIONAL |
| Retention (16) | Soft (VS) | Salary demand; `dismiss_member` | Not designed — PROVISIONAL |
| Jianghu free agents (17) | Soft (VS) | Receives unhired candidates | Not designed — PROVISIONAL |
| Onboarding (44) | Soft | Founding roster flow | Not designed — PROVISIONAL |
| Entitlement (32) | Soft | `exact_pa_all` display snapshot | Not designed |

**Depended on by:** Quests and achievements (25, event 1502), Guild screens (39, board and cards), Analytics (37), Local push notifications (46, event 1501), Realtime world view (38, arrivals at the gate), Jianghu (17, unhired candidates), Onboarding (44).

**Bidirectional check:** CA/PA (9), Member model (8), Guild and buildings (30), Schools (20), XP curve (22), Gold economy (27), Items and loot (26), Command layer (5) and RNG (2) each already list Recruitment (15). Guild and buildings lists only `member_cap` and `bld_scout`; it does not need more.

## Tuning Knobs

| Knob | Where | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `recruit_offer_interval_min` | `config.csv` (new) | 120 | 60 – 360 | Roster fills slowly; the board feels dead | Roster fills in an afternoon; rejecting is free | `member_cap`, `q_d_recruit`, offline cap |
| `recruit_offer_size` | `config.csv` (new) | 3 | 2 – 4 | Choice overload on a phone; best-of-n inflates PA | One candidate is no choice | `candidate_extra`, F4 best-of-n odds |
| `recruit_offer_size_max` | `config.csv` (new) | 8 | 4 – 8 | Unreadable cards | Scout House extra candidates capped away | `bld_scout` |
| `recruit_founding_roster` | `config.csv` (new) | 5 | 1 – `member_cap` | Founding phase skips too many real decisions | Player waits hours for a first party | `party_max`, Onboarding |
| `recruit_affiliated_ppm` | `config.csv` (new) | 500,000 | 200,000 – 800,000 | Schools' choice moment (Fantasy 2) rarely happens | Every recruit is two hours from useful | `school_join_level` |
| `recruit_school_weight_ppm` | `config.csv` (new) | 1,000,000 | any > 0 | — (only the ratio to the boost matters) | — | `recruit_buffer_boost_ppm` |
| `recruit_buffer_boost_ppm` | `config.csv` (new) | 1,000,000 | 0 – 4,000,000 | The board feels rigged toward healers | Parties go without a buffer (GDD §6.12 decision A relies on this) | `party_max`, number of live buffer schools |
| `recruit_pa_band{1..5}_lo/_hi/_w` | `config.csv` (new) | F4 table | top-band weight 5,000 – 40,000 | 4-star candidates become ordinary; Scout House and lenses lose value | Rare candidates never appear in a real schedule | XP pacing (§4.3 PA 100 standard), Items drop scaling by PA |
| `recruit_token_min_band` | `config.csv` (new, VS) | 3 | 2 – 5 | 5 → token always gives a master; token is the dominant route | 1 → token is a plain extra offer | `item_recruit_token` sources, incl. `lb_price_recruit_token` (Gold economy R16) |
| `recruit_trait_count_w`, `recruit_trait_tier_w` | `config.csv` (new, VS) | F6 | — | Epic-heavy rosters; CA trait term inflates | Members feel generic | CA/PA `max_traits`, trait reveal pacing |
| `recruit_fee_*` | `config.csv` (new, VS) | 200 / 50 / 30 | 0 – 5× | Fee gates the early game | Fee is meaningless | Gold income §19.1, `cost_scale` |
| `recruit_fame_cut_max_ppm` | `config.csv` (new, VS) | 500,000 | 0 – 750,000 | Late game floods the board | Fame has no recruitment payoff | Fame owner (OQ-3) |

Knobs owned elsewhere and only read here: `member_cap` (Guild and buildings), `candidate_extra` and `pa_error` (`bld_scout`), `school_join_level` (Schools), `max_traits`, `pa_max`, `pa_hw_no_scout` (CA/PA), `party_max`, `tick_rate`, `cost_scale`.

## Visual/Audio Requirements

*Art-director lens (Visual/Audio part of `references/lens-specialists.md`); no art bible exists yet, so these are intents, not specs.*
- **Arrival beat (1501):** strangers appear at the guild gate in the world view, one pixel figure per candidate, wearing the school's palette or plain travel clothes if undecided. A soft gong or door-knock cue. No fanfare for an ordinary offer: it happens up to twelve times a day.
- **Rare candidate:** if any card shows four stars or more, the gate figure gets a faint gold outline and a distinct chime. Driven by the shown stars only (never the true PA), so the effect leaks nothing.
- **Hire (1502):** the chosen figure walks in through the gate; the others turn and leave down the road (they go back to the jianghu, R10). A short warm sting.
- **Pass:** rejected figures walk away; no negative sound.
- Asset spec: run `/asset-spec system:recruitment` after the art bible is approved.

## Game Feel

- **Decision time over speed.** The board waits; nothing on it times out. The player should never feel hurried by it.
- **Readable at a glance:** the three cards fit one phone screen without scrolling (five-plus with the Scout House scrolls horizontally). Stars, school icon and level are the first three things the eye lands on; the range text is second.
- **Response:** tapping Accept gives immediate feedback (the card lifts, the figure walks in) on the next frame; the command result arrives next tick (≤ 100 ms) and a refusal (`roster_full`) shakes the button with its reason text.
- **No punishment for passing:** "pass on all" is one tap with no confirmation in the normal phase.

## UI Requirements

- **Recruitment board** (Guild screens 39): up to `recruit_offer_size_max` candidate cards; each shows name, school icon and name or "undecided", element, arrival level, CA, stars and range "lo–hi" (or exact PA with Thiên Nhãn), from the Vertical Slice the surface trait, `?` trait slots, fee and salary demand. Actions: Accept per card, Pass per card, Pass on all. Accept is disabled with the reason text when the roster is full or the fee is unaffordable.
- **Next arrival timer:** shown when the board is empty ("Next arrivals in 1 h 12 m"); while an offer is open, a line explains that new people come once this group is answered.
- **Badge and notification:** a badge on the guild screen when an offer is open; Local push notifications (46) may notify on 1501 with a rare-candidate variant.
- **Founding:** the first five offers are framed by Onboarding (44) as "build your first party".
- No lens button on candidate cards (CA/PA R10).
- All text through Localization (4): `recruit.*` keys; names are proper nouns, not localised (Member model R4).

> **📌 UX Flag — Recruitment**: This system has UI requirements. In Pre-Production, run `/ux-design` for the recruitment board before writing epics; stories should cite `design/ux/recruitment-board.md`.

## Cross-References

| This GDD | Refers to | Element | Source |
|---|---|---|---|
| R4, R6, Edge Cases | `deterministic-rng.md` R3–R8, domain table, Edge Cases (save-scum, probing fixed dice), OQ-6 | Domain 8, key rules, draw order, commit point | RNG |
| R2, R5, R7, F7 | `ca-pa-and-traits.md` R1, R2, R7, R8, R10, F2, F4 | `check_potential`, `candidate_view`, `pa_key`, stars, Thiên Nhãn display, candidate width 38 | CA/PA |
| R8 | `member-model.md` R2, R4, R8 | `create_member(spec)`, roster cap, names | Member model |
| R6, F3, F8 | `schools-and-school-change.md` R1, R3, `buff_role`, `school_join_level` | Live schools, aspiring school, joining on arrival | Schools |
| F8 | `xp-and-level-pacing-curve.md` R9 | Arrival level range 1 … `cap[r]` | XP curve |
| R8, R14, F5 | `guild-and-buildings.md` F2, `effect(bld_scout, candidate_extra)`, OQ-6 | `member_cap`, extra candidates, unowned fame | Guild and buildings |
| R3, Edge Cases | `sim-core-and-tick-loop.md` R2, R5 (anchored deadline ticks), R10 | P5 timers, crossed due ticks across a skip | Sim core |
| R8, R9, R16 | `command-layer.md` R2–R7, R14, MVP vocabulary | Command IDs, reason codes, all-or-nothing | Command layer |
| R15 | `event-bus-and-history-log.md` R3 | Type block, milestones | Event bus |
| F7, R14 | `gold-economy.md` entry type 27 `recruit_cost`, R9 | Fee debit | Gold economy |
| R13 | `items-and-loot-tables.md` R7, R9 | `item_recruit_token` guild-held, `take` | Items and loot |
| R12 | `local-save-and-migration.md` | Per-feature serializer | Local save |
| — | `JX1_Tycoon_GDD.md` §1, §2, §4.1, §5, §6.7, §6.12, §11, §20 S1 | Source design | Source GDD v1.0 |

## Acceptance Criteria

*QA-lead lens applied: each core rule and formula has at least one criterion; statistical criteria use fixed seeds and stated tolerances so they are deterministic.*

**Schedule (R3, R11, F1)**
- **AC-1**: **GIVEN** a new guild at tick 0, **WHEN** the first tick runs, **THEN** a walk-in offer with ordinal 1 and 3 candidates is open and event 1501 is emitted.
- **AC-2**: **GIVEN** a roster of 5 and an open offer opened at tick 0, **WHEN** ticks reach 72,000 with the offer still open, **THEN** no new offer opens, `walk_in_ordinal` is still the same, and `walk_in_due_tick` is 144,000.
- **AC-3**: **GIVEN** a roster of 5 and an offer closed at tick 80,000, **WHEN** tick 144,000 runs, **THEN** the next offer opens there, not earlier.
- **AC-4 (founding)**: **GIVEN** a roster of 2, **WHEN** an offer closes at tick N, **THEN** the next offer opens at tick N + 1; **GIVEN** a roster of 5, **THEN** it waits for the grid.

**Keys and determinism (R4, R12, F2)**
- **AC-5**: **GIVEN** a fixed world seed, **WHEN** the same command log runs twice, in Python and in GDScript, **THEN** every candidate (school, aspiring school, level, PA, name, traits) is identical (parity harness golden vectors).
- **AC-6 (save-scum)**: **GIVEN** an open offer, **WHEN** the game is saved, all candidates are rejected, and the save is reloaded, **THEN** the same three candidates are on the board.
- **AC-7 (no shift)**: **GIVEN** two runs from the same seed where run B rejects offer 1 and run A accepts from it, **WHEN** offer 2 opens in both, **THEN** offer 2's candidates in slots 0–2 have the same PA, name and affiliation draw in both runs (school may differ only through the F3 deficit weights).
- **AC-8**: **GIVEN** (kind 0, ordinal 7, slot 2), **THEN** `candidate_id = 1,795`; (kind 1, ordinal 1, slot 0) → 281,474,976,710,913.

**Generation (R5, R6, F3, F4, F8)**
- **AC-9 (PA distribution)**: **GIVEN** 10,000 walk-in candidates from a fixed seed, **THEN** band frequencies are within ±1.5 percentage points of 30 / 40 / 22 / 6.5 / 1.5%, the mean PA is 79.8 ± 1.5, and no PA is outside 0–200.
- **AC-10 (buffer lean)**: **GIVEN** 10,000 candidates generated with a buffer deficit, **THEN** `moc_1` frequency is 33.3% ± 1.5 points; **without** a deficit, 20% ± 1.5 points.
- **AC-11**: **GIVEN** a roster of 6 with one `moc_1`, **THEN** deficit is true; **GIVEN** a roster of 5 with one `moc_1`, **THEN** false; **GIVEN** an unaffiliated member aspiring to `moc_1`, **THEN** they count as a buffer.
- **AC-12 (arrival level)**: **GIVEN** 10,000 candidates, **THEN** affiliated ones are level 10 with a `school_id`, unaffiliated ones are level 1 with an `aspiring_school_id` and no `school_id`, and the affiliated share is 50% ± 1.5 points.
- **AC-13 (liveness)**: **GIVEN** wave 1 content, **WHEN** 10,000 candidates are generated, **THEN** no candidate has a school outside `kim_2, moc_1, thuy_1, hoa_2, tho_1`.
- **AC-14 (draw order)**: **GIVEN** a generator built from known raw values, **THEN** exactly these draws are consumed in this order: `chance_ppm`, school `randint`, band `randint`, PA `randint`, surname `choice`, given-name `choice`; and in MVP no further draw.
- **AC-15 (MVP traits)**: **GIVEN** the MVP build, **THEN** every candidate has an empty trait list and every `check_potential` call returns ok.

**Commands (R8, R9, R10)**
- **AC-16**: **GIVEN** an open offer and a roster below cap, **WHEN** `accept_candidate` targets slot 1, **THEN** a member is created with origin `walk_in`, `pa_key` = that candidate's ID, and the candidate's PA, school and level; the board is `Empty`; events 1502 and 1503 (reason 0) are emitted; Member model emits `member_joined`.
- **AC-17**: **GIVEN** a full roster, **WHEN** `accept_candidate` is sent, **THEN** it refuses with 101 `roster_full` and the board, roster and ledger are unchanged.
- **AC-18**: **GIVEN** an open offer, **WHEN** `reject_candidate` is sent for each of the 3 candidates, **THEN** three 1504 events then one 1503 with reason 1 are emitted and the board is `Empty`.
- **AC-19**: **GIVEN** a rejected candidate, **WHEN** `accept_candidate` targets it, **THEN** it refuses with 6 `target_missing`.
- **AC-20**: **GIVEN** two `accept_candidate` commands for different candidates of one offer in the same tick, **THEN** the lower `seq` hires and the other refuses with 6.
- **AC-21 (estimate carries over)**: **GIVEN** a candidate whose card shows range lo–hi, **WHEN** they are hired, **THEN** their member card shows the same lo–hi (CA/PA R2 continuity).

**Persistence and offline (R12, Edge Cases)**
- **AC-22**: **GIVEN** an open offer with one candidate rejected, **WHEN** saved and loaded, **THEN** the board, the candidate states, `walk_in_ordinal` and `walk_in_due_tick` are identical, and no RNG draw is made on load.
- **AC-23 (offline)**: **GIVEN** an empty board and an 8-hour offline gap crossing 4 due ticks, **WHEN** the gap is settled, **THEN** exactly one offer is open, with the next ordinal, and `walk_in_due_tick` is the first grid point after the gap's end. **GIVEN** an open board, **THEN** no offer opens.

**Vertical Slice (R13, R14, F5, F6, F7)**
- **AC-24**: **GIVEN** Scout House level 4, **WHEN** an offer opens, **THEN** it has 5 candidates and slots 0–2 equal those of the same ordinal generated with no Scout House.
- **AC-25**: **GIVEN** one `item_recruit_token` and an empty board, **WHEN** `use_recruit_token` is sent, **THEN** the token count drops by 1, an invitation offer opens, and its candidates' PA are all ≥ 100 (10,000-candidate run: bands 3/4/5 at 73.3 / 21.7 / 5.0% ± 1.5 points).
- **AC-26**: **GIVEN** an open offer, **WHEN** `use_recruit_token` is sent, **THEN** it refuses 102 and no token is spent.
- **AC-27 (traits)**: **GIVEN** 10,000 VS candidates, **THEN** none has a conflicting pair or more than `max_traits` traits; trait counts are 50 / 35 / 15% ± 1.5 points.
- **AC-28 (fee)**: **GIVEN** a level-10 candidate shown at 3 stars, **THEN** the fee is 770 and accepting debits 770 from the fund as `recruit_cost`; **GIVEN** the fund at 769, **THEN** refused 8 and nothing changes.

**Presentation**
- **AC-29 (UI, screenshot)**: the board with three cards (one undecided) and a full-roster refusal is captured in Vietnamese and English at phone width; screenshots retained in `production/qa/evidence/`.
- **AC-30 (performance)**: opening an offer of 8 candidates costs under 0.2 ms on the min-spec Android device (well inside one tick); it happens at most once per tick.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | PROVISIONAL: Member model (8) — `create_member(spec)` does not list `pa_key` in its spec (R8 of Member model); CA/PA needs it. Add `pa_key` to the spec | Member model | Consistency pass |
| OQ-2 | PROVISIONAL: CA/PA (9) — `candidate_view` returns the estimate; this GDD assumes it also returns CA for a candidate spec (level, school, no skills, no gear). Add it there, or Recruitment calls F1 through another pure CA/PA function | CA/PA | Consistency pass |
| OQ-3 | Scope: GDD §6.7 says arrival speed and rarity depend on "Tụ Nghĩa Đường + danh vọng". No Tụ Nghĩa Đường building exists in `buildings.csv`/`building_meta.csv` (the closest is `bld_scout` Thám Tử Quán, "find candidates"), and guild `fame` has no owner (Guild and buildings OQ-6). Assign fame an owner and decide whether a Tụ Nghĩa Đường building is added or the role folds into `bld_scout`. Until then `fame_cut = 0` | Producer, systems index | Before Vertical Slice |
| OQ-4 | Content gap: no person-name lists exist in `i18n/` (only content names). R6 needs surname and given-name lists in `uid` order (GDD §16 leaves names to the designer, Vietnamese-history themed). Adding the files is a data-schema addition; the validator must check them | Designer + Data layer | Before MVP build |
| OQ-5 | PROVISIONAL: Onboarding (44) — a new guild starts with no members and the founding rule (R11) fills 5 by quick offers. Onboarding may prefer a scripted first party instead | Onboarding | When Onboarding is designed |
| OQ-6 | PROVISIONAL: Jianghu free agents (17) — receives unhired candidates' specs when an offer closes (VS), and owns "gửi thiệp mời" (inviting a named free agent, GDD §6.7). Should that invite reuse `accept_candidate` on a kind-2 offer? | Jianghu | When Jianghu is designed |
| OQ-7 | PROVISIONAL: Retention (16) — supplies a candidate's salary demand and sets `contract.salary` at hire (GDD §6.7 "yêu cầu (lương/đồ)"). Item demands are not modelled here | Retention | When Retention is designed |
| OQ-8 | PROVISIONAL: Offline progress (31) — calls `settle_gap(from, to)` once per gap before `skip_ticks`; backlog is one offer | Offline progress | When Offline is designed |
| OQ-9 | Scope: Premium's "thêm lượt tuyển mộ/ngày" (GDD §11) is not modelled. Candidate: a Premium interval of 90 minutes via the entitlement snapshot. Needs a monetisation decision | User, Entitlement (32) | Before Alpha |
| OQ-10 | Should the Scout House's "search by role" (GDD §6.12 hint: "Thám Tử Quán lọc theo vai trò") be a VS command that biases one offer toward a role? Not designed here | Game design | Before Vertical Slice |
| PT-1 | Playtest: is a 2-hour walk-in cadence with skip-while-open right for real schedules, or do players feel stuck with an offer they cannot use (full roster)? | QA / user | MVP playtest |
| PT-2 | Playtest (with CA/PA PT-2): with ±38 ranges and no traits, do three MVP cards differ enough to make the pick interesting? | QA / user | MVP playtest |
