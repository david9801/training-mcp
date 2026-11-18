from fastapi.testclient import TestClient

from tests.conftest import mcp_headers, rpc


def test_tools_list_includes_ping(client: TestClient) -> None:
    r = client.post("/mcp", headers=mcp_headers("tools/list"), json=rpc("tools/list"))
    assert r.status_code == 200, r.text
    names = [t["name"] for t in r.json()["result"]["tools"]]
    assert "ping" in names


def test_ping_tool(client: TestClient) -> None:
    body = rpc("tools/call", {"name": "ping", "arguments": {}})
    r = client.post("/mcp", headers=mcp_headers("tools/call", "ping"), json=body)
    assert r.status_code == 200, r.text
    assert r.json()["result"]["content"][0]["text"] == "pong"
