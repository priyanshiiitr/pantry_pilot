# PantryPilot 🥫

**An AI agent team that routes surplus food from restaurants to food pantries — and only asks a human when there is a real decision to make.**

Built for the AWS "Agents for Humans" hackathon with the [Strands Agents SDK](https://strandsagents.com).

> ✅ Feature-complete hackathon build. See [PLAN.md](PLAN.md) for the full step-by-step build log.

## The problem

Restaurants, bakeries and grocery stores end each day with good surplus food. Nearby pantries and shelters need it.
Today one overworked coordinator matches them by phone and spreadsheet, and a lot of food spoils.

PantryPilot's agents do the coordination in the background: read the offer, pick the best pantry, dispatch a
volunteer driver, explain every choice, and raise a decision card for a human admin only when they hit a real
judgment call.

## Quickstart (Windows PowerShell)

You need **Python 3.11+** and **Node.js 20+**.

```powershell
# 1. Backend — from the project folder
python -m venv .venv
.venv\Scripts\Activate.ps1            # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
copy .env.example .env                # then add your GROQ_API_KEY (or another provider's) — see .env.example
python -m scripts.seed_demo --reset   # build the demo Seattle world (all passwords: demo1234)
python -m scripts.show_db             # optional: see what's in the database
uvicorn pantrypilot.web.main:app --reload

# 2. Frontend — in a second terminal
cd frontend
npm install
npm run dev

# 3. Background agent worker — in a third terminal (this is what makes it agentic:
#    it wakes up on its own, no button click)
python -m pantrypilot.worker
```

Open **http://localhost:5173**. Sign up, or log in with any seeded account (e.g. `hope@pantrypilot.test` /
`demo1234` for a pantry, `admin@pantrypilot.test` for the admin view). A restaurant account can post a
surplus food offer and watch its status live; the admin account sees every offer posted, the agent
activity log, and the Decisions inbox when the agent needs a human's judgment call.

To see a real escalation: `python -m scripts.trigger_hard_case --scenario spoilage` (also try
`no_drivers`, `fairness`, `unclear_allergens`), then either wait for the worker or run
`python -m scripts.run_agent_once --offer <id>` — if the agent decides it's genuinely stuck, a decision
card appears at `/admin/decisions` with its reasoning and options.

Run the tests with `pytest`.

## Project layout

| Folder | What's in it |
|---|---|
| [`pantrypilot/`](pantrypilot/README.md) | Python backend: API, database, agents, worker |
| [`frontend/`](frontend/README.md) | React app |
| `tests/` | pytest tests |
| [`docs/`](docs/architecture.md) | [Architecture](docs/architecture.md) (with diagrams), [AWS deployment path](docs/aws-deployment.md), [demo script](docs/demo-script.md) |
| [`deploy/agentcore_app.py`](deploy/agentcore_app.py) | Stub entrypoint for hosting the agent team on AWS Bedrock AgentCore Runtime (not needed to run locally) |

## Which Strands features we used and where

| Feature | Where | What it does here |
|---|---|---|
| `@tool` decorator | [`pantrypilot/agents/tools/`](pantrypilot/agents/tools/) | Exposes plain Python functions (distance checks, database lookups) as things the agent can choose to call. |
| `structured_output_model` | [`agents/schemas.py`](pantrypilot/agents/schemas.py), [`agents/matching_agent.py`](pantrypilot/agents/matching_agent.py) | Forces the Matching agent's decision into a validated `MatchProposal` (Pydantic) instead of loose prose. |
| Model providers | [`agents/model_provider.py`](pantrypilot/agents/model_provider.py) | Builds the model from `.env` — Groq (`openai/gpt-oss-120b`, via Strands' `OpenAIModel` pointed at Groq's URL), Anthropic, Bedrock or OpenAI, chosen with one setting. |
| Hooks | [`agents/hooks/reasoning_log_hook.py`](pantrypilot/agents/hooks/reasoning_log_hook.py) | Listens for `BeforeToolCallEvent`/`AfterToolCallEvent` and writes every tool call, its input and its result into the `agent_log` table — the admin "Agent activity" timeline reads this. |
| Multi-agent (agents-as-tools) | [`agents/coordinator_agent.py`](pantrypilot/agents/coordinator_agent.py) | A Coordinator agent treats Intake, Matching and Dispatch as tools it can call in whatever order and however many times it decides — not a fixed pipeline. It also decides whether to commit, retry, or flag the case for a human. |
| Structured output (more) | [`agents/schemas.py`](pantrypilot/agents/schemas.py) | `OfferDetails`, `DispatchPlan`, `CaseUpdate` — every specialist's answer is a validated Pydantic object. |
| Background execution | [`worker/`](pantrypilot/worker/README.md) | An APScheduler timer (not a request handler) wakes the agent team up on its own every 15 seconds — nobody has to click a button. |
| Sessions | [`agents/sessions.py`](pantrypilot/agents/sessions.py) | A `FileSessionManager` per offer, so the Coordinator's own prior reasoning survives a decline, a timeout, or the worker process restarting — verified live: a second, independently-built `Agent` object correctly recalled a fact from the first one's conversation. |
| Interrupts (human-in-the-loop) | [`agents/tools/human_tools.py`](pantrypilot/agents/tools/human_tools.py), [`agents/runner.py`](pantrypilot/agents/runner.py) | The `ask_admin` tool calls `tool_context.interrupt(...)`, genuinely pausing the agent mid-conversation. `runner.py` saves the paused question as a `Decision`, and `resume_case()` continues the *exact same* paused conversation once an admin answers — verified live end-to-end against Groq, including a fresh `Agent` object correctly resuming after the pause. |
| Structured output (more) | [`web/schemas.py`](pantrypilot/web/schemas.py) `DecisionOut` | The admin sees the agent's own decision card — title, situation, reasoning, options, recommendation — exactly as the model wrote it, not reshaped by our code. |
| Memory | [`agents/tools/memory_tools.py`](pantrypilot/agents/tools/memory_tools.py), [`services/memory.py`](pantrypilot/services/memory.py) | `recall_facts`/`remember_fact` tools backed by a simple table (evaluated Strands' native `MemoryManager` and chose to keep this — it integrates directly with the admin "What the agent remembers" page). |
| Observability (tracing) | [`agents/telemetry.py`](pantrypilot/agents/telemetry.py) | `StrandsTelemetry().setup_console_exporter()`, enabled via `OTEL_CONSOLE=true` — verified live producing real OpenTelemetry spans (`gen_ai.system.message`, `gen_ai.user.message`, `gen_ai.choice`, token usage) for every model call. |

All of this is complete for the hackathon build, including tests (164, all passing, zero API cost — see
`tests/`) and docs (`docs/architecture.md`, `docs/demo-script.md`, `docs/aws-deployment.md`).

## Learn more

- [`docs/architecture.md`](docs/architecture.md) — how the three processes and four agents fit together,
  with a sequence diagram of the pause/resume-for-a-human flow.
- [`docs/demo-script.md`](docs/demo-script.md) — a 5-minute demo shot list, including a live escalation.
- [`docs/aws-deployment.md`](docs/aws-deployment.md) — how each local piece (worker, runner, sessions,
  tracing) maps onto EventBridge, Lambda, AgentCore Runtime, RDS and CloudWatch.
- [PLAN.md](PLAN.md) — the full build log, step by step, with what was verified live against a real model
  and what was deliberately deferred.

## License

[Apache-2.0](LICENSE)
