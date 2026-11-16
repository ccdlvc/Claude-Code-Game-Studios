# Review Log — Ads (banner, rewarded, consent)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (3 formulas, 13 dependencies, plugin/consent ADR required; producer should verify)
Specialists: none (lean — game-designer, systems-designer, qa-lead, ux-designer lenses applied in-session)
Blocking items: 3 | Recommended: 8
Summary: Complete (8/8 sections), F1–F3 verified against data/quests.csv (0.267 / 0.25 / 0.244 and the L=10 example all reproduce) and registry values match. But it was written before its dependencies existed, and three of its interfaces now disagree with them: its own sim state contradicts R1 and is unspecified, its Entitlement read (`is_premium` + `ready`) is not what Entitlement exposes, and the banner band is owned twice with different units and sizing rules.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Core Rules R1 vs R9 / Interactions (Local save row): R1 says Ads "holds no simulation state", yet it owns a sim command applier (3301), the sim-state set `ad_watches_applied`, and an implied per-day credit counter for refusal 104. No save section (`register_section`, Local save R6) is named, the counter is not defined as state at all, and "per local calendar day" (F2) is not a deterministic sim quantity — key it to Quests' daily period (`quest_clock` / `period_index`) and name the section that persists both.
- [BLOCKING] R2(b), Interactions, Dependencies, OQ-10: Ads reads `is_premium` and a `ready` flag; Entitlement (32) exposes `feature_on(no_ads)` (host scope, R8 row `no_ads`) with `source` 0 = default (Free) and no `ready` flag. The fail-closed gate cannot be implemented as written — define "definite Free" in Entitlement's terms (e.g. boot derivation done and `source` ≠ 0, or a ready signal Entitlement adds) and switch the read to `feature_on(no_ads)`.
- [BLOCKING] R6 / Tuning Knobs `ad_banner_fallback_dp` vs Guild screens (39) R2 / `ui_ad_banner_reserve_px`: two owners of the banner band. Guild screens fixes a 50 logical-px strip (range 0–90) "below the tab bar"; Ads sizes it from the SDK adaptive height (can exceed 50) with a dp fallback. Pick one owner, one unit, one rule; otherwise an adaptive banner overlaps the tab bar.
- [RECOMMENDED] Header/Interactions/Dependencies/OQ-10, 11, 13, 14: stale "PROVISIONAL — GDD not written" markers for Entitlement, Quests, Onboarding, Audio, Analytics, Settings, Local save — all GDDs now exist; reconcile and close.
- [RECOMMENDED] R9.3 / OQ-11: Quests R5 names the call `add_ad_progress(quest_uid) → ok | not_ad_quest | satisfied`; map those results to refusals 101/102 explicitly and use the name.
- [RECOMMENDED] R8 / Edge Cases (Premium): Quests R5 makes Premium ad slots "claimable without progress" (player taps Claim), not auto-claimed; and a watch earned after Premium is applied is refused 102 by Quests, contradicting "an earned callback is still credited". Reword both.
- [RECOMMENDED] R4.5 vs Settings (45) R13/Interactions: Settings shows Privacy options only "when required" via `privacy_options_required` / `open_privacy_options()`; Ads says the entry is shown to every Free player. Align and adopt Settings' interface names.
- [RECOMMENDED] R9.5: side-file records are replayed on launch, but `ad_watches_applied` is pruned to two periods and the applier ignores the record's `period_index` — a record surviving a failed delete past pruning credits twice. Refuse records whose `period_index` is older than the previous period.
- [RECOMMENDED] OQ-4: Analytics (37) R2 adopts its own opt-in after the R3 notice — close OQ-4 and cite it.
- [RECOMMENDED] States (Consent): the PC/Web `NoticePending → ConsentResolved` transition and the "consent resolved but SDK says no ads may be requested" outcome are not rows in the table; add them and their gate effect.
- [RECOMMENDED] Acceptance Criteria: AC-3 is a build inspection tagged [Logic]; AC-19 "differ only in quest-claim path, not in totals" needs stated inputs (Free watches every ad slot, Premium claims each) and the exact fields compared. Audio (40) OQ-5 also needs the rewarded start/close signal named (R12 `rewarded_state_changed` states enumerated).
Registry search: ad_reward_share, ads_command_type_block (3300/3301, refusals 101–104), ad_rewarded_daily_max (5) — all lines match the registry; no conflicts.
Reviewed-Content-Hash: design/gdd/ads.md 6aca4cbbabb22607ee97b4ca7ad39ace5a220630
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/entitlement-and-feature-flags.md e988772d3723b158efa58a36578ef586a578bf44
Reviewed-Content-Hash: design/gdd/quests-and-achievements.md e7d8bef5eb5406eb19cbbfb37a06298bf63ae89d
Reviewed-Content-Hash: design/gdd/guild-screens.md 352a323a9500e251571cf5ecdd4eb5c2de38414b
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/gdd/onboarding-and-tutorial.md 2c478f90a0439cfd555335eb95dce08afe2f20ae
Reviewed-Content-Hash: design/gdd/audio.md 91c604570afee95f59ab2648614d5a96349f6a0d
Reviewed-Content-Hash: design/gdd/analytics.md a425a3ababa71b12fc0babedb4012cb62b91fd42
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: data/quests.csv 305983eaa348bbb291b23fa8d80505003beca03a
