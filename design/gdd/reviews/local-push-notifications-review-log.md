# Review Log — Local Push Notifications

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (11 dependencies, 5 formulas, engine ADR needed for Android scheduling and desktop toasts — OQ-8; producer should verify)
Specialists: none (lean — systems-designer, game-designer, qa-lead, ux-designer and engine lenses applied in-session)
Blocking items: 4 | Recommended: 10
Summary: All 8 sections are present and the formulas check out against the registry (tick_rate 10, golden_boss_interval_min 60, golden_boss_backlog_max 3, offline_cap_free_h 12) and the AC worked numbers. Four things block it. Five dependency rows are out of date. The Overview still states the retired 8-hour cap. Default-on hourly desktop boss notifications contradict the Player Fantasy this GDD chose. And the suspend schedule uses the wrong time anchor when a hand-off is pending.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Dependencies / Interactions / OQ-1–4: Settings (45), Onboarding (44), Analytics (37), Realtime world view (38) and Guild screens (39) are marked "No GDD — PROVISIONAL", but all five GDDs exist. Settings already conforms (its R2 and R3 note, row 6, OQ-5) and asks 46 to cite it and to define the preference key names, types and defaults for its R3 table. 46 defines none. Onboarding gives `ended` / event 4402 (R4) as the gate that R3.2 needs. Update the rows, close or re-scope the OQs, and add the Settings key table.
- [BLOCKING] Overview (line 18): "the 8-hour Free cap" contradicts R4, F2, AC-3, Edge Cases and the registry (`offline_cap_free_h` = 12 for every player, Offline R4, user decision 2026-11-16).
- [BLOCKING] R4 / R8.2 vs Player Fantasy: `boss_announced` (live, event 1401) is on by default, and it fires every hour, plus horn summons, while the desktop window is minimised. The Player Fantasy rejected framing (B) "the hourly drum" as a default because "hourly messages contradict Idle / AFK", and it asks for "very few messages". Choose one: make it default off like `boss_soon`, or justify why desktop is different, and set `notif_max_live_per_hour` to match.
- [BLOCKING] R5.1 / F1 / F2: when the suspend save is refused because a hand-off is pending, R5.1 "proceeds" on the old committed state but still anchors on `suspend_utc`. The committed `tick` stands for an earlier wall time: the last save, before the unresolved gap. The next absence is measured from `last_saved_utc` (Sim core R14). So `cap_reached_utc` and the slot times come out late by up to the pending gap. Either do not schedule in that state, or anchor F1/F2 on the save's own wall time (`last_saved_utc` / `hw_utc`), and add an AC.
- [RECOMMENDED] R4 `rare_candidate`: event 1501 `recruit_offer_opened` carries "best half-stars shown". The "four stars or more" threshold is not a data knob, is not stated in half-stars (≥ 8), and the ICU "candidate star count" argument needs the same unit.
- [RECOMMENDED] Edge Cases: missing Android device reboot during the absence. AlarmManager or scheduled notifications are cleared on reboot unless they are re-registered on BOOT_COMPLETED. Doze can also delay inexact delivery well past the 10-minute `boss_soon` lead. State the policy, or accept the loss explicitly. Feed it into OQ-8.
- [RECOMMENDED] Edge Cases (first bullet): "whatever the last suspend scheduled stays pending and may fire" contradicts R5.6. Every resume cancels all pending notifications, so a crash in the foreground leaves nothing pending, which means no cap notification for that absence. Reword it, and accept or mitigate.
- [RECOMMENDED] R3.2: "never within the first session" is undefined (no session boundary is defined anywhere). Also, "missed boss" is ambiguous against Offline R11's summary fields "bosses won, lost and missed". Name the field.
- [RECOMMENDED] R12 vs Tuning Knobs / F5: R12 says "start and end hour", while the knobs and F5 use minute-of-day (0–1,439). Pick one granularity for the picker.
- [RECOMMENDED] Acceptance Criteria: AC-14's "no store, ad, sale or premium wording" needs an explicit forbidden-term list per locale to be pass/fail. R10 (tap routing, unknown-kind payload ignored) has no automated AC, and the unknown-kind case is unit-testable. Nothing tests the R7 live-path drop during quiet hours, the R2 "nothing in foreground / on web" rule, or that R12 preferences sit outside the save.
- [RECOMMENDED] Bidirectional dependencies: Analytics (37) and Realtime world view (38) do not list 46. Guild screens (39) has its own in-app notification queue (R8), and its relation to the OS notifications is not stated.
- [RECOMMENDED] OQ-8: the engine feasibility of Android local scheduling (plugin, channels, POST_NOTIFICATIONS, inexact alarms) and desktop toasts is NOT SOURCEABLE. An ADR and a device spike are needed before the epic.
- [RECOMMENDED] Visual/Audio: `boss_backlog_full` is a Golden Boss message but goes on the "Guild news" channel, while `boss_soon` gets its own "Golden Boss" channel. Confirm this grouping is what a player muting "Golden Boss" expects.
- [RECOMMENDED] Header / CD-GDD-ALIGN: no pillars or concept doc exist (`design/gdd/game-concept.md` absent), so there is no lore or pillar alignment check (OQ-10 stands).
Registry values: searched tick_rate, golden_boss_interval_min, golden_boss_backlog_max, offline_cap_free_h, offline_cap_premium_h, offline_threshold_s, notif_* and "8 h|24 h". The only conflict is line 18 ("8-hour Free cap"). Line 7 cites the old split only as overridden. The F2 range line (170) is within the knob range.
Reviewed-Content-Hash: design/gdd/local-push-notifications.md b0369a56c1fbe4b2a63e0f764ee1a6ce365123ed
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/localization.md 4f526afa5088f0dc117a1a76231ef2a6d3829a56
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/gdd/endless-tower.md e962f7799a12b16baeae8120add5c5c0a27d961b
Reviewed-Content-Hash: design/gdd/rebirth-and-ascension.md 6918c6a05712973f7b3bd37e5521e8f780edb138
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/gdd/onboarding-and-tutorial.md 2c478f90a0439cfd555335eb95dce08afe2f20ae
Reviewed-Content-Hash: design/gdd/analytics.md a425a3ababa71b12fc0babedb4012cb62b91fd42
Reviewed-Content-Hash: design/gdd/realtime-world-view.md 7cd31abd632c70b6504f7a25d90fce0a7647d306
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
