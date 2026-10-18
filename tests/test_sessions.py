"""TEST_PLAN.md case 13."""

def test_case13_sessions_listed(api):
    r = api.get("/sessions")
    assert r.status_code == 200
    assert [s["session_id"] for s in r.json()] == ["s1", "s2"]

def test_case13_viewer_down_is_503(api_viewer_down):
    r = api_viewer_down.get("/sessions")
    assert r.status_code == 503
    assert "dash" in r.json()["detail"]
