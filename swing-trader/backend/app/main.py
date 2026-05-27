import logging
import socket
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Zerodha's IP whitelist only accepts IPv4. On dual-stack machines, Python's
# requests library prefers IPv6, which hits an unregistered source address.
# This patch ensures all outbound connections use IPv4.
_orig_getaddrinfo = socket.getaddrinfo

def _getaddrinfo_prefer_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    results = _orig_getaddrinfo(host, port, family, type, proto, flags)
    ipv4 = [r for r in results if r[0] == socket.AF_INET]
    return ipv4 if ipv4 else results

socket.getaddrinfo = _getaddrinfo_prefer_ipv4
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.session import engine, run_migrations
from app.db.models import Base
from app.jobs.scheduler import create_scheduler
from app.routes import auth, config, universe, scan, trades, stats, system, telegram, news, market

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables
    Base.metadata.create_all(bind=engine)
    run_migrations()
    logger.info("Database tables created/verified")

    # Start scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("APScheduler started")

    yield

    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")


app = FastAPI(title="Swing Trader API", version="1.0.0", lifespan=lifespan)

_cors_origins = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]
if settings.frontend_base_url and settings.frontend_base_url not in _cors_origins:
    _cors_origins.append(settings.frontend_base_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(config.router)
app.include_router(universe.router)
app.include_router(scan.router)
app.include_router(trades.router)
app.include_router(stats.router)
app.include_router(system.router)
app.include_router(telegram.router)
app.include_router(news.router)
app.include_router(market.router)


@app.get("/")
def root():
    return {"status": "swing-trader-api", "version": "1.0.0"}
