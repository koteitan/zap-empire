"""
Zap Empire System Master — Process supervisor for all agents.

Spawns and monitors infrastructure (strfry relay, Cashu mint) and user agents.
Handles graceful shutdown, crash recovery, and restart policies.
"""

import asyncio
import json
import logging
import os
import signal
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("system-master")


class AgentState(Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"


class RestartPolicy(Enum):
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    NEVER = "never"


@dataclass
class AgentInfo:
    agent_id: str
    name: str
    command: str
    restart_policy: RestartPolicy
    tick_interval: Optional[int] = None

    # Runtime state
    state: AgentState = AgentState.STOPPED
    pid: Optional[int] = None
    process: Optional[subprocess.Popen] = None
    started_at: Optional[float] = None
    restart_count: int = 0
    last_restart_time: float = 0
    restart_backoff: float = 1.0
    restart_times: list = field(default_factory=list)

    # Log file handles
    stdout_log: Optional[object] = None
    stderr_log: Optional[object] = None


class Supervisor:
    """Top-level process supervisor for Zap Empire."""

    def __init__(self, project_dir: str, manifest_path: str = "config/agents.json"):
        self.project_dir = Path(project_dir)
        self.manifest_path = self.project_dir / manifest_path
        self.agents: Dict[str, AgentInfo] = {}
        self.running = False
        self.pids_file = self.project_dir / "data" / "system-master" / "pids.json"

        # Control socket
        self.control_socket_path = self.project_dir / "data" / "system-master" / "control.sock"
        self.control_server = None

        # Ensure directories exist
        (self.project_dir / "data" / "system-master").mkdir(parents=True, exist_ok=True)
        (self.project_dir / "logs").mkdir(parents=True, exist_ok=True)

    def load_manifest(self):
        """Load agent manifest from config/agents.json."""
        with open(self.manifest_path) as f:
            manifest = json.load(f)

        for agent_def in manifest["agents"]:
            agent_id = agent_def["id"]
            restart_str = agent_def.get("restart_policy", "on-failure")

            self.agents[agent_id] = AgentInfo(
                agent_id=agent_id,
                name=agent_def.get("name", agent_id),
                command=agent_def["command"],
                restart_policy=RestartPolicy(restart_str),
                tick_interval=agent_def.get("tick_interval"),
            )

        logger.info(f"Loaded {len(self.agents)} agents from manifest")

    def _get_log_dir(self, agent_id: str) -> Path:
        log_dir = self.project_dir / "logs" / agent_id
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def _open_logs(self, agent: AgentInfo):
        """Open log files for an agent."""
        log_dir = self._get_log_dir(agent.agent_id)
        agent.stdout_log = open(log_dir / "stdout.log", "a", buffering=1)
        agent.stderr_log = open(log_dir / "stderr.log", "a", buffering=1)

    def _close_logs(self, agent: AgentInfo):
        """Close log files for an agent."""
        if agent.stdout_log:
            agent.stdout_log.close()
            agent.stdout_log = None
        if agent.stderr_log:
            agent.stderr_log.close()
            agent.stderr_log = None

    def spawn_agent(self, agent_id: str) -> bool:
        """Spawn a single agent process."""
        agent = self.agents.get(agent_id)
        if not agent:
            logger.error(f"Unknown agent: {agent_id}")
            return False

        if agent.state != AgentState.STOPPED:
            logger.warning(f"{agent_id} is already {agent.state.value}")
            return False

        agent.state = AgentState.STARTING
        self._open_logs(agent)

        # Parse command
        parts = agent.command.split()
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        # For scripts, make executable
        cmd_path = self.project_dir / cmd
        if cmd_path.exists() and cmd_path.suffix == ".sh":
            cmd_path.chmod(0o755)

        try:
            # Ensure data directory for agent exists
            agent_data_dir = self.project_dir / "data" / agent_id
            agent_data_dir.mkdir(parents=True, exist_ok=True)

            process = subprocess.Popen(
                [cmd] + args,
                stdout=agent.stdout_log,
                stderr=agent.stderr_log,
                cwd=str(self.project_dir),
                env={**os.environ, "AGENT_ID": agent_id},
                preexec_fn=os.setsid,  # New process group for clean shutdown
            )

            agent.process = process
            agent.pid = process.pid
            agent.started_at = time.time()
            agent.state = AgentState.RUNNING
            logger.info(f"Spawned {agent_id} ({agent.name}) PID={process.pid}")
            self._save_pids()
            return True

        except Exception as e:
            logger.error(f"Failed to spawn {agent_id}: {e}")
            agent.state = AgentState.STOPPED
            self._close_logs(agent)
            return False

    def stop_agent(self, agent_id: str, timeout: float = 10.0) -> bool:
        """Gracefully stop an agent (SIGTERM, then SIGKILL after timeout)."""
        agent = self.agents.get(agent_id)
        if not agent or agent.state == AgentState.STOPPED:
            return True

        if agent.process is None:
            agent.state = AgentState.STOPPED
            return True

        logger.info(f"Stopping {agent_id} (PID={agent.pid})...")

        try:
            agent.process.terminate()  # SIGTERM
            try:
                agent.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning(f"{agent_id} did not stop gracefully, sending SIGKILL")
                agent.process.kill()
                agent.process.wait(timeout=5)
        except ProcessLookupError:
            pass  # Already dead

        agent.state = AgentState.STOPPED
        agent.process = None
        agent.pid = None
        self._close_logs(agent)
        logger.info(f"{agent_id} stopped")
        self._save_pids()
        return True

    def _check_agent_restart(self, agent: AgentInfo):
        """Apply restart policy after an agent exits."""
        exit_code = agent.process.returncode if agent.process else -1
        agent.state = AgentState.STOPPED
        agent.process = None
        agent.pid = None
        self._close_logs(agent)

        logger.warning(f"{agent.agent_id} exited with code {exit_code}")

        # Check restart policy
        should_restart = False
        if agent.restart_policy == RestartPolicy.ALWAYS:
            should_restart = True
        elif agent.restart_policy == RestartPolicy.ON_FAILURE and exit_code != 0:
            should_restart = True

        if not should_restart:
            logger.info(f"{agent.agent_id}: restart policy = {agent.restart_policy.value}, not restarting")
            return

        # Check restart limit (10 restarts in 5 minutes)
        now = time.time()
        agent.restart_times = [t for t in agent.restart_times if now - t < 300]
        if len(agent.restart_times) >= 10:
            logger.error(f"{agent.agent_id}: restart limit exceeded (10 in 5min), staying stopped")
            return

        # Exponential backoff
        agent.restart_count += 1
        delay = min(agent.restart_backoff, 16)
        agent.restart_backoff = min(agent.restart_backoff * 2, 16)

        logger.info(f"{agent.agent_id}: restarting in {delay:.1f}s (restart #{agent.restart_count})")
        agent.restart_times.append(now)

        # Schedule restart
        asyncio.get_event_loop().call_later(delay, lambda: self.spawn_agent(agent.agent_id))

    def _save_pids(self):
        """Save current PIDs for crash recovery."""
        pids = {}
        for agent_id, agent in self.agents.items():
            if agent.pid:
                pids[agent_id] = {
                    "pid": agent.pid,
                    "started_at": agent.started_at,
                }
        self.pids_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pids_file, "w") as f:
            json.dump(pids, f, indent=2)

    def _try_recover_pids(self):
        """On startup, try to re-attach to previously running agents."""
        if not self.pids_file.exists():
            return

        try:
            with open(self.pids_file) as f:
                saved_pids = json.load(f)
        except Exception:
            return

        for agent_id, info in saved_pids.items():
            pid = info.get("pid")
            if not pid or agent_id not in self.agents:
                continue

            # Check if process is alive
            try:
                os.kill(pid, 0)
                logger.info(f"Recovered {agent_id} PID={pid} (still running)")
                agent = self.agents[agent_id]
                agent.pid = pid
                agent.started_at = info.get("started_at", time.time())
                agent.state = AgentState.RUNNING
            except ProcessLookupError:
                logger.info(f"Previous {agent_id} PID={pid} is dead, will respawn")

    async def _wait_for_ready(self, host: str, port: int, timeout: float = 30) -> bool:
        """Wait for a TCP port to accept connections."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect((host, port))
                s.close()
                return True
            except (ConnectionRefusedError, socket.timeout, OSError):
                await asyncio.sleep(1)
        return False

    async def start_all(self):
        """Start all agents in dependency order."""
        self.running = True
        self.load_manifest()
        self._try_recover_pids()

        # Phase 1: Infrastructure
        infra_agents = ["nostr-relay", "cashu-mint"]
        for agent_id in infra_agents:
            if agent_id in self.agents and self.agents[agent_id].state == AgentState.STOPPED:
                self.spawn_agent(agent_id)

        # Wait for infrastructure to be ready
        logger.info("Waiting for relay (port 7777)...")
        if await self._wait_for_ready("127.0.0.1", 7777, timeout=60):
            logger.info("Relay is ready!")
        else:
            logger.warning("Relay not responding on port 7777, proceeding anyway...")

        logger.info("Waiting for mint (port 3338)...")
        if await self._wait_for_ready("127.0.0.1", 3338, timeout=60):
            logger.info("Mint is ready!")
        else:
            logger.warning("Mint not responding on port 3338, proceeding anyway...")

        # Phase 2: User agents
        for agent_id, agent in self.agents.items():
            if agent_id.startswith("user") and agent.state == AgentState.STOPPED:
                self.spawn_agent(agent_id)
                await asyncio.sleep(0.5)  # Stagger startup

        logger.info("All agents started!")

    async def shutdown(self):
        """Graceful cascade shutdown."""
        logger.info("Initiating shutdown...")
        self.running = False

        # Phase 1: Stop user agents (reverse order)
        user_agents = sorted(
            [a for a in self.agents.values() if a.agent_id.startswith("user")],
            key=lambda a: a.agent_id,
            reverse=True,
        )
        for agent in user_agents:
            if agent.state != AgentState.STOPPED:
                self.stop_agent(agent.agent_id)

        # Phase 2: Stop infrastructure
        for agent_id in ["cashu-mint", "nostr-relay"]:
            if agent_id in self.agents:
                self.stop_agent(agent_id)

        # Close control socket
        if self.control_server:
            self.control_server.close()
            if self.control_socket_path.exists():
                self.control_socket_path.unlink()

        logger.info("Shutdown complete")

    async def monitor_loop(self):
        """Monitor running agents, detect exits, apply restart policy."""
        while self.running:
            for agent in self.agents.values():
                if agent.state == AgentState.RUNNING and agent.process:
                    ret = agent.process.poll()
                    if ret is not None:
                        self._check_agent_restart(agent)
                    elif agent.started_at and (time.time() - agent.started_at > 60):
                        # Reset backoff after 60s of stable running
                        agent.restart_backoff = 1.0
            await asyncio.sleep(2)

    def get_status(self) -> str:
        """Format status table."""
        lines = [
            f"{'Agent':<15} {'Name':<12} {'State':<10} {'PID':<8} {'Uptime':<10} {'Restarts'}",
            "-" * 75,
        ]
        for agent_id, agent in sorted(self.agents.items()):
            uptime = ""
            if agent.started_at and agent.state == AgentState.RUNNING:
                secs = int(time.time() - agent.started_at)
                mins, secs = divmod(secs, 60)
                hours, mins = divmod(mins, 60)
                uptime = f"{hours}h {mins:02d}m"

            lines.append(
                f"{agent_id:<15} {agent.name:<12} {agent.state.value:<10} "
                f"{str(agent.pid or '-'):<8} {uptime:<10} {agent.restart_count}"
            )
        return "\n".join(lines)

    async def start_control_server(self):
        """Start Unix domain socket control server for zapctl."""
        if self.control_socket_path.exists():
            self.control_socket_path.unlink()

        self.control_server = await asyncio.start_unix_server(
            self._handle_control_client,
            path=str(self.control_socket_path),
        )
        logger.info(f"Control server listening on {self.control_socket_path}")

    async def _handle_control_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a zapctl connection."""
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=5)
            if not data:
                writer.close()
                return

            command = data.decode("utf-8").strip()
            parts = command.split()
            cmd = parts[0] if parts else ""
            args = parts[1:] if len(parts) > 1 else []

            response = await self._execute_command(cmd, args)
            writer.write(response.encode("utf-8"))
            await writer.drain()
        except Exception as e:
            writer.write(f"Error: {e}\n".encode("utf-8"))
            await writer.drain()
        finally:
            writer.close()

    async def _execute_command(self, cmd: str, args: list) -> str:
        """Execute a control command."""
        if cmd == "status":
            return self.get_status() + "\n"

        elif cmd == "stop" and args:
            agent_id = args[0]
            if agent_id in self.agents:
                self.stop_agent(agent_id)
                return f"Stopped {agent_id}\n"
            return f"Unknown agent: {agent_id}\n"

        elif cmd == "start" and args:
            agent_id = args[0]
            if agent_id in self.agents:
                if self.spawn_agent(agent_id):
                    return f"Started {agent_id}\n"
                return f"Failed to start {agent_id}\n"
            return f"Unknown agent: {agent_id}\n"

        elif cmd == "restart" and args:
            agent_id = args[0]
            if agent_id in self.agents:
                self.stop_agent(agent_id)
                await asyncio.sleep(1)
                if self.spawn_agent(agent_id):
                    return f"Restarted {agent_id}\n"
                return f"Failed to restart {agent_id}\n"
            return f"Unknown agent: {agent_id}\n"

        elif cmd == "shutdown":
            asyncio.create_task(self.shutdown())
            return "Shutdown initiated\n"

        else:
            return (
                "Commands:\n"
                "  status              Show all agent statuses\n"
                "  start <agent-id>    Start an agent\n"
                "  stop <agent-id>     Stop an agent\n"
                "  restart <agent-id>  Restart an agent\n"
                "  shutdown            Shutdown entire system\n"
            )


async def main():
    """Main entry point for system-master."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    supervisor = Supervisor(project_dir)

    # Set up signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(supervisor.shutdown()))

    # Start
    await supervisor.start_control_server()
    await supervisor.start_all()
    await supervisor.monitor_loop()


if __name__ == "__main__":
    asyncio.run(main())
