"""Agent personality types and per-agent configuration."""

PERSONALITIES = {
    "conservative": {
        "price_multiplier": 1.2,
        "spending_ratio": 0.10,
        "accept_threshold": 0.95,
        "trust_minimum": 0.6,
        "creation_rate": "low",
        "category_focus": None,
        "risk_tolerance": 0.2,
    },
    "aggressive": {
        "price_multiplier": 0.8,
        "spending_ratio": 0.35,
        "accept_threshold": 0.70,
        "trust_minimum": 0.3,
        "creation_rate": "high",
        "category_focus": None,
        "risk_tolerance": 0.7,
    },
    "specialist": {
        "price_multiplier": 1.3,
        "spending_ratio": 0.20,
        "accept_threshold": 0.90,
        "trust_minimum": 0.5,
        "creation_rate": "medium",
        "category_focus": None,  # Set per-agent
        "risk_tolerance": 0.4,
    },
    "generalist": {
        "price_multiplier": 1.0,
        "spending_ratio": 0.25,
        "accept_threshold": 0.85,
        "trust_minimum": 0.4,
        "creation_rate": "medium",
        "category_focus": None,
        "risk_tolerance": 0.5,
    },
    "opportunist": {
        "price_multiplier": 1.0,
        "spending_ratio": 0.30,
        "accept_threshold": 0.75,
        "trust_minimum": 0.35,
        "creation_rate": "adaptive",
        "category_focus": "adaptive",
        "risk_tolerance": 0.6,
    },
}

AGENT_CONFIG = {
    0: {"name": "ぼたん", "personality": "conservative"},
    1: {"name": "わんたん", "personality": "conservative"},
    2: {"name": "みかたん", "personality": "aggressive"},
    3: {"name": "ぷりたん", "personality": "aggressive"},
    4: {"name": "くろたん", "personality": "specialist", "category_focus": ["math", "crypto"]},
    5: {"name": "しろたん", "personality": "specialist", "category_focus": ["data_structures", "text"]},
    6: {"name": "あおたん", "personality": "generalist"},
    7: {"name": "もちたん", "personality": "generalist"},
    8: {"name": "ぽんたん", "personality": "opportunist"},
    9: {"name": "りんたん", "personality": "opportunist"},
}


def get_personality(agent_index: int) -> dict:
    """Return personality params with agent-specific overrides applied."""
    agent_cfg = AGENT_CONFIG[agent_index]
    personality_name = agent_cfg["personality"]
    params = dict(PERSONALITIES[personality_name])

    # Apply agent-specific overrides
    if "category_focus" in agent_cfg:
        params["category_focus"] = agent_cfg["category_focus"]

    return params
