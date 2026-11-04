"""Offline tests of isolated Gold V2 preparation gate; no broker calls."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from gold_v2_preparation import prepare_once,status

class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=self.tmp.name+'/test.sqlite3'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE risk_state (id INTEGER PRIMARY KEY, halted INTEGER)')
            db.execute('INSERT INTO risk_state VALUES (1,1)')
            db.execute('CREATE TABLE one_off_tests (id INTEGER PRIMARY KEY, state TEXT)')
            db.execute("INSERT INTO one_off_tests VALUES (1,'position_reconciliation_failed')")
        self.env=patch.dict(os.environ,{'ENABLE_DEMO_ORDERS':'false'})
        self.env.start()
    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()
    def prepare(self):
        return prepare_once(self.path,authenticated=True,proposal_id='proposal-1',
                            explicit_preparation_approval=True)
    def test_single_preparation_never_permits_execution(self):
        self.assertEqual(self.prepare().reason,'prepared_no_execution_adapter')
        self.assertFalse(self.prepare().permitted)
        self.assertEqual(self.prepare().reason,'already_prepared_no_second_attempt')
        self.assertFalse(status(self.path)['execution_available'])
    def test_prior_lock_preserved(self):
        self.prepare()
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT state FROM one_off_tests').fetchone()[0],
                             'position_reconciliation_failed')
            self.assertEqual(db.execute('SELECT halted FROM risk_state').fetchone()[0],1)
    def test_reject_when_main_bot_enabled(self):
        with patch.dict(os.environ,{'ENABLE_DEMO_ORDERS':'true'}):
            self.assertEqual(self.prepare().reason,'main_orders_must_remain_disabled')
    def test_reject_without_authentication(self):
        result=prepare_once(self.path,authenticated=False,proposal_id='x',
                            explicit_preparation_approval=True)
        self.assertEqual(result.reason,'authentication_required')
    def test_reject_without_risk_halt(self):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE risk_state SET halted=0')
        self.assertEqual(self.prepare().reason,'risk_halt_not_verified')
    def test_reject_if_previous_lock_changes(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE one_off_tests SET state='complete'")
        self.assertEqual(self.prepare().reason,'previous_test_lock_not_verified')
if __name__=='__main__':
    unittest.main()
