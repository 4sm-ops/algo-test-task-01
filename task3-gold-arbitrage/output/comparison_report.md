# Market Orders vs Limit Orders: Comparison Report

Generated: 2026-02-23 21:10:57

## Parameters

- Entry threshold: 2.0σ
- Exit threshold: 0.5σ
- Stop loss: 4.0σ
- Z-score window: 1000 ticks
- B3 latency: 250 ms
- Limit price mode: mid
- Limit timeout: 5000 ms
- Max B3 spread: 30.0 pts

## Results

| Metric | Market Orders | Limit Orders |
|--------|--------------|-------------|
| Trades | 1590 | 17 |
| Net PnL | -42052.35 | -40.63 |
| Avg PnL/trade | -26.45 | -2.39 |
| Win rate | 0.9% | 17.6% |
| Max drawdown | 42052.35 | 40.63 |
| Sharpe | -20.84 | -11.16 |
| Profit factor | 0.00 | 0.06 |
| ROI on margin | -8133.9% | -7.9% |
| Fill rate | 100% (market) | 0.0% |

## Fill Model

**Price Touch model:** A limit BUY at price P fills when `ask_b3 ≤ P` after the latency delay, within the timeout window.

**Limitations:**
- Does NOT model queue position (optimistic)
- Does NOT account for adverse selection
- MOEX executes at market at B3 fill time (not signal time)

## Limit Order Statistics

- Orders attempted: 140055
- Orders filled: 33
- Fill rate: 0.0%
- Avg fill time: 3209 ms
