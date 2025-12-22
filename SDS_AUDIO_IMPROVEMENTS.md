# TETRA GUI Improvements - SDS Reassembly and Continuous Audio

## Changes Made

### 1. SDS Message Reassembly
**Problem**: Multi-frame SDS messages were not being reassembled, showing only fragments.

**Solution**: Added comprehensive SDS reassembly logic in `tetra_gui_modern.py`:
- Added `sds_fragments` dictionary to track message fragments by (src, dst, msg_id)
- Added `reassemble_sds_message()` method that:
  - Tracks MAC-FRAG and MAC-DATA frames
  - Collects fragments by sequence number
  - Reassembles complete messages when final fragment arrives
  - Cleans up old fragments after 30 seconds timeout
  - Marks reassembled messages with `[REASSEMBLED]` prefix
- Integrated reassembly into `on_frame()` method before displaying

### 2. Continuous Audio Recording
**Problem**: Audio was being saved in short 1-3 second WAV files instead of one continuous recording.

**Solution**: Implemented continuous recording in `on_voice_audio()`:
- Opens a single WAV file when first voice audio arrives
- Writes all voice frames to the same file continuously
- File remains open during entire capture session
- Closes and saves on Stop or application close
- Filename format: `tetra_voice_YYYYMMDD_HHMMSS.wav`
- Sample rate: 8000 Hz, 16-bit mono PCM

**Key Changes**:
- Removed timer-based chunking (`recording_timer`)
- Added `recording_active` flag to track recording state
- Added `wav_file` handle for continuous writing
- Added `recording_start_time` to track duration
- Updated `save_recording()` to close file properly
- Updated `on_stop()` and `closeEvent()` to save recording

### 3. Testing Infrastructure
**Created**: `test_real_frequency.py` - A frequency scanner script to:
- Scan 390-392 MHz and 420-430 MHz TETRA bands
- Detect strong signals (> -60 dB)
- Report top frequencies by signal strength
- Recommend best frequency for testing

## Usage Instructions

### Testing with Real Frequency:

1. **Find Active TETRA Frequencies**:
   ```bash
   python test_real_frequency.py
   ```
   This will scan and show the strongest signals around 391.5 MHz.

2. **Start the GUI**:
   ```bash
   python tetra_gui_modern.py
   ```

3. **Tune to Active Frequency**:
   - Enter frequency from scanner (e.g., `391.524`)
   - Click "⚡ Tune"
   - Click "▶ Start"

4. **Monitor for Real Data**:
   - **SDS Messages**: Look for frames with 📝 icon showing text messages
   - **Reassembled SDS**: Marked with 🧩 icon and `[REASSEMBLED]` prefix
   - **Voice Audio**: Look for 🔊 icon, check `records/` folder for WAV files

5. **Audio Recording**:
   - Recording starts automatically when voice is detected
   - Single WAV file created per session
   - Check `records/` folder for `tetra_voice_*.wav` files
   - File closes when you click Stop or close the application

### Verifying Human Audio:
- Check WAV file properties: 8000 Hz, 16-bit, mono
- Play the file - should hear continuous speech (not clicks/beeps)
- Duration should match capture session (not 1-3 seconds)

### Verifying SDS Reassembly:
- Multi-frame messages show as single entry with full text
- Marked with 🧩 icon and `[REASSEMBLED]` prefix
- Description shows complete message content

## Technical Details

### SDS Fragment Tracking:
- Fragments indexed by: `(source_ssi, dest_ssi, message_id)`
- Sequence numbers tracked: 0, 1, 2, ... N
- Reassembly triggers on MAC-END or final fragment
- 30-second timeout for incomplete messages

### Audio Pipeline:
- TETRA voice frames → cdecoder.exe → PCM samples
- PCM format: 8000 Hz, 16-bit signed, mono
- Continuous buffering to single WAV file
- No segmentation or timeout-based saving

## Files Modified:
- `tetra_gui_modern.py`: Main GUI with SDS reassembly and continuous audio

## Files Created:
- `test_real_frequency.py`: Frequency scanner for finding active TETRA signals

## Expected Results:
✅ Complete SDS text messages (not fragments)
✅ Long continuous audio recordings (not 1-3s clips)
✅ Human-readable voice in WAV files
✅ Real-time display of reassembled messages
