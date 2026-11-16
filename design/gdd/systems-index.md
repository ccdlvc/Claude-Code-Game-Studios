# Systems Index: JX1 Tycoon (placeholder title — must be renamed before release)

> **Status**: Draft
> **Created**: 2026-11-16
> **Last Updated**: 2026-11-16 (all 46 GDDs authored: 42 Designed, 4 Needs Revision; cross-GDD consistency pass run)
> **Source Concept**: `JX1_Tycoon_GDD.md` v1.0 (repo root). `design/gdd/game-concept.md` does not exist; the user chose to map systems directly from the monolithic GDD. Section references (§) below point into that file.

---

## Overview

JX1 Tycoon is a commercial, solo-developed pixel 2D idle/tycoon game (mobile first: Android → iOS → PC/Steam → Web). The player is a guild master in a martial-arts world drawn from Vietnamese history and folklore. The core loop (§1) is the guild loop: members hunt in zones, carry loot home, the guild sells, crafts and upgrades, and members grow stronger — punctuated by an hourly Golden Boss that the whole guild fights together (§6.5, §6.13). Around that loop sit the management layers that make it a tycoon rather than an idler: recruiting members with hidden potential (CA/PA, traits — §5), keeping them (loyalty, mood, negotiation — §6.8), the two-tier gold economy and its sinks (§6.6, §19), and the long tail of rebirth and Ascension (§6.10). The game must keep running while the player is away (§10), which is why the simulation is a headless, deterministic core shared by realtime play, offline fast-forward, the balance simulator and server-side leaderboard checks (§3.2). No `game-pillars.md` exists; priority reasoning below cites GDD sections instead of pillars.

**Mechanical scope at a glance.** 46 systems in nine categories: Gameplay 14, Core 7, Meta 7, Progression 6, Economy 5, Persistence 3, UI 2, Audio 1, Narrative 1. Content data for all three waves already exists as CSV in `data/` and passes `tools/content_validator.py` (§17), so most systems are designed against real tables, not invented ones.

**Systems with an existing Python reference implementation** (`sim/`, §18). Their GDDs describe built behaviour and should be authored with `/design-system retrofit` against the code, then ported to the engine per `GODOT_PORT.md`: 1 Sim core (partial), 2 RNG (`rng.py`), 3 Data layer (`data.py`), 8 Member model (`model.py`), 10 Combat (`hunt.fight`), 11 Zones and hunt trips (`hunt.py`), 13 Party (partial), 14 Golden Boss raid (`raid.py`), 22 XP curve (`formulas.py`), 26 Items and loot (`hunt.roll_drops`), 27 Gold economy (analytic model in `economy.py`, not the live economy), 31 Offline progress (`offline.py`, already a driver over `hunt.run_trip`), 43 Dev tooling (`tools/`). Not yet built: the S1–S9 modules of §20.

### Per-system notes

**Core.** *RNG (2)* is the project's PCG32; nothing in the simulation may use an engine's random functions (`GODOT_PORT.md`). *Data layer (3)* loads CSV into immutable content tables keyed by stable IDs, with `content_wave`/`unlock_wave` gating which content is live. *Sim core (1)* owns the fixed 10 Hz tick and the tick phases of §3.4; feature systems register into phases, so the core never imports a feature. It also owns the single injected **game-clock interface** that offline progress and anti-cheat both rely on. *Event bus and history log (42)* carries tick-phase-6 events (§3.4) to every consumer and keeps the guild history that the Jianghu Chronicle narrates. *Command layer (5)* is the only path from player or AI input into the core (§3.2). *Localization (4)* keeps every display string in `i18n/` keyed by ID. *Dev tooling and parity harness (43)* is the balance simulator, calibrator, content validator and the Python↔engine golden-vector tests (§4.4, S9).

**Gameplay.** *Member model (8)* is data only: stats, equipment (including enhancement level as plain data), flags. *Member state machine (41)* owns the §6.4 states; other systems enter `boss_raid`, `injured`, `away` and so on through commands or events, never by writing state directly. *Combat (10)* executes skill effects from one effect schema and applies the Five Elements multipliers (§4.2); it never branches on skill IDs. *Zones and hunt trips (11)* owns zones, grounds, monsters and spawners, and **both** the detailed and the aggregate (sampled) resolution of a hunt — grounds outside the top-N by occupancy run a cheaper card tier chosen by a deterministic in-sim rule, never the camera (§3.5 simulation LOD, Zones R17, user decision 2026-11-16), and the sampled path is what offline progress uses. *Utility AI (12)* scores options for each member (§9.1) and never forms parties itself. *Party (13)* owns how a party forms and disbands, consuming AI scores (§6.12). *Golden Boss raid (14)* is the guild-wide fight that scales with participants (§6.13). *Offline progress (31)* is a time-slicing driver over 11's aggregate resolver plus timed events (backlogged bosses, at most 3 — S7). *Recruitment (15)*, *Retention (16)* and *Jianghu free agents and NPC guilds (17)* form the people pipeline: in, kept, out to the free-agent list, possibly back. *Arena (18)* and *Endless Tower (19)* are Wave 2 endgame.

**Progression.** *Schools (20)* defines the 10 schools and their roles; school change lives here too (§6.9). *Skills (21)* owns the 120 skills and the one effect schema combat executes. *XP curve (22)* is the §4.3 pacing formula — fast early, slower after each rebirth. *Rebirth and Ascension (23)* raises the level cap and turns graduates into Elders (§6.10). *Enhancement (24)* is the +1…+20 forge and the bottomless late-game gold sink (§19.3). *Quests and achievements (25)* subscribe to the event bus rather than calling into features.

**Economy.** *Items and loot (26)* owns item definitions, drop tables, guild storage and the "designated award" action through which the bang chủ distributes supplies to members (§1, §6.5). *Gold economy (27)* owns both currencies, the guild-funds ledger and **every** credit and debit to it — tax, upkeep, building output, sinks — so the S3 money-conservation test can be enforced in one place. *Guild and buildings (30)* spends from that ledger and owns building levels and the build queue. *Crafting (28)* and *Market and trade orders (29)* sit on top of items, economy and buildings.

**Persistence.** *Local save (6)* defines the save contract: each feature registers its own serializer and migration under one `schema_version` (S8), so save never imports features. *Account and cloud save (7)* adds Supabase auth and one cloud slot (§8.1). *Settings (45)* covers language, audio, ad consent and account linking.

**Meta, UI, Audio, Narrative.** *In-app purchases (34)* writes receipts; *Entitlement and feature flags (32)* derives Premium and "exact PA unlocked" from them, and the simulation receives an entitlement **snapshot as injected input** — no service writes into simulation state. *Ads (33)* reads entitlement. *Leaderboards and anti-cheat (35)* replays signed summaries with the deterministic core (§8.1). *Analytics (37)* and *AI text layer (36)* subscribe to the event bus. *Realtime world view (38)* and *Guild screens (39)* only read state and send commands. *Onboarding (44)*, *Audio (40)* and *Local push notifications (46)* wrap the rest.

### Relationship analysis

The graph has one spine: **Data layer (3) → Sim core (1) → Member model (8) → Combat (10) → Zones and hunt (11)**. Almost everything else hangs off that spine, which is why the first eleven entries in the design order walk it. Three shared hubs carry most of the risk: the Data layer (roughly two-thirds of systems depend on it), the Member model, and the Gold economy plus Guild pair, which every management system touches. The design order locks the schemas of 3 and 8 first because 9 through 31 build on them.

Two systems are deliberately thin so they cannot become god objects: the Sim core only orders phases, and Save only defines a contract. The event bus exists so that the late, wide consumers (quests, analytics, AI text, audio, world view) depend on one stream instead of on five or more feature systems each.

---

## Systems Enumeration

| # | System Name | Category | Priority | Status | Design Doc | Depends On |
|---|-------------|----------|----------|--------|------------|------------|
| 1 | Sim core and tick loop | Core | MVP | Needs Revision | design/gdd/sim-core-and-tick-loop.md | RNG, Data layer |
| 2 | Deterministic RNG (PCG32) | Core | MVP | Needs Revision | design/gdd/deterministic-rng.md | — |
| 3 | Data layer and content pipeline | Core | MVP | Needs Revision | design/gdd/data-layer-and-content-pipeline.md | — |
| 4 | Localization (vi/en) | Core | Vertical Slice | Needs Revision | design/gdd/localization.md | — |
| 5 | Command layer (inferred) | Core | MVP | Needs Revision | design/gdd/command-layer.md | Sim core, Data layer, Event bus |
| 6 | Local save and migration | Persistence | MVP | Needs Revision | design/gdd/local-save-and-migration.md | Sim core, Data layer, Event bus |
| 7 | Account and cloud save | Persistence | Alpha | Needs Revision | design/gdd/account-and-cloud-save.md | Local save |
| 8 | Member model | Gameplay | MVP | Needs Revision | design/gdd/member-model.md | Sim core, Schools, XP curve, Items and loot, Data layer, Event bus |
| 9 | CA/PA and traits | Gameplay | MVP | Needs Revision | design/gdd/ca-pa-and-traits.md | RNG, Member model, Data layer, XP curve, Skills, Items and loot, Sim core, Event bus |
| 10 | Combat | Gameplay | MVP | Needs Revision | design/gdd/combat.md | Sim core, RNG, Member model, Schools, Skills, Data layer |
| 11 | Zones, grounds, monsters and hunt trips | Gameplay | MVP | Needs Revision | design/gdd/zones-grounds-monsters-and-hunt-trips.md | RNG, Member model, Combat, Items and loot, Data layer, Sim core, Event bus, XP curve, Gold economy |
| 12 | Utility AI | Gameplay | MVP | Needs Revision | design/gdd/utility-ai.md | RNG, Member model, CA/PA and traits, Zones and hunt, Schools, Combat, Data layer, Gold economy, Items and loot |
| 13 | Party | Gameplay | MVP | Needs Revision | design/gdd/party.md | Member model, CA/PA and traits, Combat, Utility AI, Schools, Member state machine |
| 14 | Golden Boss and guild raid | Gameplay | MVP | Needs Revision | design/gdd/golden-boss-and-guild-raid.md | Sim core, RNG, Data layer, Command layer, Local save, Member model, Combat, Zones and hunt, Party, XP curve, Items and loot, Gold economy, Guild and buildings, Member state machine, Offline progress, Event bus, Market and trade orders (VS) |
| 15 | Recruitment | Gameplay | MVP | Needs Revision | design/gdd/recruitment.md | RNG, CA/PA and traits, Guild and buildings, Member model, Schools, Command layer, Sim core, Data layer, Event bus |
| 16 | Retention, leaving and negotiation | Gameplay | Vertical Slice | Needs Revision | design/gdd/retention-leaving-and-negotiation.md | RNG, Member model, CA/PA and traits, Party, Gold economy, Member state machine, Event bus, Command layer, Sim core, Data layer, Guild and buildings, Items and loot, Zones and hunt |
| 17 | Jianghu free agents and NPC guilds | Gameplay | Full Vision | Needs Revision | design/gdd/jianghu-free-agents-and-npc-guilds.md | RNG, Retention, Guild and buildings, Member model, Gold economy |
| 18 | Arena | Gameplay | Full Vision | Needs Revision | [arena.md](arena.md) | RNG, Combat, Jianghu free agents and NPC guilds, Guild and buildings, Member model, Items and loot, Member state machine |
| 19 | Endless Tower | Gameplay | Full Vision | Needs Revision | [endless-tower.md](endless-tower.md) | RNG, Combat, Zones and hunt, Items and loot, Guild and buildings, Member state machine, Rebirth |
| 20 | Schools and school change | Progression | MVP | Needs Revision | design/gdd/schools-and-school-change.md | Data layer, Sim core, Event bus |
| 21 | Skills | Progression | MVP | Needs Revision | design/gdd/skills.md | Data layer, Schools, XP curve, Sim core, Event bus |
| 22 | XP and level pacing curve | Progression | MVP | Needs Revision | design/gdd/xp-and-level-pacing-curve.md | Data layer, Sim core, Event bus |
| 23 | Rebirth and Ascension | Progression | Alpha | Needs Revision | design/gdd/rebirth-and-ascension.md | Member model, Skills, XP curve, Gold economy, Data layer, Items and loot, Guild and buildings, CA/PA and traits |
| 24 | Equipment enhancement | Progression | Vertical Slice | Needs Revision | design/gdd/equipment-enhancement.md | RNG, Member model, Items and loot, Gold economy, Guild and buildings, Data layer, Command layer, Event bus |
| 25 | Quests and achievements | Progression | Vertical Slice | Needs Revision | design/gdd/quests-and-achievements.md | RNG, Event bus, Zones and hunt, Golden Boss, Recruitment, Gold economy, Crafting, Guild and buildings, Data layer, Command layer, Items and loot, Market, Offline progress, Local save, Entitlement, Ads |
| 26 | Items and loot tables | Economy | MVP | Needs Revision | design/gdd/items-and-loot-tables.md | RNG, Data layer, Sim core, Event bus, Schools |
| 27 | Gold economy (currencies, ledger, tax, upkeep, sinks) | Economy | MVP | Needs Revision | design/gdd/gold-economy.md | Sim core, Data layer, Event bus, Member model, Items and loot |
| 28 | Crafting and recipes | Economy | Vertical Slice | Needs Revision | design/gdd/crafting-and-recipes.md | RNG, Items and loot, Gold economy, Guild and buildings, Data layer, Command layer, Sim core, Event bus, Local save |
| 29 | Guild market and trade orders | Economy | Vertical Slice | Needs Revision | design/gdd/guild-market-and-trade-orders.md | Items and loot, Gold economy, Guild and buildings, Member model, Utility AI, Command layer |
| 30 | Guild and buildings | Economy | MVP | Needs Revision | design/gdd/guild-and-buildings.md | Sim core, Data layer, Gold economy, Items and loot, Event bus, Command layer |
| 31 | Offline progress | Gameplay | MVP | Needs Revision | design/gdd/offline-progress.md | Sim core, RNG, Member model, Combat, Zones and hunt, Party, Golden Boss, Gold economy, Event bus, Utility AI, Items and loot, XP curve, Local save |
| 32 | Entitlement and feature flags | Meta | Alpha | Needs Revision | design/gdd/entitlement-and-feature-flags.md | Account and cloud save, In-app purchases, Command layer, Local save and migration, Data layer |
| 33 | Ads (banner, rewarded, consent) | Meta | Alpha | Needs Revision | design/gdd/ads.md | Entitlement, Quests, Command layer, Local save, Data layer, Localization |
| 34 | In-app purchases (Premium, exact-PA items) | Meta | Alpha | Needs Revision | design/gdd/in-app-purchases.md | Account and cloud save, Command layer, Items and loot, Local save, Data layer, Localization |
| 35 | Leaderboards and anti-cheat | Meta | Alpha | Needs Revision | design/gdd/leaderboards-and-anti-cheat.md | Sim core, RNG, Local save, Account and cloud save, CA/PA and traits, Data layer, Command layer, Offline progress |
| 36 | AI text layer (optional local LLM) | Narrative | Full Vision | Needs Revision | design/gdd/ai-text-layer.md | Localization, Member model, CA/PA and traits, Retention, Jianghu free agents, Event bus, Local save, Entitlement |
| 37 | Analytics (inferred) | Meta | Alpha | Needs Revision | design/gdd/analytics.md | Event bus, Settings |
| 38 | Realtime world view | UI | MVP | Needs Revision | design/gdd/realtime-world-view.md | Localization, Sim core, Command layer, Member model, Member state machine, Combat, Zones and hunt, Golden Boss, Event bus |
| 39 | Guild screens (inferred) | UI | MVP | Needs Revision | design/gdd/guild-screens.md | Localization, Command layer, Sim core, Member model, Member state machine, CA/PA and traits, Party, Utility AI, Combat, Recruitment, Retention, Enhancement, Gold economy, Market, Guild and buildings, Items and loot, Zones and hunt, Golden Boss, Offline progress, Local save, Data layer, Skills, Schools, XP curve, Rebirth, Crafting, In-app purchases, Realtime world view (provisional), Entitlement (provisional) |
| 40 | Audio (inferred) | Audio | Alpha | Needs Revision | design/gdd/audio.md | Sim core, Realtime world view, Event bus, Settings, Ads |
| 41 | Member state machine | Gameplay | MVP | Needs Revision | design/gdd/member-state-machine.md | Member model, Utility AI, Event bus, Sim core, Command layer, Zones and hunt, Party |
| 42 | Event bus and history log | Core | MVP | Needs Revision | design/gdd/event-bus-and-history-log.md | Sim core, Data layer |
| 43 | Dev tooling and parity harness | Core | MVP | Needs Revision | design/gdd/dev-tooling-and-parity-harness.md | RNG, Data layer |
| 44 | Onboarding and tutorial (inferred) | Meta | Alpha | Needs Revision | design/gdd/onboarding-and-tutorial.md | Zones and hunt, Guild screens, Event bus, Command layer, Recruitment, Party, Local save, Localization, Realtime world view |
| 45 | Settings | Persistence | Vertical Slice | Needs Revision | design/gdd/settings.md | Localization, Account and cloud save, Ads, Audio, Deterministic RNG, In-app purchases, Local push notifications |
| 46 | Local push notifications (inferred) | Meta | Full Vision | Needs Revision | design/gdd/local-push-notifications.md | Sim core, Golden Boss, Offline progress, Localization, Settings |

**MVP scope cuts** (PR-SCOPE and CD-SYSTEMS, applied). In MVP:
- Skills (21) covers only the 3 slice schools — `tho_1`, `moc_1`, `hoa_2` (user decision 2026-11-16, Skills OQ-1) — × 12 = 36 skills.
- Guild and buildings (30) covers the 5 buildings of GDD prompt P3 (Tổng Đàn, Thiện Đường, Dược Phòng, Chợ Bang, Luyện Khí Đài).
- Gold economy (27) covers income, basic upkeep and a flat fixed-% tax on member income (no slider, no mood effect; user decision 2026-11-16). The tax slider and its mood effect (with Retention), the market and the Linh Bảo shop arrive in Vertical Slice.
- Guild screens (39) cover only what the slice needs.
- CA/PA and traits (9) covers CA plus the PA estimate (stars or a range) only. Traits and exact-PA reveal arrive in Vertical Slice.
- Recruitment (15) is a recurring "pick 1 of 3 candidates" event showing CA, estimated PA and school. Scouts, invitations, Chiêu Hiền Lệnh and the passive arrival rate arrive in Vertical Slice.
- Golden Boss and guild raid (14) is a scaled-down raid with capped participants and full sprites, and is built only after the P1 spike has measured raid performance on a real Android phone.

The full systems are designed once; the tiers limit what is built first.

**Distributing supplies** (one of the four guild-master verbs in GDD §1) is owned by Items and loot (26). It covers guild storage and the bang chủ's "designated award" action that hands an item to a member (§6.5).

**Tier inversions (accepted, by design).** Some MVP systems list a dependency in a later tier. Each one has a stated MVP stand-in so nothing is blocked:
- Golden Boss (14) depends on Market (29, Vertical Slice): in MVP boss loot uses the §6.5 "designated award" path only.
- Guild screens (39) list Vertical Slice and later dependencies: screens are added as each system lands.
- Settings (45, Vertical Slice) lists Account and cloud save (7, Alpha), Ads (33, Alpha) and Audio (40, Alpha): those controls appear when their systems land.

---

## Categories

| Category | Description | Typical Systems |
|----------|-------------|-----------------|
| **Core** | Foundation systems everything depends on | Sim core, RNG, data layer, command layer, event bus, localization, dev tooling |
| **Gameplay** | The systems that make the game fun | Member model and state machine, combat, hunting, AI, party, raid, recruitment, retention, offline |
| **Progression** | How members and the guild grow over time | Schools, skills, XP curve, rebirth, enhancement, quests |
| **Economy** | Resource creation and consumption | Items and loot, gold economy, crafting, market, guild buildings |
| **Persistence** | Save state and continuity | Local save, cloud save, settings |
| **UI** | Player-facing information displays | Realtime world view, guild screens |
| **Audio** | Sound and music systems | Music and SFX |
| **Narrative** | Story and dialogue delivery | Optional LLM text layer, Jianghu Chronicle narration |
| **Meta** | Systems outside the core game loop | Entitlement, ads, in-app purchases, leaderboards, analytics, onboarding, push notifications |

---

## Priority Tiers

Tiers are mapped onto the GDD's own phases (§12.2). Note the naming: this template's "Vertical Slice" tier is GDD **phase 2** (the complete core loop), not the "vertical slice" the GDD names in phase 1.

| Tier | Definition | Target Milestone | Design Urgency |
|------|------------|------------------|----------------|
| **MVP** | Required for the core loop to function. Without these, you can't test "is this fun?" GDD phases 0–1 plus offline progress, and thin slices of CA/PA and recruitment. | 30–60 min playable on a real Android device | Design FIRST |
| **Vertical Slice** | Required for the complete management loop. GDD phase 2: traits, full recruitment, retention, enhancement, crafting, market, quests, localization, settings. | Complete core loop | Design SECOND |
| **Alpha** | Everything the Wave 1 store launch needs. GDD phases 3–5. Built in order: must-ship first (Onboarding 44, Ads and consent 33, In-app purchases 34, Entitlement 32, Audio 40, Rebirth 1 via 23), then Account and cloud save 7, Leaderboards 35, Analytics 37. | Wave 1 Android launch | Design THIRD |
| **Full Vision** | Post-launch and later waves (§12.5): free agents and NPC guilds, Arena, Endless Tower, LLM text layer, push notifications. | Waves 2–4 | Design as needed |

> **Producer Note — PR-SCOPE: OPTIMISTIC** (all tiers). Rough estimate of 70–90 solo full-time weeks to the Wave 1 launch, low confidence with no velocity history. The original MVP was about twice the size of GDD phase 1. Applied: MVP cut to the phase 1 slice plus offline progress; Localization and Settings moved to Vertical Slice; Alpha ordered with must-ship first; LLM text layer, free agents and push notifications moved to Full Vision. **Not applied, by user decision:** moving Account and cloud save (7) and Leaderboards (35) post-launch, because GDD §1 locks cross-device cloud save and guild leaderboards. **Timeline: not set by the user.** Without a date this gate cannot return REALISTIC; set at least a rough Vertical Slice date.
>
> **Creative Director Note — CD-SYSTEMS: CONCERNS** (MVP, all tiers).
> - **MVP:** the first cut kept the loop machinery but removed both of the player's decisions about people (who to take, what they could become). The GDD's own P3 slice already shows the PA estimate. **Revised by user decision:** thin slices of CA/PA (9) and Recruitment (15) moved into MVP, supply distribution assigned to Items and loot (26), and the guild raid (14) kept in MVP, scaled down and gated on the P1 spike.
> - **All tiers, still open:** no game pillars exist, so scope calls rest on GDD phase order rather than on falsifiable pillars. Write 3–5 pillars (for example "every member is a person with a hidden ceiling", "the bang chủ decides, members act") before GDD authoring starts.
> - **Full Vision:** the cuts were endorsed.
>
> **Required before MVP work starts** (PR-SCOPE): (1) an **art spike**: one complete paper-doll plus 20 item icons through local Stable Diffusion, with `ART_LICENSE_LOG.md` entries (§12.4.1). If it fails, the code-drawn minimal style (§12.4) becomes the art plan, not the fallback. (2) The **P1 technical spike** on a real Android device: AdMob, in-app purchases, Google Sign-In, Supabase REST, and raid sprite performance (§12.1, §6.13).

---

## Dependency Map

### Foundation Layer (no dependencies)

1. Deterministic RNG (2) — every random outcome in the simulation flows from it; parity with the engine port depends on it (`GODOT_PORT.md` step 1).
2. Data layer and content pipeline (3) — every system reads content tables by stable ID; the largest bottleneck in the graph.
3. Localization (4) — display text is never hard-coded (§3.3); designed now, built in Vertical Slice.
4. Dev tooling and parity harness (43) — depends on 2 and 3; the balance simulator is mandatory before every number change (§4.4).

### Core Layer (depends on foundation)

1. Sim core and tick loop (1) — depends on: RNG, Data layer
2. Event bus and history log (42) — depends on: Sim core, Data layer
3. Schools and school change (20) — depends on: Data layer
4. XP and level pacing curve (22) — depends on: Data layer, Sim core, Event bus
5. Items and loot tables (26) — depends on: Data layer

### Feature Layer (depends on core)

1. Command layer (5) — depends on: Sim core
2. Local save and migration (6) — depends on: Sim core
3. Skills (21) — depends on: Data layer, Schools, XP curve
4. Member model (8) — depends on: Sim core, Schools, XP curve, Items and loot
5. CA/PA and traits (9) — depends on: Member model
6. Combat (10) — depends on: Sim core, RNG, Member model, Skills
7. Gold economy (27) — depends on: Member model, Items and loot
8. Zones, grounds, monsters and hunt trips (11) — depends on: Member model, Combat, Items and loot
9. Guild and buildings (30) — depends on: Sim core, Data layer, Gold economy
10. Utility AI (12) — depends on: Member model, CA/PA and traits, Zones and hunt
11. Member state machine (41) — depends on: Member model, Utility AI, Event bus
12. Party (13) — depends on: Member model, CA/PA and traits, Combat, Utility AI
13. Rebirth and Ascension (23) — depends on: Member model, Skills, XP curve, Gold economy
14. Equipment enhancement (24) — depends on: Member model, Items and loot, Gold economy, Guild and buildings
15. Crafting and recipes (28) — depends on: Items and loot, Gold economy, Guild and buildings
16. Guild market and trade orders (29) — depends on: Items and loot, Gold economy, Guild and buildings
17. Golden Boss and guild raid (14) — depends on: Combat, Party, Items and loot, Market, Guild and buildings
18. Recruitment (15) — depends on: CA/PA and traits, Guild and buildings
19. Retention, leaving and negotiation (16) — depends on: Member model, CA/PA and traits, Party, Gold economy
20. Jianghu free agents and NPC guilds (17) — depends on: Retention, Guild and buildings
21. Arena (18) — depends on: Combat, Jianghu free agents and NPC guilds
22. Endless Tower (19) — depends on: Combat, Zones and hunt, Items and loot
23. Quests and achievements (25) — depends on: Event bus, Zones and hunt, Golden Boss, Recruitment, Gold economy, Crafting, Guild and buildings
24. Offline progress (31) — depends on: Sim core, RNG, Member model, Combat, Zones and hunt, Party, Golden Boss, Gold economy

### Presentation Layer (depends on features)

1. Realtime world view (38) — depends on: Localization, Sim core, Command layer, Member model, Combat, Zones and hunt, Golden Boss
2. Guild screens (39) — depends on: Localization, Command layer, Member model, CA/PA and traits, Party, Recruitment, Retention, Enhancement, Gold economy, Market, Guild and buildings
3. Audio (40) — depends on: Sim core, Realtime world view
4. Settings (45) — depends on: Localization, Account and cloud save, Ads, Audio

### Polish Layer (depends on everything)

1. Account and cloud save (7) — depends on: Local save
2. In-app purchases (34) — depends on: Account and cloud save
3. Entitlement and feature flags (32) — depends on: Account and cloud save, In-app purchases
4. Ads (33) — depends on: Entitlement
5. Leaderboards and anti-cheat (35) — depends on: Sim core, RNG, Local save, Account and cloud save, CA/PA and traits
6. AI text layer (36) — depends on: Localization, Member model, CA/PA and traits, Retention, Jianghu free agents, Event bus
7. Analytics (37) — depends on: Event bus
8. Onboarding and tutorial (44) — depends on: Zones and hunt, Guild screens, Event bus
9. Local push notifications (46) — depends on: Sim core, Golden Boss, Offline progress

> **Technical Director Note — TD-SYSTEM-BOUNDARY: CONCERNS.** No restructure needed. Applied before writing this index:
> - Added Member state machine (41), Event bus and history log (42) and Dev tooling and parity harness (43).
> - Made Offline progress (31) a driver over the aggregate resolver owned by Zones and hunt (11), with a parity test. `sim/offline.py` already calls `hunt.run_trip`.
> - Replaced the CA/PA ↔ In-app purchases fix (below).
> - Routed Quests (25), Analytics (37) and AI text (36) through the event bus.
> - Added Localization to the dependencies of 36, 38 and 39.
> - Gave Zones and hunt (11) ownership of monsters and spawners.
>
> **Contracts the per-system GDDs must state:**
> - **Sim core (1):** features register into its tick phases, and it owns the injected game-clock interface.
> - **Local save (6):** each feature registers its own serializer and migration under one `schema_version`.
> - **Gold economy (27):** it owns every credit and debit to the guild-funds ledger.
> - **Skills (21):** it owns the single effect schema, and Combat (10) never branches on skill IDs.
> - **Party (13):** it owns party formation and disbanding.
> - **Utility AI (12):** it only scores options.
> - **Member state machine (41):** other systems enter its states through commands or events.

---

## Recommended Design Order

Effort is GDD-authoring sessions (S = 1 session, M = 2–3, L = 4+). "Retrofit" means the behaviour exists in `sim/` and the GDD is written from the code with `/design-system retrofit`.

| Order | System | Priority | Layer | Agent(s) | Est. Effort |
|-------|--------|----------|-------|----------|-------------|
| 1 | Deterministic RNG (2) — retrofit | MVP | Foundation | systems-designer | S |
| 2 | Data layer and content pipeline (3) — retrofit | MVP | Foundation | systems-designer | M |
| 3 | Dev tooling and parity harness (43) — retrofit | MVP | Foundation | systems-designer, tools-programmer | S |
| 4 | Sim core and tick loop (1) — retrofit | MVP | Core | systems-designer, engine-programmer | M |
| 5 | Event bus and history log (42) | MVP | Core | systems-designer | S |
| 6 | Schools and school change (20) | MVP | Core | game-designer | S |
| 7 | XP and level pacing curve (22) — retrofit | MVP | Core | game-designer, systems-designer | S |
| 8 | Items and loot tables (26) — retrofit | MVP | Core | economy-designer, systems-designer | M |
| 9 | Command layer (5) | MVP | Feature | systems-designer, gameplay-programmer | S |
| 10 | Local save and migration (6) | MVP | Feature | systems-designer | M |
| 11 | Member model (8) — retrofit | MVP | Feature | game-designer, systems-designer | M |
| 12 | Skills (21) | MVP | Feature | game-designer, systems-designer | L |
| 13 | Combat (10) — retrofit | MVP | Feature | game-designer, systems-designer, ai-programmer | L |
| 14 | Gold economy (27) — partial retrofit | MVP | Feature | economy-designer, systems-designer | L |
| 15 | Zones, grounds, monsters and hunt trips (11) — retrofit | MVP | Feature | game-designer, level-designer | L |
| 16 | Guild and buildings (30) | MVP | Feature | economy-designer, game-designer | M |
| 17 | CA/PA and traits (9) | MVP | Feature | game-designer, systems-designer | M |
| 18 | Recruitment (15) | MVP | Feature | game-designer, systems-designer | M |
| 19 | Utility AI (12) | MVP | Feature | game-designer, ai-programmer | M |
| 20 | Member state machine (41) | MVP | Feature | game-designer, ai-programmer | M |
| 21 | Party (13) — partial retrofit | MVP | Feature | game-designer, systems-designer | M |
| 22 | Golden Boss and guild raid (14) — retrofit | MVP | Feature | game-designer, systems-designer | L |
| 23 | Offline progress (31) — retrofit | MVP | Feature | systems-designer | M |
| 24 | Realtime world view (38) | MVP | Presentation | game-designer, ux-designer, art-director | M |
| 25 | Guild screens (39) | MVP | Presentation | game-designer, ux-designer | M |
| 26 | Localization (4) | Vertical Slice | Foundation | systems-designer | S |
| 27 | Equipment enhancement (24) | Vertical Slice | Feature | economy-designer, systems-designer | M |
| 28 | Crafting and recipes (28) | Vertical Slice | Feature | economy-designer | M |
| 29 | Guild market and trade orders (29) | Vertical Slice | Feature | economy-designer | M |
| 30 | Retention, leaving and negotiation (16) | Vertical Slice | Feature | game-designer, systems-designer | L |
| 31 | Quests and achievements (25) | Vertical Slice | Feature | game-designer, economy-designer | M |
| 32 | Settings (45) | Vertical Slice | Presentation | ux-designer | S |
| 33 | Rebirth and Ascension (23) | Alpha | Feature | game-designer, systems-designer | M |
| 34 | Account and cloud save (7) | Alpha | Polish | systems-designer | M |
| 35 | In-app purchases (34) | Alpha | Polish | systems-designer, economy-designer | M |
| 36 | Entitlement and feature flags (32) | Alpha | Polish | systems-designer | S |
| 37 | Ads (33) | Alpha | Polish | systems-designer | S |
| 38 | Audio (40) | Alpha | Presentation | audio-director, sound-designer | M |
| 39 | Onboarding and tutorial (44) | Alpha | Polish | ux-designer, game-designer | M |
| 40 | Leaderboards and anti-cheat (35) | Alpha | Polish | systems-designer | M |
| 41 | Analytics (37) | Alpha | Polish | systems-designer | S |
| 42 | Jianghu free agents and NPC guilds (17) | Full Vision | Feature | game-designer, world-builder | M |
| 43 | Arena (18) | Full Vision | Feature | game-designer | M |
| 44 | Endless Tower (19) | Full Vision | Feature | game-designer, level-designer | M |
| 45 | AI text layer (36) | Full Vision | Polish | game-designer, narrative-director, writer | M |
| 46 | Local push notifications (46) | Full Vision | Polish | ux-designer | S |

Design order follows dependencies, so it differs from the Alpha **build** order: Account and cloud save (7) is designed before In-app purchases (34) and Entitlement (32) because both depend on it, even though the build order puts the must-ship group first.

---

## Circular Dependencies

All six cycles found during mapping are resolved by assigning ownership. None needs simultaneous design.

- **Utility AI (12) ↔ Party (13):** Utility AI exposes scoring primitives and Party consumes them. Utility AI never calls Party, and Party owns formation and disbanding.
- **Gold economy (27) ↔ Guild and buildings (30):** the Gold economy owns both currencies and the guild-funds ledger, including every credit (tax, building output) and debit. Guild and buildings only requests spending.
- **Member model (8) ↔ Enhancement (24):** the member stores the enhancement level on each item instance as plain data, and Enhancement owns the process that changes it. This is the same pattern Member model already uses with Items and loot (26).
- **Combat (10) ↔ Skills (21):** Skills defines the effect data in one schema and Combat executes it without branching on skill IDs.
- **Entitlement (32) ↔ In-app purchases (34):** purchases write receipts, which are the source of truth, and Entitlement is derived from them.
- **CA/PA and traits (9) ↔ In-app purchases (34):** the first proposal (34 sets a flag that 9 reads) was rejected by TD-SYSTEM-BOUNDARY as a service writing into simulation state. In the adopted fix, In-app purchases depends on Account and cloud save (7) only, Entitlement derives "exact PA unlocked", and the simulation receives an entitlement snapshot as injected input. CA/PA depends on neither 32 nor 34.

---

## High-Risk Systems

| System | Risk Type | Risk Description | Mitigation |
|--------|-----------|-----------------|------------|
| Offline progress (31) | Technical | The aggregate offline result drifts from the detailed simulation, or becomes a second implementation of it. | 11 owns both resolutions and 31 is only a driver. Parity test against the detailed run (§18.1 reports about 1% XP drift today). Measure 24 h fast-forward time on a real device (P2). |
| Golden Boss and guild raid (14) | Technical | Dozens of members in one realtime fight is heavy for a phone (§6.13). | Full simulation in the core, but full sprites only near the camera (for example 15 or fewer). Measure on a real device in the P1 spike before fixing the member cap. |
| Gold economy (27) | Design | Inflation: a gear set costs 0.1–0.6 hours of income (§18.3). Money-conservation errors spread to every management system. | One owner for the ledger. S3 conservation test. Out/in target of 60–90% checked by the balance simulator (§19.5). |
| Skills (21) | Design / Scope | 120 skills in one effect schema. Real skills will shift the XP pacing (§20). | One schema, no combat special cases. MVP builds 36 skills. Re-calibrate `xp_kill_coef` after S4. |
| Data layer (3) and Member model (8) | Technical | The two largest bottlenecks: a schema change ripples to roughly two-thirds of the systems. | Design and lock both first (orders 2 and 11). IDs never change. |
| Art pipeline (not a system) | Scope / Legal | Free AI tools only, for a commercial game. Licensing and pixel consistency are unproven (§12.4.1). | Art spike before MVP (Producer Note). Code-drawn minimal style is the plan if the spike fails. |
| Mobile plugins (Ads 33, In-app purchases 34, Account and cloud save 7) | Technical | Godot plugins for AdMob, purchases and sign-in may cost more than planned (§3.1). | P1 spike on a real Android device. Unity is the fallback (§3.1). |
| AI text layer (36) | Technical / Compliance | RAM and battery cost on mobile. Google Play rules for AI-generated content. | Optional by design and moved to Full Vision. Template fallback. In-app report button (§12.4.1). |

---

## Progress Tracker

| Metric | Count |
|--------|-------|
| Total systems identified | 46 |
| Design docs started | 46 |
| Designed | 42 |
| Needs Revision | 4 (Sim core 1, RNG 2, Event bus 42, Dev tooling 43) |
| Design docs reviewed | 4 |
| Design docs approved | 0 |
| MVP systems designed | 21/25 (the other 4 are Needs Revision) |
| Vertical Slice systems designed | 7/7 |
| Alpha systems designed | 9/9 |
| Full Vision systems designed | 5/5 |
| Cross-GDD consistency pass | 2026-11-16 (`design/gdd/reviews/consistency-check-2026-11-16.md`) |

---

## Next Steps

- [ ] Review and approve this systems enumeration
- [ ] Run the art spike and the P1 technical spike before MVP implementation (Producer Note)
- [ ] Design MVP-tier systems first (use `/design-system [system-name]`, or `/design-system retrofit` for systems that exist in `sim/`)
- [ ] Run `/design-review` on each completed GDD
- [ ] Set a target date for the Vertical Slice so PR-SCOPE can be re-assessed
- [ ] Run `/gate-check technical-setup` when MVP systems are designed
- [ ] Validate the highest-risk systems with `/vertical-slice` before committing to Production
