"""
Signal processing and capture modules.

This package contains modules for:
- Signal processing (demodulation, filtering)
- BladeRF device capture
- Frequency scanning and signal detection
"""

# Lazy imports to avoid DLL loading issues during import
def __getattr__(name):
    """Lazy import for signal modules."""
    if name == "SignalProcessor":
        from tetraear.signal.processor import SignalProcessor
        return SignalProcessor
    elif name == "BladeRFCapture":
        from tetraear.signal.capture import BladeRFCapture
        return BladeRFCapture
    elif name == "list_bladerf_devices":
        from tetraear.signal.capture import list_bladerf_devices
        return list_bladerf_devices
    elif name == "TetraSignalDetector":
        from tetraear.signal.scanner import TetraSignalDetector
        return TetraSignalDetector
    elif name == "FrequencyScanner":
        from tetraear.signal.scanner import FrequencyScanner
        return FrequencyScanner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "SignalProcessor",
    "BladeRFCapture",
    "list_bladerf_devices",
    "TetraSignalDetector",
    "FrequencyScanner",
]
