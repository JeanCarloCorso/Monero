from armminer.system_metrics import SystemMetrics
def test_snapshot_has_nullable_real_metrics():
    s=SystemMetrics().snapshot()
    assert s["cpu_count"] >= 1
    assert s["temperature_c"] is None or 0 < s["temperature_c"] < 150
