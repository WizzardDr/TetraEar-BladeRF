"""
Unit tests for voice processor module.
"""

import pytest
import numpy as np
import struct
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from tetraear.audio.voice import VoiceProcessor


@pytest.mark.unit
class TestVoiceProcessor:
    """Test VoiceProcessor class."""
    
    def test_processor_initialization_no_codec(self, tmp_path):
        """Test processor initialization when codec is missing."""
        processor = VoiceProcessor(codec_path=tmp_path / "missing_cdecoder.exe")
        assert processor.working is False
    
    def test_processor_initialization_with_codec(self, mock_codec_path):
        """Test processor initialization when codec exists."""
        processor = VoiceProcessor(codec_path=mock_codec_path / "cdecoder.exe")
        assert processor.working is True
    
    def test_decode_frame_not_working(self):
        """Test decode when codec is not working."""
        processor = VoiceProcessor(codec_path="C:/this/path/does/not/exist.exe")
        result = processor.decode_frame(b'')
        assert len(result) == 0
        assert isinstance(result, np.ndarray)
    
    def test_decode_frame_empty_data(self, tmp_path):
        """Test decode with empty frame data."""
        codec = tmp_path / "cdecoder.exe"
        codec.write_bytes(b"")
        processor = VoiceProcessor(codec_path=codec)
        result = processor.decode_frame(b'')
        assert len(result) == 0
    
    def test_decode_frame_invalid_size(self, tmp_path):
        """Test decode with invalid frame size."""
        codec = tmp_path / "cdecoder.exe"
        codec.write_bytes(b"")
        processor = VoiceProcessor(codec_path=codec)
        invalid_frame = bytes([0x00] * 100)  # Not 1380 bytes
        result = processor.decode_frame(invalid_frame)
        assert len(result) == 0
    
    def test_decode_frame_invalid_header(self, tmp_path):
        """Test decode with invalid header."""
        codec = tmp_path / "cdecoder.exe"
        codec.write_bytes(b"")
        processor = VoiceProcessor(codec_path=codec)
        # Create frame with wrong header
        frame = bytearray()
        frame.extend(struct.pack('<H', 0x0000))  # Wrong header
        frame.extend(bytes([0x00] * 1378))
        result = processor.decode_frame(bytes(frame))
        assert len(result) == 0
    
    def test_decode_frame_valid_format(self, sample_tetra_frame_binary, tmp_path):
        """Test decode with valid frame format."""
        codec_dir = tmp_path / "tetra_codec" / "bin"
        codec_dir.mkdir(parents=True, exist_ok=True)
        (codec_dir / "cdecoder.exe").write_bytes(b"")
        (codec_dir / "sdecoder.exe").write_bytes(b"")
        processor = VoiceProcessor(codec_dir=codec_dir)
        
        # Mock subprocess to avoid actually calling codec
        with patch('tetraear.audio.voice.subprocess.run') as mock_run:
            def _side_effect(args, stdout=None, stderr=None, check=None, timeout=None):
                # args: [exe, in, out]
                exe = os.path.basename(str(args[0])).lower()
                out_path = str(args[2])
                if "cdecoder" in exe:
                    # Write dummy serial bits output (e.g., 2 frames * 138 int16)
                    Path(out_path).write_bytes(bytes([0x00] * 552))
                    return MagicMock(returncode=0, stdout=b"", stderr=b"")
                if "sdecoder" in exe:
                    # Write dummy synth output (int16 samples)
                    samples = (np.ones(320, dtype=np.int16) * 1000).tobytes()
                    Path(out_path).write_bytes(samples)
                    return MagicMock(returncode=0, stdout=b"", stderr=b"")
                return MagicMock(returncode=1, stdout=b"", stderr=b"")

            mock_run.side_effect = _side_effect

            result = processor.decode_frame(sample_tetra_frame_binary)
            assert isinstance(result, np.ndarray)
            assert result.size > 0
    
    def test_decode_frame_codec_failure(self, sample_tetra_frame_binary, tmp_path):
        """Test decode when codec fails."""
        codec_dir = tmp_path / "tetra_codec" / "bin"
        codec_dir.mkdir(parents=True, exist_ok=True)
        (codec_dir / "cdecoder.exe").write_bytes(b"")
        (codec_dir / "sdecoder.exe").write_bytes(b"")
        processor = VoiceProcessor(codec_dir=codec_dir)
        
        with patch('tetraear.audio.voice.subprocess.run') as mock_run:
            # Mock codec failure
            mock_run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"")
            result = processor.decode_frame(sample_tetra_frame_binary)
            assert len(result) == 0
    
    def test_decode_frame_timeout(self, sample_tetra_frame_binary, tmp_path):
        """Test decode when codec times out."""
        codec_dir = tmp_path / "tetra_codec" / "bin"
        codec_dir.mkdir(parents=True, exist_ok=True)
        (codec_dir / "cdecoder.exe").write_bytes(b"")
        (codec_dir / "sdecoder.exe").write_bytes(b"")
        processor = VoiceProcessor(codec_dir=codec_dir)
        
        with patch('tetraear.audio.voice.subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired('cdecoder', 5)
            
            result = processor.decode_frame(sample_tetra_frame_binary)
            # Should handle timeout gracefully
            assert isinstance(result, np.ndarray)
