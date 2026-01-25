"""Encryption utilities for the password vault using Fernet symmetric encryption."""

from cryptography.fernet import Fernet, InvalidToken


_fernet: Fernet | None = None


def init_crypto(key: str) -> None:
    """Initialize encryption with the provided Fernet key.

    Args:
        key: A valid Fernet key (32 bytes, URL-safe base64-encoded).
             Generate with: Fernet.generate_key()
    """
    global _fernet
    if not key:
        print("Warning: No encryption key provided, vault passwords disabled")
        return
    _fernet = Fernet(key.encode() if isinstance(key, str) else key)


def is_initialized() -> bool:
    """Check if crypto has been initialized."""
    return _fernet is not None


def encrypt_password(plaintext: str) -> bytes:
    """Encrypt a password for storage.

    Args:
        plaintext: The password to encrypt.

    Returns:
        Encrypted bytes suitable for storage in bytea column.

    Raises:
        RuntimeError: If crypto not initialized.
    """
    if not _fernet:
        raise RuntimeError("Crypto not initialized - cannot encrypt password")
    return _fernet.encrypt(plaintext.encode())


def decrypt_password(ciphertext: bytes) -> str:
    """Decrypt a password from storage.

    Args:
        ciphertext: The encrypted bytes from the database.

    Returns:
        The decrypted password string.

    Raises:
        RuntimeError: If crypto not initialized.
        InvalidToken: If decryption fails (wrong key or corrupted data).
    """
    if not _fernet:
        raise RuntimeError("Crypto not initialized - cannot decrypt password")
    return _fernet.decrypt(ciphertext).decode()


def generate_key() -> str:
    """Generate a new Fernet key for configuration.

    Returns:
        A new Fernet key as a string.
    """
    return Fernet.generate_key().decode()
