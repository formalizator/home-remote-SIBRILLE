# SIBRILLE Double Head LED Desk Lamp - IR Remote Protocol Specification

This repository contains the reverse-engineered infrared (IR) protocol specification, raw and normalized command payloads, format structural documentation, and ready-to-use integration files for the **SIBRILLE Double Head LED Desk Lamp** (OEM Series: Yusing Lighting `YS-TL...` / models `MF31037`, `MF30021`, `YS-TL23063`).

> [!CAUTION]
> This IR protocol and command set were reverse-engineered and verified exclusively on a standard white light (non-RGB, CCT-adjustable) lamp model featuring a distinct black convex dome (IR receiver) on the underside directly beneath the touch buttons. These codes have not been tested on other hardware revisions, RGB variants, or lamp models; compatibility with different versions is not guaranteed.

---

## Repository File Structure

```text
.
├── README.md                                   # Protocol specification, format anatomy, theory, and platform guides
├── LICENSE                                     # MIT License
├── BroadlinkSibrilleIrHeadlamp.py              # Python CLI to send NEC codes via Broadlink hubs
├── raw_codes/
│   └── pronto_codes.csv                        # Pronto Hex (CCF) payload catalog with NEC repeat frames
├── android_irplus/
│   └── SIBRILLE_Desk_Lamp.irplus               # Android IRPlus XML remote definition
├── flipper_zero/
│   └── SIBRILLE_Desk_Lamp.ir                   # Flipper Zero Infrared parsed remote file
├── home_assistant/
│   └── configuration.yaml                      # Home Assistant input_boolean, scripts, and template light
├── esphome/
│   └── esphome.yaml                            # ESPHome GPIO remote_transmitter and template buttons
├── etc/
│   └── lirc/
│       └── lircd.conf.d/
│           └── sibrille.lircd.conf             # Linux LIRC daemon remote definition
└── custom_components/
    └── smartir/
        └── codes/
            └── light/
                └── 7144.json                   # SmartIR light profile for Broadlink controllers
```

### Format & Ecosystem Matrix

| File Path | Target Ecosystem | Data / Config Format | Addressing Convention |
| :--- | :--- | :--- | :--- |
| `BroadlinkSibrilleIrHeadlamp.py` | Broadlink RM3 / RM4 (Python CLI) | Broadlink Binary Packet (Hex / Base64) | NEC 16-bit LSB-first (`0x22DD`) |
| `raw_codes/pronto_codes.csv` | Universal Remotes & Converters | CSV + Pronto Hex (`0000 006D 0022 0002`) | NEC 16-bit LSB-first (`0x22DD`) |
| `android_irplus/SIBRILLE_Desk_Lamp.irplus` | Android (`irplus` app) | XML (`WINLIRC_SPACEENC`) | 16-bit MSB bit-reflected (`0x44BB`) |
| `flipper_zero/SIBRILLE_Desk_Lamp.ir` | Flipper Zero | Key-value text (`type: parsed`, `NEC`) | 4-byte padded little-endian (`22 DD 00 00`) |
| `home_assistant/configuration.yaml` | Home Assistant (Native YAML) | YAML (`b64:` Broadlink payloads) | Encoded Broadlink Base64 |
| `custom_components/smartir/codes/light/7144.json` | Home Assistant (`SmartIR`) | JSON (`Broadlink` / `Base64`) | Encoded Broadlink Base64 |
| `esphome/esphome.yaml` | ESPHome (ESP32 / ESP8266) | YAML (`remote_transmitter.transmit_nec`) | NEC 16-bit LSB-first (`0x22DD`) |
| `etc/lirc/lircd.conf.d/sibrille.lircd.conf` | Linux LIRC (`lircd`) | LIRC config (`SPACE_ENC\|CONST_LENGTH`) | 16-bit MSB bit-reflected (`0x44BB`) |

---

## 1. Physical Layer and Transmission Parameters

The remote control operates using the standard [**NEC Infrared Transmission Protocol**](https://sigrok.org/wiki/Protocol_decoder:Ir_nec) modulated onto a 38 kHz optical subcarrier frequency.

* **Carrier Frequency:** 38 kHz (Duty cycle 1/3 to 1/4, nominal carrier period ~26.3 us)
* **Wavelength:** 940 nm (Near-Infrared, IR-A band)
* **Modulation Scheme:** Pulse Distance Modulation (PDM)
* **Bit Transmission Order:** Least Significant Bit first (LSB-first)
* **Frame Composition:** 32 data bits (4 octets):

  `Address Low (A) -> Address High (A_inv) -> Command (C) -> Command Inverted (~C)`

### Timing Durations

* **Leading AGC Header:**
  * Mark (Burst): 9000 us
  * Space (Pause): 4500 us
* **Logical Bit '0':**
  * Mark: 560 us
  * Space: 560 us (Total bit duration: 1120 us)
* **Logical Bit '1':**
  * Mark: 560 us
  * Space: 1690 us (Total bit duration: 2250 us)
* **End-of-Frame Stop Bit:**
  * Mark: 560 us
  * Trailing silence: 40 ms or greater (standard 108 ms total frame repetition interval)
* **NEC Repeat Frame (optional on hold):**
  * Mark: 9000 us, Space: 2250 us, Stop Mark: 560 us

```text
NEC Frame Timing Diagram:
 |--- 9000us ---|--- 4500us ---| 560us | 560us | 560us |--- 1690us ---| ... | 560us |
 +--------------+              +-------+       +-------+              + ... +-------+
 |  Sync Mark   |  Sync Space  | Bit 0 (1120us)| Bit 1 (2250us)       |     | Stop  |
```

---

## 2. Protocol Identification and Addressing

The lamp uses a standard NEC complementary 16-bit address block where the second byte is the bitwise inversion of the first byte:

* **Customer / System Code (Address Low):** `0x22` (`00100010b`)
* **Address Inverted (Address High):** `0xDD` (`11011101b`)
* **Combined Hex Address:** `0x22DD`
* **Address Integrity Check:**
  `0x22 XOR 0xDD = 0xFF` (Standard complementary pair)

---

## 3. Verified Command Map

The table below describes all 12 functions available on the lamp microcontroller:

| ID | Command | Inverted | Function Name | Visual Feedback & Operational Behavior | Remote Legend / Icon |
| :---: | :---: | :---: | :--- | :--- | :---: |
| `01` | `0x11` | `0xEE` | **Power Toggle** | Toggles main light between ON and OFF. | `POWER` / `ON/OFF` |
| `02` | `0x18` | `0xE7` | **Brightness Up** | Each press increases brightness by 0.5/5; two presses make one full 1/5 step, up to 5/5 (100%). | `BRIGHT +` / 🔆 |
| `03` | `0x1F` | `0xE0` | **Brightness Down** | Each press decreases brightness by 0.5/5; two presses make one full 1/5 step, down to 1/5. | `BRIGHT -` / 🔅 |
| `04` | `0x07` | `0xF8` | **CCT Cool** | Each press shifts CCT by 0.5/5 toward cool white (~6500 K); two presses make one full 1/5 step, up to 5/5. | `CCT +` / `COLD` |
| `05` | `0x0F` | `0xF0` | **CCT Warm** | Each press shifts CCT by 0.5/5 toward warm white (~2700 K); two presses make one full 1/5 step, down to 1/5. | `CCT -` / `WARM` |
| `06` | `0x03` | `0xFC` | **Max Brightness** | Sets brightness to 5/5 (100%), CCT 3/5 (Neutral White). | `100%` / `MAX` |
| `07` | `0x19` | `0xE6` | **Daylight Mode** | Absolute preset: Cool White (5/5, ~6500 K) at Maximum Brightness (5/5). | `DAYLIGHT` / `SUN` |
| `08` | `0x16` | `0xE9` | **Reading / Work** | Absolute preset: Neutral Cool White (~5000 K) at Maximum Brightness (5/5). | `READING` / `WORK` |
| `09` | `0x12` | `0xED` | **Relax / Warm Bright** | Absolute preset: Warm White (~2700 K) at High Brightness (4/5). | `RELAX` / `COFFEE` |
| `10` | `0x0A` | `0xF5` | **Warm Medium** | Absolute preset: Warm White (~2700 K) at Balanced Medium Brightness (3/5). | `WARM` |
| `11` | `0x0C` | `0xF3` | **Night Light / Baby Care** | Absolute preset: Warm Yellow (1/5, ~2700 K) at Minimum Brightness (1/5). | `NIGHT` / 🍼 *Feeding Bottle* |
| `12` | `0x1D` | `0xE2` | **Sleep Timer (15 Min)** | Toggle mode with optical feedback: Turns off after 15 min or cancels countdown. | `TIMER` / `15M` |

### Cross-Format Command Lookup Table

Because different ecosystems encode the same on-air bit stream using different bit orders and naming conventions, the lookup table below maps every verified command across all repository files:

| ID | CLI Key (`--cmd`) | Flipper Zero `name` | LIRC Key Name | NEC Cmd (`C`) | NEC Inv (`~C`) | LIRC / IRPlus 16-bit Code (MSB-Reflected) |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: |
| `01` | `power` | `Power_on` / `Power_off` | `KEY_POWER` | `0x11` | `0xEE` | `0x8877` |
| `02` | `bright_up` | `Brightness_up` | `KEY_BRIGHTNESSUP` | `0x18` | `0xE7` | `0x18E7` |
| `03` | `bright_dn` | `Brightness_dn` | `KEY_BRIGHTNESSDOWN` | `0x1F` | `0xE0` | `0xF807` |
| `04` | `cct_cool` | `White` | `KEY_COOLER` | `0x07` | `0xF8` | `0xE01F` |
| `05` | `cct_warm` | `Yellow` | `KEY_WARMER` | `0x0F` | `0xF0` | `0xF00F` |
| `06` | `max` | `Max_100pct` | `KEY_BRIGHTNESS_MAX` | `0x03` | `0xFC` | `0xC03F` |
| `07` | `daylight` | `Daylight_Mode` | `KEY_MODE_DAYLIGHT` | `0x19` | `0xE6` | `0x9867` |
| `08` | `work` | `Work_Mode` | `KEY_MODE_WORK` | `0x16` | `0xE9` | `0x6897` |
| `09` | `relax` | `Relax_Mode` | `KEY_MODE_RELAX` | `0x12` | `0xED` | `0x48B7` |
| `10` | `warm_mid` | `Warm_Mid` | `KEY_MODE_WARM_MID` | `0x0A` | `0xF5` | `0x50AF` |
| `11` | `nightlight` | `Night_Light` | `KEY_MODE_NIGHTLIGHT` | `0x0C` | `0xF3` | `0x30CF` |
| `12` | `timer` | `Timer_15m` | `KEY_SLEEP` | `0x1D` | `0xE2` | `0xB847` |

---

## 4. Optical Feedback and Sleep Timer Logic (`0x1D`)

Because the desk lamp lacks a status display or secondary indicator LEDs, the microcontroller provides closed-loop state feedback through blinking sequences of the primary LED panel:

```text
        Press 0x1D (Odd count: 1, 3, 5...)
        [Lamp Blinks 2 Times]
        +------------------------------------------+
        |   15-Minute Countdown Timer Activated    |
        +------------------------------------------+
                            |
             +--------------+--------------+
             |                             |
       15 Minutes Elapsed          Press 0x1D Again (Even count: 2, 4...)
             |                             |
       +-----------+             [Lamp Blinks 3 Times]
       | Power OFF |                       |
       +-----------+             +-----------------------+
                                 | Timer Canceled / Idle |
                                 +-----------------------+
```

* **Activation (Odd-numbered clicks: 1st, 3rd, 5th...):**
  * The lamp executes a double-blink sequence (**2 blinks**, duration ~2.0 s) and returns to its steady-state brightness.
  * Internal hardware timer initiates a **15-minute countdown (900 seconds)**.
  * When time expires, the lamp automatically switches to `OFF`.
* **Cancellation (Even-numbered clicks: 2nd, 4th...):**
  * The lamp executes a triple-blink sequence (**3 blinks**), confirming countdown cancellation.
  * The active timer is cleared; the lamp remains indefinitely in its active state.
* **Continuous Press / Burst Transmission:**
  * Sustained holding of `0x1D` is registered as a single triggering pulse. The microcontroller ignores subsequent repeat frames during the 2-blink animation window, activating the 15-minute timer.

---

## 5. Data & File Format Structures

Each file in this repository expresses the exact same 38 kHz NEC `0x22DD` signal using the native data format expected by its target platform.

### 5.1 Standard NEC 32-Bit Frame Structure

Every transmitted command consists of an AGC preamble, 4 octets sent LSB-first, and a final stop mark:

```text
+-------------------+-------------------+-------------------+-------------------+-------------------+----------+
|  AGC Preamble     | Byte 0: Addr Low  | Byte 1: Addr High | Byte 2: Command   | Byte 3: ~Command  | Stop Bit |
|  9000us / 4500us  | 0x22 (00100010b)  | 0xDD (11011101b)  | 8 bits (LSB->MSB) | Cmd ^ 0xFF        | 560us    |
+-------------------+-------------------+-------------------+-------------------+-------------------+----------+
```

### 5.2 Broadlink RM Packet Structure (Raw Hex & Base64)

`BroadlinkSibrilleIrHeadlamp.py`, `home_assistant/configuration.yaml`, and `custom_components/smartir/codes/light/7144.json` use Broadlink's binary pulse-duration packet encoded in Base64 (or prefixed with `b64:` in Home Assistant).

Broadlink hardware quantizes pulse and space durations into ticks, where:

$$1\text{ tick} = \frac{8192}{269}\ \mu\text{s} \approx 30.4535\ \mu\text{s}$$

Durations fitting in 1–255 ticks use a single byte (`0x01`–`0xFF`). Durations $\ge 256$ ticks use a 3-byte big-endian escape sequence `0x00 <HI> <LO>`.

For any standard command with `repeats = 0`, the complete packet is **76 bytes** (4-byte packet header + 72-byte pulse payload). Example for **Power Toggle** (`0x11`):

```text
Byte Offset:  00 01 | 02 03 | 04 05 06 | 07 | 08 .. 71 (64 bytes)          | 72 | 73 74 75
Hex Bytes  :  26 00 | 48 00 | 00 01 27 | 93 | 12 12 12 37 ... (32 pairs)   | 12 | 00 05 1E
              |  |    |       |          |    |                              |    |
              |  |    |       |          |    |                              |    +-- Trailing silence: 0x051E = 1310 ticks (~39.89 ms)
              |  |    |       |          |    |                              +------- Stop mark: 0x12 = 18 ticks (~548 us)
              |  |    |       |          |    +-------------------------------------- 32 data bits: [0x12 mark, 0x12 (0) or 0x37 (1) space]
              |  |    |       |          +------------------------------------------- AGC space: 0x93 = 147 ticks (~4477 us)
              |  |    |       +------------------------------------------------------ AGC mark (3-byte escape): 0x0127 = 295 ticks (~8984 us)
              |  |    +-------------------------------------------------------------- Pulse payload length (little-endian): 0x0048 = 72 bytes
              |  +------------------------------------------------------------------- Hardware repeat count (0x00 = send once, 0x01..0xFF repeats)
              +---------------------------------------------------------------------- Packet type identifier (0x26 = IR transmission)
```

#### Broadlink Base64 & Pronto Hex Payload Catalog

All packets below represent clean, mathematical pulse sequences sampled for a 38 kHz carrier frequency:

```json
{
  "manufacturer": "SIBRILLE",
  "model": "Double Head LED Desk Lamp",
  "protocol": "NEC (38kHz)",
  "address": "0x22DD",
  "commands": {
    "power": {
      "hex": "0x11",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxI3EhISEhISEjcSEhISEhISEhI3EjcSNxISEjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "timer_15m": {
      "hex": "0x1D",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxI3EhISNxI3EjcSEhISEhISEhI3EhISEhISEjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "max_brightness_cct_mid": {
      "hex": "0x03",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxI3EjcSEhISEhISEhISEhISEhISEjcSNxI3EjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "brightness_up": {
      "hex": "0x18",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxISEhISEhI3EjcSEhISEhISNxI3EjcSEhISEjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "brightness_down": {
      "hex": "0x1F",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxI3EjcSNxI3EjcSEhISEhISEhISEhISEhISEjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "cct_cool": {
      "hex": "0x07",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxI3EjcSNxISEhISEhISEhISEhISEhISNxI3EjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "cct_warm": {
      "hex": "0x0F",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxI3EjcSNxI3EhISEhISEhISEhISEhISEhI3EjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "daylight_preset": {
      "hex": "0x19",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxI3EhISEhI3EjcSEhISEhISEhI3EjcSEhISEjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "reading_preset": {
      "hex": "0x16",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxISEjcSNxISEjcSEhISEhISNxISEhISNxISEjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "relax_preset": {
      "hex": "0x12",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxISEjcSEhISEjcSEhISEhISNxISEjcSNxISEjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "warm_mid_preset": {
      "hex": "0x0A",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxISEjcSEhI3EhISEhISEhISNxISEjcSEhI3EjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0015 0015 0040 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 05F0"
    },
    "night_light_preset": {
      "hex": "0x0C",
      "broadlink_base64": "JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxISEhISNxI3EhISEhISEhISNxI3EhISEhI3EjcSNxI3EgAFHg==",
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0015 0015 0015 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 05F0"
    }
  }
}
```

### 5.3 Pronto Hex Format Structure (`raw_codes/pronto_codes.csv`)

[raw_codes/pronto_codes.csv](raw_codes/pronto_codes.csv) stores all 12 commands in a 4-column CSV table:

```csv
Function Name,NEC Address,NEC Command,Pronto Hex Code
Power Toggle,0x22DD,0x11,0000 006D 0022 0002 0157 00AC ... 0015 0689 0157 0056 0015 0E94
```

Every Pronto Hex (CCF) string is a sequence of 16-bit hexadecimal words representing carrier-cycle counts:

```text
0000  006D  0022  0002  [0157 00AC]  [0015 0015 / 0015 0041] x32  [0015 0689]  [0157 0056  0015 0E94]
  |     |     |     |        |                     |                    |                  |
  |     |     |     |        |                     |                    |                  +-- Repeat sequence (2 pairs):
  |     |     |     |        |                     |                    |                      9020us mark, 2261us space, 552us mark, 98.14ms gap
  |     |     |     |        |                     |                    +--------------------- Stop mark (552us) + inter-frame gap (43.99ms)
  |     |     |     |        |                     +------------------------------------------ 32 data bit pairs: '0' = 21/21 cycles (~552us/552us)
  |     |     |     |        |                                                                 '1' = 21/65 cycles (~552us/1709us)
  |     |     |     |        +---------------------------------------------------------------- AGC header pair: 343/172 cycles (~9020us/4523us)
  |     |     +-----+------------------------------------------------------------------------- Burst pair counts:
  |     |                                                                                      0x0022 (34) one-time pairs + 0x0002 (2) repeat pairs
  |     +------------------------------------------------------------------------------------- Carrier divisor N = 0x006D (109):
  |                                                                                            f = 1,000,000 / (109 * 0.241246) = 38,029 Hz (T = 26.30us)
  +------------------------------------------------------------------------------------------- Format indicator: 0000 = raw learned modulated code
```

> [!NOTE]
> The JSON catalog in Section 5.2 uses single-shot Pronto strings (`0000 006D 0022 0000 ...`, 72 words, zero repeat pairs) with `0156 00AB` / `0015 0040` / `0015 05F0`, whereas [raw_codes/pronto_codes.csv](raw_codes/pronto_codes.csv) includes the 2-pair NEC repeat sequence (`0000 006D 0022 0002 ...`, 76 words) for universal remotes that support button-hold repeat bursts.

### 5.4 Linux LIRC Format Structure (`etc/lirc/lircd.conf.d/sibrille.lircd.conf`)

[etc/lirc/lircd.conf.d/sibrille.lircd.conf](etc/lirc/lircd.conf.d/sibrille.lircd.conf) uses standard `lircd.conf` `SPACE_ENC` syntax:

```text
begin remote

  name  SIBRILLE_LAMP
  bits           16              # 16 variable payload bits (Cmd + ~Cmd) after pre_data
  flags SPACE_ENC|CONST_LENGTH   # Pulse-distance encoding with fixed 108 ms frame period
  eps            30              # 30% relative timing tolerance for decoding
  aeps          100              # 100 us absolute timing tolerance

  header       9000  4500        # Leading AGC mark (9000 us) and space (4500 us)
  one           560  1690        # Logical '1' mark/space durations (us)
  zero          560   560        # Logical '0' mark/space durations (us)
  ptrail        560              # End-of-frame stop mark (560 us)
  repeat       9000  2250        # NEC repeat frame header (us)
  pre_data_bits   16             # Fixed 16-bit prefix transmitted before each key code
  pre_data       0x44BB          # Address 0x22DD in MSB bit-reflected order
  gap          108000            # Total frame period from start to start (108 ms)
  toggle_bit_mask 0x0            # No toggle bit (NEC repeats Cmd + ~Cmd)
  frequency    38000             # 38 kHz optical carrier

      begin codes
          KEY_POWER                0x8877
          ...
      end codes

end remote
```

* Because `SPACE_ENC` shifts bits out MSB-first, both `pre_data` (`0x44BB`) and the 16-bit key codes (`0x8877` for `0x11EE`) are the bit-reversed byte equivalents of `0x22DD` and `Cmd + ~Cmd` (see [Section 6.3](#63-bit-ordering--endianness-across-ecosystems-0x22dd-vs-0x44bb)).

### 5.5 Android IRPlus XML Format Structure (`android_irplus/SIBRILLE_Desk_Lamp.irplus`)

[android_irplus/SIBRILLE_Desk_Lamp.irplus](android_irplus/SIBRILLE_Desk_Lamp.irplus) wraps the same LIRC/WinLIRC `SPACE_ENC` timing model inside an XML UI layout for Android phones:

```xml
<irplus>
    <device manufacturer="SIBRILLE" model="Double Head Desk Lamp" columns="3"
            format="WINLIRC_SPACEENC" bits="32" pre-data-bits="16" pre-data="0x44BB"
            header-pulse="9000" header-space="4500"
            one-pulse="560" one-space="1690" zero-pulse="560" zero-space="560"
            ptrail="560" gap="108000" carrier-frequency="38000">

        <button label="&#61457; POWER" backgroundColor="FFD32F2F">0x8877</button>
        <button label="100% MAX">0xC03F</button>
        <button label="&#128338; 15M">0xB847</button>
        ...
    </device>
</irplus>
```

* `<device>` defines the 3-column grid (`columns="3"`), total frame width (`bits="32"` = 16 `pre-data-bits` + 16 button bits), microsecond pulse/space timing, and 38 kHz carrier (`carrier-frequency="38000"`).
* Each `<button>` sets a display label (with optional Unicode/HTML character entities and `backgroundColor` ARGB hex) and the 16-bit MSB-reflected command word (`0x8877`, `0xC03F`, etc.).

### 5.6 Flipper Zero `.ir` Format Structure (`flipper_zero/SIBRILLE_Desk_Lamp.ir`)

[flipper_zero/SIBRILLE_Desk_Lamp.ir](flipper_zero/SIBRILLE_Desk_Lamp.ir) uses Flipper Zero's plain-text `IR signals file` Version `1` parsed format:

```text
Filetype: IR signals file
Version: 1
# 
# SIBRILLE Double Head LED Desk Lamp (NEC 0x22DD)
# 
name: Power_on
type: parsed
protocol: NEC
address: 22 DD 00 00
command: 11 00 00 00
# 
name: Power_off
type: parsed
protocol: NEC
address: 22 DD 00 00
command: 11 00 00 00
```

* `type: parsed` + `protocol: NEC` instructs Flipper Zero's Infrared firmware to synthesize the 38 kHz NEC frame timing natively rather than storing raw pulse durations.
* `address: 22 DD 00 00` stores the 16-bit address (`0x22`, `0xDD`) padded to 4 space-separated bytes (`00 00`).
* `command: 11 00 00 00` stores the 8-bit command byte (`0x11`) padded to 4 bytes; Flipper Zero automatically computes and transmits the inverted byte (`0xEE`) on air.
* The standard buttons follow the Flipper-IRDB `LEDs` naming convention (`Power_on`, `Power_off`, `Brightness_up`, `Brightness_dn`, `White`, `Yellow`), where both `Power_on` and `Power_off` map to the toggle command `11 00 00 00` so universal remote assets can trigger either action consistently.

### 5.7 SmartIR JSON Profile Structure (`custom_components/smartir/codes/light/7144.json`)

[custom_components/smartir/codes/light/7144.json](custom_components/smartir/codes/light/7144.json) follows the SmartIR light device schema:

```json
{
  "manufacturer": "SIBRILLE",
  "supportedModels": ["Double Head Desk Lamp", "MF31037", "MF30021", "YS-TL23063"],
  "supportedController": "Broadlink",
  "commandsEncoding": "Base64",
  "minTemperature": 2700,
  "maxTemperature": 6500,
  "precision": 5,
  "operationModes": ["nightlight", "warm_mid", "relax", "work", "daylight"],
  "commands": {
    "off": "JgBIAAAB...",
    "on": "JgBIAAAB...",
    "brightnessDown": "...",
    "brightnessUp": "...",
    "colorTemperatureDown": "...",
    "colorTemperatureUp": "...",
    "maxBrightness": "...",
    "sleepTimer15m": "...",
    "modes": {
      "nightlight": "...",
      "warm_mid": "...",
      "relax": "...",
      "work": "...",
      "daylight": "..."
    }
  }
}
```

* Top-level metadata declares the Broadlink controller, Base64 encoding, 2700 K–6500 K color temperature range across 5 coarse steps (`precision: 5`), and 5 named preset modes.
* Because the physical lamp has a single Power Toggle code (`0x11`), both `"on"` and `"off"` map to the same Power Toggle Base64 string.

### 5.8 Home Assistant & ESPHome YAML Structures

#### Home Assistant Native YAML (`home_assistant/configuration.yaml`)

[home_assistant/configuration.yaml](home_assistant/configuration.yaml) uses a 3-tier YAML hierarchy to wrap stateless IR payloads into a stateful Home Assistant entity:

```yaml
input_boolean:
  sibrille_desk_lamp_state:           # Tier 1: Optimistic local ON/OFF state tracker
    name: "SIBRILLE Desk Lamp State"

script:
  sibrille_lamp_power_toggle:         # Tier 2: 12 scripts calling remote.send_command
    sequence:                         # with Broadlink "b64:..." payloads and updating state
      - service: remote.send_command
        target:
          entity_id: remote.broadlink_rm4_pro
        data:
          command: "b64:JgBIAAAB..."
      - service: input_boolean.toggle
        target:
          entity_id: input_boolean.sibrille_desk_lamp_state

light:
  - platform: template                # Tier 3: Template Light entity for UI, HomeKit, Voice
    lights:
      sibrille_desk_lamp:
        value_template: "{{ is_state('input_boolean.sibrille_desk_lamp_state', 'on') }}"
        turn_on:
          service: script.sibrille_lamp_power_toggle
        turn_off:
          service: script.sibrille_lamp_power_toggle
```

#### ESPHome YAML (`esphome/esphome.yaml`)

[esphome/esphome.yaml](esphome/esphome.yaml) configures a hardware-PWM IR transmitter component and 12 template buttons:

```yaml
remote_transmitter:
  pin: GPIO4                          # GPIO connected to the IR LED driver circuit
  carrier_duty_percent: 33%           # 1/3 duty cycle at 38 kHz reduces LED heating

button:
  - platform: template
    name: "Sibrille Lamp Power"
    on_press:
      - remote_transmitter.transmit_nec:
          address: 0x22DD
          command: 0x11               # ESPHome auto-computes ~Cmd (0xEE) and 38 kHz timing
```

---

## 6. Theory of Operation

### 6.1 Optical Carrier & Hardware Demodulation (940 nm / 38 kHz)

Infrared remote controls cannot transmit raw baseband DC pulses directly across a room because sunlight, incandescent bulbs, and switching LED drivers emit intense ambient infrared noise that would overwhelm a simple photodiode.

To isolate remote control signals from ambient light:
1. **Optical Band-Pass Filtering (940 nm):** The transmitter uses a 940 nm GaAs/AlGaAs IR LED, while the lamp's underside black convex dome is molded from IR-transparent resin that blocks visible light below ~800 nm.
2. **38 kHz Subcarrier Modulation:** During every logical **Mark** (the 9000 us header, 560 us bit bursts, and 560 us stop bit), the transmitter switches the 940 nm LED on and off at **38 kHz** (period $26.3\ \mu\text{s}$) with a **25%–33% duty cycle**. Lower duty cycles allow higher peak LED current (brighter IR pulse) without overheating the diode. During a **Space**, the LED stays completely off.
3. **Integrated Receiver Demodulation:** Inside the lamp's black dome sits an integrated 38 kHz IR receiver module (such as a Vishay TSOP-series or equivalent). It applies Automatic Gain Control (AGC), a 38 kHz band-pass filter, and an envelope detector to strip the 38 kHz carrier and output a clean, active-low digital logic waveform directly to an interrupt/timer capture pin on the lamp's microcontroller.

### 6.2 NEC Pulse Distance Modulation (PDM) & Constant Frame Duration

The NEC protocol uses **Pulse Distance Modulation**, where every bit starts with a fixed-length **560 us Mark** and conveys its binary value solely through the **Space** duration that follows:
* **AGC Header (`9000 us` Mark + `4500 us` Space):** Allows the receiver's AGC amplifier to settle to the room's ambient IR noise floor and signals start-of-frame to the microcontroller's edge-capture timer.
* **Bit Discrimination (`560 us` vs `1690 us` Space):** A short `560 us` space encodes **`0`** (1.12 ms total bit time), while a triple-length `1690 us` space encodes **`1`** (2.25 ms total bit time). Because a `0` bit has no trailing mark after its space, the frame ends with a mandatory **`560 us` Stop Mark** so the receiver can measure the final space.
* **Complementary Integrity & Constant Frame Length:** Every byte is paired with its bitwise inverse (`Addr_L` + `~Addr_L` = `0x22` + `0xDD`, `Cmd` + `~Cmd`). The microcontroller validates `Byte ^ InvByte == 0xFF` to reject corrupted frames. Because every bit pair $(b_i, \overline{b_i})$ contains exactly one `0` and one `1`, every 32-bit frame always contains **exactly sixteen `0` bits and sixteen `1` bits**. Consequently, the active NEC frame duration is strictly constant regardless of which command is sent:

$$T_{\text{frame}} = 9000 + 4500 + 16(560 + 560) + 16(560 + 1690) + 560 = 67,980\ \mu\text{s} \approx 68.0\text{ ms}$$

*(Using the nominal NEC base period $T_b = 562.5\ \mu\text{s}$, $T_{\text{frame}} = 121 \times 562.5\ \mu\text{s} = 68.0625\text{ ms}$, followed by trailing silence up to the `108 ms` repetition period.)*

### 6.3 Bit-Ordering & Endianness Across Ecosystems (`0x22DD` vs `0x44BB`)

A common source of confusion when porting IR codes between tools is why the same lamp uses **`0x22DD`** in NEC tools (`BroadlinkSibrilleIrHeadlamp.py`, `esphome.yaml`, `SIBRILLE_Desk_Lamp.ir`) but **`0x44BB`** in LIRC/IRPlus (`sibrille.lircd.conf`, `SIBRILLE_Desk_Lamp.irplus`).

On the air, NEC transmits each byte **LSB-first**:
* Address Low `0x22` (`0010 0010b`) is transmitted on air starting from bit 0 to bit 7: `0, 1, 0, 0, 0, 1, 0, 0`.
* Standard NEC parsers reconstruct bytes from LSB to MSB $\to$ `0x22` followed by `0xDD` $\to$ **`0x22DD`**.
* LIRC (`SPACE_ENC`) and IRPlus (`WINLIRC_SPACEENC`) are generic shift-register engines that shift each incoming pulse-distance bit **into the LSB from left to right (MSB-first)**:
  * Shifting `0, 1, 0, 0, 0, 1, 0, 0` MSB-first yields `0100 0100b` = **`0x44`**.
  * Shifting `0xDD` (`1101 1101b`) LSB-first produces `1, 0, 1, 1, 1, 0, 1, 1`, which read MSB-first yields `1011 1011b` = **`0xBB`**.
  * Combining both bytes gives **`0x44BB`**!
* The exact same per-byte bit reversal applies to every command pair: for Power (`0x11` = `0001 0001b`, `0xEE` = `1110 1110b`), reversing each byte's bits gives `1000 1000b` = `0x88` and `0111 0111b` = `0x77` $\to$ **`0x8877`**.

### 6.4 Lamp Microcontroller State Machine & Open-Loop Automation

Internally, the lamp operates as an **open-loop infrared receiver** (it never transmits status back over IR, Wi-Fi, or BLE):
* **Coarse vs. Half-Step Resolution:** The lamp scales both brightness and CCT over 5 logical levels (`1/5` to `5/5`), yet the relative IR step keys (`0x18`, `0x1F`, `0x07`, `0x0F`) increment or decrement by **`0.5/5` per single frame** (requiring two presses to complete one full `1/5` step).
* **Absolute Presets vs. Relative Toggles:** Presets (`0x03`, `0x19`, `0x16`, `0x12`, `0x0A`, `0x0C`) jump directly to a deterministic `(CCT, Brightness)` pair and turn the lamp ON if it was OFF. In contrast, Power (`0x11`) and Sleep Timer (`0x1D`) are stateful toggles.
* **Keeping Smart Home State Synchronized:** Because there is no return telemetry, Home Assistant uses an optimistic `input_boolean.sibrille_desk_lamp_state`. If someone touches the lamp's capacitive buttons physically, Home Assistant's state can drift out of sync. Using an **absolute preset** (such as `Daylight`, `Work`, or `Night Light`) inside "turn on" automations guarantees the lamp enters a known ON state without accidentally toggling an already-lit lamp OFF.

---

## 7. Target Platforms: Preconditions, Setup & How to Start

Choose any platform below depending on the hardware you own. In all cases, ensure clear **line-of-sight** (or clean wall bounce) between the IR emitter and the **black convex IR dome** on the underside of the lamp head.

### 7.1 Broadlink Python CLI (`BroadlinkSibrilleIrHeadlamp.py`)

* **Preconditions:**
  * Python **3.9 or newer** installed on Windows, macOS, or Linux.
  * Either [`uv`](https://docs.astral.sh/uv/) or `pip` with `broadlink>=0.19.0`.
  * A **Broadlink IR blaster** (e.g., RM3 Mini, RM4 Mini, RM4 Pro) configured on the **same local Wi-Fi subnet** as your computer, with **Lock Device** disabled in the Broadlink mobile app so local LAN control is allowed. *(No hardware is needed when using `--dry-run`.)*
* **Setup & How to Start:**
  1. **Run directly with `uv` (installs `broadlink` automatically in an isolated environment):**
     ```bash
     uv run BroadlinkSibrilleIrHeadlamp.py
     ```
  2. **Or install manually via `pip` and launch the interactive menu:**
     ```bash
     pip install broadlink
     python BroadlinkSibrilleIrHeadlamp.py
     ```
  3. **Direct CLI usage examples:**
     ```bash
     # Send a named command (auto-discovers Broadlink on LAN)
     python BroadlinkSibrilleIrHeadlamp.py --cmd power

     # Target a specific Broadlink IP address directly
     python BroadlinkSibrilleIrHeadlamp.py --host 192.168.1.50 --cmd nightlight

     # Send a command with hardware repeats (0-255)
     python BroadlinkSibrilleIrHeadlamp.py --cmd bright_up --repeats 1

     # Generate and print Base64 / Raw Hex payloads without any Broadlink device
     python BroadlinkSibrilleIrHeadlamp.py --cmd timer --dry-run

     # Probe a custom NEC command byte (hex) against default address 0x22DD
     python BroadlinkSibrilleIrHeadlamp.py --custom 0x1A
     ```
  * Supported `--cmd` keys: `power`, `timer`, `max`, `bright_up`, `bright_dn`, `cct_cool`, `cct_warm`, `daylight`, `work`, `relax`, `warm_mid`, `nightlight`.

### 7.2 Android Smartphones — IRPlus (`android_irplus/SIBRILLE_Desk_Lamp.irplus`)

* **Preconditions:**
  * An **Android phone or tablet equipped with a built-in hardware IR blaster** (common on Xiaomi / Redmi / Poco, Huawei / Honor, and select LG/Samsung models) **or** a compatible external USB-C / 3.5 mm IR transmitter dongle supported by the app. *(Phones without IR hardware cannot emit infrared signals.)*
  * The **irplus - Infrared Remote** Android app installed.
  * Line-of-sight from the top edge of the phone (IR emitter) toward the lamp's black IR dome.
* **Setup & How to Start:**
  1. Download or copy [android_irplus/SIBRILLE_Desk_Lamp.irplus](android_irplus/SIBRILLE_Desk_Lamp.irplus) onto your Android device's storage (e.g., `Downloads/`).
  2. Open **irplus**, tap the top-left menu icon (**≡**), and choose **Import** $\to$ **Import from file** (or **Load** depending on app version).
  3. Select `SIBRILLE_Desk_Lamp.irplus`.
  4. Open the newly imported **SIBRILLE - Double Head Desk Lamp** remote, point your phone's IR blaster at the lamp, and tap any button in the 3-column grid.

### 7.3 Flipper Zero (`flipper_zero/SIBRILLE_Desk_Lamp.ir`)

* **Preconditions:**
  * A **Flipper Zero** with a formatted **microSD card** inserted.
  * **qFlipper** (desktop/mobile app) or a microSD card reader to transfer files.
  * Line-of-sight from Flipper Zero's front IR window to the lamp's IR receiver dome.
* **Setup & How to Start:**
  1. Connect your Flipper Zero via USB (with qFlipper) or mount its microSD card.
  2. Copy [flipper_zero/SIBRILLE_Desk_Lamp.ir](flipper_zero/SIBRILLE_Desk_Lamp.ir) to `/ext/infrared/SIBRILLE_Desk_Lamp.ir` (`SD Card/infrared/SIBRILLE_Desk_Lamp.ir`).
  3. On the Flipper Zero, press **OK** $\to$ **Infrared** $\to$ **Saved Remotes** $\to$ **SIBRILLE_Desk_Lamp**.
  4. Point the Flipper Zero at the lamp and press **OK** on any of the 13 commands (`Power_on`, `Power_off`, `Brightness_up`, `Brightness_dn`, `White`, `Yellow`, `Timer_15m`, `Night_Light`, etc.) to transmit.

### 7.4 Home Assistant — Native YAML Configuration (`home_assistant/configuration.yaml`)

* **Preconditions:**
  * A running **Home Assistant** instance (Core, OS, Container, or Supervised).
  * An active Broadlink (or other `remote.*`) integration configured in Home Assistant (the sample uses `entity_id: remote.broadlink_rm4_pro`) positioned within line-of-sight of the lamp.
* **Setup & How to Start:**
  1. Open [home_assistant/configuration.yaml](home_assistant/configuration.yaml) and copy the `input_boolean`, `script`, and `light` sections into your Home Assistant `configuration.yaml` (or split them into `scripts.yaml` / packages as appropriate).
  2. Replace every occurrence of `remote.broadlink_rm4_pro` with your actual Home Assistant `remote.*` entity ID.
  3. Open **Developer Tools** $\to$ **YAML** $\to$ **Check Configuration**, then reload YAML / restart Home Assistant.
  4. Control `light.sibrille_desk_lamp` from your Lovelace dashboard (or call `script.sibrille_lamp_preset_nightlight`, `script.sibrille_lamp_sleep_timer_15m`, etc.).

### 7.5 Home Assistant — SmartIR Integration (`custom_components/smartir/codes/light/7144.json`)

* **Preconditions:**
  * A running **Home Assistant** instance with the [**SmartIR**](https://github.com/smartHomeHub/SmartIR) custom integration installed (typically via HACS).
  * A configured Broadlink `remote.*` entity aimed at the lamp.
* **Setup & How to Start:**
  1. Copy [custom_components/smartir/codes/light/7144.json](custom_components/smartir/codes/light/7144.json) into your Home Assistant config directory at `<config>/custom_components/smartir/codes/light/7144.json`.
  2. Add the SmartIR light platform to your Home Assistant `configuration.yaml`:
     ```yaml
     smartir:

     light:
       - platform: smartir
         name: "SIBRILLE Desk Lamp"
         unique_id: sibrille_desk_lamp_smartir
         device_code: 7144
         controller_data: remote.broadlink_rm4_pro
     ```
  3. Replace `remote.broadlink_rm4_pro` with your Broadlink remote entity ID, verify your YAML configuration, and restart Home Assistant.
  4. Use the created `light.sibrille_desk_lamp` entity in dashboards, scenes, and automations.

### 7.6 ESPHome — DIY Microcontroller IR Transmitter (`esphome/esphome.yaml`)

* **Preconditions:**
  * An **ESP32** or **ESP8266** development board.
  * A **940 nm IR LED** driven through a transistor (e.g., 2N2222 / S8050 + base and current-limiting resistors) or an active IR transmitter module wired to a free GPIO pin (`GPIO4` in the example; **never drive a high-current IR LED directly from an unbuffered GPIO pin**).
  * **ESPHome** CLI (`pip install esphome`) or the Home Assistant ESPHome Device Builder add-on.
* **Setup & How to Start:**
  1. Create or open your ESPHome node YAML (with standard `esphome:`, board `esp32:`/`esp8266:`, `wifi:`, `api:`, and `ota:` sections).
  2. Merge the `remote_transmitter:` and `button:` blocks from [esphome/esphome.yaml](esphome/esphome.yaml), adjusting `pin: GPIO4` to match your hardware wiring.
  3. Compile and flash the firmware to the board:
     ```bash
     esphome run esphome/esphome.yaml
     ```
  4. Adopt the node in Home Assistant (if using the `api:` component) and trigger any of the 12 `Sibrille ...` button entities.

### 7.7 Linux LIRC (`etc/lirc/lircd.conf.d/sibrille.lircd.conf`)

* **Preconditions:**
  * A Linux host (e.g., Raspberry Pi, Debian/Ubuntu) with the **`lirc`** package installed.
  * An active kernel IR transmitter device (such as `/dev/lirc0` enabled via Raspberry Pi `dtoverlay=gpio-ir-tx,gpio_pin=17`, or a supported USB IR transceiver) wired to a 940 nm IR LED aimed at the lamp.
* **Setup & How to Start:**
  1. Install LIRC if needed and copy [etc/lirc/lircd.conf.d/sibrille.lircd.conf](etc/lirc/lircd.conf.d/sibrille.lircd.conf) into `/etc/lirc/lircd.conf.d/`:
     ```bash
     sudo cp etc/lirc/lircd.conf.d/sibrille.lircd.conf /etc/lirc/lircd.conf.d/
     sudo systemctl restart lircd
     ```
  2. Verify LIRC loaded the remote definition:
     ```bash
     irsend LIST SIBRILLE_LAMP ""
     ```
  3. Transmit commands directly from the shell or scripts:
     ```bash
     irsend SEND_ONCE SIBRILLE_LAMP KEY_POWER
     irsend SEND_ONCE SIBRILLE_LAMP KEY_MODE_NIGHTLIGHT
     ```

### 7.8 Universal Remotes & Raw Pronto Hex Importers (`raw_codes/pronto_codes.csv`)

* **Preconditions:**
  * Any programmable remote or IR bridge accepting **Pronto Hex (CCF)** strings (`0000 006D ...`) or raw NEC `0x22DD` codes (e.g., Philips Pronto, Logitech Harmony, Global Caché iTach, Tasmota `IRSend`, OpenMQTTGateway).
* **Setup & How to Start:**
  1. Open [raw_codes/pronto_codes.csv](raw_codes/pronto_codes.csv) and copy the `Pronto Hex Code` cell for the desired function.
  2. Paste the space-separated hex string into your remote editor, bridge API, or Home Assistant conversion tool.
  3. If your controller does not support repeat sequences (`0002` word in header), use the single-frame `pronto_hex` strings (`0000 006D 0022 0000 ...`) from [Section 5.2](#broadlink-base64--pronto-hex-payload-catalog).

---

## 8. Standards References

For technical details regarding infrared decoding, pulse train analysis, and capture standards, refer to:

* **SB-Projects IR Knowledge Base - NEC Protocol Standard:**  
  https://www.sb-projects.net/knowledge/ir/nec.php  
  *Detailed reference covering pulse distance modulation, lead-in marks, and inverted command validation.*
* **Vishay Semiconductor - Data Formats for IR Remote Control:**  
  https://www.vishay.com/docs/80071/dataform.pdf  
  *Industry documentation on optical transmission timing, carrier burst generation, and optical filtering.*
* **Home Assistant SmartIR Component Repository:**  
  https://github.com/smartHomeHub/SmartIR  
  *Universal open-source database integrating discrete climate, media, and light controls into Home Assistant.*
* **Remote Central - Pronto Edit Hex Format Specification:**  
  http://www.remotecentral.com/features/irdisp1.htm  
  *Standard manual for raw sampled burst pairs (`0000 006D ...`) across universal programmable remotes.*

---

## 9. Troubleshooting and Compatibility Notes

* The protocol and codes in this repository were verified on the standard white CCT-adjustable model only.
* The distinct black convex dome on the underside of the lamp is a strong marker of the tested hardware revision.
* RGB variants, alternative power boards, or other OEM revisions may not use the same NEC commands.
* If the lamp does not respond, verify:
  * the IR emitter is pointed toward the black convex dome underneath the touch panel (avoid aiming purely at the top side of the desk lamp head),
  * the IR LED is connected to the configured GPIO or emitter pin and driven with adequate current,
  * the Broadlink hub is on the same subnet as your host and unlocked for local LAN communication,
  * the NEC frame uses the verified 38 kHz carrier and `0x22DD` address (or `0x44BB` in LIRC/IRPlus).
* Because the lamp uses `0.5/5` micro-steps for `Brightness +/-` and `CCT +/-`, two single commands are required to move one full `1/5` visual notch.
* For the sleep timer (`0x1D`), repeated presses toggle between timer-active (2 blinks) and timer-canceled (3 blinks), ignoring bursts during the 2-blink animation window.

---

## 10. License and Attribution

This repository is distributed under the MIT License. See [LICENSE](LICENSE) for the full text.

The project documents a reverse-engineered IR protocol and command set for a consumer desk lamp. It is intended for hobbyist, home automation, and interoperability use, and it is provided as-is without warranty.

If you adapt the commands for another system, preserve the verified NEC address (`0x22DD` / LSB-first, or `0x44BB` / MSB-reflected) and confirm the exact hardware revision before using these payloads on a different lamp model.
