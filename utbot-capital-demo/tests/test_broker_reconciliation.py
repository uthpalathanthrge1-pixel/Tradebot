import unittest
from broker_reconciliation import (reconcile_open_confirmation, reconcile_close_confirmation, ReconciliationError)

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.position = {"market":{"epic":"GOLD"},"position":{"dealId":"D1","direction":"BUY","size":0.01}}
    def test_open_confirmed(self):
        self.assertTrue(reconcile_open_confirmation({"dealStatus":"ACCEPTED","dealId":"D1"},[self.position],"GOLD","BUY","0.01")["confirmed"])
    def test_reject_unmatched(self):
        with self.assertRaises(ReconciliationError):
            reconcile_open_confirmation({"dealStatus":"ACCEPTED","dealId":"D2"},[self.position],"GOLD","BUY","0.01")
    def test_close_confirmed(self):
        self.assertTrue(reconcile_close_confirmation({"dealStatus":"ACCEPTED"},[],"D1")["closed_confirmed"])
    def test_close_still_open(self):
        with self.assertRaises(ReconciliationError):
            reconcile_close_confirmation({"dealStatus":"ACCEPTED"},[self.position],"D1")
if __name__ == "__main__":
    unittest.main()
