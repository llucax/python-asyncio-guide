# AGENTS.md -- Python Asyncio Guide

This is a prose-only Markdown guide (31 `.md` files, no runnable source).
There are no tests, no CI, and no linter configs. Quality is enforced
by convention. The guide is built with **Zensical** (a MkDocs Material
compatible documentation tool) configured in `zensical.toml`.

## Repository Layout

```
docs/
  index.md                      # top-level guide index
  everyday-asyncio/             # Chapter 1 (9 files)
  beyond-the-basics/            # Chapter 2 (7 files)
  how-asyncio-works/            # Chapter 3 (5 files)
  the-low-level-toolkit/        # Chapter 4 (6 files)
  appendices/                   # 3 appendix files
zensical.toml                   # Zensical configuration
```

## Tooling

- **Python**: 3.11 (`.python-version`), guide examples target 3.11+.
- **Documentation**: Zensical (MkDocs Material compatible). Configuration
  is in `zensical.toml`. Preview with `zensical preview`, build with
  `zensical build`.
- **Package manager**: `uv`. The lockfile pins `zensical` as a dev dep.
- **Linters**: No config files exist. `.ruff_cache/` and `.mypy_cache/`
  are present from ad-hoc runs; treat them as informational only.
- There is **no CI, no Makefile, no test suite**. Validation is manual.

## Prose Style

- **Line width**: soft-wrap at ~77 characters. Lines may exceed 79 when
  they contain inline links to Python docs (do not break mid-link).
- **Voice**: second person ("you"), conversational but technically precise.
- **Tense**: present tense.
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
- **Emojis**: avoid unless there is a very strong reason.

## Front Matter

Every page has YAML front matter with at least `title` and `description`:

```yaml
---
title: Page Title
description: >-
  Brief SEO-friendly description of the page content.
---
```

Chapter index pages also include `icon: lucide/book-open`.

## Navigation

Navigation is handled automatically by Zensical via the
`navigation.footer` feature. Do **not** add manual Previous/Next links
in Markdown files. When adding a new page, update the chapter
`index.md` (numbered list) only.

## Admonitions

Use Zensical (MkDocs Material) admonition syntax. Available types:

```markdown
!!! note

    Supplementary information the reader should be aware of.

!!! tip

    Helpful advice, shortcuts, or best practices.

!!! info

    Key conceptual information (e.g., explaining an API contract).

!!! warning

    Potential pitfalls or dangerous patterns.

!!! danger

    Actions that could cause data loss or hard-to-debug problems.

!!! example

    Worked examples or demonstrations.
```

Additional types available: `abstract`, `success`, `question`,
`failure`, `bug`, `quote`. Use sparingly and only when they fit.

**Collapsible admonitions** use `???` (collapsed) or `???+` (expanded):

```markdown
??? tip "Optional supplementary detail"

    Content that readers can expand if interested.
```

**Custom titles** are supported:

```markdown
!!! tip "Trio users"

    asyncio's `TaskGroup` is equivalent to Trio's nursery.
```

**Trio comparison tips** follow this pattern:

```markdown
!!! tip "Trio users"

    asyncio's `TaskGroup` is equivalent to Trio's nursery.
```

## Code Blocks

### Python examples

- Language tag: always ` ```python `.
- Use the `title` attribute for filenames:
  ` ```python title="filename.py" `.
  Omit the title only for short inline fixes without a filename.
- Type annotations on all function signatures and on local variables where
  it aids clarity: `async def greet(name: str) -> str:`.
- Modern 3.11+ syntax: `list[str]`, `dict[K, V]`, `str | None`.
- Imports: `import asyncio` first, one per line, stdlib before third-party.
- Entry point: `async def main() -> None:` with
  `if __name__ == "__main__": asyncio.run(main())`.
- Line length in code: aim for ~79 characters.

### Output blocks

- Language tag: always ` ```text `.
- Use the `title` attribute for the command:
  ` ```text title="$ python filename.py" `.
- Show realistic output. Use `...` for elided tracebacks.

### Line highlighting

Use `hl_lines` to draw attention to critical lines when the surrounding
prose refers to them. Highlight 1-3 lines, not large blocks:

` ```python hl_lines="3" title="example.py" `

### Code annotations

Use sparingly for non-essential supplementary explanations. Do not put
critical information in annotations (users might miss them):

```python title="example.py"
asyncio.run(main())  # (1)!
```

1. Explanation of what this line does.

### Pseudocode

- Language tag: ` ```text ` (not ` ```python `).

### Mermaid diagrams

- Sparingly. Use ` ```mermaid ` when a visual is genuinely needed.
- Prefer flowcharts, sequence diagrams, and state diagrams.
- Zensical renders them with theme-aware colors automatically.

## Links

- **Internal**: relative Markdown links (`getting-started.md`,
  `../appendices/checkpoint-contract.md`, `coordination.md#asyncioqueue`).
  Zensical resolves `.md` links to the correct output paths.
- **Cross-linking**: link the first mention of a concept on each page to
  the page that covers it in depth, especially across chapters.
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

- When adding a new page, update the chapter `index.md` (numbered list).
- When referencing an asyncio API for the first time on a page, link to
  the official Python docs.
- Keep the "Code Review Checklist" pattern (used in getting-started.md
  and in the v1 tutorial) when closing introductory sections.
- The guide assumes the reader knows Python well but is new to asyncio.
  Do not explain basic Python; do explain every async concept.