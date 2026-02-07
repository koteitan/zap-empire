#!/usr/bin/env python3
"""
zapctl — CLI control tool for Zap Empire system-master.

Communicates with system-master via Unix domain socket.

Usage:
    zapctl status              Show all agent statuses
    zapctl start <agent-id>    Start an agent
    zapctl stop <agent-id>     Stop an agent
    zapctl restart <agent-id>  Restart an agent
    zapctl logs <agent-id>     Tail agent logs
    zapctl shutdown            Shutdown entire system
"""

import os
import socket
import subprocess
import sys
from pathlib import Path


def find_project_dir() -> Path:
    """Find the project root (walk up to find config/agents.json)."""
    path = Path.cwd()
    while path != path.parent:
        if (path / "config" / "agents.json").exists():
            return path
        path = path.parent
    return Path.cwd()


def get_socket_path() -> Path:
    project_dir = find_project_dir()
    return project_dir / "data" / "system-master" / "control.sock"


def send_command(command: str) -> str:
    """Send a command to system-master via Unix socket."""
    sock_path = get_socket_path()

    if not sock_path.exists():
        print("Error: system-master is not running (control socket not found)")
        print(f"  Expected: {sock_path}")
        sys.exit(1)

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(str(sock_path))
        sock.sendall(command.encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)

        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk

        sock.close()
        return response.decode("utf-8")

    except ConnectionRefusedError:
        print("Error: system-master is not accepting connections")
        sys.exit(1)
    except socket.timeout:
        print("Error: system-master did not respond in time")
        sys.exit(1)


def cmd_status():
    """Show status of all agents."""
    print(send_command("status"), end="")


def cmd_start(agent_id: str):
    """Start a specific agent."""
    print(send_command(f"start {agent_id}"), end="")


def cmd_stop(agent_id: str):
    """Stop a specific agent."""
    print(send_command(f"stop {agent_id}"), end="")


def cmd_restart(agent_id: str):
    """Restart a specific agent."""
    print(send_command(f"restart {agent_id}"), end="")


def cmd_logs(agent_id: str):
    """Tail logs for an agent."""
    project_dir = find_project_dir()
    log_file = project_dir / "logs" / agent_id / "stdout.log"

    if not log_file.exists():
        print(f"No logs found for {agent_id}")
        print(f"  Expected: {log_file}")
        sys.exit(1)

    try:
        subprocess.run(["tail", "-f", "-n", "50", str(log_file)])
    except KeyboardInterrupt:
        pass


def cmd_shutdown():
    """Shutdown entire system."""
    confirm = input("Shutdown all agents? [y/N] ")
    if confirm.lower() == "y":
        print(send_command("shutdown"), end="")
    else:
        print("Cancelled")


def print_usage():
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        cmd_status()
    elif cmd == "start" and len(sys.argv) >= 3:
        cmd_start(sys.argv[2])
    elif cmd == "stop" and len(sys.argv) >= 3:
        cmd_stop(sys.argv[2])
    elif cmd == "restart" and len(sys.argv) >= 3:
        cmd_restart(sys.argv[2])
    elif cmd == "logs" and len(sys.argv) >= 3:
        cmd_logs(sys.argv[2])
    elif cmd == "shutdown":
        cmd_shutdown()
    elif cmd in ("-h", "--help", "help"):
        print_usage()
    else:
        print(f"Unknown command: {cmd}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
