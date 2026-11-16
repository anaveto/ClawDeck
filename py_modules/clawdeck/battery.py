"""Battery: only what the power profiles need, whether the Claw is on the charger (profiles and autotune's
ceiling differ on battery and plugged in) and how long the charge lasts at a TDP. Charge limit, Wh and watt readouts
left the plugin in the 2026-10-21 scope reset (Steam's own battery panel shows charge; docs/HARDWARE-FINDINGS.md §6).
"""
from __future__ import annotations

import os

from . import hw, sysfs


class Battery:
    def __init__(self, hardware: hw.Hardware):
        self.p = hardware.paths
        self.system_w = hardware.model.get("system_w")

    def plugged(self) -> bool | None:
        for name in ("ACAD", "AC", "AC0", "ADP1", "ucsi-source-psy-USBC000:001"):
            v = sysfs.read_int(f"/sys/class/power_supply/{name}/online")
            if v is not None:
                return v == 1
        for d in os.listdir("/sys/class/power_supply") if os.path.isdir("/sys/class/power_supply") else []:
            t = sysfs.read(f"/sys/class/power_supply/{d}/type")
            if t in ("Mains", "USB", "USB_PD", "USB_C"):
                v = sysfs.read_int(f"/sys/class/power_supply/{d}/online")
                if v is not None:
                    return v == 1
        return None

    def minutes(self, lo: int, hi: int) -> dict[int, int] | None:
        """How long the charge lasts with the package drawing each of lo..hi W, in minutes (down to 5): the Wh left
        (charge_now x the design voltage, as UPower counts a battery without energy_*) over what the whole machine
        draws at that package draw (hw.MODELS "system_w"; HARDWARE-FINDINGS §25). None where either is not known.
        A game that draws less than its limit lasts longer."""
        bat = self.p.battery
        if not self.system_w or not bat:
            return None
        uah, uv = sysfs.read_int(f"{bat}/charge_now"), sysfs.read_int(f"{bat}/voltage_min_design")
        if uah is None or not uv:
            return None
        base, per_w = self.system_w
        return {w: int(uah * uv / 1e12 / (base + per_w * w) * 60) // 5 * 5 for w in range(lo, hi + 1)}
