import os
import tempfile
import unittest

import incremental_game as ig


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class GameTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.game = ig.Game(self.clock)

    def test_click_earns_lines(self):
        self.game.click(5)
        self.assertEqual(self.game.lines, 5)

    def test_cannot_buy_without_lines(self):
        ok, _ = self.game.buy_generator(0)
        self.assertFalse(ok)
        self.assertEqual(self.game.owned[0], 0)

    def test_buy_and_passive_income(self):
        self.game.lines = 15
        ok, _ = self.game.buy_generator(0)
        self.assertTrue(ok)
        self.assertEqual(self.game.lines, 0)
        self.clock.t += 10
        self.game.tick()
        self.assertAlmostEqual(self.game.lines, 1.0)

    def test_cost_scales(self):
        self.assertEqual(self.game.generator_cost(0), 15)
        self.game.owned[0] = 1
        self.assertEqual(self.game.generator_cost(0), 18)

    def test_buy_max(self):
        self.game.lines = 15 + 18 + 20
        ok, _ = self.game.buy_generator(0, "max")
        self.assertTrue(ok)
        self.assertEqual(self.game.owned[0], 3)
        self.assertEqual(self.game.lines, 0)

    def test_upgrades_multiply(self):
        self.game.lines = 100
        self.assertTrue(self.game.buy_upgrade("kb")[0])
        self.assertEqual(self.game.click_power(), 2)
        self.assertFalse(self.game.buy_upgrade("kb")[0])

    def test_prestige(self):
        self.assertFalse(self.game.prestige()[0])
        self.game.earn(4_000_000)
        self.game.owned[0] = 10
        ok, _ = self.game.prestige()
        self.assertTrue(ok)
        self.assertEqual(self.game.stars, 2)
        self.assertEqual(self.game.lines, 0)
        self.assertEqual(self.game.owned[0], 0)
        self.assertAlmostEqual(self.game.click_power(), 1.2)

    def test_save_load_and_offline(self):
        self.game.owned[1] = 2       # 2 LPS
        self.game.lines = 50
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "save.json")
            self.game.save(path)
            loaded, msg = ig.load_game(path)
        self.assertEqual(loaded.owned[1], 2)
        self.assertGreaterEqual(loaded.lines, 50)

        g = ig.Game.from_dict(self.game.to_dict(), self.clock)
        self.clock.t += 100
        away, gained = g.apply_offline(self.clock.t - 100)
        self.assertEqual(away, 100)
        self.assertAlmostEqual(gained, 2 * 100 * ig.OFFLINE_RATE)

    def test_handle_commands(self):
        msg, running = ig.handle(self.game, "")
        self.assertTrue(running)
        self.assertEqual(self.game.lines, 1)
        ig.handle(self.game, "c 20")
        self.assertEqual(self.game.lines, 21)
        ig.handle(self.game, "b 1")
        self.assertEqual(self.game.owned[0], 1)
        _, running = ig.handle(self.game, "q")
        self.assertFalse(running)

    def test_fmt(self):
        self.assertEqual(ig.fmt(5), "5")
        self.assertEqual(ig.fmt(1500), "1.50K")
        self.assertEqual(ig.fmt(2_340_000), "2.34M")


if __name__ == "__main__":
    unittest.main()
