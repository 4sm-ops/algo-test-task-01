#!/usr/bin/env python3
"""
Fast extraction of WDO prices from PCAP files.

Optimized for speed - processes full file and saves to CSV.
"""

import struct
import sys
from pathlib import Path

import pandas as pd
from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP


# Target instruments for calendar spread
INSTRUMENTS = {
    200001478879: 'WDOZ24',  # December 2024 (front month)
    2080363: 'WDOF25',        # January 2025 (next month)
}


def extract_prices(pcap_path: str, output_path: str):
    """Extract prices from PCAP and save to CSV."""
    print(f"Processing: {pcap_path}")

    # Pre-compute byte patterns
    patterns = {
        struct.pack('<Q', sec_id): (sec_id, symbol)
        for sec_id, symbol in INSTRUMENTS.items()
    }

    records = []
    packet_count = 0
    last_report = 0

    for pkt in PcapReader(pcap_path):
        if IP not in pkt or UDP not in pkt:
            continue

        packet_count += 1
        if packet_count - last_report >= 500000:
            print(f"  Processed {packet_count:,} packets, found {len(records):,} prices...")
            last_report = packet_count

        payload = bytes(pkt[UDP].payload)
        if len(payload) < 32:
            continue

        # Skip heartbeats
        msg_type = struct.unpack('<H', payload[0:2])[0]
        if msg_type == 334:
            continue

        # Get timestamp
        timestamp_ns = struct.unpack('<Q', payload[8:16])[0]

        # Search for instrument patterns
        for pattern, (sec_id, symbol) in patterns.items():
            idx = payload.find(pattern)
            if idx < 0:
                continue

            # Look for price after SecurityID
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

    # Save to CSV
    if records:
        df = pd.DataFrame(records)
        df['timestamp_s'] = df['timestamp_ns'] / 1e9
        df = df.sort_values('timestamp_ns')
        df.to_csv(output_path, index=False)
        print(f"  Saved to: {output_path}")

        # Summary
        print("\nSummary by symbol:")
        for symbol in df['symbol'].unique():
            sym_df = df[df['symbol'] == symbol]
            print(f"  {symbol}: {len(sym_df):,} records")
            print(f"    Price range: {sym_df['price'].min():.2f} - {sym_df['price'].max():.2f}")
            print(f"    Time range: {sym_df['timestamp_s'].min():.2f} - {sym_df['timestamp_s'].max():.2f}")
    else:
        print("  No prices found!")

    return records


if __name__ == '__main__':
    base_path = Path('/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/20241118')
    output_path = Path('/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/output')

    # Process incremental feed A
    extract_prices(
        str(base_path / '78_Incremental_feedA.pcap'),
        str(output_path / 'wdo_prices_incr.csv')
    )
