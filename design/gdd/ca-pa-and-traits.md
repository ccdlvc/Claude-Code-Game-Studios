# CA/PA and Traits

> **Status**: In Design
> **Author**: Claude (design-system, autonomous batch run) — pending user review
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no game pillars written yet). Anchored to the candidate pillar in the systems index CD note: "every member is a person with a hidden ceiling".
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, `game-concept.md` or game brief exist to check against; re-run once pillars are written
> **Retrofit note**: a partial Python reference exists (`sim/formulas.py` `ca_value`, `sim/model.py` `Member.ca`, `tests/test_core.py`). This GDD specifies the target behaviour; the differences from that code are listed in Detailed Design R13.

## Summary

CA/PA and traits is what makes each guild member a person rather than a stat line. Every member has a fixed, hidden potential (PA, 0–200) that the player can only estimate, a current ability (CA, 0–200) computed from level, skills, gear and known traits, and up to three hidden traits that come to light over time and change how the member fights, earns, learns and behaves. It exists because the guild master's two decisions about people, "who do I take?" and "what could they become?", are the management core of the game (GDD §5).

> **Quick reference** — Layer: `Feature` · Priority: `MVP` (CA and PA estimate only; traits and exact-PA reveal in Vertical Slice) · Key deps: `Deterministic RNG, Data layer and content pipeline, Member model, XP and level pacing curve, Event bus and history log, Sim core and tick loop, Skills, Items and loot, Guild and buildings, Recruitment`

## Overview

This system owns three member properties and the rules for what the player may know about them. **PA** (potential ability) is an integer from 0 to 200, rolled once when a person is generated and never changed. It speeds XP growth (applied by the XP curve) and is the soft ceiling of CA. The player never sees PA directly: they see an **estimate**, a range and a star rating that narrow as the guild's Thám Tử Quán (Scout House) improves and as the member stays longer in the guild. The exact value is shown only through the paid Thiên Cơ Kính (one member) and Thiên Nhãn (every member) products, which change what the player sees and never what the member can do. **CA** (current ability) is an integer from 0 to 200 computed on demand from the member's level, skill levels, equipment tier and revealed traits; it is never stored. Once raw CA passes PA, further gains count at half rate, so a member's growth visibly flattens at their ceiling. **Traits** are 1–3 hidden characteristics per member, drawn from the 40 in `data/traits.csv`, each with effects (`xp_mult`, `drop_rate`, `leave_threshold` and so on), conflicts and a reveal condition. Traits act from the day the member arrives; revealing one only tells the player what was already true. The player interacts with this system indirectly: they read it on the recruitment and member screens, and they act on it by choosing whom to hire, keep, gear and rebirth. The system has no tuning-free numbers: every weight, width and threshold is a `config.csv` or building-data knob. Implementation choices (caching CA, storage layout) are left to an ADR.

## Player Fantasy

**The fantasy is the talent scout's eye: "I saw something in this one before anyone else did."**

*The moment.* A recruitment event offers three strangers. Two show three stars; the third shows two and a half, with a wide range of 74–150. The guild master takes the third on a hunch. Weeks later the Scout House reaches level 5, the range snaps to 128–164 and the stars climb to four. The gem was there all along; the player found it. The opposite moment matters as much: a four-star recruit whose CA gains halve at 120, because their ceiling has arrived, and the player decides whether to keep investing or let them go.

*People, not numbers.* A quiet member returns from the first Golden Boss and the screen says *"Phúc Tinh (Child of Fortune) revealed"*. That explains why their loot has always been better. Traits make the roster a cast of characters: the greedy one who asks for a raise, the loyal one who stays through bad times, the late bloomer who suddenly accelerates at level 50.

**What the design owes the player.**
- The estimate must be honest: the true PA is always inside the shown range, and the range never jumps around when viewed twice (R6, R7).
- Discovery must be earned by play, not by re-opening a screen or reloading a save (R7, Edge Cases).
- Paying for exact PA saves guesswork and never adds power (GDD §11.2 "không bán sức mạnh").
- A hidden trait is hidden knowledge, not a hidden rule: the member card shows how many traits remain unknown (R9).

*Pillar anchor:* none written. This section anchors to GDD §5 and §6.7, and to the candidate pillar "every member is a person with a hidden ceiling" from the systems index CD-SYSTEMS note. Re-check when pillars exist. `creative-director` lens applied in this session (autonomous run); candidate framings considered were "the talent scout's eye" (chosen), "raising a family" (overlaps the XP curve's fantasy) and "the gambler's draft" (works against the honest-estimate promise).

## Detailed Design

### Core Rules

Specialist lenses applied (Section 6 routing, row "Character systems"): **game-designer** — the decision is whom to hire and invest in, so the estimate must carry signal even in MVP, where no Scout House exists; **systems-designer** — CA must be integer and pure, because Utility AI, Party, Leaderboards and Ascension all read it and the leaderboard verifier replays it; the naive "PA + fixed noise" range leaks the exact PA as soon as the width changes once (two equations, one unknown), so the range is built as a nested chain (R7); **art-director** — the star and range readout and the reveal moment need a distinct visual beat (Visual/Audio); **narrative-director** — trait reveals are story beats and should reach the Jianghu Chronicle as milestones (R11). No conflict between the lenses needed a user decision.

**R1 — Ownership.** Member model (8) stores these fields on each member record (Member model R1 "storage is ours, values are theirs"); this system is their only writer:
- `pa` (int, 0 to `pa_max`), set once by `init_potential` (R2) and never changed afterwards, including by rebirth, school change or Ascension.
- `pa_key` (int, 1 – 2⁶³−1) — the estimate key Recruitment gave the person as a candidate (R2). It keys the F3 chain, so a candidate's range carries over unchanged when they are hired. It is separate from `member_id` because Member model issues `member_id` only at hiring (Member model R2).
- `traits` — a list of 0 to `max_traits` entries `{trait_id, revealed: bool}`, ordered by the trait's `uid` (Member model stores trait IDs; this system adds the `revealed` flag). Events and RNG keys use the trait's `uid`.
- `pa_lo`, `pa_hw` (ints) — the current shown estimate range `[pa_lo, pa_lo + 2·pa_hw]` (R6, R7).
- `pa_exact` (bool) — true once a Thiên Cơ Kính has been used on this member (R10).
- `joined_tick` is stored by Member model and read here (time in guild).

No other system computes CA, writes these fields, or reads `pa` for display. Systems that need PA for rules (XP curve F2, Items and loot drop scaling) read `pa` through Member model; UI reads only what R12 exposes.

**R2 — Candidates and creation.**
- `check_potential(pa, trait_ids) → ok | 951`. Refuses if `pa` is not an integer in 0…`pa_max`; the list has more than `max_traits` entries or a duplicate; any two traits conflict (each trait's `conflicts` list, checked in both directions); or a trait is not live (Data layer `content_live`). Recruitment (15) calls it on every candidate it generates; a refused candidate is a Recruitment bug.
- `candidate_view(pa_key, pa, trait_ids, snapshot) → {exact, lo, hi, half_stars, surface_trait}`. A pure function for the recruitment screen: the F3 range at the guild's current F2 width with `days = 0`, F4 stars, and R9's surface trait. Candidates hold no state in this system; Recruitment stores `{pa_key, pa, trait_ids}` and gives each candidate a `pa_key` that is unique in the save and not player-mutable (for example Recruitment's own candidate ordinal).
- `init_potential(member_id, pa_key, pa, trait_ids)`. Called by Member model at creation (Member model R8 step 3) and on loading a migrated save. It runs `check_potential` (refusing with 951 changes nothing, so Member model refuses the creation), then stores `pa`, `pa_key`, the traits (all hidden, except R9's surface trait), `pa_exact = false`, and builds the estimate (R7) at the current F2 width, which is the width the candidate was shown.
- How PA and traits are *rolled* (the PA distribution, the number of traits, tier odds) is owned by Recruitment (15), using RNG domain 8. In the MVP build Recruitment passes an empty trait list.

**R3 — CA is computed, never stored.** `ca(member_id)` returns an integer 0–`ca_max` from F1; `ca_milli(member_id)` returns the unrounded value in thousandths for consumers that sort or compare. CA is a pure function of the member's level, rebirth, skill levels, equipped item tiers, revealed traits and `pa`, and of content tables fixed at boot. It uses no RNG and no clock. Any consumer may call it at any time in any phase.

**R4 — CA inputs.**
- *Level:* `level / cap[rebirth]`, with `cap` from the XP curve (22, R3). A member at their cap has a full level term at every rebirth.
- *Skills:* `skill_norm_ppm` from Skills F9: the member's skill levels over the `max_lv` total of their school's live skills with `rebirth_req ≤ r`. A member with no school has a skill term of 0. This system owns the weight; Skills owns the ratio.
- *Equipment:* the sum of the `tier` of each equipped item over `equip_slots × tier_max`, where `tier_max` is the highest `tier` of any live `equip` row in `items.csv`, computed at boot. An empty slot contributes 0. Enhancement level does not count yet (OQ-6).
- *Traits:* the sum of tier points (`trait_points_common` / `_rare` / `_epic`) of **revealed** traits over `max_traits × trait_points_epic`. Hidden traits do not count, so CA cannot be used to infer them.
- *PA:* the member's birth `pa`. The rebirth "effective PA" bonus (`growth_bonus` in `rebirth.csv`) is an XP-speed bonus applied only by the XP curve (F2 `pa_eff`); it does not raise the CA ceiling.

**R5 — PA is a soft ceiling.** When raw CA exceeds PA, only `ca_over_pa_ppm` (50% today) of the excess counts (F1). With the default weights, a member's maximum CA is `100 + PA/2`: PA 0 can reach CA 100, PA 100 reaches 150, PA 200 reaches 200. The flattening is visible on purpose: watching CA gains halve is one way the player learns where the ceiling is.

**R6 — The estimate half-width.** For each member (and each candidate), the half-width `h` of the PA range is F2: it starts from the Scout House level (`pa_error` in `bld_scout` effects, or `pa_hw_no_scout` without the building), shrinks with whole game days in the guild, and shrinks further while the guild has a member with the Keen Eye trait (`t_keen_eye`) revealed. It never goes below `pa_hw_min`. The shown half-width `pa_hw` only ever decreases: `pa_hw = min(pa_hw, h)`. If `h` rises (a Keen Eye member leaves), the shown range stays where it was.

**R7 — The estimate range is a nested chain, fixed per member.** For each integer half-width `w` from `pa_hw_no_scout` (the widest range any source can produce) down to 0, the range `[lo_w, lo_w + 2w]` is defined by F3: one `randint` draw from RNG domain 9 (`pa_estimate`) with event key `[member_id, w]`, choosing a position that stays inside the previous (wider) range, inside 0–`pa_max`, and contains the true PA. The step is a uniform-preserving coupling, so away from the ends of the scale the true PA is equally likely to sit anywhere in the shown range at every width (no drift to the middle or the ends). Consequences:
- The true PA is always inside the shown range.
- Each narrower range lies inside every wider one, so no sequence of views tells the player more than the current range.
- The range at a given width depends only on the world seed, the member and the width, never on when or in what order the width shrank. Reloading a save, or upgrading the Scout House earlier or later, gives exactly the same ranges.
- Viewing never changes anything; there is nothing to re-roll.

When `pa_hw` decreases from `w_old` to `w_new`, the system draws `lo` for each width `w_old − 1 … w_new` in that order (one event per width) and stores `pa_lo = lo_{w_new}`, `pa_hw = w_new`. The first estimate (R2) draws from `pa_hw_no_scout` down to the candidate's F2 width.

*Rejected alternatives* (systems-designer lens, checked by a 10,000-member simulation in this session): a fixed per-member offset `PA + u·h` leaks the exact PA from two views at different widths; independent draws per width leak through intersecting ranges; a plain uniform choice among the up-to-3 nested positions drifts the true PA toward the range ends (≈ 48 / 5 / 47% by thirds at width 6). The F3 coupling keeps ≈ 33 / 33 / 33% at widths 38, 14 and 6 for PA 100.

**R8 — Stars.** The star rating is `half_stars / 2`, where `half_stars` is 0–10 (F4). It is computed from the **midpoint of the shown range**, not from the true PA; GDD §5.1's `round(PA/20)/2` is applied to the midpoint. When `pa_exact` is true or the Thiên Nhãn entitlement is held (R10), it is computed from the true PA. (Computing stars from the true PA would place PA within ±10 for free, which is narrower than the best Scout House range below level 7 and would make the Scout House pointless.)

**R9 — Traits.**
- A member has 0 to `max_traits` traits (3 today), with no conflicting pair. Generation rules are Recruitment's (R2); the only later way to add a trait is R9b.
- **Effects apply from arrival, revealed or not.** A hidden Lucky trait raises drops from the first hunt. Revealing a trait changes the player's knowledge and the trait term of CA (R4), never the trait's effects.
- **Visible count.** The member card shows one slot per trait, with `?` for hidden ones, so the player always knows how many unknowns remain.
- **Surface trait.** At `init_potential`, if the member has any trait of category `personality`, the one with the lowest `trait_uid` starts revealed. This is the "tính cách bề mặt" a candidate shows (GDD §6.7).
- **`trait_mod_ppm(member_id, effect_key) → int`.** The sum, over all the member's traits (hidden and revealed), of the effect's value scaled to millionths (for example `xp_mult=+0.06` gives 60,000; `leave_threshold=-15` gives −15,000,000). Unknown keys return 0. This system does not interpret effects other than its own (`pa_reveal_hint`, `scout_range_narrow`); each consumer system owns the meaning of its keys (Interactions table) and clamps its own result.
- **R9b — Adding a trait** (Ngộ Đạo Đài teaching, Vertical Slice or later): `add_trait(member_id, trait_uid)` refuses with 954 if the member already has `max_traits` traits, already has that trait, or the trait conflicts with one they have. A taught trait is revealed. The teaching rules (which tiers, cost, time) are owned by Guild and buildings (30) and are an open question (OQ-5).

**R10 — Exact PA.**
- **Thiên Cơ Kính** (`item_pa_lens`): the command `use_pa_lens(member_id)` is validated in P1. It refuses with 952 if the subject is not a guild member (candidates hold no state here, so a lens cannot be used on them; GDD §11.5 says "1 thành viên"), with 953 if `pa_exact` is already true (no lens is spent), and with 955 if Items and loot (26) reports no lens in guild storage. Otherwise Items removes one lens, this system sets `pa_exact = true` permanently (it survives rebirth, leaving and returning) and emits 902.
- **Thiên Nhãn** (`item_pa_eye`, permanent): the simulation never stores it. Entitlement (32) supplies an injected snapshot with `exact_pa_all: bool`. While it is true, R12 shows every member's and candidate's exact PA. If it becomes false (a refund), display falls back to each member's estimate, except members with `pa_exact`.
- Neither product changes any simulation value. A guild with Thiên Nhãn and one without, given the same seed and commands, produce identical simulation state.

**R11 — Trait reveal.** A hidden trait is revealed by the first of these that applies. All are deterministic except the rebirth pick.
1. **Its reveal condition** (`reveal` column):
   - `time:Nd` — when `days_in_guild ≥ reveal_days(N)` (F5), checked at each game-day boundary.
   - `level:N` and `event:level_N` — when the member's level reaches N (XP curve event 2201, new level `c ≥ N`).
   - `event:skill_learn` — the member learns a skill (Skills, 21).
   - `event:golden_boss` — the member takes part in a Golden Boss fight (14).
   - `event:rare_drop` — the member's hunt produces a rare-or-better drop (Items and loot, 26).
   - `event:party_hunt` — the member completes a hunt trip in a party of 2 or more (Party, 13).
   - `event:leave_guild` — the member leaves the guild (Retention, 16); the trait is revealed as they go.
   - `building:<id>` — the guild owns that building at level 1 or higher, checked when it is built and when the member joins.
   A condition kind not in this list is a validator ERROR (Data layer R8).
2. **Rebirth.** On a rebirth whose `rebirth.csv` rewards include `trait_slot_reveal=1` (rebirths 1 and 4 today), one hidden trait is revealed: `choice` (RNG F5) over the member's hidden traits ordered by `trait_uid`, RNG domain 18 (`trait_reveal`), key `[member_id, rebirth_no]`. No hidden trait: nothing happens.
3. **Teaching** (R9b) reveals the taught trait.

A revealed trait stays revealed for the member's lifetime, including after leaving and returning. Each reveal emits 903.

**R12 — What the UI may read.** `pa_view(member_id, snapshot) → {exact: bool, lo, hi, half_stars}`: when `pa_exact` or `snapshot.exact_pa_all`, `exact = true`, `lo = hi = pa` and stars from PA; otherwise the stored range and F4 on its midpoint. `traits_view(member_id) → list of {trait_uid or none, revealed}` in `trait_uid` order, with hidden entries carrying no uid. `ca(member_id)`. The UI never reads `pa` or hidden trait uids directly; Guild screens (39) and Realtime world view (38) go through these.

**R13 — Retrofit against `sim/`.** The Python reference must change to match this GDD before it serves as the parity source:
- `ca_value` uses floats and hard-coded weights (0.40/0.25/0.25/0.10, 0.5); F1 uses integers and `config.csv` knobs. The results agree to within 1 milli on the reference examples.
- `Member.ca` uses a stand-in skill term `0.8 × level/cap` (skills are not simulated yet), a hard-coded `tier / 21`, and `traits_score / 9` with `traits_score` never set. The stand-in stays in the balance simulator until Skills (21) exists in `sim/`, and is labelled as such in the simulator report.
- `LEVEL_CAP` is imported from `sim/data.py`; it moves to the XP curve's `cap[r]` (XP curve R3).
- There is no PA estimate, trait or reveal code in `sim/` yet (GDD §20 prompt S1 places generation in `sim/recruit.py`).

### States and Transitions

**PA knowledge (per member).**

| State | Meaning | Transition | Trigger |
|---|---|---|---|
| `Estimated(w)` | Range of half-width w shown | → `Estimated(w′)`, w′ < w | F2 gives a smaller h at a day boundary, a Scout House level-up, a Keen Eye reveal or join (R6) |
| `Estimated(w)` | — | → `Exact` | `use_pa_lens` accepted (R10) |
| `Exact` | `pa_exact = true`; true PA shown | none (terminal) | — |

`Estimated(w)` never moves to a larger w. Thiên Nhãn is a display overlay over either state, not a state.

**Trait (per trait on a member).**

| State | Transition | Trigger |
|---|---|---|
| `Hidden` | → `Revealed` | Reveal condition met, rebirth pick, or teaching (R11) |
| `Revealed` | none (terminal) | — |

A member never loses a trait in this system. Whether a returning member ("cố nhân", GDD §6.11) keeps all traits is Jianghu's (17) to define; the assumption here is yes (OQ-7).

### Interactions with Other Systems

| System (#) | Direction | Data | Owner of the interface |
|---|---|---|---|
| Deterministic RNG (2) | this → RNG | Domain 9 `pa_estimate`, key `[pa_key, w]`, one `randint` per event (F3). Domain 18 `trait_reveal`, key `[member_id, rebirth_no]`, one `choice` per event | RNG owns the draws; this GDD owns keys and draw order (RNG R5–R7) |
| Data layer (3) | Data → this | `traits` table (tier, category, effects, conflicts, reveal), `bld_scout` and `bld_academy_trait` effects, `rebirth.csv` rewards, `items.csv` tier, `config.csv` knobs; `content_live` | Data layer owns loading and liveness; this system owns what trait rows mean |
| Member model (8) | both | Storage of `pa`, `pa_key`, `traits` (with `revealed`), `pa_lo`, `pa_hw`, `pa_exact`; `init_potential` from `create_member` (Member model R8); reads `level`, `rebirth`, `school_id`, equipment, `joined_tick` | Member model owns storage; this system is the only writer of its fields |
| XP and level pacing curve (22) | XP → this | `cap[r]` for the level term; event 2201 for level reveals. This → XP: `pa` (read via Member model) for F2 `growth_ppm` | XP curve owns `cap` and the growth multiplier |
| Skills (21) | Skills → this | Sum of current skill levels and sum of `max_lv` for the member's school; skill-learned event | Skills (PROVISIONAL) |
| Items and loot (26) | both | Equipped item tiers; rare-drop event; lens removal from storage. This → Items: `pa` and `trait_mod_ppm(drop_rate / rare_drop)` | Items owns drop scaling by PA (GDD §4.2) |
| Recruitment (15) | both | Recruitment → this: `check_potential`, `candidate_view` with `pa_key`, PA and traits it rolled. This → Recruitment: `max_traits`, conflict rules, the surface trait | Recruitment owns generation and its distribution (GDD §20 S1) |
| Guild and buildings (30) | Buildings → this | Scout House level and `pa_error`/`pa_reveal_hint` semantics; Ngộ Đạo Đài `trait_reveal_speed`; building-completed event | Buildings owns levels; this system owns what `pa_error` and `trait_reveal_speed` do |
| Rebirth and Ascension (23) | Rebirth → this | Rebirth event with `rebirth_no`; reads `ca` for the Ascension gate (CA ≥ 180) | Rebirth owns the gate |
| Event bus (42) | this → bus | Block 900–999 (F6); subscribes to 2201 and the provisional events above | Event bus owns delivery |
| Sim core (1) | — | P1 validator/applier for `use_pa_lens`, `add_trait`; P5 handler for day boundaries and queued recompute; P6 subscriber | Sim core owns phases |
| Entitlement (32) | Entitlement → UI read | `exact_pa_all` in the injected snapshot | Entitlement; the simulation never writes it |
| Utility AI (12), Party (13) | this → them | `ca`, `trait_mod_ppm` (party_synergy, bond_gain, solo_xp_mult, flee_hp_threshold…) | Consumers own the meaning |
| Retention (16) | this → Retention | `trait_mod_ppm` for loyalty_decay, leave_threshold, salary_demand, negotiation_success, return_chance…; leave event → reveal | Retention owns the meaning |
| Combat (10) | this → Combat | `trait_mod_ppm` for atk_pct, hp_pct, def_pct, dodge, crit_rate, atk_speed | Combat owns the meaning |
| Gold economy (27), Market (29), Crafting (28) | this → them | gold_mult, sell/buy_price_mult, spend_rate, craft_quality… | Consumers |
| Leaderboards (35) | this → 35 | `ca` (deterministic, replayable) | 35 |
| Guild screens (39), Realtime view (38) | this → UI | `pa_view`, `traits_view`, `ca`; events 901–904 | UI reads only (R12) |

**Trait effect keys that no designed system owns yet:** `xp_mult`, `skill_xp_mult`, `xp_mult_below_L50`, `xp_mult_above_L50`. The XP curve (R5) applies only PA and rebirth bonuses member-side, so trait XP modifiers have no owner (OQ-2).

## Formulas

All arithmetic is 64-bit signed integer; `//` is floor division of non-negative operands. Ratios are in parts per million (ppm, 1,000,000 = 1.0). This matches the XP curve and RNG F6 conventions so that Python and GDScript agree exactly.

### F1 — `ca_milli`

The ca_milli formula is defined as:

`l = min(1,000,000, level × 1,000,000 // cap[r])`
`s = skill_norm_ppm` (Skills F9; 0 for a member with no school)
`e = min(1,000,000, equip_tier_sum × 1,000,000 // (equip_slots × tier_max))`
`t = revealed_points × 1,000,000 // (max_traits × trait_points_epic)`
`raw = ca_max × (w_l·l + w_s·s + w_e·e + w_t·t) // 1,000,000,000`
`ca_milli = raw` if `raw ≤ pa × 1,000`, else `pa × 1,000 + (raw − pa × 1,000) × ca_over_pa_ppm // 1,000,000`
`ca = ca_milli // 1,000`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| level | int | 1 – 200 | calculated (Member model) | Current level |
| cap[r] | int | 100 – 200 | calculated (XP curve R3) | Level cap at the member's rebirth tier |
| skill_norm_ppm | int ppm | 0 – 1,000,000 | calculated (Skills F9) | Skill levels over the `max_lv` total of the school's live skills with `rebirth_req ≤ r` |
| equip_tier_sum | int | 0 – equip_slots × tier_max | calculated (Member model, `items.csv`) | Sum of equipped items' `tier` |
| equip_slots | int | 4 | constant (Member model slots: weapon, armor, ring, amulet) | Slots counted |
| tier_max | int | ≥ 1 (21 today) | calculated at boot (`items.csv`) | Highest live equip tier |
| revealed_points | int | 0 – max_traits × trait_points_epic | calculated | Sum of tier points of revealed traits |
| max_traits | int | 1 – 5 (3) | data file (`config.csv`) | Trait slots per member |
| trait_points_common / _rare / _epic | int | 1 – 10 (1 / 2 / 3) | data file (`config.csv`, new) | CA points per revealed trait by tier |
| w_l, w_s, w_e, w_t | int ppm | 0 – 1,000,000; must sum to 1,000,000 | data file (`config.csv`, new: `ca_w_level_ppm` 400,000, `ca_w_skill_ppm` 250,000, `ca_w_equip_ppm` 250,000, `ca_w_trait_ppm` 100,000) | Weights of the four terms (GDD §5.1) |
| ca_max | int | 200 | data file (`config.csv`) | Top of the CA scale |
| pa | int | 0 – 200 | calculated (R1) | Birth potential |
| ca_over_pa_ppm | int ppm | 0 – 1,000,000 (500,000) | data file (`config.csv`, new) | Share of raw CA above PA that counts |

**Output Range:** `ca_milli` 0 to 200,000; `ca` 0 to 200. Maximum CA is `pa + (200 − pa) × 0.5` = `100 + pa/2` with defaults. With `ca_over_pa_ppm = 0`, PA is a hard cap; at 1,000,000, PA has no effect on CA.
**Example:** level 50, rebirth 0 (cap 100) → `l = 500,000`. `skill_norm_ppm = 300,000` (for example 42 of 140 at rebirth 0). Gear tiers 5, 5, 4, 4 → 18 of 84 → `e = 214,285`. One revealed rare trait → 2 of 9 → `t = 222,222`. Weighted sum = 200,000,000,000 + 75,000,000,000 + 53,571,250,000 + 22,222,200,000 = 350,793,450,000; `raw = 200 × 350,793,450,000 // 10⁹ = 70,158`. With PA 100: `ca = 70`. With PA 60: `60,000 + 10,158 × 500,000 // 10⁶ = 65,079` → `ca = 65`. (The float reference gives 70.159, agreeing to within 1 milli.)

**Boundaries checked.** All terms 0 → 0. All terms at 1,000,000 → raw 200,000; PA 0 → 100,000; PA 200 → 200,000. `level > cap` cannot occur (XP curve R4) and is clamped by `min` anyway. Largest intermediate: 200 × 10¹² = 2×10¹⁴, far under 2⁶³. Division by zero is prevented by validator rules: `tier_max ≥ 1`, `max_traits ≥ 1`, `trait_points_epic ≥ 1`, `cap ≥ 1`; an unaffiliated member has `s = 0` (Skills F9). Weights not summing to 1,000,000 is a validator ERROR (otherwise CA could exceed 200 or never reach it).

**Consequence for Ascension (GDD §6.10).** Phi Thăng requires CA ≥ 180. With default knobs that needs `100 + pa/2 ≥ 180`, so **PA ≥ 160**, and every term at maximum. Only top-potential members can ever ascend. This is flagged to Rebirth and Ascension (OQ-4).

### F2 — `pa_half_width`

The pa_half_width formula is defined as:

`base = pa_hw_no_scout` if no Scout House, else `pa_error[min(scout_lv + hint, scout_lv_max)]`
`cut = min(pa_time_cut_max_ppm, days × pa_time_cut_per_day_ppm)`
`h = max(pa_hw_min, base × (1,000,000 − cut) × (1,000,000 − narrow) // 10¹²)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| scout_lv | int | 0 – 8 | calculated (Guild and buildings) | Thám Tử Quán level; 0 = not built |
| hint | int | 0 – 1 | data file (`traits.csv` `t_keen_eye` `pa_reveal_hint=+1`) | Extra effective Scout level while the guild has a revealed Keen Eye member; 0 without one. Not stacked |
| scout_lv_max | int | 8 | data file (`building_meta.csv` `bld_scout` `max_lv`) | Highest Scout level; `hint` cannot exceed it, and gives nothing without a Scout House |
| pa_error[n] | int | 1 – 100 (34 … 6) | data file (`buildings.csv` `bld_scout` effects) | Half-width at Scout level n |
| pa_hw_no_scout | int | 20 – 100 (38) | data file (`config.csv`, new) | Half-width with no Scout House; one step wider than level 1. Also the top of the F3 chain |
| days | int | ≥ 0 | calculated | Whole game days in the guild, `(tick − joined_tick) // (86,400 × tick_rate)`; 0 for candidates |
| pa_time_cut_per_day_ppm | int ppm | 0 – 100,000 (20,000) | data file (`config.csv`, new) | Width removed per day in the guild |
| pa_time_cut_max_ppm | int ppm | 0 – 900,000 (500,000) | data file (`config.csv`, new) | Most width time can remove (reached at 25 days) |
| narrow | int ppm | 0 – 500,000 (150,000) | data file (`t_keen_eye` `scout_range_narrow=+0.15`) | Keen Eye narrowing; 0 without one |
| pa_hw_min | int | 1 – 20 (2) | data file (`config.csv`, new) | Narrowest range without a lens (width 5 values) |

**Output Range:** `pa_hw_min` to `pa_hw_no_scout`: 38 for an MVP candidate (range of 77 values), 6 at Scout 8, 2 at best (Scout 8, 25+ days, Keen Eye: `6 × 0.5 × 0.85 = 2.55 → 2`).
**Example:** Scout level 3 (`pa_error` 26), 10 days in guild (`cut = 200,000`), Keen Eye revealed (`hint` → level 4, `pa_error` 22; `narrow = 150,000`): `h = 22 × 800,000 × 850,000 // 10¹² = 14`.
**Boundaries checked.** `days = 0` → no cut. `cut` capped below 1,000,000 by the validator so `h` never multiplies by 0 (the floor `pa_hw_min` covers it anyway). Any `pa_error` above `pa_hw_no_scout`, or `pa_hw_no_scout` above `pa_max / 2`, is a validator ERROR (F3 starts the chain at `pa_hw_no_scout`, so every reachable width must be at or below it).

### F3 — `pa_estimate_chain`

The pa_estimate_chain formula is defined as:

`lo_W = randint(max(0, pa − 2·W), min(pa_max − 2·W, pa))`, with `W = pa_hw_no_scout`, key `[pa_key, W]`
For `w = W − 1 … 0`, key `[pa_key, w]`: `u = pa − lo_{w+1}`, `n = 2w + 1`, `v = (u × n + randint(0, n − 1)) // (n + 2)`, `lo_w = pa − v`
Shown range at width `w`: `[lo_w, lo_w + 2w]`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| pa | int | 0 – 200 | calculated (R1) | True potential |
| pa_max | int | 200 | data file (`config.csv`) | Top of the PA scale |
| W | int | = `pa_hw_no_scout` (38) | data file (`config.csv`) | Width where the chain starts; every F2 base must be ≤ W (validator) |
| w | int | 0 – W | calculated | Half-width of a range in the chain |
| u, v | int | 0 – 2w + 2, 0 – 2w | calculated | Position of PA above the lower bound, before and after the step |
| lo_w | int | 0 – pa_max − 2w | calculated | Lower bound at width w |
| pa_key | int | 1 – 2⁶³−1 | calculated (Recruitment, stored by R1) | Key component, fixed from the candidate stage onward; never player-mutable |

**Output Range:** every range contains `pa`, lies within 0–`pa_max`, and is nested in the range one width above it: `u − v` is always 0, 1 or 2 (because `v ≥ u·n // (n+2)` and `v ≤ u`), so the new range moves inside the old one. The map `(u, r) → u·n + r` is a bijection onto `0 … (n+2)·n − 1`, so if `u` is uniform over its `n + 2` values, `v` is exactly uniform over its `n` values: the true PA's position in the range stays uniform at every width, apart from the scale-edge effect below. Each event consumes exactly one `randint`. A member uses at most `W + 1` events in their lifetime.
**Example:** PA 150, `W = 38`: `lo_38 = randint(74, 124)`, say 100 → [100, 176], midpoint 138, 3.5 stars. At w = 37: `u = 50`, `n = 75`, `v = (3,750 + randint(0, 74)) // 77` ∈ {48, 49} → [101, 175] or [102, 176]. The chain always ends at [150, 150] at w = 0, which is never shown without a lens because `pa_hw_min ≥ 1`.
**Edge behaviour.** Within `W` of either end of the scale the first range is pressed against 0 or 200, so the midpoint understates a PA near 200 and overstates one near 0 while the range is wide (PA 200 at w = 38 always shows [124, 200], 8 half-stars). This is accepted: a top talent's stars rise as the Scout House improves, which is the discovery the fantasy promises.

### F4 — `pa_half_stars`

The pa_half_stars formula is defined as:

`half_stars = (m + 10) // 20`, where `m = pa` if exact (R10), else `m = lo + pa_hw`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| m | int | 0 – 200 | calculated | True PA (exact) or the midpoint of the shown range |
| half_stars | int | 0 – 10 | calculated | Stars × 2 |

**Output Range:** 0 to 10 (0 to 5 stars in half steps). Half rounds up: m = 10 → 1, m = 9 → 0.
**Example:** range [112, 188] → m = 150 → 160 // 20 = 8 → 4 stars.

### F5 — `reveal_days`

The reveal_days formula is defined as:

`reveal_days(N) = ceil(N × 1,000,000 / (1,000,000 + speed))` computed as `(N × 1,000,000 + 1,000,000 + speed − 1) // (1,000,000 + speed)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| N | int | 1 – 60 (3 – 7 today) | data file (`traits.csv` `reveal` = `time:Nd`) | Base days |
| speed | int ppm | 0 – 800,000 | data file (`buildings.csv` `bld_academy_trait` `trait_reveal_speed`) | Ngộ Đạo Đài speed-up; 0 if not built |

**Output Range:** 1 to N days. **Example:** N = 7 (`t_loyal`), Ngộ Đạo Đài level 5 (speed 500,000): `ceil(7 / 1.5) = 5` days.

### F6 — Event volume (Event bus F1, F4)

This system registers the block **900–999** (`ca_pa_event_type_block`, block = system number × 100):

| ID | Name | Fields | Logged | Milestone | ring_per_day |
|---|---|---|---|---|---|
| 901 | `pa_estimate_narrowed` | a member_id, b lo, c hi, d exact(0/1) | no | no | 0 |
| 902 | `pa_exact_revealed` | a member_id, b pa | yes | no | 10 |
| 903 | `trait_revealed` | a member_id, b trait_uid, c cause (1 condition, 2 rebirth, 3 taught) | yes | yes (subject_slot 1) | 0 |
| 904 | `trait_added` | a member_id, b trait_uid | yes | yes (subject_slot 1) | 0 |

**Output Range:** 901 fires at most once per member per day boundary plus once per Scout House level-up; with the max-roster fixture this is well under 1 event per tick on average and at most one roster's worth (≤ the member cap) in a single tick. 902 is bounded by lens stock (5, `pa_lens_stock_cap`) plus purchases; 10/day is a generous peak. 903 and 904 are bounded by `max_traits` per member per lifetime. Candidates are not guild members, so events about them carry `subject_slot` content but are 901 only (not logged), satisfying Event bus R3a.

## Edge Cases

Systems-designer lens applied to C and D (autonomous run).

**PA and CA**
- **If `init_potential` receives PA outside 0–200 or a non-integer**: refused with 951; the candidate is not created. Recruitment's generator is at fault.
- **If a save is edited so `pa` changes**: the next load re-validates the range only; the estimate chain is rebuilt from `pa_hw_no_scout` down to the stored `pa_hw`, so a changed PA gets a fresh, consistent range. Leaderboard verification (35) will reject the summary, because replay uses the saved state hash. Local tampering is otherwise accepted (single-player save).
- **If raw CA equals PA × 1,000 exactly**: the first branch applies (`raw ≤ pa × 1,000`); no halving.
- **If a member has no school** (below level 10): skill term 0; CA comes from level, gear and traits.
- **If the member wears an item of a retired or non-live tier**: its `tier` still counts; `tier_max` is computed from live rows only, so F1 clamps `e` at 1,000,000.
- **If equipment data has no live equip rows** (`tier_max` would be 0): validator ERROR; the game does not boot.
- **If content changes `tier_max`** (a new tier 22 item ships): every member's CA drops slightly at the next boot. Accepted; content updates already bump the content hash (Data layer R7) and leaderboard summaries carry it.

**Estimate**
- **If the player reloads to re-roll the estimate**: the chain is keyed by `[pa_key, w]` only, and `pa_key` is fixed when the candidate is generated; the same ranges appear (RNG save-scum rule).
- **If the player upgrades the Scout House earlier or later, or in different steps**: same ranges at each width (path independence, R7).
- **If a Keen Eye member leaves**: F2's `h` rises; `pa_hw` stays at its smaller value (R6). The range never widens.
- **If a Scout House is demolished or loses levels** (if Guild and buildings ever allows it): same as above; never widens.
- **If several members have Keen Eye**: `hint` and `narrow` apply once (not stacked).
- **If `pa_hw` drops by many widths at once** (Scout House 0 → 8 offline): up to `pa_hw_no_scout` draws in one P5 handler for each member; at most 38 × member cap `randint` calls, done once.
- **If a lens is used while Thiên Nhãn is active**: accepted (the lens makes the knowledge permanent, independent of the entitlement); UI should warn first (UI Requirements).
- **If a lens is targeted at a candidate**: refused with 952 and no lens is spent; the candidate screen offers no lens button.
- **If Thiên Nhãn is refunded**: display reverts to estimates; no simulation value changes.
- **If a returning former member comes back** (GDD §6.11): same `member_id`, so the stored range, `pa_exact` and reveals are kept (PROVISIONAL, OQ-7).

**Traits**
- **If two conflicting traits are passed to `init_potential`**: refused with 951. Conflicts are checked both ways, so a one-sided `conflicts` entry still blocks the pair (the validator already warns about one-sided entries).
- **If a member's trait is retired from content later**: it stays on the member and keeps applying; it is never offered to new candidates. A trait row deleted outright breaks old saves and is forbidden after launch (Data layer R6).
- **If a trait's reveal condition can never happen** (for example `building:bld_x` for a building not in this wave): the trait stays hidden until a rebirth pick or teaching reveals it. The validator WARNs when a `reveal` building is not live.
- **If a reveal condition and a rebirth pick fall in the same tick**: the condition is processed first (P6 subscriber), then the rebirth pick in P5 of the next tick chooses among the traits still hidden.
- **If a member gains 30 levels in one offline award**: one 2201 event with `c` = new level; every `level:N` with N ≤ c reveals in that batch.
- **If `event:leave_guild` reveals a trait** (`t_nostalgic`): 903 is emitted while the member is still a guild member (before Retention removes them), so the milestone subject is valid (Event bus R3a).
- **If the member already holds `max_traits` traits and a teaching is attempted**: refused with 954; nothing is spent (the teaching owner must check before charging).
- **Degenerate strategy check**: viewing, reloading and re-ordering upgrades cannot shift any draw; CA cannot be raised by hiding or revealing traits except by revealing them (which only adds). Firing and re-hiring the same person is not possible except through the Jianghu return path, which keeps all fields. No loop gives unbounded gain.

## Dependencies

### Upstream (this system depends on)

| System (#) | Hard / soft | Interface | Status |
|---|---|---|---|
| Deterministic RNG (2) | Hard | Domains 9 and 18; `randint` (F4), `choice` (F5) | Designed (Needs Revision) — conforms |
| Data layer (3) | Hard | `traits`, `buildings`, `rebirth`, `items`, `config` tables; `content_live`; validator rules | Designed — conforms; adds validator rules (R11 conditions, weight sum, `pa_error` ≤ `pa_hw_no_scout`) |
| Member model (8) | Hard | Storage of R1 fields; `create_member` calls `init_potential` (R8); level, rebirth, school, equipment, `joined_tick` | Designed in parallel (`member-model.md`) — conforms; it must add `pa_key`, `pa_lo`, `pa_hw`, `pa_exact` and the `revealed` flag to its field table (OQ-1) |
| XP and level pacing curve (22) | Hard | `cap[r]`; event 2201 | Designed — conforms |
| Sim core (1) | Hard | P1 commands, P5 handler, day length from `tick_rate` | Designed (Needs Revision) |
| Event bus (42) | Hard | `register_type` block 900–999, `subscribe`, `ctx.emit` | Designed (Needs Revision) |
| Skills (21) | Hard for CA | `skill_norm_ppm` (Skills F9); skill-learned event | Designed in parallel (`skills.md`) — conforms to F9; skill-learned event PROVISIONAL |
| Items and loot (26) | Hard for CA, Soft for reveal | Item tiers; rare-drop event; `item_pa_lens` in guild storage (Items R9) | Designed in parallel (`items-and-loot-tables.md`) — conforms (it reads true PA and `trait_mod_ppm(m, rare_drop)`); rare-drop event and `item_pa_eye` handling open (OQ-12, OQ-13) |
| Guild and buildings (30) | Soft | `effect(bld_scout, pa_error)`, `effect(bld_academy_trait, trait_reveal_speed)`; building-completed event | Designed in parallel (`guild-and-buildings.md`) — lists Recruitment, not this system, as the `pa_error` reader (OQ-17); building-completed event PROVISIONAL |
| Recruitment (15) | Soft (caller) | Calls `check_potential`, `candidate_view`; supplies `pa_key` | Not designed — PROVISIONAL |
| Rebirth and Ascension (23) | Soft | Rebirth event (`member_id`, `rebirth_no`) | Not designed — PROVISIONAL |
| Golden Boss (14), Party (13), Retention (16) | Soft | Participation, party-trip and leave events for reveals | Not designed — PROVISIONAL |
| Entitlement (32) | Soft (UI only) | `exact_pa_all` snapshot | Designed — conforms (Entitlement R2, F1) |

The systems index row 9 lists RNG, Member model and Data layer. XP curve, Sim core, Event bus, Skills and Items and loot are also hard here; the row's Depends On is updated to add them.

### Downstream (systems that depend on this one)

| System (#) | Hard / soft | What it gets |
|---|---|---|
| XP curve (22) | Hard | `pa` for F2 growth (read through Member model) |
| Recruitment (15) | Hard | `check_potential`, `candidate_view`, `max_traits`, conflict rules |
| Utility AI (12), Party (13) | Hard | `ca`, `trait_mod_ppm` |
| Retention (16) | Hard | `trait_mod_ppm` (behaviour keys), leave reveal |
| Combat (10), Items and loot (26), Gold economy (27), Crafting (28), Market (29) | Soft | `trait_mod_ppm` for their keys; `pa` for drop scaling (26) |
| Rebirth and Ascension (23) | Hard | `ca` for the Phi Thăng gate |
| Leaderboards and anti-cheat (35) | Hard | Deterministic `ca` |
| Guild screens (39), Realtime world view (38) | Hard | `pa_view`, `traits_view`, `ca`, events 901–904 |
| AI text layer (36), Jianghu Chronicle | Soft | 903/904 milestones, revealed traits |
| Quests and achievements (25) | Soft | `ca` for "reach a CA milestone" (GDD §11.4) |
| Dev tooling (43) | Hard | Parity vectors for F1, F3, F5 |

**Bidirectional status.** RNG lists this system for domains 9 and 18 ✓. Data layer lists this system for `traits` ✓. XP curve lists this system for `cap[r]` ✓ (it does not list the reverse `pa` read; it lists Member model as the source of `pa`, which is consistent). All other systems above are undesigned and must list this system when designed.

## Tuning Knobs

All knobs are read at boot; none changes during play. "New" keys are proposed additions to `config.csv`, following the XP curve's precedent; the Data layer validator gets their ranges.

| Knob | Location | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|---|
| `ca_w_level_ppm` / `_skill_` / `_equip_` / `_trait_` | `config.csv` (new) | 400k / 250k / 250k / 100k | each 0–1,000,000, sum exactly 1,000,000 | One term dominates; others feel pointless | A term below ~50k makes that investment invisible in CA | Each other (sum rule) |
| `ca_over_pa_ppm` | `config.csv` (new) | 500,000 | 250,000 – 750,000 | PA barely matters; everyone can ascend | PA is a hard wall; low-PA members feel dead | Ascension gate (PA ≥ 160 at default) |
| `trait_points_common/rare/epic` | `config.csv` (new) | 1 / 2 / 3 | 1 – 10, non-decreasing | — (normalised by epic) | — | `ca_w_trait_ppm` |
| `max_traits` | `config.csv` | 3 | 1 – 5 | Roster noise; reveals take forever | Members feel generic | Recruitment generation |
| `pa_hw_no_scout` | `config.csv` (new) | 38 | 20 – 100, ≥ every `pa_error` | MVP candidates are a coin flip; more draws per member | Scout House loses value; validator ERROR if below `pa_error[1]` | `bld_scout` `pa_error`; top of the F3 chain |
| `pa_error[1..8]` | `buildings.csv` `bld_scout` | 34 … 6 | strictly decreasing, ≥ `pa_hw_min` | — | Exact-PA products lose value | Lens/Eye pricing (GDD §11.5) |
| `pa_time_cut_per_day_ppm` | `config.csv` (new) | 20,000 | 0 – 100,000 | Scout House irrelevant for long-stay members | Time in guild does nothing | `pa_time_cut_max_ppm` |
| `pa_time_cut_max_ppm` | `config.csv` (new) | 500,000 | 0 – 900,000 | Ranges collapse to `pa_hw_min` for everyone | — | Above |
| `pa_hw_min` | `config.csv` (new) | 2 | 1 – 10 | Lens worth more | 1 makes a 3-value range: near-exact for free | Lens value |
| `t_keen_eye` `pa_reveal_hint`, `scout_range_narrow` | `traits.csv` | +1, +0.15 | 0–2, 0–0.5 | One trait replaces the Scout House | Trait is pointless | `pa_error` |
| Trait `reveal` days | `traits.csv` | 3 – 7 days | 1 – 60 | Traits never seen in a session's memory | No mystery | `trait_reveal_speed` |
| `trait_reveal_speed` | `buildings.csv` `bld_academy_trait` | 0.1 – 0.8 | 0 – 0.8 | — | — | Reveal days (F5) |

Knobs owned elsewhere and only read here: `pa_max`, `ca_max` (this GDD registers them; `config.csv`), `cap[r]` (XP curve), `tick_rate` (Sim core), the PA distribution (Recruitment), `pa_lens_weekly_free` and `pa_lens_stock_cap` (Quests / Items).

## Visual/Audio Requirements

No art bible exists yet (`design/art/art-bible.md` absent); drafted from GDD §12.4 (pixel 2D, paper-doll, code-drawn minimal fallback). `art-director` lens applied in this session.

- **Stars**: 5 star glyphs with half-star states, readable at 16 px; shape-distinct (filled / half / outline) so they never rely on colour alone.
- **Range bar**: a horizontal 0–200 bar with the shown range as a band; when exact, the band collapses to a single marker with a distinct "seal" glyph (Thiên Cơ Kính motif).
- **Narrowing (901)**: the band animates from old to new bounds (≤ 400 ms) the next time the member card is open; no global popup.
- **Exact reveal (902)**: a short lens-flare/eye-opening effect on the member card and a soft chime.
- **Trait reveal (903)**: the `?` slot flips to the trait icon with a brush-stroke reveal; toast "*[Name]*: *[Trait]* revealed" and a distinct, low-priority "discovery" sting (below combat and boss cues in the mix). Epic traits get a gold variant.
- **CA at ceiling**: when `raw > pa × 1,000`, the CA number shows a subtle "ceiling" tick mark on its bar (no number leak: it only appears once the member is past their PA, which the player could already infer from growth).
- 40 trait icons are needed (one per trait, by category colour family plus a unique glyph).

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:ca-pa-and-traits` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

- **Responsiveness**: `pa_view`, `traits_view` and `ca` answer within the same frame the card opens (pure reads; target < 0.05 ms per member).
- **Weight of discovery**: narrowing and reveals are shown the next time the player looks, not interrupted mid-play; a trait reveal is the only one that toasts, and at most one toast per 2 s (batched "+2 more").
- **Honesty**: two views of the same card always show the same numbers. No animation may suggest a range is still "rolling".
- **Ceiling**: a member's CA bar slows visibly near PA; the player should be able to say "they've peaked" from the bar alone after a few days of play (playtest question PT-1).

## UI Requirements

- **Candidate card** (Recruitment, MVP): CA, stars, range "lo–hi", school, surface trait if any, `?` slots for the rest (Vertical Slice).
- **Member card**: CA with bar and ceiling tick, stars and range bar (or exact value with seal), trait slots in `trait_uid` order with revealed icon + name + effect summary, hidden `?`, days until the next time-based reveal is **not** shown (would leak the trait's N).
- **Use Thiên Cơ Kính**: button on the member card (not on candidate cards) with confirmation, showing the lens count; extra warning text when Thiên Nhãn already shows the value.
- **Roster list**: sortable by CA and by shown stars; sorting by hidden PA is impossible by construction.
- Accessibility: stars and the range are also stated as text ("3.5 stars, 74–150"); no information carried by colour alone; strings in `i18n/` (Localization, 4) with room for Vietnamese diacritics.

> **📌 UX Flag — CA/PA and traits**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for each screen or HUD element this system contributes to **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD | Refers to | Element | Source |
|---|---|---|---|
| R4, F1 | `xp-and-level-pacing-curve.md` R3 | `cap[r]` | XP curve |
| R4 | `xp-and-level-pacing-curve.md` F2 | `pa_eff`, `growth_bonus_ppm` (not used in CA) | XP curve |
| R11 | `xp-and-level-pacing-curve.md` R6 | Event 2201 (one per award, `c` = new level) | XP curve |
| R7, R11, F3 | `deterministic-rng.md` R4–R7, F4, F5 | Domains 9 and 18, keys, draw order, save-scum rule | RNG |
| R2, R11 | `data-layer-and-content-pipeline.md` R4, R5, R6, R8 | `content_live`, `uid` order, map columns, validator tiers | Data layer |
| F6 | `event-bus-and-history-log.md` R3, R3a, R6 | Type block, milestone rules, subscriber contract | Event bus |
| R1, R11 | `sim-core-and-tick-loop.md` R1, R2 | `tick_rate`, phases P1/P5/P6 | Sim core |
| R4 | `schools-and-school-change.md` | Member without a school below `school_join_level` | Schools |
| R1, R2 | `member-model.md` R1, R2, R5, R8 | Field storage, `member_id` issued at hiring, four equipment slots, `create_member` calling field owners | Member model |
| R4, F1 | `skills.md` F9 | `skill_norm_ppm` | Skills |
| R10, OQ-12, OQ-13 | `items-and-loot-tables.md` R4, R9, F (`member_luck_milli`) | PA and `rare_drop` in luck; `item_pa_lens` as a guild-held item (`item_pa_eye` is an entitlement, not an item) | Items and loot |
| F2, F5 | `guild-and-buildings.md` `effect(building_id, key)` | `bld_scout` `pa_error`, `bld_academy_trait` `trait_reveal_speed` | Guild and buildings |
| — | `JX1_Tycoon_GDD.md` §4.2, §5, §6.7, §6.10, §6.11, §11.5, §20 S1 | Source design | Source GDD v1.0 |

## Acceptance Criteria

`qa-lead` lens applied: every rule and formula has at least one criterion; logic criteria are automated (unit tests in `tests/unit/ca_pa_traits/`, plus Python parity vectors); UI criteria need screenshots in `production/qa/evidence/`.

**CA (F1, R3–R5) — Logic**
- **AC-1**: **GIVEN** level 50 / cap 100, `skill_norm_ppm` 300,000, gear tiers 5,5,4,4 (tier_max 21), one revealed rare trait, default knobs, **WHEN** `ca_milli` is computed with PA 100 and PA 60, **THEN** the results are 70,158 and 65,079, and `ca` is 70 and 65, identically in Python and GDScript.
- **AC-2 (boundaries)**: **GIVEN** every term at 0, **THEN** `ca = 0`; **GIVEN** every term at maximum, **THEN** PA 0 gives 100, PA 160 gives 180, PA 200 gives 200.
- **AC-3**: **GIVEN** raw exactly equal to `pa × 1,000`, **THEN** `ca_milli = raw`.
- **AC-4**: **GIVEN** a member with one hidden epic trait, **WHEN** it is revealed, **THEN** `t` rises from 0 to 333,333 and CA rises; before the reveal, CA equals that of the same member with no traits.
- **AC-5**: **GIVEN** a member at rebirth 2 with `growth_bonus`, **THEN** CA uses birth `pa`, not `pa_eff`.
- **AC-6 (validator)**: **GIVEN** `ca_w_*` summing to 999,999, or `tier_max` 0, or `pa_error[1]` above `pa_hw_no_scout`, **THEN** the validator reports ERROR and the game does not boot.
- **AC-7**: **GIVEN** 10,000 calls of `ca` on a fixed roster in random call orders and phases, **THEN** results are identical (pure function) and the RNG draw counter is unchanged.

**Estimate (F2–F4, R6–R8) — Logic**
- **AC-8**: **GIVEN** Scout level 3, 10 days, Keen Eye revealed, **THEN** `h = 14`; **GIVEN** no Scout House, a candidate, **THEN** `h = 38`; **GIVEN** Scout 8, 30 days, Keen Eye, **THEN** `h = 2`.
- **AC-9**: **GIVEN** 10,000 member IDs at each PA in {0, 1, 100, 199, 200} and a fixed world seed, **WHEN** the chain is built to each width 38…0, **THEN** every range contains PA, stays within 0–200, and is nested in the range one width above.
- **AC-10 (path independence)**: **GIVEN** one member, **WHEN** `pa_hw` goes 38 → 6 directly, and in another run 38 → 30 → 14 → 6, **THEN** the final `pa_lo` is identical; **WHEN** the save is reloaded and the Scout upgrade is done one day later, **THEN** the same ranges appear.
- **AC-11 (never widens)**: **GIVEN** `pa_hw = 12` with a Keen Eye member present, **WHEN** that member leaves, **THEN** `pa_hw` stays 12 and no 901 is emitted.
- **AC-12 (stars)**: **GIVEN** range [112, 188], **THEN** half-stars = 8; **GIVEN** midpoint 9 / 10, **THEN** 0 / 1; **GIVEN** `pa_exact` and PA 150, **THEN** half-stars = 8 regardless of the range.
- **AC-13 (uniformity, statistical)**: **GIVEN** PA 100, 10,000 member IDs, `pa_hw = 38`, **THEN** the true PA falls in each third of the shown range in at least 20% of members (the estimate is not biased toward one end).
- **AC-14 (draw count)**: **GIVEN** a new candidate whose F2 width is 26 (Scout level 3), **THEN** exactly 13 domain-9 events are derived, keys `[id, 38] … [id, 26]`, one draw each, and the resulting `pa_lo` matches the Python parity vector.

**Traits (R9, R11, F5) — Logic / Integration**
- **AC-15**: **GIVEN** `init_potential` with `t_greedy` and `t_generous`, or 4 traits, or PA 201, **THEN** it refuses with 951 and no member/candidate exists.
- **AC-16**: **GIVEN** a member with hidden `t_lucky`, **WHEN** `trait_mod_ppm(id, "drop_rate")` is called, **THEN** it returns 100,000 before and after reveal.
- **AC-17**: **GIVEN** a member with `t_proud` (personality) and `t_lucky`, **WHEN** created, **THEN** `t_proud` is revealed and `t_lucky` hidden; `traits_view` shows one named entry and one `?`.
- **AC-18 (time, F5)**: **GIVEN** `t_loyal` (`time:7d`) and Ngộ Đạo Đài level 5, **WHEN** 4 game days pass, **THEN** it is hidden; **WHEN** the 5th day boundary passes, **THEN** it is revealed and 903 (c = 1) is emitted once.
- **AC-19 (level)**: **GIVEN** `t_late_bloomer` (`level:50`) at level 30, **WHEN** one award raises the level to 60, **THEN** the trait is revealed in that tick's P6 batch.
- **AC-20 (rebirth, Integration)**: **GIVEN** a member with two hidden traits, **WHEN** rebirth 1 completes, **THEN** exactly one is revealed by domain 18 key `[id, 1]`, and the same seed always reveals the same one; **WHEN** rebirth 2 completes, **THEN** none is revealed (no `trait_slot_reveal`).
- **AC-21 (leave)**: **GIVEN** hidden `t_nostalgic`, **WHEN** the member leaves, **THEN** 903 is emitted with the member still a guild member at emit time, and `milestones_for(id)` contains it.
- **AC-22 (add_trait)**: **GIVEN** 3 traits, or a conflicting trait, **WHEN** `add_trait` is called, **THEN** 954 and no change.

**Exact PA (R10, R12) — Integration / UI**
- **AC-23**: **GIVEN** one lens in storage, **WHEN** `use_pa_lens` targets a member, **THEN** the lens count drops by 1, `pa_exact` is true, 902 is emitted, and `pa_view` returns `exact = true, lo = hi = pa`; **WHEN** used again, **THEN** 953 and the lens count is unchanged.
- **AC-24 (no power sold)**: **GIVEN** two identical saves, one with `exact_pa_all = true` and lenses used on three members, **WHEN** both run 100,000 ticks with the same commands except the lens uses, **THEN** all simulation state other than `pa_exact` flags and lens counts is identical.
- **AC-25 (UI never reads PA)**: **GIVEN** a code search of Guild screens and Realtime view, **THEN** no read of `pa` or hidden `trait_uid` exists outside `pa_view`/`traits_view` (code review checklist).
- **AC-26 (UI, screenshot)**: candidate card and member card show stars, range text and trait slots as specified, in Vietnamese and English; screenshots retained in `production/qa/evidence/`.

**Events (F6) — Integration**
- **AC-27**: **GIVEN** the bus sealed, **THEN** types 901–904 exist with the flags in F6; **WHEN** a Scout House upgrade narrows 40 members, **THEN** at most 40 901 events are emitted, in one tick.

**Performance**
- **AC-28**: **GIVEN** the max-roster fixture, **WHEN** a day boundary and a Scout House 0 → 8 upgrade fall in the same tick, **THEN** this system's P5 handler stays within the Sim core per-phase budget (measured by the profiler).

**Gaps flagged by the QA lens:** "feels like discovery" (Player Fantasy) and "the player can tell a member has peaked" are playtest questions, not ACs (PT-1, PT-2 in Open Questions).

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | Member model (8, designed in parallel) lists `pa` and `traits[]` (trait IDs) only. It needs `pa_key`, `pa_lo`, `pa_hw`, `pa_exact` and a per-trait `revealed` flag in its field table, all written only by this system | Member model GDD | Consistency pass |
| OQ-2 | Trait XP modifiers (`xp_mult`, `skill_xp_mult`, `xp_mult_below/above_L50`) have no owner: XP curve R5 applies only PA and rebirth bonuses member-side. Either XP curve adds traits to F2, or source-side callers apply them | XP curve owner + Skills | Before Vertical Slice |
| OQ-3 | PROVISIONAL: Skills (21) emits a skill-learned event with `member_id` (for `event:skill_learn` reveals). `skill_norm_ppm` itself is Skills F9. Until `sim/` simulates skills, the balance simulator keeps the `0.8 × level/cap` stand-in | Skills GDD | Consistency pass |
| OQ-4 | Ascension (CA ≥ 180) is reachable only with PA ≥ 160 at default knobs. Is that the intent, or should the gate or `ca_over_pa_ppm` change? | Rebirth and Ascension (23) + user | When 23 is designed |
| OQ-5 | Ngộ Đạo Đài teaching (`teach_rare`, `teach_epic`): cost, time, which traits, whether negative traits can be removed. Scope as GDD §6 defines it; not designed here | Guild and buildings (30) | Vertical Slice |
| OQ-6 | Should enhancement level (+1…+20) count in the equipment term of CA? Today only tier counts | Enhancement (24) + user | Vertical Slice |
| OQ-7 | PROVISIONAL: Jianghu (17) — a returning member keeps `member_id`, PA estimate, `pa_exact`, all traits and reveals | Jianghu GDD | Full Vision |
| OQ-8 | "Tinh Mắt of the bang chủ" (GDD §5.1): the bang chủ is the player, not a member. Assumed: any current member with Keen Eye revealed counts. Alternative: a designated "advisor" slot | User | Before Vertical Slice |
| OQ-9 | All traits add CA points by tier, including negative ones (`t_unlucky`, `t_lazy`). A per-trait `ca_points` column would fix it but is a schema change — not made in this batch | User / Data layer | Before Vertical Slice |
| OQ-10 | PROVISIONAL: Data layer converts `traits.csv` `effects` decimals to integer ppm at load (exact decimal parse, no float), and `traits.csv` gains `uid` and `wave` columns (Data layer R5, R6) | Data layer | Next Data layer revision |
| OQ-11 | PROVISIONAL: Offline progress (31) calls this system's day-boundary handler once per game day crossed, and forwards level-up/participation events, so offline reveals match live play | Offline GDD | When 31 is designed |
| OQ-12 | PROVISIONAL: Items and loot (26) emits a rare-drop event naming the member (for `event:rare_drop`); its own text says rare drops are not announced individually. Its luck formula already reads true PA and `trait_mod_ppm(m, rare_drop)`, which this GDD confirms | Items GDD | Consistency pass |
| OQ-13 | **RESOLVED (consistency-check 2026-11-16):** Entitlement (32) injects `exact_pa_all` (its R2/F1, from the `pa_eye` ownership record); Items R9 no longer treats `item_pa_eye` as a storage item. Consumable lenses (`item_pa_lens`) still enter the sim as storage items through IAP's `grant_store_item` | Entitlement / IAP / Items | Closed |
| OQ-14 | Lenses work on guild members only (GDD §11.5 "1 thành viên"; candidates hold no state). Should candidates be allowed too? That would need Recruitment to store a per-candidate exact flag | User | Before Alpha |
| OQ-17 | Guild and buildings (30) lists Recruitment as the reader of `bld_scout` `pa_error`; this system also reads it (F2) for member ranges. Its Interactions table should list CA/PA and traits (9) | Guild and buildings GDD | Consistency pass |
| OQ-15 | PROVISIONAL: Golden Boss (14), Party (13), Retention (16), Rebirth (23), Guild and buildings (30) emit participation / party-trip / leave / rebirth / building-completed events with `member_id` | Those GDDs | When designed |
| OQ-16 | No engine reference exists for the Scripting domain (`docs/engine-reference/godot/modules/` has no `scripting.md`); feasibility not checked against the pinned engine. The design uses only int64 arithmetic | Technical director | Architecture |
| PT-1 | Playtest: can players tell a member has peaked from the CA bar within a few days? | QA / user | Vertical Slice playtest |
| PT-2 | Playtest: does an MVP candidate range of ±38 still carry enough signal to make the 1-of-3 pick interesting? | QA / user | MVP playtest |
