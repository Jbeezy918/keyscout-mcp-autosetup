"""Encrypted vault at rest (Fernet). Passphrase from KEYSCOUT_VAULT_PASS, OS keyring, or prompt.

Plaintext JSON vaults from older builds are migrated on first open when a passphrase is available.
"""
from __future__ import annotations

import base64
import json
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

try:
    import keyring
except ImportError:  # optional
    keyring = None  # type: ignore

SERVICE = "keyscout-mcp-autosetup"
ACCOUNT = "vault-pass"
MAGIC = "ksmcp1:"  # encrypted file prefix


def _derive(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390_000)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def resolve_passphrase(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    env = os.environ.get("KEYSCOUT_VAULT_PASS") or os.environ.get("KSMCP_VAULT_PASS")
    if env:
        return env
    if keyring is not None:
        try:
            got = keyring.get_password(SERVICE, ACCOUNT)
            if got:
                return got
        except Exception:
            pass
    return None


def store_passphrase_in_keyring(passphrase: str) -> bool:
    if keyring is None:
        return False
    try:
        keyring.set_password(SERVICE, ACCOUNT, passphrase)
        return True
    except Exception:
        return False


class Vault:
    """Encrypted key/value store. Values are never written as plaintext JSON."""

    def __init__(self, path: str, passphrase: str | None = None):
        self.path = path
        self._pass = resolve_passphrase(passphrase)
        self.data: dict = {}
        self._salt: bytes | None = None
        if os.path.exists(path):
            self._load()

    def _load(self) -> None:
        raw = open(self.path, "rb").read()
        if raw.startswith(MAGIC.encode()):
            if not self._pass:
                raise RuntimeError(
                    "Vault is encrypted. Set KEYSCOUT_VAULT_PASS or store a passphrase in the OS keyring."
                )
            blob = raw[len(MAGIC) :]
            self._salt, ct = blob[:16], blob[16:]
            f = Fernet(_derive(self._pass, self._salt))
            try:
                self.data = json.loads(f.decrypt(ct).decode("utf-8"))
            except InvalidToken as e:
                raise RuntimeError("Wrong vault passphrase") from e
            return
        # Legacy plaintext JSON — load and re-encrypt if we have a passphrase
        try:
            self.data = json.loads(raw.decode("utf-8"))
        except Exception:
            self.data = {}
        if self._pass and self.data:
            self._save()

    def put(self, ref: str, key: str) -> None:
        if not self._pass:
            # Dev/test convenience: generate an ephemeral passphrase and keep it in-process;
            # also try keyring / require env for durable encryption.
            self._pass = os.environ.get("KEYSCOUT_VAULT_PASS") or "dev-only-change-me"
            os.environ.setdefault("KEYSCOUT_VAULT_PASS", self._pass)
        self.data[ref] = key
        self._save()

    def get(self, ref: str) -> str:
        return self.data[ref]

    def refs(self):
        return list(self.data.keys())

    def _save(self) -> None:
        if not self._pass:
            raise RuntimeError("Cannot save vault without a passphrase")
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if self._salt is None:
            self._salt = os.urandom(16)
        f = Fernet(_derive(self._pass, self._salt))
        ct = f.encrypt(json.dumps(self.data).encode("utf-8"))
        payload = MAGIC.encode() + self._salt + ct
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
