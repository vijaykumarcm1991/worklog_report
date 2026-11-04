"""Fernet-based encryption for credentials stored at rest."""
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


class CryptoError(Exception):
    pass


def _fernet() -> Fernet:
    key = get_settings().enc_key
    if not key:
        raise CryptoError(
            "WORKLOG_ENC_KEY is not set. Generate one and add it to .env: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:  # noqa: BLE001
        raise CryptoError("WORKLOG_ENC_KEY is invalid (must be a valid Fernet key).") from exc


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise CryptoError("Failed to decrypt stored credential (key mismatch?).") from exc
