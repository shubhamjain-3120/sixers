# Swing Trader

Self-hosted single-user swing trading dashboard for Indian equities (Nifty 50 + NIFTYBEES + MID150BEES).

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

## SEBI static IP requirement (mandatory before live trading)

Since April 1, 2026, Zerodha rejects API orders from unregistered IPs. You must register the **outbound public IP of the machine running the backend** in your Zerodha profile before any order placement will work.

### Step-by-step

1. Find the public IP of your backend server:
   ```bash
   curl -s https://api.ipify.org
   ```
2. Log in to Zerodha → **Profile → API** (or equivalent static-IP registration page) and add that IP.
3. Verify registration took effect — Zerodha typically activates within minutes.

### Deployment options

| Option | Static IP? | Cost | Notes |
|--------|-----------|------|-------|
| Home server (fiber/cable ISP) | Usually **No** | Free | IP changes on router reboot — orders will break silently |
| Home server + static IP ISP add-on | Yes | ~₹200–500/mo | Ask your ISP; easiest if you self-host |
| VPS (Railway, Render, Hetzner, DigitalOcean) | **Yes** — fixed per instance | $5–12/mo | Recommended; also solves uptime (keeps scheduler running) |
| Home server + Tailscale exit node | Effectively yes | Free | Advanced; exit node must have static IP |

**Recommendation:** Deploy the backend to a cheap VPS (Hetzner or DigitalOcean $6/mo droplet). Register that VPS's IP with Zerodha. Run the frontend from the same VPS or your local machine — only the backend needs the registered IP since it's the one placing orders.

### Deploying to a VPS

```bash
# On the VPS (Ubuntu 22.04+)
git clone <your-repo> swing-trader
cd swing-trader/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in keys
# Run behind a process manager
pip install gunicorn
gunicorn app.main:app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

Use `systemd` or `supervisor` to keep it alive. Set `KITE_REDIRECT_URL` and `APP_BASE_URL` to your VPS's domain/IP:
```bash
KITE_REDIRECT_URL=https://your-vps-ip-or-domain/api/auth/kite/callback
APP_BASE_URL=https://your-vps-ip-or-domain
```

> **Important:** If you redeploy to a different server or your IP changes for any reason, re-register the new IP with Zerodha immediately — existing GTTs at Zerodha will still protect open positions, but no new orders can be placed until the IP is updated.

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
| M-2 | Kite auth | ⬜ |
| M-3 | Universe (NSE CSV) | ⬜ |
| M-4 | Daily scanner | ⬜ |
| M-5 | Candidates UI | ⬜ |
| M-6 | News + LLM classifier | ⬜ |
| M-7 | Order placement + OCO GTT | ⬜ |
| M-8 | Position cycle (trailing) | ⬜ |
| M-9 | Exit reconciliation | ⬜ |
| M-10 | Time-stop | ⬜ |
| M-11 | Telegram login reminder | ⬜ |
| M-12 | Journal & stats | ⬜ |
| M-13 | 09:00 re-validation | ⬜ |
| M-14 | Polish + deploy | ⬜ |

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
