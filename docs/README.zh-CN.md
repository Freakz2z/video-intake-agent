<div align="center">
  <img src="assets/logo.svg" alt="Video Intake Agent" width="680" />

  <p><strong>用一条本地命令完成视频命名、时间戳内容描述与相似素材整理。</strong></p>

  <p>
    <a href="../README.md">English</a> ·
    <a href="README.zh-CN.md">简体中文</a> ·
    <a href="../CONTRIBUTING.md">Contributing</a> ·
    <a href="CONTRIBUTING.zh-CN.md">贡献指南</a> ·
    <a href="roadmap.md">Roadmap</a> ·
    <a href="privacy.md">隐私说明</a>
  </p>

  <p>
    <a href="https://github.com/Freakz2z/video-intake-agent/actions/workflows/ci.yml"><img src="https://github.com/Freakz2z/video-intake-agent/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB.svg" alt="Python 3.11+" /></a>
    <a href="../LICENSE"><img src="https://img.shields.io/badge/License-MIT-22C55E.svg" alt="MIT License" /></a>
    <img src="https://img.shields.io/badge/API%20key-无需-06B6D4.svg" alt="无需 API Key" />
  </p>
</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/Freakz2z/video-intake-agent/main/demo/media/preview.gif" alt="开放许可的 Big Buck Bunny 演示" width="480" />
</p>

<p align="center"><sub>v0.2 alpha · 源码安装 · 本地优先 · 不依赖云端 API</sub></p>

## 项目用途

Video Intake Agent 面向 Codex、Claude Code 和本地命令行使用，解决录制后文件名混乱、内容难以快速回顾、相似素材散落等问题。

```text
视频或目录
  → FFmpeg 在本地生成证据
  → Codex / Claude Code 理解内容
  → 可审核的文件名、时间线或归档计划
  → 明确确认后才修改文件
```

- 读取视频元数据、拍摄时间和编解码信息。
- 生成联系表和带真实时间点的分镜帧。
- 生成适合 Agent 读取的 JSON 和 Markdown 内容时间线。
- 使用本地多帧视觉指纹查找相似视频、复用持久化缓存，并单独识别完全重复文件。
- 生成带冲突检查、完整性校验和失败回滚的改名/归档计划。
- 核心命令不会上传视频，也不需要 API Key。

项目灵感来自 [`video-use`](https://github.com/browser-use/video-use) 的可审核 Agent 工作流，但更专注于视频剪辑前的素材接收与整理。

## 快速开始

需要 Python 3.11+、[FFmpeg](https://ffmpeg.org/) 和 `ffprobe`。

```bash
git clone https://github.com/Freakz2z/video-intake-agent.git
cd video-intake-agent

python3 -m venv .venv
source .venv/bin/activate
python -m pip install .

video-intake doctor
video-intake /视频或目录的绝对路径
```

Windows 激活命令为 `.venv\Scripts\activate`。

一条命令会生成：

- 输入视频：`inspect.json`、联系表、时间戳分镜帧和 `timeline.json`。
- 输入目录：`scan.json`、联系表、`similarity.json` 和可复用的指纹缓存。
- 所有结果默认位于输入旁边的 `.video-intake/`，不会修改源视频。

## 在 Codex / Claude Code 中使用

- [Codex Skill](../integrations/codex/video-intake/SKILL.md)
- [Claude Code 命令](../integrations/claude-code/commands/video-intake.md)

也可以直接告诉 Agent：

> 对这个视频或目录运行 `video-intake <路径>`，检查生成的证据，准备准确的内容描述与整理建议。除非我明确批准具体路径，否则不要执行文件改名或移动。

## 可复现演示

仓库演示素材来自采用 CC BY 3.0 许可的 Blender 开放电影《Big Buck Bunny》，不包含私人测试视频。

```bash
video-intake demo/media
```

预期结果：

- `bunny-meets-rodents.mp4` 与重新编码、轻微调色的版本被归为同一组，相似度约为 `0.98`。
- `forest-chase.mp4` 保持独立。
- 再次运行命令时会复用未变化视频的指纹，无需逐条重新解码。
- 时间线帧可由 Agent 填写描述，再渲染成 Markdown。

详见[演示说明](../demo/README.md)和[素材署名](../demo/ATTRIBUTION.md)。

## 命令

| 命令 | 用途 | 是否修改源视频 |
| --- | --- | --- |
| `video-intake <路径>` | 准备完整证据包 | 否 |
| `video-intake doctor` | 检查 Python、FFmpeg 和 FFprobe | 否 |
| `video-intake inspect <视频>` | 生成元数据和联系表 | 否 |
| `video-intake timeline <视频>` | 提取带时间戳的分镜帧 | 否 |
| `video-intake render-timeline <JSON>` | 将 Agent 描述渲染为 Markdown | 否 |
| `video-intake similar <目录>` | 查找完全重复文件并聚类视觉相似视频 | 否 |
| `video-intake propose <视频>` | 生成改名提案 | 否 |
| `video-intake plan <requests.json>` | 生成批量改名计划 | 否 |
| `video-intake archive-plan <报告>` | 生成相似视频归档计划 | 否 |
| `apply`、`apply-plan`、`apply-archive-plan` | 执行已审核计划 | 是，必须传入 `--yes` |

使用 `video-intake <命令> --help` 查看完整参数。

## 安全与隐私

- 所有媒体检查都通过本地 FFmpeg/FFprobe 完成。
- 项目本身不会调用 AI API；语义理解来自当前 Codex 或 Claude Code 会话。
- 提案不等于授权，修改文件必须经过单独确认。
- 已存在的目标文件永远不会被覆盖。
- 归档计划包含完整性摘要，批量操作失败时会尝试回滚。
- 文件大小、修改时间或采样数变化时，缓存会自动失效并重新计算。
- 相似度属于启发式结果，执行归档前必须审核。

更多信息见[隐私模型](privacy.md)和[架构说明](architecture.md)。

## 当前限制

- 暂未提供语音转录。
- 暂无后台目录监听。
- 带时间戳的问题/补录记录仍在规划中。

详见[路线图](roadmap.md)。

## 参与贡献

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python -m build
```

请阅读[中文贡献指南](CONTRIBUTING.zh-CN.md)或 [Contributing](../CONTRIBUTING.md)。安全问题请按照 [SECURITY.md](../SECURITY.md) 私下报告。

## 许可证

Python 代码采用 [MIT](../LICENSE) 许可证，© 2026 Freakz2z。

演示素材采用 [CC BY 3.0](../demo/ATTRIBUTION.md)，派生自 Blender Foundation / Blender Institute 的《Big Buck Bunny》。
