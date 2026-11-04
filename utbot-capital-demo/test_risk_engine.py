import os
import tempfile
import unittest
from risk_engine import RiskLedger, RiskError, conservative_size, orders_permitted

class RiskTests(unittest.TestCase):
    def test_sizing_rounds_down(self):
        result = conservative_size(1000,5,4000,1,1,'0.01','0.01')
        self.assertEqual(result['size'],'5.00')
        self.assertLessEqual(float(result['estimated_margin_gbp']),1000)
    def test_minimum_exceeds_budget(self):
        with self.assertRaises(RiskError):
            conservative_size(1,10,100,1,1,1,1)
    def test_halt_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=os.path.join(tmp,'state.sqlite')
            ledger=RiskLedger(path)
            self.assertTrue(ledger.state()['halted'])
            with self.assertRaises(RiskError):
                ledger.manual_reset(False,0,True)
            ledger.manual_reset(True,0,True)
            ledger.add_realised(-60)
            self.assertTrue(ledger.evaluate(-41)['halted'])
            self.assertTrue(RiskLedger(path).state()['halted'])
    def test_orders_disabled(self):
        self.assertFalse(orders_permitted())

if __name__=='__main__':
    unittest.main()
