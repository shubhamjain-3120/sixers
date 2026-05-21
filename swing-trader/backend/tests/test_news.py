"""M6 acceptance tests for news classification + badge logic."""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime

from app.news.classifier import finalize_badge, classify_news, SYSTEM_PROMPT
from app.news.fetcher import fetch_headlines


# ── finalize_badge unit tests ─────────────────────────────────────────────────

def test_fundamental_risk_always_red():
    assert finalize_badge(block_flag=False, sector_flag=False, news_verdict="FUNDAMENTAL_RISK") == "RED"
    assert finalize_badge(block_flag=True, sector_flag=True, news_verdict="FUNDAMENTAL_RISK") == "RED"


def test_mixed_verdict_is_red():
    assert finalize_badge(block_flag=False, sector_flag=False, news_verdict="MIXED") == "RED"
    assert finalize_badge(block_flag=True, sector_flag=True, news_verdict="MIXED") == "RED"


def test_noise_with_block_flag_is_green():
    assert finalize_badge(block_flag=True, sector_flag=False, news_verdict="NOISE") == "GREEN"


def test_noise_with_sector_flag_is_green():
    assert finalize_badge(block_flag=False, sector_flag=True, news_verdict="NOISE") == "GREEN"


def test_noise_without_flags_is_yellow():
    assert finalize_badge(block_flag=False, sector_flag=False, news_verdict="NOISE") == "YELLOW"


def test_insufficient_data_is_yellow():
    assert finalize_badge(block_flag=False, sector_flag=False, news_verdict="INSUFFICIENT_DATA") == "YELLOW"
    assert finalize_badge(block_flag=True, sector_flag=True, news_verdict="INSUFFICIENT_DATA") == "YELLOW"


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
def test_guidance_cut_headline_produces_red_badge(mock_openai_cls):
    """S6 scenario: 'TCS guides Q3 revenue 5% below estimate' → badge=RED."""
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
    badge = finalize_badge(block_flag=False, sector_flag=False, news_verdict=result["verdict"])
    assert badge == "RED", f"Expected RED, got {badge}"


@patch("app.news.classifier.OpenAI")
def test_block_deal_headline_with_flag_produces_green_badge(mock_openai_cls):
    """S6 scenario: 'Block deal worth 500cr in HDFC' + block_flag=True → badge=GREEN."""
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
    badge = finalize_badge(block_flag=True, sector_flag=False, news_verdict=result["verdict"])
    assert badge == "GREEN", f"Expected GREEN, got {badge}"


@patch("app.news.classifier.OpenAI")
def test_block_deal_noise_without_flag_is_yellow(mock_openai_cls):
    """NOISE verdict but no block/sector flag → YELLOW."""
    per_hl = [{"idx": 1, "classification": "NOISE", "reason": "macro noise"}]
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        verdict="NOISE", per_headline=per_hl
    )

    db = _make_db()
    result = classify_news(
        symbol="RELIANCE",
        name="Reliance Industries",
        sector="Energy",
        headlines=_headlines(["Market weakness drags Reliance"]),
        ltp=2800.0, pct_drop=1.5, n_sessions=2,
        sector_index_name="NIFTY 50", sector_change_pct=-0.8,
        scan_date=date(2099, 6, 3),
        db=db,
    )

    badge = finalize_badge(block_flag=False, sector_flag=False, news_verdict=result["verdict"])
    assert badge == "YELLOW"


@patch("app.news.classifier.OpenAI")
def test_openai_failure_falls_back_to_yellow(mock_openai_cls):
    """If OpenAI fails both attempts, badge must be YELLOW (never blocks trading)."""
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
    badge = finalize_badge(block_flag=False, sector_flag=False, news_verdict=result["verdict"])
    assert badge == "YELLOW"


def test_system_prompt_contains_required_classifications():
    """Verify the LLM prompt contains all four classification labels."""
    for label in ("NOISE", "FUNDAMENTAL_NEGATIVE", "FUNDAMENTAL_POSITIVE", "IRRELEVANT"):
        assert label in SYSTEM_PROMPT, f"Missing {label} in system prompt"
    for verdict in ("FUNDAMENTAL_RISK", "NOISE", "MIXED", "INSUFFICIENT_DATA"):
        assert verdict in SYSTEM_PROMPT, f"Missing verdict {verdict} in system prompt"
