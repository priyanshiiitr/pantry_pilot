# `pantrypilot/` — the Python backend

Everything that runs on the server side lives here.

| Folder / file | What lives there | Added in |
|---|---|---|
| `config.py` | Reads settings from `.env` (database, AI provider, secrets) | Step 1 |
| `web/` | FastAPI app: the JSON API the React frontend calls | Step 1 |
| `models/` | Database tables (SQLAlchemy classes) | Step 2 |
| `services/` | Plain business logic (distance, fairness numbers, saving offers). No AI. | Step 2+ |
| `auth/` | Password hashing and "who is logged in" | Step 3 |
| `agents/` | The AI reasoning layer: Strands agents, tools, hooks, prompts | Step 6+ |
| `worker/` | Background scheduler that wakes the agents up on its own | Step 9 |
| `deploy/` | Stub entrypoint for Amazon Bedrock AgentCore | Step 15 |

**The rule:** the AI decides things only inside `agents/`. Everything else is normal,
predictable (deterministic) code.
