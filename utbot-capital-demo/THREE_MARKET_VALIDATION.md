# Gold, Oil and US500: read-only validation branch

This branch is **not deployed**. No live or demo order execution is enabled.

## Scope
- Gold, Oil, US500 are declared in `market_validation.MARKETS`.
- A pure conservative sizing preview targets **GBP 1,500 margin** and rounds down.
- The preview is *not* an executable order size. Contract multiplier, increment,
  GBP conversion, leverage/margin and actual account buying power must be
  verified against broker data before using it.
- `inspect_market` reads broker market details only and reports missing data.
- No broker POST, PUT or DELETE is invoked by these additions.
- Existing application, one-off test locks, risk gate, Render config, and
  production webhook are untouched.

## Offline tests
From `utbot-capital-demo`:
```bash
python -m unittest discover -s tests -p 'test_market_validation.py'
```

## Before any integration
1. Verify selected account is the intended GBP CFD **demo** account and active session.
2. Confirm the exact US500 EPIC and the Gold/Oil EPICs via broker discovery.
3. Confirm broker deal size increment, contract value, quote currency and GBP FX.
4. Reconcile broker-estimated margin and account available funds.
5. Resolve previous one-off Gold reconciliation failure; preserve test lock.
6. Implement serial per-market close/confirm/reconcile/open state machine with
   durable idempotency, unknown-result halt, and broker-confirmed P/L monitoring.
7. Independently approve demo execution after controlled tests. Live remains disabled.
