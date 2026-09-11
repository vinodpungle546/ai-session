# payee-demo

A banking **payee-disambiguation** demo: a LangGraph agent that resolves a
natural-language transfer instruction to exactly one payee, and refuses to act
when the instruction is genuinely ambiguous.

> ### All data in this repository is synthetic
> Every payee name, account number, transfer and customer-master document is
> generated for demonstration purposes. There are no real names, no real account
> numbers, and deliberately no bank names, IFSC codes or branch codes anywhere in
> `data/`. Nothing here corresponds to a real person or institution.

## The scenario

Customer `CUST-1001` has twelve saved payees. Four of them are called some
variant of "Rajesh Kumar":

| payee_id | name | account_last4 | joint | last transfer |
|---|---|---|---|---|
| C-88214 | Rajesh Kumar Sharma | 4471 | no | 2026-08-12 |
| C-90117 | Rajesh Kumar Verma | 2093 | no | never |
| C-88770 | Rajesh K. Sharma | **4471** | yes | 2026-09-03 |
| C-91002 | Rajesh Kumar | 8830 | no | 2026-07-22 |

**C-88214 and C-88770 are different accounts that share the last four digits
4471.** Masked, they are indistinguishable. So an instruction like

> "Transfer 50,000 to Rajesh — same account as last time"

has no safe answer, and the demo's guardrail is expected to block it rather than
guess. That block is the point of the whole build.

**Use "to Rajesh", not "to Rajesh Kumar".** `payee_lookup` matches on substring,
and "Rajesh K. Sharma" does not contain "Rajesh Kumar" — so the longer phrasing
never retrieves C-88770 and the shared-account collision cannot fire. It still
blocks, but for weaker reasons. This is the instruction the UI should pre-fill.

## Setup

Requires Python 3.11. If you do not have it, [`uv`](https://docs.astral.sh/uv/)
will fetch it for you.

```bash
cd payee-demo

# 1. Create the virtual environment (uv downloads CPython 3.11 if needed)
uv venv --python 3.11 .venv

# 2. Activate it  ── do not skip this
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install pinned dependencies
uv pip install -r requirements.txt   # or: pip install -r requirements.txt

# 4. Configure
cp .env.example .env                 # then edit .env and set MODEL_API_KEY
```

> **Activate the venv before running anything.** This project's checks invoke
> bare `python`, which on many macOS systems does not exist outside a virtual
> environment. If you see `command not found: python`, step 2 was skipped.

## Configuration

All configuration is environment-driven; see `.env.example` for the full list.
The two that decide how the demo behaves:

- **`MODEL_PROVIDER`** — `openai_compatible` or `anthropic`. The backend is
  swappable by config alone. Use `openai_compatible` with `MODEL_BASE_URL` for
  any OpenAI-protocol endpoint (vLLM, Ollama, GLM, Together, …).
- **`TELEMETRY_BACKEND`** — `phoenix` (local) or `langfuse` (hosted). The same
  instrumentation exports to either.

`app/config.py` never raises on import: every setting has a default, so a
missing variable degrades behaviour instead of breaking start-up.

### One dependency beyond the original spec

`requirements.txt` includes **`langchain-anthropic`**, which was not in the
project's original package list. It is required for `MODEL_PROVIDER=anthropic`
to work at all — without it, selecting the anthropic backend would raise on
import, and the backend would not genuinely be "swappable by config alone".
`get_llm()` imports both provider packages lazily, so the unused one is never
loaded.

## Verifying this step

With the venv activated, from the `payee-demo` directory:

```bash
python -c "
import json
p=json.load(open('data/payees.json'))
ids={r['payee_id'] for r in p}
assert {'C-88214','C-90117','C-88770','C-91002'} <= ids, 'missing core payees'
four=[r for r in p if r['payee_id'] in {'C-88214','C-88770'}]
assert all(r['account_last4']=='4471' for r in four), 'shared account not set'
assert len(p)>=12, 'payee list too small'
print('OK', len(p), 'payees')"
```

Check the model backend resolves:

```bash
python -c "from app.config import get_llm; print(type(get_llm()).__name__)"
```

## Tracing

Both backends receive the *same* OpenTelemetry instrumentation; only
`TELEMETRY_BACKEND` decides where spans go (`phoenix` or `langfuse`).

```bash
# local: start Phoenix, then run anything
phoenix serve                       # see the caveat below
TELEMETRY_BACKEND=phoenix python -c "from app.graph import run; print(run('Transfer 50,000 to Rajesh')['trace_id'])"
```

The span tree for one run:

```
payee_demo.run
  LangGraph
    parse_instruction
    lookup_candidates      -> payee_lookup            [tool]
    retrieve_context
    resolve_payee          -> skill.payee_disambiguation  [llm]
    confidence_gate        -> skill.confidence_judge      [llm]
    execute                -> execute_transfer        [tool]   (absent when blocked)
    compose_response
```

If the run was blocked, `execute` and `execute_transfer` are simply absent from
the trace -- the clearest possible evidence that nothing was paid.

> ### Phoenix's server does not run on Python 3.11
> `arize-phoenix` 20.9.0 declares `requires-python >=3.10`, but its server fails
> at import on 3.11: `phoenix/trace/dsl/filter.py` uses `MappingProxyType({})`
> as a dataclass default, which 3.11 rejects as a mutable default and 3.12+
> accepts. This is an upstream bug, not a problem with this project.
>
> The app is unaffected -- it just posts OTLP over HTTP -- so run the Phoenix
> *server* on a newer interpreter and leave the project on 3.11:
>
> ```bash
> uvx --python 3.13 --from arize-phoenix phoenix serve
> ```
>
> Or use the container: `docker run -p 6006:6006 arizephoenix/phoenix:latest`.

## Demo instructions

Three instructions, each demonstrating a different layer. Verified reliable over
repeated runs.

| purpose | instruction | expected |
|---|---|---|
| Guardrail blocks ambiguity | `Transfer 50,000 to Rajesh — same account as last time` | blocked; shared-account 4471 named |
| Happy path | `Transfer 50,000 to Rajesh Kumar Verma` | executes to C-90117 |
| Two agents disagree | `Transfer 50,000 to Rajesh Kumar Verma — the same account as last time` | single-agent **executes**; two-agent **blocks** |

The third is the multi-agent reveal. C-90117 has never received a transfer, so
"the same account as last time" is false of it — but the name matches perfectly,
so the resolver and the confidence judge both pass it. Only the independent
verifier, which checks the instruction against the candidate's own record,
catches the contradiction:

```bash
MULTI_AGENT_MODE=false python -c "from app.graph import run; \
  print(run('Transfer 50,000 to Rajesh Kumar Verma — the same account as last time')['response'])"
# -> Transferred 50,000.00 to Rajesh Kumar Verma (C-90117). Reference ...

MULTI_AGENT_MODE=true  python -c "from app.graph import run; \
  print(run('Transfer 50,000 to Rajesh Kumar Verma — the same account as last time')['response'])"
# -> I have not made this transfer. The two agents disagreed...
```

Measured 5/5 disagreement on this instruction and 5/5 agreement on the plain
control, so it is safe to run live.

## Presenting this

To show the single-agent vs multi-agent implementation:

```bash
python demo/show_modes.py             # topology, wiring, isolation, validation
python demo/show_modes.py --validation # how the verifier validates
python demo/show_modes.py --run        # ...plus run both modes live
```

`--validation` answers the sceptical question a technical room asks — "so it
just asks another model and trusts the answer?". It prints the verifier's real
system prompt, the deterministic post-checks that follow it, and demonstrates
the one that matters: a reply claiming `agrees: true` while naming a different
payee is recorded as a **disagreement**, because the code trusts the comparison
over the model's self-report. Only the default sections and `--validation` run
without a model; `--run` makes real calls.

Everything it prints is derived from the running code — topology from the
compiled graphs, source via `inspect`, the verifier's payload from the real
prompt builder — so it cannot drift from the implementation, and a technical
room can see it is the actual code rather than a slide.

The headline: **a second agent is one node and one edge.** Multi-agent mode adds
`verify` and reroutes `confidence_gate → execute` into
`confidence_gate → verify → execute`. Everything else is unchanged, and each
mode compiles its own graph, so single-agent traces stay exactly as they were.

Two projectable walkthroughs:

- **Single-agent vs multi-agent** — topology, wiring, isolation, validation:
  <https://claude.ai/code/artifact/e8b73809-c277-45d1-af13-36a3854c993c>
- **Anatomy of one instruction** — the end-to-end sequence diagram, every hop
  from typed sentence to executed transfer, and the three ways a run can end:
  <https://claude.ai/code/artifact/a6e6944e-bffc-4a9a-89ea-92780d5e1e0e>

## Container

```bash
docker build -t payee-demo .
docker run --rm -p 8000:8000 --env-file .env payee-demo
# then open localhost:8000
```

No local Docker? `colima` gives a working `docker` CLI without Docker Desktop:

```bash
brew install colima docker && colima start --cpu 4 --memory 6 --disk 40
```

The Chroma index is built **at image build time**, not at container start. The
embedding model is a ~79 MB download on first use, so building it lazily would
make the first request after a scale-to-zero cold start wait for it.

### Slim build (recommended for deployment)

`requirements.txt` contains `arize-phoenix`, which is the Phoenix **server**.
Nothing in the container imports it — tracing exports through
`opentelemetry-exporter-otlp`, and deployed instances send traces to Langfuse.
Omitting it drops **82 transitive packages**, measured as **660 MB off the
image** (2.46 GB -> 1.8 GB), including scipy and botocore:

```bash
docker build --build-arg REQUIREMENTS=requirements-container.txt -t payee-demo .
```

Verified by building and running both images: telemetry, instrumentation, the
graph and the Chroma index all work on the slim set (134 packages vs 216), and
the container reports healthy in ~2s either way.

### Notes

- Runs as non-root (`appuser`, uid 10001). The index and the model cache are
  written after the `USER` switch so they are owned by the runtime user —
  Chroma opens its SQLite store read-write even for queries.
- `HEALTHCHECK` uses the Python stdlib rather than installing `curl`.
- No secrets are baked in; `app/config.py` imports cleanly with an entirely
  empty environment.
- `.dockerignore` keeps the build context at ~0.1 MB (the venv alone is ~1 GB).

## Layout

```
payee-demo/
  app/
    config.py        # env-driven settings + get_llm()
  data/
    payees.json              # 12 synthetic payees for CUST-1001
    transfer_history.json    # 12 past transfers
    customer_master/*.md     # one document per payee — the RAG corpus
  evals/             # eval suite
  ui/                # Streamlit UI
  deploy/            # Azure Container Apps deployment
  requirements.txt
  .env.example
```

### Data invariants

Later components depend on these holding, so preserve them when editing `data/`:

- `C-88214` and `C-88770` **must** share `account_last4` `"4471"` — this is the
  ambiguity the demo exists to demonstrate.
- `C-90117` **must** have `last_transfer_date: null` and no rows in
  `transfer_history.json`, so it can never satisfy "same as last time".
- Exactly **four** payees have "Rajesh" in the name.
- For every payee, `last_transfer_date` equals the latest matching date in
  `transfer_history.json` (or is `null` when there are no transfers).
- `data/customer_master/` holds exactly one `<payee_id>.md` per payee.
