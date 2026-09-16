# PantryPilot — Build Plan

> Status: **DRAFT — waiting for your approval.** No code has been written yet.

---

## 1. The idea in one paragraph

Restaurants post leftover food. A small **team of AI agents** wakes up on its own, reads the offer, checks which food pantries can take it, picks one, and asks a volunteer driver to collect it. It explains **why** it chose what it chose. When it hits something it can't decide responsibly (the food will spoil first, no drivers, unfair split, unclear allergens), it **pauses and asks a human admin** with a "decision card". The admin clicks an option and the agent carries on from where it stopped.

---

## 2. What I checked in the Strands docs (and the version I'm pinning)

I read the current docs at strandsagents.com. I also downloaded the real package and read its source code, so the names below are what the installed library actually exposes, not what I remember.

**Pinned version: `strands-agents==1.55.1`**, the newest release on PyPI today. We install it with the extras `[anthropic,openai,otel]`.
*(An "extra" is an optional add-on bundle: `anthropic` = the Claude API client, `otel` = tracing support.)*

Note: the Python SDK source has moved into the `strands-agents/harness-sdk` GitHub repo (folder `strands-py`), but the pip package name is still `strands-agents`.

| Feature | Exact API in 1.55.1 | What it means in plain words |
|---|---|---|
| Tools | `from strands import tool, ToolContext` → `@tool`, `@tool(context=True)` | Put `@tool` above a normal Python function and the agent is allowed to call it. The docstring becomes the explanation the AI reads. |
| Agent | `Agent(model=, system_prompt=, tools=, name=, agent_id=, hooks=, session_manager=, structured_output_model=, trace_attributes=)` | One AI "worker" with its instructions and its toolbox. |
| Structured output | `result = agent(prompt, structured_output_model=MyModel)` → `result.structured_output` · errors raise `strands.types.exceptions.StructuredOutputException` | Forces the AI to reply with a filled-in form (a Pydantic class) instead of free text, and checks the form is valid. (The old `agent.structured_output()` is deprecated, so we won't use it.) |
| Multi-agent | Agents-as-tools: call a specialist agent from inside an `@tool` function (a shortcut `Agent.as_tool(...)` also exists). Also available: `from strands.multiagent import GraphBuilder, Swarm` | A "manager" agent that can call "specialist" agents the same way it calls a tool. |
| Interrupts (human-in-the-loop) | Inside a tool: `tool_context.interrupt("name", reason={...})` · inside a hook: `event.interrupt(...)` on `BeforeToolCallEvent` · check `result.stop_reason == "interrupt"` and `result.interrupts` (each has `.id`, `.name`, `.reason`) · resume with `agent([{"interruptResponse": {"interruptId": id, "response": value}}])` | The agent can stop mid-task, say "I need a human", and later pick up exactly where it paused once it gets the answer. |
| Hooks | `from strands.hooks import HookProvider, HookRegistry, BeforeInvocationEvent, AfterInvocationEvent, BeforeToolCallEvent, AfterToolCallEvent, MessageAddedEvent` | Little "listeners" that run automatically at moments like "the agent is about to call a tool". We use them for logging and for an approval gate. |
| Sessions | `from strands.session import FileSessionManager` → `FileSessionManager(session_id=, storage_dir=)`. Later swap: `S3SessionManager`, or `RepositorySessionManager(session_id=, session_repository=)` with our own storage. | Saves the agent's conversation, state **and paused-interrupt state** to disk, so a restart doesn't lose it. |
| Memory | `strands.memory.MemoryManager` / `MemoryStore` (new in recent versions) | Long-term facts across many offers. I'll evaluate it in Step 13 and fall back to a simple table plus tools if it's too complex. |
| Tracing | `from strands.telemetry import StrandsTelemetry` → `.setup_console_exporter()`, `.setup_otlp_exporter()` | Records a timeline of every model call and tool call (OpenTelemetry = an industry-standard format for traces). |
| Model providers | `strands.models.anthropic.AnthropicModel(client_args={"api_key": ...}, model_id=, max_tokens=)` · `strands.models.BedrockModel(model_id=, region_name=)` · `strands.models.openai.OpenAIModel(client_args=, model_id=)` | Switch AI provider through `.env`. |
| Ready-made approval (considered) | `strands.vended_interventions.hitl.HumanInTheLoop` via `Agent(interventions=[...])` | A built-in "ask before running tools" helper. We write our own small hook instead, so you can read exactly how it works and so the decision card has our format. |
| AgentCore (later) | `from bedrock_agentcore.runtime import BedrockAgentCoreApp` → `@app.entrypoint`, `app.run()` (package `bedrock-agentcore` 1.23.0) | A thin wrapper that lets AWS host our agent. Only used in the deployment doc and a stub file. |

---

## 3. Tech stack

| Piece | Choice | Why |
|---|---|---|
| Language | Python 3.12 (already installed on your machine) | — |
| Web server | **FastAPI** + **Uvicorn** | FastAPI = a Python web framework; Uvicorn = the program that runs it. |
| Database | **SQLite** via **SQLAlchemy 2** | SQLite = a database stored in one file, no setup. SQLAlchemy = Python classes that map to tables, so moving to Postgres later is a one-line change. |
| Frontend | **React 19** (plain JavaScript, no TypeScript) + **Vite 6** + **React Router** + plain CSS | *(Changed from Jinja2/HTMX at your request.)* React = build pages from reusable pieces called components. Vite = the dev tool that runs React on port 5173 and forwards `/api` calls to the backend. Vite 6 is chosen because your Node 22.11 is too old for Vite 8. |
| API style | FastAPI returns **JSON** under `/api/...` | The React app fetches data from these URLs. |
| Live updates | React polls the API every few seconds | "Polling" = asking the server "anything new?" on a timer. Simple and reliable. |
| Background jobs | **APScheduler** | A timer library: "run this function every 15 seconds". |
| Passwords | **bcrypt** | Stores a scrambled one-way version of each password, never the real one. |
| Login sessions | Starlette `SessionMiddleware` (signed cookie) | After login the browser holds a tamper-proof cookie with your user id. |
| Tests | **pytest** | — |
| Map | **Leaflet** + OpenStreetMap tiles | A simple, free map library. |

Exact versions of everything get pinned in `requirements.txt` in Step 1.

---

## 4. Folder structure

```
pantry_pilot/
├── LICENSE                  Apache-2.0
├── README.md                Problem, quickstart, "Strands features we used and where"
├── PLAN.md                  This file
├── requirements.txt         Pinned dependencies
├── .env.example             Template for secrets and settings (real .env is git-ignored)
├── docs/
│   ├── architecture.md      Diagram + explanation
│   ├── aws-deployment.md    EventBridge → Lambda → AgentCore path
│   └── demo-script.md       5-minute video, shot by shot
├── pantrypilot/             The Python application (a "package" = folder of Python files)
│   ├── README.md
│   ├── config.py            Reads .env into one settings object
│   ├── database.py          Database connection + session helper
│   ├── models/              DATABASE TABLES (SQLAlchemy classes)
│   │   ├── users.py         User accounts + roles
│   │   ├── places.py        Restaurant, Pantry, Driver profiles
│   │   ├── offers.py        Offer, Delivery, DispatchRequest
│   │   └── agent_records.py Decision, AgentRun, AgentLog, AgentMemory, Notification
│   ├── services/            PLAIN DETERMINISTIC LOGIC (no AI) shared by web + tools
│   │   ├── geo.py           Distance (haversine formula), travel-time estimate, "is it open?"
│   │   ├── fairness.py      Computes how much each pantry received recently (numbers only)
│   │   ├── offers.py        Create/update offers and deliveries safely
│   │   └── notifications.py Store messages for users
│   ├── auth/
│   │   ├── passwords.py     Hash + check passwords
│   │   └── current_user.py  "Who is logged in?" + "is this user allowed here?"
│   ├── web/                 JSON API that the React frontend calls (all URLs start with /api)
│   │   ├── main.py          Creates the FastAPI app and attaches the routers
│   │   ├── schemas.py       Pydantic shapes of API requests/responses
│   │   └── routes/          auth.py, restaurant.py, pantry.py, driver.py, admin.py, decisions.py, demo.py
│   ├── agents/              THE AI REASONING LAYER
│   │   ├── README.md
│   │   ├── model_provider.py    Builds the AI model from .env
│   │   ├── schemas.py           Pydantic "forms" the agents must fill in
│   │   ├── prompts/             intake.md, matching.md, dispatch.md, coordinator.md
│   │   ├── intake_agent.py
│   │   ├── matching_agent.py
│   │   ├── dispatch_agent.py
│   │   ├── coordinator_agent.py
│   │   ├── tools/               offer_tools, pantry_tools, driver_tools, action_tools, memory_tools, human_tools
│   │   ├── hooks/               reasoning_log_hook.py, approval_gate_hook.py
│   │   ├── sessions.py          Session-manager factory (file now; S3/AgentCore later)
│   │   ├── telemetry.py         Turns on OpenTelemetry tracing
│   │   └── runner.py            run_case() and resume_case(): the only entry points into the agents
│   ├── worker/
│   │   ├── __main__.py      `python -m pantrypilot.worker` starts the background loop
│   │   └── jobs.py          The scheduled jobs
│   └── deploy/
│       └── agentcore_app.py Stub AgentCore entrypoint (not needed locally)
├── frontend/                ★ THE REACT FRONTEND (see section 4.1)
│   ├── README.md
│   ├── package.json         JavaScript dependencies (like requirements.txt)
│   ├── vite.config.js       Dev server on :5173, forwards /api to FastAPI on :8000
│   ├── index.html
│   └── src/
│       ├── main.jsx         Starts React
│       ├── App.jsx          Page routes (which URL shows which page)
│       ├── api.js           The ONLY file that calls the backend
│       ├── auth/            Login state (who is logged in), route guards per role
│       ├── pages/           restaurant/, pantry/, driver/, admin/, auth/
│       ├── components/      StatusBadge, OfferCard, DecisionCard, ActivityTimeline, StatCard, MapView, Layout
│       ├── hooks/           usePolling.js (refresh data every few seconds)
│       └── styles.css       All styling, colours as CSS variables
├── scripts/
│   ├── seed_demo.py         Builds a fake city: pantries, drivers, restaurants, accounts
│   ├── trigger_hard_case.py Creates a scenario that should make the agent escalate
│   └── reset_db.py          Wipe and start fresh
├── tests/
└── data/                    (git-ignored) pantrypilot.db, sessions/
```

---

## 4.1 The frontend — where it lives and how it works

**Where:** the top-level **`frontend/`** folder, a React app (changed from server-rendered templates at your request). The backend (`pantrypilot/web/`) only returns JSON.

**Two programs during development:**
- `uvicorn pantrypilot.web.main:app --reload` → backend on **http://localhost:8000**
- `npm run dev` inside `frontend/` → React app on **http://localhost:5173** (the address you open)

Vite forwards (*proxies*) any `/api/...` request from the React app to port 8000. The browser therefore sees a single website, so login cookies work with no CORS setup (CORS = the browser's cross-website security rules).

**How a page is made (example: restaurant's "My offers"):**
1. The browser opens `http://localhost:5173/restaurant`. **React Router** (maps URLs to page components) shows `pages/restaurant/RestaurantHome.jsx`.
2. That component calls `api.js → GET /api/restaurant/offers`. FastAPI checks the login cookie and role, then returns the offers as JSON.
3. React draws the list using small components like `<OfferCard>` and `<StatusBadge>`.
4. **Live updates:** a `usePolling` hook re-fetches every 3 seconds, so you watch the agent's progress without refreshing.
5. **Buttons** (Accept, Decline, pick a decision option) call `api.js → POST /api/...`, then refresh the data.

**Later, for the demo/deploy:** `npm run build` produces static files in `frontend/dist/`, which FastAPI can serve itself, so one command runs everything (Step 15).

**Every page, by role** (these are React Router URLs; each page reads from matching `/api/...` endpoints):

| Role | Page (URL) | What's on it | Built in step |
|---|---|---|---|
| Everyone | `/` | Landing page: what PantryPilot is, Login / Sign up | 1, 3 |
| Everyone | `/login`, `/signup` | Forms; sign up lets you pick a role | 3 |
| Restaurant | `/restaurant` | My offers with live status badges, "Post surplus food" button | 5 |
| Restaurant | `/restaurant/offers/new` | Form: description, quantity, allergens, collect-by time | 5 |
| Restaurant | `/restaurant/offers/{id}` | Timeline for one offer: which pantry, which driver, the agent's reason in plain words | 5, 8 |
| Restaurant | `/restaurant/profile` | Name, address | 4 |
| Pantry | `/pantry` | Incoming deliveries (Accept / Decline), received this week | 10 |
| Pantry | `/pantry/profile` | Capacity, opening hours, fridge/freezer, dietary restrictions | 4 |
| Driver | `/driver` | On-duty toggle, new requests (Accept / Decline with reason), my active trip | 10 |
| Driver | `/driver/trips/{id}` | Pickup and drop-off addresses, "Picked up" and "Delivered" buttons | 10 |
| Driver | `/driver/profile` | Area, radius, vehicle, weekly availability | 4 |
| Admin | `/admin` | Overview: stat cards, pending decisions, live activity feed, mini map | 12 |
| Admin | `/admin/decisions` | **Decisions inbox**: cards with the situation, the agent's reasoning, options (with its recommended one highlighted) and action buttons | 11 |
| Admin | `/admin/decisions/{id}` | Full card + the agent's full trail for that offer + "remember this" note | 11 |
| Admin | `/admin/activity` | Timeline of agent runs → tool calls → reasons, filterable by offer/agent | 7, 12 |
| Admin | `/admin/users`, `/admin/users/{id}` | All restaurants, pantries, drivers, with status and history | 12 |
| Admin | `/admin/map` | Leaflet map: restaurants, pantries, drivers, active trips | 12 |
| Admin | `/admin/memory` | What the agent remembers, with delete | 13 |
| Admin | "Demo scenarios" panel | Trigger-a-hard-case buttons | 11 |

**Look and feel:** clean card-based layout with one colour per role, status badges (grey = posted, blue = agent working, amber = needs human, green = delivered), and it works on a phone-width screen so the driver page feels like an app. Frontend work is spread through the steps above, not left to the end. Step 12 is the visual polish pass.

---

The **separation rule** (also written in code comments):
- `agents/` = **reasoning**. The AI decides things here.
- `services/`, `models/`, `auth/`, `worker/` = **deterministic**. Normal code: saving to the database, logins, timers. It never decides *which* pantry or driver.
- Tools are the bridge. They either **fetch facts** (return data, never a verdict) or **perform an action the agent chose**. Action tools do basic safety validation (e.g. "that pantry id doesn't exist", "that driver is already busy") and hand the error back to the agent, which must rethink.

---

## 5. Database tables

| Table | Key columns | Purpose |
|---|---|---|
| `users` | id, email, password_hash, role (`restaurant`/`pantry`/`driver`/`admin`), display_name, created_at | Every login account |
| `restaurants` | id, user_id, name, address, lat, lon, phone | Donor profile |
| `pantries` | id, user_id, name, address, lat, lon, capacity_kg_per_day, has_fridge, has_freezer, dietary_restrictions (JSON list, e.g. `["no_pork"]`), opening_hours (JSON), notes | Recipient profile |
| `drivers` | id, user_id, name, lat, lon, service_radius_km, max_kg, has_cooler, availability (JSON weekly slots), on_duty | Volunteer profile |
| `offers` | id, restaurant_id, description (free text), quantity_text, pickup_deadline, status, structured_details (JSON from intake agent), agent_summary, created_at, updated_at | One surplus food post |
| `deliveries` | id, offer_id, pantry_id, driver_id, status, kg, meals, match_reasoning, dispatch_reasoning, timestamps (assigned/picked_up/delivered) | The planned trip for an offer |
| `dispatch_requests` | id, delivery_id, driver_id, status (`requested`/`accepted`/`declined`/`expired`), decline_reason, sent_at, responded_at | Every ask to a driver (history lets the agent learn "Sam declines evenings") |
| `decisions` | id, offer_id, kind (`agent_escalation`/`approval_gate`), interrupt_id, interrupt_name, card (JSON), status (`pending`/`answered`/`resumed`/`failed`), chosen_option, admin_note, answered_by, created_at, answered_at | The Decisions inbox, which **survives restarts** |
| `agent_runs` | id, offer_id, trigger (`new_offer`/`driver_declined`/`pantry_declined`/`timeout`/`admin_decision`), started_at, finished_at, stop_reason, outcome (JSON), error | One row per time the agents woke up |
| `agent_log` | id, run_id, offer_id, agent_name, event_type (`tool_call`/`tool_result`/`reasoning`/`decision`/`interrupt`/`resumed`/`error`), tool_name, summary, details (JSON), created_at | Human-readable activity timeline |
| `agent_memory` | id, subject_type (`pantry`/`driver`/`restaurant`), subject_id, fact, source (`agent`/`admin`), created_at, active | Long-term facts ("Riverside can't take pork") |
| `notifications` | id, user_id, message, link, created_at, read | Messages shown to each user |
| `app_settings` | key, value | e.g. `supervised_mode` on/off |

**Offer lifecycle:**
`posted → agent_working → driver_requested → driver_assigned → picked_up → delivered`
Side paths: `needs_human` (waiting in Decisions inbox) → back to `agent_working`; `expired`; `cancelled`.

---

## 6. The agent team

### Which multi-agent pattern: **Agents-as-Tools** (recommended)

Strands offers three patterns:
- **Graph**: *you* draw fixed arrows (intake → matching → dispatch). Predictable, but the route is decided by code.
- **Swarm**: agents hand work to each other freely. Flexible, but hard to follow and hard to debug.
- **Agents-as-Tools**: one **Coordinator** agent treats each specialist as a tool and decides whom to call, when, and how often.

**Why agents-as-tools fits PantryPilot best:**
1. **The AI chooses the route, not our code.** If a driver declines, the Coordinator can decide to re-run dispatch, re-run matching with a different pantry, or escalate. With a Graph, those paths would be hard-coded arrows, the "rule engine with an AI sticker" we want to avoid.
2. **Escalation lives in one place.** Only the Coordinator has the `ask_admin` tool, which matches your brief ("Coordinator decides when a human must be asked").
3. **Each specialist returns a validated form.** Calling a specialist inside our own `@tool` function lets us use `structured_output_model` and log its reasoning. The Graph docs don't clearly cover structured output per node.
4. **Easiest for a beginner to read**: one manager plus a few helpers, each in its own file.
5. **Sessions are simpler.** Only the Coordinator needs a session manager (one per offer). The specialists start fresh each time and read long-term facts through memory tools.

### The four agents

| Agent | Job | Its tools | Returns (Pydantic form) |
|---|---|---|---|
| **Intake** | Turn "40 chicken sandwiches, grab by 6, has cheese" into clean data, and flag anything unclear or unsafe | `get_offer`, `get_current_time` | `OfferDetails`: items, est_kg, est_meals, allergens, dietary_tags, perishability, safe_until, concerns, confidence |
| **Matching** | Choose the best pantry and explain why the others lost | `find_nearby_pantries`, `get_pantry_profile`, `check_pantry_capacity`, `calculate_fairness_score`, `estimate_travel_time`, `recall_facts` | `MatchProposal`: chosen_pantry_id (or none), ranked candidates each with a reason, reasoning, concerns, confident_to_proceed |
| **Dispatch** | Choose a driver who can get there in time | `get_available_drivers`, `get_driver_history`, `estimate_travel_time`, `recall_facts` | `DispatchPlan`: driver_id (or none), eta_minutes, backup_driver_ids, reasoning, concerns |
| **Coordinator** (manager) | Run the case end-to-end, commit actions, react to events, decide when a human is needed | `run_intake`, `run_matching`, `run_dispatch` (the specialists), `assign_delivery`, `send_dispatch_request`, `cancel_offer`, `notify_user`, `remember_fact`, `recall_facts`, `ask_admin` | `CaseUpdate`: status, summary, reasoning |

Every action tool takes a required `reason: str` argument, so the agent **must** write why it's acting. That text goes into the log and the UI.

### Tool list (Python functions exposed with `@tool`)

**Fact-finding** (return data only, never a verdict):
- `get_offer(offer_id)`: offer text, restaurant location, deadline
- `get_current_time()`: now (AIs don't know the time otherwise)
- `find_nearby_pantries(lat, lon, radius_km)`: pantries with distance and whether open now or later
- `get_pantry_profile(pantry_id)`: hours, fridge/freezer, dietary restrictions, notes
- `check_pantry_capacity(pantry_id)`: capacity today and already received today
- `calculate_fairness_score(pantry_id, extra_kg)`: this pantry's share of food over the last 7 days, before and after this delivery, compared with the average
- `get_available_drivers(lat, lon, needed_by)`: on-duty drivers in range, with vehicle info
- `get_driver_history(driver_id)`: accept/decline stats, including by time of day
- `estimate_travel_time(from_lat, from_lon, to_lat, to_lon)`: rough minutes
- `recall_facts(subject_type, subject_id)`: remembered facts

**Actions** (the agent decided; code executes safely):
- `assign_delivery(offer_id, pantry_id, reason)`
- `send_dispatch_request(delivery_id, driver_id, reason)`
- `cancel_offer(offer_id, reason)`
- `notify_user(user_id, message)`
- `remember_fact(subject_type, subject_id, fact, reason)`
- `ask_admin(title, situation, reasoning, options, recommended_option, urgency)`: **raises the interrupt**

---

## 7. How escalation (the interrupt) works, step by step

```mermaid
sequenceDiagram
    participant W as Worker (timer)
    participant R as runner.py
    participant C as Coordinator agent
    participant DB as SQLite + session files
    participant A as Admin (browser)

    W->>R: new offer found → run_case(offer 7)
    R->>C: "New offer 7. Handle it."
    C->>C: calls intake, matching, dispatch…
    C->>C: reasons: "nothing reaches a pantry before it spoils"
    C->>C: calls ask_admin(card) → tool_context.interrupt()
    C-->>R: result.stop_reason == "interrupt"
    R->>DB: save Decision(interrupt_id, card), offer = needs_human
    Note over DB: Session manager already saved the paused agent to data/sessions/offer-7
    A->>DB: clicks "Send to shelter with freezer 12 km away"
    Note over W: (worker may even restart here — nothing is lost)
    W->>R: answered decision found → resume_case(decision)
    R->>C: rebuild Coordinator with session "offer-7"
    R->>C: agent([{"interruptResponse": {"interruptId": id, "response": choice}}])
    C->>C: ask_admin returns the admin's choice → agent continues
    C->>DB: assign_delivery, send_dispatch_request…
```

Key points in plain words:
1. **The AI decides to escalate.** Its system prompt tells it *when it should consider* asking a human (food safety, time, fairness, missing info). No `if` statement in our code forces it.
2. **`ask_admin` is a tool with a strict form.** The agent fills in the title, situation, reasoning and 2–4 options, each with consequences, plus its recommendation. Pydantic validates the form, so the card always looks right.
3. **Pausing = `tool_context.interrupt(...)`.** Strands stops the agent and returns `stop_reason == "interrupt"`.
4. **Two places remember the pause:** our `decisions` table (for the inbox UI) and Strands' `FileSessionManager` (for the agent's own memory of the conversation and the paused tool call).
5. **Resuming** rebuilds the Coordinator with the same `session_id` and sends the admin's answer. Inside the paused tool, `interrupt()` now *returns* the answer instead of stopping, and the agent continues.
6. **Approval gate (second kind of interrupt):** an `ApprovalGateHook` listens to `BeforeToolCallEvent`. When the admin turns on **Supervised mode**, every `assign_delivery` pauses for approval. This is a policy switch a human sets, clearly labelled in code as *deterministic policy, not AI reasoning*. It's off by default.
7. **Driver/pantry replies are not interrupts.** When a driver declines or doesn't answer in time, the worker simply wakes the Coordinator again with a new message ("Driver Sam declined: car trouble"). Thanks to the session it remembers the whole case.

**"Trigger a hard case"** (`scripts/trigger_hard_case.py --scenario spoilage|no_drivers|fairness|unclear_allergens`, plus a button on the admin dashboard) sets up a situation where a responsible agent *should* escalate. It does **not** force an escalation in code. That's more honest and a better demo. If the agent handles it without asking, the log will show why.

---

## 8. Background execution

- A separate **worker process** (`python -m pantrypilot.worker`) runs APScheduler jobs:
  - every 15 s: `pick_up_new_offers`: claim `posted` offers → `run_case`
  - every 10 s: `resume_answered_decisions`
  - every 30 s: `check_waiting_cases`: expired driver requests, declines, pantry declines, deadlines → wake the Coordinator
- The web server never runs agents. It only writes to the database.
- **AWS mapping** (documented in `docs/aws-deployment.md`): APScheduler → **EventBridge Scheduler**; each job → a small **Lambda**; `runner.run_case` → **AgentCore Runtime** entrypoint; SQLite → **RDS Postgres**; session files → **S3SessionManager** or **AgentCore Memory**; tracing → **CloudWatch** via AgentCore observability.

---

## 9. Observability

- **`agent_log` table**: written by `ReasoningLogHook` (tool called, with inputs, result summary, reasoning text) and by `runner.py` (run started, interrupted, resumed, finished). The admin "Agent activity" page reads this.
- **OpenTelemetry**: `StrandsTelemetry` turned on from `.env` (`OTEL_CONSOLE=true` prints spans; `OTEL_EXPORTER_OTLP_ENDPOINT` sends them to Jaeger if you run it). A "span" is one timed step, like one model call.

---

## 10. Model configuration (`.env`)

```
MODEL_PROVIDER=anthropic          # anthropic | bedrock | openai
ANTHROPIC_API_KEY=...
MODEL_ID=claude-haiku-4-5-20251001  # cheap + fast default
COORDINATOR_MODEL_ID=               # optional: a stronger model just for the Coordinator
AWS_REGION=us-east-1                # if bedrock
OPENAI_API_KEY=...                  # if openai
```

Exact Bedrock/OpenAI model ids are confirmed in Step 6. Keys are never hard-coded. Tests use a **scripted fake model**, so running `pytest` costs nothing.

---

## 11. Step-by-step build plan

Each step ends with something you can run and see. After each step I list the files, explain them file by file, give the command and the expected result, then **stop and wait for "next"**. Small tests and README updates are added as we go, not saved for the end.

### Phase A — Foundations (no AI yet)

**Step 1 — Project skeleton (backend + React)** ✅ done
Creates: `LICENSE` (Apache-2.0), `.gitignore`, `requirements.txt` (pinned), `.env.example`, `pantrypilot/config.py`, `pantrypilot/web/main.py` (`GET /api/health`), `frontend/` (Vite + React app that calls the health check), `tests/test_health.py`, starter `README.md`.
You run: terminal 1 `uvicorn pantrypilot.web.main:app --reload`; terminal 2 `cd frontend; npm run dev`
You see: `http://localhost:5173` shows the PantryPilot card with "✓ Backend connected".

**Step 2 — Database tables + seed data** ✅ done
Creates: `database.py`, `models/*` (users, places, offers, agent_records, system), `auth/passwords.py`, `scripts/demo_world.py` (Seattle data), `scripts/seed_demo.py`, `scripts/show_db.py`, `scripts/reset_db.py`, `pytest.ini`, tests.
You run: `python -m scripts.seed_demo --reset` then `python -m scripts.show_db`
You see: a printed summary (5 restaurants, 7 pantries, 8 drivers, 1 admin, 14 past deliveries) plus the demo logins, and a `data/pantrypilot.db` file.

**Step 3 — Signup, login, four roles** ✅ done
Creates: backend `auth/current_user.py` (session dependency + role guard), `services/accounts.py`, `web/schemas.py`, `web/routes/auth.py` (`/api/auth/signup`, `/login`, `/logout`, `/me`), `SessionMiddleware` in `web/main.py`; frontend `react-router-dom`, `auth/AuthContext.jsx` + `RequireRole.jsx`, `components/Layout.jsx`, Login/Signup pages, a placeholder home page per role.
You see: open 4 browser profiles, sign up as each role, and each lands on its own dashboard. Typing another role's URL bounces you back to your own. Seeded demo accounts (password `demo1234`) can log in too.

**Step 4 — Profiles** ✅ done
Creates: backend `services/profiles.py`, profile GET/PUT on each role's router, hours/dietary-tag validators in `web/schemas.py`; frontend `hooks/useProfileForm.js`, `components/WeeklyHoursEditor.jsx` (shared by pantry hours + driver availability), three profile pages.
You see: edit capacity/hours/fridge/dietary restrictions (pantry), area/availability/on-duty (driver), or address (restaurant); save, refresh, values persist. Bad input (unknown dietary tag, closing time before opening time, out-of-range latitude) is rejected with a clear message.

**Step 5 — Restaurant posts an offer** ✅ done
Creates: backend `services/offers.py`, offer schemas + validators (deadline must be future, non-blank fields), `/api/restaurant/offers` (create/list/get), `/api/admin/offers` (list-all); frontend `hooks/usePolling.js`, `components/StatusBadge.jsx`, `NewOffer`/`OfferDetail` pages, live-updating restaurant home, basic admin offers table.
You see: post "40 sandwiches, contains dairy, collect by 18:00" and it appears with status `posted` for both the restaurant and the admin.

### Phase B — The agents

**Step 6 — First agent, read-only tools, structured output** ✅ done, verified live against Groq
Creates: `services/geo.py` (haversine distance, travel-time estimate, `is_open_now`), `services/fairness.py`, `agents/model_provider.py` (Groq/Anthropic/Bedrock/OpenAI, chosen from `.env` — **decided: Groq free tier, model `openai/gpt-oss-120b`**, via Strands' OpenAI-compatible model class), `agents/schemas.py` (`MatchProposal`), `agents/tools/*` (offer/pantry/geo/memory fact-finding tools), `agents/matching_agent.py`, `agents/console.py` (fixes a Windows console Unicode crash — see below), `scripts/try_matching.py`. 58 tests pass without needing any API key.
You run: `python -m scripts.try_matching --offer <id>`
You see: in the terminal, each tool the agent chose to call, its live reasoning, then a validated `MatchProposal`. Confirmed live: the agent correctly ruled out pantries for missing fridges, halal-only conflicts, and being closed at arrival time, and correctly caught a genuinely-passed pickup deadline, returning `chosen_pantry_id: null, confident_to_proceed: false` with clear concerns for a human — exactly the shape Step 11's escalation will consume. Nothing is written to the database yet.

**Gotcha found and fixed:** on Windows, the model occasionally emits Unicode characters (narrow spaces, smart punctuation) that the default console encoding (cp1252) can't print. Strands' live-streaming callback would crash mid-print, and the surrounding retry logic silently re-ran the whole model call — which looked exactly like an infinite reasoning loop until diagnosed. Fixed once in `agents/console.py`; every future entrypoint that runs an agent must call `ensure_utf8_console()` at startup.

**Step 7 — Hooks + activity log** ✅ done
Creates: `services/activity_log.py` (deterministic: `start_agent_run`/`finish_agent_run`/`log_event`/`list_recent_log_entries`), `agents/hooks/reasoning_log_hook.py` (`ReasoningLogHook`, a `HookProvider` listening for `BeforeToolCallEvent`/`AfterToolCallEvent`), wired into `matching_agent.propose_match()`; `/api/admin/activity`; frontend `ActivityLog.jsx` page + nav link.
**Also fixed a real test-isolation bug**: agent tools/services open their own `SessionLocal()` — a plain `from ... import SessionLocal` freezes the real database at import time, so tests couldn't swap in a temp one. Switched every such module to `from pantrypilot import database` + `database.SessionLocal()`, and the `db_session` test fixture now monkeypatches `pantrypilot.database.SessionLocal` to match.
You see: rerun `try_matching.py`, then open `/admin/activity` and see the timeline of tool calls, results and the final decision, newest first, refreshing live.

**Step 8 — The full agent team (agents-as-tools)** ✅ done
Creates: `agents/schemas.py` additions (`OfferDetails`, `DispatchPlan`, `CaseUpdate`), `intake_agent.py`, `dispatch_agent.py` (+ `agents/tools/driver_tools.py`), `coordinator_agent.py` (agents-as-tools: `run_intake`/`run_matching`/`run_dispatch` as closures bound to one offer+run), `agents/tools/action_tools.py` (`assign_delivery`, `send_dispatch_request`, `flag_needs_human`, `cancel_offer`, `notify_user` — also closures, so the model never has to get an `offer_id` right by itself), `services/offers.py`/`services/notifications.py` additions, `runner.py` (`run_case` — the one entry point), `scripts/run_agent_once.py`. 84 tests pass.
You run: `python -m scripts.run_agent_once --offer <id>`
You see: the offer moves through `agent_working` → `driver_requested` (or `needs_human`/`cancelled` if the Coordinator can't safely proceed), the restaurant's offer detail page shows the agent's summary, and a delivery + dispatch request are visible in the database (their own dashboard pages arrive in Step 10).
**Bugs caught and fixed along the way**: a `send_dispatch_request` autoflush-ordering issue (adding a new row to the session before touching a lazy-loaded relationship it's linked to), and a latent "newest first" tie-breaking bug across four different queries — `order_by(created_at.desc())` alone isn't deterministic when two rows are created within the same timestamp resolution window; fixed by adding `id.desc()` as a secondary sort key everywhere `created_at` was used as a sole sort key.

**Step 9 — Background scheduler (no button needed)** ✅ done
Creates: `worker/__main__.py` (APScheduler `BlockingScheduler`, creates tables on startup so a brand-new database works with no separate migrate step), `worker/jobs.py` (`pick_up_new_offers`: finds every `posted` offer and runs the full agent team on it; one offer failing never blocks the rest).
You run: terminal 1 = web server, terminal 2 = `python -m pantrypilot.worker`
You see: post an offer in the browser, touch nothing, and within 15 seconds its status flips to `agent_working` by itself — **verified live**: started the worker against a fresh database with one posted offer, and it claimed it (status `posted` → `agent_working`, `claimed_at` set) with zero manual intervention. The offer/activity log pages (already polling since Steps 5/7) pick up every subsequent change automatically — no new frontend work was needed for this step.

**Step 10 — Driver + pantry flows, and sessions** ✅ done
Split `services/offers.py` into `offers.py` (offer-level), `deliveries.py`, `dispatch.py` (one responsibility each, kept under ~250 lines). Added: `requeue_offer_for_retry` (puts a declined/timed-out offer back to `posted` with a note); pantry accept/decline (`get_pending_deliveries_for_pantry`, `accept_delivery`, `decline_delivery`); driver accept/decline + pickup/delivered (`get_pending_dispatch_requests_for_driver`, `accept_dispatch_request`, `decline_dispatch_request`, `get_active_trips_for_driver`, `mark_picked_up`, `mark_delivered`); `worker/jobs.py`'s `expire_stale_dispatch_requests` (a driver who never responds gets the same treatment as an explicit decline); `agents/sessions.py` (`FileSessionManager` per offer, wired into `runner.run_case` via a new `context_message` parameter so a re-run tells the Coordinator specifically what changed). Frontend: real Pantry/Driver dashboards (`DeclineButton` shared component), 10 new API endpoints across `pantry.py`/`driver.py`.
You see: **the full happy path in 4 windows**: post → agent matches → driver accepts → picked up → delivered. Also: decline as a pantry or driver and the offer goes back to `posted` with a note, ready for the worker to re-run the agent.
**Verified live and end-to-end**: a full deterministic HTTP run through the entire happy path and the decline/requeue path, both passing every check. Separately, verified the actual new capability — session memory — live against Groq: told one `Agent` instance "my favorite number is 42," discarded it, built a **completely new** `Agent` object pointed at the same session id, and asked "what's my favorite number?" with zero explicit context. It answered "42," confirming the Coordinator genuinely resumes its own prior reasoning across separate `run_case()` calls (and process restarts), not just superficial log continuity.
*Sessions in plain terms: without this, every re-run of `run_case()` for the same offer started from a blank slate. With `FileSessionManager` attached, the Agent reloads its actual prior conversation before reading the new prompt — this is what lets it genuinely know "I already asked Sam, he declined" instead of being told in a sentence and hoping it takes note.*

### Phase C — Human in the loop

**Step 11 — Interrupts + Decisions inbox** ✅ done (Supervised-mode approval gate and the admin trigger button deferred — see below)
Creates: `agents/tools/human_tools.py` (`ask_admin` — calls `tool_context.interrupt(...)`, genuinely pausing the agent), `services/decisions.py` (deterministic Decision CRUD), `runner.py` additions (`_handle_agent_result` shared by `run_case`/`resume_case`, `resume_case` itself), `/api/admin/decisions` (list/get/answer), `worker/jobs.py`'s `resume_answered_decisions` (answering is a fast, synchronous API call; resuming calls the model, so it happens separately on the worker's own 10s schedule), the **Decisions inbox** page, `scripts/trigger_hard_case.py` (4 scenarios: spoilage, no_drivers, fairness, unclear_allergens — doesn't force an escalation, just sets up a hard situation).
You run: `python -m scripts.trigger_hard_case --scenario spoilage`, then either wait for the worker or run `python -m scripts.run_agent_once --offer <id>`.
You see: if the agent decides it's genuinely stuck, a decision card appears in `/admin/decisions` with its reasoning and 2-4 options; pick one, and within ~10 seconds (the worker's resume check) it resumes and finishes.
**Verified live, in full, against Groq** — this is the most important verification in the whole project: `run_case()` paused correctly on a real `ask_admin` call (`stop_reason == "interrupt"`, a real Strands-generated `interrupt_id`, the exact card saved as a `Decision`); the admin's answer was recorded deterministically; then `resume_case()` — using a **completely fresh `Agent` object**, no shared Python state — correctly resumed the *exact same paused conversation* and produced a final `CaseUpdate`.
**A real bug found and fixed along the way**: resuming with Strands' raw `interruptResponse` list *and* `structured_output_model` in the same call sometimes confused Groq's gpt-oss-120b into calling a nonexistent tool named `"json"` (an internal schema key, not a real tool). Fixed by splitting the resume into two ordinary turns: resume plainly first, then ask for the structured `CaseUpdate` once the conversation is back to a normal shape. Also learned firsthand that once Strands processes an interrupt response — even if a *later* step in that same call then fails for an unrelated reason — the interrupt is considered consumed and can't be re-answered; a failed resume stays visible as `status=failed` for a human to notice, by design, rather than silently retrying against a stale interrupt.
**Deferred** (noted honestly rather than silently dropped): the Supervised-mode approval gate (`hooks/approval_gate_hook.py`, an admin-toggleable "hold every assignment for approval" switch, separate from the agent's own escalation judgment) and an admin dashboard button for triggering hard cases (the script covers the same need). Both are small, additive, and can be picked up later without touching what's already built.

### Phase D — Dashboard, memory, polish

**Step 12 — Admin dashboard** ✅ done (map deferred — see below)
Creates: `services/dashboard.py` (stat aggregation, users list, per-user recent activity — reusing the existing profile schemas for the detail view rather than duplicating field lists), `/api/admin/stats`, `/api/admin/users`, `/api/admin/users/{id}`; frontend `StatCard.jsx`, stat-cards row on `AdminHome`, `AllUsers.jsx`, `UserDetail.jsx`. The activity timeline (Step 7) and Decisions inbox (Step 11) were already built earlier — this step is what completes the dashboard, not what starts it.
You see: live stat cards (active offers, pending decisions, completed today, kg/meals saved today and all-time) updating while the demo runs; a users list with role and status (on duty / accepting donations); clicking through to a detail page showing that user's own profile fields plus their 5 most recent offers/deliveries/trips.
**Deferred, noted honestly**: the map of restaurants/pantries/drivers. The plan explicitly marked it optional ("if not too complex"), and Leaflet + tile layer + coordinate plotting is a meaningful chunk of work for a purely visual feature — I judged finishing memory, tracing and docs at real depth (Steps 13-15) a better use of the remaining budget than a map. It can be added later without touching anything already built (every pantry/driver/restaurant already has lat/lon).

**Step 13 — Long-term memory + tracing** ✅ done (admin "remember this" shortcut on the decision form deferred)
`recall_facts`/`remember_fact` were already built in Steps 6/8. This step adds: `services/memory.py` (evaluated Strands' native `MemoryManager`/`MemoryStore` and chose to keep our own simple table — it already integrates directly with this admin page and the rest of the database with no extra moving parts; documented as worth revisiting for a real AgentCore deployment, where AgentCore Memory would sit behind the same tool interface), `/api/admin/memory` (list/delete — a soft delete via the existing `is_active` column, so there's a history of what was once remembered), the **"What the agent remembers"** page; `agents/telemetry.py` (`configure_tracing()`, wired into every script and the worker).
You see: a table of every fact the agents can currently recall, with a "Forget" button per row. Trace spans print in the terminal when `OTEL_CONSOLE=true` — **verified live**: a real agent call produced a proper OpenTelemetry span with `gen_ai.system.message`/`gen_ai.user.message`/`gen_ai.choice` events and token-usage attributes, matching Strands' documented format exactly.
**Deferred, noted honestly**: an inline "remember this" shortcut on the Decisions inbox answer form. The underlying capability already exists — an admin's note is read by the Coordinator when it resumes, and the agent can call `remember_fact` itself off the back of it — so this would only be a UI convenience, not new capability.

### Phase E — Proof and presentation

**Step 14 — Tests**
Tool tests (distance, capacity, fairness), auth tests, and an **escalation flow test** with a scripted fake model (interrupt → decision row → resume → delivery assigned).
You run: `pytest` → all green, no API cost.

**Step 15 — Docs + deployment path**
`README.md` (problem, users, screenshots, quickstart, **"Strands features we used and where"** with file links), `docs/architecture.md` + Mermaid diagram, `docs/aws-deployment.md` + `deploy/agentcore_app.py` stub, `docs/demo-script.md` (5-minute shot list with one escalation).
You see: a fresh-clone quickstart that runs the whole demo from scratch.

---

## 12. Known risks I'll watch

- **Interrupt restore after restart**: verified live in Step 11 — a completely fresh `Agent` object (no shared Python state) correctly resumed a paused conversation using only the persisted session file.
- **Parallel tool calls**: the Coordinator could fire two action tools at once. I'll set it to run tools one at a time (sequential tool executor, name confirmed in Step 8).
- **Cheap model quality**: Haiku may occasionally reason poorly on hard cases. The `COORDINATOR_MODEL_ID` setting lets you use a stronger model for the manager only.
- **SQLite with two processes** (web + worker): turn on WAL mode (a SQLite setting that lets reads and writes overlap safely).
- **Windows**: commands in the README are given for PowerShell. Activating a venv may need `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **Windows console + Unicode** (found in Step 6): the default terminal encoding can't print some characters the model generates, crashing any script that streams agent output live. Fixed via `agents/console.py`'s `ensure_utf8_console()` — call it at the top of every new script/worker entrypoint that runs an agent.

---

## 13. Open questions for you

1. **AI provider**: which do you have access to: an Anthropic API key, AWS Bedrock, or OpenAI? (Default plan: Anthropic with Claude Haiku 4.5.)
2. **Multi-agent pattern**: OK with **Agents-as-Tools** (Coordinator + 3 specialists), or would you prefer a Graph?
3. **Worker process**: OK to run the agent worker as a **second terminal** (clearer, and matches how AWS would run it)? The alternative is running it inside the web server (one command, but muddier).
4. ~~Live updates: HTMX?~~ **Decided:** React frontend (plain JavaScript) with polling via a `usePolling` hook.
5. **Pantry acceptance timing**: dispatch the driver **at the same time** as asking the pantry (faster for perishable food; if the pantry declines, the agent re-plans)? Or wait for the pantry to accept first?
6. **Supervised mode**: happy to have the admin-toggleable approval gate in addition to the agent's own escalations?
7. **Demo city**: which city should the fake world be set in (e.g. Seattle, Bengaluru, London)?
8. **Map**: Leaflet + OpenStreetMap needs internet during the demo. OK, or would you rather have a simple offline diagram?
9. **Git**: shall I make a git commit at the end of each step (LICENSE in the first commit)?
