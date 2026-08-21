import importlib.util
import json
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).parent.parent


def _load_builder():
    """Load scripts/build_simulations.py as a module (scripts/ is not a package)."""
    path = _ROOT / "scripts" / "build_simulations.py"
    spec = importlib.util.spec_from_file_location("build_simulations", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_simulations"] = module
    spec.loader.exec_module(module)
    return module


bs = _load_builder()


def test_scenario_number_parsed_from_title():
    assert bs.scenario_number({"scenario_title": "Scenario 3 · Multi-Agent Research"}) == 3


def test_scenario_number_none_without_title():
    assert bs.scenario_number({}) is None
    assert bs.scenario_number({"scenario_title": "Дополнительно · Prompt caching"}) is None


def test_every_simulation_draws_four_scenarios():
    for name, scenarios in bs.SIMULATIONS.items():
        assert len(scenarios) == 4, name
        assert len(set(scenarios)) == 4, name
        assert set(scenarios) <= {1, 2, 3, 4, 5, 6}, name


@pytest.mark.parametrize("name", sorted(bs.SIMULATIONS))
def test_generated_simulation_loads_and_covers_all_domains(name: str):
    path = _ROOT / "exams" / "cca-f" / f"exam-sim-{name}.json"
    if not path.exists():
        pytest.skip(f"{path.name} not generated yet — run scripts/build_simulations.py")
    from app.quiz import load_questions

    questions = load_questions(path)
    assert len(questions) == 40
    assert len({q.id for q in questions}) == 40
    # A 4-of-6 draw can miss a scored domain; the chosen combinations must not.
    domains = {q.domain.split(" · ")[0] for q in questions}
    assert domains == {"1", "2", "3", "4", "5"}
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert len(raw) == len(questions)
