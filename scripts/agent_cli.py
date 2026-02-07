#!/usr/bin/env python3
"""CLI tool for Claude agents to interact with the Zap Empire economy.

Usage:
    python3 scripts/agent_cli.py <agent_index> status
    python3 scripts/agent_cli.py <agent_index> balance
    python3 scripts/agent_cli.py <agent_index> chat <message>
    python3 scripts/agent_cli.py <agent_index> listings
    python3 scripts/agent_cli.py <agent_index> create <name> <category> <price> <source_file>
    python3 scripts/agent_cli.py <agent_index> buy <listing_d_tag> <offer_sats>
    python3 scripts/agent_cli.py <agent_index> offer <listing_d_tag> <offer_sats>
    python3 scripts/agent_cli.py <agent_index> accept <offer_event_id> <buyer_pubkey> <amount>
    python3 scripts/agent_cli.py <agent_index> pay <seller_pubkey> <amount> <trade_id>
    python3 scripts/agent_cli.py <agent_index> deliver <buyer_pubkey> <source_file> <trade_id>
"""

import asyncio
import json
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nostr.client import NostrClient
from src.nostr.event import Event
from src.nostr.crypto import KeyPair, nip04_encrypt, nip04_decrypt
from src.wallet.manager import WalletManager
from src.user.personality import AGENT_CONFIG


def load_config():
    with open("config/constants.json") as f:
        return json.load(f)


async def get_agent(agent_index: int):
    """Initialize agent keypair and wallet."""
    config = load_config()
    agent_id = f"user{agent_index}"
    data_dir = os.path.join("data", agent_id)

    keypair = KeyPair.load(data_dir)
    wallet = WalletManager(agent_id, config["mint_url"], "data")
    await wallet.initialize()

    return agent_id, keypair, wallet, config


async def cmd_status(agent_index: int):
    agent_id, keypair, wallet, config = await get_agent(agent_index)
    agent_cfg = AGENT_CONFIG[agent_index]
    print(json.dumps({
        "agent_id": agent_id,
        "name": agent_cfg["name"],
        "personality": agent_cfg["personality"],
        "pubkey": keypair.public_key_hex,
        "balance_sats": wallet.balance,
        "production_categories": agent_cfg.get("production_categories", []),
    }, ensure_ascii=False, indent=2))


async def cmd_balance(agent_index: int):
    _, _, wallet, _ = await get_agent(agent_index)
    print(wallet.balance)


async def cmd_chat(agent_index: int, message: str):
    import websockets
    agent_id, keypair, _, config = await get_agent(agent_index)
    event = Event(kind=1, content=message)
    event.sign(keypair)
    async with websockets.connect(config["relay_url"]) as ws:
        await ws.send(json.dumps(["EVENT", event.to_dict()], ensure_ascii=False))
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
    print(f"Posted: {message}")


async def cmd_listings(agent_index: int):
    """Fetch current marketplace listings from relay."""
    import websockets
    config = load_config()

    async with websockets.connect(config["relay_url"]) as ws:
        await ws.send(json.dumps(["REQ", "scan", {"kinds": [30078], "limit": 50}]))

        listings = []
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=3)
                msg = json.loads(raw)
                if msg[0] == "EOSE":
                    break
                if msg[0] == "EVENT" and len(msg) >= 3:
                    event = msg[2]
                    content = json.loads(event["content"])
                    d_tag = None
                    price_tag = None
                    for tag in event.get("tags", []):
                        if len(tag) >= 2:
                            if tag[0] == "d":
                                d_tag = tag[1]
                            elif tag[0] == "price":
                                price_tag = int(tag[1])
                    listings.append({
                        "d_tag": d_tag,
                        "name": content.get("name"),
                        "category": content.get("category"),
                        "price": content.get("price_sats", price_tag or 0),
                        "seller_pubkey": event["pubkey"],
                        "quality": content.get("quality_score"),
                        "preview": content.get("preview", "")[:100],
                    })
            except asyncio.TimeoutError:
                break

        await ws.send(json.dumps(["CLOSE", "scan"]))

    print(json.dumps(listings, ensure_ascii=False, indent=2))


async def cmd_create(agent_index: int, name: str, category: str, price: int, source_file: str):
    """Create a program and list it on marketplace."""
    import uuid as uuid_mod
    agent_id, keypair, wallet, config = await get_agent(agent_index)

    # Read source
    with open(source_file) as f:
        source = f.read()

    # Pay production cost to treasury
    base_costs = config.get("base_production_cost", {})
    base_cost = base_costs.get(category, 3)
    # Simple multiplier (Claude agent pays base cost)
    production_cost = max(1, base_cost)

    if production_cost > wallet.balance:
        print(f"ERROR: Cannot afford production cost {production_cost} sats (balance: {wallet.balance})")
        return

    if not await wallet.deduct(production_cost):
        print(f"ERROR: Failed to deduct production cost")
        return

    # Generate listing
    program_uuid = str(uuid_mod.uuid4())
    content_data = {
        "name": name,
        "description": f"A {category} program: {name}",
        "language": "python",
        "version": "1.0.0",
        "category": category,
        "price_sats": price,
        "preview": source[:500],
    }

    import websockets

    event = Event(
        kind=30078,
        content=json.dumps(content_data, ensure_ascii=False),
        tags=[
            ["d", program_uuid],
            ["t", "python"],
            ["t", category],
            ["price", str(price), "sat"],
        ],
    )
    event.sign(keypair)

    async with websockets.connect(config["relay_url"]) as ws:
        await ws.send(json.dumps(["EVENT", event.to_dict()], ensure_ascii=False))
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        resp_data = json.loads(resp)
        if resp_data[0] != "OK" or not resp_data[2]:
            print(f"ERROR: Relay rejected event: {resp_data}")
            return

    # Save program locally
    prog_dir = os.path.join("data", agent_id, "programs")
    os.makedirs(prog_dir, exist_ok=True)
    with open(os.path.join(prog_dir, f"{program_uuid}.py"), "w") as f:
        f.write(source)

    print(json.dumps({
        "status": "listed",
        "uuid": program_uuid,
        "name": name,
        "category": category,
        "price": price,
        "production_cost": production_cost,
        "new_balance": wallet.balance,
    }, ensure_ascii=False, indent=2))


async def cmd_buy(agent_index: int, listing_d_tag: str, offer_sats: int):
    """Instant buy: pay seller directly and receive program source.

    Since all agents run on the same machine, this:
    1. Finds the listing on the relay
    2. Creates a Cashu payment token from buyer's wallet
    3. Deposits the token into seller's wallet (direct file access)
    4. Copies program source to buyer's programs/ directory
    5. Posts trade events (kind:4200 offer + kind:1 announcement)
    """
    import shutil
    import uuid as uuid_mod
    import websockets
    import glob as glob_mod

    agent_id, keypair, wallet, config = await get_agent(agent_index)

    if offer_sats > wallet.balance:
        print(f"ERROR: Cannot afford {offer_sats} sats (balance: {wallet.balance})")
        return

    # Find the listing on relay
    seller_pubkey = None
    listing_content = None
    async with websockets.connect(config["relay_url"]) as ws:
        await ws.send(json.dumps(["REQ", "find", {"kinds": [30078], "#d": [listing_d_tag], "limit": 1}]))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg[0] == "EOSE":
                break
            if msg[0] == "EVENT" and len(msg) >= 3:
                seller_pubkey = msg[2]["pubkey"]
                listing_content = json.loads(msg[2]["content"])

    if not seller_pubkey or not listing_content:
        print("ERROR: Listing not found")
        return

    # Don't buy from yourself
    if seller_pubkey == keypair.public_key_hex:
        print("ERROR: Cannot buy your own listing")
        return

    # Find seller agent_id from pubkey
    seller_agent_id = None
    for idx in range(10):
        sid = f"user{idx}"
        try:
            skp = KeyPair.load(os.path.join("data", sid))
            if skp.public_key_hex == seller_pubkey:
                seller_agent_id = sid
                break
        except FileNotFoundError:
            continue

    if not seller_agent_id:
        print("ERROR: Seller not found among local agents")
        return

    # Create payment token from buyer's wallet
    token = await wallet.create_payment(offer_sats)

    # Deposit into seller's wallet
    seller_wallet = WalletManager(seller_agent_id, config["mint_url"], "data")
    await seller_wallet.initialize()
    received = await seller_wallet.receive_payment(token)

    # Copy program source
    seller_prog_dir = os.path.join("data", seller_agent_id, "programs")
    buyer_prog_dir = os.path.join("data", agent_id, "programs")
    os.makedirs(buyer_prog_dir, exist_ok=True)

    source_file = os.path.join(seller_prog_dir, f"{listing_d_tag}.py")
    if os.path.exists(source_file):
        dest_file = os.path.join(buyer_prog_dir, f"{listing_d_tag}.py")
        shutil.copy2(source_file, dest_file)

    # Post trade offer event to relay
    trade_id = str(uuid_mod.uuid4())[:8]
    offer_content = json.dumps({
        "type": "trade_complete",
        "trade_id": trade_id,
        "listing_id": listing_d_tag,
        "amount": offer_sats,
        "buyer": keypair.public_key_hex,
        "seller": seller_pubkey,
    })

    event = Event(
        kind=4200,
        content=offer_content,
        tags=[["p", seller_pubkey], ["d", listing_d_tag]],
    )
    event.sign(keypair)

    async with websockets.connect(config["relay_url"]) as ws:
        await ws.send(json.dumps(["EVENT", event.to_dict()], ensure_ascii=False))
        await asyncio.wait_for(ws.recv(), timeout=5)

    print(json.dumps({
        "status": "bought",
        "trade_id": trade_id,
        "listing_d_tag": listing_d_tag,
        "program_name": listing_content.get("name", "unknown"),
        "amount_paid": offer_sats,
        "received_by_seller": received,
        "buyer_new_balance": wallet.balance,
        "seller_id": seller_agent_id,
    }, ensure_ascii=False, indent=2))


async def cmd_offer(agent_index: int, listing_d_tag: str, offer_sats: int):
    """Send a trade offer (kind 4200) for a listing."""
    agent_id, keypair, wallet, config = await get_agent(agent_index)

    if offer_sats > wallet.balance:
        print(f"ERROR: Cannot afford {offer_sats} sats (balance: {wallet.balance})")
        return

    import websockets

    # Find the listing to get seller pubkey
    seller_pubkey = None
    async with websockets.connect(config["relay_url"]) as ws:
        await ws.send(json.dumps(["REQ", "find", {"kinds": [30078], "#d": [listing_d_tag], "limit": 1}]))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg[0] == "EOSE":
                break
            if msg[0] == "EVENT" and len(msg) >= 3:
                seller_pubkey = msg[2]["pubkey"]

    if not seller_pubkey:
        print("ERROR: Listing not found")
        return

    import uuid as uuid_mod
    offer_id = str(uuid_mod.uuid4())[:8]

    offer_content = json.dumps({
        "type": "offer",
        "offer_id": offer_id,
        "listing_id": listing_d_tag,
        "offer_sats": offer_sats,
    })

    event = Event(
        kind=4200,
        content=offer_content,
        tags=[["p", seller_pubkey], ["d", listing_d_tag]],
    )
    event.sign(keypair)

    async with websockets.connect(config["relay_url"]) as ws:
        await ws.send(json.dumps(["EVENT", event.to_dict()], ensure_ascii=False))
        await asyncio.wait_for(ws.recv(), timeout=5)

    print(json.dumps({
        "status": "offer_sent",
        "offer_id": offer_id,
        "listing_d_tag": listing_d_tag,
        "offer_sats": offer_sats,
        "seller_pubkey": seller_pubkey,
    }, ensure_ascii=False, indent=2))


async def cmd_pay(agent_index: int, seller_pubkey: str, amount: int, trade_id: str):
    """Create payment token and send via kind 4204."""
    agent_id, keypair, wallet, config = await get_agent(agent_index)

    if amount > wallet.balance:
        print(f"ERROR: Cannot afford {amount} sats (balance: {wallet.balance})")
        return

    # Create payment token
    token = await wallet.create_payment(amount)

    # Send encrypted payment
    encrypted = nip04_encrypt(keypair.secret_key_hex, seller_pubkey, token)

    nostr = NostrClient(config["relay_url"], keypair)
    await nostr.connect()

    event = Event(
        kind=4204,
        content=encrypted,
        tags=[["p", seller_pubkey], ["trade_id", trade_id]],
    )
    event.sign(keypair)
    await nostr.publish(event)
    await nostr.disconnect()

    print(json.dumps({
        "status": "payment_sent",
        "amount": amount,
        "trade_id": trade_id,
        "new_balance": wallet.balance,
    }, ensure_ascii=False, indent=2))


async def cmd_deliver(agent_index: int, buyer_pubkey: str, source_file: str, trade_id: str):
    """Deliver program source via kind 4210 (encrypted)."""
    agent_id, keypair, _, config = await get_agent(agent_index)

    with open(source_file) as f:
        source = f.read()

    encrypted = nip04_encrypt(keypair.secret_key_hex, buyer_pubkey, source)

    nostr = NostrClient(config["relay_url"], keypair)
    await nostr.connect()

    event = Event(
        kind=4210,
        content=encrypted,
        tags=[["p", buyer_pubkey], ["trade_id", trade_id]],
    )
    event.sign(keypair)
    await nostr.publish(event)
    await nostr.disconnect()

    print(json.dumps({
        "status": "delivered",
        "trade_id": trade_id,
        "buyer_pubkey": buyer_pubkey,
    }, ensure_ascii=False, indent=2))


async def cmd_broadcast_status(agent_index: int):
    """Broadcast agent status via kind:4300 for the dashboard."""
    import websockets
    agent_id, keypair, wallet, config = await get_agent(agent_index)
    agent_cfg = AGENT_CONFIG[agent_index]

    # Count programs
    prog_dir = os.path.join("data", agent_id, "programs")
    prog_count = len([f for f in os.listdir(prog_dir) if f.endswith(".py")]) if os.path.isdir(prog_dir) else 0

    content_data = {
        "balance_sats": wallet.balance,
        "programs_owned": prog_count,
        "programs_listed": prog_count,
        "active_trades": 0,
        "last_action": "active",
        "ts": int(time.time()),
    }

    event = Event(
        kind=4300,
        content=json.dumps(content_data),
        tags=[["agent_name", agent_id]],
    )
    event.sign(keypair)

    async with websockets.connect(config["relay_url"]) as ws:
        await ws.send(json.dumps(["EVENT", event.to_dict()], ensure_ascii=False))
        await asyncio.wait_for(ws.recv(), timeout=5)

    print(json.dumps({"status": "broadcast", "agent": agent_id, "balance": wallet.balance}, indent=2))


async def cmd_broadcast_treasury():
    """Broadcast treasury total via kind:4301."""
    import websockets
    treasury_file = os.path.join("data", "treasury", "tokens.jsonl")
    total = 0
    entries = 0
    if os.path.exists(treasury_file):
        with open(treasury_file) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    total += entry.get("amount", 0)
                    entries += 1
                except Exception:
                    pass

    config = load_config()
    # Use user0's keypair to sign the treasury event
    keypair = KeyPair.load(os.path.join("data", "user0"))
    event = Event(
        kind=4301,
        content=json.dumps({"total_sats": total, "entries": entries, "ts": int(time.time())}),
        tags=[["agent_name", "treasury"]],
    )
    event.sign(keypair)

    async with websockets.connect(config["relay_url"]) as ws:
        await ws.send(json.dumps(["EVENT", event.to_dict()], ensure_ascii=False))
        await asyncio.wait_for(ws.recv(), timeout=5)

    print(json.dumps({"status": "treasury_broadcast", "total_sats": total, "entries": entries}, indent=2))


async def cmd_broadcast_all():
    """Broadcast status for all 10 agents + treasury."""
    for i in range(10):
        try:
            await cmd_broadcast_status(i)
        except Exception as e:
            print(f"user{i}: error: {e}")
    try:
        await cmd_broadcast_treasury()
    except Exception as e:
        print(f"treasury: error: {e}")


async def main():
    if len(sys.argv) < 3:
        # Special case: broadcast-all needs no agent_index
        if len(sys.argv) == 2 and sys.argv[1] == "broadcast-all":
            await cmd_broadcast_all()
            return
        print(__doc__)
        sys.exit(1)

    agent_index = int(sys.argv[1])
    command = sys.argv[2]

    if command == "status":
        await cmd_status(agent_index)
    elif command == "balance":
        await cmd_balance(agent_index)
    elif command == "chat":
        await cmd_chat(agent_index, sys.argv[3])
    elif command == "listings":
        await cmd_listings(agent_index)
    elif command == "create":
        await cmd_create(agent_index, sys.argv[3], sys.argv[4], int(sys.argv[5]), sys.argv[6])
    elif command == "buy":
        await cmd_buy(agent_index, sys.argv[3], int(sys.argv[4]))
    elif command == "offer":
        await cmd_offer(agent_index, sys.argv[3], int(sys.argv[4]))
    elif command == "pay":
        await cmd_pay(agent_index, sys.argv[3], int(sys.argv[4]), sys.argv[5])
    elif command == "deliver":
        await cmd_deliver(agent_index, sys.argv[3], sys.argv[4], sys.argv[5])
    elif command == "broadcast_status":
        await cmd_broadcast_status(agent_index)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
