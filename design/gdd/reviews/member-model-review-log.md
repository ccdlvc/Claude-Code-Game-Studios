# Member Model — Review Log

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L
Specialists: none (lean mode; game-designer, systems-designer and qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 9
Summary: All 8 sections present. F1–F3 and F6 arithmetic checks out against `data/`, and the single-writer / permanent-ID / derived-profile design is sound. The GDD was written against an older picture of its neighbours. It registers its own P1 handler with string `MM_*` codes, which the Command layer forbids. It disagrees with Items and loot about who owns bag capacity, and with Guild and buildings / the registry about `member_cap` (housing is missing). The F5 example and AC-15 also encode a wrong value. These are targeted fixes, not a redesign.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R6/R8/R10, Interactions, Dependencies: contradicts Command layer R2/R3/R6. Member model registers a P1 handler at order 800 that reads commands, but only the Command layer dispatcher may do that, and features register appliers. Refusals use string `MM_*` codes where integer shared 6–9 or owner codes ≥ 100 are required. No command IDs are allocated in block 800–899. Names (`equip`/`unequip`) differ from Command layer's `equip_item`/`unequip_item`. `create_member`/`remove_member` are listed as P1 commands but are in-sim APIs called from Recruitment/Retention appliers. `equip` taking an item the caller "already removed" and returning it on refusal breaks Command layer R5 "validate before mutating / refusal changes no state". Command layer (5) is absent from Dependencies.
- [BLOCKING] R1 / R6 / Interactions: bag (`inventory[]`) capacity has no owner. Member model says Items and loot owns the bag, while Items R8 (reason 6) says "Member model owns inventory capacity".
- [BLOCKING] R8 step 1, F6, Cross-References: `member_cap` is stated as bld_hq only (12 at HQ1, 40 at HQ8). Registry `member_cap` (Guild and buildings F2) is bld_hq + bld_housing, range 12–80, and `buildings.csv` has `bld_housing member_cap=+4/+8…`. F6 `roster_max` 12–40 and the "40 disciples" max-roster fixture are understated. Recruitment also checks the cap, so the double enforcement needs one stated owner.
- [BLOCKING] F5 example / AC-15: 2,000,000 × 3,906,347 // 4,101,664 = 1,904,762, not 1,904,750. A correct implementation fails AC-15 as written.
- [RECOMMENDED] R6 rule 6: hardcoded state list omits `bounty` (MSM eligibility table). Defer to MSM `can(equip)` instead of restating it, and fix the copy in Items R8.
- [RECOMMENDED] R9: removal requires `away`, yet `unequip` is blocked in `away`. State that the removal move to storage bypasses rule 6, as R6 already does for Schools.
- [RECOMMENDED] R7 / Edge Cases C: "re-derived and HP rescaled on the next read" makes a read mutate `hp_milli`. Specify the write-time trigger (level-up from XP, school change from Schools, equip) so F5 runs exactly once per change.
- [RECOMMENDED] Dependencies / OQ-7 / Interactions: Items and loot GDD now exists. Storage is uncapped and `give` always succeeds (Items R7), so drop "no GDD yet" and close OQ-7. Command layer's `equip_item` arg is item `entity`, but storage is keyed by `(content_id, enhance_level)` with no instance IDs, so reconcile the arg kind.
- [RECOMMENDED] R10: peak "8 events per tick" conflicts with the stated 5 × 4 re-gear and with MSM R7 step 0, which re-gears all living members in one `start_rest` call. Restate the peak including the paired 805 on a swap.
- [RECOMMENDED] Edge Cases A: the same-tick rename/remove outcome depends on Command layer `seq` order, not "earlier phase / P1 order". Rewrite it against `seq`.
- [RECOMMENDED] Edge Cases B: an `enhance_lv` above the table is save data. Make it a save-load validation (Local save 6), not a boot refusal.
- [RECOMMENDED] Acceptance Criteria: AC-7 should name the level-60 item it uses. AC-1 duplicates AC-2 (merge them). AC-21 depends on the PENDING Utility AI port and has no tolerance seed stated.
- [RECOMMENDED] States: MSM allows `equip` in `elder`, but Rebirth says Elders hand gear back and stop hunting. Confirm whether Elders may be re-equipped.
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/gdd/schools-and-school-change.md b468deba3ea43b60bb05cee1b5ae8ce989637c3c
Reviewed-Content-Hash: data/sim_roles.csv d0174397e89fadc341e0a8c3705579906db9e7a8
Reviewed-Content-Hash: data/items.csv 8dc7e745e5add4dbc9d8ccc2e0145fe60078d16c
Reviewed-Content-Hash: data/enhance.csv 1caa1ea8b4895ec769d084e82d5efac6f517dbe4
Reviewed-Content-Hash: data/buildings.csv fff45a345d60567f9b13e04635c761e954350389
