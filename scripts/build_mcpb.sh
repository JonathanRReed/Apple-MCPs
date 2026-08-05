#!/bin/bash
# Build MCPB bundles (.mcpb) for the Apple MCP servers.
#
# Usage:
#   scripts/build_mcpb.sh                          # build all 11 servers
#   scripts/build_mcpb.sh Apple-Calendar-MCP ...   # build specific server folder(s)
#
# Each bundle is staged in a throwaway temp directory (the repo tree is never
# modified) and contains:
#   - the server folder (manifest.json, server.py, pyproject.toml, src/, icon, ...)
#   - vendor/AppleMCPCommon (the local apple-mcp-common workspace package)
#   - for Apple-Tools-MCP: vendor/<every sibling server package> as well
# The staged pyproject.toml is rewritten so `apple-mcp-common` (and, for
# Apple-Tools-MCP, the sibling packages) resolve from the bundle-local vendor/
# directory instead of the uv workspace, making the bundle self-contained: a
# machine with only uv + the bundle can run it via
#   uv run --directory <bundle> server.py
#
# Outputs land in dist/mcpb/<name>-<version>.mcpb and the SHA-256 of every
# bundle is printed (needed for MCP Registry entries).
#
# Requirements: macOS bash 3.2+, tar, shasum, npx (Node). `npx -y
# @anthropic-ai/mcpb pack` validates each manifest as part of packing.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$REPO_DIR/dist/mcpb"

ALL_SERVERS="Apple-Tools-MCP Apple-Calendar-MCP AppleContacts-MCP AppleFiles-MCP AppleMail-MCP AppleMaps-MCP AppleMessages-MCP AppleNotes-MCP AppleReminders-MCP AppleShortcuts-MCP AppleSystem-MCP"
# Domain packages the unified Apple-Tools-MCP server imports at runtime.
SIBLING_SERVERS="AppleMail-MCP Apple-Calendar-MCP AppleReminders-MCP AppleShortcuts-MCP AppleNotes-MCP AppleMessages-MCP AppleContacts-MCP AppleFiles-MCP AppleSystem-MCP AppleMaps-MCP"

STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/apple-mcpb.XXXXXX")"
trap 'rm -rf "$STAGE_ROOT"' EXIT

SHA_SUMMARY=""

die() {
  echo "error: $*" >&2
  exit 1
}

# Folder name -> distribution name from that folder's pyproject.toml.
dist_name_for_folder() {
  case "$1" in
    Apple-Tools-MCP) echo "apple-tools-mcp" ;;
    Apple-Calendar-MCP) echo "apple-calendar-mcp" ;;
    AppleContacts-MCP) echo "apple-contacts-mcp" ;;
    AppleFiles-MCP) echo "apple-files-mcp" ;;
    AppleMail-MCP) echo "apple-mcp-mail" ;;
    AppleMaps-MCP) echo "apple-maps-mcp" ;;
    AppleMessages-MCP) echo "apple-messages-mcp" ;;
    AppleNotes-MCP) echo "apple-mcp-notes" ;;
    AppleReminders-MCP) echo "apple-mcp-reminders" ;;
    AppleShortcuts-MCP) echo "apple-shortcuts-mcp" ;;
    AppleSystem-MCP) echo "apple-system-mcp" ;;
    *) return 1 ;;
  esac
}

# All local workspace packages a staged pyproject may reference, as
# "distribution:Folder" pairs (bash 3.2 has no associative arrays).
WORKSPACE_PKGS="apple-mcp-common:AppleMCPCommon apple-tools-mcp:Apple-Tools-MCP apple-calendar-mcp:Apple-Calendar-MCP apple-contacts-mcp:AppleContacts-MCP apple-files-mcp:AppleFiles-MCP apple-mcp-mail:AppleMail-MCP apple-maps-mcp:AppleMaps-MCP apple-messages-mcp:AppleMessages-MCP apple-mcp-notes:AppleNotes-MCP apple-mcp-reminders:AppleReminders-MCP apple-shortcuts-mcp:AppleShortcuts-MCP apple-system-mcp:AppleSystem-MCP"

# copy_tree <src_dir> <dst_dir>
# Copy a directory tree, dropping build/runtime junk and repo-only launch glue
# (start.sh / requirements.txt reference workspace-relative paths that do not
# exist inside a bundle).
copy_tree() {
  src="$1"
  dst="$2"
  mkdir -p "$dst"
  (
    cd "$src" &&
      COPYFILE_DISABLE=1 tar -cf - \
        --exclude './.venv' --exclude './.venv/*' \
        --exclude './tests' --exclude './tests/*' \
        --exclude './start.sh' \
        --exclude './requirements.txt' \
        --exclude './manifest.dxt.json' \
        --exclude './server.json' \
        --exclude '*__pycache__*' \
        --exclude '*.egg-info*' \
        --exclude '*.pyc' \
        --exclude '.DS_Store' --exclude '*/.DS_Store' \
        --exclude '*.pytest_cache*' \
        --exclude '*.ruff_cache*' \
        .
  ) | (cd "$dst" && tar -xf -)
}

# vendor_pkg <src_dir> <dst_dir>
# Minimal installable copy of a workspace package: pyproject + license/readme
# (both referenced by the pyproject) + src/.
vendor_pkg() {
  src="$1"
  dst="$2"
  mkdir -p "$dst"
  cp "$src/pyproject.toml" "$dst/pyproject.toml"
  if [ -f "$src/LICENSE" ]; then cp "$src/LICENSE" "$dst/LICENSE"; fi
  if [ -f "$src/README.md" ]; then cp "$src/README.md" "$dst/README.md"; fi
  copy_tree "$src/src" "$dst/src"
}

# rewrite_workspace_sources <pyproject> <vendor_prefix>
# Point every `<dist> = { workspace = true }` line in [tool.uv.sources] at a
# bundle-local path (<vendor_prefix>/<Folder>) so the bundle resolves its local
# packages from vendor/ instead of the repo's uv workspace.
rewrite_workspace_sources() {
  f="$1"
  prefix="$2"
  tmp="$f.tmp.$$"
  sedscript="$f.sed.$$"
  : >"$sedscript"
  for pair in $WORKSPACE_PKGS; do
    dn="${pair%%:*}"
    dir="${pair#*:}"
    echo 's|^'"$dn"' = { workspace = true }$|'"$dn"' = { path = "'"$prefix"'/'"$dir"'" }|' >>"$sedscript"
  done
  sed -f "$sedscript" "$f" >"$tmp"
  mv "$tmp" "$f"
  rm -f "$sedscript"
  if grep -q 'workspace = true' "$f"; then
    die "workspace source rewrite failed for $f"
  fi
}

# manifest_field <manifest.json> <field>
# Read a top-level string field from our two-space-indented manifest files.
manifest_field() {
  sed -n 's/^  "'"$2"'": "\(.*\)",*$/\1/p' "$1" | head -1
}

build_one() {
  folder="$1"
  dist_name="$(dist_name_for_folder "$folder")" || die "unknown server folder: $folder"
  src_dir="$REPO_DIR/$folder"
  [ -f "$src_dir/manifest.json" ] || die "missing $src_dir/manifest.json"
  [ -f "$src_dir/server.py" ] || die "missing $src_dir/server.py"

  stage="$STAGE_ROOT/$folder"
  copy_tree "$src_dir" "$stage"
  vendor_pkg "$REPO_DIR/AppleMCPCommon" "$stage/vendor/AppleMCPCommon"

  if [ "$folder" = "Apple-Tools-MCP" ]; then
    # The unified server depends on every sibling domain package; vendor them
    # all so the bundle is self-contained.
    for s in $SIBLING_SERVERS; do
      vendor_pkg "$REPO_DIR/$s" "$stage/vendor/$s"
      rewrite_workspace_sources "$stage/vendor/$s/pyproject.toml" ".."
    done
  fi

  rewrite_workspace_sources "$stage/pyproject.toml" "vendor"

  name="$(manifest_field "$stage/manifest.json" name)"
  version="$(manifest_field "$stage/manifest.json" version)"
  [ -n "$name" ] || die "could not read name from $folder/manifest.json"
  [ -n "$version" ] || die "could not read version from $folder/manifest.json"

  out="$OUT_DIR/$name-$version.mcpb"
  echo "==> Packing $folder -> ${out#"$REPO_DIR"/}"
  npx -y @anthropic-ai/mcpb pack "$stage" "$out"

  sha_line="$(shasum -a 256 "$out")"
  echo "SHA-256: $sha_line"
  SHA_SUMMARY="$SHA_SUMMARY$sha_line\n"
}

main() {
  servers="$ALL_SERVERS"
  if [ "$#" -gt 0 ]; then
    servers="$*"
    for folder in $servers; do
      dist_name_for_folder "$folder" >/dev/null || die "unknown server folder: $folder (expected one of: $ALL_SERVERS)"
    done
  fi

  mkdir -p "$OUT_DIR"

  for folder in $servers; do
    build_one "$folder"
  done

  echo ""
  echo "==> SHA-256 summary (for MCP Registry entries)"
  printf "%b" "$SHA_SUMMARY"
}

main "$@"
