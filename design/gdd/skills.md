# Skills

> **Status**: Designed (pending /design-review in a fresh session)
> **Author**: user + Claude (autonomous batch run; decisions in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against
> **Implements Pillar**: None (no game-pillars.md yet)

## Summary

Skills owns the 120 martial skills (12 per school), the one effect schema every skill is written in, and how a member's skill levels grow. For the player, skills are how a recruit turns into a recognisable fighter of their school: the tank starts taunting, the healer starts reviving, the archer's volleys widen, and an ultimate unlocked at level 60 is a visible milestone in a disciple's life. It exists so that Combat can execute any skill from data alone, never branching on a skill ID, and so that skill growth is paced by the same XP curve as the rest of the game.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Data layer and content pipeline, Schools and school change, XP and level pacing curve, Sim core and tick loop, Event bus and history log`

## Overview

Skills defines what a skill *is* and how a member gets better at it. A skill is one content row in `data/skills.csv`: its school, slot (1–12), type (`active`, `passive`, `ultimate`, `secret`), the member level and rebirth tier it needs, its maximum level, mana cost, cooldown, range, target, element, prerequisites, and a packed `effects` cell such as `dmg_mult=1.3+0.05*L;armor_break=0.05*L;dur_s=6`. Every school shares one layout (§6.2): slots 1–4 are actives, 5–8 passives, 9–10 ultimates (level 60 and 100), and 11–12 secrets that open after rebirth. All 120 rows already exist and pass `tools/content_validator.py`; this GDD turns their informal effect strings into a closed, typed schema.

The system has three jobs:
1. **The effect schema.** A closed vocabulary of effect keys, each with one *kind* (damage, damage over time, heal and restore, modifier, control, shape, spawn, trigger) and one unit. Values are linear in the skill level `L` and are converted once at load into exact integers, so the Python reference and the Godot port resolve every skill to the same numbers. Combat (10) executes kinds; it never asks which skill it is running.
2. **Skill levels.** Each member holds a level and progress for each of their school's 12 skills. A share of every XP award the member earns trains one *focus* skill; each skill's level is capped by a gate tied to the member's own level, so skills keep pace with the member instead of racing ahead. The player can pin the focus, or leave it to a deterministic auto-pick.
3. **The member's resolved kit.** For Combat, Skills supplies each member's *loadout* (castable skills with their resolved effects) and *passive sheet* (summed permanent modifiers and triggers). For CA/PA (9), it supplies `skill_norm`, the member's skill investment as a fraction.

**Player impact.** Skills are the most visible sign of growth after the level number. In an idle game the player does not press skill buttons; they watch members use what they have learned and decide where training goes. The interesting choices are which skill a valued member focuses on, and when a school change or a rebirth is worth the skill levels it costs.

**What this system does not own.**
- When a skill is cast, mana pools, cooldown timers, targeting, hit resolution and every random draw in a fight: Combat (10).
- The element multipliers: Combat (10). A skill's `element` column is an input to them.
- Which school a member belongs to, and the per-slot carry on a school change: Schools (20, F4). Skills applies the carried levels.
- The percentage kept on rebirth: Rebirth and Ascension (23), `rebirth.csv` `skill_keep_pct`. Skills applies it.
- The XP a member earns: XP curve (22) and the systems that pay XP.
- Monster abilities (`monsters.csv` `ai_skills`): Zones and hunt (11) and Combat (10). They are bare tokens today (Open Questions).
- Skill display names and descriptions: Localization (4).

## Player Fantasy

Skills serve two feelings, one direct and one beneath it.

**Direct: "my disciple grew into their school."** A recruit arrives with a basic attack. By the first evening the Thiết Huyết Môn tank is taunting the pack off the healer; a few days later, at level 60, the Hồi Xuân healer brings a fallen party member back once per fight, and the player notices because the party that used to retreat now holds the ground. Each new skill level is small; each newly learned slot, and especially each ultimate and secret, is an event worth a line in the Jianghu Chronicle.

**Beneath it: "the guild master shapes the training."** The player does not micro-manage fights, but they can say "Lan trains Mộc Linh Trận first", and see the effect on the next boss. A school change or a rebirth costs skill levels, and the player feels that cost as the loss of something earned, which is what makes those decisions deliberate.

*Candidate framings considered (creative-director lens, applied in this session):*
1. **The disciple who grew into their school (chosen).** Moment: a member's first ultimate fires in a raid. Asks of the design: visible milestones (2102 milestone event, UI badge), effects that are readable in the world view.
2. **The master's training plan.** Moment: pinning a focus and watching it pay off at the next boss. Asks of the design: a focus command, fast enough training that the choice shows within a session.
3. **The scroll collection.** Moment: reaching a secret skill after rebirth. Asks of the design: secrets that feel unlike the base kit. Folded into framing 1 as its late-game beat.

No game pillars exist yet, so no pillar is quoted; the framings are anchored to GDD §1 (members grow stronger), §6.2 (skill tree) and §6.10 (rebirth opens secrets).

## Detailed Design

### Core Rules

*Specialist lenses applied before drafting (Progression → game-designer primary; systems-designer, economy-designer supporting):*
- **game-designer:** the player's decision is focus and timing of school change or rebirth, not casting. Training must be automatic, so an AFK guild still grows; the focus pin is the one lever. Ultimates and secrets must land as milestones.
- **systems-designer:** 130 distinct effect keys exist today. Without a closed vocabulary with kinds, Combat becomes a switch on skill IDs (the index forbids it). Values must be integers for parity. Every state change (learn, level, focus, carry, rebirth) needs one writer.
- **economy-designer:** skill training costs no gold in this design (the GDD prices only the Academy building and school change); the XP share is a pure faucet from hunting. The level gate and the bank cap stop it from becoming a way around the school-change cost (Edge Cases). No conflict between roles needed a user decision.

**R1: Skill definitions are content.** A skill is one row of `skills.csv`, looked up by its stable `id` and never by row position (Data layer R3). Columns and their meaning:

| Column | Type | Meaning |
|---|---|---|
| `id` | str | Stable ID, e.g. `sk_kim1_03`. Never parsed for meaning |
| `school_id` | ref(schools) | The owning school. Its 12 rows are that school's tree |
| `slot` | int 1–12 | Position in the shared layout: 1–4 `active`, 5–8 `passive`, 9–10 `ultimate`, 11–12 `secret` |
| `type` | enum | `active`, `passive`, `ultimate`, `secret` |
| `lv_req` | int | Member level needed to learn level 1 (F2) |
| `rebirth_req` | int 0–5 | Rebirth tier needed to learn at all |
| `max_lv` | int | 20 for actives, 10 for the rest today |
| `mp_cost` | int | Mana per cast. 0 for `passive` and `secret` |
| `cooldown_s` | float | Seconds between casts. 0 for `passive` and `secret` |
| `range` | enum | `self`, `melee`, `short_range`, `ranged`, `gap_close`, `ground`. Combat maps each to a distance |
| `target` | enum | `self`, `enemy`, `enemy_aoe`, `ally`, `party`, `ally_fallen`, `ground`, `ground_aoe` |
| `element` | enum | The skill's element, the school's element today |
| `effects` | map(skill_expr) | The effect list (R2, R3) |
| `prereq` | list | `skill_id:level` entries, same school, acyclic (Data layer) |
| `wave` | int | Today `unlock_wave`; renamed by Data layer OQ-1. Equals max(school wave, rebirth tier wave) |

- **Active and ultimate** skills are *cast*: Combat decides when, spends `mp_cost`, starts `cooldown_s`, and applies the effects to `target`.
- **Passive and secret** skills are never cast. Their effects are permanent while the skill is known (R6). A secret's `cd_s` key is the internal cooldown of its trigger.

**R2: One closed effect vocabulary.** Every key that may appear in an `effects` cell is declared once in the effect vocabulary below, with a *kind* and a *unit*. A key not in the vocabulary is a validator error. Combat implements one handler per kind and reads the key's parameters; it never looks at a skill ID, school or slot.

Units: `mult` multiplier of the caster's attack (×); `frac` fraction (0.25 = 25%), signed where marked ±; `chance` a probability (a `frac` used for a draw); `sec` seconds; `tiles` world distance units; `count` whole number; `pts` mana or threat points; `flag` 1; `token` a named ID.

| Kind | Keys (unit) | What Combat does |
|---|---|---|
| `damage` | `dmg_mult` (mult), `hits` (count), `shots` (count), `dmg_per_s` (mult per s, ground zone), `trap_dmg_mult` (mult), `poison_burst` (mult per poison stack), `bonus_below_hp30` (mult, extra when target < 30% HP) | Deals damage to the row's target; `hits`/`shots` split it into that many applications, each at `dmg_mult` |
| `dot` | `burn_per_s` (mult per s), `poison_per_s` (mult per s), `poison_stack` (count), `consume_stacks` (flag) | Applies or consumes a damage-over-time status for `dur_s` |
| `restore` | `heal_mult` (mult), `hot_mult` (mult per tick), `revive_hp_pct` (frac), `mp_restore` (pts), `mp_restore_pct` (frac), `regen_pct_per_s` (frac of max HP per s), `cd_reset_pct` (frac of remaining cooldowns), `cleanse` (flag) | Heals, revives, restores mana, removes debuffs |
| `modifier` | `dmg_taken` (±frac), `dmg_taken_party` (±frac), `dmg_taken_ally` (±frac), `reflect_pct` (frac), `armor_break` (frac), `def_shred` (frac), `def_pct` (frac), `hp_pct` (frac), `atk_pct` (frac), `atk_down` (frac), `atk_speed` (frac), `buff_atk_pct`, `buff_def_pct`, `buff_regen_pct`, `buff_speed_pct` (frac), `buff_dodge` (chance), `slow_pct` (frac), `enemy_acc` (±frac), `heal_received` (±frac), `shield_pct`, `party_shield_pct` (frac of max HP), `redirect_pct` (frac), `wither` (flag), `crit_rate` (chance), `crit_dmg` (frac), `def_ignore`, `def_ignore_vs_poisoned` (frac), `element_dmg`, `element_resist` (frac), `aggro_gain`, `cc_resist` (frac), `potion_effect`, `heal_power`, `party_hp_pct` (frac), `mp_regen`, `party_mp_regen` (frac of max MP per s), `mp_max_pct` (frac), `cd_reduction` (frac), `control_dur_pct`, `buff_dur_pct`, `buff_power_pct` (frac), `poison_resist` (frac), `cleanse_chance` (chance), `poison_dmg`, `poison_dmg_pct`, `burn_dmg`, `burn_dmg_pct` (frac), `poison_stack_max`, `burn_stack_max` (count), `dot_tick_speed` (frac), `range_bonus` (tiles), `aoe_radius_bonus` (tiles), `summon_power`, `summon_cd_reduction`, `trap_dmg` (frac), `summon_count` (count), `shield_cap_pct` (frac), `overbuff_cap` (frac), `pierce` (count), `pierce_dmg` (frac), `enemy_slowed_dmg` (frac) | In an `active`/`ultimate` row: a timed status on the row's target for `dur_s`. In a `passive`/`secret` row: a permanent entry in the member's passive sheet (R6, F6) |
| `control` | `stun_s`, `root_s`, `slow_s`, `taunt_s` (sec), `aggro` (pts), `knockback`, `pull`, `dash` (tiles) | Crowd control, threat and forced movement |
| `shape` | `aoe_radius`, `radius`, `spread_radius`, `trap_chain_radius` (tiles), `dur_s`, `tick_s`, `cd_s` (sec), `stack_max` (count), `once_per_battle` (flag) | Parameters of the other effects in the same row; never an effect alone |
| `spawn` | `summon` (token: `stone_guard`, `earth_titan`), `summon_hp_mult` (mult of caster max HP), `formation` (token: `ward`, `sealed_field`) | Creates a summon or a ground formation for `dur_s` |
| `trigger` | `on_kill_atk_speed` (frac), `on_burn_kill_heal_pct` (frac), `shield_on_hit_pct` (frac), `last_stand_def` (frac) with `below_hp` (frac), `survive_at_1hp` (flag), `auto_revive_self` (flag), `auto_cleanse_party` (flag), `poison_spread_on_death` (flag), `burn_explode_on_kill` (flag) with `explode_dmg_pct` (mult), `overheal_to_shield` (frac), `execute_threshold` (frac), `stun_immunity_break` (flag), `trap_chain` (flag) | Conditional behaviour Combat checks at the named moment (on kill, on hit, below HP, on death). Only in `passive`/`secret` rows; `cd_s` and `once_per_battle` limit it |

The table covers every key in `skills.csv` today (130 keys across 120 rows). Adding a key is a data-schema change: it needs a vocabulary row here, a Combat handler for its kind if the kind is new, and a validator update. A key may not change kind.

**R3: Effect values are linear in `L`, stored as exact integers.** An effect value is a `skill_expr`: a number `c`, a slope `b*L`, or `a+b*L`, where `L` is the skill's level and `a`, `b` may be negative; or a `token` for `spawn` keys. At load each number is converted to an integer in millionths (*micro-units*), so `0.05` becomes 50,000. A number with more than 6 decimals is a load error. Every resolved value is `F1`, an integer; no float is evaluated at run time. A `chance` value is already a `ppm` probability and goes straight to RNG `chance_ppm` (RNG F6); Combat owns the draw.

**R4: A member's skill state.** Member model (8) stores, for each member, these fields. This system is their only writer:
- `skill_lv[slot]` for slots 1–12: int 0 – `max_lv`. 0 means not learned. Levels belong to the member's current school's skills.
- `skill_xp_milli[slot]`: progress toward the next level, in thousandths of skill XP. Kept per skill, so switching focus never loses progress.
- `skill_bank_milli`: skill XP that had nowhere to go (R8), capped at `skill_bank_cap_milli`.
- `skill_focus_slot`: 0 (auto) or a pinned slot 1–12.

An unaffiliated member (Schools R3) has all levels 0 and trains only into the bank.

**R5: Learnable now.** A skill `s` of the member's school can take its next level only if all hold:
1. `s` is live (Data layer F2).
2. The member's rebirth ≥ `rebirth_req(s)`.
3. `skill_lv(s) < gate(s, member)` (F2). The gate is 0 below `lv_req`, so this also covers the level requirement.
4. Every prerequisite `p:n` of `s` has `skill_lv(p) ≥ n`. Prerequisites gate only *further* learning: a level already held (from a carry or a rebirth) is never removed because a prerequisite is below its number (conforms to Schools, Edge Cases).
5. If `academy_gate_enabled` is true: `skill_lv(s) < teach_max_skill_lv` of the guild's Academy (`bld_academy_skill`), or `skill_teach_cap_unbuilt` when it is not built; and an `ultimate` needs the Academy's `unlock_ultimate = 1`, a `secret` its `unlock_secret = 1`. **In MVP `academy_gate_enabled` is false**, because the Academy is not in MVP (user decision 2026-11-16; Schools OQ-1); the gate turns on at Vertical Slice, when the Academy ships.

**R6: Training.** Skill XP comes only from member XP:
1. Each time XP curve (22) applies an award to a member, Skills receives the award's *effective* amount (after growth and rebirth bonuses, before any amount discarded at the level cap) and computes `skill_xp_milli = F4`. Training continues for a capped member, so a level-100 member waiting for rebirth still trains.
2. The amount plus the whole bank is the *pool*; the bank becomes 0.
3. **Pick the focus** (F5): the pinned slot if it is learnable now (R5), else the auto-pick.
4. Pour the pool into the focus's `skill_xp_milli`. While it is ≥ `skill_need_milli(s, skill_lv(s))` (F3) and the skill is still learnable, subtract the need and raise the level by 1.
5. If the focus stops being learnable with pool left, go back to step 3 with the remainder. Each skill is picked at most once per call, so the loop ends after at most 12 picks.
6. Whatever is left when nothing is learnable goes to the bank, up to `skill_bank_cap_milli`; the excess is discarded.
7. Recompute the member's loadout and passive sheet once, if any level changed (R9). Emit events once, after the loop (R10).

The call reads the member's level **after** the award's level-ups, so a member who reaches level 30 in this award can already train a level-30 skill with it.

**R7: Focus.** The player pins a focus with a `set_skill_focus(member_id, slot)` command (Command layer 5), applied in P1. `slot` 0 returns to auto. It is refused with a reason code and no change if the member does not exist, is unaffiliated (reason `no_school`), or `slot` is outside 0–12. A pin to a skill that is *not yet* learnable is accepted: it waits, and auto-pick is used until it becomes learnable. The pin persists until the player changes it, a school change completes (reset to 0), or the member leaves the guild.

**R8: Carry, rebirth and joining.** Skills does not decide how many levels survive; it applies what its owners decide, through one call `set_levels(member_id, levels[12])`:
- **Joining a school** (Schools R3): all levels 0, all progress 0. The bank is kept, so XP earned while unaffiliated trains the first skills at once.
- **School change complete** (Schools R5 step 1): levels = Schools F4 `carried_level` per slot; all progress 0; focus reset to 0; bank kept.
- **Rebirth complete** (Rebirth 23): levels = F7 per slot with that tier's `skill_keep_pct`; all progress 0; focus and bank kept.

A level passed to `set_levels` above the skill's `max_lv` is clamped to `max_lv`; Schools F4 and F7 never produce one.

**R9: The resolved kit.** For each member this system keeps two read-only views, rebuilt only when a level or the school changes (never per tick):
- **Loadout:** for each `active`/`ultimate` skill with level ≥ 1, in slot order: its uid, type, level, `mp_cost`, cooldown in ticks (F8), range, target, element, and its effect list as `(key, kind, value)` with values from F1. Combat reads this to cast.
- **Passive sheet:** for each `modifier` key, the sum over `passive`/`secret` skills with level ≥ 1 (F6); and the list of `trigger` entries with their parameters. Combat and Member model stats read this.

Combat owns caps on the result (for example a crit chance above 100%); this system does not clamp sums.

**R10: Events.** Skills registers the type block 2100–2199 with the Event bus (`skills_event_type_block`) and emits:
- **2101 `skill_level_up`** (`a` member_id, `b` skill uid, `c` old level, `d` new level): once per skill whose level changed in one training call or `set_levels`, never once per level. Delivered, not logged.
- **2102 `signature_skill_learned`** (`a` member_id, `b` skill uid, `c` type code: 3 ultimate, 4 secret): when an ultimate or secret goes from 0 to 1 *by training*. Logged, a milestone with subject slot 1. A carry or rebirth that sets a level does not emit it.
- **2103 `skill_focus_refused`** (`a` member_id, `b` reason code): delivered, not logged.

**R11: No randomness, no clock.** Training, gating, focus and resolution are pure functions of the member's fields, content and the award amount. Skills takes no RNG domain.

**R12: Parity.** At boot this system resolves every skill at every level (F1) into a table and hashes it (`skill_table_hash`, the same SHA-256 convention as XP curve F4). The parity harness (43) records the hash, so a Python and GDScript build that resolve one effect differently fail before play.

### States and Transitions

Per skill, per member:

| State | Meaning | To | Trigger |
|---|---|---|---|
| `Locked` | Level 0 and not learnable (R5 fails) | `Learnable` | Member level, rebirth, prerequisite, Academy or wave condition becomes true |
| `Learnable` | Level < gate and every R5 check holds | `Learned` | Training raises level 0 → 1 |
| | | `Locked` | Never by itself; only `set_levels` to 0 with conditions failing (school change) |
| `Learned` | 1 ≤ level < max_lv | `Learned` (level + 1) | Training, while R5 holds |
| | | `Gated` | Level reaches `gate(s, member)` (F2) or the Academy cap |
| `Gated` | Learned, level = current gate | `Learned` | Member level rises, rebirth, or Academy upgrade lifts the gate |
| `Mastered` | level = `max_lv` | — | Terminal for this life; `set_levels` on rebirth or school change can move it back to `Learned` |

Transitions out of `Learned`/`Mastered` downward happen only through R8 (`set_levels`). Nothing else lowers a skill level. The whole tree is replaced by the new school's tree on a school change.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Data layer (3) | in | `skills` rows typed and frozen; liveness (F2); `config.csv` knobs | — | Data layer owns loading; this system owns the `effects` vocabulary and `skill_expr` type |
| Schools (20) | in | `school_id` → its 12 skills; join and change-complete signals; F4 carried levels | — | Schools owns the carry rule; Skills applies it |
| XP curve (22) | in | Each award's effective amount and the member's post-award level (provisional hook) | — | XP curve owns `award`; Skills only listens |
| Member model (8) | both | Member level, rebirth, school | Writes the R4 fields | Member model owns storage; Skills owns values |
| Combat (10) | out | — | Loadout and passive sheet (R9); the vocabulary (R2) | Combat owns casting, mana, cooldowns, draws and caps |
| CA/PA and traits (9) | out | — | `skill_norm_ppm` (F9) | CA/PA owns the CA formula |
| Rebirth and Ascension (23) | in | Completed rebirth tier and its `skill_keep_pct` | — | Rebirth owns the percentage; Skills applies F7 |
| Guild and buildings (30) | in | Academy level and its `teach_max_skill_lv`, `unlock_ultimate`, `unlock_secret` (only when `academy_gate_enabled`) | — | Guild and buildings |
| Command layer (5) | in | `set_skill_focus` envelopes in P1 | Accepted or refused with reason | Command layer owns dispatch; Skills owns the applier |
| Sim core (1) | in | P1 applier registration; `ctx.emit` | — | Sim core |
| Event bus (42) | out | — | 2101–2103 | Event bus owns delivery |
| Offline progress (31) | in | Aggregate awards through the same XP curve path | — | Offline owns the aggregate |
| Utility AI (12), Party (13) | out | — | Loadout (which skills a member has) for scoring | Each owns its scoring |
| Guild screens (39) | out | — | Skill state, gate, focus, next-level cost | Guild screens |
| Dev tooling (43) | out | — | `skill_table_hash` (R12); validator rules (Edge Cases) | Dev tooling owns the harness |
| Localization (4) | none | — | Names keyed by skill ID | Localization |

## Formulas

*Systems-designer lens applied: every formula was worked at 0, minimum and maximum; findings are in each Output Range and in Edge Cases.*

### F1 — `effect_value`

The effect_value formula is defined as:

`effect_value(key, L) = a_micro + b_micro × L`, for 1 ≤ L ≤ max_lv; a skill at level 0 has no effects.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| a_micro | int | −10⁹ – 10⁹ | data file (`skills.csv` `effects`) | Constant term, in millionths (`0.2` → 200,000) |
| b_micro | int | −10⁹ – 10⁹ | data file (`skills.csv` `effects`) | Per-level slope, in millionths (`0.01*L` → 10,000) |
| L | int | 1 – max_lv (10 or 20) | calculated | The member's level in this skill |

**Output Range:** today −400,000 (`dmg_taken=-0.4`) to 40,000,000 (`mp_restore=10+1.5*L` at L 20 = 40 points). Integer, so identical in Python and GDScript. A `chance` value above 1,000,000 or a `frac` below −1,000,000 at `max_lv` is a validator error (Edge Cases).
**Example:** `sk_kim1_02` `reflect_pct=0.2+0.01*L` at L 12: 200,000 + 10,000 × 12 = 320,000 (32%). `sk_kim1_03` `dmg_mult=1.3+0.05*L` at L 20: 1,300,000 + 1,000,000 = 2,300,000 (×2.3).

### F2 — `gate` (level gate)

The gate formula is defined as:

`gate(s, M, r) = 0` if `M < lv_req(s)` or `r < rebirth_req(s)`; else `min( max_lv(s), 1 + floor( (M − lv_req(s)) / skill_level_step[type(s)] ) )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| M | int | 1 – 200 | calculated | The member's level (XP curve R1) |
| r | int | 0 – 5 | calculated | The member's rebirth tier |
| lv_req(s), rebirth_req(s), max_lv(s) | int | — | data file (`skills.csv`) | The skill's requirements and cap |
| skill_level_step[type] | int | 1 – 20 (active 3, passive 5, ultimate 4, secret 4) | data file (`config.csv`, new) | Member levels per extra skill level |

**Output Range:** 0 – max_lv. With today's data, actives reach level 20 at member level lv_req + 57 (slot 4: level 87), passives level 10 at lv_req + 45 (slot 8: 85), the first ultimate level 10 at 96. The level-100 ultimate (slot 10) can reach only level 1 before rebirth 1 and level 6 at level 120, so its growth spans the rebirths, which is intended (§6.10). A step of 1 makes the gate equal to the cost-only pacing; a step above 20 freezes most skills at level 1–5.
**Example:** `sk_kim1_04` (lv_req 30, active) at member level 50: `1 + floor(20 / 3) = 7`.

### F3 — `skill_need_milli`

The skill_need_milli formula is defined as:

`skill_need_milli(s, k) = max( 1, floor( need_milli[0][t] × skill_need_ppm / 1,000,000 ) )`, with `t = min( 199, lv_req(s) + k × skill_level_step[type(s)] )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| k | int | 0 – max_lv − 1 | calculated | The skill's current level; the result is the cost of k → k + 1 |
| t | int | 1 – 199 | calculated | The member level this skill level is paced to (the level at which F2 first allows k + 1) |
| need_milli[0][t] | int | 10,300 – 809,189,483 | XP curve F1 (rebirth-0 row, always) | Member XP for level t → t + 1 |
| skill_need_ppm | int | 10,000 – 1,000,000 (100,000) | data file (`config.csv`, new) | A skill level costs this share of the member level it is paced to |

**Output Range:** 1,030 milli (slot 1, k 0) to 80,918,948 milli (t 199). Always ≥ 1, so the R6 loop ends. The rebirth-0 row is used at every rebirth on purpose: member levels get 3–18× dearer after rebirth, skill levels do not, so retraining after a rebirth or school change is a quick re-climb.
**Example:** `sk_kim1_04` k 10: t = 30 + 30 = 60; `need_milli[0][60]` = 105,404,008; × 0.1 = 10,540,400 milli (10,540 skill XP). Whole rebirth-0 tree of one school (slots 1–10, every level): ≈ 1,306,656,713 milli.

### F4 — `skill_xp_milli` (training amount)

The skill_xp_milli formula is defined as:

`skill_xp_milli = floor( effective_milli × skill_xp_share_ppm / 1,000,000 )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| effective_milli | int | ≥ 0 | XP curve F2 (`effective_milli`) | The award after growth and rebirth bonuses, before cap discard |
| skill_xp_share_ppm | int | 0 – 1,000,000 (250,000) | data file (`config.csv`, new) | Share of member XP mirrored as skill XP |

**Output Range:** 0 to a quarter of the award. 0 turns training off (only carry and rebirth set levels). Member XP to level 100 at rebirth 0 is ≈ 8.98 × 10⁹ milli, so a PA 100 member (growth ×1.0) earns ≈ 2.25 × 10⁹ skill milli by level 100 against a tree of ≈ 1.31 × 10⁹: the gate (F2), not XP, binds for an average member. A PA 0 member (×0.6) earns ≈ 1.35 × 10⁹, just enough; low-PA members therefore lag on skills when they also spend XP after a school change. This is the PA growth effect of §4.2 reaching skills.
**Example:** a kill paying `effective_milli` 40,000 (40 XP) trains 10,000 milli.

### F5 — `auto_focus`

The auto_focus formula is defined as:

`auto_focus = argmin over learnable s of ( floor( (skill_lv(s) + 1) × 1,000,000 / max_lv(s) ), slot(s) )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| skill_lv(s) | int | 0 – max_lv − 1 | calculated | Current level (only learnable skills are candidates) |
| max_lv(s) | int | 10 or 20 | data file | The skill's cap |
| slot(s) | int | 1 – 12 | data file | Tie-break: lower slot first |

**Output Range:** the slot of the learnable skill furthest from mastery in relative terms; none if nothing is learnable (the pool goes to the bank). Integer keys and a slot tie-break make the pick identical everywhere. Spreading by relative level keeps prerequisites (which ask for a few levels of the previous skill) satisfied without special cases.
**Example:** slot 1 at 6/20 (key 350,000), slot 5 at 2/10 (key 300,000), slot 2 at 3/20 (key 200,000): slot 2 is picked.

### F6 — `passive_sheet`

The passive_sheet formula is defined as:

`sheet[key] = Σ effect_value(key, skill_lv(s))` over the member's `passive` and `secret` skills s with `skill_lv(s) ≥ 1`, for each `modifier` key

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| effect_value | int | F1 | calculated | Each skill's resolved value |
| skill_lv(s) | int | 0 – max_lv | calculated | Level 0 skills contribute nothing |

**Output Range:** sums are additive and uncapped here. Today one school never has the same key in two passives except `reflect_pct`, `crit_rate`, `atk_pct`, `hp_pct`, `cc_resist`, `control_dur_pct`, `buff_dur_pct`, `poison_stack_max`, `burn_stack_max` (e.g. `kim_2` `atk_pct` 0.02×10 + 0.03×10 = 0.5). Combat applies caps.
**Example:** a `kim_1` member with slot 6 at 10 (`reflect_pct=0.015*L` → 150,000) has `sheet[reflect_pct]` = 150,000; slot 2's active `reflect_pct` is a timed status, not part of the sheet.

### F7 — `rebirth_kept_level`

The rebirth_kept_level formula is defined as:

`kept(s) = floor( skill_lv(s) × skill_keep_pct / 100 )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| skill_lv(s) | int | 0 – 20 | calculated | Level before the rebirth |
| skill_keep_pct | int | 0 – 100 (50, 55, 60, 65, 70; 100 for ascension) | data file (`rebirth.csv`) | Owned by Rebirth (23); strictly increasing (validator) |

**Output Range:** 0 – 20. Level 20 at tier 1 keeps 10; level 1 keeps 0 at every tier below 100%. Because the member keeps their level (XP curve R7), F2's gate is already above `kept`, so the member retrains straight away.
**Example:** tier 2 (55%), active at 20 → 11; passive at 7 → 3.

### F8 — `seconds_to_ticks`

The seconds_to_ticks formula is defined as:

`ticks(v_micro) = ceil( v_micro × tick_rate / 1,000,000 )` for `v_micro > 0`; 0 for 0

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| v_micro | int | 0 – 3.6 × 10⁹ | data file | A `sec` value (`dur_s`, `stun_s`, `cd_s`, the `cooldown_s` column) in micro-seconds |
| tick_rate | int | 10 | Sim core (constant) | Ticks per second |

**Output Range:** any positive duration lasts at least 1 tick; rounding is always up, so a 0.8 s stun is 8 ticks and a 0.05 s value is 1 tick. Used by Combat for every `sec` unit; defined here because it is part of the schema's unit contract.
**Example:** `stun_s=1.5` → 1,500,000 × 10 / 10⁶ = 15 ticks. `cooldown_s` 8 → 80 ticks.

### F9 — `skill_norm_ppm` (input to CA)

The skill_norm_ppm formula is defined as:

`skill_norm_ppm = floor( 1,000,000 × Σ skill_lv(s) / Σ max_lv(s) )` over the member's school skills that are live and have `rebirth_req ≤ r`; 0 for an unaffiliated member

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| skill_lv(s), max_lv(s) | int | — | calculated / data file | As above |
| r | int | 0 – 5 | calculated | The member's rebirth; secrets count only once they can be learned |

**Output Range:** 0 – 1,000,000. Denominator today 140 at r 0 (slots 1–10), 150 at r 1–2, 160 at r ≥ 3; never 0 for an affiliated member. Replaces the placeholder `skill_norm = min(1, level/cap) × 0.8` in `sim/model.py`. CA/PA (9) owns how it is weighted (0.25 in `ca_value`).
**Example:** r 0, levels summing to 70 → 500,000.

### F10 — event volume (Event bus F1, F4)

The skills_event_rate formula is defined as:

`events_per_tick ≈ N_members × skill_levels_per_member_hour / (3,600 × tick_rate)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| N_members | int | 1 – 200 | calculated | Members in the guild |
| skill_levels_per_member_hour | float | ≈ 2 (140 levels over ≈ 71 h to level 100) | calculated | Typical training rate |
| tick_rate | int | 10 | Sim core | Ticks per second |

**Output Range:** typical 50 members → ≈ 0.003 events/tick of 2101 (an upper bound, because one event covers several levels). Peak: one training call emits at most 12 × 2101 + 2 × 2102 per member; an offline aggregate award to 200 members could emit 2,800 in one call, so Offline (31) must surface them per its OQ-4, not in one tick. Ring cost: 2101 and 2103 are not logged; 2102 ≈ 4 per member per life (`ring_per_day` < 1 for 50 members).
**Example:** 50 members, 2 levels/h: 100 / 36,000 ≈ 0.0028 per tick.

## Edge Cases

*Systems-designer lens applied to C and D; all findings included.*

**Data and validation (validator errors unless stated):**
- **If an `effects` key is not in the R2 vocabulary**: ERROR naming the skill and key.
- **If a value does not parse as `c`, `b*L` or `a+b*L`, or has more than 6 decimals**: ERROR. `L` is the only variable allowed.
- **If a `spawn` key holds a token not in its list** (`summon`: `stone_guard`, `earth_titan`; `formation`: `ward`, `sealed_field`): ERROR. The tokens have no stat rows yet (Open Questions).
- **If a `chance` value at `max_lv` exceeds 1,000,000, or a `frac` value goes below −1,000,000**: ERROR (a 110% crit chance or −120% damage taken is a typo).
- **If a `trigger` key appears in an `active`/`ultimate` row, or a `shape` key is the only key of a row**: ERROR.
- **If a `passive`/`secret` row has `mp_cost` ≠ 0 or `cooldown_s` ≠ 0, or an `active`/`ultimate` row has `mp_cost` = 0 or `cooldown_s` = 0**: ERROR.
- **If a school's slot types do not follow the layout** (1–4 active, 5–8 passive, 9–10 ultimate, 11–12 secret): ERROR. Schools F4 relies on it.
- **If a prerequisite's `lv_req` is higher than the dependent skill's**: ERROR (the skill could never be learned at its own level).
- **If the prerequisite level `n` exceeds `gate(p, lv_req(s), rebirth_req(s))`**: WARNING, not error: the skill is first learnable a few levels after its `lv_req`. With the default steps this happens today for slot 3 (first learnable at member level 22, not 20), slot 4 (32, not 30) and slot 8 (45, not 40) in every school; slot 9 (`sk_kim1_09` needs `sk_kim1_04:10`, gate 11 at level 60) holds. Accepted as pacing; lowering `skill_level_step_active` to 2 and `_passive` to 3 removes all three (Tuning Knobs).
- **If `skill_level_step` or `skill_need_ppm` is outside its safe range**: ERROR (Tuning Knobs).

**Training:**
- **If an award is 0**: no change, no event.
- **If the member is unaffiliated**: the whole amount goes to the bank. On joining, the bank trains slots 1 and 5 at once (a level-10 recruit typically has ≈ 1,000 skill XP banked, enough for several levels of each).
- **If nothing is learnable** (every skill gated): the pool goes to the bank; excess over `skill_bank_cap_milli` is discarded. The bank is drained into the next award after the gate lifts. Gate changes without an award (Academy upgrade, rebirth) do not train by themselves.
- **If a pinned focus is not learnable**: auto-pick is used for that call; the pin stays.
- **If the focus is gated mid-pool**: the rest moves to the next auto-picked skill in the same call (R6 step 5); the pinned skill is not picked twice.
- **If one award raises a member several levels**: the gate uses the post-award level (R6), so a big offline award trains skills as if the levels had come first. A tick-by-tick run can differ slightly, because early fragments of XP met a lower gate and went to the bank (capped). This is the same class of drift as XP curve Edge Cases D and is measured by the Offline parity test.
- **If the member is capped at their level**: training continues on the pre-discard amount (R6 step 1).

**Carry, rebirth and school change:**
- **Degenerate: bank as a school-change bypass.** A member saves a large bank, changes school, and relearns the new tree instantly. Bounded by `skill_bank_cap_milli` (default 50,000 skill XP ≈ 5 high-tier levels), so the school-change cost (Schools F4) is still felt.
- **If carried levels break a prerequisite**: the levels stand; the dependent skill cannot rise until the prerequisite catches up (R5 item 4).
- **If a carried level is above the new skill's gate**: it stands (`Gated` state); the skill cannot rise until the gate passes it.
- **If a school change and a rebirth complete in the same tick**: Schools refuses to start a change while a rebirth is pending and Rebirth refuses while `Changing` (Schools Edge Cases), so they cannot.
- **If a skill row is retired** (Data layer R3) while members hold levels: levels and effects stay (retired rows resolve), but it cannot be trained further (R5 item 1 fails).

**Effects:**
- **If two passives sum one key past a sensible cap** (e.g. `crit_rate` from two skills plus gear above 100%): Skills does not clamp; Combat (10) owns caps (provisional).
- **If a skill's only damage-relevant key is a `shape` key** (e.g. `sk_kim1_01` is `taunt_s`+`aggro`): valid; the skill deals no damage.
- **If a `chance` key resolves to 0** at low levels (`cleanse_chance=0.02*L` at L 0 never applies; at L 1 is 20,000 ppm): draws at 0 ppm always fail; no special case.

## Dependencies

### Upstream (this system depends on)

| System (#) | Hard / soft | Interface | What this system takes |
|---|---|---|---|
| Data layer and content pipeline (3) | Hard | `skills` table typed and frozen, uid order; liveness (F2); `config.csv` knobs; validator hooks | All skill content. Needs a new value type `skill_expr` inside `map(...)` (Open Questions). The Data layer already lists Skills downstream |
| Schools and school change (20) | Hard | `school_id`; join signal (R3); change-complete with F4 carried levels (R5 step 1) | Which tree a member learns; levels after a change. Schools lists Skills downstream |
| XP and level pacing curve (22) | Hard (provisional hook) | Each award's `effective_milli` and post-award level, delivered synchronously (R6 step 1); `need_milli[0][t]` table (F3) | The training faucet and the cost curve. XP curve lists Skills downstream as Soft (`level` only); this GDD needs it Hard with the award hook (Open Questions) |
| Sim core and tick loop (1) | Hard | P1 command applier; `ctx.emit`; `tick_rate` | The focus command and event emission |
| Event bus and history log (42) | Hard | `register_type` for block 2100–2199; R3a emitter rules | Delivery of 2101–2103 |
| Member model (8) | Soft (provisional) | Storage of the R4 fields; level, rebirth, school read | Where the state lives |
| Rebirth and Ascension (23) | Soft (provisional) | Rebirth-complete signal with tier `skill_keep_pct` | F7 input |
| Guild and buildings (30) | Soft (provisional) | Academy level and its effects | R5 item 5, off in MVP |
| Command layer (5) | Soft | `set_skill_focus` registration | The player's only lever |

Deterministic RNG (2) is **not** a dependency (R11).

### Downstream (systems that depend on this one)

| System (#) | Hard / soft | Interface | What it gets |
|---|---|---|---|
| Combat (10) | Hard | R2 vocabulary and kinds; loadout and passive sheet (R9); F8 | Everything a member can do beyond the basic attack, without branching on skill IDs |
| CA/PA and traits (9) | Hard | F9 `skill_norm_ppm` | The skill term of CA |
| Rebirth and Ascension (23) | Hard | `set_levels` (R8), F7 | Skill retention on rebirth |
| Schools (20) | Hard | `set_levels` (R8) | Applying the carry |
| Utility AI (12), Party (13), Golden Boss (14) | Soft | Loadout (e.g. "has a revive", "has a taunt") | Scoring inputs |
| Offline progress (31) | Hard | Same training path via aggregate awards; F10 peak volume | Offline skill growth |
| Guild screens (39) | Soft | R4 state, F2 gate, F3 next cost, refusal reasons | The skill panel |
| Jianghu Chronicle / AI text (36), Analytics (37) | Soft | 2102 milestones, 2101 | Story beats and telemetry |
| Dev tooling (43) | Hard | `skill_table_hash`; validator rules | Parity and content checks |

**Bidirectional status.** Data layer (3) and Schools (20) list Skills. XP curve (22) lists Skills as Soft for `level`; the award hook makes it Hard and must be added there (not edited here). Combat, CA/PA, Rebirth and the rest are undesigned and must list Skills when designed. Systems index row 21 lists Data layer, Schools, XP curve; Sim core and Event bus added as hard upstream.

## Tuning Knobs

| Knob | Where | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `skill_xp_share_ppm` | `config.csv` (new) | 250,000 | 100,000 – 1,000,000 | Bank fills, gate always binds, PA stops mattering for skills | Skills lag levels; low-PA members never master a tree | `skill_need_ppm` (only the ratio matters), `skill_bank_cap_milli` |
| `skill_need_ppm` | `config.csv` (new) | 100,000 | 10,000 – 1,000,000 | Skills lag member levels; school change very costly | Gate always binds; training cost inert | `skill_xp_share_ppm` |
| `skill_level_step_active` / `_passive` / `_ultimate` / `_secret` | `config.csv` (new) | 3 / 5 / 4 / 4 | 1 – 20 | Skills freeze at low levels; ultimates barely grow | Gate inert; skills limited only by XP | F3 cost (`t` uses the step) |
| `skill_bank_cap_milli` | `config.csv` (new) | 50,000,000 | 0 – 500,000,000 | Bank bypasses school-change cost (Edge Cases) | Surplus XP lost; joining trains nothing at once | `school_change_skill_keep_pct` (Schools) |
| `academy_gate_enabled` | `config.csv` (new) | false until Vertical Slice (user decision 2026-11-16) | bool | — | — | Academy `teach_max_skill_lv` (`buildings.csv`) |
| `skill_teach_cap_unbuilt` | `config.csv` (new) | 2 | 0 – 20 | Academy upgrade feels pointless | 0 blocks every skill until the Academy is built | `academy_gate_enabled` |
| Per-skill `max_lv`, `lv_req`, `mp_cost`, `cooldown_s`, effect `a`/`b` | `skills.csv` | content | validator rules | — | — | Combat balance; S4 role DPS ±15% vs `sim_roles` |
| `skill_keep_pct` | `rebirth.csv` (Rebirth 23 owns) | 50–70, 100 | strictly increasing | — | — | F7 |
| `sim_params.skill_dps_bonus` | `sim_params.csv` | 0.4 | — | — | — | **Retired by S4**: replaced by real skills; remove after calibration |

## Visual/Audio Requirements

Progression category: optional; a brief note. No art bible exists; drafted from §6.1 and §12.
- **Level-up of a skill (2101):** a small text pop over the member in the world view, batched (one per member per second at most) so offline catch-up does not flood the screen.
- **Signature learned (2102):** a distinct glow and chime on the member and a Chronicle line; the one skill event that may interrupt with a toast.
- **Cast feedback** is Combat's and the world view's (38): each `kind` maps to one generic VFX family coloured by `element` (damage slash/projectile, dot tint, restore green rise, modifier aura, control icon, spawn summon), so 120 skills need ~8 families × 5 elements, not 120 bespoke effects. Element must not be shown by colour alone (icon shape per element).

📌 **Asset Spec** — run `/asset-spec system:skills` after the art bible is approved.

## Game Feel

Optional for Progression. Targets: a newly joined level-10 member shows a first skill within the first hunt trip (bank, Edge Cases); a skill level lands roughly every 30 minutes per member early, slowing with the gate; the first ultimate at level 60 is a moment, not a stat change, which is why 2102 is a milestone.

## UI Requirements

A **member skill panel** (Guild screens 39): the 12 slots in layout order with state (`Locked` with the unmet condition, `Learnable`, `Learned` level/max, `Gated` with the member level that lifts it, `Mastered`), a progress bar for each, the bank amount, and a focus pin per slot (one tap sends `set_skill_focus`; refusal shows the reason). Text fields must fit Vietnamese names, which run longer than English. A school-change or rebirth preview shows the levels each slot will keep (Schools F4, F7).

📌 **UX Flag — Skills**: run `/ux-design` for the member skill panel before writing epics.

## Cross-References

| This GDD | Other GDD | Their rule | Relationship |
|---|---|---|---|
| R8, Edge Cases | Schools and school change | F4 `carried_level`, R3 joining, R5 step 1 | Skills applies; conforms to "prerequisites gate only further learning" (Schools provisional assumption 4) |
| R1 slot layout, validator | Schools and school change | F4 Variables: shared slot layout | Skills makes it a validator rule |
| R6, F3, F4 | XP and level pacing curve | R4 `award`, F1 `need_milli`, F2 `effective_milli`, R7 | Reads the table; needs a new award hook (OQ-2) |
| R1 `wave`, R3 | Data layer and content pipeline | R3, R4 (types, conversion at load), R5 liveness, OQ-1 rename, OQ-4 skill names | Adds `skill_expr`; follows the rename |
| R10, F10 | Event bus and history log | R2, R3, R3a, F1, F4 | Block 2100–2199; typical events stated |
| R7 | Command layer | Command vocabulary and refusal contract | Registers `set_skill_focus` |
| R3 `chance` | Deterministic RNG | F6 `chance_ppm` | Chance values are ppm |
| F8 | Sim core and tick loop | R1 `tick_rate`, R13 integers only | Integer time conversion |

## Acceptance Criteria

*QA-lead lens applied: one or more criteria per rule and formula; boundaries included; logic criteria are automated unit tests (`tests/unit/skills/`), AC-20 is integration, AC-22 is a screenshot.*

- **AC-1 (R1, R2)** — **GIVEN** the shipped `data/`, **WHEN** the validator runs, **THEN** it exits 0 and every `effects` key of all 120 rows is in the vocabulary.
- **AC-2 (R2)** — **GIVEN** a fixture with `effects` `dmg_mul=1.2`, **WHEN** the validator runs, **THEN** it exits 1 naming the skill and key `dmg_mul`.
- **AC-3 (R3)** — **GIVEN** fixtures `dmg_mult=1.2*L+3`, `dmg_mult=L^2`, `dmg_mult=0.1234567`, **WHEN** the validator runs, **THEN** each fails with a grammar or precision error.
- **AC-4 (F1)** — **GIVEN** `sk_kim1_02`, **WHEN** resolved at L 1, 12, 20, **THEN** `reflect_pct` = 210,000, 320,000, 400,000 and `dmg_taken` = −250,000 at all three; at L 0 the skill has no effects.
- **AC-5 (R3, R12)** — **GIVEN** the Python and GDScript builds, **WHEN** both resolve all skills at all levels, **THEN** `skill_table_hash` is equal.
- **AC-6 (F2)** — **GIVEN** `sk_kim1_04` and member levels 29, 30, 50, 87, 200 at r 0, **WHEN** `gate` is computed, **THEN** it is 0, 1, 7, 20, 20.
- **AC-7 (F2)** — **GIVEN** `sk_kim1_10` (lv_req 100, ultimate), **WHEN** gate is computed at level 100 r 0 and level 120 r 1, **THEN** it is 1 and 6.
- **AC-8 (F3)** — **GIVEN** default knobs, **WHEN** `skill_need_milli(sk_kim1_01, 0)` and `(sk_kim1_04, 10)` are computed, **THEN** they are 1,030 and 10,540,400.
- **AC-9 (F4, R6)** — **GIVEN** a level-40 affiliated member with every skill learnable and no bank, **WHEN** an award of `effective_milli` 40,000 arrives, **THEN** exactly 10,000 milli is added to the F5 focus.
- **AC-10 (R6, capped)** — **GIVEN** a member capped at level 100 r 0, **WHEN** an award arrives, **THEN** XP curve discards it and Skills still trains with 25% of the pre-discard amount.
- **AC-11 (F5)** — **GIVEN** slots 1 at 6/20, 2 at 3/20, 5 at 2/10, others not learnable, **WHEN** the focus is auto-picked, **THEN** slot 2 is chosen; with slot 2 removed, slot 5.
- **AC-12 (R6 overflow)** — **GIVEN** the focus one level below its gate and a pool larger than that level's cost, **WHEN** training runs, **THEN** the focus gains exactly one level, the remainder trains the next auto-pick, and no skill is picked twice.
- **AC-13 (R6 bank)** — **GIVEN** every skill gated and a bank of 49,990,000 milli, **WHEN** a 40,000-milli award arrives, **THEN** the bank is 50,000,000 and 0 events are emitted.
- **AC-14 (R4, unaffiliated)** — **GIVEN** an unaffiliated level-9 member with 1,000,000 milli banked, **WHEN** they join a school at level 10, **THEN** on the next award slots 1 and 5 have level ≥ 1 and the bank has decreased.
- **AC-15 (R5 prereq)** — **GIVEN** `sk_kim1_02` (prereq `sk_kim1_01:3`) with slot 1 at 2 and member level 40, **WHEN** training runs, **THEN** slot 2 stays 0 until slot 1 reaches 3.
- **AC-16 (R5 Academy)** — **GIVEN** `academy_gate_enabled` true and an Academy at level 1 (`teach_max_skill_lv` 2), **WHEN** a level-80 member trains, **THEN** no skill exceeds level 2 and ultimates stay 0; with the knob false, the same member reaches the F2 gate.
- **AC-17 (R7)** — **GIVEN** an unaffiliated member, **WHEN** `set_skill_focus(member, 3)` is sent, **THEN** it is refused with `no_school`, 2103 is delivered, and state is unchanged; with slot 13 it is refused as out of range.
- **AC-18 (R8, F7)** — **GIVEN** levels [20,20,20,20,10,10,10,10,10,1,0,0], **WHEN** rebirth tier 1 (50%) completes, **THEN** levels are [10,10,10,10,5,5,5,5,5,0,0,0], progress is 0 and the bank is unchanged.
- **AC-19 (R8, Schools F4)** — **GIVEN** the Schools F4 example (level-80 `kim_1` → `moc_1`), **WHEN** the change completes, **THEN** `moc_1` slots 1, 5, 9 are 6, 3, 3 and focus is 0.
- **AC-20 (Integration, Combat)** — **GIVEN** a `moc_1` member with slot 9 (`revive_hp_pct`) at level 1 and a fallen ally, **WHEN** Combat runs a fight, **THEN** the revive fires once (`once_per_battle`) and Combat's code contains no reference to `sk_moc1_09` (grep check).
- **AC-21 (F6)** — **GIVEN** a `kim_2` member with slots 5 and 12 at 10, **WHEN** the passive sheet is built, **THEN** `sheet[atk_pct]` = 500,000; an active's `reflect_pct` never appears in any sheet.
- **AC-22 (UI)** — **GIVEN** a member with skills in each state, **WHEN** the skill panel opens, **THEN** a retained screenshot in `production/qa/evidence/` shows all five states and the focus pin.
- **AC-23 (F8)** — **GIVEN** `stun_s` 1.5, 0.8, 0.05 and `cooldown_s` 8, **WHEN** converted, **THEN** 15, 8, 1 and 80 ticks.
- **AC-24 (F9)** — **GIVEN** r 0 levels summing to 70 and an unaffiliated member, **WHEN** `skill_norm_ppm` is computed, **THEN** 500,000 and 0.
- **AC-25 (R10)** — **GIVEN** one award that raises slot 1 from 3 to 5 and slot 9 from 0 to 1 by training, **WHEN** events are read, **THEN** exactly two 2101 events (3→5, 0→1) and one 2102 milestone are emitted; a rebirth `set_levels` emits 2101 but no 2102.
- **AC-26 (R11)** — **GIVEN** the same save and award sequence, **WHEN** run twice, **THEN** all R4 fields are identical, and Skills calls no RNG `derive`.
- **AC-27 (Edge, validator)** — **GIVEN** fixtures with a passive `mp_cost` 5, a slot-3 row of type `passive`, `crit_rate=0.06*L` with max_lv 20, and `summon=dragon`, **WHEN** the validator runs, **THEN** each fails with its own error.
- **AC-28 (S4 balance, playtest/sim)** — **GIVEN** the balance simulator with real skills, **WHEN** each role's DPS is measured, **THEN** it is within ±15% of `sim_roles.csv`, and the §4.3 level-100 time moves ≤ 15% after recalibrating `xp_kill_coef` (GDD §20 S4).

**Coverage map.** R1: AC-1, 27. R2: AC-1, 2. R3: AC-3, 5. R4: AC-14. R5: AC-15, 16. R6: AC-9, 10, 12, 13. R7: AC-17. R8: AC-18, 19. R9: AC-20, 21. R10: AC-25. R11: AC-26. R12: AC-5. F1: AC-4. F2: AC-6, 7. F3: AC-8. F4: AC-9. F5: AC-11. F6: AC-21. F7: AC-18. F8: AC-23. F9: AC-24. F10: stated budget, checked in the Event bus spike (no own AC). Balance: AC-28.

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **RESOLVED (user decision 2026-11-16):** the MVP slice schools are `tho_1` (tank), `moc_1` (the only Wave 1 buffer/healer) and `hoa_2` (ranged DPS) — three roles, three elements, 3 × 12 = 36 skills. | User / producer | Closed |
| OQ-2 | **RESOLVED (consistency-check 2026-11-16):** XP curve R4 step 6 now calls `on_xp_awarded(member_id, effective_milli, new_level)` synchronously on every award (pre-discard amount, post-award level), in award order, live and offline; its Skills dependency row is Hard. | XP curve owner | Closed |
| OQ-3 | **Where the effect vocabulary lives**: a new `data/skill_effect_keys.csv` (key, kind, unit, signed) or the shared schema module (Data layer R4 "constants"). Also a new value type `skill_expr` for the Data layer. Schema change, not made autonomously. | Data layer / tools | Before S4 |
| OQ-4 | **PROVISIONAL: Combat (10)** — assumes Combat owns cast selection, mana, cooldowns, targeting, draws and caps on passive sums, executes by kind only, and maps `range` enums to distances. | Combat GDD | When Combat is designed |
| OQ-5 | **Summon and formation tokens** (`stone_guard`, `earth_titan`, `ward`, `sealed_field`) have no stat rows. Owner: Combat or Zones. | Combat | Before `tho_2` ships (Wave 2) |
| OQ-6 | **Monster abilities** (`monsters.csv` `ai_skills`: `bite`, `coil`, …) are bare tokens. Should they reuse this effect schema? Out of Skills' scope. | Zones and hunt (11) / Combat | Combat design |
| OQ-7 | **PROVISIONAL: Rebirth (23)** — assumes a rebirth-complete signal carrying the tier, after which Skills applies F7; ascension (100%) keeps all levels. | Rebirth GDD | When Rebirth is designed |
| OQ-8 | **PROVISIONAL: Member model (8)** stores the R4 fields; §4.1's `skills[{id,lv,xp}]` becomes per-slot arrays. | Member model | When designed |
| OQ-9 | **Trait / "ngộ tính" conditions** (§6.2 lists them as learning conditions) have no column. Deferred with traits (Vertical Slice). | CA/PA and traits (9) | Vertical Slice |
| OQ-10 | **Training defaults are first guesses** (share 25%, need 10%, steps 3/5/4/4, bank 50k XP). Calibrate in S4 against §4.3 and the ±15% role DPS target; retire `skill_dps_bonus`. | Dev tooling (43) / balance | S4 |
| OQ-11 | **Engine feasibility not checked.** NOT SOURCEABLE — the Scripting domain has no `docs/engine-reference/godot/modules/scripting.md` (or `core.md`); only int64 arithmetic is required, which Sim core R13 already relies on. | Technical director | Architecture |
| OQ-12 | **Skill display names** are missing (Data layer OQ-4, §17.2). | Localization (4) | Vertical Slice |
| OQ-13 | **RESOLVED (user decision 2026-11-16):** the Academy is not in MVP; `academy_gate_enabled` stays false until Vertical Slice. `skill_teach_cap_unbuilt` (default 2) is tuned when the Academy ships. | Guild and buildings (30) | Closed (tune at Vertical Slice) |
