# Demo script (~5 minutes)

Goal: show a genuinely autonomous agent team doing real coordination work, and then show it stopping to
ask a human at a real judgment call — not a scripted "click here to see the AI" button.

## Before you start recording

```powershell
python -m scripts.seed_demo --reset      # fresh Seattle world, all passwords: demo1234
uvicorn pantrypilot.web.main:app --reload   # terminal 1
cd frontend; npm run dev                     # terminal 2
python -m pantrypilot.worker                 # terminal 3 — the agents wake up on their own from here
```

Open two browser windows side by side: one logged in as a **restaurant**
(`bella@pantrypilot.test` / `demo1234`), one as the **admin** (`admin@pantrypilot.test` / `demo1234`).

## Shot list

**0:00 – The problem (10s, talking over the empty restaurant dashboard)**
"Restaurants throw away good surplus food every day because matching it to a pantry and a driver is a
phone-and-spreadsheet job. PantryPilot's agents do that coordination themselves."

**0:10 – Post a normal offer (30s)**
As the restaurant, post a straightforward surplus offer (e.g. "40 sandwich platters, pickup by 6pm").
Point out: no dropdown picked a pantry, no button said "run the agent" — the worker's
`pick_up_new_offers` job (every 15s) will pick this up on its own.

**0:40 – Show the agents working (60s)**
Switch to the admin view → **Agent activity**. Refresh (or let it poll) and narrate the log as it fills
in: Intake reading the offer, Matching checking nearby pantries' capacity and fairness, Dispatch finding a
driver, the Coordinator deciding to commit. Emphasize: *this is the model's own reasoning*, logged via a
Strands hook, not a canned status string.

**1:40 – See the outcome (20s)**
Show the offer's status moving to matched/dispatched, and the pantry/driver's own screens reflecting the
same offer showing up as a request.

**2:00 – Trigger a real judgment call (20s)**
In a terminal: `python -m scripts.trigger_hard_case --scenario spoilage` (also try `no_drivers`,
`fairness`, or `unclear_allergens` if time allows). Explain: this sets up a genuinely hard situation — a
tight spoilage window, no available driver, a fairness conflict, or an ambiguous allergen note — it does
not force the escalation in code. Whether the agent actually asks a human is its own call.

**2:20 – The pause, live (60s)**
Wait for the worker's next tick (up to 15s), then switch to admin → **Decisions inbox**. A new card
appears: the Coordinator's own title, situation, reasoning, and options — written by the model, shown
verbatim, not reshaped by our code. Narrate: the agent's conversation is *actually paused* right now (a
real Strands interrupt, `tool_context.interrupt(...)`), sitting on disk in its session file, not just a
flag we set.

**3:20 – Answer it (30s)**
As the admin, pick one of the agent's own suggested options (or add a note) and submit.

**3:50 – The resume (40s)**
Point out the worker's `resume_answered_decisions` job (every 10s) picks this up next — a brand-new Python
`Agent` object gets built, reloads the exact paused conversation from `agents/sessions.py`'s session file,
and continues as if nothing happened. Refresh Agent activity to show it finishing the case after the
human's answer.

**4:30 – Wrap (30s)**
"Three specialist agents, a manager agent deciding how to use them, real memory across restarts, and a
real pause-and-resume when it hits something only a person should decide. That's the whole system —
[`docs/architecture.md`](architecture.md) has the full diagram, and the README lists exactly which Strands
feature backs each piece."

## If something goes wrong live

- **No decision appeared**: the model sometimes finds a safe way through a hard case on its own — that's a
  legitimate outcome, not a bug. Check Agent activity for its reasoning, or try a different `--scenario`.
- **Groq rate limit**: switch `.env`'s `MODEL_PROVIDER`/keys to a backup account, restart the worker.
- **Nothing is moving**: confirm all three processes (web, frontend, worker) are running — the worker is
  what makes the agents wake up; without it, offers just sit at `status=posted`.
