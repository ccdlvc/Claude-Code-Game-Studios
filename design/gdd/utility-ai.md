# Utility AI

> **Status**: Designed (pending independent `/design-review`)
> **Author**: user + design-system (autonomous batch run; decisions logged)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: none (no `game-pillars.md`); anchored to `JX1_Tycoon_GDD.md` §6.4, §6.12, §9.1
> **Creative Director Review (CD-GDD-ALIGN)**: CONCERNS (accepted) 2026-11-16 — no pillars exist; checked against GDD §1/§9.1 and this GDD's Player Fantasy (see Open Questions OQ-9)

## Summary

Utility AI is the scorer that lets guild members run themselves: given a hunting group it rates every ground it may enter and names the best one; given a member and a shop it names the gear worth buying; and it gives Party a score for how well a set of members fits together. It holds no state, takes no randomness and applies nothing: the Member state machine and Party act on what it returns. It exists because the game is an idle tycoon (GDD §1, §10): the guild must keep hunting sensibly while the player is busy elsewhere or away, and the player's orders must always win over it.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Zones and hunt trips, Member model, CA/PA and traits, Schools, Combat (element_mult), Gold economy, Items and loot, Member state machine (PROVISIONAL), Party (PROVISIONAL)`

## Overview

Utility AI (system 12) is a library of pure scoring functions inside the headless simulation core. It answers three questions, each with one function: **which ground should this group hunt** (`choose_ground`, F1), **what gear should this member buy now** (`choose_gear`, F2, the reference `auto_gear` policy moved out of the Member model), and **how good is this roster as a party** (`composition_score`, F3, the primitive Party 13 uses to form hunting parties and Golden Boss temporary teams). Every function is integer arithmetic over data it is handed; it registers no tick handler, emits no events, saves nothing and draws no random numbers. The caller applies the result: the Member state machine (41) inside Sim core phase P2, Party (13) when it forms groups, Offline progress (31) when it re-picks grounds between slices. AI decisions are not commands (Command layer R10); a player's direct order is, and it overrides the AI for that member until the order ends.

*Data layer and player impact.* On the data side the system owns about a dozen `ai_*` keys in `config.csv` and nothing else. On the player side it is the reason a guild left alone keeps levelling at the calibrated pace (GDD §4.3, ≈71 h to level 100 for the standard party): F1 reproduces the balance simulator's `pick_ground` exactly for that party, so the measured pacing is the pacing the player gets.

*Scope.* In: ground scoring, gear purchase choice, party-fit scoring, the score breakdown that UI and the AI text layer read. Out: party formation and disbanding (Party 13), member states and when to ask the AI (Member state machine 41), the trip itself (Zones and hunt 11), purchases and equipping (Gold economy 27, Items 26, Member model 8), adaptive difficulty (§9.1, not in MVP — OQ-5), needs such as hunger and fatigue (their owners add considerations later — OQ-3).

## Player Fantasy

**The master who delegates.** *The moment:* the player opens the map after ten minutes on the recruitment screen and sees every party already out, each on a ground that fits its level, the Kim swordsman's party on the Mộc grounds where his counter bonus shows in every hit, and the healer-less pair of newcomers one ground lower than the strongest party would go. Nobody stood idle while the player was busy. When the player taps a party and asks *why here?*, the suggestion panel shows the reasons in plain terms (level fit, element edge, danger without a healer), and they match what the player would have chosen.

What it asks of the design: decisions that are **legible** (every score comes with its breakdown, R8), **sensible at a glance** (level fit dominates; element and danger only shift between nearby grounds, F1), **never in the way** (a player order wins at once and the AI does not fight it, R6), and **the same whether or not the player is watching** (no camera LOD on decisions, R7).

Two other framings were considered and not chosen. "The roster as a machine" (optimisation: the player tunes AI weights) needs player-facing knobs the GDD does not ask for and would make the weights a balance exploit. "Living characters with wants" (members pick by personality) needs the needs system (§6.4 hunger, fatigue) and Retention, which are not MVP; it is kept as the extension path (OQ-3). This framing was assigned to this system by the Command layer GDD (its Player Fantasy, framing 3).

*Creative-director lens applied in this session, not as a spawned agent.*

## Detailed Design

### Core Rules

*Specialist lenses applied (Section 6 routing, row "AI, pathfinding, behavior"): **game-designer** — the decision that matters to the player is "where does the party go"; everything else is bookkeeping, so F1 gets the depth and F2 stays a retrofit. **ai-programmer** — utility scoring over a closed option set, evaluated only on a state change (idle), never per tick; no perception, no planning, no behaviour tree, because the option set is small (≤ 45 grounds) and every option is fully known. **systems-designer** — integers only, ties broken by `uid`, weights as data, and a parity target against the reference simulator.*

**R1 — A pure scorer.** Utility AI registers no Sim core handler (like Combat R1), owns no saved state, registers no Event bus block and has no RNG domain draws (R5). Each function is a pure function of its arguments and the boot content tables. The same inputs give the same output in Python and GDScript (AC-1).

**R2 — Three functions.**

| Function | Called by | When | Returns |
|---|---|---|---|
| `choose_ground(group, view) → GroundChoice` | Member state machine (41) in P2; Offline progress (31) between slices | A hunting group (1–5 members, from Party 13) is ready to start a trip | The best eligible ground's `uid`, or `none`, plus a breakdown (R8) |
| `choose_gear(member, wallet_gold, catalog) → [Purchase]` | Member state machine (41) during the town part of a trip (Selling or Resting) | Once per trip close, per member | An ordered list of `{slot, item_uid, price}` (F2), possibly empty |
| `composition_score(roster, target_element) → CompositionScore` | Party (13), including Golden Boss temporary teams (§6.13) | Whenever Party evaluates a candidate roster | An integer score in ppm plus a breakdown (F3) |

**R3 — `choose_ground`: options and eligibility.** The options are every ground row. A ground is a **candidate** only if every condition of Zones and hunt R2 holds for the group: content live, guild level, every member's `rebirth ≥ rebirth_req`, room for the whole group (R4 below), and every member eligible (R3 of Zones, reported by Member state machine 41). Utility AI applies these checks itself, through the queries Zones exposes, so that it never proposes a start that Zones would refuse. The level range is not a gate (Zones R2); it is the level-fit consideration of F1. Among candidates the highest F1 score wins; an exact tie goes to the **lowest ground `uid`** (R5). With no candidate, the result is `none` and the caller keeps the group idle (R9).

**R4 — Capacity inside one tick.** The `view` argument carries `occupancy(g)` as Zones reports it **plus** the members of groups the caller has already chosen a ground for earlier in the same P2 pass. The caller asks for groups in ascending `party_id` (the order Zones processes starts in P3, Zones R4) and adds each chosen group to the view before asking for the next one. Two groups therefore never both pick the last places of one ground in the same tick, and the starts Zones receives are never refused for capacity (refusal code 14) unless something outside the AI changed occupancy between P2 and P3.

**R5 — No randomness.** Exact ties are broken by lowest content `uid` (grounds, items), which is also what the reference does (Python `max` returns the first maximum in table order, and tables are in `uid` order). RNG domain 11 `ai_tiebreak` (Deterministic RNG R4) stays reserved for this system and unused; the RNG GDD already allows this fallback ("without RNG ties fall back to lowest ID first"). Using a draw would add a key layout and a parity vector for no player-visible gain.

**R6 — Player orders win.** A player's direct order to a member (a host command owned by Member state machine 41, Command layer R10) sets an override. While the override holds, the caller does not ask Utility AI for that member's job; a "hunt at ground g" order uses ground `g` directly, and its refusals come from Zones. If a member with an override is in a group, the caller (Party 13 / MSM 41) decides whether the group follows the order or the member leaves the group — Utility AI is not involved. When the override ends, the member is scored again at the next decision point.

**R7 — The camera never changes a decision.** Decisions are made on state changes (a group ready to start, a trip closing), never on a per-tick schedule, so there is no "update AI less often off-screen" rule. GDD §6.13's suggestion to reduce AI frequency for off-screen members is read, as Zones R12 reads §3.5, as a presentation concern: camera position is not in the command log, so a rule that let it change decisions would break leaderboard replay (35).

**R8 — Every choice carries its reasons.** `GroundChoice` and `CompositionScore` include the per-consideration terms of F1 and F3 as integers, plus the runner-up (for grounds: the top `ai_explain_top_n` candidates with their scores). These are read-only outputs: Guild screens (39) show them in the suggestion panel ("why here?"), the AI text layer (36) may narrate them, and Dev tooling (43) logs them in balance runs. Display text comes from `i18n/` by consideration ID; this system emits no text.

**R9 — Nothing to do.** If `choose_ground` returns `none` (every ground full, gated or the group ineligible), the caller leaves the group idle and asks again no sooner than `ai_reask_ticks` later, or at once when an event the caller already handles frees a place (a trip closing, 1104 followed by the close). This bounds AI cost and stops a full guild from re-scoring every tick.

**R10 — `choose_gear`: the retrofit policy.** For each slot in the fixed order `weapon`, `armor`, `ring`, `amulet`, F2 picks the best `common` item in `catalog` that the member may equip (Member model R6 rules 2–5: slot, `level_req ≤ level`, weapon `school_req`, armour `armor_class`) and buys it only if it has a higher `level_req` than what the member wears and the remaining wallet covers its price. The wallet is reduced by each purchase before the next slot is considered. This is `sim/model.py auto_gear` exactly, so the calibrated pacing holds (Member model AC-21). `catalog` is what the shop can sell at that moment, supplied by the caller (PROVISIONAL, Items 26 / Market 29: the reference assumes every common item is always in stock). Utility AI does not debit the wallet, take the item or call `equip`: the caller submits the sale through Gold economy `shop_sale` and the equip request through Member model R6.

**R11 — `composition_score`: a primitive, not a formation.** F3 scores one roster against an optional target element (the boss's element for a Golden Boss team; `none` for hunting, where the ground is chosen after the party exists). Party (13) owns the search over rosters, the size limit (`party_max = 5`), who may be grouped, keeping parties stable and disbanding. Utility AI never forms, changes or disbands a party, and never calls Party (systems index, circular dependency resolution 12 ↔ 13). The per-party buffer bonus is counted once per roster, so a search that maximises the total score across parties spreads buffers before doubling them, which is the §6.12 rule "each party should have one buffer".

**R12 — Considerations are a closed list in MVP.** F1 has three considerations (level fit, element edge, danger without a buffer) and F3 has six. The §6.4 needs (hunger, fatigue, need gear) and relationship terms (§6.12 bonds) are **not** MVP; when their owners exist (Gold economy S3 consumables, Retention 16) they add a consideration to the relevant formula through a design change to this GDD, with its own weight key and a re-run of the parity scenario (AC-12). No consideration is added at runtime.

### States and Transitions

Utility AI has no states. It is stateless by R1: every call starts from its arguments. The states it reacts to belong to others: the member's `idle` and town states (Member state machine 41) decide when `choose_ground` and `choose_gear` are called; the trip states (Zones and hunt 11) decide when a place frees up (R9).

The call sequence in one P2 pass, owned by the caller and shown here so the contract is clear:

| Step | Owner | Action |
|---|---|---|
| 1 | Member state machine (41) | Collect members who are `idle`, available to hunt and without an override (R6) |
| 2 | Party (13) | Hand over the hunting groups for those members (existing parties, newly formed ones using F3, solo members as parties of one) |
| 3 | Member state machine (41) | For each group in ascending `party_id`: `choose_ground(group, view)`; add the chosen group to `view` (R4) |
| 4 | Member state machine (41) | Submit each start to Zones for P3; groups with `none` wait (R9) |

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Zones and hunt trips (11) | in | Ground rows (level range, `danger`, `monster_pool`), eligibility checks (R2), `occupancy(g)` (R4) | — (the caller submits starts) | Zones owns ground facts and the start rules |
| Member model (8) | in | `level`, `rebirth`, `school_id`, equipment (with each item's `level_req`) | — (the caller requests `equip`) | Member model owns the record and `equip` |
| CA/PA and traits (9) | in | `trait_mod_ppm(member, party_synergy)` | — | CA/PA owns the sum; this system owns the meaning of `party_synergy` in F3 |
| Schools (20) | in | `element`, `role`, `buff_role`, `weapon`, `armor_class` per school | — | Schools |
| Combat (10) | in | `element_mult(a, d)` (F3 there) and the counter cycle | — | Combat owns the multiplier; this system only reads it |
| Data layer (3) | in | `items`, `grounds`, `monsters`, `zones` rows by `uid`; `ai_*` config keys; `content_live` | — | Data layer |
| Gold economy (27) | in | Member wallet balance (`can_debit`) | — (the caller calls `shop_sale`) | Gold economy owns every debit |
| Items and loot (26) / Market (29) | in | `catalog` of buyable items and prices | — | Items owns stock and prices (PROVISIONAL) |
| Member state machine (41) | out | Calls `choose_ground`, `choose_gear` | `GroundChoice`, purchases | MSM owns when to ask and applies the result (PROVISIONAL) |
| Party (13) | out | Calls `composition_score` | `CompositionScore` | Party owns formation (PROVISIONAL) |
| Golden Boss raid (14) | out (via Party) | Boss element as `target_element` | — | Party forms temp teams with F3 |
| Offline progress (31) | out | Calls `choose_ground` between slices | `GroundChoice` | Offline owns slicing (PROVISIONAL) |
| Command layer (5) | none | — | — | AI decisions are not commands (Command layer R10) |
| Deterministic RNG (2) | none | — | — | Domain 11 reserved, unused (R5) |
| Guild screens (39), AI text layer (36) | out | — | Score breakdowns (R8), read-only | Readers |
| Dev tooling (43) | out | — | Parity vectors for F1–F3; the `pick_ground` parity scenario (AC-12) | Dev tooling runs them |

## Formulas

All formulas are integer arithmetic. Float config values (`element_counter_mult` and the `ai_*` weights given as fractions) are converted once at load to integer parts per million with `round(1,000,000 × value)`, as Zones and hunt does. Every division below is applied to a non-negative numerator, so floor division and truncating division agree and Python `//` matches GDScript `/` on `int` (parity).

*Systems-designer lens applied: each formula was worked at 0, its minimum and its maximum; findings are noted under each formula and in Edge Cases. F1's parity claim was checked by script against `data/grounds.csv` for every level 1–100 at rebirth 0: zero mismatches with `tools/balance_sim.py pick_ground`.*

### F1 — Ground utility

The ground_utility formula is defined as:

`ground_utility(group, g) = level_fit(L, g) + elem_term(group, g) − danger_term(group, g)`

with

`L = floor(Σ member.level / n)`

`level_fit(L, g) =`
- `1,000,000 − ai_level_step_ppm × (L − g.level_min)` if `g.level_min ≤ L ≤ g.level_max` (in band: the hardest in-band ground scores highest)
- `max(0, ai_fit_above_ppm − ai_level_step_ppm × (g.level_min − L))` if `L < g.level_min` (too hard)
- `max(0, ai_fit_below_ppm − ai_level_step_ppm × (L − g.level_max))` if `L > g.level_max` (too easy)

`edge_ppm(group, g) = floor( Σ_m Σ_i [ (off(i,m) − def(m,i)) + E_max ] / (P × n) ) − E_max`
where `off(i,m) = element_mult_ppm(i.element, m.element) − 1,000,000`, `def(m,i) = element_mult_ppm(m.element, i.element) − 1,000,000`, `E_max = element_counter_ppm − element_countered_ppm`, `m` ranges over the ground's `P` non-boss pool monsters and `i` over the group's `n` members.

`elem_term = floor( ai_elem_weight_ppm × (edge_ppm + E_max) / 1,000,000 ) − floor( ai_elem_weight_ppm × E_max / 1,000,000 )`

`danger_term = ai_danger_no_buffer_ppm × (g.danger − 1)` if no member of the group is a buffer (school `buff_role = true`), else `0`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n | int | 1 – 5 | calculated | Group size (Zones R5, `party_max`) |
| L | int | 1 – 200 | calculated | Group reference level, floor of the mean (as the reference `int(sum/len)`) |
| g.level_min, g.level_max | int | 1 – 200 | data file (`grounds.csv`) | Advisory band of the ground |
| g.danger | int | 1 – 3 | data file (`grounds.csv`) | Ground danger (Zones R1) |
| P | int | 1 – 4 | data file (`grounds.monster_pool`, non-boss rows) | Monsters the ground can spawn |
| i.element, m.element | enum | kim, moc, thuy, hoa, tho, none | data file (`schools.element`, `monsters.element`) | Member and monster elements |
| element_mult_ppm | int | 800,000 – 1,250,000 | calculated (Combat F3 × 10⁶) | Five Elements multiplier |
| E_max | int | 450,000 today | calculated | Largest possible `off − def`; offsets keep every division non-negative |
| ai_level_step_ppm | int | 5,000 – 100,000 (20,000) | data file (`config.csv`) | Score lost per level away from the ideal |
| ai_fit_above_ppm | int | 0 – 900,000 (500,000) | data file (`config.csv`) | Ceiling for a ground above the group's level |
| ai_fit_below_ppm | int | 0 – 900,000 (250,000) | data file (`config.csv`) | Ceiling for a ground below the group's level |
| ai_elem_weight_ppm | int | 0 – 500,000 (200,000) | data file (`config.csv`) | Weight of the element edge |
| ai_danger_no_buffer_ppm | int | 0 – 200,000 (60,000) | data file (`config.csv`) | Penalty per danger step above 1 for a group with no buffer |
| ground_utility | int | −210,000 – 1,090,000 | calculated | Score; highest candidate wins, ties to lowest `uid` |

**Output Range:** `level_fit` is 0 – 1,000,000; `elem_term` is −90,000 – +90,000 at today's weights (edge −450,000 – +450,000 × 0.2); `danger_term` is 0 – 120,000. Total −210,000 – 1,090,000. An in-band ground scores at least `1,000,000 − 20,000 × 8 = 840,000` (the widest band today is 9 levels), always above any out-of-band ground (≤ 590,000 with the element bonus), so element and danger only choose **among in-band grounds** while one exists, and a ground the group outlevels is chosen only when nothing at or above its level is open.
**Example:** a solo Kim swordsman (`kim_2`), level 9, rebirth 0. Candidates in band: `g_z01_3` (7–10, danger 3, all-Mộc pool). `level_fit = 1,000,000 − 20,000 × 2 = 960,000`. Kim counters Mộc: `off = +250,000`; Mộc attacking Kim is countered: `def = −200,000`; `edge_ppm = 450,000`; `elem_term = floor(0.2 × 900,000) − floor(0.2 × 450,000) = 180,000 − 90,000 = 90,000`. No buffer: `danger_term = 60,000 × 2 = 120,000`. Score 930,000. `g_z02_1` (10–14) is too hard: `500,000 − 20,000 × 1 = 480,000` plus its element term — lower. He hunts `g_z01_3`.
**Standard-party parity:** the standard party (`tho_1, moc_1, kim_2, hoa_2, thuy_1`) has all five elements, so for any monster element exactly one member counters it, one is countered and one is the same element on each side, and `edge_ppm = 0` for every ground; it has a buffer, so `danger_term = 0`. F1 then reduces to `level_fit`, which picks the same ground as `pick_ground` at every level 1–100 (checked by script; AC-12).
**Boundary notes:** `n = 0` never reaches F1 (Zones refusal 16; the caller does not ask). A ground with no non-boss monster is a validator error (Zones R1), so `P ≥ 1`. `ai_level_step_ppm = 0` makes every in-band ground tie at 1,000,000 and the lowest `uid` (the easiest) win, which breaks parity: the safe range excludes 0. `ai_level_step_ppm` above 100,000 lets `level_fit` of a 9-level band fall to 100,000, below an out-of-band ceiling, and the in-band guarantee fails. Element `none` on either side gives multiplier 1.0, so 0 on that pair.
**Feedback loops:** none positive. The group's level rises, so its choice moves to harder grounds; the XP level-difference penalty (Zones F2) and fight danger already push the same way. Capacity (R4) spreads groups when one ground is popular.

### F2 — Gear purchase

The gear_choice formula is defined as:

`best(slot) = argmax over items x in catalog with x.rarity = common, slot_of(x) = slot, x.level_req ≤ member.level, equip_ok(member, x)` of `(x.level_req, −x.uid)`
`buy(slot) = best(slot)` if `best(slot).level_req > current_level_req(slot)` and `best(slot).price ≤ wallet_left`, then `wallet_left −= price`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| slot | enum | weapon, armor, ring, amulet | constant (Member model R5) | Processed in this fixed order |
| x.level_req | int | 1 – 200 | data file (`items.csv`) | Level needed to equip |
| x.price | int | ≥ 0 gold | data file (`items.csv`, Items 26) | Shop price |
| x.rarity | enum | common … | data file (`items.csv`) | Only `common` is bought (reference policy) |
| equip_ok | bool | — | calculated (Member model R6 rules 2–5) | School weapon and armour-class match |
| current_level_req | int | −1 – 200 | calculated | `level_req` of the equipped item; −1 for an empty slot |
| wallet_left | int | 0 – wallet | calculated | Member's wallet, reduced by each purchase in this call |

**Output Range:** 0 – 4 purchases per call; total price ≤ the wallet. Never a purchase that does not raise the slot's `level_req`.
**Example:** a level-12 `hoa_2` with 300 gold, wearing a level-1 crossbow and nothing else. Weapon: the best common `fire_crossbow` with `level_req ≤ 12` is the level-10 one; if it costs 180, buy it (120 left). Armor: the level-10 medium armour costs 150 > 120, skip. Ring: the level-10 ring costs 90, buy (30 left). Amulet: 95 > 30, skip. Result: two purchases.
**Boundary notes:** wallet 0 gives no purchases. A catalog with no matching item skips that slot. An item already better than anything common (a boss drop) is never replaced, because its `level_req` is compared, not its rarity. Price 0 items are bought whenever they are an upgrade.
**Feedback loops:** gear raises kill speed, which raises income, which buys gear: intended and calibrated (GDD §4.3); damped by the `level_req` gate.

### F3 — Party composition score

The composition_score formula is defined as:

`composition_score(R, t) = B·has_buffer + T·has_tank + S·sinh_links + C·counters(t) + Σ_i syn_i − W·max(0, spread − spread_max)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| R | roster | 1 – 5 members | calculated (Party 13) | The candidate roster |
| t | enum | element or none | calculated (Golden Boss row; `none` for hunting) | Target element |
| has_buffer | 0/1 | — | calculated | At least one member's school has `buff_role = true` (`moc_1`, `thuy_2`) |
| has_tank | 0/1 | — | calculated | At least one member's school role is a tank role (`tank`, `tank_guardian`), the reference `TANK_ROLES` |
| sinh_links | int | 0 – 5 | calculated | Count of elements `e` present in R whose generated element (tương sinh: Mộc→Hoả→Thổ→Kim→Thuỷ→Mộc) is also present |
| counters(t) | 0/1 | — | calculated | `t ≠ none` and some member's element counters `t` (Combat F3 cycle) |
| syn_i | int | −50,000 – +80,000 today | calculated (`trait_mod_ppm(i, party_synergy)`, CA/PA 9) | Trait fit (`t_team_player` +0.08, `t_loner` −0.05) |
| spread | int | 0 – 199 | calculated | Highest minus lowest member level |
| B = ai_buffer_bonus_ppm | int | 0 – 1,000,000 (400,000) | data file (`config.csv`) | The "big bonus" for a buffer (§6.12) |
| T = ai_tank_bonus_ppm | int | 0 – 1,000,000 (200,000) | data file | Tank present |
| S = ai_sinh_link_ppm | int | 0 – 100,000 (40,000) | data file | Each generation link |
| C = ai_counter_cover_ppm | int | 0 – 500,000 (150,000) | data file | Someone counters the target |
| W = ai_spread_penalty_ppm | int | 0 – 200,000 (50,000) | data file | Per level of spread beyond the limit |
| spread_max = ai_level_spread_max | int | 0 – 50 (10) | data file | §6.12 "±10" |
| composition_score | int | ≈ −9,700,000 – 1,350,000 | calculated | Higher is better; Party maximises |

**Output Range:** best case 1,350,000 (buffer, tank, 5 links, counter, five `t_team_player`); worst about −9,700,000 (spread 199, five loners). Within the spread limit and without traits: 0 – 950,000. The buffer bonus is the largest single term, so a roster with a buffer beats any roster without one unless it costs more than 8 levels of excess spread.
**Example:** the standard party, all level 30, no traits, hunting (`t = none`): buffer 400,000 + tank 200,000 + all five elements give 5 links × 40,000 = 200,000 + 0 + 0 − 0 = 800,000. The same party for a Mộc Golden Boss (`t = moc`): Kim counters Mộc, +150,000 = 950,000. Swap `moc_1` for a second `kim_2`: no buffer, links Thổ→Kim, Kim→Thuỷ, Hoả→Thổ = 3, score 200,000 + 120,000 + 150,000 = 470,000.
**Boundary notes:** a roster of 1 scores at most `B` or `T` plus traits (no links possible from one element), so solo members are never attractive as "parties"; whether a member hunts solo is Party's decision. `spread_max = 0` penalises any level difference. `B = 0` removes the buffer priority that §6.12 fixes as a rule [CHỐT]; the safe range starts at 200,000.
**Feedback loops:** none: the score reads the roster and returns a number.

## Edge Cases

- **If no ground is a candidate** (all full, guild level too low, the group gated by rebirth): `choose_ground` returns `none`; the group stays idle and is asked again after `ai_reask_ticks` or when a trip closes (R9). No refusal reaches Zones.
- **If the group's mean level is above every live ground's band** (level 100 at rebirth 0 once `g_z10_3` is full): the best too-easy ground wins (`ai_fit_below_ppm` ceiling); with all too-easy grounds also full, `none`. Zones F2 already reduces XP there; the player sees "no suitable ground" in the suggestion panel.
- **If two grounds score exactly the same:** lowest `uid` wins (R5). Two in-band grounds cannot tie on level fit alone, because every ground's `level_min` differs today; a tie needs the element or danger terms to cancel the difference exactly.
- **If members of very different levels are in one group** (level 10 and level 60): `L = 35` picks a level-35 ground, which is dangerous for the level-10 member and penalised in XP for the level-60 one. This is a party-quality problem, which F3's spread penalty already discourages; Utility AI does not split the group (R11).
- **If the group has a mixed-rebirth roster:** only grounds whose `rebirth_req` every member meets are candidates (Zones R2.3), so the lowest-rebirth member sets the ceiling.
- **If the pool of a ground contains `none`-element monsters** (mixed zones 10–15): those pairs add 0 to `edge_ppm`; the average still counts them in `P`.
- **If two groups want the last places of one ground in the same tick:** the lower `party_id` gets it (R4); the next group scores that ground as full and takes its next best.
- **If occupancy changes between P2 and P3** (a recall by the Golden Boss frees places, or a player order starts a trip first in P1): a start may still be refused with code 14. The caller treats it as `none` for this tick (R9). Not an error.
- **If a member has a player order** (R6): Utility AI is not called for that member; if it is called anyway (a caller bug), it scores normally and the caller must discard it. AC-8 tests the caller path.
- **If `choose_gear` is called while the member is in a state where `equip` is blocked** (`hunting`, `boss_raid`, …, Member model R6 rule 6): it still returns its list; the caller must call it only in the town states. The equip request is then refused by Member model with the item returned (no loss).
- **If the wallet drops between the decision and the sale** (another debit in the same tick): `shop_sale` is refused by Gold economy (`can_debit` false) and that purchase is skipped; the rest of the list proceeds in order.
- **If a better non-common item is equipped** (a boss drop of a lower `level_req` than the common item now available): F2 replaces it with the common item, because it compares `level_req` only. This matches the reference and is an open balance question (OQ-4).
- **If `party_synergy` sums are large** (future traits): `syn_i` is not clamped by CA/PA (consumers clamp, CA/PA R `trait_mod_ppm`). This system clamps each `syn_i` to ±`ai_synergy_cap_ppm` (200,000) so traits cannot outweigh the buffer rule.
- **Degenerate strategy check:** the player cannot steer AI choices except by orders (R6) and by roster composition, both intended. There is no repeatable loop that yields gain from an AI choice; the only exploit surface would be leaderboard replay, which R1 and R7 keep deterministic.

## Dependencies

| System | Direction | Hard/Soft | Interface | Status |
|---|---|---|---|---|
| Zones, grounds, monsters and hunt trips (11) | upstream | Hard | Ground rows, eligibility (R2), `occupancy` (R4) | Designed — conforms (Zones R2 "Utility AI reads the level range, danger, the monsters' elements and current occupancy") |
| Member model (8) | upstream | Hard | Record fields, equip rules R6 (for F2's `equip_ok`) | Designed — conforms; takes the `auto_gear` policy (Member model R6 note, AC-21), but see OQ-1 on who executes it |
| CA/PA and traits (9) | upstream | Soft (F3 synergy only) | `trait_mod_ppm(member, party_synergy)` | Designed — conforms (its Interactions row for 12) |
| Schools and school change (20) | upstream | Hard | `element`, `role`, `buff_role`, `weapon`, `armor_class` | Designed — conforms |
| Combat (10) | upstream | Hard | `element_mult` (F3) and the counter cycle | Designed — conforms; Combat R16 lists "choosing where to fight" as this system's |
| Data layer (3) | upstream | Hard | Content rows by `uid`, `content_live`, `config.csv` keys | Designed |
| Gold economy (27) | upstream | Hard (F2) | Wallet balance / `can_debit` | Designed — conforms (its row: "Utility AI owns the decision") |
| Items and loot (26) | upstream | Hard (F2) | Item rows, prices, the buyable `catalog` | Designed; catalog source PROVISIONAL (OQ-2) |
| Deterministic RNG (2) | upstream | None in MVP | Domain 11 reserved, unused (R5) | Designed — RNG lists 12 as its only soft dependent |
| Member state machine (41) | downstream | Hard (for 41) | Calls F1/F2 and applies them | Not designed — PROVISIONAL |
| Party (13) | downstream | Hard (for 13) | Calls F3 | Not designed — PROVISIONAL |
| Golden Boss raid (14) | downstream (via Party) | Soft | Boss element as `target_element` | Not designed — PROVISIONAL |
| Offline progress (31) | downstream | Soft | Calls F1 between slices | Not designed — PROVISIONAL |
| Guild screens (39), AI text layer (36) | downstream | Soft | Breakdowns (R8) | Not designed |
| Dev tooling (43) | downstream | Soft | Parity vectors, AC-12 scenario | Designed |
| Command layer (5) | none | — | AI decisions are not commands (its R10) | Designed — conforms |

The systems index lists RNG, Member model, CA/PA and traits, Zones and hunt as this system's dependencies. This GDD adds Schools, Combat, Data layer, Gold economy and Items and loot, which F1–F3 read; the index row's Depends On is updated accordingly.

## Tuning Knobs

All are new `config.csv` keys (to be added with the implementation story; key/value rows, no new columns). Defaults are chosen so F1 reproduces the reference `pick_ground` for the standard party.

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `ai_level_step_ppm` | 20,000 | 5,000 – 100,000 | In-band guarantee breaks above ~100,000 (F1 notes) | 0 ties every in-band ground; easiest wins | Sets the exchange rate for the next three: an element or danger term is worth `term / step` levels |
| `ai_fit_above_ppm` | 500,000 | 300,000 – 800,000 | Above 840,000 a too-hard ground can beat an in-band one | Too-hard grounds lose to too-easy ones when nothing fits | `ai_fit_below_ppm` (must stay above it to match the reference fallback) |
| `ai_fit_below_ppm` | 250,000 | 0 – 499,999 | Above `ai_fit_above_ppm` the fallback prefers farming low grounds | 0 makes outlevelled grounds unusable even as a last resort | `ai_fit_above_ppm` |
| `ai_elem_weight_ppm` | 200,000 | 0 – 400,000 | Element dominates level; parties farm low counter grounds | 0 removes the §6.12 element rule (inert term) | `ai_level_step_ppm`; Combat's `element_*_mult` (changing those changes `E_max`) |
| `ai_danger_no_buffer_ppm` | 60,000 | 0 – 150,000 | Healer-less groups stay on danger-1 grounds and level slowly | 0: healer-less groups go as deep as healed ones (`thuy_1` solo dies often, GDD §20 note 2) | `ai_level_step_ppm` |
| `ai_buffer_bonus_ppm` | 400,000 | 200,000 – 1,000,000 | Buffers dominate every other term (acceptable; §6.12 rule) | Below 200,000 the [CHỐT] buffer priority can lose to links | `ai_tank_bonus_ppm`, `ai_spread_penalty_ppm` |
| `ai_tank_bonus_ppm` | 200,000 | 0 – 400,000 | Above the buffer bonus, tank outranks buffer (contradicts §6.12) | 0 ignores tanks | `ai_buffer_bonus_ppm` |
| `ai_sinh_link_ppm` | 40,000 | 0 – 80,000 | 5 links outrank a tank | 0 ignores tương sinh | Party's own combat bonus for tương sinh (Combat OQ-6) |
| `ai_counter_cover_ppm` | 150,000 | 0 – 400,000 | Raid teams sacrifice buffers for counters | 0 ignores boss element in suggestions | Combat `element_counter_mult` |
| `ai_spread_penalty_ppm` | 50,000 | 10,000 – 200,000 | Any gap above the limit makes a roster unusable | Wide-level parties form; F1 then picks bad grounds | `ai_level_spread_max` |
| `ai_level_spread_max` | 10 | 0 – 30 | Weak members drag strong parties to low grounds | Small guilds cannot form parties at all | `ai_spread_penalty_ppm` |
| `ai_synergy_cap_ppm` | 200,000 | 0 – 400,000 | Traits outweigh role rules | 0 makes traits inert | CA/PA trait values |
| `ai_reask_ticks` | 50 (5 s) | 10 – 300 | Idle members visibly wait | Re-scoring cost when the guild is full | Member state machine cadence |
| `ai_explain_top_n` | 3 | 1 – 5 | UI clutter, larger outputs | Player sees only the winner | Guild screens |

Pointed to, not owned: `element_counter_mult`, `element_countered_mult`, `element_same_mult` (Combat), `party_max` (Party / Data layer), `flee_hp_pct` and `lvl_diff_*` (Zones), item prices (Items 26).

## Visual/Audio Requirements

Utility AI has no visuals of its own; its decisions become visible through the world view (38) and guild screens (39). *Art-director lens applied in this session:* the requirement is legibility of intent, not spectacle.

- **Intent cue.** When a group's ground is chosen, the world view may show, for 1.5 s above the leader, the target ground's element glyph (the same five glyphs Combat uses for the counter bonus). No new art beyond those glyphs.
- **Suggestion panel visuals.** Consideration rows use the existing element glyphs and a three-step bar (good / neutral / bad) per term; no numbers by default, numbers on long-press.
- **Debug overlay (dev builds only).** Per-group score breakdown text over the ground; never in release.
- **Audio:** none. A decision is not an event the player should hear; departures already have the trip-start sound (Zones/Audio 40).
- No art bible exists yet; when it does, the element glyph style is the only principle that applies here.

## Game Feel

- **No dithering.** A group never changes its target ground once chosen (decisions happen only when the group is ready to start, R7), so the player never sees a party turn around for an AI reason. Only recall and orders end a trip early (Zones R11).
- **No visible idling.** A group that has a candidate leaves in the same tick it becomes ready; a group without one is re-asked within `ai_reask_ticks` (≤ 5 s) or the moment a place frees (R9). Target: in a 1-hour unattended run with free capacity, no group is idle more than 5 s (AC-10).
- **Orders feel instant.** A player order takes effect from the next tick's P1 (Command layer R11); the AI never re-routes an ordered member (R6).
- **Choices look reasonable.** Playtest target: shown a party and its chosen ground, a tester agrees with the choice or names the AI's reason from the panel in at least 8 of 10 cases (playtest question, not automated).

## UI Requirements

- **"Why here?" panel** (Guild screens 39, party detail): the chosen ground and the next `ai_explain_top_n − 1` candidates, each with its level-fit, element and danger rows from the R8 breakdown. Free and Premium.
- **Party fit indicator** (Guild screens 39, party editor): the F3 breakdown as badges — buffer, tank, links, counter, spread warning. The "thiếu buffer" warning of §6.12 is shown when `has_buffer = 0`.
- **Raid team suggestion** (Golden Boss 14 screens): F3 with the boss element; the Premium "auto arrange" is Party's search over the same score.
- All labels come from `i18n/` keys per consideration ID (`ui.ai.consideration.level_fit` etc., Localization 4).

> **📌 UX Flag — Utility AI**: This system has UI requirements. In Pre-Production, run `/ux-design` for the party detail "Why here?" panel and the party editor fit badges **before** writing epics. Stories that reference this UI should cite `design/ux/[screen].md`, not this GDD.

## Cross-References

| This GDD | Other GDD | What is referenced | Kind |
|---|---|---|---|
| R3, F1 | `zones-grounds-monsters-and-hunt-trips.md` R1, R2, R4, R5, R11, R12, R14 | Ground columns, start rules, capacity and start order, refusal 14, recall, camera rule | Rule / interface |
| F1 | `combat.md` F3 | `element_mult`, counter cycle, `element_*_mult` | Formula |
| F1, AC-12 | `tools/balance_sim.py` `pick_ground` | Reference ground policy (parity target) | Code |
| R10, F2 | `member-model.md` R5, R6, AC-21 | Slots, equip rules, `auto_gear` moved here | Rule |
| R10 | `sim/model.py` `auto_gear` | Reference gear policy | Code |
| R10 | `gold-economy.md` R7, Interactions | `shop_sale`, `can_debit`, wallet ownership | Interface |
| F3 | `ca-pa-and-traits.md` `trait_mod_ppm` | `party_synergy` key | Interface |
| F1, F3 | `schools-and-school-change.md` | `element`, `role`, `buff_role`, `armor_class` | Data |
| R5 | `deterministic-rng.md` R4 (domain 11), Dependencies | Tie-break domain reserved; lowest-ID fallback | Rule |
| R6, Overview | `command-layer.md` R10, R11, OQ-7 | AI decisions are not commands; orders override | Rule |
| R1 | `sim-core-and-tick-loop.md` R2 (P2 `members`) | Phase in which decisions are applied | Rule |
| F3 | JX1 GDD §6.12, §6.13 | Matching terms, temp teams | Source |

## Acceptance Criteria

Story types: AC-1 – AC-9, AC-11, AC-13 – AC-15 are **Logic** (automated unit tests in `tests/unit/utility_ai/`); AC-10 and AC-12 are **Integration** (headless run / balance simulator); AC-16 is **UI** (screenshot).

- **AC-1 [Logic] (R1)**: **GIVEN** the parity vectors for F1, F2 and F3 (fixed groups, grounds, catalogs and rosters), **WHEN** the Python reference and the GDScript port evaluate them, **THEN** every output, including breakdown terms, is identical, and a static check finds no RNG, clock or float call in the module at runtime.
- **AC-2 [Logic] (F1 level fit)**: **GIVEN** a group with `L = 25` and grounds `g_z03_1` (20–24), `g_z03_2` (23–27), `g_z03_3` (26–30), **WHEN** `level_fit` is computed, **THEN** the values are 250,000 − 20,000 = 230,000 (too easy by 1), 1,000,000 − 40,000 = 960,000, and 500,000 − 20,000 = 480,000.
- **AC-3 [Logic] (F1 element edge, boundaries)**: **GIVEN** a solo `kim_2` and an all-Mộc ground, **THEN** `edge_ppm = 450,000` and `elem_term = 90,000`; **GIVEN** a solo `moc_1` on an all-Kim ground, **THEN** `edge_ppm = −450,000` and `elem_term = −90,000`; **GIVEN** the standard party on any ground, **THEN** `edge_ppm = 0`; **GIVEN** `ai_elem_weight_ppm = 0`, **THEN** `elem_term = 0`.
- **AC-4 [Logic] (F1 danger)**: **GIVEN** a group with no buffer on a danger-3 ground, **THEN** `danger_term = 120,000`; **GIVEN** the same group plus a `moc_1`, **THEN** `danger_term = 0`.
- **AC-5 [Logic] (R3, R5 eligibility and ties)**: **GIVEN** a rebirth-0 group at level 100, **WHEN** `choose_ground` runs, **THEN** no zone-11+ ground is returned; **GIVEN** two candidate grounds with equal scores, **THEN** the lower `uid` is returned.
- **AC-6 [Logic] (R4 capacity)**: **GIVEN** a ground with capacity 6 and occupancy 2 and two 3-member groups (party IDs 4 and 7) whose best ground it is, **WHEN** the caller asks in ascending `party_id` and adds each choice to the view, **THEN** group 4 is placed there (2 + 3 = 5 ≤ 6), group 7 is not (5 + 3 = 8 > 6) and gets its next best ground, and Zones refuses neither start.
- **AC-7 [Logic] (R9)**: **GIVEN** every ground full, **WHEN** `choose_ground` runs, **THEN** it returns `none`, and the caller does not ask again for that group for 50 ticks unless a trip closes.
- **AC-8 [Integration-lite / Logic] (R6)**: **GIVEN** a member with a player order "hunt at `g_z01_1`" and level 30, **WHEN** P2 runs, **THEN** Utility AI is not called for that member's group and the start submitted is `g_z01_1`.
- **AC-9 [Logic] (F2, R10)**: **GIVEN** the F2 example member (level 12 `hoa_2`, 300 gold, prices 180/150/90/95), **WHEN** `choose_gear` runs, **THEN** it returns exactly weapon then ring, total 270; **GIVEN** wallet 0, **THEN** it returns an empty list; **GIVEN** the reference `auto_gear` on 1,000 seeded member states, **THEN** both choose the same items.
- **AC-10 [Integration] (R7, R9, Game Feel)**: **GIVEN** a 20-member guild with free capacity, **WHEN** a headless 1-hour run executes with no player input, **THEN** no group is idle for more than 50 consecutive ticks while it has a candidate ground, the command log contains no AI entries (Command layer AC-14), and running the same seed with the world-view camera at two different positions gives byte-identical state hashes.
- **AC-11 [Logic] (F3)**: **GIVEN** the standard party at level 30 with no traits, **THEN** `composition_score(R, none) = 800,000` and `composition_score(R, moc) = 950,000`; **GIVEN** `moc_1` replaced by a second `kim_2`, **THEN** the score for `moc` is 470,000; **GIVEN** levels 10 and 25 in one roster, **THEN** the spread term is −250,000.
- **AC-12 [Integration] (F1 parity, R10)**: **GIVEN** `tools/balance_sim.py` with `pick_ground` and `auto_gear` replaced by `choose_ground` and `choose_gear`, **WHEN** the standard 5-member run goes from level 1 to 100 at rebirth 0, **THEN** the ground chosen at every step equals the reference's and the time to level 100 is within 2% of the reference (≈71 h, GDD §4.3; Member model AC-21).
- **AC-13 [Logic] (F3 clamp)**: **GIVEN** a member whose `trait_mod_ppm(party_synergy)` is 500,000, **THEN** `syn_i = 200,000`.
- **AC-14 [Logic] (R11 buffer once)**: **GIVEN** a roster with two buffers, **THEN** `has_buffer` contributes 400,000 once, not twice.
- **AC-15 [Logic] (R8 breakdown)**: **GIVEN** any `choose_ground` result, **THEN** the breakdown terms sum to the reported score for the winner and each listed runner-up, and at most `ai_explain_top_n` candidates are listed.
- **AC-16 [UI] (UI Requirements)**: **GIVEN** a party on its chosen ground, **WHEN** the player opens the party detail, **THEN** the "Why here?" panel shows the ground and two runners-up with level, element and danger rows; retained screenshot in `production/qa/evidence/`.
- **Performance [Logic/benchmark]**: one `choose_ground` call for a 5-member group over 45 grounds completes in under 0.05 ms on the reference desktop and the P2 cost of a full re-score of 50 groups stays within the P2 share of the tick budget (Sim core R16 budgets); confirm on the device spike.

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **Conflict to reconcile:** Member model R6's note says Utility AI "submits the purchase … and then calls `equip`"; this GDD (R10) only returns the list and the caller (MSM 41) executes it, per the systems-index contract "Utility AI only scores options" and Command layer R10. The consistency pass should align Member model's note. | consistency-check, Member model (8) | Before MSM GDD |
| OQ-2 | **PROVISIONAL: Items and loot (26) / Market (29)** — the buyable `catalog` is every common item at its listed price, always in stock, as in the reference. If shops have stock limits, F2 picks from what is in stock. | Items (26), Market (29) | Vertical Slice |
| OQ-3 | §6.4 needs (hunger, fatigue, out of potions → return codes 6–8; buy food/potions) are not MVP. Their owners (Gold economy S3, Retention 16, MSM 41) will add considerations through a design change (R12). | game-designer | S3 |
| OQ-4 | F2 replaces a better non-common item with a common one of higher `level_req` (reference behaviour). Should it compare the item's stat contribution instead? Needs a profile-delta check (Member model F1–F4) and a re-run of AC-12. | game-designer, systems-designer | After S4/S5 |
| OQ-5 | §9.1 "cân bằng độ khó thích nghi" (adaptive difficulty) is not designed here: it would change outcomes, not choices, and must stay deterministic for leaderboards. Scope question: which system owns it, if any? Kept out of MVP. | creative-director, producer | Alpha |
| OQ-6 | **RESOLVED (consistency-check 2026-11-16):** MSM R10 trip step and R7 step 0 do exactly this (orders override per group; gear bought via Gold economy `shop_sale` and Member model `equip`). Original: **Member state machine (41)** — it calls `choose_ground` in P2 for idle, available, un-overridden groups in ascending `party_id`, maintains the R4 view, re-asks per R9, and calls `choose_gear` once per trip close in a town state, executing purchases through Gold economy and `equip`. | MSM (41) | Its GDD |
| OQ-7 | **PROVISIONAL: Party (13)** — it supplies hunting groups (solo = party of one) with stable `party_id`, and uses `composition_score` (F3) for formation and Golden Boss temp teams; it owns search, size and disbanding. The §6.12 term "same target ground" is not in F3, because grounds are chosen after the party exists; Party may group members whose solo `choose_ground` agrees if it wants that term. | Party (13) | Its GDD |
| OQ-8 | **PROVISIONAL: Offline progress (31)** — re-picks the ground with `choose_ground` at each slice boundary (as `balance_sim` does each step), using the members' levels at that boundary. The reference `fast_forward` keeps one ground; the parity tolerance must cover the difference. Also: rebirth ladders in `balance_sim` use `pick_ground_any` (easiest ground reaching the level), which F1 does not reproduce; rebirth pacing must be re-measured with F1 (Rebirth 23, Dev tooling 43). | Offline (31), Dev tooling (43) | Their GDDs |
| OQ-9 | No game pillars exist, so CD-GDD-ALIGN could only check against GDD §1/§9.1 and this Player Fantasy (CONCERNS accepted). Re-check when pillars are written. | creative-director | When pillars exist |
| OQ-10 | Is capacity 6/8/10 enough for a full guild under F1 (everyone at one band crowds three grounds)? Measure with AC-10 at 30–50 members (Zones OQ-4). | game-designer | Vertical Slice |
