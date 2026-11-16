# Review Log — In-app Purchases (Premium, exact-PA items)

## Review — 2026-11-16 — Verdict: NEEDS REVISION
Review mode: lean · Workflow: full
Scope signal: L (producer should verify before sprint planning) — 11 dependencies, 4 formulas, ADRs needed for the billing plugin, Edge Functions and store webhook
Specialists: none (lean mode; systems-designer, economy-designer and qa-lead lenses applied in-session)
Blocking items: 4 | Recommended: 6
Summary: Structurally complete (8/8) and the core ledger + idempotent-grant design (R5, R8, F4) is sound: no erase, no duplicate, no power sold. It is held back by a hard upstream dependency that does not yet persist the fields the design rests on, one acceptance criterion that contradicts its own formula, an ill-defined price-rounding function with a wrong output range, and a registry ownership conflict on the two free-lens knobs. Several PROVISIONAL notes are stale: the Entitlement, Quests and Leaderboards GDDs now exist and answer OQ-4, OQ-5 and OQ-8.
Prior verdict resolved: First review
Findings:
- [BLOCKING] Dependencies / R8 / OQ-11: Local save and migration (6), a hard upstream dependency, never mentions `store_grants_applied`, `store_grants_revoked` or the pending-receipt side file. The no-duplicate and no-erase guarantees depend on fields their owner does not persist or migrate. Local save must add them (format, default for saves that predate them, atomic side-file write) before implementation.
- [BLOCKING] Acceptance Criteria AC-9 vs F4: F4's `grants_to_revoke` excludes refs already in `store_grants_revoked`, so a second reconcile submits nothing and can never produce `103`. Rewrite: "a second reconcile submits no command; a hand-submitted `revoke_store_item(item_pa_lens, 5, 41)` is refused with 103 and changes nothing."
- [BLOCKING] Formulas F1 (and F2 by extension): `tier_round` ("nearest .99 tier at or above the result's dollar") is ambiguous, and it contradicts the stated output range. p_lens = 0.49, n = 1 rounds to 0.99, not 0.49. p_lens = 1.99, n = 15 with a small d gives about 29.99, not "~15". Define the tier ladder as data (or as an explicit rule) and recompute F1's and F2's output ranges.
- [BLOCKING] Registry Values / Tuning Knobs (lines 260–261): the registry gives `source: design/gdd/in-app-purchases.md` for `pa_lens_weekly_free` and `pa_lens_stock_cap`, but this GDD says both are owned by Quests (25), and Quests F5 (`free_lens_grant`) now defines the cap's meaning. The registry comments are also stale ("not designed yet", "PROVISIONAL for Quests"). Re-source both entries to quests-and-achievements.md, or change the GDD's ownership claim. One owner only.
- [RECOMMENDED] Interactions / R6 / R9 / Edge Cases / OQ-4, OQ-5, OQ-8: stale PROVISIONAL text. Entitlement (32) exists and R5 answers OQ-5 (72 h provisional grant). Quests (25) exists and F5 counts paid plus free stock against the cap, which matches R9 (so OQ-4 can close). Leaderboards (35) R7.6 rejects unissued `grant_ref`s with 3506, which answers OQ-8 and the "Not defended locally" edge case. Update the table rows that say "GDD not written" and close these OQs.
- [RECOMMENDED] R4/R5/R8: `verify_purchase` receives `guild_uid`, but the grant is stored with `bound_guild_uid = null` and goes to whichever guild claims first. The parameter is unused, and a purchase made in guild A can land in guild B on the same account. Either bind at verification to the purchasing guild or drop the parameter and state the first-claim rule as intended.
- [RECOMMENDED] R10 / OQ-13: restore re-binding is last-restore-wins with no limit. Combined with Entitlement R6 (a cached `true` never downgrades on its own), one store purchase can serve several game accounts, and an offline device keeps the unlock indefinitely. Decide the cooldown/limit before Alpha.
- [RECOMMENDED] F2/F3 / OQ-3: in the example, free supply covers about 83% of lens demand (L_paid = 6 of 36), so Thiên Nhãn's price rests entirely on its floor. Treat the balance-simulator run as a precondition for Alpha pricing, not a follow-up.
- [RECOMMENDED] Acceptance Criteria: R12 (no purchase prompt during the Golden Boss or the conflict screen, no countdowns) and R13 (signals) have no criterion. R12's prompt suppression is testable via UI state, so add an [Integration] AC for it.
- [RECOMMENDED] Game Feel: the 300 ms / 100 ms / 3 s targets are not tied to any AC or measurement method. Add a [Device] check to AC-20 or mark them non-gating.
- [NICE-TO-HAVE] Header: Quick reference says Layer `Feature`, while the systems index category is Meta.
- [NICE-TO-HAVE] systems-index.md line 297 still says IAP "depends on Account and cloud save (7) only", which contradicts row 34's Depends On (index fix, not GDD).
- [NICE-TO-HAVE] Registry `iap_grants_to_deliver` output_range [0, 15] is per grant, while F4 states per-reconcile 0 – 15 × N_purchases. Clarify the comment.

Dependency graph: all declared GDDs exist on disk (account-and-cloud-save, command-layer, items-and-loot-tables, local-save-and-migration, data-layer-and-content-pipeline, localization, entitlement-and-feature-flags, ca-pa-and-traits, quests-and-achievements, settings, guild-screens, analytics, leaderboards-and-anti-cheat, ads).
Registry values checked: iap_grants_to_deliver, free_lens_grant, pa_lens_weekly_free (1), pa_lens_stock_cap (5), iap_command_type_block (3400/3401/3402, codes 101–103). Values agree; the conflict is ownership only (above).
Lore/pillars: no game-concept, game-brief or narrative files exist; checked against GDD §2/§11 as quoted. No rule sells power (R2c, AC-16).

Reviewed-Content-Hash: design/gdd/in-app-purchases.md 8c7664cce9b979a920419c261cd24312c068259b
Reviewed-Content-Hash: design/registry/entities.yaml 92a96589851cdb25b077e3bec8bb06b07d713a74
Reviewed-Content-Hash: .claude/skills/design-review/SKILL.md 4dcc8b81162613c757144532f1b72708ab3ba27f
Reviewed-Content-Hash: design/gdd/account-and-cloud-save.md 1d2ee76c49defdfb7cc8aae45a3b1ecb6e18403c
Reviewed-Content-Hash: design/gdd/command-layer.md 136a2ddaa9bb93fb451412e9e383e78d453b66fa
Reviewed-Content-Hash: design/gdd/items-and-loot-tables.md 34270ec0530cc9a076b548130100df2a73f1284d
Reviewed-Content-Hash: design/gdd/local-save-and-migration.md d315aea1f283dd6599e7b70a5e4b22b69b422f79
Reviewed-Content-Hash: design/gdd/entitlement-and-feature-flags.md e988772d3723b158efa58a36578ef586a578bf44
Reviewed-Content-Hash: design/gdd/quests-and-achievements.md e7d8bef5eb5406eb19cbbfb37a06298bf63ae89d
Reviewed-Content-Hash: design/gdd/ca-pa-and-traits.md 6f94b9f89498c0384ce2e725fc215b4349c0a346
Reviewed-Content-Hash: design/gdd/leaderboards-and-anti-cheat.md 36124b2475f1e23092510a18f6f1bb4d92a0ae06
Reviewed-Content-Hash: design/gdd/settings.md 93cdd10c26fda82cc58b2565597445ca9f32059d
