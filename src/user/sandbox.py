"""Sandboxed program execution and validation."""

import os
import subprocess
import tempfile
import logging

logger = logging.getLogger(__name__)

FORBIDDEN_IMPORTS = [
    "os.system", "subprocess", "socket", "http.server",
    "shutil.rmtree", "shutil.move", "os.remove", "os.unlink",
    "__import__", "eval(", "exec(",
]


class Sandbox:
    """Sandbox for testing generated programs before listing."""

    def __init__(self, timeout: int = 5, memory_mb: int = 64):
        self.timeout = timeout
        self.memory_mb = memory_mb

    def test(self, source_code: str) -> bool:
        """Test a program in a restricted sandbox.

        Returns True if:
        1. No forbidden imports
        2. Valid Python syntax
        3. Runs and exits cleanly within timeout
        4. Produces non-empty stdout
        5. Source is between 100 bytes and 50KB
        """
        # Size check
        if len(source_code) < 100 or len(source_code) > 50_000:
            logger.debug("Source size out of range")
            return False

        # Static analysis - check for forbidden patterns
        for pattern in FORBIDDEN_IMPORTS:
            if pattern in source_code:
                logger.debug(f"Forbidden pattern found: {pattern}")
                return False

        # Syntax check
        try:
            compile(source_code, "<sandbox-test>", "exec")
        except SyntaxError as e:
            logger.debug(f"Syntax error: {e}")
            return False

        # Execute in sandbox
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
        ) as f:
            f.write(source_code)
            f.flush()
            tmp_path = f.name

        try:
            # Restricted environment
            restricted_env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": tempfile.gettempdir(),
                "LANG": "en_US.UTF-8",
            }

            result = subprocess.run(
                ["python3", tmp_path],
                timeout=self.timeout,
                capture_output=True,
                cwd=tempfile.gettempdir(),
                env=restricted_env,
            )

            if result.returncode != 0:
                logger.debug(
                    f"Program exited with code {result.returncode}: "
                    f"{result.stderr.decode('utf-8', errors='replace')[:200]}"
                )
                return False

            if len(result.stdout) == 0:
                logger.debug("Program produced no output")
                return False

            return True

        except subprocess.TimeoutExpired:
            logger.debug("Program timed out")
            return False
        except Exception as e:
            logger.debug(f"Sandbox error: {e}")
            return False
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
