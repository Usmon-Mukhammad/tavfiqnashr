#!/usr/bin/env python3
"""Generate the ADMIN_PASSWORD_HASH secret for the blog admin Worker.

    python3 tools/hash-password.py

Prompts for the password without echoing it, prints only the hash. The password
itself is never stored, logged, or sent anywhere — paste the printed hash into:

    cd worker && npx wrangler secret put ADMIN_PASSWORD_HASH

Format: pbkdf2$<iterations>$<salt_b64>$<hash_b64>, verified by worker/src/worker.js
with WebCrypto PBKDF2-SHA256.
"""
import base64
import getpass
import hashlib
import os
import sys

ITERATIONS = 100_000  # Cloudflare Workers' WebCrypto rejects more than this


def main() -> int:
    pw = getpass.getpass("New admin password: ")
    if len(pw) < 12:
        print("error: use at least 12 characters", file=sys.stderr)
        return 1
    if pw != getpass.getpass("Repeat password: "):
        print("error: passwords do not match", file=sys.stderr)
        return 1

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, ITERATIONS, dklen=32)
    b = lambda x: base64.b64encode(x).decode("ascii")
    print()
    print(f"pbkdf2${ITERATIONS}${b(salt)}${b(digest)}")
    print()
    print("Set it with:  cd worker && npx wrangler secret put ADMIN_PASSWORD_HASH", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
