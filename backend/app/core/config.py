from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Dynaplan"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://localhost:5432/dynaplan"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    frontend_url: str = "http://localhost:3000"
    auto_create_schema: bool = False

    model_config = {"env_file": ".env", "env_prefix": "DYNAPLAN_"}


settings = Settings()
