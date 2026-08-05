from __future__ import annotations

import base64
import io
import json
import wave

import anyio
from mcp import types
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.prompts.base import UserMessage

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
