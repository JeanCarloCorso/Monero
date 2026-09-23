from __future__ import annotations

import ipaddress
import os
import platform
import re
import secrets
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse


WALLET_RE = re.compile(r"^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{90,110}$")


@dataclass(slots=True)
class Config:
    pool: str = "pool.supportxmr.com:3333"
    pool_password: str = "{worker}"
    wallet: str = ""
    worker: str = "android-arm"
    threads: int = 1
    cpu_limit: int = 50
    priority: int = 1
    randomx_mode: str = "auto"
    xmrig_path: str = "./vendor/xmrig/build/xmrig"
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8080
    lan_access: bool = False
    auth_token_file: str = "./data/admin.token"
    metrics_interval: int = 3
    xmrig_api_port: int = 18080
    log_max_bytes: int = 2_000_000
    log_backups: int = 2

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not valid_pool(self.pool): errors.append("pool deve ser host:porta ou stratum+tcp(s)://host:porta")
        if not re.fullmatch(r"[A-Za-z0-9_.{}~/-]{1,128}", self.pool_password): errors.append("pool_password inválido")
        if self.wallet and not WALLET_RE.fullmatch(self.wallet): errors.append("carteira Monero inválida")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", self.worker): errors.append("worker inválido")
        cpus = os.cpu_count() or 1
        if not 1 <= self.threads <= cpus: errors.append(f"threads deve estar entre 1 e {cpus}")
        if not 1 <= self.cpu_limit <= 100: errors.append("cpu_limit deve estar entre 1 e 100")
        if not 0 <= self.priority <= 5: errors.append("priority deve estar entre 0 e 5")
        if self.randomx_mode not in {"auto", "fast", "light"}: errors.append("randomx_mode inválido")
        if is_32bit_arm() and self.randomx_mode != "light": errors.append("ARM 32-bit requer randomx_mode='light'")
        if not 1024 <= self.dashboard_port <= 65535: errors.append("dashboard_port inválida")
        if not 1024 <= self.xmrig_api_port <= 65535: errors.append("xmrig_api_port inválida")
        if self.dashboard_port == self.xmrig_api_port: errors.append("as portas do dashboard e XMRig devem diferir")
        if self.dashboard_host == "0.0.0.0" and not self.lan_access: errors.append("lan_access=true é obrigatório para escutar em 0.0.0.0")
        if self.metrics_interval not in range(1, 61): errors.append("metrics_interval deve estar entre 1 e 60")
        return errors

    def public(self) -> dict:
        data = asdict(self)
        data["wallet"] = mask_wallet(self.wallet)
        data.pop("auth_token_file", None)
        return data


def valid_pool(value: str) -> bool:
    target = value if "://" in value else "stratum+tcp://" + value
    try:
        p = urlparse(target)
        return p.scheme in {"stratum+tcp", "stratum+ssl", "stratum+tls"} and bool(p.hostname) and 1 <= (p.port or 0) <= 65535
    except ValueError:
        return False


def is_32bit_arm() -> bool:
    machine = platform.machine().lower()
    return machine in {"arm", "armv7", "armv7l", "armv8l"} or (machine.startswith("arm") and "64" not in machine)


def mask_wallet(value: str) -> str:
    return f"{value[:6]}…{value[-6:]}" if len(value) > 16 else ("configurada" if value else "não configurada")


def load_config(path: Path) -> Config:
    if not path.exists(): raise FileNotFoundError(f"Configuração não encontrada: {path}")
    with path.open("rb") as f: raw = tomllib.load(f)
    values = raw.get("miner", {}) | raw.get("server", {}) | raw.get("logging", {})
    allowed = set(Config.__dataclass_fields__)
    unknown = set(values) - allowed
    if unknown: raise ValueError("Opções desconhecidas: " + ", ".join(sorted(unknown)))
    cfg = Config(**values)
    errors = cfg.validate()
    if errors: raise ValueError("; ".join(errors))
    return cfg


def load_or_create_token(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        token = path.read_text().strip()
        if len(token) >= 32: return token
    token = secrets.token_urlsafe(32)
    path.write_text(token + "\n")
    path.chmod(0o600)
    return token


def save_config(path: Path, cfg: Config) -> None:
    import json
    groups = {"miner": ["pool", "pool_password", "wallet", "worker", "threads", "cpu_limit", "priority", "randomx_mode", "xmrig_path", "xmrig_api_port"], "server": ["dashboard_host", "dashboard_port", "lan_access", "auth_token_file", "metrics_interval"], "logging": ["log_max_bytes", "log_backups"]}
    lines = []
    for group, keys in groups.items():
        lines.append(f"[{group}]")
        for key in keys:
            value = getattr(cfg, key)
            rendered = str(value).lower() if isinstance(value, bool) else json.dumps(value, ensure_ascii=False) if isinstance(value, str) else str(value)
            lines.append(f"{key} = {rendered}")
        lines.append("")
    tmp = path.with_suffix(path.suffix + ".tmp"); tmp.write_text("\n".join(lines)); tmp.replace(path)
