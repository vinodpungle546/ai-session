# Session runbook — UI · Code · Telemetry

**Session:** Managing the Lifecycle of AI-Enabled Products and Agents
**Demo:** Bank Transaction Scenario
**Every figure here was measured on this build. Line numbers are current.**

Each slide below has up to three lanes:

- **UI** — what to click on the Streamlit app
- **CODE** — which file and line to open, and the one thing to say about it
- **TELEMETRY** — what to point at in Phoenix or Langfuse

> **Keep every code moment to 20–30 seconds.** The audience is PMs and
> leadership. Show the *shape* — a decorator, an if/else, a prompt string —
> never scroll a function. The point is always "this is a thing your team wrote
> and owns", not "here is how it works".

---

## Pre-flight (15 minutes before)

| # | Check | Expected |
|---|---|---|
| 1 | Docker Desktop running | `docker ps` shows `payee-demo-test` |
| 2 | <http://localhost:8000> | app loads (→ Phoenix) |
| 3 | <http://localhost:6006> | Phoenix loads |
| 4 | <http://localhost:8502> | app loads (→ Langfuse) |
| 5 | <https://jp.cloud.langfuse.com> | logged in, "My Project" |
| 6 | Editor open on `payee-demo/` | font size up, minimap off |
| 7 | Send one instruction on :8000 | responds in ~4 s (warms the model) |

**Two app instances are required.** `TELEMETRY_BACKEND` is fixed per process
(`init_telemetry()` is cached at import), so one app feeds one backend:

```bash
# :8000 container already points at Phoenix.
cd payee-demo && source .venv/bin/activate
TELEMETRY_BACKEND=langfuse streamlit run ui/streamlit_app.py --server.port=8502
```

If you restart the container, keep the endpoint override or traces stop
arriving silently (inside a container, `localhost` is the container):

```bash
docker run -d --name payee-demo-test -p 8000:8000 --env-file .env \
  -e PHOENIX_ENDPOINT=http://host.docker.internal:6006/v1/traces payee-demo
```

**Tabs, left to right:** editor · `:8000` · `localhost:6006` · `:8502` · Langfuse
**In Phoenix:** sort by Start Time descending — ~4,400 spans are already stored.

---

## Code cheat sheet — every anchor in one place

| Component | File : line | What to say |
|---|---|---|
| **Tools** | `app/tools.py:38` | `@tool` + docstring — the model reads the docstring to decide when to call it |
| — payee lookup | `app/tools.py:39` | substring match; several matches is the *normal* outcome |
| — execute transfer | `app/tools.py:92` | the only function that moves money |
| **RAG** | `app/rag.py:162` | `retrieve()` — returns `[]` when grounding is off, no fallback |
| — index build | `app/rag.py:112` | idempotent; built at image build time |
| **State** | `app/state.py:17` | the typed contract every node reads and writes |
| **Agent 1 · resolver** | `app/graph.py:120` | its own `get_llm()` call; answer validated against the candidate list |
| **Judge** | `app/guardrails.py:196` | its own call, its own prompt |
| **Structural floor** | `app/guardrails.py:89` | plain Python, no model — always fires |
| **The cap** | `app/guardrails.py:28` | `STRUCTURAL_CONFIDENCE_CAP = 0.4` |
| **Combine** | `app/guardrails.py:277` | `min(judge, cap)` — the judge can only lower |
| **Agent 2 · verifier** | `app/verifier.py:91` | its own call; sees three fields only |
| — its prompt | `app/verifier.py:52` | `build_verifier_prompt()` — the whole isolation boundary |
| — the override | `app/verifier.py:145` | code overrules the model's own `agrees` |
| **Graph wiring** | `app/graph.py:352` | `build_graph()` — one if/else is the whole multi-agent difference |
| **Model factory** | `app/config.py:54` | `get_llm()` — provider swappable by env |
| **Telemetry** | `app/telemetry.py` | one instrumentation, two backends |

---

## Slide 4 — REVEAL 1 · what's inside an agent

**UI (:8000)** — defaults → **Clear payee** preset → Send.

**CODE — Tools (the box that moves money)**
Open `app/tools.py:38`.

```python
@tool
def payee_lookup(name_fragment: str, customer_id: str) -> list[dict]:
    """Find saved payees for a customer whose name contains the given text. ..."""
```

> *"That docstring is not a comment — it's what the model reads to decide when to
> call this. Tools are the box where an agent stops being a chatbot and starts
> moving money, and `execute_transfer` at line 92 is the one that does."*

Optionally `app/state.py:17` — the typed state contract, ~30 seconds.

**TELEMETRY (Phoenix)** — open the newest trace, map spans to your five boxes:

| Box | Span |
|---|---|
| Tools | `payee_lookup` · `execute_transfer` **[tool]** |
| Brain | `skill.payee_disambiguation` **[llm]** |
| Skills | the `skill.*` names |
| Harness | `confidence_gate` |

> **"This is the actual request I just sent, and every box is a row you can click."**

**⚠ Gap — no Memory span.** No memory component exists. Either drop Memory from
the five boxes, or say *"memory here is the payee's `last_transfer_date` on the
record, not a separate component."*

---

## Slide 5 — the harness is the product

**CODE only — no UI, no telemetry. ~45 seconds.**

Open `app/guardrails.py:89` (`structural_ambiguity`) and scroll to `:28`.

```python
STRUCTURAL_CONFIDENCE_CAP = 0.4
```

> *"This is the harness. It is plain Python — no model involved. It caps
> confidence at 0.4 whenever two payees share an account, or several names match,
> or the instruction says 'last time' and more than one payee has been paid. The
> model cannot argue with it."*

Then `app/guardrails.py:277` for one line:

```python
confidence = min(float(judge.get("confidence", 0.0)), cap)
```

> *"The judge is an AI and it can lower confidence. It cannot raise it above the
> floor. That asymmetry is the product."*

**The line for leadership:** *"The graph, guardrail and verifier are about 900
lines of Python that our team wrote and owns. The model is a dependency we can
swap in one environment variable — `app/config.py:54`."*

---

## Slide 6 — REVEAL 2 · non-determinism

**UI (:8000)** — **Ambiguous** preset → Send → Send again. Both appear in Run history.

**⚠ Gap — this will NOT diverge.** 27 consecutive runs all resolved to C-88214,
across gpt-4o-mini (temperatures 0 → 2.0) and gpt-3.5-turbo. Both models find
"Rajesh Kumar Sharma" the best reading, and they are not wrong to.

**Use your own recovery line — it is the stronger version:**

> **"They agreed that time — which is exactly the problem. It's not reliably
> wrong, it's unreliably right."**

**Then pivot to what does vary, on screen:** the **judge's rationale text differs
on every run**. Same verdict, different reasoning. That is genuine
non-determinism the audience can read off the projector.

**CODE (optional, 20 s)** — `app/graph.py:120`, the resolver:

```python
if chosen not in valid_ids:
    chosen = valid_ids[0] if len(valid_ids) == 1 else None
```

> *"We don't trust the model's answer. We check it came from the list we gave it."*

---

## Slide 9 — REVEAL 3 · hallucinate → ground → catch

**Settings for each part — set these before pressing Send:**

| Part | Instruction | Grounding | Guardrails | Multi-agent |
|---|---|---|---|---|
| **1 — hallucinate** | *type:* `What is the account number for Rajesh Kumar Iyer?` | **off** | **off** | off |
| **2 — ground** | same question | **on** | **off** | off |
| **3 — catch** | **Ambiguous** preset | on | **on** | off |

**There is no preset for Parts 1 and 2** — the three presets are all transfer
instructions. Type the question into the instruction box.

**⚠ Guardrails must be OFF for Parts 1 and 2.** A question has no payee
candidates, so with guardrails on the judge scores 0.00, the run is marked
blocked, and the UI shows the red **"NO TRANSFER WAS MADE"** panel with the
judge's reasoning — the model's actual answer is computed but never displayed
(`ui/streamlit_app.py:237` renders `block_reason` when blocked; the answer only
appears in the non-blocked branch at `:245`). Measured:

| Grounding | Guardrails | On screen |
|---|---|---|
| off | on | red panel — *"Judge (0.00): There are no proposed payees…"* |
| off | **off** | *"I'm sorry, but I can't provide personal account information…"* |
| on | on | red panel — judge text |
| on | **off** | *"I have no record of that payee."* |

Switching guardrails back **on** for Part 3 is itself a good beat: the next
thing the room sees is a transfer being refused.

### Part 1 — hallucinate
Grounding **off**, Guardrails **off**; type `What is the account number for Rajesh Kumar Iyer?`

**⚠ gpt-4o-mini refuses 5/5 — it will not fabricate.** Two options:

- **Fixture:** `FIXTURE_MODE=seed_hallucination` produces an invented masked
  number. A red banner appears — acknowledge it: *"a stand-in, because this model
  refuses; a weaker one invents."*
- **Honest version (recommended):** ungrounded refuses with **privacy
  boilerplate**; grounded refuses with **"I have no record of that payee."**
  Same refusal, completely different epistemics.

### Part 2 — ground
Grounding **on**, Guardrails still **off**, same question.

**CODE — RAG.** Open `app/rag.py:162`:

```python
if not _env_flag("GROUNDING_ENABLED"):
    logger.info("Grounding disabled; returning no context.")
    return []
```

> *"When grounding is off it returns nothing and reads nothing. There is
> deliberately no fallback — that is what makes the ungrounded path honest."*

Mention `app/rag.py:112` in one line: *"the index is 36 chunks from twelve
customer-master documents, embedded locally, built into the container image."*

**TELEMETRY (Phoenix)** — open `retrieve_context`, show the retrieved chunk.

> **"We're not asking anyone to trust the answer — we can show which record it
> came from, on which run, at which timestamp."**

### Part 3 — catch
Turn Guardrails back **on** → **Ambiguous** preset → Send. Red **NO TRANSFER WAS MADE**, confidence **0.40**.

**TELEMETRY** — point at what is *absent*: no `execute`, no `execute_transfer`.
**12 spans, not 14.**

---

## Slide 10 — evals

**CODE only. ~40 seconds.**

Open `evals/cases.jsonl` — scroll a few lines so they see it is a flat file.

```bash
wc -l evals/cases.jsonl        # 60
```

Then `evals/run_evals.py`, the gate:

```python
gate_passed = pass_rate >= args.threshold and not wrong
return 0 if gate_passed else 1
```

> *"One wrong-payee execution fails the build at a 100% pass rate. Some failure
> categories don't get a tolerance band — that's a business decision expressed in
> four lines of code."*

**Optional live run** (~15 s): `python evals/run_evals.py --subset 12`
Last full run: **60/60, zero wrong-payee executions, exit 0.**

---

## Slide 11 — REVEAL 4 · multi-agent

**UI (:8000)** — **Agents disagree** preset.
Multi-agent **off** → **executes**. Multi-agent **on** → **blocked**, verifier
panel reads DISAGREES.

**CODE — the two things that matter.**

1. `app/graph.py:352` — the wiring. One if/else:

```python
if multi_agent:
    builder.add_node("verify", verify)
    ...{"blocked": "compose_response", "allowed": "verify"}
else:
    ...{"blocked": "compose_response", "allowed": "execute"}
```

> *"A second agent is one node and one edge. That's the whole architectural change."*

2. `app/verifier.py:52` — `build_verifier_prompt()`. Show the three keys:

```python
payload = {"instruction": ..., "candidates": [...], "proposed_payee_id": ...}
```

> *"That is everything the second agent is told. It never sees the first agent's
> reasoning — an agent shown another agent's argument tends to agree with it, and
> an agreement produced that way tells you nothing."*

Then `app/verifier.py:145` if you have 15 seconds spare:

```python
if choice is not None and proposed is not None and choice != proposed:
    agrees = False
```

> *"If the model claims it agrees while naming a different payee, the code
> overrules it."*

**Generate all of this live instead, if you prefer:**

```bash
python demo/show_modes.py            # topology, wiring, isolation, validation
python demo/show_modes.py --run      # both modes, same instruction
```

Everything it prints is read from the running code via `inspect`, so a sceptical
room gets a command rather than a claim.

**TELEMETRY (Phoenix)** — two traces side by side, **14 spans vs 16**. In the
multi-agent trace open **`agent_handoff` → Attributes**:

```
agent1_choice = C-90117
agent2_choice = None
agrees        = false
```

**Cost delta (measured):**

| | LLM calls | tokens | wall time |
|---|---|---|---|
| single-agent | 2 | 798 | 3.9 s |
| multi-agent | 3 | 1,234 | 6.0 s |

**+55% tokens, +54% latency.** Say the number out loud.

**⚠** Phoenix does not roll tokens up to the root span (`total=0`). Read the
per-LLM spans, or use Langfuse, which totals it.

**Why it blocks:** C-90117 has never received a transfer, so "the same account as
last time" is false of it. The name matches perfectly, so the resolver and the
judge both pass it — **the judge scored 0.90**. Only the verifier checks the
instruction against the payee's own record. Measured **5/5 disagreement**, and
**5/5 agreement** on the plain control.

---

## Slide 14 — observability

**UI (:8502)** — send two or three instructions first so the dashboard is not empty.

**CODE (20 s)** — `app/telemetry.py`, the two target functions:

> *"One instrumentation. The only difference between local and hosted is the URL
> and the auth header. In production that URL points at Application Insights."*

**TELEMETRY (Langfuse)** — trace list with **latency and cost per trace**, then
open one trace to show the same span tree Phoenix showed.

> **"We're not asking for a new observability stack. We're asking for the
> AI-specific fields to flow into the one we already pay for."**

**⚠** The App Insights export is **not built**. Keep that point verbal.

---

## Slide 15 — REVEAL 5 · cost

**UI (:8502)** — same instruction three times, one toggle changed each time.
Read the costs off Langfuse:

| Configuration | Cost | LLM calls | Tokens | vs cheapest |
|---|---|---|---|---|
| guardrails **off** | $0.000079 | 1 | 494 | 1.00× |
| guardrails **on** | $0.000149 | 2 | 817 | **1.88×** |
| multi-agent | $0.000243 | 3 | 1,242 | **3.08×** |

Langfuse prices `gpt-4o-mini` automatically from token counts — no configuration.

**CODE (15 s)** — `app/guardrails.py:290`:

```python
if not _env_flag("GUARDRAILS_ENABLED"):
    ...
    return result          # no judge call is made at all
```

> *"Turning the guardrail off doesn't just stop blocking — it stops the second
> model call. That's where the cost difference comes from."*

> **"This is what it costs to be sure we're paying the right Rajesh."**
> **"Reliability isn't free, and it doesn't show up in the project budget —
> it shows up in run cost, every month, forever."**

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No traces in Phoenix from :8000 | container `localhost` ≠ host | restart with `-e PHOENIX_ENDPOINT=http://host.docker.internal:6006/v1/traces` |
| App healthy but everything blocks | invalid `MODEL_NAME` → all LLM calls 400 → judge fails closed | `docker exec payee-demo-test printenv MODEL_NAME` — **no inline comments in `.env`**; `docker --env-file` does not strip them |
| `docker` fails | Docker Desktop not running | launch it; `:8000` is down until then |
| Langfuse 401 | wrong region | `LANGFUSE_HOST=https://jp.cloud.langfuse.com` |
| Newest Phoenix trace hard to find | ~4,400 spans stored | sort by Start Time descending |
| Judge rationale identical each run | `JUDGE_TEMPERATURE=0` | default is 0.3 — variation is intended |

**Network fallback:** `FIXTURE_MODE=replay` returns saved runs with no model
calls. A red banner appears so you cannot demo in replay by accident.

---

## Known gaps — decide before the session

1. **Reveal 2 does not diverge** (27 runs, two models, five temperatures). Use
   the recovery line; pivot to the varying judge rationale.
2. **No Memory span** for Reveal 1's five-box claim.
3. **App Insights export** does not exist — keep Slide 14's point verbal.
4. **No hosted deployment** (Prompt 12 not built), so Slide 15's "what it costs
   to leave running" is illustrative.
5. **`balance_check` and `get_transfer_history` are defined but never called**
   (`app/tools.py:72`, `:120`). The demo does **not** check the balance before
   transferring — worth knowing before a banking audience asks.

---

*All payees, account numbers and transfers are synthetic. Eval gate last run:
60/60, zero wrong-payee executions, exit 0.*
