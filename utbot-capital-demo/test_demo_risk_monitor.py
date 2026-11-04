import unittest
from demo_risk_monitor import inspect

class DemoRiskMonitorTests(unittest.TestCase):
    def test_empty_positions_still_not_armed(self):
        result=inspect([],realised_gbp='0')
        self.assertTrue(result['must_halt'])
        self.assertFalse(result['ready_to_trade'])
    def test_unknown_position_halts(self):
        result=inspect([{'position':{'dealId':'demo-1'}}],realised_gbp='0')
        self.assertIn('unmanaged_or_unknown_position',result['reasons'])
    def test_missing_position_halts(self):
        result=inspect([],realised_gbp='0',expected_deal_ids={'demo-1'})
        self.assertIn('expected_position_not_visible',result['reasons'])
    def test_realised_loss_halts(self):
        result=inspect([],realised_gbp='-100')
        self.assertIn('realised_loss_limit_breached',result['reasons'])
    def test_invalid_pnl_halts(self):
        result=inspect([],realised_gbp='NaN')
        self.assertIn('invalid_risk_parameters',result['reasons'])

if __name__=='__main__':
    unittest.main()
