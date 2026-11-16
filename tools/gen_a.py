#!/usr/bin/env python3
"""Sinh dữ liệu (a): materials, items, recipes, drop_tables, buildings, quests, config + tên vật phẩm.
Chạy: python3 -I tools/gen_a.py   (GHI ĐÈ các file nó sinh ra; nếu bạn chỉnh tay CSV thì đừng chạy lại)."""
import csv, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name, folder="data"):
    with open(os.path.join(ROOT, folder, name), encoding="utf8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, head, rows, folder="data"):
    with open(os.path.join(ROOT, folder, name), "w", encoding="utf8", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    print(f"{folder}/{name}: {len(rows)} dòng")


zones = read("zones.csv")
schools = read("schools.csv")

# ---------- schools: thêm armor_class ----------
ARMOR = {"kim_1": "heavy", "kim_2": "medium", "moc_1": "light", "moc_2": "light", "thuy_1": "light",
         "thuy_2": "light", "hoa_1": "medium", "hoa_2": "medium", "tho_1": "heavy", "tho_2": "medium"}
if "armor_class" not in schools[0]:
    head = list(schools[0].keys()) + ["armor_class"]
    write("schools.csv", head, [list(s.values()) + [ARMOR[s["id"]]] for s in schools])
    schools = read("schools.csv")

TIER_LV = [1] + list(range(10, 201, 10)) + []
TIER_LV = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200]
N_TIER = len(TIER_LV)
RARITIES = [("c", "common", 1.0, 1.0), ("r", "rare", 1.3, 2.5), ("e", "epic", 1.65, 7.0)]
WEAPON_MULT = {"tank": 0.8, "tank_guardian": 0.8, "melee_burst": 1.1, "healer_support": 0.65, "dot_debuff": 0.85,
               "control_caster": 0.9, "buff_mp_support": 0.65, "melee_dps": 1.05, "ranged_dps": 1.05,
               "control_summoner": 0.85}
ARMOR_MULT = {"heavy": 1.4, "medium": 1.0, "light": 0.7}


def zone_for_level(lv):
    for z in sorted(zones, key=lambda r: int(r["order"])):
        if int(z["level_max"]) >= lv:
            return z["id"]
    return zones[-1]["id"]


# ---------- tên ----------
FAMILY_NAME = {
    "heavy_blade_armor": ("Đại Đao", "Great Blade"), "sword": ("Kiếm", "Sword"), "staff": ("Trượng", "Staff"),
    "hidden_weapon_poison": ("Phi Tiêu Độc", "Poison Darts"), "zither_fan": ("Đàn Phiến", "Zither Fan"),
    "thin_blade_whisk": ("Nhuyễn Kiếm", "Thin Blade"), "fist_staff": ("Côn", "Cudgel"),
    "fire_crossbow": ("Liên Nỏ", "Repeating Crossbow"), "shield_spear": ("Thương Khiên", "Spear and Shield"),
    "formation_trap": ("Trận Bàn", "Formation Disc"),
    "heavy": ("Giáp Nặng", "Heavy Armor"), "medium": ("Giáp Vừa", "Medium Armor"), "light": ("Áo Vải", "Light Robe"),
    "ring": ("Nhẫn", "Ring"), "amulet": ("Bùa Hộ Mệnh", "Amulet"),
}
TIER_NAME = [("Tre", "Bamboo"), ("Gỗ", "Wood"), ("Đồng", "Bronze"), ("Đồng Thau", "Brass"), ("Sắt", "Iron"),
             ("Thép", "Steel"), ("Thép Tôi", "Tempered Steel"), ("Thanh Cương", "Blue Steel"),
             ("Hàn Thiết", "Cold Iron"), ("Huyền Thiết", "Dark Iron"), ("Tinh Kim", "Fine Alloy"),
             ("Bạch Kim", "Platinum"), ("Ngọc Thiết", "Jade Steel"), ("Long Cốt", "Dragon Bone"),
             ("Hải Tinh", "Sea Crystal"), ("Hoả Tinh", "Fire Crystal"), ("Thiên Thạch", "Meteorite"),
             ("Cung Đình", "Imperial"), ("Cổ Thần", "Ancient"), ("Thần Thoại", "Mythic"), ("Hỗn Nguyên", "Primal")]
RARITY_SUFFIX = {"common": ("", ""), "rare": (" Tinh Luyện", " (Refined)"), "epic": (" Thần Phẩm", " (Divine)")}
MATERIAL_NAMES = {
    1: [("Da Thú Rừng", "Beast Hide"), ("Nanh Hổ", "Tiger Fang"), ("Hạt Lúa Linh", "Spirit Rice Grain")],
    2: [("Quặng Đồng", "Copper Ore"), ("Vảy Rắn Đồng", "Bronze Snake Scale"), ("Lõi Đồng Cổ", "Ancient Bronze Core")],
    3: [("Rêu Đầm", "Marsh Moss"), ("Vảy Cá Tinh", "Fish Spirit Scale"), ("Ngọc Đầm Lầy", "Marsh Pearl")],
    4: [("Cát Nóng", "Scorched Sand"), ("Vỏ Bọ Cạp", "Scorpion Shell"), ("Tinh Thạch Hoả", "Flame Crystal")],
    5: [("Đất Đỏ Nung", "Fired Red Clay"), ("Ngà Thú", "Beast Tusk"), ("Đá Bazan Cổ", "Ancient Basalt")],
    6: [("Móng Thú Núi", "Mountain Claw"), ("Lông Hồ Ly", "Fox Fur"), ("Châu Hồ Tinh", "Fox Spirit Orb")],
    7: [("Gỗ Cọc Cổ", "Ancient Stake Wood"), ("Vảy Giao Long", "Flood Dragon Scale"), ("Ngọc Giao", "Dragon Pearl")],
    8: [("Đá Dung Nham", "Lava Rock"), ("Lông Phụng Lửa", "Fire Phoenix Feather"), ("Hồng Ngọc Nham Thạch", "Magma Ruby")],
    9: [("Sương Đọng", "Condensed Mist"), ("Da Mãng Xà", "Python Skin"), ("Tinh Thể Mây", "Cloud Crystal")],
    10: [("Gạch Thành Cổ", "Ancient Citadel Brick"), ("Lông Gà Trắng", "White Rooster Feather"), ("Ấn Cổ Thành", "Citadel Seal")],
    11: [("Vảy Thuồng Luồng", "River Monster Scale"), ("Ngọc Long Động", "Dragon Cave Gem"), ("Tinh Thể Long Mạch", "Dragon Vein Crystal")],
    12: [("Gỗ Nghìn Năm", "Millennium Wood"), ("Lông Hổ Trắng", "White Tiger Fur"), ("Nhựa Cây Cổ Thụ", "Elder Tree Resin")],
    13: [("Vỏ Sò Biển Sâu", "Deep Sea Shell"), ("Xúc Tu Cự Tuộc", "Giant Cephalopod Tentacle"), ("Ngọc Đại Dương", "Ocean Pearl")],
    14: [("Mảnh Ngói Cung Điện", "Palace Tile Shard"), ("Đá Nghê Cổ", "Ancient Nghe Stone"), ("Ngọc Ấn Cung Đình", "Imperial Seal Jade")],
    15: [("Tro Huyền Thoại", "Legend Ash"), ("Vảy Cổ Long", "Ancient Dragon Scale"), ("Tinh Hoa Huyền Thoại", "Legend Essence")],
}

names_vi, names_en = [], []  # (id, name)

# ---------- materials ----------
mats = []
for z in sorted(zones, key=lambda r: int(r["order"])):
    n = int(z["order"])
    mid_lv = (int(z["level_min"]) + int(z["level_max"])) / 2
    for g in (1, 2, 3):
        mid = f"mat_{z['id'].replace('zone_', 'z')}_{g}"
        price = round(1.5 * mid_lv ** 1.2 * [1, 2.5, 8][g - 1])
        mats.append([mid, z["id"], g, price])
        vi, en = MATERIAL_NAMES[n][g - 1]
        names_vi.append((mid, vi))
        names_en.append((mid, en))
write("materials.csv", ["id", "zone_id", "grade", "base_price"], mats)
mat_id = lambda zone, g: f"mat_{zone.replace('zone_', 'z')}_{g}"

# ---------- items ----------
items, recipes = [], []
weapon_families = {s["weapon"]: s for s in schools}
acc_kinds = ["ring", "amulet"]


def add_item(iid, kind, slot, family, school, aclass, tier, lv, rarity, stats, price, craft, name_vi, name_en):
    items.append([iid, kind, slot, family, school, aclass, tier, lv, rarity, stats, price, "true" if craft else "false"])
    names_vi.append((iid, name_vi))
    names_en.append((iid, name_en))


for ti, L in enumerate(TIER_LV, start=1):
    tname = TIER_NAME[ti - 1]
    zone = zone_for_level(L)
    for code, rar, sm, pm in RARITIES:
        sv, se = RARITY_SUFFIX[rar]
        price_base = lambda: round(12 * L ** 1.45 * pm)
        for fam, s in weapon_families.items():
            atk = round((3 * L ** 1.25 + 5) * WEAPON_MULT[s["role"]] * sm)
            add_item(f"eq_wpn_{fam}_{ti:02d}_{code}", "equip", "weapon", fam, s["id"], "", ti, L, rar,
                     f"atk={atk}", price_base(), code == "c",
                     f"{FAMILY_NAME[fam][0]} {tname[0]}{sv}", f"{tname[1]} {FAMILY_NAME[fam][1]}{se}")
        for cls, cm in ARMOR_MULT.items():
            d = round((1.6 * L ** 1.2 + 3) * cm * sm)
            hp = round(15 * L ** 1.1 * cm * sm)
            add_item(f"eq_arm_{cls}_{ti:02d}_{code}", "equip", "armor", cls, "", cls, ti, L, rar,
                     f"def={d};hp={hp}", price_base(), code == "c",
                     f"{FAMILY_NAME[cls][0]} {tname[0]}{sv}", f"{tname[1]} {FAMILY_NAME[cls][1]}{se}")
        for ak in acc_kinds:
            val = round(min(0.30, 0.01 + 0.0008 * L) * sm, 3)
            stats = f"atk_pct={val};crit_rate={round(val / 4, 3)}" if ak == "ring" else f"hp_pct={val};def_pct={round(val / 2, 3)}"
            add_item(f"eq_acc_{ak}_{ti:02d}_{code}", "equip", "accessory", ak, "", "", ti, L, rar, stats,
                     price_base(), code == "c",
                     f"{FAMILY_NAME[ak][0]} {tname[0]}{sv}", f"{tname[1]} {FAMILY_NAME[ak][1]}{se}")
    # potions
    for pk, label, label_en, stat in (("hp", "Thuốc Hồi Máu", "HP Potion", f"heal_hp={round(45 * L ** 1.15 + 20)}"),
                                      ("mp", "Thuốc Hồi Nội Lực", "MP Potion", f"heal_mp={round(30 * L ** 1.1 + 10)}")):
        add_item(f"pot_{pk}_{ti:02d}", "consumable", "potion", pk, "", "", ti, L, "common", stat,
                 round(2 * L ** 1.2 + 5), True, f"{label} Bậc {ti}", f"{label_en} T{ti}")
    if ti in (1, 4, 7, 10, 13, 16, 19):
        add_item(f"food_{ti:02d}", "consumable", "food", "food", "", "", ti, L, "common",
                 f"satiety=60;mood=+{ti // 3}", round(1.2 * L ** 1.15 + 4), True, f"Thức Ăn Bậc {ti}", f"Meal T{ti}")

SPECIAL = [("item_rebirth_pill", "rebirth=1", 0), ("item_summon_horn", "summon_golden_boss=1", 0),
           ("item_recruit_token", "recruit_rare=1", 0), ("item_pa_lens", "reveal_pa_one=1;iap=consumable", 0),
           ("item_pa_eye", "reveal_pa_all=1;iap=permanent", 0),
           ("item_banner", "party_buffer_substitute=1;dur_min=30", 0)]
for sid, stats, price in SPECIAL:
    items.append([sid, "special", "special", "", "", "", 0, 0, "epic", stats, price, "false"])

write("items.csv", ["id", "kind", "slot", "family", "school_req", "armor_class", "tier", "level_req", "rarity",
                    "stats", "price", "craftable"], items)

# ---------- recipes ----------
bld_for = {"weapon": "bld_smith", "armor": "bld_smith", "accessory": "bld_jeweler", "potion": "bld_alchemy",
           "food": "bld_restaurant"}
for it in items:
    if it[11] != "true":
        continue
    iid, slot, ti, L, price = it[0], it[2], int(it[6]), int(it[7]), int(it[10])
    zone = zone_for_level(L)
    if slot in ("weapon", "armor"):
        q = {1: 3 + ti, 2: 1 + ti // 4 if ti >= 3 else 0, 3: ti // 6}
    elif slot == "accessory":
        q = {1: 2 + ti // 2, 2: 2 + ti // 3, 3: ti // 5}
    else:
        q = {1: 2 + ti // 2, 2: 0, 3: 0}
    inputs = ";".join(f"{mat_id(zone, g)}:{n}" for g, n in q.items() if n > 0)
    recipes.append([f"rec_{iid}", iid, bld_for[slot], math.ceil(ti / 2), inputs, round(price * 0.35),
                    round(20 * 1.15 ** ti)])
recipes.append(["rec_item_rebirth_pill", "item_rebirth_pill", "bld_shrine", 1,
                f"{mat_id('zone_08', 3)}:5;{mat_id('zone_09', 3)}:5;{mat_id('zone_10', 3)}:5", 50000, 3600])
write("recipes.csv", ["id", "output", "building", "building_lv_req", "inputs", "gold", "time_s"], recipes)

# ---------- drop tables ----------
HEAD = ["table_id", "kind", "ref", "chance", "qty_min", "qty_max", "lv_min", "lv_max"]
drops = []
for z in sorted(zones, key=lambda r: int(r["order"])):
    zid, n = z["id"], int(z["order"])
    lo, hi = int(z["level_min"]), int(z["level_max"])
    zn = f"{n:02d}"
    t, tb = f"drop_zone_{zn}", f"drop_zone_{zn}_boss"
    drops += [[t, "gold", "base_gold", 1.0, 0.8, 1.2, "", ""],
              [t, "material", mat_id(zid, 1), 0.55, 1, 3, "", ""],
              [t, "material", mat_id(zid, 2), 0.20, 1, 2, "", ""],
              [t, "material", mat_id(zid, 3), 0.04, 1, 1, "", ""],
              [t, "equip_pool", "rare", 0.015, 1, 1, lo, hi]]
    drops += [[tb, "gold", "base_gold", 1.0, 4, 6, "", ""],
              [tb, "material", mat_id(zid, 1), 1.0, 4, 8, "", ""],
              [tb, "material", mat_id(zid, 2), 1.0, 2, 4, "", ""],
              [tb, "material", mat_id(zid, 3), 0.5, 1, 2, "", ""],
              [tb, "equip_pool", "rare", 0.25, 1, 1, lo, hi],
              [tb, "equip_pool", "epic", 0.03, 1, 1, lo, hi]]
    tg = f"loot_gb_{zn}"
    pill = 0.02 if n <= 5 else (0.04 if n <= 10 else 0.06)
    drops += [[tg, "gold", "base_gold", 1.0, 10, 15, "", ""],
              [tg, "material", mat_id(zid, 1), 1.0, 10, 20, "", ""],
              [tg, "material", mat_id(zid, 2), 1.0, 5, 10, "", ""],
              [tg, "material", mat_id(zid, 3), 0.8, 2, 4, "", ""],
              [tg, "equip_pool", "rare", 0.6, 1, 1, lo, hi],
              [tg, "equip_pool", "epic", 0.15, 1, 1, lo, hi],
              [tg, "item", "item_rebirth_pill", pill, 1, 1, "", ""],
              [tg, "item", "item_banner", 0.05, 1, 1, "", ""],
              [tg, "item", "item_summon_horn", 0.03, 1, 1, "", ""],
              [tg, "item", "item_recruit_token", 0.04, 1, 1, "", ""]]
write("drop_tables.csv", HEAD, drops)

# ---------- buildings ----------
HQ_COST = [0, 2000, 15000, 80000, 350000, 1500000, 6000000, 25000000]
HQ_EFFECT = lambda n: f"member_cap={8 + 4 * n};building_slots={6 + 3 * n}"
MAXH = 8
# (id, max_lv, unlock_hq, wave, cost_base, effects_fn)
B = [
    ("bld_housing", 10, 1, 1, 600, lambda n: f"member_cap=+{4 * n}"),
    ("bld_trade", 8, 1, 1, 500, lambda n: f"order_slots={1 + n // 2}"),
    ("bld_bounty", 8, 1, 1, 500, lambda n: f"bounty_slots={1 + n // 2};bounty_reward_mult={round(1 + 0.05 * n, 2)}"),
    ("bld_restaurant", 10, 1, 1, 450, lambda n: f"satiety_mult={round(1 + 0.1 * n, 2)};max_food_tier={math.ceil(n * 7 / 10)}"),
    ("bld_tavern", 8, 2, 1, 700, lambda n: f"mood_gain={round(0.02 * n, 2)}"),
    ("bld_inn", 10, 1, 1, 500, lambda n: f"stamina_regen_mult={round(1 + 0.12 * n, 2)}"),
    ("bld_infirmary", 10, 1, 1, 550, lambda n: f"hp_regen_mult={round(1 + 0.12 * n, 2)};injury_recovery={round(0.05 * n, 2)}"),
    ("bld_training", 10, 1, 1, 650, lambda n: f"train_xp_pct={round(0.03 * n, 2)};train_slots={2 + n}"),
    ("bld_smith", 11, 1, 1, 700, lambda n: f"max_craft_tier={min(N_TIER, 2 * n)};craft_speed_mult={round(1 + 0.08 * n, 2)}"),
    ("bld_jeweler", 11, 2, 1, 800, lambda n: f"max_craft_tier={min(N_TIER, 2 * n)};craft_speed_mult={round(1 + 0.08 * n, 2)}"),
    ("bld_alchemy", 11, 1, 1, 700, lambda n: f"max_craft_tier={min(N_TIER, 2 * n)};craft_speed_mult={round(1 + 0.08 * n, 2)}"),
    ("bld_market", 10, 1, 1, 600, lambda n: f"market_slots={6 + 3 * n};tax_rate_cap={round(0.10 + 0.01 * n, 2)}"),
    ("bld_academy_skill", 10, 1, 1, 800, lambda n: f"teach_max_skill_lv={2 * n};unlock_ultimate={int(n >= 6)};unlock_secret={int(n >= 8)}"),
    ("bld_academy_trait", 8, 2, 1, 900, lambda n: f"trait_reveal_speed={round(0.1 * n, 2)};teach_rare={int(n >= 3)};teach_epic={int(n >= 6)}"),
    ("bld_enhance", 10, 3, 1, 1000, lambda n: f"max_enhance_lv={2 * n}"),
    ("bld_bank", 8, 3, 1, 1200, lambda n: f"daily_interest_pct={round(0.2 * n, 2)}"),
    ("bld_buff_courage", 10, 3, 1, 1000, lambda n: f"atk_pct={round(0.01 * n, 2)}"),
    ("bld_buff_life", 10, 3, 1, 1000, lambda n: f"hp_pct={round(0.01 * n, 2)}"),
    ("bld_buff_wisdom", 10, 3, 1, 1000, lambda n: f"xp_pct={round(0.015 * n, 3)}"),
    ("bld_shrine", 6, 2, 1, 1500, lambda n: f"revive_cost_mult={round(1 - 0.05 * n, 2)};rebirth_max={min(n, 5)};phi_thang={int(n >= 6)}"),
    ("bld_tower", 10, 5, 2, 2000, lambda n: f"floor_cap={10 * n}"),
    ("bld_arena", 8, 5, 2, 2000, lambda n: f"opponents={2 + n};reward_mult={round(1 + 0.1 * n, 1)}"),
    ("bld_scout", 8, 2, 1, 900, lambda n: f"pa_error={38 - 4 * n};candidate_extra={n // 2}"),
    ("bld_stable", 8, 3, 1, 900, lambda n: f"move_speed_pct={round(0.03 * n, 2)}"),
    ("bld_chronicle", 5, 2, 1, 600, lambda n: f"log_slots={50 * n};narrative_ai={int(n >= 1)}"),
]
zones_by_hq = {}
for z in zones:
    zones_by_hq.setdefault(int(z["guild_lv_req"]), []).append(z["id"])


def mat_zone_for_hq(h):
    best = "zone_01"
    for z in sorted(zones, key=lambda r: int(r["order"])):
        if int(z["guild_lv_req"]) <= h:
            best = z["id"]
    return best


blds = []
for n in range(1, MAXH + 1):
    z = mat_zone_for_hq(n)
    blds.append(["bld_hq", n, 1 if n == 1 else n, HQ_COST[n - 1], "" if n == 1 else f"{mat_id(z, 1)}:{10 * n}",
                 0 if n == 1 else round(30 * 2.0 ** (n - 1)), HQ_EFFECT(n)])
for bid, mx, unlock, wave, base, fx in B:
    for n in range(1, mx + 1):
        hq = max(unlock, math.ceil(n * MAXH / mx))
        z = mat_zone_for_hq(hq)
        gold = round(base * 1.9 ** (n - 1))
        qty = 4 * n + 2
        blds.append([bid, n, hq, gold, f"{mat_id(z, 1)}:{qty}" + (f";{mat_id(z, 2)}:{n}" if n >= 3 else ""),
                     round(5 * 1.7 ** (n - 1)), fx(n)])
write("buildings.csv", ["building_id", "level", "hq_lv_req", "cost_gold", "cost_mats", "build_time_min", "effects"], blds)
bmeta = [["bld_hq", 8, 1, 1]] + [[b[0], b[1], b[2], b[3]] for b in B]
write("building_meta.csv", ["id", "max_lv", "unlock_hq_lv", "wave"], bmeta)

# ---------- quests ----------
QH = ["id", "period", "objective", "count_base", "count_per_guild_lv", "reward_gold_base", "reward_gold_per_guild_lv",
      "reward_gem", "reward_items", "ad_variant", "premium_auto_claim", "min_guild_lv"]
quests = [
    ["q_d_hunt", "daily", "kill_monsters", 40, 10, 300, 150, 5, "", "false", "false", 1],
    ["q_d_golden_boss", "daily", "join_golden_boss", 1, 0, 500, 250, 10, "", "false", "false", 1],
    ["q_d_sell", "daily", "sell_items_market", 5, 2, 250, 120, 5, "", "false", "false", 1],
    ["q_d_recruit", "daily", "accept_candidate", 1, 0, 400, 200, 8, "", "false", "false", 1],
    ["q_d_login", "daily", "login", 1, 0, 200, 100, 3, "", "false", "false", 1],
    ["q_d_watch_ad", "daily", "watch_rewarded_ad", 1, 0, 600, 300, 10, "", "true", "true", 1],
    ["q_w_craft", "weekly", "craft_items", 15, 5, 1500, 800, 20, "", "false", "false", 1],
    ["q_w_upgrade", "weekly", "upgrade_building", 2, 0, 2500, 1200, 25, "", "false", "false", 1],
    ["q_w_bounty", "weekly", "complete_bounties", 10, 2, 2000, 1000, 20, "", "false", "false", 1],
    ["q_w_backlog_boss", "weekly", "defeat_backlog_boss", 1, 0, 3000, 1500, 30, "item_banner:1", "false", "false", 2],
    ["q_w_watch_ad", "weekly", "watch_rewarded_ad", 3, 0, 2000, 1000, 20, "", "true", "true", 1],
    ["q_w_all_done", "weekly", "complete_all_weekly", 1, 0, 0, 0, 0, "item_pa_lens:1", "false", "false", 1],
]
write("quests.csv", QH, quests)

# ---------- config ----------
CFG = [
    ("tick_rate", 10), ("party_max", 5), ("max_traits", 3), ("pa_max", 200), ("ca_max", 200),
    ("element_counter_mult", 1.25), ("element_countered_mult", 0.8), ("element_same_mult", 0.95),
    ("monster_hp_coef", 40), ("monster_hp_exp", 1.3), ("monster_atk_coef", 6), ("monster_atk_exp", 1.25),
    ("monster_def_coef", 3), ("monster_def_exp", 1.2), ("xp_need_coef", 100), ("xp_need_exp", 1.7),
    ("base_gold_coef", 2.0), ("base_gold_exp", 1.1), ("growth_mult_base", 0.6), ("growth_mult_pa", 0.8),
    ("party_xp_per_member", 0.08), ("party_buffer_bonus", 0.10), ("party_tank_bonus", 0.05),
    ("party_no_buffer_penalty", 0.0), ("golden_boss_interval_min", 60), ("golden_boss_backlog_max", 3),
    ("offline_cap_free_h", 8), ("offline_cap_premium_h", 24), ("pa_lens_weekly_free", 1),
    ("pa_lens_stock_cap", 5), ("cost_scale", 1.0), ("raid_min_level_ratio", 0.5),
]
write("config.csv", ["key", "value"], CFG)

# ---------- tên vật phẩm ----------
write("names_items_vi.csv", ["id", "name", "short", "desc"], [[i, n, n, ""] for i, n in names_vi], folder="i18n")
write("names_items_en.csv", ["id", "name", "short", "desc"], [[i, n, n, ""] for i, n in names_en], folder="i18n")
