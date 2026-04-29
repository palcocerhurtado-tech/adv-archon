from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from adv_archon.core.agent import TurnContextSnapshot


class Renderer:
    def __init__(
        self,
        console: Console | None = None,
        *,
        show_tool_input: bool = False,
    ) -> None:
        self.console = console or Console()
        self._show_tool_input = show_tool_input

    def show_banner(self, greeting: str) -> None:
        self.console.print(Panel.fit(greeting, border_style="cyan"))

    def show_tool(self, name: str, arguments: dict[str, object]) -> None:
        if not self._show_tool_input:
            return
        self.console.print(f"[bold cyan][tool:{name}][/bold cyan] {arguments}")

    def show_context_panel(self, snapshot: TurnContextSnapshot) -> None:
        lines = [
            f"Intent: {snapshot.intent}",
            f"Perfil: {snapshot.profile}",
            f"Modo: {snapshot.execution_mode}",
            f"Checkpoint: {snapshot.checkpoint}",
        ]
        if snapshot.reasons:
            lines.append(f"Señales: {', '.join(snapshot.reasons)}")
        if snapshot.confidence_hint:
            lines.append(f"Pista de confianza: {snapshot.confidence_hint}")
        if snapshot.memory_hits:
            lines.append("Memoria:")
            lines.extend(f"- {item}" for item in snapshot.memory_hits)
        if snapshot.knowledge_hits:
            lines.append("Conocimiento local:")
            lines.extend(f"- {item}" for item in snapshot.knowledge_hits)
        self.console.print(
            Panel.fit("\n".join(lines), border_style="magenta", title="Contexto")
        )

    def stream_chunk(self, chunk: str) -> None:
        self.console.print(chunk, end="")

    def finish_stream(self) -> None:
        self.console.print()

    def show_info(self, message: str) -> None:
        self.console.print(message)

    def show_error(self, message: str) -> None:
        self.console.print(f"[bold red]Error:[/bold red] {message}")

    def show_help(self) -> None:
        text = Text()
        text.append("Commands\n", style="bold")
        text.append("/help\n")
        text.append("/exit\n")
        text.append("/daily [brief|raw]\n")
        text.append("/briefing [query]\n")
        text.append("/mode <cloud|local>\n")
        text.append("/profile [name|status]\n")
        text.append("/auto [on|off|status]\n")
        text.append("/voice [on|off|status]\n")
        text.append("/listen\n")
        text.append("/voice-note [titulo]\n")
        text.append("/read <path>\n")
        text.append("/web <query>\n")
        text.append("/vault <query>\n")
        text.append("/meeting [query]\n")
        text.append("/triage [query]\n")
        text.append("/study [query|path]\n")
        text.append("/memory [status|categories|list|remember|edit|forget]\n")
        text.append("/automation [status|presets|install|tasks]\n")
        text.append("/pgou [status|add <municipio>|check <plano.pdf> <municipio>|report <plano.pdf> <municipio>|delete <municipio>]\n")
        text.append("/run <cmd>\n")
        text.append("/python <code>\n")
        text.append("/recall <query>\n")
        text.append("/forget <query|id>\n")
        text.append("/cost\n")
        text.append("/log [n]\n")
        self.console.print(Panel.fit(text, border_style="green"))
