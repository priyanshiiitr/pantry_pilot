"""Password hashing with bcrypt.

We never store real passwords. A *hash* is a scrambled, one-way version:
you can check a password against it, but you can't turn it back into the password.
bcrypt also adds a random "salt", so two users with the same password get different hashes.
"""

import bcrypt

# bcrypt only looks at the first 72 bytes of a password, and version 5 refuses longer ones.
MAX_PASSWORD_BYTES: int = 72


def hash_password(plain_password: str) -> str:
    """Turn a plain password into a bcrypt hash string that is safe to store."""
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password is too long (max {MAX_PASSWORD_BYTES} bytes).")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True if `plain_password` matches the stored hash."""
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
