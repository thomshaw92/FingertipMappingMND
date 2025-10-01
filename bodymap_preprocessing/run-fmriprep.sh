#!/bin/bash

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,session:,data-dir:,fs-dir:,output-dir:,dry-run,n-threads:,fmriprep-version:,fs-license:,fs-version: --name "$0" -- "$@")
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
FMRIPREP_VERSION="25.1.3"
# Use the max amount of available threads as the default value.
NTHREADS=`nproc`
FS_LICENSE_FILE="./license.txt"
FS_VERSION="8.1.0"
FS_DIR=""

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
        --fs-dir)
            FS_DIR="$2"
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
		--fmriprep-version)
			FMRIPREP_VERSION="$2"
			shift 2
			;;
		--fs-license)
			FS_LICENSE_FILE="$2"
			shift 2
			;;
        --fs-version)
			FS_VERSION="$2"
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
if [[ -z "$FS_DIR" ]]; then
    FS_DIR="${DATA_DIR}/derivatives/recon-all/output"
fi
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="${DATA_DIR}/derivatives/fmriprep/output"
fi

# Check that required arguments are present. If not terminate the script.
if [[ -z "$SUB" || -z "$SESSION" ]]; then
    echo "Error: Both --sub and --sess/--session are required"
    exit 1
fi

MODULES=( "fmriprep/$FMRIPREP_VERSION" "freesurfer/$FS_VERSION" )
for mod in "${MODULES[@]}"; do
    # Provide a better error message if the module does not exist.
    if ! module avail $mod 2>&1 | grep -q "$mod"; then
        echo "Module ${mod} could not be found. Make sure that it is downloaded
    and that you used 'module use <path/to/neurodesk/containers>' before running
    this."
        exit 1
    fi
    module load $mod
done

export SINGULARITYENV_FS_ALLOW_DEEP=1
export APPTAINERENV_FS_ALLOW_DEEP=1
mkdir -p $FS_DIR

# This env variable overwrites whatever is passed as `fs-subjects-dir` below.
# Setting it to an empty string then uses the argument value below.
export SINGULARITYENV_SUBJECTS_DIR=""
export APPTAINERENV_SUBJECTS_DIR=""

# FMRIPREP does not like 'sub-' prefix in subject numbers.
subno="${SUB#sub-}"
fmriprep --skip_bids_validation \
         --participant-label $subno \
         --nprocs $NTHREADS \
         --mem 30720 \
         --ignore fieldmaps slicetiming \
         --output-spaces MNI152NLin2009cAsym \
         --force bbr \
         --medial-surface-nan \
         --project-goodvoxels \
         --skull-strip-fixed-seed \
         --random-seed 12345 \
         --fmap-no-demean \
         --use-syn-sdc warn \
         --force syn-sdc \
         --fs-license-file $FS_LICENSE_FILE \
         --fs-subjects-dir $FS_DIR \
         -w $OUTPUT_DIR/$SUB/$SESSION/wrk-dir \
         --write-graph \
         --notrack \
         --aggregate-session-reports 1 \
         $DATA_DIR \
         $OUTPUT_DIR/$SUB/$SESSION \
         participant
