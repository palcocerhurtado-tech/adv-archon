"""Skill: README generator.

Generates a README.md for a local project directory using the LLM.
"""

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import Any

from adv_archon.skills.base import Skill, SkillResult
from adv_archon.skills.registry import registry


class ReadmeGeneratorSkill(Skill):
    name = "readme_generator"
    description = (
        "Genera un README.md profesional para un directorio de proyecto local. "
        "Inspecciona los archivos del proyecto y produce documentación clara."
    )
    args_schema = {
        "project_path": {
            "type": "string",
            "description": "Ruta absoluta al directorio del proyecto.",
        },
        "language": {
            "type": "string",
            "description": "Idioma del README: 'es' (español) o 'en' (inglés). Por defecto 'es'.",
        },
    }

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    def _scan_project(self, path: Path) -> str:
        """Return a compact project snapshot for the LLM."""
        lines: list[str] = []
        ignore = {".git", "__pycache__", ".ruff_cache", "node_modules", ".venv", "venv"}
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in ignore]
            rel = Path(root).relative_to(path)
            depth = len(rel.parts)
            if depth > 3:
                continue
            indent = "  " * depth
            lines.append(f"{indent}{rel}/")
            for f in sorted(files)[:20]:
                lines.append(f"{indent}  {f}")
        return "\n".join(lines[:100])

    def run(self, *, project_path: str, language: str = "es", **_: Any) -> SkillResult:
        path = Path(project_path).expanduser().resolve()
        if not path.is_dir():
            return SkillResult(success=False, output=f"Directorio no encontrado: {path}")

        tree = self._scan_project(path)
        lang_instr = "in Spanish" if language == "es" else "in English"

        # Try to read pyproject.toml or package.json for extra context
        extra = ""
        for meta_file in ("pyproject.toml", "package.json", "Cargo.toml"):
            meta_path = path / meta_file
            if meta_path.exists():
                with suppress(Exception):
                    extra = meta_path.read_text(encoding="utf-8")[:1500]
                break

        if self._llm is None:
            # Fallback: template-based README
            readme = _template_readme(path.name, tree, language)
        else:
            from adv_archon.core.llm_types import LLMMessage

            metadata = f"Metadata:\n{extra}" if extra else ""
            prompt = (
                f"Generate a professional README.md {lang_instr} for this project.\n\n"
                f"Project name: {path.name}\n\n"
                f"Directory tree:\n{tree}\n\n"
                f"{metadata}\n\n"
                "Include: description, installation, usage, and structure sections."
            )
            response = self._llm.complete(
                [LLMMessage(role="user", content=prompt)],
                system_prompt="You are a technical writer. Generate concise, accurate READMEs.",
                task="documents",
            )
            readme = response.text

        # Write the file
        readme_path = path / "README.md"
        try:
            readme_path.write_text(readme, encoding="utf-8")
        except Exception as exc:
            return SkillResult(success=False, output=f"No se pudo escribir README.md: {exc}")

        return SkillResult(
            success=True,
            output=f"README.md generado en {readme_path}",
            artifacts={"path": str(readme_path), "content": readme},
        )


def _template_readme(name: str, tree: str, language: str) -> str:
    if language == "es":
        return (
            f"# {name}\n\n"
            "## Descripción\n\n"
            f"Proyecto `{name}`.\n\n"
            "## Instalación\n\n"
            "```bash\n# Instala las dependencias\npip install -e .\n```\n\n"
            "## Uso\n\n"
            "```bash\n# Ejecuta el proyecto\npython -m " + name.replace("-", "_") + "\n```\n\n"
            "## Estructura\n\n"
            f"```\n{tree}\n```\n"
        )
    return (
        f"# {name}\n\n"
        "## Description\n\n"
        f"Project `{name}`.\n\n"
        "## Installation\n\n"
        "```bash\npip install -e .\n```\n\n"
        "## Usage\n\n"
        "```bash\npython -m " + name.replace("-", "_") + "\n```\n\n"
        "## Structure\n\n"
        f"```\n{tree}\n```\n"
    )


registry.register(ReadmeGeneratorSkill())
