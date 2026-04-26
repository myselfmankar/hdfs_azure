"""AES-256-GCM block encryption. Each block gets its own random 12-byte nonce."""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from config import MASTER_KEY_B64

_KEY = base64.b64decode(MASTER_KEY_B64)
assert len(_KEY) == 32, "MASTER_KEY_B64 must decode to 32 bytes (AES-256)"
_AES = AESGCM(_KEY)


def encrypt(plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
    """Returns (nonce, ciphertext+tag)."""
    nonce = os.urandom(12)
    ct = _AES.encrypt(nonce, plaintext, aad)
    return nonce, ct


def decrypt(nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
    return _AES.decrypt(nonce, ciphertext, aad)
