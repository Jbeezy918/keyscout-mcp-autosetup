# KeyScout MCP Auto-Setup

Match an API key to MCP servers from the official registry, store the key in an **encrypted vault**, write editor configs **without plaintext secrets**, and hand keys between agents safely.

**Apache-2.0** · Sandbox-first · Safety scores are automated heuristics, not audits.

## Demo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export KEYSCOUT_VAULT_PASS='long-random-passphrase'
./examples/quickstart.sh
# or:
python -m ksmcp.cli --sandbox /tmp/ks-demo --fixture tests/fixture.json find github
```

Example `find` output:

```
A  95  io.github.github/github-mcp-server  [official, has-repo, local-package, remote]  key via env:GITHUB_PERSONAL_ACCESS_TOKEN  (automated check, not an audit)
B  70  io.github.someone/gh-tool  [has-repo, local-package]  key via env:GITHUB_TOKEN  (...)
```

## Features
- **Encrypted vault** (Fernet + PBKDF2). Passphrase via `KEYSCOUT_VAULT_PASS` or OS keyring.
- **Matching** for specific env names, generic `API_KEY`/`TOKEN` + description, and remote headers like `Authorization: Bearer {GITHUB_TOKEN}`.
- **Safety score** (A–F): official namespace, public source, local vs relay, license, activity.
- **AgentKey handoff**
  - *Legacy:* inject key into a child process env only (`handoff redeem`).
  - *Stronger:* local **inject proxy** so Agent B never holds the key (`handoff proxy`).
- Dry-run setup for Claude, Cursor, VS Code, Windsurf.

## Quickstart
```bash
python -m ksmcp.cli quickstart
```

## Security
See [SECURITY.md](SECURITY.md). Never commit real keys. Tests use `ghp_FAKE…` only.

## License
Apache License 2.0 — see [LICENSE](LICENSE).
