"""Contingency scaffolding for a live demo. NOT part of the demo itself.

The demo makes real model calls. This module exists for the case where the
network or the model API dies mid-session, and for the case where the model
refuses to fabricate on the ungrounded path when the script needs it to.

It defaults to "off", and when off it is inert: intercept() returns None on its
first line and app/graph.py proceeds to the real model. There is exactly one
interception branch, in intercept(), and it is unreachable unless FIXTURE_MODE
is explicitly set.

Modes:
  off                 real model calls, no interception (default)
  replay              return a saved AgentState instead of calling the model
  seed_hallucination  fabricate an account number for a payee that does not
                      exist, to stand in for a model that refuses to
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys

from app.config import BASE_DIR, PAYEES_PATH

logger = logging.getLogger(__name__)

FIXTURES_DIR = BASE_DIR / "fixtures"
VALID_MODES = ("off", "replay", "seed_hallucination")


def active_mode() -> str:
    """The current fixture mode, re-read per call so the UI banner is live."""
    mode = os.getenv("FIXTURE_MODE", "off").strip().lower()
    return mode if mode in VALID_MODES else "off"


# Module-level snapshot, as specified.
FIXTURE_MODE = active_mode()


def _warn_if_active() -> None:
    mode = active_mode()
    if mode != "off":
        banner = (
            f"\n{'!' * 72}\n"
            f"!!  FIXTURE_MODE = {mode.upper()}  --  THIS IS NOT A LIVE DEMO\n"
            f"!!  Responses are replayed or synthesised, not produced by the model.\n"
            f"{'!' * 72}\n"
        )
        print(banner, file=sys.stderr, flush=True)


_warn_if_active()


def slugify(instruction: str) -> str:
    """Stable, readable filename key for an instruction."""
    slug = re.sub(r"[^a-z0-9]+", "-", (instruction or "").lower()).strip("-")[:70]
    # Short digest keeps two long instructions with the same prefix distinct.
    digest = hashlib.sha1((instruction or "").encode()).hexdigest()[:8]
    return f"{slug}-{digest}" if slug else digest


def save_fixture(state: dict) -> str:
    """Persist a real run so it can be replayed. Returns the file path."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / f"{slugify(state.get('instruction', ''))}.json"
    # context can hold large retrieved passages; keep them, they are part of
    # what made the run what it was.
    path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    logger.info("Saved fixture %s", path)
    return str(path)


def load_fixture(instruction: str) -> dict | None:
    path = FIXTURES_DIR / f"{slugify(instruction)}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Could not read fixture %s", path, exc_info=True)
        return None


def _known_payee_names() -> list[str]:
    try:
        return [p["name"] for p in json.loads(PAYEES_PATH.read_text(encoding="utf-8"))]
    except Exception:
        logger.warning("Could not read payees for fixture guard", exc_info=True)
        # Fail safe: if the guard cannot be evaluated, treat every name as real
        # so seeding cannot fire against a genuine payee.
        return []


def is_unknown_payee(name_fragment: str | None) -> bool:
    """True only when no saved payee name contains this fragment.

    Same case-insensitive substring rule as payee_lookup, so the guard cannot
    disagree with the real lookup about who exists.
    """
    if not name_fragment or not name_fragment.strip():
        return False
    names = _known_payee_names()
    if not names:
        return False
    fragment = name_fragment.strip().lower()
    return not any(fragment in n.lower() for n in names)


def _fabricated_account(name: str) -> str:
    """A plausible-looking masked account number, deterministic per name.

    Deterministic so a repeated demo shows the same invented number, which
    makes the point better than a different fake each time.
    """
    digest = hashlib.sha256(name.encode()).hexdigest()
    last4 = str(int(digest[:8], 16) % 10000).zfill(4)
    return f"XXXX XXXX {last4}"


def _seeded_state(instruction: str, customer_id: str, name_fragment: str) -> dict:
    from app.state import initial_state

    account = _fabricated_account(name_fragment)
    state = dict(initial_state(instruction, customer_id))
    state.update(
        grounded=False,          # nothing was retrieved, and nothing pretends it was
        candidates=[],
        context=[],
        resolved_payee_id=None,
        confidence=0.0,
        blocked=False,
        response=(
            f"The account number for {name_fragment} is {account}. "
            "It is a savings account held at your registered branch."
        ),
        fixture_mode="seed_hallucination",
    )
    return state


def intercept(instruction: str, customer_id: str = "CUST-1001") -> dict | None:
    """The one and only interception point.

    Returns None -- meaning "run the real graph" -- whenever FIXTURE_MODE is
    off, which is the default and the demo path.
    """
    mode = active_mode()
    if mode == "off":
        return None

    if mode == "replay":
        fixture = load_fixture(instruction)
        if fixture is not None:
            logger.warning("REPLAY: returning saved fixture for %r", instruction)
            fixture["fixture_mode"] = "replay"
            return fixture
        # Do not silently fall through to a live call: replay was chosen
        # because live calls are not available.
        from app.state import initial_state

        state = dict(initial_state(instruction, customer_id))
        state.update(
            response=(
                "No saved fixture exists for this instruction. "
                f"Capture one with: python -m app.fixtures capture \"{instruction}\""
            ),
            blocked=True,
            block_reason="missing fixture",
            fixture_mode="replay",
        )
        return state

    if mode == "seed_hallucination":
        from app.graph import parse_instruction

        fragment = parse_instruction({"instruction": instruction}).get("name_fragment")
        if is_unknown_payee(fragment):
            logger.warning("SEEDED HALLUCINATION for unknown payee %r", fragment)
            return _seeded_state(instruction, customer_id, fragment)
        # A real payee: never fabricate. Fall through to the real graph.
        logger.info("seed_hallucination not applied; %r is a known payee", fragment)
        return None

    return None


def _cli() -> int:
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "capture":
        instruction = args[1]
        if active_mode() != "off":
            print(
                f"Refusing to capture while FIXTURE_MODE={active_mode()}: a fixture "
                "must be captured from a real run.",
                file=sys.stderr,
            )
            return 2
        from app.graph import run

        state = run(instruction)
        path = save_fixture(dict(state))
        print(f"Captured -> {path}")
        print(f"  blocked={state.get('blocked')} resolved={state.get('resolved_payee_id')}")
        return 0
    print('usage: python -m app.fixtures capture "<instruction>"', file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
