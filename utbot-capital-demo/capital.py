import os
import requests

BASE = 'https://demo-api-capital.backend-capital.com/api/v1'

class Capital:
    def __init__(self):
        self.http = requests.Session()
        self.tokens = {}

    def request(self, method, path, **kwargs):
        if not self.tokens:
            self.login()
        r = self.http.request(method, BASE + path, headers=self.tokens, timeout=8, **kwargs)
        if r.status_code in (401, 403):
            self.login()
            r = self.http.request(method, BASE + path, headers=self.tokens, timeout=8, **kwargs)
        r.raise_for_status()
        return r.json() if r.content else {}

    def login(self):
        r = self.http.post(BASE + '/session', headers={'X-CAP-API-KEY': os.environ['CAPITAL_API_KEY']}, json={
            'identifier': os.environ['CAPITAL_IDENTIFIER'],
            'password': os.environ['CAPITAL_API_PASSWORD'],
            'encryptedPassword': False
        }, timeout=8)
        r.raise_for_status()
        self.tokens = {'CST': r.headers['CST'], 'X-SECURITY-TOKEN': r.headers['X-SECURITY-TOKEN']}
        account = os.environ['CAPITAL_DEMO_ACCOUNT_ID']
        r = self.http.put(BASE + '/session', headers=self.tokens, json={'accountId': account}, timeout=8)
        r.raise_for_status()

    def positions(self):
        return self.request('GET', '/positions').get('positions', [])

    def close(self, deal_id):
        return self.request('DELETE', f'/positions/{deal_id}')

    def open(self, epic, direction, size):
        return self.request('POST', '/positions', json={'epic': epic, 'direction': direction, 'size': size})

    def confirm(self, ref):
        return self.request('GET', f'/confirms/{ref}')

    def preferences(self):
        return self.request('GET', '/accounts/preferences')
