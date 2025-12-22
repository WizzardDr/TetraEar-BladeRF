import wave
import numpy as np
import sys
import os

def check_wav_amplitude(filename):
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return

    try:
        with wave.open(filename, 'rb') as wav:
            n_frames = wav.getnframes()
            data = wav.readframes(n_frames)
            samples = np.frombuffer(data, dtype=np.int16)
            
            max_amp = np.max(np.abs(samples))
            avg_amp = np.mean(np.abs(samples))
            non_zero = np.count_nonzero(samples)
            
            print(f"File: {filename}")
            print(f"Max Amplitude: {max_amp}")
            print(f"Avg Amplitude: {avg_amp:.2f}")
            print(f"Non-zero samples: {non_zero}/{len(samples)} ({non_zero/len(samples)*100:.1f}%)")
            
            if max_amp > 0:
                print("STATUS: VALID AUDIO (Amplitude > 0)")
            else:
                print("STATUS: SILENCE (Amplitude = 0)")
                
    except Exception as e:
        print(f"Error reading WAV: {e}")

if __name__ == "__main__":
    # Find the most recent wav file in records/
    records_dir = "records"
    if os.path.exists(records_dir):
        files = [os.path.join(records_dir, f) for f in os.listdir(records_dir) if f.endswith(".wav")]
        if files:
            latest_file = max(files, key=os.path.getctime)
            check_wav_amplitude(latest_file)
        else:
            print("No WAV files found in records/")
    else:
        print("records/ directory not found")
