# Changelog

## 2026-04-12

- Fixed input selection so `Timeline.json` works when `location-history.json` is absent (previously the script could exit incorrectly).
- `location-history.json` from device export is a single object with `semanticSegments` (not a top-level array); parsing now matches that shape instead of using the legacy list parser.
- Removed the `python-dateutil` dependency; timestamps use the standard library only.
- Enriched GPX output from the same export: inferred **visit** locations, **activity** start/end positions, and **rawSignals** GPS samples when present.
- Points within each day are sorted by time for cleaner tracks.
