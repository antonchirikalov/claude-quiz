from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.errors import QuizError
from app.quiz import (
    domain_counts,
    get_answers,
    get_question,
    list_exams,
    list_question_files,
    load_questions,
    nav_groups,
    neighbours,
    next_unanswered,
    questions_path,
    record_answer,
    score_session,
)

bp = Blueprint("quiz", __name__)


def _opens_scenario(question, questions: list) -> bool:
    """True on the first question of a scenario block.

    The scenario is shared context for a whole block of questions, so it only
    needs reading once — later questions in the block get it collapsed.
    """
    if not question.scenario:
        return False
    index = questions.index(question)
    return index == 0 or questions[index - 1].scenario != question.scenario


def _questions() -> list:
    """Return the active question list.

    Tests inject QUESTIONS directly into app.config — use that when present.
    In production, load from the exam/file stored in the session.
    """
    if "QUESTIONS" in current_app.config:
        return current_app.config["QUESTIONS"]
    if not hasattr(g, "questions"):
        exam = session.get("exam")
        file = session.get("file")
        if not exam or not file:
            g.questions = []
        else:
            try:
                g.questions = load_questions(questions_path(exam, file))
            except Exception:
                g.questions = []
    return g.questions


@bp.app_context_processor
def inject_live_stats() -> dict:
    answers = get_answers(session)
    questions = _questions()
    correct = sum(1 for q in questions if q.is_correct(answers.get(q.id)))
    answered = sum(1 for q in questions if q.id in answers)
    quiz_active = (
        "QUESTIONS" in current_app.config
        or bool(session.get("exam") and session.get("file"))
    )
    return {
        "live_stats": {"correct": correct, "answered": answered},
        "quiz_active": quiz_active,
    }


@bp.get("/")
def index():
    if request.args.get("restart"):
        session.clear()
        return redirect(url_for("quiz.index"))

    questions = _questions()

    # Test mode: QUESTIONS injected directly into config → go straight to quiz UI
    # Production path is the same view once an exam + file have been chosen.
    if "QUESTIONS" in current_app.config or (session.get("exam") and session.get("file")):
        return render_template(
            "index.html",
            mode="quiz",
            questions=questions,
            domains=domain_counts(questions),
            multi_count=sum(1 for q in questions if q.is_multi),
            exam=session.get("exam"),
            file=session.get("file"),
            answered=get_answers(session),
        )

    # Step 2: exam chosen via query param → show file list
    exam = request.args.get("exam", "").strip()
    if exam:
        if exam not in list_exams():
            flash("Unknown exam.", "error")
            return redirect(url_for("quiz.index"))
        files = list_question_files(exam)
        return render_template("index.html", mode="select_file", exam=exam, files=files)

    # Step 1: pick an exam
    exams = list_exams()
    return render_template("index.html", mode="select_exam", exams=exams)


@bp.post("/select")
def select():
    exam = request.form.get("exam", "").strip()
    filename = request.form.get("file", "").strip()
    if exam not in list_exams():
        flash("Invalid exam selection.", "error")
        return redirect(url_for("quiz.index"))
    if filename not in list_question_files(exam):
        flash("Invalid file selection.", "error")
        return redirect(url_for("quiz.index", exam=exam))
    session.clear()
    session["exam"] = exam
    session["file"] = filename
    return redirect(url_for("quiz.index"))


@bp.get("/question/<qid>")
def question(qid: str):
    questions = _questions()
    try:
        q = get_question(qid, questions)
    except QuizError:
        flash("Question not found.", "error")
        return redirect(url_for("quiz.index"))
    answered = get_answers(session)
    total = len(questions)
    remaining = total - sum(1 for item in questions if item.id in answered)
    previous_question, next_in_order = neighbours(questions, q)
    return render_template(
        "question.html",
        question=q,
        answered=answered,
        q_number=questions.index(q) + 1,
        total=total,
        remaining=remaining,
        opens_scenario=_opens_scenario(q, questions),
        nav=nav_groups(questions, answered, current_id=q.id),
        previous_question=previous_question,
        next_in_order=next_in_order,
    )


@bp.post("/question/<qid>")
def submit_answer(qid: str):
    try:
        q = get_question(qid, _questions())
    except QuizError:
        flash("Question not found.", "error")
        return redirect(url_for("quiz.index"))
    chosen = [c.strip() for c in request.form.getlist("choice") if c.strip()]
    if not chosen or any(c not in q.choices for c in chosen):
        flash("Please select a valid answer.", "warning")
        return redirect(url_for("quiz.question", qid=qid))
    expected = len(q.answers)
    if len(set(chosen)) != expected:
        flash(
            f"This question requires exactly {expected} selections — you made {len(set(chosen))}.",
            "warning",
        )
        return redirect(url_for("quiz.question", qid=qid))
    record_answer(session, qid, sorted(set(chosen)))
    return redirect(url_for("quiz.answer", qid=qid))


@bp.get("/answer/<qid>")
def answer(qid: str):
    questions = _questions()
    try:
        q = get_question(qid, questions)
    except QuizError:
        flash("Question not found.", "error")
        return redirect(url_for("quiz.index"))
    answered = get_answers(session)
    chosen = answered.get(qid)
    if chosen is None:
        return redirect(url_for("quiz.question", qid=qid))
    nxt = next_unanswered(session, questions)
    total = len(questions)
    remaining = total - sum(1 for item in questions if item.id in answered)
    previous_question, next_in_order = neighbours(questions, q)
    return render_template(
        "answer.html",
        question=q,
        answered=answered,
        chosen=chosen,
        next_question=nxt,
        q_number=questions.index(q) + 1,
        total=total,
        remaining=remaining,
        nav=nav_groups(questions, answered, current_id=q.id),
        previous_question=previous_question,
        next_in_order=next_in_order,
    )


@bp.get("/results")
def results():
    if not session.get("answers"):
        return redirect(url_for("quiz.index"))
    score = score_session(session, _questions())
    return render_template("results.html", score=score)
