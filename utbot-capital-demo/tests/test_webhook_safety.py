"""Offline tests: all supported TradingView symbols remain signal-only."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

class WebhookSafetyTests(unittest.TestCase):
    def test_all_market_alerts_never_submit(self):
        with tempfile.TemporaryDirectory() as directory:
            # app imports DB path once, so patch it explicitly.
            import app
            with patch.object(app, "DB", str(Path(directory) / "test.sqlite3")):
                with patch.dict(os.environ, {"WEBHOOK_SECRET":"test-secret"}):
                    client = TestClient(app.app)
                    for i, symbol in enumerate(("GOLD","XAUUSD","OIL","OIL_CRUDE","US500")):
                        response = client.post("/webhook/test-secret",
                            json={"symbol":symbol,"direction":"BUY","bar_time":1800000000000+i})
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertFalse(response.json()["orders_submitted"])
    def test_unknown_market_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            import app
            with patch.object(app, "DB", str(Path(directory) / "test.sqlite3")):
                with patch.dict(os.environ, {"WEBHOOK_SECRET":"test-secret"}):
                    response=TestClient(app.app).post("/webhook/test-secret",
                        json={"symbol":"UNKNOWN","direction":"SELL","bar_time":1800000000123})
                    self.assertEqual(response.json()["execution"],"unsupported_market")
                    self.assertFalse(response.json()["orders_submitted"])
if __name__=="__main__":
    unittest.main()
