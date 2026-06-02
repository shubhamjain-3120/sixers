"""Unified pre-market read: fuse India headlines + global cues + ADR moves
into a single directional summary via OpenAI.

Mirrors the JSON-mode + 2-attempt-retry pattern used elsewhere in the app
(see app/routes/market.py legacy summariser and app/news/classifier.py).
"""
import json
import logging
import time

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a market strategist briefing an Indian swing trader before the open.
You are given (a) recent NIFTY/Sensex news headlines, (b) global market cues that historically lead NIFTY \
(GIFT Nifty, US indices, Asian indices, India VIX, Brent crude, USD/INR), and (c) overnight moves in \
Indian ADRs (Infosys, ICICI Bank, HDFC Bank, Wipro, Dr Reddy's).

Write a concise pre-market read as 3-4 bullet points (each starting with "- " on its own line). Each bullet \
should cover one key driver and include specific numbers from the data provided. Synthesise into a directional \
call for how NIFTY is likely to open and behave.
Also return the overall expected direction.
Output ONLY valid JSON matching this schema:
{
  "summary": "<3-4 bullet points, each on its own line starting with '- '>",
  "direction": "up" | "down" | "flat"
}
Rules:
- "up": cues net positive (GIFT Nifty/US/ADRs higher), NIFTY likely to open/trend firm.
- "down": cues net negative, NIFTY likely to open/trend weak.
- "flat": mixed or marginal cues.
- Ground every claim in the data provided — do not invent figures.
- Lead with the strongest signal (GIFT Nifty and US cues usually dominate)."""


def _format_cues(global_cues: dict, adrs: list[dict]) -> str:
    lines: list[str] = []

    gift = global_cues.get("gift_nifty")
    if gift:
        lines.append(f"GIFT Nifty: {gift['change_pct']:+.2f}% (direction {gift['direction']})")

    def _bucket(label: str, rows: list[dict]):
        if rows:
            parts = [f"{r['name']} {r['change_pct']:+.2f}%" for r in rows]
            lines.append(f"{label}: " + ", ".join(parts))

    _bucket("US markets", global_cues.get("us", []))
    _bucket("Asian markets", global_cues.get("asia", []))
    _bucket("Macro", global_cues.get("macro", []))
    _bucket("Indian ADRs (overnight)", adrs)

    return "\n".join(lines) if lines else "No global cues available."


def _format_headlines(headlines: list[dict]) -> str:
    if not headlines:
        return "No recent NIFTY/Sensex headlines."
    lines = ["Top headlines (most recent first):"]
    for i, h in enumerate(headlines, 1):
        lines.append(f"{i}. [{h['published_at'][:10]}] {h['title']}")
    return "\n".join(lines)


def summarise(headlines: list[dict], global_cues: dict, adrs: list[dict]) -> dict:
    """Produce {"summary", "direction"} from the combined inputs."""
    user_msg = (
        "GLOBAL CUES:\n"
        + _format_cues(global_cues, adrs)
        + "\n\nINDIA NEWS:\n"
        + _format_headlines(headlines)
    )

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
        except Exception as e:  # noqa: BLE001
            logger.error(f"OpenAI call failed (attempt {attempt + 1}): {e}")
            if attempt == 0:
                time.sleep(2)

    return {"summary": "Unable to generate market summary at this time.", "direction": "flat"}
