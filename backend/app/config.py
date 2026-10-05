from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    env: str = "development"                       # development | production | test
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "ecg_hrv"
    jwt_secret: str = "CHANGE_ME_DEV_ONLY"
    jwt_algorithm: str = "HS256"
    session_hours: int = 8
    remember_days: int = 30
    cookie_secure: bool = False                    # True in production (HTTPS)
    cookie_samesite: str = "lax"
    cors_origins: str = "http://localhost:5173"
    storage_backend: str = "local"                 # local | s3
    storage_dir: str = "../storage"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    max_upload_mb: int = 500
    rate_limit_auth_per_min: int = 10
    rate_limit_upload_per_min: int = 10
    dev_print_reset_links: bool = True             # prints password-reset links to the server console (no SMTP yet)
    frontend_url: str = "http://localhost:5173"
    cookie_domain: str = ""

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_config() -> Config:
    c = Config()
    if c.env == "production" and (c.jwt_secret == "CHANGE_ME_DEV_ONLY" or len(c.jwt_secret) < 32):
        raise RuntimeError("JWT_SECRET must be set to a random string of >= 32 characters in production.")
    return c
