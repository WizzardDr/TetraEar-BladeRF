"""
BladeRF signal capture module for TETRA decoding.
"""

import os
import sys
from pathlib import Path

# Add bundled DLL search paths (Windows).
if sys.platform == "win32":
    try:
        tetraear_root = Path(__file__).resolve().parents[1]
        dll_dir = tetraear_root / "bin"

        for dll_path in (dll_dir, tetraear_root):
            if not dll_path.exists():
                continue
            dll_path_str = str(dll_path)
            if dll_path_str not in os.environ.get("PATH", ""):
                os.environ["PATH"] = dll_path_str + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(dll_path_str)
    except (OSError, AttributeError):
        pass  # Fallback if methods fail

import numpy as np
import logging
import warnings

# Lazy import of BladeRF to avoid loading issues during import
try:
    import bladerf
    BLADERF_AVAILABLE = True
except (ImportError, OSError):
    BLADERF_AVAILABLE = False
    bladerf = None  # type: ignore

logger = logging.getLogger(__name__)


class BladeRFCapture:
    """Handles BladeRF device configuration and signal capture."""
    
    def __init__(self, frequency=400e6, sample_rate=1.8e6, gain='auto'):
        """
        Initialize BladeRF capture.
        
        Args:
            frequency: Center frequency in Hz
            sample_rate: Sample rate in Hz
            gain: Gain setting ('auto' for default mode, or numeric value 0-60 dB for manual mode)
        """
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.device = None
        
    def open(self):
        """
        Open and configure BladeRF device.
        
        Returns:
            bool: True if device opened successfully, False otherwise
        
        Raises:
            RuntimeError: If BladeRF library is not available
        """
        if not BLADERF_AVAILABLE:
            logger.error("BladeRF library not available. Install with: pip install bladerf")
            return False
        
        try:
            # Open first available BladeRF device
            self.device = bladerf.open()
            
            # Validate sample rate for BladeRF
            # BladeRF generally supports: 160 kHz - 40 MHz, but common rates are
            # 1 MHz, 1.8 MHz, 2.4 MHz, 5 MHz, etc.
            # The device will auto-adjust to nearest supported rate
            
            # Set sample rate
            self.device.sample_rate = self.sample_rate
            
            # Verify actual sample rate (may differ from requested)
            actual_rate = self.device.sample_rate
            if abs(actual_rate - self.sample_rate) > 0.1e6:  # More than 100kHz difference
                logger.warning(f"Sample rate {self.sample_rate/1e6:.3f} MHz adjusted to {actual_rate/1e6:.3f} MHz by device")
                self.sample_rate = actual_rate
            
            # Set center frequency
            self.device.frequency = self.frequency
            
            # Configure gain
            if isinstance(self.gain, str) and self.gain.lower() == 'auto':
                # Use default gain mode
                self.device.gain = 'default'
                logger.debug("BladeRF gain mode: Default")
            else:
                # Use manual gain mode with specified value
                gain_value = float(self.gain) if isinstance(self.gain, str) else self.gain
                # Clamp gain to valid range (0-60 dB for BladeRF)
                gain_value = max(0, min(60, gain_value))
                self.device.gain = gain_value
                logger.debug(f"BladeRF gain mode: Manual ({gain_value} dB)")
            
            # Try to get device info
            try:
                logger.info(f"BladeRF opened successfully")
            except Exception:
                logger.info("BladeRF opened (info read not available)")
            
            logger.info(f"Frequency: {self.frequency/1e6:.2f} MHz")
            logger.info(f"Sample rate: {self.sample_rate/1e6:.2f} MHz")
            logger.info(f"Gain: {self.gain}")
            
            return True
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to open BladeRF: {e}")
            
            # Provide helpful error messages
            if "No devices found" in error_msg:
                logger.error("")
                logger.error("=" * 60)
                logger.error("NO BLADERF DEVICE FOUND")
                logger.error("=" * 60)
                logger.error("Please ensure:")
                logger.error("1. BladeRF device is connected via USB")
                logger.error("2. Device drivers are installed")
                logger.error("3. Device is not in use by another application")
                logger.error("")
                logger.error("Install drivers from: https://www.nuand.com/")
                logger.error("=" * 60)
            elif "access" in error_msg.lower() or "permission" in error_msg.lower():
                logger.error("")
                logger.error("=" * 60)
                logger.error("USB DEVICE ACCESS ERROR")
                logger.error("=" * 60)
                logger.error("Your BladeRF device needs proper USB access.")
                logger.error("")
                logger.error("On Linux, run:")
                logger.error("  sudo usermod -a -G plugdev $USER")
                logger.error("  sudo udevadm control --reload")
                logger.error("")
                logger.error("On Windows, ensure WinUSB driver is installed.")
                logger.error("=" * 60)
            
            return False
    
    def read_samples(self, num_samples=1024*1024):
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
            samples = self.device.rx(num_samples)
            return samples
        except (OSError, RuntimeError) as e:
            error_msg = str(e)
            # Check for device errors
            if "device" in error_msg.lower() or "transfer" in error_msg.lower():
                logger.error(f"BladeRF device error: {e}")
                logger.error("Device may be in invalid state. Attempting to recover...")
                # Try to close and reopen
                try:
                    self.device.close()
                except:
                    pass
                self.device = None
                raise RuntimeError("BladeRF device error - please restart the application")
            logger.error(f"Failed to read samples: {e}")
            raise
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
            self.device.frequency = frequency
            logger.debug(f"Frequency changed to {frequency/1e6:.3f} MHz")
        except Exception as e:
            logger.error(f"Failed to set frequency: {e}")
            raise
    
    def close(self):
        """Close BladeRF device."""
        if self.device is not None:
            try:
                self.device.close()
            except Exception as e:
                logger.warning(f"Error closing device: {e}")
            self.device = None
            logger.info("BladeRF device closed")
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
