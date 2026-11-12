"""Strict read-only broker reconciliation helpers for DEMO testing.

These functions do not submit, close, retry or infer broker orders.
"""
from decimal import Decimal, InvalidOperation

class ReconciliationError(ValueError):
    pass

def _size(value):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ReconciliationError("invalid_size")
    if not n.is_finite() or n <= 0:
        raise ReconciliationError("invalid_size")
    return n

def reconcile_open_confirmation(confirmation, positions, epic, direction, size):
    """Require accepted broker confirmation and exactly one matching open deal."""
    if not isinstance(confirmation, dict) or confirmation.get("dealStatus") != "ACCEPTED":
        raise ReconciliationError("order_not_confirmed")
    deal_id = confirmation.get("dealId")
    if not isinstance(deal_id, str) or not deal_id:
        raise ReconciliationError("missing_deal_id")
    if not isinstance(positions, list):
        raise ReconciliationError("positions_unavailable")
    matches = [p for p in positions if isinstance(p, dict)
               and isinstance(p.get("position"), dict)
               and isinstance(p.get("market"), dict)
               and p["position"].get("dealId") == deal_id
               and p["market"].get("epic") == epic
               and p["position"].get("direction") == direction
               and _size(p["position"].get("size")) == _size(size)]
    if len(matches) != 1:
        raise ReconciliationError("position_reconciliation_failed")
    return {"deal_id": deal_id, "confirmed": True}

def reconcile_close_confirmation(confirmation, positions, deal_id):
    """Require accepted close and absence of that deal in fresh broker positions."""
    if not isinstance(confirmation, dict) or confirmation.get("dealStatus") != "ACCEPTED":
        raise ReconciliationError("close_not_confirmed")
    if not isinstance(positions, list):
        raise ReconciliationError("positions_unavailable")
    if any(isinstance(p, dict) and isinstance(p.get("position"), dict)
           and p["position"].get("dealId") == deal_id for p in positions):
        raise ReconciliationError("position_still_open")
    return {"deal_id": deal_id, "closed_confirmed": True}
