"""Fernet encryption for sensitive data at rest."""

import base64
import hashlib

from cryptography.fernet import Fernet

_fernet_cache: dict[str, Fernet] = {}

# Prefix to distinguish encrypted values from plaintext
_ENCRYPTED_PREFIX = 'enc:'


def _derive_fernet(secret_key: str) -> Fernet:
    """Derive a Fernet instance from a secret key via PBKDF2.

    Args:
        secret_key: The secret to derive the encryption key from.

    Returns:
        A Fernet instance.
    """
    if secret_key in _fernet_cache:
        return _fernet_cache[secret_key]
    key_bytes = hashlib.pbkdf2_hmac(
        'sha256',
        secret_key.encode(),
        b'chicago-sports-recap-salt',
        100_000,
    )
    fernet_key = base64.urlsafe_b64encode(key_bytes[:32])
    fernet = Fernet(fernet_key)
    _fernet_cache[secret_key] = fernet
    return fernet


def _get_secret_key(explicit_key: str | None = None) -> str:
    """Get the encryption secret key.

    Args:
        explicit_key: Override key for testing. Falls back to secrets provider.

    Returns:
        The secret key string.

    Raises:
        RuntimeError: If no key is available.
    """
    if explicit_key:
        return explicit_key
    from utils.secrets import get_secret

    key = get_secret('APPROVAL_SECRET_KEY')
    if not key:
        raise RuntimeError(
            'APPROVAL_SECRET_KEY is required for token encryption. '
            'Set it via the secrets provider.'
        )
    return key


def encrypt_token(plaintext: str, key: str | None = None) -> str:
    """Encrypt a plaintext token.

    Args:
        plaintext: The value to encrypt.
        key: Explicit encryption key (for testing). Falls back to secrets provider.

    Returns:
        Encrypted string with 'enc:' prefix.
    """
    secret_key = _get_secret_key(key)
    fernet = _derive_fernet(secret_key)
    encrypted = fernet.encrypt(plaintext.encode()).decode()
    return f'{_ENCRYPTED_PREFIX}{encrypted}'


def decrypt_token(stored_value: str, key: str | None = None) -> str:
    """Decrypt a stored token value.

    Handles both encrypted (prefixed with 'enc:') and plaintext values.
    Plaintext values are returned as-is.

    Args:
        stored_value: The value from the database.
        key: Explicit encryption key (for testing). Falls back to secrets provider.

    Returns:
        The decrypted plaintext.
    """
    if not stored_value.startswith(_ENCRYPTED_PREFIX):
        return stored_value

    secret_key = _get_secret_key(key)
    fernet = _derive_fernet(secret_key)
    ciphertext = stored_value[len(_ENCRYPTED_PREFIX) :]
    return fernet.decrypt(ciphertext.encode()).decode()


def is_encrypted(value: str) -> bool:
    """Check if a stored value is encrypted.

    Args:
        value: The stored value to check.

    Returns:
        True if the value has the encryption prefix.
    """
    return value.startswith(_ENCRYPTED_PREFIX)
