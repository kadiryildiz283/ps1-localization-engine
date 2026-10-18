# Security Policy

## Reporting a Vulnerability

Please do **not** open a public issue for security vulnerabilities.

Instead, use [GitHub Private Vulnerability Reporting](https://github.com/kadiryildiz283/ps1-localization-engine/security/advisories/new)
or email the maintainer directly.

We will acknowledge receipt within 72 hours and aim to publish a fix or mitigation
timeline within 14 days.

## Scope

In scope:

- Arbitrary code execution through project tooling
- Path traversal or unsafe deserialization in `tools/` or `engine.py`
- CI/CD workflow compromise (`.github/workflows/`)
- Secrets leaking into the repository

Out of scope:

- Issues that require a malicious disc image as input **and** already require the
  attacker to control local files the user deliberately opens
- Copyright / licensing complaints about game assets (see README "Legal")
- Denial of service against a local CLI tool
