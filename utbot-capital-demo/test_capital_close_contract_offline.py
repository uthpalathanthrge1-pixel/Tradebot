"""Offline Capital.com close API contract tests; no network or orders."""
import os
import unittest
from unittest.mock import patch
from capital import Capital, CapitalCheckError, BASE

class Response:
    def __init__(self,status=200,payload=None):
        self.status_code=status
        self.ok=200<=status<300
        self.payload=payload if payload is not None else {'dealReference':'close-ref'}
    def json(self):
        return self.payload

class Session:
    def __init__(self,response):
        self.response=response
        self.calls=[]
    def request(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs))
        return self.response

class CloseContractTests(unittest.TestCase):
    def broker(self,response):
        client=Capital()
        client.tokens={'CST':'test','X-SECURITY-TOKEN':'test'}
        client.http=Session(response)
        return client

    def test_close_uses_single_delete_with_encoded_deal_id(self):
        client=self.broker(Response())
        with patch.dict(os.environ,{'CAPITAL_API_KEY':'test'}):
            result=client.close_position('deal/id')
        self.assertEqual(result['dealReference'],'close-ref')
        self.assertEqual(len(client.http.calls),1)
        method,url,options=client.http.calls[0]
        self.assertEqual(method,'DELETE')
        self.assertEqual(url,BASE+'/positions/deal%2Fid')
        self.assertIsNone(options['json'])

    def test_rejected_close_is_not_retried(self):
        client=self.broker(Response(400,{'errorCode':'invalid.deal'}))
        with patch.dict(os.environ,{'CAPITAL_API_KEY':'test'}):
            with self.assertRaises(CapitalCheckError):
                client.close_position('deal-123')
        self.assertEqual(len(client.http.calls),1)

    def test_missing_reference_not_fabricated(self):
        client=self.broker(Response(payload={}))
        with patch.dict(os.environ,{'CAPITAL_API_KEY':'test'}):
            self.assertNotIn('dealReference',client.close_position('deal-123'))

if __name__=='__main__':
    unittest.main()
