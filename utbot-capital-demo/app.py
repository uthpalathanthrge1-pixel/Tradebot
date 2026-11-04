"""Demo-only guarded prototype. No live trading endpoint exists."""
import os, sqlite3, threading
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title='UT Bot Capital Demo')
lock = threading.RLock()
DB = os.getenv('DB_PATH', '/data/utbot.sqlite3')
os.makedirs(os.path.dirname(DB) or '.', exist_ok=True)

def db():
    conn = sqlite3.connect(DB)
    conn.execute('CREATE TABLE IF NOT EXISTS alerts (symbol TEXT, bar_time INTEGER, direction TEXT, PRIMARY KEY(symbol,bar_time,direction))')
    conn.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    return conn

def get_setting(key, default):
    with db() as conn:
        r = conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return r[0] if r else default

@app.get('/health')
def health():
    return {'status':'running', 'demo_only':True, 'orders_enabled':False, 'halted':True}

@app.post('/webhook/{secret}')
async def webhook(secret: str, request: Request):
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    try:
        alert = await request.json()
        symbol = str(alert['symbol']).upper()
        direction = str(alert['direction']).upper()
        raw_time = alert['bar_time']
        if isinstance(raw_time, int) or (isinstance(raw_time, str) and raw_time.isdigit()):
            bar_time = int(raw_time)
        else:
            bar_time = int(datetime.fromisoformat(str(raw_time).replace('Z', '+00:00')).timestamp() * 1000)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, 'Invalid alert')
    if direction not in ('BUY','SELL') or bar_time <= 0:
        raise HTTPException(400, 'Invalid signal')
    with lock:
        with db() as conn:
            try:
                conn.execute('INSERT INTO alerts VALUES (?,?,?)',(symbol,bar_time,direction))
            except sqlite3.IntegrityError:
                return {'status':'duplicate'}
    return {'status':'logged_only', 'reason':'broker execution disabled pending account and risk verification'}

@app.get('/status/{secret}')
def status(secret: str):
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    with db() as conn:
        alerts = conn.execute('SELECT symbol,bar_time,direction FROM alerts ORDER BY bar_time DESC LIMIT 20').fetchall()
    return {'halted':True, 'signals':[{'symbol':a,'bar_time':b,'direction':c} for a,b,c in alerts], 'note':'signal-only validation; no orders submitted'}

@app.get('/capital-check/{secret}')
def capital_check(secret: str):
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    required = ('CAPITAL_API_KEY', 'CAPITAL_IDENTIFIER', 'CAPITAL_API_PASSWORD')
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        return {'ready': False, 'missing_variables': missing, 'orders_enabled': False}
    from capital import Capital, CapitalCheckError
    import requests
    try:
        info = Capital().account_check()
        return {'ready': True, 'account': info, 'orders_enabled': False}
    except CapitalCheckError as exc:
        return {'ready': False, 'stage': exc.stage, 'http_status': exc.status, 'orders_enabled': False}
    except requests.exceptions.Timeout:
        return {'ready': False, 'stage': 'network_timeout', 'orders_enabled': False}
    except requests.exceptions.RequestException:
        return {'ready': False, 'stage': 'network_request_failed', 'orders_enabled': False}
    except Exception:
        return {'ready': False, 'stage': 'unexpected_error', 'orders_enabled': False}

@app.get('/trade-readiness/{secret}')
def trade_readiness(secret: str):
    """Read-only broker discovery. Never enables or submits orders."""
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    from capital import Capital, CapitalCheckError
    client = Capital()
    try:
        account = client.account_check()
        if not account.get('configured_account_found') or account.get('account_type') != 'CFD':
            return {'ready': False, 'reason': 'unique_gbp_cfd_demo_not_verified',
                    'orders_enabled': False}
        preferences = client.preferences()
        existing = client.positions()
        results = {}
        for market in ('GOLD', 'OIL'):
            epic = os.getenv('CAPITAL_' + market + '_EPIC', '').strip()
            if not epic:
                results[market] = {'epic_configured': False, 'market_verified': False}
                continue
            detail = client.market_details(epic)
            instrument = detail.get('instrument', {})
            dealing = detail.get('dealingRules', {})
            results[market] = {
                'epic_configured': True,
                'market_verified': instrument.get('epic') == epic,
                'instrument_name': instrument.get('name'),
                'instrument_type': instrument.get('type'),
                'market_status': detail.get('snapshot', {}).get('marketStatus'),
                'min_deal_size': dealing.get('minDealSize'),
                'min_step_distance': dealing.get('minStepDistance'),
                'margin_factor': instrument.get('marginFactor'),
                'margin_factor_unit': instrument.get('marginFactorUnit'),
                'lot_size': instrument.get('lotSize'),
                'currency': instrument.get('currencies'),
            }
        return {
            'ready': False,
            'reason': 'order_size_and_risk_engine_not_yet_validated',
            'demo_account_verified': True,
            'hedging_mode': preferences.get('hedgingMode'),
            'leverage_preferences': preferences.get('leverages'),
            'open_position_count': len(existing),
            'markets': results,
            'margin_target_gbp_each': 1000,
            'combined_loss_trigger_gbp': -100,
            'orders_enabled': False,
        }
    except CapitalCheckError as exc:
        return {'ready': False, 'stage': exc.stage, 'http_status': exc.status, 'orders_enabled': False}
    except Exception:
        return {'ready': False, 'stage': 'readiness_check_failed', 'orders_enabled': False}
