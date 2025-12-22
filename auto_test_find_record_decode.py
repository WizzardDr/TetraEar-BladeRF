"""
Automated TETRA Testing Script

Finds frequencies, records signals, decodes, and verifies TEXT (SDS) and VOICE.
Implements TETRA specifications according to:
- ETSI EN 300 392-2 V3.2.1 (Air Interface)
- ETSI EN 300 395-2 V1.3.0 (Voice Codec)
- π/4-DQPSK modulation at 18 kHz symbol rate
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime
from pathlib import Path
import numpy as np

# Setup logging with professional style
# Note: Logs overwrite on each start and use professional format (per user preference)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)-8s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('test_session.log', mode='w'),  # Overwrites on each start
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

from rtl_capture import RTLCapture
from signal_processor import SignalProcessor
from tetra_decoder import TetraDecoder
from tetra_crypto import TetraKeyManager
from frequency_scanner import FrequencyScanner
from voice_processor import VoiceProcessor

class AutoTester:
    """Automated TETRA testing and verification."""
    
    def __init__(self, sample_rate=2.4e6, default_gain=50, noise_floor=-45, bottom_threshold=-85):
        """
        Initialize automated TETRA tester.
        
        Args:
            sample_rate: Sample rate in Hz (default: 2.4 MHz per TETRA spec)
            default_gain: Default RTL-SDR gain setting (default: 50)
            noise_floor: Noise floor threshold in dB (default: -45 dB)
            bottom_threshold: Bottom power threshold in dB (default: -85 dB)
        """
        self.sample_rate = sample_rate
        self.default_gain = default_gain
        self.noise_floor = noise_floor
        self.bottom_threshold = bottom_threshold
        self.capture = None
        self.processor = None
        self.decoder = None
        self.voice_processor = VoiceProcessor()
        self.records_dir = Path("records")
        self.records_dir.mkdir(exist_ok=True)
        self.found_frequencies = []
        self.test_results = {
            'frequencies_found': [],
            'text_messages': [],
            'voice_frames': [],
            'decoded_audio': []
        }
        
    def find_frequencies(self, start_freq=390.0e6, end_freq=395.0e6, step=25e3, dwell_time=0.5):
        """Find active TETRA frequencies."""
        logger.info("=" * 60)
        logger.info("STEP 1: Finding TETRA Frequencies")
        logger.info("=" * 60)
        logger.info(f"Scanning {start_freq/1e6:.3f} - {end_freq/1e6:.3f} MHz (step: {step/1e3:.1f} kHz)")
        
        try:
            self.capture = RTLCapture(
                frequency=start_freq,
                sample_rate=self.sample_rate,
                gain=self.default_gain
            )
            
            if not self.capture.open():
                logger.error("Failed to open RTL-SDR device")
                return []
            
            scanner = FrequencyScanner(
                self.capture, 
                self.sample_rate, 
                scan_step=step,
                noise_floor=self.noise_floor,
                bottom_threshold=self.bottom_threshold
            )
            # Use bottom_threshold as minimum power for detection
            found = scanner.scan_range(
                start_freq, 
                end_freq, 
                min_power=self.bottom_threshold, 
                min_confidence=0.4
            )
            
            self.found_frequencies = found
            logger.info(f"\nFound {len(found)} active frequency(ies):")
            for ch in found:
                freq_mhz = ch['frequency'] / 1e6
                power = ch['power_db']
                conf = ch['confidence']
                logger.info(f"  - {freq_mhz:.3f} MHz: Power={power:.1f} dB, Confidence={conf:.2f}")
            
            self.test_results['frequencies_found'] = found
            return found
            
        except Exception as e:
            logger.error(f"Error finding frequencies: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return []
    
    def record_and_decode(self, frequency, duration=10.0):
        """Record and decode signals at a specific frequency."""
        logger.info("=" * 60)
        logger.info(f"STEP 2: Recording and Decoding at {frequency/1e6:.3f} MHz")
        logger.info("=" * 60)
        
        try:
            # Tune to frequency
            if self.capture:
                self.capture.close()
            
            self.capture = RTLCapture(
                frequency=frequency,
                sample_rate=self.sample_rate,
                gain=self.default_gain
            )
            
            if not self.capture.open():
                logger.error("Failed to open RTL-SDR")
                return False
            
            logger.info(f"Tuned to {frequency/1e6:.3f} MHz, recording for {duration:.1f} seconds...")
            
            # Initialize processors
            self.processor = SignalProcessor(sample_rate=self.sample_rate)
            self.decoder = TetraDecoder(auto_decrypt=True)
            
            # Recording buffers
            raw_frames_buffer = []
            text_messages = []
            voice_frames_count = 0
            decoded_audio_samples = []
            
            # Timestamp for filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            freq_mhz = frequency / 1e6
            
            # Raw frames file
            raw_frames_file = self.records_dir / f"tetra_frames_{freq_mhz:.3f}MHz_{timestamp}.bin"
            raw_frames_fp = open(raw_frames_file, 'wb')
            
            # WAV file for decoded audio
            import wave
            wav_file = self.records_dir / f"tetra_voice_{freq_mhz:.3f}MHz_{timestamp}.wav"
            wav_fp = wave.open(str(wav_file), 'wb')
            wav_fp.setnchannels(1)
            wav_fp.setsampwidth(2)
            wav_fp.setframerate(8000)
            
            start_time = time.time()
            frame_count = 0
            samples_collected = 0
            
            logger.info("Recording... (press Ctrl+C to stop early)")
            
            try:
                while time.time() - start_time < duration:
                    # Read samples - INCREASED BUFFER SIZE to ensure full frames
                    # 2.4 MSps * 0.1s = 240k samples. Let's use 256k or 512k.
                    # Previous 32k was too small (~13ms), splitting every frame.
                    samples = self.capture.read_samples(512 * 1024)
                    if len(samples) < 1000:
                        time.sleep(0.1)
                        continue
                    
                    samples_collected += len(samples)
                    
                    # Process signal
                    demodulated = self.processor.process(samples)
                    
                    # Store demodulated symbols for voice extraction
                    if hasattr(self.processor, 'symbols'):
                        demodulated_symbols = self.processor.symbols
                    else:
                        demodulated_symbols = demodulated if isinstance(demodulated, np.ndarray) else None
                    
                    samples_per_symbol = int(self.sample_rate / 18000) if 18000 > 0 else 10
                    
                    # Decode frames
                    frames = self.decoder.decode(demodulated)
                    
                    for frame in frames:
                        frame_count += 1
                        
                        # Check for text messages (SDS)
                        sds_message = None
                        if 'sds_message' in frame and frame['sds_message']:
                            sds_message = frame['sds_message']
                        elif 'decoded_text' in frame and frame['decoded_text']:
                            sds_message = frame['decoded_text']
                        
                        if sds_message:
                            text_messages.append({
                                'time': datetime.now().isoformat(),
                                'frequency': frequency,
                                'message': sds_message,
                                'frame': frame
                            })
                            logger.info(f"[TEXT] {sds_message}")
                        
                        # Extract and decode voice
                        if self.voice_processor and self.voice_processor.working:
                            codec_input = None
                            
                            # Check if frame is encrypted and decrypted
                            voice_bits = None
                            if frame.get('decrypted') and 'decrypted_payload' in frame:
                                # Use decrypted bits!
                                try:
                                    payload_str = frame['decrypted_payload']
                                    # Convert string '0101...' to list of ints
                                    voice_bits = np.array([int(b) for b in payload_str], dtype=np.uint8)
                                    # Skip header (first 32 bits usually) if needed, but payload usually starts after header
                                    # In tetra_decoder, decrypted_payload is bits[32:]
                                    # So we have the payload bits directly.
                                    # But voice frames might need the whole frame or specific parts.
                                    # The codec expects 432 bits for a speech frame.
                                    # If decrypted_payload is the MAC PDU payload, it might be enough.
                                except Exception as e:
                                    logger.debug(f"Error using decrypted payload: {e}")
                            
                            # If no decrypted bits, try raw bits (only if not encrypted)
                            if voice_bits is None and not frame.get('encrypted'):
                                if 'bits' in frame:
                                    voice_bits = frame['bits']
                                elif 'mac_pdu' in frame:
                                    mac = frame['mac_pdu']
                                    if isinstance(mac, dict) and 'data' in mac:
                                        data = mac['data']
                                        if isinstance(data, bytes) and len(data) >= 17:
                                            bit_list = []
                                            for byte_val in data:
                                                for bit_idx in range(8):
                                                    bit_list.append((byte_val >> (7 - bit_idx)) & 1)
                                            voice_bits = np.array(bit_list[:432], dtype=np.uint8)
                            
                            # Try to build codec frame from bits (decrypted or clear)
                            if voice_bits is not None and len(voice_bits) >= 432:
                                codec_input = self._build_codec_frame(voice_bits)
                            
                            # Fallback: Try to extract from symbols (ONLY if not encrypted)
                            # Symbols are raw air interface, so they are encrypted if frame is encrypted
                            if codec_input is None and not frame.get('encrypted') and demodulated_symbols is not None:
                                codec_input = self._extract_voice_slot_from_symbols(
                                    frame, demodulated_symbols, samples_per_symbol
                                )
                            
                            # Decode voice frame
                            if codec_input is not None and len(codec_input) == 1380:
                                # Save raw frame
                                raw_frames_fp.write(codec_input)
                                raw_frames_buffer.append(codec_input)
                                
                                # Decode with codec
                                audio_segment = self.voice_processor.decode_frame(codec_input)
                                if len(audio_segment) > 0:
                                    voice_frames_count += 1
                                    decoded_audio_samples.extend(audio_segment)
                                    
                                    # Write to WAV
                                    audio_int16 = (audio_segment * 32767).astype(np.int16)
                                    wav_fp.writeframes(audio_int16.tobytes())
                                    
                                    if voice_frames_count % 10 == 0:
                                        logger.info(f"[VOICE] Decoded {voice_frames_count} voice frames, {len(decoded_audio_samples)} samples")
                    
                    # Progress update
                    elapsed = time.time() - start_time
                    if int(elapsed) % 2 == 0 and int(elapsed * 10) % 20 == 0:
                        logger.info(f"  Progress: {elapsed:.1f}s / {duration:.1f}s, Frames: {frame_count}, Samples: {samples_collected}")
            
            except KeyboardInterrupt:
                logger.info("\nRecording stopped by user")
            
            finally:
                # Close files
                raw_frames_fp.close()
                wav_fp.close()
                
                logger.info(f"\nRecording complete:")
                logger.info(f"  - Frames decoded: {frame_count}")
                logger.info(f"  - Text messages: {len(text_messages)}")
                logger.info(f"  - Voice frames: {voice_frames_count}")
                logger.info(f"  - Audio samples: {len(decoded_audio_samples)}")
                logger.info(f"  - Raw frames file: {raw_frames_file}")
                logger.info(f"  - Audio file: {wav_file}")
            
            # Test cdecoder on recorded frames
            if len(raw_frames_buffer) > 0:
                logger.info("\nTesting cdecoder on recorded frames...")
                self._test_cdecoder(raw_frames_file, wav_file.parent / f"cdecoded_{wav_file.name}")
            
            # Store results
            self.test_results['text_messages'].extend(text_messages)
            self.test_results['voice_frames'].append({
                'frequency': frequency,
                'count': voice_frames_count,
                'samples': len(decoded_audio_samples),
                'raw_file': str(raw_frames_file),
                'audio_file': str(wav_file)
            })
            
            return len(text_messages) > 0 or voice_frames_count > 0
            
        except Exception as e:
            logger.error(f"Error recording/decoding at {frequency/1e6:.3f} MHz: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _extract_voice_slot_from_symbols(self, frame, demodulated_symbols, samples_per_symbol):
        """Extract voice slot from symbol stream."""
        try:
            import struct
            
            pos = frame.get('position')
            if pos is None:
                return None
            
            symbol_pos = pos // 3
            if symbol_pos + 255 > len(demodulated_symbols):
                return None
            
            slot_symbols = demodulated_symbols[symbol_pos:symbol_pos+255]
            soft_bits = []
            
            # Extract first block (108 symbols = 216 bits)
            for i in range(108):
                if i >= len(slot_symbols):
                    break
                sym = int(slot_symbols[i])
                bit1 = (sym >> 1) & 1
                bit0 = sym & 1
                # Scale to ±127 range
                # Logic: 1 -> -127, 0 -> 127
                soft_bits.append(-127 if bit1 else 127)
                soft_bits.append(-127 if bit0 else 127)
            
            # Extract second block (108 symbols = 216 bits)
            for i in range(119, 227):
                if i >= len(slot_symbols):
                    break
                sym = int(slot_symbols[i])
                bit1 = (sym >> 1) & 1
                bit0 = sym & 1
                soft_bits.append(-127 if bit1 else 127)
                soft_bits.append(-127 if bit0 else 127)
            
            # Build 690-short frame
            return self._build_codec_frame_from_soft_bits(soft_bits)
            
        except Exception as e:
            logger.debug(f"Error extracting voice slot from symbols: {e}")
            return None
    
    def _build_codec_frame_from_soft_bits(self, soft_bits):
        """Build codec frame from soft bits."""
        import struct
        
        if len(soft_bits) < 432:
            return None
        
        block = [0] * 690
        
        # Header 1
        block[0] = 0x6B21
        
        idx = 0
        # Block 1: positions 1-114 (114 bits)
        for i in range(1, 115):
            if idx < len(soft_bits):
                block[i] = soft_bits[idx]
                idx += 1
        
        # Header 2
        block[115] = 0x6B22
        
        # Block 2: positions 116-229 (114 bits)
        for i in range(116, 230):
            if idx < len(soft_bits):
                block[i] = soft_bits[idx]
                idx += 1
        
        # Header 3
        block[230] = 0x6B26
        
        # Block 3: positions 231-344 (114 bits)
        for i in range(231, 345):
            if idx < len(soft_bits):
                block[i] = soft_bits[idx]
                idx += 1
        
        # Block 4: positions 345-434 (90 bits)
        for i in range(345, 435):
            if idx < len(soft_bits):
                block[i] = soft_bits[idx]
                idx += 1
        
        # Header 4 at end of data?
        block[435] = 0x6B21
        
        return struct.pack(f'<{len(block)}h', *block)
    
    def _build_codec_frame(self, voice_bits):
        """Build codec frame from hard bits."""
        import struct
        
        if len(voice_bits) < 432:
            return None
        
        soft_bits = []
        for bit in voice_bits[:432]:
            # Logic: 1 -> -127, 0 -> 127
            soft_bits.append(-127 if bit else 127)
        
        return self._build_codec_frame_from_soft_bits(soft_bits)
    
    def _test_cdecoder(self, input_file, output_file):
        """Test cdecoder on recorded frames."""
        codec_path = Path("tetra_codec") / "bin" / "cdecoder.exe"
        
        if not codec_path.exists():
            logger.warning(f"cdecoder not found at {codec_path}")
            return False
        
        # Use a temporary file for raw output
        raw_output = output_file.with_suffix('.raw')
        logger.info(f"Running: {codec_path} {input_file} {raw_output}")
        
        try:
            result = subprocess.run(
                [str(codec_path), str(input_file), str(raw_output)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            logger.info(f"Return code: {result.returncode}")
            if result.stdout:
                logger.info(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                logger.info(f"STDERR:\n{result.stderr}")
            
            if raw_output.exists() and raw_output.stat().st_size > 0:
                logger.info(f"[OK] cdecoder output: {raw_output} ({raw_output.stat().st_size} bytes)")
                
                # Convert raw output to WAV
                self._convert_raw_to_wav(raw_output, output_file)
                
                # Cleanup raw file
                try:
                    raw_output.unlink()
                except:
                    pass
                    
                return True
            else:
                logger.warning(f"[FAIL] cdecoder produced no output")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("cdecoder execution timed out after 30 seconds")
            return False
        except Exception as e:
            logger.error(f"Error running cdecoder: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False

    def _convert_raw_to_wav(self, raw_file, wav_file):
        """Convert cdecoder raw output (with BFI) to WAV."""
        try:
            import wave
            
            with open(raw_file, 'rb') as f:
                raw_data = f.read()
            
            # Format: BFI (2 bytes) + 137 shorts (274 bytes)
            block_size = 276
            pcm_data = bytearray()
            
            for i in range(0, len(raw_data), block_size):
                if i + block_size <= len(raw_data):
                    # Skip first 2 bytes (BFI), take next 274 bytes
                    pcm_data.extend(raw_data[i+2 : i+276])
            
            with wave.open(str(wav_file), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(pcm_data)
                
            logger.info(f"[OK] Converted to WAV: {wav_file}")
            
        except Exception as e:
            logger.error(f"Error converting to WAV: {e}")
    
    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        
        logger.info(f"\nFrequencies Found: {len(self.test_results['frequencies_found'])}")
        for ch in self.test_results['frequencies_found']:
            logger.info(f"  - {ch['frequency']/1e6:.3f} MHz")
        
        logger.info(f"\nText Messages (SDS): {len(self.test_results['text_messages'])}")
        for msg in self.test_results['text_messages']:
            # Sanitize message for console output (handle encoding errors)
            safe_msg = msg['message'].encode('ascii', 'replace').decode('ascii')
            logger.info(f"  [{msg['time']}] {safe_msg}")
        
        logger.info(f"\nVoice Recordings: {len(self.test_results['voice_frames'])}")
        for vf in self.test_results['voice_frames']:
            logger.info(f"  - {vf['frequency']/1e6:.3f} MHz: {vf['count']} frames, {vf['samples']} samples")
            logger.info(f"    Raw: {vf['raw_file']}")
            logger.info(f"    Audio: {vf['audio_file']}")
        
        logger.info("\n" + "=" * 60)
        
        # Success criteria
        has_text = len(self.test_results['text_messages']) > 0
        has_voice = len(self.test_results['voice_frames']) > 0 and any(vf['count'] > 0 for vf in self.test_results['voice_frames'])
        
        if has_text and has_voice:
            logger.info("[SUCCESS] Both TEXT and VOICE decoded!")
        elif has_text:
            logger.info("[PARTIAL] TEXT decoded, but no VOICE")
        elif has_voice:
            logger.info("[PARTIAL] VOICE decoded, but no TEXT")
        else:
            logger.info("[FAIL] No TEXT or VOICE decoded")
        
        logger.info("=" * 60 + "\n")
    
    def cleanup(self):
        """Cleanup resources."""
        if self.capture:
            try:
                self.capture.close()
            except:
                pass


def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated TETRA Testing')
    parser.add_argument('--freq', type=float, default=390.865, help='Specific frequency in MHz to test (default: 390.865)')
    parser.add_argument('--scan-start', type=float, default=390.0, help='Scan start frequency (MHz)')
    parser.add_argument('--scan-end', type=float, default=395.0, help='Scan end frequency (MHz)')
    parser.add_argument('--duration', type=float, default=10.0, help='Recording duration per frequency (seconds)')
    parser.add_argument('--no-scan', action='store_true', help='Skip frequency scanning')
    parser.add_argument('--sample-rate', type=float, default=2.4, help='Sample rate in MHz (default: 2.4)')
    parser.add_argument('--gain', type=int, default=50, help='RTL-SDR gain setting (default: 50)')
    parser.add_argument('--noise-floor', type=float, default=-45, help='Noise floor in dB (default: -45)')
    parser.add_argument('--bottom', type=float, default=-85, help='Bottom threshold in dB (default: -85)')
    
    args = parser.parse_args()
    
    tester = AutoTester(
        sample_rate=args.sample_rate * 1e6,
        default_gain=args.gain,
        noise_floor=args.noise_floor,
        bottom_threshold=args.bottom
    )
    
    try:
        # Step 1: Find frequencies
        frequencies_to_test = []
        
        if args.freq:
            frequencies_to_test = [args.freq * 1e6]
            logger.info(f"Testing specific frequency: {args.freq} MHz")
        elif not args.no_scan:
            found = tester.find_frequencies(
                start_freq=args.scan_start * 1e6,
                end_freq=args.scan_end * 1e6,
                step=25e3,
                dwell_time=0.5
            )
            frequencies_to_test = [ch['frequency'] for ch in found]
        else:
            # Default test frequency (390.865 MHz per user specification)
            frequencies_to_test = [args.freq * 1e6]
            logger.info(f"No scan requested, using default: {frequencies_to_test[0]/1e6:.3f} MHz")
        
        if not frequencies_to_test:
            logger.warning("No frequencies found or specified. Exiting.")
            return
        
        # Step 2: Record and decode at each frequency
        for freq in frequencies_to_test:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing frequency: {freq/1e6:.3f} MHz")
            logger.info(f"{'='*60}\n")
            
            success = tester.record_and_decode(freq, duration=args.duration)
            
            if success:
                logger.info(f"[OK] Successfully recorded and decoded at {freq/1e6:.3f} MHz")
            else:
                logger.warning(f"[WARN] Limited success at {freq/1e6:.3f} MHz")
            
            # Brief pause between frequencies
            if len(frequencies_to_test) > 1:
                time.sleep(2)
        
        # Step 3: Print summary
        tester.print_summary()
        
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        tester.cleanup()


if __name__ == '__main__':
    main()
