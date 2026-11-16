from dataclasses import dataclass, field
from . import formulas as F
from .hunt import _k


@dataclass
class RaidResult:
    win: bool
    time_s: float
    deaths: int
    contrib: dict = field(default_factory=dict)
    boss_hp: float = 0.0


def form_parties(members, data, size=5):
    """Chia cả bang thành các đội ≤5; mỗi đội cố gắng có 1 buffer và 1 tank (ưu tiên chốt trong GDD 6.12)."""
    n_parties = max(1, -(-len(members) // size))
    buffers = [m for m in members if m.is_buffer(data)]
    tanks = [m for m in members if m.is_tank(data)]
    rest = [m for m in members if m not in buffers and m not in tanks]
    parties = [[] for _ in range(n_parties)]
    for i, b in enumerate(buffers):
        parties[i % n_parties].append(b)
    for i, t in enumerate(tanks):
        parties[i % n_parties].append(t)
    for m in rest:
        p = min(parties, key=len)
        p.append(m)
    # cân bằng lại nếu đội nào vượt size
    flat_over = []
    for p in parties:
        while len(p) > size:
            flat_over.append(p.pop())
    for m in flat_over:
        min(parties, key=len).append(m)
    return parties


def simulate_raid(members, gb_id, data, rng):
    s, cfg = data.sim, data.cfg
    gb = data.bosses[gb_id]
    mon = data.monsters[gb["monster_id"]]
    L = int(mon["level"])
    n = len(members)
    hp = F.monster_hp(L, float(mon["hp_mult"]), cfg) * (1 + float(gb["hp_per_participant"]) * n) * s["raid_hp_mult"]
    base_hit = F.monster_atk(L, float(mon["atk_mult"]), cfg) * s["monster_dmg_factor"] * s["raid_dmg_mult"]
    mdef = F.monster_def(L, float(mon["def_mult"]), cfg)
    pf = _k(L, s) / (_k(L, s) + mdef)
    interval = s["raid_boss_interval_s"] / float(mon["speed"])
    parties = form_parties(members, data)
    party_of = {}
    for i, p in enumerate(parties):
        for m in p:
            party_of[m.id] = i
    has_buf = [any(m.is_buffer(data) for m in p) for p in parties]
    for m in members:
        m.hp = m.stats(data)["hp_max"]
        m.alive = True
    nxt = {m.id: rng.random() for m in members}
    boss_next = rng.random() * interval
    contrib = {m.id: 0.0 for m in members}
    deaths = 0
    t = 0.0
    while hp > 0:
        alive = [m for m in members if m.alive]
        if not alive or t > s["raid_time_limit_s"]:
            return RaidResult(False, t, deaths, contrib, hp)
        nm = min(alive, key=lambda m: nxt[m.id])
        if nxt[nm.id] <= boss_next:
            t = nxt[nm.id]
            nxt[nm.id] += 1.0
            pi = party_of[nm.id]
            if nm.role(data) == "healer_support":
                mates = [m for m in parties[pi] if m.alive]
                if mates:
                    tgt = min(mates, key=lambda m: m.hp / m.stats(data)["hp_max"])
                    if tgt.hp / tgt.stats(data)["hp_max"] < 0.8:
                        tgt.hp = min(tgt.stats(data)["hp_max"], tgt.hp + s["healer_heal_frac"] * tgt.stats(data)["hp_max"])
                        continue
            d = nm.stats(data)["dps"] * (1 + (s["buffer_atk"] if has_buf[pi] else 0)) \
                * F.element_mult(nm.element(data), mon["element"], cfg) * (0.9 + 0.2 * rng.random()) * pf
            hp -= d
            contrib[nm.id] += d
        else:
            t = boss_next
            boss_next += interval
            enrage = 1 + s["raid_enrage_atk"] * int(t // s["raid_enrage_every_s"])
            pool = list(alive)
            for _ in range(int(s["raid_boss_targets"])):
                if not pool:
                    break
                tanks = [m for m in pool if m.is_tank(data)]
                tgt = rng.choice(tanks) if tanks and rng.random() < s["tank_aggro_share"] else rng.choice(pool)
                pool.remove(tgt)
                red = s["buffer_dmg_reduction"] if has_buf[party_of[tgt.id]] else 0.0
                ts = tgt.stats(data)
                dmg = base_hit * enrage * F.element_mult(mon["element"], tgt.element(data), cfg) * (1 - red) \
                    * _k(L, s) / (_k(L, s) + ts["def"])
                tgt.hp -= dmg
                if tgt.hp <= 0:
                    tgt.hp = 0.0
                    tgt.alive = False
                    deaths += 1
    return RaidResult(True, t, deaths, contrib, 0.0)
