"""Offline tests only: no Capital.com calls, orders, or account access."""
import unittest
from close_validation import FakeBroker, validate_close_sequence

GOOD = {'dealStatus':'ACCEPTED',
        'affectedDeals':[{'dealId':'test-deal','status':'OPENED'}]}

class CloseSequenceTests(unittest.TestCase):
    def test_delayed_position_and_close(self):
        result=validate_close_sequence(FakeBroker(visible_after=3,absent_after=3),GOOD)
        self.assertTrue(result['passed'])
        self.assertEqual(result['stage'],'complete')

    def test_mismatched_deal_never_closes(self):
        broker=FakeBroker(wrong_deal=True)
        result=validate_close_sequence(broker,GOOD)
        self.assertFalse(result['passed'])
        self.assertFalse(result['close_attempted'])
        self.assertIsNone(broker.close_called_with)

    def test_rejected_open_never_closes(self):
        broker=FakeBroker()
        result=validate_close_sequence(broker,{'dealStatus':'REJECTED'})
        self.assertEqual(result['stage'],'open_confirmation')
        self.assertIsNone(broker.close_called_with)

    def test_rejected_close_does_not_claim_success(self):
        result=validate_close_sequence(FakeBroker(close_accepted=False),GOOD)
        self.assertFalse(result['passed'])
        self.assertEqual(result['stage'],'close_confirmation')

    def test_position_remains_open_fails(self):
        result=validate_close_sequence(FakeBroker(absent_after=99),GOOD)
        self.assertFalse(result['passed'])
        self.assertEqual(result['stage'],'position_still_open')

if __name__=='__main__':
    unittest.main()
