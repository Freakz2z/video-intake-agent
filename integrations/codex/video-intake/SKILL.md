---
name: video-intake
description: Organize local recordings with Video Intake Agent by preparing evidence, naming videos, creating timestamped descriptions, grouping visually similar files, and safely archiving them. Use for naming, reviewing, grouping, archiving, or describing .mp4, .mov, .mkv, .m4v, .avi, and .webm files or directories.
---

# Video Intake

Start every workflow with one command:

```bash
video-intake <absolute-video-or-directory-path>
```

For a video, open the returned contact sheet and every frame referenced by `timeline_json`. Use observable content to fill descriptions and choose a concise title. Run `propose` and show the proposed path before any confirmed `apply --yes`.

For a directory, read `scan_json` and `similarity_json`. Inspect representative contact sheets in every similarity group because visual fingerprints can produce false positives. Generate an `archive-plan` only when grouping is requested, and show every move before any confirmed `apply-archive-plan --yes`.

## Follow-up actions

- Render completed descriptions with `render-timeline <timeline.json> --output <timeline.md>`.
- Prepare one rename with `propose <video> --title '<title>' [--take N]`.
- Prepare batch renames with `plan <requests.json>`.
- Prepare archive moves with `archive-plan <similarity.json> --destination <directory>`.

Use the detailed subcommands only for follow-up actions or when the user explicitly requests custom intervals, thresholds, or frame limits.

## Safety rules

- Treat every proposal and plan as a review artifact, not permission to modify files.
- Never infer confirmation from requests such as “organize these videos.”
- Stop on collisions, integrity errors, or missing sources; never overwrite.
- Do not invent identities, brands, or unheard speech from still frames.
- Explain when `captured_at_source` is `file_mtime`, because it is weaker than embedded metadata.
