import base64
import json
import time
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from fastapi.testclient import TestClient
from pydantic import SecretStr
from requests.adapters import BaseAdapter

from tests.conftest import DEV_TOKEN, mcp_headers, rpc
from training_mcp.config import Settings
from training_mcp.main import create_app
from training_mcp.providers.garmin import GarminProvider

API_KEY = "test-garmin-key"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"


def make_jwt(exp: float) -> str:
    def b64(d: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{b64({'alg': 'none'})}.{b64({'exp': exp})}.sig"


class FakeGarmin(BaseAdapter):
    """Stands in for personal.connectapi.garmin.com at the requests transport layer."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[requests.PreparedRequest] = []
        self.token_calls = 0
        self.token_exp = time.time() + 24 * 3600
        self.reject_bearer_once = False
        self.routes: dict[str, tuple[int, object]] = {
            "/activitylist-service/activities/search/activities": (
                200,
                [
                    {
                        "activityId": 42,
                        "activityName": "Morning ride",
                        "startTimeLocal": "2026-11-20 08:00:00",
                        "activityType": {"typeKey": "road_biking", "typeId": 10},
                        "distance": 52000.0,
                        "duration": 6300.0,
                        "averageHR": 141.0,
                        "summarizedDiveInfo": {"noise": True},
                    }
                ],
            ),
            "/activity-service/activity/42": (200, {"activityId": 42, "laps": 3}),
            "/sleep-service/sleep/dailySleep": (200, {"sleepTimeSeconds": 27000}),
            "/hrv-service/hrv/2026-11-20": (200, {"lastNightAvg": 58}),
            "/wellness-service/wellness/bodyBattery/reports/daily": (500, "internal detail"),
        }

    def _respond(self, request: requests.PreparedRequest, status: int, body: object) -> requests.Response:
        r = requests.Response()
        r.status_code = status
        r.request = request
        r.url = request.url or ""
        r._content = (body if isinstance(body, str) else json.dumps(body)).encode()
        return r

    def send(self, request: requests.PreparedRequest, **kwargs: object) -> requests.Response:  # type: ignore[override]
        self.requests.append(request)
        auth = request.headers.get("Authorization", "")
        path = urlsplit(request.url or "").path
        if path == TOKEN_PATH:
            assert request.method == "POST"
            if auth != f"ApiKey {API_KEY}":
                return self._respond(request, 401, "bad key")
            self.token_calls += 1
            return self._respond(request, 200, make_jwt(self.token_exp) + "\n")
        if not auth.startswith("Bearer "):
            return self._respond(request, 401, "")
        if self.reject_bearer_once:
            self.reject_bearer_once = False
            return self._respond(request, 401, "")
        status, body = self.routes.get(path, (404, "nope"))
        return self._respond(request, status, body)

    def close(self) -> None:
        pass


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fake() -> FakeGarmin:
    return FakeGarmin()


def make_provider(fake: FakeGarmin, cache: Path, key: str = API_KEY) -> GarminProvider:
    session = requests.Session()
    session.mount("https://", fake)
    return GarminProvider(SecretStr(key), token_cache_file=cache / "token.json", session=session)


@pytest.fixture
def garmin_client(fake: FakeGarmin, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(Settings(dev_token=DEV_TOKEN), garmin=make_provider(fake, tmp_path))
    with TestClient(app, base_url="http://localhost:8000") as c:
        yield c


def call_tool(client: TestClient, name: str, args: dict[str, object]) -> dict[str, object]:
    body = rpc("tools/call", {"name": name, "arguments": args})
    r = client.post("/mcp", headers=mcp_headers("tools/call", name), json=body)
    assert r.status_code == 200, r.text
    result: dict[str, object] = r.json()["result"]
    return result


# --- provider -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_token_is_cached_on_disk_and_reused(fake: FakeGarmin, tmp_path: Path) -> None:
    provider = make_provider(fake, tmp_path)
    await provider.get_activity(42)
    await provider.get_activity(42)
    assert fake.token_calls == 1
    assert (tmp_path / "token.json").stat().st_mode & 0o077 == 0  # not readable by others


@pytest.mark.anyio
async def test_token_close_to_expiry_is_renewed(fake: FakeGarmin, tmp_path: Path) -> None:
    fake.token_exp = time.time() + 30 * 60  # inside the library's 1 h renewal window
    provider = make_provider(fake, tmp_path)
    await provider.get_activity(42)
    await provider.get_activity(42)
    assert fake.token_calls == 2


@pytest.mark.anyio
async def test_retries_once_with_new_token_on_401(fake: FakeGarmin, tmp_path: Path) -> None:
    provider = make_provider(fake, tmp_path)
    await provider.get_activity(42)
    fake.reject_bearer_once = True
    assert await provider.get_activity(42) == {"activityId": 42, "laps": 3}
    assert fake.token_calls == 2


@pytest.mark.anyio
async def test_api_key_only_sent_to_token_endpoint(fake: FakeGarmin, tmp_path: Path) -> None:
    provider = make_provider(fake, tmp_path)
    await provider.search_activities(limit=500)
    data_calls = [r for r in fake.requests if urlsplit(r.url or "").path != TOKEN_PATH]
    assert all(API_KEY not in str(r.headers.get("Authorization")) for r in data_calls)
    assert parse_qs(urlsplit(data_calls[0].url or "").query)["limit"] == ["100"]  # capped


# --- tools ----------------------------------------------------------------------------


def test_garmin_tools_hidden_without_key(client: TestClient) -> None:
    r = client.post("/mcp", headers=mcp_headers("tools/list"), json=rpc("tools/list"))
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert not any(n.startswith("garmin_") for n in names)


def test_blank_key_counts_as_unset() -> None:
    assert Settings(garmin_personal_api_key="  ").garmin_personal_api_key is None


def test_garmin_tools_listed_with_key(garmin_client: TestClient) -> None:
    r = garmin_client.post("/mcp", headers=mcp_headers("tools/list"), json=rpc("tools/list"))
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert {"garmin_list_activities", "garmin_get_activity", "garmin_daily_wellness"} <= names


def test_list_activities_returns_summaries(garmin_client: TestClient, fake: FakeGarmin) -> None:
    result = call_tool(
        garmin_client,
        "garmin_list_activities",
        {"start_date": "2026-11-17", "end_date": "2026-11-23", "activity_type": "cycling"},
    )
    assert not result.get("isError"), result
    data = result["structuredContent"]
    assert data == {
        "activities": [
            {
                "activityId": 42,
                "activityName": "Morning ride",
                "startTimeLocal": "2026-11-20 08:00:00",
                "activityType": "road_biking",
                "distance": 52000.0,
                "duration": 6300.0,
                "averageHR": 141.0,
            }
        ],
        "count": 1,
        "offset": 0,
    }
    params = parse_qs(urlsplit(fake.requests[-1].url or "").query)
    assert params["startDate"] == ["2026-11-17"]
    assert params["activityType"] == ["cycling"]


def test_list_activities_rejects_inverted_range(garmin_client: TestClient) -> None:
    result = call_tool(
        garmin_client, "garmin_list_activities", {"start_date": "2026-11-23", "end_date": "2026-11-17"}
    )
    assert result["isError"] is True


def test_get_activity_not_found_is_tool_error(garmin_client: TestClient) -> None:
    result = call_tool(garmin_client, "garmin_get_activity", {"activity_id": 7})
    assert result["isError"] is True
    assert "Not found" in result["content"][0]["text"]  # type: ignore[index]


def test_daily_wellness_reports_partial_failures(garmin_client: TestClient) -> None:
    result = call_tool(garmin_client, "garmin_daily_wellness", {"day": "2026-11-20"})
    assert not result.get("isError"), result
    data = result["structuredContent"]
    assert data["sleep"] == {"sleepTimeSeconds": 27000}  # type: ignore[index]
    assert data["hrv"] == {"lastNightAvg": 58}  # type: ignore[index]
    assert data["body_battery"] is None  # type: ignore[index]
    assert "500" in data["errors"]["body_battery"]  # type: ignore[index]
    assert "internal detail" not in json.dumps(data)  # Garmin's raw body is not leaked


def test_rejected_api_key_message_is_actionable(tmp_path: Path) -> None:
    fake = FakeGarmin()
    app = create_app(Settings(dev_token=DEV_TOKEN), garmin=make_provider(fake, tmp_path, key="bogus-key-123"))
    with TestClient(app, base_url="http://localhost:8000") as c:
        result = call_tool(c, "garmin_get_activity", {"activity_id": 42})
    assert result["isError"] is True
    text = result["content"][0]["text"]  # type: ignore[index]
    assert "Personal API Token" in text
    assert "bogus-key-123" not in text
