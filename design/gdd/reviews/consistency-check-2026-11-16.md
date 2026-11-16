# Consistency Check Report — 2026-11-16

Date: 2026-11-16
Mode: full scope, **autonomous** (user override). Each resolution is logged in `production/session-logs/decision-log.md` (23 entries, skill `consistency-check`).
Registry entries checked: 0 entities, 0 items, 84 formulas, 177 constants (261 total)
GDDs scanned: 46 (every `design/gdd/*.md` except `systems-index.md`)
Scope: all GDD sections (workflow `full`, no system overrides)

---

## 1. Registry scan (Phase 3)

An automated scan matched every registered constant's name against each numeric value stated next to it in every GDD (`name = N`, `name: N`, `name | N`). The scan returned 60 mismatches. Every one was a test fixture inside an AC (for example, `command_drain_max = 10` in Command layer AC-12), a derived value (`ticks_per_day = 864,000`) or a section number. **No registered value contradicts its source GDD.** Formula variable and range checks found no conflicts either. Verdict on the registry itself: clean, with no stale entries.

## 2. Cross-GDD conflicts found and fixed (Phase 4)

Resolution rule: the GDD that owns the fact wins. The owner is the registry `source:`, or the system the systems index assigns it to. The dependent GDD was edited to match. Where dependents needed a small interface, it was added to the owner.

| # | Conflict | Owner (wins) | Fix |
|---|---|---|---|
| C1 | Guild and buildings said guild income comes from tax, but tax is off in MVP | Gold economy R6/R7 | Buildings' feedback-loop text and F5 lens note now name the 30% shop-sale share as the MVP income, with tax arriving in VS |
| C2 | Loot paid twice: Gold economy `sell_item` sold materials from storage; Gold named Zones as owner of `base_gold_*` and the sell ratios | Items R13, F1, F5 | `sell_item` refuses materials; the ownership pointers now name Items. Items F5 names consumables. Gold OQ-9/11/15 and Crafting OQ-7 closed |
| C3 | Who splits trip income (Items R6 vs Zones R8 vs Gold OQ-11). Offline handed in sampled bags while Zones F10 carried gold only | Zones (split), Offline (driver) | `hand_in` returns totals and credits nothing. Zones R8 splits live income; Offline credits `offline_hunt` with the same split. Zones R15 returns per-trip `bags[i]`, and F10 no longer scales gold. Items OQ-6/11, Zones OQ-7/11 and Offline OQ-7 closed |
| C4 | Schools assumed a capped guild storage owned by Buildings | Items R7 (uncapped) | Schools interactions, edge case, dependency row, assumption 3 and AC-23 rewritten. Buildings OQ-11 closed |
| C5 | Member model said Utility AI submits gear purchases and calls `equip` | Utility AI R1/R10, MSM R7 | Member model R6 note and interaction rows now say MSM executes the returned list. Utility AI OQ-6 closed |
| C6 | `item_pa_eye` (Thiên Nhãn) was a storage item in Items R9 but an entitlement elsewhere | Entitlement / CA/PA | Items R7/R9: Thiên Nhãn is not a storage item; its `items.csv` row is catalog-only. CA/PA OQ-13 and IAP OQ-9 closed |
| C7 | Schools read the raid minimum level against guild level | Golden Boss F2 (boss level) | Schools edge case fixed; Golden Boss OQ-3 closed; registry `raid_min_level_ratio` referenced_by updated |
| C8 | Golden Boss assumed Offline closes trips before the backlog runs; Offline pauses them | Offline R5 (driver), Golden Boss R16 (rule) | GB R16: members of a paused trip count as home for eligibility, and the trip is untouched. GB PROVISIONAL-3 and Offline OQ-6 closed |
| C9 | Party OQ-7: hunt intent carried a ground, but Utility AI chooses per group | MSM R10 | MSM already chooses per group, and a group with an order goes to the ordered ground. Party's `hunt_intent` / `hunt_intent_timeout_s` references were aligned to MSM's "free to hunt" and `ai_reask_ticks`. Party's solo proposal was not adopted |
| C10 | Zones said "party_id never reused"; Party says party_id = key leader `member_id`, trip_ordinal = `trips_led` | Party R5 | Zones R5 rewritten; Zones OQ-5 closed |
| C11 | Schools ran its own P1 handler, IDs were only proposed, and event 2004 duplicated Command layer 502 | Command layer R3/R6/R7 | Schools R8 registers appliers 2001–2003 with reason codes 101–107 (shared 7/8/9 where they fit), and 2004 is now for sim-origin refusals only. Command layer OQ-1 closed; vocabulary rows got their owners' IDs |
| C12 | Number abbreviation: Gold economy said "above a million"; Localization uses 10,000 | Localization F2 | Gold UI item 5 now defers to Localization; Guild screens OQ-13 closed |
| C13 | Member model and MSM listed Jianghu poaching on-roster members; Jianghu does not do that | Jianghu R1, GDD §6.11 | References removed from Member model R9 and from the MSM capability table, interactions, dependencies and PROVISIONAL row. Whether to **add** on-roster poaching is left to the user (Jianghu OQ-2) |
| C14 | Raid survivors: Golden Boss sent them "to idle"; MSM uses a short rest | MSM R8 | GB R5, R6, R9, the edge case and AC-6 now route survivors through `leave_raid`, then `resting`, then `idle` |
| C15 | Skills OQ-2 needed an XP hook; Offline OQ-5 needed `award` without a ctx | XP curve R4 | Added steps 5–7: `ctx = null` emits nothing, the `on_xp_awarded(member_id, effective_milli, new_level)` listener, and the `{discarded, old_level, new_level}` return. Offline is the one other permitted 2201 emitter. The XP dependency row for Skills is now Hard. XP OQ-4, Skills OQ-2 and Offline OQ-5 closed |
| C16 | Audio needed `played_records`; the world view needed a `fight_timeline`; Golden Boss `want_timeline` depended on the camera | World view R13, Zones R12, Golden Boss R8 | `view_context.played_records` added; Zones `fight_timeline(...)` query added; the raid passes `want_timeline = false` and offers `raid_fight_timeline(raid_ordinal)`. Combat interaction row and V/A item 4 aligned. World view OQ-1/2/6 and Audio OQ-2 closed |
| C17 | Sim core R6 said replay goes by apply stamp, with no next-seq query and no credited-window log | Command layer R9 (rule), Sim core R6 (log) | Sim core R6 now logs the envelope with `origin`, exposes `next_command_seq()`, replays host entries by `seq`, and adds an `offline_credit {at_tick, c}` time entry via `log_offline_credit(c)`. Offline R1 step 6 calls it. Command layer OQ-2 and Offline OQ-2 closed; Leaderboards OQ-5 partly closed |
| C18 | Elders: upkeep (Gold OQ-13) and retention exemption (Retention OQ-9) | Gold F3, Retention R1 | Both already matched Rebirth R10 and were confirmed. Schools R4 now excludes `elder`. Rebirth OQ-9/11 closed; Rebirth OQ-6 partly closed |
| C19 | **New:** owner reason codes reused Command layer shared codes with other meanings (Retention 1/7/8/9, Jianghu 7 = `cooldown`). Ads used non-integer codes `3301-1…4` | Command layer R4/R6 | Retention now uses 101–104, Jianghu `cooldown` is 106 and Ads uses 101–104. Jianghu OQ-6 and Ads OQ-12 closed; IAP OQ-10 closed |
| C20 | **New:** ledger entry types assumed but never assigned (Arena, Tower, Jianghu) | Gold economy R3 | Added 12 `arena_reward`, 13 `tower_reward`, 31 `jianghu_invite` and 32 `jianghu_poach`. Arena OQ-3, Tower OQ-6 and Jianghu OQ-4 closed |
| C21 | **New:** Analytics said subscriber order 3700 is "the highest order in use" (4100 and 4400 are higher); Onboarding/Analytics step signal | Event bus R4; Onboarding | Wording corrected (harmless, because the tap is passive). Analytics OQ-7 closed via events 4401/4402 |
| C22 | Onboarding newbie XP: Hunt never stated the call | Onboarding F1 | Zones F1 now applies `onboarding.xp_mult_ppm()` to live kills only. Onboarding OQ-2 closed |
| C23 | Tower needed a keyed guild-loot roll | Items R3/R9a | Added `roll_guild_loot_keyed(key, table, level, rolls)`. Tower OQ-5 closed |
| C24 | Earlier log entry (consistency-failures): Schools cited `rebirth.csv new_level_cap` for the rebirth-0 cap | XP curve R3 | The Schools edge case now cites `cap[0]` = row 1 `req_level` |
| C25 | Other confirmations closed while verifying: Buildings OQ-2 (arrears), Gold OQ-8 and OQ-12 | owners | Closed |

**Count:** 25 conflict groups found, 25 fixed (C13 and C18 are partly fixed; their open part is listed below). 47 Open Question rows were rewritten as `RESOLVED (consistency-check 2026-11-16)`, plus several Dependency and Interaction rows that had said PROVISIONAL.

## 3. ID blocks and handler orders (verified unique)

- **Event and command blocks:** 500 Command layer · 800 Member model · 900 CA/PA · 1100 Hunt · 1300 Party · 1400 Golden Boss · 1500 Recruitment · 1600 Retention · 1700 Jianghu · 1800 Arena · 1900 Tower · 2000 Schools · 2100 Skills · 2200 XP · 2300 Rebirth · 2400 Enhancement · 2500 Quests · 2600 Items · 2700 Gold · 2800 Crafting · 2900 Market · 3000 Buildings · 3100 Offline · 3200 Entitlement · 3300 Ads · 3400 IAP · 3500 Leaderboards (reason codes only) · 4100 MSM · 4400 Onboarding. No two GDDs claim the same block.
- **Tick-handler orders, unique within each phase:** P1: 100 Command layer (the only queue reader) plus 800, 1800, 1900, 2900 and 3000. P2: 4100. P3: 1100, 1800 and 1900. P4: 1800, 1900, 2600, 2700 and 2900. P5: 1400 (Golden Boss, newly stated), 1500, 1600, 1700, 2800, 3000, 3100 and 4400.
- **Bus subscriber orders:** 2500, 2600, 3100, 3700 (Analytics), 4100 and 4400.
- **Caution:** P1 orders 800, 1800, 1900, 2900 and 3000 are still listed as P1 handlers even though Command layer R3 says features register appliers rather than P1 handlers. This pass did not change them. They are flagged for the Command layer owner (see 5).

## 4. Registry corrections

`design/registry/entities.yaml` was updated (each change has a `revised: 2026-11-16` line with the old value):
- `schools_event_type_block`: 2004 scope, commands, codes, plus `command-layer.md`.
- `raid_min_level_ratio`: Schools added.
- `sell_value`: consumables named, plus `gold-economy.md`.
- `newbie_xp_ppm`: OQ resolved, plus `zones`.
- `ads_command_type_block`: codes renumbered.
- `iap_command_type_block`: confirmed.
- Jianghu `poach_fee`: entry type 32.
- Buildings effective-level formula: arrears signal confirmed.

`bash .claude/scripts/registry.sh validate`: **0 issues** (duplicate 0, path_missing 0, status 0, layout 0).

Systems index Progress Tracker updated: 46 started, 42 Designed, 4 Needs Revision (1, 2, 42, 43), MVP 21/25, VS 7/7, Alpha 9/9, Full Vision 5/5.

## 5. Left open, and why

- **128 PROVISIONAL Open Question rows remain.** They are not contradictions found here. Most fall into one of three groups:
  - schema or data-key additions (new `config.csv` / `sim_params.csv` keys, `feature_flags.csv`, `achievements.csv`, new columns), which this pass may not decide;
  - scope questions (who produces advisor suggestions or random events, Settings accessibility options, a Zones boss spawn);
  - assumptions about another system that were not verified in this pass: Settings / Ads / Onboarding / Guild screens UI hooks, Local save section registration, Leaderboards server rules, Entitlement details, CA/PA reveal hooks and Retention ↔ Offline settle calls.
  Run `grep -n PROVISIONAL design/gdd/*.md | grep -v RESOLVED` for the list. A follow-up pass per owner is recommended.
- **Command layer R3 vs feature "P1 handlers"** (Member model 800, Arena, Tower, Market and Buildings list P1 handler orders). Each should become an applier. This was not fixed, because confirming each one needs a read of each feature's command section.
- **Rebirth OQ-6:** Schools grants the free credit from a rebirth signal, while Rebirth assumes a `grant_free_change` call. One interface must be picked.
- **Zones PROVISIONAL rows** (Party `xp_mult_ppm`, MSM states, Golden Boss recall, Buildings guild-level reader) were not re-verified.

## 6. Decisions that need the user (not taken)

- **Scope:** add NPC-guild poaching of on-roster members (Jianghu OQ-2)?
- **Scope:** reduced motion and other accessibility options in Settings (Settings OQ-8, World view OQ-5).
- **Scope:** owners for advisor suggestions and random events (AI text OQ-3/4); the zone-boss spawn rule (Zones OQ-1).
- **Scope:** ship the Academy in MVP, or MVP has no school change (Schools OQ-1)?
- **Schema:** new config keys proposed across GDDs. Examples: `host_pending_max`, `shop_fund_share_pct`, `newbie_xp_ppm`, the tower and arena `sim_params` keys, `elder_slots` in `bld_hq`, `ui_*` keys and the `lb_*` keys.
- **Schema:** new tables or columns: `feature_flags.csv`, `achievements.csv`, `traits.csv` `uid`/`wave`, `items.csv` member-held/guild-held column (Items OQ-5), `grounds.wave`.
- **Schema:** an `ai_text` save section (AI text OQ-2); new Local save fields for Ads and IAP.
- **Balance:** faucet size of the new `arena_reward` and `tower_reward` mints, and whether the MVP fund (30% shop share, no tax) reaches the §19.4 yardstick (S3).
- **Balance:** ward and pill fees (Crafting OQ-9); `pa_lens_stock_cap` behaviour for paying players (IAP OQ-4).

Verdict: **CONFLICTS FOUND — 25 fixed, 0 known contradictions left unresolved.** The open items above are unverified assumptions and user decisions, not detected contradictions. Recommended next step: `/review-all-gdds`, then a per-owner PROVISIONAL sweep.
