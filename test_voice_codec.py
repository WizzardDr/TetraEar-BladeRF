"""
Test if TETRA voice codec is working
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import struct
from voice_processor import VoiceProcessor

print("=" * 60)
print("TETRA Voice Codec Test")
print("=" * 60)

vp = VoiceProcessor()
if not vp.working:
    print("✗ ERROR: Codec not found at:", vp.codec_path)
    print("\nPlease install the codec:")
    print("1. Run: python install_tetra_codec.py")
    print("2. Or manually place cdecoder.exe in tetra_codec/bin/")
    sys.exit(1)
else:
    print(f"✓ Codec found at: {vp.codec_path}")

# Create test frame (all zeros with header)
print("\nCreating test voice frame...")
shorts = [0x6B21] + [0] * 689
test_data = struct.pack('<' + 'h' * 690, *shorts)
print(f"  Frame size: {len(test_data)} bytes")
print(f"  Header: 0x{shorts[0]:04X}")

print("\nCalling codec...")
audio = vp.decode_frame(test_data)

if len(audio) > 0:
    print(f"✓ Codec working: produced {len(audio)} samples")
    print(f"  Audio format: {audio.dtype}")
    print(f"  Audio range: [{audio.min():.4f}, {audio.max():.4f}]")
    print(f"  Sample rate: 8000 Hz")
    
    # Save test audio
    import wave
    records_dir = os.path.join(os.path.dirname(__file__), "records")
    os.makedirs(records_dir, exist_ok=True)
    test_wav = os.path.join(records_dir, "codec_test.wav")
    
    with wave.open(test_wav, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        audio_int16 = (audio * 32767).astype(np.int16)
        wf.writeframes(audio_int16.tobytes())
    
    print(f"\n✓ Test audio saved to: {test_wav}")
    print("  You can play this file to verify codec output")
    
else:
    print("✗ Codec failed to produce audio")
    print("  This may indicate a codec configuration issue")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ Voice codec test PASSED")
print("=" * 60)
print("\nThe codec is ready to decode TETRA voice frames.")
print("You should now hear audio when voice transmissions occur.")
