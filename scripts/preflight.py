#!/usr/bin/env python3
import argparse, os, platform, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from armminer.config import load_config

p=argparse.ArgumentParser();p.add_argument("--config",required=True);a=p.parse_args()
cfg=load_config(Path(a.config)); arch=platform.machine().lower(); errors=[]; warnings=[]
if arch not in {"aarch64","arm64","arm","armv7","armv7l","armv8l"}: errors.append(f"arquitetura não suportada: {arch}")
is_arm32=arch in {"arm","armv7","armv7l","armv8l"}
if is_arm32 and cfg.randomx_mode != 'light': errors.append("ARM 32-bit exige randomx_mode=\"light\"")
mem=None
try:
    mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:')))*1024
except (OSError,StopIteration,ValueError): warnings.append("não foi possível detectar a RAM")
if mem and cfg.randomx_mode != 'light' and mem < 3_000_000_000: warnings.append("menos de 3 GB de RAM: considere randomx_mode=\"light\"")
if is_arm32: warnings.append("ARM 32-bit usa RandomX interpretado/light; o hashrate será baixo")
x=Path(cfg.xmrig_path)
if not x.is_absolute(): x=Path(a.config).resolve().parent/x
if not x.exists(): warnings.append(f"XMRig ainda não encontrado em {x}")
print(f"Arquitetura: {arch}; CPUs: {os.cpu_count()}; RAM: {round(mem/1073741824,1) if mem else '?'} GB")
for w in warnings: print("AVISO:",w)
if errors:
    for e in errors: print("ERRO:",e)
    raise SystemExit(1)
print("Pré-verificação concluída.")
