import os
import tempfile

from ksmcp import run
from ksmcp.vault import Vault


def test_usage_errors():
    assert run.main([]) == 2
    assert run.main(["ref", "--env", "X"]) == 2
    assert run.main(["ref", "--env", "--", "echo"]) == 2


def test_missing_ref_is_clear(capsys, monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("KEYSCOUT_VAULT_PASS", "t")
        p = os.path.join(d, "vault.json")
        Vault(p).put("other", "ghp_FAKE000")
        monkeypatch.setenv("KEYSCOUT_VAULT", p)
        assert run.main(["missing", "--env", "X", "--", "echo", "hi"]) == 3
        err = capsys.readouterr().err
        assert "vault-put missing" in err and "ghp_FAKE" not in err
