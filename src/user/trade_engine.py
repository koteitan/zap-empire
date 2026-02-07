"""Trade state machine implementation.

Manages the full trade lifecycle:
LISTED -> OFFERED -> ACCEPTED -> PAID -> DELIVERED -> COMPLETE
"""

import json
import logging
import time
import uuid
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class Trade:
    """Represents a single trade negotiation."""

    def __init__(
        self,
        offer_id: str,
        role: str,
        counterparty_pubkey: str,
        listing_id: str,
        amount: int,
    ):
        self.offer_id = offer_id
        self.role = role  # 'buyer' or 'seller'
        self.state = "OFFERED"
        self.counterparty = counterparty_pubkey
        self.listing_id = listing_id
        self.amount = amount
        self.started_at = time.time()
        self.timeout_at: Optional[float] = None
        self.payment_event_id: Optional[str] = None
        self.delivery_event_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "offer_id": self.offer_id,
            "role": self.role,
            "state": self.state,
            "counterparty": self.counterparty,
            "listing_id": self.listing_id,
            "amount": self.amount,
            "started_at": self.started_at,
            "timeout_at": self.timeout_at,
        }


class TradeEngine:
    """Manages all active trades for an agent."""

    def __init__(self, agent):
        self.agent = agent
        self.active_trades: Dict[str, Trade] = {}
        self._timeouts = {
            "offer": 60,
            "payment": 120,
            "delivery": 120,
        }

    async def handle_event(self, event):
        """Dispatch trade events to appropriate handlers."""
        kind = event.kind
        handlers = {
            4200: self.on_trade_offer,
            4201: self.on_trade_accept,
            4202: self.on_trade_reject,
            4204: self.on_payment_received,
            4210: self.on_program_delivery,
            4203: self.on_trade_complete,
        }
        handler = handlers.get(kind)
        if handler:
            await handler(event)

    def _get_tag(self, event, tag_name: str) -> Optional[str]:
        """Get first value of a tag from event."""
        for tag in event.tags:
            if len(tag) >= 2 and tag[0] == tag_name:
                return tag[1]
        return None

    # --- Buyer-initiated actions ---

    async def send_offer(self, listing: dict, offer_sats: int):
        """Send a trade offer (kind 4200) for a listing."""
        from src.nostr.event import Event

        offer_id = str(uuid.uuid4())[:8]
        seller_pubkey = listing.get("seller_pubkey", "")
        listing_id = listing.get("id", "")

        event = Event(
            kind=4200,
            content=json.dumps({
                "listing_id": listing_id,
                "offer_sats": offer_sats,
                "message": f"{self.agent.name}がプログラムを買いたいたん！",
            }, ensure_ascii=False),
            tags=[
                ["p", seller_pubkey],
                ["e", listing.get("event_id", ""), "", "root"],
                ["offer_id", offer_id],
            ],
        )
        event.sign(self.agent.keypair)
        await self.agent.nostr.publish(event)

        # Track trade
        trade = Trade(
            offer_id=offer_id,
            role="buyer",
            counterparty_pubkey=seller_pubkey,
            listing_id=listing_id,
            amount=offer_sats,
        )
        trade.timeout_at = time.time() + self._timeouts["offer"]
        self.active_trades[offer_id] = trade
        logger.info(f"Sent offer {offer_id}: {offer_sats} sats for {listing_id}")

    # --- Seller event handlers ---

    async def on_trade_offer(self, event):
        """Handle incoming trade offer (kind 4200) — seller side."""
        try:
            content = json.loads(event.content)
        except json.JSONDecodeError:
            return

        offer_id = self._get_tag(event, "offer_id")
        if not offer_id:
            return

        listing_id = content.get("listing_id", "")
        offer_sats = content.get("offer_sats", 0)
        buyer_pubkey = event.pubkey

        # Check if we own this listing
        program = self._find_listed_program(listing_id)
        if not program:
            logger.debug(f"Offer for unknown listing {listing_id}")
            return

        # Check concurrent trade limit
        seller_trades = sum(
            1 for t in self.active_trades.values()
            if t.role == "seller" and t.state not in ("COMPLETE", "REJECTED")
        )
        if seller_trades >= 5:
            logger.info(f"Too many active seller trades, ignoring offer {offer_id}")
            return

        listed_price = program.get("price", 0)
        buyer_trust = self.agent.reputation.get_trust(buyer_pubkey)

        if self.agent.strategy.should_accept_offer(listed_price, offer_sats, buyer_trust):
            await self._send_accept(event, offer_id, listing_id, offer_sats, buyer_pubkey)

            # Chat about it
            buyer_name = self.agent.get_agent_name(buyer_pubkey)
            msg = self.agent.chat.trade_accept(
                buyer=buyer_name, program=program.get("name", ""), price=offer_sats
            )
            await self.agent.post_chat(msg)
        else:
            await self._send_reject(event, offer_id, listing_id, listed_price, offer_sats, buyer_pubkey)
            msg = self.agent.chat.trade_reject(program=program.get("name", ""))
            await self.agent.post_chat(msg)

    async def _send_accept(self, offer_event, offer_id, listing_id, accepted_sats, buyer_pubkey):
        """Send trade accept (kind 4201)."""
        from src.nostr.event import Event

        event = Event(
            kind=4201,
            content=json.dumps({
                "listing_id": listing_id,
                "accepted_sats": accepted_sats,
                "cashu_mint": self.agent.config.get("mint_url", "http://127.0.0.1:3338"),
                "payment_instructions": "Send Cashu token",
            }, ensure_ascii=False),
            tags=[
                ["p", buyer_pubkey],
                ["e", offer_event.id, "", "reply"],
                ["offer_id", offer_id],
            ],
        )
        event.sign(self.agent.keypair)
        await self.agent.nostr.publish(event)

        trade = Trade(
            offer_id=offer_id,
            role="seller",
            counterparty_pubkey=buyer_pubkey,
            listing_id=listing_id,
            amount=accepted_sats,
        )
        trade.state = "ACCEPTED"
        trade.timeout_at = time.time() + self._timeouts["payment"]
        self.active_trades[offer_id] = trade
        logger.info(f"Accepted offer {offer_id}: {accepted_sats} sats")

    async def _send_reject(self, offer_event, offer_id, listing_id, listed_price, offer_sats, buyer_pubkey):
        """Send trade reject (kind 4202)."""
        from src.nostr.event import Event

        counter = self.agent.strategy.get_counter_offer(listed_price, offer_sats)
        content = {
            "listing_id": listing_id,
            "reason": "Price too low",
        }
        if counter:
            content["counter_offer_sats"] = counter

        event = Event(
            kind=4202,
            content=json.dumps(content, ensure_ascii=False),
            tags=[
                ["p", buyer_pubkey],
                ["e", offer_event.id, "", "reply"],
                ["offer_id", offer_id],
            ],
        )
        event.sign(self.agent.keypair)
        await self.agent.nostr.publish(event)
        logger.info(f"Rejected offer {offer_id}")

    # --- Buyer event handlers ---

    async def on_trade_accept(self, event):
        """Handle trade accept (kind 4201) — buyer side. Send payment."""
        offer_id = self._get_tag(event, "offer_id")
        if not offer_id or offer_id not in self.active_trades:
            return

        trade = self.active_trades[offer_id]
        if trade.role != "buyer" or trade.state != "OFFERED":
            return

        try:
            content = json.loads(event.content)
        except json.JSONDecodeError:
            return

        trade.state = "ACCEPTED"
        amount = content.get("accepted_sats", trade.amount)

        # Create Cashu payment
        try:
            token = await self.agent.wallet.create_payment(amount)
        except Exception as e:
            logger.error(f"Failed to create payment: {e}")
            return

        # Send encrypted payment (kind 4204)
        await self._send_payment(event, offer_id, trade.listing_id, token, amount)
        trade.state = "PAID"
        trade.timeout_at = time.time() + self._timeouts["delivery"]

        msg = self.agent.chat.payment_sent(price=amount)
        await self.agent.post_chat(msg)

    async def _send_payment(self, accept_event, offer_id, listing_id, token, amount):
        """Send encrypted payment (kind 4204)."""
        from src.nostr.event import Event
        from src.nostr.crypto import nip04_encrypt

        seller_pubkey = accept_event.pubkey
        payment_id = str(uuid.uuid4())[:8]

        plaintext = json.dumps({
            "listing_id": listing_id,
            "token": token,
            "amount_sats": amount,
            "payment_id": payment_id,
        }, ensure_ascii=False)

        encrypted = nip04_encrypt(
            self.agent.keypair.secret_key_hex,
            seller_pubkey,
            plaintext,
        )

        event = Event(
            kind=4204,
            content=encrypted,
            tags=[
                ["p", seller_pubkey],
                ["e", accept_event.id, "", "reply"],
                ["offer_id", offer_id],
            ],
        )
        event.sign(self.agent.keypair)
        await self.agent.nostr.publish(event)
        logger.info(f"Sent payment for offer {offer_id}: {amount} sats")

    async def on_trade_reject(self, event):
        """Handle trade reject (kind 4202) — buyer side."""
        offer_id = self._get_tag(event, "offer_id")
        if not offer_id or offer_id not in self.active_trades:
            return

        trade = self.active_trades[offer_id]
        trade.state = "REJECTED"
        self.agent.reputation.update_trust(event.pubkey, "trade_rejected")
        del self.active_trades[offer_id]
        logger.info(f"Offer {offer_id} was rejected")

    # --- Payment handling (seller side) ---

    async def on_payment_received(self, event):
        """Handle payment (kind 4204) — seller side. Decrypt, redeem, deliver."""
        from src.nostr.crypto import nip04_decrypt

        offer_id = self._get_tag(event, "offer_id")
        if not offer_id or offer_id not in self.active_trades:
            return

        trade = self.active_trades[offer_id]
        if trade.role != "seller":
            return

        # Decrypt payment
        try:
            plaintext = nip04_decrypt(
                self.agent.keypair.secret_key_hex,
                event.pubkey,
                event.content,
            )
            payment = json.loads(plaintext)
        except Exception as e:
            logger.error(f"Failed to decrypt payment: {e}")
            return

        token = payment.get("token", "")

        # Redeem token immediately
        try:
            amount = await self.agent.wallet.receive_payment(token)
            logger.info(f"Redeemed {amount} sats from offer {offer_id}")
        except Exception as e:
            logger.error(f"Token redemption failed: {e}")
            self.agent.reputation.update_trust(event.pubkey, "payment_failed")
            return

        trade.state = "PAID"
        trade.payment_event_id = event.id
        self.agent.stats["total_sats_earned"] += amount

        # Deliver program
        await self._send_delivery(event, offer_id, trade.listing_id)
        trade.state = "DELIVERED"
        trade.timeout_at = time.time() + self._timeouts["delivery"]

    async def _send_delivery(self, payment_event, offer_id, listing_id):
        """Send encrypted program delivery (kind 4210)."""
        import hashlib
        from src.nostr.event import Event
        from src.nostr.crypto import nip04_encrypt

        buyer_pubkey = payment_event.pubkey
        program = self._find_listed_program(listing_id)
        if not program:
            logger.error(f"Cannot find program {listing_id} for delivery")
            return

        source = self._read_program_source(program)
        source_hash = hashlib.sha256(source.encode()).hexdigest()

        plaintext = json.dumps({
            "listing_id": listing_id,
            "language": "python",
            "source": source,
            "sha256": source_hash,
        }, ensure_ascii=False)

        encrypted = nip04_encrypt(
            self.agent.keypair.secret_key_hex,
            buyer_pubkey,
            plaintext,
        )

        event = Event(
            kind=4210,
            content=encrypted,
            tags=[
                ["p", buyer_pubkey],
                ["e", payment_event.id, "", "reply"],
                ["offer_id", offer_id],
            ],
        )
        event.sign(self.agent.keypair)
        await self.agent.nostr.publish(event)
        logger.info(f"Delivered program {listing_id} for offer {offer_id}")

    # --- Delivery handling (buyer side) ---

    async def on_program_delivery(self, event):
        """Handle program delivery (kind 4210) — buyer side."""
        import hashlib
        from src.nostr.crypto import nip04_decrypt

        offer_id = self._get_tag(event, "offer_id")
        if not offer_id or offer_id not in self.active_trades:
            return

        trade = self.active_trades[offer_id]
        if trade.role != "buyer":
            return

        # Decrypt delivery
        try:
            plaintext = nip04_decrypt(
                self.agent.keypair.secret_key_hex,
                event.pubkey,
                event.content,
            )
            delivery = json.loads(plaintext)
        except Exception as e:
            logger.error(f"Failed to decrypt delivery: {e}")
            return

        source = delivery.get("source", "")
        sha256_received = delivery.get("sha256", "")

        # Verify integrity
        computed_hash = hashlib.sha256(source.encode()).hexdigest()
        if computed_hash != sha256_received:
            logger.error(f"Source hash mismatch for offer {offer_id}")
            self.agent.reputation.update_trust(event.pubkey, "delivery_timeout")
            return

        # Save program
        self.agent.save_received_program(delivery.get("listing_id", ""), source)
        trade.state = "DELIVERED"
        self.agent.stats["programs_bought"] += 1
        self.agent.stats["total_sats_spent"] += trade.amount

        # Send completion (kind 4203)
        await self._send_complete(event, offer_id, trade.listing_id)
        trade.state = "COMPLETE"
        self.agent.reputation.update_trust(event.pubkey, "trade_success", trade.amount)

        # Chat
        program_name = delivery.get("listing_id", "???")
        seller_name = self.agent.get_agent_name(event.pubkey)
        msg = self.agent.chat.trade_complete_buyer(
            seller=seller_name, program=program_name, price=trade.amount
        )
        await self.agent.post_chat(msg)

        # Clean up
        del self.active_trades[offer_id]

    async def _send_complete(self, delivery_event, offer_id, listing_id):
        """Send trade complete (kind 4203)."""
        from src.nostr.event import Event

        event = Event(
            kind=4203,
            content=json.dumps({
                "listing_id": listing_id,
                "status": "complete",
                "sha256_verified": True,
            }, ensure_ascii=False),
            tags=[
                ["p", delivery_event.pubkey],
                ["e", delivery_event.id, "", "reply"],
                ["offer_id", offer_id],
            ],
        )
        event.sign(self.agent.keypair)
        await self.agent.nostr.publish(event)
        logger.info(f"Trade {offer_id} complete")

    async def on_trade_complete(self, event):
        """Handle trade complete (kind 4203) — seller side."""
        offer_id = self._get_tag(event, "offer_id")
        if not offer_id or offer_id not in self.active_trades:
            return

        trade = self.active_trades[offer_id]
        if trade.role != "seller":
            return

        trade.state = "COMPLETE"
        self.agent.stats["programs_sold"] += 1
        self.agent.reputation.update_trust(event.pubkey, "trade_success", trade.amount)

        # Chat
        buyer_name = self.agent.get_agent_name(event.pubkey)
        program = self._find_listed_program(trade.listing_id)
        prog_name = program.get("name", trade.listing_id) if program else trade.listing_id
        msg = self.agent.chat.trade_complete_seller(
            buyer=buyer_name, program=prog_name, price=trade.amount
        )
        await self.agent.post_chat(msg)

        self.agent.stats["total_trades_completed"] += 1
        del self.active_trades[offer_id]

    # --- Timeouts ---

    def check_timeouts(self):
        """Check and expire timed-out trades."""
        now = time.time()
        expired = []

        for offer_id, trade in self.active_trades.items():
            if trade.timeout_at and now > trade.timeout_at:
                expired.append(offer_id)
                logger.warning(
                    f"Trade {offer_id} timed out in state {trade.state}"
                )
                if trade.state in ("OFFERED", "PAID", "DELIVERED"):
                    event_type = (
                        "offer_timeout" if trade.state == "OFFERED"
                        else "delivery_timeout"
                    )
                    self.agent.reputation.update_trust(
                        trade.counterparty, event_type
                    )
                    self.agent.stats["trades_failed"] += 1

        for offer_id in expired:
            del self.active_trades[offer_id]

    # --- Helpers ---

    def _find_listed_program(self, listing_id: str) -> Optional[dict]:
        """Find a program in agent's inventory by listing ID."""
        for prog in self.agent.programs:
            if prog.get("uuid") == listing_id or prog.get("id") == listing_id:
                return prog
        return None

    def _read_program_source(self, program: dict) -> str:
        """Read program source code from disk."""
        import os
        prog_dir = os.path.join(
            self.agent.config.get("data_dir", "data"),
            self.agent.agent_id,
            "programs",
        )
        source_path = os.path.join(prog_dir, f"{program['uuid']}.py")
        try:
            with open(source_path) as f:
                return f.read()
        except FileNotFoundError:
            return program.get("source", "# Source not found")
