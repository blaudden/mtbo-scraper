---
name: python-code-reviewer
description: Performs a professional code review of Python files. Analyzes structure, PEP 8 compliance, type safety, and logic clarity. Use when asked to "review my code," "find bugs," or "check for best practices."
---

# 🛡️ Python Code Reviewer Skill

## 🎯 Review Objectives
* **Logical Integrity:** Detect "code smells," redundant loops, and complex conditionals.
* **Static Analysis:** Enforce type hints and detect potential runtime errors using static tools.
* **Security:** Identify common vulnerabilities (e.g., unsafe imports, hardcoded secrets).
* **Clarity:** Ensure variable naming is descriptive and docstrings follow the Google/NumPy standard.

## 🛠️ Execution Protocol (Antigravity Surfaces)

1.  **Terminal Surface:** * Run `ruff check .` to identify linting and style violations.
    * Run `mypy .` to verify type-hint consistency.
2.  **Editor Surface:** * Walk through changed files (`git diff` or recent saves).
    * Identify "God Objects" (classes that are too large) or functions with high cyclomatic complexity.
3.  **Browser Surface (Optional):** * If a library is used in an unusual way, the agent must browse the official documentation to verify the latest 2026 usage patterns.

## 📦 Deliverables (Artifacts)
* **Implementation Plan:** A list of suggested refactors.
* **Review Scorecard:** A Markdown table scoring:
    * **Structure:** (0-10)
    * **Type Safety:** (0-10)
    * **Clarity:** (0-10)
* **Automated Diffs:** Direct code suggestions that the user can "Accept" in the Editor.

## 🚫 Constraints
* **Observe Only:** Do not apply fixes automatically. Only suggest them as an Implementation Plan artifact.
* **Environment Respect:** Do not install new global packages; only use what is in the `.venv`.
