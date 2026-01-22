#!/bin/bash
set -euo pipefail

#######################################
# Argument parsing
#######################################

PARSED=$(getopt --options "v" \
  --long sub:,sess:,session:,data-dir:,dry-run,verbose,custom-dir:,keep-files: \
  --name "$0" -- "$@")

if [[ $? -ne 0 ]]; then
    echo "Error parsing options" >&2
    exit 1
fi

eval set -- "$PARSED"

SUB=""
SESSION=""
DATA_DIR="."
DRYRUN=false
VERBOSE=false
CUSTOM_DIR=""
KEEP_FILES_FILE=""

while true; do
    case "$1" in
        --sub)
            SUB="$2"; shift 2 ;;
        --session|--sess)
            SESSION="$2"; shift 2 ;;
        --data-dir)
            DATA_DIR="$2"; shift 2 ;;
        --dry-run)
            DRYRUN=true; shift ;;
        -v|--verbose)
            VERBOSE=true; shift ;;
        --custom-dir)
            CUSTOM_DIR="$2"; shift 2 ;;
        --keep-files)
            KEEP_FILES_FILE="$2"; shift 2 ;;
        --)
            shift; break ;;
        *)
            echo "Unexpected option: $1"
            exit 1 ;;
    esac
done

#######################################
# Validation
#######################################

if [[ -z "$CUSTOM_DIR" && ( -z "$SUB" || -z "$SESSION" ) ]]; then
    echo "Error: --sub and --session are required unless --custom-dir is used"
    exit 1
fi

if [[ -z "$KEEP_FILES_FILE" || ! -f "$KEEP_FILES_FILE" ]]; then
    echo "Error: --keep-files must point to an existing file"
    exit 1
fi


if [[ -n "$CUSTOM_DIR" ]]; then
    RESULT_DIR="$CUSTOM_DIR"
else
    RESULT_DIR="$DATA_DIR/$SUB/$SESSION"
fi

if [[ ! -d "$RESULT_DIR" ]]; then
    echo "Error: RESULT_DIR does not exist: $RESULT_DIR"
    exit 1
fi

#######################################
# Temp files + cleanup
#######################################

FILTER_EXPANDED="$(mktemp)"
TMP_DIR="$(mktemp -d)"

cleanup() {
    [[ -n "${FILTER_EXPANDED:-}" ]] && rm -f "$FILTER_EXPANDED"
    [[ -n "${TMP_DIR:-}" ]] && rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM HUP QUIT

#######################################
# Prepare rsync filter file
#######################################

# Convert keep file format into rsync filter rules
# Rules:
#   pattern      -> + pattern
#   !pattern     -> - pattern
# Also expand variables like ${SUB}, ${SESSION}
while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*$ ]] && continue

    expanded=$(SUB="$SUB" SESSION="$SESSION" envsubst <<< "$line")

    if [[ "$expanded" == !* ]]; then
        echo "- ${expanded:1}"
    else
        echo "+ $expanded"
    fi
done < "$KEEP_FILES_FILE" > "$FILTER_EXPANDED"

# Allow directory traversal
echo "+ */" >> "$FILTER_EXPANDED"
# Drop everything else
echo "- *" >> "$FILTER_EXPANDED"

#######################################
# Zip contents
#######################################

ZIP_FLAGS=(-r -T)
$VERBOSE || ZIP_FLAGS+=(-q)

# Brackets ensure that this runs in a sub-shell so 'cd' does not affect
# the script.
(
    cd "$RESULT_DIR"
    if [[ "$DRYRUN" == true ]]; then
        echo "zip ${ZIP_FLAGS[*]} contents.zip ./*"
        echo
    else
        zip "${ZIP_FLAGS[@]}" contents.zip ./*
    fi
)

#######################################
# Rsync keep-only tree
#######################################

RSYNC_OPTS=(
    -a
    --prune-empty-dirs
    --filter="merge $FILTER_EXPANDED"
)

$VERBOSE && RSYNC_OPTS+=(-v)
$DRYRUN && RSYNC_OPTS+=(--dry-run)

echo "Summary:"
rsync "${RSYNC_OPTS[@]}" \
    "$RESULT_DIR/" \
    "$TMP_DIR/"

if [[ "$DRYRUN" == true ]]; then
    echo
    echo "Dry run complete. No files were modified."
    exit 0
fi

#######################################
# Replacement
#######################################

echo "Replacing original directory..."
rm -rf "$RESULT_DIR"
mkdir -p "$(dirname "$RESULT_DIR")"
mv "$TMP_DIR" "$RESULT_DIR"

echo "Cleanup complete."
