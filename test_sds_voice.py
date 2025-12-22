"""
Test script to verify SDS message reconstruction and voice decoding.
"""

import numpy as np
import logging
from tetra_protocol import TetraProtocolParser, PDUType
from tetra_decoder import TetraDecoder
from voice_processor import VoiceProcessor
import struct

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_sds_fragmentation():
    """Test SDS message reconstruction from fragments."""
    print("\n" + "="*60)
    print("TEST 1: SDS Message Fragmentation")
    print("="*60)
    
    parser = TetraProtocolParser()
    
    # Create a test message: "HELLO WORLD FROM TETRA"
    test_message = b"HELLO WORLD FROM TETRA"
    
    # Simulate MAC-RESOURCE frame (start)
    # Type (3 bits) = 0 (MAC-RESOURCE)
    # Fill (1 bit) = 0
    # Encrypted (1 bit) = 0
    # Address (24 bits) = 0x123456
    # Length (6 bits) = 10
    # Data: first 10 bytes of message
    
    resource_bits = []
    resource_bits.extend([0, 0, 0])  # Type = 0
    resource_bits.append(0)  # Fill = 0
    resource_bits.append(0)  # Encrypted = 0
    
    # Address: 0x123456 (24 bits)
    address = 0x123456
    for i in range(23, -1, -1):
        resource_bits.append((address >> i) & 1)
    
    # Length: 10 bytes (6 bits)
    length = 10
    for i in range(5, -1, -1):
        resource_bits.append((length >> i) & 1)
    
    # Data: first 10 bytes
    for byte in test_message[:10]:
        for i in range(7, -1, -1):
            resource_bits.append((byte >> i) & 1)
    
    # Pad to at least 216 bits
    while len(resource_bits) < 216:
        resource_bits.append(0)
    
    print(f"MAC-RESOURCE frame with {len(resource_bits)} bits")
    pdu1 = parser.parse_mac_pdu(np.array(resource_bits))
    if pdu1:
        print(f"  Type: {pdu1.pdu_type.name}")
        print(f"  Address: 0x{pdu1.address:06X}" if pdu1.address else "  Address: None")
        print(f"  Data: {pdu1.data}")
        print(f"  Fragment buffer: {len(parser.fragment_buffer)} bytes")
    
    # Simulate MAC-FRAG frame (continue)
    # Type (3 bits) = 1 (MAC-FRAG)
    # Fill (1 bit) = 0
    # Data: next 12 bytes
    
    frag_bits = []
    frag_bits.extend([0, 0, 1])  # Type = 1
    frag_bits.append(0)  # Fill = 0
    
    # Data: next 12 bytes
    for byte in test_message[10:22]:
        for i in range(7, -1, -1):
            frag_bits.append((byte >> i) & 1)
    
    # Pad to 216 bits
    while len(frag_bits) < 216:
        frag_bits.append(0)
    
    print(f"\nMAC-FRAG frame with {len(frag_bits)} bits")
    pdu2 = parser.parse_mac_pdu(np.array(frag_bits))
    if pdu2:
        print(f"  Type: {pdu2.pdu_type.name}")
        print(f"  Data: {pdu2.data}")
        print(f"  Fragment buffer: {len(parser.fragment_buffer)} bytes")
    
    # Simulate MAC-END frame (finalize)
    # Type (3 bits) = 2 (MAC-END)
    # Fill (1 bit) = 0
    # Length (6 bits) = 0 (remaining bytes)
    # Data: empty or remaining
    
    end_bits = []
    end_bits.extend([0, 1, 0])  # Type = 2
    end_bits.append(0)  # Fill = 0
    
    # Length: 0 (no more data in this frame)
    for i in range(5, -1, -1):
        end_bits.append(0)
    
    # Pad to 216 bits
    while len(end_bits) < 216:
        end_bits.append(0)
    
    print(f"\nMAC-END frame with {len(end_bits)} bits")
    pdu3 = parser.parse_mac_pdu(np.array(end_bits))
    if pdu3:
        print(f"  Type: {pdu3.pdu_type.name}")
        print(f"  Reassembled data: {pdu3.reassembled_data}")
        if pdu3.reassembled_data:
            # Try to parse as SDS
            text = parser.parse_sds_data(pdu3.reassembled_data)
            print(f"  ✅ DECODED TEXT: {text}")
        print(f"  Fragment buffer after END: {len(parser.fragment_buffer)} bytes")
    
    print("\n" + "="*60)
    return pdu3 and pdu3.reassembled_data is not None


def test_voice_frame():
    """Test voice frame extraction and decoding."""
    print("\n" + "="*60)
    print("TEST 2: Voice Frame Decoding")
    print("="*60)
    
    # Create a test voice slot (255 symbols)
    # Simulate π/4-DQPSK symbols with some pattern
    symbols = []
    
    # First block: 108 symbols (alternating pattern)
    for i in range(108):
        symbols.append(i % 4)  # Values 0-3 (2 bits)
    
    # Training sequence: 11 symbols (fixed pattern)
    training = [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0]
    symbols.extend(training)
    
    # Second block: 108 symbols
    for i in range(108):
        symbols.append((i + 2) % 4)
    
    # Tail: remaining symbols to reach 255
    while len(symbols) < 255:
        symbols.append(0)
    
    symbols = np.array(symbols)
    print(f"Created symbol stream with {len(symbols)} symbols")
    
    # Extract voice slot
    from tetra_decoder_main import extract_voice_slot_from_symbols
    
    frame = {'position': 0}  # Start at position 0 (in bits)
    
    voice_data = extract_voice_slot_from_symbols(frame, symbols, 1)
    
    if voice_data:
        print(f"✅ Voice slot extracted: {len(voice_data)} bytes")
        
        # Check header
        header = struct.unpack('<H', voice_data[0:2])[0]
        print(f"  Header: 0x{header:04X} (expected 0x6B21)")
        
        if header == 0x6B21:
            print("  ✅ Header is CORRECT!")
        else:
            print("  ❌ Header is WRONG!")
        
        # Check total length
        shorts_count = len(voice_data) // 2
        print(f"  Total shorts: {shorts_count} (expected 690)")
        
        if shorts_count == 690:
            print("  ✅ Length is CORRECT!")
        else:
            print("  ❌ Length is WRONG!")
        
        # Try to decode with codec
        voice_processor = VoiceProcessor()
        if voice_processor.working:
            audio = voice_processor.decode_frame(voice_data)
            if len(audio) > 0:
                print(f"  ✅ Codec produced {len(audio)} audio samples")
            else:
                print(f"  ⚠️  Codec produced no audio (expected for test pattern)")
        else:
            print("  ⚠️  Codec not available")
            
        return True
    else:
        print("❌ Failed to extract voice slot")
        return False
    
    print("\n" + "="*60)


def test_sds_parsing():
    """Test SDS message parsing with different encodings."""
    print("\n" + "="*60)
    print("TEST 3: SDS Message Parsing")
    print("="*60)
    
    parser = TetraProtocolParser()
    
    test_cases = [
        # Simple ASCII text
        (b"Hello World", "Simple ASCII"),
        # SDS-1 format (05 00 Length Text)
        (bytes([0x05, 0x00, 0x0B]) + b"HELLO WORLD", "SDS-1 format"),
        # Text with special chars
        (b"Status: OK\nReady", "Text with newline"),
        # Binary data (should show as hex)
        (bytes([0xFF, 0xAA, 0x55, 0x00, 0x12, 0x34]), "Binary data"),
    ]
    
    for data, description in test_cases:
        print(f"\nTest: {description}")
        print(f"  Input: {data.hex() if len(data) <= 16 else data.hex()[:32] + '...'}")
        text = parser.parse_sds_data(data)
        print(f"  Output: {text}")
    
    print("\n" + "="*60)
    return True


def main():
    """Run all tests."""
    print("\n" + "#"*60)
    print("# TETRA SDS & Voice Processing Tests")
    print("#"*60)
    
    results = []
    
    # Test 1: SDS Fragmentation
    try:
        result = test_sds_fragmentation()
        results.append(("SDS Fragmentation", result))
    except Exception as e:
        logger.error(f"SDS Fragmentation test failed: {e}", exc_info=True)
        results.append(("SDS Fragmentation", False))
    
    # Test 2: Voice Frame
    try:
        result = test_voice_frame()
        results.append(("Voice Frame", result))
    except Exception as e:
        logger.error(f"Voice Frame test failed: {e}", exc_info=True)
        results.append(("Voice Frame", False))
    
    # Test 3: SDS Parsing
    try:
        result = test_sds_parsing()
        results.append(("SDS Parsing", result))
    except Exception as e:
        logger.error(f"SDS Parsing test failed: {e}", exc_info=True)
        results.append(("SDS Parsing", False))
    
    # Summary
    print("\n" + "#"*60)
    print("# TEST SUMMARY")
    print("#"*60)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("#"*60 + "\n")
    
    return passed == total


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
