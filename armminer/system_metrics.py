from __future__ import annotations

import os
import platform
import time
from pathlib import Path


class SystemMetrics:
    def __init__(self):
        self.prev_cpu: tuple[int, int] | None = None

    def snapshot(self) -> dict:
        return {
            "architecture": platform.machine(), "cpu_count": os.cpu_count(),
            "cpu_percent": self._cpu(), "memory": self._memory(),
            "load_average": self._load(), "system_uptime": self._uptime(),
            "temperature_c": self._temperature(), "frequency_mhz": self._frequency(),
            "thermal_throttling": None,
        }

    def _cpu(self):
        try:
            fields = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
            idle, total = fields[3] + fields[4], sum(fields)
            current = (idle, total)
            if self.prev_cpu is None: value = None
            else:
                di, dt = idle - self.prev_cpu[0], total - self.prev_cpu[1]
                value = round(100 * (1 - di / dt), 1) if dt else None
            self.prev_cpu = current
            return value
        except (OSError, ValueError, IndexError): return None

    @staticmethod
    def _memory():
        try:
            rows = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, v = line.split(":", 1); rows[k] = int(v.split()[0]) * 1024
            return {"total": rows["MemTotal"], "available": rows.get("MemAvailable"), "used": rows["MemTotal"] - rows.get("MemAvailable", rows.get("MemFree", 0))}
        except (OSError, ValueError, KeyError): return None

    @staticmethod
    def _load():
        try:
            getter = getattr(os, "getloadavg", None)
            values = getter() if getter else [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
            return [round(x, 2) for x in values]
        except (OSError, ValueError): return None

    @staticmethod
    def _uptime():
        try: return int(float(Path("/proc/uptime").read_text().split()[0]))
        except (OSError, ValueError, IndexError): return None

    @staticmethod
    def _temperature():
        values = []
        for p in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
            try:
                v = float(p.read_text().strip()); v = v / 1000 if v > 200 else v
                if 0 < v < 150: values.append(v)
            except (OSError, ValueError): pass
        return round(max(values), 1) if values else None

    @staticmethod
    def _frequency():
        vals = []
        for p in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_cur_freq"):
            try: vals.append(float(p.read_text()) / 1000)
            except (OSError, ValueError): pass
        return round(sum(vals) / len(vals), 1) if vals else None
