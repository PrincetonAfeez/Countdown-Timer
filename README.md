# pytimer

A terminal countdown timer built as a small Python package. It supports compact,
colon, and natural duration input, multiple sequential timers, presets, JSONL
session logs, completion notifications, and an interactive keyboard-driven UI.

## Install

```powershell
python -m pip install -e ".[dev]"
```

For desktop notifications:

```powershell
python -m pip install -e ".[desktop]"
```

## Usage

```powershell
pytimer 5m
pytimer start 5m --label "tea"
pytimer start 25m 5m 25m 5m
pytimer preset pomodoro
pytimer preset add stretch 10m
pytimer log --last 10
pytimer log --stats
```

Accepted duration formats include:

- `5m`, `1h30m`, `90s`, `2h15m30s`, `500ms`
- `5:00`, `1:30:00`, `00:00:10`
- `5 minutes`, `1 hour 30 min`, `ninety seconds`

## Keybindings

| Key | Action |
| --- | --- |
| `p` | pause/resume the active timer |
| `r` | reset the active timer |
| `a` | add a 5 minute timer |
| `d` | cancel the active timer |
| `+` | add 30 seconds |
| `-` | subtract 30 seconds |
| `n` | select the next timer |
| `?` | toggle help |
| `q` | quit |

## Files

Runtime files live in `~/.pytimer`:

- `config.toml` for defaults such as tick rate, renderer, parser order, and notifiers
- `presets.json` for named durations
- `sessions.jsonl` for completed and cancelled timer history

## Development

```powershell
python -m pytest
python -m ruff check .
python -m mypy src/pytimer
```

The core tests use `FakeTimeSource`, so timer behavior is deterministic and no
test has to sleep.

