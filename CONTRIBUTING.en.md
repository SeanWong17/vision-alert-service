# Contributing Guide

[中文](CONTRIBUTING.md) | [English](CONTRIBUTING.en.md)

Thank you for your interest in improving Vision Alert Service.

## Development Environment

```bash
python3 -m pip install -r requirements-ci.txt
```

If you need to run the full inference pipeline locally, install the additional dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Pre-Submission Checklist

Please complete at minimum the following checks before submitting:

```bash
python3 -m compileall -q app tests scripts
python3 -m pytest tests/test_worker.py tests/test_settings.py
python3 scripts/ci_unittest_gate.py
```

If `ruff` is installed locally, also run:

```bash
ruff check app tests scripts
ruff format --check app tests scripts
```

## Code Conventions

- Prefer small, focused changes. Avoid mixing refactoring, features, and documentation updates in a single PR.
- Do not change the semantics of public API fields without explanation.
- When adding new behavior branches, add corresponding tests first.
- Changes to logging, error codes, or configuration options must be reflected in the documentation.
- Changes to Docker, deployment, or runtime dependencies must include a rollback plan.

## Pull Request Description

A PR description should ideally include:

- Background and objective of the change
- Core implementation approach
- Risk factors and compatibility impact
- Test scope and results
- If the interface changes, include request/response examples

## Issue Reporting

- For bugs, include reproduction steps, relevant configuration snippets, logs, and environment details.
- For feature requests, describe the use case, expected benefit, and alternatives considered.
- For security issues, do not disclose exploitable details publicly — refer to [SECURITY.en.md](SECURITY.en.md) instead.
