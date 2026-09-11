# Managing the Lifecycle of AI-Enabled Products and Agents
## Deliverable A — Slide-by-Slide Outline

**Session length:** 40 min (35 min content + 5 min Q&A, running to ~42 with overflow)
**Audience:** Project managers and leadership, IT services organisation
**Demo stack:** LangGraph + LangChain, Arize Phoenix (local traces), Langfuse (hosted, cost), Streamlit UI
**Live demo total:** ~12 min across 5 short reveals

**Notation used below**
- `[REVEAL n]` — a live demo moment. Full choreography comes in Deliverable D.
- `[ILLUSTRATIVE]` — a made-up figure, used for teaching. Confirmed approach: present these as illustrative and say the word out loud so nobody quotes them back at you in a steering committee.
- Timings in speaker notes are cumulative elapsed time.

**Running example: banking payee disambiguation**
One scenario carries the whole session. A retail banking assistant handles a fund-transfer instruction — *"transfer 50,000 to Rajesh Kumar"* — against a customer base containing several near-identical payees:

| Payee ID | Name | Account | Last transfer |
|---|---|---|---|
| C-88214 | Rajesh Kumar Sharma | ...4471 | 12 Aug |
| C-90117 | Rajesh Kumar Verma | ...2093 | never |
| C-88770 | Rajesh K. Sharma | ...4471 (joint) | 3 Sep |
| C-91002 | Rajesh Kumar | ...8830 | 22 Jul |

The agent must pick one. Sometimes it picks a different one than it did a minute ago. This single scenario carries slides 2, 6, 9, 11 and 15, which means the audience learns one domain and then watches five different things go wrong and get fixed inside it — far more effective than five unrelated toy examples.

**Use fully synthetic data.** Generated names, generated account numbers, no connection to any real customer master. Say this out loud once, early — a banking-adjacent audience will wonder, and answering before they ask is worth more than answering after.

**Positioning against the parallel sessions**
The tech team is already running manager sessions on LLM fundamentals and productivity tools. This session sits *above* those: not what the technology is, but how you deliver, test, sign off and pay for it. Say this explicitly on slide 3 so nobody spends the first five minutes wondering whether they're in the wrong room. It also lets you cut the recap on slide 4 short with a clean justification.

---

## Slide 1 — Title

**Title:** Managing the Lifecycle of AI-Enabled Products and Agents
**Subtitle:** Making non-deterministic software deliverable

**Key points**
- Your name, role, date
- One line: "Everything you're about to see is running live, not recorded."

**Visual:** Plain title slide. No stock robot imagery — it signals hype and this audience has seen enough of it.

**Speaker notes (0:00–0:30)**
Keep this to fifteen seconds. Do not introduce yourself at length; the audience knows you. Say the one line about it being live — it buys attention for the next four minutes.

---

## Slide 2 — "Transfer 50,000 to Rajesh Kumar"

**Key points**
- The instruction. The four candidate payees. The agent picks one.
- Run it again, unchanged: it picks a different one.
- Nothing was broken. No code changed. No configuration differed.
- Traditional software: same input → same output, every time. That contract is how we test, estimate and sign off.
- AI-enabled software breaks that contract by design.

**Visual:** The instruction in large type at the top. The four-row payee table beneath it. Two result badges below that — *Run 1: C-88214* and *Run 2: C-88770* — in red.

**Speaker notes (0:30–2:00)**
The hook. Spend the full ninety seconds; it buys you the rest of the session.

Read the instruction aloud, then read the four names aloud slowly. Let the room notice the problem before you state it — someone will visibly react at "Rajesh K. Sharma" sharing an account with "Rajesh Kumar Sharma". That reaction is what you want.

Then the sentence the whole session rests on: *"There is no defect to raise here. Nobody wrote bad code. This is the system working exactly as designed."*

Most of the room assumes AI output is flaky because someone did a poor job. Break that assumption now or nothing after slide 7 lands.

Say the synthetic-data line here, in one sentence, then move on: *"Generated names, generated accounts, nothing from any real system."*

If a delivery pod has a genuine near-miss of this shape and you're permitted to describe it, use it — it will beat anything synthetic. Sanitised and verbal, no slide.

---

## Slide 3 — Why this lands on your desk

**Key points**
- Estimation: "done" is no longer binary, so story points based on a definition of done that assumes repeatability will drift
- Testing: pass/fail assertions don't hold; you need statistical acceptance instead
- Sign-off: what does UAT mean when the system may answer differently on the day?
- Support: reproducing a customer-reported issue may be impossible
- Cost: unlike traditional software, per-transaction cost is variable and can be driven up by your own quality measures

**Visual:** Five-row table — column 1 "Traditional delivery", column 2 "AI-enabled delivery". Keep the rows to five words each.

**Speaker notes (2:00–4:00)**
This slide is the argument for why they should stay awake. Do not solve anything here — just name the five places where their existing process quietly stops working. Land it with: "Nothing today is about the model. It's about the five rows on the right."

Watch the room on the Support row; that's usually where heads start nodding, because someone has already lived it.

**Position against the parallel sessions here, in two sentences:** *"The tech team's sessions cover what these models are and how to use the productivity tools. This one starts one layer up — you already know it's non-deterministic, so how do we estimate it, test it, sign it off and pay for it?"* Delivered early, this stops anyone deciding they've heard this material before, and it makes the short recap on the next slide feel deliberate rather than thin.

---

## Slide 4 — What's actually inside an "agent"

**Key points**
Each component named against what it does in the transfer scenario:
- **Brain** — the model. Decides which Rajesh the instruction meant. Interchangeable, and cheaper than you think.
- **Memory** — that this customer transferred to C-88214 last month. Short-term (this conversation) vs long-term (persisted).
- **Tools** — payee lookup, balance check, the transfer API itself. This is where an agent stops being a chatbot and starts moving money.
- **Skills** — the packaged disambiguation procedure. Reusable know-how, versioned like code.
- **Harness** — what stops it executing the transfer when confidence is low. Covered on the next slide because it matters most.

`[REVEAL 1]` — Live trace showing all five components lighting up on a single request.

**Visual:** Simple five-box diagram, then cut to the live Phoenix trace. Draw the diagram so the boxes match the span names the audience will see in the trace — visual continuity does the teaching work for you.

**Speaker notes (4:00–10:00)**
Slides 4 and 5 together get six minutes, of which ~2.5 is the live reveal.

Do the diagram in **sixty seconds, not ninety** — with the fundamentals sessions running in parallel, a chunk of this room has seen the five boxes already. Name each one against the transfer scenario and move. If you sense the room is ahead of you, skip the brain and memory bullets entirely and go straight to tools: *"You've seen these. The one that changes the risk conversation is tools, because that's the box that moves money."*

Then switch to Phoenix and walk one trace top to bottom, pointing at each span as it maps to a box you just drew. The line that works: *"This isn't a diagram of how it might work. This is the actual transfer request I just sent, and every box is a row you can click."*

The point being made is not "look how clever agents are." It's *"this is inspectable"* — which is the foundation for everything in the second half.

---

## Slide 5 — The harness is the product

**Key points**
- The model is a component you can swap. The harness is what your team actually builds and owns.
- What it does: routes steps, enforces output structure, retries on failure, validates before acting, stops runaway loops
- In our scenario it's the difference between *"I've transferred 50,000 to Rajesh Kumar Sharma"* and *"I found four matching payees — which one?"* Same model. Same data. Entirely different product.
- Two teams using the identical model can ship products of wildly different reliability — the harness is the difference
- Consequence for planning: budget engineering effort for the harness, not for "integrating the AI"

**Visual:** Same five-box diagram, harness highlighted and everything else greyed out.

**Speaker notes (continues to 10:00)**
This is the slide senior leadership should remember. The framing that works with them: *"When a vendor tells you they've built an AI product, ask what their harness does. If the answer is a description of the model, they've bought a component and called it a product."*

Also flag the cost angle here in one sentence — it sets up slide 16: a strong harness lets you run a cheaper model, which is exactly the trade-off we make internally.

---

## Slide 6 — Non-determinism, live

**Key points**
- The transfer instruction, submitted twice, unchanged, in front of you
- Point at what diverged — the selected payee — and what didn't: the amount, the format, the confident tone
- The confidence is identical in both runs. That's the dangerous part.
- Temperature is only part of it; retrieval order, tool response timing and context assembly all contribute
- Even at temperature zero you do not get a guarantee

`[REVEAL 2]` — The transfer instruction submitted twice. Different payee selected. Divergence highlighted.

**Visual:** Split-screen Streamlit, two runs. Minimal slide furniture — the app is the slide.

**Speaker notes (10:00–14:00)**
Deliverable D will specify the exact input, but the shape is settled: payee disambiguation is genuinely ambiguous, so the runs will diverge reliably. A factual lookup would return the same answer twice and destroy the moment — this won't.

The sentence that does the work here is about tone, not correctness: *"Look at how certain it sounds. Both times. It isn't hedging in either run, and if you were the customer you'd have no way to tell which one you got."* Managers can absorb "sometimes wrong". "Confidently wrong, differently, each time" is what actually changes their behaviour.

Have the pre-captured pair ready on a second tab. If the live runs happen to agree, say so cheerfully and switch: *"They agreed that time — which is exactly the problem. It's not reliably wrong, it's unreliably right."* That recovery is stronger than the planned version, so genuinely don't panic.

Then the pivot line into the next slide: *"So we can't eliminate this. The question is what we do instead."*

---

## Slide 7 — You don't get determinism. You get bounded variance.

**Key points**
- Chasing true determinism is the wrong goal and an expensive one
- The achievable goal: variation constrained to a range you've measured and accepted
- Reframes three things — acceptance criteria become statistical, testing becomes sampling, sign-off becomes a threshold
- Example acceptance criterion for our scenario: "correct payee on 95% of the 200-case eval set, and **zero** wrong-payee executions without confirmation" `[ILLUSTRATIVE]`
- Note the asymmetry: the second half of that criterion is absolute. Some failure categories don't get a tolerance band, and deciding which is a business decision, not a technical one.

**Visual:** Two distribution curves — wide and unconstrained vs narrow and inside a tolerance band. Label the band "acceptable".

**Speaker notes (14:00–16:00)**
The conceptual centre of the session. If the audience takes one idea home, this is it.

The analogy that works with a delivery audience: manufacturing tolerance. We never demanded that two machined parts be atomically identical — we specified a tolerance and measured against it. Same move here.

Warn them explicitly: a stakeholder demanding 100% consistency is asking for something the technology cannot provide at any budget, and your job is to renegotiate that conversation early rather than discover it at UAT.

The 95% is illustrative — say so as you say it: *"That number's made up for the example; the real one comes from the business."* Otherwise it will reappear in someone's steering pack as a committed target.

The asymmetry bullet is worth an extra fifteen seconds. It's the bridge to the guardrails discussion, and it gives risk-minded attendees somewhere to put their concern.

---

## Slide 8 — The toolkit

**Key points**
Five levers, with an honest note on what each does *not* fix:
- **Structured outputs** — fixes format drift. Does not fix wrong content.
- **RAG / grounding** — fixes "makes things up about our domain." Does not fix bad reasoning over good facts.
- **Guardrails and validation** — fixes unsafe or malformed actions reaching production. Adds latency and cost.
- **Evals** — fixes "we changed something and didn't notice it got worse." Requires ongoing maintenance.
- **Human-in-the-loop** — fixes the high-consequence tail. Caps your throughput.
- Full catalogue is in the handout

**Visual:** Five rows, three columns — Lever / Fixes / Doesn't fix. The third column is the one they'll photograph.

**Speaker notes (16:00–17:30)**
Ninety seconds, deliberately brisk — this is a map, not the territory. Say out loud that the third column is the honest one and it's the reason you're not going to promise them a silver bullet.

Point at the handout. Resist elaborating; you need the time for the reveal.

---

## Slide 9 — Grounding and catching a hallucination

**Key points**
- Run 1: ungrounded. Asked about a payee that doesn't exist, the system invents a plausible account number rather than saying it can't find one.
- Run 2: same question, grounded against the customer master. Correct — and the trace shows exactly which record it retrieved.
- Run 3: the confidence check firing on an ambiguous match, blocking the transfer and forcing a confirmation instead of executing
- What the manager sees: not "the AI got it right", but *the receipt* — the retrieved record, in the trace, clickable

`[REVEAL 3]` — Three-part sequence: hallucinate, ground, catch.

**Visual:** Live throughout. Slide is a holding frame with three labels: Hallucinate → Ground → Catch.

**Speaker notes (17:30–23:00)**
Longest reveal, ~3.5 min. It's the payoff of the whole first half, so don't rush the middle step.

Part one is the strongest single moment in the session — an invented account number for a customer who doesn't exist. Read the fabricated number aloud. It looks completely legitimate, which is the entire point.

The sentence to say while the retrieval span opens in part two: *"This is the bit that changes the audit conversation. We're not asking anyone to trust the answer — we can show which record it came from, on which run, at which timestamp."* In a banking context that sentence is worth more to leadership than any accuracy statistic.

For part three, make sure the audience sees the check **rejecting** the transfer and asking for confirmation, not merely scoring it low. A blocked action is visceral; a confidence score is abstract. Tie it back to slide 7's absolute criterion.

Fallback: pre-captured traces for all three runs on a second Phoenix tab.

---

## Slide 10 — Evals: the regression suite you don't have yet

**Key points**
- A fixed set of inputs with known-good expectations, run on every change
- Catches the thing that will otherwise hurt us most: a prompt tweak that fixes one case and silently breaks eleven
- Belongs in the pipeline, not in someone's notebook
- For our scenario the eval set is a list of instructions with the payee that *should* be selected — including the nasty ones: the joint account, the initial-only variant, the never-used payee
- Delivery consequence: build eval-set creation into the estimate from day one. It is not a testing afterthought, it is a deliverable with its own effort.
- Rough shape: 100–300 cases for a first production feature, growing with every incident `[ILLUSTRATIVE]`

**Visual:** Pipeline diagram — commit → eval run → gate → deploy. Show a failed gate in red.

**Speaker notes (23:00–24:30)**
This is the most actionable slide for the PMs specifically, because it's a line item they control.

The line that gets budget approved: *"If a team tells you they've improved the prompt, the only correct next question is 'what did the eval set say?' If there isn't one, they don't know whether they improved it."*

---

## Slide 11 — Multi-agent: when it earns its keep, and when it doesn't

**Key points**
- **Earns it:** genuinely separable responsibilities, different tools per role, one agent's output checkable by another. In our scenario: one agent resolves the payee, a second independently verifies the resolution against the master record before the transfer executes. The check is real because the checker didn't make the original decision.
- **Doesn't:** a single linear task split up because multi-agent sounds sophisticated
- Costs of splitting: more calls, more tokens, more latency, more places to fail, harder to trace
- The honest heuristic: start with one agent and a good harness. Split only when you can name the specific thing the split fixes.

`[REVEAL 4]` — Multi-agent handoff visible in the trace, with the token cost delta against the single-agent run.

**Visual:** Two traces side by side — single-agent and multi-agent — with total token count and duration visible on both.

**Speaker notes (24:30–27:00)**
~2 min of reveal. The cost delta on screen does the arguing for you. Say the number out loud.

This slide will get pushback from anyone who has been sold a multi-agent platform, and that's a good thing — it's the moment leadership realises architecture choices have a line on the invoice. If someone challenges you, the safe response is: *"I'm not saying never. I'm saying the split needs a reason you can state, and here's what it costs when there isn't one."*

---

## Slide 12 — What changes in the delivery lifecycle

**Key points**
Stage by stage, what's different:
- **Requirements** — specify acceptable behaviour ranges and failure modes, not just features
- **Estimation** — add explicit effort for eval sets, harness, and observability. Prompt iteration is unpredictable; timebox it rather than estimating it.
- **Testing** — sampling and thresholds replace assertions; the eval set is the test suite
- **Release** — canary and staged rollout become close to mandatory, because you cannot fully test in advance
- **Support** — capture the trace, not just the screenshot. Without it the issue is unreproducible.

**Visual:** Five-stage horizontal lifecycle bar, one change annotated under each.

**Speaker notes (27:00–29:00)**
This is the "so what do I do Monday" slide for the PM half of the room.

The Support point is worth ten extra seconds — tell them to change their bug template now to require a trace ID. It's a small, free, immediately actionable change and it makes you look practical.

---

## Slide 13 — Vibe coding: what your developers are already doing

**Key points**
- Developers on our teams are already using AI coding agents to build features and fix bugs. This is happening whether or not it's on your plan.
- The productivity is real. So is the review debt.
- Five signals to monitor:
  - Review discipline — is generated code reviewed at the same standard, or waved through because it looks clean?
  - Test coverage — are tests written for the behaviour, or generated alongside the code and therefore blind to the same mistakes?
  - Provenance — do we know what was AI-authored? We will want to know during an incident.
  - Scope creep — agents helpfully do more than asked; diffs grow quietly
  - Silent dependencies — new packages appear without a procurement or security conversation
- Practices for developers are in the handout

**Visual:** Two columns — "What the developer does" / "What you should be able to see". Five rows.

**Speaker notes (29:00–31:00)**
Two minutes, and pitch it carefully. The failure mode is sounding like you want to police developers — that reads badly and it isn't the point.

Frame it as: these are the five things that used to be guaranteed by the pace of hand-writing code, and aren't any more. The diff size point tends to land hardest because managers have seen a 40-file pull request appear overnight and felt uneasy without being able to say why.

---

## Slide 14 — Observability: what you should be able to see

**Key points**
- Per request: which steps ran, what was retrieved, which tools were called, what was rejected
- Aggregate: failure rate, hallucination-check trip rate, latency, cost per transaction
- Manager's version of the dashboard is four numbers, not four hundred traces
- Production recommendation: this is OpenTelemetry, exported to Azure Application Insights — the same pipeline our existing applications already use. This is not a new tooling silo.

**Visual:** Langfuse dashboard, hosted instance. Then a single slide showing the same signals in App Insights.

**Speaker notes (31:00–32:30)**
The App Insights point is aimed squarely at leadership and it's the reassurance line of the session: *"We are not asking for a new observability stack. We're asking for the AI-specific fields to flow into the one we already pay for."*

Keep the dashboard tour short. Four numbers, name each one, move on.

---

## Slide 15 — Where the money actually goes

**Key points**
- Cost is per-transaction and variable, so volume growth and quality measures both push it up
- The counter-intuitive part: the things that make output more reliable — retries, validation passes, larger retrieved context, multi-agent handoffs, running evals in CI — all add cost
- Live: the same request with guardrails off vs on, with the token cost of each shown
- Plus the infrastructure line: the hosted demo itself, and what it costs to leave running

`[REVEAL 5]` — Langfuse cost view, guardrails off vs on.

**Visual:** Langfuse per-trace cost comparison, live.

**Speaker notes (32:30–34:00)**
Short reveal, ~1.5 min. One number vs another number.

Frame it in the scenario: *"This is what it costs to be sure we're paying the right Rajesh."* The verification agent, the grounding retrieval and the confidence check are all visible in the cost delta — the audience watched each one get added, so the number arrives already explained.

The framing sentence: *"Reliability isn't free, and it doesn't show up in the project budget — it shows up in run cost, every month, forever."* That distinction between capex-shaped and opex-shaped spend is the thing leadership will actually act on.

The per-transaction figure on screen is real (it's a live trace), but any extrapolation you do to annual volume is illustrative — say so if you extrapolate.

---

## Slide 16 — Controlling it

**Key points**
- Cheaper model plus a strong harness will often beat an expensive model with a weak one — this is exactly the pattern we use internally, defaulting to a fast model and escalating only when quality demands it
- Route by difficulty: don't send every request to the most capable model
- Cache aggressively — repeated context is repeated spend
- Cap retries and set hard loop limits; runaway agents are a cost incident, not just a bug
- Scale to zero on non-production environments
- Set a per-feature cost budget at design time, and treat breaching it as a design defect

**Visual:** Six levers as a simple list. No diagram needed.

**Speaker notes (34:00–35:00)**
Sixty seconds, brisk. The first bullet is the one to say slowly because it connects back to slide 5 and closes the loop on the harness argument.

The last bullet is the one to leave hanging — a per-feature cost budget is a governance ask, and if leadership picks it up in Q&A you've achieved something.

---

## Slide 17 — What to ask your teams

**Key points**
The checklist, abbreviated to six questions on screen:
1. What does "good enough" mean numerically for this feature?
2. Where's the eval set, and how many cases?
3. What happens when the model gets it wrong — who or what catches it?
4. Can you show me a trace of a real request?
5. What does this cost per transaction, and what's the ceiling?
6. Which parts of this code were AI-authored, and were they reviewed to the same standard?

Full one-page version is the handout.

**Visual:** Six numbered questions, large type. This is the photograph slide — make it legible from the back of the room.

**Speaker notes (35:00–36:30)**
Pause before you start. Tell them explicitly this is the slide worth photographing; people will get their phones out and you should let them.

Read them aloud, don't elaborate. The elaboration is the handout.

---

## Slide 18 — Close

**Key points**
- Three sentences, no more:
  - AI output varies by design; we manage the variance, we don't eliminate it
  - The harness, the evals, and the traces are what turn a model into a product we can sign off
  - Every one of those is a delivery line item, and that makes it yours
- Handout link / QR

**Visual:** Three lines of text. Nothing else.

**Speaker notes (36:30–37:00)**
Thirty seconds. Do not summarise the session — they were there. Say the three sentences and stop.

Then open Q&A with a specific question rather than a general one: *"Who here has a feature in flight that this applies to?"* is far better than "any questions?", which gets silence.

---

## Q&A — 37:00 to 42:00

Anticipated questions and answers are in Deliverable H. Keep the Langfuse dashboard on screen during Q&A rather than the closing slide — it invites more specific questions.

---

## Notes on what I cut, and why

- **Detailed determinism technique catalogue** — moved to the handout. On stage it becomes a list nobody retains.
- **Developer-level vibe coding practices** — moved to the handout. Wrong audience for the detail; they need the monitoring signals, not the practices.
- **A dedicated memory/RAG architecture slide** — folded into Reveal 3. The trace teaches it better than a diagram.
- **Vendor and build-vs-buy discussion** — deliberately out of scope for 40 minutes. Flag it as a follow-up session if leadership asks.

## Decisions resolved

1. **Running example** — banking payee disambiguation, fully synthetic data, threaded through slides 2, 4, 5, 6, 7, 9, 10, 11 and 15.
2. **Illustrative figures** — presented as illustrative, with the word said out loud at slides 7, 10 and 15.
3. **Styling** — clean neutral, corporate template to be applied by you afterwards.
4. **Overlap** — no repetition, but parallel fundamentals sessions are running. Positioning statement added to slide 3; the anatomy recap on slide 4 shortened to sixty seconds with an escape hatch if the room is ahead.

---

## Added after sign-off: agenda, conclusion, precautions

Three slides were added to the built deck. **All slide numbers above shift by one from the agenda onward** — the deck is now 21 slides. Mapping: outline slide *n* = deck slide *n+1* for everything from the old slide 2 onward.

### Deck slide 2 — Agenda: "Forty minutes, five live demos"

**Key points**
Six blocks with timings, five marked with a red dot for "includes a live demo":
1. The problem, live — why the same instruction gives a different answer (4 min)
2. Anatomy and the harness — what's inside an agent, and which part you own (6 min)
3. Making it predictable — bounded variance, grounding, hallucination checks, evals (11 min)
4. Multi-agent and lifecycle — when to split, what changes, vibe coding oversight (7 min)
5. Observability and cost — what you should see, and what reliability costs (4 min)
6. What to ask your teams — six questions, and the handout (3 min)

Footer: questions at the end or interrupt — either is fine.

**Speaker notes (0:30–1:00)**
Thirty seconds. Do not read the six rows aloud — they can read. Say only two things: that five of the six blocks contain a live demo so this isn't forty minutes of slides, and that the last block is the one to stay awake for because it's six questions they can use on Monday.

The interrupt invitation is deliberate. With this audience a question asked in the moment beats one saved for the end, and the demo beats give natural pause points.

### Deck slide 19 — Conclusion: "Where this leaves us"

Two columns.

**Left — key learnings**
1. Variance is managed, not eliminated — acceptance criteria need numbers, agreed before build
2. The harness, the evals and the traces are the deliverables that make an AI feature signable
3. Reliability lands in monthly run cost, not the project budget

**Right — action items for you**
- Add a trace ID field to the bug template for any AI-enabled feature
- Require an eval set, named with its case count, in every AI feature estimate
- Set a cost ceiling per feature at design time, and treat breaching it as a design defect

Closing line: none of these need budget; all three are process changes you already control.

**Speaker notes (36:30–37:30)**
Sixty seconds. This is the slide that converts a talk into a decision. The left column they've already heard — read the three headers only.

Spend the time on the right column, and land the closing line: no budget approval needed, which removes the usual reason to defer.

**Edit the three action items before presenting.** They follow from the session, but you know what will land in your organisation and what's already in flight. An item someone has already implemented makes you look out of touch; one needing a budget line gets parked. If leadership picks up the cost-ceiling one, that's the best available outcome from this session — it's the only one with governance teeth.

### Deck slide 20 — Precautions: "Six things to watch for"

Six warning cards, two columns:

| Precaution | The point |
|---|---|
| A demo is not a tested feature | It worked once. That's one sample. Ask what the eval set says. |
| "We improved the prompt" | Without eval evidence nobody knows whether it improved. Unverified change, not a fix. |
| 100% consistency as a requirement | Cannot be met at any budget. Renegotiate at requirements, not UAT. |
| What data goes into the prompt | Prompts and retrieval indexes are data flows. Which customer data leaves our boundary, to which provider? |
| Clean-looking generated code | AI-authored code reads well and reviews easily. That's the risk, not the reassurance. |
| Run cost after go-live | Reliability measures compound monthly. Can pass sign-off and still become a cost problem. |

Closing line: each of these has cost somebody a release, and none look like risks at the time.

**Speaker notes (37:30–38:30)**
Sixty seconds. Don't read all six — name the two most relevant to your portfolios and let them read the rest.

**The two worth saying aloud:**

*"A demo is not a tested feature"* — say this even though you've just spent twelve minutes demoing. It's the honest framing and it protects you. Someone in the room will otherwise walk out and tell a client we have this ready.

*"What data goes into the prompt"* — the compliance question nobody has asked yet. For banking-adjacent accounts somebody will eventually ask which customer data left our boundary and to which model provider. Better it comes from you now than from an audit later.

If you're short of time, this is the slide to compress to twenty seconds: *"Read these six — they're the ways this goes wrong quietly"* and move to the close.

### Timing consequence

The three additions cost 150 seconds. Content now runs to ~38:30 and the close lands at ~39:00, leaving three minutes of Q&A inside 42.

That's tight. Pick two of these before you present:
- **Trim slide 3** (the five-row table) by 30s — they read it faster than you can narrate it
- **Cut beat 3.5** in Reveal 3, which Deliverable D already nominates as first to drop (−25s)
- **Compress the precautions slide** to 20s using the line in its notes (−40s)
- **Cut Reveal 4 to beats 4.1–4.3**, dropping the side-by-side baseline comparison and just stating the number (−45s)
- **Accept a 44-minute session.** For a bi-weekly update with five live demos this is usually fine, but check whether your slot is hard-stopped.

My recommendation: compress precautions to 20s and trim slide 3. That returns 70 seconds, gets Q&A back to four minutes, and costs you nothing that matters.

## How the .pptx will be built, given you'll apply the template yourself

Because the corporate theme goes on afterwards, the deck has to be built so that applying it re-styles cleanly instead of scattering the layout. So:

- Every slide uses standard built-in layouts (Title, Title and Content, Two Content, Title Only, Blank) with real placeholders — **no floating text boxes** where a placeholder will do. Floating boxes ignore the incoming theme and are the main reason applied templates look broken.
- No hard-coded fonts or colours on body text; it inherits from the theme so yours takes over automatically.
- Where colour carries meaning — the red divergence highlights on slides 2 and 6 — it's applied explicitly and deliberately, and I'll list those slides so you can re-check them after applying the template.
- Speaker notes go in the notes pane, so they survive the template change untouched.
- 16:9, and body text no smaller than 18pt so it reads from the back.

One caveat worth knowing in advance: applying a corporate template to an existing deck usually still needs a pass through **Home → Layout** on a few slides to re-map them. Budget ten minutes for that rather than being surprised by it.

## Ready for B?

If the outline reads right, say go and I'll build the .pptx. If you want changes first — reordering, cutting a slide, more or less depth anywhere — mark them up now, since the deck gets built from whatever version you sign off.
