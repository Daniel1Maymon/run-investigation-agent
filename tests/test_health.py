"""TEST_PLAN.md cases 1–2."""


def test_case1_viewer_reachable(api):
    r = api.get(url="/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["viewer"]["reachable"] is True


def test_case2_viewer_down_is_degraded_not_a_crash(api_viewer_down):
    r = api_viewer_down.get(url="/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["viewer"]["reachable"] is False
    assert "could not be reached" in body["viewer"]["error"]
