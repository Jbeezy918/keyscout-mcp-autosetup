"""KeyScout MCP auto-setup CLI."""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap

from . import clients, match, registry
from .catalog import CATALOG, identify_key
from .vault import Vault, store_passphrase_in_keyring

EPILOG = """
examples:
  # Dry-run: see which GitHub MCP servers match (no writes)
  ksmcp --sandbox /tmp/ks-demo --fixture tests/fixture.json find github

  # Set up recommended servers for a FAKE test key
  export KEYSCOUT_VAULT_PASS='choose-a-long-passphrase'
  ksmcp --sandbox /tmp/ks-demo --fixture tests/fixture.json setup --key ghp_FAKE... --clients cursor

  # Agent handoff (legacy): B runs a command with key injected into env only
  ksmcp --sandbox /tmp/ks-demo handoff issue gh --from A --to B
  ksmcp --sandbox /tmp/ks-demo handoff redeem --agent B --env GITHUB_TOKEN TOKEN -- python -c '...'

  # Agent handoff (proxy): B only sees http://127.0.0.1:PORT — key never leaves the vault/proxy
  ksmcp --sandbox /tmp/ks-demo handoff proxy --agent B --target https://api.github.com/ TOKEN
"""


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="ksmcp",
        description="KeyScout MCP auto-setup — match keys to MCP servers, vault-safe configs, AgentKey handoff",
        epilog=textwrap.dedent(EPILOG),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--sandbox", required=False, help="Fake home dir for configs (real $HOME is refused)")
    ap.add_argument("--fixture", help="Registry JSON instead of live API (tests/offline)")
    ap.add_argument("--vault-pass", help="Vault passphrase (or set KEYSCOUT_VAULT_PASS)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("find", help="List matching MCP servers for an API, with safety scores")
    f.add_argument("api", help="API id, e.g. github, openai, stripe")

    s = sub.add_parser("setup", help="Store key in encrypted vault + write recommended client configs")
    s.add_argument("--api", help="API id (optional if --key prefix is known)")
    s.add_argument("--key", help="FAKE/test key only in sandbox demos")
    s.add_argument("--clients", default="claude,cursor,vscode")
    s.add_argument("--top", type=int, default=3)
    s.add_argument("--dry-run", action="store_true")

    a = sub.add_parser("add", help="Add one named server to clients")
    a.add_argument("api")
    a.add_argument("server")
    a.add_argument("--clients", default="claude,cursor,vscode")
    a.add_argument("--dry-run", action="store_true")

    r = sub.add_parser("remove", help="Remove a server id from clients")
    r.add_argument("server_id")
    r.add_argument("--clients", default="claude,cursor,vscode")
    r.add_argument("--dry-run", action="store_true")

    h = sub.add_parser("handoff", help="AgentKey stand-in tokens (env inject or local proxy)")
    hs = h.add_subparsers(dest="hcmd", required=True)
    hi = hs.add_parser("issue", help="Issue a short-lived stand-in token")
    hi.add_argument("ref")
    hi.add_argument("--from", dest="frm", required=True)
    hi.add_argument("--to", required=True)
    hi.add_argument("--ttl", type=int, default=300)
    hi.add_argument("--uses", type=int, default=1)
    hi.add_argument("--scope", default="")
    hi.add_argument("--spend-cap", type=float)

    hr = hs.add_parser("redeem", help="Legacy: run a command with key in child env only")
    hr.add_argument("token")
    hr.add_argument("--agent", required=True)
    hr.add_argument("--env", required=True)
    hr.add_argument("--purpose")
    hr.add_argument("--cost", type=float, default=0)
    hr.add_argument("run", nargs=argparse.REMAINDER)

    hp = hs.add_parser("proxy", help="Stronger: start local inject proxy (B never holds the key)")
    hp.add_argument("token")
    hp.add_argument("--agent", required=True)
    hp.add_argument("--target", required=True, help="Upstream base URL")
    hp.add_argument("--header", default="Authorization")
    hp.add_argument("--header-template", default="Bearer {key}")
    hp.add_argument("--purpose")
    hp.add_argument("--cost", type=float, default=0)
    hp.add_argument("--port", type=int, default=0)
    hp.add_argument("--block", action="store_true", help="Keep process alive until Ctrl-C")

    hv = hs.add_parser("revoke")
    hv.add_argument("token_id")
    hs.add_parser("list")

    vp = sub.add_parser("vault-put", help="Store a key in the encrypted vault")
    vp.add_argument("ref")
    vp.add_argument("--key", required=True)
    vp.add_argument("--save-keyring", action="store_true", help="Remember passphrase in OS keyring")

    sub.add_parser("quickstart", help="Print a 60-second getting-started guide")
    return ap


def _vault(root, pass_=None):
    if pass_:
        os.environ["KEYSCOUT_VAULT_PASS"] = pass_
    return Vault(os.path.join(root, ".keyscout/vault.json"), passphrase=pass_)


def main(argv=None):
    ap = build_parser()
    o = ap.parse_args(argv)
    if o.cmd == "quickstart":
        print(
            textwrap.dedent(
                """
                KeyScout MCP auto-setup — quickstart
                ===================================
                1) Pick a sandbox folder (never your real home):
                     export SB=/tmp/ks-demo && mkdir -p "$SB"
                2) Set a vault passphrase:
                     export KEYSCOUT_VAULT_PASS='long-random-passphrase'
                3) Find servers for an API:
                     python -m ksmcp.cli --sandbox "$SB" --fixture tests/fixture.json find github
                4) Dry-run setup:
                     python -m ksmcp.cli --sandbox "$SB" --fixture tests/fixture.json setup --api github --dry-run
                5) Real sandbox write with a FAKE key:
                     python -m ksmcp.cli --sandbox "$SB" --fixture tests/fixture.json \\
                       setup --key ghp_FAKE... --clients cursor
                Safety scores (A–F) are automated heuristics, not audits.
                Handoff proxy mode keeps raw keys out of Agent B entirely.
                """
            ).strip()
        )
        return 0

    root = os.path.abspath(o.sandbox)
    clients.safe_path(root, "x")
    if getattr(o, "vault_pass", None):
        os.environ["KEYSCOUT_VAULT_PASS"] = o.vault_pass
        if getattr(o, "save_keyring", False):
            store_passphrase_in_keyring(o.vault_pass)

    def entries_for(api):
        if o.fixture:
            return json.load(open(o.fixture))
        return registry.fetch(api, os.path.join(root, ".ksmcp-cache"))

    if o.cmd == "vault-put":
        _vault(root, getattr(o, "vault_pass", None)).put(o.ref, o.key)
        print(f"stored {o.ref} (encrypted at rest)")
        return 0

    if o.cmd == "handoff":
        from .handoff import Handoff

        H = Handoff(root)
        if o.hcmd == "issue":
            tok, tid = H.issue(o.ref, o.frm, o.to, o.ttl, o.uses, [x for x in o.scope.split(",") if x], o.spend_cap)
            print(f"stand-in token for {o.to}: {tok}  (id {tid}, ttl {o.ttl}s, uses {o.uses})")
            return 0
        if o.hcmd == "redeem":
            cmd = o.run[1:] if o.run[:1] == ["--"] else o.run
            try:
                rc, out = H.redeem_exec(o.token, o.agent, o.env, cmd, o.purpose, o.cost)
            except PermissionError as e:
                print(f"DENIED: {e}")
                return 3
            print(out, end="")
            return rc
        if o.hcmd == "proxy":
            try:
                proxy, info = H.redeem_proxy(
                    o.token,
                    o.agent,
                    o.target,
                    header_name=o.header,
                    header_template=o.header_template,
                    purpose=o.purpose,
                    cost=o.cost,
                    port=o.port,
                )
            except PermissionError as e:
                print(f"DENIED: {e}")
                return 3
            print(json.dumps(info, indent=2))
            if o.block:
                import time

                print("proxy running — Ctrl-C to stop", file=sys.stderr)
                try:
                    while True:
                        time.sleep(3600)
                except KeyboardInterrupt:
                    proxy.stop()
            return 0
        if o.hcmd == "revoke":
            print("revoked" if H.revoke(o.token_id) else "not found")
            return 0
        for r in H.list():
            print(r)
        return 0

    if o.cmd == "find":
        for c in match.candidates(entries_for(o.api), o.api):
            s = c["safety"]
            print(
                f"{s['grade']} {s['score']:>3}  {c['server']['name']}  "
                f"[{', '.join(c['flags'])}]  key via {c['hits'][0][0]}:{c['hits'][0][1]}  ({s['disclaimer']})"
            )
        return 0

    if o.cmd == "remove":
        for cl in o.clients.split(","):
            res = clients.apply(root, cl, remove=[o.server_id], dry_run=o.dry_run)
            print(
                f"{cl}: {'would change' if res['dry_run'] and res['changed'] else 'changed' if res['changed'] else 'no change'} {res['path']}"
            )
        return 0

    api = o.api or (identify_key(o.key) if getattr(o, "key", None) else None)
    if api not in CATALOG:
        print(f"unknown API (known: {', '.join(CATALOG)})")
        return 2
    cands = match.candidates(entries_for(api), api)
    picks = [c for c in cands if c["server"]["name"] == o.server] if o.cmd == "add" else match.bundle(cands, o.top)
    if not picks:
        print("no matching servers")
        return 1
    ref = f"keyscout-{api}"
    if o.cmd == "setup" and o.key and not o.dry_run:
        _vault(root).put(ref, o.key)
        print(f"stored key in encrypted vault as {ref} (not written to any config)")
    print(f"API: {CATALOG[api]['label']}  get key: {CATALOG[api]['get_key']}  free tier: {CATALOG[api]['free_tier']}")
    for c in picks:
        s = c["safety"]
        print(f"  + {c['server']['name']}  safety {s['grade']} ({s['score']}/100) [{', '.join(c['flags'])}]")
    for cl in o.clients.split(","):
        res = clients.apply(root, cl, add=picks, ref=ref, api=api, dry_run=o.dry_run)
        tag = "DRY-RUN" if o.dry_run else ("written" if res["changed"] else "unchanged")
        print(f"{cl}: {tag} {res['path']}" + (f" (backup {os.path.basename(res['backup'])})" if res.get("backup") else ""))
        if o.dry_run:
            print(json.dumps(res["config"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
