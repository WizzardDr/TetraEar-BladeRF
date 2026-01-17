#!/usr/bin/env python3
"""
List all connected BladeRF devices.

This utility helps identify and enumerate BladeRF devices connected to the system.
Useful for device selection when multiple devices are connected.

Usage:
    python -m tetraear.tools.list_bladerf_devices
    
    # With verbose output
    python -m tetraear.tools.list_bladerf_devices -v
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for device listing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='List all connected BladeRF devices',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  List all devices:
    python -m tetraear.tools.list_bladerf_devices
    
  List devices with verbose output:
    python -m tetraear.tools.list_bladerf_devices -v
        """
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Import after arg parsing to avoid import errors
    from tetraear.signal.capture import list_bladerf_devices, BLADERF_AVAILABLE
    
    print("=" * 60)
    print("BladeRF Device Enumeration")
    print("=" * 60)
    
    if not BLADERF_AVAILABLE:
        print("\n❌ ERROR: BladeRF library not available")
        print("\nInstall with:")
        print("  pip install bladerf")
        return 1
    
    devices = list_bladerf_devices()
    
    if not devices:
        print("\n⚠️  No BladeRF devices found")
        print("\nPlease verify:")
        print("  - Device is connected via USB")
        print("  - Device drivers are installed")
        print("  - Device is not in use by another application")
        print("\nOn Linux, you may need to:")
        print("  - Set udev rules: sudo usermod -a -G plugdev $USER")
        print("  - Reload rules: sudo udevadm control --reload")
        return 1
    
    print(f"\n✅ Found {len(devices)} BladeRF device(s):\n")
    
    for i, device in enumerate(devices, 1):
        print(f"Device {i}:")
        print(f"  Serial:   {device['serial']}")
        print(f"  Backend:  {device['backend']}")
        print(f"  USB Bus:  {device['usb_bus']}")
        print(f"  USB Addr: {device['usb_addr']}")
        print(f"  Instance: {device['instance']}")
        
        # Build device identifier string
        device_id = f"{device['backend']}:bus={device['usb_bus']}:addr={device['usb_addr']} instance={device['instance']}"
        print(f"  ID:       {device_id}")
        print()
    
    print("=" * 60)
    print("Device Identifiers:")
    print("=" * 60)
    
    for i, device in enumerate(devices, 1):
        device_id = device['serial']
        print(f"  By Serial: {device_id}")
    
    print("\nUse device ID with:")
    print("  from tetraear.signal.capture import BladeRFCapture")
    print("  capture = BladeRFCapture(device_identifier='<serial>')")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
