# Best Practices, Pitfalls, and Gotchas

This page distills every recommendation from the guide into one place. The
pattern is always the same: use structured concurrency to bound task lifetimes,
respect cancellation so timeouts and teardown actually work, manage resources
with `async with`, and never block the event loop. If you follow these twenty
rules, the vast majority of asyncio bugs simply cannot happen.

Each item gets a brief explanation and a reference to the chapter where the full
discussion lives. When in doubt, follow the reference -- the chapters have
runnable examples, edge cases, and the reasoning behind each recommendation.

The list is ordered roughly by importance. The first few rules prevent the most
common and most damaging mistakes; the later ones are about polish and
operational discipline.

---

## Best Practices

1. **Always use `TaskGroup` instead of bare `create_task()`.** A task created
   with `asyncio.create_task()` can outlive its parent, silently drop
   exceptions, and leak if nobody awaits it. `TaskGroup` scopes every child
   task's lifetime to the `async with` block, propagates exceptions via
   `ExceptionGroup`, and cancels siblings on failure. Reach for `create_task()`
   only when you are building library internals that genuinely need unscoped
   tasks.
   See [Concurrent Tasks -- `asyncio.TaskGroup`](../everyday-asyncio/concurrent-tasks.md#asynciotaskgroup).

2. **Never swallow `CancelledError`.** Catching `CancelledError` and not
   re-raising it defeats timeouts, `TaskGroup` teardown, and graceful
   shutdown -- the caller that requested cancellation will never know it
   happened. If you catch it for logging or cleanup, always `raise` at the
   end. This is the single most important cancellation rule in the entire
   guide.
   See [Cancellation and Timeouts -- The Cardinal Rule: Never Swallow Cancellation](../everyday-asyncio/cancellation-and-timeouts.md#the-cardinal-rule-never-swallow-cancellation).

3. **Always set `maxsize` on `Queue`.** An unbounded queue hides backpressure.
   If the producer is faster than the consumer, memory grows without limit and
   you discover the problem only when the process is killed by the OS. Setting
   `maxsize` makes `put()` suspend when the queue is full, which naturally
   throttles producers and surfaces design mismatches early.
   See [Coordination -- Backpressure](../everyday-asyncio/coordination.md#backpressure).

4. **Always close `StreamWriter` and call `wait_closed()`.** Calling
   `writer.close()` initiates shutdown but does not wait for the transport to
   finish. Without the subsequent `await writer.wait_closed()`, you can exit
   the coroutine while data is still in the send buffer and the OS socket is
   still open. Do both, in sequence, every time. Better yet, wrap the stream
   in an async context manager so the cleanup cannot be skipped (see rule 5).
   See [Streams -- `StreamWriter`](../everyday-asyncio/streams.md#streamwriter)
   and [Streams -- Resource Management for Streams](../everyday-asyncio/streams.md#resource-management-for-streams).

5. **Use `async with` for every resource that supports it.** Locks, task
   groups, timeouts, streams, database connections -- anything with
   `__aenter__`/`__aexit__` should be used as an async context manager. This
   guarantees cleanup runs even when the block is interrupted by an exception
   or a cancellation. Manual `acquire()`/`release()` and `close()` calls are
   easy to skip under cancellation; `async with` makes skipping impossible.
   See [Resource Management -- `async with`](../everyday-asyncio/resource-management.md#async-with).

6. **Use `contextlib.aclosing()` for async generators.** An async generator
   that is abandoned mid-iteration never runs its `finally` block -- the
   cleanup code simply does not execute. Wrapping it with `async with
   aclosing(gen)` ensures `aclose()` is called when the block exits, so
   cleanup runs reliably even if the consumer breaks out early or gets
   cancelled. This is easy to forget because synchronous generators do not
   have the same problem.
   See [Resource Management -- `contextlib.aclosing()`](../everyday-asyncio/resource-management.md#contextlibaclosing).

7. **Don't block the event loop.** The event loop is single-threaded. A call
   to `time.sleep()`, `requests.get()`, `open().read()`, or any CPU-heavy
   computation blocks *every* other task until it returns. The symptoms are
   indirect -- timeouts fire late, heartbeats miss, the UI freezes. Debug mode
   warns about calls that exceed 100 ms, but the real fix is to move the
   blocking work out of the coroutine entirely (see rules 8 and 9).
   See [Blocking Code -- The Problem: Blocking the Event Loop](../beyond-the-basics/blocking-code.md#the-problem-blocking-the-event-loop).

8. **Use `asyncio.to_thread()` for blocking I/O.** When you must call a
   synchronous function that does I/O -- file reads, synchronous HTTP clients,
   DNS lookups -- wrap it with `await asyncio.to_thread(func, *args)`. This
   runs the function in a thread-pool worker, freeing the event loop to
   service other tasks while the blocking call completes. For CPU-bound work
   that needs to release the GIL, consider `ProcessPoolExecutor` instead.
   See [Blocking Code -- `asyncio.to_thread()`](../beyond-the-basics/blocking-code.md#asyncioto_thread).

9. **Don't make sync-only functions `async`.** Adding `async def` to a
   function that never `await`s anything gives it a coroutine wrapper for no
   benefit. It introduces scheduling overhead, cannot be called from
   synchronous code without an event loop, and misleads readers into thinking
   the function yields control. Pure computations, data transformations, and
   validation logic should stay synchronous. If a function does no async I/O,
   keep it as a regular `def`.
   See [Getting Started -- Coroutines](../everyday-asyncio/getting-started.md#coroutines).

10. **Enable debug mode during development.** Pass `debug=True` to
    `asyncio.run()` or set the `PYTHONASYNCIODEBUG=1` environment variable.
    Debug mode warns about unawaited coroutines, slow callbacks that block the
    loop, and unclosed resources. The runtime overhead is negligible and the
    diagnostics catch mistakes that are otherwise completely silent until
    production.
    See [Debugging -- Debug Mode](../everyday-asyncio/debugging.md#debug-mode).

11. **Use `asyncio.timeout()` instead of `wait_for()`.** `asyncio.timeout()`
    is a structured context manager -- the timeout scope is visible in the
    code, you can nest it cleanly, and you can inspect the deadline or check
    whether it fired after the block exits. `wait_for()` is a low-level
    function with subtle cancellation edge cases and exists primarily for
    backward compatibility. Prefer `timeout()` in all new code.
    See [Cancellation and Timeouts -- `asyncio.timeout()`](../everyday-asyncio/cancellation-and-timeouts.md#asynciotimeout)
    and [Task Coordination -- `asyncio.wait_for()`](../the-low-level-toolkit/task-coordination.md#asynciowait_for).

12. **Keep shielded work short and deliberate.** `asyncio.shield()` lets an
    inner task survive the cancellation of its outer task, but the outer task
    still unwinds immediately. If the shielded work takes a long time, it runs
    unmonitored in the background with no parent to collect its result or
    handle its errors. Shield only small, critical operations like flushing a
    buffer or committing a transaction, and always document *why* the work
    needs to survive cancellation.
    See [Shielding -- When to Use It](../beyond-the-basics/shielding.md#when-to-use-it).

13. **Use sentinel values for queue shutdown.** Cancelling consumer tasks
    while they are blocked on `queue.get()` works, but sentinel values give
    you a cleaner, cooperative shutdown path. Send one sentinel per consumer so
    each one receives the stop signal. If `None` is valid data, define a
    dedicated sentinel with `_STOP = object()` and compare with `is`. The
    sentinel pattern composes well with `TaskGroup` -- producers finish first,
    then the cleanup code sends sentinels, and consumers exit naturally.
    See [Coordination -- Queue Shutdown Patterns](../everyday-asyncio/coordination.md#queue-shutdown-patterns).

14. **Use `try`/`finally` for cleanup, not `except CancelledError`.** Cleanup
    logic -- closing connections, releasing locks, flushing files -- belongs in
    a `finally` block (or an `__aexit__` method). A `finally` block runs
    regardless of whether the exit is normal, an exception, or a cancellation.
    Catching `CancelledError` specifically for cleanup is fragile: you must
    remember to re-raise, and the code wrongly suggests that cleanup only
    matters during cancellation. Reserve `except CancelledError` for the rare
    case where you need cancellation-specific *logic*, not just cleanup.
    See [Cancellation and Timeouts -- Cleanup with `try`/`finally`](../everyday-asyncio/cancellation-and-timeouts.md#cleanup-with-tryfinally).

15. **Avoid bare `except:` and `except BaseException:` without re-raising
    `CancelledError`.** Both of these catch `CancelledError` alongside
    ordinary exceptions. If your handler does not re-raise it, you silently
    break cancellation -- the same problem as rule 2, but easier to do by
    accident because the intent to catch cancellation is not visible in the
    code. If you need a broad catch, filter out `CancelledError` explicitly
    and re-raise it, or use `except Exception:` which deliberately excludes it.
    See [Cancellation and Timeouts -- The `except BaseException:` Trap](../everyday-asyncio/cancellation-and-timeouts.md#the-except-baseexception-trap).

16. **Name your tasks for debugging.** Pass `name=` to `tg.create_task()` or
    `asyncio.create_task()`. Task names appear in tracebacks, debug-mode
    warnings, and `asyncio.all_tasks()` output. Without names, you get
    auto-generated labels like `Task-14` that tell you nothing when you are
    staring at a log trying to figure out which task is stuck or leaking. A
    descriptive name like `"fetch-user-42"` makes the difference between a
    five-second diagnosis and a thirty-minute investigation.
    See [Concurrent Tasks -- Collecting Results](../everyday-asyncio/concurrent-tasks.md#collecting-results)
    and [Tasks and Futures](../how-asyncio-works/tasks-and-futures.md).

17. **Use `asyncio.run()` exactly once at the top level.** `asyncio.run()`
    creates an event loop, runs your top-level coroutine, and tears everything
    down when it finishes. Calling it more than once in the same program
    creates multiple loops with separate task sets, which leads to "no running
    event loop" errors and resources that belong to a dead loop. If you need
    to run multiple top-level coroutines on the same loop, use
    `asyncio.Runner` as a context manager.
    See [Getting Started -- `asyncio.run()`](../everyday-asyncio/getting-started.md#asynciorun)
    and [Runner](../beyond-the-basics/runner.md).

18. **Don't mix threading primitives with asyncio primitives.** `asyncio.Lock`
    and `threading.Lock` solve the same problem for different concurrency
    models. Using a `threading.Lock` inside a coroutine will block the event
    loop when it contends; using an `asyncio.Lock` from a thread has no
    effect because it is not thread-safe. Keep the two worlds separate:
    asyncio primitives in coroutines, threading primitives in threads, and
    `asyncio.to_thread()` or `run_coroutine_threadsafe()` at the boundary
    between them.
    See [Blocking Code -- Thread Safety](../beyond-the-basics/blocking-code.md#thread-safety).

19. **Prefer bounded concurrency (`Semaphore`) over unlimited fan-out.**
    Launching thousands of tasks at once to hit an external API will exhaust
    connections, file descriptors, or remote rate limits. Use
    `asyncio.Semaphore` to cap the number of tasks performing a given
    operation concurrently. The semaphore acts as an async-friendly throttle:
    tasks that exceed the limit suspend on `async with sem:` instead of
    blocking, and proceed as earlier tasks finish.
    See [Coordination -- `asyncio.Semaphore`](../everyday-asyncio/coordination.md#asynciosemaphore).

20. **Test with debug mode and strict exception handling.** Run your test
    suite with `asyncio.run(main(), debug=True)` or the `PYTHONASYNCIODEBUG`
    environment variable. Treat `ResourceWarning` and "coroutine was never
    awaited" as test failures, not noise. These warnings are free bug reports
    -- they surface forgotten `await`s, leaked connections, and unclosed
    transports before they reach production. Combining debug mode with Python's
    `-W error` flag turns warnings into hard failures that your CI pipeline
    cannot miss.
    See [Debugging -- Debug Mode](../everyday-asyncio/debugging.md#debug-mode).

---

## Quick Reference

| Rule | One-liner |
|------|-----------|
| 1 | `TaskGroup` over `create_task()` |
| 2 | Never swallow `CancelledError` |
| 3 | `Queue(maxsize=N)`, always |
| 4 | `writer.close()` then `await writer.wait_closed()` |
| 5 | `async with` for every resource |
| 6 | `aclosing()` for async generators |
| 7 | Never call blocking functions in a coroutine |
| 8 | `asyncio.to_thread()` for blocking I/O |
| 9 | Don't add `async` to sync-only functions |
| 10 | `debug=True` during development |
| 11 | `asyncio.timeout()` over `wait_for()` |
| 12 | Shield only short, critical work |
| 13 | One sentinel per consumer for queue shutdown |
| 14 | `try`/`finally` for cleanup |
| 15 | Re-raise `CancelledError` in broad `except` |
| 16 | Name every task |
| 17 | `asyncio.run()` exactly once |
| 18 | Don't mix threading and asyncio primitives |
| 19 | `Semaphore` for bounded concurrency |
| 20 | Test under debug mode |
