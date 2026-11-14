# Security Policy

## Supported Versions

The latest tagged release (1.x) and the default branch are supported with security fixes.

## Reporting a Vulnerability

Do not open a public GitHub issue for a suspected security problem.

Use GitHub's private vulnerability reporting for this repository if it is enabled. If private reporting is not available, contact the maintainer directly through the repository owner profile before sharing technical details publicly.

Include:

- affected server or servers
- impact and attack preconditions
- steps to reproduce
- whether the issue requires local access, macOS permissions, or a malicious MCP client
- any proof-of-concept material needed to reproduce safely

## What Counts As Security-Sensitive Here

The highest-risk areas in this repository include:

- mail send, reply, forward, archive, move, and delete flows
- messages send, reply, group-chat targeting, and attachment sends
- contacts mutation and recipient-resolution logic
- notes mutation and cross-app digest generation
- local file access and attachment preparation
- system actions that touch clipboard, notifications, or app launch
- prompt and resource surfaces that expose local user data

## Expected Response

The goal is to acknowledge valid reports quickly, reproduce the issue, prepare a fix, and disclose responsibly once users have a safe upgrade path.

## Known Limits

- **Content from other people is untrusted.** Email, messages, notes, invitations and files can carry text written to steer an agent. The instructions of every server except Maps tell the model to treat that text as information and to check with the user before acting on it, but no instruction makes a model immune. The safety modes and folder limits are the real boundary: below `full_access` Mail sends nothing, and in every mode file tools stay inside the allowed folders.
- **Streamable HTTP has no authentication.** It binds to loopback only and rejects requests with a foreign `Host` header, or a foreign or `null` `Origin`, which stops ordinary websites and DNS rebinding. A page served from `localhost` or `127.0.0.1` is accepted, and any program or user account on the same Mac can call the tools while it runs. `stdio`, the default, has no such exposure.

## Hardening Guidance

When contributing changes:

- keep tool inputs validated and explicit
- avoid widening allowed file-system scope without clear need
- keep destructive actions easy to preview and audit
- preserve permission checks and safety-mode boundaries
- document any new privacy or automation prompts the user may see
