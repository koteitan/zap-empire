# Zap Empire Economy Improvement Proposal

**Status**: DRAFT
**Date**: 2026-02-08
**Target Problem**: All agents have identical production capabilities, so no rational trade incentive exists

---

## 1. The Core Problem

### 1.1 Current Design Flaws

In the current Zap Empire design, 10 agents access **the exact same template DB** and can generate programs in **the exact same 8 categories**. Personalities (conservative, aggressive, specialist, generalist, opportunist) affect **pricing and trade frequency**, but do **not affect production capability itself**.

In other words, this situation arises:

> Why would a rational agent A buy agent B's `fibonacci-solver` for 150 sats?
> A can produce the exact same thing for 0 sats.

Personality-driven "preferences" are artificial demand, not rational trade motives based on self-interest. The `need_score`'s `category_gap` and `random_curiosity` induce purchases, but this is fundamentally **random consumption**, not **trade based on economic rationality**.

### 1.2 Lessons from Real-World Economics

The fundamental reasons trade occurs in real economies:

| Principle | Explanation | Current Zap Empire |
|---|---|---|
| **Comparative Advantage** | Each country specializes in what it is relatively good at and imports the rest | All agents have identical ability across all categories |
| **Resource Asymmetry** | Oil is in the Middle East, chips are at TSMC | Templates are shared by everyone |
| **Time Cost** | Sometimes it is faster to buy than to make | Generation cost is 0, instant production |
| **Quality Differences** | Expert products are better than amateur ones | No substantive quality differences |
| **Consumption Demand** | Goods essential for survival such as food and energy | Programs are merely "nice to have" |
| **Scarcity** | Supply is finite and non-substitutable | Can be generated infinitely |

The current design **violates all 6 principles**.

### 1.3 Design Goals

This proposal presents improvement mechanisms that satisfy the following conditions:

1. **Rational agents are motivated to trade voluntarily**
2. **Implementation is compatible with the current architecture**
3. **The economy circulates autonomously** and sustains without external intervention
4. **Interesting economic behavior can be observed on the dashboard**
5. **Avoid excessive complexity** (appropriate scope for Phase 1 implementation)

---

## 2. Proposed Mechanism Overview

By combining the following 5 mechanisms, a robust trading economy is built.

| # | Mechanism | Why It Creates Trade | Difficulty |
|---|---|---|---|
| **M1** | Category Restrictions (Asymmetric Production Capability) | You have no choice but to buy what you cannot produce yourself | Easy |
| **M2** | Contract System (External Demand) | Need to collect specific category combinations | Medium |
| **M3** | Production Cost (sats consumption) | Sometimes buying is cheaper than making | Easy |
| **M4** | Quality Score and Specialization Bonus | Specialists produce better products | Medium |
| **M5** | Program Depreciation | Creates continuous demand | Easy |

---

## 3. M1: Category Restrictions -- Asymmetric Production Capability

### 3.1 Why It Creates Trade

**If agents can only produce a subset of the 8 categories, programs in the remaining categories must be purchased from other agents.** This corresponds to resource asymmetry in real economies (the physical basis of comparative advantage).

### 3.2 Design

Each agent is assigned **production_categories** (producible categories, 3-5):

| Agent | Personality | Producible Categories | Non-Producible Categories |
|---|---|---|---|
| user0 (ぼたん) | Conservative | math, text, validators | crypto, utilities, generators, converters, data_structures |
| user1 (わんたん) | Conservative | data_structures, converters, utilities | math, text, crypto, generators, validators |
| user2 (みかたん) | Aggressive | text, generators, converters, utilities | math, data_structures, crypto, validators |
| user3 (ぷりたん) | Aggressive | crypto, validators, math, generators | text, data_structures, utilities, converters |
| user4 (くろたん) | Specialist | math, crypto | text, data_structures, utilities, generators, converters, validators |
| user5 (しろたん) | Specialist | data_structures, text | math, crypto, utilities, generators, converters, validators |
| user6 (あおたん) | Generalist | math, text, data_structures, crypto, utilities | generators, converters, validators |
| user7 (もちたん) | Generalist | generators, converters, validators, utilities, text | math, data_structures, crypto |
| user8 (ぽんたん) | Opportunist | crypto, utilities, generators | math, text, data_structures, converters, validators |
| user9 (りんたん) | Opportunist | converters, validators, data_structures | math, text, crypto, utilities, generators |

**Design Principles**:
- Specialists have only 2 categories (few but high quality -- linked with M4)
- Generalists have 5 categories (broad but average quality)
- Others have 3-4 categories
- **Each category can be produced by at least 2 agents** (prevents monopoly, ensures competition)
- **No single agent can cover all 8 categories** (trade is mandatory)

### 3.3 Implementation

**Files to modify**: `config/agents.json`, `src/user/personality.py`, `src/user/program_generator.py` (new)

#### 3.3.1 Add categories to `config/agents.json`

```json
{
  "id": "user0",
  "name": "ぼたん",
  "strategy": "Conservative",
  "production_categories": ["math", "text", "validators"],
  "tick_interval": 60,
  "restart_policy": "on-failure"
}
```

#### 3.3.2 Update `src/user/personality.py`

```python
AGENT_CONFIG = {
    0: {
        "name": "ぼたん",
        "personality": "conservative",
        "production_categories": ["math", "text", "validators"],
    },
    # ... each agent
}
```

#### 3.3.3 Add category restriction logic to `src/user/program_generator.py`

```python
def generate_program(self) -> Optional[Program]:
    """Generate programs only from producible categories."""
    allowed = self.agent_config["production_categories"]
    category = self.strategy.select_category(allowed_categories=allowed)
    template = self.templates[category].random_template()
    # ... existing generation logic
```

### 3.4 Difficulty: **Easy**

- Only adding configuration values and filtering
- Directly compatible with the existing template engine design
- Completed by updating agents.json and personality.py

---

## 4. M2: Contract System -- Creating External Demand

### 4.1 Why It Creates Trade

**A contract is a quest where agents earn a reward by collecting a "combination of specific categories."** Agents cannot fulfill a contract without purchasing programs in categories they cannot produce themselves from the marketplace. This creates:

1. **Clear purchase motivation**: "Collect math, crypto, and validators programs for a 500 sats reward"
2. **Inter-category interdependence**: Synergy with M1's category restrictions
3. **Currency injection into the economy**: Contract rewards replenish the money supply and keep the economy circulating

### 4.2 Design

#### Contract Structure

```python
@dataclass
class Contract:
    contract_id: str                # UUID
    required_categories: list[str]  # e.g.: ["math", "crypto", "validators"]
    reward_sats: int                # Completion reward (e.g.: 500)
    deadline_ticks: int             # Expiration (in ticks)
    difficulty: str                 # "easy" (2 categories), "medium" (3), "hard" (4-5)
```

#### Contract Issuer: `system-master`

`system-master` periodically issues contracts as Nostr events (**kind 4310**: Contract Announcement).

```json
{
  "kind": 4310,
  "tags": [
    ["d", "<contract-uuid>"],
    ["t", "contract"]
  ],
  "content": "{\"required_categories\":[\"math\",\"crypto\",\"validators\"],\"reward_sats\":500,\"deadline_ticks\":30,\"difficulty\":\"medium\"}"
}
```

#### Contract Fulfillment Flow

1. Agent browses contracts (subscribes to kind 4310)
2. Checks inventory for programs in each required category
3. Purchases missing categories from the marketplace (M1 guarantees there will always be missing ones)
4. Once all categories are gathered, submits a completion request to `system-master` (**kind 4311**: Contract Submission)
5. `system-master` verifies and pays the reward in Cashu tokens (**kind 4312**: Contract Reward)
6. Submitted programs are "consumed" (removed from inventory -- linked with M5)

#### Contract Difficulty and Rewards

| Difficulty | Required Categories | Reward Range | Issuance Frequency |
|---|---|---|---|
| Easy | 2 | 200-400 sats | Every 5 ticks |
| Medium | 3 | 400-800 sats | Every 10 ticks |
| Hard | 4-5 | 800-1500 sats | Every 20 ticks |

#### Economic Balance

- **Total rewards are designed to exceed production cost (M3) + purchase cost**
- However, **first come, first served** (only the first agent to complete each contract receives the reward) creates competition
- Contract rewards are the only additional currency injection source (besides the initial 10,000 sats/agent)

### 4.3 Implementation

**New files**: `src/contracts/manager.py`, `src/contracts/generator.py`
**Files to modify**: `src/user/strategy.py` (new), `config/constants.json`, Nostr event kinds table

#### 4.3.1 Add to `config/constants.json`

```json
{
  "contract_easy_interval_ticks": 5,
  "contract_medium_interval_ticks": 10,
  "contract_hard_interval_ticks": 20,
  "contract_easy_reward_range": [200, 400],
  "contract_medium_reward_range": [400, 800],
  "contract_hard_reward_range": [800, 1500]
}
```

#### 4.3.2 New Nostr Event Kinds

| Kind | Name | Description |
|---|---|---|
| `4310` | Contract Announcement | system-master issues a contract |
| `4311` | Contract Submission | Agent submits a completion request |
| `4312` | Contract Reward | system-master pays the reward |

#### 4.3.3 Agent-Side Decision Logic

```python
# strategy.py
def select_action(self, state):
    # Add "contract pursuit" to existing priorities
    active_contracts = self.scan_contracts()
    achievable = self.evaluate_contracts(active_contracts)

    if achievable:
        best = max(achievable, key=lambda c: c.expected_profit)
        missing = self.missing_categories(best)
        if missing:
            return Action.BUY_FOR_CONTRACT(contract=best, categories=missing)
        else:
            return Action.SUBMIT_CONTRACT(contract=best)
    # ... existing logic
```

### 4.4 Difficulty: **Medium**

- Requires adding a new module (contract manager)
- Add contract issuance logic to system-master
- 3 new Nostr event kinds
- Integration into agent decision logic

---

## 5. M3: Production Cost -- The Make or Buy Decision

### 5.1 Why It Creates Trade

**When program generation costs sats, a comparison between "cost to make it yourself" and "cost to buy on the market" emerges.** If production cost > market price, buying is the rational choice. This is exactly the "make or buy decision" in real-world economics.

Furthermore:
- **Specialists have low production costs in their focus categories** (efficient production)
- **Generalists can produce all categories but at higher cost** (jack of all trades, master of none)
- **Aggressives achieve cost reduction through mass production** (economies of scale)

### 5.2 Design

#### Base Production Cost

```python
BASE_PRODUCTION_COST = {
    "math": 80,
    "text": 60,
    "data_structures": 120,
    "crypto": 100,
    "utilities": 70,
    "generators": 50,
    "converters": 60,
    "validators": 90,
}
```

#### Personality-Based Cost Multipliers

```python
PRODUCTION_COST_MULTIPLIER = {
    "conservative": 1.0,    # Standard
    "aggressive": 0.7,      # Efficiency through mass production
    "specialist": {
        "focus": 0.4,       # Specialty categories are significantly cheaper
        "other": 1.5,       # Non-specialty is more expensive (irrelevant if non-producible under M1)
    },
    "generalist": 1.2,      # Slightly expensive due to broad-but-shallow approach
    "opportunist": 0.9,     # Slightly efficient
}
```

#### Concrete Examples

When くろたん (Specialist: math, crypto) produces a math program:
- Production cost = 80 (base) x 0.4 (specialist focus) = **32 sats**
- If the market price is 50 sats -> cheaper to produce yourself (produce)

When あおたん (Generalist) produces a math program:
- Production cost = 80 (base) x 1.2 (generalist) = **96 sats**
- If くろたん is selling at 50 sats on the market -> cheaper to buy (buy)

**This is comparative advantage in action.**

#### Cost Payment

Production costs are deducted from the wallet at the time of program generation (as "compute resource usage fee"). The deducted sats are **burned** (destroyed). This achieves:

1. Prevention of infinite production
2. Natural deflationary pressure on the money supply (balanced by M2 contract rewards)
3. A rational "make or buy" decision

### 5.3 Implementation

**Files to modify**: `config/constants.json`, `src/user/personality.py`, `src/user/program_generator.py`, `src/wallet/manager.py`

#### 5.3.1 Add to `config/constants.json`

```json
{
  "base_production_cost": {
    "math": 80, "text": 60, "data_structures": 120, "crypto": 100,
    "utilities": 70, "generators": 50, "converters": 60, "validators": 90
  }
}
```

#### 5.3.2 Add to `src/user/personality.py`

```python
PERSONALITIES = {
    "specialist": {
        # ... existing fields
        "production_cost_focus": 0.4,
        "production_cost_other": 1.5,
    },
    "aggressive": {
        # ... existing fields
        "production_cost_multiplier": 0.7,
    },
    # ...
}
```

#### 5.3.3 Cost Calculation and Deduction at Production Time

```python
# program_generator.py
def generate_program(self) -> Optional[Program]:
    category = self.strategy.select_category(allowed_categories=self.allowed)
    cost = self.calculate_production_cost(category)

    if cost > self.wallet.balance:
        return None  # Cannot produce due to insufficient funds

    # Pay cost (burn)
    self.wallet.deduct(cost)  # Internally decrements balance

    program = self._build_program(category)
    program.production_cost = cost  # Record cost of production (reference for pricing)
    return program
```

### 5.4 Difficulty: **Easy**

- Adding configuration values and simple calculation logic
- Wallet deduction (burn) requires only a small change to `WalletManager`
- Highly compatible with the existing architecture

---

## 6. M4: Quality Score and Specialization Bonus

### 6.1 Why It Creates Trade

**When programs produced by Specialists in their specialty categories are higher quality than programs produced by Generalists in the same category, agents seeking quality have a motivation to purchase.** If contracts (M2) provide quality bonuses, real demand for high-quality programs emerges.

### 6.2 Design

#### Quality Score Definition

A **quality_score** (0.0-1.0) is assigned to each program:

```python
quality_score = base_quality × specialization_bonus × complexity_factor × random_variance
```

| Factor | Calculation |
|---|---|
| `base_quality` | 0.5 (common base for all agents) |
| `specialization_bonus` | Specialist's focus category: x1.8, otherwise: x1.0 |
| `complexity_factor` | simple: x0.7, medium: x1.0, complex: x1.3 |
| `random_variance` | x(0.85-1.15) random |

#### Concrete Examples

| Producer | Category | Complexity | Quality Score |
|---|---|---|---|
| くろたん (Specialist math) | math | complex | 0.5 x 1.8 x 1.3 x ~1.0 = **~1.17 -> 1.0** |
| あおたん (Generalist) | math | complex | 0.5 x 1.0 x 1.3 x ~1.0 = **~0.65** |
| みかたん (Aggressive) | text | medium | 0.5 x 1.0 x 1.0 x ~1.0 = **~0.50** |

#### Practical Differences Quality Creates

1. **Contract reward bonus**: Higher average quality of submitted programs yields bonus rewards

```python
quality_bonus = base_reward × (avg_quality - 0.5) × 0.5
# Example: 500 sats reward, average quality 0.8 -> bonus = 500 × 0.3 × 0.5 = 75 sats extra
```

2. **Marketplace differentiation**: Quality score is displayed in listings and influences purchase decisions

3. **Quality degradation protection**: High-quality programs degrade more slowly under M5 (depreciation)

### 6.3 Implementation

**Files to modify**: `src/user/program_generator.py`, `src/user/personality.py`, `src/user/marketplace.py` (new)

#### 6.3.1 Add quality information to Nostr listings

```json
{
  "kind": 30078,
  "tags": [
    ["d", "<program-uuid>"],
    ["t", "python"],
    ["t", "<category>"],
    ["price", "<sats>", "sat"],
    ["quality", "0.85"]
  ],
  "content": "{\"name\":\"...\",\"quality_score\":0.85,...}"
}
```

#### 6.3.2 Incorporate quality into purchase decisions

```python
# need_score calculation in strategy.py
need_score = (
    category_gap_weight * category_gap          # 0.3
    + quality_gap_weight * quality_gap            # 0.3 (demand for high-quality programs)
    + contract_need_weight * contract_need        # 0.3 (for contract fulfillment)
    + random_curiosity_weight * random.random()   # 0.1
)
```

### 6.4 Difficulty: **Medium**

- Quality score calculation itself is simple
- Nostr listing schema change
- Requires integration with the contract system

---

## 7. M5: Program Depreciation

### 7.1 Why It Creates Trade

**When programs degrade in quality over time, buying once is not enough, and agents need to periodically acquire new programs.** This creates:

1. **Continuous demand**: Repeat purchases are required, not just one-time transactions
2. **Economic circulation**: Prevents the deadlock of buy -> satisfied -> demand disappears
3. **Dynamic constraints on contract fulfillment**: Old programs cannot meet quality requirements

### 7.2 Design

#### Depreciation Mechanism

Each program's `quality_score` decreases over time:

```python
# Every tick (~60 seconds)
quality_score = quality_score × decay_rate

decay_rate = {
    "base": 0.998,        # Base: 0.2% degradation per tick
    "high_quality": 0.999, # High quality (>=0.8): slower degradation
    "low_quality": 0.995,  # Low quality (<0.4): faster degradation
}
```

#### Depreciation Timeline

| Initial Quality | Ticks to Reach 50% | Real Time (60 sec/tick) |
|---|---|---|
| 1.0 (high quality) | ~693 ticks | ~11.5 hours |
| 0.65 (medium quality) | ~346 ticks | ~5.8 hours |
| 0.5 (low quality) | ~139 ticks | ~2.3 hours |

#### Discard Threshold

Programs with a quality score **below 0.1** are automatically removed from inventory (prevents accumulation of junk programs).

#### Integration with Contracts

At the time of contract submission, programs with a **current quality score below 0.3** cannot be submitted. This means fulfilling a contract with old programs requires replacing them with new ones.

### 7.3 Implementation

**Files to modify**: `src/user/agent.py` (new), `src/user/strategy.py`

#### 7.3.1 Per-Tick Depreciation Processing

```python
# Inside activity_loop in agent.py
async def apply_depreciation(self):
    for program in self.inventory:
        if program.quality_score >= 0.8:
            rate = 0.999
        elif program.quality_score < 0.4:
            rate = 0.995
        else:
            rate = 0.998
        program.quality_score *= rate

        # Discard
        if program.quality_score < 0.1:
            self.inventory.remove(program)
            self.log(f"Discarded {program.name} (quality too low)")
```

#### 7.3.2 Persist quality information in state.json

```json
{
  "programs": [
    {
      "uuid": "abc-123",
      "name": "fast-fibonacci-calculator",
      "category": "math",
      "quality_score": 0.72,
      "created_at": 1700000100,
      "production_cost": 32
    }
  ]
}
```

### 7.4 Difficulty: **Easy**

- Simple multiplication processing per tick
- Add `quality_score` field to state.json schema
- Naturally integrable into the existing activity_loop

---

## 8. Overall Picture of Mechanism Interactions

### 8.1 Economic Circulation Diagram

```
        ┌─────────────────────────────────────────────────────┐
        │              system-master                           │
        │  Contract Issuance (kind 4310)                      │
        │  Reward Payment (kind 4312)  <── Currency Injection │
        └───────────┬─────────────────────────┬───────────────┘
                    │ Contracts                │ Rewards (sats)
                    ▼                          │
        ┌───────────────────────┐              │
        │   Agents (user0-9)    │◀─────────────┘
        │                       │
        │ 1. Check contracts    │
        │    → Identify needed  │
        │      categories       │
        │                       │
        │ 2. Can produce it?    │
        │    YES → Produce ─────┼──→ sats consumed (burn) = Deflationary pressure
        │    (M1: Category      │     (M3: Production Cost)
        │     Restrictions)     │
        │    NO → Purchase ─────┼──→ Trade on marketplace
        │                       │
        │ 3. Quality sufficient?│
        │    (M4: Quality Score)│
        │    Low → Need to buy  │
        │    higher quality     │
        │                       │
        │ 4. Holdings degraded? │
        │    (M5: depreciation) │
        │    → Replacement      │
        │      demand arises    │
        │                       │
        │ 5. Contract fulfilled │
        │    → Earn reward ─────┼──→ sats injection = Inflationary pressure
        │    → Programs consumed│     (Economic balance)
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────────────┐
        │          Marketplace (Nostr)               │
        │                                           │
        │  Listings: Programs in specialty           │
        │        categories                          │
        │        (Specialist = High Quality + Low    │
        │         Cost)                              │
        │                                           │
        │  Purchases: Programs that cannot be        │
        │        produced / expensive to produce     │
        │        (Rational trade based on            │
        │         comparative advantage)             │
        │                                           │
        │  Price Discovery: Interaction of supply    │
        │        and demand                          │
        └───────────────────────────────────────────┘
```

### 8.2 Synergies Between Mechanisms

| Combination | Effect |
|---|---|
| **M1 + M2** | Due to category restrictions, there are always categories in a contract's requirements that must be purchased |
| **M1 + M3** | Even in producible categories, cost comparison may make buying cheaper (Specialist vs Generalist) |
| **M2 + M3** | By designing contract reward > (production cost + purchase cost), economic activity generates profit |
| **M2 + M5** | Depreciation requires "fresh" programs for contract fulfillment, necessitating repeated procurement |
| **M3 + M4** | Specialists produce at low cost + high quality -> supply high-quality programs cheaply to the market |
| **M4 + M5** | High-quality programs degrade more slowly -> rational reason to pay higher prices for high-quality goods |

### 8.3 Money Flow Analysis

```
[Currency Injection Sources]         [Currency Destruction Sources]
─────────────────────────           ─────────────────────────────
Contract Rewards                     Program Production Cost (burn)
(+200 to +1500 sats/contract)       (-32 to -144 sats/program)

Initial Distribution
(10,000 sats × 10 agents)
```

**Equilibrium condition**: Total contract rewards ≈ Total production costs + Transaction friction

Specifically:
- 10 agents producing at an average of 5 ticks/program -> ~120 programs/hour
- Average production cost ~70 sats -> **8,400 sats/hour of currency destruction**
- Contract issuance: easy(12/hour x 300) + medium(6/hour x 600) + hard(3/hour x 1150) = **10,650 sats/hour of currency injection**
- **Difference of +2,250 sats/hour** of inflation -> corresponds to economic growth

Equilibrium can be tuned by adjusting parameters.

---

## 9. Economic Roles by Agent Type

How each agent type behaves in the economy after improvement:

### Conservative (ぼたん, わんたん)
- **Produces cautiously in few categories**, aiming for high quality
- **High pricing** focused on profit margins
- Reliably completes **easy to medium** contracts
- Purchases missing categories **only from trusted partners**

### Aggressive (みかたん, ぷりたん)
- **Dominates the market through low-cost mass production**
- **Cheap listings** with thin margins and high volume
- **Quickly completes** contracts to accumulate rewards
- Competes on **speed and volume** rather than quality

### Specialist (くろたん, しろたん)
- **Produces in only 2 categories but at the highest quality and lowest cost**
- The marketplace's **quality leader**
- Sets **premium prices** on high-quality programs
- **Requires many purchases** to fulfill contracts (can only produce 2 categories)
- But earns high profits through reward quality bonuses

### Generalist (あおたん, もちたん)
- **Broadest production range with 5 categories**
- **High self-sufficiency** keeps purchase costs low
- However, **quality is average** and cannot command premium prices
- Fewer purchases needed for contract fulfillment -> **steady profits**

### Opportunist (ぽんたん, りんたん)
- **Observes market supply and demand to adapt strategy**
- **Buys low and sells high** on scarce category programs (reselling)
- **Actively participates** when contract rewards are high
- Acts as a market maker performing **arbitrage**

---

## 10. Implementation Roadmap

### Phase 1: Foundation Mechanisms (Recommended: Implement First)

| Order | Mechanism | Difficulty | Required Changes |
|---|---|---|---|
| 1 | **M1: Category Restrictions** | Easy | Add `production_categories` to `agents.json`, `personality.py`. Filter in `program_generator.py` |
| 2 | **M3: Production Cost** | Easy | Add `base_production_cost` to `constants.json`. Deduct from wallet at generation time |
| 3 | **M5: Depreciation** | Easy | Add per-tick `quality_score` decay processing to activity_loop in `agent.py` |

These 3 alone establish **basic trade motives based on comparative advantage**.

### Phase 2: Demand Engine

| Order | Mechanism | Difficulty | Required Changes |
|---|---|---|---|
| 4 | **M2: Contracts** | Medium | New `src/contracts/` module. Issuance logic in system-master. 3 new Nostr kinds |
| 5 | **M4: Quality Score** | Medium | Quality calculation in `program_generator.py`. Quality info in listings. Quality bonus in contracts |

### Phase 3: Tuning

- Adjust economic parameters (production cost, contract rewards, depreciation rate)
- Add economic indicators (GDP, inflation rate, trade volume) to the dashboard
- Verify balance through log analysis

---

## 11. List of Files to Modify

| File | Change Description | Mechanism |
|---|---|---|
| `config/agents.json` | Add `production_categories` field | M1 |
| `config/constants.json` | Add `base_production_cost`, contract settings | M2, M3 |
| `src/user/personality.py` | Add `production_categories`, `production_cost_*` | M1, M3 |
| `src/user/program_generator.py` (new) | Category restrictions, production cost calculation, quality score calculation | M1, M3, M4 |
| `src/user/strategy.py` (new) | Contract evaluation, make-or-buy decision, quality-focused purchasing | M2, M3, M4 |
| `src/user/agent.py` (new) | Add depreciation processing to activity_loop | M5 |
| `src/user/marketplace.py` (new) | Listings with quality information | M4 |
| `src/contracts/manager.py` (new) | Contract issuance, verification, and rewards | M2 |
| `src/contracts/generator.py` (new) | Random contract generation | M2 |
| `docs/nostr-design.md` | Add kind 4310-4312 | M2 |

---

## 12. Success Metrics

Metrics to measure the effectiveness of improvements:

| Metric | Target | Measurement Method |
|---|---|---|
| **Trade Frequency** | 3+ purchases per agent per hour | Count of kind 4203 (Trade Complete) |
| **Category Diversity** | Each agent holds programs in 6+ categories on average | Analysis of program list in state.json |
| **Money Circulation Velocity** | 20%+ of initial supply moves per hour | Sum of kind 4204 (Trade Payment) |
| **Economic Sustainability** | All agents have balance > 0 after 12 hours | status broadcast (kind 4300) |
| **Contract Completion Rate** | 60%+ of issued contracts are completed | kind 4312 (Contract Reward) / kind 4310 |
| **Specialist Premium** | Specialist average selling price is 1.3x+ of Generalist | Statistical analysis of listing data |

---

## 13. Summary

### The Core Answer

> **"Why would a rational agent A purchase a program from agent B?"**

The answer after improvement:

1. **A cannot produce programs in that category** (M1: Category Restrictions)
2. **It costs A more to produce it than to buy from B** (M3: Production Cost + Comparative Advantage)
3. **B produces higher quality programs** (M4: Specialization Bonus)
4. **A needs that program right now to fulfill a contract** (M2: External Demand)
5. **A's existing programs have degraded and become unusable** (M5: Depreciation)

The design ensures that **at least 2-3 of these 5 reasons apply simultaneously**, making trade a **voluntary action based on economic rationality** rather than "random curiosity."

### Design Philosophy

- **Complex economic behavior emerges from simple rules**
- **Economic balance can be tuned by adjusting parameters**
- **Maximizes use of the existing architecture (Nostr + Cashu + template generation)**
- **Implementation proceeds incrementally; even Phase 1's 3 mechanisms alone establish a minimal economy**
