"""Read-only market discovery and conservative GBP margin previews.

Never submits, modifies or closes orders. Missing broker metadata fails closed.
"""
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

MARKETS = {
    "GOLD": {"search": "Gold", "env": "CAPITAL_GOLD_EPIC"},
    "OIL": {"search": "Crude Oil", "env": "CAPITAL_OIL_EPIC"},
    "US500": {"search": "US500", "env": "CAPITAL_US500_EPIC"},
}
MARGIN_TARGET_GBP = Decimal("1500")


def positive(value):
    try:
        number = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        raise ValueError("missing_or_invalid_broker_input")
    if not number.is_finite() or number <= 0:
        raise ValueError("missing_or_invalid_broker_input")
    return number


def margin_preview(*, price, margin_factor_percent, units_per_size,
                   gbp_per_quote_unit, min_size, size_increment,
                   margin_target_gbp=MARGIN_TARGET_GBP):
    """Round DOWN to size increment; return no order-ready claim.

    units_per_size and GBP conversion MUST be independently verified.
    """
    p, pct, units, fx, minimum, step, budget = (
        positive(x) for x in (price, margin_factor_percent, units_per_size,
                              gbp_per_quote_unit, min_size, size_increment,
                              margin_target_gbp))
    per_size = p * (pct / Decimal("100")) * units * fx
    raw = budget / per_size
    size = (raw / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if size < minimum:
        return {"ready": False, "reason": "minimum_size_exceeds_margin_budget",
                "orders_enabled": False}
    margin = size * per_size
    return {"ready": False, "reason": "read_only_estimate_requires_broker_validation",
            "size_preview": str(size), "estimated_margin_gbp": str(margin),
            "target_margin_gbp": str(budget), "orders_enabled": False}


def inspect_market(client, epic):
    """Broker GET only; does not infer a size from incomplete market metadata."""
    if not epic:
        return {"configured": False, "orders_enabled": False}
    details = client.market_details(epic)
    instrument = details.get("instrument") or {}
    snapshot = details.get("snapshot") or {}
    rules = details.get("dealingRules") or {}
    return {
        "configured": True,
        "epic_matches": instrument.get("epic") == epic,
        "name": instrument.get("name"),
        "instrument_type": instrument.get("type"),
        "market_status": snapshot.get("marketStatus"),
        "bid": snapshot.get("bid"),
        "offer": snapshot.get("offer"),
        "contract_size": instrument.get("contractSize"),
        "lot_size": instrument.get("lotSize"),
        "margin_factor": instrument.get("marginFactor"),
        "margin_factor_unit": instrument.get("marginFactorUnit"),
        "min_deal_size": rules.get("minDealSize"),
        "max_deal_size": rules.get("maxDealSize"),
        "size_increment": rules.get("dealSizeIncrement"),
        "currencies": instrument.get("currencies"),
        "size_preview": None,
        "reason": "contract_units_size_increment_fx_and_margin_require_verification",
        "orders_enabled": False,
    }
