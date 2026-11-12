"""No-network coordinator tests; mock broker never touches real accounts."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from execution_coordinator import execute_reversal,OrderIntent,ExecutionHalted

class Broker:
    def __init__(self, direction=None):
        self.direction=direction
        self.calls=[]
    def active_account_check(self):
        return {"active_account_verified":True,"account_type":"CFD","account_currency":"GBP"}
    def positions(self):
        return ([{"position":{"dealId":"D1" if self.direction=="BUY" else "D2",
                                "direction":self.direction,"size":"0.01"},
                  "market":{"epic":"GOLD"}}] if self.direction else [])
    def close_position(self,deal_id):
        self.calls.append("close")
        self.direction=None
        return {"dealReference":"CLOSE"}
    def open_protected_position(self,epic,direction,size,stop):
        self.calls.append("open")
        self.direction=direction
        return {"dealReference":"OPEN"}
    def confirm(self,reference):
        self.calls.append("confirm")
        return {"dealStatus":"ACCEPTED","dealId":"D1" if reference=="CLOSE" else "D2"}

class TestCoordinator(unittest.TestCase):
    def setUp(self):
        self.intent=OrderIntent("GOLD","SELL","0.01","2","signal-1")
    def test_unapproved_never_calls_broker(self):
        b=Broker("BUY")
        with self.assertRaises(ExecutionHalted):
            execute_reversal(b,self.intent,claim=lambda _:True,audit=lambda *_:None)
        self.assertEqual(b.calls,[])
    def test_opposite_closes_before_open(self):
        b=Broker("BUY")
        events=[]
        result=execute_reversal(b,self.intent,approved=True,
                    claim=lambda _:True,audit=lambda event,data:events.append(event))
        self.assertEqual(result["action"],"OPEN_CONFIRMED")
        self.assertEqual(b.calls,["close","confirm","open","confirm"])
        self.assertEqual(events,["close_attempt","close_confirmed","open_attempt","open_confirmed"])
    def test_duplicate_never_mutates(self):
        b=Broker()
        with self.assertRaisesRegex(ExecutionHalted,"duplicate"):
            execute_reversal(b,self.intent,approved=True,claim=lambda _:False,audit=lambda *_:None)
        self.assertEqual(b.calls,[])
    def test_failed_close_does_not_open(self):
        b=Broker("BUY")
        b.confirm=lambda ref:{"dealStatus":"REJECTED","dealId":"D1"}
        with self.assertRaisesRegex(ExecutionHalted,"close_not_reconciled"):
            execute_reversal(b,self.intent,approved=True,claim=lambda _:True,audit=lambda *_:None)
        self.assertEqual(b.calls,["close"])
if __name__=="__main__":
    unittest.main()
