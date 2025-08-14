from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal
import os


class Settings(BaseSettings):
    app_name: str = Field(default="AI Superconnector", alias="APP_NAME")
    env: str = Field(default="dev", alias="ENV")
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Public base URL for webhooks (e.g., ngrok URL). If unset, derived from request.
    public_base_url: str | None = Field(default=None, alias="PUBLIC_BASE_URL")

    # DB: prefer SQLITE_PATH for local; fall back to standard URL
    sqlite_path: str = Field(default=".data/dev.db", alias="SQLITE_PATH")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    secret_key: str = Field(default="change-me", alias="SECRET_KEY")

    # Embeddings
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    embeddings_provider: Literal["hash", "openai"] = Field(default="hash", alias="EMBEDDINGS_PROVIDER")

    # Twilio Configuration (Voice  WhatsApp)
    twilio_account_sid: str | None = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str | None = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_api_key: str | None = Field(default=None, alias="TWILIO_API_KEY")
    twilio_api_secret: str | None = Field(default=None, alias="TWILIO_API_SECRET")
    twilio_whatsapp_number: str | None = Field(default=None, alias="TWILIO_WHATSAPP_NUMBER")
    twilio_phone_number: str | None = Field(default=None, alias="TWILIO_PHONE_NUMBER")
    whatsapp_business_account_id: str | None = Field(default=None, alias="WHATSAPP_BUSINESS_ACCOUNT_ID")

    # Connectors (placeholders)
    gmail_client_id: str | None = Field(default=None, alias="GMAIL_CLIENT_ID")
    gmail_client_secret: str | None = Field(default=None, alias="GMAIL_CLIENT_SECRET")
    slack_client_id: str | None = Field(default=None, alias="SLACK_CLIENT_ID")
    slack_client_secret: str | None = Field(default=None, alias="SLACK_CLIENT_SECRET")
    notion_client_id: str | None = Field(default=None, alias="NOTION_CLIENT_ID")
    notion_client_secret: str | None = Field(default=None, alias="NOTION_CLIENT_SECRET")

    # Feature flags
    force_tts_fallback: bool = Field(default=False, alias="FORCE_TTS_FALLBACK")
    media_echo_back: bool = Field(default=False, alias="MEDIA_ECHO_BACK")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def resolved_database_url(self) -> str:
        # If an explicit DB URL is set and not the known malformed example, use it.
        if self.database_url and "sqlite+sqlite" not in self.database_url:
            return self.database_url
        # Otherwise, build a local SQLite URL.
        sqlite_path = os.path.abspath(self.sqlite_path)
        return f"sqlite+pysqlite:///{sqlite_path}"


settings = Settings()

