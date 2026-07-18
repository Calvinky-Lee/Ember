# Ember, explained simply

*No jargon version. For the technical map with diagrams, see [OVERVIEW.md](./OVERVIEW.md);
for build details, see [specs/](./specs/README.md). Jargon that can't be avoided is
in the [glossary](#glossary) at the bottom.*

---

## What is Ember, in one sentence?

Ember is a smart dispatcher that sits between an app and AI models: for every
question, it picks the **cheapest AI model that can answer it just as well as the
best one**, checks the answer's quality, and keeps an honest receipt of the money
and pollution saved.

## The problem it solves

Think of AI models like vehicles. Claude Opus is a transport truck: incredibly
capable, expensive to run, burns a lot of fuel. A small model is a bicycle: cheap,
light, fine for small errands.

Today, almost every AI product **sends the truck for everything** — including
"what's the capital of France?" and "make this text uppercase." That wastes two
things on every trivial question:

- **Money** — big-model answers cost hundreds of times more than small-model ones.
- **Electricity → pollution** — bigger models burn more power per word, and
  depending on *where* the datacenter is, that electricity can come from coal
  (very dirty) or hydro/nuclear (very clean) — up to a 10× difference.

## What Ember does — every feature, plainly

1. **Sizes up the question** (*the classifier*). A quick check: does this look
   trivial, medium, or genuinely hard?
2. **Sends it to the smallest fitting model** (*the router*). Trivial → small
   Llama model. Medium → bigger Llama. Hard → Claude Opus, the best there is.
3. **Checks the answer before you ever see it** (*the quality gate*). A separate
   AI — Google's Gemini, deliberately from a different company so it has no
   loyalty — grades the answer. Good enough? Deliver it. Any doubt? **Escalate**:
   redo it with the next bigger model. Worst case you always end at Opus. That's
   why quality never drops — being green never beats being right.
4. **Picks the cleanest place to run** (*carbon-aware placement*). Live data shows
   how dirty each region's electricity is *right now*; Ember picks the greenest
   option. (In our demo this choice is simulated — clearly labeled — because
   public AI services don't let you pick their datacenter; big cloud platforms do.)
5. **Writes an honest receipt for every single call** (*measurement*). Words
   processed × energy-per-word × how dirty the local grid is = grams of CO₂.
   Plus the exact dollar cost from public price sheets. Even Ember's own overhead
   (the classifier, the judge, failed attempts) goes on Ember's bill — we never
   hide our own footprint.
6. **Proves it with a fair race** (*the benchmark*). The same ~150 questions run
   twice: once "everything to Opus" (how apps work today), once through Ember.
   Same questions, same rules, statistics done properly. Output: *"−X% CO₂,
   answers within Y% of Opus, −Z% cost."*
7. **Shows it live** (*the `ember race` command*). Ember is a command-line tool:
   run `ember race` and two counters race in the terminal — pollution and dollars —
   one for the old way, one for Ember. `ember methodology` prints every assumption
   (our audit trail), and `ember report --html` produces an ESG report file — the
   kind of sustainability paperwork companies are increasingly required to file.

## What we use, and why (the ingredient list)

| Ingredient | What it is, plainly | Its job in Ember |
|---|---|---|
| **Groq** | A free service that runs Meta's open Llama models very fast | Powers the small and medium tiers |
| **Claude Opus** (Anthropic) | The most capable AI model — our quality bar | The "hard" tier, and the thing we prove we match |
| **Gemini** (Google, sponsor) | Another company's AI | The neutral referee grading answers |
| **Electricity Maps** | A live world map of "how dirty is electricity right now, per region," fed by official grid operators | Turns energy into pollution numbers; tells the router which region is greenest |
| **Python + SQLite** | The programming language and a single-file database | The whole engine: runs the logic, remembers every call |
| **Rich + Textual** | Tools that draw polished interfaces inside a terminal | The live race view and pretty command output people see |

## How it all connects (one question's journey)

> Your app asks: *"What's 15% of $80?"*
> → **Classifier**: "that's trivial" → **Router** sends it to the small Llama on
> Groq → answer comes back: *"$12"* → **Gemini judge**: "correct, complete — pass"
> → **Measurement** writes the receipt: 40 words processed ≈ 0.005 Wh ≈ 0.0001 g
> CO₂ (at Sweden's clean grid) ≈ $0.00001 → answer delivered.
> The old way, Opus would have answered the same *"$12"* for ~300× the money and
> ~50× the energy.
>
> Now a hard one: *"Prove this algorithm terminates."* → classifier says hard →
> straight to Opus → no judge needed (nothing is better than Opus) → receipt
> written. **Same quality as always — Ember only saves where saving is free.**

The benchmark repeats that journey 150×2 times and `ember race` draws the result.

## What we do NOT claim (honesty is the strategy)

- We don't claim to beat Opus — we claim to **match** it while wasting less.
- Our carbon numbers are **estimates** (nobody outside a datacenter can measure
  its meters) — but every assumption is published, which is more than anyone
  else offers. The **dollar savings are exact.**
- Training the models polluted too — that already happened either way; we count
  only the pollution of *using* them, and we say so.

## Glossary

| Term | Meaning |
|---|---|
| **Token** | Roughly ¾ of a word. AI models read and write in tokens; price and energy scale with them. |
| **Inference vs training** | Training = building the model (done once, by Meta/Anthropic/Google). Inference = using it to answer. Ember only deals with inference. |
| **Open-weight model** | A model whose file is published so anyone can run it (Llama). Opposite: closed (Opus, Gemini) — usable only through the maker's service. |
| **Escalation** | The quality gate rejecting a small model's answer and retrying with a bigger one. ~10–30% of the time is healthy. |
| **Quality floor** | The minimum judge score (0.85/1.00) an answer needs to pass without escalating. |
| **gCO₂ / kWh** | Grams of carbon dioxide; kilowatt-hours of electricity. Pollution = energy used × how dirty the grid is. |
| **Grid intensity** | How many grams of CO₂ one kWh causes in a region right now (Quebec ~30, Poland ~600). |
| **PUE** | Datacenter overhead multiplier (~1.2): cooling and facilities on top of the computers themselves. |
| **Arm A / Arm B** | The two sides of the benchmark race: A = everything-to-Opus (today's normal), B = Ember. |
| **SCI** | An industry-standard way to report "emissions per unit of work" (ours: per query) — what makes the ESG report credible. |
| **Confidence interval (CI)** | The honest range around a measurement ("within ±2%") instead of pretending one exact number. |
| **Provenance label** | The tag on every number saying where it came from: `exact`, `estimated`, `live`, `fallback`, `replay`. Our anti-BS system. |

## Who builds what

- **P1** — the receipts and the server (measurement, database, API)
- **P2** — the dispatcher (classifier, router, judge, escalation)
- **P3** — the race and the statistics (benchmark, evaluation)
- **P4** — everything you see (terminal race view, HTML report, demo)

Your personal checklist: `specs/tasks/P<you>.md`. Run the tests any time with
`uv run pytest` — they're fast, need no keys, and every test explains what it
protects and why.
