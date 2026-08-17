#!/bin/sh
set -eu
# Runs after official 30_config_env_subst.sh. Mutate contribPlugins only.

CONF="${TAIGA_FRONT_CONF:-/usr/share/nginx/html/conf.json}"
ADDONS="${TAIGA_ADDONS_TXT:-/opt/taiga-addons/addons.txt}"

if [ ! -f "$CONF" ]; then
    echo "patch-front-conf: missing $CONF" >&2
    exit 1
fi
if [ ! -f "$ADDONS" ]; then
    echo "patch-front-conf: missing $ADDONS" >&2
    exit 1
fi

extra="[]"
while IFS= read -r raw || [ -n "$raw" ]; do
    line=${raw%%#*}
    line=$(printf '%s\n' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$line" ] && continue
    extra=$(printf '%s\n' "$extra" | jq --arg p "plugins/${line}/${line}.json" '. + [$p]')
done < "$ADDONS"

tmp=$(mktemp)
jq --argjson extra "$extra" \
    '.contribPlugins = ((.contribPlugins // []) + $extra | unique)' \
    "$CONF" > "$tmp"
mv "$tmp" "$CONF"
