# SIBRILLE Double Head LED Desk Lamp - IR Remote Protocol Specification

This repository contains the reverse-engineered infrared (IR) protocol specification, clean payload codes, and integration configurations for the **SIBRILLE Double Head LED Desk Lamp** (OEM Series: Yusing Lighting `YS-TL...` / models `MF31037`, `MF30021`).


> [!CAUTION]
> This IR protocol and command set were reverse-engineered and verified exclusively on a standard white light (non-RGB, CCT-adjustable) lamp model featuring a distinct black convex dome (IR receiver) on the underside directly beneath the touch buttons. These codes have not been tested on other hardware revisions, RGB variants, or lamp models; compatibility with different versions is not guaranteed.

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
  * Trailing silence: 40 ms or greater

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
| `02` | `0x18` | `0xE7` | **Brightness Up** | Stepwise increases luminous flux (5 discrete steps up to 100%). | `BRIGHT +` / 🔆 |
| `03` | `0x1F` | `0xE0` | **Brightness Down** | Stepwise decreases luminous flux (down to level 1/5). | `BRIGHT -` / 🔅 |
| `04` | `0x07` | `0xF8` | **CCT Cool** | Stepwise shifts color temperature toward cool white (~6500 K). | `CCT +` / `COLD` |
| `05` | `0x0F` | `0xF0` | **CCT Warm** | Stepwise shifts color temperature toward warm white (~2700 K). | `CCT -` / `WARM` |
| `06` | `0x03` | `0xFC` | **Max Brightness** | Absolute preset: Sets brightness to 100% (5/5) Medium White (CCT 3/5). | `100%` / `MAX` |
| `07` | `0x19` | `0xE6` | **Daylight Mode** | Absolute preset: Cool White (5/5, ~6500 K) at Maximum Brightness (5/5). | `DAYLIGHT` / `SUN` |
| `08` | `0x16` | `0xE9` | **Reading / Work** | Absolute preset: Neutral Cool White (~5000 K) at Maximum Brightness (5/5). | `READING` / `WORK` |
| `09` | `0x12` | `0xED` | **Relax / Warm Bright** | Absolute preset: Warm White (~2700 K) at High Brightness (4/5). | `RELAX` / `COFFEE` |
| `10` | `0x0A` | `0xF5` | **Warm Medium** | Absolute preset: Warm White (~2700 K) at Balanced Medium Brightness (3/5). | `WARM` |
| `11` | `0x0C` | `0xF3` | **Night Light / Baby Care** | Absolute preset: Warm Yellow (1/5, ~2700 K) at Minimum Brightness (1/5). | `NIGHT` / 🍼 *Feeding Bottle* |
| `12` | `0x1D` | `0xE2` | **Sleep Timer (15 Min)** | Toggle mode with optical feedback: Turns off after 15 min or cancels countdown. | `TIMER` / `15M` |

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

## 5. Payloads and Integration Formats

### Broadlink Base64 & Pronto Hex Payload Catalog

All packets represent clean, mathematical pulse sequences sampled for a 38 kHz carrier frequency:

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
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 05F0"
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
      "pronto_hex": "0000 006D 0022 0000 0156 00AB 0015 0015 0015 0040 0015 0015 0015 0015 0015 0015 0015 0040 0015 0015 0015 0015 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0040 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0015 0040 0015 0040 0015 0040 0015 0040 0015 05F0"
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

---

## 6. Home Assistant Integration

Add the following scripts to your `configuration.yaml` or `scripts.yaml` to trigger presets and the sleep timer using a Broadlink IR remote entity:

```yaml
script:
  desk_lamp_night_light:
    alias: "Desk Lamp - Night Light (Baby Bottle)"
    icon: mdi:baby-bottle-outline
    sequence:
      - service: remote.send_command
        target:
          entity_id: remote.broadlink_rm4_pro
        data:
          command: "b64:JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxISEhISNxI3EhISEhISEhISNxI3EhISEhI3EjcSNxI3EgAFHg=="

  desk_lamp_sleep_timer:
    alias: "Desk Lamp - Toggle 15m Timer"
    icon: mdi:timer-sand
    sequence:
      - service: remote.send_command
        target:
          entity_id: remote.broadlink_rm4_pro
        data:
          command: "b64:JgBIAAABJ5MSEhI3EhISEhISEjcSEhISEjcSEhI3EjcSNxISEjcSNxI3EhISNxI3EjcSEhISEhISEhI3EhISEhISEjcSNxI3EgAFHg=="
```

---

## 7. Standards References

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
  <http://www.remotecentral.com/features/irdisp1.htm>  
  *Standard manual for raw sampled burst pairs (`0000 006D ...`) across universal programmable remotes.*
