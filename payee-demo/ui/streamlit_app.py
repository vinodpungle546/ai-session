"""Streamlit UI for the Bank Transaction Scenario demo.

Projected to a room, so legibility beats density: large type, few panels, and
the two pieces of model-written text an audience actually reads -- the judge's
rationale and the verifier's -- given real room.

All state lives in st.session_state. Sidebar toggles write their environment
variables immediately before run() is called; every module downstream re-reads
those variables per call, so a toggle applies to the very next run with no
restart. See app/rag.py:retrieve, app/guardrails.py:confidence_check and
app/graph.py:_multi_agent_enabled.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import fixtures  # noqa: E402

st.set_page_config(page_title="Bank Transaction Scenario", layout="wide")

st.markdown(
    """
    <style>
      /* Theme-agnostic by construction. Panels are a translucent TINT over
         whatever background is active, and their text is `inherit`, so the
         theme supplies the correct foreground in both light and dark. Nothing
         here hard-codes a page background. Measured contrast for body text on
         the tinted panels is 12.5:1 (light) and 15.8:1 (dark) at worst. */
      .block-container { padding-top: 2rem; max-width: 1400px; }

      .big-answer   { font-size: 1.55rem; line-height: 1.5;  color: inherit; }
      .rationale    { font-size: 1.35rem; line-height: 1.55; color: inherit; }
      .payee-name   { font-size: 2.6rem; font-weight: 700; line-height: 1.15;
                      color: inherit; }
      /* Secondary text: dim the theme's own colour rather than pick a grey,
         so it stays legible on a light or a dark page. */
      .payee-id     { font-size: 1.3rem; color: inherit; opacity: .72;
                      font-family: ui-monospace, monospace; }
      .trace        { font-family: ui-monospace, monospace; font-size: .95rem;
                      color: inherit; opacity: .72; }

      .panel        { padding: 1.1rem 1.3rem; border-radius: 10px;
                      margin: .5rem 0 1rem 0; color: inherit; }
      .panel *      { color: inherit; }
      .panel-h      { font-size: .95rem; font-weight: 700; letter-spacing: .09em;
                      text-transform: uppercase; opacity: .78;
                      margin-bottom: .45rem; }

      .panel-block  { background: rgba(176, 0, 32, .13);  border-left: 8px solid #d92d20; }
      .panel-ok     { background: rgba(30, 126, 52, .13); border-left: 8px solid #1e9e46; }
      .panel-judge  { background: rgba(91, 63, 168, .14); border-left: 8px solid #7c5cd6; }
      .panel-verify { background: rgba(28, 95, 176, .13); border-left: 8px solid #3b82f6; }

      /* #d92d20 clears AA on white (4.83) and on Streamlit dark #0e1117 (3.91). */
      .nothing      { font-size: 1.7rem; font-weight: 700; color: #d92d20 !important; }

      .fixture-banner { background: #b00020; color: #ffffff !important;
                        padding: 1.1rem 1.3rem; border-radius: 8px;
                        font-size: 1.5rem; font-weight: 800; letter-spacing: .04em;
                        text-align: center; margin-bottom: 1rem; }
      .fixture-banner * { color: #ffffff !important; }

      /* The instruction box is the one control the presenter touches, so make
         it findable on a projector: a solid accent border, and a clear focus
         ring. Both the BaseWeb wrapper and the textarea are targeted because
         the wrapper draws its own border. */
      [data-testid="stTextArea"] textarea,
      [data-testid="stTextArea"] [data-baseweb="textarea"],
      [data-testid="stTextArea"] [data-baseweb="base-input"] {
        border: 2px solid #3b82f6 !important;
        border-radius: 8px !important;
        box-shadow: 0 0 0 1px rgba(59,130,246,.18) !important;
      }
      [data-testid="stTextArea"] textarea {
        font-size: 1.12rem !important;
        line-height: 1.45 !important;
      }
      [data-testid="stTextArea"] textarea:focus,
      [data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within {
        border-color: #d92d20 !important;
        box-shadow: 0 0 0 4px rgba(217,45,32,.28) !important;
        outline: none !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Fixture-mode banner: first thing rendered, impossible to miss ------
_mode = fixtures.active_mode()
if _mode != "off":
    st.markdown(
        f'<div class="fixture-banner">FIXTURE MODE ACTIVE &mdash; NOT LIVE MODEL CALLS'
        f'<br/><span style="font-size:1.05rem;font-weight:600;">mode: {_mode}</span></div>',
        unsafe_allow_html=True,
    )

st.title("Bank Transaction Scenario")
st.caption(
    "All payees, account numbers and transfers shown here are synthetic demo data. "
    "No real customer, account or institution is represented."
)

if "history" not in st.session_state:
    st.session_state.history = []
if "last" not in st.session_state:
    st.session_state.last = None
if "instruction" not in st.session_state:
    # "to Rajesh", not "to Rajesh Kumar": payee_lookup matches on substring, and
    # "Rajesh K. Sharma" does not contain "Rajesh Kumar", so the longer phrasing
    # never retrieves C-88770 and the shared-account collision cannot fire.
    st.session_state.instruction = "Transfer 50,000 to Rajesh — same account as last time"

# --- Sidebar ------------------------------------------------------------
with st.sidebar:
    st.header("Controls")
    grounding = st.toggle("Grounding (RAG)", value=True, key="t_grounding")
    guardrails = st.toggle("Guardrails", value=True, key="t_guardrails")
    multi_agent = st.toggle("Multi-agent verification", value=False, key="t_multi")
    st.divider()
    st.caption(
        f"model **{os.getenv('MODEL_NAME', '?')}**  \n"
        f"telemetry **{os.getenv('TELEMETRY_BACKEND', 'phoenix')}**  \n"
        f"fixture mode **{_mode}**"
    )
    if st.button("Clear run history"):
        st.session_state.history = []
        st.session_state.last = None

# --- Instruction input --------------------------------------------------
st.text_area(
    "Customer instruction",
    key="instruction",
    height=90,
    label_visibility="visible",
)

col_send, col_p1, col_p2, col_p3 = st.columns([1.1, 1.5, 1.5, 1.5])
send = col_send.button("Send instruction", type="primary", use_container_width=True)


def _preset(text: str) -> None:
    st.session_state.instruction = text


col_p1.button(
    "Ambiguous", use_container_width=True,
    on_click=_preset, args=("Transfer 50,000 to Rajesh — same account as last time",),
)
col_p2.button(
    "Clear payee", use_container_width=True,
    on_click=_preset, args=("Transfer 50,000 to Rajesh Kumar Verma",),
)
col_p3.button(
    "Agents disagree", use_container_width=True,
    on_click=_preset,
    args=("Transfer 50,000 to Rajesh Kumar Verma — the same account as last time",),
)

# --- Run ----------------------------------------------------------------
if send and st.session_state.instruction.strip():
    # Written BEFORE run(); every consumer re-reads these per call.
    os.environ["GROUNDING_ENABLED"] = "true" if grounding else "false"
    os.environ["GUARDRAILS_ENABLED"] = "true" if guardrails else "false"
    os.environ["MULTI_AGENT_MODE"] = "true" if multi_agent else "false"

    from app.graph import run

    with st.spinner("Running…"):
        started = time.time()
        try:
            state = dict(run(st.session_state.instruction))
        except Exception as exc:
            st.error(f"Run failed: {type(exc).__name__}: {exc}")
            state = None
        elapsed = time.time() - started

    if state is not None:
        st.session_state.last = state
        by_id = {c["payee_id"]: c for c in (state.get("candidates") or [])}
        resolved = state.get("resolved_payee_id")
        st.session_state.history.insert(0, {
            "time": time.strftime("%H:%M:%S"),
            "instruction": state.get("instruction", ""),
            "resolved payee": (
                f"{by_id[resolved]['name']} ({resolved})" if resolved in by_id else "—"
            ),
            "blocked": "BLOCKED" if state.get("blocked") else "executed",
            "confidence": (
                round(float(state.get("confidence") or 0.0), 2)
                if state.get("guardrails_enabled", True) else "—"
            ),
            "grounded": bool(state.get("grounded")),
            "seconds": round(elapsed, 1),
        })

# --- Result -------------------------------------------------------------
state = st.session_state.last
if state:
    st.divider()
    by_id = {c["payee_id"]: c for c in (state.get("candidates") or [])}
    resolved = state.get("resolved_payee_id")
    payee = by_id.get(resolved or "")
    blocked = bool(state.get("blocked"))

    left, right = st.columns([2, 1])
    with left:
        st.markdown(
            f'<div class="payee-name">{payee["name"] if payee else "No payee resolved"}</div>'
            f'<div class="payee-id">{resolved or "—"}</div>',
            unsafe_allow_html=True,
        )
    with right:
        if state.get("guardrails_enabled", True):
            st.metric("Confidence", f"{float(state.get('confidence') or 0):.2f}")
        else:
            # Not zero -- never measured. Showing 0.00 here would read as
            # "the model was unsure" when in fact no check ran at all.
            st.metric("Confidence", "—", help="Guardrails off: no confidence was computed")
        st.markdown(
            f"**Grounding:** {'on — context retrieved' if state.get('grounded') else 'OFF — no context'}"
        )

    if blocked:
        st.markdown(
            '<div class="panel panel-block">'
            '<div class="nothing">NO TRANSFER WAS MADE</div>'
            f'<div class="big-answer" style="margin-top:.5rem">{state.get("block_reason") or ""}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        transfer = state.get("transfer") or {}
        st.markdown(
            '<div class="panel panel-ok">'
            f'<div class="big-answer">{state.get("response", "")}</div>'
            + (f'<div class="trace">reference {transfer.get("reference","")}</div>'
               if transfer else "")
            + "</div>",
            unsafe_allow_html=True,
        )

    # --- The judge's own words: an audience reads this off the screen ---
    judge = state.get("judge")
    if judge:
        st.markdown(
            '<div class="panel panel-judge">'
            f'<div class="panel-h">LLM judge &mdash; confidence {float(judge.get("confidence",0)):.2f}'
            f'{"" if judge.get("judge_available", True) else " (JUDGE UNAVAILABLE)"}</div>'
            f'<div class="rationale">{judge.get("rationale","")}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    elif not state.get("guardrails_enabled", True):
        st.markdown(
            '<div class="panel panel-judge"><div class="panel-h">LLM judge</div>'
            '<div class="rationale">Guardrails are off — no judge call was made.</div></div>',
            unsafe_allow_html=True,
        )

    verification = state.get("verification")
    if verification:
        agrees = verification.get("agrees")
        st.markdown(
            '<div class="panel panel-verify">'
            f'<div class="panel-h">Independent verifier &mdash; '
            f'{"AGREES" if agrees else "DISAGREES"}</div>'
            f'<div class="rationale">{verification.get("rationale","")}</div>'
            + (f'<div class="trace">verifier chose {verification.get("verifier_choice") or "no payee"}</div>')
            + "</div>",
            unsafe_allow_html=True,
        )

    if state.get("candidates"):
        with st.expander(f"Candidates considered ({len(state['candidates'])})", expanded=blocked):
            st.dataframe(
                [
                    {
                        "payee_id": c["payee_id"], "name": c["name"],
                        "acct ••••": c["account_last4"], "joint": c["is_joint"],
                        "last transfer": c["last_transfer_date"] or "never",
                    }
                    for c in state["candidates"]
                ],
                use_container_width=True, hide_index=True,
            )

    if state.get("trace_id"):
        st.markdown(
            f'<div class="trace">trace_id <b>{state["trace_id"]}</b> — '
            f'open it in Phoenix at localhost:6006 to see the span tree</div>',
            unsafe_allow_html=True,
        )

# --- Run history --------------------------------------------------------
if st.session_state.history:
    st.divider()
    st.subheader("Run history (this session)")
    st.caption("Two runs of the same instruction sit side by side here — that is the comparison.")
    st.dataframe(st.session_state.history, use_container_width=True, hide_index=True)
