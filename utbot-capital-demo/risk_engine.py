"""Fail-closed demo execution engine. No orders unless all explicit gates pass.

This module is intentionally NOT wired to the webhook until the broker's
deal-size and P&L currency semantics are verified with controlled demo orders.
"""
import os
import sqlite3
import threading
from decimal import Decimal, InvalidOperation

class RiskError(Exception):
    pass

class RiskLedger:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS risk_state
              (id INTEGER PRIMARY KEY CHECK(id=1), halted INTEGER NOT NULL,
               realised_gbp TEXT NOT NULL, reason TEXT NOT NULL)""")
            db.execute("INSERT OR IGNORE INTO risk_state VALUES (1,1,'0','not_armed')")

    def connection(self):
        return sqlite3.connect(self.path, timeout=10)

    def state(self):
        with self.connection() as db:
            row = db.execute("SELECT halted,realised_gbp,reason FROM risk_state WHERE id=1").fetchone()
        return {'halted': bool(row[0]), 'realised_gbp': Decimal(row[1]), 'reason': row[2]}

    def halt(self, reason):
        with self.lock, self.connection() as db:
            db.execute("UPDATE risk_state SET halted=1,reason=? WHERE id=1", (reason,))

    def add_realised(self, amount_gbp):
        amount = Decimal(str(amount_gbp))
        with self.lock, self.connection() as db:
            db.execute("UPDATE risk_state SET realised_gbp=CAST(realised_gbp AS REAL)+? WHERE id=1", (float(amount),))
            state = self.state()
            if state['realised_gbp'] <= Decimal('-100'):
                self.halt('realised_loss_limit')
        return self.state()

    def evaluate(self, unrealised_gbp):
        # This method accepts only verified GBP net P&L from broker positions.
        pnl = Decimal(str(unrealised_gbp))
        state = self.state()
        net = state['realised_gbp'] + pnl
        if net <= Decimal('-100'):
            self.halt('combined_loss_limit')
        return {'net_gbp': str(net), 'halted': self.state()['halted']}

    def manual_reset(self, no_positions, verified_net_gbp, authorised):
        if not authorised or not no_positions:
            raise RiskError('Reset requires explicit authorisation and zero open bot positions')
        if Decimal(str(verified_net_gbp)) <= Decimal('-100'):
            raise RiskError('Cannot reset while loss threshold is breached')
        with self.lock, self.connection() as db:
            db.execute("UPDATE risk_state SET halted=0,realised_gbp='0',reason='manually_armed' WHERE id=1")


def conservative_size(margin_gbp, margin_percent, price, gbp_per_quote_unit,
                      units_per_size, minimum, increment):
    """Broker-verified parameters only. Round DOWN, never exceed margin target."""
    try:
        m, pct, p, fx, unit, min_size, step = [
            Decimal(str(x)) for x in
            (margin_gbp, margin_percent, price, gbp_per_quote_unit,
             units_per_size, minimum, increment)]
    except (InvalidOperation, ValueError):
        raise RiskError('Invalid sizing inputs')
    if min(m, pct, p, fx, unit, min_size, step) <= 0:
        raise RiskError('Sizing inputs must be positive')
    raw = m / ((pct / Decimal('100')) * p * fx * unit)
    size = (raw // step) * step
    if size < min_size:
        raise RiskError('Minimum deal size exceeds allowed margin')
    return {'size': str(size), 'estimated_margin_gbp': str(
        size * p * fx * unit * pct / Decimal('100'))}


def orders_permitted():
    # Hard disable until demo sizing and order-confirmation semantics are tested.
    return False
