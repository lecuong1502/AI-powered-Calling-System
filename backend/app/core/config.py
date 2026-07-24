from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "AI Voice Call Platform"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me"
    allowed_hosts: list[str] = ["*"]

    # JWT
    jwt_secret_key: str = "change-me-jwt"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://voicecall:voicecall_dev_password@localhost:5432/voicecall"

    # MongoDB
    mongo_url: str = "mongodb://voicecall:voicecall_dev_password@localhost:27017/voicecall_logs?authSource=admin"
    mongo_db: str = "voicecall_logs"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_url: str = "redis://localhost:6379/1"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_prefix: str = "tenant_"

    # Telephony
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    freeswitch_esl_host: str = "localhost"
    freeswitch_esl_port: int = 8021
    freeswitch_esl_password: str = "ClueCon"

    # AI Services
    llama_cpp_base_url: str = "http://localhost:8080"
    whisper_model_path: str = "./models/phowhisper-small"
    xtts_server_url: str = "http://localhost:5002"


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()