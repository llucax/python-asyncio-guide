# Asyncio Guide -- Comparative Evaluation Report

## Overview

| Version | Location | Files | Word Count | Status |
|---------|----------|------:|----------:|--------|
| **new-guide-tmp** | `new-guide-tmp/` | 7 | ~16,300 | Draft (flat files, no directory structure) |
| **v1** | `python/asyncio/` | 12 | ~21,700 | Incomplete (index references nonexistent files) |
| **v2** | `python/asyncio-v2/` | 30 | ~42,600 | Complete and self-consistent |
| **v3** | `python/asyncio-v3/` | 16 | ~6,200 | Compact but thin on several topics |

All four versions target Python 3.11+, are inspired by Trio's documentation style, and promote structured concurrency (TaskGroup over bare create_task). They share a common pedagogical philosophy: concepts before APIs, modern patterns first, legacy deferred.

---

## Scoring (1-10 scale)

| Criterion | new-guide-tmp | v1 | v2 | v3 |
|-----------|:---:|:---:|:---:|:---:|
| **Organization & Structure** | 6 | 5 | 9 | 8 |
| **Readability & Clarity** | 8 | 8 | 9 | 8 |
| **Beginner Friendliness** | 8 | 7 | 9 | 7 |
| **Technical Depth** | 7 | 8 | 9 | 6 |
| **Completeness (topic coverage)** | 6 | 5 | 9 | 4 |
| **Code Examples Quality** | 7 | 9 | 9 | 7 |
| **Practical Applicability** | 5 | 6 | 9 | 4 |
| **Navigation & Cross-referencing** | 3 | 6 | 9 | 3 |
| **Reference Value** | 7 | 7 | 9 | 6 |
| **Consistency & Polish** | 6 | 5 | 9 | 7 |
| **OVERALL** | **6.3** | **6.6** | **9.0** | **6.0** |

---

## Detailed Analysis by Criterion

### 1. Organization & Structure

**v2 (9/10)** has the best structure by far. Four progressively deeper chapters (Everyday Asyncio -> Beyond the Basics -> How Asyncio Works -> The Low-Level Toolkit) plus three appendices. Every chapter has its own `index.md` with a section summary. The layering is deliberate: Chapters 1-2 are sufficient for application developers, Chapter 3 satisfies curiosity about internals, Chapter 4 serves framework authors. The appendices provide consolidated reference material (checkpoint contract, 20-rule best practices, full debugging guide). This "stop when you've had enough" design is the right choice for a guide serving multiple skill levels.

**v3 (8/10)** mirrors v2's 4-chapter arc (Everyday Basics -> Everyday Advanced -> Understanding Asyncio -> Building Tools) and gets the progression right, but has no top-level index file linking everything together. A reader must rely on filesystem ordering to navigate.

**v1 (5/10)** has a split personality: a `tutorial/` directory with 5 progressive files and a `core/` directory with 6 reference-style files. The problem is the index.md references a *different* structure (chapters 1-4 plus 3 appendices) that maps to files that don't exist. A reader starting at the index hits dead links immediately. The actual tutorial/core split is reasonable but the broken index is a serious organizational failure.

**new-guide-tmp (6/10)** is 7 flat files with no directory structure. The content itself follows a logical progression (everyday -> in practice -> how it works -> building tools -> appendices), but there's no index, no navigation, and the flat file layout makes it unclear how a reader should proceed.

### 2. Readability & Clarity

All four versions share a conversational-but-precise writing style with second-person ("you") address. The writing quality is uniformly good across versions -- this is clearly the same author iterating.

**v2 (9/10)** edges ahead because it has the most room to explain concepts fully. Each section follows a consistent pattern: motivation -> problem statement -> solution with code -> gotchas/caveats with admonition boxes. The transitions between sections are smooth, with each file ending with text that bridges to the next topic.

**v1 and new-guide-tmp (both 8/10)** are well-written, with v1's "two questions" mental model ("who owns the lifetime?" and "where are the suspension points?") being an especially effective heuristic. The new-guide-tmp version has slightly tighter prose.

**v3 (8/10)** is clear and direct, benefiting from extreme conciseness. Individual sections read quickly (2-3 minutes each). The trade-off is that some topics feel rushed.

### 3. Beginner Friendliness

**v2 (9/10)** is the most welcoming. It starts from zero (explaining what a coroutine object is before any code), shows the "wrong" way first (`wrong_call.py` with the RuntimeWarning), then fixes it. The "async sandwich" metaphor anchors the async/sync boundary concept. Every code example includes a simulated `$ python filename.py` output block so beginners can verify their understanding without running code. Admonition boxes (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`) provide sidebar context without breaking the main narrative flow. The deliberate deferral of `create_task()` until Chapter 3 prevents beginners from learning the wrong API first.

**new-guide-tmp (8/10)** uses the same pedagogical approach and explicitly states prerequisites ("You do not need prior experience with threads or event loops"). Good.

**v1 (7/10)** starts well (the tutorial begins with the forgetting-await mistake) but the core/ section assumes the tutorial has been read and doesn't re-explain terms. The broken index would immediately confuse a beginner. The checkpoint contract table in `execution-model.md` is dense and could overwhelm someone who jumps there early.

**v3 (7/10)** starts with a restaurant/cook analogy that works well, but has no prerequisites section. The first code example (`fetch_data`) returns a value that's never used -- a minor dangling thread that could confuse a beginner. The lack of shown output for code examples means beginners must run every snippet or mentally trace concurrent execution, which is challenging.

### 4. Technical Depth

**v2 (9/10)** goes deepest. Specific highlights:
- Event loop internals with a 3-phase iteration model and pseudocode
- `Task.__step` pseudocode showing exactly how a task drives its coroutine
- Cancellation counter (`cancelling()`/`uncancel()`) with worked examples
- How `timeout()` and `TaskGroup` use cancel/uncancel internally
- 7-step `asyncio.run()` shutdown sequence (leaked task handling, async gen finalization, executor shutdown)
- Transports and protocols with flow control and ASCII watermark diagrams
- Signal handling via `add_signal_handler()`
- `run_coroutine_threadsafe()` for cross-thread communication

**v1 (8/10)** is also technically deep. Its pseudocode event loop model, checkpoint contract table, and cancellation counter explanations are excellent. The actor pipeline in `building-real-applications.md` is one of the best asyncio tutorials available anywhere -- building from ~30 lines to ~120 lines across 4 incremental steps with fan-out, nested TaskGroups, type-safe sentinels, and match/case. However, the depth is concentrated in what exists; missing sections (streams, subprocesses, protocols) reduce the overall score.

**new-guide-tmp (7/10)** covers internals and the checkpoint contract well, but goes less deep on cancellation mechanics and lacks the shutdown sequence coverage.

**v3 (6/10)** covers the cancellation counter (which is rare and valuable) but stays conceptual on event loop internals. No selectors, no `_run_once`, no pseudocode models. The brevity limits depth.

### 5. Completeness (Topic Coverage)

This is where the versions diverge most dramatically.

**v2 (9/10)** covers essentially everything an asyncio developer needs:

| Topic | v2 | v1 | new-guide-tmp | v3 |
|-------|:--:|:--:|:--:|:--:|
| Coroutines & await | Yes | Yes | Yes | Yes |
| asyncio.run() | Yes | Yes | Yes | Yes |
| TaskGroup | Yes | Yes | Yes | Yes |
| ExceptionGroup / except* | Yes | Yes | Yes | **No** |
| Cancellation basics | Yes | Yes | Yes | Yes |
| Cancellation internals (counter) | Yes | Yes | Yes | Yes |
| Timeouts (timeout/timeout_at) | Yes | Yes | Yes | Yes |
| Streams (TCP client/server) | **Yes** | No | No | No |
| Subprocesses | **Yes** | No | No | No |
| Transports & Protocols | **Yes** | No | No | No |
| Queue / bounded queues / backpressure | Yes | Yes | Yes | Partial |
| Lock, Event, Semaphore | Yes | Yes | Yes | Partial |
| Condition, Barrier, BoundedSemaphore | **Yes** | Partial | Partial | **No** |
| Async iterators/generators | Yes | Partial | Partial | Yes |
| aclosing() | Yes | Yes | Yes | Yes |
| Async context managers | **Yes** | Partial | Partial | Yes |
| AsyncExitStack | **Yes** | Yes | Partial | No |
| asyncio.shield() | Yes | Yes | Yes | Yes |
| asyncio.to_thread() | Yes | Yes | Yes | Yes |
| ProcessPoolExecutor | Yes | Yes | Partial | Partial |
| asyncio.Runner | **Yes** | Partial | Partial | No |
| gather/wait/as_completed/wait_for | **Yes** | Table only | Partial | Yes |
| Futures (low-level) | **Yes** | Yes | Partial | Partial |
| Callbacks & threading | **Yes** | No | No | No |
| Signal handling | **Yes** | Brief | No | No |
| Shutdown sequence | **Yes** | Yes | No | No |
| Debug mode | Yes | Yes | Yes | Yes |
| Debugging guide (diagnostic patterns) | **Yes** | No | Yes | No |
| Best practices (consolidated) | **Yes** | No | Yes | Partial |
| Checkpoint contract table | Yes | Yes | Yes | Yes |

v2 is the only version that covers real networking (streams with TCP client and echo server examples), subprocesses, transports/protocols, signal handling, cross-thread communication, and has a comprehensive debugging appendix. These are not niche topics -- streams and subprocesses are core use cases for an I/O framework.

**v3 (4/10)** is the thinnest. It notably omits ExceptionGroup/except* (critical since TaskGroup is its centerpiece), has only one-sentence mentions of Event and Condition with no code, omits Barrier entirely, has no networking at all, no Runner, and no index file.

### 6. Code Examples Quality

**v2 and v1 (both 9/10)** lead here. Both provide:
- Complete, runnable files with imports, `main()`, and `asyncio.run()`
- Consistent type annotations throughout
- Expected output shown after every example

v2 adds filenames as comments (`# echo_server.py`) and shows output as `$ python filename.py` blocks, making examples feel like real scripts you'd save and run. v2 also includes real I/O examples (TCP client, echo server, subprocess execution) rather than exclusively `asyncio.sleep()` stand-ins.

v1's unique strength is the incremental actor pipeline in `building-real-applications.md` -- this is a genuine production-quality example built in 4 progressive steps. No other version has anything comparable.

**new-guide-tmp and v3 (both 7/10)** have complete runnable examples but v3 never shows expected output (the reader must run or mentally trace). Both rely exclusively on `asyncio.sleep()` for all examples.

### 7. Practical Applicability

**v2 (9/10)** is the only version a developer could use as their primary asyncio learning resource and feel prepared for real work. It covers actual TCP networking, subprocess management, thread integration, and signal handling -- the things you actually do with asyncio. The 20-rule best practices appendix with cross-references to explanations is immediately actionable.

**v1 (6/10)** has the excellent actor pipeline, but otherwise relies entirely on `asyncio.sleep()`. A reader would learn the mechanics of concurrency without seeing how to apply them to real I/O.

**new-guide-tmp (5/10)** and **v3 (4/10)** would leave a reader understanding the theory but unprepared for practical application.

### 8. Navigation & Cross-referencing

**v2 (9/10)** has Previous/Next links on every page, chapter index files listing all sections with summaries, extensive internal cross-references between sections, and the best practices appendix links back to the specific chapter section for each rule. Links to official Python docs for every API mentioned. Trio user callouts (`> [!TIP] **Trio users:**`) throughout.

**v1 (6/10)** has prev/next links and cross-references between tutorial and core sections, plus good external links to Python docs.

**v3 (3/10)** and **new-guide-tmp (3/10)** have no navigation links, no index files (v3), and no cross-referencing system.

### 9. Reference Value

**v2 (9/10)** has the highest reference value thanks to three appendices: the checkpoint contract table (categorizing every API as always/conditionally/never suspends), the 20-rule best practices with quick reference table, and the debugging guide with specific diagnostic patterns for blocked loops, task leaks, deadlocks, and timeout failures. These are the kind of pages developers bookmark.

**v1 (7/10)** has the checkpoint contract table (the original, equally good) and the core/ section serves as a decent reference, but lacks consolidated best practices or debugging reference.

### 10. Consistency & Polish

**v2 (9/10)** is the most polished. Every file follows the same format: Previous/Next links, introductory paragraph, H2 sections with concept -> code -> output -> caveats, consistent admonition usage, consistent code style. No broken links, no references to nonexistent content. Chapter transitions are smooth.

**v3 (7/10)** is consistent within its scope -- every file follows the same structure pattern. Clean but minimal.

**v1 (5/10)** has a broken index, redundancy between tutorial and core sections (cancellation and TaskGroup covered twice with near-identical shielding examples), and the `communication-and-synchronization.md` file at 882 lines is too long and should be split.

**new-guide-tmp (6/10)** is clearly a draft. The flat file structure and lack of navigation suggest this is an intermediate artifact, not a finished product.

---

## Recommendation

**Keep v2 (`python/asyncio-v2/`).** It is the clear winner across every evaluation criterion. It is the most complete, best organized, most polished, most practical, and most navigable version. It is the only version that covers real networking, subprocesses, and transports/protocols -- core use cases for an I/O framework. The layered chapter architecture serves beginners through framework authors. The three appendices provide genuine reference value.

The other three versions appear to be earlier iterations leading to v2:
- **new-guide-tmp** looks like an early draft exploring the structure
- **v1** developed the tutorial/core split but was left incomplete
- **v3** appears to be an experiment in extreme conciseness that sacrificed too much

---

## What v2 Could Still Improve (Drawing From Other Versions)

Despite being the best version, v2 has some gaps and could incorporate strengths from the other versions:

### Missing from v2 that other versions do better

1. **v1's actor pipeline tutorial.** v1's `building-real-applications.md` builds a production-quality actor pipeline incrementally across 4 steps (simple -> backpressure -> error handling -> fan-out with type-safe sentinels). This is v1's single best piece of content and has no equivalent in v2. v2 could add a similar end-to-end "building a real application" section, perhaps as a capstone to Chapter 2 or as a standalone tutorial.

2. **v1's "two questions" mental model.** v1's `mental-model.md` introduces "who owns the lifetime of this work?" and "where are the suspension points?" as the two questions to ask about any async code. This is a powerful heuristic absent from v2.

3. **v1's execution trace walkthrough.** v1's `first-async-program.md` numbers each step of the event loop's scheduling for a concurrent example, showing exactly what runs when. v2 explains scheduling conceptually but doesn't do this step-by-step trace, which is valuable for building intuition.

### Topics missing from all versions

4. **Testing async code.** None of the four versions cover `pytest-asyncio`, `unittest.IsolatedAsyncioTestCase`, mocking async functions, or testing patterns. This is a significant gap -- testing is one of the most common pain points for asyncio developers.

5. **Third-party library integration.** No coverage of `aiohttp`, `httpx`, database drivers (asyncpg, aiosqlite), or how to evaluate and integrate async libraries. Even a brief "ecosystem overview" section would help.

6. **Retry and backoff patterns.** Common in production async code, not covered anywhere.

7. **Connection pooling patterns.** A frequent real-world need with async database/HTTP clients.

8. **Performance considerations.** When to choose asyncio vs threading vs multiprocessing, and how to benchmark async code.

### Polish improvements for v2

9. **The debugging section in Chapter 1** (`01-everyday-asyncio/debugging.md` at 171 lines) feels thin compared to the appendix debugging guide (418 lines). Consider whether the Ch1 section pulls its weight or if it should be folded into the appendix with a brief pointer from Ch1.

10. **Exercises or challenges.** All versions are read-only. Adding optional exercises ("modify this example to add retry logic", "make this echo server handle multiple connections") would strengthen learning retention.

11. **Migration guide.** v2 positions `gather`/`wait_for` as legacy but doesn't provide a systematic "if you have X, replace with Y" migration table for developers modernizing existing codebases.

---

## Assistant

That's the full report. The short version:

**v2 wins decisively** (9.0/10 overall vs 6.0-6.6 for the others). It's the most complete, best organized, and only version with real I/O examples (TCP streams, subprocesses, transports/protocols). The other three versions read like progressive iterations toward v2.

The most valuable things v2 could still absorb from the others are v1's incremental actor pipeline tutorial (genuinely excellent teaching material), v1's "two questions" mental model, and v1's step-by-step execution trace. The biggest gap across all four versions is the total absence of testing guidance.
