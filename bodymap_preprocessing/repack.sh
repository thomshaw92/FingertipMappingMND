#!/bin/bash
set -e

# Parse arguments.
PARSED=$(getopt --options "o" --long sub:,sess:,session:,repack-dir:,dry-run,keep-files:,overwrite --name "$0" -- "$@")
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
# Controls overwriting during unzipping. '-n' means no overwriting.
UNZIP=-n

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
        -o|--overwrite)
            UNZIP=-o
            shift
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

# For overwriting option to be used.
export UNZIP

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

if [[ "$DRYRUN" = true ]]; then
    summary="
    cd $RESULT_DIR

    unzip_output=\$(unzip -n contents.zip \"${KEEP_FILES[@]}\" -x \"${EXCLUDE_FILES[@]}\" 2>&1)

    These files should be removed:"
    for file in $(find $RESULT_DIR -type f,d -printf '%P\n'); do
        # Check whether the file fits a pattern. If it also fits an exclusion
        # pattern then remove it.
        remove=true
        for pattern in "${KEEP_FILES[@]}"; do
            if [[ "${file#$RESULT_DIR/}" == $pattern ]]; then
                remove=false
                break
            fi
        done
        for pattern in "${EXCLUDE_FILES[@]}"; do
            if [[ ${file#$RESULT_DIR/} == $pattern ]]; then
                remove=true
                break
            fi
        done

        if [[ $remove = true ]]; then
            summary+="\n    - ${file#$RESULT_DIR/}"
        fi
    done
    summary+="\n"

    printf "$summary"
else
    cd $RESULT_DIR

    unzip_output=$(unzip contents.zip "${KEEP_FILES[@]}" -x "${EXCLUDE_FILES[@]}" 2>&1)
    # Use a nicer message for files that are not found.
    unzip_output=$(sed -E 's/caution: filename not matched:  (.+)/WARNING: File pattern "\1" not found in the archive./' <<< $unzip_output)
    unzip_output=$(sed -E 's/caution: excluded filename not matched:  (.+)/WARNING: Excluded file pattern "\1" not found in the archive./' <<< $unzip_output)
    echo "$unzip_output"

    for file in $(find . -type f,d -printf '%P\n'); do
        # Check whether the file fits a pattern. If it also fits an exclusion
        # pattern then remove it.
        remove=true
        for pattern in "${KEEP_FILES[@]}"; do
            if [[ $file == $pattern ]]; then
                remove=false
                break
            fi
        done
        for pattern in "${EXCLUDE_FILES[@]}"; do
            if [[ $file == $pattern ]]; then
                remove=true
                break
            fi
        done

        if [[ $remove = true ]]; then
            # Use '-r' in case 'file' is a folder.
            rm -r $file
        fi
    done
fi
