"""Fernet encryption round-trip tests."""
import pytest

from app import crypto


def test_encrypt_decrypt_roundtrip():
    plain = "ATATT3xFfGF0-secret-token-123"
    enc = crypto.encrypt(plain)
    assert enc != plain
    assert "secret-token" not in enc
    assert crypto.decrypt(enc) == plain


def test_decrypt_wrong_value_raises():
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt("not-a-valid-ciphertext")
