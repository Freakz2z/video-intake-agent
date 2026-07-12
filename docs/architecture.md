# Architecture

Video Intake Agent separates semantic judgment from deterministic media and filesystem work.

```text
local video(s)
  │
  ├─ FFprobe ─────────────── metadata and capture time
  ├─ FFmpeg ──────────────── contact sheets and timestamped frames
  └─ local visual hashes ─── similarity report
             │
             ▼
       evidence JSON bundle
             │
             ▼
      Codex / Claude Code
             │
             ▼
     reviewable rename, timeline,
       or archive plan
             │
       explicit approval
             ▼
      guarded filesystem action
```

## Data contracts

Every JSON artifact includes `schema_version` and `kind` where applicable. Current schema version: `1.0`.

- `video-intake.prepared-video`: paths to metadata, contact sheet, and timeline evidence.
- `video-intake.prepared-directory`: paths to scan and similarity reports.
- `video-intake.timeline`: ordered timestamp ranges, frames, and Agent descriptions.
- `video-intake.similarity-report`: local visual signatures, groups, and singles.
- `video-intake.rename-plan`: validated single or batch rename operations.
- `video-intake.archive-plan`: integrity-protected source-to-group moves.

## Safety boundaries

Read-only commands may create evidence files but never modify source videos. Filesystem mutations require a separate apply command with `--yes`. Apply operations reject collisions and batch operations attempt rollback after partial failure.

Visual similarity is based on multiple grayscale difference hashes, luminance, and duration. It is deliberately explainable and dependency-light, but it is not semantic identity detection; all proposed groups require review.
