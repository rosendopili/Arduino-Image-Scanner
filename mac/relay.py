#!/usr/bin/env python3
"""Read one camera frame from the Nano and hand it to the Uno Q.

The Mac is only the USB adapter. The viewscreen and Gemma run on the board.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import zlib
import struct
from pathlib import Path

import serial
from serial.tools import list_ports

FRAME_W = 176
FRAME_H = 144
FRAME_BYTES = FRAME_W * FRAME_H * 2
BANNER = b"TRICORDER_CAM"


def rgb565_to_png(raw, swap_bytes):
    if len(raw) != FRAME_BYTES:
        raise ValueError(f"expected {FRAME_BYTES} bytes, got {len(raw)}")
    rgb = bytearray(FRAME_W * FRAME_H * 3)
    out = 0
    for i in range(0, FRAME_BYTES, 2):
        hi = raw[i + 1] if swap_bytes else raw[i]
        lo = raw[i] if swap_bytes else raw[i + 1]
        pixel = (hi << 8) | lo
        rgb[out] = ((pixel >> 11) & 0x1F) << 3
        rgb[out + 1] = ((pixel >> 5) & 0x3F) << 2
        rgb[out + 2] = (pixel & 0x1F) << 3
        out += 3
    return encode_png(FRAME_W, FRAME_H, bytes(rgb))


def encode_png(width, height, rgb):
    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(
        b"\x00" + rgb[y * width * 3 : (y + 1) * width * 3] for y in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def candidate_ports(explicit):
    if explicit:
        return [explicit]
    found = []
    for port in list_ports.comports():
        name = port.device
        if "usbmodem" in name or "usbserial" in name:
            found.append(name)
    return found


def read_exact(ser, count):
    buf = bytearray()
    deadline = time.monotonic() + 8
    while len(buf) < count:
        if time.monotonic() > deadline:
            raise TimeoutError(f"serial stopped after {len(buf)} of {count} bytes")
        chunk = ser.read(count - len(buf))
        if chunk:
            buf.extend(chunk)
    return bytes(buf)


def wait_banner(ser):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        line = ser.readline()
        if BANNER in line:
            return True
        if b"CAM_FAIL" in line:
            raise RuntimeError("camera did not respond on the Nano")
    return False


def open_camera(explicit):
    ports = candidate_ports(explicit)
    if not ports:
        raise SystemExit("No USB serial port found. Plug the Nano into this Mac.")
    errors = []
    for port in ports:
        try:
            ser = serial.Serial(port, 115200, timeout=0.4)
        except serial.SerialException as exc:
            errors.append(f"{port}: {exc}")
            continue
        try:
            saw_banner = wait_banner(ser)
        except (TimeoutError, RuntimeError) as exc:
            ser.close()
            errors.append(f"{port}: {exc}")
            continue
        if not saw_banner:
            print(f"{port}: no boot banner, assuming the sketch is already running", flush=True)
        print(f"camera {port}", flush=True)
        return ser
    raise SystemExit("Could not find the tricorder camera.\n" + "\n".join(errors))


def capture_png(ser, swap_bytes):
    ser.reset_input_buffer()
    ser.write(b"S\n")
    ser.flush()
    deadline = time.monotonic() + 8
    header = b""
    while time.monotonic() < deadline:
        header = ser.readline()
        if header.startswith(b"FRAME "):
            break
        if header.startswith(b"CAM_"):
            raise RuntimeError(header.decode(errors="replace").strip())
    else:
        raise TimeoutError("camera did not send a frame")
    parts = header.split()
    if len(parts) != 3 or int(parts[1]) != FRAME_W or int(parts[2]) != FRAME_H:
        raise RuntimeError(f"unexpected frame header: {header!r}")
    raw = read_exact(ser, FRAME_BYTES)
    trailer = ser.readline()
    if trailer.strip() != b"END":
        # The sketch writes "\nEND\n", so the first readline after the raw
        # bytes may be empty and the next line is END.
        if trailer.strip() == b"":
            trailer = ser.readline()
        if trailer.strip() != b"END":
            raise RuntimeError(f"frame trailer was {trailer!r}")
    return rgb565_to_png(raw, swap_bytes)


def request(url, data=None, headers=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def request_json(url, timeout):
    return json.loads(request(url, timeout=timeout).decode())


def wait_for_scan(base):
    try:
        body = request_json(f"{base}/capture-request", timeout=60)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"viewscreen unreachable: {exc}", flush=True)
        time.sleep(2)
        return False
    return body.get("scan") is True


def post_frame(base, png):
    request(
        f"{base}/scan",
        data=png,
        headers={"Content-Type": "image/png"},
        timeout=30,
    )


def post_failure(base, message):
    try:
        request(
            f"{base}/scan-failed",
            data=message.encode(),
            headers={"Content-Type": "text/plain"},
            timeout=10,
        )
    except urllib.error.URLError as exc:
        print(f"could not report camera failure: {exc}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Forward one Nano frame to the Uno Q.")
    parser.add_argument("--host", default="http://roarduino.local:8090")
    parser.add_argument("--port", default="", help="Serial device, for example /dev/cu.usbmodem1101")
    parser.add_argument(
        "--swap-bytes",
        action="store_true",
        help="Swap RGB565 bytes if the snapshot colors are wrong.",
    )
    parser.add_argument(
        "--once",
        type=Path,
        default=None,
        help="Capture one PNG to this path and exit. Does not talk to the Uno Q.",
    )
    args = parser.parse_args()
    base = args.host.rstrip("/")
    ser = open_camera(args.port or None)
    try:
        if args.once:
            png = capture_png(ser, args.swap_bytes)
            args.once.write_bytes(png)
            print(f"wrote {args.once}", flush=True)
            return
        print(f"waiting for Scan on {base}", flush=True)
        while True:
            if not wait_for_scan(base):
                continue
            print("scan", flush=True)
            try:
                png = capture_png(ser, args.swap_bytes)
                post_frame(base, png)
            except (TimeoutError, RuntimeError, serial.SerialException) as exc:
                print(f"capture failed: {exc}", flush=True)
                post_failure(base, str(exc))
    finally:
        ser.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
