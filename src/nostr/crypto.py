"""
Nostr key management, BIP-340 Schnorr signatures, and NIP-04 encryption.

Uses secp256k1 for key operations/ECDH and pycryptodome for AES-256-CBC.
"""

import hashlib
import os
from pathlib import Path

import secp256k1
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64


class KeyPair:
    """Nostr keypair (secp256k1) with x-only public key."""

    def __init__(self, privkey: secp256k1.PrivateKey):
        self._privkey = privkey

    @classmethod
    def generate(cls) -> "KeyPair":
        """Create a new random keypair."""
        secret = os.urandom(32)
        privkey = secp256k1.PrivateKey(secret)
        return cls(privkey)

    @classmethod
    def from_hex(cls, secret_hex: str) -> "KeyPair":
        """Load keypair from a hex-encoded secret key."""
        secret = bytes.fromhex(secret_hex)
        privkey = secp256k1.PrivateKey(secret)
        return cls(privkey)

    def save(self, directory: str) -> None:
        """Save keypair to nostr_secret.hex and nostr_pubkey.hex files."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path / "nostr_secret.hex").write_text(self.secret_key_hex)
        (path / "nostr_pubkey.hex").write_text(self.public_key_hex)

    @classmethod
    def load(cls, directory: str) -> "KeyPair":
        """Load keypair from a directory containing nostr_secret.hex."""
        path = Path(directory)
        secret_hex = (path / "nostr_secret.hex").read_text().strip()
        return cls.from_hex(secret_hex)

    @property
    def secret_key(self) -> bytes:
        """Raw 32-byte secret key."""
        return self._privkey.private_key

    @property
    def public_key(self) -> bytes:
        """X-only public key (32 bytes, no prefix)."""
        # Compressed pubkey is 33 bytes (02/03 prefix + 32 bytes x-coordinate)
        compressed = self._privkey.pubkey.serialize()
        return compressed[1:]  # drop the 02/03 prefix

    @property
    def public_key_hex(self) -> str:
        return self.public_key.hex()

    @property
    def secret_key_hex(self) -> str:
        return self.secret_key.hex()


def sign_schnorr(secret_key_bytes: bytes, message_bytes: bytes) -> bytes:
    """BIP-340 Schnorr signature over a 32-byte message hash.

    Returns 64-byte signature.
    """
    privkey = secp256k1.PrivateKey(secret_key_bytes)
    sig = privkey.schnorr_sign(message_bytes, '', raw=True)
    return sig


def verify_schnorr(pubkey_bytes: bytes, message_bytes: bytes, signature_bytes: bytes) -> bool:
    """Verify a BIP-340 Schnorr signature.

    pubkey_bytes: 32-byte x-only public key
    message_bytes: 32-byte message hash
    signature_bytes: 64-byte signature
    """
    # Construct a PublicKey object from x-only bytes (add 02 prefix)
    try:
        pubkey_obj = secp256k1.PublicKey(b"\x02" + pubkey_bytes, raw=True)
        return pubkey_obj.schnorr_verify(message_bytes, signature_bytes, '', raw=True)
    except Exception:
        return False


def _compute_shared_secret(our_privkey_hex: str, their_pubkey_hex: str) -> bytes:
    """Compute NIP-04 shared secret via ECDH.

    Returns 32-byte shared secret (raw ECDH output).
    """
    privkey = secp256k1.PrivateKey(bytes.fromhex(our_privkey_hex))
    # Add 02 prefix to make compressed public key
    their_pubkey_obj = secp256k1.PublicKey(b"\x02" + bytes.fromhex(their_pubkey_hex), raw=True)
    # ECDH returns 32-byte shared secret (x-coordinate of shared point, SHA256'd)
    shared = privkey.ecdh(their_pubkey_obj.serialize())
    return shared


def nip04_encrypt(sender_privkey_hex: str, recipient_pubkey_hex: str, plaintext: str) -> str:
    """NIP-04 encrypt: AES-256-CBC with ECDH shared secret.

    Returns: base64(ciphertext) + "?iv=" + base64(iv)
    """
    shared_secret = _compute_shared_secret(sender_privkey_hex, recipient_pubkey_hex)

    iv = os.urandom(16)
    cipher = AES.new(shared_secret, AES.MODE_CBC, iv)
    padded = pad(plaintext.encode("utf-8"), AES.block_size)
    ciphertext = cipher.encrypt(padded)

    ct_b64 = base64.b64encode(ciphertext).decode("ascii")
    iv_b64 = base64.b64encode(iv).decode("ascii")
    return f"{ct_b64}?iv={iv_b64}"


def nip04_decrypt(recipient_privkey_hex: str, sender_pubkey_hex: str, encrypted_content: str) -> str:
    """NIP-04 decrypt: parse 'base64(ct)?iv=base64(iv)', decrypt with ECDH shared secret."""
    shared_secret = _compute_shared_secret(recipient_privkey_hex, sender_pubkey_hex)

    # Parse "base64_ciphertext?iv=base64_iv"
    parts = encrypted_content.split("?iv=")
    if len(parts) != 2:
        raise ValueError("Invalid NIP-04 encrypted content format")

    ciphertext = base64.b64decode(parts[0])
    iv = base64.b64decode(parts[1])

    cipher = AES.new(shared_secret, AES.MODE_CBC, iv)
    padded = cipher.decrypt(ciphertext)
    plaintext = unpad(padded, AES.block_size)
    return plaintext.decode("utf-8")
