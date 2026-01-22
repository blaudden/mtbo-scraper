# SAFETY.md - Safety & Safe-Write Protocol

This document outlines the protocols AI agents must follow to ensure repository stability and data integrity.

## 🛡️ Safe-Write Protocol

To prevent accidental corruption of core logic or data:

1.  **Drafting**: Always write significant logic changes to a temporary buffer or use `task_boundary` to summarize changes before application.
2.  **Validation**: Run `run_tests.sh` immediately after any file modification.
3.  **JSON Integrity**: Never manually edit `mtbo_events.json` unless absolutely necessary. Use the scraper or specialized scripts.
4.  **Schema Enforcement**: Any change to `models.py` MUST be reflected in `schema.json`.

## ✅ Agent Safety Checklist

Before committing or concluding a session, verify:

- [ ] `uv run mypy src/` passes with no errors (Gravity).
- [ ] `uv run ruff check .` is clean.
- [ ] `uv run pytest tests/` all pass.
- [ ] `python3 verify_env.py` confirms environment alignment.
- [ ] No temporary files or `__pycache__` have been accidentally committed.

## ⚠️ High-Risk Areas

- `src/sources/eventor_parser.py`: Complex BeautifulSoup logic. Highly sensitive to site structure changes.
- `src/storage.py`: Core I/O logic. Failures here can wipe the event database.
- `src/models.py`: Structural changes here ripple through the entire codebase.

> [!CAUTION]
> Avoid modifying `uv.lock` manually. Use `uv add` or `uv sync` to manage dependencies.
