import unittest
from unittest.mock import Mock
from demo_order_bridge import validate_signal
from demo_execution_engine import execute_signal, ExecutionUncertain, confirm_accepted

class DemoExecutionOfflineTests(unittest.TestCase):
    def setUp(self):
        self.signal=validate_signal({'epic':'GOLD','direction':'BUY','size':'0.01'})
        self.client=Mock()
        self.client.account_check.return_value={
            'configured_account_found':True,'account_currency':'GBP','account_type':'CFD'}
        self.client.active_account_check.return_value={'active_account_verified':True}
        self.client.market_details.return_value={
            'instrument':{'epic':'GOLD'},'snapshot':{'marketStatus':'TRADEABLE'}}
        self.client.positions.return_value=[]
        self.kwargs={'verified_gbp_per_point_per_unit':'100',
                     'broker_min_stop_distance':'1',
                     'broker_distance_increment':'0.1'}
    def test_not_approved_never_contacts_broker(self):
        result=execute_signal(self.client,self.signal,approved=False,**self.kwargs)
        self.assertEqual(result['status'],'blocked')
        self.client.assert_not_called()
    def test_missing_point_value_never_places_order(self):
        with self.assertRaises(ValueError):
            execute_signal(self.client,self.signal,approved=True,
                verified_gbp_per_point_per_unit=None,
                broker_min_stop_distance='1',broker_distance_increment='0.1')
        self.client.open_protected_position.assert_not_called()
    def test_wrong_account_never_places_order(self):
        self.client.account_check.return_value={'configured_account_found':False}
        result=execute_signal(self.client,self.signal,approved=True,**self.kwargs)
        self.assertEqual(result['status'],'blocked')
        self.client.open_protected_position.assert_not_called()
    def test_wrong_active_account_never_places_order(self):
        self.client.active_account_check.return_value={'active_account_verified':False}
        result=execute_signal(self.client,self.signal,approved=True,**self.kwargs)
        self.assertEqual(result['reason'],'active_session_account_not_verified')
        self.client.open_protected_position.assert_not_called()
    def test_market_closed_never_places_order(self):
        self.client.market_details.return_value={
            'instrument':{'epic':'GOLD'},'snapshot':{'marketStatus':'CLOSED'}}
        result=execute_signal(self.client,self.signal,approved=True,**self.kwargs)
        self.assertEqual(result['status'],'blocked')
        self.client.open_protected_position.assert_not_called()
    def test_rejected_confirmation_fails_closed(self):
        self.client.open_protected_position.return_value={'dealReference':'ref'}
        self.client.confirm.return_value={'dealStatus':'REJECTED'}
        with self.assertRaises(ExecutionUncertain):
            execute_signal(self.client,self.signal,approved=True,**self.kwargs)
        self.client.open_protected_position.assert_called_once()
        self.client.close_position.assert_not_called()
    def test_missing_reference_does_not_retry(self):
        self.client.open_protected_position.return_value={}
        with self.assertRaises(ExecutionUncertain):
            execute_signal(self.client,self.signal,approved=True,**self.kwargs)
        self.client.open_protected_position.assert_called_once()
    def test_unrecognised_position_never_mutates(self):
        self.client.positions.return_value=[{'position':{'dealId':'x','direction':'BUY','size':'1'},
                                             'market':{'epic':'OIL'}}]
        result=execute_signal(self.client,self.signal,approved=True,**self.kwargs)
        self.assertEqual(result['status'],'halt')
        self.client.close_position.assert_not_called()
        self.client.open_protected_position.assert_not_called()

if __name__=='__main__':
    unittest.main()
