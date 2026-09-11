"""The LangGraph single-agent graph.

Written against langgraph 1.2.11: StateGraph + START/END, add_conditional_edges
with an explicit path map, and .compile().

Every step is its own named function registered as its own node, so each shows
up as a distinct span in tracing. The audience is shown that span tree, so node
names are part of the deliverable, not an implementation detail.
"""

from __future__ import annotations

import json
import logging
import os
import re

from langgraph.graph import END, START, StateGraph

from app.config import get_llm
from app.guardrails import confidence_check
from app.rag import retrieve
from app.state import AgentState, initial_state
from app.telemetry import current_trace_id, get_tracer, init_telemetry
from app.tools import execute_transfer, payee_lookup
from app.verifier import verify_resolution

logger = logging.getLogger(__name__)

# Initialise tracing at module import, before any node runs, so the
# instrumentor is registered ahead of the first LangChain call.
init_telemetry()

# The span name shown to an audience for the disambiguation step.
DISAMBIGUATION_SPAN = "skill.payee_disambiguation"
ANSWER_SPAN = "skill.answer_question"

# An instruction that asks something rather than ordering a payment.
_QUESTION_RE = re.compile(
    r"^\s*(what|which|who|whose|when|where|how|is|are|does|do|did|can|could|"
    r"tell me|show me|give me)\b",
    re.IGNORECASE,
)


def _is_question(text: str) -> bool:
    return "?" in (text or "") or bool(_QUESTION_RE.match(text or ""))


def _multi_agent_enabled() -> bool:
    """Read per call, so the UI toggle applies to the next run."""
    return os.getenv("MULTI_AGENT_MODE", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )


# Module-level flag, as specified; run() re-reads the environment per call.
MULTI_AGENT_MODE = _multi_agent_enabled()

# Amount: the first number in the instruction, with thousands separators.
_AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)

# Payee name: whatever follows "to"/"for", stopping at punctuation or at a
# relative reference. "to Rajesh Kumar — same account as last time" must yield
# "Rajesh Kumar", not the whole tail, or the lookup returns nothing.
_NAME_RE = re.compile(
    r"\b(?:to|for)\s+(.+?)"
    r"(?=\s*[—–\-,;:.?!]|\s+same\b|\s+as\s+usual\b|\s+the\s+usual\b|\s+like\s+before\b|$)",
    re.IGNORECASE,
)


# --- nodes -------------------------------------------------------------


def parse_instruction(state: AgentState) -> dict:
    """Pull the payee name fragment and the amount out of the instruction."""
    text = state.get("instruction", "") or ""

    amount = None
    m = _AMOUNT_RE.search(text)
    if m:
        try:
            amount = float(m.group(1).replace(",", ""))
        except ValueError:
            amount = None

    fragment = None
    m = _NAME_RE.search(text)
    if m:
        fragment = m.group(1).strip(" .,;:!?\"'")

    logger.debug("parsed fragment=%r amount=%r", fragment, amount)
    return {"name_fragment": fragment, "amount": amount}


def lookup_candidates(state: AgentState) -> dict:
    """Find every saved payee whose name matches the fragment."""
    fragment = state.get("name_fragment")
    if not fragment:
        return {"candidates": []}
    candidates = payee_lookup.invoke(
        {"name_fragment": fragment, "customer_id": state["customer_id"]}
    )
    logger.debug("lookup %r -> %d candidates", fragment, len(candidates))
    return {"candidates": candidates}


def retrieve_context(state: AgentState) -> dict:
    """Retrieve customer-master passages and record whether we are grounded."""
    query = state.get("instruction", "")
    if state.get("name_fragment"):
        query = f"{state['name_fragment']} account details"
    context = retrieve(query, k=4)
    # grounded is a factual report of whether context was retrieved, never an
    # assumption -- the ungrounded path depends on this being honest.
    return {"context": context, "grounded": bool(context)}


def resolve_payee(state: AgentState) -> dict:
    """Ask the model to pick exactly one payee_id from the candidate list."""
    candidates = state.get("candidates") or []
    if not candidates:
        return {"resolved_payee_id": None}

    valid_ids = [c["payee_id"] for c in candidates]

    prompt = {
        "instruction": state.get("instruction", ""),
        "candidates": [
            {
                "payee_id": c.get("payee_id"),
                "name": c.get("name"),
                "account_last4": c.get("account_last4"),
                "is_joint": c.get("is_joint"),
                "last_transfer_date": c.get("last_transfer_date"),
            }
            for c in candidates
        ],
        "context": [c.get("content", "") for c in (state.get("context") or [])],
    }
    system = (
        "You resolve a bank transfer instruction to exactly one saved payee. "
        "Choose the single payee_id the customer most likely meant. "
        "You must choose from the candidate list and nothing else.\n"
        'Reply with ONLY JSON: {"payee_id": "<one id from the list>"}'
    )

    chosen = None
    try:
        # run_name is what puts the audience-facing span name on this step.
        llm = get_llm().with_config(
            {"run_name": DISAMBIGUATION_SPAN, "tags": ["disambiguation"]}
        )
        reply = llm.invoke(
            [("system", system), ("human", json.dumps(prompt, indent=2))]
        )
        raw = getattr(reply, "content", reply)
        if isinstance(raw, list):
            raw = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in raw
            )
        raw = str(raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            chosen = json.loads(match.group(0)).get("payee_id")
        else:  # model replied with a bare id
            chosen = raw.strip().strip('"')
    except Exception:
        logger.warning("resolve_payee model call failed", exc_info=True)

    if chosen not in valid_ids:
        if chosen is not None:
            logger.warning("model returned %r, not in candidates", chosen)
        # Only fall back when there is genuinely nothing to choose between.
        # With several candidates we leave this unresolved rather than guess;
        # the confidence gate then blocks, which is the safe outcome.
        chosen = valid_ids[0] if len(valid_ids) == 1 else None

    return {"resolved_payee_id": chosen}


def confidence_gate(state: AgentState) -> dict:
    """Run the two-layer guardrail and decide whether execution may proceed."""
    checked = confidence_check(dict(state))
    return {
        "confidence": checked.get("confidence", 0.0),
        "blocked": checked.get("blocked", False),
        "block_reason": checked.get("block_reason"),
        "judge": checked.get("judge"),
        "structural_reasons": checked.get("structural_reasons", []),
        "guardrails_enabled": checked.get("guardrails_enabled", True),
    }


def execute(state: AgentState) -> dict:
    """Send the transfer. Only reachable when the gate did not block."""
    payee_id = state.get("resolved_payee_id")
    if not payee_id:
        # Defence in depth: never call the payment tool without a payee.
        return {"transfer": None}
    result = execute_transfer.invoke(
        {
            "payee_id": payee_id,
            "amount": state.get("amount") or 0.0,
            "customer_id": state["customer_id"],
        }
    )
    return {"transfer": result}


def _answer_question(state: AgentState) -> str:
    """Answer an informational question with a real model call.

    This is where grounding visibly matters. With retrieval on, the model is
    given customer-master passages and told to answer only from them. With
    retrieval off there are no passages and no source constraint -- which is
    what an ungrounded assistant actually is, and why it may invent an account
    number rather than admit it has no record.

    Nothing here fabricates on purpose. Whether the model invents or refuses is
    the model's own behaviour, which is exactly what the demo is showing.
    """
    context = state.get("context") or []
    if context:
        system = (
            "You are a bank assistant answering a customer's question about "
            "their saved payees. Answer ONLY from the reference passages "
            "below. If they do not contain the answer, say you have no record "
            "of that payee. Never guess an account number.\n\n"
            "Reference passages:\n"
            + "\n---\n".join(c.get("content", "") for c in context)
        )
    else:
        system = (
            "You are a bank assistant answering a customer's question about "
            "their saved payees."
        )
    try:
        llm = get_llm().with_config(
            {"run_name": ANSWER_SPAN, "tags": ["answer", "grounded" if context else "ungrounded"]}
        )
        reply = llm.invoke([("system", system), ("human", state.get("instruction", ""))])
        raw = getattr(reply, "content", reply)
        if isinstance(raw, list):
            raw = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in raw
            )
        return str(raw).strip()
    except Exception:
        logger.warning("answer_question call failed", exc_info=True)
        return "I could not answer that question."


def compose_response(state: AgentState) -> dict:
    """Write the final user-facing message."""
    # Informational questions get a real answer; payment instructions get a
    # deterministic confirmation or refusal.
    if _is_question(state.get("instruction", "")) and not state.get("transfer"):
        return {"response": _answer_question(state)}

    by_id = {c["payee_id"]: c for c in (state.get("candidates") or [])}
    payee = by_id.get(state.get("resolved_payee_id") or "")
    name = payee["name"] if payee else state.get("resolved_payee_id")

    if state.get("blocked"):
        text = (
            "I have not made this transfer. "
            + (state.get("block_reason") or "The instruction was ambiguous.")
            + " Please confirm which payee you meant."
        )
    elif state.get("transfer"):
        t = state["transfer"]
        text = (
            f"Transferred {t['amount']:,.2f} to {name} ({t['payee_id']}). "
            f"Reference {t['reference']}."
        )
    elif not state.get("candidates"):
        fragment = state.get("name_fragment") or "that payee"
        text = (
            f"I could not find a saved payee matching \"{fragment}\". "
            "No transfer was made."
        )
    else:
        text = "I could not determine which payee you meant. No transfer was made."

    return {"response": text}


def verify(state: AgentState) -> dict:
    """Second agent: independently re-check the resolution before execution.

    Only reachable in multi-agent mode, and only on the path the confidence gate
    already allowed -- there is nothing to verify about a blocked transfer.
    """
    # An explicit child span for the handoff itself. The node span is created by
    # the OpenInference callback handler and is not the current span inside this
    # function body, so attributes set on trace.get_current_span() here would be
    # silently dropped. Opening our own span is what makes the handoff visible.
    with get_tracer().start_as_current_span("agent_handoff") as span:
        result = verify_resolution(dict(state))
        try:
            span.set_attribute("handoff.from", "resolve_payee")
            span.set_attribute("handoff.to", "verify")
            span.set_attribute(
                "handoff.agent1_choice", str(state.get("resolved_payee_id"))
            )
            span.set_attribute(
                "handoff.agent2_choice", str(result.get("verifier_choice"))
            )
            span.set_attribute("handoff.agrees", bool(result.get("agrees")))
        except Exception:
            pass

    if result.get("agrees"):
        return {"verification": result}

    proposed = state.get("resolved_payee_id")
    choice = result.get("verifier_choice")
    by_id = {c["payee_id"]: c for c in (state.get("candidates") or [])}

    def label(pid):
        c = by_id.get(pid or "")
        return f"{c['name']} ({pid})" if c else (pid or "no payee")

    reason = (
        "The two agents disagreed. The resolving agent chose "
        f"{label(proposed)}; the independent verifier chose {label(choice)}. "
        f"Verifier's reasoning: {result.get('rationale')} "
        "No transfer was made."
    )
    return {"verification": result, "blocked": True, "block_reason": reason}


def _route_after_verify(state: AgentState) -> str:
    return "blocked" if state.get("blocked") else "allowed"


# --- wiring ------------------------------------------------------------


def _route_after_gate(state: AgentState) -> str:
    """Blocked instructions skip execution entirely."""
    return "blocked" if state.get("blocked") else "allowed"


# One compiled graph per mode. Compiling per run is wasteful, but a single
# cached graph could not switch topology, and the UI toggles mode between runs.
_compiled: dict[bool, object] = {}


def build_graph(multi_agent: bool | None = None):
    """Build and compile the graph for the given mode (cached).

    In single-agent mode the topology is exactly as it was before the verifier
    existed -- no verify node at all, so its traces stay clean for comparison.
    """
    if multi_agent is None:
        multi_agent = _multi_agent_enabled()
    if multi_agent in _compiled:
        return _compiled[multi_agent]

    builder = StateGraph(AgentState)
    builder.add_node("parse_instruction", parse_instruction)
    builder.add_node("lookup_candidates", lookup_candidates)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("resolve_payee", resolve_payee)
    builder.add_node("confidence_gate", confidence_gate)
    builder.add_node("execute", execute)
    builder.add_node("compose_response", compose_response)
    if multi_agent:
        builder.add_node("verify", verify)

    builder.add_edge(START, "parse_instruction")
    builder.add_edge("parse_instruction", "lookup_candidates")
    builder.add_edge("lookup_candidates", "retrieve_context")
    builder.add_edge("retrieve_context", "resolve_payee")
    builder.add_edge("resolve_payee", "confidence_gate")
    if multi_agent:
        # confidence_gate -> verify -> execute, so the verifier sits between
        # the gate and execution exactly as specified.
        builder.add_conditional_edges(
            "confidence_gate",
            _route_after_gate,
            {"blocked": "compose_response", "allowed": "verify"},
        )
        builder.add_conditional_edges(
            "verify",
            _route_after_verify,
            {"blocked": "compose_response", "allowed": "execute"},
        )
    else:
        builder.add_conditional_edges(
            "confidence_gate",
            _route_after_gate,
            {"blocked": "compose_response", "allowed": "execute"},
        )
    builder.add_edge("execute", "compose_response")
    builder.add_edge("compose_response", END)

    _compiled[multi_agent] = builder.compile()
    return _compiled[multi_agent]


def run(instruction: str, customer_id: str = "CUST-1001") -> AgentState:
    """Run one instruction end to end and return the final state.

    The whole run is wrapped in a single root span, so every node, LLM call and
    tool call hangs off one trace the UI can link to. The trace id is read from
    inside that span -- outside it there is no active context and it would
    always be None.
    """
    # Contingency interception. Returns None when FIXTURE_MODE is off (the
    # default), so the real path below is untouched in normal operation.
    from app import fixtures

    replayed = fixtures.intercept(instruction, customer_id)
    if replayed is not None:
        return replayed

    graph = build_graph(_multi_agent_enabled())
    tracer = get_tracer()
    with tracer.start_as_current_span("payee_demo.run") as span:
        try:
            span.set_attribute("payee_demo.instruction", instruction)
            span.set_attribute("payee_demo.customer_id", customer_id)
        except Exception:  # a no-op span when telemetry is off
            pass
        state = initial_state(instruction, customer_id)
        # Seeded before invoke so it survives regardless of which nodes run.
        state["trace_id"] = current_trace_id()
        return graph.invoke(state)


if __name__ == "__main__":  # pragma: no cover
    import sys

    state = run(sys.argv[1] if len(sys.argv) > 1 else "Transfer 50,000 to Rajesh Kumar Verma")
    print(json.dumps({k: v for k, v in state.items() if k != "context"}, indent=2, default=str))
