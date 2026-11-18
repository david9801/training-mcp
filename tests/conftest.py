from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from training_mcp.config import Settings
from training_mcp.main import create_app

DEV_TOKEN = "test-dev-token"
PROTOCOL_VERSION = "2026-07-28"


@pytest.fixture
def settings() -> Settings:
    return Settings(dev_token=DEV_TOKEN)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), base_url="http://localhost:8000") as c:
        yield c


def rpc(method: str, params: dict | None = None, id_: int = 1) -> dict:
    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": {**(params or {}), "_meta": meta}}


def mcp_headers(method: str, name: str | None = None, token: str | None = DEV_TOKEN) -> dict:
    headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if name:
        headers["Mcp-Name"] = name
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
