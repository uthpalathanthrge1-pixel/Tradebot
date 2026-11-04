import unittest
from reconciliation import wait_for_position, opened_deal_ids, wait_for_absence

class ReconciliationTests(unittest.TestCase):
    def test_delayed_position(self):
        count=[0]
        def fetch():
            count[0]+=1
            if count[0]<3: return []
            return [{'position':{'dealId':'abc','direction':'BUY','size':0.01},
                     'market':{'epic':'GOLD'}}]
        position, info=wait_for_position(fetch,'abc','GOLD','BUY','0.01',
                                         attempts=4,delay_seconds=0,sleep=lambda _:None)
        self.assertIsNotNone(position)
        self.assertEqual(info['poll'],3)

    def test_wrong_size_never_matches(self):
        fetch=lambda:[{'position':{'dealId':'abc','direction':'BUY','size':1},
                       'market':{'epic':'GOLD'}}]
        position, info=wait_for_position(fetch,'abc','GOLD','BUY','0.01',
                                         attempts=2,delay_seconds=0,sleep=lambda _:None)
        self.assertIsNone(position)
        self.assertEqual(info['reason'],'no_exact_position_match_after_polling')

    def test_wrong_deal_never_matches(self):
        fetch=lambda:[{'position':{'dealId':'other','direction':'BUY','size':0.01},
                       'market':{'epic':'GOLD'}}]
        position, _=wait_for_position(fetch,'abc','GOLD','BUY','0.01',
                                      attempts=1,sleep=lambda _:None)
        self.assertIsNone(position)

class CloseTests(unittest.TestCase):
    def test_affected_deals_preferred_over_primary_id(self):
        confirmation={'dealId':'order-id',
                      'affectedDeals':[{'dealId':'position-id','status':'OPENED'}]}
        self.assertEqual(opened_deal_ids(confirmation),['position-id'])

    def test_multiple_opened_deals_detected(self):
        confirmation={'dealId':'order-id','affectedDeals':[
            {'dealId':'a','status':'OPENED'},{'dealId':'b','status':'OPENED'}]}
        self.assertEqual(len(opened_deal_ids(confirmation)),2)

    def test_close_eventual_absence(self):
        n=[0]
        def fetch():
            n[0]+=1
            return [{'position':{'dealId':'abc'}}] if n[0]<3 else []
        self.assertTrue(wait_for_absence(fetch,'abc',attempts=4,
                                        delay_seconds=0,sleep=lambda _:None))

    def test_close_still_open(self):
        fetch=lambda:[{'position':{'dealId':'abc'}}]
        self.assertFalse(wait_for_absence(fetch,'abc',attempts=2,
                                         delay_seconds=0,sleep=lambda _:None))

if __name__=='__main__':
    unittest.main()
