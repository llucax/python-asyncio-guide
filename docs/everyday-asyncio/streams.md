---
title: Streams
description: >-
  Build TCP clients and servers with asyncio's Streams API. Use
  asyncio.open_connection() and asyncio.start_server() with StreamReader
  and StreamWriter for clean async networking.
---

# Streams

Everything up to this point has used `asyncio.sleep()` as a stand-in for real
work. Streams are where asyncio earns its keep: actual TCP networking with
clean async/await syntax. The streams API gives you a high-level interface for
reading and writing bytes over the network -- no callbacks, no protocol
classes, just a reader and a writer that you `await` like anything else.

## Opening a Client Connection

[`asyncio.open_connection()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection)
opens a TCP connection and returns a `(StreamReader, StreamWriter)` tuple. The
reader is for receiving data, the writer is for sending it.

Here is a minimal client that connects to an HTTP server, sends a request, and
reads the response:

```python
# http_client.py
import asyncio

async def main() -> None:
    reader, writer = await asyncio.open_connection("example.com", 80)

    request: bytes = b"GET / HTTP/1.0\r\nHost: example.com\r\n\r\n"
    writer.write(request)
    await writer.drain()

    response: bytes = await reader.read(4096)
    print(response[:200].decode())

    writer.close()
    await writer.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python http_client.py
HTTP/1.0 200 OK
Content-Type: text/html; charset=UTF-8
...
```

A few things to notice. `open_connection()` is a coroutine -- the TCP
handshake happens during the `await`. The writer's `.write()` method buffers
data synchronously (no `await`), but `.drain()` is a coroutine that waits for
the buffer to flush. And at the end, you must call both `.close()` and
`.wait_closed()` -- more on that shortly.

!!! warning

    Always close the writer when you are done. An unclosed writer leaks a socket
    and its associated file descriptor. The reader does not need to be closed
    separately -- closing the writer shuts down the underlying connection.

## `StreamReader`

[`asyncio.StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader)
is the read side of a stream. All of its read methods are coroutines -- each
one is a *checkpoint* that may suspend while waiting for data from the network.

The main methods:

- **[`.read(n)`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.read)**
  -- read *up to* `n` bytes. Returns fewer if fewer are available. Returns
  `b""` at EOF. This is the most common read method.
- **[`.readline()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readline)**
  -- read until `\n` (inclusive). If EOF is reached before a newline, returns
  whatever is left.
- **[`.readexactly(n)`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readexactly)**
  -- read exactly `n` bytes. Raises
  [`asyncio.IncompleteReadError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.IncompleteReadError)
  if EOF is reached before `n` bytes have been read. Use this when your
  protocol defines fixed-size messages.
- **[`.readuntil(separator)`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readuntil)**
  -- read until `separator` is found in the stream (inclusive). Raises
  `asyncio.IncompleteReadError` if EOF comes first, or
  `asyncio.LimitOverrunError` if the internal buffer limit is exceeded before
  the separator appears.
- **[`.at_eof()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.at_eof)**
  -- returns `True` if the read buffer is empty *and* the connection has been
  closed by the remote end. This is not a coroutine.

The pattern for reading until the remote end disconnects:

```python
while not reader.at_eof():
    chunk: bytes = await reader.read(4096)
    if not chunk:
        break
    process(chunk)
```

!!! tip

    `.read(n)` returning `b""` and `.at_eof()` returning `True` both indicate
    EOF, but they serve different purposes. Use `read()` return value checks in
    loops where you are consuming data; use `at_eof()` when you need a
    non-blocking check outside of a read call.

## `StreamWriter`

[`asyncio.StreamWriter`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter)
is the write side. Writing works differently from reading: you buffer data
synchronously, then flush asynchronously.

- **[`.write(data)`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write)**
  -- buffer `data` (a `bytes` object) for sending. This returns `None`
  immediately -- it does **not** await. The data is queued in an internal
  buffer and sent by the event loop when the socket is ready.
- **[`.writelines(data)`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.writelines)**
  -- buffer a list of `bytes` objects. Same as calling `.write()` for each
  item, but potentially more efficient. Also not a coroutine.
- **[`.drain()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain)**
  -- wait for the write buffer to be flushed to the OS. This **is** a
  coroutine and a checkpoint. This is where *backpressure* happens: if the
  remote end is reading slowly, the OS send buffer fills up, and `drain()`
  will suspend your coroutine until there is room.
- **[`.close()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.close)**
  -- initiate closing the underlying connection. Not a coroutine.
- **[`.wait_closed()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.wait_closed)**
  -- wait for the connection to actually close. This is a coroutine.

The *write/drain dance* is the core pattern: call `.write()` to buffer, call
`await .drain()` to flush. You must call `drain()` after writing -- otherwise
you can pile up unbounded data in the buffer without ever giving the event loop
a chance to send it (or to tell you the remote end is gone).

```python
writer.write(b"Hello, ")
writer.write(b"world!\n")
await writer.drain()  # Flush both writes to the network
```

!!! warning

    `.write()` does not raise if the connection has been lost. The error only
    surfaces when you call `drain()` (or `close()`). If you forget `drain()`,
    you may silently write into a broken pipe for a long time before noticing.

## Resource Management for Streams

Always close writers. Always call `wait_closed()` after `close()`. The
`.close()` method starts the shutdown process, but `.wait_closed()` is the
coroutine that waits for it to complete -- including flushing any remaining
buffered data and tearing down the TLS layer if one exists.

The standard pattern is `try`/`finally`:

```python
reader, writer = await asyncio.open_connection(host, port)
try:
    writer.write(b"hello\n")
    await writer.drain()
    response: bytes = await reader.readline()
finally:
    writer.close()
    await writer.wait_closed()
```

!!! danger

    `StreamWriter` is **not** an async context manager in the standard library
    (as of Python 3.13). You cannot write `async with writer:`. You must call
    `.close()` and `.wait_closed()` manually in a `try`/`finally` block. Some
    third-party libraries add this, but the stdlib does not provide it.

If you want to keep things tidy, you can write a small helper:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

@asynccontextmanager
async def open_stream(
    host: str, port: int
) -> AsyncIterator[tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()
```

This lets you write `async with open_stream(host, port) as (reader, writer):`
and get automatic cleanup. But understand what it does under the hood -- you
will encounter plenty of code that uses the manual pattern.

## Building a TCP Server

[`asyncio.start_server()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_server)
starts a TCP server. You give it a *callback* that is called with a
`(StreamReader, StreamWriter)` pair for each new incoming connection. The
callback can be a coroutine function -- asyncio will schedule it as a task
automatically.

Here is a simple echo server:

```python
# echo_server.py
import asyncio

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    addr: tuple[str, int] = writer.get_extra_info("peername")
    print(f"New connection from {addr}")

    try:
        while True:
            data: bytes = await reader.readline()
            if not data:
                break
            print(f"Received: {data.decode().strip()!r} from {addr}")
            writer.write(data)
            await writer.drain()
    finally:
        print(f"Closing connection from {addr}")
        writer.close()
        await writer.wait_closed()

async def main() -> None:
    server: asyncio.Server = await asyncio.start_server(
        handle_client, "127.0.0.1", 8888
    )
    addrs = [s.getsockname() for s in server.sockets]
    print(f"Serving on {addrs}")

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python echo_server.py
Serving on [('127.0.0.1', 8888)]
```

A few details worth noting.
[`asyncio.Server`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.Server)
is an async context manager -- `async with server:` ensures the server is
closed and cleaned up when the block exits. Inside the block,
[`server.serve_forever()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.Server.serve_forever)
runs until the server is stopped or cancelled.

The callback `handle_client` is responsible for its own writer cleanup. Each
connection is handled independently -- if one client disconnects, the others
keep going. The `try`/`finally` ensures the writer is closed even if the
client disconnects unexpectedly or the read raises an exception.

!!! note

    `start_server()` spawns each callback as an independent task. This means
    errors in one connection do not propagate to the server or to other
    connections. If you want centralised error handling, catch exceptions inside
    the callback and log them.

## Complete Example: Echo Client and Server

Let's put both sides together into a single runnable program. The server echoes
lines back, and the client sends a few messages and reads the echoes. A
`TaskGroup` starts the server, runs the client, and shuts everything down
cleanly.

```python
# echo_client_server.py
import asyncio

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    addr = writer.get_extra_info("peername")
    try:
        while True:
            data: bytes = await reader.readline()
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
        print(f"Server: connection from {addr} closed")

async def run_client(port: int) -> list[str]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    results: list[str] = []

    try:
        messages: list[str] = ["Hello", "asyncio", "streams"]
        for msg in messages:
            writer.write(f"{msg}\n".encode())
            await writer.drain()

            response: bytes = await reader.readline()
            decoded: str = response.decode().strip()
            print(f"Client: sent {msg!r}, got {decoded!r}")
            results.append(decoded)
    finally:
        writer.close()
        await writer.wait_closed()

    return results

async def main() -> None:
    server: asyncio.Server = await asyncio.start_server(
        handle_client, "127.0.0.1", 0  # Port 0 = pick a free port
    )

    async with server:
        port: int = server.sockets[0].getsockname()[1]
        print(f"Server: listening on port {port}")

        async with asyncio.TaskGroup() as tg:
            client_task = tg.create_task(run_client(port))

        print(f"Results: {client_task.result()}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python echo_client_server.py
Server: listening on port 41233
Client: sent 'Hello', got 'Hello'
Client: sent 'asyncio', got 'asyncio'
Client: sent 'streams', got 'streams'
Server: connection from ('127.0.0.1', 54321) closed
Results: ['Hello', 'asyncio', 'streams']
```

A few things to note about this example. The server uses port `0`, which tells
the OS to pick an available port -- this avoids "address already in use" errors
when running examples. The `TaskGroup` runs the client task; when the client
finishes, the group exits, and the `async with server:` block exits, stopping
the server cleanly. No manual cancellation needed -- structured concurrency
takes care of shutdown.

!!! tip

    Using port `0` is a good practice for tests and examples. In production you
    will bind to a specific port, but for development it avoids a whole class of
    annoying startup errors.

## Timeouts on Stream Operations

Network operations can hang indefinitely if the remote end stops responding.
Wrap stream reads and writes in
[`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout)
to enforce deadlines:

```python
# stream_timeout.py
import asyncio

async def cautious_read(
    reader: asyncio.StreamReader,
    timeout_seconds: float,
) -> bytes | None:
    try:
        async with asyncio.timeout(timeout_seconds):
            data: bytes = await reader.readline()
            return data if data else None
    except TimeoutError:
        print("Read timed out")
        return None

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    addr = writer.get_extra_info("peername")
    try:
        while True:
            data: bytes | None = await cautious_read(reader, timeout_seconds=5.0)
            if data is None:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
        print(f"Connection from {addr} closed")

async def main() -> None:
    server = await asyncio.start_server(handle_client, "127.0.0.1", 8888)
    async with server:
        print("Serving with 5s read timeout...")
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
```

The `cautious_read` function wraps a single `readline()` in a 5-second
timeout. If the client goes silent for too long, the read is cancelled and the
server can drop the connection. You can apply the same pattern to writes --
wrap the `drain()` call in `asyncio.timeout()` to guard against slow
consumers.

!!! warning

    A timeout on `.write()` alone does nothing useful -- `.write()` is
    synchronous and returns immediately. Put the timeout around `.drain()`,
    which is the coroutine that actually waits for the buffer to flush.

---
