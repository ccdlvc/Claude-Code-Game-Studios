# Review Log — Audio (`design/gdd/audio.md`)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: M (4 small formulas, 6 upstream deps, cue table location may need an ADR per OQ-1; producer should verify)
Specialists: none (lean: game-designer, systems-designer, audio-director, qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 8
Summary: Complete (8/8 sections), well cross-referenced and consistent with the registry (channel_gain_db, raid_time_limit_s 300, raid_music_timeout_s 360, audio_cue_tier_priorities, max_event_subscribers 16; F1 example -3.88/-12.04 dB verified). It contradicts Guild screens on UI cues during catch-up and on the refusal cue, and the mixer has gaps that leave R6/R7 and AC-9/AC-12 undeterminable: the collapse key for event cues, T2 numeric priorities, the milestone queue order and what happens when a queued T2 gets no voice.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R6 step 1: UI-channel cues play during catch-up, but guild-screens.md Visual/Audio item 4 says all UI cues are suppressed while catching up except the summary. Pick one rule and align both docs.
- [BLOCKING] Detailed Design R4 / V/A cue list: refusal cue has two paths. Event 502 `command_refused` (ui bus, -6 dB) and Guild screens' `play_cue("ui_refused")` can both fire for one refusal, a tick apart, so collapse cannot merge them. Guild screens also says `ui_refused` "must be audible over gameplay", while Command layer V/A says it must be quieter than any combat or boss cue. Guild screens' UI cue names (`ui_tap`, `ui_confirm`, `ui_refused`, `ui_toast`, `ui_modal_open`, `ui_badge_new`) are not reconciled with Audio's "tap / open / close / confirm".
- [BLOCKING] Detailed Design R1/R6 step 2: the collapse `context` key is defined only for the UI channel (`member_id`). The doc does not say how event-channel cues (1502/801, 2401/2403, 1103) or the view-channel `combat_death` get a key: which payload slot, and what happens across channels for group `death`. AC-9 cannot be built as written.
- [BLOCKING] R7 / F2 / AC-12: most T2 rows have no numeric priority (1407 horn, 2102, 1502, 3004, 2202, 2403, 2001/2003, 1105), but R7 replacement and F2 compare integers. Queue drain order (FIFO or priority) is unstated. What happens to a queued T2 that F2 still refuses when its slot comes is unstated. AC-12 contains "…" and is not deterministic. Assign priorities, define order and re-refusal, and rewrite AC-12 with exact start times.
- [RECOMMENDED] States and Transitions: the `CatchingUp` row includes view `suppressed`, but the Active→CatchingUp and CatchingUp→Active triggers list only the facade flags.
- [RECOMMENDED] Player Fantasy: "Thirty seconds later they hear a roar" does not match Golden Boss R2/R5. 1401 comes 120 s before the due tick and gathering takes up to 120 s more, so 1401→1402 is 120–240 s.
- [RECOMMENDED] R8 Music: no music state is given for viewing the Raid arena outside a raid. The interaction of `report` with `raid` is unspecified, and so is whether `report_music_db` and `duck_db` stack.
- [RECOMMENDED] R1/R4: `gb_enrage` is T1 ("act or look now") but view-channel only, so it is heard only when the raid arena is on screen. That contradicts the off-screen-player fantasy. Make it an event cue or lower its tier.
- [RECOMMENDED] R4 / Game Feel: 1103 member downed is T1 in routine hunts (40 members, frequent wipes) with nothing for the player to act on. This risks breaking the "quiet by default" target. Consider T3 outside raids, or a per-guild collapse.
- [RECOMMENDED] Dependencies: offline-progress.md names its report cues but never names Audio (40). Settings and Guild screens still mark Audio PROVISIONAL. Bidirectional links are incomplete.
- [RECOMMENDED] Interactions: event-bus-and-history-log.md Overview calls audio a subscriber, while Audio says it is not one of the R4 subscribers and reads through the facade. Clarify on the Event bus side.
- [RECOMMENDED] Acceptance Criteria: AC-20 "about 300 ms" and AC-22 "within one frame of the settlement visual" need tolerances and a measurement method (logged timestamps). AC-23 "rates no cue as annoying" needs a scored threshold. AC-24 needs the min-spec device named.
Reviewed-Content-Hash: design/gdd/audio.md 91c604570afee95f59ab2648614d5a96349f6a0d
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/gdd/realtime-world-view.md 7cd31abd632c70b6504f7a25d90fce0a7647d306
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/gdd/ads.md 6aca4cbbabb22607ee97b4ca7ad39ace5a220630
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
