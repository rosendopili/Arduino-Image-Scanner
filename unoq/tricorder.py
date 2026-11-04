#!/usr/bin/env python3
"""Viewscreen for the Uno Q. Gemma runs on this same board."""

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "::"
PORT = int(os.environ.get("TRICORDER_PORT", "8090"))
GEMMA_URL = os.environ.get(
    "GEMMA_URL", "http://127.0.0.1:8080/v1/chat/completions"
)
ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
SNAPSHOT = ROOT / "last.png"

SYSTEM = (
    "You are a Starfleet tricorder. Reply with one sentence, no more than 25 words. "
    "Describe what the image shows as concisely as possible. Read text if possible."
    "If the picture is too unclear, say what the sensors cannot resolve. "
    "Do not mention being a language model."
)

lock = threading.Lock()
cond = threading.Condition(lock)
state = {
    "phase": "idle",
    "report": "",
    "error": "",
    "has_image": False,
    "pending": 0,
}


def set_state(**updates):
    with lock:
        state.update(updates)


def snapshot_state():
    with lock:
        return dict(state)


def request_scan():
    with cond:
        state["pending"] += 1
        state["phase"] = "waiting_camera"
        state["report"] = ""
        state["error"] = ""
        cond.notify_all()
    threading.Thread(target=camera_timeout, daemon=True).start()


def camera_timeout():
    time.sleep(25)
    with lock:
        if state["phase"] == "waiting_camera":
            state["phase"] = "error"
            state["error"] = "The camera link did not answer."


def wait_for_scan():
    with cond:
        if state["pending"] == 0:
            cond.wait(timeout=25)
        if state["pending"] == 0:
            return False
        state["pending"] -= 1
        return True


def message_text(message):
    content = message.get("content", "")
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            elif isinstance(part, str):
                parts.append(part)
        content = "".join(parts)
    if not content:
        content = message.get("reasoning_content") or ""
    return str(content).strip()


def ask_gemma(png):
    import base64

    body = {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64," + base64.b64encode(png).decode()
                        },
                    },
                    {"type": "text", "text": "File your report."},
                ],
            },
        ],
        "max_tokens": 40,
        "temperature": 0.8,
    }
    req = urllib.request.Request(
        GEMMA_URL,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode())
    return message_text(payload["choices"][0]["message"])


def read_report(png):
    set_state(phase="reading", error="", report="")
    try:
        report = ask_gemma(png)
        if not report:
            set_state(phase="error", error="The model returned an empty report.")
            return
        set_state(phase="done", report=report, error="")
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, OSError) as exc:
        set_state(phase="error", error=f"The board could not finish the reading. {exc}")


class Server(ThreadingHTTPServer):
    # macOS resolves roarduino.local to the Wi-Fi link-local IPv6 address
    # before the IPv4 address. Listen on both.
    address_family = socket.AF_INET6
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def send_bytes(self, code, body, content_type):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self.send_bytes(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/status":
            self.send_bytes(200, json.dumps(snapshot_state()), "application/json")
            return
        if path == "/snapshot":
            if not SNAPSHOT.exists():
                self.send_bytes(404, b"", "image/png")
                return
            self.send_bytes(200, SNAPSHOT.read_bytes(), "image/png")
            return
        if path == "/capture-request":
            ready = wait_for_scan()
            self.send_bytes(200, json.dumps({"scan": ready}), "application/json")
            return
        self.send_bytes(404, b"not found", "text/plain")

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        if path == "/request-scan":
            request_scan()
            self.send_bytes(200, json.dumps({"ok": True}), "application/json")
            return
        if path == "/scan":
            if not body.startswith(b"\x89PNG"):
                self.send_bytes(400, b"expected a PNG", "text/plain")
                return
            SNAPSHOT.write_bytes(body)
            set_state(has_image=True, phase="reading", report="", error="")
            threading.Thread(target=read_report, args=(body,), daemon=True).start()
            self.send_bytes(202, json.dumps({"ok": True}), "application/json")
            return
        if path == "/scan-failed":
            message = body.decode(errors="replace").strip() or "The camera did not send a frame."
            set_state(phase="error", error=message)
            self.send_bytes(200, json.dumps({"ok": True}), "application/json")
            return
        self.send_bytes(404, b"not found", "text/plain")


def main():
    STATIC.mkdir(parents=True, exist_ok=True)
    server = Server((HOST, PORT), Handler)
    print(f"tricorder http://0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
