"""
Quick test with detected frequency
Run this to test TETRA decoder with the strongest detected signal
"""
import sys
sys.path.insert(0, 'C:\\Users\\Adrian\\Documents\\Repos\\Tetra')

print("=" * 60)
print("TETRA DECODER TEST - Strongest Signal")
print("=" * 60)
print()
print("Detected Frequency: 392.225 MHz")
print("Signal Strength: -36.2 dB")
print()
print("Instructions:")
print("1. The GUI should now be starting...")
print("2. Enter frequency: 392.225")
print("3. Click '⚡ Tune'")
print("4. Click '▶ Start'")
print("5. Monitor for:")
print("   - 📝 SDS text messages")
print("   - 🧩 Reassembled multi-frame messages")
print("   - 🔊 Voice audio")
print("   - Check records/ folder for WAV files")
print()
print("=" * 60)

# Launch GUI
from tetra_gui_modern import main
main()
