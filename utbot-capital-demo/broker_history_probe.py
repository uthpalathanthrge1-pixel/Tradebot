"""Read-only Capital.com DEMO transaction schema probe.

Call from an authenticated diagnostic route, never expose raw payloads.
No order placement, journal mutation, or assumption about P/L currency.
"""
from datetime import date, timedelta
from broker_history_validation import summarize_raw_history


def probe_history(capital_client, *, today=None, lookback_days=7):
    if not isinstance(lookback_days, int) or isinstance(lookback_days, bool) or not 1 <= lookback_days <= 30:
        raise ValueError('lookback_days must be 1..30')
    end = today or date.today()
    if not isinstance(end, date):
        raise ValueError('today must be a date')
    start = end - timedelta(days=lookback_days)
    # Uses existing read-only Capital.activity() adapter. Its query semantics
    # still need confirmation against the broker's API documentation.
    raw = capital_client.activity(start.isoformat(), end.isoformat())
    summary = summarize_raw_history(raw)
    return {
        'mode': 'read_only_schema_probe',
        'date_from': start.isoformat(),
        'date_to': end.isoformat(),
        **summary,
        'orders_submitted': False,
        'journal_updated': False,
        'currency_verified': False,
        'note': 'Field names only; never expose raw transactions or infer GBP.',
    }
