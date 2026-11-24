from mcp.server import MCPServer
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings

from training_mcp.auth.verifier import DenyAllTokenVerifier, DevTokenVerifier
from training_mcp.config import Settings


def build_token_verifier(settings: Settings) -> TokenVerifier:
    if settings.dev_token:
        return DevTokenVerifier(settings.dev_token, str(settings.resource_url), settings.scopes_supported)
    return DenyAllTokenVerifier()


def build_mcp_server(settings: Settings) -> MCPServer:
    mcp = MCPServer(
        name="training-mcp",
        title="Training MCP",
        description="Query your cycling and running activities ingested from FIT files.",
        version="0.1.0",
        token_verifier=build_token_verifier(settings),
        auth=AuthSettings(
            issuer_url=settings.issuer_url,
            resource_server_url=settings.resource_url,
            required_scopes=settings.scopes_supported,
            # Reject tokens whose RFC 8707 resource/audience is not this server.
            validate_token_resource=True,
        ),
    )

    @mcp.tool()
    def ping() -> str:
        """Health check tool: returns 'pong' if the server is reachable and authorized."""
        return "pong"

    return mcp
