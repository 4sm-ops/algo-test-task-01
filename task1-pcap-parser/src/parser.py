#!/usr/bin/env python3
"""
B3 UMDF Binary PCAP Parser.

Parses PCAP files from B3 exchange and extracts market data.
Prices are stored with 2 decimal places (multiplier 100).
"""

import struct
import re
from dataclasses import dataclass
from typing import Iterator, Dict, List, Tuple, Set
from pathlib import Path

from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP


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
                      max_packets: int = None) -> List[MDEntry]:
    """
    Extract prices from incremental feed.
    """
    entries = []
    seen = set()
    packet_count = 0

    # Pre-compute byte patterns
    id_bytes = {sec_id: struct.pack('<Q', sec_id) for sec_id in instruments}

    for pkt_time, payload in read_udp_payloads(pcap_path):
        if max_packets and packet_count >= max_packets:
            break
        packet_count += 1

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
                            entry_type='UPDATE',
                            price=price,
                            size=0
                        ))
                    break

    return entries


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


if __name__ == '__main__':
    import pandas as pd

    base_path = Path('/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/20241118')
    output_path = Path('/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/output')

    print("=" * 60)
    print("B3 PCAP Parser")
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

    # Parse incremental (limited for speed)
    print("\n3. Parsing incremental feed (first 100k packets)...")
    update_entries = parse_incremental(
        str(base_path / '78_Incremental_feedA.pcap'),
        wdo_futures,
        max_packets=100000
    )
    print(f"   Found {len(update_entries)} update entries")

    # Save updates CSV
    entries_to_csv(update_entries, str(output_path / 'updates.csv'))

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
