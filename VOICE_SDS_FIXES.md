# TETRA Decoder - Voice and SDS Fixes

## Issues Fixed

### Issue 1: No Voice Audio When Monitoring
**Problem**: Enabling "🔊 Monitor Audio" doesn't play decoded voice

**Root Cause**: 
- Voice extraction method was too complex and dependent on symbol-level extraction
- Voice frames weren't being properly identified
- Codec input format was incorrect

**Fix Applied**:
1. Simplified voice detection to look for MAC-FRAG and clear MAC-DATA frames
2. Extract voice data directly from MAC PDU payload
3. Convert payload bytes to codec soft-bit format
4. Properly format for cdecoder.exe (690 shorts starting with 0x6B21 header)

**How It Works Now**:
```python
MAC-FRAG frame → Extract data → Convert to soft bits → cdecoder.exe → PCM audio
```

### Issue 2: SDS Messages Show as Numbers, Not Text
**Problem**: SDS filter shows frames with hex data instead of reconstructed text

**Root Cause**:
- GUI reassembly logic was too complex and not parsing existing SDS messages
- Not falling back to text parsing when SDS parser fails
- Not checking decoded_text field from decoder

**Fix Applied**:
1. Simplified reassembly to first check if message is already parsed
2. Parse from decrypted_bytes or MAC PDU data
3. Fall back to text decoding if SDS parser doesn't work
4. Check both 'sds_message' and 'decoded_text' fields

## Testing Instructions

### Test Voice Audio:

1. **Start GUI**:
   ```bash
   python tetra_gui_modern.py
   ```

2. **Tune to active frequency** (from scanner):
   - Enter: `392.225`
   - Click "⚡ Tune"

3. **Enable audio monitoring**:
   - Check "🔊 Monitor Audio"

4. **Start capture**:
   - Click "▶ Start"

5. **Look for voice frames**:
   - Green rows with 🔊 icon in Data column
   - MAC-FRAG frames (green background)
   - Should hear audio if voice transmission is active

6. **Verify**:
   - Audio should play through speakers
   - Check `records/` folder for WAV file
   - WAV should contain human speech, not noise

### Test SDS Messages:

1. **Filter for SDS**:
   - Type filter dropdown → "SDS"

2. **Look for text messages**:
   - Cyan rows with 📝 icon
   - Description column should show actual text
   - Data column should show readable message

3. **Expected formats**:
   - `[SDS-1] HELLO WORLD`
   - `[SDS-GSM] STATUS OK`
   - `[TXT] Message text here`

## Troubleshooting

### Still No Voice Audio?

**Check 1**: Verify codec is installed
```bash
dir tetra_codec\bin\cdecoder.exe
```
Should exist and be executable.

**Check 2**: Look for MAC-FRAG frames
- Filter by type: "Traffic" or "All"
- Look for green rows (MAC-FRAG)
- These typically carry voice

**Check 3**: Check if frames are encrypted
- If "Encrypted" column shows "Yes", voice won't decode
- Need proper keys for encrypted voice

**Check 4**: Verify audio device
- Windows: Check sound settings
- Ensure default playback device is set
- Volume should be up

**Check 5**: Enable debug logging
Edit `tetra_gui_modern.py`, add at top:
```python
logging.basicConfig(level=logging.DEBUG)
```
Look for "Decoded voice: N samples" messages.

### Still No Text in SDS?

**Check 1**: Verify frames have data
- Look at Data column
- Should show hex bytes at minimum

**Check 2**: Check encryption
- Encrypted frames won't show text
- Look for "Clear" in Status column

**Check 3**: Try different frequencies
- Some frequencies may only carry voice
- Others may carry data/SDS
- Use scanner to find active frequencies

**Check 4**: Check frame types
- SDS typically in:
  - MAC-DATA (cyan)
  - MAC-SUPPL (purple)
  - Sometimes MAC-FRAG

## What You Should See

### Successful Voice Decoding:
```
Console output:
"Decoded voice: 274 samples"
"Codec produced audio with max amp 0.4567"

GUI:
- Green rows in table (MAC-FRAG)
- 🔊 icon in Data column
- "Voice Audio (Decoded)" text
- Audio playing through speakers
- WAV file growing in records/
```

### Successful SDS Decoding:
```
GUI:
- Cyan rows in table (MAC-DATA/SUPPL)
- 📝 icon in Description column
- Actual message text visible
- Data column shows "[TXT] message" or "[SDS-1] message"
```

## Known Limitations

1. **Voice Quality**: Depends on signal strength and codec quality
   - Weak signals may produce distorted audio
   - Need -40 dB or better for good quality

2. **SDS Fragments**: Multi-frame messages may still show as separate frames
   - Each fragment will be parsed individually
   - Full reassembly requires sequence tracking

3. **Encryption**: Encrypted traffic won't decode without proper keys
   - Most commercial TETRA networks are encrypted
   - Need keys file for decryption

4. **Real-time**: Voice has ~100-200ms latency
   - Due to buffering and codec processing
   - Normal for digital voice systems

## Quick Test Script

Test if voice codec is working:

```python
# test_voice_codec.py
import numpy as np
import struct
from voice_processor import VoiceProcessor

vp = VoiceProcessor()
if not vp.working:
    print("ERROR: Codec not found!")
else:
    print("✓ Codec found")
    
    # Create test frame (all zeros with header)
    shorts = [0x6B21] + [0] * 689
    test_data = struct.pack('<' + 'h' * 690, *shorts)
    
    audio = vp.decode_frame(test_data)
    if len(audio) > 0:
        print(f"✓ Codec working: produced {len(audio)} samples")
    else:
        print("✗ Codec failed to produce audio")
```

Run it:
```bash
python test_voice_codec.py
```

Expected output:
```
✓ Codec found
✓ Codec working: produced 274 samples
```

## File Changes Summary

**Modified**: `tetra_gui_modern.py`
1. Simplified `reassemble_sds_message()` - now checks existing parsed messages first
2. Rewrote voice extraction in capture thread - direct MAC PDU to codec conversion
3. Added proper byte-to-softbit conversion for voice codec
4. Added more debug logging for voice processing

## Next Steps

1. Launch GUI with: `python tetra_gui_modern.py`
2. Tune to: `392.225 MHz` (or use scanner results)
3. Enable "🔊 Monitor Audio"
4. Click Start
5. Wait for voice transmission
6. Should hear decoded speech in real-time
7. Check records/ for WAV file

If still not working after these fixes, the issue may be:
- No active voice transmissions on the frequency
- Signal too weak (< -60 dB)
- Voice codec incompatibility
- Audio device configuration

## Success Indicators

✅ **Voice Working**:
- Hearing audio through speakers
- Console shows "Decoded voice: N samples"
- WAV file in records/ contains speech
- Green MAC-FRAG frames with 🔊 icon

✅ **SDS Working**:
- Cyan frames with readable text in Description
- Data column shows "[TXT]" or "[SDS-1]" prefix
- Can filter by "SDS" and see messages
- No hex dumps, actual readable text
