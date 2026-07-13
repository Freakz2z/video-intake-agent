<div align="center">
  <img src="docs/assets/logo.svg" alt="Video Intake Agent" width="680" />

  <p><strong>One local command for video naming, timestamped descriptions, and similarity-based organization.</strong></p>
  <p>用一条本地命令完成视频命名、时间戳内容描述与相似素材整理。</p>

  <p>
    <a href="README.md">English</a> ·
    <a href="docs/README.zh-CN.md">简体中文</a> ·
    <a href="docs/mcp.md">MCP</a> ·
    <a href="CONTRIBUTING.md">Contributing</a> ·
    <a href="docs/CONTRIBUTING.zh-CN.md">贡献指南</a> ·
    <a href="docs/roadmap.md">Roadmap</a> ·
    <a href="docs/privacy.md">Privacy</a>
  </p>

  <p>
    <a href="https://github.com/Freakz2z/video-intake-agent/actions/workflows/ci.yml"><img src="https://github.com/Freakz2z/video-intake-agent/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB.svg" alt="Python 3.11+" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-22C55E.svg" alt="MIT License" /></a>
    <img src="https://img.shields.io/badge/API%20key-not%20required-06B6D4.svg" alt="No API key required" />
  </p>
</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/Freakz2z/video-intake-agent/main/demo/media/preview.gif" alt="Openly licensed Big Buck Bunny demo" width="480" />
</p>

<p align="center"><sub>v0.2 alpha · Source installation · Local-first · No cloud API required</sub></p>

## What it does

```text
video or directory
  → local FFmpeg evidence
  → Codex / Claude Code understands the content
  → reviewable name, timeline, or archive plan
  → explicit confirmation before filesystem changes
```

- Prepares video metadata, contact sheets, and timestamped storyboard frames.
- Builds Agent-readable JSON for factual naming and Markdown timelines.
- Computes multi-frame visual fingerprints locally, caches them, and separates exact duplicates from similar recordings.
- Generates collision-safe rename and archive plans with rollback attempts.
- Never uploads media. The repository contains only the attributed open-movie demo under `demo/`.

The project is inspired by the reviewable Agent workflow of [`video-use`](https://github.com/browser-use/video-use), with a narrower focus on post-recording intake and organization.

## Quick start

Requirements: Python 3.11+ and [FFmpeg](https://ffmpeg.org/) with `ffprobe` on `PATH`.

```bash
git clone https://github.com/Freakz2z/video-intake-agent.git
cd video-intake-agent

python3 -m venv .venv
source .venv/bin/activate
python -m pip install .

video-intake doctor
video-intake /absolute/path/to/video-or-directory
```

On Windows, activate with `.venv\Scripts\activate`.

The one-command workflow is read-only with respect to source videos:

- A video produces `inspect.json`, a contact sheet, storyboard frames, and `timeline.json`.
- A directory produces `scan.json`, contact sheets, `similarity.json`, and a reusable fingerprint cache.
- Outputs go into a hidden `.video-intake/` directory beside the input.

## Use it from an Agent

Bundled integrations:

- [Codex skill](https://github.com/Freakz2z/video-intake-agent/tree/main/integrations/codex/video-intake)
- [Claude Code command](https://github.com/Freakz2z/video-intake-agent/blob/main/integrations/claude-code/commands/video-intake.md)
- [MCP Server](https://github.com/Freakz2z/video-intake-agent/blob/main/docs/mcp.md) with 12 structured tools, a workflow resource, and a reusable review prompt

Or give either Agent this instruction:

> Run `video-intake <path>`, inspect the generated evidence, and prepare factual descriptions and organization proposals. Do not apply filesystem changes until I approve the exact paths.

Install and verify the MCP integration:

```bash
python -m pip install -e '.[mcp]'
video-intake-mcp-client
```

The server uses local stdio by default, supports an optional filesystem allowlist, and requires exact path or SHA-256 confirmation before write actions. See the [MCP guide](docs/mcp.md) for Codex and Claude Code setup.

## Reproducible demo

The included demo uses CC BY 3.0 excerpts from Blender Foundation's *Big Buck Bunny*—not private user footage.

```bash
video-intake demo/media
```

Expected result:

- `bunny-meets-rodents.mp4` and its re-encoded color variant form one group at about `0.98` similarity.
- `forest-chase.mp4` remains separate.
- Running the command again reuses unchanged fingerprints instead of decoding every video again.
- Timeline frames can be described and rendered without sending video to an external service.

See the [demo guide](https://github.com/Freakz2z/video-intake-agent/blob/main/demo/README.md) and [media attribution](https://github.com/Freakz2z/video-intake-agent/blob/main/demo/ATTRIBUTION.md).

## Commands

| Command | Purpose | Changes source videos? |
| --- | --- | --- |
| `video-intake <path>` | Prepare the complete evidence bundle | No |
| `video-intake doctor` | Check Python, FFmpeg, and FFprobe | No |
| `video-intake inspect <video>` | Create metadata and a contact sheet | No |
| `video-intake timeline <video>` | Extract timestamped storyboard frames | No |
| `video-intake render-timeline <json>` | Render Agent descriptions to Markdown | No |
| `video-intake similar <directory>` | Find exact duplicates and group visually similar videos | No |
| `video-intake propose <video>` | Generate a rename proposal | No |
| `video-intake plan <requests.json>` | Generate a batch rename plan | No |
| `video-intake archive-plan <report.json>` | Generate a similarity archive plan | No |
| `apply`, `apply-plan`, `apply-archive-plan` | Execute an approved plan | Yes, requires `--yes` |

Run `video-intake <command> --help` for all options.

## Safety and privacy

- All media inspection runs locally through FFmpeg and FFprobe.
- Semantic understanding comes from the Codex or Claude Code session where you invoke the tool.
- Proposals do not imply permission to rename or move files.
- Existing destinations are never overwritten.
- Archive plans include an integrity digest; batch failures attempt rollback.
- Fingerprint cache entries are invalidated automatically when file size, modification time, or sample count changes.
- Visual similarity is heuristic. Review groups before applying an archive plan.

Read the full [privacy model](https://github.com/Freakz2z/video-intake-agent/blob/main/docs/privacy.md) and [architecture](https://github.com/Freakz2z/video-intake-agent/blob/main/docs/architecture.md).

## Current limits

- No speech transcription yet.
- No background folder watcher.
- Timestamped issue/retake notes are planned but not yet implemented.

See the [roadmap](https://github.com/Freakz2z/video-intake-agent/blob/main/docs/roadmap.md).

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python -m build
```

Contributions are welcome. Read [CONTRIBUTING.md](https://github.com/Freakz2z/video-intake-agent/blob/main/CONTRIBUTING.md) and report vulnerabilities privately via [SECURITY.md](https://github.com/Freakz2z/video-intake-agent/blob/main/SECURITY.md).

## License

Python code: [MIT](https://github.com/Freakz2z/video-intake-agent/blob/main/LICENSE) © 2026 Freakz2z.

Demo media: [CC BY 3.0](https://github.com/Freakz2z/video-intake-agent/blob/main/demo/ATTRIBUTION.md), derived from *Big Buck Bunny* by Blender Foundation / Blender Institute.
