from pathlib import Path
import pytest
from armminer.config import Config, load_config, mask_wallet, valid_pool, is_32bit_arm

def test_pool_validation():
    assert valid_pool("pool.example.org:3333")
    assert valid_pool("stratum+tls://pool.example.org:443")
    assert not valid_pool("https://example.org")

def test_mask_wallet(): assert mask_wallet("4"*95)=="444444…444444"
def test_reject_lan_without_opt_in():
    c=Config(dashboard_host="0.0.0.0",lan_access=False)
    assert any("lan_access" in x for x in c.validate())
def test_unknown_config(tmp_path):
    p=tmp_path/"c.toml";p.write_text("[miner]\nwat = 1\n")
    with pytest.raises(ValueError): load_config(p)

def test_32bit_arm_detection(monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: "armv8l")
    assert is_32bit_arm()
    assert any("light" in x for x in Config(randomx_mode="auto").validate())
