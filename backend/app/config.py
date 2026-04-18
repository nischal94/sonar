# backend/app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str

    openai_api_key: str
    groq_api_key: str

    resend_api_key: str
    resend_from_email: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    telegram_bot_token: str

    apify_api_token: str
    extension_version: str = "1.0.0"

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Project-wide LLM routing constants. Keep in lockstep with sonar/CLAUDE.md
# "LLM and agent discipline" routing rules. Single source of truth — every
# caller imports from here, no hardcoding model names at call sites.
OPENAI_MODEL_EXPENSIVE = "gpt-5.4-mini"
