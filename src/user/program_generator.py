"""Template-based program generation for 8 categories.

Generates complete, runnable Python programs from templates with
randomized variants, complexity levels, and pricing.
"""

import json
import logging
import os
import random
import uuid

from .templates import TEMPLATES, COMPLEXITY_MULTIPLIERS

logger = logging.getLogger(__name__)

# Load base production costs from constants.json
_constants_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "constants.json"
)
try:
    with open(_constants_path) as _f:
        _constants = json.load(_f)
    BASE_PRODUCTION_COST = _constants.get("base_production_cost", {})
except Exception:
    BASE_PRODUCTION_COST = {}


class ProgramGenerator:
    """Generates programs based on agent personality."""

    def __init__(self, personality_params: dict):
        self.params = personality_params
        self._category_focus = personality_params.get("category_focus")
        self._production_categories = personality_params.get("production_categories")
        self._generated_count = 0

    def generate(self, category: str = None) -> dict:
        """Generate a program, optionally in a specific category.

        Returns dict with keys: uuid, name, category, complexity, source, price,
        production_cost, quality_score.
        Returns None if category is not in allowed production_categories.
        """
        # Determine allowed categories
        allowed = self._production_categories or list(TEMPLATES.keys())

        # Pick category (M1: only from allowed production_categories)
        if category and category in TEMPLATES and category in allowed:
            cat = category
        elif self._category_focus and self._category_focus != "adaptive":
            # Specialist: 70% chance of focused category (within allowed)
            focus_allowed = [c for c in (self._category_focus if isinstance(self._category_focus, list) else []) if c in allowed]
            if focus_allowed and random.random() < 0.7:
                cat = random.choice(focus_allowed)
            else:
                cat = random.choice(allowed)
        else:
            cat = random.choice(allowed)

        # Pick a template from the category
        templates = TEMPLATES[cat]
        template = random.choice(templates)

        # Pick a variant
        variant = random.choice(template["variants"])

        # Determine complexity
        complexity = random.choice(["simple", "medium", "complex"])

        # Build the program source
        source = self._build_source(template, variant, complexity)

        # Calculate price
        base_price = template.get("base_price", 100)
        price_mult = self.params.get("price_multiplier", 1.0)
        complexity_mult = COMPLEXITY_MULTIPLIERS.get(complexity, 1.0)
        price = max(10, int(base_price * price_mult * complexity_mult))

        # M3: Calculate production cost
        production_cost = self.calculate_production_cost(cat)

        # M5 (lite): Calculate initial quality_score
        quality_score = self._calculate_initial_quality(cat)

        # Generate name
        name = template["name_pattern"].format(variant=variant)

        program_uuid = str(uuid.uuid4())
        self._generated_count += 1

        return {
            "uuid": program_uuid,
            "name": name,
            "category": cat,
            "complexity": complexity,
            "source": source,
            "price": price,
            "production_cost": production_cost,
            "quality_score": quality_score,
        }

    def calculate_production_cost(self, category: str) -> int:
        """Calculate the production cost for a category based on personality.

        M3: base_production_cost[category] * personality multiplier.
        Specialist gets focus/other split.
        """
        base_cost = BASE_PRODUCTION_COST.get(category, 70)

        # Specialist has separate focus vs other multipliers
        if "production_cost_focus" in self.params:
            focus_cats = self._category_focus if isinstance(self._category_focus, list) else []
            if category in focus_cats:
                multiplier = self.params["production_cost_focus"]
            else:
                multiplier = self.params["production_cost_other"]
        else:
            multiplier = self.params.get("production_cost_multiplier", 1.0)

        return max(1, int(base_cost * multiplier))

    def _calculate_initial_quality(self, category: str) -> float:
        """Calculate initial quality_score for a newly produced program.

        M5 lite: Specialist focus categories get 0.9, others range 0.5-0.65.
        """
        # Specialist focus category -> high quality
        if "production_cost_focus" in self.params:
            focus_cats = self._category_focus if isinstance(self._category_focus, list) else []
            if category in focus_cats:
                return min(1.0, 0.9 * random.uniform(0.95, 1.05))

        # Personality-based base quality
        personality_quality = {
            1.2: 0.60,   # conservative price_multiplier -> decent quality
            0.8: 0.55,   # aggressive -> slightly lower (mass production)
            1.3: 0.50,   # specialist (non-focus, shouldn't happen often)
            1.0: 0.58,   # generalist / opportunist
        }
        price_mult = self.params.get("price_multiplier", 1.0)
        base_q = personality_quality.get(price_mult, 0.55)

        # Add small random variance
        return min(1.0, max(0.1, base_q * random.uniform(0.90, 1.10)))

    def _build_source(self, template: dict, variant: str, complexity: str) -> str:
        """Build source code from a template and variant."""
        skeleton = template["skeleton"]

        # Get body for this variant
        body = ""
        if "body_variants" in template:
            body = template["body_variants"].get(variant, "")

        # Get main body if available
        main_body = ""
        if "main_variants" in template:
            main_body = template["main_variants"].get(variant, "")

        # Get description if available
        description = ""
        if "descriptions" in template:
            description = template["descriptions"].get(variant, "")

        # Get limit if available (for fibonacci/factorial style templates)
        limit = 10
        if "limits" in template:
            limit = template["limits"].get(variant, 10)

        # Build the source using the skeleton
        source = skeleton.format(
            variant=variant,
            body=body,
            main_body=main_body,
            description=description,
            limit=limit,
        )

        return source

    @property
    def generated_count(self) -> int:
        return self._generated_count
