# Security Policy

## Supported Versions

This project currently supports the latest code on the default branch. Tagged release support can be added once formal releases begin.

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
- task, prompt, and resource surfaces that expose local user data

## Expected Response

The goal is to acknowledge valid reports quickly, reproduce the issue, prepare a fix, and disclose responsibly once users have a safe upgrade path.

## Hardening Guidance

When contributing changes:

- keep tool inputs validated and explicit
- avoid widening allowed file-system scope without clear need
- keep destructive actions easy to preview and audit
- preserve permission checks and safety-mode boundaries
- document any new privacy or automation prompts the user may see
