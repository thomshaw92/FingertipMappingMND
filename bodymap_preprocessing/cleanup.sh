#!/bin/bash
set -e

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,session:,data-dir:,dry-run,keep-files: --name "$0" -- "$@")
# Terminate script if failed to parse arguments properly.
if [[ $? -ne 0 ]]; then
    echo "Error parsing options" >&2
    exit 1
fi

# Reset the positional parameters to the parsed arguments.
eval set -- "$PARSED"

SUB=""
SESSION=""
DATA_DIR="."
DRYRUN=false
KEEP_FILES=(
        "contents.zip"
        "mri/brain.nii.gz"
        "mri/native.nii.gz"
        "SUMA/std.141.${SUB}_${SESSION}_lh.spec"
        "SUMA/std.141.${SUB}_${SESSION}_rh.spec"
        "SUMA/std.60.${SUB}_${SESSION}_lh.spec"
        "SUMA/std.60.${SUB}_${SESSION}_rh.spec"
        "SUMA/${SUB}_${SESSION}_SurfVol.nii"
    )

# Extract values from arguments. `--` indicates the end of arguments.
while true; do
    case "$1" in
        --sub)
            SUB="$2"
            shift 2
            ;;
        --session|--sess)
            SESSION="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRYRUN=true
            shift
            ;;
        --keep-files)
            KEEP_FILES_FILE="$2"
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Unexpected option: $1"
            exit 1
            ;;
    esac
done

# Check that required arguments are present. If not terminate the script.
if [[ -z "$SUB" || -z "$SESSION" ]]; then
    echo "Error: Both --sub and --sess/--session are required"
    exit 1
fi

# Parse the file that stores filenames to be kept.
if [[ -n "$KEEP_FILES_FILE" ]]; then
    if [[ -f "$KEEP_FILES_FILE" ]]; then
        KEEP_FILES=()
        EXCLUDE_FILES=()
        while IFS= read -r filename; do
            # Skip empty lines or lines that are just whitespace.
            [[ -z "$filename" || "$filename" =~ ^[[:space:]]*$ ]] && continue
            
            # Make sure to evaluate any variables within filenames.
            expanded=$(SUB="$SUB" SESSION="$SESSION" envsubst <<< "$filename")

            # If it starts with '!' it indicates that it should be excluded.
            if [[ "$expanded" == !* ]]; then
                EXCLUDE_FILES+=("${expanded:1}")
            else
                KEEP_FILES+=("$expanded")
            fi
        done < "$KEEP_FILES_FILE"
    else
        echo "Error: File '$KEEP_FILES_FILE' does not exist."
        exit 1
    fi
fi

# Where output will be stored.
RESULT_DIR=$DATA_DIR/$SUB/$SESSION
# Set up the temp dir and make sure it is deleted afterwards. Check that it was
# actually created as well.
TEMP_DIR=$(mktemp -d --tmpdir="$DATA_DIR")
trap 'rm -rf "$TEMP_DIR"' EXIT
if [[ ! -d "$TEMP_DIR" ]]; then
    echo "Temp dir was not created: ${TEMP_DIR} does not exist or is not a folder."
    exit 1
fi

if [[ "$DRYRUN" = true ]]; then
    summary="
    shopt -s globstar nullglob
    cd $RESULT_DIR

    zip -r ./contents.zip ./*

    find \"./\" -mindepth 1 -not -path "$TEMP_DIR*" -exec rm -rf {} +

    cp -r $TEMP_DIR/* ./ 2>/dev/null

    These files should be kept:"
    shopt -s globstar nullglob
    for pattern in "${KEEP_FILES[@]}"; do
        matches=($RESULT_DIR/$pattern)
        if [[ ${#matches[@]} -eq 0 ]]; then
            SUMMARY+="\n    - $pattern (not matched)"
            continue
        fi
        for file in "${matches[@]}"; do
            preserve=true
            for exclude_pattern in "${EXCLUDE_FILES[@]}"; do
                # echo "${file#$RESULT_DIR/}"
                if [[ "${file#$RESULT_DIR/}" == $exclude_pattern ]]; then
                    preserve=false
                    break
                fi
            done
            if [[ $preserve = false ]]; then
                summary+="\n    - ${file#$RESULT_DIR/} (excluded)"
            elif [[ -e $file ]]; then
                summary+="\n    - ${file#$RESULT_DIR/}"
            else
                summary+="\n    - ${file#$RESULT_DIR/} (not found)"
            fi
        done
    done
    summary+="\n"

    printf "$summary"
else
    # Needed for matching '*', 'folder*/**', etc.
    shopt -s globstar nullglob
    cd $RESULT_DIR

    # Clean-up to reduce the number of file/inodes (for RDM).
    zip -r ./contents.zip ./*

    for pattern in "${KEEP_FILES[@]}"; do
        matches=($pattern)
        if [[ ${#matches[@]} -eq 0 ]]; then
            echo "WARNING: No matches for pattern '$pattern'"
            continue
        fi

        for file in "${matches[@]}"; do
            # Check is this file also matches any of the exclusion patterns. If
            # it does, do not preserve it.
            preserve=true
            for exclude_pattern in "${EXCLUDE_FILES[@]}"; do
                if [[ $file == $exclude_pattern ]]; then
                    preserve=false
                    break
                fi
            done
            if [[ $preserve = false ]]; then
                continue
            fi

            # Full paths (without *) get matched by default even if the file
            # does not exist. Therefore, checking for existence is needed.
            if [[ -e $file ]]; then
                echo "Keeping: $file"
                # If the file comes from a folder the folder needs to be created
                # first.
                mkdir -p "$TEMP_DIR/$(dirname $file)"
                cp -r "$file" "$TEMP_DIR/$file"
            else
                echo "WARNING: '$file' not found, skipping."
            fi
        done
    done

    echo "Deleting all contents in $PWD"
    find "./" -mindepth 1 -not -path "$TEMP_DIR*" -exec rm -rf {} +

    echo "Restoring kept files from $TEMP_DIR"
    cp -r $TEMP_DIR/* ./ 2>/dev/null

    echo "Cleanup complete."
fi
