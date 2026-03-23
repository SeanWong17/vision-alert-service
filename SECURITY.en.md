# Security Policy

[中文](SECURITY.md) | [English](SECURITY.en.md)

## Scope

Only the latest code on the current main branch is guaranteed to receive fixes and responses. If you are using an older commit or a long-outdated branch, please first attempt to reproduce the issue on the latest version.

## Reporting a Vulnerability

- Do not disclose exploitable vulnerability details in a public issue.
- Prefer submitting reports privately via GitHub Security Advisories.
- If the repository does not yet have a private security channel enabled, contact the maintainers first to establish a non-public communication channel before deciding on disclosure.

## What to Include

Please provide as much of the following as possible:

- Vulnerability type and scope of impact
- Reproduction steps or a minimal proof of concept (PoC)
- Trigger conditions, privilege requirements, and prerequisite configuration
- Data, interfaces, or deployment configurations that may be affected
- Any temporary mitigations you have already identified

## Response Principles

- Maintainers will first confirm the validity and severity of the reported issue.
- Publicly reproducible attack details should be withheld until a fix has been released.
- After a fix is released, it is recommended to supplement with tests, a changelog entry, and the range of affected versions.
