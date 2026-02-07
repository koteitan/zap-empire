"""Entry point for running a user agent.

Usage: python -m src.user.main <agent_index>

Where agent_index is 0-9 corresponding to the 10 agents.
"""

import asyncio
import json
import logging
import sys

from .agent import UserAgent


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.user.main <agent_index>")
        print("  agent_index: 0-9")
        sys.exit(1)

    agent_index = int(sys.argv[1])
    if agent_index < 0 or agent_index > 9:
        print(f"Invalid agent index: {agent_index}. Must be 0-9.")
        sys.exit(1)

    # Load config
    with open("config/constants.json") as f:
        constants = json.load(f)

    config = {
        "relay_url": constants["relay_url"],
        "mint_url": constants["mint_url"],
        "data_dir": "data",
        "tick_interval": constants.get("tick_interval_default", 60),
    }

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format=(
            '{"ts":"%(asctime)s","level":"%(levelname)s",'
            f'"agent":"user{agent_index}","msg":"%(message)s"}}'
        ),
    )

    agent = UserAgent(agent_index, config)
    asyncio.run(agent_main(agent))


async def agent_main(agent: UserAgent):
    await agent.boot()
    await agent.run()


if __name__ == "__main__":
    main()
