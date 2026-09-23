from __future__ import annotations

import collections
import json
import logging
import os
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import Config

LOG = logging.getLogger("armminer.miner")


class MinerManager:
    def __init__(self, cfg: Config, data_dir: Path):
        self.cfg, self.data_dir = cfg, data_dir
        self.process: subprocess.Popen | None = None
        self.started_at: float | None = None
        self.paused = False
        self.logs = collections.deque(maxlen=500)
        self.lock = threading.RLock()
        self.last_error: str | None = None
        self.api_token = os.urandom(24).hex()

    def _xmrig_config(self) -> dict:
        pool = self.cfg.pool.split("://", 1)[-1]
        max_threads = max(1, min(self.cfg.threads, int((os.cpu_count() or 1) * self.cfg.cpu_limit / 100) or 1))
        return {
            "autosave": False, "background": False,
            "api": {"worker-id": self.cfg.worker},
            "http": {"enabled": True, "host": "127.0.0.1", "port": self.cfg.xmrig_api_port, "access-token": self.api_token, "restricted": True},
            "randomx": {"mode": self.cfg.randomx_mode, "1gb-pages": False, "wrmsr": False, "rdmsr": False},
            "cpu": {"enabled": True, "huge-pages": False, "yield": True, "max-threads-hint": self.cfg.cpu_limit},
            "pools": [{"algo": "rx/0", "url": pool, "user": self.cfg.wallet, "pass": self.cfg.pool_password.replace("{worker}", self.cfg.worker), "keepalive": True, "tls": self.cfg.pool.startswith(("stratum+ssl://", "stratum+tls://"))}],
            "print-time": 10, "retries": 10, "retry-pause": 5,
        }, max_threads

    def start(self):
        with self.lock:
            if self.process and self.process.poll() is None: raise RuntimeError("minerador já está em execução")
            if not self.cfg.wallet: raise RuntimeError("configure uma carteira antes de iniciar")
            binary = Path(self.cfg.xmrig_path).expanduser().resolve()
            if not binary.is_file() or not os.access(binary, os.X_OK): raise RuntimeError(f"XMRig não encontrado ou não executável: {binary}")
            config, threads = self._xmrig_config()
            self.data_dir.mkdir(parents=True, exist_ok=True)
            generated = self.data_dir / "xmrig.generated.json"
            generated.write_text(json.dumps(config, indent=2))
            cmd = [str(binary), "--config", str(generated), "--threads", str(threads), "--cpu-priority", str(self.cfg.priority)]
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
            self.started_at, self.paused, self.last_error = time.time(), False, None
            threading.Thread(target=self._read_logs, daemon=True).start()
            LOG.info("XMRig iniciado pid=%s threads=%s", self.process.pid, threads)

    def _read_logs(self):
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            clean = line.rstrip(); self.logs.append(clean); LOG.info("xmrig: %s", clean)
        code = self.process.poll()
        if code and code != 0: self.last_error = f"XMRig encerrou com código {code}"

    def stop(self):
        with self.lock:
            if not self.process or self.process.poll() is not None: return
            os.killpg(self.process.pid, signal.SIGTERM)
            try: self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL); self.process.wait(timeout=2)
            self.paused = False; LOG.info("XMRig encerrado")

    def pause(self):
        with self.lock:
            if not self.process or self.process.poll() is not None: raise RuntimeError("minerador não está ativo")
            os.killpg(self.process.pid, signal.SIGSTOP); self.paused = True; LOG.info("XMRig pausado")

    def resume(self):
        with self.lock:
            if not self.process or self.process.poll() is not None: raise RuntimeError("minerador não está ativo")
            os.killpg(self.process.pid, signal.SIGCONT); self.paused = False; LOG.info("XMRig retomado")

    def status(self) -> dict:
        alive = bool(self.process and self.process.poll() is None)
        base = {"state": "paused" if alive and self.paused else "running" if alive else "stopped", "pid": self.process.pid if alive else None,
                "uptime": int(time.time() - self.started_at) if alive and self.started_at else 0, "last_error": self.last_error,
                "hashrate": {"current": None, "average": None, "minute_1": None, "minute_5": None, "minute_15": None},
                "shares": {"accepted": 0, "rejected": 0, "reject_rate": 0}, "connection": "disconnected", "last_share": None}
        if not alive or self.paused: return base
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.cfg.xmrig_api_port}/2/summary", headers={"Authorization": "Bearer " + self.api_token})
            with urllib.request.urlopen(req, timeout=1) as response: x = json.load(response)
            total = x.get("hashrate", {}).get("total", [])
            accepted, rejected = x.get("results", {}).get("shares_good", 0), x.get("results", {}).get("shares_total", 0) - x.get("results", {}).get("shares_good", 0)
            base.update({"hashrate": {"current": _at(total, 0), "average": _at(total, 2), "minute_1": _at(total, 0), "minute_5": _at(total, 1), "minute_15": _at(total, 2)},
                         "shares": {"accepted": accepted, "rejected": rejected, "reject_rate": round(100 * rejected / (accepted + rejected), 2) if accepted + rejected else 0},
                         "connection": "connected" if x.get("connection", {}).get("pool") else "connecting", "last_share": x.get("results", {}).get("best")})
        except (OSError, ValueError, urllib.error.URLError): base["connection"] = "starting"
        return base


def _at(values, index):
    try: return values[index]
    except (IndexError, TypeError): return None
