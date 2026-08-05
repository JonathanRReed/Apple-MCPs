# Publishing to PyPI and the MCP Registry

Runbook for publishing the 11 Apple MCP servers to PyPI and the official
[MCP Registry](https://registry.modelcontextprotocol.io) under the
`io.github.jonathanrreed` namespace.

## What ships where

| Component | PyPI | MCP Registry |
| --- | --- | --- |
| `apple-mcp-common` (AppleMCPCommon) | Yes | No — it is a shared library, not an MCP server; the registry only lists servers |
| The 11 servers (`apple-tools-mcp`, `apple-calendar-mcp`, `apple-contacts-mcp`, `apple-files-mcp`, `apple-mail-mcp`, `apple-maps-mcp`, `apple-messages-mcp`, `apple-notes-mcp`, `apple-reminders-mcp`, `apple-shortcuts-mcp`, `apple-system-mcp`) | Yes | Yes — each server directory has a `server.json` |

The registry hosts metadata only, never artifacts, so PyPI publishing must
happen **before** registry publishing.

Each server's `README.md` starts with an HTML comment like
`<!-- mcp-name: io.github.jonathanrreed/apple-mail-mcp -->`. The registry
verifies PyPI package ownership by finding that exact string in the package's
PyPI description (the README). Do not remove these markers, and make sure the
README is included in the sdist/wheel metadata (it is, via `readme = "README.md"`
in each `pyproject.toml`).

## 1. Publish packages to PyPI with uv

Order matters: every server depends on `apple-mcp-common>=1.0.0,<2`, so publish
`AppleMCPCommon` first. (The `[tool.uv.sources]` workspace pins only apply to
local development; built wheels resolve `apple-mcp-common` from PyPI.)

```bash
cd AppleMCPCommon
uv build
uv publish        # needs a PyPI token: UV_PUBLISH_TOKEN or --token

# then each server, in any order:
for dir in Apple-Tools-MCP Apple-Calendar-MCP AppleContacts-MCP AppleFiles-MCP \
           AppleMail-MCP AppleMaps-MCP AppleMessages-MCP AppleNotes-MCP \
           AppleReminders-MCP AppleShortcuts-MCP AppleSystem-MCP; do
  (cd "$dir" && uv build && uv publish)
done
```

Sanity checks after publishing:

- `uvx apple-mcp-mail` (etc.) starts the server via the console script.
- The PyPI project page description contains the `mcp-name:` marker.

## 2. Install mcp-publisher

```bash
brew install mcp-publisher
```

or grab a release binary:

```bash
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher
sudo mv mcp-publisher /usr/local/bin/
```

## 3. Authenticate and publish to the MCP Registry

GitHub auth grants the `io.github.jonathanrreed/*` namespace (must match the
GitHub account that owns the repo):

```bash
mcp-publisher login github   # device-code flow in the browser
```

Then publish each server (the CLI reads `./server.json`):

```bash
for dir in Apple-Tools-MCP Apple-Calendar-MCP AppleContacts-MCP AppleFiles-MCP \
           AppleMail-MCP AppleMaps-MCP AppleMessages-MCP AppleNotes-MCP \
           AppleReminders-MCP AppleShortcuts-MCP AppleSystem-MCP; do
  (cd "$dir" && mcp-publisher publish)
done
```

Verify:

```bash
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.jonathanrreed"
```

If publishing fails with "Registry validation failed for package", the PyPI
README marker is missing or does not match the `name` in `server.json`. If it
fails with a permissions error, the logged-in GitHub account does not own the
`jonathanrreed` namespace.

## 4. Adding MCPB packages later (at release time)

The `server.json` files intentionally ship with only a `pypi` package entry.
MCPB entries require a `fileSha256` of a real release asset, which does not
exist until a GitHub release is cut. Once `.mcpb` bundles are attached to a
release:

1. Compute the hash: `openssl dgst -sha256 apple-mail.mcpb`
2. Append to that server's `packages` array:

   ```json
   {
     "registryType": "mcpb",
     "identifier": "https://github.com/JonathanRReed/Apple-MCPs/releases/download/v1.0.0/apple-mail.mcpb",
     "fileSha256": "<sha256 hex>",
     "transport": { "type": "stdio" }
   }
   ```

   The download URL must contain the string "mcp" (the `.mcpb` extension
   satisfies this). The registry does not verify the hash, but MCP clients do
   before installing.
3. Bump `version` in `server.json` (and the package versions to match the
   release) and run `mcp-publisher publish` again.

## 5. Optional: automate with GitHub Actions

Per [the registry docs](https://modelcontextprotocol.io/registry/github-actions),
a tag-triggered workflow (`on: push: tags: ["v*"]`) can build, publish to PyPI,
then publish every `server.json`. Key points:

- Use OIDC auth: job permissions `id-token: write`, then
  `mcp-publisher login github-oidc` — no stored registry secret needed.
- PyPI publishing can likewise use a trusted publisher (OIDC) or a
  `PYPI_TOKEN` secret with `uv publish`.
- **Trusted-publisher setup for this monorepo**: PyPI requires a unique
  (owner, repo, workflow, environment) tuple per pending publisher, so each
  of the 12 packages has its own GitHub environment named
  `pypi-<package-name>` (e.g. `pypi-apple-tools-mcp`), and `release.yml`
  publishes through a per-package matrix job bound to that environment.
  When registering the pending publishers on
  https://pypi.org/manage/account/publishing/, set Environment name to
  `pypi-<package-name>` for each entry — a shared environment name will be
  rejected with "matching this configuration has already been registered".
- Optionally rewrite `.version` in each `server.json` from the tag with `jq`
  before publishing.
- For this monorepo, loop the publish step over the 11 server directories,
  mirroring the loop in section 3.

## Notes

- The MCP Registry is in preview; breaking changes or data resets may occur.
- `server.json` files validate against the official schema
  `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`.
- Registry `version` and the PyPI package version are kept in lockstep at
  `1.0.0`; bump both together.
