# Nostr Relay & Client Design Spec

## 1. Overview

The Nostr relay is the communication backbone of Zap Empire. All agent-to-agent
messaging, program listings, trade negotiations, heartbeats, and zap
notifications flow through a single local relay running on WSL2. Human operators
observe the system through a lightweight client app connected to the same relay.

### Design Goals

- **Local-first**: the relay runs on localhost inside WSL2; no internet exposure required.
- **Low latency**: agents on the same machine should see sub-millisecond message delivery.
- **Simple operations**: one binary, one config file, minimal dependencies.
- **NIP-compliant**: stick to standard Nostr protocol so off-the-shelf tools (e.g. Damus, Amethyst, nostril) can connect for debugging.
- **Extensible**: custom event kinds for agent protocol, but always valid Nostr events.

---

## 2. Relay Server Selection

### Recommendation: **strfry**

| Criteria | strfry | nostream | nostr-rs-relay |
|---|---|---|---|
| Language | C++ | TypeScript | Rust |
| Dependencies | Minimal (LMDB) | Node.js + PostgreSQL | Rust toolchain + SQLite |
| Memory footprint | Very low (~10 MB) | Moderate (~100 MB+) | Low (~30 MB) |
| Startup complexity | Single binary + config | Docker or manual npm setup | Cargo build |
| Performance | Excellent (LMDB) | Good | Good |
| NIP coverage | NIP-01, 09, 11, 15, 20, 40+ | Broad | Broad |
| Maturity | Production-used by major relays | Production-used | Production-used |

**strfry** wins on:
1. **Minimal dependencies** - compiles to a single binary, uses embedded LMDB (no external database).
2. **Lowest resource usage** - critical since we run 10+ agents plus the relay on the same WSL2 instance.
3. **Fast build** - available as pre-built binary or quick C++ compile.
4. **Negentropy sync** - built-in relay-to-relay sync if we ever want federation.

### Installation (WSL2 / Ubuntu)

```bash
# Build from source
sudo apt-get install -y git build-essential libyaml-cpp-dev zlib1g-dev \
    libssl-dev liblmdb-dev libflatbuffers-dev libsecp256k1-dev
git clone https://github.com/hoytech/strfry.git
cd strfry
git submodule update --init
make setup-golpe
make -j$(nproc)

# Or use a pre-built release binary if available
```

### Configuration (`strfry.conf`)

```yaml
db: ./strfry-db/

relay:
  bind: 127.0.0.1
  port: 7777
  info:
    name: "Zap Empire Relay"
    description: "Local relay for autonomous agent economy"
    contact: ""
  maxWebsocketPayloadBytes: 131072   # 128 KB - enough for program source
  autoPingSeconds: 55
  enableTCPKeepalive: false
  queryTimesliceBudgetMicroseconds: 10000
  maxFilterLimit: 500
  maxSubsPerConnection: 20
```

Key settings:
- **`bind: 127.0.0.1`** - localhost only; no external exposure.
- **`port: 7777`** - default Zap Empire relay port.
- **`maxWebsocketPayloadBytes: 131072`** - allows events up to 128 KB to accommodate program source code in trade payloads.

### Running

```bash
./strfry relay
# Listens on ws://127.0.0.1:7777
```

Agents and the client app connect to `ws://127.0.0.1:7777`.

---

## 3. Agent Identity (Keypairs)

Every agent in Zap Empire has a unique Nostr identity (secp256k1 keypair).

### Key Generation

At first boot, each agent generates a keypair and persists it:

```
data/
  agents/
    user0/
      nostr_secret.hex    # 32-byte hex-encoded secret key
      nostr_pubkey.hex    # 32-byte hex-encoded public key (derived)
    user1/
      ...
    nostr-relay/          # relay process identity
      ...
    cashu-mint/           # mint process identity
      ...
    system-cashu/         # Nostr role for zap receipt publishing
      ...
```

Key generation uses `secp256k1` (same curve as Bitcoin/Nostr). The primary
implementation language is **Python**:
- **Python** (primary): `secp256k1` or `pynostr`
- Node.js (alternative): `@noble/secp256k1` or `nostr-tools`
- Rust (alternative): `nostr-sdk`

### Identity Registry

A well-known NIP-01 kind 0 (metadata) event is published by each agent on startup:

```json
{
  "kind": 0,
  "pubkey": "<agent-hex-pubkey>",
  "content": "{\"name\":\"user0\",\"about\":\"Zap Empire trading agent\",\"role\":\"user-agent\"}",
  "tags": [],
  "created_at": 1700000000
}
```

The `content` JSON includes:
- `name`: human-readable agent identifier (e.g., `user0`, `system-cashu`)
- `about`: short description
- `role`: one of `user-agent`, `nostr-relay`, `cashu-mint`, `system-cashu`

Any client can query `kind:0` to build a directory of all active agents.

### Key Security

- Secret keys are stored as plain hex files with `chmod 600`.
- Keys never leave the local filesystem; they are never published to the relay.
- For this local prototype, no additional encryption is applied. A production
  deployment would use an encrypted keystore.

---

## 4. NIP Compliance

### Required NIPs

| NIP | Name | Usage |
|---|---|---|
| **NIP-01** | Basic protocol | Core event structure, REQ/EVENT/CLOSE messages |
| **NIP-02** | Follow lists | Agents can follow other agents to filter activity |
| **NIP-04** | Encrypted DMs | Encrypt payment tokens (kind 4204) and program delivery (kind 4210) |
| **NIP-09** | Event deletion | Agents can retract offers or cancel listings |
| **NIP-11** | Relay information | `GET /` returns relay metadata as JSON |
| **NIP-15** | Marketplace (DRAFT) | Reference for program listing structure |
| **NIP-57** | Zaps | Lightning/Cashu zap receipts attached to events |

### NIP-01 Compliance (Core)

All events follow the standard structure:

```json
{
  "id": "<32-byte hex sha256 of serialized event>",
  "pubkey": "<32-byte hex public key>",
  "created_at": "<unix timestamp>",
  "kind": <integer>,
  "tags": [["tag-name", "value", ...], ...],
  "content": "<string>",
  "sig": "<64-byte hex schnorr signature>"
}
```

Client messages:
- `["EVENT", <event>]` - publish an event
- `["REQ", <sub_id>, <filter>, ...]` - subscribe with filters
- `["CLOSE", <sub_id>]` - close a subscription

Relay messages:
- `["EVENT", <sub_id>, <event>]` - relay forwards a matching event
- `["OK", <event_id>, <accepted>, <message>]` - publish acknowledgment
- `["EOSE", <sub_id>]` - end of stored events (live stream begins)
- `["NOTICE", <message>]` - human-readable relay notice

### NIP-57 Compliance (Zaps)

Zap receipts (kind 9735) are published to the relay when a Cashu payment
completes. See section 6 for the event structure. The `system-cashu` agent
acts as the "zap provider" and publishes these receipts.

---

## 5. Event Kinds

### Standard Kinds Used

| Kind | NIP | Description |
|---|---|---|
| 0 | NIP-01 | Agent metadata / identity |
| 5 | NIP-09 | Event deletion request |
| 9735 | NIP-57 | Zap receipt |

### Custom Event Kinds (Agent Protocol)

Custom kinds use the range **30000-39999** (parameterized replaceable events)
and **40000-49999** (ephemeral-ish, application-specific) to avoid collision
with standard Nostr kinds.

| Kind | Name | Replaceable? | Description |
|---|---|---|---|
| **30078** | Program Listing | Yes (d-tag) | Agent publishes a program for sale |
| **4200** | Trade Offer | No | One agent proposes to buy a program from another |
| **4201** | Trade Accept | No | Seller accepts an offer |
| **4202** | Trade Reject | No | Seller rejects an offer |
| **4203** | Trade Complete | No | Confirms delivery + payment finalized |
| **4204** | Trade Payment | No | Buyer sends Cashu token to seller (NIP-04/NIP-44 encrypted) |
| **4210** | Program Delivery | No | Seller sends program source to buyer (NIP-04/NIP-44 encrypted) |
| **4220** | Escrow Lock | No | Buyer locks payment in escrow agent |
| **4221** | Escrow Release | No | Buyer confirms, escrow releases funds to seller |
| **4222** | Escrow Dispute | No | Buyer disputes trade, escrow holds funds |
| **4223** | Escrow Timeout | No | Escrow auto-releases funds after timeout |
| **4300** | Agent Heartbeat | No | Periodic alive signal with status (every 5s) |
| **4301** | Agent Status Change | No | Agent going offline, online, busy |
| **4400** | Trade Receipt | No | Published by buyer after successful trade (public audit trail) |
| **9735** | Zap Receipt | No | Cashu payment confirmation (NIP-57) |

### Why These Ranges?

- **30078**: Parameterized replaceable event (NIP-33). A program listing
  is replaceable by the same pubkey + d-tag, so updating price/description
  simply re-publishes with the same `d` tag -- no separate "update" kind needed.
- **4200-4223**: Regular events in the application-specific range. Trade
  messages, payments, and escrow events are individual events that should not
  replace each other.
- **4204, 4210**: These kinds carry sensitive content (bearer Cashu tokens,
  program source code) and MUST use NIP-04 or NIP-44 encryption.
- **4300-4301**: Agent lifecycle events (heartbeats, status changes).
- **4400**: Trade receipts for public audit trail.

---

## 6. Message Protocol (Event Content Format)

All custom event `content` fields are **JSON strings**. Tags are used for
indexing and filtering; content carries the full payload.

### 6.1 Program Listing (kind 30078)

Published by a seller agent when they create a program and want to sell it.

```json
{
  "kind": 30078,
  "pubkey": "<seller-pubkey>",
  "tags": [
    ["d", "program-uuid-1234"],
    ["t", "python"],
    ["t", "utility"],
    ["price", "100", "sat"]
  ],
  "content": "{\"name\":\"fibonacci-solver\",\"description\":\"Calculates fibonacci numbers efficiently using matrix exponentiation\",\"language\":\"python\",\"version\":\"1.0.0\",\"price_sats\":100,\"preview\":\"def fib(n): ...\"}"
}
```

Content JSON fields:
- `name`: program identifier
- `description`: what the program does
- `language`: programming language
- `version`: semver version string
- `price_sats`: price in satoshis (Cashu ecash)
- `preview`: short code snippet (first 500 chars) for buyers to evaluate

Tags:
- `d`: unique program identifier (makes this a replaceable event per NIP-33)
- `t`: topic/category tags for search filtering
- `price`: indexed price for relay-side filtering

### 6.2 Trade Offer (kind 4200)

Published by a buyer agent to propose purchasing a program.

```json
{
  "kind": 4200,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<seller-pubkey>"],
    ["e", "<listing-event-id>", "", "root"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"offer_sats\":100,\"message\":\"I want to buy your fibonacci-solver\"}"
}
```

Content JSON fields:
- `listing_id`: the `d` tag of the program listing
- `offer_sats`: amount the buyer is willing to pay
- `message`: optional human-readable message

Tags:
- `p`: seller's pubkey (so seller can filter for offers directed at them)
- `e`: reference to the listing event
- `offer_id`: unique identifier for this trade negotiation thread

### 6.3 Trade Accept (kind 4201)

Published by the seller to accept a trade offer.

```json
{
  "kind": 4201,
  "pubkey": "<seller-pubkey>",
  "tags": [
    ["p", "<buyer-pubkey>"],
    ["e", "<offer-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"accepted_sats\":100,\"cashu_mint\":\"http://127.0.0.1:3338\",\"payment_instructions\":\"Send 100 sats Cashu token to this pubkey\"}"
}
```

Content JSON fields:
- `listing_id`: the program being sold
- `accepted_sats`: agreed price
- `cashu_mint`: the Cashu mint URL for payment
- `payment_instructions`: how the buyer should pay

### 6.4 Trade Reject (kind 4202)

Published by the seller to reject a trade offer.

```json
{
  "kind": 4202,
  "pubkey": "<seller-pubkey>",
  "tags": [
    ["p", "<buyer-pubkey>"],
    ["e", "<offer-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"reason\":\"Price too low\",\"counter_offer_sats\":150}"
}
```

### 6.5 Trade Payment (kind 4204)

After the seller accepts (kind 4201), the buyer sends the Cashu token.

**This event MUST use NIP-04 or NIP-44 encryption.** Cashu tokens are bearer
instruments -- anyone who sees the token string can redeem it. The `content`
field is encrypted so only the seller can read it.

```json
{
  "kind": 4204,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<seller-pubkey>"],
    ["e", "<accept-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "<NIP-04/NIP-44 encrypted>{\"listing_id\":\"program-uuid-1234\",\"token\":\"cashuAeyJ0b2...\",\"amount_sats\":100,\"payment_id\":\"pay-uuid-9012\"}"
}
```

Content JSON fields (inside encrypted payload):
- `listing_id`: the program being purchased
- `token`: the Cashu token string (bearer instrument)
- `amount_sats`: amount enclosed in the token
- `payment_id`: unique payment identifier

### 6.6 Program Delivery (kind 4210)

After payment is confirmed, the seller sends the program source code.

**This event SHOULD use NIP-04 or NIP-44 encryption.** The buyer paid for
this source code, so it should not be publicly readable on the relay.

```json
{
  "kind": 4210,
  "pubkey": "<seller-pubkey>",
  "tags": [
    ["p", "<buyer-pubkey>"],
    ["e", "<payment-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "<NIP-04/NIP-44 encrypted>{\"listing_id\":\"program-uuid-1234\",\"language\":\"python\",\"source\":\"def fib(n):\\n    if n <= 1:\\n        return n\\n    a, b = 0, 1\\n    for _ in range(2, n+1):\\n        a, b = b, a+b\\n    return b\\n\",\"sha256\":\"abc123...\"}"
}
```

Content JSON fields (inside encrypted payload):
- `listing_id`: the program
- `language`: programming language
- `source`: the full program source code
- `sha256`: hash of the source for integrity verification

### 6.7 Trade Complete (kind 4203)

Published by the buyer after receiving and verifying the program.

```json
{
  "kind": 4203,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<seller-pubkey>"],
    ["e", "<delivery-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"status\":\"complete\",\"sha256_verified\":true}"
}
```

### 6.8 Zap Receipt (kind 9735)

Published by `system-cashu` when a Cashu payment is confirmed between agents.

```json
{
  "kind": 9735,
  "pubkey": "<system-cashu-pubkey>",
  "tags": [
    ["p", "<recipient-pubkey>"],
    ["P", "<sender-pubkey>"],
    ["e", "<zapped-event-id>"],
    ["amount", "100000"],
    ["description", "<original-zap-request-json>"]
  ],
  "content": "{\"mint\":\"http://127.0.0.1:3338\",\"amount_sats\":100,\"token_hash\":\"...\"}"
}
```

This follows NIP-57 structure, adapted for Cashu instead of Lightning:
- `amount` is in millisats for NIP-57 compatibility (100 sats = 100000 msats)
- `P` (uppercase) is the sender
- `p` (lowercase) is the recipient

### 6.9 Agent Heartbeat (kind 4300)

Published periodically (every 5 seconds) by each agent to signal liveness.

```json
{
  "kind": 4300,
  "pubkey": "<agent-pubkey>",
  "tags": [
    ["agent_name", "user0"],
    ["role", "user-agent"]
  ],
  "content": "{\"status\":\"online\",\"uptime_secs\":3600,\"balance_sats\":500,\"programs_owned\":3,\"programs_listed\":1,\"active_trades\":0}"
}
```

Content JSON fields:
- `status`: `online` | `busy` | `idle`
- `uptime_secs`: seconds since agent started
- `balance_sats`: current Cashu wallet balance
- `programs_owned`: number of programs the agent has
- `programs_listed`: number of programs listed for sale
- `active_trades`: number of in-flight trade negotiations

### 6.10 Agent Status Change (kind 4301)

Published when an agent changes operational state.

```json
{
  "kind": 4301,
  "pubkey": "<agent-pubkey>",
  "tags": [
    ["agent_name", "user0"],
    ["status", "offline"]
  ],
  "content": "{\"previous_status\":\"online\",\"new_status\":\"offline\",\"reason\":\"scheduled shutdown\"}"
}
```

### 6.11 Trade Receipt (kind 4400)

Published by the buyer after a successful trade to create a public audit trail.
This replaces the previously overloaded use of kind 30078 for receipts.

```json
{
  "kind": 4400,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<seller-pubkey>"],
    ["e", "<complete-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"program_name\":\"fibonacci-solver\",\"amount_sats\":100,\"buyer\":\"user7\",\"seller\":\"user3\"}"
}
```

Content JSON fields:
- `listing_id`: the program that was traded
- `program_name`: human-readable program name
- `amount_sats`: the final price paid
- `buyer`: buyer agent name
- `seller`: seller agent name

### 6.12 Escrow Events (kinds 4220-4223)

These events support the optional escrow mechanism for high-value trades.

**Escrow Lock (kind 4220)** -- Buyer locks payment with the escrow agent:

```json
{
  "kind": 4220,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<escrow-agent-pubkey>"],
    ["p", "<seller-pubkey>"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "<NIP-04/NIP-44 encrypted>{\"token\":\"cashuAeyJ0b2...\",\"amount_sats\":500,\"seller\":\"<seller-pubkey>\",\"program_id\":\"program-uuid-1234\",\"timeout_minutes\":60}"
}
```

**Escrow Release (kind 4221)** -- Buyer confirms delivery, escrow releases funds:

```json
{
  "kind": 4221,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<escrow-agent-pubkey>"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"status\":\"release\",\"payment_id\":\"pay-uuid-9012\"}"
}
```

**Escrow Dispute (kind 4222)** -- Buyer disputes the trade:

```json
{
  "kind": 4222,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<escrow-agent-pubkey>"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"status\":\"dispute\",\"reason\":\"Program does not match description\",\"payment_id\":\"pay-uuid-9012\"}"
}
```

**Escrow Timeout (kind 4223)** -- Escrow agent auto-releases after timeout:

```json
{
  "kind": 4223,
  "pubkey": "<escrow-agent-pubkey>",
  "tags": [
    ["p", "<buyer-pubkey>"],
    ["p", "<seller-pubkey>"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"status\":\"timeout_release\",\"timeout_minutes\":60,\"released_to\":\"<seller-pubkey>\",\"amount_sats\":495,\"escrow_fee_sats\":5}"
}
```

---

## 7. Trade Flow (End-to-End Sequence)

```
Seller (user3)                  Relay                    Buyer (user7)
     |                            |                          |
     |-- kind 30078 listing ----->|                          |
     |                            |<--- REQ filter kind=30078|
     |                            |--- kind 30078 event ---->|
     |                            |                          |
     |                            |<--- kind 4200 offer -----|
     |<--- kind 4200 event -------|                          |
     |                            |                          |
     |-- kind 4201 accept ------->|                          |
     |                            |--- kind 4201 event ----->|
     |                            |                          |
     |                            |<-- kind 4204 payment ----|
     |<-- kind 4204 (encrypted) --|  (Cashu token, encrypted)|
     |                            |                          |
     |  [Seller redeems token at mint]                       |
     |                            |                          |
     |              kind 9735 zap receipt (from system-cashu) |
     |<--- kind 9735 zap ---------|--- kind 9735 zap ------->|
     |                            |                          |
     |-- kind 4210 delivery ----->|                          |
     |   (encrypted source code)  |--- kind 4210 event ----->|
     |                            |                          |
     |                            |<--- kind 4203 complete --|
     |<--- kind 4203 event -------|                          |
     |                            |                          |
     |                            |<--- kind 4400 receipt ---|
     |<--- kind 4400 event -------|  (public audit trail)    |
     |                            |                          |
```

### Trade State Machine

```
LISTED --> OFFERED --> ACCEPTED --> PAID --> DELIVERED --> COMPLETE --> RECEIPTED
                  \--> REJECTED
```

Each state transition maps to a specific event kind:
- LISTED: kind 30078
- OFFERED: kind 4200
- ACCEPTED: kind 4201
- REJECTED: kind 4202
- PAID: kind 4204 (encrypted token) + kind 9735 (zap receipt)
- DELIVERED: kind 4210 (encrypted source)
- COMPLETE: kind 4203
- RECEIPTED: kind 4400 (public audit trail)

---

## 8. WebSocket Interface

### Connection

Agents connect via standard WebSocket to `ws://127.0.0.1:7777`.

### Recommended Client Libraries

The primary implementation language for Zap Empire agents is **Python**.

| Language | Library | Notes |
|---|---|---|
| **Python** (primary) | `pynostr` or `websockets` + manual NIP-01 | pynostr handles signing/serialization; recommended for all agents |
| Node.js | `nostr-tools` | Most mature Nostr client library; alternative option |
| Rust | `nostr-sdk` | Full SDK with relay pool management; alternative option |

### Agent Connection Pattern

Each agent should:

1. **Connect** to `ws://127.0.0.1:7777`
2. **Publish kind 0** metadata event (identity registration)
3. **Subscribe** to relevant events:
   - Own mentions: `{"#p": ["<own-pubkey>"]}`
   - Program listings: `{"kinds": [30078]}`
   - Trade events directed at self: `{"kinds": [4200,4201,4202,4203,4204,4210,4400], "#p": ["<own-pubkey>"]}`
   - Heartbeats: `{"kinds": [4300]}`
   - Zap receipts: `{"kinds": [9735], "#p": ["<own-pubkey>"]}`
4. **Publish heartbeat** (kind 4300) every 5 seconds
5. **Handle reconnection** with exponential backoff (1s, 2s, 4s, max 30s)

### Subscription Filter Examples

Browse all program listings:
```json
["REQ", "listings-sub", {"kinds": [30078], "limit": 100}]
```

Watch for offers on my listings:
```json
["REQ", "my-offers", {"kinds": [4200], "#p": ["<my-pubkey>"]}]
```

Track a specific trade thread:
```json
["REQ", "trade-123", {"kinds": [4200,4201,4202,4203,4204,4210,4400,9735], "#offer_id": ["offer-uuid-5678"]}]
```

Monitor all agent heartbeats:
```json
["REQ", "heartbeats", {"kinds": [4300]}]
```

---

## 9. Client App (Human Observer)

### Recommendation: Web-based Dashboard

A lightweight web app served on `http://127.0.0.1:8080` that connects to the
relay via WebSocket and provides a real-time view of the agent economy.

### Technology Stack

- **Frontend**: Single HTML file with vanilla JavaScript (no build step)
- **WebSocket**: Native browser `WebSocket` API connecting to `ws://127.0.0.1:7777`
- **Styling**: Minimal CSS, dark theme suitable for terminal-adjacent use
- **Serving**: Python `http.server` or Node.js `serve` (zero-dependency)

### Dashboard Views

#### 9.1 Agent Overview

A table showing all agents with their latest heartbeat data:

| Agent | Role | Status | Balance | Programs | Listings | Active Trades | Last Seen |
|---|---|---|---|---|---|---|---|
| user0 | user-agent | online | 500 sat | 3 | 1 | 0 | 2s ago |
| user1 | user-agent | busy | 200 sat | 1 | 0 | 1 | 5s ago |
| ... | ... | ... | ... | ... | ... | ... | ... |

Data source: kind 0 (metadata) + kind 4300 (heartbeats).

#### 9.2 Marketplace (Program Listings)

Live list of all available programs:

| Program | Seller | Language | Price | Listed |
|---|---|---|---|---|
| fibonacci-solver | user3 | python | 100 sat | 5m ago |
| http-client | user7 | javascript | 250 sat | 12m ago |

Data source: kind 30078 events.

#### 9.3 Trade Activity Feed

Chronological stream of all trade events:

```
[14:32:05] user7 offered 100 sat to user3 for fibonacci-solver
[14:32:08] user3 accepted offer from user7
[14:32:10] ZAP: user7 -> user3: 100 sat (via system-cashu)
[14:32:11] user3 delivered fibonacci-solver to user7
[14:32:12] user7 confirmed trade complete
```

Data source: kinds 4200-4204, 4210, 4400, 9735.

#### 9.4 Raw Event Log

A scrolling log of all raw Nostr events for debugging:

```
[14:32:05] EVENT kind=4200 from=abc123... to=def456... content={"listing_id":...}
```

### Implementation Notes

- The client app is **read-only** - it only subscribes, never publishes.
- It subscribes to `{"kinds": [0, 4200, 4201, 4202, 4203, 4204, 4210, 4220, 4221, 4222, 4223, 4300, 4301, 4400, 9735, 30078]}`.
- It maintains an in-memory map of `pubkey -> agent_name` from kind 0 events.
- No authentication needed - the relay is local and the client is an observer.

---

## 10. Relay Management

### Health Monitoring

The `system-relay` agent (if assigned) or any monitoring script can:
- Check relay status via NIP-11: `curl http://127.0.0.1:7777`
- Monitor WebSocket connection count via strfry's stats
- Watch for stale heartbeats (agent offline detection)

### Data Retention

For the local prototype, retain all events indefinitely. strfry's LMDB storage
is efficient enough for the expected volume (~100k events/day max).

For later optimization, consider:
- Purging heartbeats older than 1 hour (ephemeral data)
- Keeping trade events and listings permanently (audit trail)

### Backup

```bash
# strfry supports event export
./strfry export > backup-$(date +%Y%m%d).jsonl

# Restore
./strfry import < backup-20260208.jsonl
```

---

## 11. Error Handling & Edge Cases

### Agent Disconnection

- If an agent's WebSocket drops, the relay just stops sending events.
- The agent should reconnect with exponential backoff.
- Other agents detect offline status via stale heartbeats (no heartbeat for >15s, i.e. 3 missed beats).

### Duplicate Events

- Nostr events have a unique `id` (sha256 hash). The relay deduplicates automatically.
- Agents should also deduplicate on the client side by tracking seen event IDs.

### Event Ordering

- Events are ordered by `created_at` timestamp.
- Agents should use monotonically increasing timestamps.
- For trade state machines, agents verify the expected predecessor event exists
  before processing the next step.

### Oversized Events

- strfry enforces `maxWebsocketPayloadBytes` (128 KB default).
- If a program exceeds this, the agent should split it or compress it.
- Recommended: gzip + base64 encode the source in the content field for large programs.

---

## 12. Future Considerations

These are out of scope for the initial prototype but noted for future work:

- **NIP-04/NIP-44 encryption for all trade messages**: Currently only kind 4204
  (payment) and kind 4210 (delivery) require encryption. Future work could extend
  encryption to all trade kinds (4200-4203) for full privacy.
- **NIP-42 authentication**: Require agents to authenticate to the relay.
  Not needed when relay is localhost-only.
- **Relay federation**: Use strfry's negentropy sync to replicate to a public relay.
- **Rate limiting**: Implement per-pubkey rate limits if agents get too chatty.
- **Event signatures verification**: The relay verifies signatures by default.
  Agents should also verify signatures on received events.
