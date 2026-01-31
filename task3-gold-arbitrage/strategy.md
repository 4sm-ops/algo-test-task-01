# Арбитражная стратегия: Gold B3 ↔ MOEX

## 1. Executive Summary

Стратегия статистического арбитража между фьючерсами на золото на биржах B3 (Бразилия) и MOEX (Россия). Эксплуатирует временные расхождения цен одного базового актива на разных рынках.

**Тип стратегии:** Market-neutral pairs trading
**Инструменты:** GLDG26 (B3) ↔ GOLD-3.26 (MOEX)
**Горизонт:** Внутридневной (intraday)

---

## 2. Допущения (Assumptions)

| Параметр | Допущение | Комментарий |
|----------|-----------|-------------|
| Базовый актив | Оба фьючерса привязаны к золоту | Разные биржи, но один underlying |
| Валюта расчётов | PnL в пунктах спреда, маржа в USD | Упрощение: игнорируем BRL/RUB конвертацию |
| Данные | Top-of-book (лучший bid/ask) | Структура CSV |
| Дубликаты в данных | Удаляем | Технический артефакт |
| Таймзона | UTC | Стандарт |
| Размер позиции | 1 контракт на каждой ноге | Market-neutral |
| Комиссии | **0.10 BRL за контракт** | Фиксированная комиссия |
| Slippage | Пересечение спреда (cross spread) | Worst-case execution |
| Latency B3 | **250 мс** | MOEX — мгновенно |
| ГО (маржа) | B3: $217, MOEX: $300 | Итого $517 на сделку |
| Время удержания | Без ограничений | Держим до сигнала выхода |
| Margin call | Не моделируется | Только initial margin check |

---

## 3. Описание данных

**Файл:** `quotes_202512260854-GOLD.csv`

| Поле | Описание |
|------|----------|
| `ts` | Timestamp (наносекунды) |
| `symbol` | `GLDG26` (B3) или `GOLD-3.26` (MOEX) |
| `bid_price` | Лучшая цена покупки |
| `bid_qty` | Объём на лучшем bid |
| `ask_price` | Лучшая цена продажи |
| `ask_qty` | Объём на лучшем ask |

**Предобработка:**
1. Удаление дубликатов
2. Фильтрация нулевых цен (bid=0 или ask=0)
3. Синхронизация по времени (forward-fill для выравнивания)

---

## 4. Логика стратегии

### 4.1 Расчёт спреда (по tradeable ценам)

**Важно:** Используем bid/ask цены, а не mid — по mid-ценам реально купить невозможно.

```python
# Для LONG спреда (покупаем B3, продаём MOEX):
spread_long = ask_b3 - bid_moex

# Для SHORT спреда (продаём B3, покупаем MOEX):
spread_short = bid_b3 - ask_moex
```

Каждое направление имеет свой Z-score: `zscore_long` и `zscore_short`.

### 4.2 Нормализация спреда (Z-score)

```python
zscore_long = (spread_long - rolling_mean(spread_long, N)) / rolling_std(spread_long, N)
zscore_short = (spread_short - rolling_mean(spread_short, N)) / rolling_std(spread_short, N)
```

Где `N = 1000` тиков — окно расчёта.

### 4.3 Торговые сигналы

| Условие | Действие |
|---------|----------|
| `zscore_short > +2.0` | **SHORT SPREAD**: Sell B3 @ bid, Buy MOEX @ ask |
| `zscore_long < -2.0` | **LONG SPREAD**: Buy B3 @ ask, Sell MOEX @ bid |
| `zscore_long > -0.5` (для LONG) | **Закрыть LONG** (спред вернулся к среднему) |
| `zscore_short < +0.5` (для SHORT) | **Закрыть SHORT** (спред вернулся к среднему) |
| `abs(zscore) > 4.0` | **Stop-loss** |

**Параметры по умолчанию:**
- `entry_threshold = 2.0` σ
- `exit_threshold = 0.5` σ
- `stop_loss_threshold = 4.0` σ
- `zscore_window = 1000` тиков

---

## 5. Сигналы входа и выхода

### Вход в позицию

```
IF no_position AND z_score > +2.0:
    SELL 1 GLDG26 @ ask_b3      # Продаём B3
    BUY  1 GOLD-3.26 @ ask_moex # Покупаем MOEX
    position = SHORT_SPREAD

IF no_position AND z_score < -2.0:
    BUY  1 GLDG26 @ ask_b3      # Покупаем B3
    SELL 1 GOLD-3.26 @ bid_moex # Продаём MOEX
    position = LONG_SPREAD
```

### Выход из позиции

```
IF position == SHORT_SPREAD AND z_score < +0.5:
    BUY  1 GLDG26 @ ask_b3      # Закрываем short B3
    SELL 1 GOLD-3.26 @ bid_moex # Закрываем long MOEX
    position = NONE

IF position == LONG_SPREAD AND z_score > -0.5:
    SELL 1 GLDG26 @ bid_b3      # Закрываем long B3
    BUY  1 GOLD-3.26 @ ask_moex # Закрываем short MOEX
    position = NONE
```

### Stop-loss

```
IF abs(z_score) > 4.0:
    CLOSE position immediately  # Спред ушёл слишком далеко
```

---

## 6. Risk Management

### 6.1 Позиционные лимиты

| Параметр | Значение |
|----------|----------|
| Max позиция на инструмент | 1 контракт |
| Max открытых сделок | 1 |
| Max убыток на сделку | 2% от капитала |
| Max дневной убыток | 5% от капитала |

### 6.2 Условия торговли

- **Ликвидность:** `bid_qty >= 1 AND ask_qty >= 1` на обоих инструментах
- **Спред:** `ask - bid < max_spread_threshold` (фильтр широкого спреда)
- **Время:** Только в пересечение торговых сессий B3 и MOEX

### 6.3 Риски стратегии

| Риск | Описание | Митигация |
|------|----------|-----------|
| Execution risk | Невозможность исполнить обе ноги одновременно | Лимитные ордера, проверка ликвидности |
| Model risk | Спред не возвращается к среднему | Stop-loss на 4σ |
| Liquidity risk | Недостаточная ликвидность | Фильтр по qty |
| Currency risk | Движение BRL/RUB | В данной версии игнорируется |
| Latency risk | Задержка между биржами | **Смоделировано**: B3 = 250 мс, MOEX = 0 мс |

---

## 7. Ожидаемые метрики

Для бэктеста на исторических данных планируется рассчитать:

| Метрика | Описание |
|---------|----------|
| **Total PnL** | Общая прибыль/убыток |
| **Number of trades** | Количество сделок |
| **Win rate** | % прибыльных сделок |
| **Average trade** | Средний PnL на сделку |
| **Sharpe Ratio** | Risk-adjusted return (annualized) |
| **Max Drawdown** | Максимальная просадка |
| **Profit Factor** | Gross profit / Gross loss |
| **Calmar Ratio** | Annualized return / Max Drawdown |
| **VaR 95%** | 5-й перцентиль PnL по сделкам |
| **ROI on Margin** | Net PnL / Margin * 100% |

---

## 8. Ограничения и следующие шаги

### Текущие ограничения

1. **Упрощённая модель валют** — не учитываем реальную конвертацию BRL/RUB/USD
2. **Размер контракта** — не учтён реальный notional value
3. **Margin call** — не моделируется (только initial margin check)

### Выполненные шаги

1. [x] Загрузка и очистка данных из CSV
2. [x] Расчёт спреда по tradeable ценам (bid/ask)
3. [x] Dual Z-score (zscore_long, zscore_short)
4. [x] Реализация бэктеста с latency (B3: 250 мс)
5. [x] Фиксированная комиссия (0.10 BRL/контракт)
6. [x] Моделирование маржи (ГО): B3 $217 + MOEX $300
7. [x] Метрики: Calmar, VaR 95%, ROI on margin
8. [x] Визуализация (Plotly dashboards)

### Следующие шаги

1. [ ] Оптимизация параметров (threshold, window)
2. [ ] Анализ чувствительности к комиссиям
3. [ ] Фильтр по ширине спреда B3

---

## 9. Реализация (Python)

### 9.1 Структура проекта

```
task3-gold-arbitrage/
├── config.py              # Параметры стратегии (~50 LOC)
├── main.py                # Основной скрипт (~300 LOC)
├── requirements.txt       # Зависимости
├── src/
│   ├── __init__.py
│   ├── data_loader.py     # Загрузка CSV (~90 LOC)
│   ├── indicators.py      # Z-score (~50 LOC)
│   └── backtest.py        # Движок бэктеста (~200 LOC)
├── output/
│   ├── backtest_report.md # Отчёт
│   ├── backtest_results.png # Графики
│   └── trades.csv         # Список сделок
└── strategy.md            # Документация
```

### 9.2 Запуск

```bash
cd task3-gold-arbitrage
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 9.3 Модули

#### config.py
Dataclass-конфигурация с параметрами стратегии:
- `entry_threshold`, `exit_threshold`, `stop_loss_threshold` — пороги Z-score
- `zscore_window` — окно расчёта
- `commission_per_contract` — комиссия (0.10 BRL)
- `b3_latency_ms` — задержка исполнения B3 (250 мс)
- `margin_b3`, `margin_moex` — маржинальные требования в USD
- `symbol_b3`, `symbol_moex` — тикеры инструментов

#### src/data_loader.py
- `load_quotes()` — загрузка CSV, очистка заголовков, удаление дубликатов
- `prepare_synchronized_data()` — объединение данных B3 и MOEX по времени с forward-fill
- `get_data_summary()` — статистика по данным

#### src/indicators.py
- `calculate_tradeable_spreads()` — spread_long и spread_short по bid/ask
- `calculate_zscore_dual()` — rolling Z-score для обоих направлений
- `add_indicators()` — добавление всех индикаторов в DataFrame

#### src/backtest.py
- `Backtest` класс — движок симуляции с поддержкой:
  - Открытие/закрытие позиций по сигналам
  - **Latency моделирование**: MOEX мгновенно, B3 через 250 мс
  - Фиксированная комиссия (0.10 BRL/контракт)
  - Stop-loss на 4σ
  - Проверка ликвидности
- `BacktestResult` — метрики (PnL, Sharpe, Calmar, VaR, ROI on margin)
- `Trade`, `Position` — структуры данных

#### src/visualization.py
- `plot_equity_plotly()` — интерактивная кривая капитала
- `plot_strategy_dashboard()` — комплексный дашборд (цены, спреды, Z-score, equity)

#### main.py
- Загрузка данных
- Расчёт индикаторов
- Запуск бэктеста
- Генерация отчётов и графиков

---

## 10. Результаты бэктеста

### 10.1 Параметры

| Параметр | Значение |
|----------|----------|
| Entry threshold | 2.0 σ |
| Exit threshold | 0.5 σ |
| Stop loss | 4.0 σ |
| Z-score window | 1000 ticks |
| Commission | **0.10 BRL/контракт** |
| B3 latency | **250 мс** |
| Margin B3 | **$217** (~1,300 BRL) |
| Margin MOEX | **$300** (~30,000 ₽) |

### 10.2 Данные

| Метрика | Значение |
|---------|----------|
| Период | 2025-11-24 — 2025-12-09 |
| Всего строк | 498,188 |
| B3 avg spread | **26.34** пунктов |
| MOEX avg spread | **2.22** пункта |

### 10.3 Результаты (с учётом latency и маржи)

| Метрика | Значение |
|---------|----------|
| Количество сделок | 1,590 |
| Win rate | 0.9% |
| Total PnL | -41,416 |
| Total commission | 636 |
| **Net PnL** | **-42,052** |
| Max drawdown | 42,052 |
| Sharpe ratio | -20.84 |
| Profit factor | 0.00 |
| Calmar ratio | -0.50 |
| VaR 95% | -75 |
| Margin per trade | **$517** |
| **ROI on margin** | **-8,134%** |

### 10.4 Анализ результатов

**Стратегия убыточна.** Основные причины:

1. **Огромный спред на B3** (~26 пунктов vs ~2 на MOEX)
   - При каждой сделке теряем на crossing the spread
   - Mean-reversion не компенсирует эти потери
   - Средний убыток на сделку: **-26.45 пунктов**

2. **Latency B3** (250 мс)
   - Дополнительный slippage при исполнении
   - Цена B3 меняется между сигналом и исполнением

3. **Асимметрия ликвидности**
   - MOEX: узкий спред, высокая ликвидность
   - B3: широкий спред, низкая ликвидность
   - Арбитраж требует сопоставимой ликвидности

4. **ROI on margin: -8,134%**
   - Потеря превышает маржу в 81 раз
   - Полное уничтожение капитала

### 10.5 Рекомендации по улучшению

1. **Фильтр по спреду B3** — торговать только когда spread_b3 < threshold
2. **Увеличить порог входа** — entry_threshold = 3.0-4.0 σ
3. **Использовать лимитные ордера** вместо market orders
4. **Оптимизация окна** — подобрать zscore_window
5. **Альтернативная стратегия** — торговать только MOEX, используя B3 как сигнал

---

## Приложение A: Диаграмма логики стратегии

```mermaid
flowchart TD
    subgraph DATA["📊 Данные"]
        CSV[(quotes.csv)] --> LOAD[Загрузка данных]
        LOAD --> DEDUP[Удаление дубликатов]
        DEDUP --> FILTER[Фильтрация нулевых цен]
        FILTER --> SYNC[Синхронизация B3 + MOEX]
    end

    subgraph INDICATORS["📈 Индикаторы"]
        SYNC --> SPREAD_LONG["spread_long = ask_b3 - bid_moex"]
        SYNC --> SPREAD_SHORT["spread_short = bid_b3 - ask_moex"]
        SPREAD_LONG --> ZSCORE_LONG["zscore_long = (spread_long - μ) / σ"]
        SPREAD_SHORT --> ZSCORE_SHORT["zscore_short = (spread_short - μ) / σ"]
    end

    subgraph SIGNALS["🎯 Сигналы"]
        ZSCORE_LONG --> CHECK_POS{Есть позиция?}
        ZSCORE_SHORT --> CHECK_POS

        CHECK_POS -->|Нет| ENTRY_CHECK{Z-score?}
        ENTRY_CHECK -->|"zscore_short > +2.0"| SHORT_SPREAD["🔴 SHORT SPREAD<br/>Sell B3, Buy MOEX"]
        ENTRY_CHECK -->|"zscore_long < -2.0"| LONG_SPREAD["🟢 LONG SPREAD<br/>Buy B3, Sell MOEX"]
        ENTRY_CHECK -->|"в пределах ±2.0"| NO_ACTION[Ждём сигнала]

        CHECK_POS -->|Да| EXIT_CHECK{Условие выхода?}
        EXIT_CHECK -->|"zscore_short < +0.5"| CLOSE_SHORT["Закрыть SHORT"]
        EXIT_CHECK -->|"zscore_long > -0.5"| CLOSE_LONG["Закрыть LONG"]
        EXIT_CHECK -->|"zscore > ±4.0"| STOP_LOSS["⛔ STOP LOSS"]
        EXIT_CHECK -->|Нет| HOLD[Держим позицию]
    end

    subgraph EXECUTION["⚡ Исполнение с Latency"]
        SHORT_SPREAD --> EXEC_SHORT["MOEX: BUY @ ask (instant)<br/>B3: SELL @ bid (+250ms)"]
        LONG_SPREAD --> EXEC_LONG["MOEX: SELL @ bid (instant)<br/>B3: BUY @ ask (+250ms)"]
        CLOSE_SHORT --> EXEC_CLOSE_S["MOEX: SELL @ bid (instant)<br/>B3: BUY @ ask (+250ms)"]
        CLOSE_LONG --> EXEC_CLOSE_L["MOEX: BUY @ ask (instant)<br/>B3: SELL @ bid (+250ms)"]
        STOP_LOSS --> EXEC_STOP["Закрыть по рынку"]

        EXEC_SHORT --> COMMISSION["Комиссия: 0.10 BRL × 4"]
        EXEC_LONG --> COMMISSION
        EXEC_CLOSE_S --> COMMISSION
        EXEC_CLOSE_L --> COMMISSION
        EXEC_STOP --> COMMISSION
    end

    subgraph METRICS["📉 Метрики"]
        COMMISSION --> PNL["PnL (points)"]
        PNL --> EQUITY["Equity Curve"]
        EQUITY --> RESULTS["Sharpe, Calmar, VaR 95%,<br/>ROI on Margin"]
    end

    NO_ACTION --> NEXT[Следующий тик]
    HOLD --> NEXT
    RESULTS --> NEXT
    NEXT --> ZSCORE_LONG
    NEXT --> ZSCORE_SHORT

    style SHORT_SPREAD fill:#ffcccc
    style LONG_SPREAD fill:#ccffcc
    style STOP_LOSS fill:#ff9999
    style RESULTS fill:#cceeff
```

### Диаграмма состояний позиции

```mermaid
stateDiagram-v2
    [*] --> FLAT: Старт

    FLAT --> LONG_SPREAD: zscore_long < -2.0
    FLAT --> SHORT_SPREAD: zscore_short > +2.0

    LONG_SPREAD --> FLAT: zscore_long > -0.5 (profit)
    LONG_SPREAD --> FLAT: zscore_short > 4.0 (stop-loss)

    SHORT_SPREAD --> FLAT: zscore_short < +0.5 (profit)
    SHORT_SPREAD --> FLAT: zscore_long < -4.0 (stop-loss)

    note right of FLAT
        Нет открытых позиций
        Ждём сигнала входа
    end note

    note right of LONG_SPREAD
        Buy B3 @ ask (+250ms)
        Sell MOEX @ bid (instant)
    end note

    note left of SHORT_SPREAD
        Sell B3 @ bid (+250ms)
        Buy MOEX @ ask (instant)
    end note
```

### Схема расчёта двойных спредов и Z-score

```mermaid
flowchart LR
    subgraph INPUT["Входные данные"]
        B3_BID[bid_b3]
        B3_ASK[ask_b3]
        MOEX_BID[bid_moex]
        MOEX_ASK[ask_moex]
    end

    subgraph SPREADS["Tradeable Spreads"]
        B3_ASK --> SPREAD_LONG["spread_long =<br/>ask_b3 - bid_moex"]
        MOEX_BID --> SPREAD_LONG
        B3_BID --> SPREAD_SHORT["spread_short =<br/>bid_b3 - ask_moex"]
        MOEX_ASK --> SPREAD_SHORT
    end

    subgraph ROLLING["Rolling (N=1000)"]
        SPREAD_LONG --> MEAN_L["μ_long"]
        SPREAD_LONG --> STD_L["σ_long"]
        SPREAD_SHORT --> MEAN_S["μ_short"]
        SPREAD_SHORT --> STD_S["σ_short"]
    end

    subgraph ZSCORE_CALC["Z-scores"]
        SPREAD_LONG --> Z_LONG["zscore_long =<br/>(spread_long - μ) / σ"]
        MEAN_L --> Z_LONG
        STD_L --> Z_LONG
        SPREAD_SHORT --> Z_SHORT["zscore_short =<br/>(spread_short - μ) / σ"]
        MEAN_S --> Z_SHORT
        STD_S --> Z_SHORT
    end

    Z_LONG --> SIGNAL_LONG{{"LONG: zscore_long < -2"}}
    Z_SHORT --> SIGNAL_SHORT{{"SHORT: zscore_short > +2"}}
```

---

## Приложение B: Формулы

### Z-score
$$z = \frac{x - \mu}{\sigma}$$

### Sharpe Ratio
$$SR = \frac{E[R] - R_f}{\sigma_R} \times \sqrt{252}$$

### Maximum Drawdown
$$MDD = \max_{t} \left( \frac{\max_{s \leq t} P_s - P_t}{\max_{s \leq t} P_s} \right)$$
