#!/data/data/com.termux/files/usr/bin/bash
set -eu
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
"$ROOT_DIR/stop.sh" || true
echo "Por segurança, nenhum arquivo foi apagado. Para remover, exclua manualmente: $ROOT_DIR"
