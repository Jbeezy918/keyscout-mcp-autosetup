#!/usr/bin/env bash
# Build dist/keyscout-mcp-autosetup.mcpb (for Smithery / Claude Desktop). Needs Node (npx).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
cp "$ROOT/mcpb/manifest.json" "$ROOT/LICENSE" "$ROOT/README.md" "$ROOT/pyproject.toml" "$STAGE/"
cp -R "$ROOT/ksmcp" "$STAGE/ksmcp"
mkdir -p "$ROOT/dist"
npx -y @anthropic-ai/mcpb pack "$STAGE" "$ROOT/dist/keyscout-mcp-autosetup.mcpb"
echo "built $ROOT/dist/keyscout-mcp-autosetup.mcpb (staging left in $STAGE)"
