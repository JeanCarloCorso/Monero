#!/data/data/com.termux/files/usr/bin/bash
set -eu
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"; PID_FILE="$ROOT_DIR/data/dashboard.pid"
if [ ! -f "$PID_FILE" ]; then echo "Dashboard não está ativo."; exit 0; fi
PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then kill "$PID"; for _ in 1 2 3 4 5 6 7 8; do kill -0 "$PID" 2>/dev/null || break; sleep 1; done; fi
rm -f "$PID_FILE"; echo "Dashboard encerrado."
