"""Read-only, redacted Capital.com confirmation diagnostics."""
import re
from capital import Capital

REFERENCE=re.compile(r"^[A-Za-z0-9_-]{1,100}$")

def inspect_confirmation(reference,client=None):
    if not isinstance(reference,str) or not REFERENCE.fullmatch(reference):
        raise ValueError("invalid_deal_reference")
    broker=client if client is not None else Capital()
    account=broker.active_account_check()
    if not account.get("active_account_verified") or account.get("account_type")!="CFD":
        raise ValueError("demo_account_not_verified")
    response=broker.confirm(reference)
    if not isinstance(response,dict):
        raise ValueError("invalid_confirmation_response")
    # Do not expose raw broker responses, identifiers, tokens or free text.
    allowed=("dealStatus","direction","epic","size","status","reason")
    result={k:response.get(k) for k in allowed if k in response
            and isinstance(response.get(k),(str,int,float,bool))}
    result["deal_id_present"]=bool(response.get("dealId"))
    result["deal_reference_present"]=bool(response.get("dealReference"))
    result["response_fields"]=sorted(k for k in response if isinstance(k,str))[:40]
    return result
