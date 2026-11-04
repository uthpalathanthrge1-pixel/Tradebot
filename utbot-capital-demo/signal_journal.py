"""Signal-only UT Bot journal. No broker order submission."""
import sqlite3
from decimal import Decimal, InvalidOperation

def init(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS paper_trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,
      direction TEXT NOT NULL, entry_time INTEGER NOT NULL,
      entry_price TEXT, exit_time INTEGER, exit_price TEXT,
      points TEXT, outcome TEXT NOT NULL DEFAULT 'OPEN',
      entry_source TEXT NOT NULL DEFAULT 'tradingview_close',
      exit_source TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS journal_events (
      symbol TEXT NOT NULL, bar_time INTEGER NOT NULL,
      direction TEXT NOT NULL, price TEXT,
      disposition TEXT NOT NULL,
      PRIMARY KEY(symbol,bar_time, direction))""")

def parse_price(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number<=0:
            raise ValueError('Invalid price')
        return str(number)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Invalid price')

def record(conn, symbol, bar_time, direction, price):
    """Process one confirmed signal atomically; return event disposition."""
    init(conn)
    if conn.execute('SELECT 1 FROM journal_events WHERE symbol=? AND bar_time=? AND direction=?',
                    (symbol,bar_time,direction)).fetchone():
        return 'duplicate'
    latest=conn.execute('SELECT MAX(bar_time) FROM journal_events WHERE symbol=?',(symbol,)).fetchone()[0]
    if latest is not None and bar_time<=latest:
        disposition='out_of_order_ignored'
    else:
        current=conn.execute("""SELECT id,direction,entry_price FROM paper_trades
                                 WHERE symbol=? AND outcome='OPEN' ORDER BY id DESC LIMIT 1""",(symbol,)).fetchone()
        if current and current[1]==direction:
            disposition='same_direction_ignored'
        else:
            if current:
                points=None
                outcome='UNPRICED'
                if current[2] is not None and price is not None:
                    diff=Decimal(price)-Decimal(current[2])
                    if current[1]=='SELL': diff=-diff
                    points=str(diff)
                    outcome='WIN' if diff>0 else 'LOSS' if diff<0 else 'BREAKEVEN'
                conn.execute("""UPDATE paper_trades SET exit_time=?,exit_price=?,points=?,
                                 outcome=?,exit_source=? WHERE id=?""",
                             (bar_time,price,points,outcome,
                              'tradingview_close' if price is not None else None,current[0]))
            conn.execute("""INSERT INTO paper_trades
                (symbol,direction,entry_time,entry_price,entry_source)
                VALUES (?,?,?,?,?)""",(symbol,direction,bar_time,price,
                  'tradingview_close' if price is not None else 'unavailable'))
            disposition='reversed' if current else 'opened'
    conn.execute("""INSERT INTO journal_events
      (symbol,bar_time,direction,price,disposition) VALUES (?,?,?,?,?)""",
      (symbol,bar_time,direction,price,disposition))
    return disposition

def report(conn, limit=100):
    init(conn)
    rows=conn.execute("""SELECT id,symbol,direction,entry_time,entry_price,
      exit_time,exit_price,points,outcome FROM paper_trades
      ORDER BY id DESC LIMIT ?""",(limit,)).fetchall()
    columns=('id','symbol','direction','entry_time','entry_price',
             'exit_time','exit_price','points','outcome')
    trades=[dict(zip(columns,r)) for r in rows]
    summary={}
    for symbol,total,wins,losses,flat,unpriced in conn.execute("""
       SELECT symbol,COUNT(*),
       SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END),
       SUM(CASE WHEN outcome='LOSS' THEN 1 ELSE 0 END),
       SUM(CASE WHEN outcome='BREAKEVEN' THEN 1 ELSE 0 END),
       SUM(CASE WHEN outcome='UNPRICED' THEN 1 ELSE 0 END)
       FROM paper_trades WHERE outcome!='OPEN' GROUP BY symbol"""):
        summary[symbol]={'closed':total,'wins':wins,'losses':losses,
                         'breakeven':flat,'unpriced':unpriced,
                         'win_rate_percent':round(100*wins/(wins+losses+flat),2)
                         if wins+losses+flat else None}
    return {'mode':'signal_only_paper_journal','price_basis':'TradingView bar close (not executable bid/ask)',
            'pnl_unit':'instrument price points per 1 unit, not GBP',
            'broker_orders_submitted':False,'summary':summary,'trades':trades}
