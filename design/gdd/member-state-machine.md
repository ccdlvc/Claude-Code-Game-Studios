# Member State Machine

> **Status**: Designed
> **Author**: user + Claude (design-system, autonomous batch run)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no game pillars written yet)
> **Reference implementation**: none. `sim/` has no member state machine: `hunt.run_trip` runs one trip end to end and the balance simulator loops trips back to back. This GDD is a new design; its timing is chosen so that a member with no needs pressure reproduces the reference's back-to-back trip timeline (R4, F7).
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief exist to check against; re-run once pillars are written

## Summary

The Member state machine decides what each guild member is doing right now: waiting in town, out hunting, walking home, resting, dead and waiting for revival, injured, fighting the Golden Boss, training, leaving, or retired as an Elder. It owns the two needs, hunger (satiety) and fatigue (stamina), the player's direct orders ("go hunt there", "come home", "stay home"), and the rule that no other system may set a member's state directly. It exists so that the guild looks and behaves like a town of people with routines, and so that every system that needs a member "free", "home" or "busy" asks one place and gets the same answer.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Member model, Sim core and tick loop, Event bus and history log, Command layer, Zones and hunt trips, Utility AI, Party, Guild and buildings, Items and loot tables, Gold economy`

## Overview

GDD §6.4 describes a member's day as a loop: `idle → (chọn việc) → [đi bãi → hunting → nhặt đồ] → (túi đầy | HP thấp | đói | mệt | hết thuốc) → returning → [bán đồ → mua đồ → ăn → nghỉ → chữa trị] → idle`, with special states `injured`, `dead (chờ hồi sinh)`, `boss_raid`, `bounty`, `training` and `away (rời bang)`. This system is that loop, made exact. Each member is in exactly one of eleven states at every tick. The state changes only at defined moments: when an owning system reports something (a trip started, a member fell, a trip ended), when a timer this system set runs out (rest over, revived, injury healed), when the Utility AI's choice is applied in an idle member's decision step, or when another system *asks* through this system's request calls and the request passes this system's rules. The player sees the result everywhere: the member's pose and icon in the world view, the state label and countdown on the member panel, and who answers the hourly Golden Boss call. The player acts on it through three orders (hunt at a ground, return, stay home) that override the AI until they finish or are cleared. The system adds two needs, satiety and stamina, that make Thiện Đường food a recurring purchase and occasionally send a tired party home early, while leaving the calibrated pacing of GDD §4.3 within about 2% (F7).

## Player Fantasy

**"My guild has a rhythm, and I can step into it."** The bang chủ glances at the town and reads it at once: three parties out in the Bamboo Grove, one walking home with a sack of loot, two disciples asleep at the inn, one bandaged after a bad run. Nobody needed telling. And when the master does step in ("you, home now"; "you two, Tàng Kinh Các is free, stay in town"), the member obeys on the next beat and the guild carries on around them.

- **Anchor moment.** The hourly Golden Boss gong sounds. Members in town drop what they are doing and gather; hunting parties finish their fight and turn back; the injured disciple stays in bed, visibly left out. The player sees, without opening a menu, exactly who answered and why the others did not.
- **Anchor text.** GDD §6.4 (the loop and the special states), §6.4 "Người chơi có thể chạm vào thành viên để ra lệnh trực tiếp" (direct orders, as in Evil Hunter Tycoon), §6.13 (who joins a raid).
- **What it asks of the design.** Every state must be visible and distinct (Visual/Audio, UI). A state change must show on the tick it happens (Game Feel). An order must always produce a visible answer: obeyed, queued until the member is free, or refused with a reason (R9). Needs must warn before they bite (UI: thresholds shown on the bars).

*Pillar anchor:* none. The project has no game pillars, so this framing is anchored to GDD §1 and §6.4. Two alternative framings were considered: "the clockwork guild" (pure optimisation, the member as a machine with uptime; it suits the Utility AI GDD better) and "every member is a character with moods" (personality-first; that belongs to Retention (16) and CA/PA traits (9)).

## Detailed Design

*Specialist lenses applied (Section 6 routing: `Gameplay`, row AI/pathfinding/behavior, primary game-designer; supporting ai-programmer and systems-designer):*

> - **game-designer:** the player's decisions here are few and must matter: *when to pull a member out* (order home), *who stays in town* (hold), and *whether to feed and rest the guild* (building the Thiện Đường, keeping gold for food). Everything else is automatic, because this is an idle game. Hunger and fatigue must never soft-lock a poor guild: a member with no food still hunts.
> - **ai-programmer:** the AI decides only at an idle member's decision point, never every tick; decisions must be cheap, deterministic and staggered. A member waiting for a party must not wait forever (intent timeout). A player order must be visibly respected and visibly finished.
> - **systems-designer:** every state needs an entry trigger, an exit trigger and an owner; every external request needs a refusal rule. Needs must be computed lazily (no per-tick scan of 40 members) and their threshold crossings scheduled as deadline ticks. The post-trip rest must stay a *group* rest so the trip timeline matches the reference.
>
> No conflict between the roles needed a decision by the user. Decisions taken in this autonomous run are logged in `production/session-logs/decision-log.md`.

### Core Rules

Rules are numbered R1–R17. "Home" states are `idle`, `resting`, `injured`, `training` and `elder`; "active" states are `hunting`, `returning`, `boss_raid` and `bounty`.

**State and ownership**

**R1 — One state per member, one writer.** Every member on the roster has exactly one state from the table in States and Transitions. The fields `state`, `ground_id`, `satiety` and `stamina` on the member record (Member model R1) are written only by this system. Other systems change a member's state only by (a) emitting an event this system subscribes to (R5), or (b) calling one of this system's request calls (R6), which this system validates and applies or refuses. A write to `state` from any other system is a defect (AC-1).

**R2 — Creation and removal.** When Member model (8) creates a member, it calls `init_member(member_id, tick)`. This system sets `state = idle`, `satiety = stamina = need_max`, `decide_due_tick = tick` and no order. It never refuses. A member can be removed from the roster only while `away` (Member model R9); this system then deletes the member's state record, cancels its timers and ends any order with outcome `invalidated`.

**R3 — Registration.** This system registers:
- one P2 handler: `register(P2, order = 4100, owner_id = "member_state", handler)` (4100 = system number × 100);
- one Event bus subscriber: `subscribe("member_state", order = 4100, [1101, 1103, 1104], handler)`;
- its event types 4101–4103 (R15) in block 4100–4199 (`member_state_event_type_block`);
- its two host commands, `order_member` (4101) and `clear_order` (4102), with the Command layer, applied in P1 (R9);
- one serializer with Local save (6) (R17).

It takes no randomness: it makes no `derive` call.

**The P2 step**

**R4 — What runs in P2 of tick N, in this order.**
1. **Timers.** Every timer this system owns whose due tick is ≤ N fires, in ascending `(due_tick, kind, key)` order, where `kind` is 1 group rest, 2 member timer, 3 need-return timer, and `key` is the `party_id` or `member_id`. Firing is described in R7, R8, R11 and R12.
2. **Member step.** Every `idle` member whose `decide_due_tick` is ≤ N runs the member step of R10 (errands, fatigue, hold), in ascending `member_id` order.
3. **Trip step.** The members still due and free to hunt are grouped and sent out (R10, the trip step; Utility AI's P2 call sequence).

Nothing else runs in P2. A member whose state has no timer and who is not due to decide costs nothing that tick (F6).

**Events from other systems**

**R5 — Events this system reacts to.** The subscriber receives events in P6 and updates only this system's own state (Event bus R6). It never calls another system from the subscriber.
- **1101 `hunt_trip_started` (a = party_id).** The roster of the trip (`trip_roster(party_id)`, Party R9, as submitted in R10) moves `idle → hunting`, `ground_id` is set, and the need-return timer is scheduled for the party (R12). A roster member who is not `idle` is a defect: the subscriber calls `ctx.fail(41001)`.
- **1103 `hunt_member_downed` (a = member_id).** The member moves `hunting → dead`. The death tick is appended to the member's death record (R13). No timer is set: a member who falls in a trip stays `dead` until the trip's group rest ends (R7).
- **1104 `hunt_trip_ended` (a = party_id, c = reason).** For reasons 1, 2, 3, 5, 6 and 7, the roster's living members move `hunting → returning`; `dead` members stay `dead`. For reason 4 (`recalled` by the Golden Boss) see R8. A `hunt` order held by any roster member completes with outcome `completed` (R9).

**Requests from other systems**

**R6 — Request calls.** Another system asks for a state change by calling one of these, synchronously, from its own handler. Each returns `ok` or a reason code (R16) and, if refused, changes nothing.

| Call | Caller | Allowed from | Result |
|---|---|---|---|
| `start_rest(party_id, roster, rest_ms)` | Zones and hunt (11), at settlement (Hunt R6 step 11) | roster in `returning` or `dead` | Group rest (R7) |
| `enter_raid(member_id)` | Golden Boss raid (14, R4–R5) | `idle`, or `hunting` during the recall hand-off | `boss_raid` (R8) |
| `leave_raid(member_id, alive)` | Golden Boss raid (14, R6, R9) | `boss_raid` | `resting` (alive) or `dead` (R8) |
| `enter_training(member_id, owner_id)` | Schools (20); a training-ground owner later | `idle`, `resting` | `training` |
| `leave_training(member_id, owner_id)` | the same owner | `training` held by that owner | `idle` |
| `enter_injured(member_id, duration_s, cause)` | Retention (16) R7, cause `recuperate` (dưỡng sức) | `idle`, `resting` | `injured` (R13) |
| `enter_away(member_id)` | Retention (16) R8 | `idle`, `resting`, `injured`; **queued** from `hunting`, `returning`, `boss_raid` | `away` (at once, or when the member next reaches `idle`) |
| `cancel_away(member_id)` | Retention (16) | `away` | `idle` |
| `enter_bounty(member_id, owner_id)` / `leave_bounty(…)` | the bounty owner (Vertical Slice or later, OQ-6) | `idle` / `bounty` | `bounty` / `idle` |
| `enter_elder(member_id)` | Rebirth and Ascension (23) | `idle` | `elder` (terminal) |

Queries, which change nothing: `state_of(member_id)`, `can(member_id, action)` for the actions in the capability table (States and Transitions), `needs(member_id, tick)` (F1), `order_of(member_id)`, `available_to_hunt(member_id)` (the Zones R3 / Party R2 test: `can(start a trip)` and full HP).

- **Leaving `resting` early.** `enter_training` (and `enter_injured`, `enter_away`) on a `resting` member end that member's rest at once and restore full HP (the same heal as R7); the group rest continues for the others and still ends at its due tick. The member gains at most 75 s of regeneration early, which is accepted. A `resting` member is not raid-eligible (Golden Boss R4: "`resting`-complete"); they become eligible when the rest ends, if gathering is still open.
- **Queued departure.** `enter_away` for a member in an active state is accepted and stored; it applies the moment the member next becomes `idle`, before anything else in that tick's member step (Retention R8: "the move waits for the trip to close … for the raid to end"). Reaching `away` emits 4101 with to-state 10, which is the "away reached" signal Retention and Party read.
- **Gating is this system's only check.** A caller's own conditions (raid level minimum, Academy level, cost) are checked by the caller before it asks.

**R7 — The group rest after a trip.** `start_rest` creates one group-rest timer for the party, due at `N + ceil(rest_ms / tick_ms)`, where `rest_ms` is Hunt F7 (the maximum over the roster: `revive_ms` if anyone died). Living roster members move `returning → resting`; dead members stay `dead` and are attached to the same timer.
0. **Trip-close shopping.** At `start_rest`, for each living roster member in ascending `member_id`, this system calls Utility AI `choose_gear(member, wallet_gold, catalog)` once (Utility AI R2, R10) and executes the returned purchases in order through Gold economy `shop_sale` and Member model `equip`. A purchase that is refused is skipped. This takes no game time, as in the reference `auto_gear`.

When the timer fires:
1. Every attached member still in `resting` or `dead` is healed to full HP through Member model's heal call (PROVISIONAL, OQ-3).
2. Each revived member is checked against the injury rule (R13, F5): if it holds, the member moves `dead → injured`; otherwise `→ idle`. Living members move `resting → idle`.
3. The member's `decide_due_tick` is set to N (they run the member and trip steps of this same P2, R4 steps 2–3).
4. This system calls Hunt's `rest_ended(party_id)`, which closes the trip and releases occupancy (Hunt R10).

Because every member leaves at the same tick and decides at once, a party with no needs pressure starts its next trip with the same downtime as the reference's `rest` term (F7), plus the one or two ticks Party and Hunt take to start it.

**R8 — Golden Boss raid.** The raid (14) owns who is eligible, the gathering time, the fight and its rewards (GDD §6.13). This system owns only the member's state around it.
- **Joining from town:** `enter_raid` on an `idle` member moves them to `boss_raid` (Golden Boss R5, "eligible idle members move to `boss_raid` at once").
- **Joining from a hunt:** after a recall, Hunt settles at once and hands the group to the raid in P3 (Hunt R11); the raid calls `enter_raid` for each member still eligible. When 1104 with reason 4 is delivered in P6, roster members already in `boss_raid` are left alone; living members the raid did not take (opted out, under-level, or arriving after `raid_gather_max_s`) move to `resting` with a member timer of Hunt F7 for that member; dead members get a member timer of `revive_ms`. Members on such a timer return to `idle` (or `injured`, R13) when it fires. Golden Boss R5 now sends these members home through this rule (aligned 2026-11-16); this system routes them through a short rest so that they are at full HP before their next trip (Zones R3), which is the "41 decides resting" of Golden Boss R9.
- **Leaving:** `leave_raid(member_id, alive)` (Golden Boss R6 for capped-out members, R9 at the deadline tick) moves a living member to `resting` with a member timer of Hunt F7 for their `hp_after`, and a dead member to `dead` with a member timer of `revive_ms` (revival at Linh Miếu). Raid deaths count toward the injury rule (R13); that rule is the "serious injury by its rules" of Golden Boss R9.
- **Not eligible here:** `resting`, `dead`, `injured`, `training`, `away`, `bounty`, `elder`, `returning` and members already in `boss_raid` (Golden Boss R4). A member in Homebound, Selling or Resting joins only if their trip closes before gathering ends (Golden Boss R4).

**Decisions and the AI**

**R9 — Player orders.** The player gives orders with two host commands (Command layer R10), applied in P1:
- `order_member(member_id, job, target)` (4101). Jobs: **1 `hunt`** (target = ground uid), **2 `return`** (target 0), **3 `rest`** (target 0, "stay home"). Values 4 (`heal`) and 5 (`shop`) are reserved: in MVP HP is always full when a member is home (R7), and shopping is the existing `buy_item` / `equip_item` commands.
- `clear_order(member_id)` (4102).

An order is **refused** (no change) with `MSM_MEMBER_UNKNOWN` if the member is not on the roster; with `MSM_STATE_BLOCKED` if the member is `away` or `elder`; with `MSM_BAD_JOB` for an unknown or reserved job; with `MSM_BAD_TARGET` if a `hunt` target is not a live ground (Data layer `content_live`); with `MSM_NOT_APPLICABLE` for `return` when the member is not `hunting`; and `clear_order` with `MSM_NO_ORDER` when there is none. Otherwise:
- **`hunt`** is stored. It replaces any earlier order (that one ends with outcome `replaced`). It takes effect at the member's next trip step (R10), so an order given to a hunting member applies when they are next idle. Its ground is used directly, without asking Utility AI (Utility AI R6). It completes when that member's next trip ends (1104), or **expires** (outcome `expired`) if the start it produced is refused by Zones (for example code 14, ground full); the refusal reason is shown to the player.
- **`return`** on a `hunting` member calls Hunt's order home for the member's party (Hunt R11, code 5): the whole party comes home, because a trip's roster is fixed. It completes when the member reaches `idle`.
- **`rest`** is a **hold**: while it stands, the decision step never sends the member out; they stay home (`idle`, or `resting` for fatigue) until `clear_order` or a new order. Given to a `hunting` member, it also orders the party home. A held member still answers a Golden Boss call unless the raid's own per-member opt-out says otherwise (Golden Boss 14).
- Every order that ends emits 4103 with its outcome (R15).

**R10 — The decision step (idle members, in P2).** It has two parts.

*Member step* (each due `idle` member, ascending `member_id`; the first branch that applies ends it):
1. **Queued departure.** If an `enter_away` is queued, apply it (R6). Step ends.
2. **Eat.** If `satiety < eat_below`, the member eats (R11, F4): this system picks the food (the highest-tier `food` row the Thiện Đường sells under its `max_food_tier`, with `level_req ≤ level`, that the member's wallet covers; ties to the lowest `uid`), takes payment through Gold economy `shop_sale` (Gold economy R7) and the item through Items (26), and applies `eat`. If nothing is sold or affordable, the member does not eat and the step goes on: hunger never blocks hunting. Eating takes no game time in MVP (see Edge Cases).
3. **Fatigue.** If `stamina < fatigue_rest_below`, the member moves to `resting` with a member timer of F3 (rest until stamina is full). Step ends.
4. **Hold.** If a `rest` order stands, set `decide_due_tick = N + ai_reask_ticks` (Utility AI knob, 50 ticks). Step ends.
5. Otherwise the member is **free to hunt** this tick and goes to the trip step.

*Trip step* (the Utility AI P2 call sequence, Utility AI States and Transitions, steps 1–4):
1. Collect the members free to hunt from the member step that are `available_to_hunt`.
2. Party (13) hands over the hunting groups for them (existing parties, newly formed ones, solo members as parties of one; Party R9 `trip_roster`).
3. For each group in ascending `party_id`: if a member of the group holds an unapplied `hunt` order, the group's ground is that order's target (the lowest `member_id`'s order if several; the order is marked applied). Otherwise call Utility AI `choose_ground(group, view)`. Either way the group is added to `view` (Utility AI R4).
4. Submit each start to Zones for P3 (`request_start(party_id, roster, ground)`, PROVISIONAL). A group whose result is `none` stays `idle` and its members get `decide_due_tick = N + ai_reask_ticks` (Utility AI R9); the same happens if Zones refuses the start in P3, which Zones reports back to this system (`start_refused(party_id, code)`, PROVISIONAL). An ordered hunt whose start is refused expires. Submitted members also get `decide_due_tick = N + ai_reask_ticks`, so they are not resubmitted before Zones answers (a start accepted in P3 delivers 1101 in P6 of the same tick).

When 1101 arrives the roster becomes `hunting` (R5). Trip-close purchases happen at the group rest, not here (R7 step 0).

**Needs**

**R11 — Satiety and stamina.** Each is an integer in milli-points, `0 … need_max × 1000` (`need_max = 100`). They are stored as a value plus the tick at which it was last computed (the anchor), and read through F1, so no member is touched on ticks when nothing happens to them. Every state change re-anchors both needs at the current value.
- **Satiety** falls at `satiety_decay_per_h` in active states and does not change in any other state. It rises only by eating (F4).
- **Stamina** falls at `stamina_decay_per_h` in active states and rises at `stamina_regen_per_h` (times the Inn's `stamina_regen_mult`, F1) in `idle`, `resting`, `injured` and `training`. It is frozen in `dead`, `away` and `elder`.
- A member's needs never cause damage, death or a combat penalty. Their effects are: eating and resting in the decision step (R10), the return triggers (R12), and the mood inputs Retention (16) reads (`satiety`, `stamina` on a 0–100 scale: `needs()` returns milli-points, so Retention divides by 1000). When a member eats, this system calls Retention's `add_mood(member_id, points_milli)` with the food's `mood` stat (Retention table of mood inputs; Retention OQ-13 resolved on this side, PROVISIONAL until Retention confirms).

**R12 — Need-return triggers (Hunt codes 6 and 7).** When a trip starts (1101), this system computes, for every roster member whose satiety is above `hunger_return_at`, the tick at which it would reach that threshold (F2), and likewise for stamina and `fatigue_return_at`. The earliest of these, if any, is the party's need-return timer. When it fires and the trip is still in progress, this system calls Hunt's `request_return(party_id, code)` with code 6 (hunger) or 7 (fatigue; 6 wins a tie). Hunt ends the trip at its next return check, as for an order home (Hunt R11, R14). A member who starts a trip already below a threshold never triggers it for that trip. This is what stops a hungry member with no food from being sent home after every encounter.

**R13 — Injury.** GDD §6.4 lists `injured`; §6.13 says severe raid injuries follow §6.4. The rule is deterministic, so it needs no randomness:
- Each member keeps the ticks of their last `injury_after_deaths` deaths (trip and raid deaths alike; R5, R8).
- When a dead member is revived (R7 step 2, R8), if F5 says the deaths within `injury_window_s` reach `injury_after_deaths`, the member becomes `injured` for F5's duration instead of `idle`, the death record is cleared, and 4102 is emitted.
- `enter_injured` from Retention (R7 there, reason `recuperate`, `recup_days` of game time) sets the duration directly, with cause code 2. It is **not** scaled by the Infirmary and does not count as an injury for Retention's `bump_injured` (Retention's own table excludes it).
- When the injury timer fires the member moves to `idle` and decides at once.
- An injured member does not hunt, raid, train or join a party; they may still be given gear and may still leave (Retention).

**R14 — Elders, training, bounty and away.** `elder` is terminal: an Elder never decides, never hunts, and their needs are frozen (GDD §6.10: Elders give guild buffs and no longer hunt). `training` and `bounty` are held by the owning system named in the request, and only that owner can end them; a `leave_training` from a different owner is refused with `MSM_WRONG_OWNER`. `away` means the member is leaving the guild: nothing happens to them until Retention cancels (`→ idle`) or Member model removes them (R2).

**Events, codes and saving**

**R15 — Events.** Block 4100–4199 (`member_state_event_type_block`). Payloads are integers (Event bus R2).

| ID | Name | a | b | c | d | Logged | Milestone |
|----|------|---|---|---|---|--------|-----------|
| 4101 | `member_state_changed` | member_id | from-state code | to-state code | cause code | no | no |
| 4102 | `member_injured` | member_id | duration in s | deaths in window | cause (1 deaths, 2 Retention) | yes (ring, `ring_per_day = 100`) | no |
| 4103 | `member_order_ended` | member_id | job | outcome (1 completed, 2 expired, 3 cleared, 4 replaced, 5 invalidated) | 0 | no | no |

State codes: 1 `idle`, 2 `hunting`, 3 `returning`, 4 `resting`, 5 `dead`, 6 `injured`, 7 `boss_raid`, 8 `bounty`, 9 `training`, 10 `away`, 11 `elder`. Codes are permanent and never reused. Cause codes for 4101 are the triggering event type or request (for example 1104, or 4100 + the row number of R6's table) so the Chronicle and the world view can tell "came home with a full bag" from "recalled to the boss". Volumes: typical about 4 events per member per trip (under 0.1 per tick for a 40-member guild); peak 40 in one tick (a Golden Boss call that moves the whole roster). Refusals emit nothing; they return a reason code.

**R16 — Reason and fail codes.** Refusals (returned to the caller, and through the Command layer to the UI): 1 `MSM_MEMBER_UNKNOWN`, 2 `MSM_STATE_BLOCKED`, 3 `MSM_BAD_JOB`, 4 `MSM_BAD_TARGET`, 5 `MSM_NOT_APPLICABLE`, 6 `MSM_NO_ORDER`, 7 `MSM_WRONG_OWNER`. Fail codes (system 41 → 41001–41099, Sim core R10): **41001** an event names a member in a state that cannot receive it (for example 1101 for a member who is not `idle`); **41002** `start_rest` or `rest_ended` for a party with no trip or a roster mismatch; **41003** a timer or saved record names a member not on the roster. These are defects in a caller or a corrupt save, so the tick fails rather than guessing.

**R17 — Saved state.** Through Local save's (6) serializer contract, per member: `state`, `state_since_tick`, `ground_id`, `state_owner_id` (for `training`/`bounty`), satiety and stamina values with their anchor tick, `decide_due_tick`, a queued-departure flag, the order (job, target, applied flag), the member timer (kind, due tick) if any, and the death-tick record. Per party in a group rest: `party_id`, due tick, attached members. The party's need-return timer (due tick and code). Every value is an integer. On load nothing is recomputed: the timers resume from their saved due ticks.

**Offline and pause**

**R18 — Paused, failed and offline.** While the core is `Paused` no handler runs and no timer fires (Sim core R9): due ticks are in sim time, so pausing gains or loses nothing. If a tick fails, its changes are untrusted (Sim core R10) and this system does nothing special. Across an offline gap, Offline progress (31) owns every due tick the gap crosses (Sim core R5; Offline R8). This system registers its timers with Offline at boot in two classes:
- **Paused** (activity in progress): group rests, post-raid and post-recall rests, fatigue rests and need-return timers. Offline shifts their due ticks by the skipped amount; they resume after the skip with their remaining time.
- **Elapsing** (recovery): revival timers outside a trip, injury timers. Due ticks inside a credited window fire through this system's `settle_to(to_tick)` hook in R4 order, as if at their due ticks; members whose recovery completes become available to later slices (Offline R6 rule 1).
- **Needs are frozen across a gap** (Offline OQ-9: hunger is not modelled offline at MVP). At the skip, this system re-anchors every member's satiety and stamina at the gap's start value and moves the anchor to the gap's end, so no need changes during the absence. `training` and `bounty` end only when their owners end them.

### States and Transitions

**States**

| Code | State | Where (for the world view) | Needs (R11) | Decides (R10) | Timer |
|---|---|---|---|---|---|
| 1 | `idle` | town | stamina regenerates | yes, at `decide_due_tick` | intent timeout |
| 2 | `hunting` | the ground, outbound or fighting | both fall | no | party need-return timer |
| 3 | `returning` | the road home, then selling | both fall | no | none (Hunt calls `start_rest`) |
| 4 | `resting` | the inn or the trip's rest | stamina regenerates | no | group rest or member timer |
| 5 | `dead` | carried home, then Linh Miếu (shrine) | frozen | no | group rest or member timer (`revive_ms`) |
| 6 | `injured` | infirmary | stamina regenerates | no | member timer (F5) |
| 7 | `boss_raid` | the raid | both fall | no (the raid owns it) | none (the raid calls `leave_raid`) |
| 8 | `bounty` | away on a bounty | both fall | no | none (owner) |
| 9 | `training` | Tàng Kinh Các / training ground | stamina regenerates | no | none (owner) |
| 10 | `away` | leaving; off the map | frozen | no | none |
| 11 | `elder` | the Elders' hall | frozen | never | none |

**Transitions** (every transition not listed is invalid)

| # | From | To | Trigger |
|---|---|---|---|
| T1 | (created) | `idle` | `init_member` (R2) |
| T2 | `idle` | `hunting` | 1101 for the member's party (R5) |
| T3 | `hunting` | `dead` | 1103 for the member (R5) |
| T4 | `hunting` | `returning` | 1104, reason ≠ 4, member alive (R5) |
| T5 | `hunting` | `boss_raid` | `enter_raid` during the recall hand-off (R8) |
| T6 | `hunting` | `resting` | 1104 reason 4, living member not taken by the raid (R8) |
| T7 | `returning` | `resting` | `start_rest` (R7) |
| T8 | `resting` | `idle` | group rest or member timer fires (R7, R8, R10 step 2) |
| T9 | `dead` | `idle` | revival timer fires, injury rule does not hold (R7, R8) |
| T10 | `dead` | `injured` | revival timer fires, injury rule holds (R13) |
| T11 | `idle` | `resting` | decision step, `stamina < fatigue_rest_below` (R10 step 2) |
| T12 | `idle` | `boss_raid` | `enter_raid` (R8) |
| T13 | `boss_raid` | `resting` / `dead` | `leave_raid(alive = true / false)` (R8) |
| T14 | `idle`, `resting` | `training` | `enter_training` (R6) |
| T15 | `training` | `idle` | `leave_training` by the owner (R14) |
| T16 | `idle`, `resting` | `injured` | `enter_injured` (R13) |
| T17 | `injured` | `idle` | injury timer fires (R13) |
| T18 | `idle`, `resting`, `injured` | `away` | `enter_away` (R6); from an active state, queued until the member is next `idle` |
| T19 | `away` | `idle` | `cancel_away` (R6) |
| T20 | `away` | (removed) | Member model `remove_member` (R2) |
| T21 | `idle` | `bounty` / `bounty` → `idle` | owner request (R14) |
| T22 | `idle` | `elder` | `enter_elder` (R14) |

Invalid on purpose: nothing leaves `elder`; nothing enters `hunting` except T2, so no system can teleport a member into a trip; `returning` cannot be interrupted (the party is already on its way home); `dead` cannot be ended early by any request; `away` is reachable only from home states, so a member never vanishes mid-trip or mid-raid.

**Capability table** (`can(member_id, action)`; other systems' rules reference this table)

| State | Start a trip (Hunt R3) | Equip (Member model R6) | Enter training | Join raid | Start a leave (Retention) | Join a party (Party 13) |
|---|---|---|---|---|---|---|
| `idle` | yes | yes | yes | yes | yes | yes |
| `hunting` | no (already in one) | no | no | via recall only | no | no |
| `returning` | no | yes | no | no | no | no |
| `resting` | no (after rest) | yes | yes (ends rest) | no (Golden Boss R4) | yes | yes (starts when idle) |
| `dead` | no | no | no | no | no | no |
| `injured` | no | yes | no | no | yes | no |
| `boss_raid` | no | no | no | — | no | kept (raid keeps parties, §6.13) |
| `bounty` | no | no | no | no | no | no |
| `training` | no | no | — | no | no | no |
| `away` | no | no | no | no | — | no |
| `elder` | no | yes | no | no | no | no |

This matches Member model R6 rule 6 (equip blocked in `hunting`, `boss_raid`, `away`, `dead`, `training`) and adds `bounty`. It matches Schools R4 condition 3 (training excluded in `boss_raid`, `away`, `dead`, `injured`) and also excludes `hunting`, `returning`, `bounty` and `elder`. Golden Boss R4 and Party R2/Zones R3 ("available to hunt") read the Join raid and Start a trip columns. Rebirth R4 rule 7's "home and free" (`can(rebirth)`) is true in `idle`, `returning` and `resting` and false elsewhere, exactly Rebirth's provisional list. Party R8 applies its hard triggers from 4101 (to-state `away`, `training` or `elder`), delivered in P6 of the tick the change happens.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|---|---|---|---|---|
| Sim core (1) | in | P2 registration, `ctx` (tick, emit, fail) | — | Sim core owns phases; this system owns its handler at P2 order 4100 |
| Event bus (42) | both | 1101, 1103, 1104 (subscriber order 4100) | 4101–4103 | This system owns block 4100–4199 |
| Command layer (5) | in | `order_member` (4101), `clear_order` (4102), applied in P1 | Reason codes (R16) | Command layer owns the vocabulary; this system owns the rules |
| Member model (8) | both | Roster, `init_member` call at creation; HP | `state`, `ground_id`, `satiety`, `stamina`; `can()` for equip and removal; heal request at rest end | Member model stores; this system writes its four fields |
| Zones and hunt (11) | both | 1101/1103/1104; trip roster at start; `start_rest`; Hunt F7 `rest_ms` | `can()` (available to hunt); `rest_ended(party_id)`; `request_return(party_id, 6/7)`; order home (code 5) | Hunt owns trips; this system owns member states |
| Utility AI (12) | out | `GroundChoice`, gear purchases | Calls `choose_ground(group, view)` in the trip step and `choose_gear` once per trip close (R7, R10); members with an order are not scored (Utility AI R6) | Utility AI owns scoring; this system owns when to ask |
| Party (13) | both | Hunting groups and `trip_roster(party_id)` | `available_to_hunt`, 4101 for Party's hard triggers | Party owns forming groups |
| Golden Boss raid (14) | in | `enter_raid`, `leave_raid` | `can(join raid)` | The raid owns eligibility and the fight |
| Retention (16) | both | `enter_injured` (recuperate), `enter_away`, `cancel_away` | Needs; `add_mood` on eating; 4101/4102 (injured entry, away reached) | Retention owns loyalty, mood and leaving |
| Jianghu (17) | — | None: Jianghu never takes an on-roster member (Jianghu R1; OQ-2 resolved by user decision 2026-11-16 — NPC guilds sign free agents only) | — | Jianghu owns free agents |
| Schools (20) | in | `enter_training`, `leave_training` | `can(enter training)` | Schools owns school change |
| Rebirth and Ascension (23) | in | `enter_elder` | `can()` | Rebirth owns Ascension |
| Items and loot (26) | both | Food item and its `satiety=` stat | `eat` consumes the item the caller removed | Items owns items and the bag |
| Gold economy (27) | out | — | Food purchases through `shop_sale` (Gold economy R7) | Gold economy owns every debit |
| Guild and buildings (30) | in | `effect(bld_restaurant, satiety_mult)`, `effect(bld_inn, stamina_regen_mult)`, `effect(bld_infirmary, injury_recovery)` | — | Guild owns which value is in force; this system owns what each means (Guild R7) |
| Offline progress (31) | both | Shift amounts; `settle_to(to_tick)` calls | Timer registration (Paused / Elapsing), recovery completions, state names | Offline owns the gap (Offline R8) |
| Local save (6) | out | — | Serializer (R17) | Save owns the contract |
| World view (38), Guild screens (39), Audio (40) | out | — | Events 4101–4103; read-only state, timers, needs, orders | Read only |
| Analytics (37), AI text (36) | out | — | Events 4101–4103 | Subscribers |

## Formulas

All formulas are integer arithmetic on non-negative values. Divisions are floor divisions of non-negative integers, which give the same result in Python (`//`) and GDScript (`/` on `int`). `K = 3,600 × tick_rate` converts a per-hour rate into per-tick terms (36,000 at 10 Hz).

### F1 — Need value at a tick

The need formula is defined as:

`fall(v₀, r, Δ) = max(0, v₀ − (r × Δ) // K)`
`rise(v₀, r, m, Δ) = min(need_max_milli, v₀ + (r × m // 1,000,000) × Δ // K)`
`need(t) = fall(…)` in a state where the need falls, `rise(…)` where it rises, `v₀` where it is frozen, with `Δ = t − anchor_tick`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| v₀ | int | 0 – 100,000 | calculated (saved) | Need value at the anchor tick, milli-points |
| r | int | 0 – 10,000,000 | data file (`config`: `satiety_decay_per_h`, `stamina_decay_per_h`, `stamina_regen_per_h`, × 1000) | Rate in milli-points per hour |
| m | int | 1,000,000 – 3,000,000 | Guild and buildings `effect(bld_inn, stamina_regen_mult)` × 10⁶; 1,000,000 when `none` | Inn multiplier (stamina rise only) |
| Δ | int | 0 – 2⁶² | calculated | Ticks since the anchor |
| need_max_milli | int | 100,000 | constant (`need_max = 100` points × 1000) | Cap |
| K | int | 36,000 at 10 Hz | constant (Sim core `tick_rate`) | Ticks per hour |

**Output Range:** 0 to 100,000. `r = 0` freezes the need (a legal way to switch a need off). `r × Δ` stays below 2⁶³ for any Δ under about 29 million years at the maximum rate.
**Example:** a 15-minute hunt (Δ = 9,000 ticks) at `satiety_decay_per_h = 60` (r = 60,000): `60,000 × 9,000 // 36,000 = 15,000`, so satiety falls by 15 points. Resting 30 s (300 ticks) with no Inn at `stamina_regen_per_h = 1,200`: `1,200,000 × 300 // 36,000 = 10,000`, so stamina rises by 10 points.
**Boundary notes:** re-anchoring at every state change floors each segment separately, so a value can be up to 1 milli-point per state change below the continuous value. This is deterministic in both ports and too small to matter.

### F2 — Need threshold crossing tick

The crossing formula is defined as:

`t_cross(v₀, h, r) = anchor_tick + ceil((v₀ − h) × K / r)` if `v₀ > h` and `r > 0`; otherwise none
with `ceil(a / b) = (a + b − 1) // b`
`need_return_due(party) = min over roster members and both needs of t_cross`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| v₀ | int | 0 – 100,000 | calculated | Need at trip start |
| h | int | 0 – 100,000 | data file (`hunger_return_at`, `fatigue_return_at`, × 1000) | Return threshold |
| r | int | 1 – 10,000,000 | data file | Fall rate in active states, milli-points per hour |
| K | int | 36,000 | constant | Ticks per hour |

**Output Range:** from `anchor_tick + 1` up; none if every member is already at or below the threshold or the rate is 0.
**Example:** satiety 60,000 at trip start, `h = 10,000`, `r = 60,000`: `ceil(50,000 × 36,000 / 60,000) = 30,000` ticks (50 minutes). A 15-minute trip never reaches it.
**Boundary notes:** F2 gives the first tick at which F1 is at or below `h`, exactly: at Δ = `t_cross − anchor_tick`, `r × Δ ≥ (v₀ − h) × K`, and one tick earlier it is not (AC-11).

### F3 — Fatigue rest duration

The fatigue rest formula is defined as:

`rest_ticks = max(1, ceil((need_max_milli − v₀) × K / (r_regen × m // 1,000,000)))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| v₀ | int | 0 – 100,000 | calculated | Stamina when the rest starts |
| r_regen | int | 1 – 10,000,000 | data file (`stamina_regen_per_h` × 1000) | Regeneration rate at home |
| m | int | 1,000,000 – 3,000,000 | Guild and buildings (`bld_inn`), 1,000,000 when `none` | Inn multiplier |
| K | int | 36,000 | constant | Ticks per hour |

**Output Range:** 1 tick to `ceil(100,000 × 36,000 / 1,000) = 3,600,000` ticks (100 hours) at the slowest legal rate; 2,100 ticks (210 s) at the default from `fatigue_rest_below = 30`.
**Example:** stamina 29,500, default rate 1,200,000, no Inn: `ceil(70,500 × 36,000 / 1,200,000) = 2,115` ticks (211.5 s). With Inn level 1 (`1.12`): rate 1,344,000, 1,889 ticks.
**Boundary notes:** `stamina_regen_per_h = 0` would divide by zero and leave a member resting forever; the loader must refuse it (OQ-2).

### F4 — Eating

The eating formula is defined as:

`satiety₁ = min(need_max_milli, satiety₀ + food_satiety × 1000 × s // 1,000,000)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| satiety₀ | int | 0 – 100,000 | calculated (F1) | Satiety before eating |
| food_satiety | int | 1 – 100 | data file (`items.stats` `satiety=` on `food` rows; 60 on `food_01`, `food_04`) | Points the food restores |
| s | int | 1,000,000 – 3,000,000 | Guild and buildings `effect(bld_restaurant, satiety_mult)` × 10⁶; 1,000,000 when `none` | Restaurant multiplier |

**Output Range:** satiety₀ to 100,000. One meal restores 60 points (66 with Thiện Đường level 1).
**Example:** satiety 38,000 eats `food_01` with Thiện Đường level 1: `38,000 + 60 × 1000 × 1,100,000 // 1,000,000 = 104,000`, capped to 100,000.
**Boundary notes:** eating at `eat_below = 40` with a 60-point food never wastes food below Thiện Đường level 1; with the restaurant up to 6 points are lost to the cap, which is accepted.

### F5 — Injury

The injury formula is defined as:

`injured = count{ d ∈ deaths : N − d < injury_window_s × tick_rate } ≥ injury_after_deaths`
`injury_ticks = max(1, injury_s × tick_rate × (1,000,000 − min(q, 900,000)) // 1,000,000)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| deaths | list of int | at most `injury_after_deaths` entries | calculated (saved, R13) | Ticks of the member's latest deaths, including the one just revived |
| N | int | ≥ 0 | calculated | Tick of the revival |
| injury_window_s | int | 60 – 86,400 (3,600 today) | data file (`config`) | Window in which deaths count |
| injury_after_deaths | int | 1 – 10 (3 today) | data file (`config`) | Deaths in the window that cause an injury |
| injury_s | int | 0 – 86,400 (900 today); or the Retention duration | data file (`config`) / Retention request | Base injury length |
| q | int | 0 – 1,000,000 | Guild and buildings `effect(bld_infirmary, injury_recovery)` × 10⁶; 0 when `none` | Infirmary reduction, capped at 90% |

**Output Range:** `injured` is true or false. `injury_ticks` from 1 tick (`injury_s = 0`) to 864,000 ticks (24 h); 9,000 ticks (15 min) by default, 8,550 with Infirmary level 1 (0.05).
**Example:** deaths at ticks 10,000, 25,000 and 40,000; revived at 41,800; window 36,000 ticks: all three satisfy `41,800 − d < 36,000`, so the member is injured for 9,000 ticks.
**Boundary notes:** `injury_after_deaths = 1` injures on every death, which roughly doubles the cost of a death (revive 180 s + 900 s) and changes pacing sharply; keep it ≥ 2. The 90% cap means the Infirmary can never make an injury free.

### F6 — P2 cost per tick (scaling statement for Sim core R17)

The P2 cost formula is defined as:

`c_P2(N) = n_timers(N) × c_timer + n_decide(N) × (c_decide + c_ai)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n_timers(N) | int | 0 – 2 × roster | calculated | Timers due at tick N |
| n_decide(N) | int | 0 – roster | calculated | Idle members due to decide at N |
| c_timer, c_decide | µs | measured | measured on the P1 device spike | Cost of firing one timer, of one decision step without the AI |
| c_ai | µs | measured | Utility AI (12) | Cost of one `choose_ground` per group (amortised per member) |

**Output Range:** 0 on most ticks. Average for a 40-member guild: about 4 transitions per member per 15-minute trip, so under 0.2 timers and decisions per tick. Peak: a whole roster leaving a group rest or a raid on one tick, 40 decisions.
**Example:** 8 parties of 5 rotating 15-minute trips: 40 members × 2 decisions per trip / 9,000 ticks ≈ 0.009 decisions per tick.
**Boundary notes:** the peak is the case to measure. If 40 × `c_ai` exceeds P2's share of the tick budget, the decision step must be staggered (spread `decide_due_tick` over the next few ticks by member ID), which does not change any outcome except start ticks (OQ-1).

### F7 — Expected fatigue downtime (pacing check for the balance simulator)

The downtime share formula is defined as:

`loss_per_trip = decay × T_active − regen × T_home` (points; regen and decay per second)
`trips_per_rest = (100 − fatigue_rest_below) / loss_per_trip` (if `loss_per_trip > 0`; otherwise fatigue never forces a rest)
`downtime_share = T_rest / (trips_per_rest × T_trip + T_rest)`, with `T_rest = (100 − fatigue_rest_below) / regen`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| decay, regen | float | ≥ 0 | data file (`stamina_decay_per_h`, `stamina_regen_per_h`, / 3600) | Points per second |
| T_active | s | measured | Hunt F5 | Time hunting and returning per trip |
| T_home | s | measured | Hunt F7 | Group rest per trip |
| T_trip | s | measured | Hunt F5 | Whole trip |
| fatigue_rest_below | int | 0 – 100 | data file | Threshold that forces a rest |

**Output Range:** 0 (regeneration at home covers the trip) to just under 1. It is a design check, not runtime code.
**Example:** a full party: `T_active = 940 s`, `T_home = 30 s`, `T_trip = 970 s`, defaults (decay 1/60 per s, regen 1/3 per s): `loss = 15.7 − 10 = 5.7`, `trips_per_rest = 12.3`, `T_rest = 210 s`, `downtime_share = 210 / (12.3 × 970 + 210) ≈ 1.7%`. A solo hunter (about 220 s active, about 75 s of rest after a low-HP exit) regenerates more than it loses, so its share is 0.
**Boundary notes:** this is the reason for the default rates: the needs make food a sink and fatigue visible without moving GDD §4.3's pacing by more than about 2%. The balance simulator must confirm it (OQ-8).

## Edge Cases

**Timing and order**
- **If a group rest and a member's need-return timer fall on the same tick**: R4's order fires the group rest first (`kind` 1), so the trip is already closed and the need-return timer is discarded as stale.
- **If 1104 and 1103 for the same trip arrive in one P6 batch**: they are handled in emission order. Hunt emits 1103 for a death before the 1104 that ends the chain (Hunt R6 step 7), so the member is `dead` before the roster moves to `returning`, and stays `dead`.
- **If Hunt's 1101 roster contains a member who is not `idle`**: the tick fails with 41001. Hunt R3 asks `can(start a trip)` before starting, so this is a defect, not a game situation.
- **If no ground is a candidate, or Zones refuses a start**: the group stays `idle` and is asked again after `ai_reask_ticks` (Utility AI R9). Utility AI's view (its R4) makes a capacity refusal rare. A player's `hunt` order whose start is refused expires with outcome `expired`, and the UI shows the reason ("Bamboo Grove is full").
- **If two orders for one member arrive in one tick**: P1 applies them in `seq` order; the later one replaces the earlier (outcome `replaced` for the first).
- **If `return` is ordered for a member whose party is in Homebound or Selling**: the member is `returning`, not `hunting`, so it is refused with `MSM_NOT_APPLICABLE`; they are already coming home.

**Needs**
- **If a member has no food and no gold**: the eat errand finds nothing and the member hunts hungry. Satiety stays at 0; no damage, no block (R11). Retention may lower mood (OQ-4). This prevents a soft-lock for a broke guild.
- **If a member starts a trip below `hunger_return_at`**: no need-return timer is set for them (R12), so they are not pulled home after every encounter.
- **If `stamina_decay_per_h` and `satiety_decay_per_h` are set to 0**: the needs are switched off; members never eat or rest for fatigue, and the timeline is exactly the reference's. This is the fallback if the balance gate rejects F7's drift.
- **If an Elder, `away` or `dead` member's needs are read**: they return the frozen value; no timer exists for them.

**Raids, deaths and injuries**
- **If a raid calls `enter_raid` for a member who is `hunting` outside a recall hand-off**: refused `MSM_STATE_BLOCKED`. Only Hunt's recall path (P3, before 1104) may move a hunting member into the raid.
- **If a member dies in the raid and was already at two deaths in the window**: the raid death is the third, so the member becomes `injured` at revival (F5). Severe raid injury in GDD §6.13 is exactly this rule.
- **If a dead member in a group rest is attached to a trip whose rest is cut short**: it cannot be: `dead` cannot be ended early (Transitions), and only living `resting` members can leave a group rest early (R6).
- **If `revive_s = 0` and a member dies**: the group rest's due tick is at least N + 1 (rounding up from 0 still gives one tick after `start_rest`, R7), so revival is on the next tick and the injury rule still applies.

**Orders and holds**
- **If a held (`rest` order) member is fatigued**: they rest (T11), and return to `idle` and stay held. The hold outlives the rest.
- **If the player orders `hunt` for an injured or training member**: the order is stored (it is not refused), and it applies when the member is next `idle`. The UI shows it as queued.
- **If a member with an order leaves the guild, becomes an Elder or is removed**: the order ends with outcome `invalidated`.

**Save, load and offline**
- **If the game is saved during a group rest**: the rest, its attached members and due tick are saved (R17); after load it ends at the same tick and calls `rest_ended`, so the trip closes exactly once.
- **If an offline gap crosses an injury's end**: the injury timer is Elapsing, so `settle_to` ends it at its due tick and the member is available to Offline's later slices (R18). Needs are unchanged by the gap.
- **If a save holds a state code this build does not know** (a later wave's state in an old build): Local save's schema check refuses the save before this system sees it (Local save `schema_version`); this system never maps unknown codes.

**Why errands take no time.** GDD §6.4 lists selling, buying, eating, resting and healing as steps of the town visit. Selling is Hunt's `sell_s`; resting and healing are the group rest (Hunt F7). Buying and eating take zero time in MVP because the calibrated pacing (GDD §4.3, `calibrate.py`) has no shopping time; adding some would slow every trip. The world view may still show a member walking to the shop during the rest, since it draws, it does not decide (OQ-9).

## Dependencies

### Upstream (this system depends on)

| System | Hard / soft | Interface | What it provides |
|---|---|---|---|
| Sim core and tick loop (1) | Hard | `register(P2, 4100, "member_state", handler)`; `ctx` | Phase and tick; deadline-tick convention (R5 there) |
| Event bus and history log (42) | Hard | `subscribe` order 4100 for 1101, 1103, 1104; `register_type` 4101–4103 | Delivery of Hunt's events |
| Command layer (5) | Hard | Command types 4101, 4102 (host), P1 appliers | Player orders |
| Member model (8) | Hard | `init_member` at creation; field storage; heal to full at rest end (PROVISIONAL, OQ-3) | The member record |
| Data layer and content pipeline (3) | Hard | `config` keys (Tuning Knobs), `sim_params.revive_s`, `items` food rows, `content_live` for grounds | Values |
| Zones, grounds, monsters and hunt trips (11) | Hard | 1101/1103/1104, trip roster at start, `start_rest`, `rest_ended`, `request_return`, order home, Hunt F7 | Trips |
| Utility AI (12) | Hard | `choose_ground(group, view)`, `choose_gear(member, wallet_gold, catalog)` (Utility AI R2) | Ground and gear choice |
| Party (13) | Hard | Hunting groups for free members; `trip_roster(party_id)` (Party R9) | Groups |
| Golden Boss raid (14) | Hard | `enter_raid`, `leave_raid` calls; raid eligibility owned there | Raid participation |
| Retention (16) | Soft | `add_mood` on eating; requests in R6 | Mood input |
| Guild and buildings (30) | Soft | `effect()` for `bld_restaurant.satiety_mult`, `bld_inn.stamina_regen_mult`, `bld_infirmary.injury_recovery` | Multipliers; `none` → neutral |
| Items and loot tables (26) | Soft | Food item handed to `eat`; `satiety=` stat | Food |
| Gold economy (27) | Soft | `shop_sale` for food | Paying for food |
| Local save (6) | Hard | Serializer registration | Persistence |

### Downstream (systems that depend on this one)

| System | Hard / soft | Interface | What they need |
|---|---|---|---|
| Member model (8) | Hard | `can(equip)`, state `away` for removal | Gating R6 rule 6 and R9 |
| Zones and hunt (11) | Hard | `can(start a trip)`; rest hand-off; `rest_ended` | Eligibility and trip closing |
| Utility AI (12), Party (13) | Hard | When to ask, `available_to_hunt`, orders (Utility AI R6), 4101 | Inputs |
| Golden Boss raid (14) | Hard | `enter_raid`, `leave_raid`, `can(join raid)` | Who can join |
| Retention (16) | Hard | `enter_injured`, `enter_away`, `cancel_away`; needs | Leaving and mood |
| Schools (20) | Hard | `enter_training`, `leave_training`, `can(enter training)` | School change |
| Rebirth and Ascension (23) | Hard | `enter_elder`, `can()` | Ascension |
| Offline progress (31) | Hard | Timer registration, `settle_to`, state names (Offline R6, R8) | Crossing timers |
| World view (38), Guild screens (39), Audio (40) | Hard | Events 4101–4103; read-only state | Display |
| Analytics (37), AI text (36), Quests (25) | Soft | Events 4101–4103 | Subscribers |

## Tuning Knobs

All proposed as new `config` keys (not yet in `data/config.csv`; adding them is a data change, OQ-2).

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `satiety_decay_per_h` | 60 | 0 – 200 | members eat every few trips; food cost dominates early gold | 0 switches hunger off | `eat_below`, food `satiety=`, `hunger_return_at` |
| `stamina_decay_per_h` | 60 | 0 – 200 | frequent fatigue rests; pacing drift beyond F7's 2% | 0 switches fatigue off | `stamina_regen_per_h` (only their ratio matters for F7) |
| `stamina_regen_per_h` | 1,200 | 300 – 6,000 | fatigue never forces a rest | long rests; pacing drift | `stamina_decay_per_h`, Inn multiplier |
| `eat_below` | 40 | 10 – 80 | eats often, wastes food at the cap | rarely eats; long hungry spells | food `satiety=` (keep `100 − eat_below ≥ satiety=` to avoid waste) |
| `fatigue_rest_below` | 30 | 5 – 60 | short, frequent rests | rare, long rests | `fatigue_return_at` (must stay above it) |
| `hunger_return_at` | 10 | 0 – 40 | trips cut short by hunger | never triggers (0) | `eat_below` (must stay below it) |
| `fatigue_return_at` | 10 | 0 – 40 | trips cut short by fatigue | never triggers (0) | `fatigue_rest_below` (must stay below it) |
| `injury_after_deaths` | 3 | 2 – 10 | injuries never happen | 1 injures on every death | `injury_window_s` |
| `injury_window_s` | 3,600 | 600 – 86,400 | injuries frequent for risky grounds | injuries almost never happen | `injury_after_deaths` |
| `injury_s` | 900 | 0 – 7,200 | an injury removes a member for a long time | 0 makes injury cosmetic | Infirmary `injury_recovery` |
| `need_max` | 100 | constant | — | — | Display scale only |

Owned elsewhere and only read here: `ai_reask_ticks` (Utility AI, the re-ask cadence for idle and held members), `revive_s`, `regen_pct_per_s` (Hunt F7), `satiety_mult`, `stamina_regen_mult`, `injury_recovery` (building effects, Guild R7), food `satiety=` (Items).

The validator must check `hunger_return_at < eat_below`, `fatigue_return_at < fatigue_rest_below`, `stamina_regen_per_h > 0`, and `injury_after_deaths ≥ 1` (OQ-2).

## Visual/Audio Requirements

*Art-director lens applied. No art bible exists (`design/art/art-bible.md` absent), so this is drafted from GDD §1 (pixel 2D, martial-arts town) and the Player Fantasy; revisit when the art bible is written.*

- **Every state must read at a glance from the town view, without colour alone.** Each state has a distinct pose or location plus a small state icon above the member: `idle` (wandering the town square), `hunting` (on the ground, weapon out), `returning` (walking home with a loot sack), `resting` (sitting or lying at the inn), `dead` (a pale spirit figure drifting to the Linh Miếu shrine), `injured` (bandaged, in the infirmary bed), `boss_raid` (gathering under the guild banner), `training` (seated with a scroll), `bounty` (absent; a notice-board pin), `away` (fades out at the town gate), `elder` (robe and a soft aura at the Elders' hall).
- **Needs:** a bowl icon when satiety is below `eat_below` and a "zzz" icon when stamina is below `fatigue_rest_below`. Icons have shapes, not only colours.
- **Transitions are the feedback.** State changes animate on the tick they happen (from 4101): a short "set off" beat on leaving town, a sack-drop on arriving home, a soft light when revived. While the core is catching up, presentation skips these animations (Sim core R17).
- **Audio:** a light gong cue for the raid call (owned by Golden Boss audio), a short low cue for an injury (4102), a gentle chime on revival; no cue for routine trip transitions, which happen too often. All suppressed during catch-up.

## Game Feel

- **Orders feel immediate.** An order applies in P1 of the next tick (0.1 s at 10 Hz). The member's icon changes on that tick; the UI marks the order pending at once and resolved on `command_applied` (Command layer R11). Target: visible reaction within 200 ms of the tap in normal play.
- **The guild has a rhythm, not jitter.** Idle members decide at once after a rest but re-decide only every `ai_reask_ticks` (5 s), so an idle member does not flicker between choices.
- **Needs warn before they act.** The icon appears at the eat or rest threshold, long before the return threshold, so a trip cut short by hunger never comes as a surprise.
- **An injury is felt, not punishing.** 15 minutes out of an idle session is noticeable without being a loss of progress; the death cause is named in the Chronicle.

## UI Requirements

- **Member panel** (Guild screens 39): the state label (localisation key `ui_msm_state_<code>`, Localization 4), time left for timed states (rest, revival, injury), satiety and stamina bars with the eat/rest thresholds marked, the current order with a Clear button, and the reason for a refused order (`ui_msm_reason_<code>`).
- **Order buttons:** Hunt (opens a ground picker), Return (enabled only while `hunting`), Stay home (toggle). A queued order (member not yet idle) is shown as "queued".
- **Roster list:** filter and count by state ("12 hunting · 3 resting · 1 injured").
- **Multi-select orders** expand to one command per member (Command layer R12), and each refusal is shown on its member.

## Cross-References

| This document references | Target GDD | Specific element | Nature |
|---|---|---|---|
| Member record fields `state`, `ground_id`, `satiety`, `stamina` | `design/gdd/member-model.md` | R1, R6 rule 6, R8 step 3, R9 | Ownership; this GDD writes them |
| P2 phase, order convention, deadline ticks, fail codes | `design/gdd/sim-core-and-tick-loop.md` | R2, R4, R5, R10, R17 | Rule dependency |
| Subscriber contract, type blocks, ring budget | `design/gdd/event-bus-and-history-log.md` | R3, R4, R6, F4 | Rule dependency |
| `order_member`, `clear_order`; AI decisions not commands | `design/gdd/command-layer.md` | R10, R11, R12, MVP vocabulary | Rule dependency; IDs assigned here (4101, 4102) |
| Trip events, rest hand-off, return codes 6–7, F7 | `design/gdd/zones-grounds-monsters-and-hunt-trips.md` | R3, R6, R10, R11, R13, R14, F7, OQ-10 | Data and rule dependency |
| Training state for school change | `design/gdd/schools-and-school-change.md` | R4 condition 3, R4 step 3, R5 step 5 | Request interface |
| Elders earn no XP and do not hunt | `design/gdd/xp-and-level-pacing-curve.md` | `Capped` state | State ownership |
| Building effects `satiety_mult`, `stamina_regen_mult`, `injury_recovery` | `design/gdd/guild-and-buildings.md` | R7 `effect()` | Data dependency |
| Shop sales for food | `design/gdd/gold-economy.md` | R7 | Interface |
| Food items and the bag | `design/gdd/items-and-loot-tables.md` | `items` consumable rows | Data dependency |
| "In combat" is part of `hunting` | `design/gdd/combat.md` | States and Transitions, last paragraph | State ownership |
| P2 call sequence, `choose_ground`, `choose_gear`, orders win, `ai_reask_ticks` | `design/gdd/utility-ai.md` | R2, R4, R6, R9, R10, R12, States and Transitions | Interface; this GDD is the caller |
| Hunting groups, `trip_roster`, no `in_party` state, hard triggers | `design/gdd/party.md` | R1, R2, R8, R9 | Interface |
| Raid eligibility, recall, gathering, survivors and deaths | `design/gdd/golden-boss-and-guild-raid.md` | R4, R5, R6, R9 | Request interface |
| Recuperate, departure waits for trip/raid end, needs as mood input, `add_mood` | `design/gdd/retention-leaving-and-negotiation.md` | R7, R8, mood input table, OQ-1, OQ-13 | Request interface and data |
| Paused / Elapsing timers, `settle_to`, available members per slice | `design/gdd/offline-progress.md` | R6, R8, OQ-9 | Rule dependency |
| Home-and-free check; `elder` terminal state | `design/gdd/rebirth-and-ascension.md` | R4 rule 7, R6 step 4 | Request interface |

## Acceptance Criteria

*QA-lead lens applied: every rule (R1–R18) and formula (F1–F5) has at least one criterion; F6 and F7 are measurement checks. **Logic** = automated unit test in `tests/unit/member_state/`; **Integration** = automated test in `tests/integration/member_state/`; **Visual/Playtest** = screenshot or playtest evidence in `production/qa/evidence/`. [PENDING] marks criteria that need another system's GDD or implementation.*

**Ownership and lifecycle**
- **AC-1 [Logic] (R1)**: **GIVEN** the full test suite with a write-guard on `state`, **WHEN** every system's tests run, **THEN** every write to `state`, `ground_id`, `satiety` or `stamina` comes from this system (grep and runtime check).
- **AC-2 [Logic] (R2)**: **GIVEN** `create_member` at tick 500, **THEN** the member is `idle` with satiety and stamina 100,000 and `decide_due_tick = 500`. **GIVEN** a member in `away` with a `hunt` order, **WHEN** `remove_member` runs, **THEN** the state record is gone and 4103 with outcome 5 was emitted.
- **AC-3 [Logic] (R3)**: **GIVEN** boot, **THEN** the phase table holds `(P2, 4100, "member_state")`, the bus has a subscriber at 4100 for exactly [1101, 1103, 1104], types 4101–4103 are registered with the flags of R15, and commands 4101 and 4102 are registered as host commands.
- **AC-4 [Logic] (R4)**: **GIVEN** a group rest for party 7, a member timer for member 3 and a need-return timer for party 2, all due at tick 1,000, and members 5 and 9 due to decide, **WHEN** P2 of tick 1,000 runs, **THEN** the firing order is party 7's rest, member 3's timer, party 2's need timer, then the member step for 5 then 9, then one trip step for every member still free (members released by the rest join the same member and trip steps, in ID order).

**Trips**
- **AC-5 [Integration] (R5, R7)**: **GIVEN** a stub Hunt that starts a 3-member trip, kills member B, ends with code 2 and calls `start_rest(rest_ms = 180,000)` at tick T, **THEN** the states go `idle → hunting` (all), `hunting → dead` (B), `hunting → returning` (A, C), `returning → resting` (A, C) at T, and at T + 1,800 A, B and C are `idle` with full HP, `rest_ended` was called once, and 4101 was emitted for each change.
- **AC-6 [Logic] (R5)**: **GIVEN** a 1101 whose roster contains a member in `training`, **WHEN** P6 delivers it, **THEN** the tick fails with code 41001 and nothing is committed.
- **AC-7 [Integration] (R7, F7)**: **GIVEN** needs switched off (decay rates 0) and a fixed scenario of 20 back-to-back trips for a party of 5, **WHEN** run through this system, Party and Hunt, **THEN** total elapsed time equals the sum of Hunt F5 trip lengths plus at most 2 ticks per trip.

**Raid**
- **AC-8 [Integration] [PENDING: Golden Boss 14] (R8)**: **GIVEN** a recall during a 3-member trip in which member C is dead and the raid takes A only, **WHEN** 1104 with reason 4 is delivered, **THEN** A is `boss_raid`, B is `resting` with a member timer of Hunt F7 for B, and C is `dead` with a timer of 1,800 ticks.
- **AC-9 [Logic] (R8, R6)**: **GIVEN** an `idle` member, **WHEN** `enter_raid` is called, **THEN** they are `boss_raid`. **GIVEN** a `resting`, `injured`, `dead`, `training` or `returning` member, **THEN** it is refused with `MSM_STATE_BLOCKED`. **GIVEN** `leave_raid(alive = true)` with `hp_after` at 40%, **THEN** the member is `resting` for 600 ticks (Hunt F7) and then `idle` at full HP.
- **AC-9b [Logic] (R6, queued departure)**: **GIVEN** a `hunting` member, **WHEN** `enter_away` is called, **THEN** it returns `ok`, the member stays `hunting`, and on the tick they next become `idle` they move to `away` before any trip step, with 4101 to-state 10.

**Orders**
- **AC-10 [Logic] (R9)**: **GIVEN** an `idle` member, **WHEN** `order_member(hunt, g_z01_1)` applies at tick N, **THEN** in the trip step of P2 of N the member's group is submitted to Zones for `g_z01_1` without a `choose_ground` call; **GIVEN** Zones refuses it with code 14, **THEN** the order ends with outcome 2 (`expired`) and the member is asked again after `ai_reask_ticks`. **GIVEN** a target that is not a live ground, **THEN** it is refused with `MSM_BAD_TARGET`. **GIVEN** job 4 or 5, **THEN** `MSM_BAD_JOB`.
- **AC-11 [Integration] (R9)**: **GIVEN** a hunting member of a 4-member party, **WHEN** `order_member(return)` applies, **THEN** Hunt receives an order home for that party, the trip ends with code 5 at its next return check, all 4 members come home, and the order completes when the member reaches `idle`. **GIVEN** the member is `returning`, **THEN** it is refused with `MSM_NOT_APPLICABLE`.
- **AC-12 [Logic] (R9, R10)**: **GIVEN** a `rest` order on an `idle` member, **WHEN** 1 hour of ticks run with a stub `choose_ground` that always returns a ground, **THEN** the member is never in a group passed to `choose_ground` and never leaves town; after `clear_order`, the next trip step includes them.

**Decisions and needs**
- **AC-13 [Logic] (R10)**: **GIVEN** an `idle` member with satiety 39,000, stamina 29,000 and gold for food, **WHEN** the decision step runs, **THEN** the member eats first (satiety becomes 99,000 with `food_01` and no restaurant), then moves to `resting` with an F3 timer, and the AI is not called. **GIVEN** no gold and no food, **THEN** satiety stays 39,000 and the step proceeds to the fatigue check.
- **AC-14 [Logic] (R11, F1)**: **GIVEN** satiety 100,000 anchored at tick 0 in `hunting`, **THEN** `needs()` gives 85,000 at tick 9,000 and 0 at tick 360,000 and every later tick. **GIVEN** `idle`, **THEN** satiety is unchanged after 9,000 ticks, and stamina 50,000 becomes 60,000 after 300 ticks (no Inn) and 61,200 with an Inn multiplier of 1.12. **GIVEN** rate 0, **THEN** the value never changes.
- **AC-15 [Logic] (R12, F2)**: **GIVEN** a 2-member trip starting at tick 0 with satiety 60,000 and 100,000, stamina 100,000 each, **THEN** the need-return timer is due at tick 30,000 with code 6; at tick 29,999 F1 gives 10,002 and at 30,000 it gives 10,000. **GIVEN** a member starting at satiety 9,000, **THEN** they contribute no crossing. **GIVEN** both crossings on one tick, **THEN** the code is 6.
- **AC-16 [Logic] (F3)**: **GIVEN** stamina 29,500, **THEN** `rest_ticks` is 2,115 with no Inn and 1,889 with the Inn multiplier 1.12. **GIVEN** stamina 100,000, **THEN** it is 1. **GIVEN** `stamina_regen_per_h = 0` in a fixture, **THEN** the content validator refuses the load.
- **AC-17 [Logic] (F4)**: **GIVEN** satiety 38,000 and `food_01`, **THEN** it becomes 98,000 with no restaurant and 100,000 (capped from 104,000) with `satiety_mult` 1.1.

**Injury**
- **AC-18 [Logic] (R13, F5)**: **GIVEN** deaths at ticks 10,000, 25,000 and 40,000 and a revival at 41,800, **THEN** the member becomes `injured` for 9,000 ticks and 4102 is emitted with b = 900 and c = 3. **GIVEN** the first death at tick 5,000 instead (`41,800 − 5,000 = 36,800 ≥ 36,000`), **THEN** the member becomes `idle`. **GIVEN** Infirmary `injury_recovery` 0.05, **THEN** the duration is 8,550 ticks; **GIVEN** 1.0, **THEN** it is 900 ticks (90% cap).
- **AC-19 [Logic] (R13)**: **GIVEN** an `injured` member, **WHEN** a party assignment, a raid entry and `enter_training` are tried, **THEN** each is refused; `can(equip)` is true; at the injury's due tick the member is `idle` and decides in the same P2.

**Other states**
- **AC-20 [Logic] (R6, R14)**: **GIVEN** a member in `training` held by `schools`, **WHEN** `leave_training` is called with owner `bounty_board`, **THEN** it is refused with `MSM_WRONG_OWNER`; with owner `schools`, the member is `idle`. **GIVEN** an Elder, **THEN** every order is refused with `MSM_STATE_BLOCKED`, the decision step never runs for them and their needs never change.
- **AC-21 [Integration] [PENDING: Schools 20] (Schools R4, capability table)**: **GIVEN** a member in each of the 11 states, **WHEN** `change_school` is ordered, **THEN** it is accepted only for `idle` and `resting`.
- **AC-22 [Logic] (Transitions)**: **GIVEN** a member in each state, **WHEN** every request call of R6 is tried, **THEN** exactly the transitions T1–T22 succeed and every other attempt returns a reason code with no state change.

**Events, save, offline**
- **AC-23 [Logic] (R15)**: **GIVEN** a 1-hour scripted run of a 40-member guild, **THEN** every state change produced exactly one 4101 with correct from/to codes, 4101 and 4103 never reach the history ring, and the count of 4102 in the ring equals the number of injuries.
- **AC-24 [Integration] (R17)**: **GIVEN** a fixed seed and a 2-hour run, **WHEN** it is saved at tick 20,000 (during a group rest and an injury), loaded and run to the end, **THEN** the final state and the event stream after tick 20,000 are identical to an uninterrupted run.
- **AC-25 [Logic] (R18)**: **GIVEN** the core `Paused` for 1,000 frames of `advance`, **THEN** no timer fires and no need changes. **GIVEN** an Offline skip of 36,000 ticks that crosses an injury end (Elapsing) and a fatigue rest due 1,000 ticks after the skip starts (Paused), **THEN** `settle_to` ends the injury at its due tick, the fatigue rest ends 1,000 ticks after the skip ends, and every member's satiety and stamina are the same after the skip as before. [PENDING: Offline 31]
- **AC-26 [Logic] (R16)**: **GIVEN** a saved timer naming a member who is not on the roster, **WHEN** it fires, **THEN** the tick fails with 41003.

**Performance and feel**
- **AC-27 [Integration] (F6)**: **GIVEN** the max-roster fixture (40 members) on the min-spec device, **WHEN** all 40 leave a raid on one tick, **THEN** P2's cost for that tick is within P2's share of the per-tick budget (Sim core F6), measured by the Sim core profiler. [PENDING: P1 device spike, Utility AI 12]
- **AC-28 [Integration] (F7)**: **GIVEN** the default needs and `python3 tools/balance_sim.py --quick` with the state machine in the reference, **THEN** time to level 100 differs from the needs-off run by at most 3%. [PENDING: reference implementation]
- **AC-29 [Visual] (Visual/Audio)**: **GIVEN** a town with members in each of the 11 states, **THEN** a screenshot shows each state distinguishable by pose or icon in greyscale.
- **AC-30 [Playtest] (Game Feel)**: **GIVEN** an `idle` member, **WHEN** the player taps "Stay home", **THEN** the member's icon changes within 200 ms on the target device.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Decision stagger.** If F6's peak (40 members in one trip step) exceeds P2's budget, spread `decide_due_tick` by member ID over a few ticks. Measure on the P1 device spike. | Utility AI (12), performance-analyst | P1 spike |
| OQ-2 | **New `config` keys and validator checks (schema/data change, not made here):** the 11 knobs above (`need_max` is a constant); checks `hunger_return_at < eat_below`, `fatigue_return_at < fatigue_rest_below`, `stamina_regen_per_h > 0`, `injury_after_deaths ≥ 1`. | Data layer (3), Dev tooling (43) | Before implementation |
| OQ-3 | **Heal to full at rest end.** Member model R1 gives `hp_milli` to Combat and to Member model (creation and F5) only; Hunt R10 gives the end-of-rest heal to this system. A `heal_full(member_id)` call owned by Member model (or Combat) is assumed. | Member model (8), consistency pass | Next consistency check |
| OQ-4 | **Needs, food and mood.** Retention reads `satiety`/`stamina` on 0–100 (`needs_low` 30, `needs_pen` 8) and expects `add_mood` for food; this GDD calls `add_mood` on eating (R11). Retention OQ-1 also asks for an `injured` sub-reason `recuperate` (cause 2 here) and an "away reached" event (4101 to-state 10 here). Confirm in the consistency pass. | Retention (16) | Next consistency check |
| OQ-5 | **Post-raid routing.** Golden Boss R5/R9 send survivors and non-taken recalled members "to `idle`" with "41 decides resting"; this GDD routes them through a Hunt F7 rest so they meet Zones R3's full-HP rule. Does a `rest` hold count as `raid_opt_out`? (Recommended: no; the opt-out is the raid's flag.) | Golden Boss (14) | Next consistency check |
| OQ-6 | **Who owns `bounty`?** GDD §6.4 lists the state; `bld_bounty` has `bounty_slots`. No system in the index owns bounty jobs (Quests 25 is the nearest). The state is defined here and reserved. | systems index, producer | Vertical Slice |
| OQ-7 | **Needs across an offline gap.** Frozen (R18), following Offline OQ-9 ("hunger not modelled at MVP"). So an absence eats no food, which slightly favours offline over live play in the food sink (about 1 meal per active hour). Revisit with Gold economy S3 consumables. | Offline progress (31), Gold economy (27) | Vertical Slice |
| OQ-8 | **Pacing check.** F7 estimates about 1.7% downtime for full parties. The Python reference has no state machine; one must be added to `sim/` (GDD §20 style module) so the balance simulator and parity harness can confirm it. | Dev tooling (43), game-designer | Before MVP balance pass |
| OQ-9 | **Errand time.** Buying and eating take zero time in MVP. Should a later wave give the town visit a duration (and with it a reason to build a Stable for move speed)? | game-designer | Vertical Slice |
| OQ-10 | **Ring budget for 4102.** `ring_per_day = 100` assumes the Utility AI avoids grounds where members die repeatedly. A guild farming far above its level could exceed it; check against Event bus F4. | Event bus (42), Utility AI (12) | Next consistency check |
| OQ-11 | **Training queued from a trip.** A school change ordered while the member is hunting is refused (only `idle`/`resting` may train). A "pending entry" that starts training when the member next becomes idle would need Schools to set `change_due_tick` at entry, not at acceptance (Schools R4 step 2). | Schools (20) | Next consistency check |
| OQ-12 | **Engine feasibility not checked against the pinned engine.** NOT SOURCEABLE: no `scripting.md` or `core.md` under `docs/engine-reference/godot/modules/`. The design uses only integer arithmetic and plain data, so the risk is low. | technical-director | Architecture |
| OQ-13 | **Food choice lives here, not in Utility AI.** Utility AI R12 keeps needs out of MVP scoring, so R10's food pick is a fixed rule in this system. If food choice should become a scored consideration later, it moves to Utility AI by a design change. | Utility AI (12) | Vertical Slice |
| OQ-14 | **Ordered member in a group.** R10 trip step lets a member's `hunt` order steer their whole group (Utility AI R6 leaves this to Party/MSM). Party may prefer to split the member out instead. | Party (13) | Next consistency check |
| PROVISIONAL | **Zones and hunt (11)** — accepts `request_start(party_id, roster, ground)` from the P2 trip step for P3 and reports refusals back (`start_refused`); calls `start_rest(party_id, roster, rest_ms)` at settlement; accepts `rest_ended(party_id)` to close the trip; accepts `request_return(party_id, code)` for codes 6 and 7, checked first at the return check (Hunt R14, OQ-10 there). | Zones and hunt (11) | Next consistency check |
| PROVISIONAL | **Party (13)** — hands over hunting groups for the free members of one P2 trip step (Utility AI sequence step 2) and reads 4101 for its R8 hard triggers. | Party (13) | Next consistency check |
| PROVISIONAL | **Retention (16), Rebirth (23)** (Jianghu dropped, consistency-check 2026-11-16: it never takes on-roster members) — use `enter_injured`, `enter_away`/`cancel_away` and `enter_elder` as in R6, and Rebirth's home-and-free check is `can(rebirth)`. | Their GDDs | Next consistency check |
| PROVISIONAL | **Offline progress (31)** — accepts this system's Paused/Elapsing timer registration and calls `settle_to` (Offline R8). | Offline progress (31) | Next consistency check |
