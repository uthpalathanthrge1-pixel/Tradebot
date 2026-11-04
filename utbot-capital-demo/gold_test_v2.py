"""V2 Gold demo execution review scaffold.

No broker order is placed by this module. An execution adapter must be
separately reviewed and enabled after explicit authorisation.
"""
import os
import sqlite3
from dataclasses import dataclass

@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason: str

def execution_gate(database_path: str, *, authenticated: bool) -> GateResult:
    """Fail closed until separate V2 approval and verified broker close path."""
    if not authenticated:
        return GateResult(False, "authentication_required")
    if os.environ.get("ENABLE_DEMO_ORDERS", "false").lower() != "false":
        return GateResult(False, "main_orders_must_remain_disabled")
    if os.environ.get("ALLOW_ONE_OFF_GOLD_TEST_V2", "false").lower() != "true":
        return GateResult(False, "v2_not_armed")
    if os.environ.get("V2_CLOSE_API_VERIFIED", "false").lower() != "true":
        return GateResult(False, "broker_close_api_unverified")
    with sqlite3.connect(database_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS one_off_tests_v2 (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL)")
        row = conn.execute("SELECT state FROM one_off_tests_v2 WHERE id=1").fetchone()
    if row:
        return GateResult(False, "v2_already_attempted")
    return GateResult(False, "execution_adapter_not_installed")
