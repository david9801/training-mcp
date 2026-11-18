import hmac

from mcp.server.auth.provider import AccessToken, TokenVerifier


class DenyAllTokenVerifier(TokenVerifier):
    """Rejects every token. Default until JWT validation lands."""

    async def verify_token(self, token: str) -> AccessToken | None:
        return None


class DevTokenVerifier(TokenVerifier):
    """Accepts a single static token for local development.

    The token is treated as issued for this server (audience = resource_url)
    with the configured scopes. Not for production use.
    """

    def __init__(self, dev_token: str, resource: str, scopes: list[str]) -> None:
        self._dev_token = dev_token
        self._resource = resource
        self._scopes = scopes

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token.encode(), self._dev_token.encode()):
            return None
        return AccessToken(
            token=token,
            client_id="dev-client",
            scopes=self._scopes,
            resource=self._resource,
            subject="dev-user",
        )
