"""Agent-native video naming, timeline, and similarity archive workflows."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"}
SAFE_SUBJECT = re.compile(r"[^\w\u4e00-\u9fff-]+", flags=re.UNICODE)
COMMANDS = {
    "doctor",
    "prepare",
    "inspect",
    "timeline",
    "render-timeline",
    "scan",
    "similar",
    "archive-plan",
    "apply-archive-plan",
    "propose",
    "plan",
    "apply",
    "apply-plan",
}


class IntakeError(RuntimeError):
    """A recoverable command-line error."""


def package_version() -> str:
    try:
        return version("video-intake-agent")
    except PackageNotFoundError:
        return "0.2.0"


def doctor() -> dict[str, Any]:
    tools: dict[str, dict[str, Any]] = {}
    for command in ("ffmpeg", "ffprobe"):
        path = shutil.which(command)
        if path is None:
            tools[command] = {"available": False, "path": None, "version": None}
            continue
        result = subprocess.run([path, "-version"], check=False, text=True, capture_output=True)
        first_line = (result.stdout or result.stderr).splitlines()
        tools[command] = {
            "available": result.returncode == 0,
            "path": path,
            "version": first_line[0] if first_line else None,
        }
    python_supported = sys.version_info >= (3, 11)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "video-intake.doctor",
        "version": package_version(),
        "python": {
            "available": python_supported,
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "executable": sys.executable,
        },
        "tools": tools,
        "ready": python_supported and all(item["available"] for item in tools.values()),
    }


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise IntakeError(f"未找到 {command[0]}；请先安装 FFmpeg（需包含 ffprobe）。") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "未知 FFmpeg 错误"
        raise IntakeError(detail) from exc


def _run_bytes(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise IntakeError(f"未找到 {command[0]}；请先安装 FFmpeg（需包含 ffprobe）。") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip() or "未知 FFmpeg 错误"
        raise IntakeError(detail) from exc


def _ratio(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        top, bottom = value.split("/", 1)
        return round(float(top) / float(bottom), 3)
    except (ValueError, ZeroDivisionError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _capture_time(probe: dict[str, Any], path: Path) -> tuple[datetime, str]:
    tags: list[dict[str, Any]] = [probe.get("format", {}).get("tags", {})]
    tags.extend(stream.get("tags", {}) for stream in probe.get("streams", []))
    for tag in tags:
        raw = tag.get("creation_time") or tag.get("com.apple.quicktime.creationdate")
        if not raw:
            continue
        try:
            value = str(raw).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(value)
            return (parsed.astimezone() if parsed.tzinfo else parsed), "embedded_metadata"
        except ValueError:
            continue
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone(), "file_mtime"


def inspect_video(path_value: str) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise IntakeError(f"找不到视频文件：{path}")
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise IntakeError(
            f"不支持的文件扩展名：{path.suffix}；支持 {', '.join(sorted(VIDEO_EXTENSIONS))}"
        )

    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
    )
    probe = json.loads(result.stdout)
    video = next(
        (item for item in probe.get("streams", []) if item.get("codec_type") == "video"), None
    )
    if not video:
        raise IntakeError("文件中没有可用的视频流。")
    audio = next(
        (item for item in probe.get("streams", []) if item.get("codec_type") == "audio"), None
    )
    timestamp, timestamp_source = _capture_time(probe, path)
    duration = _as_float(probe.get("format", {}).get("duration")) or _as_float(
        video.get("duration")
    )
    return {
        "source": str(path),
        "file": {
            "name": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
        },
        "captured_at": timestamp.isoformat(timespec="seconds"),
        "captured_at_source": timestamp_source,
        "video": {
            "duration_seconds": duration,
            "codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": _ratio(video.get("avg_frame_rate")),
            "rotation": (video.get("tags", {}) or {}).get("rotate", "0"),
        },
        "audio": {
            "present": audio is not None,
            "codec": audio.get("codec_name") if audio else None,
        },
    }


def create_contact_sheet(evidence: dict[str, Any], output_dir: str | None) -> Path:
    duration = evidence["video"].get("duration_seconds") or 1
    frames = max(1, min(12, math.ceil(duration / 8)))
    # A contact sheet is evidence for the agent, not a derived video asset.  It is
    # kept outside the source directory unless the caller explicitly chooses otherwise.
    target_dir = (
        Path(output_dir).expanduser().resolve() if output_dir else Path.cwd() / ".video-intake"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    source = Path(evidence["source"])
    fingerprint = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:8]
    output = target_dir / f"{source.stem}-{fingerprint}-contact-sheet.jpg"
    fps = frames / max(duration, 0.1)
    columns = min(4, frames)
    rows = math.ceil(frames / columns)
    filter_graph = f"fps={fps:.6f},scale=320:-2,tile={columns}x{rows}:padding=8:margin=8"
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vf",
            filter_graph,
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(output),
        ]
    )
    return output


def _format_media_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    base = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{base}.{millis:03d}" if millis else base


def create_timeline(
    evidence: dict[str, Any], output_dir: str | None, interval: float, max_frames: int
) -> dict[str, Any]:
    duration = evidence["video"].get("duration_seconds")
    if not duration or duration <= 0:
        raise IntakeError("无法读取视频时长，不能生成时间线。")
    if not math.isfinite(interval) or interval <= 0:
        raise IntakeError("--interval 必须大于 0。")
    if max_frames < 1:
        raise IntakeError("--max-frames 必须大于 0。")

    source = Path(evidence["source"])
    fingerprint = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:8]
    base_dir = (
        Path(output_dir).expanduser().resolve()
        if output_dir
        else Path.cwd() / ".video-intake" / "timelines"
    )
    target_dir = base_dir / f"{source.stem}-{fingerprint}"
    target_dir.mkdir(parents=True, exist_ok=True)

    requested_count = max(1, math.ceil(duration / interval))
    frame_count = min(requested_count, max_frames)
    effective_interval = interval if requested_count <= max_frames else duration / frame_count
    timestamps = [round(index * effective_interval, 3) for index in range(frame_count)]

    entries: list[dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        end = timestamps[index + 1] if index + 1 < len(timestamps) else duration
        frame = target_dir / f"{round(timestamp * 1000):010d}.jpg"
        _run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
                "-q:v",
                "2",
                str(frame),
            ]
        )
        entries.append(
            {
                "start_seconds": timestamp,
                "end_seconds": round(end, 3),
                "timestamp": _format_media_time(timestamp),
                "frame": str(frame),
                "description": "",
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "video-intake.timeline",
        "source": str(source),
        "duration_seconds": duration,
        "requested_interval_seconds": interval,
        "effective_interval_seconds": round(effective_interval, 3),
        "entries": entries,
        "agent_instruction": (
            "依次查看 entries 中的 frame，为每项填写简洁、客观的 description；描述画面和正在进行的操作，"
            "不要猜测看不见或听不清的内容。保留所有时间和路径字段不变，再运行 render-timeline。"
        ),
    }


def render_timeline(manifest_path: str, output_value: str, force: bool) -> dict[str, Any]:
    manifest, source_manifest = _read_json(manifest_path)
    if manifest.get("kind") != "video-intake.timeline" or not isinstance(
        manifest.get("entries"), list
    ):
        raise IntakeError("这不是有效的 video-intake timeline。")
    output = Path(output_value).expanduser().resolve()
    if output.exists() and not force:
        raise IntakeError(f"输出文件已存在：{output}；如需覆盖请添加 --force。")

    lines = [f"# {Path(manifest.get('source', 'video')).name} 内容时间线", ""]
    completed = 0
    for entry in manifest["entries"]:
        if not isinstance(entry, dict):
            raise IntakeError("时间线条目必须是 object。")
        timestamp = entry.get("timestamp")
        description = entry.get("description")
        if not isinstance(timestamp, str) or not isinstance(description, str):
            raise IntakeError("每条时间线都必须包含 timestamp 和 description。")
        cleaned = " ".join(description.split())
        if cleaned:
            completed += 1
        else:
            cleaned = "（待描述）"
        lines.append(f"- `{timestamp}` {cleaned}")
    lines.extend(
        [
            "",
            f"> 来源：`{manifest.get('source', '')}`",
            f"> 时间线清单：`{source_manifest}`",
            "",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "output": str(output),
        "entries": len(manifest["entries"]),
        "described": completed,
    }


def _frame_fingerprint(source: Path, timestamp: float) -> str:
    result = _run_bytes(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            "scale=9:8,format=gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
    )
    pixels = result.stdout[:72]
    if len(pixels) != 72:
        raise IntakeError(f"无法在 {_format_media_time(timestamp)} 提取视觉指纹。")
    bits = 0
    for row in range(8):
        offset = row * 9
        for column in range(8):
            bits = (bits << 1) | int(pixels[offset + column] > pixels[offset + column + 1])
    mean_luma = round(sum(pixels) / len(pixels))
    return f"{bits:016x}:{mean_luma:02x}"


def visual_signature(evidence: dict[str, Any], samples: int) -> list[str]:
    duration = evidence["video"].get("duration_seconds")
    if not duration or duration <= 0:
        raise IntakeError("无法读取视频时长，不能计算视觉指纹。")
    if not 1 <= samples <= 12:
        raise IntakeError("--samples 必须在 1 到 12 之间。")
    source = Path(evidence["source"])
    timestamps = [duration * (index + 1) / (samples + 1) for index in range(samples)]
    return [_frame_fingerprint(source, timestamp) for timestamp in timestamps]


def _fingerprint_similarity(left: str, right: str) -> float:
    left_hash, left_luma = left.split(":", 1)
    right_hash, right_luma = right.split(":", 1)
    structure = 1 - (int(left_hash, 16) ^ int(right_hash, 16)).bit_count() / 64
    luminance = 1 - abs(int(left_luma, 16) - int(right_luma, 16)) / 255
    return 0.7 * structure + 0.3 * luminance


def signature_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_signature, right_signature = left["signature"], right["signature"]
    if len(left_signature) != len(right_signature) or not left_signature:
        raise IntakeError("视觉指纹采样数量不一致。")
    visual = sum(
        _fingerprint_similarity(left_frame, right_frame)
        for left_frame, right_frame in zip(left_signature, right_signature, strict=True)
    ) / len(left_signature)
    left_duration, right_duration = left["duration_seconds"], right["duration_seconds"]
    duration_match = min(left_duration, right_duration) / max(left_duration, right_duration)
    return round(0.85 * visual + 0.15 * duration_match, 4)


def find_similar_videos(
    directory_value: str, recursive: bool, threshold: float, samples: int, limit: int
) -> dict[str, Any]:
    directory = Path(directory_value).expanduser().resolve()
    if not directory.is_dir():
        raise IntakeError(f"找不到目录：{directory}")
    if not 0.5 <= threshold <= 0.99:
        raise IntakeError("--threshold 必须在 0.5 到 0.99 之间。")
    candidates = sorted(
        path
        for path in (directory.rglob("*") if recursive else directory.glob("*"))
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    if len(candidates) > limit:
        raise IntakeError(
            f"发现 {len(candidates)} 个视频，超过 --limit {limit}；请缩小目录或提高上限。"
        )

    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for candidate in candidates:
        try:
            evidence = inspect_video(str(candidate))
            items.append(
                {
                    "source": evidence["source"],
                    "duration_seconds": evidence["video"]["duration_seconds"],
                    "captured_at": evidence["captured_at"],
                    "signature": visual_signature(evidence, samples),
                }
            )
        except IntakeError as exc:
            errors.append({"source": str(candidate), "error": str(exc)})

    clusters: list[list[dict[str, Any]]] = []
    for item in items:
        matching_cluster = next(
            (
                cluster
                for cluster in clusters
                if min(signature_similarity(item, member) for member in cluster) >= threshold
            ),
            None,
        )
        if matching_cluster is None:
            clusters.append([item])
        else:
            matching_cluster.append(item)

    groups: list[dict[str, Any]] = []
    singles: list[dict[str, Any]] = []
    for cluster in clusters:
        if len(cluster) == 1:
            singles.extend(cluster)
            continue
        pair_scores = [
            signature_similarity(cluster[left], cluster[right])
            for left in range(len(cluster))
            for right in range(left + 1, len(cluster))
        ]
        groups.append(
            {
                "group_id": f"similar-{len(groups) + 1:03d}",
                "minimum_similarity": min(pair_scores),
                "members": cluster,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "video-intake.similarity-report",
        "directory": str(directory),
        "threshold": threshold,
        "samples": samples,
        "groups": groups,
        "singles": singles,
        "errors": errors,
        "summary": {
            "videos": len(candidates),
            "similar_groups": len(groups),
            "grouped_videos": sum(len(group["members"]) for group in groups),
            "single_videos": len(singles),
            "failed": len(errors),
        },
    }


def _clean_subject(value: str) -> str:
    normalized = SAFE_SUBJECT.sub("_", value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_.-")
    if not normalized:
        raise IntakeError("标题在清理特殊字符后为空；请提供能描述内容的标题。")
    return normalized[:64]


def propose_name(evidence: dict[str, Any], title: str, take: int | None) -> dict[str, Any]:
    captured_at = datetime.fromisoformat(evidence["captured_at"])
    subject = _clean_subject(title)
    take_suffix = f"_take-{take:02d}" if take else ""
    filename = f"{captured_at:%Y%m%d-%H%M%S}_{subject}{take_suffix}{evidence['file']['extension']}"
    source = Path(evidence["source"])
    proposed = source.with_name(filename)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(source),
        "proposed_path": str(proposed),
        "proposed_filename": filename,
        "title": title,
        "take": take,
        "naming_rule": "YYYYMMDD-HHMMSS_内容主题_take-序号.扩展名",
        "destination_exists": proposed.exists() and proposed != source,
        "requires_explicit_apply": True,
    }


def apply_rename(proposal: dict[str, Any], yes: bool) -> dict[str, Any]:
    if not yes:
        raise IntakeError("改名尚未执行。核对 proposed_path 后重新运行，并添加 --yes。")
    source, destination = Path(proposal["source"]), Path(proposal["proposed_path"])
    if not source.is_file():
        raise IntakeError(f"原始文件已不存在：{source}")
    if source == destination:
        return {**proposal, "renamed": False, "reason": "文件名已经符合提案"}
    if destination.exists():
        raise IntakeError(f"目标文件已存在，为避免覆盖已停止：{destination}")
    shutil.move(str(source), str(destination))
    return {**proposal, "renamed": True}


def scan_directory(
    directory_value: str,
    output_dir: str | None,
    recursive: bool,
    contact_sheets: bool,
    limit: int,
) -> dict[str, Any]:
    directory = Path(directory_value).expanduser().resolve()
    if not directory.is_dir():
        raise IntakeError(f"找不到目录：{directory}")
    candidates = sorted(
        path
        for path in (directory.rglob("*") if recursive else directory.glob("*"))
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    if len(candidates) > limit:
        raise IntakeError(
            f"发现 {len(candidates)} 个视频，超过 --limit {limit}；请缩小目录或提高上限。"
        )
    items, errors = [], []
    for candidate in candidates:
        try:
            evidence = inspect_video(str(candidate))
            item: dict[str, Any] = {"evidence": evidence}
            if contact_sheets:
                item["contact_sheet"] = str(create_contact_sheet(evidence, output_dir))
            items.append(item)
        except IntakeError as exc:
            errors.append({"source": str(candidate), "error": str(exc)})
    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "recursive": recursive,
        "items": items,
        "errors": errors,
        "summary": {
            "videos_found": len(candidates),
            "inspected": len(items),
            "failed": len(errors),
        },
        "next_step": "让 Agent 为每条 item 写入 title，再使用 video-intake plan <rename-requests.json> 生成批量改名提案。",
    }


def _read_json(path_value: str) -> tuple[dict[str, Any], Path]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise IntakeError(f"找不到 JSON 文件：{path}")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IntakeError(f"JSON 格式无效：{exc}") from exc
    if not isinstance(loaded, dict):
        raise IntakeError("JSON 根对象必须是 object。")
    return loaded, path


def _resolve_request_source(value: Any, manifest_path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntakeError("每条请求都必须包含非空 source。")
    source = Path(value).expanduser()
    if not source.is_absolute():
        source = manifest_path.parent / source
    return str(source.resolve())


def build_batch_plan(request_path: str) -> dict[str, Any]:
    request, manifest_path = _read_json(request_path)
    requests = request.get("requests")
    if not isinstance(requests, list) or not requests:
        raise IntakeError("请求文件需要包含非空 requests 数组。")
    proposals: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, item in enumerate(requests):
        try:
            if not isinstance(item, dict):
                raise IntakeError("请求项必须是 object。")
            title = item.get("title")
            if not isinstance(title, str):
                raise IntakeError("每条请求都必须包含字符串 title。")
            take = item.get("take")
            if take is not None and (
                isinstance(take, bool) or not isinstance(take, int) or not 1 <= take <= 99
            ):
                raise IntakeError("take 必须是 1 到 99 的整数。")
            evidence = inspect_video(_resolve_request_source(item.get("source"), manifest_path))
            proposals.append(propose_name(evidence, title, take))
        except IntakeError as exc:
            errors.append({"index": index, "error": str(exc)})
    destinations = [proposal["proposed_path"] for proposal in proposals]
    duplicate_destinations = sorted({item for item in destinations if destinations.count(item) > 1})
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "video-intake.rename-plan",
        "source_request": str(manifest_path),
        "proposals": proposals,
        "errors": errors,
        "valid": not errors
        and not duplicate_destinations
        and not any(item["destination_exists"] for item in proposals),
        "blocking_issues": {
            "duplicate_destinations": duplicate_destinations,
            "existing_destinations": [
                item["proposed_path"] for item in proposals if item["destination_exists"]
            ],
        },
        "requires_explicit_apply": True,
    }


def _validate_batch_plan(plan: dict[str, Any]) -> list[tuple[Path, Path]]:
    if plan.get("kind") != "video-intake.rename-plan" or not isinstance(
        plan.get("proposals"), list
    ):
        raise IntakeError("这不是有效的 video-intake rename plan。")
    if plan.get("errors"):
        raise IntakeError("计划包含无效请求，不能执行。")
    if not plan["proposals"]:
        raise IntakeError("计划没有可执行的改名项。")
    pairs: list[tuple[Path, Path]] = []
    destinations: set[Path] = set()
    sources: set[Path] = set()
    for proposal in plan["proposals"]:
        if not isinstance(proposal, dict):
            raise IntakeError("计划项必须是 object。")
        raw_source = Path(proposal.get("source", "")).expanduser()
        raw_destination = Path(proposal.get("proposed_path", "")).expanduser()
        if not raw_source.is_absolute() or not raw_destination.is_absolute():
            raise IntakeError("计划中的源和目标路径必须是绝对路径。")
        source, destination = raw_source.resolve(), raw_destination.resolve()
        title, take = proposal.get("title"), proposal.get("take")
        if not isinstance(title, str) or (
            take is not None
            and (isinstance(take, bool) or not isinstance(take, int) or not 1 <= take <= 99)
        ):
            raise IntakeError("计划项包含无效的 title 或 take。")
        if not source.is_file():
            raise IntakeError(f"原始文件已不存在：{source}")
        expected = propose_name(inspect_video(str(source)), title, take)
        if destination != Path(expected["proposed_path"]):
            raise IntakeError("计划目标与当前源文件的受控命名规则不一致。请重新生成计划。")
        if source in sources:
            raise IntakeError(f"计划重复引用同一个源文件：{source}")
        if destination in destinations:
            raise IntakeError(f"计划存在重复目标文件：{destination}")
        if destination.exists() and destination != source:
            raise IntakeError(f"目标文件已存在，为避免覆盖已停止：{destination}")
        pairs.append((source, destination))
        sources.add(source)
        destinations.add(destination)
    if destinations & sources - {source for source, destination in pairs if source == destination}:
        raise IntakeError("计划不能把一个文件改成另一个待改名文件的原名。")
    return pairs


def apply_batch_plan(plan_path: str, yes: bool) -> dict[str, Any]:
    if not yes:
        raise IntakeError("批量改名尚未执行。核对计划后重新运行，并添加 --yes。")
    plan, path = _read_json(plan_path)
    pairs = _validate_batch_plan(plan)
    completed: list[tuple[Path, Path]] = []
    try:
        for source, destination in pairs:
            if source != destination:
                shutil.move(str(source), str(destination))
                completed.append((source, destination))
    except OSError as exc:
        rollback_errors = []
        for source, destination in reversed(completed):
            try:
                if destination.exists() and not source.exists():
                    shutil.move(str(destination), str(source))
            except OSError as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        suffix = f"；回滚失败：{rollback_errors}" if rollback_errors else "；已回滚已完成的改名"
        raise IntakeError(f"批量改名失败：{exc}{suffix}") from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "plan": str(path),
        "renamed": len(completed),
        "unchanged": len(pairs) - len(completed),
    }


def _archive_plan_digest(plan: dict[str, Any]) -> str:
    payload = {key: value for key, value in plan.items() if key != "integrity_sha256"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_archive_plan(report_path: str, destination_value: str) -> dict[str, Any]:
    report, source_report = _read_json(report_path)
    if report.get("kind") != "video-intake.similarity-report" or not isinstance(
        report.get("groups"), list
    ):
        raise IntakeError("这不是有效的 video-intake similarity report。")
    archive_root = Path(destination_value).expanduser().resolve()
    moves: list[dict[str, Any]] = []
    issues: list[str] = []
    for group in report["groups"]:
        if not isinstance(group, dict) or not re.fullmatch(
            r"similar-\d{3,}", str(group.get("group_id", ""))
        ):
            issues.append("相似组包含无效的 group_id。")
            continue
        group_id = group["group_id"]
        members = group.get("members")
        if not isinstance(members, list) or len(members) < 2:
            issues.append(f"{group_id} 少于两个成员。")
            continue
        for member in members:
            if not isinstance(member, dict) or not isinstance(member.get("source"), str):
                issues.append(f"{group_id} 包含无效成员。")
                continue
            source = Path(member["source"]).expanduser().resolve()
            destination = archive_root / group_id / source.name
            if not source.is_file():
                issues.append(f"原始文件已不存在：{source}")
            moves.append(
                {
                    "group_id": group_id,
                    "source": str(source),
                    "destination": str(destination),
                    "destination_exists": destination.exists() and destination != source,
                }
            )

    destinations = [move["destination"] for move in moves]
    duplicate_destinations = sorted(
        {destination for destination in destinations if destinations.count(destination) > 1}
    )
    existing_destinations = [move["destination"] for move in moves if move["destination_exists"]]
    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "video-intake.archive-plan",
        "source_report": str(source_report),
        "archive_root": str(archive_root),
        "moves": moves,
        "valid": bool(moves)
        and not issues
        and not duplicate_destinations
        and not existing_destinations,
        "blocking_issues": {
            "errors": issues,
            "duplicate_destinations": duplicate_destinations,
            "existing_destinations": existing_destinations,
        },
        "requires_explicit_apply": True,
    }
    plan["integrity_sha256"] = _archive_plan_digest(plan)
    return plan


def _validate_archive_plan(plan: dict[str, Any]) -> tuple[Path, list[tuple[Path, Path]]]:
    if plan.get("kind") != "video-intake.archive-plan" or not isinstance(plan.get("moves"), list):
        raise IntakeError("这不是有效的 video-intake archive plan。")
    if plan.get("integrity_sha256") != _archive_plan_digest(plan):
        raise IntakeError("归档计划完整性校验失败；请重新生成计划。")
    if not plan.get("valid") or plan.get("blocking_issues", {}).get("errors"):
        raise IntakeError("归档计划包含阻塞问题，不能执行。")
    archive_root_raw = Path(plan.get("archive_root", "")).expanduser()
    if not archive_root_raw.is_absolute():
        raise IntakeError("archive_root 必须是绝对路径。")
    archive_root = archive_root_raw.resolve()
    pairs: list[tuple[Path, Path]] = []
    sources: set[Path] = set()
    destinations: set[Path] = set()
    for move in plan["moves"]:
        if not isinstance(move, dict):
            raise IntakeError("归档计划项必须是 object。")
        group_id = str(move.get("group_id", ""))
        if not re.fullmatch(r"similar-\d{3,}", group_id):
            raise IntakeError("归档计划包含无效 group_id。")
        raw_source = Path(move.get("source", "")).expanduser()
        raw_destination = Path(move.get("destination", "")).expanduser()
        if not raw_source.is_absolute() or not raw_destination.is_absolute():
            raise IntakeError("归档计划中的路径必须是绝对路径。")
        source, destination = raw_source.resolve(), raw_destination.resolve()
        if not source.is_file():
            raise IntakeError(f"原始文件已不存在：{source}")
        expected_parent = archive_root / group_id
        if destination.parent != expected_parent or destination.name != source.name:
            raise IntakeError("归档目标必须保留原文件名，并位于计划指定的相似组目录。")
        if source in sources or destination in destinations:
            raise IntakeError("归档计划包含重复的源或目标路径。")
        if destination.exists() and destination != source:
            raise IntakeError(f"目标文件已存在，为避免覆盖已停止：{destination}")
        sources.add(source)
        destinations.add(destination)
        pairs.append((source, destination))
    if not pairs:
        raise IntakeError("归档计划没有可执行项。")
    return archive_root, pairs


def apply_archive_plan(plan_path: str, yes: bool) -> dict[str, Any]:
    if not yes:
        raise IntakeError("归档尚未执行。核对计划后重新运行，并添加 --yes。")
    plan, path = _read_json(plan_path)
    archive_root, pairs = _validate_archive_plan(plan)
    completed: list[tuple[Path, Path]] = []
    created_directories: set[Path] = set()
    try:
        for source, destination in pairs:
            if source == destination:
                continue
            if not destination.parent.exists():
                destination.parent.mkdir(parents=True, exist_ok=False)
                created_directories.add(destination.parent)
            shutil.move(str(source), str(destination))
            completed.append((source, destination))
    except OSError as exc:
        rollback_errors = []
        for source, destination in reversed(completed):
            try:
                if destination.exists() and not source.exists():
                    source.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(destination), str(source))
            except OSError as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        for directory in sorted(created_directories, reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        suffix = f"；回滚失败：{rollback_errors}" if rollback_errors else "；已回滚已完成的归档"
        raise IntakeError(f"归档失败：{exc}{suffix}") from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "plan": str(path),
        "archive_root": str(archive_root),
        "archived": len(completed),
        "unchanged": len(pairs) - len(completed),
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_target(
    target_value: str,
    output_dir: str | None,
    recursive: bool,
    timeline_interval: float | None,
    max_frames: int,
    threshold: float,
    samples: int,
    limit: int,
) -> dict[str, Any]:
    target = Path(target_value).expanduser().resolve()
    if not target.exists():
        raise IntakeError(f"找不到输入：{target}")

    if target.is_file():
        evidence = inspect_video(str(target))
        fingerprint = hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:8]
        bundle = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else target.parent / ".video-intake" / f"{target.stem}-{fingerprint}"
        )
        bundle.mkdir(parents=True, exist_ok=True)
        contact_sheet = create_contact_sheet(evidence, str(bundle / "evidence"))
        duration = evidence["video"].get("duration_seconds") or 1
        interval = timeline_interval if timeline_interval is not None else max(3.0, duration / 12)
        timeline = create_timeline(evidence, str(bundle / "frames"), interval, max_frames)
        inspect_result = {
            "schema_version": SCHEMA_VERSION,
            "evidence": evidence,
            "contact_sheet": str(contact_sheet),
            "agent_instruction": agent_instruction(evidence, contact_sheet),
        }
        inspect_path = bundle / "inspect.json"
        timeline_path = bundle / "timeline.json"
        _write_json(inspect_path, inspect_result)
        _write_json(timeline_path, timeline)
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "video-intake.prepared-video",
            "source": str(target),
            "bundle": str(bundle),
            "inspect_json": str(inspect_path),
            "contact_sheet": str(contact_sheet),
            "timeline_json": str(timeline_path),
            "timeline_frames": len(timeline["entries"]),
            "next_step": "Agent 查看联系表和时间线帧后，可填写描述并生成命名提案。",
        }

    if target.is_dir():
        bundle = Path(output_dir).expanduser().resolve() if output_dir else target / ".video-intake"
        bundle.mkdir(parents=True, exist_ok=True)
        scan = scan_directory(str(target), str(bundle / "contact-sheets"), recursive, True, limit)
        similarity = find_similar_videos(str(target), recursive, threshold, samples, limit)
        scan_path = bundle / "scan.json"
        similarity_path = bundle / "similarity.json"
        _write_json(scan_path, scan)
        _write_json(similarity_path, similarity)
        failed_sources = {item["source"] for item in [*scan["errors"], *similarity["errors"]]}
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "video-intake.prepared-directory",
            "source": str(target),
            "bundle": str(bundle),
            "scan_json": str(scan_path),
            "similarity_json": str(similarity_path),
            "summary": {
                "videos": scan["summary"]["videos_found"],
                "similar_groups": similarity["summary"]["similar_groups"],
                "grouped_videos": similarity["summary"]["grouped_videos"],
                "single_videos": similarity["summary"]["single_videos"],
                "failed": len(failed_sources),
            },
            "next_step": "Agent 审核联系表与相似组后，可生成批量命名或归档计划。",
        }
    raise IntakeError(f"输入既不是普通文件也不是目录：{target}")


def agent_instruction(evidence: dict[str, Any], contact_sheet: Path) -> str:
    return "\n".join(
        [
            "你正在为一条原始视频命名。请先查看联系表，并结合下面的客观元数据判断内容。",
            "只输出一个简洁、可检索的中文内容主题（2–12 个词）；不要包含日期、时间、扩展名、take 编号或猜测性人物姓名。",
            f"联系表：{contact_sheet}",
            "元数据：",
            json.dumps(evidence, ensure_ascii=False, indent=2),
            "之后由调用者执行：video-intake propose <视频路径> --title '<你的主题>' [--take N]。",
            "改名必须由用户或上层 Agent 审核 proposed_path 后，才可以使用 video-intake apply ... --yes。",
        ]
    )


def _emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-intake",
        description="为 Agent 提供可审核的视频命名、描述与相似归档工作流",
        epilog="快捷用法：video-intake <视频或目录路径>",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="检查 Python、FFmpeg 和 FFprobe 是否可用")

    prepare = commands.add_parser("prepare", help="一条命令准备视频或目录的完整 Agent 证据包")
    prepare.add_argument("target")
    prepare.add_argument("--output-dir", help="证据包输出目录；默认写入输入旁的 .video-intake")
    prepare.add_argument("--recursive", action="store_true", help="目录输入时递归扫描")
    prepare.add_argument("--timeline-interval", type=float, help="视频时间线抽帧间隔；默认自动计算")
    prepare.add_argument("--max-frames", type=int, default=12, help="视频时间线最大帧数；默认 12")
    prepare.add_argument("--threshold", type=float, default=0.82, help="目录相似阈值；默认 0.82")
    prepare.add_argument(
        "--samples", type=int, default=5, help="目录中每条视频的指纹采样数；默认 5"
    )
    prepare.add_argument("--limit", type=int, default=100, choices=range(1, 1001), metavar="1-1000")

    inspect = commands.add_parser("inspect", help="读取元数据并生成联系表，不会修改原视频")
    inspect.add_argument("video")
    inspect.add_argument("--output-dir", help="联系表输出目录；默认当前目录/.video-intake")

    timeline = commands.add_parser("timeline", help="按真实视频时间抽帧，生成待描述的内容时间线")
    timeline.add_argument("video")
    timeline.add_argument(
        "--output-dir", help="分镜帧输出目录；默认当前目录/.video-intake/timelines"
    )
    timeline.add_argument("--interval", type=float, default=10.0, help="抽帧间隔秒数；默认 10")
    timeline.add_argument("--max-frames", type=int, default=24, help="最大帧数；默认 24")

    render_timeline_parser = commands.add_parser(
        "render-timeline", help="把 Agent 填写过的时间线 JSON 渲染为 Markdown"
    )
    render_timeline_parser.add_argument("timeline_json")
    render_timeline_parser.add_argument("--output", required=True, help="Markdown 输出路径")
    render_timeline_parser.add_argument("--force", action="store_true", help="允许覆盖已有输出")

    scan = commands.add_parser("scan", help="扫描一个目录并生成供 Agent 审核的证据清单，不会改名")
    scan.add_argument("directory")
    scan.add_argument("--output-dir", help="联系表输出目录；默认当前目录/.video-intake")
    scan.add_argument("--recursive", action="store_true", help="递归扫描子目录")
    scan.add_argument("--no-contact-sheets", action="store_true", help="仅读取元数据，跳过联系表")
    scan.add_argument("--limit", type=int, default=100, choices=range(1, 1001), metavar="1-1000")

    similar = commands.add_parser("similar", help="计算视觉指纹并把相似视频聚类，不会移动文件")
    similar.add_argument("directory")
    similar.add_argument("--recursive", action="store_true", help="递归扫描子目录")
    similar.add_argument(
        "--threshold", type=float, default=0.82, help="相似阈值 0.5-0.99；默认 0.82"
    )
    similar.add_argument("--samples", type=int, default=5, help="每条视频采样帧数 1-12；默认 5")
    similar.add_argument("--limit", type=int, default=100, choices=range(1, 1001), metavar="1-1000")

    archive_plan = commands.add_parser("archive-plan", help="从相似度报告生成可审核的归档计划")
    archive_plan.add_argument("similarity_json")
    archive_plan.add_argument("--destination", required=True, help="相似组归档根目录")

    apply_archive = commands.add_parser("apply-archive-plan", help="执行已审核的相似视频归档计划")
    apply_archive.add_argument("plan_json")
    apply_archive.add_argument("--yes", action="store_true", help="确认执行；没有它绝不会移动文件")

    propose = commands.add_parser("propose", help="根据 Agent 给出的内容主题生成改名提案，不会改名")
    propose.add_argument("video")
    propose.add_argument("--title", required=True, help="视频内容主题，例如：产品开箱_桌面展示")
    propose.add_argument("--take", type=int, choices=range(1, 100), metavar="1-99")

    plan = commands.add_parser("plan", help="从 requests JSON 生成批量改名计划，不会改名")
    plan.add_argument("requests_json", help="包含 source、title 和可选 take 的 requests JSON 文件")

    apply = commands.add_parser("apply", help="执行已经审核过的改名")
    apply.add_argument("video")
    apply.add_argument("--title", required=True)
    apply.add_argument("--take", type=int, choices=range(1, 100), metavar="1-99")
    apply.add_argument("--yes", action="store_true", help="确认执行；没有它绝不会改名")

    apply_plan = commands.add_parser("apply-plan", help="执行已经审核过的批量改名计划")
    apply_plan.add_argument("plan_json")
    apply_plan.add_argument("--yes", action="store_true", help="确认执行；没有它绝不会改名")
    return parser


def main() -> None:
    argv = sys.argv[1:]
    if argv and not argv[0].startswith("-") and argv[0] not in COMMANDS:
        argv.insert(0, "prepare")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            _emit(doctor())
        elif args.command == "prepare":
            _emit(
                prepare_target(
                    args.target,
                    args.output_dir,
                    args.recursive,
                    args.timeline_interval,
                    args.max_frames,
                    args.threshold,
                    args.samples,
                    args.limit,
                )
            )
        elif args.command == "inspect":
            evidence = inspect_video(args.video)
            contact_sheet = create_contact_sheet(evidence, args.output_dir)
            _emit(
                {
                    "schema_version": SCHEMA_VERSION,
                    "evidence": evidence,
                    "contact_sheet": str(contact_sheet),
                    "agent_instruction": agent_instruction(evidence, contact_sheet),
                }
            )
        elif args.command == "timeline":
            evidence = inspect_video(args.video)
            _emit(create_timeline(evidence, args.output_dir, args.interval, args.max_frames))
        elif args.command == "render-timeline":
            _emit(render_timeline(args.timeline_json, args.output, args.force))
        elif args.command == "scan":
            _emit(
                scan_directory(
                    args.directory,
                    args.output_dir,
                    args.recursive,
                    not args.no_contact_sheets,
                    args.limit,
                )
            )
        elif args.command == "similar":
            _emit(
                find_similar_videos(
                    args.directory,
                    args.recursive,
                    args.threshold,
                    args.samples,
                    args.limit,
                )
            )
        elif args.command == "archive-plan":
            _emit(build_archive_plan(args.similarity_json, args.destination))
        elif args.command == "apply-archive-plan":
            _emit(apply_archive_plan(args.plan_json, args.yes))
        elif args.command == "propose":
            evidence = inspect_video(args.video)
            _emit(propose_name(evidence, args.title, args.take))
        elif args.command == "plan":
            _emit(build_batch_plan(args.requests_json))
        elif args.command == "apply":
            evidence = inspect_video(args.video)
            _emit(apply_rename(propose_name(evidence, args.title, args.take), args.yes))
        else:
            _emit(apply_batch_plan(args.plan_json, args.yes))
    except IntakeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
