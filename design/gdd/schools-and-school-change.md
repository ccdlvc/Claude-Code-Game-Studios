# Schools and School Change

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet)

## Summary

Schools and school change defines the ten martial schools (two per element, each with one combat role) and how a guild member joins one at level 10 and later retrains into another at the Academy. For the player, the school is how a roster becomes a party plan: it fixes a member's element, role, skill tree and gear. A paid change, and the free one after rebirth, let a veteran be remade into what the guild lacks. It exists so that composition, counter-elements and long careers all rest on one clear identity per member.

> **Quick reference** — Layer: `Core` · Priority: `MVP` · Key deps: `Data layer and content pipeline, Sim core and tick loop, Event bus and history log`

## Overview

Schools and school change defines the ten martial schools a guild member can belong to, and the rules for joining one and for leaving one for another. A school is a content row in `data/schools.csv`. Each fixes one of the Five Elements, one combat role (tank, burst, healer and buffer, damage over time, control, and so on), a weapon family and an armour class, and it marks whether the school counts as a party buffer. Two schools share each element, and each school owns its own skill tree of 12 skills, which Skills (21) defines. A school enters the game when its content wave goes live: five schools in Wave 1 and five in Wave 2.

A member starts unaffiliated, joins a school once they reach the joining level, and may later change school at the Academy (Tàng Kinh Các). A change costs items, gold and time, and keeps only part of the member's skill investment. The first change after each rebirth is free (§6.9, §6.10).

**Player impact.** The school is the first thing a player reads about a recruit, and the main lever for building a party: a guild without a buffer school struggles, and a Golden Boss of the wrong element punishes a guild whose schools share one element. School change is the late-game correction. A member the player has invested in for weeks can be retrained into the role the guild now lacks, at a price that makes the choice deliberate rather than free.

**What the system does not own.** It does not own:
- The element multipliers and the counter cycle. Combat (10) owns the ×1.25 / ×0.80 / ×0.95 values, and the Data layer schema declares the cycle once (Data layer R4).
- Skill definitions and skill levels, which belong to Skills (21).
- The member record that stores a member's school, which belongs to Member model (8).
- Party scoring with buffer and element bonuses, which belongs to Party (13).
- Recruit generation, which belongs to Recruitment (15).
- The rebirth tiers that grant a free change, which belong to Rebirth (23).
- School display names, which live in `i18n/` (Data layer R9).

This system owns the school vocabulary, the joining rule, the change rule and its cost, and the rule that decides which school-restricted items a member may equip.

## Player Fantasy

**Both.** The player acts on schools directly: they choose a recruit by school, pick a school at the joining level, and order a school change. They also feel the system indirectly, through party strength and boss results. Three moments carry it across the game.

**1. "I build the sect my guild needs" (early and throughout).** A Kim Golden Boss is due in twenty minutes. The player scans the roster, sees no Hoả school to counter it, and no buffer if the healer is injured. They take the Hoả recruit over a higher-CA candidate. The roster reads like a party plan, because each school is visibly one element and one role. The anchor is §6.1: *"mỗi phái một vai trò rõ trong boss raid"* (each school has a clear role in boss raids). This asks the design for schools that differ legibly in role and element, so a gap in a roster can be seen at a glance.

**2. "Each disciple chooses a path" (early to mid).** A member the player recruited unaffiliated reaches the joining level. The player picks their school from the live ones, weighing the gear in storage and the guild's gaps. From then on the member is a Thanh Mộc Cốc healer, not "member 41". The anchor is §6.1: *"chọn phái khi đạt điều kiện (đề xuất lv10)"* (pick a school once the condition is met, proposed at level 10). This asks for an unaffiliated stage that is short but real, and for a joining choice that matters.

**3. "A veteran's second life" (late).** The guild's oldest tank has just been reborn. For one window the change is free, so the player retrains them as the buffer the guild has always lacked. They keep part of their skill investment and their name in the Chronicle. The anchor is §6.9–6.10: *"đổi phái miễn phí 1 lần"* (one free school change), and §2: *"Đổi phái: Được [CHỐT]"* (school change: allowed, decided). This asks for a paid change whose cost is clearly felt, so the free one after rebirth feels like a gift, and for a change that never erases who the member is.

*No game pillars exist, so no pillar is quoted. These three are anchored to the main GDD (§2, §6.1, §6.9, §6.10). CD-GDD-ALIGN will be NOT ASSESSED.*

## Detailed Design

### Core Rules

**R1: The school vocabulary is content.** A school is one row of `data/schools.csv`, keyed by its permanent `id` (Data layer R3). Its columns are the facts the rest of the game reads:

| Column | Meaning | Read by |
|---|---|---|
| `element` | One of the five elements (`kim`, `moc`, `thuy`, `hoa`, `tho`), the member's element while in this school | Combat (10), Party (13), Golden Boss (14) |
| `role` | The school's combat role (for example `tank`, `healer_support`, `ranged_dps`) | Party (13), Utility AI (12), Recruitment (15) |
| `buff_role` | Whether the school counts as a party buffer | Party (13) |
| `weapon` | The weapon family its members fight with | Items and loot (26), presentation |
| `armor_class` | `heavy`, `medium` or `light`: the one armour class its members may wear (R7) | Items and loot (26) |
| `wave` | The content wave that releases it (Data layer R5) | Liveness, through the Data layer F2 query |

- The school's skills are the 12 rows of `skills.csv` whose `school_id` is this school. Skills (21) owns them.
- Display names and descriptions live in `i18n/` (Data layer R9). The `notes` column is never shown.
- No system parses a school ID: `kim_1` is not read as "Kim". The `element` column is the fact (Data layer R3).
- The roster invariants are validator rules, owned by the Data layer (R8): exactly 10 schools, 5 in Wave 1, and at least one buffer in Wave 1. "Two schools per element" is true of the content today but is not yet a validator rule; this GDD asks for it (OQ-7).
- **A school is offered only while live.** Joining and changing (R3, R4) accept only a school for which the Data layer's liveness query (F2) is true. A member already in a school that is later retired keeps it, because retired rows still resolve (Data layer R3).

**R2: A member's school state.** Member model (8) stores these fields. This system alone decides their values, and writes them only through its own handlers (R3–R5):
- `school_id`: a school ID, or `none` while the member is unaffiliated.
- `aspiring_school_id`: the school the member will join (R3). Meaningful only while unaffiliated.
- `change_target_id` and `change_due_tick`: set only while a change is in progress (R4).
- `free_change_credits`: 0 or 1 (R6).
- `last_paid_change_tick`: the tick of the last paid change that completed, or `none`.

**R3: Joining a school.** A member is unaffiliated until they reach `school_join_level` (default 10, F1).
- **While unaffiliated**, a member has no element and no school skills. Combat (10) treats a missing element as neutral, ×1.0 against every element. The member fights with the basic attack, may wear armour of any class and accessories, and may hold no weapon (R7).
- **Every unaffiliated member has an aspiring school.** Recruitment (15) sets one when it generates the member, including a candidate shown as having no school (§6.7): such a candidate's aspiring school is still set, and only displayed as undecided. The player may change it at any time while the member is unaffiliated, through a `set_aspiring_school` command. Only a live school is accepted.
- **Joining is automatic.** When an unaffiliated member reaches `school_join_level`, this system queues a `join_school` request, and the member joins the aspiring school in P1 of the next tick. A recruit who arrives already at or above `school_join_level` joins in the same way on the tick after arriving. The player's choice is the aspiring school, so the member's progress never waits on a menu.
- **On joining:** `school_id` becomes the aspiring school. The member takes that school's element and its skills at level 0, so they learn them as normal from then on (Skills 21). Any armour of the wrong class moves to guild storage (R7). Joining is free, takes no time, and does not start the change cooldown (R5).
- A member never becomes unaffiliated again. School change (R4) moves them between schools.

**R4: Changing school.** The player orders a change with a `change_school(member_id, target_school_id)` command. It is applied in P1. It is **refused**, with a reason code and no cost taken, unless every one of these holds:
1. The member is affiliated (`school_id` is not `none`), and no change is already in progress.
2. `target_school_id` is live (R1) and differs from `school_id`.
3. The member is in a state where the Member state machine (41) allows starting training. At minimum that excludes `boss_raid`, `away`, `dead`, `injured` and `elder` (Elders never change school, Rebirth R10).
4. The guild's Academy (`bld_academy_skill`) is built at level `school_change_academy_level` or above (default 1).
5. The change is **free** (R6), or it is **paid** and both of these hold:
   - the guild holds the item cost and the gold cost (F2);
   - the cooldown has passed: `last_paid_change_tick` is `none`, or the current tick − `last_paid_change_tick` ≥ `change_cooldown_ticks` (F3).

**When the change is accepted:**
1. Take the cost. A paid change consumes the items from guild storage and the gold from the guild fund (Gold economy 27). A free change consumes one free credit instead.
2. Set `change_target_id`, and set `change_due_tick` to the current tick + `change_duration_ticks` (F3).
3. Ask the Member state machine to put the member in `training` until the due tick.

The member keeps their old school, its skills and their element until the change completes. A change cannot be cancelled once accepted, because its cost is already taken.

**R5: Completing a change.** In P5, when the current tick reaches `change_due_tick` (an anchored deadline tick, Sim core R5), the change completes, in this order:
1. **Skill carry.** Each new-school skill gets its carried level from the old school's skill in the same slot (F4). Skills (21) applies the levels.
2. **Gear.** A weapon whose `school_req` is not the new school, or armour whose `armor_class` is not the new school's, moves from the member to guild storage. It is never destroyed. Choosing replacement gear is Member model's and the AI's job.
3. **School and element.** `school_id` becomes `change_target_id`, and the element follows. Both change fields are cleared.
4. **Cooldown.** A paid change sets `last_paid_change_tick` to the current tick. A free change leaves it unchanged.
5. **Training ends.** The member leaves `training` (Member state machine 41).

**R6: Free changes.** A rebirth tier whose `rewards` include `free_school_change=1` sets the member's `free_change_credits` to 1 when the member completes that rebirth (Rebirth 23). Today only tier 1 has it, and designers grant it to other tiers in `rebirth.csv`, not in code.
- Credits never stack. A rebirth that grants one while the member already holds one leaves the count at 1.
- When the player orders a change and the member holds a credit, the change is free and consumes the credit. The player cannot choose to pay and keep the credit, because the order is one deliberate act.
- A free change waives only the item and gold cost and the cooldown check. The skill carry (F4) and the training time (F3) still apply, so the change is still felt.
- A free change neither checks nor sets the cooldown.

**R7: Who may equip what.** This rule is the only one that decides whether a member's school allows an item:
- **Weapon:** allowed only if the item's `school_req` equals the member's `school_id`. An unaffiliated member may hold no weapon.
- **Armour:** allowed only if the item's `armor_class` equals the school's `armor_class`. An unaffiliated member may wear any class.
- **Accessory and other slots:** no school restriction.

Level requirements, rarity and every other equip condition belong to Items and loot (26). That system asks this rule and adds its own checks.

**R8: Events.** This system emits (Event bus R2, R3):
- `school_joined(member_id, school_uid)`, a milestone with subject slot 1.
- `school_change_started(member_id, from_school_uid, to_school_uid, due_tick)`, logged in the ring.
- `school_changed(member_id, from_school_uid, to_school_uid, free_flag)`, a milestone with subject slot 1. A school change is a roster change, so it must be a milestone (Event bus R3a).
- `school_change_refused(member_id, reason_code)`, delivered and not logged. It is emitted **only for sim-origin refusals** (`join_school`, and the R3 `aspiring_not_live` case), which the Command layer does not report. A refused **host** order (`set_aspiring_school`, `change_school`) is reported by the Command layer's `command_refused` (502) alone; this system does not emit 2004 for it (consistency-check 2026-11-16, Command layer OQ-1).

**Commands (Command layer R2, R3).** This system registers three appliers with the Command layer, not a P1 handler of its own: `set_aspiring_school` (2001, host), `change_school` (2002, host) and `join_school` (2003, sim origin, R3). Reason codes use the shared codes where they fit — 7 `not_allowed_now` (the AC-8 `busy` case), 8 `cannot_afford`, 9 `not_live` — and this system's own codes for the rest: 101 `not_affiliated`, 102 `change_in_progress`, 103 `same_school`, 104 `no_academy`, 105 `cooldown`, 106 `already_affiliated`, 107 `aspiring_not_live` (2004 only).

School IDs travel as their content `uid` (Data layer R6), because event payloads are integers. This system's type block, ring rates and emission rates are set in Formulas (F5).

### States and Transitions

Each member is in exactly one school state.

| State | Meaning | `school_id` | Element |
|---|---|---|---|
| `Unaffiliated` | Below the joining level, or arrived and not yet joined | `none` | none (neutral ×1.0) |
| `Affiliated` | In a school | set | the school's |
| `Changing` | A change is accepted and the member is training | the old school | the old school's |

| From | To | Trigger | Phase |
|---|---|---|---|
| (new member) | `Unaffiliated` | Recruitment creates a member with no school | — |
| (new member) | `Affiliated` | Recruitment creates a member who already has a school (§6.7 allows a recruit with a school) | — |
| `Unaffiliated` | `Unaffiliated` | `set_aspiring_school` with a live school | P1 |
| `Unaffiliated` | `Affiliated` | `join_school` after reaching `school_join_level` (R3) | P1 |
| `Affiliated` | `Changing` | `change_school` accepted (R4) | P1 |
| `Affiliated` | `Affiliated` | `change_school` refused: reason code, no cost (R4) | P1 |
| `Changing` | `Affiliated` (the new school) | `change_due_tick` reached (R5) | P5 |

There is no transition back to `Unaffiliated`, and no cancellation from `Changing`.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Data layer (3) | in | `schools` rows, liveness query (F2), `config.csv` keys (Tuning Knobs) | — | Data layer |
| Sim core (1) | both | Deadline ticks in P5 | The P5 handler | Sim core owns phases; this system owns its handler |
| Command layer (5) | both | Dispatch of 2001–2003 in P1 (`seq` order); `command_refused` (502) for host refusals | Appliers and reason codes (R8) | Command layer owns the envelope; this system owns the rules |
| Member model (8) | both | The member's level and school fields | Writes to the R2 fields, through this system only | Member model owns storage; this system owns the values |
| Member state machine (41) | both | Whether the member may start training | Requests to enter and leave `training` | State machine owns states |
| Skills (21) | out | The old school's skill levels by slot | Carried levels by slot (F4); the new school's skills at level 0 on joining | Skills owns skill levels; this system owns the carry rule |
| XP and level curve (22) | in | A level-up event (it emits) | — | XP curve |
| Items and loot (26) | out | — | The R7 equip rule; items moved to storage on joining or changing | Items owns all other equip rules |
| Guild and buildings (30) | in | Academy level | — | Guild and buildings |
| Items and loot (26), guild storage | both | `count` of the token | `take` the item cost, `give` returned gear (storage is uncapped, Items R7) | Items and loot |
| Gold economy (27) | out | — | The gold cost (F2) as a sink | Gold economy owns the fund |
| Rebirth and Ascension (23) | in | Completed rebirth tier and its `free_school_change` reward | — | Rebirth |
| Recruitment (15) | in | A new member's school or aspiring school | — | Recruitment owns generation; this system owns liveness of the choice |
| Combat (10) | out | — | The member's element, or none | Combat owns the multipliers and the neutral case |
| Party (13), Golden Boss (14), Utility AI (12) | out | — | `role`, `buff_role`, `element` | Each owns its scoring |
| Event bus (42) | out | — | The R8 events | Event bus owns delivery; this system owns its types |
| Localization (4) | none | — | Names come from `i18n/` by school ID | Localization |

## Formulas

### F1 — `join_due`

The join_due formula is defined as:

`join_due(m) = (m.school_id = none) ∧ (m.level ≥ school_join_level) ∧ content_live(m.aspiring_school_id)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| m.level | int | 0 – 200 | calculated | The member's level (XP curve 22) |
| school_join_level | int | 1 – 20 | data file | The joining level (default 10, §6.1) |
| content_live | bool | — | calculated | Data layer F2, for the aspiring school |

**Output Range:** true or false. It is evaluated on a level-up event and on a recruit's arrival (R3), never by scanning the roster each tick. If the aspiring school is not live (for example, a save edited by hand), `join_due` is false and the member stays unaffiliated until the player sets a live one (Edge Cases).
**Example:** a member at level 9 with aspiring school `moc_1` (Wave 1, live) levels up to 10: `join_due` is true, and they join in P1 of the next tick.

### F2 — `change_gold_cost` and the item cost

The change cost formula is defined as:

`change_gold_cost(L) = school_change_income_hours × income_ref_per_level × L` (paid changes only; a free change costs 0)

`change_item_cost = school_change_item_count × item_school_token`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L | int | `school_join_level` – 200 | calculated | The member's level when the change is ordered |
| school_change_income_hours | int | 0 – 48 | data file | Hours of the member's own reference income that one change costs (default 4) |
| income_ref_per_level | int | 1,000 | data file (owned by Gold economy 27) | Reference income per level per hour (§19.1, `config.csv`) |
| school_change_item_count | int | 0 – 5 | data file | Tokens per paid change (default 1) |
| item_school_token | item | — | data file | A new special item, the Scripture token. It can be bought with Linh Bảo at `lb_price_school_token` (default 200, about half a week's quest faucet; Gold economy R16/F9, user decision 2026-11-16); any drop or craft source is owned by Items and loot (26) and Crafting (28) (OQ-2). The gold cost is never payable in Linh Bảo |

**Output Range:** 40,000 gold at level 10, 400,000 at level 100 and 800,000 at level 200 with the defaults. It is always 4 hours of that member's reference income, so the price stays a felt sink at every level (§19.1, §19.5). It is 0 when `school_change_income_hours = 0`, and then the token is the only gate. The cost never goes negative, because every input is non-negative.
**Why 4 hours.** It sits above daily consumables (about 23% of income, §19.2) and well below rebirth at high tiers (rebirth 5 is 20M, about 111 h of a level-180 member's income). It is a deliberate purchase, not a routine one. The balance sim retunes it (§4.4).
**Example:** a level-60 member's paid change costs `4 × 1,000 × 60 = 240,000` gold and 1 Scripture token.

### F3 — `change_duration_ticks` and `change_cooldown_ticks`

The change timing formulas are defined as:

`change_duration_ticks = school_change_duration_s × tick_rate`  and  `change_cooldown_ticks = school_change_cooldown_s × tick_rate`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| school_change_duration_s | int | 60 – 86,400 | data file | Training time in game seconds (default 14,400, 4 h) |
| school_change_cooldown_s | int | 0 – 2,592,000 | data file | Minimum game time between two paid changes (default 604,800, 7 days) |
| tick_rate | int | the Sim core F1 set | data file (owned by Sim core 1) | Ticks per game second (10) |

**Output Range:** at 10 Hz, training is 600 – 864,000 ticks (default 144,000) and the cooldown is 0 – 25,920,000 ticks (default 6,048,000). The duration's minimum of 60 s means a change always passes through `Changing` for at least one P5. A cooldown of 0 disables it. Both are anchored deadline ticks (Sim core R5), so an offline hand-off completes a change at the right tick and never "early".
**Example:** a change accepted in tick 1,000,000 completes in P5 of tick 1,144,000. The next paid change is accepted no earlier than tick 7,192,000, counted from completion (R5).

### F4 — `carried_level`

The skill carry formula is defined as:

`carried_level(slot) = 0` if the member does not meet the new skill's `lv_req` or `rebirth_req`; else `min( new.max_lv, floor( old_level(slot) × school_change_skill_keep_pct / 100 ) )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| slot | int | 1 – 12 | data file | `skills.csv` slot. All schools share the layout: 1–4 active, 5–8 passive, 9–10 ultimate, 11–12 secret |
| old_level(slot) | int | 0 – 20 | calculated | The member's level in the old school's skill in that slot (Skills 21) |
| school_change_skill_keep_pct | int | 0 – 49 | data file | Percent kept per slot (default 30) |
| new.max_lv | int | 10 or 20 | data file | The new school's skill's `max_lv` |
| new.lv_req, new.rebirth_req | int | — | data file | The new school's skill's requirements |

**Output Range:** 0 – 20 per slot. With the default 30%, a level-20 active carries 6, a level-10 passive carries 3, and anything below level 4 carries 0. Keep below 50% is a validator rule, so a change never keeps as much as the gentlest rebirth (`skill_keep_pct` 50, `rebirth.csv`). At 0%, every skill restarts at 0. That is valid but harsh. The rule is per slot, not pooled, so it is deterministic and needs no spending step.
**Example:** a level-80 `kim_1` with slot 1 at 20, slot 5 at 10 and slot 9 (ultimate, `lv_req` 60) at 10 changes to `moc_1`. Slot 1 → 6, slot 5 → 3, slot 9 → 3 (80 ≥ 60). A secret skill whose `rebirth_req` is 1, held by a member with no rebirth, gets 0.

### F5 — event volume (Event bus F1, F4)

The event volume formula is defined as:

`ring_per_day(school_change_started) = school_events_ring_per_day` and every other type here has `ring_per_day = 0`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| school_events_ring_per_day | int | 20 | constant | Declared peak ring records per 86,400 game seconds (Event bus R3) |
| type block | int | 2000 – 2099 | constant | This system's Event bus type IDs (block = system number × 100) |

**Output Range:** the four types are 2001 `school_joined` (milestone), 2002 `school_change_started` (ring), 2003 `school_changed` (milestone) and 2004 `school_change_refused` (not logged). The peak is bounded: a paid change per member per 7 days, plus at most one free change per rebirth, gives far fewer than 20 a day even at a large roster. 20 is 0.2% of the default ring budget (10,000, Event bus F4). Typical events per tick are effectively 0, so this system adds nothing measurable to `E_floor` (Event bus F1).
**Example:** a 60-member guild in which every member changes once a week averages 8.6 `school_change_started` records a day, under the declared 20.

**Feedback loops.** None that compound. A change makes a member better suited to the guild's need, but it costs gold, a token, training time and 70% of the skill investment. It cannot be repeated faster than the cooldown, so it is no loop for unbounded gain.

## Edge Cases

**Joining**
- **If the aspiring school is not live when the member reaches `school_join_level`** (a hand-edited save, or a school retired after it was set): `join_due` is false (F1). The member stays unaffiliated and keeps hunting with the basic attack. A `school_change_refused` event with reason `aspiring_not_live` is emitted once, so the UI can prompt. The member joins on the tick after the player sets a live aspiring school.
- **If a member gains several levels in one tick and passes `school_join_level`** (for example a large XP grant): they join once, on the next tick. The level they reach does not matter, only that it is ≥ the joining level.
- **If `set_aspiring_school` names a school while the member is already at or above `school_join_level`**: the command is accepted and the member joins on the next tick. Setting the aspiring school is the join.
- **If `set_aspiring_school` is ordered for an affiliated member**: refused with reason `already_affiliated`, no change. A member never chooses a school twice by this route. School change is R4.
- **If a recruit arrives with a school that is no longer live**: Recruitment must not generate one (R1). If one arrives anyway, they keep the school, as any member of a retired school does (R1). It is a Recruitment bug, caught by Recruitment's own ACs.

**Ordering a change**
- **If two `change_school` commands for one member arrive in the same tick**: they apply in ascending `seq` (Sim core R6). The first is judged by R4. The second is refused with `change_in_progress` if the first was accepted, or judged on its own if the first was refused.
- **If the target is the member's current school**: refused with `same_school`. Nothing is taken, and a free credit is kept.
- **If the guild has the gold but not the token, or the token but not the gold**: refused with `cannot_afford`. Nothing is taken. The cost is taken all at once or not at all.
- **If a paid change is ordered right after a free one**: allowed, if the cooldown since the last **paid** change has passed. A free change neither checks nor sets the cooldown (R6).
- **If the member holds a free credit and the guild could also pay**: the change is free and uses the credit (R6). The player cannot keep the credit by paying.

**During training**
- **If the member leaves the guild while `Changing`**: the change is void. The cost is not refunded, and the change fields are cleared when Member model removes the member. The member state machine should make this rare, because a member in `training` does not start a leave request (Member state machine 41, provisional).
- **If a rebirth or a party assignment is attempted while `Changing`**: Rebirth (23) and Party (13) must refuse it, because the member is in `training`. The carry (F4) is computed from the old school's levels at completion, so a rebirth in between would change what is carried.
- **If `change_due_tick` falls inside an offline gap**: Offline progress (31) must complete the change at its due tick during its aggregate resolution, in R5's order, so the member hunts in the new school for the rest of the gap. A change is never completed "late" at reload.
- **If R5 or R3 returns gear to storage**: it always fits. Guild storage is owned by Items and loot (26) and is uncapped (Items R7: `give` always succeeds), so gear is never destroyed. If a cap is ever added, Items R7 already requires that it never destroy items.
- **If the new school has no matching weapon or armour in storage**: the member fights with the basic attack and whatever accessories they wear, until Member model's re-gear finds some. It is not an error.

**Degenerate strategies and validator rules**
- **If a player tries to change school to counter each hourly Golden Boss**: the paid cooldown (default 7 days, F3) and the 4-hour training block it. A free change exists only once per granting rebirth.
- **If carried levels break a skill prerequisite** (a skill carries level 3 while its prerequisite carries 0): the carried levels stand. Prerequisites gate learning further levels only (Skills 21, provisional), so the member must raise the prerequisite before raising that skill again.
- **If `school_change_skill_keep_pct` is ≥ 50, or `school_join_level` exceeds the rebirth-0 level cap (`cap[0]` = 100, rebirth row 1 `req_level`, XP curve R3)**: the validator rejects it (Tuning Knobs).
- **If an unaffiliated member joins a raid or a party**: their element is neutral (×1.0 both ways, Combat 10) and they are not a buffer (Party 13). Few reach a raid, because the raid's minimum level is half the **boss's** level (`ceil(raid_min_level_ratio × boss_level)`, ratio 0.5, Golden Boss F2), but nothing forbids it.

## Dependencies

### Upstream (this system depends on)

| System (#) | Hard / soft | Interface | What this system takes |
|---|---|---|---|
| Data layer and content pipeline (3) | Hard | `schools`, `skills`, `items`, `rebirth`, `buildings` rows; the liveness query (F2); `config.csv` keys (Tuning Knobs) | The school vocabulary and every tuning value. The Data layer GDD already lists this system downstream, so the two-way record holds |
| Sim core and tick loop (1) | Hard | The P1 command appliers, P5 deadline ticks (R5), `ctx.submit`, `tick_rate` | When joins and changes apply. Sim core does not list individual features, and does not need to (its R4 registry is generic) |
| Event bus and history log (42) | Hard | `register_type` for block 2000–2099, `subscribe` to the level-up event, `ctx.emit` | Delivery of the R8 events. The Event bus lists "feature systems that emit (8–30, 41)", which includes this one |
| XP and level curve (22) | Soft (provisional) | Event 2201 `member_level_up`, carrying `member_id`, the old level and the new level | The trigger for F1. Without it, joining waits until a recruit's arrival. The XP curve (22) emits one event per award, not per level gained; F1 uses `≥`, so a jump past `school_join_level` still joins the member |
| Member state machine (41) | Soft (provisional) | "May this member start `training`?", and enter or leave `training` | R4 condition 3 and the training block. Without it a change still works, but a member could be ordered mid-raid |
| Guild and buildings (30) | Soft (provisional) | Academy (`bld_academy_skill`) level (guild storage is Items and loot's, below) | R4 condition 4, the item cost and gear return. **The Academy is not in the MVP building set**, so school change is designed now and becomes usable when the Academy ships (OQ-1) |
| Gold economy (27) | Soft (provisional) | Debit the guild fund; `income_ref_per_level` | The F2 gold cost |
| Rebirth and Ascension (23) | Soft (provisional) | A completed-rebirth signal with the tier's rewards | The free credit (R6) |

Deterministic RNG (2) is **not** a dependency. No rule in this system draws.

### Downstream (systems that depend on this one)

| System (#) | Hard / soft | Interface | What it gets |
|---|---|---|---|
| Member model (8) | Hard | The R2 fields and their rules | What a member's school state is, and who may write it (only this system) |
| Skills (21) | Hard | `school_id` → that school's 12 skills; the F4 carry by slot | Which tree a member learns from, and the levels to set on a change |
| Combat (10) | Hard | The member's element, or none | The Five Elements input. Combat must define the neutral case (×1.0) for an unaffiliated member |
| Party (13), Golden Boss raid (14), Utility AI (12) | Hard | `role`, `buff_role`, `element` | Composition scoring, buffer bonus and counter-element coverage |
| Items and loot (26) | Hard | The R7 equip rule | Whether a member's school allows an item; the gear returned to storage |
| Recruitment (15) | Hard | Live schools; a new member's school or aspiring school | What a candidate may be offered (R1) |
| Rebirth and Ascension (23) | Soft | The R6 credit; "refuse while `Changing`" (Edge Cases) | The free change as a rebirth reward. Ascension's `guild_buff_by_school` reads `school_id` |
| Offline progress (31) | Hard | F1 and R5, applied at their ticks during aggregate resolution | Joins and changes that fall inside a gap (Edge Cases) |
| Guild screens (39) | Soft | School state, aspiring school, change cost and refusal reasons | The player's school choice and change UI |
| Jianghu Chronicle and AI text (36) | Soft | `school_joined`, `school_changed` (milestones) | The second-life moment in the member's story |

"Hard" means the dependent cannot meet its own acceptance criteria without this system.

**Bidirectional status.** Data layer (3) lists this system. The Event bus (42) covers it under "feature systems that emit". Every other system above is undesigned and must list this system when it is designed. The systems index row 20 lists only the Data layer. It should also list Sim core and Event bus, which are hard upstream dependencies (proposed in Phase 5, not made silently).

**Provisional assumptions about undesigned systems.**
1. XP curve (22) emits one level-up event (2201) per award, carrying the old and new level, even when several levels are gained (XP curve R6; resolved 2026-11-16).
2. Member state machine (41) has a `training` state that blocks hunting, raids, parties, rebirth and leave requests.
3. ~~Guild storage accepts returned gear beyond its cap (30).~~ RESOLVED (consistency-check 2026-11-16): storage is Items and loot's and is uncapped (Items R7).
4. Skills (21) stores levels per skill and lets prerequisites gate only further learning.
5. Combat (10) treats a missing element as ×1.0.
6. Offline progress (31) applies F1 and R5 at their exact ticks.

## Tuning Knobs

All knobs are `config.csv` rows, read once at load (Data layer R10). They were derived from Section D's variable tables: every `data file` variable owned here is a knob, and every value owned by another GDD is pointed to under "Not knobs". All defaults are provisional until the balance sim (§4.4) measures change frequency and gold flow.

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `school_join_level` | 10 | 1 – 20 | The unaffiliated stage drags (level 10 already takes about 2–4 h AFK, §4.3), and members fight without an element longer | Fantasy 2's choice disappears, because members join almost at once | Recruitment's arrival levels (0 or 10, §6.7): at or below 10, a level-10 recruit joins on arrival; XP curve early pacing |
| `school_change_skill_keep_pct` | 30 | 0 – 49 | A change costs little in skills, and schools stop being a commitment | A change erases nearly everything, so Fantasy 3 feels like starting over | Rebirth's `skill_keep_pct` (lowest 50): must stay below it |
| `school_change_income_hours` | 4 | 0 – 48 | Changes become unaffordable mid-game and the sink is avoided entirely | Gold stops gating, and only the token and cooldown limit changes | `income_ref_per_level` (Gold economy); §19.5's 60–90% out/in target |
| `school_change_item_count` | 1 | 0 – 5 | Token supply becomes the bottleneck | 0: the token is not needed | The token's drop or craft rate (OQ-2) |
| `school_change_duration_s` | 14,400 (4 h) | 60 – 86,400 | A member is out of play for most of a day per change | The change is instant in practice, and the commitment weakens | Offline gaps (the change may complete during one); party and raid availability |
| `school_change_cooldown_s` | 604,800 (7 days) | 0 – 2,592,000 | A guild cannot fix a mistake for weeks | 0: schools can be flipped per Golden Boss, if the gold allows | `school_change_income_hours` (both limit frequency); the free credit, which ignores it |
| `school_change_academy_level` | 1 | 1 – 10 | School change unlocks very late | 1 is the minimum: the Academy must exist | `bld_academy_skill` levels in `buildings.csv` |

**Validator rules for the Data layer:**
- `school_join_level` is a whole number in 1 – 20 and at most the rebirth-0 level cap (`rebirth.csv`, 100).
- `school_change_skill_keep_pct` is a whole number in 0 – 49 and below the smallest `skill_keep_pct` in `rebirth.csv`.
- `school_change_income_hours` is 0 – 48, `school_change_item_count` is 0 – 5, `school_change_academy_level` is 1 – 10 and at most the Academy's highest level.
- `school_change_duration_s` is 60 – 86,400 and `school_change_cooldown_s` is 0 – 2,592,000, both whole seconds.
- `item_school_token` exists in `items.csv` as a `special` item.

**Interactions.**
- `school_change_income_hours`, `school_change_item_count` and `school_change_cooldown_s` all limit how often a guild changes. Setting all three to 0 leaves only the training time. Tune one at a time.
- `school_change_skill_keep_pct` is the felt cost that the free change keeps (R6). Lowering it makes a free change less of a gift, because the skills are still lost.

**Not knobs, and where their values live.**
- **`income_ref_per_level`** (1,000) belongs to Gold economy (27).
- **`tick_rate`** belongs to the Sim core (1).
- **The school rows themselves** (element, role, buffer flag, armour class, wave) are content in `schools.csv`. Changing one is a content patch under the Data layer's rules, not tuning.
- **The free-change grant** is the `free_school_change` reward in `rebirth.csv`, owned by Rebirth (23).
- **The skill slot layout** (12 slots, the same in every school) is a validator invariant owned by Skills (21), on which F4 relies.
- **The event type block 2000–2099 and its declared ring rate** (F5) are permanent IDs and a design constant.

*Lens applied: systems-designer (Section G), economy-designer for the cost knobs.*

## Visual/Audio Requirements

This system owns no rendering. It sets three requirements for the presentation systems:
- **School identity is visible.** Each school has a distinct outfit and weapon layer in the paper-doll set, with an element palette (§12.4, art pipeline), so the roster reads as a party plan (Fantasy 1). That visual identity is owned by the art bible, which does not exist yet.
- **Element is never shown by colour alone.** An element icon or glyph accompanies every element colour (accessibility floor).
- **The two milestone moments get a beat.** `school_joined` and `school_changed` deserve a short visual and audio cue in the Realtime world view (38) and Audio (40), suppressed during catch-up (Sim core R15). They own the cue design.

No art bible exists, so no art-bible principle is cited.

## Game Feel

Not a feel system. Its timing promises:
- An order (set aspiring school, change school) is acknowledged in the UI at once, and applied in P1 of the next tick (≤ 100 ms at 10 Hz).
- A change visibly enters `training` on that tick and completes exactly at its due tick, including across an offline gap (F3).
- A refused order always shows its reason code in words (UI Requirements), never a silent no-op.

## UI Requirements

This system needs player-facing UI. Guild screens (39) own the screens, and this section lists what they must offer:
1. **Recruit and member cards** show the school (name, element glyph, role) or, for an unaffiliated member, "Unaffiliated → [aspiring school]" with the joining level.
2. **Aspiring-school picker** for an unaffiliated member. It lists only live schools, and shows each one's element, role, buffer flag and armour class. It marks what the guild currently lacks (no buffer, no counter to the next Golden Boss's element), as an aid to Fantasy 1, never as an automatic choice.
3. **School-change dialog** at the Academy. It shows:
   - the target list (live schools other than the current one);
   - the cost: gold (F2) and the token, or "Free" when a credit is held;
   - the training time (F3);
   - the skill carry preview, slot by slot (F4);
   - which equipped items will go to storage (R5);
   - the cooldown remaining, if any.

   The confirm button names the irreversible part: "the change cannot be cancelled".
4. **Refusal reasons** (R4, Edge Cases) are shown as plain text through `i18n/` keys, one per reason code.
5. **A member in `Changing`** shows the target school and the time remaining.

Every string goes through Localization (4), and the school names are the IDs' `i18n` names.

## Cross-References

| This document references | Target | Element | Nature |
|---|---|---|---|
| `schools` table, `wave` column, liveness query | `data-layer-and-content-pipeline.md` | R2, R5, F2 | Data dependency |
| IDs are meaning-free; the element cycle is declared once | `data-layer-and-content-pipeline.md` | R3, R4 | Rule dependency |
| Roster invariants (10 schools, 5 in Wave 1, a buffer in Wave 1) | `data-layer-and-content-pipeline.md` | R8 | Ownership handoff: the Data layer's validator enforces them |
| School IDs as content `uid`s in events | `data-layer-and-content-pipeline.md` | R6 | Data dependency |
| Display names in `i18n/` | `data-layer-and-content-pipeline.md` | R9 | Rule dependency |
| Commands applied in P1, ordered by `seq` | `sim-core-and-tick-loop.md` | R2, R6 | Rule dependency |
| Anchored deadline ticks for change completion | `sim-core-and-tick-loop.md` | R5 | Rule dependency |
| `tick_rate` | `sim-core-and-tick-loop.md` | F1; registry `tick_rate` | Data dependency (F3) |
| Type registration, blocks of 100, `ring_per_day`, milestones | `event-bus-and-history-log.md` | R3, R3a, F4 | Rule dependency (R8, F5) |
| Roster changes are milestones | `event-bus-and-history-log.md` | R3a | Rule dependency (`school_changed` is a milestone) |
| `income_ref_per_level` | `JX1_Tycoon_GDD.md` | §19.1 | Data dependency (F2), owned by Gold economy (27) when designed |
| Schools, joining, school change, free change at rebirth | `JX1_Tycoon_GDD.md` | §6.1, §6.9, §6.10 | Source of intent |
| Five Elements multipliers | `JX1_Tycoon_GDD.md` | §4.2 | Owned by Combat (10); this system supplies only the element |

## Acceptance Criteria

Story types follow the Testing Standards:
- **[Logic]** is the default: an automated unit test under `tests/unit/schools/`. Logic tests use a fake member store, a fake guild (fund, storage, Academy level) and a fake context, so no other system is needed.
- **[Integration]** uses the real Sim core and Event bus, under `tests/integration/schools/`.

Values come from a fixture factory. Tests do not read the real `config.csv`, except where a boundary value is the point. A criterion with several GIVEN/THEN pairs is one parametrized test with one case per pair. `[PENDING: …]` marks a criterion that needs an undesigned system; it is a separate criterion, so the others can close.

**Core rules**

- **AC-1 (R1)**: **GIVEN** the real `schools.csv`, **WHEN** it is loaded, **THEN** each school's `element`, `role`, `buff_role`, `weapon`, `armor_class` and `wave` are readable by ID, and no code path derives an element from the ID string (a test school `xx_9` with `element = kim` is Kim).
- **AC-2 (R1, liveness)**: **GIVEN** `live_wave = 1`, **THEN** `set_aspiring_school` and `change_school` accept `moc_1` (Wave 1) and refuse `thuy_2` (Wave 2) with `not_live`. **GIVEN** a member already in a school that is then marked `retired`, **THEN** the member keeps it and keeps its element.
- **AC-3 (R2)**: **GIVEN** a test handler of another system that writes `school_id` directly, **THEN** the write is impossible through the public API. Only this system's appliers change R2 fields. This is checked by an API-surface test listing the writers.
- **AC-4 (R3, join)**: **GIVEN** an unaffiliated member at level 9 with aspiring school `moc_1` and `school_join_level = 10`, **WHEN** a level-up event to 10 is delivered in tick N, **THEN** in P1 of tick N + 1 `school_id = moc_1` and the element is `moc`. Every `moc_1` skill is at level 0, and one `school_joined` event is emitted.
- **AC-5 (R3, unaffiliated)**: **GIVEN** an unaffiliated member, **THEN** their element is `none`, the R7 rule refuses every weapon, and it allows armour of all three classes and any accessory.
- **AC-6 (R3, recruit at level)**: **GIVEN** a recruit created unaffiliated at level 10 with a live aspiring school, **THEN** they join on the tick after arriving. **GIVEN** a recruit created with a school, **THEN** they start `Affiliated` and no join happens.
- **AC-7 (R3, gear on join)**: **GIVEN** an unaffiliated member wearing heavy armour who joins `moc_1` (light), **THEN** the armour is in guild storage and not on the member. The item count across member and storage is unchanged.
- **AC-8 (R4, refusals)**: **GIVEN** each of these, **WHEN** `change_school` is applied, **THEN** it is refused with the named reason, and the fund, storage, credit and R2 fields are unchanged:
  - an unaffiliated member → `not_affiliated`;
  - a change already in progress → `change_in_progress`;
  - a target that is not live → `not_live`;
  - the same school → `same_school`;
  - a member in `boss_raid`, `away`, `dead` or `injured` → `busy`;
  - an Academy below `school_change_academy_level` → `no_academy`;
  - a missing token, or missing gold → `cannot_afford`;
  - a paid change inside the cooldown → `cooldown`.
- **AC-9 (R4, accept)**: **GIVEN** a level-60 `kim_1` member with no credit, Academy level 1, the fund at 240,000 and 1 token in storage, **WHEN** `change_school(moc_1)` is applied in tick N, **THEN** the fund is 0, storage holds 0 tokens, `change_target_id = moc_1`, and `change_due_tick = N + 144,000`. The member is in `training`, is still `kim_1` with element `kim`, and one `school_change_started` event is emitted.
- **AC-10 (R5, completion)**: **GIVEN** the AC-9 state, **WHEN** tick N + 143,999 runs, **THEN** the member is still `kim_1`. **WHEN** tick N + 144,000 runs, **THEN** in its P5 the member is `moc_1`, the change fields are cleared, `last_paid_change_tick = N + 144,000`, the member is out of `training`, and one `school_changed` event with `free_flag = 0` is emitted.
- **AC-11 (R5, gear on change)**: **GIVEN** the AC-9 member wielding a `kim_1` weapon and wearing heavy armour, **WHEN** the change to `moc_1` completes, **THEN** both are in guild storage, and an accessory the member wears stays on.
- **AC-12 (R6, free credit)**: **GIVEN** a member completing rebirth tier 1 (`free_school_change=1`), **THEN** `free_change_credits = 1`. **GIVEN** a member completing tier 2 (no grant), **THEN** the count is unchanged. **GIVEN** a credit already held and another granting rebirth, **THEN** the count stays 1.
- **AC-13 (R6, free change)**: **GIVEN** a member with a credit, an empty fund and no token, **WHEN** `change_school` is applied inside the paid cooldown, **THEN** it is accepted, the credit is 0, the fund and storage are unchanged, and the training time still applies. **WHEN** it completes, **THEN** `last_paid_change_tick` is unchanged and `free_flag = 1`.
- **AC-14 (R7)**: **GIVEN** a `moc_1` member, **THEN** a weapon with `school_req = moc_1` is allowed and one with `school_req = kim_1` is refused. Light armour is allowed, heavy and medium are refused, and every accessory is allowed.
- **AC-15 (R8) [Integration]**: **GIVEN** the bus sealed with this system registered, **THEN** types 2001–2004 exist with the flags in F5: 2001 and 2003 are milestones with `subject_slot = 1`, 2002 is logged with `ring_per_day = 20`, and 2004 is not logged. **WHEN** a member joins and later changes, **THEN** `milestones_for(member_id)` returns the `school_joined` and `school_changed` records in tick order, carrying school `uid`s, not strings.

**States**

- **AC-16 (States)**: **GIVEN** the transition table, **WHEN** each listed trigger is applied from each state, **THEN** the resulting state matches the table. **GIVEN** any trigger not listed (for example `join_school` while `Affiliated`, or any attempt to return to `Unaffiliated`), **THEN** it is refused and the state is unchanged.

**Formulas**

- **AC-17 (F1)**: **GIVEN** `school_join_level = 10`, **THEN** `join_due` is false at level 9, true at 10, and true at 15 for a member who jumped past it. It is false for an affiliated member, and false when the aspiring school is not live.
- **AC-18 (F2)**: **GIVEN** the defaults, **THEN** `change_gold_cost` is 40,000 at level 10, 240,000 at 60 and 800,000 at 200. **GIVEN** `school_change_income_hours = 0`, **THEN** it is 0 and the token is still required. **GIVEN** a free change, **THEN** both costs are 0.
- **AC-19 (F3)**: **GIVEN** `tick_rate = 10`, **THEN** a duration of 60 s gives 600 ticks and 14,400 s gives 144,000. A cooldown of 0 allows a second paid change in the tick after the first completes, and 604,800 s allows it no earlier than 6,048,000 ticks after completion.
- **AC-20 (F4)**: **GIVEN** `school_change_skill_keep_pct = 30` and an old school with slot 1 at 20, slot 5 at 10, slot 3 at 3 and slot 9 at 10, held by a level-80 member with no rebirth, **WHEN** the change completes, **THEN** the new school's slot 1 = 6, slot 5 = 3, slot 3 = 0 and slot 9 = 3, and slot 11 (`rebirth_req` 1) = 0. **GIVEN** keep 0, **THEN** every slot is 0. **GIVEN** keep 49 and slot 1 at 20, **THEN** slot 1 = 9.
- **AC-21 (F5)**: **GIVEN** the registered types, **THEN** the sum of this system's `ring_per_day` is 20, and no type outside 2000–2099 is registered by `owner_id = "schools"`.

**Edge cases and cross-system**

- **AC-22 (Edge Cases, same tick)**: **GIVEN** two `change_school` commands for one affordable member in one tick, **THEN** the lower `seq` is accepted and the higher is refused with `change_in_progress`, and the cost is taken once.
- **AC-23 (Edge Cases, storage)**: **GIVEN** guild storage at its cap, **WHEN** a change returns two items, **THEN** storage holds its previous count + 2 and no item is lost (storage is uncapped, Items R7; the "at its cap" precondition is void).
- **AC-24 (Edge Cases, aspiring not live)**: **GIVEN** a member reaching `school_join_level` with an aspiring school that is not live, **THEN** they stay `Unaffiliated`, and exactly one `school_change_refused` with `aspiring_not_live` is emitted. **WHEN** the player then sets a live aspiring school, **THEN** they join on the next tick.
- **AC-25 [Integration] (Edge Cases, offline)**: **GIVEN** a change due at tick D and an offline gap covering D, **WHEN** the gap is resolved, **THEN** the member is in the new school with the F4 levels, as in a run with no gap `[PENDING: Offline progress (31)]`.
- **AC-26 [Integration] (Edge Cases, training blocks)**: **GIVEN** a member in `Changing`, **THEN** a party assignment and a rebirth order are both refused `[PENDING: Party (13), Rebirth (23), Member state machine (41)]`.
- **AC-27 (Tuning Knobs, validator) [PENDING: Data layer validator]**: **GIVEN** `school_join_level` 0 or 21, `school_change_skill_keep_pct` 50, `school_change_duration_s` 59, `school_change_cooldown_s` 2,592,001, or no `item_school_token` row, **THEN** each is rejected. **GIVEN** each knob at both ends of its safe range, **THEN** each is accepted.

**Gaps, recorded not hidden**
1. **Fantasy 1** ("the roster reads like a party plan") is a readability goal. No automated test proves it. It is a playtest question for Guild screens (39): can a tester name the guild's missing role within 10 seconds of opening the roster?
2. **R4 condition 3** depends on the Member state machine's list of states. AC-8 tests the four states named here, and the full list arrives with that GDD (41).

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | The Academy (`bld_academy_skill`) is not in the MVP building set, so school change cannot be used in MVP. Ship the Academy in MVP, or accept that MVP has joining only? | Producer, with Guild and buildings (30) | Before MVP sprint planning |
| OQ-2 | Source and rarity of `item_school_token`: partly answered (user decision 2026-11-16) — it is a Linh Bảo shop item (Gold economy R16, `lb_price_school_token`). Open: is there also a Golden Boss drop or an Academy craft? Its supply sets how often changes really happen | Items and loot (26), Crafting (28) | When those GDDs are designed |
| OQ-3 | Should the free credit expire at the next rebirth (§6.9's "the first change in each rebirth cycle"), or persist until used? Today it persists | This GDD, with Rebirth (23) | When Rebirth is designed |
| OQ-4 | Combat must define the neutral element case for an unaffiliated member (×1.0 both ways) | Combat (10) | When Combat is designed |
| OQ-5 | The Python reference sim gives every member a school from level 1. It needs the unaffiliated stage and joining (R3) before the balance sim measures early pacing | Dev tooling and balance sim (43) | Before the balance sim retunes F2–F4 |
| OQ-6 | Does Ascension's `guild_buff_by_school` read the Elder's school at Ascension, or their current school (Elders do not change school)? | Rebirth and Ascension (23) | When Rebirth is designed |
| OQ-7 | Add "exactly two schools per element" to the validator's roster invariants (R1) | Data layer (3) | When the Data layer next changes |
