"""Offline read-only validation tests. No broker credentials or network required."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_validation import MARKETS, margin_preview, inspect_market
from dashboard import dashboard


class TestMarketValidation(unittest.TestCase):
    def test_three_markets(self):
        self.assertEqual(set(MARKETS), {"GOLD", "OIL", "US500"})

    def test_rounds_down_under_margin_target(self):
        result = margin_preview(price="100", margin_factor_percent="5",
            units_per_size="1", gbp_per_quote_unit="1",
            min_size="0.1", size_increment="0.1")
        self.assertEqual(float(result["size_preview"]), 300.0)
        self.assertEqual(float(result["estimated_margin_gbp"]), 1500.0)
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["ready"])

    def test_rejects_missing_fx(self):
        with self.assertRaises(ValueError):
            margin_preview(price=100, margin_factor_percent=5,
                units_per_size=1, gbp_per_quote_unit=None,
                min_size=0.1, size_increment=0.1)

    def test_minimum_exceeds_budget(self):
        result = margin_preview(price=1000, margin_factor_percent=10,
            units_per_size=1, gbp_per_quote_unit=1,
            min_size=20, size_increment=1)
        self.assertEqual(result["reason"], "minimum_size_exceeds_margin_budget")

    def test_inspection_never_trades(self):
        class Client:
            def market_details(self, epic):
                return {"instrument": {"epic": epic, "marginFactor": 5},
                        "snapshot": {"offer": 100},
                        "dealingRules": {"minDealSize": {"value": 0.01}}}
            def open_position(self, *args):
                raise AssertionError("trade attempted")
        result = inspect_market(Client(), "GOLD")
        self.assertIsNone(result["size_preview"])
        self.assertFalse(result["orders_enabled"])


if __name__ == "__main__":
    unittest.main()
