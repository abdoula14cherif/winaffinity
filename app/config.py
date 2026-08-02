from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "development"

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    resend_api_key: str = ""

    allowed_origins: str = "http://localhost:3000"

    class Config:
        extra = "ignore"
        env_file = ".env"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
