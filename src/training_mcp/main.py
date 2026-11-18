from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from training_mcp.config import Settings, get_settings
from training_mcp.mcp.server import build_mcp_server


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    mcp = build_mcp_server(settings)
    # Stateless Streamable HTTP (MCP 2026-07-28): no sessions, scales horizontally.
    mcp_app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(allowed_hosts=settings.allowed_hosts),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="training-mcp", lifespan=lifespan)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # Serves /mcp and /.well-known/oauth-protected-resource/mcp (RFC 9728).
    app.mount("/", mcp_app)
    return app


app = create_app()
