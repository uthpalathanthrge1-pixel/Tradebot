import unittest
from demo_order_bridge import validate_signal,plan_signal,calculate_stop_distance

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
    def test_fifty_pound_planned_loss(self):
        result=calculate_stop_distance(self.buy,verified_gbp_per_point_per_unit='100',
            broker_min_stop_distance='1',broker_distance_increment='0.1')
        self.assertEqual(result['stop_distance'],'50')
        self.assertEqual(result['planned_loss_gbp'],'50.00')
        self.assertIsNone(result['take_profit'])
    def test_round_down_not_over_budget(self):
        result=calculate_stop_distance(self.buy,verified_gbp_per_point_per_unit='90',
            broker_min_stop_distance='1',broker_distance_increment='0.3')
        self.assertLessEqual(float(result['planned_loss_gbp']),50)
    def test_reject_unverified_point_value(self):
        with self.assertRaises(ValueError):
            calculate_stop_distance(self.buy,verified_gbp_per_point_per_unit=None,
                broker_min_stop_distance='1',broker_distance_increment='0.1')
    def test_reject_minimum_exceeding_risk(self):
        with self.assertRaises(ValueError):
            calculate_stop_distance(self.buy,verified_gbp_per_point_per_unit='100',
                broker_min_stop_distance='100',broker_distance_increment='0.1')
    def test_invalid_size_rejected(self):
        with self.assertRaises(ValueError):
            validate_signal({'epic':'GOLD','direction':'BUY','size':'NaN'})

if __name__=='__main__':
    unittest.main()
