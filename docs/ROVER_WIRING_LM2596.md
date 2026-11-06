# AgriSahayak rover wiring (firmware-matched)

This pin map matches `arduino/agri_rover_full/agri_rover_full.ino`. The two supplied PDFs disagree on some Arduino pins and on which battery pack drives the motors. Follow this pin map for signals. Do not connect either battery until the motor voltage, fuse, and Li-ion pack protection are confirmed.

## Stop and check these power labels first

1. **Motors:** the component sheet says 6–12 V, but the photo shows a yellow TT-style motor whose rating is not visible. Read the motor label or seller specification. Do not connect the 3-cell pack directly to an unverified motor.
2. **Cells:** use only matching rechargeable 3.7 V Li-ion cells in a correctly rated protected/balanced 2S or 3S pack. A holder alone is not a charger or a battery protection board. The small blue board in the photo is not identifiable as a 3S BMS from that image.
3. **Fuse:** the one-pack wiring plan in the wiring guide calls for a 3 A fuse. Read the marking on your fuse. If it is not the correct rating, do not power the battery bus; never bypass a fuse or replace it with foil/a wire.
4. **Pump:** read its voltage and current label before wiring it. Leave the pump and relay contacts disconnected if the label is unknown.
5. **Buck setting:** use a multimeter to set the LM2596 output to exactly 5.0 V before connecting the servo or any 5 V load.

The LM2596 is a **step-down (buck) converter**. It is not a charger, battery-protection board, or isolator.

## Build with all batteries disconnected and switch OFF

### 1. Breadboard rails and Arduino-to-tablet link

- Tablet USB-C → OTG adapter/hub → USB data cable → Uno USB-B. This USB link powers the Uno and carries commands/telemetry.
- Uno `5V` → breadboard **LOGIC +5 V** rail.
- Uno `GND` → breadboard **GND** rail.
- If the 170-point breadboard has no long power rails, use short jumper wires to make these two buses. Do not pass motor or battery current through the breadboard.

### 2. Sensors and display (logic 5 V rail)

| Part pin | Connect to |
|---|---|
| Soil sensor `VCC` / `GND` / `AOUT` | Logic +5 V / GND / Uno `A0` |
| DHT11 `VCC` / `GND` / `DATA` | Logic +5 V / GND / Uno `D2` |
| IR module `VCC` / `GND` / `OUT` | Logic +5 V / GND / Uno `D3` |
| HC-SR04 `VCC` / `GND` / `TRIG` / `ECHO` | Logic +5 V / GND / Uno `D12` / Uno `D13` |
| LCD I2C `GND` / `VCC` / `SDA` / `SCL` | GND / Logic +5 V / Uno `A4` / Uno `A5` |

The LCD connection above requires the 4-pin I2C backpack. A bare 16-pin LCD is not wired by this firmware pin map.

### 3. Servo and L298N signal wiring

- SG90 brown → common GND; red → **LM2596 AUX +5 V**; orange/yellow → Uno `D11`.
- On the L298N, remove the `ENA` and `ENB` jumpers so the Uno can control speed. Keep the board's `5V-EN` jumper in place. Leave the L298N `5V` screw terminal empty.
- Uno `D5` → L298N `ENA`; Uno `D6` → `ENB`.
- Uno `D7` → `IN1`; `D8` → `IN2`; `D9` → `IN3`; `D10` → `IN4`.
- Left-side motors: both motors' first wires → `OUT1`; both second wires → `OUT2`.
- Right-side motors: both first wires → `OUT3`; both second wires → `OUT4`.
- Uno `GND` must connect to L298N `GND`. If one side reverses during the raised-wheel test, switch that side's two motor wires at its OUT terminals.

Two motors in parallel on one L298N channel can exceed the driver's current limit if they stall. Keep the wheels raised for the first test, use brief low-speed commands, and never hold a wheel still while powered.

### 4. LM2596 and one-pack power bus (only after the checks above)

For the single-fuse layout from the wiring guide, use **one protected pack only**:

```text
Pack +  → fuse (marked 3 A) → main switch → switched + bus
Pack −  ───────────────────────────────────→ common GND

Switched + bus → L298N `12V` terminal       [only if motor rating permits]
Switched + bus → LM2596 `IN+`
Common GND      → L298N `GND`
Common GND      → LM2596 `IN−`
LM2596 `OUT+`   → separate AUX +5 V rail (after meter reads 5.0 V)
LM2596 `OUT−`   → common GND
```

- The Uno remains powered by tablet USB. **Do not connect LM2596 `OUT+` to the Uno `5V` pin or the LOGIC +5 V rail while USB is connected.** The grounds are common; the two +5 V rails remain separate.
- The guide's one-fuse plan uses the 3-cell pack on the motor bus only for verified 6–12 V motors and a protected 3S pack. If the motor label says 3–6 V, do not use this direct 3S-to-L298N plan. Stop and get a motor-compatible supply/current plan first.
- Keep the 2-cell holder disconnected as a spare in this one-fuse plan. Never tie the 2-cell and 3-cell packs together.
- A 170-point breadboard is enough for low-current signal/logic distribution; use the L298N screw terminals and appropriately thick insulated wire for battery and motor power.

### 5. Capacitors and diodes

- **1000 µF, 25 V electrolytic:** across L298N `12V` (+) and `GND` (−), close to its power terminals. Long leg is usually positive; the stripe on the can marks negative. Double-check the markings before power.
- **0.1 µF (100 nF) ceramic capacitors:** one directly across each motor's two terminals, close to the motor. Ceramic capacitors are non-polarized. Do not connect these across `OUT1`/`OUT2` on the driver instead of at the motor.
- **LM2596 board:** the pictured module already has its inductor, switching diode, and input/output capacitors installed. Leave those parts in place; do not add a loose diode to its input or output. Follow the board's printed `IN+`, `IN−`, `OUT+`, and `OUT−` labels.
- **1N4007 pump diode:** only for a verified DC pump. Connect it **in parallel across the pump wires**, not in series: striped end (cathode) to pump `+` (the relay `NO` side), unstriped end (anode) to pump `−`. If the pump current is over the diode's rating or its voltage/current is unknown, leave it disconnected until a correctly rated diode is chosen.
- **L298N motor flyback diodes:** the L298 IC itself requires external bridge diodes. Standard red L298N modules usually have these diodes on the module; verify yours visibly has its diode set. If it does not, do not connect the motors until suitable fast-recovery diodes are fitted. The 1N4007 pump diode is not a substitute for the motor-driver diode bridge.

### 6. Relay and pump (optional; leave out for the rover-drive demo unless verified)

- Relay module `VCC` → Uno **LOGIC +5 V**; `GND` → common GND; `IN` → Uno `D4`.
- `NC` is unused. For a verified **5–6 V pump**, relay `COM` → LM2596 AUX +5 V and relay `NO` → pump `+`. For a verified **12 V pump**, relay `COM` → switched battery + bus and `NO` → pump `+`.
- Pump `−` → common GND. Install the 1N4007 across the pump as described above.
- The relay connects to Uno `D4`; it does **not** connect to the ultrasonic sensor. The pump is optional for motor movement and sensor readings.
- The current sketch sets `PUMP_ACTIVE_LOW` to `0` (active-HIGH relay input). If the relay board is marked low-trigger and turns on when `IN` is LOW, change that define to `1` and upload the sketch. The wiring guide's opposite default description does not match this firmware file.

## First power-up order

1. With batteries absent, check every signal wire and confirm there is no short between either + rail and GND.
2. Power the Uno by tablet/laptop USB only. Check the sensor readings and Arduino link first.
3. With the protected pack still switched off and the fuse removed, connect the battery negative/common GND and the switched-positive wiring. Verify polarity at every terminal.
4. Only once the pack and motor voltage are verified, insert the marked fuse, switch on briefly with wheels raised, and test a short low-speed forward/backward movement. If the fuse opens, any wire heats, the pack warms, or the L298N overheats, switch off and disconnect the pack.
5. Do not test the pump until its voltage/current and relay module markings are verified.
