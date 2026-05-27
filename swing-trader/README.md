# Swing Trader

Self-hosted single-user swing trading dashboard for Indian equities (Nifty 50 + NIFTYCASE + MID150CASE).

## Quick start

### Backend
```bash
cd backend
cp .env.example .env        # fill in your keys
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev                 # runs on :5174
```

## Production deployment (Fly.io + Supabase + Render)

### Architecture
- **Backend:** Fly.io (Mumbai region, dedicated IPv4, ~$4/mo)
- **Database:** Supabase PostgreSQL (free tier)
- **Frontend:** Render Static Site (free tier)

### Step 1 — Supabase database

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **Project Settings → Database → Connection string → URI**
3. Copy the **direct connection** string (port 5432, NOT the pooler on port 6543)
4. It looks like: `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`

### Step 2 — Fly.io backend

```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
cd backend

# Launch (first time only — fly.toml is already committed)
fly launch --no-deploy --name swing-trader-api

# Add a dedicated IPv4 (required for Zerodha static IP registration)
fly ips allocate-v4 --shared=false

# Find your IP
fly ips list
# → Register this IP in Zerodha: Profile → API → Static IP

# Set all secrets
fly secrets set \
  KITE_API_KEY=your_key \
  KITE_API_SECRET=your_secret \
  KITE_REDIRECT_URL=https://swing-trader-api.fly.dev/api/auth/kite/callback \
  OPENAI_API_KEY=sk-... \
  DATABASE_URL="postgresql://postgres:password@db.xxx.supabase.co:5432/postgres" \
  APP_BASE_URL=https://swing-trader-api.fly.dev \
  FRONTEND_BASE_URL=https://your-site.onrender.com

# Deploy
fly deploy
```

Also update the **Redirect URL** in your Kite app at developers.kite.trade to:
`https://swing-trader-api.fly.dev/api/auth/kite/callback`

> **Important:** `auto_stop_machines = false` is set in `fly.toml` so the VM stays alive for APScheduler. Do not change this — a sleeping machine misses scheduled jobs.

### Step 3 — Render frontend

1. Connect your repo to [render.com](https://render.com)
2. Render detects `render.yaml` automatically — it will create the static site
3. Set the `VITE_API_URL` env var to your Fly.io app URL: `https://swing-trader-api.fly.dev`
4. Deploy

### Step 4 — SEBI static IP registration

Since April 1, 2026, Zerodha rejects API orders from unregistered IPs.

```bash
fly ips list   # find your dedicated IPv4
```

Register that IP in Zerodha → **Profile → API → Static IP**. This is a one-time step per deployment. GTTs already at Zerodha are unaffected by IP changes; only new order placement requires the registered IP.

### Cost summary

| Service | Plan | Cost |
|---------|------|------|
| Fly.io (backend) | shared-cpu-1x 256MB | ~$2/mo |
| Fly.io dedicated IPv4 | | $2/mo |
| Supabase | Free tier (500MB) | Free |
| Render (frontend) | Static site | Free |
| **Total** | | **~$4/mo** |

## Environment variables

See `.env.example`. Required before trading:
- `KITE_API_KEY` + `KITE_API_SECRET` — from https://developers.kite.trade/
- `OPENAI_API_KEY` — for news classification
- `TOTAL_CAPITAL_INR` — or set via Settings UI
- `KITE_REDIRECT_URL` — must match the redirect URL registered in your Kite app **and** be reachable from Zerodha's servers
- `APP_BASE_URL` — used in Telegram login reminders; set to your server's public URL

## Milestone status

| # | Milestone | Status |
|---|-----------|--------|
| M-1 | Skeleton + DB + Config | ✅ Done |
| M-2 | Kite auth | ✅ Done |
| M-3 | Universe (NSE CSV) | ✅ Done |
| M-4 | Daily scanner | ✅ Done |
| M-5 | Candidates UI | ✅ Done |
| M-6 | News + LLM classifier | ✅ Done |
| M-7 | Order placement + OCO GTT | ✅ Done |
| M-8 | Position cycle (trailing) | ✅ Done |
| M-9 | Exit reconciliation | ✅ Done |
| M-10 | Time-stop | ✅ Done |
| M-11 | Telegram login reminder | ✅ Done |
| M-12 | Journal & stats | ✅ Done |
| M-13 | 09:00 re-validation | ✅ Done |
| M-14 | Polish + deploy | ✅ Done |

## Architecture

```
backend/app/
  main.py           — FastAPI app, lifespan (DB create + APScheduler start)
  config.py         — pydantic-settings from .env
  db/models.py      — all ORM models (Config, Trade, DailyScan, …)
  kite/             — auth, rate-limited client, orders, GTT helpers
  nse/              — NSE HTTP helper, universe CSV, sector map, block deals
  scanner/          — signals (RSI, MAs, pivots), scorer, runner
  trading/          — entry, position cycle, time-stop, reconcile
  news/             — Google News RSS fetcher, OpenAI classifier
  telegram_bot/     — single function: send_login_link()
  jobs/scheduler.py — APScheduler cron table (IST timezone)
  routes/           — FastAPI routers per domain
```

## Scheduler (all times IST)

| Job | Time |
|-----|------|
| Universe refresh | 1st of month 01:00 |
| Kite instruments | Daily 08:30 |
| Login reminder | Weekdays 06:30 |
| Morning sync | 09:00 (trading days) |
| Position cycle | Every 15 min 09:15–15:30 |
| Time-stop | 15:00 |
| Daily scanner | 15:45 |
| Block/bulk deals | 17:30 (+ retries) |
| News + LLM | 18:00 |
