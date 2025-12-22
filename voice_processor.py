"""
TETRA Voice Processor
Handles TETRA voice decoding using external cdecoder.exe.
"""

import os
import logging
import subprocess
import tempfile
import numpy as np

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """
    Handles TETRA voice decoding using external cdecoder.exe.
    """
    def __init__(self):
        self.codec_path = os.path.join(os.path.dirname(__file__), "tetra_codec", "bin", "cdecoder.exe")
        self.working = os.path.exists(self.codec_path)
        if not self.working:
            logger.warning(f"TETRA codec not found at {self.codec_path}")
        else:
            logger.debug(f"TETRA codec found at {self.codec_path}")
            
    def decode_frame(self, frame_data: bytes) -> np.ndarray:
        """
        Decode ACELP frame to PCM audio.
        cdecoder expects binary format: 690 shorts (16-bit integers)
        - First short: 0x6B21 (header marker)
        - Next 689 shorts: Frame data (soft bits as 16-bit values)
        """
        if not self.working or not frame_data:
            return np.zeros(0)
            
        try:
            import struct
            
            # frame_data should already be in correct format (1380 bytes = 690 shorts)
            # Verify frame size
            if len(frame_data) != 1380:
                logger.debug(f"Invalid frame size: {len(frame_data)} bytes (expected 1380)")
                return np.zeros(0)
            
            # Verify header
            header = struct.unpack('<H', frame_data[0:2])[0]
            if header != 0x6B21:
                logger.debug(f"Invalid header: 0x{header:04X} (expected 0x6B21)")
                return np.zeros(0)
            
            # Write frame to temp file (binary) - already in correct format
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.tet') as tmp_in:
                tmp_in.write(frame_data)
                tmp_in_path = tmp_in.name
                
            tmp_out_path = tmp_in_path + ".out"
            
            # Log input data stats
            input_shorts = np.frombuffer(frame_data, dtype=np.int16)
            logger.debug(f"Codec input: {len(input_shorts)} shorts, Max: {np.max(np.abs(input_shorts))}, Header: 0x{input_shorts[0]:04X}")
            logger.debug(f"Codec input file: {tmp_in_path}")
            
            logger.debug(f"Calling codec: {self.codec_path} {tmp_in_path} {tmp_out_path}")
            
            # Run decoder
            # cdecoder.exe input output
            # It might be that cdecoder doesn't like the temp file paths or permissions?
            # Or maybe it needs to be run from its directory?
            
            codec_dir = os.path.dirname(self.codec_path)
            codec_exe = os.path.basename(self.codec_path)
            
            # Use absolute paths for input/output
            abs_in = os.path.abspath(tmp_in_path)
            abs_out = os.path.abspath(tmp_out_path)
            
            # Try shell=False with absolute paths and no cwd
            result = subprocess.run([self.codec_path, abs_in, abs_out], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE,
                          check=False,
                          timeout=5)
            
            # Log codec process output
            if result.stdout:
                logger.debug(f"Codec STDOUT: {result.stdout.decode('utf-8', errors='ignore').strip()}")
            if result.stderr:
                logger.debug(f"Codec STDERR: {result.stderr.decode('utf-8', errors='ignore').strip()}")
            
            if result.returncode != 0:
                logger.debug(f"Codec failed with return code {result.returncode}")
            
            # Read output
            if os.path.exists(tmp_out_path) and os.path.getsize(tmp_out_path) > 0:
                output_size = os.path.getsize(tmp_out_path)
                logger.debug(f"Codec output file: {tmp_out_path} ({output_size} bytes)")
                
                with open(tmp_out_path, 'rb') as f:
                    pcm_data = f.read()
                
                # Output format: BFI (2 bytes) + 137 shorts (274 bytes) + BFI (2 bytes) + 137 shorts (274 bytes)
                # Total: 552 bytes for 2 speech frames
                if len(pcm_data) >= 552:
                    # Skip BFI bytes and extract PCM samples
                    # Read as 16-bit signed integers
                    pcm_samples1 = np.frombuffer(pcm_data[2:276], dtype=np.int16)
                    pcm_samples2 = np.frombuffer(pcm_data[278:552], dtype=np.int16)
                    # Combine both frames
                    audio = np.concatenate([pcm_samples1, pcm_samples2]).astype(np.float32) / 32768.0
                    
                    # Check if audio is silent
                    max_amp = np.max(np.abs(audio))
                    if max_amp == 0:
                        logger.debug("Codec produced silent audio")
                    else:
                        logger.debug(f"Codec produced audio with max amp {max_amp:.4f}")
                    
                    # Cleanup
                    try:
                        # os.remove(tmp_in_path)
                        # os.remove(tmp_out_path)
                        pass
                    except:
                        pass
                    
                    if len(audio) > 0:
                        logger.info(f"Decoded {len(audio)} audio samples from voice frame")
                        return audio
                elif len(pcm_data) > 0:
                    # Try to read whatever we got
                    audio = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
                    if len(audio) > 0:
                        logger.debug(f"Decoded {len(audio)} audio samples (partial)")
                        # Cleanup
                        try:
                            # os.remove(tmp_in_path)
                            # os.remove(tmp_out_path)
                            pass
                        except:
                            pass
                        return audio
                
                # Cleanup if no valid audio
                try:
                    # os.remove(tmp_in_path)
                    # os.remove(tmp_out_path)
                    pass
                except:
                    pass
                return np.zeros(0)
            else:
                logger.debug(f"Codec produced no output file or empty file (return code: {result.returncode})")
                try:
                    os.remove(tmp_in_path)
                    if os.path.exists(tmp_out_path):
                        os.remove(tmp_out_path)
                except:
                    pass
                return np.zeros(0)
                
        except Exception as e:
            logger.debug(f"Voice decode error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return np.zeros(0)
