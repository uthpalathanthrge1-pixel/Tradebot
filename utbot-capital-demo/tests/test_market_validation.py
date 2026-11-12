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


class TestBrokerReconciliation(unittest.TestCase):
    def test_open_requires_exact_matching_position(self):
        from demo_order_bridge import verify_open_confirmation
        confirm = {"dealStatus": "ACCEPTED", "dealId": "demo-deal"}
        positions = [{"position": {"dealId": "demo-deal", "direction": "BUY", "size": 0.01},
                      "market": {"epic": "GOLD"}}]
        self.assertTrue(verify_open_confirmation(confirm, positions, epic="GOLD",
                                                direction="BUY", size="0.01")["verified"])
        self.assertFalse(verify_open_confirmation(confirm, [], epic="GOLD",
                                                 direction="BUY", size="0.01")["verified"])

    def test_close_requires_absent_position(self):
        from demo_order_bridge import verify_close_confirmation
        confirm = {"dealStatus": "ACCEPTED", "dealId": "demo-deal"}
        positions = [{"position": {"dealId": "demo-deal"}}]
        self.assertFalse(verify_close_confirmation(confirm, positions, deal_id="demo-deal")["verified"])
        self.assertTrue(verify_close_confirmation(confirm, [], deal_id="demo-deal")["verified"])

    def test_rejects_unaccepted_confirmations(self):
        from demo_order_bridge import verify_open_confirmation, verify_close_confirmation
        self.assertFalse(verify_open_confirmation({"dealStatus": "REJECTED", "dealId": "x"},
                          [], epic="GOLD", direction="BUY", size="0.01")["verified"])
        self.assertFalse(verify_close_confirmation({"dealStatus": "REJECTED", "dealId": "x"},
                          [], deal_id="x")["verified"])


class TestReversalPlanning(unittest.TestCase):
    def test_flat_opens(self):
        from demo_order_bridge import validate_signal, plan_signal
        signal=validate_signal({'epic':'GOLD','direction':'BUY','size':'0.01'})
        self.assertEqual(plan_signal(signal,[])['action'],'OPEN')

    def test_same_direction_holds(self):
        from demo_order_bridge import validate_signal, plan_signal
        signal=validate_signal({'epic':'GOLD','direction':'BUY','size':'0.01'})
        p=[{'position':{'dealId':'d1','direction':'BUY','size':0.01},
            'market':{'epic':'GOLD'}}]
        self.assertEqual(plan_signal(signal,p)['action'],'HOLD')

    def test_opposite_requires_close_confirmation(self):
        from demo_order_bridge import validate_signal, plan_signal
        signal=validate_signal({'epic':'GOLD','direction':'SELL','size':'0.01'})
        p=[{'position':{'dealId':'d1','direction':'BUY','size':0.01},
            'market':{'epic':'GOLD'}}]
        result=plan_signal(signal,p)
        self.assertEqual(result['action'],'CLOSE_THEN_OPEN')
        self.assertTrue(result['requires_confirmed_close'])

    def test_ambiguous_positions_halt(self):
        from demo_order_bridge import validate_signal, plan_signal
        signal=validate_signal({'epic':'GOLD','direction':'BUY','size':'0.01'})
        self.assertEqual(plan_signal(signal,[{},{}])['action'],'HALT')

    def test_missing_stop_metadata_fails_closed(self):
        from demo_order_bridge import validate_signal, calculate_stop_distance
        signal=validate_signal({'epic':'GOLD','direction':'BUY','size':'0.01'})
        with self.assertRaises(ValueError):
            calculate_stop_distance(signal,verified_gbp_per_point_per_unit=None,
                                    broker_min_stop_distance='1',
                                    broker_distance_increment='0.1')

from test_execution_coordinator import TestCoordinator
from test_webhook_safety import WebhookSafetyTests
from test_broker_reconciliation import ReconciliationTests

if __name__ == "__main__":
    unittest.main()
