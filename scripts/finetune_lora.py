#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fine-tuning LoRA offline para datasets ADV ARCHON. "
            "No modifica Ollama ni el flujo principal de la app."
        )
    )
    parser.add_argument(
        "--base-model",
        required=True,
        help="Ruta local o id compatible Transformers.",
    )
    parser.add_argument("--dataset", required=True, type=Path, help="JSONL Alpaca.")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Directorio de checkpoints LoRA.",
    )
    parser.add_argument("--rank", type=int, default=8)
    parser.add_argument("--alpha", type=float, default=16.0)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--allow-hf-download", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _train_lora(args)
    return 0


def _train_lora(args: argparse.Namespace) -> None:
    try:
        import torch
        from torch.nn.utils import clip_grad_norm_
        from torch.utils.data import DataLoader, Dataset
        from tqdm import tqdm
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            get_cosine_schedule_with_warmup,
        )
    except ImportError as exc:
        raise SystemExit(
            "Faltan dependencias opcionales. Instala solo para fine-tuning:\n"
            "uv pip install torch transformers tqdm llms-from-scratch"
        ) from exc

    replace_linear_with_lora = _load_lora_replacer()
    rows = _load_jsonl(args.dataset)
    if not rows:
        raise SystemExit(f"Dataset vacío o inválido: {args.dataset}")

    local_only = not bool(args.allow_hf_download)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, local_files_only=local_only)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.base_model, local_files_only=local_only)

    for parameter in model.parameters():
        parameter.requires_grad = False
    model = replace_linear_with_lora(model, rank=int(args.rank), alpha=float(args.alpha))
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if not trainable:
        raise SystemExit("No se encontraron parámetros LoRA entrenables.")

    class InstructionJsonlDataset(Dataset):  # type: ignore[misc]
        def __init__(self, records: list[dict[str, Any]]) -> None:
            self._records = records

        def __len__(self) -> int:
            return len(self._records)

        def __getitem__(self, index: int) -> dict[str, Any]:
            text = _format_instruction(self._records[index])
            encoded = tokenizer(
                text,
                max_length=int(args.max_length),
                truncation=True,
                padding="max_length",
                return_tensors="pt",
            )
            input_ids = encoded["input_ids"].squeeze(0)
            attention_mask = encoded["attention_mask"].squeeze(0)
            labels = input_ids.clone()
            labels[attention_mask == 0] = -100
            return {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": labels,
            }

    dataset = InstructionJsonlDataset(rows)
    loader = DataLoader(dataset, batch_size=max(1, int(args.batch_size)), shuffle=True)
    optimizer = torch.optim.AdamW(trainable, lr=float(args.lr))
    total_steps = max(1, len(loader) * int(args.epochs))
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=max(1, total_steps // 20),
        num_training_steps=total_steps,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    model.train()
    for epoch in range(1, int(args.epochs) + 1):
        progress = tqdm(loader, desc=f"epoch {epoch}")
        losses: list[float] = []
        for batch in progress:
            optimizer.zero_grad(set_to_none=True)
            batch = {key: value.to(model.device) for key, value in batch.items()}
            output = model(**batch)
            loss = output.loss
            loss.backward()
            clip_grad_norm_(trainable, max_norm=1.0)
            optimizer.step()
            scheduler.step()
            losses.append(float(loss.detach().cpu()))
            progress.set_postfix(loss=f"{losses[-1]:.4f}")
        checkpoint = args.output / f"epoch-{epoch}.pt"
        torch.save(_lora_state_dict(model), checkpoint)
        average = sum(losses) / len(losses) if losses else 0.0
        print(f"epoch {epoch}: loss={average:.4f} checkpoint={checkpoint}")


def _load_lora_replacer():
    try:
        from llms_from_scratch.appendix_e import replace_linear_with_lora

        return replace_linear_with_lora
    except Exception:
        return _replace_linear_with_lora_fallback


def _replace_linear_with_lora_fallback(model: Any, rank: int, alpha: float) -> Any:
    import torch
    import torch.nn as nn

    class LoRALayer(nn.Module):
        def __init__(self, in_features: int, out_features: int, rank: int, alpha: float) -> None:
            super().__init__()
            self.A = nn.Parameter(torch.randn(in_features, rank) * 0.01)
            self.B = nn.Parameter(torch.zeros(rank, out_features))
            self.scale = alpha / rank

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.scale * (x @ self.A @ self.B)

    class LinearWithLoRA(nn.Module):
        def __init__(self, linear: nn.Linear, rank: int, alpha: float) -> None:
            super().__init__()
            self.linear = linear
            self.lora = LoRALayer(linear.in_features, linear.out_features, rank, alpha)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.linear(x) + self.lora(x)

    for parameter in model.parameters():
        parameter.requires_grad = False
    _replace_children(model, LinearWithLoRA, rank=rank, alpha=alpha)
    return model


def _replace_children(module: Any, wrapper: Any, *, rank: int, alpha: float) -> None:
    import torch.nn as nn

    for name, child in list(module.named_children()):
        if isinstance(child, nn.Linear):
            setattr(module, name, wrapper(child, rank, alpha))
        else:
            _replace_children(child, wrapper, rank=rank, alpha=alpha)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if isinstance(data, dict):
            rows.append(data)
    return rows


def _format_instruction(row: dict[str, Any]) -> str:
    return (
        "### Instrucción\n"
        f"{row.get('instruction', '')}\n\n"
        "### Entrada\n"
        f"{row.get('input', '')}\n\n"
        "### Respuesta\n"
        f"{row.get('output', '')}"
    )


def _lora_state_dict(model: Any) -> dict[str, Any]:
    return {
        name: tensor.detach().cpu()
        for name, tensor in model.state_dict().items()
        if ".lora." in name or name.endswith(".A") or name.endswith(".B")
    }


if __name__ == "__main__":
    raise SystemExit(main())
