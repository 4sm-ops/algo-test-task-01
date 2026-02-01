#!/usr/bin/env python3
"""
B3 PCAP Parser - Main Entry Point

Parses B3 exchange PCAP files and generates:
1. snapshot.csv - Order book snapshots
2. updates.csv - Incremental updates (orders)
3. orderbook_tob.csv - Top-of-book from reconstructed order book
4. wdo_prices.html - Interactive price chart
5. wdo_spread.html - Calendar spread (4 types)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from parser import (
    parse_instruments, parse_snapshot, parse_incremental,
    entries_to_csv, tob_to_csv
)
from visualization import create_wdo_chart, create_calendar_spread_4types


def main():
    """Run the full parsing pipeline."""
    base_path = Path(__file__).parent / '20241118'
    output_path = Path(__file__).parent / 'output'
    output_path.mkdir(exist_ok=True)

    print("=" * 70)
    print("B3 PCAP Parser - WDO Futures Analysis")
    print("=" * 70)

    # Step 1: Parse instruments
    print("\n[1/5] Parsing instruments from 78_Instrument.pcap...")
    instruments = parse_instruments(str(base_path / '78_Instrument.pcap'))
    wdo_futures = {k: v for k, v in instruments.items() if len(v.symbol) == 6}
    print(f"      Found {len(wdo_futures)} WDO futures contracts")

    # Step 2: Parse snapshot
    print("\n[2/5] Parsing snapshot from 78_Snapshot.pcap...")
    snapshot_entries = parse_snapshot(str(base_path / '78_Snapshot.pcap'), wdo_futures)
    entries_to_csv(snapshot_entries, str(output_path / 'snapshot.csv'))

    # Step 3: Parse incremental updates with order book reconstruction
    print("\n[3/5] Parsing incremental feed and reconstructing order book...")
    update_entries, tob_snapshots = parse_incremental(
        str(base_path / '78_Incremental_feedA.pcap'),
        wdo_futures,
        max_packets=100000
    )
    entries_to_csv(update_entries, str(output_path / 'updates.csv'))

    # Step 4: Save top-of-book snapshots
    print("\n[4/5] Saving top-of-book snapshots...")
    tob_to_csv(tob_snapshots, str(output_path / 'orderbook_tob.csv'))

    # Step 5: Create visualizations
    print("\n[5/5] Creating visualizations...")
    tob_file = output_path / 'orderbook_tob.csv'
    if tob_file.exists():
        create_wdo_chart(str(tob_file), str(output_path / 'wdo_prices.html'))
    create_calendar_spread_4types(str(output_path / 'wdo_spread.html'))

    # Summary
    print("\n" + "=" * 70)
    print("Output Files")
    print("=" * 70)
    print(f"\nCSV files:")
    print(f"  - output/snapshot.csv       - Order book snapshots")
    print(f"  - output/updates.csv        - Incremental updates (orders)")
    print(f"  - output/orderbook_tob.csv  - Top-of-book from order book")
    print(f"\nHTML charts (open in browser):")
    print(f"  - output/wdo_prices.html    - WDO price chart")
    print(f"  - output/wdo_spread.html    - Calendar spread (4 types)")

    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == '__main__':
    main()
