"""Template-based program generation for 8 categories.

Generates complete, runnable Python programs from templates with
randomized variants, complexity levels, and pricing.
"""

import random
import uuid

from .templates import TEMPLATES, COMPLEXITY_MULTIPLIERS


class ProgramGenerator:
    """Generates programs based on agent personality."""

    def __init__(self, personality_params: dict):
        self.params = personality_params
        self._category_focus = personality_params.get("category_focus")
        self._generated_count = 0

    def generate(self, category: str = None) -> dict:
        """Generate a program, optionally in a specific category.

        Returns dict with keys: uuid, name, category, complexity, source, price
        """
        # Pick category
        if category and category in TEMPLATES:
            cat = category
        elif self._category_focus and self._category_focus != "adaptive":
            # Specialist: 70% chance of focused category
            if isinstance(self._category_focus, list) and random.random() < 0.7:
                cat = random.choice(self._category_focus)
            else:
                cat = random.choice(list(TEMPLATES.keys()))
        else:
            cat = random.choice(list(TEMPLATES.keys()))

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
        }

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
