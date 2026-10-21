"""TEST_PLAN.md cases 7, 34, 59, 70 and 75. Cases 8–11 and 35 run in the browser and are verified live."""

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

# Case 70

def test_case70_eval_page_and_links(api):
    r = api.get("/eval")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert 'fetch("/eval/cases")' in r.text and 'href="/"' in r.text
    assert 'href="/eval"' in api.get("/").text

# Case 75

def test_case75_eval_page_has_the_pick_steps(api):
    page = api.get("/eval").text
    for part in ('id="case-list"', 'id="grid"', 'id="past"', 'fetch("/eval/results")'):
        assert part in page
