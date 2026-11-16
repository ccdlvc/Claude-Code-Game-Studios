# Review Log — Crafting and Recipes

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: M (producer should verify before sprint planning)
Specialists: none (lean mode; economy-designer, systems-designer, game-designer and qa-lead lenses applied in-session)
Blocking items: 2 | Recommended: 7
Summary: Structurally complete (8/8 sections) with sound, worked integer formulas: F1–F4 examples and AC-1/AC-10 arithmetic all check out against data/recipes.csv and buildings.csv, and the F2 no-profit invariant closes the craft-and-sell loop. Two cross-document defects block: the GDD states in three places that the Enhancement Ward is craft-only with no Linh Bảo path, while Gold economy R16 (user decision 2026-11-16) and Equipment enhancement sell it for 60 Linh Bảo, and the GDD's own downstream table already says so; and the R3 unlock gate calls an unkeyed `effective_level(building)` that Guild and buildings does not offer (its F4 is `effective_level(k, key)`, decay depends on the key, and its interface lists only the smith/jeweler/alchemy keys), so whether the gate decays for the four keyless workshops is undefined.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Core Rules R9, R11, Player Fantasy 3, Overview: "Ward has no other source (no drop, no shop, no Linh Bảo)" / "stays craft-only" contradicts Gold economy R16 (`lb_price_enhance_ward` 60), Equipment enhancement lines 12/24/47/133, and this GDD's own Downstream table (line 306). Pick one: rewrite R9/PF3 to "gold path is crafting; Linh Bảo shop is the earned-currency path", or take it to Gold economy R16 to remove the offer.
- [BLOCKING] Core Rules R3, F5, Interactions, OQ-3: the gate needs a building-level query with defined decay semantics for all seven workshops. Guild and buildings F4 is `effective_level(k, key)` (capacity keys never decay) and its Interactions/Downstream rows give Crafting only `max_craft_tier` and `craft_speed_mult` of three buildings. Resolve OQ-3 with Guild and buildings (add the query and list Crafting's use, or add a level-gate key to all seven) before implementation; AC-7, AC-15 depend on it.
- [RECOMMENDED] Formulas F6: "about 290 tier-1 swords per hour at Thiết Tượng Phô 1" is wrong; time_s 23, speed 1.08 → 213 ticks → ~169/h.
- [RECOMMENDED] Dependencies, provisional assumption 3: still says Items F5 names equipment only; OQ-7 marks this resolved. Remove or mark resolved.
- [RECOMMENDED] Dependencies, Bidirectional status: "Rebirth (23) is undesigned" is stale; rebirth-and-ascension.md exists and lists the Shrine recipe as a pill faucet (its line 187, OQ-14). Also Downstream row 23 "the only source of rebirth pills besides rebirth rewards" omits the Golden Boss drop Rebirth names.
- [RECOMMENDED] Tuning Knobs vs F3: `craft_batch_max` range is 1–100 in F3 but safe range 1–50 in Tuning Knobs; state one validator range.
- [RECOMMENDED] Core Rules R3 / V-CR4: Thiện Đường does carry `max_food_tier` (member shop gate), and food recipe levels do not match it (food_07 needs L4 while max_food_tier 3 is reached at L3; food_19 needs L10 vs tier 7 at L9). Say explicitly that the craft gate and the shop gate are independent, or add a V-CR rule aligning them.
- [RECOMMENDED] Acceptance Criteria AC-21: "crafts every recipe the materials allow" is not a fixed fixture; name the recipe set and order (e.g. every live recipe using only `mat_z05_1`, in uid order, max qty) so the test is deterministic.
- [RECOMMENDED] Open Questions OQ-5: shop stock tied to crafted output is a VS scope question that would change Gold economy R7 and Utility AI; needs a producer decision before VS sprint planning, as the GDD itself says.
- [NICE-TO-HAVE] Formulas F4: Output Range "24 game hours" assumes tick_rate 10; express as `86,400 × tick_rate` ticks.
Registry values: searched craft_gold, craft_unit_ticks, craft_gold_ratio (0.45), craft_batch_max (10), craft_queue_max (5), crafting_event_type_block (2800), ward 20,000 / pill 50,000; all consistent with the registry. Data spot-checks (recipes.csv): sword_01 gold 4 time 23, pot_hp_05 gold 60 (pre-regeneration, as OQ-1 states), ward inputs mat_z06_1:8; mat_z06_2:2 gold 20,000 time 600 (matches AC-22), pill 50,000 / 3,600 s.
Dependency graph: all 9 upstream and 7 downstream GDDs exist on disk; Sim core and RNG are Needs Revision.
Reviewed-Content-Hash: design/gdd/crafting-and-recipes.md ae31dfda676080b5aaba9627f9ca6d08c0bc3474
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/equipment-enhancement.md f34423bdf934dfc4fe6e0b7df0e00fe853e4b331
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
