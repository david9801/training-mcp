from mcp.server import MCPServer
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings

from training_mcp.auth.verifier import DenyAllTokenVerifier, DevTokenVerifier
from training_mcp.config import Settings
from training_mcp.mcp.garmin_tools import register_garmin_tools
from training_mcp.providers.garmin import GarminProvider


def build_token_verifier(settings: Settings) -> TokenVerifier:
    if settings.dev_token:
        return DevTokenVerifier(settings.dev_token, str(settings.resource_url), settings.scopes_supported)
    return DenyAllTokenVerifier()


def build_garmin_provider(settings: Settings) -> GarminProvider | None:
    if settings.garmin_personal_api_key is None:
        return None
    return GarminProvider(settings.garmin_personal_api_key, token_cache_file=settings.garmin_token_cache_file)


def build_mcp_server(settings: Settings, garmin: GarminProvider | None = None) -> MCPServer:
    mcp = MCPServer(
        name="training-mcp",
        title="Training MCP",
        description="Query your cycling and running activities from FIT files and Garmin Connect.",
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

    if garmin is not None:
        register_garmin_tools(mcp, garmin)

    return mcp
