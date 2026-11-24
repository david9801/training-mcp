from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables prefixed with TMCP_."""

    # Keep path-less URLs without a trailing slash: issuer comparison (RFC 9207) is exact.
    model_config = SettingsConfigDict(
        env_prefix="TMCP_", env_file=".env", extra="ignore", url_preserve_empty_path=True
    )

    # Canonical URI of this MCP server (RFC 8707 resource indicator). No trailing slash.
    resource_url: AnyHttpUrl = "http://localhost:8000/mcp"  # type: ignore[assignment]
    # Authorization server that issues tokens for this resource.
    issuer_url: AnyHttpUrl = "http://localhost:9000"  # type: ignore[assignment]
    # Scopes advertised in Protected Resource Metadata (minimal set for basic use).
    scopes_supported: list[str] = ["activities:read"]

    # Local development only: a static bearer token accepted instead of a JWT.
    # Never set in production. Replaced by real JWT validation on day 2.
    dev_token: str | None = None

    # Host headers accepted on /mcp (DNS rebinding protection). Add your public host in prod.
    allowed_hosts: list[str] = ["localhost:*", "127.0.0.1:*"]

    database_url: str = "postgresql+psycopg://training:training@localhost:5432/training"

    # Garmin Connect Personal API key (own data only). Same variable name as Garmin's own CLI.
    # When unset, the Garmin tools are not registered. Never commit it.
    garmin_personal_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GARMIN_PERSONAL_API_KEY", "TMCP_GARMIN_PERSONAL_API_KEY"),
    )
    # Where Garmin's client caches the bearer token (file mode 0600). Must be writable.
    garmin_token_cache_file: Path = Path("~/.config/garmin/connect-personal-api-bearer-token.json")

    @field_validator("garmin_personal_api_key", mode="before")
    @classmethod
    def _blank_key_is_unset(cls, v: object) -> object:
        # `GARMIN_PERSONAL_API_KEY=` copied from .env.example means "not configured".
        return None if isinstance(v, str) and not v.strip() else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
