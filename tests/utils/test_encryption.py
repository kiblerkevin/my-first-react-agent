"""Tests for utils/encryption.py."""

import pytest

from utils.encryption import decrypt_token, encrypt_token, is_encrypted

TEST_KEY = 'test-secret-key-for-encryption'


class TestEncryptDecrypt:
    """Tests for encrypt/decrypt round-trip."""

    def test_round_trip(self):
        plaintext = 'my-oauth-token-abc123'
        encrypted = encrypt_token(plaintext, key=TEST_KEY)
        decrypted = decrypt_token(encrypted, key=TEST_KEY)
        assert decrypted == plaintext

    def test_encrypted_value_differs_from_plaintext(self):
        plaintext = 'my-oauth-token-abc123'
        encrypted = encrypt_token(plaintext, key=TEST_KEY)
        assert encrypted != plaintext

    def test_encrypted_value_has_prefix(self):
        encrypted = encrypt_token('token', key=TEST_KEY)
        assert encrypted.startswith('enc:')

    def test_decrypt_plaintext_returns_as_is(self):
        plaintext = 'not-encrypted-value'
        result = decrypt_token(plaintext, key=TEST_KEY)
        assert result == plaintext

    def test_different_keys_produce_different_ciphertext(self):
        plaintext = 'same-token'
        enc1 = encrypt_token(plaintext, key='key-one')
        enc2 = encrypt_token(plaintext, key='key-two')
        assert enc1 != enc2

    def test_wrong_key_raises(self):
        from cryptography.fernet import InvalidToken

        encrypted = encrypt_token('token', key='correct-key')
        with pytest.raises(InvalidToken):
            decrypt_token(encrypted, key='wrong-key')


class TestIsEncrypted:
    """Tests for is_encrypted."""

    def test_encrypted_value(self):
        assert is_encrypted('enc:abc123') is True

    def test_plaintext_value(self):
        assert is_encrypted('plain-token') is False

    def test_empty_string(self):
        assert is_encrypted('') is False


class TestKeyDerivation:
    """Tests for key derivation and caching."""

    def test_same_key_produces_same_fernet(self):
        from utils.encryption import _derive_fernet

        f1 = _derive_fernet('test-key')
        f2 = _derive_fernet('test-key')
        assert f1 is f2

    def test_missing_key_raises(self):
        from unittest.mock import patch

        with (
            patch('utils.secrets.get_secret', return_value=None),
            pytest.raises(RuntimeError, match='APPROVAL_SECRET_KEY'),
        ):
            encrypt_token('token')

    def test_falls_back_to_secrets_provider(self):
        from unittest.mock import patch

        with patch('utils.secrets.get_secret', return_value=TEST_KEY):
            encrypted = encrypt_token('token')
            decrypted = decrypt_token(encrypted, key=TEST_KEY)
            assert decrypted == 'token'
