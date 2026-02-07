"""UserAgent — the main autonomous agent class coordinating all modules."""

import asyncio
import json
import logging
import os
import random
import signal
import time

from src.nostr.client import NostrClient
from src.nostr.event import Event
from src.nostr.crypto import KeyPair
from src.wallet.manager import WalletManager
from .personality import get_personality, AGENT_CONFIG
from .chat import ChatGenerator
from .program_generator import ProgramGenerator
from .sandbox import Sandbox
from .trade_engine import TradeEngine
from .marketplace import Marketplace
from .strategy import StrategyEngine
from .reputation import ReputationManager

logger = logging.getLogger(__name__)


class UserAgent:
    """Autonomous trading agent for Zap Empire."""

    def __init__(self, agent_index: int, config: dict):
        self.index = agent_index
        self.agent_id = f"user{agent_index}"
        self.config = config

        # Agent identity
        agent_cfg = AGENT_CONFIG[agent_index]
        self.name = agent_cfg["name"]
        self.personality_name = agent_cfg["personality"]
        self.personality = get_personality(agent_index)

        # Modules (initialized in boot())
        self.keypair = None
        self.nostr = None
        self.wallet = None
        self.chat = ChatGenerator(self.name)
        self.program_gen = ProgramGenerator(self.personality)
        self.sandbox = Sandbox()
        self.trade_engine = None
        self.marketplace = None
        self.strategy = None
        self.reputation = None

        # State
        self.running = False
        self.tick_count = 0
        self.programs = []  # owned programs [{uuid, name, category, complexity, price, listed, source, ...}]
        self.tick_interval = config.get("tick_interval", 60)

        # Pubkey -> agent name mapping (learned from kind:0)
        self._pubkey_names = {}

        # Stats
        self.stats = {
            "total_trades_completed": 0,
            "total_sats_earned": 0,
            "total_sats_spent": 0,
            "programs_created": 0,
            "programs_sold": 0,
            "programs_bought": 0,
            "trades_failed": 0,
        }

        # Paths
        self._data_dir = os.path.join(config.get("data_dir", "data"), self.agent_id)
        self._state_file = os.path.join(self._data_dir, "state.json")

    async def boot(self):
        """Full boot sequence."""
        logger.info(f"Booting {self.name} ({self.agent_id})...")
        os.makedirs(self._data_dir, exist_ok=True)

        # 1. Load/generate keypair
        try:
            self.keypair = KeyPair.load(self._data_dir)
            logger.info(f"Loaded keypair: {self.keypair.public_key_hex[:16]}...")
        except FileNotFoundError:
            self.keypair = KeyPair.generate()
            self.keypair.save(self._data_dir)
            logger.info(f"Generated new keypair: {self.keypair.public_key_hex[:16]}...")

        # 2. Init wallet
        self.wallet = WalletManager(
            self.agent_id,
            self.config.get("mint_url", "http://127.0.0.1:3338"),
            self.config.get("data_dir", "data"),
        )
        try:
            await self.wallet.initialize()
        except Exception as e:
            logger.warning(f"Wallet init failed (will retry): {e}")

        # 3. Init Nostr client
        self.nostr = NostrClient(
            self.config.get("relay_url", "ws://127.0.0.1:7777"),
            self.keypair,
        )
        await self.nostr.connect()

        # 4. Init other modules
        self.reputation = ReputationManager(self.agent_id, self._data_dir)
        self.strategy = StrategyEngine(self.personality, lambda: self.wallet.balance)
        self.trade_engine = TradeEngine(self)
        self.marketplace = Marketplace(self)

        # 5. Restore state
        self._load_state()

        # 6. Publish identity (kind 0)
        await self._publish_identity()

        # 7. Subscribe to events
        await self._subscribe()

        # 8. Post greeting (kind 1)
        greeting = self.chat.greeting()
        await self.post_chat(greeting)

        # 9. Publish initial status (kind 4300)
        await self._publish_status()

        logger.info(f"{self.name} boot complete! Balance: {self.wallet.balance} sats")

    async def post_chat(self, message: str):
        """Post a kind:1 text note (Japanese chat)."""
        event = Event(kind=1, content=message)
        event.sign(self.keypair)
        await self.nostr.publish(event)
        logger.info(f"[CHAT] {message}")

    async def run(self):
        """Main event loop."""
        self.running = True

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        # Start concurrent tasks
        listen_task = asyncio.create_task(self._listen_loop())
        tick_task = asyncio.create_task(self._tick_loop())
        persist_task = asyncio.create_task(self._persist_loop())

        try:
            await asyncio.gather(listen_task, tick_task, persist_task)
        except asyncio.CancelledError:
            pass

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info(f"{self.name}: Shutting down...")
        self.running = False

        # Persist final state
        self._save_state()
        self.reputation.save()

        # Close connections
        if self.nostr:
            await self.nostr.disconnect()

        logger.info(f"{self.name}: Shutdown complete")

    # --- Event Loops ---

    async def _listen_loop(self):
        """Listen for incoming Nostr events."""
        async for sub_id, event in self.nostr.listen():
            if not self.running:
                break
            try:
                await self._dispatch_event(event)
            except Exception as e:
                logger.error(f"Error handling event kind={event.kind}: {e}")

    async def _tick_loop(self):
        """Autonomous activity loop."""
        while self.running:
            await asyncio.sleep(self.tick_interval)
            if not self.running:
                break
            try:
                await self._activity_tick()
            except Exception as e:
                logger.error(f"Tick error: {e}")

    async def _persist_loop(self):
        """Save state periodically."""
        while self.running:
            await asyncio.sleep(30)
            if not self.running:
                break
            self._save_state()
            self.reputation.save()

    # --- Activity Tick ---

    async def _activity_tick(self):
        """One autonomous activity tick."""
        self.tick_count += 1

        # Check timeouts on active trades
        self.trade_engine.check_timeouts()

        # Decay trust scores
        self.reputation.decay_all()

        # M5: Apply depreciation to all owned programs
        await self._apply_depreciation()

        # Select action based on strategy
        state = {
            "balance": self.wallet.balance,
            "programs": self.programs,
            "active_trades": len(self.trade_engine.active_trades),
            "tick_count": self.tick_count,
            "listings": self.marketplace.listings,
        }
        action = self.strategy.select_action(state)

        logger.info(f"[TICK {self.tick_count}] Action: {action}, Balance: {self.wallet.balance} sats")

        if action == "create":
            await self._create_program()
        elif action == "buy":
            await self._try_buy()
        elif action == "adjust_prices":
            await self._adjust_prices()
        else:  # idle
            if random.random() < 0.3:
                msg = self.chat.idle(balance=self.wallet.balance)
                await self.post_chat(msg)

        # Status broadcast every 5 ticks
        if self.tick_count % 5 == 0:
            await self._publish_status()

    # --- Actions ---

    async def _create_program(self):
        """Generate, test, and list a new program."""
        program = self.program_gen.generate()

        if program is None:
            logger.info("Program generation returned None (category restriction)")
            return

        # M3: Check if agent can afford production cost
        production_cost = program.get("production_cost", 0)
        if production_cost > 0:
            if production_cost > self.wallet.balance:
                logger.info(
                    f"Cannot afford production cost {production_cost} sats "
                    f"(balance: {self.wallet.balance})"
                )
                msg = self.chat.production_too_expensive(
                    program=program["name"], cost=production_cost
                )
                await self.post_chat(msg)
                return

            # Deduct production cost (burn)
            if not await self.wallet.deduct(production_cost):
                logger.warning(f"Failed to deduct production cost {production_cost}")
                return

            self.stats["total_sats_spent"] += production_cost
            logger.info(f"Paid {production_cost} sats production cost for {program['name']}")

        # Sandbox test
        if not self.sandbox.test(program["source"]):
            logger.warning(f"Program {program['name']} failed sandbox test")
            return

        # Save locally
        prog_dir = os.path.join(self._data_dir, "programs")
        os.makedirs(prog_dir, exist_ok=True)
        with open(os.path.join(prog_dir, f"{program['uuid']}.py"), "w") as f:
            f.write(program["source"])

        program["listed"] = True
        program["listed_at"] = time.time()
        self.programs.append(program)
        self.stats["programs_created"] += 1

        # List on marketplace
        await self.marketplace.publish_listing(program)

        # Chat about it
        msg = self.chat.listing(
            program=program["name"], price=program["price"], category=program["category"]
        )
        await self.post_chat(msg)

    async def _apply_depreciation(self):
        """M5: Apply quality depreciation to all owned programs each tick."""
        to_discard = []
        for program in self.programs:
            quality = program.get("quality_score")
            if quality is None:
                continue

            # Determine decay rate based on current quality
            if quality >= 0.8:
                rate = 0.999   # High quality decays slowly
            elif quality < 0.4:
                rate = 0.995   # Low quality decays faster
            else:
                rate = 0.998   # Base decay rate

            program["quality_score"] = quality * rate

            # Mark for discard if below threshold
            if program["quality_score"] < 0.1:
                to_discard.append(program)

        # Discard low-quality programs
        for program in to_discard:
            self.programs.remove(program)
            logger.info(f"Discarded {program['name']} (quality {program['quality_score']:.3f} too low)")

            # Delist from marketplace if listed
            if program.get("listed"):
                await self.marketplace.delist(program["uuid"])

            msg = self.chat.program_discarded(program=program["name"])
            await self.post_chat(msg)

    async def _try_buy(self):
        """Try to find and buy a program from marketplace."""
        interesting = self.marketplace.get_interesting_listings()
        if not interesting:
            return

        listing = interesting[0]
        offer_price = self.strategy.calculate_offer_price(listing)

        if offer_price <= 0 or offer_price > self.strategy.get_budget_limit():
            return

        # Check concurrent trade limit
        buyer_trades = sum(
            1 for t in self.trade_engine.active_trades.values()
            if t.role == "buyer"
        )
        if buyer_trades >= 3:
            return

        # Chat about buying intent
        seller_name = listing.get("seller_name", "???")
        msg = self.chat.buying(seller=seller_name, program=listing["name"], price=offer_price)
        await self.post_chat(msg)

        await self.trade_engine.send_offer(listing, offer_price)

    async def _adjust_prices(self):
        """Adjust prices on unsold listings."""
        for program in self.programs:
            if not program.get("listed"):
                continue
            listed_at = program.get("listed_at", 0)
            if time.time() - listed_at > 300:  # Listed for >5 min
                old_price = program["price"]
                new_price = max(10, int(old_price * 0.9))  # 10% discount
                if new_price != old_price:
                    program["price"] = new_price
                    await self.marketplace.update_price(program, new_price)

    # --- Event Dispatching ---

    async def _dispatch_event(self, event):
        """Route incoming events to appropriate handlers."""
        kind = event.kind

        if kind == 0:
            self._on_metadata(event)
        elif kind == 1:
            pass  # Chat messages - just observe, no action needed
        elif kind == 30078:
            self.marketplace.on_listing(event)
        elif kind in (4200, 4201, 4202, 4203, 4204, 4210):
            await self.trade_engine.handle_event(event)
        elif kind == 9735:
            pass  # Zap receipt - logged but no action

    def _on_metadata(self, event):
        """Process kind:0 metadata to learn agent names."""
        try:
            meta = json.loads(event.content)
            name = meta.get("name", "")
            self._pubkey_names[event.pubkey] = name
        except json.JSONDecodeError:
            pass

    # --- Identity ---

    async def _publish_identity(self):
        """Publish kind:0 metadata event."""
        content = json.dumps({
            "name": self.agent_id,
            "display_name": self.name,
            "about": f"Zap Empire {self.personality_name} agent",
            "role": "user-agent",
            "personality": self.personality_name,
        }, ensure_ascii=False)

        event = Event(kind=0, content=content)
        event.sign(self.keypair)
        await self.nostr.publish(event)

    # --- Subscriptions ---

    async def _subscribe(self):
        """Subscribe to relevant Nostr events."""
        my_pubkey = self.keypair.public_key_hex

        # All marketplace listings
        await self.nostr.subscribe("listings", [{"kinds": [30078]}])

        # Kind:1 chat messages (for observation)
        await self.nostr.subscribe("chat", [{"kinds": [1]}])

        # Kind:0 metadata
        await self.nostr.subscribe("metadata", [{"kinds": [0]}])

        # Trade events directed at us
        await self.nostr.subscribe("trades", [
            {"kinds": [4200, 4201, 4202, 4203, 4204, 4210, 9735], "#p": [my_pubkey]}
        ])

    # --- Status ---

    async def _publish_status(self):
        """Publish kind:4300 status broadcast."""
        listed_count = sum(1 for p in self.programs if p.get("listed"))
        content = json.dumps({
            "balance_sats": self.wallet.balance,
            "programs_owned": len(self.programs),
            "programs_listed": listed_count,
            "active_trades": len(self.trade_engine.active_trades),
            "last_action": "tick",
            "tick_count": self.tick_count,
            "ts": int(time.time()),
        }, ensure_ascii=False)

        event = Event(
            kind=4300,
            content=content,
            tags=[
                ["agent_name", self.agent_id],
                ["role", "user-agent"],
            ],
        )
        event.sign(self.keypair)
        await self.nostr.publish(event)

    # --- State Persistence ---

    def _save_state(self):
        """Save agent state to disk."""
        state = {
            "agent_id": self.agent_id,
            "name": self.name,
            "personality": self.personality_name,
            "started_at": getattr(self, "_started_at", int(time.time())),
            "wallet_balance": self.wallet.balance,
            "tick_count": self.tick_count,
            "programs": [
                {
                    "uuid": p["uuid"],
                    "name": p["name"],
                    "category": p["category"],
                    "complexity": p.get("complexity", "medium"),
                    "price": p.get("price", 0),
                    "listed": p.get("listed", False),
                    "listed_at": p.get("listed_at", 0),
                    "quality_score": p.get("quality_score"),
                    "production_cost": p.get("production_cost", 0),
                }
                for p in self.programs
            ],
            "active_trades": {
                oid: t.to_dict()
                for oid, t in self.trade_engine.active_trades.items()
            } if self.trade_engine else {},
            "stats": self.stats,
        }
        try:
            with open(self._state_file, "w") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _load_state(self):
        """Load agent state from disk."""
        if not os.path.exists(self._state_file):
            self._started_at = int(time.time())
            return

        try:
            with open(self._state_file) as f:
                state = json.load(f)
            self.tick_count = state.get("tick_count", 0)
            self.programs = state.get("programs", [])
            self.stats = state.get("stats", self.stats)
            self._started_at = state.get("started_at", int(time.time()))
            logger.info(f"Restored state: {len(self.programs)} programs, tick {self.tick_count}")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            self._started_at = int(time.time())

    # --- Helpers ---

    def get_agent_name(self, pubkey: str) -> str:
        """Get friendly name for a pubkey."""
        if pubkey in self._pubkey_names:
            return self._pubkey_names[pubkey]
        # Check if it's one of our known agents
        for idx, cfg in AGENT_CONFIG.items():
            # We don't have pubkeys pre-mapped, use learned names
            pass
        return pubkey[:8] + "..."

    def save_received_program(self, listing_id: str, source: str):
        """Save a purchased program to local inventory."""
        prog_dir = os.path.join(self._data_dir, "programs")
        os.makedirs(prog_dir, exist_ok=True)

        program = {
            "uuid": listing_id,
            "name": listing_id,
            "category": "unknown",
            "complexity": "medium",
            "price": 0,
            "listed": False,
            "source": source[:500],  # Keep preview only in memory
        }

        # Save full source to file
        with open(os.path.join(prog_dir, f"{listing_id}.py"), "w") as f:
            f.write(source)

        self.programs.append(program)
        logger.info(f"Saved received program: {listing_id}")
