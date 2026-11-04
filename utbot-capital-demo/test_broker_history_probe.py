import unittest
from datetime import date
from broker_history_probe import probe_history

class FakeCapital:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
    def activity(self, start, end):
        self.calls.append((start, end))
        return self.payload

class BrokerHistoryProbeTests(unittest.TestCase):
    def test_redacted_read_only_probe(self):
        client = FakeCapital({'transactions':[{'dealId':'SENSITIVE','profit':12}]})
        result = probe_history(client, today=date(2026,11,4))
        self.assertEqual(client.calls, [('2026-10-28','2026-11-04')])
        self.assertEqual(result['field_names'], ['dealId','profit'])
        self.assertNotIn('SENSITIVE', str(result))
        self.assertFalse(result['currency_verified'])
    def test_invalid_window(self):
        with self.assertRaises(ValueError):
            probe_history(FakeCapital({}),lookback_days=31)
    def test_unexpected_schema(self):
        result=probe_history(FakeCapital({'other':[]}),today=date(2026,11,4))
        self.assertFalse(result['schema_valid'])

if __name__=='__main__':
    unittest.main()
