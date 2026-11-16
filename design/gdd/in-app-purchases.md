# In-app Purchases (Premium, exact-PA items)

> **Status**: Designed (pending independent /design-review)
> **Author**: user + Claude (autonomous batch run, decisions logged in `production/session-logs/decision-log.md`)
> **Last Updated**: 2026-11-16
> **Last Verified**: 2026-11-16
> **Creative Director Review (CD-GDD-ALIGN)**: NOT ASSESSED 2026-11-16 — no game pillars, concept or brief exist to check against (see Post-design note at the end of Open Questions)
> **Implements Pillar**: None (no game-pillars.md yet). Serves the locked GDD §2 rows "1 app + IAP Premium mua một lần", "PA chính xác bán riêng, không nằm trong Premium" and "Bán cả Thiên Cơ Kính và Thiên Nhãn", and the §11.2 rule "không bán sức mạnh trực tiếp".

## Summary

In-app purchases is the store-facing service that sells the game's three kinds of product: the one-time **Premium** unlock, the **Thiên Nhãn** permanent exact-PA unlock, and packs of **Thiên Cơ Kính** consumable lenses that reveal one member's exact PA. It takes a store purchase, has the backend verify the receipt, records the result on the player's account, and then either writes a non-consumable ownership record (which Entitlement turns into "Premium" and "exact PA for all") or delivers lenses into the guild's storage exactly once. It exists because the game is a commercial, solo-developed title whose only revenue besides ads is these purchases (GDD §2, §11), and because a paid consumable that a cloud-save conflict could erase or duplicate would be a refund and a review waiting to happen.

> **Quick reference** — Layer: `Feature` · Priority: `Alpha` · Key deps: `Account and cloud save (7)`; depended on by `Entitlement and feature flags (32)`, `CA/PA and traits (9, via Items storage)`, `Items and loot (26, storage give/take)`, `Command layer (5, two host commands)`

## Overview

In-app purchases (IAP) is a host-level service (GDD §3.2 `[Services]`: "IAP, Entitlement(Free/Premium)") that sits outside the deterministic simulation. It owns the **product catalog** (five store products, R2), the **purchase transaction** from the moment the player taps *Buy* until the store has been told the purchase is finished (R4–R7), the **server-side purchase ledger** keyed by `account_id` (R5), **restore purchases** for non-consumables (R10), **refund and revocation** handling (R11), and the **delivery** of purchased Thiên Cơ Kính into the simulation through one host command (R8). It never decides what a purchase *unlocks*: Premium features and the `exact_pa_all` display overlay are Entitlement's (32) derivation from the ledger, and the lens effect is CA/PA's (9) `use_pa_lens` command. It never writes simulation state directly: the only way a purchase changes the save is a host-origin `grant_store_item` command that the Command layer logs and the leaderboard verifier can replay (Command layer R8–R9), and no product changes any simulation value except the count of `item_pa_lens` in guild storage (CA/PA AC-24 "no power sold"). Players see it as a shop panel with localized store prices, a *Restore purchases* button, and a short "delivering…" note when the network is slow. Implementation choices — the Godot billing plugin, the Supabase Edge Function layout, the store-notification webhook, and secret storage — become ADRs.

*Framing: technical (Meta category, recommended option); no ADR exists yet, so none is cited. Player effect is stated where it matters.*

## Player Fantasy

**"A fair shop that never cheats me and never sells my rivals power."** This is an indirect fantasy (Meta category): the player does not enjoy the purchase system, they enjoy what it protects. The moment: a player who bought a 5-pack of Thiên Cơ Kính loses their phone, signs in on a new one, picks the cloud save from yesterday, and the two lenses they had not used are still in storage — while the member they revealed last week still shows the seal on her exact PA. Nothing was lost, nothing was double-counted, and nobody on the guild leaderboard got stronger by paying.

Three supporting promises the rules must keep:

- **Money buys knowledge and comfort, never strength.** Premium removes ads and adds convenience; Kính and Nhãn reveal a number that already exists. A paying and a free guild with the same seed and commands play out identically (CA/PA AC-24).
- **What I paid for follows my account.** Premium and Thiên Nhãn come back through *Restore purchases* on any device; unspent paid lenses come back through the account ledger even after a save conflict.
- **No surprises at the till.** Every price shown is the store's own localized price; nothing is randomized; nothing is bought by accident (one confirm, R4).

*`creative-director` lens applied in this run (no agent spawned). No game pillars exist, so framings were anchored to GDD §2 and §11.2 text; the "fair shop" framing was chosen over "the reveal moment" because the reveal moment belongs to CA/PA's Player Fantasy.*

## Detailed Design

> Specialist lenses applied (SKILL §6 routing; `Meta` → Foundation/Infrastructure row, plus the Economy row because the system prices products): **systems-designer** (primary), **economy-designer** (pricing), **gameplay-programmer** and **engine-programmer** (supporting). Points are folded into the rules; the one disagreement is recorded under R8.
> - systems-designer: a consumable has two copies of the truth (server ledger, save blob); the design must define which wins and make delivery idempotent, or a save conflict duplicates or erases paid items (Cloud save R17).
> - economy-designer: Premium must not include Kính/Nhãn (§11.5), free lenses must not make paid lenses pointless, and Nhãn's price must be anchored to lens demand. F2/F3 show that with 1 free lens a week the free supply may cover most of a deep player's lens use — flagged, not settled (OQ-3).
> - gameplay-programmer: nothing here may run inside a tick; the only path into the sim is a host command (Command layer R8), and grant commands must be replay-safe.
> - engine-programmer: Godot has no built-in store billing; Android Google Play Billing goes through an Android plugin whose current API is not covered by `docs/engine-reference/godot/` → **NOT SOURCEABLE**, verify in the P1 spike (§12.1).

### Core Rules

**R1 — Outside the simulation.** IAP is a host-level service. It holds no simulation state, registers no tick phase, emits no Event-bus events (the bus carries sim events only), and is never called from inside a tick. Its outputs are host signals (`purchase_state_changed`, `ledger_changed`, `restore_finished`) and, for lens delivery only, host-origin commands (R8). It may use engine time and engine randomness (the determinism rules bind only the simulation).

**R2 — The catalog.** Five store products. Prices are the store's; the reference prices below are design proposals used for balance (F1, F2) and must be confirmed by the user (GDD §11.5 "chờ bạn chốt số lượng", OQ-1).

| `product_id` | Store type | Grants | Reference price (USD, approved by the user 2026-11-16) | Restorable from store |
|---|---|---|---|---|
| `premium_unlock` | non-consumable | Ownership record `premium` → Entitlement `is_premium` | 4.99 | Yes |
| `pa_eye` | non-consumable | Ownership record `pa_eye` → Entitlement `exact_pa_all` | 9.99 floor (F2) | Yes |
| `pa_lens_1` | consumable | 1 × `item_pa_lens` | 0.99 | No — ledger only (R5) |
| `pa_lens_5` | consumable | 5 × `item_pa_lens` | 3.99 | No — ledger only |
| `pa_lens_15` | consumable | 15 × `item_pa_lens` | 9.99 | No — ledger only |

Catalog rules: (a) Premium never contains Kính or Nhãn, and neither lens product nor Nhãn contains any Premium feature (§11.5 "hai thứ độc lập"). (b) No product is randomized (no loot box, no gacha). (c) No product sells gold, Linh Bảo, XP, items other than `item_pa_lens`, or any value that changes a simulation outcome (§11.2). (d) The catalog is data: product ids, store type, granted item and quantity, and reference price live in a data file (proposed `data/iap_products.csv`, OQ-2), not in code. (e) The Steam build has no `premium_unlock` (Premium is the paid app itself, §11.1, Entitlement's derivation) and sells `pa_eye` as DLC and lenses as Steam in-game purchases — **PROVISIONAL**, post Wave 1 (OQ-6).

**R3 — Who can buy.** The *Buy* buttons are enabled only when (a) the store connection is ready and reports the product, and (b) the account state is `Guest` or `Linked` (Account and cloud save R3). In `NoAccount` or `SessionLost` they show "Connect to sign in before buying" because a receipt cannot be bound to an account. A `Guest` buyer is shown once, after the first successful purchase, "Link Google to keep your purchases if you change phones" (Cloud save R13: an unlinked guest account cannot be recovered). Buying `pa_eye` or `premium_unlock` that the ledger already shows as owned is not offered (the button reads "Owned").

**R4 — The purchase flow.** 1. Player taps *Buy* on a product; the game shows one confirmation with the store's localized price string and what the product does and does not do ("Reveals one member's exact PA. Does not make anyone stronger."). 2. The store's own purchase sheet opens; the game waits and does not pause the simulation. 3. On a store result of *purchased*, the client records a **local pending receipt** (purchase token, product id, `account_id`, `guild_uid` from the current save header) in a small file beside the save — not inside it — so a crash cannot lose it. 4. The client calls the backend function `verify_purchase` (R5). 5. On a verified answer it **finalizes** the purchase with the store (consumables are consumed, non-consumables acknowledged) and runs a delivery reconcile (R8). 6. The pending receipt is removed only after step 5's store call succeeds.

**R5 — The server ledger is the source of truth.** `verify_purchase(account_id, store, purchase_token, product_id, guild_uid)` checks the receipt with the store's server API (Google Play Developer API on Android; App Store Server API on iOS later; Steam Web API on PC later), and is **idempotent by `(store, purchase_token)`**: the same token always returns the same result and never creates a second row. On success it writes:
- for a **non-consumable**: one **ownership record** `{account_id, product_id, store, purchase_token, state = active}`;
- for a **consumable**: one **grant** `{grant_ref, account_id, product_id, item = item_pa_lens, qty, state = verified, bound_guild_uid = null, store, purchase_token}`, where `grant_ref` is a server-assigned positive 62-bit integer, unique forever.
Row-level security lets an account read only its own rows; only the backend functions write them. The client never creates, edits or deletes ledger rows. This satisfies Cloud save R17: paid lens balances do not live only in the save blob.

**R6 — Verify before deliver, for consumables.** A consumable is never delivered before `verify_purchase` succeeds, because a delivered lens can be spent offline at once and cannot be clawed back (R11). While verification cannot complete (network down, backend error), the purchase stays *Purchased — delivering* in the shop and retries with the Account and cloud save F2 back-off (`retry_delay_s`), not a new schedule. Non-consumables are also verified server-side before the ownership record exists; whether Entitlement may grant a **provisional** local unlock from the store's own client-side purchase state while verification is pending is Entitlement's (32) decision (PROVISIONAL, OQ-5).

**R7 — Finalize within the store window.** Stores refund purchases that are not finalized in time (Google Play: unacknowledged purchases are refunded after a window — **NOT SOURCEABLE** here; the proposed knob `store_finalize_deadline_h` = 72 must be checked against current Google documentation in the P1 spike). IAP finalizes immediately after verification succeeds, which is safe because the ledger row already exists (R5) — delivery into the save does not have to happen first. On every launch and resume, IAP queries the store for unfinalized purchases and re-runs R4 steps 4–6 for each, so a purchase interrupted by a crash, a kill or a dead battery completes on the next launch.

**R8 — Lens delivery: claim, then one idempotent host command per grant.** Delivery reconciles the ledger with the save; it runs after every successful verification, after the save finishes loading (cold start and after a Cloud save adopt, Cloud save R8), and after sign-in.
1. The client calls `claim_grants(account_id, guild_uid)`. The backend binds every grant of this account with `bound_guild_uid = null` and `state = verified` to this `guild_uid`, then returns every grant bound to this `guild_uid` with its state (`verified` or `revoked`).
2. For each returned grant in `grant_ref` order that is `verified` and **not** in the save's `store_grants_applied` set (F4), the client submits `grant_store_item(item_pa_lens, qty, grant_ref)` through the host path (Command layer R8).
3. In P1, the handler refuses with `101 grant_already_applied` if `grant_ref` is already in `store_grants_applied`, and with `102 item_not_grantable` if the item is not marked store-grantable in the catalog (only `item_pa_lens`). Otherwise it calls Items and loot `give({item_pa_lens: qty})` (always succeeds, storage is uncapped) and adds `grant_ref` to `store_grants_applied`, in that order inside one apply. A `101` refusal is treated by the client as success.
4. `store_grants_applied` is simulation state (a set of int64, saved with the guild; size = number of lens purchases ever delivered to this guild). It is the only simulation state this system defines; its owner-side handler lives in the sim and is registered at boot by this system (Command layer R2).

Consequences: **no erase** — a save from before a delivery (an older cloud copy, a restored backup) lacks the `grant_ref`, so the next reconcile delivers it again; **no duplicate** — a save that already has the `grant_ref` refuses it; **no transfer to another guild** — a grant bound to guild A is never delivered to guild B on the same account (a player who starts a new guild does not get their old guild's lenses again); lenses spent in a save that the player then discards in a conflict come back unspent with the older save, together with the loss of that save's reveal, so no paid value is gained or lost. *(Lens disagreement, resolved by recommended option: systems-designer proposed a pure server-side wallet decremented online at use time. gameplay-programmer objected that `use_pa_lens` is a sim command that must work offline and replay deterministically, and CA/PA R10 already consumes the lens from guild storage. The design keeps storage as the spend point and makes the server ledger authoritative for what was delivered.)*

**R9 — Free lenses are not IAP's, but IAP must not break them.** Free Thiên Cơ Kính come from the weekly quest (`data/quests.csv` `q_w_all_done` → `item_pa_lens:1`, `pa_lens_weekly_free` = 1) and milestone rewards, owned by Quests and achievements (25). They enter storage as ordinary sim rewards, never through the ledger. `pa_lens_stock_cap` = 5 (§11.5 "tồn kho tối đa 5") limits **free** grants only: this design assumes a free grant is skipped while storage holds ≥ 5 lenses, and **paid deliveries ignore the cap** (a player must always receive what they paid for). PROVISIONAL for Quests (25), OQ-4. Rewarded-ad quest variants never grant `item_pa_lens` or `item_pa_eye` (§11.5); this is a content-validator rule (AC-14).

**R10 — Restore purchases.** Settings and the shop both have *Restore purchases*. It queries the store for the store account's owned non-consumables, runs `verify_purchase` for each (idempotent, R5), and the backend **re-binds** each ownership record to the calling `account_id` if it belonged to another account (last restore wins, logged server-side). Consumables are not restorable from any store; unspent paid lenses come back only through the ledger (R8), which follows the `account_id` (linked sign-in on a new device, Cloud save R3). Restore never creates a grant. iOS requires a visible restore control (verify current App Store guideline wording before submission, OQ-7).

**R11 — Refunds and revocation.** The backend learns of refunds and chargebacks from the store's server notifications (Google real-time developer notifications / voided purchases; Apple server notifications later) and marks the matching row `revoked`. The client learns at its next `claim_grants` or entitlement refresh.
- **Non-consumable revoked** (`premium_unlock`, `pa_eye`): the ownership record becomes `revoked`; Entitlement (32) derives the loss of `is_premium` / `exact_pa_all`. CA/PA already defines the display fallback (CA/PA edge cases: "If Thiên Nhãn is refunded").
- **Consumable revoked before delivery**: never delivered.
- **Consumable revoked after delivery**: the client submits `revoke_store_item(item_pa_lens, qty, grant_ref)` once. The handler (P1) takes `min(qty, count(item_pa_lens))` from storage via Items `take`, records `grant_ref` in `store_grants_revoked`, and refuses with `103 revoke_already_applied` if already recorded. Lenses already spent stay spent and their reveals stay (CA/PA R10: `pa_exact` is permanent); storage never goes negative. Repeated refund-after-spend is a store-policy and analytics matter, not a gameplay penalty.

**R12 — Prices, text and legality.** Prices are always the store's localized price strings, never a number from the catalog (the reference price is for balance math only). All shop text goes through Localization. The shop states, per product, what it does not do. No countdown timers, no "limited offer" pressure, no purchase prompt during the Golden Boss or the conflict screen. Age-rating and store-listing declarations (in-app purchases present, no randomized items) are Release's checklist, not runtime rules.

**R13 — Signals for other services.** IAP emits host signals only: `purchase_state_changed(product_id, state)`, `ledger_changed(account_id)` (Entitlement refreshes on it), `restore_finished(count)`, `delivery_done(grant_ref)`. Analytics (37) may subscribe; nothing reaches the sim Event bus.

### States and Transitions

One state machine per purchase transaction (keyed by purchase token once the store returns one).

| State | Meaning | → To | Trigger |
|---|---|---|---|
| `Confirming` | Game confirmation shown (R4.1) | `StoreSheet` | Player confirms |
| | | (none) | Player cancels — nothing recorded |
| `StoreSheet` | Store purchase UI open | `Purchased` | Store returns *purchased* |
| | | `StorePending` | Store returns *pending* (deferred payment, parental approval) |
| | | (none) | Store returns *cancelled* or *error* — nothing recorded |
| `StorePending` | Store will confirm later | `Purchased` | Store update: purchased (seen live or at the next launch query, R7) |
| | | (none) | Store update: declined/expired |
| `Purchased` | Local pending receipt written (R4.3), not yet verified | `Verifying` | Account is `Guest`/`Linked` and network is up |
| `Verifying` | `verify_purchase` in flight | `Verified` | Valid receipt; ledger row exists |
| | | `Rejected` | Store says the token is invalid or not for this app |
| | | `Backoff` | Network or server error |
| `Backoff` | Waiting Cloud save F2 delay | `Verifying` | Delay elapsed, app resume, or *Restore purchases* |
| `Verified` | Ledger row written | `Finalized` | Store consume/acknowledge succeeds (R7) |
| | | `Verified` | Store call failed — retried at next launch/resume |
| `Finalized` | Store is done; pending receipt removed | `Delivered` | Consumable: grant applied in the save (R8) — non-consumable goes here directly |
| `Delivered` | Effect is live (ownership record active, or `grant_ref` in `store_grants_applied`) | `Revoked` | Refund/chargeback notification (R11) |
| `Rejected` | Not a real purchase; pending receipt removed and logged | — | terminal |
| `Revoked` | Refunded; R11 applied | — | terminal |

The grant itself has a server-side life: `verified` (bound or unbound) → `revoked`. Binding (`bound_guild_uid` null → set) happens once at the first `claim_grants` and never changes.

### Interactions with Other Systems

| System | Direction | Data / call | Owner of the interface |
|---|---|---|---|
| Account and cloud save (7) | Upstream, hard | Reads `account_id`, session token, `account_state_changed`; reads `guild_uid` from the save header (Cloud save R5 `summary`); uses its F2 `retry_delay_s` for back-off; is told after every adopt (Cloud save R8) so R8 reconcile runs. Implements Cloud save R17 (consumable balances server-side). | Account and cloud save for identity and adopt signal; this system for the ledger. |
| Entitlement and feature flags (32) | Downstream, hard | Reads the account's ownership records (`premium`, `pa_eye`, state) and refreshes on `ledger_changed`; derives `is_premium` and `exact_pa_all` and injects the snapshot into the sim. | Entitlement. **PROVISIONAL** — GDD not written. |
| Command layer (5) | Upstream, hard | Registers two host-only command types in block 3400: `grant_store_item` (3401) and `revoke_store_item` (3402), args `content(items)`, `int(1, 999)`, `int(1, 2^62−1)`; reason codes 101–103. Replay (Leaderboards 35, parity harness) re-submits them like any host command. | Command layer owns the envelope; this system owns the two types. **PROVISIONAL** ids. |
| Items and loot (26) | Upstream, hard | Handlers call `give({item_pa_lens: qty})` and `take({item_pa_lens: n})` (Items and loot R7 storage API: `count`, `give`, `take`). | Items and loot. |
| CA/PA and traits (9) | Downstream, soft | Consumes delivered lenses through `use_pa_lens` (CA/PA R10); reads `exact_pa_all` from Entitlement's snapshot, not from IAP. | CA/PA. |
| Local save and migration (6) | Upstream, hard | Saves `store_grants_applied` and `store_grants_revoked` with the guild (sim state). Pending receipts live in a separate small file beside the save, written atomically. | Local save owns the format. **PROVISIONAL** — new save fields. |
| Quests and achievements (25) | Sideways, soft | Free lenses (R9); the stock cap applies to free grants only; ad-variant rewards never include lens/eye. | Quests. **PROVISIONAL** — GDD not written. |
| Ads (33) | Sideways, soft (via Entitlement) | Reads `is_premium` from Entitlement, never from IAP. | Ads. |
| Settings (45) | Downstream, hard | Hosts *Restore purchases* and the purchase history list. | Settings owns the screen; this system owns the action. |
| Guild screens (39) | Downstream, hard | Shop panel and the lens counter link to it; the member card's *Use Thiên Cơ Kính* button shows a *Buy* link when the count is 0. | Guild screens own layout; this system owns shop behaviour. |
| Localization (4) | Upstream, hard | All shop strings and product descriptions. Prices come from the store, not from string tables. | Localization. |
| Analytics (37) | Downstream, soft | Subscribes to R13 host signals. | Analytics. |
| Leaderboards and anti-cheat (35) | Downstream, soft | Sees grant/revoke commands in the command log; they change only lens counts and cannot affect any ranked value (CA/PA AC-24). | Leaderboards. |

## Formulas

All prices are reference values in USD used only for balance reasoning; the store sets real, localized prices (R12). None of these formulas runs inside the simulation except F4, whose membership test is the R8 handler.

### F1 — `pack_price`

The pack_price formula is defined as:

`pack_price(n) = tier_round( p_lens × n × (1 − d(n)) )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| n | int | 1, 5, 15 | data file (`iap_products.csv`, proposed) | Lenses in the pack |
| p_lens | float USD | 0.49 – 1.99 (0.99) | data file | Reference price of one lens |
| d(n) | float | 0 – 0.5 (d(1)=0, d(5)=0.20, d(15)=0.33) | data file | Bulk discount for pack size n |
| tier_round | function | — | constant | Round to the nearest store price tier ending in .99 at or above the result's dollar (store convention) |

**Output Range:** 0.49 to ~15 under the safe ranges. d(n) ≥ 1 would give price ≤ 0, so d is capped at 0.5. Each larger pack must have a lower unit price: require `pack_price(n_k)/n_k < pack_price(n_{k−1})/n_{k−1}` (validator check, AC-12).
**Example:** p_lens = 0.99, n = 5, d = 0.20 → 0.99 × 5 × 0.80 = 3.96 → 3.99 (unit 0.80). n = 15, d = 0.33 → 9.95 → 9.99 (unit 0.67).

### F2 — `eye_price_target`

The eye_price_target formula is defined as:

`eye_price_target = tier_round( max( p_eye_floor, u_best × L_paid × (1 − d_eye) ) )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| p_eye_floor | float USD | p_premium – 3 × p_premium (9.99) | data file | Floor: Nhãn is "cao, mua một lần" (§11.5) and also reveals candidates, which lenses cannot (CA/PA R10) |
| u_best | float USD | — | calculated | Lowest per-lens price in the catalog (F1: 0.67) |
| L_paid | float | 0 – 500 | calculated (F3) | Lenses a deep player would buy over the planning horizon |
| d_eye | float | 0 – 0.5 (0.25) | data file | Discount for buying the "lifetime" bundle up front |
| p_premium | float USD | (4.99) | data file | Premium reference price, for the floor range only |

**Output Range:** p_eye_floor to ~250. L_paid = 0 → the floor. Unbounded L_paid is capped by its range.
**Example:** L_paid = 6 (F3 example) → 0.67 × 6 × 0.75 = 3.0 → max(9.99, 3.0) = 9.99. L_paid = 40 → 20.1 → 20.99. *With the F3 example the floor binds: Nhãn's price is set by its candidate-reveal value, not by lens equivalence. This is a balance finding, see OQ-3.*

### F3 — `L_paid` (lens demand net of free supply)

The L_paid formula is defined as:

`L_paid = max( 0, H × r_inspect − ( W × pa_lens_weekly_free + M ) )`

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| H | int | 0 – 2,000 | calculated (balance simulator, `sim/`) | Members accepted into the guild over the horizon |
| r_inspect | float | 0 – 1 (0.4, assumption) | data file (balance assumption) | Share of accepted members a deep player wants exact PA on |
| W | int | 0 – 260 | constant (horizon in weeks, 26 for the example) | Planning horizon |
| pa_lens_weekly_free | int | 0 – 3 (1) | data file (`config.csv`) | Free lenses per week (§11.5) |
| M | int | 0 – 50 (4, assumption) | calculated (Quests 25 milestone rewards) | One-off free lenses from milestones over the horizon |

**Output Range:** 0 to ~800. The free term is an upper bound: `pa_lens_stock_cap` only reduces real free supply when a player hoards (R9), which raises L_paid slightly.
**Example:** H = 90 over 26 weeks, r_inspect = 0.4 → 36 wanted; free = 26 + 4 = 30 → L_paid = 6. *H, r_inspect and M are placeholders until the balance simulator reports accepted-member counts per horizon (§11.5 "tính bằng simulator").*

### F4 — `grants_to_deliver` (reconcile)

The grants_to_deliver formula is defined as:

`grants_to_deliver = { g ∈ claim_grants(account_id, guild_uid) | g.state = verified ∧ g.grant_ref ∉ save.store_grants_applied }`, ordered by `grant_ref`; and `grants_to_revoke = { g | g.state = revoked ∧ g.grant_ref ∈ store_grants_applied ∧ g.grant_ref ∉ store_grants_revoked }`.

**Variables:**
| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| claim_grants(...) | set of grants | 0 – N_purchases | calculated (backend, R8.1) | Grants bound to this guild after binding unbound ones |
| store_grants_applied | set of int64 | 0 – N_purchases | calculated (sim state) | grant_refs already delivered into this save |
| store_grants_revoked | set of int64 | ⊆ applied | calculated (sim state) | grant_refs already revoked in this save |

**Output Range:** the empty set when the save is in sync with the ledger. Lenses delivered by one reconcile = Σ g.qty over `grants_to_deliver`, between 0 and 15 × N_purchases.
**Example:** ledger has grants 41 (qty 5) and 57 (qty 1) bound to this guild; the adopted cloud save has {41} → deliver 57 only (+1 lens). An older backup with {} → deliver 41 and 57 (+6).

## Edge Cases

*`systems-designer` lens applied to Sections C and D (no agent spawned).*

- **If the app is killed after the store charges but before `verify_purchase` returns**: the pending receipt file (R4.3) and the store's unfinalized-purchase list both survive; the next launch re-runs verification (R7). The token is idempotent (R5), so a verification that did reach the server is not doubled.
- **If verification succeeds but the client dies before finalizing**: the ledger row exists; the next launch finds the purchase still unfinalized in the store, calls `verify_purchase` again (same row returned) and finalizes. Delivery comes from the ledger regardless.
- **If the network stays down past `store_finalize_deadline_h`**: the store refunds automatically; if the ledger row was never written, nothing was delivered and nothing is lost. If it was written (verified, then finalization failed for days), the store's refund notification revokes it (R11). The shop shows "Purchase could not be completed — refunded by the store" when the client next sees the store state.
- **If the same purchase token is submitted from two devices**: one ledger row (R5 idempotency); the second call returns the existing row; a consumable grant is bound to the first guild to claim it.
- **If the player buys lenses on a guest account and signs out before linking**: grants already delivered stay in the local save; undelivered grants stay on the orphaned guest account and are lost. The R3 link prompt and the Cloud save R13 sign-out warning both say so. Non-consumables return through *Restore purchases* (store account, not game account).
- **If a cloud-save conflict picks a save that lacks a delivered grant**: R8 re-delivers it after the adopt reload. If the picked save has spent lenses that the discarded save had not, nothing is added: the ledger grant is already in `store_grants_applied`.
- **If the player starts a new guild on the same account**: new `guild_uid`; grants bound to the old guild are not delivered (R8); unbound grants (bought but never claimed) go to whichever guild claims first.
- **If two different guilds are opened alternately on the same account** (Cloud save R7 case 5, "two different guilds"): each sees only its own bound grants.
- **If a lens refund arrives after the lens was spent**: `revoke_store_item` takes `min(qty, count)`; storage stays ≥ 0; the reveal stays (R11). If storage holds lenses from a free source, they may be taken — the item is fungible. Accepted: the player was refunded money for that many lenses.
- **If `revoke_store_item` and a `use_pa_lens` are submitted in the same tick**: both are P1 commands applied in `seq` order (Command layer); whichever is first sees the count; the other works on what remains. Deterministic under replay.
- **If a grant arrives while Thiên Nhãn is owned**: delivered as normal; lenses still make a reveal permanent past a Nhãn refund (CA/PA edge case "lens used while Thiên Nhãn is active").
- **If a Premium or Nhãn purchase is restored to account B while account A still uses it on another device**: last restore wins (R10); A loses the record at its next entitlement refresh. A store account shared across many game accounts can only hold the unlock on one at a time.
- **If the store reports a product that is not in the catalog, or the catalog lists a product the store does not return**: the unknown product is ignored and logged; the missing product's button is hidden. No crash, no purchase of an unknown id.
- **If `grant_store_item` names any item other than `item_pa_lens`**: refused with `102` (R8.3). A tampered client cannot use the grant command to mint gold or gear; and it is a host command in the log, so a leaderboard replay sees it (Leaderboards 35 may reject runs whose `grant_ref`s the server never issued — PROVISIONAL, OQ-8).
- **If a forged `grant_store_item` with an unissued `grant_ref` is submitted on a modified client**: the local save gains lenses that only reveal PA (no power, CA/PA AC-24). Not defended locally; offline single-player tampering is out of scope beyond OQ-8.
- **If the store returns *pending* and the player closes the app for a week**: the next launch query (R7) picks up the final state; nothing is delivered until *purchased* and verified.
- **If the player has 5 or more lenses in storage and buys a pack**: delivered in full; paid deliveries ignore `pa_lens_stock_cap` (R9). The next free weekly lens is skipped while ≥ 5 (Quests' rule, PROVISIONAL).
- **If the save's `store_grants_applied` grows very large**: bounded by the number of lens purchases ever made for that guild (tens to a few hundred); no pruning, since pruning would break no-duplicate.

## Dependencies

| System | Kind | Interface |
|---|---|---|
| Account and cloud save (7) | **Hard, upstream** | `account_id`, session token, account state, `guild_uid` from the save header, adopt-finished signal, F2 back-off. This system fulfils Cloud save R17 / OQ-9. |
| Command layer (5) | **Hard, upstream** | Registration and host submit path for `grant_store_item` (3401) and `revoke_store_item` (3402); replay re-submits them. |
| Items and loot (26) | **Hard, upstream** | Storage `give` / `take` / `count` for `item_pa_lens`. |
| Local save and migration (6) | **Hard, upstream** | Persists `store_grants_applied` / `store_grants_revoked` (sim state) and the pending-receipt side file. |
| Data layer (3) | **Hard, upstream** | Loads the product catalog (proposed `iap_products.csv`) and `config.csv` keys. |
| Localization (4) | **Hard, upstream** | Shop strings. |
| Entitlement and feature flags (32) | **Hard, downstream** | Reads ownership records; derives `is_premium`, `exact_pa_all`. |
| CA/PA and traits (9) | Soft, downstream | Spends delivered lenses; never reads IAP. |
| Quests and achievements (25) | Soft, sideways | Free lens supply; cap semantics (R9). |
| Settings (45), Guild screens (39) | Hard, downstream (UI) | Restore button, shop panel, buy link from the lens counter. |
| Analytics (37), Leaderboards (35), Ads (33) | Soft, downstream | Host signals; command log; Premium via Entitlement only. |

Bidirectional check: the systems index lists 34 → Account and cloud save only; Command layer, Items and loot, Local save, Data layer and Localization are added here because the delivery path (R8) needs them — the systems index row's Depends On is updated accordingly. Account and cloud save already lists IAP as a hard downstream dependent. CA/PA and Items list IAP as the seller of `item_pa_lens` / `item_pa_eye`. Entitlement, Quests, Settings, Guild screens, Local save and Command layer must add IAP when their GDDs are written or revised (Open Questions).

## Tuning Knobs

| Knob | Default | Safe range | Too high | Too low | Owner / where |
|---|---|---|---|---|---|
| `p_lens` | 0.99 | 0.49 – 1.99 | Lenses feel greedy; players wait for free ones | Undercuts Nhãn and packs | `iap_products.csv` (proposed) |
| `d(5)`, `d(15)` | 0.20, 0.33 | 0 – 0.5, strictly increasing with n | Single lens looks like a trap | Packs pointless | `iap_products.csv` |
| `p_eye_floor` | 9.99 | p_premium – 3 × p_premium | Nobody buys Nhãn; lenses dominate | Nhãn cannibalizes all lens revenue | `iap_products.csv`; interacts with F3 (when L_paid is small the floor alone sets the price) |
| `d_eye` | 0.25 | 0 – 0.5 | Only matters when F2's floor does not bind | — | `iap_products.csv` |
| `p_premium` | 4.99 | 2.99 – 9.99 | Conversion drops | Revenue too low for solo dev | store console; reference in catalog |
| `pa_lens_weekly_free` | 1 | 0 – 3 | Paid lenses pointless (F3 → 0) | Free players never see the reveal | `config.csv`, **owned by Quests (25)**; pointed to, not duplicated |
| `pa_lens_stock_cap` | 5 | 1 – 20 | Hoarding | Paying players lose free lenses (R9) | `config.csv`, **owned by Quests (25)** |
| `store_finalize_deadline_h` | 72 | must be < the store's real window | Purchases auto-refunded | — | proposed `config.csv` key; **verify against store docs (NOT SOURCEABLE)** |
| Back-off schedule | Cloud save F2 | — | — | — | **owned by Account and cloud save**; pointed to |

`r_inspect`, `H` and `M` (F3) are balance-simulator assumptions, not runtime knobs.

## Visual/Audio Requirements

Optional for the Meta category; brief by design. No art bible exists yet, so this is drafted from GDD §11 and CA/PA's visual notes. `art-director` lens applied in this run; no agent spawned.

- Product icons: Premium (guild banner with a gold seal), Thiên Nhãn (an open eye in a bronze mirror frame), Thiên Cơ Kính packs (one, a stack of three, a lacquered box), consistent with CA/PA's "seal" glyph motif for exact PA.
- Purchase success: a short, quiet chime and the product icon settling into the shop slot; lens delivery animates the storage lens counter +n. No fireworks, no loot-box reveal (R2b).
- Pending/delivering: a small spinner with text, never a modal.
- Refund/revocation: a neutral notice, no sound.

📌 **Asset Spec** — Visual/Audio requirements are defined. After the art bible is approved, run `/asset-spec system:in-app-purchases` to produce per-asset visual descriptions, dimensions, and generation prompts from this section.

## Game Feel

Optional for Meta. Targets: the shop opens in under 300 ms from cached catalog data (store prices refresh in the background); the store sheet appears within one frame of confirmation; after a successful store result the "delivering…" note shows within 100 ms and, on a normal connection, the lens counter updates within 3 s. Buying must never stall the simulation or the realtime world view.

## UI Requirements

- **Shop panel** (reached from Guild screens and Settings): three sections — Premium (what it includes, per §11.2 list, and "does not include exact PA"), Thiên Nhãn, Thiên Cơ Kính packs with per-lens price shown. Owned non-consumables show "Owned". Store localized prices only.
- **Confirmation dialog** (R4.1): product, price string, one line of what it does, one line of what it does not do, *Buy* / *Cancel*.
- **Lens counter** on the member card (CA/PA UI): when 0, a *Get Thiên Cơ Kính* link opens the shop at the lens section. When Nhãn is owned, the shop's lens section shows CA/PA's warning ("Thiên Nhãn already shows every PA; a lens only makes one permanent").
- **Restore purchases** button in Settings and at the foot of the shop, with a result toast ("2 purchases restored" / "Nothing to restore").
- **Pending state**: a "Purchase received — delivering when connected" row at the top of the shop while any transaction is in `Purchased`/`Verifying`/`Backoff`.
- **Guest link prompt** after the first purchase (R3), dismissible, shown once.
- **Purchase history** (Settings): product, date, state (delivered / refunded) — supports store support tickets.
- Accessibility: text never relies on colour alone for Owned/Pending; all buttons readable at the game's minimum text scale; room for Vietnamese and English string lengths.

> **📌 UX Flag — In-app purchases**: This system has UI requirements. In Phase 4 (Pre-Production), run `/ux-design` to create a UX spec for each screen or HUD element this system contributes to **before** writing epics. Stories that reference UI should cite `design/ux/[screen].md`, not the GDD directly.

## Cross-References

| This GDD | References | Their section | Relationship |
|---|---|---|---|
| R5, R8, Edge Cases | Account and cloud save | R3, R5 `summary.guild_uid`, R8, R13, R17, F2, OQ-9 | Implements R17; uses identity, adopt signal and back-off |
| R8, R11 | CA/PA and traits | R10 (`use_pa_lens`, `pa_exact` permanent), R12, AC-24, Edge Cases (Nhãn refund, lens while Nhãn), OQ-13 | Delivers the item CA/PA consumes; agrees Nhãn is an Entitlement snapshot, not a storage item |
| R8, R11 | Items and loot tables | R7 storage `give`/`take`/`count`, R9 special items | Uses storage API; Items R9 now agrees `item_pa_eye` is not a storage item (OQ-9 resolved) |
| R8 | Command layer | R2 registration, R8 host submit path, R9 replay, R14 gating | Registers two host commands in block 3400 |
| R9 | `data/quests.csv`, `data/config.csv` | `q_w_all_done`, `pa_lens_weekly_free`, `pa_lens_stock_cap` | Free lens supply and cap semantics |
| R2, F1–F3 | JX1_Tycoon_GDD.md | §2, §11.1–§11.5, §12.1 | Source of the product split, free-lens rule, Steam, spike |

## Acceptance Criteria

Story types: **[Logic]** automated unit test; **[Integration]** automated test against a fake store and fake backend; **[UI]** retained screenshot in `production/qa/evidence/`; **[Device]** manual check on a real Android device in the P1 spike / pre-launch.

- **AC-1 [Logic] (R5 idempotency)**: **GIVEN** a fake backend and a valid consumable token for `pa_lens_5`, **WHEN** `verify_purchase` is called 3 times with the same token, **THEN** exactly one grant row exists with qty 5 and all three calls return the same `grant_ref`.
- **AC-2 [Logic] (R8 delivery)**: **GIVEN** a save whose storage holds 2 `item_pa_lens` and an empty `store_grants_applied`, and a ledger with grant 41 (qty 5) bound to this guild, **WHEN** reconcile runs, **THEN** storage holds 7 and `store_grants_applied = {41}`.
- **AC-3 [Logic] (R8 no duplicate)**: **GIVEN** the end state of AC-2, **WHEN** reconcile runs again and `grant_store_item(item_pa_lens, 5, 41)` is also submitted by hand, **THEN** the command is refused with 101, storage still holds 7.
- **AC-4 [Integration] (R8 no erase, F4)**: **GIVEN** save S1 with `store_grants_applied = {}` and save S2 with `{41}`, ledger grants 41 (qty 5) and 57 (qty 1), **WHEN** S1 is adopted through the Cloud save adopt path and reconcile runs, **THEN** 6 lenses are added and the set becomes {41, 57}; **WHEN** instead S2 is loaded, **THEN** 1 lens is added.
- **AC-5 [Logic] (R8 guild binding)**: **GIVEN** grant 41 bound to guild A, **WHEN** a save of guild B on the same account reconciles, **THEN** grant 41 is not returned and no lens is added.
- **AC-6 [Logic] (R8.3 item guard)**: **GIVEN** any save, **WHEN** `grant_store_item(item_pa_eye, 1, 99)` (or any item other than `item_pa_lens`) is submitted, **THEN** it is refused with 102 and no state changes.
- **AC-7 [Integration] (R6 verify before deliver)**: **GIVEN** a fake store that returns *purchased* and a backend that is unreachable, **WHEN** 10 minutes of back-off pass, **THEN** storage lens count is unchanged, the shop shows the pending row, and on backend recovery the lens arrives within one retry.
- **AC-8 [Integration] (R7 crash recovery)**: **GIVEN** a purchase verified on the server but not finalized (client killed), **WHEN** the app relaunches, **THEN** the purchase is finalized with the fake store, no second grant row exists, and the lens is delivered once.
- **AC-9 [Logic] (R11 revoke after spend)**: **GIVEN** grant 41 (qty 5) applied and 4 of those lenses spent (storage = 1), **WHEN** grant 41 is revoked and reconcile runs, **THEN** storage = 0, `store_grants_revoked = {41}`, the 4 `pa_exact` flags are still true; a second reconcile refuses with 103 and changes nothing.
- **AC-10 [Integration] (R11 non-consumable)**: **GIVEN** an active `pa_eye` ownership record and Entitlement's `exact_pa_all = true`, **WHEN** the fake store sends a refund notification, **THEN** the record becomes `revoked` and at the next refresh Entitlement reports `exact_pa_all = false`.
- **AC-11 [Integration] (R10 restore)**: **GIVEN** a fresh install signed in to a new account and a fake store account owning `premium_unlock`, **WHEN** the player taps *Restore purchases*, **THEN** the ownership record is bound to the new account, no grant is created, and the toast reads "1 purchase restored".
- **AC-12 [Logic] (F1 pack ordering)**: **GIVEN** the product catalog data, **WHEN** the content validator runs, **THEN** it fails if any larger lens pack has a per-lens price ≥ a smaller pack's, or if any `d(n)` ≥ 0.5, and passes for the defaults (0.99 / 0.80 / 0.67 per lens).
- **AC-13 [Logic] (F2, F3 boundaries)**: **GIVEN** the balance script, **WHEN** L_paid = 0, **THEN** `eye_price_target = p_eye_floor`; **WHEN** H × r_inspect < free supply, **THEN** L_paid = 0 (never negative); **WHEN** the F3 example inputs are used, **THEN** L_paid = 6 and the target is 9.99.
- **AC-14 [Logic] (R9, §11.5)**: **GIVEN** `data/quests.csv`, **WHEN** the content validator runs, **THEN** it fails if any row with `ad_variant = true` has `item_pa_lens` or `item_pa_eye` in `reward_items`.
- **AC-15 [Logic] (R2 catalog)**: **GIVEN** the catalog, **WHEN** validated, **THEN** `premium_unlock` grants no item, no consumable grants anything but `item_pa_lens`, and no product is marked random.
- **AC-16 [Integration] (no power sold, CA/PA AC-24)**: **GIVEN** two identical saves, one receiving three lens grants via `grant_store_item`, **WHEN** both run 100,000 ticks with the same other commands, **THEN** all simulation state other than lens counts and `store_grants_applied` is identical.
- **AC-17 [Integration] (R1 boundary)**: **GIVEN** the sim core under the parity harness, **WHEN** a full purchase flow runs, **THEN** the only commands in the log from IAP are `grant_store_item`/`revoke_store_item`, and no sim Event-bus event is emitted by IAP.
- **AC-18 [Logic] (R3 gating)**: **GIVEN** account state `NoAccount`, **WHEN** the shop opens, **THEN** every *Buy* button is disabled with the sign-in message; **GIVEN** `pa_eye` owned, **THEN** its button reads "Owned".
- **AC-19 [UI] (UI Requirements)**: Screenshots of the shop (Free player, Premium owned, Nhãn owned), the confirmation dialog, the pending row and the restore toast, in Vietnamese and English, retained in `production/qa/evidence/`.
- **AC-20 [Device] (P1 spike, §12.1)**: **GIVEN** a Play Console internal-test track and a real Android device, **WHEN** a license tester buys `pa_lens_1` and `premium_unlock`, **THEN** both verify through the Edge Function, the lens is delivered, Premium is restored after reinstall, and a test refund revokes it. Records the plugin and API versions used (closes the NOT SOURCEABLE items).

*`qa-lead` lens applied: every core rule R3–R11 and F1–F4 has a criterion; R12 (no pressure prompts) and R13 (signals) are checked by review rather than test — flagged here rather than dropped. Game Feel timings are playtest checks, not automated.*

## Open Questions

| ID | Question | Owner | Target |
|---|---|---|---|
| OQ-1 | **RESOLVED (user decision 2026-11-16):** reference prices approved — Premium 4.99 USD; Thiên Cơ Kính packs 1 / 5 / 15 at 0.99 / 3.99 / 9.99; Thiên Nhãn floor 9.99 (F2 may raise it above the floor, OQ-3). The store still sets localized prices (R12); this approval also closes GDD §11.5's pending quantities. Linh Bảo stays off the catalog (rule c; not sold for real money, user decision 2026-11-16) | User | Closed |
| OQ-2 | Schema change, not made here: add `data/iap_products.csv` (`product_id, store_type, item, qty, ref_price_usd, discount, platforms`) and the `config.csv` key `store_finalize_deadline_h`. | Data layer (3) / User | Alpha |
| OQ-3 | Balance: with 1 free lens/week, F3's example gives L_paid ≈ 6 over 26 weeks — free supply may make paid lenses nearly pointless and Nhãn's price rests on its floor. Run the balance simulator for accepted members per horizon (H) and decide whether to lower the free rate, raise the cap effect, or accept lenses as a minor product. | economy-designer / User | Before Alpha pricing |
| OQ-4 | **PROVISIONAL: Quests and achievements (25)** — assumes `pa_lens_stock_cap` blocks free grants only while storage ≥ cap, and paid deliveries ignore it. Paying players with ≥ 5 stored lenses therefore lose free lenses; Quests may prefer counting only free-sourced lenses (needs a separate counter). | Quests GDD author | When 25 is designed |
| OQ-5 | **PROVISIONAL: Entitlement and feature flags (32)** — assumes it reads ownership records `{product_id, state}` per `account_id`, refreshes on `ledger_changed`, derives `is_premium` and `exact_pa_all`, and decides whether to grant a provisional local unlock before server verification and how long a cached entitlement survives offline. | Entitlement GDD author | When 32 is designed |
| OQ-6 | **PROVISIONAL: Steam / PC** — Premium is the paid app; Nhãn as DLC; lenses as Steam in-game purchases verified by the backend. Web build monetization is not defined in GDD §11. | User | Post Wave 1 |
| OQ-7 | iOS: StoreKit flow, Ask-to-Buy as `StorePending`, App Store server notifications, restore-button guideline wording, Family Sharing for non-consumables. Not verifiable without Apple Developer membership (§12.1). | User | Before iOS |
| OQ-8 | **PROVISIONAL: Leaderboards and anti-cheat (35)** — may reject a submitted run whose command log contains `grant_ref`s the server never issued to that account. Lenses do not affect ranked values, so this is hygiene, not a requirement. | Leaderboards GDD author | When 35 is designed |
| OQ-9 | Conflict carried from CA/PA OQ-13: Items and loot R9 lists `item_pa_eye` as a guild-held storage item; this GDD (with the systems index TD-SYSTEM-BOUNDARY fix and CA/PA R10) treats Nhãn as an Entitlement snapshot that is never in storage. Items R9 should drop `item_pa_eye` from storage handling; the `items.csv` row stays only as a display/catalog reference. **RESOLVED (consistency-check 2026-11-16):** Items R7/R9 edited accordingly. | Items GDD author / consistency pass | Closed |
| OQ-10 | **RESOLVED (consistency-check 2026-11-16):** command ids 3401/3402 in block 3400 (unique in the registry; Command layer R2 owner allocation; Schools' 2001–2003 are now confirmed the same way); reason codes 101–103 are valid owner codes. | Command layer GDD author | When the vocabulary table is next revised |
| OQ-11 | **PROVISIONAL: Local save (6)** — new sim-state fields `store_grants_applied`, `store_grants_revoked` and the pending-receipt side file written atomically beside the save. | Local save GDD author | When 6 is revised |
| OQ-12 | **NOT SOURCEABLE** — Godot 4.7 Android billing plugin API, Google Play Billing finalize window and RTDN format are not covered by `docs/engine-reference/godot/`. Verify in the P1 spike (AC-20) before an ADR. | User / technical-director | P1 spike |
| OQ-13 | Should *Restore purchases* re-binding (last restore wins) have a cooldown to limit one store account unlocking many game accounts in turn? Current design: no limit, logged. | User | Alpha |

*Post-design note — CD-GDD-ALIGN run in this session against GDD §2/§11 text (no pillars, concept or brief exist): no rule sells power (R2c, AC-16), Premium and exact-PA stay separate (R2a), free lenses are never ad rewards (R9, AC-14). Verdict recorded as NOT ASSESSED because the required pillar input is missing.*
