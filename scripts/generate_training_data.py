#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from adv_archon.core.config import load_app_config
from adv_archon.core.training_data import (
    generate_training_examples,
    load_case_templates,
    write_jsonl,
)
from adv_archon.integrations.ollama import OllamaClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Genera dataset sintético de cumplimiento urbanístico con Ollama local."
    )
    parser.add_argument("--n", type=int, default=200, help="Número de ejemplos válidos.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/compliance_dataset.jsonl"),
        help="Ruta JSONL de salida.",
    )
    parser.add_argument(
        "--templates",
        type=Path,
        default=Path("data/case_templates.json"),
        help="Plantillas base de casos urbanísticos.",
    )
    parser.add_argument("--model", default="", help="Modelo Ollama. Default: config local.")
    parser.add_argument("--seed", type=int, default=42, help="Semilla reproducible.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_app_config(mode_override="local")
    model = args.model.strip() or config.llm.ollama_model
    client = OllamaClient(
        base_url=config.llm.ollama_base_url,
        model=model,
        temperature=0.2,
        timeout=float(config.llm.ollama_timeout_seconds),
        num_ctx=config.llm.ollama_num_ctx,
        keep_alive=config.llm.ollama_keep_alive,
    )
    templates = load_case_templates(args.templates)
    examples = generate_training_examples(
        templates=templates,
        client=client,
        count=args.n,
        seed=args.seed,
    )
    write_jsonl(examples, args.output)
    print(
        f"Dataset generado: {len(examples)}/{args.n} ejemplos válidos -> "
        f"{args.output.expanduser()}"
    )
    if len(examples) < args.n:
        print("Aviso: algunos intentos se descartaron por JSON inválido o campos incompletos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
