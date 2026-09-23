from __future__ import annotations

import argparse
import hmac
import json
import logging
import signal
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .config import Config, load_config, load_or_create_token, save_config
from .miner import MinerManager
from .system_metrics import SystemMetrics

ROOT = Path(__file__).resolve().parent.parent


class App:
    def __init__(self, cfg: Config, config_path: Path):
        self.cfg, self.config_path = cfg, config_path
        self.data_dir = ROOT / "data"
        token_path = Path(cfg.auth_token_file)
        if not token_path.is_absolute(): token_path = ROOT / token_path
        self.token = load_or_create_token(token_path)
        self.miner = MinerManager(cfg, self.data_dir)
        self.system = SystemMetrics()
        self.boot = time.time()

    def snapshot(self):
        return {"version": __version__, "dashboard_uptime": int(time.time() - self.boot), "miner": self.miner.status(),
                "system": self.system.snapshot(), "config": self.cfg.public(), "timestamp": int(time.time())}


def handler_for(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ARMMoneroDashboard/" + __version__

        def log_message(self, fmt, *args): logging.getLogger("armminer.http").info(fmt, *args)

        def _json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

        def _auth(self):
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
            return bool(supplied) and hmac.compare_digest(supplied, app.token)

        def _body(self):
            size = int(self.headers.get("Content-Length", 0))
            if size > 16_384: raise ValueError("corpo excede 16 KiB")
            return json.loads(self.rfile.read(size) or b"{}")

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/v1/status": return self._json(app.snapshot())
            if path == "/api/v1/logs":
                if not self._auth(): return self._json({"error": "não autorizado"}, 401)
                return self._json({"lines": list(app.miner.logs)})
            if path == "/api/v1/events":
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-store"); self.send_header("Connection", "keep-alive"); self.end_headers()
                try:
                    while True:
                        payload = json.dumps(app.snapshot(), ensure_ascii=False)
                        self.wfile.write(f"data: {payload}\n\n".encode()); self.wfile.flush(); time.sleep(app.cfg.metrics_interval)
                except (BrokenPipeError, ConnectionResetError): pass
                return
            if path in {"/", "/index.html"}: return self._static("index.html", "text/html; charset=utf-8")
            if path == "/app.js": return self._static("app.js", "text/javascript; charset=utf-8")
            if path == "/style.css": return self._static("style.css", "text/css; charset=utf-8")
            return self._json({"error": "não encontrado"}, 404)

        def _static(self, name, content_type):
            body = (ROOT / "web" / name).read_bytes()
            self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'")
            self.send_header("Referrer-Policy", "no-referrer"); self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            if not self._auth(): return self._json({"error": "não autorizado"}, 401)
            action = urlparse(self.path).path.removeprefix("/api/v1/miner/")
            try:
                if action == "start": app.miner.start()
                elif action == "stop": app.miner.stop()
                elif action == "pause": app.miner.pause()
                elif action == "resume": app.miner.resume()
                elif action == "restart": app.miner.stop(); app.miner.start()
                else: return self._json({"error": "ação desconhecida"}, 404)
                return self._json({"ok": True, "state": app.miner.status()["state"]})
            except RuntimeError as exc: return self._json({"error": str(exc)}, 409)
            except Exception:
                logging.exception("Falha no controle do minerador")
                return self._json({"error": "falha interna"}, 500)

        def do_PUT(self):
            if urlparse(self.path).path != "/api/v1/config": return self._json({"error": "não encontrado"}, 404)
            if not self._auth(): return self._json({"error": "não autorizado"}, 401)
            if app.miner.status()["state"] != "stopped": return self._json({"error": "pare o minerador antes de alterar a configuração"}, 409)
            allowed = {"pool", "pool_password", "wallet", "worker", "threads", "cpu_limit", "priority", "randomx_mode"}
            try:
                body = self._body()
                if not isinstance(body, dict) or set(body) - allowed: raise ValueError("campos de configuração inválidos")
                current = {k: getattr(app.cfg, k) for k in Config.__dataclass_fields__}
                candidate = Config(**(current | body)); errors = candidate.validate()
                if errors: raise ValueError("; ".join(errors))
                save_config(app.config_path, candidate); app.cfg = candidate; app.miner.cfg = candidate
                logging.info("Configuração atualizada: %s", ", ".join(sorted(body)))
                return self._json({"ok": True, "config": candidate.public()})
            except (ValueError, TypeError) as exc: return self._json({"error": str(exc)}, 400)

    return Handler


def configure_logging(cfg: Config):
    (ROOT / "data").mkdir(exist_ok=True)
    handler = RotatingFileHandler(ROOT / "data" / "dashboard.log", maxBytes=cfg.log_max_bytes, backupCount=cfg.log_backups)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", handlers=[handler, logging.StreamHandler()])


def main(argv=None):
    parser = argparse.ArgumentParser(description="ARM Monero Miner Dashboard")
    parser.add_argument("--config", default=str(ROOT / "config.toml")); parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try: cfg = load_config(Path(args.config).resolve())
    except (OSError, ValueError) as exc: parser.error(str(exc))
    if args.check: print("Configuração válida"); return 0
    configure_logging(cfg); app = App(cfg, Path(args.config))
    server = ThreadingHTTPServer((cfg.dashboard_host, cfg.dashboard_port), handler_for(app))
    def shutdown(*_): threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown); signal.signal(signal.SIGINT, shutdown)
    logging.info("Dashboard em http://%s:%s", cfg.dashboard_host, cfg.dashboard_port)
    try: server.serve_forever()
    finally: app.miner.stop(); server.server_close()
    return 0


if __name__ == "__main__": raise SystemExit(main())
