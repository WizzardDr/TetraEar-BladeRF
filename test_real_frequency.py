"""
Test script to scan around 391.5 MHz for TETRA signals
"""
import time
from rtl_capture import RTLCapture
from signal_processor import SignalProcessor
import numpy as np

def scan_frequency_range(center=391.5e6, range_mhz=2, step_khz=25):
    """Scan frequency range for signals."""
    print(f"Scanning {center/1e6:.1f} MHz +/- {range_mhz} MHz")
    
    # Initialize RTL-SDR
    rtl = RTLCapture(frequency=center, sample_rate=1.8e6, gain='auto')
    if not rtl.open():
        print("ERROR: Failed to open RTL-SDR device")
        return []
    
    print(f"RTL-SDR opened successfully")
    
    start_freq = center - (range_mhz * 1e6 / 2)
    stop_freq = center + (range_mhz * 1e6 / 2)
    step = step_khz * 1e3
    
    results = []
    freq = start_freq
    
    print(f"\nScanning from {start_freq/1e6:.3f} to {stop_freq/1e6:.3f} MHz")
    print(f"Step: {step_khz} kHz\n")
    
    while freq <= stop_freq:
        # Tune to frequency
        rtl.set_frequency(freq)
        time.sleep(0.05)  # Let it settle
        
        # Capture samples
        samples = rtl.read_samples(64*1024)
        
        # Calculate power
        if len(samples) > 1024:
            fft = np.fft.fftshift(np.fft.fft(samples[:1024] * np.hanning(1024)))
            power = 20 * np.log10(np.abs(fft) / 1024 + 1e-20)
            avg_power = np.mean(power)
            max_power = np.max(power)
            
            # Detect signals above noise floor
            if max_power > -60:  # Strong signal threshold
                print(f"  {freq/1e6:.3f} MHz: {max_power:.1f} dB (avg: {avg_power:.1f} dB) *** SIGNAL DETECTED ***")
                results.append({
                    'freq': freq,
                    'power': max_power,
                    'avg_power': avg_power
                })
            elif max_power > -75:  # Weak signal
                print(f"  {freq/1e6:.3f} MHz: {max_power:.1f} dB (avg: {avg_power:.1f} dB) - weak signal")
            else:
                print(f"  {freq/1e6:.3f} MHz: {max_power:.1f} dB", end='\r')
        
        freq += step
    
    rtl.close()
    
    print("\n\n=== SCAN RESULTS ===")
    if results:
        print(f"Found {len(results)} strong signals:")
        results.sort(key=lambda x: x['power'], reverse=True)
        for r in results:
            print(f"  {r['freq']/1e6:.3f} MHz: {r['power']:.1f} dB")
    else:
        print("No strong signals found")
    
    return results

if __name__ == '__main__':
    # Scan around common TETRA frequencies
    print("TETRA Frequency Scanner")
    print("=" * 50)
    
    # Common TETRA bands
    bands = [
        (391.5e6, "390-392 MHz (Common EU TETRA)"),
        (420.0e6, "420-430 MHz (Common EU TETRA)"),
    ]
    
    all_results = []
    
    for center, desc in bands:
        print(f"\n\nScanning: {desc}")
        print("-" * 50)
        results = scan_frequency_range(center, range_mhz=2, step_khz=25)
        all_results.extend(results)
        time.sleep(1)
    
    print("\n\n=== OVERALL RESULTS ===")
    if all_results:
        all_results.sort(key=lambda x: x['power'], reverse=True)
        print(f"\nTop 5 frequencies by signal strength:")
        for r in all_results[:5]:
            print(f"  {r['freq']/1e6:.3f} MHz: {r['power']:.1f} dB")
        print(f"\nRecommended frequency to test: {all_results[0]['freq']/1e6:.3f} MHz")
    else:
        print("No signals found. Check antenna and RTL-SDR connection.")
