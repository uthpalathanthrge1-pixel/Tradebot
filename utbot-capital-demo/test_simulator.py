import unittest
from simulator import Simulator

class SimulatorTests(unittest.TestCase):
    def test_reverse(self):
        bot = Simulator()
        self.assertEqual(bot.signal('GOLD','BUY'), 'SIMULATED_BUY')
        self.assertEqual(bot.signal('GOLD','SELL'), 'SIMULATED_SELL')
        self.assertEqual(bot.positions['GOLD'], 'SELL')

    def test_combined_loss_shutdown(self):
        bot = Simulator()
        bot.signal('GOLD','BUY')
        bot.signal('OIL','SELL')
        bot.mark('GOLD', -60)
        bot.mark('OIL', -41)
        self.assertTrue(bot.halted)
        self.assertFalse(bot.positions)
        self.assertEqual(bot.signal('GOLD','BUY'), 'HALTED')

    def test_no_duplicate_entry(self):
        bot = Simulator()
        bot.signal('GOLD','BUY')
        self.assertEqual(bot.signal('GOLD','BUY'), 'UNCHANGED')

if __name__ == '__main__':
    unittest.main()
