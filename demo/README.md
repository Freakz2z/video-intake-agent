# Reproducible demo

This demo uses three short excerpts derived from Blender Foundation's open movie *Big Buck Bunny*:

- `bunny-meets-rodents.mp4`: the primary 24-second clip.
- `bunny-meets-rodents-mobile.mp4`: the same clip, re-encoded with a small brightness and saturation change.
- `forest-chase.mp4`: a different 24-second scene.

Run the entire preparation workflow with one command:

```bash
video-intake demo/media
```

The generated `.video-intake/similarity.json` contains the similarity result.

Expected behavior:

- The two `bunny-meets-rodents` clips form one group (measured similarity around `0.98`).
- `forest-chase.mp4` remains a single video.

Generate a timestamped description template:

```bash
video-intake timeline demo/media/bunny-meets-rodents.mp4 \
  --interval 4 > bunny-timeline.json
```

Ask Codex or Claude Code to inspect every returned frame, fill the descriptions, and render the result with `video-intake render-timeline`.

Rebuild all media from the verified official source:

```bash
python scripts/build_demo_assets.py
```

See [ATTRIBUTION.md](ATTRIBUTION.md) for source and license information.
