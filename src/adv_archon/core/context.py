from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

IGNORED_DIRS = {".git", ".venv", "node_modules", "__pycache__"}
PROJECT_MARKERS = (
    "README.md",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "requirements.txt",
    "Makefile",
)
WEEKDAY_NAMES = (
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
)


@dataclass(slots=True)
class GitContext:
    repo_root: Path | None
    branch: str | None
    dirty: bool
    changed_files: int
    changed_paths: list[str]

    def summary(self) -> str:
        if self.repo_root is None:
            return "sin repo git"
        state = "sucio" if self.dirty else "limpio"
        details = f"{self.branch or 'detached'}, {state}"
        if self.changed_files:
            details += f", {self.changed_files} cambios"
        return details


@dataclass(slots=True)
class WorkingSet:
    project_root: Path
    project_name: str
    markers: list[str]
    top_entries: list[str]

    def summary(self) -> str:
        markers = ", ".join(self.markers) if self.markers else "sin marcadores claros"
        entries = ", ".join(self.top_entries) if self.top_entries else "sin entradas relevantes"
        return f"{self.project_name} | marcadores: {markers} | entradas: {entries}"


@dataclass(slots=True)
class RuntimeContext:
    cwd: Path
    now: datetime
    git: GitContext
    working_set: WorkingSet
    active_profile: str = "general"

    def greeting(self) -> str:
        time_of_day = _time_of_day(self.now.hour)
        weekday = WEEKDAY_NAMES[self.now.weekday()]
        git_info = f" (git: {self.git.summary()})" if self.git.repo_root else ""
        return (
            f"{time_of_day}, Pablo. {weekday}, {self.now:%H:%M}.\n"
            f"Estas en {self.cwd}{git_info}.\n"
            "¿En qué te ayudo?"
        )

    def prompt_block(self) -> str:
        lines = [
            "Runtime context:",
            f"- Local time: {WEEKDAY_NAMES[self.now.weekday()]}, {self.now:%H:%M}",
            f"- Current directory: {self.cwd}",
            f"- Active profile: {self.active_profile}",
            f"- Git: {self.git.summary()}",
            f"- Working set: {self.working_set.summary()}",
        ]
        return "\n".join(lines)


def capture_runtime_context(
    cwd: Path | None = None,
    *,
    active_profile: str = "general",
) -> RuntimeContext:
    resolved_cwd = (cwd or Path.cwd()).resolve()
    git = _capture_git_context(resolved_cwd)
    project_root = git.repo_root or _find_project_root(resolved_cwd) or resolved_cwd
    working_set = _capture_working_set(project_root)
    return RuntimeContext(
        cwd=resolved_cwd,
        now=datetime.now(),
        git=git,
        working_set=working_set,
        active_profile=active_profile,
    )


def _capture_git_context(cwd: Path) -> GitContext:
    repo_root_text = _run_git(cwd, "rev-parse", "--show-toplevel")
    if repo_root_text is None:
        return GitContext(
            repo_root=None,
            branch=None,
            dirty=False,
            changed_files=0,
            changed_paths=[],
        )
    repo_root = Path(repo_root_text).resolve()
    branch_text = _run_git(cwd, "branch", "--show-current")
    status_text = _run_git(cwd, "status", "--porcelain")
    changed_files = 0
    changed_paths: list[str] = []
    if status_text:
        status_lines = [line for line in status_text.splitlines() if line.strip()]
        changed_files = len(status_lines)
        for line in status_lines[:10]:
            changed_paths.append(line[3:])
    return GitContext(
        repo_root=repo_root,
        branch=(branch_text or "") or None,
        dirty=changed_files > 0,
        changed_files=changed_files,
        changed_paths=changed_paths,
    )


def _run_git(cwd: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.rstrip("\r\n")


def _find_project_root(cwd: Path) -> Path | None:
    for candidate in (cwd, *cwd.parents):
        if any((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate
    return None


def _capture_working_set(project_root: Path) -> WorkingSet:
    markers = [marker for marker in PROJECT_MARKERS if (project_root / marker).exists()]
    top_entries = []
    children = sorted(
        project_root.iterdir(),
        key=lambda item: (not item.is_dir(), item.name.lower()),
    )
    for child in children:
        if child.name in IGNORED_DIRS:
            continue
        suffix = "/" if child.is_dir() else ""
        top_entries.append(f"{child.name}{suffix}")
        if len(top_entries) >= 8:
            break
    project_name = _infer_project_name(project_root)
    return WorkingSet(
        project_root=project_root,
        project_name=project_name,
        markers=markers,
        top_entries=top_entries,
    )


def _infer_project_name(project_root: Path) -> str:
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            with pyproject.open("rb") as handle:
                data = tomllib.load(handle)
        except tomllib.TOMLDecodeError:
            data = {}
        project = data.get("project", {})
        if isinstance(project, dict):
            name = project.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()

    package_json = project_root / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        name = payload.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()

    return project_root.name


def _time_of_day(hour: int) -> str:
    if hour < 6:
        return "Buenas noches"
    if hour < 12:
        return "Buenos dias"
    if hour < 20:
        return "Buenas tardes"
    return "Buenas noches"
