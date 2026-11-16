from .data import ELEMENT_COUNTER, LEVEL_CAP


def monster_hp(L, mult, cfg):
    return cfg["monster_hp_coef"] * L ** cfg["monster_hp_exp"] * mult


def monster_atk(L, mult, cfg):
    return cfg["monster_atk_coef"] * L ** cfg["monster_atk_exp"] * mult


def monster_def(L, mult, cfg):
    return cfg["monster_def_coef"] * L ** cfg["monster_def_exp"] * mult


def xp_need(L, cfg, rebirth=0):
    """XP cần để lên cấp L. Đầu game nhanh (xp_early_floor → 1 tại xp_early_end),
    mỗi lần chuyển sinh chậm hơn (xp_rebirth_mult_<n>)."""
    base = cfg["xp_need_coef"] * L ** cfg["xp_need_exp"]
    early = cfg.get("xp_early_floor", 1.0)
    end = cfg.get("xp_early_end", 1.0)
    f = early + (1.0 - early) * min(1.0, L / end) if end > 0 else 1.0
    return base * f * cfg.get("xp_rebirth_mult_%d" % rebirth, 1.0)


def base_gold(L, cfg):
    return cfg["base_gold_coef"] * L ** cfg["base_gold_exp"]


def growth_mult(pa, cfg):
    return cfg["growth_mult_base"] + cfg["growth_mult_pa"] * (pa / cfg["pa_max"])


def element_mult(att, defn, cfg):
    """Hệ số sát thương của hệ `att` lên hệ `defn` (khắc / bị khắc / cùng hệ / trung tính)."""
    if ELEMENT_COUNTER.get(att) == defn:
        return cfg["element_counter_mult"]
    if ELEMENT_COUNTER.get(defn) == att:
        return cfg["element_countered_mult"]
    if att == defn:
        return cfg["element_same_mult"]
    return 1.0


def ca_value(level, rebirth, skill_norm, equip_norm, trait_norm, pa, cfg):
    """CA 0–200; vượt PA thì chỉ tăng nửa phần vượt (PA là trần mềm)."""
    l_norm = min(1.0, level / LEVEL_CAP[rebirth])
    raw = cfg["ca_max"] * (0.40 * l_norm + 0.25 * skill_norm + 0.25 * equip_norm + 0.10 * trait_norm)
    return raw if raw <= pa else pa + 0.5 * (raw - pa)


def party_xp_mult(n, has_buffer, has_tank, cfg):
    return 1 + cfg["party_xp_per_member"] * (n - 1) + (cfg["party_buffer_bonus"] if has_buffer else 0) \
        + (cfg["party_tank_bonus"] if has_tank else 0)
