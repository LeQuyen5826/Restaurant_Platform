from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://rb:rb@localhost:5432/rb"
    jwt_secret: str = "dev-only-change-me"
    jwt_expire_minutes: int = 60 * 8
    cors_origins: str = "http://localhost:5173"
    upload_dir: str = "uploads"
    timezone: str = "Asia/Ho_Chi_Minh"


settings = Settings()
