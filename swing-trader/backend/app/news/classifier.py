import json
import logging
from datetime import date, datetime
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from openai import OpenAI
from app.config import settings
from app.db.models import NewsClassification, SetupClassification, DailyScan

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a financial analyst classifying whether news about an Indian listed company indicates a NOISE-driven price move (which tends to mean-revert) or a FUNDAMENTAL change in the company's outlook (which does not).
Output ONLY valid JSON matching this schema:
{
  "per_headline": [
    {"idx": <1-5>, "classification": "NOISE"|"FUNDAMENTAL_NEGATIVE"|"FUNDAMENTAL_POSITIVE"|"IRRELEVANT", "reason": "<one short clause>"}
  ],
  "overall_verdict": "NOISE" | "FUNDAMENTAL_RISK" | "MIXED" | "INSUFFICIENT_DATA",
  "confidence": <float 0.0 to 1.0>,
  "summary": "<plain-English explanation of what is causing the recent price move, 1-2 sentences, max 40 words. If no headline plausibly explains the move, return an empty string. Do NOT restate the verdict or comment on data quality — only describe the driver if one exists.>"
}
Classification rules:
- NOISE: block deals, sector/macro/geopolitical moves, profit booking, routine business updates, broker price-target changes without rationale
- FUNDAMENTAL_NEGATIVE: guidance cuts, earnings misses, management exits, regulatory probes, ratings downgrades on fundamentals, deal losses, fraud allegations, accounting concerns
- FUNDAMENTAL_POSITIVE: guidance raises, strong order wins, positive regulatory developments, accretive M&A, breakthrough product launches
- IRRELEVANT: not about this company, dated >5 days, generic listicles, paid promotional content
Overall verdict logic:
- FUNDAMENTAL_RISK: any FUNDAMENTAL_NEGATIVE classification in the top 3 (most recent) headlines
- NOISE: majority NOISE/IRRELEVANT and zero FUNDAMENTAL_NEGATIVE
- MIXED: combination of FUNDAMENTAL_NEGATIVE and FUNDAMENTAL_POSITIVE
- INSUFFICIENT_DATA: fewer than 3 relevant (non-IRRELEVANT) headlines
Confidence: 0.9+ if you are sure, 0.6-0.8 if reasonable doubt, <0.5 if guessing.
Examples:
- "Block deal worth 500 cr in TCS" → NOISE
- "Iran-Israel tensions drag IT stocks" → NOISE
- "TCS guides Q3 revenue 5% below estimate" → FUNDAMENTAL_NEGATIVE
- "Infosys wins $500M deal from European bank" → FUNDAMENTAL_POSITIVE"""


def _build_user_message(
    symbol: str, name: str, sector: str,
    headlines: List[Tuple[str, datetime, str]],
    ltp: float, pct_drop: float, n_sessions: int,
    sector_index_name: str, sector_change_pct: float,
) -> str:
    lines = [
        f"Company: {symbol} ({name})",
        f"Sector: {sector}",
        f"Price action: down {pct_drop:.1f}% over last {n_sessions} sessions, currently at ₹{ltp:.2f}",
        f"Sector context: {sector_index_name} moved {sector_change_pct:.2f}% today",
        "Top 5 headlines (most recent first):",
    ]
    for i in range(5):
        if i < len(headlines):
            headline, pub, _ = headlines[i]
            date_str = pub.strftime("%d %b")
            lines.append(f"{i+1}. [{date_str}] {headline}")
        else:
            lines.append(f"{i+1}. [no further headlines]")
    return "\n".join(lines)


def classify_news(
    symbol: str, name: str, sector: str,
    headlines: List[Tuple[str, datetime, str]],
    ltp: float, pct_drop: float, n_sessions: int,
    sector_index_name: str, sector_change_pct: float,
    scan_date: date, db: Session,
    temperature: float = 0.2,
) -> dict:
    """Call OpenAI, persist result. Returns classification dict."""
    existing = (
        db.query(NewsClassification)
        .filter(
            NewsClassification.symbol == symbol,
            NewsClassification.classification_date == scan_date,
        )
        .first()
    )
    if existing:
        return {
            "verdict": existing.verdict,
            "confidence": existing.confidence,
            "summary": existing.summary,
            "per_headline": json.loads(existing.per_headline_json or "[]"),
        }

    if not headlines:
        _save_classification(db, symbol, scan_date, headlines, [], "INSUFFICIENT_DATA", 0.0, "", "")
        return {"verdict": "INSUFFICIENT_DATA", "confidence": 0.0, "summary": "", "per_headline": []}

    user_msg = _build_user_message(symbol, name, sector, headlines, ltp, pct_drop, n_sessions, sector_index_name, sector_change_pct)
    client = OpenAI(api_key=settings.openai_api_key)

    for attempt in range(2):
        try:
            temp = temperature if attempt == 0 else 0.0
            resp = client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                temperature=temp,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            )
            raw = resp.choices[0].message.content
            data = json.loads(raw)
            verdict = data.get("overall_verdict", "INSUFFICIENT_DATA")
            confidence = float(data.get("confidence", 0.5))
            summary = data.get("summary", "")
            per_headline = data.get("per_headline", [])
            _save_classification(db, symbol, scan_date, headlines, per_headline, verdict, confidence, summary, raw)
            return {"verdict": verdict, "confidence": confidence, "summary": summary, "per_headline": per_headline}
        except json.JSONDecodeError as e:
            logger.error(f"Malformed JSON from LLM for {symbol} (attempt {attempt+1}): {e}")
        except Exception as e:
            logger.error(f"OpenAI call failed for {symbol} (attempt {attempt+1}): {e}")
            import time; time.sleep(2 ** attempt)

    # Both attempts failed
    _save_classification(db, symbol, scan_date, headlines, [], "INSUFFICIENT_DATA", 0.0, "", "")
    return {"verdict": "INSUFFICIENT_DATA", "confidence": 0.0, "summary": "", "per_headline": []}


def _save_classification(
    db: Session, symbol: str, scan_date: date,
    headlines: list, per_headline: list,
    verdict: str, confidence: float, summary: str, raw: str,
):
    headlines_json = json.dumps([h[0] for h in headlines]) if headlines else "[]"
    obj = NewsClassification(
        symbol=symbol,
        classification_date=scan_date,
        headlines_json=headlines_json,
        per_headline_json=json.dumps(per_headline),
        verdict=verdict,
        confidence=confidence,
        summary=summary,
        raw_response=raw,
    )
    db.add(obj)
    try:
        db.commit()
    except Exception:
        db.rollback()


def run_news_classification():
    """Full pipeline: fetch news + classify + badge for all today's candidates."""
    from app.db.session import SessionLocal
    from app.news.fetcher import fetch_headlines
    from app.db.models import Instrument, Config
    from sqlalchemy import desc

    db = SessionLocal()
    try:
        today = date.today()
        cfg = db.query(Config).filter(Config.id == 1).first()
        min_score = cfg.min_score_threshold if cfg else 60.0

        scans = (
            db.query(DailyScan)
            .filter(DailyScan.scan_date == today, DailyScan.score >= min_score)
            .all()
        )
        logger.info(f"Classifying {len(scans)} candidates")

        for s in scans:
            inst = db.query(Instrument).filter(Instrument.symbol == s.symbol).first()
            if not inst:
                continue

            headlines = fetch_headlines(s.symbol, inst.name or s.symbol, db)

            pct_drop = s.pct_below_20d_high or 0.0
            ltp = s.ltp or 0.0

            result = classify_news(
                symbol=s.symbol,
                name=inst.name or s.symbol,
                sector=inst.sector or "Unknown",
                headlines=headlines,
                ltp=ltp,
                pct_drop=pct_drop,
                n_sessions=5,
                sector_index_name="NIFTY 50",
                sector_change_pct=0.0,
                scan_date=today,
                db=db,
            )

            existing_setup = (
                db.query(SetupClassification)
                .filter(
                    SetupClassification.symbol == s.symbol,
                    SetupClassification.scan_date == today,
                )
                .first()
            )
            if existing_setup:
                existing_setup.news_verdict = result["verdict"]
            else:
                db.add(SetupClassification(
                    symbol=s.symbol,
                    scan_date=today,
                    sector_flag=False,
                    news_verdict=result["verdict"],
                    badge="YELLOW",
                ))
            try:
                db.commit()
            except Exception:
                db.rollback()

            logger.info(f"{s.symbol}: verdict={result['verdict']}")

    except Exception as e:
        logger.error(f"News classification pipeline failed: {e}", exc_info=True)
    finally:
        db.close()
