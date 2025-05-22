#!/bin/bash

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,session:,data-dir:,output-dir:,dry-run,n-threads:,freesurfer-version: --name "$0" -- "$@")
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
# Use the max amount of available threads as the default value.
NTHREADS=`nproc`
FREESURFER_VERSION=8.0.0

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
        --n-threads)
            NTHREADS="$2"
            shift 2
            ;;
        --freesurfer-version)
            FREESURFER_VERSION="$2"
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
    OUTPUT_DIR="${DATA_DIR}/recon-all-clinical"
fi

# Check that required arguments are present. If not terminate the script.
if [[ -z "$SUB" || -z "$SESSION" ]]; then
    echo "Error: Both --sub and --sess/--session are required"
    exit 1
fi

INPUT_IMAGE="${DATA_DIR}/${SUB}/${SESSION}/anat/${SUB}_${SESSION}_acq-UNIDEN_run-1_T1w.nii.gz"

# Setting this env variable is strongly recommended but I don't understand why.
# It works even without it.
# SINGULARITY_BINDPATH=$OUTPUT_DIR,$BASE_DIR,$SINGULARITY_BINDPATH
# echo $SINGULARITY_BINDPATH

MODULE=freesurfer/$FREESURFER_VERSION
# Provide a better error message if the module does not exist.
if ! module avail $MODULE 2>&1 | grep -q "$MODULE"; then
    echo "Module ${MODULE} could not be found. Make sure that it is downloaded
and that you used 'module use <path/to/neurodesk/containers>' before running
this."
    exit 1
fi
# Set up Freesurfer
module load $MODULE
export FS_ALLOW_DEEP=1
export SINGULARITYENV_FS_ALLOW_DEEP=$FS_ALLOW_DEEP

# Where output will be stored. Freesurfer will create a folder in here with the
# name of the subject as used in the recon-all-clinical command (2nd argument).
SUBJECTS_DIR=$OUTPUT_DIR/output
mkdir -p $SUBJECTS_DIR
export SINGULARITYENV_SUBJECTS_DIR=$SUBJECTS_DIR
RESULT_DIR=$SUBJECTS_DIR/$SUB/$SESSION

if [ "$DRYRUN" = true ]; then
    FREE_COMMAND="
    recon-all-clinical.sh $INPUT_IMAGE
                          $SUB/$SESSION
                          $NTHREADS
                          $SUBJECTS_DIR
    
    mri_convert $RESULT_DIR/mri/brain.mgz $RESULT_DIR/mri/brain.nii.gz
    mri_convert $RESULT_DIR/mri/native.mgz $RESULT_DIR/mri/native.nii.gz
    "
    echo "$FREE_COMMAND"
else
    recon-all-clinical.sh $INPUT_IMAGE      \
                          $SUB/$SESSION     \
                          $NTHREADS         \
                          $SUBJECTS_DIR

    mri_convert $RESULT_DIR/mri/brain.mgz $RESULT_DIR/mri/brain.nii.gz
    mri_convert $RESULT_DIR/mri/native.mgz $RESULT_DIR/mri/native.nii.gz
fi


