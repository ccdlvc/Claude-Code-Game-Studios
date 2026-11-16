#!/usr/bin/env python3
"""Kiểm tra dữ liệu game. Chạy: python3 -I tools/content_validator.py [thư_mục_gốc]
Thoát mã 1 nếu có lỗi (ERROR); cảnh báo (WARN) không làm fail."""
import csv, os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERR, WARN = [], []
ELEMENTS = {"kim", "moc", "thuy", "hoa", "tho"}
ZONE_ELEMENTS = ELEMENTS | {"mixed"}
LEVEL_CAP = {0: 100, 1: 120, 2: 140, 3: 160, 4: 180, 5: 200}
REBIRTH_WAVE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 3, 5: 3}


def load(name, folder="data"):
    path = os.path.join(ROOT, folder, name)
    if not os.path.exists(path):
        ERR.append(f"thiếu file {folder}/{name}")
        return []
    with open(path, encoding="utf8", newline="") as f:
        rows = list(csv.reader(f))
    head, body = rows[0], rows[1:]
    out = []
    for i, r in enumerate(body, start=2):
        if len(r) != len(head):
            ERR.append(f"{name} dòng {i}: {len(r)} cột, cần {len(head)}")
            continue
        out.append(dict(zip(head, r)))
    return out


def unique(rows, name):
    seen = set()
    for r in rows:
        if r["id"] in seen:
            ERR.append(f"{name}: id trùng {r['id']}")
        seen.add(r["id"])
    return seen


def to_int(v, ctx):
    try:
        return int(v)
    except ValueError:
        ERR.append(f"{ctx}: '{v}' không phải số nguyên")
        return 0


schools = load("schools.csv")
skills = load("skills.csv")
traits = load("traits.csv")
zones = load("zones.csv")
monsters = load("monsters.csv")
grounds = load("grounds.csv")
bosses = load("golden_bosses.csv")

school_ids = unique(schools, "schools")
skill_ids = unique(skills, "skills")
trait_ids = unique(traits, "traits")
zone_ids = unique(zones, "zones")
mon_ids = unique(monsters, "monsters")
ground_ids = unique(grounds, "grounds")
boss_ids = unique(bosses, "golden_bosses")

# schools
if len(schools) != 10:
    ERR.append(f"schools: có {len(schools)} phái, cần 10")
for sc in schools:
    if sc.get("armor_class") not in ("heavy", "medium", "light"):
        ERR.append(f"schools {sc['id']}: armor_class lạ")
for s in schools:
    if s["element"] not in ELEMENTS:
        ERR.append(f"schools {s['id']}: hệ lạ '{s['element']}'")
w1 = [s for s in schools if s["wave"] == "1"]
if len(w1) != 5:
    ERR.append(f"schools: Wave 1 có {len(w1)} phái, cần 5")
if not any(s["buff_role"] == "true" for s in w1):
    ERR.append("schools: Wave 1 không có phái buff")
if {s["element"] for s in w1} != ELEMENTS:
    WARN.append("schools: Wave 1 chưa đủ 5 hệ")

# skills
per_school = {}
for s in skills:
    per_school.setdefault(s["school_id"], []).append(s)
    sid = s["id"]
    if s["school_id"] not in school_ids:
        ERR.append(f"skills {sid}: phái '{s['school_id']}' không tồn tại")
    if s["element"] not in ELEMENTS:
        ERR.append(f"skills {sid}: hệ lạ")
    lv_req = to_int(s["lv_req"], sid)
    rb = to_int(s["rebirth_req"], sid)
    if rb not in LEVEL_CAP:
        ERR.append(f"skills {sid}: rebirth_req {rb} không hợp lệ")
        continue
    if lv_req > LEVEL_CAP[rb]:
        ERR.append(f"skills {sid}: lv_req {lv_req} vượt level cap {LEVEL_CAP[rb]} của chuyển sinh {rb}")
    school_wave = int(next((x["wave"] for x in schools if x["id"] == s["school_id"]), 1))
    need_wave = max(REBIRTH_WAVE[rb], school_wave)
    if to_int(s["unlock_wave"], sid) != need_wave:
        ERR.append(f"skills {sid}: unlock_wave {s['unlock_wave']} lệch (cần {need_wave}: chuyển sinh {rb}, phái wave {school_wave})")
    for p in filter(None, s["prereq"].split(";")):
        pid, _, plv = p.partition(":")
        if pid not in skill_ids:
            ERR.append(f"skills {sid}: tiền đề '{pid}' không tồn tại")
        elif not plv.isdigit():
            ERR.append(f"skills {sid}: tiền đề '{p}' thiếu cấp")
        else:
            ps = next(x for x in skills if x["id"] == pid)
            if int(plv) > int(ps["max_lv"]):
                ERR.append(f"skills {sid}: tiền đề {pid}:{plv} vượt max_lv {ps['max_lv']}")
            if ps["school_id"] != s["school_id"]:
                ERR.append(f"skills {sid}: tiền đề khác phái")
    for e in filter(None, s["effects"].split(";")):
        if "=" not in e:
            ERR.append(f"skills {sid}: effect '{e}' sai định dạng")
for sc, lst in per_school.items():
    if len(lst) != 12:
        ERR.append(f"skills: phái {sc} có {len(lst)} skill, cần 12")
    slots = sorted(int(x["slot"]) for x in lst)
    if slots != list(range(1, 13)):
        ERR.append(f"skills: phái {sc} slot không đủ 1–12")
for s in schools:
    if s["id"] not in per_school:
        ERR.append(f"skills: phái {s['id']} chưa có skill")

# traits
tr_by_id = {t["id"]: t for t in traits}
if len(traits) != 40:
    WARN.append(f"traits: có {len(traits)} trait, mục tiêu 40")
for t in traits:
    for c in filter(None, t["conflicts"].replace(",", ";").split(";")):
        if c not in trait_ids:
            ERR.append(f"traits {t['id']}: xung đột với '{c}' không tồn tại")
        elif t["id"] not in tr_by_id[c]["conflicts"].split(";"):
            WARN.append(f"traits: {t['id']} xung đột {c} nhưng chiều ngược lại chưa khai báo")
    for e in filter(None, t["effects"].split(";")):
        if "=" not in e:
            ERR.append(f"traits {t['id']}: effect '{e}' sai định dạng")

# zones
prev_max = None
for z in sorted(zones, key=lambda r: int(r["order"])):
    zid = z["id"]
    lo, hi = to_int(z["level_min"], zid), to_int(z["level_max"], zid)
    rb = to_int(z["rebirth_req"], zid)
    if z["primary_element"] not in ZONE_ELEMENTS:
        ERR.append(f"zones {zid}: hệ lạ")
    if prev_max is not None and lo != prev_max:
        ERR.append(f"zones {zid}: level_min {lo} không nối với vùng trước (max {prev_max})")
    prev_max = hi
    if rb not in REBIRTH_WAVE or int(z["wave"]) != REBIRTH_WAVE[rb]:
        ERR.append(f"zones {zid}: wave {z['wave']} lệch với rebirth_req {rb}")
    if z["boss_monster_id"] not in mon_ids:
        ERR.append(f"zones {zid}: boss '{z['boss_monster_id']}' không có trong monsters")
if len(zones) != 15:
    ERR.append(f"zones: có {len(zones)} vùng, cần 15")

# monsters
zone_by_id = {z["id"]: z for z in zones}
drop_tables = set()
for m in monsters:
    mid = m["id"]
    z = zone_by_id.get(m["zone_id"])
    if not z:
        ERR.append(f"monsters {mid}: vùng '{m['zone_id']}' không tồn tại")
        continue
    lv = to_int(m["level"], mid)
    if not (int(z["level_min"]) <= lv <= int(z["level_max"])):
        ERR.append(f"monsters {mid}: level {lv} ngoài vùng {z['level_min']}–{z['level_max']}")
    if m["element"] not in ELEMENTS:
        ERR.append(f"monsters {mid}: hệ lạ")
    if m["is_boss"] == "true" and m["role"] != "boss":
        ERR.append(f"monsters {mid}: is_boss nhưng role != boss")
    drop_tables.add(m["drop_table"])
for z in zones:
    if True:
        n_boss = sum(1 for m in monsters if m["zone_id"] == z["id"] and m["is_boss"] == "true")
        n_norm = sum(1 for m in monsters if m["zone_id"] == z["id"] and m["is_boss"] != "true")
        if n_boss != 1:
            ERR.append(f"zones {z['id']}: có {n_boss} boss, cần 1")
        if n_norm < 4:
            ERR.append(f"zones {z['id']}: chỉ {n_norm} loại quái thường, cần ≥ 4")

# grounds
for g in grounds:
    gid = g["id"]
    z = zone_by_id.get(g["zone_id"])
    if not z:
        ERR.append(f"grounds {gid}: vùng không tồn tại")
        continue
    lo, hi = to_int(g["level_min"], gid), to_int(g["level_max"], gid)
    if lo < int(z["level_min"]) or hi > int(z["level_max"]):
        ERR.append(f"grounds {gid}: level {lo}–{hi} ngoài vùng")
    for mid in g["monster_pool"].split(";"):
        m = next((x for x in monsters if x["id"] == mid), None)
        if not m:
            ERR.append(f"grounds {gid}: quái '{mid}' không tồn tại")
        elif m["zone_id"] != g["zone_id"]:
            ERR.append(f"grounds {gid}: quái {mid} thuộc vùng khác")
        elif m["is_boss"] == "true":
            ERR.append(f"grounds {gid}: bãi thường không được chứa boss {mid}")
for z in zones:
    if True:
        n = sum(1 for g in grounds if g["zone_id"] == z["id"])
        if n != 3:
            WARN.append(f"zones {z['id']}: có {n} bãi (kỳ vọng 3)")

# golden bosses
for b in bosses:
    m = next((x for x in monsters if x["id"] == b["monster_id"]), None)
    if not m:
        ERR.append(f"golden_bosses {b['id']}: quái '{b['monster_id']}' không tồn tại")
    elif m["is_boss"] != "true":
        ERR.append(f"golden_bosses {b['id']}: {m['id']} không phải boss")

# tham số mô phỏng
sim_roles = load("sim_roles.csv")
sim_params = load("sim_params.csv")
role_ids = {r["role"] for r in sim_roles}
for sc in schools:
    if sc["role"] not in role_ids:
        ERR.append(f"sim_roles: thiếu vai trò '{sc['role']}' của phái {sc['id']}")
for r in sim_roles:
    for k in ("dps_mult", "hp_mult", "def_mult"):
        try:
            if float(r[k]) <= 0:
                ERR.append(f"sim_roles {r['role']}: {k} phải > 0")
        except ValueError:
            ERR.append(f"sim_roles {r['role']}: {k} không phải số")
for r in sim_params:
    try:
        float(r["value"])
    except ValueError:
        ERR.append(f"sim_params {r['key']}: '{r['value']}' không phải số")
need = ["monster_dmg_factor", "flee_hp_pct", "bag_slots", "xp_kill_coef", "raid_hp_mult", "raid_dmg_mult", "raid_time_limit_s"]
have = {r["key"] for r in sim_params}
for k in need:
    if k not in have:
        ERR.append(f"sim_params: thiếu khoá {k}")

# chuyển sinh
rebirth = load("rebirth.csv")
prev_keep = 0
for r in rebirth:
    no = int(r["no"])
    if r["kind"] == "rebirth":
        if no not in LEVEL_CAP or no < 1:
            ERR.append(f"rebirth {no}: số lần ngoài 1–5")
            continue
        if int(r["req_level"]) != LEVEL_CAP[no - 1] or int(r["new_level_cap"]) != LEVEL_CAP[no]:
            ERR.append(f"rebirth {no}: req/cap lệch LEVEL_CAP ({LEVEL_CAP[no - 1]}→{LEVEL_CAP[no]})")
        if int(r["wave"]) != REBIRTH_WAVE[no]:
            ERR.append(f"rebirth {no}: wave {r['wave']} lệch (cần {REBIRTH_WAVE[no]})")
        if int(r["skill_keep_pct"]) <= prev_keep:
            ERR.append(f"rebirth {no}: skill_keep_pct phải tăng dần")
        prev_keep = int(r["skill_keep_pct"])
        if int(r["pill_cost"]) != no:
            WARN.append(f"rebirth {no}: pill_cost {r['pill_cost']} ≠ {no} (GDD 6.10: số đan = số lần)")
    elif r["kind"] != "ascension":
        ERR.append(f"rebirth {no}: kind lạ")
if sorted(int(r["no"]) for r in rebirth if r["kind"] == "rebirth") != [1, 2, 3, 4, 5]:
    ERR.append("rebirth: cần đủ 5 lần chuyển sinh")

# ====== vật phẩm, chế tạo, rơi đồ, công trình, nhiệm vụ, cấu hình ======
materials = load("materials.csv")
items = load("items.csv")
recipes = load("recipes.csv")
drops = load("drop_tables.csv")
blds = load("buildings.csv")
bmeta = load("building_meta.csv")
quests = load("quests.csv")
config = load("config.csv")

mat_ids = unique(materials, "materials")
item_ids = unique(items, "items")
unique(recipes, "recipes")
bmeta_by = {b["id"]: b for b in bmeta}
unique(bmeta, "building_meta")
quest_ids = unique(quests, "quests")
cfg = {c["key"]: c["value"] for c in config}
for k in ("tick_rate", "party_max", "offline_cap_free_h", "offline_cap_premium_h", "pa_lens_weekly_free", "pa_lens_stock_cap"):
    if k not in cfg:
        ERR.append(f"config: thiếu khoá {k}")
for c in config:
    try:
        float(c["value"])
    except ValueError:
        ERR.append(f"config {c['key']}: giá trị '{c['value']}' không phải số")
if cfg.get("party_max") not in (None, "5"):
    ERR.append("config: party_max phải là 5 (đã chốt)")

for m in materials:
    if m["zone_id"] not in zone_ids:
        ERR.append(f"materials {m['id']}: vùng không tồn tại")
for z in zones:
    for g in (1, 2, 3):
        if f"mat_{z['id'].replace('zone_', 'z')}_{g}" not in mat_ids:
            ERR.append(f"materials: vùng {z['id']} thiếu nguyên liệu hạng {g}")

TIERS = sorted({int(i["tier"]) for i in items if i["kind"] == "equip"})
if TIERS != list(range(1, 22)):
    ERR.append(f"items: bậc trang bị {TIERS[:3]}…{TIERS[-1:]} không đủ 1–21")
for i in items:
    if i["kind"] == "equip":
        if i["slot"] == "weapon" and i["school_req"] not in school_ids:
            ERR.append(f"items {i['id']}: school_req '{i['school_req']}' không tồn tại")
        if i["rarity"] not in ("common", "rare", "epic"):
            ERR.append(f"items {i['id']}: độ hiếm lạ")
        if (i["craftable"] == "true") != (i["rarity"] == "common"):
            ERR.append(f"items {i['id']}: chỉ đồ common mới chế tạo được")
fam_per_school = {sc["weapon"]: sc["id"] for sc in schools}
for tier in TIERS:
    for fam in fam_per_school:
        for code in "cre":
            if f"eq_wpn_{fam}_{tier:02d}_{code}" not in item_ids:
                ERR.append(f"items: thiếu vũ khí {fam} bậc {tier} ({code})")

for r in recipes:
    if r["output"] not in item_ids:
        ERR.append(f"recipes {r['id']}: sản phẩm '{r['output']}' không tồn tại")
    bm = bmeta_by.get(r["building"])
    if not bm:
        ERR.append(f"recipes {r['id']}: công trình '{r['building']}' không tồn tại")
    elif int(r["building_lv_req"]) > int(bm["max_lv"]):
        ERR.append(f"recipes {r['id']}: cần cấp {r['building_lv_req']} > max_lv {bm['max_lv']} của {r['building']}")
    for part in r["inputs"].split(";"):
        mid, _, q = part.partition(":")
        if mid not in mat_ids:
            ERR.append(f"recipes {r['id']}: nguyên liệu '{mid}' không tồn tại")
        if not q.isdigit() or int(q) <= 0:
            ERR.append(f"recipes {r['id']}: số lượng '{part}' sai")
craft_outputs = {r["output"] for r in recipes}
for i in items:
    if i["craftable"] == "true" and i["id"] not in craft_outputs:
        ERR.append(f"items {i['id']}: craftable nhưng không có công thức")

# bảng rơi đồ
drop_by_table = {}
for d in drops:
    drop_by_table.setdefault(d["table_id"], []).append(d)
    k = d["kind"]
    ch = float(d["chance"])
    if not (0 < ch <= 1):
        ERR.append(f"drop_tables {d['table_id']}: chance {ch} ngoài (0,1]")
    if k == "material" and d["ref"] not in mat_ids:
        ERR.append(f"drop_tables {d['table_id']}: nguyên liệu '{d['ref']}' không tồn tại")
    elif k == "item" and d["ref"] not in item_ids:
        ERR.append(f"drop_tables {d['table_id']}: vật phẩm '{d['ref']}' không tồn tại")
    elif k == "equip_pool":
        lo, hi = int(d["lv_min"]), int(d["lv_max"])
        hit = [i for i in items if i["kind"] == "equip" and i["rarity"] == d["ref"] and lo <= int(i["level_req"]) <= hi]
        if not hit:
            ERR.append(f"drop_tables {d['table_id']}: không có đồ {d['ref']} trong level {lo}–{hi}")
    elif k not in ("gold", "material", "item", "equip_pool"):
        ERR.append(f"drop_tables {d['table_id']}: loại '{k}' lạ")
    if int(float(d["qty_min"]) * 1000) > int(float(d["qty_max"]) * 1000):
        ERR.append(f"drop_tables {d['table_id']}: qty_min > qty_max")
for m in monsters:
    if m["drop_table"] not in drop_by_table:
        ERR.append(f"monsters {m['id']}: bảng rơi '{m['drop_table']}' chưa định nghĩa")
for b in bosses:
    if b["loot_table"] not in drop_by_table:
        ERR.append(f"golden_bosses {b['id']}: bảng '{b['loot_table']}' chưa định nghĩa")

# công trình
bl_by = {}
for b in blds:
    bl_by.setdefault(b["building_id"], []).append(b)
for bid, lst in bl_by.items():
    bm = bmeta_by.get(bid)
    if not bm:
        ERR.append(f"buildings: '{bid}' thiếu trong building_meta")
        continue
    lvs = sorted(int(x["level"]) for x in lst)
    if lvs != list(range(1, int(bm["max_lv"]) + 1)):
        ERR.append(f"buildings {bid}: các cấp không liên tục 1–{bm['max_lv']}")
    prev_cost, prev_hq = -1, 0
    for x in sorted(lst, key=lambda r: int(r["level"])):
        hq = int(x["hq_lv_req"])
        if hq < prev_hq:
            ERR.append(f"buildings {bid} cấp {x['level']}: hq_lv_req giảm")
        if int(x["cost_gold"]) < prev_cost:
            ERR.append(f"buildings {bid} cấp {x['level']}: chi phí giảm")
        prev_cost, prev_hq = int(x["cost_gold"]), hq
        for part in filter(None, x["cost_mats"].split(";")):
            if part.split(":")[0] not in mat_ids:
                ERR.append(f"buildings {bid}: nguyên liệu '{part}' không tồn tại")
        for e in filter(None, x["effects"].split(";")):
            if "=" not in e:
                ERR.append(f"buildings {bid}: effect '{e}' sai định dạng")
for bm in bmeta:
    if bm["id"] not in bl_by:
        ERR.append(f"building_meta: '{bm['id']}' không có cấp nào")
if len(bmeta) != 26:
    ERR.append(f"building_meta: có {len(bmeta)} công trình, cần 26")

# nhiệm vụ
weekly_lens = 0
for q in quests:
    qid = q["id"]
    if q["period"] not in ("daily", "weekly"):
        ERR.append(f"quests {qid}: period lạ")
    for part in filter(None, q["reward_items"].split(";")):
        iid, _, n = part.partition(":")
        if iid not in item_ids:
            ERR.append(f"quests {qid}: vật phẩm thưởng '{iid}' không tồn tại")
        if iid in ("item_pa_lens", "item_pa_eye"):
            if q["ad_variant"] == "true":
                ERR.append(f"quests {qid}: nhiệm vụ quảng cáo KHÔNG được thưởng Thiên Cơ Kính/Thiên Nhãn")
            if iid == "item_pa_eye":
                ERR.append(f"quests {qid}: Thiên Nhãn không được phát miễn phí")
            elif q["period"] == "weekly":
                weekly_lens += int(n or 1)
    if q["ad_variant"] == "true" and q["premium_auto_claim"] != "true":
        ERR.append(f"quests {qid}: nhiệm vụ quảng cáo phải có premium_auto_claim=true")
if weekly_lens != int(cfg.get("pa_lens_weekly_free", 1)):
    ERR.append(f"quests: tổng Thiên Cơ Kính miễn phí/tuần = {weekly_lens}, config = {cfg.get('pa_lens_weekly_free')}")
if sum(1 for q in quests if q["period"] == "daily") < 5:
    WARN.append("quests: ít hơn 5 nhiệm vụ ngày")

# tên (i18n)
required_ids = (set(school_ids) | set(zone_ids) | {m["id"] for m in monsters if m["is_boss"] == "true"}
                | set(mat_ids) | set(item_ids) | {b["id"] for b in bmeta})
for lang in ("vi", "en"):
    ids = set()
    for fname in (f"names_{lang}.csv", f"names_items_{lang}.csv"):
        names = load(fname, folder="i18n")
        ids |= unique(names, fname)
        for n in names:
            if not n["name"].strip():
                ERR.append(f"{fname}: id {n['id']} chưa có tên")
    miss = sorted(required_ids - ids)
    if miss:
        ERR.append(f"names_{lang}: thiếu tên cho {len(miss)} id, ví dụ {', '.join(miss[:6])}")

# ---------- tiêu vàng & nhịp XP ----------
_cfg = {r["key"]: r["value"] for r in load("config.csv")}
for k in ["xp_early_floor", "xp_early_end", "guild_tax_pct", "guild_upkeep_per_level_day",
          "enhance_base_per_level", "enhance_max_lv", "income_ref_per_level"] + [f"xp_rebirth_mult_{i}" for i in range(6)]:
    if k not in _cfg:
        ERR.append(f"config thiếu khoá {k}")
_mult = [float(_cfg.get(f"xp_rebirth_mult_{i}", 0)) for i in range(6)]
if _mult != sorted(_mult) or len(set(_mult)) != 6:
    ERR.append("xp_rebirth_mult_* phải tăng dần nghiêm ngặt (chuyển sinh càng về sau càng chậm)")
_enh = load("enhance.csv")
if [int(r["level"]) for r in _enh] != list(range(1, int(float(_cfg.get("enhance_max_lv", 0))) + 1)):
    ERR.append("enhance.csv: level phải liên tục 1..enhance_max_lv")
_p = [float(r["success_pct"]) for r in _enh]
_c = [float(r["cost_mult"]) for r in _enh]
if _p != sorted(_p, reverse=True) or any(not 0 < x <= 100 for x in _p):
    ERR.append("enhance.csv: success_pct phải giảm dần trong (0,100]")
if _c != sorted(_c):
    ERR.append("enhance.csv: cost_mult phải tăng dần")
_bm = {r["id"]: r for r in load("building_meta.csv")}
_blds = load("buildings.csv")
for r in _blds:
    if r["building_id"] == "bld_enhance":
        m = re.search(r"max_enhance_lv=(\d+)", r["effects"])
        if m and int(m.group(1)) > float(_cfg.get("enhance_max_lv", 0)):
            ERR.append(f"bld_enhance cấp {r['level']}: max_enhance_lv vượt enhance_max_lv")

for w in WARN:
    print("WARN ", w)
for e in ERR:
    print("ERROR", e)
print(f"\n{len(ERR)} lỗi, {len(WARN)} cảnh báo")
sys.exit(1 if ERR else 0)
