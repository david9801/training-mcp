# ADR 0003: Read Garmin data through the Personal API with Garmin's official client

- Status: accepted
- Date: 2026-11-24
- Refines: [ADR 0001](0001-fit-files-instead-of-vendor-apis.md)

## Context

ADR 0001 chose FIT uploads because Garmin's developer program was closed to individuals.
Since 2026-10-21 Garmin offers a free **Personal API key**: each user creates it in
Garmin Connect (Settings > Personal API Token, valid 30 days to 1 year) and can read
their own activities and wellness data. It is for personal use only, does not include
the Training API (no pushing workouts to the watch), and is not meant for apps that
serve other users. The business Connect Developer Program stays out of scope for now.

## Decision

- Add a Garmin provider (`providers/garmin.py`) on top of Garmin's official Python client,
  `garmin-connect-personal-api-python` (Apache-2.0). It handles the key-for-token
  exchange, the 0600 on-disk token cache and renewal when less than an hour is left.
- The client is synchronous (`requests`), so each call runs in a worker thread
  (`asyncio.to_thread`) and never blocks the server's event loop. On a 401 from a data
  endpoint we force a new token and retry once.
- The key is read from `GARMIN_PERSONAL_API_KEY` (the name Garmin's own CLI uses), held
  as a `SecretStr`, and never committed. Without it the Garmin tools are not registered.
- Library errors are mapped to short messages; Garmin's raw response bodies and URLs
  never reach the MCP client.
- Tools are read-only and gated by the existing `activities:read` scope:
  `garmin_list_activities`, `garmin_get_activity`, `garmin_daily_wellness`.

## Consequences

- One server instance serves one Garmin account (the key owner), which matches the
  Personal API terms. Multi-user Garmin access would need the business program and
  per-user OAuth with Garmin.
- FIT ingestion stays the main path for history and other devices; downloading the
  original FIT through the Personal API can feed the same parser later.
- A thread per Garmin call is fine at personal volume; revisit if the client gains async
  support or the load grows.
