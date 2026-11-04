import sqlite3
import unittest
from broker_journal import record_open,record_close,report

class BrokerJournalTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
    def tearDown(self):
        self.conn.close()
    def open(self,deal='D1'):
        record_open(self.conn,deal_id=deal,symbol='GOLD',direction='BUY',
                    size='0.01',opened_at='2026-11-04T12:00:00Z',entry_price='4000')
    def test_verified_profit(self):
        self.open()
        self.assertEqual(record_close(self.conn,deal_id='D1',
          closed_at='2026-11-04T12:05:00Z',exit_price='4010',
          net_pnl_gbp='1.25',currency='GBP',broker_verified=True),'WIN')
        self.assertEqual(report(self.conn)['total_net_pnl_gbp'],'1.25')
    def test_verified_loss(self):
        self.open()
        self.assertEqual(record_close(self.conn,deal_id='D1',
          closed_at='2026-11-04T12:05:00Z',exit_price='3990',
          net_pnl_gbp='-2.50',currency='GBP',broker_verified=True),'LOSS')
    def test_reject_unverified_pnl(self):
        self.open()
        with self.assertRaises(ValueError):
            record_close(self.conn,deal_id='D1',closed_at='now',
              exit_price='4010',net_pnl_gbp='1',currency='GBP',broker_verified=False)
    def test_reject_wrong_currency(self):
        self.open()
        with self.assertRaises(ValueError):
            record_close(self.conn,deal_id='D1',closed_at='now',
              exit_price='4010',net_pnl_gbp='1',currency='USD',broker_verified=True)
    def test_reject_duplicate_close(self):
        self.open()
        args=dict(deal_id='D1',closed_at='now',exit_price='4010',
                  net_pnl_gbp='1',currency='GBP',broker_verified=True)
        record_close(self.conn,**args)
        with self.assertRaises(ValueError):
            record_close(self.conn,**args)
    def test_open_has_no_pnl(self):
        self.open()
        self.assertEqual(report(self.conn)['trades'][0]['outcome'],'OPEN')
        self.assertEqual(report(self.conn)['total_net_pnl_gbp'],'0')

if __name__=='__main__':
    unittest.main()
