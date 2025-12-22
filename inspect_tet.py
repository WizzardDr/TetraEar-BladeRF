import struct
import sys
import os

def inspect_tet(filename):
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return

    with open(filename, 'rb') as f:
        data = f.read()
        
    print(f"File size: {len(data)} bytes")
    if len(data) % 2 != 0:
        print("Warning: File size is not multiple of 2")
        
    count = len(data) // 2
    shorts = struct.unpack(f'<{count}h', data)
    
    print(f"Header: 0x{shorts[0]:04X}")
    print("First 20 shorts:")
    for i in range(20):
        print(f"{shorts[i]}", end=" ")
    print()
    
    print("Min:", min(shorts))
    print("Max:", max(shorts))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        inspect_tet(sys.argv[1])
