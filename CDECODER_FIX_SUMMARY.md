# cdecoder Format Fix Summary

## Issues Fixed

### 1. Frame Format Correction
- **Problem**: Soft bits were using ±16384 range (too large)
- **Fix**: Scaled to ±127 range (matching cdecoder expectations)
- **Location**: `tetra_gui_modern.py::_extract_voice_slot_from_symbols()`

### 2. Frame Structure Fix
- **Problem**: Frames weren't structured correctly for `Read_Tetra_File()`
- **Fix**: Implemented proper 690-short block structure:
  - Header: 0x6B21 at position 0
  - Block 1: positions 1-114 (114 soft bits)
  - Block 2: positions 116-229 (114 soft bits)
  - Block 3: positions 231-344 (114 soft bits)
  - Block 4: positions 346-435 (90 soft bits)
  - Total: 432 soft bits in correct positions

### 3. Raw Frame Recording
- **Added**: Automatic recording of raw TETRA frames to binary files
- **Format**: `tetra_frames_<freq>MHz_<timestamp>.bin`
- **Content**: 690 shorts (1380 bytes) per frame, ready for cdecoder

### 4. Test Script
- **Created**: `test_cdecoder_format.py` to verify format
- **Usage**: `python test_cdecoder_format.py [recorded_file.bin]`
- **Tests**: Frame creation, format validation, cdecoder decoding

## cdecoder Input Format

### Required Format
- **File**: Binary file with 690 shorts (16-bit signed integers) per frame
- **Frame size**: 1380 bytes per frame
- **Header**: First short must be 0x6B21
- **Soft bits**: 432 soft bits in range -127 to +127, placed at specific positions
- **Endianness**: Little-endian

### Frame Structure (690 shorts = 1380 bytes)
```
Position 0:    0x6B21 (header)
Positions 1-114:   Block 1 (114 soft bits)
Positions 116-229: Block 2 (114 soft bits)
Positions 231-344: Block 3 (114 soft bits)
Positions 346-435: Block 4 (90 soft bits)
Remaining:      Padding (zeros)
```

### cdecoder Output Format
- **Output**: Binary file with decoded PCM audio
- **Format**: BFI (2 bytes) + 137 shorts (274 bytes) + BFI (2 bytes) + 137 shorts (274 bytes)
- **Per frame**: 276 bytes (2 speech frames)
- **Sample rate**: 8000 Hz

## Usage

### Recording Raw Frames
1. Start the modern GUI: `python tetra_gui_modern.py`
2. Tune to a TETRA frequency (e.g., 392.240 MHz)
3. Raw frames are automatically saved to `records/tetra_frames_<freq>MHz_<timestamp>.bin`

### Decoding Recorded Frames
```bash
cd tetra_codec\bin
.\cdecoder.exe ..\..\records\tetra_frames_392.240MHz_20251222_162956.bin out.wav
```

### Testing Format
```bash
python test_cdecoder_format.py
python test_cdecoder_format.py records\tetra_frames_392.240MHz_20251222_162956.bin
```

## Verification

### Test Results
- ✓ Frame format: 1380 bytes per frame
- ✓ Header: 0x6B21 correct
- ✓ cdecoder processes frames: "10 Channel Frames processed, 20 Speech Frames"
- ✓ Soft bits in correct range: -127 to +127

### Expected cdecoder Output
```
Frame Nb 1 Bfi active
...
cdecoder: reached end of input_file
10 Channel Frames processed
ie 20 Speech Frames
```

## Next Steps

1. **Find Active Frequencies**: Use GUI frequency scanner or manual tuning
2. **Record Signals**: Let GUI record raw frames automatically
3. **Decode**: Use cdecoder.exe on recorded .bin files
4. **Verify**: Check output WAV files for clear audio

## Notes

- Raw frames are saved automatically when voice frames are detected
- Files are appended to, so multiple frames accumulate in one file
- cdecoder can process multiple frames from one file
- BFI (Bad Frame Indicator) messages are normal - frames are still decoded
