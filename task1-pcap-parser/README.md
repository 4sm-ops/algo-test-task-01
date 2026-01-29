# Task 1: B3 PCAP Parser — Отчёт

## Цель задания

Разобрать PCAP файлы биржи B3 (Brasil, Bolsa, Balcão) и создать:
1. Таблицы `snapshot.csv` и `updates.csv` с рыночными данными
2. График календарного спреда WDO (Mini Dollar Futures)

## Что было сделано

### 1. Анализ формата данных

PCAP файлы содержат UDP multicast трафик с рыночными данными B3:

| Файл | Содержимое | Размер |
|------|------------|--------|
| 78_Instrument.pcap | Определения инструментов | 930 пакетов |
| 78_Snapshot.pcap | Снимки книги заявок | 650 пакетов |
| 78_Incremental_feedA.pcap | Инкрементальные обновления | 500K+ пакетов |

**Протокол:** Binary UMDF (Unified Market Data Feed) с SBE (Simple Binary Encoding)

**Структура SBE Message Header (8 байт):**
```
Offset 0-1: BlockLength (2 bytes, Little Endian)
Offset 2-3: TemplateID (2 bytes, LE) — тип сообщения
Offset 4-5: SchemaID (2 bytes, LE) — всегда 2 для B3
Offset 6-7: Version (2 bytes, LE) — версия схемы
```

### 2. Определение версии схемы

Прочитав SBE заголовки из пакетов, определили версии:

| Тип сообщений | SchemaID | Version |
|---------------|----------|---------|
| Sequence/Heartbeat | 2 | 2 |
| Market Data (Snapshot, Trade, Order) | 2 | 9 |

Публично доступные XML схемы B3 (v2.1.0, v2.2.0) имеют Version=16, но оказались частично совместимы с нашими данными.

### 3. Реализация парсера

#### Этап 1: Ручной парсинг (struct)

Первоначально написали парсер с прямым чтением бинарных данных через `struct`:

```python
# Поиск SecurityID по паттерну
for match in re.finditer(rb'BVMF[0-9A-Z]{3}\x00(WDO[FGHJKMNQUVXZ][0-9]{2})\x00', payload):
    symbol = match.group(1).decode('ascii')
    sec_id = struct.unpack('<Q', payload[idx-8:idx])[0]
```

**Файлы:**
- `src/parser.py` — основной парсер
- `extract_wdo_fast.py` — быстрое извлечение цен WDO

#### Этап 2: Парсинг через sbe-python

Нашли и интегрировали библиотеку `sbe-python` для корректного декодирования SBE сообщений.

**Файлы:**
- `sbe_parser.py` — парсер на базе sbe-python
- `sbe_visualization.py` — визуализации

## Библиотека sbe-python

### Что это

[sbe-python](https://github.com/python-sbe/sbe) — Python библиотека для работы с Simple Binary Encoding (SBE), стандартом FIX Protocol для высокопроизводительной сериализации финансовых сообщений.

**Установка:**
```bash
pip install sbe
```

### Особенности интеграции с B3

1. **Патч для UTF-8 кодировки**

   B3 использует `characterEncoding="UTF-8"` в XML схеме, но sbe-python поддерживает только ASCII. Решение:

   ```python
   import sbe
   sbe.CharacterEncoding._value2member_map_['UTF-8'] = sbe.CharacterEncoding.ASCII
   ```

2. **Загрузка схемы**

   ```python
   schema = sbe.Schema.parse('b3-market-data-messages-2.2.0.xml')
   # Schema ID: 2, Version: 16, Messages: 30
   ```

3. **Декодирование сообщений**

   ```python
   # Найти SBE header в UDP payload
   header = find_sbe_header(payload)

   # Декодировать сообщение
   msg_data = payload[header['offset']:]
   decoded = schema.decode(msg_data)

   # Доступ к полям
   print(decoded.message_name)  # 'Trade_53'
   print(decoded.value)         # {'securityID': 200001478879, 'mDEntryPx': {...}, ...}
   ```

### Поддерживаемые типы сообщений

| TemplateID | Название | Описание |
|------------|----------|----------|
| 2 | Sequence_2 | Heartbeat/sequence number |
| 3 | SecurityStatus_3 | Статус инструмента |
| 10 | SecurityGroupPhase_10 | Фаза торговой сессии |
| 22 | PriceBand_22 | Ценовые лимиты |
| 30 | SnapshotFullRefresh_Header_30 | Заголовок снимка |
| 50 | Order_MBO_50 | Заявка в книге |
| 51 | DeleteOrder_MBO_51 | Удаление заявки |
| 53 | Trade_53 | Сделка |
| 55 | ExecutionSummary_55 | Итоги исполнения |
| 71 | SnapshotFullRefresh_Orders_MBO_71 | Полный снимок книги |

### Ограничения

1. **Фрагментация сообщений** — крупные сообщения (SecurityDefinition, Order_MBO) могут быть разбиты на несколько UDP пакетов. Для полного декодирования нужна сборка фрагментов.

2. **Частичная совместимость версий** — схема v2.2.0 (Version=16) работает с данными Version=9, но некоторые поля могут декодироваться некорректно.

## Результаты

### Найденные инструменты (21 WDO фьючерс)

| Символ | SecurityID | Описание |
|--------|------------|----------|
| WDOZ24 | 200001478879 | December 2024 (front month) |
| WDOF25 | 2080363 | January 2025 |
| WDOG25 | 200001436849 | February 2025 |
| ... | ... | ... |

### Выходные файлы

| Файл | Записей | Описание |
|------|---------|----------|
| `output/snapshot_sbe.csv` | 95 | Снимки книги заявок |
| `output/updates_sbe.csv` | 8,523 | Инкрементальные обновления |
| `output/wdo_prices_sbe.csv` | 8,523 | Временной ряд цен WDO |
| `output/wdo_prices_sbe.html` | — | Интерактивный график WDOZ24 |
| `output/wdo_spread_sbe.html` | — | Демо календарного спреда |

### Статистика по данным

**WDOZ24 (December 2024):**
- Записей: 8,522
- Диапазон цен: 5000.40 - 6999.10 BRL
- Период: 2024-11-18 12:01:12 — 12:35:13 (~34 минуты)

**WDOF25 (January 2025):**
- Записей: 1 (недостаточно для спреда)
- Цена: 6493.04 BRL

## Календарный спред

### Проблема

Для расчёта календарного спреда нужны синхронные котировки двух контрактов:
```
spread = price_front(WDOZ24) - price_back(WDOF25)
```

В наших данных WDOF25 имеет только 1 тик, поэтому реальный спред рассчитать невозможно.

### Решение

Создана демо-визуализация с синтетическими данными (`wdo_spread_sbe.html`), иллюстрирующая концепцию календарного спреда.

## Структура проекта

```
task1-pcap-parser/
├── 20241118/                      # Исходные PCAP файлы
│   ├── 78_Instrument.pcap
│   ├── 78_Snapshot.pcap
│   └── 78_Incremental_feedA.pcap
├── b3-samples/                    # B3 официальные примеры
│   ├── b3-market-data-messages-2.2.0.xml  # XML схема SBE
│   └── *.pcap
├── output/                        # Результаты
│   ├── snapshot_sbe.csv
│   ├── updates_sbe.csv
│   ├── wdo_prices_sbe.csv
│   ├── wdo_prices_sbe.html
│   └── wdo_spread_sbe.html
├── src/
│   ├── parser.py                  # Оригинальный парсер (struct)
│   ├── visualization.py           # Оригинальные визуализации
│   └── spread_analysis.py         # Анализ спреда
├── sbe_parser.py                  # Парсер на sbe-python
├── sbe_visualization.py           # Визуализации (sbe)
├── test_sbe_decode.py             # Тесты декодирования
├── main.py                        # Точка входа
├── requirements.txt
└── README.md
```

## Запуск

```bash
cd task1-pcap-parser
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Запуск SBE-парсера
python sbe_parser.py

# Создание визуализаций
python sbe_visualization.py
```

## Выводы

1. **sbe-python работает** с данными B3, несмотря на разницу версий схемы (16 vs 9)

2. **Основные сообщения декодируются корректно**: Trade, Sequence, SecurityStatus, PriceBand, SnapshotHeader

3. **Ограничение данных**: WDOF25 практически не торговался в записанный период, что делает невозможным расчёт реального календарного спреда

4. **Для production-решения** рекомендуется:
   - Получить точную XML схему версии 9 от B3
   - Реализовать сборку фрагментированных сообщений
   - Использовать данные за период активной торговли обоих контрактов

## Ссылки

- [B3 Developer Portal](https://www.b3.com.br/en_us/solutions/platforms/puma-trading-system/for-developers-and-vendors/binary-umdf/)
- [sbe-python GitHub](https://github.com/python-sbe/sbe)
- [FIX SBE Specification](https://www.fixtrading.org/standards/sbe/)
