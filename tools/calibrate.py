#!/usr/bin/env python3
"""Quét tham số để hunter solo đúng level có nhịp chiến đấu ổn định qua các level.
Mục tiêu: 8–16 quái/chuyến, tỉ lệ chết < 3%, thời gian hạ 1 quái 6–25 giây."""
import os, sys, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.data import Data
from sim.rng import PCG32
from sim.model import new_member, auto_gear
from sim.hunt import run_trip, fight

LEVELS = [(5, "g_z01_2"), (15, "g_z02_2"), (30, "g_z03_3"), (50, "g_z05_3"), (70, "g_z07_3"), (90, "g_z09_3"), (110, "g_z11_2")]
SCHOOLS = ["kim_2", "hoa_2", "tho_1"]


def evaluate(d, hp_exp, factor, trips=12):
    d.cfg["monster_hp_exp"] = hp_exp
    d.sim["monster_dmg_factor"] = factor
    rows = []
    for L, g in LEVELS:
        kills = tot = dead = 0
        ttk = []
        for sc in SCHOOLS:
            m = new_member(d, 1, sc, 100, level=L)
            m.gold = 1e12
            auto_gear(m, d)
            m.gold = 0
            rng = PCG32(11 + L)
            for _ in range(trips):
                r = run_trip([m], g, d, rng)
                kills += r.kills
                tot += 1
                dead += r.deaths
            for mon in d.ground_monsters(g):
                if mon["is_boss"] != "true":
                    m.hp = m.stats(d)["hp_max"]
                    ok, t, _ = fight([m], mon, d, PCG32(5))
                    ttk.append(t)
                    m.alive = True
                    m.hp = m.stats(d)["hp_max"]
        rows.append((L, kills / tot, dead / tot, sum(ttk) / len(ttk)))
    return rows


if __name__ == "__main__":
    d = Data()
    best = []
    for hp_exp, f in itertools.product([1.25, 1.3, 1.35, 1.4, 1.5, 1.6], [0.01, 0.015, 0.02, 0.03, 0.05]):
        rows = evaluate(d, hp_exp, f, trips=6)
        kp = [r[1] for r in rows]
        score = sum(1 for r in rows if 8 <= r[1] <= 16 and r[2] < 0.03 and 6 <= r[3] <= 25)
        best.append((score, -max(abs(k - 12) for k in kp), hp_exp, f, [round(k, 1) for k in kp], [round(r[3]) for r in rows]))
    best.sort(reverse=True)
    for b in best[:8]:
        print(b)
