#!/data/data/com.termux/files/usr/bin/bash
set -eu
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT_DIR"
XMRIG_VERSION="${XMRIG_VERSION:-v6.25.0}"
if [ -z "${PREFIX:-}" ] || [ ! -x "${PREFIX}/bin/pkg" ]; then
  echo "Erro: execute este script dentro do Termux oficial." >&2; exit 1
fi
echo "Instalando dependências do Termux..."
pkg update
pkg install -y python git clang cmake make libuv openssl
DPKG_ARCH="$(dpkg --print-architecture)"
case "$DPKG_ARCH" in
  aarch64) ARM_TARGET=8; ARM_FLAGS="" ;;
  arm) ARM_TARGET=7; ARM_FLAGS="-march=armv7-a -mfpu=neon" ;;
  *) echo "Erro: arquitetura Termux não suportada: $DPKG_ARCH" >&2; exit 1 ;;
esac
mkdir -p "$ROOT_DIR/vendor" "$ROOT_DIR/data"
if [ ! -d "$ROOT_DIR/vendor/xmrig/.git" ]; then
  git clone --branch "$XMRIG_VERSION" --depth 1 https://github.com/xmrig/xmrig.git "$ROOT_DIR/vendor/xmrig"
fi
cmake -S "$ROOT_DIR/vendor/xmrig" -B "$ROOT_DIR/vendor/xmrig/build" \
  -DCMAKE_BUILD_TYPE=Release -DARM_TARGET="$ARM_TARGET" \
  -DCMAKE_C_FLAGS="$ARM_FLAGS" -DCMAKE_CXX_FLAGS="$ARM_FLAGS" \
  -DWITH_HWLOC=OFF -DWITH_OPENCL=OFF -DWITH_CUDA=OFF \
  -DWITH_HTTP=ON -DWITH_TLS=ON -DWITH_ASM=OFF \
  -DWITH_SSE4_1=OFF -DWITH_AVX2=OFF -DWITH_VAES=OFF -DWITH_MSR=OFF
cmake --build "$ROOT_DIR/vendor/xmrig/build" --parallel "$(nproc)"
if [ ! -f "$ROOT_DIR/config.toml" ]; then cp "$ROOT_DIR/config.example.toml" "$ROOT_DIR/config.toml"; fi
python "$ROOT_DIR/scripts/preflight.py" --config "$ROOT_DIR/config.toml"
echo "Instalação concluída. Edite config.toml e execute ./start.sh"
