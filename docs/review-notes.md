# Zap Empire: Cross-Review Notes (Consolidated)

**Reviewers**: system-autonomy, system-nostr, system-zap
**Approver**: team-lead
**Date**: 2026-02-08
**Status**: FINAL -- all resolutions confirmed by team lead

**Documents reviewed**:
- `docs/autonomy-design.md` (by system-autonomy)
- `docs/nostr-design.md` (by system-nostr)
- `docs/zap-design.md` (by system-zap)

---

## Confirmed Resolutions

All issues below have been reviewed and resolved by the team lead. Each resolution is FINAL and should be applied to the respective design documents.

---

### ISSUE-1: Heartbeat event kind conflict [CRITICAL]

**Finding**: autonomy-design uses kind `30078` (parameterized replaceable event) for heartbeats. nostr-design uses kind `4300` (regular event). Kind `30078` is also used for program listings in nostr-design, creating a triple conflict.

| Document | Heartbeat Kind | Details |
|---|---|---|
| autonomy-design.md | `30078` (parameterized replaceable) | Section 3.1 -- uses `d` tag with agent ID |
| nostr-design.md | `4300` (regular event) | Section 6.8 -- uses `agent_name` tag |

**RESOLUTION**: Use **kind `4300`** (regular event, not replaceable).

Heartbeats are ephemeral status signals, not data that should be updated in-place. A regular event kind is semantically correct. Kind `30078` is reserved exclusively for program listings.

**Update required**: autonomy-design.md Section 3.1 and 3.2.

---

### ISSUE-2: Heartbeat interval mismatch [MODERATE]

**Finding**: autonomy-design specifies 5-second heartbeat interval with 15-second dead threshold. nostr-design specifies 30-second interval with 60-second offline detection.

| Document | Heartbeat Interval | Dead Threshold |
|---|---|---|
| autonomy-design.md | 5 seconds | 15 seconds (3 missed beats) |
| nostr-design.md | 30 seconds | 60 seconds |

**RESOLUTION**: Use **5-second interval** with **15-second dead threshold** (3 missed beats).

The autonomy framework is the authority on health monitoring. 5-second beats enable fast crash detection, critical for the restart recovery flow. The relay trivially handles ~2.6 heartbeat events/second from 13 agents.

**Update required**: nostr-design.md Section 6.8 and Section 8.

---

### ISSUE-3: Heartbeat payload schema mismatch [MODERATE]

**Finding**: The heartbeat content fields differ between the two documents.

| Field | autonomy-design | nostr-design |
|---|---|---|
| `status` | `healthy` / `degraded` / `shutting-down` | `online` / `busy` / `idle` |
| `uptime` | `uptime` (seconds) | `uptime_secs` (seconds) |
| `memory` | `mem_mb` | not included |
| `balance` | not included | `balance_sats` |
| `programs` | not included | `programs_owned`, `programs_listed` |
| `trades` | not included | `active_trades` |

**RESOLUTION**: **Merge both schemas** into a single heartbeat payload.

autonomy-design's fields (`status`, `uptime_secs`, `mem_mb`) provide system-level health data for the supervisor. nostr-design's fields (`balance_sats`, `programs_owned`, `programs_listed`, `active_trades`) provide application-level data for the dashboard. Both are needed.

Canonical heartbeat payload:

```json
{
  "kind": 4300,
  "pubkey": "<agent-pubkey>",
  "tags": [
    ["agent_name", "user3"],
    ["role", "user-agent"]
  ],
  "content": "{\"status\":\"healthy\",\"uptime_secs\":3621,\"mem_mb\":42,\"balance_sats\":500,\"programs_owned\":3,\"programs_listed\":1,\"active_trades\":0,\"ts\":1700000000}"
}
```

Status vocabulary: `healthy` / `degraded` / `shutting-down` (from autonomy-design, used by system-master for supervision decisions).

**Update required**: Both autonomy-design.md (Section 3.2) and nostr-design.md (Section 6.8).

---

### ISSUE-4: Program listing event kind conflict [CRITICAL]

**Finding**: nostr-design uses kind `30078` for program listings. zap-design uses kind `30023` (NIP-23 long-form content).

| Document | Listing Kind | Details |
|---|---|---|
| nostr-design.md | `30078` | Parameterized replaceable, `d` tag = program UUID |
| zap-design.md | `30023` | NIP-23 "Long-form Content" |

**RESOLUTION**: Use **kind `30078`** (NIP-78 application-specific data, parameterized replaceable).

Kind `30023` is NIP-23 "Long-form Content" intended for blog posts and articles -- a semantic mismatch for marketplace listings. Kind `30078` is in the application-specific replaceable range (30000-39999), the correct range for custom replaceable data like program listings. nostr-design already defines a complete listing structure for this kind.

**Update required**: zap-design.md Sections 5.1, 5.3, and 8.4.

---

### ISSUE-5: Trade message transport conflict [CRITICAL]

**Finding**: nostr-design defines custom event kinds `4200-4203` and `4210` for trade messages (all plaintext). zap-design routes all trade and payment messages through encrypted DMs (kind `4`, NIP-04).

| Document | Trade Messages Via | Details |
|---|---|---|
| nostr-design.md | Custom kinds `4200-4203`, `4210` (plaintext) | Structured trade protocol |
| zap-design.md | Encrypted DMs, kind `4` (NIP-04) | All trade/payment as encrypted DMs |

**RESOLUTION**: **Hybrid approach**.

- **Public custom kinds** (`4200-4203`) for trade negotiation (offer, accept, reject, complete). These are observable by the dashboard and power marketplace analytics.
- **New kind `4204`** ("Trade Payment") for the **encrypted Cashu token transfer**. Cashu tokens are bearer instruments -- anyone who sees the token string can redeem it. Token transfer MUST be encrypted (NIP-04 or NIP-44).
- **Kind `4210`** (Program Delivery) is also **encrypted** -- program source code is the paid product and must not be visible to relay observers.

Updated trade flow:

```
Step  Kind   Name              Encryption  Description
───── ────── ───────────────── ─────────── ────────────────────────────────────
1     30078  Program Listing   Public      Seller lists program for sale
2     4200   Trade Offer       Public      Buyer proposes purchase
3     4201   Trade Accept      Public      Seller accepts with payment info
4     4204   Trade Payment     ENCRYPTED   Buyer sends Cashu token to seller
5     9735   Zap Receipt       Public      system-cashu confirms payment
6     4210   Program Delivery  ENCRYPTED   Seller sends program source to buyer
7     4203   Trade Complete    Public      Buyer confirms receipt
```

**Update required**: Both nostr-design.md (add kind 4204, mark 4210 as encrypted) and zap-design.md (adopt custom kinds, replace kind 4 DMs for trade flow).

---

### ISSUE-6: Agent naming inconsistency [MODERATE]

**Finding**: Three different naming conventions across the docs.

| Document | Cashu Mint Agent | Relay Agent | Cashu Zap Agent |
|---|---|---|---|
| autonomy-design.md | `cashu-mint` | `nostr-relay` | not mentioned |
| nostr-design.md | `system-cashu` | `system-relay` | `system-cashu` |
| zap-design.md | `system-cashu` | `system-nostr` | `system-mint-admin` |

**RESOLUTION**: Standardize on the following canonical names:

| Canonical Name | Role | Description |
|---|---|---|
| `system-master` | Process supervisor | Top-level supervisor, spawns and monitors all agents |
| `system-relay` | Nostr relay process | Local strfry relay on port 7777 |
| `system-mint` | Cashu mint process | Nutshell mint on port 3338 |
| `system-cashu` | Zap receipt publisher | Monitors token swaps, publishes kind 9735 receipts |
| `system-escrow` | Escrow agent | Holds escrowed payments for high-value trades |
| `user0`--`user9` | User agents | Trading agents that create programs and transact |

**Update required**: All three design documents.

---

### ISSUE-7: Data directory structure conflict [MODERATE]

**Finding**: Three different directory layouts proposed.

| Document | Layout |
|---|---|
| autonomy-design.md | `data/<agent-id>/state.json`, `logs/<agent-id>/` |
| nostr-design.md | `data/agents/<agent-id>/nostr_secret.hex` |
| zap-design.md | `data/wallets/<agent-id>/wallet.db`, `data/mint/` |

**RESOLUTION**: Unified layout under `data/<agent-id>/` with all per-agent files together.

```
zap-empire/
  config/
    agents.json              # Agent manifest (autonomy framework)
    constants.json           # Shared constants (relay URL, mint URL, ports)
  data/
    system-master/
      pids.json              # Child process PIDs for crash recovery
      control.sock           # Unix domain socket for zapctl
    system-relay/
      state.json
    system-mint/
      state.json
      mint.db                # Cashu mint SQLite database
    system-cashu/
      state.json
      nostr_secret.hex
      nostr_pubkey.hex
      wallet.db
      wallet.json
    system-escrow/
      state.json
      nostr_secret.hex
      nostr_pubkey.hex
      wallet.db
      wallet.json
    user0/
      state.json             # Autonomy framework state
      nostr_secret.hex       # Nostr keypair
      nostr_pubkey.hex
      wallet.db              # Cashu wallet
      wallet.json
    user1/
      ...
    user9/
      ...
  logs/
    system-master/
      state.log
      master.log
    system-relay/
      stdout.log
      stderr.log
    user0/
      stdout.log
      stderr.log
    ...
```

Key principle: All per-agent data lives under `data/<agent-id>/`. No separate `data/agents/`, `data/wallets/`, etc.

**Update required**: All three design documents.

---

### ISSUE-8: Zap receipt publisher identity [MODERATE]

**Finding**: nostr-design says `system-cashu` publishes kind `9735` zap receipts. zap-design describes direct buyer-to-seller token transfer with no mediating agent in the payment loop.

**RESOLUTION**: **`system-cashu`** publishes kind `9735` zap receipts after confirming a token swap at the mint.

Flow: When a buyer sends an encrypted Cashu token (kind `4204`) to a seller, the seller redeems it at the mint. `system-cashu` monitors the mint's swap activity (or is notified by the seller) and publishes a kind `9735` zap receipt as an independent attestation of payment. This follows the NIP-57 pattern where a trusted third party (the "zap provider") issues receipts.

**Update required**: zap-design.md (add system-cashu to payment flow).

---

### ISSUE-9: Kind 30078 overloaded [MODERATE]

**Finding**: Kind `30078` was used for program listings (nostr-design), trade receipts (zap-design), and heartbeats (autonomy-design) -- three different semantic purposes.

**RESOLUTION**: Each purpose gets a distinct kind.

- `30078` -- Program listings only (parameterized replaceable)
- `4300` -- Heartbeats (resolved in ISSUE-1)
- Trade receipts are replaced by kind `9735` zap receipts from `system-cashu` (resolved in ISSUE-8)
- Kind `30079` is removed -- NIP-33 replaceable events handle listing updates by re-publishing with the same `d` tag. A separate "update" kind is redundant.

**Update required**: nostr-design.md (remove kind 30079 from table), zap-design.md (use 9735 not 30078 for receipts).

---

### ISSUE-10: Missing escrow event kinds [NEW -- team lead addition]

**Finding**: zap-design.md describes an escrow mechanism (Section 9) but does not define Nostr event kinds for escrow operations. The escrow flow uses informal JSON messages with no standardized kind.

**RESOLUTION**: Add **escrow event kinds `4220-4223`**:

| Kind | Name | Encryption | Description |
|---|---|---|---|
| `4220` | Escrow Lock | ENCRYPTED | Buyer locks payment with system-escrow (contains Cashu token) |
| `4221` | Escrow Release | Public | Buyer confirms receipt, authorizes release to seller |
| `4222` | Escrow Dispute | Public | Buyer disputes the trade |
| `4223` | Escrow Timeout | Public | system-escrow auto-releases after timeout expiry |

Kind `4220` must be encrypted because it contains a Cashu bearer token (same rationale as kind `4204`).

**Update required**: Both nostr-design.md (add to event kinds table) and zap-design.md (Section 9, use these kinds).

---

### ISSUE-11: Relay URL and Mint URL not consistently referenced [MINOR]

**Finding**: autonomy-design does not specify the relay port. The mint URL is absent from autonomy-design.

| Document | Relay URL | Mint URL |
|---|---|---|
| autonomy-design.md | `ws://127.0.0.1:<port>` (unspecified) | not mentioned |
| nostr-design.md | `ws://127.0.0.1:7777` | `http://127.0.0.1:3338` (in trade accept) |
| zap-design.md | not mentioned | `http://127.0.0.1:3338` |

**RESOLUTION**: Add both URLs to a shared configuration constants file and reference them consistently.

Shared constants (`config/constants.json`):

```json
{
  "relay_url": "ws://127.0.0.1:7777",
  "mint_url": "http://127.0.0.1:3338",
  "relay_port": 7777,
  "mint_port": 3338,
  "tick_interval_s": 60,
  "status_broadcast_every_n_ticks": 5,
  "startup_timeout_ms": 30000
}
```

**Update required**: autonomy-design.md (reference constants, specify port 7777 explicitly).

---

### ISSUE-12: Technology stack ambiguity [MINOR]

**Finding**: autonomy-design assumes Node.js (agent manifest uses `node`, `--max-old-space-size`). nostr-design lists multiple languages. zap-design assumes Python (Nutshell library).

| Document | Assumed Language | Details |
|---|---|---|
| autonomy-design.md | Node.js | Manifest uses `node`, memory limit via `--max-old-space-size` |
| nostr-design.md | Multi-language | Python, Node.js, Rust all listed as options |
| zap-design.md | Python | All code examples use Nutshell (Python) |

**RESOLUTION**: **Python throughout** (updated by team lead after initial review).

- **All agents and mint**: Python -- the Cashu mint (Nutshell) is Python, and agents import `cashu.wallet` directly for wallet operations. Nostr communication uses `pynostr` or `websockets`.
- This avoids an unnecessary HTTP hop between agents and the mint, and keeps the entire stack in one language for simplicity.

All three design docs (autonomy-design.md, nostr-design.md, zap-design.md) have been updated to reflect Python as the primary language.

**Status**: APPLIED to all docs.

---

## Updated Event Kinds Table (CANONICAL)

This is the single source of truth for all Nostr event kinds in Zap Empire.

### Standard Kinds

| Kind | NIP | Name | Description |
|---|---|---|---|
| `0` | NIP-01 | Agent Metadata | Agent identity and profile (published on startup) |
| `5` | NIP-09 | Event Deletion | Retract offers, cancel listings |
| `9735` | NIP-57 | Zap Receipt | Payment confirmation (published by system-cashu) |

### Application Kinds -- Marketplace

| Kind | Name | Replaceable? | Encryption | Description |
|---|---|---|---|---|
| `30078` | Program Listing | Yes (`d` tag) | Public | Agent lists a program for sale |

### Application Kinds -- Trade Protocol

| Kind | Name | Replaceable? | Encryption | Description |
|---|---|---|---|---|
| `4200` | Trade Offer | No | Public | Buyer proposes to purchase a program |
| `4201` | Trade Accept | No | Public | Seller accepts an offer |
| `4202` | Trade Reject | No | Public | Seller rejects an offer |
| `4203` | Trade Complete | No | Public | Buyer confirms delivery received |
| `4204` | Trade Payment | No | **ENCRYPTED** | Buyer sends Cashu token to seller |
| `4210` | Program Delivery | No | **ENCRYPTED** | Seller sends program source to buyer |

### Application Kinds -- Escrow

| Kind | Name | Replaceable? | Encryption | Description |
|---|---|---|---|---|
| `4220` | Escrow Lock | No | **ENCRYPTED** | Buyer locks Cashu token with system-escrow |
| `4221` | Escrow Release | No | Public | Buyer authorizes payment release to seller |
| `4222` | Escrow Dispute | No | Public | Buyer disputes the trade |
| `4223` | Escrow Timeout | No | Public | system-escrow auto-releases expired escrow |

### Application Kinds -- System

| Kind | Name | Replaceable? | Encryption | Description |
|---|---|---|---|---|
| `4300` | Agent Status Broadcast | No | Public | Periodic status report for dashboard (~every 5 min); NOT for health monitoring |
| `4301` | Agent Status Change | No | Public | Agent state transition announcement |

### Retired/Removed Kinds

| Kind | Previously | Reason |
|---|---|---|
| `30079` | Program Listing Update | Redundant; NIP-33 replaceable events handle updates by re-publishing kind `30078` with same `d` tag |
| `30023` | Program Listing (zap-design) | Replaced by kind `30078`; NIP-23 is semantically wrong for listings |

---

## Updated Agent Inventory (CANONICAL)

| Canonical Name | Type | Restart Policy | Wallet? | Nostr Identity? | Description |
|---|---|---|---|---|---|
| `system-master` | supervisor | N/A (top-level) | No | No | Spawns and monitors all agents; exposes zapctl |
| `system-relay` | infrastructure | `always` | No | Yes | Local strfry Nostr relay on `ws://127.0.0.1:7777` |
| `system-mint` | infrastructure | `always` | No | No | Nutshell Cashu mint on `http://127.0.0.1:3338` (Python) |
| `system-cashu` | system agent | `always` | Yes | Yes | Monitors mint swaps, publishes kind 9735 zap receipts |
| `system-escrow` | system agent | `on-failure` | Yes | Yes | Holds escrowed payments for high-value trades |
| `user0` | user agent | `on-failure` | Yes | Yes | Trading agent |
| `user1` | user agent | `on-failure` | Yes | Yes | Trading agent |
| `user2` | user agent | `on-failure` | Yes | Yes | Trading agent |
| `user3` | user agent | `on-failure` | Yes | Yes | Trading agent |
| `user4` | user agent | `on-failure` | Yes | Yes | Trading agent |
| `user5` | user agent | `on-failure` | Yes | Yes | Trading agent |
| `user6` | user agent | `on-failure` | Yes | Yes | Trading agent |
| `user7` | user agent | `on-failure` | Yes | Yes | Trading agent |
| `user8` | user agent | `on-failure` | Yes | Yes | Trading agent |
| `user9` | user agent | `on-failure` | Yes | Yes | Trading agent |

**Total**: 15 managed processes.

### Spawn Order

1. **Phase 1 -- Infrastructure**: `system-relay`, `system-mint` (parallel)
2. **Phase 2 -- System agents**: `system-cashu`, `system-escrow` (after Phase 1 healthy)
3. **Phase 3 -- User agents**: `user0` through `user9` (parallel, after Phase 2 healthy)

---

## Updated Trade Flow (CANONICAL)

```
Seller (user3)              Relay                system-cashu         Buyer (user7)
     |                        |                       |                    |
     |-- 30078 listing ------>|                       |                    |
     |                        |                       |                    |
     |                        |<----- 4200 offer -------------------------|
     |<--- 4200 offer --------|                       |                    |
     |                        |                       |                    |
     |-- 4201 accept -------->|                       |                    |
     |                        |---- 4201 accept ----->|------------------->|
     |                        |                       |                    |
     |                        |<----- 4204 payment (ENCRYPTED) -----------|
     |<--- 4204 payment ------|                       |                    |
     |                        |                       |                    |
     |  [redeem token at mint]|                       |                    |
     |  ...................... mint swap ............. |                    |
     |                        |                       |                    |
     |                        |<-- 9735 zap receipt --|                    |
     |<--- 9735 receipt ------|                       |--- 9735 receipt -->|
     |                        |                       |                    |
     |-- 4210 delivery ------>| (ENCRYPTED)           |                    |
     |                        |---- 4210 delivery --->|------------------->|
     |                        |                       |                    |
     |                        |<----- 4203 complete ----------------------|
     |<--- 4203 complete -----|                       |                    |
     |                        |                       |                    |
```

### Trade State Machine

```
LISTED ──> OFFERED ──> ACCEPTED ──> PAID ──> DELIVERED ──> COMPLETE
                   \──> REJECTED
```

| State | Triggered By | Event Kind |
|---|---|---|
| LISTED | Seller publishes listing | `30078` |
| OFFERED | Buyer sends offer | `4200` |
| ACCEPTED | Seller accepts | `4201` |
| REJECTED | Seller rejects | `4202` |
| PAID | Buyer sends token + system-cashu confirms | `4204` + `9735` |
| DELIVERED | Seller sends program source | `4210` |
| COMPLETE | Buyer confirms receipt | `4203` |

---

## Summary Table

| Issue | Severity | Resolution | Update Required |
|---|---|---|---|
| ISSUE-1: Heartbeat kind | CRITICAL | Use kind `4300` | autonomy-design |
| ISSUE-2: Heartbeat interval | MODERATE | Use 5-second interval | nostr-design |
| ISSUE-3: Heartbeat payload | MODERATE | Merge both schemas | autonomy-design, nostr-design |
| ISSUE-4: Listing kind | CRITICAL | Use kind `30078` | zap-design |
| ISSUE-5: Trade transport | CRITICAL | Hybrid: public negotiation + encrypted payment (kind `4204`) | nostr-design, zap-design |
| ISSUE-6: Agent naming | MODERATE | Standardized names (see inventory) | all three docs |
| ISSUE-7: Directory structure | MODERATE | Unified `data/<agent-id>/` layout | all three docs |
| ISSUE-8: Zap receipt publisher | MODERATE | system-cashu publishes kind `9735` | zap-design |
| ISSUE-9: Kind 30078 overloaded | MODERATE | Distinct kinds per purpose; remove `30079` | nostr-design, zap-design |
| ISSUE-10: Escrow event kinds | NEW | Add kinds `4220-4223` | nostr-design, zap-design |
| ISSUE-11: Relay/Mint URLs | MINOR | Shared `config/constants.json` | autonomy-design |
| ISSUE-12: Tech stack | MINOR | Mint=Python, Agents=Python throughout | zap-design, nostr-design |
| ISSUE-13: Heartbeat redesign | CRITICAL | Heartbeat is NOT health-check; redesigned as autonomous activity loop (~60s tick). Kind 4300 repurposed as status broadcast (~5 min) for dashboard only. No UNHEALTHY state. Process monitoring via OS-level waitpid only. | autonomy-design, nostr-design, user-agent-design |

---

## Action Items

### system-autonomy (autonomy-design.md)
1. ~~Update heartbeat kind from `30078` to `4300`~~ ✓ Done
2. ~~Merge heartbeat payload schema~~ ✓ Done
3. Add relay URL `ws://127.0.0.1:7777` and mint URL `http://127.0.0.1:3338` (Section 8.4)
4. Update agent inventory: rename agents to canonical names, add `system-cashu` and `system-escrow`, update total to 15 (Section 1.1)
5. Add Phase 2 (system agents) to spawn order (Section 2.3)
6. Reference `config/constants.json` for shared configuration
7. **ISSUE-13**: Redesigned heartbeat → autonomous activity loop (~60s tick). Removed UNHEALTHY state, removed health-check loop, added activity selection logic. ✓ Done

### system-nostr (nostr-design.md)
1. ~~Update heartbeat interval from 30s to 5s~~ → **ISSUE-13**: Kind 4300 repurposed as status broadcast (~5 min). ✓ Done
2. Remove kind `30079` from event kinds table (Section 5)
3. Add kind `4204` (Trade Payment, encrypted) to event kinds table
4. Mark kind `4210` (Program Delivery) as encrypted
5. Add escrow kinds `4220-4223` to event kinds table
6. Update agent names to canonical convention
7. Recommend `nostr-tools` as primary client library

### system-zap (zap-design.md)
1. Update listing kind from `30023` to `30078` (Sections 5.1, 5.3, 8.4)
2. Adopt custom trade kinds `4200-4203`, `4204` for payment, `4210` for delivery
3. Add system-cashu to payment flow as zap receipt publisher
4. Use escrow kinds `4220-4223` in Section 9
5. Add Node.js/cashu-ts code examples alongside Python
6. Update agent names to canonical convention
7. Update directory layout to `data/<agent-id>/`
