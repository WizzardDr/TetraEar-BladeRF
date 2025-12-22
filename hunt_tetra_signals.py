"""
Automated TETRA Signal Hunter
Scans frequencies and monitors for voice/SDS until found
"""
import sys
import time
import subprocess
import signal
from datetime import datetime

def scan_and_find_best():
    """Scan and return best frequencies."""
    print("=" * 70)
    print("TETRA SIGNAL HUNTER - Automated Voice/SDS Detection")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Import here to avoid issues
    from rtl_capture import RTLCapture
    import numpy as np
    
    print("Phase 1: Scanning for TETRA signals...")
    print("-" * 70)
    
    # Scan common TETRA bands
    bands = [
        (390.0, 392.0, "390-392 MHz EU TETRA"),
        (420.0, 422.0, "420-422 MHz EU TETRA"),
    ]
    
    all_signals = []
    
    for start_mhz, stop_mhz, desc in bands:
        print(f"\n📡 Scanning: {desc}")
        rtl = RTLCapture(frequency=start_mhz*1e6, sample_rate=1.8e6, gain='auto')
        if not rtl.open():
            print("  ✗ Failed to open RTL-SDR")
            continue
        
        freq = start_mhz * 1e6
        stop = stop_mhz * 1e6
        step = 25e3  # 25 kHz TETRA channel spacing
        
        while freq <= stop:
            rtl.set_frequency(freq)
            time.sleep(0.05)
            
            samples = rtl.read_samples(32*1024)
            if len(samples) > 1024:
                fft = np.fft.fftshift(np.fft.fft(samples[:1024] * np.hanning(1024)))
                power = 20 * np.log10(np.abs(fft) / 1024 + 1e-20)
                max_power = np.max(power)
                
                if max_power > -50:  # Strong signal
                    all_signals.append({
                        'freq_mhz': freq / 1e6,
                        'power': max_power,
                        'band': desc
                    })
                    print(f"  ✓ {freq/1e6:.3f} MHz: {max_power:.1f} dB")
            
            freq += step
        
        rtl.close()
        time.sleep(0.5)
    
    if not all_signals:
        print("\n✗ No strong signals found. Check antenna and connection.")
        return []
    
    # Sort by power
    all_signals.sort(key=lambda x: x['power'], reverse=True)
    
    print("\n" + "=" * 70)
    print(f"Found {len(all_signals)} strong signals")
    print("Top 10 by signal strength:")
    for i, sig in enumerate(all_signals[:10]):
        print(f"  {i+1}. {sig['freq_mhz']:.3f} MHz: {sig['power']:.1f} dB ({sig['band']})")
    
    return all_signals


def monitor_frequency(freq_mhz, duration_sec=30):
    """Monitor a frequency and look for voice/SDS."""
    print("\n" + "=" * 70)
    print(f"Phase 2: Monitoring {freq_mhz:.3f} MHz for {duration_sec}s")
    print("-" * 70)
    print("Looking for:")
    print("  📝 SDS text messages")
    print("  🔊 Voice frames")
    print("  🔓 Clear (unencrypted) traffic")
    print()
    
    # Launch GUI with this frequency
    cmd = [
        sys.executable,
        "tetra_gui_modern.py",
        "-f", f"{freq_mhz:.3f}",
        "--auto-start",
        "-m",  # Enable audio monitoring
        "-v"   # Verbose
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print(f"Monitoring for {duration_sec} seconds...")
    print("(GUI will launch - watch for decoded frames)")
    print()
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        start_time = time.time()
        voice_found = False
        sds_found = False
        clear_frames = 0
        
        while time.time() - start_time < duration_sec:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue
            
            line = line.strip()
            
            # Check for voice
            if 'Decoded voice:' in line or 'has_voice' in line:
                voice_found = True
                print(f"  🔊 VOICE DETECTED: {line}")
            
            # Check for SDS
            if 'sds_message' in line or 'decoded_text' in line or '[SDS' in line or '[TXT]' in line:
                sds_found = True
                print(f"  📝 SDS MESSAGE: {line}")
            
            # Check for clear mode
            if 'clear mode' in line.lower():
                clear_frames += 1
                if clear_frames == 1:
                    print(f"  🔓 Clear traffic detected")
            
            # Show decoded frames
            if 'Decoded frame' in line or 'TETRA Signal Detected' in line:
                print(f"  📡 {line}")
        
        # Terminate process
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
        
        print()
        print("Monitoring complete:")
        print(f"  Voice found: {'✓ YES' if voice_found else '✗ NO'}")
        print(f"  SDS found: {'✓ YES' if sds_found else '✗ NO'}")
        print(f"  Clear frames: {clear_frames}")
        
        return voice_found, sds_found, clear_frames
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        if proc:
            proc.terminate()
        return False, False, 0


def main():
    """Main hunter loop."""
    print("\n🎯 TETRA Signal Hunter - Automated Voice/SDS Finder")
    print("=" * 70)
    print()
    print("This script will:")
    print("  1. Scan 390-392 MHz and 420-422 MHz bands")
    print("  2. Find strongest signals")
    print("  3. Monitor each for voice/SDS (30s per frequency)")
    print("  4. Report findings")
    print()
    input("Press ENTER to start hunting... ")
    
    # Phase 1: Scan
    signals = scan_and_find_best()
    if not signals:
        print("\nNo signals found. Exiting.")
        return
    
    # Phase 2: Monitor top frequencies
    print("\n" + "=" * 70)
    print("Phase 2: Monitoring top frequencies for voice/SDS")
    print("=" * 70)
    
    results = []
    
    # Try top 5 signals
    for i, sig in enumerate(signals[:5]):
        print(f"\n[{i+1}/5] Testing {sig['freq_mhz']:.3f} MHz ({sig['power']:.1f} dB)")
        
        voice, sds, clear = monitor_frequency(sig['freq_mhz'], duration_sec=30)
        
        results.append({
            'freq': sig['freq_mhz'],
            'power': sig['power'],
            'voice': voice,
            'sds': sds,
            'clear': clear
        })
        
        # If we found voice or SDS, highlight it
        if voice or sds:
            print(f"\n🎉 SUCCESS on {sig['freq_mhz']:.3f} MHz!")
            print(f"  Voice: {'✓' if voice else '✗'}")
            print(f"  SDS: {'✓' if sds else '✗'}")
        
        time.sleep(2)
    
    # Final report
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print()
    print(f"Tested {len(results)} frequencies:")
    print()
    
    found_something = False
    for r in results:
        if r['voice'] or r['sds']:
            found_something = True
            print(f"✅ {r['freq']:.3f} MHz ({r['power']:.1f} dB)")
            if r['voice']:
                print(f"   🔊 Voice detected!")
            if r['sds']:
                print(f"   📝 SDS messages detected!")
            if r['clear'] > 0:
                print(f"   🔓 {r['clear']} clear frames")
            print()
    
    if not found_something:
        print("❌ No voice or SDS found on any frequency.")
        print()
        print("Possible reasons:")
        print("  • No active transmissions during monitoring")
        print("  • All traffic is encrypted")
        print("  • Wrong frequency band for your location")
        print("  • Weak signal / antenna issues")
        print()
        print("Top frequencies by power (try these manually):")
        for r in results:
            print(f"  {r['freq']:.3f} MHz ({r['power']:.1f} dB) - {r['clear']} clear frames")
    
    print()
    print("=" * 70)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
        sys.exit(1)
