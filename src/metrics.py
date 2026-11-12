"""Benchmark metrics: token totals per mode/run, verdict accuracy vs ground
truth, and cross-mode agreement. Writes results/metrics.json and a
human-readable RESULTS.md table.
"""

from __future__ import annotations

import json
from pathlib import Path

from .llm import TokenLedger


def verdict_accuracy(reports: list[dict], ground_truth: dict[str, str]) -> dict:
    correct = 0
    compared = 0
    misses = []
    for r in reports:
        name = r["candidate"]
        got = r["verdict"]
        if got == "REUSED":
            # Recalled from Meko memory; compare the recalled verdict instead.
            got = _recalled_verdict(r.get("detail", "")) or got
        want = ground_truth.get(name)
        if want is None:
            continue
        compared += 1
        if got == want:
            correct += 1
        else:
            misses.append({"candidate": name, "want": want, "got": got})
    return {
        "compared": compared,
        "correct": correct,
        "accuracy": round(correct / compared, 4) if compared else None,
        "misses": misses,
    }


def _recalled_verdict(detail: str) -> str | None:
    for v in ("PASS", "FAIL", "UNSURE"):
        if f"final verdict" in detail and v in detail:
            return v
    return None


def build_results(ledger: TokenLedger, reports_by_mode: dict, ground_truth: dict[str, str], runs: int) -> dict:
    modes = {}
    for mode, reports in reports_by_mode.items():
        per_run = {str(run): ledger.summary(mode, run) for run in range(1, runs + 1)}
        modes[mode] = {
            "overall": ledger.summary(mode),
            "per_run": per_run,
            "accuracy": verdict_accuracy(reports, ground_truth),
        }
    out = {"modes": modes}
    if "baseline" in modes and "meko" in modes:
        b = modes["baseline"]["overall"]["total_tokens"]
        m = modes["meko"]["overall"]["total_tokens"]
        bc = modes["baseline"]["overall"]["llm_calls"]
        mc = modes["meko"]["overall"]["llm_calls"]
        out["comparison"] = {
            "token_reduction_pct": round(100 * (1 - m / b), 1) if b else None,
            "llm_call_reduction_pct": round(100 * (1 - mc / bc), 1) if bc else None,
            "quality_equal": modes["baseline"]["accuracy"]["accuracy"] == modes["meko"]["accuracy"]["accuracy"],
        }
    return out


def write_results(out: dict, outdir: str = "results") -> None:
    p = Path(outdir)
    p.mkdir(exist_ok=True)
    (p / "metrics.json").write_text(json.dumps(out, indent=2))
    lines = ["# HackHunt Crew benchmark results", ""]
    lines.append("| Mode | Run | LLM calls | Prompt tokens | Completion tokens | Total tokens |")
    lines.append("|---|---|---|---|---|---|")
    for mode, data in out["modes"].items():
        for run, s in sorted(data["per_run"].items(), key=lambda kv: int(kv[0])):
            lines.append(
                f"| {mode} | {run} | {s['llm_calls']} | {s['prompt_tokens']} | {s['completion_tokens']} | {s['total_tokens']} |"
            )
    if "comparison" in out:
        c = out["comparison"]
        lines += [
            "",
            f"- Token reduction with Meko: **{c['token_reduction_pct']}%**",
            f"- LLM call reduction with Meko: **{c['llm_call_reduction_pct']}%**",
            f"- Output quality equal across modes: **{c['quality_equal']}**",
        ]
    for mode, data in out["modes"].items():
        acc = data["accuracy"]
        lines.append(f"- {mode} verdict accuracy vs ground truth: {acc['correct']}/{acc['compared']} ({acc['accuracy']})")
    (p / "RESULTS.md").write_text("\n".join(lines) + "\n")
