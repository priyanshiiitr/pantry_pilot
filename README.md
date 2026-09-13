# PantryPilot 🥫

**An AI agent team that routes surplus food from restaurants to food pantries — and only asks a human when there is a real decision to make.**

Built for the AWS "Agents for Humans" hackathon with the [Strands Agents SDK](https://strandsagents.com).

> 🚧 Under construction. See [PLAN.md](PLAN.md) for the full plan and progress.

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
copy .env.example .env
uvicorn pantrypilot.web.main:app --reload

# 2. Frontend — in a second terminal
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. You should see "✓ Backend connected".

Run the tests with `pytest`.

## Project layout

| Folder | What's in it |
|---|---|
| [`pantrypilot/`](pantrypilot/README.md) | Python backend: API, database, agents, worker |
| [`frontend/`](frontend/README.md) | React app |
| `tests/` | pytest tests |
| `docs/` | Architecture, AWS deployment, demo script (coming in later steps) |

## Which Strands features we used and where

*Filled in as each feature is built (Steps 6–13).*

## License

[Apache-2.0](LICENSE)
