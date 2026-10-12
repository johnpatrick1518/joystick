"""Exercise the real serial transport with a pseudo-terminal ESP32."""
import importlib.util
import json
import os
from pathlib import Path
import pty
import threading
import unittest
from unittest.mock import patch, Mock
from http.server import ThreadingHTTPServer
import urllib.request
import urllib.error

spec = importlib.util.spec_from_file_location("usb_bridge", Path(__file__).resolve().parents[1] / "scripts/usb_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BridgeTests(unittest.TestCase):
    def test_browser_http_adapter(self):
        link = Mock()
        link.request.return_value = {"armed": False, "wiring": "Direct GPIO"}
        server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.handler_for(link, 0))
        port = server.server_address[1]
        server.RequestHandlerClass = bridge.handler_for(link, port)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://localhost:{port}"
        try:
            with urllib.request.urlopen(base + "/api/status") as response:
                self.assertIn("USB serial", json.load(response)["wiring"])
            link.request.assert_called_with("STATUS")
            link.request.return_value = {"ok": True}
            with urllib.request.urlopen(urllib.request.Request(base + "/api/stop", data=b"")) as response:
                self.assertTrue(json.load(response)["ok"])
            link.request.assert_called_with("STOP")
            with self.assertRaises(urllib.error.HTTPError) as rejected:
                urllib.request.urlopen(urllib.request.Request(base + "/api/drive", data=b"v=nan"))
            self.assertEqual(rejected.exception.code, 400)
            link.request.assert_called_with("STOP")
            with urllib.request.urlopen(base + "/") as response:
                self.assertIn(b'step="5" value="20"', response.read())
        finally:
            server.shutdown()
            server.server_close()

    def test_serial_handshake_and_commands(self):
        master, slave = pty.openpty()
        seen = []

        def esp32():
            buffer = b""
            while True:
                buffer += os.read(master, 128)
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    command = line.decode().strip()
                    seen.append(command)
                    result = {"ok": True}
                    if command == "HELLO":
                        result["protocol"] = "KENNY_USB_V1"
                    elif command == "STATUS":
                        result = {"armed": False, "pwm": [0, 0, 0, 0]}
                    os.write(master, json.dumps(result).encode() + b"\n")
                    if len(seen) == 4:
                        return

        worker = threading.Thread(target=esp32, daemon=True)
        worker.start()
        try:
            with patch.object(bridge.time, "sleep"):
                link = bridge.UsbLink(os.ttyname(slave))
            self.assertEqual(link.request("STATUS")["pwm"], [0, 0, 0, 0])
            link.close()
            worker.join(1)
            self.assertEqual(seen, ["HELLO", "STOP", "STATUS", "STOP"])
        finally:
            os.close(master)
            os.close(slave)

    def test_invalid_motion(self):
        for bad in ("nan", "inf", "0.11", "-0.11"):
            with self.assertRaises(ValueError):
                bridge.drive_command({"lease": ["123"], "seq": ["1"], "v": [bad], "w": ["0"]})
        self.assertEqual(bridge.drive_command({"lease": ["123"], "seq": ["1"], "v": ["0.03"], "w": ["0"]}),
                         "V 123 1 0.03000 0.00000")


if __name__ == "__main__":
    unittest.main()
