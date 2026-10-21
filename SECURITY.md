# Security Policy — KeyScout MCP Auto-Setup

## Guarantees we aim for
- Raw API keys are **not** written into editor config files when using the vault/launcher path.
- Dry-run mode writes only into a test folder with fake keys.
- Community MCP servers should never be auto-installed without an explicit confirm.

## Never commit
- `.env`, real API keys, KeyScout vault exports, Stripe live secrets, OAuth tokens.

## Reporting issues
Contact the maintainers (see README) once the public repo exists. Redact secrets in any report.
