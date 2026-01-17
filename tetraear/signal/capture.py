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


def list_bladerf_devices():
    """
    List all connected BladeRF devices.
    
    Returns:
        list: List of dicts with device info, or empty list if none found
        
    Example:
        devices = list_bladerf_devices()
        for dev in devices:
            print(f"Serial: {dev['serial']} (Bus: {dev['usb_bus']}, Addr: {dev['usb_addr']})")
    """
    if not BLADERF_AVAILABLE:
        logger.warning("BladeRF library not available")
        return []
    
    try:
        devices = []
        try:
            device_list = bladerf.get_device_list()
        except bladerf.NoDevError:
            # No devices found
            logger.debug("No BladeRF devices found")
            return []
        
        for device_info in device_list:
            # DevInfo is a namedtuple with: backend, serial, usb_bus, usb_addr, instance
            # serial is bytes, need to decode to string
            serial_str = device_info.serial.decode('utf-8') if isinstance(device_info.serial, bytes) else str(device_info.serial)
            
            device_dict = {
                'backend': str(device_info.backend),
                'serial': serial_str,
                'usb_bus': device_info.usb_bus,
                'usb_addr': device_info.usb_addr,
                'instance': device_info.instance,
            }
            devices.append(device_dict)
            logger.debug(f"Found BladeRF: Serial={serial_str}, Bus={device_info.usb_bus}, Addr={device_info.usb_addr}")
        
        return devices
    except Exception as e:
        logger.error(f"Error listing BladeRF devices: {e}")
        return []


class BladeRFCapture:
    """Handles BladeRF device configuration and signal capture."""
    
    def __init__(self, frequency=400e6, sample_rate=1.8e6, gain='auto', device_identifier=None):
        """
        Initialize BladeRF capture.
        
        Args:
            frequency: Center frequency in Hz
            sample_rate: Sample rate in Hz
            gain: Gain setting ('auto' for default mode, or numeric value 0-60 dB for manual mode)
            device_identifier: Optional device identifier (serial number or device string).
                              If None, opens first available device.
        """
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.device_identifier = device_identifier
        self.device = None
    def open(self):
        """
        Open and configure BladeRF device.
        
        Returns:
            bool: True if device opened successfully, False otherwise
        """
        if not BLADERF_AVAILABLE:
            logger.error("BladeRF library not available. Install with: pip install bladerf")
            return False
        
        try:
            # Open BladeRF device
            # Use BladeRF class constructor (not bladerf.open())
            try:
                if self.device_identifier:
                    # Device identifier can be:
                    # - Serial string: "*:serial=f12ce103"
                    # - Bus/address: "libusb:device=1:10"
                    logger.info(f"Opening BladeRF device: {self.device_identifier}")
                    self.device = bladerf.BladeRF(self.device_identifier)
                else:
                    # Open first available device
                    logger.info("Opening first available BladeRF device")
                    self.device = bladerf.BladeRF()
            except bladerf.NoDevError:
                logger.error("No BladeRF devices found")
                return False
            
            # Set sample rate using channel API
            # set_sample_rate returns actual rate (device may adjust)
            try:
                actual_rate = self.device.set_sample_rate(bladerf.CHANNEL_RX(0), self.sample_rate)
                if abs(actual_rate - self.sample_rate) > 0.1e6:  # More than 100kHz difference
                    logger.warning(f"Sample rate {self.sample_rate/1e6:.3f} MHz adjusted to {actual_rate/1e6:.3f} MHz by device")
                    self.sample_rate = actual_rate
            except Exception as e:
                logger.error(f"Failed to set sample rate: {e}")
                self.device.close()
                return False
            
            # Set center frequency
            try:
                self.device.set_frequency(bladerf.CHANNEL_RX(0), self.frequency)
            except Exception as e:
                logger.error(f"Failed to set frequency: {e}")
                self.device.close()
                return False
            
            # Configure gain mode and value
            try:
                if isinstance(self.gain, str) and self.gain.lower() == 'auto':
                    # Use default AGC mode
                    self.device.set_gain_mode(bladerf.CHANNEL_RX(0), bladerf.GainMode.Default)
                    logger.debug("BladeRF gain mode: Default (AGC)")
                else:
                    # Use manual gain mode
                    self.device.set_gain_mode(bladerf.CHANNEL_RX(0), bladerf.GainMode.Manual)
                    gain_value = float(self.gain) if isinstance(self.gain, str) else self.gain
                    # Clamp gain to valid range (typically -10 to +60 dB for RX)
                    gain_range = self.device.get_gain_range(bladerf.CHANNEL_RX(0))
                    gain_value = max(gain_range.min, min(gain_range.max, gain_value))
                    self.device.set_gain(bladerf.CHANNEL_RX(0), gain_value)
                    logger.debug(f"BladeRF gain mode: Manual ({gain_value} dB)")
            except Exception as e:
                logger.warning(f"Could not set gain mode/value: {e}")
                # Don't fail completely, as gain control may not be critical
            
            # Log device information
            try:
                logger.info(f"BladeRF Device: {self.device.board_name}")
                logger.info(f"Serial: {self.device.serial}")
                logger.info(f"Firmware: {self.device.fw_version}")
                logger.info(f"FPGA: {self.device.fpga_version}")
            except Exception:
                logger.info("BladeRF opened (device info not available)")
            
            logger.info(f"Frequency: {self.frequency/1e6:.2f} MHz")
            logger.info(f"Sample rate: {self.sample_rate/1e6:.2f} MHz")
            logger.info(f"Gain: {self.gain}")
            
            return True
            
        except bladerf.NoDevError:
            logger.error("")
            logger.error("=" * 60)
            logger.error("NO BLADERF DEVICE FOUND")
            logger.error("=" * 60)
            logger.error("Please ensure:")
            logger.error("1. BladeRF device is connected via USB")
            logger.error("2. Device drivers are installed")
            logger.error("3. Device is not in use by another application")
            logger.error("")
            logger.error("To list devices: python -m tetraear.tools.list_bladerf_devices")
            logger.error("Install drivers from: https://www.nuand.com/")
            logger.error("=" * 60)
            return False
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to open BladeRF: {e}")
            
            # Provide helpful error messages
            if "access" in error_msg.lower() or "permission" in error_msg.lower():
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
                logger.error("On Windows, ensure WinUSB or BladeRF drivers are installed.")
                logger.error("=" * 60)
            
            return False
    
    def read_samples(self, num_samples=1024*1024):
        """
        Read samples from BladeRF using synchronous RX API.
        
        Args:
            num_samples: Number of samples to read
            
        Returns:
            Complex numpy array of samples
        """
        if self.device is None:
            raise RuntimeError("BladeRF device not opened")
        
        try:
            # BladeRF requires synchronous mode setup for RX
            # Each sample is 4 bytes (I16 + Q16)
            buffer_size = num_samples * 4
            buffer = bytearray(buffer_size)
            
            # Read samples using sync_rx
            # timeout_ms=5000 gives 5 second timeout
            # Returns number of samples actually read
            num_read = self.device.sync_rx(buffer, num_samples, timeout_ms=5000)
            
            if num_read < 0:
                raise RuntimeError(f"BladeRF sync_rx returned error code: {num_read}")
            
            if num_read < num_samples:
                logger.warning(f"Requested {num_samples} samples, got {num_read}")
            
            # Convert buffer to complex numpy array
            # Buffer is packed as int16 pairs (I, Q)
            import struct
            # Unpack buffer as signed 16-bit integers
            unpacked = struct.unpack(f'{num_read*2}h', buffer[:num_read*4])
            
            # Combine I and Q samples into complex numbers
            samples = []
            for i in range(0, len(unpacked), 2):
                samples.append(complex(unpacked[i], unpacked[i+1]))
            
            # Convert to numpy array and normalize
            samples = np.array(samples, dtype=np.complex64)
            # Normalize by max int16 value to get values in range approximately [-1, 1]
            samples = samples / 32768.0
            
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
            # Use the channel-based API for frequency setting
            self.device.set_frequency(bladerf.CHANNEL_RX(0), frequency)
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
