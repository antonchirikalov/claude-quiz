def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Claude" in resp.data


def test_index_lists_domains_and_multi_count(client):
    resp = client.get("/")
    body = resp.data.decode()
    assert "Multi Domain" in body
    assert "multiple-response" in body


def test_index_restart_clears_session(client):
    with client.session_transaction() as sess:
        sess["answers"] = {"test-q-001": ["A"]}
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


def test_question_shows_scenario_when_present(client):
    body = client.get("/question/test-q-002").data.decode()
    assert "European capitals" in body
    assert "Scenario 1 · Geography" in body


def test_question_without_scenario_has_no_scenario_block(client):
    resp = client.get("/question/test-q-001")
    assert b"European capitals" not in resp.data


def test_scenario_is_expanded_on_its_first_question(client):
    body = client.get("/question/test-q-002").data.decode()
    assert '<details class="scenario" open>' in body


def test_scenario_is_collapsed_on_later_questions_of_the_block(client):
    body = client.get("/question/test-q-004").data.decode()
    assert '<details class="scenario" open>' not in body
    assert '<details class="scenario"' in body
    assert "European capitals" in body


def test_scenario_is_collapsed_on_the_answer_page(client):
    client.post("/question/test-q-002", data={"choice": "C"})
    body = client.get("/answer/test-q-002").data.decode()
    assert '<details class="scenario">' in body


def test_question_number_is_position_not_answer_count(client):
    client.post("/question/test-q-003", data={"choice": ["B", "D"]})
    resp = client.get("/question/test-q-001")
    assert b"Question 1 of 4" in resp.data


def test_submit_answer_valid_redirects_to_answer(client):
    resp = client.post("/question/test-q-001", data={"choice": "B"})
    assert resp.status_code == 302
    assert "answer" in resp.headers["Location"]


def test_submit_answer_invalid_choice_redirects_to_question(client):
    resp = client.post("/question/test-q-001", data={"choice": "Z"})
    assert resp.status_code == 302
    assert "question" in resp.headers["Location"]


def test_submit_answer_empty_choice_redirects_to_question(client):
    resp = client.post("/question/test-q-001", data={})
    assert resp.status_code == 302
    assert "question" in resp.headers["Location"]


def test_submit_extra_choices_on_single_answer_question_rejected(client):
    resp = client.post("/question/test-q-001", data={"choice": ["A", "B"]})
    assert resp.status_code == 302
    assert "question" in resp.headers["Location"]
    with client.session_transaction() as sess:
        assert "test-q-001" not in (sess.get("answers") or {})


def test_answer_page_renders_after_answering(client):
    client.post("/question/test-q-001", data={"choice": "B"})
    resp = client.get("/answer/test-q-001")
    assert resp.status_code == 200
    assert b"Why B is correct" in resp.data


def test_answer_page_shows_reference(client):
    client.post("/question/test-q-002", data={"choice": "C"})
    resp = client.get("/answer/test-q-002")
    assert b"TS 9.9" in resp.data


def test_answer_unanswered_redirects_to_question(client):
    resp = client.get("/answer/test-q-001")
    assert resp.status_code == 302
    assert "question" in resp.headers["Location"]


# --- multiple response ---

def test_multi_question_renders_checkboxes_and_hint(client):
    resp = client.get("/question/test-q-003")
    body = resp.data.decode()
    assert 'type="checkbox"' in body
    assert "select exactly 2" in body


def test_multi_submit_exact_match_is_correct(client):
    resp = client.post("/question/test-q-003", data={"choice": ["B", "D"]})
    assert resp.status_code == 302
    resp = client.get("/answer/test-q-003")
    assert b"Correct! Well done." in resp.data


def test_multi_submit_partial_selection_rejected(client):
    resp = client.post("/question/test-q-003", data={"choice": ["B"]}, follow_redirects=True)
    assert b"requires exactly 2 selections" in resp.data
    with client.session_transaction() as sess:
        assert "test-q-003" not in (sess.get("answers") or {})


def test_multi_submit_wrong_pair_is_incorrect(client):
    client.post("/question/test-q-003", data={"choice": ["A", "B"]})
    resp = client.get("/answer/test-q-003")
    assert b"Incorrect" in resp.data
    assert b"B, D" in resp.data


# --- results ---

def test_results_no_session_redirects(client):
    resp = client.get("/results")
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_results_after_answering_returns_200(client):
    client.post("/question/test-q-001", data={"choice": "B"})
    resp = client.get("/results")
    assert resp.status_code == 200
    assert b"Quiz Complete" in resp.data


def test_results_shows_domain_breakdown(client):
    client.post("/question/test-q-001", data={"choice": "B"})
    client.post("/question/test-q-003", data={"choice": ["B", "D"]})
    body = client.get("/results").data.decode()
    assert "Score by Domain" in body
    assert "Multi Domain" in body


def test_live_score_counts_multi_correctly(client):
    client.post("/question/test-q-003", data={"choice": ["B", "D"]})
    body = client.get("/question/test-q-001").data.decode()
    assert "1 / 1" in body


# --- question navigator ---

def test_question_page_renders_navigator(client):
    body = client.get("/question/test-q-001").data.decode()
    assert 'class="qnav"' in body
    assert 'class="qnav-cell state-unanswered' in body
    assert "qnav-current" in body


def test_navigator_links_answered_questions_to_the_answer_page(client):
    client.post("/question/test-q-001", data={"choice": "B"})
    body = client.get("/question/test-q-002").data.decode()
    assert '/answer/test-q-001"' in body
    assert 'state-correct' in body


def test_navigator_marks_a_wrong_answer(client):
    client.post("/question/test-q-001", data={"choice": "A"})
    body = client.get("/question/test-q-002").data.decode()
    assert "state-wrong" in body


def test_navigator_groups_by_scenario(client):
    body = client.get("/question/test-q-002").data.decode()
    assert "Scenario 1</span>" in body


def test_step_links_disabled_at_the_ends(client):
    first = client.get("/question/test-q-001").data.decode()
    assert "qnav-step-off" in first  # no previous
    last = client.get("/question/test-q-003").data.decode()
    assert "qnav-step-off" in last  # no next


def test_step_links_move_by_position(client):
    body = client.get("/question/test-q-002").data.decode()
    assert "/question/test-q-001" in body
    assert "/question/test-q-004" in body


def test_answer_page_renders_navigator(client):
    client.post("/question/test-q-001", data={"choice": "B"})
    body = client.get("/answer/test-q-001").data.decode()
    assert 'class="qnav"' in body
    assert "qnav-current" in body


def test_navigator_marks_multi_response_questions(client):
    body = client.get("/question/test-q-001").data.decode()
    assert "qnav-multi" in body


# --- structured explanation and sources ---

def test_answer_page_splits_lead_from_distractor_points(client):
    client.post("/question/test-q-003", data={"choice": ["B", "D"]})
    body = client.get("/answer/test-q-003").data.decode()
    assert "Why B, D is correct" in body
    assert "Why the other options fail" in body
    assert "2 and 4 are even." in body
    assert "<li>A: odd.</li>" in body


def test_answer_page_lists_sources_with_quote(client):
    client.post("/question/test-q-002", data={"choice": "C"})
    body = client.get("/answer/test-q-002").data.decode()
    assert "Read it in the docs" in body
    assert 'href="https://docs.claude.com/en/docs/test-page"' in body
    assert 'rel="noopener noreferrer"' in body
    assert "Paris is the capital" in body
    assert "read 2026-08-14" in body


def test_answer_page_without_sources_has_no_docs_block(client):
    client.post("/question/test-q-001", data={"choice": "B"})
    body = client.get("/answer/test-q-001").data.decode()
    assert "Read it in the docs" not in body
