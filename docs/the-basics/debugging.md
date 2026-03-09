---
title: Debugging
description: >-
  Catch common async bugs quickly — forgotten awaits, blocking calls, and
  swallowed CancelledErrors. Enable asyncio debug mode and learn essential
  diagnostic techniques for your first async programs.
---

# Debugging

Async bugs can be genuinely confusing. A forgotten [`await`][await] produces a
coroutine object instead of a value. A blocking call freezes the entire loop
with no obvious error. A swallowed [`CancelledError`][cancellederror] makes a timeout silently
fail. The symptoms are indirect and the tracebacks look unfamiliar. This
section gives you the tools to catch the common ones quickly -- enough to debug
your first few programs without drowning in detail. A comprehensive
[Debugging Guide](../appendices/debugging.md) lives in the appendices for when
you need heavier machinery.

## Debug Mode

Asyncio has a built-in debug mode that catches several common mistakes at
runtime. Enable it by passing
`debug=True` to [`asyncio.run()`][asyncio-run]:

```python
import asyncio

async def main() -> None:
    ...

if __name__ == "__main__":
    asyncio.run(main(), debug=True)
```

You can also enable it without touching code by setting the
`PYTHONASYNCIODEBUG` environment variable:

```text
$ PYTHONASYNCIODEBUG=1 python my_program.py
```

When debug mode is active, the event loop:

- **Warns about unawaited coroutines** -- louder and earlier than the default
  `RuntimeWarning` from the garbage collector.
- **Logs slow callbacks** -- any callback or coroutine step that blocks the
  loop for more than 100 ms gets a warning with a traceback showing where the
  slow code ran.
- **Reports unclosed resources** -- transports, event loops, and other objects
  that were garbage-collected without being properly shut down.

!!! tip

    Always develop with `debug=True`. The overhead is negligible and the
    diagnostics catch real bugs. Turn it off in production if the extra logging
    is too noisy, but consider leaving it on in staging.

## Common Mistakes Checklist

Most asyncio bugs fall into a handful of categories. When something goes wrong,
run through this list before reaching for heavier tools.

**1. Forgotten [`await`][await]**

*Symptom:* You get a `#!py RuntimeWarning: coroutine '...' was never awaited`, or a
variable contains a coroutine object instead of the value you expected.

*Fix:* Add [`await`][await] in front of the async function call. Debug mode makes this
warning harder to miss.

**2. Blocking call in async code**

*Symptom:* The event loop freezes. Other tasks stop making progress. In debug
mode you see "Executing ... took X.XXX seconds" warnings.

*Culprits:* `#!py time.sleep()`, `#!py requests.get()`, heavy computation, synchronous
file I/O, any C extension that holds the GIL for a long time.

*Fix:* Replace with the async equivalent ([`asyncio.sleep()`][asyncio-sleep], `aiohttp`,
[`asyncio.to_thread()`][asyncio-to-thread] for unavoidable blocking work -- covered in
[Chapter 2](../beyond-the-basics/index.md)).

**3. Swallowing [`CancelledError`][cancellederror]**

*Symptom:* Timeouts don't fire. [`TaskGroup`][taskgroup] hangs instead of shutting down.
Code after [`asyncio.timeout()`][asyncio-timeout] runs even though the deadline passed.

*Fix:* Always re-raise [`CancelledError`][cancellederror]. If you catch it for cleanup, end the
`except` block with `raise`. See
[Cancellation and Timeouts](cancellation-and-timeouts.md) for the full rule.

**4. Fire-and-forget tasks**

*Symptom:* "Task exception was never retrieved" in the logs. Work silently
disappears. Errors go unnoticed.

*Fix:* Use [`TaskGroup`][taskgroup] instead of bare [`asyncio.create_task()`][asyncio-create-task]. The group
ensures every child's exception is propagated. See
[Concurrent Tasks](concurrent-tasks.md).

**5. Using threading primitives in async code**

*Symptom:* [`threading.Lock`][threading-lock] does not actually protect shared state (it never
suspends, so concurrent tasks interleave around it). Or worse, it *does* block
the loop thread, deadlocking everything.

*Fix:* Use [`asyncio.Lock`][asyncio-lock],
[`asyncio.Event`][asyncio-event], `asyncio.Semaphore`, etc. The `threading` versions are for
threads; the [`asyncio`][asyncio] versions are for tasks. See
[Coordination](coordination.md).

!!! note

    If your bug isn't in this list, check the
    [Best Practices, Pitfalls, and Gotchas](../appendices/best-practices.md)
    appendix for a more comprehensive catalogue.

## Checkpoint Contract (Condensed)

Understanding which operations suspend and which don't is key to reasoning
about task interleaving and cancellation. Here is the short version -- enough
for everyday debugging. The full table is in the
[Checkpoint Contract](../appendices/checkpoint-contract.md) appendix.

| Category                | Examples                                                        |
|-------------------------|-----------------------------------------------------------------|
| **Always suspends**     | [`asyncio.sleep()`][asyncio-sleep], stream `read`/`readline`/`readexactly`, [`Queue.get()`][queue-get] on empty queue, `#!py Queue.put()` on full queue, [`Lock.acquire()`][lock-acquire] when held by another task |
| **May or may not suspend** | [`Lock.acquire()`][lock-acquire] when free, [`Queue.get()`][queue-get] on non-empty queue, `#!py Queue.put()` on non-full queue |
| **Never suspends**      | `#!py StreamWriter.write()` (buffers only), [`Queue.get_nowait()`][queue-get-nowait], `#!py Queue.put_nowait()`, [`Event.set()`][event-set], [`Event.is_set()`][event-is-set] |

The practical implication: if you are wondering "can another task run between
these two lines?", check whether there is an [`await`][await] on something in the
"always suspends" category between them. If so, yes -- another task can (and
will) get a turn. If the only [`await`][await] is on something that completes
immediately, the switch is not guaranteed.

!!! info

    [`await`][await] does not *always* mean "another task runs here." It means "another
    task *may* run here." The distinction matters when reasoning about shared
    mutable state.

## Reading Tracebacks

Asyncio tracebacks look different from synchronous ones, and the differences
can be disorienting at first. A few things to know:

**Task names in tracebacks.** When a task raises, the traceback includes the
task's name. If you passed `name=` to `#!py tg.create_task()`, that name appears in
the output -- one good reason to always name your tasks during development.

**[`ExceptionGroup`][exceptiongroup] tracebacks are nested.** When a [`TaskGroup`][taskgroup] propagates
errors, you get an [`ExceptionGroup`][exceptiongroup] containing one or more sub-exceptions.
The traceback shows each sub-exception indented under the group. If you used
[`except*`][except] to handle some but not all of them, the unhandled ones propagate in
a *new* [`ExceptionGroup`][exceptiongroup]. This nesting can be deep -- read from the innermost
exception outward to find the root cause.

**Debug mode improves tracebacks.** With `debug=True`, asyncio stores the
creation-site traceback for every task. When something goes wrong, you see not
just *where* the exception was raised, but *where the task was created*. This
is invaluable when a task was spawned in one place and failed in another.

!!! tip

    When a traceback is overwhelming, start from the bottom. The last exception
    in the chain is usually the root cause. Work upward to see how it propagated
    through task groups and [`except*`][except] handlers.

---

[await]: https://docs.python.org/3/reference/expressions.html#await
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[asyncio-sleep]: https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep
[asyncio-to-thread]: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[asyncio-create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[threading-lock]: https://docs.python.org/3/library/threading.html#threading.Lock
[asyncio-lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[asyncio-event]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event
[asyncio]: https://docs.python.org/3/library/asyncio.html
[queue-get]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get
[lock-acquire]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock.acquire
[queue-get-nowait]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get_nowait
[event-set]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.set
[event-is-set]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.is_set
[exceptiongroup]: https://docs.python.org/3/library/builtins.html#ExceptionGroup
[except]: https://docs.python.org/3/reference/compound_stmts.html#the-try-statement
