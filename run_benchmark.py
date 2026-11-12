#!/usr/bin/env python3
"""Run the HackHunt Crew benchmark.

Usage:
    python run_benchmark.py --mode baseline --runs 2
    python run_benchmark.py --mode meko --runs 2
    python run_benchmark.py --mode both --runs 2

Each run evaluates every candidate in data/candidates.json. In meko mode the
second run starts warm: verdicts and failure patterns are recalled from the
shared datapack instead of being re-derived.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.crew import Crew
from src.llm import GroqLLM, TokenLedger
from src.meko_client import MekoClient
from src.metrics import build_results, write_results

ROOT = Path(__file__).parent


def load_candidates() -> list[dict]:
    candidates = json.loads((ROOT / "data" / "candidates.json").read_text())
    for c in candidates:
        c["page_text"] = (ROOT / "data" / c["page_file"]).read_text()
    return candidates


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "meko", "both"], default="both")
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()

    ledger = TokenLedger()
    llm = GroqLLM(
        api_key=os.environ["GROQ_API_KEY"],
        model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        ledger=ledger,
    )
    candidates = load_candidates()
    ground_truth = {c["name"]: c["ground_truth"]["verdict"] for c in candidates}
    modes = ["baseline", "meko"] if args.mode == "both" else [args.mode]

    reports_by_mode: dict[str, list[dict]] = {}
    for mode in modes:
        meko = None
        if mode == "meko":
            meko = MekoClient(
                api_key=os.environ["MEKO_API_KEY"],
                datapack_id=os.environ["MEKO_DATAPACK_ID"],
                base_url=os.environ.get("MEKO_MCP_URL", "https://mcp.mekodata.ai/mcp"),
            )
            meko.initialize()
        crew = Crew(llm, meko=meko, mode=mode)
        crew.seed_knowledge()
        reports: list[dict] = []
        for run in range(1, args.runs + 1):
            for c in candidates:
                reports.append(crew.evaluate(c, run))
        reports_by_mode[mode] = reports
        (ROOT / "results").mkdir(exist_ok=True)
        (ROOT / "results" / f"reports-{mode}.json").write_text(json.dumps(reports, indent=2))

    out = build_results(ledger, reports_by_mode, ground_truth, args.runs)
    write_results(out, str(ROOT / "results"))
    print(json.dumps(out.get("comparison", out), indent=2))


if __name__ == "__main__":
    main()
