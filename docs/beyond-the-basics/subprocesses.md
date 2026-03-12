---
title: Subprocesses
description: >-
  A concise guide to asyncio subprocesses. Learn when to use
  create_subprocess_exec() or create_subprocess_shell(), how to avoid pipe
  deadlocks, and when to lean on the official docs for full details.
---

# Subprocesses

Running external commands is common in async programs. You might call `git`,
`ffmpeg`, or another CLI tool as one step in a larger workflow.

This is a good place to lean on the official docs. Python's subprocess coverage
is already solid, so this section stays focused on the choices and pitfalls that
matter most when you are learning asyncio.

!!! Info

    Read this section for the shape of the API and the safety rules. Use the
    official docs for the full signatures, all stream options, and platform
    details:
    [Subprocesses][subprocesses].

## `#!py exec()` vs `#!py shell()`

Use [`asyncio.create_subprocess_exec()`][create-subprocess-exec] by default.
Pass the program and its arguments separately:

```python
proc = await asyncio.create_subprocess_exec(
    "git",
    "status",
    "--short",
    stdout=asyncio.subprocess.PIPE,
)
```

Use [`asyncio.create_subprocess_shell()`][create-subprocess-shell] only when you
genuinely need shell features such as pipes, glob expansion, or `&&` chaining.

```python
proc = await asyncio.create_subprocess_shell(
    "printf 'a\n' | wc -l",
    stdout=asyncio.subprocess.PIPE,
)
```

!!! Danger

    Never pass untrusted input to [`create_subprocess_shell()`][create-subprocess-shell]. If the command
    string contains attacker-controlled text, you have a shell-injection bug.

## The Default Pattern: `communicate()`

If you want to send optional stdin, collect stdout and stderr, and wait for the
child to finish, use [`Process.communicate()`][process-communicate].

```python title="subprocess_exec.py"
import asyncio


async def main() -> None:
    proc = await asyncio.create_subprocess_exec(
        "python",
        "-c",
        "print('hello from child')",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()
    print(stdout.decode().strip())
    print(f"return code: {proc.returncode}")
    if stderr:
        print(stderr.decode().strip())


if __name__ == "__main__":
    asyncio.run(main())
```

This is the safest default because it handles stdin, stdout, stderr, and child
termination together.

## The Main Pitfall: Pipe Deadlocks

If you open `stdout=PIPE` or `stderr=PIPE`, do not just call [`await proc.wait()`][await-proc-wait]
and ignore the pipes. A child can block trying to write into a full pipe while
you block waiting for it to exit.

That is why the safe default is:

- [`communicate()`][communicate] when you want all output at the end
- manual stream reading *plus* [`wait()`][wait] when you want output incrementally

## Streaming Output

For long-running processes, you can treat `proc.stdout` and `proc.stderr` as
stream readers and consume them as data arrives.

```python
proc = await asyncio.create_subprocess_exec(
    "python",
    "-c",
    "import time\nfor i in range(3):\n print(i, flush=True); time.sleep(0.2)",
    stdout=asyncio.subprocess.PIPE,
)

assert proc.stdout is not None
while True:
    line = await proc.stdout.readline()
    if not line:
        break
    print(f"child: {line.decode().strip()}")

await proc.wait()
```

That final [`await proc.wait()`][await-proc-wait] still matters. Reading the pipes does not by
itself reap the process.

## What to Read Next

- Full subprocess reference: [Subprocesses][subprocesses]
- Stream behavior, since subprocess pipes use the same high-level model:
  [Streams][streams]
- Blocking-process integration and executor choices:
  [Blocking Code](blocking-code.md)

[create-subprocess-exec]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_exec
[create-subprocess-shell]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_shell
[process-communicate]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.communicate
[subprocesses]: https://docs.python.org/3/library/asyncio-subprocess.html
[streams]: https://docs.python.org/3/library/asyncio-stream.html
[await-proc-wait]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.wait
[communicate]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.communicate
[wait]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.wait