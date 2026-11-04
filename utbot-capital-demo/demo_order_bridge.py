"""Capital.com DEMO-only signal-reversal planning, with execution disabled.

No SL/TP is attached. An opposite signal means close the exact verified
position first; a new position must never open before confirmed closure.
No broker POST or DELETE is performed by this module.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

@dataclass(frozen=True)
class Signal:
    epic: str
    direction: str
    size: str

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
        account=broker.account_check()
        if not (account.get('configured_account_found') and
                account.get('account_currency')=='GBP' and
                account.get('account_type')=='CFD'):
            return {'action':'HALT','reason':'gbp_demo_account_not_verified',
                    'orders_submitted':False}
        result=plan_signal(signal,broker.positions())
        return {**result,'orders_submitted':False}

    def submit(self,signal,*,gate_approved=False):
        return {'submitted':False,'reason':'execution_adapter_not_installed'}
