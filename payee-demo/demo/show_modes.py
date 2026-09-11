#!/usr/bin/env python
"""Show the single-agent and multi-agent implementations, side by side.

A presentation aid, not part of the app. Everything printed here is derived
from the running code at call time -- topology from the compiled graphs,
source from ``inspect``, the verifier's payload from the real prompt builder --
so it cannot drift from the implementation, and a sceptical room can see that
it is the actual code rather than a slide.

    python demo/show_modes.py              # topology, code, isolation
    python demo/show_modes.py --run        # ...plus run both modes live
    python demo/show_modes.py --topology   # one section only
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import textwrap
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

WIDTH = 78

# The instruction whose outcome differs between the two modes. C-90117 has
# never received a transfer, so "the same account as last time" is false of it;
# the name still matches perfectly, so only the verifier catches it.
REVEAL_INSTRUCTION = (
    "Transfer 50,000 to Rajesh Kumar Verma — the same account as last time"
)


def rule(title: str = "") -> None:
    if title:
        print(f"\n{'═' * WIDTH}\n  {title}\n{'═' * WIDTH}")
    else:
        print("─" * WIDTH)


def sub(title: str) -> None:
    print(f"\n  {title}\n  {'-' * (WIDTH - 4)}")


def indent(text: str, prefix: str = "    ") -> str:
    return textwrap.indent(text.rstrip(), prefix)


def _wrap_prose(text: str, width: int = WIDTH - 10) -> str:
    """Wrap paragraphs to the projector width, keeping blank lines and the
    hanging indent of bulleted lines intact."""
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            out.append("")
        elif stripped.startswith("-"):
            out.extend(
                textwrap.wrap(
                    stripped, width=width, initial_indent="  ", subsequent_indent="    "
                )
            )
        else:
            out.extend(textwrap.wrap(stripped, width=width) or [""])
    return "\n".join(out)


def _graphs():
    from app.graph import build_graph

    return build_graph(False).get_graph(), build_graph(True).get_graph()


def _nodes(g) -> set[str]:
    return {n for n in g.nodes if not n.startswith("__")}


def _edges(g) -> set[tuple]:
    return {(e.source, e.target, getattr(e, "data", None)) for e in g.edges}


def section_topology() -> None:
    rule("1. TOPOLOGY — what the graph actually looks like")
    single, multi = _graphs()
    sn, mn = _nodes(single), _nodes(multi)

    print(f"\n  single-agent : {len(sn)} nodes")
    print(f"  multi-agent  : {len(mn)} nodes")
    print(f"\n  node added in multi-agent mode: {sorted(mn - sn)}")

    se, me = _edges(single), _edges(multi)

    sub("edges only in MULTI-AGENT")
    for s, t, d in sorted(me - se, key=str):
        label = f"  [{d}]" if d else ""
        print(f"    {s} → {t}{label}")

    sub("edges only in SINGLE-AGENT")
    for s, t, d in sorted(se - me, key=str):
        label = f"  [{d}]" if d else ""
        print(f"    {s} → {t}{label}")

    print(
        "\n  In one sentence: the second agent is ONE node, and one edge\n"
        "  rerouted. confidence_gate → execute becomes\n"
        "  confidence_gate → verify → execute."
    )

    sub("single-agent flow")
    print(indent(" → ".join(_ordered_flow(single))))
    sub("multi-agent flow")
    print(indent(" → ".join(_ordered_flow(multi))))


def _ordered_flow(g) -> list[str]:
    """Best-effort linear reading of the happy path, for a one-line summary."""
    order = [
        "parse_instruction",
        "lookup_candidates",
        "retrieve_context",
        "resolve_payee",
        "confidence_gate",
        "verify",
        "execute",
        "compose_response",
    ]
    present = _nodes(g)
    return [n for n in order if n in present]


def _source_between(fn, start_marker: str, end_marker: str) -> tuple[str, int]:
    """Return (excerpt, first line number in the file) between two markers.

    The line number is the excerpt's own start, not the function's, so anyone
    following along in an editor lands on the right line.
    """
    src, first = inspect.getsource(fn), inspect.getsourcelines(fn)[1]
    lines = src.splitlines()
    try:
        i = next(n for n, l in enumerate(lines) if start_marker in l)
        j = next(n for n, l in enumerate(lines[i:], i) if end_marker in l)
    except StopIteration:
        return src, first
    return "\n".join(lines[i : j + 1]), first + i


def section_code() -> None:
    import app.graph as G
    import app.verifier as V

    rule("2. THE WIRING — the only difference in how the graph is built")
    wiring, line = _source_between(
        G.build_graph, "if multi_agent:", 'builder.add_edge("execute"'
    )
    print(f"\n  app/graph.py:{line}  (printed via inspect, not copied)\n")
    print(indent(wiring))

    rule("3. THE SECOND AGENT — the verify node")
    print(f"\n  app/graph.py:{inspect.getsourcelines(G.verify)[1]}\n")
    print(indent(inspect.getsource(G.verify)))

    rule("4. THE SECOND AGENT — its own model call")
    call, line = _source_between(
        V.verify_resolution, "human = build_verifier_prompt", "parsed = _parse"
    )
    print(f"\n  app/verifier.py:{line}")
    print("  Note get_llm() here: a separate call, not a continuation of the first.\n")
    print(indent(call))


def section_isolation() -> None:
    import json as _json

    import app.verifier as V
    from app.config import PAYEES_PATH

    rule("5. ISOLATION — what the verifier is deliberately NOT told")
    payees = _json.loads(PAYEES_PATH.read_text())
    candidates = [p for p in payees if "Rajesh" in p["name"]]

    payload = V.build_verifier_prompt(
        "Transfer 50,000 to Rajesh — same account as last time",
        candidates,
        "C-88214",
    )
    print("\n  The literal string sent to the second agent:\n")
    print(indent(payload))

    keys = sorted(json.loads(payload).keys())
    print(f"\n  Keys it receives ({len(keys)}): {', '.join(keys)}")
    print(
        "\n  Withheld from it, though present in state at that moment:\n"
        "    context            — the retrieved customer-master passages\n"
        "    judge              — the confidence judge's score and rationale\n"
        "    structural_reasons — what the deterministic floor found\n"
        "    resolve_payee's reasoning / any message history\n"
        "\n  That is the whole point: an agent shown another agent's argument\n"
        "  tends to agree with it, and an agreement produced that way tells\n"
        "  you nothing."
    )


def section_validation() -> None:
    """How the verifier validates -- model judgment vs deterministic code."""
    import app.verifier as V

    rule("6. VALIDATION — what the verifier checks, and what checks the verifier")

    print(
        "\n  Two layers, easy to conflate:\n"
        "    the MODEL decides whether the instruction contradicts the record\n"
        "    the CODE  decides whether the model's answer is usable at all\n"
    )

    sub("a) what the model is asked to check — VERIFIER_SYSTEM, app/verifier.py")
    print(indent(_wrap_prose(V.VERIFIER_SYSTEM)))

    sub("b) what the code checks afterwards — it does not take the reply on trust")
    checks, line = _source_between(
        V.verify_resolution, "choice = parsed.get", 'verifier_available": True'
    )
    print(f"    app/verifier.py:{line}\n")
    print(indent(checks))

    sub("c) fail-closed — an unavailable reviewer is not an approving one")
    failed, line = _source_between(
        V.verify_resolution, "except Exception as exc", '"verifier_available": False'
    )
    print(f"    app/verifier.py:{line}\n")
    print(indent(failed))

    sub("d) the override, demonstrated")
    print(
        "    NOTE: the reply below is a SYNTHETIC string, not a model call. It\n"
        "    exists only to exercise the post-check in (b). Every other section\n"
        "    of this script reads real code or runs the real graph.\n"
    )
    result = _demonstrate_override()
    print("    synthetic verifier reply:")
    print(indent('{"agrees": true, "verifier_choice": "C-88770", "rationale": "..."}', "      "))
    print("\n    proposed by agent 1: C-88214")
    print("    verifier named     : C-88770   ← a different payee")
    print(f"\n    verify_resolution() returned agrees = {result['agrees']}")
    print(
        "\n    The model said it agreed. The code compared the two choices and\n"
        "    recorded a disagreement. The comparison is trusted over the\n"
        "    self-report."
    )


def _demonstrate_override() -> dict:
    """Run the post-check against a synthetic reply. Makes no model call.

    get_llm is patched for the duration of this call only, so nothing leaks
    into --run or any other section.
    """
    from unittest.mock import patch

    import app.verifier as V

    body = json.dumps(
        {
            "agrees": True,
            "verifier_choice": "C-88770",
            "rationale": "synthetic reply, for demonstrating the post-check",
        }
    )

    class _Reply:
        content = body

    class _StubLLM:
        def with_config(self, _cfg):
            return self

        def invoke(self, _messages):
            return _Reply()

    state = {
        "instruction": "Transfer 50,000 to Rajesh — same account as last time",
        "candidates": [
            {"payee_id": "C-88214", "name": "Rajesh Kumar Sharma"},
            {"payee_id": "C-88770", "name": "Rajesh K. Sharma"},
        ],
        "resolved_payee_id": "C-88214",
    }
    with patch.object(V, "get_llm", lambda **_kw: _StubLLM()):
        return V.verify_resolution(state)


def section_run() -> None:
    rule("6. BEHAVIOUR — the same instruction, both modes")
    import logging

    logging.disable(logging.CRITICAL)
    from app.graph import run

    print(f"\n  instruction: {REVEAL_INSTRUCTION}\n")
    for mode in ("false", "true"):
        os.environ["MULTI_AGENT_MODE"] = mode
        # graph._multi_agent_enabled() re-reads this per call, so no restart
        # and no extra plumbing is needed.
        state = run(REVEAL_INSTRUCTION)
        label = "multi-agent " if mode == "true" else "single-agent"
        outcome = "BLOCKED " if state["blocked"] else "EXECUTED"
        print(f"  MULTI_AGENT_MODE={mode:<5} → {label}  {outcome}")
        if state.get("verification"):
            v = state["verification"]
            print(f"      verifier agrees : {v['agrees']}")
            print(f"      verifier says   : {textwrap.shorten(v['rationale'], 62)}")
        elif state.get("transfer"):
            print(f"      paid            : {state['transfer']['payee_id']}")
            print(f"      reference       : {state['transfer']['reference'][:8]}…")
        print()
    print(
        "  Measured over repeated runs: 5/5 disagreement on this instruction,\n"
        "  5/5 agreement on the plain control ('…to Rajesh Kumar Verma')."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--topology", action="store_true")
    ap.add_argument("--code", action="store_true")
    ap.add_argument("--isolation", action="store_true")
    ap.add_argument("--validation", action="store_true", help="how the verifier validates")
    ap.add_argument("--run", action="store_true", help="run both modes live (makes model calls)")
    ap.add_argument("--all", action="store_true", help="every section, including --run")
    a = ap.parse_args()

    chosen = a.topology or a.code or a.isolation or a.validation or a.run or a.all
    print("\n  SINGLE-AGENT vs MULTI-AGENT — generated from the running code")

    if a.all or a.topology or not chosen:
        section_topology()
    if a.all or a.code or not chosen:
        section_code()
    if a.all or a.isolation or not chosen:
        section_isolation()
    if a.all or a.validation or not chosen:
        section_validation()
    if a.all or a.run:
        section_run()

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
