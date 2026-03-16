---
title: Debugging Guide
description: >-
  Comprehensive asyncio debugging reference — debug mode internals, slow
  callback detection, blocked loop diagnosis, task leak hunting, deadlock
  analysis, and timeout failure investigation.
---

# Debugging Guide

The [Debugging](../the-basics/debugging.md) section in
[The Basics](../the-basics/index.md) covers the most common async mistakes.
This appendix is the full reference --
it goes deeper on debug mode and adds diagnostic techniques for problems that
show up in larger programs: blocked loops, task leaks, deadlocks, and timeout
failures that make you question your understanding of time itself.

## Debug Mode -- the Full Picture

You already know the basics: pass `#!py debug=True` to
[`asyncio.run()`][asyncio-run],
or set `PYTHONASYNCIODEBUG=1` in the environment. Here is a deeper look at
what debug mode actually does and how to tune it.

If the program is already running, you can still enable debug mode for the
current loop:

```python
loop = asyncio.get_running_loop()
loop.set_debug(True)
```

This only affects that loop from this point onward. It cannot retroactively add
creation-site tracebacks to tasks that already exist, and it cannot warn about
problems that already happened before you enabled it. If you want the fullest
diagnostics, turn it on at startup with `#!py asyncio.run(debug=True)` or
`PYTHONASYNCIODEBUG=1`.

That limitation does not make runtime enabling useless. During a production
incident, it can be a practical compromise: turn it on temporarily, gather slow
callback warnings, task creation tracebacks for newly spawned tasks, and new
resource warnings, then turn it back off once you have enough signal. This is
especially useful when restarting the process would hide the problem or cost too
much.

### What It Detects

When active, debug mode enables several runtime checks:

- **Slow callbacks.** Any callback or coroutine step that blocks the loop for
  more than a threshold (default: 100 ms) gets a warning with a traceback.
- **Unawaited coroutines.** Coroutine objects created but never awaited
  produce a warning with the creation-site traceback -- louder than the
  default [`RuntimeWarning`][runtimewarning] from the garbage collector.
- **Unclosed resources.** Transports, event loops, and other asyncio objects
  garbage-collected without being closed generate resource warnings.
- **Better task tracebacks.** Every
  [`Task`][task]
  stores the traceback of the code that created it. When something goes wrong,
  you see not just where the exception was raised but where the task was
  spawned.

### Trade-Offs

Debug mode is instrumentation. It makes async programs easier to inspect, but
it is not free:

- **More bookkeeping.** Asyncio stores extra traceback and scheduling metadata
  so it can tell you where tasks and coroutines came from.
- **More logging and warnings.** Slow callback reports, resource warnings, and
  other diagnostics can add a lot of output in a busy process.
- **Some runtime overhead.** The extra checks and metadata usually make little
  difference in local development, but they can matter in high-throughput or
  latency-sensitive services.
- **Stricter behavior.** Some mistakes that pass silently in normal mode fail
  loudly in debug mode. That is usually what you want while debugging, but it
  can surprise you if you turn it on everywhere without expecting new errors.

That is why debug mode is best treated as a development aid, not as a default
production setting.

### Recommended Usage

Think in terms of signal versus cost. Debug mode is most useful when you are
actively trying to understand async behavior and can tolerate extra warnings,
tracebacks, and overhead. It is less attractive when steady-state performance
and log clarity matter more than extra diagnostics.

Use it by default in situations like these:

- local development
- test runs or manual verification while you are changing async code
- reproducing a bug that only shows up under load or after long runtimes
- staging environments where the extra logging is acceptable
- temporary incident investigation in production, especially when restarting
  would hide the bug or cost too much

Start with it off, and enable it only deliberately, in situations like these:

- high-throughput production services
- latency-sensitive request paths
- environments with very tight memory budgets
- production systems where the extra warnings would drown out useful logs

These are heuristics, not hard rules. If you have measured the overhead and
log volume, and the diagnostics are worth the cost, you can leave it on in
production. But make that a deliberate choice.

If you enable it temporarily at runtime during an incident, remember that it
only helps from that point onward.

### Tuning the Slow Callback Threshold

The default 100 ms threshold is reasonable for development, but you can
tighten it. Adjust it through the loop's
[`slow_callback_duration`][slow-callback-duration]
attribute:

```python
import asyncio

async def main() -> None:
    loop = asyncio.get_running_loop()
    loop.slow_callback_duration = 0.05  # Warn after 50 ms instead of 100 ms

    # ... rest of your program ...

if __name__ == "__main__":
    asyncio.run(main(), debug=True)
```

!!! Tip

    In staging, set the threshold to something slightly below your latency
    budget. If your SLA is 200 ms end-to-end, warning at 50 ms gives you
    early notice before a single slow callback eats your entire budget.

## Diagnosing a Blocked Loop

**Symptoms:** Tasks stop making progress. Heartbeats miss. Timeouts don't fire
on time. Your async server stops responding, then catches up in a burst.

**Cause:** A blocking call is running directly in a coroutine. While it
executes, nothing else can run -- the event loop is single-threaded. Common
culprits: `#!py time.sleep()`, synchronous HTTP libraries like `requests`, heavy
computation, synchronous file I/O.

**Diagnosis:**

1. **Enable debug mode.** When the loop is blocked for more than
   [`slow_callback_duration`][slow-callback-duration], you get a log message like:

   ```text
   Executing <Task name='my_task' ...> took 2.015 seconds
   ```

   The traceback points to the coroutine that held the loop.

2. **Lower the threshold** if 100 ms is too coarse. A 50 ms or 20 ms threshold
   catches subtler stalls.

3. **Look for the absence of [`await`][await].** The blocking call will be a plain
   function call:

   ```python
   # These block the loop:
   time.sleep(1)
   response = requests.get(url)
   data = open("big_file.bin").read()
   ```

**Fix:** Replace the blocking call with a non-blocking equivalent, or offload
it to a thread. See [Offloading Blocking
Work](../beyond-the-basics/offloading-blocking-work.md) for the full treatment.

```python
await asyncio.sleep(1)                                      # not time.sleep()
response = await asyncio.to_thread(requests.get, url)       # sync I/O -> thread
data = await asyncio.to_thread(Path("big_file.bin").read_bytes)

loop = asyncio.get_running_loop()                           # CPU-bound -> process
with ProcessPoolExecutor() as pool:
    result = await loop.run_in_executor(pool, expensive_computation, payload)
```

!!! Note

    Debug mode warns *after* the blocking call completes. It cannot
    interrupt the call or prevent the freeze. The only real fix is to not
    block the loop.

## Diagnosing Task Leaks

**Symptoms:** You see `#!py "Task was destroyed but it is pending"` warnings.
Memory usage grows over time. Exceptions go unreported.

**Cause:** Tasks were created with
[`create_task()`][create-task]
but never awaited, or tasks outlive the scope they were meant to run in -- the
"fire-and-forget" problem from
[Concurrent Tasks](../the-basics/concurrent-tasks.md).

**Diagnosis:**

Use [`asyncio.all_tasks()`][asyncio-all-tasks]
to inspect what is currently running:

```python
async def check_tasks() -> None:
    for task in asyncio.all_tasks():
        print(f"  {task.get_name()}: {task.get_coro()}")
```

If you see tasks that should have finished, you have a leak. The task name and
coroutine tell you what it is; debug mode's creation-site tracebacks tell you
where it was spawned.

**Fix:** Use
[`TaskGroup`][taskgroup]
instead of bare [`create_task()`][create-task]. The group ensures every child is awaited
before the scope exits:

```python
# Before: task leak risk
task = asyncio.create_task(do_work())
# If an exception happens here, task is abandoned

# After: no leak possible
async with asyncio.TaskGroup() as tg:
    tg.create_task(do_work())
# Task is guaranteed complete (or cancelled) here
```

If you genuinely need a long-lived background task that outlives any single
scope, give it a name and ensure something cancels it during shutdown. But
question whether you really need that -- most of the time a [`TaskGroup`][taskgroup] with
the right lifetime is a better fit.

## Diagnosing a Cancelled Timeout

**Symptoms:** A timeout doesn't fire. Code runs well past its deadline.
[`asyncio.timeout()`][asyncio-timeout]
appears to have no effect.

**Cause:** Something inside the timeout block is catching [`CancelledError`][cancellederror]
and suppressing it. When the timeout fires, it injects a [`CancelledError`][cancellederror] at
the next checkpoint. If that error is caught and not re-raised, the `async
with` block never sees the cancellation, so it never raises `TimeoutError`.

**Diagnosis:**

Add logging around any `#!py except CancelledError` or `#!py except BaseException`
handlers inside the timeout scope:

```python
async def suspicious_operation() -> str:
    try:
        await asyncio.sleep(10)
        return "done"
    except asyncio.CancelledError:
        logger.warning(
            "CancelledError caught in suspicious_operation -- re-raising"
        )
        raise  # If this line is missing, the timeout breaks

async def main() -> None:
    try:
        async with asyncio.timeout(1):
            result = await suspicious_operation()
    except TimeoutError:
        print("Timed out as expected")
```

If you see the log message but [`TimeoutError`][timeouterror] is never raised, the
[`CancelledError`][cancellederror] is being swallowed somewhere. Search for `except
CancelledError` and `except BaseException` blocks in the call chain -- every
one must end with `#!py raise`.

**Fix:** Re-raise the [`CancelledError`][cancellederror]. Always. This is the cardinal rule from
[Cancellation and Timeouts](../the-basics/cancellation-and-timeouts.md):

```python
except asyncio.CancelledError:
    # Cleanup is fine here
    await cleanup()
    raise  # Never omit this
```

!!! Danger

    Third-party libraries can swallow [`CancelledError`][cancellederror] too. If the bug is
    not in your code, check the library's exception handling. This is a
    common source of hard-to-find timeout failures.

## Diagnosing ExceptionGroup Confusion

**Symptoms:** You have a `#!py try`/`#!py except Exception` around a [`TaskGroup`][taskgroup], but
errors from child tasks are not caught. The exception propagates as if the
`#!py except` clause does not exist.

**Cause:**
[`TaskGroup`][taskgroup]
wraps child exceptions in an
[`ExceptionGroup`][exceptiongroup].
[`ExceptionGroup`][exceptiongroup] inherits from [`BaseException`][baseexception], not `Exception`, so a plain
`#!py except Exception` does not match it.

**Diagnosis:**

Print or log the exception type to see what you are actually getting:

```python
async def main() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(failing_task())
    except BaseException as exc:
        print(f"Type: {type(exc).__name__}  Value: {exc!r}")
```

```text
Type: ExceptionGroup  Value: ExceptionGroup('unhandled errors in a TaskGroup (1 sub-exception)', [ValueError('something broke')])
```

You will see [`ExceptionGroup`][exceptiongroup], not [`ValueError`][valueerror]. That is why `except
ValueError` didn't match.

**Fix:** Use
[`except*`][except]
to match specific exception types inside the group:

```python
async def main() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(failing_task())
    except* ValueError as eg:
        for exc in eg.exceptions:
            print(f"Handled: {exc}")
```

[`except*`][except] splits the [`ExceptionGroup`][exceptiongroup], routes each sub-exception to the
matching handler, and re-raises anything unhandled as a new [`ExceptionGroup`][exceptiongroup].
See [Concurrent Tasks](../the-basics/concurrent-tasks.md) for the
full explanation.

!!! Info

    You cannot mix `#!py except` and [`except*`][except] in the same `#!py try` block. If you
    need [`except*`][except] for the [`TaskGroup`][taskgroup] errors, all handlers in that block
    must use the starred form.

## Diagnosing Deadlocks

**Symptoms:** Your program hangs. No progress, no exceptions.

**Causes:**

- **Two tasks waiting on each other.** Task A holds lock X and waits for lock
  Y. Task B holds lock Y and waits for lock X. Neither can proceed.
- **[`Lock.acquire()`][lock-acquire] without release.** A task acquires an
  [`asyncio.Lock`][asyncio-lock]
  but an exception prevents the release. Use `#!py async with lock:` instead of
  manual `#!py acquire()`/`#!py release()`.
- **[`Queue.get()`][queue-get] with no corresponding `#!py put()`.** A consumer waits for data
  that will never arrive because the producer has finished or crashed.
- **Blocking call masquerading as a hang.** Sometimes what looks like a
  deadlock is actually a blocking call that takes a very long time. Check the
  "Diagnosing a Blocked Loop" subsection first.

**Diagnosis:**

Use [`asyncio.all_tasks()`][asyncio-all-tasks] combined with
[`Task.print_stack()`][task-print-stack]
to see where every task is suspended:

```python
async def dump_tasks() -> None:
    for task in asyncio.all_tasks():
        print(f"\n--- {task.get_name()} ---", file=sys.stderr)
        task.print_stack(file=sys.stderr)
```

Call this from a signal handler or a diagnostic endpoint. The stack traces
show you exactly which [`await`][await] each task is stuck on -- typically a
[`Lock.acquire()`][lock-acquire] or [`Queue.get()`][queue-get]. From there, trace the dependency chain to
find the cycle.

**Fix:**

- **Lock ordering.** If multiple tasks need multiple locks, acquire them in a
  consistent order. Circular waits cannot happen if every task acquires lock X
  before lock Y.
- **Use [`async with`][async-with] for locks.** This guarantees the lock is released even if
  the body raises:

  ```python
  async with lock:
      await do_work()
  # lock is released here, even if do_work() raised
  ```

- **Sentinel values for queues.** If a producer might crash or finish early,
  send a sentinel so consumers stop waiting. See the fan-out pattern in
  [Concurrent Tasks](../the-basics/concurrent-tasks.md).
- **Timeouts as a safety net.** Wrapping lock acquisitions or queue gets in
  [`asyncio.timeout()`][asyncio-timeout] turns a deadlock into a [`TimeoutError`][timeouterror], which is at
  least diagnosable:

  ```python
  async with asyncio.timeout(5):
      async with lock:
          await do_work()
  ```

## Useful Diagnostic Patterns

Patterns worth keeping in your toolkit for non-trivial async programs.

### Task Monitor

A background coroutine that periodically logs all running tasks -- useful for
spotting leaks in long-running services:

```python
async def monitor_tasks(interval: float = 10.0) -> None:
    """Log all running tasks every `interval` seconds."""
    while True:
        await asyncio.sleep(interval)
        tasks = asyncio.all_tasks()
        logger.info("Active tasks: %d", len(tasks))
        for task in sorted(tasks, key=lambda t: t.get_name()):
            logger.debug("  %s: %s", task.get_name(), task.get_coro())
```

Add it to your [`TaskGroup`][taskgroup] at startup -- it will be cancelled automatically
when the group shuts down:

```python
async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(monitor_tasks(interval=30.0), name="task-monitor")
        # ... rest of your application ...
```

### Structured Logging with Task Names

Name your tasks and include the task name in log output. This makes it
easier to trace which task produced a given log line:

```python
async def worker(item: str) -> None:
    task_name = asyncio.current_task().get_name()  # type: ignore[union-attr]
    logger.info("[%s] Processing %s", task_name, item)
    await asyncio.sleep(1)
    logger.info("[%s] Finished %s", task_name, item)

async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        for i, item in enumerate(["alpha", "beta", "gamma"]):
            tg.create_task(worker(item), name=f"worker-{i}")
```

### `Task.print_stack()` for On-Demand Inspection

[`Task.print_stack()`][task-print-stack]
prints the stack trace of a specific task -- where it is currently suspended.
You already saw it in the deadlock subsection; it is equally useful for any case
where you need to understand what a task is waiting on. Use
[`Task.get_stack()`][task-get-stack]
if you need the frames as a list for programmatic inspection.

## Third-Party Tools

The standard library covers most situations. When you need more:

- **[`aiomonitor`][aiomonitor-docs]** -- Attaches a
  console to your running async application. Inspect tasks, print stacks,
  cancel tasks, and run async code -- all without stopping the program.

- **[`py-spy`][py-spy-docs]** -- A sampling profiler that
  attaches to a running process without modifying it. Generates flame graphs
  and works with async code.

- **[`VizTracer`][viztracer-docs]** -- A tracing
  profiler that generates timeline visualizations. It understands [`await`][await]
  boundaries, showing when tasks are running versus suspended.

These tools complement debug mode rather than replacing it. Start with
`#!py debug=True` and [`asyncio.all_tasks()`][asyncio-all-tasks], and reach for third-party tools when
you need to inspect a running production process or generate a performance
profile.

---

[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[runtimewarning]: https://docs.python.org/3/library/exceptions.html#RuntimeWarning
[task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task
[slow-callback-duration]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.slow_callback_duration
[await]: https://docs.python.org/3/reference/expressions.html#await
[create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[asyncio-all-tasks]: https://docs.python.org/3/library/asyncio-task.html#asyncio.all_tasks
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[timeouterror]: https://docs.python.org/3/library/exceptions.html#TimeoutError
[exceptiongroup]: https://docs.python.org/3/library/builtins.html#ExceptionGroup
[baseexception]: https://docs.python.org/3/library/exceptions.html#BaseException
[valueerror]: https://docs.python.org/3/library/exceptions.html#ValueError
[except]: https://docs.python.org/3/reference/compound_stmts.html#the-try-statement
[lock-acquire]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock.acquire
[asyncio-lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[queue-get]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get
[task-print-stack]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.print_stack
[task-get-stack]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_stack
[aiomonitor-docs]: https://aiomonitor.aio-libs.org/
[py-spy-docs]: https://github.com/benfred/py-spy
[viztracer-docs]: https://viztracer.readthedocs.io/en/stable/
