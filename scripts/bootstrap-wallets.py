#!/usr/bin/env python3
"""Bootstrap wallets for all Zap Empire agents.

Creates a Cashu wallet for each user agent (user0-user9) and mints
initial sats using the FakeWallet backend.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from cashu.core.settings import settings
    from cashu.wallet.wallet import Wallet

    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Load constants
    with open(os.path.join(project_dir, "config", "constants.json")) as f:
        constants = json.load(f)

    mint_url = constants["mint_url"]
    initial_balance = constants["initial_balance_sats"]

    # Load agent names
    with open(os.path.join(project_dir, "config", "agents.json")) as f:
        agents = json.load(f)

    user_agents = [a for a in agents["agents"] if a["id"].startswith("user")]

    print(f"=== Zap Empire: Wallet Bootstrap ===")
    print(f"Mint URL: {mint_url}")
    print(f"Initial balance per agent: {initial_balance} sats")
    print(f"Agents to bootstrap: {len(user_agents)}")
    print()

    for agent in user_agents:
        agent_id = agent["id"]
        agent_name = agent["name"]
        wallet_dir = os.path.join(project_dir, "data", "wallets", agent_id)
        os.makedirs(wallet_dir, exist_ok=True)

        try:
            wallet = await Wallet.with_db(
                url=mint_url,
                db=wallet_dir,
                name=agent_id,
            )
            await wallet.load_mint()

            # Mint initial tokens
            await wallet.mint(initial_balance, split=[initial_balance])

            balance = await wallet.balance()
            print(f"  {agent_id} ({agent_name}): {balance} sats")

        except Exception as e:
            print(f"  {agent_id} ({agent_name}): FAILED - {e}", file=sys.stderr)

    print()
    print("Bootstrap complete.")


if __name__ == "__main__":
    asyncio.run(main())
