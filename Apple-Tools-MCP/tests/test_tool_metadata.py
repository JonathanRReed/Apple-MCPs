"""Tool metadata contract for every Apple server.

Apple-Tools-MCP must expose delegated tools with exactly the metadata of the
standalone server that implements them, and every server's annotations must
follow the MCP spec definitions consistently.
"""

from __future__ import annotations

import asyncio
from collections import Counter

import pytest
from mcp import types

from apple_agent_mcp import tools as unified
from apple_mcp_common.server import AppleMCPServer

DISCOVERY_TOOLS = {"search_tools", "get_tool_info"}

# Tokens in a tool name that mean it changes or removes existing state, or acts
# irreversibly toward other people. Such a tool is never read-only and always
# destructive (spec: "may perform destructive updates to its environment").
DESTRUCTIVE_ACTIONS = {
    "delete", "send", "run", "update", "set", "remove", "move", "archive", "reply", "forward",
    "rename", "undo", "mark", "complete", "uncomplete", "control", "click", "press", "type", "choose", "tag",
}
# Tokens for actions that reach outside the local data store: messages and
# mail to other people, Shortcuts that can do anything, GUI control of apps.
OPEN_WORLD_ACTIONS = {"send", "reply", "forward", "run", "control", "click", "press", "type", "choose"}
# The action token right after the domain prefix for tools that only read.
READ_ONLY_ACTIONS = {
    "health", "list", "get", "search", "view", "read", "suggest", "preview", "find", "resolve",
    "recent", "status", "build", "overview", "permission",
}


def _all_servers() -> dict[str, AppleMCPServer]:
    return {"apple": unified.mcp, **unified.STANDALONE_SERVERS}


def _list(server) -> list[types.Tool]:
    return asyncio.run(server.list_tools())


ALL_TOOLS = [(domain, tool) for domain, server in _all_servers().items() for tool in _list(server)]


def _id(item: tuple[str, types.Tool]) -> str:
    return f"{item[0]}:{item[1].name}"


def test_every_server_flags_failures_as_errors() -> None:
    assert all(isinstance(server, AppleMCPServer) for server in _all_servers().values())


def test_every_delegated_tool_matches_its_standalone_metadata() -> None:
    standalone = {tool.name: tool for domain, server in unified.STANDALONE_SERVERS.items() for tool in _list(server)}
    delegated = [tool for tool in _list(unified.mcp) if tool.name in standalone and tool.name not in DISCOVERY_TOOLS]
    assert {tool.name for tool in delegated} == {fn.__name__ for fn in unified.UNIFIED_TOOL_FUNCTIONS}
    for tool in delegated:
        source = standalone[tool.name]
        assert tool.title == source.title, tool.name
        assert tool.annotations == source.annotations, tool.name
        if tool.name in unified.DELEGATED_DESCRIPTION_OVERRIDES:
            assert tool.description == unified.DELEGATED_DESCRIPTION_OVERRIDES[tool.name]
        else:
            assert tool.description == source.description, tool.name
        source_properties = source.input_schema.get("properties", {})
        for parameter, schema in tool.input_schema.get("properties", {}).items():
            if parameter in source_properties:
                assert schema.get("description") == source_properties[parameter].get("description"), (tool.name, parameter)
        assert "Delegated Apple domain tool" not in (tool.description or "")


def test_unified_tool_titles_are_unique() -> None:
    titles = Counter(tool.title for tool in _list(unified.mcp) if tool.name not in DISCOVERY_TOOLS)
    assert [title for title, count in titles.items() if count > 1] == []


@pytest.mark.parametrize("item", ALL_TOOLS, ids=[_id(item) for item in ALL_TOOLS])
def test_annotations_follow_spec_rules(item: tuple[str, types.Tool]) -> None:
    _domain, tool = item
    annotations = tool.annotations
    assert annotations is not None, tool.name
    assert tool.title, tool.name
    assert tool.description, tool.name
    # Spec defaults openWorldHint to true and destructiveHint to true; say it explicitly.
    assert annotations.open_world_hint is not None, tool.name
    tokens = tool.name.split("_")
    if annotations.read_only_hint:
        assert annotations.destructive_hint is None, f"{tool.name}: destructiveHint is meaningless when read-only"
    else:
        assert annotations.destructive_hint is not None, tool.name
    if "preview" in tokens:
        assert annotations.read_only_hint is True, tool.name
        return
    if DESTRUCTIVE_ACTIONS.intersection(tokens):
        assert not annotations.read_only_hint, tool.name
        assert annotations.destructive_hint is True, tool.name
    if OPEN_WORLD_ACTIONS.intersection(tokens):
        assert annotations.open_world_hint is True, tool.name
    if len(tokens) > 1 and tokens[1] in READ_ONLY_ACTIONS:
        assert annotations.read_only_hint is True, tool.name


@pytest.mark.parametrize("item", ALL_TOOLS, ids=[_id(item) for item in ALL_TOOLS])
def test_every_parameter_is_described(item: tuple[str, types.Tool]) -> None:
    _domain, tool = item
    undescribed = [name for name, schema in tool.input_schema.get("properties", {}).items() if not schema.get("description")]
    assert undescribed == [], tool.name
