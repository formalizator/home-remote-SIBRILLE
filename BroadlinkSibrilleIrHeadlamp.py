#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "broadlink>=0.19.0",
# ]
# ///
"""
SIBRILLE Double Head LED Desk Lamp - Broadlink IR Remote Controller
Protocol: Standard NEC (38 kHz), Default Address: 0x22DD

===============================================================================
INSTALLATION & DEPENDENCIES
===============================================================================
This script requires the external `broadlink` Python library to communicate
with Broadlink RM4 Pro / RM4 Mini / RM3 Mini IR blasters over the local network.

Option 1: Standard pip installation:
    pip install broadlink

Option 2: Run directly via `uv` (automatically manages dependencies):
    uv run sibrille_remote.py

===============================================================================
USAGE EXAMPLES
===============================================================================
1. Interactive Menu Mode (Default):
    python sibrille_remote.py

2. Direct CLI Command by Name:
    python sibrille_remote.py --cmd power
    python sibrille_remote.py --cmd nightlight

3. Send a Custom NEC Command (Hex) to Default Address (0x22DD):
    python sibrille_remote.py --custom 0x1A

4. Generate Base64/Hex Payloads Without a Broadlink Device (Dry Run):
    python sibrille_remote.py --cmd timer --dry-run
===============================================================================
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from dataclasses import dataclass
from typing import Optional

try:
    import broadlink
    from broadlink.exceptions import BroadlinkException
except ImportError:
    print("[ERROR] The 'broadlink' library is not installed.", file=sys.stderr)
    print("Please install it using: pip install broadlink", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# PROTOCOL CONSTANTS (NEC 38kHz -> Broadlink Tick Units: 1 tick = 8192 / 269 us)
# =============================================================================
DEFAULT_ADDR_L = 0x22
DEFAULT_ADDR_H = 0xDD

BL_PACKET_TYPE_IR = 0x26
NEC_HDR_MARK_SPACE = [0x00, 0x01, 0x27, 0x93]  # 9000 us mark, 4500 us space
NEC_BIT_MARK = 0x12                            # 560 us mark
NEC_ONE_SPACE = 0x37                           # 1690 us space
NEC_ZERO_SPACE = 0x12                          # 560 us space
NEC_TRAILER = [0x12, 0x00, 0x05, 0x1E]         # 560 us stop bit + ~40 ms silence


@dataclass(frozen=True)
class CommandSpec:
    menu_id: str
    key: str
    cmd: int
    name: str
    desc: str


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("1",  "power",      0x11, "Power Toggle (ON/OFF)",        "Toggles main lamp power state"),
    CommandSpec("2",  "timer",      0x1D, "Sleep Timer 15m (Toggle)",     "Odd click: 2 blinks (15m ON) | Even click: 3 blinks (OFF)"),
    CommandSpec("3",  "max",        0x03, "Max Brightness (100%)",        "Sets brightness to 5/5 (100%), CCT 3/5 (Neutral White)"),
    CommandSpec("4",  "bright_up",  0x18, "Brightness Up (+)",            "Each press increases brightness by 0.5/5; two presses make one full 1/5 step, up to 5/5"),
    CommandSpec("5",  "bright_dn",  0x1F, "Brightness Down (-)",          "Each press decreases brightness by 0.5/5; two presses make one full 1/5 step, down to 1/5"),
    CommandSpec("6",  "cct_cool",   0x07, "CCT Cooler (+)",               "Each press shifts CCT by 0.5/5 toward cool white; two presses make one full 1/5 step, up to 5/5"),
    CommandSpec("7",  "cct_warm",   0x0F, "CCT Warmer (-)",               "Each press shifts CCT by 0.5/5 toward warm yellow; two presses make one full 1/5 step, down to 1/5"),
    CommandSpec("8",  "daylight",   0x19, "Preset: Daylight Mode",        "CCT 5/5 (Cool White), Brightness 5/5"),
    CommandSpec("9",  "work",       0x16, "Preset: Reading / Work Mode",  "CCT 4/5 (Neutral White), Brightness 5/5"),
    CommandSpec("10", "relax",      0x12, "Preset: Relax / Warm Bright",  "CCT 1/5 (Warm Yellow), Brightness 4/5"),
    CommandSpec("11", "warm_mid",   0x0A, "Preset: Warm Medium",          "CCT 1/5 (Warm Yellow), Brightness 3/5"),
    CommandSpec("12", "nightlight", 0x0C, "Preset: Night Light (Bottle)", "CCT 1/5 (Warm Yellow), Brightness 1/5"),
)

COMMANDS_BY_MENU = {c.menu_id: c for c in COMMANDS}
COMMANDS_BY_KEY = {c.key: c for c in COMMANDS}


def build_nec_packet(addr_l: int, addr_h: int, cmd: int, repeats: int = 0) -> bytearray:
    """
    Constructs a raw Broadlink IR packet for the standard 32-bit NEC protocol (38 kHz).
    Format: [Addr_L, Addr_H, Cmd, ~Cmd] sent LSB-first.
    """
    if not (0 <= repeats <= 255):
        raise ValueError(f"Repeat count must be between 0 and 255, got {repeats}.")

    inv_cmd = (cmd ^ 0xFF) & 0xFF
    frame_bytes = (addr_l & 0xFF, addr_h & 0xFF, cmd & 0xFF, inv_cmd)

    pulses = list(NEC_HDR_MARK_SPACE)
    for byte_val in frame_bytes:
        for bit_idx in range(8):
            bit = (byte_val >> bit_idx) & 1
            pulses.append(NEC_BIT_MARK)
            pulses.append(NEC_ONE_SPACE if bit else NEC_ZERO_SPACE)

    pulses.extend(NEC_TRAILER)

    length = len(pulses)
    header = [BL_PACKET_TYPE_IR, repeats, length & 0xFF, (length >> 8) & 0xFF]
    return bytearray(header + pulses)


def parse_address(addr_str: str) -> tuple[int, int]:
    """
    Parses a 16-bit hex address (e.g., '0x22DD', '0x00FF') or 8-bit address (e.g., '0x22' -> '0x22DD').
    Returns (addr_low, addr_high).
    """
    cleaned = addr_str.strip().lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]

    if not cleaned or not all(c in "0123456789abcdef" for c in cleaned):
        raise ValueError(f"Invalid hexadecimal address: '{addr_str}'")

    val = int(cleaned, 16)
    if len(cleaned) <= 2:
        return val, val ^ 0xFF
    if len(cleaned) <= 4 and val <= 0xFFFF:
        return (val >> 8) & 0xFF, val & 0xFF

    raise ValueError(f"Address '{addr_str}' exceeds 16-bit range (0x0000 - 0xFFFF).")


def parse_hex_byte(byte_str: str) -> int:
    """Parses and validates a single hexadecimal byte (0x00 - 0xFF)."""
    val = int(byte_str.strip(), 16)
    if not (0x00 <= val <= 0xFF):
        raise ValueError(f"Hex byte '{byte_str}' out of range (must be 0x00 - 0xFF).")
    return val


def parse_raw_payload(raw_str: str) -> bytearray:
    """
    Decodes a raw Broadlink payload from either Hex or Base64 string.
    Supports optional 'hex:' or 'b64:' prefixes.
    """
    s = raw_str.strip()
    if s.lower().startswith("hex:"):
        return bytearray.fromhex(s[4:].strip())
    if s.lower().startswith("b64:"):
        return bytearray(base64.b64decode(s[4:].strip()))

    # Heuristic: Broadlink IR hex packets start with '26' and contain only hex chars
    is_hex = len(s) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in s)
    if is_hex and s.startswith("26"):
        return bytearray.fromhex(s)

    return bytearray(base64.b64decode(s))


def connect_broadlink(host_ip: Optional[str] = None, timeout: int = 4):
    """Discovers or connects directly to a Broadlink IR device on the local network."""
    if host_ip:
        print(f"Connecting to Broadlink device at {host_ip}...")
        device = broadlink.hello(host_ip, timeout=timeout)
    else:
        print("Discovering Broadlink IR devices on the local network...")
        discovered = broadlink.discover(timeout=timeout)
        ir_devices = [d for d in discovered if hasattr(d, "send_data")]

        if not ir_devices:
            raise ConnectionError(
                "No Broadlink IR devices found on the local network. "
                "Ensure your PC and hub are on the same subnet, or specify --host <IP>."
            )

        if len(ir_devices) == 1:
            device = ir_devices[0]
        else:
            print(f"\nFound {len(ir_devices)} Broadlink IR devices:")
            for idx, dev in enumerate(ir_devices, 1):
                print(f"  [{idx}] {dev.type} at {dev.host[0]} (MAC: {dev.mac.hex(':')})")
            sel = input(f"Select device [1-{len(ir_devices)}, default=1]: ").strip()
            chosen_idx = int(sel) - 1 if sel.isdigit() and 1 <= int(sel) <= len(ir_devices) else 0
            device = ir_devices[chosen_idx]

    device.auth()
    print(f"Connected to {device.type} at {device.host[0]} (MAC: {device.mac.hex(':')})")
    return device


def send_ir_packet(device, packet: bytearray, dry_run: bool = False) -> bool:
    """Sends a raw IR packet to the Broadlink device with automatic retry on timeout."""
    if dry_run or device is None:
        return True

    for attempt in range(1, 4):
        try:
            device.send_data(packet)
            return True
        except (BroadlinkException, OSError, TimeoutError) as err:
            print(f"[WARN] Transmission attempt {attempt}/3 failed ({err}). Retrying...", file=sys.stderr)
            time.sleep(0.8)
            try:
                device.auth()
            except (BroadlinkException, OSError):
                pass

    print("[ERROR] Failed to transmit IR packet after 3 attempts.", file=sys.stderr)
    return False


def print_packet_info(addr_l: int, addr_h: int, cmd: int, packet: bytearray, label: str, dry_run: bool = False):
    """Displays technical details of the transmitted (or generated) NEC frame."""
    inv_cmd = (cmd ^ 0xFF) & 0xFF
    b64_payload = base64.b64encode(packet).decode("ascii")
    status = "Generated (Dry Run)" if dry_run else "Transmitted"
    print("-" * 76)
    print(f"Status    : {status} -> {label}")
    print(f"NEC Frame : Addr=0x{addr_l:02X}{addr_h:02X} | Cmd=0x{cmd:02X} (~Cmd=0x{inv_cmd:02X})")
    print(f"Base64    : {b64_payload}")
    print(f"Raw Hex   : {packet.hex()}")
    print("-" * 76)


def interactive_loop(device, default_addr_l: int, default_addr_h: int, dry_run: bool = False):
    """Runs the interactive console remote control menu."""
    addr_l, addr_h = default_addr_l, default_addr_h

    while True:
        mode_tag = " [DRY RUN]" if dry_run else ""
        print("\n" + "=" * 76)
        print(f"SIBRILLE LED DESK LAMP - IR REMOTE (Addr: 0x{addr_l:02X}{addr_h:02X}){mode_tag}")
        print("=" * 76)
        for spec in COMMANDS:
            print(f"  [{spec.menu_id:>2}] 0x{spec.cmd:02X} - {spec.name:<32} | {spec.desc}")
        print("-" * 76)
        print("  [ C] Send Custom Command (Hex byte, e.g., 0x1A or 0x00)")
        print("  [ A] Change NEC Address (Default: 0x22DD)")
        print("  [ R] Send Raw Broadlink Base64 / Hex Payload")
        print("  [ Q] Quit")
        print("=" * 76)

        choice = input("Select button [1-12 / C / A / R / Q]: ").strip().upper()

        if choice == "Q":
            print("Exiting remote control.")
            break

        if choice in COMMANDS_BY_MENU:
            spec = COMMANDS_BY_MENU[choice]
            pkt = build_nec_packet(addr_l, addr_h, spec.cmd)
            if send_ir_packet(device, pkt, dry_run=dry_run):
                print_packet_info(addr_l, addr_h, spec.cmd, pkt, label=spec.name, dry_run=dry_run)

        elif choice == "C":
            raw_cmd = input("Enter custom command byte in hex (e.g., 0x1A or 1A): ").strip()
            try:
                cmd_val = parse_hex_byte(raw_cmd)
                reps_in = input("Number of hardware repeats [0-255, Default = 0]: ").strip()
                reps = int(reps_in) if reps_in else 0
                pkt = build_nec_packet(addr_l, addr_h, cmd_val, repeats=reps)
                if send_ir_packet(device, pkt, dry_run=dry_run):
                    print_packet_info(
                        addr_l, addr_h, cmd_val, pkt, label=f"Custom Command 0x{cmd_val:02X}", dry_run=dry_run
                    )
            except ValueError as err:
                print(f"[!] Input error: {err}")

        elif choice == "A":
            raw_addr = input("Enter 16-bit NEC address in hex (e.g., 0x22DD) or [Enter] to reset: ").strip()
            if not raw_addr:
                addr_l, addr_h = DEFAULT_ADDR_L, DEFAULT_ADDR_H
                print("Address reset to 0x22DD.")
            else:
                try:
                    addr_l, addr_h = parse_address(raw_addr)
                    print(f"Active NEC address updated to: 0x{addr_l:02X}{addr_h:02X}")
                except ValueError as err:
                    print(f"[!] {err}")

        elif choice == "R":
            raw_payload = input("Paste Broadlink Base64 or Hex string: ").strip()
            if not raw_payload:
                continue
            try:
                pkt = parse_raw_payload(raw_payload)
                if send_ir_packet(device, pkt, dry_run=dry_run):
                    print(f"Processed raw payload ({len(pkt)} bytes).")
            except Exception as err:
                print(f"[!] Failed to decode payload: {err}")

        else:
            print("[!] Unknown option. Choose 1-12, C, A, R, or Q.")


def main():
    parser = argparse.ArgumentParser(
        description="Broadlink IR Remote Controller for SIBRILLE Double Head LED Desk Lamp (NEC 0x22DD)"
    )
    parser.add_argument("--host", type=str, default=None, help="Broadlink device IP address (auto-discovers if omitted)")
    parser.add_argument("--addr", type=str, default="0x22DD", help="NEC 16-bit address in hex (default: 0x22DD)")
    parser.add_argument("--repeats", type=int, default=0, help="Hardware repeat count for the IR frame (0-255, default: 0)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and print IR packets without connecting to a Broadlink device",
    )

    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--cmd",
        type=str.lower,
        choices=list(COMMANDS_BY_KEY.keys()),
        help="Send a verified lamp command by key",
    )
    action_group.add_argument(
        "--custom",
        type=str,
        default=None,
        help="Send a custom command byte in hex (e.g., 0x1A)",
    )

    args = parser.parse_args()

    try:
        addr_l, addr_h = parse_address(args.addr)
        device = None if args.dry_run else connect_broadlink(args.host)

        if args.cmd:
            spec = COMMANDS_BY_KEY[args.cmd]
            pkt = build_nec_packet(addr_l, addr_h, spec.cmd, repeats=args.repeats)
            if send_ir_packet(device, pkt, dry_run=args.dry_run):
                print_packet_info(addr_l, addr_h, spec.cmd, pkt, label=spec.name, dry_run=args.dry_run)
            return

        if args.custom:
            cmd_val = parse_hex_byte(args.custom)
            pkt = build_nec_packet(addr_l, addr_h, cmd_val, repeats=args.repeats)
            if send_ir_packet(device, pkt, dry_run=args.dry_run):
                print_packet_info(
                    addr_l, addr_h, cmd_val, pkt, label=f"Custom Command 0x{cmd_val:02X}", dry_run=args.dry_run
                )
            return

        interactive_loop(device, addr_l, addr_h, dry_run=args.dry_run)

    except (ValueError, ConnectionError, BroadlinkException, OSError) as err:
        print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("\nExited.")


if __name__ == "__main__":
    main()