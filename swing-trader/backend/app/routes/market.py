import json
import logging
import time as _time
from datetime import datetime, timezone, timedelta
from typing import Optional

import feedparser
from fastapi import APIRouter, Query
from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/market", tags=["market"])

CACHE_TTL = timedelta(minutes=15)

_cache: Optional[dict] = None
_cache_ts: Optional[datetime] = None

SYSTEM_PROMPT = """You are a financial analyst covering Indian equity markets.
You will be given today's top news headlines about NIFTY/Sensex and the broader Indian stock market.
Write a concise 3-4 sentence summary of how the market performed, the key drivers (macro, geopolitical, sector-specific), and the overall tone.
Also return the overall market direction based on the headlines.
Output ONLY valid JSON matching this schema:
{
  "summary": "<3-4 sentence market narrative>",
  "direction": "up" | "down" | "flat"
}
Rules:
- "up": headlines mostly positive, indices gained
- "down": headlines mostly negative, indices fell
- "flat": mixed signals or marginal movement
- Keep the summary factual and grounded in the headlines — do not speculate beyond what is reported.
- Write in past tense as if markets have closed for the day."""


def _parse_published(entry) -> datetime:
    try:
        t = _time.mktime(entry.published_parsed)
        return datetime.fromtimestamp(t, tz=timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


def _fetch_nifty_headlines() -> list[dict]:
    """Fetch top NIFTY/Sensex headlines from Google News RSS."""
    url = "https://news.google.com/rss/search?q=Nifty+Sensex+market+India&hl=en-IN&gl=IN&ceid=IN:en"
    cutoff = datetime.utcnow() - timedelta(days=2)
    results = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:15]:
            pub = _parse_published(entry)
            if pub < cutoff:
                continue
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if title:
                results.append({
                    "title": title,
                    "published_at": pub.isoformat(),
                    "url": link,
                })
    except Exception as e:
        logger.error(f"NIFTY news fetch failed: {e}")

    # Sort newest first, cap at 10
    results.sort(key=lambda x: x["published_at"], reverse=True)
    return results[:10]


def _summarise_with_openai(headlines: list[dict]) -> dict:
    """Call OpenAI to produce a market narrative + direction from headlines."""
    if not headlines:
        return {"summary": "No recent headlines found for NIFTY/Sensex.", "direction": "flat"}

    lines = ["Top headlines (most recent first):"]
    for i, h in enumerate(headlines, 1):
        pub = h["published_at"][:10]  # YYYY-MM-DD
        lines.append(f"{i}. [{pub}] {h['title']}")
    user_msg = "\n".join(lines)

    client = OpenAI(api_key=settings.openai_api_key)
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                temperature=0.2 if attempt == 0 else 0.0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            )
            data = json.loads(resp.choices[0].message.content)
            return {
                "summary": data.get("summary", ""),
                "direction": data.get("direction", "flat"),
            }
        except json.JSONDecodeError as e:
            logger.error(f"Malformed JSON from OpenAI (attempt {attempt + 1}): {e}")
        except Exception as e:
            logger.error(f"OpenAI call failed (attempt {attempt + 1}): {e}")
            if attempt == 0:
                import time; time.sleep(2)

    return {"summary": "Unable to generate summary at this time.", "direction": "flat"}


@router.get("/nifty-summary")
def get_nifty_summary(force: bool = Query(default=False)):
    """
    Fetch top NIFTY/Sensex news and return an AI-generated market summary.
    Results are cached for 15 minutes. Pass ?force=true to bypass the cache.
    """
    global _cache, _cache_ts

    now = datetime.utcnow()
    if (
        not force
        and _cache is not None
        and _cache_ts is not None
        and (now - _cache_ts) < CACHE_TTL
    ):
        return {**_cache, "cached": True}

    headlines = _fetch_nifty_headlines()
    llm_result = _summarise_with_openai(headlines)

    result = {
        "summary": llm_result["summary"],
        "direction": llm_result["direction"],
        "headlines": headlines,
        "fetched_at": now.isoformat() + "Z",
        "cached": False,
    }

    _cache = {k: v for k, v in result.items() if k != "cached"}
    _cache_ts = now

    return result
