# Architecture

Video Intake Agent separates semantic judgment from deterministic media and filesystem work.

```text
local video(s)
  │
  ├─ FFprobe ─────────────── metadata and capture time
  ├─ FFmpeg ──────────────── contact sheets and timestamped frames
  ├─ local visual hashes ─── cached similarity report
  └─ selective SHA-256 ───── exact duplicate groups
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
- `video-intake.fingerprint-cache`: stat-validated visual signatures and optional content hashes.
- `video-intake.similarity-report`: exact duplicates, visual groups, singles, and cache statistics.
- `video-intake.rename-plan`: validated single or batch rename operations.
- `video-intake.archive-plan`: integrity-protected source-to-group moves.

## Safety boundaries

Read-only commands may create evidence files but never modify source videos. Filesystem mutations require a separate apply command with `--yes`. Apply operations reject collisions and batch operations attempt rollback after partial failure.

Visual similarity is based on multiple grayscale difference hashes, luminance, and duration. It is deliberately explainable and dependency-light, but it is not semantic identity detection; all proposed groups require review.

The cache is keyed by absolute path and validated against file size, nanosecond modification time, and sample count. Exact duplicate detection first buckets files by size and computes SHA-256 only inside buckets containing at least two files. This avoids hashing every unique-size recording while keeping byte identity distinct from visual similarity.
