# Evaluation (GPT5.4)

**Verdict**
- If you keep one, keep `python/asyncio-v2/`.
- It is the best balance of structure, clarity, completeness, real-world usefulness, and publish-readiness.
- `new-guide-tmp/` is the strongest alternate draft, but it still feels like a draft.
- `python/asyncio/` has some of the best individual teaching sections, but not the best overall package.
- `python/asyncio-v3/` is the cleanest concise version, but too thin to be the canonical guide.

**Scorecard**
```text
Version             Org  Read  Friendly  Depth  Complete  Examples  Practical  Nav  Polish  Overall
python/asyncio-v2    9     9       9       9        9         9         9      9      9      9.0
new-guide-tmp        7     8       8       8        8         8         7      4      6      7.1
python/asyncio       5     8       7       8        7         9         7      5      5      6.8
python/asyncio-v3    8     8       7       7        5         7         6      4      7      6.6
```

**Why v2 wins**
- Best top-level structure and reading path in `python/asyncio-v2/index.md:32`.
- Best beginner onboarding in `python/asyncio-v2/01-everyday-asyncio/getting-started.md:20`; it shows common mistakes, fixes them, and includes expected output.
- Best practical coverage: real streams in `python/asyncio-v2/01-everyday-asyncio/streams.md:6`, subprocesses in `python/asyncio-v2/02-beyond-the-basics/subprocesses.md:6`, low-level networking in `python/asyncio-v2/04-the-low-level-toolkit/transports-and-protocols.md:6`.
- Best long-term reference value: chapter indexes, appendices, and even a testing-oriented `Runner` pattern in `python/asyncio-v2/02-beyond-the-basics/runner.md:141`.
- It feels finished, whereas the others feel either incomplete, experimental, or draft-like.

**Guide-by-guide notes**
- `python/asyncio-v2/`
  - Best overall.
  - Strongest combination of tutorial + reference.
  - Weak spots are mostly editorial: a few overly absolute statements in `python/asyncio-v2/01-everyday-asyncio/concurrent-tasks.md:57` and some checkpoint claims that should be audited in `python/asyncio-v2/appendices/checkpoint-contract.md:47`.

- `new-guide-tmp/`
  - Strong second place.
  - Good onboarding in `new-guide-tmp/everyday-asyncio.md:23` and a very useful debugging appendix in `new-guide-tmp/appendix-debugging.md:47`.
  - Main problem is packaging: flat files, weaker navigation, less polished finish.
  - Also has a couple of technical inconsistencies, like the `communicate()` deadlock warning in `new-guide-tmp/asyncio-in-practice.md:236` and the `get_event_loop()` example in `new-guide-tmp/everyday-asyncio.md:633`.

- `python/asyncio/`
  - Best standout teaching moments.
  - The execution trace in `python/asyncio/tutorial/first-async-program.md:216` is excellent.
  - The actor pipeline in `python/asyncio/tutorial/building-real-applications.md:53` is probably the best single tutorial section across all four.
  - But the entry point is badly broken: `python/asyncio/index.md:52` points to files that do not exist, and there is at least one flawed example in `python/asyncio/core/communication-and-synchronization.md:387`.

- `python/asyncio-v3/`
  - Best if you want a short, fast read.
  - Nice concise intro in `python/asyncio-v3/01-everyday-basics/01-introduction.md:5` and good cancellation internals in `python/asyncio-v3/03-understanding-asyncio/03-cancellation-internals.md:38`.
  - But it is too thin on real-world coverage, and there is no root `python/asyncio-v3/index.md`, which hurts navigation.

**What I would keep from the other versions**
- From `python/asyncio/tutorial/building-real-applications.md:53`: add a capstone “real application” tutorial to `python/asyncio-v2/`.
- From `python/asyncio/tutorial/first-async-program.md:216`: add the numbered execution trace to `python/asyncio-v2/`.
- From `new-guide-tmp/everyday-asyncio.md:23`: add the explicit prerequisites/on-ramp framing.
- From `python/asyncio-v3/01-everyday-basics/01-introduction.md:5`: borrow some of the brevity; `python/asyncio-v2/` is strongest, but sometimes heavier than it needs to be.

**What is still missing even in the best version**
- A real async testing section; `python/asyncio-v2/02-beyond-the-basics/runner.md:141` helps, but it is not enough on its own.
- More ecosystem guidance: HTTP clients, DB drivers, choosing async libraries.
- A few production patterns like retry/backoff, pooling, and performance tradeoffs.

My recommendation: keep `python/asyncio-v2/` as the canonical guide, mine `python/asyncio/` for the actor-pipeline and execution-trace material, and optionally mine `new-guide-tmp/` for onboarding phrasing. Retire `python/asyncio-v3/` unless you want a separate short-form companion.

If you want, I can next turn this into a concrete merge plan: exactly what to copy from which files into `python/asyncio-v2/`.

---

