#!/bin/bash

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,session:,der-dir:,output-dir:,dry-run,n-threads:,ants-version:,template: --name "$0" -- "$@")
# Terminate script if failed to parse arguments properly.
if [[ $? -ne 0 ]]; then
    echo "Error parsing options" >&2
    exit 1
fi

# Reset the positional parameters to the parsed arguments.
eval set -- "$PARSED"

SUB=""
SESSION=""
DER_DIR="."
OUTPUT_DIR=""
DRYRUN=false
ANTS_VERSION="2.6.0"
# Use the max amount of available threads as the default value.
NTHREADS=`nproc`
TEMPLATE="MNI152_2009_template_SSW_brain.nii.gz"

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
        --der-dir)
            DER_DIR="$2"
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
		--ants-version)
			ANTS_VERSION="$2"
			shift 2
			;;
        --template)
            TEMPLATE="$2"
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
    OUTPUT_DIR="${DER_DIR}/ants/output"
fi

# Check that required arguments are present. If not terminate the script.
if [[ -z "$SUB" || -z "$SESSION" ]]; then
    echo "Error: Both --sub and --sess/--session are required"
    exit 1
fi

MODULE=ants/$ANTS_VERSION
# Provide a better error message if the module does not exist.
if ! module avail $MODULE 2>&1 | grep -q "$MODULE"; then
    echo "Module ${MODULE} could not be found. Make sure that it is downloaded
and that you used 'module use <path/to/neurodesk/containers>' before running
this."
    exit 1
fi
module load $MODULE

# Set up directories
ANAT_SS=$DER_DIR/fastsurfer/output/$SUB/$SESSION/mri/brain.nii.gz

if [ "$DRYRUN" = true ]; then
    ANTS_CMD="
    mkdir -p $OUTPUT_DIR/$SUB/$SESSION/

    antsRegistrationSyN.sh
        -d 3
        -f $TEMPLATE
        -m $ANAT_SS
        -o $OUTPUT_DIR/$SUB/$SESSION/
        -n $NTHREADS
        -j 1
    "
    echo $ANTS_CMD
else
    mkdir -p $OUTPUT_DIR/$SUB/$SESSION/

    antsRegistrationSyN.sh              \
        -d 3                            \
        -f $TEMPLATE                    \
        -m $ANAT_SS                     \
        -o $OUTPUT_DIR/$SUB/$SESSION/   \
        -n $NTHREADS                    \
        -j 1
fi