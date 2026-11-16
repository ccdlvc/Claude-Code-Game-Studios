# Guild Screens

> **Status**: Designed (pending independent review)
> **Author**: user + Claude (design-system, autonomous batch run; decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Implements Pillar**: None (no `design/gdd/game-pillars.md`). Serves `JX1_Tycoon_GDD.md` §1 (the bang chủ's four verbs: recruit, build, distribute supplies, direct the boss fight), §3.2 ("Presentation chỉ đọc state và gửi lệnh"), §11.2–11.3 (Free/Premium, bottom banner counted into the layout from the start) and Prompt P3's screen list.
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, game concept or game brief to check against. Player Fantasy is anchored to `JX1_Tycoon_GDD.md` §1 and §3.2 instead. Re-run once pillars exist.
> **Mode**: new design (no Python reference; `sim/` has no presentation code). Systems index row 39, category `UI`, priority `MVP` ("inferred"; MVP covers only what the slice needs).

## Summary

Guild screens are every menu-style screen of the game: the guild header, the bottom tab bar, the roster and member panel, parties, storage, buildings, recruitment, the forge and market, the "while you were away" report, the notices and the failure screens. They show what the simulation already holds and turn each player tap into a command; they never change game state themselves. They exist because an idle tycoon is played mostly through these panels, so the guild master must be able to read what needs attention and act on it in a few taps, in Vietnamese or English, on a phone.

> **Quick reference** — Layer: `Presentation` · Priority: `MVP` (screens are added tier by tier as each owning system lands) · Key deps: `Command layer, Localization, Sim core, Member model, Member state machine, CA/PA and traits, Party, Items and loot, Guild and buildings, Gold economy, Recruitment, Zones and hunt, Offline progress, Golden Boss, Local save, Realtime world view (provisional), Entitlement (provisional)` · Feasibility: engine domain `UI`, checked against `docs/engine-reference/godot/modules/ui.md` (Godot 4.7); safe-area, haptics and the ad plugin's banner size are NOT SOURCEABLE there (→ ADR / Ads 33).

## Overview

**What it is.** Guild screens are the presentation shell and the full set of panel screens that sit beside the Realtime world view (38). The world view draws the living map: members walking, fighting and coming home. Guild screens draw everything a manager reads as a list, a card or a dialog: who is in the guild and how they are doing, which party lacks a buffer, what the treasury earns and spends, which building to raise next, which candidate to hire, what happened while the player was away.

**Data layer.** This system owns no simulation state and no save section. It owns: the shell layout (header, tab bar, ad reserve, safe area); the navigation stack; a per-screen read cache refreshed between ticks (Sim core R15); the set of *pending orders* (Command layer R11), held only in memory; the notification queue; and the presentation-only preferences that the Settings system (45) will persist. Each screen reads its owner's read model (for example `pa_view` from CA/PA, `retention_view` from Retention, the storage read model from Items and loot) and sends player actions through the Command layer's `submit` and `submit_batch`. Every visible word comes from Localization (4) at draw time.

**Player impact.** The player experiences this system directly; it is most of the game's interface. A good guild screen answers "what needs me now?" at a glance (badges, warnings, the away report), explains every "no" in words (refusal reasons, locked reasons), and makes the common actions one or two taps: send a party hunting, award a potion, accept a candidate, queue a building.

**Scope.** In: the shell, navigation, the shared interaction patterns (order acknowledgement, confirmation, refusal display, notices, toasts, badges, multi-select, lists), the screen inventory with each screen's tier, and the layout of the screens that other GDDs assign here. Out: what each screen *contains* in detail is already listed by the owning system's UI Requirements and is referenced, not repeated; the map and its in-world overlays (HP bars, damage numbers, walking sprites) belong to the Realtime world view (38); the Settings screen belongs to Settings (45); purchase behaviour belongs to In-app purchases (34); every game rule shown here belongs to its owner.

No ADR exists for this system (`docs/architecture/` has no ADR files). Implementation questions are marked "→ ADR" for `/architecture-decision`.

## Player Fantasy

**Framing: direct.** The player taps, reads and decides on these screens every session (`UI` category).

*No game pillars exist, so no pillar is quoted. The candidates are anchored to `JX1_Tycoon_GDD.md` §1 (the bang chủ manages: "tuyển thành viên, xây công trình, phân phối vật tư, điều phối đánh boss") and §3.2. CD-GDD-ALIGN remains NOT ASSESSED.*

Three framings were considered (creative-director lens):

1. **"The guild ledger at a glance" — chosen.** *The moment:* the player opens the game on the bus. A report says the guild worked eight hours; the Members tab carries a red "2" badge. One tap shows a leave request from a Mộc healer and a member ready to rebirth. Two more taps meet the healer's demand by awarding the potion she asked for. The player closes the game in under a minute knowing the guild is in order. The feeling is *"I run a big guild and nothing slips past me."* It asks the design for: badges that count only what needs a decision (R14), an away report that leads with what changed (R10), refusal reasons in words (R5), and short paths for the four verbs of §1.
2. **"The master's study" (atmosphere).** *The moment:* the building screen looks like a scroll-and-lacquer ledger of a martial-arts sect, with seals for each building level. Kept as the **visual direction** (Visual/Audio), not the lead fantasy: it is a style, not a decision the player makes.
3. **"Spreadsheet mastery" (depth).** *The moment:* a deep player sorts eighty members by CA, filters by school and spots the one Thổ tank whose stars outshine their level. Kept as a **secondary line**: sorting and filtering are in (R11), and Premium adds bulk actions (R9), but the default view must never require it.

**Target feeling.** Calm control: the guild runs itself, and the screens make the master's few decisions obvious, explained and quick. A refused order is never a mystery.

## Detailed Design

### Core Rules

*Specialist lenses applied in this conversation (no agent spawned), per the `UI systems` routing row:*

> - **game-designer**: the screens serve the §1 verbs; every high-frequency verb must be reachable in ≤ 2 taps from a tab root (recruit from the badge, award from storage or the member panel, build from the Guild tab, boss opt-out from the roster). The player cannot do anything here a system has not defined as a command; there is no "UI-only cheat" path.
> - **ux-designer**: most important first (what needs me, then what is happening, then detail); feedback for every tap in the same frame; nothing by colour alone; one-thumb reach on a portrait phone; confirmations only where a mistake hurts. **Tension** with the game-designer's low-friction goal on spend confirmations: resolved by F4 (confirm only above a share of the fund, or when irreversible).
> - **ui-programmer**: read models are pulled between ticks, never during one; list screens must be virtualised for an 80-member roster (`member_cap` ≤ 80); every text field must survive the `qps` pseudo-locale (Localization R15); pending orders are keyed by `seq` and are not saved. Feasibility: Godot 4.6 dual focus (touch focus separate from keyboard focus) matters for the PC port; 4.5 AccessKit gives screen-reader labels on `Control` nodes (`modules/ui.md`).
> - **art-director**: pixel-art panels in one frame family; status shown by icon *and* label; no text baked into art (Localization R12). See Visual/Audio.
> - **technical-artist**: the UI must not cost the map its 30 FPS on a mid-range phone (§3.5): no per-frame relayout of large lists, no shader-heavy panel effects, atlas the UI icons.

**R1 — Read state, send commands, nothing else.** A guild screen never writes simulation state. It reads committed state only between ticks, through the owning system's read API (the list in Interactions), and through the tick's event batch delivered by the Sim core facade (R15 of Sim core). Every player action is one command, or one batch, submitted through the Command layer. A screen that needs a value no owner exposes asks that owner for a read API; it does not compute game rules itself. *Exception:* pure display computations defined here or in Localization (formatting, countdowns F1, sorting, the confirm threshold F4).

**R2 — Shell layout (portrait, mobile first).** From top to bottom, inside the OS safe area:
1. **Guild header** (always visible): guild name, guild level (Tổng Đàn level), members `n / member_cap`, the fund (gold) and Linh Bảo balances (Gold economy UI 1), an arrears warning when the guild is `In arrears`, the Golden Boss countdown or gathering counter when one is announced (Golden Boss UI), and the catching-up indicator (R12).
2. **Content area**: the Map tab shows the Realtime world view (38); every other tab shows its root screen. Detail screens and dialogs stack on top (R3).
3. **Bottom tab bar**: five tabs, each with an icon, a label and a badge (R14): **Guild** (buildings and queue), **Members** (roster, parties, recruitment), **Map** (world view, zones and grounds), **Storage** (guild storage and award flow), **More** (treasury, market, shop, settings, quests, history; each entry appears when its system's tier lands).
4. **Ad reserve** (Free build only): a fixed strip of `ui_ad_banner_reserve_px` below the tab bar, reserved from MVP so the layout never shifts when Ads (33) lands (§11.3 "tính vào layout UI từ đầu"). It is 0 in Premium and on PC/Steam. An unfilled banner leaves the strip empty, never collapses it.
The layout is portrait-locked on mobile in MVP. A landscape/PC two-pane layout is a later port task (Open Questions).

**R3 — Navigation stack.** Each tab keeps its own stack: root → detail → dialog, at most `ui_stack_depth_max` (3) levels. Switching tabs keeps each tab's stack. Opening a fourth level replaces the top detail instead of stacking. The OS back action (Android back, Esc on PC) closes the topmost dialog, then the topmost detail; at a tab root other than Map it switches to Map; at the Map root it opens a quit confirmation. A dialog is either *player-opened* (a confirm, a picker) or *system-opened* (a notice, R8).

**R4 — Screen inventory.** Every screen, its data owner and the tier it is built in. The owner's UI Requirements section lists the contents; this GDD owns layout, navigation and the shared patterns.

| # | Screen / element | Entry points | Data owner(s) (UI Requirements) | Tier |
|---|---|---|---|---|
| G1 | Guild header | Always | Guild and buildings 30, Gold economy 27, Golden Boss 14 | MVP |
| G2 | Building list, queue, order confirm, effect preview, decay notice | Guild tab | Guild and buildings 30 | MVP |
| G3 | Roster list (sort, filter, state counts, raid opt-out column) | Members tab | Member model 8, MSM 41, CA/PA 9, Golden Boss 14 | MVP |
| G4 | Member panel: Overview (school, level, XP bar, state, needs, current order, profile), Gear (equip flow), Skills, Potential (CA, PA estimate) | Roster row, map tap (38), any member link | Member model 8, MSM 41, XP 22, Skills 21, Schools 20, CA/PA 9, Items 26 | MVP |
| G5 | Party panel (cards, free strip, warnings, fit badges, "Why here?") | Members tab | Party 13, Utility AI 12, Combat 10 | MVP |
| G6 | Recruitment board | Members tab, badge, notification | Recruitment 15, CA/PA 9, Schools 20 | MVP |
| G7 | Zone and ground panels, trip card, trip report, "Hunt here" / "Order home" | Map tab (over 38's map) | Zones and hunt 11, Combat 10 | MVP |
| G8 | Guild storage, award flow, hand-in summary, summon button | Storage tab | Items and loot 26, Golden Boss 14 | MVP |
| G9 | Golden Boss banner, gathering counter, result card | Header, notification | Golden Boss 14, Combat 10 | MVP |
| G10 | "While you were away" report, resolving overlay, short-absence toast | On return | Offline progress 31 (+ Retention 16, Rebirth 23 lines when live) | MVP |
| G11 | Fatal screens (core failure, data damaged) and save notices | System | Sim core 1, Data layer 3, Local save 6 | MVP |
| G12 | Aspiring-school picker | Member panel (unaffiliated member) | Schools 20 | MVP |
| G13 | Language list (stand-in until Settings 45) | More tab | Localization 4 | MVP |
| G14 | Forge | Luyện Khí Đài, member gear slot | Equipment enhancement 24 | MVP building, screen VS (Enhancement is VS) |
| G15 | Chợ Bang and Thương Hội screens | Building, More tab | Market and trade orders 29 | Vertical Slice |
| G16 | Treasury (totals, tax slider, upkeep) | More tab, header fund tap | Gold economy 27 | Vertical Slice |
| G17 | Workshop and recipe list, order dialog | Crafting building, storage "craft with this" | Crafting 28 | Vertical Slice |
| G18 | Member panel: Mood tab, leave-request card, salary, dismiss | Member panel, badge | Retention 16 | Vertical Slice |
| G19 | Traits on member card, Use Thiên Cơ Kính | Member panel Potential tab | CA/PA 9, IAP 34 | Vertical Slice |
| G20 | School-change dialog | Academy building | Schools 20 | Vertical Slice |
| G21 | Quest board (daily/weekly) | More tab, Cáo Thị Đường | Quests 25 (**provisional**, no GDD) | Vertical Slice |
| G22 | Shrine (Linh Miếu), Ascension confirm, Elders' hall | Building, badge | Rebirth and Ascension 23 | Alpha |
| G23 | Shop panel, purchase confirm, pending row | More tab, lens counter link | In-app purchases 34 | Alpha |
| G24 | Chronicle (history) | More tab, Giang Hồ Ký Quán | Event bus 42 (`read_history`) — **owner unassigned** (Open Questions) | Alpha (provisional) |
| G25 | Endless Tower panel, group picker, run view | Building | Endless Tower 19 | Full Vision |
| G26 | Arena, Jianghu free-agent list | Building | Arena 18, Jianghu 17 (no GDD) | Full Vision |

A screen whose owning system is not live is absent: its tab entry, building link and badge do not exist. Content inside a live screen that belongs to an unreleased wave is hidden (not greyed), because the player cannot act on it (Data layer: `content_wave`).

**R5 — Order acknowledgement (pending, applied, refused).** This implements Command layer R11 and its UI Requirements 1–6:
1. When `submit` returns `seq > 0`, the control that sent it (and the target row, if visible) shows a **pending** marker in the same frame. The set of pending orders is keyed by `seq` and lives only in memory.
2. On `command_applied` with that `seq`, the marker becomes an **applied** mark for `ui_ack_show_ms`, then clears. The screen re-reads (R6) so the new state replaces the old.
3. On `command_refused`, the marker becomes a **refused** mark with the reason in words (`i18n` key per reason code, owner's namespace) beside the target. If the target is not on screen, a toast carries it (R8). Reason codes 1–5 (layer-level bugs or tampering) show one generic "the order could not be given" text in a release build.
4. A host refusal (`seq = 0`) is shown at once, with its reason. `host_queue_full` reads "the guild is busy — try again in a moment" and is **never** retried automatically.
5. While `catching_up` or `handoff_pending` is true, pending markers read "waiting for the guild", never "failed". A pending order has no timeout: it always resolves.
6. A load or a new core instance clears the pending set (the command queue is never saved, Sim core R14).

**R6 — Refresh between ticks.** A screen holds a cache of the read models it shows. It is marked *dirty* when the tick batch contains an event type in the screen's subscription list, when one of its pending orders resolves, or when the locale changes. A dirty, visible screen re-reads when F2 allows. Countdowns update every frame from F1 without a re-read. A screen covered by a dialog stays subscribed and re-reads when uncovered. Nothing re-reads during a tick.

**R7 — Disabled, hidden, explained.** A control the player cannot use right now is **visible and disabled, with the reason** in words next to it or one tap away: unaffordable (with the missing amount, Gold economy UI 4), locked by level or building (with the requirement), Premium-only (with a Premium badge and a link to the shop once IAP 34 is live), member busy (with the state). A control for unreleased content is hidden (R4). The owner's refusal is still handled when a disabled state was stale (Command layer R14).

**R8 — Notifications.** Four kinds, one queue:
- **Blocking screen** — replaces the content area and accepts only its own actions.
- **Modal sheet** — a dialog over the content; one at a time.
- **Banner** — a strip under the header, persists until dismissed or resolved; at most `ui_banner_max` (2) visible, newest on top.
- **Toast** — a short line above the tab bar; one visible at a time, duration F5, queue of at most `ui_toast_queue_max`; beyond that the queue collapses its oldest entries into "+N more" that opens a list.

Priority, highest first (a higher one pre-empts a lower system-opened one, which goes back to the queue; equal priority is first-in, first-out):

| P | Notification | Kind | Owner of content |
|---|---|---|---|
| 0 | Core failed; data damaged | Blocking | Sim core 1, Data layer 3 |
| 1 | Save from newer version; save damaged; open elsewhere; cloud adopt/conflict/blocked | Blocking (open elsewhere: blocking banner) | Local save 6, Account 7 |
| 2 | Offline resolving overlay | Blocking, with progress | Offline progress 31 |
| 3 | "While you were away" report | Modal sheet | Offline progress 31 |
| 4 | Leave request with a deadline (VS) | Modal sheet, or badge if the player is mid-dialog | Retention 16 |
| 5 | Golden Boss result card | Modal sheet | Golden Boss 14 |
| 6 | Cannot save; restored from earlier save; arrears; building decay; boss announced | Banner | 6, 27, 30, 14 |
| 7 | Order refused off-screen; short-absence summary; purchase restore result; level-ups (summarised) | Toast | 5, 31, 34, 22 |

A **player-opened dialog** (a confirm, a picker) is pre-empted only by priorities 0–2; priorities 3–7 wait until it closes. Recruitment offers, ready-to-rebirth members and other decisions without a deadline never interrupt: they are badges (R14).

**R9 — Multi-select and batch orders.** Roster and party screens allow selecting several members and giving one order ("Hunt at…", "Return", "Stay home", "Opt out of raid"). The selection expands to one command per member through `submit_batch` (Command layer R12), and each refusal is shown on its member. On Free, a selection holds at most `ui_multiselect_free_max` members (default 5, one party). **Select all** and **apply to a filter** ("every resting member") are Premium (§11.2 "thao tác hàng loạt"), shown with a Premium badge and disabled on Free. A batch larger than `host_pending_max` is split per F3.

**R10 — Return from absence.** On load or resume, after Offline progress (31) finishes resolving: if `credited_s ≥ offline_report_min_s`, the away report opens (priority 3) and leads with the headline, then the lines that need a decision (leave requests, ready to rebirth, missed bosses), then the per-member table. Otherwise a toast summarises. Badges are recomputed before the report opens, so closing the report leaves the player looking at accurate badges.

**R11 — Lists.** Every list has a default sort and a stable tiebreak by ID (never by display name in a way that changes between locales; Localization R13 collation applies only to sorts the player chooses by name). The roster sorts by state (needs attention first), then level, then CA, and offers sorting by name, level, CA, shown stars (`half_stars` from `pa_view`, never hidden PA: CA/PA R12), school and state. Filters: state, school, element, party. Lists longer than one screen are virtualised (only visible rows are built). When two visible members share a name, each shows a short ID tag after the name (Member model edge case).

**R12 — Catching up and resolving.** While the facade reports `catching_up` or `handoff_pending`, the header shows a "catching up" indicator with progress from `debt_us`; screens refresh at the slower F2 rate; per-event toasts are held and replaced by one summary toast when catch-up ends. Input stays live: orders are queued (R5.5). During the offline **resolving** overlay (priority 2), input is blocked: nothing can be submitted until the report is ready.

**R13 — Failure and notice shells.** Blocking screens (R8 priorities 0–1) use one shell: title, body, facts, actions, error code. They draw only with the core string set (Localization R11) and must not read content tables, because the failure may be a data failure. Their actions are exactly those their owners list (Sim core: "Reload last save", "Quit"; Local save adds "Load an older save" on the core-failure screen; Data layer: "Quit" and, where the store allows, "Verify / reinstall"). Guild screens add no "continue" and no read-only guild view (answers Sim core OQ-2 for this system).

**R14 — Badges.** A tab's badge counts items that need a decision and that the player can act on now: Members — open recruitment offer (1 while open), open leave requests, members ready to rebirth or ascend (Alpha), unaffiliated members without an aspiring school; Guild — 1 when the build queue is empty and at least one build is affordable; Storage — 1 while a summon horn is held and no raid runs; More — quests with a claimable reward (VS). Counts above `ui_badge_max` show as "99+". A badge is a number plus a shape, never only a colour dot.

**R15 — Text and numbers.** Every string comes from Localization `text(key, field, args)`; numbers use F1 (grouped) or F2 (compact) with the exact value on long-press; durations use F6; content names use F4 fit with the full name in the detail view; UI strings wrap and are never truncated (Localization F4). Every screen is signed off in `vi`, `en` and `qps` (Localization R15). Player names are proper nouns (Member model R4) and are drawn verbatim. Rename accepts 1 to `member_name_max_len` code points after NFC normalisation and trimming, rejects control characters, and validates live; the submit button is disabled while invalid.

**R16 — Accessibility floor.** Nothing is conveyed by colour alone (element, rarity, state, danger, refusal, Premium, pending: each has an icon or shape and a text label). Touch targets are at least `ui_touch_min_px` in both dimensions at the reference viewport. Every interactive control carries an accessible name for screen readers (AccessKit, Godot 4.5+, `modules/ui.md`). Text size comes from Settings (45) `a11y_text_scale` (options `a11y_text_scale_options`, default 100;125;150 %), applied live as a theme font-size multiplier; every screen must lay out without clipping at the largest offered scale. Element colours come from Settings `a11y_element_palette` (`standard` or the colour-blind-safe `colorblind` palette from the art bible), and every element is always drawn with its non-colour glyph and name in either palette. Motion is limited to short transitions, and Settings `a11y_reduced_motion` removes them (Settings R12a, user decision 2026-11-16).

**R17 — No pause.** No guild screen pauses the simulation, including dialogs and the shop: the guild keeps working while the player reads. (Answers Sim core OQ-7 for Guild screens; whether Settings or a modal ad needs `pause()` is theirs.)

**R18 — Onboarding hooks.** Each primary control has a stable anchor ID (`ui_anchor.<screen>.<control>`) so Onboarding (44) can highlight it and listen for its use without depending on layout. Anchor IDs are part of this system's interface and change only with a note in Cross-References.

### States and Transitions

**Shell states.**

| State | Shown | Enters from | Leaves to |
|---|---|---|---|
| `Booting` | Loading screen (core string set) | App start | `Resolving` (a gap needs offline resolution), `Running`, `Fatal`, `BlockedNotice` |
| `Resolving` | Resolving overlay with progress; input blocked | `Booting`, app resume after a gap | `Running` (report queued at priority 3), `Fatal` |
| `Running` | Header, tabs, content | `Booting`, `Resolving`, `CatchingUp`, `BlockedNotice` (dismissed) | `CatchingUp`, `BlockedNotice`, `Fatal`, `Resolving` (resume after gap) |
| `CatchingUp` | As `Running`, plus the indicator; slower refresh (F2); toasts held | `Running` when facade `catching_up` or `handoff_pending` becomes true | `Running` when both are false (summary toast), `Fatal` |
| `BlockedNotice` | Priority-1 blocking screen | `Booting`, `Running` | `Running` (dismissed where allowed), app quit, `Booting` (reload) |
| `Fatal` | Priority-0 screen | Any state | `Booting` (reload last / older save), app quit |

There is no transition out of `Fatal` except a new core instance or quitting (Sim core R10).

**Screen states** (each open screen): `Live` (cache current) → `Dirty` (an event or outcome concerns it) → `Live` after the F2 re-read; `Live`/`Dirty` → `Covered` (a dialog on top; still marks dirty) → re-read on uncover; any → `Closed` (cache dropped). A screen whose data owner reports the target gone (a departed member, a sold item) moves to `Gone`: it shows the last known name read-only with "no longer in the guild" or "no longer in storage", and disables every action.

**Order marker states** (per `seq`): `Pending` → `Applied` (shown for `ui_ack_show_ms`, then cleared) or `Refused` (shown until the player dismisses it, the screen closes, or a new order is given to the same target). A host refusal goes from nothing straight to `Refused`. `Pending` shows "waiting for the guild" while the shell is `CatchingUp`. All markers clear on `Booting`.

### Interactions with Other Systems

| System | Direction | Data in | Data out | Interface owner |
|---|---|---|---|---|
| Command layer (5) | 39 → 5 | `[seq, reason]` from `submit` / `submit_batch`; outcome events | Commands with the owner's payloads | Command layer |
| Localization (4) | 39 → 4 | `text()`, F1, F2, F3, F4, F6; core string set | Keys and typed arguments | Localization |
| Sim core (1) | 1 → 39 | Facade: event batch, `tick`, `alpha`, `catching_up`, `handoff_pending`, `debt_us`; fatal state | None (no pause, R17) | Sim core (**provisional**: R15 names only 38 and 40) |
| Member model (8) | 8 → 39 | Record, profile, name record | Rename command | Member model |
| Member state machine (41) | 41 → 39 | State, timers, needs, current order; events 4101–4103 | Hunt / Return / Stay home / Clear order | MSM |
| CA/PA and traits (9) | 9 → 39 | `pa_view`, `traits_view`, `ca`; events 901–904 | Use lens command | CA/PA |
| Party (13), Utility AI (12) | → 39 | Party records, R15 warnings; R8 breakdowns, F3 badges | Party edit commands | Party, Utility AI |
| Recruitment (15) | 15 → 39 | Board state, cards, refusal reasons; event 1501 | Accept / Pass / Pass all | Recruitment |
| Items and loot (26) | 26 → 39 | Storage read model, hand-in summary | Award, equip | Items and loot |
| Guild and buildings (30) | 30 → 39 | Levels, queue, costs, previews, refusal reasons | Build / cancel | Guild and buildings |
| Gold economy (27) | 27 → 39 | Balances, totals, metrics, events | Tax rate (VS) | Gold economy |
| Zones and hunt (11), Combat (10) | → 39 | Zone/ground panels, trip state, trip report; matchups | Hunt here / Order home | Zones and hunt |
| Golden Boss (14) | 14 → 39 | Announcement, gathering counter, raid record | Opt-out, summon | Golden Boss |
| Offline progress (31) | 31 → 39 | Summary record, resolving progress | None | Offline progress |
| Local save (6), Account (7) | → 39 | Notice kinds and their facts | Player's choice on the notice | Those systems; layout here |
| XP (22), Skills (21), Schools (20), Rebirth (23) | → 39 | Level/XP, skill states, school state and costs, `rebirth_status` | Their commands | Owners |
| Enhancement (24), Market (29), Crafting (28), Retention (16) | → 39 (VS) | Their screen read models | Their commands | Owners |
| IAP (34), Entitlement (32) | → 39 | Shop data; entitlement snapshot (`is_premium`, exact-PA flag) | Open shop / buy | IAP; Entitlement (**provisional**, no GDD) |
| Realtime world view (38) | peer | Map scene in the Map tab; member taps open G4 | Selection focus ("show on map") | **Provisional**, no GDD |
| Ads (33) | 33 ↔ 39 | Banner fill state | Reserve strip size | **Provisional**, no GDD |
| Settings (45) | 45 → 39 | `a11y_text_scale`, `a11y_element_palette`, `a11y_reduced_motion` (Settings R3, R12a); haptics, language | None | Designed (`settings.md`); haptics still provisional |
| Onboarding (44) | 39 → 44 | — | Anchor IDs and their use events (R18) | Guild screens |
| Audio (40) | 39 → 40 | — | UI cue names (Visual/Audio) | **Provisional**, no GDD |

## Formulas

### F1 — Countdown display

The countdown_s formula is defined as:

`countdown_s = max(0, ceil(((due_tick − tick) − alpha) × tick_us / 1,000,000))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| due_tick | int64 | ≥ 0 | calculated (owner's read model) | tick at which the timed thing happens (build done, boss, arrival, revival) |
| tick | int64 | ≥ 0 | calculated (facade) | last committed tick |
| alpha | float | 0.0 – 1.0 | calculated (facade, Sim core F3) | fraction of the next tick already elapsed |
| tick_us | int | 100,000 | constant (Sim core `tick_rate` = 10 Hz) | microseconds per tick |

**Output Range:** 0 to the owner's longest timer, in whole seconds, rendered by Localization F6. `ceil` means the label never shows 0 before the event is due. At or after `due_tick` it shows the owner's "now" text until the event arrives and the screen re-reads. While catching up `alpha` is clamped to 1.0, so the countdown drops in steps; that is correct, the guild is catching up.
**Example:** `due_tick − tick = 1,000`, `alpha = 0.4` → `999.6 × 0.1 = 99.96` → `100` s → "1 phút 40 giây" / "1m 40s".

### F2 — Refresh gate

The may_refresh formula is defined as:

`may_refresh = dirty AND visible AND (now_ms − last_read_ms ≥ (catching_up ? ui_catchup_refresh_ms : ui_refresh_min_ms))`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| dirty | bool | — | calculated (R6) | an event, outcome or locale change concerns this screen |
| visible | bool | — | calculated | screen is on top of its tab and the tab is shown |
| now_ms, last_read_ms | int64 | ≥ 0 | calculated (wall clock, presentation only) | current time and time of this screen's last read |
| catching_up | bool | — | calculated (facade `catching_up OR handoff_pending`) | shell is `CatchingUp` |
| ui_refresh_min_ms | int | 100 – 1,000 | data file (`config.csv`, new key, default 200) | normal minimum interval between reads |
| ui_catchup_refresh_ms | int | 200 – 2,000 | data file (`config.csv`, new key, default 500) | interval while catching up |

**Output Range:** boolean. At the defaults a visible screen re-reads at most 5 times a second (every second tick) in normal play, and twice a second while catching up, whatever the tick rate. Wall time is used only by presentation and never reaches the simulation, so determinism is unaffected. A refresh that the gate holds back runs at the first frame the gate opens; a dirty flag is never lost.
**Example:** a member's state event arrives 120 ms after the last read: no read. The next frame at 200 ms reads once, even if three more events arrived meanwhile.

### F3 — Batch split

The batch_parts formula is defined as:

`allowed = premium ? n : min(n, ui_multiselect_free_max)` and `parts = ceil(allowed / host_pending_max)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n | int | 0 – `member_cap` (≤ 80) | calculated | members selected (or matched by a Premium filter) |
| premium | bool | — | calculated (entitlement snapshot, provisional) | Premium entitlement |
| ui_multiselect_free_max | int | 1 – 80 | data file (`config.csv`, new key, default 5) | Free selection cap |
| host_pending_max | int | 25 – `command_queue_max ÷ 2` | data file (Command layer F1, default 200) | host commands that may wait at once |
| parts | int | 0 – 4 | calculated | batches submitted one after another |

**Output Range:** `parts = 0` when nothing is selected (the order button is disabled). With the defaults every roster fits one part (80 ≤ 200). At the lowest legal `host_pending_max` (25) a Premium order to 80 members goes in 4 parts. Each part is submitted only after every outcome of the previous part has arrived. If a part is refused with `host_queue_full`, the remaining parts are not sent, the unsent members stay selected, and R5.4's message is shown.
**Example:** Free, 7 members ticked: the 6th and 7th checkboxes are disabled with "Premium: select more than 5", so `allowed = 5`, `parts = 1`.

### F4 — Confirmation threshold

The needs_confirm formula is defined as:

`needs_confirm = irreversible(action) OR (cost > 0 AND cost ≥ threshold)` where `threshold = (fund ÷ 1,000,000) × ui_confirm_spend_ppm + ((fund mod 1,000,000) × ui_confirm_spend_ppm) ÷ 1,000,000` (integer division)

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| cost | int64 | ≥ 0 | calculated (owner's read model) | gold the action costs; for a batch, the worst case (Enhancement "×N") |
| fund | int64 | ≥ 0 | calculated (Gold economy balance) | guild fund now |
| ui_confirm_spend_ppm | int | 0 – 1,000,000 | data file (`config.csv`, new key, default 100,000 = 10%) | share of the fund above which a spend is confirmed |
| irreversible(action) | bool | — | data file (per-action flag in the UI action table) | the action cannot be undone or refunded |

**Output Range:** boolean. The split form keeps `fund × ppm` from overflowing int64 for any fund. `ui_confirm_spend_ppm = 0` confirms every spend; `1,000,000` confirms only spends of the whole fund or more. At `fund = 0` any positive cost confirms, but such a button is already disabled as unaffordable (R7). Default irreversible actions: school change, Ascension, dismiss member, let a member go, pass on candidates, a crafting order (Crafting R6: cannot be cancelled), a store purchase. Building orders are not irreversible (cancel refunds in full, Guild and buildings). Every confirm shows the fund before and after (Gold economy UI 4). Owners that require a **second** confirm (Ascension, large cloud discards) use the same dialog twice, with the confirm button in a different position the second time.
**Example:** fund 50,000: a 120-gold potion (threshold 5,000) goes through at once; an 8,000-gold build asks "Spend 8,000? Fund 50,000 → 42,000".

### F5 — Toast duration

The toast_ms formula is defined as:

`toast_ms = clamp(ui_toast_base_ms + chars × ui_toast_ms_per_char, ui_toast_min_ms, ui_toast_max_ms)`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| chars | int | ≥ 0 | calculated | grapheme clusters in the rendered toast text |
| ui_toast_base_ms | int | 0 – 3,000 | data file (default 1,500) | fixed reading overhead |
| ui_toast_ms_per_char | int | 20 – 120 | data file (default 50) | reading time per character |
| ui_toast_min_ms / ui_toast_max_ms | int | 1,000 – 10,000 | data file (defaults 2,000 / 6,000) | bounds |

**Output Range:** 2,000 to 6,000 ms at the defaults. Vietnamese toasts, usually longer, stay longer. A toast longer than the max is still readable in full from the "+N more" list. Tapping a toast dismisses it at once.
**Example:** "Lý Thanh không thể đi săn: đang bị thương" (41 graphemes): `1,500 + 2,050 = 3,550` ms.

## Edge Cases

- **If a member leaves or is dismissed while their panel is open**: the panel moves to `Gone`, shows the name from the name record with "no longer in the guild", and disables every action. Pending orders for that member resolve as refused by their owners and are shown as such.
- **If the fund changes while a confirm dialog is open** (income, upkeep): the dialog re-reads under F2. If the spend becomes unaffordable, the confirm button disables with the missing amount. A dialog that is open stays open even if the spend now falls below the F4 threshold. The owner's refusal is still handled if the tap wins the race.
- **If the away report becomes due while a player-opened dialog is open**: it waits until the dialog closes (R8); badges update meanwhile.
- **If a priority-0 failure happens with pending orders and an open dialog**: everything is replaced by the fatal screen; its body states that orders since the last save are lost (Sim core R10); the pending set is cleared.
- **If the player taps repeatedly while catching up**: each order is pending ("waiting for the guild"); once `host_pending_max` is reached, further taps are refused at once with `host_queue_full`, shown once per burst as one toast, not one toast per tap.
- **If a batch part is refused with `host_queue_full`**: later parts are not sent and their members stay selected (F3); the player re-sends when ready.
- **If a Free player had a selection larger than the cap from a Premium period** (Premium refunded or expired): the selection is trimmed to the first `ui_multiselect_free_max` in display order the next time it is used, with a one-line note.
- **If Premium is lost**: Premium-only controls return to disabled with the badge on the next entitlement read; saved Premium data (Party presets) is shown as the owner decides, not deleted by the UI.
- **If two visible members share a display name**: each gets a short ID tag (R11). Sorting by name ties are broken by `member_id`.
- **If a name or content name does not fit** (Vietnamese, `qps`): content names use F4 `short` then ellipsis with the full name in the detail view; player names truncate with an ellipsis in rows and show in full in the member panel; UI strings wrap, never truncate.
- **If a countdown reaches 0 before its event arrives**: it shows the owner's "now" text (F1), never a negative time, until the event and the re-read.
- **If the locale changes with a text field half-typed** (rename): the typed text is kept and the next frame draws in the new locale (Localization R7).
- **If the ad banner fails to load or Ads is not yet built**: the reserve strip stays (Free) so nothing moves; on Premium it is 0 from the first frame after entitlement is read. A late Premium read causes at most one layout change per session.
- **If the OS back action is used during a blocking screen or the resolving overlay**: it does nothing (blocking screens accept only their own actions); on the fatal screen it is the same as "Quit" only if the platform requires it.
- **If a screen for a not-yet-live system is linked from another screen** (e.g. a leave demand for a building whose screen is VS): the link is hidden; the owning text still explains the demand.
- **If the roster has more members than one screen shows**: rows are virtualised; the state-count line ("12 hunting · 3 resting · 1 injured", MSM) is computed from the full read model, not from the visible rows.
- **If an owner's read model is unavailable for a live screen** (a bug): the screen shows an empty state with a generic "not available" text and logs the owner ID once per session; it never shows stale values as current.
- **Degenerate use — tapping "Pass" to reroll recruitment candidates**: not a UI concern; Recruitment's cadence rules bound it. "Pass on all" is single-confirmed because the candidates are lost (F4 irreversible).

## Dependencies

### Upstream (this system depends on)

| System | Hard / Soft | Interface | Status |
|---|---|---|---|
| Command layer (5) | Hard | `submit`, `submit_batch`, `[seq, reason]`, outcome events, `host_pending_max` | Designed |
| Localization (4) | Hard | `text()`, F1–F4, F6, core string set R11, `qps` R15 | Designed |
| Sim core (1) | Hard | Facade (R15), fatal state (R10) | Needs Revision; **provisional** facade access for 39 |
| Member model (8), Member state machine (41), CA/PA (9), XP (22), Skills (21), Schools (20) | Hard | Member panel and roster read models | Designed |
| Party (13), Utility AI (12), Combat (10) | Hard (Party), Soft (12, 10) | Party panel data | Designed |
| Items and loot (26) | Hard | Storage read model, award | Designed |
| Guild and buildings (30), Gold economy (27) | Hard | Building screen, header, treasury | Designed |
| Recruitment (15) | Hard | Board | Designed |
| Zones and hunt (11) | Hard | Zone, ground, trip panels | Designed |
| Golden Boss (14) | Hard | Banner, opt-out, result | Designed |
| Offline progress (31) | Hard | Summary record, resolving progress | Designed |
| Local save (6), Data layer (3) | Hard | Notices, data-damaged screen, `config.csv` keys | Designed |
| Retention (16), Enhancement (24), Market (29), Crafting (28) | Hard for their VS screens | Their read models and commands | Designed |
| Rebirth (23), IAP (34), Account (7) | Hard for their Alpha screens | Their read models | Designed |
| Entitlement (32) | Soft (Premium gating display) | Entitlement snapshot | **Not designed — provisional** |
| Realtime world view (38) | Hard (Map tab content) | Map scene, member selection | **Not designed — provisional** |
| Ads (33), Settings (45), Audio (40), Quests (25), Event bus (42, Chronicle) | Soft | Reserve strip; preferences; UI cues; quest board; `read_history` | Not designed / Needs Revision — provisional |

### Downstream (systems that depend on this one)

| System | Interface |
|---|---|
| Onboarding and tutorial (44) | Anchor IDs and their use events (R18); founding offers framed on the recruitment board |
| Settings (45) | Hosted in the More tab; MVP language stand-in G13 hands over to it |
| Every system above whose UI Requirements name Guild screens | Layout, navigation and the shared patterns R5–R16 |

**Bidirectionality.** Command layer, Localization, Member model, MSM, CA/PA, Party, Utility AI, Combat, Items, Guild and buildings, Gold economy, Recruitment, Zones and hunt, Golden Boss, Offline progress, Local save, Skills, Schools, XP, Rebirth, Enhancement, Market, Crafting, Retention, IAP and Sim core already name Guild screens (39) as a dependent. The systems index row lists 11 of them; it is widened to the full list here. Market (29) OQ-13 asked this GDD to list it: done.

## Tuning Knobs

All new keys are proposed `config.csv` keys; adding them and their validator bounds belongs to the Data layer (Open Questions).

| Knob | Default | Safe range | Too high | Too low | Interacts with |
|---|---|---|---|---|---|
| `ui_refresh_min_ms` (F2) | 200 | 100 – 1,000 | Values lag behind the map; feels stale | Wasted reads on large lists; frame drops on mid-range phones | `ui_catchup_refresh_ms` |
| `ui_catchup_refresh_ms` (F2) | 500 | 200 – 2,000 | Catch-up looks frozen | Catch-up competes with the core for frame time | Sim core catch-up budget |
| `ui_multiselect_free_max` (F3) | 5 | 1 – 80 | Premium's bulk value disappears | Free multi-select is useless; one tap per member | `party_max` (5 matches one party) |
| `ui_confirm_spend_ppm` (F4) | 100,000 | 0 – 1,000,000 | Big mistakes pass unconfirmed | Confirm fatigue; players stop reading | Gold economy income scale |
| `ui_confirm_arm_ms` | 300 | 0 – 1,000 | Dialog feels sluggish | Double-tap goes through the confirm | — |
| `ui_ack_show_ms` (R5) | 800 | 300 – 2,000 | Applied marks clutter lists | Player misses the confirmation | — |
| `ui_toast_base_ms`, `ui_toast_ms_per_char`, `ui_toast_min_ms`, `ui_toast_max_ms` (F5) | 1,500 / 50 / 2,000 / 6,000 | See F5 | Toasts pile up | Unreadable, especially in Vietnamese | `ui_toast_queue_max` |
| `ui_toast_queue_max` (R8) | 5 | 1 – 20 | Stale toasts shown long after the fact | Information collapses into "+N more" early | F5 |
| `ui_banner_max` (R8) | 2 | 1 – 3 | Banners cover the content area | Important banners hidden | — |
| `ui_badge_max` (R14) | 99 | 9 – 999 | Wide badges break the tab bar | "9+" hides real counts | — |
| `ui_stack_depth_max` (R3) | 3 | 2 – 4 | Player gets lost | Detail views cannot open a picker | — |
| `ui_touch_min_px` (R16) | 44 (logical px at the 360 × 640 reference) | 40 – 64 | Fewer rows per screen | Mis-taps; accessibility failure | Text scale |
| `ui_ad_banner_reserve_px` (R2) | 50 (logical px) | 0 – 90 | Wasted space | Banner overlaps the tab bar | Ads (33) banner size (provisional) |

Owned elsewhere and not duplicated: `host_pending_max` (Command layer), `offline_report_min_s` (Offline progress), `ai_explain_top_n` (Utility AI), `member_name_max_len` (Member model), `l10n_compact_threshold` and `l10n_duration_units` (Localization), `recruit_offer_size_max` (Recruitment).

## Visual/Audio Requirements

*Art-director lens applied in this conversation (no agent spawned). No art bible exists (`design/art/` is absent), so this is drafted from §1, §3.5 and §12.4 and must be re-checked when the art bible is written.*

1. **Visual feedback per event.** Pending: a small animated pixel hourglass on the control and row. Applied: a check mark for `ui_ack_show_ms`. Refused: a cross icon plus the reason text, never a red tint alone. Badge: a numbered seal shape on the tab icon. Level-up and new arrivals on screens use a one-time glint on the row, not a particle burst (the world view owns spectacle).
2. **Style constraints.** Pixel-art panels from one 9-slice frame family (the "master's study" direction: lacquer, paper, seals). Rarity is shown by frame shape and a text label (Items UI). Element glyphs are icon + name (Schools, Zones), always shown; element colours have a standard and a colour-blind-safe set (Settings R12a). School icons are distinct in silhouette, not only in palette. No readable text in any art asset (Localization R12). Pixel fonts must cover Vietnamese stacked diacritics (Localization Visual/Audio).
3. **Performance.** UI icons in one atlas; no full-screen blur or shader effects on panels; lists reuse row nodes (§3.5: 30 FPS mid-range).
4. **Audio (provisional, Audio 40).** Cue names this system emits: `ui_tap`, `ui_confirm`, `ui_refused`, `ui_toast`, `ui_modal_open`, `ui_badge_new`. UI cues mix below world and boss cues; `ui_refused` is the only one that must be audible over gameplay. All UI cues are suppressed while catching up, except the summary.

> 📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:guild-screens` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

- **Same-frame response.** Every tap shows a pressed state and, for an order, its pending marker in the same rendered frame (≤ 33 ms at 30 FPS). The applied mark normally arrives one tick later (100 ms, Command layer F2).
- **Fast screens.** A detail screen opens with a transition of at most 150 ms (0 with reduced motion) and is fully populated on its first frame from the cache or one read; no spinner for local data.
- **No jitter.** Numbers use fixed-width (tabular) digits and F2 flooring so a rising fund never flickers (Localization Game Feel). Rows do not reorder while the player is touching the list; a re-sort waits until the touch ends.
- **Safe confirms.** Confirm buttons ignore taps for `ui_confirm_arm_ms` after a dialog opens, so a double-tap cannot pass through it. A second confirm moves the button.
- **Long-press** (500 ms) shows the exact value of a compact number and the full name of a truncated one.
- **Haptics** (mobile, optional, Settings 45): a light pulse on a refused order only. Haptics APIs are NOT SOURCEABLE in `docs/engine-reference/godot/` (→ ADR).
- **Scroll.** An 80-member roster scrolls at the game's 30 FPS target on a mid-range Android phone.

## UI Requirements

This whole system is UI. The screens and their contents are R4's inventory; the patterns are R5–R16. Before epics, the following UX specs must exist:

- `design/ux/interaction-patterns.md` — order acknowledgement (R5), confirmations (F4), disabled-with-reason (R7), notifications and their priority (R8), badges (R14), multi-select (R9), lists (R11). Command layer's UX flag points at this file.
- `design/ux/shell.md` — header, tab bar, ad reserve, safe area, navigation stack, back behaviour, catching-up indicator, blocking-screen shell (R2, R3, R12, R13).
- One spec per MVP screen G2–G13, then per later screen as its tier is scheduled. Each spec includes `vi`, `en` and `qps` states.

> **📌 UX Flag — Guild screens**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for each screen or HUD element this system contributes to **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This document references | Target GDD | Specific element | Nature |
|---|---|---|---|
| Order acknowledgement and batch split | `command-layer.md` | R6, R11, R12, R14, F1, UI Requirements 1–6 | Implements |
| Read between ticks; facade; fatal screen | `sim-core-and-tick-loop.md` | R10, R14, R15, R17, F3, OQ-2, OQ-7 | Rule dependency; answers OQ-7 (no pause from 39) |
| Text, numbers, durations, fit, core strings, `qps` | `localization.md` | R1, R7, R11, R13, R15, F1–F4, F6 | Rule dependency |
| PA display limits | `ca-pa-and-traits.md` | R10, R12, AC-25 | Rule dependency |
| Member panel contents; name length | `member-model.md` | UI Requirements, `member_name_max_len`, OQ-11 | Data dependency; accepts 20 |
| State labels, order buttons, multi-select | `member-state-machine.md` | UI Requirements | Data dependency |
| Party panel; warnings | `party.md`, `utility-ai.md` | Party R15, UI Requirements; Utility AI R8, F3 | Data dependency |
| Storage, award flow | `items-and-loot-tables.md` | UI Requirements, R8 reasons | Data dependency |
| Building screen; header | `guild-and-buildings.md` | UI Requirements 1–6 | Data dependency |
| Fund, confirmations, numbers | `gold-economy.md` | UI Requirements 1–5 | Data dependency; see OQ on compact threshold |
| Recruitment board | `recruitment.md` | UI Requirements | Data dependency |
| Zone, ground, trip panels | `zones-grounds-monsters-and-hunt-trips.md` | UI Requirements | Data dependency |
| Boss banner, opt-out, result | `golden-boss-and-guild-raid.md` | UI Requirements, AC-24 | Data dependency |
| Away report, resolving overlay | `offline-progress.md` | UI Requirements, AC-21, `offline_report_min_s` | Data dependency |
| Notices | `local-save-and-migration.md`, `account-and-cloud-save.md`, `data-layer-and-content-pipeline.md` | UI Requirements | Layout for their facts |
| VS/Alpha screens | `equipment-enhancement.md`, `guild-market-and-trade-orders.md`, `crafting-and-recipes.md`, `retention-leaving-and-negotiation.md`, `rebirth-and-ascension.md`, `in-app-purchases.md`, `skills.md`, `schools-and-school-change.md`, `xp-and-level-pacing-curve.md`, `endless-tower.md` | UI Requirements | Data dependency |
| Chronicle reads | `event-bus-and-history-log.md` | R8 `read_history`, OQ-8 | Open ownership |

## Acceptance Criteria

Criteria marked **[Logic]** need an automated test in `tests/unit/guild_screens/`; **[UI]** need a retained screenshot in `production/qa/evidence/` in each locale touched; **[Playtest]** are playtest questions.

**Core rules**
- **AC-1 [Logic] (R1)**: **GIVEN** a code search of `src/ui/`, **WHEN** it looks for writes to simulation state or calls into the core loop, **THEN** none exist; every player action goes through `submit` or `submit_batch`, and reads of PA or hidden traits use only `pa_view` / `traits_view` (CA/PA AC-25).
- **AC-2 [Logic] (R5)**: **GIVEN** a stub command layer, **WHEN** `submit` returns `seq = 7`, **THEN** a pending marker for 7 exists in the same frame; **WHEN** `command_applied(7)` arrives, **THEN** the marker becomes applied and clears after `ui_ack_show_ms`; **WHEN** `command_refused(8, reason)` arrives for a target off screen, **THEN** one toast with the reason's localised text is queued.
- **AC-3 [Logic] (R5.3–5.4)**: **GIVEN** a release build, **WHEN** a refusal with reason code 3 arrives, **THEN** the generic text is shown, not the code name; **WHEN** `submit` returns `[0, host_queue_full]`, **THEN** the "guild is busy" text is shown and no further `submit` happens without a new tap.
- **AC-4 [Logic] (R5.5–5.6)**: **GIVEN** a pending order and `catching_up = true`, **THEN** its marker text is "waiting for the guild"; **GIVEN** any pending orders, **WHEN** a save is loaded, **THEN** the pending set is empty.
- **AC-5 [UI] (R2)**: **GIVEN** a Free build on a 360 × 640 reference viewport, **THEN** a screenshot shows header, content, five labelled tabs and an empty reserve strip of `ui_ad_banner_reserve_px`; **GIVEN** Premium, **THEN** the strip is 0 and the tab bar sits at the bottom of the safe area.
- **AC-6 [Logic] (R3)**: **GIVEN** the Members tab with root → member panel → equip picker open, **WHEN** back is pressed three times, **THEN** the picker closes, then the panel, then the app shows Map; **WHEN** back is pressed at the Map root, **THEN** a quit confirmation opens.
- **AC-7 [Logic] (R4, R7)**: **GIVEN** content with `content_wave` above the live wave, **THEN** it has no row on any screen; **GIVEN** a Premium-only control on Free, **THEN** it is visible, disabled, and has a Premium badge and reason text.
- **AC-8 [Logic] (R8)**: **GIVEN** a Golden Boss result card (P5) open, **WHEN** an away report (P3) is queued, **THEN** the report pre-empts it and the result card is shown after the report closes; **GIVEN** a player-opened confirm dialog, **WHEN** a P3 report is queued, **THEN** it waits until the dialog closes; **WHEN** a P0 failure occurs, **THEN** the fatal screen replaces everything at once.
- **AC-9 [Logic] (R8)**: **GIVEN** 8 toasts queued with `ui_toast_queue_max = 5`, **THEN** at most 5 entries are queued and the oldest are collapsed into one "+N more" entry listing them all.
- **AC-10 [Logic] (R9, F3)**: **GIVEN** Free and `ui_multiselect_free_max = 5`, **WHEN** a 6th member is ticked, **THEN** it is refused with the Premium text and 5 commands go in one `submit_batch`; **GIVEN** Premium, `host_pending_max = 25` and 80 selected, **THEN** 4 batches of 25, 25, 25 and 5 are submitted, each only after the previous batch's outcomes have all arrived.
- **AC-11 [Logic] (F3 edge)**: **GIVEN** the second of 4 parts is refused with `host_queue_full`, **THEN** parts 3 and 4 are not submitted and their 30 members stay selected.
- **AC-12 [Logic] (R10)**: **GIVEN** `credited_s` one second below `offline_report_min_s`, **WHEN** the game resumes, **THEN** a toast and no report; **GIVEN** exactly `offline_report_min_s`, **THEN** the report opens, and the Members badge already includes the leave requests filed while away.
- **AC-13 [Logic] (R11)**: **GIVEN** two members with the same CA and shown stars, **WHEN** the roster is sorted by stars, **THEN** they order by `member_id` in both locales; **GIVEN** the sort options, **THEN** none reads hidden `pa`.
- **AC-14 [Logic] (R12)**: **GIVEN** 40 order-refused events during catch-up, **THEN** no per-event toast is shown until catch-up ends, then one summary toast.
- **AC-15 [UI] (R13)**: **GIVEN** a forced core failure and a forced data failure in a dev build with `i18n/` unreadable, **THEN** screenshots show both fatal screens rendered from the core string set with exactly their owners' actions and no "continue" (covers Sim core AC-35 and Data layer AC-28 layout).
- **AC-16 [Logic] (R14)**: **GIVEN** an open recruitment offer and two leave requests, **THEN** the Members badge reads 3; **GIVEN** 150 actionable items and `ui_badge_max = 99`, **THEN** it reads "99+".
- **AC-17 [Logic] (R15)**: **GIVEN** a rename of 21 code points with `member_name_max_len = 20`, or of only spaces, **THEN** the submit button is disabled with the reason; a 20-code-point name in NFD form is normalised to NFC before the length check.
- **AC-18 [UI] (R15, R16)**: **GIVEN** each MVP screen G2–G13 in `vi`, `en` and `qps` at the largest offered text scale (`a11y_text_scale` = 150), **THEN** screenshots show no clipped or overlapping text, and every state, element, rarity and refusal is readable with colours removed (greyscale capture); a further capture with `a11y_element_palette = colorblind` shows the swapped element colours with icons and names intact.
- **AC-19 [Logic] (R16)**: **GIVEN** the MVP screens' scene trees, **THEN** every interactive control is at least `ui_touch_min_px` in both dimensions and has a non-empty accessible name.
- **AC-20 [Logic] (R17)**: **GIVEN** any guild screen or dialog open for 10 seconds, **THEN** `tick` advanced by about 100 and `pause()` was never called.
- **AC-21 [Logic] (R18)**: **GIVEN** the MVP build, **THEN** every control listed in the shell and screen UX specs as primary has a unique `ui_anchor` ID, and a tap on it emits the anchor's use signal once.

**Formulas**
- **AC-22 [Logic] (F1)**: **GIVEN** `due_tick − tick = 1,000`, `alpha = 0.4`, **THEN** 100 s; **GIVEN** `due_tick − tick = 1`, `alpha = 0.99`, **THEN** 1 s (not 0); **GIVEN** `due_tick ≤ tick`, **THEN** 0 and the "now" text.
- **AC-23 [Logic] (F2)**: **GIVEN** a dirty visible screen read 120 ms ago, **THEN** no read; at 200 ms one read, even after 3 more events; **GIVEN** `catching_up`, **THEN** reads are at least 500 ms apart; **GIVEN** a hidden dirty screen, **THEN** no read until it is shown, and then one.
- **AC-24 [Logic] (F4)**: **GIVEN** fund 50,000 and 100,000 ppm, **THEN** cost 4,999 → no confirm, 5,000 → confirm; **GIVEN** cost 0 and an irreversible action, **THEN** confirm; **GIVEN** fund `9,000,000,000,000,000`, **THEN** the threshold is computed without overflow as `900,000,000,000,000`.
- **AC-25 [Logic] (F5)**: **GIVEN** 0, 41 and 200 graphemes, **THEN** 2,000, 3,550 and 6,000 ms.

**Cross-system and feel**
- **AC-26 [UI] [PENDING: owners' UX specs]**: **GIVEN** a tap on "Hunt here" for three members, one injured, **THEN** a screenshot in the tap frame shows three pending markers, and one taken a tick later shows two applied and one refused with the localised MSM reason (covers Command layer AC-23).
- **AC-27 [UI]**: **GIVEN** an away report from a 9 h 12 m Free absence, **THEN** a screenshot shows the Offline progress headline and cap line (covers Offline AC-21 layout), followed by the decision lines.
- **AC-28 [UI]**: **GIVEN** a party without a buffer, **THEN** a screenshot of the party panel shows the "thiếu buffer" tag with its icon (covers Party AC-29).
- **AC-29 [Logic] (performance)**: **GIVEN** an 80-member roster on the reference mid-range Android phone, **WHEN** the list is flung for 10 seconds while the map runs behind it, **THEN** the frame rate stays at or above 30 FPS for at least 95% of frames.
- **AC-30 [Playtest] (Player Fantasy)**: **GIVEN** a tester returning after an 8 h absence with one leave request and one candidate offer, **THEN** they find and resolve both within 60 seconds without help; and (Schools Fantasy 1) can name the guild's missing role within 10 seconds of opening the roster.

*QA lens applied (no agent spawned): every rule R1–R18 and F1–F5 has a criterion; boundary values are tested for F1 (1 tick, due), F3 (cap, minimum host cap), F4 (threshold, overflow) and F5 (min, max). Gaps: R6's subscription lists per screen and the full notice set are verified in the UX specs' screenshots rather than here.*

## Open Questions

| # | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **PROVISIONAL: Sim core (1)** — R15's facade names only World view (38) and Audio (40). Guild screens assume the same facade (event batch, `tick`, `alpha`, `catching_up`, `handoff_pending`, `debt_us`) plus permission to call owners' read APIs between ticks. | Sim core | Its revision |
| OQ-2 | **PROVISIONAL: Realtime world view (38)** — the Map tab hosts 38's map scene; 39 owns the header (incl. the boss countdown and fund) and the zone/ground panels drawn over the map; 38 owns in-world overlays. Tapping a member on the map opens G4. | World view (38) | When 38 is designed |
| OQ-3 | **PROVISIONAL: Entitlement (32)** — the snapshot exposes at least `is_premium` and the exact-PA-all flag, read-only, and changes are signalled by an event or a version number the UI can watch. | Entitlement | Alpha |
| OQ-4 | **PROVISIONAL: Ads (33)** — a fixed bottom banner of 50 logical px on Free only; no interstitials (§11.2); rewarded ads only from the quest board. The banner height is a common AdMob size, not sourced from the engine reference; confirm with the ad plugin in the P1 spike. | Ads (33) | P1 spike |
| OQ-5 | **Partly RESOLVED (user decision 2026-11-16):** Settings (45) now defines text size, colour-blind element palette and reduced motion (Settings R12a), consumed by R16. Still PROVISIONAL: haptics. Settings owns the Settings screen (language, accessibility, account, restore purchases). Until it lands, G13 in the More tab is the MVP stand-in for the language list required by Prompt P3. | Settings (45) | Vertical Slice |
| OQ-6 | **PROVISIONAL: Onboarding (44)** — uses anchor IDs (R18) and the use signal; needs no other hook. | Onboarding (44) | Alpha |
| OQ-7 | **PROVISIONAL: Quests (25)** — a quest board screen (G21) in the More tab and Cáo Thị Đường, VS. Contents unknown until 25 is designed. | Quests (25) | Vertical Slice |
| OQ-8 | **PROVISIONAL: Audio (40)** — the UI cue names in Visual/Audio. | Audio (40) | Alpha |
| OQ-9 | **PROVISIONAL: Data layer (3)** — the `ui_*` keys in Tuning Knobs are new `config.csv` keys with the stated bounds for the validator; plus a UI action table carrying the F4 `irreversible` flag. Not added here. | Data layer (3) | With the first UI story |
| OQ-10 | **Chronicle ownership** (Event bus OQ-8): is G24 a Guild screen (39) or Guild and buildings' (30)? This GDD lists it provisionally and does not claim it; paging and caching rules stay unwritten until it is assigned. | Systems index owner | Before Alpha |
| OQ-11 | **Premium bulk actions** — §11.2 lists "thao tác hàng loạt" as a *suggested* Premium feature. This GDD keeps Free multi-select up to 5 and makes select-all / apply-to-filter Premium (R9). Confirm the split. | User / creative director | Before VS |
| OQ-12 | **Premium analytics screen** — §11.2 suggests "thống kê chi tiết/phân tích bang" for Premium. No owner or screen exists; not added (scope). | User / systems index | Alpha |
| OQ-13 | **RESOLVED (consistency-check 2026-11-16):** Gold economy UI item 5 now defers to Localization F2 (`l10n_compact_threshold` = 10,000). | Gold economy / Localization | Closed |
| OQ-14 | **Text scale and minimum font size** — offered scales are now Settings `a11y_text_scale_options` (100;125;150 %, user decision 2026-11-16). The minimum base font size is still set by the art bible with the pixel font (Localization OQ); R16 requires layouts to survive 150 %. | Art bible / Settings (45) | Before UI stories |
| OQ-15 | **Absolute dates** (Localization OQ-10) — Guild screens use durations everywhere except save notices and backup times, which need a local date-time. The format is Localization's. | Localization | Vertical Slice |
| OQ-16 | **Landscape / PC layout** — portrait-locked in MVP (decision logged). The PC/Steam port needs a two-pane layout and keyboard focus (Godot 4.6 dual focus). | Guild screens | Before the PC port |
| OQ-17 | **Engine feasibility gaps** — safe-area insets, haptics and AccessKit behaviour on Android are NOT SOURCEABLE in `docs/engine-reference/godot/modules/ui.md`; verify in the P1 spike (→ ADR). Stretch mode `canvas_items` / aspect `expand` (4.7 new-project default) is assumed. | Technical director | P1 spike |
