"""Mô hình kinh tế giải tích (chưa nhúng vào chiến đấu): thu nhập tham chiếu, tiêu hao, cường hoá, thuế/phí bang."""
import csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_enhance(root=ROOT):
    with open(os.path.join(root, "data", "enhance.csv"), encoding="utf8", newline="") as f:
        return [{"level": int(r["level"]), "p": float(r["success_pct"]) / 100, "cost": float(r["cost_mult"]),
                 "drop": r["fail_effect"] == "drop_1", "stat": float(r["stat_pct_total"])} for r in csv.DictReader(f)]


def income_per_hour(level, cfg):
    return cfg["income_ref_per_level"] * level


def upkeep_per_hour(level, cfg, use_feast=True, use_brew=True):
    """Chi phí thuốc + buff ăn/uống mỗi giờ cho 1 người (giá theo công thức gen_c: pot_hp 14·L, feast 90·L, brew 70·L)."""
    c = cfg["potion_use_per_hour"] * 14 * level
    if use_feast:
        c += cfg["feast_use_per_hour"] * 90 * level
    if use_brew:
        c += cfg["brew_use_per_hour"] * 70 * level
    return c


def enhance_attempt_cost(item_level, to_level, cfg, table):
    return cfg["enhance_base_per_level"] * max(1, item_level) * table[to_level - 1]["cost"]


def enhance_expected_cost(item_level, target, cfg, table, ward=False, ward_cost=0.0):
    """Kỳ vọng vàng để từ +0 lên +target, mô phỏng chuỗi Markov (thất bại ≥+6 tụt 1 cấp trừ khi dùng bùa).
    Tính chính xác bằng giải hệ tuyến tính đệ quy theo cấp: E[n] = chi phí từ n-1 lên n khi đang ở n-1."""
    # e[n]: kỳ vọng chi phí để từ cấp n-1 lên cấp n (lần đầu), giả sử đang ở n-1.
    e = []
    for n in range(1, target + 1):
        row = table[n - 1]
        cost, p = enhance_attempt_cost(item_level, n, cfg, table), row["p"]
        if ward:
            cost += ward_cost
        # thất bại: ở n-1 và (nếu drop & không ward) rớt xuống n-2 rồi phải leo lại e[n-2] bước
        back = e[n - 2] if (row["drop"] and not ward and n >= 2) else 0.0
        # E = cost + (1-p)·(back + E)  =>  E = (cost + (1-p)·back) / p
        e.append((cost + (1 - p) * back) / p)
    return sum(e)


def stat_bonus(level, table):
    return table[level - 1]["stat"] if level > 0 else 0.0
