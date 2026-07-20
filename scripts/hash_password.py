"""Generate a bcrypt hash for a trainer's password, for TRAINER_ACCOUNTS_JSON.

Usage:
    .venv/Scripts/python scripts/hash_password.py "the real password"

Paste the printed hash into TestCase1/.env as the "password_hash" field:
    TRAINER_ACCOUNTS_JSON=[{"email":"priya@example.com","password_hash":"<paste here>"}]
"""
import sys

import bcrypt

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/hash_password.py \"the real password\"", file=sys.stderr)
        sys.exit(1)
    print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())
