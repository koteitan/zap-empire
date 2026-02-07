"""Cashu wallet manager for agent wallet operations."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class WalletManager:
    """Manages a Cashu wallet for a single agent."""

    def __init__(self, agent_id: str, mint_url: str, data_dir: str):
        self.agent_id = agent_id
        self.mint_url = mint_url
        self.data_dir = data_dir
        self.wallet = None
        self._initialized = False

    async def initialize(self):
        """Initialize wallet and connect to mint."""
        from cashu.wallet.wallet import Wallet

        wallet_dir = os.path.join(self.data_dir, self.agent_id, "wallet")
        os.makedirs(wallet_dir, exist_ok=True)

        db_path = os.path.join(wallet_dir, "wallet")

        self.wallet = await Wallet.with_db(
            url=self.mint_url,
            db=db_path,
            name=self.agent_id,
        )
        await self.wallet.load_mint()
        self._initialized = True
        logger.info(
            f"Wallet initialized for {self.agent_id}, "
            f"balance: {self.wallet.available_balance}"
        )

    @property
    def balance(self) -> int:
        """Available balance in sats."""
        if not self._initialized:
            return 0
        return self.wallet.available_balance

    @property
    def pending_balance(self) -> int:
        """Pending outgoing balance."""
        if not self._initialized:
            return 0
        return self.wallet.balance - self.wallet.available_balance

    async def create_payment(self, amount: int) -> str:
        """Create a Cashu token for sending.

        Returns serialized token string (cashuA...).
        """
        if amount > self.balance:
            raise ValueError(f"Insufficient balance: {self.balance} < {amount}")

        send_proofs, _ = await self.wallet.select_to_send(
            self.wallet.proofs, amount
        )
        token = await self.wallet.serialize_proofs(send_proofs)
        logger.info(f"{self.agent_id}: Created payment token for {amount} sats")
        return token

    async def receive_payment(self, token: str) -> int:
        """Receive and redeem a Cashu token.

        Returns amount received.
        """
        amount = await self.wallet.receive(token)
        logger.info(f"{self.agent_id}: Received payment of {amount} sats")
        return amount

    async def get_balance_info(self) -> dict:
        """Get detailed balance information."""
        return {
            "available": self.balance,
            "pending_outgoing": self.pending_balance,
            "total": self.wallet.balance if self._initialized else 0,
        }

    def deduct(self, amount: int) -> bool:
        """Deduct sats from balance (internal burn, e.g. production cost).

        This is a local balance reduction — the sats are destroyed, not sent.
        Returns True if deduction succeeded, False if insufficient balance.
        """
        if not self._initialized:
            return False
        if amount <= 0:
            return True
        if amount > self.balance:
            return False

        # Burn proofs to reduce balance
        # Select proofs that cover the amount and destroy them
        try:
            proofs_to_burn = []
            remaining = amount
            for proof in list(self.wallet.proofs):
                if remaining <= 0:
                    break
                proofs_to_burn.append(proof)
                remaining -= proof.amount

            if remaining > 0:
                return False  # Not enough proofs

            # Remove burned proofs from wallet
            for proof in proofs_to_burn:
                self.wallet.proofs.remove(proof)

            logger.info(f"{self.agent_id}: Burned {amount} sats (production cost)")
            return True
        except Exception as e:
            logger.error(f"{self.agent_id}: Deduct failed: {e}")
            return False

    async def mint_tokens(self, amount: int) -> int:
        """Mint new tokens (for bootstrap only, using FakeWallet)."""
        quote = await self.wallet.request_mint(amount)
        await self.wallet.mint(amount, quote_id=quote.quote)
        logger.info(f"{self.agent_id}: Minted {amount} sats")
        return amount
