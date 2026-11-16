#!/usr/bin/env python3
"""Sinh dữ liệu (c): nhịp XP (đầu game nhanh, chuyển sinh chậm dần), hệ thống TIÊU VÀNG:
cường hoá (enhance.csv), buff ăn/uống (feast_/brew_), Bùa Hộ Cường, giá thuốc/đồ ăn, thuế & phí duy trì bang.
Idempotent: chạy lại cho cùng kết quả (upsert theo id/key; giá tính theo công thức tuyệt đối).
Chạy: python3 -I tools/gen_c.py"""
import csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf8", newline="") as f:
        r = csv.reader(f)
        head = next(r)
        return head, [dict(zip(head, row)) for row in r]


def write(path, head, rows):
    with open(os.path.join(ROOT, path), "w", encoding="utf8", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        for r in rows:
            w.writerow([r.get(h, "") for h in head])
    print(f"{path}: {len(rows)} dòng")


def upsert(rows, new, key):
    ids = {r[key] for r in new}
    return [r for r in rows if r[key] not in ids] + new


# ---------- 1. config ----------
CFG = [
    ("xp_early_floor", 0.08), ("xp_early_end", 40),
    ("xp_rebirth_mult_0", 1), ("xp_rebirth_mult_1", 3), ("xp_rebirth_mult_2", 5),
    ("xp_rebirth_mult_3", 8), ("xp_rebirth_mult_4", 12), ("xp_rebirth_mult_5", 18),
    ("income_ref_per_level", 1000),      # vàng/giờ/người ≈ 1000·level (đo bằng simulator)
    ("potion_use_per_hour", 5), ("feast_use_per_hour", 1), ("brew_use_per_hour", 1),
    ("feast_xp_pct", 0.10), ("brew_dps_pct", 0.10), ("buff_duration_s", 3600),
    ("guild_tax_pct", 0.10), ("guild_upkeep_per_level_day", 700),
    ("enhance_base_per_level", 30), ("enhance_max_lv", 20),
]
h, rows = read("data/config.csv")
rows = upsert(rows, [{"key": k, "value": str(v)} for k, v in CFG], "key")
write("data/config.csv", h, rows)

# ---------- 2. enhance.csv ----------
SUCC = [100, 100, 95, 90, 85, 80, 70, 60, 50, 40, 35, 30, 25, 20, 15, 12, 10, 8, 6, 5]
COST = [1, 1, 1.5, 2, 3, 4, 6, 8, 12, 18, 25, 36, 50, 70, 100, 140, 200, 280, 400, 600]
enh = []
cum = 0.0
for n in range(1, 21):
    cum += 0.04 if n <= 10 else 0.025
    enh.append({"level": n, "success_pct": SUCC[n - 1], "cost_mult": COST[n - 1],
                "fail_effect": "none" if n <= 5 else "drop_1", "stat_pct_total": round(cum, 3),
                "ward_usable": "false" if n <= 5 else "true"})
write("data/enhance.csv", ["level", "success_pct", "cost_mult", "fail_effect", "stat_pct_total", "ward_usable"], enh)

# ---------- 3. vật phẩm: giá thuốc/đồ ăn, feast_/brew_, Bùa Hộ Cường ----------
ih, items = read("data/items.csv")
for it in items:
    if it["kind"] == "consumable" and it["id"].startswith(("pot_", "food_")):
        L = int(it["level_req"])
        if it["id"].startswith("pot_hp"):
            it["price"] = str(max(8, round(14 * L)))
        elif it["id"].startswith("pot_mp"):
            it["price"] = str(max(6, round(11 * L)))
        else:
            it["price"] = str(max(5, round(6 * L)))
TIERS = sorted({(int(i["tier"]), int(i["level_req"])) for i in items if i["kind"] == "equip"})
new_items, new_rec, nv, ne = [], [], [], []
_, recs = read("data/recipes.csv")
rec_by_out = {r["output"]: r for r in recs}
_, bm = read("data/building_meta.csv")
maxlv = {r["id"]: int(r["max_lv"]) for r in bm}
for t, L in TIERS:
    for pre, bld, price_k, stats, vi, en in (
        ("feast", "bld_restaurant", 90, "xp_pct=0.10;dur_s=3600", "Tiệc Bồi Bổ", "Nourishing Feast"),
        ("brew", "bld_tavern", 70, "dps_pct=0.10;dur_s=3600", "Rượu Tráng Khí", "Valor Brew"),
    ):
        iid = f"{pre}_{t:02d}"
        price = max(30, round(price_k * L))
        new_items.append({"id": iid, "kind": "consumable", "slot": "food" if pre == "feast" else "drink",
                          "family": "buff", "school_req": "", "armor_class": "", "tier": t, "level_req": L,
                          "rarity": "common", "stats": stats, "price": price, "craftable": "true"})
        src = rec_by_out.get(f"eq_wpn_sword_{t:02d}_c")
        mat = src["inputs"].split(";")[0].split(":")[0] if src else "mat_z01_1"
        new_rec.append({"id": f"rec_{iid}", "output": iid, "building": bld,
                        "building_lv_req": min(maxlv[bld], (t + 1) // 2), "inputs": f"{mat}:3",
                        "gold": round(price * 0.3), "time_s": 20 + t * 2})
        nv.append({"id": iid, "name": f"{vi} Bậc {t}", "short": f"{vi} Bậc {t}", "desc": ""})
        ne.append({"id": iid, "name": f"{en} Tier {t}", "short": f"{en} T{t}", "desc": ""})
new_items.append({"id": "item_enhance_ward", "kind": "special", "slot": "special", "family": "", "school_req": "",
                  "armor_class": "", "tier": 0, "level_req": 0, "rarity": "epic",
                  "stats": "enhance_no_drop=1;craft_only=1", "price": 0, "craftable": "false"})
nv.append({"id": "item_enhance_ward", "name": "Bùa Hộ Cường", "short": "Hộ Cường",
           "desc": "Giữ nguyên cấp cường hoá khi thất bại. Chỉ chế tạo, không bán."})
ne.append({"id": "item_enhance_ward", "name": "Enhancement Ward", "short": "Ward",
           "desc": "Keeps the enhancement level on failure. Craft-only, not sold."})
items = upsert(items, new_items, "id")
write("data/items.csv", ih, items)
rh, recs = read("data/recipes.csv")
new_rec.append({"id": "rec_item_enhance_ward", "output": "item_enhance_ward", "building": "bld_enhance",
                "building_lv_req": 3, "inputs": "mat_z06_1:8;mat_z06_2:2", "gold": 20000, "time_s": 600})
recs = upsert(recs, new_rec, "id")
write("data/recipes.csv", rh, recs)
for lang, new in (("vi", nv), ("en", ne)):
    p = f"i18n/names_items_{lang}.csv"
    nh, nr = read(p)
    write(p, nh, upsert(nr, new, "id"))
