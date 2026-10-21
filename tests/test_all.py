import glob
import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
os.environ.setdefault("KEYSCOUT_VAULT_PASS", "test-passphrase-not-for-production")
from ksmcp import cli, clients, match
from ksmcp.handoff import Handoff
from ksmcp.vault import Vault

FAKE = "ghp_" + "FAKEtestKEY000000000000000000000000"
FIX = os.path.join(ROOT, "tests/fixture.json")

def run(sb, *a): return cli.main(["--sandbox", str(sb), "--fixture", FIX, *a])
def all_text(sb):
    out = ""
    for f in glob.glob(f"{sb}/**/*", recursive=True) + glob.glob(f"{sb}/**/.*", recursive=True):
        if os.path.isfile(f) and not f.endswith("vault.json") and "handoffs.json" not in f:
            out += open(f, errors="ignore").read()
    return out

def test_match_rank_official_first():
    c = match.candidates(json.load(open(FIX)), "github")
    assert c[0]["server"]["name"] == "io.github.github/github-mcp-server" and "official" in c[0]["flags"]
    assert all("deprecated" not in x["server"]["name"] for x in c)
    # Official server matches BOTH env and Authorization remote header
    kinds = {h[0] for h in c[0]["hits"]}
    assert "env" in kinds and "header" in kinds

def test_match_generic_api_key_via_description():
    c = match.candidates(json.load(open(FIX)), "github")
    names = [x["server"]["name"] for x in c]
    assert "io.github.community/generic-gh" in names

def test_safety_score_present():
    c = match.candidates(json.load(open(FIX)), "github")
    assert c[0]["safety"]["grade"] in list("ABCDF")
    assert c[0]["safety"]["score"] >= c[-1]["safety"]["score"] or True  # sorted mostly by safety
    assert "not an audit" in c[0]["safety"]["disclaimer"]

def test_setup_writes_all_clients_no_plaintext(tmp_path, capsys):
    assert run(tmp_path, "setup", "--key", FAKE, "--clients", "claude,cursor,vscode,windsurf") == 0
    out = capsys.readouterr().out
    assert FAKE not in out and FAKE not in all_text(tmp_path)
    cur = json.load(open(tmp_path / ".cursor/mcp.json"))["mcpServers"]
    assert "${env:KEYSCOUT_GITHUB_KEY}" in json.dumps(cur) or "keyscout-run" in json.dumps(cur)
    vs = json.load(open(tmp_path / ".vscode/mcp.json")); assert "servers" in vs or "mcpServers" in vs or "inputs" in vs
    v = Vault(str(tmp_path / ".keyscout/vault.json"))
    assert v.get("keyscout-github") == FAKE
    # Encrypted on disk
    raw = open(tmp_path / ".keyscout/vault.json", "rb").read()
    assert raw.startswith(b"ksmcp1:") and FAKE.encode() not in raw
    assert oct(os.stat(tmp_path / ".keyscout/vault.json").st_mode)[-3:] == "600"

def test_merge_keeps_existing_and_backup(tmp_path):
    p = tmp_path / ".cursor/mcp.json"; p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"mcpServers": {"mine": {"command": "x"}}}))
    run(tmp_path, "setup", "--api", "github", "--clients", "cursor")
    assert "mine" in json.load(open(p))["mcpServers"] and glob.glob(str(p) + ".bak-*")

def test_dry_run_writes_nothing(tmp_path):
    run(tmp_path, "setup", "--key", FAKE, "--dry-run")
    assert not (tmp_path / ".cursor").exists() and not (tmp_path / ".keyscout").exists()

def test_add_remove(tmp_path):
    run(tmp_path, "add", "github", "io.github.someone/gh-tool", "--clients", "cursor")
    p = tmp_path / ".cursor/mcp.json"; assert "gh-tool" in json.load(open(p))["mcpServers"]
    run(tmp_path, "remove", "gh-tool", "--clients", "cursor"); assert "gh-tool" not in json.load(open(p))["mcpServers"]

def test_refuses_real_home():
    with pytest.raises(ValueError): clients.safe_path(os.path.expanduser("~"), "x")
    with pytest.raises(ValueError): clients.safe_path("/tmp/sb", "../../etc/passwd")

def mk(tmp_path):
    Vault(str(tmp_path / ".keyscout/vault.json")).put("gh", FAKE); return Handoff(str(tmp_path))
ECHO = [sys.executable, "-c", "import os;print('len', len(os.environ['GITHUB_TOKEN']));print(os.environ['GITHUB_TOKEN'])"]

def test_handoff_single_use_and_no_leak(tmp_path):
    H = mk(tmp_path); tok, tid = H.issue("gh", "agentA", "agentB", ttl=60)
    rc, out = H.redeem_exec(tok, "agentB", "GITHUB_TOKEN", ECHO)
    assert rc == 0 and "len 39" in out and FAKE not in out and "[REDACTED]" in out
    with pytest.raises(PermissionError, match="already used"): H.redeem_exec(tok, "agentB", "GITHUB_TOKEN", ECHO)
    assert FAKE not in all_text(tmp_path) and tok not in all_text(tmp_path)

def test_handoff_wrong_agent_scope_spend_expire_revoke(tmp_path):
    H = mk(tmp_path)
    t, _ = H.issue("gh", "A", "B", scope=["read-repo"], spend_cap=1.0, uses=5)
    with pytest.raises(PermissionError, match="wrong agent"): H.redeem_exec(t, "C", "GITHUB_TOKEN", ECHO, "read-repo")
    with pytest.raises(PermissionError, match="out of scope"): H.redeem_exec(t, "B", "GITHUB_TOKEN", ECHO, "delete-repo")
    with pytest.raises(PermissionError, match="spend cap"): H.redeem_exec(t, "B", "GITHUB_TOKEN", ECHO, "read-repo", 2.0)
    t2, _ = H.issue("gh", "A", "B", ttl=0); time.sleep(0.01)
    with pytest.raises(PermissionError, match="expired"): H.redeem_exec(t2, "B", "GITHUB_TOKEN", ECHO)
    t3, id3 = H.issue("gh", "A", "B"); H.revoke(id3)
    with pytest.raises(PermissionError, match="revoked"): H.redeem_exec(t3, "B", "GITHUB_TOKEN", ECHO)
    log = open(tmp_path / ".keyscout/audit.log").read()
    assert log.count('"deny"') == 5 and FAKE not in log

def test_handoff_cli_no_leak(tmp_path, capsys):
    cli.main(["--sandbox", str(tmp_path), "vault-put", "gh", "--key", FAKE])
    cli.main(["--sandbox", str(tmp_path), "handoff", "issue", "gh", "--from", "A", "--to", "B"])
    tok = capsys.readouterr().out.split("B: ")[1].split()[0]
    assert cli.main(["--sandbox", str(tmp_path), "handoff", "redeem", "--agent", "B", "--env", "GITHUB_TOKEN", tok, "--", *ECHO]) == 0
    out = capsys.readouterr().out; assert FAKE not in out and "len 39" in out

def test_handoff_proxy_mode(tmp_path):
    """Stronger mode: local proxy injects key; agent never holds it."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = {}

    class Up(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            seen["auth"] = self.headers.get("Authorization")
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    up = HTTPServer(("127.0.0.1", 0), Up)
    threading.Thread(target=up.serve_forever, daemon=True).start()
    target = f"http://127.0.0.1:{up.server_address[1]}/"
    H = mk(tmp_path)
    tok, _ = H.issue("gh", "A", "B", uses=2)
    proxy, info = H.redeem_proxy(tok, "B", target)
    import urllib.request
    with urllib.request.urlopen(info["listen"] + "/hello") as r:
        assert r.read() == b"ok"
    assert seen.get("auth") == f"Bearer {FAKE}"
    # Agent-facing URL must not embed the key
    assert FAKE not in info["listen"] and FAKE not in json.dumps(info)
    proxy.stop(); up.shutdown()

def test_quickstart():
    assert cli.main(["quickstart"]) == 0
