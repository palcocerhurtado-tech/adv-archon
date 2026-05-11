"""Skill: Code patcher.

Applies targeted patches to source files given a description of the change.
Uses the LLM to generate the patch, then writes it back.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adv_archon.skills.base import Skill, SkillResult
from adv_archon.skills.registry import registry

_SYSTEM = (
    "Eres un experto en ingeniería de software. "
    "Generas parches precisos para archivos de código. "
    "Devuelve SOLO el código completo del archivo modificado, sin explicaciones adicionales."
)


class CodePatcherSkill(Skill):
    name = "code_patcher"
    description = (
        "Aplica un cambio descrito en lenguaje natural a un archivo de código fuente. "
        "Lee el archivo, genera el código modificado con la LLM, y lo escribe."
    )
    args_schema = {
        "file_path": {
            "type": "string",
            "description": "Ruta absoluta al archivo a modificar.",
        },
        "change_description": {
            "type": "string",
            "description": "Descripción del cambio a aplicar en lenguaje natural.",
        },
        "dry_run": {
            "type": "boolean",
            "description": "Si true, muestra el resultado pero no escribe el archivo.",
        },
    }

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    def run(  # type: ignore[override]
        self,
        *,
        file_path: str,
        change_description: str,
        dry_run: bool = False,
        **_: Any,
    ) -> SkillResult:
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            return SkillResult(success=False, output=f"Archivo no encontrado: {path}")
        if not path.is_file():
            return SkillResult(success=False, output=f"No es un archivo: {path}")

        try:
            original = path.read_text(encoding="utf-8")
        except Exception as exc:
            return SkillResult(success=False, output=f"Error al leer el archivo: {exc}")

        if len(original) > 50_000:
            return SkillResult(
                success=False,
                output=f"Archivo demasiado grande ({len(original):,} chars). Límite: 50.000.",
            )

        if self._llm is None:
            return SkillResult(
                success=False,
                output="CodePatcherSkill requiere una LLM configurada.",
            )

        from adv_archon.core.llm_types import LLMMessage

        prompt = (
            f"Archivo: {path.name}\n\n"
            f"Contenido actual:\n```\n{original}\n```\n\n"
            f"Cambio solicitado: {change_description}\n\n"
            "Devuelve el archivo completo con el cambio aplicado. "
            "SOLO el código, sin markdown ni explicaciones."
        )
        resp = self._llm.complete(
            [LLMMessage(role="user", content=prompt)],
            system_prompt=_SYSTEM,
            task="coding",
        )

        patched = resp.text.strip()
        # Strip accidental markdown fences
        if patched.startswith("```"):
            lines = patched.splitlines()
            patched = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        if dry_run:
            preview = patched[:2000] + ("..." if len(patched) > 2000 else "")
            return SkillResult(
                success=True,
                output=f"[DRY RUN] Parche generado para {path.name}:\n\n{preview}",
                artifacts={"patched_content": patched, "dry_run": True},
            )

        backup_path = path.with_suffix(path.suffix + ".bak")
        try:
            backup_path.write_text(original, encoding="utf-8")
            path.write_text(patched, encoding="utf-8")
        except Exception as exc:
            return SkillResult(success=False, output=f"Error al escribir el archivo: {exc}")

        return SkillResult(
            success=True,
            output=(
                f"Parche aplicado a {path.name}.\n"
                f"Backup guardado en: {backup_path.name}"
            ),
            artifacts={"patched_path": str(path), "backup_path": str(backup_path)},
        )


registry.register(CodePatcherSkill())
