"""Nostr relay WebSocket client with reconnection and subscription management."""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List, Tuple

import websockets

from .crypto import KeyPair
from .event import Event

logger = logging.getLogger(__name__)


class NostrClient:
    """Async Nostr relay client.

    Handles connection, reconnection with exponential backoff,
    event publishing, subscriptions, and event deduplication.
    """

    def __init__(self, relay_url: str, keypair: KeyPair):
        self.relay_url = relay_url
        self.keypair = keypair
        self.ws = None
        self._subscriptions: Dict[str, List[dict]] = {}
        self._seen_events: set = set()
        self._max_seen = 10000
        self._connected = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 30
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def connect(self):
        """Connect to relay with exponential backoff retry."""
        while True:
            try:
                self.ws = await websockets.connect(self.relay_url)
                self._connected = True
                self._reconnect_delay = 1
                logger.info(f"Connected to {self.relay_url}")
                # Re-subscribe after reconnect
                for sub_id, filters in self._subscriptions.items():
                    await self._send_req(sub_id, filters)
                return
            except Exception as e:
                logger.warning(
                    f"Connection failed: {e}, retrying in {self._reconnect_delay}s"
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )

    async def disconnect(self):
        """Close connection and stop listening."""
        self._running = False
        self._connected = False
        if self.ws:
            await self.ws.close()

    async def publish(self, event: Event) -> bool:
        """Publish an event to the relay. Signs the event if not already signed."""
        if not event.sig:
            event.sign(self.keypair)
        msg = json.dumps(["EVENT", event.to_dict()], ensure_ascii=False)
        try:
            await self.ws.send(msg)
            return True
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            return False

    async def subscribe(self, sub_id: str, filters: List[dict]):
        """Subscribe to events matching the given filters."""
        self._subscriptions[sub_id] = filters
        await self._send_req(sub_id, filters)

    async def _send_req(self, sub_id: str, filters: List[dict]):
        """Send a REQ message to the relay."""
        msg = json.dumps(["REQ", sub_id] + filters)
        await self.ws.send(msg)

    async def unsubscribe(self, sub_id: str):
        """Close a subscription."""
        if sub_id in self._subscriptions:
            del self._subscriptions[sub_id]
        msg = json.dumps(["CLOSE", sub_id])
        await self.ws.send(msg)

    async def listen(self) -> AsyncGenerator[Tuple[str, Event], None]:
        """Listen for events from the relay. Async generator yielding (sub_id, event).

        Handles reconnection automatically on connection loss.
        Deduplicates events by their id.
        """
        self._running = True
        while self._running:
            try:
                async for raw_msg in self.ws:
                    try:
                        msg = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        continue

                    if msg[0] == "EVENT" and len(msg) >= 3:
                        sub_id = msg[1]
                        event = Event.from_dict(msg[2])
                        if event.id not in self._seen_events:
                            self._seen_events.add(event.id)
                            if len(self._seen_events) > self._max_seen:
                                # Trim to half capacity
                                self._seen_events = set(
                                    list(self._seen_events)[self._max_seen // 2 :]
                                )
                            yield (sub_id, event)
                    elif msg[0] == "OK":
                        pass  # Publish confirmation
                    elif msg[0] == "EOSE":
                        pass  # End of stored events
                    elif msg[0] == "NOTICE":
                        logger.info(f"Relay notice: {msg[1]}")
            except websockets.ConnectionClosed:
                logger.warning("Connection closed, reconnecting...")
                self._connected = False
                await self.connect()
            except Exception as e:
                if self._running:
                    logger.error(f"Listen error: {e}, reconnecting...")
                    self._connected = False
                    await asyncio.sleep(1)
                    await self.connect()
