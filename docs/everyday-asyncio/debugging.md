# Debugging

Previous: [Building a Pipeline](building-a-pipeline.md)
Next: [Beyond the Basics](../02-beyond-the-basics/index.md)

Async bugs can be genuinely confusing. A forgotten `await` produces a
coroutine object instead of a value. A blocking call freezes the entire loop
with no obvious error. A swallowed `CancelledError` makes a timeout silently
fail. The symptoms are indirect and the tracebacks look unfamiliar. This
section gives you the tools to catch the common ones quickly -- enough to debug
your first few programs without drowning in detail. A comprehensive
[Debugging Guide](../appendices/debugging.md) lives in the appendices for when
you need heavier machinery.

## Debug Mode

Asyncio has a built-in
[debug mode](https://docs.python.org/3/library/asyncio-dev.html#debug-mode)
that catches several common mistakes at runtime. Enable it by passing
`debug=True` to `asyncio.run()`:

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

> [!TIP]
> Always develop with `debug=True`. The overhead is negligible and the
> diagnostics catch real bugs. Turn it off in production if the extra logging
> is too noisy, but consider leaving it on in staging.

## Common Mistakes Checklist

Most asyncio bugs fall into a handful of categories. When something goes wrong,
run through this list before reaching for heavier tools.

**1. Forgotten `await`**

*Symptom:* You get a `RuntimeWarning: coroutine '...' was never awaited`, or a
variable contains a coroutine object instead of the value you expected.

*Fix:* Add `await` in front of the async function call. Debug mode makes this
warning harder to miss.

**2. Blocking call in async code**

*Symptom:* The event loop freezes. Other tasks stop making progress. In debug
mode you see "Executing ... took X.XXX seconds" warnings.

*Culprits:* `time.sleep()`, `requests.get()`, heavy computation, synchronous
file I/O, any C extension that holds the GIL for a long time.

*Fix:* Replace with the async equivalent (`asyncio.sleep()`, `aiohttp`,
`asyncio.to_thread()` for unavoidable blocking work -- covered in
[Chapter 2](../02-beyond-the-basics/index.md)).

**3. Swallowing `CancelledError`**

*Symptom:* Timeouts don't fire. `TaskGroup` hangs instead of shutting down.
Code after `asyncio.timeout()` runs even though the deadline passed.

*Fix:* Always re-raise `CancelledError`. If you catch it for cleanup, end the
`except` block with `raise`. See
[Cancellation and Timeouts](cancellation-and-timeouts.md) for the full rule.

**4. Fire-and-forget tasks**

*Symptom:* "Task exception was never retrieved" in the logs. Work silently
disappears. Errors go unnoticed.

*Fix:* Use `TaskGroup` instead of bare `asyncio.create_task()`. The group
ensures every child's exception is propagated. See
[Concurrent Tasks](concurrent-tasks.md).

**5. Using threading primitives in async code**

*Symptom:* `threading.Lock` does not actually protect shared state (it never
suspends, so concurrent tasks interleave around it). Or worse, it *does* block
the loop thread, deadlocking everything.

*Fix:* Use [`asyncio.Lock`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock),
`asyncio.Event`, `asyncio.Semaphore`, etc. The `threading` versions are for
threads; the `asyncio` versions are for tasks. See
[Coordination](coordination.md).

> [!NOTE]
> If your bug isn't in this list, check the
> [Best Practices, Pitfalls, and Gotchas](../appendices/best-practices.md)
> appendix for a more comprehensive catalogue.

## Checkpoint Contract (Condensed)

Understanding which operations suspend and which don't is key to reasoning
about task interleaving and cancellation. Here is the short version -- enough
for everyday debugging. The full table is in the
[Checkpoint Contract](../appendices/checkpoint-contract.md) appendix.

| Category                | Examples                                                        |
|-------------------------|-----------------------------------------------------------------|
| **Always suspends**     | `asyncio.sleep()`, stream `read`/`readline`/`readexactly`, `Queue.get()` on empty queue, `Queue.put()` on full queue, `Lock.acquire()` when held by another task |
| **May or may not suspend** | `Lock.acquire()` when free, `Queue.get()` on non-empty queue, `Queue.put()` on non-full queue |
| **Never suspends**      | `StreamWriter.write()` (buffers only), `Queue.get_nowait()`, `Queue.put_nowait()`, `Event.set()`, `Event.is_set()` |

The practical implication: if you are wondering "can another task run between
these two lines?", check whether there is an `await` on something in the
"always suspends" category between them. If so, yes -- another task can (and
will) get a turn. If the only `await` is on something that completes
immediately, the switch is not guaranteed.

> [!IMPORTANT]
> `await` does not *always* mean "another task runs here." It means "another
> task *may* run here." The distinction matters when reasoning about shared
> mutable state.

## Reading Tracebacks

Asyncio tracebacks look different from synchronous ones, and the differences
can be disorienting at first. A few things to know:

**Task names in tracebacks.** When a task raises, the traceback includes the
task's name. If you passed `name=` to `tg.create_task()`, that name appears in
the output -- one good reason to always name your tasks during development.

**`ExceptionGroup` tracebacks are nested.** When a `TaskGroup` propagates
errors, you get an `ExceptionGroup` containing one or more sub-exceptions.
The traceback shows each sub-exception indented under the group. If you used
`except*` to handle some but not all of them, the unhandled ones propagate in
a *new* `ExceptionGroup`. This nesting can be deep -- read from the innermost
exception outward to find the root cause.

**Debug mode improves tracebacks.** With `debug=True`, asyncio stores the
creation-site traceback for every task. When something goes wrong, you see not
just *where* the exception was raised, but *where the task was created*. This
is invaluable when a task was spawned in one place and failed in another.

> [!TIP]
> When a traceback is overwhelming, start from the bottom. The last exception
> in the chain is usually the root cause. Work upward to see how it propagated
> through task groups and `except*` handlers.

---

That covers the essentials for debugging your first async programs: turn on
debug mode, check the common mistakes list, understand which operations are
checkpoints, and learn to read the tracebacks. When you need more -- diagnosing
blocked loops, tracking down task leaks, profiling event loop latency -- the
[Debugging Guide](../appendices/debugging.md) appendix goes deeper. Next up:
[Beyond the Basics](../02-beyond-the-basics/index.md), where you will learn
`asyncio.to_thread()`, `shield()`, subprocesses, and more.
