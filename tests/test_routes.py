def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Claude" in resp.data


def test_index_restart_clears_session(client):
    with client.session_transaction() as sess:
        sess["answers"] = {"test-q-001": "A"}
    resp = client.get("/?restart=1", follow_redirects=True)
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("answers") is None or sess.get("answers") == {}


def test_question_valid_id_returns_200(client):
    resp = client.get("/question/test-q-001")
    assert resp.status_code == 200
    assert b"2 + 2" in resp.data


def test_question_invalid_id_redirects(client):
    resp = client.get("/question/nonexistent-id")
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_submit_answer_valid_redirects_to_answer(client):
    resp = client.post("/question/test-q-001", data={"choice": "B"})
    assert resp.status_code == 302
    assert "answer" in resp.headers["Location"]


def test_submit_answer_invalid_choice_redirects_to_question(client):
    resp = client.post("/question/test-q-001", data={"choice": "Z"})
    assert resp.status_code == 302
    assert "question" in resp.headers["Location"]


def test_answer_page_renders_after_answering(client):
    client.post("/question/test-q-001", data={"choice": "B"})
    resp = client.get("/answer/test-q-001")
    assert resp.status_code == 200
    assert b"Explanation" in resp.data


def test_answer_unanswered_redirects_to_question(client):
    resp = client.get("/answer/test-q-001")
    assert resp.status_code == 302
    assert "question" in resp.headers["Location"]


def test_results_no_session_redirects(client):
    resp = client.get("/results")
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_results_after_answering_returns_200(client):
    client.post("/question/test-q-001", data={"choice": "B"})
    resp = client.get("/results")
    assert resp.status_code == 200
    assert b"Quiz Complete" in resp.data
