# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [0.1.0] - unreleased (date set on release)

### Added
- **MCP server (stdio)** `keyscout-mcp-autosetup` with tools `list_apis`, `detect_clients`, `find_servers`, `preview_config`, `apply_setup` (dry-run by default; writes only inside a sandbox folder, never the real home dir; backs up existing files).
- Works with MCP Python SDK 1.x and 2.x.
- Packaging (`pyproject.toml`): one-line run with `uvx keyscout-mcp-autosetup`; console scripts `ksmcp`, `keyscout-run`.
- `server.json` for the Official MCP Registry (validated against the 2025-12-11 schema).
- Platform-aware Claude Desktop config path (macOS, Windows, Linux).
- `ksmcp vault-put` prompts for the key when `--key` is omitted, keeping it out of shell history.
- `keyscout-run`: clear errors for bad usage, missing vault entries and missing commands; Windows support.
- CI on Linux, macOS, Windows × Python 3.10/3.12/3.13, SDK 1.x job, package + server.json schema check.
- Registry matching, A–F safety heuristics, encrypted vault, AgentKey handoff, dry-run configs for Claude, Cursor, VS Code, Windsurf.
