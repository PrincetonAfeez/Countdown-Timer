# Architecture

## Injected Monotonic Time

Timers use `time.monotonic()` through a `TimeSource` protocol instead of wall
clock time. Wall clocks can move because of user changes, NTP corrections, or
DST. Monotonic time only moves forward, which is exactly what a countdown needs.

The engine receives its `TimeSource` through constructor injection. Production
uses `SystemTimeSource`; tests use `FakeTimeSource`, which can be advanced
manually. That is why pause/resume and completion tests run instantly and never
depend on `sleep()`.

## Remaining Time Is Pure

There is no mutable `remaining` field on `Timer`. Remaining time is derived from
the original duration, start timestamp, accumulated paused duration, current
timestamp, and status.

That single choice removes a common source of countdown bugs. Pausing for thirty
seconds does not require decrementing or restoring a stored value. Resuming only
adds the pause interval to `paused_elapsed`, and the same pure calculation keeps
working afterward.

## Events Decouple Side Effects

The engine publishes events such as `TimerStarted`, `TimerTick`, and
`TimerCompleted` through a tiny `EventBus`. The renderer can react to ticks, the
notifier can react to completion, and the session log can append history without
those pieces calling each other directly.

That keeps the state machine small and testable. Adding a new completion side
effect means subscribing to `TimerCompleted`, not changing the transition code.

