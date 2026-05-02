from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from adv_archon.tools.files import ToolResult, find_local, list_dir, read_file


@dataclass(frozen=True, slots=True)
class FileAccessPolicy:
    allowed_roots: tuple[Path, ...]
    sensitive_roots: tuple[Path, ...]
    allow_sensitive_reads: bool = False

    def validate_path(self, path: str) -> Path:
        target = Path(path).expanduser().resolve()
        if self._is_sensitive(target) and not self.allow_sensitive_reads:
            raise PermissionError(
                f"Ruta sensible bloqueada por política local: {target}"
            )
        if not self._is_allowed(target):
            roots = ", ".join(str(root) for root in self.allowed_roots)
            raise PermissionError(
                f"Ruta fuera de los roots permitidos: {target}. Roots actuales: {roots}"
            )
        return target

    def filter_matches(self, matches: list[dict[str, object]]) -> list[dict[str, object]]:
        filtered: list[dict[str, object]] = []
        for item in matches:
            raw_path = str(item.get("path") or "").strip()
            if not raw_path:
                continue
            try:
                self.validate_path(raw_path)
            except PermissionError:
                continue
            filtered.append(item)
        return filtered

    def _is_allowed(self, target: Path) -> bool:
        return any(_is_relative_to(target, root) for root in self.allowed_roots)

    def _is_sensitive(self, target: Path) -> bool:
        return any(_is_relative_to(target, root) for root in self.sensitive_roots)


class GuardedFileTools:
    def __init__(self, *, policy: FileAccessPolicy) -> None:
        self._policy = policy

    def read_file(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        preview: bool = False,
    ) -> ToolResult:
        target = self._policy.validate_path(path)
        return read_file(
            str(target),
            start_line=start_line,
            end_line=end_line,
            preview=preview,
        )

    def list_dir(self, path: str, depth: int = 1) -> ToolResult:
        target = self._policy.validate_path(path)
        return list_dir(str(target), depth=depth)

    def find_local(
        self,
        query: str,
        path: str | None = None,
        folder_hint: str | None = None,
        kind: str = "file",
        max_results: int = 10,
    ) -> ToolResult:
        guarded_path = None
        if path is not None:
            guarded_path = str(self._policy.validate_path(path))
        result = find_local(
            query=query,
            path=guarded_path,
            folder_hint=folder_hint,
            kind=kind,
            max_results=max_results,
        )
        payload = dict(result.payload)
        payload["matches"] = self._policy.filter_matches(
            list(payload.get("matches") or [])
        )
        return ToolResult(name=result.name, payload=payload)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
