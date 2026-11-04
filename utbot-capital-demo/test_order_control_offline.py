"""Offline tests for operator pause/resume; no broker requests."""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
import app

class FakeRequest:
    def __init__(self, action, origin='https://example.test'):
        self.headers={'origin':origin,'host':'example.test','content-type':'application/json'}
        self.url=type('URL',(),{'scheme':'https'})()
        self.action=action
    async def json(self):
        return {'action':self.action}

class OrderControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.dbpatch=patch.object(app,'DB',os.path.join(self.tmp.name,'control.sqlite3'))
        self.dbpatch.start()
        self.envpatch=patch.dict(os.environ,{'WEBHOOK_SECRET':'unit-test-secret',
                                            'ENABLE_DEMO_ORDERS':'false'})
        self.envpatch.start()
    def tearDown(self):
        self.envpatch.stop()
        self.dbpatch.stop()
        self.tmp.cleanup()
    def update(self,action,origin='https://example.test'):
        return asyncio.run(app.order_control_update('unit-test-secret',FakeRequest(action,origin)))
    def test_default_paused(self):
        state=app.order_control_status('unit-test-secret')
        self.assertTrue(state['operator_paused'])
        self.assertFalse(state['orders_enabled'])
    def test_resume_then_pause_persists(self):
        state=self.update('resume')
        self.assertEqual(state['operator_mode'],'RESUMED')
        self.assertFalse(state['orders_enabled'])
        self.assertFalse(app.order_control_state())
        state=self.update('pause')
        self.assertEqual(state['operator_mode'],'PAUSED')
        self.assertTrue(app.order_control_state())
    def test_resume_never_arms_broker(self):
        self.update('resume')
        from risk_engine import orders_permitted
        self.assertFalse(orders_permitted())
        self.assertFalse(app.health()['orders_enabled'])
    def test_reject_cross_origin(self):
        with self.assertRaises(HTTPException) as ctx:
            self.update('resume',origin='https://other.test')
        self.assertEqual(ctx.exception.status_code,403)
        self.assertTrue(app.order_control_state())
    def test_reject_bad_secret(self):
        with self.assertRaises(HTTPException) as ctx:
            app.order_control_status('wrong-secret')
        self.assertEqual(ctx.exception.status_code,403)
    def test_reject_unknown_action(self):
        with self.assertRaises(HTTPException) as ctx:
            self.update('cancel-all')
        self.assertEqual(ctx.exception.status_code,400)
        self.assertTrue(app.order_control_state())

if __name__=='__main__':
    unittest.main()
