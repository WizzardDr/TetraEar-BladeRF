"""
Pytest configuration and shared fixtures.
"""

import pytest
import numpy as np
import struct
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_tetra_frame_binary():
    """
    Create a sample TETRA frame in binary format.
    Format: 690 shorts (16-bit integers)
    - First short: 0x6B21 (header marker)
    - Next 689 shorts: Frame data (soft bits as 16-bit values)
    """
    frame = bytearray()
    
    # Header: 0x6B21 (little endian for Windows)
    frame.extend(struct.pack('<H', 0x6B21))
    
    # Fill with soft bits: values should be in range -127 to 127
    # For testing, use small values (0-127) representing soft bits
    for i in range(689):
        # Soft bit value (signed 16-bit)
        soft_bit = (i % 2) * 64  # 0 or 64
        frame.extend(struct.pack('<h', soft_bit))
    
    return bytes(frame)


@pytest.fixture
def sample_tetra_bits():
    """Sample TETRA frame as bit array (510 bits)."""
    # TETRA frame sync pattern + data
    sync_pattern = [0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0,
                    1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0]
    # Fill rest with test data
    data_bits = [i % 2 for i in range(510 - len(sync_pattern))]
    return sync_pattern + data_bits


@pytest.fixture
def sample_iq_samples():
    """Sample IQ data for signal processing tests."""
    # Generate complex IQ samples (simulated TETRA signal)
    sample_rate = 2.4e6
    duration = 0.01  # 10ms
    t = np.arange(0, duration, 1/sample_rate)
    
    # Simulate π/4-DQPSK modulated signal
    frequency = 0  # Baseband
    iq = np.exp(1j * 2 * np.pi * frequency * t)
    
    # Add some noise
    noise = (np.random.randn(len(iq)) + 1j * np.random.randn(len(iq))) * 0.1
    return iq + noise


@pytest.fixture
def mock_rtl_sdr():
    """Mock RTL-SDR device for testing."""
    mock_device = MagicMock()
    mock_device.sample_rate = 2.4e6
    mock_device.center_freq = 392.24e6
    mock_device.gain = 50.0
    mock_device.read_samples.return_value = np.random.randn(1000) + 1j * np.random.randn(1000)
    return mock_device


@pytest.fixture
def mock_codec_path(tmp_path):
    """Create a mock codec directory structure."""
    codec_dir = tmp_path / "tetra_codec" / "bin"
    codec_dir.mkdir(parents=True)
    
    # Create mock codec executables (empty files for testing)
    for codec in ["cdecoder.exe", "ccoder.exe", "sdecoder.exe", "scoder.exe"]:
        (codec_dir / codec).touch()
    
    return codec_dir


@pytest.fixture
def temp_codec_file(tmp_path):
    """Create a temporary codec input file."""
    codec_file = tmp_path / "test_codec_input.tet"
    # Write sample TETRA frame
    frame = bytearray()
    frame.extend(struct.pack('<H', 0x6B21))
    for i in range(689):
        frame.extend(struct.pack('<h', (i % 2) * 64))
    codec_file.write_bytes(bytes(frame))
    return codec_file


@pytest.fixture
def sample_encrypted_frame():
    """Sample encrypted TETRA frame data."""
    # 64-bit encrypted block (8 bytes)
    return bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0])


@pytest.fixture
def sample_tea1_key():
    """Sample TEA1 key (80-bit, 10 bytes)."""
    return bytes([0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99])


@pytest.fixture
def sample_tea2_key():
    """Sample TEA2 key (128-bit, 16 bytes)."""
    return bytes([0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
                  0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])


@pytest.fixture
def sample_mac_pdu():
    """Sample MAC PDU data."""
    # MAC-RESOURCE PDU structure
    pdu_data = bytes([
        0x00,  # PDU type (MAC_RESOURCE)
        0x01,  # Encrypted flag
        0x12, 0x34,  # Address
        0x10,  # Length
    ] + [0xAA] * 16)  # Data
    return pdu_data


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration before each test."""
    import logging
    logging.root.handlers = []
    logging.root.setLevel(logging.WARNING)
    yield
    logging.root.handlers = []


@pytest.fixture
def project_root_path():
    """Return the project root directory."""
    return Path(__file__).parent.parent
