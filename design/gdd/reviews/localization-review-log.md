# Review Log — Localization (vi/en)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: M (producer should verify before sprint planning)
Specialists: none (lean mode; systems-designer, qa-lead, ux and engine lenses applied in-session)
Blocking items: 4 | Recommended: 8
Summary: Structurally complete (8/8 sections), formulas F1–F5 are integer-exact and match their ACs, and registry values (format_compact, l10n_compact_threshold, ui_string_key_prefix) agree. But the GDD was written before most of its dependents existed and now conflicts with them: the person-name lists that Recruitment and Member model read from `i18n/` are not a catalogue this GDD defines, member renames are player text with no NFC rule, and the Realtime world view lets old-locale pops survive a switch that R7.3 forbids. F6 is too loose to implement without guessing.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Core Rules R3/R1: person-name lists (Recruitment R6/OQ-4, Member model R4 "generated from the i18n name lists") are read by the simulation from `i18n/` but are not defined here (file, columns, locale-independence, NFC/validator coverage, uid order); contradicts R1 "IDs only below the presentation line" and Data layer "loader never reads i18n".
- [BLOCKING] Core Rules R8: member names are renamable (`rename_member`, Member model R4), so they are player-entered text, but R8 treats them as a provisional name record and Member R4 has no NFC rule; R8/R4 must agree on NFC-on-rename and ownership.
- [BLOCKING] Core Rules R7.3: "no frame shows a mix of the two languages on one screen" conflicts with Realtime world view Edge Cases/R14 (transient pops finish in the old locale for up to `view_icon_s`); one document must change.
- [BLOCKING] Formulas F6: zero-unit behaviour undefined (3600 s → `1 giờ 0 phút` or `1 giờ`?), `ui_dur_join` values never given, and en plural rows for `{n}d/h/m/s` unspecified; AC-16 does not pin these cases.
- [RECOMMENDED] Dependencies / Open Questions: Member model, Settings, AI text layer, 38, 39 and 46 GDDs now exist; the "not designed yet" bidirectional notes and OQ-1/OQ-3/OQ-4 are stale (Settings R2 answered OQ-3 device-only; 46 R9 answered OQ-4).
- [RECOMMENDED] R10: AI text layer R8 stores `{m:<member_id>}`-style placeholders in cached text and expects them filled at display; this syntax is outside R4 and the formatter has no rule for it.
- [RECOMMENDED] R5 / OQ-10: Push notifications R9 asks for "ICU arguments" and a local `HH:MM` time; R5 defines neither ICU nor a time-of-day type.
- [RECOMMENDED] F3: claims CLDR rules but maps en −1 to `other`; CLDR uses the absolute value (`one`). Either drop the CLDR claim or fix AC-15.
- [RECOMMENDED] R5: no rule for which `count` argument selects the plural variant when a template has two counts.
- [RECOMMENDED] AC-20: "any name longer than 3 characters" match is undefined (case, whole-field vs substring, ID fields) and will false-positive on member names drawn from the name lists; define the scan precisely.
- [RECOMMENDED] Cross-doc: Settings ui-programmer note says "Vietnamese strings run ~30% longer than English", contradicting F4's measurement (English 1.2x median); fix in Settings via /consistency-check.
- [RECOMMENDED] F4: truncation must cut on grapheme-cluster boundaries, not code points.
- [NICE] F2 Output Range "about 13 characters" is 14 with a minus sign; say whether `ui_unknown_member` is in the R11 core set; say whether the 48-char key limit includes `_one/_other`.
Reviewed-Content-Hash: design/gdd/localization.md 4f526afa5088f0dc117a1a76231ef2a6d3829a56
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/gdd/member-model.md 6b7825174944540e5227d253ab4eb65710e578c2
Reviewed-Content-Hash: design/gdd/ai-text-layer.md 7fb82e64228d84f29c309f6081e141a1d1de5cf0
Reviewed-Content-Hash: design/gdd/local-push-notifications.md b0369a56c1fbe4b2a63e0f764ee1a6ce365123ed
Reviewed-Content-Hash: design/gdd/realtime-world-view.md 7cd31abd632c70b6504f7a25d90fce0a7647d306
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/gdd/data-layer-and-content-pipeline.md c3f4acefb5084f8b639f485e3d9714219f496da8
Reviewed-Content-Hash: design/gdd/sim-core-and-tick-loop.md 860d8037ca4fb3e1cb8048b156fef11e618287eb
Reviewed-Content-Hash: design/gdd/event-bus-and-history-log.md 30839f92ebbb29676909f42a5c772493b1014cfd
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/gdd/leaderboards-and-anti-cheat.md 36124b2475f1e23092510a18f6f1bb4d92a0ae06
Reviewed-Content-Hash: design/gdd/onboarding-and-tutorial.md 2c478f90a0439cfd555335eb95dce08afe2f20ae
Reviewed-Content-Hash: design/gdd/in-app-purchases.md 8c7664cce9b979a920419c261cd24312c068259b
Reviewed-Content-Hash: design/gdd/analytics.md a425a3ababa71b12fc0babedb4012cb62b91fd42
