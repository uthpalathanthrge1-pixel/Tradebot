"""DEMO-only close-and-reverse execution coordinator.

Not wired to the webhook or armed for orders. Broker mutations require a
separately reviewed operator gate and a persistent idempotency store.
"""
from dataclasses import dataclass
from decimal import Decimal
from broker_reconciliation import (reconcile_open_confirmation,
                                   reconcile_close_confirmation,
                                   ReconciliationError)

class ExecutionHalted(RuntimeError):
    pass

@dataclass(frozen=True)
class OrderIntent:
    epic: str
    direction: str
    size: str
    stop_distance: str
    signal_id: str

def execute_reversal(client, intent, *, approved=False, claim=None, audit=None):
    """Fail closed on any ambiguous broker response; never retry mutations.

    claim(signal_id) must atomically persist a unique signal before any order.
    audit(event, fields) must durably persist an attempt BEFORE its mutation.
    """
    if not approved:
        raise ExecutionHalted("execution_not_approved")
    if not callable(claim) or not callable(audit):
        raise ExecutionHalted("durable_idempotency_unavailable")
    if intent.direction not in ("BUY", "SELL") or not intent.epic or not intent.signal_id:
        raise ExecutionHalted("invalid_intent")
    try:
        size, stop = Decimal(intent.size), Decimal(intent.stop_distance)
    except Exception as exc:
        raise ExecutionHalted("invalid_order_parameters") from exc
    if not all(x.is_finite() and x > 0 for x in (size, stop)):
        raise ExecutionHalted("invalid_order_parameters")
    account = client.active_account_check()
    if not (account.get("active_account_verified")
            and account.get("account_type") == "CFD"
            and account.get("account_currency") == "GBP"):
        raise ExecutionHalted("demo_account_not_verified")
    positions = client.positions()
    if not isinstance(positions, list):
        raise ExecutionHalted("positions_unavailable")
    if len(positions) > 1:
        raise ExecutionHalted("multiple_positions")
    prior = None
    if positions:
        item = positions[0]
        p, m = item.get("position"), item.get("market")
        if not isinstance(p, dict) or not isinstance(m, dict):
            raise ExecutionHalted("malformed_position")
        if (m.get("epic") != intent.epic or p.get("direction") not in ("BUY","SELL")
                or not p.get("dealId") or Decimal(str(p.get("size"))) != size):
            raise ExecutionHalted("unrecognised_position")
        if p["direction"] == intent.direction:
            return {"action":"HOLD","deal_id":p["dealId"]}
        prior = p["dealId"]
    if not claim(intent.signal_id):
        raise ExecutionHalted("duplicate_or_unclaimed_signal")
    if prior:
        audit("close_attempt", {"signal_id":intent.signal_id,"deal_id":prior})
        result = client.close_position(prior)
        reference = result.get("dealReference")
        if not reference:
            raise ExecutionHalted("close_reference_missing")
        confirmation = client.confirm(reference)
        try:
            reconcile_close_confirmation(confirmation, client.positions(), prior)
        except ReconciliationError as exc:
            raise ExecutionHalted("close_not_reconciled") from exc
        audit("close_confirmed", {"signal_id":intent.signal_id,"deal_id":prior})
    audit("open_attempt", {"signal_id":intent.signal_id,"epic":intent.epic,
                           "direction":intent.direction,"size":intent.size})
    result = client.open_protected_position(intent.epic,intent.direction,
                                             intent.size,intent.stop_distance)
    reference = result.get("dealReference")
    if not reference:
        raise ExecutionHalted("open_reference_missing")
    confirmation = client.confirm(reference)
    try:
        verified = reconcile_open_confirmation(confirmation,client.positions(),
                                                 intent.epic,intent.direction,intent.size)
    except ReconciliationError as exc:
        raise ExecutionHalted("open_not_reconciled") from exc
    audit("open_confirmed",{"signal_id":intent.signal_id,"deal_id":verified["deal_id"]})
    return {"action":"OPEN_CONFIRMED","deal_id":verified["deal_id"]}
