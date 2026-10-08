from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://clinicq:clinicq@localhost:5432/clinicq"
    app_name: str = "ClinicQ"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
