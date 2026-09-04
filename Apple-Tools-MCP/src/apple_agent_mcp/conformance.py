from __future__ import annotations

import base64
import io
import json
import wave
from typing import Any

import anyio
from mcp import types
from mcp.server.caching import CacheHint
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.prompts import Prompt
from mcp.server.mcpserver.prompts.base import UserMessage
from mcp.shared.exceptions import MCPError

PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+XlN0AAAAASUVORK5CYII="
_REGISTERED_SERVER_IDS: set[int] = set()


def _wav_base64() -> str:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 80)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


WAV_BASE64 = _wav_base64()


def _text_result(text: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)])


def _image_result() -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.ImageContent(type="image", data=PNG_BASE64, mime_type="image/png")]
    )


def _audio_result() -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.AudioContent(type="audio", data=WAV_BASE64, mime_type="audio/wav")]
    )


def _embedded_resource(uri: str, text: str, mime_type: str = "text/plain") -> types.EmbeddedResource:
    return types.EmbeddedResource(
        type="resource",
        resource=types.TextResourceContents(uri=uri, mime_type=mime_type, text=text),
    )


def enable_conformance_mode(mcp: MCPServer) -> None:
    """Register the official MCP conformance fixtures on the unified server.

    Fixtures cover content types, resources, templates, prompts, progress, and
    completion. Fixtures for features removed or deprecated by spec 2026-07-28
    (server-initiated sampling, logging/setLevel, legacy elicitation, and
    per-resource subscriptions) are intentionally absent.
    """
    server_id = id(mcp)
    if server_id in _REGISTERED_SERVER_IDS:
        return
    _REGISTERED_SERVER_IDS.add(server_id)

    mcp._lowlevel_server.cache_hints = {
        method: CacheHint(ttl_ms=0, scope="private")
        for method in (
            "tools/list",
            "prompts/list",
            "resources/list",
            "resources/templates/list",
            "resources/read",
            "server/discover",
        )
    }

    @mcp.resource(
        "test://static-text",
        name="conformance_static_text",
        title="Conformance Static Text",
        description="Static text resource used by official MCP conformance tests.",
        mime_type="text/plain",
    )
    def conformance_static_text() -> str:
        return "This is the content of the static text resource."

    @mcp.resource(
        "test://static-binary",
        name="conformance_static_binary",
        title="Conformance Static Binary",
        description="Static binary resource used by official MCP conformance tests.",
        mime_type="image/png",
    )
    def conformance_static_binary() -> bytes:
        return base64.b64decode(PNG_BASE64)

    @mcp.resource(
        "test://template/{id}/data",
        name="conformance_template_data",
        title="Conformance Template Data",
        description="Template resource used by official MCP conformance tests.",
        mime_type="application/json",
    )
    def conformance_template_data(id: str) -> str:
        return json.dumps(
            {"id": id, "templateTest": True, "data": f"Data for ID: {id}"},
            separators=(",", ":"),
        )

    @mcp.prompt(
        name="test_simple_prompt",
        title="Conformance Simple Prompt",
        description="Simple prompt used by official MCP conformance tests.",
    )
    def conformance_simple_prompt() -> list[types.PromptMessage]:
        return [
            UserMessage(types.TextContent(type="text", text="This is a simple prompt for testing."))
        ]

    @mcp.prompt(
        name="test_prompt_with_arguments",
        title="Conformance Prompt With Arguments",
        description="Parameterized prompt used by official MCP conformance tests.",
    )
    def conformance_prompt_with_arguments(arg1: str, arg2: str) -> list[types.PromptMessage]:
        return [
            UserMessage(
                types.TextContent(
                    type="text",
                    text=f"Prompt with arguments: arg1='{arg1}', arg2='{arg2}'",
                )
            )
        ]

    @mcp.prompt(
        name="test_prompt_with_embedded_resource",
        title="Conformance Prompt With Embedded Resource",
        description="Prompt with embedded resource content used by official MCP conformance tests.",
    )
    def conformance_prompt_with_embedded_resource(resourceUri: str) -> list[types.PromptMessage]:
        return [
            UserMessage(
                _embedded_resource(
                    resourceUri,
                    "Embedded resource content for testing.",
                    mime_type="text/plain",
                )
            ),
            UserMessage(types.TextContent(type="text", text="Please process the embedded resource above.")),
        ]

    @mcp.prompt(
        name="test_prompt_with_image",
        title="Conformance Prompt With Image",
        description="Prompt with image content used by official MCP conformance tests.",
    )
    def conformance_prompt_with_image() -> list[types.PromptMessage]:
        return [
            UserMessage(types.ImageContent(type="image", data=PNG_BASE64, mime_type="image/png")),
            UserMessage(types.TextContent(type="text", text="Please analyze the image above.")),
        ]

    @mcp.tool(
        name="test_image_content",
        title="Conformance Image Content",
        description="Return image content for official MCP conformance tests.",
        structured_output=False,
    )
    def conformance_image_content() -> types.CallToolResult:
        return _image_result()

    @mcp.tool(
        name="test_audio_content",
        title="Conformance Audio Content",
        description="Return audio content for official MCP conformance tests.",
        structured_output=False,
    )
    def conformance_audio_content() -> types.CallToolResult:
        return _audio_result()

    @mcp.tool(
        name="test_embedded_resource",
        title="Conformance Embedded Resource",
        description="Return embedded resource content for official MCP conformance tests.",
        structured_output=False,
    )
    def conformance_embedded_resource() -> types.CallToolResult:
        return types.CallToolResult(
            content=[_embedded_resource("test://embedded-resource", "This is an embedded resource content.")]
        )

    @mcp.tool(
        name="test_multiple_content_types",
        title="Conformance Mixed Content",
        description="Return multiple content types for official MCP conformance tests.",
        structured_output=False,
    )
    def conformance_multiple_content_types() -> types.CallToolResult:
        return types.CallToolResult(
            content=[
                types.TextContent(type="text", text="Multiple content types test:"),
                types.ImageContent(type="image", data=PNG_BASE64, mime_type="image/png"),
                _embedded_resource(
                    "test://mixed-content-resource",
                    '{"test":"data","value":123}',
                    mime_type="application/json",
                ),
            ]
        )

    @mcp.tool(
        name="test_tool_with_progress",
        title="Conformance Progress Tool",
        description="Send progress notifications during execution for official MCP conformance tests.",
        structured_output=False,
    )
    async def conformance_tool_with_progress(ctx: Context) -> types.CallToolResult:
        await ctx.report_progress(0, 100, "Starting")
        await anyio.sleep(0.05)
        await ctx.report_progress(50, 100, "Halfway")
        await anyio.sleep(0.05)
        await ctx.report_progress(100, 100, "Done")
        return _text_result("Progress tool completed successfully.")

    name_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    def name_elicitation(message: str = "What is your name?") -> types.ElicitRequest:
        return types.ElicitRequest(
            params=types.ElicitRequestFormParams(message=message, requested_schema=name_schema)
        )

    @mcp.tool(name="test_input_required_result_elicitation", description="Request one elicitation input and return it.", structured_output=False)
    async def conformance_input_required_elicitation(ctx: Context) -> str | types.InputRequiredResult:
        responses = ctx.input_responses
        if responses and "user_name" in responses:
            answer = responses["user_name"]
            name = answer.content.get("name", "stranger") if isinstance(answer, types.ElicitResult) and answer.content else "?"
            return f"Hello, {name}!"
        return types.InputRequiredResult(input_requests={"user_name": name_elicitation()})

    @mcp.tool(name="test_input_required_result_sampling", description="Request one sampling input and return it.", structured_output=False)
    async def conformance_input_required_sampling(ctx: Context) -> str | types.InputRequiredResult:
        responses = ctx.input_responses
        if responses and "capital_question" in responses:
            answer = responses["capital_question"]
            text = answer.content.text if isinstance(answer, types.CreateMessageResult) and answer.content.type == "text" else "?"
            return f"Model said: {text}"
        return types.InputRequiredResult(
            input_requests={
                "capital_question": types.CreateMessageRequest(
                    params=types.CreateMessageRequestParams(
                        messages=[types.SamplingMessage(role="user", content=types.TextContent(type="text", text="What is the capital of France?"))],
                        max_tokens=100,
                    )
                )
            }
        )

    @mcp.tool(name="test_input_required_result_list_roots", description="Request client roots and report their count.", structured_output=False)
    async def conformance_input_required_roots(ctx: Context) -> str | types.InputRequiredResult:
        responses = ctx.input_responses
        if responses and "client_roots" in responses:
            answer = responses["client_roots"]
            count = len(answer.roots) if isinstance(answer, types.ListRootsResult) else 0
            return f"Client exposed {count} root(s)."
        return types.InputRequiredResult(input_requests={"client_roots": types.ListRootsRequest()})

    @mcp.tool(name="test_input_required_result_request_state", description="Round-trip protected request state.", structured_output=False)
    async def conformance_input_required_state(ctx: Context) -> str | types.InputRequiredResult:
        if ctx.input_responses and "confirm" in ctx.input_responses and ctx.request_state == "request-state-nonce":
            return "state-ok: confirmation received"
        confirm = types.ElicitRequest(
            params=types.ElicitRequestFormParams(
                message="Please confirm",
                requested_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
            )
        )
        return types.InputRequiredResult(input_requests={"confirm": confirm}, request_state="request-state-nonce")

    @mcp.tool(name="test_input_required_result_multiple_inputs", description="Request several input types in one result.", structured_output=False)
    async def conformance_input_required_multiple(ctx: Context) -> str | types.InputRequiredResult:
        responses = ctx.input_responses
        if responses and {"user_name", "greeting", "client_roots"} <= responses.keys():
            return "All inputs received."
        return types.InputRequiredResult(
            input_requests={
                "user_name": name_elicitation(),
                "greeting": types.CreateMessageRequest(
                    params=types.CreateMessageRequestParams(
                        messages=[types.SamplingMessage(role="user", content=types.TextContent(type="text", text="Generate a greeting"))],
                        max_tokens=50,
                    )
                ),
                "client_roots": types.ListRootsRequest(),
            },
            request_state="multiple-inputs",
        )

    @mcp.tool(name="test_input_required_result_multi_round", description="Complete a two-step input exchange.", structured_output=False)
    async def conformance_input_required_multi_round(ctx: Context) -> str | types.InputRequiredResult:
        state = json.loads(ctx.request_state) if ctx.request_state else {"round": 0}
        responses = ctx.input_responses or {}
        if state["round"] == 0:
            return types.InputRequiredResult(
                input_requests={"step1": name_elicitation("Step 1: What is your name?")},
                request_state=json.dumps({"round": 1}),
            )
        if state["round"] == 1 and "step1" in responses:
            answer = responses["step1"]
            name = answer.content.get("name") if isinstance(answer, types.ElicitResult) and answer.content else None
            return types.InputRequiredResult(
                input_requests={
                    "step2": types.ElicitRequest(
                        params=types.ElicitRequestFormParams(
                            message="Step 2: What is your favorite color?",
                            requested_schema={"type": "object", "properties": {"color": {"type": "string"}}, "required": ["color"]},
                        )
                    )
                },
                request_state=json.dumps({"round": 2, "name": name}),
            )
        if state["round"] == 2 and "step2" in responses:
            answer = responses["step2"]
            color = answer.content.get("color") if isinstance(answer, types.ElicitResult) and answer.content else None
            return f"{state.get('name')} likes {color}."
        return types.InputRequiredResult(
            input_requests={"step1": name_elicitation("Step 1: What is your name?")},
            request_state=json.dumps({"round": 1}),
        )

    @mcp.tool(name="test_input_required_result_tampered_state", description="Exercise protected request-state validation.", structured_output=False)
    async def conformance_input_required_tampered(ctx: Context) -> str | types.InputRequiredResult:
        if ctx.request_state is None:
            return types.InputRequiredResult(
                input_requests={"confirm": name_elicitation("Please confirm")},
                request_state="round-1",
            )
        return f"state-ok: {ctx.request_state}"

    @mcp.tool(name="test_input_required_result_capabilities", description="Request only client-supported input types.", structured_output=False)
    async def conformance_input_required_capabilities(ctx: Context) -> types.InputRequiredResult:
        capabilities = ctx.client_capabilities
        requests: dict[str, types.InputRequest] = {}
        if capabilities is None or capabilities.sampling is not None:
            requests["sample"] = types.CreateMessageRequest(
                params=types.CreateMessageRequestParams(
                    messages=[types.SamplingMessage(role="user", content=types.TextContent(type="text", text="Say hello"))],
                    max_tokens=50,
                )
            )
        if capabilities is None or capabilities.elicitation is not None:
            requests["ask"] = name_elicitation()
        return types.InputRequiredResult(input_requests=requests, request_state="capability-gated")

    @mcp.prompt(name="test_input_required_result_prompt", description="Request context before rendering a prompt.")
    async def conformance_input_required_prompt(ctx: Context) -> list[types.PromptMessage] | types.InputRequiredResult:
        responses = ctx.input_responses
        if responses and "user_context" in responses:
            answer = responses["user_context"]
            value = answer.content.get("context", "?") if isinstance(answer, types.ElicitResult) and answer.content else "?"
            return [UserMessage(types.TextContent(type="text", text=f"Use the following context: {value}"))]
        return types.InputRequiredResult(
            input_requests={
                "user_context": types.ElicitRequest(
                    params=types.ElicitRequestFormParams(
                        message="What context should the prompt use?",
                        requested_schema={"type": "object", "properties": {"context": {"type": "string"}}, "required": ["context"]},
                    )
                )
            }
        )

    def dynamic_tool() -> str:
        return "dynamic"

    def dynamic_prompt() -> str:
        return "dynamic"

    @mcp.tool(name="test_trigger_tool_change", description="Trigger a tool-list change notification.", structured_output=False)
    async def conformance_trigger_tool_change(ctx: Context) -> str:
        mcp.add_tool(dynamic_tool, name="test_dynamic_tool")
        mcp.remove_tool("test_dynamic_tool")
        await ctx.notify_tools_changed()
        return "tool list changed"

    @mcp.tool(name="test_trigger_prompt_change", description="Trigger a prompt-list change notification.", structured_output=False)
    async def conformance_trigger_prompt_change(ctx: Context) -> str:
        mcp.add_prompt(Prompt.from_function(dynamic_prompt, name="test_dynamic_prompt", description="dynamic"))
        mcp.remove_prompt("test_dynamic_prompt")
        await ctx.notify_prompts_changed()
        return "prompt list changed"

    @mcp.tool(
        name="test_missing_capability",
        description="Report the standard error when the client lacks sampling support.",
        structured_output=False,
    )
    async def conformance_missing_capability(ctx: Context) -> str:
        capabilities = ctx.client_capabilities
        if capabilities is None or capabilities.sampling is None:
            raise MCPError(
                code=types.MISSING_REQUIRED_CLIENT_CAPABILITY,
                message="Client does not support sampling",
                data={"requiredCapabilities": {"sampling": {}}},
            )
        return "sampling capability present"

    @mcp.completion()
    async def conformance_completion(
        ref: types.PromptReference | types.ResourceTemplateReference,
        argument: types.CompletionArgument,
        context: types.CompletionContext | None,
    ) -> types.Completion | None:
        if isinstance(ref, types.PromptReference) and ref.name == "test_prompt_with_arguments" and argument.name == "arg1":
            return types.Completion(values=["paris", "park", "party"], total=3, has_more=False)
        if isinstance(ref, types.ResourceTemplateReference) and str(ref.uri) == "test://template/{id}/data" and argument.name == "id":
            return types.Completion(values=["123", "456", "789"], total=3, has_more=False)
        return types.Completion(values=[], total=0, has_more=False)

    # The conformance runner reads the first listed resource while testing
    # resources/read caching. Keep its synthetic resource ahead of resources
    # backed by local Apple applications, which may be unavailable in CI.
    resources = mcp._resource_manager._resources
    synthetic_resources = {
        uri: resource for uri, resource in resources.items() if uri.startswith("test://")
    }
    if synthetic_resources:
        mcp._resource_manager._resources = {
            **synthetic_resources,
            **{uri: resource for uri, resource in resources.items() if uri not in synthetic_resources},
        }
