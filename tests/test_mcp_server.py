import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

import video_intake as core
import video_intake_mcp as server


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client_session() -> AsyncGenerator[ClientSession]:
    async with create_connected_server_and_client_session(
        server.mcp, raise_exceptions=True
    ) as session:
        yield session


@pytest.mark.anyio
async def test_mcp_exposes_tools_resource_prompt_and_structured_output(
    client_session: ClientSession,
) -> None:
    tools = await client_session.list_tools()
    resources = await client_session.list_resources()
    prompts = await client_session.list_prompts()
    result = await client_session.call_tool("doctor", {})

    tools_by_name = {tool.name: tool for tool in tools.tools}
    assert set(tools_by_name) == {
        "apply_archive_plan",
        "apply_rename",
        "apply_rename_plan",
        "build_archive_plan",
        "build_rename_plan",
        "doctor",
        "extract_timeline",
        "find_similar_videos",
        "inspect_video",
        "prepare",
        "propose_rename",
        "render_timeline",
    }
    assert [str(item.uri) for item in resources.resources] == ["video-intake://workflow"]
    assert [item.name for item in prompts.prompts] == ["review_video_workflow"]
    assert tools_by_name["propose_rename"].annotations.readOnlyHint is True
    assert tools_by_name["apply_rename"].annotations.destructiveHint is True
    assert result.structuredContent["kind"] == "video-intake.doctor"
    assert result.structuredContent["mcp"]["transport"] == "stdio or streamable-http"


@pytest.mark.anyio
async def test_mcp_client_can_call_propose_rename_with_structured_output(
    client_session: ClientSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "raw.mov"
    source.write_bytes(b"video")
    monkeypatch.setattr(
        core,
        "inspect_video",
        lambda path: {
            "source": path,
            "captured_at": "2026-07-13T12:30:00+08:00",
            "file": {"extension": ".mov"},
        },
    )

    result = await client_session.call_tool(
        "propose_rename",
        {"video": str(source), "title": "产品演示", "take": 2},
    )

    assert result.structuredContent["proposed_filename"] == ("20260713-123000_产品演示_take-02.mov")
    assert result.structuredContent["requires_explicit_apply"] is True


def test_filesystem_scope_rejects_paths_outside_allowed_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"video")
    monkeypatch.setenv("VIDEO_INTAKE_ALLOWED_ROOTS", str(allowed))

    with pytest.raises(core.IntakeError, match="超出 MCP 允许目录"):
        server.propose_rename(str(outside), "测试")


def test_apply_rename_requires_the_exact_proposed_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "raw.mov"
    source.write_bytes(b"video")

    def fake_inspect(path: str) -> dict:
        return {
            "source": path,
            "captured_at": "2026-07-13T12:30:00+08:00",
            "file": {"extension": ".mov"},
        }

    monkeypatch.setattr(core, "inspect_video", fake_inspect)
    proposed = tmp_path / "20260713-123000_产品演示.mov"

    with pytest.raises(core.IntakeError, match="确认路径与当前提案不一致"):
        server.apply_rename(str(source), "产品演示", str(tmp_path / "wrong.mov"))
    assert source.exists()

    result = server.apply_rename(str(source), "产品演示", str(proposed))
    assert result["renamed"] is True
    assert proposed.is_file()


def test_saved_plan_requires_matching_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "raw.mov"
    source.write_bytes(b"video")
    requests = tmp_path / "requests.json"
    requests.write_text(
        json.dumps({"requests": [{"source": str(source), "title": "测试"}]}),
        encoding="utf-8",
    )

    def fake_inspect(path: str) -> dict:
        return {
            "source": path,
            "captured_at": "2026-07-13T12:30:00+08:00",
            "file": {"extension": ".mov"},
        }

    monkeypatch.setattr(core, "inspect_video", fake_inspect)
    plan_path = tmp_path / "rename-plan.json"
    plan = server.build_rename_plan(str(requests), str(plan_path))

    with pytest.raises(core.IntakeError, match="确认摘要与当前计划不一致"):
        server.apply_rename_plan(str(plan_path), "0" * 64)
    assert source.exists()

    result = server.apply_rename_plan(str(plan_path), plan["confirmation_sha256"])
    assert result["renamed"] == 1
    assert not source.exists()
