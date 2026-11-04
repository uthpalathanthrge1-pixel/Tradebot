"""Strict validation of normalized Capital.com DEMO closed-trade records.

This module does not call Capital.com, submit orders, or change trading state.
Raw broker history must be inspected and mapped separately after verifying its
schema and currency semantics. Never infer GBP from an account's base currency.
"""
from decimal import Decimal, InvalidOperation


class UnverifiedTransaction(ValueError):
    """Raised when a closed-trade record lacks verifiable evidence."""


def _decimal(value):
    if isinstance(value, bool) or value is None:
        raise UnverifiedTransaction("invalid_amount")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise UnverifiedTransaction("invalid_amount") from None
    if not amount.is_finite():
        raise UnverifiedTransaction("nonfinite_amount")
    return amount


def normalize_close(record):
    """Validate an already verified, canonical closed-position record.

    This is NOT a parser for raw Capital.com API transaction payloads.
    The upstream adapter must verify deal identity, fees, currency, and the
    broker's close event before setting the explicit verification fields.
    """
    if not isinstance(record, dict):
        raise UnverifiedTransaction("invalid_record")
    if record.get("source") != "capital_demo_confirmed":
        raise UnverifiedTransaction("unverified_source")
    if record.get("transaction_type") != "POSITION_CLOSED":
        raise UnverifiedTransaction("not_a_close")
    if record.get("net_pnl_currency") != "GBP":
        raise UnverifiedTransaction("unverified_currency")
    if record.get("net_includes_fees") is not True:
        raise UnverifiedTransaction("net_fees_unverified")
    if not record.get("deal_id") or not record.get("closed_at"):
        raise UnverifiedTransaction("missing_identity_or_timestamp")
    pnl = _decimal(record.get("net_pnl"))
    price = _decimal(record.get("exit_price"))
    if price <= 0:
        raise UnverifiedTransaction("invalid_exit_price")
    return {
        "deal_id": str(record["deal_id"]),
        "closed_at": str(record["closed_at"]),
        "exit_price": str(price),
        "net_pnl_gbp": str(pnl),
        "currency": "GBP",
        "broker_verified": True,
    }


def summarize_raw_history(payload):
    """Inspect transaction field names without exposing trade identifiers."""
    if not isinstance(payload, dict):
        return {"schema_valid": False, "record_count": 0, "field_names": []}
    rows = payload.get("transactions")
    if not isinstance(rows, list):
        return {"schema_valid": False, "record_count": 0, "field_names": []}
    keys = sorted({
        key for row in rows[:30] if isinstance(row, dict)
        for key in row if isinstance(key, str)
    })
    return {
        "schema_valid": True,
        "record_count": len(rows),
        "field_names": keys[:80],
        "note": "Field names only; no trades imported or assumed to be GBP.",
    }
