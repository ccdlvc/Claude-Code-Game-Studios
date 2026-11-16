# Member Model

> **Status**: Designed
> **Author**: user + Claude (design-system, autonomous batch run)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no game pillars written yet)
> **Reference implementation**: `sim/model.py` (`Member`, `new_member`, `auto_gear`). This GDD specifies the built behaviour, records where the port must differ, and moves code that belongs to other systems to its owner.
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief exist to check against; re-run once pillars are written

## Summary

The Member model is the record of one guild member: who they are (a permanent ID and a name), what they wear (four equipment slots), and the storage for every other fact about them that other systems own, such as level, school, PA, gold and HP. It also derives the member's combat profile (attack, damage per second, maximum HP, defence) from level, school role and gear, so every system reads the same numbers. It exists because almost every gameplay system reads or writes a member, and one thin, well-policed record is what keeps those systems from fighting over the same fields.

> **Quick reference** — Layer: `Core` · Priority: `MVP` · Key deps: `Data layer and content pipeline, Sim core and tick loop, Event bus and history log, Schools and school change, XP and level pacing curve, Items and loot tables, Guild and buildings, Equipment enhancement`

## Overview

A guild member in JX1 Tycoon is a person the player recruited, named and watches grow: a disciple with a school, a level, gear and a hidden potential. The Member model is the data layer under that person. It owns the member record and three rules that no other system may break: every member has a **permanent ID** that is never given to anyone else, even after they leave; every field of the record has **exactly one writer**, so Schools alone sets a school, the XP curve alone sets a level, Gold economy alone moves gold; and the member's **combat profile** is always derived from the record, never stored, so it cannot drift from the gear the member is wearing. The player meets this system directly in two places, the member's name and the four gear slots, and indirectly everywhere else: every number on the member panel and every hit in a fight is read from this record. Without it, each of the thirty systems that touch a member would keep its own partial copy, and the first school change or gear swap would leave them disagreeing. The model is deliberately thin. It does not decide what a member does (Utility AI, Member state machine), how they grow (XP curve, Skills, Rebirth) or what they are worth (CA/PA and traits). It stores, validates and derives.

## Player Fantasy

**"I know every one of them."** The player opens a member and reads a person, not a unit: a name they kept or chose, the school they joined at level 10, the sword they were handed after the last Golden Boss, and an attack number that rose the moment that sword went on. When the same disciple leaves the guild and the Jianghu Chronicle still names them a year later, or returns under the same name with the same ID, the guild has a memory.

- **Anchor moment.** The bang chủ awards a rare drop to a member (Items and loot, "designated award"). The gear slot fills, the attack and HP numbers change on the same tick, and the member walks out to hunt visibly stronger. The player made that happen.
- **Anchor text.** GDD §1: members "mạnh hơn" (grow stronger) through the guild loop; §6.11: "Cố nhân trở lại" (old friends return).
- **What it asks of the design.** Gear must change the profile immediately and legibly (Game Feel). A member's identity must survive renames, leaving and returning (R2, R3). A member must never silently lose gear (R6: gear moves to guild storage, never vanishes).

*Pillar anchor:* none. The project has no game pillars, so this framing is anchored to GDD §1 and §6.11. Two alternative framings were considered and not chosen: "the roster as a machine" (optimisation fantasy, which suits the Utility AI and Party GDDs better) and "the guild as a family tree" (lineage fantasy, which belongs to Rebirth and Ascension).

## Detailed Design

### Core Rules

**R1: The member record.** A member is one record. Its fields, and the one system allowed to write each, are:

| Field | Type | Written by | When |
|-------|------|------------|------|
| `member_id` | int, 1 – 2³¹−1 | Member model | Once, at creation (R2) |
| `name` | string, 1–`member_name_max_len` code points | Member model | Creation, and the `rename_member` command (R4) |
| `rank` | `disciple` \| `elder` | Rebirth and Ascension (23) | Ascension turns a disciple into an Elder |
| `origin` | `walk_in` \| `recruited` \| `returned` \| `poached` | Recruitment (15), Jianghu (17) | Once, at creation |
| `joined_tick` | int | Member model | At creation (each time the member joins) |
| `pa` | int, 0–`pa_max` | CA/PA and traits (9) | Once, at creation; never changes (GDD §5.1) |
| `traits[]` | trait IDs, ≤ `max_traits` | CA/PA and traits (9) | Creation and reveal |
| `school_id`, `aspiring_school_id`, `change_target_id`, `change_due_tick`, `free_change_credits`, `last_paid_change_tick` | see Schools R2 | Schools and school change (20) | Schools R3–R6 |
| `level`, `xp_milli` | int | XP and level pacing curve (22) | XP R4, R9 |
| `rebirth` | int, 0–5 | Rebirth and Ascension (23) | Rebirth |
| `skills[]` | `{skill_id, lv, xp}` | Skills (21) | Learning and training |
| `equipment` | four slots (R5) | Member model, through R6 only | `equip` / `unequip` |
| `hp_milli` | int ≥ 0 | Combat (10); Member model only for F5 rescaling and creation | Damage, healing, rescale |
| `gold` | int | Gold economy (27) | Every member-wallet credit and debit |
| `inventory[]` | item stacks (the carry bag) | Items and loot (26) | Pickup, sale, use |
| `state`, `ground_id`, `satiety`, `stamina` | see 41 | Member state machine (41) | State transitions |
| `loyalty`, `mood`, `contract{salary, demands[]}` | see 16 | Retention (16) | Retention rules |

- **Storage is ours, values are theirs.** The Member model stores every field. It writes only `member_id`, `name`, `joined_tick`, `equipment`, and `hp_milli` at creation and under F5. Every other field is written only through the owning system's own calls, the same pattern as Schools R2 and XP curve R1. A write to a field from any other system is a defect, and AC-2 tests for it.
- **Field values from content are stable IDs** (Data layer R3): `school_id`, item IDs, skill IDs and trait IDs. 0 / `content_id_none` means none.
- **Not in the record.** The combat profile (R7) and CA (owned by CA/PA and traits, 9) are derived and never saved. Per-member history is a query over the Event bus history log, not a field. The reference code's lifetime counters (`kills`, `deaths`, `xp_total`, `gold_total`) are balance-simulator instrumentation owned by Dev tooling (43), derived from events; they are not simulation state.
- **Primary attributes are not specified.** GDD §4.1 lists `stats{str,agi,vit,int,luck}`; the reference implementation has no such fields and derives the profile from level, role and gear. This GDD specifies the built behaviour and leaves the scope question open (OQ-1).

**R2: Member IDs are permanent.** The guild keeps one counter, `next_member_id`, starting at 1 and saved with the guild.
- `create_member` issues `next_member_id` and increments it. IDs are never reused within a save, never given to a different person, and never freed. 0 means "no member".
- A **returning member** (GDD §6.11, origin `returned`) is the same person and keeps their original ID. Jianghu (17) hands the original ID back to `create_member`; it is accepted only if that ID was issued by this save and is not on the roster now.
- Reaching 2³¹−1 refuses creation with `MM_ID_EXHAUSTED`. This is unreachable in play (F6) and exists so the port has a defined result.

**R3: The name record.** Every issued ID has an entry in `name_record[member_id]`, holding the member's current name. It is written at creation and on every rename, and **is kept after the member leaves the roster**. The Event bus and Jianghu Chronicle resolve a departed member's ID to a name through it (Event bus OQ-4). It is never pruned. Its size is bounded by F6.

**R4: Names.** A name is 1 to `member_name_max_len` Unicode code points after trimming leading and trailing whitespace, containing no control characters. Names are player-facing text but **not localised**: they are proper nouns, generated by Recruitment (15) from the `i18n` name lists (GDD §16.5) and stored as text. The player renames a member with `rename_member(member_id, name)`, applied in P1. An invalid name is refused with `MM_NAME_INVALID` and the old name kept. Two members may share a name; the ID is the identity.

**R5: Equipment slots.** A member has four slots: `weapon`, `armor`, `ring`, `amulet`. Each slot is empty or holds one equipped item `{item_id, enhance_lv}`, where `enhance_lv` is an integer 0–20 written only by Equipment enhancement (24). An item row maps to a slot by its `slot` and `family` columns in `items.csv`: `slot = weapon` → `weapon`; `slot = armor` → `armor`; `slot = accessory` with `family = ring` → `ring`; with `family = amulet` → `amulet`. Consumables (`potion`, `food`, `drink`, `special`) are never equipped; they live in `inventory[]` (Items and loot, 26).

**R6: Equip and unequip.** The only way equipment changes. Both are requests from another system or a player command, applied in P1:
- `equip(member_id, slot, item)` takes an item that the caller has already removed from guild storage or the member's bag (Items and loot, 26) and puts it in the slot. It is **refused**, with the item returned to its source and a reason code, unless all of these hold:
  1. The member exists and is on the roster (`MM_MEMBER_UNKNOWN`).
  2. The item is an equip row whose slot (R5) is `slot` (`MM_SLOT_INVALID`).
  3. `level_req ≤ level` (`MM_LEVEL_TOO_LOW`).
  4. Weapon: `school_req` equals the member's `school_id`. An unaffiliated member may hold no weapon (Schools R3) (`MM_SCHOOL_MISMATCH`).
  5. Armour: `armor_class` equals the member's school's `armor_class`; an unaffiliated member may wear any class (Schools R3) (`MM_ARMOR_CLASS_MISMATCH`).
  6. The member is not in `hunting`, `boss_raid`, `away`, `dead` or `training` (Member state machine 41; provisional) (`MM_STATE_BLOCKED`).
- If the slot was occupied, the old item goes to **guild storage** (Items and loot, 26) in the same step. An item is never destroyed by this system.
- `unequip(member_id, slot)` moves the item to guild storage, under rule 6 above.
- Schools R5 and R3 move wrong-school gear to storage on a school change or join; they do so through `unequip`, bypassing rule 6 only (the member is in `training`, which is exactly when the change completes).
- After either call the profile is re-derived (R7) and HP rescaled (F5).
- **Who decides what to wear is not this system.** The reference `auto_gear` (buy the best common item the member can wear and afford) is a policy: it moves to Utility AI (12), whose `choose_gear` only **returns** an ordered purchase list (Utility AI R1, R10); the Member state machine (41) executes it at trip close through Gold economy `shop_sale` and this system's `equip` (MSM R7 step 0). *(consistency-check 2026-11-16: Utility AI is pure and submits nothing.)*

**R7: The combat profile is derived.** `profile(member)` returns four integers: `atk_milli`, `dps_milli`, `hp_max_milli`, `def_milli` (F1–F4). It is a pure function of the member's `level`, `school_id` (through the school's `role`), equipment and the boot tables. It is cached per member and recomputed when its signature `(level, school_id, equipment)` changes. The reference cache key omits `school_id`, which would serve stale role multipliers after a school change; the port must include it (AC-9). Combat (10), Zones and hunt (11), Golden Boss (14), Party (13) and the UI read the profile through this call and never recompute it.
- Equipment stats other than `atk`, `hp`, `def`, `atk_pct`, `hp_pct`, `def_pct` (today only `crit_rate`) are summed and exposed by `gear_stat(member, key)` for Combat to read; the profile does not use them (OQ-4).
- An unaffiliated member has no role and uses neutral multipliers of 1.0 for dps, hp and def (OQ-3).

**R8: Creation.** `create_member(spec)` is called by Recruitment (15), by Jianghu (17) for a returning member, and by the dev tools. `spec` carries `name`, `origin`, `pa`, `traits[]`, `aspiring_school_id` or `school_id`, `level`, `rebirth` and, for a return, the original ID. In order:
1. Refuse with `MM_ROSTER_FULL` if the roster already holds `member_cap` disciples (Guild and buildings 30, from `bld_hq` effects; 12 at headquarters level 1, 40 at level 8). Elders are not counted against `member_cap` and have no cap of their own (unlimited, user decision 2026-11-16; OQ-5).
2. Issue or re-accept the ID (R2), write the name record (R3).
3. Ask each field owner to initialise its fields: XP curve `init_progress(member_id, level, rebirth)` (XP R9), Schools for the school fields, CA/PA for `pa` and `traits`, Gold economy for `gold` = 0, Member state machine for `state = idle`, Retention for `loyalty`/`mood`. If any owner refuses, the whole creation is refused, the ID is not consumed and nothing is emitted.
4. Equipment starts empty. `hp_milli` is set to the derived `hp_max_milli` (the reference `hp = -1` "fill on first read" sentinel is replaced by this explicit step).
5. Emit `member_joined` (R10).

**R9: Removal.** `remove_member(member_id, reason)` takes the member off the roster. It is called by Retention (16) when a member leaves (every departure cause, including dismissal), and by Rebirth (23) never (an Elder stays on the roster). Jianghu (17) never removes an on-roster member: NPC guilds only sign free agents (Jianghu R1, GDD §6.11; user decision 2026-11-16, Jianghu OQ-2 resolved). Origin `poached` means a member the *player* signed back from an NPC guild (Jianghu R8), never one taken from this roster. The member must be in `away` (Member state machine 41); otherwise `MM_STATE_BLOCKED`. Their equipment and bag go to guild storage. Their member-wallet gold leaves with them (Gold economy 27 records the debit). The record is handed, as a snapshot, to Jianghu free agents (17); in MVP, where Jianghu is not built, the snapshot is discarded. The name record stays (R3). Emit `member_removed` (R10).

**R10: Events.** This system registers the type block 800–899 (`member_event_type_block`) with the Event bus.

| ID | Name | a | b | c | d | Logged | Milestone |
|----|------|---|---|---|---|--------|-----------|
| 801 | `member_joined` | member_id | origin code | school uid or 0 | level | yes | yes, `subject_slot` 1 |
| 802 | `member_removed` | member_id | reason code | level | rebirth | yes | no |
| 803 | `member_renamed` | member_id | — | — | — | yes | no |
| 804 | `member_equipped` | member_id | slot code (1–4) | item uid | enhance_lv | no | no |
| 805 | `member_unequipped` | member_id | slot code | item uid | enhance_lv | no | no |

Refusals emit nothing; they return a reason code to the caller. Planning volumes for the Event bus F1 and F4 budgets: typical 0 events per tick, peak 8 (a Utility AI re-gear pass of a party: 5 members × 4 slots, spread over the town visit); `ring_per_day` 801 ≤ 10, 802 ≤ 10, 803 ≤ 5. No `derive` (RNG) calls: this system takes no randomness.

**R11: Determinism.** Every rule here is integer arithmetic over the record and boot tables. No RNG, no clock, no float at runtime. The Python reference and the GDScript port must produce identical profiles for the parity vectors (F1–F4, AC-12).

### States and Transitions

A member record is in one of two roster states. The behavioural states (`idle`, `hunting`, `dead` …) belong to Member state machine (41), not here.

| State | Meaning | In `name_record` | Counts against `member_cap` |
|-------|---------|------------------|------------------------------|
| `OnRoster` | In the guild | yes | yes, if `rank = disciple` |
| `OffRoster` | Left (any Retention cause) or not yet returned — never poached off the roster (user decision 2026-11-16) | yes (kept forever) | no |

| From | To | Trigger |
|------|----|---------|
| (none) | `OnRoster` | `create_member` with a new ID |
| `OnRoster` | `OffRoster` | `remove_member` (R9) |
| `OffRoster` | `OnRoster` | `create_member` with the original ID, origin `returned` (R2) |
| `OnRoster` | `OnRoster` | `rank` changes to `elder` (Rebirth 23): stops counting against `member_cap` (Elders are unlimited) |

There is no deletion: an ID that was issued always resolves to a name.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Owner of the interface |
|--------|-----------|---------|----------|------------------------|
| Data layer (3) | in | `schools` (role, armor_class), `items` (slot, family, school_req, armor_class, level_req, stats), `sim_params` member keys, `sim_roles`, `enhance` (`stat_pct_total`) | — | Data layer owns loading; this system owns the meaning of the `member_*` keys |
| Sim core (1) | in | P1 handler registration (commands: `rename_member`, `equip`, `unequip`, `create_member`, `remove_member`) | — | Sim core owns phases; this system owns its handlers at P1 order 800 |
| Event bus (42) | out | — | Types 801–805 | This system owns block 800–899 |
| Schools (20) | both | Writes the R2 school fields; calls `unequip` on join/change | `school_id` read for role and gear checks | Schools owns the values |
| XP curve (22) | both | Writes `level`, `xp_milli` | `init_progress` called at creation | XP curve owns the values |
| CA/PA and traits (9) | both | Writes `pa`, `traits` at creation | Reads level, rebirth, equipment tiers, skills for CA | CA/PA owns CA (moved out of `model.py`) |
| Items and loot (26) | both | Hands items to `equip`; receives items from `unequip`, removal | Equipped items | Items owns storage and the bag |
| Equipment enhancement (24) | in | Writes `enhance_lv` on an equipped item; owns `stat_pct_total` | — | Enhancement owns the values |
| Combat (10) | both | Writes `hp_milli` | `profile`, `gear_stat` | This system owns the profile formula; Combat owns how it is used |
| Gold economy (27) | in | Writes `gold` | — | Gold economy owns every credit and debit |
| Member state machine (41) | both | Writes `state` and needs | Reads roster; gates `equip` and removal | 41 owns states |
| Utility AI (12) | out | — (returns purchases; owns the former `auto_gear` policy) | Profile, equipment | Utility AI owns gear choice |
| Member state machine (41) | out | Calls `equip` with Utility AI's purchases at trip close | Profile, equipment | MSM owns when gear is applied |
| Recruitment (15), Jianghu (17) | in | `create_member(spec)` | ID | This system owns creation and the ID rule |
| Retention (16) | in | Writes loyalty, mood, contract; calls `remove_member` | — | Retention owns leaving |
| Rebirth and Ascension (23) | in | Writes `rebirth`, `rank` | — | Rebirth owns them |
| Guild and buildings (30) | in | `member_cap` (no Elder cap) | — | Guild owns capacity |
| Local save (6) | out | — | Record serializer, `next_member_id`, `name_record` | Save owns the contract; this system registers its serializer |
| Guild screens (39), World view (38) | out | — | Read-only record, profile, name record | Read only |

## Formulas

All stat values are integers in thousandths (`_milli`); multipliers are integers in parts per million (`_ppm`). Float `pow()` runs only at boot, to build the tables; `round` is round-half-away-from-zero; `//` is floor division on non-negative integers. The reference `sim/model.py` computes the same values in float at runtime; the boot tables reproduce them to within 0.001.

### F1: Base stat tables

The base_stat formula is defined as:

`atk_base_milli[L] = round(1000 · member_atk_coef · L^member_atk_exp)`
`hp_base_milli[L] = round(1000 · (member_hp_coef · L^member_hp_exp + member_hp_flat))`
`def_base_milli[L] = round(1000 · member_def_coef · L^member_def_exp)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| L | int | 1 – 200 | calculated (table index) | Member level |
| member_atk_coef | float | 0.5 – 10 (2.5 today) | data file (`sim_params`) | Attack scale |
| member_atk_exp | float | 1.0 – 1.6 (1.25) | data file | Attack growth exponent |
| member_hp_coef | float | 5 – 100 (30) | data file | HP scale |
| member_hp_exp | float | 1.0 – 1.5 (1.15) | data file | HP growth exponent |
| member_hp_flat | float | 0 – 1,000 (100) | data file | Flat HP every member has |
| member_def_coef | float | 0.2 – 5 (1.2) | data file | Defence scale |
| member_def_exp | float | 1.0 – 1.5 (1.2) | data file | Defence growth exponent |

**Output Range:** atk 2.5 (L1) to ≈1,880 (L200); hp 130 (L1) to ≈13,383 (L200); def 1.2 to ≈692. Monotonic in L for any exponent > 0.
**Example:** L50: atk 2.5 · 50^1.25 = 332.40 → 332,400 milli; hp 30 · 50^1.15 + 100 = 2,797.35 → 2,797,347; def 1.2 · 50^1.2 = 131.20 → 131,203.

### F2: Gear sums

The gear_sum formula is defined as:

`flat_milli(k) = Σ_slots round(1000 · v_k(item) · (1 + stat_pct_total[enhance_lv]))` for k in {atk, hp, def}
`pct_ppm(k) = Σ_slots round(1,000,000 · v_k(item))` for k in {atk_pct, hp_pct, def_pct}

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| v_k(item) | float | 0 – ~2,000 flat; 0 – 0.1 pct | data file (`items.stats`) | The item's stat k; absent = 0 |
| enhance_lv | int | 0 – 20 | calculated (Enhancement 24) | The item's enhancement level |
| stat_pct_total | float | 0 at lv 0; 0.04 – 0.65 at lv 1–20 | data file (`enhance.csv`) | Enhancement bonus on the item's flat stats (provisional, OQ-2) |

**Output Range:** 0 with no gear. With four best-tier items at +20, flat atk ≈ 1.65 × the weapon's atk. pct sums ≤ 4 × the largest pct on any item (0.05 today → 200,000 ppm).
**Example:** L50 kim_2 wearing `eq_wpn_sword_06_c` (atk 444), `eq_arm_medium_06_c` (def 178, hp 1109), `eq_acc_ring_06_c` (atk_pct 0.05), `eq_acc_amulet_06_c` (hp_pct 0.05, def_pct 0.025), all +0: atk 444,000; hp 1,109,000; def 178,000; atk_pct 50,000 ppm; hp_pct 50,000; def_pct 25,000.

### F3: Combat profile

The profile formula is defined as:

`atk_milli = (atk_base_milli[L] + flat_milli(atk)) · (10⁶ + pct_ppm(atk_pct)) // 10⁶`
`skill_ppm = round(10⁶ · skill_dps_bonus) · min(L, skill_dps_ref_level) // skill_dps_ref_level`
`dps_milli = (atk_milli · role_dps_ppm // 10⁶) · (10⁶ + skill_ppm) // 10⁶`
`hp_max_milli = ((hp_base_milli[L] + flat_milli(hp)) · role_hp_ppm // 10⁶) · (10⁶ + pct_ppm(hp_pct)) // 10⁶`
`def_milli = ((def_base_milli[L] + flat_milli(def)) · role_def_ppm // 10⁶) · (10⁶ + pct_ppm(def_pct)) // 10⁶`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| role_dps_ppm, role_hp_ppm, role_def_ppm | int | 500,000 – 1,600,000 | data file (`sim_roles`, × 10⁶ rounded at boot) | The school role's multipliers; 1,000,000 for an unaffiliated member (R7) |
| skill_dps_bonus | float | 0 – 1 (0.4) | data file (`sim_params`) | Stand-in for skill damage until Skills (21) supplies it (OQ-6) |
| skill_dps_ref_level | int | 1 – 200 (100) | data file (`sim_params`, new key; the reference hardcodes 100) | Level at which the skill stand-in is full |
| atk/hp/def_base_milli, flat_milli, pct_ppm | int | F1, F2 | calculated | As above |

**Output Range:** dps ≈1.38 (L1 healer, no gear: 2.5 × 0.55 × 1.004) to ≈3,290 (L200 melee_burst, no gear) and higher with gear. All outputs > 0 for L ≥ 1, because every base term is positive and every multiplier ≥ 500,000 ppm. Largest intermediate (hp at L200 with gear, ≈ 3 × 10⁷ milli × 1.6 × 10⁶) is under 10¹⁴, well inside int64.
**Example:** the F2 member (melee_burst: dps 1.25, hp 1.0, def 1.0): atk (332,400 + 444,000) × 1.05 = 815,220; skill_ppm = 400,000 × 50 // 100 = 200,000; dps 815,220 × 1.25 × 1.2 = 1,222,830 (reference 1,222.82); hp_max (2,797,347 + 1,109,000) × 1.05 = 4,101,664 (reference 4,101.66); def (131,203 + 178,000) × 1.025 = 316,933 (reference 316.93).

### F4: Profile hash

The profile_table_hash formula is defined as:

`profile_table_hash = hash(atk_base_milli[1..200], hp_base_milli[1..200], def_base_milli[1..200], role ppm rows)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| tables | int arrays | F1, F3 | calculated at boot | The boot tables |
| hash | function | — | constant (the same content hash as Data layer F1) | Order-sensitive hash |

**Output Range:** one 64-bit value per content build. Recorded in the parity vectors (Dev tooling 43), so a Python and GDScript build that disagree on one cell fail before play.
**Example:** changing `member_atk_exp` from 1.25 to 1.26 changes every `atk_base_milli` cell from L2 up and so changes the hash.

### F5: HP rescale

The hp_rescale formula is defined as:

`hp_new = min(hp_max_new, hp_old · hp_max_new // hp_max_old)` when `hp_max_old > 0`; `hp_new = hp_max_new` at creation

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| hp_old | int | 0 – hp_max_old | calculated (record) | HP before the profile change |
| hp_max_old, hp_max_new | int | > 0 | calculated (F3) | Max HP before and after |

**Output Range:** 0 to hp_max_new. The member's HP fraction is preserved (rounded down), so swapping gear neither heals nor wounds. A dead member (hp 0) stays at 0.
**Example:** hp 2,000,000 of 4,101,664, member removes the amulet (hp_max → 3,906,347): 2,000,000 × 3,906,347 // 4,101,664 = 1,904,750.

### F6: ID and name-record bound

The lifetime_members formula is defined as:

`lifetime_members ≈ roster_max + leave_rate · roster_max · months + ascensions`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| roster_max | int | 12 – 40 | data file (`bld_hq` `member_cap`) | Disciples on the roster |
| leave_rate | float | 0.03 – 0.10 per month | constant (S2 target, Retention 16) | Monthly share of members leaving |
| months | int | 1 – 36 | constant (planning horizon) | Save lifetime |
| ascensions | int | 0 – ~100 | calculated | Graduates replaced by recruits |

**Output Range:** 40 + 0.10 × 40 × 36 + 100 ≈ 284 over three years at the worst rate; recruits who are rejected before joining are never issued an ID. This confirms the Event bus planning bound `milestone_subjects_planned = 1,000` with ≈3.5× margin (Event bus OQ-4). At ≈64 bytes per name-record entry, 1,000 entries are ≈64 KB of save.
**Example:** 40 members, 5% leaving per month, 24 months, 30 ascensions: 40 + 48 + 30 = 118 IDs.

## Edge Cases

### A. Identity

- **If `create_member` is refused by any field owner**: no ID is consumed, no name record is written, nothing is emitted. The next successful creation gets the ID this one would have had.
- **If a returning member's original ID is on the roster already, or was never issued by this save**: refused with `MM_ID_INVALID`. A save edit cannot forge a returning member into an ID that belongs to someone else.
- **If two members have the same name**: allowed; screens and the Chronicle disambiguate by ID (Guild screens 39).
- **If a rename is submitted for a member who left in the same tick**: the rename is refused with `MM_MEMBER_UNKNOWN`, because removal ran first in an earlier phase or earlier in P1 order; the name record keeps the last name.
- **If `name_record` exceeds 1,000 entries**: nothing is lost; F6 is a planning bound, not a cap. The Event bus may start evicting old milestones (its F5), which is its rule to apply.

### B. Equipment

- **If an item is equipped into an occupied slot**: the old item moves to guild storage in the same step, before the new one is placed. There is never a tick with two items in one slot or zero items lost.
- **If guild storage is full when an item must move there**: Items and loot (26) owns the storage capacity rule; this system requires that storage never refuses an item from `unequip`, removal or a school change (PROVISIONAL, OQ-7). An item is never destroyed.
- **If an equipped item's row is later retired**: it stays equipped and keeps its stats; retired rows still resolve (Data layer R3).
- **If an equipped item no longer meets `level_req`**: cannot happen, because levels never fall (XP R7).
- **If a member changes school while wearing a now-invalid weapon or armour**: Schools R5 unequips it to storage. Accessories have no school rule and stay.
- **If `enhance_lv` is above the table's last row**: Enhancement (24) never writes one; the validator bounds it to 0–20. This system treats it as a data error and refuses to boot.
- **If gear is swapped to exploit HP**: impossible. F5 keeps the HP fraction, so equipping a high-HP item, healing, and removing it ends at the same fraction as before.

### C. Profile and HP

- **If a member is unaffiliated**: neutral role multipliers (R7), no weapon. Their profile is weaker than any affiliated member of the same level only through the missing weapon.
- **If a member is dead (hp 0) and gear changes**: hp stays 0 (F5). Revival is Member state machine (41) and Combat's.
- **If the level rises mid-fight**: the profile signature changes, the profile is re-derived and HP rescaled on the next read, inside the same tick. Combat reads the new profile from then on.
- **If `hp_max_old` is 0**: unreachable (F3 outputs > 0 for L ≥ 1); the rescale treats it as creation and sets full HP.

### D. Roster

- **If headquarters capacity falls below the roster** (a future building rule): no one is removed; only new creations are refused until the count is below `member_cap`.
- **If `remove_member` is called for a member in a party or raid**: refused with `MM_STATE_BLOCKED`; Member state machine (41) must move them to `away` first, which takes them out of the party.
- **If the save loads a member whose ID is ≥ `next_member_id`**: the save is invalid; Local save (6) owns the policy for a corrupt save. This system reports `MM_ID_INVALID`.

## Dependencies

### Upstream (this system depends on)

| System | Hard / soft | Interface | What it provides |
|--------|-------------|-----------|------------------|
| Data layer and content pipeline (3) | Hard | `schools`, `items`, `sim_params`, `sim_roles`, `enhance` tables | Content and profile parameters |
| Sim core and tick loop (1) | Hard | `register(P1, 800, member_model, handler)`; handler context | Command phase and `emit` |
| Event bus and history log (42) | Hard | `register_type` for 801–805; ring budget | Delivery and the history log |
| Schools and school change (20) | Hard | The R2 fields; `school_id` → role, armor_class | School state |
| XP and level pacing curve (22) | Hard | `init_progress`; `level` | Level |
| Items and loot tables (26) | Hard (PROVISIONAL, no GDD yet) | Hands items to `equip`, accepts items from `unequip` without refusal | Item movement, storage, bag |
| Guild and buildings (30) | Hard (PROVISIONAL) | `member_cap` from `bld_hq` (Elders uncapped) | Roster capacity |
| Equipment enhancement (24) | Soft (PROVISIONAL) | `enhance_lv` writes; `stat_pct_total` | Gear bonus (0 until it ships) |
| Member state machine (41) | Hard (PROVISIONAL) | Current state for R6 rule 6 and R9 | State gating |

### Downstream (systems that depend on this one)

| System | Hard / soft | Interface | What they need |
|--------|-------------|-----------|----------------|
| CA/PA and traits (9) | Hard | Record fields; `pa`, `traits` storage | Inputs to CA |
| Combat (10) | Hard | `profile`, `gear_stat`, `hp_milli` | Fighting numbers |
| Zones and hunt (11), Party (13), Golden Boss (14) | Hard | `profile`, roster | Who fights, how hard |
| Utility AI (12) | Hard | Record, profile, `equip` | Decisions and gearing |
| Recruitment (15), Jianghu (17) | Hard | `create_member`, `remove_member`, ID rule | People in and out |
| Retention (16) | Hard | Field storage, `remove_member` | Leaving |
| Skills (21), Rebirth (23) | Hard | Field storage | Their fields |
| Gold economy (27) | Hard | `gold` storage | Member wallet |
| Offline progress (31) | Hard | Profile, record | Aggregate resolution |
| Local save (6) | Hard | Serializer, `next_member_id`, `name_record` | Persistence |
| Event bus (42), AI text (36), Analytics (37) | Soft | Events 801–805, name record | History and names |
| World view (38), Guild screens (39) | Hard | Read-only record and profile | Display |
| Member state machine (41) | Hard | Roster, field storage | States |

## Tuning Knobs

| Knob | Source | Default | Safe range | Too high | Too low | Interacts with |
|------|--------|---------|------------|----------|---------|----------------|
| `member_atk_coef` | `sim_params` | 2.5 | 1.5 – 4 | Monsters die too fast; hunts out-pace XP curve | Kill time balloons, XP/hour drops | `monster_hp_coef` (Zones 11): only the ratio matters |
| `member_atk_exp` | `sim_params` | 1.25 | 1.15 – 1.35 | Late levels trivialise monsters | Late game stalls | `monster_hp_exp` (1.3) |
| `member_hp_coef`, `member_hp_exp`, `member_hp_flat` | `sim_params` | 30, 1.15, 100 | 20–45, 1.05–1.25, 50–200 | No deaths, potions unused (sink, §19) | `thuy_1`-style fragility everywhere | `monster_atk_*`, `monster_dmg_factor` |
| `member_def_coef`, `member_def_exp` | `sim_params` | 1.2, 1.2 | 0.8–2, 1.1–1.3 | Damage floor hit, armour dominant | Armour irrelevant | Combat's damage formula (10) |
| `skill_dps_bonus` | `sim_params` | 0.4 | 0 – 0.6 | — | — | Retired by Skills (21), OQ-6 |
| `skill_dps_ref_level` | `sim_params` (new) | 100 | 50 – 200 | Skill stand-in ramps too slowly | Full by mid-game | `skill_dps_bonus` |
| `sim_roles` rows | `sim_roles` | per role | dps 0.5–1.3, hp 0.85–1.6 | One role dominates parties | Role unplayable solo | Party (13), Combat (10) |
| `member_name_max_len` | `config` (new) | 20 | 12 – 32 | Names overflow UI | Vietnamese full names truncated | Guild screens (39) |
| `member_cap` | `buildings.csv` (`bld_hq`) | 12 – 40 | — | Owned by Guild and buildings (30); not duplicated here | — | Raid performance (§3.5, Sim core OQ-6) |
| `stat_pct_total` | `enhance.csv` | 0.04 – 0.65 | — | Owned by Equipment enhancement (24) | — | GDD §19.3 balance warning |

Every profile knob shifts the XP pacing measured in XP curve §4.3; re-run `balance_sim` after any change.

## Visual/Audio Requirements

No art bible exists (`design/art/art-bible.md` absent), so this is drafted from GDD §1 and §12.4, and `art-director` input is from the lens only.
- **Member identity.** Each member's sprite is selected by school (and `unaffiliated` uses a plain trainee look). The name is shown above the sprite in the world view when selected (World view 38).
- **Equipment.** In MVP, gear is not drawn on the sprite (pixel sprites per school, §12.4). A gear change shows a short "power up" glint on the sprite and the stat delta on the member panel.
- **Events.** `member_joined`: an arrival beat at the headquarters gate (walk-in), with a short welcome chime. `member_removed`: the member walks out of the gate; no sound beyond the UI notification. `member_renamed`: UI only.
- **Audio.** Equip: a short metallic click (weapon/armour) or soft chime (accessory). Owned and mixed by Audio (40).

📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:member-model` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

This is a data system; its feel is responsiveness and trust.
- **Gear lands on the same tick.** The profile is re-derived in the tick the `equip` is applied (≤ 100 ms at 10 Hz); the panel numbers update in the next presented frame. No "recalculating" state.
- **Numbers never jump the wrong way.** HP keeps its fraction on a gear swap (F5), so a bar never refills or empties because of a swap.
- **The member is the same person.** Renames, school changes and returns keep the ID; the panel and Chronicle never show a stranger.

## UI Requirements

- **Member panel** (Guild screens 39): name (editable), school or "aspiring: X", level and rebirth, the four profile values (atk, dps, max HP, def), and the four gear slots with item name, tier and `+enhance_lv`. PA is never shown exactly unless the entitlement allows it (CA/PA 9, §5.1).
- **Equip flow:** choosing an item from guild storage shows the profile delta before confirming. A refused equip shows its reason (level too low, wrong school, wrong armour class, member busy) in words, not by colour alone.
- **Rename:** inline text field, `member_name_max_len` limit, live validation.
- **Departed members:** the Chronicle and history show their name from the name record, marked as no longer in the guild.

**📌 UX Flag — Member model**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for each screen or HUD element this system contributes to **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD | Other GDD | Their section | Relationship |
|----------|-----------|---------------|--------------|
| R1, R6, R7 | Schools and school change | R2, R3, R5, R7 | Schools owns the school fields; Member model stores them and enforces the weapon/armour rules Schools defines |
| R1, R8 | XP and level pacing curve | R1, R9 | XP owns `level`/`xp_milli`; Member model calls `init_progress` |
| R2, R3, R10, F6 | Event bus and history log | R3a, F5, OQ-4, AC-30b | IDs never reused; name record for every issued ID; `milestone_subjects_planned` = 1,000 confirmed |
| R10 | Event bus and history log | R2 (type blocks) | Block 800–899 |
| R8 (P1 order 800) | Sim core and tick loop | R4, R5, OQ-5 | Handler registration |
| Formulas | Data layer and content pipeline | R3, F1, F6 | Stable IDs, content hash, `_ppm` integers |
| F4 | Dev tooling and parity harness | parity vectors | `profile_table_hash` in golden vectors |
| Max roster | Sim core and tick loop | AC-34 (max-roster fixture) | 40 disciples + a fixture Elder count (Elders are uncapped and terminal, so they add save size, not tick cost; OQ-5) |

## Acceptance Criteria

Automated (Logic) unless marked.

- **AC-1 [Logic] (R1)**: **GIVEN** a member created with `pa` 120, **WHEN** any system other than CA/PA writes `pa`, **THEN** the write is refused (Python: the record exposes no setter outside the owner's module; port: a code search finds no write path). `pa` reads 120 after 10,000 ticks of hunting.
- **AC-2 [Logic] (R1)**: **GIVEN** the record's field table, **WHEN** the test suite runs the ownership check, **THEN** each field has writes from exactly its listed owner and none from any other module.
- **AC-3 [Logic] (R2)**: **GIVEN** a new save, **WHEN** three members are created, one removed, and two more created, **THEN** the IDs are 1, 2, 3, 4, 5 and the removed member's ID is never issued again.
- **AC-4 [Logic] (R2)**: **GIVEN** member 2 removed, **WHEN** `create_member` is called with origin `returned` and ID 2, **THEN** the member is back on the roster as ID 2 and `next_member_id` is unchanged. **WHEN** called with ID 2 while 2 is on the roster, or with ID 99 never issued, **THEN** `MM_ID_INVALID`.
- **AC-5 [Integration] (R3)**: **GIVEN** member 7 renamed "Lý Thường Kiệt" and then removed, **THEN** `name_record[7]` returns "Lý Thường Kiệt" and the Event bus resolves ID 7 to that name (satisfies Event bus AC-30b).
- **AC-6 [Logic] (R4)**: **GIVEN** `member_name_max_len` 20, **WHEN** renaming to "", to 21 code points, or to a string containing U+0007, **THEN** each is refused with `MM_NAME_INVALID` and the old name kept; a 20-code-point Vietnamese name with diacritics is accepted.
- **AC-7 [Logic] (R5, R6)**: **GIVEN** a level 50 `kim_2` member, **WHEN** equipping `eq_wpn_sword_06_c` (level_req 50), **THEN** it is accepted; `eq_wpn_heavy_blade_armor_01_c` (school_req kim_1) is refused with `MM_SCHOOL_MISMATCH`; a level 60 item with `MM_LEVEL_TOO_LOW`; a potion with `MM_SLOT_INVALID`; and each refused item is back where it came from.
- **AC-8 [Logic] (R6)**: **GIVEN** a member with a sword in `weapon`, **WHEN** a second sword is equipped, **THEN** the first sword is in guild storage, the second is in the slot, and the total count of that item ID across slots and storage is unchanged. **WHEN** the member is in `hunting`, **THEN** `equip` is refused with `MM_STATE_BLOCKED`.
- **AC-9 [Logic] (R7)**: **GIVEN** a cached profile for a `kim_2` member, **WHEN** Schools completes a change to `kim_1` (tank), **THEN** the next `profile` read uses the tank multipliers (dps 0.7, hp 1.6, def 1.3), not the cached melee_burst ones.
- **AC-10 [Logic] (F1)**: **GIVEN** default `sim_params`, **THEN** `atk_base_milli[1]` = 2,500, `hp_base_milli[1]` = 130,000, `def_base_milli[1]` = 1,200, and `atk_base_milli[50]` = 332,400 ± 1.
- **AC-11 [Logic] (F2, F3)**: **GIVEN** the F2 example member, **THEN** `profile` returns atk 815,220 ± 2, dps 1,222,830 ± 2, hp_max 4,101,664 ± 2, def 316,933 ± 2 milli, and each is within 0.001 of `sim/model.py` `Member.stats` for the same member.
- **AC-12 [Integration] (R11, F4)**: **GIVEN** the parity vectors, **WHEN** Python and GDScript build the boot tables, **THEN** `profile_table_hash` is equal, and 200 sampled members (all levels × roles × gear sets) have identical profiles.
- **AC-13 [Logic] (F3 boundary)**: **GIVEN** an unaffiliated L1 member with no gear, **THEN** dps = 2,500 × 1.0 × 1.004 → 2,510 milli and hp_max = 130,000; **GIVEN** a L200 melee_burst member with no gear, **THEN** all values are > 0 and below 10¹⁴ intermediate.
- **AC-14 [Logic] (F2, Enhancement)**: **GIVEN** the sword at `enhance_lv` 10 (`stat_pct_total` 0.40 in `enhance.csv`), **THEN** its flat atk contribution is 444 × 1.40 = 621,600 milli, and at `enhance_lv` 0 it is 444,000.
- **AC-15 [Logic] (F5)**: **GIVEN** hp 2,000,000 of 4,101,664, **WHEN** the amulet is removed, **THEN** hp = 1,904,750; **WHEN** re-equipped, **THEN** hp ≤ 2,000,000 and the fraction differs by under 0.001. **GIVEN** hp 0, **WHEN** gear changes, **THEN** hp stays 0.
- **AC-16 [Logic] (R8)**: **GIVEN** `member_cap` 12 and 12 disciples, **WHEN** `create_member` is called, **THEN** `MM_ROSTER_FULL`, no ID consumed, no event. **GIVEN** 11, **THEN** the member is created with full HP, empty slots, and `init_progress` was called once.
- **AC-17 [Logic] (R8)**: **GIVEN** XP curve refuses the spec's level (error 2202), **WHEN** `create_member` runs, **THEN** creation is refused, `next_member_id` is unchanged, and no 801 event is emitted.
- **AC-18 [Integration] (R9)**: **GIVEN** a member in `away` wearing four items with 2 potions in the bag, **WHEN** `remove_member` runs, **THEN** the four items and potions are in guild storage, the member is `OffRoster`, the name record remains, and 802 is emitted once. **GIVEN** the member is in a party in `hunting`, **THEN** `MM_STATE_BLOCKED`.
- **AC-19 [Logic] (R10)**: **GIVEN** the Event bus boot, **THEN** types 801–805 are registered to `member_model` in block 800–899, 801 is a logged milestone with `subject_slot` 1, 802–803 are logged, 804–805 are not.
- **AC-20 [Logic] (R11)**: **GIVEN** the same command stream and seed, **WHEN** run twice, **THEN** the serialized member records and `name_record` are byte-identical, and this system made 0 `derive` calls.
- **AC-21 [Integration] (Utility AI 12, PENDING)**: **GIVEN** the balance simulator with `auto_gear` moved to Utility AI, **WHEN** the standard 5-member run reaches level 100, **THEN** the time is within 2% of the reference measurement (≈71 hours, GDD §4.3).
- **AC-22 [UI] (UI Requirements)**: screenshot of the member panel showing name, school, level, the four profile values and four gear slots, retained in `production/qa/evidence/`.

## Open Questions

| # | Question | Owner | Target |
|---|----------|-------|--------|
| OQ-1 | **Scope question (not decided in this batch run).** GDD §4.1 lists primary attributes `stats{str,agi,vit,int,luck}`; `sim/model.py` has none and derives the profile from level, role and gear. Add them (and define how they enter F3), or drop them from §4.1? | User / game-designer | Before Combat (10) is designed |
| OQ-2 | PROVISIONAL: Equipment enhancement (24) — `stat_pct_total` multiplies the enhanced item's flat stats only, not its pct stats, and `enhance_lv` is plain data on the equipped item. Confirm, and re-measure pacing with S5 (§19.3 warns +10 = +40%). | Equipment enhancement (24) | When 24 is designed |
| OQ-3 | Unaffiliated members use neutral role multipliers as constants. Should `sim_roles.csv` get an `unaffiliated` row so they are data-driven? (Data schema change; not made here.) | Data layer (3) / Schools (20) | Before implementation |
| OQ-4 | `crit_rate` (63 items) and any future non-profile stat are exposed by `gear_stat` but no system consumes them yet. Combat (10) to define. | Combat (10) | When 10 is designed |
| OQ-5 | **RESOLVED (user decision 2026-11-16):** Elders are unlimited and outside `member_cap`; there are no elder slots (Rebirth F2, registry `elder_slots_max` deprecated). Elders sit in the terminal `elder` state and do not tick, so the Sim core AC-34 max-roster fixture is 40 disciples plus a fixture-chosen Elder count that tests save size only; the lifetime bound is F6 (`ascensions` term). | Guild and buildings (30), Rebirth (23) | Closed |
| OQ-6 | `skill_dps_bonus` × `min(1, L/100)` is a stand-in for skills. When Skills (21) supplies skill damage, the term is removed and the pacing re-measured. `skill_dps_ref_level` is a new `sim_params` key replacing a hardcoded 100. | Skills (21) | S4 |
| OQ-7 | PROVISIONAL: Items and loot (26) — guild storage never refuses an item returned by `unequip`, removal or a school change; item movement is by value `{item_id, enhance_lv}`, with no per-instance IDs. | Items and loot (26) | When 26 is designed |
| OQ-8 | PROVISIONAL: Member state machine (41) — `equip`/`unequip` are refused in `hunting`, `boss_raid`, `away`, `dead`, `training`; `remove_member` requires `away`. | Member state machine (41) | When 41 is designed |
| OQ-9 | PROVISIONAL: Recruitment (15) / Jianghu (17) — the `create_member(spec)` fields listed in R8, and Jianghu handing back the original ID for a returning member. | Recruitment (15), Jianghu (17) | When designed |
| OQ-10 | PROVISIONAL: Gold economy (27) — a departing member's wallet gold leaves with them, recorded as a debit (counts as money leaving the economy in the S3 conservation test). | Gold economy (27) | When 27 is designed |
| OQ-11 | `member_name_max_len` (20) is a new `config` key. Confirm against Guild screens (39) layout and Vietnamese full names. | Guild screens (39) | When 39 is designed |
