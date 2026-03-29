from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _infer_run_dir(report_path: Path) -> Path:
    # Expected layout in pipeline: <run_dir>/implementation/<candidate>/round_x/report.md
    # For standalone smoke tests, fall back to report parent.
    parts = report_path.parts
    if len(parts) >= 5:
        return report_path.parents[3]
    return report_path.parent


@dataclass(frozen=True)
class Strategy:
    name: str
    description: str
    bits_schedule: tuple[int, int, int]
    group_schedule: tuple[int, int, int]
    include_terms: tuple[str, ...]
    exclude_terms: tuple[str, ...]

    def round_bits(self, round_index: int) -> int:
        idx = max(0, min(2, round_index - 1))
        return self.bits_schedule[idx]

    def round_group_size(self, round_index: int) -> int:
        idx = max(0, min(2, round_index - 1))
        return self.group_schedule[idx]


STRATEGIES: dict[str, Strategy] = {
    "q8_selective": Strategy(
        name="q8_selective",
        description="8-bit per-channel quantization for attention/MLP projection matrices.",
        bits_schedule=(8, 8, 8),
        group_schedule=(0, 0, 0),
        include_terms=("self_attn", "mlp"),
        exclude_terms=("embed_tokens", "lm_head", "layernorm", "norm"),
    ),
    "q6_balanced": Strategy(
        name="q6_balanced",
        description="6-bit grouped quantization with round-wise group-size refinement for balanced compression and quality.",
        bits_schedule=(6, 6, 6),
        group_schedule=(128, 96, 64),
        include_terms=("self_attn", "mlp"),
        exclude_terms=("embed_tokens", "lm_head", "layernorm", "norm"),
    ),
    "q4_aggressive": Strategy(
        name="q4_aggressive",
        description="4-bit grouped quantization for aggressive compression.",
        bits_schedule=(4, 4, 4),
        group_schedule=(128, 128, 96),
        include_terms=("self_attn", "mlp", "embed_tokens", "lm_head"),
        exclude_terms=("layernorm", "norm"),
    ),
}


def _should_quantize(name: str, tensor: torch.Tensor, strategy: Strategy) -> bool:
    if not tensor.is_floating_point():
        return False
    if tensor.ndim < 2:
        return False
    lowered = name.lower()
    if any(term in lowered for term in strategy.exclude_terms):
        return False
    if strategy.include_terms and not any(term in lowered for term in strategy.include_terms):
        return False
    return True


def _quantize_dequantize_matrix(matrix: torch.Tensor, bits: int, group_size: int) -> tuple[torch.Tensor, float]:
    # matrix shape: [rows, cols]
    rows, cols = matrix.shape
    qmax = float((1 << (bits - 1)) - 1)
    if qmax <= 0:
        raise ValueError(f"bits must be >=2, got {bits}")

    if group_size <= 0:
        absmax = matrix.abs().amax(dim=1, keepdim=True).clamp_min(1e-8)
        scale = absmax / qmax
        quant = torch.round(matrix / scale).clamp(-qmax, qmax)
        dequant = quant * scale
        quant_bytes = (rows * cols * bits) / 8.0 + (rows * 4.0)
        return dequant, quant_bytes

    pad_cols = (group_size - (cols % group_size)) % group_size
    if pad_cols > 0:
        padded = torch.nn.functional.pad(matrix, (0, pad_cols), mode="constant", value=0.0)
    else:
        padded = matrix
    grouped = padded.view(rows, -1, group_size)
    absmax = grouped.abs().amax(dim=2, keepdim=True).clamp_min(1e-8)
    scale = absmax / qmax
    quant = torch.round(grouped / scale).clamp(-qmax, qmax)
    dequant_grouped = quant * scale
    dequant = dequant_grouped.reshape(rows, -1)
    if pad_cols > 0:
        dequant = dequant[:, :cols]
    quant_bytes = (rows * cols * bits) / 8.0 + (scale.numel() * 4.0)
    return dequant, quant_bytes


def _apply_quantization(
    model: torch.nn.Module,
    *,
    strategy: Strategy,
    bits: int,
    group_size: int,
) -> dict[str, Any]:
    quantized_tensors = 0
    skipped_tensors = 0
    quantized_params = 0
    total_params = 0
    quantized_size_bytes = 0.0
    baseline_size_bytes = 0.0

    with torch.no_grad():
        for name, param in model.named_parameters():
            tensor = param.data
            param_numel = int(tensor.numel())
            total_params += param_numel
            baseline_size_bytes += float(param_numel * tensor.element_size())

            if not _should_quantize(name, tensor, strategy):
                skipped_tensors += 1
                quantized_size_bytes += float(param_numel * tensor.element_size())
                continue

            original_shape = tensor.shape
            flat = tensor.float().view(original_shape[0], -1)
            dequant, qbytes = _quantize_dequantize_matrix(flat, bits=bits, group_size=group_size)
            restored = dequant.view(original_shape).to(dtype=tensor.dtype)
            tensor.copy_(restored)

            quantized_tensors += 1
            quantized_params += param_numel
            quantized_size_bytes += qbytes

    compression_ratio = baseline_size_bytes / max(1e-9, quantized_size_bytes)
    size_reduction_pct = (1.0 - (quantized_size_bytes / max(1e-9, baseline_size_bytes))) * 100.0
    quantized_param_pct = (quantized_params / max(1, total_params)) * 100.0
    return {
        "quantized_tensors": quantized_tensors,
        "skipped_tensors": skipped_tensors,
        "quantized_params": quantized_params,
        "total_params": total_params,
        "quantized_param_pct": quantized_param_pct,
        "baseline_size_bytes": baseline_size_bytes,
        "quantized_size_bytes": quantized_size_bytes,
        "compression_ratio": compression_ratio,
        "size_reduction_pct": size_reduction_pct,
    }


def _evaluate_perplexity(
    model: torch.nn.Module,
    tokenizer: Any,
    *,
    eval_text: str,
    seq_len: int,
    max_eval_tokens: int,
) -> tuple[float, int, float]:
    encoded = tokenizer(eval_text, return_tensors="pt")
    input_ids = encoded["input_ids"][0]
    if input_ids.numel() < 8:
        raise ValueError("evaluation corpus is too short after tokenization")
    if max_eval_tokens > 0 and input_ids.numel() > max_eval_tokens:
        input_ids = input_ids[:max_eval_tokens]

    total_nll = 0.0
    total_tokens = 0
    t0 = time.perf_counter()

    model.eval()
    with torch.no_grad():
        for start in range(0, max(1, input_ids.numel() - 1), seq_len):
            chunk = input_ids[start : start + seq_len]
            if chunk.numel() < 2:
                continue
            batch = chunk.unsqueeze(0)
            out = model(input_ids=batch, labels=batch)
            loss = float(out.loss.item())
            tokens_in_loss = int(batch.shape[1] - 1)
            total_nll += loss * tokens_in_loss
            total_tokens += tokens_in_loss

    if total_tokens <= 0:
        raise ValueError("no valid evaluation tokens found for perplexity computation")

    ppl = math.exp(total_nll / total_tokens)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    return ppl, total_tokens, latency_ms


def _score_quantization(
    *,
    baseline_ppl: float,
    quant_ppl: float,
    compression_ratio: float,
) -> float:
    # Keep perplexity stability as the primary goal, compression as secondary.
    ppl_delta_pct = ((quant_ppl - baseline_ppl) / max(1e-9, baseline_ppl)) * 100.0
    quality_score = max(0.0, 1.0 - (abs(ppl_delta_pct) / 8.0))
    compression_score = min(1.0, max(0.0, (compression_ratio - 1.0) / 3.0))
    score = 0.75 * quality_score + 0.25 * compression_score
    return max(0.0, min(1.0, score))


def _write_report(
    *,
    report_path: Path,
    run_id: str,
    candidate_id: str,
    round_index: int,
    strategy: Strategy,
    bits: int,
    group_size: int,
    baseline_ppl: float,
    quant_ppl: float,
    ppl_delta_pct: float,
    quant_stats: dict[str, Any],
    score: float,
    eval_tokens: int,
    eval_latency_ms: float,
) -> None:
    compression_ratio = _safe_float(quant_stats.get("compression_ratio"))
    size_reduction_pct = _safe_float(quant_stats.get("size_reduction_pct"))
    qparam_pct = _safe_float(quant_stats.get("quantized_param_pct"))
    gate_ok = abs(ppl_delta_pct) <= 3.0 and compression_ratio >= 1.5
    gate_text = "PASS" if gate_ok else "FAIL"
    lines = [
        "## Key Hypothesis",
        f"Strategy `{strategy.name}` can reduce effective model storage while keeping perplexity almost unchanged on SmolLM2-360M.",
        "",
        "## Implementation Delta",
        f"- Run `{run_id}` candidate `{candidate_id}` round `{round_index}` executed real perplexity evaluation on local SmolLM2-360M.",
        f"- Quantization settings: bits={bits}, group_size={group_size if group_size > 0 else 'per-channel'}, quantized_param_pct={qparam_pct:.2f}%.",
        f"- Baseline perplexity={baseline_ppl:.4f}, quantized perplexity={quant_ppl:.4f}, delta={ppl_delta_pct:.2f}%.",
        f"- Effective size reduction={size_reduction_pct:.2f}% (compression={compression_ratio:.3f}x), gate={gate_text}.",
        "",
        "## Strengths",
        "- Uses real forward-pass perplexity on local model instead of simulated metrics.",
        f"- Compression gain is measurable ({compression_ratio:.3f}x) with deterministic quantization configuration.",
        f"- Primary score={score:.4f} keeps perplexity stability as first priority.",
        "",
        "## Weaknesses",
        "- Evaluation corpus is finite and may not cover all distribution shifts.",
        "- Weight-only quantization error is measured via dequantized inference, not specialized low-bit kernels.",
        "- Further calibration/tuning may be needed for broader domain robustness.",
        "",
        "## Transferable Insights",
        "- Selective quantization on attention/MLP projections is a practical first step for small perplexity drift.",
        "- Group size tuning can trade off compression granularity and quality retention.",
        "- A hard gate on perplexity delta prevents over-optimized but inaccurate compression choices.",
        "",
        "## Open Problems",
        "- Validate the same strategy on larger and domain-specific evaluation corpora.",
        "- Add latency and memory peak profiling under real serving runtime.",
        "- Explore mixed-precision KV-cache and activation quantization.",
        "",
        "## Proposed Next Move",
        "- Keep strategy if gate PASS; otherwise roll back one quantization aggressiveness level.",
        "- Run an extra ablation on quantized module subsets (attn-only vs attn+mlp).",
        "- Integrate final winner into deployment benchmarking with throughput tests.",
        "",
        f"- eval_tokens={eval_tokens}, eval_latency_ms={eval_latency_ms:.2f}",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_experiment(
    *,
    strategy_name: str,
    model_path: Path,
    eval_corpus: Path,
    max_eval_tokens: int,
    seq_len: int,
) -> dict[str, Any]:
    if strategy_name not in STRATEGIES:
        raise ValueError(f"Unsupported strategy: {strategy_name}. Available: {', '.join(sorted(STRATEGIES))}")
    strategy = STRATEGIES[strategy_name]

    report_path = Path(os.environ.get("NANOBOT_REPORT_PATH", "")).expanduser()
    metrics_path = Path(os.environ.get("NANOBOT_METRICS_PATH", "")).expanduser()
    run_id = str(os.environ.get("NANOBOT_RUN_ID", "quant_run")).strip() or "quant_run"
    candidate_id = str(os.environ.get("NANOBOT_CANDIDATE_ID", "candidate")).strip() or "candidate"
    round_index = max(1, _safe_int(os.environ.get("NANOBOT_ROUND", "1"), default=1))

    if not report_path:
        raise ValueError("NANOBOT_REPORT_PATH is required")
    if not metrics_path:
        raise ValueError("NANOBOT_METRICS_PATH is required")
    if not model_path.exists():
        raise FileNotFoundError(f"model path does not exist: {model_path}")
    if not eval_corpus.exists():
        raise FileNotFoundError(f"eval corpus file does not exist: {eval_corpus}")

    run_dir = _infer_run_dir(report_path)
    cache_dir = run_dir / "runtime" / "quant_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    lock_path = run_dir / "runtime" / "quant_model.lock"

    bits = strategy.round_bits(round_index)
    group_size = strategy.round_group_size(round_index)

    eval_text = eval_corpus.read_text(encoding="utf-8")
    cache_key = f"{model_path.resolve()}|{eval_corpus.resolve()}|{max_eval_tokens}|{seq_len}"
    baseline_cache_file = cache_dir / f"baseline_{abs(hash(cache_key))}.json"

    start = time.perf_counter()
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            baseline_cache = _load_json(baseline_cache_file)
            tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
            model = AutoModelForCausalLM.from_pretrained(str(model_path), local_files_only=True)

            if baseline_cache.get("status") == "ok":
                baseline_ppl = _safe_float(baseline_cache.get("baseline_ppl"))
                baseline_tokens = _safe_int(baseline_cache.get("eval_tokens"))
                baseline_latency_ms = _safe_float(baseline_cache.get("eval_latency_ms"))
            else:
                baseline_ppl, baseline_tokens, baseline_latency_ms = _evaluate_perplexity(
                    model,
                    tokenizer,
                    eval_text=eval_text,
                    seq_len=seq_len,
                    max_eval_tokens=max_eval_tokens,
                )
                _save_json(
                    baseline_cache_file,
                    {
                        "status": "ok",
                        "model_path": str(model_path),
                        "eval_corpus": str(eval_corpus),
                        "max_eval_tokens": max_eval_tokens,
                        "seq_len": seq_len,
                        "baseline_ppl": baseline_ppl,
                        "eval_tokens": baseline_tokens,
                        "eval_latency_ms": baseline_latency_ms,
                        "generated_at_utc": _utc_now(),
                    },
                )

            quant_stats = _apply_quantization(
                model,
                strategy=strategy,
                bits=bits,
                group_size=group_size,
            )
            quant_ppl, eval_tokens, eval_latency_ms = _evaluate_perplexity(
                model,
                tokenizer,
                eval_text=eval_text,
                seq_len=seq_len,
                max_eval_tokens=max_eval_tokens,
            )
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    ppl_delta_pct = ((quant_ppl - baseline_ppl) / max(1e-9, baseline_ppl)) * 100.0
    compression_ratio = _safe_float(quant_stats.get("compression_ratio"), default=1.0)
    score = _score_quantization(
        baseline_ppl=baseline_ppl,
        quant_ppl=quant_ppl,
        compression_ratio=compression_ratio,
    )
    total_duration_ms = (time.perf_counter() - start) * 1000.0

    secondary_metrics = {
        "baseline_perplexity": round(baseline_ppl, 6),
        "quantized_perplexity": round(quant_ppl, 6),
        "perplexity_delta_pct": round(ppl_delta_pct, 6),
        "compression_ratio": round(compression_ratio, 6),
        "size_reduction_pct": round(_safe_float(quant_stats.get("size_reduction_pct")), 6),
        "quantized_param_pct": round(_safe_float(quant_stats.get("quantized_param_pct")), 6),
        "baseline_size_mb": round(_safe_float(quant_stats.get("baseline_size_bytes")) / (1024 * 1024), 6),
        "quantized_size_mb": round(_safe_float(quant_stats.get("quantized_size_bytes")) / (1024 * 1024), 6),
        "eval_tokens": int(eval_tokens),
        "eval_latency_ms": round(eval_latency_ms, 4),
        "baseline_eval_tokens": int(baseline_tokens),
        "baseline_eval_latency_ms": round(baseline_latency_ms, 4),
        "quantized_tensors": int(quant_stats.get("quantized_tensors", 0)),
        "skipped_tensors": int(quant_stats.get("skipped_tensors", 0)),
        "bits": bits,
        "group_size": group_size,
    }

    metrics_payload = {
        "primary_metric": round(score, 6),
        "secondary_metrics": secondary_metrics,
        "execution_info": {
            "strategy": strategy.name,
            "strategy_description": strategy.description,
            "run_id": run_id,
            "candidate_id": candidate_id,
            "round": round_index,
            "model_path": str(model_path),
            "eval_corpus": str(eval_corpus),
            "max_eval_tokens": max_eval_tokens,
            "seq_len": seq_len,
            "duration_ms": round(total_duration_ms, 3),
            "generated_at_utc": _utc_now(),
        },
    }

    _write_report(
        report_path=report_path,
        run_id=run_id,
        candidate_id=candidate_id,
        round_index=round_index,
        strategy=strategy,
        bits=bits,
        group_size=group_size,
        baseline_ppl=baseline_ppl,
        quant_ppl=quant_ppl,
        ppl_delta_pct=ppl_delta_pct,
        quant_stats=quant_stats,
        score=score,
        eval_tokens=eval_tokens,
        eval_latency_ms=eval_latency_ms,
    )
    _save_json(metrics_path, metrics_payload)
    return metrics_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SmolLM2-360M quantization experiment and emit nanobot worker artifacts.")
    parser.add_argument("--strategy", required=True, choices=sorted(STRATEGIES.keys()))
    parser.add_argument("--model-path", required=True, help="Local model directory path.")
    parser.add_argument("--eval-corpus", required=True, help="Local text file for perplexity evaluation.")
    parser.add_argument("--max-eval-tokens", type=int, default=896, help="Maximum evaluation tokens.")
    parser.add_argument("--seq-len", type=int, default=128, help="Sequence length for perplexity chunks.")
    args = parser.parse_args()

    run_experiment(
        strategy_name=args.strategy,
        model_path=Path(args.model_path).expanduser(),
        eval_corpus=Path(args.eval_corpus).expanduser(),
        max_eval_tokens=max(64, int(args.max_eval_tokens)),
        seq_len=max(32, int(args.seq_len)),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
