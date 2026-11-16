# Roadmap: from design to implementation

> Created 2026-11-16 after the batch /design-system + consistency-check run.
> State then: 46 systems indexed — 42 Designed, 4 Needs Revision (1 Sim core, 2 RNG,
> 42 Event bus, 43 Dev tooling). `project.yaml` stage: Concept.
> User decisions of 2026-11-16 are logged in `production/session-logs/decision-log.md`
> (skill `user-decision`) and propagated into the GDDs.

The studio pipeline has 7 stages, each passed with `/gate-check`:
Concept → Systems Design → Technical Setup → Pre-Production → Production → Polish → Release.

## Step 0 — Close the design (Systems Design)

1. Commit the design baseline.
2. `/design-review design/gdd/<name>.md` for every GDD, each in a fresh session (or a fresh
   agent — the reviewer must not inherit the authoring history). MVP GDDs first, in the
   systems-index design order.
3. Revise the 4 Needs Revision GDDs: `/design-system <name>` (resumes against the reviews in
   `design/gdd/reviews/`).
4. Write 3–5 game pillars (`/reverse-document` for a brief from `JX1_Tycoon_GDD.md`, or
   `design/gdd/game-pillars.md`). Every CD-GDD-ALIGN is NOT ASSESSED until pillars exist.
5. `/review-all-gdds`, then `/consistency-check` again (128 PROVISIONAL rows remain).
6. `/gate-check` → Technical Setup.

## Step 1 — Technical Setup

7. Install Godot 4.7.x; `godot --version`; `/setup-engine` to record the installed version in
   `docs/engine-reference/godot/VERSION.md`.
8. `/create-architecture` → `docs/architecture/`.
9. `/architecture-decision` — at least 3 Foundation ADRs. Proposed:
   - Determinism contract: integer/fixed-point math, per-event RNG seeding, no engine random.
   - Python reference + GDScript authoritative port, matched by parity vectors. Game code
     root is `src/` (`src/core/` for the headless sim), not `res://core/` as GDD §21 says.
   - Save format: no JSON numbers (ints as strings), header + checksum, gzip.
   - Tick loop, event bus and command dispatcher on Godot.
   - Simulation LOD: deterministic in-sim tier rule (Zones R17), camera visual only.
   - Platform plugins (billing, ads/consent, notifications) — not sourceable, need spikes.
10. `/architecture-review`, then `/create-control-manifest`.
11. `/ux-design` accessibility → `design/accessibility-requirements.md` (exact path; the gates
    check it), then the interaction-patterns library.
12. `/test-setup` — GdUnit4 + GitHub Actions; CI runs `make check` and `balance_sim --quick`
    (blocking quick gate per Dev tooling GDD).
13. `/gate-check` → Pre-Production.

## Step 2 — Pre-Production

14. Required spikes (PR-SCOPE):
    - Art spike: one paper-doll + 20 item icons via local Stable Diffusion, logged in
      `ART_LICENSE_LOG.md`. Fallback: code-drawn minimal style.
    - P1 performance spike on a real Android phone: raid size (`raid_max_participants` = 20),
      LOD defaults (`lod_detail_grounds` = 4, `lod_eval_ticks` = 600), 30 FPS budget,
      per-command cost. Use `/prototype`.
15. `/ux-design` for MVP screens (world view/HUD, member list, recruitment, menus); `/ux-review`.
16. `/create-epics`, then `/create-stories <epic>` for the MVP epics.
17. `/vertical-slice`, then `/gate-check` → Production.

## Step 3 — Production loop (per story)

```
/sprint-plan → /story-readiness <story> → /dev-story <story>
   → make check (+ balance-quick on any number change) → screenshot to production/qa/evidence/ if player-visible
   → /story-done → /sprint-status … → /retrospective at sprint end
```

Project shortcuts: `/validate`, `/test`, `/balance`, `/step S1…S9`.

## MVP implementation order

| Epic | Content | Note |
|---|---|---|
| E1. Bring the Python reference up to the GDDs | Audit fixes: `sim/model.py` stats cache key must include school; `sim/rng.py` randint → Lemire with rejection; gold-split conservation test; offline kills carry. Regenerate `data/recipes.csv` at 45% + validator rule fee ≥ sell value. `data/config.csv` offline cap 8/24 → 12. RNG per-event seeding, Data layer uid/ppm, integer formulas. Export parity vectors. | First — the GDDs changed a lot vs. the code |
| E2. Godot core port | `GODOT_PORT.md` steps 1–7 (rng → data → formulas → model → hunt → offline → raid), each checked against E1's vectors | Headless, no UI |
| E3. Sim infrastructure | Sim core tick loop, Command layer, Event bus, Local save | |
| E4. Gameplay MVP | Member model + state machine, Combat, Zones/hunt with LOD, Party, Utility AI, XP, Skills (tho_1, moc_1, hoa_2), Items/loot, Gold economy with flat tax, 5 buildings, Recruitment slice, CA/PA slice, Offline | Golden Boss after the P1 measurement |
| E5. Presentation | Realtime world view, MVP Guild screens, localization keys | Screenshot evidence per screen |

Then Vertical Slice (traits, retention, market, crafting, quests, Linh Bảo shop — includes
`items.csv` ward `craft_only`/`lb_price`), then Alpha (ads, IAP, entitlement, cloud save,
leaderboards).
