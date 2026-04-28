# Schema

This folder documents the expected data shapes for the `pytimer` runtime files.

The application stores its runtime files in `~/.pytimer`:

- `config.toml` — user preferences and runtime defaults
- `presets.json` — named countdown durations
- `sessions.jsonl` — one JSON object per completed or cancelled timer session

## Files

| File | Purpose |
| --- | --- |
| `config.schema.json` | JSON Schema describing the object represented by `config.toml`. |
| `presets.schema.json` | JSON Schema for `presets.json`. |
| `session-record.schema.json` | JSON Schema for each line/object in `sessions.jsonl`. |
| `examples/config.example.toml` | Example config file. |
| `examples/presets.example.json` | Example presets file. |
| `examples/session-record.example.json` | Example single session log record. |

## Notes

- JSON Schema does not validate TOML syntax directly. Parse `config.toml` into an object first, then validate that object against `config.schema.json`.
- `sessions.jsonl` is newline-delimited JSON. Validate each non-empty line against `session-record.schema.json`.
- Duration strings follow the timer parser formats used by the app, such as `5m`, `1h30m`, `90s`, `5:00`, or `5 minutes`.
