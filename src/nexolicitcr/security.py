import re

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

PASSWORDS = PasswordHash.recommended()
DUMMY_HASH = PASSWORDS.hash("dummy-verification-only-not-an-account")


def valid_username(username):
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", username))


def check_password(password, encoded):
    try:
        return PASSWORDS.verify_and_update(password, encoded)
    except (UnknownHashError, ValueError):
        return False, None


def validate_password(password):
    if not 14 <= len(password) <= 256:
        raise ValueError("Usá una contraseña de entre 14 y 256 caracteres.")
