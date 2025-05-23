#!/bin/bash

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,session:,data-dir:,output-dir:,dry-run,afni-version: --name "$0" -- "$@")
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
AFNI_VERSION="24.3.00"

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
        --afni-version)
            AFNI_VERSION="$2"
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

# Setting this env variable is strongly recommended but I don't understand why.
# It works even without it.
# SINGULARITY_BINDPATH=$OUTPUT_DIR,$BASE_DIR,$SINGULARITY_BINDPATH
# echo $SINGULARITY_BINDPATH

MODULE=afni/$AFNI_VERSION
# Provide a better error message if the module does not exist.
if ! module avail $MODULE 2>&1 | grep -q "$MODULE"; then
    echo "Module ${MODULE} could not be found. Make sure that it is downloaded
and that you used 'module use <path/to/neurodesk/containers>' before running
this."
    exit 1
fi
module load $MODULE

# Where output will be stored.
RESULT_DIR=$OUTPUT_DIR/output/$SUB/$SESSION

if [[ "$DRYRUN" = true ]]; then
    SUMMARY="
    mkdir -p $RESULT_DIR/SUMA
    mkdir -p $RESULT_DIR/orig
    cp $RESULT_DIR/mri/native.mgz $RESULT_DIR/mri/orig.mgz
    @SUMA_Make_Spec_FS -NIFTI -fspath $RESULT_DIR -sid \"${SUB}_${SESSION}\"
    "

    echo "$SUMMARY"
else
    # Create all the files needed for SUMA.
    mkdir -p $RESULT_DIR/SUMA
    mkdir -p $RESULT_DIR/orig
    cp $RESULT_DIR/mri/native.mgz $RESULT_DIR/mri/orig.mgz
    @SUMA_Make_Spec_FS -NIFTI -fspath $RESULT_DIR -sid "${SUB}_${SESSION}"
fi
