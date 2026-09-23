#!/data/data/com.termux/files/usr/bin/bash
set -eu
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"; PID_FILE="$ROOT_DIR/data/dashboard.pid"
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then echo "Dashboard ativo (PID $(cat "$PID_FILE"))."; exit 0; fi
echo "Dashboard parado."; exit 1
