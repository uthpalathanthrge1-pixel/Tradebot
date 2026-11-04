"""Guarded DEMO order lifecycle. Not wired to TradingView webhook.

A broker-verified GBP point value is mandatory before any order is sent.
One mutation per signal, no automatic retry on uncertain outcomes.
"""
from demo_order_bridge import plan_signal, calculate_stop_distance
from reconciliation import opened_deal_ids, wait_for_position, wait_for_absence
from decimal import Decimal
import time

class ExecutionUncertain(RuntimeError):
    pass

def confirm_accepted(client, response, expected_action):
    reference=response.get('dealReference')
    if not reference:
        raise ExecutionUncertain('missing_deal_reference')
    confirmation=None
    for _ in range(5):
        try:
            confirmation=client.confirm(reference)
            break
        except Exception as exc:
            if getattr(exc,'status',None)!=404:
                raise ExecutionUncertain('confirmation_failed') from exc
            time.sleep(1)
    if not confirmation or confirmation.get('dealStatus')!='ACCEPTED':
        raise ExecutionUncertain('deal_not_confirmed')
    return confirmation

def execute_signal(client, signal, *, verified_gbp_per_point_per_unit=None,
                   broker_min_stop_distance=None, broker_distance_increment=None,
                   approved=False):
    """A single synchronous DEMO execution; external persistent lock required.

    Not callable by the webhook. Only after the risk ledger is armed and
    broker contract economics and closing semantics have been validated.
    """
    if not approved:
        return {'status':'blocked','reason':'execution_not_armed'}
    from capital import BASE
    if BASE!='https://demo-api-capital.backend-capital.com/api/v1':
        return {'status':'blocked','reason':'demo_only'}
    account=client.account_check()
    if not (account.get('configured_account_found')
            and account.get('account_currency')=='GBP'
            and account.get('account_type')=='CFD'):
        return {'status':'blocked','reason':'account_not_verified'}
    active=client.active_account_check()
    if not active.get('active_account_verified'):
        return {'status':'blocked','reason':'active_session_account_not_verified'}
    stop=calculate_stop_distance(signal,
        verified_gbp_per_point_per_unit=verified_gbp_per_point_per_unit,
        broker_min_stop_distance=broker_min_stop_distance,
        broker_distance_increment=broker_distance_increment)
    market=client.market_details(signal.epic)
    if (market.get('instrument',{}).get('epic')!=signal.epic or
        market.get('snapshot',{}).get('marketStatus')!='TRADEABLE'):
        return {'status':'blocked','reason':'market_not_tradeable'}
    decision=plan_signal(signal,client.positions())
    if decision['action'] in ('HALT','HOLD'):
        return {'status':decision['action'].lower(),'reason':decision.get('reason')}
    if decision['action']=='CLOSE_THEN_OPEN':
        deal_id=decision['close_deal_id']
        response=client.close_position(deal_id)
        confirmation=confirm_accepted(client,response,'CLOSE')
        if not wait_for_absence(client.positions,deal_id):
            raise ExecutionUncertain('close_not_reconciled')
        if client.positions():
            raise ExecutionUncertain('unexpected_positions_after_close')
    else:
        if client.positions():
            raise ExecutionUncertain('unexpected_positions_before_open')
    opened=client.open_protected_position(signal.epic,signal.direction,signal.size,
                                           stop['stop_distance'])
    confirmation=confirm_accepted(client,opened,'OPEN')
    ids=opened_deal_ids(confirmation)
    if len(ids)!=1:
        raise ExecutionUncertain('ambiguous_opened_deals')
    matched,diag=wait_for_position(client.positions,ids[0],signal.epic,
                                   signal.direction,signal.size)
    if matched is None:
        raise ExecutionUncertain('open_not_reconciled')
    # Broker protection must be observed, not inferred from request success.
    details=matched.get('position') or {}
    if details.get('stopLevel') is None and details.get('stopDistance') is None:
        raise ExecutionUncertain('broker_stop_not_observed')
    return {'status':'opened_verified','direction':signal.direction,
            'stop_distance':stop['stop_distance'],
            'planned_loss_gbp':stop['planned_loss_gbp']}
