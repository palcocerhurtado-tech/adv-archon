from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ProfileDefinition:
    name: str
    description: str
    system_hint: str
    knowledge_roots: tuple[str, ...] = ()
    vault_roots: tuple[str, ...] = ()


DEFAULT_PROFILE_DEFINITIONS = {
    "general": ProfileDefinition(
        name="general",
        description="Perfil equilibrado para uso diario y peticiones mixtas.",
        system_hint="Keep responses balanced and broadly useful.",
    ),
    "work": ProfileDefinition(
        name="work",
        description="Orientado a clientes, propuestas, repos y operativa profesional.",
        system_hint="Prioritize client work, deliverables, proposals, and execution clarity.",
    ),
    "personal": ProfileDefinition(
        name="personal",
        description="Enfocado en vida personal, notas, recordatorios y organización privada.",
        system_hint="Prioritize personal organization, life admin, and private notes.",
    ),
    "research": ProfileDefinition(
        name="research",
        description="Enfocado en exploración, síntesis y análisis comparativo.",
        system_hint=(
            "Prioritize exploration, synthesis, source comparison, "
            "and structured findings."
        ),
    ),
    "urbanismo": ProfileDefinition(
        name="urbanismo",
        description="Revisión urbanística española, PGOU, afecciones y viabilidad.",
        system_hint=(
            "Prioriza cumplimiento urbanístico español, PGOU municipal, Catastro, "
            "afecciones sectoriales, trazabilidad oficial y advertencias jurídicas prudentes."
        ),
    ),
    "arquitectura": ProfileDefinition(
        name="arquitectura",
        description="Expedientes de arquitectura, memoria, planos, mediciones e informes.",
        system_hint=(
            "Prioriza entregables de despacho: memoria, mediciones, presupuesto, "
            "análisis de planos, coordinación técnica y claridad para cliente final."
        ),
    ),
    "legal": ProfileDefinition(
        name="legal",
        description="Lectura jurídico-técnica prudente con fuentes y límites explícitos.",
        system_hint=(
            "Prioriza precisión legal, separación entre dato oficial e inferencia, "
            "citas verificables, cautelas y asuntos pendientes de validación técnica."
        ),
    ),
    "coding": ProfileDefinition(
        name="coding",
        description="Enfocado en repos, código, debugging y cambios verificables.",
        system_hint="Prioritize code understanding, verification, and implementation details.",
    ),
}


class ProfileManager:
    def __init__(
        self,
        state_file: Path,
        *,
        default_profile: str = "general",
        definitions: dict[str, ProfileDefinition] | None = None,
    ) -> None:
        merged = {name: definition for name, definition in DEFAULT_PROFILE_DEFINITIONS.items()}
        if definitions:
            merged.update(definitions)
        self._definitions = merged
        self._state_file = state_file
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._default_profile = (
            default_profile if default_profile in self._definitions else "general"
        )
        self._active_profile = self._load_active_profile()

    @property
    def active_profile(self) -> str:
        return self._active_profile

    def available_profiles(self) -> list[str]:
        return sorted(self._definitions)

    def describe(self, profile_name: str | None = None) -> ProfileDefinition:
        return self._definitions[self.resolve(profile_name)]

    def knowledge_roots(self, profile_name: str | None = None) -> tuple[str, ...]:
        return self.describe(profile_name).knowledge_roots

    def vault_roots(self, profile_name: str | None = None) -> tuple[str, ...]:
        return self.describe(profile_name).vault_roots

    def system_hint(self, profile_name: str | None = None) -> str:
        return self.describe(profile_name).system_hint

    def set_active_profile(self, profile_name: str) -> str:
        resolved = self.resolve(profile_name)
        self._active_profile = resolved
        self._state_file.write_text(resolved, encoding="utf-8")
        return resolved

    def resolve(self, profile_name: str | None) -> str:
        candidate = (profile_name or self._active_profile or self._default_profile).strip()
        if candidate in self._definitions:
            return candidate
        raise ValueError(
            "Perfil desconocido. Perfiles disponibles: "
            + ", ".join(self.available_profiles())
        )

    def _load_active_profile(self) -> str:
        if self._state_file.exists():
            stored = self._state_file.read_text(encoding="utf-8").strip()
            if stored in self._definitions:
                return stored
        return self._default_profile
