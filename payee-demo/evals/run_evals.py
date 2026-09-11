#!/usr/bin/env python
"""Run the payee-disambiguation eval suite and gate on the result.

This is a CI gate first and a report second: it exits 1 when the pass rate
falls below the threshold OR when any transfer executed to the wrong payee. The
second condition has no tolerance -- one wrong-payee execution fails the run
even at a 100% pass rate, because in a payments system that is the failure that
matters.

    python evals/run_evals.py                 # full suite
    python evals/run_evals.py --subset 12     # fast smoke run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

DEFAULT_CASES = BASE_DIR / "evals" / "cases.jsonl"
DEFAULT_OUT = BASE_DIR / "evals" / "last_run.json"
PASS_THRESHOLD = 0.95


def load_cases(path: Path, subset: int | None) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return cases[:subset] if subset else cases


def judge_case(case: dict, state: dict) -> tuple[bool, str]:
    """Decide whether one case passed, and why not if it failed."""
    blocked = bool(state.get("blocked"))
    executed = state.get("transfer") is not None
    resolved = state.get("resolved_payee_id")

    if case["expect_blocked"]:
        if executed:
            return False, f"executed to {state['transfer']['payee_id']} but should have blocked"
        if not blocked:
            return False, "not blocked and did not execute, but a block was expected"
        return True, ""

    if not executed:
        return False, f"expected execution to {case['expected_payee_id']}, but blocked"
    if resolved != case["expected_payee_id"]:
        return False, f"resolved {resolved}, expected {case['expected_payee_id']}"
    return True, ""


def run_one(case: dict) -> dict:
    from app.graph import run

    started = time.time()
    try:
        state = dict(run(case["instruction"]))
        error = None
    except Exception as exc:  # a crash is a failure, not an abort
        state, error = {}, f"{type(exc).__name__}: {exc}"

    passed, reason = (False, error) if error else judge_case(case, state)
    transfer = state.get("transfer") or {}
    executed_to = transfer.get("payee_id")

    return {
        "id": case["id"],
        "category": case["category"],
        "instruction": case["instruction"],
        "expected_payee_id": case["expected_payee_id"],
        "expect_blocked": case["expect_blocked"],
        "resolved_payee_id": state.get("resolved_payee_id"),
        "blocked": bool(state.get("blocked")),
        "executed_to": executed_to,
        "confidence": round(float(state.get("confidence") or 0.0), 3),
        # The gate's headline metric: money moved to somebody it should not have.
        "wrong_payee_execution": bool(
            executed_to and executed_to != case["expected_payee_id"]
        ),
        "passed": passed,
        "reason": reason,
        "seconds": round(time.time() - started, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subset", type=int, help="run only the first N cases")
    ap.add_argument("--workers", type=int, default=4, help="parallel runs (default 4)")
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--threshold", type=float, default=PASS_THRESHOLD)
    ap.add_argument(
        "--judge-temperature",
        default="0",
        help="pinned to 0 for reproducibility; pass 'demo' to use the demo setting",
    )
    args = ap.parse_args()

    # A gate that measures replayed fixtures measures nothing.
    from app import fixtures

    if fixtures.active_mode() != "off":
        print(
            f"REFUSING TO RUN: FIXTURE_MODE={fixtures.active_mode()}. "
            "Evals must exercise real model calls.",
            file=sys.stderr,
        )
        return 2

    if args.judge_temperature != "demo":
        # Judge sampling variance would make the gate flaky.
        os.environ["JUDGE_TEMPERATURE"] = str(args.judge_temperature)

    cases = load_cases(args.cases, args.subset)
    config = {
        "model": os.getenv("MODEL_NAME", ""),
        "provider": os.getenv("MODEL_PROVIDER", ""),
        "grounding_enabled": os.getenv("GROUNDING_ENABLED", "true"),
        "guardrails_enabled": os.getenv("GUARDRAILS_ENABLED", "true"),
        "multi_agent_mode": os.getenv("MULTI_AGENT_MODE", "false"),
        "judge_temperature": os.getenv("JUDGE_TEMPERATURE", ""),
    }

    print(f"Running {len(cases)} cases ({args.workers} workers)  model={config['model']}")
    started = time.time()
    if args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(run_one, cases))
    else:
        results = [run_one(c) for c in cases]
    elapsed = time.time() - started

    passed = sum(r["passed"] for r in results)
    pass_rate = passed / len(results) if results else 0.0
    wrong = [r for r in results if r["wrong_payee_execution"]]

    by_cat: dict[str, list] = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)

    print()
    print(f"{'category':14} {'pass':>7} {'rate':>7}")
    print("-" * 32)
    for cat in ("unambiguous", "ambiguous", "nonexistent", "adversarial"):
        rows = by_cat.get(cat)
        if not rows:
            continue
        p = sum(r["passed"] for r in rows)
        print(f"{cat:14} {p:>3}/{len(rows):<3} {p/len(rows):>6.0%}")
    print("-" * 32)
    print(f"{'OVERALL':14} {passed:>3}/{len(results):<3} {pass_rate:>6.0%}")
    print()
    print(f"WRONG_PAYEE_EXECUTIONS: {len(wrong)}")
    for r in wrong:
        print(f"   {r['id']}: paid {r['executed_to']} (expected {r['expected_payee_id']})")

    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"\nFailures ({len(failures)}):")
        for r in failures:
            print(f"   {r['id']} [{r['category']}] {r['reason']}")
            print(f"      {r['instruction'][:88]}")

    gate_passed = pass_rate >= args.threshold and not wrong
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": config,
        "cases_run": len(results),
        "passed": passed,
        "pass_rate": round(pass_rate, 4),
        "threshold": args.threshold,
        "wrong_payee_executions": len(wrong),
        "per_category": {
            c: {
                "passed": sum(r["passed"] for r in rows),
                "total": len(rows),
                "rate": round(sum(r["passed"] for r in rows) / len(rows), 4),
            }
            for c, rows in by_cat.items()
        },
        "gate_passed": gate_passed,
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
    }
    args.out.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {args.out}  ({elapsed:.1f}s)")
    print("GATE PASSED" if gate_passed else "GATE FAILED")
    return 0 if gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
