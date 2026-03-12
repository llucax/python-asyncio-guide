---
title: Task Coordination
description: >-
  A concise guide to asyncio.wait(), asyncio.as_completed(), and
  asyncio.wait_for(). Learn when each fits, what cleanup work they leave to
  you, and where to read the official reference next.
---

# Task Coordination

[`TaskGroup`][taskgroup] is the right default for concurrent work. These APIs
exist for the cases where you deliberately want something lower-level:

- act on whichever task finishes first
- process results in completion order
- put a timeout around one awaitable at an API boundary

Because they sit below structured concurrency, they also hand more cleanup work
back to you.

!!! Warning

    These APIs do not own the tasks they operate on. If you leave pending tasks
    behind, they keep running.

## Which Tool Fits Which Job?

| Use case | Tool |
|---|---|
| "Wait until one or all tasks meet a condition, then inspect done and pending sets" | [`asyncio.wait()`][wait] |
| "Process results in the order they arrive" | [`asyncio.as_completed()`][as-completed] |
| "Apply a timeout to one awaitable" | [`asyncio.wait_for()`][wait-for] |

## `asyncio.wait()`

[`asyncio.wait()`][wait] returns two sets: `done` and `pending`.

That makes it useful when you want to race tasks or keep manual control over
the stragglers.

```python
done, pending = await asyncio.wait(
    tasks,
    return_when=asyncio.FIRST_COMPLETED,
)

winner = next(iter(done))
print(winner.result())

for task in pending:
    task.cancel()
if pending:
    await asyncio.wait(pending)
```

That last cleanup step is the key rule for this whole section:

!!! Danger

    [`wait()`][wait] never cancels pending tasks for you. If you do not cancel and wait
    for them yourself, you have recreated fire-and-forget tasks.

## `asyncio.as_completed()`

[`asyncio.as_completed()`][as-completed] is for streaming results in completion
order instead of submission order.

Use it when early results are useful on their own, for example when showing
progress or consuming responses as soon as they are ready.

```python
for next_result in asyncio.as_completed(tasks):
    value = await next_result
    print(value)
```

This is often simpler than [`wait()`][wait] when you care about *every* result but want
them in arrival order.

## `asyncio.wait_for()`

[`asyncio.wait_for()`][wait-for] is the old low-level timeout helper.

Use it mainly when you are putting a timeout around one specific awaitable at a
boundary where introducing a surrounding timeout scope would be awkward.

In new application code, prefer [`asyncio.timeout()`][timeout] from
[Cancellation and Timeouts](../the-basics/cancellation-and-timeouts.md).
It is more visible in the control flow and composes better with structured
concurrency.

## What to Read Next

- Full task reference: [Coroutines and Tasks][coroutines-and-tasks]
- Structured alternative: [Concurrent Tasks](../the-basics/concurrent-tasks.md)
- Timeout-first application design:
  [Cancellation and Timeouts](../the-basics/cancellation-and-timeouts.md)

[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[wait]: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait
[as-completed]: https://docs.python.org/3/library/asyncio-task.html#asyncio.as_completed
[wait-for]: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for
[timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[coroutines-and-tasks]: https://docs.python.org/3/library/asyncio-task.html
