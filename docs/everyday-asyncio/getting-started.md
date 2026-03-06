# Getting Started

This section introduces the core vocabulary of asyncio: coroutines, `await`,
`asyncio.run()`, and `asyncio.sleep()`. By the end you will be able to write
and run a simple async program and understand what happens under the hood.
Everything here is sequential -- the next section covers running things
concurrently.

## Cooperative Scheduling

Python gives you two main tools for concurrency: threads and asyncio.
They solve the same problem -- doing more than one thing at a time -- but
they work in fundamentally different ways.

With **threads**, the operating system preempts your code at any point.
Multiple threads can genuinely run in parallel, but you need locks to
protect shared state because interruption is invisible and unpredictable.

With **asyncio**, your code runs on a single thread and only yields
control when it hits an `await`. Only one coroutine executes at a time.
The tradeoff: you can never be interrupted mid-statement, so you rarely
need locks -- but you must cooperate by awaiting regularly, or you will
block everyone else.

## Coroutines and `asyncio.run()`

An *async function* (also called a *coroutine function*) is any function
defined with `async def` instead of plain `def`. Let's start with a
complete, working program:

```python
# hello_async.py
import asyncio

async def greet(name: str) -> str:
    return f"Hello, {name}"

async def main() -> None:
    message: str = await greet("world")
    print(message)

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python hello_async.py
Hello, world
```

Here is what happens when you run this:

1. `async def greet` and `async def main` define coroutine functions.
2. [`asyncio.run()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run)
   creates an event loop, drives `main()` to completion, and tears the
   loop down cleanly. It is the bridge between the synchronous world and
   the async world.
3. Inside `main`, `await greet("world")` calls the coroutine function,
   drives the resulting coroutine to completion, and gives you back its
   return value.

That is the pattern you will use in nearly every asyncio program: define
an `async def main()`, put your logic there, and call
`asyncio.run(main())` at the bottom. `asyncio.run()` is meant to be
called **once**, at the top level of your program.

> [!NOTE]
> Do not call `asyncio.run()` from inside an async function. It will
> raise a `RuntimeError` because a loop is already running. If you need
> to run async code from sync code that is itself called from async
> code, that is a different problem (covered in Chapter 2 with
> `asyncio.Runner`).

## What Goes Wrong Without `await`

Calling an async function does **not** execute its body. It returns a
*coroutine object* -- a little package of suspended work that must be
driven by the event loop (or by `await`). If you forget that step, the
body never runs.

```python
# wrong_call.py
import asyncio

async def greet(name: str) -> str:
    return f"Hello, {name}"

if __name__ == "__main__":
    greet("world")  # Oops -- this never drives the coroutine
```

```text
$ python wrong_call.py
wrong_call.py:7: RuntimeWarning: coroutine 'greet' was never awaited
  greet("world")
```

Nothing printed, no greeting -- just a `RuntimeWarning`. The coroutine
was created and immediately garbage-collected without ever running.

The same bug is more subtle when it happens *inside* an async function:

```python
# forgot_await.py
import asyncio

async def get_answer() -> int:
    return 42

async def main() -> None:
    answer = get_answer()  # Bug: missing await
    print(f"The answer is {answer}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python forgot_await.py
The answer is <coroutine object get_answer at 0x...>
forgot_await.py:8: RuntimeWarning: coroutine 'get_answer' was never awaited
  answer = get_answer()
```

Instead of `42`, you get a coroutine object printed as a string. The fix
is simple -- add `await`:

```python
    answer = await get_answer()  # Fixed
```

> [!TIP]
> Enable asyncio's *debug mode* during development by passing
> `debug=True` to `asyncio.run()`. It makes warnings about unawaited
> coroutines louder and catches other common errors. See
> [`asyncio` debug mode](https://docs.python.org/3/library/asyncio-dev.html#debug-mode)
> for details.

> [!TIP]
> **Trio users:** Trio raises an error immediately when a coroutine is
> not awaited inside a nursery. In asyncio the diagnostic is a
> `RuntimeWarning` from the garbage collector, which can be delayed or
> even silenced. Turning on debug mode helps close this gap.

## `await`

The `await` keyword does two things:

1. It *drives* a coroutine (or any *awaitable*) to completion and gives you
   back its return value.
2. It marks a potential *suspension point* -- a place where the event loop
   **may** pause your coroutine and go do other work.

You can only use `await` inside an `async def`. This is enforced by the
compiler, not by convention. If you try to use it in a regular function you
will get a `SyntaxError`.

Here is a small example that chains two async calls and uses the return values:

```python
# await_demo.py
import asyncio

async def add(a: int, b: int) -> int:
    return a + b

async def double(n: int) -> int:
    return n * 2

async def main() -> None:
    total: int = await add(3, 4)
    result: int = await double(total)
    print(f"3 + 4 = {total}, doubled = {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python await_demo.py
3 + 4 = 7, doubled = 14
```

Nothing surprising yet -- this looks and behaves exactly like synchronous code.
The difference only becomes visible once there are multiple tasks (next
section) and real I/O operations. For now, just remember: **every call to an
async function must be `await`-ed** (or explicitly scheduled, covered
later).

## The Async Sandwich

You will sometimes hear people complain that `async`/`await` is "infectious" --
once one function is async, every caller has to be async too, all the way up
to `asyncio.run()`. This is sometimes called *function colouring* and it is
not a bug. It is a feature, and once you see the structure it becomes
intuitive.

Think of your program as a sandwich:

- **Top slice** -- `asyncio.run()`. This is synchronous code that starts the
  loop. You call it once, at the very top.
- **Filling** -- your async application code. Functions here are `async def`
  and they `await` each other freely.
- **Bottom slice** -- asyncio primitives (I/O operations, `asyncio.sleep()`,
  task groups, etc.). These are the points where the loop can actually suspend
  your code and do useful work elsewhere.

The filling is necessarily async because it sits between a synchronous entry
point and async I/O primitives. If you could call an I/O primitive from a
plain `def`, the compiler would have no way to know that the function might
suspend -- and the loop would not know when it is safe to switch. The `async`
keyword is how Python tracks that information through the call chain.

So when you see a tall stack of `async def` calling `async def`, that is not
ceremony -- it is the language telling you, at every level, "this function may
pause."

> [!NOTE]
> You do *not* need to make everything async. Pure computation -- parsing a
> string, doing math, transforming a data structure -- should stay in regular
> `def` functions. Only add `async` when the function needs to `await`
 > something.

## How the Event Loop Works

The phrases "event loop" and "coroutine" are easier to reason about once
you have a concrete picture of the machinery. Below is a three-step
progression -- pseudocode, not real Python -- that builds the mental
model you will rely on for the rest of this guide.

### Step 1: One Coroutine

Strip everything down to one coroutine and a loop that drives it:

```text
# One coroutine, one loop

ready = [main_coroutine]

while ready:
    coro = ready.pop()
    result = coro.resume()        # run until next yield
    if result is YIELD_SLEEP:
        schedule_timer(coro)      # put back on ready when timer fires
    elif result is FINISHED:
        pass                      # done
```

The loop pops a coroutine, runs it until it yields at an `await`, then
decides what to do next.
[`asyncio.sleep()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep)
says "wake me after this many seconds" -- the loop sets a timer and
moves on.

### Step 2: Multiple Coroutines

Real programs have more than one coroutine, so the loop needs a *ready
queue* and a *waiting map*:

```text
# Multiple coroutines

ready   = [coro_a, coro_b]
waiting = {}                      # fd/timer -> coroutine

while ready or waiting:
    for coro in drain(ready):     # run everything that is ready
        result = coro.resume()
        if result is YIELD_SLEEP:
            schedule_timer(coro)
        elif result is YIELD_IO:
            waiting[coro.fd] = coro
        elif result is FINISHED:
            pass

    events = poll(waiting, timeout=next_timer())
    for event in events:
        ready.append(waiting.pop(event.fd))
```

The loop drains everything in the ready queue, then calls the OS to
wait for I/O or timers (`poll`). When something becomes ready, it goes
back on the queue. This is the core of every event loop -- asyncio's
included.

### Step 3: Tasks

So what is an
[`asyncio.Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task)?
A thin wrapper around a coroutine that the loop knows about:

```text
# Tasks = coroutines the loop tracks

class Task:
    def __init__(self, coro):
        self.coro = coro
        self.result = None
        loop.ready.append(self)   # auto-schedule

    def step(self):
        result = self.coro.resume()
        ...                       # same bookkeeping as above
```

A Task wraps a coroutine and registers it with the event loop. That is
why
[`asyncio.create_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task)
(and `tg.create_task()`) is what gives you concurrency -- it puts a
new entry on the loop's ready queue. A bare `await some_coro()` just
inlines the work into the current task; it does **not** create a new
ready-queue entry.

> [!TIP]
> If concurrency is not appearing where you expect, check whether you
> are `await`-ing a coroutine directly instead of wrapping it in a
> task. That is the single most common mistake.

### Putting It Together

| Concept | One-line summary |
|---|---|
| **Coroutine** | A function that can suspend and resume (`async def`). |
| **Task** | A coroutine the loop tracks and schedules independently. |
| **Event loop** | A `while` loop: run ready tasks, wait for I/O, repeat. |

That is the entire machine. Everything else in asyncio -- task groups,
cancellation, timeouts, queues -- is built on top of this loop.

## Checkpoints

A *checkpoint* is a point in your code where the event loop gets the
opportunity to switch to another task. Without checkpoints, a single coroutine
would hold the loop hostage and no other task could make progress.

In asyncio, checkpoints happen at `await` expressions -- but **not every
`await` is a checkpoint**. If the awaited operation completes immediately
(e.g., awaiting a coroutine that just returns a value without doing I/O), the
loop may not actually suspend your coroutine. The rule of thumb is:

> An `await` is a checkpoint when the underlying operation needs to wait for
> something external -- a timer, a network read, a lock held by another task.

For now, that mental model is enough. There is a full checkpoint contract table
in the [appendices](../appendices/checkpoint-contract.md) that documents
exactly which asyncio operations always suspend, conditionally suspend, or
never suspend. You don't need to memorise it, but it is there when you need
precise answers.

When you want to give other tasks a chance to run without actually waiting for
anything, you can insert an explicit checkpoint:

```python
await asyncio.sleep(0)
```

This tells the loop "I have nothing to wait for, but please go check if
anyone else needs a turn." You will see this pattern used in CPU-heavy async
code to avoid starving other tasks.

> [!TIP]
> **Trio users:** Trio has an explicit `trio.testing.checkpoints()` and
> guarantees that *every* checkpoint is documented. In asyncio the contract is
> less strict -- most I/O operations are checkpoints, but it is not always
> guaranteed. The `asyncio.sleep(0)` idiom is the closest equivalent to
> Trio's `await trio.sleep(0)`.

## `asyncio.sleep()`

[`asyncio.sleep()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep)
suspends the current coroutine for (at least) the given number of seconds. It
serves two purposes: it is a timer, and it is a guaranteed checkpoint.

```python
# sleep_demo.py
import asyncio

async def countdown(label: str, n: int) -> None:
    for i in range(n, 0, -1):
        print(f"{label}: {i}")
        await asyncio.sleep(1)
    print(f"{label}: done!")

async def main() -> None:
    await countdown("A", 3)

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python sleep_demo.py
A: 3
A: 2
A: 1
A: done!
```

Each `await asyncio.sleep(1)` pauses the coroutine for one second **and**
gives the loop a chance to run other tasks (if there were any -- right now you
only have one). You will put this to real use in the next section when you run
multiple countdowns concurrently.

> [!WARNING]
> Do not use `time.sleep()` in async code. It blocks the entire thread --
> including the event loop -- so no other coroutine can run during the sleep.
> Always use `asyncio.sleep()` instead.

## Code Review Checklist

Before moving on, here are a few things to check every time you write async
code at this stage:

1. **Every async function call is `await`-ed.** If you see a bare
   `some_async_fn()` without `await` in front of it, that is almost certainly
   a bug.

2. **No blocking calls in async code.** `time.sleep()`,
   `requests.get()`, `open().read()` on large files -- anything that makes the
   thread wait -- will freeze the entire loop. If you must call blocking code,
   use `asyncio.to_thread()` (covered in Chapter 2).

3. **Don't make sync-only functions `async`.** If a function never `await`-s
   anything, it should be a regular `def`. Adding `async` for no reason adds
   overhead and confuses readers about where suspension can happen.

4. **Use `asyncio.run()` exactly once.** It is the top slice of your sandwich.
   Nested `asyncio.run()` calls will raise `RuntimeError`.

5. **Turn on debug mode during development.** Pass `debug=True` to
   `asyncio.run()` to catch common mistakes early.

---
