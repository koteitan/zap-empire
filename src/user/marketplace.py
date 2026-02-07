"""Marketplace scanner and listing publisher."""

import json
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Marketplace:
    """Manages marketplace listings — both scanning others' and publishing own."""

    def __init__(self, agent):
        self.agent = agent
        self.listings: Dict[str, dict] = {}  # d-tag -> listing data
        self._own_listings: Dict[str, str] = {}  # d-tag -> event_id

    def on_listing(self, event):
        """Process a marketplace listing event (kind 30078)."""
        try:
            content = json.loads(event.content)
        except json.JSONDecodeError:
            return

        d_tag = None
        price_tag = None
        categories = []
        for tag in event.tags:
            if len(tag) >= 2:
                if tag[0] == "d":
                    d_tag = tag[1]
                elif tag[0] == "price":
                    price_tag = int(tag[1])
                elif tag[0] == "t":
                    categories.append(tag[1])

        if not d_tag:
            return

        self.listings[d_tag] = {
            "id": d_tag,
            "event_id": event.id,
            "name": content.get("name", "unknown"),
            "description": content.get("description", ""),
            "language": content.get("language", "python"),
            "category": content.get("category", categories[0] if categories else "unknown"),
            "complexity": content.get("complexity", "medium"),
            "price": content.get("price_sats", price_tag or 0),
            "preview": content.get("preview", ""),
            "quality_score": content.get("quality_score"),
            "seller_pubkey": event.pubkey,
            "seller_name": self.agent.get_agent_name(event.pubkey),
            "created_at": event.created_at,
        }

    def get_interesting_listings(self) -> List[dict]:
        """Find listings worth buying based on agent strategy."""
        my_pubkey = self.agent.keypair.public_key_hex
        owned_categories = [p.get("category", "") for p in self.agent.programs]
        interesting = []

        for listing_id, listing in self.listings.items():
            # Skip own listings
            if listing["seller_pubkey"] == my_pubkey:
                continue

            # Skip if price is 0 or missing
            if listing["price"] <= 0:
                continue

            # Skip old listings (> 30 min)
            if time.time() - listing["created_at"] > 1800:
                continue

            seller_trust = self.agent.reputation.get_trust(listing["seller_pubkey"])

            if self.agent.strategy.should_buy(listing, owned_categories, seller_trust):
                interesting.append(listing)

        # Sort by estimated value/price ratio
        interesting.sort(key=lambda l: l["price"])
        return interesting

    async def publish_listing(self, program: dict):
        """Publish a program listing (kind 30078)."""
        from src.nostr.event import Event

        d_tag = program["uuid"]
        content_data = {
            "name": program["name"],
            "description": program.get("description", f"A {program['category']} program"),
            "language": "python",
            "version": "1.0.0",
            "category": program["category"],
            "complexity": program.get("complexity", "medium"),
            "price_sats": program["price"],
            "preview": program["source"][:500] if len(program.get("source", "")) > 0 else "",
        }
        if program.get("quality_score") is not None:
            content_data["quality_score"] = round(program["quality_score"], 3)
        content = json.dumps(content_data, ensure_ascii=False)

        tags = [
            ["d", d_tag],
            ["t", "python"],
            ["t", program["category"]],
            ["price", str(program["price"]), "sat"],
        ]
        if program.get("quality_score") is not None:
            tags.append(["quality", f"{program['quality_score']:.3f}"])

        event = Event(
            kind=30078,
            content=content,
            tags=tags,
        )
        event.sign(self.agent.keypair)
        await self.agent.nostr.publish(event)

        self._own_listings[d_tag] = event.id
        program["listed"] = True
        program["listed_price"] = program["price"]
        program["listed_at"] = time.time()

        logger.info(f"Listed {program['name']} for {program['price']} sats")

    async def update_price(self, program: dict, new_price: int):
        """Update a listing's price by re-publishing."""
        old_price = program.get("price", 0)
        program["price"] = new_price
        await self.publish_listing(program)

        msg = self.agent.chat.price_adjust(
            program=program["name"], old_price=old_price, new_price=new_price
        )
        await self.agent.post_chat(msg)

    async def delist(self, listing_id: str):
        """Remove a listing (kind 5 deletion event)."""
        from src.nostr.event import Event

        event_id = self._own_listings.get(listing_id)
        if not event_id:
            return

        event = Event(
            kind=5,
            content="Delisted: sold or withdrawn",
            tags=[["e", event_id]],
        )
        event.sign(self.agent.keypair)
        await self.agent.nostr.publish(event)

        if listing_id in self._own_listings:
            del self._own_listings[listing_id]
        if listing_id in self.listings:
            del self.listings[listing_id]

        logger.info(f"Delisted {listing_id}")
