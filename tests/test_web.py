from __future__ import annotations

import adv_archon.tools.web as web_module


def test_extract_price_lines_filters_noise_and_deduplicates() -> None:
    page_text = """
    Envío gratuito en pedidos superiores a 50 €
    172,51 €
    172,51 €
    Price $220
    shipping 5 €
    """

    prices = web_module._extract_price_lines(page_text)

    assert prices == ["172,51 €", "Price $220"]


def test_should_fallback_to_browser_for_shop_page_without_price() -> None:
    assert web_module._should_fallback_to_browser(
        "https://example.com/products/sudadera",
        "Texto escaso sin precio",
    )


def test_web_fetch_uses_browser_fallback_when_static_text_is_insufficient(
    monkeypatch,
) -> None:
    monkeypatch.setattr(web_module, "_allowed_by_robots", lambda _url: True)
    monkeypatch.setattr(web_module, "_fetch_static_text", lambda _url: "Texto corto")
    monkeypatch.setattr(
        web_module,
        "_fetch_browser_text",
        lambda _url: "Precio: 172,51 €\n\nSudadera Le Connoisseur",
    )

    result = web_module.web_fetch("https://example.com/products/sudadera")

    assert result.payload["text"].startswith("Precio: 172,51 €")
