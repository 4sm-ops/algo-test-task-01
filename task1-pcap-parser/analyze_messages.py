#!/usr/bin/env python3
"""Analyze B3 UMDF message structure in detail."""

import struct
from collections import Counter
from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP


def analyze_incremental(filepath: str, max_packets: int = 1000):
    """Analyze message types in incremental feed."""
    print(f"\n{'='*60}")
    print(f"Analyzing: {filepath}")
    print(f"{'='*60}")

    template_ids = Counter()
    msg_sizes = []
    sample_payloads = {}

    count = 0
    for packet in PcapReader(filepath):
        if count >= max_packets:
            break

        if IP not in packet or UDP not in packet:
            continue

        payload = bytes(packet[UDP].payload)
        if len(payload) < 8:
            continue

        count += 1

        # Parse packet header (different from SBE message header)
        # B3 UMDF packet structure:
        # Bytes 0-1: Message type/flags
        # Bytes 2-3: Template ID (little-endian)
        # Bytes 4-7: Sequence number

        msg_type = struct.unpack('<H', payload[0:2])[0]
        template_id = struct.unpack('<H', payload[2:4])[0]
        seq_num = struct.unpack('<I', payload[4:8])[0]

        template_ids[(msg_type, template_id)] += 1
        msg_sizes.append(len(payload))

        # Save sample of each type
        key = (msg_type, template_id)
        if key not in sample_payloads:
            sample_payloads[key] = payload

    print(f"Analyzed {count} packets")
    print(f"Message sizes: min={min(msg_sizes)}, max={max(msg_sizes)}, avg={sum(msg_sizes)/len(msg_sizes):.0f}")

    print("\nMessage types (msg_type, template_id) -> count:")
    for (msg_type, template_id), cnt in template_ids.most_common():
        print(f"  ({msg_type:5d}, {template_id:5d}) -> {cnt}")

        # Show sample payload for this type
        payload = sample_payloads[(msg_type, template_id)]
        print(f"    Sample: {payload[:48].hex()}")


def analyze_snapshot_detail(filepath: str, max_packets: int = 100):
    """Analyze snapshot message structure."""
    print(f"\n{'='*60}")
    print(f"Snapshot detail: {filepath}")
    print(f"{'='*60}")

    for i, packet in enumerate(PcapReader(filepath)):
        if i >= max_packets:
            break

        if IP not in packet or UDP not in packet:
            continue

        payload = bytes(packet[UDP].payload)
        if len(payload) < 20:
            continue

        # Header analysis
        msg_type = struct.unpack('<H', payload[0:2])[0]
        template_id = struct.unpack('<H', payload[2:4])[0]
        seq_num = struct.unpack('<I', payload[4:8])[0]

        # Timestamp at offset 8 (8 bytes, nanoseconds since epoch)
        timestamp_ns = struct.unpack('<Q', payload[8:16])[0]
        timestamp_s = timestamp_ns / 1e9

        # Try to find security ID and other fields
        print(f"\nPacket {i+1}:")
        print(f"  MsgType: {msg_type}, TemplateID: {template_id}, Seq: {seq_num}")
        print(f"  Timestamp: {timestamp_s:.6f}")
        print(f"  Payload ({len(payload)} bytes): {payload[:64].hex()}")

        if i >= 5:
            break


if __name__ == '__main__':
    base_path = '/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/20241118'

    # Analyze incremental feed
    analyze_incremental(f'{base_path}/78_Incremental_feedA.pcap', max_packets=5000)

    # Analyze snapshot detail
    analyze_snapshot_detail(f'{base_path}/78_Snapshot.pcap', max_packets=10)
