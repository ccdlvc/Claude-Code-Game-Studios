# Review Log — Settings (design/gdd/settings.md)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: M (producer should verify before sprint planning)
Specialists: none (lean mode; lenses applied in-session)
Blocking items: 3 | Recommended: 9
Summary: Complete (8/8 sections), well-structured host-service spec whose registry values (channel_gain_db, volume_slider_step = 5, settings_write_debounce_ms = 1000) all match. F1 and F2 check out at their boundaries. It blocks on three points: R13 conflicts with the now-Designed Ads GDD; the R6 forward-compatibility rule corrupts preferences on a downgrade; and the store state machine does not cover writes that start without a player action.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Detailed Design R13 / Dependencies: conflicts with ads.md (Designed). Ads R4.5 shows "Ad privacy settings" to every Free player, but Settings R13.2 and AC-13 show it only when the SDK requires it. Ads R3 makes the first-launch privacy notice reachable again from Settings → Privacy & ads, and R13 has no Privacy notice row. Ads and Audio are listed as "Not Started — PROVISIONAL" although both GDDs are Designed (OQ-6/OQ-7 can be resolved against them).
- [BLOCKING] Detailed Design R6/R7 + Edge Cases: an older build reading a higher-version store "reads the keys it recognises". But a version bump happens exactly when a known key changes meaning or type, so the old build misreads that key and then drops or overwrites it on write (R7), corrupting the newer build's preferences. Related: R7 says an unshipped `locale` is "dropped on the next write", while the Edge Case keeps it "until the player picks a language". Pick one rule. On a higher version, the build should treat changed keys as read-only.
- [BLOCKING] States and Transitions / F2: `Loaded` exits only to `Clean`, yet a loaded store can need an immediate write: missing or zero `install_id` (R5.2, Edge Cases), migration on load (R6), or keys rejected or rounded by R7. That makes "disk matches memory" false. The write-back after `Recovered` has no F2 trigger (no `t_last_change`, no flush event), so AC-7's Recovered → Dirty → Clean path has no defined timing.
- [RECOMMENDED] R4: the a11y keys (`a11y_text_scale_options`/`_default`) come from data, but the boot, loading and boot-failure screens render before the Data layer is Ready. Add a compiled fallback, as Localization's core string set does. Also say what Audio plays on the failure screen when volume defaults are unresolved.
- [RECOMMENDED] Tuning Knobs: the `volume_slider_step` safe range 1–10 allows steps that do not divide 100 (3, 6, 7, 8, 9), so the slider cannot reach 100 (0 dB). Restrict it to divisors of 100 and make "defaults are multiples of the step" a content-validator rule.
- [RECOMMENDED] Dependencies (bidirectional): realtime-world-view.md lists only reduced motion, still as PROVISIONAL "No GDD", and does not know about text scale or the palette. Its damage-number toggle request and Guild screens' haptics request are not answered here.
- [RECOMMENDED] Cross-tier: Guild screens (MVP) AC-18 needs `a11y_text_scale` = 150, but Settings is Vertical Slice. State how MVP screens get the key, or move the AC.
- [RECOMMENDED] R8/R12 / Interactions: cite Audio's actual interface `apply_volumes(vol_master, vol_music, vol_sfx, vol_ui, mute_all)` and the preview cues `ui_preview`/`sfx_preview` (audio.md R10), and drop the stale PROVISIONAL tags on R12/R13.
- [RECOMMENDED] Acceptance Criteria: no AC covers the R12.3 preview cue or its suppression under Mute all, a change made during `Writing`, or the R14 divider before destructive rows. AC-15 hardcodes 10 Hz and 600 ticks; write it as 60·`tick_rate`.
- [RECOMMENDED] F2 Output Range: "at most once per debounce window while a slider is dragged" contradicts "one write 1 s after release". Continuous dragging produces no write until release.
- [RECOMMENDED] Header: Status still reads "pending /design-review".
- [RECOMMENDED] Acceptance Criteria: AC-19 sits after AC-23, so the numbering is out of order. Renumber or reorder.
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/audio.md 91c604570afee95f59ab2648614d5a96349f6a0d
Reviewed-Content-Hash: design/gdd/ads.md 6aca4cbbabb22607ee97b4ca7ad39ace5a220630
Reviewed-Content-Hash: design/gdd/deterministic-rng.md bb6db49beac3e05ec31e45e5d2d277c6acfa8646
Reviewed-Content-Hash: design/gdd/account-and-cloud-save.md 1d2ee76c49defdfb7cc8aae45a3b1ecb6e18403c
Reviewed-Content-Hash: design/gdd/localization.md 4f526afa5088f0dc117a1a76231ef2a6d3829a56
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/gdd/realtime-world-view.md 7cd31abd632c70b6504f7a25d90fce0a7647d306
Reviewed-Content-Hash: design/gdd/local-push-notifications.md b0369a56c1fbe4b2a63e0f764ee1a6ce365123ed
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
