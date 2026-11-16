from dataclasses import dataclass, field
from . import formulas as F
from .data import LEVEL_CAP

TANK_ROLES = ("tank", "tank_guardian")
SLOT_KEYS = ("weapon", "armor", "ring", "amulet")


@dataclass
class Member:
    id: int
    school: str
    pa: int
    level: int = 1
    xp: float = 0.0
    rebirth: int = 0
    gold: float = 0.0
    hp: float = -1.0
    equipment: dict = field(default_factory=dict)
    traits_score: int = 0
    alive: bool = True
    # thống kê tích luỹ (dùng cho ước lượng tốc độ và báo cáo)
    kills: int = 0
    deaths: int = 0
    xp_total: float = 0.0
    gold_total: float = 0.0
    _sig: object = None
    _stats: dict = None

    def role(self, data):
        return data.schools[self.school]["role"]

    def element(self, data):
        return data.schools[self.school]["element"]

    def is_buffer(self, data):
        return data.schools[self.school]["buff_role"] == "true"

    def is_tank(self, data):
        return self.role(data) in TANK_ROLES

    def stats(self, data):
        sig = (self.level, tuple(sorted(self.equipment.items())))
        if self._sig == sig:
            return self._stats
        s = data.sim
        role = data.roles[self.role(data)]
        L = self.level
        eq = [data.item_stats(i) for i in self.equipment.values()]
        g = lambda k: sum(e.get(k, 0.0) for e in eq)
        atk = (s["member_atk_coef"] * L ** s["member_atk_exp"] + g("atk")) * (1 + g("atk_pct"))
        dps = atk * role["dps_mult"] * (1 + s["skill_dps_bonus"] * min(1.0, L / 100))
        hp_max = (s["member_hp_coef"] * L ** s["member_hp_exp"] + s["member_hp_flat"] + g("hp")) \
            * role["hp_mult"] * (1 + g("hp_pct"))
        df = (s["member_def_coef"] * L ** s["member_def_exp"] + g("def")) * role["def_mult"] * (1 + g("def_pct"))
        old_max = self._stats["hp_max"] if self._stats else None
        self._sig, self._stats = sig, {"dps": dps, "hp_max": hp_max, "def": df}
        if self.hp < 0:
            self.hp = hp_max
        elif old_max:
            self.hp = min(hp_max, self.hp * hp_max / old_max)
        return self._stats

    def level_cap(self):
        return LEVEL_CAP[self.rebirth]

    def gain_xp(self, amount, data):
        self.xp += amount
        self.xp_total += amount
        cap = self.level_cap()
        while self.level < cap:
            need = F.xp_need(self.level, data.cfg, self.rebirth)
            if self.xp < need:
                break
            self.xp -= need
            self.level += 1
        if self.level >= cap:
            self.xp = 0.0

    def ca(self, data):
        cap = self.level_cap()
        skill_norm = min(1.0, self.level / cap) * 0.8  # giả định: kỹ năng luyện theo level (chưa mô phỏng skill)
        tiers = [int(data.items[i]["tier"]) / 21 for i in self.equipment.values()]
        equip_norm = sum(tiers) / 4 if tiers else 0.0
        return F.ca_value(self.level, self.rebirth, skill_norm, equip_norm, self.traits_score / 9, self.pa, data.cfg)


def new_member(data, mid, school, pa, level=1, rebirth=0):
    m = Member(id=mid, school=school, pa=pa, level=level, rebirth=rebirth)
    m.stats(data)
    return m


def auto_gear(m, data):
    """Chính sách mua đồ: mua đồ common bậc cao nhất đủ level nếu đủ tiền (giả định đồ có sẵn ở Chợ Bang)."""
    sc = data.schools[m.school]
    want = {"weapon": ("weapon", sc["weapon"]), "armor": ("armor", sc["armor_class"]),
            "ring": ("accessory", "ring"), "amulet": ("accessory", "amulet")}
    for key, (slot, fam) in want.items():
        best = None
        for lv, iid, price in data.gear[(slot, fam, "common")]:
            if lv <= m.level:
                best = (lv, iid, price)
        if not best:
            continue
        cur = m.equipment.get(key)
        cur_lv = int(data.items[cur]["level_req"]) if cur else -1
        if best[0] > cur_lv and m.gold >= best[2]:
            m.gold -= best[2]
            m.equipment[key] = best[1]
