# Bank Transaction Scenario — an AI agent you can run yourself

This is the live demo from the session **Managing the Lifecycle of AI-Enabled
Products and Agents**. It is a small banking assistant that takes an instruction
like *"Transfer 50,000 to Rajesh — same account as last time"*, works out which
saved payee is meant, and **refuses to move money when it can't be sure**.

It shows, in about a thousand lines of Python, the ideas from the session:
an agent built with LangGraph, retrieval (RAG), a two-layer guardrail
(deterministic rules + an AI judge), an optional second agent that
independently double-checks the first, traces you can inspect, and an eval
suite that works as a CI gate.

> **All data is synthetic.** Every name, account number and transfer is
> generated. Nothing corresponds to a real person, account or bank.

---

## What you need

| | |
|---|---|
| **Git** | to clone the repository |
| **Python 3.11** | tested version. Don't have it? [`uv`](https://docs.astral.sh/uv/) installs it for you (step 2) |
| **A model API key** | your own — OpenAI, Anthropic, or any OpenAI-compatible provider (step 3) |
| Docker | *optional* — only if you prefer running it in a container |

You do **not** need Langfuse, Azure, or any other account. Everything runs on
your machine except the calls to your chosen model.

**Cost:** measured on `gpt-4o-mini`, one instruction costs roughly
**$0.0001–0.0003** (1–3 model calls). Trying every scenario below costs well
under one US cent.

---

## 1. Clone

```bash
git clone https://github.com/vinodpungle546/ai-session.git
cd ai-session/payee-demo
```

All commands below run from this `payee-demo` folder.

## 2. Create a Python environment

**Option A — with `uv`** (fastest; downloads Python 3.11 if you don't have it):

```bash
uv venv --python 3.11 .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

**Option B — plain Python 3.11:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> **Always activate the environment first** (`source .venv/bin/activate`).
> If you later see `command not found: python` or `No module named …`, you
> skipped that step in a new terminal.

## 3. Add your own model key

```bash
cp .env.example .env                 # Windows: copy .env.example .env
```

Open `.env` and set the four `MODEL_*` lines for **one** of these providers.
Leave every other line as it is — the Langfuse lines are unused.

**OpenAI** (the configuration used in the session)

```ini
MODEL_PROVIDER=openai_compatible
MODEL_NAME=gpt-4o-mini
MODEL_API_KEY=sk-...your key...
MODEL_BASE_URL=
```

**Anthropic**

```ini
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-haiku-4-5-20251001
MODEL_API_KEY=sk-ant-...your key...
MODEL_BASE_URL=
```

**Any OpenAI-compatible endpoint** — set `MODEL_BASE_URL` to the provider's URL:

| Provider | `MODEL_BASE_URL` | `MODEL_NAME` example |
|---|---|---|
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` |
| Ollama (local, free) | `http://localhost:11434/v1` | `llama3.1` — set `MODEL_API_KEY=ollama` |
| LM Studio (local, free) | `http://localhost:1234/v1` | the model you loaded |

Only OpenAI was tested end-to-end with this build; the others use the same
standard interface.

**Three rules for `.env`:**

1. **Never commit it or share it** — it holds your key. It is already listed in
   `.gitignore`.
2. **No comments on the same line as a value.** `MODEL_NAME=gpt-4o-mini  # fast`
   works when running locally but breaks under Docker, which reads the comment
   as part of the model name.
3. **Use a capable model.** The agent asks the model for strict JSON answers.
   Small local models often don't comply, and when an answer can't be parsed
   the guardrail *fails safe* — it blocks. If every instruction is refused,
   try a stronger model before assuming the code is broken.

## 4. Run it

```bash
streamlit run ui/streamlit_app.py
```

Open **<http://localhost:8501>**.

The **first** instruction takes 20–60 seconds longer than usual: it downloads a
small (~79 MB) embedding model and builds the local search index. This happens
once; afterwards each instruction takes a few seconds.

---

## 5. Try the scenarios

Use the three buttons under the instruction box, and the switches in the
sidebar. Each run is added to **Run history** at the bottom so you can compare.

| Try | How | What you should see |
|---|---|---|
| **An ambiguous instruction** | **Ambiguous** button → *Send instruction* | **NO TRANSFER WAS MADE.** Four saved payees are called some variant of "Rajesh", and two share an account ending **4471** — so the agent refuses and shows the judge's reasoning |
| **A clear instruction** | **Clear payee** button → Send | Transfer to *Rajesh Kumar Verma (C-90117)* goes through, with a reference number |
| **Switch the guardrail off** | untick **Guardrails**, then the Ambiguous instruction again | The same risky instruction now **executes** — and the confidence reads "—" because no check ran |
| **Two agents disagree** | tick **Multi-agent verification** → **Agents disagree** button → Send | Blocked by the second agent: that payee has *never* been paid, so "same account as last time" can't be true. Untick multi-agent and send again — it executes |
| **Grounding (RAG)** | untick **Guardrails**, then type `What is the account number for Rajesh Kumar Iyer?` and send with **Grounding** off, then on | Off: a generic refusal. On: *"I have no record of that payee"* — an answer based on the actual records |

For the grounding question, keep **Guardrails off**: a question has no payee to
check, so with guardrails on the app shows a "no transfer" panel instead of
the model's answer.

---

## 6. Optional — see inside each run (Phoenix traces)

[Arize Phoenix](https://phoenix.arize.com/) shows every step of a run — each
model call, tool call and retrieval — as a clickable tree. Start it in a second
terminal **before** sending instructions:

```bash
# with uv (runs Phoenix on its own Python, see note below)
uvx --python 3.12 --from arize-phoenix phoenix serve

# or with Docker
docker run -p 6006:6006 arizephoenix/phoenix:latest
```

Open **<http://localhost:6006>**, send an instruction in the app, and the new
trace appears (sort by start time, newest first). Compare a blocked run with an
executed one: the blocked trace has **no `execute_transfer` step at all**.

> **Why not just `phoenix serve` from the project environment?** The Phoenix
> *server* has a bug on Python 3.11 and won't start. The demo itself is
> unaffected — it only sends traces — so run Phoenix separately as above.
> If Phoenix isn't running, the app works exactly the same; traces are simply
> not collected.

## 7. Optional — run it in Docker

```bash
docker build -t bank-transaction-demo .
docker run --rm -p 8000:8000 --env-file .env \
  -e PHOENIX_ENDPOINT=http://host.docker.internal:6006/v1/traces \
  bank-transaction-demo
```

Open **<http://localhost:8000>**. The `PHOENIX_ENDPOINT` line lets the
container send traces to Phoenix on your machine — inside a container,
`localhost` means the container itself. (On Linux, add
`--add-host=host.docker.internal:host-gateway`.) If you use a local model such
as Ollama, point `MODEL_BASE_URL` at `http://host.docker.internal:11434/v1`
for the same reason.

The first build takes several minutes; the image is about 2.5 GB. For a
smaller 1.8 GB image, add `--build-arg REQUIREMENTS=requirements-container.txt`.

## 8. Optional — run the evaluation suite

Sixty test instructions with known correct answers — the "regression suite"
from the session:

```bash
python evals/run_evals.py --subset 12     # quick: first 12 cases
python evals/run_evals.py                 # all 60 (~1 minute, about 1 cent)
```

It prints a pass rate per category, and **exits with an error if the pass rate
is below 95% or if even one transfer went to the wrong payee**. That exit code
is what makes it usable as a CI gate. Try it with a different model and compare
the numbers.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: python` / `No module named streamlit` | activate the environment: `source .venv/bin/activate` |
| **Every** instruction is refused, even the clear one | the model call is failing, and the guardrail fails safe. Check your key, check `MODEL_NAME` is a real model for your provider, check for comments on the same line in `.env`, or try a more capable model |
| `401` / `Incorrect API key` in the terminal | wrong or expired key in `.env` |
| First instruction very slow | expected once — it downloads the embedding model |
| Nothing appears in Phoenix | start Phoenix *before* sending instructions; with Docker, include the `PHOENIX_ENDPOINT` line |
| `pip install` fails | make sure you're on Python 3.11 (`python --version` inside the environment) |

---

## How it's built

| Piece | File |
|---|---|
| The agent (LangGraph) | `app/graph.py` |
| Tools — payee lookup, transfer | `app/tools.py` |
| Retrieval (RAG, Chroma, local embeddings) | `app/rag.py` |
| Guardrail — deterministic rules + AI judge | `app/guardrails.py` |
| Second agent — the independent verifier | `app/verifier.py` |
| Model selection (swap by config) | `app/config.py` |
| Tracing (OpenTelemetry) | `app/telemetry.py` |
| UI | `ui/streamlit_app.py` |
| Eval suite | `evals/` |
| Synthetic data | `data/` |

For the full technical walkthrough — design decisions, the data, and the
evaluation results — see [`payee-demo/README.md`](payee-demo/README.md).
To see the single-agent vs multi-agent code side by side, run
`python demo/show_modes.py`.
