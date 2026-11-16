# Revision clusters — Option A step 2 (2026-11-16)

Source: latest `## Review` section of all 46 `design/gdd/reviews/*-review-log.md`.
193 BLOCKING issues total. Raw extract: grep `[BLOCKING]` per log.

## Cross-GDD rule (applies to every cluster)
1. **The provider of an interface is authoritative.** A consumer aligns to the provider's signature/state names.
   When the consumer needs something the provider lacks, the *provider's* cluster adds it (inbound request).
2. **Inbound requests:** each cluster agent greps ALL review logs (not only its own) for its GDD filenames and
   system numbers, and resolves blocking items that ask its GDDs to add/change something.
3. **Command layer (5) mirrors owner GDDs** for command names/args; owners allocate IDs in their blocks; reason codes
   owner-range ≥ 100.
4. **Stale "No GDD / PROVISIONAL / Not designed" dependency rows**: every cluster re-verifies every row against the
   existing GDD (all 46 exist) — mechanical, no user decision.
5. **Offline cap is 12 h for everyone** (registry `offline_cap_free_h`, `offline_cap_premium_h` deprecated). Fix any 8 h / 24 h text.
6. **Timer owners adopt Offline progress R8** (register Paused/Elapsing at boot, `settle_to(to_tick)`); no invented hooks.
7. **Member state machine (41) is the authority on states**; consumers gate on `can(...)` / its enter_* APIs.
8. User decisions (below) are applied as given; any other new design question → log as OQ, do not invent.

## Clusters (disjoint file sets)

| C | GDDs (system #) | Blocking | Notes |
|---|---|---|---|
| C1 Determinism & data | deterministic-rng (2), data-layer (3), dev-tooling (43) | 22 | mostly internal rigour |
| C2 Runtime spine | sim-core (1), event-bus (42), command-layer (5) | 22 | command vocabulary mirrors owners; sim-origin queue on save |
| C3 Member & progression | member-model (8), ca-pa (9), recruitment (15), schools (20), skills (21), xp (22), rebirth (23) | 26 | create_member spec (+pa_key, skills, pa_exact, reveals, salary for Jianghu), candidate CA, reveal_on_rebirth / grant_free_change sync calls, member_cap 12–80 |
| C4 Hunt loop | combat (10), zones (11), utility-ai (12), party (13), golden-boss (14), member-state-machine (41) | 19 | MSM adds tower state + enter/leave (inbound from 19), recall closes trip, raid parity |
| C5 Economy | items (26), gold (27), crafting (28), market (29), guild-buildings (30), enhancement (24), quests (25) | 23 | Ward source, ppm ×10⁴, F5 overflow, roll_guild_loot_keyed (inbound from 19), building commands |
| C6 Persistence & money | local-save (6), account-cloud (7), entitlement (32), IAP (34), leaderboards (35) | 22 | Local save adds grant fields, export/import contract, ready signal for Ads |
| C7 UI shell | realtime-world-view (38), guild-screens (39), onboarding (44), settings (45), ads (33) | 18 | Ads owns banner band; Settings adds tips/AI/push keys + privacy rows; anchors `ui_anchor.<screen>.<control>` |
| C8 Services | localization (4), analytics (37), audio (40), ai-text (36), push (46) | 22 | name lists in i18n, consent, cue rules |
| C9 Late game & offline | offline (31), retention (16), jianghu (17), arena (18), tower (19) | 20 | Arena aligns to Jianghu API; carry across gaps; clock base |

Total 194 (one cross-listed). Run C1–C9 in parallel (disjoint files); registry `design/registry/entities.yaml`
and `systems-index.md` are shared: re-read before each edit, change only own rows, retry on conflict.

## User decisions (2026-11-16) — filled in after the user answers
(see production/session-logs/decision-log.md)
- D1 Ward: craft + 60 LB (Crafting R9 rewritten). -> C5
- D2 Founding: fixed seeded pool, reject-all advances board, last board not rejectable. -> C3 (recruitment)
- D3 Horn recall keeps the skip (intended value). -> C4 (zones, golden-boss)
- D4 Weekly lens: backlog boss -> any Golden Boss N times; upgrade_building only while available, else swapped. -> C5 (quests)
- D5 Raid parity: Combat GDD matches reference code exactly; no sim_version bump. -> C4 (combat)
- D6 Offline: persist per-group carry across gaps in save. -> C9 (offline); C6 local-save notes section field
- D7 Push boss_announced default off. -> C8
- D8 Analytics: buffer in memory until consent; send on opt-in, discard on decline. -> C8
