from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class Renderer:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def show_banner(self, greeting: str) -> None:
        self.console.print(Panel.fit(greeting, border_style="cyan"))

    def show_tool(self, name: str, arguments: dict[str, object]) -> None:
        self.console.print(f"[bold cyan][tool:{name}][/bold cyan] {arguments}")

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
        text.append("/mode <cloud|local>\n")
        text.append("/auto [on|off|status]\n")
        text.append("/voice [on|off|status]\n")
        text.append("/listen\n")
        text.append("/read <path>\n")
        text.append("/web <query>\n")
        text.append("/run <cmd>\n")
        text.append("/python <code>\n")
        text.append("/recall <query>\n")
        text.append("/forget <query|id>\n")
        text.append("/cost\n")
        text.append("/log [n]\n")
        self.console.print(Panel.fit(text, border_style="green"))
