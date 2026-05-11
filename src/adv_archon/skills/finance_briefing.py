"""Skill: Finance briefing.

Fetches stock/crypto quotes and generates a concise market briefing.
Requires: yfinance (added to pyproject.toml).
"""

from __future__ import annotations

from typing import Any

from adv_archon.skills.base import Skill, SkillResult
from adv_archon.skills.registry import registry


class FinanceBriefingSkill(Skill):
    name = "finance_briefing"
    description = (
        "Genera un resumen financiero para una lista de tickers (acciones, ETFs, cripto). "
        "Devuelve precio actual, cambio diario y resumen narrativo."
    )
    args_schema = {
        "tickers": {
            "type": "string",
            "description": "Tickers separados por comas, ej: 'AAPL,MSFT,BTC-USD'.",
        },
        "currency": {
            "type": "string",
            "description": "Moneda de visualización: 'USD' (defecto) o 'EUR'.",
        },
    }

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    def run(self, *, tickers: str, currency: str = "USD", **_: Any) -> SkillResult:
        try:
            import yfinance as yf  # type: ignore[import]
        except ImportError:
            return SkillResult(
                success=False,
                output="yfinance no instalado. Ejecuta: uv add yfinance",
            )

        symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if not symbols:
            return SkillResult(success=False, output="No se proporcionaron tickers.")

        rows: list[str] = []
        data_for_llm: list[dict[str, Any]] = []

        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = getattr(info, "last_price", None) or getattr(
                    info, "regularMarketPrice", None
                )
                prev_close = getattr(info, "previous_close", None) or getattr(
                    info, "regularMarketPreviousClose", None
                )

                if price is None:
                    rows.append(f"  {sym}: precio no disponible")
                    continue

                change = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
                arrow = "▲" if change >= 0 else "▼"
                rows.append(
                    f"  {sym:10s} {price:>10.2f} {currency}  {arrow} {abs(change):.2f}%"
                )
                data_for_llm.append({"ticker": sym, "price": price, "change_pct": change})
            except Exception as exc:
                rows.append(f"  {sym}: error — {exc}")

        table = "\n".join(rows)

        if self._llm and data_for_llm:
            from adv_archon.core.llm_types import LLMMessage

            prompt = (
                "Resume en 2-3 frases el estado del mercado basándote en estos datos:\n"
                + "\n".join(
                    f"{d['ticker']}: {d['price']:.2f} ({d['change_pct']:+.2f}%)"
                    for d in data_for_llm
                )
            )
            resp = self._llm.complete(
                [LLMMessage(role="user", content=prompt)],
                system_prompt="Eres un analista financiero conciso. Responde en español.",
                task="fast",
            )
            narrative = "\n\n" + resp.text
        else:
            narrative = ""

        output = f"Resumen financiero — {len(symbols)} ticker(s):\n{table}{narrative}"
        return SkillResult(
            success=True,
            output=output,
            artifacts={"data": data_for_llm},
        )


registry.register(FinanceBriefingSkill())
