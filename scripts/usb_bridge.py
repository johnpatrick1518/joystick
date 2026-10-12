"""Serve the existing joystick over localhost, forwarding commands over USB.

Install pyserial, then: python3 scripts/usb_bridge.py --port /dev/ttyUSB0
No motion is generated automatically. Browser heartbeats refresh the watchdog.
"""
import argparse
import json
import math
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import serial

ROOT = Path(__file__).resolve().parents[1]


class UsbLink:
    def __init__(self, port):
        self.lock = threading.Lock()
        self.serial = serial.Serial()
        self.serial.port = port
        self.serial.baudrate = 115200
        self.serial.timeout = 0.05
        self.serial.write_timeout = 0.2
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.exclusive = True
        self.serial.open()
        # Some USB bridges reset on open, even with DTR/RTS deasserted.
        time.sleep(2)
        self.serial.reset_input_buffer()
        hello = self.request("HELLO")
        if hello.get("protocol") != "KENNY_USB_V1":
            self.serial.close()
            raise RuntimeError("Upload the USB-enabled joystick firmware first")
        self.request("STOP")

    def request(self, command):
        with self.lock:
            self.serial.write((command + "\n").encode("ascii"))
            deadline = time.monotonic() + 0.4
            while time.monotonic() < deadline:
                line = self.serial.readline()
                if not line:
                    continue
                try:
                    response = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue  # Ignore boot diagnostics, never treat them as ACKs.
                if isinstance(response, dict):
                    return response
            # Do not allow an acknowledgement arriving late to match another call.
            self.serial.write(b"STOP\n")
            self.serial.close()
            raise RuntimeError("ESP32 response timed out; restart bridge to reconnect")

    def close(self):
        if self.serial.is_open:
            try:
                self.request("STOP")
            finally:
                self.serial.close()


def drive_command(values):
    lease, seq = int(values["lease"][0]), int(values["seq"][0])
    v, w = float(values["v"][0]), float(values["w"][0])
    if not 0 < lease <= 0xFFFFFFFF or not 0 <= seq <= 0xFFFFFFFF:
        raise ValueError("Invalid lease or sequence")
    if not math.isfinite(v) or not math.isfinite(w) or abs(v) > 0.1 or abs(w) > 0.6:
        raise ValueError("Velocity outside controller limits")
    return f"V {lease} {seq} {v:.5f} {w:.5f}"


def handler_for(link, port):
    page = (ROOT / "firmware/kenny_mobile/web/index.html").read_text()
    page = page.replace("Join <strong>KENNY-Robot</strong> Wi-Fi and open <strong>http://192.168.4.1</strong>.",
                        "Connected through the computer's USB data cable. Open <strong>http://localhost:%s</strong>." % port)
    page = page.replace("Connect to KENNY-Robot Wi-Fi and open http://192.168.4.1/.",
                        "Check the USB cable and restart scripts/usb_bridge.py.")
    # Start USB commissioning at modest power, preserving Wi-Fi UI defaults.
    page = page.replace('id="limitValue">100%', 'id="limitValue">20%')
    page = page.replace('step="5" value="100"', 'step="5" value="20"')

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, body, content_type="application/json"):
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def valid_origin(self):
            host = self.headers.get("Host", "")
            allowed = {f"localhost:{port}", f"127.0.0.1:{port}"}
            origin = self.headers.get("Origin")
            return host in allowed and (not origin or origin in {"http://" + h for h in allowed})

        def do_GET(self):
            if not self.valid_origin():
                self.reply(403, {"ok": False, "error": "Use localhost"})
                return
            path = urlsplit(self.path).path
            if path == "/":
                self.reply(200, page, "text/html; charset=utf-8")
            elif path == "/api/status":
                self.forward_command("STATUS")
            else:
                self.reply(404, {"ok": False})

        def forward_command(self, command):
            try:
                result = link.request(command)
                if command == "STATUS":
                    result["wiring"] = result.get("wiring", "") + " · USB serial"
                self.reply(409 if result.get("ok") is False else 200, result)
            except (OSError, RuntimeError, serial.SerialException) as error:
                self.reply(503, {"ok": False, "error": str(error)})

        def do_POST(self):
            if not self.valid_origin():
                self.reply(403, {"ok": False, "error": "Use localhost"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 512:
                    raise ValueError("Request too large")
                values = parse_qs(self.rfile.read(length).decode("ascii"))
                path = urlsplit(self.path).path
                commands = {"/api/arm": "ARM", "/api/stop": "STOP"}
                command = drive_command(values) if path == "/api/drive" else commands.get(path)
                if command is None:
                    self.reply(404, {"ok": False})
                    return
            except (ValueError, KeyError, UnicodeDecodeError) as error:
                try:
                    link.request("STOP")
                except (OSError, RuntimeError, serial.SerialException):
                    pass
                self.reply(400, {"ok": False, "error": str(error)})
                return
            self.forward_command(command)

        def log_message(self, format, *args):
            pass  # Heartbeats generate many requests; display errors in the UI.

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="ESP32 USB serial device")
    parser.add_argument("--http-port", type=int, default=8765)
    args = parser.parse_args()
    link = UsbLink(args.port)
    server = ThreadingHTTPServer(("127.0.0.1", args.http_port), handler_for(link, args.http_port))
    print(f"ESP32 connected. USB joystick: http://localhost:{args.http_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        link.close()


if __name__ == "__main__":
    main()
