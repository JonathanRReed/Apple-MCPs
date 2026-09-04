# Publishing to PyPI and the MCP Registry

Runbook for publishing the 11 Apple MCP servers to PyPI and the official
[MCP Registry](https://registry.modelcontextprotocol.io) under the
`io.github.JonathanRReed` namespace.

## What ships where

| Component | PyPI | MCP Registry |
| --- | --- | --- |
| `apple-mcp-common` (AppleMCPCommon) | Yes | No, it is a shared library rather than an MCP server |
| The 11 servers (`apple-tools-mcp`, `apple-calendar-mcp`, `apple-contacts-mcp`, `apple-files-mcp`, `apple-mcp-mail`, `apple-maps-mcp`, `apple-messages-mcp`, `apple-mcp-notes`, `apple-mcp-reminders`, `apple-shortcuts-mcp`, `apple-system-mcp`) | Yes | Yes, each server directory has a `server.json` |

The registry hosts metadata only, never artifacts, so PyPI publishing must
happen **before** registry publishing.

Each server's `README.md` starts with an HTML comment like
`<!-- mcp-name: io.github.JonathanRReed/apple-mcp-mail -->`. The registry
verifies PyPI package ownership by finding that exact string in the package's
PyPI description (the README). Do not remove these markers, and make sure the
README is included in the sdist/wheel metadata (it is, via `readme = "README.md"`
in each `pyproject.toml`).

## 0. Bump versions

The suite version lives in ~4 files per package. Bump every copy in one step,
then update `CHANGELOG.md` (move `[Unreleased]` entries under the new
heading), refresh the lockfile, and run the test suites:

```bash
python3 scripts/bump_version.py 1.0.4
uv sync --all-packages
python3 scripts/check_release.py --tag v1.0.4
```

The bump command validates every package before writing any file. It updates
the project, config, manifest, top-level server, and PyPI package versions. It
leaves each checked-in MCPB URL, version, and hash together because those fields
describe an existing release asset. Tagging `vX.Y.Z` after committing triggers
the release workflow.

## 1. Publish packages to PyPI with uv

Order matters: every server requires the same suite version of
`apple-mcp-common`, so publish `AppleMCPCommon` first. The unified server also
requires that suite version of every domain package. The `[tool.uv.sources]`
workspace pins apply only to local development. Built wheels resolve these
packages from PyPI.

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

## 2. Automated registry publication

The tag-triggered release workflow is the default publication path. It waits
for all 12 PyPI uploads, creates the GitHub release, then publishes all 11
generated metadata records to the MCP Registry in sequence.

The registry job downloads the same `release-assets` artifact used for the
GitHub release. It requires exactly 11 `*.server.json` files and validates all
of them before publishing any record. It uses `mcp-publisher` v1.8.1, verifies
the Linux archive against its pinned upstream SHA-256, and authenticates through
GitHub OIDC. The job needs no registry secret or browser session.

## 3. Manual recovery

Use the manual path only to recover from a failed registry job after PyPI and
the GitHub release have succeeded. Download the generated `*.server.json`
assets from that GitHub release. Do not regenerate or edit them during
recovery, since their MCPB URLs and hashes describe the attached release files.

Install `mcp-publisher`:

```bash
brew install mcp-publisher
```

or grab a release binary:

```bash
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher
sudo mv mcp-publisher /usr/local/bin/
```

Authenticate and publish:

GitHub auth grants the `io.github.JonathanRReed/*` namespace (must match the
GitHub account that owns the repo):

```bash
mcp-publisher login github   # device-code flow in the browser
```

Put the downloaded records in `release-metadata/`. Validate all 11 before
publishing any of them, then publish the same files:

```bash
for metadata in release-metadata/*.server.json; do
  mcp-publisher validate "$metadata"
done

for metadata in release-metadata/*.server.json; do
  mcp-publisher publish "$metadata"
done
```

Verify:

```bash
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.JonathanRReed"
```

If publishing fails with "Registry validation failed for package", the PyPI
README marker is missing or does not match the `name` in `server.json`. If it
fails with a permissions error, the logged-in GitHub account does not own the
`JonathanRReed` namespace.

## 4. Updating MCPB packages at release time

Each checked-in `server.json` includes both its PyPI package and a `.mcpb` asset
from an existing release. MCPB entries require the SHA-256 of the exact asset.
Do not change an MCPB package version until the matching bundle exists.

The release workflow builds all 11 bundles, checks that all 12 wheels and
sdists and all 11 bundles are present, and generates one
`<server-directory>.server.json` file per server. Each generated file contains
the exact release URL and SHA-256 for its built bundle. The workflow attaches
those files, the bundles, the wheels, the sdists, and `SHA256SUMS` to the GitHub
release after every PyPI publish succeeds. This makes each checksum directly
verifiable against an attached file.

For a manual release, generate the same metadata only after building every
artifact:

```bash
uv build --all-packages
bash scripts/build_mcpb.sh
python3 scripts/check_release.py --tag vX.Y.Z --artifacts
```

To update and publish registry metadata manually:

1. Open the generated file in `release-metadata/` and verify its MCPB entry
   against the matching bundle and tag.
2. Use that generated metadata as the server's registry document. Its MCPB
   entry has this form:

   ```json
   {
     "registryType": "mcpb",
     "identifier": "https://github.com/JonathanRReed/Apple-MCPs/releases/download/vX.Y.Z/apple-mail-X.Y.Z.mcpb",
     "fileSha256": "<sha256 hex>",
     "transport": { "type": "stdio" }
   }
   ```

   The download URL must contain the string "mcp" (the `.mcpb` extension
   satisfies this). The registry does not verify the hash, but MCP clients do
   before installing.
3. Publish the generated metadata through the release workflow. Use the manual
   recovery steps above only if the registry job fails.

## 5. GitHub Actions authentication

Per [the registry docs](https://modelcontextprotocol.io/registry/github-actions),
the workflow uses GitHub OIDC for registry authentication. Key points:

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
  `pypi-<package-name>` for each entry. A shared environment name will be
  rejected with "matching this configuration has already been registered".
- The registry job consumes generated metadata from `release-assets`. It does
  not publish the older `server.json` files checked into each server directory.

## Notes

- The MCP Registry is in preview; breaking changes or data resets may occur.
- `server.json` files validate against the official schema
  `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`.
- A published registry record should use matching server, PyPI, and MCPB
  versions. Checked-in source metadata may retain the prior MCPB record until
  the next bundle has been built and hashed.
