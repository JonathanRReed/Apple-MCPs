# Code Mode

Code mode is the generated wrapper layer for code-execution clients that want to call Apple MCP tools from Python without loading every tool schema into model context.

Use code mode when:

- your client can run Python or another code execution step
- you want search-first MCP discovery, but also want normal function calls inside code
- you want smaller prompt context than a full `tools/list` dump

## What ships in this repo

- `generated/tool_catalogs`, searchable JSON metadata for each server
- `generated/tool_wrappers/python`, generated Python wrappers for every published tool

The generated Python package is:

```text
generated/tool_wrappers/python/apple_mcp_wrappers
```

It includes:

- `index.py`, a tool-name to wrapper-path index
- one wrapper module per tool
- small per-domain `client.py` helpers that call `client.call_tool(...)` and coerce the result into JSON or text

## How code mode fits with search-first MCP

The runtime model is:

1. `tools/list` stays minimal
2. `search_tools` finds the tool you need
3. `get_tool_info` loads the full schema only when needed
4. code-execution clients can skip repeated schema loading by importing the generated wrapper directly

Direct `call_tool` still works for deferred tools. Code mode is a convenience and context-efficiency layer, not a separate protocol.

## The client shape

Each generated wrapper expects a client object that implements:

```python
async def call_tool(name: str, arguments: dict[str, object]) -> object
```

That is the only required interface.

## Basic example

```python
from apple_mcp_wrappers.apple.apple_health import apple_health
from apple_mcp_wrappers.apple.mail_send_message import mail_send_message


class MyClient:
    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        return await mcp_session.call_tool(name, arguments)


client = MyClient()

health = await apple_health(client)

result = await mail_send_message(
    client,
    to=[{"email": "reedjonathan2016@gmail.com"}],
    subject="Apple-Tools code mode test",
    body="test",
    from_account="jonathanrayreed@gmail.com",
)
```

## Result handling

The generated wrappers normalize tool results in this order:

1. `structuredContent`, when present
2. JSON parsed from text content, when the tool returned text chunks
3. raw text, when the content is not JSON
4. the original tool result object, as a last resort

This is why the wrapper functions usually return plain Python data structures instead of raw MCP envelope objects.

## Discovering wrappers

If you already know the tool name, import the specific wrapper module directly.

If you need to discover what exists, use:

```python
from apple_mcp_wrappers import WRAPPER_INDEX
```

`WRAPPER_INDEX` maps tool names to wrapper module paths. Pair that with the catalog files under `generated/tool_catalogs` when you want ranked search metadata, aliases, argument summaries, and example calls.

## Choosing unified vs standalone wrappers

Use unified wrappers under:

```text
generated/tool_wrappers/python/apple_mcp_wrappers/apple
```

These target `Apple-Tools-MCP`.

Use standalone wrappers under sibling domains such as:

```text
generated/tool_wrappers/python/apple_mcp_wrappers/mail
generated/tool_wrappers/python/apple_mcp_wrappers/calendar
generated/tool_wrappers/python/apple_mcp_wrappers/files
```

These target the standalone servers.

Choose unified wrappers when you want cross-app workflows and Apple-Tools routing helpers. Choose standalone wrappers when you want tighter app boundaries.

## Recommended workflow

For search-aware code clients:

1. query `search_tools`
2. inspect the matching catalog entry or call `get_tool_info` if you need schema details
3. import only the wrapper you need
4. call the wrapper with a client that implements `call_tool`

For deterministic Mail sender identity, pass the exact sender email in `from_account`, not just a nickname or display label.

## Regenerating artifacts

When the live tool registry changes, regenerate the catalogs and wrappers:

```bash
cd /path/to/Apple-MCPs
python scripts/generate_tool_search_artifacts.py
```

Then validate the generated Python package if needed:

```bash
python -m compileall generated/tool_wrappers/python
```

## Scope and limitations

- The generated wrappers are Python-only today
- They do not replace MCP permissions, transport, or server health checks
- They are generated artifacts, so they should be regenerated whenever tool names or argument shapes change
- Search quality still comes from the generated catalogs and server-side `search_tools`, not from wrapper filenames alone
