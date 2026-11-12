#!/usr/bin/env python3
"""Run the HackHunt Crew benchmark.

Usage:
    python run_benchmark.py --mode baseline --runs 2
    python run_benchmark.py --mode meko --runs 2
    python run_benchmark.py --mode both --runs 2
    python run_benchmark.py --mode meko --runs 2 --limit 3   # resumable chunk

Each run evaluates every candidate in data/candidates.json. In meko mode the
later passes recall scoped facts from the shared datapack. Every verdict
is re-evaluated; no label is reused as a shortcut.

With --limit the run is resumable: reports and the token ledger are
checkpointed under results/ after every candidate, so a later invocation
picks up exactly where the previous one stopped.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from src.crew import Crew
from src.llm import LLM, CallRecord, TokenLedger
from src.meko_client import MekoClient
from src.metrics import build_results, write_results

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"


def load_candidates() -> list[dict]:
    candidates = json.loads((ROOT / "data" / "candidates.json").read_text())
    for c in candidates:
        c["page_text"] = (ROOT / "data" / c["page_file"]).read_text()
    return candidates


def load_checkpoint(mode: str) -> tuple[list[dict], TokenLedger]:
    reports_path = RESULTS / f"reports-{mode}.json"
    ledger_path = RESULTS / f"ledger-{mode}.json"
    reports = json.loads(reports_path.read_text()) if reports_path.exists() else []
    ledger = TokenLedger()
    if ledger_path.exists():
        ledger.records = [CallRecord(**r) for r in json.loads(ledger_path.read_text())]
    return reports, ledger


def save_checkpoint(mode: str, reports: list[dict], ledger: TokenLedger, crew: Crew) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"state-{mode}.json").write_text(json.dumps({"learnings": crew.learnings, "conversations": crew._conversations}))
    (RESULTS / f"reports-{mode}.json").write_text(json.dumps(reports, indent=2))
    (RESULTS / f"ledger-{mode}.json").write_text(json.dumps([asdict(r) for r in ledger.records], indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "meko", "both"], default="both")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="max candidates this invocation (0 = all)")
    ap.add_argument("--fresh", action="store_true", help="discard existing checkpoints first")
    args = ap.parse_args()

    candidates = load_candidates()
    ground_truth = {c["name"]: c["ground_truth"]["verdict"] for c in candidates}
    modes = ["baseline", "meko"] if args.mode == "both" else [args.mode]
    n = len(candidates)
    total = args.runs * n

    if args.fresh:
        for mode in modes:
            for suffix in (f"reports-{mode}.json", f"ledger-{mode}.json", f"state-{mode}.json"):
                p = RESULTS / suffix
                if p.exists():
                    p.unlink()

    reports_by_mode: dict[str, list[dict]] = {}
    combined_ledger = TokenLedger()
    for mode in modes:
        reports, ledger = load_checkpoint(mode)
        meko = None
        if mode == "meko":
            meko = MekoClient(
                api_key=os.environ["MEKO_API_KEY"],
                datapack_id=os.environ["MEKO_DATAPACK_ID"],
                base_url=os.environ.get("MEKO_MCP_URL", "https://mcp.mekodata.ai/mcp"),
            )
            meko.initialize()
        llm = LLM.from_env(ledger)
        crew = Crew(llm, meko=meko, mode=mode)
        state_path = RESULTS / f"state-{mode}.json"
        if state_path.exists():
            state = json.loads(state_path.read_text())
            crew.learnings = state["learnings"]
            crew._conversations = state["conversations"]
        elif reports:
            raise RuntimeError("Reports without persisted context state: start a fresh experiment")
        crew.seed_knowledge()

        done_this_call = 0
        while len(reports) < total:
            if args.limit and done_this_call >= args.limit:
                break
            idx = len(reports) % n
            run = len(reports) // n + 1
            reports.append(crew.evaluate(candidates[idx], run))
            save_checkpoint(mode, reports, ledger, crew)
            done_this_call += 1
            print(f"[{mode}] run {run} candidate {idx + 1}/{n} done -> {reports[-1].get('verdict')}", flush=True)
        reports_by_mode[mode] = reports
        combined_ledger.records.extend(ledger.records)

    complete = all(len(reports_by_mode[m]) >= total for m in modes)
    if complete:
        out = build_results(combined_ledger, reports_by_mode, ground_truth, args.runs)
        write_results(out, str(RESULTS))
        print(json.dumps(out.get("comparison", out), indent=2))
    else:
        progress = {m: f"{len(reports_by_mode[m])}/{total}" for m in modes}
        print(json.dumps({"status": "partial", "progress": progress}, indent=2))


if __name__ == "__main__":
    main()
