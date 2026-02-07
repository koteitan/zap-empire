# Zap Empire: Autonomy Framework Design

## 1. Overview

This document specifies how Zap Empire agent processes are spawned, monitored, supervised, and recovered on a local WSL2 environment. The system supports **10 user agents** (`user0`--`user9`) and multiple **system agents** that manage infrastructure.

### 1.1 Agent Inventory

| Agent Type | Instances | Role |
|---|---|---|
| `system-master` | 1 | Top-level supervisor; spawns and monitors all other agents |
| `nostr-relay` | 1 | Local Nostr relay server |
| `cashu-mint` | 1 | Cashu mint for ecash issuance and redemption |
| `user0`--`user9` | 10 | User agents that create programs, trade, and transact |

Total: **13 processes** under management.

---

## 2. Process Management

### 2.1 Technology Choice: Custom Process Manager

Rather than using systemd (which requires root and complicates WSL2 setups) or a third-party supervisor like `supervisord`, Zap Empire uses a **custom lightweight process manager** written in the project's primary language. This gives us full control over lifecycle, autonomous activity loops, and inter-agent messaging without external dependencies.

The process manager is embedded in `system-master`.

### 2.2 Process Spawning

`system-master` is the single entry point. When launched, it:

1. Reads a declarative agent manifest (`config/agents.json`) that lists every agent to run.
2. Spawns each agent as a **child process** using OS-level process creation (`subprocess.Popen`).
3. Records each agent's **PID**, **spawn timestamp**, and **assigned identity** (e.g., `user3`).
4. Pipes each child's `stdout`/`stderr` to per-agent rotating log files under `logs/<agent-id>/`.

#### Agent Manifest Example

```json
{
  "relay_url": "ws://127.0.0.1:7777",
  "mint_url": "http://127.0.0.1:3338",
  "agents": [
    { "id": "nostr-relay",  "cmd": "./strfry", "args": ["relay"],                          "restart": "always" },
    { "id": "cashu-mint",   "cmd": "python",   "args": ["-m", "cashu.mint"],               "restart": "always" },
    { "id": "user0",        "cmd": "python",   "args": ["src/user/main.py", "0"],          "restart": "on-failure" },
    { "id": "user1",        "cmd": "python",   "args": ["src/user/main.py", "1"],          "restart": "on-failure" }
  ]
}
```

### 2.3 Spawn Order and Dependencies

Agents are started in **dependency order**:

1. **Phase 1 -- Infrastructure**: `nostr-relay`, `cashu-mint`
2. **Phase 2 -- Users**: `user0` through `user9` (can start in parallel once Phase 1 agents report healthy)

`system-master` waits for Phase 1 agents to signal readiness (relay accepts WebSocket connections; mint responds to health endpoint) before proceeding to Phase 2.

---

## 3. Autonomous Activity Loop

### 3.1 Concept

Each user agent runs an internal **activity loop** — a periodic tick that drives autonomous economic behavior. When an agent has no pending tasks (no incoming offers, no trades to complete), the tick selects and executes an autonomous action.

This is the "heartbeat" of the Zap Empire economy: not a health signal, but the **pulse of self-directed activity**.

### 3.2 Tick Configuration

| Parameter | Value |
|---|---|
| Default tick interval | **60 seconds** |
| Configurable range | 30–300 seconds |
| Per-agent override | `tick_interval` field in agent manifest |
| Nostr status broadcast kind | `4300` (informational, not for health checks) |
| Status broadcast frequency | Every 5 ticks (~5 minutes) |

The interval is deliberately long (1 minute) because:
- Actions involve real Nostr events and Cashu transactions
- The marketplace needs time between actions for natural price discovery
- Lower system load and more readable logs

### 3.3 Activity Selection

Each tick, the agent runs through a priority-ordered decision process:

| Priority | Condition | Action |
|---|---|---|
| 1 | Pending trade messages (offers/acceptances/payments) | Respond to trade |
| 2 | Marketplace has attractive programs below budget | Browse & consider purchase |
| 3 | Fewer than N programs in inventory | Generate a new program |
| 4 | Listed programs haven't sold recently | Adjust prices |
| 5 | Portfolio review interval reached | Analyze performance & update strategy |
| 6 | None of the above | Idle (log, wait for next tick) |

The specific decision logic and personality-based variations are defined in the [User Agent Design](./user-agent-design.md).

### 3.4 Activity Loop Pseudocode

```python
async def activity_loop(agent):
    while agent.running:
        # 1. Check for and handle pending trade messages
        pending = await agent.nostr.fetch_pending_events()
        if pending:
            await agent.trade_engine.process(pending)
        else:
            # 2. Autonomous action selection
            action = agent.strategy.select_action(agent.state)
            await agent.execute(action)

        # 3. Publish status for dashboard (every N ticks)
        if agent.tick_count % STATUS_BROADCAST_INTERVAL == 0:
            await agent.publish_status()

        agent.tick_count += 1
        await asyncio.sleep(agent.tick_interval)
```

### 3.5 Agent Manifest Extension

```json
{
  "agents": [
    { "id": "user0", "cmd": "python", "args": ["src/user/main.py", "0"],
      "restart": "on-failure", "tick_interval": 60 },
    { "id": "user1", "cmd": "python", "args": ["src/user/main.py", "1"],
      "restart": "on-failure", "tick_interval": 45 }
  ]
}
```

Different tick intervals per agent create natural variation in market activity.

### 3.6 Infrastructure Agents

Infrastructure agents (`nostr-relay`, `cashu-mint`) do **not** run an activity loop. They are servers that respond to requests. Their liveness is monitored only via OS-level child process exit detection (Section 5.3), not via heartbeats.

---

## 4. Agent States & Process Monitoring

### 4.1 Agent States

`system-master` maintains a state machine for each agent:

```
         spawn
  [STOPPED] ──────> [STARTING]
      ^                  │
      │           initialization
      │            complete
      │                  v
      │             [RUNNING]
      │                  │
      │            process exit
      │             detected
      │                  │
      │           restart policy
      │              applied
      │            /          \
      │     restart=yes    restart=no
      │         │               │
      │         v               v
      └──── [STARTING]     [STOPPED]
```

States:

| State | Description |
|---|---|
| `STOPPED` | Not running; no PID |
| `STARTING` | Process spawned; waiting for initialization to complete |
| `RUNNING` | Process alive; activity loop active (user agents) or serving requests (infrastructure) |

There is no `UNHEALTHY` state. If a process exits, it is immediately either restarted or stopped based on policy.

### 4.2 Process Monitoring

`system-master` monitors agents via **OS-level child process handling** only:

- Detects child process exit via `waitpid` / process handle callbacks.
- On unexpected exit → apply restart policy (Section 5).
- No heartbeat-based health checks. No polling. No timeouts.

This is simple and reliable: if the process is running, it's alive.

### 4.3 Status Broadcasting (Observability)

User agents optionally publish **status events** (kind `4300`) every ~5 minutes for dashboard display:

```json
{
  "kind": 4300,
  "tags": [
    ["agent_name", "user3"],
    ["role", "user-agent"]
  ],
  "content": "{\"balance_sats\":500,\"programs_owned\":3,\"programs_listed\":1,\"active_trades\":0,\"last_action\":\"browse_marketplace\",\"tick_count\":42,\"ts\":1700000000}"
}
```

Fields in `content`:

| Field | Type | Description |
|---|---|---|
| `balance_sats` | int | Current Cashu wallet balance in sats |
| `programs_owned` | int | Number of programs the agent has |
| `programs_listed` | int | Number of programs listed for sale |
| `active_trades` | int | Number of in-flight trade negotiations |
| `last_action` | string | What the agent did on its last tick |
| `tick_count` | int | Total ticks since agent started |
| `ts` | int | Unix timestamp |

**Important**: These status events are purely informational for the dashboard. `system-master` does **not** consume or act on them.

### 4.4 System Dashboard

A simple status endpoint or CLI command that prints a table:

```
Agent         State      PID     Uptime    Restarts  Last Action
───────────── ────────── ─────── ───────── ───────── ──────────────────
nostr-relay   RUNNING    12345   1h 23m    0         (server)
cashu-mint    RUNNING    12346   1h 23m    0         (server)
user0         RUNNING    12350   1h 22m    1         generate_program
user1         RUNNING    12351   0h 04m    3         browse_marketplace
...
user9         RUNNING    12359   1h 22m    0         idle
```

---

## 5. Agent Lifecycle

### 5.1 Start

1. `system-master` reads the agent manifest.
2. Spawns the agent process, sets state to `STARTING`.
3. Starts a **startup timeout** of **30 seconds**.
4. If the agent completes initialization (connects to relay, loads wallet) within the timeout, state becomes `RUNNING`.
5. If the timeout expires, the restart policy is applied.

### 5.2 Graceful Stop

1. `system-master` sends `SIGTERM` to the agent process.
2. Agent receives the signal, completes any in-flight trade, persists state to disk, and exits with code 0.
3. `system-master` waits up to **10 seconds** for the process to exit.
4. If the process does not exit, `system-master` sends `SIGKILL`.
5. State becomes `STOPPED`.

### 5.3 Crash Detection

A crash is detected when:
- The child process exits unexpectedly (exit code != 0, or signal-killed).
- `system-master` receives the `exit` event on the child process handle.

On crash:
1. The crash is logged with exit code/signal, timestamp, and last 50 lines of the agent's stderr.
2. Restart policy is applied immediately.

### 5.4 Restart Policy

Each agent has a `restart` field in the manifest:

| Policy | Behavior |
|---|---|
| `always` | Always restart, regardless of exit code. Used for infrastructure agents. |
| `on-failure` | Restart only if exit code != 0. Used for user agents. |
| `never` | Do not restart. Used for one-shot tasks. |

### 5.5 Restart Backoff

To prevent rapid restart loops (crash-restart-crash), restarts use **exponential backoff with jitter**:

| Restart # | Delay |
|---|---|
| 1 | 1 second |
| 2 | 2 seconds |
| 3 | 4 seconds |
| 4 | 8 seconds |
| 5+ | 16 seconds (capped) |

Plus random jitter of 0--500ms.

The backoff counter **resets to 0** after the agent has been `RUNNING` for at least **60 seconds** continuously.

### 5.6 Maximum Restart Limit

If an agent restarts **10 times within 5 minutes**, it is placed in `STOPPED` state and flagged as `restart-exhausted`. `system-master` logs a critical error. Manual intervention (or a command from the operator) is required to restart it.

---

## 6. Inter-Agent Supervision

### 6.1 Supervision Tree

```
system-master (root supervisor)
├── nostr-relay          [restart: always]
├── cashu-mint           [restart: always]
├── user0                [restart: on-failure]
├── user1                [restart: on-failure]
├── ...
└── user9                [restart: on-failure]
```

`system-master` is the **single supervisor**. There is no nested supervision for the initial design -- the agent count (13) is small enough that a flat tree is sufficient and simpler to reason about.

### 6.2 Dependency-Aware Restart

When an infrastructure agent (`nostr-relay` or `cashu-mint`) crashes and restarts:

1. `system-master` transitions all dependent agents (user agents) to a **`WAITING`** sub-state.
2. User agents are notified via `SIGUSR1` to pause external operations and buffer messages.
3. Once the infrastructure agent returns to `RUNNING`, `system-master` sends `SIGUSR2` to user agents to resume.

This prevents user agents from failing en masse when the relay or mint has a brief outage.

### 6.3 Cascade Stop

When `system-master` itself is stopped (receives `SIGTERM` or `SIGINT`):

1. Stop user agents first (Phase 2 reverse): send `SIGTERM` to `user9`..`user0`, wait for exit.
2. Stop infrastructure agents (Phase 1 reverse): send `SIGTERM` to `cashu-mint`, then `nostr-relay`.
3. Exit cleanly.

This ensures user agents can complete in-flight transactions before the mint/relay go down.

---

## 7. Crash Recovery and Data Integrity

### 7.1 Agent State Persistence

Each agent persists its state to disk periodically:

- **Location**: `data/agents/<agent-id>/state.json`
- **Frequency**: Every 30 seconds, and on graceful shutdown.
- **Content**: Agent-specific (e.g., wallet balance for user agents, pending transactions).

On restart, the agent reads `state.json` to resume from the last checkpoint.

### 7.2 system-master Crash Recovery

If `system-master` itself crashes (e.g., killed by OOM or operator error):

1. On restart, `system-master` reads `data/system-master/pids.json` which records the PIDs of all spawned children.
2. For each recorded PID, it checks if the process is still alive (`kill -0 <pid>`).
3. If alive, it re-attaches monitoring (re-registers child process handles).
4. If dead, it applies the restart policy.

This allows `system-master` to recover without restarting all agents.

### 7.3 Orphan Process Cleanup

On startup, `system-master` also scans for orphan processes (agents running without a supervisor) by checking for processes matching expected command patterns. Orphans are adopted or killed depending on configuration.

---

## 8. Scalability Considerations

### 8.1 Current Scale

- 10 user agents + 3 system processes = 13 total processes.
- Status broadcasts: 13 agents × 1 event per ~5 minutes = negligible relay load.
- Trade activity: ~1–2 Nostr events/minute per user agent during active trading.

### 8.2 Scaling Beyond 10 Users

If the system needs more than 10 user agents:

- The agent manifest supports arbitrary entries; adding `user10`..`user99` requires only config changes.
- Activity tick interval can be increased to 120s or 300s to reduce event volume.
- User agents can be grouped into **supervision groups** (e.g., `user0-9`, `user10-19`) with a sub-supervisor per group, creating a two-level tree.

### 8.3 Resource Limits

Each agent process should be constrained to prevent a single runaway agent from starving others:

| Resource | Limit | Mechanism |
|---|---|---|
| Memory | 256 MB per user agent | `resource.setrlimit()` (Python) or cgroup |
| CPU | No hard limit (WSL2 shares host CPU) | Monitor via status broadcast or `ps` |
| File descriptors | 1024 per agent | `ulimit -n` |
| Disk (logs) | 50 MB per agent | Log rotation (keep last 5 files x 10 MB) |

### 8.4 WSL2-Specific Notes

- **No systemd by default**: WSL2 distributions may or may not have systemd enabled. The custom process manager avoids this dependency entirely.
- **Filesystem performance**: Agent state files are written to the Linux filesystem (`/home/...`), not `/mnt/c/`, to avoid NTFS translation overhead.
- **Networking**: The Nostr relay binds to `127.0.0.1` (localhost). All agents connect via `ws://127.0.0.1:7777`. The Cashu mint is available at `http://127.0.0.1:3338`. No Windows firewall rules needed.
- **Process signals**: `SIGTERM`, `SIGKILL`, `SIGUSR1`, `SIGUSR2` all work correctly on WSL2.

---

## 9. Logging and Observability

### 9.1 Log Structure

```
logs/
├── system-master/
│   ├── state.log        # State transitions for all agents
│   └── master.log       # system-master's own operational log
├── nostr-relay/
│   ├── stdout.log
│   └── stderr.log
├── cashu-mint/
│   ├── stdout.log
│   └── stderr.log
├── user0/
│   ├── stdout.log
│   └── stderr.log
...
```

### 9.2 Log Rotation

- Each log file is rotated at **10 MB**.
- Last **5 rotated files** are kept per agent.
- Rotation is handled by `system-master` (or a simple built-in rotator), not an external tool.

### 9.3 Structured Logging

All agents emit JSON-formatted log lines:

```json
{"ts":"2025-01-15T12:00:00Z","level":"info","agent":"user3","msg":"Published program listing","event_id":"abc123"}
```

This allows simple `grep`/`jq` based analysis without specialized tooling.

---

## 10. Control Interface

### 10.1 CLI Commands

`system-master` exposes a control interface via a Unix domain socket at `data/system-master/control.sock`. An operator CLI tool (`zapctl`) sends commands:

| Command | Description |
|---|---|
| `zapctl status` | Print agent status table (Section 4.3) |
| `zapctl stop <agent-id>` | Gracefully stop an agent |
| `zapctl start <agent-id>` | Start a stopped agent |
| `zapctl restart <agent-id>` | Graceful restart |
| `zapctl logs <agent-id>` | Tail agent logs |
| `zapctl shutdown` | Graceful shutdown of entire system |

### 10.2 Nostr-Based Control (Future)

In a later phase, `system-master` could accept control commands as Nostr events (kind `30079`), allowing remote management through the relay. This is out of scope for the initial implementation.

---

## 11. Summary of Key Design Decisions

| Decision | Rationale |
|---|---|
| Custom process manager over systemd | Avoids root requirement; works on all WSL2 setups; tighter integration with Nostr |
| Autonomous activity loop (~60s tick) | Agents self-direct economic actions (create, browse, trade) when idle |
| OS-level process monitoring only | Simple `waitpid`-based crash detection; no heartbeat polling needed |
| Flat supervision tree | 13 agents is small; simplicity over premature abstraction |
| Exponential backoff on restarts | Prevents crash loops from consuming resources |
| JSON state files for recovery | Simple, human-readable, no database dependency |
| Unix domain socket for control | Secure (filesystem permissions), low overhead, no network exposure |
