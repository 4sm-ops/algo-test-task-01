#!/usr/bin/env python3
"""
B3 PCAP Parser using sbe-python library.

Parses PCAP files from B3 exchange using proper SBE decoding.
Reconstructs order book from Order_MBO messages.
Generates CSV files and visualizations for WDO futures.
"""

import struct
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional
from collections import defaultdict

import sbe
import pandas as pd
from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP

from order_book import OrderBookManager, TopOfBook

# Patch sbe-python to accept UTF-8 encoding (B3 uses UTF-8 in schema)
sbe.CharacterEncoding._value2member_map_['UTF-8'] = sbe.CharacterEncoding.ASCII

BASE_DIR = Path(__file__).parent
SCHEMA_FILE = BASE_DIR / 'b3-samples' / 'b3-market-data-messages-2.2.0.xml'
DATA_DIR = BASE_DIR / '20241118'
OUTPUT_DIR = BASE_DIR / 'output'


@dataclass
class Instrument:
    """Instrument definition."""
    security_id: int
    symbol: str
    security_exchange: str = ''


@dataclass
class MDEntry:
    """Market data entry."""
    timestamp_ns: int
    security_id: int
    symbol: str
    entry_type: str  # 'BID', 'OFFER', 'TRADE', etc.
    price: float
    size: int
    source: str  # 'SNAPSHOT' or 'INCREMENTAL'


def load_schema() -> sbe.Schema:
    """Load B3 SBE schema."""
    print(f"Loading schema: {SCHEMA_FILE.name}")
    schema = sbe.Schema.parse(str(SCHEMA_FILE))
    print(f"  Schema ID: {schema.id}, Version: {schema.version}")
    return schema


def find_sbe_header(payload: bytes, target_schema_id: int = 2) -> Optional[dict]:
    """Find SBE message header in UDP payload."""
    for pos in range(len(payload) - 8):
        schema_id = struct.unpack('<H', payload[pos+4:pos+6])[0]
        version = struct.unpack('<H', payload[pos+6:pos+8])[0]
        if schema_id == target_schema_id and 1 <= version <= 20:
            return {
                'offset': pos,
                'block_len': struct.unpack('<H', payload[pos:pos+2])[0],
                'template_id': struct.unpack('<H', payload[pos+2:pos+4])[0],
                'schema_id': schema_id,
                'version': version,
            }
    return None


def extract_timestamp(payload: bytes) -> int:
    """Extract timestamp from UMDF packet header."""
    # Timestamp is typically at offset 8-16 in the framing header
    if len(payload) >= 16:
        return struct.unpack('<Q', payload[8:16])[0]
    return 0


def parse_instruments_sbe(pcap_path: str, schema: sbe.Schema) -> Dict[int, Instrument]:
    """
    Parse instrument definitions from PCAP using SBE decoder.

    Note: SecurityDefinition messages are often fragmented.
    Falls back to pattern matching for fragmented messages.
    """
    print(f"\nParsing instruments: {Path(pcap_path).name}")
    instruments = {}

    # Pattern for WDO futures: BVMF + exchange code + WDO symbol
    import re
    wdo_pattern = rb'BVMF[0-9A-Z]{3}\x00(WDO[FGHJKMNQUVXZ][0-9]{2})\x00'

    packet_count = 0
    for pkt in PcapReader(pcap_path):
        if IP not in pkt or UDP not in pkt:
            continue

        packet_count += 1
        payload = bytes(pkt[UDP].payload)

        # Try SBE decoding first
        header = find_sbe_header(payload)
        if header and header['template_id'] == 12:  # SecurityDefinition
            msg_data = payload[header['offset']:]
            try:
                decoded = schema.decode(msg_data)
                if 'SecurityID' in decoded.value:
                    sec_id = decoded.value['SecurityID']
                    symbol = decoded.value.get('Symbol', '')
                    if isinstance(symbol, bytes):
                        symbol = symbol.decode('ascii', errors='ignore').strip('\x00')
                    if symbol.startswith('WDO') and len(symbol) == 6:
                        instruments[sec_id] = Instrument(
                            security_id=sec_id,
                            symbol=symbol,
                            security_exchange='BVMF'
                        )
            except:
                pass

        # Fallback: pattern matching for fragmented messages
        for match in re.finditer(wdo_pattern, payload):
            symbol = match.group(1).decode('ascii')
            idx = match.start()
            if idx >= 8:
                sec_id = struct.unpack('<Q', payload[idx-8:idx])[0]
                if sec_id > 0 and sec_id not in instruments:
                    instruments[sec_id] = Instrument(
                        security_id=sec_id,
                        symbol=symbol,
                        security_exchange='BVMF'
                    )

    print(f"  Packets processed: {packet_count}")
    print(f"  WDO instruments found: {len(instruments)}")
    for sec_id, inst in sorted(instruments.items(), key=lambda x: x[1].symbol):
        print(f"    {inst.symbol}: {sec_id}")

    return instruments


def parse_snapshot_sbe(pcap_path: str, schema: sbe.Schema,
                       instruments: Dict[int, Instrument]) -> List[MDEntry]:
    """Parse snapshot data using SBE decoder."""
    print(f"\nParsing snapshot: {Path(pcap_path).name}")

    entries = []
    template_stats = defaultdict(int)
    security_ids = set(instruments.keys())
    id_bytes = {sec_id: struct.pack('<Q', sec_id) for sec_id in security_ids}

    packet_count = 0
    for pkt in PcapReader(pcap_path):
        if IP not in pkt or UDP not in pkt:
            continue

        packet_count += 1
        payload = bytes(pkt[UDP].payload)
        timestamp_ns = extract_timestamp(payload)

        header = find_sbe_header(payload)
        if not header:
            continue

        template_id = header['template_id']
        template_stats[template_id] += 1

        # Try to decode and extract prices
        msg_data = payload[header['offset']:]
        try:
            decoded = schema.decode(msg_data)
            values = decoded.value

            # Get SecurityID from message
            sec_id = values.get('SecurityID')
            if sec_id and sec_id in instruments:
                symbol = instruments[sec_id].symbol

                # Extract price fields based on message type
                price = None
                size = 0
                entry_type = 'SNAPSHOT'

                # Price field mappings for different message types
                if 'mDEntryPx' in values:
                    px = values['mDEntryPx']
                    if isinstance(px, dict) and 'mantissa' in px:
                        price = px['mantissa'] / 1e8  # Price9 format
                    elif isinstance(px, (int, float)):
                        price = px / 100

                if 'lastPx' in values:
                    px = values['lastPx']
                    if isinstance(px, dict) and 'mantissa' in px:
                        price = px['mantissa'] / 1e8

                if 'mDEntrySize' in values:
                    size = values['mDEntrySize'] or 0

                if 'mDEntryType' in values:
                    et = values['mDEntryType']
                    if et == b'0' or et == 'BID':
                        entry_type = 'BID'
                    elif et == b'1' or et == 'OFFER':
                        entry_type = 'OFFER'
                    elif et == b'2' or et == 'TRADE':
                        entry_type = 'TRADE'

                if price and 5000 < price < 7000:
                    entries.append(MDEntry(
                        timestamp_ns=timestamp_ns,
                        security_id=sec_id,
                        symbol=symbol,
                        entry_type=entry_type,
                        price=price,
                        size=size,
                        source='SNAPSHOT'
                    ))
        except:
            pass

        # Fallback: direct binary search for prices
        for sec_id, pattern in id_bytes.items():
            idx = payload.find(pattern)
            if idx < 0:
                continue

            # Look for price after SecurityID
            for offset in [8, 12, 16, 20, 24, 28, 32, 36, 40]:
                if idx + offset + 4 > len(payload):
                    break

                val = struct.unpack('<I', payload[idx + offset:idx + offset + 4])[0]
                price = val / 100.0

                if 5000 < price < 7000:
                    entries.append(MDEntry(
                        timestamp_ns=timestamp_ns,
                        security_id=sec_id,
                        symbol=instruments[sec_id].symbol,
                        entry_type='SNAPSHOT',
                        price=price,
                        size=0,
                        source='SNAPSHOT'
                    ))
                    break

    print(f"  Packets: {packet_count}")
    print(f"  Entries extracted: {len(entries)}")
    print(f"  Template distribution: {dict(sorted(template_stats.items()))}")

    return entries


def parse_incremental_sbe(pcap_path: str, schema: sbe.Schema,
                          instruments: Dict[int, Instrument],
                          max_packets: int = 500000) -> tuple:
    """
    Parse incremental feed using SBE decoder.

    Reconstructs order book from Order_MBO_50 and DeleteOrder_MBO_51 messages.
    Trades are NOT extracted per task requirements.

    Returns:
        Tuple of (order_entries, tob_snapshots)
    """
    print(f"\nParsing incremental (reconstructing order book): {Path(pcap_path).name}")

    entries = []
    template_stats = defaultdict(int)
    security_ids = set(instruments.keys())
    id_bytes = {sec_id: struct.pack('<Q', sec_id) for sec_id in security_ids}

    # Order book manager for reconstruction
    ob_manager = OrderBookManager()

    # Counter for synthetic order IDs (for fallback parsing)
    next_order_id = 1

    packet_count = 0
    for pkt in PcapReader(pcap_path):
        if IP not in pkt or UDP not in pkt:
            continue

        packet_count += 1
        if packet_count > max_packets:
            break

        if packet_count % 100000 == 0:
            tob_count = len(ob_manager.tob_history)
            print(f"  {packet_count:,} packets, {len(entries):,} orders, {tob_count:,} TOB updates...")

        payload = bytes(pkt[UDP].payload)
        timestamp_ns = extract_timestamp(payload)

        header = find_sbe_header(payload)
        if header:
            template_id = header['template_id']
            template_stats[template_id] += 1

            # Extract Order Book updates (Order_MBO_50, DeleteOrder_MBO_51)
            if template_id in (50, 51):
                msg_data = payload[header['offset']:]
                try:
                    decoded = schema.decode(msg_data)
                    values = decoded.value

                    sec_id = values.get('SecurityID') or values.get('securityID')
                    if sec_id and sec_id in instruments:
                        price = None
                        if 'mDEntryPx' in values:
                            px = values['mDEntryPx']
                            if isinstance(px, dict) and 'mantissa' in px:
                                price = px['mantissa'] / 1e8
                            elif isinstance(px, (int, float)):
                                price = px / 100

                        # Determine side (BID or OFFER)
                        side = 'BID'
                        if 'mDEntryType' in values:
                            et = values['mDEntryType']
                            if et == b'1' or et == 'OFFER' or et == 1:
                                side = 'OFFER'

                        # Get order ID and size
                        order_id = values.get('OrderID', values.get('orderID', next_order_id))
                        next_order_id += 1
                        size = values.get('mDEntrySize', 0) or 0

                        # Determine action
                        action = 'NEW'
                        if template_id == 51:  # DeleteOrder
                            action = 'DELETE'
                        elif values.get('mDUpdateAction') == 'CHANGE':
                            action = 'CHANGE'

                        if price and 5000 < price < 7000:
                            # Add to raw entries
                            entries.append(MDEntry(
                                timestamp_ns=timestamp_ns,
                                security_id=sec_id,
                                symbol=instruments[sec_id].symbol,
                                entry_type=side,
                                price=price,
                                size=size,
                                source='INCREMENTAL'
                            ))

                            # Update order book
                            ob_manager.process_order(
                                security_id=sec_id,
                                symbol=instruments[sec_id].symbol,
                                order_id=order_id,
                                action=action,
                                side=side,
                                price=price,
                                size=size,
                                timestamp_ns=timestamp_ns
                            )
                except:
                    pass

        # Fallback: binary search for SecurityID and prices
        for sec_id, pattern in id_bytes.items():
            idx = payload.find(pattern)
            if idx < 0:
                continue

            for offset in [8, 12, 16, 20, 24, 28, 32]:
                if idx + offset + 4 > len(payload):
                    break

                val = struct.unpack('<I', payload[idx + offset:idx + offset + 4])[0]
                price = val / 100.0

                if 5000 < price < 7000:
                    # Add to raw entries
                    entries.append(MDEntry(
                        timestamp_ns=timestamp_ns,
                        security_id=sec_id,
                        symbol=instruments[sec_id].symbol,
                        entry_type='ORDER',
                        price=price,
                        size=0,
                        source='INCREMENTAL'
                    ))

                    # Update order book (assume BID for fallback)
                    ob_manager.process_order(
                        security_id=sec_id,
                        symbol=instruments[sec_id].symbol,
                        order_id=next_order_id,
                        action='NEW',
                        side='BID',
                        price=price,
                        size=1,
                        timestamp_ns=timestamp_ns
                    )
                    next_order_id += 1
                    break

    print(f"  Packets: {packet_count:,}")
    print(f"  Order entries: {len(entries):,}")
    print(f"  TOB updates: {len(ob_manager.tob_history):,}")
    print(f"  Template distribution: {dict(sorted(template_stats.items()))}")

    # Print order book summary
    print(f"\n  Order book summary:")
    for sec_id, book in ob_manager.books.items():
        tob = book.get_top_of_book()
        if tob.best_bid_price or tob.best_ask_price:
            spread_str = f"{tob.spread:.2f}" if tob.spread is not None else "N/A"
            print(f"    {book.symbol}: bid={tob.best_bid_price}, ask={tob.best_ask_price}, spread={spread_str}")

    return entries, ob_manager.get_all_tob()


def entries_to_dataframe(entries: List[MDEntry]) -> pd.DataFrame:
    """Convert entries to DataFrame."""
    if not entries:
        return pd.DataFrame()

    df = pd.DataFrame([
        {
            'timestamp_ns': e.timestamp_ns,
            'timestamp_s': e.timestamp_ns / 1e9,
            'security_id': e.security_id,
            'symbol': e.symbol,
            'entry_type': e.entry_type,
            'price': e.price,
            'size': e.size,
            'source': e.source
        }
        for e in entries
    ])

    # Remove duplicates and sort
    df = df.drop_duplicates(subset=['timestamp_ns', 'security_id', 'price'])
    df = df.sort_values('timestamp_ns').reset_index(drop=True)

    return df


def save_csv(df: pd.DataFrame, output_path: str):
    """Save DataFrame to CSV."""
    df.to_csv(output_path, index=False)
    print(f"  Saved: {output_path} ({len(df)} rows)")


def main():
    """Run the full parsing pipeline."""
    print("=" * 70)
    print("B3 PCAP Parser (SBE-based)")
    print("=" * 70)

    OUTPUT_DIR.mkdir(exist_ok=True)
    schema = load_schema()

    # Step 1: Parse instruments
    print("\n[1/4] Parsing instruments...")
    instruments = parse_instruments_sbe(
        str(DATA_DIR / '78_Instrument.pcap'),
        schema
    )

    # Filter to main futures (6-char symbols)
    wdo_futures = {k: v for k, v in instruments.items() if len(v.symbol) == 6}

    # Step 2: Parse snapshot
    print("\n[2/4] Parsing snapshot...")
    snapshot_entries = parse_snapshot_sbe(
        str(DATA_DIR / '78_Snapshot.pcap'),
        schema,
        wdo_futures
    )
    snapshot_df = entries_to_dataframe(snapshot_entries)
    save_csv(snapshot_df, str(OUTPUT_DIR / 'snapshot_sbe.csv'))

    # Step 3: Parse incremental and reconstruct order book
    print("\n[3/5] Parsing incremental feed and reconstructing order book...")
    incremental_entries, tob_snapshots = parse_incremental_sbe(
        str(DATA_DIR / '78_Incremental_feedA.pcap'),
        schema,
        wdo_futures,
        max_packets=500000
    )
    incremental_df = entries_to_dataframe(incremental_entries)
    save_csv(incremental_df, str(OUTPUT_DIR / 'updates_sbe.csv'))

    # Step 4: Save top-of-book snapshots
    print("\n[4/5] Saving top-of-book snapshots...")
    if tob_snapshots:
        tob_df = pd.DataFrame([
            {
                'timestamp_ns': t.timestamp_ns,
                'timestamp_s': t.timestamp_ns / 1e9,
                'security_id': t.security_id,
                'symbol': t.symbol,
                'best_bid': t.best_bid_price,
                'best_bid_size': t.best_bid_size,
                'best_ask': t.best_ask_price,
                'best_ask_size': t.best_ask_size,
                'spread': t.spread,
                'mid_price': t.mid_price
            }
            for t in tob_snapshots
        ])
        tob_df = tob_df.sort_values('timestamp_ns').reset_index(drop=True)
        save_csv(tob_df, str(OUTPUT_DIR / 'orderbook_tob_sbe.csv'))
    else:
        tob_df = pd.DataFrame()
        print("  No TOB snapshots generated")

    # Step 5: Extract WDO prices for visualization
    print("\n[5/5] Creating WDO price time series...")
    # Use mid_price from TOB if available, fallback to best_bid, then order prices
    if len(tob_df) > 0:
        wdo_prices = tob_df[tob_df['symbol'].str.startswith('WDO')].copy()
        # Use mid_price if available, otherwise use best_bid
        wdo_prices['price'] = wdo_prices['mid_price'].fillna(wdo_prices['best_bid'])
        wdo_prices = wdo_prices[['timestamp_ns', 'timestamp_s', 'security_id', 'symbol', 'price', 'spread']]
    else:
        wdo_prices = incremental_df[incremental_df['symbol'].str.startswith('WDO')].copy()
        wdo_prices = wdo_prices[['timestamp_ns', 'timestamp_s', 'security_id', 'symbol', 'price']]

    if len(wdo_prices) > 0:
        # Filter out rows with no price
        wdo_prices = wdo_prices[wdo_prices['price'].notna()]
        save_csv(wdo_prices, str(OUTPUT_DIR / 'wdo_prices_sbe.csv'))

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    print(f"\nInstruments: {len(wdo_futures)}")
    for sec_id, inst in sorted(wdo_futures.items(), key=lambda x: x[1].symbol):
        print(f"  {inst.symbol}: {sec_id}")

    print(f"\nSnapshot entries: {len(snapshot_df)}")
    if len(snapshot_df) > 0:
        for symbol in snapshot_df['symbol'].unique():
            count = len(snapshot_df[snapshot_df['symbol'] == symbol])
            print(f"  {symbol}: {count}")

    print(f"\nIncremental entries: {len(incremental_df)}")
    if len(incremental_df) > 0:
        for symbol in incremental_df['symbol'].unique():
            sym_df = incremental_df[incremental_df['symbol'] == symbol]
            print(f"  {symbol}: {len(sym_df)} entries, "
                  f"price range {sym_df['price'].min():.2f} - {sym_df['price'].max():.2f}")

    # TOB summary
    if len(tob_df) > 0:
        print(f"\nTop-of-book snapshots: {len(tob_df)}")
        for symbol in tob_df['symbol'].unique():
            sym_df = tob_df[tob_df['symbol'] == symbol]
            avg_spread = sym_df['spread'].mean()
            spread_str = f"{avg_spread:.2f}" if pd.notna(avg_spread) else "N/A"
            print(f"  {symbol}: {len(sym_df)} snapshots, avg spread={spread_str}")

    print("\n" + "=" * 70)
    print("Output files:")
    print("=" * 70)
    print(f"  {OUTPUT_DIR / 'snapshot_sbe.csv'}")
    print(f"  {OUTPUT_DIR / 'updates_sbe.csv'}")
    print(f"  {OUTPUT_DIR / 'orderbook_tob_sbe.csv'}")
    print(f"  {OUTPUT_DIR / 'wdo_prices_sbe.csv'}")


if __name__ == '__main__':
    main()
