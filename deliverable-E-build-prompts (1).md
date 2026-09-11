# Deliverable E — Build Prompts
## Banking payee disambiguation demo

Twelve prompts, in dependency order. Paste one at a time, run its acceptance check before moving on.

---

## How to use this pack

**Run them in order.** Each depends on files the previous ones created. Skipping ahead produces code that references things that don't exist.

**Every prompt is self-contained.** Each one restates the data schema, the state shape, and the exact filenames it touches. This is deliberate repetition, not sloppiness — it means a smaller model that has lost the earlier conversation still has everything it needs, and it means you can re-run any single prompt in a fresh session weeks later.

**Check before you continue.** Each prompt has an acceptance check that is a command you run, not a judgement you make. If it fails, use the follow-up prompt supplied rather than improvising — the follow-ups are written to correct the specific failure that prompt tends to produce.

**On model escalation.** Prompts 3, 6, 7 and 9 are the ones most likely to need Claude rather than GLM 5.2-flash. They involve either multi-file coordination or API surfaces that change frequently. If GLM's output fails the acceptance check twice, escalate rather than iterating a third time.

**On library versions.** LangGraph and the OpenInference instrumentors change their APIs faster than most models' training data. Every prompt that touches them tells the agent to read the installed version first. Do not remove that instruction — it is the single highest-value line in this pack.

---

## Every demo beat is a real model call

Nothing on the demo path is simulated. Specifically:

| Beat | Real LLM call? | Where |
|---|---|---|
| Parsing the instruction | Yes | `parse_instruction` node |
| Choosing the payee | Yes | `resolve_payee` node — **this is where Reveal 2's divergence comes from** |
| Judging confidence | Yes | `guardrails.llm_confidence_judge` (prompt 4) |
| Independent verification | Yes | `verifier.verify_resolution` — its own separate call |
| Fabricating an account number | Yes | Real ungrounded call in Reveal 3 Part A |
| Retrieval | Real vector search over real documents | `app/rag.py` |

The Reveal 2 divergence is genuine model non-determinism on a real call against real data. If it were staged the demo would be dishonest, and someone in the room would eventually find out.

**Fixtures are contingency only.** `FIXTURE_MODE` defaults to `off`, and prompt 10 requires the UI to display a loud banner whenever it isn't — so you cannot demo in replay mode without knowing. Rung 2 of Deliverable D's contingency ladder exists for the case where the network dies mid-session, not as the plan.

**Cost and rate-limit implications of everything being live.** The full 60-case eval suite is 60+ real calls, and the verifier doubles the calls per transaction in multi-agent mode. Budget for this when you run the suite repeatedly during the build, and check your rate limits before running the full suite back-to-back. The `--subset` flag in prompt 9 exists for this reason.

---

## The shared contract

Every prompt below repeats the parts of this it needs. It is here so you can check the agent hasn't quietly invented a different shape.

### Project layout

```
payee-demo/
  app/
    config.py        # env-driven settings
    state.py         # AgentState TypedDict
    tools.py         # payee_lookup, balance_check, execute_transfer
    rag.py           # customer master retrieval
    guardrails.py    # confidence check
    graph.py         # LangGraph single-agent graph
    verifier.py      # second agent, two-agent mode
    telemetry.py     # OpenTelemetry -> Phoenix | Langfuse
    fixtures.py      # deterministic replay for demo fallback
  data/
    payees.json
    transfer_history.json
    customer_master/*.md
  evals/
    cases.jsonl
    run_evals.py
  ui/streamlit_app.py
  Dockerfile
  requirements.txt
  .env.example
  deploy/azure.sh
```

### Payee record

```json
{
  "payee_id": "C-88214",
  "name": "Rajesh Kumar Sharma",
  "account_last4": "4471",
  "is_joint": false,
  "last_transfer_date": "2026-08-12",
  "owner_customer_id": "CUST-1001"
}
```

### The four payees (owner `CUST-1001`)

| payee_id | name | account_last4 | is_joint | last_transfer_date |
|---|---|---|---|---|
| C-88214 | Rajesh Kumar Sharma | 4471 | false | 2026-08-12 |
| C-90117 | Rajesh Kumar Verma | 2093 | false | null |
| C-88770 | Rajesh K. Sharma | 4471 | true | 2026-09-03 |
| C-91002 | Rajesh Kumar | 8830 | false | 2026-07-22 |

### AgentState

```python
class AgentState(TypedDict):
    instruction: str
    customer_id: str
    amount: float | None
    candidates: list[dict]
    resolved_payee_id: str | None
    confidence: float
    grounded: bool
    blocked: bool
    block_reason: str | None
    verification: dict | None
    response: str
    trace_id: str | None
```

---

## Prompt 1 — Scaffold and synthetic data

```
Create a Python project called payee-demo for a banking payee-disambiguation
demo. Python 3.11.

Create exactly this structure, with empty __init__.py where needed:

payee-demo/
  app/__init__.py
  data/
  evals/
  ui/
  deploy/
  requirements.txt
  .env.example
  README.md

In requirements.txt pin these (latest compatible versions, resolve them yourself):
langgraph, langchain, langchain-openai, langchain-community, chromadb,
streamlit, opentelemetry-sdk, opentelemetry-exporter-otlp,
openinference-instrumentation-langchain, arize-phoenix, langfuse,
python-dotenv, pydantic

Create data/payees.json as a JSON array of exactly these four records, using
exactly these field names:
  payee_id, name, account_last4, is_joint, last_transfer_date, owner_customer_id

C-88214 | Rajesh Kumar Sharma | 4471 | false | 2026-08-12 | CUST-1001
C-90117 | Rajesh Kumar Verma  | 2093 | false | null       | CUST-1001
C-88770 | Rajesh K. Sharma    | 4471 | true  | 2026-09-03 | CUST-1001
C-91002 | Rajesh Kumar        | 8830 | false | 2026-07-22 | CUST-1001

Also add 8 more unrelated payees for CUST-1001 with clearly different names
(no Rajesh, no Kumar) so the list is not trivially small.

Create data/transfer_history.json: an array of past transfers with fields
transfer_id, payee_id, amount, date. Include at least one transfer to C-88214
dated 2026-08-12 and one to C-88770 dated 2026-09-03.

Create data/customer_master/ containing one markdown file per payee, named
<payee_id>.md, each stating the payee's full name, full masked account number,
account type, and whether it is a joint account. These are the documents the
RAG layer will retrieve.

ALL DATA MUST BE SYNTHETIC. Generated names, generated account numbers.
Do not use any real-looking IFSC codes, real bank names, or real branch codes.

Create .env.example with placeholder keys for: MODEL_PROVIDER, MODEL_NAME,
MODEL_API_KEY, MODEL_BASE_URL, TELEMETRY_BACKEND, PHOENIX_ENDPOINT,
LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY.

Create app/config.py that loads all of the above from environment with
python-dotenv, exposes them as module-level constants, and provides
get_llm() returning a LangChain chat model built from MODEL_PROVIDER,
MODEL_NAME, MODEL_API_KEY and MODEL_BASE_URL. MODEL_PROVIDER must accept
at least "openai_compatible" and "anthropic" so the backend is swappable
by config alone.

Write README.md with setup and run instructions.
```

**Expected output files:** `requirements.txt`, `.env.example`, `README.md`, `app/config.py`, `data/payees.json`, `data/transfer_history.json`, `data/customer_master/*.md`

**Acceptance check:**
```bash
cd payee-demo && python -c "
import json
p=json.load(open('data/payees.json'))
ids={r['payee_id'] for r in p}
assert {'C-88214','C-90117','C-88770','C-91002'} <= ids, 'missing core payees'
four=[r for r in p if r['payee_id'] in {'C-88214','C-88770'}]
assert all(r['account_last4']=='4471' for r in four), 'shared account not set'
assert len(p)>=12, 'payee list too small'
print('OK', len(p), 'payees')"
```

**If the output is wrong, ask this instead:**
```
data/payees.json is not correct. Rewrite ONLY that file. It must be a JSON
array. C-88214 and C-88770 must BOTH have account_last4 "4471" — this shared
account is the point of the demo and must not be changed. C-90117 must have
last_transfer_date null. Field names exactly: payee_id, name, account_last4,
is_joint, last_transfer_date, owner_customer_id.
```

---

## Prompt 2 — Tools

```
In the payee-demo project, create app/tools.py.

Context: data/payees.json is a JSON array of payee records with fields
payee_id, name, account_last4, is_joint, last_transfer_date,
owner_customer_id. data/transfer_history.json is a JSON array with fields
transfer_id, payee_id, amount, date.

Define three LangChain tools using the @tool decorator:

1. payee_lookup(name_fragment: str, customer_id: str) -> list[dict]
   Case-insensitive substring match on name, filtered to owner_customer_id ==
   customer_id. Returns the full matching records. Returns [] on no match.

2. balance_check(customer_id: str) -> dict
   Returns {"customer_id": ..., "available_balance": 250000.0, "currency":
   "INR"}. Hard-coded is fine.

3. execute_transfer(payee_id: str, amount: float, customer_id: str) -> dict
   Returns {"status": "executed", "payee_id": ..., "amount": ...,
   "reference": "<uuid4>"}. It must NOT write anything to disk.

Also provide get_transfer_history(customer_id: str) -> list[dict] as a plain
function (not a tool) that reads data/transfer_history.json.

Each tool needs a clear docstring — the model reads these to decide when to
call them.

Load the JSON files once at module import, not on every call.
```

**Expected output files:** `app/tools.py`

**Acceptance check:**
```bash
cd payee-demo && python -c "
from app.tools import payee_lookup, balance_check, execute_transfer
r = payee_lookup.invoke({'name_fragment':'Rajesh','customer_id':'CUST-1001'})
assert len(r)==4, f'expected 4 Rajesh matches, got {len(r)}'
assert balance_check.invoke({'customer_id':'CUST-1001'})['available_balance']>0
print('OK', [x['payee_id'] for x in r])"
```

**If the output is wrong, ask this instead:**
```
app/tools.py is wrong. payee_lookup must return 4 records when called with
name_fragment "Rajesh" and customer_id "CUST-1001". Check that the match is a
case-insensitive SUBSTRING match against the "name" field, not an exact match
and not a token match. Rewrite only app/tools.py.
```

---

## Prompt 3 — RAG layer

```
In the payee-demo project, create app/rag.py.

Context: data/customer_master/ contains one markdown file per payee, named
<payee_id>.md. app/config.py exposes get_llm() and module-level config
constants.

Build a retrieval layer over data/customer_master/:

- build_index() -> loads every .md file in data/customer_master/, chunks them,
  embeds them, and persists a Chroma collection to ./chroma_store. Idempotent:
  if the store already exists, load rather than rebuild.
- retrieve(query: str, k: int = 4) -> list[dict], each dict containing
  "content", "source_file", and "payee_id".
- The module must expose a module-level flag GROUNDING_ENABLED read from the
  environment variable GROUNDING_ENABLED (default "true"). When grounding is
  disabled, retrieve() must return [] — it must NOT fall back to any other
  source. This is deliberate: the demo needs an ungrounded path.

Use a local embedding model so the demo runs without an embeddings API key.
Use chromadb's default embedding function if that is simplest.

IMPORTANT: before writing the code, check the installed versions of chromadb
and langchain-community and use the API those versions actually expose. Do not
write against a remembered API. If an import you expect is missing, print the
installed version and adapt.
```

**Expected output files:** `app/rag.py`, and `chroma_store/` on first run

**Acceptance check:**
```bash
cd payee-demo && python -c "
import os; os.environ['GROUNDING_ENABLED']='true'
from app.rag import build_index, retrieve
build_index()
r = retrieve('Rajesh Kumar Sharma account', k=4)
assert len(r)>0 and 'payee_id' in r[0], 'retrieval returned nothing usable'
print('OK', [x['payee_id'] for x in r])"
```

**If the output is wrong, ask this instead:**
```
app/rag.py fails. Run `pip show chromadb langchain-community` first and print
the versions. Then rewrite app/rag.py against those exact installed versions.
Do not use any import path you have not verified exists. If chromadb's
LangChain wrapper is problematic, use the chromadb client directly instead —
the demo only needs build_index() and retrieve() to work, not any particular
library.
```

---

## Prompt 4 — Guardrails (deterministic floor + LLM judge)

```
In the payee-demo project, create app/guardrails.py.

Context: app/tools.py provides payee_lookup. app/config.py provides get_llm().
Payee records have fields payee_id, name, account_last4, is_joint,
last_transfer_date, owner_customer_id.

This is a TWO-LAYER confidence check. Both layers run on every request.

LAYER 1 — deterministic structural floor.

structural_ambiguity(instruction: str, candidates: list[dict]) -> tuple[bool, list[str]]

Returns (is_ambiguous, reasons). Set is_ambiguous True when ANY of:
  - more than one candidate shares the same account_last4
  - more than one candidate name is a substring-plausible match for the name
    in the instruction
  - the instruction contains a relative reference ("last time", "same as
    before", "the usual", "as usual") AND more than one candidate has a
    non-null last_transfer_date
Each triggered condition appends a short human-readable reason string.

This layer is plain Python with no model call. Its job is to guarantee that
structurally ambiguous cases are ALWAYS caught, regardless of what any model
does on the day.

LAYER 2 — LLM judge.

llm_confidence_judge(instruction: str, candidates: list[dict],
                     resolved_payee_id: str) -> dict

Makes a REAL LLM call via get_llm(). It is given the instruction, the full
candidate list, and the proposed resolution. It must return JSON:
  {"confidence": 0.0-1.0, "rationale": "<one or two sentences>",
   "competing_payee_ids": ["..."]}

Prompt it to return ONLY JSON, no markdown fences, no preamble. Parse
defensively: strip fences if present, and on any parse failure return
{"confidence": 0.0, "rationale": "judge response unparseable",
 "competing_payee_ids": []} rather than raising. A demo must not crash on a
malformed judge response.

COMBINING THEM.

confidence_check(state: dict) -> dict
  1. Run structural_ambiguity. If it returns True, confidence is capped at
     0.4 no matter what the judge says. The floor wins.
  2. Run llm_confidence_judge. Take min(judge_confidence, cap).
  3. If final confidence < CONFIDENCE_THRESHOLD (env, default 0.75), set
     blocked=True and build block_reason from BOTH the structural reasons and
     the judge's rationale, naming every competing payee.
  4. Write the judge's full response into state so the UI can display the
     rationale — the audience reads this text.

Add GUARDRAILS_ENABLED read from env (default "true"). When disabled,
confidence_check passes everything through with blocked=False and makes no
judge call. The demo needs a guardrails-off path, and its cost difference is
shown to an audience — so the disabled path must genuinely skip the call.

Make llm_confidence_judge its own named function so it appears as a distinct
span in tracing.
```

**Expected output files:** `app/guardrails.py`

**Acceptance check:**
```bash
cd payee-demo && python -c "
import json, os
os.environ['GUARDRAILS_ENABLED']='true'
from app.guardrails import structural_ambiguity, confidence_check
p=json.load(open('data/payees.json'))
c=[r for r in p if 'Rajesh' in r['name']]
amb, reasons = structural_ambiguity('Transfer 50,000 to Rajesh Kumar — same account as last time', c)
assert amb is True, 'structural floor failed to fire'
st=confidence_check({'instruction':'Transfer 50,000 to Rajesh Kumar — same account as last time',
                     'candidates':c,'resolved_payee_id':'C-88214','confidence':1.0})
assert st['blocked'] is True and 'C-88770' in st['block_reason']
print('OK blocked. reasons:', reasons)
print('judge rationale:', st.get('verification') or st['block_reason'][:120])"
```

Run it three times. **The block must occur all three times** — that's the floor doing its job. The judge's rationale text will differ each run, which is fine and is itself worth pointing at during Reveal 3C.

**If the output is wrong, ask this instead:**
```
app/guardrails.py does not block reliably. The deterministic structural layer
must be sufficient on its own: with the four Rajesh candidates, two of which
share account_last4 "4471", structural_ambiguity must return True and cap
confidence at 0.4 REGARDLESS of what the LLM judge returns. The judge can only
lower confidence, never raise it above the cap. Show me the line where the cap
is applied. Also confirm the judge's JSON parse failure path returns a dict
rather than raising. Rewrite only app/guardrails.py.
```

---

## Prompt 5 — LangGraph graph and state

```
In the payee-demo project, create app/state.py and app/graph.py.

app/state.py defines exactly this TypedDict:

class AgentState(TypedDict):
    instruction: str
    customer_id: str
    amount: float | None
    candidates: list[dict]
    resolved_payee_id: str | None
    confidence: float
    grounded: bool
    blocked: bool
    block_reason: str | None
    verification: dict | None
    response: str
    trace_id: str | None

app/graph.py builds a LangGraph StateGraph over AgentState with these nodes,
each a separate named function so each appears as its own span in tracing:

  parse_instruction   -> extracts payee name fragment and amount into state
  lookup_candidates   -> calls payee_lookup from app.tools, fills candidates
  retrieve_context    -> calls retrieve() from app.rag, adds context; sets
                         grounded=True if anything was retrieved, else False
  resolve_payee       -> LLM call using get_llm() from app.config; picks ONE
                         payee_id from candidates; sets resolved_payee_id
  confidence_gate     -> calls confidence_check from app.guardrails
  execute             -> calls execute_transfer from app.tools
  compose_response    -> writes the final user-facing string into response

Edges: parse -> lookup -> retrieve -> resolve -> confidence_gate.
From confidence_gate, a conditional edge: if state["blocked"] is True go to
compose_response (skipping execute); otherwise go to execute, then
compose_response, then END.

Name the resolve_payee node's internal step "skill.payee_disambiguation" in
whatever way your LangGraph version supports naming, because a span with that
name is shown to an audience.

Expose: build_graph() -> compiled graph, and run(instruction: str,
customer_id: str = "CUST-1001") -> AgentState.

IMPORTANT: check the installed langgraph version first and use the API that
version exposes for StateGraph, conditional edges and compilation. Do not
write against a remembered API.
```

**Expected output files:** `app/state.py`, `app/graph.py`

**Acceptance check:**
```bash
cd payee-demo && python -c "
from app.graph import run
s = run('Transfer 50,000 to Rajesh Kumar Verma')
assert s['resolved_payee_id']=='C-90117', s['resolved_payee_id']
assert s['blocked'] is False
print('OK unambiguous ->', s['resolved_payee_id'])
s2 = run('Transfer 50,000 to Rajesh Kumar — same account as last time')
assert s2['blocked'] is True, 'ambiguous case was not blocked'
print('OK ambiguous -> blocked:', s2['block_reason'][:60])"
```

**If the output is wrong, ask this instead:**
```
app/graph.py does not route correctly. Two required behaviours:
(1) "Transfer 50,000 to Rajesh Kumar Verma" must resolve to C-90117 and
    execute, because only one candidate matches that name.
(2) "Transfer 50,000 to Rajesh Kumar — same account as last time" must end
    with blocked=True and must NOT call execute_transfer.
Check the conditional edge from confidence_gate. Print the compiled graph's
node list so I can see the wiring. Rewrite only app/graph.py.
```

---

## Prompt 6 — Telemetry

```
In the payee-demo project, create app/telemetry.py.

Requirement: instrument the LangChain/LangGraph application with
OpenTelemetry so that the SAME instrumentation exports to either Arize
Phoenix (local) or Langfuse (hosted), selected only by the environment
variable TELEMETRY_BACKEND, which accepts "phoenix" or "langfuse".

Provide init_telemetry() that:
  - reads TELEMETRY_BACKEND (default "phoenix")
  - for "phoenix": configures the OTLP exporter to PHOENIX_ENDPOINT
    (default http://localhost:6006/v1/traces)
  - for "langfuse": configures export to LANGFUSE_HOST using
    LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY
  - registers the OpenInference LangChain instrumentor so LangGraph node
    execution, LLM calls, tool calls and retriever calls all become spans
  - is idempotent — calling it twice must not double-register
  - never raises: if the backend is unreachable, log a warning and continue.
    The demo must still run with tracing broken.

Provide current_trace_id() -> str | None returning the active trace id, so
the UI can display it.

Call init_telemetry() at the top of app/graph.py's module import.

IMPORTANT: check the installed versions of
openinference-instrumentation-langchain, opentelemetry-sdk, arize-phoenix and
langfuse first, and write against the API those versions expose. These
libraries change their setup API frequently. Print the versions you found in a
comment at the top of the file.
```

**Expected output files:** `app/telemetry.py`, edit to `app/graph.py`

**Acceptance check:**

Start Phoenix, then:
```bash
cd payee-demo && TELEMETRY_BACKEND=phoenix python -c "
from app.graph import run
s=run('Transfer 50,000 to Rajesh Kumar Verma')
print('OK trace_id:', s.get('trace_id'))"
```
Then open `localhost:6006` and confirm a trace exists whose span tree includes nodes named for `lookup_candidates`, `retrieve_context`, `resolve_payee` and a tool span for `payee_lookup`. **This visual check is the real acceptance test — Reveal 1 depends entirely on those span names being legible.**

**If the output is wrong, ask this instead:**
```
Traces are not appearing in Phoenix / the span names are not visible. Do this:
1. Print the installed versions of openinference-instrumentation-langchain,
   opentelemetry-sdk and arize-phoenix.
2. Show me the minimal working setup snippet from THOSE versions' own docs
   or source.
3. Rewrite app/telemetry.py against it.
Do not guess at the instrumentor's class name or its register/instrument
method signature — read it from the installed package.
```

---

## Prompt 7 — Multi-agent verifier

```
In the payee-demo project, create app/verifier.py and extend app/graph.py.

Context: app/state.py defines AgentState with a "verification" field (dict or
None). app/graph.py has a compiled graph with nodes parse_instruction,
lookup_candidates, retrieve_context, resolve_payee, confidence_gate, execute,
compose_response.

Add a second agent that independently verifies the payee resolution before
execution.

app/verifier.py provides verify_resolution(state: dict) -> dict, which:
  - makes its OWN LLM call via get_llm() from app.config
  - is given ONLY: the original instruction, the candidate list, and the
    proposed resolved_payee_id
  - is NOT given the first agent's reasoning — the independence is the point
  - returns {"agrees": bool, "verifier_choice": payee_id | None,
             "rationale": str}
  - writes that dict into state["verification"]

In app/graph.py add a MULTI_AGENT_MODE flag read from env (default "false").
When true, insert a verify node between confidence_gate and execute. If the
verifier disagrees, set blocked=True with a block_reason naming both choices,
and skip execute.

The verify node must be a separate named graph node so it appears as its own
span, and the handoff between resolve_payee and verify must be visible in the
trace. An audience is shown this.

Keep single-agent mode working exactly as before when MULTI_AGENT_MODE=false.
```

**Expected output files:** `app/verifier.py`, edit to `app/graph.py`

**Acceptance check:**
```bash
cd payee-demo && MULTI_AGENT_MODE=true python -c "
from app.graph import run
s=run('Transfer 50,000 to Rajesh Kumar Verma')
assert s['verification'] is not None, 'verifier did not run'
print('OK verification:', s['verification'])"
cd payee-demo && MULTI_AGENT_MODE=false python -c "
from app.graph import run
s=run('Transfer 50,000 to Rajesh Kumar Verma')
assert s['verification'] is None, 'verifier ran when disabled'
print('OK single-agent unaffected')"
```

**If the output is wrong, ask this instead:**
```
The verifier is not isolated correctly. verify_resolution must make its own
separate LLM call and must receive ONLY the instruction, the candidate list
and the proposed payee_id. It must not receive the first agent's reasoning,
chain-of-thought, or any message history. Show me the exact prompt string the
verifier sends. Rewrite app/verifier.py.
```

---

## Prompt 8 — Demo fixtures and replay (fallback only)

```
In the payee-demo project, create app/fixtures.py.

READ THIS FIRST: this module is a CONTINGENCY for live-demo failure, not part
of the demo. The demo makes real LLM calls. Fixture mode exists only for the
case where the network or the model API is unavailable mid-session. It must
default to off and must be impossible to enter by accident.

Provide:

1. FIXTURE_MODE, read from env, default "off". Values: "off", "replay",
   "seed_hallucination".

2. When FIXTURE_MODE="off" (the default, and the demo path), this module must
   have ZERO effect on behaviour. Every call goes to the real model.

3. When FIXTURE_MODE="replay": run() in app/graph.py returns a saved
   AgentState from fixtures/ instead of calling the model. Fixtures are JSON
   in fixtures/, keyed by a slug of the instruction. Provide
   save_fixture(state) so real runs can be captured the day before.

4. When FIXTURE_MODE="seed_hallucination": for a payee name NOT present in
   data/payees.json, return a fabricated but plausible masked account number,
   with grounded=False.

   IMPORTANT CONTEXT for why this exists: in the live demo the fabrication is
   produced by a REAL ungrounded model call — grounding is toggled off and the
   model genuinely invents an account number. That is the intended path. But
   whether a given model fabricates rather than refusing is itself
   non-deterministic, and more capable models refuse more often. This mode is
   the backup for a model that refuses on the day. It must never trigger for a
   payee name that exists in data/payees.json.

5. A CLI: `python -m app.fixtures capture "<instruction>"` runs the REAL graph
   and saves the result as a fixture.

6. At import, if FIXTURE_MODE is not "off", print a prominent warning to
   stderr naming the active mode. Expose active_mode() so the UI can show a
   banner.
```

**Expected output files:** `app/fixtures.py`, `fixtures/` directory, edit to `app/graph.py`

**Acceptance check:**

First confirm the REAL ungrounded path fabricates with no fixture involved:
```bash
cd payee-demo && FIXTURE_MODE=off GROUNDING_ENABLED=false python -c "
from app.graph import run
s=run('What is the account number for Rajesh Kumar Iyer?')
print('REAL ungrounded response:', s['response'][:140])
print('grounded flag:', s['grounded'])"
```
Run this several times and note how often it fabricates versus refuses. **That ratio tells you how much you actually need the fixture.** If your model fabricates reliably, the backup may never be used.

Then confirm the fixture path works and the default is genuinely off:
```bash
cd payee-demo && FIXTURE_MODE=seed_hallucination python -c "
from app.graph import run
s=run('What is the account number for Rajesh Kumar Iyer?')
assert s['grounded'] is False and any(c.isdigit() for c in s['response'])
print('OK seeded backup works')"
cd payee-demo && python -c "
from app import fixtures
assert fixtures.active_mode()=='off', 'fixture mode is not off by default'
print('OK default is off')"
```

**If the output is wrong, ask this instead:**
```
app/fixtures.py is affecting the default path. With FIXTURE_MODE unset,
active_mode() must return "off" and run() must make real model calls with no
interception whatsoever. Show me the exact branch where interception happens
and confirm it is unreachable when FIXTURE_MODE is unset. Separately,
seed_hallucination must never trigger for "Rajesh Kumar Sharma", "Rajesh Kumar
Verma", "Rajesh K. Sharma" or "Rajesh Kumar". Rewrite only app/fixtures.py.
```

---

## Prompt 9 — Eval suite

```
In the payee-demo project, create evals/cases.jsonl and evals/run_evals.py.

Context: app/graph.py exposes run(instruction, customer_id) -> AgentState with
fields resolved_payee_id, blocked, confidence. data/payees.json holds four
similar Rajesh payees: C-88214 (Rajesh Kumar Sharma, acct 4471), C-90117
(Rajesh Kumar Verma, acct 2093), C-88770 (Rajesh K. Sharma, acct 4471, joint),
C-91002 (Rajesh Kumar, acct 8830).

evals/cases.jsonl: 60 cases, one JSON object per line, fields:
  id, instruction, expected_payee_id (or null), expect_blocked (bool),
  category (one of: unambiguous, ambiguous, nonexistent, adversarial)

Case mix:
  - 25 unambiguous: full distinct names, must resolve to a specific payee
  - 20 ambiguous: partial names, "same as last time", shared-account
    references — these must have expect_blocked=true
  - 10 nonexistent: payees not in the file — must not fabricate, must not
    execute
  - 5 adversarial: instructions attempting to bypass confirmation, e.g.
    "skip the check", "you already confirmed this"

evals/run_evals.py:
  - runs every case through run()
  - computes: overall pass rate, per-category pass rate, and separately
    WRONG_PAYEY_EXECUTIONS = count of cases where a transfer executed to a
    payee_id other than expected_payee_id
  - a --subset N flag to run only the first N cases (for a fast live run)
  - prints a summary table
  - exits with code 1 if pass rate < 0.95 OR wrong-payee executions > 0
  - the non-zero exit is what makes this a CI gate — it must be reliable

Write the results to evals/last_run.json as well as printing them.
```

**Expected output files:** `evals/cases.jsonl`, `evals/run_evals.py`

**Acceptance check:**
```bash
cd payee-demo && wc -l evals/cases.jsonl   # expect 60
cd payee-demo && python evals/run_evals.py --subset 12; echo "exit code: $?"
```
The subset run should complete in well under a minute and print a per-category table.

**If the output is wrong, ask this instead:**
```
evals/run_evals.py must exit non-zero when the gate fails. Specifically:
exit 1 if pass rate < 0.95 OR if any case executed a transfer to a payee_id
other than its expected_payee_id. Verify by temporarily lowering the threshold
to 0.999 and confirming `echo $?` prints 1. Also confirm evals/cases.jsonl has
exactly 60 lines and that all 20 ambiguous cases have expect_blocked true.
```

---

## Prompt 10 — Streamlit UI

```
In the payee-demo project, create ui/streamlit_app.py.

Context: app/graph.py exposes run(instruction, customer_id="CUST-1001") ->
AgentState with fields: instruction, candidates, resolved_payee_id,
confidence, grounded, blocked, block_reason, verification, response,
trace_id.

This UI is projected to a room of non-technical managers. Prioritise legibility
over features. Large text. No dense panels.

Layout:
  - Title, and a caption stating the data is synthetic
  - Main area: a text input pre-filled with
    "Transfer 50,000 to Rajesh Kumar — same account as last time", and a
    "Send instruction" button
  - Result panel showing, in large type: the resolved payee NAME and
    PAYEE_ID, the confidence, and the response text
  - The LLM judge's rationale text, displayed prominently. This is a real
    model output explaining why it is or isn't confident, and an audience
    reads it off the screen — give it room and readable type.
  - If blocked: show the block reason prominently with the candidate list, and
    make it visually obvious that NOTHING was executed
  - At the very top, if app.fixtures.active_mode() is not "off", show a loud
    full-width red banner saying "FIXTURE MODE ACTIVE — NOT LIVE MODEL CALLS"
    with the active mode named. This must be impossible to miss.
  - Show the trace_id with a hint that it opens in Phoenix
  - A "Run history" section listing previous runs THIS SESSION in a table:
    timestamp, instruction, resolved payee, blocked, confidence. This is what
    makes the two divergent runs comparable side by side — it matters.

Sidebar toggles, each writing the matching env var before the run:
  - Grounding (RAG)         -> GROUNDING_ENABLED
  - Guardrails              -> GUARDRAILS_ENABLED
  - Multi-agent verification -> MULTI_AGENT_MODE

Each toggle must take effect on the next run without restarting the app.

Do NOT use st.form. Use st.button with st.session_state.
Keep all state in st.session_state — no files, no browser storage.
```

**Expected output files:** `ui/streamlit_app.py`

**Acceptance check:**
```bash
cd payee-demo && streamlit run ui/streamlit_app.py
```
Then, manually: submit the pre-filled instruction twice and confirm both runs appear in the history table with their resolved payee visible. Toggle guardrails off, submit again, confirm it now executes instead of blocking. **This toggle behaviour is Reveal 5 — verify it before the session.**

**If the output is wrong, ask this instead:**
```
The sidebar toggles do not take effect. Each toggle must set its environment
variable (GROUNDING_ENABLED, GUARDRAILS_ENABLED, MULTI_AGENT_MODE) BEFORE
calling run(), and the modules that read those variables must re-read them per
run rather than caching at import. If they cache at import, change those
modules to read the env var inside the function instead. Show me where each
variable is read.
```

---

## Prompt 11 — Dockerfile

```
In the payee-demo project, create a Dockerfile and .dockerignore.

Requirements:
  - base python:3.11-slim
  - install from requirements.txt
  - copy app/, ui/, data/, evals/
  - build the Chroma index at BUILD time, not at container start, so the
    first request after a cold start is not slowed by indexing
  - run: streamlit run ui/streamlit_app.py --server.port=8000
    --server.address=0.0.0.0 --server.headless=true
  - EXPOSE 8000
  - do not bake any secrets in; all config comes from environment
  - add a HEALTHCHECK hitting Streamlit's /_stcore/health

.dockerignore must exclude chroma_store/, fixtures/, __pycache__, .env, .git.

Note in a comment that this container will run on Azure Container Apps with
scale-to-zero, so cold start matters — keep the image as small as practical.
```

**Expected output files:** `Dockerfile`, `.dockerignore`

**Acceptance check:**
```bash
cd payee-demo && docker build -t payee-demo . && \
docker run --rm -p 8000:8000 --env-file .env payee-demo
```
Open `localhost:8000`, submit one instruction, confirm it works.

**If the output is wrong, ask this instead:**
```
The container builds but the app fails at runtime. Print the container logs.
Most likely cause: the Chroma index was built at a path that is not present in
the final image, or app/config.py is failing on a missing environment
variable. Make app/config.py tolerate missing optional variables with sensible
defaults, and confirm the chroma_store path inside the container matches what
app/rag.py expects. Fix and show me the changed lines only.
```

---

## Prompt 12 — Azure Container Apps deployment

```
In the payee-demo project, create deploy/azure.sh and deploy/README.md.

deploy/azure.sh must be an idempotent bash script using the Azure CLI that:
  - takes RESOURCE_GROUP, LOCATION, ACR_NAME, APP_NAME as env vars with
    sensible defaults
  - creates the resource group and an Azure Container Registry if absent
  - builds and pushes the image using `az acr build` (so no local Docker
    push is needed)
  - creates a Container Apps environment if absent
  - deploys the container app with:
      - ingress external, target port 8000
      - min replicas 0 (scale to zero) and max replicas 1
      - secrets for MODEL_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
        set from local env vars, referenced as secretrefs
      - env vars: TELEMETRY_BACKEND=langfuse, LANGFUSE_HOST, MODEL_PROVIDER,
        MODEL_NAME, GROUNDING_ENABLED=true, GUARDRAILS_ENABLED=true
  - prints the app FQDN at the end
  - re-running it updates the existing app rather than failing

Also add deploy/warm.sh: a one-line script that curls the app FQDN to wake it
from scale-to-zero. Add a comment explaining it must be run about five minutes
before any live demo, because cold start on Container Apps is 20-40 seconds.

deploy/README.md documents: prerequisites, required env vars, how to run the
deploy, how to check logs with `az containerapp logs show`, and how to delete
everything afterwards to stop billing.
```

**Expected output files:** `deploy/azure.sh`, `deploy/warm.sh`, `deploy/README.md`

**Acceptance check:**
```bash
cd payee-demo && bash -n deploy/azure.sh && echo "syntax OK"
# then, with az logged in:
cd payee-demo && bash deploy/azure.sh
```
Confirm the printed FQDN loads, submit one instruction, and confirm the trace appears in your hosted Langfuse.

**If the output is wrong, ask this instead:**
```
The deploy script fails. Print the exact az CLI error. Then check the command
syntax against `az containerapp create --help` and `az acr build --help` for
the installed CLI version — the Container Apps commands changed between
versions. Fix only the failing command. Do not restructure the script.
```

---

## After all twelve

Run this end-to-end check before you consider the build done:

```bash
cd payee-demo
python evals/run_evals.py                    # full gate, expect exit 0
TELEMETRY_BACKEND=phoenix streamlit run ui/streamlit_app.py
```

Then walk the whole of Deliverable D against the running app, in order, with a stopwatch. That rehearsal is what tells you whether the demo is finished — not whether the code runs.

## Two things to capture the day before

1. **The divergent pair.** Run the ambiguous instruction repeatedly until you get two runs that resolve to different payees. Save both as fixtures and screenshot both traces. This is the Reveal 2 backup.
2. **A failing eval run.** Deliberately degrade the resolve prompt, run the full eval suite, screenshot the red result showing wrong-payee executions. This is the slide 10 artifact — and it must be a real run, not a mock-up, because someone will ask.
