"""A second, independent agent that re-checks the payee resolution.

The whole value of this agent is what it is *not* told. It receives only the
original instruction, the candidate list, and the payee the first agent
proposed. It never sees the first agent's reasoning, the retrieved context, the
guardrail's structural findings, or the judge's rationale -- because an agent
shown another agent's argument tends to agree with it, and an agreement
produced that way tells you nothing.

Build the payload with build_verifier_prompt() if you need to audit exactly what
crosses the boundary; it returns the literal string that is sent.
"""

from __future__ import annotations

import json
import logging
import os
import re

from app.config import get_llm

logger = logging.getLogger(__name__)

# Named so the second agent's call is distinguishable from the resolver's and
# the judge's in the trace. An audience is shown this handoff.
VERIFIER_SPAN = "skill.independent_verification"

VERIFIER_SYSTEM = (
    "You are a second, independent reviewer at a bank. Another system has "
    "already proposed which saved payee a transfer instruction refers to. You "
    "were deliberately not shown its reasoning.\n\n"
    "Decide for yourself which single payee the instruction means, then say "
    "whether the proposal matches your own choice. If the instruction does not "
    "identify one payee beyond doubt, disagree and set verifier_choice to null "
    "rather than picking the most likely one.\n\n"
    "Check the instruction against the candidate's own record, not just its "
    "name. Disagree if the instruction asserts something the record "
    "contradicts. For example:\n"
    "  - it refers to a previous transfer (\"same as last time\", \"the usual\") "
    "but last_transfer_date is null, so no previous transfer exists;\n"
    "  - it says the account is joint but is_joint is false, or vice versa;\n"
    "  - it names account digits that do not match account_last4.\n"
    "A name that matches is not enough if the rest of the instruction is false "
    "of that payee.\n\n"
    "Reply with ONLY a JSON object, no markdown fences and no preamble:\n"
    '{"agrees": true|false, "verifier_choice": "<payee_id or null>", '
    '"rationale": "<one or two sentences>"}'
)


def build_verifier_prompt(
    instruction: str, candidates: list[dict], resolved_payee_id: str | None
) -> str:
    """The exact human-message string sent to the verifier.

    Everything the verifier is allowed to know is assembled here and nowhere
    else, so the isolation boundary is auditable in one place.
    """
    payload = {
        "instruction": instruction,
        "candidates": [
            {
                "payee_id": c.get("payee_id"),
                "name": c.get("name"),
                "account_last4": c.get("account_last4"),
                "is_joint": c.get("is_joint"),
                "last_transfer_date": c.get("last_transfer_date"),
            }
            for c in (candidates or [])
        ],
        "proposed_payee_id": resolved_payee_id,
    }
    return json.dumps(payload, indent=2)


def _parse(raw: str) -> dict:
    cleaned = (raw or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    raise ValueError("no JSON object in verifier response")


def verify_resolution(state: dict) -> dict:
    """Independently verify the proposed resolution.

    Returns {"agrees": bool, "verifier_choice": str | None, "rationale": str}
    and also writes it into state["verification"].

    Fails closed: if the verifier cannot run or cannot be parsed, it reports
    disagreement rather than waving the transfer through. For a payments
    guardrail, an unavailable reviewer is not the same as an approving one.
    """
    instruction = state.get("instruction", "")
    candidates = state.get("candidates") or []
    proposed = state.get("resolved_payee_id")
    valid_ids = [c.get("payee_id") for c in candidates]

    # NOTE: only these three values are read from state. Do not add to this
    # call without re-reading the module docstring -- the isolation is the
    # feature, and it is easy to erode by accident.
    human = build_verifier_prompt(instruction, candidates, proposed)

    try:
        llm = get_llm(
            temperature=float(os.getenv("VERIFIER_TEMPERATURE", "0"))
        ).with_config({"run_name": VERIFIER_SPAN, "tags": ["verifier", "agent2"]})
        reply = llm.invoke([("system", VERIFIER_SYSTEM), ("human", human)])
        raw = getattr(reply, "content", reply)
        if isinstance(raw, list):
            raw = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in raw
            )
        parsed = _parse(str(raw))
    except Exception as exc:
        logger.warning("Verifier call failed: %s", exc, exc_info=True)
        result = {
            "agrees": False,
            "verifier_choice": None,
            "rationale": f"verifier unavailable ({type(exc).__name__}); "
            "treated as disagreement",
            "verifier_available": False,
        }
        state["verification"] = result
        return result

    choice = parsed.get("verifier_choice")
    if choice is not None:
        choice = str(choice)
        if choice.lower() in ("null", "none", ""):
            choice = None
        elif choice not in valid_ids:
            # A verifier naming a payee outside the candidate list has not
            # verified anything; treat it as no choice.
            logger.warning("Verifier returned unknown payee_id %r", choice)
            choice = None

    agrees = bool(parsed.get("agrees", False))
    # Trust the comparison over the model's own boolean: if it claims agreement
    # while naming a different payee, that is a disagreement.
    if choice is not None and proposed is not None and choice != proposed:
        agrees = False

    result = {
        "agrees": agrees,
        "verifier_choice": choice,
        "rationale": str(parsed.get("rationale", "")).strip() or "no rationale given",
        "verifier_available": True,
    }
    state["verification"] = result
    return result
