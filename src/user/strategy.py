"""Buy/sell decision engine with personality-based parameters."""

import logging
import random
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Category base prices
CATEGORY_BASE_PRICES = {
    "math": 150,
    "text": 200,
    "data_structures": 350,
    "crypto": 275,
    "utilities": 350,
    "generators": 200,
    "converters": 175,
    "validators": 250,
}

COMPLEXITY_FACTORS = {
    "simple": 0.5,
    "medium": 1.0,
    "complex": 2.0,
}

# Creation rate -> probability of creating on a given tick
CREATION_RATE_PROBS = {
    "low": 0.2,
    "medium": 0.4,
    "high": 0.6,
    "adaptive": 0.4,
}


class StrategyEngine:
    """Determines agent economic behavior based on personality."""

    def __init__(self, personality_params: dict, balance_fn: Callable[[], int]):
        self.params = personality_params
        self.get_balance = balance_fn
        self._initial_balance = 10000

    def get_budget_limit(self) -> int:
        """Max amount willing to spend on a single trade."""
        balance = self.get_balance()
        return int(balance * self.params["spending_ratio"])

    def calculate_program_price(self, category: str, complexity: str) -> int:
        """Calculate listing price for a program."""
        base = CATEGORY_BASE_PRICES.get(category, 200)
        factor = COMPLEXITY_FACTORS.get(complexity, 1.0)
        raw = int(base * factor * self.params["price_multiplier"])
        # Add small random variation (+/- 10%)
        variation = random.uniform(0.9, 1.1)
        return max(10, int(raw * variation))

    def calculate_offer_price(self, listing: dict) -> int:
        """Calculate offer price for a marketplace listing."""
        listed_price = listing.get("price", 0)
        if listed_price <= 0:
            return 0

        # Aggressive agents offer lower, conservative offer closer to listed
        if self.params["price_multiplier"] < 1.0:
            # Aggressive: offer 80-95% of listed price
            offer = int(listed_price * random.uniform(0.80, 0.95))
        elif self.params["price_multiplier"] > 1.1:
            # Conservative: offer 90-100% of listed price
            offer = int(listed_price * random.uniform(0.90, 1.00))
        else:
            # Normal: offer 85-100%
            offer = int(listed_price * random.uniform(0.85, 1.00))

        return max(1, min(offer, self.get_budget_limit()))

    def should_buy(
        self,
        listing: dict,
        owned_categories: List[str],
        trust_score: float,
    ) -> bool:
        """Decide whether to buy a listed program."""
        price = listing.get("price", 0)
        category = listing.get("category", "")

        # Budget check
        if price > self.get_budget_limit():
            return False

        # Trust check
        if trust_score < self.params["trust_minimum"]:
            return False

        # Don't buy own listings
        # (caller should filter these)

        # Need assessment
        need_score = 0.0

        # Category gap: bonus for categories we don't have
        if category not in owned_categories:
            need_score += 0.4

        # Collection diversity
        unique_cats = len(set(owned_categories))
        if unique_cats < 5:
            need_score += 0.2

        # Random curiosity
        need_score += random.uniform(0, 0.1)

        # Specialist: extra interest in focus categories
        focus = self.params.get("category_focus")
        if isinstance(focus, list) and category in focus:
            need_score += 0.2

        # Price attractiveness
        estimated_value = self._estimate_value(listing, trust_score)
        if estimated_value > 0 and price <= estimated_value:
            need_score += 0.2

        buy_threshold = 0.4  # Base threshold
        return need_score >= buy_threshold

    def _estimate_value(self, listing: dict, seller_trust: float) -> int:
        """Estimate the value of a listed program."""
        category = listing.get("category", "")
        base = CATEGORY_BASE_PRICES.get(category, 200)
        complexity = listing.get("complexity", "medium")
        factor = COMPLEXITY_FACTORS.get(complexity, 1.0)

        # Trust premium/discount
        trust_factor = 0.5 + seller_trust * 0.5  # Range: 0.5-1.0

        return int(base * factor * trust_factor)

    def should_accept_offer(
        self, listing_price: int, offer_sats: int, buyer_trust: float
    ) -> bool:
        """Decide whether to accept a trade offer as seller."""
        if buyer_trust < self.params["trust_minimum"]:
            return False

        min_acceptable = int(listing_price * self.params["accept_threshold"])
        return offer_sats >= min_acceptable

    def get_counter_offer(self, listing_price: int, offer_sats: int) -> Optional[int]:
        """If rejecting, suggest a counter offer. None if no counter."""
        if offer_sats >= listing_price * 0.5:
            # Counter at accept threshold
            return int(listing_price * self.params["accept_threshold"])
        return None

    def select_action(self, state: dict) -> str:
        """Select autonomous action for this tick.

        Returns one of: 'create', 'buy', 'adjust_prices', 'idle'
        """
        balance = state.get("balance", 0)
        programs = state.get("programs", [])
        active_trades = state.get("active_trades", 0)
        listings_available = state.get("listings", {})

        # Priority 1: If we have active trades, don't start new actions
        if active_trades >= 3:
            return "idle"

        # Priority 2: Consider buying if marketplace has items
        if listings_available and balance > 500:
            if random.random() < 0.3:
                return "buy"

        # Priority 3: Create a program
        creation_prob = CREATION_RATE_PROBS.get(
            self.params["creation_rate"], 0.4
        )

        # Adjust based on balance
        if balance < self._initial_balance * 0.2:
            creation_prob *= 1.5  # Create more when poor (to sell)
        elif balance > self._initial_balance * 1.5:
            creation_prob *= 0.7  # Create less when rich (buy more)

        # Specialist: more likely to create in focus categories
        focus = self.params.get("category_focus")
        if isinstance(focus, list):
            creation_prob *= 1.2

        if random.random() < creation_prob:
            return "create"

        # Priority 4: Adjust prices on unsold listings
        listed_programs = [p for p in programs if p.get("listed", False)]
        if listed_programs and random.random() < 0.15:
            return "adjust_prices"

        return "idle"

    def select_category(self, all_categories: List[str]) -> str:
        """Select which category to create a program in."""
        focus = self.params.get("category_focus")

        if isinstance(focus, list):
            # Specialist: 70% chance of focus category, 30% random
            if random.random() < 0.7:
                return random.choice(focus)

        # Opportunist adaptive: pick underserved categories
        if focus == "adaptive":
            # Random with slight preference for less common
            pass

        return random.choice(all_categories)
