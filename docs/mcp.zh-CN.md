# MCP 接入说明

Video Intake Agent 已包含基于官方 Python SDK 实现的本地 MCP Server，可将现有确定性视频处理能力接入 Codex、Claude Code、Cursor 等 MCP Host。服务本身不调用云端模型，也不会上传视频。

## 安装与自检

需要 Python 3.11+、FFmpeg 和 `ffprobe`。

```bash
python -m pip install -e '.[mcp]'
video-intake-mcp-client
```

验证客户端会通过 stdio 启动 MCP Server，完成协议握手，列出 Tools、Resource 和 Prompt，并实际调用 `doctor`。

项目将依赖约束为稳定版 `mcp>=1.27,<2`；MCP Python SDK v2 目前仍是包含破坏性变更的预发布版本。

## 连接 MCP Host

命令中请使用虚拟环境内可执行文件的绝对路径。

### Codex

```bash
codex mcp add video-intake \
  --env VIDEO_INTAKE_ALLOWED_ROOTS=/视频目录的绝对路径 \
  -- /项目绝对路径/.venv/bin/video-intake-mcp
```

### Claude Code

```bash
claude mcp add video-intake \
  -e VIDEO_INTAKE_ALLOWED_ROOTS=/视频目录的绝对路径 \
  -- /项目绝对路径/.venv/bin/video-intake-mcp
```

`VIDEO_INTAKE_ALLOWED_ROOTS` 为可选但推荐的文件系统作用域。多个目录使用系统路径分隔符连接：macOS/Linux 使用 `:`，Windows 使用 `;`。Server 会检查所有输入、输出、计划及目标路径是否位于允许目录内。

## MCP 能力

Server 提供结构化输出，覆盖：

- Python、FFmpeg、FFprobe 与目录作用域检查；
- 一条命令生成视频/目录证据包；
- 元数据、联系表与时间戳分镜帧；
- 完全重复检测和视觉相似度分析；
- 单文件及批量改名提案；
- 带完整性校验的归档计划与 Markdown 时间线；
- 经过精确确认的改名、批量改名与归档执行。

此外还提供：

- `video-intake://workflow` Resource：描述统一安全约束；
- `review_video_workflow` Prompt：复用证据审核和用户确认流程。

## 写操作安全约束

MCP Tool Annotation 会区分证据写入与破坏性文件操作；真正的安全限制同时在 Server 内部强制执行。

- 证据与计划工具不会修改源视频。
- 单文件改名必须提交 `propose_rename` 返回的精确 `proposed_path`。
- 保存计划后会返回 `confirmation_sha256`，批量执行工具必须提交完全一致的摘要。
- 已存在的目标文件不会被覆盖。
- 批量操作继续执行原有的计划校验与失败回滚。
- MCP Host 必须先展示全部源/目标路径并获得用户明确批准，再调用 apply 工具。

因此，即使 Host 忽略 Tool Annotation，Server 仍会独立检查目录、路径、摘要和文件冲突。

## 传输方式

默认使用本地 stdio，也是推荐方式：

```bash
video-intake-mcp
```

本地开发时也可启动 Streamable HTTP：

```bash
video-intake-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

HTTP 模式目前不包含身份认证，并默认只监听本机回环地址。不要直接暴露到不可信网络；远程生产部署需要额外设计认证、授权、TLS 与部署边界。

## 开发验证

```bash
.venv/bin/python -m pytest -q tests/test_mcp_server.py
.venv/bin/video-intake-mcp-client
```

测试会通过官方 SDK 的内存 Client/Server 会话执行真实 MCP 调用，并验证目录作用域、精确路径确认和 SHA-256 计划确认。
