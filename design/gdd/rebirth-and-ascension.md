# Rebirth and Ascension

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet); anchored to JX1 GDD §1, §4.3 and §6.10

## Summary

Rebirth and Ascension is how a member who has hit the level cap keeps growing. The player spends Rebirth Pills and guild gold at the Shrine (Linh Miếu) to rebirth them. Five rebirths raise the cap from 100 to 200, cost part of their skill levels, make each later level slower and unlock new content. At level 200 with CA 180 or more, a member can **ascend** and become an **Elder**. An Elder stops hunting, hands their gear back to the guild and gives a permanent guild-wide buff based on their school and revealed traits. The system exists to make the game endless (JX1 GDD §6.10): the guild keeps raising recruits, and its best members graduate into its legacy.

> **Quick reference** — Layer: `Feature` · Priority: `Alpha` (Wave 1 ships rebirth 1 only; rebirths 2–3 come in Wave 2; rebirths 4–5 and Ascension in Wave 3) · Key deps: `Member model, Skills, XP and level pacing curve, Gold economy, Data layer and content pipeline, Items and loot tables, Guild and buildings, CA/PA and traits, Schools and school change, Command layer, Event bus and history log`

## Overview

This system owns the `rebirth.csv` ladder and the two player commands that climb it, `rebirth_member` and `ascend_member`. **Data layer:** each member carries a `rebirth` tier from 0 to 5 and a `rank` (`disciple` or `elder`). Member model (8) stores both, and this system is the only one that writes them. A rebirth checks a fixed list of gates: the member is at the level cap, the Shrine is built high enough, the tier's wave is live, the member is at home, and the pills and gold are there. It then takes the cost, raises `rebirth` by one and tells Skills (21) to cut each skill to the tier's `skill_keep_pct`. It also hands out that tier's one-time rewards through each owner's own API. The ongoing rewards (the XP bonuses, the drop bonus, secret skills, the high Tower floors) are not applied here. Each owner reads them from `rebirth.csv` against the member's `rebirth` field. Ascension is the sixth row of the ladder: it turns a level-200, CA-180 disciple into an Elder. **Player impact:** a capped member is a decision. Rebirth them now and pay pills, gold and skill levels for a higher ceiling and slower levels? Or keep them as they are? At the very end, is a top member worth more hunting or as an Elder whose buff reaches every disciple? Without this system the game stops at level 100, and the CA/PA promise ("every member has a hidden ceiling") has no final payoff. This GDD stays at the behaviour level. How the elder-buff lookup is cached and where the appliers live are left to an ADR.

## Player Fantasy

**Direct and indirect: "my disciples become masters, and my masters become the guild."** The player feels rebirth directly. A veteran of a hundred levels stands at the Shrine, gives up half their technique and rises again with a higher ceiling. Ascension is the graduation. The member who arrived as a nameless walk-in, whose star rating the player studied for weeks, takes their place among the Elders. From then on every new recruit fights a little better because they came before.

Three framings were considered (creative-director lens; no pillars exist, so each is anchored to JX1 GDD text instead of a pillar):

1. **"The long apprenticeship"** (chosen). Moment: the player watches an old disciple's skill bars drop at the Shrine, then watches them climb past where they used to stop. Anchor: §4.3, "nhanh đầu game, chậm dần theo chuyển sinh" (fast early game, slower after each rebirth), and §6.10, "bang liên tục nhận người mới và 'tốt nghiệp' người cũ thành buff vĩnh viễn" (the guild keeps taking in new members and "graduating" old ones into permanent buffs). The rules must deliver this: a visible cost (skill loss) and a visible gain (a cap that rises, new secret skills).
2. **"The lineage"**. Moment: the Elders' hall shows five portraits, each with the buff they left. Anchor: §6.10's Elder. This framing makes the Elders a collection, so it asks for an Elders' hall (no slot limit, user decision 2026-11-16) and an Elder screen (UI Requirements). It is folded into framing 1 as the ending.
3. **"The cultivation ascent"** (rejected). It presents rebirth as raw power gain. But rebirth makes each level slower (×3 to ×18 XP need), so a pure power framing promises something the numbers do not deliver.

*What the chosen framing asks of the design:* the cost has to be felt (skill loss, pills, gold), so the rewards also have to be felt. Each tier unlocks something the player can name (a secret skill, a free school change, a revealed trait, new zones). An Elder's buff also has to name the member it comes from.

## Detailed Design

*Specialist lenses applied (Section 6 routing, row "Progression/XP/skills": game-designer primary; systems-designer, economy-designer supporting; no agents spawned):*
- **game-designer:** the decision is *when* to rebirth and *whom* to ascend. Rebirth must never happen automatically: the AI never issues it, because the guild master decides (GDD §1). The member keeps their level and gear, so the cost has to come from skills, pills, gold and the slower XP curve.
- **systems-designer:** every one-time reward must be applied in the same applier call as the tier change. If it waits for P6, a `change_school` queued after the rebirth in the same batch would miss the free credit. The ongoing rewards must have exactly one reader each, keyed on `rebirth`, never copied onto the member. Elder buffs must be a pure function of the roster, so the replay verifier (35) reproduces them.
- **economy-designer:** rebirth gold is a burn from the fund (Gold economy entry type 24). The binding constraint should be XP time and pills, not gold (see F4), so gold works as a sink, not a wall. Elder buffs are a permanent faucet multiplier, so they need a per-key cap. (A slot limit was proposed; the user removed it on 2026-11-16, so the per-key cap is the only bound.)
- *Tension found and resolved:* the GDD's "endless loop" and a fixed number of Elder slots pulled against each other. **User decision 2026-11-16 (OQ-1):** Elders are unlimited; there is no slot gate, and the per-key cap (F3) alone bounds the buff.

### Core Rules

**R1: One owner of `rebirth` and `rank`.** Member model (8) stores both fields. This system writes them, and only through R4 and R6. `rebirth` only goes up (0 → 5) and `rank` only goes from `disciple` to `elder`. Nothing lowers either one, and there is no "un-rebirth".

**R2: The ladder is `rebirth.csv`.** It has six rows. Rows 1–5 are `kind = rebirth`, where `no` is the tier the member reaches. Row 6 is `kind = ascension`. The columns: `req_level` (the level the member must be at), `new_level_cap`, `skill_keep_pct`, `pill_cost`, `gold_cost`, `rewards` (a `key=value` list, R3) and `wave`. XP curve (22) R3 reads the caps from this table, and the existing validator rules stay: `req_level` of row n+1 = `new_level_cap` of row n, `skill_keep_pct` strictly increasing, and `wave` matching the rebirth-wave map. This GDD adds these validator rules:
- every `rewards` key is in the R3 table (an unknown key is an ERROR, Data layer R8);
- `pill_cost` ≥ 0, and `gold_cost` from 0 to `gold_op_max`;
- the ascension row has `ca_min` from 0 to `ca_max`;
- `unlock_secret=k` on row n matches `skills.csv`: the secret skills of slot 10+k have `rebirth_req = n` (cross-check; `skills.csv` is authoritative).

**R3: Reward keys, their kind and their reader.** There are three kinds:
- *One-time* rewards fire once, when the member completes that row (R4 step 6). This system calls the owner.
- *From-tier* rewards are true for every member with `rebirth ≥ n`. The owner reads them.
- *Cumulative* rewards add up the values of rows 1..`rebirth`. The owner sums them.

| Key | Rows today | Kind | Meaning | Applied by |
|---|---|---|---|---|
| `trait_slot_reveal` | 1, 4 (=1) | one-time | Reveal one hidden trait | CA/PA and traits (9) R11, via `reveal_on_rebirth(member_id, rebirth_no)` (PROVISIONAL name). The validator restricts the value to 1, because 9 reveals one |
| `free_school_change` | 1 (=1) | one-time | Free school change credit | Schools (20) R6, via `grant_free_change(member_id)` (PROVISIONAL name). Credits never stack (Schools R6) |
| `unlock_secret` | 1 (=1), 3 (=2) | from-tier | Secret skill k becomes learnable | Skills (21), through `skills.csv` `rebirth_req`; the reward key is a display label and a validator cross-check (R2) |
| `xp_pct` | 1, 4 (=0.10) | cumulative | Member-side XP bonus | XP curve (22) R5, `bonus_ppm[r]` |
| `growth_bonus` | 2 (=0.05) | cumulative | Bonus added to the PA growth multiplier | XP curve (22) R5, `growth_bonus_ppm[r]` |
| `drop_rate` | 3 (=0.05) | cumulative | Rare drop bonus | Items and loot (26), `rebirth_drop_milli` |
| `unlock_tower_high` | 2 (=1) | from-tier | High Tower floors open | Endless Tower (19), PROVISIONAL |
| `unlock_ascension` | 5 (=1) | from-tier | Ascension may be ordered | This system (R6) |
| `become_elder` | 6 (=1) | ascension | Rank becomes `elder` | This system (R6) |
| `ca_min` | 6 (=180) | ascension gate | Minimum CA to ascend | This system (R6, F5) |
| `guild_buff_by_school` | 6 (=1) | ascension | The Elder gives the guild buff (F3) | This system (R8) |

**R4: `rebirth_member(member_id)` (command 2301, host only).** The applier runs in P1. It checks the gates **in this order** and refuses at the first one that fails, with that reason code (R9), taking nothing:
1. The member exists, is on the roster and has `rank = disciple`. A missing member gets Command layer's generic code; an Elder gets 112.
2. `rebirth < 5`. Otherwise 102: the member must ascend.
3. The member is `Capped`: `level = cap[rebirth]` (XP curve 22 states). Otherwise 101.
4. Row n = `rebirth + 1` is live (Data layer F2, by its `wave`). Otherwise 103.
5. The guild's Shrine allows it: `effect(bld_shrine, rebirth_max) ≥ n` (Guild and buildings 30). Otherwise 104.
6. The member has no school change in progress (`change_target_id` is `none`, Schools R4). Otherwise 106. This is checked before the state check, so the player sees the specific reason.
7. Member state machine (41) reports the member at home and free: not `hunting`, `boss_raid`, `away`, `dead`, `injured` or `training` (PROVISIONAL list, like Schools R4 rule 3). Otherwise 105.
8. The member's own inventory holds at least `pill_cost[n]` of `item_rebirth_pill` (Items 26 R9: the pill is member-held). Otherwise 107.
9. `can_debit(fund, gold_cost[n])` (Gold economy 27). Otherwise 108.

**When the command is accepted**, in this order, in the same applier call:
1. Debit `gold_cost[n]` from the guild fund as a `rebirth_cost` burn (entry type 24, `ref_uid = member_id`). A cost of 0 is skipped, with no ledger entry.
2. Consume `pill_cost[n]` pills from the member's inventory (Items 26, PROVISIONAL `consume_member_item(member_id, item_id, qty)`).
3. Set `rebirth = n`. The XP curve now reads `cap[n]`, so the member is `Growing` again at the same level with `xp_milli` 0 (XP R7). Level, XP, equipment, gold, traits and school are not touched.
4. Call Skills (21) `set_levels(member_id, kept)`, where `kept` is Skills F7 per slot with `skill_keep_pct[n]`.
5. For each one-time key in row n's rewards, call its owner, in the R3 table's order (trait reveal, then free change).
6. Emit **2301 `member_reborn`** (R7).

Steps 1–6 cannot fail after the gates pass: every precondition was checked against the same state in the same call. A failure there is a defect, and the applier calls `ctx.fail(2399, …)` (Sim core fatal sink) instead of leaving a half-done rebirth.

**R5: What rebirth keeps and what it costs.**
- *Kept:* level, equipment (GDD §6.10: "toàn bộ trang bị" (all equipment), at every tier), traits, school, gold, the skill bank and focus (Skills R8), loyalty and mood.
- *Lost or paid:* skill levels above F7, the pills, the gold, and speed, because each later level needs `xp_rebirth_mult[n]` times the base XP (XP curve F1).
- *Gained:* a cap 20 levels higher, the row's rewards (R3), and access to content gated on `rebirth_req` (zones, skills).

**R6: `ascend_member(member_id)` (command 2302, host only).** The applier runs in P1. It checks these gates in order:
1. The member exists, with `rank = disciple`. Otherwise generic code or 112.
2. `rebirth = 5` (the `unlock_ascension` tier) and `level = cap[5]` (200). Otherwise 109.
3. The ascension row is live. Otherwise 103.
4. `effect(bld_shrine, phi_thang) = 1`. Otherwise 104.
5. No school change in progress (106), and the member is at home and free (105), as in R4.
6. `ca(member_id) ≥ ca_min` (CA/PA 9 R3, computed now). Otherwise 110.
7. *(Removed, user decision 2026-11-16: there is no Elder count gate; Elders are unlimited, F2.)*
8. Pills (if `pill_cost > 0`, today 0): 107. Gold: `can_debit(fund, gold_cost)`, otherwise 108.

**When the command is accepted**, in this order:
1. Debit `gold_cost` as `rebirth_cost` (entry type 24). Consume pills if any.
2. Move every equipped item to guild storage (Member model `unequip`, R6: an item is never destroyed). The Elder's best gear goes to the next generation.
3. Set `rank = elder`. The member stops counting against `member_cap` (Member model state table); Elders have no cap of their own (F2). Skills are not touched: the ascension row's `skill_keep_pct` is 100, so F7 would change nothing.
4. Ask Member state machine (41) to place the member in `elder`, a terminal state (PROVISIONAL). An Elder never hunts, raids, trains or is assigned to a party. They earn no XP (XP curve: Hunt does not call `award` for them) and never leave (R10).
5. Emit **2302 `member_ascended`** (R7).

Ascension needs no Rebirth Pills, because the `rebirth.csv` row has `pill_cost` 0. GDD §6.10's "vật phẩm đặc biệt" (special item) has no matching item, so it is not modelled. See OQ-3.

**R7: Events.** This system registers block **2300 – 2399** with the Event bus (`rebirth_event_type_block`) and uses the same numbers for its command IDs (Command layer R2 ID rule).

| `type_id` | Name | Fields | `logged` | `milestone` | `subject_slot` | `ring_per_day` |
|---|---|---|---|---|---|---|
| 2301 | `member_reborn` | `a` member_id, `b` new rebirth_no, `c` gold paid, `d` pills paid | yes | yes | 1 | 0 |
| 2302 | `member_ascended` | `a` member_id, `b` school_id at ascension, `c` CA at ascension, `d` Elder count after | yes | yes | 1 | 0 |

Both are milestones because both are promotions (Event bus R3a). A member has at most 6 such records in a lifetime, within `milestone_cap_per_subject` (24). Refusals are reported by Command layer's 502 `command_refused` with this system's reason code. This system emits no refusal event of its own, because both commands are host-only.

**R8: The Elder buff.** Every Elder contributes to a guild-wide modifier table `elder_mod_ppm(effect_key)` (F3), from two sources:
- **School:** one `(effect_key, value)` row per school in a new data file, `data/elder_buffs.csv` (proposed defaults in Tuning Knobs). The school used is the Elder's `school_id`. An Elder never changes school (R10), so this is also the school they had at Ascension (this answers Schools OQ-6).
- **Traits:** each **revealed** trait of the Elder whose `category` is in `elder_trait_categories` (default `talent`, `insight`, `luck`) shares every one of its effects at `elder_trait_share_ppm` (default 25%). Hidden traits share nothing, which is one more reason to reveal traits before Ascension. Negative effects share too. The player can see every revealed trait before ascending, so the choice is informed.

The table applies to every **disciple** and never to Elders. This system does not apply it itself. CA/PA and traits (9) adds `elder_mod_ppm(key)` to the result of `trait_mod_ppm(member_id, key)` for disciples (PROVISIONAL). That way every system that already reads trait modifiers gets the Elder buff with no new read path. The table is a pure function of the roster: the set of Elders, their `school_id` and their revealed traits. It is never saved.

**R9: Reason codes** (owner range 100 – 999, Command layer R6). Localisation keys are `cmd_reason.rebirth.<name>`.

| Code | Name | Meaning |
|---|---|---|
| 101 | `not_capped` | Level is below the current cap |
| 102 | `max_rebirth` | Already at tier 5; Ascension is next |
| 103 | `tier_not_live` | The next row's wave is not released |
| 104 | `shrine_level` | `bld_shrine` `rebirth_max` too low, or `phi_thang` = 0 |
| 105 | `member_busy` | Member state forbids it (hunting, raid, away, dead, injured, training) |
| 106 | `changing_school` | A school change is in progress |
| 107 | `pills_missing` | The member holds fewer than `pill_cost` pills |
| 108 | `gold_missing` | The guild fund cannot pay `gold_cost` |
| 109 | `not_ascension_ready` | Not at tier 5 and level 200 |
| 110 | `ca_too_low` | CA below `ca_min` |
| 111 | `elder_slots_full` | **Retired (user decision 2026-11-16):** never emitted, because there is no Elder slot gate. The code stays reserved and is never reused |
| 112 | `is_elder` | The member is already an Elder |

**R10: Elders are permanent.** An Elder stays on the roster for good. Rebirth never calls `remove_member` (Member model R9). Retention (16) excludes Elders from leaving, contract and mood rules, and `dismiss_member` refuses an Elder (Retention R1, code 104). Schools (20) refuses `change_school` for an Elder (Schools R4 condition 3). Elders still count toward upkeep (Gold economy F3 sums the whole roster). This is this GDD's recommendation for Gold OQ-13: a level-200 Elder costs 140,000 gold a day, about 0.1% of a late guild's daily member income, so making an exception is not worth it. **With unlimited Elders (2026-11-16) this still holds and becomes the soft brake:** upkeep grows linearly with the Elder count while the buff stops growing at the cap (F3), so an Elder past the cap on every key they touch is a pure cost the player can see. Ten Elders cost 1.4M a day (about 1% of that income); retention needs no change because Elders are `Exempt` (Retention R1).

**R11: `rebirth_status(member_id)` query.** A pure query that runs the R4 gates (or the R6 gates, at tier 5) without taking anything. It returns `ready_rebirth`, `ready_ascend`, `elder`, or `blocked(first_reason_code)`, plus the costs. The UI's "ready to rebirth" badge (XP curve UI Requirements) and the appliers call the same gate function, so the screen and the command can never disagree.

**R12: No automation.** Utility AI (12) never submits 2301 or 2302, and nothing in the simulation does either (both are host-only). Offline progress does not rebirth: a member who reaches the cap offline waits `Capped`, and their extra XP is discarded (XP R4). The return screen lists the members who are ready (UI Requirements).

### States and Transitions

The rebirth position is derived from `rebirth`, `rank`, `level` and `cap[rebirth]`. It is not a stored state.

| State | Condition | Can do |
|---|---|---|
| `Tier r · Growing` (r = 0–5) | disciple, `level < cap[r]` | Earn XP; no rebirth (101) |
| `Tier r · Capped` (r = 0–4) | disciple, `level = cap[r]` | `rebirth_member`, subject to the R4 gates |
| `Tier 5 · Capped` | disciple, `rebirth = 5`, `level = 200` | `ascend_member`, subject to the R6 gates |
| `Elder` | `rank = elder` | Nothing; gives F3 buff. Terminal |

| From | To | Trigger |
|---|---|---|
| `Tier r · Growing` | `Tier r · Capped` | XP curve `award` reaches the cap (XP 2202) |
| `Tier r · Capped` (r < 5) | `Tier r+1 · Growing` | `rebirth_member` accepted (2301) |
| `Tier 5 · Capped` | `Elder` | `ascend_member` accepted (2302) |

No other transitions exist. In particular, nothing goes from `Elder` back to disciple, no transition lowers the tier, and nothing skips a tier: one command moves one tier.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|---|---|---|---|---|
| Data layer (3) | in | `rebirth.csv`, `elder_buffs.csv` (new), config knobs; liveness by `wave` | — | Data layer owns loading; this system owns the rows' meaning and the R2 validator rules |
| Command layer (5) | in | Commands 2301, 2302 (host) | Reason codes R9; applier cost (F6) | Command layer owns dispatch |
| Member model (8) | both | `rank`, `rebirth`, `level`, inventory, equipment | Writes `rebirth`, `rank`; `unequip` calls | Member model owns storage; this system owns the two values |
| CA/PA and traits (9) | both | `ca()`, revealed traits | `reveal_on_rebirth` call; `elder_mod_ppm` added into `trait_mod_ppm` (PROVISIONAL) | 9 owns reveal and the trait-mod sum |
| Skills (21) | out | — | `set_levels` with F7 | Skills applies; this system owns `skill_keep_pct` |
| Schools (20) | out | `change_target_id` (gate 6) | `grant_free_change` call | Schools owns the credit (R6) |
| XP curve (22) | both | `cap[r]`, `Capped` | The new `rebirth` value; `xp_pct`, `growth_bonus` rows | XP owns the cap and the multipliers |
| Items and loot (26) | both | Member's pill count | Pill consumption; `drop_rate` rows | Items owns inventory and the drop bonus |
| Gold economy (27) | out | `can_debit` | `rebirth_cost` burns (type 24) | Gold owns the ledger |
| Guild and buildings (30) | in | `effect(bld_shrine, rebirth_max / phi_thang)`, (the proposed `effect(bld_hq, elder_slots)` key is no longer needed, 2026-11-16) | — | Guild owns the effects |
| Member state machine (41) | both | Home-and-free check | Request to place the member in `elder` | 41 owns states (PROVISIONAL) |
| Event bus (42) | out | — | 2301, 2302 | Bus owns delivery |
| Golden Boss (14), Crafting (28) | — | Pill supply (boss drop, Shrine recipe) | — | They own the pill faucets |
| Endless Tower (19), Zones (11) | out | — | `rebirth` read for `unlock_tower_high`, `rebirth_req` | Each owns its gate |
| Retention (16) | out | — | "Elders never leave" (R10) | 16 (PROVISIONAL) |
| Leaderboards (35), Account and cloud save (7) | out | — | `rebirth`, `rank`, events | Read only |
| Guild screens (39), Push notifications (46) | out | — | `rebirth_status`, events | Read only |

## Formulas

### F1 — `rebirth_cost`

The rebirth_cost formula is defined as:

`gold(n) = rebirth.gold_cost[n]` ; `pills(n) = rebirth.pill_cost[n]` for the row n being completed (n = 1–5 for rebirth, row 6 for Ascension)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n | int | 1 – 6 | calculated (`rebirth + 1`, or 6 for Ascension) | Row being completed |
| gold_cost[n] | int | 0 – `gold_op_max` (today 0, 200k, 1M, 5M, 20M, 50M) | data file (`rebirth.csv`) | Gold burned from the fund |
| pill_cost[n] | int | 0 – 99 (today 1, 2, 3, 4, 5, 0) | data file (`rebirth.csv`) | Pills taken from the member's own inventory |

**Output Range:** gold 0 – 50,000,000 with today's data, and at most `gold_op_max` (10¹²) by the validator. Pills 0 – 5. A cost of 0 skips that step (R4.1).
**Example:** a member at tier 2, capped at 140, rebirths to tier 3: 1,000,000 gold from the fund and 3 pills from their bag.

**Ladder totals (derived, for balance):** one member from tier 0 to Elder pays 15 pills and 76,200,000 gold (26,200,000 for the five rebirths plus 50,000,000 to ascend). A party of five rebirthing together at tier 5 needs 25 pills at once.

### F2 — Elder count (no cap)

**RESOLVED (user decision 2026-11-16):** Elders are **unlimited**. There is no `elder_slots` formula, no `bld_hq` capacity key and no Ascension gate on the Elder count. The former F2 (`elder_slots = effect(bld_hq, elder_slots)`, 5 at HQ 8) is withdrawn and the registry entry `elder_slots_max` is deprecated. The only bound on the Elder buff is the per-key cap in F3; the soft brake on the Elder count is the cost of each Ascension (50M gold, CA ≥ 180) and upkeep (R10).

**Output Range:** Elder count 0 – unbounded in rules. In practice it is bounded by Ascension's cost and CA gate (F5) and by the save's member bound (Member model F6; every Elder is one roster record). Elders are terminal (Member state machine `elder`) and do not tick, so their count affects save size, not tick cost.
**Example:** HQ 8, Shrine 6, 7 Elders → an 8th Ascension is allowed if gates 1–6 and 8 pass.

### F3 — `elder_mod_ppm`

The elder_mod_ppm formula is defined as:

`raw(k) = Σ_e school_buff_ppm[school(e)][k] + Σ_e Σ_{t ∈ revealed(e), cat(t) ∈ C} tz( trait_ppm(t, k) × elder_trait_share_ppm / 1,000,000 )`
`elder_mod_ppm(k) = clamp( raw(k), −elder_buff_cap_ppm, +elder_buff_cap_ppm )`

Here `tz(x)` truncates toward zero: the division runs on |x| and the sign is put back afterwards. GDScript and Python integer division differ for negative numbers, so this rule is stated explicitly for parity.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| e | member | 0 – n Elders (no cap, F2) | calculated (roster) | Each Elder |
| k | effect key | trait effect keys | — | A modifier key (`xp_mult`, `hp_pct`, …) |
| school_buff_ppm[s][k] | int ppm | 0 – 1,000,000 | data file (`elder_buffs.csv`, new) | School s's Elder buff on key k (0 when the row has another key) |
| trait_ppm(t, k) | int ppm | −1,000,000 – 1,000,000 | data file (`traits.csv` effects ×10⁶, CA/PA 9) | Trait t's effect on k |
| C | set | subset of trait categories | data file (`config.csv` `elder_trait_categories`, new: `talent;insight;luck`) | Trait categories an Elder shares |
| elder_trait_share_ppm | int ppm | 0 – 1,000,000 (250,000) | data file (`config.csv`, new) | Share of a revealed trait passed to the guild |
| elder_buff_cap_ppm | int ppm | 0 – 1,000,000 (150,000) | data file (`config.csv`, new) | Per-key cap on the total, in both directions |

**Output Range:** −150,000 to +150,000 ppm per key at defaults (±15%), however many Elders there are: buffs stack additively across all Elders and the total is capped per key (user decision 2026-11-16). It is 0 with no Elders. With 5 Elders of one school on a 40,000 key, the raw total is 200,000, capped to 150,000. The largest intermediate value is 10⁶ × 10⁶ = 10¹², far below 2⁶³.
**Example:** Elders `kim_2` (crit_rate 20,000), `moc_1` (injury_recovery 150,000) and `thuy_2` (xp_mult 30,000). The `kim_2` Elder has revealed `t_lucky` (luck: drop_rate +0.10, rare_drop +0.08). The `moc_1` Elder has revealed `t_greedy` (personality, not shared). Result: crit_rate 20,000; injury_recovery 150,000; xp_mult 30,000; drop_rate tz(100,000 × 0.25) = 25,000; rare_drop 20,000. Every disciple gets +2% crit, +15% injury recovery, +3% XP, +2.5% drop rate and +2% rare drop.

**Boundaries checked.** No Elders → every key 0. Share 0 → school buffs only. Share 1,000,000 → an Elder passes on full traits, so with 5 Elders a single key reaches the cap quickly. Cap 0 → the Elder buff is off. A negative-only trait (`t_dull` skill_xp −0.08) → −20,000, so an Elder can make a key worse, which the player can see before ascending. **Feedback loop:** `xp_mult` and `skill_xp_mult` speed up future Ascensions (a positive loop). It is damped by the cap alone (no slot limit since 2026-11-16) and by Ascension's cost: at most +15% XP, which is inside XP curve's ±20% pacing band.

### F4 — `rebirth_afford_hours` (reference, not a rule)

The rebirth_afford_hours formula is defined as:

`afford_h(n) = gold_cost[n] / fund_income_per_h` ; `fund_income_per_h ≈ guild_tax_pct × income_ref_per_level × Σ level_i`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| gold_cost[n] | int | 0 – 50,000,000 | data file (`rebirth.csv`) | F1 |
| guild_tax_pct | float | 0.1 | data file (`config.csv`, Gold economy 27) | Fund's share of member income |
| income_ref_per_level | int | 1,000 | data file (`config.csv`, Gold economy F4) | Gold per member-level per hour |
| Σ level_i | int | 0 – 8,000 | calculated | Roster level sum |

**Output Range:** reference only. It is used by the balance simulator (Dev tooling 43) to check that gold is a sink, not the binding gate.
**Example:** 20 members averaging level 120 in Wave 2: the fund earns ≈ 240,000/h, so tier 2 (200k) takes 0.8 h and tier 3 (1M) takes 4.2 h. 40 members averaging level 175 in Wave 3: ≈ 700,000/h, so tier 5 (20M) takes 29 h and Ascension (50M) takes 71 h. The XP stretch 180→200 takes about 21 days of AFK time (GDD §4.3), so time and pills bind long before gold does. Rebirth gold is a medium sink at tier 5 and Ascension, about 1–3 days of fund income, and close to nothing before that. This is intended. If the simulator shows gold piling up late, raise `gold_cost` for tiers 4–6 first.

### F5 — `ascension_ca_reachable` (consequence of CA/PA F1)

The ascension_ca_reachable formula is defined as:

`reachable(pa) = ( ca_max_at(pa) ≥ ca_min )` with `ca_max_at(pa) = pa + (ca_max − pa) × ca_over_pa_ppm / 10⁶` (all CA terms at maximum)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| pa | int | 0 – 200 | calculated (CA/PA 9) | Member potential |
| ca_max | int | 200 | data file (`config.csv`) | Top of CA |
| ca_over_pa_ppm | int ppm | 500,000 | data file (`config.csv`, CA/PA 9) | Share of raw CA above PA that counts |
| ca_min | int | 0 – 200 (180) | data file (`rebirth.csv` row 6) | Ascension gate |

**Output Range:** at defaults, reachable only when PA ≥ 160, and then only with every CA term at its maximum (all skills at max, top gear, all trait slots revealed at top tier). At PA 200, raw CA ≥ 180 is enough (90% of every term).
**Example:** PA 170 → ca_max_at = 170 + 30 × 0.5 = 185 ≥ 180, so reachable, but only if raw CA ≥ 190 (95% of the maximum). PA 150 → 175, never reachable. This answers CA/PA OQ-4 by stating the consequence. Whether it is intended is the user's call (OQ-4 here).

### F6 — applier cost and event volume

`c_apply(2301) ≈ c_gates + c_debit + c_consume + c_set_levels(12 slots) + c_reward_calls + c_emit` ; `c_apply(2302) ≈ c_gates + c_ca + c_debit + 4 × c_unequip + c_emit`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| c_* | float µs | > 0 | measured (P1 spike) | Per-step GDScript cost |

**Output Range:** estimated ≤ 150 µs each. That is O(1) per command, with no roster scan except the Elder count, which is ≤ 20. Peak sim-origin requests per tick: 0 (host only). Event volume: ≤ 6 milestone records per member per lifetime and `ring_per_day` 0. `elder_mod_ppm` costs O(Elders × traits ≤ 20 × 3) per evaluation, and an ADR may cache it, invalidated on 2302 and on trait reveal (903) for an Elder.

## Edge Cases

- **If two `rebirth_member` commands for one member arrive in the same tick**: the first, in `seq` order, is applied. The second sees the member `Growing` and is refused 101. The player is never charged twice.
- **If `rebirth_member` and `change_school` for the same member are in one batch**: they apply in `seq` order. Change first: the member is in a change, so the rebirth gets 106. Rebirth first: the free credit is granted in the same applier call (R4.5), so the change after it uses the credit and is free. This is why one-time rewards are synchronous.
- **If the member reached the cap while offline**: they stay `Capped` and the extra XP is discarded (XP R4). There is no automatic rebirth (R12). The return summary lists the members who are ready.
- **If the next tier's wave is not live** (Wave 1, a member at tier 1 capped at 120): refused 103. The member stays capped until the wave ships. The status badge reads "next rebirth: coming in a later update" instead of "ready".
- **If the pills are in guild storage, not on the member**: refused 107. The rebirth screen offers a one-tap batch: `award_item` × pills, then `rebirth_member`, submitted together (Command layer R12). The awards apply first, in seq order.
- **If the fund cannot pay**: refused 108 and nothing is taken. Upkeep arrears do not block a rebirth that the fund can pay.
- **If the member is hunting, raiding, injured, dead, away or training**: refused 105. The player has to recall them first. A rebirth can never interrupt a trip or a raid.
- **If the Shrine level is too low**: refused 104. Shrine capacity keys never decay (Guild and buildings R7), so arrears cannot take away access the guild already has.
- **If a `rebirth.csv` row changes in a content update** (for example `skill_keep_pct` is raised): past rebirths are not recomputed. Cumulative rewards (`xp_pct`, `growth_bonus`, `drop_rate`) are read live, so they follow the new data for every member at that tier.
- **If the member has no hidden trait at a `trait_slot_reveal` tier**: nothing is revealed (CA/PA R11), and the rebirth still completes.
- **If the member already holds a free change credit at a `free_school_change` tier**: the count stays at 1 (Schools R6). The credit does not expire at the next rebirth, which answers Schools OQ-3: keep "persist until used".
- **If the member is unaffiliated** (no school) when rebirthing: allowed. `set_levels` runs on zeros. A level-100 unaffiliated member is a degenerate roster, but it is legal.
- **If the member's CA drops below `ca_min` between `rebirth_status` and `ascend_member`** (gear moved in the same batch): the applier recomputes CA and refuses 110. The status query is advisory, and the applier decides.
- **If the guild already has many Elders** (no slot limit, user decision 2026-11-16): Ascension is still allowed. Once every key a new Elder touches is at `elder_buff_cap_ppm`, that Elder adds no buff but still costs upkeep (R10); the Ascension confirm shows this (UI Requirements). Code 111 is never emitted.
- **If `elder_buff_cap_ppm` is lowered in data below the current total**: the total is re-clamped at the next evaluation (F3 is never saved). No Elder loses rank.
- **If an Elder's school is retired in data** (no longer live): the Elder stays, and their `elder_buffs.csv` row still applies (retired content keeps working, Data layer). A live school with no `elder_buffs.csv` row is a validator ERROR. A missing row at runtime contributes 0.
- **If an Elder's hidden trait is revealed after Ascension** (time-based reveal, CA/PA R11): it starts to count in F3 at the next evaluation.
- **If the roster has zero disciples** (everyone ascended): F3 still evaluates, applies to no one, and the guild goes on (recruitment). Elders do not hunt, so income drops to building output only. This is a player choice, not a lock.
- **If an Elder is targeted by `remove_member`, `dismiss_member`, `change_school`, `order_member` or a party assignment**: refused by the owning system (R10, PROVISIONAL). Rebirth asserts in its ACs that it never calls `remove_member`.
- **Degenerate strategy, "never rebirth to keep fast XP"**: not possible. A capped member earns nothing (XP R4), so delaying a rebirth only wastes XP.
- **Degenerate strategy, "stack many Elders of one school"** (unlimited Elders): bounded by `elder_buff_cap_ppm` (F3). On a 40,000 key the fourth Elder already reaches +15% (160,000 capped) and every further one adds nothing but upkeep, so mixing schools is the better choice.
- **Degenerate strategy, "ascend for the gear"**: Ascension sends the Elder's gear to storage. That is a benefit, not an exploit: the gear already existed, and nothing is created.

## Dependencies

### Upstream (this system depends on)

| System | Hard/Soft | Interface | What it provides |
|---|---|---|---|
| Data layer and content pipeline (3) | Hard | `rebirth`, `elder_buffs` (new) tables; liveness; validator hooks (R2) | The ladder |
| Command layer (5) | Hard | `register_command` 2301, 2302; reason codes | The only input path |
| Member model (8) | Hard | `rebirth`, `rank` storage; `unequip`; Elders outside `member_cap`, no Elder cap (its OQ-5) | Storage |
| CA/PA and traits (9) | Hard | `ca()`; revealed traits; `reveal_on_rebirth` (PROVISIONAL); adds `elder_mod_ppm` in `trait_mod_ppm` (PROVISIONAL) | Ascension gate; trait reward; buff delivery |
| Skills (21) | Hard | `set_levels`, F7 | Skill cost of a rebirth |
| XP and level pacing curve (22) | Hard | `cap[r]`, `Capped` | When a member may rebirth |
| Gold economy (27) | Hard | `can_debit`, `debit(24, fund, …)` | Gold cost |
| Items and loot tables (26) | Hard | Member inventory count and consume (PROVISIONAL call name) | Pill cost |
| Guild and buildings (30) | Hard | `effect(bld_shrine, rebirth_max / phi_thang)`; `elder_slots` key no longer needed (2026-11-16) | Gates |
| Schools and school change (20) | Soft | `change_target_id`; `grant_free_change` (PROVISIONAL) | Free change reward |
| Member state machine (41) | Hard (PROVISIONAL, no GDD) | Home-and-free check; `elder` terminal state | State gate |
| Event bus and history log (42) | Hard | Block 2300; 2301, 2302 milestones | History |
| Sim core and tick loop (1) | Hard | P1 appliers; `ctx.fail` | Execution |

### Downstream (systems that depend on this one)

| System | Hard/Soft | Interface | What it needs |
|---|---|---|---|
| XP curve (22) | Hard | `rebirth` value; `xp_pct`, `growth_bonus` rows | Cap and bonus tier |
| Skills (21) | Hard | `rebirth` (secret `rebirth_req`); F7 call | Learnability, retention |
| Items and loot (26) | Soft | `drop_rate` rows | Rebirth drop bonus |
| CA/PA and traits (9) | Hard | Rebirth tier (CA level term uses `cap[rebirth]`); one-time reveal call; `elder_mod_ppm` | CA, trait reveal |
| Schools (20) | Soft | `grant_free_change`; Elders refused | Free change |
| Zones and hunt (11), Endless Tower (19) | Soft | `rebirth` vs `rebirth_req` / `unlock_tower_high` | Content gates |
| Gold economy (27) | Hard | `rebirth_cost` debits; Elders on the roster for upkeep | Ledger |
| Member model (8) | Hard | `rank` changes taking a member out of `member_cap` (no Elder cap) | Capacity |
| Retention (16), Party (13), Golden Boss (14), Utility AI (12) | Soft | `rank = elder` excludes the member | Exclusion |
| Leaderboards (35), Account and cloud save (7), Analytics (37) | Soft | `rebirth`, `rank`, 2301/2302 | Display, verification |
| Guild screens (39), Push notifications (46), Audio (40) | Soft | `rebirth_status`, events | Presentation |

Bidirectional check: XP curve, Skills, CA/PA, Schools, Gold economy, Items, Guild and buildings, Member model and Data layer already list Rebirth (23). Guild and buildings lists `bld_shrine`; the `elder_slots` key it was asked to add is no longer needed (OQ-2, consistency follow-up for Guild and buildings).

## Tuning Knobs

| Knob | Source | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `skill_keep_pct[n]` | `rebirth.csv` | 50, 55, 60, 65, 70; 100 | 31 – 100, strictly increasing, and above `school_change_skill_keep_pct` (30) | Rebirth costs nothing in skills | Rebirth feels like a punishment; skill CA term collapses | Skills F7; CA skill term |
| `pill_cost[n]` | `rebirth.csv` | 1 – 5; 0 | 0 – 20 | Pills become the wall, and Golden Boss luck decides progress | No reason to farm bosses or craft | Golden Boss drop rate, Shrine recipe (28) |
| `gold_cost[n]` | `rebirth.csv` | 0, 200k, 1M, 5M, 20M; 50M | 0 – `gold_op_max` | Gold becomes the wall (F4) | No late gold sink | Gold economy out/in ratio (F7 there) |
| reward values (`xp_pct`, `growth_bonus`, `drop_rate`) | `rebirth.csv` | see R3 | 0 – 0.5 each | Undoes the §4.3 slowdown | Rebirth reward not felt | XP F2 (owned there); Items F3 |
| `ca_min` | `rebirth.csv` row 6 | 180 | 120 – 200 | No one can ascend (F5) | Every member ascends | CA/PA `ca_over_pa_ppm` (F5) |
| `school_buff_ppm` per school | `elder_buffs.csv` (new) | kim_1 hp_pct 40,000; kim_2 crit_rate 20,000; moc_1 injury_recovery 150,000; moc_2 potion_effect 80,000; thuy_1 skill_xp_mult 50,000; thuy_2 xp_mult 30,000; hoa_1 atk_speed 30,000; hoa_2 gold_mult 30,000; tho_1 def_pct 40,000; tho_2 drop_rate 40,000 | 0 – `elder_buff_cap_ppm` | Elders beat the roster's own traits; pacing breaks | The graduation is not felt | `elder_buff_cap_ppm` |
| `elder_trait_share_ppm` | `config.csv` (new) | 250,000 | 0 – 500,000 | Trait luck of a single Elder dominates | Traits irrelevant to Ascension choice | `elder_trait_categories`, cap |
| `elder_trait_categories` | `config.csv` (new) | `talent;insight;luck` | any subset of trait categories | Personality effects (salary demand) spread guild-wide | Only school buffs | — |
| `elder_buff_cap_ppm` | `config.csv` (new) | 150,000 | 50,000 – 300,000 | Late guild out-scales the pacing bands | Several Elders become pointless | All buff values |
| ~~`elder_slots`~~ | — | **Removed (user decision 2026-11-16):** Elders are unlimited; `elder_buff_cap_ppm` is the only bound | — | — | — | — |
| `rebirth_max`, `phi_thang` | `buildings.csv` `bld_shrine` | 1 – 5; 1 at level 6 | owned by Guild and buildings (30) | — | — | Pointed to, not duplicated |
| `xp_rebirth_mult_n`, caps | `config.csv`, `rebirth.csv` | owned by XP curve (22) | — | — | — | Pointed to |

*Rationale for the school buffs:* each is about a third of one rare trait's single effect (for example `t_iron_body` hp +0.12 → Elder +0.04), but it applies to every disciple, permanently. Keys are trait effect keys, so they reach every consumer through the existing `trait_mod_ppm` path (R8). Each school's key echoes its role (tank → HP or defence, healer → injury recovery, support → XP, ranged → gold).

## Visual/Audio Requirements

Category `Progression`: this section is optional, but it is authored because rebirth and Ascension are the game's biggest member moments. No art bible exists, so this is drafted from JX1 GDD §12.4 (pixel 2D, AI tools plus hand touch-up).
- **Rebirth (2301):** at the Shrine sprite, a short column of light (≤ 1.5 s, pixel particles in the member's element colour) and a brief ring around the portrait. Skill bars shrink visibly to their kept level before the screen settles. The cost must be seen, not hidden.
- **Ascension (2302):** a longer moment (≤ 4 s, skippable). The member walks to the Elders' hall, and the gear icons fly into the storage chest. The portrait takes a gold frame in the Elders' panel. One-off event; no per-frame cost.
- **Audio (40):** rebirth is a bell strike plus a rising pad. Ascension gets a short unique sting, the highest-priority non-warning cue. Both are mixed below raid warnings.
- **Elder buff:** no world VFX. The buff is shown only in UI (an icon on affected stats), so 40 disciples do not each carry an aura.

> 📌 **Asset Spec**: Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:rebirth-and-ascension` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

Optional for `Progression`. Targets: the rebirth confirm opens in one tap from the member card's "ready" badge. Costs, the kept skill levels (before → after) and the rewards are shown on one screen before the confirm. The result is shown within the same frame the command is acknowledged (P1 → P6 of one tick, ≤ 100 ms). Ascension needs a second confirm, because it cannot be undone and takes the member off hunting for good.

## UI Requirements

- **Member card:** tier pips (0–5) or a gold Elder frame. The `rebirth_status` badge reads "Ready to rebirth", "Ready to ascend", or the blocking reason in words (R9 localisation keys) with its icon, never by colour alone.
- **Shrine (Linh Miếu) screen:** the list of capped members with their status; per member: gold (fund balance shown), pills (on the member / in storage, with the one-tap award-and-rebirth batch), skill levels before → after (F7), the rewards of the next row, and the new cap. The confirm button is disabled, with its reason, when blocked.
- **Ascension confirm:** CA vs `ca_min`, current Elder count (no limit), the predicted F3 buff, with each key that is already at the cap marked "no further gain" (school buff plus shared revealed traits, showing the cap when it applies), and a warning that gear goes to storage and the member stops hunting. Second confirm.
- **Elders' hall panel:** one portrait per Elder with their buff lines. Guild total per key (F3) with the cap shown.
- **Return-from-offline summary:** "N members are ready to rebirth".
- **Localisation room:** the reason strings and reward names come from `i18n/` (Localization 4), sized for Vietnamese.

> **📌 UX Flag — Rebirth and Ascension**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for the Shrine screen, the Ascension confirm and the Elders' hall **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD uses | Source GDD | Section | Nature |
|---|---|---|---|
| `cap[r]`, `Capped`, level kept on rebirth, overflow discarded, `xp_pct`/`growth_bonus` readers | `xp-and-level-pacing-curve.md` | R1, R3, R4, R5, R7, States | Interface; this GDD writes `rebirth` only |
| `set_levels`, F7 `rebirth_kept_level`, 100% for ascension | `skills.md` | R8, F7 | Rule dependency |
| `rebirth`, `rank` fields; Elders outside `member_cap`; never removed by Rebirth | `member-model.md` | Fields, R9, States, OQ-5 | Storage interface |
| `ca()`, F1 consequence PA ≥ 160; trait reveal on rebirth (domain 18); `trait_mod_ppm` | `ca-pa-and-traits.md` | R3, R9, R11, F1, OQ-4 | Gate and delivery path |
| Free change credit R6; refuse while `Changing`; OQ-3, OQ-6 answered | `schools-and-school-change.md` | R4, R6, Edge Cases | One-time reward |
| Entry type 24 `rebirth_cost`; `can_debit`, `debit`; upkeep F3 counts roster (OQ-13 answered) | `gold-economy.md` | Entry table, R4, R9, F3 | Ledger |
| `item_rebirth_pill` member-held; `award_item`; `drop_rate` reward | `items-and-loot-tables.md` | R8, R9 | Pill path |
| `effect(bld_shrine, rebirth_max / phi_thang)`; capacity keys never decay | `guild-and-buildings.md` | R7 (`effect()` and the never-decay list) | Gate |
| Command ID block = owner × 100; reason codes 100–999; 502 refusals; R12 batches | `command-layer.md` | R2, R6, R7, R12 | Input path |
| Block 2300; milestone rules R3a; `milestone_cap_per_subject` | `event-bus-and-history-log.md` | R3, R3a | Events |
| P1 appliers, `ctx.fail` | `sim-core-and-tick-loop.md` | R2, R10 | Execution |

## Acceptance Criteria

*(qa-lead lens applied: at least one criterion per core rule and per formula, boundaries tested, and cross-system checks included. [Logic] = automated unit test in `tests/unit/rebirth/`; [Integration] = real Sim core, Command layer and Event bus; [UI] = retained screenshot in `production/qa/evidence/`.)*

- **AC-1 [Logic] (R4, happy path)**: **GIVEN** a disciple at tier 0, level 100, at home, holding 1 pill, Shrine level 1, fund 0 gold, **WHEN** `rebirth_member` is applied, **THEN** `rebirth` = 1, level is still 100, `xp_milli` is 0, the member is `Growing` under cap 120, the pill count is 0, no gold ledger entry is written (cost 0), and a 2301 event is emitted with `b` = 1, `c` = 0, `d` = 1.
- **AC-2 [Logic] (R4 step 4, F7)**: **GIVEN** a tier-1 member capped at 120 with skill levels [20, 15, 9, 1, …], **WHEN** they rebirth to tier 2 (`skill_keep_pct` 55), **THEN** the levels are [11, 8, 4, 0, …] and all skill progress is 0.
- **AC-3 [Logic] (R4 gates, order)**: **GIVEN** one fixture per gate where only that gate fails, **WHEN** `rebirth_member` is applied, **THEN** it is refused with 101, 102, 103, 104, 105, 106, 107 or 108 respectively, and member, inventory, fund and skills are byte-identical to before. **AND GIVEN** a member failing gates 3 and 8 at once, **THEN** the reason is 101 (first in order).
- **AC-4 [Logic] (R4 step 1, F1)**: **GIVEN** a capped tier-2 member with 3 pills and a fund of 1,000,000, **WHEN** they rebirth, **THEN** the fund is 0, a type-24 burn of 1,000,000 with `ref_uid` = member_id is recorded, and the 2301 event has `c` = 1,000,000 and `d` = 3. **AND GIVEN** a fund of 999,999, **THEN** the command is refused 108.
- **AC-5 [Integration] (R4 step 5, edge "same batch")**: **GIVEN** a capped tier-0 member, **WHEN** a batch [`rebirth_member`, `change_school`] is submitted in one tick, **THEN** the school change is accepted as free (credit consumed, no gold or items taken) in the same tick.
- **AC-6 [Integration] (R3 `trait_slot_reveal`)**: **GIVEN** a member with 2 hidden traits, **WHEN** they complete rebirth 1, **THEN** exactly one trait is revealed (CA/PA event 903), chosen by RNG domain 18 key [member_id, 1], and the same seed gives the same trait on replay.
- **AC-7 [Logic] (R3 cumulative, XP)**: **GIVEN** a member at tier 4, **WHEN** XP curve computes their bonus, **THEN** it uses `xp_pct` 0.10 + 0.10 and `growth_bonus` 0.05 summed over rows 1–4. The member record holds no copied bonus field.
- **AC-8 [Logic] (edge, double command)**: **GIVEN** two `rebirth_member` commands for one capped member in one tick, **THEN** exactly one is applied and the second is refused 101. Pills and gold are taken once.
- **AC-9 [Logic] (R6, happy path)**: **GIVEN** a tier-5 disciple at level 200 with CA 185, Shrine level 6, HQ 8 with 0 Elders, a fund of 50,000,000 and 4 equipped items, **WHEN** `ascend_member` is applied, **THEN** `rank` = `elder`, all 4 items are in guild storage, the fund is 0, 2302 is emitted with `d` = 1, and the member no longer counts against `member_cap`.
- **AC-10 [Logic] (R6 gates)**: **GIVEN** one fixture per failing gate, **THEN** `ascend_member` is refused with 109 (tier 4), 104 (Shrine 5), 110 (CA 179), 111 (5 of 5 Elders) or 112 (already Elder), and nothing changes. CA exactly 180 is accepted.
- **AC-11 [Logic] (F3)**: **GIVEN** the F3 example roster (`kim_2` + `t_lucky`, `moc_1` + `t_greedy`, `thuy_2`), **WHEN** `elder_mod_ppm` is evaluated, **THEN** it returns crit_rate 20,000, injury_recovery 150,000, xp_mult 30,000, drop_rate 25,000, rare_drop 20,000, and 0 for salary_demand.
- **AC-12 [Logic] (F3 boundaries)**: **GIVEN** 5 `tho_1` Elders (def_pct 40,000 each), **THEN** `elder_mod_ppm(def_pct)` = 150,000. **GIVEN** no Elders, **THEN** every key is 0. **GIVEN** one Elder with revealed `t_dull` (skill_xp_mult −0.08) and share 250,000, **THEN** skill_xp_mult contribution = −20,000; and an Elder with share giving −12,345.6 truncates to −12,345 in both Python and GDScript.
- **AC-13 [Integration] (R8 delivery)**: **GIVEN** one `thuy_2` Elder, **WHEN** CA/PA `trait_mod_ppm(d, xp_mult)` is read for a disciple d with no traits, **THEN** it returns 30,000. For the Elder themself it returns their own traits only.
- **AC-14 [Logic] (F2, no cap)**: **GIVEN** a guild at HQ 8 and Shrine 6 with 6 Elders and a member passing gates 1–6 and 8, **WHEN** `ascend_member` runs, **THEN** it is accepted (7 Elders) and no refusal 111 is ever produced. **GIVEN** 6 `tho_1` Elders (def_pct 40,000 each), **THEN** `elder_mod_ppm(def_pct)` = 150,000 (capped), not 240,000.
- **AC-15 [Logic] (R10)**: **GIVEN** an Elder, **WHEN** `change_school`, `dismiss_member` or a party assignment targets them, **THEN** each is refused by its owner `[PENDING: Schools 20, Retention 16, Party 13]`. Across the whole rebirth test suite, `remove_member` is never called.
- **AC-16 [Logic] (R11)**: **GIVEN** every AC-3 and AC-10 fixture, **WHEN** `rebirth_status` is queried, **THEN** it returns `blocked(code)` with the same code the applier refuses with, and `ready_rebirth`/`ready_ascend` exactly when the applier accepts.
- **AC-17 [Integration] (R12, offline)**: **GIVEN** a member at level 99 tier 0 and an 8-hour offline gap that would carry them past 100, **WHEN** offline progress resolves, **THEN** they end at level 100 `Capped` with `rebirth` still 0, and no 2301 event exists.
- **AC-18 [Logic] (R2 validator)**: **GIVEN** a `rebirth.csv` with an unknown reward key, or `trait_slot_reveal=2`, or `unlock_secret=1` on a row whose slot-11 skills have another `rebirth_req`, **THEN** `content_validator` reports an ERROR naming the row.
- **AC-19 [Integration] (R7, history)**: **GIVEN** a member taken from tier 0 to Elder, **THEN** the history log holds 5 × 2301 and 1 × 2302 milestones with subject = that member, and none is evicted by ring traffic.
- **AC-20 [Logic] (determinism)**: **GIVEN** a fixed seed and a scripted ladder (S6 parity: lv1 → 200 → Elder), **WHEN** run in Python and in GDScript, **THEN** member records, the fund and the `elder_mod_ppm` table are identical, and stage durations match GDD §4.3 within ±20% (Dev tooling 43).
- **AC-21 [UI]**: **GIVEN** a capped member, **THEN** the Shrine screen shows costs, before → after skill levels, rewards and the confirm. A blocked member shows the reason in words and an icon. A retained screenshot exists for the Shrine screen, the Ascension confirm and the Elders' hall.

## Open Questions

| ID | Question | Owner | Resolve by |
|---|---|---|---|
| OQ-1 | **RESOLVED (user decision 2026-11-16):** Elders are unlimited. No slot cap, no retirement mechanic: Elder buffs stack additively across all Elders and the per-key total stays capped at ±15% (`elder_buff_cap_ppm`). F2, R6 gate 7, code 111, Edge Cases and AC-14 updated; registry `elder_slots_max` deprecated. | User + game-designer | Closed |
| OQ-2 | **RESOLVED (user decision 2026-11-16, consistency follow-up):** Guild and buildings (30) no longer needs the `elder_slots` capacity key on `bld_hq` or on its never-decay list; Elders are unlimited (OQ-1). Guild and buildings should drop any reference to it at its next revision. | Guild and buildings (30) | Follow-up at next 30 revision |
| OQ-3 | GDD §6.10 prices Ascension at "vật phẩm đặc biệt" (a special item). `rebirth.csv` has 50M gold and 0 pills, and no such item exists. Keep the data, or add an item (a new `items.csv` row)? | User | Wave 3 content |
| OQ-4 | Ascension (CA ≥ 180) needs PA ≥ 160 and every CA term near its maximum (F5). Is graduation meant to be this rare? If not, lower `ca_min` (e.g. 150 → PA ≥ 100) or change `ca_over_pa_ppm` (CA/PA 9). Joint with CA/PA OQ-4. | User + CA/PA (9) | Before Wave 3 balance pass |
| OQ-5 | **PROVISIONAL: CA/PA and traits (9)** — `reveal_on_rebirth(member_id, rebirth_no)` as a synchronous call (not an event subscription), and `trait_mod_ppm` adding `elder_mod_ppm(k)` for disciples. | CA/PA (9) | Next 9 revision |
| OQ-6 | **Partly RESOLVED (consistency-check 2026-11-16):** Schools R4 condition 3 now excludes `elder` (refused 7 `not_allowed_now`, no new code needed). Still open: Schools R6 grants the credit from a completed-rebirth signal rather than a `grant_free_change` call — the two must agree on one interface at the next Schools/Rebirth revision. | Schools (20) | Next 20 revision |
| OQ-7 | **PROVISIONAL: Items and loot (26)** — `consume_member_item(member_id, item_id, qty)` on the member inventory; count query for gate 8. | Items (26) | Next 26 revision |
| OQ-8 | **PROVISIONAL: Member state machine (41)** — home-and-free predicate covering `hunting`, `boss_raid`, `away`, `dead`, `injured`, `training`; a terminal `elder` state that Utility AI, Party, Golden Boss and Hunt never select. | Member state machine (41) | When 41 is designed |
| OQ-9 | **RESOLVED (consistency-check 2026-11-16):** Retention R1 (`Exempt` state) excludes Elders from leaving, mood and contracts, and `dismiss_member` refuses them (code 104 `elder`). | Retention (16) | Closed |
| OQ-10 | **PROVISIONAL: Endless Tower (19)** — reads `unlock_tower_high` as from-tier (`rebirth ≥ 2`). | Endless Tower (19) | When 19 is designed |
| OQ-11 | **RESOLVED (consistency-check 2026-11-16):** Gold economy F3 counts every roster member and its OQ-13 now records Elders as counted. | Gold economy (27) | Closed |
| OQ-12 | Do Elders appear on the member leaderboard (35), and does a guild's Elder count feed guild ranking? | Leaderboards (35) | When 35 is designed |
| OQ-13 | New data file `data/elder_buffs.csv` and four `config.csv` keys (`elder_trait_share_ppm`, `elder_trait_categories`, `elder_buff_cap_ppm`; the HQ key formerly in OQ-2 is withdrawn) need Data layer table registration and validator rules (every live school has one row; keys are known trait effect keys). | Data layer (3) | Before S6 implementation |
| OQ-14 | Pill supply versus demand (15 per member over the ladder; 25 at once for a tier-5 party) has not been simulated: Golden Boss drop 2–6% per raid, plus the Shrine recipe (50k gold, 15 mats, 1 h). Run the balance simulator after S6. | Dev tooling (43) + Crafting (28) | S6 |
