#!/bin/bash

log () {
    echo "$(date '+%Y-%m-%d %H:%M:%S')   $*" | tee -a $LOG_FILE
}

# Parse arguments.
PARSED=$(getopt --options "" --long data-dir:,output-dir:,dry-run,n-threads:,freesurfer-version:,excluded: --name "$0" -- "$@")
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
FREESURFER_VERSION="8.0.0"
EXCLUDED=()

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
        --freesurfer-version)
            FREESURFER_VERSION="$2"
            shift 2
            ;;
        --excluded)
            IFS=' ' read -r -a EXCLUDED <<< "$2"
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

# Set up logging file and a file for failed sessions (for re-running).
# Make sure to include all the arguments and git info for reproducibility.
LOG_FILE=$OUTPUT_DIR/run-recon-all-clinical_$(date "+%Y-%m-%d_%H-%M-%S").log
log "$0 --data-dir $DATA_DIR --output-dir $OUTPUT_DIR --n-threads $NTHREADS --freesurfer-version $FREESURFER_VERSION --excluded ${EXCLUDED[*]}"

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
            $HOME/freesurfer.sh --data-dir $DATA_DIR/mri/bids --free-dir $OUTPUT_DIR --sub $SUB --session $SESSION --n-threads $NTHREADS --freesurfer-version $FREESURFER_VERSION --dry-run
        else
            $HOME/freesurfer.sh --data-dir $DATA_DIR/mri/bids --free-dir $OUTPUT_DIR --sub $SUB --session $SESSION --n-threads $NTHREADS --freesurfer-version $FREESURFER_VERSION 2>> $LOG_FILE
        fi

        if [ $? -ne 0 ]; then
            log "Error processing $SUB/$SESSION"
            echo "$SUB $SESSION" >> "$FAILED_FILE"
        fi

        log "Done with $SUB/$SESSION"
    done
done
