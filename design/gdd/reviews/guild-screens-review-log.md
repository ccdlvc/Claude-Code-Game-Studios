# Review Log — Guild Screens (design/gdd/guild-screens.md)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (29 upstream systems, 5 formulas, shell/UX-spec and safe-area/haptics ADRs pending; producer should verify)
Specialists: none (lean mode; game-designer, ux-designer, systems-designer and qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 7
Summary: Complete (8/8 sections) and unusually precise on shared patterns (order acks, refresh gate, overflow-safe confirm threshold, notification priority); F1–F5 arithmetic and examples check out, and registry values (host_pending_max 200, member_name_max_len 20, party_max 5, member_cap ≤ 80, l10n_compact_threshold) match. It blocks because it was written while Ads (33), Entitlement (32), Realtime world view (38), Audio (40), Quests (25) and Settings (45) had no GDD, and all are now Designed: their contracts with Guild screens contradict or exceed what this GDD provides (banner-band ownership, feature_on gating and trial banners, world-view cards and focus calls), and F1 hardcodes a tick length Sim core makes configurable.
Prior verdict resolved: First review
Findings:
- [BLOCKING] R2 / Tuning Knobs / OQ-4 / Dependencies: `ui_ad_banner_reserve_px` (fixed 50 logical px, safe 0–90) duplicates and contradicts Ads R6, which owns the band height (SDK anchored adaptive height for the screen width, else `ad_banner_fallback_dp` 50, safe 50–90; AC-7 expects 56 dp from a fake SDK). Drop the knob, read band height from Ads; replace "provisional, no GDD" for 33.
- [BLOCKING] R7 / R9 / F3 / OQ-3 / OQ-12 / R8: gating uses a raw `premium` / `is_premium` bool, but Entitlement R1/F3 requires every gated check to be `feature_on(feature_id)` (rows `batch_orders`, `detailed_stats`, `themes` name Guild screens as consumer). Missing: trial banners from events 3201/3202 (`trial_started`/`trial_ended`) in the R8 table, and the `detailed_stats` screen OQ-12 says has no owner (EFF assigns it to 39). Entitlement row still says "not designed".
- [BLOCKING] R4 / Interactions / OQ-2: Realtime world view (Designed) R10, state table and OQ-4 require Guild screens to lay out the member quick card and the building card and to offer `focus_member(id)` / `focus_location(loc)`; R4's inventory has neither card and Interactions offers only an unnamed "selection focus". Add the cards (tier, owner data) and the two calls; resolve who draws the catching-up indicator (38 R12 overlay vs header R12).
- [BLOCKING] Formulas F1 / F2 / AC-20: `tick_us` is listed as "constant 100,000", but Sim core R1/F (registry `tick_rate`, config, valid 1–20 divisors of 1,000,000) defines `tick_us = 1,000,000 // tick_rate`. F1 must read it from the facade/config; F2's "every second tick" and AC-20's "about 100 ticks" assume 10 Hz.
- [RECOMMENDED] R15 / Edge Cases: "F1 (grouped) or F2 (compact)", "F4 fit", "F6" are Localization formula numbers, colliding with this GDD's own F1–F5 (F1 here is countdown, F4 is confirm). Prefix them (e.g. Localization F2).
- [RECOMMENDED] F3 / R9 / AC-11: Command layer F1 accepts a batch only if `host_pending + k ≤ host_pending_max`, so a part sized `host_pending_max` is refused whenever any host order is already pending (common while catching up). Size parts as `host_pending_max − host_pending`, and state whether the refused part's own members stay selected (AC-11 counts only parts 3–4).
- [RECOMMENDED] R8 / R13: notification table lacks the Ads first-launch privacy/consent screen (Ads R3–R5) and quest notices; give them a priority and kind.
- [RECOMMENDED] Dependencies / OQ-1 / OQ-5 / OQ-7 / OQ-8: refresh statuses — Audio (40, `play_cue` UI channel), Quests (25, quest board spec), Settings (45) are Designed; Sim core and Event bus remain Needs Revision. Sim core R15 still names only 38 and 40 for the facade, so the hard Sim core dependency stays provisional until Sim core's revision adds 39.
- [RECOMMENDED] Acceptance Criteria AC-20: "about 100" ticks over 10 wall seconds is time-dependent and imprecise; drive a fake clock and assert exact ticks with `pause()` never called.
- [RECOMMENDED] Acceptance Criteria AC-29: "reference mid-range Android phone" is undefined; name the device or spec (or point to the perf budget doc).
- [RECOMMENDED] Player Fantasy / AC-30: the chosen fantasy moment and its playtest rely on leave requests (Retention, VS) and rebirth (Alpha); give an MVP-testable variant (e.g. recruitment offer + injured member) so the MVP tier can validate the fantasy.
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/ads.md 6aca4cbbabb22607ee97b4ca7ad39ace5a220630
Reviewed-Content-Hash: design/gdd/entitlement-and-feature-flags.md e988772d3723b158efa58a36578ef586a578bf44
Reviewed-Content-Hash: design/gdd/realtime-world-view.md 7cd31abd632c70b6504f7a25d90fce0a7647d306
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/audio.md 91c604570afee95f59ab2648614d5a96349f6a0d
Reviewed-Content-Hash: design/gdd/quests-and-achievements.md e7d8bef5eb5406eb19cbbfb37a06298bf63ae89d
Reviewed-Content-Hash: design/gdd/offline-progress.md 68851067bc795a92c8a94554ce6c49b900d31e9c
Reviewed-Content-Hash: design/gdd/gold-economy.md 8b560ebe62cfd160080165f64b91df7e485b5de5
Reviewed-Content-Hash: design/gdd/localization.md 4f526afa5088f0dc117a1a76231ef2a6d3829a56
