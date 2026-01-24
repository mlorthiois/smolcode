---
name: python-best-practices
description: Always read this file before making any python change. It enumerates python development best practices to follow.
---
# Python best practices

## Objectives
- Produce code that is **readable, testable, typed, and maintainable**.
- Prefer **simple, explicit designs** over cleverness.
- Keep changes **small and reviewable** (focused diffs, clear commits).

## Baseline standards
- Target Python **3.13+** (unless the repo specifies otherwise).
- Follow **PEP 8** and modern Python idioms:
  - `pathlib` over `os.path`
  - `dataclasses` / `pydantic` (if already used) for structured data
  - `typing` everywhere it clarifies intent
- Prefer the standard library unless a dependency brings clear leverage.
- Prefer pyproject.toml over setup.py and requirements.txt.
- Don't hesitate to read pyproject.toml to see what's installed and setup.

---

## Formatting, linting, and typing
- **Auto-format** with one consistent formatter (Black or Ruff format, depending on repo).
- **Lint** with Ruff (preferred) or Flake8, and keep the config in-repo.
- **Type-check** with mypy/pyright (pick the repo’s choice, do not mix).
- Never silence rules globally without a strong reason; prefer targeted ignores.
