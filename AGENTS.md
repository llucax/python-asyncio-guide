# AGENTS.md -- Python Asyncio Guide

This repository is a prose-first documentation project for learning
Python's `asyncio`. It contains Markdown pages, embedded example snippets,
and Zensical configuration. It does not contain application code.

There are no Cursor rules in `.cursor/rules/`, no `.cursorrules`, and no
Copilot instructions in `.github/copilot-instructions.md`.

## Repository Shape

```text
docs/
  index.md
  the-basics/
  beyond-the-basics/
  how-asyncio-works/
  the-low-level-toolkit/
  appendices/
zensical.toml
pyproject.toml
uv.lock
```

- `docs/` contains the guide content.
- `zensical.toml` defines navigation and Markdown extensions.
- `pyproject.toml` only declares package metadata plus a dev dependency on
  `zensical`.

## Environment And Tooling

- Python: 3.11+ (`.python-version` is `3.11`).
- Package manager: `uv`.
- Docs engine: `zensical`.
- CI build command from `.github/workflows/docs.yml`:

  ```sh
  zensical build --clean
  ```

- There is no configured linter, formatter, or automated test suite.

## Setup Commands

- Install dev tools:

  ```sh
  uv sync --dev
  ```

- If `.contai-venv/` exists, prefer it for direct Python commands.
- For repo tooling, prefer `uv run ...`.

## Build / Preview / Validation Commands

- Full docs build:

  ```sh
  uv run zensical build --clean
  ```

- Local preview server:

  ```sh
  uv run zensical serve
  ```

- If `uv` is unavailable but `zensical` is already installed globally:

  ```sh
  zensical build --clean
  zensical serve
  ```

## Lint / Test Commands

- Lint: not applicable.
- Tests: not applicable.
- Single test: not applicable; this repo has no test suite.

Validation is manual:

1. Run `uv run zensical build --clean` after content or config changes.
2. Optionally run `uv run zensical preview` and inspect affected pages.
3. Check links, headings, admonitions, code fences, and navigation.

## How To Verify Changes

- Content edits: verify the changed page renders correctly.
- Navigation edits: verify both `docs/index.md` and `zensical.toml`.
- Cross-links: click through in preview rather than assuming anchors.
- Mermaid/admonition/code-block changes: verify visually in preview.

## Core Writing Style

- Soft-wrap prose at about 77 characters.
- Use second person and present tense.
- Prefer expanded forms: `do not`, `cannot`, `it is`, `you will`.
- Use ` -- ` for prose dashes. Use a Unicode em dash only where a file
  already uses it intentionally.
- Keep explanations concept-first: establish the mental model, then show code.
- Explain why a pattern exists, not just what to type.
- Assume the reader knows Python well but is new to `asyncio`.

## File Structure Rules

- Every page needs YAML front matter with at least `title` and `description`.
- Chapter index pages also include `icon: lucide/book-open`.
- Use ATX headings only (`#`, `##`, `###`).
- Keep one blank line between sections.
- No trailing whitespace.
- No trailing blank line at end of file.

## Navigation Rules

- Do not add manual Previous/Next links in Markdown.
- When adding or renaming pages, update the chapter `index.md` page list.
- If the path or chapter structure changes, also update `zensical.toml`.

## Links And Reference Style

- Internal links: use relative Markdown links such as
  `../appendices/debugging.md`.
- Link guide-level concepts to the page in this guide that explains them in
  depth.
- For Python stdlib APIs, link to the official Python 3 docs.
- For Trio APIs/concepts, link to the official Trio docs.
- For other external library APIs/concepts, link to the project's official docs
  rather than a GitHub repository when possible.
- In prose, link all meaningful occurrences of Python, Trio, and external API
  mentions, not just the first one on the page.
- Prefer split reference links for readability:

  ```markdown
  [`asyncio.sleep()`][asyncio-sleep]

  [asyncio-sleep]: https://docs.python.org/...
  ```

- Use explicit labels, not shortcut references.
- Prefer short labels when they are unambiguous (`[await]`, `[taskgroup]`).
- For guide-level topics such as debugging workflows, prefer linking to this
  guide's own pages before linking externally.
- Link PEPs directly with their canonical URL.

## Code Block Rules

- Real examples: use `python` fences.
- Output examples: use `text` fences with a command title.
- Use `title="filename.py"` when a filename helps.
- Type-annotate function signatures and locals when it improves clarity.
- Use modern Python 3.11 syntax: `list[str]`, `str | None`, etc.
- Imports: stdlib first, one per line, `import asyncio` first when present.
- Preferred entry point:

  ```python
  async def main() -> None:
      ...

  if __name__ == "__main__":
      asyncio.run(main())
  ```

- Language-agnostic pseudocode: use `text` fences.
- Python-flavoured pseudocode: `python` fences are allowed when the Python-like
  structure helps explain the idea, even if the snippet is not runnable.
- For inline Python syntax in prose, prefer inline highlighting with
  backticks plus `#!py` when it improves readability, for example
  `` `#!py async with sem:` `` or `` `#!py await queue.get()` ``.
- Keep plain backticks for file paths, environment variables, headings, and
  non-Python snippets.
- Prefer code annotations (`# (1)!`) over dense inline comments for step-by-step
  explanations.
- Use `hl_lines` sparingly to emphasize 1-3 critical lines.

## Asyncio Content Guidelines

- Link meaningful mentions of `asyncio` APIs in prose to the official docs.
- Keep cancellation guidance consistent: cancellation arrives at checkpoints,
  not at arbitrary points.
- Prefer structured concurrency terminology and patterns.
- Keep Chapter 1 beginner-friendly but technically precise.
- Preserve the "Code Review Checklist" pattern on introductory pages when it
  fits.

## Naming And Terminology

- Use the repository's chapter names exactly, e.g. `The Basics`.
- Be consistent with coroutine, coroutine function, task, awaitable, event
  loop, checkpoint, and cancellation.
- Prefer `Python interpreter` over `compiler` when describing syntax rules.

## Admonitions And Diagrams

- Use Zensical/MkDocs admonitions: `note`, `tip`, `info`, `warning`,
  `danger`, `example`.
- Use `!!! tip "Trio users"` for Trio comparisons.
- Mermaid is supported. Prefer simple flowcharts, sequence diagrams, or state
  diagrams when a visual clearly improves comprehension.

## Agent Guidance

- Treat this repo as documentation, not as a Python package to refactor.
- Before changing style conventions, inspect nearby pages and preserve the
  existing voice.
- Be careful with bulk replacements; chapter renames and link-style changes can
  touch many files.
- Never assume tests exist; say explicitly when validation is manual.
- If you change content conventions, update this file too.
