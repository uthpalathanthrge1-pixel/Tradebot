"""Read-only broker position shape diagnostics. Never sends orders.

Do not log account IDs, tokens, deal IDs, or full broker payloads.
"""
from decimal import Decimal, InvalidOperation

def _number(value):
    try:
        n=Decimal(str(value))
        return str(n) if n.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None

def describe_positions(positions):
    result=[]
    for item in positions:
        p=item.get('position') or {}
        m=item.get('market') or {}
        result.append({
            'deal_id_present':bool(p.get('dealId')),
            'deal_id_type':type(p.get('dealId')).__name__,
            'epic':str(m.get('epic') or '')[:60],
            'direction':str(p.get('direction') or '')[:10],
            'size':_number(p.get('size')),
            'position_field_names':sorted(k for k in p if isinstance(k,str))[:40],
            'market_field_names':sorted(k for k in m if isinstance(k,str))[:40],
        })
    return result[:20]

def validate_broker_position(position, *, deal_id, epic, direction, size):
    p=position.get('position') or {}
    m=position.get('market') or {}
    if not deal_id or str(p.get('dealId'))!=str(deal_id):
        return False
    if str(m.get('epic','')).upper()!=str(epic).upper():
        return False
    if str(p.get('direction','')).upper()!=str(direction).upper():
        return False
    try:
        return Decimal(str(p.get('size')))==Decimal(str(size))
    except (InvalidOperation,ValueError,TypeError):
        return False
