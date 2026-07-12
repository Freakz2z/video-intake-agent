# Contributing

[English](CONTRIBUTING.md) · [简体中文](docs/CONTRIBUTING.zh-CN.md)

Thank you for helping make post-recording workflows less painful.

## Local setup

Install Python 3.11+ and FFmpeg, then create a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/pytest -q
```

## Pull requests

- Keep filesystem operations conservative: no silent overwrites, implicit renames, or unreviewed archive moves.
- Treat similarity as a heuristic and keep a human/Agent review checkpoint before filesystem changes.
- Add tests for every behavior change, especially error and rollback paths.
- Preserve JSON output compatibility or document intentional schema changes.
- Do not add a cloud dependency or collect media without an explicit opt-in design.
- Use concise English for public-facing documentation; Chinese examples are welcome.

## Issues

Open a bug report with the command, anonymized JSON output, platform, Python version, FFmpeg version, and a minimal reproducible sample when possible. Do not attach private recordings to public issues.
