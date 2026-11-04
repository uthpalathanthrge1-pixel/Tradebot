"""Capital.com DEMO-only signal-to-order adapter, disabled until verified.

No live account URL is accepted. No order submission occurs unless the
independent execution gate is explicitly enabled after integration tests.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from capital import Capital, BASE

@dataclass(frozen=True)
class Signal:
    epic: str
    direction: str
    size: str
    stop_distance: str
    limit_distance: str

def validate_signal(payload):
    if not isinstance(payload, dict):
        raise ValueError('invalid_payload')
    epic=payload.get('epic')
    direction=payload.get('direction')
    if epic != 'GOLD' or direction not in ('BUY','SELL'):
        raise ValueError('unsupported_market_or_direction')
    try:
        size=Decimal(str(payload.get('size')))
        stop=Decimal(str(payload.get('stop_distance')))
        limit=Decimal(str(payload.get('limit_distance')))
    except (InvalidOperation, TypeError):
        raise ValueError('invalid_risk_parameters')
    if size != Decimal('0.01') or stop <= 0 or limit <= 0:
        raise ValueError('invalid_risk_parameters')
    return Signal(epic,direction,str(size),str(stop),str(limit))

class DemoOrderBridge:
    def __init__(self, client=None):
        self.client=client or Capital()

    def submit(self, signal, *, gate_approved=False):
        if not gate_approved:
            return {'submitted':False,'reason':'execution_gate_not_approved'}
        if BASE != 'https://demo-api-capital.backend-capital.com/api/v1':
            raise RuntimeError('demo_endpoint_required')
        # Broker state must be checked immediately before any submission.
        account=self.client.account_check()
        if not (account.get('configured_account_found') and
                account.get('account_currency')=='GBP' and
                account.get('account_type')=='CFD'):
            return {'submitted':False,'reason':'gbp_demo_account_not_verified'}
        if self.client.positions():
            return {'submitted':False,'reason':'existing_positions'}
        # Deliberately no POST until stop/limit semantics, risk budget,
        # persistence and close supervision are fully validated.
        return {'submitted':False,'reason':'protected_order_adapter_not_validated'}
