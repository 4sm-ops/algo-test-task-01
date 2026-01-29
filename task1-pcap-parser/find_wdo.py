#!/usr/bin/env python3
"""Find WDO instruments in Instrument.pcap."""

import struct
import re
from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP


def extract_symbols(payload: bytes) -> list:
    """Extract ASCII symbols from payload."""
    # Look for WDO pattern in bytes
    symbols = []
    # B3 symbols are typically 8-20 bytes, null-padded
    pattern = rb'WDO[A-Z0-9]{1,15}'
    matches = re.findall(pattern, payload)
    for m in matches:
        symbols.append(m.decode('ascii'))
    return list(set(symbols))


def find_wdo_instruments(filepath: str):
    """Find all WDO instruments in Instrument.pcap."""
    print(f"Scanning {filepath} for WDO instruments...")

    all_symbols = set()
    packet_count = 0

    for packet in PcapReader(filepath):
        if IP not in packet or UDP not in packet:
            continue

        payload = bytes(packet[UDP].payload)
        symbols = extract_symbols(payload)
        all_symbols.update(symbols)
        packet_count += 1

    print(f"Scanned {packet_count} packets")
    print(f"\nFound {len(all_symbols)} unique WDO symbols:")

    # Group by contract type
    futures = []
    options = []

    for sym in sorted(all_symbols):
        if 'C' in sym or 'P' in sym:  # Call/Put options
            options.append(sym)
        else:
            futures.append(sym)

    print("\nWDO Futures:")
    for s in sorted(futures):
        print(f"  {s}")

    print(f"\nWDO Options ({len(options)} total):")
    # Just show a sample
    for s in sorted(options)[:10]:
        print(f"  {s}")
    if len(options) > 10:
        print(f"  ... and {len(options) - 10} more")


if __name__ == '__main__':
    base_path = '/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/20241118'
    find_wdo_instruments(f'{base_path}/78_Instrument.pcap')
    print("\n" + "="*60)
    find_wdo_instruments(f'{base_path}/88_Instrument.pcap')
