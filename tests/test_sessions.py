"""TEST_PLAN.md cases 13 and 58."""

def test_case13_sessions_listed(api):
    r = api.get(url="/sessions")
    assert r.status_code == 200
    assert [s["session_id"] for s in r.json()] == ["s1", "s2"]

def test_case13_viewer_down_is_503(api_viewer_down):
    r = api_viewer_down.get(url="/sessions")
    assert r.status_code == 503
    assert "dash" in r.json()["detail"]

def test_case58_version_returned(api):
    r = api.get(url="/sessions/version")
    assert r.status_code == 200
    assert r.json() == {"v": 0}

def test_case58_viewer_down_is_503(api_viewer_down):
    r = api_viewer_down.get(url="/sessions/version")
    assert r.status_code == 503
    assert "dash" in r.json()["detail"]
