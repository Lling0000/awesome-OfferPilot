from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OfferPilot"
    database_url: str = "sqlite:///data/offerpilot.db"
    storage_dir: Path = Path("storage")
    demo_user_email: str = "demo@offerpilot.local"

    model_config = SettingsConfigDict(env_prefix="OFFERPILOT_", env_file=".env", extra="ignore")


def get_settings() -> Settings:
    return Settings()
