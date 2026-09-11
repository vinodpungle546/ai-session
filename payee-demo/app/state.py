"""Shared state for the payee-disambiguation graph.

The first block is the state contract as originally specified. The second block
adds fields that the nodes in app/graph.py genuinely produce.

That addition is not optional. LangGraph 1.2 *silently discards* any key a node
returns that is not declared in the schema -- it does not raise. So an
under-declared state would drop the judge's rationale and the retrieved context
on the floor with no error, and the UI would simply show nothing.
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict):
    # --- as specified ---
    instruction: str
    customer_id: str
    amount: float | None
    candidates: list[dict]
    resolved_payee_id: str | None
    confidence: float
    grounded: bool
    blocked: bool
    block_reason: str | None
    verification: dict | None   # reserved for the Prompt 7 verifier agent
    response: str
    trace_id: str | None

    # --- required by the nodes described in the same prompt ---
    # parse_instruction "extracts payee name fragment ... into state"
    name_fragment: str | None
    # retrieve_context "adds context"
    context: list[dict]

    # --- required by the two-layer guardrail ---
    # The LLM judge's full response: confidence, rationale, competing ids.
    # The audience reads this text on screen, so it must survive the graph.
    judge: dict | None
    # The deterministic layer's reasons, shown next to the judge's rationale.
    structural_reasons: list[str]
    # False when the guardrail was switched off, so the UI can distinguish
    # "confidence 0.00" from "confidence was never measured".
    guardrails_enabled: bool

    # Result of execute_transfer, so the UI can show the reference number.
    transfer: dict | None


def initial_state(instruction: str, customer_id: str = "CUST-1001") -> AgentState:
    """A fully populated starting state, so no node has to guess a default."""
    return AgentState(
        instruction=instruction,
        customer_id=customer_id,
        amount=None,
        candidates=[],
        resolved_payee_id=None,
        confidence=0.0,
        grounded=False,
        blocked=False,
        block_reason=None,
        verification=None,
        response="",
        trace_id=None,
        name_fragment=None,
        context=[],
        judge=None,
        structural_reasons=[],
        guardrails_enabled=True,
        transfer=None,
    )
