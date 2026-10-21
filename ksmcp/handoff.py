"""AgentKey handoff: Agent A asks the vault for a scoped, short-lived, single-use stand-in
token for Agent B. B redeems it by asking the vault to run its command with the key injected
into the child process env only. The raw key is never returned, printed, logged or written
outside the vault file. All events are audit-logged (token id + hash only)."""
import hashlib
import json
import os
import secrets
import subprocess
import time

from .vault import Vault


def _h(s): return hashlib.sha256(s.encode()).hexdigest()

class Handoff:
    def __init__(self, root):
        self.dir = os.path.join(root, ".keyscout"); os.makedirs(self.dir, exist_ok=True)
        self.vault = Vault(os.path.join(self.dir, "vault.json"))
        self.tpath = os.path.join(self.dir, "handoffs.json")
        self.lpath = os.path.join(self.dir, "audit.log")
        self.t = json.load(open(self.tpath)) if os.path.exists(self.tpath) else {}

    def _save(self):
        fd = os.open(self.tpath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f: json.dump(self.t, f, indent=1)

    def _log(self, ev, tid, **kw):
        with open(self.lpath, "a") as f:
            f.write(json.dumps({"ts": round(time.time(), 3), "event": ev, "token_id": tid, **kw}) + "\n")

    def issue(self, ref, from_agent, to_agent, ttl=300, uses=1, scope=None, spend_cap=None):
        self.vault.get(ref)  # must exist
        tok = "ksh_" + secrets.token_urlsafe(24); tid = _h(tok)[:12]
        self.t[_h(tok)] = {"id": tid, "ref": ref, "from": from_agent, "to": to_agent, "exp": time.time() + ttl,
                            "uses_left": uses, "scope": scope or [], "spend_cap": spend_cap, "spent": 0, "revoked": False}
        self._save(); self._log("issue", tid, ref=ref, frm=from_agent, to=to_agent, ttl=ttl, uses=uses, scope=scope, spend_cap=spend_cap)
        return tok, tid

    def _check(self, tok, agent, purpose, cost):
        r = self.t.get(_h(tok))
        if not r: return None, "unknown token"
        if r["revoked"]: return r, "revoked"
        if time.time() > r["exp"]: return r, "expired"
        if r["uses_left"] <= 0: return r, "already used"
        if agent != r["to"]: return r, "wrong agent"
        if r["scope"] and purpose not in r["scope"]: return r, "out of scope"
        if r["spend_cap"] is not None and r["spent"] + cost > r["spend_cap"]: return r, "spend cap"
        return r, None

    def redeem_exec(self, tok, agent, env_var, cmd, purpose=None, cost=0.0):
        r, err = self._check(tok, agent, purpose, cost)
        tid = r["id"] if r else _h(tok)[:12]
        if err:
            self._log("deny", tid, agent=agent, reason=err); raise PermissionError(err)
        r["uses_left"] -= 1; r["spent"] += cost; self._save()
        self._log("redeem", tid, agent=agent, purpose=purpose, cost=cost)
        key = self.vault.get(r["ref"])
        p = subprocess.run(cmd, env=dict(os.environ, **{env_var: key}), capture_output=True, text=True)
        out = (p.stdout + p.stderr).replace(key, "[REDACTED]")  # never echo the key back
        return p.returncode, out

    def revoke(self, tid):
        for r in self.t.values():
            if r["id"] == tid: r["revoked"] = True; self._save(); self._log("revoke", tid); return True
        return False

    def list(self):
        now = time.time()
        return [{k: v for k, v in r.items() if k != "ref"} | {"state": "revoked" if r["revoked"] else
                 "expired" if now > r["exp"] else "used" if r["uses_left"] <= 0 else "active"} for r in self.t.values()]

    def redeem_proxy(self, tok, agent, target_base, header_name="Authorization",
                     header_template="Bearer {key}", purpose=None, cost=0.0, port=0):
        """Start a local inject proxy; Agent B never sees the key (stronger mode)."""
        from .proxy import InjectProxy
        r, err = self._check(tok, agent, purpose, cost)
        tid = r["id"] if r else _h(tok)[:12]
        if err:
            self._log("deny", tid, agent=agent, reason=err); raise PermissionError(err)
        r["uses_left"] -= 1; r["spent"] += cost; self._save()
        self._log("redeem_proxy", tid, agent=agent, purpose=purpose, cost=cost, target=target_base)
        proxy = InjectProxy(self.vault, r["ref"], target_base, header_name=header_name,
                            header_template=header_template, port=port)
        url = proxy.start()
        info = proxy.info()
        info["token_id"] = tid
        info["mode"] = "proxy"
        # Keep proxy object alive on instance for tests
        self._live_proxies = getattr(self, "_live_proxies", [])
        self._live_proxies.append(proxy)
        return proxy, info
