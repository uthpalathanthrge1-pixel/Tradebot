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
        self.account_id = None

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
        # Account discovery is read-only. Never guess if multiple GBP accounts exist.
        accounts = self.get("/accounts").get("accounts", [])
        gbp = [a for a in accounts if str(a.get("currency", "")).upper() == "GBP"]
        if len(gbp) != 1:
            return {
                "configured_account_found": False,
                "reason": "Expected exactly one GBP demo account; manual selection required",
                "gbp_account_count": len(gbp),
                "available_accounts": [
                    {"currency": a.get("currency"), "account_name": a.get("accountName"),
                     "account_type": a.get("accountType")} for a in accounts
                ],
                "no_orders_submitted": True,
            }
        selected = gbp[0]
        # Do not return full account IDs in public/browser responses.
        return {
            "configured_account_found": True,
            "account_currency": selected.get("currency"),
            "account_type": selected.get("accountType"),
            "account_name": selected.get("accountName"),
            "account_id_detected": bool(selected.get("accountId")),
            "available_accounts_count": len(accounts),
            "no_orders_submitted": True,
        }
