from __future__ import annotations

import json
import keyword
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence

from mcp import types
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

STOPWORDS = {
    "a",
    "an",
    "and",
    "app",
    "apple",
    "by",
    "for",
    "from",
    "get",
    "in",
    "inside",
    "into",
    "list",
    "local",
    "macos",
    "of",
    "on",
    "or",
    "read",
    "return",
    "the",
    "through",
    "to",
    "use",
    "with",
}

DOMAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "calendar": ("calendar", "event", "events", "meeting", "meetings", "schedule"),
    "contacts": ("contact", "contacts", "person", "people", "recipient", "address-book"),
    "files": ("file", "files", "folder", "folders", "document", "documents", "finder", "icloud", "downloads"),
    "mail": ("mail", "email", "emails", "inbox", "thread"),
    "maps": ("maps", "place", "places", "route", "directions", "restaurant", "restaurants"),
    "messages": ("messages", "imessage", "sms", "text", "chat", "conversation"),
    "notes": ("note", "notes", "memo"),
    "reminders": ("reminder", "reminders", "task", "tasks", "todo"),
    "shortcuts": ("shortcut", "shortcuts", "automation", "workflow"),
    "system": ("system", "mac", "desktop", "clipboard", "battery", "focus", "settings"),
    "apple": ("apple", "assistant", "unified", "cross-app"),
}

AUTO_VISIBLE_MARKERS = (
    "_health",
    "permission_guide",
    "recheck_permissions",
    "list_prompts",
    "get_prompt",
)


@dataclass(frozen=True)
class ToolSearchMetadata:
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    usage_intent: str | None = None
    example_calls: tuple[dict[str, Any], ...] = ()
    always_visible: bool = False


@dataclass
class SearchFirstDiscovery:
    WRAPPER_ROOT_PACKAGE = "apple_mcp_wrappers"
    mcp: FastMCP
    server_name: str
    domain: str
    list_all_tools: Callable[[], Awaitable[list[types.Tool]]]
    call_tool: Callable[[str, dict[str, Any]], Awaitable[Any]]
    metadata: Mapping[str, ToolSearchMetadata] = field(default_factory=dict)
    visible_tool_names: set[str] = field(default_factory=set)
    catalog_json_path: Path | None = None
    wrapper_namespace: str | None = None
    discovery_tool_names: tuple[str, str] = ("search_tools", "get_tool_info")

    def register(self) -> SearchFirstDiscovery:
        async def search_tools(
            query: str,
            limit: int = 10,
            domain_tags: list[str] | None = None,
            mode: str = "compact",
        ) -> dict[str, Any]:
            catalog = await self.catalog_entries()
            results = self.search_catalog(query=query, catalog=catalog, limit=limit, domain_tags=domain_tags, mode=mode)
            return {
                "ok": True,
                "server": self.server_name,
                "domain": self.domain,
                "query": query,
                "count": len(results),
                "results": results,
            }

        async def get_tool_info(
            name: str,
            include_schema: bool = True,
            include_examples: bool = True,
        ) -> dict[str, Any]:
            catalog = await self.catalog_entries()
            tools_by_name = await self.tools_by_name()
            tool = tools_by_name.get(name)
            if tool is None:
                suggestions = self.search_catalog(query=name, catalog=catalog, limit=5, domain_tags=None, mode="compact")
                return {
                    "ok": False,
                    "error": {
                        "code": "UNKNOWN_TOOL",
                        "message": f"Unknown tool: {name}",
                        "suggestions": [item["name"] for item in suggestions],
                        "suggestion": "Use search_tools to find the right tool name.",
                    },
                }
            entry = next(item for item in catalog if item["name"] == name)
            payload = dict(entry)
            if include_schema:
                payload["input_schema"] = tool.inputSchema
                payload["output_schema"] = tool.outputSchema
            else:
                payload.pop("schema_ref", None)
            if not include_examples:
                payload.pop("example_calls", None)
            payload["ok"] = True
            return payload

        self.mcp.add_tool(
            search_tools,
            name=self.discovery_tool_names[0],
            title="Search Tools",
            description="Search this server's tool catalog without loading every full tool schema into the default tool list.",
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            structured_output=True,
        )
        self.mcp.add_tool(
            get_tool_info,
            name=self.discovery_tool_names[1],
            title="Get Tool Info",
            description="Load the full schema, examples, and metadata for one tool from this server.",
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            structured_output=True,
        )

        @self.mcp._mcp_server.list_tools()
        async def _search_first_list_tools(_: types.ListToolsRequest) -> list[types.Tool]:
            tools_by_name = await self.tools_by_name()
            ordered_tools = await self.list_all_tools()
            visible = self.visible_tool_name_set(tool.name for tool in ordered_tools)
            return [tool for tool in ordered_tools if tool.name in visible and tool.name in tools_by_name]

        @self.mcp._mcp_server.call_tool(validate_input=False)
        async def _search_first_call_tool(name: str, arguments: dict[str, Any]) -> Any:
            tools_by_name = await self.tools_by_name()
            if name not in tools_by_name:
                suggestions = self.search_catalog(
                    query=name,
                    catalog=await self.catalog_entries(),
                    limit=5,
                    domain_tags=None,
                    mode="compact",
                )
                suggestion_text = ", ".join(item["name"] for item in suggestions) or "no close matches"
                raise ValueError(f"Unknown tool '{name}'. Closest matches: {suggestion_text}. Use search_tools to discover tools.")
            return await self.call_tool(name, arguments or {})

        return self

    async def tools_by_name(self) -> dict[str, types.Tool]:
        tools = await self.list_all_tools()
        tools_by_name: dict[str, types.Tool] = {}
        for tool in tools:
            tools_by_name.setdefault(tool.name, tool)
        return tools_by_name

    def visible_tool_name_set(self, available_names: Sequence[str] | None = None) -> set[str]:
        visible = set(self.visible_tool_names)
        visible.update(self.discovery_tool_names)
        if available_names is not None:
            visible.update(name for name in available_names if self._auto_visible(name))
        for name, metadata in self.metadata.items():
            if metadata.always_visible:
                visible.add(name)
        return visible

    def _auto_visible(self, name: str) -> bool:
        return any(marker in name for marker in AUTO_VISIBLE_MARKERS)

    async def catalog_entries(self) -> list[dict[str, Any]]:
        tools = await self.list_all_tools()
        catalog: list[dict[str, Any]] = []
        for tool in tools:
            metadata = self.metadata.get(tool.name, ToolSearchMetadata())
            catalog.append(self._catalog_entry(tool, metadata))
        return catalog

    async def export_catalog(self) -> dict[str, Any]:
        tools = await self.catalog_entries()
        return {
            "server": self.server_name,
            "domain": self.domain,
            "tool_count": len(tools),
            "tools": tools,
        }

    def search_catalog(
        self,
        *,
        query: str,
        catalog: Sequence[dict[str, Any]],
        limit: int,
        domain_tags: Sequence[str] | None,
        mode: str,
    ) -> list[dict[str, Any]]:
        normalized_query = query.strip().lower()
        query_tokens = self._tokenize(normalized_query)
        domain_filters = {item.lower() for item in domain_tags or []}
        scored: list[tuple[float, dict[str, Any]]] = []
        for entry in catalog:
            if entry["name"] in self.discovery_tool_names:
                continue
            if domain_filters and not domain_filters.intersection({entry["domain"], *entry["tags"]}):
                continue
            score = self._score_entry(entry, normalized_query, query_tokens)
            if normalized_query and score <= 0:
                continue
            scored.append((score, entry))
        scored.sort(key=lambda item: (-item[0], item[1]["name"]))
        results: list[dict[str, Any]] = []
        for score, entry in scored[: max(1, limit)]:
            shaped = {
                "name": entry["name"],
                "title": entry["title"],
                "description": entry["description"],
                "domain": entry["domain"],
                "tags": entry["tags"],
                "risk_level": entry["risk_level"],
                "argument_summary": entry["argument_summary"],
                "score": round(score, 2),
            }
            if mode in {"detail", "full"}:
                shaped["usage_intent"] = entry["usage_intent"]
                shaped["aliases"] = entry["aliases"]
                shaped["schema_ref"] = entry["schema_ref"]
            if mode == "full":
                shaped["example_calls"] = entry["example_calls"]
                shaped["read_only"] = entry["read_only"]
            results.append(shaped)
        return results

    def _catalog_entry(self, tool: types.Tool, metadata: ToolSearchMetadata) -> dict[str, Any]:
        tags = self._tags_for_tool(tool, metadata)
        example_calls = list(metadata.example_calls) or [self._example_call(tool)]
        return {
            "name": tool.name,
            "title": tool.title or self._title_from_name(tool.name),
            "description": tool.description or "",
            "domain": self.domain,
            "usage_intent": metadata.usage_intent or self._usage_intent(tool),
            "tags": tags,
            "aliases": list(dict.fromkeys([*metadata.aliases, *self._aliases_for_tool(tool)])),
            "risk_level": self._risk_level(tool),
            "read_only": bool(getattr(tool.annotations, "readOnlyHint", False)),
            "argument_summary": self._argument_summary(tool.inputSchema),
            "example_calls": example_calls,
            "schema_ref": tool.name,
        }

    def _score_entry(self, entry: Mapping[str, Any], normalized_query: str, query_tokens: Sequence[str]) -> float:
        if not normalized_query:
            return 1.0 if entry["risk_level"] == "low" else 0.5
        exact_tags = set(entry.get("tags", []))
        exact_aliases = set(entry.get("aliases", []))
        name_tokens = set(self._tokenize(entry["name"].replace("_", " ")))
        haystacks = [
            entry["name"].lower(),
            (entry.get("title") or "").lower(),
            (entry.get("description") or "").lower(),
            " ".join(entry.get("aliases", [])).lower(),
            " ".join(entry.get("tags", [])).lower(),
            (entry.get("usage_intent") or "").lower(),
        ]
        score = 0.0
        if normalized_query == entry["name"].lower():
            score += 100
        if normalized_query in set(entry.get("aliases", [])):
            score += 80
        for haystack in haystacks:
            if normalized_query and normalized_query in haystack:
                score += 20
        for token in query_tokens:
            if token in exact_tags:
                score += 12
            if token in exact_aliases:
                score += 10
            if token in name_tokens:
                score += 8
            for haystack in haystacks:
                if token == entry["domain"]:
                    score += 8
                if token and re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack):
                    score += 6
                elif token and token in haystack:
                    score += 2
        score += self._tool_kind_bias(entry["name"], query_tokens)
        if entry["read_only"]:
            score += 0.25
        return score

    def _tool_kind_bias(self, tool_name: str, query_tokens: Sequence[str]) -> float:
        tokens = tool_name.split("_")
        query_token_set = set(query_tokens)
        if {"suggest", "suggestion", "autocomplete", "completion", "complete"}.intersection(query_token_set):
            suggestion_penalty = 0.0
        else:
            suggestion_penalty = -8.0 if "suggest" in tokens else 0.0
        if {"preview", "draft", "plan"}.intersection(query_token_set):
            preview_penalty = 0.0
        else:
            preview_penalty = -10.0 if "preview" in tokens else 0.0
        direct_action_bonus = 0.0
        if {"list", "get", "find", "search", "read", "create", "send", "run", "archive", "delete", "update", "write", "add"}.intersection(tokens):
            direct_action_bonus = 4.0
        return suggestion_penalty + preview_penalty + direct_action_bonus

    def _usage_intent(self, tool: types.Tool) -> str:
        description = (tool.description or "").strip()
        if description:
            return description
        return f"Use {tool.name} when the request matches the {self.domain} domain."

    def _risk_level(self, tool: types.Tool) -> str:
        annotations = tool.annotations
        if annotations and getattr(annotations, "destructiveHint", False):
            return "high"
        if annotations and getattr(annotations, "readOnlyHint", False):
            return "low"
        return "medium"

    def _argument_summary(self, schema: Mapping[str, Any]) -> list[str]:
        properties = schema.get("properties", {}) if isinstance(schema, Mapping) else {}
        required = set(schema.get("required", [])) if isinstance(schema, Mapping) else set()
        summaries: list[str] = []
        for name, definition in properties.items():
            type_name = self._schema_type_name(definition)
            suffix = "required" if name in required else "optional"
            summaries.append(f"{name}: {type_name} ({suffix})")
        return summaries[:8]

    def _example_call(self, tool: types.Tool) -> dict[str, Any]:
        schema = tool.inputSchema or {}
        properties = schema.get("properties", {}) if isinstance(schema, Mapping) else {}
        required = set(schema.get("required", [])) if isinstance(schema, Mapping) else set()
        arguments: dict[str, Any] = {}
        for name, definition in properties.items():
            if name in required or len(arguments) < 2:
                arguments[name] = self._example_value(name, definition)
        return {"tool": tool.name, "arguments": arguments}

    def _example_value(self, name: str, definition: Mapping[str, Any]) -> Any:
        if "enum" in definition and definition["enum"]:
            return definition["enum"][0]
        schema_type = self._schema_type_name(definition)
        if schema_type == "boolean":
            return False
        if schema_type == "integer":
            return 1
        if schema_type == "number":
            return 1.0
        if schema_type == "array":
            return []
        if schema_type == "object":
            return {}
        lowered = name.lower()
        if "path" in lowered:
            return "/path/to/item"
        if "email" in lowered:
            return "person@example.com"
        if "phone" in lowered:
            return "+15551234567"
        if "recipient" in lowered:
            return "Example Person"
        if "date" in lowered or "time" in lowered or lowered.endswith("_iso"):
            return "2026-04-07T18:00:00"
        if "query" in lowered:
            return f"find {self.domain}"
        return f"example_{name}"

    def _aliases_for_tool(self, tool: types.Tool) -> list[str]:
        aliases = list(DOMAIN_ALIASES.get(self.domain, ()))
        base_name = tool.name
        prefix = f"{self.domain}_"
        if base_name.startswith(prefix):
            aliases.append(base_name[len(prefix) :].replace("_", " "))
        aliases.append(base_name.replace("_", " "))
        return list(dict.fromkeys(alias.lower() for alias in aliases if alias))

    def _tags_for_tool(self, tool: types.Tool, metadata: ToolSearchMetadata) -> list[str]:
        tags = [self.domain, *DOMAIN_ALIASES.get(self.domain, ())]
        tags.extend(metadata.tags)
        tags.extend(self._tokenize(tool.name.replace("_", " ")))
        tags.extend(self._tokenize((tool.title or "") + " " + (tool.description or "")))
        filtered = [token for token in tags if token and token not in STOPWORDS and len(token) > 2]
        return list(dict.fromkeys(filtered))[:20]

    def _tokenize(self, value: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9]+", value.lower())
        expanded: list[str] = []
        for token in tokens:
            expanded.append(token)
            if token.endswith("ies") and len(token) > 3:
                expanded.append(f"{token[:-3]}y")
            elif token.endswith("es") and len(token) > 3:
                expanded.append(token[:-2])
            elif token.endswith("s") and len(token) > 3:
                expanded.append(token[:-1])
        return list(dict.fromkeys(expanded))

    def _schema_type_name(self, definition: Mapping[str, Any]) -> str:
        schema_type = definition.get("type")
        if isinstance(schema_type, list):
            non_null = [item for item in schema_type if item != "null"]
            return non_null[0] if non_null else "any"
        if isinstance(schema_type, str):
            return schema_type
        any_of = definition.get("anyOf")
        if isinstance(any_of, list):
            for item in any_of:
                if item.get("type") and item.get("type") != "null":
                    return str(item["type"])
        return "any"

    def _title_from_name(self, name: str) -> str:
        return name.replace("_", " ").title()

    async def write_catalog_json(self, output_path: Path) -> Path:
        payload = await self.export_catalog()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return output_path

    async def generate_python_wrappers(self, output_dir: Path) -> list[Path]:
        catalog = await self.catalog_entries()
        tool_definitions = await self.list_all_tools()
        tools_by_name = {tool.name: tool for tool in tool_definitions}
        output_dir.mkdir(parents=True, exist_ok=True)
        root_package_dir = output_dir / self.WRAPPER_ROOT_PACKAGE
        root_package_dir.mkdir(parents=True, exist_ok=True)
        package_name = self.wrapper_namespace or self.domain
        package_dir = root_package_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)
        created_paths: list[Path] = []
        root_init_path = root_package_dir / "__init__.py"
        root_init_path.write_text(
            "from __future__ import annotations\n\n"
            "from .index import WRAPPER_INDEX\n\n"
            '__all__ = ["WRAPPER_INDEX"]\n',
            encoding="utf-8",
        )
        created_paths.append(root_init_path)
        init_lines = ["from __future__ import annotations", "", "from .client import MCPToolCaller", ""]
        client_path = package_dir / "client.py"
        client_path.write_text(
            "from __future__ import annotations\n\n"
            "import json\n\n"
            "from typing import Any, Protocol\n\n\n"
            "class MCPToolCaller(Protocol):\n"
            "    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...\n\n\n"
            "def _coerce_tool_result(result: Any) -> Any:\n"
            '    structured = getattr(result, "structuredContent", None)\n'
            "    if structured is not None:\n"
            "        return structured\n"
            '    content = getattr(result, "content", None) or []\n'
            "    chunks: list[str] = []\n"
            "    for item in content:\n"
            '        text = getattr(item, "text", None)\n'
            "        if text:\n"
            "            chunks.append(text)\n"
            "    if not chunks:\n"
            "        return result\n"
            '    text_payload = "".join(chunks)\n'
            "    try:\n"
            "        return json.loads(text_payload)\n"
            "    except json.JSONDecodeError:\n"
            "        return text_payload\n\n\n"
            "async def call_tool_json(client: MCPToolCaller, name: str, arguments: dict[str, Any]) -> Any:\n"
            "    result = await client.call_tool(name, arguments)\n"
            "    return _coerce_tool_result(result)\n",
            encoding="utf-8",
        )
        created_paths.append(client_path)
        index_entries: list[str] = []
        exported_functions: list[str] = []
        for entry in catalog:
            if entry["name"] in self.discovery_tool_names:
                continue
            file_name = f"{entry['name']}.py"
            function_name = self._safe_identifier(entry["name"])
            module_path = package_dir / file_name
            schema = tools_by_name[entry["name"]].inputSchema
            parameters_block, arguments_dict = self._python_wrapper_signature(schema)
            example = entry["example_calls"][0]["arguments"] if entry["example_calls"] else {}
            module_path.write_text(
                self._render_wrapper_module(
                    function_name=function_name,
                    tool_name=entry["name"],
                    title=entry["title"],
                    description=entry["description"],
                    parameters_block=parameters_block,
                    arguments_dict=arguments_dict,
                    example=example,
                ),
                encoding="utf-8",
            )
            created_paths.append(module_path)
            init_lines.append(f"from .{entry['name']} import {function_name}")
            index_entries.append(f'    "{entry["name"]}": "{self.WRAPPER_ROOT_PACKAGE}/{package_name}/{file_name}",')
            exported_functions.append(function_name)
        init_lines.append("")
        init_lines.append("__all__ = [")
        init_lines.extend(f'    "{name}",' for name in exported_functions)
        init_lines.append("]")
        init_path = package_dir / "__init__.py"
        init_path.write_text("\n".join(init_lines) + "\n", encoding="utf-8")
        created_paths.append(init_path)
        index_path = root_package_dir / "index.py"
        index_lines = ["from __future__ import annotations", "", "WRAPPER_INDEX = {"]
        if index_path.exists():
            existing = index_path.read_text(encoding="utf-8")
            existing_entries = [line for line in existing.splitlines() if line.startswith('    "')]
            index_lines.extend(existing_entries)
        index_lines.extend(index_entries)
        index_lines = list(dict.fromkeys(index_lines))
        index_lines.append("}")
        index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
        created_paths.append(index_path)
        return created_paths

    def _python_wrapper_signature(self, schema: Mapping[str, Any]) -> tuple[str, str]:
        properties = schema.get("properties", {}) if isinstance(schema, Mapping) else {}
        required = set(schema.get("required", [])) if isinstance(schema, Mapping) else set()
        parameters = ["client: MCPToolCaller"]
        argument_lines: list[str] = []
        for name, definition in properties.items():
            annotation = self._python_annotation(definition)
            safe_name = self._safe_identifier(name)
            if name in required:
                parameters.append(f"{safe_name}: {annotation}")
            else:
                parameters.append(f"{safe_name}: {annotation} | None = None")
            argument_lines.append(f'        "{name}": {safe_name},')
        argument_dict = "\n".join(argument_lines)
        return ",\n    ".join(parameters), argument_dict

    def _python_annotation(self, definition: Mapping[str, Any]) -> str:
        if "enum" in definition and definition["enum"]:
            return "str"
        schema_type = self._schema_type_name(definition)
        return {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "list[Any]",
            "object": "dict[str, Any]",
        }.get(schema_type, "Any")

    def _render_wrapper_module(
        self,
        *,
        function_name: str,
        tool_name: str,
        title: str,
        description: str,
        parameters_block: str,
        arguments_dict: str,
        example: Mapping[str, Any],
    ) -> str:
        example_arguments = ", ".join(f"{self._safe_identifier(key)}={value!r}" for key, value in example.items())
        return (
            "from __future__ import annotations\n\n"
            "from typing import Any\n\n"
            "from .client import MCPToolCaller, call_tool_json\n\n\n"
            f"async def {function_name}(\n"
            f"    {parameters_block}\n"
            ") -> Any:\n"
            f'    """{title}\n\n'
            f"    {description}\n\n"
            f"    Example:\n"
            f"        await {function_name}(client"
            + (f", {example_arguments}" if example_arguments else "")
            + ")\n"
            '    """\n'
            "    arguments = {\n"
            f"{arguments_dict}\n"
            "    }\n"
            "    payload = {key: value for key, value in arguments.items() if value is not None}\n"
            f'    return await call_tool_json(client, "{tool_name}", payload)\n'
        )

    def _safe_identifier(self, value: str) -> str:
        identifier = re.sub(r"[^a-zA-Z0-9_]", "_", value)
        if identifier and identifier[0].isdigit():
            identifier = f"tool_{identifier}"
        if keyword.iskeyword(identifier):
            identifier = f"{identifier}_tool"
        return identifier


def install_search_first_discovery(
    mcp: FastMCP,
    *,
    server_name: str,
    domain: str,
    list_all_tools: Callable[[], Awaitable[list[types.Tool]]] | None = None,
    call_tool: Callable[[str, dict[str, Any]], Awaitable[Any]] | None = None,
    metadata: Mapping[str, ToolSearchMetadata] | None = None,
    visible_tool_names: set[str] | None = None,
    catalog_json_path: Path | None = None,
    wrapper_namespace: str | None = None,
) -> SearchFirstDiscovery:
    discovery = SearchFirstDiscovery(
        mcp=mcp,
        server_name=server_name,
        domain=domain,
        list_all_tools=list_all_tools or mcp.list_tools,
        call_tool=call_tool or mcp.call_tool,
        metadata=metadata or {},
        visible_tool_names=visible_tool_names or set(),
        catalog_json_path=catalog_json_path,
        wrapper_namespace=wrapper_namespace,
    )
    return discovery.register()
