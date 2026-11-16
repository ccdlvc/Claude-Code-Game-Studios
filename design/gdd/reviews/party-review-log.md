# Review Log — Party (design/gdd/party.md)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (multi-system integration, 4 formulas, command/event table ADR pending; producer should verify)
Specialists: none (lean mode; game-designer, systems-designer and qa-lead lenses applied in-session)
Blocking items: 3 | Recommended: 7
Summary: Complete (8/8 sections), deterministic and mostly precise; F1, F2, F3 arithmetic and the AC-2 pick sequence check out against Utility AI F3. Three defects block: the hand-over rule lets a party that is already OnTrip start a second trip with a newly added member, the roster bound of 40 contradicts the registry's member_cap range (12–80), and the registry's event range for the 1300 block (1301–1307) disagrees with the GDD's six events.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R3 step 3 / R4 / Edge Cases: hand-over returns a group for any party with one idle member with a hunt intent and does not exclude OnTrip parties, so a member added to an OnTrip party (R4) is handed over as that party's roster and starts a second concurrent trip; contradicts the Edge Case "Party never hands them over alone" and R5's "a member leads at most one trip at a time". Restrict step 3 to Assembled parties (and say members of OnTrip parties are held).
- [BLOCKING] Formulas F3 / F4 / Core Rules ai-programmer lens / AC-24 / AC-25: roster bounded at 40 ("member_cap at headquarters level 8"), but registry `member_cap` (Guild and buildings F2) is cap_hq + cap_housing = 12–80. F3 max becomes 80 × 4 × 80 = 25,600 calls; the max-roster fixture (40 disciples, 8 parties) and F4's 400/day and 56-records peak must be re-derived at 80 members / 16 parties.
- [BLOCKING] Detailed Design R18 vs registry: registry `party_event_type_block` notes "events 1301-1307"; the GDD defines 1301–1306. Reconcile (fix the registry note or add the missing event).
- [RECOMMENDED] R4 / R8 row 4 / Game Feel: R4 allows out-of-band manual parties, but on the free tier R8 drift removes those members after their first trip, so the permission lasts one trip and "Auto never fights the player" is not true. Exempt manually created members from drift, or warn at create time.
- [RECOMMENDED] R13 `set_leader` / R6: does the new leader move to slot 0 (combatant order, R1 invariant party_id = slot-0)? R6 says so for automatic succession only; also state that set_leader emits 1305.
- [RECOMMENDED] R18 / F4: unspecified whether disband emits 1304 per member and whether Form emits 1303 per member; F4's 56-record peak assumes joins are emitted. State it.
- [RECOMMENDED] F4: the 400/day bound is asserted ("only a small share change membership") with no derivation; give the expected share or mark the number provisional until AC-25 measures it.
- [RECOMMENDED] Dependencies: Entitlement (32), Guild screens (39) and World view (38) are listed as "No GDD", but entitlement-and-feature-flags.md, guild-screens.md and realtime-world-view.md exist; update statuses, PROVISIONAL-1 and the PENDING reasons of AC-21 / AC-29.
- [RECOMMENDED] Interfaces: Member state machine trip step 2 calls Party "R9 `trip_roster`"; Party names the interface `groups_for_trips(N)` (R14). Align names.
- [RECOMMENDED] Game Feel: "×1.29 → ×1.39" describes swapping a fourth DPS for a buffer; adding a buffer to the 3-member example is ×1.21 → ×1.39. Say which.
Registry values: searched party_max, party_xp_mult_ppm, buffer_atk, buffer_dmg_reduction, member_cap, tick_rate, kill_base_milli, party_event_type_block, level_spread; 30 lines; conflicts: L269 member_cap ≤40 vs registry 12–80; R18 (L162–171) events 1301–1306 vs registry note 1301–1307. F1 output range 1,000,000–1,470,000 and party_max 5 match.
Reviewed-Content-Hash: design/gdd/party.md 6d61064e0aa51fe0b2623d9fa43792cd0a330c11
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/utility-ai.md 9623faf37b9dba716b70349067a807abd4166ff5
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/entitlement-and-feature-flags.md e988772d3723b158efa58a36578ef586a578bf44
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
