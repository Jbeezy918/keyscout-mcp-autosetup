"""keyscout-run <vault-ref> --env VAR -- cmd args...

Reads one key from the encrypted vault and injects it into the child process env only.
"""
import os
import subprocess
import sys

USAGE = "usage: keyscout-run <vault-ref> --env VAR -- command [args...]"


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 5 or "--env" not in a or "--" not in a or a.index("--env") + 1 >= a.index("--"):
        print(USAGE, file=sys.stderr)
        return 2
    ref, var = a[0], a[a.index("--env") + 1]
    cmd = a[a.index("--") + 1:]
    if not cmd:
        print(USAGE, file=sys.stderr)
        return 2
    from .vault import Vault

    vault = os.environ.get("KEYSCOUT_VAULT", os.path.expanduser("~/.keyscout/vault.json"))
    try:
        key = Vault(vault).get(ref)
    except Exception as e:  # noqa: BLE001 - surface a clear message, never the key
        print(f"keyscout-run: could not read '{ref}' from {vault}: {type(e).__name__}. "
              f"Store it with: ksmcp vault-put {ref}", file=sys.stderr)
        return 3
    if not key:
        print(f"keyscout-run: no key stored under '{ref}'. Store it with: ksmcp vault-put {ref}", file=sys.stderr)
        return 3
    env = dict(os.environ, **{var: key})
    cmd = [x.replace("${%s}" % var, key) for x in cmd]
    if sys.platform.startswith("win"):
        try:
            return subprocess.call(cmd, env=env)
        except FileNotFoundError:
            print(f"keyscout-run: command not found: {cmd[0]}", file=sys.stderr)
            return 127
    try:
        os.execvpe(cmd[0], cmd, env)
    except FileNotFoundError:
        print(f"keyscout-run: command not found: {cmd[0]}", file=sys.stderr)
        return 127
    return 0


if __name__ == "__main__":
    sys.exit(main())
