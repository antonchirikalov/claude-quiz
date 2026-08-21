import importlib.util
import json
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).parent.parent


def _load_importer():
    """Load scripts/import_bank.py as a module (scripts/ is not a package)."""
    path = _ROOT / "scripts" / "import_bank.py"
    spec = importlib.util.spec_from_file_location("import_bank", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["import_bank"] = module
    spec.loader.exec_module(module)
    return module


ib = _load_importer()

BANK = """# CCA-X — банк

## Как этим пользоваться

Текст вступления.

# Часть 1 — вопросы

## Scenario 1 · Support Agent

You are building a support agent. Backend access is through MCP tools.

**1.** How should loop termination be controlled?

- A. Check `stop_reason`
- B. Scan the text for "done"
- C. Cap iterations at 10
- D. Stop on the first text block

**2.** Which two reasons justify a multi-agent split? (Select TWO.)

- A. Context isolation
- B. Real parallelism
- C. It looks modern
- D. Duplication adds reliability

# Часть 2 — ключ и разбор

## Сценарий 1 — разбор

**1 · A** · TS 1.1. Единственный корректный признак — `stop_reason`.
- B: разбор текста — анти-паттерн.
- C: лимит итераций — только страховка.
- D: текстовый блок бывает вместе с `tool_use`.

**2 · A, B** · O 1.4. Законные причины — изоляция контекста и параллелизм.
- C: презентабельность не критерий.
- D: дублирование не следует из мультиагентности.

# Часть 3 — подсчёт и диагностика

## Ответы одной строкой

| 1–2 |
|---|
| A AB |

## Результат по доменам

| Домен | Номера вопросов | Всего | Твой результат |
|---|---|---|---|
| 1 · Agentic Architecture | 1 | 1 | |
| 2 · Multi-Agent Design | 2 | 1 | |
"""


@pytest.fixture()
def bank(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "CCA-X_exam_bank.md"
    path.write_text(BANK, encoding="utf-8")
    return path


def _records(bank_path: pathlib.Path, prefix: str = "cca-x"):
    text = bank_path.read_text(encoding="utf-8-sig")
    part1, part2, part3 = ib.split_parts(text)
    records, warnings = ib.build_records(
        ib.parse_questions(part1), ib.parse_keys(part2), ib.parse_domain_map(part3), prefix
    )
    warnings += ib.cross_check(records, ib.parse_answer_tables(part3))
    return records, warnings


def test_parses_both_questions_without_warnings(bank):
    records, warnings = _records(bank)
    assert warnings == []
    assert [r["id"] for r in records] == ["cca-x-01", "cca-x-02"]


def test_single_answer_question_fields(bank):
    record = _records(bank)[0][0]
    assert record["answer"] == "A"
    assert "answers" not in record
    assert record["domain"] == "1 · Agentic Architecture"
    assert record["reference"] == "TS 1.1"
    assert record["stem"].startswith("How should loop termination")
    assert record["choices"]["A"] == "Check `stop_reason`"
    assert len(record["choices"]) == 4


def test_multi_answer_question_fields(bank):
    record = _records(bank)[0][1]
    assert record["answers"] == ["A", "B"]
    assert "answer" not in record
    assert record["domain"] == "2 · Multi-Agent Design"
    assert record["reference"] == "O 1.4"


def test_scenario_text_is_attached_to_every_question_in_the_group(bank):
    records = _records(bank)[0]
    for record in records:
        assert record["scenario_title"] == "Scenario 1 · Support Agent"
        assert record["scenario"] == (
            "You are building a support agent. Backend access is through MCP tools."
        )


def test_explanation_keeps_distractor_bullets(bank):
    record = _records(bank)[0][0]
    lines = record["explanation"].splitlines()
    assert lines[0].startswith("Единственный корректный признак")
    assert lines[1] == "- B: разбор текста — анти-паттерн."
    assert len(lines) == 4


def test_answer_table_mismatch_is_reported(bank, tmp_path: pathlib.Path):
    broken = tmp_path / "broken.md"
    broken.write_text(BANK.replace("| A AB |", "| C AB |"), encoding="utf-8")
    warnings = _records(broken)[1]
    assert any("part 3 table says C" in w for w in warnings)


def test_select_count_mismatch_is_reported(bank, tmp_path: pathlib.Path):
    broken = tmp_path / "broken.md"
    broken.write_text(BANK.replace("(Select TWO.)", "(Select THREE.)"), encoding="utf-8")
    warnings = _records(broken)[1]
    assert any("Select THREE" in w for w in warnings)


def test_question_without_key_is_skipped_with_warning(bank, tmp_path: pathlib.Path):
    broken = tmp_path / "broken.md"
    renumbered = BANK.replace("**2 · A, B** · O 1.4.", "**9 · A, B** · O 1.4.")
    broken.write_text(renumbered, encoding="utf-8")
    records, warnings = _records(broken)
    assert [r["id"] for r in records] == ["cca-x-01"]
    assert any("no answer key" in w for w in warnings)


def test_missing_part_heading_exits(tmp_path: pathlib.Path):
    bad = tmp_path / "bad.md"
    bad.write_text("# Just a title\n\nNo parts here.\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        ib.split_parts(bad.read_text(encoding="utf-8"))


# --- the generated exam files, when present ---

@pytest.mark.parametrize("name", ["cca-f/full-bank-70.json", "cca-p/full-bank-63.json"])
def test_generated_exam_file_loads(name: str):
    path = _ROOT / "exams" / name
    if not path.exists():
        pytest.skip(f"{name} not generated yet — run scripts/import_bank.py")
    from app.quiz import load_questions

    questions = load_questions(path)
    assert questions
    ids = [q.id for q in questions]
    assert len(ids) == len(set(ids))
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert len(raw) == len(questions)


def test_prompt_caching_reference_is_parsed(bank, tmp_path: pathlib.Path):
    """The caching block references guide subsections as 'PC N', not 'TS N.N'."""
    variant = tmp_path / "pc.md"
    variant.write_text(BANK.replace("**1 · A** · TS 1.1.", "**1 · A** · PC 3."), encoding="utf-8")
    record = _records(variant)[0][0]
    assert record["reference"] == "PC 3"


def test_domain_map_ignores_answer_table_header():
    """Only cells carrying a '·' are domain labels — number ranges are not."""
    part3 = "\n".join(
        [
            "| 1–10 | 11–20 |",
            "|---|---|",
            "| A B C D A B C D A B | B C D A B C D A B C |",
            "",
            "| Домен | Номера вопросов | Всего | Твой результат |",
            "|---|---|---|---|",
            "| 1 · Real Domain | 1, 2 | 2 | |",
        ]
    )
    assert ib.parse_domain_map(part3) == {1: "1 · Real Domain", 2: "1 · Real Domain"}
