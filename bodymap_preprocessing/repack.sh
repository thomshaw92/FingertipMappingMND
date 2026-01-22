#!/bin/bash
set -euo pipefail

#######################################
# Argument parsing
#######################################

PARSED=$(getopt --options "ov" \
  --long sub:,sess:,session:,data-dir:,dry-run,keep-files:,overwrite,verbose,custom-dir: \
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
OVERWRITE=false
VERBOSE=false
KEEP_FILES_FILE=""

while true; do
    case "$1" in
        --sub) SUB="$2"; shift 2 ;;
        --session|--sess) SESSION="$2"; shift 2 ;;
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        --dry-run) DRYRUN=true; shift ;;
        --keep-files) KEEP_FILES_FILE="$2"; shift 2 ;;
        --custom-dir) CUSTOM_DIR="$2"; shift 2 ;;
        -o|--overwrite) OVERWRITE=true; shift ;;
        -v|--verbose) VERBOSE=true; shift ;;
        --) shift; break ;;
        *) echo "Unexpected option: $1"; exit 1 ;;
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

ARCHIVE="$RESULT_DIR/contents.zip"
if [[ ! -f "$ARCHIVE" ]]; then
    echo "Error: contents.zip not found in $RESULT_DIR"
    exit 1
fi

#######################################
# Temp files + cleanup
#######################################

ARCHIVE_LIST="$(mktemp)"
TMP_DIR="$(mktemp -d)"

cleanup() {
    rm -f "$ARCHIVE_LIST"
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM HUP QUIT

#######################################
# Read keep / exclude patterns
#######################################

KEEP_PATTERNS=()
EXCLUDE_PATTERNS=()

while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*$ ]] && continue

    expanded=$(SUB="$SUB" SESSION="$SESSION" envsubst <<< "$line")

    if [[ "$expanded" == !* ]]; then
        EXCLUDE_PATTERNS+=("${expanded:1}")
    else
        KEEP_PATTERNS+=("$expanded")
    fi
done < "$KEEP_FILES_FILE"

#######################################
# Keep logic
#######################################

matches_keep_patterns() {
    local rel="$1"
    local keep=false

    for pat in "${KEEP_PATTERNS[@]}"; do
        [[ "$rel" == $pat ]] && keep=true && break
    done

    for pat in "${EXCLUDE_PATTERNS[@]}"; do
        [[ "$rel" == $pat ]] && keep=false && break
    done

    $keep && return 0 || return 1
}

#######################################
# List archive contents
#######################################

unzip -Z1 "$ARCHIVE" > "$ARCHIVE_LIST"

#######################################
# Decide what to extract
#######################################

FILES_TO_EXTRACT=()
SKIPPED_EXISTING=()

while IFS= read -r rel; do
    matches_keep_patterns "$rel" || continue

    # Skip directory entries since they are never overwritten
    [[ "$rel" == */ ]] && continue

    if [[ -e "$RESULT_DIR/$rel" && "$OVERWRITE" == false ]]; then
        SKIPPED_EXISTING+=("$rel")
    else
        FILES_TO_EXTRACT+=("$rel")
    fi
done < "$ARCHIVE_LIST"

#######################################
# Dry-run output
#######################################

if [[ "$DRYRUN" == true ]]; then
    echo "Archive: $ARCHIVE"
    echo

    if (( ${#FILES_TO_EXTRACT[@]} )); then
        echo "Would extract:"
        for f in "${FILES_TO_EXTRACT[@]}"; do
            if [[ -e "$RESULT_DIR/$f" ]]; then
                echo "  OVERWRITE  $f"
            else
                echo "  CREATE     $f"
            fi
        done
    else
        echo "Nothing would be extracted."
    fi

    if (( ${#SKIPPED_EXISTING[@]} )); then
        echo
        echo "Would skip (already exists):"
        printf "  %s\n" "${SKIPPED_EXISTING[@]}"
    fi

    echo
    echo "Would remove unkept files:"
    cd "$RESULT_DIR"
    find . -type f -print0 | while IFS= read -r -d '' path; do
        rel="${path#./}"
        matches_keep_patterns "$rel" || echo "  REMOVE     $rel"
    done

    exit 0
fi

#######################################
# Selective unzip
#######################################

if (( ${#FILES_TO_EXTRACT[@]} )); then
    unzip "$ARCHIVE" "${FILES_TO_EXTRACT[@]}" -d "$TMP_DIR"
fi

#######################################
# Merge into RESULT_DIR
#######################################

RSYNC_OPTS=(-a --prune-empty-dirs --itemize-changes)
$VERBOSE && RSYNC_OPTS+=(-v)

if [[ "$OVERWRITE" == true ]]; then
    RSYNC_OPTS+=(--ignore-times)
else
    RSYNC_OPTS+=(--ignore-existing)
fi

rsync "${RSYNC_OPTS[@]}" "$TMP_DIR/" "$RESULT_DIR/"

#######################################
# Remove unkept files
#######################################

cd "$RESULT_DIR"

find . -type f -print0 | while IFS= read -r -d '' path; do
    rel="${path#./}"

    if ! matches_keep_patterns "$rel"; then
        rm -f -- "$path"
        $VERBOSE && echo "Removed $rel"
    fi
done

#######################################
# Remove empty directories
#######################################

find . -depth -type d -empty | while IFS= read -r dir; do
    [[ "$dir" == "." ]] && continue
    rmdir -- "$dir"
    $VERBOSE && echo "Removed empty dir ${dir#./}"
done

echo "Repacking complete."
