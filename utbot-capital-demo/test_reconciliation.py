import unittest
from reconciliation import wait_for_position

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

if __name__=='__main__':
    unittest.main()
