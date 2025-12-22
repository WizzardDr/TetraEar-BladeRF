import wave
import struct
import sys
import os

def check_wav_amplitude(filename):
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return

    try:
        with wave.open(filename, 'rb') as wav_file:
            n_channels = wav_file.getnchannels()
            sampwidth = wav_file.getsampwidth()
            n_frames = wav_file.getnframes()
            
            print(f"Checking {filename}")
            print(f"Channels: {n_channels}, Width: {sampwidth}, Frames: {n_frames}")
            
            if n_frames == 0:
                print("Empty file")
                return

            frames = wav_file.readframes(n_frames)
            
            max_amp = 0
            min_amp = 0
            
            if sampwidth == 2: # 16-bit
                # Unpack as signed short
                fmt = f"<{n_frames * n_channels}h"
                samples = struct.unpack(fmt, frames)
                if samples:
                    max_amp = max(samples)
                    min_amp = min(samples)
            elif sampwidth == 1: # 8-bit
                # Unpack as unsigned char
                fmt = f"<{n_frames * n_channels}B"
                samples = struct.unpack(fmt, frames)
                # Convert to signed for amplitude check (0-255 -> -128 to 127)
                samples = [s - 128 for s in samples]
                if samples:
                    max_amp = max(samples)
                    min_amp = min(samples)
                
            print(f"Max Amplitude: {max_amp}")
            print(f"Min Amplitude: {min_amp}")
            
            if max_amp == 0 and min_amp == 0:
                print("SILENCE DETECTED (Amplitude 0)")
            else:
                print("Audio data present")

    except Exception as e:
        print(f"Error reading wav: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_wav_amplitude(sys.argv[1])
    else:
        # Find the most recent wav file in records/
        records_dir = "records"
        if os.path.exists(records_dir):
            files = [os.path.join(records_dir, f) for f in os.listdir(records_dir) if f.endswith(".wav")]
            if files:
                newest_file = max(files, key=os.path.getctime)
                check_wav_amplitude(newest_file)
            else:
                print("No wav files found in records/")
        else:
            print("records/ directory not found")
