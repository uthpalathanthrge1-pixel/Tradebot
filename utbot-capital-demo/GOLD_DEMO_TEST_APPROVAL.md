# Isolated 0.01 Gold DEMO test — approval checklist (NO EXECUTION)

Status: PREPARATION ONLY. This document does not authorise a broker order.

## Verified baseline
- GBP CFD DEMO account identified; zero positions at last preflight.
- Main bot disabled (ENABLE_DEMO_ORDERS=false), risk ledger halted/not_armed.
- Previous one-off test locked with position_reconciliation_failed; preserve permanently.
- Eight offline tests passed. They do not verify Capital.com live close semantics.
- V2 execution_gate currently returns execution_adapter_not_installed even when its flags are true. No V2 execution adapter exists.

## Required before requesting final order approval
1. Independently verify Gold market epic, account ID/type, market status, min deal size, size increment, margin factor, quote currency, GBP conversion and estimated spread/fees using broker read-only endpoints. Do not assume 0.01 is accepted or low-risk.
2. Check zero open positions immediately before submission; confirm broker account and no pending orders; verify persistent test lock and ensure an isolated V2 idempotency key/one-attempt record survives Render restarts.
3. Confirm an actual Capital.com DEMO close-position API contract, including method, deal ID, size and direction requirements, and accepted/rejected confirmation handling. Mocked DELETE tests are insufficient.
4. Implement a one-off operator-approved adapter isolated from TradingView webhook; never change ENABLE_DEMO_ORDERS, global risk halt or existing test record. No automatic retry on POST/DELETE or ambiguous broker outcome.
5. Define maximum acceptable loss, slippage, stop/limit protection, time-in-market and an operator-supervised manual-close fallback; never promise guaranteed loss caps.
6. Operator must be present and approve the exact Gold epic, 0.01 size, side, margin estimate, maximum loss and close procedure immediately before any order submission.

## Proposed single attempt after separate approval
- Persist attempt ID as pending before network call; reject all repeated submissions.
- Submit at most one DEMO open; require accepted confirmation and unique permanent deal ID.
- Reconcile exact deal ID, epic, side and size against broker positions. If ambiguous, halt and ask operator to inspect manually; never submit a second open.
- Close the uniquely reconciled position only after the close API is independently verified; confirm accepted close and absence from broker positions. If unresolved, halt and escalate to manual broker close.
- Read closed transaction record; only journal realised net GBP P/L if deal linkage, currency, costs and signed amount are independently verified. Otherwise record unresolved status, not a fabricated £ amount.
- Keep all execution disabled after the attempt regardless of result.

## Explicit exclusions
No live account. No unattended execution. No reset of prior lock. No automated Gold or Oil webhook trading. No automatic risk-ledger arming. No claim that the -£100 combined loss monitor is active.
