"""Offline persistence tests; no broker requests."""
import tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from execution_ledger import ExecutionLedger,LedgerError

class TestExecutionLedger(unittest.TestCase):
    def test_claim_survives_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"ledger.db")
            self.assertTrue(ExecutionLedger(path).claim("gold:123:BUY"))
            self.assertFalse(ExecutionLedger(path).claim("gold:123:BUY"))
            self.assertTrue(ExecutionLedger(path).claim("gold:124:SELL"))
    def test_audit_survives_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"ledger.db")
            ledger=ExecutionLedger(path)
            ledger.claim("s1")
            ledger.audit("close_attempt",{"signal_id":"s1","deal_id":"D1"})
            self.assertEqual(ExecutionLedger(path).recent()[0][2],"close_attempt")
    def test_rejects_missing_signal(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=ExecutionLedger(str(Path(d)/"ledger.db"))
            with self.assertRaises(LedgerError):
                ledger.audit("open_attempt",{})
if __name__=="__main__":
    unittest.main()
