# Fix Summary

## Issues Addressed
1. **Garbage Text Decoding**: The automated test script was blindly decoding raw binary data as text when no valid SDS message was found.
2. **Corrupted Voice WAV Files**: The `cdecoder` output contains raw PCM data interleaved with Bad Frame Indicators (BFI), which was being saved directly as a WAV file without processing or headers.

## Changes Made

### `auto_test_find_record_decode.py`
- Removed the fallback logic that attempted to decode `mac_pdu['data']` as UTF-8/Latin-1 when no SDS message was present. This prevents garbage output like `****`, `((`, etc.
- Updated `_test_cdecoder` to post-process the `cdecoder` output.
- Added `_convert_raw_to_wav` method to:
  - Parse the raw output format (BFI + 137 shorts).
  - Extract valid PCM samples.
  - Write a proper WAV file with correct header (8kHz, 16-bit, mono).

### `tetra_decoder.py`
- Removed redundant logic in `decode_frame` that was re-attempting SDS parsing unnecessarily.

## Verification
- The text output should now only show valid SDS messages.
- The `cdecoded_*.wav` files should now be playable audio files instead of raw data with static/corruption.
