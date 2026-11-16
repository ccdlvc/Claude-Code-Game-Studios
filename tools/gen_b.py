#!/usr/bin/env python3
"""Sinh dữ liệu (b): skill 5 phái Wave 2, quái/bãi/boss vùng 12–15, rebirth.csv, tên.
Chạy: python3 -I tools/gen_b.py. Chạy lại là idempotent (bỏ dòng cũ cùng id rồi thêm lại)."""
import csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name, folder="data"):
    with open(os.path.join(ROOT, folder, name), encoding="utf8", newline="") as f:
        r = csv.reader(f)
        head = next(r)
        return head, [dict(zip(head, row)) for row in r]


def write(name, head, rows, folder="data"):
    with open(os.path.join(ROOT, folder, name), "w", encoding="utf8", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        for r in rows:
            w.writerow([r[h] if isinstance(r, dict) else r[i] for i, h in enumerate(head)] if isinstance(r, dict) else r)
    print(f"{folder}/{name}: {len(rows)} dòng")


def upsert(head, rows, new_rows, key="id"):
    ids = {r[key] for r in new_rows}
    kept = [r for r in rows if r[key] not in ids]
    return kept + new_rows


# ---------- skills Wave 2 ----------
_, schools = read("schools.csv")
school = {s["id"]: s for s in schools}
SK_HEAD, skills = read("skills.csv")
# (type, mp, cd, range, target, effects)
SPEC = {
    "kim_1": [
        ("active", 5, 8, "short_range", "enemy_aoe", "taunt_s=3;aggro=120"),
        ("active", 12, 14, "self", "self", "dmg_taken=-0.25;reflect_pct=0.2+0.01*L;dur_s=6"),
        ("active", 18, 16, "melee", "enemy", "dmg_mult=1.3+0.05*L;armor_break=0.05*L;dur_s=6"),
        ("active", 25, 18, "melee", "enemy_aoe", "aoe_radius=2.5;knockback=2;stun_s=1;dmg_mult=1.0+0.04*L"),
        ("passive", 0, 0, "self", "self", "def_pct=0.025*L"),
        ("passive", 0, 0, "self", "self", "reflect_pct=0.015*L"),
        ("passive", 0, 0, "self", "self", "hp_pct=0.02*L"),
        ("passive", 0, 0, "self", "self", "aggro_gain=0.03*L;cc_resist=0.01*L"),
        ("ultimate", 50, 60, "self", "party", "dmg_taken_party=-0.4;reflect_pct=0.3;dur_s=8"),
        ("ultimate", 90, 120, "self", "enemy_aoe", "taunt_s=6;stun_s=2;aoe_radius=4;dmg_mult=2.5+0.06*L"),
        ("secret", 0, 0, "self", "self", "shield_on_hit_pct=0.02*L;shield_cap_pct=0.25"),
        ("secret", 0, 0, "self", "self", "last_stand_def=0.5;below_hp=0.3"),
    ],
    "moc_2": [
        ("active", 6, 2, "ranged", "enemy", "dmg_mult=0.9+0.04*L;poison_stack=1;poison_per_s=0.1+0.01*L;dur_s=6"),
        ("active", 14, 9, "ranged", "enemy_aoe", "aoe_radius=2.5;def_shred=0.05+0.005*L;dur_s=8"),
        ("active", 22, 12, "ranged", "ground_aoe", "aoe_radius=3;dur_s=8;poison_per_s=0.2+0.01*L;slow_pct=0.15"),
        ("active", 28, 16, "ranged", "enemy", "wither=1;heal_received=-0.3;atk_down=0.1+0.005*L;dur_s=8"),
        ("passive", 0, 0, "self", "self", "poison_dmg=0.03*L"),
        ("passive", 0, 0, "self", "self", "poison_stack_max=1;crit_rate=0.005*L"),
        ("passive", 0, 0, "self", "self", "def_ignore_vs_poisoned=0.02*L"),
        ("passive", 0, 0, "self", "self", "dot_tick_speed=0.01*L"),
        ("ultimate", 60, 45, "ranged", "enemy", "poison_burst=3+0.1*L;consume_stacks=1"),
        ("ultimate", 100, 100, "ranged", "enemy_aoe", "aoe_radius=5;dur_s=10;poison_per_s=0.5+0.02*L;def_shred=0.2"),
        ("secret", 0, 0, "self", "self", "poison_spread_on_death=1;spread_radius=3"),
        ("secret", 0, 0, "self", "self", "poison_stack_max=3;poison_dmg_pct=0.1*L"),
    ],
    "thuy_2": [
        ("active", 8, 3, "ranged", "ally", "mp_restore=10+1.5*L"),
        ("active", 14, 12, "ranged", "party", "buff_atk_pct=0.06+0.006*L;dur_s=25"),
        ("active", 20, 14, "ranged", "party", "buff_speed_pct=0.08+0.004*L;buff_dodge=0.05;dur_s=20"),
        ("active", 28, 20, "ranged", "party", "cleanse=1;shield_pct=0.1+0.005*L;dur_s=6"),
        ("passive", 0, 0, "self", "self", "mp_regen=0.04*L"),
        ("passive", 0, 0, "self", "self", "buff_dur_pct=0.015*L"),
        ("passive", 0, 0, "self", "self", "party_mp_regen=0.01*L"),
        ("passive", 0, 0, "self", "self", "buff_power_pct=0.01*L"),
        ("ultimate", 60, 90, "ranged", "party", "buff_atk_pct=0.15;buff_def_pct=0.15;dur_s=12"),
        ("ultimate", 110, 120, "ranged", "party", "mp_restore_pct=0.5;cd_reset_pct=0.3"),
        ("secret", 0, 0, "self", "self", "overbuff_cap=0.1;buff_dur_pct=0.2"),
        ("secret", 0, 0, "self", "self", "auto_cleanse_party=1;cd_s=45"),
    ],
    "hoa_1": [
        ("active", 5, 1.5, "melee", "enemy", "dmg_mult=1.2+0.05*L;burn_per_s=0.08+0.005*L;dur_s=3"),
        ("active", 12, 6, "melee", "enemy", "hits=4;dmg_mult=0.55+0.03*L"),
        ("active", 18, 10, "melee", "enemy_aoe", "aoe_radius=2;dmg_mult=1.2+0.05*L;burn_per_s=0.15+0.01*L;dur_s=4"),
        ("active", 25, 14, "gap_close", "enemy", "dash=4;dmg_mult=2.0+0.06*L;stun_s=0.8"),
        ("passive", 0, 0, "self", "self", "atk_pct=0.02*L"),
        ("passive", 0, 0, "self", "self", "burn_dmg=0.03*L"),
        ("passive", 0, 0, "self", "self", "atk_speed=0.01*L"),
        ("passive", 0, 0, "self", "self", "on_burn_kill_heal_pct=0.01*L;crit_rate=0.005*L"),
        ("ultimate", 50, 35, "melee", "enemy", "hits=6;dmg_mult=0.9+0.03*L;burn_per_s=0.3"),
        ("ultimate", 100, 90, "melee", "enemy_aoe", "aoe_radius=4;dmg_mult=5.0+0.1*L;burn_per_s=0.5;dur_s=6"),
        ("secret", 0, 0, "self", "self", "burn_stack_max=3;burn_dmg_pct=0.05*L"),
        ("secret", 0, 0, "self", "self", "burn_explode_on_kill=1;explode_dmg_pct=0.2*L"),
    ],
    "tho_2": [
        ("active", 8, 10, "ground", "ground", "trap_dmg_mult=1.0+0.05*L;root_s=1.5;dur_s=15"),
        ("active", 15, 18, "self", "self", "summon=stone_guard;summon_hp_mult=1.0+0.1*L;dur_s=20"),
        ("active", 22, 14, "ranged", "ground_aoe", "aoe_radius=3;stun_s=1.2;dmg_mult=1.0+0.04*L"),
        ("active", 30, 25, "ranged", "ground", "formation=ward;dmg_taken_ally=-0.15;dur_s=12;radius=3"),
        ("passive", 0, 0, "self", "self", "summon_power=0.03*L"),
        ("passive", 0, 0, "self", "self", "trap_dmg=0.03*L"),
        ("passive", 0, 0, "self", "self", "control_dur_pct=0.015*L"),
        ("passive", 0, 0, "self", "self", "summon_cd_reduction=0.01*L"),
        ("ultimate", 60, 60, "ranged", "ground_aoe", "formation=sealed_field;stun_s=3;aoe_radius=4;dmg_mult=2.0+0.06*L"),
        ("ultimate", 100, 120, "self", "self", "summon=earth_titan;summon_hp_mult=4.0+0.1*L;dur_s=25"),
        ("secret", 0, 0, "self", "self", "summon_count=1"),
        ("secret", 0, 0, "self", "self", "trap_chain=1;trap_chain_radius=3"),
    ],
}
LV = [1, 10, 20, 30, 5, 15, 25, 40, 60, 100, 100, 140]
MAXLV = [20] * 4 + [10] * 8
RB = [0] * 10 + [1, 3]
PREREQ = {1: "", 2: "{p}01:3", 3: "{p}02:5", 4: "{p}03:5", 5: "", 6: "{p}05:3", 7: "{p}06:3", 8: "{p}07:5",
          9: "{p}04:10", 10: "{p}09:10", 11: "{p}10:1", 12: "{p}11:5"}
new = []
for sid, spec in SPEC.items():
    assert len(spec) == 12 and school[sid]["wave"] == "2", sid
    p = f"sk_{sid.replace('_', '')}_"
    for slot, (typ, mp, cd, rng, tgt, eff) in enumerate(spec, start=1):
        new.append({"id": f"{p}{slot:02d}", "school_id": sid, "slot": str(slot), "type": typ, "lv_req": str(LV[slot - 1]),
                    "rebirth_req": str(RB[slot - 1]), "max_lv": str(MAXLV[slot - 1]), "mp_cost": str(mp),
                    "cooldown_s": str(cd).rstrip("0").rstrip(".") if "." in str(cd) else str(cd), "range": rng,
                    "target": tgt, "element": school[sid]["element"], "effects": eff,
                    "prereq": PREREQ[slot].format(p=p), "unlock_wave": "2"})
skills = upsert(SK_HEAD, skills, new)
order = {s["id"]: i for i, s in enumerate(schools)}
skills.sort(key=lambda r: (order[r["school_id"]], int(r["slot"])))
write("skills.csv", SK_HEAD, [[r[h] for h in SK_HEAD] for r in skills])

# ---------- monsters / zones / grounds / golden bosses (vùng 12–15) ----------
M_HEAD, monsters = read("monsters.csv")
# zone, [(suffix, level, element, role, hp, atk, def, spd, skills)], boss(level, element, hp, atk, def, spd, skills)
Z = {
    12: ([("a", 122, "moc", "melee", 1.2, 1.3, 1.1, 1.1, "claw;pounce"),
          ("b", 127, "moc", "swarm", 0.9, 1.2, 0.9, 1.2, "bite;swarm_rush"),
          ("c", 133, "tho", "tank", 1.8, 1.2, 1.7, 0.8, "slam;roar"),
          ("d", 138, "moc", "caster", 1.1, 1.6, 1.0, 1.0, "thorn_burst;root_snare")],
         (140, "kim", 18, 2.0, 1.6, 1.2, "leap_strike;bleed;enrage_30pct")),
    13: ([("a", 142, "thuy", "melee", 1.3, 1.4, 1.2, 1.1, "pincer;water_jet"),
          ("b", 148, "thuy", "tank", 1.9, 1.3, 1.8, 0.8, "shell_bash;tidal_slam"),
          ("c", 154, "thuy", "caster", 1.1, 1.7, 1.0, 1.0, "ink_cloud;drown_touch"),
          ("d", 158, "hoa", "ranged", 1.1, 1.7, 1.0, 1.1, "vent_blast")],
         (160, "thuy", 18, 2.0, 1.6, 1.0, "tentacle_sweep;ink_blind;summon_adds")),
    14: ([("a", 162, "kim", "melee", 1.3, 1.5, 1.3, 1.1, "stone_claw;lunge"),
          ("b", 168, "tho", "tank", 2.0, 1.4, 1.9, 0.8, "stone_slam;guard"),
          ("c", 174, "hoa", "caster", 1.1, 1.8, 1.0, 1.0, "ember_curse;flame_wave"),
          ("d", 178, "kim", "ranged", 1.1, 1.8, 1.0, 1.2, "shard_throw")],
         (180, "tho", 20, 2.1, 1.7, 0.9, "stomp_stun;armor_phase;summon_adds")),
    15: ([("a", 182, "hoa", "melee", 1.4, 1.6, 1.3, 1.1, "legend_flame;lunge"),
          ("b", 188, "thuy", "caster", 1.2, 1.9, 1.1, 1.0, "legend_tide;drown_touch"),
          ("c", 194, "tho", "tank", 2.2, 1.5, 2.0, 0.8, "legend_guard;slam"),
          ("d", 198, "moc", "ranged", 1.2, 1.9, 1.1, 1.2, "legend_thorn;root_snare")],
         (200, "hoa", 22, 2.2, 1.8, 1.1, "dragon_breath;flood_phase;enrage_30pct")),
}
new_m = []
for n, (norm, boss) in Z.items():
    zn = f"{n:02d}"
    for suf, lv, el, role, hp, atk, df, spd, sk in norm:
        new_m.append({"id": f"m_z{zn}_{suf}", "zone_id": f"zone_{zn}", "level": str(lv), "element": el, "role": role,
                      "hp_mult": str(hp), "atk_mult": str(atk), "def_mult": str(df), "speed": str(spd), "ai_skills": sk,
                      "drop_table": f"drop_zone_{zn}", "is_boss": "false"})
    lv, el, hp, atk, df, spd, sk = boss
    new_m.append({"id": f"m_z{zn}_boss", "zone_id": f"zone_{zn}", "level": str(lv), "element": el, "role": "boss",
                  "hp_mult": str(hp), "atk_mult": str(atk), "def_mult": str(df), "speed": str(spd), "ai_skills": sk,
                  "drop_table": f"drop_zone_{zn}_boss", "is_boss": "true"})
monsters = upsert(M_HEAD, monsters, new_m)
zorder = lambda r: (int(r["zone_id"].split("_")[1]), r["is_boss"] == "true", r["level"].zfill(3))
monsters.sort(key=zorder)
write("monsters.csv", M_HEAD, [[r[h] for h in M_HEAD] for r in monsters])

Z_HEAD, zones = read("zones.csv")
THEME = {12: "primeval_forest", 13: "deep_sea", 14: "fallen_palace", 15: "realm_of_legends"}
for z in zones:
    n = int(z["order"])
    if n in Z:
        z["boss_monster_id"] = f"m_z{n:02d}_boss"
        z["theme"] = THEME[n]
write("zones.csv", Z_HEAD, [[r[h] for h in Z_HEAD] for r in zones])

G_HEAD, grounds = read("grounds.csv")
new_g = []
for n in Z:
    z = next(x for x in zones if int(x["order"]) == n)
    lo, hi = int(z["level_min"]), int(z["level_max"])
    cuts = [(lo, lo + 8, "a", "b", 6, 1), (lo + 6, lo + 14, "b", "c", 8, 2), (lo + 12, hi, "c", "d", 10, 3)]
    for i, (a, b, m1, m2, cap, dg) in enumerate(cuts, start=1):
        new_g.append({"id": f"g_z{n:02d}_{i}", "zone_id": z["id"], "level_min": str(a), "level_max": str(b),
                      "capacity": str(cap), "spawn_rate": "1.0", "monster_pool": f"m_z{n:02d}_{m1};m_z{n:02d}_{m2}",
                      "danger": str(dg)})
grounds = upsert(G_HEAD, grounds, new_g)
grounds.sort(key=lambda r: (r["zone_id"], r["id"]))
write("grounds.csv", G_HEAD, [[r[h] for h in G_HEAD] for r in grounds])

B_HEAD, bosses = read("golden_bosses.csv")
GB = {12: ("kim", 7, "leap_strike;bleed;enrage_30pct", 2), 13: ("thuy", 7, "tentacle_sweep;ink_blind;summon_adds", 2),
      14: ("tho", 8, "stomp_stun;armor_phase;summon_adds", 3), 15: ("hoa", 8, "dragon_breath;flood_phase;enrage_30pct", 3)}
new_b = [{"id": f"gb_{n:02d}", "monster_id": f"m_z{n:02d}_boss", "element": el, "min_guild_lv": str(g),
          "hp_per_participant": "0.10", "loot_table": f"loot_gb_{n:02d}", "mechanics": mech, "wave": str(w)}
         for n, (el, g, mech, w) in GB.items()]
bosses = upsert(B_HEAD, bosses, new_b)
bosses.sort(key=lambda r: r["id"])
write("golden_bosses.csv", B_HEAD, [[r[h] for h in B_HEAD] for r in bosses])

# ---------- chuyển sinh ----------
RB_HEAD = ["no", "kind", "req_level", "new_level_cap", "skill_keep_pct", "pill_cost", "gold_cost", "rewards", "wave"]
write("rebirth.csv", RB_HEAD, [
    [1, "rebirth", 100, 120, 50, 1, 0, "trait_slot_reveal=1;unlock_secret=1;free_school_change=1;xp_pct=0.10", 1],
    [2, "rebirth", 120, 140, 55, 2, 200000, "unlock_tower_high=1;growth_bonus=0.05", 2],
    [3, "rebirth", 140, 160, 60, 3, 1000000, "unlock_secret=2;drop_rate=0.05", 2],
    [4, "rebirth", 160, 180, 65, 4, 5000000, "trait_slot_reveal=1;xp_pct=0.10", 3],
    [5, "rebirth", 180, 200, 70, 5, 20000000, "unlock_ascension=1", 3],
    [6, "ascension", 200, 200, 100, 0, 50000000, "become_elder=1;ca_min=180;guild_buff_by_school=1", 3],
])

# ---------- tên ----------
BOSS_NAME = {
    "m_z12_boss": (("Bạch Hổ Nghìn Năm", "Bạch Hổ", "Con hổ trắng sống nghìn năm trong rừng nguyên sinh."),
                   ("Millennium White Tiger", "White Tiger", "A white tiger a thousand years old in the primeval forest.")),
    "m_z13_boss": (("Cự Tuộc Đông Hải", "Cự Tuộc", "Con mực khổng lồ dưới vực biển sâu."),
                   ("Giant Cephalopod of the Eastern Sea", "Cephalopod", "A giant squid in the deep sea trench.")),
    "m_z14_boss": (("Nghê Đá Cổ Đô", "Nghê Đá", "Tượng nghê bằng đá hoá thú canh giữ cung điện."),
                   ("Stone Nghe of the Old Capital", "Stone Nghe", "A stone guardian beast awakened to guard the palace.")),
    "m_z15_boss": (("Cổ Long Chúa", "Cổ Long", "Con rồng cổ trong cõi truyền thuyết."),
                   ("Ancient Dragon Lord", "Ancient Dragon", "An ancient dragon of the realm of legends.")),
}
ZONE_DESC = {
    "zone_12": (("Trường Sơn Nguyên Lâm", "Nguyên Lâm", "Rừng nguyên sinh rậm rạp; thú dữ và cây thành tinh."),
                ("Truong Son Primeval Forest", "Primeval Forest", "Dense primeval forest; fierce beasts and living trees.")),
    "zone_13": (("Đông Hải Thâm Uyên", "Thâm Uyên", "Vực biển sâu tối tăm; thuỷ quái khổng lồ."),
                ("Eastern Sea Abyss", "Sea Abyss", "A dark deep-sea trench; giant water monsters.")),
    "zone_14": (("Phế Cung Cổ Đô", "Phế Cung", "Cung điện hoang phế của kinh đô cũ; tượng đá hoá thú."),
                ("Fallen Palace of the Old Capital", "Fallen Palace", "The ruined palace of an old capital; statues come alive.")),
    "zone_15": (("Cõi Truyền Thuyết", "Truyền Thuyết", "Cõi huyền thoại nơi các linh vật cổ xưa ngự trị."),
                ("Realm of Legends", "Legends", "A mythical realm ruled by ancient creatures.")),
}
for lang, idx in (("vi", 0), ("en", 1)):
    head, rows = read(f"names_{lang}.csv", folder="i18n")
    by = {r["id"]: r for r in rows}
    for zid, d in ZONE_DESC.items():
        n, sh, ds = d[idx]
        by[zid].update(name=n, short=sh, desc=ds)
    newr = [{"id": k, "name": v[idx][0], "short": v[idx][1], "desc": v[idx][2]} for k, v in BOSS_NAME.items()]
    rows = upsert(head, rows, newr)
    write(f"names_{lang}.csv", head, [[r[h] for h in head] for r in rows], folder="i18n")
