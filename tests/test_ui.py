"""TEST_PLAN.md cases 7, 34 and 59. Cases 8–11 and 35 run in the browser and are verified live."""

def test_case7_root_serves_the_page(api):
    r = api.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert 'id="run-id"' in r.text
    assert 'id="check"' in r.text
    assert 'id="sessions"' in r.text  # case 15: the session list…
    assert 'id="sessions-toggle"' in r.text  # …behind a button
    assert '"/investigate", { method: "POST" }' in r.text  # case 34: the page can start an investigation
    assert 'fetch("/sessions/version")' in r.text  # case 59: the list checks for new sessions
