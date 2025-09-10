# Privacy

Understand-First operates locally by default. Metrics are opt-in and no source code content is uploaded by the CLI.

## Metrics controls
Enable or disable metrics via `.understand-first.yml`:
```yaml
metrics:
  enabled: false
```
- When `enabled: false`, the CLI does not record any events.
- When `enabled: true`, the CLI records timestamped events to `metrics/events.jsonl`.

## What is recorded
- Event name (e.g., `map_open`, `tour_run`, `fixture_pass`)
- Unix timestamp
- Optional event-specific fields

## Where data is stored
- Local file: `metrics/events.jsonl`
- Weekly report (if generated): `docs/ttu.md`
- No network transmission is performed by the CLI for metrics collection.

## How to remove data
- Delete the `metrics/` directory to remove all recorded events.
- Set `metrics.enabled: false` to prevent future recording.

## Artifacts
Generated artifacts (maps, tours, dashboards) are written to the repository by default and are not transmitted by the CLI.

## Third‑party services
- The demo may start a local HTTP server for examples; it does not transmit data externally.
- If you manually publish artifacts, that is under your control and outside the CLI’s default behavior.
