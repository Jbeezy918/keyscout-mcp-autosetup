# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [0.1.0] - unreleased (date set on release)

### Security
- **Inject proxy destination pinning (fixes credential exfiltration).** Earlier development builds joined the request path onto the upstream with `urljoin`, so a request target like `http://other-host/...` made the proxy send the injected API key to another host. Every request is now resolved and must match the upstream's scheme, host and port exactly. Full URLs, `//host` and `///host` forms, backslashes, `@`, control characters and non-`/` paths are rejected with `400` before any key is attached. Upstream redirects are no longer followed.
- **Proxy caller authentication.** Each proxy session gets a random token. Callers must send it as `X-KeyScout-Proxy-Token` (checked in constant time and stripped before forwarding). Otherwise they get `401`.
- Proxy binds to loopback only unless `allow_remote=True`. Proxy info files are written `0600`.

### Breaking
- `ksmcp handoff proxy` clients must now send the `X-KeyScout-Proxy-Token` header, using the `session_token` value from the proxy info.
- **If you used `handoff proxy` from a build before this fix, rotate the API keys you used with it.**

### Added
- **MCP server (stdio)** `keyscout-mcp-autosetup` with tools `list_apis`, `detect_clients`, `find_servers`, `preview_config`, `apply_setup` (dry-run by default; writes only inside a sandbox folder, never the real home dir; backs up existing files).
- Works with MCP Python SDK 1.x and 2.x.
- Packaging (`pyproject.toml`): one-line run with `uvx keyscout-mcp-autosetup`; console scripts `ksmcp`, `keyscout-run`.
- MCPB bundle manifest + `scripts/build_mcpb.sh` (Smithery / Claude Desktop).
- `server.json` for the Official MCP Registry (validated against the 2025-12-11 schema).
- Platform-aware Claude Desktop config path (macOS, Windows, Linux).
- `ksmcp vault-put` prompts for the key when `--key` is omitted, keeping it out of shell history.
- `keyscout-run`: clear errors for bad usage, missing vault entries and missing commands; Windows support.
- CI on Linux, macOS, Windows × Python 3.10/3.12/3.13, SDK 1.x job, package + server.json schema check.
- Registry matching, A–F safety heuristics, encrypted vault, AgentKey handoff, dry-run configs for Claude, Cursor, VS Code, Windsurf.
