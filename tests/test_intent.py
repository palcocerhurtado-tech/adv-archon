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
