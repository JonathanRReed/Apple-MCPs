# Changelog

All notable changes to this repository will be documented in this file.

The format is based on Keep a Changelog, and this project intends to follow Semantic Versioning once tagged releases begin.

## [Unreleased]

### Added
- Unified `Apple-Tools-MCP` server covering Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps.
- Standalone MCP servers for each supported Apple domain.
- Assistant defaults, contact-aware communication routing, preview helpers, undo helpers, and audit history in `Apple-Tools-MCP`.
- MCP prompt fallback tools for thinner clients.
- MCP completion, elicitation, resource subscription handling, and task-capable briefing tools in the unified server.
- Streamable HTTP support and protocol validation support where applicable.
- Inspector smoke checks and MCP conformance coverage for the unified server.

### Changed
- Renamed the unified server brand from `Apple-AIO-MCP` to `Apple-Tools-MCP`.
- Renamed the calendar server brand from `ICal-MCP` to `Apple-Calendar-MCP`.
- Standardized README routing guidance, permissions guidance, and launch instructions across the suite.

### Fixed
- Notes create and update AppleScript failures that dropped or failed to write body content.
- Contacts lookup and method extraction issues affecting recipient resolution.
- Messages and Calendar health reporting so blocked permissions are surfaced clearly.
- Unified routing behavior for communication, preview flows, and contact resolution.
