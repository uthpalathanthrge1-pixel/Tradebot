"""One-use Gold DEMO execution preparation. NO BROKER MUTATION.

This module intentionally contains no Capital.open_position/close_position calls.
It creates an immutable proposal and reserves a single attempt in SQLite;
a separate reviewed broker adapter and fresh user approval are required.
"""
import os
import sqlite3
import secrets
from dataclasses import dataclass

@dataclass(frozen=True)
class Decision:
    permitted: bool
    reason: str

def prepare_once(db_path, *, authenticated, proposal_id, explicit_preparation_approval):
    if not authenticated:
        return Decision(False, "authentication_required")
    if not explicit_preparation_approval:
        return Decision(False, "preparation_approval_required")
    if not proposal_id or len(proposal_id) > 128:
        return Decision(False, "invalid_proposal_id")
    if os.getenv("ENABLE_DEMO_ORDERS", "false").lower() != "false":
        return Decision(False, "main_orders_must_remain_disabled")
    with sqlite3.connect(db_path, timeout=10, isolation_level=None) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            risk = conn.execute("SELECT halted FROM risk_state WHERE id=1").fetchone()
            old = conn.execute("SELECT state FROM one_off_tests WHERE id=1").fetchone()
            if risk is None or not bool(risk[0]):
                conn.execute("ROLLBACK")
                return Decision(False, "risk_halt_not_verified")
            if old is None or old[0] != "position_reconciliation_failed":
                conn.execute("ROLLBACK")
                return Decision(False, "previous_test_lock_not_verified")
            conn.execute("""CREATE TABLE IF NOT EXISTS gold_v2_preparations
                (id INTEGER PRIMARY KEY CHECK(id=1), proposal_id TEXT NOT NULL,
                 status TEXT NOT NULL CHECK(status='prepared_no_execution'))""")
            existing = conn.execute("SELECT proposal_id FROM gold_v2_preparations WHERE id=1").fetchone()
            if existing:
                conn.execute("ROLLBACK")
                return Decision(False, "already_prepared_no_second_attempt")
            conn.execute("INSERT INTO gold_v2_preparations VALUES (1,?,'prepared_no_execution')", (proposal_id,))
            conn.execute("COMMIT")
            return Decision(False, "prepared_no_execution_adapter")
        except Exception:
            conn.execute("ROLLBACK")
            raise

def status(db_path):
    with sqlite3.connect(db_path) as conn:
        row=conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gold_v2_preparations'").fetchone()
        prepared=bool(row and conn.execute("SELECT 1 FROM gold_v2_preparations WHERE id=1").fetchone())
    return {"prepared":prepared,"execution_available":False,
            "orders_submitted":False,"main_bot_enabled":False}
