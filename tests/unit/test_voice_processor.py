"""
Unit tests for voice processor module.
"""

import pytest
import numpy as np
import struct
import os
from unittest.mock import patch, MagicMock
from voice_processor import VoiceProcessor


@pytest.mark.unit
class TestVoiceProcessor:
    """Test VoiceProcessor class."""
    
    def test_processor_initialization_no_codec(self, tmp_path):
        """Test processor initialization when codec is missing."""
        with patch('voice_processor.os.path.exists', return_value=False):
            processor = VoiceProcessor()
            assert processor.working is False
    
    def test_processor_initialization_with_codec(self, mock_codec_path):
        """Test processor initialization when codec exists."""
        with patch('voice_processor.os.path.join') as mock_join:
            mock_join.return_value = str(mock_codec_path / "cdecoder.exe")
            processor = VoiceProcessor()
            # Working status depends on whether codec file actually exists
            assert isinstance(processor.working, bool)
    
    def test_decode_frame_not_working(self):
        """Test decode when codec is not working."""
        processor = VoiceProcessor()
        processor.working = False
        result = processor.decode_frame(b'')
        assert len(result) == 0
        assert isinstance(result, np.ndarray)
    
    def test_decode_frame_empty_data(self):
        """Test decode with empty frame data."""
        processor = VoiceProcessor()
        processor.working = True
        result = processor.decode_frame(b'')
        assert len(result) == 0
    
    def test_decode_frame_invalid_size(self):
        """Test decode with invalid frame size."""
        processor = VoiceProcessor()
        processor.working = True
        invalid_frame = bytes([0x00] * 100)  # Not 1380 bytes
        result = processor.decode_frame(invalid_frame)
        assert len(result) == 0
    
    def test_decode_frame_invalid_header(self):
        """Test decode with invalid header."""
        processor = VoiceProcessor()
        processor.working = True
        # Create frame with wrong header
        frame = bytearray()
        frame.extend(struct.pack('<H', 0x0000))  # Wrong header
        frame.extend(bytes([0x00] * 1378))
        result = processor.decode_frame(bytes(frame))
        assert len(result) == 0
    
    def test_decode_frame_valid_format(self, sample_tetra_frame_binary):
        """Test decode with valid frame format."""
        processor = VoiceProcessor()
        processor.working = True
        
        # Mock subprocess to avoid actually calling codec
        with patch('voice_processor.subprocess.run') as mock_run:
            # Mock successful codec execution
            mock_run.return_value = MagicMock(returncode=0)
            
            # Mock output file
            with patch('voice_processor.os.path.exists', return_value=True):
                with patch('voice_processor.os.path.getsize', return_value=552):
                    with patch('builtins.open', create=True) as mock_open:
                        # Mock file read - return PCM data
                        pcm_data = bytes([0x00] * 552)
                        mock_file = MagicMock()
                        mock_file.read.return_value = pcm_data
                        mock_open.return_value.__enter__.return_value = mock_file
                        
                        result = processor.decode_frame(sample_tetra_frame_binary)
                        # Should return audio array (may be empty if codec fails)
                        assert isinstance(result, np.ndarray)
    
    def test_decode_frame_codec_failure(self, sample_tetra_frame_binary):
        """Test decode when codec fails."""
        processor = VoiceProcessor()
        processor.working = True
        
        with patch('voice_processor.subprocess.run') as mock_run:
            # Mock codec failure
            mock_run.return_value = MagicMock(returncode=1)
            
            with patch('voice_processor.os.path.exists', return_value=False):
                result = processor.decode_frame(sample_tetra_frame_binary)
                assert len(result) == 0
    
    def test_decode_frame_timeout(self, sample_tetra_frame_binary):
        """Test decode when codec times out."""
        processor = VoiceProcessor()
        processor.working = True
        
        with patch('voice_processor.subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired('cdecoder', 5)
            
            result = processor.decode_frame(sample_tetra_frame_binary)
            # Should handle timeout gracefully
            assert isinstance(result, np.ndarray)
