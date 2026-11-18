# ADR 0001: Ingest FIT files instead of vendor APIs

- Status: accepted
- Date: 2026-11-17

## Context

The server needs per-user training data (rides, runs). The Garmin Connect developer
program is not accepting new applications, unofficial libraries need the user's
password and may break the vendor's terms, and Strava restricts using its data with AI.
iGPSport may offer a data API, but this is unconfirmed.

## Decision

Users upload FIT files, the format training devices record natively. The server parses
them and stores activities in PostgreSQL. Data sources sit behind a provider interface
(`providers/`), so a vendor API such as iGPSport can be added later without changing
the MCP tools.

## Consequences

- No third-party credentials to store, no dependency on vendor approval.
- The public demo uses sample FIT files only, never real personal data.
- Data is not synced automatically; that becomes a provider concern later.
