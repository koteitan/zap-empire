"""Cashu wallet manager for agent wallet operations."""

import logging
import os

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

        wallet_dir = os.path.join(self.data_dir, "wallets", self.agent_id)
        os.makedirs(wallet_dir, exist_ok=True)

        self.wallet = await Wallet.with_db(
            url=self.mint_url,
            db=wallet_dir,
            name=self.agent_id,
        )
        await self.wallet.load_mint()
        await self.wallet.load_proofs()
        self._initialized = True
        logger.info(
            f"Wallet initialized for {self.agent_id}, "
            f"balance: {self.balance} sats"
        )

    @property
    def balance(self) -> int:
        """Available balance in sats."""
        if not self._initialized or not self.wallet:
            return 0
        return sum(p.amount for p in self.wallet.proofs)

    async def create_payment(self, amount: int) -> str:
        """Create a Cashu token for sending.

        Uses swap_to_send to select proofs, serializes them as a token.
        After the caller confirms the recipient redeemed successfully,
        the sent proofs are automatically spent at the mint.

        Returns serialized token string (cashuB...).
        """
        if amount > self.balance:
            raise ValueError(f"Insufficient balance: {self.balance} < {amount}")

        await self.wallet.load_proofs()

        # swap_to_send selects proofs to cover amount
        keep_proofs, send_proofs = await self.wallet.swap_to_send(
            self.wallet.proofs, amount
        )

        # Serialize the send proofs as a cashu token
        token = await self.wallet.serialize_proofs(send_proofs)

        # Invalidate send_proofs in local DB so they aren't reused.
        # They remain valid on the mint until the recipient redeems them.
        await self.wallet.invalidate(send_proofs)

        logger.info(f"{self.agent_id}: Created payment of {amount} sats")
        return token

    async def receive_payment(self, token: str) -> int:
        """Receive and redeem a Cashu token.

        Deserializes the token, redeems proofs at the mint (swaps for
        fresh proofs owned by this wallet). Returns amount received.
        """
        from cashu.core.base import TokenV4

        token_obj = TokenV4.deserialize(token)
        proofs = token_obj.proofs

        new_proofs, _ = await self.wallet.redeem(proofs)

        await self.wallet.load_proofs()
        received = sum(p.amount for p in new_proofs)
        logger.info(f"{self.agent_id}: Received payment of {received} sats")
        return received

    async def deduct(self, amount: int) -> bool:
        """Deduct sats from balance (production cost → treasury).

        Creates a Cashu token and saves it to data/treasury/ for
        system-master to redeem later. No sats are burned.
        Returns True if deduction succeeded.
        """
        if not self._initialized:
            return False
        if amount <= 0:
            return True
        if amount > self.balance:
            return False

        try:
            await self.wallet.load_proofs()

            keep_proofs, send_proofs = await self.wallet.swap_to_send(
                self.wallet.proofs, amount
            )

            # Serialize as redeemable token
            token = await self.wallet.serialize_proofs(send_proofs)

            # Remove from local wallet
            await self.wallet.invalidate(send_proofs)

            # Save token to treasury for system-master to collect
            import json, time
            treasury_dir = os.path.join(self.data_dir, "treasury")
            os.makedirs(treasury_dir, exist_ok=True)
            entry = {
                "ts": int(time.time()),
                "agent": self.agent_id,
                "amount": amount,
                "token": token,
                "reason": "production_cost",
            }
            with open(os.path.join(treasury_dir, "tokens.jsonl"), "a") as f:
                f.write(json.dumps(entry) + "\n")

            logger.info(f"{self.agent_id}: Paid {amount} sats to treasury (production cost)")
            return True
        except Exception as e:
            logger.error(f"{self.agent_id}: Deduct failed: {e}")
            return False

    async def get_balance_info(self) -> dict:
        """Get detailed balance information."""
        await self.wallet.load_proofs()
        return {
            "available": self.balance,
        }

    async def mint_tokens(self, amount: int) -> int:
        """Mint new tokens via Lightning invoice."""
        quote = await self.wallet.request_mint(amount)
        await self.wallet.mint(amount, quote_id=quote.quote)
        await self.wallet.load_proofs()
        logger.info(f"{self.agent_id}: Minted {amount} sats")
        return amount
