"""Acceptance tests for news classification logic."""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime

from app.news.classifier import classify_news, SYSTEM_PROMPT
from app.news.fetcher import fetch_headlines


# ── classify_news with mocked OpenAI ─────────────────────────────────────────

def _make_db():
    """Return a minimal mock session that satisfies classify_news."""
    db = MagicMock()
    # No existing classification in DB
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def _mock_openai_response(verdict: str, per_headline: list, confidence: float = 0.9, summary: str = "Test summary"):
    payload = {
        "per_headline": per_headline,
        "overall_verdict": verdict,
        "confidence": confidence,
        "summary": summary,
    }
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(payload)
    return mock_resp


def _headlines(texts: list[str]):
    return [(t, datetime.utcnow(), "") for t in texts]


@patch("app.news.classifier.OpenAI")
def test_guidance_cut_produces_fundamental_risk(mock_openai_cls):
    """Guidance cut headline → FUNDAMENTAL_RISK verdict."""
    per_hl = [
        {"idx": 1, "classification": "FUNDAMENTAL_NEGATIVE", "reason": "guidance cut"},
    ]
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        verdict="FUNDAMENTAL_RISK",
        per_headline=per_hl,
        summary="Guidance cut signals fundamental deterioration.",
    )

    db = _make_db()
    result = classify_news(
        symbol="TCS",
        name="Tata Consultancy Services",
        sector="IT",
        headlines=_headlines(["TCS guides Q3 revenue 5% below estimate"]),
        ltp=3200.0,
        pct_drop=3.5,
        n_sessions=5,
        sector_index_name="NIFTY IT",
        sector_change_pct=-1.2,
        scan_date=date(2099, 6, 1),
        db=db,
    )

    assert result["verdict"] == "FUNDAMENTAL_RISK"


@patch("app.news.classifier.OpenAI")
def test_block_deal_headline_produces_noise(mock_openai_cls):
    """Block deal headline → NOISE verdict."""
    per_hl = [
        {"idx": 1, "classification": "NOISE", "reason": "block deal is institutional selling, noise"},
    ]
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        verdict="NOISE",
        per_headline=per_hl,
        summary="Block deal explains dip; macro noise.",
    )

    db = _make_db()
    result = classify_news(
        symbol="HDFCBANK",
        name="HDFC Bank Ltd.",
        sector="Financial Services",
        headlines=_headlines(["Block deal worth 500cr in HDFC"]),
        ltp=1502.0,
        pct_drop=2.1,
        n_sessions=3,
        sector_index_name="NIFTY BANK",
        sector_change_pct=-0.5,
        scan_date=date(2099, 6, 2),
        db=db,
    )

    assert result["verdict"] == "NOISE"


@patch("app.news.classifier.OpenAI")
def test_openai_failure_falls_back_to_insufficient_data(mock_openai_cls):
    """If OpenAI fails both attempts, verdict is INSUFFICIENT_DATA."""
    mock_openai_cls.return_value.chat.completions.create.side_effect = Exception("timeout")

    db = _make_db()
    result = classify_news(
        symbol="INFY",
        name="Infosys",
        sector="IT",
        headlines=_headlines(["Infosys wins $500M deal"]),
        ltp=1500.0, pct_drop=2.0, n_sessions=3,
        sector_index_name="NIFTY IT", sector_change_pct=0.3,
        scan_date=date(2099, 6, 4),
        db=db,
    )

    assert result["verdict"] == "INSUFFICIENT_DATA"


def test_system_prompt_contains_required_classifications():
    """Verify the LLM prompt contains all four classification labels."""
    for label in ("NOISE", "FUNDAMENTAL_NEGATIVE", "FUNDAMENTAL_POSITIVE", "IRRELEVANT"):
        assert label in SYSTEM_PROMPT, f"Missing {label} in system prompt"
    for verdict in ("FUNDAMENTAL_RISK", "NOISE", "MIXED", "INSUFFICIENT_DATA"):
        assert verdict in SYSTEM_PROMPT, f"Missing verdict {verdict} in system prompt"
