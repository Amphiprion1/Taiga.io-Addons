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
    line=$(printf '%s\n' "$line" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$line" ] && continue
    printf '%s\n' "$line" | grep -Eq '^[a-z][a-z0-9_]*$' || {
        echo "patch-front-conf: invalid slug: $line" >&2
        exit 1
    }
    extra=$(printf '%s\n' "$extra" | jq --arg p "plugins/${line}/${line}.json" '. + [$p]')
done < "$ADDONS"

tmp=$(mktemp)
# Dedup via reduce+index (jq's sort-unique reorders official plugins).
# index($x) != null: jq treats 0 as false, so a hit at position 0 must not append.
jq --argjson extra "$extra" \
    '.contribPlugins = ((.contribPlugins // []) + $extra | reduce .[] as $x ([]; if index($x) != null then . else . + [$x] end))' \
    "$CONF" > "$tmp"
# Overwrite in place so nginx's original mode/owner stay (mktemp is 0600).
cat "$tmp" > "$CONF"
rm -f "$tmp"
