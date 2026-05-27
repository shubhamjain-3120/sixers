from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_redirect_url: str = "http://localhost:8000/api/auth/kite/callback"

    # Automated daily login (TOTP-based 2FA)
    kite_user_id: str = ""
    kite_password: str = ""
    kite_totp_secret: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    database_url: str = "sqlite:///./swing_trader.db"
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5174"
    timezone: str = "Asia/Kolkata"
    log_level: str = "INFO"

    class Config:
        env_file = (".env", "../.env")  # works from both backend/ and swing-trader/
        case_sensitive = False


settings = Settings()
