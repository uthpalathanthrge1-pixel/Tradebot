"""Capital.com DEMO read-only account verification adapter.
Never send orders until account and risk engine are separately validated.
"""
import os
import requests

class CapitalCheckError(Exception):
    def __init__(self, stage, status=None):
        super().__init__(stage)
        self.stage = stage
        self.status = status

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
        if not r.ok:
            raise CapitalCheckError("session_login", r.status_code)
        if not r.headers.get("CST") or not r.headers.get("X-SECURITY-TOKEN"):
            raise CapitalCheckError("session_tokens_missing", r.status_code)
        self.tokens = {
            "CST": r.headers["CST"],
            "X-SECURITY-TOKEN": r.headers["X-SECURITY-TOKEN"],
        }

    def get(self, path):
        if not self.tokens:
            self.login()
        r = self.http.get(BASE + path, headers={**self.tokens, "X-CAP-API-KEY": os.environ["CAPITAL_API_KEY"]}, timeout=10)
        if r.status_code in (401, 403):
            self.login()
            r = self.http.get(BASE + path, headers={**self.tokens, "X-CAP-API-KEY": os.environ["CAPITAL_API_KEY"]}, timeout=10)
        if not r.ok:
            raise CapitalCheckError("accounts_lookup", r.status_code)
        try:
            return r.json()
        except ValueError:
            raise CapitalCheckError("accounts_invalid_response", r.status_code)

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

    def request(self, method, path, payload=None, params=None):
        """Demo-only API request. Mutating methods must be called only by approved engine."""
        if not self.tokens:
            self.login()
        headers = {**self.tokens, "X-CAP-API-KEY": os.environ["CAPITAL_API_KEY"]}
        r = self.http.request(method, BASE + path, headers=headers,
                              json=payload, params=params, timeout=12)
        if r.status_code in (401, 403) and method == "GET":
            self.login()
            headers = {**self.tokens, "X-CAP-API-KEY": os.environ["CAPITAL_API_KEY"]}
            r = self.http.request(method, BASE + path, headers=headers,
                                  json=payload, params=params, timeout=12)
        if not r.ok:
            raise CapitalCheckError("broker_" + method.lower(), r.status_code)
        return r.json()

    def market_search(self, query):
        return self.request("GET", "/markets", params={"searchTerm": query})

    def market_details(self, epic):
        from urllib.parse import quote
        return self.request("GET", "/markets/" + quote(epic, safe=""))

    def preferences(self):
        return self.get("/accounts/preferences")

    def positions(self):
        return self.get("/positions").get("positions", [])

    def confirm(self, reference):
        from urllib.parse import quote
        return self.request("GET", "/confirms/" + quote(reference, safe=""))

    def open_position(self, epic, direction, size):
        return self.request("POST", "/positions",
                            {"epic": epic, "direction": direction, "size": size})

    def close_position(self, deal_id):
        from urllib.parse import quote
        return self.request("DELETE", "/positions/" + quote(deal_id, safe=""))

    def activity(self, from_date, to_date):
        """Read-only history lookup with bounded timeout retry.

        This path is GET-only. Never retry POST/DELETE order operations.
        """
        import time
        if not self.tokens:
            self.login()
        params = {"from": from_date, "to": to_date,
                  "pageSize": 10, "pageNumber": 1}
        headers = {**self.tokens, "X-CAP-API-KEY": os.environ["CAPITAL_API_KEY"]}
        for attempt in range(2):
            try:
                response = self.http.get(BASE + "/history/transactions",
                                         headers=headers, params=params,
                                         timeout=(5, 30))
            except requests.exceptions.Timeout:
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise
            if response.status_code in (401, 403) and attempt == 0:
                self.login()
                headers = {**self.tokens,
                           "X-CAP-API-KEY": os.environ["CAPITAL_API_KEY"]}
                continue
            if not response.ok:
                raise CapitalCheckError("history_transactions", response.status_code)
            try:
                return response.json()
            except ValueError:
                raise CapitalCheckError("history_invalid_response", response.status_code)
        raise CapitalCheckError("history_unavailable")
