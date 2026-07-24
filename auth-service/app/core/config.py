from pydantic_settings import BaseSettings
from pathlib import Path
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME:str
    ENV:str
    DATABASE_URL:str
    DATABASE_URL_SYNC:str
    JWT_ISSUER:str
    JWT_AUDIENCE:str
    JWT_ALGORITHM:str
    JWT_KID:str
    PRIVATE_KEY_PATH:str
    PUBLIC_KEY_PATH:str
    ACCESS_TOKEN_EXPIRE_MINUTES:int
    REFRESH_TOKEN_EXPIRE_DAYS:int

    LOGIN_RATE_LIMIT:str
    REGISTER_RATE_LIMIT:str

    model_config=SettingsConfigDict(env_file=(".env.example",".env"),case_sensitive=False)

    @property
    def private_key_path(self) -> Path :
        return Path(self.PRIVATE_KEY_PATH)

    @property
    def public_key_path(self) -> Path:
        return Path(self.PUBLIC_KEY_PATH)

settings=Settings()



