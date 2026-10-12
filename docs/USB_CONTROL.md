# USB + Wi-Fi control for the installed Kenny ESP32

The matching firmware is `firmware/kenny_mobile/kenny_mobile.ino` in this
`joystick` repository. It preserves the installed direct-GPIO motor arrangement,
E-stop/encoder configuration, PWM settings, and Wi-Fi joystick. USB and Wi-Fi
share **one control lease**: a second controller cannot arm while another is
armed. STOP is available through either connection.

## Connect and run

Connect the ESP32's Type-C socket to this computer using a **USB data cable**.
The CP2102 bridge on this machine appears as:

```text
/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
```

Close Arduino Serial Monitor before starting the bridge. From `/home/kenny/joystick`:

```bash
python3 -m pip install pyserial  # Only if it is not already installed.
python3 scripts/usb_bridge.py \
  --port /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
```

Open **http://localhost:8765/** on this computer, or select **ESP32 USB control**
on the Kenny app home screen at **http://localhost:5173/**. The USB page starts
at **20% power**. It uses the existing joystick and displays real ESP32 status
and PWM. With encoders disabled, RPM and physical speed are not measured.
`localhost` means the computer hosting the bridge; opening this link on a phone
does not reach the Pi. For phone control, use the ESP32 Wi-Fi page below.

The bridge works in Firefox/Chrome because Python owns the serial port; Web
Serial browser support is not required. The bridge binds to loopback only.
Restart it after unplugging/reconnecting USB or uploading firmware.

## Firmware upload

With motor power disconnected, from `/home/kenny/joystick`:

```bash
~/.local/bin/arduino-cli compile --fqbn esp32:esp32:esp32 --jobs 2 --warnings all firmware/kenny_mobile
~/.local/bin/arduino-cli upload --fqbn esp32:esp32:esp32 \
  --port /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0 \
  firmware/kenny_mobile
```

The startup message includes `KENNY_USB_V1`. This firmware also keeps Wi-Fi
**KENNY-Robot**, password **KennyDrive!2026**, and **http://192.168.4.1/**.

## Protocol and communication code

115200 baud, 8-N-1; ASCII commands terminated by newline, at most 95 characters.
Every complete command gets a single JSON response. Startup diagnostics are
plain text and must be ignored when waiting for JSON. No automatic telemetry
stream: request STATUS to avoid mixing command replies with status data.

| Command | Response / behavior |
| --- | --- |
| `HELLO` | `{"ok":true,"protocol":"KENNY_USB_V1","baud":115200}` |
| `STATUS` | Same JSON fields as Wi-Fi `/api/status`, including armed, faults, counts, RPM, PWM |
| `ARM` | Arms at zero and returns `{"ok":true,"lease":...}`; refuses an occupied session |
| `V <lease> <sequence> <linear> <angular>` | Updates motion for that lease; increasing uint32 sequence |
| `STOP` | Stops/disarms; returns `{"ok":true}` after motor-task acknowledgement |

Send V every **50–60 ms** while armed, including zero commands while idle.
The ESP32's **300 ms watchdog** disarms if messages stop. Allowed requests:
linear ±0.10, angular ±0.60. In the installed open-loop mode these values scale
PWM rather than specifying a verified speed. Invalid/malformed lines stop;
wrong leases/replayed sequences are rejected without refreshing the watchdog.

`scripts/usb_bridge.py` provides reusable `UsbLink.request(command)` and
`UsbLink.close()` methods. It identifies the firmware, sends STOP on connection
and orderly shutdown, serializes requests, and closes the serial session after
a reply timeout. It forwards browser V heartbeats; it never keeps motion alive
after a browser stops sending commands.

## First motion test

1. Raise all four wheels and open the USB diagnostics page.
2. Verify actual wiring, readiness, feedback mode and zero PWM before arming.
3. Keep the initial 20% power setting. Press Arm, hold forward briefly, and
   release. Check all four wheel directions; STOP & DISARM must zero all PWM.
4. Test a turn and reverse, then verify closing/hiding the page and unplugging
   USB stop commands through the watchdog. Wheels may coast.
5. Stop the USB session before arming the phone Wi-Fi controller; test that the
   second interface cannot take over an armed session.

The installed breadboard configuration has E-stop input and encoder feedback
disabled. The app's marker tracking/navigation provider remains simulated;
this USB interface is manual motor control and real telemetry. Autonomous
pickup requires the separate sensor/localization/navigation integration.

## Checks

```bash
g++ -std=c++17 -Wall -Wextra -Werror tests/usb_protocol_test.cpp -o /tmp/kenny-usb-test
/tmp/kenny-usb-test
python3 -m unittest discover -s tests -p test_usb_bridge.py -v
```

The Python test exercises the actual serial transport against a pseudo-terminal
ESP32, including identification, startup STOP, status and shutdown STOP.

## Verified on the connected board — 2026-10-12

- Compiled with Arduino-ESP32 3.3.12 and uploaded to the connected ESP32-D0WD-V3.
- HELLO identification, real STATUS telemetry, ARM with zero commands, STOP
  acknowledgement and the 300 ms command-loss watchdog passed over USB.
- Opened the Kenny app and followed its USB control link in Chromium; the page
  connected at 20% power, with no JavaScript errors.
- Final board state: ready, disarmed, no faults, PWM `[0, 0, 0, 0]`.
- No nonzero motor commands were sent. Physical wheel movement, polarity and
  loaded behavior remain to be tested using the raised-wheel procedure above.
