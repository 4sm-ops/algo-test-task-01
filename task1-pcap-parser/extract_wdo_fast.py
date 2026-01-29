#!/usr/bin/env python3
"""
Fast extraction of WDO prices - limited to first N packets.
"""

import struct
from pathlib import Path

import pandas as pd
from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP


# Target instruments
INSTRUMENTS = {
    200001478879: 'WDOZ24',
    2080363: 'WDOF25',
}

MAX_PACKETS = 500000  # Limit for speed


def extract_prices(pcap_path: str, output_path: str):
    """Extract prices from PCAP."""
    print(f"Processing: {pcap_path} (max {MAX_PACKETS:,} packets)")

    patterns = {
        struct.pack('<Q', sec_id): (sec_id, symbol)
        for sec_id, symbol in INSTRUMENTS.items()
    }

    records = []
    packet_count = 0

    for pkt in PcapReader(pcap_path):
        if IP not in pkt or UDP not in pkt:
            continue

        packet_count += 1
        if packet_count >= MAX_PACKETS:
            break

        if packet_count % 100000 == 0:
            print(f"  {packet_count:,} packets, {len(records):,} prices...")

        payload = bytes(pkt[UDP].payload)
        if len(payload) < 32:
            continue

        msg_type = struct.unpack('<H', payload[0:2])[0]
        if msg_type == 334:
            continue

        timestamp_ns = struct.unpack('<Q', payload[8:16])[0]

        for pattern, (sec_id, symbol) in patterns.items():
            idx = payload.find(pattern)
            if idx < 0:
                continue

            for offset in [8, 12, 16, 20, 24, 28, 32]:
                pos = idx + offset
                if pos + 4 > len(payload):
                    break

                val = struct.unpack('<I', payload[pos:pos+4])[0]
                price = val / 100.0

                if 5000 < price < 7000:
                    records.append({
                        'timestamp_ns': timestamp_ns,
                        'security_id': sec_id,
                        'symbol': symbol,
                        'price': price
                    })
                    break

    print(f"  Total: {packet_count:,} packets, {len(records):,} prices")

    if records:
        df = pd.DataFrame(records)
        df['timestamp_s'] = df['timestamp_ns'] / 1e9
        df = df.sort_values('timestamp_ns')
        df.to_csv(output_path, index=False)
        print(f"  Saved: {output_path}")

        for symbol in df['symbol'].unique():
            sym_df = df[df['symbol'] == symbol]
            print(f"  {symbol}: {len(sym_df):,} records, {sym_df['price'].min():.2f} - {sym_df['price'].max():.2f}")

    return records


if __name__ == '__main__':
    base_path = Path('/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/20241118')
    output_path = Path('/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/output')

    extract_prices(
        str(base_path / '78_Incremental_feedA.pcap'),
        str(output_path / 'wdo_prices_incr.csv')
    )
