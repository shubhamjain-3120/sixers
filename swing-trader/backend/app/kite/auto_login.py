import logging
from urllib.parse import urlparse, parse_qs, urljoin

import pyotp
import requests
from kiteconnect import KiteConnect
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import KiteToken
from app.kite.auth import store_kite_token

logger = logging.getLogger(__name__)

LOGIN_URL = "https://kite.zerodha.com/api/login"
TWOFA_URL = "https://kite.zerodha.com/api/twofa"
CONNECT_URL = "https://kite.zerodha.com/connect/login"


def _token_in(url: str):
    return parse_qs(urlparse(url or "").query).get("request_token", [None])[0]


def _extract_request_token(session: requests.Session) -> str:
    """Walk the connect/login redirect chain and pull out request_token.

    connect/login 302s to connect/finish (still on kite.zerodha.com), which in
    turn 302s to the registered redirect_url carrying request_token. We follow
    hops manually, but only while they stay on Zerodha's domain — we must NOT
    fetch the final redirect_url (the live callback), since that endpoint would
    consume the one-time request_token before we can use it.
    """
    next_url = f"{CONNECT_URL}?api_key={settings.kite_api_key}&v=3"
    for _ in range(5):
        resp = session.get(next_url, allow_redirects=False, timeout=15)
        location = resp.headers.get("Location", "")
        # The token first appears in a Location we're about to be redirected to.
        token = _token_in(location) or _token_in(getattr(resp, "url", ""))
        if token:
            return token
        if resp.is_redirect and location:
            location = urljoin(next_url, location)
            if urlparse(location).netloc.endswith("zerodha.com"):
                next_url = location
                continue
        break
    raise RuntimeError("request_token not found in connect/login redirect")


def auto_login(db: Session) -> KiteToken:
    """Programmatically log into Kite using stored credentials + TOTP and store a fresh token."""
    if not (settings.kite_user_id and settings.kite_password and settings.kite_totp_secret):
        raise RuntimeError("Auto-login credentials not configured (KITE_USER_ID/PASSWORD/TOTP_SECRET)")

    session = requests.Session()

    resp = session.post(
        LOGIN_URL,
        data={"user_id": settings.kite_user_id, "password": settings.kite_password},
        timeout=15,
    )
    resp.raise_for_status()
    request_id = resp.json()["data"]["request_id"]

    totp = pyotp.TOTP(settings.kite_totp_secret).now()
    resp = session.post(
        TWOFA_URL,
        data={
            "user_id": settings.kite_user_id,
            "request_id": request_id,
            "twofa_value": totp,
            "twofa_type": "totp",
        },
        timeout=15,
    )
    resp.raise_for_status()

    request_token = _extract_request_token(session)

    kite = KiteConnect(api_key=settings.kite_api_key)
    data = kite.generate_session(request_token, api_secret=settings.kite_api_secret)

    token = store_kite_token(db, data["access_token"], data.get("public_token"))
    logger.info(f"Kite auto-login succeeded, token expires_at={token.expires_at}")
    return token
