#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <plugin-dir-name> <MAJOR.MINOR.PATCH>" >&2
  exit 1
fi

PLUGIN_NAME="$1"
VERSION="$2"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Version must be MAJOR.MINOR.PATCH" >&2
  exit 1
fi

if [ ! -d "$PLUGIN_NAME" ]; then
  echo "Plugin directory '$PLUGIN_NAME' not found" >&2
  exit 1
fi

# Determine main plugin file
case "$PLUGIN_NAME" in
  "featured-artists-standardizer")
    FILE="$PLUGIN_NAME/plugin.py"
    ;;
  "file-collision-protection")
    FILE="$PLUGIN_NAME/plugin.py"
    ;;
  "asciifier")
    FILE="$PLUGIN_NAME/plugin.py"
    ;;
  *)
    echo "Unknown plugin '$PLUGIN_NAME'" >&2
    exit 1
    ;;
fi

if [ ! -f "$FILE" ]; then
  echo "Plugin file '$FILE' not found" >&2
  exit 1
fi

# Update PLUGIN_VERSION in the plugin file
perl -pi -e "s/^(PLUGIN_VERSION\s*=\s*[\'\"])([^\'\"]+)([\'\"])$/\1$VERSION\3/" "$FILE"

git diff -- "$FILE"

echo "About to commit and tag $PLUGIN_NAME at version $VERSION"

git add "$FILE"
git commit -m "chore($PLUGIN_NAME): release v$VERSION"

git tag "${PLUGIN_NAME}-v${VERSION}"

git push origin HEAD

git push origin "${PLUGIN_NAME}-v${VERSION}"
