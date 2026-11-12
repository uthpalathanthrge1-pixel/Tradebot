import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from confirmation_diagnostic import inspect_confirmation
class Fake:
    def active_account_check(self):
        return {"active_account_verified":True,"account_type":"CFD"}
    def confirm(self,ref):
        return {"dealStatus":"ACCEPTED","dealId":"PRIVATE123","epic":"GOLD",
                "secret":"do-not-leak","dealReference":ref}
class TestConfirmationDiagnostic(unittest.TestCase):
    def test_redaction(self):
        data=inspect_confirmation("ABC-123",Fake())
        self.assertTrue(data["deal_id_present"])
        self.assertNotIn("dealId",data)
        self.assertNotIn("secret",data)
        self.assertIn("dealId",data["response_fields"])
    def test_invalid_reference(self):
        with self.assertRaises(ValueError):
            inspect_confirmation("../positions",Fake())
if __name__=="__main__":unittest.main()
