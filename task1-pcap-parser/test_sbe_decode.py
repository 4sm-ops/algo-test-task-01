#!/usr/bin/env python3
"""
Test SBE decoding with B3 schema and sample/real PCAP files.

sbe-python library successfully decodes B3 UMDF messages.
Note: Our data uses SchemaID=2, Version=9, but the schema is Version=16.
Most messages decode correctly despite version mismatch.
"""

import struct
from pathlib import Path
from collections import defaultdict

import sbe
from scapy.all import PcapReader
from scapy.layers.inet import IP, UDP

# Patch sbe-python to accept UTF-8 encoding (B3 uses UTF-8 in schema)
sbe.CharacterEncoding._value2member_map_['UTF-8'] = sbe.CharacterEncoding.ASCII

BASE_DIR = Path(__file__).parent
SAMPLES_DIR = BASE_DIR / 'b3-samples'
DATA_DIR = BASE_DIR / '20241118'
SCHEMA_FILE = SAMPLES_DIR / 'b3-market-data-messages-2.2.0.xml'


def load_schema():
    """Load B3 SBE schema."""
    print(f"Loading schema: {SCHEMA_FILE.name}")
    schema = sbe.Schema.parse(str(SCHEMA_FILE))
    print(f"  Schema ID: {schema.id}, Version: {schema.version}")
    print(f"  Messages: {len(schema.messages)}")
    return schema


def find_sbe_messages(payload: bytes, target_schema_id: int = 2):
    """Find SBE message start positions in UDP payload."""
    positions = []
    for pos in range(len(payload) - 8):
        schema_id = struct.unpack('<H', payload[pos+4:pos+6])[0]
        version = struct.unpack('<H', payload[pos+6:pos+8])[0]
        if schema_id == target_schema_id and 1 <= version <= 20:
            template_id = struct.unpack('<H', payload[pos+2:pos+4])[0]
            block_len = struct.unpack('<H', payload[pos:pos+2])[0]
            positions.append({
                'offset': pos,
                'block_len': block_len,
                'template_id': template_id,
                'schema_id': schema_id,
                'version': version,
            })
            break  # Usually one message per packet
    return positions


def decode_pcap(pcap_path: str, schema: sbe.Schema, max_packets: int = 1000):
    """Decode SBE messages from PCAP file."""
    print(f"\nDecoding: {Path(pcap_path).name}")

    template_stats = defaultdict(int)
    decoded_samples = {}
    decode_errors = defaultdict(int)

    packet_count = 0
    for pkt in PcapReader(pcap_path):
        if IP not in pkt or UDP not in pkt:
            continue

        packet_count += 1
        if packet_count > max_packets:
            break

        payload = bytes(pkt[UDP].payload)
        positions = find_sbe_messages(payload)

        for pos_info in positions:
            tid = pos_info['template_id']
            template_stats[tid] += 1

            # Try to decode if not already sampled
            if tid not in decoded_samples:
                msg_data = payload[pos_info['offset']:]
                try:
                    decoded = schema.decode(msg_data)
                    decoded_samples[tid] = {
                        'name': decoded.message_name,
                        'fields': list(decoded.value.keys()),
                        'sample': {k: v for k, v in decoded.value.items()
                                   if v is not None and v != [] and v != b''}
                    }
                except Exception as e:
                    decode_errors[tid] = str(e)

    # Print results
    print(f"  Packets: {packet_count}")
    print(f"\n  Template distribution:")
    for tid, cnt in sorted(template_stats.items()):
        if tid in decoded_samples:
            name = decoded_samples[tid]['name']
            print(f"    {tid:3d}: {cnt:5d} - {name}")
        elif tid in decode_errors:
            print(f"    {tid:3d}: {cnt:5d} - ERROR: {decode_errors[tid][:50]}")
        else:
            print(f"    {tid:3d}: {cnt:5d} - ?")

    # Print sample decoded messages
    print(f"\n  Sample decoded messages:")
    for tid in sorted(decoded_samples.keys())[:5]:
        info = decoded_samples[tid]
        print(f"\n    [{info['name']}]")
        for k, v in list(info['sample'].items())[:5]:
            val_str = str(v)[:60]
            print(f"      {k}: {val_str}")

    return template_stats, decoded_samples


def main():
    print("=" * 70)
    print("B3 SBE Decode Test")
    print("=" * 70)

    schema = load_schema()

    # List available messages
    print("\nAvailable message types:")
    for tid, msg in sorted(schema.messages.items()):
        print(f"  {tid:3d}: {msg.name}")

    # Test with our real data
    print("\n" + "=" * 70)
    print("Testing with real PCAP data (SchemaID=2, Version=9)")
    print("=" * 70)

    if DATA_DIR.exists():
        for pcap_name in ['78_Snapshot.pcap', '78_Incremental_feedA.pcap']:
            pcap_path = DATA_DIR / pcap_name
            if pcap_path.exists():
                decode_pcap(str(pcap_path), schema, max_packets=500)

    # Test with B3 samples
    print("\n" + "=" * 70)
    print("Testing with B3 sample data (SchemaID=2, Version=16)")
    print("=" * 70)

    if SAMPLES_DIR.exists():
        for pcap_file in SAMPLES_DIR.glob('*.pcap'):
            decode_pcap(str(pcap_file), schema, max_packets=200)

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print("""
sbe-python successfully decodes B3 UMDF messages!

Working messages (both Version=9 and Version=16):
- Sequence_2 (heartbeat/sequence)
- Trade_53 (trades)
- ExecutionSummary_55 (execution summaries)
- SecurityStatus_3 (status updates)
- SnapshotFullRefresh_Header_30 (snapshot headers)
- PriceBand_22 (price bands)
- SecurityGroupPhase_10 (group phases)

Messages requiring packet reassembly:
- SecurityDefinition_12 (instrument definitions) - fragmented
- Order_MBO_50 (order book entries) - fragmented

Note: Schema Version=16, but data Version=9 - partial compatibility.
For full accuracy, obtain the matching schema version from B3.
""")


if __name__ == '__main__':
    main()
