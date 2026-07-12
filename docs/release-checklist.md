# Release checklist

Use this checklist before publishing a GitHub release or PyPI package.

- [ ] Update version in `pyproject.toml` and record changes.
- [ ] Run `python -m pip install -e '.[dev]'`.
- [ ] Run `ruff check .` and `pytest -q`.
- [ ] Run `video-intake <video>` and `video-intake <directory>` plus approved copy-only rename/archive plans.
- [ ] Verify `video-intake --help` and a clean editable install.
- [ ] Review README links, roadmap status, license, and security contact.
- [ ] Tag the commit and create GitHub release notes that describe behavior and migration impact.
- [ ] Enable GitHub Actions, Dependabot, issue templates, and branch protection after creating the remote repository.
