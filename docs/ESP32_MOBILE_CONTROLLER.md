# KENNY ESP32 Wi-Fi joystick

The ESP32 hosts its own Wi-Fi network and self-contained phone web page. No phone
app, internet connection, Pi process or extra Arduino library is required after
flashing. This is **manual commissioning control**, not autonomous navigation.

## Select the wiring before upload

Open `firmware/kenny_mobile/config.h`. Use **one** of these settings:

```cpp
// Earlier independent ESP32-to-L298N wiring (shipped default):
#define KENNY_WIRING KENNY_DIRECT_GPIO

// Replace the line above with this for the new carrier PCB:
#define KENNY_WIRING KENNY_CARRIER_MCP23017
```

The modes have different direction and E-stop connections. The phone page and
USB startup message identify the selected mode. Do not upload direct mode onto
the carrier PCB: GPIO16/17/21/22 have different purposes there.

Direct-GPIO mode ships with **E-stop and encoder inputs disabled** for a bare
breadboard. Leave GPIO15 unconnected: it is not read and cannot block arming.
Unconnected encoder pins have no interrupts attached and cannot produce faults.
Hold the joystick at **http://192.168.4.1/#master** to command outputs and release
to stop. A breadboard does not drive motors by itself; use the connections below
for motors, and avoid connecting separate GPIO outputs to the same breadboard row.

After wiring an E-stop contact and encoders, add these settings **before their
`#ifndef` defaults** in `config.h` and upload again:

```cpp
#define KENNY_ESTOP_ENABLED 1
#define KENNY_ENCODERS_ENABLED 1
```

Each setting is independent. Carrier mode defaults to both enabled. With encoders
disabled, PWM uses the existing target ramp and maps straight travel directly to
the slider percentage, without PI feedback or encoder faults. At full forward
joystick travel, 25% gives about 63/255 PWM and 100% gives 255/255.
This matches the working KennyBreadboardControl sketch’s percentage scale;
PWM is 10 kHz and direction changes wait 500 ms before power is applied.
Combined forward/turn commands are rescaled together to preserve curvature.
Pure left turns command both left motors in reverse and both right motors forward;
pure right turns do the opposite. Pure turns use the same PWM percentage as
straight travel at the same slider setting, rather than reducing it by track width.
RPM/counts are shown as unavailable, not simulated;
the speed slider is a command scale, not a measured speed guarantee.

### Direct-GPIO mode: classic 38-pin ESP32-WROOM

Numbers below are printed **GPIO labels**, not physical header positions.
This direct-wiring table matches the confirmed motor connections: L298N #1
drives the left side (#1 A rear, #1 B front), and #2 drives the right side.

| Motor | External driver | Red / white | Direction terminals → GPIO | Enable → GPIO | Yellow A / green B → GPIO |
| --- | --- | --- | --- | --- | --- |
| Left-front | L298N #1 B | OUT3 / OUT4 | IN3 → 18, IN4 → 19 | ENB → 26 | 34 / 27 |
| Right-front | L298N #2 A | OUT1 / OUT2 | IN1 → 21, IN2 → 22 | ENA → 32 | 35 / 14 |
| Left-rear | L298N #1 A | OUT1 / OUT2 | IN1 → 16, IN2 → 17 | ENA → 25 | 36 (VP) / 13 |
| Right-rear | L298N #2 B | OUT3 / OUT4 | IN3 → 4, IN4 → 5 | ENB → 33 | 39 (VN) / 23 |

All encoder **blue → stable 3.3 V**, **black → common GND**, as permitted by the
[identified supplier](https://precisionminidrives.com/product/37mm-gear-motor-with-encoder-41mm-type-model-nfp-jgb37-520-en).
GPIO34/35/36/39 have no internal pull-ups; this encoder has output pull-up circuitry.
Encoder pins above are the intended connections by physical wheel; verify them
before enabling encoder feedback. The default encoder-free setup does not read them.

- Remove all ENA/ENB jumpers; use **10 kΩ enable-to-GND pull-downs**.
- Preserve GPIO5's default boot HIGH level with the documented **10 kΩ pull-up
  to 3.3 V**. PWM pull-downs keep motors disabled during reset.
- Optional enabled E-stop input: **GPIO15 → normally-closed auxiliary contact → GND**. Open=stop.
  GPIO15 LOW suppresses ROM boot messages on classic ESP32 but permits flash boot.
- Power motors from their appropriate fused/switched **12 V motor supply**,
  never from the ESP32/Pi. Join ESP32, encoder, driver and supply-return grounds.
- Configure L298N logic-supply/regulator jumpers according to the exact modules;
  do not back-power USB/ESP32. The physical motor-power E-stop is separate.
- This mapping is for **WROOM**, not WROVER/S3/C3. GPIO16/17/21/22 are used for
  motor directions, so do not add the carrier sensor connections in direct mode.

### Carrier-PCB mode

Use the terminal blocks in [the carrier wiring guide](CARRIER_WIRING.md):

- Direct PWM: **LF 25, RF 26, LR 32, RR 33**; encoder GPIOs unchanged.
- E-stop: **J9 → GPIO18**, not GPIO15.
- I²C **SDA21/SCL22**, 100 kHz, MCP23017 at **0x20**.
- Directions: **GPB0/1 LF, GPB2/3 RF, GPB4/5 LR, GPB6/7 RR**.
- HX711 GPIO16/17 remain reserved; SCK is held LOW. This sketch controls motors
  and reports encoders, but **does not yet read MPU6050 or load-cell measurements**.

The expander's latch is zeroed before its direction outputs are enabled. Unused
port A remains input with pull-ups. I²C transactions have a 10 ms timeout, and
direction mode/latch are checked approximately every 100 ms. An I²C error or
unexpected expander reset zeros all direct PWM enables and disarms. Fix the
connection and **restart the ESP32**; recovery does not automatically re-arm.

## Upload

Open **`firmware/kenny_mobile/kenny_mobile.ino`** in Arduino IDE. Keep **config.h,
control.h and web_ui.h** beside it. Install **esp32 by Espressif Systems 3.3.12**,
select **ESP32 Dev Module**, select the verified ESP32 USB port, choose the wiring,
and upload initially with motor power disconnected.

WiFi, WebServer and Wire are included in the ESP32 core. The sketch uses the
Arduino-ESP32 **3.x** LEDC API. Serial Monitor at **115200 baud** shows the mode
and URL. USB serial also accepts the `KENNY_USB_V1` command interface alongside
Wi-Fi. See [USB control](USB_CONTROL.md) for the local browser bridge and protocol.
The earlier standalone controller's ARM/V protocol differs: this sketch requires
the session lease returned by ARM in each V command.

### Arduino CLI

Install Arduino CLI and the Espressif 3.3.12 core. On the development Pi, the CLI
is at `~/.local/bin/arduino-cli`; these commands assume it is on PATH:

```bash
cd ~/joystick
python3 scripts/build_mobile_ui.py
# Direct GPIO build:
arduino-cli compile --fqbn esp32:esp32:esp32 --jobs 2 --warnings all \
  --build-property compiler.cpp.extra_flags=-DKENNY_WIRING=1 firmware/kenny_mobile
# Carrier PCB build:
arduino-cli compile --fqbn esp32:esp32:esp32 --jobs 2 --warnings all \
  --build-property compiler.cpp.extra_flags=-DKENNY_WIRING=2 firmware/kenny_mobile
```

For upload, set `config.h` to the actual mode and compile without an override.
Identify the board with `arduino-cli board list`; never select the LiDAR adapter:

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 --jobs 2 firmware/kenny_mobile
arduino-cli upload --fqbn esp32:esp32:esp32 \
  --port /dev/serial/by-id/YOUR_VERIFIED_ESP32_DEVICE firmware/kenny_mobile
```

## Phone connection and controls

| Setting | Default |
| --- | --- |
| Wi-Fi network | **KENNY-Robot** |
| Password | **KennyDrive!2026** |
| Page | **http://192.168.4.1/** |

Join the network, choose **stay connected** if the phone reports no internet,
and open the HTTP address in Safari/Chrome. Disable automatic Wi-Fi switching
if it prevents reaching the page. Verify the displayed wiring/E-stop state.

With all wheels raised for the first test: **Arm**, then hold and drag:

- Up=forward, down=reverse, left/right=turn; horizontal movement rotates in place.
- Release centers the joystick and sends exact zero requests. The session stays
  ready for another touch while fresh neutral heartbeats continue.
- **STOP & DISARM** ends the control session.
- Speed limit defaults to **100%**, scaling both speed and turn rate.
- Leaving/hiding the page, interrupted touch capture, failed/rejected commands
  disarm the UI. Re-arm deliberately to continue.
- Only one active control lease is accepted. Another browser cannot take over
  an armed controller; STOP is available to anyone on the local access point.

The default password is published in source. Change it in `config.h` before
regular use. This is a local WPA-protected AP with plain HTTP, not an
internet-facing or certified robot-control service.

## Dedicated Master Control

Select **Master Control →** in the full interface or bookmark
**http://192.168.4.1/#master**. The minimal view contains only the speed slider
and joystick: no dashboard, connection instructions, telemetry, Arm or STOP buttons.
The slider supports **0–100%** here and scales both speed and turn rate.

- **Touch and hold:** requests a new control lease, then drives only after the
  ARM acknowledgement and only while that same gesture is still held.
- **Release:** sends STOP and disarms. The next deliberate gesture obtains a new
  lease; it may need to wait briefly for fresh status confirming readiness.
- Releasing before ARM completes never sends motion, even if the reply arrives late.
- Loading the view or moving the speed slider does not arm the controller.
- Switching into/out of Master Control stops/disarms and waits for a STOP
  acknowledgement. If it is lost, fresh disarmed status can confirm stopping.
  Otherwise return to the full UI and press STOP to retry, or reconnect.
- Hardware/connection/E-stop gates and the firmware watchdog remain active.
  A disabled/red joystick indicates an unavailable controller. Status messages
  remain available to assistive technology; use browser Back to view diagnostics.

The full interface retains its explicit Arm and STOP controls and neutral-session
behavior described above. The minimal interface is an alternative view, not an
alternative motor-command path.

## Control limits and behavior

- Requested speed **±0.10 m/s**, turn **±0.60 rad/s**; individual wheel commands
  rescaled together to **±0.10** without encoders or **±0.15 m/s** with encoder
  feedback, while preserving curvature. Without encoders these are PWM scales.
- PWM: 8-bit. Without encoders: **10 kHz**, up to **255/255**, controlled by
  the slider (default 100%). With encoders: **20 kHz**, commissioning cap **90/255**.
- Motor updates at approximately **100 Hz**; encoder-feedback speed loops when enabled.
- Browser commands about every **60 ms**, normally one outstanding drive request.
  In the full interface, release sends a priority zero even if an earlier request
  is still pending. Master Control release sends STOP and disarms instead.
- **300 ms** without a fresh accepted command → zero targets and disarm.
- Replays/out-of-order sequences do not refresh the watchdog. Each deliberate
  ARM creates a random lease; old packets cannot re-arm/drive a new session.
- HTTP handlers enqueue commands; a separate FreeRTOS motor task owns outputs.
  A slow HTTP client does not directly block watchdog/PID processing. Urgent
  STOP clears queued ARM/drive messages; a motor-loop gap over 100 ms disarms.

Default **1320 x4 counts/revolution** comes from 11 PPR × 30:1 × 4. Confirm it by
hand rotation. Forward rotation must increase the count; correct each motor's
`encoderSign` if necessary. The page shows all four counts, RPM and actual PWM.

KP=1.5, KI=0.5 and nominal 333 RPM feedforward apply only with encoders.
The 40 RPM/s target ramp applies in both modes. These are **untuned starting values**.
Direction changes insert at least **500 ms** with enable LOW without encoders,
or **50 ms** with encoder feedback and a wait for opposing measured rotation to slow.
Missing/wrong-direction
encoder feedback can latch an encoder fault; it is not current protection.

Zero PWM can **coast**, not actively brake. Verify wiring, polarity, encoder
signs, watchdog/E-stop and stopping latency on raised wheels before floor tests.
These 333 RPM motors specify **2.4 A stall current per motor**, exceeding the
common L298N continuous-channel rating; resolve driver/current/thermal sizing
before loaded use. The joystick does not avoid obstacles or detect cliffs.

## Faults and API

| Bit | Fault |
| --- | --- |
| 1 | Command watchdog expired |
| 2 | E-stop contact open |
| 4 | Invalid/nonfinite/out-of-bounds command |
| 8 | Encoder missing/opposite direction, or motor cannot move at the PWM cap |
| 16 | Control-loop timing stall |
| 32 | Encoder configuration missing |
| 64 | PWM initialization failure |
| 128 | MCP23017 I²C/latch failure; fix connection and restart |

STOP waits for an acknowledgement, clears the local lease/cached armed state,
and refreshes status. Late pre-STOP status replies cannot lock Arm again. If
the reply fails, a fresh disarmed status can restore view readiness; otherwise
press STOP again to retry. E-stop and hardware readiness must still be valid.
The full UI explains the blocking reason directly below the Arm button.

If Arm is disabled, read that explanation, mode, E-stop, ready state and faults. If another session
is still armed after a reload, use STOP or wait for watchdog expiry. Inspect
driver power, jumpers, grounds and motor/encoder signs if movement fails.

- `GET /api/status`: mode, armed/ready/E-stop/faults, counts/RPM/PWM and limits.
- `POST /api/arm`: activation; returns a new `lease`.
- `POST /api/drive`: form fields `lease`, uint32 `seq`, `v` m/s, `w` rad/s.
- `POST /api/stop`: urgent stop/disarm, no lease required.

## Verification and editing

Both modes compile with Espressif core 3.3.12. Host checks cover ownership,
numeric bounds/NaNs, stale queue, replay, counter wrap, watchdog/release/E-stop
and 10,000 wheel-limit cases. Chromium exercises the actual page at phone size:
touch drag, forward/reverse/turn, release during a pending request, STOP, blur,
command rejection and E-stop lockout. Master Control checks also verify exactly
two visible controls, gesture-only arming, release/canceled-ARM handling, zero
speed and view-change stopping. **Browser telemetry is simulated**; radio,
physical timing and motor behavior remain untested until an ESP32 is connected.

```bash
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined \
  tests/mobile_control_test.cpp -o /tmp/kenny-mobile-control-test
/tmp/kenny-mobile-control-test
# Requires Playwright and its Chromium browser in a test venv:
python tests/check_mobile_browser.py
# Explicitly refresh documentation screenshots after the checks pass:
python tests/check_mobile_browser.py --refresh-previews
```

Edit `firmware/kenny_mobile/web/index.html`, then run
`python3 scripts/build_mobile_ui.py` before compiling. The complete page is
embedded in flash; no CDN, online fonts or external assets are fetched.
`artifacts/mobile/joystick-preview.png` shows **mock telemetry** from the browser
check. This repository contains source/instructions, not an already-flashed ESP32.
