import sys
import time

import serial

port = sys.argv[1]
ser = serial.Serial(port, 115200, timeout=0.4)


def read_for(seconds):
    end = time.time() + seconds
    buf = b""
    while time.time() < end:
        data = ser.read(1024)
        if data:
            buf += data
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    return buf


print("listening", flush=True)
first = read_for(8)
print("\nsending S", flush=True)
ser.write(b"S\n")
second = read_for(8)
print("\nTOTAL", len(first) + len(second))
ser.close()
