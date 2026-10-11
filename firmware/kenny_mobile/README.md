# KENNY mobile joystick

Open **kenny_mobile.ino** with **config.h**, **control.h** and **web_ui.h** beside
it. Arduino IDE board: **ESP32 Dev Module**, Espressif core **3.3.12**.

Select the actual wiring in config.h before upload:

- **KENNY_DIRECT_GPIO** (default): independent L298N/breadboard GPIO connections;
  E-stop and encoder inputs disabled, so GPIO15 can remain unconnected.
- **KENNY_CARRIER_MCP23017**: new carrier PCB; expander directions, E-stop GPIO18.

Direct mode matches the confirmed motor wiring: L298N #1 OUT1/2 = left-rear,
OUT3/4 = left-front; #2 OUT1/2 = right-front, OUT3/4 = right-rear.
Keep the driver-to-ESP32 control wires as documented in the full guide.
The controller matches the verified ALL+/ALL-/LEFT/RIGHT motor-test directions.
In the default encoder-free mode, at 100% speed and full forward, reverse or
sideways joystick travel, all four wheels receive 255/255 PWM after the direction
pause and ramp. Release stops; Master Control also disarms.

For wired hardware, set `KENNY_ESTOP_ENABLED` and/or `KENNY_ENCODERS_ENABLED`
to `1` before their `#ifndef` defaults in config.h. Carrier mode enables both
by default. Without encoders the controller uses open-loop PWM, not measured
speed feedback. The slider starts at 100%; full straight joystick travel at 25%
produces about 63/255 PWM, matching KennyBreadboardControl's percentage scale.
Open-loop PWM is 10 kHz, with a 500 ms coast before applying a new direction.
Encoder-feedback operation retains the 90/255 commissioning cap and 20 kHz PWM.
A breadboard alone lets you test the joystick/GPIO outputs;
motors require powered drivers and the documented wiring.

Phone Wi-Fi: **KENNY-Robot**, password **KennyDrive!2026**, page
**http://192.168.4.1/**. Arm, hold/drag, release to zero; STOP disarms. Motors
start disabled. No internet/app/additional Arduino libraries are needed.

Select **Master Control →** or open **http://192.168.4.1/#master** for a view with
only the speed slider and joystick. Touch-and-hold requests arming; release stops
and disarms. Browser Back returns to diagnostics. Opening the view does not arm.

Full guide: [`docs/ESP32_MOBILE_CONTROLLER.md`](../../docs/ESP32_MOBILE_CONTROLLER.md).
Edit `web/index.html`, then regenerate web_ui.h with `scripts/build_mobile_ui.py`.
Test on raised wheels and resolve driver sizing for the 2.4 A-stall motors
before loaded operation. Software tests do not validate physical hardware.
