"""Capital.com DEMO read-only account verification adapter.
Never send orders until account and risk engine are separately validated.
"""
import os
import requests

BASE = "https://demo-api-capital.backend-capital.com/api/v1"

class Capital:
    def __init__(self):
        self.http = requests.Session()
        self.tokens = {}
        self.account_id = os.environ["CAPITAL_DEMO_ACCOUNT_ID"]

    def login(self):
        r = self.http.post(
            BASE + "/session",
            headers={"X-CAP-API-KEY": os.environ["CAPITAL_API_KEY"]},
            json={
                "identifier": os.environ["CAPITAL_IDENTIFIER"],
                "password": os.environ["CAPITAL_API_PASSWORD"],
                "encryptedPassword": False,
            },
            timeout=10,
        )
        r.raise_for_status()
        self.tokens = {
            "CST": r.headers["CST"],
            "X-SECURITY-TOKEN": r.headers["X-SECURITY-TOKEN"],
        }
        r = self.http.put(
            BASE + "/session",
            headers=self.tokens,
            json={"accountId": self.account_id},
            timeout=10,
        )
        r.raise_for_status()

    def get(self, path):
        if not self.tokens:
            self.login()
        r = self.http.get(BASE + path, headers=self.tokens, timeout=10)
        if r.status_code in (401, 403):
            self.login()
            r = self.http.get(BASE + path, headers=self.tokens, timeout=10)
        r.raise_for_status()
        return r.json()

    def account_check(self):
        accounts = self.get("/accounts").get("accounts", [])
        selected = next((a for a in accounts if str(a.get("accountId")) == self.account_id), None)
        if selected is None:
            raise ValueError("Configured demo account ID is not in the authenticated account list")
        preferences = self.get("/accounts/preferences")
        positions = self.get("/positions").get("positions", [])
        return {
            "configured_account_found": True,
            "account_currency": selected.get("currency"),
            "account_type": selected.get("accountType"),
            "account_name": selected.get("accountName"),
            "leverages": preferences.get("leverages"),
            "hedging_mode": preferences.get("hedgingMode"),
            "open_position_count": len(positions),
            "no_orders_submitted": True,
        }
