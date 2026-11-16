import csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVEL_CAP = {0: 100, 1: 120, 2: 140, 3: 160, 4: 180, 5: 200}
ELEMENT_COUNTER = {"kim": "moc", "moc": "tho", "tho": "thuy", "thuy": "hoa", "hoa": "kim"}  # khắc


def _rows(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf8", newline="") as f:
        return list(csv.DictReader(f))


def kv(s):
    out = {}
    for part in filter(None, s.split(";")):
        k, _, v = part.partition("=")
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = v
    return out


class Data:
    def __init__(self):
        self.cfg = {r["key"]: float(r["value"]) for r in _rows("config.csv")}
        self.sim = {r["key"]: float(r["value"]) for r in _rows("sim_params.csv")}
        self.roles = {r["role"]: {k: float(v) for k, v in r.items() if k != "role"} for r in _rows("sim_roles.csv")}
        self.schools = {r["id"]: r for r in _rows("schools.csv")}
        self.zones = {r["id"]: r for r in _rows("zones.csv")}
        self.monsters = {r["id"]: r for r in _rows("monsters.csv")}
        self.grounds = {r["id"]: r for r in _rows("grounds.csv")}
        self.bosses = {r["id"]: r for r in _rows("golden_bosses.csv")}
        self.materials = {r["id"]: r for r in _rows("materials.csv")}
        self.items = {r["id"]: r for r in _rows("items.csv")}
        self.drops = {}
        for r in _rows("drop_tables.csv"):
            self.drops.setdefault(r["table_id"], []).append(r)
        # chỉ mục trang bị: (slot, family, rarity) -> [(level_req, id, price)] tăng dần
        self.gear = {}
        for it in self.items.values():
            if it["kind"] == "equip":
                self.gear.setdefault((it["slot"], it["family"], it["rarity"]), []).append(
                    (int(it["level_req"]), it["id"], int(it["price"])))
        for v in self.gear.values():
            v.sort()
        self._stats = {}

    def item_stats(self, iid):
        if iid not in self._stats:
            self._stats[iid] = kv(self.items[iid]["stats"])
        return self._stats[iid]

    def ground_monsters(self, gid):
        return [self.monsters[m] for m in self.grounds[gid]["monster_pool"].split(";")]
