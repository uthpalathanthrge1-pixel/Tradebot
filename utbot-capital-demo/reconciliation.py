"""Strict, bounded reconciliation of a confirmed demo deal to a broker position."""
from decimal import Decimal, InvalidOperation
import time


def _matching(position, deal_id, epic, direction, size):
    details = position.get('position') or {}
    market = position.get('market') or {}
    if str(details.get('dealId', '')) != str(deal_id):
        return False
    if str(market.get('epic', '')).upper() != epic.upper():
        return False
    if str(details.get('direction', '')).upper() != direction.upper():
        return False
    try:
        return Decimal(str(details.get('size'))) == Decimal(str(size))
    except (InvalidOperation, TypeError):
        return False


def wait_for_position(fetch_positions, deal_id, epic, direction, size,
                      attempts=12, delay_seconds=2, sleep=time.sleep):
    """Return only an exact unique match; never fall back to epic-only matching.

    On timeout return a non-sensitive diagnostic. API failures propagate so the
    caller halts and requests manual reconciliation, without retrying orders.
    """
    if not deal_id:
        return None, {'reason': 'missing_confirmed_deal_id'}
    for attempt in range(attempts):
        positions = fetch_positions()
        matches = [p for p in positions
                   if _matching(p, deal_id, epic, direction, size)]
        if len(matches) == 1:
            return matches[0], {'reason': 'matched', 'poll': attempt + 1}
        if len(matches) > 1:
            return None, {'reason': 'ambiguous_duplicate_deal_id'}
        if attempt + 1 < attempts:
            sleep(delay_seconds)
    return None, {'reason': 'no_exact_position_match_after_polling',
                  'polls': attempts}


def opened_deal_ids(confirmation):
    """Return unique OPENED position IDs; order reference is not position ID."""
    deals = confirmation.get('affectedDeals') or []
    ids = [str(d['dealId']) for d in deals
           if d.get('status') == 'OPENED' and d.get('dealId')]
    ids = list(dict.fromkeys(ids))
    if ids:
        return ids
    # Some broker confirmations contain only the permanent dealId.
    direct = confirmation.get('dealId')
    return [str(direct)] if direct else []


def wait_for_absence(fetch_positions, deal_id, attempts=12,
                     delay_seconds=2, sleep=time.sleep):
    """Poll until a previously verified position disappears."""
    if not deal_id:
        return False
    for attempt in range(attempts):
        positions = fetch_positions()
        if not any(str((p.get('position') or {}).get('dealId')) == str(deal_id)
                   for p in positions):
            return True
        if attempt + 1 < attempts:
            sleep(delay_seconds)
    return False
