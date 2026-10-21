#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export KEYSCOUT_VAULT_PASS="${KEYSCOUT_VAULT_PASS:-demo-passphrase-change-me}"
SB="${TMPDIR:-/tmp}/ksmcp-demo-$$"
mkdir -p "$SB"
cd "$ROOT"
python -m ksmcp.cli quickstart
python -m ksmcp.cli --sandbox "$SB" --fixture tests/fixture.json find github
python -m ksmcp.cli --sandbox "$SB" --fixture tests/fixture.json setup --api github --dry-run --clients cursor
echo "Sandbox was $SB (dry-run only; safe to rm -rf)"
