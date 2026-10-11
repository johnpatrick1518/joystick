# Kenny carrier-PCB wiring

Select **`KENNY_CARRIER_MCP23017`** in `firmware/kenny_mobile/config.h` for the
sensor-equipped carrier. This repository contains firmware and the wiring
contract, not the full KiCad PCB design. Verify the actual carrier revision,
DevKit fit and physical wiring before use.

## Encoder terminal blocks

| Terminal | Encoder | Yellow A → GPIO | Green B → GPIO |
| --- | --- | --- | --- |
| J1 | Left-front | 34 | 27 |
| J2 | Right-front | 35 | 14 |
| J3 | Left-rear | 36 / VP | 13 |
| J4 | Right-rear | 39 / VN | 23 |

Every block: **1 blue +3V3, 2 black GND, 3 yellow A, 4 green B**. The selected
encoder supports 3.3 V. Red/white winding wires connect directly to driver outputs,
not to these encoder terminals.

## L298N logic terminal blocks

| Pin | J7: front L298N #1 | J8: rear L298N #2 |
| --- | --- | --- |
| 1 | GND | GND |
| 2 | ENA: LF PWM GPIO25 | ENA: LR PWM GPIO32 |
| 3 | IN1: LF direction GPB0 | IN1: LR direction GPB4 |
| 4 | IN2: LF direction GPB1 | IN2: LR direction GPB5 |
| 5 | IN3: RF direction GPB2 | IN3: RR direction GPB6 |
| 6 | IN4: RF direction GPB3 | IN4: RR direction GPB7 |
| 7 | ENB: RF PWM GPIO26 | ENB: RR PWM GPIO33 |

**GPB numbers are MCP23017 bits, not ESP32 GPIOs.** Expander address pins are
grounded for **0x20**, on **SDA21/SCL22**. Every direction signal is independent.
The firmware zeros OLATB before enabling port-B outputs.

- L298N #1 OUT1/OUT2 → LF red/white; OUT3/OUT4 → RF red/white.
- L298N #2 OUT1/OUT2 → LR red/white; OUT3/OUT4 → RR red/white.

Swap an individual motor's winding polarity if positive requests run backward.
Remove all ENA/ENB jumpers. The carrier has enable/direction pull-downs; add
driver-side pull-downs if drive must stay disabled with the control cable unplugged.

## E-stop and sensor headers

- **J9:** pin 1 GND, pin 2 **GPIO18** signal, normally-closed contact. Open=STOP.
  Physical motor-power interruption is separate.
- **J5 MPU6050:** 3V3, GND, SDA21, SCL22; typical address 0x68 with AD0 low.
- **J6 HX711:** 3V3, GND, DOUT16, SCK17. Use a compatible amplifier module,
  not a bare load cell. The sketch holds SCK LOW and reserves the sensor pins;
  MPU6050/load-cell measurements are not yet reported.

The carrier is USB-powered logic only: DevKit USB-derived 5 V feeds its peripheral
3.3 V regulator. Verify that source on the actual DevKit. Motor/driver supply
wiring is external; no 12 V may enter the carrier or back-power USB. ESP32,
encoder, driver and motor-supply return grounds are common.

On I²C failure or unexpected expander reset, all PWM enables are zeroed and the
controller disarms. Fix power/address/wiring and restart. Fault bit **128**
identifies this condition; recovery does not silently re-arm.

The motors specify **2.4 A stall current each**. This logic interface does not
resolve driver sizing. Verify encoder counts and electrical/current/stopping
behavior on guarded raised-wheel tests before loaded operation.
