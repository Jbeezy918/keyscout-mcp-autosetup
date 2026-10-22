# KeyScout MCP Auto-Setup

<!-- mcp-name: io.github.Jbeezy918/keyscout-mcp-autosetup -->

**Pick an API key, get the matching MCP servers and ready-to-paste Claude / Cursor / VS Code / Windsurf configs, with no plaintext key in any config file.**

[![CI](https://github.com/Jbeezy918/keyscout-mcp-autosetup/actions/workflows/ci.yml/badge.svg)](https://github.com/Jbeezy918/keyscout-mcp-autosetup/actions/workflows/ci.yml) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) [![Stars](https://img.shields.io/github/stars/Jbeezy918/keyscout-mcp-autosetup?style=social)](https://github.com/Jbeezy918/keyscout-mcp-autosetup)

![MCP Auto-Setup demo: an MCP client calling find_servers and preview_config](docs/demo.gif)

## Use it as an MCP server (one line)

Add to Claude Desktop, Cursor, Windsurf or any MCP client:

```json
{ "mcpServers": { "keyscout-autosetup": { "command": "uvx", "args": ["keyscout-mcp-autosetup"] } } }
```

Until the PyPI release, use `"args": ["--from", "git+https://github.com/Jbeezy918/keyscout-mcp-autosetup", "keyscout-mcp-autosetup"]`. Requires [uv](https://docs.astral.sh/uv/).

| Tool | What it does | Writes files? |
|---|---|---|
| `list_apis` | APIs it can match, with where to get each key | No |
| `detect_clients` | Which of Claude / Cursor / VS Code / Windsurf have a config, and server names in it | No (read-only) |
| `find_servers` | Registry servers that accept your key type, A–F scored | No |
| `preview_config` | Exact config each client would get | No |
| `apply_setup` | Writes those configs into a sandbox folder | Only with `dry_run=false`; backs up first; refuses your real home dir |

No tool ever takes or returns a raw key. Then ask your assistant: *"Which GitHub MCP servers are safest, and show me the Cursor config."*

## Use it as a CLI (one line)

```bash
uvx --from git+https://github.com/Jbeezy918/keyscout-mcp-autosetup ksmcp quickstart
```

## Quick start (CLI)

```bash
SB=$(mktemp -d)
ksmcp --sandbox "$SB" find github
ksmcp --sandbox "$SB" setup --api github --dry-run --clients cursor
ksmcp --sandbox "$SB" vault-put keyscout-github      # prompts; key stays out of shell history
```

Configs launch servers through `keyscout-run`, which pulls the key from the encrypted vault into the child process env only (set `KEYSCOUT_VAULT` to the vault path printed by the tool).

## Agent handoff proxy (breaking change in 0.1.0)
`ksmcp handoff proxy` now prints a `session_token` and requires every request to send it:

```bash
curl -H "X-KeyScout-Proxy-Token: <session_token>" http://127.0.0.1:<port>/user
```

Requests without the token get `401`. Paths must be plain paths (`/repos/...`). Full URLs, `//host` forms and anything that would change the destination host get `400`, and the key is never sent. The proxy only binds to localhost. See [SECURITY.md](SECURITY.md).

## Recovery and troubleshooting
- **Where things live:** the vault is `<sandbox>/.keyscout/vault.json` for the CLI (or `~/.keyscout/vault.json` / `KEYSCOUT_VAULT` for `keyscout-run`). The registry cache is in `~/.keyscout` (override with `KSMCP_CACHE`).
- **Undo a config write:** `apply_setup` / `ksmcp setup` back up every file before changing it as `<file>.bak-<timestamp>-<n>`. To roll back, copy the newest `.bak-` file over the config and restart your client.
- **Back up the vault:** copy `vault.json` while nothing is writing to it. It's encrypted, so you'll need the same passphrase to restore it.
- **Forgot the vault passphrase:** the vault can't be decrypted without it. Move the old `vault.json` aside, run `ksmcp vault-put` again for each key, and rotate any key you can't account for.
- **`keyscout-run` says the entry is missing:** check that `KEYSCOUT_VAULT` points to the vault the tool printed and that the entry name matches.
- **Proxy returns 401 or 400:** send the `X-KeyScout-Proxy-Token` header, and use a plain path, not a full URL.
- **`find_servers` fails offline:** it needs the Official MCP Registry. The cache only helps within 24 hours of the last successful fetch.

## Platforms
macOS, Linux, Windows; Python 3.10+. CI runs all three. Claude Desktop config path is chosen per OS.

## Limits, honestly
- Writes go to a sandbox folder you choose; it will not edit configs in your real home dir. Copy the previewed config into your client yourself, or point `apply_setup` at a project folder.
- Safety grades are heuristics, not an audit.
- `find_servers` needs network access to the Official MCP Registry (cached 24h).

## Why
Hand-editing `mcp.json` usually means pasting a raw token into a file that gets synced, backed up and committed. This tool matches your key to servers in the official MCP registry, scores them (A-F, automated heuristics, not an audit), and writes configs that reference the vault instead.

## Features
- **Encrypted vault** (Fernet + PBKDF2); passphrase via `KEYSCOUT_VAULT_PASS` or OS keyring.
- **Matching** on specific env names, generic `API_KEY`/`TOKEN` + description, and remote headers.
- **Safety score** A-F: official namespace, public source, local vs relay, license, activity.
- **AgentKey handoff**: inject into a child env only, or a local inject proxy so Agent B never holds the key.
- Dry-run setup for Claude, Cursor, VS Code, Windsurf.

**Want the full key manager?** [KeyScout](https://getkeyscout.com) (Mac & Windows, free to start) searches nearly 5,000 APIs, links to each key page, keeps your keys in an encrypted vault on your own computer, and scans projects for keys you already leaked. This free tool is the open-source piece of it.

## Security
See [SECURITY.md](SECURITY.md) for the full safety model.

## Changelog
See [CHANGELOG.md](CHANGELOG.md).

## Development
```bash
pip install -r requirements.txt && KEYSCOUT_VAULT_PASS=dev pytest -q && ruff check ksmcp tests
```


Never commit real keys; tests use `ghp_FAKE…` only.

## License
[Apache-2.0](LICENSE)
