#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SOURCE="$SCRIPT_DIR/terasy_eval"

PLUGIN_DIR="${HOME}/.local/share/QGIS/QGIS3/profiles/default/python/plugins/terasy_eval"

if [[ ! -d "$SOURCE" ]]; then
    echo "CHYBA: Priecinok pluginu neexistuje: $SOURCE"
    exit 1
fi

mkdir -p "$PLUGIN_DIR"

cp -r "$SOURCE"/. "$PLUGIN_DIR"/

echo "Plugin / Plugin installed to:"
echo "$PLUGIN_DIR"
echo "Reštartujte QGIS / Restart QGIS."
