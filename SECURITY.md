# Security Policy — KeyScout MCP Auto-Setup

## Guarantees we aim for
- Raw API keys are **not** written into editor config files when using the vault/launcher path.
- Dry-run mode writes only into a test folder with fake keys.
- Community MCP servers should never be auto-installed without an explicit confirm.

## Never commit
- `.env`, real API keys, KeyScout vault exports, Stripe live secrets, OAuth tokens.

## Reporting issues
Contact the maintainers (see README) once the public repo exists. Redact secrets in any report.

## MCP server safety model
- No tool accepts, returns or logs a raw API key. Keys go into the vault only via `ksmcp vault-put`, which prompts locally, so the key never passes through the AI model.
- `detect_clients` is read-only and reports file paths and server *names* only, never config values.
- `preview_config` and `find_servers` never write files. `find_servers` makes read-only requests to registry.modelcontextprotocol.io (cached 24h).
- `apply_setup` defaults to `dry_run=True`; with `dry_run=False` it writes only inside the given sandbox folder (the real home dir, or any folder containing it, is refused) and backs up any file it changes.
- Safety grades are automated heuristics, **not** a security audit.
- Reporting: open a private GitHub Security Advisory on this repo (Security tab → Report a vulnerability). Do not file public issues for vulnerabilities.
