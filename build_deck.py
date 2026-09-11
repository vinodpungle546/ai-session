#!/usr/bin/env python3
"""Build Deliverable B: 40-minute managers' session deck (.pptx).

Source of truth: deliverable-A-session-outline.md (v1, unedited).
Styling: corporate-neutral, 16:9, readable at back of room.
Speaker notes included in the notes pane of every slide.
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# ---------------------------------------------------------------- palette ---
NAVY = RGBColor(0x1F, 0x2A, 0x44)      # titles
TEAL = RGBColor(0x0E, 0x7C, 0x7B)      # accent
DARK = RGBColor(0x2B, 0x2B, 0x2B)      # body text
GREY = RGBColor(0x6B, 0x72, 0x80)      # muted text / footers
LIGHT = RGBColor(0xF2, 0xF4, 0xF7)     # panel fill
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xB3, 0x3A, 0x3A)       # red-flag accent

FONT = "Calibri"
SW, SH = Inches(13.333), Inches(7.5)   # 16:9

prs = Presentation()
prs.slide_width, prs.slide_height = SW, SH
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- helpers ---
def add_slide():
    return prs.slides.add_slide(BLANK)


def add_text(slide, left, top, width, height, text, size, color=DARK,
             bold=False, italic=False, align=PP_ALIGN.LEFT, font=FONT,
             line_spacing=1.0, space_after=0):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    if space_after:
        p.space_after = Pt(space_after)
    run = p.add_run()
    run.text = text
    f = run.font
    f.name, f.size, f.bold, f.italic = font, Pt(size), bold, italic
    f.color.rgb = color
    return box


def add_rect(slide, left, top, width, height, fill=LIGHT, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top,
                                 width, height)
    shp.adjustments[0] = 0.06
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    shp.shadow.inherit = False
    return shp


def set_notes(slide, notes):
    slide.notes_slide.notes_text_frame.text = notes


def add_footer(slide, block_label, timing):
    add_text(slide, Inches(0.55), Inches(7.08), Inches(9.0), Inches(0.35),
             block_label, 11, color=GREY, italic=True)
    add_text(slide, Inches(11.2), Inches(7.08), Inches(1.6), Inches(0.35),
             timing, 11, color=GREY, italic=True, align=PP_ALIGN.RIGHT)


def add_header(slide, title, kicker=None):
    top = Inches(0.42)
    if kicker:
        add_text(slide, Inches(0.55), top, Inches(12.2), Inches(0.32),
                 kicker.upper(), 12, color=TEAL, bold=True)
        top = Inches(0.78)
    add_text(slide, Inches(0.55), top, Inches(12.2), Inches(0.75), title,
             28, color=NAVY, bold=True)


def bullets(slide, items, left=Inches(0.55), top=Inches(1.75),
            width=Inches(12.2), height=Inches(4.9), size=17,
            gap=10, lead_gap=14):
    """items: list of (level, text) tuples. level 0 = bullet, 1 = sub-bullet."""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    first = True
    for level, text in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(lead_gap if level == 0 else gap)
        p.line_spacing = 1.06
        p.level = level
        run = p.add_run()
        run.text = ("•  " if level == 0 else "–  ") + text
        f = run.font
        f.name = FONT
        f.size = Pt(size if level == 0 else size - 2)
        f.color.rgb = DARK if level == 0 else GREY
    return box


def panel(slide, left, top, width, height, heading, lines, heading_color=NAVY,
          body_size=15):
    add_rect(slide, left, top, width, height)
    add_text(slide, left + Inches(0.22), top + Inches(0.14), width - Inches(0.4),
             Inches(0.4), heading, 15, color=heading_color, bold=True)
    box = slide.shapes.add_textbox(left + Inches(0.22), top + Inches(0.55),
                                   width - Inches(0.4), height - Inches(0.7))
    tf = box.text_frame
    tf.word_wrap = True
    for i, (txt, color) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(6)
        p.line_spacing = 1.05
        run = p.add_run()
        run.text = txt
        run.font.name = FONT
        run.font.size = Pt(body_size)
        run.font.color.rgb = color


def note_text(header, body):
    return header + "\n" + body


# ======================================================== SLIDE 1 — title ===
s = add_slide()
add_rect(s, Inches(0), Inches(0), SW, Inches(2.6), fill=NAVY)
add_text(s, Inches(0.7), Inches(0.75), Inches(11.9), Inches(1.0),
         "Managing the Lifecycle of AI-Enabled Products and Agents",
         36, color=WHITE, bold=True)
add_text(s, Inches(0.7), Inches(1.75), Inches(11.9), Inches(0.6),
         "Making AI features behave predictably when the model doesn't",
         20, color=RGBColor(0xBF, 0xD4, 0xD4))
add_text(s, Inches(0.7), Inches(3.1), Inches(11.9), Inches(0.5),
         "Bi-weekly managers' update  ·  40 minutes including live demo",
         16, color=GREY)
add_text(s, Inches(0.7), Inches(3.6), Inches(11.9), Inches(0.5),
         "[Speaker name]  ·  [Date]", 16, color=GREY)

# coin-flip vs checklist motif, rendered as two simple panels
panel(s, Inches(2.4), Inches(4.6), Inches(3.9), Inches(1.5), "TRADITIONAL",
      [("Same input + same code", DARK), ("= same output, every run", DARK)],
      heading_color=GREY)
panel(s, Inches(7.0), Inches(4.6), Inches(3.9), Inches(1.5), "AI-ENABLED",
      [("Same input + same code", DARK), ("can give different outputs", RED)],
      heading_color=TEAL)

set_notes(s, note_text("TIMING: 1:00  |  BLOCK: Hook", """
- One-line framing: "Today is not about how models work. It's about what it means to deliver software whose core component sometimes answers the same question differently."
- Promise: by the end, you'll have a checklist of questions to ask any team building an AI feature, and a mental model for where the cost and risk live.
"""))

# ==================================================== SLIDE 2 — the hook ====
s = add_slide()
add_header(s, "The one thing that's different", kicker="Block 1 · Hook")
bullets(s, [
    (0, "Traditional software: same input + same code = same output. Test it once, it stays tested."),
    (0, "AI features: same input + same code can produce different outputs. The model is a component you don't fully control."),
    (0, "This means: quality is statistical, not binary. \u201cIt passed testing\u201d needs a new definition."),
    (0, "Example: a ticket-triage feature that routes 96/100 tickets correctly every run — but the same 4 tickets fail different ones each run. [illustrative]"),
])
add_footer(s, "Block 1 · Hook", "0:00–2:30")
set_notes(s, note_text("TIMING: 1:30  |  BLOCK: Hook", """
- Land the vocabulary early: non-determinism = the same input can give different outputs across runs. Not a bug; a property.
- Analogy: hiring a very fast, very bright contractor who is right 95% of the time and confidently wrong the rest — and the 5% moves around. You don't stop hiring them; you change how you review their work.
- "Everything after this slide is about the how you review their work part."
"""))

# ================================================= SLIDE 3 — demo setup =====
s = add_slide()
add_rect(s, Inches(0), Inches(0), SW, Inches(1.35), fill=TEAL)
add_text(s, Inches(0.55), Inches(0.32), Inches(12.2), Inches(0.75),
         "LIVE DEMO — an AI coding agent on a real backlog task",
         28, color=WHITE, bold=True)
panel(s, Inches(0.9), Inches(1.9), Inches(11.5), Inches(1.7), "THE TASK",
      [("\u201cAdd an input-validation fix to a small service and update its tests.\u201d", DARK)],
      heading_color=TEAL, body_size=20)
add_text(s, Inches(0.9), Inches(4.0), Inches(11.5), Inches(0.5),
         "Watch for three things:", 18, color=NAVY, bold=True)
add_rect(s, Inches(0.9), Inches(4.6), Inches(3.6), Inches(1.3))
add_text(s, Inches(1.1), Inches(4.85), Inches(3.2), Inches(0.9), "1. What tools it uses",
         17, color=DARK, bold=True)
add_rect(s, Inches(4.85), Inches(4.6), Inches(3.6), Inches(1.3))
add_text(s, Inches(5.05), Inches(4.85), Inches(3.2), Inches(0.9), "2. What it remembers",
         17, color=DARK, bold=True)
add_rect(s, Inches(8.8), Inches(4.6), Inches(3.6), Inches(1.3))
add_text(s, Inches(9.0), Inches(4.85), Inches(3.2), Inches(0.9),
         "3. Where it hesitates or goes wrong", 17, color=DARK, bold=True)
add_footer(s, "Block 2 · Live demo", "2:30–4:30")
set_notes(s, note_text("TIMING: 0:30 (demo runs ~5:00)  |  BLOCK: Demo", """
- Keep this slide up while running the demo. Say the three watch-points out loud — they are the structure of the debrief.
- Contingency if the demo stalls: "Watch what it does when it gets confused — that IS the lesson," then switch to the pre-recorded run.
- Backup plan: pre-recorded run of the same task, side-by-side with the live attempt — "same task, same model class, different path" makes the non-determinism point even better.
"""))

# ============================================ SLIDE 4 — agent components ====
s = add_slide()
add_header(s, "Debrief #1 — the five parts of an agent", kicker="Block 2 · Demo debrief")
comps = [
    ("BRAIN", "The model. Proposes what to do next. (Here: our in-house agent on a fast, cost-efficient model.)"),
    ("TOOLS", "Things it can DO — read files, run tests, call APIs, open PRs."),
    ("SKILLS", "Packaged know-how — reusable playbooks for recurring tasks."),
    ("MEMORY", "What it remembers across steps and sessions — the task, decisions, prior corrections."),
    ("HARNESS", "The code around the model that turns 'a clever answer' into 'a completed task' — orchestration, output checks, limits, logging."),
]
top = Inches(1.7)
for i, (name, desc) in enumerate(comps):
    fill = NAVY if name == "HARNESS" else LIGHT
    txt_color = WHITE if name == "HARNESS" else DARK
    add_rect(s, Inches(0.55), top, Inches(2.5), Inches(0.92),
             fill=NAVY if name == "HARNESS" else RGBColor(0xE3, 0xEA, 0xF2))
    add_text(s, Inches(0.75), top + Inches(0.25), Inches(2.1), Inches(0.5),
             name, 16, color=WHITE if name == "HARNESS" else NAVY, bold=True)
    add_text(s, Inches(3.25), top + Inches(0.06), Inches(9.4), Inches(0.9),
             desc, 15, color=txt_color)
    top += Inches(1.02)
add_text(s, Inches(0.55), Inches(6.85), Inches(12.2), Inches(0.4),
         "The model is rented intelligence. The harness is the part you own.",
         15, color=TEAL, bold=True)
add_footer(s, "Block 2 · Demo debrief", "4:30–6:30")
set_notes(s, note_text("TIMING: 2:00  |  BLOCK: Demo debrief", """
- Map each part to what was just seen on screen ("you saw it call the run-tests tool at 2:14...").
- The harness is the part most teams underinvest in. Without one: an agent with shell access once "fixed" a failing test by DELETING the test. With a harness rule ("tests are read-only during fix tasks"), that path is blocked.
- Without memory: the agent re-asks the same clarifying question every session; with memory, corrections persist.
- Key line: "The model is rented intelligence. The harness is the part you own. Quality and safety live mostly in the part you own."
"""))

# ============================================ SLIDE 5 — multi-agent =========
s = add_slide()
add_header(s, "Debrief #2 — when multi-agent helps (and when it doesn't)",
           kicker="Block 2 · Demo debrief")
panel(s, Inches(0.55), Inches(1.7), Inches(6.0), Inches(3.1), "HELPS WHEN",
      [("• Genuinely separable concerns (planner → coder → reviewer)", DARK),
       ("• Parallelisable work — e.g. migrate 40 files across 4 workers", DARK),
       ("• An independent REVIEWER agent that didn't write the code it checks", DARK),
       ("", DARK)],
      heading_color=TEAL)
panel(s, Inches(6.8), Inches(1.7), Inches(6.0), Inches(3.1), "COSTS WHEN IT DOESN'T",
      [("• Every handoff multiplies tokens and latency — a 3-agent chain can cost 2–4× a single agent [illustrative]", RED),
       ("• Errors compound at each handoff", RED),
       ("• Debugging \u201cwhich agent dropped the context?\u201d is its own specialty", RED)],
      heading_color=RED)
bullets(s, [
    (0, "Rule of thumb: start with one agent + good tools. Add agents only when a specific, measured failure says you need them."),
], top=Inches(5.1), height=Inches(1.0))
add_footer(s, "Block 2 · Demo debrief", "6:30–8:00")
set_notes(s, note_text("TIMING: 1:30  |  BLOCK: Demo debrief", """
- Vendor demos love multi-agent because it photographs well. In delivery, it's usually the more expensive and less debuggable option.
- The one multi-agent pattern with consistently good ROI: a separate reviewer/critic agent, because independence catches what self-review misses. Everything else: default to single-agent.
- Tie to demo: "What you just saw was one agent with five good tools. Note how much that already did."
"""))

# ==================================== SLIDE 6 — lifecycle: requirements =====
s = add_slide()
add_header(s, "Requirements: from spec to intent + examples",
           kicker="Block 3 · Lifecycle shifts")
bullets(s, [
    (0, "Traditional: detailed requirements → build. AI features: you specify intent plus worked examples (\u201cthese 10 inputs, these 10 expected outputs\u201d)."),
    (0, "New artefact that didn't exist before: the eval set — curated inputs with known-good outputs; a spec AND a test suite in one."),
    (0, "Implication: SME time moves upstream. Domain experts co-own the examples, not just the sign-off."),
])
panel(s, Inches(0.55), Inches(4.55), Inches(6.0), Inches(2.0), "MANAGER QUESTION",
      [("\u201cShow me the eval set. Who approved it, and how many real production cases does it cover?\u201d", NAVY)],
      heading_color=TEAL, body_size=17)
panel(s, Inches(6.8), Inches(4.55), Inches(6.0), Inches(2.0), "CONCRETE ASK",
      [("50–200 real cases across normal, edge, and adversarial inputs — before you trust any accuracy number a team quotes you.", DARK)],
      heading_color=GREY, body_size=16)
add_footer(s, "Block 3 · Lifecycle", "11:30–13:00")
set_notes(s, note_text("TIMING: 1:30  |  BLOCK: Lifecycle", """
- Define jargon on first use: eval set = a curated set of inputs with known-good outputs, treated like a spec and a test suite.
- Manager question to ask: "Show me the eval set. Who approved it, and how many real production cases does it cover?"
"""))

# ===================================== SLIDE 7 — lifecycle: estimation ======
s = add_slide()
add_header(s, "Estimation: the new uncertainty", kicker="Block 3 · Lifecycle shifts")
bullets(s, [
    (0, "Building the feature is often faster (days not weeks). Two new cost centres replace the old one: evaluation and harness/guardrail work."),
    (0, "Realistic shape for a first AI feature [illustrative]:"),
], top=Inches(1.75), height=Inches(1.6))
# stacked bars
bars = [("BUILD 30%", Inches(2.7), TEAL),
        ("EVALS + HARNESS 40%", Inches(3.6), NAVY),
        ("INTEGRATION + ROLLOUT 30%", Inches(2.7), RGBColor(0x8A, 0xA3, 0xB8))]
x = Inches(1.2)
for label, w, color in bars:
    add_rect(s, x, Inches(3.45), w, Inches(0.75), fill=color)
    add_text(s, x + Inches(0.08), Inches(3.62), w - Inches(0.1), Inches(0.5),
             label, 12, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    x += w
add_text(s, Inches(1.2), Inches(4.25), Inches(9.5), Inches(0.4),
         "vs. traditional: ~70% build, ~30% test + rollout [illustrative]",
         12, color=GREY, italic=True)
bullets(s, [
    (0, "Why estimates slip: quality is discovered empirically. You can't code-review your way to knowing a model gets 92% vs 97% — you have to measure it, and the target moves with each model update."),
], top=Inches(4.85), height=Inches(1.4))
add_footer(s, "Block 3 · Lifecycle", "13:00–14:30")
set_notes(s, note_text("TIMING: 1:30  |  BLOCK: Lifecycle", """
- The line that lands: "You're not estimating construction any more. You're estimating experimentation plus construction."
- Practical guidance: timebox quality cycles. "Two eval-and-tune iterations, then we decide ship / shrink scope / descope" beats open-ended "make it better."
"""))

# ======================================= SLIDE 8 — lifecycle: testing =======
s = add_slide()
add_header(s, "Testing: from assertions to distributions",
           kicker="Block 3 · Lifecycle shifts")
bullets(s, [
    (0, "Traditional tests: pass/fail assertions, fully automatable. AI testing: quality RATES over many cases — \u201c94% correct this run, 96% last run\u201d — plus targeted assertions for the deterministic parts (schema, formatting, refusal rules)."),
    (0, "Two layers that must both exist:"),
    (1, "Evals — does the output meet the bar?"),
    (1, "Regression evals — did last week's prompt/model/skill change break something that worked? (The layer teams forget.)"),
    (0, "Release criteria change: from \u201call tests pass\u201d to \u201cquality ≥ threshold on eval set, no regression on golden set, failure modes within agreed limits.\u201d"),
])
panel(s, Inches(0.55), Inches(5.35), Inches(12.2), Inches(1.3), "MENTAL SHIFT",
      [("Less like unit testing, more like performance testing: track a metric against a threshold, and re-run the benchmark on every change.", DARK)],
      heading_color=TEAL, body_size=15)
add_footer(s, "Block 3 · Lifecycle", "14:30–16:00")
set_notes(s, note_text("TIMING: 1:30  |  BLOCK: Lifecycle", """
- Analogy: performance testing — you track a metric against a threshold, and any change requires re-running the benchmark.
- Cost note (foreshadowing slide 18): evals aren't free — every regression run is API spend. Budget for it.
"""))

# ============================= SLIDE 9 — lifecycle: release & support ======
s = add_slide()
add_header(s, "Release and support: shipping a component that drifts",
           kicker="Block 3 · Lifecycle shifts")
bullets(s, [
    (0, "Traditional release risk is YOUR change. AI release risk includes things you didn't change: the model behind your feature can be silently updated by the vendor; behaviour can drift."),
    (0, "Two practices that close the gap:"),
    (1, "Version pinning — know exactly which model + prompt + skill version produced every output."),
    (1, "Canary rollouts — route 5–10% of traffic first, compare quality metrics before full release [illustrative]."),
    (0, "Support changes: tickets stop being \u201cit's broken\u201d and become \u201cthe answer was wrong / subtle-wrong.\u201d Support needs an escalation path that feeds failing cases back into the eval set."),
])
panel(s, Inches(0.55), Inches(5.5), Inches(12.2), Inches(1.25),
      "THE UNCOMFORTABLE SENTENCE",
      [("\u201cYou can ship nothing, change nothing, and get a customer-impacting change anyway.\u201d Pinning + evals on upgrade is the defence. Ask: when the model provider updates the model, what's our process? Who re-runs the eval set?", NAVY)],
      heading_color=RED, body_size=14)
add_footer(s, "Block 3 · Lifecycle", "16:00–17:30")
set_notes(s, note_text("TIMING: 1:30  |  BLOCK: Lifecycle", """
- The uncomfortable sentence for leadership: "You can ship nothing, change nothing, and get a customer-impacting change anyway." Pinning + evals on upgrade is the defence.
- Ask teams: "When the model provider updates the model, what's our process? Who re-runs the eval set?"
"""))

# ===================================== SLIDE 10 — toolkit overview ==========
s = add_slide()
add_rect(s, Inches(0), Inches(0), SW, Inches(2.1), fill=NAVY)
add_text(s, Inches(0.7), Inches(0.5), Inches(12.0), Inches(0.8),
         "The Determinism Toolkit", 32, color=WHITE, bold=True)
add_text(s, Inches(0.7), Inches(1.35), Inches(12.0), Inches(0.5),
         "You can't stop the dice — but you can build around them",
         18, color=RGBColor(0xBF, 0xD4, 0xD4))
bullets(s, [
    (0, "Goal is not literal determinism; it's predictable-enough behaviour: bounded failure modes, consistent quality, auditable decisions."),
    (0, "Six techniques — each with a \u201cdoes\u201d and a \u201cdoes not fix.\u201d"),
    (0, "These are layers — pick per risk, not all always (cost: block 7)."),
], top=Inches(2.5), height=Inches(1.8))
layers = ["Structured outputs", "Guardrails", "RAG (grounding)",
          "Human-in-the-loop", "Retries + fallbacks", "Eval suite (wraps all)"]
lx = Inches(0.55)
widths = [Inches(1.95)] * 5 + [Inches(2.15)]
for i, name in enumerate(layers):
    color = TEAL if i < 5 else NAVY
    add_rect(s, lx, Inches(4.7), widths[i], Inches(1.1), fill=color)
    add_text(s, lx + Inches(0.08), Inches(5.0), widths[i] - Inches(0.16),
             Inches(0.6), name, 13, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER)
    lx += widths[i] + Inches(0.1)
add_text(s, Inches(0.55), Inches(6.0), Inches(12.2), Inches(0.4),
         "Eval suite is the measurement layer around every other layer.",
         14, color=GREY, italic=True)
add_footer(s, "Block 4 · Determinism toolkit", "19:30–20:15")
set_notes(s, note_text("TIMING: 0:45  |  BLOCK: Toolkit", """
- This is the section to photograph. The next six slides are one technique each — what it does, what it doesn't, and the manager's one-line check.
"""))

# =========================== SLIDE 11 — technique 1: structured outputs ====
s = add_slide()
add_header(s, "1. Structured / constrained outputs", kicker="Block 4 · Toolkit")
panel(s, Inches(0.55), Inches(1.7), Inches(6.0), Inches(2.6), "DOES",
      [("Forces the answer into a schema (JSON with required fields, an enumerated category, a strict format).", DARK),
       ("Turns \u201cprose that looks right\u201d into data you can validate programmatically.", DARK),
       ("Cheap, fast, high ROI — do this everywhere.", TEAL)],
      heading_color=TEAL)
panel(s, Inches(6.8), Inches(1.7), Inches(6.0), Inches(2.6), "DOES NOT FIX",
      [("Whether the CONTENT is correct. A perfectly formatted JSON can contain a wrong category or an invented ticket ID.", RED)],
      heading_color=RED)
panel(s, Inches(0.55), Inches(4.55), Inches(8.2), Inches(1.9), "MANAGER CHECK",
      [("\u201cAre model outputs validated against a schema before any downstream action?\u201d", NAVY)],
      heading_color=TEAL, body_size=17)
panel(s, Inches(9.0), Inches(4.55), Inches(3.8), Inches(1.9), "SMALL-MODEL CAVEAT",
      [("Strict schemas can wobble on fast/cheap models. Mitigation: validate-and-retry once; keep schemas shallow.", DARK)],
      heading_color=GREY, body_size=13)
add_footer(s, "Block 4 · Determinism toolkit", "20:15–21:15")
set_notes(s, note_text("TIMING: 1:00  |  BLOCK: Toolkit", """
- Demo hook: "In the demo you'll see the triage agent's output constrained to a three-field schema. The format was perfect every run; the content still needed the eval suite."
- Manager check: "Are model outputs validated against a schema before any downstream action?"
- Small-model caveat: strict schema adherence can wobble on fast/cheap models — mitigation: validate-and-retry once, and keep schemas shallow.
"""))

# ================================== SLIDE 12 — technique 2: guardrails =====
s = add_slide()
add_header(s, "2. Guardrails", kicker="Block 4 · Toolkit")
panel(s, Inches(0.55), Inches(1.7), Inches(6.0), Inches(2.6), "DOES",
      [("Enforces the rules AROUND the model: input filters, output filters, allow-lists of actions, permission limits on tools (the harness's job).", DARK),
       ("This is what stops \u201cdelete the failing test.\u201d", DARK)],
      heading_color=TEAL)
panel(s, Inches(6.8), Inches(1.7), Inches(6.0), Inches(2.6), "DOES NOT FIX",
      [("Subtle quality problems. Guardrails catch FORBIDDEN behaviour, not MEDIOCRE behaviour.", RED)],
      heading_color=RED)
bullets(s, [
    (0, "Best guardrails are structural, not persuasive: don't prompt \u201cplease don't delete tests\u201d — remove the tool permission."),
], top=Inches(4.55), height=Inches(0.9))
panel(s, Inches(0.55), Inches(5.5), Inches(12.2), Inches(1.15), "MANAGER CHECK",
      [("\u201cWhat can the agent DO to production systems, and what is structurally impossible for it?\u201d", NAVY)],
      heading_color=TEAL, body_size=17)
add_footer(s, "Block 4 · Determinism toolkit", "21:15–22:15")
set_notes(s, note_text("TIMING: 1:00  |  BLOCK: Toolkit", """
- Best guardrails are structural, not persuasive: don't prompt "please don't delete tests" — remove the tool permission.
- Manager check: "What can the agent do to production systems, and what is structurally impossible for it?"
"""))

# ============================================ SLIDE 13 — technique 3: RAG ==
s = add_slide()
add_header(s, "3. RAG — grounding in your own content", kicker="Block 4 · Toolkit")
add_text(s, Inches(0.55), Inches(1.7), Inches(12.2), Inches(0.7),
         "RAG (\u201cretrieval-augmented generation\u201d): before answering, the system fetches relevant passages from YOUR documents and tells the model to answer only from those.",
         16, color=DARK)
panel(s, Inches(0.55), Inches(2.55), Inches(6.0), Inches(2.9), "DOES",
      [("Sharply reduces invented facts on knowledge tasks", DARK),
       ("Gives you citations you can audit", DARK),
       ("Keeps answers current without retraining", DARK)],
      heading_color=TEAL)
panel(s, Inches(6.8), Inches(2.55), Inches(6.0), Inches(2.9), "DOES NOT FIX",
      [("Bad source documents — RAG faithfully retrieves your stale wiki", RED),
       ("Multi-document synthesis: weaker on small models. Mitigation: narrower retrieval, chunked answers", RED)],
      heading_color=RED)
panel(s, Inches(0.55), Inches(5.65), Inches(12.2), Inches(1.15), "MANAGER CHECK",
      [("\u201cWhere does the answer's knowledge come from, and can a reviewer click through to the source?\u201d  ·  Track: grounded-answer rate — % of answers whose claims trace to a retrieved source.", NAVY)],
      heading_color=TEAL, body_size=15)
add_footer(s, "Block 4 · Determinism toolkit", "22:15–23:15")
set_notes(s, note_text("TIMING: 1:00  |  BLOCK: Toolkit", """
- The measurable claim worth tracking: answer grounded-rate — % of answers whose claims trace to a retrieved source.
- Manager check: "Where does the answer's knowledge come from, and can a reviewer click through to the source?"
"""))

# ========================== SLIDE 14 — technique 4: human-in-the-loop ======
s = add_slide()
add_header(s, "4. Human-in-the-loop checkpoints", kicker="Block 4 · Toolkit")
panel(s, Inches(0.55), Inches(1.7), Inches(6.0), Inches(2.7), "DOES",
      [("Puts a human approval gate at consequential steps — before code merges, before an email sends, before a refund issues.", DARK),
       ("The single most effective risk control early in an AI feature's life.", TEAL)],
      heading_color=TEAL)
panel(s, Inches(6.8), Inches(1.7), Inches(6.0), Inches(2.7), "DOES NOT FIX",
      [("Throughput — it's a bottleneck", RED),
       ("It DECAYS: rubber-stamping sets in around approval #200 [illustrative]. Design for graduated autonomy.", RED)],
      heading_color=RED)
# autonomy ladder
add_text(s, Inches(0.55), Inches(4.65), Inches(6.0), Inches(0.4),
         "The autonomy ladder (earned with evidence, reversible):",
         14, color=NAVY, bold=True)
steps = ["SUGGEST", "APPROVE ALL", "EXCEPTIONS ONLY", "AUDIT ONLY"]
sx = Inches(0.55)
shades = [RGBColor(0xE3, 0xEA, 0xF2), RGBColor(0xB9, 0xCB, 0xDE),
          TEAL, NAVY]
tcolors = [NAVY, NAVY, WHITE, WHITE]
for i, (name, fill, tc) in enumerate(zip(steps, shades, tcolors)):
    add_rect(s, sx, Inches(5.15), Inches(2.85), Inches(0.75), fill=fill)
    add_text(s, sx + Inches(0.08), Inches(5.36), Inches(2.7), Inches(0.4),
             name, 13, color=tc, bold=True, align=PP_ALIGN.CENTER)
    sx += Inches(2.97)
panel(s, Inches(0.55), Inches(6.15), Inches(12.2), Inches(0.85), "MANAGER CHECK",
      [("\u201cWhich actions require a human click today, and what evidence would move that gate?\u201d", NAVY)],
      heading_color=TEAL, body_size=15)
add_footer(s, "Block 4 · Determinism toolkit", "23:15–24:15")
set_notes(s, note_text("TIMING: 1:00  |  BLOCK: Toolkit", """
- Key management insight: autonomy is earned with evidence (eval scores, not vibes), and it's reversible — the ladder goes down too.
- Manager check: "Which actions require a human click today, and what evidence would move that gate?"
"""))

# ================= SLIDE 15 — techniques 5+6: retries/fallbacks + evals ====
s = add_slide()
add_header(s, "5 + 6. Retries, fallbacks — and the eval suite",
           kicker="Block 4 · Toolkit")
panel(s, Inches(0.55), Inches(1.7), Inches(6.0), Inches(3.0),
      "RETRIES + FALLBACKS",
      [("A failed validation or low-confidence answer triggers a re-ask, a different prompt, or escalation to a stronger model.", DARK),
       ("DOES: rescues transient failures cheaply.", TEAL),
       ("DOES NOT FIX: systematic errors — retrying a misunderstanding 3× gets the same wrong answer, 3× the cost.", RED)],
      heading_color=NAVY)
panel(s, Inches(6.8), Inches(1.7), Inches(6.0), Inches(3.0),
      "THE EVAL SUITE WRAPS EVERYTHING",
      [("The measurement layer: tells you whether any of the other five layers actually improved quality.", DARK),
       ("Doubles as a regression suite — run on every change to prompts, skills, or model version.", DARK)],
      heading_color=TEAL)
panel(s, Inches(0.55), Inches(4.95), Inches(12.2), Inches(1.7),
      "THIS IS OUR OWN OPERATING MODEL",
      [("Primary: our in-house agent on a fast, cost-efficient model. Escalation: frontier model for the hard tail.", DARK),
       ("Deliberately model-agnostic — one config change swaps the backend. Cheap-first routing with an evidence-based escalation trigger.", NAVY)],
      heading_color=TEAL, body_size=15)
add_footer(s, "Block 4 · Determinism toolkit", "24:15–25:30")
set_notes(s, note_text("TIMING: 1:00  |  BLOCK: Toolkit", """
- This is our own operating model, live: primary = our in-house agent on a fast, cost-efficient model; escalation = frontier model for the hard tail. Deliberately model-agnostic — one config change swaps the backend.
- The point isn't the specific models; it's the pattern: cheap-first routing with an evidence-based escalation trigger.
"""))

# ======================================= SLIDE 16 — observability ==========
s = add_slide()
add_header(s, "The manager's dashboard for AI features",
           kicker="Block 5 · Observability")
add_text(s, Inches(0.55), Inches(1.65), Inches(12.2), Inches(0.75),
         "Instrument every call: input, output, model + prompt + skill VERSIONS, tool calls made, latency, token cost, and the eval verdict.",
         16, color=DARK)
tiles = [("QUALITY %", "sampled prod traffic"),
         ("GROUNDED %", "claims trace to a source"),
         ("ESCALATIONS", "to the stronger model"),
         ("COST / TASK", "incl. retries + evals"),
         ("OVERRIDES", "humans reversing the AI"),
         ("LATENCY", "p95, trended")]
tx, ty = Inches(0.55), Inches(2.6)
for i, (name, sub) in enumerate(tiles):
    col = i % 3
    row = i // 3
    x = tx + col * Inches(4.15)
    y = ty + row * Inches(1.5)
    add_rect(s, x, y, Inches(3.95), Inches(1.3),
             fill=NAVY if name == "OVERRIDES" else LIGHT)
    add_text(s, x + Inches(0.2), y + Inches(0.18), Inches(3.5), Inches(0.5),
             name, 18, color=WHITE if name == "OVERRIDES" else NAVY, bold=True)
    add_text(s, x + Inches(0.2), y + Inches(0.72), Inches(3.5), Inches(0.45),
             sub + "  ·  trend + threshold line", 12,
             color=RGBColor(0xC5, 0xD3, 0xE0) if name == "OVERRIDES" else GREY)
bullets(s, [
    (0, "Traffic-light thresholds agreed up front: green = within failure budget · amber = regression on golden set · red = override rate or cost/task over limit. Watch trends week over week — a slow quality slide means upstream drift or content rot."),
], top=Inches(5.85), height=Inches(1.0), size=14)
add_footer(s, "Block 5 · Observability", "26:30–29:30")
set_notes(s, note_text("TIMING: 3:00  |  BLOCK: Observability", """
- What to watch week over week, not just point-in-time: a slow quality slide usually means upstream drift or content rot.
- One tile people forget: override rate — how often humans reverse the AI. Rising overrides = your human-in-the-loop is quietly becoming the quality process.
- Manager check: "Which of these six numbers can you see today for the AI features in your portfolio?"
"""))

# ========================================= SLIDE 17 — vibe coding ==========
s = add_slide()
add_header(s, "Vibe coding: developer practices → manager signals",
           kicker="Block 6 · Vibe coding")
add_text(s, Inches(0.55), Inches(1.6), Inches(12.2), Inches(0.5),
         "Vibe coding = developers building features and fixing bugs by directing AI coding agents in natural language. Already happening on several teams. The failure mode isn't bad code — it's UNREVIEWED code that looks fine.",
         15, color=DARK)
rows = [
    ("Small, scoped tasks (one function/bug per prompt)", "PR size stays reviewable — watch for mega-PRs"),
    ("Agent writes tests first / tests included", "Coverage % on AI-authored code — watch for drops"),
    ("Every AI line reviewed like a hire's work", "Review comments per AI PR — watch for \u201cLGTM, zero comments\u201d streaks"),
    ("Provenance logged (agent/model/prompt)", "Provenance field in PR — watch for unlabelled AI PRs"),
    ("Dependencies only via approved list", "Dependency-diff in PRs — watch for silent new packages (supply-chain risk)"),
    ("No AI-only merges to prod", "Branch rules — watch for override frequency"),
]
col_w = [Inches(5.6), Inches(6.6)]
x0 = Inches(0.55)
y0 = Inches(2.6)
row_h = Inches(0.62)
# header row
add_rect(s, x0, y0, col_w[0], row_h, fill=NAVY)
add_rect(s, x0 + col_w[0] + Inches(0.12), y0, col_w[1], row_h, fill=NAVY)
add_text(s, x0 + Inches(0.15), y0 + Inches(0.13), col_w[0], Inches(0.4),
         "DEVELOPER PRACTICE", 13, color=WHITE, bold=True)
add_text(s, x0 + col_w[0] + Inches(0.27), y0 + Inches(0.13), col_w[1],
         Inches(0.4), "SIGNAL THE MANAGER WATCHES", 13, color=WHITE, bold=True)
for i, (a, b) in enumerate(rows):
    y = y0 + row_h + i * (row_h + Inches(0.06))
    fill = LIGHT if i % 2 == 0 else WHITE
    add_rect(s, x0, y, col_w[0], row_h, fill=fill)
    add_rect(s, x0 + col_w[0] + Inches(0.12), y, col_w[1], row_h, fill=fill)
    add_text(s, x0 + Inches(0.15), y + Inches(0.09), col_w[0] - Inches(0.25),
             row_h, a, 13, color=DARK)
    add_text(s, x0 + col_w[0] + Inches(0.27), y + Inches(0.09),
             col_w[1] - Inches(0.25), row_h, b, 13, color=DARK)
add_text(s, Inches(0.55), Inches(6.75), Inches(12.2), Inches(0.4),
         "One number to own: defect rate of AI-assisted PRs vs hand-written PRs.",
         14, color=TEAL, bold=True)
add_footer(s, "Block 6 · Vibe coding", "29:30–34:30")
set_notes(s, note_text("TIMING: 5:00  |  BLOCK: Vibe coding", """
- Tone: this is a productivity win IF the review discipline holds.
- Story example: an agent "fixed" a bug by catching and silently swallowing the exception — test passed, bug moved to production. The control that catches it: reviewer checklist item "did the test actually exercise the failure path?"
- Manager check: "What fraction of last sprint's merged PRs were AI-assisted, and did their defect rate differ from hand-written PRs?" That measurable difference is the whole conversation in one number.
"""))

# ============================================== SLIDE 18 — cost ============
s = add_slide()
add_header(s, "Where the money goes — and the cheaper-model trade-off",
           kicker="Block 7 · Cost")
bullets(s, [
    (0, "Spend accumulates in four places — three are CAUSED by your determinism efforts:"),
    (1, "Per-run tokens (multi-agent chains multiply this)"),
    (1, "Retries and escalations (each retry = full re-run)"),
    (1, "Evals + regression runs (API spend on every change)"),
    (1, "Observability / infra (logging every call)"),
], top=Inches(1.7), height=Inches(2.1), size=15)
panel(s, Inches(0.55), Inches(3.55), Inches(6.0), Inches(1.9), "ILLUSTRATIVE ARITHMETIC",
      [("Triage feature, 10k runs/month: base run on a fast model ≈ $0.004/run. Adding retry-on-validate + daily eval cycle + reviewer-agent pass → effective cost per ACCEPTED output = 3–5× base [illustrative].", DARK),
       ("Still trivially cheap vs a human analyst — the point is knowing your multiplier.", TEAL)],
      heading_color=GREY, body_size=12)
panel(s, Inches(6.8), Inches(3.55), Inches(6.0), Inches(1.9), "CONTROLS THAT KEEP QUALITY",
      [("1. Route by difficulty — fast model first, escalate on low confidence", DARK),
       ("2. Cache and reuse (same question + docs → same answer)", DARK),
       ("3. Right-size evals (full suite on release; smoke set daily)", DARK),
       ("4. Multi-agent only for independent review", DARK)],
      heading_color=TEAL, body_size=12)
panel(s, Inches(0.55), Inches(5.65), Inches(12.2), Inches(1.25),
      "THE TRADE-OFF TO INTERNALISE",
      [("A cheaper model + a stronger harness usually beats an expensive model + a thin harness — on cost AND predictability. Upgrade the model only when the eval suite shows the harness has hit its ceiling. Ask for: cost per ACCEPTED, quality-checked output — not cost per token.", NAVY)],
      heading_color=TEAL, body_size=13)
add_footer(s, "Block 7 · Cost", "34:30–38:00")
set_notes(s, note_text("TIMING: 3:30  |  BLOCK: Cost", """
- The one number to ask for: cost per accepted, quality-checked output — not cost per token. The first includes your determinism tax; the second hides it.
- Our own setup as the case study: fast model handles most traffic; the harness decides when to escalate. The eval suite tells us the escalation trigger is calibrated — that's why evals are spend you protect, not spend you cut.
- Flag: structure sourced from practice; figures illustrative.
"""))

# ============================================= SLIDE 19 — close ============
s = add_slide()
add_header(s, "What to take back to your teams", kicker="Block 8 · Close")
qs = [
    "\u201cShow me the eval set — who approved it, and what does it cover?\u201d",
    "\u201cWhat is the model ALLOWED to do, and what's structurally impossible?\u201d",
    "\u201cWhich human approvals exist, and what evidence moves them?\u201d",
    "\u201cWhich of the six dashboard numbers do I get, weekly?\u201d",
    "\u201cWhat's the cost per accepted output, and what's the escalation rule?\u201d",
]
top = Inches(1.7)
for i, q in enumerate(qs, 1):
    add_rect(s, Inches(0.55), top, Inches(0.75), Inches(0.78), fill=NAVY)
    add_text(s, Inches(0.55), top + Inches(0.17), Inches(0.75), Inches(0.5),
             str(i), 22, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_rect(s, Inches(1.45), top, Inches(11.3), Inches(0.78), fill=LIGHT)
    add_text(s, Inches(1.7), top + Inches(0.2), Inches(10.9), Inches(0.5),
             q, 16, color=DARK)
    top += Inches(0.92)
add_text(s, Inches(0.55), Inches(6.45), Inches(12.2), Inches(0.8),
         "The theme: you can't make the model deterministic — you build the predictability around it. That's now a delivery discipline with its own estimation, testing, and cost profile.",
         15, color=TEAL, bold=True)
add_footer(s, "Block 8 · Close · Q&A + handout", "38:00–40:00")
set_notes(s, note_text("TIMING: 2:00  |  BLOCK: Close", """
- Close with the ask: "Pick one AI feature in your portfolio. Bring me the five answers at the next update."
- Hand off to Q&A / handout distribution.
"""))

# ------------------------------------------------------------------ save ---
OUT = "/Users/vinod.pungle/ai-session/deliverable-B-deck.pptx"
prs.save(OUT)
print(f"Saved {OUT} with {len(prs.slides.__iter__.__self__._sldIdLst)} slides")
