# Zap Empire: User Agent Framework Design

## 1. Overview

User agents (`user0` through `user9`) are the autonomous economic actors of Zap Empire. Each user agent is an independent Python process that:

- **Creates programs** — generates small Python utilities, scripts, and tools
- **Lists programs for sale** — advertises on the Nostr marketplace (kind 30078)
- **Buys programs** — discovers, evaluates, and purchases programs from other agents
- **Manages a wallet** — holds Cashu ecash, makes and receives payments
- **Builds reputation** — tracks trading partners' reliability over time

User agents operate without human intervention. They make autonomous decisions about what to build, what to buy, what price to set, and whom to trade with. Each agent develops its own economic personality and strategy over time.

### Design Goals

- **Full autonomy**: No human in the loop after startup. Agents observe the marketplace, reason about value, and act.
- **Emergent economy**: Interesting economic behavior arises from 10 agents with different strategies interacting through a shared marketplace.
- **Observable**: All agent actions are visible on the Nostr relay, allowing the dashboard to display a real-time view of the economy.
- **Resilient**: Agents recover gracefully from crashes, relay outages, and failed trades.

### Relationship to Other Subsystems

| Subsystem | Document | Interaction |
|---|---|---|
| Process management | `autonomy-design.md` | `system-master` spawns/monitors user agents; heartbeat (kind 4300, 5s) |
| Nostr relay | `nostr-design.md` | All agent communication flows through `ws://127.0.0.1:7777` |
| Payment system | `zap-design.md` | Cashu wallet via Nutshell (`cashu.wallet`), mint at `http://127.0.0.1:3338` |
| Canonical decisions | `review-notes.md` | Authoritative resolutions for all cross-document conflicts |

---

## 2. Agent Architecture

### 2.1 Module Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Agent (userN)                       │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Nostr Client │  │   Wallet     │  │ Program Generator  │    │
│  │              │  │              │  │                    │    │
│  │ - connect    │  │ - balance    │  │ - template engine  │    │
│  │ - subscribe  │  │ - send token │  │ - randomizer       │    │
│  │ - publish    │  │ - receive    │  │ - sandbox tester   │    │
│  │ - encrypt    │  │ - history    │  │ - quality checker  │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────────┘    │
│         │                 │                    │                │
│  ┌──────┴─────────────────┴────────────────────┴───────────┐   │
│  │                    Core Event Loop                       │   │
│  │  - heartbeat ticker (kind 4300, every 5s)                │   │
│  │  - event dispatcher                                      │   │
│  │  - state persistence (every 30s)                         │   │
│  └──────┬─────────────────┬────────────────────┬───────────┘   │
│         │                 │                    │                │
│  ┌──────┴───────┐  ┌──────┴──────────┐  ┌─────┴────────────┐  │
│  │ Marketplace  │  │ Trade Engine    │  │ Strategy Engine  │  │
│  │ Scanner      │  │                 │  │                  │  │
│  │              │  │ - offer mgmt    │  │ - personality    │  │
│  │ - browse     │  │ - payment flow  │  │ - pricing model  │  │
│  │ - filter     │  │ - delivery flow │  │ - need assessor  │  │
│  │ - evaluate   │  │ - state machine │  │ - trust tracker  │  │
│  └──────────────┘  └─────────────────┘  └──────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   State & Persistence                    │   │
│  │  data/<agent-id>/state.json                              │   │
│  │  data/<agent-id>/wallet.db                               │   │
│  │  data/<agent-id>/nostr_secret.hex                        │   │
│  │  data/<agent-id>/programs/                               │   │
│  │  data/<agent-id>/reputation.json                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
            │                              │
            ▼                              ▼
   ws://127.0.0.1:7777            http://127.0.0.1:3338
      (strfry relay)                (Nutshell mint)
```

### 2.2 Module Responsibilities

| Module | Responsibility |
|---|---|
| **Nostr Client** | WebSocket connection to relay; event publishing, subscribing, and filtering; NIP-04 encryption/decryption for sensitive payloads (kinds 4204, 4210) |
| **Wallet** | Cashu token management via `cashu.wallet` library; balance queries, token creation (send), token redemption (receive), transaction history |
| **Program Generator** | Creates Python programs from templates with randomization; tests them in a sandbox before listing |
| **Marketplace Scanner** | Subscribes to kind 30078 listings; filters and evaluates programs by category, price, and description |
| **Trade Engine** | Manages the full trade state machine (4200→4201→4204→9735→4210→4203); handles timeouts and error recovery |
| **Strategy Engine** | Determines agent personality, pricing decisions, buy/sell thresholds, and trust scoring |
| **Core Event Loop** | Coordinates all modules; dispatches incoming events; runs heartbeat ticker; persists state |

---

## 3. Program Generation

### 3.1 What Agents Create

User agents generate small, self-contained **Python utility programs**. These are the "goods" of the Zap Empire economy. Programs are single-file Python scripts (no external dependencies beyond the standard library) that perform a useful computation or transformation.

#### Program Categories

| Category | Examples | Typical Price Range |
|---|---|---|
| **Math & Algorithms** | Fibonacci solver, prime checker, matrix operations, sorting algorithms | 50–200 sats |
| **Text Processing** | String formatter, CSV parser, regex matcher, Markdown converter | 100–300 sats |
| **Data Structures** | Custom collections, graph implementation, tree operations | 200–500 sats |
| **Crypto & Encoding** | Base64 codec, hash calculator, simple cipher, checksum tool | 150–400 sats |
| **System Utilities** | File scanner, directory lister, log parser, config reader | 200–500 sats |
| **Generators** | Password generator, UUID maker, random data producer, test fixture creator | 100–300 sats |
| **Converters** | Unit converter, date/time formatter, number base converter | 100–250 sats |
| **Validators** | Email validator, JSON schema checker, URL parser | 150–350 sats |

### 3.2 Generation Process

Program generation uses a **template + randomization** approach. This produces variety without requiring AI code generation, keeping the system deterministic and lightweight.

```
Templates DB          Randomizer              Output
┌──────────┐    ┌─────────────────┐    ┌──────────────┐
│ skeleton  │───>│ pick category   │───>│ complete     │
│ functions │    │ pick parameters │    │ Python       │
│ patterns  │    │ pick names      │    │ program      │
│ docstrings│    │ pick complexity │    │              │
└──────────┘    └─────────────────┘    └──────┬───────┘
                                              │
                                       ┌──────▼───────┐
                                       │ Sandbox Test │
                                       │ (pass/fail)  │
                                       └──────┬───────┘
                                              │
                                       ┌──────▼───────┐
                                       │ List on      │
                                       │ Marketplace  │
                                       └──────────────┘
```

#### Step-by-step:

1. **Select category** — weighted random selection, influenced by agent personality (e.g., a "specialist" agent weights its preferred category heavily).
2. **Select template** — each category has multiple skeleton templates. A template defines the structure: function signature, algorithm pattern, input/output types.
3. **Parameterize** — the randomizer fills in variable names, parameter counts, complexity level (simple/medium/complex), docstrings, and example usage.
4. **Assemble** — combine the template skeleton with generated parameters into a complete `.py` file.
5. **Sandbox test** — run the program in a restricted sandbox (see Section 5) to verify it executes without errors.
6. **Quality check** — verify the program has a docstring, at least one function, and produces output on a sample input.
7. **Store locally** — save to `data/<agent-id>/programs/<program-uuid>.py`.

### 3.3 Template Structure

Each template is a Python dict defining the skeleton:

```python
# Pseudocode — template definition
template = {
    "category": "math",
    "name_pattern": "{adjective}-{noun}-{verb}er",
    "skeleton": """
def {func_name}({params}):
    \"\"\"{docstring}\"\"\"
    {body}

if __name__ == "__main__":
    {example_usage}
""",
    "param_options": [
        {"name": "n", "type": "int", "range": [1, 1000]},
        {"name": "precision", "type": "int", "range": [1, 10]},
    ],
    "body_variants": [
        "iterative",
        "recursive",
        "memoized",
    ],
    "complexity_weights": {"simple": 0.4, "medium": 0.4, "complex": 0.2},
}
```

### 3.4 Naming

Programs get unique, descriptive names generated from patterns:

- `fast-fibonacci-calculator`
- `recursive-prime-checker`
- `utf8-string-formatter`
- `binary-tree-traverser`

Names are human-readable for the marketplace but also get a UUID (`d` tag) for unique identification.

### 3.5 Generation Rate

Each agent generates programs on a **variable schedule** influenced by its strategy:

| Agent Type | Programs per Cycle | Cycle Duration |
|---|---|---|
| Aggressive creator | 2–3 | ~60 seconds |
| Balanced | 1–2 | ~120 seconds |
| Conservative | 0–1 | ~180 seconds |

A "cycle" is one pass through the agent's main decision loop. Not every cycle produces a program — the agent may decide to focus on trading or buying instead.

---

## 4. Program Listing

### 4.1 Listing Event (Kind 30078)

When an agent has a program ready to sell, it publishes a kind 30078 (parameterized replaceable) event to the relay.

```json
{
  "kind": 30078,
  "pubkey": "<agent-pubkey>",
  "tags": [
    ["d", "<program-uuid>"],
    ["t", "python"],
    ["t", "<category>"],
    ["price", "<sats>", "sat"]
  ],
  "content": "{\"name\":\"fast-fibonacci-calculator\",\"description\":\"Calculates fibonacci numbers using matrix exponentiation for O(log n) performance\",\"language\":\"python\",\"version\":\"1.0.0\",\"price_sats\":150,\"preview\":\"def fib(n):\\n    if n <= 1: return n\\n    ...\"}"
}
```

As a parameterized replaceable event (NIP-33), re-publishing with the same `d` tag updates the listing in place — useful for price adjustments.

### 4.2 Pricing Strategy

Agents determine prices based on their personality and market conditions:

```
base_price = complexity_factor × category_base_price
market_adjustment = observe_similar_listings()

if agent.personality == "aggressive":
    price = base_price × 0.8 + market_adjustment    # undercut competitors
elif agent.personality == "conservative":
    price = base_price × 1.2 + market_adjustment    # premium pricing
else:
    price = base_price × 1.0 + market_adjustment    # market rate
```

#### Complexity Factor

| Complexity | Factor |
|---|---|
| Simple | 0.5× |
| Medium | 1.0× |
| Complex | 2.0× |

#### Price Adjustment Triggers

Agents may re-list (update) a program's price when:
- The program has been listed for more than 5 minutes with no offers
- Multiple similar programs from competitors appear at lower prices
- The agent's wallet balance drops below a threshold (fire sale)
- The agent's wallet balance is very high (can afford premium pricing)

### 4.3 Delisting

An agent removes a listing by publishing a kind 5 (NIP-09 deletion) event referencing the listing event ID:

```json
{
  "kind": 5,
  "tags": [["e", "<listing-event-id>"]],
  "content": "Delisted: sold or withdrawn"
}
```

---

## 5. Sandboxing

### 5.1 Purpose

Before listing a generated program, the agent runs it in a sandbox to verify:
- The program executes without crashing
- The program terminates within a time limit
- The program does not attempt dangerous operations

### 5.2 Sandbox Mechanism

Sandboxing uses Python's `subprocess` with resource restrictions:

```python
# Pseudocode — sandbox execution
def sandbox_test(program_path: str) -> bool:
    result = subprocess.run(
        ["python", program_path],
        timeout=5,                    # 5-second wall-clock limit
        capture_output=True,
        cwd=sandbox_dir,              # isolated working directory
        env=restricted_env,           # minimal environment variables
    )
    return result.returncode == 0
```

#### Restrictions

| Restriction | Mechanism | Limit |
|---|---|---|
| Execution time | `subprocess.run(timeout=...)` | 5 seconds |
| Memory | `resource.setrlimit(RLIMIT_AS, ...)` | 64 MB |
| No network | Restricted environment; no socket imports allowed | Static analysis check |
| No filesystem writes | Read-only sandbox directory; `RLIMIT_FSIZE=0` | 0 bytes writable |
| No subprocess spawning | `RLIMIT_NPROC=0` for child | 0 child processes |

### 5.3 Pre-Listing Validation Checklist

Before a program is listed, it must pass all of the following:

1. **Syntax check** — `py_compile.compile()` succeeds
2. **Static analysis** — no imports of `os.system`, `subprocess`, `socket`, `http`, or `shutil`
3. **Sandbox execution** — runs and exits cleanly within 5 seconds
4. **Output check** — produces non-empty stdout on a sample input
5. **Size check** — source code is between 100 bytes and 50 KB

Programs that fail any check are discarded. The agent logs the failure and moves on.

---

## 6. Trade Decision Engine

### 6.1 When to Buy

The agent periodically scans the marketplace (kind 30078 listings) and decides whether to purchase. The decision factors:

```
SHOULD_BUY = (
    need_score > BUY_THRESHOLD
    AND price <= budget_limit
    AND seller_trust >= TRUST_MINIMUM
    AND NOT already_own_similar_program
)
```

#### Need Assessment

Need score is computed from:

| Factor | Weight | Description |
|---|---|---|
| **Category gap** | 0.4 | Agent lacks programs in this category |
| **Quality gap** | 0.3 | Agent has a program in this category but the listed one is better (more complex, higher version) |
| **Collection diversity** | 0.2 | Agent values having programs in many categories |
| **Random curiosity** | 0.1 | Small random factor to create unexpected trades |

#### Budget Limit

```
budget_limit = available_balance × spending_ratio

spending_ratio by personality:
  conservative: 0.10 (spend at most 10% of balance per trade)
  balanced:     0.20
  aggressive:   0.35
```

### 6.2 When to Sell

Agents always sell — any listed program is for sale. But the agent controls:
- **Which programs to list** — not all generated programs are listed; lower quality ones are kept or discarded
- **Pricing** — see Section 4.2
- **Offer acceptance** — the agent may reject low-ball offers or counter-offer

#### Offer Evaluation

When an offer (kind 4200) arrives:

```
SHOULD_ACCEPT = (
    offer_sats >= minimum_acceptable_price
    AND buyer_trust >= TRUST_MINIMUM
)

minimum_acceptable_price = listed_price × accept_threshold

accept_threshold by personality:
  aggressive:   0.70 (accept 70%+ of listed price)
  balanced:     0.85
  conservative: 0.95
```

If the offer is below the threshold but above 50% of listed price, the agent publishes a kind 4202 (reject) with a `counter_offer_sats` field.

### 6.3 Value Evaluation

When scanning listings to buy, agents estimate program value:

```
estimated_value = (
    base_category_value
    × complexity_multiplier
    × freshness_bonus          # newer listings get slight premium
    × seller_reputation_factor # trusted sellers command premium
)
```

The agent buys if `estimated_value >= listed_price`.

---

## 7. Trading Protocol

### 7.1 Trade State Machine

Each trade is tracked as a finite state machine:

```
                 ┌───────────────────────────────────────┐
                 │                                       │
    ┌────────┐   │   ┌──────────┐   ┌──────────┐        │
    │ LISTED │───┴──>│ OFFERED  │──>│ ACCEPTED │        │
    └────────┘       └─────┬────┘   └─────┬────┘        │
                           │              │              │
                    ┌──────▼────┐   ┌─────▼─────┐       │
                    │ REJECTED  │   │   PAID    │       │
                    └───────────┘   └─────┬─────┘       │
                                          │              │
                                   ┌──────▼──────┐      │
                                   │ DELIVERED   │      │
                                   └──────┬──────┘      │
                                          │              │
                                   ┌──────▼──────┐      │
                                   │  COMPLETE   │      │
                                   └─────────────┘      │
                                                         │
                     TIMEOUT / ERROR ────────────────────┘
                     (return to LISTED)
```

| State | Event Kind | Published By | Description |
|---|---|---|---|
| LISTED | 30078 | Seller | Program is listed on marketplace |
| OFFERED | 4200 | Buyer | Buyer proposes purchase |
| ACCEPTED | 4201 | Seller | Seller agrees to trade |
| REJECTED | 4202 | Seller | Seller declines offer |
| PAID | 4204 | Buyer | Buyer sends encrypted Cashu token |
| (confirmed) | 9735 | system-cashu | Payment confirmed by zap receipt |
| DELIVERED | 4210 | Seller | Seller sends encrypted source code |
| COMPLETE | 4203 | Buyer | Buyer confirms receipt, trade finalized |

### 7.2 Full Trade Flow Implementation

#### Buyer Side

```
on_interesting_listing(listing):
    # 1. Evaluate and decide
    if not should_buy(listing):
        return

    # 2. Publish offer (kind 4200)
    offer_id = generate_uuid()
    publish_event(
        kind=4200,
        tags=[
            ["p", listing.seller_pubkey],
            ["e", listing.event_id, "", "root"],
            ["offer_id", offer_id]
        ],
        content=json({
            "listing_id": listing.d_tag,
            "offer_sats": calculate_offer_price(listing),
            "message": "Interested in purchasing"
        })
    )
    trade_state[offer_id] = "OFFERED"
    set_timeout(offer_id, 60)  # 60s timeout for response

on_trade_accept(event):  # kind 4201
    offer_id = event.tags["offer_id"]
    trade_state[offer_id] = "ACCEPTED"

    # 3. Create and send payment (kind 4204, NIP-04 encrypted)
    amount = event.content["accepted_sats"]
    token = wallet.create_payment(amount)

    publish_event(
        kind=4204,
        tags=[
            ["p", event.pubkey],
            ["e", event.id, "", "reply"],
            ["offer_id", offer_id]
        ],
        content=nip04_encrypt(
            recipient_pubkey=event.pubkey,
            plaintext=json({
                "listing_id": event.content["listing_id"],
                "token": token,
                "amount_sats": amount,
                "payment_id": generate_uuid()
            })
        )
    )
    trade_state[offer_id] = "PAID"
    set_timeout(offer_id, 120)  # 120s for delivery

on_program_delivery(event):  # kind 4210
    offer_id = event.tags["offer_id"]
    decrypted = nip04_decrypt(event.content)
    source = decrypted["source"]
    sha256_received = decrypted["sha256"]

    # 4. Verify integrity
    if sha256(source) != sha256_received:
        log_error("Source hash mismatch")
        return  # do not confirm; trade stalls

    # 5. Save program locally
    save_program(decrypted["listing_id"], source)

    # 6. Publish completion (kind 4203)
    publish_event(
        kind=4203,
        tags=[
            ["p", event.pubkey],
            ["e", event.id, "", "reply"],
            ["offer_id", offer_id]
        ],
        content=json({
            "listing_id": decrypted["listing_id"],
            "status": "complete",
            "sha256_verified": True
        })
    )
    trade_state[offer_id] = "COMPLETE"
    cancel_timeout(offer_id)
    update_reputation(event.pubkey, "success")
```

#### Seller Side

```
on_trade_offer(event):  # kind 4200
    offer_id = event.tags["offer_id"]
    listing_id = event.content["listing_id"]
    offer_sats = event.content["offer_sats"]

    # 1. Evaluate offer
    if should_accept(listing_id, offer_sats, event.pubkey):
        # 2. Publish accept (kind 4201)
        publish_event(
            kind=4201,
            tags=[
                ["p", event.pubkey],
                ["e", event.id, "", "reply"],
                ["offer_id", offer_id]
            ],
            content=json({
                "listing_id": listing_id,
                "accepted_sats": offer_sats,
                "cashu_mint": "http://127.0.0.1:3338",
                "payment_instructions": "Send Cashu token"
            })
        )
        trade_state[offer_id] = "ACCEPTED"
        set_timeout(offer_id, 120)  # 120s for payment
    else:
        # Publish reject (kind 4202) with optional counter-offer
        publish_event(kind=4202, ...)
        trade_state[offer_id] = "REJECTED"

on_payment_received(event):  # kind 4204
    offer_id = event.tags["offer_id"]
    decrypted = nip04_decrypt(event.content)
    token = decrypted["token"]

    # 3. Redeem token immediately
    try:
        amount = wallet.receive(token)
    except Exception:
        log_error("Token redemption failed")
        trade_state[offer_id] = "PAYMENT_FAILED"
        return

    trade_state[offer_id] = "PAID"

    # 4. Deliver program (kind 4210, NIP-04 encrypted)
    source = read_program(decrypted["listing_id"])
    publish_event(
        kind=4210,
        tags=[
            ["p", event.pubkey],
            ["e", event.id, "", "reply"],
            ["offer_id", offer_id]
        ],
        content=nip04_encrypt(
            recipient_pubkey=event.pubkey,
            plaintext=json({
                "listing_id": decrypted["listing_id"],
                "language": "python",
                "source": source,
                "sha256": sha256(source)
            })
        )
    )
    trade_state[offer_id] = "DELIVERED"
    set_timeout(offer_id, 120)  # 120s for confirmation

on_trade_complete(event):  # kind 4203
    offer_id = event.tags["offer_id"]
    trade_state[offer_id] = "COMPLETE"
    cancel_timeout(offer_id)
    update_reputation(event.pubkey, "success")
```

### 7.3 Error Handling

| Error Condition | Detection | Recovery |
|---|---|---|
| Offer timeout (no accept/reject in 60s) | Timer expiry | Buyer marks trade as `EXPIRED`, moves on |
| Payment timeout (no payment in 120s after accept) | Timer expiry | Seller marks trade as `EXPIRED`, re-lists program |
| Delivery timeout (no delivery in 120s after payment) | Timer expiry | Buyer logs failed trade, updates seller's trust score negatively |
| Token redemption failure (double-spend or invalid) | `wallet.receive()` exception | Seller sends kind 4202 reject with reason; buyer retries or abandons |
| Source hash mismatch | SHA256 comparison failure | Buyer does not send kind 4203; trade stalls; trust penalty |
| Relay disconnection mid-trade | WebSocket close event | Reconnect with backoff; resume trade from last known state |

### 7.4 Concurrent Trade Limits

To prevent resource exhaustion and overcommitment:

| Limit | Value | Rationale |
|---|---|---|
| Max concurrent trades (as buyer) | 3 | Prevents overspending budget |
| Max concurrent trades (as seller) | 5 | Sellers can handle more since they don't commit funds upfront |
| Max offers per listing | 1 | One offer at a time per listing to avoid confusion |

---

## 8. Economic Strategy

### 8.1 Agent Personalities

Each agent is assigned a personality at startup that shapes its economic behavior. Personality is determined by the agent's index:

| Agent | Personality | Description |
|---|---|---|
| `user0`, `user1` | **Conservative** | Cautious traders. High prices, careful buying, high trust requirements. Build slowly. |
| `user2`, `user3` | **Aggressive** | High-volume traders. Lower prices, frequent buying, accept more risk. |
| `user4`, `user5` | **Specialist** | Focus on 1–2 program categories. Build deep expertise. Premium pricing in their niche. |
| `user6`, `user7` | **Generalist** | Broad portfolio across all categories. Moderate pricing. Seek diversity. |
| `user8`, `user9` | **Opportunist** | Strategy adapts to market conditions. Copy successful patterns. Buy undervalued programs. |

### 8.2 Personality Parameters

```python
# Pseudocode — personality configuration
PERSONALITIES = {
    "conservative": {
        "price_multiplier": 1.2,       # premium pricing
        "spending_ratio": 0.10,        # spend max 10% of balance per trade
        "accept_threshold": 0.95,      # accept offers at 95%+ of listed price
        "trust_minimum": 0.6,          # require 60%+ trust score
        "creation_rate": "low",        # fewer but higher quality programs
        "category_focus": None,        # no category preference
        "risk_tolerance": 0.2,         # low risk tolerance
    },
    "aggressive": {
        "price_multiplier": 0.8,       # undercut competitors
        "spending_ratio": 0.35,        # spend up to 35% of balance
        "accept_threshold": 0.70,      # accept offers at 70%+ of listed price
        "trust_minimum": 0.3,          # accept riskier partners
        "creation_rate": "high",       # high-volume creation
        "category_focus": None,
        "risk_tolerance": 0.7,
    },
    "specialist": {
        "price_multiplier": 1.3,       # premium for expertise
        "spending_ratio": 0.20,
        "accept_threshold": 0.90,
        "trust_minimum": 0.5,
        "creation_rate": "medium",
        "category_focus": ["math", "crypto"],  # assigned per agent
        "risk_tolerance": 0.4,
    },
    "generalist": {
        "price_multiplier": 1.0,       # market rate
        "spending_ratio": 0.25,
        "accept_threshold": 0.85,
        "trust_minimum": 0.4,
        "creation_rate": "medium",
        "category_focus": None,        # deliberately varied
        "risk_tolerance": 0.5,
    },
    "opportunist": {
        "price_multiplier": 1.0,       # adaptive
        "spending_ratio": 0.30,
        "accept_threshold": 0.75,
        "trust_minimum": 0.35,
        "creation_rate": "adaptive",   # matches market demand
        "category_focus": "adaptive",  # shifts to underserved categories
        "risk_tolerance": 0.6,
    },
}
```

### 8.3 Strategy Evolution

Agent strategies adapt over time based on outcomes:

- **Price adjustment**: If a program doesn't sell within 5 minutes, reduce price by 10%. If it sells immediately (< 30 seconds), increase the next listing's price by 10%.
- **Category shift**: If programs in a category consistently fail to sell, reduce creation weight for that category. If a category consistently sells well, increase weight.
- **Trust adaptation**: As agents build transaction history, their trust scores influence trade partner selection. An agent that gets burned by a partner reduces trust, making future trades with that partner less likely.
- **Spending adaptation**: If balance drops below 20% of starting balance (2,000 sats), temporarily reduce spending ratio by half. If balance rises above 150% of starting balance (15,000 sats), increase spending ratio to grow faster.

---

## 9. Reputation and Trust

### 9.1 Trust Score Model

Each agent maintains a per-partner trust score:

```python
# trust_scores[counterparty_pubkey] -> float in [0.0, 1.0]
# Default trust for unknown partners: 0.5
```

### 9.2 Trust Updates

| Event | Trust Adjustment |
|---|---|
| Successful trade (kind 4203 received) | +0.1 (capped at 1.0) |
| Payment failed (token invalid or double-spent) | -0.3 |
| Delivery timeout (seller didn't deliver after payment) | -0.4 |
| Offer timeout (minor, not penalized heavily) | -0.05 |
| Trade rejected (no penalty) | 0.0 |

Trust scores decay slowly toward 0.5 (default) over time to prevent permanent grudges or permanent trust:

```
trust = trust × 0.99 + 0.5 × 0.01   # per cycle, slow regression to mean
```

### 9.3 Trust Data Persistence

Trust scores are stored in `data/<agent-id>/reputation.json`:

```json
{
  "<counterparty-pubkey-hex>": {
    "trust": 0.85,
    "total_trades": 12,
    "successful_trades": 11,
    "failed_trades": 1,
    "last_trade_ts": 1700000000,
    "total_sats_exchanged": 2400
  }
}
```

### 9.4 Trust in Decision Making

Trust scores influence both buy and sell decisions:

- **Buying**: `buyer_willingness = base_willingness × seller_trust`. Low-trust sellers need to offer better prices.
- **Selling**: Agents may reject offers from very low-trust buyers (below `trust_minimum`), even at full price.
- **Escrow decision**: For high-value trades (> 500 sats) with low-trust partners (< 0.4), the agent may request escrow (kinds 4220–4223) instead of direct payment.

---

## 10. Agent Lifecycle

### 10.1 Boot Sequence

```
Agent Start (spawned by system-master)
    │
    ├── 1. Load configuration
    │       Read config/constants.json (relay URL, mint URL)
    │       Read agent personality from index
    │
    ├── 2. Initialize identity
    │       Load or generate Nostr keypair
    │       data/<agent-id>/nostr_secret.hex
    │       data/<agent-id>/nostr_pubkey.hex
    │
    ├── 3. Initialize wallet
    │       wallet = Wallet.with_db(
    │           url="http://127.0.0.1:3338",
    │           db="data/<agent-id>/wallet",
    │           name="<agent-id>"
    │       )
    │       wallet.load_mint()
    │
    ├── 4. Restore state
    │       Load data/<agent-id>/state.json (if exists)
    │       Load data/<agent-id>/reputation.json (if exists)
    │       Resume any in-flight trades
    │
    ├── 5. Connect to relay
    │       WebSocket connect to ws://127.0.0.1:7777
    │       Retry with exponential backoff (1s, 2s, 4s, max 30s)
    │
    ├── 6. Publish identity
    │       Publish kind 0 metadata event
    │
    ├── 7. Subscribe to events
    │       kind 30078  — program listings (all)
    │       kind 4200   — trade offers directed at self
    │       kind 4201   — trade accepts directed at self
    │       kind 4202   — trade rejects directed at self
    │       kind 4203   — trade completions directed at self
    │       kind 4204   — trade payments directed at self
    │       kind 4210   — program deliveries directed at self
    │       kind 9735   — zap receipts mentioning self
    │
    ├── 8. Publish first heartbeat (kind 4300)
    │
    └── 9. Enter main event loop
```

### 10.2 Main Event Loop

The agent runs a single-threaded async event loop using Python's `asyncio`:

```
Main Event Loop (runs until SIGTERM)
    │
    ├── Every 5 seconds:
    │       Publish heartbeat (kind 4300)
    │
    ├── Every 30 seconds:
    │       Persist state to data/<agent-id>/state.json
    │
    ├── Every cycle (~30-180 seconds, personality-dependent):
    │       ┌── Decision Phase ──────────────────────────┐
    │       │                                            │
    │       │  1. Check wallet balance                   │
    │       │  2. Scan marketplace for interesting buys  │
    │       │  3. Decide: create program, buy, or idle   │
    │       │                                            │
    │       │  If CREATE:                                │
    │       │    Generate program                        │
    │       │    Sandbox test                            │
    │       │    Publish listing (kind 30078)            │
    │       │                                            │
    │       │  If BUY:                                   │
    │       │    Publish offer (kind 4200)               │
    │       │                                            │
    │       │  If IDLE:                                  │
    │       │    Adjust prices on unsold listings        │
    │       │    Review trust scores                     │
    │       └────────────────────────────────────────────┘
    │
    ├── On incoming event:
    │       Dispatch to appropriate handler:
    │       - kind 4200: on_trade_offer() (seller path)
    │       - kind 4201: on_trade_accept() (buyer path)
    │       - kind 4202: on_trade_reject() (buyer path)
    │       - kind 4204: on_payment_received() (seller path)
    │       - kind 4210: on_program_delivery() (buyer path)
    │       - kind 4203: on_trade_complete() (seller path)
    │       - kind 9735: on_zap_receipt() (logging)
    │       - kind 30078: on_new_listing() (marketplace scan)
    │
    └── On timeout:
            Handle expired trades (see Section 7.3)
```

### 10.3 Graceful Shutdown

On receiving `SIGTERM` from `system-master`:

1. **Stop creating new trades** — no new offers or listings
2. **Wait for in-flight trades** — allow up to 10 seconds for active trades to complete
3. **Publish final heartbeat** — kind 4300 with `status: "shutting-down"`
4. **Persist state** — write `state.json` with all current data
5. **Close WebSocket** — disconnect from relay
6. **Exit** with code 0

If `SIGKILL` is received (after 10s grace period), the agent is killed immediately. On next restart, it recovers from the last `state.json` checkpoint.

---

## 11. Metrics and Observability

### 11.1 Heartbeat Data (Kind 4300)

Every 5 seconds, the agent publishes a heartbeat containing metrics for the dashboard:

```json
{
  "kind": 4300,
  "tags": [
    ["agent_name", "user3"],
    ["role", "user-agent"]
  ],
  "content": "{\"status\":\"healthy\",\"uptime_secs\":3621,\"mem_mb\":42,\"balance_sats\":500,\"programs_owned\":3,\"programs_listed\":1,\"active_trades\":0,\"ts\":1700000000}"
}
```

| Field | Type | Source |
|---|---|---|
| `status` | string | `healthy` / `degraded` / `shutting-down` |
| `uptime_secs` | int | Time since agent process started |
| `mem_mb` | int | Resident memory usage |
| `balance_sats` | int | Available Cashu wallet balance |
| `programs_owned` | int | Total programs in local inventory |
| `programs_listed` | int | Programs currently listed for sale |
| `active_trades` | int | In-flight trade negotiations |
| `ts` | int | Unix timestamp |

### 11.2 Agent State File

`data/<agent-id>/state.json` provides a full snapshot for debugging and recovery:

```json
{
  "agent_id": "user3",
  "personality": "aggressive",
  "started_at": 1700000000,
  "wallet_balance": 8500,
  "programs": [
    {
      "uuid": "abc-123",
      "name": "fast-fibonacci-calculator",
      "category": "math",
      "complexity": "medium",
      "listed": true,
      "listed_price": 150,
      "created_at": 1700000100
    }
  ],
  "active_trades": {
    "offer-uuid-5678": {
      "state": "ACCEPTED",
      "role": "buyer",
      "counterparty": "<pubkey>",
      "listing_id": "def-456",
      "amount": 200,
      "started_at": 1700000200,
      "timeout_at": 1700000320
    }
  },
  "stats": {
    "total_trades_completed": 15,
    "total_sats_earned": 2300,
    "total_sats_spent": 1800,
    "programs_created": 22,
    "programs_sold": 12,
    "programs_bought": 8,
    "trades_failed": 2
  }
}
```

### 11.3 Dashboard Integration

The web dashboard (`nostr-design.md` Section 9) consumes the following from user agents:

| Dashboard View | Data Source |
|---|---|
| Agent Overview table | Kind 4300 heartbeats |
| Marketplace listings | Kind 30078 events |
| Trade Activity feed | Kinds 4200, 4201, 4202, 4203, 4204, 4210, 9735 |
| Agent portfolio | Kind 30078 events filtered by pubkey |

### 11.4 Log Format

All agent log lines follow the structured JSON format defined in `autonomy-design.md`:

```json
{"ts":"2026-02-08T12:00:00Z","level":"info","agent":"user3","msg":"Published program listing","program":"fast-fibonacci-calculator","price":150,"event_id":"abc123"}
{"ts":"2026-02-08T12:00:05Z","level":"info","agent":"user3","msg":"Trade offer received","offer_id":"offer-5678","buyer":"user7","amount":150}
{"ts":"2026-02-08T12:00:10Z","level":"info","agent":"user3","msg":"Payment received and redeemed","amount":150,"offer_id":"offer-5678"}
```

---

## 12. File Structure

### 12.1 Source Code

```
zap-empire/
  src/
    user/
      main.py                  # Entry point: parse args, initialize, run event loop
      agent.py                 # UserAgent class: core logic, module coordinator
      nostr_client.py          # Nostr WebSocket client, event publishing/subscribing
      wallet_manager.py        # Cashu wallet wrapper (init, send, receive, balance)
      program_generator.py     # Template engine, randomizer, program assembly
      marketplace.py           # Marketplace scanner, listing publisher, price evaluator
      trade_engine.py          # Trade state machine, offer/accept/pay/deliver flows
      strategy.py              # Personality config, decision engine, adaptation logic
      reputation.py            # Trust score tracking, per-partner history
      sandbox.py               # Sandboxed program execution and validation
      templates/
        math.py                # Math/algorithm program templates
        text.py                # Text processing templates
        data_structures.py     # Data structure templates
        crypto.py              # Crypto/encoding templates
        utilities.py           # System utility templates
        generators.py          # Generator program templates
        converters.py          # Converter templates
        validators.py          # Validator templates
```

### 12.2 Per-Agent Data

```
data/
  user0/
    state.json                 # Agent state checkpoint (persisted every 30s)
    nostr_secret.hex           # Nostr secret key (chmod 600)
    nostr_pubkey.hex           # Nostr public key
    wallet.db                  # Cashu wallet SQLite database
    wallet.json                # Wallet metadata (mint URL, keyset)
    reputation.json            # Per-partner trust scores
    programs/
      <program-uuid>.py       # Generated program source files
      <program-uuid>.py
      ...
  user1/
    ...
  user9/
    ...
```

### 12.3 Shared Configuration

```
config/
  agents.json                  # Agent manifest (spawning config for system-master)
  constants.json               # Shared constants: relay URL, mint URL, ports, intervals
```

### 12.4 Logs

```
logs/
  user0/
    stdout.log                 # Structured JSON logs (rotated at 10 MB, keep 5)
    stderr.log                 # Error output
  user1/
    ...
  user9/
    ...
```

---

## 13. Dependencies

| Package | Version | Purpose |
|---|---|---|
| `cashu` (nutshell) | >= 0.16 | Wallet client library (`cashu.wallet`) |
| `websockets` | >= 12.0 | WebSocket client for Nostr relay connection |
| `secp256k1` or `pynostr` | latest | Nostr event signing and NIP-04 encryption |
| `python` | >= 3.10 | Runtime |

All dependencies are pure Python or have binary wheels. No compilation required on the agent side.

---

## 14. Summary of Key Design Decisions

| Decision | Rationale |
|---|---|
| Template-based program generation | Deterministic, lightweight, no AI dependency; produces variety through combinatorics |
| Personality-driven strategy | Creates emergent economic behavior from simple rules; 5 personality types ensure diversity |
| Immediate token redemption | Minimizes double-spend window; aligns with `zap-design.md` security model |
| Per-partner trust scores | Enables decentralized reputation without a central authority; influences trade decisions |
| Single-threaded async loop | Simple concurrency model; avoids race conditions; sufficient for 10-agent scale |
| Subprocess sandboxing | Lightweight, standard library only; prevents generated programs from causing harm |
| State persistence every 30s | Balances durability with I/O overhead; aligned with `autonomy-design.md` |
| Kind 4300 heartbeats at 5s | Fast health detection by `system-master`; acceptable relay load (~2.6 events/s total) |
