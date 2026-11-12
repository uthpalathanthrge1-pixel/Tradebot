import tempfile,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from guarded_execution import execute_with_ledger
from execution_coordinator import OrderIntent,ExecutionHalted
from test_execution_coordinator import Broker

class TestGuardedExecution(unittest.TestCase):
    def setUp(self):
        self.intent=OrderIntent("GOLD","BUY","0.01","2","test-signal")
    def test_gate_blocks_without_broker_calls(self):
        broker=Broker()
        with self.assertRaisesRegex(ExecutionHalted,"not_approved"):
            execute_with_ledger(broker,self.intent)
        self.assertEqual(broker.calls,[])
    def test_tmp_storage_rejected(self):
        broker=Broker()
        with self.assertRaisesRegex(ExecutionHalted,"persistent_execution_store_required"):
            execute_with_ledger(broker,self.intent,approved=True,db_path="/tmp/ledger.db")
        self.assertEqual(broker.calls,[])
    def test_duplicate_after_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/"execution.db")
            broker=Broker()
            result=execute_with_ledger(broker,self.intent,approved=True,db_path=path)
            self.assertEqual(result["action"],"OPEN_CONFIRMED")
            with self.assertRaisesRegex(ExecutionHalted,"duplicate"):
                # Different broker instance simulates restart and stale broker state.
                execute_with_ledger(Broker(),self.intent,approved=True,db_path=path)
if __name__=="__main__":
    unittest.main()
