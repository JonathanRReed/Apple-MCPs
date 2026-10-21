#!/usr/bin/env python3
"""Launch each built MCPB through its manifest command from an isolated directory."""

from __future__ import annotations

import asyncio
import json
import tempfile
import zipfile
from pathlib import Path

from mcp import StdioServerParameters
from protocol_smoke import check_server

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    bundles = sorted((ROOT / "dist" / "mcpb").glob("*.mcpb"))
    assert len(bundles) == 11, f"Expected 11 bundles, found {len(bundles)}"
    with tempfile.TemporaryDirectory(prefix="apple-mcpb-smoke-") as temp:
        for bundle in bundles:
            destination = Path(temp) / bundle.stem
            with zipfile.ZipFile(bundle) as archive:
                archive.extractall(destination)
            manifest = json.loads((destination / "manifest.json").read_text())
            config = manifest["server"]["mcp_config"]

            # Substitute settings the way the MCPB reference client does when the
            # user changed nothing: declared defaults only (booleans as "true"/"false").
            defaults = {
                f"${{user_config.{key}}}": (("true" if spec["default"] else "false") if isinstance(spec["default"], bool) else str(spec["default"]))
                for key, spec in manifest.get("user_config", {}).items()
                if "default" in spec
            }

            def expand(value: str, directory: Path = destination, defaults: dict[str, str] = defaults) -> str:
                for placeholder, default in defaults.items():
                    value = value.replace(placeholder, default)
                return value.replace("${__dirname}", str(directory)).replace("${HOME}", str(Path.home()))

            parameters = StdioServerParameters(
                command=config["command"],
                args=[expand(arg) for arg in config.get("args", [])],
                env={key: expand(value) for key, value in config.get("env", {}).items()},
                cwd=destination,
            )
            for mode in ("auto", "legacy"):
                async with asyncio.timeout(240):
                    await check_server(bundle.name, mode, parameters, timeout=180)


if __name__ == "__main__":
    asyncio.run(main())
