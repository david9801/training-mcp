from functools import lru_cache

from pydantic import AnyHttpUrl
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
