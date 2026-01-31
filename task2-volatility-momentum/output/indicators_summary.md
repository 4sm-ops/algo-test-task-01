# Volatility & Momentum Analysis Report

## Configuration

- **Windows (ticks):** 50 / 200 / 1000
- **EWMA decay (λ):** 0.94
- **Data source:** Gold futures (B3 + MOEX)

## Data Summary

| Metric | B3 (GLDG26) | MOEX (GOLD-3.26) |
|--------|-------------|------------------|
| Rows | 145,621 | 362,448 |
| Price Range | 4102.00 - 4311.25 | 4061.05 - 4285.10 |
| Avg Spread | 22.39 | 2.24 |
| Return Std | 0.000144 | 0.000063 |

## Volatility Summary

### Realized Volatility (window=200)

| Metric | B3 | MOEX |
|--------|-----|------|
| Mean | 0.001033 | 0.000724 |
| Median | 0.000571 | 0.000598 |
| Max | 0.031959 | 0.006474 |
| 95th percentile | 0.003055 | 0.001467 |

### EWMA Volatility

| Metric | B3 | MOEX |
|--------|-----|------|
| Mean | 0.000063 | 0.000047 |
| Median | 0.000034 | 0.000037 |
| Max | 0.004413 | 0.001538 |

## Momentum Summary

### ROC (window=200)

| Metric | B3 | MOEX |
|--------|-----|------|
| Mean | 0.0045% | 0.0024% |
| Std | 0.1070% | 0.0737% |
| % Positive | 48.8% | 51.3% |
| Autocorrelation | 0.982 | 0.993 |

## Output Files

| File | Description |
|------|-------------|
| `indicators_b3.html` | B3 indicators dashboard |
| `indicators_moex.html` | MOEX indicators dashboard |
| `comparison.html` | B3 vs MOEX comparison |
| `indicators_summary.md` | This report |

## Interpretation

### Volatility
- Higher volatility indicates larger price movements
- EWMA adapts faster to recent changes (useful for 400ms latency)
- Consider reducing position size when volatility is high

### Momentum
- Positive ROC = upward price movement
- Autocorrelation > 0 suggests momentum persistence (trend following)
- Autocorrelation < 0 suggests mean reversion
