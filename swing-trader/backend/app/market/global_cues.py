"""Fetch global market cues that predict NIFTY's direction.

These are reference signals for the pre-open / overnight read — NOT execution
data — so the data only needs to be roughly fresh (the route caches for 15 min).

Sources:
- yfinance (Yahoo Finance, free/unofficial) for US/Asian indices, macro, ADRs.
- A best-effort web scrape for GIFT Nifty (no clean free API). If it fails the
  rest of the payload still renders.

Every group is wrapped so one failure degrades gracefully instead of killing
the whole response.
"""
import logging
import re

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

# (yfinance ticker, friendly name) grouped by bucket.
US_TICKERS = [("^DJI", "Dow Jones"), ("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq")]
ASIA_TICKERS = [("^N225", "Nikkei 225"), ("^HSI", "Hang Seng")]
MACRO_TICKERS = [("^INDIAVIX", "India VIX"), ("BZ=F", "Brent Crude"), ("INR=X", "USD/INR")]
ADR_TICKERS = [
    ("INFY", "Infosys"),
    ("IBN", "ICICI Bank"),
    ("HDB", "HDFC ADR"),
    ("WIT", "Wipro"),
    ("RDY", "Dr Reddy's"),
]

GIFT_NIFTY_URL = "https://www.moneycontrol.com/indian-indices/gift-nifty-50-9.html"


def _direction(change_pct: float) -> str:
    if change_pct > 0.05:
        return "up"
    if change_pct < -0.05:
        return "down"
    return "flat"


def _fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Return {symbol: {"last", "prev_close"}} via yfinance.

    Uses the last two daily closes so we can compute an overnight/day change.
    Per-symbol failures are skipped rather than raising.
    """
    out: dict[str, dict] = {}
    tickers = yf.Tickers(" ".join(symbols))
    for sym in symbols:
        try:
            hist = tickers.tickers[sym].history(period="2d", interval="1d")
            closes = [float(c) for c in hist["Close"].dropna().tolist()]
            if not closes:
                continue
            last = closes[-1]
            prev = closes[-2] if len(closes) >= 2 else closes[-1]
            out[sym] = {"last": last, "prev_close": prev}
        except Exception as e:  # noqa: BLE001 — one bad ticker shouldn't sink the group
            logger.warning(f"Quote fetch failed for {sym}: {e}")
    return out


def _format_group(group: list[tuple[str, str]]) -> list[dict]:
    """Fetch + format one bucket; returns [] if the whole group errors out."""
    try:
        quotes = _fetch_quotes([sym for sym, _ in group])
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Group quote fetch failed: {e}")
        return []

    rows = []
    for sym, name in group:
        q = quotes.get(sym)
        if not q:
            continue
        prev = q["prev_close"]
        change_pct = round((q["last"] - prev) / prev * 100, 2) if prev else 0.0
        rows.append({
            "name": name,
            "symbol": sym,
            "last": round(q["last"], 2),
            "change_pct": change_pct,
            "direction": _direction(change_pct),
        })
    return rows


def _fetch_gift_nifty() -> dict | None:
    """Best-effort GIFT Nifty quote. Fragile by nature — returns None on any
    failure so the rest of the payload is unaffected."""
    try:
        resp = requests.get(
            GIFT_NIFTY_URL,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; swing-trader)"},
            timeout=8,
        )
        resp.raise_for_status()
        html = resp.text

        # moneycontrol embeds: <span id="sp_val">23,544.55</span> and a
        # change block <div id="sp_ch_prch" ...> -3.20 (-0.01%) </div>.
        pct_match = re.search(
            r'id="sp_ch_prch".*?\(?\s*(-?\d+(?:\.\d+)?)\s*%', html, re.DOTALL
        )
        if not pct_match:
            return None
        change_pct = round(float(pct_match.group(1)), 2)

        last = None
        price_match = re.search(r'id="sp_val"[^>]*>\s*([\d,]+\.\d+)', html)
        if price_match:
            last = round(float(price_match.group(1).replace(",", "")), 2)

        return {
            "name": "GIFT Nifty",
            "last": last,
            "change_pct": change_pct,
            "direction": _direction(change_pct),
        }
    except Exception as e:  # noqa: BLE001
        logger.warning(f"GIFT Nifty fetch failed (degrading gracefully): {e}")
        return None


def fetch_global_cues() -> dict:
    """Assemble the global-cue payload. Each piece degrades independently."""
    return {
        "gift_nifty": _fetch_gift_nifty(),
        "us": _format_group(US_TICKERS),
        "asia": _format_group(ASIA_TICKERS),
        "macro": _format_group(MACRO_TICKERS),
        "adrs": _format_group(ADR_TICKERS),
    }
