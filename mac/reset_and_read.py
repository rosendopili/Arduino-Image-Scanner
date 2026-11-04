import time

import serial

PORT = "/dev/cu.usbmodem31201"

# 1200 baud open/close restarts a Nano 33 BLE into the bootloader,
# which then times out and runs the sketch.
touch = serial.Serial(PORT, 1200)
touch.close()
time.sleep(3)

ser = serial.Serial(PORT, 115200, timeout=0.4)
end = time.time() + 15
buf = b""
while time.time() < end:
    data = ser.read(1024)
    if data:
        buf += data
        print(repr(data), flush=True)
print("TOTAL", len(buf))
ser.close()
