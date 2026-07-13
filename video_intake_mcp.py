"""MCP server for Video Intake Agent.

The server keeps semantic decisions in the MCP host while reusing the
deterministic media and filesystem operations from :mod:`video_intake`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

import video_intake as core

SERVER_INSTRUCTIONS = """
Use Video Intake Agent to prepare local video evidence, inspect timestamped
frames, and produce reviewable rename or archive plans. Treat visual similarity
as heuristic and inspect representative frames before acting. Never call an
apply tool until the user has approved the exact destination paths. Apply tools
require an exact path or SHA-256 confirmation value and still run the core
collision, integrity, and rollback checks.
""".strip()

mcp = FastMCP(
    "Video Intake Agent",
    instructions=SERVER_INSTRUCTIONS,
    website_url="https://github.com/Freakz2z/video-intake-agent",
    json_response=True,
)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
LOCAL_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)


def _allowed_roots() -> tuple[Path, ...]:
    raw = os.environ.get("VIDEO_INTAKE_ALLOWED_ROOTS", "")
    return tuple(
        Path(value).expanduser().resolve() for value in raw.split(os.pathsep) if value.strip()
    )


def _guard_path(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    roots = _allowed_roots()
    if roots and not any(path == root or path.is_relative_to(root) for root in roots):
        rendered = ", ".join(str(root) for root in roots)
        raise core.IntakeError(f"{label}超出 MCP 允许目录：{path}；允许目录：{rendered}")
    return path


def _guard_optional_path(value: str | None, label: str) -> str | None:
    return str(_guard_path(value, label)) if value else None


def _guard_plan_paths(plan: dict[str, Any]) -> None:
    for key in ("source_request", "source_report", "archive_root"):
        value = plan.get(key)
        if isinstance(value, str):
            _guard_path(value, key)
    for collection in ("proposals", "moves"):
        for item in plan.get(collection, []):
            if not isinstance(item, dict):
                continue
            for key in ("source", "proposed_path", "destination"):
                value = item.get(key)
                if isinstance(value, str):
                    _guard_path(value, key)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _save_plan(plan: dict[str, Any], output_path: str | None) -> dict[str, Any]:
    if not output_path:
        return plan
    path = _guard_path(output_path, "计划输出路径")
    if path.exists():
        raise core.IntakeError(f"计划输出文件已存在，为避免覆盖已停止：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        **plan,
        "plan_path": str(path),
        "confirmation_sha256": _file_sha256(path),
    }


@mcp.resource("video-intake://workflow")
def workflow_resource() -> str:
    """Return the safe, reviewable workflow shared by all tools."""

    return SERVER_INSTRUCTIONS


@mcp.prompt(name="review_video_workflow", title="Review a video intake workflow")
def review_video_workflow(target: str, goal: str = "命名、描述并整理视频") -> str:
    """Build a reusable prompt for reviewing one video or directory."""

    return "\n".join(
        [
            f"目标：{goal}",
            f"输入：{target}",
            "先调用 prepare 生成本地证据，再查看联系表和时间线帧。",
            "描述只能基于可见证据，不猜测人物身份、品牌或未听到的语音。",
            "先生成提案或计划并展示全部源/目标路径；只有用户明确批准后才能调用 apply 工具。",
            "执行后检查返回的 renamed、archived、unchanged 和错误字段。",
        ]
    )


@mcp.tool(title="Check video runtime", annotations=READ_ONLY)
def doctor() -> dict[str, Any]:
    """Check Python, FFmpeg, FFprobe, MCP version, and filesystem scope."""

    result = core.doctor()
    result["mcp"] = {
        "transport": "stdio or streamable-http",
        "allowed_roots": [str(root) for root in _allowed_roots()],
        "filesystem_scope_enabled": bool(_allowed_roots()),
    }
    return result


@mcp.tool(title="Prepare video evidence", annotations=LOCAL_WRITE)
def prepare(
    target: str,
    output_dir: str | None = None,
    recursive: bool = False,
    timeline_interval: float | None = None,
    max_frames: int = 12,
    threshold: float = 0.82,
    samples: int = 5,
    limit: int = 100,
) -> dict[str, Any]:
    """Prepare an Agent-readable evidence bundle without modifying source videos."""

    guarded_target = _guard_path(target, "输入路径")
    guarded_output = _guard_optional_path(output_dir, "证据输出目录")
    return core.prepare_target(
        str(guarded_target),
        guarded_output,
        recursive,
        timeline_interval,
        max_frames,
        threshold,
        samples,
        limit,
    )


@mcp.tool(title="Inspect one video", annotations=LOCAL_WRITE)
def inspect_video(video: str, output_dir: str | None = None) -> dict[str, Any]:
    """Read metadata and create a contact sheet; the source video is unchanged."""

    source = _guard_path(video, "视频路径")
    target_dir = (
        _guard_path(output_dir, "联系表输出目录")
        if output_dir
        else _guard_path(source.parent / ".video-intake" / "evidence", "联系表输出目录")
    )
    evidence = core.inspect_video(str(source))
    contact_sheet = core.create_contact_sheet(evidence, str(target_dir))
    return {
        "schema_version": core.SCHEMA_VERSION,
        "evidence": evidence,
        "contact_sheet": str(contact_sheet),
        "agent_instruction": core.agent_instruction(evidence, contact_sheet),
    }


@mcp.tool(title="Extract a timestamped timeline", annotations=LOCAL_WRITE)
def extract_timeline(
    video: str,
    output_dir: str | None = None,
    interval: float = 10.0,
    max_frames: int = 24,
) -> dict[str, Any]:
    """Extract timestamped storyboard frames for factual Agent descriptions."""

    source = _guard_path(video, "视频路径")
    target_dir = (
        _guard_path(output_dir, "时间线输出目录")
        if output_dir
        else _guard_path(source.parent / ".video-intake" / "timelines", "时间线输出目录")
    )
    evidence = core.inspect_video(str(source))
    return core.create_timeline(evidence, str(target_dir), interval, max_frames)


@mcp.tool(title="Find similar videos", annotations=LOCAL_WRITE)
def find_similar_videos(
    directory: str,
    recursive: bool = False,
    threshold: float = 0.82,
    samples: int = 5,
    limit: int = 100,
    cache_path: str | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Find byte-identical and visually similar videos using local evidence only."""

    source = _guard_path(directory, "视频目录")
    guarded_cache = _guard_optional_path(cache_path, "指纹缓存路径")
    return core.find_similar_videos(
        str(source), recursive, threshold, samples, limit, guarded_cache, use_cache
    )


@mcp.tool(title="Propose a safe filename", annotations=READ_ONLY)
def propose_rename(video: str, title: str, take: int | None = None) -> dict[str, Any]:
    """Generate a reviewable rename proposal without changing the source video."""

    source = _guard_path(video, "视频路径")
    proposal = core.propose_name(core.inspect_video(str(source)), title, take)
    _guard_plan_paths({"proposals": [proposal]})
    return proposal


@mcp.tool(title="Build a batch rename plan", annotations=LOCAL_WRITE)
def build_rename_plan(requests_json: str, output_path: str | None = None) -> dict[str, Any]:
    """Build and optionally save a collision-checked batch rename plan."""

    request_path = _guard_path(requests_json, "批量请求文件")
    plan = core.build_batch_plan(str(request_path))
    _guard_plan_paths(plan)
    return _save_plan(plan, output_path)


@mcp.tool(title="Build a similarity archive plan", annotations=LOCAL_WRITE)
def build_archive_plan(
    similarity_json: str,
    destination: str,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Build and optionally save an integrity-protected archive plan."""

    report_path = _guard_path(similarity_json, "相似度报告")
    archive_root = _guard_path(destination, "归档目录")
    plan = core.build_archive_plan(str(report_path), str(archive_root))
    _guard_plan_paths(plan)
    return _save_plan(plan, output_path)


@mcp.tool(title="Render a reviewed timeline", annotations=LOCAL_WRITE)
def render_timeline(timeline_json: str, output_path: str, force: bool = False) -> dict[str, Any]:
    """Render Agent-filled timeline JSON as Markdown."""

    manifest = _guard_path(timeline_json, "时间线 JSON")
    output = _guard_path(output_path, "Markdown 输出路径")
    return core.render_timeline(str(manifest), str(output), force)


@mcp.tool(title="Apply one approved rename", annotations=DESTRUCTIVE)
def apply_rename(
    video: str,
    title: str,
    confirmed_proposed_path: str,
    take: int | None = None,
) -> dict[str, Any]:
    """Rename one video only when the exact proposed path is supplied after approval."""

    source = _guard_path(video, "视频路径")
    proposal = core.propose_name(core.inspect_video(str(source)), title, take)
    expected = Path(proposal["proposed_path"]).resolve()
    confirmed = _guard_path(confirmed_proposed_path, "确认目标路径")
    if confirmed != expected:
        raise core.IntakeError(f"确认路径与当前提案不一致，未执行。当前提案：{expected}")
    return core.apply_rename(proposal, yes=True)


def _confirmed_plan(plan_path: str, confirmed_sha256: str) -> tuple[Path, dict[str, Any]]:
    path = _guard_path(plan_path, "计划文件")
    if not path.is_file():
        raise core.IntakeError(f"找不到计划文件：{path}")
    actual = _file_sha256(path)
    if confirmed_sha256 != actual:
        raise core.IntakeError(f"确认摘要与当前计划不一致，未执行。当前 SHA-256：{actual}")
    plan = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise core.IntakeError("计划 JSON 根对象必须是 object。")
    _guard_plan_paths(plan)
    return path, plan


@mcp.tool(title="Apply an approved rename plan", annotations=DESTRUCTIVE)
def apply_rename_plan(plan_path: str, confirmed_sha256: str) -> dict[str, Any]:
    """Apply a saved rename plan only when its exact SHA-256 has been approved."""

    path, _ = _confirmed_plan(plan_path, confirmed_sha256)
    return core.apply_batch_plan(str(path), yes=True)


@mcp.tool(title="Apply an approved archive plan", annotations=DESTRUCTIVE)
def apply_archive_plan(plan_path: str, confirmed_sha256: str) -> dict[str, Any]:
    """Apply a saved archive plan only when its exact SHA-256 has been approved."""

    path, _ = _confirmed_plan(plan_path, confirmed_sha256)
    return core.apply_archive_plan(str(path), yes=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Video Intake Agent MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.environ.get("VIDEO_INTAKE_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.environ.get("VIDEO_INTAKE_MCP_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("VIDEO_INTAKE_MCP_PORT", "8000"))
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
