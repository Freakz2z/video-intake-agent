# Privacy model

Video Intake Agent is local-first. Its core CLI does not upload media, call an AI API, or require an API key.

## What stays local

- Source videos
- FFprobe metadata
- Contact sheets and storyboard frames
- Visual fingerprints, SHA-256 content hashes, cache statistics, and similarity reports
- Rename and archive plans

Generated evidence is stored under `.video-intake/` by default. These files can contain thumbnails, absolute filesystem paths, timestamps, visual fingerprints, and other information derived from the source media. The fingerprint cache does not contain video frames, but it still reveals filenames and local paths. Treat the evidence directory as private and do not publish it without review.

## Agent responsibility

Codex or Claude Code provides semantic visual understanding. Video Intake Agent does not control the data-handling policy of the Agent runtime. Review the runtime's privacy settings before asking it to inspect confidential material.

## Network behavior

The installed `video-intake` command performs no network requests. The optional `scripts/build_demo_assets.py` script downloads the openly licensed *Big Buck Bunny* source only when a contributor explicitly runs it.

## Repository media

No private user recordings or extracted private frames are included in this repository. Files under `demo/media/` are reproducible derivatives of *Big Buck Bunny* and are documented in `demo/ATTRIBUTION.md`.

## Cleanup

Delete the generated `.video-intake/` directory when its evidence is no longer needed. The tool never deletes source media automatically.
