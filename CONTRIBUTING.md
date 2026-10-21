# Contributing

Thanks for helping. This is a **sandbox-first** tool — never write configs into a real `$HOME` without an explicit non-sandbox mode (not shipped yet).

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export KEYSCOUT_VAULT_PASS='dev-only'
pytest -q
ruff check ksmcp tests
```

## Good first issues
1. Add a catalog entry for another API (env patterns + aliases + official namespace).
2. Improve `safety_score` with registry `publishedAt` age buckets.
3. Windows path support in `clients.CLIENTS`.
4. Document a real Claude Desktop + proxy-handoff walkthrough GIF.
5. Optional `age` encryption backend alongside Fernet.

## Rules
- No plaintext keys in configs, logs, or git.
- Tests must use FAKE keys only.
- Keep `--sandbox` refusing real home.
