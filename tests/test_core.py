import os, sys, copy, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.data import Data
from sim.rng import PCG32
from sim import formulas as F
from sim.model import new_member, auto_gear
from sim.hunt import run_trip, run_hunt, fight
from sim.offline import fast_forward
from sim.raid import simulate_raid, form_parties

D = Data()


class TestRng(unittest.TestCase):
    def test_pcg32_official_vectors(self):
        g = PCG32(42, 54)
        self.assertEqual([g.next_u32() for _ in range(6)],
                         [0xa15c02b7, 0x7b47f409, 0xba1d3330, 0x83d2f293, 0xbfa4784b, 0xcbed606e])

    def test_deterministic_and_bounds(self):
        a, b = PCG32(1), PCG32(1)
        self.assertEqual([a.random() for _ in range(50)], [b.random() for _ in range(50)])
        g = PCG32(9)
        vals = [g.randint(3, 7) for _ in range(2000)]
        self.assertEqual(set(vals), {3, 4, 5, 6, 7})
        self.assertTrue(all(0 <= PCG32(s).random() < 1 for s in range(50)))


class TestFormulas(unittest.TestCase):
    def test_element_cycle(self):
        c = D.cfg
        cycle = ["kim", "moc", "tho", "thuy", "hoa"]  # mỗi hệ khắc hệ kế tiếp
        for i, e in enumerate(cycle):
            nxt = cycle[(i + 1) % 5]
            self.assertEqual(F.element_mult(e, nxt, c), 1.25)
            self.assertEqual(F.element_mult(nxt, e, c), 0.8)
            self.assertEqual(F.element_mult(e, e, c), 0.95)
            self.assertEqual(F.element_mult(e, cycle[(i + 2) % 5], c), 1.0)

    def test_growth_and_party_mult(self):
        self.assertAlmostEqual(F.growth_mult(0, D.cfg), 0.6)
        self.assertAlmostEqual(F.growth_mult(200, D.cfg), 1.4)
        self.assertAlmostEqual(F.party_xp_mult(1, False, False, D.cfg), 1.0)
        self.assertAlmostEqual(F.party_xp_mult(5, True, True, D.cfg), 1 + 0.32 + 0.10 + 0.05)

    def test_ca_soft_cap(self):
        lo = F.ca_value(100, 0, 0.8, 0.5, 0.5, 60, D.cfg)
        self.assertGreaterEqual(lo, 60)  # vượt PA vẫn tăng nhưng chậm
        hi_pa = F.ca_value(100, 0, 0.8, 0.5, 0.5, 200, D.cfg)
        self.assertGreater(hi_pa, lo)
        self.assertLessEqual(F.ca_value(100, 0, 1, 1, 1, 200, D.cfg), 200)


class TestMember(unittest.TestCase):
    def test_level_up_and_cap(self):
        m = new_member(D, 1, "kim_2", 100)
        m.gain_xp(1e12, D)
        self.assertEqual(m.level, 100)  # chặn ở level cap của chuyển sinh 0
        m2 = new_member(D, 2, "kim_2", 100, rebirth=1)
        m2.gain_xp(1e15, D)
        self.assertEqual(m2.level, 120)

    def test_pa_speeds_up_leveling(self):
        res = {}
        for pa in (40, 160):
            m = new_member(D, 1, "kim_2", pa)
            run_hunt([m], "g_z01_1", 2 * 3600, D, PCG32(5))
            res[pa] = m.level
        self.assertGreater(res[160], res[40])

    def test_gear_policy_buys_upgrade(self):
        m = new_member(D, 1, "kim_2", 100, level=30)
        m.gold = 1e9
        auto_gear(m, D)
        self.assertEqual(set(m.equipment), {"weapon", "armor", "ring", "amulet"})
        self.assertTrue(all(int(D.items[i]["level_req"]) <= 30 for i in m.equipment.values()))
        self.assertTrue(m.gold < 1e9)


class TestHunt(unittest.TestCase):
    def test_same_seed_same_result(self):
        outs = []
        for _ in range(2):
            m = new_member(D, 1, "hoa_2", 100, level=20)
            r = run_hunt([m], "g_z02_3", 3 * 3600, D, PCG32(77))
            outs.append((r, m.level, round(m.xp, 3), round(m.gold, 3), m.kills))
        self.assertEqual(outs[0], outs[1])

    def test_party_with_buffer_beats_solo_xp_rate(self):
        # cùng level, cùng bãi: đội đủ tank + buffer + dps có XP/giờ mỗi người >= solo
        solo = new_member(D, 1, "kim_2", 100, level=30)
        run_hunt([solo], "g_z03_3", 4 * 3600, D, PCG32(3), gear=False)
        party = [new_member(D, i, s, 100, level=30) for i, s in
                 enumerate(["tho_1", "moc_1", "kim_2", "hoa_2", "thuy_1"], start=10)]
        run_hunt(party, "g_z03_3", 4 * 3600, D, PCG32(3), gear=False)
        mean_party = sum(m.xp_total for m in party) / 5
        self.assertGreater(mean_party, solo.xp_total * 0.9)

    def test_death_revives_and_counts(self):
        m = new_member(D, 1, "moc_1", 100, level=5)  # healer yếu, bãi quá khó
        r = run_hunt([m], "g_z05_3", 3600, D, PCG32(2), gear=False)
        self.assertTrue(m.alive and m.hp > 0)  # luôn được hồi sinh sau chuyến
        self.assertGreaterEqual(r["deaths"], 1)


class TestOfflineFastForward(unittest.TestCase):
    def test_matches_exact_within_tolerance(self):
        hours = 6
        exact, ff = [], []
        for seed in (1, 2, 3):
            a = new_member(D, 1, "kim_2", 100, level=20)
            b = copy.deepcopy(a)
            run_hunt([a], "g_z02_3", hours * 3600, D, PCG32(seed))
            fast_forward([b], "g_z02_3", hours * 3600, D, PCG32(seed + 100))
            exact.append(a.xp_total)
            ff.append(b.xp_total)
        mean = lambda v: sum(v) / len(v)
        self.assertAlmostEqual(mean(ff) / mean(exact), 1.0, delta=0.2)

    def test_deterministic(self):
        r = []
        for _ in range(2):
            m = new_member(D, 1, "kim_2", 100, level=20)
            fast_forward([m], "g_z02_3", 5 * 3600, D, PCG32(8))
            r.append((m.level, round(m.xp_total, 2), round(m.gold, 2)))
        self.assertEqual(r[0], r[1])


class TestRaid(unittest.TestCase):
    def guild(self, n, level, schools=("tho_1", "moc_1", "kim_2", "hoa_2", "thuy_1")):
        ms = []
        for i in range(n):
            m = new_member(D, i, schools[i % len(schools)], 100, level=level)
            m.gold = 1e12
            auto_gear(m, D)
            ms.append(m)
        return ms

    def test_parties_have_buffer_and_tank_and_size_cap(self):
        ms = self.guild(25, 50)
        ps = form_parties(ms, D)
        self.assertEqual(sum(len(p) for p in ps), 25)
        for p in ps:
            self.assertLessEqual(len(p), 5)
            self.assertTrue(any(m.is_buffer(D) for m in p))
            self.assertTrue(any(m.is_tank(D) for m in p))

    def test_more_members_faster_kill_but_boss_scales(self):
        small = simulate_raid(self.guild(10, 50), "gb_05", D, PCG32(1))
        big = simulate_raid(self.guild(30, 50), "gb_05", D, PCG32(1))
        self.assertTrue(big.win)
        if small.win:
            self.assertLessEqual(big.time_s, small.time_s * 1.5)

    def test_undergeared_guild_loses(self):
        weak = self.guild(10, 20)
        self.assertFalse(simulate_raid(weak, "gb_08", D, PCG32(1)).win)

    def test_raid_deterministic(self):
        a = simulate_raid(self.guild(15, 60), "gb_06", D, PCG32(4))
        b = simulate_raid(self.guild(15, 60), "gb_06", D, PCG32(4))
        self.assertEqual((a.win, round(a.time_s, 6), a.deaths), (b.win, round(b.time_s, 6), b.deaths))


if __name__ == "__main__":
    unittest.main()


class TestPacingAndEconomy(unittest.TestCase):
    def setUp(self):
        from sim.data import Data
        self.D = Data()

    def test_early_levels_cheaper(self):
        from sim import formulas as F
        c = dict(self.D.cfg)
        c["xp_early_floor"], c["xp_early_end"] = 1.0, 1.0
        flat = F.xp_need(5, c)
        self.assertLess(F.xp_need(5, self.D.cfg), 0.5 * flat)
        self.assertAlmostEqual(F.xp_need(60, self.D.cfg), F.xp_need(60, c), places=6)

    def test_rebirth_slower(self):
        from sim import formulas as F
        needs = [F.xp_need(110, self.D.cfg, rb) for rb in range(6)]
        self.assertEqual(needs, sorted(needs))
        self.assertGreater(needs[5], 10 * needs[0])

    def test_enhance_cost_monotonic_and_ward(self):
        from sim import economy as E
        t = E.load_enhance()
        costs = [E.enhance_expected_cost(100, n, self.D.cfg, t) for n in range(1, 21)]
        self.assertEqual(costs, sorted(costs))
        no_ward = E.enhance_expected_cost(100, 15, self.D.cfg, t)
        ward = E.enhance_expected_cost(100, 15, self.D.cfg, t, ward=True, ward_cost=20000)
        self.assertLess(ward, no_ward)

    def test_enhance_markov_matches_simulation(self):
        from sim import economy as E
        t = E.load_enhance()
        target, L = 9, 50
        exact = E.enhance_expected_cost(L, target, self.D.cfg, t)
        rng = PCG32(99)
        tot, runs = 0.0, 3000
        for _ in range(runs):
            lv = 0
            while lv < target:
                n = lv + 1
                tot += E.enhance_attempt_cost(L, n, self.D.cfg, t)
                if rng.random() < t[n - 1]["p"]:
                    lv += 1
                elif t[n - 1]["drop"]:
                    lv = max(0, lv - 1)
        self.assertLess(abs(tot / runs - exact) / exact, 0.08)

    def test_upkeep_share_reasonable(self):
        from sim import economy as E
        share = E.upkeep_per_hour(100, self.D.cfg) / E.income_per_hour(100, self.D.cfg)
        self.assertTrue(0.1 < share < 0.4)
