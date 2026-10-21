from apple_mcp_common.discovery import SearchFirstDiscovery, ToolSearchMetadata, install_search_first_discovery
from apple_mcp_common.runtime import notify_resource_updated, notify_resources_changed, require_loopback_host
from apple_mcp_common.server import AppleMCPServer, flag_failed_tool_result

__all__ = [
    "AppleMCPServer",
    "SearchFirstDiscovery",
    "ToolSearchMetadata",
    "flag_failed_tool_result",
    "install_search_first_discovery",
    "notify_resource_updated",
    "notify_resources_changed",
    "require_loopback_host",
]
