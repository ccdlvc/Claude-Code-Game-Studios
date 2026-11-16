# Review Log — Realtime World View

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning)
Specialists: none (lean mode; game-designer, systems-designer, ux-designer and qa-lead lenses applied in the main session)
Blocking items: 3 | Recommended: 9
Summary: Complete (8/8 sections), well-structured and faithful to the "draw only, never decide" contract; registry values (tick_rate, fight_time_limit_s 600, raid_time_limit_s 300, view_full_sprites_max 15, view_damage_numbers_max 20) all match. Three defects block implementation: the F4 hysteresis is applied to squared distance, so the formula does not do what its text, example and AC-12 claim; R7 still names a provisional `fight_timeline(fight_key)` query that disagrees with the signatures Zones R12 and Golden Boss R8 now define; and the downstream interface the view offers Guild screens and Onboarding (focus calls, anchor IDs, screen rect) is undefined while the dependency tables still call designed GDDs "No GDD / PROVISIONAL". Creative-director pillar alignment remains NOT ASSESSED (no pillars or concept doc).
Prior verdict resolved: First review
Findings:
- [BLOCKING] F4 / AC-12: `score = d² − h²` subtracts a squared constant, so the "h px advantage" shrinks with distance (boundary at 200 px: a full sprite 30 px beyond scores 230² − 32² = 51,876 > 40,000 and is replaced); the example and AC-12 (30 px stays, 40 px replaced) are false. Use `score = |d| − (h if full)` or `(|d| − h)²`, then re-check the example.
- [BLOCKING] R7 / Interactions / Dependencies: R7 specifies `fight_timeline(fight_key)` [PROVISIONAL] and one query for raids, but Zones R12 defines `fight_timeline(party_id, trip_ordinal, encounter_ordinal)` and Golden Boss R8 defines a separate `raid_fight_timeline(raid_ordinal)`; R7, the fight playback states and AC-6/8/9 must use the owners' signatures and drop the PROVISIONAL tag (OQ-1/OQ-2 already say resolved).
- [BLOCKING] Dependencies (downstream) / OQ-4: Onboarding (44) hard-depends on view anchors `world_party`, `world_gate` and a focused-object screen rect (Onboarding OQ-7); Guild screens (39) expects "show on map" selection focus. This GDD names `focus_member(id)` / `focus_location(loc)` only in a provisional OQ with no signature, behaviour (does focus switch location, set Follow, clear on what) or AC. Define the contract; also fix the stale table rows (Settings, Guild screens, Onboarding, Audio exist and are designed) and the bidirectional-check paragraph.
- [RECOMMENDED] Interactions table: Settings row lists only reduced motion and a provisional damage-number toggle; R15 and Settings R12a also give `a11y_text_scale` and `a11y_element_palette` — use the key names.
- [RECOMMENDED] R10 / UI: the quick card's HP source during `Playing` is unspecified (playback HP is ahead of committed HP until the deadline tick); state which one the card shows.
- [RECOMMENDED] R6: `dead` "spirit follows the party home" does not say where the spirit is drawn while the party keeps hunting; `resting` "(or the trip's rest spot)" names no anchor.
- [RECOMMENDED] R8 / AC-11: `sell_s` range is 0–600 (Zones), so "never instant" and AC-11's `≥ sell_s − 0.1 s` break at `sell_s = 0`; give a minimum beat length or an edge case.
- [RECOMMENDED] R8: Skills V/A says 2102 is "the one skill event that may interrupt with a toast" with a chime; this GDD maps it to an F6-limited glow only — reconcile.
- [RECOMMENDED] R12 / AC-16: "one merged toast per category" never lists the categories; enumerate them (level-ups, raid result, arrivals, leave requests ...).
- [RECOMMENDED] F7: `debt_peak_us ≥ 1` is asserted but not enforced; entering `CatchingUp` with `debt_us = 0` (handoff only) divides by zero — state `max(1, ...)`.
- [RECOMMENDED] R16 / AC coverage: the `Background` state has no criterion of its own (AC-4 covers load, not focus loss: no draw while backgrounded, resume into `CatchingUp` by the flags).
- [RECOMMENDED] OQ-3 and OQ-8 are marked "before implementation" (where presentation knobs live outside the content hash; integer-scale stretch setting in 4.7) — schedule the Data layer decision and the ADR before the world-view epic.
Registry check: searched tick_rate, fight_time_limit_s, raid_time_limit_s, view_full_sprites_max, view_damage_numbers_max, sell_s, raid_full_sprites across the document; no value conflicts.
Reviewed-Content-Hash: design/gdd/realtime-world-view.md 7cd31abd632c70b6504f7a25d90fce0a7647d306
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/zones-grounds-monsters-and-hunt-trips.md e7660b1143a9be72097e81af96ac1721002560c9
Reviewed-Content-Hash: design/gdd/golden-boss-and-guild-raid.md 5095c1a5b93913caa332ea0ef6c1dfe820e3427b
Reviewed-Content-Hash: design/gdd/combat.md cf888cacc1802c9e3bf6b6b888e43e89ba7b9133
Reviewed-Content-Hash: design/gdd/member-state-machine.md a3076c148db9e4cf37e7f1b6b0fc2e5141980c41
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/gdd/onboarding-and-tutorial.md 2c478f90a0439cfd555335eb95dce08afe2f20ae
Reviewed-Content-Hash: design/gdd/skills.md 5ccd62bd5b0d5419255d23ca2b3f4b92244c9583
Reviewed-Content-Hash: design/gdd/recruitment.md 0a79a802cf96822cb3059aa827ec50c7416eb81a
Reviewed-Content-Hash: design/gdd/retention-leaving-and-negotiation.md 91d46c4b4dbdcd99a429121e589d1a9330d2da8c
Reviewed-Content-Hash: design/gdd/xp-and-level-pacing-curve.md 8b013cb956e1ab238db7f78e811a78b4e397e7fb
Reviewed-Content-Hash: design/gdd/guild-and-buildings.md a1e2ed200bc5f3e3cbe9f8cbdd016959127ead74
