"""Dry-run validation of demo close sequencing; does not call Capital.com."""
from reconciliation import opened_deal_ids,wait_for_position,wait_for_absence

def validate_close_sequence(broker, confirmation, *, epic='GOLD',
                            direction='BUY', size='0.01', sleep=lambda _:None):
    """Fake broker only. Fail closed on ambiguity or stale position state."""
    ids=opened_deal_ids(confirmation)
    if confirmation.get('dealStatus')!='ACCEPTED' or len(ids)!=1:
        return {'passed':False,'stage':'open_confirmation','close_attempted':False}
    deal_id=ids[0]
    position,detail=wait_for_position(broker.positions,deal_id,epic,direction,size,
        attempts=5,delay_seconds=0,sleep=sleep)
    if position is None:
        return {'passed':False,'stage':'position_reconciliation',
                'reason':detail['reason'],'close_attempted':False}
    result=broker.close_position(deal_id)
    reference=result.get('dealReference')
    if not reference:
        return {'passed':False,'stage':'close_reference','close_attempted':True}
    close_confirmation=broker.confirm(reference)
    if close_confirmation.get('dealStatus')!='ACCEPTED':
        return {'passed':False,'stage':'close_confirmation','close_attempted':True}
    closed=wait_for_absence(broker.positions,deal_id,attempts=5,
                           delay_seconds=0,sleep=sleep)
    return {'passed':closed,'stage':'complete' if closed else 'position_still_open',
            'close_attempted':True,'close_confirmed':closed}

class FakeBroker:
    def __init__(self, *, visible_after=2, absent_after=2,
                 wrong_deal=False, close_accepted=True):
        self.visible_after=visible_after
        self.absent_after=absent_after
        self.wrong_deal=wrong_deal
        self.close_accepted=close_accepted
        self.polls=0
        self.close_polls=0
        self.close_called_with=None
    def positions(self):
        if self.close_called_with is not None:
            self.close_polls+=1
            if self.close_polls>=self.absent_after:
                return []
        else:
            self.polls+=1
            if self.polls<self.visible_after:
                return []
        return [{'position':{'dealId':'wrong' if self.wrong_deal else 'test-deal',
                             'direction':'BUY','size':'0.01'},
                 'market':{'epic':'GOLD'}}]
    def close_position(self,deal_id):
        self.close_called_with=deal_id
        return {'dealReference':'test-close-reference'}
    def confirm(self,reference):
        return {'dealStatus':'ACCEPTED' if self.close_accepted else 'REJECTED'}

def simulation():
    confirmation={'dealStatus':'ACCEPTED',
                  'affectedDeals':[{'dealId':'test-deal','status':'OPENED'}]}
    return validate_close_sequence(FakeBroker(),confirmation)
