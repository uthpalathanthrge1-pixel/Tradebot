"""Read-only risk evaluation for Capital.com DEMO positions.

No order submission or automatic closing. Unknown currency, stale or missing
P/L, or unexpected positions block execution. Does not arm the risk engine.
"""
from decimal import Decimal, InvalidOperation

class RiskDataError(ValueError):
    pass

def decimal(value):
    try:
        result=Decimal(str(value))
        if not result.is_finite():
            raise RiskDataError('non_finite')
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise RiskDataError('invalid_number')

def inspect(positions, *, realised_gbp, max_loss_gbp=100, expected_deal_ids=None):
    """Evaluate only broker-verified GBP P/L, never assume USD is GBP."""
    expected=set(expected_deal_ids or [])
    observed=set()
    unrealised=Decimal('0')
    reasons=[]
    for item in positions:
        p=item.get('position') or {}
        deal=p.get('dealId')
        if not deal or str(deal) in observed:
            reasons.append('missing_or_duplicate_deal_id')
        else:
            observed.add(str(deal))
        if not expected or str(deal) not in expected:
            reasons.append('unmanaged_or_unknown_position')
        # Broker field mappings are not validated yet: intentionally refuse
        # to infer P/L from ambiguous position fields or quote currencies.
        reasons.append('gbp_unrealised_pnl_mapping_unverified')
    if expected-observed:
        reasons.append('expected_position_not_visible')
    try:
        realised=decimal(realised_gbp)
        threshold=decimal(max_loss_gbp)
        if threshold<=0:
            raise RiskDataError('invalid_loss_limit')
    except RiskDataError:
        reasons.append('invalid_risk_parameters')
        realised=Decimal('0')
        threshold=Decimal('100')
    if realised<=-threshold:
        reasons.append('realised_loss_limit_breached')
    return {'ready_to_trade':False,'must_halt':True,
            'reasons':sorted(set(reasons+['broker_pnl_mapping_and_close_unverified'])),
            'realised_gbp':str(realised),
            'unrealised_gbp':None,
            'combined_gbp':None,
            'open_positions':len(positions),
            'orders_submitted':False}
