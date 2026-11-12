"""Single-use DEMO API round-trip. Never enabled on ordinary webhook.

Must run with a persistent SQLite path and explicit one-off environment
authorization; only minimum-size Gold, never LIVE.
"""
import os
from decimal import Decimal
from capital import Capital
from execution_ledger import ExecutionLedger
from broker_reconciliation import reconcile_open_confirmation,reconcile_close_confirmation

class OneOffError(RuntimeError): pass

def run_one_off(*,client=None,ledger_path=None,stop_distance=None):
    if os.getenv("ENABLE_DEMO_ORDERS","false").lower()=="true":
        raise OneOffError("unattended_execution_must_remain_disabled")
    if os.getenv("ENABLE_ONE_OFF_API_TEST","false").lower()!="true":
        raise OneOffError("one_off_test_not_armed")
    path=ledger_path or os.getenv("ONE_OFF_LEDGER_PATH","")
    if not (path.startswith("/data/") or path == "/tmp/utbot-one-off-test.sqlite3"):
        raise OneOffError("invalid_test_ledger_path")
    if not os.getenv("CAPITAL_GOLD_EPIC"):
        raise OneOffError("gold_epic_missing")
    if stop_distance is None:
        raise OneOffError("verified_stop_distance_required")
    try:
        stop=Decimal(str(stop_distance))
    except Exception as exc:
        raise OneOffError("invalid_stop_distance") from exc
    if not stop.is_finite() or stop<=0:
        raise OneOffError("invalid_stop_distance")
    broker=client or Capital()
    account=broker.active_account_check()
    if not (account.get("active_account_verified") and
            account.get("account_type")=="CFD" and
            account.get("account_currency")=="GBP"):
        raise OneOffError("demo_account_not_verified")
    if broker.positions():
        raise OneOffError("existing_positions_detected")
    details=broker.market_details(os.environ["CAPITAL_GOLD_EPIC"])
    rules=details.get("dealingRules") or {}
    min_size=rules.get("minDealSize") or {}
    value=min_size.get("value") if isinstance(min_size,dict) else min_size
    if Decimal(str(value))!=Decimal("0.01"):
        raise OneOffError("gold_min_size_not_verified")
    ledger=ExecutionLedger(path)
    if not ledger.claim("ONE_OFF_GOLD_BUY_001_V1"):
        raise OneOffError("test_already_claimed")
    epic=os.environ["CAPITAL_GOLD_EPIC"]
    ledger.audit("open_attempt",{"signal_id":"ONE_OFF_GOLD_BUY_001_V1","epic":epic,"direction":"BUY","size":"0.01"})
    # Never retry mutations on timeouts or ambiguous confirmations.
    result=broker.open_protected_position(epic,"BUY","0.01",str(stop))
    ref=result.get("dealReference")
    if not ref:
        raise OneOffError("open_reference_missing_manual_intervention")
    confirmation=broker.confirm(ref)
    opened=reconcile_open_confirmation(confirmation,broker.positions(),epic,"BUY","0.01")
    deal_id=opened["deal_id"]
    ledger.audit("open_confirmed",{"signal_id":"ONE_OFF_GOLD_BUY_001_V1","deal_id":deal_id})
    ledger.audit("close_attempt",{"signal_id":"ONE_OFF_GOLD_BUY_001_V1","deal_id":deal_id})
    closed=broker.close_position(deal_id)
    close_ref=closed.get("dealReference")
    if not close_ref:
        raise OneOffError("close_reference_missing_manual_intervention")
    reconcile_close_confirmation(broker.confirm(close_ref),broker.positions(),deal_id)
    ledger.audit("close_confirmed",{"signal_id":"ONE_OFF_GOLD_BUY_001_V1","deal_id":deal_id})
    return {"test":"complete","open_confirmed":True,"close_confirmed":True}
