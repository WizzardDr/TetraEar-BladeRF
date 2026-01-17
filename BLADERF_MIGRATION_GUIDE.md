# Migrating TetraEar from RTL-SDR to BladeRF

## Overview

This guide outlines the modifications needed to convert TetraEar from RTL-SDR to BladeRF hardware. The codebase is well-structured with hardware abstraction primarily in the signal capture module, making this migration relatively straightforward.

## Key Changes Required

### 1. **Dependencies** (`requirements.txt`)

**Current:**
```plaintext
pyrtlsdr>=0.2.9
```

**Replace with:**
```plaintext
bladerf>=1.0.0
libusb>=1.2.1
```

BladeRF uses libusb for USB communication. The `bladerf` Python package is the official wrapper.

---

### 2. **Hardware Abstraction Layer** (`tetraear/signal/capture.py`)

This is the **primary file** requiring modification. The current `RTLCapture` class must be replaced or refactored to support BladeRF.

#### Option A: Replace the Class (Recommended)

Replace the `RTLCapture` class with a `BladeRFCapture` class that maintains the same interface:

**Key changes:**
- Import `bladerf` instead of `rtlsdr`
- Update initialization to configure BladeRF-specific parameters:
  - RX channel setup
  - Sample rate validation (BladeRF supports different ranges)
  - Gain handling (BladeRF uses different gain modes: `Default`, `Bypass`, `Manual`)
  - Enable TX bias (if supported) instead of bias tee

**BladeRF-specific considerations:**
```python
from bladerf import RxChannel, TxChannel, ChannelMode, GainMode

class BladeRFCapture:
    """Handles BladeRF device configuration and signal capture."""
    
    def __init__(self, frequency=400e6, sample_rate=1.8e6, gain='auto'):
        # BladeRF supports: 160 kHz - 40 MHz (RX mode)
        # Different sample rates depending on clock source
        # Gain: 0-60 dB (depends on gain mode)
        pass
    
    def open(self):
        # 1. Open BladeRF device
        # 2. Configure RX channel
        # 3. Set sample rate (BladeRF may auto-adjust)
        # 4. Set gain mode (Manual, Default, Bypass)
        # 5. Set center frequency
        # 6. Start RX streaming
        pass
    
    def read_samples(self, num_samples):
        # Use BladeRF's rx_samples or rx_stream
        pass
```

#### Option B: Create an Abstract Interface (More Scalable)

Create a base `SDRCapture` class and implement hardware-specific subclasses:

```python
from abc import ABC, abstractmethod

class SDRCapture(ABC):
    """Abstract base class for SDR hardware."""
    
    @abstractmethod
    def open(self) -> bool: ...
    
    @abstractmethod
    def read_samples(self, num_samples: int) -> np.ndarray: ...
    
    @abstractmethod
    def set_frequency(self, frequency: float) -> None: ...
    
    @abstractmethod
    def close(self) -> None: ...

class RTLCapture(SDRCapture):
    # Existing implementation
    pass

class BladeRFCapture(SDRCapture):
    # New implementation
    pass
```

This allows easy switching and future hardware support.

---

### 3. **UI Updates** (`tetraear/ui/modern.py`)

Search for `RTLCapture` imports and instantiations (approximately 4 locations):

**Lines to update:**
- ~193: Import statement
- ~1641-1645: Frequency scanning (test mode)
- ~1868-1872: Main capture initialization
- ~5456-5462: Another frequency scanning instance

**Changes:**
```python
# OLD:
from tetraear.signal.capture import RTLCapture
self.capture = RTLCapture(frequency=self.frequency, ...)

# NEW (if keeping same class name):
from tetraear.signal.capture import BladeRFCapture
self.capture = BladeRFCapture(frequency=self.frequency, ...)

# NEW (if using abstract interface):
from tetraear.signal.capture import get_sdr_capture
self.capture = get_sdr_capture('bladerf')(frequency=self.frequency, ...)
```

**Error messages to update:**
- Line ~1870: "Failed to open RTL-SDR" → "Failed to open BladeRF"
- Status messages referencing RTL-SDR

---

### 4. **CLI Tools** (3 files need updates)

#### a. `continuous_capture.py` (lines 12, 30, 32)
```python
# Replace RTLCapture with BladeRFCapture
from tetraear.signal.capture import BladeRFCapture
capture = BladeRFCapture(...)
print("[FAIL] Could not open BladeRF")
```

#### b. `tetraear/tools/rtl_auto_capture.py` (lines 21, 145)
```python
from tetraear.signal.capture import BladeRFCapture
capture = BladeRFCapture(...)
```

#### c. `tetraear/__init__.py` (lines 30, 44)
Update imports to reference `BladeRFCapture` or use dynamic factory

```python
# Option 1: Direct import
"BladeRFCapture",

# Option 2: Factory pattern
elif name == "BladeRFCapture":
    from tetraear.signal.capture import BladeRFCapture
    return BladeRFCapture
```

---

### 5. **Documentation Updates**

Update these files to reference BladeRF:

- **README.md**: 
  - Change "RTL-SDR with real-time voice decoding" to "BladeRF..."
  - Update requirements section
  - Update installation section

- **BUILD_INSTRUCTIONS.md**:
  - Update PyInstaller hidden imports if needed
  - Update DLL references (BladeRF uses different DLLs)

- **requirements.txt**:
  - Already covered above

---

## BladeRF Technical Differences

### Sample Rate Considerations

**RTL-SDR valid rates:**
- 0.225, 0.9, 1.024, 1.536, 1.8, 1.92, 2.048, 2.4, 2.56, 2.88, 3.2 MHz

**BladeRF valid rates:**
- Depends on architecture (x40, x115, Micro)
- Generally: 160 kHz - 40 MHz
- Common rates: 1 MHz, 1.8 MHz, 2.4 MHz, 5 MHz (some adjustable)
- Needs validation similar to RTL-SDR

### Gain Handling

**RTL-SDR:**
- String 'auto' or numeric value (0-49 dB)

**BladeRF:**
- Gain modes: `Default`, `Bypass`, `Manual`
- Range with Manual: 0-60 dB
- May require updating UI gain slider

### Frequency Range

**RTL-SDR:**
- 24 MHz - 1.7 GHz (varies by dongle)

**BladeRF:**
- x40/x115: 300 MHz - 3.8 GHz
- Micro: 70 MHz - 6 GHz
- Generally better for TETRA frequencies (380-400 MHz in EU)

### USB/Driver Differences

**RTL-SDR:**
- Requires WinUSB driver (Zadig)
- Error handling for LIBUSB_ERROR_ACCESS

**BladeRF:**
- Requires libusb (pre-installed on most Linux)
- Windows: May need WinUSB or bladerf-specific drivers
- Update error handling and driver installation docs

---

## Implementation Checklist

- [ ] Create BladeRFCapture class in `tetraear/signal/capture.py`
- [ ] Update imports in `tetraear/ui/modern.py` (4 locations)
- [ ] Update `continuous_capture.py`
- [ ] Update `tetraear/tools/rtl_auto_capture.py`
- [ ] Update `tetraear/__init__.py` exports
- [ ] Update `tetraear/signal/__init__.py` exports
- [ ] Update README.md
- [ ] Update BUILD_INSTRUCTIONS.md
- [ ] Update requirements.txt
- [ ] Update error messages and logging
- [ ] Test on actual BladeRF hardware
- [ ] Update test mocks if needed (`tests/conftest.py`, `tests/integration/test_frequency_scanner.py`)

---

## Sample BladeRFCapture Implementation

Here's a basic template for the new class:

```python
"""
BladeRF signal capture module for TETRA decoding.
"""

import numpy as np
import logging
from typing import Optional

try:
    import bladerf
    BLADERF_AVAILABLE = True
except ImportError:
    BLADERF_AVAILABLE = False
    bladerf = None

logger = logging.getLogger(__name__)

class BladeRFCapture:
    """Handles BladeRF device configuration and signal capture."""
    
    def __init__(self, frequency=400e6, sample_rate=1.8e6, gain='auto'):
        """
        Initialize BladeRF capture.
        
        Args:
            frequency: Center frequency in Hz
            sample_rate: Sample rate in Hz
            gain: Gain setting ('auto' or numeric value 0-60 dB)
        """
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.device = None
        self.channel = None
    
    def open(self) -> bool:
        """
        Open and configure BladeRF device.
        
        Returns:
            bool: True if device opened successfully
        """
        if not BLADERF_AVAILABLE:
            logger.error("BladeRF library not available")
            return False
        
        try:
            # Open first available BladeRF
            self.device = bladerf.open()
            
            # Configure RX channel
            self.channel = self.device.Channel.RX(0)  # RX channel 0
            
            # Set sample rate
            self.channel.sample_rate = self.sample_rate
            
            # Set center frequency
            self.channel.frequency = self.frequency
            
            # Set gain mode and value
            if isinstance(self.gain, str) and self.gain.lower() == 'auto':
                self.channel.gain_mode = bladerf.GainMode.Default
            else:
                self.channel.gain_mode = bladerf.GainMode.Manual
                self.channel.gain = float(self.gain)
            
            # Enable RX
            self.device.sync_config(
                bladerf.ChannelMode.RX_TX,
                bladerf.Format.CS16,
                16,  # buffer_size
                8,   # num_buffers
                8,   # num_transfers
                8    # timeout_ms
            )
            
            logger.info(f"BladeRF opened successfully")
            logger.info(f"Frequency: {self.frequency/1e6:.2f} MHz")
            logger.info(f"Sample rate: {self.sample_rate/1e6:.2f} MHz")
            logger.info(f"Gain: {self.gain}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to open BladeRF: {e}")
            return False
    
    def read_samples(self, num_samples=1024*1024) -> np.ndarray:
        """
        Read samples from BladeRF.
        
        Args:
            num_samples: Number of samples to read
            
        Returns:
            Complex numpy array of samples
        """
        if self.device is None:
            raise RuntimeError("BladeRF device not opened")
        
        try:
            # Read RX samples
            samples = self.device.sync_rx(num_samples)
            return samples
        except Exception as e:
            logger.error(f"Failed to read samples: {e}")
            raise
    
    def set_frequency(self, frequency: float):
        """
        Change center frequency.
        
        Args:
            frequency: New center frequency in Hz
        """
        if self.device is None:
            raise RuntimeError("BladeRF device not opened")
        
        try:
            self.frequency = frequency
            self.channel.frequency = frequency
            logger.debug(f"Frequency changed to {frequency/1e6:.3f} MHz")
        except Exception as e:
            logger.error(f"Failed to set frequency: {e}")
            raise
    
    def close(self):
        """Close BladeRF device."""
        if self.device is not None:
            try:
                self.device.close()
            except:
                pass
            self.device = None
            logger.info("BladeRF device closed")
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
```

---

## Testing Considerations

- Update mock fixtures to simulate BladeRF behavior
- Add BladeRF-specific sample rate validation tests
- Test gain mode switching
- Verify frequency setting range (TETRA band: 380-400 MHz)
- Test USB connection/disconnection handling

---

## Hardware-Specific Notes

### BladeRF x40 (Most Common)
- 40 MHz dual-channel transceiver
- Good for TETRA (EU: 380-400 MHz)
- Requires external LNA for weak signal reception

### BladeRF Micro
- Smaller, more recent variant
- Better sensitivity
- Good choice for portable TETRA monitoring

### BladeRF x115
- Professional variant
- Industrial-grade stability
- Wider frequency range

Choose based on your use case and budget.

---

## Troubleshooting

**"BladeRF library not available"**
- Install: `pip install bladerf`
- Ensure libusb is installed

**"Failed to open BladeRF"**
- Check USB connection
- Verify drivers installed (Windows)
- Check device permissions (Linux: may need udev rules)

**Sample rate issues**
- BladeRF may auto-adjust to nearest valid rate
- Check actual rate after opening
- Validate against device specs

---

## References

- BladeRF Python API: https://github.com/Nuand/bladerf/tree/master/host/libraries/libbladeRF/bindings/python
- BladeRF Hardware: https://www.nuand.com/
- TETRA Decoder Protocol: ETSI EN 300 392-2 V3.2.1

