#!/bin/bash

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,session:,data-dir:,fs-dir:,output-dir:,dry-run,n-threads:,fmriprep-version:,fs-license: --name "$0" -- "$@")
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
# A bug was introduced in 25.1.0 that stretched data out of FoV of EPI. It was
# fixed in 25.2.0. Be careful when using any version between those two.
FMRIPREP_VERSION="25.2.3"
# Use the max amount of available threads as the default value.
NTHREADS=`nproc`
FS_LICENSE_FILE="./license.txt"
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
    FS_DIR="${DATA_DIR}/derivatives/long-fastsurfer/output"
fi
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="${DATA_DIR}/derivatives/fmriprep/output"
fi

# Check that required arguments are present. If not terminate the script.
if [[ -z "$SUB" || -z "$SESSION" ]]; then
    echo "Error: Both --sub and --sess/--session are required"
    exit 1
fi

MODULES=( "fmriprep/$FMRIPREP_VERSION" )
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

# This env variable overwrites whatever is passed as `fs-subjects-dir` below.
# Setting it to an empty string then uses the argument value below.
export SINGULARITYENV_SUBJECTS_DIR=""
export APPTAINERENV_SUBJECTS_DIR=""

# FMRIPREP does not like 'sub-' and 'ses-' prefixes.
subno="${SUB#sub-}"
sesno="${SESSION#ses-}"
if [ "$DRYRUN" = true ]; then
    fmriprep_cmd="
    fmriprep --skip_bids_validation
             --participant-label $subno
             --session-label $sesno
             --subject-anatomical-reference unbiased
             --ignore fieldmaps slicetiming
             --output-spaces MNI152NLin2009cAsym
             --force bbr
             --medial-surface-nan
             --skull-strip-fixed-seed
             --skull-strip-template OASIS30ANTs
             --random-seed 12345
             --bold2anat-dof 12
             --use-syn-sdc warn
             --force syn-sdc
             --fs-license-file $FS_LICENSE_FILE
             -w $OUTPUT_DIR/$SUB/$SESSION/wrk-dir
             --write-graph
             --notrack
             --aggregate-session-reports 1
             --fs-subjects-dir $FS_DIR
             --fs-no-resume
             --nthreads $NTHREADS
             $DATA_DIR
             $OUTPUT_DIR
             participant
    "
    echo "$fmriprep_cmd"
else
    fmriprep --skip_bids_validation \
             --participant-label $subno \
             --session-label $sesno \
             --subject-anatomical-reference unbiased \
             --ignore fieldmaps slicetiming \
             --output-spaces MNI152NLin2009cAsym \
             --force bbr \
             --medial-surface-nan \
             --skull-strip-fixed-seed \
             --skull-strip-template OASIS30ANTs \
             --random-seed 12345 \
             --bold2anat-dof 12 \
             --use-syn-sdc warn \
             --force syn-sdc \
             --fs-license-file $FS_LICENSE_FILE \
             -w $OUTPUT_DIR/$SUB/$SESSION/wrk-dir \
             --write-graph \
             --notrack \
             --aggregate-session-reports 1 \
             --fs-subjects-dir $FS_DIR \
             --fs-no-resume \
             --nthreads $NTHREADS \
             $DATA_DIR \
             $OUTPUT_DIR \
             participant
fi