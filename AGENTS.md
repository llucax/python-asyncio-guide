# AGENTS.md -- Python Asyncio Guide

This repository is a prose-first documentation project for learning Python's
`asyncio`. It contains Markdown sections, embedded Python examples, and
Zensical configuration. It does not contain application code.

There are no Cursor rules in `.cursor/rules/`, no `.cursorrules`, and no
Copilot instructions in `.github/copilot-instructions.md`.

## Repository Shape

- `docs/` holds the guide content.
- `docs/the-basics/`, `docs/beyond-the-basics/`,
  `docs/how-asyncio-works/`, `docs/the-low-level-toolkit/`, and
  `docs/appendices/` are the main chapter directories.
- `docs/index.md` is the guide index.
- `zensical.toml` defines navigation and Markdown extensions.
- `pyproject.toml` only declares package metadata plus a dev dependency on
  `zensical>=0.0.24`.

## Environment And Tooling

- Python: 3.11+ (`.python-version` is `3.11`).
- Package manager: `uv`.
- Docs engine: `zensical`.
- CI builds the site with `zensical build --clean`.
- No configured linter, formatter, or automated test suite exists.
- If `.contai-venv/` exists, prefer it for direct Python commands.
- For repo tooling, prefer `uv run ...`.

## Setup / Build / Preview Commands

- Install dev tools: `uv sync --dev`
- Full docs build: `uv run zensical build --clean`
- Local preview server: `uv run zensical serve`
- Fallback if `uv` is unavailable: `zensical build --clean`
- Fallback preview: `zensical serve`

## Lint / Test Commands

- Lint: not applicable.
- Tests: not applicable.
- Single test: not applicable; this repo has no test suite.

Validation is manual:

1. Run `uv run zensical build --clean` after content or config changes.
2. Optionally run `uv run zensical serve` and inspect affected sections.
3. Check links, headings, admonitions, code fences, diagrams, and navigation.

## Verification Checklist

- Content edits: verify the changed section renders correctly.
- Navigation edits: verify both `docs/index.md` and `zensical.toml`.
- Cross-links: click through in preview rather than assuming anchors.
- Mermaid or admonition edits: verify visually in preview.

## Core Writing Style

- Soft-wrap prose at about 77 characters.
- Use second person and present tense.
- Prefer expanded forms: `do not`, `cannot`, `it is`, `you will`.
- Use ` -- ` for prose dashes. Use a Unicode em dash only where a file
  already uses one intentionally.
- Keep explanations concept-first: establish the mental model, then show code.
- Explain why a pattern exists, not just what to type.
- Assume the reader knows Python well but is new to `asyncio`.

## Structure And Navigation

- Use `chapter` for directory-level units, `section` for Markdown files, and
  `subsection` for in-file H2/H3 units.
- Every section file needs YAML front matter with at least `title` and
  `description`.
- Chapter index sections also include `icon: lucide/book-open`.
- Use ATX headings only (`#`, `##`, `###`).
- Do not put links in headings. If a heading includes Python code or symbols,
  format them with `#!py ...` rather than a Markdown link.
- Keep one blank line between blocks and subsections.
- No trailing whitespace.
- No trailing blank line at end of file.
- Do not add manual Previous/Next links in Markdown.
- Prefer contextual cross-links between related chapters and sections.
- When adding or renaming sections, update the chapter `index.md` section list.
- If the path or chapter structure changes, also update `zensical.toml`.

## Links And Reference Style

- Internal links: use relative Markdown links such as
  `../appendices/debugging.md`.
- In `index.md` overview text, prefer internal cross-links to the guide's own
  headings when describing what a chapter or section covers. Leave external
  API reference links to the section pages themselves.
- Link guide-level concepts to the guide's own sections before linking
  externally.
- For Python stdlib APIs, link to the official Python 3 docs.
- For Trio APIs and concepts, link to the official Trio docs.
- For third-party libraries, prefer official project docs over GitHub when
  possible.
- In prose outside `index.md` overview text, link all meaningful occurrences of
  Python, Trio, and external API mentions, not just the first one in a
  section.
- In prose that is *explaining a nearby code example*, prefer inline
  `#!py ...` for the exact code, symbols, or syntax being discussed.
- In other prose, prefer official-doc cross-links for Python syntax and stdlib
  APIs that have a documentation page, rather than plain inline code.
- Prefer split reference links for readability, for example
  ``[`asyncio.sleep()`][asyncio-sleep]`` with
  `[asyncio-sleep]: https://docs.python.org/...`.
- Use explicit labels, not shortcut references.
- Prefer short labels when unambiguous (`[await]`, `[taskgroup]`).
- Link PEPs directly with their canonical URL.

## Embedded Python Style

These rules apply to runnable examples and Python-flavoured pseudocode.

- Use modern Python 3.11 syntax: `list[str]`, `str | None`, etc.
- Type-annotate function signatures and locals when it improves clarity.
- Prefer small, self-contained examples over framework-heavy code.
- Imports: stdlib only, one import per line, and put `import asyncio` first
  when it is present.
- Use descriptive names such as `main`, `worker`, `queue`, `task`, and
  `deadline`; avoid clever abbreviations.
- Prefer explicit control flow over compact tricks.
- Keep examples cancellation-safe and resource-safe.
- Do not swallow `CancelledError`; if you catch it for cleanup, re-raise it.
- Prefer `async with` for owned resources and structured concurrency.
- Prefer `TaskGroup` over bare `create_task()` in application-level examples
  unless the section is explicitly teaching low-level internals.
- Prefer `python` fences for real examples and `text` fences for output.
- Use `title="filename.py"` when a filename helps.
- For inline Python syntax in prose, use `#!py` when discussing code from a
  nearby example, for example `#!py async with sem:`.
- Preferred entry point:

  ```python
  async def main() -> None:
      ...

  if __name__ == "__main__":
      asyncio.run(main())
  ```

## Asyncio Content Guidelines

- Link meaningful mentions of `asyncio` APIs in prose to the official docs,
  except in `index.md` overview text where you should point to internal guide
  headings first.
- Keep cancellation guidance consistent: cancellation arrives at checkpoints,
  not at arbitrary points.
- Prefer structured concurrency terminology and patterns.
- Keep `The Basics` beginner-friendly but technically precise.
- Preserve the "Code Review Checklist" pattern on introductory sections when it
  fits.

## Terminology, Admonitions, And Diagrams

- Use the repository's chapter names exactly, for example `The Basics`.
- Be consistent with coroutine, coroutine function, task, awaitable, event
  loop, checkpoint, and cancellation.
- Prefer `Python interpreter` over `compiler` when describing syntax rules.
- Use capitalized admonition markers: `!!! Note`, `!!! Tip`, `!!! Info`,
  `!!! Warning`, `!!! Danger`, `!!! Example`.
- Use `!!! Tip "Trio"` for Trio comparisons.
- Mermaid is supported. Prefer simple diagrams that clarify a concept.

## Agent Guidance

- Treat this repo as documentation, not as a Python package to refactor.
- Before changing conventions, inspect nearby sections and preserve the voice.
- Be careful with bulk replacements; navigation and link-style changes can
  affect many sections at once.
- Never assume tests exist; say explicitly when validation is manual.
- If you change content conventions, update this file too.
