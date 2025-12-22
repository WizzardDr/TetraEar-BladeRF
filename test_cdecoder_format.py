"""
Test script to verify cdecoder input format and test decoding.
Creates test frames in the correct format and tests cdecoder.
"""

import os
import struct
import subprocess
import numpy as np

def create_test_frame():
    """Create a test TETRA frame in the correct format for cdecoder."""
    # Create 690-short block structure
    block = [0] * 690
    
    # Header: 0x6B21 for speech frame
    block[0] = 0x6B21
    
    # Create 432 soft bits (test pattern: alternating high/low confidence)
    # Soft bits must be in range -127 to +127
    soft_bits = []
    for i in range(432):
        # Create a test pattern (alternating)
        if i % 2 == 0:
            soft_bits.append(127)  # High confidence 1
        else:
            soft_bits.append(-127)  # High confidence 0
    
    # Place 432 soft bits in correct positions according to Write_Tetra_File structure
    idx = 0
    # Block 1: positions 1-114 (114 bits)
    for i in range(1, 115):
        if idx < len(soft_bits):
            block[i] = soft_bits[idx] & 0x00FF  # Mask to 8-bit range
            idx += 1
    
    # Block 2: positions 116-229 (114 bits) 
    for i in range(116, 230):
        if idx < len(soft_bits):
            block[i] = soft_bits[idx] & 0x00FF
            idx += 1
    
    # Block 3: positions 231-344 (114 bits)
    for i in range(231, 345):
        if idx < len(soft_bits):
            block[i] = soft_bits[idx] & 0x00FF
            idx += 1
    
    # Block 4: positions 346-435 (90 bits)
    for i in range(346, 436):
        if idx < len(soft_bits):
            block[i] = soft_bits[idx] & 0x00FF
            idx += 1
    
    # Pack as little-endian signed shorts
    return struct.pack(f'<{len(block)}h', *block)

def test_cdecoder():
    """Test cdecoder with a test frame."""
    codec_path = os.path.join("tetra_codec", "bin", "cdecoder.exe")
    
    if not os.path.exists(codec_path):
        print(f"ERROR: Codec not found at {codec_path}")
        return False
    
    # Create test input file
    test_input = "test_frame_input.bin"
    test_output = "test_frame_output.wav"
    
    # Create multiple frames (cdecoder processes multiple frames)
    with open(test_input, 'wb') as f:
        # Write 10 test frames
        for _ in range(10):
            frame_data = create_test_frame()
            f.write(frame_data)
    
    print(f"Created test input file: {test_input} ({os.path.getsize(test_input)} bytes)")
    print(f"  - Contains 10 frames (690 shorts = 1380 bytes each)")
    
    # Run cdecoder
    print(f"\nRunning: {codec_path} {test_input} {test_output}")
    try:
        result = subprocess.run(
            [codec_path, test_input, test_output],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print(f"\nReturn code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
        
        # Check output
            if os.path.exists(test_output):
                output_size = os.path.getsize(test_output)
                print(f"\n[OK] Output file created: {test_output} ({output_size} bytes)")
            
            # Expected: 10 frames * 2 speech frames * (BFI + 137 shorts) = 10 * 276 = 2760 bytes
            expected_size = 10 * 276  # 10 frames * 276 bytes per frame pair
            print(f"  Expected size: ~{expected_size} bytes (10 frames * 276 bytes)")
            
            if output_size > 0:
                print("[OK] cdecoder produced output!")
                return True
            else:
                print("[FAIL] Output file is empty")
                return False
        else:
            print("[FAIL] Output file was not created")
            return False
            
    except subprocess.TimeoutExpired:
        print("[FAIL] cdecoder timed out")
        return False
    except Exception as e:
        print(f"[FAIL] Error running cdecoder: {e}")
        return False

def analyze_recorded_file(filename):
    """Analyze a recorded TETRA frame file."""
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return
    
    file_size = os.path.getsize(filename)
    print(f"\nAnalyzing: {filename}")
    print(f"  Size: {file_size} bytes")
    
    # Check if size is multiple of 1380 (690 shorts = 1380 bytes per frame)
    frame_size = 1380
    num_frames = file_size // frame_size
    remainder = file_size % frame_size
    
    print(f"  Frames: {num_frames} complete frames")
    if remainder > 0:
        print(f"  Remainder: {remainder} bytes (incomplete frame)")
    
    # Read first frame and check header
    with open(filename, 'rb') as f:
        first_frame = f.read(min(frame_size, file_size))
        if len(first_frame) >= 2:
            header = struct.unpack('<H', first_frame[0:2])[0]
            print(f"  First frame header: 0x{header:04X} (expected 0x6B21)")
            
            if header == 0x6B21:
                print("  [OK] Header is correct")
            else:
                print("  [FAIL] Header is incorrect")
    
    # Test decoding
    if num_frames > 0:
        print(f"\nTesting decoding with cdecoder...")
        codec_path = os.path.join("tetra_codec", "bin", "cdecoder.exe")
        if os.path.exists(codec_path):
            test_output = filename + "_decoded.wav"
            result = subprocess.run(
                [codec_path, filename, test_output],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            print(f"  Return code: {result.returncode}")
            if result.stdout:
                print(f"  STDOUT: {result.stdout.strip()}")
            if result.stderr:
                print(f"  STDERR: {result.stderr.strip()}")
            
            if os.path.exists(test_output) and os.path.getsize(test_output) > 0:
                print(f"  [OK] Decoded output: {test_output} ({os.path.getsize(test_output)} bytes)")
            else:
                print(f"  [FAIL] No decoded output created")

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("TETRA cdecoder Format Test")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        # Analyze a recorded file
        analyze_recorded_file(sys.argv[1])
    else:
        # Run format test
        print("\n1. Testing frame format creation...")
        test_frame = create_test_frame()
        print(f"   [OK] Created test frame: {len(test_frame)} bytes (690 shorts)")
        
        # Verify header
        header = struct.unpack('<H', test_frame[0:2])[0]
        print(f"   Header: 0x{header:04X} (expected 0x6B21)")
        
        print("\n2. Testing cdecoder...")
        success = test_cdecoder()
        
        if success:
            print("\n" + "=" * 60)
            print("[OK] Format test PASSED!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("[FAIL] Format test FAILED!")
            print("=" * 60)
        
        # Cleanup
        for f in ["test_frame_input.bin", "test_frame_output.wav"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
