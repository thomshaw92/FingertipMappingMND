#!/bin/bash
set -e

# Parse arguments.
PARSED=$(getopt --options "v" --long sub:,sess:,session:,data-dir:,dry-run,keep-files:,verbose,custom-dir: --name "$0" -- "$@")
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
VERBOSE=false
CUSTOM_DIR=""

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
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --custom-dir)
            CUSTOM_DIR="$2"
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
if [[ ( -z "$SUB" || -z "$SESSION" ) && -z "$CUSTOM_DIR" ]]; then
    echo "Error: Both --sub and --sess/--session are required when not using --custom-dir"
    exit 1
fi

# Parse the file that stores filenames to be kept.
if [[ -n "$KEEP_FILES_FILE" ]]; then
    if [[ -f "$KEEP_FILES_FILE" ]]; then
        KEEP_FILES=()
        EXCLUDE_FILES=()
        while IFS= read -r filename || [[ -n $filename ]]; do
            # Remove trailing CR if present (Windows newline characters).
            filename="${filename%$'\r'}"

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
KEEP_FILES+=("contents.zip")

# Where output will be stored.
if [[ -n "$CUSTOM_DIR" ]]; then
    RESULT_DIR=$CUSTOM_DIR
else
    RESULT_DIR=$DATA_DIR/$SUB/$SESSION
fi

zip_flags=(-r -T -v)
if [[ "$VERBOSE" == false ]]; then
    zip_flags+=(-q)
fi

# Needed for matching '*', 'folder*/**', etc.
shopt -s globstar nullglob
if [[ "$DRYRUN" = true ]]; then
    summary="
    cd $RESULT_DIR

    zip ${zip_flags[@]} ./contents.zip ./*

    Summary:
       - Keeping contents.zip"
    while IFS= read -r path; do
        keep=false
        relpath="${path#$RESULT_DIR/}"

        for pattern in "${KEEP_FILES[@]}"; do
            [[ $relpath == $pattern ]] && keep=true && break
        done

        if $keep; then
            for pattern in "${EXCLUDE_FILES[@]}"; do
                [[ $relpath == $pattern ]] && keep=false && break
            done
        fi

        if $keep; then
            summary+="\n       - Keeping ${relpath}"
        else
            [[ "$VERBOSE" == true ]] && summary+="\n       - Removing ${relpath}"

        fi
    done < <(find "$RESULT_DIR" -mindepth 1 -depth)

    printf "%b\n" "$summary"
else
    cd $RESULT_DIR

    # Clean-up to reduce the number of file/inodes (for RDM).
    zip "${zip_flags[@]}" ./contents.zip ./*

    # Traverse all files and directories (deepest first, so empty dirs can be removed after files)
    find . -mindepth 1 -depth | while IFS= read -r path; do
        keep=false

        # Strip leading "./" for matching
        relpath="${path#./}"

        # Check against KEEP_FILES
        for pattern in "${KEEP_FILES[@]}"; do
            [[ $relpath == $pattern ]] && keep=true && break
        done

        # Check against EXCLUDE_FILES (force delete)
        if $keep; then
            for pattern in "${EXCLUDE_FILES[@]}"; do
                [[ $relpath == $pattern ]] && keep=false && break
            done
        fi

        if ! $keep; then
            rm -rf -- "$path"
            [[ "$VERBOSE" == true ]] && echo "Removing $relpath"
        else
            [[ "$VERBOSE" == true ]] && echo "Keeping  $relpath"
        fi
    done
    echo "Cleanup complete."
fi
