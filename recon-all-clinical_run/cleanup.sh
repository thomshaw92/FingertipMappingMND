#!/bin/bash
set -e

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,session:,data-dir:,output-dir:,dry-run,keep-files: --name "$0" -- "$@")
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
OUTPUT_DIR=""
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
        --output-dir)
            OUTPUT_DIR="$2"
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

# Make sure to use the DATA_DIR value that was specified in the arguments.
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="${DATA_DIR}/recon-all-clinical"
fi

# Check that required arguments are present. If not terminate the script.
if [[ -z "$SUB" || -z "$SESSION" ]]; then
    echo "Error: Both --sub and --sess/--session are required"
    exit 1
fi

# Parse the file that stores filenames to be kept.
if [[ -n "$KEEP_FILES_FILE" ]]; then
    if [[ -f "$KEEP_FILES_FILE" ]]; then
        KEEP_FILES=()
        while IFS= read -r filename || [[ -n "$filename" ]]; do
            # Skip empty lines or lines that are just whitespace
            [[ -z "$filename" || "$filename" =~ ^[[:space:]]*$ ]] && continue
            
            # Make sure to evaluate any variables within filenames.
            expanded=$(SUB="$SUB" SESSION="$SESSION" envsubst <<< "$filename")
            KEEP_FILES+=("$expanded")
        done < "$KEEP_FILES_FILE"
    else
        echo "Error: File '$KEEP_FILES_FILE' does not exist."
        exit 1
    fi
fi

# Where output will be stored.
RESULT_DIR=$OUTPUT_DIR/output/$SUB/$SESSION
# Set up the temp dir and make sure it is deleted afterwards. Check that it was
# actually created as well.
TEMP_DIR=$(mktemp -d --tmpdir="$OUTPUT_DIR")
trap 'rm -rf "$TEMP_DIR"' EXIT
if [[ ! -d "$TEMP_DIR" ]]; then
    echo "Temp dir was not created: ${TEMP_DIR} does not exist or is not a folder."
    exit 1
fi

if [[ "$DRYRUN" = true ]]; then
    SUMMARY="
    cd $RESULT_DIR

    zip -r ./contents.zip ./*

    find \"./\" -mindepth 1 -not -path "$TEMP_DIR*" -exec rm -rf {} +

    cp -r $TEMP_DIR/* ./ 2>/dev/null

    These files should be kept:"
    for file in "${KEEP_FILES[@]}"; do
        if [[ -f "$RESULT_DIR/$file" ]]; then
            SUMMARY+="\n    - $file"
        else
            SUMMARY+="\n    - $file (not found)"    
        fi
    done
    SUMMARY+="\n"

    printf "$SUMMARY"
else
    cd $RESULT_DIR

    # Clean-up to reduce the number of file/inodes (for RDM).
    zip -r ./contents.zip ./*

    for file in "${KEEP_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            echo "Keeping: $file"
            # If the file comes from a folder the folder needs to be created first.
            mkdir -p "$TEMP_DIR/$(dirname "$file")"
            cp "$file" "$TEMP_DIR/$file"
        else
            echo "Warning: '$file' not found, skipping."
        fi
    done

    echo "Deleting all contents in $PWD"
    find "./" -mindepth 1 -not -path "$TEMP_DIR*" -exec rm -rf {} +

    echo "Restoring kept files from $TEMP_DIR"
    cp -r $TEMP_DIR/* ./ 2>/dev/null

    echo "Cleanup complete."
fi
