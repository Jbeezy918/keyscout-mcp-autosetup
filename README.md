# KeyScout MCP Auto-Setup

**Pick an API key, get the matching MCP servers and ready-to-paste Claude / Cursor / VS Code / Windsurf configs, with no plaintext key in any config file.**

[![CI](https://github.com/Jbeezy918/keyscout-mcp-autosetup/actions/workflows/ci.yml/badge.svg)](https://github.com/Jbeezy918/keyscout-mcp-autosetup/actions/workflows/ci.yml) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) [![Stars](https://img.shields.io/github/stars/Jbeezy918/keyscout-mcp-autosetup?style=social)](https://github.com/Jbeezy918/keyscout-mcp-autosetup)

![MCP Auto-Setup demo](docs/demo.gif)

## Install (one line)

```bash
git clone https://github.com/Jbeezy918/keyscout-mcp-autosetup && cd keyscout-mcp-autosetup && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m ksmcp.cli quickstart
```

## Quick start

```bash
export KEYSCOUT_VAULT_PASS='long-random-passphrase'
python -m ksmcp.cli --sandbox /tmp/ks-demo --fixture tests/fixture.json find github
python -m ksmcp.cli --sandbox /tmp/ks-demo --fixture tests/fixture.json setup --api github --dry-run --clients cursor
```

Configs launch servers through `keyscout-run`, which pulls the key from the encrypted vault into the child process env only.

## Why
Hand-editing `mcp.json` usually means pasting a raw token into a file that gets synced, backed up and committed. This tool matches your key to servers in the official MCP registry, scores them (A-F, automated heuristics, not an audit), and writes configs that reference the vault instead.

## Features
- **Encrypted vault** (Fernet + PBKDF2); passphrase via `KEYSCOUT_VAULT_PASS` or OS keyring.
- **Matching** on specific env names, generic `API_KEY`/`TOKEN` + description, and remote headers.
- **Safety score** A-F: official namespace, public source, local vs relay, license, activity.
- **AgentKey handoff**: inject into a child env only, or a local inject proxy so Agent B never holds the key.
- Dry-run setup for Claude, Cursor, VS Code, Windsurf.

**Want the full key manager?** [KeyScout](https://getkeyscout.com) finds every key on your machine, tracks where each one lives, and keeps them in one vault. This free tool is the open-source piece of it.

## Security
See [SECURITY.md](SECURITY.md). Never commit real keys; tests use `ghp_FAKE…` only.

## License
[Apache-2.0](LICENSE)
