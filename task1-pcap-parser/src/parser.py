#!/usr/bin/env python3
"""
B3 UMDF Binary PCAP Parser.

Parses PCAP files from B3 exchange and extracts market data.
Reconstructs order book from Order_MBO messages.
Prices are stored with 2 decimal places (multiplier 100).
"""

import struct
import re
import sys
from dataclasses import dataclass
from typing import Iterator, Dict, List, Tuple, Set, Optional
from pathlib import Path

# Add parent directory for order_book import
sys.path.insert(0, str(Path(__file__).parent.parent))

from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP

from order_book import OrderBookManager, TopOfBook


PRICE_MULTIPLIER = 100


@dataclass
class SecurityDefinition:
    """Instrument definition."""
    security_id: int
    symbol: str


@dataclass
class MDEntry:
    """Market data entry."""
    timestamp_ns: int
    security_id: int
    symbol: str
    entry_type: str  # 'SNAPSHOT', 'UPDATE'
    price: float
    size: int


def read_udp_payloads(pcap_path: str) -> Iterator[Tuple[float, bytes]]:
    """Read UDP payloads from PCAP file."""
    for packet in PcapReader(pcap_path):
        if IP in packet and UDP in packet:
            timestamp = float(packet.time)
            payload = bytes(packet[UDP].payload)
            if len(payload) >= 16:
                yield timestamp, payload


def parse_instruments(pcap_path: str) -> Dict[int, SecurityDefinition]:
    """
    Parse instrument definitions from Instrument.pcap.

    Returns dict mapping SecurityID -> SecurityDefinition for WDO futures only.
    """
    instruments = {}

    for _, payload in read_udp_payloads(pcap_path):
        # Find WDO futures pattern: BVMF marker followed by symbol
        # SecurityID is 8 bytes before BVMF
        for match in re.finditer(rb'BVMF[0-9A-Z]{3}\x00(WDO[FGHJKMNQUVXZ][0-9]{2})\x00', payload):
            symbol = match.group(1).decode('ascii')
            idx = match.start()

            if idx >= 8:
                sec_id = struct.unpack('<Q', payload[idx-8:idx])[0]
                # Use first occurrence of each symbol (main contract)
                if sec_id > 0:
                    # Check if we already have this symbol with lower ID
                    existing = [k for k, v in instruments.items() if v.symbol == symbol]
                    if not existing:
                        instruments[sec_id] = SecurityDefinition(
                            security_id=sec_id,
                            symbol=symbol
                        )

    return instruments


def parse_snapshot(pcap_path: str, instruments: Dict[int, SecurityDefinition],
                   price_range: Tuple[float, float] = (5000, 7000)) -> List[MDEntry]:
    """
    Extract prices from snapshot file.

    Searches for SecurityID patterns and extracts associated prices.
    """
    entries = []
    seen = set()

    # Pre-compute byte patterns for known SecurityIDs
    id_bytes = {sec_id: struct.pack('<Q', sec_id) for sec_id in instruments}

    for pkt_time, payload in read_udp_payloads(pcap_path):
        # Get timestamp from packet header
        timestamp_ns = struct.unpack('<Q', payload[8:16])[0]

        # Search for each known SecurityID
        for sec_id, pattern in id_bytes.items():
            pos = 0
            while True:
                idx = payload.find(pattern, pos)
                if idx < 0:
                    break
                pos = idx + 8

                # Look for price after SecurityID (typically at offset +8 to +48)
                for offset in [8, 12, 16, 20, 24, 28, 32, 36, 40]:
                    if idx + offset + 4 > len(payload):
                        break

                    val = struct.unpack('<I', payload[idx + offset:idx + offset + 4])[0]
                    price = val / PRICE_MULTIPLIER

                    if price_range[0] < price < price_range[1]:
                        key = (timestamp_ns, sec_id, price)
                        if key not in seen:
                            seen.add(key)
                            entries.append(MDEntry(
                                timestamp_ns=timestamp_ns,
                                security_id=sec_id,
                                symbol=instruments[sec_id].symbol,
                                entry_type='SNAPSHOT',
                                price=price,
                                size=0
                            ))
                        break

    return entries


def parse_incremental(pcap_path: str, instruments: Dict[int, SecurityDefinition],
                      price_range: Tuple[float, float] = (5000, 7000),
                      max_packets: int = None) -> Tuple[List[MDEntry], List[TopOfBook]]:
    """
    Extract prices from incremental feed and reconstruct order book.

    Returns:
        Tuple of (entries, tob_snapshots)
    """
    entries = []
    seen = set()
    packet_count = 0
    next_order_id = 1

    # Order book manager for reconstruction
    ob_manager = OrderBookManager()

    # Pre-compute byte patterns
    id_bytes = {sec_id: struct.pack('<Q', sec_id) for sec_id in instruments}

    for pkt_time, payload in read_udp_payloads(pcap_path):
        if max_packets and packet_count >= max_packets:
            break
        packet_count += 1

        if packet_count % 100000 == 0:
            print(f"  {packet_count:,} packets, {len(entries):,} orders...")

        # Skip heartbeat messages (msg_type 334)
        msg_type = struct.unpack('<H', payload[0:2])[0]
        if msg_type == 334:
            continue

        # Get timestamp
        timestamp_ns = struct.unpack('<Q', payload[8:16])[0]

        # Search for SecurityIDs and associated prices
        for sec_id, pattern in id_bytes.items():
            idx = payload.find(pattern)
            if idx < 0:
                continue

            # Try to determine side from mDEntryType byte
            # mDEntryType is typically 1 byte after price data
            # '0' = BID, '1' = OFFER
            side = 'BID'  # default
            for type_offset in [4, 5, 6, 7]:
                if idx + type_offset < len(payload):
                    type_byte = payload[idx + type_offset:idx + type_offset + 1]
                    if type_byte == b'1':
                        side = 'OFFER'
                        break

            # Look for price after SecurityID
            for offset in [8, 12, 16, 20, 24, 28, 32]:
                if idx + offset + 4 > len(payload):
                    break

                val = struct.unpack('<I', payload[idx + offset:idx + offset + 4])[0]
                price = val / PRICE_MULTIPLIER

                if price_range[0] < price < price_range[1]:
                    key = (timestamp_ns, sec_id, price)
                    if key not in seen:
                        seen.add(key)
                        entries.append(MDEntry(
                            timestamp_ns=timestamp_ns,
                            security_id=sec_id,
                            symbol=instruments[sec_id].symbol,
                            entry_type=side,
                            price=price,
                            size=1
                        ))

                        # Update order book
                        ob_manager.process_order(
                            security_id=sec_id,
                            symbol=instruments[sec_id].symbol,
                            order_id=next_order_id,
                            action='NEW',
                            side=side,
                            price=price,
                            size=1,
                            timestamp_ns=timestamp_ns
                        )
                        next_order_id += 1
                    break

    print(f"  Total: {packet_count:,} packets, {len(entries):,} orders, "
          f"{len(ob_manager.tob_history):,} TOB updates")

    return entries, ob_manager.get_all_tob()


def entries_to_csv(entries: List[MDEntry], output_path: str):
    """Write entries to CSV file."""
    import pandas as pd

    if not entries:
        print(f"No entries to write to {output_path}")
        return

    df = pd.DataFrame([
        {
            'timestamp_ns': e.timestamp_ns,
            'timestamp_s': e.timestamp_ns / 1e9,
            'security_id': e.security_id,
            'symbol': e.symbol,
            'entry_type': e.entry_type,
            'price': e.price,
            'size': e.size
        }
        for e in entries
    ])

    df = df.sort_values('timestamp_ns')
    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df)} rows to {output_path}")


def tob_to_csv(tob_list: List[TopOfBook], output_path: str):
    """Write top-of-book snapshots to CSV file."""
    import pandas as pd

    if not tob_list:
        print(f"No TOB snapshots to write to {output_path}")
        return

    df = pd.DataFrame([
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
        for t in tob_list
    ])

    df = df.sort_values('timestamp_ns').reset_index(drop=True)
    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df)} TOB snapshots to {output_path}")


if __name__ == '__main__':
    import pandas as pd

    base_path = Path(__file__).parent.parent / '20241118'
    output_path = Path(__file__).parent.parent / 'output'
    output_path.mkdir(exist_ok=True)

    print("=" * 60)
    print("B3 PCAP Parser (with Order Book Reconstruction)")
    print("=" * 60)

    # Parse instruments
    print("\n1. Parsing instruments...")
    instruments = parse_instruments(str(base_path / '78_Instrument.pcap'))

    # Filter to main futures (6-char symbols like WDOZ24, WDOF25)
    wdo_futures = {k: v for k, v in instruments.items() if len(v.symbol) == 6}
    print(f"   Found {len(wdo_futures)} WDO futures:")
    for sec_id, inst in sorted(wdo_futures.items(), key=lambda x: x[1].symbol):
        print(f"     {inst.symbol}: {sec_id}")

    # Parse snapshot
    print("\n2. Parsing snapshot...")
    snapshot_entries = parse_snapshot(
        str(base_path / '78_Snapshot.pcap'),
        wdo_futures
    )
    print(f"   Found {len(snapshot_entries)} snapshot entries")

    # Save snapshot CSV
    entries_to_csv(snapshot_entries, str(output_path / 'snapshot.csv'))

    # Parse incremental with order book reconstruction
    print("\n3. Parsing incremental feed (first 100k packets)...")
    update_entries, tob_snapshots = parse_incremental(
        str(base_path / '78_Incremental_feedA.pcap'),
        wdo_futures,
        max_packets=100000
    )

    # Save updates CSV
    entries_to_csv(update_entries, str(output_path / 'updates.csv'))

    # Save TOB snapshots
    print("\n4. Saving top-of-book snapshots...")
    tob_to_csv(tob_snapshots, str(output_path / 'orderbook_tob.csv'))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    if snapshot_entries:
        df = pd.DataFrame([{'symbol': e.symbol, 'price': e.price} for e in snapshot_entries])
        print("\nSnapshot prices by symbol:")
        for symbol in df['symbol'].unique():
            prices = df[df['symbol'] == symbol]['price']
            print(f"  {symbol}: min={prices.min():.2f}, max={prices.max():.2f}, count={len(prices)}")

    if update_entries:
        df = pd.DataFrame([{'symbol': e.symbol, 'price': e.price} for e in update_entries])
        print("\nUpdate prices by symbol:")
        for symbol in df['symbol'].unique():
            prices = df[df['symbol'] == symbol]['price']
            print(f"  {symbol}: min={prices.min():.2f}, max={prices.max():.2f}, count={len(prices)}")

    if tob_snapshots:
        print(f"\nTop-of-book snapshots: {len(tob_snapshots)}")
        tob_df = pd.DataFrame([{'symbol': t.symbol} for t in tob_snapshots])
        for symbol in tob_df['symbol'].unique():
            count = len(tob_df[tob_df['symbol'] == symbol])
            print(f"  {symbol}: {count} snapshots")
