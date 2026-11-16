# Review Log — Member State Machine (`design/gdd/member-state-machine.md`)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (multi-system integration, 7 formulas, ~14 dependencies; producer should verify before sprint planning)
Specialists: none (lean mode; game-designer, systems-designer, ai-programmer and qa-lead lenses applied in the main review)
Blocking items: 3 | Recommended: 10
Summary: Complete (8/8 sections), all 19 dependency GDDs exist, registry values match (need_max, decay/regen rates, eat_below, fatigue_rest_below, injury knobs, event block 4100) and data (food_01/04 satiety=60, bld_restaurant 1.1, bld_inn 1.12, bld_infirmary 0.05, revive_s 180, regen_pct_per_s 0.01). Formula examples and ACs 13–18 recompute correctly. Three rule-level gaps block implementation: unapplied hunt orders are completed by the wrong trip end, the P6 subscriber relies on another system's state against Event bus R6, and the recall path never closes the trip.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Core Rules R5/R9: 1104 completes "a `hunt` order held by any roster member", but R9 says an order given to a hunting member applies only at their next trip (and R10 step 3 marks only the lowest member_id's order applied). The current trip's 1104 therefore ends an unapplied order with outcome `completed` without it ever running. Gate completion on the order's `applied` flag (and define what happens to a group-mate's losing order); add an AC.
- [BLOCKING] Core Rules R5: the 1101/1104 subscriber uses `trip_roster(party_id)` (Party R9), which reads another system's state from a P6 subscriber; Event bus R6 forbids that and R5's own sentence says it "never calls another system from the subscriber". State that the roster comes from this system's own record of the start it submitted in R10 (saved per R17), or move the work to P2.
- [BLOCKING] Core Rules R8 / Hunt R10–R11: on a recall (1104 reason 4) there is no group rest, so `rest_ended(party_id)` is never called, and nothing states who deletes the trip record and releases ground occupancy. Golden Boss AC-6 expects "their trip is closed". Name the call and the tick (e.g. MSM calls `rest_ended` on processing reason 4, or Hunt closes on recall settlement) and add it to AC-8.
- [RECOMMENDED] States and Transitions T8, T11: cite "R10 step 2" for the fatigue rest; it is R10 step 3 (step 2 is Eat).
- [RECOMMENDED] Core Rules intro: "Rules are numbered R1–R17" but R18 exists.
- [RECOMMENDED] Formulas F3: output range max (3,600,000 ticks) assumes r_regen = 1,000, but the variable range starts at 1 (gives 3.6×10⁹ ticks); align the range with the validator floor.
- [RECOMMENDED] Formulas F4 / Tuning Knobs `eat_below`: "up to 6 points lost" and "keep 100 − eat_below ≥ satiety=" ignore `satiety_mult`; at Thiện Đường L8 (1.8, data/buildings.csv) a 60-point food restores 108 and wastes ~47. Fold the multiplier into the guidance or scale `eat_below`.
- [RECOMMENDED] Core Rules R10 step 2: food comes from "the Thiện Đường under its `max_food_tier`", but behaviour when the restaurant is unbuilt (`effect` = none) is not stated: is any food sold? This decides whether hunger exists before the building.
- [RECOMMENDED] States table: `idle` lists an "intent timeout" timer that no rule defines (R10 uses `ai_reask_ticks`); define it or replace it.
- [RECOMMENDED] Core Rules R6/R14: `enter_away` from `training` or `bounty` is neither allowed nor queued; state Retention's outcome (refuse with `MSM_STATE_BLOCKED`, or queue).
- [RECOMMENDED] Core Rules R6/R14: `leave_training`, `cancel_away`, `leave_bounty` move to `idle` without setting `decide_due_tick`; say it is set to the current/next tick.
- [RECOMMENDED] Acceptance Criteria AC-22: "exactly T1–T22 succeed and every other attempt returns a reason code" conflicts with queued `enter_away` (returns `ok`, no transition) and with T-rows triggered by events, not request calls; restate per request call with the expected result.
- [RECOMMENDED] Capability table / R15: Party "hard triggers from 4101 delivered in P6 of the tick the change happens" holds for P2-driven changes only; 4101 emitted from the P6 subscriber (1101/1104) lands next tick (Event bus R6). State the one-tick lag.
- [NICE-TO-HAVE] R3/R15: command IDs 4101/4102 reuse the numbers of events 4101/4102; legal if namespaces are separate, but name the namespace each time to avoid confusion.
- [NICE-TO-HAVE] Registry: MSM-owned entries list only this GDD in `referenced_by` although Retention, Golden Boss and Guild screens read them.
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: data/buildings.csv fff45a345d60567f9b13e04635c761e954350389
Reviewed-Content-Hash: data/items.csv 8dc7e745e5add4dbc9d8ccc2e0145fe60078d16c
Reviewed-Content-Hash: data/sim_params.csv 4ec1fa574f7c586911be2d5fffe47fab06ee276b
