# training-mcp

A remote [Model Context Protocol](https://modelcontextprotocol.io) server that lets an AI
assistant query your cycling and running activities, protected with OAuth 2.1.

Activities are ingested from FIT files (the format training devices record) into
PostgreSQL. The server exposes them as MCP tools, so you can ask things like
*"How did this week compare to last week?"*. Each user authorizes the assistant with
their own account, and every tool is gated by a scope.

> Status: day 1 of 15. A `ping` tool behind OAuth; real tools are coming.

## Highlights

- **MCP 2026-07-28**, stateless Streamable HTTP: no sessions, scales horizontally.
- **OAuth 2.1 resource server**: Protected Resource Metadata (RFC 9728), audience
  validation (RFC 8707), `401`/`403` challenges with `WWW-Authenticate`.
- **Provider interface** for data sources: FIT upload today, vendor APIs later.

## Run locally

Requirements: Docker, or Python 3.13 with [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env          # set TMCP_DEV_TOKEN to any local secret
docker compose up --build
curl localhost:8000/healthz
curl localhost:8000/.well-known/oauth-protected-resource/mcp
```

`TMCP_DEV_TOKEN` is a static bearer token accepted only for local development, until JWT
validation lands. Without it the server rejects every token.

Try it with [MCP Inspector](https://github.com/modelcontextprotocol/inspector): connect to
`http://localhost:8000/mcp` with header `Authorization: Bearer <TMCP_DEV_TOKEN>`.

## Develop

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

## Project layout

```
src/training_mcp/
  main.py        FastAPI app, mounts the MCP endpoint
  config.py      settings from TMCP_* environment variables
  auth/          token verification
  mcp/           MCP server and tools
  providers/     data source adapters (FIT files, later vendor APIs)
  ingestion/     FIT parsing
  db/            persistence
docs/adr/        architecture decision records
```

## Decisions

- [ADR 0001: Ingest FIT files instead of vendor APIs](docs/adr/0001-fit-files-instead-of-vendor-apis.md)
- [ADR 0002: Target MCP specification 2026-07-28](docs/adr/0002-mcp-spec-revision.md)

## License

MIT
