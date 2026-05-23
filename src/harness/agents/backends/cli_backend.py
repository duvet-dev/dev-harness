"""CLI backend — subprocess tool execution.

Runs CLI tools (Claude Code, Aider, etc.) as subprocesses. Each tool has
a known invocation pattern defined in constitution.yaml. Supports timeout,
streaming output, and structured result parsing.

Backend name: 'cli'
"""

from __future__ import annotations

import asyncio
import os
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.agents.context import ContextPacket
from harness.agents.backends.base import (
    AbstractBackend,
    BackendConfigError,
    BackendError,
    BackendResult,
    BackendTimeoutError,
    Invocation,
)


@dataclass
class ToolDef:
    """Definition of a CLI tool that can be executed."""

    name: str
    binary: str
    template_args: list[str] = field(default_factory=list)
    timeout_seconds: int = 1800
    env_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class CliBackendConfig:
    """Configuration for the CLI backend."""

    tools: dict[str, ToolDef] = field(default_factory=dict)
    default_timeout: int = 1800

    @classmethod
    def from_dict(cls, config: dict) -> CliBackendConfig:
        c = cls()
        if "default_timeout" in config:
            c.default_timeout = int(config["default_timeout"])
        raw_tools = config.get("tools", {})
        for name, tdef in raw_tools.items():
            c.tools[name] = ToolDef(
                name=tdef.get("name", name),
                binary=tdef.get("binary", name),
                template_args=tdef.get("args", []),
                timeout_seconds=int(
                    tdef.get("timeout", c.default_timeout)
                ),
                env_overrides=tdef.get("env", {}),
            )
        return c


class CliBackend(AbstractBackend):
    """Backend that runs CLI tools as subprocesses."""

    name = "cli"

    def __init__(self, config: dict | None = None):
        self._config = CliBackendConfig.from_dict(config or {})

    async def prepare(self, packet: ContextPacket) -> Invocation:
        """Prepare a CLI invocation from context.

        Builds the command line from the spec_content, writing it
        to a temp file if needed, and resolving the tool to use.
        """
        # Determine which tool to use — from constraint_section or first available
        tool_name = packet.constraint_section.get(
            "tool", next(iter(self._config.tools.keys()), "default")
        )
        tool = self._config.tools.get(tool_name)
        if not tool:
            # Use first available tool
            tool = next(
                iter(self._config.tools.values()), ToolDef(name="default", binary="")
            )

        # Write spec content to a temp file for the tool to read
        work_dir = Path(packet.target_directory)
        spec_file = work_dir / "context.md"
        work_dir.mkdir(parents=True, exist_ok=True)

        spec_content = (
            f"# Task: {packet.task_id}\n"
            f"## Spec\n{packet.spec_content}\n"
            f"## Architecture Rules\n"
            + "\n".join(f"- {r}" for r in packet.architecture_rules)
        )
        spec_file.write_text(spec_content)

        # Build the command
        args = [
            a.replace("{spec_file}", str(spec_file))
            .replace("{project_dir}", str(packet.target_directory))
            for a in tool.template_args
        ]

        env = os.environ.copy()
        env.update(tool.env_overrides)

        return Invocation(
            command=tool.binary,
            args=args,
            env=env,
            work_dir=str(packet.target_directory),
            input_packet=packet,
            timeout_seconds=tool.timeout_seconds,
        )

    async def run(self, invocation: Invocation) -> BackendResult:
        """Execute the CLI command as a subprocess.

        When ``invocation.resolved_config`` has a ``cli`` type provider,
        its ``command`` field is used as the binary, overriding whatever
        was set during ``prepare()``.
        """
        start_time = time.monotonic()

        # Check for resolved CLI provider config override
        command = invocation.command
        args = invocation.args
        if invocation.resolved_config and invocation.resolved_config.get("type") == "cli":
            cli_command = invocation.resolved_config.get("command", "")
            if cli_command:
                command = cli_command
                # When using a configured CLI provider, discard template args
                # and pass the spec content directly via env or stdin
                args = []

        cmd = [command] + args

        # Build environment
        env = invocation.env if invocation.env else os.environ.copy()
        work_dir = invocation.work_dir or os.getcwd()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=work_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=invocation.timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                duration_ms = int((time.monotonic() - start_time) * 1000)
                return BackendResult(
                    status="timeout",
                    errors=[
                        f"CLI '{invocation.command}' timed out "
                        f"(>{invocation.timeout_seconds}s)"
                    ],
                    metrics={"duration_ms": duration_ms},
                )

            duration_ms = int((time.monotonic() - start_time) * 1000)

            stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

            artifacts: dict[str, str] = {}
            errors: list[str] = []

            if proc.returncode != 0:
                errors.append(
                    f"CLI '{invocation.command}' exited with code "
                    f"{proc.returncode}"
                )
                if stderr_text:
                    errors.append(stderr_text[:500])
                status = "failure"
            else:
                status = "success"

            # Capture stdout as log output
            if stdout_text:
                artifacts["stdout.log"] = stdout_text
            if stderr_text:
                artifacts["stderr.log"] = stderr_text

            # Also try to find any produced files in the working dir
            work_path = Path(work_dir)
            if work_path.exists():
                for f in work_path.iterdir():
                    if f.is_file() and f.suffix in (
                        ".py", ".md", ".txt", ".yaml", ".json", ".toml",
                    ):
                        if f.name not in artifacts:
                            artifacts[f.name] = f.read_text(encoding="utf-8", errors="replace")

            return BackendResult(
                status=status,
                output_dir=work_dir,
                artifacts=artifacts,
                errors=errors,
                metrics={
                    "duration_ms": duration_ms,
                    "return_code": proc.returncode,
                    "stdout_bytes": len(stdout_text),
                    "stderr_bytes": len(stderr_text),
                },
            )

        except FileNotFoundError:
            return BackendResult(
                status="failure",
                errors=[f"CLI tool not found: {invocation.command}"],
                metrics={"duration_ms": int((time.monotonic() - start_time) * 1000)},
            )
        except Exception as exc:
            return BackendResult(
                status="failure",
                errors=[f"CLI execution error: {exc}"],
                metrics={"duration_ms": int((time.monotonic() - start_time) * 1000)},
            )

    def validate_config(self, config: dict) -> list[str]:
        """Validate CLI backend configuration."""
        errors: list[str] = []
        bc = CliBackendConfig.from_dict(config)
        for name, tool in bc.tools.items():
            if not tool.binary:
                errors.append(f"tool '{name}': binary is required")
            if tool.timeout_seconds < 10:
                errors.append(f"tool '{name}': timeout must be >= 10")
        return errors
