# Demo script (~5 minutes)

For the **deployed** app. The local version is at the bottom.

| | |
|---|---|
| App | https://pantry-pilot-twoe.vercel.app |
| API | https://pantrypilot-api-ou1p.onrender.com |
| Password (every account) | `demo1234` |

Goal: show an agent team doing real coordination on its own, and then stopping
to ask a human at a real judgment call — not a "click here to see the AI" button.

---

## Before you hit record

**1. Wake the API.** Render's free tier sleeps; a cold start is ~30 seconds and
you don't want it on camera. Open the health URL and wait for `{"ok":true,...}`:

    https://pantrypilot-api-ou1p.onrender.com/api/health

**2. Log in as admin** at the app URL: `admin@pantrypilot.test` / `demo1234`.

**3. Have a second browser window ready** — you'll want to jump between the
restaurant and admin views. Or use Switch View, which is the point of it.

**4. Know the timing.** The cron fires every minute, and an agent run takes one
to three minutes on Groq's free tier. Post the offer, then talk over the wait —
the activity feed fills while you speak, which is better television than silence.

---

## Shot list

### 0:00 — The problem (15s)

On the admin Overview.

> "Restaurants throw away good food every day, because matching it to a pantry
> and a driver is a phone-and-spreadsheet job nobody has time for. PantryPilot
> does that coordination itself — and only interrupts a human when there's a
> real decision to make."

### 0:15 — Post an offer (30s)

Sidebar → **Switch view → Restaurant → Golden Crust Bakery**. Then **Post surplus**.

| Field | Value |
|---|---|
| Title | `Leftover chicken biryani` |
| Description | `Three large trays of chicken biryani from a cancelled catering order. Cooked 2 hours ago, still hot. Also 40 raita cups.` |
| Quantity | `3 trays plus 40 raita cups, about 50 servings` |
| Allergens | `dairy` |
| Deadline | 3 hours from now |

> "I'm typing this the way a busy restaurant manager actually would — messy
> free text, no weights, no structured fields. Notice I never chose a pantry or
> a driver. There's no 'run the agent' button either."

### 0:45 — Nothing happens, on purpose (15s)

Stay on the offer page. It says **Posted**, all five stages waiting.

> "Nothing is happening yet, and that's the point. A scheduler wakes the agents
> on their own. Nobody is triggering this."

### 1:00 — Watch it think (75s)

The stage tracker starts moving. **What the agents did** fills in below it.

> "Intake just read that free text and turned it into structured data — it
> worked out the weight, spotted the dairy, decided it needs refrigeration.
> Now Matching is comparing pantries on capacity, fairness, dietary rules and
> opening hours. Then Dispatch looks for a driver who can actually make the
> deadline."

Point at a couple of real lines in the feed as they appear. Then:

> "This is the model's own reasoning, logged as it happens. Not a progress bar."

### 2:15 — The outcome (20s)

Stages go green: **Understood → Pantry matched → Driver assigned**.

> "It picked the pantry, picked the driver, and wrote the reason for both."

### 2:35 — The driver's side, without logging out (25s)

Sidebar → **Switch view → Driver**. The list shows a **red badge** next to
whoever was asked.

> "I'm still signed in as the admin — this is a preview. And notice the badge:
> it's telling me which of eight drivers the agents actually asked."

Click that driver → **Accept** → **Mark picked up** → **Mark delivered**.

### 3:00 — Now the interesting part (20s)

Switch back to **Admin**, then a restaurant, and post a deliberately hard offer:

| Field | Value |
|---|---|
| Title | `Fresh cream pastries` |
| Description | `80 fresh cream-filled pastries, made 3 hours ago. Must be refrigerated immediately or they are unsafe.` |
| Quantity | `80 pastries` |
| Allergens | `dairy, eggs, gluten` |
| Deadline | **20 minutes from now** |

> "Same system, but this one is genuinely hard — a 20-minute window on food
> that spoils. I'm not forcing anything; I'm just giving it a problem that
> might not have a safe answer."

### 3:20 — It stops and asks (60s)

Admin → **Decisions**. A card appears.

> "It stopped. This card is the agent's own writing — the title, the situation,
> the options with their consequences, and which one it would pick. Not a
> template.
>
> And this isn't a status flag we set. The agent's conversation is genuinely
> paused mid-thought, saved to disk. It is waiting."

Read one option aloud. Then answer it.

### 4:20 — It picks up where it left off (30s)

> "Within ten seconds the scheduler notices my answer, rebuilds the agent, and
> loads that exact paused conversation back — then carries on from the moment
> it stopped. It doesn't start over."

Refresh the activity feed to show it continuing.

### 4:50 — Close (20s)

Back to the Overview.

> "Four agents — a coordinator and three specialists. Real memory across
> restarts. And a genuine pause-and-resume when it hits something only a person
> should decide. That last part is the whole idea: not an AI that acts like it
> knows everything, but one that knows when it doesn't."

---

## If it goes wrong on camera

**Nothing is moving.** The cron only fires once a minute. To force it now:

```bash
curl -X POST https://pantrypilot-api-ou1p.onrender.com/api/tick \
  -H "X-Tick-Secret: YOUR_TICK_SECRET"
```

Returns `202` immediately — that means *started*, not finished.

**No decision card appeared.** The agent found a safe route on its own. That's a
legitimate outcome, not a bug — say so, show its reasoning in the activity feed,
and try the `no_drivers` or `fairness` scenario instead. Honesty here reads
better than pretending.

**Everything looks logged out.** `FRONTEND_ORIGINS` on Render no longer matches
the Vercel URL exactly. Nothing else causes this.

**It is very slow.** Groq's free tier caps tokens per minute per key. Failover
across six keys measured 48,000 tokens/minute and zero full backoffs — if it is
still crawling, a key has likely been revoked.

---

## Running it locally instead

Three terminals, from the project folder:

```bash
uvicorn pantrypilot.web.main:app --reload    # 1
cd frontend && npm run dev                   # 2
python -m pantrypilot.worker                 # 3  <- this is what wakes the agents
```

Then http://localhost:5173. Locally the worker polls every **15 seconds** rather
than every minute, so the whole demo runs faster — worth using if you are
recording and want less dead air.

To drive one offer by hand and watch every tool call stream past:

```bash
python -m scripts.run_agent_once --offer <id>
```

To set up a hard case deliberately:

```bash
python -m scripts.trigger_hard_case --scenario spoilage
```

(also `no_drivers`, `fairness`, `unclear_allergens`)
