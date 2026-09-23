# Deploying PantryPilot

Frontend on **Vercel**, API on **Render**, database on **Neon**. All three have
free tiers that fit this project.

> This is the practical, do-it-today path. `docs/aws-deployment.md` describes the
> AWS-native mapping (EventBridge → Lambda → AgentCore Runtime) that the hackathon
> brief asked for; both trigger the exact same `runner.run_case`.

## The one thing to understand first

PantryPilot has three parts, and **one of them cannot run on Vercel**:

| Part | Where | Why |
|---|---|---|
| React frontend | Vercel | Static files. Vercel is ideal. |
| FastAPI API | Render | Needs a real server process. |
| **Agent worker** | see below | It's an infinite loop. Vercel is serverless — it has nowhere to put one. |

The worker is what makes this agentic: it wakes the agents up on a timer with
nobody clicking anything. You have two ways to keep that true.

**Option A — free.** An external scheduler calls `POST /api/tick` on a timer.
That endpoint runs exactly one pass of the same three jobs. It also keeps
Render's free service from sleeping.

**Option B — $7/month.** Uncomment the `worker` block in `render.yaml` and run
the real scheduler as its own always-on process.

Same code either way — `pantrypilot/worker/jobs.py`. Only the trigger differs.
Start with A.

---

## 1. Database — Neon (5 minutes)

Render's free Postgres is deleted after 30 days. [Neon](https://neon.tech)'s free
tier isn't, which matters if you want the demo alive after judging.

1. Create a project. **Put it in the same region you will deploy Render to.**
2. Copy the connection string. It looks like
   `postgresql://user:pass@ep-xxx.aws.neon.tech/neondb?sslmode=require`.

> **Region is the single biggest performance decision here, and it cannot be
> changed after the project is created.**
>
> The admin Overview issues ~23 queries, so every millisecond of round trip is
> multiplied by 23. Measured from one laptop in India:
>
> | Neon region | Per query | Overview page |
> |---|---|---|
> | `ap-southeast-2` (Sydney) | ~407 ms | ~19.5 s |
> | `ap-southeast-1` (Singapore) | ~83 ms | ~2.3 s |
>
> Deployed, the client is Render rather than a laptop, so putting both in the
> same region takes this into single-digit milliseconds. Pick a region Render
> and Neon share — Singapore, Oregon, Ohio and Frankfurt all work.
>
> Getting this wrong looks like "the app is slow", not "the database is far
> away", and no amount of query tuning recovers it.

Keep it somewhere safe — it's a password.

You don't need to create tables. The app calls `create_tables()` on startup, and
`postgres://` / `postgresql://` URLs are rewritten to the psycopg 3 driver
automatically (`pantrypilot/database.py:normalise_database_url`).

## 2. API — Render

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → pick the repo. It reads `render.yaml`.
   **Set the region to match your Neon project** — see the table above.
3. Fill in the variables it asks for:

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Neon string from step 1 |
| `GROQ_API_KEY` | your primary key |
| `GROQ_FALLBACK_API_KEYS` | the rest, comma-separated |
| `CITY_TIMEZONE` | **your own timezone**, e.g. `Asia/Kolkata` |
| `CITY_NAME` | e.g. `Seattle, WA` |
| `FRONTEND_ORIGINS` | leave blank for now — you get it in step 3 |

`SESSION_SECRET` and `TICK_SECRET` are generated for you. Copy `TICK_SECRET`
out of the dashboard; step 4 needs it.

> **`CITY_TIMEZONE` is not cosmetic.** Driver shifts and pantry opening hours are
> stored in the demo city's *local* time. Leave it on US Pacific and demo from
> India, and it's 4am there — no driver is on shift, every pantry is shut, and
> the agents will correctly but uselessly report that nobody is available.

Wait for the deploy, then check `https://<your-api>.onrender.com/api/health`.

## 3. Frontend — Vercel

1. Vercel → **Add New → Project** → same repo.
2. Set **Root Directory** to `frontend`. Vercel reads `frontend/vercel.json`.
3. Add one environment variable:

   ```
   VITE_API_BASE_URL = https://<your-api>.onrender.com
   ```

   This is baked in at **build** time, so changing it later needs a redeploy, not
   just a restart.

4. Deploy, and copy the resulting URL.

## 4. Close the loop

**Tell the API where the frontend lives.** Back in Render, set:

```
FRONTEND_ORIGINS = https://<your-app>.vercel.app
```

Exact origin, no trailing slash, no wildcard — the login cookie is a credentialed
request, and browsers reject `*` for those. Redeploy.

**Seed the demo world.** In Render → your service → **Shell**:

```bash
python -m scripts.seed_demo --reset
```

**Start the agents.** At [cron-job.org](https://cron-job.org) (free), create a job:

- URL: `https://<your-api>.onrender.com/api/tick`
- Method: **POST**
- Header: `X-Tick-Secret: <the TICK_SECRET from step 2>`
- Every **1 minute**

That both drives the agents and keeps the free service awake. A minute is the
shortest most free cron services allow, so offers are picked up within a minute
rather than the 15 seconds you get locally.

Check it worked: the response should be
`{"ran": {"expire_stale_dispatch_requests": "ok", ...}}`.

## Verify end to end

1. Open the Vercel URL, log in as `goldencrust@pantrypilot.test` / `demo1234`.
2. Post an offer.
3. Within a minute the progress tracker moves past **Understood**.
4. As admin, switch view to whichever driver has the badge, and accept.

If step 1 fails with everything looking logged out, it's almost always
`FRONTEND_ORIGINS` not exactly matching the Vercel URL.

## Known limits of the free tier

Worth knowing before you demo, and worth saying out loud if asked:

- **First request after a quiet spell is slow.** Render's free service sleeps;
  the cron ping mostly prevents this, but a cold start takes ~30 seconds.
- **Agent runs take minutes, not seconds.** Groq's free tier caps tokens per
  minute per key. Key failover (`GROQ_FALLBACK_API_KEYS`) multiplies the budget —
  six keys gave a measured 48,000 tokens/minute and zero full backoffs.
- **Agent memory is lost on redeploy.** Conversations are files under
  `data/sessions/`, and Render's disk is ephemeral. Interrupt-and-resume still
  works normally; it just won't survive a deploy. Moving that to Postgres or S3
  is the fix, and `agents/sessions.py` is the only file that would change.
- **750 free hours/month** is one always-on service and no more.

## Switching to Bedrock

If Groq's limits get in the way — or judges prefer AWS — the Bedrock provider is
already implemented. In Render, set `MODEL_PROVIDER=bedrock`, `AWS_REGION`, and
the usual AWS credentials. No code changes; see
`pantrypilot/agents/model_provider.py`.
