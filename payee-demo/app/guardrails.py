"""Two-layer confidence check for payee resolution.

Layer 1 is deterministic structural analysis with no model call. Layer 2 is a
real LLM judge. Both run on every request, and the two are combined by taking
the minimum -- so the judge can only ever *lower* confidence.

The asymmetry is the point. The structural layer guarantees that a structurally
ambiguous instruction is caught every single time, regardless of what the model
does on the day; the judge adds a written rationale a human can read. If the
judge is confidently wrong, the floor still blocks.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict

from app.config import get_llm

logger = logging.getLogger(__name__)

# Confidence ceiling applied whenever the structural layer finds ambiguity.
# Sits below every sane CONFIDENCE_THRESHOLD, so the floor alone is sufficient
# to block: the judge cannot talk the system into executing.
STRUCTURAL_CONFIDENCE_CAP = 0.4

# Span name for the judge's own model call. Without this it appears in traces as
# a bare "ChatOpenAI", indistinguishable from the resolver's call - and the
# judge span is one the audience is shown.
JUDGE_SPAN = "skill.confidence_judge"

DEFAULT_CONFIDENCE_THRESHOLD = 0.75

# Phrases that point at an earlier transfer instead of naming a payee outright.
RELATIVE_REFERENCE_PATTERNS = (
    "last time",
    "same as before",
    "same account as before",
    "the usual",
    "as usual",
    "like before",
    "same as last",
)

# Tokens too short or too common to identify anybody on their own.
_MIN_TOKEN_LEN = 3
_NAME_STOPWORDS = {"mr", "mrs", "ms", "dr", "shri", "smt"}


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# Module-level flag, as specified. confidence_check() re-reads the environment
# per call so the Streamlit toggle applies to the next run without a restart.
GUARDRAILS_ENABLED = _env_flag("GUARDRAILS_ENABLED")


def _threshold() -> float:
    try:
        return float(os.getenv("CONFIDENCE_THRESHOLD", DEFAULT_CONFIDENCE_THRESHOLD))
    except ValueError:
        return DEFAULT_CONFIDENCE_THRESHOLD


def _normalise(text: str) -> str:
    """Lowercase and strip punctuation so 'Rajesh K. Sharma' tokenises cleanly."""
    return re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())


def _name_tokens(name: str) -> set[str]:
    return {
        t
        for t in _normalise(name).split()
        if len(t) >= _MIN_TOKEN_LEN and t not in _NAME_STOPWORDS
    }


def _describe(candidate: dict) -> str:
    return f"{candidate.get('name')} ({candidate.get('payee_id')})"


# --- Layer 1: deterministic structural floor ---------------------------


def structural_ambiguity(instruction: str, candidates: list[dict]) -> tuple[bool, list[str]]:
    """Detect structural ambiguity without calling a model.

    Returns (is_ambiguous, reasons). Ambiguous when any of:
      - more than one candidate shares an account_last4
      - more than one candidate name plausibly matches the instruction
      - the instruction uses a relative reference ("last time", "the usual")
        and more than one candidate has ever received a transfer

    This runs identically on every request, which is what makes the block
    reproducible in front of an audience.
    """
    reasons: list[str] = []
    candidates = candidates or []
    if len(candidates) < 2:
        # One candidate cannot be ambiguous against itself, and zero candidates
        # is a lookup miss handled elsewhere.
        return False, reasons

    instruction_norm = _normalise(instruction)
    instruction_tokens = set(instruction_norm.split())

    # -- shared account ------------------------------------------------
    by_account: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        if c.get("account_last4"):
            by_account[c["account_last4"]].append(c)
    for last4, group in sorted(by_account.items()):
        if len(group) > 1:
            reasons.append(
                f"{len(group)} payees share account ending {last4}: "
                + ", ".join(_describe(c) for c in group)
            )

    # -- multiple plausible name matches --------------------------------
    plausible = [
        c
        for c in candidates
        if _normalise(c.get("name", "")).strip() in instruction_norm
        or _name_tokens(c.get("name", "")) & instruction_tokens
    ]
    if len(plausible) > 1:
        reasons.append(
            f"{len(plausible)} payee names plausibly match the instruction: "
            + ", ".join(_describe(c) for c in plausible)
        )

    # -- relative reference with more than one prior recipient -----------
    matched_phrase = next(
        (p for p in RELATIVE_REFERENCE_PATTERNS if p in instruction_norm), None
    )
    if matched_phrase:
        with_history = [c for c in candidates if c.get("last_transfer_date")]
        if len(with_history) > 1:
            reasons.append(
                f'instruction refers to "{matched_phrase}" but {len(with_history)} '
                "payees have prior transfers: "
                + ", ".join(
                    f"{_describe(c)} last paid {c['last_transfer_date']}"
                    for c in sorted(with_history, key=lambda c: c["last_transfer_date"], reverse=True)
                )
            )

    return bool(reasons), reasons


# --- Layer 2: LLM judge ------------------------------------------------

_JUDGE_SYSTEM = (
    "You are a payment risk reviewer at a bank. You are shown a customer's "
    "transfer instruction, the saved payees that match it, and the payee an "
    "automated system proposes to pay. Judge how confident you are that the "
    "proposed payee is unambiguously the one the customer meant.\n\n"
    "Be strict. If two payees could plausibly be the intended recipient - "
    "similar names, a shared account number, or a vague reference to an "
    "earlier transfer - confidence must be low. Paying the wrong person is "
    "far worse than asking the customer to confirm.\n\n"
    'Reply with ONLY a JSON object, no markdown fences and no preamble:\n'
    '{"confidence": <number 0.0-1.0>, "rationale": "<one or two sentences>", '
    '"competing_payee_ids": ["<payee_id>", ...]}'
)

_UNPARSEABLE = {
    "confidence": 0.0,
    "rationale": "judge response unparseable",
    "competing_payee_ids": [],
}


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model reply, tolerating fences and preamble."""
    cleaned = (text or "").strip()
    # Strip ```json ... ``` or ``` ... ``` fences.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Fall back to the first balanced-looking object in the text.
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("no JSON object found in judge response")


def llm_confidence_judge(
    instruction: str, candidates: list[dict], resolved_payee_id: str | None
) -> dict:
    """Ask a real LLM how confident it is in the proposed payee resolution.

    A separate named function so it shows up as its own span in tracing.

    Returns {"confidence": float, "rationale": str, "competing_payee_ids": list}.
    Never raises: a malformed reply, an unreachable model or a missing API key
    all degrade to confidence 0.0 with an explanatory rationale, because a demo
    must not crash on the judge.
    """
    payload = {
        "instruction": instruction,
        "proposed_payee_id": resolved_payee_id,
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
    }

    try:
        # A little sampling variation is deliberate: the structural floor
        # guarantees the block, so the judge is free to phrase its reasoning
        # differently each run - which is what shows an audience that a real
        # judgement is happening rather than a canned string.
        llm = get_llm(
            temperature=float(os.getenv("JUDGE_TEMPERATURE", "0.3"))
        ).with_config({"run_name": JUDGE_SPAN, "tags": ["guardrail", "judge"]})
        reply = llm.invoke(
            [
                ("system", _JUDGE_SYSTEM),
                ("human", json.dumps(payload, indent=2)),
            ]
        )
        raw = getattr(reply, "content", reply)
        if isinstance(raw, list):  # some providers return content blocks
            raw = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw
            )
    except Exception as exc:
        # Loud in the logs and visible on screen: the rationale itself says the
        # judge did not run, so a keyless demo cannot masquerade as a real one.
        logger.warning("LLM judge call failed: %s", exc, exc_info=True)
        return {
            "confidence": 0.0,
            "rationale": f"judge call failed ({type(exc).__name__}); "
            "confidence withheld and treated as zero",
            "competing_payee_ids": [],
            "judge_available": False,
        }

    try:
        parsed = _extract_json(raw if isinstance(raw, str) else str(raw))
        confidence = float(parsed.get("confidence", 0.0))
        # Clamp: a judge returning 1.5 must not defeat the threshold.
        confidence = max(0.0, min(1.0, confidence))
        competing = parsed.get("competing_payee_ids") or []
        if not isinstance(competing, list):
            competing = [str(competing)]
        return {
            "confidence": confidence,
            "rationale": str(parsed.get("rationale", "")).strip() or "no rationale given",
            "competing_payee_ids": [str(p) for p in competing],
            "judge_available": True,
        }
    except Exception as exc:
        logger.warning("Could not parse judge response: %s", exc)
        return {**_UNPARSEABLE, "judge_available": True, "raw_response": str(raw)[:500]}


# --- Combining the two layers ------------------------------------------


def confidence_check(state: dict) -> dict:
    """Apply both layers and decide whether the transfer may proceed.

    The structural layer caps confidence at 0.4 when it fires; the judge's score
    is then combined with min(). Blocking is therefore guaranteed for
    structurally ambiguous cases no matter what the judge says.
    """
    result = dict(state)
    instruction = state.get("instruction", "")
    candidates = state.get("candidates") or []
    resolved = state.get("resolved_payee_id")

    # Re-read per call so the UI toggle applies to the next run.
    if not _env_flag("GUARDRAILS_ENABLED"):
        logger.info("Guardrails disabled; skipping structural check and judge call.")
        result.update(
            blocked=False,
            block_reason=None,
            structural_reasons=[],
            judge=None,
            guardrails_enabled=False,
        )
        return result

    # 1. Deterministic floor.
    is_ambiguous, reasons = structural_ambiguity(instruction, candidates)
    cap = STRUCTURAL_CONFIDENCE_CAP if is_ambiguous else 1.0

    # 2. Real judge call. Runs on every request, including unambiguous ones,
    #    so the rationale is always available to display.
    judge = llm_confidence_judge(instruction, candidates, resolved)

    # 3. Combine. min() means the judge can lower confidence but never raise it
    #    above the structural cap.
    confidence = min(float(judge.get("confidence", 0.0)), cap)

    threshold = _threshold()
    blocked = confidence < threshold

    block_reason = None
    if blocked:
        parts: list[str] = []
        if reasons:
            parts.append("Structural check: " + "; ".join(reasons) + ".")
        rationale = (judge.get("rationale") or "").strip()
        if rationale:
            parts.append(f"Judge ({judge.get('confidence', 0.0):.2f}): {rationale}")
        # Name every payee that could have been meant, so a human can choose.
        competing = [c for c in candidates if c.get("payee_id")]
        if competing:
            parts.append(
                "Candidates: " + ", ".join(_describe(c) for c in competing) + "."
            )
        parts.append(
            f"Confidence {confidence:.2f} is below the {threshold:.2f} threshold, "
            "so no transfer was made."
        )
        block_reason = " ".join(parts)

    result.update(
        confidence=confidence,
        blocked=blocked,
        block_reason=block_reason,
        structural_ambiguous=is_ambiguous,
        structural_reasons=reasons,
        structural_cap=cap,
        judge=judge,
        guardrails_enabled=True,
    )
    return result
