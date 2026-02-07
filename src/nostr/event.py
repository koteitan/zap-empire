"""NIP-01 Nostr event creation, serialization, and signing."""

import hashlib
import json
import time
from typing import List, Optional

from .crypto import KeyPair, sign_schnorr


class Event:
    """Represents a Nostr event (NIP-01)."""

    def __init__(
        self,
        kind: int,
        content: str,
        tags: Optional[List[List[str]]] = None,
        pubkey: str = None,
        created_at: int = None,
        id: str = None,
        sig: str = None,
    ):
        self.kind = kind
        self.content = content
        self.tags = tags or []
        self.pubkey = pubkey or ""
        self.created_at = created_at or int(time.time())
        self.id = id or ""
        self.sig = sig or ""

    def serialize_for_id(self) -> str:
        """NIP-01 serialization: [0, pubkey, created_at, kind, tags, content]"""
        data = [0, self.pubkey, self.created_at, self.kind, self.tags, self.content]
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    def compute_id(self) -> str:
        """Compute the event id (SHA-256 of the serialized event)."""
        serialized = self.serialize_for_id()
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def sign(self, keypair: KeyPair):
        """Sign this event with the given keypair. Sets pubkey, id, and sig."""
        self.pubkey = keypair.public_key_hex
        self.id = self.compute_id()
        id_bytes = bytes.fromhex(self.id)
        sig_bytes = sign_schnorr(keypair.secret_key, id_bytes)
        self.sig = sig_bytes.hex()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pubkey": self.pubkey,
            "created_at": self.created_at,
            "kind": self.kind,
            "tags": self.tags,
            "content": self.content,
            "sig": self.sig,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            kind=d["kind"],
            content=d["content"],
            tags=d.get("tags", []),
            pubkey=d.get("pubkey", ""),
            created_at=d.get("created_at", 0),
            id=d.get("id", ""),
            sig=d.get("sig", ""),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
