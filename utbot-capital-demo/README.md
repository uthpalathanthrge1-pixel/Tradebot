# UT Bot → Capital.com demo integration (Phase 1)

**Signal-only prototype: execution is disabled. No broker orders are submitted.**

Strategy requested: 1-minute UT Bot close-and-reverse on Gold and Oil, £1,000 margin allocation per trade with instrument-specific leverage, no individual stop-loss/take-profit, and £100 combined net-loss shutdown. The latter is **not implemented** in Phase 1 and is not a guaranteed loss cap.

## Files
- `utbot_v6.pine`: TradingView Pine Script v6 alerts on confirmed 1-minute candles.
- `app.py`: FastAPI webhook receiver with duplicate detection and persistent signal logging.
- `capital.py`: demo API adapter; **not used to execute orders in this build**.
- `.env.example`: placeholder configuration only.
- `../render.yaml`: Render Blueprint for this subfolder.

## Deploy via Render
1. In Render, choose **New → Blueprint** and connect the GitHub repository `uthpalathanthrge1-pixel/Tradebot`.
2. The root-level `render.yaml` points to the `utbot-capital-demo` subfolder. Review paid service and disk pricing before applying.
3. In the service environment, verify `WEBHOOK_SECRET` is generated. Do not publish it. Leave `ENABLE_DEMO_ORDERS=false`.
4. On TradingView, add `utbot_v6.pine` to a 1-minute chart. Create an alert with **Any alert() function call**, once per bar close, and webhook URL `https://YOUR-SERVICE.onrender.com/webhook/YOUR-WEBHOOK-SECRET`. TradingView webhook eligibility and 2FA requirements apply.
5. Check `https://YOUR-SERVICE.onrender.com/health` for server health. To view logged signals use `/status/YOUR-WEBHOOK-SECRET` (keep URL private).

## Before enabling demo trading
Verify Capital.com spread-betting demo API order support and selected account, Gold/Oil EPICs, deal sizes, GBP conversion and instrument margin requirements. Implement confirmed close-and-reverse with position reconciliation, persistent realised+unrealised net GBP P&L, emergency liquidation at the -£100 threshold, outage handling, and manual reset. Test thoroughly. With no broker-side stops, loss can exceed £100 during outages or fast markets.

Documentation: https://open-api.capital.com/ and https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/
