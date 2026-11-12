"""Wire DEMO execution coordinator to a durable ledger, fail closed by default.

This module is deliberately not connected to public TradingView webhook.
"""
import os
from execution_coordinator import execute_reversal, ExecutionHalted
from execution_ledger import ExecutionLedger

def execute_with_ledger(client,intent,*,approved=False,db_path=None):
    if not approved:
        raise ExecutionHalted("execution_not_approved")
    path=db_path or os.getenv("EXECUTION_LEDGER_PATH","")
    if not path or path.startswith("/tmp/"):
        raise ExecutionHalted("persistent_execution_store_required")
    if not os.path.isabs(path):
        raise ExecutionHalted("absolute_execution_store_path_required")
    # Persistent storage validation is an infrastructure requirement; an
    # arbitrary absolute path is NOT sufficient to arm the public webhook.
    ledger=ExecutionLedger(path)
    return execute_reversal(client,intent,approved=True,
                            claim=ledger.claim,audit=ledger.audit)
