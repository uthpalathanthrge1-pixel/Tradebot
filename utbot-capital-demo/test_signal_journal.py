import sqlite3
import unittest
from signal_journal import record,report

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
    def tearDown(self):
        self.db.close()
    def test_buy_to_sell_profit(self):
        self.assertEqual(record(self.db,'GOLD',100,'BUY','4000'),'opened')
        self.assertEqual(record(self.db,'GOLD',200,'SELL','4010'),'reversed')
        r=report(self.db)
        self.assertEqual(r['trades'][1]['outcome'],'WIN')
        self.assertEqual(r['trades'][1]['points'],'10')
    def test_sell_to_buy_profit(self):
        record(self.db,'OIL',100,'SELL','90')
        record(self.db,'OIL',200,'BUY','88')
        self.assertEqual(report(self.db)['trades'][1]['points'],'2')
    def test_missing_price_unpriced(self):
        record(self.db,'GOLD',100,'BUY',None)
        record(self.db,'GOLD',200,'SELL','4010')
        self.assertEqual(report(self.db)['trades'][1]['outcome'],'UNPRICED')
    def test_duplicate_ignored(self):
        record(self.db,'GOLD',100,'BUY','4000')
        self.assertEqual(record(self.db,'GOLD',100,'BUY','4000'),'duplicate')
        self.assertEqual(len(report(self.db)['trades']),1)
    def test_old_signal_ignored(self):
        record(self.db,'GOLD',200,'BUY','4000')
        self.assertEqual(record(self.db,'GOLD',100,'SELL','3990'),'out_of_order_ignored')
        self.assertEqual(len(report(self.db)['trades']),1)
    def test_same_direction_ignored(self):
        record(self.db,'GOLD',100,'BUY','4000')
        self.assertEqual(record(self.db,'GOLD',200,'BUY','4002'),'same_direction_ignored')
        self.assertEqual(len(report(self.db)['trades']),1)

if __name__=='__main__':
    unittest.main()
