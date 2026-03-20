---
title: Best Practices, Pitfalls, and Gotchas
description: >-
  A collection of actionable asyncio best practices, pitfalls, and gotchas,
  grouped by review topic.
---

# Best Practices, Pitfalls, and Gotchas

This appendix collects the guide's best practices, pitfalls, and gotchas in
one place. The groups follow a practical review flow: structure the program,
keep the event loop responsive, coordinate work, handle cancellation and
failure paths, clean up resources safely, and verify behavior during
development and CI.

Each rule has a short explanation and a reference to the chapter where the full
discussion lives. When in doubt, follow the reference -- the chapter sections
have runnable examples, edge cases, and the reasoning behind each rule.

If you follow these rules, the vast majority of asyncio bugs simply cannot
happen.

---

The group and rule headings make it easy to link directly to a specific item in
a review, issue, or code comment.

## Structure the Program

### ❌ Avoid `#!py asyncio.create_task()`

A task created with [`asyncio.create_task()`][asyncio-create-task] can outlive
its parent, silently drop exceptions, and leak if nobody awaits it. Use
[`TaskGroup`][taskgroup] instead. [`TaskGroup`][taskgroup] scopes every child
task's lifetime to the [`async with`][async-with] block, propagates exceptions
via [`ExceptionGroup`][exceptiongroup], and cancels siblings on failure. Reach
for [`create_task()`][create-task] only when you are building library internals
that genuinely need unscoped tasks.

See [Concurrent Tasks](../the-basics/concurrent-tasks.md#asynciotaskgroup).

### ✅ Give tasks a `#!py name`

Pass `#!py name=` to `#!py tg.create_task()` or
[`asyncio.create_task()`][asyncio-create-task]. Task names appear in
tracebacks, debug-mode warnings, and [`asyncio.all_tasks()`][asyncio-all-tasks]
output. Without names, you get auto-generated labels like `Task-14` that tell
you nothing when you are staring at a log trying to figure out which task is
stuck or leaking. A descriptive name like `#!py "fetch-user-42"` makes the
difference between a five-second diagnosis and a thirty-minute investigation.

See [Concurrent Tasks -- Collecting
Results](../the-basics/concurrent-tasks.md#collecting-results) and [Tasks and
Futures](../how-asyncio-works/tasks-and-futures.md).

### ❌ Do not nest `#!py run()` calls

[`asyncio.run()`][asyncio-run] creates an event loop, runs your top-level
coroutine, and tears everything down when it finishes. Calling it more than
once in the same program creates multiple loops with separate task sets, which
leads to "no running event loop" errors and resources that belong to a dead
loop. If you need to run multiple top-level coroutines on the same loop, use
[`asyncio.Runner`][asyncio-runner] as a context manager.

See [Getting Started](../the-basics/getting-started.md#asynciorun) and
[Runner](../beyond-the-basics/runner.md).

## Handle Failures and Interruptions

### ❌ Do not swallow `#!py CancelledError`

Catching [`CancelledError`][cancellederror] and not re-raising it defeats
timeouts, [`TaskGroup`][taskgroup] teardown, and graceful shutdown -- the
caller that requested cancellation will never know it happened. If you catch it
for logging or cleanup, always `#!py raise` at the end. This is the single most
important cancellation rule in the entire guide.

See [Cancellation and Timeouts -- Never Swallow a
`CancelledError`](../the-basics/cancellation-and-timeouts.md#never-swallow-a-cancellederror).

### ❌ Avoid `#!py except:` and `#!py except BaseException:`

Both `#!py except:` and `#!py except BaseException:` catch
[`CancelledError`][cancellederror] alongside other exceptions. These overly
broad exception handlers are a common anti-pattern in general, but in asyncio
they are even more dangerous because they silently break cancellation. The same
problem as [Do not swallow `CancelledError`](#do-not-swallow-cancellederror),
but easier to do by accident because the intent to catch
[`CancelledError`][cancellederror] is not visible in the code. If you need a
broad catch, filter out [`CancelledError`][cancellederror] explicitly and
re-raise it, or use `#!py except Exception:`, which deliberately excludes it.

See [Cancellation and Timeouts -- Never Swallow a
`CancelledError`](../the-basics/cancellation-and-timeouts.md#never-swallow-a-cancellederror)
and [Cancellation and Timeouts -- Cleanup with
`#!py try`/`finally`](../the-basics/cancellation-and-timeouts.md#cleanup-with-tryfinally).

### ✅ Use `#!py try`/`#!py finally` for cleanup

Cleanup logic -- closing connections, releasing locks, flushing files --
belongs in a `#!py finally` block (or an [`__aexit__`][aexit] method). A
`#!py finally` block runs regardless of whether the exit is normal, an
exception, or a cancellation. Catching [`CancelledError`][cancellederror]
specifically for cleanup is fragile: you must remember to re-raise, and the
code wrongly suggests that cleanup only matters during cancellation. Reserve
`#!py except CancelledError` for the rare case where you need
cancellation-specific *logic*, not just cleanup.

See [Cancellation and Timeouts -- Cleanup with `#!py
try`/`finally`](../the-basics/cancellation-and-timeouts.md#cleanup-with-tryfinally).

### ❌ Do not allow `#!py finally` to raise

If cleanup code in a `#!py finally` block raises while a
[`CancelledError`][cancellederror] is already unwinding the stack, the new
exception replaces the original cancellation. That effectively breaks the
caller's cancellation logic even though you did not catch
[`CancelledError`][cancellederror] explicitly. Treat this as another form of
the "Never Swallow" rule: your `#!py finally` block should never raise. If the
cleanup is best-effort and can still fail, wrap that part in a nested `#!py
try`/`#!py except Exception:` and log the failure there.

See [Cancellation and Timeouts -- Cleanup with `#!py
try`/`finally`](../the-basics/cancellation-and-timeouts.md#cleanup-with-tryfinally)
and [Cancellation and Timeouts -- Never Swallow a
`CancelledError`](../the-basics/cancellation-and-timeouts.md#never-swallow-a-cancellederror).

### ❌ Do not let `#!py __aexit__()` swallow cancellation

[`__aexit__()`][aexit] runs while the surrounding [`async with`][async-with]
block is unwinding. If it returns `#!py True`, it suppresses whatever
exception is leaving the block -- including [`CancelledError`][cancellederror].
Catching [`CancelledError`][cancellederror] inside [`__aexit__()`][aexit] and
not re-raising it has the same effect. That makes timeouts,
[`TaskGroup`][taskgroup] teardown, and shutdown logic think the block exited
normally. In almost every async context manager, [`__aexit__()`][aexit] should
return `#!py None` or `#!py False` after cleanup so cancellation can keep
propagating.

See [Context Managers and Lifetimes -- `__aexit__` and
Cancellation](../beyond-the-basics/context-managers-and-lifetimes.md#__aexit__-and-cancellation)
and [Cancellation and Timeouts -- Never Swallow a
`CancelledError`](../the-basics/cancellation-and-timeouts.md#never-swallow-a-cancellederror).

### ❌ Avoid `#!py wait_for()`

[`asyncio.wait_for()`][asyncio-wait-for] is a low-level function with subtle
cancellation edge cases and exists primarily for backward compatibility.
Prefer [`asyncio.timeout()`][asyncio-timeout] in all new code.
[`asyncio.timeout()`][asyncio-timeout] is a structured context
manager -- the timeout scope is visible in the code, you can nest it cleanly,
and you can inspect the deadline or check whether it fired after the block
exits.

See [Cancellation and Timeouts -- Timeouts](../the-basics/cancellation-and-timeouts.md#timeouts)
and [Task Coordination -- `#!py
asyncio.wait_for()`](../the-low-level-toolkit/task-coordination.md#asynciowait_for).

### ❌ Do not `#!py timeout()` around task creation

[`asyncio.timeout()`][asyncio-timeout] cancels the *current task*, not tasks
you create inside the block. A pattern like:

```python
async with TaskGroup() as tg:
    async with asyncio.timeout(...):
        tg.create_task(...)
```

Exits almost immediately, before the child can hit a checkpoint, so it does
**not** bound the child's runtime. Put the timeout around the whole
[`TaskGroup`][taskgroup] or inside the child coroutine instead:

```python
async with asyncio.timeout(...):
    async with TaskGroup() as tg:
        tg.create_task(...)
```

See [Cancellation and Timeouts -- Timeouts and Task
Groups](../the-basics/cancellation-and-timeouts.md#timeouts-and-task-groups).

### ❌ Avoid shielding long-running work

[`asyncio.shield()`][asyncio-shield] lets an inner task survive the
cancellation of its outer task, but the outer task still unwinds immediately.
If the shielded work takes a long time, it can keep running in the background
after its caller has exited. Shield only small, critical operations like
flushing a buffer or committing a transaction, and make sure some longer-lived
owner will await the inner task and observe its errors.

See [Shielding -- When to Use
Shielding](../beyond-the-basics/shielding.md#when-to-use-shielding).

## Keep the Event Loop Responsive

### ❌ Do not block the event loop

The event loop is single-threaded. A call to `#!py time.sleep()`,
[`requests.get()`][requests-get], [`open().read()`][open-read], or any
CPU-heavy computation blocks *every* other task until it returns. The symptoms
are indirect -- timeouts fire late, heartbeats miss, the UI freezes. Debug mode
warns about calls that exceed 100 ms, but the real fix is to move the blocking
work out of the coroutine entirely (see [Use `to_thread()` for blocking
I/O](#use-to_thread-for-blocking-io)).

See [Offloading Blocking Work -- The Problem](../beyond-the-basics/offloading-blocking-work.md#the-problem).

### ✅ Use `#!py to_thread()` for blocking I/O

When you must call a synchronous function that does I/O -- file reads,
synchronous HTTP clients, DNS lookups -- wrap it with
`#!py await asyncio.to_thread(func, *args)`. This runs the function in a
thread-pool worker, freeing the event loop to service other tasks while the
blocking call completes. For CPU-bound work that needs to release the GIL,
consider [`ProcessPoolExecutor`][processpoolexecutor] instead.

See [Offloading Blocking Work -- `#!py
asyncio.to_thread()`](../beyond-the-basics/offloading-blocking-work.md#asyncioto_thread).

### ❌ Avoid making functions `#!py async` unnecessarily

Adding `#!py async def` to a function that never [`await`][await]s anything
gives it a coroutine wrapper for no benefit. It introduces scheduling overhead,
cannot be called from synchronous code without an event loop, and misleads
readers into thinking the function yields control. Pure computations, data
transformations, and validation logic should stay synchronous. If a function
does no async I/O, keep it as a regular `#!py def`.

See [Getting Started -- The Async
Sandwich](../the-basics/getting-started.md#the-async-sandwich).

### ❌ Do not mix `#!py threading` and `#!py asyncio`

[`asyncio.Lock`][asyncio-lock] and [`threading.Lock`][threading-lock] solve the
same problem for different concurrency models. Using a
[`threading.Lock`][threading-lock] inside a coroutine will block the event loop
when it contends; using an [`asyncio.Lock`][asyncio-lock] from a thread has no
effect because it is not thread-safe. Keep the two worlds separate: asyncio
primitives in coroutines, threading primitives in threads, and
[`asyncio.to_thread()`][asyncio-to-thread] or
[`asyncio.run_coroutine_threadsafe()`][asyncio-run-coroutine-threadsafe]
at the boundary between them.

See [Offloading Blocking Work -- Thread
Safety](../beyond-the-basics/offloading-blocking-work.md#thread-safety).

## Clean Up Resources Safely

### ✅ Close `#!py StreamWriter` with `#!py wait_closed()`

Calling `#!py writer.close()` initiates shutdown but does not wait for the
transport to finish. Without the subsequent `#!py await writer.wait_closed()`,
you can exit the coroutine while data is still in the send buffer and the OS
socket is still open. Do both, in sequence, every time. Better yet, wrap the
stream in an async context manager so the cleanup cannot be skipped -- see [Use
`async with` for resources](#use-async-with-for-resources).

See [Streams -- `StreamWriter`](../beyond-the-basics/streams.md#streamwriter)
and [Streams -- Resource Management for
Streams](../beyond-the-basics/streams.md#resource-management-for-streams).

### ✅ Use `#!py async with` for resources

Locks, task groups, timeouts, streams, database connections -- anything with
[`__aenter__`][aenter]/[`__aexit__`][aexit] should be used as an async context
manager. This guarantees cleanup runs even when the block is interrupted by an
exception or a cancellation. Manual `#!py acquire()`/`#!py release()` and
`#!py close()` calls are easy to skip under cancellation; [`async with`][async-with]
makes skipping impossible.

See [Resource Management -- Async Context Managers and `async
with`](../the-basics/resource-management.md#async-context-managers-and-async-with).

### ✅ Use `#!py aclosing()` for async generators

An async generator that is abandoned mid-iteration never runs its
`#!py finally` block -- the cleanup code simply does not execute. Wrapping it
with `#!py async with aclosing(gen)` ensures `aclose()` is called when the
block exits, so cleanup runs reliably even if the consumer breaks out early or
gets cancelled. This is easy to forget because synchronous generators do not
have the same problem.

See [Resource Management -- `#!py
contextlib.aclosing()`](../the-basics/resource-management.md#contextlibaclosing).

## Coordinate Work and Control Load

### ❌ Avoid `#!py Queue`s with no `#!py maxsize`

An unbounded queue hides backpressure. If the producer is faster than the
consumer, memory grows without limit and you discover the problem only when the
process is killed by the OS. Setting `maxsize` makes `#!py put()` suspend when
the queue is full, which naturally throttles producers and surfaces design
mismatches early.

See [Coordination -- Backpressure](../the-basics/coordination.md#backpressure).

### ✅ Use sentinels for queue shutdown

Cancelling consumer tasks while they are blocked on `#!py queue.get()` works,
but sentinel values give you a cleaner, cooperative shutdown path. Send one
sentinel per consumer so each one receives the stop signal. If `#!py None` is
valid data, define a dedicated sentinel with `#!py _STOP = object()` and
compare with `#!py is`. The sentinel pattern composes well with
[`TaskGroup`][taskgroup] -- producers finish first, then the cleanup code sends
sentinels, and consumers exit naturally.

See [Coordination -- Queue Shutdown
Patterns](../the-basics/coordination.md#queue-shutdown-patterns).

### ✅ Prefer bounded concurrency

Launching thousands of tasks at once to hit an external API will exhaust
connections, file descriptors, or remote rate limits. Use
[`asyncio.Semaphore`][asyncio-semaphore] to cap the number of tasks performing
a given operation concurrently. The semaphore acts as an async-friendly
throttle: tasks that exceed the limit suspend on `#!py async with sem:` instead
of blocking, and proceed as earlier tasks finish.

See [Coordination -- `asyncio.Semaphore`](../the-basics/coordination.md#asynciosemaphore).

## Improve Debugability

### ✅ Use debug mode in development

Pass `#!py debug=True` to [`asyncio.run()`][asyncio-run] or set the
`PYTHONASYNCIODEBUG=1` environment variable. Debug mode warns about unawaited
coroutines, slow callbacks that block the loop, and unclosed resources. The
runtime overhead is negligible and the diagnostics catch mistakes that are
otherwise completely silent until production.

This is the right default for local development, bug reproduction, and often
staging. For steady-state production, see [Avoid debug mode in production by
default](#avoid-debug-mode-in-production-by-default) and [Allow optional
runtime debug mode](#allow-optional-runtime-debug-mode).

See [Debugging -- Debug Mode](../the-basics/debugging.md#debug-mode).

### ✅ Test with debug mode

Run your test suite with `#!py asyncio.run(main(), debug=True)` or the
`PYTHONASYNCIODEBUG` environment variable. Treat `ResourceWarning` and
"coroutine was never awaited" as test failures, not noise. These warnings are
free bug reports -- they surface forgotten [`await`][await]s, leaked
connections, and unclosed transports before they reach production. Combining
debug mode with Python's `-W error` flag turns warnings into hard failures that
your CI pipeline cannot miss.

See [Debugging -- Debug Mode](../the-basics/debugging.md#debug-mode).

### ❌ Avoid debug mode in production by default

Debug mode is instrumentation, not a free upgrade. It stores extra traceback
and scheduling metadata, emits slow-callback warnings and resource warnings,
and increases log volume. In development that cost is usually worth it. In
production -- especially in high-throughput or latency-sensitive services --
leave it off by default and enable it deliberately when the extra diagnostics
are worth the overhead.

See [Debugging -- Debug Mode](../the-basics/debugging.md#debug-mode) and
[Debugging Guide -- Recommended
Usage](debugging.md#recommended-usage).

### ✅ Allow optional runtime debug mode

If the program is already running, you can enable debug mode for the current
loop with `#!py asyncio.get_running_loop().set_debug(True)`. That makes it a
useful incident-response tool: when restarting would hide the bug or cost too
much, you can turn debug mode on temporarily, gather slow-callback warnings,
tracebacks for newly created tasks, and new resource warnings, then turn it off
again.

See [Debugging -- Debug Mode](../the-basics/debugging.md#debug-mode) and
[Debugging Guide -- Debug Mode -- the Full
Picture](debugging.md#debug-mode----the-full-picture).

[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[requests-get]: https://requests.readthedocs.io/en/latest/api/#requests.get
[open-read]: https://docs.python.org/3/library/io.html#io.IOBase.read
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[asyncio-create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[exceptiongroup]: https://docs.python.org/3/library/builtins.html#ExceptionGroup
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[wait-closed]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.wait_closed
[aenter]: https://docs.python.org/3/reference/datamodel.html#object.__aenter__
[aexit]: https://docs.python.org/3/reference/datamodel.html#object.__aexit__
[contextlib-aclosing]: https://docs.python.org/3/library/contextlib.html#contextlib.aclosing
[asyncio-to-thread]: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
[processpoolexecutor]: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ProcessPoolExecutor
[async]: https://docs.python.org/3/reference/compound_stmts.html#async-def
[await]: https://docs.python.org/3/reference/expressions.html#await
[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[asyncio-wait-for]: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for
[asyncio-shield]: https://docs.python.org/3/library/asyncio-task.html#asyncio.shield
[asyncio-all-tasks]: https://docs.python.org/3/library/asyncio-task.html#asyncio.all_tasks
[asyncio-runner]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner
[asyncio-run-coroutine-threadsafe]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run_coroutine_threadsafe
[asyncio-lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[threading-lock]: https://docs.python.org/3/library/threading.html#threading.Lock
[semaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
[asyncio-semaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
