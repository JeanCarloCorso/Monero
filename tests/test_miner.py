import json, os, stat, time
from pathlib import Path
from armminer.config import Config
from armminer.miner import MinerManager

def test_start_stop_fake_miner(tmp_path):
    fake=tmp_path/"xmrig";fake.write_text("#!/bin/sh\necho started\nwhile :; do sleep 1; done\n");fake.chmod(fake.stat().st_mode|stat.S_IXUSR)
    c=Config(wallet="4"*95,xmrig_path=str(fake),threads=1)
    m=MinerManager(c,tmp_path);m.start()
    try:
        assert m.status()["state"]=="running"
        generated=json.loads((tmp_path/"xmrig.generated.json").read_text())
        assert generated["http"]["host"]=="127.0.0.1"
        assert generated["randomx"]["wrmsr"] is False
    finally: m.stop()
    assert m.status()["state"]=="stopped"
