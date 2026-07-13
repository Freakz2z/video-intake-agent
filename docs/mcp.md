# MCP integration

Video Intake Agent includes a local MCP server built with the official Python SDK. It exposes the existing deterministic video workflow to Codex, Claude Code, Cursor, and other MCP hosts without adding a cloud model or uploading media.

## Install

Python 3.11+, FFmpeg, and `ffprobe` are required.

```bash
python -m pip install -e '.[mcp]'
video-intake-mcp-client
```

The client command launches the server over stdio, completes the MCP handshake, lists its tools/resources/prompts, and calls `doctor`.

The project pins the stable SDK line with `mcp>=1.27,<2`. MCP Python SDK v2 is still a pre-release and contains breaking API changes.

## Connect an MCP host

Use the absolute path to the executable inside your virtual environment.

### Codex

```bash
codex mcp add video-intake \
  --env VIDEO_INTAKE_ALLOWED_ROOTS=/absolute/path/to/videos \
  -- /absolute/path/to/video-intake-agent/.venv/bin/video-intake-mcp
```

### Claude Code

```bash
claude mcp add video-intake \
  -e VIDEO_INTAKE_ALLOWED_ROOTS=/absolute/path/to/videos \
  -- /absolute/path/to/video-intake-agent/.venv/bin/video-intake-mcp
```

`VIDEO_INTAKE_ALLOWED_ROOTS` is optional but recommended. Separate multiple roots with the operating system path separator (`:` on macOS/Linux, `;` on Windows). Every source, output, plan, and destination path is checked against this scope.

## Exposed capabilities

The server exposes structured MCP output for:

- runtime checks and filesystem-scope reporting;
- one-command evidence bundle preparation;
- metadata/contact-sheet inspection and timestamped frame extraction;
- exact-duplicate and visual-similarity analysis;
- single and batch rename proposals;
- integrity-protected archive plans and Markdown timeline rendering;
- explicitly confirmed rename and archive execution.

It also exposes:

- `video-intake://workflow`, a resource describing the safety contract;
- `review_video_workflow`, a reusable prompt for evidence review and approval.

## Write-action contract

MCP tool annotations distinguish evidence writes from destructive filesystem operations.

- Evidence and plan tools never modify source videos.
- A single rename requires the exact `proposed_path` returned by `propose_rename`.
- A saved batch/archive plan returns `confirmation_sha256`; apply tools require that exact digest.
- Existing destinations are never overwritten.
- Batch operations retain the core validation and rollback attempts.
- The MCP host must show the exact paths and obtain user approval before calling an apply tool.

Tool annotations are advisory protocol metadata. The path/digest checks are enforced again inside the server and do not rely on the host following those annotations.

## Transports

stdio is the default and recommended local transport:

```bash
video-intake-mcp
```

For local Streamable HTTP development:

```bash
video-intake-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

This HTTP mode has no authentication and binds to loopback by default. Do not expose it to an untrusted network. Production remote hosting requires a separate authentication, authorization, TLS, and deployment design.

## Development verification

```bash
.venv/bin/python -m pytest -q tests/test_mcp_server.py
.venv/bin/video-intake-mcp-client
```

Tests use the official SDK's connected in-memory client/server session and also exercise filesystem scoping plus exact path/SHA-256 confirmation.
