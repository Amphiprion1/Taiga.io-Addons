#!/bin/sh
set -eu
# Build-time fan-out: addons.txt is the single enable switch (AD-9).
# Usage: install-enabled-addons.sh <back|front>

ROLE="${1:?usage: install-enabled-addons.sh back|front}"
ADDONS="${TAIGA_ADDONS_TXT:-/opt/taiga-addons/addons.txt}"
SRC="${TAIGA_ADDONS_SRC:-/opt/taiga-addons/src}"
BACK_DEST="${TAIGA_BACK_DEST:-/taiga-back}"
FRONT_DEST="${TAIGA_FRONT_DEST:-/usr/share/nginx/html/plugins}"

if [ ! -f "$ADDONS" ]; then
    echo "install-enabled-addons: missing addon registry $ADDONS" >&2
    exit 1
fi
if [ ! -d "$SRC" ]; then
    echo "install-enabled-addons: missing addon tree $SRC" >&2
    exit 1
fi

while IFS= read -r raw || [ -n "$raw" ]; do
    line=${raw%%#*}
    line=$(printf '%s\n' "$line" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$line" ] && continue
    printf '%s\n' "$line" | grep -Eq '^[a-z][a-z0-9_]*$' || {
        echo "install-enabled-addons: invalid slug: $line" >&2
        exit 1
    }
    case "$ROLE" in
        back)
            pkg="$SRC/$line/back/taiga_contrib_$line"
            dest="$BACK_DEST/taiga_contrib_$line"
            if [ ! -d "$pkg" ]; then
                echo "install-enabled-addons: missing back package $pkg" >&2
                exit 1
            fi
            cp -a "$pkg" "$dest"
            ;;
        front)
            plugin="$SRC/$line/front"
            dest="$FRONT_DEST/$line"
            if [ ! -d "$plugin" ]; then
                echo "install-enabled-addons: missing front plugin $plugin" >&2
                exit 1
            fi
            mkdir -p "$dest"
            cp -a "$plugin"/. "$dest"/
            ;;
        *)
            echo "install-enabled-addons: role must be back or front" >&2
            exit 1
            ;;
    esac
done < "$ADDONS"
