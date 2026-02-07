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

Rather than using systemd (which requires root and complicates WSL2 setups) or a third-party supervisor like `supervisord`, Zap Empire uses a **custom lightweight process manager** written in the project's primary language. This gives us full control over lifecycle, heartbeat semantics, and inter-agent messaging without external dependencies.

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

`system-master` waits for Phase 1 agents to emit their first successful heartbeat before proceeding to Phase 2.

---

## 3. Heartbeat Mechanism

### 3.1 Design

Every managed agent periodically sends a **heartbeat message** to `system-master`. Heartbeats use the project's own Nostr relay as the transport layer, keeping the design consistent with inter-agent communication.

| Parameter | Value |
|---|---|
| Heartbeat interval | **5 seconds** |
| Heartbeat timeout (dead threshold) | **15 seconds** (3 missed beats) |
| Heartbeat Nostr event kind | `4300` (regular event) |
| Heartbeat tags | `["agent_name", "<id>"]`, `["role", "<role>"]` |

### 3.2 Heartbeat Payload

Each heartbeat is a Nostr event published to the local relay:

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

Fields in `content`:

| Field | Type | Description |
|---|---|---|
| `status` | string | `healthy`, `degraded`, or `shutting-down` |
| `uptime_secs` | int | Seconds since agent started |
| `mem_mb` | int | Resident memory in MB |
| `balance_sats` | int | Current Cashu wallet balance in sats |
| `programs_owned` | int | Number of programs the agent has |
| `programs_listed` | int | Number of programs listed for sale |
| `active_trades` | int | Number of in-flight trade negotiations |
| `ts` | int | Unix timestamp of heartbeat |

### 3.3 Fallback: Pipe-Based Heartbeat

If the Nostr relay itself is the agent being monitored (chicken-and-egg problem), `system-master` monitors `nostr-relay` via a **secondary channel**:

- `nostr-relay` writes a heartbeat line to its `stdout` every 5 seconds.
- `system-master` reads the child process pipe directly.
- Format: `HEARTBEAT <unix_timestamp> <status>`

This ensures `nostr-relay` health is tracked even before (or if) the relay is unavailable.

---

## 4. Health Monitoring

### 4.1 Agent States

`system-master` maintains a state machine for each agent:

```
         spawn
  [STOPPED] ──────> [STARTING]
      ^                  │
      │           first heartbeat
      │                  v
      │             [RUNNING]
      │            /         \
      │    heartbeat          timeout / crash
      │    received            detected
      │        │                  │
      │        v                  v
      │    [RUNNING]         [UNHEALTHY]
      │                          │
      │                   restart policy
      │                   applied
      │                  /          \
      │          restart=yes     restart=no
      │              │                │
      │              v                v
      └──────── [STARTING]      [STOPPED]
```

States:

| State | Description |
|---|---|
| `STOPPED` | Not running; no PID |
| `STARTING` | Process spawned; waiting for first heartbeat |
| `RUNNING` | Healthy; heartbeats arriving on time |
| `UNHEALTHY` | Heartbeat missed beyond timeout threshold |

### 4.2 Health Check Loop

`system-master` runs a health check loop every **5 seconds**:

1. For each agent, compute `time_since_last_heartbeat`.
2. If `>= 15s` and state is `RUNNING`, transition to `UNHEALTHY`.
3. If `UNHEALTHY`, apply the agent's restart policy (see Section 5).
4. If a heartbeat arrives for a `STARTING` agent, transition to `RUNNING`.
5. Log all state transitions to `logs/system-master/state.log`.

### 4.3 System Dashboard (Optional, Phase 2)

A simple status endpoint or CLI command that prints a table:

```
Agent         State      Last Beat   Uptime    Restarts
───────────── ────────── ─────────── ───────── ────────
nostr-relay   RUNNING    2s ago      1h 23m    0
cashu-mint    RUNNING    1s ago      1h 23m    0
user0         RUNNING    3s ago      1h 22m    1
user1         UNHEALTHY  18s ago     0h 04m    3
...
user9         RUNNING    0s ago      1h 22m    0
```

---

## 5. Agent Lifecycle

### 5.1 Start

1. `system-master` reads the agent manifest.
2. Spawns the agent process, sets state to `STARTING`.
3. Starts a **startup timeout** of **30 seconds**.
4. If the agent sends its first heartbeat within the timeout, state becomes `RUNNING`.
5. If the timeout expires without a heartbeat, state becomes `UNHEALTHY` and the restart policy is applied.

### 5.2 Graceful Stop

1. `system-master` sends `SIGTERM` to the agent process.
2. Agent receives the signal, publishes a final heartbeat with `status: "shutting-down"`, performs cleanup, and exits with code 0.
3. `system-master` waits up to **10 seconds** for the process to exit.
4. If the process does not exit, `system-master` sends `SIGKILL`.
5. State becomes `STOPPED`.

### 5.3 Crash Detection

A crash is detected when:
- The child process exits unexpectedly (exit code != 0, or signal-killed).
- `system-master` receives the `exit` event on the child process handle.

On crash:
1. State transitions to `UNHEALTHY`.
2. The crash is logged with exit code/signal, timestamp, and last 50 lines of the agent's stderr.
3. Restart policy is applied immediately.

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
3. If alive, it re-attaches monitoring (re-subscribes to heartbeats, re-pipes stdout for relay).
4. If dead, it applies the restart policy.

This allows `system-master` to recover without restarting all agents.

### 7.3 Orphan Process Cleanup

On startup, `system-master` also scans for orphan processes (agents running without a supervisor) by checking for processes matching expected command patterns. Orphans are adopted or killed depending on configuration.

---

## 8. Scalability Considerations

### 8.1 Current Scale

- 10 user agents + 3 system processes = 13 total processes.
- Heartbeat traffic: 13 events every 5 seconds = ~2.6 events/second on the local relay.
- This is trivially handled by any Nostr relay implementation.

### 8.2 Scaling Beyond 10 Users

If the system needs more than 10 user agents:

- The agent manifest supports arbitrary entries; adding `user10`..`user99` requires only config changes.
- Heartbeat interval can be increased to 10s or 15s if relay load becomes a concern.
- User agents can be grouped into **supervision groups** (e.g., `user0-9`, `user10-19`) with a sub-supervisor per group, creating a two-level tree.

### 8.3 Resource Limits

Each agent process should be constrained to prevent a single runaway agent from starving others:

| Resource | Limit | Mechanism |
|---|---|---|
| Memory | 256 MB per user agent | `resource.setrlimit()` (Python) or cgroup |
| CPU | No hard limit (WSL2 shares host CPU) | Monitor via heartbeat `cpu_pct` field |
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
| Nostr-based heartbeats | Reuses existing infrastructure; heartbeats are observable by any relay subscriber |
| Pipe fallback for relay monitoring | Solves the chicken-and-egg problem of monitoring the relay via the relay |
| Flat supervision tree | 13 agents is small; simplicity over premature abstraction |
| Exponential backoff on restarts | Prevents crash loops from consuming resources |
| JSON state files for recovery | Simple, human-readable, no database dependency |
| Unix domain socket for control | Secure (filesystem permissions), low overhead, no network exposure |
