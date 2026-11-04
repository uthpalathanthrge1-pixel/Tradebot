import unittest
from broker_history_validation import (
    UnverifiedTransaction, normalize_close, summarize_raw_history,
)


class BrokerHistoryValidationTests(unittest.TestCase):
    def setUp(self):
        self.valid = {
            "source": "capital_demo_confirmed",
            "transaction_type": "POSITION_CLOSED",
            "net_pnl_currency": "GBP",
            "net_includes_fees": True,
            "deal_id": "test-deal",
            "closed_at": "2026-11-04T12:00:00Z",
            "net_pnl": "-3.25",
            "exit_price": "4000.50",
        }

    def test_valid_canonical_close(self):
        self.assertEqual(normalize_close(self.valid)["net_pnl_gbp"], "-3.25")

    def test_wrong_currency_rejected(self):
        data = {**self.valid, "net_pnl_currency": "USD"}
        with self.assertRaises(UnverifiedTransaction):
            normalize_close(data)

    def test_unverified_fees_rejected(self):
        data = {**self.valid, "net_includes_fees": False}
        with self.assertRaises(UnverifiedTransaction):
            normalize_close(data)

    def test_nonfinite_pnl_rejected(self):
        data = {**self.valid, "net_pnl": "NaN"}
        with self.assertRaises(UnverifiedTransaction):
            normalize_close(data)

    def test_redacted_history_schema(self):
        result = summarize_raw_history({"transactions": [{"dealId": "SECRET", "profit": 3}]})
        self.assertEqual(result["field_names"], ["dealId", "profit"])
        self.assertNotIn("SECRET", str(result))


if __name__ == "__main__":
    unittest.main()
