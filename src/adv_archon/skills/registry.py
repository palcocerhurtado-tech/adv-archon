"""Skill registry — discovers and exposes skills as ToolSpecs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from adv_archon.skills.base import Skill, SkillResult

if TYPE_CHECKING:
    from adv_archon.core.agent import ToolSpec


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def to_tool_specs(self) -> list[ToolSpec]:
        from adv_archon.core.agent import ToolSpec

        specs = []
        for skill in self._skills.values():
            # Capture skill in closure
            def _make_fn(s: Skill) -> Any:
                def _fn(**kwargs: Any) -> str:
                    result: SkillResult = s.run(**kwargs)
                    return result.output if result.success else f"[Skill error] {result.output}"
                return _fn

            specs.append(
                ToolSpec(
                    name=f"skill_{skill.name}",
                    description=skill.description,
                    schema={
                        "type": "object",
                        "properties": skill.args_schema,
                        "required": list(skill.args_schema.keys()),
                    },
                    fn=_make_fn(skill),
                )
            )
        return specs


# Global registry — import this and call register() in each skill module
registry = SkillRegistry()
