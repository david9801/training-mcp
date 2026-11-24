"""MCP tools backed by the Garmin Connect Personal API (read-only, the key owner's data)."""

import asyncio
from collections.abc import Awaitable
from datetime import date
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from training_mcp.providers.garmin import MAX_ACTIVITIES_PER_PAGE, GarminError, GarminProvider, JsonValue

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)

# Fields kept from each activity in list results, so a page of 100 stays small for the model.
ACTIVITY_SUMMARY_FIELDS = (
    "activityId",
    "activityName",
    "startTimeLocal",
    "distance",
    "duration",
    "movingDuration",
    "elevationGain",
    "averageSpeed",
    "averageHR",
    "maxHR",
    "averagePower",
    "normPower",
    "calories",
    "aerobicTrainingEffect",
    "anaerobicTrainingEffect",
    "activityTrainingLoad",
)


def summarize_activity(activity: dict[str, Any]) -> dict[str, Any]:
    summary = {k: activity[k] for k in ACTIVITY_SUMMARY_FIELDS if activity.get(k) is not None}
    activity_type = activity.get("activityType")
    if isinstance(activity_type, dict) and activity_type.get("typeKey"):
        summary["activityType"] = activity_type["typeKey"]
    return summary


async def _call(coro: Awaitable[JsonValue]) -> JsonValue:
    try:
        return await coro
    except GarminError as exc:
        raise ToolError(str(exc)) from exc


def register_garmin_tools(mcp: MCPServer, garmin: GarminProvider) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def garmin_list_activities(
        start_date: Annotated[date | None, Field(description="First day, inclusive (YYYY-MM-DD)")] = None,
        end_date: Annotated[date | None, Field(description="Last day, inclusive (YYYY-MM-DD)")] = None,
        activity_type: Annotated[
            str | None, Field(description="Garmin type key, e.g. cycling, running, road_biking")
        ] = None,
        limit: Annotated[int, Field(ge=1, le=MAX_ACTIVITIES_PER_PAGE)] = 20,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict[str, Any]:
        """List your Garmin Connect activities, newest first, with summary metrics.

        Units: distance in meters, durations in seconds, speed in m/s, power in watts.
        Use garmin_get_activity for the full detail of one activity.
        """
        if start_date and end_date and start_date > end_date:
            raise ToolError("start_date must be on or before end_date")
        raw = await _call(
            garmin.search_activities(
                start_date=start_date,
                end_date=end_date,
                activity_type=activity_type,
                start=offset,
                limit=limit,
            )
        )
        items = raw if isinstance(raw, list) else []
        activities = [summarize_activity(a) for a in items if isinstance(a, dict)]
        return {"activities": activities, "count": len(activities), "offset": offset}

    @mcp.tool(annotations=READ_ONLY)
    async def garmin_get_activity(
        activity_id: Annotated[int, Field(gt=0, description="activityId from garmin_list_activities")],
    ) -> dict[str, Any]:
        """Get the full Garmin Connect detail of one activity (summary, laps metadata, device)."""
        raw = await _call(garmin.get_activity(activity_id))
        return raw if isinstance(raw, dict) else {"activity": raw}

    @mcp.tool(annotations=READ_ONLY)
    async def garmin_daily_wellness(
        day: Annotated[date, Field(description="Calendar day (YYYY-MM-DD)")],
    ) -> dict[str, Any]:
        """Get recovery data for one day from Garmin Connect: sleep, HRV and body battery.

        A section is null if Garmin has no data for that day; per-section errors are reported
        under "errors" so one failing source does not hide the others.
        """
        results = await asyncio.gather(
            garmin.get_daily_sleep(day),
            garmin.get_daily_hrv(day),
            garmin.get_daily_body_battery(day),
            return_exceptions=True,
        )
        out: dict[str, Any] = {"date": day.isoformat()}
        errors: dict[str, str] = {}
        for name, result in zip(("sleep", "hrv", "body_battery"), results, strict=True):
            if isinstance(result, GarminError):
                out[name] = None
                errors[name] = str(result)
            elif isinstance(result, BaseException):
                raise result
            else:
                out[name] = result
        if len(errors) == 3:
            raise ToolError(f"All Garmin wellness calls failed: {errors['sleep']}")
        if errors:
            out["errors"] = errors
        return out
