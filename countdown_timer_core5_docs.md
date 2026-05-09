# Architecture Decision Record
## App 33 — Countdown Timer
**Terminal Tools Group | Document 1 of 5**  
**Status: Accepted**

---

## Context

Countdown Timer is a terminal timer application packaged as `pytimer-countdown`. It supports direct command-line timers, multiple sequential timers, preset management, JSONL session logging, completion notifications, and an interactive keyboard-driven UI. The app accepts several human-friendly duration formats — compact (`5m`, `1h30m`, `500ms`), colon (`5:00`, `1:30:00`), and natural language (`5 minutes`, `ninety seconds`) — then normalizes all of them into a single `Duration` value object.

The main architectural problem was that a timer is not just a sleep loop. It has mutable real-world behavior: start, pause, resume, reset, adjust, cancel, complete, log, notify, render, and respond to keyboard input. The project needed to keep that behavior understandable while still supporting interactive terminal operation. The chosen design separates pure timing logic from terminal I/O, rendering, persistence, notifications, and CLI parsing.

---

## Decisions

### Decision 1 — Store durations as immutable total milliseconds

**Chosen:** A frozen `Duration` dataclass stores one canonical value: `total_milliseconds`.

**Rejected:** Store separate `hours`, `minutes`, `seconds`, and `milliseconds` fields.

**Reason:** A countdown timer has many input and output formats, but internally every duration should mean exactly one thing. Storing total milliseconds prevents equivalent inputs such as `30s`, `0:30`, and `thirty seconds` from becoming different internal shapes. Derived fields (`hours`, `minutes`, `seconds`, `millis`) and format styles (`hms`, `compact`, `pretty`, `ms`) are calculated from that one canonical value.

---

### Decision 2 — Parser registry over one permissive parser

**Chosen:** Three explicit parser strategies — `CompactParser`, `ColonParser`, and `NaturalParser` — selected through `ParserRegistry`.

**Rejected:** A single large parser with mixed regexes and conditionals for all duration formats.

**Reason:** Compact, colon, and natural duration syntax have different rules. Compact parsing must validate token adjacency, colon parsing must enforce minute/second bounds, and natural parsing must understand unit words and number words. Separate parser classes keep each grammar small and testable. The registry preserves a single public `parse(text)` interface while allowing config-driven parser order.

---

### Decision 3 — Explicit timer state machine

**Chosen:** `TimerStatus` plus a `LEGAL_TRANSITIONS` table define valid timer movement:
- `PENDING → RUNNING, CANCELLED`
- `RUNNING → PAUSED, COMPLETED, CANCELLED`
- `PAUSED → RUNNING, CANCELLED`
- `COMPLETED` and `CANCELLED` are terminal.

**Rejected:** Let methods freely mutate timer state without a central transition table.

**Reason:** Pause/resume/cancel/complete bugs are easy to introduce when state transitions are scattered across methods. A table makes the lifecycle visible and forces the engine to reject illegal operations such as resuming a completed timer. This is especially important because the interactive UI can receive commands at any time.

---

### Decision 4 — Immutable timer snapshots

**Chosen:** `Timer` is a frozen dataclass. State changes create updated copies through `with_changes()` and store the new value in `TimerEngine`.

**Rejected:** Mutable timer objects modified in place.

**Reason:** The app repeatedly renders timers, logs final timer states, and publishes timer events. Immutable timer snapshots make it easier to reason about what a handler received. They also make pure helper functions such as `timer_remaining()` and `remaining_time()` easier to test.

---

### Decision 5 — Injected time source

**Chosen:** `TimerEngine` depends on a `TimeSource` protocol with `SystemTimeSource` for real runtime and `FakeTimeSource` for tests.

**Rejected:** Call `time.monotonic()` directly throughout the engine.

**Reason:** A timer app must be tested without sleeping. Injecting time allows deterministic tests: fake time advances instantly, and the engine can be checked for completion, pause/resume arithmetic, and remaining time calculation without wall-clock delays. This is one of the strongest design decisions in the project.

---

### Decision 6 — Event bus for completion/cancellation side effects

**Chosen:** `TimerEngine` publishes events such as `TimerStarted`, `TimerPaused`, `TimerCompleted`, `TimerCancelled`, and `TimerTick`.

**Rejected:** Engine directly calls loggers, notifiers, and display code.

**Reason:** The engine should own timer state, not terminal side effects. Events let `TimerApp` subscribe to completion/cancellation and then call notifiers and session logging outside the timing core. This keeps engine tests focused on state transitions and keeps notification/logging policy outside the core.

---

### Decision 7 — CLI and interactive loop share the same engine

**Chosen:** `pytimer start`, `pytimer preset`, and the interactive app all create/use `TimerEngine`, `Duration`, renderers, notifiers, and `SessionLog`.

**Rejected:** Separate code paths for one-shot CLI mode versus interactive mode.

**Reason:** Multiple front ends should not mean multiple timer implementations. The CLI parses inputs and constructs timers; the app loop manages execution. This keeps direct commands, presets, and interactive operation aligned with the same state machine.

---

### Decision 8 — JSON/TOML persistence using stdlib formats

**Chosen:** Runtime files live under `~/.pytimer`: `config.toml`, `presets.json`, and `sessions.jsonl`.

**Rejected:** SQLite, YAML, or a third-party config/persistence layer.

**Reason:** The project is a CLI learning project. TOML, JSON, and JSON Lines are simple, inspectable, and sufficient for user-editable settings, named durations, and append-only session records. JSONL also makes log appends simple and resilient: each completed or cancelled timer becomes one independent line.

---

### Decision 9 — Renderer protocol and pure renderers

**Chosen:** Renderers accept `list[Timer]` and `now` and return a string. `Display` owns terminal writes.

**Rejected:** Renderers directly print, clear the screen, or read keyboard input.

**Reason:** Keeping renderers pure makes them testable and reusable. The same timer state can be rendered as a large ASCII timer, compact rows, or pipe-friendly minimal output without changing the engine. `Display` is the only module responsible for stdout redraw behavior.

---

### Decision 10 — Threaded input queue for interactive mode

**Chosen:** `TimerApp` runs a daemon input thread that reads non-blocking keys into a queue; the main loop drains keys between ticks.

**Rejected:** Blocking keyboard reads in the main loop.

**Reason:** Timers must keep ticking even when the user does not press a key. A queue separates input capture from timer progression. The main loop can tick, handle queued commands, render, and sleep at the configured tick rate.

---

## Consequences

**Positive:**
- Duration parsing is flexible without contaminating engine logic.
- Timer behavior is controlled by a visible state machine.
- Tests can exercise timing deterministically through `FakeTimeSource`.
- Renderers are pure functions and can be tested without terminal side effects.
- JSONL logging and preset persistence are simple enough for a CLI app and easy to inspect manually.
- Event bus boundaries keep notification and logging out of core timer state management.
- `pytimer 5m` works as a shortcut because CLI argument normalization injects the `start` command when appropriate.

**Negative / Trade-offs:**
- The interactive app uses a background input thread, which is more complex than a single-threaded loop.
- JSONL logs are easy to append but not ideal for large-scale querying or editing.
- Natural-language duration parsing is intentionally limited; it supports common number words but is not a general language parser.
- Desktop notifications require the optional `plyer` dependency and silently degrade when unavailable.
- Config loading assumes a valid TOML file; the project keeps config simple rather than implementing a full validation/reporting layer.

---

## Alternatives Not Explored

- **`asyncio` event loop:** Avoided to keep the project approachable. The current thread plus queue model is easier to understand for a terminal CLI.
- **Curses/Textual/Rich UI:** Rejected for scope discipline and dependency control. ANSI/string rendering is enough for the project’s learning goals.
- **SQLite history database:** Unnecessary for small personal session history. JSONL is more transparent for this scope.
- **OS-specific notification APIs:** Avoided in favor of a small strategy interface and optional `plyer` desktop notifier.
- **Cron/daemon scheduling:** Out of scope. The app is an interactive countdown timer, not a background scheduler.

---

*Constitution reference: Article 1 (Python fundamentals and architectural thinking), Article 3 (scope discipline), Article 4 (engineering quality), Article 6 (behavior verification). No authorship flags identified from the inspected repository content.*

-e 

---


# Technical Design Document
## App 33 — Countdown Timer
**Terminal Tools Group | Document 2 of 5**

---

## Overview

Countdown Timer is a small Python package exposing a `pytimer` command. It provides a duration parser, immutable timer model, timer engine, interactive terminal app, renderers, preset storage, session logs, and completion notifications.

**Package:** `pytimer`  
**CLI entry point:** `pytimer = "pytimer.cli:main"`  
**Module entry point:** `python -m pytimer`  
**Python requirement:** Python 3.11 or later  
**Core dependencies:** stdlib only  
**Optional dependency:** `plyer>=2.1` for desktop notifications  
**Development dependencies:** `pytest`, `hypothesis`, `mypy`, `ruff`

---

## System Context

```
User / Shell
   │
   ├── pytimer 5m
   ├── pytimer start 25m 5m
   ├── pytimer preset pomodoro
   ├── pytimer preset add tea 4m
   └── pytimer log --stats
        │
        ▼
pytimer.cli
        │
        ├── ParserRegistry → Duration
        ├── JSONPresetRepository
        ├── TimerEngine
        ├── TimerApp
        ├── Renderer
        ├── Notifier
        └── SessionLog
                │
                ▼
        ~/.pytimer/
          ├── config.toml
          ├── presets.json
          └── sessions.jsonl
```

The app interacts with the operating system through stdin, stdout, terminal control sequences, optional desktop notification libraries, signal handling, and files under the user’s home directory.

---

## Component Breakdown

### `src/pytimer/__init__.py`
Exports the public package surface: `Duration`, `TimerEngine`, `Timer`, `TimerStatus`, and timer-specific exceptions.

### `src/pytimer/__main__.py`
Allows `python -m pytimer` by delegating to `pytimer.cli.main()`.

### `src/pytimer/duration.py`
Defines the immutable `Duration` value object and constants:
- `MILLIS_PER_SECOND`
- `MILLIS_PER_MINUTE`
- `MILLIS_PER_HOUR`

Responsibilities:
- store canonical total milliseconds
- reject negative or non-integer internal duration values
- convert from seconds or milliseconds
- support arithmetic/comparison
- format as `hms`, `compact`, `pretty`, or raw milliseconds

### `src/pytimer/parsers.py`
Implements duration parsing strategies:
- `CompactParser`
- `ColonParser`
- `NaturalParser`
- `ParserRegistry`

Responsibilities:
- parse raw duration text into `Duration`
- combine parser strategies in configured order
- produce a helpful aggregate error when no parser accepts input

### `src/pytimer/timer.py`
Defines:
- `TimerStatus`
- `LEGAL_TRANSITIONS`
- frozen `Timer`
- pure timing helpers: `elapsed_duration`, `remaining_time`, `timer_remaining`

Responsibilities:
- model a timer’s lifecycle state
- calculate remaining countdown time
- exclude paused time from elapsed time
- clamp remaining time to zero when the timer expires

### `src/pytimer/engine.py`
Defines `TimerEngine`.

Responsibilities:
- create timers
- list/get timers
- start, pause, resume, cancel, reset, and adjust timers
- complete timers during `tick()`
- validate legal state transitions
- publish timer lifecycle events
- support injectable time sources

### `src/pytimer/events.py`
Defines event dataclasses and a small observer pattern:
- `TimerStarted`
- `TimerPaused`
- `TimerResumed`
- `TimerCompleted`
- `TimerCancelled`
- `TimerTick`
- `EventBus`

Responsibilities:
- decouple engine state changes from side effects
- allow app-level subscribers to log and notify

### `src/pytimer/time_source.py`
Defines:
- `TimeSource` protocol
- `SystemTimeSource`
- `FakeTimeSource`

Responsibilities:
- isolate monotonic time access
- support deterministic tests with fake time

### `src/pytimer/cli.py`
Defines command-line parsing and top-level dispatch.

Responsibilities:
- normalize bare duration commands into `start`
- load config and parser order
- run `start`, `preset`, and `log` subcommands
- construct engine/renderers/notifiers/session log
- return user-facing exit codes

### `src/pytimer/app.py`
Defines `TimerApp`, the interactive runtime loop.

Responsibilities:
- start the first pending timer
- handle keyboard input through an input thread and queue
- tick engine at configured rate
- render current timer state
- subscribe to completion/cancellation events
- trigger notifications and log session outcomes
- handle SIGINT/SIGTERM shutdown

### `src/pytimer/commands.py`
Defines the command pattern for interactive keybindings:
- pause/resume
- reset
- add timer
- delete/cancel timer
- adjust duration
- select next timer
- toggle help
- quit

Responsibilities:
- map keys to command objects
- mutate app UI state or call engine methods safely

### `src/pytimer/display.py`
Defines terminal I/O helpers:
- `Display`
- `raw_terminal()`
- `read_key_nonblocking()`
- `sleep_until_next_tick()`

Responsibilities:
- redraw only when output changes
- clear/hide/show cursor with ANSI sequences
- read single-key input without blocking the timer loop
- restore terminal state after raw mode

### `src/pytimer/renderers.py`
Defines output renderers:
- `BigRenderer`
- `CompactRenderer`
- `MinimalRenderer`
- `build_renderer()`

Responsibilities:
- render timers into strings
- support ANSI styling
- produce pipe-friendly minimal output
- format clocks and progress bars

### `src/pytimer/persistence.py`
Defines:
- `Config`
- `PresetRepository`
- `JSONPresetRepository`
- `InMemoryPresetRepository`
- `SessionLog`
- `SessionRecord`

Responsibilities:
- load runtime config from TOML
- create/read/update presets from JSON
- append and read JSONL session records
- calculate total session duration by label

### `src/pytimer/notifiers.py`
Defines notification strategies:
- `BellNotifier`
- `BannerNotifier`
- `DesktopNotifier`
- `CompositeNotifier`
- `NullNotifier`
- `build_notifier()`

Responsibilities:
- notify on timer completion
- support opt-out through `--no-sound`
- degrade gracefully when desktop notification dependency is missing

### `src/pytimer/errors.py`
Defines timer-specific exception hierarchy:
- `TimerError`
- `InvalidDurationError`
- `TimerNotFoundError`
- `InvalidStateTransitionError`

---

## Module Dependency Graph

```
cli
 ├── app
 │    ├── commands
 │    ├── display
 │    ├── engine
 │    ├── events
 │    ├── notifiers
 │    ├── persistence
 │    ├── renderers
 │    └── timer
 ├── engine
 ├── notifiers
 ├── parsers
 ├── persistence
 └── renderers

engine
 ├── duration
 ├── errors
 ├── events
 ├── time_source
 └── timer

timer
 └── duration

parsers
 ├── duration
 └── errors

persistence
 ├── duration
 ├── parsers
 └── timer

renderers
 ├── duration
 └── timer

commands
 ├── duration
 ├── engine
 ├── errors
 └── timer
```

Design intent: lower-level modules (`duration`, `timer`, `events`, `time_source`, `errors`) do not import CLI, display, or app code. The dependency direction flows from UI/orchestration down toward pure domain logic.

---

## Core Algorithms & Logic

### Duration parsing pipeline

1. CLI loads `Config`.
2. Config supplies `parser_order`, defaulting to `("compact", "colon", "natural")`.
3. `ParserRegistry.from_names()` builds parser strategy instances.
4. `ParserRegistry.parse(text)` tries parsers in order.
5. First successful parser returns a `Duration`.
6. If all parsers fail, registry raises `InvalidDurationError` with accepted formats and parser-specific details.

### Compact parsing

1. Strip and lowercase input.
2. Match repeated tokens using a compiled regex:
   - numeric amount
   - unit: `ms`, `h`, `m`, or `s`
3. Ensure each match begins exactly where the previous match ended.
4. Convert each token to milliseconds using unit multipliers.
5. Return `Duration(round(total))`.
6. Reject empty input, gaps, unknown units, or trailing characters.

### Colon parsing

1. Match two-part or three-part duration using `\d+(?::\d{1,2}){1,2}`.
2. Two parts mean `minutes:seconds`.
3. Three parts mean `hours:minutes:seconds`.
4. Reject minutes or seconds greater than or equal to 60.
5. Convert to milliseconds and return `Duration`.

### Natural parsing

1. Lowercase text and replace hyphens with spaces.
2. Extract alphabetic words and numeric tokens.
3. Ignore `and`.
4. Accumulate amount tokens until a recognized unit appears.
5. Parse amount tokens as digits or supported number words.
6. Multiply amount by the unit’s milliseconds.
7. Reject leftover tokens, missing amounts, or unknown number words.

### Timer lifecycle

1. `TimerEngine.add_timer()` creates a pending immutable `Timer`.
2. `TimerEngine.start()` validates `PENDING → RUNNING`, stores a new timer snapshot, and publishes `TimerStarted`.
3. `pause()` records `pause_started_at`.
4. `resume()` adds the pause interval to `paused_elapsed`.
5. `tick()` checks running timers:
   - if remaining time is zero, `_complete()` transitions to `COMPLETED`
   - publishes `TimerCompleted`
   - publishes `TimerTick`
6. `TimerApp` receives completion events and calls notifier + session log.

### Remaining time calculation

`timer_remaining(timer, now)` delegates to `remaining_time()`:

1. If timer is `PENDING`, return original duration.
2. If timer is `COMPLETED`, return zero.
3. Use `pause_started_at` as effective now when paused.
4. Use `ended_at` when terminal.
5. Calculate active elapsed seconds:
   ```
   effective_now - start_monotonic - paused_elapsed.total_seconds
   ```
6. Clamp result so remaining duration never goes below zero.

### Sequential timers

1. CLI adds every requested duration to the engine as a pending timer.
2. `TimerApp.run()` calls `_start_next_pending_if_idle()` before loop and after every tick.
3. If no timer is running or paused, the first pending timer is started.
4. When the active timer completes, the next pending timer starts on the next loop cycle.
5. This creates sequential behavior without a separate queue type.

---

## Data Structures

### `Duration`
```python
Duration(total_milliseconds: int)
```
Immutable value object. Every duration in the app normalizes to this type.

### `Timer`
```python
Timer(
    id: str,
    label: str,
    original_duration: Duration,
    created_at: float,
    status: TimerStatus,
    start_monotonic: float | None,
    pause_started_at: float | None,
    paused_elapsed: Duration,
    ended_at: float | None,
)
```

### `TimerEngine._timers`
```python
dict[str, Timer]
```
Stores timer snapshots by generated or supplied timer ID.

### `LEGAL_TRANSITIONS`
```python
dict[TimerStatus, set[TimerStatus]]
```
Central state-machine table.

### `Config`
```python
Config(
    tick_rate_hz: float = 10.0,
    renderer: str = "big",
    notifiers: tuple[str, ...] = ("bell",),
    color_scheme: str = "default",
    parser_order: tuple[str, ...] = ("compact", "colon", "natural"),
    bell_volume: float = 1.0,
)
```

### `SessionRecord`
```python
SessionRecord(
    label: str,
    duration: Duration,
    status: TimerStatus,
    completed_at: datetime,
)
```

### JSONL log line
```json
{
  "completed_at": "2026-04-21T12:00:00+00:00",
  "duration": "5s",
  "duration_ms": 5000,
  "label": "tea",
  "status": "completed"
}
```

### Presets JSON
```json
{
  "pomodoro": "25m",
  "standup": "15m",
  "tea": "4m"
}
```

---

## State Management

### In-memory state
- `TimerEngine._timers`
- `TimerApp.state`
- keyboard queue
- current time source
- event subscriptions

### File-based state
- `~/.pytimer/config.toml`
- `~/.pytimer/presets.json`
- `~/.pytimer/sessions.jsonl`

### Environment variables
No first-class environment-variable configuration was identified in the inspected source.

---

## Error Handling Strategy

- `InvalidDurationError` signals invalid input text, invalid duration arithmetic, or invalid preset usage.
- `TimerNotFoundError` signals unknown timer IDs.
- `InvalidStateTransitionError` signals illegal lifecycle operations.
- CLI catches `InvalidDurationError` and `KeyError`, prints `pytimer: ...` to stderr, and returns exit code 2.
- Interactive commands swallow some invalid operations to avoid crashing the UI when a user presses keys at awkward times.
- Notifier failure for desktop notifications degrades by logging a warning when `plyer` is unavailable.
- `Display` catches `UnicodeEncodeError` and writes replacement characters rather than crashing on unsupported output encodings.

---

## External Dependencies

### Runtime
None required for the core package.

### Optional
- `plyer>=2.1` — desktop notifications.

### Development
- `pytest>=8.0`
- `hypothesis>=6.100`
- `mypy>=1.8`
- `ruff>=0.6`

---

## Concurrency Model

The core engine is synchronous. The interactive app uses one background daemon thread for keyboard input:

- main thread: tick engine, handle queued keys, render, sleep
- input thread: poll keys and push them into a queue
- synchronization: `queue.Queue` for key transfer; `threading.Event` for stopping input thread

The engine itself does not attempt internal locking. It is used from the main app loop, while the input thread only enqueues keys.

---

## Known Limitations

- Natural language parsing is intentionally limited to supported number words and units.
- JSONL logs can grow indefinitely unless manually rotated or deleted.
- `bell_volume` exists in config but the inspected bell notifier only emits the terminal bell; no volume scaling is applied.
- Desktop notifications depend on optional `plyer` and operating-system support.
- The interactive UI is terminal-dependent and may behave differently across shells.
- There is no full config validation/error reporting layer beyond simple field loading.
- There is no persistent queue/resume feature for interrupted active timers.
- Timer IDs are generated UUID hex strings and are not exposed as a friendly short command interface.

---

## Design Patterns Used

| Pattern | Location | Purpose |
|---|---|---|
| Value Object | `Duration` | Canonical immutable time duration |
| State Machine | `TimerStatus` + `LEGAL_TRANSITIONS` | Controlled timer lifecycle |
| Strategy | duration parsers, renderers, notifiers | Swap behavior behind small interfaces |
| Observer | `EventBus` | Decouple engine events from log/notify side effects |
| Command | interactive keybinding classes | Encapsulate key actions |
| Repository | preset repository classes | Abstract preset storage |
| Dependency Injection | `TimeSource`, `Renderer`, `Notifier`, `SessionLog` | Testability and replaceable behavior |
| Pure Function Boundary | `timer_remaining`, renderers | Easier testing and lower side effects |

-e 

---


# Interface Design Specification
## App 33 — Countdown Timer
**Terminal Tools Group | Document 3 of 5**

---

## Invocation Syntax

### Installed command

```bash
pytimer [GLOBAL_OPTIONS] <duration>
pytimer [GLOBAL_OPTIONS] start <duration> [duration ...] [--label LABEL]
pytimer [GLOBAL_OPTIONS] preset [list]
pytimer [GLOBAL_OPTIONS] preset add <name> <duration>
pytimer [GLOBAL_OPTIONS] preset remove <name>
pytimer [GLOBAL_OPTIONS] preset <name>
pytimer [GLOBAL_OPTIONS] log [--last N]
pytimer [GLOBAL_OPTIONS] log --stats
```

### Module command

```bash
python -m pytimer start 5m
```

### Bare duration shortcut

```bash
pytimer 5m
```

The CLI normalizes the first non-option positional argument into `start` when it is not already `start`, `preset`, or `log`.

---

## Global Options

| Name | Type | Required | Default | Accepted Values | Description |
|---|---:|---:|---:|---|---|
| `--no-sound` | bool | No | `False` | present/absent | Disable completion notifications |
| `--minimal` | bool | No | `False` | present/absent | Use pipe-friendly minimal renderer |
| `--no-color` | bool | No | `False` | present/absent | Disable ANSI color output |
| `--data-dir` | path | No | `~/.pytimer` | filesystem path | Hidden/testing option that overrides runtime data directory |

---

## Command Reference

### `start`

```bash
pytimer start <duration> [duration ...] [--label LABEL]
```

| Argument | Type | Required | Default | Valid Values | Description |
|---|---:|---:|---:|---|---|
| `durations` | list[str] | Yes | — | duration text | One or more durations to run sequentially |
| `--label` | str | No | formatted duration | any string | Label for timer display/logging |

If multiple durations are supplied with one label, the implementation appends the timer index to labels, such as `focus 1`, `focus 2`.

### `preset`

```bash
pytimer preset
pytimer preset list
pytimer preset add <name> <duration>
pytimer preset remove <name>
pytimer preset <name>
```

| Argument | Type | Required | Default | Valid Values | Description |
|---|---:|---:|---:|---|---|
| `action` | str | No | `list` | `list`, `add`, `remove`, or preset name | Preset operation |
| `values` | list[str] | Depends | — | preset args | Arguments for add/remove/run |

Default presets created on first use:
- `pomodoro`: `25m`
- `tea`: `4m`
- `standup`: `15m`

### `log`

```bash
pytimer log --last 10
pytimer log --stats
```

| Argument | Type | Required | Default | Valid Values | Description |
|---|---:|---:|---:|---|---|
| `--last` | int | No | `10` | positive integer expected | Number of recent log rows to print |
| `--stats` | bool | No | `False` | present/absent | Print total logged time grouped by label |

---

## Duration Input Contract

Accepted duration formats:

### Compact

```text
5m
1h30m
90s
2h15m30s
500ms
```

Rules:
- Units: `h`, `m`, `s`, `ms`
- Numeric values can be integers or decimals
- Tokens must be adjacent with no unparsed gaps
- Negative durations are rejected

### Colon

```text
5:00
1:30:00
00:00:10
```

Rules:
- Two-part format means `minutes:seconds`
- Three-part format means `hours:minutes:seconds`
- Minutes and seconds must be less than 60

### Natural

```text
5 minutes
1 hour 30 min
ninety seconds
```

Rules:
- Supported unit words include hour(s), hr(s), minute(s), min(s), second(s), sec(s), millisecond(s), milli(s)
- Supports digits and common English number words from zero through ninety, plus hundred composition
- Hyphens are treated as spaces
- `and` is ignored

---

## Output Contract

### Interactive renderer output

The default renderer displays:
- active timer label
- status
- remaining time
- large ASCII clock
- progress bar
- other timers, if present

### Compact renderer output

One line per timer, including short timer ID, label, status, remaining time, and progress.

### Minimal renderer output

Pipe-friendly format:

```text
<timer_id>|<label>|<status>|<remaining_milliseconds>
```

Example:

```text
abc123...|tea|pending|5000
```

### Preset list output

```text
pomodoro         25m
standup          15m
tea              4m
```

### Log output

Recent logs:

```text
2026-04-21 12:00:00  completed  tea                      5 seconds
```

Stats:

```text
tea                      5 seconds
```

---

## Exit Code Reference

| Exit Code | Condition |
|---:|---|
| `0` | Successful command or normal interactive completion |
| `2` | Invalid duration input or preset/key lookup error caught by CLI |
| Nonzero from shell/runtime | Unhandled OS/runtime failure outside expected app errors |

---

## Error Output Behavior

CLI user errors are printed to stderr as:

```text
pytimer: <message>
```

Examples:
```text
pytimer: Could not parse 'tomorrow'. Accepted formats: compact (5m, 1h30m, 500ms), colon (5:00, 1:30:00), natural (5 minutes). Details: ...
pytimer: 'Unknown preset: focus'
```

The interactive app avoids crashing for many command-time invalid transitions by ignoring invalid key operations.

---

## Environment Variables

No app-specific environment variables were identified in the inspected source.

---

## Configuration Files

### Config file path

```text
~/.pytimer/config.toml
```

### Supported keys

```toml
tick_rate_hz = 10.0
renderer = "big"
notifiers = ["bell"]
color_scheme = "default"
parser_order = ["compact", "colon", "natural"]
bell_volume = 1.0
```

### Effective precedence

1. CLI flags where implemented (`--minimal`, `--no-color`, `--no-sound`, `--data-dir`)
2. Config file settings
3. Hardcoded defaults

---

## Preset File

### Path

```text
~/.pytimer/presets.json
```

### Shape

```json
{
  "pomodoro": "25m",
  "tea": "4m",
  "standup": "15m"
}
```

Presets are stored as duration strings and parsed through `ParserRegistry`.

---

## Session Log File

### Path

```text
~/.pytimer/sessions.jsonl
```

### Shape

```json
{"completed_at":"2026-04-21T12:00:00+00:00","duration":"5s","duration_ms":5000,"label":"tea","status":"completed"}
```

Each completed or cancelled timer appends one line.

---

## Side Effects

| Operation | Side Effect |
|---|---|
| `pytimer start ...` | Runs interactive terminal UI; appends completion/cancellation records |
| `pytimer preset add ...` | Creates/updates `presets.json` |
| `pytimer preset remove ...` | Updates `presets.json` |
| First preset access | Creates default `presets.json` if missing |
| Timer completion | Emits configured notifier(s), appends JSONL log |
| Timer cancellation / quit | Appends cancellation log for open timers |
| `pytimer log` | Reads `sessions.jsonl` |
| Interactive display | Writes ANSI terminal control sequences unless disabled/minimal |

---

## Interactive Keybindings

| Key | Action |
|---|---|
| `p` | Pause/resume active timer |
| `r` | Reset active timer |
| `a` | Add a 5-minute timer |
| `d` | Cancel active timer |
| `+` | Add 30 seconds |
| `-` | Subtract 30 seconds |
| `n` | Select next timer |
| `?` | Toggle help |
| `q` | Quit |

---

## Usage Examples

### Basic timer

```bash
pytimer 5m
```

### Explicit start command

```bash
pytimer start 5m --label tea
```

### Sequential Pomodoro-style timers

```bash
pytimer start 25m 5m 25m 5m --label focus
```

### Add and run a preset

```bash
pytimer preset add stretch 10m
pytimer preset stretch
```

### List presets

```bash
pytimer preset list
```

### Show last 10 log records

```bash
pytimer log --last 10
```

### Show aggregate time by label

```bash
pytimer log --stats
```

### Pipe-friendly output

```bash
pytimer --minimal start 5m
```

### Intentional failure

```bash
pytimer start tomorrow
```

Expected behavior: prints an invalid duration message to stderr and exits with code 2.

-e 

---


# Runbook
## App 33 — Countdown Timer
**Terminal Tools Group | Document 4 of 5**

---

## Prerequisites

- Python 3.11 or later
- Terminal capable of basic ANSI display for full UI
- Windows, macOS, or Linux shell
- Optional: `plyer` for desktop notifications

---

## Installation Procedure

### Development install

```bash
git clone https://github.com/PrincetonAfeez/Countdown-Timer.git
cd Countdown-Timer
python -m pip install -e ".[dev]"
```

### Runtime install without dev tools

```bash
python -m pip install -e .
```

### Runtime install with desktop notifications

```bash
python -m pip install -e ".[desktop]"
```

---

## Configuration Steps

### Create config directory

The app uses:

```text
~/.pytimer
```

It can create preset/log paths as needed, but you can create it manually:

```bash
mkdir -p ~/.pytimer
```

### Optional config file

Create:

```text
~/.pytimer/config.toml
```

Example:

```toml
tick_rate_hz = 10.0
renderer = "big"
notifiers = ["bell"]
parser_order = ["compact", "colon", "natural"]
```

If the config file is missing, built-in defaults are used.

---

## Standard Operating Procedures

### Start a simple timer

```bash
pytimer 5m
```

### Start with an explicit label

```bash
pytimer start 4m --label tea
```

### Start multiple sequential timers

```bash
pytimer start 25m 5m 25m 5m --label pomodoro
```

### Pause/resume during timer

Press:

```text
p
```

### Reset active timer

Press:

```text
r
```

### Add a quick 5-minute timer

Press:

```text
a
```

### Adjust the active timer

```text
+    add 30 seconds
-    subtract 30 seconds
```

### Cancel active timer

Press:

```text
d
```

### Quit the app

Press:

```text
q
```

Open timers are cancelled before shutdown.

---

## Preset Operations

### List presets

```bash
pytimer preset list
```

### Add preset

```bash
pytimer preset add stretch 10m
```

### Remove preset

```bash
pytimer preset remove stretch
```

### Run preset

```bash
pytimer preset pomodoro
```

Default presets are created on first repository access:
- `pomodoro`
- `tea`
- `standup`

---

## Log Operations

### Show recent log records

```bash
pytimer log --last 10
```

### Show aggregate time by label

```bash
pytimer log --stats
```

### Inspect raw log

```bash
cat ~/.pytimer/sessions.jsonl
```

Each row is a JSON object.

---

## Health Checks

### Verify package imports

```bash
python -c "import pytimer; print(pytimer.Duration.from_seconds(5))"
```

Expected: no traceback.

### Verify CLI entry point

```bash
pytimer --help
```

Expected: command help output.

### Verify parser behavior

```bash
python - <<'PY'
from pytimer.parsers import ParserRegistry
print(ParserRegistry().parse("1h30m").total_milliseconds)
print(ParserRegistry().parse("1:30:00").total_milliseconds)
print(ParserRegistry().parse("ninety seconds").total_milliseconds)
PY
```

Expected:
```text
5400000
5400000
90000
```

### Verify deterministic engine behavior

```bash
python - <<'PY'
from pytimer.duration import Duration
from pytimer.engine import TimerEngine
from pytimer.time_source import FakeTimeSource

clock = FakeTimeSource()
engine = TimerEngine(time_source=clock)
timer = engine.add_timer(Duration.from_seconds(2), label="test")
engine.start(timer.id)
clock.advance(2)
print(engine.tick()[0].status.value)
PY
```

Expected:
```text
completed
```

---

## Expected Output Samples

### Minimal renderer

```text
<timer_id>|tea|pending|5000
```

### Preset list

```text
pomodoro         25m
standup          15m
tea              4m
```

### Log row

```text
2026-04-21 12:00:00  completed  tea                      5 seconds
```

---

## Known Failure Modes

| Symptom | Probable Cause | Diagnostic Step | Resolution |
|---|---|---|---|
| `pytimer: Could not parse ...` | Invalid duration format | Try `5m`, `5:00`, or `5 minutes` | Re-enter duration in supported format |
| `pytimer: Unknown preset ...` | Preset name does not exist | Run `pytimer preset list` | Add preset or use correct name |
| Timer display does not update | Non-interactive/limited terminal | Try `--minimal` | Use minimal output or compatible terminal |
| Desktop notification does not appear | `plyer` missing or OS unsupported | Install desktop extra | `python -m pip install -e ".[desktop]"` |
| Bell notification unwanted | Terminal bell enabled | Use `--no-sound` | Run with `pytimer --no-sound start 5m` |
| Unicode progress bar looks wrong | Terminal encoding/font issue | Try minimal renderer | Use `--minimal` or terminal with Unicode support |
| App exits but timers logged as cancelled | User quit before completion | Check `sessions.jsonl` status | Expected behavior on quit |
| Presets file corrupted | Invalid JSON in `presets.json` | Open file manually | Fix/delete `~/.pytimer/presets.json` |

---

## Troubleshooting Decision Tree

```text
Problem starting timer?
├── Does `pytimer --help` work?
│   ├── No → reinstall package with `python -m pip install -e .`
│   └── Yes
│       └── Is duration valid?
│           ├── No → use compact, colon, or natural format
│           └── Yes → check terminal support
│
Problem with preset?
├── Run `pytimer preset list`
│   ├── Preset missing → add it with `pytimer preset add <name> <duration>`
│   └── Preset present → inspect `~/.pytimer/presets.json`
│
Problem with logs?
├── Does `~/.pytimer/sessions.jsonl` exist?
│   ├── No → no completed/cancelled timers have been logged yet
│   └── Yes → run `pytimer log --last 10`
│
Problem with notification?
├── Using `--no-sound`?
│   ├── Yes → notifications intentionally disabled
│   └── No
│       └── Desktop notification configured?
│           ├── Yes → install `[desktop]` extra / check OS permissions
│           └── No → bell notification should be terminal-dependent
```

---

## Dependency Failure Handling

### Missing optional desktop dependency

The desktop notifier catches `ImportError`, logs a warning once, and returns without crashing. Use the `desktop` extra to enable it:

```bash
python -m pip install -e ".[desktop]"
```

### Missing config file

`Config.load()` returns defaults.

### Missing presets file

`JSONPresetRepository` creates default presets.

### Missing sessions log

`SessionLog.recent()` returns an empty list; `log --stats` prints nothing.

---

## Recovery Procedures

### Reset presets to defaults

```bash
rm ~/.pytimer/presets.json
pytimer preset list
```

The repository will recreate defaults.

### Clear session history

```bash
rm ~/.pytimer/sessions.jsonl
```

### Disable all notifications

```bash
pytimer --no-sound start 5m
```

### Use pipe-friendly mode in unsupported terminals

```bash
pytimer --minimal start 5m
```

### Recover from a broken config

```bash
mv ~/.pytimer/config.toml ~/.pytimer/config.toml.bak
pytimer 5m
```

---

## Running Tests

```bash
python -m pytest
```

Expected coverage areas from the inspected tests:
- duration arithmetic and formatting
- parser accepted/rejected inputs
- engine state transitions
- pause/resume elapsed-time arithmetic
- completion events
- fake time source behavior
- preset repository defaults and updates
- session log recent/stats behavior
- renderer string output and minimal format

### Static checks

```bash
python -m ruff check .
python -m mypy src/pytimer
```

---

## Maintenance Notes

- Watch for unbounded growth in `~/.pytimer/sessions.jsonl`.
- Keep natural-language parsing intentionally limited unless there is a clear requirement.
- If adding more notifiers, preserve the notifier strategy interface.
- If adding more renderers, keep them pure: state in, string out.
- If adding persistence beyond presets/logs, consider whether JSON/TOML still remains adequate.
- Any change to timer state transitions should update `LEGAL_TRANSITIONS` and engine tests together.

-e 

---


# Lessons Learned
## App 33 — Countdown Timer
**Terminal Tools Group | Document 5 of 5**

---

## Project Summary

Countdown Timer is a terminal countdown timer packaged as `pytimer`. It accepts compact, colon, and natural duration inputs; runs one or more sequential timers; supports presets; logs completed and cancelled sessions to JSONL; notifies on completion; and provides an interactive keyboard-driven terminal UI. The project is more than a sleep loop: it is a small event-driven terminal application with a real state machine, persistence boundaries, rendering strategies, and deterministic timer tests.

---

## Original Goals vs. Actual Outcome

**Original goal:** Build a command-line countdown timer that can parse friendly time inputs and run timers in the terminal.

**Actual outcome:** The app grew into a well-structured Python package with:
- multiple duration parser strategies
- canonical `Duration` value object
- explicit timer lifecycle state machine
- injected time source for deterministic tests
- event bus
- interactive keyboard UI
- renderers
- notifiers
- presets
- JSONL logs
- development tooling through pytest, ruff, and mypy

The outcome is larger than a beginner script, but the features are coherent around one central product: terminal countdown timing.

---

## Technical Decisions That Paid Off

### Canonical duration representation

Using total milliseconds as the only stored value simplified the whole app. Parser strategies can be different, but the rest of the system receives the same `Duration` type.

### Time source injection

This is the strongest testing decision. `FakeTimeSource` made it possible to test timers without `sleep()`, including completion, pause/resume arithmetic, and remaining time.

### Explicit state transitions

The `LEGAL_TRANSITIONS` table turned timer behavior into a visible rule set. This reduced ambiguity around whether a timer can resume, cancel, complete, or adjust.

### Pure renderers

Renderers returning strings made display tests simple. The renderer does not need terminal state to prove it works.

### Event bus boundary

Timer completion and cancellation are engine events. The engine does not need to know about notification or session logging details.

---

## Technical Decisions That Created Debt

### Input thread in interactive app

The thread-and-queue approach solves non-blocking input but introduces lifecycle complexity:
- thread start/stop
- signal restoration
- queue draining
- terminal cleanup

It is appropriate for this project, but it is still a complexity cost.

### JSONL log without rotation

Appending one line per session is simple, but the log can grow forever. That is acceptable for a learning CLI, but a long-lived tool would need rotation or cleanup commands.

### Limited natural-language parser

The natural parser is intentionally hand-built. It supports common cases but not arbitrary language. If users expect phrases like “half an hour” or “1.5 hours” in natural mode, the parser would need expansion.

### Config field not fully wired

`bell_volume` exists in config, but the inspected notifier implementation does not apply volume control. This is minor but should either be implemented or removed.

---

## What Was Harder Than Expected

### Pause/resume time arithmetic

A countdown timer must exclude paused time. That required tracking `start_monotonic`, `pause_started_at`, and accumulated `paused_elapsed`, then carefully choosing effective time for running, paused, and ended timers.

### Interactive terminal control

Terminal UI requires careful cleanup: hide/show cursor, raw mode, signal handling, non-blocking input, and redraw behavior. This is significantly more complex than printing output once.

### Natural duration parsing

Compact and colon formats are straightforward. Natural language introduces tokenization, number words, unit aliases, and error handling.

### Sequential timers

Sequential timers sound simple, but the engine still stores multiple timers while the app has to detect when no timer is running or paused and then start the next pending timer.

---

## What Was Easier Than Expected

### Presets

A JSON file is enough for named durations. The repository abstraction makes it easy to add/list/remove presets without a database.

### Session logs

JSONL is a good fit for append-only event history. Each log entry is independent and readable.

### Renderer selection

Once renderers were kept pure, adding `big`, `compact`, and `minimal` output was straightforward.

---

## Python-Specific Learnings

- `dataclass(frozen=True)` is useful for value objects and timer snapshots.
- `typing.Protocol` can express replaceable dependencies like `TimeSource` and `Notifier`.
- `contextlib.contextmanager` is appropriate for raw terminal setup/cleanup.
- `queue.Queue` cleanly separates producer/consumer behavior between input thread and main loop.
- `time.monotonic()` is the right time base for elapsed timer logic.
- `tomllib` supports stdlib TOML reads in Python 3.11.
- JSON Lines are easy to implement with one append per record.
- `Enum` makes timer statuses explicit and readable.

---

## Architecture Insights

The main architectural insight is that a countdown timer has multiple concerns that should not be merged:

- **duration parsing** answers “what duration did the user mean?”
- **timer engine** answers “what state is each timer in?”
- **time source** answers “what time is it?”
- **commands** answer “what should this key do?”
- **renderer** answers “how should state look?”
- **display** answers “how is text written to the terminal?”
- **persistence** answers “what survives after the process exits?”
- **notifier** answers “how should completion be announced?”

The architecture is strongest where each module owns only one of these questions.

---

## Testing Gaps

The inspected tests cover core behavior well, especially:
- duration arithmetic
- accepted/rejected duration parsing
- state transitions
- pause/resume remaining time
- completion events
- preset persistence
- session logging
- renderer outputs

Likely gaps:
- full interactive loop behavior with real keyboard input
- signal handling behavior
- malformed TOML config handling
- desktop notification behavior
- long-running log growth
- terminal behavior across Windows/macOS/Linux shells
- multi-timer sequential behavior at the application loop level

These gaps are understandable because terminal I/O and OS notifications are harder to test reliably than pure domain logic.

---

## Reusable Patterns Identified

- **Canonical value object:** normalize messy user input into one internal type.
- **Strategy registry:** support multiple parsing/rendering/notification implementations without one giant conditional.
- **Time source injection:** make time-dependent code deterministic.
- **State transition table:** make lifecycle rules visible.
- **Event bus:** publish domain events and handle side effects outside the core engine.
- **Pure renderer:** return strings instead of writing directly.
- **Append-only JSONL log:** simple durable history for CLI tools.
- **Command objects for keybindings:** map UI actions to small classes.

---

## If I Built This Again

1. **Add app-level tests for sequential timers.**  
   The engine is tested well, but the app loop’s “start next pending timer” behavior deserves direct tests.

2. **Add log maintenance commands.**  
   A `pytimer log clear` or `pytimer log prune --days N` command would prevent unbounded log growth.

3. **Validate config more explicitly.**  
   Bad renderer names, unsupported notifier names, or invalid tick rates should produce clearer user-facing messages.

4. **Unify runtime config and CLI options.**  
   Some config fields, such as `color_scheme` and `bell_volume`, are present but not strongly surfaced through behavior.

---

## Open Questions

- Should cancelled timers count toward `log --stats`, or should stats default to completed timers only?
- Should presets support sequences of durations, such as a full Pomodoro cycle?
- Should natural-language parsing support fractional expressions like `1.5 hours` or phrases like `half an hour`?
- Should the app preserve active timer state across process restarts?
- Should there be a non-interactive mode that blocks quietly and exits without terminal UI?
- Should `bell_volume` be implemented, removed, or documented as reserved?

---

## Constitution Checklist

- **Article 1 — Python fundamentals and architecture:** Strong pass. The app demonstrates dataclasses, protocols, enums, parser strategies, event handling, and package organization.
- **Article 3 — Scope discipline:** Pass with note. This is larger than a tiny CLI, but appropriate for a later roadmap app because all features serve the countdown timer domain.
- **Article 4 — Engineering quality:** Strong pass. Domain logic, UI, persistence, rendering, notification, and parsing are separated.
- **Article 5 — Trade-offs:** Satisfied here through explicit discussion of parser limitations, threading cost, and JSONL persistence.
- **Article 6 — Verification:** Satisfied by tests for duration, parsing, engine transitions, persistence, and rendering.
- **Article 8 — Final evaluation standard:** Valid learner work: intentional, understandable, verifiable, and reflective.

-e
