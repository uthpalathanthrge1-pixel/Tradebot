"""SQLite idempotency ledger for DEMO execution attempts.

Requires a persistent, single-writer database before any live wiring.
Unresolved attempts stay claimed after restarts; never auto-replay.
"""
import json
import sqlite3
from datetime import datetime,timezone

class LedgerError(RuntimeError): pass

class ExecutionLedger:
    def __init__(self,path):
        self.path=path
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS execution_claims
                (signal_id TEXT PRIMARY KEY, claimed_at TEXT NOT NULL, status TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS execution_audit
                (id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id TEXT NOT NULL,
                 created_at TEXT NOT NULL, event TEXT NOT NULL, payload TEXT NOT NULL)""")
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA synchronous=FULL")
        return db
    def claim(self,signal_id):
        if not isinstance(signal_id,str) or not signal_id or len(signal_id)>200:
            raise LedgerError("invalid_signal_id")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("INSERT INTO execution_claims VALUES (?,?,?)",
                    (signal_id,datetime.now(timezone.utc).isoformat(),"CLAIMED"))
            except sqlite3.IntegrityError:
                db.rollback()
                return False
            db.commit()
            return True
    def audit(self,event,fields):
        if not isinstance(fields,dict) or not fields.get("signal_id"):
            raise LedgerError("missing_signal_id")
        if event not in ("close_attempt","close_confirmed","open_attempt","open_confirmed"):
            raise LedgerError("unsupported_event")
        payload=json.dumps(fields,sort_keys=True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO execution_audit(signal_id,created_at,event,payload) VALUES (?,?,?,?)",
                (fields["signal_id"],datetime.now(timezone.utc).isoformat(),event,payload))
            db.commit()
    def recent(self,limit=30):
        with self.connect() as db:
            return db.execute("SELECT signal_id,created_at,event,payload FROM execution_audit ORDER BY id DESC LIMIT ?",
                              (min(max(int(limit),1),30),)).fetchall()
