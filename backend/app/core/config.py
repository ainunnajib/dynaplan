from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Dynaplan"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://localhost:5432/dynaplan"
    database_read_replica_urls: List[str] = Field(default_factory=list)
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_pool_timeout: int = 30
    database_pool_recycle: int = 1800
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    frontend_url: str = "http://localhost:3000"
    auto_create_schema: bool = False

    @field_validator("database_read_replica_urls", mode="before")
    @classmethod
    def parse_database_read_replica_urls(cls, value):
        if value is None:
            return []

        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            return [item.strip() for item in cleaned.split(",") if item.strip()]

        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]

        return value

    model_config = {"env_file": ".env", "env_prefix": "DYNAPLAN_"}


settings = Settings()
