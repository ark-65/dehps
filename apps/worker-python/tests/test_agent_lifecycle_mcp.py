from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest
import tomllib
from dehps.agents.lifecycle_adapter import TOOL_INPUT_SCHEMAS, TOOL_NAMES
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

WORKER_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.anyio
async def test_stdio_initialize_tools_list_and_db_free_invalid_call() -> None:
    parameters = StdioServerParameters(
        command=str(WORKER_ROOT / ".venv/bin/python"),
        args=["-m", "dehps.agents.lifecycle_mcp"],
        cwd=str(WORKER_ROOT),
        env={**os.environ, "PYTHONPATH": str(WORKER_ROOT)},
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        initialized = await session.initialize()
        assert initialized.serverInfo.name == "dehps-lifecycle"
        listed = await session.list_tools()
        assert tuple(tool.name for tool in listed.tools) == TOOL_NAMES
        assert [tool.inputSchema for tool in listed.tools] == [
            TOOL_INPUT_SCHEMAS[name] for name in TOOL_NAMES
        ]
        invalid = await session.call_tool("not_a_lifecycle_tool", {})
        assert invalid.isError is True
        assert "unknown" in invalid.content[0].text.lower()


def test_server_module_contains_no_generic_capability_names() -> None:
    forbidden = {"shell", "sql", "git", "supervisor", "workload", "artifact_get", "promotion", "p3", "p4"}
    assert not any(token in name.lower() for name in TOOL_NAMES for token in forbidden)


def test_project_config_and_authorized_pycharm_files_are_frozen() -> None:
    project_root = WORKER_ROOT.parents[1]
    config = tomllib.loads((project_root / ".codex/config.toml").read_text())
    server = config["mcp_servers"]["dehps_lifecycle"]
    assert server == {
        "command": "/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python",
        "args": ["-m", "dehps.agents.lifecycle_mcp"],
        "cwd": "/home/ark/workspace/dehps/apps/worker-python",
        "enabled": True,
        "required": True,
        "startup_timeout_sec": 10,
        "tool_timeout_sec": 30,
        "default_tools_approval_mode": "auto",
        "enabled_tools": list(TOOL_NAMES),
    }
    expected = {
        ".idea/.gitignore": "7ade64d47c121e7a8250564beeb6f0f521f2c27dc8e0ef4f3e11637453bec907",
        ".idea/dehps.iml": "0266269f1c2d97153dec670e72e68dd6a0077b8952b9e5ad3a972f65212e6ef7",
        ".idea/inspectionProfiles/profiles_settings.xml": "6172c5997eeb3cd19c9ca2b5b97d6e2983cdd1fa60b2460d7bbb74055edcaa46",
        ".idea/misc.xml": "b7f252db0a1a8eacefa0262eb38b05d6fef9f9b9070efcd45317adc6098534b0",
        ".idea/modules.xml": "b6c69aeda709d7b0e8b42deac6f3b2cc32a51f2a087b246991a6d28e430c446a",
        ".idea/vcs.xml": "6323e12648862a0a96fc0d7877672817d6cd91e2c2a3c3d78f1090db23c6e88e",
    }
    for relative, digest in expected.items():
        assert hashlib.sha256((project_root / relative).read_bytes()).hexdigest() == digest
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".idea/workspace.xml"],
        cwd=project_root,
        check=False,
    )
    assert ignored.returncode == 0
