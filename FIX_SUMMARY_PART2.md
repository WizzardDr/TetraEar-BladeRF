# Fix Summary - Part 2

## Issues Addressed
1. **Garbage Text Decoding**: Fixed in Part 1.
2. **Corrupted Voice WAV Files**: Fixed in Part 1.
3. **Missing/Fragmented SDS Messages**: The user noted that "multiple frames can be one message". This implies that fragmented SDS messages were not being reassembled correctly.
4. **Incorrect Symbol/Bit Processing**: The decoder was treating 3-bit symbols (0-7) as 3 bits instead of mapping them to 2-bit π/4-DQPSK symbols. This caused:
    - Incorrect bit stream.
    - Incorrect sync detection (or sync detection on wrong data).
    - Incorrect burst parsing (garbage frame types and data).

## Changes Made

### `tetra_decoder.py`
- **`symbols_to_bits`**: Updated to correctly map 8-PSK symbols (0-7) to π/4-DQPSK symbols (0-3) and then to 2 bits.
    - Mapping: 1->00, 3->01, 5->11, 7->10 (Gray coding).
- **`find_sync`**: Updated to use the standard TETRA Training Sequence 1 (22 bits) for synchronization.
- **`decode`**:
    - Now uses the corrected bit stream.
    - Adjusts the sync position by subtracting 216 bits (offset to start of burst).
    - Extracts the correct 255 symbols (0-3) for the frame.
    - Passes these symbols to `decode_frame`.
- **`decode_frame`**:
    - Accepts optional `symbols` argument.
    - If `symbols` are provided, passes them directly to `protocol_parser.parse_burst`.
    - If not, reconstructs them from bits (fallback).
    - This ensures `parse_burst` receives the correct 0-3 symbols it expects.

## Verification
- Run the test script again.
- Expect to see valid frame types (0, 1, 2) instead of random ones (5, 7, 13).
- Expect to see "Reassembled" messages if fragmented SDS is present.
- Voice decoding should still work (or work better).
