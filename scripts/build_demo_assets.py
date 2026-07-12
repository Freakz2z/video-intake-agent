"""Build the small, redistributable Big Buck Bunny demo clips."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_320x180.mp4"
SOURCE_SHA256 = "f78f39603e6774907f2faafabf26a667f4a6fc31769ec304a8a8f7c62d280508"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def verify_source(path: Path) -> None:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest != SOURCE_SHA256:
        raise RuntimeError(f"Source checksum mismatch: expected {SOURCE_SHA256}, got {digest}")


def render_clip(source: Path, output: Path, start: int) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            str(start),
            "-i",
            str(source),
            "-t",
            "24",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "24",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def build(source: Path, output_dir: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("FFmpeg is required")
    verify_source(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    original = output_dir / "bunny-meets-rodents.mp4"
    render_clip(source, original, start=105)
    render_clip(source, output_dir / "forest-chase.mp4", start=300)
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(original),
            "-vf",
            "eq=brightness=0.025:saturation=0.88",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-b:a",
            "80k",
            "-movflags",
            "+faststart",
            str(output_dir / "bunny-meets-rodents-mobile.mp4"),
        ]
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(original),
            "-t",
            "8",
            "-filter_complex",
            (
                "fps=8,scale=320:-2:flags=lanczos,split[frames][palette_input];"
                "[palette_input]palettegen=max_colors=128[palette];"
                "[frames][palette]paletteuse=dither=bayer"
            ),
            str(output_dir / "preview.gif"),
        ]
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Use an existing official source download")
    parser.add_argument(
        "--output-dir", type=Path, default=project_root / "demo" / "media", help="Output directory"
    )
    args = parser.parse_args()
    if args.source:
        build(args.source.expanduser().resolve(), args.output_dir.expanduser().resolve())
        return
    with tempfile.TemporaryDirectory(prefix="video-intake-demo-") as temporary:
        source = Path(temporary) / "BigBuckBunny_320x180.mp4"
        print(f"Downloading {SOURCE_URL}")
        urllib.request.urlretrieve(SOURCE_URL, source)
        build(source, args.output_dir.expanduser().resolve())


if __name__ == "__main__":
    main()
