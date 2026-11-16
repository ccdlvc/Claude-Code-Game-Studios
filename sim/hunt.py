from dataclasses import dataclass, field
from . import formulas as F
from .model import auto_gear


@dataclass
class TripResult:
    kills: int = 0
    time_s: float = 0.0
    deaths: int = 0
    reason: str = ""


def _k(level, s):
    return s["def_k_per_level"] * level + s["def_k_flat"]


def fight(party, mon, data, rng):
    """Một trận với 1 quái. Hướng sự kiện (không quét từng tick). Trả (thắng, thời_gian, đóng_góp)."""
    s, cfg = data.sim, data.cfg
    L = int(mon["level"])
    mhp = F.monster_hp(L, float(mon["hp_mult"]), cfg)
    hit = F.monster_atk(L, float(mon["atk_mult"]), cfg) * s["monster_dmg_factor"]
    mdef = F.monster_def(L, float(mon["def_mult"]), cfg)
    interval = 1.0 / float(mon["speed"])
    pf = _k(L, s) / (_k(L, s) + mdef)
    members = [m for m in party if m.alive and m.hp > 0]
    buff = any(m.is_buffer(data) for m in members)
    atk_bonus = s["buffer_atk"] if buff else 0.0
    dmg_red = s["buffer_dmg_reduction"] if buff else 0.0
    nxt = {m.id: rng.random() for m in members}
    mon_next = rng.random() * interval
    contrib = {m.id: 0.0 for m in members}
    t = 0.0
    while mhp > 0:
        alive = [m for m in members if m.alive and m.hp > 0]
        if not alive or t > 600:
            return False, t, contrib
        nm = min(alive, key=lambda m: nxt[m.id])
        if nxt[nm.id] <= mon_next:
            t = nxt[nm.id]
            nxt[nm.id] += 1.0
            st = nm.stats(data)
            if nm.role(data) == "healer_support":
                tgt = min(alive, key=lambda m: m.hp / m.stats(data)["hp_max"])
                if tgt.hp / tgt.stats(data)["hp_max"] < 0.8:
                    tgt.hp = min(tgt.stats(data)["hp_max"], tgt.hp + s["healer_heal_frac"] * tgt.stats(data)["hp_max"])
                    continue
            d = st["dps"] * (1 + atk_bonus) * F.element_mult(nm.element(data), mon["element"], cfg) \
                * (0.9 + 0.2 * rng.random()) * pf
            mhp -= d
            contrib[nm.id] += d
        else:
            t = mon_next
            mon_next += interval
            tanks = [m for m in alive if m.is_tank(data)]
            tgt = rng.choice(tanks) if tanks and rng.random() < s["tank_aggro_share"] else rng.choice(alive)
            ts = tgt.stats(data)
            dmg = hit * F.element_mult(mon["element"], tgt.element(data), cfg) * (1 - dmg_red) \
                * _k(L, s) / (_k(L, s) + ts["def"])
            tgt.hp -= dmg
            if tgt.hp <= 0:
                tgt.hp = 0.0
                tgt.alive = False
                tgt.deaths += 1
    return True, t, contrib


_equip_cache = {}


def _equip_pool(data, rarity, lo, hi):
    key = (id(data), rarity, lo, hi)
    if key not in _equip_cache:
        _equip_cache[key] = [i for i in data.items.values()
                             if i["kind"] == "equip" and i["rarity"] == rarity and lo <= int(i["level_req"]) <= hi]
    return _equip_cache[key]


def roll_drops(table_id, mon_level, data, rng, bag):
    """Trả (vàng, giá_trị_bán_vật_phẩm). `bag` = [số ô đã dùng]; mỗi đơn vị vật phẩm chiếm 1 ô."""
    s, cfg = data.sim, data.cfg
    gold = value = 0.0
    for d in data.drops[table_id]:
        if not rng.chance(float(d["chance"])):
            continue
        k = d["kind"]
        if k == "gold":
            gold += F.base_gold(mon_level, cfg) * (float(d["qty_min"]) + (float(d["qty_max"]) - float(d["qty_min"])) * rng.random())
        elif k == "material":
            q = rng.randint(int(float(d["qty_min"])), int(float(d["qty_max"])))
            bag[0] += q
            value += q * float(data.materials[d["ref"]]["base_price"]) * s["mat_sell_ratio"]
        elif k == "equip_pool":
            pool = _equip_pool(data, d["ref"], int(d["lv_min"]), int(d["lv_max"]))
            it = rng.choice(pool)
            bag[0] += 1
            value += float(it["price"]) * s["equip_sell_ratio"]
        else:
            bag[0] += 1
    return gold, value


def run_trip(party, ground_id, data, rng):
    s, cfg = data.sim, data.cfg
    pool = [m for m in data.ground_monsters(ground_id) if m["is_boss"] != "true"]
    members = [m for m in party if m.alive]
    n = len(party)
    xp_mult = F.party_xp_mult(n, any(m.is_buffer(data) for m in members), any(m.is_tank(data) for m in members), cfg)
    bag = [0]
    gold_pool = value_pool = 0.0
    r = TripResult()
    t = 0.0
    while True:
        alive = [m for m in members if m.alive]
        if not alive:
            r.reason = "wiped"
            break
        if min(m.hp / m.stats(data)["hp_max"] for m in alive) < s["flee_hp_pct"]:
            r.reason = "low_hp"
            break
        if bag[0] >= s["bag_slots"] * n:  # mỗi thành viên mang một túi riêng
            r.reason = "bag_full"
            break
        mon = rng.choice(pool)
        win, dur, _ = fight(party, mon, data, rng)
        t += dur + s["gap_s"]
        if not win:
            r.reason = "lost"
            break
        r.kills += 1
        L = int(mon["level"])
        base_xp = s["xp_kill_coef"] * L ** s["xp_kill_exp"]
        for m in alive:
            if not m.alive:
                continue
            diff = m.level - L
            f = 1.0 if diff <= s["lvl_diff_free"] else max(s["lvl_diff_min"], 1 - s["lvl_diff_penalty"] * (diff - s["lvl_diff_free"]))
            m.kills += 1
            m.gain_xp(base_xp * F.growth_mult(m.pa, cfg) * xp_mult * f / n, data)
        g, v = roll_drops(mon["drop_table"], L, data, rng, bag)
        gold_pool += g
        value_pool += v
    # về nhà: đi lại, bán đồ, nghỉ/hồi sinh
    rest = 0.0
    for m in members:
        if not m.alive:
            rest = max(rest, s["revive_s"])
        else:
            rest = max(rest, (1 - m.hp / m.stats(data)["hp_max"]) / s["regen_pct_per_s"])
    r.time_s = t + 2 * s["travel_s"] + s["sell_s"] + rest
    r.deaths = sum(1 for m in members if not m.alive)
    share = (gold_pool + value_pool) / n
    for m in members:
        m.gold += share
        m.gold_total += share
        m.alive = True
        m.hp = m.stats(data)["hp_max"]
    return r


def run_hunt(party, ground_id, seconds, data, rng, gear=True):
    elapsed, trips, kills, deaths = 0.0, 0, 0, 0
    while elapsed < seconds:
        r = run_trip(party, ground_id, data, rng)
        elapsed += r.time_s
        trips += 1
        kills += r.kills
        deaths += r.deaths
        if gear:
            for m in party:
                auto_gear(m, data)
    return {"seconds": elapsed, "trips": trips, "kills": kills, "deaths": deaths}
