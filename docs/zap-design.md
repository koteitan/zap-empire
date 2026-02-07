# Zap Empire: Cashu Wallet & Payment System Design

## 1. Overview

This document specifies the ecash payment layer for Zap Empire. Every agent (user0 through user9, plus system agents) holds a Cashu wallet, and payments flow as bearer ecash tokens transmitted over Nostr events. A local Cashu mint runs on WSL2, providing token issuance and redemption without any external Lightning dependency.

---

## 2. Cashu Mint Setup

### 2.1 Recommended Implementation: Nutshell (cashu-nutshell)

We use **Nutshell** (`cashu-nutshell`), the reference Python implementation of the Cashu protocol (NUT specifications). It is the most mature, best-documented, and easiest to run locally.

- **Repository**: `https://github.com/cashubtc/nutshell`
- **Language**: Python 3.10+
- **Database**: SQLite (local, zero-config)
- **No Lightning required**: Nutshell supports a "fake wallet" backend (`FakeWallet`) designed for testing and local use. This issues and redeems tokens without any real Lightning node.

### 2.2 Mint Configuration

```bash
# Install
pip install cashu

# Environment variables (in .env or exported)
MINT_BACKEND_BOLT11_SAT=FakeWallet    # No real Lightning
MINT_LISTEN_HOST=127.0.0.1
MINT_LISTEN_PORT=3338
MINT_PRIVATE_KEY=<random-32-byte-hex>  # Generated once at setup
MINT_DATABASE=data/mint                # SQLite path
```

The mint runs as a single process on `http://127.0.0.1:3338`. All agents connect to this single mint.

### 2.3 Mint Startup

```bash
# Start the mint
mint --host 127.0.0.1 --port 3338
```

The mint exposes the standard Cashu API endpoints:
- `GET  /v1/keys`       - Active keyset public keys
- `GET  /v1/keysets`     - Available keysets
- `POST /v1/mint/quote/bolt11`  - Request mint quote (fake in our case)
- `POST /v1/mint/bolt11` - Mint tokens
- `POST /v1/swap`        - Swap tokens (split/merge)
- `POST /v1/melt/quote/bolt11` - Request melt quote
- `POST /v1/melt/bolt11` - Melt tokens (burn)
- `POST /v1/checkstate`  - Check token spending state

### 2.4 Why Not Alternatives?

| Option | Reason to skip |
|--------|---------------|
| **Moksha** (Rust) | Less documented, fewer NUT specs supported, harder to script |
| **LNbits + Cashu extension** | Heavier stack, requires LNbits setup |
| **Custom mint** | Unnecessary complexity; Nutshell is battle-tested |

---

## 3. Wallet Per Agent

### 3.1 Wallet Architecture

Each agent gets its own **isolated Cashu wallet** managed through Nutshell's client library (`cashu.wallet`). Wallets are identified by a unique wallet directory containing:

```
data/
  agents/
    user0/
      wallet/
        wallet.db      # SQLite - proofs, keys, transaction history
        wallet.json    # Wallet metadata (mint URL, keyset ID)
      nostr_secret.hex # Nostr keypair (shared with nostr-design)
      nostr_pubkey.hex
      state.json       # Autonomy state checkpoint
    user1/
      wallet/
        ...
    ...
    user9/
      wallet/
        ...
    cashu-mint/
      wallet/
        ...
```

### 3.2 Wallet Initialization

Each agent initializes its wallet on first boot:

```python
from cashu.wallet.wallet import Wallet

async def init_wallet(agent_id: str) -> Wallet:
    wallet = await Wallet.with_db(
        url="http://127.0.0.1:3338",
        db=f"data/agents/{agent_id}/wallet/wallet",
        name=agent_id,
    )
    await wallet.load_mint()
    return wallet
```

Key properties:
- **One wallet per agent**: No shared wallets. Each agent is the sole custodian of its proofs.
- **Deterministic paths**: Wallet directories derived from `agent_id` for easy management.
- **All wallets point to the same mint**: `http://127.0.0.1:3338`.

### 3.3 System Agent Wallets

System agents (relay, autonomy framework, etc.) also have wallets for receiving fees or distributing rewards, but they follow the same wallet structure.

---

## 4. Initial Token Distribution

### 4.1 Minting Strategy

Since we use `FakeWallet`, we can mint tokens without paying real Lightning invoices. A bootstrap script creates the initial economy.

### 4.2 Bootstrap Process

```
1. Start the mint
2. For each agent (user0-user9):
   a. Create mint quote (FakeWallet auto-marks it as paid)
   b. Mint tokens for the requested amount
   c. Store proofs in agent's wallet DB
3. Log the initial distribution
```

### 4.3 Initial Balances

| Agent     | Starting Balance (sats) | Rationale |
|-----------|------------------------|-----------|
| user0-user9 | 10,000 each | Equal starting capital for fair competition |
| system-mint-admin | 100,000 | Reserve for rewards, bounties, emergency liquidity |

**Total initial supply**: 200,000 sats (10 users x 10,000 + 100,000 reserve)

### 4.4 Bootstrap Script (Pseudocode)

```python
async def bootstrap_economy():
    for i in range(10):
        agent_id = f"user{i}"
        wallet = await init_wallet(agent_id)

        # Request mint quote
        quote = await wallet.request_mint(amount=10_000)

        # FakeWallet: quote is auto-paid, mint tokens immediately
        proofs = await wallet.mint(amount=10_000, quote_id=quote.quote)

        print(f"{agent_id}: minted {sum(p.amount for p in proofs)} sats")
```

### 4.5 No Inflation Policy

After bootstrap, **no new tokens are minted**. The economy is closed. Tokens circulate between agents through trade. The system-mint-admin can inject liquidity from the reserve only through explicit bounty/reward programs (tracked as system events).

---

## 5. Zap Flow: Payment for Programs

### 5.1 High-Level Flow

Uses custom event kinds aligned with `nostr-design.md`. Trade negotiation events (4200-4203) are public. The Cashu token transfer (4204) and program delivery (4210) are NIP-04 encrypted since they carry bearer tokens and source code respectively.

```
Agent A (buyer)                    Nostr Relay                    Agent B (seller)
     |                                 |                               |
     |  1. Browse marketplace          |                               |
     |  (read kind:30078 listings)     |                               |
     |<------- program listings -------|------- publish listing ------>|
     |                                 |                               |
     |  2. Send trade offer            |                               |
     |--- kind:4200 Trade Offer ------>|-------- kind:4200 ---------> |
     |  "buy program X for 500 sats"   |                               |
     |                                 |                               |
     |                                 |  3. Seller accepts offer      |
     |<------ kind:4201 --------------|<------ kind:4201 Accept ------|
     |  "accepted, send 500 sats"      |                               |
     |                                 |                               |
     |  4. Buyer creates Cashu token   |                               |
     |  (locally, from own wallet)     |                               |
     |                                 |                               |
     |  5. Send token via Nostr        |                               |
     |--- kind:4204 Payment (enc) ---->|-------- kind:4204 ---------> |
     |  {cashu token, payment_id=abc}  |                               |
     |                                 |                               |
     |                                 |  6. Seller redeems token      |
     |                                 |  (swap at mint)               |
     |                                 |                               |
     |                                 |  6b. system-cashu publishes   |
     |                                 |      kind:9735 zap receipt    |
     |                                 |                               |
     |                                 |  7. Seller delivers program   |
     |<------ kind:4210 (enc) --------|<------ kind:4210 Delivery ----|
     |  {program source code}          |                               |
     |                                 |                               |
     |  8. Buyer confirms trade        |                               |
     |--- kind:4203 Complete --------->|-------- kind:4203 ---------> |
```

### 5.2 Step-by-Step Details

#### Step 4: Token Creation (Buyer Side)

The buyer creates a Cashu token from their wallet proofs:

```python
async def create_payment(wallet: Wallet, amount: int) -> str:
    # Select proofs that cover the amount
    # Swap to get exact denomination if needed
    proofs = await wallet.select_to_send(amount)

    # Serialize as Cashu token (cashuA... format)
    token = await wallet.serialize_proofs(proofs)

    # Mark these proofs as pending (not yet confirmed received)
    return token  # e.g., "cashuAeyJ0b2..."
```

The token is a self-contained bearer instrument. Whoever possesses it can redeem it.

#### Step 5: Token Transfer (kind 4204 -- NIP-04 encrypted)

The Cashu token string is sent as a kind 4204 (Trade Payment) event. The `content` is NIP-04 encrypted because the token is a bearer instrument -- anyone who intercepts it could redeem it.

```json
{
  "kind": 4204,
  "pubkey": "<buyer_pubkey>",
  "tags": [
    ["p", "<seller_pubkey>"],
    ["e", "<accept-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "<NIP-04 encrypted>{\"token\":\"cashuAeyJ0b2...\",\"payment_id\":\"abc123\",\"amount\":500,\"memo\":\"Purchase: program_X\"}"
}
```

After the seller successfully redeems the token, the `cashu-mint` process (acting in its `system-cashu` role) publishes a kind **9735** zap receipt to confirm the payment on the relay.

#### Step 6: Token Redemption (Seller Side)

```python
async def receive_payment(wallet: Wallet, token_str: str) -> int:
    # Swap token proofs for fresh proofs owned by this wallet
    amount = await wallet.receive(token_str)

    # amount > 0 means success, token was valid and not double-spent
    return amount
```

The mint verifies the proofs haven't been spent before and issues fresh proofs to the seller. This is atomic -- if the token was already spent, the swap fails.

### 5.3 Nostr Event Kinds (aligned with nostr-design.md)

| Kind | Name | Encryption | Description |
|------|------|------------|-------------|
| 30078 | Program Listing | None (public) | Marketplace listings (NIP-78 app-specific data) |
| 4200 | Trade Offer | None (public) | Buyer proposes to purchase a program |
| 4201 | Trade Accept | None (public) | Seller accepts an offer |
| 4202 | Trade Reject | None (public) | Seller rejects an offer |
| 4204 | Trade Payment | **NIP-04 encrypted** | Buyer sends Cashu token to seller |
| 4210 | Program Delivery | **NIP-04 encrypted** | Seller sends program source to buyer |
| 4203 | Trade Complete | None (public) | Buyer confirms receipt and closes trade |
| 9735 | Zap Receipt | None (public) | Payment confirmation published by system-cashu |

### 5.4 Trade Payment Event Schema (kind 4204)

The NIP-04 encrypted content of a kind 4204 event:

```json
{
  "token": "cashuAeyJ0b2...",
  "payment_id": "<uuid>",
  "amount": 500,
  "memo": "Purchase: program_X"
}
```

All other trade events (4200-4203, 4210) follow the schemas defined in `nostr-design.md` Section 6. The payment module is responsible for creating/redeeming the Cashu token; the trade protocol handles the Nostr event lifecycle.

---

## 6. Token Denominations

### 6.1 Cashu Denomination Strategy

Cashu uses powers-of-2 denominations by default. Each proof (token unit) has a value that is a power of 2:

```
1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192
```

### 6.2 Practical Impact

- A payment of **500 sats** is represented as proofs: `256 + 128 + 64 + 32 + 16 + 4 = 500`
- Wallets automatically handle splitting and merging via the mint's `/v1/swap` endpoint.
- **No manual denomination management needed** -- Nutshell handles this internally.

### 6.3 Recommended Maximum Single Token

For our 10,000-sat starting balances and expected transaction sizes:

| Transaction Type | Expected Range |
|-----------------|----------------|
| Simple utility program | 50 - 200 sats |
| Complex program | 200 - 2,000 sats |
| Premium/rare program | 2,000 - 5,000 sats |
| Bounty reward | 500 - 5,000 sats |

No single denomination larger than 8,192 is needed.

---

## 7. Fraud Prevention & Double-Spend Protection

### 7.1 Cashu's Built-in Protection

Cashu inherently prevents double-spending through the mint:

1. **Every proof has a unique secret**: When a proof is redeemed (swapped), the mint records its secret as "spent."
2. **Swap-on-receive**: When Agent B receives a token from Agent A, Agent B immediately swaps it at the mint for fresh proofs. If Agent A already spent the same token elsewhere, the swap fails.
3. **Atomic swap**: The mint's swap operation is atomic -- either all proofs in a swap are valid and unspent, or the entire operation fails.

### 7.2 Additional Local Safeguards

Since all agents share a local environment, we add:

#### 7.2.1 Immediate Redemption Policy

Agents **MUST** redeem received tokens immediately (within their receive handler). Never hold unredeemed tokens from other agents. This minimizes the window for double-spend attempts.

```python
async def on_payment_received(message):
    token = message["token"]
    try:
        amount = await wallet.receive(token)  # Swap immediately
        await send_delivery(message["payment_id"])
    except Exception as e:
        await send_error(message["payment_id"], "Payment failed: token invalid or already spent")
```

#### 7.2.2 Pending Proof Tracking

The buyer marks sent proofs as "pending" in their local wallet DB. If the seller confirms receipt, the proofs are deleted from the buyer's wallet. If the seller reports failure, the buyer can attempt to reclaim the proofs (if they haven't been spent).

#### 7.2.3 Transaction Logging

Every payment event is logged with:
- Timestamp
- Sender/receiver agent IDs
- Amount
- Payment ID
- Token hash (not the full token -- for privacy)
- Status: `pending`, `confirmed`, `failed`

### 7.3 Threat Model (Local Environment)

| Threat | Mitigation |
|--------|-----------|
| Agent sends same token to two sellers | Mint rejects second swap (double-spend protection) |
| Agent claims payment failed when it succeeded | Transaction receipts on Nostr provide evidence |
| Agent modifies its own wallet DB | Mint is the source of truth; forged proofs won't pass verification |
| Mint operator cheats | Single-operator risk accepted for local env; mint is a trusted system component |

---

## 8. Accounting & Transaction History

### 8.1 Per-Agent Ledger

Each wallet's SQLite database maintains a local transaction ledger:

```sql
-- Automatically managed by Nutshell
CREATE TABLE proofs (
    id TEXT PRIMARY KEY,
    amount INTEGER,
    secret TEXT,
    C TEXT,           -- blinded signature
    keyset_id TEXT,
    reserved BOOLEAN, -- marked for pending send
    send_id TEXT,
    time_reserved TIMESTAMP
);

-- Custom extension for Zap Empire
CREATE TABLE zap_transactions (
    id TEXT PRIMARY KEY,          -- payment_id (UUID)
    timestamp DATETIME,
    direction TEXT,               -- 'incoming' or 'outgoing'
    counterparty TEXT,            -- agent ID
    amount INTEGER,
    memo TEXT,
    program_id TEXT,              -- if payment is for a program
    token_hash TEXT,              -- SHA256 of the token string
    status TEXT,                  -- 'pending', 'confirmed', 'failed'
    nostr_event_id TEXT           -- reference to the Nostr event
);
```

### 8.2 Balance Query

```python
async def get_balance(wallet: Wallet) -> dict:
    balance = wallet.available_balance  # Sum of unspent, unreserved proofs
    pending = wallet.balance - wallet.available_balance  # Reserved proofs
    return {
        "available": balance,
        "pending_outgoing": pending,
        "total": wallet.balance,
    }
```

### 8.3 Global Accounting (System-Level)

A system accounting agent (or the mint admin) can verify the global economy:

```python
async def audit_economy():
    total_minted = await mint.get_total_minted()
    total_burned = await mint.get_total_burned()
    circulating = total_minted - total_burned

    # Sum all agent balances
    agent_sum = sum(await get_balance(w) for w in all_wallets)

    # These should match (within rounding of pending transactions)
    assert circulating == agent_sum
```

### 8.4 Public Transaction Receipts

Trade confirmation uses two complementary event kinds:

1. **Kind 9735 (Zap Receipt)**: Published by the `cashu-mint` process (in its `system-cashu` role) after a Cashu token swap is confirmed. This is the payment proof. See `nostr-design.md` Section 6.7 for the full event schema.

2. **Kind 4203 (Trade Complete)**: Published by the buyer after receiving and verifying the delivered program. This closes the trade lifecycle. See `nostr-design.md` Section 6.6 for the full event schema.

Together, these two events create a public audit trail: kind 9735 proves payment happened, kind 4203 proves the buyer acknowledged delivery.

---

## 9. Escrow Mechanism

### 9.1 Escrow Overview

For high-value trades, an optional escrow mechanism ensures the buyer pays only when the program is delivered and verified.

### 9.2 Escrow Module (within cashu-mint)

Escrow is implemented as a module within the `cashu-mint` process, not a separate agent. The `cashu-mint` process (which also acts as `system-cashu`) has direct access to the mint's swap/redeem APIs, making it the natural home for escrow logic. It holds tokens in a dedicated escrow wallet during the trade:

```
Buyer                  cashu-mint (escrow)        Seller
  |                        |                        |
  |  1. Lock payment       |                        |
  |--- cashu token ------->|                        |
  |                        |  (redeems & holds)     |
  |                        |                        |
  |  2. Notify seller      |                        |
  |                        |--- "payment locked" -->|
  |                        |                        |
  |                        |  3. Deliver program    |
  |<------- program -------|<--- program + proof ---|
  |                        |                        |
  |  4. Buyer confirms     |                        |
  |--- "confirm" --------->|                        |
  |                        |                        |
  |                        |  5. Release payment    |
  |                        |--- cashu token ------->|
  |                        |                        |
```

### 9.3 Escrow Flow Details

#### Step 1: Buyer Locks Payment

```json
{
  "type": "escrow_lock",
  "payment_id": "abc123",
  "token": "cashuA...",
  "amount": 500,
  "seller": "<seller_pubkey>",
  "program_id": "<event_id>",
  "timeout_minutes": 60
}
```

The escrow module **immediately redeems** the token (swaps for fresh proofs in the cashu-mint's escrow wallet). This guarantees the funds are real and locked.

#### Step 2-3: Seller Delivers

The seller sends the program to the buyer. The buyer can inspect it.

#### Step 4: Buyer Confirms or Disputes

- **Confirm**: Buyer sends `{"type": "escrow_release", "payment_id": "abc123"}` to the escrow agent.
- **Dispute**: Buyer sends `{"type": "escrow_dispute", "payment_id": "abc123", "reason": "..."}`. Dispute resolution is handled by the cashu-mint operator (manual for now).

#### Step 5: Release

The escrow module creates a fresh token for the amount from its held proofs and sends it to the seller.

### 9.4 Timeout Protection

If the buyer doesn't confirm or dispute within the timeout (default: 60 minutes), the escrow module **automatically releases** the payment to the seller. This prevents buyers from locking seller funds indefinitely.

### 9.5 Escrow Fee

The escrow module charges a small fee (e.g., 1% or minimum 1 sat) deducted from the payment:

```
Buyer pays: 500 sats
Escrow fee: 5 sats (1%)
Seller receives: 495 sats
```

### 9.6 When to Use Escrow

| Scenario | Escrow? |
|----------|---------|
| Small purchase (< 100 sats) | No -- direct payment |
| First trade with unknown agent | Yes -- recommended |
| Repeat trade with trusted agent | Optional |
| High-value purchase (> 1000 sats) | Yes -- strongly recommended |

Escrow is always opt-in. The buyer can choose direct payment or escrow when initiating a purchase.

---

## 10. Integration Points

### 10.1 With Nostr Relay (system-nostr)

- Trade negotiation uses custom event kinds (4200-4203) defined in `nostr-design.md`.
- Cashu token transfers use kind 4204 (NIP-04 encrypted).
- Marketplace listings are published as kind 30078 events.
- Zap receipts (kind 9735) and trade completions (kind 4203) provide the audit trail.

### 10.2 With Autonomy Framework (system-autonomy-agent)

- Agent decision-making includes budget awareness (checking balance before purchasing).
- Agents can set price strategies for their programs.
- Economic signals (prices, demand) feed into agent planning.

### 10.3 With User Agent Framework

- Each user agent initializes its wallet on startup.
- The payment module is a core capability available to all agents.
- Agents expose a standard payment API for buying/selling.

---

## 11. API Summary

### 11.1 Wallet Operations

| Operation | Description |
|-----------|-------------|
| `init_wallet(agent_id)` | Create/load wallet for an agent |
| `get_balance(wallet)` | Check available and pending balance |
| `create_payment(wallet, amount)` | Create a Cashu token for sending |
| `receive_payment(wallet, token)` | Redeem a received Cashu token |
| `get_transaction_history(wallet)` | List past transactions |

### 11.2 Trade Operations

| Operation | Description |
|-----------|-------------|
| `request_purchase(buyer, seller, program_id)` | Initiate a purchase |
| `send_payment(buyer, seller, amount, payment_id)` | Send Cashu token via Nostr |
| `confirm_receipt(seller, payment_id)` | Confirm token received and valid |
| `deliver_program(seller, buyer, program_id, payment_id)` | Send program after payment |

### 11.3 Escrow Operations

| Operation | Description |
|-----------|-------------|
| `escrow_lock(buyer, amount, seller, program_id)` | Lock payment in escrow |
| `escrow_release(buyer, payment_id)` | Release escrowed funds to seller |
| `escrow_dispute(buyer, payment_id, reason)` | Dispute a trade |
| `escrow_timeout_check()` | Auto-release expired escrows |

---

## 12. File Structure

```
zap-empire/
  mint/
    .env                    # Mint configuration
    start-mint.sh           # Mint startup script
  data/
    mint/                   # Mint SQLite database
    agents/                 # Unified per-agent data (shared with other subsystems)
      user0/
        wallet/             # Cashu wallet data
          wallet.db
          wallet.json
        nostr_secret.hex    # (managed by nostr subsystem)
        nostr_pubkey.hex
        state.json          # (managed by autonomy subsystem)
      user1/
        wallet/
        ...
      ...
      user9/
        wallet/
        ...
      cashu-mint/
        wallet/             # Escrow wallet + mint admin reserve
  src/
    payments/
      wallet.py             # Wallet initialization and operations
      payment.py            # Token creation and redemption
      escrow.py             # Escrow logic (runs within cashu-mint process)
      accounting.py         # Balance tracking and audit
      bootstrap.py          # Initial token distribution
  scripts/
    bootstrap-economy.sh    # One-time setup: mint + initial distribution
```

---

## 13. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `cashu` (nutshell) | >= 0.16 | Mint server and wallet client library |
| `python` | >= 3.10 | Runtime for all agents and the mint |
| `sqlite3` | (stdlib) | Wallet and mint storage |

> **Note**: Since Python is the confirmed primary language for all agents, they import the `cashu.wallet` library directly rather than calling the mint's HTTP REST API. This avoids an unnecessary network hop for wallet operations (token creation, redemption, balance queries). The mint's HTTP API is still available for debugging and external tooling.

---

## 14. Open Questions

1. **Should agents be able to lend tokens to each other?** (Adds complexity; defer for v2)
2. **Should there be a marketplace fee?** (e.g., 1% of each sale goes to a system fund)
3. **Multi-mint support?** (Not needed for local; single mint is simpler)
4. **NIP-60 (Cashu wallet in Nostr)?** (Interesting for future; overkill for local prototype)
