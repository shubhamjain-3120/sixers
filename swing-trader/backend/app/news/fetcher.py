import feedparser
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple
from sqlalchemy.orm import Session
from app.db.models import NewsItem

logger = logging.getLogger(__name__)
FIVE_DAYS_AGO = timedelta(days=5)


def _parse_published(entry) -> datetime:
    try:
        import time as _time
        t = _time.mktime(entry.published_parsed)
        return datetime.fromtimestamp(t, tz=timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


def fetch_headlines(symbol: str, company_name: str, db: Session) -> List[Tuple[str, datetime, str]]:
    """Returns list of (headline, published_at, url) from Google News RSS, newest first."""
    cutoff = datetime.utcnow() - FIVE_DAYS_AGO
    query = f"{symbol} {company_name} stock NSE"
    url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"

    results = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            pub = _parse_published(entry)
            if pub < cutoff:
                continue
            headline = entry.get("title", "").strip()
            link = entry.get("link", "")
            if headline:
                results.append((headline, pub, link))
                # Persist to news_items
                existing = (
                    db.query(NewsItem)
                    .filter(NewsItem.symbol == symbol, NewsItem.headline == headline)
                    .first()
                )
                if not existing:
                    db.add(NewsItem(
                        symbol=symbol, headline=headline, url=link,
                        source="google_news", published_at=pub,
                    ))
    except Exception as e:
        logger.error(f"News fetch failed for {symbol}: {e}")

    try:
        db.commit()
    except Exception:
        db.rollback()

    return sorted(results, key=lambda x: x[1], reverse=True)[:5]
