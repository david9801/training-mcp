# ADR 0002: Target MCP specification 2026-07-28

- Status: accepted
- Date: 2026-11-18

## Decision

Target MCP revision 2026-07-28 with the official Python SDK (`mcp` 2.x):

- Stateless Streamable HTTP: no sessions, so instances scale horizontally behind Nginx.
- The server is an OAuth 2.1 resource server: Protected Resource Metadata (RFC 9728),
  audience validation against its canonical URI (RFC 8707), 401/403 challenges with
  `WWW-Authenticate`.
- The authorization server should support Client ID Metadata Documents, the preferred
  client registration method in this revision (Dynamic Client Registration is deprecated).
