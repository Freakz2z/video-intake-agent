import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

import video_intake
from video_intake import (
    IntakeError,
    apply_archive_plan,
    apply_batch_plan,
    apply_rename,
    build_archive_plan,
    build_batch_plan,
    create_timeline,
    doctor,
    prepare_target,
    propose_name,
    scan_directory,
    signature_similarity,
)


def evidence(tmp_path: Path) -> dict:
    source = tmp_path / "IMG_1001.MOV"
    source.write_bytes(b"video")
    return {
        "source": str(source),
        "file": {"extension": ".mov"},
        "captured_at": datetime(2026, 7, 12, 9, 5, 3).isoformat(),
    }


def test_proposal_uses_timestamp_subject_and_take(tmp_path: Path) -> None:
    proposal = propose_name(evidence(tmp_path), "咖啡拉花 / 俯拍", 2)
    assert proposal["proposed_filename"] == "20260712-090503_咖啡拉花_俯拍_take-02.mov"
    assert proposal["requires_explicit_apply"] is True


def test_doctor_reports_runtime_and_required_tools() -> None:
    result = doctor()

    assert result["kind"] == "video-intake.doctor"
    assert result["python"]["available"] is True
    assert set(result["tools"]) == {"ffmpeg", "ffprobe"}
    assert result["ready"] is True


def test_apply_requires_explicit_confirmation(tmp_path: Path) -> None:
    proposal = propose_name(evidence(tmp_path), "桌面演示", None)
    with pytest.raises(IntakeError, match="--yes"):
        apply_rename(proposal, yes=False)
    assert Path(proposal["source"]).exists()


def test_apply_never_overwrites_existing_file(tmp_path: Path) -> None:
    proposal = propose_name(evidence(tmp_path), "桌面演示", None)
    Path(proposal["proposed_path"]).write_bytes(b"existing")
    with pytest.raises(IntakeError, match="已存在"):
        apply_rename(proposal, yes=True)


def test_scan_directory_collects_supported_videos_without_contact_sheets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "clip.mov").write_bytes(b"video")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    monkeypatch.setattr(video_intake, "inspect_video", lambda path: evidence(tmp_path))

    result = scan_directory(str(tmp_path), None, recursive=False, contact_sheets=False, limit=10)

    assert result["summary"] == {"videos_found": 1, "inspected": 1, "failed": 0}
    assert result["items"][0]["evidence"]["source"].endswith("IMG_1001.MOV")


def test_plan_and_apply_batch_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "recording.mov"
    source.write_bytes(b"video")
    request_path = tmp_path / "requests.json"
    request_path.write_text(
        json.dumps({"requests": [{"source": "recording.mov", "title": "产品开箱", "take": 1}]}),
        encoding="utf-8",
    )

    def fake_inspect(path: str) -> dict:
        result = evidence(tmp_path)
        result["source"] = str(Path(path))
        result["file"]["extension"] = ".mov"
        return result

    monkeypatch.setattr(video_intake, "inspect_video", fake_inspect)
    plan = build_batch_plan(str(request_path))
    assert plan["valid"] is True
    assert plan["proposals"][0]["proposed_filename"] == "20260712-090503_产品开箱_take-01.mov"

    plan_path = tmp_path / "rename-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    result = apply_batch_plan(str(plan_path), yes=True)
    assert result["renamed"] == 1
    assert not source.exists()
    assert (tmp_path / "20260712-090503_产品开箱_take-01.mov").exists()


def test_apply_batch_rejects_tampered_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "recording.mov"
    source.write_bytes(b"video")
    request_path = tmp_path / "requests.json"
    request_path.write_text(
        json.dumps({"requests": [{"source": "recording.mov", "title": "产品开箱"}]}),
        encoding="utf-8",
    )

    def fake_inspect(path: str) -> dict:
        result = evidence(tmp_path)
        result["source"] = str(Path(path))
        result["file"]["extension"] = ".mov"
        return result

    monkeypatch.setattr(video_intake, "inspect_video", fake_inspect)
    plan = build_batch_plan(str(request_path))
    plan["proposals"][0]["proposed_path"] = str(tmp_path / "outside-the-rule.mov")
    plan_path = tmp_path / "tampered-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(IntakeError, match="受控命名规则"):
        apply_batch_plan(str(plan_path), yes=True)
    assert source.exists()


def test_signature_similarity_uses_structure_luminance_and_duration() -> None:
    black = {"signature": ["0000000000000000:00"], "duration_seconds": 10.0}
    same_black = {"signature": ["0000000000000000:00"], "duration_seconds": 10.0}
    white = {"signature": ["0000000000000000:ff"], "duration_seconds": 10.0}

    assert signature_similarity(black, same_black) == 1.0
    assert signature_similarity(black, white) < 0.82


def test_timeline_frame_cap_still_covers_full_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = evidence(tmp_path)
    item["video"] = {"duration_seconds": 100.0}
    monkeypatch.setattr(video_intake, "_run", lambda command: None)

    timeline = create_timeline(item, str(tmp_path / "frames"), interval=1.0, max_frames=2)

    assert [entry["start_seconds"] for entry in timeline["entries"]] == [0.0, 50.0]
    assert timeline["entries"][-1]["end_seconds"] == 100.0
    assert timeline["effective_interval_seconds"] == 50.0


def test_archive_plan_moves_similar_group_without_renaming(tmp_path: Path) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    report = {
        "kind": "video-intake.similarity-report",
        "groups": [
            {
                "group_id": "similar-001",
                "members": [{"source": str(first)}, {"source": str(second)}],
            }
        ],
    }
    report_path = tmp_path / "similarity.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    plan = build_archive_plan(str(report_path), str(tmp_path / "archive"))
    assert plan["valid"] is True

    plan_path = tmp_path / "archive-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    result = apply_archive_plan(str(plan_path), yes=True)

    assert result["archived"] == 2
    assert (tmp_path / "archive/similar-001/first.mp4").read_bytes() == b"first"
    assert (tmp_path / "archive/similar-001/second.mp4").read_bytes() == b"second"


def test_archive_plan_rejects_tampering(tmp_path: Path) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    report_path = tmp_path / "similarity.json"
    report_path.write_text(
        json.dumps(
            {
                "kind": "video-intake.similarity-report",
                "groups": [
                    {
                        "group_id": "similar-001",
                        "members": [{"source": str(first)}, {"source": str(second)}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = build_archive_plan(str(report_path), str(tmp_path / "archive"))
    plan["moves"][0]["destination"] = str(tmp_path / "unexpected.mp4")
    plan_path = tmp_path / "tampered-archive-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(IntakeError, match="完整性校验失败"):
        apply_archive_plan(str(plan_path), yes=True)
    assert first.exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is required for demo matching")
def test_one_command_directory_bundle_groups_demo_videos(tmp_path: Path) -> None:
    demo = Path(__file__).parents[1] / "demo" / "media"
    prepared = prepare_target(str(demo), str(tmp_path / "bundle"), False, None, 12, 0.82, 5, 10)
    report = json.loads(Path(prepared["similarity_json"]).read_text(encoding="utf-8"))

    assert prepared["kind"] == "video-intake.prepared-directory"
    grouped = {Path(member["source"]).name for member in report["groups"][0]["members"]}
    singles = {Path(member["source"]).name for member in report["singles"]}
    assert grouped == {"bunny-meets-rodents.mp4", "bunny-meets-rodents-mobile.mp4"}
    assert singles == {"forest-chase.mp4"}


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="FFmpeg is required for this end-to-end test"
)
def test_cli_inspect_plan_and_apply_with_real_video(tmp_path: Path) -> None:
    source = tmp_path / "raw.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:d=0.2",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    script = Path(__file__).parents[1] / "video_intake.py"

    inspect = subprocess.run(
        [
            sys.executable,
            str(script),
            "inspect",
            str(source),
            "--output-dir",
            str(tmp_path / "evidence"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    inspected = json.loads(inspect.stdout)
    assert Path(inspected["contact_sheet"]).is_file()

    prepared = subprocess.run(
        [
            sys.executable,
            str(script),
            str(source),
            "--output-dir",
            str(tmp_path / "one-command-bundle"),
            "--timeline-interval",
            "0.1",
            "--max-frames",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    prepared_data = json.loads(prepared.stdout)
    assert prepared_data["kind"] == "video-intake.prepared-video"
    assert Path(prepared_data["inspect_json"]).is_file()
    assert Path(prepared_data["timeline_json"]).is_file()

    timeline = subprocess.run(
        [
            sys.executable,
            str(script),
            "timeline",
            str(source),
            "--output-dir",
            str(tmp_path / "timeline-frames"),
            "--interval",
            "0.1",
            "--max-frames",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    timeline_data = json.loads(timeline.stdout)
    assert len(timeline_data["entries"]) == 2
    assert all(Path(entry["frame"]).is_file() for entry in timeline_data["entries"])
    timeline_data["entries"][0]["description"] = "黑色测试画面"
    timeline_path = tmp_path / "timeline.json"
    timeline_path.write_text(json.dumps(timeline_data), encoding="utf-8")
    markdown_path = tmp_path / "timeline.md"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "render-timeline",
            str(timeline_path),
            "--output",
            str(markdown_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "`00:00:00` 黑色测试画面" in markdown_path.read_text(encoding="utf-8")

    duplicate = tmp_path / "raw-copy.mp4"
    shutil.copy2(source, duplicate)
    similar = subprocess.run(
        [
            sys.executable,
            str(script),
            "similar",
            str(tmp_path),
            "--threshold",
            "0.99",
            "--samples",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    similarity_report = json.loads(similar.stdout)
    assert similarity_report["summary"]["similar_groups"] == 1
    assert similarity_report["summary"]["grouped_videos"] == 2

    requests = tmp_path / "requests.json"
    requests.write_text(
        json.dumps({"requests": [{"source": str(source), "title": "黑色视频", "take": 1}]}),
        encoding="utf-8",
    )
    plan = subprocess.run(
        [sys.executable, str(script), "plan", str(requests)],
        check=True,
        capture_output=True,
        text=True,
    )
    plan_path = tmp_path / "rename-plan.json"
    plan_path.write_text(plan.stdout, encoding="utf-8")
    planned = json.loads(plan.stdout)
    assert planned["valid"] is True

    applied = subprocess.run(
        [sys.executable, str(script), "apply-plan", str(plan_path), "--yes"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(applied.stdout)["renamed"] == 1
    assert not source.exists()
    assert Path(planned["proposals"][0]["proposed_path"]).is_file()
