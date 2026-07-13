# Security policy

## Supported versions

Security fixes are applied to the latest `main` branch while the project is pre-1.0.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could cause data loss, command injection, or unintended file access. Email `freak050321@gmail.com` with a clear reproduction, impact, and suggested mitigation. You should receive an acknowledgement within seven days.

This tool works on local media and intentionally treats filesystem safety as a security concern.

The MCP server should use local stdio whenever possible. Configure `VIDEO_INTAKE_ALLOWED_ROOTS` for least-privilege filesystem access, and do not expose the unauthenticated development HTTP transport to an untrusted network. MCP write tools require exact path or plan-digest confirmation, but the connected host is still responsible for obtaining genuine user approval.
