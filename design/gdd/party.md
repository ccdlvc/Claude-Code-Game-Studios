# Party

> **Status**: Designed (pending independent review)
> **Author**: user + Claude (design-system, autonomous batch run; decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no `design/gdd/game-pillars.md`). Serves the locked rule of `JX1_Tycoon_GDD.md` §2 ("Tối đa 5 người/đội; ưu tiên mỗi đội có 1 thành viên buff/hỗ trợ") and §6.12
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief to check against. Player Fantasy is anchored to `JX1_Tycoon_GDD.md` §2 and §6.12 instead. Re-run once pillars exist.
> **Mode**: partial retrofit. The Python reference has only the party XP multiplier (`sim/formulas.py` `party_xp_mult`), a caller-supplied party list (`sim/hunt.py` `run_trip`) and a raid-only grouping (`sim/raid.py` `form_parties`). Persistent parties, formation, disbanding, commands and the key identity are new. Every difference from the code is named here and listed in Open Questions.

## Summary

Party is how guild members group up to hunt: up to five members who travel, fight and come home together, ideally with one buffer (support) member in each group. It forms and disbands parties automatically, lets the player build and edit them by hand, computes the party's XP bonus, and hands each hunt trip its roster and its random-number identity. It exists because the game's one locked composition rule, "five per party, one buffer each", must be both automatic for an idle player and readable for a guild master who wants to plan.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Member model, Schools and school change, Utility AI, Member state machine, Zones and hunt trips, Combat, Golden Boss and guild raid, Offline progress, Retention, Items and loot, Command layer, Event bus`

## Overview

**What it is.** A *party* is a saved group of 2 to `party_max` (5) guild members who hunt as one group. Party owns the whole life of that group: forming it (automatically from free members, or by the player), keeping it across trips, changing its members, and disbanding it (systems index contract: "Party owns party formation and disbanding"). A member in no party hunts alone. For the hunt, a lone member is "a party of one" with the same identity rules, so every trip has the same shape.

**Data layer.** Party keeps one save section: the party records (members in slot order, leader, lock flag, Lệnh Kỳ banner timer, absence counters), each member's `trips_led` counter, the solo flags and the Premium presets. It has no tick handler of its own: the Member state machine calls it once per P2 pass to turn members who want to hunt into hunting groups. It owns a block of commands for the player's edits and a block of events. It provides pure functions other systems call: the hunting groups, the party XP multiplier, the trip key identity, membership, and the existing parties for a raid. How well a set of members fits together is scored by Utility AI (12, F3 `composition_score`); Party owns the search that uses that score.

**Player impact.** The player sees parties on the map and in the guild screens, and reads them as a plan: who is with whom, whether each group has a buffer and a tank, and whether its levels match. On the free tier, parties form by themselves and the player can rearrange them. Premium adds locking, a whole-guild re-arrange and saved presets (GDD §6.12, §11.2). A party without a buffer still hunts, only slower, and the screens say so with the "thiếu buffer" (no buffer) warning.

**Scope.** In: formation and disbanding, membership edits, leader choice, the party XP bonus, the trip roster and key identity, existing parties for the raid, the Lệnh Kỳ banner, warnings, and the proposed generation-cycle and counter-coverage group bonus for Combat. Out, owned elsewhere: the composition score (Utility AI 12, F3); where a group hunts (Utility AI `choose_ground`); the trip itself (Zones and hunt 11); the fight and the in-fight buffer bonus (Combat 10); loot sharing (Items and loot 26, rule `suited_first`); who joins the raid and the raid's temporary groups (Golden Boss 14, R7); bonds between members (Retention 16, R9); member behaviour states and hunt intents (Member state machine 41).

No ADR exists for this system (`docs/architecture/` has no ADR files). Items marked "→ ADR" are for `/architecture-decision`.

## Player Fantasy

**Framing: direct.** The player builds, reads and fixes parties, so the system is player-facing (`Gameplay` category).

*No game pillars exist, so no pillar is quoted. The candidates below are anchored to `JX1_Tycoon_GDD.md` §2 (the locked "one buffer per party" rule) and §6.12. CD-GDD-ALIGN remains NOT ASSESSED.*

Three framings were considered (creative-director lens):

1. **"The balanced party" — chosen.** *The moment:* the guild master opens the party panel before the hourly boss. Four groups show a buffer icon, one shows a red "thiếu buffer" tag. The player drags the new Mộc healer into that group, the tag clears, and on the next homecoming that party's XP bar fills visibly faster than before. The feeling is *"I saw what was missing and fixed it"*. It asks the design for: a composition the player can read at a glance (roles, elements, level spread), a buffer bonus that is true in the numbers (Combat R8, F1 here), and auto-formation that is good but leaves room for a human to do better.
2. **"Sworn brothers" (bond).** *The moment:* two members who have hunted together for a week refuse to be split when one is offered a better contract. It asks for persistent parties, which this design has, and for bonds that matter, which Retention (16, R9) owns. Kept as the **secondary line**: Party makes it possible by keeping parties together across trips.
3. **"The machine runs itself" (automation).** *The moment:* the player returns after a night and finds parties formed and reformed without them. Rejected as the lead: true for the free tier, but a fantasy without the player is no reason to show the system at all. It survives as a requirement: auto-formation is always on and never worse than solo play.

**Target feeling.** Planning satisfaction: "my groups are well built and I can see why." A badly built party is never punished hard, it is only slower, so a mistake reads as a lesson, not a loss.

## Detailed Design

### Core Rules

*Specialist lenses applied (Section 6 routing: "Character systems" within `Gameplay`, unioned with "AI/pathfinding/behavior" because formation is an automatic decision):*

- *game-designer* — The player's decisions are who goes with whom, who leads and who stays solo. Auto-formation must be good enough that a free player is not punished, and transparent enough that a better human choice is visible (warning tags, Utility AI's fit badges). The player cannot pick a ground here (Utility AI), cannot change a roster mid-trip, and cannot exceed five.
- *systems-designer* — Every rule must be deterministic and integer, with no random draws, so realtime, offline, the simulator and server replay agree. A party is Assembled or OnTrip; disbanding is terminal. The drift-out rule damps the "members level apart" loop.
- *ai-programmer* — Formation is a greedy pass with a fixed order and a cost bounded by the roster (80 members at most, `member_cap` 12–80, Guild and buildings F2). It runs inside the Member state machine's P2 pass, before Utility AI picks grounds, so free members are grouped before anyone is sent out alone.
- *art-director* — Parties must read on the map as one unit: a banner over the leader and a tag for "no buffer". See Visual/Audio.
- *narrative-director* — The only story beat here is "these people stay together", which Retention turns into bonds.

No conflict between roles needed a decision. Conflicts with built behaviour and with sibling GDDs were resolved by conforming to the existing GDD and are logged (R7, R16, OQ-1, OQ-7).

**R1 — What a party is.** A party record holds:

| Field | Meaning |
|---|---|
| `party_id` | The leader's `member_id` (R5). Unique among live parties, because a member is in at most one party. |
| `members[]` | 2 – `party_max` member IDs in slot order. Slot 0 is the leader. Slot order is the combatant order Combat uses (Combat R3). |
| `locked` | Premium flag (R11). A locked party is not changed by the automatic rules of R3 and R8. |
| `formed_tick` | The tick the record was created. |
| `banner_until_tick` | The tick until which the Lệnh Kỳ banner counts as a buffer (R12); 0 if none. |
| `absent_streak[]` | Per member, consecutive trip starts the member missed (R9). |

A member belongs to at most one party. A member in no party is *free*. Membership is Party's record, not a behaviour state: there is no `in_party` state in the Member state machine and no `party_id` field on the member record. Other systems ask `party_of(member_id) -> party_id or 0`, an index Party rebuilds from its records on load. (GDD §6.12 suggests a member field and an `in_party` state; this design keeps one copy of the fact. Open Questions OQ-3.)

**R2 — Who can be grouped.** A member is *groupable* when all of these hold:
1. They are on the roster with rank `disciple` (Elders do not hunt; Member state machine `elder`).
2. Member state machine (41) reports `can(member, join party)` (its capability table: `idle` yes; `resting` yes, starting when idle; every other state no).
3. They are `idle` with a hunt intent — in Member state machine terms, **free to hunt** this tick (MSM R10 member step 5, which carries no ground) — so a member on the way to eat or rest is not pulled into a group.
4. They are not flagged solo (R10).

**R3 — The formation pass.** Party registers no Sim core handler. Each P2 pass, after the Member state machine has collected its idle members and run their decision steps, it calls `groups_for_trips(N)` (Utility AI "call sequence", step 2). Party then:

1. **Fill.** For each unlocked, Assembled party with fewer than `party_max` members, in ascending `party_id`: while it has room, add the free groupable member with the highest Utility AI `composition_score(party ∪ {c}, none)` among those whose level is within `ai_level_spread_max` (Utility AI, 10) of the leader's level. Ties: higher level, then lower `member_id`.
2. **Form.** Sort the remaining free groupable members by level descending, then `member_id` ascending. While at least two remain: the first is the leader of a new party. Candidates are the others whose level is at least the leader's level − `ai_level_spread_max` (the leader is the highest remaining, so no candidate is above). Add candidates by the same rule as Fill until the party is full or no candidate remains. If no candidate exists, the leader stays free and is skipped for the rest of this pass. Otherwise the party is created (event 1301) and its members leave the list.
3. **Hand over.** Return, in ascending `party_id`, one group per **Assembled** party that has at least one member who is `idle` with a hunt intent (its roster by R9), then one group of one per free member with a hunt intent who was not grouped. A party that is OnTrip (States and Transitions) is never handed over, and its members who are at the guild (added during the trip, R4) are **held**: they are in neither a party group nor a group of one until the trip closes and the party is Assembled again. This keeps "a member keys at most one trip at a time" (R5). The Member state machine asks Utility AI `choose_ground` for each group and submits trip starts to Zones (Utility AI call sequence, steps 3–4).

**The pass adds a member even when the score gain is zero or negative**, because party size is Party's rule: a fifth member always raises F1 and kill speed. The score only decides *which* candidate. Because Utility AI counts the buffer bonus once per roster (Utility AI R11), a party that already has a buffer prefers anything else, so scarce buffers spread over parties before doubling up.

The pass draws no random numbers. Its result depends only on member IDs, levels, schools, traits and the existing records, so the same state always gives the same parties.

**R4 — Manual formation and edits.** The player edits parties with the commands of R13. Rules:
- A manual party may have any composition within `party_max`, including members outside the level band. The band only limits automatic formation.
- The player may add only a member for whom Member state machine `can(member, join party)` is true (so not `hunting`, `injured`, `training`, `away` …). A member in another party is moved out of it (R8 applies to that party).
- **Edits never touch a trip in progress.** If the party is OnTrip, the record changes at once, but the trip's roster is fixed (Zones Edge Cases). A member removed during a trip finishes it, then becomes free. A member added while the party is OnTrip waits at the guild (their hunt intents expire and renew, Member state machine R10) and joins the next trip.
- On the free tier an edited party is not otherwise protected: R3 Fill and R8 still apply. Locking (R11) is the Premium protection.

**R5 — Key identity: `party_id` and `trip_ordinal`.** Combat, Items and Zones key every encounter on `[party_id, trip_ordinal, encounter_ordinal]` (Zones R5, F9). Party supplies the first two:
- `party_id` = the `member_id` of the trip's key leader: the party's slot-0 member, the lowest-slot present member if the leader is absent (R9), or the lone member of a solo trip.
- `trip_ordinal` = that member's `trips_led` before the trip. Zones calls `begin_trip(party_id)` at trip start; it returns the counter and then increases it by 1. Party saves `trips_led` for every member who has led a live trip. It never decreases or resets, whatever happens to the member's parties.

The pair is unique for the life of the save: member IDs are never reused (Member model R2), a member leads at most one trip at a time (one party, one trip), and each counter only grows. No guild-wide counter is involved, so one party's re-formation never shifts another party's dice (RNG R5), and disbanding and re-forming a party under the same leader does not give new dice. (This answers Zones OQ-5 and Combat PROVISIONAL-3. Zones R5 calls `party_id` "never reused"; under this rule the *pair* is unique, not the ID. Open Questions OQ-1.)

**R6 — Leader.** Set at creation: in automatic formation, the first member picked (R3); in manual creation, the first member named; `set_leader` changes it. It does not change when levels change. If the leader leaves the party, the remaining member with the highest level becomes leader (ties: lower `member_id`) and moves to slot 0, and event 1305 is emitted. The party's ID changes with its leader (R1); 1305 lets the UI and logs follow it.

**R7 — The party XP bonus.** For a trip roster of `n` members, `xp_mult_ppm` is F1. Zones reads it once at trip start and keeps it for the trip (Zones R6). A solo trip gets exactly 1,000,000. "Has a buffer" means a roster member's school has `buff_role = true` (Schools R2), or the party's banner is active (R12). "Has a tank" means a roster member's school role is `tank` or `tank_guardian` (the set of Combat R10 and Utility AI F3).

*Difference from the reference:* `sim/formulas.py` gives a solo buffer or tank the role bonus (`party_xp_mult(1, True, …) = 1.10`). This design conforms to Zones F1 ("a solo member, who gets no party bonus"), which is also what "party bonus" means in §6.12. Solo `moc_1`, `tho_1` and `kim_1` level up to 10% slower than in the reference. Open Questions OQ-2.

**R8 — Leaving and disbanding.** A member leaves their party, and a party left with fewer than 2 members is disbanded (1302), in these cases:

| # | Trigger | Applies to | Checked |
|---|---|---|---|
| 1 | Member enters `away` or leaves the roster (Retention 16) | All parties | When the Member state machine reports the transition |
| 2 | Member enters `training` (school change, Schools R4; Member state machine) | All parties | Same. Schools requires refusing an *assignment* while changing; leaving an existing party is the matching rule |
| 3 | Member becomes `elder` (Rebirth and Ascension 23) | All parties | Same |
| 4 | Member's level differs from the leader's by more than `party_level_spread_disband` | Unlocked only | When the party becomes Assembled after a trip |
| 5 | Member missed `party_absent_trips_max` consecutive trip starts (R9) | Unlocked only | At each trip start |
| 6 | Player removes the member or disbands the party (R13) | All parties | When the command applies |

A member who leaves becomes free. `party_level_spread_disband` (15) is larger than `ai_level_spread_max` (10), so a party formed at the edge of the band does not dissolve after one level-up.

**R9 — Trip roster and absent members.** A party's roster for a trip is its members, in slot order, who are `idle` with a hunt intent at the hand-over (R3 step 3). Because a party rests as one group after each trip (Member state machine R7: every member leaves rest on the same tick and decides at once), a healthy party is normally complete. A member who is not ready (dead and waiting to revive, injured, resting for fatigue) is *absent*: the trip starts without them and their `absent_streak` grows by 1; a member who goes has their streak reset to 0. In an unlocked party, a streak reaching `party_absent_trips_max` (2) makes the member leave (R8 row 5); a locked party keeps them. If the leader is absent, the trip's key uses the present member in the lowest slot (R5); the record's leader does not change.

**R10 — Solo flag.** `set_solo(member, on)` keeps a member out of automatic formation. The player may still add them by hand, which clears the flag. A solo member hunts alone when they have a hunt intent.

**R11 — Premium features.** The command appliers read Premium from the injected entitlement snapshot (Entitlement and feature flags, 32) and refuse a free-tier attempt with `PARTY_PREMIUM_REQUIRED` (Command layer R14). The automatic rules do not depend on the tier.
- **Lock** (`set_party_lock`). A locked party is skipped by Fill, and R8 rows 4 and 5 do not remove its members. Hard triggers and the player's own edits still apply. If Premium lapses, locks stay in force and can still be switched off.
- **Re-arrange all** (`rearrange_all`, "Tự động xếp đội"). Every unlocked, Assembled party is disbanded (1302 reason 3), and Form (R3 step 2) runs at once over all free members who pass R2 rules 1, 2 and 4 (a hunt intent is not required). The greedy search then works over the whole guild, not only over the members who happen to be free. OnTrip and locked parties are not touched.
- **Presets** (`save_preset`, `apply_preset`). Up to `party_preset_slots` (5) saved lists of 2–5 member IDs. Applying one forms a party from the preset's members who are on the roster, pass `can(join party)` and are not in a locked party, in the preset's order, taking them out of their current parties first. If fewer than 2 qualify, it is refused with `PARTY_TOO_FEW`. The new party is locked.

The free tier keeps automatic formation and every manual edit (§6.12: "Ở Free vẫn có ghép đội tự động cơ bản và chỉnh tay").

**R12 — Lệnh Kỳ banner (`item_banner`).** `use_banner(party_id)` takes one `item_banner` from guild storage (Items `take`; Items R9 lists it as guild-held and consumed by Party) and sets `banner_until_tick = max(banner_until_tick, N) + dur_min × 60 × tick_rate`, with `dur_min` from the item's `stats` (30 today). While `N < banner_until_tick`, the party counts as having a buffer for F1 and for the warning (R15). This is the GDD §2 fallback for a guild short of buffer schools. It affects the in-fight buffer bonus only if Combat accepts a group flag (OQ-6). With none in storage the command is refused with `PARTY_NO_BANNER`.

**R13 — Commands.** Block 1300–1399 (Command layer R2). All host-origin. Refusals change nothing.

| ID | Command | Args | Rule | Reason codes |
|---|---|---|---|---|
| 1301 | `create_party` | 2–5 member `entity` (first = leader) | R4 | `PARTY_MEMBER_UNAVAILABLE`, `PARTY_DUPLICATE_MEMBER`, `PARTY_TOO_FEW` |
| 1302 | `add_to_party` | party `entity`, member `entity` | R4 | `PARTY_NOT_FOUND`, `PARTY_FULL`, `PARTY_MEMBER_UNAVAILABLE` |
| 1303 | `remove_from_party` | member `entity` | R8 | `PARTY_NOT_IN_PARTY` |
| 1304 | `disband_party` | party `entity` | R8 | `PARTY_NOT_FOUND` |
| 1305 | `set_party_lock` | party `entity`, on `int(0, 1)` | R11 | `PARTY_NOT_FOUND`, `PARTY_PREMIUM_REQUIRED` (lock on only) |
| 1306 | `set_solo` | member `entity`, on `int(0, 1)` | R10 | `PARTY_MEMBER_UNAVAILABLE` |
| 1307 | `use_banner` | party `entity` | R12 | `PARTY_NOT_FOUND`, `PARTY_NO_BANNER` |
| 1308 | `rearrange_all` | none | R11 | `PARTY_PREMIUM_REQUIRED` |
| 1309 | `save_preset` | slot `int(1, party_preset_slots)`, party `entity` | R11 | `PARTY_NOT_FOUND`, `PARTY_PREMIUM_REQUIRED` |
| 1310 | `apply_preset` | slot `int(1, party_preset_slots)` | R11 | `PARTY_PRESET_EMPTY`, `PARTY_TOO_FEW`, `PARTY_PREMIUM_REQUIRED` |
| 1311 | `set_leader` | member `entity` | R6 | `PARTY_NOT_IN_PARTY` |

`create_party` uses 5 of the 6 argument slots. Reason-code numbers are assigned in the implementation story (→ ADR with the command table, OQ-8). Applier cost is O(`party_max`), except `rearrange_all`, which runs one Form (F3).

**R14 — Interfaces provided.**
- `groups_for_trips(N) -> ordered list of (party_id, roster)` (R3), called by the Member state machine in its P2 pass.
- `begin_trip(party_id) -> trip_ordinal` (R5), called by Zones at trip start.
- `xp_mult_ppm(roster, party_id, N) -> int` (F1), called by Zones at trip start.
- `party_of(member_id)`, `members_of(party_id)`: membership, for Offline (31), Retention (16, hourly bond slot), Golden Boss (14) and the screens.
- `parties_for_raid(participants) -> ordered list of (party_id, participants in slot order)` (R16).
- `has_buffer(party_id, N)`, `has_tank(party_id)`, `group_bonus(roster, target_element)` (F2): read-only.

**R15 — Warnings.** For the guild screens (39), Party derives per party `no_buffer` (F1's `B = 0` over all members), `no_tank` and `level_spread` (max − min level); Utility AI's fit badges show the score breakdown (Utility AI UI Requirements). Guild-wide, "fewer buffers than parties" is `buffer_count < party_count`; Recruitment (15) may read it for its buffer-candidate boost (GDD §2, S1 `recruit_buffer_boost`).

**R16 — Raid groups.** Golden Boss (14) owns who takes part and its grouping (Golden Boss R7). Party supplies step 1 of that rule: `parties_for_raid(participants)` returns each existing party with at least one participant, in ascending `party_id`, its participants in slot order. Golden Boss builds the temporary groups for everyone else with the reference `form_parties()` rule (its R7 step 2), which keeps raid parity with `sim/raid.py`. Temporary groups are not party records. (§6.13 says temporary groups use "the same algorithm as 6.12". Party accepts Golden Boss's choice for parity and does not supply its own; OQ-4.)

**R17 — Bonds are Retention's.** Retention (16, R9) grows a bond each game hour for every pair in the same party at the hour slot, reading `party_of`. Party only keeps parties stable, which is what makes bonds possible. Party does not read bonds in MVP; if a bond term is added to formation later, it enters through Utility AI's F3 (Utility AI R12).

**R18 — Events.** Block 1300–1399 (Event bus R3). Payload `a, b, c, d`. All are logged ring events; none is a milestone.

| ID | Name | a | b | c | d |
|---|---|---|---|---|---|
| 1301 | `party_formed` | party_id | size | flags (bit 0 buffer, bit 1 tank, bit 2 manual) | 0 |
| 1302 | `party_disbanded` | party_id | reason (1 player, 2 too few, 3 re-arrange, 4 preset) | size before | 0 |
| 1303 | `party_member_joined` | party_id | member_id | slot | 0 |
| 1304 | `party_member_left` | party_id | member_id | R8 row (1–6) | 0 |
| 1305 | `party_leader_changed` | old party_id | new party_id | 0 | 0 |
| 1306 | `party_banner_used` | party_id | until tick, low 32 bits | 0 | 0 |

Form emits 1301 and then one 1303 per member in slot order (the leader included); `disband_party` and a disband by R8 emit 1302 only, with no 1304 per member (F4's peak counts this way).

CA/PA's `event:party_hunt` reveal ("completes a hunt trip in a party of 2 or more") can be read from Zones 1104 with the trip's roster size (Zones 1101 `c`); Party adds no event for it.

**R19 — Saved state.** Party registers one serializer with Local save (6): the party records (R1), `trips_led` per member, solo flags and presets. Its invariant check (Local save `check()`) reports an error if a member is in two parties, a party has fewer than 2 or more than `party_max` members, a `party_id` differs from its slot-0 member, or a member in a party is not on the roster. The `party_of` index is rebuilt on load. If `party_max` was lowered by a patch, the members beyond it (highest slots first) leave on load (1304 on the first tick).

**R20 — Offline.** Offline progress (31) samples each party with its available members and each free member solo (Offline R6), reading membership at the hand-off tick. During the gap, parties do not form, change or disband. Sampled trips use Offline's own RNG keys (domain 5), so they do not call `begin_trip` and do not advance `trips_led`. After the gap, the first live P2 pass applies R8 and R3 as usual.

### States and Transitions

A party record has two live states and a terminal one. OnTrip is not stored: it is true while Zones has an active trip whose roster includes a member of the party.

| State | Meaning | Automatic rules active |
|---|---|---|
| `Assembled` | At the guild between trips | Fill (R3, unlocked), drift (R8 row 4, unlocked), absence at trip start (R8 row 5, unlocked) |
| `OnTrip` | A trip with its members is in progress | None. Edits change the record only (R4) |
| `Disbanded` | Terminal; the record is deleted | — |

| From | To | Trigger |
|---|---|---|
| (none) | `Assembled` | Form (R3), `create_party`, `apply_preset` |
| `Assembled` | `OnTrip` | Zones starts a trip with its roster (1101) |
| `OnTrip` | `Assembled` | The trip closes (Zones R10, after the group rest) |
| `Assembled` | `Disbanded` | Fewer than 2 members after R8, `disband_party`, `rearrange_all` (unlocked), `apply_preset` taking members |
| `OnTrip` | `Disbanded` | Fewer than 2 members after a hard trigger or a player edit; the trip continues with its fixed roster |

Per member: *free* ↔ *in a party*. Membership and Member state machine states are independent, except that `can(join party)` gates joining (R2, R4).

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|---|---|---|---|---|
| Member model (8) | in | Roster, `member_id` (never reused), `level`, `rank` | — | Member model |
| Schools (20) | in | `role`, `buff_role`, `element` | — | Schools |
| Utility AI (12) | in | `composition_score(roster, t)` (F3), `ai_level_spread_max` | Groups for `choose_ground` (via MSM) | Utility AI owns the score; Party owns the search (Utility AI R11) |
| Member state machine (41) | both | Hunt intents, `can(join party)`, `away` / `training` / `elder` transitions; calls `groups_for_trips` | Groups | MSM owns states and the P2 pass |
| Zones and hunt (11) | out | 1101, trip close | `begin_trip`, `xp_mult_ppm`, `party_id` | Party owns roster and key identity |
| Combat (10) | out | — | Group membership and slot order; proposed `group_bonus` (F2) | Party owns composition |
| Golden Boss (14) | out | Participants | `parties_for_raid` (R16) | Golden Boss owns participation and temp groups |
| Offline progress (31) | out | — | Membership at the hand-off tick (R20) | Offline drives |
| Retention (16) | out | — | `party_of` at each hour slot | Retention owns bonds |
| Recruitment (15) | out | — | Guild buffer shortfall (R15) | Recruitment owns the rate |
| Items and loot (26) | in | `take(item_banner)`; item `stats` | — | Items owns storage and `suited_first` |
| Command layer (5) | in | Commands 1301–1311 | Reason codes | Party owns appliers |
| Event bus (42) | out | — | Events 1301–1306 | Party owns the types |
| Local save (6) | both | Restore | Serializer, `check()` | Local save |
| Entitlement (32) | in | Premium in the snapshot | — | Entitlement |
| Guild screens (39), World view (38) | out | — | Records, warnings, events | Screens read and send commands |

## Formulas

All formulas are integer. Fractions are parts per million (ppm); float config values are converted once at boot as `round(value × 10⁶)` (as Member model F3). Values are today's from `data/config.csv`; keys marked *proposed* do not exist yet (OQ-5).

### F1 — `xp_mult_ppm`

The xp_mult_ppm formula is defined as:

`xp_mult_ppm = 1,000,000` if `n = 1`; otherwise
`xp_mult_ppm = 1,000,000 + per_member_ppm × (n − 1) + buffer_ppm × B + tank_ppm × T − no_buffer_ppm × (1 − B)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n | int | 1 – 5 | calculated | Roster size at trip start (R9) |
| per_member_ppm | int | 0 – 150,000 | data file (`party_xp_per_member` 0.08 → 80,000) | Bonus per extra member |
| buffer_ppm | int | 0 – 300,000 | data file (`party_buffer_bonus` 0.10 → 100,000) | Bonus when B = 1 |
| tank_ppm | int | 0 – 200,000 | data file (`party_tank_bonus` 0.05 → 50,000) | Bonus when T = 1 |
| no_buffer_ppm | int | 0 – per_member_ppm | data file (`party_no_buffer_penalty` 0.0 → 0) | Penalty when B = 0 and n ≥ 2 |
| B | 0/1 | — | calculated | A roster member has `buff_role = true`, or the banner is active (R12) |
| T | 0/1 | — | calculated | A roster member's role is `tank` or `tank_guardian` |

**Output Range:** 1,000,000 (solo) to 1,470,000 today (5 members, buffer and tank). Because `no_buffer_ppm ≤ per_member_ppm` is checked at load, an n ≥ 2 party is never below 1,000,000. A load with `no_buffer_ppm > per_member_ppm` is refused.
**Example:** 5 members with `moc_1` and `tho_1`: `1,000,000 + 80,000 × 4 + 100,000 + 50,000 = 1,470,000`, matching Zones F1. `kim_2`, `hoa_2`, `tho_1`: `1,000,000 + 160,000 + 50,000 = 1,210,000`. Adding a `moc_1` gives 1,390,000; adding a fourth DPS instead gives 1,290,000. The buffer is worth more than an extra body, which is the §2 rule in numbers.

Zones F1 divides kill XP by `n` after this multiplier, so each member of a full party gets 0.294 of a solo kill's XP; parties still out-level solo hunters because they kill far faster and safer (GDD §4.3: the standard party reaches L100 in about 71 h, the best solo school in 4.2 days).

### F2 — `group_bonus` (proposed; shipped at 0)

The group_bonus formula is defined as:

`group_atk_add_ppm = sinh_atk_ppm × links + cover_atk_ppm × K`
`group_dmgred_add_ppm = sinh_dmgred_ppm × links`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| links | int | 0 – 5 | calculated (Utility AI F3 `sinh_links` over the trip roster; tương sinh Mộc→Hoả→Thổ→Kim→Thuỷ→Mộc, GDD §4.2) | Generation links present |
| K | 0/1 | — | calculated (Utility AI F3 `counters(t)` with `t` = the target's element) | Someone counters the target |
| sinh_atk_ppm | int | 0 – 20,000 | data file (proposed `party_sinh_atk_per_link`; proposed live 15,000; shipped 0) | Attack bonus per link |
| sinh_dmgred_ppm | int | 0 – 15,000 | data file (proposed `party_sinh_dmgred_per_link`; proposed live 10,000; shipped 0) | Damage-taken reduction per link |
| cover_atk_ppm | int | 0 – 50,000 | data file (proposed `party_counter_cover_atk`; proposed live 30,000; shipped 0) | §6.12 "Phủ khắc hệ" bonus |

**Output Range:** shipped: 0 (parity with the reference). At the proposed live values: attack 0 to +105,000 ppm (+10.5%), reduction 0 to 50,000 ppm (5%). On top of Combat R8's buffer bonus (+8% attack, 10% reduction) the largest group total is +18.5% and 15%, still below what a buffer adds, so the buffer remains the main lever (§2). At the top of every safe range the reduction is 10% + 75,000 ppm = 17.5%, far below 1.
**Example:** kim, thuy, moc against a Thổ target: links 2 (Kim→Thuỷ, Thuỷ→Mộc), K = 1 (Mộc counters Thổ): attack `2 × 15,000 + 30,000 = 60,000` ppm, reduction `20,000` ppm.
**Status:** this is Party's answer to Combat OQ-6. Combat's encounter (R3) has no field for it, so it needs a Combat change and a balance re-measure before going live (OQ-6). These are combat bonuses, separate from Utility AI's `ai_sinh_link_ppm`, which is only a formation score weight (Utility AI Tuning Knobs).

### F3 — Formation pass cost

`calls_pass ≤ P × (party_max − 1) × P`, with `P` the free groupable members (≤ 80, the top of `member_cap` 12–80, Guild and buildings F2) and one call = one Utility AI `composition_score` on ≤ 5 members.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| P | int | 0 – 80 | calculated | Free groupable members at the pass |
| party_max | int | 5 | data file (`party_max`) | Party size cap |

**Output Range:** 0 (no free members: the pass returns existing groups only) to 25,600 score calls (`rearrange_all` over 80 members: `80 × 4 × 80`). Typical: a party returns and Fill looks at 0–3 free members, under 20 calls.
**Example:** 12 free members after a re-arrange: at most `12 × 4 × 12 = 576` calls. Planning statement for Sim core's per-phase budget; measured in AC-24.

### F4 — Event volume (Event bus F1, F4)

`ring_per_day(1300 block) = 800` at the max-roster fixture (80 members, 16 parties). PROVISIONAL until AC-25 measures it.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| ring_per_day | int | ≥ 0 | constant (declared here) | Peak ring records per 86,400 game seconds |

**Output Range:** the declared bound is 800, PROVISIONAL. Rationale: membership events follow homecomings (about 6 per party-hour × 16 parties × 24 h ≈ 2,300 homecomings a day), and the bound assumes at most about a third of them change membership (drift, absence, fills); the earlier 400 at 40 members is scaled linearly with the roster. The share is not derived from a rule; AC-25 measures it and the number is replaced by the measurement. Peak per tick: one `rearrange_all` emits at most 16 disbands + 16 forms + 80 joins = 112 records (R18: Form emits one 1303 per member, disband no 1304).
**Example:** a stable guild with no level drift emits 0 per day; AC-25 measures the fixture and this number is raised in the same change if a rule raises it.

## Edge Cases

- **If the guild has no buffer at all**: parties form by score and level with B = 0; F1 gives no buffer bonus; every party shows "thiếu buffer"; R15's guild warning is on. Nothing is refused (§6.12 "vẫn chạy được").
- **If buffers are fewer than parties**: Fill serves existing parties in ascending `party_id` first, then Form serves the highest-level leaders first. Lower-level groups go without. Deterministic and visible; the player may move a buffer by hand or use a banner (R12).
- **If only one member is free**: no party forms; they hunt alone when they have an intent.
- **If two free members are more than `ai_level_spread_max` apart**: no automatic party; both hunt alone. A manual party is allowed (R4).
- **If a member levels past the band during a trip**: nothing changes until the party is Assembled; then R8 row 4 (15-level limit) applies, unlocked only.
- **If the leader levels far above everyone**: the leader stays leader; members beyond 15 levels leave by drift one by one; with one member left, the party disbands. A locked party keeps them.
- **If the leader dies on a trip**: the trip continues (Zones). If still dead at the next trip start, they are absent (R9); the key uses the present member in the lowest slot.
- **If every member of a party is absent**: no group is handed over; the party waits Assembled. Streaks grow only at trip starts, so it does not dissolve by itself. Accepted: an injured party waits for its members; the player can disband it.
- **If a member is added to an OnTrip party**: they wait at the guild; they are re-asked every `ai_reask_ticks` (Utility AI knob used by Member state machine R10), and Party never hands them over alone, because a member in a party hunts only with their party (R3 step 3).
- **If the player removes the last-but-one member during a trip**: the party is disbanded at once (OnTrip → Disbanded); the trip continues with its fixed roster and key; at trip close all are free.
- **If `create_party` names a member who is `hunting`**: refused with `PARTY_MEMBER_UNAVAILABLE` (Member state machine capability table: join a party, `hunting` = no).
- **If `create_party` names one member twice**: refused with `PARTY_DUPLICATE_MEMBER`.
- **If any add command names a member in `training` or `injured`**: refused with `PARTY_MEMBER_UNAVAILABLE` (Schools AC-26, Member state machine AC-19).
- **If a member leaves and later returns under the same `member_id`**: their `trips_led` continues from its saved value, so their keys never repeat. A returner under a new ID starts at 0 and is still unique.
- **If the player disbands and re-forms a party to re-roll a trip**: no new dice; the same leader's next ordinal is used either way (R5). Choosing a different leader uses that member's next ordinal: a different but fixed sequence, so the re-roll space is at most one sequence per member, each costing a trip.
- **If the player reloads and changes the party before a trip**: same leader and ordinal, so the same dice on new inputs (RNG R5; Combat Edge Cases).
- **If a banner expires mid-trip**: F1 was read at trip start and holds for the trip; the next trip has B = 0.
- **If a banner is used while one is active**: the time adds on (R12); no item is wasted.
- **If Premium lapses**: locks stay; presets stay saved but cannot be applied or saved; `set_party_lock(…, 0)` is still allowed.
- **If a preset names a member who has left**: that member is skipped; fewer than 2 left is `PARTY_TOO_FEW`.
- **If only one member of a party takes part in a raid**: `parties_for_raid` still returns that party with one participant (Golden Boss R7 step 1: "at least one participant").
- **If a save holds a member in two parties**: `check()` reports it and Local save's load-failure rule applies; Party never silently picks one.
- **If `party_max` is raised by a patch**: parties stay as they are; Fill tops them up.
- **Degenerate strategy: all-buffer party.** Five `moc_1` get B once and low damage (role dps 0.55); Combat makes it slow. F1's single buffer term, Utility AI's once-per-roster buffer score and Combat R8's no-stack rule leave no exploit.
- **Degenerate strategy: parties of 2 for XP.** Each member gets 1.08 / 2 = 0.54 of a solo kill's XP but kills faster; no special rule. Checked by the balance gate (AC-23).

## Dependencies

### Upstream (this system depends on)

| System | Hard/Soft | Interface | Status |
|---|---|---|---|
| Member model (8) | Hard | Roster, `member_id` (never reused, R2), `level`, `rank` | Designed — conforms |
| Schools and school change (20) | Hard | `role`, `buff_role`, `element`; `training` during a change | Designed — conforms |
| Utility AI (12) | Hard | `composition_score` (F3), `ai_level_spread_max`; `choose_ground` for the groups | Designed — conforms (R11, call sequence) |
| Member state machine (41) | Hard | Calls `groups_for_trips` in its P2 pass; hunt intents; `can(join party)`; `away`, `training`, `elder` transitions | Designed — conforms (R10, capability table) |
| Items and loot (26) | Soft | `take(item_banner)`; item `stats` | Designed — conforms (R9) |
| Data layer (3) | Hard | `config.csv` party keys; `schools.csv`; `items.csv` | Designed |
| Command layer (5), Event bus (42), Local save (6) | Hard | Command and event block 1300, serializer + `check()` | Designed |
| Entitlement and feature flags (32) | Soft | Premium in the injected snapshot | Designed |
| CA/PA and traits (9) | Soft | Only through Utility AI F3 (`party_synergy`) | Designed |

### Downstream (systems that depend on this one)

| System | Hard/Soft | Interface | Status |
|---|---|---|---|
| Zones and hunt trips (11) | Hard | `begin_trip`, `xp_mult_ppm`, `party_id`, groups via MSM | Designed — its PROVISIONAL on 13 answered (R5, F1) |
| Combat (10) | Soft | Groups and slot order; proposed `group_bonus` | Designed — OQ-6 answered by F2 (shipped 0) |
| Golden Boss and guild raid (14) | Hard | `parties_for_raid` (R16) | Designed — its PROVISIONAL-1 answered (Party keeps its R7 step 2) |
| Offline progress (31) | Hard | Membership at the hand-off tick (R20) | Designed — its OQ-4 answered |
| Retention (16) | Soft | `party_of` at each hour slot | Designed — conforms (R9) |
| Recruitment (15) | Soft | Guild buffer shortfall (R15) | Designed |
| Guild screens (39), World view (38) | Soft | Records, warnings, events | Designed |
| Dev tooling and parity harness (43) | Soft | Golden vectors for F1 and the formation pass | Designed |

**Bidirectional check.** The systems index lists Party as depending on Member model, CA/PA and traits, Combat and Utility AI; this GDD adds Schools and Member state machine to that row (Combat is a consumer here, and CA/PA is reached only through Utility AI). Zones, Combat, Schools, Member model, XP curve, Utility AI, Member state machine, Golden Boss, Offline and Retention already list Party.

## Tuning Knobs

| Knob | Current | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `party_max` | 5 | 2 – 5 (locked by §2) | — | Parties cannot hold all roles | Every rule; Items bag capacity (`bag_slots × n`) |
| `party_xp_per_member` | 0.08 | 0 – 0.15 | Big parties dominate; solo pointless | Grouping pays only in kill speed | `party_no_buffer_penalty` (must stay ≤) |
| `party_buffer_bonus` | 0.10 | 0 – 0.30 | No-buffer parties feel broken | "Thiếu buffer" not true in XP | Combat `buffer_atk`, `buffer_dmg_reduction` |
| `party_tank_bonus` | 0.05 | 0 – 0.20 | Tanks mandatory | Tanks matter only for survival | — |
| `party_no_buffer_penalty` | 0.0 | 0 – `party_xp_per_member` | Refused at load above the bound | — | `party_xp_per_member` |
| `party_level_spread_disband` (proposed) | 15 | `ai_level_spread_max` – 40 | Mismatched parties linger | Parties dissolve after one level-up | `ai_level_spread_max` (Utility AI) |
| `party_absent_trips_max` (proposed) | 2 | 1 – 10 | Parties wait on long-injured members | Members dropped after one missed trip | Member state machine injury and rest times |
| `party_preset_slots` (proposed) | 5 | 1 – 10 | UI clutter | Premium feature thin | — |
| `party_sinh_atk_per_link`, `party_sinh_dmgred_per_link`, `party_counter_cover_atk` (proposed) | 0 shipped | F2 table | Element harmony outweighs buffers | No harmony effect (today) | Combat `buffer_*` |

**Owned elsewhere and read here:** `ai_level_spread_max` and every `composition_score` weight (Utility AI 12); `buffer_atk`, `buffer_dmg_reduction` (Combat 10); `item_banner` duration (`items.csv`, Items 26); `ai_reask_ticks` (Utility AI 12, used by Member state machine 41); bond rates (Retention 16); `member_cap` (Guild and buildings 30).

## Visual/Audio Requirements

*Art-director lens applied. No `design/art/art-bible.md` exists; drafted from GDD §12.4 (AI-assisted pixel art, code-drawn minimal style as the fallback) and the Combat and Zones Visual/Audio sections.*

| Event | Visual | Audio |
|---|---|---|
| Party formed (1301) | Members gather at the guild gate; a small banner in the party's colour appears over the leader | Short drum roll; suppressed if several form within 1 s |
| Member joins / leaves (1303/1304) | A colour ring appears / fades under the member | None (too frequent) |
| No buffer | A "thiếu buffer" tag with a crossed-cross icon over the leader's banner and on the party card (text and icon, never colour alone) | None |
| Banner used (1306) | The leader's banner becomes a gold Lệnh Kỳ flag for its duration | Cloth snap |
| Leader changed (1305) | The banner moves to the new leader | None |
| Disbanded (1302) | The banner folds; rings fade | None |

**Style constraints.** Party colour is one of 8 fixed hues by on-screen party slot, paired with a shape mark (circle, square, triangle …) so it is never read by colour alone. The banner sits above the head layer of the paper-doll set and fits the 15-full-sprite raid budget (§6.13); Golden Boss's temporary groups use the same banner with a "temp" mark.

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:party` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

- **No input timing.** The player never acts in real time here; feel targets are edit responsiveness and readability.
- **Edits land in one tick.** A drag-and-drop edit is a command applied in the next P1 (≤ 100 ms at 10 Hz); the card updates in the next presented frame. No "saving…" state.
- **The fix is felt.** After adding a buffer, the card shows the new F1 multiplier at once (×1.29 → ×1.39 in the F1 example) and the next trip report shows the XP difference.
- **Auto never fights the player.** Fill only adds to open slots; drift and absence run only when a party is home. A player who wants a permanent arrangement locks it (Premium) or flags members solo (free).

## UI Requirements

- **Party panel (Guild screens 39).** One card per party: members in slot order with school, role and element icons and level; the leader marked; F1 multiplier; warnings (no buffer, no tank, level spread); Utility AI's fit badges; lock state; banner timer. A "free members" strip below, with solo flags.
- **Edits.** Drag a member between cards or to the free strip; buttons for create, disband, set leader, solo, use banner. Premium buttons (lock, re-arrange all, presets) are visible with a Premium badge and disabled on the free tier, and the UI still handles the applier's refusal (Command layer R14).
- **Guild warning.** A banner on the panel when buffers < parties, with a shortcut to Recruitment's school filter (§6.12 "gợi ý tuyển phái buff").
- **Text.** All labels through Localization (4); "thiếu buffer" is a string key. Cards must fit Vietnamese strings, which run longer than English.

> **📌 UX Flag — Party**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the party panel (cards, free strip, warnings, Premium controls) **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not this GDD directly.

## Cross-References

| This GDD uses | Source | Section | Nature |
|---|---|---|---|
| 5 per party, one buffer per party, Lệnh Kỳ fallback | `JX1_Tycoon_GDD.md` | §2, §6.12 | Locked rules |
| Party schema `{id, leader_id, member_ids[<=5], …}` | `JX1_Tycoon_GDD.md` | §4.1 | Source schema (adapted in R1) |
| Free vs Premium features | `JX1_Tycoon_GDD.md` | §6.12, §11.2 | Source rule |
| Encounter key `[party_id, trip_ordinal, encounter_ordinal]` | `zones-grounds-monsters-and-hunt-trips.md` | R5, F9, OQ-5 | Contract fulfilled by R5 |
| `xp_mult_ppm` read once at trip start; solo gets none | `zones-grounds-monsters-and-hunt-trips.md` | R6, F1 | Contract; F1 matches |
| Groups, slot order, buffer no-stack, tank roles | `combat.md` | R3, R8, R9, R10 | Data dependency |
| Group bonus proposal | `combat.md` | OQ-6 | Answered by F2 |
| Keys hold no counter that unrelated actions advance | `deterministic-rng.md` | R5 | Constraint on R5 |
| `member_id` never reused | `member-model.md` | R2 | Basis of R5 |
| `role`, `buff_role`, `element`; training blocks assignment | `schools-and-school-change.md` | R2, R4, Edge Cases, AC-26 | Data dependency |
| `composition_score`, `ai_level_spread_max`, call sequence | `utility-ai.md` | R2, R11, F3, States and Transitions | Score used by R3 |
| Hunt intents, `can(join party)`, group rest | `member-state-machine.md` | R7, R10, capability table | Inputs to R2, R3, R9 |
| Raid grouping step 1 and temp groups | `golden-boss-and-guild-raid.md` | R7 | R16 supplies step 1 |
| Offline groups from party membership | `offline-progress.md` | R6 | R20 |
| Bonds from party membership | `retention-leaving-and-negotiation.md` | R9 | R17 |
| `item_banner` guild-held, consumed by Party | `items-and-loot-tables.md` | R9 | Data dependency |
| Command and event blocks = system number × 100; owner gates Premium | `command-layer.md`, `event-bus-and-history-log.md` | R2, R14; R3 | Allocation and gating |

## Acceptance Criteria

*QA-lead lens applied: every core rule and formula has at least one criterion; formula criteria test boundaries; cross-system criteria are marked. **Logic** = automated unit test in `tests/unit/party/`; **Integration** = automated test in `tests/integration/party/`; **UI** = retained screenshot in `production/qa/evidence/`; **Playtest** = documented playtest. [PENDING] marks criteria that need a system not yet built.*

- **AC-1 [Logic] (R1, R19)**: **GIVEN** any sequence of fixture commands and passes, **WHEN** `check()` runs after each tick, **THEN** no member is in two parties, every party has 2–5 members, and every `party_id` equals its slot-0 member's ID.
- **AC-2 [Logic] (R3, pick order)**: **GIVEN** free groupable members, all with hunt intents and no traits, `kim_2` L50 (lowest ID), `hoa_2` L50, `tho_1` L48, `moc_1` L45, `thuy_1` L42, and Utility AI's default weights, **WHEN** a pass runs, **THEN** one party forms with slots `kim_2, moc_1, tho_1, hoa_2, thuy_1` (picks scoring 400,000, 640,000, 720,000 with `hoa_2` winning the tie with `thuy_1` by level, then 800,000), and 1301 has the buffer and tank flags.
- **AC-3 [Logic] (R3, band)**: **GIVEN** only two free members at L50 and L39, **WHEN** a pass runs, **THEN** no party forms and two solo groups are handed over. **GIVEN** L50 and L40, **THEN** a party of 2 forms.
- **AC-4 [Logic] (R3, determinism)**: **GIVEN** the same save, **WHEN** the pass runs twice, **THEN** parties, slot orders, events and hand-over order are identical, and a counting generator records 0 draws.
- **AC-5 [Logic] (R3, buffer spread)**: **GIVEN** 10 free members in band, 2 of them `moc_1`, **WHEN** a pass runs, **THEN** two parties of 5 form, each with exactly one `moc_1`.
- **AC-6 [Logic] (R3, fill first)**: **GIVEN** an unlocked Assembled party of 3 and a free in-band `moc_1` with a hunt intent, **WHEN** a pass runs, **THEN** the `moc_1` joins that party (1303) and no new party forms.
- **AC-7 [Logic] (R3, hand-over)**: **GIVEN** a party whose members are all `idle` with hunt intents and one free member with an intent, **WHEN** `groups_for_trips` returns, **THEN** the party's group comes first in `party_id` order, the free member's group of one follows, and a party member never appears in a group of one.
- **AC-8 [Logic] (R4)**: **GIVEN** a party OnTrip, **WHEN** `remove_from_party` applies to one member, **THEN** the record has one fewer member at once, Zones' saved roster is unchanged, and the member is free at trip close.
- **AC-9 [Logic] (R4, refusals)**: **GIVEN** `create_party` with a `hunting` member, the same member twice, or a single member, **THEN** it is refused with `PARTY_MEMBER_UNAVAILABLE`, `PARTY_DUPLICATE_MEMBER` or `PARTY_TOO_FEW`, and state is unchanged.
- **AC-10 [Logic] (R5)**: **GIVEN** member 7 with `trips_led = 11` leading a party, **WHEN** Zones calls `begin_trip(7)`, **THEN** it returns 11 and `trips_led[7]` becomes 12. **WHEN** the party is disbanded and member 7 starts a solo trip, **THEN** `begin_trip(7)` returns 12.
- **AC-11 [Logic] (R5, isolation)**: **GIVEN** parties led by members 3 and 7, **WHEN** party 3 is disbanded and re-formed five times, **THEN** `trips_led[7]` and party 7's next key are unchanged.
- **AC-12 [Logic] (R6)**: **GIVEN** a 3-member party led by 7, with members 9 (L40) and 4 (L40), **WHEN** member 7 leaves, **THEN** member 4 is leader in slot 0, the party ID is 4, and 1305 `(7, 4)` is emitted.
- **AC-13 [Logic] (F1)**: **GIVEN** today's config, **THEN** `xp_mult_ppm` is 1,000,000 for a solo `moc_1`; 1,080,000 for two DPS; 1,210,000 for `kim_2`, `hoa_2`, `tho_1`; 1,470,000 for five with `moc_1` and `tho_1`. **GIVEN** `party_no_buffer_penalty = 0.09`, **THEN** the data load is refused.
- **AC-14 [Logic] (R7, R12)**: **GIVEN** a 3-member party with no buffer school and an active banner, **THEN** F1 has B = 1; **WHEN** `banner_until_tick` has passed, **THEN** B = 0.
- **AC-15 [Logic] (R12)**: **GIVEN** 1 `item_banner` in storage and a banner active until tick T > N, **WHEN** `use_banner` applies, **THEN** storage holds 0 and `banner_until_tick = T + 18,000`. **GIVEN** 0 in storage, **THEN** refused with `PARTY_NO_BANNER`.
- **AC-16 [Logic] (F2)**: **GIVEN** shipped data, **THEN** `group_bonus` is (0, 0) for every roster. **GIVEN** the proposed live values and roster kim, thuy, moc against a Thổ target, **THEN** it is (60,000, 20,000) ppm; **GIVEN** a single-element roster and no counter, **THEN** (0, 0).
- **AC-17 [Logic] (R8, drift)**: **GIVEN** an unlocked party with leader L60 and a member L44, **WHEN** it becomes Assembled, **THEN** the L44 member leaves (1304 row 4). **GIVEN** the same party locked, **THEN** nobody leaves.
- **AC-18 [Logic] (R9, absence)**: **GIVEN** an unlocked party where one member is injured at two consecutive trip starts, **THEN** both trips start without them and after the second they leave. **GIVEN** the leader absent, **THEN** the trip's `party_id` is the present member in the lowest slot and that member's `trips_led` advances.
- **AC-19 [Integration] (R8, hard triggers)**: **GIVEN** a 2-member party, **WHEN** one member enters `training` through a school change, **THEN** the party is disbanded (1302 reason 2) and the other member is free.
- **AC-20 [Logic] (R10)**: **GIVEN** a solo-flagged free member in band with another free member, **WHEN** a pass runs, **THEN** no party forms; **WHEN** the player adds the solo member by hand, **THEN** the flag is cleared.
- **AC-21 [Logic] (R11)**: **GIVEN** a free-tier snapshot, **WHEN** `set_party_lock(…, 1)`, `rearrange_all`, `save_preset` or `apply_preset` is submitted, **THEN** each is refused with `PARTY_PREMIUM_REQUIRED`. **GIVEN** Premium, **WHEN** `rearrange_all` applies, **THEN** every unlocked Assembled party is disbanded and Form runs once; locked and OnTrip parties are unchanged. [PENDING: Entitlement 32 snapshot]
- **AC-22 [Integration] (R16)**: **GIVEN** 12 raid participants: 5 of a full party, 1 of a second party and 6 free members, **WHEN** Golden Boss builds its groups, **THEN** `parties_for_raid` returns the full party, then the second party with 1 participant, and no party record is created for Golden Boss's temporary groups.
- **AC-23 [Integration, Balance] (F1, R7)**: **GIVEN** `tools/balance_sim.py --quick` after the R7 solo change, **WHEN** run, **THEN** party and solo L100 times stay within Dev tooling's budget bands, and solo `moc_1` and `tho_1` times before and after are reported. [PENDING: S9 budget table]
- **AC-24 [Performance] (F3)**: **GIVEN** the max-roster fixture (80 free groupable members, 25,600 score calls at most), **WHEN** `rearrange_all` runs on the min-spec device, **THEN** the P1 applier stays within Sim core's per-phase budget. [PENDING: P1 spike]
- **AC-25 [Integration] (F4)**: **GIVEN** the max-roster fixture simulated for 24 game hours, **WHEN** the 1300-block ring records are counted, **THEN** they are ≤ 800, and the measured value replaces F4's provisional bound.
- **AC-31 [Logic] (R3 hand-over)**: **GIVEN** a party OnTrip and a member added to it by `add_to_party` who is `idle` with a hunt intent, **WHEN** `groups_for_trips` returns, **THEN** neither that party nor a group of one containing that member is in the list; **WHEN** the trip closes and the party is Assembled, **THEN** the next pass hands the party over with that member in its roster.
- **AC-26 [Integration] (R20)**: **GIVEN** an 8-hour offline gap, **WHEN** Offline fast-forwards it, **THEN** no Party event is emitted during the gap, the parties at its end equal those at its start, and no `trips_led` value changed.
- **AC-27 [Logic] (R19, load)**: **GIVEN** a save with a party of 5 and `party_max` patched to 4, **WHEN** it loads, **THEN** the slot-4 member is free and one 1304 is emitted on the first tick.
- **AC-28 [Integration] (Zones R5, R6)**: **GIVEN** a 5-member party with buffer and tank, **WHEN** Zones starts a trip, **THEN** the trip records `xp_mult_ppm = 1,470,000` and its first encounter key is `[leader member_id, pre-increment trips_led, 0]`.
- **AC-29 [UI]**: **GIVEN** a guild with one party missing a buffer, **WHEN** the party panel is open, **THEN** a retained screenshot in `production/qa/evidence/` shows that card's "thiếu buffer" tag with its icon, the F1 multiplier on every card, and the guild warning. [PENDING: Guild screens 39]
- **AC-30 [Playtest] (Player Fantasy)**: **GIVEN** a tester shown the party panel with one card lacking a buffer, **WHEN** asked what to fix, **THEN** they name the missing buffer within 10 seconds, and after moving one in they can point to the changed multiplier.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Key identity wording (R5).** `party_id` is the key leader's `member_id`; `trip_ordinal` is that member's `trips_led`. Zones R5/R16 ("never reused", "stored on Party's record") and Combat's key note should be reworded to "unique pair; per-leader counter". | Consistency pass; Zones (11), Combat (10) | Next `/consistency-check` |
| OQ-2 | **Solo bonus parity (R7).** `sim/formulas.py` gives a solo buffer or tank the role bonus; this GDD and Zones F1 do not. Change the reference in the implementation story, then re-run `calibrate.py` and `balance_sim`. | Implementation story; Dev tooling (43) | With Zones OQ-3 |
| OQ-3 | **`in_party` state and a member `party_id` field (§4.1, §6.12).** Kept out (R1). If anything needs them, derive from `party_of`. | Member state machine (41), Member model (8) | Consistency pass |
| OQ-4 | **Raid temporary groups.** §6.13 says they use the 6.12 algorithm; Golden Boss R7 keeps `form_parties()` for parity, and Party does not override it. Revisit after the P1 spike if raid groups should match hunting groups. | Golden Boss (14), user | After the P1 spike |
| OQ-5 | **New config keys (schema change, not made in this autonomous run).** `party_level_spread_disband`, `party_absent_trips_max`, `party_preset_slots`, `party_sinh_atk_per_link`, `party_sinh_dmgred_per_link`, `party_counter_cover_atk`; validator checks `party_no_buffer_penalty ≤ party_xp_per_member` and `party_level_spread_disband ≥ ai_level_spread_max`. | user + Data layer (3) | Before the Party implementation story |
| OQ-6 | **Group bonus and banner in Combat (F2, R12).** Combat's encounter needs per-group `atk_bonus_add`, `dmg_red_add` and a `has_buffer` override (for the banner) to apply F2 and the Lệnh Kỳ in-fight. Until then F2 ships at 0 and the banner affects XP and warnings only. | Combat (10), user | Before S4 (real skills) |
| OQ-7 | **Hunt intent carries a ground; Utility AI chooses per group.** Member state machine R10 step 5 sets an intent with a ground from a per-member `choose_job`, while Utility AI's call sequence chooses the ground per group after Party groups members. Party ignores the intent's ground and groups first (R3). The two sibling GDDs must agree; an ordered hunt at a specific ground (MSM step 4) also needs a rule: does the ordered member drag their party (MSM PROVISIONAL)? Proposed: an ordered member hunts solo at the ordered ground for that trip and counts as absent from the party. **RESOLVED (consistency-check 2026-11-16):** Member state machine R10 (owner of orders and the P2 pass) no longer gives intents a ground: the member step only marks a member free to hunt, Party groups first, then the ground is chosen per group. A group containing an unapplied `hunt` order goes to that order's ground (lowest `member_id`'s order if several); otherwise Utility AI `choose_ground`. The proposed solo rule is not adopted. | Member state machine (41), Utility AI (12) | Closed |
| OQ-8 | **Reason-code numbers** for R13 inside block 1300 are assigned in the implementation story (→ ADR with the Command layer table). | Implementation story | Before the Party story |
| OQ-9 | **Per-party `loot_rule` (§4.1).** Party stores none; loot rules are guild-wide and Items' (Items OQ-7). Confirm. | Items (26), user | Vertical Slice |
| PROVISIONAL-1 | Closed 2026-11-16: Entitlement and feature flags (32) is designed and supplies the injected snapshot. | — | — |
