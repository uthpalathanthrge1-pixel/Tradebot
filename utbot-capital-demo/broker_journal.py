"""Broker-fill journal for verified DEMO executions, separate from signal paper trades.

Only verified GBP net P/L may be recorded. No broker orders are submitted.
"""
import sqlite3
from decimal import Decimal, InvalidOperation

def _money(value):
    try:
        x=Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        raise ValueError('Invalid GBP amount')
    if not x.is_finite():
        raise ValueError('Invalid GBP amount')
    return str(x)

def init(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS broker_trades (
        deal_id TEXT PRIMARY KEY, symbol TEXT NOT NULL,
        direction TEXT NOT NULL CHECK(direction IN ('BUY','SELL')),
        size TEXT NOT NULL, opened_at TEXT NOT NULL,
        entry_price TEXT NOT NULL,
        closed_at TEXT, exit_price TEXT,
        net_pnl_gbp TEXT, outcome TEXT NOT NULL DEFAULT 'OPEN',
        source TEXT NOT NULL DEFAULT 'capital_demo_verified',
        CHECK ((outcome='OPEN' AND closed_at IS NULL AND net_pnl_gbp IS NULL)
        OR (outcome IN ('WIN','LOSS','BREAKEVEN') AND closed_at IS NOT NULL
        AND net_pnl_gbp IS NOT NULL))
    )""")

def record_open(conn, *, deal_id, symbol, direction, size, opened_at, entry_price):
    if not deal_id or not symbol or direction not in ('BUY','SELL') or not opened_at:
        raise ValueError('Incomplete broker open confirmation')
    for value in (size,entry_price):
        if Decimal(str(value))<=0:
            raise ValueError('Invalid broker size or price')
    init(conn)
    conn.execute("""INSERT INTO broker_trades
      (deal_id,symbol,direction,size,opened_at,entry_price)
      VALUES(?,?,?,?,?,?)""",(deal_id,symbol,direction,str(size),opened_at,str(entry_price)))

def record_close(conn, *, deal_id, closed_at, exit_price, net_pnl_gbp, currency, broker_verified):
    if currency!='GBP' or not broker_verified:
        raise ValueError('GBP broker-verified P/L required')
    if not closed_at or Decimal(str(exit_price))<=0:
        raise ValueError('Invalid broker exit')
    net=_money(net_pnl_gbp)
    outcome='WIN' if Decimal(net)>0 else 'LOSS' if Decimal(net)<0 else 'BREAKEVEN'
    init(conn)
    cur=conn.execute("""UPDATE broker_trades SET closed_at=?,exit_price=?,
        net_pnl_gbp=?,outcome=? WHERE deal_id=? AND outcome='OPEN'""",
        (closed_at,str(exit_price),net,outcome,deal_id))
    if cur.rowcount!=1:
        raise ValueError('Unknown or already-closed deal')
    return outcome

def report(conn, limit=100):
    init(conn)
    rows=conn.execute("""SELECT deal_id,symbol,direction,size,opened_at,entry_price,
       closed_at,exit_price,net_pnl_gbp,outcome FROM broker_trades
       ORDER BY opened_at DESC LIMIT ?""",(limit,)).fetchall()
    keys=('deal_id','symbol','direction','size','opened_at','entry_price',
          'closed_at','exit_price','net_pnl_gbp','outcome')
    trades=[dict(zip(keys,row)) for row in rows]
    wins=sum(t['outcome']=='WIN' for t in trades)
    losses=sum(t['outcome']=='LOSS' for t in trades)
    closed=[t for t in trades if t['outcome']!='OPEN']
    total=sum((Decimal(t['net_pnl_gbp']) for t in closed),Decimal('0'))
    return {'mode':'broker_verified_demo','currency':'GBP','trade_count':len(trades),
            'closed_count':len(closed),'wins':wins,'losses':losses,
            'total_net_pnl_gbp':str(total),'trades':trades,
            'note':'Only confirmed broker fills and verified GBP net P/L. No execution.'}
