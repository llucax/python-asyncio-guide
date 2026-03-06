# AGENTS.md -- Python Asyncio Guide

This is a prose-only Markdown guide (31 `.md` files, no runnable source).
There are no tests, no CI, and no linter configs. Quality is enforced
by convention.

## Repository Layout

```
index.md                        # top-level guide index
01-everyday-asyncio/            # Chapter 1 (9 files)
02-beyond-the-basics/           # Chapter 2 (7 files)
03-how-asyncio-works/           # Chapter 3 (5 files)
04-the-low-level-toolkit/       # Chapter 4 (6 files)
appendices/                     # 3 appendix files
```

## Tooling

- **Python**: 3.11 (`.python-version`), guide examples target 3.11+.
- **Package manager**: `uv`. The lockfile pins `zensical` as a dev dep.
- **Linters**: No config files exist. `.ruff_cache/` and `.mypy_cache/`
  are present from ad-hoc runs; treat them as informational only.
- There is **no CI, no Makefile, no test suite**. Validation is manual.

## Prose Style

- **Line width**: soft-wrap at ~77 characters. Lines may exceed 79 when
  they contain inline links to Python docs (do not break mid-link).
- **Voice**: second person ("you"), conversational but technically precise.
- **Tense**: present tense. Avoid future tense except in "Next up" teasers.
- **Contractions**: prefer expanded forms ("do not", "it is", "you will",
  "cannot"). Contractions are acceptable occasionally but not the default.
- **Em-dashes**: use ` -- ` (space-hyphen-hyphen-space) in prose. Use
  ` — ` (Unicode em-dash) only in index page list-item descriptions.
- **Lists**: unordered lists use `-`, ordered lists use sequential numbers
  (`1.`, `2.`, `3.`). Bold lead-in pattern: `- **Term.** Explanation...`
- **Headings**: ATX only (`#`, `##`, `###`). Blank line before and after.
  Inline code in headings is fine (e.g., `` ## `asyncio.timeout()` ``).
- **Teaching approach**: concept-first. Build the mental model, then show
  code. Explain *why*, not just *how*.

## Admonitions

Use GitHub-flavored blockquote admonitions. All five types are in use:

```markdown
> [!NOTE]
> Supplementary information the reader should be aware of.

> [!TIP]
> Helpful advice, shortcuts, or best practices.

> [!IMPORTANT]
> Key information the reader must not miss.

> [!WARNING]
> Potential pitfalls or dangerous patterns.

> [!CAUTION]
> Actions that could cause data loss or hard-to-debug problems.
```

**Trio comparison tips** follow this pattern:

```markdown
> [!TIP]
> **Trio users:** asyncio's `TaskGroup` is equivalent to Trio's nursery.
```

## Code Blocks

### Python examples

- Language tag: always ` ```python `.
- First line: `# filename.py` comment (omit only for short inline fixes).
- Type annotations on all function signatures and on local variables where
  it aids clarity: `async def greet(name: str) -> str:`.
- Modern 3.11+ syntax: `list[str]`, `dict[K, V]`, `str | None`.
- Imports: `import asyncio` first, one per line, stdlib before third-party.
- Entry point: `async def main() -> None:` with
  `if __name__ == "__main__": asyncio.run(main())`.
- Line length in code: aim for ~79 characters.

### Output blocks

- Language tag: always ` ```text `.
- First line: `$ python filename.py` matching the preceding code block.
- Show realistic output. Use `...` for elided tracebacks.

### Pseudocode

- Language tag: ` ```text ` (not ` ```python `).

### Mermaid diagrams

- Sparingly. Use ` ```mermaid ` when a visual is genuinely needed.

## Links

- **Internal**: relative Markdown links (`getting-started.md`,
  `../appendices/checkpoint-contract.md`, `coordination.md#asyncioqueue`).
- **Python docs**: full URL to the 3.x docs, e.g.,
  `[asyncio.TaskGroup](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup)`.
  Mention the linked API at least once per page where it is used.
- **PEPs**: link as `[PEP 654](https://peps.python.org/pep-0654/)`.

## Tables

Standard Markdown pipe tables. Alignment markers are optional:

```markdown
| Column A | Column B |
|---|---|
| data | data |
```

## Whitespace and Formatting

- No tabs; spaces only.
- No trailing whitespace on any line.
- One blank line between sections; no multiple consecutive blank lines.
- No trailing blank line at end of file.

## Content Guidelines

- When adding a new page, update the chapter `index.md` (numbered list)
  and fix `Previous:`/`Next:` navigation in the adjacent files.
- When referencing an asyncio API for the first time on a page, link to
  the official Python docs.
- Keep the "Code Review Checklist" pattern (used in getting-started.md
  and in the v1 tutorial) when closing introductory sections.
- The guide assumes the reader knows Python well but is new to asyncio.
  Do not explain basic Python; do explain every async concept.
