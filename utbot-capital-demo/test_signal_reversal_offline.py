import unittest
from demo_order_bridge import validate_signal,plan_signal

def position(direction='BUY',epic='GOLD',deal='test-id',size='0.01'):
    return {'position':{'dealId':deal,'direction':direction,'size':size},
            'market':{'epic':epic}}

class SignalReversalTests(unittest.TestCase):
    def setUp(self):
        self.buy=validate_signal({'epic':'GOLD','direction':'BUY','size':'0.01'})
        self.sell=validate_signal({'epic':'GOLD','direction':'SELL','size':'0.01'})
    def test_flat_opens(self):
        self.assertEqual(plan_signal(self.buy,[])['action'],'OPEN')
    def test_same_direction_holds(self):
        self.assertEqual(plan_signal(self.buy,[position()])['action'],'HOLD')
    def test_opposite_closes_first(self):
        result=plan_signal(self.sell,[position()])
        self.assertEqual(result['action'],'CLOSE_THEN_OPEN')
        self.assertTrue(result['requires_confirmed_close'])
        self.assertEqual(result['close_deal_id'],'test-id')
    def test_multiple_positions_halt(self):
        self.assertEqual(plan_signal(self.buy,[position(),position()])['action'],'HALT')
    def test_unknown_position_halt(self):
        self.assertEqual(plan_signal(self.buy,[position(epic='OIL')])['action'],'HALT')
    def test_missing_deal_halt(self):
        self.assertEqual(plan_signal(self.buy,[position(deal='')])['action'],'HALT')
    def test_no_stop_or_limit_required(self):
        self.assertEqual(self.buy.size,'0.01')
        self.assertFalse(hasattr(self.buy,'stop_distance'))
    def test_invalid_size_rejected(self):
        with self.assertRaises(ValueError):
            validate_signal({'epic':'GOLD','direction':'BUY','size':'NaN'})

if __name__=='__main__':
    unittest.main()
