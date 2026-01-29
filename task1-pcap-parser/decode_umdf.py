#!/usr/bin/env python3
"""
Decode B3 UMDF Binary messages.

Based on B3 Binary UMDF Message Specification.
Reference: https://www.b3.com.br/en_us/solutions/platforms/puma-trading-system/for-developers-and-vendors/binary-umdf/
"""

import struct
from dataclasses import dataclass
from typing import Optional, List, Dict
from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP


# B3 UMDF Template IDs
TEMPLATE_SEQUENCE = 1  # Sequence message
TEMPLATE_SECURITY_STATUS = 3  # Security status
TEMPLATE_SECURITY_DEFINITION = 4  # Security definition (instruments)
TEMPLATE_NEWS = 5  # News
TEMPLATE_ORDER_MBO = 50  # Market by Order - single order update
TEMPLATE_DELETE_ORDER_MBO = 51  # Delete order
TEMPLATE_MASS_DELETE_ORDERS_MBO = 52  # Mass delete
TEMPLATE_TRADE_MBO = 54  # Trade
TEMPLATE_TRADE_BUST = 57  # Trade bust
TEMPLATE_SNAPSHOT_FULL_REFRESH_MBO_71 = 71  # Snapshot

# Message type constants
MSG_TYPE_INCREMENTAL = 0x4E  # 78
MSG_TYPE_HEARTBEAT = 0x14E  # 334


@dataclass
class PacketHeader:
    """UMDF Packet header."""
    msg_type: int  # 2 bytes
    template_id: int  # 2 bytes
    schema_id: int  # 4 bytes (includes sequence number info)
    timestamp_ns: int  # 8 bytes


@dataclass
class MDEntry:
    """Market data entry (bid/ask/trade)."""
    md_entry_type: str  # 'BID', 'ASK', 'TRADE'
    price: float
    size: int
    position: int
    order_id: Optional[int] = None
    update_action: Optional[str] = None  # 'NEW', 'CHANGE', 'DELETE'


def parse_packet_header(data: bytes) -> PacketHeader:
    """Parse UMDF packet header."""
    msg_type, template_id = struct.unpack('<HH', data[0:4])
    schema_id = struct.unpack('<I', data[4:8])[0]
    timestamp_ns = struct.unpack('<Q', data[8:16])[0]

    return PacketHeader(
        msg_type=msg_type,
        template_id=template_id,
        schema_id=schema_id,
        timestamp_ns=timestamp_ns
    )


def decode_price(raw: int, exponent: int = -2) -> float:
    """Decode B3 price (mantissa with implied exponent)."""
    return raw * (10 ** exponent)


def find_wdo_prices_in_snapshot(filepath: str):
    """Extract WDO prices from snapshot file."""
    print(f"\nExtracting prices from: {filepath}")

    # Known SecurityID for WDOZ24 and WDOF25 (need to find these first)
    # Let's search for them in the data

    for i, packet in enumerate(PcapReader(filepath)):
        if IP not in packet or UDP not in packet:
            continue

        payload = bytes(packet[UDP].payload)
        if len(payload) < 32:
            continue

        header = parse_packet_header(payload)

        # Template 9301 seems to be the actual template ID we see
        # Let's analyze the structure more

        # After header (16 bytes), we have:
        # - blockLength (2 bytes)
        # - more message content

        # Looking at hex: 2c 00 50 eb 20 00 0a 00 02 00 09 00
        # After timestamp at offset 16

        if i < 10:
            print(f"\nPacket {i+1}:")
            print(f"  Header: type={header.msg_type}, template={header.template_id}")
            print(f"  Timestamp: {header.timestamp_ns / 1e9:.6f}")

            # Analyze bytes after header
            rest = payload[16:]
            print(f"  After header ({len(rest)} bytes): {rest[:32].hex()}")

            # Try to find security ID pattern (looking for hex 0x17487868 = WDOF25 based on pattern)
            # SecurityID seems to be at a fixed offset

            if len(rest) >= 16:
                # Try different offsets
                for offset in [8, 12, 16, 20]:
                    if len(rest) >= offset + 8:
                        sec_id = struct.unpack('<Q', rest[offset:offset+8])[0]
                        print(f"    Offset {offset}: SecurityID candidate = {sec_id} (0x{sec_id:x})")


def find_incremental_with_prices(filepath: str, max_packets: int = 10000):
    """Find incremental messages that contain price updates."""
    print(f"\nSearching for price updates in: {filepath}")

    price_messages = []

    for i, packet in enumerate(PcapReader(filepath)):
        if i >= max_packets:
            break

        if IP not in packet or UDP not in packet:
            continue

        payload = bytes(packet[UDP].payload)
        if len(payload) < 40:  # Too small for price data
            continue

        header = parse_packet_header(payload)

        # Skip heartbeats (type 334)
        if header.msg_type == 334:
            continue

        # Messages with type 78 (0x4E) contain actual data
        # Template 365 seems to be used

        # Look for larger messages which likely have price data
        if len(payload) > 50:
            price_messages.append({
                'index': i,
                'size': len(payload),
                'template': header.template_id,
                'timestamp': header.timestamp_ns,
                'payload': payload
            })

    print(f"Found {len(price_messages)} potential price messages")

    # Show sample
    for msg in price_messages[:5]:
        print(f"\nPacket {msg['index']}:")
        print(f"  Size: {msg['size']}, Template: {msg['template']}")
        print(f"  Payload: {msg['payload'][:80].hex()}")

        # Try to decode
        payload = msg['payload']
        rest = payload[16:]  # Skip header

        # Look for price-like values (5 digits around 5000-6000 range for WDO)
        for offset in range(0, min(len(rest), 64), 4):
            val = struct.unpack('<I', rest[offset:offset+4])[0]
            if 400000 < val < 700000:  # Possible price * 100 range
                print(f"    Offset {offset+16}: possible price = {val/100:.2f}")


if __name__ == '__main__':
    base_path = '/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/20241118'

    find_wdo_prices_in_snapshot(f'{base_path}/78_Snapshot.pcap')
    find_incremental_with_prices(f'{base_path}/78_Incremental_feedA.pcap', max_packets=10000)
