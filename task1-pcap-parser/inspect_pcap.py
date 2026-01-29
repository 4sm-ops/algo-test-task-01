#!/usr/bin/env python3
"""Inspect PCAP files to understand B3 UMDF/SBE message structure."""

import struct
from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP


def hex_dump(data: bytes, max_bytes: int = 64) -> str:
    """Pretty hex dump of bytes."""
    result = []
    for i in range(0, min(len(data), max_bytes), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        result.append(f'{i:04x}: {hex_part:<48} {ascii_part}')
    if len(data) > max_bytes:
        result.append(f'... ({len(data) - max_bytes} more bytes)')
    return '\n'.join(result)


def parse_sbe_header(data: bytes) -> dict:
    """Parse SBE message header."""
    if len(data) < 8:
        return None

    # SBE Message Header (8 bytes):
    # - BlockLength (2 bytes, LE)
    # - TemplateID (2 bytes, LE)
    # - SchemaID (2 bytes, LE)
    # - Version (2 bytes, LE)
    block_length, template_id, schema_id, version = struct.unpack('<HHHH', data[:8])

    return {
        'block_length': block_length,
        'template_id': template_id,
        'schema_id': schema_id,
        'version': version
    }


def inspect_pcap(filepath: str, max_packets: int = 10):
    """Inspect first N packets from PCAP file."""
    print(f"\n{'='*60}")
    print(f"Inspecting: {filepath}")
    print(f"{'='*60}")

    count = 0
    for packet in PcapReader(filepath):
        if count >= max_packets:
            break

        if IP not in packet or UDP not in packet:
            continue

        count += 1
        udp = packet[UDP]
        payload = bytes(udp.payload)

        print(f"\n--- Packet {count} ---")
        print(f"Timestamp: {float(packet.time):.6f}")
        print(f"Src: {packet[IP].src}:{udp.sport}")
        print(f"Dst: {packet[IP].dst}:{udp.dport}")
        print(f"UDP Payload length: {len(payload)} bytes")

        if len(payload) > 0:
            # Parse SBE header
            header = parse_sbe_header(payload)
            if header:
                print(f"SBE Header: {header}")

            print("Raw payload:")
            print(hex_dump(payload, max_bytes=128))


if __name__ == '__main__':
    import sys

    base_path = '/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/20241118'

    # Inspect different file types
    files = [
        f'{base_path}/78_Instrument.pcap',
        f'{base_path}/78_Snapshot.pcap',
        f'{base_path}/78_Incremental_feedA.pcap',
    ]

    for f in files:
        inspect_pcap(f, max_packets=3)
