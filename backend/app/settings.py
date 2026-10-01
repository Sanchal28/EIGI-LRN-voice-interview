from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    eigi_base_url: str = ""
    eigi_api_key: str = ""
    eigi_agent_id: str = ""

    @property
    def eigi_configured(self) -> bool:
        return all(
            value.strip()
            for value in (
                self.eigi_base_url,
                self.eigi_api_key,
                self.eigi_agent_id,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

