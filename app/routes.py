from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.errors import QuizError
from app.quiz import get_question, next_unanswered, record_answer, score_session

bp = Blueprint("quiz", __name__)


def _questions():
    return current_app.config["QUESTIONS"]


@bp.get("/")
def index():
    if request.args.get("restart"):
        session.clear()
    return render_template("index.html", questions=_questions())


@bp.get("/question/<qid>")
def question(qid: str):
    try:
        q = get_question(qid, _questions())
    except QuizError:
        flash("Question not found.", "error")
        return redirect(url_for("quiz.index"))
    answered = session.get("answers", {})
    return render_template("question.html", question=q, answered=answered)


@bp.post("/question/<qid>")
def submit_answer(qid: str):
    try:
        q = get_question(qid, _questions())
    except QuizError:
        flash("Question not found.", "error")
        return redirect(url_for("quiz.index"))
    choice = request.form.get("choice", "").strip()
    if choice not in q.choices:
        flash("Please select a valid answer.", "warning")
        return redirect(url_for("quiz.question", qid=qid))
    record_answer(session, qid, choice)
    return redirect(url_for("quiz.answer", qid=qid))


@bp.get("/answer/<qid>")
def answer(qid: str):
    try:
        q = get_question(qid, _questions())
    except QuizError:
        flash("Question not found.", "error")
        return redirect(url_for("quiz.index"))
    chosen = session.get("answers", {}).get(qid)
    if chosen is None:
        return redirect(url_for("quiz.question", qid=qid))
    nxt = next_unanswered(session, _questions())
    return render_template("answer.html", question=q, chosen=chosen, next_question=nxt)


@bp.get("/results")
def results():
    if not session.get("answers"):
        return redirect(url_for("quiz.index"))
    score = score_session(session, _questions())
    return render_template("results.html", score=score)
