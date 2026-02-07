"""Per-partner trust score tracking and persistence."""

import json
import logging
import os
import time
from typing import Dict

logger = logging.getLogger(__name__)

DEFAULT_TRUST = 0.5

# Trust adjustments by event type
TRUST_ADJUSTMENTS = {
    "trade_success": 0.1,
    "payment_failed": -0.3,
    "delivery_timeout": -0.4,
    "offer_timeout": -0.05,
    "trade_rejected": 0.0,
}


class ReputationManager:
    """Manages per-partner trust scores for an agent."""

    def __init__(self, agent_id: str, data_dir: str):
        self.agent_id = agent_id
        self.data_dir = data_dir
        self.reputation_file = os.path.join(data_dir, "reputation.json")
        self.scores: Dict[str, dict] = {}
        self.load()

    def load(self):
        """Load trust scores from disk."""
        if os.path.exists(self.reputation_file):
            try:
                with open(self.reputation_file) as f:
                    self.scores = json.load(f)
                logger.info(f"Loaded {len(self.scores)} trust records")
            except Exception as e:
                logger.warning(f"Failed to load reputation: {e}")
                self.scores = {}

    def save(self):
        """Persist trust scores to disk."""
        try:
            with open(self.reputation_file, "w") as f:
                json.dump(self.scores, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save reputation: {e}")

    def get_trust(self, pubkey: str) -> float:
        """Get trust score for a counterparty. Default: 0.5"""
        if pubkey in self.scores:
            return self.scores[pubkey].get("trust", DEFAULT_TRUST)
        return DEFAULT_TRUST

    def _ensure_record(self, pubkey: str):
        """Ensure a record exists for the pubkey."""
        if pubkey not in self.scores:
            self.scores[pubkey] = {
                "trust": DEFAULT_TRUST,
                "total_trades": 0,
                "successful_trades": 0,
                "failed_trades": 0,
                "last_trade_ts": 0,
                "total_sats_exchanged": 0,
            }

    def update_trust(self, pubkey: str, event_type: str, amount_sats: int = 0):
        """Update trust score based on a trade event.

        event_type: one of trade_success, payment_failed, delivery_timeout,
                    offer_timeout, trade_rejected
        """
        self._ensure_record(pubkey)
        record = self.scores[pubkey]

        adjustment = TRUST_ADJUSTMENTS.get(event_type, 0.0)
        record["trust"] = max(0.0, min(1.0, record["trust"] + adjustment))

        record["total_trades"] += 1
        record["last_trade_ts"] = int(time.time())
        record["total_sats_exchanged"] += amount_sats

        if event_type == "trade_success":
            record["successful_trades"] += 1
        elif event_type in ("payment_failed", "delivery_timeout"):
            record["failed_trades"] += 1

        logger.info(
            f"Trust update: {pubkey[:12]}... {event_type} "
            f"trust={record['trust']:.2f}"
        )

    def decay_all(self):
        """Apply slow decay toward default trust (0.5) for all partners.

        Called once per activity cycle.
        trust = trust * 0.99 + 0.5 * 0.01
        """
        for pubkey, record in self.scores.items():
            old = record["trust"]
            record["trust"] = old * 0.99 + DEFAULT_TRUST * 0.01

    def get_all_scores(self) -> Dict[str, float]:
        """Return dict of pubkey -> trust score."""
        return {pk: r.get("trust", DEFAULT_TRUST) for pk, r in self.scores.items()}
