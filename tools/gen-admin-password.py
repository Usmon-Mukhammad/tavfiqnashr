#!/usr/bin/env python3
"""Generate the publisher's admin password and print ONLY its hash.

    python3 tools/gen-admin-password.py [password-file]

Writes a freshly generated password to `password-file` (default
worker/.admin-password.txt, mode 0600, gitignored) and prints the PBKDF2 hash
on stdout — nothing else. That lets the hash be piped straight into

    npx wrangler secret put ADMIN_PASSWORD_HASH

so neither the password nor the hash is ever displayed. Open the file to read
the password and hand it to the publisher, then delete the file.
"""
import base64
import hashlib
import os
import secrets
import sys

ITERATIONS = 100_000  # Cloudflare Workers' WebCrypto rejects more than this
# Omits look-alike characters so the password can be read aloud or retyped.
ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "worker", ".admin-password.txt")

    password = "".join(secrets.choice(ALPHABET) for _ in range(20))

    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(password + "\n")

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS, dklen=32)
    b = lambda x: base64.b64encode(x).decode("ascii")

    print(f"pbkdf2${ITERATIONS}${b(salt)}${b(digest)}")        # stdout: hash only
    print(f"password written to {out} (chmod 600)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
