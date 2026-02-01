# Task 1: B3 PCAP Parser

## Задание

> **Контекст:** архив с pcap-файлами с биржи B3.
>
> **Задача 1.1:** Разобрать архив и записать таблицы snapshot, updates.
>
> **Задача 1.2:** Вывести календарный спред между фьючерсами WDO разных месяцев.

---

## Результаты

### CSV-файлы с разбором PCAP

| Файл | Записей | Описание |
|------|---------|----------|
| [snapshot_sbe.csv](output/snapshot_sbe.csv) | 95 | Снимки top-of-book |
| [updates_sbe.csv](output/updates_sbe.csv) | 8,523 | Ордера из order book |
| [orderbook_tob_sbe.csv](output/orderbook_tob_sbe.csv) | 118 | Top-of-book из восстановленного стакана |

### График календарного спреда WDO

**Контракты:** WDOZ24 (декабрь 2024) vs WDOF25 (январь 2025)

![WDO Calendar Spread](output/wdo_spread_screenshot.png)

**Интерактивный график:** [wdo_spread_sbe.html](output/wdo_spread_sbe.html)

**Типы спредов** (подтверждено автором задания):

| Тип | Формула | Описание |
|-----|---------|----------|
| Ask-Ask | `front_ask - back_ask` | Спред по ценам предложения |
| Bid-Bid | `front_bid - back_bid` | Спред по ценам спроса |
| Ask-Bid | `front_ask - back_bid` | Худший для покупателя |
| Bid-Ask | `front_bid - back_ask` | Худший для продавца |

> **Примечание:** В данных WDOF25 имеет только 1 тик, поэтому график построен на синтетических данных для демонстрации концепции.

---

## Требования (подтверждённые автором)

- **Snapshot**: только top-of-book (лучший bid/ask)
- **Updates**: только стакан (order book), трейды не нужны
- **Order Book**: восстанавливать из ордеров (Order_MBO_50, DeleteOrder_MBO_51)
- **Календарный спред**: 4 типа расчёта (Ask-Ask, Bid-Bid, Ask-Bid, Bid-Ask)

---

## Исходные данные

PCAP файлы в `20241118/`:

| Файл | Содержимое | Размер |
|------|------------|--------|
| 78_Instrument.pcap | Определения инструментов | 930 пакетов |
| 78_Snapshot.pcap | Top-of-book снимки | 650 пакетов |
| 78_Incremental_feedA.pcap | Инкрементальные обновления | 500K+ пакетов |

**Протокол:** Binary UMDF (Unified Market Data Feed) с SBE (Simple Binary Encoding)

**Найденные WDO контракты:**

| Символ | SecurityID | Тиков в данных |
|--------|------------|----------------|
| WDOZ24 | 200001478879 | 8,522 |
| WDOF25 | 2080363 | 1 |
| WDOG25 | 200001436849 | 3 |

---

## Запуск

```bash
cd task1-pcap-parser
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Парсинг PCAP → CSV
python sbe_parser.py

# Создание графиков
python sbe_visualization.py
```

---

## Технические детали

### Библиотека sbe-python

Использована библиотека [sbe-python](https://github.com/python-sbe/sbe) для декодирования SBE сообщений.

**Патч для UTF-8:**
```python
import sbe
sbe.CharacterEncoding._value2member_map_['UTF-8'] = sbe.CharacterEncoding.ASCII
```

### Структура SBE Message Header

```
Offset 0-1: BlockLength (2 bytes, LE)
Offset 2-3: TemplateID (2 bytes, LE) — тип сообщения
Offset 4-5: SchemaID (2 bytes, LE) — всегда 2 для B3
Offset 6-7: Version (2 bytes, LE) — версия схемы
```

### Типы сообщений

| TemplateID | Название | Использование |
|------------|----------|---------------|
| 50 | Order_MBO_50 | ✅ Ордера для стакана |
| 51 | DeleteOrder_MBO_51 | ✅ Удаление ордеров |
| 53 | Trade_53 | ❌ Не используем |
| 71 | SnapshotFullRefresh_Orders_MBO_71 | ✅ Снимки |

### Восстановление Order Book

Реализовано в `order_book.py`:
- Класс `OrderBook` — стакан для одного инструмента
- Класс `OrderBookManager` — управление стаканами всех инструментов
- Методы: `add_order`, `delete_order`, `modify_order`, `get_top_of_book`

---

## Структура проекта

```
task1-pcap-parser/
├── 20241118/                      # Исходные PCAP файлы
├── b3-samples/                    # XML схема SBE
├── output/                        # CSV и HTML результаты
│   ├── snapshot_sbe.csv
│   ├── updates_sbe.csv
│   ├── orderbook_tob_sbe.csv
│   ├── wdo_prices_sbe.html
│   └── wdo_spread_sbe.html
├── sbe_parser.py                  # Основной парсер
├── sbe_visualization.py           # Визуализации
├── order_book.py                  # Восстановление стакана
├── requirements.txt
└── README.md
```

---

## Ограничения

1. **Данные WDOF25 недостаточны** — только 1 тик за весь период
2. **Версия схемы** — данные используют Version=9, публичные схемы B3 имеют Version=16
3. **Фрагментация** — крупные сообщения могут быть разбиты на несколько UDP пакетов

---

## Ссылки

- [B3 Developer Portal](https://www.b3.com.br/en_us/solutions/platforms/puma-trading-system/for-developers-and-vendors/binary-umdf/)
- [sbe-python GitHub](https://github.com/python-sbe/sbe)
- [FIX SBE Specification](https://www.fixtrading.org/standards/sbe/)
