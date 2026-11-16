#!/usr/bin/env python3
"""Balance simulator: chạy lõi mô phỏng không đồ hoạ, xuất báo cáo Markdown + CSV vào out/.
Dùng: python3 tools/balance_sim.py [--quick]   (kết quả là điểm khởi đầu để chỉnh, KHÔNG phải số cuối)."""
import os, sys, csv, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.data import Data
from sim.rng import PCG32
from sim.model import new_member, auto_gear
from sim.offline import fast_forward
from sim.raid import simulate_raid

D = Data()
QUICK = "--quick" in sys.argv
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")
os.makedirs(OUT, exist_ok=True)
W1_SCHOOLS = [s["id"] for s in D.schools.values() if s["wave"] == "1"]
STD_PARTY = ["tho_1", "moc_1", "kim_2", "hoa_2", "thuy_1"]


def pick_ground(level):
    """Bãi khó nhất mà level_min ≤ level ≤ level_max."""
    c = [g for g in D.grounds.values() if int(g["level_min"]) <= level <= int(g["level_max"])
         and int(D.zones[g["zone_id"]]["rebirth_req"]) == 0]
    if not c:
        c = [g for g in D.grounds.values() if int(g["level_max"]) >= level]
        c.sort(key=lambda g: int(g["level_min"]))
        return c[0]["id"]
    return max(c, key=lambda g: int(g["level_min"]))["id"]


def pick_ground_any(level):
    """Bãi dùng cho level cao (kể cả vùng cần chuyển sinh): bãi đầu tiên có level_max ≥ level."""
    c = sorted(D.grounds.values(), key=lambda g: int(g["level_min"]))
    c = [g for g in c if int(g["level_max"]) >= level]
    return (c[0] if c else max(D.grounds.values(), key=lambda g: int(g["level_min"])))["id"]


def ladder(schools, pa, seed, target=100, step_h=1.0, max_h=24 * 90, start=1, rebirth=0):
    party = [new_member(D, i, s, pa, level=start, rebirth=rebirth) for i, s in enumerate(schools)]
    rng = PCG32(seed)
    h, curve = 0.0, []
    milestones = {}
    while party[0].level < target and h < max_h:
        lv = int(sum(m.level for m in party) / len(party))
        fast_forward(party, pick_ground(lv) if start == 1 else pick_ground_any(lv), step_h * 3600, D, rng, chunk_s=step_h * 3600, trips=6)
        h += step_h
        mean_lv = sum(m.level for m in party) / len(party)
        for t in (10, 25, 50, 75, 100):
            if mean_lv >= t and t not in milestones:
                milestones[t] = h
        if int(h) % 6 == 0:
            curve.append((h, round(mean_lv, 1), round(sum(m.gold for m in party) / len(party))))
    deaths = sum(m.deaths for m in party)
    return {"hours": h, "milestones": milestones, "curve": curve, "deaths": deaths,
            "kills": sum(m.kills for m in party), "gold": sum(m.gold_total for m in party) / len(party),
            "level": sum(m.level for m in party) / len(party)}


def fmt_days(h):
    return f"{h:.0f} giờ" if h < 72 else f"{h / 24:.1f} ngày"


lines = ["# Báo cáo cân bằng (balance_sim) — điểm khởi đầu, chưa phải số cuối\n",
         "Giả định: nhân vật AFK 24/7 (không tính giờ ngủ/đóng app), trang bị common theo level mua bằng vàng tự kiếm, "
         "không có thuốc/đồ ăn/kỹ năng thật (kỹ năng gộp vào hệ số), không có sự kiện, không có công trình buff. "
         "Mọi con số dùng để SO SÁNH tương đối giữa phái/PA/đội, không dùng như thời gian chơi thật.\n"]

# 1. solo theo phái
lines.append("## 1. Solo, PA 100: thời gian đạt level 100\n")
lines.append("| Phái | Vai trò | Lv10 | Lv25 | Lv50 | Lv75 | Lv100 | Chết | Vàng TB |\n|---|---|---|---|---|---|---|---|---|")
rows_csv = [["scenario", "school", "pa", "hours_lv10", "hours_lv25", "hours_lv50", "hours_lv75", "hours_lv100", "deaths"]]
schools_for = W1_SCHOOLS if not QUICK else W1_SCHOOLS[:2]
for sc in schools_for:
    r = ladder([sc], 100, 7)
    ms = r["milestones"]
    lines.append(f"| {sc} | {D.schools[sc]['role']} | " + " | ".join(
        fmt_days(ms[t]) if t in ms else "—" for t in (10, 25, 50, 75, 100)) + f" | {r['deaths']} | {r['gold']:.0f} |")
    rows_csv.append(["solo", sc, 100] + [round(ms.get(t, -1), 1) for t in (10, 25, 50, 75, 100)] + [r["deaths"]])

# 2. đội chuẩn và PA
lines.append("\n## 2. Đội chuẩn 5 người (tank + buffer + 3 dps), ảnh hưởng của PA\n")
lines.append("| PA | Lv25 | Lv50 | Lv100 | Chết | Giết |\n|---|---|---|---|---|---|")
for pa in ((40, 100, 160) if not QUICK else (100,)):
    r = ladder(STD_PARTY, pa, 11)
    ms = r["milestones"]
    lines.append(f"| {pa} | " + " | ".join(fmt_days(ms[t]) if t in ms else "—" for t in (25, 50, 100)) +
                 f" | {r['deaths']} | {r['kills']} |")
    rows_csv.append(["party5", "+".join(STD_PARTY), pa] + [round(ms.get(t, -1), 1) for t in (10, 25, 50, 75, 100)] + [r["deaths"]])

# 3. đội thiếu buffer
lines.append("\n## 3. Đội thiếu buffer (4 người không có `moc_1`)\n")
no_buf = ["tho_1", "kim_2", "hoa_2", "thuy_1"]
r_with = ladder(STD_PARTY, 100, 21, target=50)
r_without = ladder(no_buf, 100, 21, target=50)
lines.append(f"- Có buffer (5 người): Lv50 sau {fmt_days(r_with['milestones'].get(50, r_with['hours']))}, chết {r_with['deaths']}")
lines.append(f"- Không buffer (4 người): Lv50 sau {fmt_days(r_without['milestones'].get(50, r_without['hours']))}, chết {r_without['deaths']}")

# 4. raid
def make_guild(n, level):
    ms = []
    for i in range(n):
        m = new_member(D, i, STD_PARTY[i % 5], 100, level=max(1, level))
        m.gold = 1e12
        auto_gear(m, D)
        ms.append(m)
    return ms


def raid_cell(gb, n, ratio, seeds):
    """ratio = level bang / level boss."""
    L = int(D.monsters[gb["monster_id"]]["level"])
    offset = round(L * ratio) - L
    wins, tsum, dsum = 0, 0.0, 0
    for sd in range(seeds):
        res = simulate_raid(make_guild(n, L + offset), gb["id"], D, PCG32(100 + sd))
        wins += res.win
        tsum += res.time_s
        dsum += res.deaths
    return f"{100 * wins // seeds}% ({tsum / seeds:.0f}s, {dsum / seeds:.1f} chết)"


seeds = 3 if QUICK else 6
bosses = [b for b in D.bosses.values() if b["wave"] == "1"]
sample = bosses[:4] if QUICK else bosses
lines.append("\n## 4. Raid Boss Hoàng Kim cả bang (boss Wave 1)\n")
lines.append("Bang 5 phái Wave 1 xoay vòng, trang bị common theo level. Ô: tỉ lệ thắng (thời gian TB, số người chết TB).\n")
lines.append("**4a. Bang 20 người, level bang = tỉ lệ × level boss:**\n")
lines.append("| Boss | Lv | 100% | 90% | 80% | 70% | 60% |\n|---|---|---|---|---|---|---|")
for gb in sample:
    L = int(D.monsters[gb["monster_id"]]["level"])
    lines.append(f"| {gb['id']} | {L} | " + " | ".join(raid_cell(gb, 20, o, seeds) for o in (1.0, 0.9, 0.8, 0.7, 0.6)) + " |")
lines.append("\n**4b. Số thành viên, level bang = 85% level boss:**\n")
lines.append("| Boss | N=5 | N=10 | N=20 | N=30 |\n|---|---|---|---|---|")
for gb in sample:
    lines.append(f"| {gb['id']} | " + " | ".join(raid_cell(gb, n, 0.85, seeds) for n in (5, 10, 20, 30)) + " |")

# 5. kinh tế
from sim.offline import estimate_rates
from sim.model import Member
lines.append("\n## 5. Kinh tế một hunter solo (vàng/giờ so với giá bộ trang bị common)\n")
lines.append("| Level | Bãi | Vàng/giờ | Giá 4 món common | Giờ kiếm đủ 1 bộ | XP/giờ → quái/giờ |\n|---|---|---|---|---|---|")
for L in (10, 30, 50, 70, 90, 110):
    g = pick_ground(L) if L <= 100 else "g_z11_2"
    m = new_member(D, 1, "kim_2", 100, level=L)
    m.gold = 1e12
    auto_gear(m, D)
    m.gold = 0
    price = sum(int(D.items[i]["price"]) for i in m.equipment.values())
    rx, rg, rk, rd = estimate_rates([m], g, D, PCG32(5), trips=12)[1]
    lines.append(f"| {L} | {g} | {rg * 3600:,.0f} | {price:,} | {price / (rg * 3600):.1f} | {rk * 3600:.0f} quái/giờ |")
bsum = 0
with open(os.path.join(os.path.dirname(OUT), "data", "buildings.csv"), encoding="utf8", newline="") as f:
    for r in csv.DictReader(f):
        bsum += int(r["cost_gold"])
lines.append(f"\nTổng vàng để xây/nâng cấp MỌI công trình lên tối đa: {bsum:,}. Nếu bang thu thuế 10% thu nhập "
             f"của 20 hunter ở level 70 (≈ 20 × vàng/giờ × 10%), cần số giờ ≈ xem cột vàng/giờ ở trên.")

# 6. nhịp theo chuyển sinh
lines.append("\n## 6. Nhịp theo chuyển sinh (đội chuẩn, PA 100, AFK 24/7)\n")
lines.append(f"Đầu game nhanh: hệ số XP {D.cfg['xp_early_floor']} tại level 1 tăng tuyến tính tới 1.0 tại level {D.cfg['xp_early_end']:.0f}; "
             "mỗi lần chuyển sinh nhân XP cần thêm `xp_rebirth_mult_n`.\n")
lines.append("| Giai đoạn | Level | Hệ số XP | Thời gian |\n|---|---|---|---|")
r0 = ladder(STD_PARTY, 100, 31, target=100)
lines.append(f"| Mới | 1→100 | ×{D.cfg['xp_rebirth_mult_0']:g} | {fmt_days(r0['hours'])} |")
rows_csv.append(["rebirth_stage", "r0", 100, -1, -1, -1, -1, round(r0["hours"], 1), r0["deaths"]])
tot = r0["hours"]
for rb, (a, b) in enumerate([(100, 120), (120, 140), (140, 160), (160, 180), (180, 200)], start=1):
    if QUICK and rb > 2:
        break
    r = ladder(STD_PARTY, 100, 31 + rb, target=b, start=a, rebirth=rb, max_h=24 * 400)
    tot += r["hours"]
    lines.append(f"| Chuyển sinh {rb} | {a}→{b} | ×{D.cfg['xp_rebirth_mult_%d' % rb]:g} | {fmt_days(r['hours'])} |")
    rows_csv.append(["rebirth_stage", f"r{rb}", 100, -1, -1, -1, -1, round(r["hours"], 1), r["deaths"]])
lines.append(f"\nTổng tới mốc đã chạy: {fmt_days(tot)} AFK 24/7. Người chơi thật chỉ online/offline-cap một phần ngày nên thực tế dài gấp ~2–4 lần.")

# 7. tiêu vàng
from sim import economy as ECO
tbl = ECO.load_enhance()
lines.append("\n## 7. Hệ thống tiêu vàng (mô hình giải tích)\n")
lines.append(f"Thu nhập tham chiếu ≈ {D.cfg['income_ref_per_level']:g} × level vàng/giờ/người (đo ở mục 5). "
             f"Thuốc {D.cfg['potion_use_per_hour']:g}/giờ + tiệc + rượu (giá 14·L / 90·L / 70·L).\n")
lines.append("| Level | Thu/giờ | Chi thuốc+buff/giờ | % thu nhập | Phí duy trì bang/người/ngày |\n|---|---|---|---|---|")
for L in (10, 30, 50, 100, 150, 200):
    inc = ECO.income_per_hour(L, D.cfg)
    up = ECO.upkeep_per_hour(L, D.cfg)
    lines.append(f"| {L} | {inc:,.0f} | {up:,.0f} | {100 * up / inc:.0f}% | {D.cfg['guild_upkeep_per_level_day'] * L:,.0f} |")
lines.append("\nCường hoá (kỳ vọng vàng để từ +0 lên +N, tính bằng GIỜ thu nhập của người đó, mỗi món; bùa hộ cường tính 20,000 vàng/lần):\n")
lines.append("| Mục tiêu | Không bùa | Có bùa | Chỉ số cộng |\n|---|---|---|---|")
for tg in (5, 8, 10, 12, 15, 20):
    a = ECO.enhance_expected_cost(100, tg, D.cfg, tbl) / ECO.income_per_hour(100, D.cfg)
    b = ECO.enhance_expected_cost(100, tg, D.cfg, tbl, ward=True, ward_cost=20000) / ECO.income_per_hour(100, D.cfg)
    lines.append(f"| +{tg} | {a:,.1f} giờ | {b:,.1f} giờ | +{100 * ECO.stat_bonus(tg, tbl):.0f}% |")
lines.append("\n(Chi phí tỉ lệ thuận với level nên số giờ như nhau ở mọi level; bùa là giá cố định nên rẻ dần ở level cao.)")

with open(os.path.join(OUT, "balance_report.md"), "w", encoding="utf8") as f:
    f.write("\n".join(lines) + "\n")
with open(os.path.join(OUT, "balance_summary.csv"), "w", encoding="utf8", newline="") as f:
    csv.writer(f).writerows(rows_csv)
print("\n".join(lines))
