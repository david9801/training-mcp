from fastapi.testclient import TestClient

from tests.conftest import mcp_headers, rpc


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_protected_resource_metadata(client: TestClient) -> None:
    # RFC 9728: metadata lives at /.well-known/oauth-protected-resource + resource path.
    r = client.get("/.well-known/oauth-protected-resource/mcp")
    assert r.status_code == 200
    body = r.json()
    assert body["resource"] == "http://localhost:8000/mcp"
    assert body["authorization_servers"] == ["http://localhost:9000"]
    assert body["scopes_supported"] == ["activities:read"]


def test_mcp_without_token_returns_401_with_metadata_pointer(client: TestClient) -> None:
    r = client.post("/mcp", headers=mcp_headers("tools/list", token=None), json=rpc("tools/list"))
    assert r.status_code == 401
    challenge = r.headers["www-authenticate"]
    assert challenge.startswith("Bearer ")
    assert 'resource_metadata="http://localhost:8000/.well-known/oauth-protected-resource/mcp"' in challenge


def test_mcp_with_wrong_token_returns_401(client: TestClient) -> None:
    r = client.post("/mcp", headers=mcp_headers("tools/list", token="nope"), json=rpc("tools/list"))
    assert r.status_code == 401
