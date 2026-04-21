from pathlib import Path

from adv_archon.core.context import GitContext, RuntimeContext, WorkingSet
from adv_archon.core.intent import IntentRouter


def test_intent_router_detects_coding_repo_context() -> None:
    router = IntentRouter()
    context = RuntimeContext(
        cwd=Path("/tmp/demo"),
        now=__import__("datetime").datetime(2026, 4, 21, 12, 0),
        git=GitContext(
            repo_root=Path("/tmp/demo"),
            branch="main",
            dirty=True,
            changed_files=3,
            changed_paths=["src/app.py"],
        ),
        working_set=WorkingSet(
            project_root=Path("/tmp/demo"),
            project_name="demo",
            markers=["pyproject.toml"],
            top_entries=["src/", "README.md"],
        ),
    )

    analysis = router.analyze("revisa este bug en Python y propon un refactor", context)

    assert analysis.category == "coding"
    assert analysis.profile == "coding"
    assert analysis.needs_plan is True
    assert analysis.needs_shell is True


def test_intent_router_detects_document_query() -> None:
    router = IntentRouter()

    analysis = router.analyze("resume ~/Desktop/propuesta.pdf y dime si el scope esta bien")

    assert analysis.category == "documents"
    assert analysis.needs_knowledge is True


def test_intent_router_detects_browser_automation_query() -> None:
    router = IntentRouter()

    analysis = router.analyze("abre esta pagina, rellena el formulario y saca una captura")

    assert analysis.needs_plan is True
    assert "keywords de navegador/automatizacion" in analysis.reasons


def test_intent_router_does_not_force_knowledge_for_calendar_tasks_query() -> None:
    router = IntentRouter()

    analysis = router.analyze(
        "que tengo esta semana en el calendario y qué tareas pendientes tengo"
    )

    assert analysis.category == "assistant"
    assert analysis.needs_knowledge is False


def test_intent_router_inherits_active_profile_when_relevant() -> None:
    router = IntentRouter()
    context = RuntimeContext(
        cwd=Path("/tmp/home"),
        now=__import__("datetime").datetime(2026, 4, 21, 9, 0),
        git=GitContext(
            repo_root=None,
            branch=None,
            dirty=False,
            changed_files=0,
            changed_paths=[],
        ),
        working_set=WorkingSet(
            project_root=Path("/tmp/home"),
            project_name="home",
            markers=[],
            top_entries=[],
        ),
        active_profile="work",
    )

    analysis = router.analyze("organiza mis prioridades para hoy", context)

    assert analysis.category == "assistant"
    assert analysis.profile == "work"
