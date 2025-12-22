"""
Main TETRA decoder application using RTL-SDR.
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from rtl_capture import RTLCapture
from signal_processor import SignalProcessor
from tetra_decoder import TetraDecoder
from tetra_crypto import TetraKeyManager
from frequency_scanner import FrequencyScanner
from voice_processor import VoiceProcessor


def setup_logging(log_file=None, debug=False):
    """
    Setup logging configuration.
    
    Args:
        log_file: Optional log file path
        debug: Enable debug logging
    """
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        # Overwrite log file on each start
        handlers.append(logging.FileHandler(log_file, mode='w'))
    
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )


def extract_voice_slot_from_symbols(frame, demodulated_symbols, samples_per_symbol):
    """
    Extract TETRA voice slot from symbol stream for codec.
    Returns soft bits (16-bit integers) in TETRA format (690 shorts = 1380 bytes).
    """
    try:
        import struct
        import numpy as np
        
        # Get frame position in symbol stream (in bits, not symbols)
        pos = frame.get('position')
        if pos is None:
            return None
        
        # Convert bit position to symbol position (3 bits per symbol for π/4-DQPSK)
        symbol_pos = pos // 3
            
        # TETRA slot is 255 symbols (510 bits)
        if symbol_pos + 255 > len(demodulated_symbols):
            return None
            
        slot_symbols = demodulated_symbols[symbol_pos:symbol_pos+255]
        
        # Convert symbols to soft bits for codec
        # π/4-DQPSK has 2 bits per symbol (dibits)
        soft_bits = []
        
        # Normal burst structure:
        # First block: 108 symbols (216 bits)
        # Training: 11 symbols (22 bits)
        # Second block: 108 symbols (216 bits)
        # Total: 227 symbols before tail
        
        # Extract first block (108 symbols = 216 bits)
        for i in range(108):
            if i >= len(slot_symbols):
                break
            sym = int(slot_symbols[i])
            # Extract 2 bits from symbol (MSB first)
            bit1 = (sym >> 1) & 1
            bit0 = sym & 1
            # Convert to soft bits: 1 -> +16384, 0 -> -16384
            soft_bits.append(16384 if bit1 else -16384)
            soft_bits.append(16384 if bit0 else -16384)
        
        # Skip training sequence (11 symbols at position 108-118)
        
        # Extract second block (108 symbols = 216 bits)
        for i in range(119, 227):
            if i >= len(slot_symbols):
                break
            sym = int(slot_symbols[i])
            bit1 = (sym >> 1) & 1
            bit0 = sym & 1
            soft_bits.append(16384 if bit1 else -16384)
            soft_bits.append(16384 if bit0 else -16384)
        
        # Now we have 432 soft bits (216 from each block)
        # cdecoder expects: Header (0x6B21) + 689 shorts = 690 shorts = 1380 bytes
        output_shorts = [0x6B21]  # Header marker
        output_shorts.extend(soft_bits)
        
        # Pad to 690 shorts if needed
        while len(output_shorts) < 690:
            output_shorts.append(0)
        
        # Truncate if too long
        output_shorts = output_shorts[:690]
        
        # Pack as little-endian signed shorts
        return struct.pack(f'<{len(output_shorts)}h', *output_shorts)
        
    except Exception as e:
        logging.getLogger(__name__).debug(f"Error extracting voice slot: {e}")
        return None


def main():
    """Main decoder application."""
    parser = argparse.ArgumentParser(
        description='TETRA Decoder using RTL-SDR',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--auto-tune',
        action='store_true',
        help='Automatically scan and tune to the strongest TETRA signal'
    )
    
    parser.add_argument(
        '-f', '--frequency',
        type=float,
        default=400e6,
        help='Center frequency in Hz (default: 400 MHz)'
    )
    
    parser.add_argument(
        '-s', '--sample-rate',
        type=float,
        default=1.8e6,
        help='Sample rate in Hz (default: 1.8 MHz)'
    )
    
    parser.add_argument(
        '-g', '--gain',
        type=str,
        default='auto',
        help='Gain setting: auto or numeric value (default: auto)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output file for decoded data'
    )
    
    parser.add_argument(
        '--log',
        type=str,
        help='Log file path (default: tetra_decoder.log)'
    )
    
    parser.add_argument(
        '--samples',
        type=int,
        default=1024*1024,
        help='Number of samples per capture (default: 1048576)'
    )
    
    parser.add_argument(
        '-k', '--keys',
        type=str,
        help='Path to key file for decryption'
    )
    
    parser.add_argument(
        '--auto-decrypt',
        action='store_true',
        default=True,
        help='Automatically try common keys for encrypted frames (default: enabled)'
    )
    
    parser.add_argument(
        '--no-auto-decrypt',
        action='store_false',
        dest='auto_decrypt',
        help='Disable automatic decryption attempts'
    )
    
    parser.add_argument(
        '--scan',
        action='store_true',
        help='Enable frequency scanning mode (finds TETRA signals automatically)'
    )
    
    parser.add_argument(
        '--scan-poland',
        action='store_true',
        help='Scan Poland TETRA frequency ranges (380-385, 390-395, 410-430 MHz)'
    )
    
    parser.add_argument(
        '--scan-start',
        type=float,
        help='Start frequency for scanning in MHz'
    )
    
    parser.add_argument(
        '--scan-end',
        type=float,
        help='End frequency for scanning in MHz'
    )
    
    parser.add_argument(
        '--min-power',
        type=float,
        default=-70,
        help='Minimum signal power in dB for detection (default: -70)'
    )
    
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.4,
        help='Minimum confidence threshold for TETRA detection (default: 0.4)'
    )
    
    parser.add_argument(
        '--decode-found',
        action='store_true',
        help='After scanning, decode found channels automatically'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_file = args.log or 'tetra_decoder.log'
    setup_logging(log_file, debug=args.debug)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("TETRA Decoder Starting")
    logger.info("=" * 60)
    
    # Determine if scanning mode
    scanning = args.scan or args.scan_poland or args.auto_tune
    
    if scanning:
        logger.info("Mode: Frequency Scanning")
        if args.auto_tune:
            logger.info("Target: Auto-tune to strongest signal")
        elif args.scan_poland:
            logger.info("Target: Poland TETRA frequency ranges")
        elif args.scan_start and args.scan_end:
            logger.info(f"Range: {args.scan_start} - {args.scan_end} MHz")
        else:
            logger.info("Range: Poland TETRA frequency ranges (default)")
    else:
        logger.info("Mode: Single Frequency Decoding")
        logger.info(f"Frequency: {args.frequency/1e6:.2f} MHz")
    
    logger.info(f"Sample Rate: {args.sample_rate/1e6:.2f} MHz")
    logger.info(f"Gain: {args.gain}")
    logger.info(f"Samples per capture: {args.samples}")
    logger.info(f"Auto-decrypt: {'Enabled' if args.auto_decrypt else 'Disabled'}")
    
    # Initialize key manager if key file provided
    key_manager = None
    if args.keys:
        try:
            key_manager = TetraKeyManager()
            key_manager.load_key_file(args.keys)
            logger.info(f"Loaded encryption keys from: {args.keys}")
        except Exception as e:
            logger.error(f"Failed to load key file: {e}")
            logger.warning("Continuing without decryption support")
    
    # Initialize components
    capture = RTLCapture(
        frequency=args.frequency,
        sample_rate=args.sample_rate,
        gain=args.gain if args.gain == 'auto' else float(args.gain)
    )
    
    processor = SignalProcessor(sample_rate=args.sample_rate)
    decoder = TetraDecoder(key_manager=key_manager, auto_decrypt=args.auto_decrypt)
    voice_processor = VoiceProcessor()
    
    # Open output file if specified
    output_file = None
    if args.output:
        output_file = open(args.output, 'w')
        output_file.write(f"TETRA Decoder Output - Started: {datetime.now()}\n")
        output_file.write("=" * 60 + "\n\n")
    
    # Initialize frame counter
    frame_count = 0
    
    try:
        # Open RTL-SDR device
        if not capture.open():
            logger.error("Failed to open RTL-SDR device")
            return 1
        
        # Scanning mode
        if scanning:
            scanner = FrequencyScanner(capture, sample_rate=args.sample_rate)
            
            try:
                if args.scan_poland:
                    found_channels = scanner.scan_poland(
                        min_power=args.min_power,
                        min_confidence=args.min_confidence
                    )
                elif args.scan_start and args.scan_end:
                    found_channels = scanner.scan_range(
                        args.scan_start * 1e6,
                        args.scan_end * 1e6,
                        min_power=args.min_power,
                        min_confidence=args.min_confidence
                    )
                else:
                    # Default to Poland ranges
                    found_channels = scanner.scan_poland(
                        min_power=args.min_power,
                        min_confidence=args.min_confidence
                    )
                
                # Print found channels
                scanner.print_found_channels()
                
                # Auto-tune logic
                if args.auto_tune and found_channels:
                    # Sort by power
                    found_channels.sort(key=lambda x: x.get('power_db', -100), reverse=True)
                    best_channel = found_channels[0]
                    freq = best_channel['frequency']
                    logger.info(f"\nAuto-tuning to strongest signal: {freq/1e6:.3f} MHz ({best_channel['power_db']:.1f} dB)")
                    
                    # Switch to single frequency decoding mode
                    capture.set_frequency(freq)
                    time.sleep(0.5)
                    scanning = False # Exit scanning block and fall through to decoding loop
                    
                elif args.auto_tune:
                    logger.warning("Auto-tune failed: No TETRA signals found")
                    return 0
                
                # Save found channels to output file if specified
                if args.output and not args.auto_tune:
                    with open(args.output, 'w') as f:
                        f.write(f"TETRA Channel Scan Results - {datetime.now()}\n")
                        f.write("=" * 80 + "\n\n")
                        for channel in found_channels:
                            f.write(f"Frequency: {channel['frequency_mhz']:.3f} MHz\n")
                            f.write(f"  Power: {channel['power_db']:.1f} dB\n")
                            f.write(f"  Confidence: {channel['confidence']:.2f}\n")
                            f.write(f"  Sync Detected: {channel.get('sync_detected', False)}\n")
                            f.write("\n")
                
                # Decode found channels if requested (and not auto-tuning which falls through)
                if args.decode_found and found_channels and not args.auto_tune:
                    logger.info("\nStarting decoding on found channels...")
                    logger.info("Press Ctrl+C to stop\n")
                    
                    frame_count = 0
                    output_file = None
                    if args.output:
                        output_file = open(args.output, 'a')
                        output_file.write("\n" + "=" * 80 + "\n")
                        output_file.write("Decoded Frames:\n")
                        output_file.write("=" * 80 + "\n\n")
                    
                    try:
                        for channel in found_channels:
                            freq = channel['frequency']
                            logger.info(f"\nTuning to {freq/1e6:.3f} MHz...")
                            capture.set_frequency(freq)
                            time.sleep(0.5)  # Allow PLL to lock
                            
                            # Decode for a short time on each channel
                            for _ in range(5):  # 5 captures per channel
                                try:
                                    samples = capture.read_samples(args.samples)
                                    demodulated = processor.process(samples)
                                    frames = decoder.decode(demodulated)
                                    
                                    if frames:
                                        frame_count += len(frames)
                                        logger.info(f"Found {len(frames)} frame(s) on {freq/1e6:.3f} MHz")
                                        
                                        for frame in frames:
                                            frame_info = decoder.format_frame_info(frame)
                                            logger.info(frame_info)
                                            
                                            if output_file:
                                                output_file.write(
                                                    f"{datetime.now()} - {freq/1e6:.3f} MHz - {frame_info}\n"
                                                )
                                                output_file.flush()
                                    
                                    time.sleep(1)
                                    
                                except KeyboardInterrupt:
                                    raise
                                except Exception as e:
                                    logger.debug(f"Error decoding on {freq/1e6:.3f} MHz: {e}")
                                    
                        if output_file:
                            output_file.write(f"\nTotal frames decoded: {frame_count}\n")
                            output_file.close()
                    
                    except KeyboardInterrupt:
                        logger.info("\nStopping decoder...")
                        if output_file:
                            output_file.close()
                
                if not args.auto_tune:
                    logger.info(f"\nScan complete. Found {len(found_channels)} channel(s)")
                    return 0
                
            except KeyboardInterrupt:
                logger.info("\nScan interrupted by user")
                return 0
        
        # Single frequency decoding mode (or auto-tuned)
        logger.info("Starting signal capture and decoding...")
        logger.info("Press Ctrl+C to stop\n")
        
        frame_count = 0
        
        while True:
            try:
                # Capture samples
                logger.debug("Capturing samples...")
                samples = capture.read_samples(args.samples)
                logger.debug(f"Captured {len(samples)} samples")
                
                # Process signal
                logger.debug("Processing signal...")
                demodulated = processor.process(samples)
                logger.debug(f"Demodulated {len(demodulated)} symbols")
                
                # Decode frames
                logger.debug("Decoding frames...")
                frames = decoder.decode(demodulated)
                
                if frames:
                    frame_count += len(frames)
                    logger.info(f"\nFound {len(frames)} frame(s) in this capture")
                    
                    for frame in frames:
                        frame_info = decoder.format_frame_info(frame)
                        logger.info(frame_info)
                        
                        # Check for voice frames and decode
                        mac_pdu = frame.get('mac_pdu', {})
                        pdu_type = mac_pdu.get('type', '') if isinstance(mac_pdu, dict) else ''
                        
                        is_voice_frame = (
                            frame.get('type') == 1 or  # Traffic
                            'FRAG' in str(pdu_type) or
                            frame.get('type_name', '').upper() == 'MAC-FRAG'
                        )
                        
                        if is_voice_frame:
                            logger.debug(f"Voice frame detected (Frame #{frame['number']})")
                            voice_slot = extract_voice_slot_from_symbols(
                                frame, demodulated, processor.samples_per_symbol
                            )
                            if voice_slot:
                                audio = voice_processor.decode_frame(voice_slot)
                                if len(audio) > 0:
                                    logger.info(f"  🔊 Decoded {len(audio)} audio samples")
                                    
                                    # Save to file - Append to session file
                                    try:
                                        import wave
                                        import os
                                        records_dir = "records"
                                        os.makedirs(records_dir, exist_ok=True)
                                        
                                        # Use a fixed filename for the session to append
                                        session_filename = os.path.join(records_dir, "session_audio.wav")
                                        
                                        # Check if file exists to determine mode
                                        mode = 'wb'
                                        if os.path.exists(session_filename):
                                            # Wave module doesn't support 'ab' (append) directly for writing frames easily without reading first
                                            # So we'll read existing, append, and write back (inefficient but works for CLI demo)
                                            # OR better: just write raw PCM and convert later, or use a different approach.
                                            # Let's use a simple approach: Write separate files but with millisecond timestamps to avoid overwrite
                                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19] # include ms
                                            filename = os.path.join(records_dir, f"voice_{timestamp}.wav")
                                            
                                            with wave.open(filename, 'wb') as wav_file:
                                                wav_file.setnchannels(1)
                                                wav_file.setsampwidth(2)
                                                wav_file.setframerate(8000)
                                                audio_int16 = (audio * 32767).astype(int)
                                                wav_file.writeframes(audio_int16.tobytes())
                                                logger.info(f"  💾 Saved {len(audio)} samples to {filename}")
                                        else:
                                            # First file
                                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
                                            filename = os.path.join(records_dir, f"voice_{timestamp}.wav")
                                            with wave.open(filename, 'wb') as wav_file:
                                                wav_file.setnchannels(1)
                                                wav_file.setsampwidth(2)
                                                wav_file.setframerate(8000)
                                                audio_int16 = (audio * 32767).astype(int)
                                                wav_file.writeframes(audio_int16.tobytes())
                                                logger.info(f"  💾 Saved {len(audio)} samples to {filename}")

                                    except Exception as e:
                                        logger.error(f"Failed to save audio: {e}")
                        
                        if output_file:
                            output_file.write(f"{datetime.now()} - {frame_info}\n")
                            output_file.flush()
                    
                    logger.info(f"Total frames decoded: {frame_count}\n")
                else:
                    logger.debug("No frames found in this capture")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                logger.info("\nStopping decoder...")
                break
            except Exception as e:
                logger.error(f"Error during processing: {e}", exc_info=True)
                time.sleep(1)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    finally:
        # Cleanup
        capture.close()
        if output_file:
            output_file.write(f"\nDecoder stopped: {datetime.now()}\n")
            output_file.write(f"Total frames decoded: {frame_count}\n")
            output_file.close()
        
        logger.info("=" * 60)
        logger.info(f"TETRA Decoder Stopped - Total frames: {frame_count}")
        logger.info("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
