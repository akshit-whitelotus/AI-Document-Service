from functools import lru_cache
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME:str
    ENVIRONMENT:str
    UPLOAD_DIR:str
    OUTPUT_DIR:str
    MAX_UPLOAD_SIZE_MB:int
    LOG_LEVEL:str
    DATABASE_URL: str
    DATABASE_URL_SYNC:str
    AUTH_JWKS_URL: str
    AUTH_ISSUER: str
    AUTH_AUDIENCE: str
    AUTH_JWKS_CACHE_TTL_SECONDS: int
    model_config=SettingsConfigDict(env_file=".env.example",case_sensitive=False)

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings=get_settings()