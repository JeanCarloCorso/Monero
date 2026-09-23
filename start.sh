#!/data/data/com.termux/files/usr/bin/bash
set -eu
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"; PID_FILE="$ROOT_DIR/data/dashboard.pid"
cd "$ROOT_DIR"
mkdir -p "$ROOT_DIR/data"
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then echo "Dashboard já está ativo (PID $(cat "$PID_FILE"))."; exit 0; fi
python "$ROOT_DIR/scripts/preflight.py" --config "$ROOT_DIR/config.toml"
nohup python -m armminer.server --config "$ROOT_DIR/config.toml" >>"$ROOT_DIR/data/launcher.log" 2>&1 &
PID=$!; echo "$PID" > "$PID_FILE"; sleep 1
if ! kill -0 "$PID" 2>/dev/null; then echo "Falha ao iniciar. Consulte data/launcher.log" >&2; exit 1; fi
HOST="$(python -c 'import tomllib;print(tomllib.load(open("config.toml","rb"))["server"]["dashboard_host"])')"
PORT="$(python -c 'import tomllib;print(tomllib.load(open("config.toml","rb"))["server"]["dashboard_port"])')"
if [ "$HOST" = "0.0.0.0" ]; then HOST="$(ip route get 1 2>/dev/null | awk '{for(i=1;i<=NF;i++)if($i=="src"){print $(i+1);exit}}')"; fi
echo "Dashboard iniciado: http://${HOST:-127.0.0.1}:$PORT"
echo "Token administrativo: $ROOT_DIR/data/admin.token"
