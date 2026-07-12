# Video Intake Agent

[![CI](https://github.com/Freakz2z/video-intake-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Freakz2z/video-intake-agent/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/Freakz2z/video-intake-agent/blob/main/LICENSE)

One local command to prepare recordings for naming, timestamped description, and similarity-based organization with Codex or Claude Code.

用一条本地命令整理录制文件：生成命名证据、带时间戳的内容分镜，并把视觉上相似的视频归为一组。

![Openly licensed Big Buck Bunny demo](https://raw.githubusercontent.com/Freakz2z/video-intake-agent/main/demo/media/preview.gif)

> v0.2 alpha · Source installation only · No cloud API or API key required

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
- Computes multi-frame visual fingerprints locally and groups similar recordings.
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
- A directory produces `scan.json`, contact sheets, and `similarity.json`.
- Outputs go into a hidden `.video-intake/` directory beside the input.

## Use it from an Agent

Bundled integrations:

- [Codex skill](https://github.com/Freakz2z/video-intake-agent/tree/main/integrations/codex/video-intake)
- [Claude Code command](https://github.com/Freakz2z/video-intake-agent/blob/main/integrations/claude-code/commands/video-intake.md)

Or give either Agent this instruction:

> Run `video-intake <path>`, inspect the generated evidence, and prepare factual descriptions and organization proposals. Do not apply filesystem changes until I approve the exact paths.

## Reproducible demo

The included demo uses CC BY 3.0 excerpts from Blender Foundation's *Big Buck Bunny*—not private user footage.

```bash
video-intake demo/media
```

Expected result:

- `bunny-meets-rodents.mp4` and its re-encoded color variant form one group at about `0.98` similarity.
- `forest-chase.mp4` remains separate.
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
| `video-intake similar <directory>` | Group videos by local visual fingerprints | No |
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
- Visual similarity is heuristic. Review groups before applying an archive plan.

Read the full [privacy model](https://github.com/Freakz2z/video-intake-agent/blob/main/docs/privacy.md) and [architecture](https://github.com/Freakz2z/video-intake-agent/blob/main/docs/architecture.md).

## Current limits

- No speech transcription yet.
- No persistent fingerprint cache, so large directories take longer on repeated runs.
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
