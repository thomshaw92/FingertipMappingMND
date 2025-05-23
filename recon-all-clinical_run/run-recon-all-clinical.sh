#!/bin/bash

log () {
    echo "$(date '+%Y-%m-%d %H:%M:%S')   $*" | tee -a $LOG_FILE
}

# Parse arguments.
PARSED=$(getopt --options "" --long data-dir:,output-dir:,dry-run,n-threads:,modules:,excluded:,keep-files: --name "$0" -- "$@")
# Terminate script if failed to parse arguments properly.
if [[ $? -ne 0 ]]; then
    echo "Error parsing options" >&2
    exit 1
fi

# Reset the positional parameters to the parsed arguments.
eval set -- "$PARSED"

DATA_DIR="."
OUTPUT_DIR=""
DRYRUN=false
# Use the max amount of available threads as the default value.
NTHREADS=`nproc`
EXCLUDED=()
MODULES=( "freesurfer/8.0.0" "afni/24.3.00" )
KEEP_FILES_FILE=""

# Extract values from arguments. `--` indicates the end of arguments.
while true; do
    case "$1" in
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
        --n-threads)
            NTHREADS="$2"
            shift 2
            ;;
        --modules)
            IFS=' ' read -r -a MODULES <<< "$2"
            shift 2
            ;;
        --excluded)
            IFS=' ' read -r -a EXCLUDED <<< "$2"
            shift 2
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

# Make sure to use the DATA_DIR value that was sepcified in the arguments.
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="${DATA_DIR}/mri/bids/derivatives/recon-all-clinical"
fi

# Check that a file that contains files to keep exists. If no file was provided
# create a temp file and delete it if the script exits or terminates.
if [[ -n "$KEEP_FILES_FILE" && ! -f "$KEEP_FILES_FILE" ]]; then
    echo "The file provided in --keep-files could not be found: ${KEEP_FILES_FILE}"
    exit 1
elif [[ -z "$KEEP_FILES_FILE" ]]; then
    KEEP_FILES_FILE=$(mktemp --tmpdir="$PWD")
    trap 'rm -f "$KEEP_FILES_FILE"' EXIT INT TERM
    cat <<EOF > "$KEEP_FILES_FILE"
contents.zip
mri/brain.nii.gz
mri/native.nii.gz
SUMA/std.141.\${SUB}_\${SESSION}_lh.spec
SUMA/std.141.\${SUB}_\${SESSION}_rh.spec
SUMA/std.60.\${SUB}_\${SESSION}_lh.spec
SUMA/std.60.\${SUB}_\${SESSION}_rh.spec
SUMA/\${SUB}_\${SESSION}_SurfVol.nii
EOF
fi

 # Make sure to check that the modules are available. Check all the requested
 # modules before terminating the script.
MODULE_ERROR=false
for mod in $MODULES; do
    # Provide a better error message if the module does not exist.
    if ! module avail $mod 2>&1 | grep -q "$mod"; then
        echo "Module ${mod} could not be found. Make sure that it is downloaded
    and that you used 'module use <path/to/neurodesk/containers>' before running
    this."
        MODULE_ERROR=true
    fi
done
if [[ "$MODULE_ERROR" = true ]]; then
    exit 1
fi
# Extract versions from the modules.
for mod in "${MODULES[@]}"; do
    name="${mod%%/*}"
    version="${mod##*/}"

    case "$name" in
        freesurfer)
            FREESURFER_VERSION="$version"
            ;;
        afni)
            AFNI_VERSION="$version"
            ;;
        *)
            echo "Warning: Undefined module $name"
            ;;
    esac
done

# Set up logging file and a file for failed sessions (for re-running).
# Make sure to include all the arguments and git info for reproducibility.
LOG_FILE=$OUTPUT_DIR/run-recon-all-clinical_$(date "+%Y-%m-%d_%H-%M-%S").log
log "$0 --data-dir $DATA_DIR --output-dir $OUTPUT_DIR --n-threads $NTHREADS --modules ${MODULES[*]} --excluded ${EXCLUDED[*]}"

GIT_URL=$(git config --get remote.origin.url)
if [[ -z "$GIT_URL" ]]; then
    log "No git information"
else
    COMMIT=$(git rev-parse HEAD)
    GIT_PATH=$(git ls-files --full-name "$0")
    if [[ -z "$GIT_PATH" ]]; then
        GIT_PATH="<$(basename $0) - not added to git yet>"
    fi
    log "${GIT_URL%.git}/blob/$COMMIT/$GIT_PATH"
fi

echo "" >> $LOG_FILE

FAILED_FILE=$OUTPUT_DIR/run-recon-all-clinical-failed_$(date "+%Y-%m-%d_%H-%M-%S").txt
# Make sure that each run starts with an empty failed session file.
> $FAILED_FILE

for SUBJECT_DIR in "$DATA_DIR"/mri/bids/sub-*; do
    # Get subject number.
    SUB=$(basename "$SUBJECT_DIR")

    if [[ " ${EXCLUDED[*]} " =~ " $SUB " ]]; then
        log "Skipping excluded subject: $SUB"
        continue
    fi

    for SESSION_DIR in "$SUBJECT_DIR"/ses-*; do
        # Get session number.
        SESSION=$(basename "$SESSION_DIR")

        # These sessions should have incomplete/invalid data.
        if [[ "$SESSION" == "ses-00" ]]; then
            log "Skipping $SUB/$SESSION (00 are not valid sessions)"
            continue
        fi

        log "Starting $SUB/$SESSION"

        # Run processing but make sure that any errors are recorded in the
        # log file.
        if [ "$DRYRUN" = true ]; then
            ./freesurfer.sh --data-dir $DATA_DIR/mri/bids --output-dir $OUTPUT_DIR --sub $SUB --session $SESSION --n-threads $NTHREADS --freesurfer-version $FREESURFER_VERSION --dry-run
            ./suma.sh --data-dir $DATA_DIR/mri/bids --output-dir $OUTPUT_DIR --sub $SUB --session $SESSION --afni-version $AFNI_VERSION --dry-run
            ./cleanup.sh --data-dir $DATA_DIR/mri/bids --output-dir $OUTPUT_DIR --sub $SUB --session $SESSION --keep-files $KEEP_FILES_FILE --dry-run
        else
            ./freesurfer.sh --data-dir $DATA_DIR/mri/bids --output-dir $OUTPUT_DIR --sub $SUB --session $SESSION --n-threads $NTHREADS --freesurfer-version $FREESURFER_VERSION 2>> $LOG_FILE
            ./suma.sh --data-dir $DATA_DIR/mri/bids --output-dir $OUTPUT_DIR --sub $SUB --session $SESSION --afni-version $AFNI_VERSION 2>> $LOG_FILE
            ./cleanup.sh --data-dir $DATA_DIR/mri/bids --output-dir $OUTPUT_DIR --sub $SUB --session $SESSION --keep-files $KEEP_FILES_FILE 2>> $LOG_FILE
        fi

        if [ $? -ne 0 ]; then
            log "Error processing $SUB/$SESSION"
            echo "$SUB $SESSION" >> "$FAILED_FILE"
        fi

        log "Done with $SUB/$SESSION"
    done
done
