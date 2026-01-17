# BladeRF Python API Corrections

## Summary

Fixed implementation errors to match the actual python-bladerf library API. The DevInfo namedtuple from python-bladerf contains only 5 fields, not the originally assumed 8.

## Files Corrected

### 1. `tetraear/signal/capture.py`

**Function**: `list_bladerf_devices()`

**Changes**:
- Removed incorrect dictionary keys: `'serial_str'`, `'devstr'`, `'device'`
- Now returns only the actual DevInfo attributes as dict keys
- Properly handles serial decoding from bytes to string

**Correct return structure**:
```python
{
    'backend': str,      # Backend enum as string ('libusb', 'linux', etc.)
    'serial': str,       # Serial number (decoded from bytes)
    'usb_bus': int,      # USB bus number
    'usb_addr': int,     # USB address on bus
    'instance': int,     # Device instance/ID
}
```

**DevInfo namedtuple actual attributes**:
- `backend` - Backend enum value
- `serial` - Serial number (bytes)
- `usb_bus` - USB bus number (uint8)
- `usb_addr` - USB device address (uint8)
- `instance` - Instance/ID number (unsigned int)

### 2. `tetraear/ui/modern.py`

**Function**: `refresh_device_list()`

**Changes**:
- Removed access to non-existent `device.get('device', 0)` field
- Updated display format to use actual fields: `usb_bus` and `usb_addr`
- Changed from: `{backend}:device={device},instance={instance}`
- Changed to: `{backend}:bus={usb_bus}:addr={usb_addr} instance={instance}`

### 3. `tetraear/tools/list_bladerf_devices.py`

**Function**: Device enumeration and display

**Changes**:
- Removed reference to non-existent `device['device']` field
- Updated display to show actual USB information: `usb_bus`, `usb_addr`
- Device ID format updated to match actual python-bladerf conventions

## Device Opening

The correct way to open a BladeRF device with python-bladerf:

```python
import bladerf

# Open first available device
dev = bladerf.BladeRF()

# Open specific device by serial
dev = bladerf.BladeRF("*:serial=f12ce103")

# Open with specific backend
dev = bladerf.BladeRF("libusb:serial=f12ce103")
```

## DevInfo Properties

The DevInfo namedtuple also has useful properties:

```python
device_info.serial_str  # Returns str (decoded version of serial)
device_info.devstr      # Returns formatted device string
```

These are accessed via the properties defined in the DevInfo class in `_bladerf.py`.

## Source Reference

Based on the official python-bladerf library:
- Repository: https://github.com/Nuand/bladeRF
- File: `host/libraries/libbladeRF_bindings/python/bladerf/_bladerf.py`
- DevInfo definition: Lines 110-146
- get_device_list() function: Lines 418-429

## Testing

All files now pass syntax validation:
- ✅ `tetraear/signal/capture.py` - No errors
- ✅ `tetraear/ui/modern.py` - No errors  
- ✅ `tetraear/tools/list_bladerf_devices.py` - No errors

The implementation now correctly matches the actual python-bladerf API structure and will work with real BladeRF devices connected to the system.
