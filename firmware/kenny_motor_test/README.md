# Individual and all-motor tests

Use this standalone sketch when the original working controller and the mobile
controller both show missing motors or one-direction-only movement. It helps
separate a channel/wiring fault from the joystick mixing. It does not measure
voltage, current, or actual wheel motion.

1. Raise all wheels and turn motor power off.
2. Upload `kenny_motor_test.ino` to the classic ESP32-WROOM with Arduino-ESP32 3.x.
3. Open Serial Monitor at **115200 baud** with Newline or Both NL & CR selected.
4. Turn motor power on. Send one command at a time and observe the physical wheel.

| Physical wheel | Driver outputs | Positive test | Negative test | Enable | Direction pins |
| --- | --- | --- | --- | --- | --- |
| Left-front | #1 OUT3/4 | `LF+` | `LF-` | ENB GPIO26 | IN3 GPIO18, IN4 GPIO19 |
| Right-front | #2 OUT1/2 | `RF+` | `RF-` | ENA GPIO32 | IN1 GPIO21, IN2 GPIO22 |
| Left-rear | #1 OUT1/2 | `LR+` | `LR-` | ENA GPIO25 | IN1 GPIO16, IN2 GPIO17 |
| Right-rear | #2 OUT3/4 | `RR+` | `RR-` | ENB GPIO33 | IN3 GPIO4, IN4 GPIO5 |

Once individual wheels work in both directions, use these combined commands:

| Command | Left-front / left-rear | Right-front / right-rear |
| --- | --- | --- |
| `ALL+` | Forward | Forward |
| `ALL-` | Reverse | Reverse |
| `LEFT` | Reverse | Forward |
| `RIGHT` | Forward | Reverse |
| `STOP` | Stopped | Stopped |

These physical directions assume motor polarity was corrected during individual tests.
Each test first stops all outputs, waits 500 ms, then powers the selected
motors at **255/255 PWM (100%)** for **1.5 seconds**. `STOP` cancels a pending or
running test. Nothing starts automatically on boot. No Wi-Fi or encoder feedback
is used. Keep the wheels unloaded for these tests.

Record which wheel moves and whether it turns physically forward/backward for
both signs. A wheel should respond in opposite directions to `+` and `-`.
If only one sign works, check both direction connections and the driver channel.
If neither sign works, check its enable connection, motor output connections,
driver logic/motor supply, and common ground. Turn motor power off before changing
wires. Correct reversed motor polarity only after the channel works in both signs.

Remove ENA/ENB jumpers for GPIO PWM. This test does not require adding resistors,
but without hardware pull-downs motor inactivity during reset is not guaranteed.
Restore `firmware/kenny_mobile/kenny_mobile.ino` after testing to use the phone
controller again. This sketch is for the direct wiring, not the MCP23017 carrier.
