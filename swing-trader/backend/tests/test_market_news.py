"""Acceptance tests for the combined Market News feature.

No real network: yfinance, OpenAI, the GIFT Nifty scrape and feedparser are
all mocked (see tests/conftest.py + project rule "no real Zerodha/OpenAI/NSE
calls in tests").
"""
import json
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
import app.market.global_cues as gc
import app.market.summary as summ
import app.routes.market as market

client = TestClient(app)


# ── global_cues.fetch_global_cues ────────────────────────────────────────────

def _fake_quotes(symbols):
    """Two closes per symbol → +1% move for every ticker."""
    return {s: {"last": 101.0, "prev_close": 100.0} for s in symbols}


@patch("app.market.global_cues._fetch_gift_nifty", return_value=None)
@patch("app.market.global_cues._fetch_quotes", side_effect=_fake_quotes)
def test_fetch_global_cues_shape(mock_quotes, mock_gift):
    cues = gc.fetch_global_cues()
    assert {"gift_nifty", "us", "asia", "macro", "adrs"} <= cues.keys()
    assert len(cues["us"]) == 3 and len(cues["asia"]) == 2
    assert len(cues["adrs"]) == 5
    dow = next(r for r in cues["us"] if r["name"] == "Dow Jones")
    assert dow["change_pct"] == 1.0 and dow["direction"] == "up"


@patch("app.market.global_cues._fetch_gift_nifty", return_value=None)
def test_one_group_failure_degrades_gracefully(mock_gift):
    """A group whose quotes raise yields [] but other groups still populate."""
    def selective(symbols):
        if "^N225" in symbols:  # Asia group blows up
            raise RuntimeError("yahoo down")
        return _fake_quotes(symbols)

    with patch("app.market.global_cues._fetch_quotes", side_effect=selective):
        cues = gc.fetch_global_cues()

    assert cues["asia"] == []        # degraded
    assert len(cues["us"]) == 3      # intact


@patch("app.market.global_cues._fetch_quotes", side_effect=_fake_quotes)
def test_gift_nifty_scrape_failure_returns_none(mock_quotes):
    """If the scrape raises, gift_nifty is None and the rest is intact."""
    with patch("app.market.global_cues.requests.get", side_effect=Exception("boom")):
        cues = gc.fetch_global_cues()
    assert cues["gift_nifty"] is None
    assert len(cues["us"]) == 3


# ── summary.summarise ────────────────────────────────────────────────────────

def _mock_openai_summary(summary: str, direction: str):
    resp = MagicMock()
    resp.choices[0].message.content = json.dumps({"summary": summary, "direction": direction})
    return resp


@patch("app.market.summary.OpenAI")
def test_summarise_returns_unified_read(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_summary(
        "Global cues firm, Nifty likely to open higher.", "up"
    )
    out = summ.summarise(
        headlines=[{"title": "Nifty hits record", "published_at": "2026-06-01", "url": ""}],
        global_cues={"us": [{"name": "Dow Jones", "change_pct": 0.6, "direction": "up"}],
                     "asia": [], "macro": [], "gift_nifty": None},
        adrs=[{"name": "Infosys", "change_pct": 1.2, "direction": "up"}],
    )
    assert out["direction"] == "up"
    assert "Nifty" in out["summary"]


@patch("app.market.summary.OpenAI")
def test_summarise_openai_failure_falls_back(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.side_effect = Exception("timeout")
    with patch("app.market.summary.time.sleep"):
        out = summ.summarise(headlines=[], global_cues={"us": [], "asia": [], "macro": [], "gift_nifty": None}, adrs=[])
    assert out["direction"] == "flat"
    assert "Unable to generate" in out["summary"]


# ── /api/market/news-summary route ───────────────────────────────────────────

def _reset_news_cache():
    market._news_cache = None
    market._news_cache_ts = None


@patch("app.routes.market.summarise", return_value={"summary": "Read.", "direction": "up"})
@patch("app.routes.market.fetch_global_cues")
@patch("app.routes.market._fetch_nifty_headlines")
def test_news_summary_endpoint(mock_headlines, mock_cues, mock_summ):
    _reset_news_cache()
    mock_headlines.return_value = [{"title": "H1", "published_at": "2026-06-01", "url": "u"}]
    mock_cues.return_value = {
        "gift_nifty": {"name": "GIFT Nifty", "last": 23000.0, "change_pct": 0.4, "direction": "up"},
        "us": [{"name": "Dow Jones", "last": 100.0, "change_pct": 0.6, "direction": "up"}],
        "asia": [], "macro": [],
        "adrs": [{"name": "Infosys", "symbol": "INFY", "last": 20.0, "change_pct": 1.2, "direction": "up"}],
    }

    r = client.get("/api/market/news-summary?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["direction"] == "up"
    assert body["cached"] is False
    assert body["global_cues"]["gift_nifty"]["change_pct"] == 0.4
    assert "adrs" not in body["global_cues"]      # adrs hoisted to top level
    assert body["adrs"][0]["name"] == "Infosys"


@patch("app.routes.market.summarise", return_value={"summary": "Read.", "direction": "up"})
@patch("app.routes.market.fetch_global_cues", return_value={"gift_nifty": None, "us": [], "asia": [], "macro": [], "adrs": []})
@patch("app.routes.market._fetch_nifty_headlines", return_value=[])
def test_news_summary_uses_cache(mock_headlines, mock_cues, mock_summ):
    _reset_news_cache()
    first = client.get("/api/market/news-summary")
    assert first.json()["cached"] is False
    second = client.get("/api/market/news-summary")
    assert second.json()["cached"] is True
    # Underlying fetchers only called once thanks to the 15-min cache.
    assert mock_summ.call_count == 1
