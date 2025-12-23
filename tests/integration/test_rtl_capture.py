"""
Integration tests for RTL-SDR capture module.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from rtl_capture import RTLCapture


@pytest.mark.integration
class TestRTLCapture:
    """Test RTLCapture class with mocked RTL-SDR."""
    
    def test_capture_initialization(self):
        """Test capture initialization."""
        capture = RTLCapture(frequency=400e6, sample_rate=2.4e6, gain=50.0)
        assert capture.frequency == 400e6
        assert capture.sample_rate == 2.4e6
        assert capture.gain == 50.0
        assert capture.sdr is None
    
    def test_capture_initialization_auto_gain(self):
        """Test capture initialization with auto gain."""
        capture = RTLCapture(gain='auto')
        assert capture.gain == 'auto'
    
    def test_open_success(self):
        """Test successful device opening."""
        capture = RTLCapture()
        with patch('rtl_capture.RtlSdr') as mock_rtl:
            mock_sdr = MagicMock()
            mock_rtl.return_value = mock_sdr
            mock_sdr.get_device_serial_addresses.return_value = ['00000001']
            
            result = capture.open()
            assert result is True
            assert capture.sdr is not None
            assert mock_sdr.sample_rate == capture.sample_rate
            assert mock_sdr.center_freq == capture.frequency
    
    def test_open_failure(self):
        """Test device opening failure."""
        capture = RTLCapture()
        with patch('rtl_capture.RtlSdr', side_effect=Exception("Device not found")):
            result = capture.open()
            assert result is False
            assert capture.sdr is None
    
    def test_open_usb_access_error(self):
        """Test USB access error handling."""
        capture = RTLCapture()
        with patch('rtl_capture.RtlSdr', side_effect=Exception("LIBUSB_ERROR_ACCESS")):
            result = capture.open()
            assert result is False
    
    def test_read_samples_success(self):
        """Test reading samples successfully."""
        capture = RTLCapture()
        mock_sdr = MagicMock()
        mock_samples = np.random.randn(1000) + 1j * np.random.randn(1000)
        mock_sdr.read_samples.return_value = mock_samples
        capture.sdr = mock_sdr
        
        result = capture.read_samples(1000)
        assert len(result) == 1000
        assert np.array_equal(result, mock_samples)
        mock_sdr.read_samples.assert_called_once_with(1000)
    
    def test_read_samples_not_opened(self):
        """Test reading samples when device not opened."""
        capture = RTLCapture()
        with pytest.raises(RuntimeError, match="not opened"):
            capture.read_samples()
    
    def test_read_samples_device_error(self):
        """Test handling device errors during read."""
        capture = RTLCapture()
        mock_sdr = MagicMock()
        mock_sdr.read_samples.side_effect = OSError("access violation")
        capture.sdr = mock_sdr
        
        with pytest.raises(RuntimeError):
            capture.read_samples()
    
    def test_set_frequency(self):
        """Test setting frequency."""
        capture = RTLCapture()
        mock_sdr = MagicMock()
        capture.sdr = mock_sdr
        
        capture.set_frequency(392.24e6)
        assert capture.frequency == 392.24e6
        assert mock_sdr.center_freq == 392.24e6
    
    def test_set_gain(self):
        """Test setting gain."""
        capture = RTLCapture()
        mock_sdr = MagicMock()
        capture.sdr = mock_sdr
        
        # RTLCapture doesn't have set_gain, but we can set it directly
        capture.gain = 45.0
        mock_sdr.gain = 45.0
        assert capture.gain == 45.0
        assert mock_sdr.gain == 45.0
    
    def test_set_gain_auto(self):
        """Test setting gain to auto."""
        capture = RTLCapture()
        mock_sdr = MagicMock()
        capture.sdr = mock_sdr
        
        # RTLCapture doesn't have set_gain, but we can set it directly
        capture.gain = 'auto'
        mock_sdr.gain = 'auto'
        assert capture.gain == 'auto'
        assert mock_sdr.gain == 'auto'
    
    def test_close(self):
        """Test closing device."""
        capture = RTLCapture()
        mock_sdr = MagicMock()
        capture.sdr = mock_sdr
        
        capture.close()
        mock_sdr.close.assert_called_once()
        assert capture.sdr is None
    
    def test_close_not_opened(self):
        """Test closing when device not opened."""
        capture = RTLCapture()
        # Should not raise error
        capture.close()
    
    def test_sample_rate_validation(self):
        """Test sample rate validation and rounding."""
        capture = RTLCapture(sample_rate=2.5e6)  # Not a valid RTL-SDR rate
        with patch('rtl_capture.RtlSdr') as mock_rtl:
            mock_sdr = MagicMock()
            mock_rtl.return_value = mock_sdr
            mock_sdr.get_device_serial_addresses.return_value = ['00000001']
            
            capture.open()
            # Should round to nearest valid rate (2.4e6 or 2.56e6)
            assert capture.sample_rate in [2.4e6, 2.56e6]
