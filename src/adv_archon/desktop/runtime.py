from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from adv_archon.desktop.models import DesktopChatRequest, DesktopChatResponse


@dataclass(frozen=True, slots=True)
class DesktopRuntimeAssumption:
    title: str
    description: str


def build_default_runtime_assumptions() -> tuple[DesktopRuntimeAssumption, ...]:
    return (
        DesktopRuntimeAssumption(
            title="Chat sync placeholder",
            description=(
                "La ventana desktop habla con un backend simple. La integración con el agente "
                "real quedará detrás de una interfaz dedicada."
            ),
        ),
        DesktopRuntimeAssumption(
            title="Adjuntos locales",
            description=(
                "Los adjuntos son rutas locales del Mac. El runtime compartido decidirá después "
                "si solo leerlos, resumirlos o incorporarlos al knowledge base."
            ),
        ),
        DesktopRuntimeAssumption(
            title="Streaming local activo",
            description=(
                "La UI pinta la respuesta del modelo local a medida que llegan tokens, "
                "sin esperar al bloque completo."
            ),
        ),
    )


@runtime_checkable
class DesktopChatBackend(Protocol):
    def complete(self, request: DesktopChatRequest) -> DesktopChatResponse:
        """Resolve a desktop chat request."""


class EchoDesktopBackend:
    def __init__(
        self,
        *,
        assumptions: tuple[DesktopRuntimeAssumption, ...] | None = None,
    ) -> None:
        self._assumptions = assumptions or build_default_runtime_assumptions()

    @property
    def assumptions(self) -> tuple[DesktopRuntimeAssumption, ...]:
        return self._assumptions

    def complete(self, request: DesktopChatRequest) -> DesktopChatResponse:
        attachment_names = [attachment.display_name for attachment in request.attachments]
        if attachment_names:
            attachment_line = (
                "Adjuntos capturados: " + ", ".join(attachment_names[:4]) + "."
            )
        else:
            attachment_line = "No has adjuntado archivos todavía."
        assumption_line = self._assumptions[0].description if self._assumptions else ""
        text = (
            "Esta es la primera capa desktop de ADV ARCHON. "
            f"Prompt recibido: {request.prompt.strip() or '(vacío)'}. "
            f"{attachment_line} {assumption_line}"
        ).strip()
        return DesktopChatResponse(
            text=text,
            used_attachments=request.attachments,
            metadata={"backend": "echo-desktop"},
        )
