# PantryPilot 🥫

**An AI agent team that routes surplus restaurant food to food pantries — and stops to ask a
human when, and only when, it hits a decision a person should make.**

Built for **Global Innovation Hackathon 2026 — *Innovate Without Borders***
Domains: Artificial Intelligence & Machine Learning · Social Impact · Sustainability & Climate Technology

| | |
|---|---|
| 🌐 **Live demo** | https://pantry-pilot-twoe.vercel.app |
| 🔌 **API** | https://pantrypilot-api-ou1p.onrender.com/api/health |
| 💻 **Source** | https://github.com/priyanshiiitr/pantry_pilot |
| 🔑 **Demo logins** | `admin@pantrypilot.test` · `goldencrust@pantrypilot.test` · `jordan@pantrypilot.test` — password `demo1234` for all |
| 🎬 **Demo walkthrough** | [`docs/demo-script.md`](docs/demo-script.md) |

---

## The problem

A third of the world's food is wasted while 733 million people go hungry. The gap is rarely
supply — it is **coordination**.

A restaurant with 40 surplus meals at 9pm has maybe two hours before the food is unsafe. Somewhere
within five kilometres there is a pantry that wants it and a volunteer who could drive it. Matching
those three things means knowing, right now: which pantries are open, which have a fridge, which
have space today, which have dietary restrictions this food breaks, which volunteer is on shift and
close enough to make the deadline — and which pantry has been quietly getting less than its share
all month.

Today that is one overworked coordinator with a phone and a spreadsheet. So the food gets thrown
away, not because nobody wanted it, but because nobody could work out who in time.

## The solution

PantryPilot runs that coordination as a team of AI agents that wake up on their own, reason about
each offer, and act.

```
Restaurant posts surplus food  (messy free text, no forms)
            ↓  scheduler wakes the agents — no button, nobody watching
      COORDINATOR agent
        ├─ Intake     → reads the text: weight, allergens, perishability
        ├─ Matching   → picks the pantry: capacity, fairness, diet, hours
        └─ Dispatch   → finds a driver who can make the deadline
            ↓
      Confident?  ──YES──→  requests the pantry, dispatches the driver
            │
            └──NO───→  PAUSES mid-thought and asks a human
                            ↓ coordinator answers
                     resumes the same paused conversation
            ↓
      Driver picks up → delivers → done
```

## What makes it different

**It knows when it doesn't know.** Most "AI agents" are a scoring function with a language model
bolted on, and they always produce an answer. PantryPilot's agents can genuinely stop. When the
Coordinator hits a real judgment call — food that may spoil before anyone can reach it, a pantry
whose dietary rules the food might break, two options with no honest winner — it calls `ask_admin`,
which fires a **real Strands interrupt**. The agent's conversation halts mid-tool-call and is saved
to disk. It is not a status flag we set; nothing continues until a person answers, and then the
*same* paused conversation resumes from exactly where it stopped, even if the server restarted in
between.

**The escalation is written by the agent, not by us.** The decision card a coordinator sees — the
title, the situation, two to four options each with its real consequence, and a recommendation —
is the model's own writing, shown verbatim. A rule engine can only emit `ERROR: NO_ELIGIBLE_DRIVER`.

**It reasons past gaps in its own tooling.** Watching a real run, the Dispatch agent needed
driver-to-restaurant travel time, found the tool returned only distance, and derived its own
estimate rather than giving up. (We then fixed the tool — but a deterministic pipeline would have
returned `null` and stopped.)

**Fairness is a first-class input.** Nearest-pantry-wins quietly starves the pantries furthest from
the restaurants. The Matching agent is given each pantry's recent share and weighs it against
distance and spoilage risk, case by case, rather than against a fixed constant we picked in advance.

## Technical implementation

Four agents in an **agents-as-tools** architecture: a Coordinator that treats Intake, Matching and
Dispatch as tools it may call in any order, as many times as it decides. There is no fixed pipeline
— when a driver declines, the Coordinator re-plans rather than replaying a script.

Built on the **Strands Agents SDK**. Every feature below is load-bearing, not decoration:

| Feature | Where | What it does here |
|---|---|---|
| `@tool` | [`agents/tools/`](pantrypilot/agents/tools/) | 7 tool modules: pantry/driver lookups, distance and travel time, fairness, memory, and the actions that commit a decision. |
| Multi-agent (agents-as-tools) | [`coordinator_agent.py`](pantrypilot/agents/coordinator_agent.py) | The Coordinator decides which specialist to call, when, and whether to commit, retry or escalate. |
| `structured_output_model` | [`schemas.py`](pantrypilot/agents/schemas.py) | Every specialist answers as a validated Pydantic object, never loose prose. |
| **Interrupts** | [`human_tools.py`](pantrypilot/agents/tools/human_tools.py), [`runner.py`](pantrypilot/agents/runner.py) | `tool_context.interrupt(...)` genuinely suspends the agent; `resume_case()` continues that exact conversation with the human's answer. |
| Sessions | [`sessions.py`](pantrypilot/agents/sessions.py) | Per-offer conversation memory, so a paused agent survives the process dying. |
| Hooks | [`reasoning_log_hook.py`](pantrypilot/agents/hooks/reasoning_log_hook.py) | `BeforeToolCallEvent`/`AfterToolCallEvent` record every tool call — this backs the live activity feed users watch. |
| Memory | [`memory_tools.py`](pantrypilot/agents/tools/memory_tools.py) | `remember_fact`/`recall_facts` persist things learned across offers ("this pantry's fridge is broken"). |
| Model providers | [`model_provider.py`](pantrypilot/agents/model_provider.py) | Groq, Anthropic, OpenAI or AWS Bedrock behind one setting. |
| Observability | [`telemetry.py`](pantrypilot/agents/telemetry.py) | OpenTelemetry spans for every model call. |

**Engineering beyond the agents**

- **247 automated tests**, all passing, costing nothing to run — no test touches a model or the network.
- **API-key failover**: Groq's free tier caps tokens per minute per key. A custom httpx transport
  rotates across keys on a 429 instead of waiting out a 30-second backoff — measured 48,000
  tokens/minute across six keys, with zero full backoffs.
- **Admin "view as"**: preview any restaurant, pantry or driver dashboard without logging out,
  with a badge showing who the agents are actually waiting on. Enforced server-side so previewing
  can never *grant* access.
- **Derived progress tracking**: the five-stage tracker reads existing rows rather than keeping its
  own state, so it cannot drift from reality.

## Real-world impact

The people this is for are not technologists: a restaurant manager closing up, a pantry volunteer,
a driver with a spare hour, one coordinator holding it together. So the system does the
coordination and asks for a human only at genuine decisions — which is the difference between
software that saves a coordinator's evening and software that adds to it.

Every action is explained in plain English, because a coordinator overruling the agent needs to
know *why* it chose what it chose. Nothing is a black box.

## Feasibility and scalability

It is **deployed and running right now** — not a prototype behind a login. Frontend on Vercel,
API on Render, Postgres on Neon, entirely on free tiers.

Scaling is a matter of configuration, not rewriting: [`docs/aws-deployment.md`](docs/aws-deployment.md)
maps every piece onto AWS (scheduler → EventBridge, jobs → Lambda, `runner.run_case` → Bedrock
AgentCore Runtime, Postgres → RDS, tracing → CloudWatch) without a single agent or prompt changing,
because `runner.py` is the one entry point into the agent system.

Real numbers we hit and fixed: matching the database region to the API region took a page load from
19.5s to 0.52s; eliminating an N+1 query took one endpoint from 21 queries to 6.

## User experience

One interface, four roles, no manuals. A restaurant posts food the way it would text a colleague.
A pantry sees what is coming. A driver accepts a pickup. A coordinator watches everything and
answers the few questions that are genuinely theirs.

The screen that matters is the offer page: a live five-stage tracker with the agents' own reasoning
streaming underneath, so a wait is legible instead of frightening.

## Tech stack

| Layer | Technology |
|---|---|
| AI agents | Strands Agents SDK · Groq (`openai/gpt-oss-120b`), swappable to Bedrock/Anthropic/OpenAI |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic · APScheduler |
| Frontend | React 19 · Vite · React Router |
| Database | PostgreSQL (Neon) in production · SQLite locally |
| Deployment | Vercel · Render · Neon · cron-job.org |
| Testing / observability | pytest (247 tests) · OpenTelemetry |

## Run it locally

Python 3.11+ and Node 20+.

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env              # add a GROQ_API_KEY — see .env.example
python -m scripts.seed_demo --reset # builds the demo world (all passwords: demo1234)

uvicorn pantrypilot.web.main:app --reload   # terminal 1
cd frontend && npm install && npm run dev   # terminal 2
python -m pantrypilot.worker                # terminal 3 — this wakes the agents
```

Open http://localhost:5173. Run the tests with `pytest`.

To watch one offer run end to end with every tool call printed:

```bash
python -m scripts.run_agent_once --offer <id>
```

To deliberately create a hard case and see the agent escalate:

```bash
python -m scripts.trigger_hard_case --scenario spoilage
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — how the pieces fit, with a sequence diagram of the pause/resume flow
- [`docs/demo-script.md`](docs/demo-script.md) — 5-minute demo walkthrough
- [`docs/deployment.md`](docs/deployment.md) — deploying to Vercel + Render + Neon
- [`docs/aws-deployment.md`](docs/aws-deployment.md) — the AWS scaling path
- [`PLAN.md`](PLAN.md) — the full build log, including what was verified against a real model and what was deliberately deferred

## Honest limitations

- Agent runs take 1–3 minutes on a free model tier. Key failover helps; a paid tier removes it.
- Agent session files live on ephemeral disk, so paused conversations are lost on redeploy.
  Interrupt-and-resume works normally otherwise; moving sessions to Postgres is a one-file change.
- The demo world is seeded fictional data for a single city.

## Acknowledgements

Built with the [Strands Agents SDK](https://strandsagents.com). Model inference by
[Groq](https://groq.com). Hosted on Vercel, Render and Neon. Developed with AI-assisted tooling;
all architecture decisions, verification and the code in this repository are the team's own.

## License

[Apache-2.0](LICENSE)
