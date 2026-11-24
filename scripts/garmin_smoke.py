"""Call the Garmin MCP tools once against your real account and save what they return.

For a manual check without an MCP client: it builds the same MCP server the app serves
and calls its tools in-process (no HTTP, no OAuth), with the key from
GARMIN_PERSONAL_API_KEY in your environment or .env.

    uv run python scripts/garmin_smoke.py            # last 7 days
    uv run python scripts/garmin_smoke.py --days 30 --day 2026-11-20

Full JSON goes to garmin-output/ (gitignored). It is your personal data: review it before
sharing it with anyone.
"""

import argparse
import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from training_mcp.config import Settings
from training_mcp.mcp.server import build_garmin_provider, build_mcp_server

OUTPUT_DIR = Path("garmin-output")


async def call(mcp: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    result = await mcp.call_tool(name, arguments)
    if result.is_error:
        text = result.content[0].text if result.content else "(no message)"
        print(f"  FAILED {name}: {text}")
        return None
    data: dict[str, Any] = result.structured_content or {}
    save(name, data)
    return data


def save(name: str, data: dict[str, Any]) -> None:
    path = OUTPUT_DIR / f"{name}.json"
    text = json.dumps(data, indent=2, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    print(f"  OK     {name}: {', '.join(data)[:100]} -> {path} ({len(text.encode()) / 1024:.1f} KB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=7, help="activities from the last N days (default 7)")
    parser.add_argument("--day", type=date.fromisoformat, help="day for wellness (default yesterday)")
    args = parser.parse_args()

    settings = Settings()
    garmin = build_garmin_provider(settings)
    if garmin is None:
        print("GARMIN_PERSONAL_API_KEY is not set (environment or .env).", file=sys.stderr)
        return 2
    OUTPUT_DIR.mkdir(exist_ok=True)
    try:
        asyncio.run(run(build_mcp_server(settings, garmin), args.days, args.day))
    finally:
        garmin.close()
    print(f"\nDone. Full responses in {OUTPUT_DIR}/")
    return 0


async def run(mcp: Any, days: int, wellness_day: date | None) -> None:
    today = date.today()
    start = today - timedelta(days=days)
    day = wellness_day or today - timedelta(days=1)
    print(f"Activities from {start} to {today}:")
    listed = await call(
        mcp,
        "garmin_list_activities",
        {"start_date": str(start), "end_date": str(today), "limit": 20},
    )
    activities = (listed or {}).get("activities", [])
    for a in activities[:5]:
        km = a.get("distance", 0) / 1000
        when, kind, aid = a.get("startTimeLocal"), a.get("activityType"), a.get("activityId")
        print(f"         {when}  {kind}  {km:.1f} km  id={aid}")

    if activities:
        print("Detail of the most recent activity:")
        await call(mcp, "garmin_get_activity", {"activity_id": activities[0]["activityId"]})
    else:
        print("No activities in range: skipping garmin_get_activity (try --days 30).")

    print(f"Wellness for {day}:")
    wellness = await call(mcp, "garmin_daily_wellness", {"day": str(day)})
    if wellness and wellness.get("errors"):
        print(f"         partial: {wellness['errors']}")


if __name__ == "__main__":
    sys.exit(main())
