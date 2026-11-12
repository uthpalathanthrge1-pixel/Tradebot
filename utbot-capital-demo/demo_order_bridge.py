"""Capital.com DEMO-only signal-reversal planning, with execution disabled.

A GBP 50 planned-loss stop is mandatory for future orders; no TP.\nAn opposite signal means close the exact verified
position first; a new position must never open before confirmed closure.
No broker POST or DELETE is performed by this module.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

@dataclass(frozen=True)
class Signal:
    epic: str
    direction: str
    size: str
    max_planned_loss_gbp: str = '50'

def validate_signal(payload):
    if not isinstance(payload, dict):
        raise ValueError('invalid_payload')
    if payload.get('epic') != 'GOLD' or payload.get('direction') not in ('BUY','SELL'):
        raise ValueError('unsupported_market_or_direction')
    try:
        size=Decimal(str(payload.get('size')))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('invalid_size')
    if not size.is_finite() or size != Decimal('0.01'):
        raise ValueError('invalid_size')
    return Signal('GOLD',payload['direction'],'0.01')

def calculate_stop_distance(signal, *, verified_gbp_per_point_per_unit,
                            broker_min_stop_distance, broker_distance_increment):
    """Fail closed unless broker-verified point value supports a <= GBP50 stop.

    Returns a positive stopDistance for a broker-protected order. The caller
    must validate broker-specific stop rules and attach it atomically to OPEN.
    Stop orders do not guarantee a GBP50 realised loss during gaps/slippage.
    """
    try:
        point_value=Decimal(str(verified_gbp_per_point_per_unit))
        minimum=Decimal(str(broker_min_stop_distance))
        increment=Decimal(str(broker_distance_increment))
        risk=Decimal(signal.max_planned_loss_gbp)
        size=Decimal(signal.size)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('unverified_stop_inputs')
    if not all(x.is_finite() and x>0 for x in (point_value,minimum,increment,risk,size)):
        raise ValueError('unverified_stop_inputs')
    raw=risk/(point_value*size)
    distance=(raw/increment).to_integral_value(rounding=ROUND_FLOOR)*increment
    if distance<minimum:
        raise ValueError('minimum_stop_exceeds_50_gbp_risk')
    return {'stop_distance':format(distance,'f'),
            'planned_loss_gbp':format(distance*point_value*size,'.2f'),
            'max_planned_loss_gbp':'50', 'take_profit':None}

def plan_signal(signal, positions):
    """Pure decision function. Never treats an ambiguous broker state as flat."""
    if not isinstance(positions,list):
        return {'action':'HALT','reason':'invalid_broker_positions'}
    if len(positions)>1:
        return {'action':'HALT','reason':'multiple_positions'}
    if not positions:
        return {'action':'OPEN','direction':signal.direction}
    item=positions[0]
    details=item.get('position') or {}
    market=item.get('market') or {}
    deal_id=details.get('dealId')
    direction=details.get('direction')
    try:
        size=Decimal(str(details.get('size')))
    except (InvalidOperation, TypeError, ValueError):
        size=None
    if (market.get('epic')!=signal.epic or direction not in ('BUY','SELL')
            or not deal_id or size!=Decimal(signal.size)):
        return {'action':'HALT','reason':'unrecognised_position'}
    if direction==signal.direction:
        return {'action':'HOLD','reason':'same_direction'}
    return {'action':'CLOSE_THEN_OPEN','close_deal_id':str(deal_id),
            'next_direction':signal.direction,
            'requires_confirmed_close':True}

class DemoOrderBridge:
    def __init__(self,client=None):
        self.client=client

    def preview(self,signal):
        from capital import Capital
        broker=self.client or Capital()
        account=broker.active_account_check()
        if not (account.get('active_account_verified') and
                account.get('account_currency')=='GBP' and
                account.get('account_type')=='CFD'):
            return {'action':'HALT','reason':'gbp_demo_account_not_verified',
                    'orders_submitted':False}
        result=plan_signal(signal,broker.positions())
        return {**result,'orders_submitted':False}

    def submit(self,signal,*,gate_approved=False):
        return {'submitted':False,'reason':'execution_adapter_not_installed'}

def verify_open_confirmation(confirmation, positions, *, epic, direction, size):
    """Verify an accepted broker deal against the current position snapshot.

    This is a pure read-only reconciliation helper, NOT authority to place an order.
    An accepted confirmation alone is insufficient without an exact position match.
    """
    if not isinstance(confirmation, dict) or not isinstance(positions, list):
        return {'verified': False, 'reason': 'invalid_broker_response'}
    if confirmation.get('dealStatus') != 'ACCEPTED':
        return {'verified': False, 'reason': 'deal_not_accepted'}
    deal_id = confirmation.get('dealId')
    if not isinstance(deal_id, str) or not deal_id:
        return {'verified': False, 'reason': 'deal_id_missing'}
    matches = []
    for item in positions:
        if not isinstance(item, dict):
            return {'verified': False, 'reason': 'malformed_position'}
        position, market = item.get('position'), item.get('market')
        if not isinstance(position, dict) or not isinstance(market, dict):
            return {'verified': False, 'reason': 'malformed_position'}
        if position.get('dealId') == deal_id:
            matches.append((position, market))
    if len(matches) != 1:
        return {'verified': False, 'reason': 'position_not_uniquely_found'}
    position, market = matches[0]
    try:
        actual = Decimal(str(position.get('size')))
        expected = Decimal(str(size))
    except (InvalidOperation, TypeError, ValueError):
        return {'verified': False, 'reason': 'invalid_position_size'}
    if (not actual.is_finite() or not expected.is_finite() or
            actual != expected or position.get('direction') != direction or
            market.get('epic') != epic):
        return {'verified': False, 'reason': 'position_mismatch'}
    return {'verified': True, 'deal_id': deal_id}

def verify_close_confirmation(confirmation, positions, *, deal_id):
    """Require broker acceptance AND absence of the exact closed deal ID."""
    if not isinstance(confirmation, dict) or not isinstance(positions, list):
        return {'verified': False, 'reason': 'invalid_broker_response'}
    if confirmation.get('dealStatus') != 'ACCEPTED':
        return {'verified': False, 'reason': 'close_not_accepted'}
    if confirmation.get('dealId') != deal_id:
        return {'verified': False, 'reason': 'close_deal_mismatch'}
    for item in positions:
        if not isinstance(item, dict) or not isinstance(item.get('position'), dict):
            return {'verified': False, 'reason': 'malformed_position'}
        if item['position'].get('dealId') == deal_id:
            return {'verified': False, 'reason': 'position_still_open'}
    return {'verified': True, 'deal_id': deal_id}
