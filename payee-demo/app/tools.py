"""Tools the payee-disambiguation agent can call.

Three are LangChain tools the model may invoke on its own; ``get_transfer_history``
is a plain function the graph calls directly, because reading history is never a
decision the model should make.

The JSON files are read once at import and then treated as read-only. Every
accessor returns copies, so a caller mutating a returned record cannot corrupt
the in-memory dataset for subsequent runs — the demo runs many instructions in
one Streamlit process.
"""

from __future__ import annotations

import json
import uuid

from langchain_core.tools import tool

from app.config import PAYEES_PATH, TRANSFER_HISTORY_PATH

# --- Data loaded once at import ----------------------------------------
with open(PAYEES_PATH, encoding="utf-8") as fh:
    _PAYEES: list[dict] = json.load(fh)

with open(TRANSFER_HISTORY_PATH, encoding="utf-8") as fh:
    _TRANSFERS: list[dict] = json.load(fh)

# Transfer records carry only a payee_id, so ownership is resolved through the
# payee list rather than stored on each transfer.
_PAYEE_OWNER: dict[str, str] = {p["payee_id"]: p["owner_customer_id"] for p in _PAYEES}

# The demo has no ledger; a fixed balance keeps runs comparable.
AVAILABLE_BALANCE = 250000.0
CURRENCY = "INR"


@tool
def payee_lookup(name_fragment: str, customer_id: str) -> list[dict]:
    """Find saved payees for a customer whose name contains the given text.

    Use this to turn a name mentioned in a transfer instruction into concrete
    payee records before deciding who to pay. The match is a case-insensitive
    substring match, so a partial name such as "Rajesh" will return every payee
    whose name contains it — often more than one. Returning several records is
    the normal, expected outcome and means the instruction is ambiguous; it is
    not an error and must not be resolved by guessing.

    Args:
        name_fragment: All or part of the payee's name, as written in the
            instruction.
        customer_id: The customer whose payee list should be searched, e.g.
            "CUST-1001". Payees belonging to other customers are never returned.

    Returns:
        A list of full payee records, each containing payee_id, name,
        account_last4, is_joint, last_transfer_date and owner_customer_id.
        Returns an empty list if no payee matches, which means the payee is not
        saved for this customer.
    """
    fragment = (name_fragment or "").strip().lower()
    if not fragment:
        return []
    return [
        dict(p)
        for p in _PAYEES
        if p["owner_customer_id"] == customer_id and fragment in p["name"].lower()
    ]


@tool
def balance_check(customer_id: str) -> dict:
    """Check the funds currently available to a customer before a transfer.

    Use this to confirm a transfer amount can be covered. It reports available
    funds only; it does not reserve or move money.

    Args:
        customer_id: The customer to check, e.g. "CUST-1001".

    Returns:
        A dict with customer_id, available_balance (a float) and currency.
    """
    return {
        "customer_id": customer_id,
        "available_balance": AVAILABLE_BALANCE,
        "currency": CURRENCY,
    }


@tool
def execute_transfer(payee_id: str, amount: float, customer_id: str) -> dict:
    """Send money to one specific, already-identified payee. Irreversible.

    Only call this once exactly one payee_id has been established. Never call it
    to "try" a payee, and never call it while more than one candidate matches the
    instruction — resolve the ambiguity first, or stop and ask the customer.

    Args:
        payee_id: The exact identifier of the payee to pay, e.g. "C-90117".
            This must come from payee_lookup, never from memory.
        amount: The amount to transfer.
        customer_id: The customer sending the funds, e.g. "CUST-1001".

    Returns:
        A dict with status, payee_id, amount and a unique reference for the
        transfer.
    """
    # Deliberately no ownership or balance validation here: the confidence gate
    # in app/guardrails.py is what decides whether execution is permitted, and
    # duplicating that check here would hide gate failures during the demo.
    return {
        "status": "executed",
        "payee_id": payee_id,
        "amount": amount,
        "reference": str(uuid.uuid4()),
    }


def get_transfer_history(customer_id: str) -> list[dict]:
    """Return the past transfers made by a customer, most recent first.

    Not a tool: the graph calls this directly when resolving relative references
    such as "the same as last time".

    Transfer records store only a payee_id, so they are attributed to a customer
    via that payee's owner_customer_id.
    """
    return sorted(
        (
            dict(t)
            for t in _TRANSFERS
            if _PAYEE_OWNER.get(t["payee_id"]) == customer_id
        ),
        key=lambda t: t["date"],
        reverse=True,
    )
