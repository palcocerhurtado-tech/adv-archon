from __future__ import annotations

from pathlib import Path
from typing import Any

from adv_archon.core.research_workbench import (
    build_research_queries,
    export_research_docx,
    export_research_pdf,
    extract_formula_candidates,
    load_research_attachments,
    run_research_workbench,
)


def _fake_search(query: str, n: int) -> dict[str, Any]:
    return {
        "results": [
            {
                "title": f"Fuente para {query}",
                "url": f"https://example.com/{abs(hash(query)) % 10000}",
                "snippet": "Explica formulas y evidencia para resolver el trabajo.",
            }
        ][:n]
    }


def _fake_fetch(_url: str) -> dict[str, str]:
    return {
        "text": (
            "Para un triangulo, la formula de area es area = base * altura / 2. "
            "El metodo exige declarar unidades, supuestos y comprobacion manual."
        )
    }


def test_research_workbench_builds_offline_evidence_and_exports(tmp_path: Path) -> None:
    statement = tmp_path / "enunciado.txt"
    statement.write_text(
        "Resolver un problema de area de triangulo con base y altura conocidas.",
        encoding="utf-8",
    )

    result = run_research_workbench(
        "Calcular el area de un triangulo y justificar la formula",
        attachment_paths=[str(statement)],
        search_fn=_fake_search,
        fetch_fn=_fake_fetch,
    )
    docx_path = export_research_docx(result, tmp_path / "research.docx")
    pdf_path = export_research_pdf(result, tmp_path / "research.pdf")

    assert result.evidence_count >= 1
    assert "area = base * altura / 2" in "\n".join(result.formula_candidates)
    assert result.gaps == (
        "Revisar manualmente cualquier formula antes de entregar si tiene impacto "
        "academico o profesional.",
    )
    assert docx_path.exists() and docx_path.stat().st_size > 0
    assert pdf_path.exists() and pdf_path.stat().st_size > 0


def test_research_queries_mix_question_and_attachment_terms(tmp_path: Path) -> None:
    statement = tmp_path / "brief.txt"
    statement.write_text("inundabilidad catastro parcela vivienda", encoding="utf-8")
    attachments = load_research_attachments([str(statement)])

    queries = build_research_queries(
        "Analizar una parcela urbana",
        attachments=attachments,
        max_queries=4,
    )

    assert queries[0] == "Analizar una parcela urbana"
    assert any("catastro" in query for query in queries)


def test_extract_formula_candidates_finds_equations_and_formula_lines() -> None:
    formulas = extract_formula_candidates(
        "Formula principal: V = superficie * altura\n"
        "Otra relacion: coste = horas * tarifa\n"
        "Texto sin calculo relevante"
    )

    assert any("V =" in item for item in formulas)
    assert any("coste = horas * tarifa" in item for item in formulas)


def test_research_workbench_survives_search_failures() -> None:
    def broken_search(_query: str, _n: int) -> dict[str, Any]:
        raise TimeoutError("network timeout")

    result = run_research_workbench(
        "Investigar cargas de viento",
        search_fn=broken_search,
        fetch_fn=_fake_fetch,
    )

    assert result.evidence_count == 0
    assert "Faltan fuentes web verificadas" in result.gaps[0]
