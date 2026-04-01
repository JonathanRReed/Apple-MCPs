from __future__ import annotations

import base64
import io
import json
import wave
from typing import Any

import anyio
from mcp import types
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.prompts.base import UserMessage
from pydantic import BaseModel, Field

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


class _ConformanceUserInput(BaseModel):
    username: str = Field(description="User's response")
    email: str = Field(description="User's email address")


def _text_result(text: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)])


def _image_result() -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.ImageContent(type="image", data=PNG_BASE64, mimeType="image/png")]
    )


def _audio_result() -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.AudioContent(type="audio", data=WAV_BASE64, mimeType="audio/wav")]
    )


def _embedded_resource(uri: str, text: str, mime_type: str = "text/plain") -> types.EmbeddedResource:
    return types.EmbeddedResource(
        type="resource",
        resource=types.TextResourceContents(uri=uri, mimeType=mime_type, text=text),
    )


def _extract_message_text(result: types.CreateMessageResult | types.CreateMessageResultWithTools) -> str:
    content = result.content
    if isinstance(content, list):
        for item in content:
            if isinstance(item, types.TextContent):
                return item.text
        return json.dumps([item.model_dump() for item in content], sort_keys=True)
    if isinstance(content, types.TextContent):
        return content.text
    return json.dumps(content.model_dump(), sort_keys=True)


def _format_elicitation_result(result: Any) -> str:
    action = getattr(result, "action", "unknown")
    content = getattr(result, "data", None)
    if content is None:
        content = getattr(result, "content", None)
    if hasattr(content, "model_dump"):
        content = content.model_dump()
    return f"action={action}, content={json.dumps(content, sort_keys=True)}"


def enable_conformance_mode(mcp: FastMCP) -> None:
    server_id = id(mcp)
    if server_id in _REGISTERED_SERVER_IDS:
        return
    _REGISTERED_SERVER_IDS.add(server_id)

    subscribed_resources: set[str] = set()
    logging_state = {"level": "info"}

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
            UserMessage(types.ImageContent(type="image", data=PNG_BASE64, mimeType="image/png")),
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
                types.ImageContent(type="image", data=PNG_BASE64, mimeType="image/png"),
                _embedded_resource(
                    "test://mixed-content-resource",
                    '{"test":"data","value":123}',
                    mime_type="application/json",
                ),
            ]
        )

    @mcp.tool(
        name="test_tool_with_logging",
        title="Conformance Logging Tool",
        description="Send log notifications during execution for official MCP conformance tests.",
        structured_output=False,
    )
    async def conformance_tool_with_logging(ctx: Context) -> types.CallToolResult:
        await ctx.request_context.session.send_log_message(
            level="info",
            data="Tool execution started",
            logger="conformance",
        )
        await anyio.sleep(0.05)
        await ctx.request_context.session.send_log_message(
            level="info",
            data="Tool processing data",
            logger="conformance",
        )
        await anyio.sleep(0.05)
        await ctx.request_context.session.send_log_message(
            level="info",
            data="Tool execution completed",
            logger="conformance",
        )
        await anyio.sleep(0.05)
        return _text_result("Logging tool completed successfully.")

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

    @mcp.tool(
        name="test_elicitation",
        title="Conformance Elicitation Tool",
        description="Request elicitation from the client for official MCP conformance tests.",
        structured_output=False,
    )
    async def conformance_elicitation(message: str, ctx: Context) -> types.CallToolResult:
        result = await ctx.elicit(message, _ConformanceUserInput)
        return _text_result(f"User response: {_format_elicitation_result(result)}")

    @mcp.tool(
        name="test_elicitation_sep1034_defaults",
        title="Conformance Elicitation Defaults",
        description="Request elicitation with default values for official MCP conformance tests.",
        structured_output=False,
    )
    async def conformance_elicitation_defaults(ctx: Context) -> types.CallToolResult:
        result = await ctx.request_context.session.elicit_form(
            message="Provide values or accept the defaults.",
            requestedSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "John Doe"},
                    "age": {"type": "integer", "default": 30},
                    "score": {"type": "number", "default": 95.5},
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive", "pending"],
                        "default": "active",
                    },
                    "verified": {"type": "boolean", "default": True},
                },
                "required": ["name", "age", "score", "status", "verified"],
            },
            related_request_id=ctx.request_id,
        )
        return _text_result(f"Elicitation completed: {_format_elicitation_result(result)}")

    @mcp.tool(
        name="test_elicitation_sep1330_enums",
        title="Conformance Elicitation Enums",
        description="Request elicitation with enum schema variants for official MCP conformance tests.",
        structured_output=False,
    )
    async def conformance_elicitation_enums(ctx: Context) -> types.CallToolResult:
        result = await ctx.request_context.session.elicit_form(
            message="Choose enum values for the conformance test.",
            requestedSchema={
                "type": "object",
                "properties": {
                    "untitledSingle": {"type": "string", "enum": ["option1", "option2", "option3"]},
                    "titledSingle": {
                        "type": "string",
                        "oneOf": [
                            {"const": "value1", "title": "First Option"},
                            {"const": "value2", "title": "Second Option"},
                            {"const": "value3", "title": "Third Option"},
                        ],
                    },
                    "legacyEnum": {
                        "type": "string",
                        "enum": ["opt1", "opt2", "opt3"],
                        "enumNames": ["Option One", "Option Two", "Option Three"],
                    },
                    "untitledMulti": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["option1", "option2", "option3"]},
                    },
                    "titledMulti": {
                        "type": "array",
                        "items": {
                            "anyOf": [
                                {"const": "value1", "title": "First Choice"},
                                {"const": "value2", "title": "Second Choice"},
                                {"const": "value3", "title": "Third Choice"},
                            ]
                        },
                    },
                },
                "required": [
                    "untitledSingle",
                    "titledSingle",
                    "legacyEnum",
                    "untitledMulti",
                    "titledMulti",
                ],
            },
            related_request_id=ctx.request_id,
        )
        return _text_result(f"Elicitation completed: {_format_elicitation_result(result)}")

    @mcp.tool(
        name="test_sampling",
        title="Conformance Sampling Tool",
        description="Request LLM sampling from the client for official MCP conformance tests.",
        structured_output=False,
    )
    async def conformance_sampling(prompt: str, ctx: Context) -> types.CallToolResult:
        result = await ctx.request_context.session.create_message(
            messages=[
                types.SamplingMessage(
                    role="user",
                    content=types.TextContent(type="text", text=prompt),
                )
            ],
            max_tokens=100,
            related_request_id=ctx.request_id,
        )
        return _text_result(f"LLM response: {_extract_message_text(result)}")

    @mcp.completion()
    async def conformance_completion(
        ref: types.PromptReference | types.ResourceTemplateReference,
        argument: types.CompletionArgument,
        context: types.CompletionContext | None,
    ) -> types.Completion | None:
        if isinstance(ref, types.PromptReference) and ref.name == "test_prompt_with_arguments" and argument.name == "arg1":
            return types.Completion(values=["paris", "park", "party"], total=3, hasMore=False)
        if isinstance(ref, types.ResourceTemplateReference) and str(ref.uri) == "test://template/{id}/data" and argument.name == "id":
            return types.Completion(values=["123", "456", "789"], total=3, hasMore=False)
        return types.Completion(values=[], total=0, hasMore=False)

    @mcp._mcp_server.set_logging_level()
    async def conformance_set_logging_level(level: types.LoggingLevel) -> None:
        logging_state["level"] = str(level)

    async def conformance_subscribe(req: types.SubscribeRequest) -> types.ServerResult:
        subscribed_resources.add(str(req.params.uri))
        return types.ServerResult(types.EmptyResult())

    async def conformance_unsubscribe(req: types.UnsubscribeRequest) -> types.ServerResult:
        subscribed_resources.discard(str(req.params.uri))
        return types.ServerResult(types.EmptyResult())

    mcp._mcp_server.request_handlers[types.SubscribeRequest] = conformance_subscribe
    mcp._mcp_server.request_handlers[types.UnsubscribeRequest] = conformance_unsubscribe
