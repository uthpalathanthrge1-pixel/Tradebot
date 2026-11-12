"""Demo-only guarded prototype. No live trading endpoint exists."""
import os, sqlite3, threading
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title='UT Bot Capital Demo')

@app.get('/', include_in_schema=False)
def homepage():
    from dashboard import dashboard
    return dashboard()

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

def order_control_state():
    """Operator pause is independent of the immutable broker safety gate."""
    return get_setting('operator_orders_paused', 'true') != 'false'

@app.get('/order-control/{secret}')
def order_control_status(secret: str):
    import secrets as secure
    expected = os.getenv('WEBHOOK_SECRET', '')
    if not expected or not secure.compare_digest(secret, expected):
        raise HTTPException(403, 'Forbidden')
    paused = order_control_state()
    return {'operator_paused': paused, 'operator_mode': 'PAUSED' if paused else 'RESUMED',
            'orders_enabled': False, 'broker_execution_available': False,
            'existing_positions_unchanged': True,
            'queued_signals_replayed': False,
            'note': 'Resume allows future signals only after separate execution safety approval.'}

@app.post('/order-control/{secret}')
async def order_control_update(secret: str, request: Request):
    """Dashboard operator intent only; cannot arm risk engine or place orders."""
    import secrets as secure
    expected = os.getenv('WEBHOOK_SECRET', '')
    if not expected or not secure.compare_digest(secret, expected):
        raise HTTPException(403, 'Forbidden')
    origin = request.headers.get('origin')
    from urllib.parse import urlsplit
    if not origin or urlsplit(origin).netloc != request.headers.get('host') or urlsplit(origin).scheme != request.url.scheme:
        raise HTTPException(403, 'Same-origin request required')
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON required')
    body = await request.json()
    if not isinstance(body, dict) or body.get('action') not in ('pause', 'resume'):
        raise HTTPException(400, 'Expected pause or resume')
    paused = body['action'] == 'pause'
    with db() as conn:
        conn.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                     ('operator_orders_paused', 'true' if paused else 'false'))
    return order_control_status(secret)


@app.get('/broker-dashboard', include_in_schema=False)
def broker_dashboard(request: Request):
    """Password-protected, GET-only demo broker dashboard."""
    import base64, hmac
    from fastapi.responses import HTMLResponse
    from market_validation import MARKETS, inspect_market
    from dashboard import dashboard
    expected = os.getenv('DASHBOARD_PASSWORD', '')
    auth = request.headers.get('authorization', '')
    valid = False
    if expected and auth.startswith('Basic '):
        try:
            raw = base64.b64decode(auth[6:], validate=True).decode('utf-8')
            username, password = raw.split(':', 1)
            valid = hmac.compare_digest(username, 'dashboard') and hmac.compare_digest(password, expected)
        except (ValueError, UnicodeDecodeError):
            pass
    if not valid:
        return HTMLResponse('Dashboard authentication required', status_code=401,
                            headers={'WWW-Authenticate': 'Basic realm="UT Bot Demo Dashboard"',
                                     'Cache-Control': 'no-store'})
    required = ('CAPITAL_API_KEY', 'CAPITAL_IDENTIFIER', 'CAPITAL_API_PASSWORD')
    missing = [k for k in required if not os.getenv(k)]
    state = {'connection': 'Credentials missing' if missing else 'Not verified',
             'markets': {}, 'account': 'Not verified'}
    if not missing:
        from capital import Capital, CapitalCheckError
        try:
            client = Capital()
            account = client.active_account_check()
            state['account'] = 'GBP CFD DEMO verified' if account.get('active_account_verified') else 'Account unverified'
            if not account.get('active_account_verified'):
                state['connection'] = 'Connected; account unverified'
                state['account_reason'] = account.get('reason', 'verification_incomplete')
                if 'gbp_cfd_account_count' in account:
                    state['account_count'] = account['gbp_cfd_account_count']
            else:
                state['connection'] = 'Connected to demo API'
                try:
                    prefs = client.preferences()
                    state['preferences_status'] = 'Available' if isinstance(prefs, dict) else 'Unavailable'
                except (CapitalCheckError, ValueError, KeyError, __import__('requests').exceptions.RequestException):
                    state['preferences_status'] = 'Unavailable'
                try:
                    existing = client.positions()
                    gold_epic = os.getenv('CAPITAL_GOLD_EPIC', '').strip()
                    if not isinstance(existing, list):
                        state['gold_test_preflight'] = 'Blocked — broker positions response invalid'
                    elif not gold_epic:
                        state['gold_test_preflight'] = 'Blocked — Gold EPIC not configured'
                    else:
                        gold_positions = [p for p in existing
                                          if isinstance(p, dict)
                                          and isinstance(p.get('market'), dict)
                                          and p['market'].get('epic') == gold_epic]
                        state['gold_test_preflight'] = (
                            'Blocked — existing Gold position(s): ' + str(len(gold_positions))
                            if gold_positions else 'No Gold positions found — order execution still disabled')
                except (CapitalCheckError, ValueError, KeyError, __import__('requests').exceptions.RequestException):
                    state['gold_test_preflight'] = 'Blocked — unable to verify broker positions'
                for label, definition in MARKETS.items():
                    epic = os.getenv(definition['env'], '').strip()
                    if not epic:
                        state['markets'][label] = {'reason': 'EPIC not configured'}
                        continue
                    try:
                        state['markets'][label] = inspect_market(client, epic)
                    except (CapitalCheckError, ValueError):
                        state['markets'][label] = {'reason': 'Broker market lookup failed'}
        except (CapitalCheckError, ValueError, KeyError, __import__('requests').exceptions.RequestException):
            state['connection'] = 'Broker connection failed'
    response = dashboard(state)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Robots-Tag'] = 'noindex'
    return response

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
        from signal_journal import parse_price
        price = parse_price(alert.get('price'))
        if isinstance(raw_time, int) or (isinstance(raw_time, str) and raw_time.isdigit()):
            bar_time = int(raw_time)
        else:
            bar_time = int(datetime.fromisoformat(str(raw_time).replace('Z', '+00:00')).timestamp() * 1000)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, 'Invalid alert')
    if direction not in ('BUY','SELL') or bar_time <= 0:
        raise HTTPException(400, 'Invalid signal')
    if not symbol or len(symbol)>80:
        raise HTTPException(400, 'Invalid symbol')
    from signal_journal import record
    with lock:
        with db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                conn.execute('INSERT INTO alerts VALUES (?,?,?)',(symbol,bar_time,direction))
            except sqlite3.IntegrityError:
                return {'status':'duplicate','orders_submitted':False}
            disposition=record(conn,symbol,bar_time,direction,price)
    # Connect the existing TradingView signal path to the DEMO bridge.
    # Broker mutations remain blocked until GBP stop sizing, durable
    # idempotency, close reconciliation and risk arming are verified.
    if symbol in ('GOLD', 'XAUUSD'):
        from demo_order_bridge import validate_signal, DemoOrderBridge
        from risk_engine import RiskLedger, orders_permitted
        signal = validate_signal({'epic':'GOLD','direction':direction,'size':'0.01'})
        state = RiskLedger(DB).state()
        if order_control_state():
            return {'status':'journaled','disposition':disposition,
                    'execution':'operator_paused','orders_submitted':False}
        if state['halted'] or not orders_permitted():
            return {'status':'journaled','disposition':disposition,
                    'execution':'connected_but_halted',
                    'halt_reason':state['reason'],
                    'orders_submitted':False}
        # An independent broker execution review must change the gate;
        # receiving an alert never constitutes permission to place orders.
        outcome = DemoOrderBridge().submit(signal, gate_approved=False)
        return {'status':'journaled','disposition':disposition,
                'execution':outcome,'orders_submitted':False}
    return {'status':'journaled','disposition':disposition,'orders_submitted':False}

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

@app.get('/discover-markets/{secret}')
def discover_markets(secret: str):
    """Read-only candidate search; requires manual confirmation of exact EPICs."""
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    from capital import Capital, CapitalCheckError
    try:
        client = Capital()
        account = client.account_check()
        if not account.get('configured_account_found') or account.get('account_type') != 'CFD':
            return {'ready': False, 'reason': 'unique_gbp_cfd_demo_not_verified', 'orders_enabled': False}
        found = {}
        for label, term in [('GOLD', 'Gold'), ('OIL', 'Crude Oil')]:
            response = client.market_search(term)
            candidates = response.get('markets', [])
            found[label] = [
                {'epic': m.get('epic'), 'instrument_name': m.get('instrumentName'),
                 'instrument_type': m.get('instrumentType'), 'market_status': m.get('marketStatus')}
                for m in candidates[:20]
            ]
        return {'ready': True, 'candidates': found, 'selection_required': True,
                'orders_enabled': False}
    except CapitalCheckError as exc:
        return {'ready': False, 'stage': exc.stage, 'http_status': exc.status, 'orders_enabled': False}
    except Exception:
        return {'ready': False, 'stage': 'market_discovery_failed', 'orders_enabled': False}

@app.get('/contract-specs/{secret}')
def contract_specs(secret: str):
    """Read-only instrument specification inspection; does not size or submit orders."""
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    from capital import Capital, CapitalCheckError
    try:
        client = Capital()
        account = client.account_check()
        if not account.get('configured_account_found') or account.get('account_type') != 'CFD':
            return {'ready': False, 'reason': 'gbp_cfd_demo_not_verified', 'orders_enabled': False}
        specs = {}
        for label, expected in [('GOLD', 'GOLD'), ('OIL', 'OIL_CRUDE')]:
            epic = os.getenv('CAPITAL_' + label + '_EPIC', '')
            if epic != expected:
                specs[label] = {'configured': False, 'expected_epic': expected}
                continue
            detail = client.market_details(epic)
            instrument = detail.get('instrument', {})
            dealing = detail.get('dealingRules', {})
            snapshot = detail.get('snapshot', {})
            specs[label] = {
                'configured': True,
                'epic': instrument.get('epic'),
                'name': instrument.get('name'),
                'type': instrument.get('type'),
                'market_status': snapshot.get('marketStatus'),
                'bid': snapshot.get('bid'),
                'offer': snapshot.get('offer'),
                'lot_size': instrument.get('lotSize'),
                'contract_size': instrument.get('contractSize'),
                'margin_factor': instrument.get('marginFactor'),
                'margin_factor_unit': instrument.get('marginFactorUnit'),
                'min_deal_size': dealing.get('minDealSize'),
                'max_deal_size': dealing.get('maxDealSize'),
                'min_step_distance': dealing.get('minStepDistance'),
                'currencies': instrument.get('currencies'),
            }
        return {'ready': True, 'specifications': specs,
                'margin_target_gbp_each': 1000, 'orders_enabled': False,
                'note': 'Read-only broker values. No order size has been calculated or approved.'}
    except CapitalCheckError as exc:
        return {'ready': False, 'stage': exc.stage, 'http_status': exc.status, 'orders_enabled': False}
    except Exception:
        return {'ready': False, 'stage': 'contract_spec_lookup_failed', 'orders_enabled': False}

@app.get('/risk-readiness/{secret}')
def risk_readiness(secret: str):
    """Safe inspection only; no order placement or arming."""
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    from risk_engine import RiskLedger, orders_permitted
    ledger = RiskLedger(DB)
    state = ledger.state()
    return {
        'demo_only': True,
        'orders_enabled': orders_permitted(),
        'halted': state['halted'],
        'halt_reason': state['reason'],
        'realised_gbp': str(state['realised_gbp']),
        'margin_target_gbp_each': 1000,
        'combined_loss_trigger_gbp': -100,
        'sizing_verified': False,
        'broker_pnl_currency_verified': False,
        'broker_order_confirmations_tested': False,
        'continuous_risk_monitor_running': False,
        'note': 'Fail-closed risk module installed but not connected to order execution.'
    }

@app.get('/gold-test-preview/{secret}')
def gold_test_preview(secret: str):
    """Read-only preflight for a controlled minimum-size Gold demo test.
    Does NOT send orders; a separate explicit confirmation is required.
    """
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    from capital import Capital, CapitalCheckError
    from decimal import Decimal
    try:
        client = Capital()
        account = client.account_check()
        if not account.get('configured_account_found') or account.get('account_type') != 'CFD':
            return {'ready': False, 'reason': 'GBP_CFD_DEMO_ACCOUNT_NOT_VERIFIED',
                    'orders_enabled': False}
        positions = client.positions()
        if positions:
            return {'ready': False, 'reason': 'EXISTING_POSITIONS_PRESENT',
                    'open_position_count': len(positions), 'orders_enabled': False}
        detail = client.market_details('GOLD')
        instrument = detail.get('instrument', {})
        dealing = detail.get('dealingRules', {})
        snapshot = detail.get('snapshot', {})
        minimum = dealing.get('minDealSize', {}).get('value')
        factor = instrument.get('marginFactor')
        offer = snapshot.get('offer')
        if (instrument.get('epic') != 'GOLD' or
                instrument.get('type') != 'COMMODITIES' or
                snapshot.get('marketStatus') != 'TRADEABLE' or
                minimum is None or factor is None or offer is None):
            return {'ready': False, 'reason': 'GOLD_MARKET_DETAILS_INCOMPLETE',
                    'orders_enabled': False}
        return {
            'ready': True, 'test_mode': 'PREVIEW_ONLY',
            'instrument': 'GOLD', 'direction': 'BUY',
            'minimum_deal_size': minimum,
            'offer': offer, 'margin_factor_percent': factor,
            'contract_size_verified': False,
            'pnl_currency_verified': False,
            'margin_estimate_verified': False,
            'existing_positions': 0,
            'main_bot_halted': True,
            'orders_enabled': False,
            'next_step': 'Review preview and explicitly approve a one-off demo test.'
        }
    except CapitalCheckError as exc:
        return {'ready': False, 'stage': exc.stage,
                'http_status': exc.status, 'orders_enabled': False}
    except Exception:
        return {'ready': False, 'stage': 'gold_test_preflight_failed',
                'orders_enabled': False}

@app.post('/one-off-gold-test')
def one_off_gold_test(request: Request):
    """Single-use controlled DEMO test. No TradingView signal can call this."""
    import secrets, time
    from capital import Capital, CapitalCheckError
    from risk_engine import RiskLedger
    from fastapi import Header
    # Separate test authorisation header, not the webhook URL secret.
    key = request.headers.get('X-DEMO-TEST-KEY', '')
    expected = os.environ.get('DEMO_TEST_KEY', '')
    if not expected or len(expected) < 24 or not secrets.compare_digest(key, expected):
        raise HTTPException(403, 'Test authorisation required')
    if os.environ.get('ALLOW_ONE_OFF_GOLD_TEST') != 'true':
        raise HTTPException(409, 'One-off test disabled')
    with lock:
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS one_off_tests (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL, deal_ref TEXT, deal_id TEXT)')
            old = conn.execute('SELECT state FROM one_off_tests WHERE id=1').fetchone()
            if old:
                raise HTTPException(409, 'One-off test already attempted; manual review required')
            # Mark as used BEFORE any broker mutation; never retry automatically.
            conn.execute("INSERT INTO one_off_tests(id,state) VALUES(1,'started')")
        client = Capital()
        def record(state, ref=None, deal=None):
            with db() as conn:
                conn.execute('UPDATE one_off_tests SET state=?,deal_ref=COALESCE(?,deal_ref),deal_id=COALESCE(?,deal_id) WHERE id=1',
                             (state,ref,deal))
        try:
            account = client.account_check()
            if not account.get('configured_account_found') or account.get('account_type') != 'CFD':
                record('account_verification_failed')
                return {'state':'account_verification_failed','orders_enabled':False}
            if client.positions():
                record('existing_positions')
                return {'state':'existing_positions','orders_enabled':False}
            detail = client.market_details('GOLD')
            instrument, snapshot, rules = detail.get('instrument',{}), detail.get('snapshot',{}), detail.get('dealingRules',{})
            if (instrument.get('epic') != 'GOLD' or instrument.get('type') != 'COMMODITIES'
                    or snapshot.get('marketStatus') != 'TRADEABLE'
                    or float(rules.get('minDealSize',{}).get('value',-1)) != 0.01):
                record('market_preflight_failed')
                return {'state':'market_preflight_failed','orders_enabled':False}
            if not RiskLedger(DB).state()['halted']:
                record('main_bot_not_halted')
                return {'state':'main_bot_not_halted','orders_enabled':False}
            record('submitting_buy')
            opened = client.open_position('GOLD','BUY',0.01)
            reference = opened.get('dealReference')
            record('buy_submitted', reference)
            if not reference:
                record('buy_uncertain')
                return {'state':'buy_uncertain','manual_check_required':True}
            confirmation = None
            for _ in range(5):
                try:
                    confirmation = client.confirm(reference)
                    break
                except CapitalCheckError as exc:
                    if exc.status != 404:
                        raise
                    time.sleep(1)
            if not confirmation or confirmation.get('dealStatus') != 'ACCEPTED':
                record('buy_unconfirmed')
                return {'state':'buy_unconfirmed','manual_check_required':True}
            from reconciliation import opened_deal_ids
            opened_ids = opened_deal_ids(confirmation)
            # Never guess which position to close if a single test order
            # opened multiple positions.
            if len(opened_ids) != 1:
                record('ambiguous_opened_deals')
                return {'state':'ambiguous_opened_deals',
                        'opened_deal_count':len(opened_ids),
                        'manual_check_required':True}
            deal_id = opened_ids[0]
            record('buy_confirmed',reference,deal_id)
            if not deal_id:
                return {'state':'buy_confirmed_missing_deal_id','manual_check_required':True}
            # Capital.com may report an accepted deal before GET /positions
            # reflects it. Poll, match by deal ID and verify the instrument,
            # direction and size. Never guess or close an unrelated position.
            from reconciliation import wait_for_position
            matched, diagnostic = wait_for_position(
                client.positions, deal_id, epic='GOLD', direction='BUY',
                size='0.01', attempts=12, delay_seconds=2)
            if matched is None:
                record('position_reconciliation_failed')
                return {'state':'position_reconciliation_failed',
                        'diagnostic':diagnostic,
                        'manual_check_required':True}
            record('submitting_close')
            closed = client.close_position(deal_id)
            close_ref = closed.get('dealReference')
            record('close_submitted')
            if not close_ref:
                return {'state':'close_uncertain','manual_check_required':True}
            close_confirmation = None
            for _ in range(5):
                try:
                    close_confirmation = client.confirm(close_ref)
                    break
                except CapitalCheckError as exc:
                    if exc.status != 404:
                        raise
                    time.sleep(1)
            from reconciliation import wait_for_absence
            if not close_confirmation or close_confirmation.get('dealStatus') != 'ACCEPTED':
                record('close_unconfirmed')
                return {'state':'close_unconfirmed','manual_check_required':True}
            if not wait_for_absence(client.positions, deal_id,
                                    attempts=12, delay_seconds=2):
                record('close_still_visible')
                return {'state':'close_still_visible','manual_check_required':True}
            record('closed_confirmed')
            return {'state':'closed_confirmed','gold_size':0.01,'main_bot_orders_enabled':False}
        except Exception:
            record('error_manual_reconciliation_required')
            return {'state':'error_manual_reconciliation_required',
                    'manual_check_required':True,'main_bot_orders_enabled':False}

@app.get('/one-off-gold-test-status/{secret}')
def one_off_gold_test_status(secret: str):
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    with db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS one_off_tests (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL, deal_ref TEXT, deal_id TEXT)')
        row=conn.execute('SELECT state FROM one_off_tests WHERE id=1').fetchone()
    return {'test_state': row[0] if row else 'not_started',
            'main_bot_orders_enabled':False}

@app.get('/gold-test-reconcile/{secret}')
def gold_test_reconcile(secret: str):
    """Read-only, sanitized broker position reconciliation; never closes orders."""
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    from capital import Capital, CapitalCheckError
    try:
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS one_off_tests (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL, deal_ref TEXT, deal_id TEXT)')
            row=conn.execute('SELECT state,deal_id FROM one_off_tests WHERE id=1').fetchone()
        if not row:
            return {'test_state':'not_started','orders_enabled':False}
        state, stored_id=row
        positions=Capital().positions()
        matches=[p for p in positions if p.get('position',{}).get('dealId') == stored_id]
        gold=[p for p in positions if p.get('market',{}).get('epic') == 'GOLD']
        return {
            'test_state':state,
            'broker_position_count':len(positions),
            'gold_position_count':len(gold),
            'stored_deal_id_present':bool(stored_id),
            'stored_deal_id_matches_open_position':len(matches)==1,
            'gold_positions':[{
                'direction':p.get('position',{}).get('direction'),
                'size':p.get('position',{}).get('size'),
                'deal_id_matches_test':p.get('position',{}).get('dealId')==stored_id,
                'position_keys':sorted(p.get('position',{}).keys()),
                'market_keys':sorted(p.get('market',{}).keys())
            } for p in gold[:5]],
            'orders_enabled':False,
            'action':'Check and close any test Gold position manually in Capital.com; do not rerun test.'
        }
    except CapitalCheckError as exc:
        return {'ready':False,'stage':exc.stage,'http_status':exc.status,'orders_enabled':False}
    except Exception:
        return {'ready':False,'stage':'reconciliation_read_failed','orders_enabled':False}

@app.get('/gold-test-followup/{secret}')
def gold_test_followup(secret: str):
    """Read-only gate for a subsequent test; never resets a consumed test lock."""
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    from capital import Capital, CapitalCheckError
    try:
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS one_off_tests (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL, deal_ref TEXT, deal_id TEXT)')
            row = conn.execute('SELECT state FROM one_off_tests WHERE id=1').fetchone()
        client = Capital()
        account = client.account_check()
        positions = client.positions()
        return {'ready_for_new_order':False,
                'account_verified': bool(account.get('configured_account_found') and account.get('account_type') == 'CFD'),
                'open_position_count':len(positions),
                'previous_test_state':row[0] if row else 'not_started',
                'previous_test_lock_preserved':bool(row),
                'close_api_verified':False,
                'main_bot_orders_enabled':False,
                'next_step':'Review broker close request semantics and separately authorise a fresh isolated test.'}
    except CapitalCheckError as exc:
        return {'ready_for_new_order':False,'stage':exc.stage,'http_status':exc.status}
    except Exception:
        return {'ready_for_new_order':False,'stage':'followup_read_failed'}

@app.get('/gold-test-v2-preview/{secret}')
def gold_test_v2_preview(secret: str):
    """Read-only preflight for a separately authorised second Gold demo test.

    Does not unlock, arm, submit or close any order.
    """
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    from capital import Capital, CapitalCheckError
    from risk_engine import RiskLedger
    try:
        client = Capital()
        account = client.account_check()
        positions = client.positions()
        detail = client.market_details('GOLD')
        instrument = detail.get('instrument') or {}
        snapshot = detail.get('snapshot') or {}
        rules = detail.get('dealingRules') or {}
        min_size = (rules.get('minDealSize') or {}).get('value')
        try:
            from decimal import Decimal
            size_allowed = min_size is not None and Decimal(str(min_size)) <= Decimal('0.01')
        except Exception:
            size_allowed = False
        account_ok = bool(account.get('configured_account_found') and account.get('account_type') == 'CFD')
        market_ok = (instrument.get('epic') == 'GOLD' and
                     instrument.get('type') == 'COMMODITIES' and
                     snapshot.get('marketStatus') == 'TRADEABLE')
        no_positions = len(positions) == 0
        halted = bool(RiskLedger(DB).state()['halted'])
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS one_off_tests (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL, deal_ref TEXT, deal_id TEXT)')
            old = conn.execute('SELECT state FROM one_off_tests WHERE id=1').fetchone()
        return {
            'preflight_passed': account_ok and market_ok and size_allowed and no_positions and halted,
            'account_verified': account_ok,
            'gold_market_tradeable': market_ok,
            'gold_min_size': min_size,
            'test_size': '0.01',
            'test_size_allowed': size_allowed,
            'open_position_count': len(positions),
            'main_bot_halted': halted,
            'previous_test_state': old[0] if old else 'not_started',
            'previous_test_lock_preserved': bool(old),
            'v2_order_execution_available': False,
            'close_api_live_verified': False,
            'new_order_submitted': False,
            'next_step': 'Review preflight and separately authorise creation of a one-use execution endpoint.'
        }
    except CapitalCheckError as exc:
        return {'preflight_passed': False, 'stage': exc.stage,
                'http_status': exc.status, 'new_order_submitted': False}
    except Exception:
        return {'preflight_passed': False, 'stage': 'preview_failed',
                'new_order_submitted': False}

@app.get('/gold-test-v2-simulation/{secret}')
def gold_test_v2_simulation(secret: str):
    """Offline broker-response simulation. No broker mutation or new order."""
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403, 'Forbidden')
    from reconciliation import opened_deal_ids, wait_for_position, wait_for_absence
    confirmation = {
        'dealStatus':'ACCEPTED',
        'dealId':'order-reference',
        'affectedDeals':[{'dealId':'simulated-position','status':'OPENED'}]
    }
    ids = opened_deal_ids(confirmation)
    opening_polls = [[],[],[{
        'position':{'dealId':'simulated-position','direction':'BUY','size':0.01},
        'market':{'epic':'GOLD'}}]]
    def fetch_open():
        return opening_polls.pop(0) if opening_polls else []
    matched, diagnostic = wait_for_position(
        fetch_open, ids[0] if len(ids)==1 else None, 'GOLD','BUY','0.01',
        attempts=3,delay_seconds=0,sleep=lambda _:None)
    closing_polls = [[{'position':{'dealId':'simulated-position'}}],[]]
    def fetch_close():
        return closing_polls.pop(0) if closing_polls else []
    closed = bool(matched) and wait_for_absence(
        fetch_close,ids[0],attempts=2,delay_seconds=0,sleep=lambda _:None)
    return {'simulation_passed':bool(closed),
            'correct_position_id_selected':ids==['simulated-position'],
            'opening_poll':diagnostic.get('poll'),
            'closure_verified_in_simulation':bool(closed),
            'broker_close_api_live_verified':False,
            'new_order_submitted':False,
            'main_bot_orders_enabled':False}

@app.post('/gold-test-v2-execute')
def gold_test_v2_execute(request: Request):
    """Fail-closed V2 entry point. No order capability is installed."""
    import secrets
    from gold_test_v2 import execution_gate
    supplied = request.headers.get('X-DEMO-TEST-KEY','')
    expected = os.environ.get('DEMO_TEST_KEY','')
    authenticated = bool(expected and len(expected)>=24 and
                         secrets.compare_digest(supplied,expected))
    gate = execution_gate(DB,authenticated=authenticated)
    if not authenticated:
        raise HTTPException(403,'Test authorisation required')
    return {'execution_permitted':gate.allowed,
            'reason':gate.reason,
            'new_order_submitted':False,
            'main_bot_orders_enabled':False}

@app.get('/journal/{secret}')
def journal(secret: str):
    """Authenticated paper journal of real TradingView alerts; no broker fills."""
    if not os.environ.get('WEBHOOK_SECRET') or secret != os.environ['WEBHOOK_SECRET']:
        raise HTTPException(403,'Forbidden')
    from signal_journal import report
    with db() as conn:
        return report(conn)

@app.get('/dashboard/{secret}')
def dashboard(secret: str):
    """Private, responsive signal journal UI; no trading actions."""
    import secrets as secure
    from pathlib import Path
    from fastapi.responses import HTMLResponse
    expected=os.environ.get('WEBHOOK_SECRET','')
    if not expected or not secure.compare_digest(secret,expected):
        raise HTTPException(403,'Forbidden')
    page=Path(__file__).with_name('dashboard.html').read_text(encoding='utf-8')
    return HTMLResponse(page,headers={'Cache-Control':'no-store',
                                     'Referrer-Policy':'no-referrer',
                                     'X-Content-Type-Options':'nosniff',
                                     'Content-Security-Policy':"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'"})


@app.get('/demo-execution-preflight/{secret}')
def demo_execution_preflight(secret: str):
    """Read-only gate: validate broker state and persistent risk lock. No orders."""
    import secrets as secure
    from decimal import Decimal
    expected=os.environ.get('WEBHOOK_SECRET','')
    if not expected or not secure.compare_digest(secret,expected):
        raise HTTPException(403,'Forbidden')
    from capital import Capital, CapitalCheckError
    from risk_engine import RiskLedger
    risk=RiskLedger(DB).state()
    checks={'risk_halted':risk['halted'],
            'risk_reason':risk['reason'],
            'main_orders_disabled':os.getenv('ENABLE_DEMO_ORDERS','false').lower()=='false',
            'sizing_verified':False,
            'automatic_close_verified':False,
            'broker_gbp_pnl_verified':False,
            'continuous_risk_monitor_running':False}
    try:
        client=Capital()
        account=client.account_check()
        checks['unique_gbp_cfd_demo']=bool(account.get('configured_account_found') and
             account.get('account_currency')=='GBP' and account.get('account_type')=='CFD')
        positions=client.positions()
        checks['zero_open_positions']=len(positions)==0
        checks['open_position_count']=len(positions)
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS one_off_tests (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL, deal_ref TEXT, deal_id TEXT)')
            previous=conn.execute('SELECT state FROM one_off_tests WHERE id=1').fetchone()
        checks['previous_test_state']=previous[0] if previous else 'not_started'
        checks['previous_test_lock_preserved']=bool(previous)
    except CapitalCheckError as exc:
        return {'ready_to_enable':False,'checks':checks,'error_stage':exc.stage,
                'http_status':exc.status,'orders_submitted':False}
    except Exception:
        return {'ready_to_enable':False,'checks':checks,'error_stage':'preflight_failed',
                'orders_submitted':False}
    return {'ready_to_enable':False,'checks':checks,'orders_submitted':False,
            'next_step':'Validate broker close semantics, contract sizing and net GBP P/L in isolated approved demo tests before enabling execution.'}


@app.get('/broker-diagnostics/{secret}')
def broker_diagnostics(secret: str):
    """Read-only broker inspection, redacted; never places or closes orders."""
    import secrets as secure
    expected=os.environ.get('WEBHOOK_SECRET','')
    if not expected or not secure.compare_digest(secret,expected):
        raise HTTPException(403,'Forbidden')
    from capital import Capital, CapitalCheckError
    from broker_diagnostics import describe_positions
    try:
        client=Capital()
        account=client.account_check()
        positions=client.positions()
        return {'demo_account_verified':bool(
                    account.get('configured_account_found') and
                    account.get('account_currency')=='GBP' and
                    account.get('account_type')=='CFD'),
                'open_position_count':len(positions),
                'position_shapes':describe_positions(positions),
                'orders_submitted':False,
                'note':'No historical closed position payloads are available from this endpoint.'}
    except CapitalCheckError as exc:
        return {'ready':False,'stage':exc.stage,'http_status':exc.status,
                'orders_submitted':False}
    except Exception:
        return {'ready':False,'stage':'broker_diagnostics_failed','orders_submitted':False}


@app.get('/broker-journal/{secret}')
def broker_journal_view(secret: str):
    """Verified broker journal only. Does not contain TradingView paper fills."""
    import secrets as secure
    expected=os.environ.get('WEBHOOK_SECRET','')
    if not expected or not secure.compare_digest(secret,expected):
        raise HTTPException(403,'Forbidden')
    from broker_journal import report
    with db() as conn:
        result=report(conn)
    # Avoid exposing full deal identifiers in browser responses.
    for trade in result['trades']:
        trade['deal_id']='redacted'
    return result

@app.get('/demo-risk-monitor/{secret}')
def demo_risk_monitor_view(secret: str):
    """Read-only diagnostic, intentionally fail closed. No orders or closes."""
    import secrets as secure
    expected=os.environ.get('WEBHOOK_SECRET','')
    if not expected or not secure.compare_digest(secret,expected):
        raise HTTPException(403,'Forbidden')
    from capital import Capital, CapitalCheckError
    from demo_risk_monitor import inspect
    from risk_engine import RiskLedger
    state=RiskLedger(DB).state()
    try:
        positions=Capital().positions()
        result=inspect(positions,realised_gbp=state['realised_gbp'])
        result['persistent_halt']=state['halted']
        result['halt_reason']=state['reason']
        return result
    except CapitalCheckError as exc:
        return {'ready_to_trade':False,'must_halt':True,
                'reason':'broker_read_failed','stage':exc.stage,
                'http_status':exc.status,'orders_submitted':False}
    except Exception:
        return {'ready_to_trade':False,'must_halt':True,
                'reason':'risk_inspection_failed','orders_submitted':False}


@app.get('/broker-history-probe/{secret}')
def broker_history_probe_view(secret: str):
    """Authenticated, read-only schema probe. No raw transactions exposed."""
    import secrets as secure
    expected=os.environ.get('WEBHOOK_SECRET','')
    if not expected or not secure.compare_digest(secret,expected):
        raise HTTPException(403,'Forbidden')
    from capital import Capital, CapitalCheckError
    from broker_history_probe import probe_history
    try:
        return probe_history(Capital(),lookback_days=1)
    except CapitalCheckError as exc:
        return {'ready':False,'stage':exc.stage,'http_status':exc.status,
                'broker_error_code':exc.error_code,
                'orders_submitted':False,'journal_updated':False}
    except Exception as exc:
        # Report only the exception class; exception text may contain credentials,
        # request URLs, or broker transaction identifiers.
        import requests
        if isinstance(exc, requests.exceptions.Timeout):
            category='broker_timeout'
        elif isinstance(exc, requests.exceptions.ConnectionError):
            category='broker_connection_error'
        elif isinstance(exc, (ImportError, ModuleNotFoundError)):
            category='module_import_error'
        elif isinstance(exc, (TypeError, ValueError, KeyError, AttributeError)):
            category='response_parsing_error'
        else:
            category='unexpected_probe_error'
        return {'ready':False,'stage':'broker_history_probe_failed',
                'error_category':category,'error_type':type(exc).__name__,
                'orders_submitted':False,'journal_updated':False}


@app.post('/gold-v2-prepare')
async def gold_v2_prepare(request: Request):
    """One-time proposal reservation only. Never sends broker orders."""
    import secrets as secure
    from gold_v2_preparation import prepare_once, status
    expected=os.environ.get('DEMO_TEST_KEY','')
    supplied=request.headers.get('X-DEMO-TEST-KEY','')
    if not expected or len(expected)<24 or not secure.compare_digest(expected,supplied):
        raise HTTPException(403,'Test authorisation required')
    body=await request.json()
    if not isinstance(body,dict) or body.get('approval')!='PREPARE_ONLY_NO_ORDERS':
        raise HTTPException(400,'Explicit preparation-only approval required')
    proposal_id=body.get('proposal_id')
    if not isinstance(proposal_id,str):
        raise HTTPException(400,'Invalid proposal ID')
    result=prepare_once(DB,authenticated=True,proposal_id=proposal_id,
                        explicit_preparation_approval=True)
    return {'preparation_accepted':result.reason=='prepared_no_execution_adapter',
            'execution_permitted':False,'reason':result.reason,
            **status(DB)}

@app.get('/gold-v2-preparation-status/{secret}')
def gold_v2_preparation_status(secret: str):
    """Read-only inspection of isolated preparation record."""
    import secrets as secure
    expected=os.environ.get('WEBHOOK_SECRET','')
    if not expected or not secure.compare_digest(expected,secret):
        raise HTTPException(403,'Forbidden')
    from gold_v2_preparation import status
    return status(DB)
