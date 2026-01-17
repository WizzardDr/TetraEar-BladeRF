# BladeRF Device Management

## Listing Connected Devices

To see all connected BladeRF devices, use the device listing utility:

```bash
python -m tetraear.tools.list_bladerf_devices
```

### Output Example

```
============================================================
BladeRF Device Enumeration
============================================================

✅ Found 2 BladeRF device(s):

Device 1:
  Serial:   5e7aad0d0e5f11eea98c5f3f0a0b0c0d
  Backend:  libusb
  Device:   0
  Instance: 0
  ID:       libusb:device=0,instance=0

Device 2:
  Serial:   1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d
  Backend:  libusb
  Device:   1
  Instance: 0
  ID:       libusb:device=1,instance=0

============================================================
Device Identifiers:
============================================================
  By Serial: 5e7aad0d0e5f11eea98c5f3f0a0b0c0d
  By Serial: 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d
```

## Using Device Identifiers

Once you've identified your device, you can select it explicitly using the serial number:

### Python API

```python
from tetraear.signal.capture import BladeRFCapture, list_bladerf_devices

# List all devices
devices = list_bladerf_devices()
for dev in devices:
    print(f"Serial: {dev['serial']}")

# Open a specific device by serial
serial = '5e7aad0d0e5f11eea98c5f3f0a0b0c0d'
capture = BladeRFCapture(
    frequency=392.241e6,
    sample_rate=2.4e6,
    gain='auto',
    device_identifier=serial
)

if capture.open():
    print("Device opened successfully")
    # ... use capture
    capture.close()
```

### Command Line

When using CLI tools, pass the device identifier:

```bash
python -m tetraear.tools.rtl_auto_capture --device 5e7aad0d0e5f11eea98c5f3f0a0b0c0d
```

## Multiple Device Scenarios

### Scenario 1: Single Device (Default)

```python
capture = BladeRFCapture()  # Opens first device found
capture.open()
```

### Scenario 2: Multiple Devices - Select by Serial

```python
capture = BladeRFCapture(device_identifier='your_serial_here')
capture.open()
```

### Scenario 3: Multiple Devices - List and Choose Programmatically

```python
from tetraear.signal.capture import list_bladerf_devices, BladeRFCapture

devices = list_bladerf_devices()
if len(devices) > 0:
    # Use the first device with 'x40' in the model (if available)
    target_device = devices[0]['serial']
    
    for dev in devices:
        if 'x40' in str(dev.get('backend', '')):
            target_device = dev['serial']
            break
    
    capture = BladeRFCapture(device_identifier=target_device)
    capture.open()
```

## Troubleshooting

### "No BladeRF devices found"

**Windows:**
- Verify device is connected and powered
- Check Device Manager for unrecognized devices
- Install BladeRF drivers from https://www.nuand.com/

**Linux:**
- Add user to plugdev group: `sudo usermod -a -G plugdev $USER`
- Reload udev rules: `sudo udevadm control --reload`
- Log out and back in for group changes to take effect

**macOS:**
- Install via Homebrew: `brew install libbladerf`
- Verify USB permissions

### "BladeRF library not available"

Install the Python bindings:
```bash
pip install bladerf
```

### Device in Use by Another Application

- Close any other applications using the device
- Restart the driver/system if needed
- Check for hung processes: `lsof | grep bladerf`

## Device Information Fields

When listing devices, the following information is provided:

| Field | Description |
|-------|-------------|
| Serial | Unique serial number for the device |
| Backend | USB backend (typically 'libusb') |
| Device | Device index (0, 1, 2, etc.) |
| Instance | Instance number (usually 0) |
| ID | Full device identifier string |

## Advanced: Programmatic Device Management

```python
from tetraear.signal.capture import list_bladerf_devices, BladeRFCapture

# Get list of available devices
devices = list_bladerf_devices()

# Group by backend
by_backend = {}
for dev in devices:
    backend = dev['backend']
    if backend not in by_backend:
        by_backend[backend] = []
    by_backend[backend].append(dev)

# Print grouped devices
for backend, devs in by_backend.items():
    print(f"{backend}: {len(devs)} device(s)")
    for dev in devs:
        print(f"  - {dev['serial']}")

# Open first device of each backend
for backend, devs in by_backend.items():
    if devs:
        serial = devs[0]['serial']
        capture = BladeRFCapture(device_identifier=serial)
        if capture.open():
            print(f"Opened {backend} device: {serial}")
            capture.close()
```

## See Also

- [BladeRF Python API Documentation](https://github.com/Nuand/bladerf/tree/master/host/libraries/libbladeRF/bindings/python)
- [BladeRF Official Website](https://www.nuand.com/)
- [BLADERF_MIGRATION_GUIDE.md](../BLADERF_MIGRATION_GUIDE.md)
